"""System package and tool scanning for Warden.

Scans installed Homebrew formulae/casks, apt packages, and developer tools.
All operations are synchronous (subprocess.run).
"""

import shutil
import subprocess
from pathlib import Path
from typing import Any

from warden import display
from warden.platform_info import Platform


def _run(cmd: list[str], *, timeout: int = 30) -> tuple[bool, str]:
    """Run a command and return (success, stdout)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode == 0, result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False, ""


# ---------------------------------------------------------------------------
# Homebrew
# ---------------------------------------------------------------------------


def scan_brew_formulae() -> list[str]:
    """List installed Homebrew formulae."""
    ok, output = _run(["brew", "list", "--formula", "-1"])
    if not ok:
        return []
    return sorted(line.strip() for line in output.splitlines() if line.strip())


def scan_brew_casks() -> list[str]:
    """List installed Homebrew casks."""
    ok, output = _run(["brew", "list", "--cask", "-1"])
    if not ok:
        return []
    return sorted(line.strip() for line in output.splitlines() if line.strip())


# ---------------------------------------------------------------------------
# APT
# ---------------------------------------------------------------------------


def scan_apt_packages() -> list[str]:
    """List installed apt packages (manually installed only)."""
    ok, output = _run(["dpkg", "--get-selections"], timeout=60)
    if not ok:
        return []
    packages = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "install":
            name = parts[0].split(":")[0]
            packages.append(name)
    return sorted(packages)


# ---------------------------------------------------------------------------
# Developer tools detection
# ---------------------------------------------------------------------------


def _is_brew_managed(binary: str) -> bool:
    """Check if a binary was installed via Homebrew."""
    path = shutil.which(binary)
    if not path:
        return False
    resolved = str(Path(path).resolve())
    return "/Cellar/" in resolved or "/Caskroom/" in resolved


def _has_binary(name: str, *, skip_brew: bool = True) -> bool:
    """Check if a binary exists, optionally excluding brew-managed ones."""
    if not shutil.which(name):
        return False
    if skip_brew and _is_brew_managed(name):
        return False
    return True


def _xcode_cli_installed() -> bool:
    """Check if Xcode Command Line Tools are installed."""
    try:
        result = subprocess.run(["xcode-select", "-p"], capture_output=True, timeout=5)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# Tool slug -> (display_name, detect_fn, platforms)
_TOOL_DEFS: list[tuple[str, str, callable, list[str]]] = [
    ("xcode", "Xcode CLI Tools", _xcode_cli_installed, ["macos"]),
    ("rustup", "Rust (rustup)", lambda: _has_binary("rustup"), ["macos", "linux"]),
    ("conda", "Miniforge (conda)", lambda: _has_binary("conda"), ["macos", "linux"]),
    ("node", "Node.js (fnm)", lambda: _has_binary("node"), ["macos", "linux"]),
    ("pnpm", "pnpm", lambda: _has_binary("pnpm"), ["macos", "linux"]),
    (
        "flutter",
        "Flutter SDK",
        lambda: _has_binary("flutter"),
        ["macos", "linux"],
    ),
    (
        "gcloud",
        "Google Cloud SDK",
        lambda: _has_binary("gcloud"),
        ["macos", "linux"],
    ),
    ("aws", "AWS CLI", lambda: _has_binary("aws"), ["macos", "linux"]),
    (
        "wrangler",
        "Cloudflare Wrangler",
        lambda: _has_binary("wrangler", skip_brew=False),
        ["macos", "linux"],
    ),
    (
        "android-tools",
        "Android Platform Tools",
        lambda: _has_binary("adb"),
        ["macos", "linux"],
    ),
]


def scan_tools(platform: Platform) -> list[str]:
    """Detect installed developer tools. Returns list of tool slugs."""
    found: list[str] = []
    for slug, _name, detect, platforms in _TOOL_DEFS:
        if platform.value not in platforms:
            continue
        if detect():
            found.append(slug)
    return sorted(found)


def list_tools(platform: Platform) -> list[tuple[str, str, bool]]:
    """Return (slug, display_name, installed) for all tools on this platform."""
    result: list[tuple[str, str, bool]] = []
    for slug, name, detect, platforms in _TOOL_DEFS:
        if platform.value not in platforms:
            continue
        result.append((slug, name, detect()))
    return result


# ---------------------------------------------------------------------------
# Full system scan
# ---------------------------------------------------------------------------


def scan_system(platform: Platform) -> dict[str, Any]:
    """Scan the system for packages and tools. Returns packages/tools dicts."""
    packages: dict[str, Any] = {}

    # Homebrew
    if shutil.which("brew"):
        display.info("Scanning Homebrew packages...")
        formulae = scan_brew_formulae()
        casks = scan_brew_casks()
        brew: dict[str, list[str]] = {}
        if formulae:
            brew["formulae"] = formulae
        if casks:
            brew["casks"] = casks
        if brew:
            packages["brew"] = brew
        display.success(f"Found {len(formulae)} formulae, {len(casks)} casks")

    # APT
    if shutil.which("apt"):
        display.info("Scanning apt packages...")
        apt_pkgs = scan_apt_packages()
        if apt_pkgs:
            packages["apt"] = {"packages": apt_pkgs}
        display.success(f"Found {len(apt_pkgs)} apt packages")

    # Developer tools
    display.info("Scanning developer tools...")
    tools = scan_tools(platform)
    if tools:
        tool_names = []
        for slug in tools:
            for s, name, _, _ in _TOOL_DEFS:
                if s == slug:
                    tool_names.append(name)
                    break
        display.success(f"Found {len(tools)} tools: {', '.join(tool_names)}")
    else:
        display.success("No developer tools detected")

    return {"packages": packages, "tools": tools}
