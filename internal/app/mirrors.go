package app

import (
	"os"
	"strings"
)

func mirrorScript(s string) string {
	return strings.NewReplacer("https://sh.rustup.rs", "https://rsproxy.cn/rustup-init.sh", "https://fnm.vercel.app/install", "https://ghp.ci/https://fnm.vercel.app/install", "https://get.pnpm.io/install.sh", "https://ghp.ci/https://get.pnpm.io/install.sh", "https://sdk.cloud.google.com", "https://ghp.ci/https://sdk.cloud.google.com", "https://github.com/", "https://ghp.ci/https://github.com/").Replace(s)
}
func mirrorEnv() []string {
	env := os.Environ()
	if !truthy(os.Getenv("WARDEN_USE_CN")) {
		return env
	}
	values := map[string]string{"RUSTUP_DIST_SERVER": "https://rsproxy.cn", "RUSTUP_UPDATE_ROOT": "https://rsproxy.cn/rustup", "FNM_NODE_DIST_MIRROR": "https://npmmirror.com/mirrors/node", "NPM_CONFIG_REGISTRY": "https://registry.npmmirror.com", "PIP_INDEX_URL": "https://mirrors.aliyun.com/pypi/simple/", "HOMEBREW_BREW_GIT_REMOTE": "https://mirrors.ustc.edu.cn/brew.git", "HOMEBREW_CORE_GIT_REMOTE": "https://mirrors.ustc.edu.cn/homebrew-core.git", "HOMEBREW_BOTTLE_DOMAIN": "https://mirrors.ustc.edu.cn/homebrew-bottles", "HOMEBREW_API_DOMAIN": "https://mirrors.ustc.edu.cn/homebrew-bottles/api"}
	out := []string{}
	for _, v := range env {
		k, _, _ := strings.Cut(v, "=")
		if _, ok := values[k]; !ok {
			out = append(out, v)
		}
	}
	for _, k := range sortedKeys(values) {
		out = append(out, k+"="+values[k])
	}
	return out
}
