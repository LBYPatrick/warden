# Changelog

## [Unreleased]

### Added
- Unified `warden.jsonc` config format with `identities`, `packages`, and `tools` sections
- `warden scan` command to snapshot installed brew formulae/casks, apt packages, and developer tools into config
- `warden apply` command to install missing packages/tools from config (skips already-installed unless `--force`)
- `warden update` command for self-updating via git pull and reinstall
- System package scanning: Homebrew formulae/casks, apt packages, 10 developer tools (rustup, node, pnpm, conda, flutter, gcloud, aws, wrangler, xcode, android-tools)
- Config merge algorithm for restore: identities override by name, package/tool lists union-merged and deduplicated
- Legacy flat config format auto-detection and backward compatibility
- `warden/scanner.py` — synchronous system package and tool scanning
- `warden/installer.py` — package/tool installation with skip-if-present logic
- `warden/platform_info.py` — OS and architecture detection (macOS/Linux, amd64/arm64)
- `warden backup all` / `warden restore all` to backup and restore both git identities and SSH config in a single archive
- `.warden-marker` JSON marker file in every archive for type identification with double safety validation
- `--dry-run` global flag for all mutating commands (switch, backup, restore)
- Pytest test suite with 90 tests covering config, SSH config, backup/restore, display, and scanner modules
- GitHub Actions CI workflow running lint, format check, and tests on Ubuntu and macOS

### Changed
- Config format: identities now live under `"identities"` key (legacy flat format still supported)
- `backup git` and `backup ssh` now exclude packages/tools sections from archives
- `backup all` includes the full config (identities + packages + tools)
- Restore now merges warden.jsonc with existing config instead of overwriting
- Shell completions updated for new commands (scan, apply, update)

## [0.1.0] - 2026-03-15

### Added
- Config-driven Git identity switching via `warden switch <target>`
- JSONC config file support (`warden.jsonc`) with `//` and `/* */` comment stripping
- Config resolution: `~/.ssh/warden.jsonc`, `~/warden.jsonc`, `./warden.jsonc`, or `-c <path>`
- `warden list` to show all available identity targets
- `warden show [target]` to display current git identity or a specific target's config
- Auto-derived `core.sshCommand` from signing key path (non-default keys only)
- Auto-enable SSH commit signing (`gpg.format=ssh`, `commit.gpgsign=true`) on switch
- Case-insensitive target name lookup
- `warden backup git` to archive warden.jsonc and signing keys into portable tar.gz
- `warden backup ssh` to archive `~/.ssh/config` and identity keys into portable tar.gz
- `warden restore git <archive>` to restore git identities to `~/.warden/`
- `warden restore ssh <archive>` to restore and merge SSH config into `~/.ssh/config`
- 6-digit path-based hashing for key filenames to avoid collisions in archives
- SSH config merge strategy: update existing hosts in-place, append new ones
- `--include-missing` flag for SSH backup to include hosts with missing key files
- `~/.ssh/config.bak` safety backup before SSH config merge
- Path traversal protection when extracting archives
- Proper file permissions on restore (600 for private keys, 644 for public keys)
- Sheriff-style ANSI terminal output with TTY detection
- Bash and Zsh tab-completion scripts
- `--help` at every subcommand level
- Cross-platform support (macOS and Linux via `Path.home()`)
- Makefile with install, uninstall, clean, build, format, and test targets
- `bin/warden` bash wrapper with symlink resolution
