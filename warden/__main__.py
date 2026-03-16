"""Warden — Describe the system you live in."""

import os
import sys

# Pre-parse --no-color before any display imports so Console initializes correctly.
if "--no-color" in sys.argv:
    os.environ["WARDEN_NO_COLOR"] = "1"

import argparse  # noqa: E402
import re as _re  # noqa: E402
from pathlib import Path  # noqa: E402

from warden import display  # noqa: E402
from warden.backup import (  # noqa: E402
    backup_all,
    backup_git,
    backup_ssh,
    restore_all,
    restore_git,
    restore_ssh,
)
from warden.cli import (  # noqa: E402
    cmd_apply,
    cmd_install,
    cmd_install_list,
    cmd_list,
    cmd_scan,
    cmd_show,
    cmd_switch,
    cmd_update,
)
from warden.cn import detect_use_cn  # noqa: E402
from warden.config import load_config, resolve_config_path  # noqa: E402

# ---------------------------------------------------------------------------
# Colored argparse help
# ---------------------------------------------------------------------------


def _color_enabled() -> bool:
    return os.environ.get("WARDEN_NO_COLOR", "").strip().lower() not in (
        "1",
        "true",
        "yes",
    )


def _colorize_help(text: str) -> str:
    if not _color_enabled():
        return text
    text = _re.sub(
        r"^(usage:|positional arguments|options|optional arguments|available commands)(:?)",
        lambda m: f"\033[1m{m.group(1)}{m.group(2)}\033[0m",
        text,
        flags=_re.MULTILINE,
    )
    text = _re.sub(
        r"(?<=\s)(--?[a-zA-Z][\w-]*)",
        lambda m: f"\033[36m{m.group(1)}\033[0m",
        text,
    )
    text = _re.sub(
        r"(?<=\s)([A-Z][A-Z_:]+(?:\.\.\.)?)(?=[\s,\]\)])",
        lambda m: f"\033[2m{m.group(1)}\033[0m",
        text,
    )
    return text


class _CF(argparse.RawDescriptionHelpFormatter):
    def format_help(self) -> str:
        return _colorize_help(super().format_help())


