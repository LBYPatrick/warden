#!/bin/bash
set -euo pipefail

# Color support — disabled by WARDEN_NO_COLOR or NO_COLOR
_no_color=false
case "${WARDEN_NO_COLOR:-${NO_COLOR:-}}" in
    1 | true | yes) _no_color=true ;;
esac
if ! [ -t 1 ]; then _no_color=true; fi

if $_no_color; then
    GREEN='' RED='' BLUE='' NC='' BOLD='' DIM=''
else
    GREEN=$'\033[0;32m' RED=$'\033[0;31m'
    BLUE=$'\033[0;34m' NC=$'\033[0m'
    BOLD=$'\033[1m' DIM=$'\033[2m'
fi

IS_TTY=false
[ -t 1 ] && ! $_no_color && IS_TTY=true

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

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
            cat "$log_file"
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

# Lazy-check formatter installation
if [[ "${1:-}" != "--skip-check" ]]; then
    if ! uv run ruff --version &>/dev/null; then
        echo "  ${BLUE}◐${NC} Installing formatters..."
        bash scripts/install-formatter.sh
    fi
fi

echo ""
echo "${BOLD}===========================================${NC}"
echo "${BOLD}            Code Formatting${NC}"
echo "${BOLD}===========================================${NC}"
echo ""

run_with_progress "ruff check" "$STATUS_DIR/ruff-check.log" \
    uv run ruff check --select I,F401 --fix .

run_with_progress "ruff format" "$STATUS_DIR/ruff-format.log" \
    uv run ruff format .

if ls scripts/*.sh &>/dev/null; then
    run_with_progress "beautysh" "$STATUS_DIR/beautysh.log" \
        uv run -m beautysh scripts/*.sh tidy.sh
fi

echo ""
echo "${BOLD}===========================================${NC}"
echo ""
echo "${GREEN}${BOLD}All tidy!${NC}"
