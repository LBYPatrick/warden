"""Package and tool installation for Warden.

Installs packages across multiple package managers and developer tools.
Skips already-installed items unless force=True.
Supports China mirrors via use_cn flag.
"""

import os
import shutil
import subprocess

from warden import display
from warden.cn import CN_ENV, HOMEBREW_CN_ENV, apply_cn_rewrites
from warden.platform_info import Platform
from warden.scanner import (
    _TOOL_DEFS,
    scan_apk_packages,
    scan_apt_packages,
    scan_brew_casks,
    scan_brew_formulae,
    scan_cargo_packages,
    scan_dnf_packages,
    scan_flatpak_packages,
    scan_mas_apps,
    scan_npm_global_packages,
    scan_pacman_packages,
    scan_pipx_packages,
    scan_pnpm_global_packages,
    scan_snap_packages,
    scan_tools,
)


def _run(
    cmd: list[str],
    *,
    timeout: int = 300,
    extra_env: dict[str, str] | None = None,
) -> tuple[bool, str]:
    """Run a command and return (success, combined output)."""
    env = None
    if extra_env:
        env = {**os.environ, **extra_env}
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        output = (result.stdout + "\n" + result.stderr).strip()
        return result.returncode == 0, output
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return False, str(e)


def _run_shell(
    cmd: str,
    *,
    timeout: int = 300,
    extra_env: dict[str, str] | None = None,
) -> tuple[bool, str]:
    """Run a shell command and return (success, combined output)."""
    env = None
    if extra_env:
        env = {**os.environ, **extra_env}
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        output = (result.stdout + "\n" + result.stderr).strip()
        return result.returncode == 0, output
    except subprocess.TimeoutExpired as e:
        return False, str(e)


# ---------------------------------------------------------------------------
# Generic installer: one-at-a-time with spinner
# ---------------------------------------------------------------------------


def _install_packages_generic(
    wanted: list[str],
    *,
    label: str,
    binary: str,
    scan_fn: callable,
    install_cmd: list[str],
    force: bool = False,
    dry_run: bool = False,
    extra_env: dict[str, str] | None = None,
    timeout: int = 600,
) -> tuple[int, int, list[str]]:
    """Generic package installer. Returns (installed, skipped, failed).

    install_cmd should be a list where the package name is appended,
    e.g. ["brew", "install"] -> ["brew", "install", "pkg"].
    """
    if not wanted:
        return 0, 0, []

    if not shutil.which(binary):
        display.warn(f"{label}: {binary} not found, skipping")
        return 0, len(wanted), []

    installed_set = set(scan_fn()) if not force else set()
    to_install = [p for p in wanted if p not in installed_set]
    skipped = len(wanted) - len(to_install)

    if not to_install:
        return 0, skipped, []

    if dry_run:
        for p in to_install:
            display.info(f"Would install {label}: {p}")
        return 0, skipped, []

    installed = 0
    failed: list[str] = []
    for pkg in to_install:
        cmd_display = " ".join(install_cmd) + f" {pkg}"
        with display.spinner(cmd_display) as sp:
            ok, output = _run([*install_cmd, pkg], timeout=timeout, extra_env=extra_env)
            if ok:
                sp.ok(f"Installed {pkg}")
                installed += 1
            else:
                last_line = output.splitlines()[-1] if output else "unknown error"
                sp.fail(f"{pkg}: {last_line}")
                failed.append(pkg)

    return installed, skipped, failed


# ---------------------------------------------------------------------------
# Homebrew
# ---------------------------------------------------------------------------


