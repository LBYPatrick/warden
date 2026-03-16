"""Package and tool installation for Warden.

Installs brew formulae/casks, apt packages, and developer tools.
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
    scan_apt_packages,
    scan_brew_casks,
    scan_brew_formulae,
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


def install_brew_formulae(
    wanted: list[str],
    *,
    force: bool = False,
    dry_run: bool = False,
    use_cn: bool = False,
) -> tuple[int, int, list[str]]:
    """Install Homebrew formulae. Returns (installed, skipped, failed)."""
    if not wanted:
        return 0, 0, []

    if not shutil.which("brew"):
        display.warn("Homebrew not found, skipping formulae")
        return 0, len(wanted), []

    installed_set = set(scan_brew_formulae()) if not force else set()
    to_install = [p for p in wanted if p not in installed_set]
    skipped = len(wanted) - len(to_install)

    if not to_install:
        return 0, skipped, []

    if dry_run:
        for p in to_install:
            display.info(f"Would install formula: {p}")
        return 0, skipped, []

    brew_env = HOMEBREW_CN_ENV if use_cn else None

    installed = 0
    failed: list[str] = []
    for pkg in to_install:
        with display.spinner(f"brew install {pkg}") as sp:
            ok, output = _run(["brew", "install", pkg], timeout=600, extra_env=brew_env)
            if ok:
                sp.ok(f"Installed {pkg}")
                installed += 1
            else:
                last_line = output.splitlines()[-1] if output else "unknown error"
                sp.fail(f"{pkg}: {last_line}")
                failed.append(pkg)

    return installed, skipped, failed


def install_brew_casks(
    wanted: list[str],
    *,
    force: bool = False,
    dry_run: bool = False,
    use_cn: bool = False,
) -> tuple[int, int, list[str]]:
    """Install Homebrew casks. Returns (installed, skipped, failed)."""
    if not wanted:
        return 0, 0, []

    if not shutil.which("brew"):
        display.warn("Homebrew not found, skipping casks")
        return 0, len(wanted), []

    installed_set = set(scan_brew_casks()) if not force else set()
    to_install = [p for p in wanted if p not in installed_set]
    skipped = len(wanted) - len(to_install)

    if not to_install:
        return 0, skipped, []

    if dry_run:
        for p in to_install:
            display.info(f"Would install cask: {p}")
        return 0, skipped, []

    brew_env = HOMEBREW_CN_ENV if use_cn else None

    installed = 0
    failed: list[str] = []
    for pkg in to_install:
        with display.spinner(f"brew install --cask {pkg}") as sp:
            ok, output = _run(
                ["brew", "install", "--cask", pkg], timeout=600, extra_env=brew_env
            )
            if ok:
                sp.ok(f"Installed {pkg}")
                installed += 1
            else:
                last_line = output.splitlines()[-1] if output else "unknown error"
                sp.fail(f"{pkg}: {last_line}")
                failed.append(pkg)

    return installed, skipped, failed


def install_apt_packages(
    wanted: list[str], *, force: bool = False, dry_run: bool = False
) -> tuple[int, int, list[str]]:
    """Install apt packages. Returns (installed, skipped, failed)."""
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

    if dry_run:
        for p in to_install:
            display.info(f"Would install apt package: {p}")
        return 0, skipped, []

    # Update index
    display.info("Updating apt package index...")
    _run(["sudo", "apt-get", "update", "-qq"], timeout=120)

    # Try bulk install first
    ok, output = _run(["sudo", "apt-get", "install", "-y", *to_install], timeout=600)
    if ok:
        return len(to_install), skipped, []

    # Fall back to individual installs
    installed = 0
    failed: list[str] = []
    for pkg in to_install:
        with display.spinner(f"apt-get install {pkg}") as sp:
            ok, output = _run(["sudo", "apt-get", "install", "-y", pkg], timeout=300)
            if ok:
                sp.ok(f"Installed {pkg}")
                installed += 1
            else:
                last_line = output.splitlines()[-1] if output else "unknown error"
                sp.fail(f"{pkg}: {last_line}")
                failed.append(pkg)

    return installed, skipped, failed


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

    # Filter to tools available on this platform
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
            # Apply CN URL rewrites if needed
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
