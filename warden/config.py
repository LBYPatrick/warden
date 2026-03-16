"""Config resolution and loading for Warden."""

import sys
from pathlib import Path
from typing import Any

import json5

DEFAULT_SEARCH_PATHS = [
    Path.home() / ".ssh" / "warden.jsonc",
    Path.home() / "warden.jsonc",
    Path.cwd() / "warden.jsonc",
]


def resolve_config_path(override: str | None = None) -> Path | None:
    """Find the first existing config file from search paths.

    Args:
        override: Explicit path from -c flag, takes absolute priority.

    Returns:
        Path to config file, or None if not found.
    """
    if override:
        p = Path(override).expanduser().resolve()
        if p.is_file():
            return p
        return None

    for path in DEFAULT_SEARCH_PATHS:
        resolved = path.expanduser().resolve()
        if resolved.is_file():
            return resolved

    return None


def load_config(override: str | None = None) -> dict[str, Any]:
    """Load and parse the warden.jsonc config file.

    Args:
        override: Explicit path from -c flag.

    Returns:
        Dict mapping target names to their config dicts.

    Exits with error if config not found or invalid.
    """
    from warden import display

    path = resolve_config_path(override)
    if path is None:
        searched = [str(p.expanduser()) for p in DEFAULT_SEARCH_PATHS]
        if override:
            searched = [override]
        display.error(
            "Config not found. Searched:\n" + "\n".join(f"    - {s}" for s in searched)
        )
        sys.exit(1)

    try:
        raw = path.read_text(encoding="utf-8")
        data = json5.loads(raw)
    except (ValueError, OSError) as e:
        display.error(f"Failed to parse {path}: {e}")
        sys.exit(1)

    if not isinstance(data, dict):
        display.error(f"Config must be a JSON object, got {type(data).__name__}")
        sys.exit(1)

    return data


def find_target(config: dict[str, Any], name: str) -> tuple[str, dict[str, Any]] | None:
    """Case-insensitive target lookup.

    Returns:
        Tuple of (canonical_name, target_config) or None.
    """
    lower = name.lower()
    for key, val in config.items():
        if key.lower() == lower:
            return key, val
    return None


def resolve_ssh_command(signing_key: str) -> str | None:
    """Derive core.sshCommand from signing_key path.

    Returns:
        The ssh command string, or None if default key (unset sshCommand).
    """
    expanded = str(Path(signing_key).expanduser())
    # Strip .pub to get private key path
    if expanded.endswith(".pub"):
        private_key = expanded[:-4]
    else:
        private_key = expanded

    default_key = str(Path.home() / ".ssh" / "id_ed25519")
    if private_key == default_key:
        return None

    return f"ssh -o IdentitiesOnly=yes -i {private_key}"


def serialize_config(data: dict[str, Any]) -> str:
    """Serialize a config dict to pretty JSON5."""
    return json5.dumps(data, indent=2, ensure_ascii=False) + "\n"
