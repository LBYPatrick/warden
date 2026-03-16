#!/bin/bash
set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}▶${NC} Installing dev dependencies..."

if ! command -v uv &>/dev/null; then
    echo -e "  ${YELLOW}⚠${NC} uv not found, installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo -e "  ${GREEN}✓${NC} uv installed"
fi

uv sync --group dev
echo -e "  ${GREEN}✓${NC} Dev dependencies installed"
