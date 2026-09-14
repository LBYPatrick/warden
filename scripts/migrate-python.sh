#!/bin/bash
# Migrate a legacy launcher without requiring or invoking Python, uv, Go, or git.
set -euo pipefail
umask 077
install_dir="${WARDEN_INSTALL_DIR:-$HOME/.local/bin}"
source_dir=""
binary=""
version="${WARDEN_VERSION:-}"
repo="${WARDEN_REPO:-LBYPatrick/warden}"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --binary|--source|--version|--install-dir)
            [[ $# -ge 2 && -n "$2" ]] || { echo "$1 requires a value" >&2; exit 1; }
            case "$1" in
                --binary) binary="$2" ;;
                --source) source_dir="$2" ;;
                --version) version="$2" ;;
                --install-dir) install_dir="$2" ;;
            esac
            shift 2 ;;
        --help)
            echo 'Usage: migrate-python.sh [--version VERSION | --binary PATH] [--source CHECKOUT] [--install-dir DIR]'
            echo 'Defaults: latest release, detected legacy checkout, ~/.local/bin.'
            echo 'Backs up replaced launchers; retains configs, keys, archives, checkout, and shared runtimes.'
            exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done
[[ -z "$binary" || -z "$version" ]] || { echo 'Choose --binary or --version, not both.' >&2; exit 1; }
[[ "$repo" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || { echo 'Invalid WARDEN_REPO' >&2; exit 1; }
if [[ -n "$source_dir" ]]; then
    [[ -f "$source_dir/warden/__main__.py" ]] || { echo "Not a legacy Warden checkout: $source_dir" >&2; exit 1; }
    source_dir="$(cd "$source_dir" && pwd -P)"
fi
mkdir -p "$install_dir"
install_dir="$(cd "$install_dir" && pwd -P)"
launcher="$install_dir/warden"
[[ ! -d "$launcher" ]] || { echo "Launcher is a directory: $launcher" >&2; exit 1; }

# Read symlinks only; never execute a legacy wrapper, even to query its version.
resolve_link() {
    local resolved="$1" target depth
    for ((depth=0; depth<40; depth++)); do
        if [[ ! -L "$resolved" ]]; then printf '%s\n' "$resolved"; return; fi
        target="$(readlink "$resolved")"
        if [[ "$target" == /* ]]; then resolved="$target"; else resolved="$(dirname "$resolved")/$target"; fi
    done
    echo "Symlink loop: $1" >&2
    return 1
}
legacy_source() {
    local resolved parent
    resolved="$(resolve_link "$1")" || return 1
    [[ "$(basename "$resolved")" == warden && "$(basename "$(dirname "$resolved")")" == bin ]] || return 0
    parent="$(dirname "$resolved")/.."
    if [[ -f "$parent/warden/__main__.py" ]]; then (cd "$parent" && pwd -P); fi
}
# Recognize only our exact development wrapper, without executing it. A legacy
# symlink can point into a checkout that has already been updated to Go.
is_development_launcher() {
    [[ -f "$1" ]] || return 1
    cmp -s "$1" <(cat <<'WRAPPER'
#!/bin/bash
# Development launcher only; releases ship a native executable.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$root/build/warden" "$@"
WRAPPER
    )
}
path_launcher="$(type -P warden || true)"
if [[ -n "$path_launcher" ]]; then
    path_launcher="$(cd "$(dirname "$path_launcher")" && pwd -P)/$(basename "$path_launcher")"
fi
shadow=""
for old in "$launcher" "$path_launcher"; do
    [[ -n "$old" ]] || continue
    if [[ "$old" != "$launcher" ]] && is_development_launcher "$old"; then
        shadow="$old"
        continue
    fi
    [[ -L "$old" ]] || continue
    detected="$(legacy_source "$old")"
    if [[ -z "$source_dir" && -n "$detected" ]]; then source_dir="$detected"; fi
    if [[ "$old" != "$launcher" && -n "$detected" && "$detected" == "$source_dir" ]]; then
        shadow="$old"
    fi
done
if [[ -z "$source_dir" && -f "${WARDEN_DIR:-$HOME/.warden/repo}/warden/__main__.py" ]]; then
    source_dir="$(cd "${WARDEN_DIR:-$HOME/.warden/repo}" && pwd -P)"
fi
if [[ -n "$shadow" && ! -w "$(dirname "$shadow")" ]]; then
    echo "Legacy launcher shadows the new binary but its directory is not writable: $shadow" >&2
    echo 'Adjust PATH to prefer the install directory, or migrate that launcher with appropriate permissions.' >&2
    exit 1
fi

tmp="$(mktemp -d)"
candidate=""
trap 'rm -rf "$tmp"; if [[ -n "$candidate" ]]; then rm -f "$candidate"; fi' EXIT
if [[ -n "$binary" ]]; then
    [[ -f "$binary" ]] || { echo "Binary not found: $binary" >&2; exit 1; }
    cp "$binary" "$tmp/warden"
else
    # A helper copied into an old checkout must not run its Python installer.
    curl --retry 3 -fsSL "https://raw.githubusercontent.com/$repo/main/scripts/install.sh" -o "$tmp/install.sh"
    version_args=()
    if [[ -n "$version" ]]; then version_args=(--version "$version"); fi
    bash "$tmp/install.sh" --install-dir "$tmp" ${version_args[@]+"${version_args[@]}"}
fi
# Reject scripts before executing a supplied binary, including Python/shell wrappers.
magic="$(od -An -tx1 -N4 "$tmp/warden" | tr -d ' \n')"
case "$magic" in
    7f454c46|cffaedfe|feedfacf|cefaedfe|feedface|cafebabe|bebafeca) ;;
    *) echo 'Migration requires a native Warden release binary.' >&2; exit 1 ;;
esac
chmod 755 "$tmp/warden"
actual="$("$tmp/warden" --version)"
[[ "$actual" =~ ^warden\ [0-9]+\.[0-9]+\.[0-9]+(-[a-z]+\.[0-9]+)?$ ]] || { echo 'Not a versioned Warden binary.' >&2; exit 1; }

mkdir -p "$HOME/.warden/migrations"
backup="$(mktemp -d "$HOME/.warden/migrations/python-to-go-XXXXXX")"
if [[ -e "$launcher" || -L "$launcher" ]]; then cp -Pp "$launcher" "$backup/warden"; fi
if [[ -n "$shadow" ]]; then cp -Pp "$shadow" "$backup/path-warden"; fi
printf 'Legacy source: %s\nLauncher: %s\nPATH launcher: %s\nReplacement: %s\n' "$source_dir" "$launcher" "$shadow" "$actual" > "$backup/origin.txt"
printf 'Migration backup: %s\n' "$backup"
candidate="$(mktemp "$install_dir/.warden-migrate-XXXXXX")"
cp "$tmp/warden" "$candidate"
chmod 755 "$candidate"
mv -f "$candidate" "$launcher"
candidate=""
if [[ -n "$shadow" ]]; then
    link_stage="$(mktemp -d "$(dirname "$shadow")/.warden-link-XXXXXX")"
    ln -s "$launcher" "$link_stage/warden"
    mv -f "$link_stage/warden" "$shadow"
    rmdir "$link_stage"
fi
printf '\n  Migrated to %s\n  Executable  %s\n  Backup      %s\n' "$actual" "$launcher" "$backup"
echo 'Configs, keys, archives, the old checkout, and shared Python/uv installations were retained.'
if [[ -n "$source_dir" && -f "$source_dir/warden.jsonc" ]]; then
    printf 'Checkout-local config retained: %s/warden.jsonc\nUse -c with that path if it was your active config.\n' "$source_dir"
fi
if [[ -n "$path_launcher" && "$path_launcher" != "$launcher" && -z "$shadow" ]]; then
    printf 'Another launcher is on PATH: %s. Put %s first on PATH.\n' "$path_launcher" "$install_dir"
fi
printf 'Start a new shell (or run hash -r), then run: %s --version\n' "$launcher"
