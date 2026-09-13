<h1 align="center">Warden</h1>
<p align="center"><strong>Describe the system you live in</strong></p>
<p align="center">
  <img src="https://img.shields.io/badge/Go-1.25+-00ADD8?logo=go&logoColor=white" alt="Go" />
  <img src="https://img.shields.io/badge/version-1.1.0-blue" alt="Version" />
  <img src="https://img.shields.io/badge/license-LGPL--3.0-green" alt="License" />
  <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Linux-lightgrey" alt="Platform" />
</p>

Warden captures Git identities, SSH configuration, packages, and developer tools in a portable JSON5 file. A native Go executable provides both a CLI and an interactive dashboard, with the dark surfaces, blue accents, section navigation, and detail panes used by [Ashley](https://github.com/LBYPatrick/ashley).

## Install

Install a published binary release:

```bash
curl -fsSL https://raw.githubusercontent.com/LBYPatrick/warden/main/scripts/remote-install.sh | bash
```

Pin a specific published version:

```bash
curl -fsSL https://raw.githubusercontent.com/LBYPatrick/warden/main/scripts/remote-install.sh \
  | bash -s -- --version X.Y.Z
```

Replace `X.Y.Z` with a release containing the Go binary assets. The installer supports macOS and Linux on ARM64 and x86-64, verifies SHA-256 and the executable's version, and atomically installs to `~/.local/bin/warden`. It also installs the man page and Bash/Zsh completions. Target computers need Bash, curl, tar, and a SHA-256 utility; they do not need Go, Python, uv, a checkout, or a virtual environment.

Use `--install-dir DIR`, `WARDEN_INSTALL_DIR`, or `WARDEN_VERSION` to customize installation. Ensure `~/.local/bin` is on `PATH`.

**Migration from Python:** existing configs and archives remain readable. Install the binary, then use `command -v warden` to check which launcher your shell resolves. If an older `/usr/local/bin/warden` symlink takes precedence, remove that old symlink or put `~/.local/bin` first in `PATH`. Your old checkout/virtual environment is no longer required. Keep `~/.warden/warden.jsonc` and `~/.warden/keys`.

The Go changes are unreleased until a new version tag publishes the binary assets. For a checkout containing these changes, use `make install` to build and install locally.

## Quick start

```bash
warden                              # interactive dashboard when attached to a terminal
warden tui                          # explicitly open the dashboard
warden id list
warden id switch personal
warden pkg scan
warden pkg apply --dry-run
warden backup -o ~/warden.tar.gz
warden restore ~/warden.tar.gz
```

With redirected input/output, bare `warden` prints help. `warden tui` requires an interactive terminal.

## Dashboard

The TUI has Overview, Identities, Packages, Archives, and Maintenance sections. Wide terminals show selection details beside the list; narrow terminals use a compact layout.

| Key | Action |
|---|---|
| `←` / `→`, Tab / Shift-Tab | Change section |
| `1`–`5` | Jump to a section |
| `↑` / `↓`, `j` / `k` | Move through entries |
| Enter | Open or review selected action |
| `/` | Filter entries |
| `r` | Reload configuration |
| `s` in Packages | Scan installed packages |
| `a` in Packages | Review and apply configuration |
| `b` | Review a full backup |
| Esc | Cancel, clear filter, or return from a result |
| `q` / Ctrl-C | Quit |

Identity switches, package application, restores, backups, updates, and maintenance actions have a review screen. Restore accepts an archive path, including spaces. Operations show their result or error in a scrollable panel. Start with `warden --dry-run` to preview actions.

## Configuration

Warden searches for `warden.jsonc` in this order:

1. `~/.warden/warden.jsonc`
2. `~/.ssh/warden.jsonc`
3. `~/warden.jsonc`
4. `./warden.jsonc`

`-c PATH` takes precedence, including when creating a new config. Paths are resolved from your current directory. Reading a missing config does not create files; scans and saves create it when needed. Malformed existing configs cause an error and are preserved.

```json5
{
  identities: {
    personal: {
      name: 'Your Name',
      email: 'you@example.com',
      signing_key: '~/.ssh/id_ed25519.pub',
    },
  },
  packages: {
    brew: {formulae: ['git', 'ripgrep'], casks: ['firefox']},
    cargo: {packages: ['bat']},
    npm: {packages: ['typescript']},
  },
  tools: ['rustup', 'node', 'pnpm'],
}
```

Comments, unquoted keys, single quotes, trailing commas, and legacy identity-only configs are supported. Writes use formatted JSON, which is valid JSON5; comments are not retained.

## Commands

### Identities

```bash
warden id list                     # aligned identity summary
warden id list --names             # one name per line, for completions/scripts
warden id list --json
warden id show                     # current global Git settings
warden id show personal --json
warden id switch personal          # case-insensitive lookup
```

Switching sets supplied name/email/signing-key fields, derives `core.sshCommand`, enables SSH signing, and sets `commit.gpgsign=true`. The default `~/.ssh/id_ed25519` unsets a custom SSH command. Key paths with spaces or shell metacharacters are quoted.

### Packages

```bash
warden pkg scan
warden pkg apply --force
warden pkg install brew:ripgrep cask:firefox cargo:bat
warden pkg install --save npm:typescript
warden pkg install --any apt:curl
warden pkg install                 # manager and developer-tool list
warden pkg deps -o dependencies.json
```

| Manager | Platform | Config section |
|---|---|---|
| brew / cask | macOS, Linux | `brew.formulae` / `brew.casks` |
| mas | macOS | `mas.apps` (`id:name`) |
| apt, dnf, pacman, apk, snap, flatpak | Linux | `<manager>.packages` |
| cargo, npm, pnpm, pipx | macOS, Linux | `<manager>.packages` |
| tool | macOS, Linux | top-level `tools` |

Developer tools: xcode (macOS), rustup, conda, node, pnpm, flutter, gcloud, aws, wrangler, android-tools. Tool installers may require additional system utilities or privileges.

Scans replace the package/tool snapshot while preserving identities, and stop on a scan failure rather than saving incomplete results. Install/apply skips already-present entries unless forced. `--save` records successful and already-present packages; failed installations return a nonzero exit status. Homebrew installs in bulk with live CLI output and retries individual packages on failure. APT scans manual packages, falls back to dpkg, refreshes its index, filters unavailable packages, and uses bulk installation with individual retries. macOS operations that need Homebrew bootstrap it when missing. `pkg deps` emits JSON without decorative output.

### Backup and restore

```bash
warden backup -m git,ssh -o ~/identities.tar.gz
warden backup --skip-scan
warden restore ~/identities.tar.gz
warden restore ~/full.tar.gz -m pkg
warden restore ~/full.tar.gz --dry-run
```

Modules are `git` (identities/signing keys), `ssh` (SSH config/keys), and `pkg` (packages/tools and Linux APT sources). Backup defaults to `all` and scans packages unless `--skip-scan` is supplied. Restore defaults to modules recorded in the archive. Only selected modules and their referenced keys are restored. Missing SSH config is backed up as an empty config. SSH hosts with missing key files are omitted by default; `--include-missing` retains those hosts and their original references with a notice.

Identities merge by name, package/tool lists by sorted union, and SSH Host/Match blocks by name. Existing SSH config is copied to `~/.ssh/config.bak`. The `-c` override also controls restore's destination config. Linux APT sources use their original `/etc/apt` paths and can require sudo.

**Key deduplication:** Git and SSH share a content-based key collector. Identical pairs under different names are archived once. Restore searches `~/.ssh`, `~/.warden/keys`, configured signing keys, and SSH identity paths, reuses matching key pairs, and rewrites references. Public-key comments and supported private-key encodings do not affect identity. Encrypted private keys that cannot be parsed without a passphrase are compared by contents. Existing different keys are preserved under their original names; incoming collisions receive a new name. Repeated restores do not add copies, including duplicate pairs in older Python archives.

Archives contain private keys and are **not encrypted**. Archives, configs, and restored keys are written with private permissions. Restore rejects traversal, links, duplicate members, invalid metadata, and oversized archives before applying changes. Writes are atomic per file, not a transaction across the whole restore.

### Maintenance and updates

```bash
warden mole clean                  # macOS, via tw93/mole
warden mole optimize
warden mole analyze /Volumes
warden mole status --json
warden update                      # latest published binary release
warden update X.Y.Z                # select an exact release
warden update X.Y.Z --dry-run
```

Mole is installed through Homebrew if needed. `mole clean --dry-run` and `mole optimize --dry-run` invoke the installed Mole’s native preview; dry runs never install missing Mole. Updates download the platform archive, verify its SHA-256 and version, and atomically replace the executable. Branch/source updates such as `warden update main` are no longer supported. An explicit version chooses that release; a later bare `update` chooses latest.

### Global options and mirrors

`-c PATH`, `--dry-run`, and `--no-color` work before or after subcommands. `--version` reports the embedded binary version. Piped CLI output is plain text; `NO_COLOR` and truthy `WARDEN_NO_COLOR` disable color.

`WARDEN_USE_CN=1` enables the existing Homebrew, Rust, Node/npm, PyPI, and GitHub mirror mappings for downloads and installations. Truthy flags accept `1`, `true`, or `yes` in Go. Pass environment settings to the installer side of a pipe:

```bash
curl -fsSL https://raw.githubusercontent.com/LBYPatrick/warden/main/scripts/remote-install.sh \
  | WARDEN_USE_CN=1 bash
```

## Development and releases

Go 1.25+ is required only to build from source.

```bash
make format        # gofmt + shell syntax checks
make test          # race-enabled Go tests + vet
make build         # build/warden with VERSION embedded
make install       # install locally compiled binary and shell integrations
make uninstall     # preserve configuration, keys, and archives
make release       # four platform archives + per-archive SHA-256 files
bash tests/install.sh  # offline installer test after make build
bash tests/cli.sh      # compiled CLI and isolated Git/archive integration
```

`cmd/warden` contains the entry point; `internal/app` owns config, identity, packages, archives, and updates; `internal/tui` owns the Bubble Tea dashboard. `scripts/release/package.sh` builds one self-contained archive. Runtime assets are the executable, license, man page, and completions.

To publish, update `VERSION` and the README badge, commit the release, and push the matching `vX.Y.Z` tag. The release workflow verifies the tag/version match, runs tests, builds all four archives, and publishes a GitHub release. CI runs tests on macOS and Linux. Generated binaries and archives are ignored by Git.

For Zsh completions, add `fpath=(~/.zsh/completions $fpath)` before `autoload -Uz compinit && compinit`. Bash completions live in `~/.local/share/bash-completion/completions/warden`; the man page is in `~/.local/share/man/man1/warden.1`.

See [the feature-parity audit](docs/feature-parity.md) for the Python baseline, regression coverage, and intentional migration changes.

## License

[LGPL-3.0-or-later](LICENSE).
