#!/bin/bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
gofmt -w cmd internal
for script in bin/warden scripts/*.sh scripts/release/*.sh tests/*.sh; do bash -n "$script"; done
