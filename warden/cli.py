"""CLI command implementations for Warden."""

import subprocess
import sys
from pathlib import Path

from warden import display
from warden.config import find_target, resolve_ssh_command


def _git_config_set(key: str, value: str, *, dry_run: bool = False) -> None:
    """Set a git config value globally."""
    if dry_run:
        display.info(f"Would set {key} = {value}")
        return
    subprocess.run(
        ["git", "config", "--global", key, value],
        check=True,
        capture_output=True,
    )


def _git_config_unset(key: str, *, dry_run: bool = False) -> None:
    """Unset a git config value globally, ignoring if not set."""
    if dry_run:
        display.info(f"Would unset {key}")
        return
    subprocess.run(
        ["git", "config", "--global", "--unset", key],
        capture_output=True,
    )


def _git_config_get(key: str) -> str | None:
    """Get a git config value globally."""
    result = subprocess.run(
        ["git", "config", "--global", "--get", key],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return None


def cmd_switch(config: dict, target_name: str, *, dry_run: bool = False) -> None:
    """Apply a git identity from config."""
    result = find_target(config, target_name)
    if result is None:
        display.error(f'Target "{target_name}" not found')
        available = ", ".join(config.keys())
        display.info(f"Available: {available}")
        sys.exit(1)

    name, target = result
    label = "dry run — " if dry_run else ""
    display.header(f'{label}Switching to "{name}"')

    # user.name
    if "name" in target:
        _git_config_set("user.name", target["name"], dry_run=dry_run)
        if not dry_run:
            display.success(f"user.name = {target['name']}")

    # user.email
    if "email" in target:
        _git_config_set("user.email", target["email"], dry_run=dry_run)
        if not dry_run:
            display.success(f"user.email = {target['email']}")

    # user.signingkey
    if "signing_key" in target:
        expanded = str(Path(target["signing_key"]).expanduser())
        _git_config_set("user.signingkey", expanded, dry_run=dry_run)
        if not dry_run:
            display.success(f"user.signingkey = {expanded}")

        # core.sshCommand
        ssh_cmd = resolve_ssh_command(target["signing_key"])
        if ssh_cmd:
            _git_config_set("core.sshCommand", ssh_cmd, dry_run=dry_run)
            if not dry_run:
                display.success(f"core.sshCommand = {ssh_cmd}")
        else:
            _git_config_unset("core.sshCommand", dry_run=dry_run)
            if not dry_run:
                display.skip("core.sshCommand unset (default key)")

    # gpg format for SSH signing
    _git_config_set("gpg.format", "ssh", dry_run=dry_run)
    if not dry_run:
        display.success("gpg.format = ssh")

    _git_config_set("commit.gpgsign", "true", dry_run=dry_run)
    if not dry_run:
        display.success("commit.gpgsign = true")

    print()
    if dry_run:
        display.info(f"Would switch to {display.bold(name)} (no changes made)")
    else:
        display.success(f"Switched to {display.bold(name)}")


def cmd_list(config: dict) -> None:
    """List all available targets."""
    display.header("Available targets")
    for name, target in config.items():
        email = target.get("email", "")
        uname = target.get("name", "")
        label = f"{display.bold(name)}"
        detail = f"{uname} {display.dim(f'<{email}>')}"
        display.item(f"{label} — {detail}")
    print()


def cmd_show(config: dict, target_name: str | None = None) -> None:
    """Show current git config or a specific target's config."""
    if target_name is None:
        # Show current git identity
        display.header("Current git identity")
        fields = {
            "user.name": _git_config_get("user.name"),
            "user.email": _git_config_get("user.email"),
            "user.signingkey": _git_config_get("user.signingkey"),
            "core.sshCommand": _git_config_get("core.sshCommand"),
            "gpg.format": _git_config_get("gpg.format"),
            "commit.gpgsign": _git_config_get("commit.gpgsign"),
        }
        for key, val in fields.items():
            if val:
                display.kv(key, val)
            else:
                display.kv(key, display.dim("(not set)"))
        print()
        return

    result = find_target(config, target_name)
    if result is None:
        display.error(f'Target "{target_name}" not found')
        sys.exit(1)

    name, target = result
    display.header(f"Target: {name}")
    for key, val in target.items():
        expanded = str(Path(val).expanduser()) if key == "signing_key" else val
        display.kv(key, expanded)

    # Show derived ssh command
    if "signing_key" in target:
        ssh_cmd = resolve_ssh_command(target["signing_key"])
        if ssh_cmd:
            display.kv("ssh_command (derived)", ssh_cmd)
        else:
            display.kv("ssh_command (derived)", display.dim("(default key, unset)"))
    print()
