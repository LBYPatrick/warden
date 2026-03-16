#!/bin/bash
set -euo pipefail

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Lazy-check formatter installation
if [[ "${1:-}" != "--skip-check" ]]; then
    if ! uv run ruff --version &>/dev/null; then
        echo -e "  ${BLUE}◐${NC} Installing formatters..."
        bash scripts/install-formatter.sh
    fi
fi

echo -e "${BLUE}▶${NC} Formatting..."

# Ruff lint (import sorting + unused imports)
uv run ruff check --select I,F401 --fix .
echo -e "  ${GREEN}✓${NC} ruff check"

# Ruff format
uv run ruff format .
echo -e "  ${GREEN}✓${NC} ruff format"

# Shell scripts
if ls scripts/*.sh &>/dev/null; then
    uv run -m beautysh scripts/*.sh tidy.sh
    echo -e "  ${GREEN}✓${NC} beautysh"
fi

echo -e "\n  ${GREEN}✓${NC} All tidy"
