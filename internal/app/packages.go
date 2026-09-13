package app

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
	"time"
)

func runtimeOS() string { return runtime.GOOS }

type manager struct {
	name, key, section, platform string
	scan, install                []string
}

var managers = []manager{
	{"brew", "brew", "formulae", "", []string{"brew", "list", "--formula", "-1"}, []string{"brew", "install"}},
	{"cask", "brew", "casks", "", []string{"brew", "list", "--cask", "-1"}, []string{"brew", "install", "--cask"}},
	{"mas", "mas", "apps", "darwin", []string{"mas", "list"}, []string{"mas", "install"}},
	{"apt", "apt", "packages", "linux", []string{"apt-mark", "showmanual"}, []string{"sudo", "apt-get", "install", "-y"}},
	{"dnf", "dnf", "packages", "linux", []string{"dnf", "repoquery", "--userinstalled", "--qf", "%{name}"}, []string{"sudo", "dnf", "install", "-y"}},
	{"pacman", "pacman", "packages", "linux", []string{"pacman", "-Qqe"}, []string{"sudo", "pacman", "-S", "--noconfirm"}},
	{"apk", "apk", "packages", "linux", []string{"apk", "list", "--installed"}, []string{"sudo", "apk", "add"}},
	{"snap", "snap", "packages", "linux", []string{"snap", "list"}, []string{"sudo", "snap", "install"}},
	{"flatpak", "flatpak", "packages", "linux", []string{"flatpak", "list", "--app", "--columns=application"}, []string{"flatpak", "install", "-y"}},
	{"cargo", "cargo", "packages", "", []string{"cargo", "install", "--list"}, []string{"cargo", "install"}},
	{"npm", "npm", "packages", "", []string{"npm", "list", "-g", "--depth=0", "--json"}, []string{"npm", "install", "-g"}},
	{"pnpm", "pnpm", "packages", "", []string{"pnpm", "list", "-g", "--depth=0", "--json"}, []string{"pnpm", "add", "-g"}},
	{"pipx", "pipx", "packages", "", []string{"pipx", "list", "--short"}, []string{"pipx", "install"}},
}
var toolBinaries = map[string]string{"xcode": "xcode-select", "rustup": "rustup", "conda": "conda", "node": "node", "pnpm": "pnpm", "flutter": "flutter", "gcloud": "gcloud", "aws": "aws", "wrangler": "wrangler", "android-tools": "adb"}

func parsePackages(name, s string) ([]string, error) {
	result := []string{}
	if name == "npm" || name == "pnpm" {
		var data struct {
			Dependencies map[string]any `json:"dependencies"`
		}
		if strings.HasPrefix(strings.TrimSpace(s), "[") {
			var entries []struct {
				Dependencies map[string]any `json:"dependencies"`
			}
			if e := json.Unmarshal([]byte(s), &entries); e != nil {
				return nil, e
			}
			if len(entries) > 0 {
				data.Dependencies = entries[0].Dependencies
			}
		} else {
			if e := json.Unmarshal([]byte(s), &data); e != nil {
				return nil, e
			}
		}
		for p := range data.Dependencies {
			if name != "npm" || p != "npm" {
				result = append(result, p)
			}
		}
		return union(result, nil), nil
	}
	for i, line := range strings.Split(s, "\n") {
		f := strings.Fields(line)
		if len(f) == 0 {
			continue
		}
		v := strings.TrimSpace(line)
		switch name {
		case "mas":
			if len(f) < 2 {
				continue
			}
			label := strings.TrimSpace(strings.TrimPrefix(strings.TrimSpace(line), f[0]))
			if idx := strings.LastIndex(label, "("); idx >= 0 {
				label = strings.TrimSpace(label[:idx])
			}
			v = f[0] + ":" + label
		case "cargo":
			if line[0] == ' ' || line[0] == '\t' {
				continue
			}
			v = strings.TrimSuffix(f[0], ":")
		case "apk":
			v = regexp.MustCompile(`-[0-9].*$`).ReplaceAllString(f[0], "")
		case "snap":
			if i == 0 || strings.HasPrefix(f[0], "core") {
				continue
			}
			v = f[0]
		case "pipx":
			v = f[0]
		}
		result = append(result, v)
	}
	return union(result, nil), nil
}
func (a *App) scanManager(m manager) ([]string, error) {
	s, e := a.Run(m.scan)
	if m.name == "apt" && (e != nil || strings.TrimSpace(s) == "") {
		s, e = a.Run([]string{"dpkg", "--get-selections"})
		if e == nil {
			var pkgs []string
			for _, line := range strings.Split(s, "\n") {
				f := strings.Fields(line)
				if len(f) > 1 && f[1] == "install" {
					pkgs = append(pkgs, strings.Split(f[0], ":")[0])
				}
			}
			return union(pkgs, nil), nil
		}
	}
	if e != nil {
		return nil, e
	}
	return parsePackages(m.name, s)
}

