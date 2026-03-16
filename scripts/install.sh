#!/bin/bash
set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SOURCE" ]; do
    DIR="$(cd "$(dirname "$SOURCE")" && pwd)"
    SOURCE="$(readlink "$SOURCE")"
    [[ "$SOURCE" != /* ]] && SOURCE="$DIR/$SOURCE"
done
SCRIPT_DIR="$(cd "$(dirname "$SOURCE")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo -e "${BLUE}▶${NC} Installing Warden..."

# Check for uv
if ! command -v uv &>/dev/null; then
    echo -e "  ${YELLOW}⚠${NC} uv not found, installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo -e "  ${GREEN}✓${NC} uv installed"
fi

# Sync dependencies
echo -e "  ${BLUE}◐${NC} Syncing Python dependencies..."
cd "$PROJECT_ROOT"
uv sync
echo -e "  ${GREEN}✓${NC} Dependencies synced"

# Make bin/warden executable
chmod +x "$PROJECT_ROOT/bin/warden"
echo -e "  ${GREEN}✓${NC} bin/warden marked executable"

# Symlink to /usr/local/bin
if [ -w /usr/local/bin ] || [ "$(id -u)" -eq 0 ]; then
    ln -sf "$PROJECT_ROOT/bin/warden" /usr/local/bin/warden
    echo -e "  ${GREEN}✓${NC} Symlinked to /usr/local/bin/warden"
else
    sudo ln -sf "$PROJECT_ROOT/bin/warden" /usr/local/bin/warden
    echo -e "  ${GREEN}✓${NC} Symlinked to /usr/local/bin/warden (via sudo)"
fi

# Install shell completions
COMP_DIR="$PROJECT_ROOT/completions"
SHELL_NAME="$(basename "$SHELL")"

if [[ "$SHELL_NAME" == "zsh" ]]; then
    ZSH_COMP_DIR="${HOME}/.zsh/completions"
    mkdir -p "$ZSH_COMP_DIR"
    ln -sf "$COMP_DIR/warden.zsh" "$ZSH_COMP_DIR/_warden"
    echo -e "  ${GREEN}✓${NC} Zsh completions installed to $ZSH_COMP_DIR/_warden"
    if ! grep -q 'fpath.*\.zsh/completions' "${HOME}/.zshrc" 2>/dev/null; then
        echo -e "  ${YELLOW}⚠${NC} Add this to your ~/.zshrc if not already present:"
        echo -e "    ${BLUE}fpath=(~/.zsh/completions \$fpath)${NC}"
        echo -e "    ${BLUE}autoload -Uz compinit && compinit${NC}"
    fi
elif [[ "$SHELL_NAME" == "bash" ]]; then
    BASH_COMP_DIR="${HOME}/.local/share/bash-completion/completions"
    mkdir -p "$BASH_COMP_DIR"
    ln -sf "$COMP_DIR/warden.bash" "$BASH_COMP_DIR/warden"
    echo -e "  ${GREEN}✓${NC} Bash completions installed to $BASH_COMP_DIR/warden"
fi

echo ""
echo -e "  ${GREEN}✓${NC} Warden installed successfully"
