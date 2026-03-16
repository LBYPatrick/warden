"""Backup and restore logic for warden config, SSH, and packages."""

import hashlib
import io
import json
import sys
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from warden import display
from warden.config import get_identities, merge_configs, serialize_config
from warden.ssh_config import (
    HostBlock,
    get_identity_files,
    merge_ssh_configs,
    parse_ssh_config,
    rewrite_identity_files,
    serialize_ssh_config,
)

WARDEN_DIR = Path.home() / ".warden"
KEYS_DIR = WARDEN_DIR / "keys"

MARKER_FILE = ".warden-marker"

ALL_MODULES = ("git", "ssh", "pkg")


def _resolve_output_path(output: str | None, default_name: str) -> Path:
    """Resolve an output path relative to the user's original working directory.

    The bin/warden wrapper changes cwd to the project root before running Python,
    so we use WARDEN_ORIG_CWD (set by the wrapper) to resolve relative paths
    against the directory the user actually invoked warden from.
    """
    import os

    orig_cwd = os.environ.get("WARDEN_ORIG_CWD")
    if output:
        p = Path(output)
    else:
        p = Path(default_name)

    if not p.is_absolute() and orig_cwd:
        p = Path(orig_cwd) / p

    return p.resolve()


def parse_modules(spec: str) -> list[str]:
    """Parse a comma-delimited module spec into a sorted, validated list.

    Accepts 'all' as shorthand for all modules. Exits on invalid module names.
    """
    raw = [s.strip().lower() for s in spec.split(",") if s.strip()]
    if "all" in raw:
        return sorted(ALL_MODULES)
    invalid = [m for m in raw if m not in ALL_MODULES]
    if invalid:
        display.error(
            f"Unknown module(s): {', '.join(invalid)}. "
            f"Valid modules: {', '.join(ALL_MODULES)}, all"
        )
        sys.exit(1)
    # Deduplicate and sort for deterministic archives
    return sorted(set(raw))


def path_hash(absolute_path: str) -> str:
    """6-digit hex hash of the absolute path string."""
    return hashlib.sha256(absolute_path.encode("utf-8")).hexdigest()[:6]


def _strip_existing_hash(name: str) -> str:
    """Strip a trailing _<6-hex-chars> suffix from a name.

    Prevents hash stacking when backing up previously restored keys.
    E.g. 'id_ed25519_abc123' -> 'id_ed25519'.
    """
    import re

    return re.sub(r"_[0-9a-f]{6}$", "", name)


def hashed_key_name(original_name: str, hash_suffix: str) -> str:
    """Insert hash before extension: id_ed25519.pub -> id_ed25519_a3f2b1.pub.

    Strips any existing hash suffix first to prevent stacking.
    """
    p = Path(original_name)
    if p.suffix:
        stem = _strip_existing_hash(p.stem)
        return f"{stem}_{hash_suffix}{p.suffix}"
    base = _strip_existing_hash(p.name)
    return f"{base}_{hash_suffix}"


def _collect_key_files(key_path_str: str) -> list[tuple[Path, bool]]:
    """Collect existing key files (private + pub) from a key reference."""
    expanded = Path(key_path_str).expanduser().resolve()
    files: list[tuple[Path, bool]] = []

    if str(expanded).endswith(".pub"):
        private = Path(str(expanded)[:-4])
        pub = expanded
    else:
        private = expanded
        pub = Path(str(expanded) + ".pub")

    if private.is_file():
        files.append((private, False))
    if pub.is_file():
        files.append((pub, True))

    return files


def _add_bytes_to_tar(tar: tarfile.TarFile, name: str, data: bytes) -> None:
    """Add in-memory bytes as a file to a tar archive."""
    info = tarfile.TarInfo(name=name)
    info.size = len(data)
    tar.addfile(info, io.BytesIO(data))


def _validate_tar_member(name: str) -> bool:
    """Reject path traversal and absolute paths."""
    return not (name.startswith("/") or ".." in name.split("/"))


# ---------------------------------------------------------------------------
# Marker file helpers
# ---------------------------------------------------------------------------


