# Warden

System descriptor and identity switcher — manages git identities, SSH configs, and system packages from a unified `warden.jsonc` config.

## Quick Reference

```bash
make install       # Install deps, symlink bin, set up completions
make format        # ruff + beautysh (or: bash tidy.sh)
make test          # pytest
make build         # Smoke test (warden --help)
make clean         # Remove .venv, caches, build artifacts
```

## Architecture

```
warden/
  __main__.py       # Argparse CLI — all subcommands defined here
  cli.py            # Command implementations (switch, list, show, scan, apply, install, update)
  config.py         # JSON5 config loading, resolution, merge algorithm
  display.py        # Rich-powered terminal output (respects WARDEN_NO_COLOR)
  backup.py         # Backup/restore for git identities and SSH config
  ssh_config.py     # SSH config parser, serializer, merge engine
  scanner.py        # Package manager scanning (brew, apt, dnf, cargo, npm, pnpm, pipx, etc.)
  installer.py      # Package installation with skip-if-present logic
  cn.py             # China mirror URL rewrites and env vars (WARDEN_USE_CN)
  platform_info.py  # OS/arch detection
bin/warden          # Bash wrapper → uv run python -m warden
completions/        # Bash + Zsh tab-completion scripts
scripts/            # install.sh, uninstall.sh, install-formatter.sh
tests/              # Pytest suite (conftest.py + test_*.py)
```

## Commit Messages

Conventional Commits format: `<type>(<scope>): <summary>`

| Type | When |
|---|---|
| `feat` | New user-facing functionality |
| `fix` | Bug fix |
| `refactor` | Code restructuring, no behavior change |
| `docs` | Documentation only |
| `test` | Adding/updating tests |
| `chore` | Tooling, config, release prep |

Scopes: `cli`, `config`, `backup`, `scanner`, `installer`, `cn`, `display`.

Example: `feat(scanner): add flatpak package scanning`

## Code Style

- Python 3.13+, formatted with ruff, shell scripts with beautysh
- Run `bash tidy.sh` or `make format` before committing
- All user-facing output goes through `display.py` (success, error, warn, info, item, skip, header, kv, spinner, banner)
- Errors: `display.error()` + `sys.exit(1)` — no exceptions for user-facing failures
- Config loading: always `config.load_config()` → use `get_identities()`, `get_packages()`, `get_tools()` helpers
- Identity lookups: `config.get_identities()` then `config.find_target()` (case-insensitive)
- System scanning is synchronous (`subprocess.run`, not async)
- Shell scripts: use `$'...'` ANSI color vars, respect `WARDEN_NO_COLOR`/`NO_COLOR` env

## Config Format

Search order: `~/.warden/warden.jsonc` > `~/.ssh/warden.jsonc` > `~/warden.jsonc` > `./warden.jsonc` > `-c <path>`.

Three top-level sections: `identities`, `packages`, `tools`. Legacy flat format (identities at root) auto-detected.

Merge algorithm (restore): identities override by name; all package lists union-merged (sorted, deduped); tools union-merged.

## Environment Flags

| Flag | Effect |
|---|---|
| `WARDEN_NO_COLOR=1` | Disable all colored output (Python + shell + Makefile) |
| `WARDEN_USE_CN=1` | Route downloads through China-accessible mirrors |

Both accept `1`, `true`, or `yes` (case-insensitive). `--no-color` CLI flag also works.

## Testing

```bash
make test                  # or: uv run python -m pytest tests/ -v
```

Tests live in `tests/`. Fixtures in `conftest.py` (fake_keys, fake_warden_config, fake_ssh_config, fake_legacy_config). Write tests for new/modified code — fix code, not tests.

## Pre-Commit Checklist

1. `bash tidy.sh` — format passes
2. `uv run ruff format --check .` — CI-identical check
3. `uv run python -m pytest tests/ -v` — all tests pass
4. `uv run python -m warden --help` — smoke test

## Versioning

Bump in **all three** locations:
1. `VERSION`
2. `pyproject.toml` → `version`
3. `README.md` → badge URL (`version-X.Y.Z-blue`)

## Changelog

`CHANGELOG.md` follows [Keep a Changelog](https://keepachangelog.com/). Categories: Added, Changed, Fixed, Removed. Imperative verbs. Update `[Unreleased]` on every user-visible commit. On release, rename to `[X.Y.Z] - YYYY-MM-DD`.

## Key Design Decisions

- No runtime deps beyond json5 + rich — scanning/installing via subprocess
- Cross-platform paths via `Path.home()`, never hardcoded
- `backup git`/`backup ssh` exclude packages; only `backup all` includes full config
- `--scan`/`-s` on `backup all` optionally refreshes packages before archiving
- `warden install` validates manager against current OS platform (unless `--any`)
- Argparse help colorized via `_ColorHelpFormatter` post-processing with ANSI regexes
