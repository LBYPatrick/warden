#!/bin/bash
# Exercise installation offline with the built executable and a fake download transport.
set -euo pipefail
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
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
# Piped remote installation handles old Python and updated Go checkout launchers.
cp "$root/scripts/install.sh" "$tmp/downloads/install.sh"
for mode in python go copied-python; do
    fixture="$tmp/$mode home"
    mkdir -p "$fixture/checkout/bin" "$fixture/shadow" "$fixture/.local/bin" "$fixture/.warden/keys"
    if [[ "$mode" == go ]]; then
        cp "$root/bin/warden" "$fixture/checkout/bin/warden"
    else
        cp "$root/tests/fixtures/python-launcher.sh" "$fixture/checkout/bin/warden"
        mkdir -p "$fixture/checkout/warden"
        touch "$fixture/checkout/warden/__main__.py"
    fi
    chmod +x "$fixture/checkout/bin/warden"
    ln -s ../../checkout/bin/warden "$fixture/.local/bin/warden"
    if [[ "$mode" == copied-python ]]; then
        cp "$fixture/checkout/bin/warden" "$fixture/shadow/warden"
    else
        ln -s ../checkout/bin/warden "$fixture/shadow/warden"
    fi
    printf 'preserve key\n' > "$fixture/.warden/keys/key"
    printf '{identities:{}}\n' > "$fixture/.warden/warden.jsonc"
    env HOME="$fixture" PATH="$tmp/transport:$fixture/shadow:$PATH" bash -s -- --version "$version" < "$root/scripts/remote-install.sh" > "$tmp/install-result"
    [[ "$("$fixture/shadow/warden" --version)" == "warden $version" ]]
    [[ "$(readlink "$fixture/shadow/warden")" == "$fixture/.local/bin/warden" ]]
    [[ "$(cat "$fixture/.warden/keys/key")" == 'preserve key' ]]
    [[ "$(cat "$fixture/.warden/warden.jsonc")" == '{identities:{}}' ]]
    backups=("$fixture/.warden/migrations"/python-to-go-*)
    [[ "$(readlink "${backups[0]}/warden")" == ../../checkout/bin/warden ]]
    # A second install must not reimport or back up a native installation.
    env HOME="$fixture" PATH="$tmp/transport:$fixture/.local/bin:$PATH" bash -s -- --version "$version" < "$root/scripts/remote-install.sh" >/dev/null
    backups=("$fixture/.warden/migrations"/python-to-go-*)
    [[ ${#backups[@]} -eq 1 ]]
done
# Protected shadowing launchers fail clearly before replacing the old binary.
if [[ "$EUID" != 0 ]]; then
    protected="$tmp/protected"
    mkdir -p "$protected/shadow" "$protected/.local/bin"
    cp "$root/bin/warden" "$protected/shadow/warden"
    cp "$root/tests/fixtures/python-launcher.sh" "$protected/.local/bin/warden"
    chmod +x "$protected/shadow/warden" "$protected/.local/bin/warden"
    chmod 555 "$protected/shadow"
    result=0
    env HOME="$protected" PATH="$tmp/transport:$protected/shadow:$PATH" bash -s -- --version "$version" < "$root/scripts/remote-install.sh" > "$tmp/protected-result" 2>&1 || result=$?
    chmod 755 "$protected/shadow"
    [[ "$result" != 0 ]]
    grep -q 'requires administrator permission' "$tmp/protected-result"
    cmp "$root/tests/fixtures/python-launcher.sh" "$protected/.local/bin/warden"
    [[ ! -e "$protected/.warden/migrations" ]]
fi
printf 'invalid checksum\n' > "$tmp/downloads/$archive.sha256"
if PATH="$tmp/transport:$PATH" HOME="$tmp/home" bash "$root/scripts/install.sh" --version "$version" --install-dir "$tmp/bin" >/dev/null 2>&1; then
    echo 'Installer accepted a bad checksum' >&2; exit 1
fi
[[ "$("$tmp/bin/warden" --version)" == "warden $version" ]]
[[ ! -e "$tmp/home/.warden/repo" && ! -e "$tmp/home/.venv" ]]
broken="$tmp/broken"
mkdir -p "$broken/.local/bin"
ln -s /missing/python/warden "$broken/.local/bin/warden"
if env HOME="$broken" PATH="$tmp/transport:$PATH" bash -s -- --version "$version" < "$root/scripts/remote-install.sh" >/dev/null 2>&1; then
    echo 'Corrupt release migrated a legacy installation' >&2; exit 1
fi
[[ "$(readlink "$broken/.local/bin/warden")" == /missing/python/warden ]]
[[ ! -e "$broken/.warden/migrations" ]]
printf 'Installer: fresh install, automatic Python/Go migration, protected PATH handling, version pin, checksum rejection, and integrations passed.\n'
