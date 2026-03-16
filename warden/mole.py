"""Mole integration — system cleanup and optimization powered by tw93/mole.

Mole is macOS-only. All commands exit with an error on non-macOS platforms.
"""

import platform as _platform
import shutil
import subprocess
import sys

from warden import display


def is_macos() -> bool:
    """Check if the current platform is macOS."""
    return _platform.system().lower() == "darwin"


def _require_macos() -> None:
    """Exit with error if not running on macOS."""
    if not is_macos():
        display.error("Mole is only available on macOS")
        sys.exit(1)


def _ensure_mole() -> str:
    """Return path to `mo` binary, installing via brew if missing.

    Exits with error on non-macOS, if installation fails, or if brew is
    unavailable.
    """
    _require_macos()
    path = shutil.which("mo")
    if path:
        return path

    display.info("Mole (mo) not found — installing via Homebrew...")

    if not shutil.which("brew"):
        display.error(
            "Homebrew is required to auto-install Mole. "
            "Install brew first or install Mole manually: "
            "https://github.com/tw93/mole"
        )
        sys.exit(1)

    result = subprocess.run(
        ["brew", "install", "mole"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        display.error(f"Failed to install Mole: {result.stderr.strip()}")
        sys.exit(1)

    display.success("Mole installed via Homebrew")

    path = shutil.which("mo")
    if not path:
        display.error("Mole installed but `mo` not found on PATH")
        sys.exit(1)

    return path


def cmd_mole_clean(*, dry_run: bool = False) -> None:
    """Run Mole deep system cleanup."""
    mo = _ensure_mole()
    cmd = [mo, "clean"]
    if dry_run:
        cmd.append("--dry-run")
    sys.exit(subprocess.call(cmd))


def cmd_mole_optimize(*, dry_run: bool = False) -> None:
    """Run Mole system optimization."""
    mo = _ensure_mole()
    cmd = [mo, "optimize"]
    if dry_run:
        cmd.append("--dry-run")
    sys.exit(subprocess.call(cmd))


def cmd_mole_analyze(path: str | None = None) -> None:
    """Run Mole disk space analyzer."""
    mo = _ensure_mole()
    cmd = [mo, "analyze"]
    if path:
        cmd.append(path)
    sys.exit(subprocess.call(cmd))


def cmd_mole_status(*, json_output: bool = False) -> None:
    """Run Mole system status dashboard."""
    mo = _ensure_mole()
    cmd = [mo, "status"]
    if json_output:
        cmd.append("--json")
    sys.exit(subprocess.call(cmd))