def _write_marker(tar: tarfile.TarFile, modules: list[str]) -> None:
    """Write a .warden-marker JSON file as the first entry in the archive."""
    marker = {
        "modules": sorted(modules),
        "version": _get_version(),
        "created": datetime.now(timezone.utc).isoformat(),
    }
    _add_bytes_to_tar(tar, MARKER_FILE, json.dumps(marker).encode("utf-8"))


def _get_version() -> str:
    """Read version from VERSION file or return default."""
    version_file = Path(__file__).parent.parent / "VERSION"
    if version_file.is_file():
        return version_file.read_text().strip()
    return "0.1.0"


def _read_marker(tar: tarfile.TarFile) -> list[str] | None:
    """Read the marker file and return the modules list, or None on error."""
    names = tar.getnames()
    if MARKER_FILE not in names:
        display.error("Not a valid warden backup (missing marker file)")
        return None

    try:
        with tar.extractfile(tar.getmember(MARKER_FILE)) as f:
            if f:
                marker = json.loads(f.read().decode("utf-8"))
            else:
                display.error("Failed to read marker file")
                return None
    except (json.JSONDecodeError, KeyError):
        display.error("Corrupt marker file")
        return None

    # Support new format (modules list) and legacy format (type string)
    if "modules" in marker:
        return marker["modules"]
    if "type" in marker:
        legacy_type = marker["type"]
        if legacy_type == "all":
            return sorted(ALL_MODULES)
        if legacy_type in ALL_MODULES:
            return [legacy_type]
        display.error(f"Unknown legacy archive type: {legacy_type}")
        return None

    display.error("Marker file missing 'modules' field")
    return None


def _validate_archive(
    tar: tarfile.TarFile, requested_modules: list[str]
) -> list[str] | None:
    """Validate archive and check that requested modules are available.

    Returns the archive's modules list on success, or None on failure.
    """
    archive_modules = _read_marker(tar)
    if archive_modules is None:
        return None

    names = tar.getnames()

    # Validate all member paths
    for name in names:
        if not _validate_tar_member(name):
            display.error(f"Archive contains unsafe path: {name}")
            return None

    # Verify content files match claimed modules
    if any(m in archive_modules for m in ("git", "pkg")):
        if "warden.jsonc" not in names:
            display.error("Archive missing warden.jsonc")
            return None
    if "ssh" in archive_modules:
        if "ssh_config" not in names:
            display.error("Archive missing ssh_config")
            return None

    # Check that all requested modules exist in the archive
    missing = [m for m in requested_modules if m not in archive_modules]
    if missing:
        display.error(
            f"Archive does not contain module(s): {', '.join(missing)} "
            f"(available: {', '.join(archive_modules)})"
        )
        return None

    return archive_modules


def _open_and_validate(
    archive_path: Path, requested_modules: list[str]
) -> tarfile.TarFile | None:
    """Open a tar.gz archive and validate it. Returns TarFile or exits."""
    if not archive_path.is_file():
        display.error(f"Archive not found: {archive_path}")
        sys.exit(1)

    try:
        tar = tarfile.open(str(archive_path), "r:gz")
    except tarfile.TarError:
        display.error("Not a valid tar.gz archive")
        sys.exit(1)

    if _validate_archive(tar, requested_modules) is None:
        tar.close()
        sys.exit(1)

    return tar


def _extract_keys(tar: tarfile.TarFile, *, dry_run: bool = False) -> int:
    """Extract keys/ members from archive to KEYS_DIR. Returns count."""
    if not dry_run:
        KEYS_DIR.mkdir(parents=True, exist_ok=True)

    count = 0
    for member in tar.getmembers():
        if member.name.startswith("keys/") and member.isfile():
            fname = member.name.removeprefix("keys/")
            if dry_run:
                display.info(f"Would restore {fname} to {KEYS_DIR}")
            else:
                dest = KEYS_DIR / fname
                with tar.extractfile(member) as src:
                    if src:
                        dest.write_bytes(src.read())
                if fname.endswith(".pub"):
                    dest.chmod(0o644)
                else:
                    dest.chmod(0o600)
                display.success(f"Restored {fname}")
            count += 1
    return count


def _add_keys_to_tar(tar: tarfile.TarFile, keys: list[tuple[Path, str]]) -> int:
    """Add key files to tar, deduplicating by archive name. Returns count."""
    written: set[str] = set()
    for real_path, archive_name in keys:
        if archive_name not in written:
            tar.add(str(real_path), arcname=archive_name)
            written.add(archive_name)
    return len(written)


