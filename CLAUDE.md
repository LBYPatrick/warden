# Warden

Config-driven Git identity switcher with backup/restore for git identities and SSH configs.

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
  __main__.py     # argparse entry point — all subcommand definitions
  cli.py          # switch, list, show command implementations
  config.py       # JSONC parsing, config resolution, path helpers
  display.py      # Sheriff-style ANSI output (TTY-aware)
  backup.py       # backup/restore logic for git identities and SSH config
  ssh_config.py   # SSH config parser, serializer, and merge engine
bin/warden        # Bash wrapper → uv run python -m warden
completions/      # Bash and Zsh tab-completion scripts
scripts/          # install.sh, uninstall.sh, install-formatter.sh
```

## Key Design Decisions

- **Zero runtime dependencies** — stdlib only. JSONC parsed by stripping comments before `json.loads()`.
- **Cross-platform** — all paths use `Path.home()`, never hardcoded `/Users/` or `/home/`.
- **ANSI output** — raw escape codes, auto-stripped when stdout is not a TTY.
- **Config search order** — `-c` flag > `~/.ssh/warden.jsonc` > `~/warden.jsonc` > `./warden.jsonc`.
- **Backup archives** — tar.gz with hashed key filenames (6-digit SHA256 of absolute path). Config paths rewritten to `~/.warden/keys/`.
- **SSH config merge** — parse into Host blocks, update existing in-place by name, append new at end.

## Code Conventions

- Python 3.13+, formatted with ruff, shell scripts with beautysh
- All user-facing output goes through `display.py` functions (success, error, warn, info, item, skip, header, kv)
- Errors: `display.error()` + `sys.exit(1)` — no exceptions for user-facing failures
- Config loading always goes through `config.load_config()` which handles JSONC and error reporting
- `find_target()` does case-insensitive lookup, returns `(canonical_name, config_dict)`

## Testing

No test framework yet — `make test` runs a smoke test (`warden --help`). To manually verify:

```bash
warden list                                    # requires ~/.ssh/warden.jsonc
warden backup git -o /tmp/test.tar.gz          # creates archive
warden restore git /tmp/test.tar.gz            # restores to ~/.warden/
warden backup ssh -o /tmp/ssh.tar.gz           # backs up SSH config
warden restore ssh /tmp/ssh.tar.gz             # merges into ~/.ssh/config
```
