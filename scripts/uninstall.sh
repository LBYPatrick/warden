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

# Remove symlink
if [ -L /usr/local/bin/warden ]; then
    if [ -w /usr/local/bin ] || [ "$(id -u)" -eq 0 ]; then
        rm -f /usr/local/bin/warden
    else
        sudo rm -f /usr/local/bin/warden
    fi
    echo -e "  ${GREEN}✓${NC} Removed /usr/local/bin/warden"
else
    echo -e "  ${YELLOW}⊘${NC} /usr/local/bin/warden not found"
fi

# Remove venv
if [ -d "$PROJECT_ROOT/.venv" ]; then
    rm -rf "$PROJECT_ROOT/.venv"
    echo -e "  ${GREEN}✓${NC} Removed .venv"
fi

# Remove caches
rm -rf "$PROJECT_ROOT/__pycache__" "$PROJECT_ROOT/.ruff_cache" "$PROJECT_ROOT/warden/__pycache__"
echo -e "  ${GREEN}✓${NC} Removed caches"

# Remove man page
MAN_PAGE="/usr/local/share/man/man1/warden.1"
if [ -f "$MAN_PAGE" ]; then
    if [ -w "$(dirname "$MAN_PAGE")" ] || [ "$(id -u)" -eq 0 ]; then
        rm -f "$MAN_PAGE"
    else
        sudo rm -f "$MAN_PAGE"
    fi
    echo -e "  ${GREEN}✓${NC} Removed man page"
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