// Scan replaces installed package snapshots, failing rather than erasing data on scan errors.
func (a *App) Scan(c Config) (Config, error) {
	out := emptyConfig()
	out.Identities = c.Identities
	a.Header("Scan packages")
	for _, m := range managers {
		if m.platform != "" && m.platform != a.Platform {
			continue
		}
		if _, e := a.LookPath(managerBinary(m)); e != nil {
			continue
		}
		p, e := a.scanManager(m)
		if e != nil {
			// Homebrew's cask inventory is optional on Linux.
			if m.name == "cask" && a.Platform == "linux" {
				continue
			}
			return c, e
		}
		if len(p) > 0 {
			if out.Packages[m.key] == nil {
				out.Packages[m.key] = map[string][]string{}
			}
			out.Packages[m.key][m.section] = p
		}
		a.Row(m.name, fmt.Sprintf("%d packages", len(p)))
	}
	for _, slug := range sortedKeys(toolBinaries) {
		if a.toolInstalled(slug) {
			out.Tools = append(out.Tools, slug)
		}
	}
	return out, nil
}
func addPackage(c *Config, m manager, p string) {
	if c.Packages[m.key] == nil {
		c.Packages[m.key] = map[string][]string{}
	}
	c.Packages[m.key][m.section] = union(c.Packages[m.key][m.section], []string{p})
}
func packageID(m, p string) string {
	if m == "mas" {
		return strings.SplitN(p, ":", 2)[0]
	}
	return p
}

