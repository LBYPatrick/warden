#!/bin/bash
# Install a prebuilt Warden release. Requires no Go, Python, uv, git, or npm.
set -euo pipefail
version="${WARDEN_VERSION:-}"
install_dir="${WARDEN_INSTALL_DIR:-$HOME/.local/bin}"
repo="${WARDEN_REPO:-LBYPatrick/warden}"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --version | --install-dir)
            [[ $# -ge 2 ]] || { echo "$1 requires a value" >&2; exit 1; }
            case "$1" in
                --version) version="$2" ;;
                --install-dir) install_dir="$2" ;;
            esac
            shift 2
            ;;
        --help)
            echo "Usage: install.sh [--version X.Y.Z] [--install-dir DIR]"
            exit 0
            ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

# Inspect launchers as files: the old Python runtime may already be gone.
resolve_launcher() {
    local resolved="$1" target depth
    for ((depth=0; depth<40; depth++)); do
        if [[ ! -L "$resolved" ]]; then printf '%s\n' "$resolved"; return; fi
        target="$(readlink "$resolved")"
        if [[ "$target" == /* ]]; then resolved="$target"; else resolved="$(dirname "$resolved")/$target"; fi
    done
    echo "Symlink loop: $1" >&2
    return 1
}
native_launcher() {
    [[ -f "$1" ]] || return 1
    case "$(od -An -tx1 -N4 "$1" | tr -d ' \n')" in
        7f454c46|cffaedfe|feedfacf|cefaedfe|feedface|cafebabe|bebafeca) return 0 ;;
        *) return 1 ;;
    esac
}
legacy_checkout() {
    local resolved parent
    resolved="$(resolve_launcher "$1")" || return 1
    [[ "$(basename "$resolved")" == warden && "$(basename "$(dirname "$resolved")")" == bin ]] || return 0
    parent="$(dirname "$resolved")/.."
    if [[ -f "$parent/warden/__main__.py" ]]; then (cd "$parent" && pwd -P); fi
}
known_wrapper() {
    [[ -f "$1" ]] || return 1
    [[ "$(head -c 2 "$1")" == '#!' ]] || return 1
    # Match repository launcher commands without invoking an old runtime.
    head -c 8192 "$1" | grep -Fqx -e 'exec "$UV_BIN" run python -m warden "$@"' -e 'exec "$root/build/warden" "$@"'
}
prepare_migration() {
    source_dir=""
    shadow=""
    backup=""
    path_launcher="$(type -P warden || true)"
    if [[ -n "$path_launcher" ]]; then
        path_launcher="$(cd "$(dirname "$path_launcher")" && pwd -P)/$(basename "$path_launcher")"
    fi
    local old detected migrate=false
    for old in "$launcher" "$path_launcher"; do
        [[ -n "$old" ]] || continue
        detected=""
        if [[ -L "$old" ]]; then detected="$(legacy_checkout "$old")"; fi
        if [[ -n "$detected" ]]; then
            if [[ -n "$source_dir" && "$source_dir" != "$detected" ]]; then
                echo 'Conflicting legacy checkouts; adjust PATH to select one before installing.' >&2
                exit 1
            fi
            source_dir="$detected"
        fi
        if [[ -n "$detected" ]] || known_wrapper "$old"; then
            migrate=true
            if [[ "$old" != "$launcher" ]]; then shadow="$old"; fi
        fi
    done
    if [[ -e "$launcher" || -L "$launcher" ]] && ! native_launcher "$launcher"; then migrate=true; fi
    if [[ -z "$source_dir" && ( "$migrate" == true || ! -e "$launcher" ) ]]; then
        local parent="${WARDEN_DIR:-$HOME/.warden/repo}"
        if [[ -f "$parent/warden/__main__.py" ]]; then source_dir="$(cd "$parent" && pwd -P)"; migrate=true; fi
    fi
    [[ "$migrate" == true ]] || return 0
    if [[ -n "$shadow" && ! -w "$(dirname "$shadow")" ]]; then
        printf 'Legacy launcher shadows the installation and requires administrator permission: %s\n' "$shadow" >&2
        printf 'Put the install directory first on PATH before rerunning:\n  export PATH=%q:"$PATH"\n' "$install_dir" >&2
        exit 1
    fi
    # Downloads and version validation have succeeded before any backups/writes.
    (umask 077; mkdir -p "$HOME/.warden/migrations")
    backup="$(mktemp -d "$HOME/.warden/migrations/python-to-go-XXXXXX")"
    if [[ -e "$launcher" || -L "$launcher" ]]; then cp -Pp "$launcher" "$backup/warden"; fi
    if [[ -n "$shadow" ]]; then cp -Pp "$shadow" "$backup/path-warden"; fi
    printf 'Legacy source: %s\nLauncher: %s\nPATH launcher: %s\n' "$source_dir" "$launcher" "$shadow" > "$backup/origin.txt"
    printf '  Migration backup  %s\n' "$backup"
}
repair_migration_path() {
    if [[ -n "$shadow" ]]; then
        local stage
        stage="$(mktemp -d "$(dirname "$shadow")/.warden-link-XXXXXX")"
        ln -s "$launcher" "$stage/warden"
        mv -f "$stage/warden" "$shadow"
        rmdir "$stage"
    fi
    if [[ -n "$path_launcher" && "$path_launcher" != "$launcher" && -z "$shadow" ]]; then
        printf '  Another executable is first on PATH: %s\n  Prefer this installation: export PATH=%q:"$PATH"\n' "$path_launcher" "$install_dir"
    fi
    if [[ -n "$backup" ]]; then
        echo '  Migration complete. User data, the old checkout, and shared runtimes were retained.'
        echo '  Start a new shell or run hash -r.'
        if [[ -n "$source_dir" && -f "$source_dir/warden.jsonc" ]]; then
            printf '  Checkout config retained: %s/warden.jsonc; use -c with this path if it was your active config.\n' "$source_dir"
        fi
    fi
}

case "$(uname -s)" in
    Darwin) platform=darwin ;;
    Linux) platform=linux ;;
    *) echo "Warden binary releases support macOS and Linux." >&2; exit 1 ;;
esac
case "$(uname -m)" in
    arm64 | aarch64) arch=arm64 ;;
    x86_64 | amd64) arch=amd64 ;;
    *) echo "Unsupported CPU architecture." >&2; exit 1 ;;
esac
if [[ -z "$version" ]]; then
    latest="$(curl --retry 3 -fsSL -o /dev/null -w '%{url_effective}' "https://github.com/$repo/releases/latest")"
    version="${latest##*/}"
fi
version="${version#v}"
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-z]+\.[0-9]+)?$ ]] || { echo "Invalid release version: $version" >&2; exit 1; }
printf '\n  Warden / Download\n\n  Version      %s\n  Platform     %s / %s\n  Downloading and verifying binary…\n' "$version" "$platform" "$arch"
archive="warden-$version-$platform-$arch.tar.gz"
url="https://github.com/$repo/releases/download/v$version"
case "${WARDEN_USE_CN:-}" in 1|true|yes|TRUE|YES) url="https://ghp.ci/$url" ;; esac
tmp="$(mktemp -d)"
candidate=""
trap 'rm -rf "$tmp"; if [[ -n "$candidate" ]]; then rm -f "$candidate"; fi' EXIT
curl --retry 3 -fsSL "$url/$archive" -o "$tmp/$archive"
curl --retry 3 -fsSL "$url/$archive.sha256" -o "$tmp/$archive.sha256"
(
    cd "$tmp"
    read -r expected checksum_file < "$archive.sha256"
    [[ "$checksum_file" == "$archive" && "$expected" =~ ^[0-9a-fA-F]{64}$ ]] || { echo "Invalid checksum manifest" >&2; exit 1; }
    if command -v sha256sum >/dev/null; then
        actual="$(sha256sum "$archive")"
    else
        actual="$(shasum -a 256 "$archive")"
    fi
    [[ "${actual%% *}" == "$expected" ]] || { echo "Checksum mismatch" >&2; exit 1; }
)
# Only regular files from the release allowlist may be extracted.
while IFS= read -r entry; do
    case "$entry" in warden|LICENSE|man/|man/warden.1|completions/|completions/warden.bash|completions/warden.zsh) ;;
        *) echo "Unexpected release member: $entry" >&2; exit 1 ;;
    esac