def _run_live(
    cmd: list[str],
    *,
    timeout: int = 1200,
    extra_env: dict[str, str] | None = None,
) -> bool:
    """Run a command with stdout/stderr streamed to the terminal. Returns success."""
    env = None
    if extra_env:
        env = {**os.environ, **extra_env}
    try:
        result = subprocess.run(cmd, timeout=timeout, env=env)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _install_brew_bulk(
    wanted: list[str],
    *,
    label: str,
    scan_fn: callable,
    install_cmd: list[str],
    force: bool = False,
    dry_run: bool = False,
    extra_env: dict[str, str] | None = None,
) -> tuple[int, int, list[str]]:
    """Install Homebrew packages in bulk with live output.

    Sends all packages to brew in a single command for speed, streaming
    output to the terminal.  If that fails (e.g. one bad formula), retries
    each package individually.
    """
    if not wanted:
        return 0, 0, []

    if not shutil.which("brew"):
        display.warn(f"{label}: brew not found, skipping")
        return 0, len(wanted), []

    installed_set = set(scan_fn()) if not force else set()
    to_install = [p for p in wanted if p not in installed_set]
    skipped = len(wanted) - len(to_install)

    if not to_install:
        return 0, skipped, []

    if dry_run:
        for p in to_install:
            display.info(f"Would install {label}: {p}")
        return 0, skipped, []

    # Bulk install with live output
    display.info(f"Installing {len(to_install)} {label}(s)...")
    print()
    ok = _run_live([*install_cmd, *to_install], timeout=1200, extra_env=extra_env)
    print()
    if ok:
        display.success(f"Installed {len(to_install)} {label}(s)")
        return len(to_install), skipped, []

    display.warn("Bulk install failed, retrying individually...")

    # Fallback: one at a time with live output
    installed = 0
    failed: list[str] = []
    for pkg in to_install:
        display.info(f"Installing {pkg}...")
        ok = _run_live([*install_cmd, pkg], timeout=600, extra_env=extra_env)
        if ok:
            display.success(f"Installed {pkg}")
            installed += 1
        else:
            display.error(f"Failed to install {pkg}")
            failed.append(pkg)

    return installed, skipped, failed


def install_brew_formulae(
    wanted: list[str],
    *,
    force: bool = False,
    dry_run: bool = False,
    use_cn: bool = False,
) -> tuple[int, int, list[str]]:
    """Install Homebrew formulae in bulk."""
    return _install_brew_bulk(
        wanted,
        label="brew formula",
        scan_fn=scan_brew_formulae,
        install_cmd=["brew", "install"],
        force=force,
        dry_run=dry_run,
        extra_env=HOMEBREW_CN_ENV if use_cn else None,
    )


def install_brew_casks(
    wanted: list[str],
    *,
    force: bool = False,
    dry_run: bool = False,
    use_cn: bool = False,
) -> tuple[int, int, list[str]]:
    """Install Homebrew casks in bulk."""
    return _install_brew_bulk(
        wanted,
        label="brew cask",
        scan_fn=scan_brew_casks,
        install_cmd=["brew", "install", "--cask"],
        force=force,
        dry_run=dry_run,
        extra_env=HOMEBREW_CN_ENV if use_cn else None,
    )


# ---------------------------------------------------------------------------
# Mac App Store
# ---------------------------------------------------------------------------


def install_mas_apps(
    wanted: list[str],
    *,
    force: bool = False,
    dry_run: bool = False,
) -> tuple[int, int, list[str]]:
    """Install Mac App Store apps. Items are 'id:name' strings."""
    if not wanted:
        return 0, 0, []

    if not shutil.which("mas"):
        display.warn("mas not found, skipping Mac App Store apps")
        return 0, len(wanted), []

    # Build set of installed IDs
    installed_ids = set()
    if not force:
        for entry in scan_mas_apps():
            app_id = entry.split(":")[0]
            installed_ids.add(app_id)

    to_install = [a for a in wanted if a.split(":")[0] not in installed_ids]
    skipped = len(wanted) - len(to_install)

    if not to_install:
        return 0, skipped, []

    if dry_run:
        for app in to_install:
            display.info(f"Would install mas app: {app}")
        return 0, skipped, []

    installed = 0
    failed: list[str] = []
    for app in to_install:
        app_id = app.split(":")[0]
        name = app.split(":", 1)[1] if ":" in app else app_id
        with display.spinner(f"mas install {name}") as sp:
            ok, output = _run(["mas", "install", app_id], timeout=600)
            if ok:
                sp.ok(f"Installed {name}")
                installed += 1
            else:
                last_line = output.splitlines()[-1] if output else "unknown error"
                sp.fail(f"{name}: {last_line}")
                failed.append(app)

    return installed, skipped, failed


