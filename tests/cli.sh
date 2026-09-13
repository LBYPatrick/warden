#!/bin/bash
# Compiled CLI smoke test with an isolated home and Git configuration.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
export HOME="$tmp/home" GIT_CONFIG_GLOBAL="$tmp/gitconfig" WARDEN_NO_COLOR=1
mkdir -p "$HOME/.ssh"
cat > "$tmp/config.jsonc" <<'CONFIG'
{identities:{personal:{name:'Test User',email:'test@example.invalid',signing_key:'~/.ssh/test.pub'}}}
CONFIG
printf 'test-private-key\n' > "$HOME/.ssh/test"
printf 'test-public-key\n' > "$HOME/.ssh/test.pub"
printf 'Host example\n  IdentityFile ~/.ssh/test\n' > "$HOME/.ssh/config"
[[ "$("$root/build/warden" -c "$tmp/config.jsonc" id list --names)" == personal ]]
"$root/build/warden" id switch PERSONAL -c "$tmp/config.jsonc" >/dev/null
[[ "$(git config --global user.email)" == test@example.invalid ]]
"$root/build/warden" backup -m git,ssh -c "$tmp/config.jsonc" -o "$tmp/archive.tar.gz" >/dev/null
"$root/build/warden" restore "$tmp/archive.tar.gz" -c "$tmp/restored.jsonc" >/dev/null
"$root/build/warden" restore "$tmp/archive.tar.gz" -c "$tmp/restored.jsonc" >/dev/null
[[ ! -d "$HOME/.warden/keys" ]]
[[ "$("$root/build/warden" id list --names -c "$tmp/restored.jsonc")" == personal ]]
"$root/build/warden" backup -m git --dry-run -c "$tmp/missing/config.jsonc" -o "$tmp/no-write.tar.gz" >/dev/null
[[ ! -e "$tmp/no-write.tar.gz" && ! -e "$tmp/missing" ]]
printf 'CLI: isolated Git switch, legacy JSON5, backup/restore, key reuse, dry-run passed.\n'

if [[ "$(uname -s)" == Darwin ]]; then
    mkdir -p "$tmp/fakebin"
    printf '#!/bin/bash\nprintf "mole stub\\n"\nexit 7\n' > "$tmp/fakebin/mo"
    chmod +x "$tmp/fakebin/mo"
    mole_status=0
    PATH="$tmp/fakebin:$PATH" "$root/build/warden" mole status --json >/dev/null 2>&1 || mole_status=$?
    [[ "$mole_status" == 7 ]]
    printf 'CLI: Mole child exit status preserved.\n'
fi