// Install installs explicit manager:package specs and optionally saves successful entries.
func (a *App) Install(specs []string, force, save, anyPlatform bool) error {
	grouped := map[string][]string{}
	registry := map[string]manager{}
	for _, m := range managers {
		registry[m.name] = m
	}
	for _, s := range specs {
		mgr, p, ok := strings.Cut(s, ":")
		mgr = strings.ToLower(mgr)
		if !ok || p == "" || strings.HasPrefix(p, "-") || strings.ContainsAny(p, "\n\r\x00") {
			return fmt.Errorf("invalid package spec %q", s)
		}
		m, known := registry[mgr]
		if !known && mgr != "tool" {
			return fmt.Errorf("unknown manager %q", mgr)
		}
		if mgr == "tool" {
			if _, ok := toolScripts[p]; !ok {
				return fmt.Errorf("unknown developer tool %q", p)
			}
			if p == "xcode" && a.Platform != "darwin" {
				return fmt.Errorf("xcode requires macOS")
			}
		} else if !anyPlatform && m.platform != "" && m.platform != a.Platform {
			return fmt.Errorf("%s is unavailable on %s (use --any to override)", mgr, a.Platform)
		}
		grouped[mgr] = union(grouped[mgr], []string{p})
	}
	c := emptyConfig()
	var e error
	if save {
		c, e = a.Load()
		if e != nil {
			return e
		}
	}
	a.Header("Install packages")
	failed := []string{}
	installed, skipped := 0, 0
	for _, mgr := range sortedKeys(grouped) {
		m := registry[mgr]
		current := []string{}
		if a.Platform == "darwin" && (mgr == "brew" || mgr == "cask" || mgr == "mas" || mgr == "pipx") {
			if _, err := a.LookPath("brew"); err != nil {
				if err = a.ensureHomebrew(); err != nil {
					for _, p := range grouped[mgr] {
						failed = append(failed, mgr+":"+p)
					}
					fmt.Fprintln(a.Err, err)
					continue
				}
			}
		}
		if mgr != "tool" && !force {
			if _, err := a.LookPath(managerBinary(m)); err == nil {
				current, e = a.scanManager(m)
				if e != nil {
					for _, p := range grouped[mgr] {
						failed = append(failed, mgr+":"+p)
					}
					fmt.Fprintln(a.Err, e)
					continue
				}
			}
		}
		todo := []string{}
		for _, p := range grouped[mgr] {
			present := false
			for _, v := range current {
				if packageID(mgr, v) == packageID(mgr, p) {
					present = true
				}
			}
			if mgr == "tool" && !force {
				present = a.toolInstalled(p)
			}
			if present && !force {
				skipped++
				a.Row("Already installed", mgr+":"+p)
				if save {
					if mgr == "tool" {
						c.Tools = union(c.Tools, []string{p})
					} else {
						addPackage(&c, m, p)
					}
				}
				continue
			}
			todo = append(todo, p)
		}
		if mgr != "tool" && len(todo) > 0 {
			if _, err := a.LookPath(managerBinary(m)); err != nil {
				hint := managerBootstrap(mgr, a.Platform)
				if len(hint) > 0 {
					if a.Dry {
						a.Row("Would set up", mgr)
					} else if _, err = a.Run(hint); err != nil {
						for _, p := range todo {
							failed = append(failed, mgr+":"+p)
						}
						fmt.Fprintln(a.Err, err)
						continue
					}
				}
			}
		}
		if mgr == "apt" && len(todo) > 0 && !a.Dry {
			if _, err := a.Run([]string{"sudo", "apt-get", "update", "-qq"}); err != nil {
				a.Row("Index refresh", "Failed; using the existing APT cache")
			}
			available, err := a.Run([]string{"apt-cache", "pkgnames"})
			if err == nil && strings.TrimSpace(available) != "" {
				set := map[string]bool{}
				for _, p := range strings.Fields(available) {
					set[p] = true
				}
				filtered := []string{}
				for _, p := range todo {
					if set[p] {
						filtered = append(filtered, p)
					} else {
						failed = append(failed, "apt:"+p)
						a.Row("Unavailable", p)
					}
				}
				todo = filtered
			} else {
				a.Row("APT cache", "Unavailable; trying the requested packages")
			}
		}
		if (mgr == "apt" || mgr == "brew" || mgr == "cask") && len(todo) > 0 && !a.Dry {
			command := installCommand(m, force)
			bulk := append(append([]string{}, command...), todo...)
			var err error
			if mgr == "apt" {
				_, err = a.Run(bulk)
			} else {
				err = a.runLive(bulk, 20*time.Minute)
			}
			if err == nil {
				installed += len(todo)
				if save {
					for _, p := range todo {
						addPackage(&c, m, p)
					}
				}
				continue
			}
			a.Row("Bulk install", "Failed; retrying each package")
		}
		for _, p := range todo {
			var args []string
			if mgr == "tool" {
				script := toolScripts[p]
				if truthy(os.Getenv("WARDEN_USE_CN")) {
					script = mirrorScript(script)
				}
				args = []string{"bash", "-euo", "pipefail", "-c", script}
			} else {
				args = append(installCommand(m, force), packageID(mgr, p))
			}
			if a.Dry {
				a.Row("Would install", mgr+":"+p)
				continue
			}
			a.Row("Installing", mgr+":"+p)
			if mgr == "brew" || mgr == "cask" {
				e = a.runLive(args, 10*time.Minute)
			} else {
				_, e = a.Run(args)
			}
			if e != nil {
				failed = append(failed, mgr+":"+p)
				fmt.Fprintln(a.Err, e)
				continue
			}
			installed++
			if save {
				if mgr == "tool" {
					c.Tools = union(c.Tools, []string{p})
				} else {
					addPackage(&c, m, p)
				}
			}
		}
	}
	if save && !a.Dry {
		if e = a.Save(c); e != nil {
			return e
		}
	}
	a.Row("Result", fmt.Sprintf("%d installed · %d already present · %d failed", installed, skipped, len(failed)))
	if len(failed) > 0 {
		return fmt.Errorf("installation failed: %s", strings.Join(failed, ", "))
	}
	if a.Dry {
		a.Success("Preview complete; no changes made")
	} else {
		a.Success("Packages ready")
	}
	return nil
}

// Apply installs the configured packages and tools.
func (a *App) Apply(force bool) error {
	c, e := a.Load()
	if e != nil {
		return e
	}
	specs := []string{}
	for _, m := range managers {
		if m.platform != "" && m.platform != a.Platform {
			continue
		}
		for _, p := range c.Packages[m.key][m.section] {
			specs = append(specs, m.name+":"+p)
		}
	}
	for _, t := range c.Tools {
		if t == "xcode" && a.Platform != "darwin" {
			continue
		}
		specs = append(specs, "tool:"+t)
	}
	return a.Install(specs, force, false, false)
}

