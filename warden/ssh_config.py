"""SSH config parser, serializer, and merger."""

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class HostBlock:
    name: str
    lines: list[str] = field(default_factory=list)
    options: dict[str, str] = field(default_factory=dict)


def parse_ssh_config(text: str) -> tuple[list[str], list[HostBlock]]:
    """Parse SSH config text into preamble lines and Host blocks."""
    preamble: list[str] = []
    blocks: list[HostBlock] = []
    current: HostBlock | None = None

    for raw_line in text.splitlines():
        stripped = raw_line.strip()

        # Detect Host or Match directive
        m = re.match(r"^(Host|Match)\s+(.+)", stripped, re.IGNORECASE)
        if m:
            if current is not None:
                blocks.append(current)
            current = HostBlock(name=stripped)
            current.lines.append(raw_line)
            continue

        if current is None:
            preamble.append(raw_line)
        else:
            current.lines.append(raw_line)
            # Parse key-value option
            kv = re.match(r"^\s+(\S+)\s+(.+)", raw_line)
            if kv and not stripped.startswith("#"):
                current.options[kv.group(1)] = kv.group(2).strip()

    if current is not None:
        blocks.append(current)

    return preamble, blocks


def serialize_ssh_config(preamble: list[str], blocks: list[HostBlock]) -> str:
    """Reconstruct SSH config text from preamble and blocks."""
    parts: list[str] = []

    if preamble:
        parts.extend(preamble)

    for block in blocks:
        parts.extend(block.lines)

    result = "\n".join(parts)
    if not result.endswith("\n"):
        result += "\n"
    return result


def merge_ssh_configs(existing_text: str, restored_text: str) -> tuple[str, int, int]:
    """Merge restored SSH config into existing one.

    Returns:
        Tuple of (merged_text, updated_count, added_count).
    """
    ex_preamble, ex_blocks = parse_ssh_config(existing_text)
    _, re_blocks = parse_ssh_config(restored_text)

    # Build ordered index of existing blocks by name
    existing_index: dict[str, int] = {}
    for i, block in enumerate(ex_blocks):
        existing_index[block.name] = i

    updated = 0
    added = 0

    for rb in re_blocks:
        if rb.name in existing_index:
            ex_blocks[existing_index[rb.name]] = rb
            updated += 1
        else:
            ex_blocks.append(rb)
            added += 1

    return serialize_ssh_config(ex_preamble, ex_blocks), updated, added


def get_identity_files(blocks: list[HostBlock]) -> dict[str, Path]:
    """Return mapping of block name to expanded IdentityFile path."""
    result: dict[str, Path] = {}
    for block in blocks:
        identity = block.options.get("IdentityFile")
        if identity:
            result[block.name] = Path(identity).expanduser()
    return result


def rewrite_identity_files(
    blocks: list[HostBlock],
    path_map: dict[str, str],
) -> list[HostBlock]:
    """Rewrite IdentityFile lines in blocks using path_map.

    Args:
        blocks: Parsed host blocks.
        path_map: Maps original expanded absolute path -> new path string.

    Returns:
        New list of blocks with rewritten lines.
    """
    new_blocks: list[HostBlock] = []
    for block in blocks:
        identity = block.options.get("IdentityFile")
        if identity:
            expanded = str(Path(identity).expanduser().resolve())
            new_path = path_map.get(expanded)
            if new_path:
                new_lines = []
                for line in block.lines:
                    if re.match(r"^\s+IdentityFile\s+", line):
                        indent = re.match(r"^(\s+)", line)
                        prefix = indent.group(1) if indent else "  "
                        new_lines.append(f"{prefix}IdentityFile {new_path}")
                    else:
                        new_lines.append(line)
                new_block = HostBlock(
                    name=block.name,
                    lines=new_lines,
                    options={**block.options, "IdentityFile": new_path},
                )
                new_blocks.append(new_block)
                continue
        new_blocks.append(block)
    return new_blocks
