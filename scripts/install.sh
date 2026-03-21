#!/bin/bash
set -euo pipefail

# Color support — disabled by WARDEN_NO_COLOR or NO_COLOR
_no_color=false
case "${WARDEN_NO_COLOR:-${NO_COLOR:-}}" in
    1 | true | yes) _no_color=true ;;
esac
if ! [ -t 1 ]; then _no_color=true; fi

if $_no_color; then
    GREEN='' RED='' YELLOW='' BLUE='' CYAN='' NC='' BOLD='' DIM=''
else
    GREEN=$'\033[0;32m' RED=$'\033[0;31m' YELLOW=$'\033[0;33m'
    BLUE=$'\033[0;34m' CYAN=$'\033[0;36m' NC=$'\033[0m'
    BOLD=$'\033[1m' DIM=$'\033[2m'
fi

IS_TTY=false
[ -t 1 ] && ! $_no_color && IS_TTY=true

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
        echo "  ${BLUE}▶${NC} $description..."
        if "${cmd[@]}" > "$log_file" 2>&1; then
            local end_time=$(date +%s)
            local elapsed=$((end_time - start_time))
            echo "  ${GREEN}✓${NC} $description ${DIM}($(format_elapsed $elapsed))${NC}"
            return 0
        else
            local end_time=$(date +%s)
            local elapsed=$((end_time - start_time))
            echo "  ${RED}✗${NC} $description FAILED ${DIM}($(format_elapsed $elapsed))${NC}"
            cat "$log_file"
            return 1
        fi
    fi
}

echo ""
echo "${BOLD}===========================================${NC}"
echo "${BOLD}         Warden Installation${NC}"
echo "${BOLD}===========================================${NC}"
echo ""

# China mirror support
USE_CN=false
case "${WARDEN_USE_CN:-}" in
    1 | true | yes)
        USE_CN=true
        export UV_INDEX_URL="${UV_INDEX_URL:-https://mirrors.aliyun.com/pypi/simple/}"
        echo "  ${CYAN}▶${NC} China mirror mode enabled"
        ;;
esac

# Step 1: Dependencies
echo "${BOLD}[1/5] Dependencies${NC}"

