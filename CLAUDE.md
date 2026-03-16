# Warden

Config-driven system descriptor: Git identity switcher + system package tracker with backup/restore.

## Quick Reference

```bash
make install       # Install deps, symlink bin, set up completions
make format        # Run ruff + beautysh (or: bash tidy.sh)
make build         # Verify CLI runs
make test          # Run tests (falls back to smoke test)
make clean         # Remove .venv, caches, build artifacts
```

## Architecture

```
warden/
  __main__.py       # argparse entry point — all subcommand definitions
  cli.py            # switch, list, show, scan, apply, update implementations
  config.py         # JSONC parsing, config resolution, merge algorithm, path helpers
  display.py        # Sheriff-style ANSI output (TTY-aware, rich-powered)
  backup.py         # backup/restore logic for git identities and SSH config
  ssh_config.py     # SSH config parser, serializer, and merge engine
  scanner.py        # System package/tool scanning (brew, apt, dev tools)
  installer.py      # Package/tool installation (brew, apt, dev tool scripts)
  platform_info.py  # OS/arch detection (macOS/Linux, amd64/arm64)
bin/warden          # Bash wrapper → uv run python -m warden
completions/        # Bash and Zsh tab-completion scripts
scripts/            # install.sh, uninstall.sh, install-formatter.sh
```

## Config Format (warden.jsonc)

New unified format with three sections:

```jsonc
{
  "identities": {
    "personal": { "name": "...", "email": "...", "signing_key": "~/.ssh/id_ed25519.pub" }
  },
  "packages": {
    "brew": { "formulae": ["git"], "casks": ["firefox"] },
    "apt": { "packages": ["curl"] }
  },
  "tools": ["rustup", "node"]
}
```

Legacy format (flat identity dict) is auto-detected and still supported for reads.

## Key Design Decisions

- **Zero runtime dependencies** beyond json5 + rich. All scanning/installing via subprocess.
- **Cross-platform** — all paths use `Path.home()`, never hardcoded `/Users/` or `/home/`.
- **Config search order** — `-c` flag > `~/.warden/warden.jsonc` > `~/.ssh/warden.jsonc` > `~/warden.jsonc` > `./warden.jsonc`.
- **Backup scoping** — `backup git`/`backup ssh` exclude packages/tools. `backup all` includes everything.
- **Merge algorithm** — On restore: identities override by name; packages/tools lists are union-merged (sorted, deduped).
- **Skip redundancy** — `apply` skips already-installed packages unless `--force`.
- **SSH config merge** — parse into Host blocks, update existing in-place by name, append new at end.
- **Backup archives** — tar.gz with hashed key filenames (6-digit SHA256 of absolute path). Config paths rewritten to `~/.warden/keys/`.

## Code Conventions

- Python 3.13+, formatted with ruff, shell scripts with beautysh
- All user-facing output goes through `display.py` functions (success, error, warn, info, item, skip, header, kv, spinner)
- Errors: `display.error()` + `sys.exit(1)` — no exceptions for user-facing failures
- Config loading always goes through `config.load_config()` which handles JSONC and error reporting
- Identity lookups use `config.get_identities()` then `config.find_target()` (case-insensitive)
- System scanning is synchronous (subprocess.run, not async)

## Testing

```bash
make test    # runs pytest
```

Test files: `test_config.py`, `test_backup.py`, `test_ssh_config.py`, `test_display.py`, `test_scanner.py`
