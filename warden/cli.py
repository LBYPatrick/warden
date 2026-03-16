"""CLI command implementations for Warden."""

import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from warden import display
from warden.config import (
    find_target,
    get_identities,
    get_packages,
    get_tools,
    resolve_ssh_command,
    serialize_config,
    update_packages,
)


def _git_config_set(key: str, value: str, *, dry_run: bool = False) -> None:
    """Set a git config value globally."""
    if dry_run:
        display.info(f"Would set {key} = {value}")
        return
    subprocess.run(
        ["git", "config", "--global", key, value],
        check=True,
        capture_output=True,
    )


def _git_config_unset(key: str, *, dry_run: bool = False) -> None:
    """Unset a git config value globally, ignoring if not set."""
    if dry_run:
        display.info(f"Would unset {key}")
        return
    subprocess.run(
        ["git", "config", "--global", "--unset", key],
        capture_output=True,
    )


def _git_config_get(key: str) -> str | None:
    """Get a git config value globally."""
    result = subprocess.run(
        ["git", "config", "--global", "--get", key],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return None


def cmd_switch(config: dict, target_name: str, *, dry_run: bool = False) -> None:
    """Apply a git identity from config."""
    identities = get_identities(config)
    result = find_target(identities, target_name)
    if result is None:
        display.error(f'Target "{target_name}" not found')
        available = ", ".join(identities.keys())
        display.info(f"Available: {available}")
        sys.exit(1)

    name, target = result
    label = "Dry Run — " if dry_run else ""
    display.banner(f"{label}Switch to {name}")

    start = time.monotonic()

    # user.name
    if "name" in target:
        _git_config_set("user.name", target["name"], dry_run=dry_run)
        if not dry_run:
            display.success(f"user.name = {target['name']}")

    # user.email
    if "email" in target:
        _git_config_set("user.email", target["email"], dry_run=dry_run)
        if not dry_run:
            display.success(f"user.email = {target['email']}")

    # user.signingkey
    if "signing_key" in target:
        expanded = str(Path(target["signing_key"]).expanduser())
        _git_config_set("user.signingkey", expanded, dry_run=dry_run)
        if not dry_run:
            display.success(f"user.signingkey = {expanded}")

        # core.sshCommand
        ssh_cmd = resolve_ssh_command(target["signing_key"])
        if ssh_cmd:
            _git_config_set("core.sshCommand", ssh_cmd, dry_run=dry_run)
            if not dry_run:
                display.success(f"core.sshCommand = {ssh_cmd}")
        else:
            _git_config_unset("core.sshCommand", dry_run=dry_run)
            if not dry_run:
                display.skip("core.sshCommand unset (default key)")

    # gpg format for SSH signing
    _git_config_set("gpg.format", "ssh", dry_run=dry_run)
    if not dry_run:
        display.success("gpg.format = ssh")

    _git_config_set("commit.gpgsign", "true", dry_run=dry_run)
    if not dry_run:
        display.success("commit.gpgsign = true")

    elapsed = time.monotonic() - start
    print()
    if dry_run:
        display.info(f"Would switch to {display.bold(name)} (no changes made)")
    else:
        display.success_timed(f"Switched to {display.bold(name)}", elapsed)


def cmd_list(config: dict) -> None:
    """List all available targets."""
    identities = get_identities(config)
    display.banner("Available Targets")
    for name, target in identities.items():
        email = target.get("email", "")
        uname = target.get("name", "")
        label = f"{display.bold(name)}"
        detail = f"{uname} {display.dim(f'<{email}>')}"
        display.item(f"{label} — {detail}")
    print()


def cmd_show(config: dict, target_name: str | None = None) -> None:
    """Show current git config or a specific target's config."""
    identities = get_identities(config)

    if target_name is None:
        display.banner("Current Git Identity")
        fields = {
            "user.name": _git_config_get("user.name"),
            "user.email": _git_config_get("user.email"),
            "user.signingkey": _git_config_get("user.signingkey"),
            "core.sshCommand": _git_config_get("core.sshCommand"),
            "gpg.format": _git_config_get("gpg.format"),
            "commit.gpgsign": _git_config_get("commit.gpgsign"),
        }
        for key, val in fields.items():
            if val:
                display.kv(key, val)
            else:
                display.kv(key, display.dim("(not set)"))
        print()
        return

    result = find_target(identities, target_name)
    if result is None:
        display.error(f'Target "{target_name}" not found')
        sys.exit(1)

    name, target = result
    display.banner(f"Target: {name}")
    for key, val in target.items():
        expanded = str(Path(val).expanduser()) if key == "signing_key" else val
        display.kv(key, expanded)

    # Show derived ssh command
    if "signing_key" in target:
        ssh_cmd = resolve_ssh_command(target["signing_key"])
        if ssh_cmd:
            display.kv("ssh_command (derived)", ssh_cmd)
        else:
            display.kv("ssh_command (derived)", display.dim("(default key, unset)"))
    print()


def cmd_scan(
    config: dict[str, Any],
    config_path: Path,
    *,
    dry_run: bool = False,
) -> None:
    """Scan the system and update packages/tools in warden.jsonc."""
    from warden.platform_info import detect_platform
    from warden.scanner import scan_system

    display.banner("Scan System Packages")
    start = time.monotonic()

    platform = detect_platform()
    display.info(f"Platform: {display.bold(platform.value)}")
    print()

    scanned = scan_system(platform)

    new_config = update_packages(
        config,
        scanned["packages"],
        scanned["tools"],
    )

    if dry_run:
        print()
        display.info(f"Would write to {config_path}")
        _print_config_summary(new_config)
        return

    config_path.write_text(serialize_config(new_config), encoding="utf-8")

    elapsed = time.monotonic() - start
    print()
    display.success_timed(f"Config written to {config_path}", elapsed)
    _print_config_summary(new_config)


def cmd_apply(
    config: dict[str, Any],
    *,
    force: bool = False,
    dry_run: bool = False,
    use_cn: bool = False,
) -> None:
    """Install packages and tools from warden.jsonc onto the system.

    Skips already-installed items unless force=True.
    """
    from warden import installer
    from warden.platform_info import detect_platform

    label = "Dry Run — " if dry_run else ""
    force_label = " (force)" if force else ""
    cn_label = " [CN]" if use_cn else ""
    display.banner(f"{label}Apply Config{force_label}{cn_label}")
    start = time.monotonic()

    platform = detect_platform()
    display.info(f"Platform: {display.bold(platform.value)}")
    if use_cn:
        display.info("China mirror mode enabled")

    pkgs = get_packages(config)
    tools_list = get_tools(config)

    total_installed = 0
    total_skipped = 0
    all_failed: list[str] = []

    def _apply_section(
        key: str,
        header_name: str,
        items: list[str],
        install_fn: callable,
        **kwargs,
    ) -> None:
        nonlocal total_installed, total_skipped
        if not items:
            return
        print()
        display.header(f"{header_name} ({len(items)})")
        installed, skipped, failed = install_fn(
            items, force=force, dry_run=dry_run, **kwargs
        )
        total_installed += installed
        total_skipped += skipped
        all_failed.extend(f"{key}:{f}" for f in failed)
        if skipped and not dry_run:
            display.skip(f"{skipped} already installed")

    # --- Package managers (order: system managers first, then cross-platform) ---

    # Brew formulae + casks
    brew = pkgs.get("brew", {})
    _apply_section(
        "brew",
        "Homebrew formulae",
        brew.get("formulae", []),
        installer.install_brew_formulae,
        use_cn=use_cn,
    )
    _apply_section(
        "cask",
        "Homebrew casks",
        brew.get("casks", []),
        installer.install_brew_casks,
        use_cn=use_cn,
    )

    # Mac App Store
    _apply_section(
        "mas",
        "Mac App Store",
        pkgs.get("mas", {}).get("apps", []),
        installer.install_mas_apps,
    )

    # Linux system package managers
    _LINUX_MANAGERS = [
        ("apt", "APT", installer.install_apt_packages),
        ("dnf", "DNF", installer.install_dnf_packages),
        ("pacman", "Pacman", installer.install_pacman_packages),
        ("apk", "APK", installer.install_apk_packages),
        ("snap", "Snap", installer.install_snap_packages),
        ("flatpak", "Flatpak", installer.install_flatpak_packages),
    ]
    for key, name, install_fn in _LINUX_MANAGERS:
        section_pkgs = pkgs.get(key, {}).get("packages", [])
        _apply_section(key, f"{name} packages", section_pkgs, install_fn)

    # Cross-platform package managers
    _CROSS_MANAGERS = [
        ("cargo", "Cargo", installer.install_cargo_packages),
        ("npm", "npm global", installer.install_npm_global_packages),
        (
            "pnpm",
            "pnpm global",
            lambda pkgs, **kw: installer.install_pnpm_global_packages(
                pkgs, use_cn=use_cn, **kw
            ),
        ),
        ("pipx", "pipx", installer.install_pipx_packages),
    ]
    for key, name, install_fn in _CROSS_MANAGERS:
        section_pkgs = pkgs.get(key, {}).get("packages", [])
        _apply_section(key, f"{name} packages", section_pkgs, install_fn)

    # Developer tools
    if tools_list:
        print()
        display.header(f"Developer tools ({len(tools_list)})")
        inst, skip, failed = installer.install_tools(
            tools_list, platform, force=force, dry_run=dry_run, use_cn=use_cn
        )
        total_installed += inst
        total_skipped += skip
        all_failed.extend(f"tool:{f}" for f in failed)
        if skip and not dry_run:
            display.skip(f"{skip} already installed")

    elapsed = time.monotonic() - start
    print()
    if dry_run:
        display.info("No changes made (dry run)")
    elif all_failed:
        display.error_timed(
            f"Installed {total_installed}, skipped {total_skipped}, "
            f"failed {len(all_failed)}",
            elapsed,
        )
        for f in all_failed:
            display.error(f"  {f}")
    else:
        display.success_timed(
            f"Installed {total_installed}, skipped {total_skipped}", elapsed
        )


def cmd_install_list() -> None:
    """Show available package managers with install status for the current OS."""
    import shutil

    from warden.platform_info import detect_platform

    platform = detect_platform()

    # (prefix, display_name, binary, platforms)
    _ALL_MANAGERS = [
        ("brew", "Homebrew formulae", "brew", ["macos", "linux"]),
        ("cask", "Homebrew casks", "brew", ["macos", "linux"]),
        ("mas", "Mac App Store", "mas", ["macos"]),
        ("apt", "APT", "apt-get", ["linux"]),
        ("dnf", "DNF", "dnf", ["linux"]),
        ("pacman", "Pacman", "pacman", ["linux"]),
        ("apk", "APK", "apk", ["linux"]),
        ("snap", "Snap", "snap", ["linux"]),
        ("flatpak", "Flatpak", "flatpak", ["linux"]),
        ("cargo", "Cargo (Rust)", "cargo", ["macos", "linux"]),
        ("npm", "npm (global)", "npm", ["macos", "linux"]),
        ("pnpm", "pnpm (global)", "pnpm", ["macos", "linux"]),
        ("pipx", "pipx (Python)", "pipx", ["macos", "linux"]),
        ("tool", "Developer tools", None, ["macos", "linux"]),
    ]

    display.banner("Available Package Managers")
    display.info(f"Platform: {display.bold(platform.value)}")
    print()

    for prefix, name, binary, platforms in _ALL_MANAGERS:
        if platform.value not in platforms:
            continue

        if binary is None:
            # tool — always available
            status = display.green("available")
        elif shutil.which(binary):
            status = display.green("installed")
        else:
            status = display.dim("not found")

        display.kv(display.bold(prefix), f"{name} [{status}]")

    print()
    display.info(
        "Usage: warden install " + display.dim("MANAGER:PKG [MANAGER:PKG ...]")
    )
    display.info("Example: warden install brew:ripgrep cask:firefox cargo:bat")
    print()
    display.header("Options")
    display.kv(display.cyan("--save"), "Also add installed packages to warden.jsonc")
    display.kv(display.cyan("--any"), "Bypass OS platform check (allow any manager)")
    display.kv(display.cyan("--no-color"), "Disable colored output")
    display.kv(display.cyan("--dry-run"), "Preview without making changes")
    print()


def cmd_install(
    specs: list[str],
    *,
    config_path: Path | None = None,
    save: bool = False,
    allow_any: bool = False,
    dry_run: bool = False,
    use_cn: bool = False,
) -> None:
    """Install packages via manager:package syntax.

    Filters managers to those supported on the current OS unless --any.
    Auto-installs missing manager binaries when possible.
    """
    import shutil

    from warden import installer
    from warden.platform_info import detect_platform

    display.banner("Install Packages")
    start = time.monotonic()

    platform = detect_platform()

    # Parse specs into {manager: [packages]}
    grouped: dict[str, list[str]] = {}
    for spec in specs:
        if ":" not in spec:
            display.error(
                f'Invalid spec "{spec}" — use manager:package (e.g. brew:ripgrep)'
            )
            sys.exit(1)
        mgr, pkg = spec.split(":", 1)
        mgr = mgr.lower()
        if not pkg:
            display.error(f'Empty package name in "{spec}"')
            sys.exit(1)
        grouped.setdefault(mgr, []).append(pkg)

    # Manager definitions: (install_fn, config_key, sub_key, platforms, auto_install_hint)
    # auto_install_hint: how to get the manager if missing (None = skip)
    _INSTALL_MAP: dict[str, tuple[callable, str, str | None, list[str], str | None]] = {
        "brew": (
            lambda pkgs, **kw: installer.install_brew_formulae(
                pkgs, use_cn=use_cn, **kw
            ),
            "brew",
            "formulae",
            ["macos", "linux"],
            None,
        ),
        "cask": (
            lambda pkgs, **kw: installer.install_brew_casks(pkgs, use_cn=use_cn, **kw),
            "brew",
            "casks",
            ["macos", "linux"],
            None,
        ),
        "mas": (
            installer.install_mas_apps,
            "mas",
            "apps",
            ["macos"],
            "brew install mas",
        ),
        "apt": (installer.install_apt_packages, "apt", "packages", ["linux"], None),
        "dnf": (installer.install_dnf_packages, "dnf", "packages", ["linux"], None),
        "pacman": (
            installer.install_pacman_packages,
            "pacman",
            "packages",
            ["linux"],
            None,
        ),
        "apk": (installer.install_apk_packages, "apk", "packages", ["linux"], None),
        "snap": (
            installer.install_snap_packages,
            "snap",
            "packages",
            ["linux"],
            "sudo apt install snapd",
        ),
        "flatpak": (
            installer.install_flatpak_packages,
            "flatpak",
            "packages",
            ["linux"],
            "sudo apt install flatpak",
        ),
        "cargo": (
            installer.install_cargo_packages,
            "cargo",
            "packages",
            ["macos", "linux"],
            None,
        ),
        "npm": (
            installer.install_npm_global_packages,
            "npm",
            "packages",
            ["macos", "linux"],
            None,
        ),
        "pnpm": (
            lambda pkgs, **kw: installer.install_pnpm_global_packages(
                pkgs, use_cn=use_cn, **kw
            ),
            "pnpm",
            "packages",
            ["macos", "linux"],
            None,
        ),
        "pipx": (
            installer.install_pipx_packages,
            "pipx",
            "packages",
            ["macos", "linux"],
            "brew install pipx",
        ),
        "tool": (
            lambda pkgs, **kw: installer.install_tools(
                pkgs, platform, use_cn=use_cn, **kw
            ),
            "tools",
            None,
            ["macos", "linux"],
            None,
        ),
    }

    # Binary name for each manager (for auto-install check)
    _MGR_BINARY: dict[str, str] = {
        "brew": "brew",
        "cask": "brew",
        "mas": "mas",
        "apt": "apt-get",
        "dnf": "dnf",
        "pacman": "pacman",
        "apk": "apk",
        "snap": "snap",
        "flatpak": "flatpak",
        "cargo": "cargo",
        "npm": "npm",
        "pnpm": "pnpm",
        "pipx": "pipx",
        "tool": "",  # tools don't need a single binary
    }

    total_installed = 0
    all_failed: list[str] = []
    saved_entries: dict[str, Any] = {}

    for mgr, pkgs in grouped.items():
        if mgr not in _INSTALL_MAP:
            display.error(
                f'Unknown manager "{mgr}". Available: {", ".join(sorted(_INSTALL_MAP))}'
            )
            sys.exit(1)

        install_fn, config_key, sub_key, platforms, auto_hint = _INSTALL_MAP[mgr]

        # Platform check
        if not allow_any and platform.value not in platforms:
            display.error(
                f'Manager "{mgr}" is not available on {platform.value} '
                f"(use --any to override)"
            )
            sys.exit(1)

        # Auto-install missing manager binary
        binary = _MGR_BINARY.get(mgr, "")
        if binary and not shutil.which(binary):
            if auto_hint and not dry_run:
                display.info(f"{mgr} not found, installing via: {auto_hint}")
                ok, output = installer._run_shell(auto_hint, timeout=300)
                if not ok:
                    display.error(
                        f"Failed to install {mgr}: {output.splitlines()[-1] if output else 'unknown'}"
                    )
                    all_failed.extend(f"{mgr}:{p}" for p in pkgs)
                    continue
                display.success(f"Installed {mgr}")
            elif auto_hint and dry_run:
                display.info(f"Would install {mgr} via: {auto_hint}")

        print()
        display.header(f"{mgr} ({len(pkgs)})")
        installed, _skipped, failed = install_fn(pkgs, dry_run=dry_run)
        total_installed += installed
        all_failed.extend(f"{mgr}:{f}" for f in failed)

        # Track successfully installed for --save
        if save and installed > 0:
            successful = [p for p in pkgs if p not in failed]
            if sub_key:
                saved_entries.setdefault(config_key, {}).setdefault(sub_key, []).extend(
                    successful
                )
            else:
                saved_entries.setdefault(config_key, []).extend(successful)

    # Save to config if requested
    if save and saved_entries and not dry_run and config_path:
        _save_to_config(config_path, saved_entries)

    elapsed = time.monotonic() - start
    print()
    if dry_run:
        display.info("No changes made (dry run)")
    elif all_failed:
        display.error_timed(
            f"Installed {total_installed}, failed {len(all_failed)}", elapsed
        )
        for f in all_failed:
            display.error(f"  {f}")
    else:
        display.success_timed(f"Installed {total_installed}", elapsed)
        if save and config_path:
            display.success(f"Saved to {config_path}")


def _save_to_config(config_path: Path, entries: dict[str, Any]) -> None:
    """Merge installed packages into existing warden.jsonc."""
    import json5

    if config_path.is_file():
        try:
            config = json5.loads(config_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            config = {}
    else:
        config = {}

    packages = config.get("packages", {})

    for key, value in entries.items():
        if key == "tools":
            # Tools is a top-level list
            existing_tools = config.get("tools", [])
            if isinstance(value, list):
                merged = sorted(set(existing_tools) | set(value))
                config["tools"] = merged
        elif isinstance(value, dict):
            # Package manager section
            existing_section = packages.get(key, {})
            for sub_key, new_pkgs in value.items():
                existing_list = existing_section.get(sub_key, [])
                merged = sorted(set(existing_list) | set(new_pkgs))
                existing_section[sub_key] = merged
            packages[key] = existing_section

    if packages:
        config["packages"] = packages

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(serialize_config(config), encoding="utf-8")


def cmd_update(
    *, branch: str | None = None, dry_run: bool = False, use_cn: bool = False
) -> None:
    """Self-update warden by pulling latest from git and reinstalling."""
    cn_label = " [CN]" if use_cn else ""
    display.banner(f"Update Warden{cn_label}")
    start = time.monotonic()

    repo_root = Path(__file__).resolve().parent.parent

    # Detect current branch if not specified
    if branch is None:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            cwd=repo_root,
        )
        if result.returncode != 0:
            display.error("Failed to detect current branch")
            sys.exit(1)
        branch = result.stdout.strip()

    display.info(f"Repository: {repo_root}")
    display.info(f"Branch: {display.bold(branch)}")

    # Check for uncommitted changes
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    if result.stdout.strip():
        display.warn("Uncommitted changes detected — pulling may cause conflicts")

    if dry_run:
        display.info(f"Would run: git pull origin {branch}")
        display.info("Would run: make install")
        return

    # Pull
    display.step(1, 2, f"Pulling from origin/{branch}")
    result = subprocess.run(
        ["git", "pull", "origin", branch],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    if result.returncode != 0:
        display.error(f"git pull failed:\n{result.stderr.strip()}")
        sys.exit(1)

    pull_output = result.stdout.strip()
    if "Already up to date" in pull_output:
        display.success("Already up to date")
    else:
        display.success("Pulled latest changes")

    # Reinstall
    display.step(2, 2, "Reinstalling")
    install_env = None
    if use_cn:
        import os

        from warden.cn import UV_CN_ENV

        install_env = {**os.environ, **UV_CN_ENV}
    result = subprocess.run(
        ["make", "install"],
        capture_output=True,
        text=True,
        cwd=repo_root,
        env=install_env,
    )
    if result.returncode != 0:
        display.error(f"make install failed:\n{result.stderr.strip()}")
        sys.exit(1)
    display.success("Reinstalled")

    elapsed = time.monotonic() - start
    print()
    display.success_timed("Warden updated", elapsed)


def _print_config_summary(config: dict[str, Any]) -> None:
    """Print a summary of config contents."""
    pkgs = get_packages(config)
    tools = get_tools(config)

    brew = pkgs.get("brew", {})
    formulae_count = len(brew.get("formulae", []))
    cask_count = len(brew.get("casks", []))
    apt_count = len(pkgs.get("apt", {}).get("packages", []))

    if formulae_count or cask_count:
        display.kv("Homebrew", f"{formulae_count} formulae, {cask_count} casks")
    if apt_count:
        display.kv("APT", f"{apt_count} packages")
    if tools:
        display.kv("Tools", ", ".join(tools))
    identities = get_identities(config)
    if identities:
        display.kv("Identities", ", ".join(identities.keys()))
