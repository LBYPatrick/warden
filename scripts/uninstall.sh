#!/bin/bash
set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'
BOLD='\033[1m'

SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SOURCE" ]; do
    DIR="$(cd "$(dirname "$SOURCE")" && pwd)"
    SOURCE="$(readlink "$SOURCE")"
    [[ "$SOURCE" != /* ]] && SOURCE="$DIR/$SOURCE"
done
SCRIPT_DIR="$(cd "$(dirname "$SOURCE")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo ""
echo -e "${BOLD}===========================================${NC}"
echo -e "${BOLD}         Warden Uninstall${NC}"
echo -e "${BOLD}===========================================${NC}"
echo ""

# Remove symlink — check both new (~/.local/bin) and legacy (/usr/local/bin) locations
BIN_DIR="${HOME}/.local/bin"
LEGACY_BIN_DIR="/usr/local/bin"
_removed_bin=false

if [ -L "$BIN_DIR/warden" ]; then
    rm -f "$BIN_DIR/warden"
    echo -e "  ${GREEN}✓${NC} Removed $BIN_DIR/warden"
    _removed_bin=true
fi
if [ -L "$LEGACY_BIN_DIR/warden" ]; then
    if [ -w "$LEGACY_BIN_DIR" ] || [ "$(id -u)" -eq 0 ]; then
        rm -f "$LEGACY_BIN_DIR/warden"
    else
        sudo rm -f "$LEGACY_BIN_DIR/warden"
    fi
    echo -e "  ${GREEN}✓${NC} Removed $LEGACY_BIN_DIR/warden (legacy)"
    _removed_bin=true
fi
if ! $_removed_bin; then
    echo -e "  ${YELLOW}⊘${NC} No warden symlink found"
fi

# Remove venv
if [ -d "$PROJECT_ROOT/.venv" ]; then
    rm -rf "$PROJECT_ROOT/.venv"
    echo -e "  ${GREEN}✓${NC} Removed .venv"
fi

# Remove caches
rm -rf "$PROJECT_ROOT/__pycache__" "$PROJECT_ROOT/.ruff_cache" "$PROJECT_ROOT/warden/__pycache__"
echo -e "  ${GREEN}✓${NC} Removed caches"

# Remove man page — check both new and legacy locations
MAN_PAGE="${HOME}/.local/share/man/man1/warden.1"
LEGACY_MAN_PAGE="/usr/local/share/man/man1/warden.1"

if [ -f "$MAN_PAGE" ]; then
    rm -f "$MAN_PAGE"
    echo -e "  ${GREEN}✓${NC} Removed man page"
fi
if [ -f "$LEGACY_MAN_PAGE" ]; then
    if [ -w "$(dirname "$LEGACY_MAN_PAGE")" ] || [ "$(id -u)" -eq 0 ]; then
        rm -f "$LEGACY_MAN_PAGE"
    else
        sudo rm -f "$LEGACY_MAN_PAGE"
    fi
    echo -e "  ${GREEN}✓${NC} Removed legacy man page"
fi

# Remove completions
if [ -L "${HOME}/.zsh/completions/_warden" ]; then
    rm -f "${HOME}/.zsh/completions/_warden"
    echo -e "  ${GREEN}✓${NC} Removed zsh completions"
fi
if [ -L "${HOME}/.local/share/bash-completion/completions/warden" ]; then
    rm -f "${HOME}/.local/share/bash-completion/completions/warden"
    echo -e "  ${GREEN}✓${NC} Removed bash completions"
fi

echo ""
echo -e "${BOLD}===========================================${NC}"
echo ""
echo -e "${GREEN}${BOLD}Warden uninstalled!${NC}"