# ---------------------------------------------------------------------------
# APT (with bulk fallback)
# ---------------------------------------------------------------------------


def _apt_available_packages() -> set[str]:
    """Get the set of all package names available in apt cache."""
    ok, output = _run(["apt-cache", "pkgnames"], timeout=60)
    if not ok:
        return set()
    return set(line.strip() for line in output.splitlines() if line.strip())


def install_apt_packages(
    wanted: list[str], *, force: bool = False, dry_run: bool = False
) -> tuple[int, int, list[str]]:
    """Install apt packages with bulk-then-individual fallback.

    Filters packages through apt-cache to skip unavailable ones, then
    installs all available packages in a single apt-get call.
    """
    if not wanted:
        return 0, 0, []

    if not shutil.which("apt-get"):
        display.warn("apt-get not found, skipping apt packages")
        return 0, len(wanted), []

    installed_set = set(scan_apt_packages()) if not force else set()
    to_install = [p for p in wanted if p not in installed_set]
    skipped = len(wanted) - len(to_install)

    if not to_install:
        return 0, skipped, []

    display.info("Updating apt package index...")
    _run(["sudo", "apt-get", "update", "-qq"], timeout=120)

    # Filter to only packages that exist in apt cache
    available = _apt_available_packages()
    if available:
        installable = [p for p in to_install if p in available]
        unavailable = [p for p in to_install if p not in available]
        if unavailable:
            display.warn(
                f"Skipping {len(unavailable)} unavailable apt packages: "
                + ", ".join(unavailable[:10])
                + ("..." if len(unavailable) > 10 else "")
            )
    else:
        # apt-cache failed — try installing everything and let apt sort it out
        installable = to_install
        unavailable = []

    if not installable:
        return 0, skipped, []

    if dry_run:
        for p in installable:
            display.info(f"Would install apt package: {p}")
        return 0, skipped, []

    # Bulk install all at once
    ok, output = _run(["sudo", "apt-get", "install", "-y", *installable], timeout=600)
    if ok:
        return len(installable), skipped, unavailable

    # Fall back to individual installs
    inst, _, failed = _install_packages_generic(
        installable,
        label="apt",
        binary="apt-get",
        scan_fn=lambda: [],  # Already filtered
        install_cmd=["sudo", "apt-get", "install", "-y"],
        force=True,
    )
    return inst, skipped, failed + unavailable


# ---------------------------------------------------------------------------
# DNF
# ---------------------------------------------------------------------------


def install_dnf_packages(
    wanted: list[str], *, force: bool = False, dry_run: bool = False
) -> tuple[int, int, list[str]]:
    """Install dnf packages."""
    return _install_packages_generic(
        wanted,
        label="dnf",
        binary="dnf",
        scan_fn=scan_dnf_packages,
        install_cmd=["sudo", "dnf", "install", "-y"],
        force=force,
        dry_run=dry_run,
    )


# ---------------------------------------------------------------------------
# Pacman
# ---------------------------------------------------------------------------


def install_pacman_packages(
    wanted: list[str], *, force: bool = False, dry_run: bool = False
) -> tuple[int, int, list[str]]:
    """Install pacman packages."""
    return _install_packages_generic(
        wanted,
        label="pacman",
        binary="pacman",
        scan_fn=scan_pacman_packages,
        install_cmd=["sudo", "pacman", "-S", "--noconfirm"],
        force=force,
        dry_run=dry_run,
    )


# ---------------------------------------------------------------------------
# APK
# ---------------------------------------------------------------------------


def install_apk_packages(
    wanted: list[str], *, force: bool = False, dry_run: bool = False
) -> tuple[int, int, list[str]]:
    """Install apk packages."""
    return _install_packages_generic(
        wanted,
        label="apk",
        binary="apk",
        scan_fn=scan_apk_packages,
        install_cmd=["sudo", "apk", "add"],
        force=force,
        dry_run=dry_run,
    )


# ---------------------------------------------------------------------------
# Snap
# ---------------------------------------------------------------------------


