# Changelog

## [Unreleased]

### Fixed

- Recognize copied and symlinked Go development launchers during migration, including legacy symlinks into checkouts already updated to Go.

### Added

- Match Ashley’s sidebar, selection rows, and rounded TUI panels; add persistent light/dark mode and ten accent presets under Settings.

- Automatically migrate Python installations and stale development launchers through the normal remote installer, with backups and PATH repair.

- Add an Ashley-style Python-to-Go migration helper with native binary validation, launcher backups, legacy symlink detection, and PATH repair while preserving configuration and keys.

## [2.0.0] - 2026-09-13

### Added

- Add a native Go CLI and an Ashley-inspired interactive dashboard for identities, packages, archives, and maintenance.
- Add checksum-verified binary installation and updates, explicit release version selection, and macOS/Linux ARM64/x86-64 release artifacts.
- Add machine-readable identity listings, archive validation, and Go regression tests.
- Backup and restore apt sources (`/etc/apt/sources.list`, `sources.list.d/`) with the `pkg` module on Linux
- Restore auto-detects available modules from archive marker when `-m` is not specified

### Changed

- Replace the Python runtime and source-based installation with native Go binaries.
- Refresh CLI output, completions, and installation documentation.
- Replace branch-based self-update with binary release selection.
- APT scanning now uses `apt-mark showmanual` to capture only user-installed packages (falls back to `dpkg --get-selections`)
- APT install filters packages through `apt-cache pkgnames` to skip unavailable ones before bulk install

### Fixed

- Restore Homebrew bulk/live installation and retries, APT refresh/fallback behavior, contextual help, derived identity details, and Mole native previews.
- Preserve pnpm inventory, Xcode toolchain detection, and Linux formula scanning when cask inventory is unsupported.
- Keep successful package saves when a later manager fails; avoid requiring config for standalone installation.
- Make `--include-missing` retain absent-key SSH hosts without attempting to archive nonexistent files.
- Deduplicate key pairs across Git and SSH backups and reuse matching local keys during restore, including legacy archive duplicates.
- Preserve different local keys on filename collisions and honor selected restore modules and explicit config paths.
- Keep dry runs free of file writes and preserve malformed existing configurations.

## [1.1.0] - 2026-03-16

### Added
- `warden mole` subcommand group for system cleanup and optimization powered by tw93/mole (macOS only)
- `warden mole clean`, `optimize`, `analyze`, `status` subcommands with `--dry-run` and `--json` support
- Auto-install Mole via Homebrew when not found on macOS
- Man page (`man warden`) installed automatically by `make install`
- Curl-installable `scripts/remote-install.sh` for one-line installation

### Changed
- Backup/restore now use `-m` flag with comma-delimited modules (`git`, `ssh`, `pkg`, or `all`); defaults to `all`
- Archive marker stores a modules list instead of a single type string (backward-compatible with legacy archives)
- Restore validates that each requested module exists in the archive before proceeding
- `backup` now re-scans system packages by default when `pkg` module is included; use `--skip-scan` to disable (replaces `-s`/`--scan`)

### Fixed
- Backup archives now save to the user's current directory instead of the project root
- Backup output messages now show the absolute path to the created archive

## [1.0.0] - 2026-03-15

### Added
- Config-driven Git identity switching via `warden switch <target>`
- JSON5 config file support (`warden.jsonc`) with comments and trailing commas
- Config resolution: `~/.warden/warden.jsonc`, `~/.ssh/warden.jsonc`, `~/warden.jsonc`, `./warden.jsonc`, or `-c <path>`
- `warden list` to show all available identity targets
- `warden show [target]` to display current git identity or a specific target's config
- Auto-derived `core.sshCommand` from signing key path (non-default keys only)
- Auto-enable SSH commit signing (`gpg.format=ssh`, `commit.gpgsign=true`) on switch
- Case-insensitive target name lookup
- `warden backup git` to archive identities and signing keys into portable tar.gz
- `warden backup ssh` to archive `~/.ssh/config` and identity keys into portable tar.gz
- `warden backup all` / `warden restore all` for combined backup and restore
- `warden restore git <archive>` to restore git identities to `~/.warden/`
- `warden restore ssh <archive>` to restore and merge SSH config into `~/.ssh/config`
- Unified `warden.jsonc` config format with `identities`, `packages`, and `tools` sections
- Legacy flat config format auto-detection and backward compatibility
- `warden scan` command to snapshot installed brew formulae/casks, apt packages, and developer tools into config
- `warden apply` command to install missing packages/tools from config (skips already-installed unless `--force`)
- `warden update` command for self-updating via git pull and reinstall
- System package scanning: Homebrew formulae/casks, apt packages, 10 developer tools
- Config merge algorithm for restore: identities override by name, package/tool lists union-merged and deduplicated
- `WARDEN_USE_CN` env flag for China mirror mode (Homebrew, PyPI, rustup, npm, fnm, GitHub)
- `.warden-marker` JSON marker file in every archive for type identification
- `--dry-run` global flag for all mutating commands
- 6-digit path-based hashing for key filenames to avoid collisions in archives
- SSH config merge strategy: update existing hosts in-place, append new ones
- Path traversal protection when extracting archives
- Proper file permissions on restore (600 for private keys, 644 for public keys)
- Rich-powered terminal output with TTY detection
- Bash and Zsh tab-completion scripts
- Pytest test suite with 102 tests
- Cross-platform support (macOS and Linux)
- Makefile with install, uninstall, clean, build, format, and test targets
