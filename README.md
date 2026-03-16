<h1 align="center">Warden</h1>

<p align="center">
  <strong>Config-driven Git identity switcher with portable backup/restore</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.13+-3776AB?logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/version-0.1.0-blue" alt="Version" />
  <img src="https://img.shields.io/badge/license-LGPL--3.0-green" alt="License" />
  <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Linux-lightgrey" alt="Platform" />
</p>

---

## Overview

Warden manages multiple Git identities and SSH configurations from a single JSON5 config file. Switch between identities with one command, and back everything up — configs, signing keys, SSH keys — into portable archives that restore on any machine.

- **Switch** git identity (name, email, signing key, SSH command) in one step
- **Backup** git identities, SSH config, or both into a single `.tar.gz`
- **Restore** from archive with automatic SSH config merging
- **Cross-platform** — macOS and Linux via `Path.home()`

---

## Tech Stack

- **Python 3.13+** (managed via [uv](https://github.com/astral-sh/uv))
- **json5** — JSON5/JSONC config parsing (comments, trailing commas)
- **rich** — Terminal output with automatic color and TTY handling

---

## Quick Start

```bash
git clone git@github.com:LBYPatrick/warden.git ~/code/warden
cd ~/code/warden
make install
```

```bash
warden switch personal                   # apply a git identity
warden backup all -o ~/keys.tar.gz       # backup everything
warden restore all ~/keys.tar.gz         # restore on a new machine
```

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.13+ | Runtime |
| [uv](https://github.com/astral-sh/uv) | latest | Auto-installed by `make install` if missing |

---

## Config

Create `warden.jsonc` at one of these locations (first found wins):

1. `~/.ssh/warden.jsonc`
2. `~/warden.jsonc`
3. `./warden.jsonc`

Or pass `-c <path>` to use an explicit file.

```jsonc
{
  // Git identity profiles
  "personal": {
    "name": "Your Name",
    "email": "you@example.com",
    "signing_key": "~/.ssh/id_ed25519.pub",
  },
  "work": {
    "name": "Work Name",
    "email": "work@company.com",
    "signing_key": "~/.ssh/id_ed25519_work.pub",
  }
}
```

Each target auto-configures:

| Config Field | Git Config | Behavior |
|---|---|---|
| `name` | `user.name` | Set directly |
| `email` | `user.email` | Set directly |
| `signing_key` | `user.signingkey` | Expanded path |
| *(derived)* | `core.sshCommand` | `ssh -o IdentitiesOnly=yes -i <key>` for non-default keys; unset for `~/.ssh/id_ed25519` |
| *(auto)* | `gpg.format` | Set to `ssh` |
| *(auto)* | `commit.gpgsign` | Set to `true` |

---

## Usage

### Identity Management

```bash
warden switch <target>       # apply git identity
warden list                  # list all targets
warden show                  # show current git identity
warden show <target>         # show a specific target
```

Target names are case-insensitive.

### Backup

```bash
warden backup git            # backup warden.jsonc + signing keys
warden backup ssh            # backup ~/.ssh/config + identity keys
warden backup all            # backup everything in one archive
```

| Flag | Description |
|---|---|
| `-o FILE` | Custom output path (default: `warden-{type}-backup-{date}.tar.gz`) |
| `--include-missing` | Include SSH hosts whose key files are missing from disk |
| `--dry-run` | Show what would happen without creating the archive |

Archives contain a `.warden-marker` for type validation, the config (paths rewritten to `~/.warden/keys/`), and all key files renamed with 6-digit hashes to avoid collisions.

### Restore

```bash
warden restore git <archive>   # restore to ~/.warden/
warden restore ssh <archive>   # merge into ~/.ssh/config
warden restore all <archive>   # restore both
```

| Type | Config | Keys | SSH Merge |
|---|---|---|---|
| `git` | `~/.warden/warden.jsonc` | `~/.warden/keys/` | — |
| `ssh` | `~/.ssh/config` | `~/.warden/keys/` | Update existing, append new |
| `all` | Both | `~/.warden/keys/` | Update existing, append new |

SSH restore saves `~/.ssh/config.bak` before merging. Keys get `chmod 600` (private) / `644` (public).

### Global Flags

| Flag | Description |
|---|---|
| `-c PATH` | Override config file path |
| `--dry-run` | Preview changes without writing to disk |

---

## Project Structure

```
warden/
  __main__.py       # argparse entry point
  cli.py            # switch, list, show commands
  config.py         # json5 config parsing + resolution
  display.py        # rich-powered terminal output
  backup.py         # backup/restore + archive marker logic
  ssh_config.py     # SSH config parser, serializer, merge engine
bin/warden          # bash wrapper (symlink-friendly)
completions/        # bash + zsh tab-completion
tests/              # pytest suite (no sensitive data)
scripts/            # install, uninstall, formatter setup
```

---

## Development

| Command | Description |
|---|---|
| `make install` | Install deps, symlink binary, set up completions |
| `make uninstall` | Remove symlink and caches |
| `make test` | Run pytest suite |
| `make format` | Run ruff + beautysh |
| `make build` | Verify the CLI runs |
| `make clean` | Remove `.venv`, caches, build artifacts |

### Shell Completions

Installed automatically by `make install`. For manual setup:

<details>
<summary>Zsh</summary>

Add to `~/.zshrc`:
```bash
fpath=(~/.zsh/completions $fpath)
autoload -Uz compinit && compinit
```
</details>

<details>
<summary>Bash</summary>

Completions are installed to `~/.local/share/bash-completion/completions/warden`.
</details>

---

## Troubleshooting

<details>
<summary>warden: command not found</summary>

Run `make install` to symlink the binary to `/usr/local/bin/warden`. If `/usr/local/bin` is not on your `PATH`, add it or create a symlink manually.
</details>

<details>
<summary>Config not found</summary>

Warden searches `~/.ssh/warden.jsonc`, `~/warden.jsonc`, then `./warden.jsonc`. Use `-c <path>` to point to a specific file, or run `warden list` to confirm the config is found.
</details>

<details>
<summary>Archive type mismatch on restore</summary>

Each archive contains a `.warden-marker` file identifying its type (`git`, `ssh`, or `all`). Use `warden restore all` for combined archives, or the specific type for single-purpose ones.
</details>

---

## License

[LGPL-3.0-or-later](LICENSE)
