<h1 align="center">Warden</h1>

<p align="center">
  <strong>Describe the system you live in</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.13+-3776AB?logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/version-0.1.0-blue" alt="Version" />
  <img src="https://img.shields.io/badge/license-LGPL--3.0-green" alt="License" />
  <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Linux-lightgrey" alt="Platform" />
</p>

---

## Overview

Warden captures everything about your development environment — Git identities, SSH configs, system packages, and developer tools — into a single config file. Switch identities with one command, snapshot your installed software, apply configs to a fresh machine, and back everything up into portable archives.

- **Switch** git identity (name, email, signing key, SSH command) in one step
- **Scan** installed Homebrew formulae/casks, apt packages, and developer tools into config
- **Apply** config to a new machine — installs only what's missing
- **Backup** git identities, SSH config, or everything into a portable `.tar.gz`
- **Restore** from archive with smart config merging
- **Update** warden itself with `warden update`

---

## Quick Start

```bash
git clone git@github.com:LBYPatrick/warden.git ~/code/warden
cd ~/code/warden
make install
```

```bash
warden scan                              # snapshot system packages into config
warden switch personal                   # apply a git identity
warden apply                             # install missing packages from config
warden backup all -o ~/backup.tar.gz     # backup everything
warden restore all ~/backup.tar.gz       # restore on a new machine
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

1. `~/.warden/warden.jsonc`
2. `~/.ssh/warden.jsonc`
3. `~/warden.jsonc`
4. `./warden.jsonc`

Or pass `-c <path>` to use an explicit file.

```jsonc
{
  // Git identity profiles
  "identities": {
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
  },
  // Populated by `warden scan`
  "packages": {
    "brew": {
      "formulae": ["git", "ripgrep", "fd"],
      "casks": ["firefox", "visual-studio-code"]
    },
    "apt": {
      "packages": ["build-essential", "curl"]
    }
  },
  // Developer tools detected on the system
  "tools": ["rustup", "node", "pnpm"]
}
```

The legacy flat format (identity targets at top level) is still supported for reads.

### Identity Config

Each identity auto-configures:

| Config Field | Git Config | Behavior |
|---|---|---|
| `name` | `user.name` | Set directly |
| `email` | `user.email` | Set directly |
| `signing_key` | `user.signingkey` | Expanded path |
| *(derived)* | `core.sshCommand` | `ssh -o IdentitiesOnly=yes -i <key>` for non-default keys; unset for `~/.ssh/id_ed25519` |
| *(auto)* | `gpg.format` | Always `ssh` |
| *(auto)* | `commit.gpgsign` | Always `true` |

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

### System Packages

```bash
warden scan                  # scan system → update packages/tools in config
warden apply                 # install missing packages/tools from config
warden apply --force         # reinstall everything regardless of current state
```

`scan` replaces the packages and tools sections with freshly detected data, preserving identities.

`apply` compares config against what's already installed and only installs the difference. Supported:

| Source | What's Installed |
|---|---|
| `packages.brew.formulae` | Homebrew formulae |
| `packages.brew.casks` | Homebrew casks |
| `packages.apt.packages` | apt packages (Linux) |
| `tools` | Developer tools (rustup, node, pnpm, conda, flutter, gcloud, aws, wrangler, etc.) |

### Backup

```bash
warden backup git            # backup identities + signing keys
warden backup ssh            # backup ~/.ssh/config + identity keys
warden backup all            # backup everything (identities + SSH + packages + tools)
```

| Flag | Description |
|---|---|
| `-o FILE` | Custom output path (default: `warden-{type}-backup-{date}.tar.gz`) |
| `--include-missing` | Include SSH hosts whose key files are missing from disk |
| `--dry-run` | Preview without creating the archive |

**Scoping:** `backup git` and `backup ssh` exclude the packages/tools sections — only `backup all` includes the full config.

### Restore

```bash
warden restore git <archive>   # restore identities to ~/.warden/
warden restore ssh <archive>   # merge into ~/.ssh/config
warden restore all <archive>   # restore everything
```

**Merge algorithm** on restore:

| Section | Strategy |
|---|---|
| `identities` | Incoming overrides existing by name; new names added |
| `packages.brew.formulae` | Sorted union (deduplicated) |
| `packages.brew.casks` | Sorted union (deduplicated) |
| `packages.apt.packages` | Sorted union (deduplicated) |
| `tools` | Sorted union (deduplicated) |
| SSH config | Update existing Host blocks by name; append new |

SSH restore saves `~/.ssh/config.bak` before merging. Keys get `chmod 600` (private) / `644` (public).

### Self-Update

```bash
warden update                # pull latest + reinstall
warden update main           # pull from a specific branch
```

### Global Flags

| Flag | Description |
|---|---|
| `-c PATH` | Override config file path |
| `--dry-run` | Preview changes without writing to disk |

---

## Project Structure

```
warden/
  __main__.py       # argparse entry point — all subcommand definitions
  cli.py            # switch, list, show, scan, apply, update commands
  config.py         # json5 config parsing, resolution, merge algorithm
  display.py        # rich-powered terminal output (TTY-aware)
  backup.py         # backup/restore + archive marker logic
  ssh_config.py     # SSH config parser, serializer, merge engine
  scanner.py        # system package/tool scanning (brew, apt, dev tools)
  installer.py      # package/tool installation with skip-if-present logic
  platform_info.py  # OS/arch detection (macOS/Linux, amd64/arm64)
bin/warden          # bash wrapper (symlink-friendly)
completions/        # bash + zsh tab-completion
tests/              # pytest suite
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

Warden searches `~/.warden/warden.jsonc`, `~/.ssh/warden.jsonc`, `~/warden.jsonc`, then `./warden.jsonc`. Use `-c <path>` to point to a specific file. Running `warden scan` creates a new config at `~/.warden/warden.jsonc` if none exists.
</details>

<details>
<summary>Archive type mismatch on restore</summary>

Each archive contains a `.warden-marker` file identifying its type (`git`, `ssh`, or `all`). Use `warden restore all` for combined archives, or the specific type for single-purpose ones.
</details>

<details>
<summary>Legacy config format</summary>

If your `warden.jsonc` uses the old flat format (identities at root level), it still works for all identity commands. Run `warden scan` to migrate to the new unified format with packages and tools sections.
</details>

---

## License

[LGPL-3.0-or-later](LICENSE)
