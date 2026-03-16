"""Warden — Describe the system you live in."""

import argparse
import sys
from pathlib import Path

from warden.backup import (
    backup_all,
    backup_git,
    backup_ssh,
    restore_all,
    restore_git,
    restore_ssh,
)
from warden.cli import cmd_apply, cmd_list, cmd_scan, cmd_show, cmd_switch, cmd_update
from warden.cn import detect_use_cn
from warden.config import load_config, resolve_config_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="warden",
        description="Describe the system you live in",
    )
    parser.add_argument(
        "-c",
        metavar="PATH",
        help="path to warden.jsonc config file",
        default=None,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="show what would be done without making any changes",
    )

    sub = parser.add_subparsers(dest="command", help="available commands")

    # switch
    p_switch = sub.add_parser(
        "switch",
        help="apply a git identity",
        description="Apply a git identity from your warden.jsonc config.",
    )
    p_switch.add_argument("target", help="target name from config")

    # list
    sub.add_parser(
        "list",
        help="list available targets",
        description="List all targets defined in your warden.jsonc config.",
    )

    # show
    p_show = sub.add_parser(
        "show",
        help="show current or specific target config",
        description="Show the current git identity or a specific target's config.",
    )
    p_show.add_argument("target", nargs="?", help="target name (omit for current)")

    # scan
    sub.add_parser(
        "scan",
        help="scan system and update packages/tools in config",
        description="Scan installed system packages and developer tools, "
        "then update the packages and tools sections in warden.jsonc.",
    )

    # apply
    p_apply = sub.add_parser(
        "apply",
        help="install packages/tools from config onto the system",
        description="Install packages and developer tools listed in warden.jsonc. "
        "Already-installed items are skipped unless --force is used.",
    )
    p_apply.add_argument(
        "-f",
        "--force",
        action="store_true",
        default=False,
        help="reinstall all packages even if already present",
    )

    # update
    p_update = sub.add_parser(
        "update",
        help="self-update warden from git",
        description="Pull latest changes from the warden repository and reinstall.",
    )
    p_update.add_argument(
        "branch",
        nargs="?",
        default=None,
        help="branch to pull from (default: current branch)",
    )

    # backup
    p_backup = sub.add_parser(
        "backup",
        help="backup git identities, SSH config, or both",
        description="Backup git identities, SSH config, or both into a tar.gz archive.",
    )
    backup_sub = p_backup.add_subparsers(dest="backup_command", help="what to backup")

    p_backup_git = backup_sub.add_parser(
        "git",
        help="backup warden.jsonc and signing keys",
        description="Backup identities and signing keys. "
        "System packages are excluded from git backups.",
    )
    p_backup_git.add_argument(
        "-o",
        "--output",
        metavar="FILE",
        help="output archive path (default: warden-git-backup-<date>.tar.gz)",
    )

    p_backup_ssh = backup_sub.add_parser(
        "ssh",
        help="backup ~/.ssh/config and identity keys",
        description="Backup SSH config and all referenced identity key files.",
    )
    p_backup_ssh.add_argument(
        "-o",
        "--output",
        metavar="FILE",
        help="output archive path (default: warden-ssh-backup-<date>.tar.gz)",
    )
    p_backup_ssh.add_argument(
        "--include-missing",
        action="store_true",
        default=False,
        help="include hosts whose key files are missing from disk",
    )

    p_backup_all = backup_sub.add_parser(
        "all",
        help="backup everything (git + SSH + packages + tools)",
        description="Backup identities, SSH config, system packages, and tools.",
    )
    p_backup_all.add_argument(
        "-o",
        "--output",
        metavar="FILE",
        help="output archive path (default: warden-all-backup-<date>.tar.gz)",
    )
    p_backup_all.add_argument(
        "--include-missing",
        action="store_true",
        default=False,
        help="include SSH hosts whose key files are missing from disk",
    )

    # restore
    p_restore = sub.add_parser(
        "restore",
        help="restore git identities, SSH config, or both from backup",
        description="Restore git identities, SSH config, or both from a warden backup archive.",
    )
    restore_sub = p_restore.add_subparsers(
        dest="restore_command", help="what to restore"
    )

    p_restore_git = restore_sub.add_parser(
        "git",
        help="restore git identities from backup archive",
        description="Restore identities and signing keys to ~/.warden/. "
        "Merges with existing config (preserving packages/tools).",
    )
    p_restore_git.add_argument("archive", help="path to backup .tar.gz archive")

    p_restore_ssh = restore_sub.add_parser(
        "ssh",
        help="restore SSH config from backup archive",
        description="Restore SSH config (merged) and identity keys to ~/.warden/.",
    )
    p_restore_ssh.add_argument("archive", help="path to backup .tar.gz archive")

    p_restore_all = restore_sub.add_parser(
        "all",
        help="restore everything from backup archive",
        description="Restore identities, SSH config, packages, and tools. "
        "Merges with existing config.",
    )
    p_restore_all.add_argument("archive", help="path to backup .tar.gz archive")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    dry = args.dry_run
    cn = detect_use_cn()

    match args.command:
        case "switch":
            config = load_config(args.c)
            cmd_switch(config, args.target, dry_run=dry)
        case "list":
            config = load_config(args.c)
            cmd_list(config)
        case "show":
            config = load_config(args.c)
            cmd_show(config, getattr(args, "target", None))
        case "scan":
            config_path = resolve_config_path(args.c)
            if config_path is None:
                # Create a new config if none exists
                config_path = Path.home() / ".warden" / "warden.jsonc"
                config_path.parent.mkdir(parents=True, exist_ok=True)
                config_path.write_text("{}\n", encoding="utf-8")
            config = load_config(args.c or str(config_path))
            cmd_scan(config, config_path, dry_run=dry)
        case "apply":
            config = load_config(args.c)
            cmd_apply(config, force=args.force, dry_run=dry, use_cn=cn)
        case "update":
            cmd_update(branch=args.branch, dry_run=dry, use_cn=cn)
        case "backup":
            if not args.backup_command:
                parser.parse_args(["backup", "--help"])
                return
            match args.backup_command:
                case "git":
                    config = load_config(args.c)
                    config_path = resolve_config_path(args.c)
                    backup_git(config_path, config, args.output, dry_run=dry)
                case "ssh":
                    backup_ssh(args.output, args.include_missing, dry_run=dry)
                case "all":
                    config = load_config(args.c)
                    config_path = resolve_config_path(args.c)
                    backup_all(
                        config_path,
                        config,
                        args.output,
                        args.include_missing,
                        dry_run=dry,
                    )
        case "restore":
            if not args.restore_command:
                parser.parse_args(["restore", "--help"])
                return
            match args.restore_command:
                case "git":
                    restore_git(Path(args.archive), dry_run=dry)
                case "ssh":
                    restore_ssh(Path(args.archive), dry_run=dry)
                case "all":
                    restore_all(Path(args.archive), dry_run=dry)


if __name__ == "__main__":
    main()
