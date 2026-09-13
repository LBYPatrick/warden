#!/bin/bash
# Exercise installation offline with the built executable and a fake download transport.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/transport" "$tmp/payload" "$tmp/downloads" "$tmp/home"
version="$(cat "$root/VERSION")"
case "$(uname -s)" in Darwin) platform=darwin ;; *) platform=linux ;; esac
case "$(uname -m)" in arm64|aarch64) arch=arm64 ;; *) arch=amd64 ;; esac
archive="warden-$version-$platform-$arch.tar.gz"
cp "$root/build/warden" "$tmp/payload/warden"
cp -R "$root/man" "$root/completions" "$tmp/payload/"
COPYFILE_DISABLE=1 tar -czf "$tmp/downloads/$archive" -C "$tmp/payload" warden man completions
(cd "$tmp/downloads"; shasum -a 256 "$archive" > "$archive.sha256")
cat > "$tmp/transport/curl" <<'CURL'
#!/bin/bash
set -euo pipefail
url=""; dest=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        -o) dest="$2"; shift 2 ;;
        --retry|-w) shift 2 ;;
        https://*) url="$1"; shift ;;
        *) shift ;;
    esac
done
cp "$WARDEN_TEST_DOWNLOADS/${url##*/}" "$dest"
CURL
chmod +x "$tmp/transport/curl"
export WARDEN_TEST_DOWNLOADS="$tmp/downloads"
PATH="$tmp/transport:$PATH" HOME="$tmp/home" bash "$root/scripts/install.sh" --version "$version" --install-dir "$tmp/bin"
[[ "$("$tmp/bin/warden" --version)" == "warden $version" ]]
[[ -f "$tmp/home/.zsh/completions/_warden" ]]
printf 'invalid checksum\n' > "$tmp/downloads/$archive.sha256"
if PATH="$tmp/transport:$PATH" HOME="$tmp/home" bash "$root/scripts/install.sh" --version "$version" --install-dir "$tmp/bin" >/dev/null 2>&1; then
    echo 'Installer accepted a bad checksum' >&2; exit 1
fi
[[ "$("$tmp/bin/warden" --version)" == "warden $version" ]]
[[ ! -e "$tmp/home/.warden/repo" && ! -e "$tmp/home/.venv" ]]
printf 'Installer: version pin, checksum rejection, atomic replacement, integrations passed.\n'