def _sub(parent, **kw):
    """Create a subparsers group with colored help propagated."""
    return parent.add_subparsers(
        **kw,
        parser_class=lambda **k: argparse.ArgumentParser(**k, formatter_class=_CF),
    )


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="warden",
        description="Describe the system you live in",
        formatter_class=_CF,
    )
    parser.add_argument("-c", metavar="PATH", help="config file override", default=None)
    parser.add_argument(
        "--dry-run", action="store_true", default=False, help="preview without changes"
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        default=False,
        help="disable colored output (also: WARDEN_NO_COLOR=1)",
    )

    sub = _sub(parser, dest="command", help="available commands")

    # ── warden id ─────────────────────────────────────────────
    p_id = sub.add_parser("id", help="git identity management")
    id_sub = _sub(p_id, dest="id_command", help="identity commands")

    p_switch = id_sub.add_parser(
        "switch",
        help="apply a git identity",
        description="Apply a git identity from your warden.jsonc config.",
    )
    p_switch.add_argument("target", help="target name from config")

    id_sub.add_parser(
        "list",
        help="list available targets",
        description="List all targets defined in your warden.jsonc config.",
    )

    p_show = id_sub.add_parser(
        "show",
        help="show current or specific target config",
        description="Show the current git identity or a specific target's config.",
    )
    p_show.add_argument("target", nargs="?", help="target name (omit for current)")

    # ── warden pkg ────────────────────────────────────────────
    p_pkg = sub.add_parser("pkg", help="system package management")
    pkg_sub = _sub(p_pkg, dest="pkg_command", help="package commands")

    pkg_sub.add_parser(
        "scan",
        help="scan system and update packages/tools in config",
        description="Scan installed system packages and developer tools, "
        "then update the packages and tools sections in warden.jsonc.",
    )

    p_apply = pkg_sub.add_parser(
        "apply",
        help="install packages/tools from config",
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

    # install (custom help — both --help and no-args show cmd_install_list)
    p_install = pkg_sub.add_parser(
        "install",
        add_help=False,
        help="install packages via any manager",
    )
    p_install.add_argument("packages", nargs="*", metavar="MANAGER:PKG")
    p_install.add_argument("-h", "--help", action="store_true", default=False)
    p_install.add_argument("--save", action="store_true", default=False)
    p_install.add_argument("--any", action="store_true", default=False)

    # ── warden backup ─────────────────────────────────────────
    p_backup = sub.add_parser(
        "backup",
        help="backup git identities, SSH config, or both",
        description="Backup git identities, SSH config, or both into a tar.gz archive.",
    )
    backup_sub = _sub(p_backup, dest="backup_command", help="what to backup")

    p_bg = backup_sub.add_parser(
        "git",
        help="backup identities and signing keys",
        description="Backup identities and signing keys. System packages are excluded.",
    )
    p_bg.add_argument("-o", "--output", metavar="FILE", help="output archive path")

    p_bs = backup_sub.add_parser(
        "ssh",
        help="backup ~/.ssh/config and identity keys",
        description="Backup SSH config and all referenced identity key files.",
    )
    p_bs.add_argument("-o", "--output", metavar="FILE", help="output archive path")
    p_bs.add_argument(
        "--include-missing",
        action="store_true",
        default=False,
        help="include hosts whose key files are missing",
    )

    p_ba = backup_sub.add_parser(
        "all",
        help="backup everything (git + SSH + packages + tools)",
        description="Backup identities, SSH config, system packages, and tools.",
    )
    p_ba.add_argument("-o", "--output", metavar="FILE", help="output archive path")
    p_ba.add_argument(
        "--include-missing",
        action="store_true",
        default=False,
        help="include SSH hosts whose key files are missing",
    )
    p_ba.add_argument(
        "-s",
        "--scan",
        action="store_true",
        default=False,
        help="re-scan system packages before backup (updates config)",
    )

    # ── warden restore ────────────────────────────────────────
    p_restore = sub.add_parser(
        "restore",
        help="restore from backup archive",
        description="Restore git identities, SSH config, or both from a backup archive.",
    )
    restore_sub = _sub(p_restore, dest="restore_command", help="what to restore")

    p_rg = restore_sub.add_parser(
        "git",
        help="restore git identities",
        description="Restore identities and signing keys to ~/.warden/. "
        "Merges with existing config (preserving packages/tools).",
    )
    p_rg.add_argument("archive", help="path to backup .tar.gz archive")

    p_rs = restore_sub.add_parser(
        "ssh",
        help="restore SSH config",
        description="Restore SSH config (merged) and identity keys.",
    )
    p_rs.add_argument("archive", help="path to backup .tar.gz archive")

    p_ra = restore_sub.add_parser(
        "all",
        help="restore everything",
        description="Restore identities, SSH config, packages, and tools. "
        "Merges with existing config.",
    )
    p_ra.add_argument("archive", help="path to backup .tar.gz archive")

    # ── warden update ─────────────────────────────────────────
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

    return parser


# ---------------------------------------------------------------------------
# Rich main help
# ---------------------------------------------------------------------------


def _print_main_help() -> None:
    from warden.display import _console

    _console.print()
    _console.print("[bold]warden[/bold] — Describe the system you live in")
    _console.print()
    _console.print("[bold]Usage:[/bold]")
    _console.print("  warden [dim]<command> [subcommand] [options][/dim]")
    _console.print()
    _console.print("[bold]Identity[/bold] [dim](warden id)[/dim][bold]:[/bold]")
    _console.print(
        "  [cyan]id switch[/cyan]  [dim]<target>[/dim]     Apply a git identity"
    )
    _console.print("  [cyan]id list[/cyan]                 List available targets")
    _console.print(
        "  [cyan]id show[/cyan]    [dim][target][/dim]     Show current or specific config"
    )
    _console.print()
    _console.print("[bold]Packages[/bold] [dim](warden pkg)[/dim][bold]:[/bold]")
    _console.print("  [cyan]pkg scan[/cyan]                Scan system, update config")
    _console.print(
        "  [cyan]pkg apply[/cyan]   [dim][-f][/dim]        Install packages from config"
    )
    _console.print(
        "  [cyan]pkg install[/cyan] [dim]MGR:PKG[/dim]    Install via any manager"
    )
    _console.print()
    _console.print("[bold]Backup:[/bold]")
    _console.print(
        "  [cyan]backup[/cyan]  [dim]<git|ssh|all>[/dim]    Backup identities, SSH, or both"
    )
    _console.print(
        "  [cyan]restore[/cyan] [dim]<git|ssh|all>[/dim]    Restore from archive"
    )
    _console.print()
    _console.print("[bold]System:[/bold]")
    _console.print(
        "  [cyan]update[/cyan]  [dim][branch][/dim]        Self-update warden"
    )
    _console.print()
    _console.print("[bold]Global flags:[/bold]")
    _console.print("  [dim]-c PATH[/dim]        Config file override")
    _console.print("  [dim]--dry-run[/dim]      Preview without making changes")
    _console.print("  [dim]--no-color[/dim]     Disable colored output")
    _console.print()
    _console.print("[dim]Run[/dim] warden <command> --help [dim]for details.[/dim]")
    _console.print()


# ---------------------------------------------------------------------------
# Main dispatch
# ---------------------------------------------------------------------------


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        _print_main_help()
        sys.exit(0)

    dry = args.dry_run
    cn = detect_use_cn()

    match args.command:
        # ── id ────────────────────────────────────────────
        case "id":
            if not getattr(args, "id_command", None):
                parser.parse_args(["id", "--help"])
                return
            match args.id_command:
                case "switch":
                    config = load_config(args.c)
                    cmd_switch(config, args.target, dry_run=dry)
                case "list":
                    config = load_config(args.c)
                    cmd_list(config)
                case "show":
                    config = load_config(args.c)
                    cmd_show(config, getattr(args, "target", None))

        # ── pkg ───────────────────────────────────────────
        case "pkg":
            if not getattr(args, "pkg_command", None):
                parser.parse_args(["pkg", "--help"])
                return
            match args.pkg_command:
                case "scan":
                    config_path = resolve_config_path(args.c)
                    if config_path is None:
                        config_path = Path.home() / ".warden" / "warden.jsonc"
                        config_path.parent.mkdir(parents=True, exist_ok=True)
                        config_path.write_text("{}\n", encoding="utf-8")
                    config = load_config(args.c or str(config_path))
                    cmd_scan(config, config_path, dry_run=dry)
                case "apply":
                    config = load_config(args.c)
                    cmd_apply(config, force=args.force, dry_run=dry, use_cn=cn)
                case "install":
                    if not args.packages or args.help:
                        cmd_install_list()
                    else:
                        config_path = resolve_config_path(args.c)
                        cmd_install(
                            args.packages,
                            config_path=config_path,
                            save=args.save,
                            allow_any=args.any,
                            dry_run=dry,
                            use_cn=cn,
                        )

        # ── backup ────────────────────────────────────────
        case "backup":
            if not getattr(args, "backup_command", None):
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
                    config_path = resolve_config_path(args.c)
                    config = load_config(args.c)
                    if args.scan:
                        from warden.platform_info import detect_platform
                        from warden.scanner import scan_system

                        display.info("Re-scanning system packages...")
                        scanned = scan_system(detect_platform())
                        from warden.config import serialize_config, update_packages

                        config = update_packages(
                            config, scanned["packages"], scanned["tools"]
                        )
                        if not dry:
                            config_path.write_text(
                                serialize_config(config), encoding="utf-8"
                            )
                            display.success(f"Config updated: {config_path}")
                    backup_all(
                        config_path,
                        config,
                        args.output,
                        args.include_missing,
                        dry_run=dry,
                    )

        # ── restore ───────────────────────────────────────
        case "restore":
            if not getattr(args, "restore_command", None):
                parser.parse_args(["restore", "--help"])
                return
            match args.restore_command:
                case "git":
                    restore_git(Path(args.archive), dry_run=dry)
                case "ssh":
                    restore_ssh(Path(args.archive), dry_run=dry)
                case "all":
                    restore_all(Path(args.archive), dry_run=dry)

        # ── update ────────────────────────────────────────
        case "update":
            cmd_update(branch=args.branch, dry_run=dry, use_cn=cn)


if __name__ == "__main__":
    main()
