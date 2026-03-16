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
) -> None:
    """Install packages and tools from warden.jsonc onto the system.

    Skips already-installed items unless force=True.
    """
    from warden.installer import (
        install_apt_packages,
        install_brew_casks,
        install_brew_formulae,
        install_tools,
    )
    from warden.platform_info import detect_platform

    label = "Dry Run — " if dry_run else ""
    force_label = " (force)" if force else ""
    display.banner(f"{label}Apply Config{force_label}")
    start = time.monotonic()

    platform = detect_platform()
    display.info(f"Platform: {display.bold(platform.value)}")

    pkgs = get_packages(config)
    tools_list = get_tools(config)

    total_installed = 0
    total_skipped = 0
    all_failed: list[str] = []

    # Brew formulae
    brew = pkgs.get("brew", {})
    formulae = brew.get("formulae", [])
    if formulae:
        print()
        display.header(f"Homebrew formulae ({len(formulae)})")
        installed, skipped, failed = install_brew_formulae(
            formulae, force=force, dry_run=dry_run
        )
        total_installed += installed
        total_skipped += skipped
        all_failed.extend(f"brew:{f}" for f in failed)
        if skipped and not dry_run:
            display.skip(f"{skipped} already installed")

    # Brew casks
    casks = brew.get("casks", [])
    if casks:
        print()
        display.header(f"Homebrew casks ({len(casks)})")
        installed, skipped, failed = install_brew_casks(
            casks, force=force, dry_run=dry_run
        )
        total_installed += installed
        total_skipped += skipped
        all_failed.extend(f"cask:{f}" for f in failed)
        if skipped and not dry_run:
            display.skip(f"{skipped} already installed")

    # APT packages
    apt_pkgs = pkgs.get("apt", {}).get("packages", [])
    if apt_pkgs:
        print()
        display.header(f"APT packages ({len(apt_pkgs)})")
        installed, skipped, failed = install_apt_packages(
            apt_pkgs, force=force, dry_run=dry_run
        )
        total_installed += installed
        total_skipped += skipped
        all_failed.extend(f"apt:{f}" for f in failed)
        if skipped and not dry_run:
            display.skip(f"{skipped} already installed")

    # Developer tools
    if tools_list:
        print()
        display.header(f"Developer tools ({len(tools_list)})")
        installed, skipped, failed = install_tools(
            tools_list, platform, force=force, dry_run=dry_run
        )
        total_installed += installed
        total_skipped += skipped
        all_failed.extend(f"tool:{f}" for f in failed)
        if skipped and not dry_run:
            display.skip(f"{skipped} already installed")

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


def cmd_update(*, branch: str | None = None, dry_run: bool = False) -> None:
    """Self-update warden by pulling latest from git and reinstalling."""
    display.banner("Update Warden")
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
    result = subprocess.run(
        ["make", "install"],
        capture_output=True,
        text=True,
        cwd=repo_root,
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
