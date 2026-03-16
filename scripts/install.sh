#!/bin/bash
set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'
DIM='\033[2m'

if [ -t 1 ]; then IS_TTY=true; else IS_TTY=false; fi

SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SOURCE" ]; do
    DIR="$(cd "$(dirname "$SOURCE")" && pwd)"
    SOURCE="$(readlink "$SOURCE")"
    [[ "$SOURCE" != /* ]] && SOURCE="$DIR/$SOURCE"
done
SCRIPT_DIR="$(cd "$(dirname "$SOURCE")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

STATUS_DIR=$(mktemp -d)
trap "rm -rf $STATUS_DIR" EXIT

format_elapsed() {
    local seconds=$1
    if [ "$seconds" -lt 60 ]; then
        echo "${seconds}s"
    else
        local mins=$((seconds / 60))
        local secs=$((seconds % 60))
        echo "${mins}m ${secs}s"
    fi
}

run_with_progress() {
    local description="$1"
    local log_file="$2"
    shift 2
    local cmd=("$@")
    local start_time=$(date +%s)

    if $IS_TTY; then
        printf "  ${BLUE}◐${NC} %s..." "$description"
        if "${cmd[@]}" > "$log_file" 2>&1; then
            local end_time=$(date +%s)
            local elapsed=$((end_time - start_time))
            printf "\r\033[K  ${GREEN}✓${NC} %s ${DIM}($(format_elapsed $elapsed))${NC}\n" "$description"
            return 0
        else
            local end_time=$(date +%s)
            local elapsed=$((end_time - start_time))
            printf "\r\033[K  ${RED}✗${NC} %s FAILED ${DIM}($(format_elapsed $elapsed))${NC}\n" "$description"
            echo -e "  ${YELLOW}--- Error log ---${NC}"
            cat "$log_file"
            echo -e "  ${YELLOW}--- End of log ---${NC}"
            return 1
        fi
    else
        echo -e "  ${BLUE}▶${NC} $description..."
        if "${cmd[@]}" > "$log_file" 2>&1; then
            local end_time=$(date +%s)
            local elapsed=$((end_time - start_time))
            echo -e "  ${GREEN}✓${NC} $description ${DIM}($(format_elapsed $elapsed))${NC}"
            return 0
        else
            local end_time=$(date +%s)
            local elapsed=$((end_time - start_time))
            echo -e "  ${RED}✗${NC} $description FAILED ${DIM}($(format_elapsed $elapsed))${NC}"
            cat "$log_file"
            return 1
        fi
    fi
}

echo ""
echo -e "${BOLD}===========================================${NC}"
echo -e "${BOLD}         Warden Installation${NC}"
echo -e "${BOLD}===========================================${NC}"
echo ""

# Step 1: Dependencies
echo -e "${BOLD}[1/4] Dependencies${NC}"

if ! command -v uv &>/dev/null; then
    run_with_progress "Installing uv" "$STATUS_DIR/uv.log" \
        bash -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'
else
    echo -e "  ${GREEN}✓${NC} uv already installed"
fi

cd "$PROJECT_ROOT"
run_with_progress "Syncing Python dependencies" "$STATUS_DIR/sync.log" \
    uv sync
echo ""

# Step 2: Binary
echo -e "${BOLD}[2/4] Binary${NC}"

chmod +x "$PROJECT_ROOT/bin/warden"
echo -e "  ${GREEN}✓${NC} bin/warden marked executable"

if [ -w /usr/local/bin ] || [ "$(id -u)" -eq 0 ]; then
    ln -sf "$PROJECT_ROOT/bin/warden" /usr/local/bin/warden
    echo -e "  ${GREEN}✓${NC} Symlinked to /usr/local/bin/warden"
else
    sudo ln -sf "$PROJECT_ROOT/bin/warden" /usr/local/bin/warden
    echo -e "  ${GREEN}✓${NC} Symlinked to /usr/local/bin/warden (via sudo)"
fi
echo ""

# Step 3: Shell completions
echo -e "${BOLD}[3/4] Shell completions${NC}"

COMP_DIR="$PROJECT_ROOT/completions"
SHELL_NAME="$(basename "$SHELL")"

if [[ "$SHELL_NAME" == "zsh" ]]; then
    ZSH_COMP_DIR="${HOME}/.zsh/completions"
    mkdir -p "$ZSH_COMP_DIR"
    ln -sf "$COMP_DIR/warden.zsh" "$ZSH_COMP_DIR/_warden"
    echo -e "  ${GREEN}✓${NC} Zsh completions installed to $ZSH_COMP_DIR/_warden"
    if ! grep -q 'fpath.*\.zsh/completions' "${HOME}/.zshrc" 2>/dev/null; then
        echo -e "  ${YELLOW}⚠${NC} Add this to your ~/.zshrc if not already present:"
        echo -e "    ${CYAN}fpath=(~/.zsh/completions \$fpath)${NC}"
        echo -e "    ${CYAN}autoload -Uz compinit && compinit${NC}"
    fi
elif [[ "$SHELL_NAME" == "bash" ]]; then
    BASH_COMP_DIR="${HOME}/.local/share/bash-completion/completions"
    mkdir -p "$BASH_COMP_DIR"
    ln -sf "$COMP_DIR/warden.bash" "$BASH_COMP_DIR/warden"
    echo -e "  ${GREEN}✓${NC} Bash completions installed to $BASH_COMP_DIR/warden"
else
    echo -e "  ${YELLOW}⊘${NC} Unknown shell: $SHELL_NAME (skipping completions)"
fi
echo ""

# Step 4: Verify
echo -e "${BOLD}[4/4] Verification${NC}"

run_with_progress "Running smoke test" "$STATUS_DIR/smoke.log" \
    uv run python -m warden --help
echo ""

# Summary
echo -e "${BOLD}===========================================${NC}"
echo -e "${BOLD}       Installation Summary${NC}"
echo -e "${BOLD}===========================================${NC}"
echo ""
echo -e "  ${GREEN}✓${NC} Dependencies"
echo -e "  ${GREEN}✓${NC} Binary"
echo -e "  ${GREEN}✓${NC} Completions"
echo -e "  ${GREEN}✓${NC} Verification"
echo ""
echo -e "${BOLD}===========================================${NC}"
echo ""
echo -e "${GREEN}${BOLD}Installation complete!${NC}"