def install_snap_packages(
    wanted: list[str], *, force: bool = False, dry_run: bool = False
) -> tuple[int, int, list[str]]:
    """Install snap packages."""
    return _install_packages_generic(
        wanted,
        label="snap",
        binary="snap",
        scan_fn=scan_snap_packages,
        install_cmd=["sudo", "snap", "install"],
        force=force,
        dry_run=dry_run,
    )


# ---------------------------------------------------------------------------
# Flatpak
# ---------------------------------------------------------------------------


def install_flatpak_packages(
    wanted: list[str], *, force: bool = False, dry_run: bool = False
) -> tuple[int, int, list[str]]:
    """Install flatpak applications."""
    return _install_packages_generic(
        wanted,
        label="flatpak",
        binary="flatpak",
        scan_fn=scan_flatpak_packages,
        install_cmd=["flatpak", "install", "-y"],
        force=force,
        dry_run=dry_run,
    )


# ---------------------------------------------------------------------------
# Cargo
# ---------------------------------------------------------------------------


def install_cargo_packages(
    wanted: list[str], *, force: bool = False, dry_run: bool = False
) -> tuple[int, int, list[str]]:
    """Install cargo packages."""
    return _install_packages_generic(
        wanted,
        label="cargo",
        binary="cargo",
        scan_fn=scan_cargo_packages,
        install_cmd=["cargo", "install"],
        force=force,
        dry_run=dry_run,
    )


# ---------------------------------------------------------------------------
# npm (global)
# ---------------------------------------------------------------------------


def install_npm_global_packages(
    wanted: list[str], *, force: bool = False, dry_run: bool = False
) -> tuple[int, int, list[str]]:
    """Install npm global packages."""
    return _install_packages_generic(
        wanted,
        label="npm global",
        binary="npm",
        scan_fn=scan_npm_global_packages,
        install_cmd=["npm", "install", "-g"],
        force=force,
        dry_run=dry_run,
    )


# ---------------------------------------------------------------------------
# pnpm (global)
# ---------------------------------------------------------------------------


def install_pnpm_global_packages(
    wanted: list[str],
    *,
    force: bool = False,
    dry_run: bool = False,
    use_cn: bool = False,
) -> tuple[int, int, list[str]]:
    """Install pnpm global packages."""
    extra_env = (
        {"NPM_CONFIG_REGISTRY": "https://registry.npmmirror.com"} if use_cn else None
    )
    return _install_packages_generic(
        wanted,
        label="pnpm global",
        binary="pnpm",
        scan_fn=scan_pnpm_global_packages,
        install_cmd=["pnpm", "add", "-g"],
        force=force,
        dry_run=dry_run,
        extra_env=extra_env,
    )


# ---------------------------------------------------------------------------
# pipx
# ---------------------------------------------------------------------------


def install_pipx_packages(
    wanted: list[str], *, force: bool = False, dry_run: bool = False
) -> tuple[int, int, list[str]]:
    """Install pipx packages."""
    return _install_packages_generic(
        wanted,
        label="pipx",
        binary="pipx",
        scan_fn=scan_pipx_packages,
        install_cmd=["pipx", "install"],
        force=force,
        dry_run=dry_run,
    )


# ---------------------------------------------------------------------------
# Developer tools
# ---------------------------------------------------------------------------

