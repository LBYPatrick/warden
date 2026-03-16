# Changelog

## [Unreleased]

### Added
- `warden backup all` / `warden restore all` to backup and restore both git identities and SSH config in a single archive
- `.warden-marker` JSON marker file in every archive for type identification with double safety validation
- `--dry-run` global flag for all mutating commands (switch, backup, restore)
- Pytest test suite with 61 tests covering config, SSH config, backup/restore, and display modules
- GitHub Actions CI workflow running lint, format check, and tests on Ubuntu and macOS

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
