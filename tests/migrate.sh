#!/bin/bash
# Test migration in isolated homes without executing legacy runtimes or networking.
set -euo pipefail
# Keep host Warden launchers out of fixture discovery.
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
root="$(cd "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
version="$(cat "$root/VERSION")"
fixture_home="$tmp/home"
mkdir -p "$fixture_home/legacy/bin" "$fixture_home/legacy/warden" "$fixture_home/.local/bin" "$fixture_home/shadow" "$fixture_home/.warden/keys" "$fixture_home/.ssh"
printf '# legacy Python entry point\n' > "$fixture_home/legacy/warden/__main__.py"
printf '#!/bin/bash\ntouch "%s/legacy-executed"\nexit 91\n' "$tmp" > "$fixture_home/legacy/bin/warden"
chmod +x "$fixture_home/legacy/bin/warden"
for runtime in python python3 uv go git; do cp "$fixture_home/legacy/bin/warden" "$fixture_home/shadow/$runtime"; done
printf '{identities:{}}\n' > "$fixture_home/.warden/warden.jsonc"
printf 'fixture private key\n' > "$fixture_home/.warden/keys/key"
printf 'Host fixture\n HostName example.invalid\n' > "$fixture_home/.ssh/config"
cp "$fixture_home/.warden/warden.jsonc" "$tmp/config-before"
cp "$fixture_home/.warden/keys/key" "$tmp/key-before"
cp "$fixture_home/.ssh/config" "$tmp/ssh-before"
ln -s ../../legacy/bin/warden "$fixture_home/.local/bin/warden"
ln -s ../legacy/bin/warden "$fixture_home/shadow/warden"
env HOME="$fixture_home" PATH="$fixture_home/shadow:$PATH" bash "$root/scripts/migrate-python.sh" --binary "$root/build/warden" > "$tmp/result"
[[ ! -L "$fixture_home/.local/bin/warden" ]]
[[ "$(readlink "$fixture_home/shadow/warden")" == "$fixture_home/.local/bin/warden" ]]
[[ "$("$fixture_home/shadow/warden" --version)" == "warden $version" ]]
[[ ! -e "$tmp/legacy-executed" ]]
backups=("$fixture_home/.warden/migrations"/python-to-go-*)
[[ "$(readlink "${backups[0]}/warden")" == ../../legacy/bin/warden ]]
[[ "$(readlink "${backups[0]}/path-warden")" == ../legacy/bin/warden ]]
[[ -f "$fixture_home/legacy/warden/__main__.py" ]]
cmp "$tmp/config-before" "$fixture_home/.warden/warden.jsonc"
cmp "$tmp/key-before" "$fixture_home/.warden/keys/key"
cmp "$tmp/ssh-before" "$fixture_home/.ssh/config"
# Repeated migrations remain safe; a directory alias must not become a self-link.
ln -s .local/bin "$fixture_home/bin-alias"
env HOME="$fixture_home" PATH="$fixture_home/bin-alias:$PATH" bash "$root/scripts/migrate-python.sh" --binary "$root/build/warden" >/dev/null
[[ ! -L "$fixture_home/.local/bin/warden" ]]
[[ "$("$fixture_home/bin-alias/warden" --version)" == "warden $version" ]]
# Supplied shell/Python launchers are rejected before execution or replacement.
if env HOME="$fixture_home" bash "$root/scripts/migrate-python.sh" --binary "$fixture_home/legacy/bin/warden" >/dev/null 2>&1; then
    echo 'Accepted a legacy wrapper as a native binary' >&2; exit 1
fi
[[ ! -e "$tmp/legacy-executed" ]]
[[ "$("$fixture_home/.local/bin/warden" --version)" == "warden $version" ]]
# A dangling launcher is backed up without dereferencing it.
broken_home="$tmp/broken-home"
mkdir -p "$broken_home/.local/bin"
ln -s /nonexistent/old-warden "$broken_home/.local/bin/warden"
env HOME="$broken_home" bash "$root/scripts/migrate-python.sh" --binary "$root/build/warden" >/dev/null
backups=("$broken_home/.warden/migrations"/python-to-go-*)
[[ "$(readlink "${backups[0]}/warden")" == /nonexistent/old-warden ]]
# Updated checkouts no longer have Python files; their Go wrapper can still
# shadow the installed binary, either copied or reached through a symlink.
for mode in symlink copy; do
    dev_home="$tmp/dev-$mode"
    mkdir -p "$dev_home/checkout/bin" "$dev_home/shadow"
    cp "$root/bin/warden" "$dev_home/checkout/bin/warden"
    if [[ "$mode" == symlink ]]; then
        ln -s ../checkout/bin/warden "$dev_home/shadow/warden"
    else
        cp "$root/bin/warden" "$dev_home/shadow/warden"
    fi
    env HOME="$dev_home" PATH="$dev_home/shadow:$PATH" bash "$root/scripts/migrate-python.sh" --binary "$root/build/warden" >/dev/null
    [[ "$(readlink "$dev_home/shadow/warden")" == "$dev_home/.local/bin/warden" ]]
    [[ "$("$dev_home/shadow/warden" --version)" == "warden $version" ]]
    cmp "$root/bin/warden" "$dev_home/checkout/bin/warden"
    backups=("$dev_home/.warden/migrations"/python-to-go-*)
    if [[ "$mode" == symlink ]]; then
        [[ "$(readlink "${backups[0]}/path-warden")" == ../checkout/bin/warden ]]
    else
        cmp "$root/bin/warden" "${backups[0]}/path-warden"
    fi
done
# Exercise the piped bootstrap and pinned, checksum-verified download route.
mkdir -p "$tmp/downloads" "$tmp/transport" "$tmp/payload" "$tmp/download-home/.local/bin"
case "$(uname -s)" in Darwin) platform=darwin ;; *) platform=linux ;; esac
case "$(uname -m)" in arm64|aarch64) arch=arm64 ;; *) arch=amd64 ;; esac
archive="warden-$version-$platform-$arch.tar.gz"
cp "$root/build/warden" "$tmp/payload/warden"
cp "$root/scripts/install.sh" "$tmp/downloads/install.sh"
COPYFILE_DISABLE=1 tar -czf "$tmp/downloads/$archive" -C "$tmp/payload" warden
(cd "$tmp/downloads" && shasum -a 256 "$archive" > "$archive.sha256")
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
cp "$fixture_home/legacy/bin/warden" "$tmp/download-home/.local/bin/warden"
env HOME="$tmp/download-home" PATH="$tmp/transport:$PATH" WARDEN_TEST_DOWNLOADS="$tmp/downloads" bash -s -- --version "$version" < "$root/scripts/migrate-python.sh" >/dev/null
[[ "$("$tmp/download-home/.local/bin/warden" --version)" == "warden $version" ]]
backups=("$tmp/download-home/.warden/migrations"/python-to-go-*)
cmp "${backups[0]}/warden" "$fixture_home/legacy/bin/warden"
printf 'bad checksum\n' > "$tmp/downloads/$archive.sha256"
if env HOME="$tmp/download-home" PATH="$tmp/transport:$PATH" WARDEN_TEST_DOWNLOADS="$tmp/downloads" bash "$root/scripts/migrate-python.sh" --version "$version" >/dev/null 2>&1; then
    echo 'Accepted a corrupt release checksum' >&2; exit 1
fi
[[ "$("$tmp/download-home/.local/bin/warden" --version)" == "warden $version" ]]
printf 'Migration: symlink backups, PATH repair, repeat runs, dangling launchers, runtime rejection, data preservation, piped install, and checksum rejection passed.\n'
