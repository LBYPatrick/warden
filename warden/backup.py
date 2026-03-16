"""Backup and restore logic for git identities and SSH config."""

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


def _write_marker(tar: tarfile.TarFile, archive_type: str) -> None:
    """Write a .warden-marker JSON file as the first entry in the archive."""
    marker = {
        "type": archive_type,
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


def _validate_archive(tar: tarfile.TarFile, expected_type: str) -> bool:
    """Validate archive marker file matches expected type.

    Returns True if valid. Prints error and returns False otherwise.
    """
    names = tar.getnames()

    # Check marker file
    if MARKER_FILE not in names:
        display.error("Not a valid warden backup (missing marker file)")
        return False

    try:
        with tar.extractfile(tar.getmember(MARKER_FILE)) as f:
            if f:
                marker = json.loads(f.read().decode("utf-8"))
            else:
                display.error("Failed to read marker file")
                return False
    except (json.JSONDecodeError, KeyError):
        display.error("Corrupt marker file")
        return False

    actual_type = marker.get("type")
    if actual_type != expected_type:
        display.error(
            f"Archive type mismatch: expected '{expected_type}', got '{actual_type}'"
        )
        return False

    # Double safety: manually verify expected content files
    if expected_type in ("git", "all"):
        if "warden.jsonc" not in names:
            display.error("Archive missing warden.jsonc (expected for git backup)")
            return False
    if expected_type in ("ssh", "all"):
        if "ssh_config" not in names:
            display.error("Archive missing ssh_config (expected for ssh backup)")
            return False

    # Validate all member paths
    for name in names:
        if not _validate_tar_member(name):
            display.error(f"Archive contains unsafe path: {name}")
            return False

    return True


def _open_and_validate(
    archive_path: Path, expected_type: str
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

    if not _validate_archive(tar, expected_type):
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
# Git backup / restore
# ---------------------------------------------------------------------------


def backup_git(
    config_path: Path,
    config_data: dict[str, Any],
    output: str | None,
    *,
    dry_run: bool = False,
) -> None:
    """Backup identities and all referenced signing keys.

    Only the identities section is included — packages and tools are excluded.
    """
    label = "Dry Run — " if dry_run else ""
    display.banner(f"{label}Backup Git Identities")

    start = time.monotonic()
    out_path = Path(
        output or f"warden-git-backup-{datetime.now().strftime('%Y-%m-%d')}.tar.gz"
    )
    if out_path.exists() and not dry_run:
        display.warn(f"Overwriting {out_path}")

    identities = get_identities(config_data)

    display.step(1, 2, "Collecting keys")
    modified_identities, keys_to_add = _collect_git_keys(identities)
    seen: set[str] = {a for _, a in keys_to_add}

    if dry_run:
        display.info(f"Would create archive: {out_path}")
        display.info(
            f"Would include {len(modified_identities)} targets, {len(seen)} key files"
        )
        display.info("Packages and tools excluded from git backup")
        return

    display.step(2, 2, "Creating archive")
    # Only save identities in git backup (no packages/tools)
    archive_config = {"identities": modified_identities}
    config_bytes = serialize_config(archive_config).encode("utf-8")

    with tarfile.open(str(out_path), "w:gz") as tar:
        _write_marker(tar, "git")
        _add_bytes_to_tar(tar, "warden.jsonc", config_bytes)
        written = _add_keys_to_tar(tar, keys_to_add)

    elapsed = time.monotonic() - start
    display.success_timed(f"Archive created: {out_path}", elapsed)
    display.info(f"{len(modified_identities)} targets, {written} key files")


def restore_git(archive_path: Path, *, dry_run: bool = False) -> None:
    """Restore git identities from a warden backup archive.

    Uses merge algorithm: incoming identities override existing by name,
    new names are added. Packages and tools are preserved from existing config.
    """
    label = "Dry Run — " if dry_run else ""
    display.banner(f"{label}Restore Git Identities")

    start = time.monotonic()
    tar = _open_and_validate(archive_path, "git")
    with tar:
        if dry_run:
            key_count = _extract_keys(tar, dry_run=True)
            display.info(f"Would merge config into {WARDEN_DIR / 'warden.jsonc'}")
            display.info(f"{key_count} key files (no changes made)")
            return

        display.step(1, 2, "Extracting keys")
        key_count = _extract_keys(tar)

        display.step(2, 2, "Merging config")
        with tar.extractfile(tar.getmember("warden.jsonc")) as src:
            if src:
                incoming_text = src.read().decode("utf-8")
            else:
                display.error("Failed to read warden.jsonc from archive")
                sys.exit(1)

    _merge_warden_config(incoming_text)
    elapsed = time.monotonic() - start
    display.success_timed(f"Restored {key_count} key files to {KEYS_DIR}", elapsed)


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


# ---------------------------------------------------------------------------
# SSH backup / restore
# ---------------------------------------------------------------------------


def backup_ssh(
    output: str | None,
    include_missing: bool = False,
    *,
    dry_run: bool = False,
) -> None:
    """Backup ~/.ssh/config and all referenced identity keys."""
    label = "Dry Run — " if dry_run else ""
    display.banner(f"{label}Backup SSH Config")

    start = time.monotonic()
    out_path = Path(
        output or f"warden-ssh-backup-{datetime.now().strftime('%Y-%m-%d')}.tar.gz"
    )
    if out_path.exists() and not dry_run:
        display.warn(f"Overwriting {out_path}")

    display.step(1, 2, "Collecting keys")
    preamble, blocks, path_map, keys_to_add = _collect_ssh_keys(include_missing)
    seen: set[str] = {a for _, a in keys_to_add}

    if dry_run:
        display.info(f"Would create archive: {out_path}")
        display.info(
            f"Would include {len(path_map)} hosts with keys, {len(seen)} key files"
        )
        return

    display.step(2, 2, "Creating archive")
    rewritten_blocks = rewrite_identity_files(blocks, path_map)
    modified_config = serialize_ssh_config(preamble, rewritten_blocks)

    with tarfile.open(str(out_path), "w:gz") as tar:
        _write_marker(tar, "ssh")
        _add_bytes_to_tar(tar, "ssh_config", modified_config.encode("utf-8"))
        written = _add_keys_to_tar(tar, keys_to_add)

    elapsed = time.monotonic() - start
    display.success_timed(f"Archive created: {out_path}", elapsed)
    display.info(f"{len(path_map)} hosts with keys, {written} key files")


def restore_ssh(archive_path: Path, *, dry_run: bool = False) -> None:
    """Restore SSH config and keys from a warden backup archive."""
    label = "Dry Run — " if dry_run else ""
    display.banner(f"{label}Restore SSH Config")

    start = time.monotonic()
    tar = _open_and_validate(archive_path, "ssh")
    with tar:
        if dry_run:
            key_count = _extract_keys(tar, dry_run=True)
            ssh_config_path = Path.home() / ".ssh" / "config"
            with tar.extractfile(tar.getmember("ssh_config")) as src:
                restored_text = src.read().decode("utf-8") if src else ""

            if ssh_config_path.is_file():
                existing_text = ssh_config_path.read_text(encoding="utf-8")
                _, updated, added = merge_ssh_configs(existing_text, restored_text)
                display.info(
                    f"Would backup {ssh_config_path} to {ssh_config_path.with_suffix('.bak')}"
                )
                display.info(
                    f"Would merge: {updated} hosts updated, {added} hosts added"
                )
            else:
                display.info(f"Would write SSH config to {ssh_config_path}")
            display.info(f"{key_count} key files (no changes made)")
            return

        display.step(1, 2, "Extracting keys")
        key_count = _extract_keys(tar)

        display.step(2, 2, "Merging SSH config")
        with tar.extractfile(tar.getmember("ssh_config")) as src:
            if src:
                restored_text = src.read().decode("utf-8")
            else:
                display.error("Failed to read ssh_config from archive")
                sys.exit(1)

    _merge_ssh_config(restored_text)
    elapsed = time.monotonic() - start
    display.success_timed(f"Restored {key_count} key files to {KEYS_DIR}", elapsed)


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
# All backup / restore
# ---------------------------------------------------------------------------


def backup_all(
    config_path: Path,
    config_data: dict[str, Any],
    output: str | None,
    include_missing: bool = False,
    *,
    dry_run: bool = False,
) -> None:
    """Backup both git identities and SSH config into a single archive.

    The full warden.jsonc (identities + packages + tools) is included.
    """
    label = "Dry Run — " if dry_run else ""
    display.banner(f"{label}Backup All (Git + SSH)")

    start = time.monotonic()
    out_path = Path(
        output or f"warden-all-backup-{datetime.now().strftime('%Y-%m-%d')}.tar.gz"
    )
    if out_path.exists() and not dry_run:
        display.warn(f"Overwriting {out_path}")

    identities = get_identities(config_data)

    # Collect git keys
    display.step(1, 3, "Collecting git keys")
    modified_identities, git_keys = _collect_git_keys(identities)

    # Collect SSH keys
    display.step(2, 3, "Collecting SSH keys")
    preamble, blocks, path_map, ssh_keys = _collect_ssh_keys(include_missing)

    all_keys = git_keys + ssh_keys
    seen: set[str] = {a for _, a in all_keys}

    if dry_run:
        display.info(f"Would create archive: {out_path}")
        display.info(
            f"Would include {len(modified_identities)} git targets, "
            f"{len(path_map)} SSH hosts, {len(seen)} key files"
        )
        display.info("Full config included (identities + packages + tools)")
        return

    display.step(3, 3, "Creating archive")
    # Full config: replace identities with key-rewritten version, keep packages/tools
    full_config: dict[str, Any] = {"identities": modified_identities}
    from warden.config import get_packages, get_tools

    pkgs = get_packages(config_data)
    tools = get_tools(config_data)
    if pkgs:
        full_config["packages"] = pkgs
    if tools:
        full_config["tools"] = tools

    git_config_bytes = serialize_config(full_config).encode("utf-8")
    rewritten_blocks = rewrite_identity_files(blocks, path_map)
    ssh_config_text = serialize_ssh_config(preamble, rewritten_blocks)

    with tarfile.open(str(out_path), "w:gz") as tar:
        _write_marker(tar, "all")
        _add_bytes_to_tar(tar, "warden.jsonc", git_config_bytes)
        _add_bytes_to_tar(tar, "ssh_config", ssh_config_text.encode("utf-8"))
        written = _add_keys_to_tar(tar, all_keys)

    elapsed = time.monotonic() - start
    display.success_timed(f"Archive created: {out_path}", elapsed)
    display.info(
        f"{len(modified_identities)} git targets, "
        f"{len(path_map)} SSH hosts, {written} key files"
    )


def restore_all(archive_path: Path, *, dry_run: bool = False) -> None:
    """Restore both git identities and SSH config from a single archive.

    Uses merge algorithm for warden.jsonc.
    """
    label = "Dry Run — " if dry_run else ""
    display.banner(f"{label}Restore All (Git + SSH)")

    start = time.monotonic()
    tar = _open_and_validate(archive_path, "all")
    with tar:
        if dry_run:
            key_count = _extract_keys(tar, dry_run=True)
            display.info(f"Would merge config into {WARDEN_DIR / 'warden.jsonc'}")

            ssh_config_path = Path.home() / ".ssh" / "config"
            with tar.extractfile(tar.getmember("ssh_config")) as src:
                restored_text = src.read().decode("utf-8") if src else ""
            if ssh_config_path.is_file():
                existing = ssh_config_path.read_text(encoding="utf-8")
                _, updated, added = merge_ssh_configs(existing, restored_text)
                display.info(
                    f"Would backup {ssh_config_path} to {ssh_config_path.with_suffix('.bak')}"
                )
                display.info(
                    f"Would merge SSH: {updated} hosts updated, {added} hosts added"
                )
            else:
                display.info(f"Would write SSH config to {ssh_config_path}")
            display.info(f"{key_count} key files (no changes made)")
            return

        display.step(1, 3, "Extracting keys")
        key_count = _extract_keys(tar)

        display.step(2, 3, "Merging config")
        with tar.extractfile(tar.getmember("warden.jsonc")) as src:
            if src:
                incoming_text = src.read().decode("utf-8")
            else:
                display.error("Failed to read warden.jsonc from archive")
                sys.exit(1)

        display.step(3, 3, "Merging SSH config")
        with tar.extractfile(tar.getmember("ssh_config")) as src:
            if src:
                restored_ssh = src.read().decode("utf-8")
            else:
                display.error("Failed to read ssh_config from archive")
                sys.exit(1)

    _merge_warden_config(incoming_text)
    _merge_ssh_config(restored_ssh)
    elapsed = time.monotonic() - start
    display.success_timed(f"Restored {key_count} key files to {KEYS_DIR}", elapsed)
