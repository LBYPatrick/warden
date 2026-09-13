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
candidate="$(mktemp "$install_dir/.warden-XXXXXX")"
cp "$tmp/warden" "$candidate"
chmod 755 "$candidate"
mv -f "$candidate" "$install_dir/warden"
candidate=""
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
