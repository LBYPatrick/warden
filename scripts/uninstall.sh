#!/bin/bash
# Remove only installed launchers and integration files. Preserve keys/configs.
set -euo pipefail
install_dir="${WARDEN_INSTALL_DIR:-$HOME/.local/bin}"
rm -f "$install_dir/warden"
rm -f "$HOME/.local/share/man/man1/warden.1"
rm -f "$HOME/.local/share/bash-completion/completions/warden"
rm -f "$HOME/.zsh/completions/_warden"
printf 'Warden uninstalled. Configuration, keys, and archives were preserved.\n'
