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
from warden.backup import backup, parse_modules, restore  # noqa: E402
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
from warden.mole import (  # noqa: E402
    cmd_mole_analyze,
    cmd_mole_clean,
    cmd_mole_optimize,
    cmd_mole_status,
    is_macos,
)

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


def _ensure_config(override: str | None) -> tuple[dict, Path]:
    """Load config if it exists, otherwise create an empty one at the default path.

    Returns (config_data, config_path).
    """
    config_path = resolve_config_path(override)
    if config_path is not None:
        return load_config(override), config_path

    config_path = Path.home() / ".warden" / "warden.jsonc"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{}\n", encoding="utf-8")
    display.info(f"Created empty config at {config_path}")
    return {}, config_path


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
        help="backup modules (git, ssh, pkg, or all)",
        description="Backup selected modules into a tar.gz archive.\n\n"
        "Defaults to all modules. Use -m to select specific ones.\n"
        "Modules: git (identities + keys), ssh (SSH config + keys), "
        "pkg (packages + tools). System packages are re-scanned by default\n"
        "when pkg is included; use --skip-scan to disable.",
    )
    p_backup.add_argument(
        "-m",
        metavar="MODULES",
        default="all",
        help="modules to backup: git,ssh,pkg (comma-separated) or 'all' (default: all)",
    )
    p_backup.add_argument("-o", "--output", metavar="FILE", help="output archive path")
    p_backup.add_argument(
        "--include-missing",
        action="store_true",
        default=False,
        help="include SSH hosts whose key files are missing",
    )
    p_backup.add_argument(
        "--skip-scan",
        action="store_true",
        default=False,
        help="skip re-scanning system packages before backup",
    )

    # ── warden restore ────────────────────────────────────────
    p_restore = sub.add_parser(
        "restore",
        help="restore modules from backup archive",
        description="Restore selected modules from a backup archive.\n\n"
        "Defaults to all modules. Use -m to select specific ones.\n"
        "Rejects if the archive does not contain a requested module.",
    )
    p_restore.add_argument(
        "-m",
        metavar="MODULES",
        default="all",
        help="modules to restore: git,ssh,pkg (comma-separated) or 'all' (default: all)",
    )
    p_restore.add_argument("archive", help="path to backup .tar.gz archive")

    # ── warden mole (macOS only) ─────────────────────────────
    if is_macos():
        p_mole = sub.add_parser(
            "mole",
            help="system cleanup and optimization (powered by tw93/mole)",
            description="System cleanup and optimization powered by Mole (tw93/mole). "
            "Auto-installs Mole via Homebrew if not found. "
            "For additional Mole features (uninstall, purge, installer, touchid), "
            "run `mo` directly.",
        )
        mole_sub = _sub(p_mole, dest="mole_command", help="mole commands")

        mole_sub.add_parser(
            "clean",
            help="deep system cleanup (caches, logs, temp files)",
            description="Run Mole deep system cleanup — removes app caches, "
            "browser caches, developer tool caches, system logs, and temp files.",
        )

        mole_sub.add_parser(
            "optimize",
            help="rebuild system databases and services",
            description="Run Mole system optimization — rebuilds system databases, "
            "resets network services, refreshes Finder/Dock, and cleans diagnostics.",
        )

        p_ma = mole_sub.add_parser(
            "analyze",
            help="visual disk space explorer",
            description="Run Mole disk space analyzer with interactive navigation. "
            "Optionally pass a path to analyze a specific directory.",
        )
        p_ma.add_argument(
            "path", nargs="?", default=None, help="directory to analyze (default: /)"
        )

        p_ms = mole_sub.add_parser(
            "status",
            help="real-time system health dashboard",
            description="Run Mole system status dashboard — CPU, memory, disk, "
            "power, network, and overall health score.",
        )
        p_ms.add_argument(
            "--json",
            action="store_true",
            default=False,
            help="output in JSON format",
        )

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
        "  [cyan]backup[/cyan]  [dim][-m git,ssh,pkg][/dim]  Backup modules (default: all)"
    )
    _console.print(
        "  [cyan]restore[/cyan] [dim][-m git,pkg][/dim] [dim]<archive>[/dim] Restore from archive"
    )
    _console.print()
    if is_macos():
        _console.print(
            "[bold]Maintenance[/bold] [dim](warden mole — powered by tw93/mole)[/dim][bold]:[/bold]"
        )
        _console.print("  [cyan]mole clean[/cyan]              Deep system cleanup")
        _console.print(
            "  [cyan]mole optimize[/cyan]           Rebuild system databases"
        )
        _console.print(
            "  [cyan]mole analyze[/cyan] [dim][path][/dim]    Disk space explorer"
        )
        _console.print("  [cyan]mole status[/cyan]             System health dashboard")
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
                    config, _ = _ensure_config(args.c)
                    cmd_switch(config, args.target, dry_run=dry)
                case "list":
                    config, _ = _ensure_config(args.c)
                    cmd_list(config)
                case "show":
                    config, _ = _ensure_config(args.c)
                    cmd_show(config, getattr(args, "target", None))

        # ── pkg ───────────────────────────────────────────
        case "pkg":
            if not getattr(args, "pkg_command", None):
                parser.parse_args(["pkg", "--help"])
                return
            match args.pkg_command:
                case "scan":
                    config, config_path = _ensure_config(args.c)
                    cmd_scan(config, config_path, dry_run=dry)
                case "apply":
                    config, _ = _ensure_config(args.c)
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
            modules = parse_modules(args.m)
            config, config_path = _ensure_config(args.c)
            if not args.skip_scan and "pkg" in modules:
                from warden.platform_info import detect_platform
                from warden.scanner import scan_system

                display.info("Re-scanning system packages...")
                scanned = scan_system(detect_platform())
                from warden.config import serialize_config, update_packages

                config = update_packages(config, scanned["packages"], scanned["tools"])
                if not dry:
                    config_path.write_text(serialize_config(config), encoding="utf-8")
                    display.success(f"Config updated: {config_path}")
            backup(
                modules,
                config,
                args.output,
                args.include_missing,
                dry_run=dry,
            )

        # ── restore ───────────────────────────────────────
        case "restore":
            modules = parse_modules(args.m)
            restore(modules, Path(args.archive), dry_run=dry)

        # ── mole ─────────────────────────────────────────
        case "mole":
            if not getattr(args, "mole_command", None):
                parser.parse_args(["mole", "--help"])
                return
            match args.mole_command:
                case "clean":
                    cmd_mole_clean(dry_run=dry)
                case "optimize":
                    cmd_mole_optimize(dry_run=dry)
                case "analyze":
                    cmd_mole_analyze(path=args.path)
                case "status":
                    cmd_mole_status(json_output=args.json)

        # ── update ────────────────────────────────────────
        case "update":
            cmd_update(branch=args.branch, dry_run=dry, use_cn=cn)


if __name__ == "__main__":
    main()
