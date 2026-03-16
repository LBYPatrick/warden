"""Config resolution, loading, and merging for Warden."""

import sys
from pathlib import Path
from typing import Any

import json5

DEFAULT_SEARCH_PATHS = [
    Path.home() / ".warden" / "warden.jsonc",
    Path.home() / ".ssh" / "warden.jsonc",
    Path.home() / "warden.jsonc",
    Path.cwd() / "warden.jsonc",
]

# Reserved top-level keys in the new config format.
_RESERVED_KEYS = {"identities", "packages", "tools"}


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
        Dict with the full config (new or legacy format).

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


def is_new_format(config: dict[str, Any]) -> bool:
    """Check if config uses the new unified format (has 'identities' key)."""
    return "identities" in config


def get_identities(config: dict[str, Any]) -> dict[str, Any]:
    """Extract identities section from config, handling legacy format.

    Legacy format: every top-level key is an identity target.
    New format: identities live under the 'identities' key.
    """
    if is_new_format(config):
        identities = config.get("identities", {})
        return identities if isinstance(identities, dict) else {}

    # Legacy: everything at top level is an identity
    return {k: v for k, v in config.items() if isinstance(v, dict)}


def get_packages(config: dict[str, Any]) -> dict[str, Any]:
    """Extract packages section from config."""
    return config.get("packages", {})


def get_tools(config: dict[str, Any]) -> list[str]:
    """Extract tools list from config."""
    tools = config.get("tools", [])
    return tools if isinstance(tools, list) else []


def find_target(
    identities: dict[str, Any], name: str
) -> tuple[str, dict[str, Any]] | None:
    """Case-insensitive target lookup in identities dict.

    Returns:
        Tuple of (canonical_name, target_config) or None.
    """
    lower = name.lower()
    for key, val in identities.items():
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


# ---------------------------------------------------------------------------
# Config merging (for restore)
# ---------------------------------------------------------------------------


def _merge_list_union(existing: list, incoming: list) -> list:
    """Merge two lists into a sorted, deduplicated union."""
    combined = set(existing) | set(incoming)
    return sorted(combined)


def _merge_pkg_section(
    ex_section: dict[str, Any], in_section: dict[str, Any]
) -> dict[str, Any]:
    """Merge two package manager sections by union-merging all sub-lists."""
    if not ex_section and not in_section:
        return {}
    all_keys = set(ex_section) | set(in_section)
    merged: dict[str, Any] = {}
    for key in sorted(all_keys):
        ex_val = ex_section.get(key, [])
        in_val = in_section.get(key, [])
        if isinstance(ex_val, list) and isinstance(in_val, list):
            union = _merge_list_union(ex_val, in_val)
            if union:
                merged[key] = union
        elif in_val:
            merged[key] = in_val
        elif ex_val:
            merged[key] = ex_val
    return merged


def merge_configs(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """Merge incoming config into existing config.

    Merge rules:
    - identities: incoming overrides existing by name, new names added
    - packages.*: each manager's sub-lists are union-merged
    - tools: sorted union
    """
    result: dict[str, Any] = {}

    # Merge identities
    ex_ids = get_identities(existing)
    in_ids = get_identities(incoming)
    merged_ids = dict(ex_ids)
    merged_ids.update(in_ids)
    if merged_ids:
        result["identities"] = merged_ids

    # Merge packages — handle every manager key generically
    ex_pkgs = get_packages(existing)
    in_pkgs = get_packages(incoming)
    all_mgr_keys = set(ex_pkgs) | set(in_pkgs)
    merged_pkgs: dict[str, Any] = {}

    for mgr_key in sorted(all_mgr_keys):
        ex_section = ex_pkgs.get(mgr_key, {})
        in_section = in_pkgs.get(mgr_key, {})
        if isinstance(ex_section, dict) and isinstance(in_section, dict):
            merged_section = _merge_pkg_section(ex_section, in_section)
            if merged_section:
                merged_pkgs[mgr_key] = merged_section
        elif in_section:
            merged_pkgs[mgr_key] = in_section
        elif ex_section:
            merged_pkgs[mgr_key] = ex_section

    if merged_pkgs:
        result["packages"] = merged_pkgs

    # Merge tools
    ex_tools = get_tools(existing)
    in_tools = get_tools(incoming)
    merged_tools = _merge_list_union(ex_tools, in_tools)
    if merged_tools:
        result["tools"] = merged_tools

    return result


# ---------------------------------------------------------------------------
# Config update (for sync)
# ---------------------------------------------------------------------------


def update_packages(
    config: dict[str, Any],
    packages: dict[str, Any],
    tools: list[str],
) -> dict[str, Any]:
    """Update packages and tools in config, preserving identities.

    This replaces (not merges) the packages and tools sections
    with freshly scanned data.
    """
    result: dict[str, Any] = {}

    # Preserve identities
    identities = get_identities(config)
    if identities:
        result["identities"] = identities

    # Set new packages
    if packages:
        result["packages"] = packages

    # Set new tools
    if tools:
        result["tools"] = tools

    return result