done < <(tar -tzf "$tmp/$archive")
if tar -tvzf "$tmp/$archive" | awk 'substr($0,1,1) != "-" && substr($0,1,1) != "d" { bad=1 } END { exit !bad }'; then
    echo 'Release contains links or special files' >&2
    exit 1
fi
tar -xzf "$tmp/$archive" -C "$tmp"
[[ -f "$tmp/warden" && ! -L "$tmp/warden" ]] || { echo "Archive does not contain a warden executable" >&2; exit 1; }
chmod +x "$tmp/warden"
actual="$("$tmp/warden" --version)"
[[ "$actual" == "warden $version" ]] || { echo "Downloaded binary version mismatch: $actual" >&2; exit 1; }
mkdir -p "$install_dir"
install_dir="$(cd "$install_dir" && pwd -P)"
launcher="$install_dir/warden"
[[ ! -d "$launcher" ]] || { echo "Launcher is a directory: $launcher" >&2; exit 1; }
source_dir=""; shadow=""; backup=""; path_launcher=""
if [[ "${WARDEN_MIGRATION_STAGING:-}" != 1 ]]; then prepare_migration; fi
candidate="$(mktemp "$install_dir/.warden-XXXXXX")"
cp "$tmp/warden" "$candidate"
chmod 755 "$candidate"
mv -f "$candidate" "$install_dir/warden"
candidate=""
repair_migration_path
mkdir -p "$HOME/.local/share/man/man1" "$HOME/.local/share/bash-completion/completions" "$HOME/.zsh/completions"
if [[ -f "$tmp/man/warden.1" ]]; then cp "$tmp/man/warden.1" "$HOME/.local/share/man/man1/warden.1"; fi
if [[ -f "$tmp/completions/warden.bash" ]]; then cp "$tmp/completions/warden.bash" "$HOME/.local/share/bash-completion/completions/warden"; fi
if [[ -f "$tmp/completions/warden.zsh" ]]; then cp "$tmp/completions/warden.zsh" "$HOME/.zsh/completions/_warden"; fi
printf '\n  ✓ Installed Warden %s\n  Executable   %s/warden\n\n' "$version" "$install_dir"
if [[ "${WARDEN_BOOTSTRAP:-}" != 1 ]]; then
case ":$PATH:" in
    *":$install_dir:"*) ;;
    *) printf '  Add to PATH  export PATH=%q:"$PATH"\n\n' "$install_dir" ;;
esac
fi
