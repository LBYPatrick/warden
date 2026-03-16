"""System package and tool scanning for Warden.

Scans installed packages across multiple package managers and developer tools.
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


def _lines(output: str) -> list[str]:
    """Split output into sorted, non-empty, stripped lines."""
    return sorted(line.strip() for line in output.splitlines() if line.strip())


# ---------------------------------------------------------------------------
# Homebrew (macOS, Linux via Linuxbrew)
# ---------------------------------------------------------------------------


def scan_brew_formulae() -> list[str]:
    """List installed Homebrew formulae."""
    ok, output = _run(["brew", "list", "--formula", "-1"])
    return _lines(output) if ok else []


def scan_brew_casks() -> list[str]:
    """List installed Homebrew casks."""
    ok, output = _run(["brew", "list", "--cask", "-1"])
    return _lines(output) if ok else []


# ---------------------------------------------------------------------------
# Mac App Store (macOS only, requires `mas` CLI)
# ---------------------------------------------------------------------------


def scan_mas_apps() -> list[str]:
    """List installed Mac App Store apps as 'id:name' strings."""
    ok, output = _run(["mas", "list"], timeout=15)
    if not ok:
        return []
    apps = []
    for line in output.splitlines():
        # Format: "123456789 App Name (version)"
        parts = line.strip().split(None, 1)
        if len(parts) >= 2:
            app_id = parts[0]
            # Strip trailing version in parens
            name = parts[1].rsplit("(", 1)[0].strip()
            apps.append(f"{app_id}:{name}")
    return sorted(apps)


# ---------------------------------------------------------------------------
# APT (Debian/Ubuntu)
# ---------------------------------------------------------------------------


def scan_apt_packages() -> list[str]:
    """List installed apt packages."""
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
# DNF (Fedora/RHEL/CentOS)
# ---------------------------------------------------------------------------


def scan_dnf_packages() -> list[str]:
    """List user-installed dnf packages."""
    ok, output = _run(
        ["dnf", "repoquery", "--userinstalled", "--qf", "%{name}"], timeout=60
    )
    if not ok:
        return []
    return _lines(output)


# ---------------------------------------------------------------------------
# Pacman (Arch Linux)
# ---------------------------------------------------------------------------


def scan_pacman_packages() -> list[str]:
    """List explicitly installed pacman packages."""
    ok, output = _run(["pacman", "-Qqe"], timeout=30)
    if not ok:
        return []
    return _lines(output)


# ---------------------------------------------------------------------------
# APK (Alpine Linux)
# ---------------------------------------------------------------------------


def scan_apk_packages() -> list[str]:
    """List installed apk packages."""
    ok, output = _run(["apk", "list", "--installed"], timeout=30)
    if not ok:
        return []
    # Format: "pkg-name-1.2.3-r0 x86_64 {origin} (license)"
    packages = []
    for line in output.splitlines():
        name = line.split()[0] if line.strip() else ""
        if name:
            # Strip version: everything after the last hyphen before a digit
            # e.g. "curl-8.5.0-r0" -> "curl"
            parts = name.split("-")
            pkg_parts = []
            for p in parts:
                if p and p[0].isdigit():
                    break
                pkg_parts.append(p)
            if pkg_parts:
                packages.append("-".join(pkg_parts))
    return sorted(set(packages))


# ---------------------------------------------------------------------------
# Snap (Ubuntu/etc.)
# ---------------------------------------------------------------------------


def scan_snap_packages() -> list[str]:
    """List installed snap packages."""
    ok, output = _run(["snap", "list"], timeout=15)
    if not ok:
        return []
    # First line is header: "Name  Version  Rev  ..."
    lines = output.splitlines()[1:]
    packages = []
    for line in lines:
        name = line.split()[0] if line.strip() else ""
        if name and name != "core" and not name.startswith("core"):
            packages.append(name)
    return sorted(packages)


# ---------------------------------------------------------------------------
# Flatpak
# ---------------------------------------------------------------------------


def scan_flatpak_packages() -> list[str]:
    """List installed flatpak application IDs."""
    ok, output = _run(["flatpak", "list", "--app", "--columns=application"], timeout=15)
    if not ok:
        return []
    return _lines(output)


# ---------------------------------------------------------------------------
# Cargo (Rust)
# ---------------------------------------------------------------------------


def scan_cargo_packages() -> list[str]:
    """List cargo-installed binaries."""
    ok, output = _run(["cargo", "install", "--list"], timeout=15)
    if not ok:
        return []
    # Lines without leading whitespace are package names: "ripgrep v14.1.0:"
    packages = []
    for line in output.splitlines():
        if line and not line[0].isspace():
            name = line.split()[0].rstrip(":")
            if name:
                packages.append(name)
    return sorted(packages)


# ---------------------------------------------------------------------------
# npm (global packages)
# ---------------------------------------------------------------------------


def scan_npm_global_packages() -> list[str]:
    """List globally installed npm packages."""
    ok, output = _run(["npm", "list", "-g", "--depth=0", "--json"], timeout=15)
    if not ok:
        return []
    import json

    try:
        data = json.loads(output)
        deps = data.get("dependencies", {})
        # Exclude npm itself
        return sorted(k for k in deps if k != "npm")
    except (json.JSONDecodeError, AttributeError):
        return []


# ---------------------------------------------------------------------------
# pnpm (global packages)
# ---------------------------------------------------------------------------


def scan_pnpm_global_packages() -> list[str]:
    """List globally installed pnpm packages."""
    ok, output = _run(["pnpm", "list", "-g", "--depth=0", "--json"], timeout=15)
    if not ok:
        return []
    import json

    try:
        data = json.loads(output)
        # pnpm returns an array of store entries
        if isinstance(data, list) and data:
            deps = data[0].get("dependencies", {})
        elif isinstance(data, dict):
            deps = data.get("dependencies", {})
        else:
            return []
        return sorted(deps.keys())
    except (json.JSONDecodeError, AttributeError, IndexError):
        return []


# ---------------------------------------------------------------------------
# pipx (Python CLI tools)
# ---------------------------------------------------------------------------


def scan_pipx_packages() -> list[str]:
    """List pipx-installed packages."""
    ok, output = _run(["pipx", "list", "--short"], timeout=15)
    if not ok:
        return []
    # Format: "package 1.2.3"
    packages = []
    for line in output.splitlines():
        name = line.split()[0] if line.strip() else ""
        if name:
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
# Package manager registry
# ---------------------------------------------------------------------------

# (config_key, display_name, detect_binary, scan_fn, sub_key, platforms)
# sub_key is the key inside the config section (e.g. "packages", "formulae", "apps")
# For brew, we handle formulae/casks specially in scan_system.
_PKG_MANAGERS: list[tuple[str, str, str, callable, str, list[str]]] = [
    ("mas", "Mac App Store", "mas", scan_mas_apps, "apps", ["macos"]),
    ("apt", "APT", "apt", scan_apt_packages, "packages", ["linux"]),
    ("dnf", "DNF", "dnf", scan_dnf_packages, "packages", ["linux"]),
    ("pacman", "Pacman", "pacman", scan_pacman_packages, "packages", ["linux"]),
    ("apk", "APK", "apk", scan_apk_packages, "packages", ["linux"]),
    ("snap", "Snap", "snap", scan_snap_packages, "packages", ["linux"]),
    ("flatpak", "Flatpak", "flatpak", scan_flatpak_packages, "packages", ["linux"]),
    ("cargo", "Cargo", "cargo", scan_cargo_packages, "packages", ["macos", "linux"]),
    (
        "npm",
        "npm (global)",
        "npm",
        scan_npm_global_packages,
        "packages",
        ["macos", "linux"],
    ),
    (
        "pnpm",
        "pnpm (global)",
        "pnpm",
        scan_pnpm_global_packages,
        "packages",
        ["macos", "linux"],
    ),
    ("pipx", "pipx", "pipx", scan_pipx_packages, "packages", ["macos", "linux"]),
]


# ---------------------------------------------------------------------------
# Full system scan
# ---------------------------------------------------------------------------


def scan_system(platform: Platform) -> dict[str, Any]:
    """Scan the system for packages and tools. Returns packages/tools dicts."""
    packages: dict[str, Any] = {}

    # Homebrew (special: has formulae + casks)
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

    # All other package managers
    for key, name, binary, scan_fn, sub_key, platforms in _PKG_MANAGERS:
        if platform.value not in platforms:
            continue
        if not shutil.which(binary):
            continue
        display.info(f"Scanning {name} packages...")
        pkgs = scan_fn()
        if pkgs:
            packages[key] = {sub_key: pkgs}
        display.success(f"Found {len(pkgs)} {name} packages")

    # Developer tools
    display.info("Scanning developer tools...")
    tools = scan_tools(platform)
    if tools:
        tool_names = []
        for slug in tools:
            for s, tname, _, _ in _TOOL_DEFS:
                if s == slug:
                    tool_names.append(tname)
                    break
        display.success(f"Found {len(tools)} tools: {', '.join(tool_names)}")
    else:
        display.success("No developer tools detected")

    return {"packages": packages, "tools": tools}