# Tool slug -> install script lines
_TOOL_INSTALL_SCRIPTS: dict[str, list[str]] = {
    "xcode": [
        "xcode-select -p &>/dev/null && exit 0",
        "xcode-select --install",
        "echo 'Waiting for Xcode CLI tools installation...'",
        "until xcode-select -p &>/dev/null; do sleep 5; done",
    ],
    "rustup": [
        "command -v rustup &>/dev/null && exit 0",
        'curl --proto "=https" --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y',
    ],
    "conda": [
        "command -v conda &>/dev/null && exit 0",
        'curl -fsSL -o /tmp/miniforge.sh "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"',
        "bash /tmp/miniforge.sh -b",
        "rm -f /tmp/miniforge.sh",
    ],
    "node": [
        "command -v node &>/dev/null && exit 0",
        "curl -fsSL https://fnm.vercel.app/install | bash -s -- --skip-shell",
        'export PATH="$HOME/.local/share/fnm:$PATH"',
        'eval "$(fnm env)"',
        "fnm install --lts",
    ],
    "pnpm": [
        "command -v pnpm &>/dev/null && exit 0",
        "curl -fsSL https://get.pnpm.io/install.sh | sh -",
    ],
    "flutter": [
        "command -v flutter &>/dev/null && exit 0",
        'git clone https://github.com/flutter/flutter.git -b stable "$HOME/.flutter"',
        'echo "Add $HOME/.flutter/bin to your PATH"',
    ],
    "gcloud": [
        "command -v gcloud &>/dev/null && exit 0",
        "curl -fsSL https://sdk.cloud.google.com | bash -s -- --disable-prompts",
    ],
    "aws": [
        "command -v aws &>/dev/null && exit 0",
        'if [ "$(uname)" = "Darwin" ]; then '
        'curl -fsSL "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o /tmp/AWSCLIV2.pkg && '
        "sudo installer -pkg /tmp/AWSCLIV2.pkg -target / && "
        "rm -f /tmp/AWSCLIV2.pkg; "
        "else "
        'curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-$(uname -m).zip" -o /tmp/awscliv2.zip && '
        "unzip -oq /tmp/awscliv2.zip -d /tmp && "
        "sudo /tmp/aws/install && "
        "rm -rf /tmp/aws /tmp/awscliv2.zip; "
        "fi",
    ],
    "wrangler": [
        "command -v wrangler &>/dev/null && exit 0",
        "npm install -g wrangler",
    ],
    "android-tools": [
        "command -v adb &>/dev/null && exit 0",
        'if [ "$(uname)" = "Darwin" ]; then '
        "brew install android-platform-tools; "
        "else "
        'curl -fsSL "https://dl.google.com/android/repository/platform-tools-latest-linux.zip" -o /tmp/platform-tools.zip && '
        "sudo unzip -oq /tmp/platform-tools.zip -d /opt && "
        "sudo ln -sf /opt/platform-tools/adb /usr/local/bin/adb && "
        "sudo ln -sf /opt/platform-tools/fastboot /usr/local/bin/fastboot && "
        "rm -f /tmp/platform-tools.zip; "
        "fi",
    ],
}


def install_tools(
    wanted: list[str],
    platform: Platform,
    *,
    force: bool = False,
    dry_run: bool = False,
    use_cn: bool = False,
) -> tuple[int, int, list[str]]:
    """Install developer tools. Returns (installed, skipped, failed)."""
    if not wanted:
        return 0, 0, []

    already_installed = set(scan_tools(platform)) if not force else set()

    platform_tools = set()
    for slug, _name, _detect, platforms in _TOOL_DEFS:
        if platform.value in platforms:
            platform_tools.add(slug)

    to_install = [
        t for t in wanted if t in platform_tools and t not in already_installed
    ]
    skipped = len(wanted) - len(to_install)

    if not to_install:
        return 0, skipped, []

    if dry_run:
        for slug in to_install:
            name = _tool_display_name(slug)
            display.info(f"Would install tool: {name}")
        return 0, skipped, []

    cn_env = CN_ENV if use_cn else {}

    installed = 0
    failed: list[str] = []
    for slug in to_install:
        name = _tool_display_name(slug)
        script_lines = _TOOL_INSTALL_SCRIPTS.get(slug)
        if not script_lines:
            display.warn(f"No install script for {name}")
            failed.append(slug)
            continue

        with display.spinner(f"Installing {name}") as sp:
            if use_cn:
                script = "\n".join(apply_cn_rewrites(line) for line in script_lines)
            else:
                script = "\n".join(script_lines)
            ok, output = _run_shell(script, timeout=600, extra_env=cn_env or None)
            if ok:
                sp.ok(f"Installed {name}")
                installed += 1
            else:
                last_line = output.splitlines()[-1] if output else "unknown error"
                sp.fail(f"{name}: {last_line}")
                failed.append(slug)

    return installed, skipped, failed


def _tool_display_name(slug: str) -> str:
    """Get display name for a tool slug."""
    for s, name, _, _ in _TOOL_DEFS:
        if s == slug:
            return name
    return slug
