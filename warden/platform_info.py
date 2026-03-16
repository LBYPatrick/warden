"""Platform detection for Warden."""

import platform as _platform
from enum import Enum


class Platform(Enum):
    MACOS = "macos"
    LINUX = "linux"


_ARCH_MAP = {
    "x86_64": "amd64",
    "amd64": "amd64",
    "aarch64": "arm64",
    "arm64": "arm64",
}


def detect_platform() -> Platform:
    """Detect the current operating system."""
    system = _platform.system().lower()
    if system == "darwin":
        return Platform.MACOS
    if system == "linux":
        return Platform.LINUX
    raise RuntimeError(f"Unsupported platform: {system}")


def detect_arch() -> str:
    """Detect the CPU architecture (amd64 or arm64)."""
    machine = _platform.machine().lower()
    return _ARCH_MAP.get(machine, machine)
