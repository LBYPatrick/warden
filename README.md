<h1 align="center">Warden</h1>

<p align="center">
  <strong>Describe the system you live in</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.13+-3776AB?logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/version-1.0.0-blue" alt="Version" />
  <img src="https://img.shields.io/badge/license-LGPL--3.0-green" alt="License" />
  <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Linux-lightgrey" alt="Platform" />
</p>

---

## Overview

Warden captures your development environment — git identities, SSH configs, system packages, and developer tools — into a single config file. Switch identities, snapshot installed software, apply configs to a fresh machine, and back everything up into portable archives.

- **Identity** — switch git identity (name, email, signing key) in one step
- **Packages** — scan, install, and apply across 14 package managers
- **Backup** — portable `.tar.gz` archives with smart merge on restore
- **China mirrors** — `WARDEN_USE_CN=1` routes all downloads through CN-accessible mirrors

---

## Quick Start

```bash
git clone git@github.com:LBYPatrick/warden.git ~/code/warden
cd ~/code/warden
make install
```

```bash
warden pkg scan                          # snapshot system packages into config
warden id switch personal                # apply a git identity
warden pkg apply                         # install missing packages from config
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
  "identities": {
    "personal": {
      "name": "Your Name",
      "email": "you@example.com",
      "signing_key": "~/.ssh/id_ed25519.pub",
    },
  },
  // Populated by `warden pkg scan`
  "packages": {
    "brew": { "formulae": ["git", "ripgrep"], "casks": ["firefox"] },
    "cargo": { "packages": ["bat", "fd-find"] },
    "npm": { "packages": ["typescript"] },
  },
  "tools": ["rustup", "node", "pnpm"]
}
```

Legacy flat format (identities at root level) is still supported for reads.

---

## Usage

### Identity (`warden id`)

```bash
warden id switch <target>    # apply git identity (case-insensitive)
warden id list               # list all targets
warden id show               # show current git identity
warden id show <target>      # show a specific target
```

Each switch auto-configures `user.name`, `user.email`, `user.signingkey`, `core.sshCommand`, `gpg.format=ssh`, and `commit.gpgsign=true`.

### Packages (`warden pkg`)

```bash
warden pkg scan              # scan system → update packages/tools in config
warden pkg apply             # install missing packages from config
warden pkg apply --force     # reinstall everything
warden pkg install MGR:PKG   # install via any manager
```

`pkg install` uses `manager:package` syntax and shows available managers when run with no args:

```bash
warden pkg install brew:ripgrep cask:firefox cargo:bat npm:typescript
warden pkg install --save brew:fd     # also adds to warden.jsonc
warden pkg install --any apt:curl     # bypass OS platform check
```

**Supported package managers:**

| Manager | Platform | Config key |
|---|---|---|
| `brew` | macOS, Linux | `packages.brew.formulae` |
| `cask` | macOS, Linux | `packages.brew.casks` |
| `mas` | macOS | `packages.mas.apps` |
| `apt` | Linux | `packages.apt.packages` |
| `dnf` | Linux | `packages.dnf.packages` |
| `pacman` | Linux | `packages.pacman.packages` |
| `apk` | Linux | `packages.apk.packages` |
| `snap` | Linux | `packages.snap.packages` |
| `flatpak` | Linux | `packages.flatpak.packages` |
| `cargo` | both | `packages.cargo.packages` |
| `npm` | both | `packages.npm.packages` |
| `pnpm` | both | `packages.pnpm.packages` |
| `pipx` | both | `packages.pipx.packages` |
| `tool` | both | `tools` (dev tool slugs) |

### Backup & Restore

```bash
warden backup git              # identities + signing keys
warden backup ssh              # ~/.ssh/config + identity keys
warden backup all              # everything (git + SSH + packages + tools)
warden backup all -s           # re-scan packages before archiving
```

```bash
warden restore git <archive>   # restore to ~/.warden/ (merges config)
warden restore ssh <archive>   # merge into ~/.ssh/config
warden restore all <archive>   # restore everything
```

`backup git` and `backup ssh` exclude packages. Only `backup all` includes the full config. Use `--scan`/`-s` to refresh packages before archiving — without it, the curated list is preserved as-is.

**Merge on restore:** identities override by name; package lists are union-merged (sorted, deduplicated); SSH hosts updated by name, new ones appended.

### Self-Update

```bash
warden update                  # pull latest + reinstall
warden update main             # pull from a specific branch
```

### Global Flags

| Flag | Description |
|---|---|
| `-c PATH` | Override config file path |
| `--dry-run` | Preview changes without writing to disk |
| `--no-color` | Disable colored output (also: `WARDEN_NO_COLOR=1`) |

### China Mirror Mode

Set `WARDEN_USE_CN=1` to route downloads through CN-accessible mirrors:

| What | Mirror |
|---|---|
| Homebrew | USTC (`mirrors.ustc.edu.cn`) |
| PyPI / uv | Aliyun (`mirrors.aliyun.com`) |
| Rust (rustup) | rsproxy.cn |
| Node / npm / pnpm | npmmirror.com |
| GitHub downloads | ghp.ci proxy |

---

## Project Structure

```
warden/
  __main__.py       # argparse CLI — subcommand definitions and dispatch
  cli.py            # command implementations (id, pkg, update)
  config.py         # JSON5 config loading, resolution, merge algorithm
  display.py        # rich-powered output (respects WARDEN_NO_COLOR)
  backup.py         # backup/restore + archive marker logic
  ssh_config.py     # SSH config parser, serializer, merge engine
  scanner.py        # multi-manager package scanning
  installer.py      # multi-manager package installation
  cn.py             # China mirror URL rewrites and env vars
  platform_info.py  # OS/arch detection
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

Warden searches `~/.warden/warden.jsonc`, `~/.ssh/warden.jsonc`, `~/warden.jsonc`, then `./warden.jsonc`. Use `-c <path>` to point to a specific file. Running `warden pkg scan` creates a new config at `~/.warden/warden.jsonc` if none exists.
</details>

<details>
<summary>Archive type mismatch on restore</summary>

Each archive contains a `.warden-marker` file identifying its type (`git`, `ssh`, or `all`). Use `warden restore all` for combined archives, or the specific type for single-purpose ones.
</details>

<details>
<summary>Legacy config format</summary>

If your `warden.jsonc` uses the old flat format (identities at root level), it still works for all identity commands. Run `warden pkg scan` to migrate to the new unified format.
</details>

---

## License

[LGPL-3.0-or-later](LICENSE)
