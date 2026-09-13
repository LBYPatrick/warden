package app

// Fixed recipes are executed with bash -euo pipefail. Package names never enter shell code.
var toolScripts = map[string]string{
	"xcode": `xcode-select -p &>/dev/null && exit 0
xcode-select --install
until xcode-select -p &>/dev/null; do sleep 5; done`,
	"rustup": `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y`,
	"conda": `warden_tmp="$(mktemp -d)"
trap 'rm -rf "$warden_tmp"' EXIT
curl -fsSL -o "$warden_tmp/miniforge.sh" "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"
bash "$warden_tmp/miniforge.sh" -b`,
	"node": `curl -fsSL https://fnm.vercel.app/install | bash -s -- --skip-shell
export PATH="$HOME/.local/share/fnm:$HOME/Library/Application Support/fnm:$PATH"
eval "$(fnm env)"
fnm install --lts`,
	"pnpm": `curl -fsSL https://get.pnpm.io/install.sh | sh -`,
	"flutter": `if [[ -d "$HOME/.flutter/.git" ]]; then
 git -C "$HOME/.flutter" pull --ff-only
else
 git clone https://github.com/flutter/flutter.git -b stable "$HOME/.flutter"
fi
printf 'Add %s/.flutter/bin to your PATH\n' "$HOME"`,
	"gcloud": `curl -fsSL https://sdk.cloud.google.com | bash -s -- --disable-prompts`,
	"aws": `warden_tmp="$(mktemp -d)"
trap 'rm -rf "$warden_tmp"' EXIT
if [[ "$(uname)" == Darwin ]]; then
 curl -fsSL https://awscli.amazonaws.com/AWSCLIV2.pkg -o "$warden_tmp/aws.pkg"
 sudo installer -pkg "$warden_tmp/aws.pkg" -target /
else
 curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-$(uname -m).zip" -o "$warden_tmp/aws.zip"
 unzip -oq "$warden_tmp/aws.zip" -d "$warden_tmp"
 sudo "$warden_tmp/aws/install" --update
fi`,
	"wrangler": `npm install -g wrangler`,
	"android-tools": `if [[ "$(uname)" == Darwin ]]; then
 brew install android-platform-tools
else
 warden_tmp="$(mktemp -d)"
 trap 'rm -rf "$warden_tmp"' EXIT
 curl -fsSL https://dl.google.com/android/repository/platform-tools-latest-linux.zip -o "$warden_tmp/platform-tools.zip"
 sudo unzip -oq "$warden_tmp/platform-tools.zip" -d /opt
 sudo ln -sf /opt/platform-tools/adb /usr/local/bin/adb
 sudo ln -sf /opt/platform-tools/fastboot /usr/local/bin/fastboot
fi`,
}