# ---------------------------------------------------------------------------
# Git key collection helper
# ---------------------------------------------------------------------------


def _collect_git_keys(
    identities: dict[str, Any],
) -> tuple[dict[str, Any], list[tuple[Path, str]]]:
    """Collect keys from identities and build modified identities dict.

    Returns (modified_identities, keys_to_add).
    """
    modified: dict[str, Any] = {}
    keys_to_add: list[tuple[Path, str]] = []

    for target_name, target in identities.items():
        new_target = dict(target)
        signing_key = target.get("signing_key")
        if not signing_key:
            modified[target_name] = new_target
            continue

        key_files = _collect_key_files(signing_key)
        if not key_files:
            display.warn(f"No key files found for {target_name}: {signing_key}")
            modified[target_name] = new_target
            continue

        expanded = str(Path(signing_key).expanduser().resolve())
        if not expanded.endswith(".pub"):
            expanded = expanded + ".pub"
        h = path_hash(expanded)

        for real_path, is_pub in key_files:
            archive_name = "keys/" + hashed_key_name(real_path.name, h)
            keys_to_add.append((real_path, archive_name))
            display.success(f"Found {real_path.name}")

        pub_name = hashed_key_name(Path(expanded).name, h)
        new_target["signing_key"] = f"~/.warden/keys/{pub_name}"
        modified[target_name] = new_target

    return modified, keys_to_add


# ---------------------------------------------------------------------------
# SSH key collection helper
# ---------------------------------------------------------------------------


def _collect_ssh_keys(
    include_missing: bool = False,
) -> tuple[list[str], list[HostBlock], dict[str, str], list[tuple[Path, str]]]:
    """Collect keys from SSH config.

    Returns (preamble, blocks, path_map, keys_to_add).
    """

    ssh_config_path = Path.home() / ".ssh" / "config"
    if not ssh_config_path.is_file():
        display.error(f"No SSH config found at {ssh_config_path}")
        sys.exit(1)

    text = ssh_config_path.read_text(encoding="utf-8")
    preamble, blocks = parse_ssh_config(text)
    identity_files = get_identity_files(blocks)

    path_map: dict[str, str] = {}
    keys_to_add: list[tuple[Path, str]] = []

    for block_name, id_path in identity_files.items():
        resolved = id_path.resolve()
        private = resolved
        pub = Path(str(resolved) + ".pub")

        if not private.is_file():
            if include_missing:
                display.warn(
                    f"Key missing for {block_name}: {resolved} (including anyway)"
                )
            else:
                display.skip(f"Skipping {block_name}: key not found at {resolved}")
                continue

        h = path_hash(str(resolved))
        hashed_priv = hashed_key_name(private.name, h)
        new_path = f"~/.warden/keys/{hashed_priv}"
        path_map[str(resolved)] = new_path

        keys_to_add.append((private, "keys/" + hashed_priv))
        display.success(f"Found {private.name} ({block_name})")

        if pub.is_file():
            hashed_pub = hashed_key_name(pub.name, h)
            keys_to_add.append((pub, "keys/" + hashed_pub))

    return preamble, blocks, path_map, keys_to_add


# ---------------------------------------------------------------------------
# Merge helpers
# ---------------------------------------------------------------------------


