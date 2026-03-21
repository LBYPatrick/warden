#!/bin/bash
# Warden — One-line installer
# Usage: curl -fsSL https://raw.githubusercontent.com/LBYPatrick/warden/main/scripts/remote-install.sh | bash
set -euo pipefail

WARDEN_DIR="${WARDEN_DIR:-$HOME/.warden/repo}"
REPO_URL="https://github.com/LBYPatrick/warden.git"

# Color support — disabled by WARDEN_NO_COLOR or NO_COLOR
_no_color=false
case "${WARDEN_NO_COLOR:-${NO_COLOR:-}}" in
    1 | true | yes) _no_color=true ;;
esac
if ! [ -t 1 ]; then _no_color=true; fi

if $_no_color; then
    GREEN='' RED='' YELLOW='' CYAN='' NC='' BOLD='' DIM=''
else
    GREEN=$'\033[0;32m' RED=$'\033[0;31m' YELLOW=$'\033[0;33m'
    CYAN=$'\033[0;36m' NC=$'\033[0m'
    BOLD=$'\033[1m' DIM=$'\033[2m'
fi

# China mirror support
case "${WARDEN_USE_CN:-}" in
    1 | true | yes)
        REPO_URL="https://ghp.ci/https://github.com/LBYPatrick/warden.git"
        ;;
esac

echo ""
echo "${BOLD}===========================================${NC}"
echo "${BOLD}     Warden Remote Installation${NC}"
echo "${BOLD}===========================================${NC}"
echo ""

# On Apple Silicon, install Rosetta 2 silently
if [[ "$(uname -s)" == "Darwin" ]] && [[ "$(uname -m)" == "arm64" ]]; then
    if ! /usr/bin/pgrep -q oahd 2>/dev/null; then
        echo "  ${CYAN}▶${NC} Installing Rosetta 2..."
        /usr/sbin/softwareupdate --install-rosetta --agree-to-license 2>/dev/null
        echo "  ${GREEN}✓${NC} Rosetta 2 installed"
    else
        echo "  ${GREEN}✓${NC} Rosetta 2 already installed"
    fi
fi

# On macOS, ensure Xcode Command Line Tools are installed (provides git + make)
if [[ "$(uname -s)" == "Darwin" ]]; then
    if ! xcode-select -p &>/dev/null; then
        echo "  ${CYAN}▶${NC} Installing Xcode Command Line Tools (provides git, make)..."
        echo "  ${DIM}A system dialog may appear — click Install and wait for it to finish.${NC}"
        xcode-select --install 2>/dev/null || true
        # Wait for the installation to complete
        until xcode-select -p &>/dev/null; do
            sleep 5
        done
        echo "  ${GREEN}✓${NC} Xcode Command Line Tools installed"
    else
        echo "  ${GREEN}✓${NC} Xcode Command Line Tools already installed"
    fi
fi

# Check prerequisites
for cmd in git make; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "  ${RED}✗${NC} Required command not found: ${BOLD}$cmd${NC}"
        exit 1
    fi
done
echo "  ${GREEN}✓${NC} Prerequisites OK (git, make)"

# Clone or update
if [ -d "$WARDEN_DIR/.git" ]; then
    echo "  ${CYAN}▶${NC} Existing installation found at ${BOLD}$WARDEN_DIR${NC}"
    echo "  ${CYAN}▶${NC} Pulling latest changes..."
    git -C "$WARDEN_DIR" pull --ff-only || {
        echo "  ${YELLOW}⚠${NC} Pull failed — continuing with existing version"
    }
else
    if [ -e "$WARDEN_DIR" ]; then
        echo "  ${RED}✗${NC} ${BOLD}$WARDEN_DIR${NC} exists but is not a git repo"
        echo "  ${DIM}Set WARDEN_DIR to change the install location${NC}"
        exit 1
    fi
    echo "  ${CYAN}▶${NC} Cloning into ${BOLD}$WARDEN_DIR${NC}..."
    mkdir -p "$(dirname "$WARDEN_DIR")"
    git clone "$REPO_URL" "$WARDEN_DIR"
    echo "  ${GREEN}✓${NC} Cloned"
fi
echo ""

# Run make install
cd "$WARDEN_DIR"
make install

echo ""
echo "  ${DIM}Install location: $WARDEN_DIR${NC}"
echo "  ${DIM}To uninstall:     cd $WARDEN_DIR && make uninstall${NC}"
echo ""