// Deps emits the Homebrew dependency graph as machine-readable JSON.
func (a *App) Deps(output string) error {
	s, e := a.Run([]string{"brew", "deps", "--installed", "--for-each"})
	if e != nil {
		return e
	}
	leaves, e := a.Run([]string{"brew", "leaves"})
	if e != nil {
		fmt.Fprintln(a.Err, "Could not read brew leaves; exporting dependencies without leaf classifications")
		leaves = ""
	}
	casks, e := a.scanManager(managers[1])
	if e != nil {
		fmt.Fprintln(a.Err, "Could not read brew casks; exporting formula dependencies")
		casks = []string{}
	}
	formulae := map[string]any{}
	leafList := []string{}
	for _, line := range strings.Split(s, "\n") {
		name, deps, ok := strings.Cut(line, ":")
		if !ok {
			continue
		}
		name = strings.TrimSpace(name)
		leaf := contains(strings.Fields(leaves), name)
		if leaf {
			leafList = append(leafList, name)
		}
		formulae[name] = map[string]any{"dependencies": union(strings.Fields(deps), nil), "is_leaf": leaf}
	}
	b := encode(map[string]any{"formulae": formulae, "casks": casks, "leaves": union(leafList, nil), "summary": map[string]int{"total_formulae": len(formulae), "total_casks": len(casks), "leaves": len(leafList), "dependencies_only": len(formulae) - len(leafList)}})
	if output != "" {
		if a.Dry {
			a.Row("Would write", output)
			return nil
		}
		return writeAtomic(a.Expand(output), b, 0600)
	}
	_, e = a.Out.Write(b)
	return e
}

func managerBootstrap(name, platform string) []string {
	if platform == "darwin" {
		switch name {
		case "mas", "pipx":
			return []string{"brew", "install", name}
		}
	} else if platform == "linux" {
		switch name {
		case "snap":
			return []string{"sudo", "apt-get", "install", "-y", "snapd"}
		case "flatpak", "pipx":
			return []string{"sudo", "apt-get", "install", "-y", name}
		}
	}
	return nil
}

func managerBinary(m manager) string {
	if m.name == "apt" {
		return "apt-get"
	}
	return m.scan[0]
}
func installCommand(m manager, force bool) []string {
	args := append([]string{}, m.install...)
	if force {
		switch m.name {
		case "brew", "cask":
			args[1] = "reinstall"
		case "apt":
			args = append(args, "--reinstall")
		case "cargo", "pipx":
			args = append(args, "--force")
		}
	}
	return args
}
func (a *App) toolInstalled(slug string) bool {
	if slug == "xcode" {
		if a.Platform != "darwin" {
			return false
		}
		_, err := a.Run([]string{"xcode-select", "-p"})
		return err == nil
	}
	p, err := a.LookPath(toolBinaries[slug])
	if err != nil {
		return false
	}
	if resolved, e := filepath.EvalSymlinks(p); e == nil {
		p = resolved
	}
	return slug == "wrangler" || (!strings.Contains(p, "/Cellar/") && !strings.Contains(p, "/Caskroom/"))
}

func (a *App) ensureHomebrew() error {
	if _, err := a.LookPath("brew"); err == nil {
		return nil
	}
	if a.Platform != "darwin" {
		return fmt.Errorf("Homebrew is required; install it before continuing")
	}
	if a.Dry {
		a.Row("Would set up", "Homebrew")
		return nil
	}
	script := `warden_tmp="$(mktemp -d)"
trap 'rm -rf "$warden_tmp"' EXIT
curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh -o "$warden_tmp/install.sh"
NONINTERACTIVE=1 /bin/bash "$warden_tmp/install.sh"`
	if truthy(os.Getenv("WARDEN_USE_CN")) {
		script = strings.ReplaceAll(script, "https://raw.githubusercontent.com/", "https://ghp.ci/https://raw.githubusercontent.com/")
	}
	a.Row("Setting up", "Homebrew")
	_, err := a.Run([]string{"bash", "-euo", "pipefail", "-c", script})
	return err
}