def _merge_warden_config(incoming_text: str) -> None:
    """Merge incoming warden.jsonc into existing one at WARDEN_DIR."""
    import json5

    incoming = json5.loads(incoming_text)
    config_dest = WARDEN_DIR / "warden.jsonc"

    WARDEN_DIR.mkdir(parents=True, exist_ok=True)

    if config_dest.is_file():
        try:
            existing = json5.loads(config_dest.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            existing = {}

        merged = merge_configs(existing, incoming)
        config_dest.write_text(serialize_config(merged), encoding="utf-8")
        display.success(f"Merged config into {config_dest}")
    else:
        config_dest.write_text(serialize_config(incoming), encoding="utf-8")
        display.success(f"Config written to {config_dest}")


def _merge_ssh_config(restored_text: str) -> None:
    """Merge restored SSH config into ~/.ssh/config."""
    ssh_config_path = Path.home() / ".ssh" / "config"

    if ssh_config_path.is_file():
        existing_text = ssh_config_path.read_text(encoding="utf-8")
        bak_path = ssh_config_path.with_suffix(".bak")
        bak_path.write_text(existing_text, encoding="utf-8")
        display.success(f"Backed up existing config to {bak_path}")

        merged, updated, added = merge_ssh_configs(existing_text, restored_text)
        ssh_config_path.write_text(merged, encoding="utf-8")
        display.success(f"Merged: {updated} hosts updated, {added} hosts added")
    else:
        ssh_config_path.parent.mkdir(parents=True, exist_ok=True)
        ssh_config_path.write_text(restored_text, encoding="utf-8")
        ssh_config_path.chmod(0o644)
        display.success(f"Written SSH config to {ssh_config_path}")


# ---------------------------------------------------------------------------
# Unified backup
# ---------------------------------------------------------------------------


def backup(
    modules: list[str],
    config_data: dict[str, Any],
    output: str | None,
    include_missing: bool = False,
    *,
    dry_run: bool = False,
) -> None:
    """Backup selected modules into a single tar.gz archive.

    Modules: 'git' (identities + keys), 'ssh' (SSH config + keys),
    'pkg' (packages + tools).
    """
    from warden.config import get_packages, get_tools

    label_parts = [m for m in ALL_MODULES if m in modules]
    label = "Dry Run — " if dry_run else ""
    mod_label = ", ".join(label_parts)
    display.banner(f"{label}Backup [{mod_label}]")

    start = time.monotonic()

    default_name = (
        f"warden-backup-{'+'.join(label_parts)}"
        f"-{datetime.now().strftime('%Y-%m-%d')}.tar.gz"
    )
    out_path = _resolve_output_path(output, default_name)
    if out_path.exists() and not dry_run:
        display.warn(f"Overwriting {out_path}")

    has_git = "git" in modules
    has_ssh = "ssh" in modules
    has_pkg = "pkg" in modules

    # Collect data for each module
    step = 0
    total_steps = sum([has_git, has_ssh]) + 1  # collection steps + archive step

    modified_identities: dict[str, Any] = {}
    git_keys: list[tuple[Path, str]] = []
    preamble: list[str] = []
    blocks: list[HostBlock] = []
    path_map: dict[str, str] = {}
    ssh_keys: list[tuple[Path, str]] = []

    if has_git:
        step += 1
        display.step(step, total_steps, "Collecting git keys")
        identities = get_identities(config_data)
        modified_identities, git_keys = _collect_git_keys(identities)

    if has_ssh:
        step += 1
        display.step(step, total_steps, "Collecting SSH keys")
        preamble, blocks, path_map, ssh_keys = _collect_ssh_keys(include_missing)

    all_keys = git_keys + ssh_keys

    if dry_run:
        display.info(f"Would create archive: {out_path}")
        if has_git:
            display.info(
                f"  git: {len(modified_identities)} targets, {len(git_keys)} key files"
            )
        if has_ssh:
            display.info(f"  ssh: {len(path_map)} hosts, {len(ssh_keys)} key files")
        if has_pkg:
            pkgs = get_packages(config_data)
            tools = get_tools(config_data)
            _print_pkg_summary(pkgs, tools, indent=True)
        return

    step += 1
    display.step(step, total_steps, "Creating archive")

    # Build warden.jsonc content based on selected modules
    archive_config: dict[str, Any] = {}
    if has_git:
        archive_config["identities"] = modified_identities
    if has_pkg:
        pkgs = get_packages(config_data)
        tools = get_tools(config_data)
        if pkgs:
            archive_config["packages"] = pkgs
        if tools:
            archive_config["tools"] = tools

    with tarfile.open(str(out_path), "w:gz") as tar:
        _write_marker(tar, modules)

        if archive_config:
            config_bytes = serialize_config(archive_config).encode("utf-8")
            _add_bytes_to_tar(tar, "warden.jsonc", config_bytes)

        if has_ssh:
            rewritten_blocks = rewrite_identity_files(blocks, path_map)
            ssh_text = serialize_ssh_config(preamble, rewritten_blocks)
            _add_bytes_to_tar(tar, "ssh_config", ssh_text.encode("utf-8"))

        written = _add_keys_to_tar(tar, all_keys)

    elapsed = time.monotonic() - start
    display.success_timed(f"Archive created: {out_path}", elapsed)

    summary_parts: list[str] = []
    if has_git:
        summary_parts.append(f"{len(modified_identities)} git targets")
    if has_ssh:
        summary_parts.append(f"{len(path_map)} SSH hosts")
    if written:
        summary_parts.append(f"{written} key files")
    if summary_parts:
        display.info(", ".join(summary_parts))


# ---------------------------------------------------------------------------
# Unified restore
# ---------------------------------------------------------------------------


def restore(
    modules: list[str],
    archive_path: Path,
    *,
    dry_run: bool = False,
) -> None:
    """Restore selected modules from a backup archive.

    Validates that each requested module is present in the archive.
    Modules: 'git' (identities + keys), 'ssh' (SSH config + keys),
    'pkg' (packages + tools).
    """
    label_parts = [m for m in ALL_MODULES if m in modules]
    label = "Dry Run — " if dry_run else ""
    mod_label = ", ".join(label_parts)
    display.banner(f"{label}Restore [{mod_label}]")

    start = time.monotonic()
    tar = _open_and_validate(archive_path, modules)

    has_git = "git" in modules
    has_ssh = "ssh" in modules
    has_pkg = "pkg" in modules
    has_keys = has_git or has_ssh

    with tar:
        if dry_run:
            if has_keys:
                _extract_keys(tar, dry_run=True)
            if has_git or has_pkg:
                display.info(f"Would merge config into {WARDEN_DIR / 'warden.jsonc'}")
            if has_ssh:
                ssh_config_path = Path.home() / ".ssh" / "config"
                with tar.extractfile(tar.getmember("ssh_config")) as src:
                    restored_text = src.read().decode("utf-8") if src else ""
                if ssh_config_path.is_file():
                    existing = ssh_config_path.read_text(encoding="utf-8")
                    _, updated, added = merge_ssh_configs(existing, restored_text)
                    display.info(
                        f"Would merge SSH: {updated} hosts updated, {added} hosts added"
                    )
                else:
                    display.info(f"Would write SSH config to {ssh_config_path}")
            display.info("No changes made")
            return

        step = 0
        total_steps = sum([has_keys, has_git or has_pkg, has_ssh])

        key_count = 0
        if has_keys:
            step += 1
            display.step(step, total_steps, "Extracting keys")
            key_count = _extract_keys(tar)

        incoming_text = None
        if has_git or has_pkg:
            step += 1
            display.step(step, total_steps, "Merging config")
            with tar.extractfile(tar.getmember("warden.jsonc")) as src:
                if src:
                    incoming_text = src.read().decode("utf-8")
                else:
                    display.error("Failed to read warden.jsonc from archive")
                    sys.exit(1)

        restored_ssh = None
        if has_ssh:
            step += 1
            display.step(step, total_steps, "Merging SSH config")
            with tar.extractfile(tar.getmember("ssh_config")) as src:
                if src:
                    restored_ssh = src.read().decode("utf-8")
                else:
                    display.error("Failed to read ssh_config from archive")
                    sys.exit(1)

    if incoming_text is not None:
        _merge_warden_config(incoming_text)
    if restored_ssh is not None:
        _merge_ssh_config(restored_ssh)

    elapsed = time.monotonic() - start
    parts: list[str] = []
    if key_count:
        parts.append(f"{key_count} key files to {KEYS_DIR}")
    if incoming_text is not None:
        parts.append(f"config to {WARDEN_DIR / 'warden.jsonc'}")
    if restored_ssh is not None:
        parts.append("SSH config merged")
    display.success_timed("Restored " + ", ".join(parts), elapsed)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _print_pkg_summary(
    pkgs: dict[str, Any], tools: list[str], *, indent: bool = False
) -> None:
    """Print a summary of packages and tools."""
    prefix = "  " if indent else ""
    total = 0
    for mgr, section in pkgs.items():
        if isinstance(section, dict):
            for sub_key, items in section.items():
                if isinstance(items, list):
                    count = len(items)
                    total += count
                    display.info(f"{prefix}{mgr}/{sub_key}: {count}")
    if tools:
        display.info(f"{prefix}tools: {len(tools)}")
        total += len(tools)
    display.info(f"{prefix}Total: {total} entries")
