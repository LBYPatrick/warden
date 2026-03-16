"""China network mirror support for Warden.

When USE_CN=1|true|yes is set, URLs and environment variables are
rewritten to use mirrors accessible from mainland China.
"""

import os

# Environment variables injected into tool install scripts under CN mode.
CN_ENV: dict[str, str] = {
    "RUSTUP_DIST_SERVER": "https://rsproxy.cn",
    "RUSTUP_UPDATE_ROOT": "https://rsproxy.cn/rustup",
    "FNM_NODE_DIST_MIRROR": "https://npmmirror.com/mirrors/node",
    "NPM_CONFIG_REGISTRY": "https://registry.npmmirror.com",
}

# URL rewrites applied to shell commands under CN mode.
# Order matters — more specific prefixes first.
_CN_REWRITES: list[tuple[str, str]] = [
    ("https://sh.rustup.rs", "https://rsproxy.cn/rustup-init.sh"),
    ("https://fnm.vercel.app/install", "https://ghp.ci/https://fnm.vercel.app/install"),
    ("https://get.pnpm.io/install.sh", "https://ghp.ci/https://get.pnpm.io/install.sh"),
    ("https://sdk.cloud.google.com", "https://ghp.ci/https://sdk.cloud.google.com"),
    ("https://github.com/", "https://ghp.ci/https://github.com/"),
]

# Homebrew mirrors for CN mode.
HOMEBREW_CN_ENV: dict[str, str] = {
    "HOMEBREW_BREW_GIT_REMOTE": "https://mirrors.ustc.edu.cn/brew.git",
    "HOMEBREW_CORE_GIT_REMOTE": "https://mirrors.ustc.edu.cn/homebrew-core.git",
    "HOMEBREW_BOTTLE_DOMAIN": "https://mirrors.ustc.edu.cn/homebrew-bottles",
    "HOMEBREW_API_DOMAIN": "https://mirrors.ustc.edu.cn/homebrew-bottles/api",
}

# uv / pip index mirror for CN mode.
UV_CN_ENV: dict[str, str] = {
    "UV_INDEX_URL": "https://mirrors.aliyun.com/pypi/simple/",
}


def detect_use_cn() -> bool:
    """Check if WARDEN_USE_CN environment variable is set to a truthy value."""
    val = os.environ.get("WARDEN_USE_CN", "").strip().lower()
    return val in ("1", "true", "yes")


def apply_cn_rewrites(cmd: str) -> str:
    """Rewrite URLs in a shell command for China mirrors."""
    for original, mirror in _CN_REWRITES:
        cmd = cmd.replace(original, mirror)
    return cmd
