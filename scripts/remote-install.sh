#!/bin/bash
# Bootstrap the binary installer; target computers need no source or runtime.
# install.sh automatically backs up and migrates recognized legacy launchers.
set -euo pipefail
repo="${WARDEN_REPO:-LBYPatrick/warden}"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
curl --retry 3 -fsSL "https://raw.githubusercontent.com/$repo/main/scripts/install.sh" -o "$tmp/install.sh"
bash "$tmp/install.sh" "$@"
