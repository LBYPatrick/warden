<h1 align="center">Warden</h1>

<p align="center">
  <strong>Describe the system you live in</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.13+-3776AB?logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/version-1.1.0-blue" alt="Version" />
  <img src="https://img.shields.io/badge/license-LGPL--3.0-green" alt="License" />
  <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Linux-lightgrey" alt="Platform" />
</p>

---

Warden captures your development environment — git identities, SSH configs, system packages, and developer tools — into a single JSON5 config file. Switch identities, snapshot installed software, apply configs to a fresh machine, back everything up into portable archives, and keep your system clean.

- **Identity** — switch git identity (name, email, signing key, SSH command) in one step
- **Packages** — scan, install, and apply across 14 package managers
- **Backup** — portable `.tar.gz` archives with module selection and smart merge on restore
- **Maintenance** — system cleanup and optimization via [Mole](https://github.com/tw93/mole) (macOS) — we love it
- **China mirrors** — `WARDEN_USE_CN=1` routes all downloads through CN-accessible mirrors

---

## Quick Start

**One-line install:**

```bash
curl -fsSL https://raw.githubusercontent.com/LBYPatrick/warden/main/scripts/remote-install.sh | bash
```

**Or clone manually:**

```bash
git clone https://github.com/LBYPatrick/warden.git ~/.warden/repo
cd ~/.warden/repo
make install
```

**Then:**

```bash
warden pkg scan                    # snapshot system packages into config
warden id switch personal          # apply a git identity
warden pkg apply                   # install missing packages from config
warden backup -o ~/backup.tar.gz   # backup everything
warden restore ~/backup.tar.gz     # restore on a new machine
```

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.13+ | Runtime |
| [uv](https://github.com/astral-sh/uv) | latest | Auto-installed by `make install` if missing |

---

## Config

Warden searches for `warden.jsonc` in this order (first found wins):

1. `~/.warden/warden.jsonc`
2. `~/.ssh/warden.jsonc`
3. `~/warden.jsonc`
4. `./warden.jsonc`

Or pass `-c <path>` for an explicit file.

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

Each switch configures `user.name`, `user.email`, `user.signingkey`, `core.sshCommand`, `gpg.format=ssh`, and `commit.gpgsign=true`.

### Packages (`warden pkg`)

```bash
warden pkg scan              # scan system → update packages/tools in config
warden pkg apply             # install missing packages from config
warden pkg apply --force     # reinstall everything
warden pkg install MGR:PKG   # install via any manager
```

`pkg install` uses `manager:package` syntax:

```bash
warden pkg install brew:ripgrep cask:firefox cargo:bat
warden pkg install --save brew:fd     # also adds to warden.jsonc
warden pkg install --any apt:curl     # bypass OS platform check
```

<details>
<summary><strong>Supported package managers (14)</strong></summary>

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

</details>

### Backup & Restore

Use `-m` to select which modules to backup or restore. Backup defaults to `all`. Restore auto-detects modules from the archive when `-m` is omitted.

| Module | What it includes |
|---|---|
| `git` | Identities + signing keys |
| `ssh` | `~/.ssh/config` + identity keys |
| `pkg` | Packages + tools from config + apt sources (Linux) |

```bash
warden backup                         # backup everything (scans packages first)
warden backup -m git                  # just identities + keys
warden backup -m git,ssh              # identities + SSH config
warden backup --skip-scan             # skip package re-scan
warden backup -o ~/bak.tar.gz         # custom output path
```

```bash
warden restore ~/backup.tar.gz        # auto-detect and restore available modules
warden restore -m git ~/backup.tar.gz # restore just identities
warden restore -m pkg ~/backup.tar.gz # restore just packages
warden restore -m all ~/backup.tar.gz # explicitly restore all modules
```

Restore auto-detects available modules from the archive marker when `-m` is not specified. Use `-m` to override. Merge on restore: identities override by name; package lists union-merged (sorted, deduplicated); SSH hosts updated by name, new ones appended. On Linux, apt sources are backed up and restored with the `pkg` module.

**Linux improvements:** APT scanning captures only user-installed packages (via `apt-mark showmanual`), not auto-installed dependencies. APT install filters packages through `apt-cache` to skip unavailable ones, then installs all available packages in a single `apt-get` call.

### Maintenance (`warden mole`) — macOS only

System cleanup and optimization powered by [Mole](https://github.com/tw93/mole) — we love it. Auto-installed via Homebrew if not already present.

```bash
warden mole clean              # deep system cleanup (caches, logs, temp files)
warden mole optimize           # rebuild system databases and services
warden mole analyze            # visual disk space explorer
warden mole analyze /Volumes   # analyze a specific path
warden mole status             # real-time system health dashboard
warden mole status --json      # machine-readable JSON output
```

For additional features, run `mo` directly:

```bash
mo                             # interactive menu
mo uninstall                   # smart app uninstaller
mo purge                       # clean build artifacts (node_modules, target, etc.)
mo installer                   # find and remove .dmg/.pkg/.zip installers
mo touchid                     # configure Touch ID for sudo
```

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

### Man Page

```bash
man warden
```

Installed automatically by `make install`.

### China Mirror Mode

Set `WARDEN_USE_CN=1` to route downloads through CN-accessible mirrors:

| What | Mirror |
|---|---|
| Homebrew | USTC (`mirrors.ustc.edu.cn`) |
| PyPI / uv | Aliyun (`mirrors.aliyun.com`) |
| Rust (rustup) | rsproxy.cn |
| Node / npm / pnpm | npmmirror.com |
| GitHub downloads | ghp.ci proxy |

Works with remote install too:

```bash
WARDEN_USE_CN=1 curl -fsSL https://raw.githubusercontent.com/LBYPatrick/warden/main/scripts/remote-install.sh | bash
```

---

## Project Structure

```
warden/
  __main__.py       # argparse CLI — subcommand definitions and dispatch
  cli.py            # command implementations (id, pkg, update)
  config.py         # JSON5 config loading, resolution, merge algorithm
  display.py        # rich-powered output (respects WARDEN_NO_COLOR)
  backup.py         # backup/restore + archive marker logic
  mole.py           # Mole integration (system cleanup, macOS only)
  ssh_config.py     # SSH config parser, serializer, merge engine
  scanner.py        # multi-manager package scanning
  installer.py      # multi-manager package installation
  cn.py             # China mirror URL rewrites and env vars
  platform_info.py  # OS/arch detection
bin/warden          # bash wrapper (symlink-friendly)
man/                # man page (warden.1)
completions/        # bash + zsh tab-completion
tests/              # pytest suite
scripts/            # install, uninstall, remote-install, formatter setup
```

---

## Development

| Command | Description |
|---|---|
| `make install` | Install deps, symlink binary, man page, completions |
| `make uninstall` | Remove symlink, caches, man page, completions |
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
<summary>Module not found in archive on restore</summary>

Each archive records which modules it contains. Use `warden backup` (defaults to all) to create a full archive. To restore specific modules, pass `-m git,pkg` etc. — the error message shows which modules are available in the archive.
</details>

<details>
<summary>Legacy config format</summary>

If your `warden.jsonc` uses the old flat format (identities at root level), it still works for all identity commands. Run `warden pkg scan` to migrate to the new unified format.
</details>

---

## License

[LGPL-3.0-or-later](LICENSE)
