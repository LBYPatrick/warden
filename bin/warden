#!/bin/bash
# Warden — Describe the system you live in
# Resolve symlinks to find repo root
SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SOURCE" ]; do
    DIR="$(cd "$(dirname "$SOURCE")" && pwd)"
    SOURCE="$(readlink "$SOURCE")"
    [[ "$SOURCE" != /* ]] && SOURCE="$DIR/$SOURCE"
done
WARDEN_ROOT="$(cd "$(dirname "$SOURCE")/.." && pwd)"

# China mirror: set uv index when WARDEN_USE_CN is truthy
case "${WARDEN_USE_CN:-}" in
    1 | true | yes)
        export UV_INDEX_URL="${UV_INDEX_URL:-https://mirrors.aliyun.com/pypi/simple/}"
        ;;
esac

export WARDEN_ORIG_CWD="${WARDEN_ORIG_CWD:-$PWD}"
cd "$WARDEN_ROOT" || exit 1

# Resolve uv binary — may not be in PATH after fresh install
UV_BIN="uv"
if ! command -v uv &>/dev/null; then
    if [ -x "$HOME/.local/bin/uv" ]; then
        UV_BIN="$HOME/.local/bin/uv"
    elif [ -x "$HOME/.cargo/bin/uv" ]; then
        UV_BIN="$HOME/.cargo/bin/uv"
    else
        echo "Error: uv not found. Install it with: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
        exit 1
    fi
fi
exec "$UV_BIN" run python -m warden "$@"
