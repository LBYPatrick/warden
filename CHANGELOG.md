# Changelog

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