# Auto-install Homebrew on macOS
if [[ "$(uname -s)" == "Darwin" ]] && ! command -v brew &>/dev/null; then
    if $USE_CN; then
        run_with_progress "Installing Homebrew (CN mirror)" "$STATUS_DIR/brew.log" \
            bash -c 'export HOMEBREW_BREW_GIT_REMOTE="https://mirrors.ustc.edu.cn/brew.git" && export HOMEBREW_CORE_GIT_REMOTE="https://mirrors.ustc.edu.cn/homebrew-core.git" && /bin/bash -c "$(curl -fsSL https://ghp.ci/https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    else
        run_with_progress "Installing Homebrew" "$STATUS_DIR/brew.log" \
            bash -c 'NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    fi
    # Add brew to PATH for the rest of this script
    if [ -x /opt/homebrew/bin/brew ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [ -x /usr/local/bin/brew ]; then
        eval "$(/usr/local/bin/brew shellenv)"
    fi
elif [[ "$(uname -s)" == "Darwin" ]]; then
    echo "  ${GREEN}✓${NC} Homebrew already installed"
fi

if ! command -v uv &>/dev/null; then
    if $USE_CN; then
        run_with_progress "Installing uv (CN mirror)" "$STATUS_DIR/uv.log" \
            bash -c 'curl -LsSf https://ghp.ci/https://astral.sh/uv/install.sh | sh'
    else
        run_with_progress "Installing uv" "$STATUS_DIR/uv.log" \
            bash -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'
    fi
    # uv installs to ~/.local/bin by default — add to PATH for this session
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    if ! command -v uv &>/dev/null; then
        echo "  ${RED}✗${NC} uv not found after install — check ~/.local/bin or ~/.cargo/bin"
        exit 1
    fi
else
    echo "  ${GREEN}✓${NC} uv already installed"
fi

cd "$PROJECT_ROOT"
run_with_progress "Syncing Python dependencies" "$STATUS_DIR/sync.log" \
    uv sync
echo ""

# Step 2: Binary
echo "${BOLD}[2/5] Binary${NC}"

chmod +x "$PROJECT_ROOT/bin/warden"
echo "  ${GREEN}✓${NC} bin/warden marked executable"

BIN_DIR="${HOME}/.local/bin"
mkdir -p "$BIN_DIR"
ln -sf "$PROJECT_ROOT/bin/warden" "$BIN_DIR/warden"
echo "  ${GREEN}✓${NC} Symlinked to $BIN_DIR/warden"

if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo "  ${YELLOW}⚠${NC} $BIN_DIR is not in your PATH. Add it to your shell profile:"
    echo "    ${CYAN}export PATH=\"\$HOME/.local/bin:\$PATH\"${NC}"
fi
echo ""

# Step 3: Man page
echo "${BOLD}[3/5] Man page${NC}"

MAN_DIR="${HOME}/.local/share/man/man1"
MAN_SRC="$PROJECT_ROOT/man/warden.1"
if [ -f "$MAN_SRC" ]; then
    mkdir -p "$MAN_DIR"
    cp "$MAN_SRC" "$MAN_DIR/warden.1"
    echo "  ${GREEN}✓${NC} Man page installed to $MAN_DIR/warden.1"
else
    echo "  ${YELLOW}⊘${NC} Man page source not found — skipping"
fi
echo ""

# Step 4: Shell completions
echo "${BOLD}[4/5] Shell completions${NC}"

COMP_DIR="$PROJECT_ROOT/completions"
SHELL_NAME="$(basename "$SHELL")"

if [[ "$SHELL_NAME" == "zsh" ]]; then
    ZSH_COMP_DIR="${HOME}/.zsh/completions"
    mkdir -p "$ZSH_COMP_DIR"
    ln -sf "$COMP_DIR/warden.zsh" "$ZSH_COMP_DIR/_warden"
    echo "  ${GREEN}✓${NC} Zsh completions installed to $ZSH_COMP_DIR/_warden"
    if ! grep -q 'fpath.*\.zsh/completions' "${HOME}/.zshrc" 2>/dev/null; then
        echo "  ${YELLOW}⚠${NC} Add this to your ~/.zshrc if not already present:"
        echo "    ${CYAN}fpath=(~/.zsh/completions \$fpath)${NC}"
        echo "    ${CYAN}autoload -Uz compinit && compinit${NC}"
    fi
elif [[ "$SHELL_NAME" == "bash" ]]; then
    BASH_COMP_DIR="${HOME}/.local/share/bash-completion/completions"
    mkdir -p "$BASH_COMP_DIR"
    ln -sf "$COMP_DIR/warden.bash" "$BASH_COMP_DIR/warden"
    echo "  ${GREEN}✓${NC} Bash completions installed to $BASH_COMP_DIR/warden"
else
    echo "  ${YELLOW}⊘${NC} Unknown shell: $SHELL_NAME (skipping completions)"
fi
echo ""

# Step 5: Verify
echo "${BOLD}[5/5] Verification${NC}"

run_with_progress "Running smoke test" "$STATUS_DIR/smoke.log" \
    uv run python -m warden --help
echo ""

# Summary
echo "${BOLD}===========================================${NC}"
echo "${BOLD}       Installation Summary${NC}"
echo "${BOLD}===========================================${NC}"
echo ""
echo "  ${GREEN}✓${NC} Dependencies"
echo "  ${GREEN}✓${NC} Binary"
echo "  ${GREEN}✓${NC} Man page"
echo "  ${GREEN}✓${NC} Completions"
echo "  ${GREEN}✓${NC} Verification"
echo ""
echo "${BOLD}===========================================${NC}"
echo ""
echo "${GREEN}${BOLD}Installation complete!${NC}"
