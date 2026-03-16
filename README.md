# Warden

Config-driven Git identity switcher with backup/restore. Manage multiple Git identities and SSH configs from JSONC config files, back them up with keys into portable archives, and restore them on any machine.

## Install

```bash
make install
```

This installs Python dependencies via [uv](https://github.com/astral-sh/uv), symlinks `warden` to `/usr/local/bin`, and sets up shell completions (bash/zsh).

### Uninstall

```bash
make uninstall
```

## Config

Create `warden.jsonc` at one of these locations (first found wins):

1. `~/.ssh/warden.jsonc`
2. `~/warden.jsonc`
3. `./warden.jsonc` (current directory)

Or pass an explicit path with `-c <path>`.

### Format

```jsonc
{
  // Git identity profiles
  "personal": {
    "name": "Your Name",
    "email": "you@example.com",
    "signing_key": "~/.ssh/id_ed25519.pub"
  },
  "work": {
    "name": "Work Name",
    "email": "you@company.com",
    "signing_key": "~/.ssh/id_ed25519_work.pub"
  }
}
```

Each target maps to these git config values:

| Field | Git Config | Notes |
|---|---|---|
| `name` | `user.name` | |
| `email` | `user.email` | |
| `signing_key` | `user.signingkey` | Path to `.pub` file |
| *(derived)* | `core.sshCommand` | Auto-derived from `signing_key` — strips `.pub` for private key path. Default key (`~/.ssh/id_ed25519`) leaves `core.sshCommand` unset; non-default keys set `ssh -o IdentitiesOnly=yes -i <private_key>` |

Switching also enables SSH commit signing (`gpg.format=ssh`, `commit.gpgsign=true`).

## Usage

### Identity switching

```bash
# Switch to a git identity
warden switch personal

# List all available targets
warden list

# Show current git identity
warden show

# Show a specific target's config
warden show work

# Use explicit config file
warden -c /path/to/config.jsonc list
```

Target names are case-insensitive.

### Backup

```bash
# Backup git identities (warden.jsonc + signing keys)
warden backup git
warden backup git -o ~/backups/git-keys.tar.gz

# Backup SSH config (~/.ssh/config + identity keys)
warden backup ssh
warden backup ssh -o ~/backups/ssh-keys.tar.gz

# Include hosts whose keys are missing from disk
warden backup ssh --include-missing
```

Archives contain the config file (with paths rewritten to `~/.warden/keys/`) and all key files renamed with 6-digit hashes to avoid collisions.

### Restore

```bash
# Restore git identities to ~/.warden/
warden restore git ~/backups/git-keys.tar.gz

# Restore SSH config (merges into ~/.ssh/config) + keys to ~/.warden/keys/
warden restore ssh ~/backups/ssh-keys.tar.gz
```

**Git restore** places config at `~/.warden/warden.jsonc` and keys at `~/.warden/keys/`.

**SSH restore** merges the backed-up SSH config into your existing `~/.ssh/config` (updates existing hosts in-place, appends new ones). A backup of your current config is saved to `~/.ssh/config.bak`. Keys go to `~/.warden/keys/`.

## Shell Completions

Completions for bash and zsh are installed automatically by `make install`. If you need to set them up manually:

**Zsh** — add to `~/.zshrc`:
```bash
fpath=(~/.zsh/completions $fpath)
autoload -Uz compinit && compinit
```

**Bash** — completions are installed to `~/.local/share/bash-completion/completions/warden`.

## Development

```bash
make help          # Show all targets
make format        # Run ruff + beautysh
make build         # Verify the project runs
make clean         # Remove caches and .venv
```

### Requirements

- Python 3.13+
- [uv](https://github.com/astral-sh/uv)

## License

[LGPL-3.0-or-later](LICENSE)
