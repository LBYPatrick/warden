# Warden

Native Go system descriptor and identity switcher. Use Ashley at `../ashley` as the reference for release packaging and terminal design.

## Architecture

- `cmd/warden`: entry point; launch TUI on an interactive bare invocation, help otherwise.
- `internal/app`: JSON5 config, identity operations, package registry/scanning/installing, SSH merging, portable archives, binary updates, CLI output.
- `internal/tui`: Bubble Tea dashboard, Ashley dark-blue palette, responsive navigation and details.
- `scripts/install.sh`: checksum-verified, version-pinned release installer.
- `scripts/release/package.sh`: static archives for darwin/linux × arm64/amd64.
- `tests/install.sh`: isolated offline installer integration test.

## Checks

Run `make format`, `make test`, and `make build` in that order. `make test` runs race tests and vet. After installer/package changes run `bash tests/install.sh` and `make release`. Do not commit generated build/dist artifacts. Use Conventional Commits.

## Invariants

- Keep legacy flat/unified JSON5 configs and Python `.warden-marker` archives readable.
- Explicit `-c` overrides default search paths, including restore and initial save.
- No writes for dry runs, help, listing, or reads of missing config.
- Preserve malformed destination configs and propagate process/write failures.
- Merge identity names, union package/tool lists, and replace matching SSH blocks.
- Deduplicate key pairs by material, share references across Git and SSH, reuse local pairs, and never overwrite different local keys.
- Validate archives before writing; reject traversal, links, duplicate entries, and excessive sizes.
- Use atomic private file writes. Never print private key contents.
- `App.Run` is injectable; tests must not change the user's Git settings or packages.
- Fixed tool recipes may use bash; package/identity values go through argument arrays, never string interpolation into shell code.
- CLI output is plain when piped; honor `NO_COLOR` and `WARDEN_NO_COLOR`.
- Runtime distribution is a native binary, never a checkout or language environment.

## Versioning

`VERSION` is embedded with `-X main.version` by build/package targets. Update the README version badge when bumping it. The release tag must equal `v$(cat VERSION)`. Update `[Unreleased]` in `CHANGELOG.md` for user-visible changes. Publishing is separate from local build verification.
