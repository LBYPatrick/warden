package app

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
	"time"
)

func testManager(t *testing.T, name string) manager {
	t.Helper()
	for _, m := range managers {
		if m.name == name {
			return m
		}
	}
	t.Fatalf("missing manager %s", name)
	return manager{}
}
func fakeAvailable(a *App) {
	a.LookPath = func(s string) (string, error) { return "/test/bin/" + s, nil }
}

func TestParityAllManagerScans(t *testing.T) {
	cases := []struct {
		name, raw string
		want      []string
	}{
		{"brew", "wget\ngit\n", []string{"git", "wget"}}, {"cask", "firefox\n", []string{"firefox"}},
		{"mas", " 123 App (Special Edition) (1.2)\n", []string{"123:App (Special Edition)"}},
		{"apt", "git\ncurl\n", []string{"curl", "git"}}, {"dnf", "git\n", []string{"git"}},
		{"pacman", "git\n", []string{"git"}}, {"apk", "git-2.40-r0 x86_64\n", []string{"git"}},
		{"snap", "Name Version\ncore 1\nhello 2\n", []string{"hello"}}, {"flatpak", "org.mozilla.Firefox\n", []string{"org.mozilla.Firefox"}},
		{"cargo", "bat v0.1:\n    bat\nfd-find:\n    fd\n", []string{"bat", "fd-find"}},
		{"npm", `{"dependencies":{"npm":{},"typescript":{}}}`, []string{"typescript"}},
		{"pnpm", `[{"dependencies":{"npm":{},"typescript":{}}}]`, []string{"npm", "typescript"}},
		{"pipx", "black 1.2\nruff 1.0\n", []string{"black", "ruff"}},
	}
	if len(managers) != len(cases) {
		t.Fatal("manager registry changed; update parity cases")
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			a := testApp(t)
			m := testManager(t, tc.name)
			a.Run = func(args []string) (string, error) {
				if !reflect.DeepEqual(args, m.scan) {
					t.Fatalf("scan command %v", args)
				}
				return tc.raw, nil
			}
			got, e := a.scanManager(m)
			if e != nil || !reflect.DeepEqual(got, tc.want) {
				t.Fatalf("got %v %v, want %v", got, e, tc.want)
			}
		})
	}
}

func TestParityAPTEmptyAndMissingManualFallback(t *testing.T) {
	for _, fail := range []bool{false, true} {
		a := testApp(t)
		a.Run = func(args []string) (string, error) {
			if args[0] == "apt-mark" {
				if fail {
					return "", os.ErrNotExist
				}
				return "", nil
			}
			if args[0] != "dpkg" {
				t.Fatal(args)
			}
			return "curl:amd64 install\nremoved deinstall\ngit install", nil
		}
		got, e := a.scanManager(testManager(t, "apt"))
		if e != nil || !reflect.DeepEqual(got, []string{"curl", "git"}) {
			t.Fatalf("%v %v", got, e)
		}
	}
}

func TestParityBrewBulkLiveFallbackAndSave(t *testing.T) {
	for _, name := range []string{"brew", "cask"} {
		t.Run(name, func(t *testing.T) {
			a := testApp(t)
			fakeAvailable(a)
			var calls [][]string
			var limits []time.Duration
			a.Stream = func(args []string, limit time.Duration, out, errOut io.Writer) error {
				calls = append(calls, append([]string{}, args...))
				limits = append(limits, limit)
				fmt.Fprintln(out, "live install output")
				if args[len(args)-1] == "bad" {
					return fmt.Errorf("bad formula")
				}
				return nil
			}
			if e := a.Install([]string{name + ":aaa", name + ":bad"}, true, true, false); e == nil {
				t.Fatal("expected failed package")
			}
			m := testManager(t, name)
			base := installCommand(m, true)
			want := [][]string{append(append([]string{}, base...), "aaa", "bad"), append(append([]string{}, base...), "aaa"), append(append([]string{}, base...), "bad")}
			if !reflect.DeepEqual(calls, want) {
				t.Fatalf("%v", calls)
			}
			if limits[0] != 20*time.Minute {
				t.Fatal(limits)
			}
			c, _ := a.Load()
			if !reflect.DeepEqual(c.Packages[m.key][m.section], []string{"aaa"}) {
				t.Fatal(c)
			}
			if !strings.Contains(a.Out.(*bytes.Buffer).String(), "live install output") {
				t.Fatal("lost live output")
			}
		})
	}
}

func TestParityAPTBulkRefreshAndFallback(t *testing.T) {
	a := testApp(t)
	a.Platform = "linux"
	fakeAvailable(a)
	var calls []string
	a.Run = func(args []string) (string, error) {
		cmd := strings.Join(args, " ")
		calls = append(calls, cmd)
		switch cmd {
		case "sudo apt-get update -qq":
			return "", nil
		case "apt-cache pkgnames":
			return "aaa\nbad\n", nil
		case "sudo apt-get install -y --reinstall aaa":
			return "", nil
		}
		return "", fmt.Errorf("failure")
	}
	if e := a.Install([]string{"apt:aaa", "apt:bad", "apt:unavailable"}, true, true, false); e == nil {
		t.Fatal("expected failure")
	}
	want := []string{"sudo apt-get update -qq", "apt-cache pkgnames", "sudo apt-get install -y --reinstall aaa bad", "sudo apt-get install -y --reinstall aaa", "sudo apt-get install -y --reinstall bad"}
	if !reflect.DeepEqual(calls, want) {
		t.Fatalf("%v", calls)
	}
	c, _ := a.Load()
	if !reflect.DeepEqual(c.Packages["apt"]["packages"], []string{"aaa"}) {
		t.Fatal(c)
	}
}
func TestParityAPTCacheFailureStillInstalls(t *testing.T) {
	a := testApp(t)
	a.Platform = "linux"
	fakeAvailable(a)
	installed := false
	a.Run = func(args []string) (string, error) {
		if strings.Contains(strings.Join(args, " "), "install -y") {
			installed = true
			return "", nil
		}
		return "", fmt.Errorf("cache unavailable")
	}
	if e := a.Install([]string{"apt:curl"}, true, false, false); e != nil || !installed {
		t.Fatalf("%v %v", installed, e)
	}
}

func TestParityAllInstallCommands(t *testing.T) {
	cases := map[string][]string{"mas": {"mas", "install", "123"}, "dnf": {"sudo", "dnf", "install", "-y", "hello"}, "pacman": {"sudo", "pacman", "-S", "--noconfirm", "hello"}, "apk": {"sudo", "apk", "add", "hello"}, "snap": {"sudo", "snap", "install", "hello"}, "flatpak": {"flatpak", "install", "-y", "hello"}, "cargo": {"cargo", "install", "--force", "hello"}, "npm": {"npm", "install", "-g", "hello"}, "pnpm": {"pnpm", "add", "-g", "hello"}, "pipx": {"pipx", "install", "--force", "hello"}}
	for name, want := range cases {
		t.Run(name, func(t *testing.T) {
			a := testApp(t)
			fakeAvailable(a)
			a.Platform = "linux"
			if name == "mas" {
				a.Platform = "darwin"
			}
			var calls [][]string
			a.Run = func(args []string) (string, error) { calls = append(calls, args); return "", nil }
			pkg := "hello"
			if name == "mas" {
				pkg = "123:An App"
			}
			if e := a.Install([]string{name + ":" + pkg}, true, false, false); e != nil {
				t.Fatal(e)
			}
			if len(calls) != 1 || !reflect.DeepEqual(calls[0], want) {
				t.Fatalf("%v != %v", calls, want)
			}
		})
	}
}
func TestParityAllDeveloperToolsAndDetection(t *testing.T) {
	slugs := []string{"android-tools", "aws", "conda", "flutter", "gcloud", "node", "pnpm", "rustup", "wrangler", "xcode"}
	if !reflect.DeepEqual(sortedKeys(toolScripts), slugs) || !reflect.DeepEqual(sortedKeys(toolBinaries), slugs) {
		t.Fatal("tool registry parity")
	}
	for _, slug := range slugs {
		a := testApp(t)
		a.Platform = "darwin"
		a.Run = func(args []string) (string, error) {
			if args[0] != "bash" || args[4] != toolScripts[slug] {
				t.Fatalf("%s: %v", slug, args)
			}
			return "", nil
		}
		if e := a.Install([]string{"tool:" + slug}, true, false, false); e != nil {
			t.Fatal(e)
		}
	}
	a := testApp(t)
	a.Platform = "darwin"
	fakeAvailable(a)
	if a.toolInstalled("xcode") {
		t.Fatal("xcode-select launcher is not proof of toolchain")
	}
	a.Run = func([]string) (string, error) { return "/Library/Developer/CommandLineTools", nil }
	if !a.toolInstalled("xcode") {
		t.Fatal("installed Xcode not detected")
	}
	a.LookPath = func(s string) (string, error) { return "/opt/homebrew/Cellar/" + s + "/bin/" + s, nil }
	if a.toolInstalled("node") || !a.toolInstalled("wrangler") {
		t.Fatal("Homebrew exclusion changed")
	}
}
func TestParityMoleNativePreviewAndJSON(t *testing.T) {
	for _, tc := range []struct {
		args []string
		dry  bool
		want []string
	}{{[]string{"mole", "clean"}, true, []string{"mo", "clean", "--dry-run"}}, {[]string{"mole", "optimize"}, true, []string{"mo", "optimize", "--dry-run"}}, {[]string{"mole", "analyze", "/test path"}, false, []string{"mo", "analyze", "/test path"}}, {[]string{"mole", "status", "--json"}, false, []string{"mo", "status", "--json"}}} {
		a := testApp(t)
		a.Platform = "darwin"
		fakeAvailable(a)
		a.Dry = tc.dry
		var got []string
		a.Stream = func(args []string, d time.Duration, _, _ io.Writer) error {
			got = args
			if d != 0 {
				t.Fatal("interactive Mole must not timeout")
			}
			return nil
		}
		o, e := a.Parse(tc.args)
		if e != nil {
			t.Fatal(e)
		}
		if e = a.Execute(o); e != nil || !reflect.DeepEqual(got, tc.want) {
			t.Fatalf("%v %v", got, e)
		}
	}
}
func TestParityMoleDryRunDoesNotInstall(t *testing.T) {
	a := testApp(t)
	a.Platform = "darwin"
	a.Dry = true
	a.LookPath = func(string) (string, error) { return "", os.ErrNotExist }
	if e := a.Execute(Options{Args: []string{"mole", "clean"}}); e != nil {
		t.Fatal(e)
	}
}
func TestParityContextHelpAndIdentityDetails(t *testing.T) {
	for _, args := range [][]string{{"pkg", "install", "--help"}, {"backup", "--help"}, {"restore", "--help"}, {"id", "show", "--help"}, {"pkg", "apply", "--help"}} {
		a := testApp(t)
		o, e := a.Parse(args)
		if e != nil {
			t.Fatal(e)
		}
		if e = a.Execute(o); e != nil {
			t.Fatal(e)
		}
		text := a.Out.(*bytes.Buffer).String()
		if !strings.Contains(text, "Usage") || !strings.Contains(text, "warden "+strings.Join(args[:len(args)-1], " ")) {
			t.Fatal(text)
		}
	}
	a := testApp(t)
	c := emptyConfig()
	c.Identities["work"] = map[string]string{"signing_key": "~/.ssh/custom.pub"}
	a.Save(c)
	if e := a.Execute(Options{Args: []string{"id", "show", "WORK"}}); e != nil {
		t.Fatal(e)
	}
	text := a.Out.(*bytes.Buffer).String()
	if !strings.Contains(text, a.Expand("~/.ssh/custom.pub")) || !strings.Contains(text, "ssh_command (derived)") {
		t.Fatal(text)
	}
}
func TestParityModuleSyntaxAndShortArguments(t *testing.T) {
	for _, s := range []string{"ALL", "git,all", " all ", "git,ssh,pkg,"} {
		got, e := Modules(s)
		if e != nil || !reflect.DeepEqual(got, []string{"git", "pkg", "ssh"}) {
			t.Fatalf("%s %v %v", s, got, e)
		}
	}
	a := testApp(t)
	o, e := a.Parse([]string{"-c/test/config", "backup", "-mgit,ssh", "-o/test/out"})
	if e != nil || a.ConfigFile != "/test/config" || o.Modules != "git,ssh" || o.Output != "/test/out" {
		t.Fatalf("%+v %v", o, e)
	}
	o, e = a.Parse([]string{"restore", "--", "-archive.tar.gz"})
	if e != nil || !reflect.DeepEqual(o.Args, []string{"restore", "-archive.tar.gz"}) {
		t.Fatal(o, e)
	}
}
func TestParityMissingSSHHostOption(t *testing.T) {
	for _, include := range []bool{false, true} {
		a := testApp(t)
		put(t, a.Expand("~/.ssh/config"), []byte("Host missing\n IdentityFile ~/.ssh/missing\nHost normal\n HostName example.com\n"))
		archive := filepath.Join(t.TempDir(), "ssh.tar.gz")
		if e := a.Backup("ssh", archive, true, include); e != nil {
			t.Fatal(e)
		}
		files, _, e := readArchive(archive)
		if e != nil {
			t.Fatal(e)
		}
		text := string(files["ssh_config"])
		if strings.Contains(text, "Host missing") != include || !strings.Contains(text, "Host normal") {
			t.Fatal(text)
		}
	}
}
func TestParityCaptureKeepsJSONSeparateFromStderr(t *testing.T) {
	a := New("test")
	out, e := a.Run([]string{"sh", "-c", `printf '{"dependencies":{"hello":{}}}'; printf 'warning\n' >&2`})
	if e != nil {
		t.Fatal(e)
	}
	pkgs, e := parsePackages("npm", out)
	if e != nil || !reflect.DeepEqual(pkgs, []string{"hello"}) {
		t.Fatal(out, e)
	}
}
func TestParityDepsJSONAndBestEffortMetadata(t *testing.T) {
	a := testApp(t)
	a.Run = func(args []string) (string, error) {
		if args[1] == "deps" {
			return "git: gettext pcre2\ngettext:\n", nil
		}
		return "", fmt.Errorf("metadata unavailable")
	}
	if e := a.Deps(""); e != nil {
		t.Fatal(e)
	}
	var data map[string]any
	if e := json.Unmarshal(a.Out.(*bytes.Buffer).Bytes(), &data); e != nil {
		t.Fatal(e)
	}
	if data["summary"].(map[string]any)["total_formulae"] != float64(2) {
		t.Fatal(data)
	}
}
func TestParityInstallWithoutSaveDoesNotNeedConfig(t *testing.T) {
	a := testApp(t)
	put(t, a.ConfigPath(), []byte("invalid JSON"))
	a.Run = func([]string) (string, error) { return "", nil }
	if e := a.Install([]string{"npm:hello"}, true, false, false); e != nil {
		t.Fatal(e)
	}
}

func TestParityLinuxScanKeepsBrewWhenCasksUnsupported(t *testing.T) {
	a := testApp(t)
	a.Platform = "linux"
	a.LookPath = func(s string) (string, error) {
		if s == "brew" || s == "apt-get" {
			return "/test/" + s, nil
		}
		return "", os.ErrNotExist
	}
	a.Run = func(args []string) (string, error) {
		if args[0] == "brew" {
			if contains(args, "--cask") {
				return "", fmt.Errorf("unsupported")
			}
			return "git", nil
		}
		if args[0] == "apt-mark" {
			return "", os.ErrNotExist
		}
		if args[0] == "dpkg" {
			return "curl install", nil
		}
		t.Fatal(args)
		return "", nil
	}
	c, e := a.Scan(emptyConfig())
	if e != nil || !reflect.DeepEqual(c.Packages["brew"]["formulae"], []string{"git"}) || !reflect.DeepEqual(c.Packages["apt"]["packages"], []string{"curl"}) {
		t.Fatal(c, e)
	}
}
func TestParitySaveSurvivesLaterManagerFailure(t *testing.T) {
	a := testApp(t)
	a.Platform = "darwin"
	a.LookPath = func(s string) (string, error) {
		if s == "pipx" {
			return "", os.ErrNotExist
		}
		return "/test/" + s, nil
	}
	a.Run = func(args []string) (string, error) {
		if contains(args, "pipx") {
			return "", fmt.Errorf("bootstrap failure")
		}
		return "", nil
	}
	if e := a.Install([]string{"brew:hello", "pipx:black"}, true, true, false); e == nil {
		t.Fatal("expected bootstrap failure")
	}
	c, _ := a.Load()
	if !reflect.DeepEqual(c.Packages["brew"]["formulae"], []string{"hello"}) {
		t.Fatal(c)
	}
}
func TestParityManagerHelpPlatformFiltering(t *testing.T) {
	a := testApp(t)
	a.Platform = "linux"
	a.managerHelp(false)
	text := a.Out.(*bytes.Buffer).String()
	if strings.Contains(text, "xcode") || strings.Contains(text, "  mas ") || !strings.Contains(text, "  apt ") {
		t.Fatal(text)
	}
}
func TestParityMirrorsAndFlags(t *testing.T) {
	for _, v := range []string{"1", "true", "TRUE", " yes "} {
		if !truthy(v) {
			t.Fatal(v)
		}
	}
	t.Setenv("WARDEN_USE_CN", "TRUE")
	env := strings.Join(mirrorEnv(), "\n")
	for _, key := range []string{"RUSTUP_DIST_SERVER=https://rsproxy.cn", "FNM_NODE_DIST_MIRROR=https://npmmirror.com/mirrors/node", "NPM_CONFIG_REGISTRY=https://registry.npmmirror.com", "HOMEBREW_BOTTLE_DOMAIN=https://mirrors.ustc.edu.cn/homebrew-bottles"} {
		if !strings.Contains(env, key) {
			t.Fatal(key)
		}
	}
	if got := mirrorScript("curl https://sh.rustup.rs"); got != "curl https://rsproxy.cn/rustup-init.sh" {
		t.Fatal(got)
	}
	t.Setenv("WARDEN_USE_CN", "false")
	if !reflect.DeepEqual(mirrorEnv(), os.Environ()) {
		t.Fatal("mirrors applied while disabled")
	}
}
func TestParityDryAPTDoesNotRefreshOrInstall(t *testing.T) {
	a := testApp(t)
	a.Platform = "linux"
	fakeAvailable(a)
	a.Dry = true
	if e := a.Install([]string{"apt:curl"}, true, false, false); e != nil {
		t.Fatal(e)
	}
}

func TestParityActualPythonArchive(t *testing.T) {
	a := testApp(t)
	archive := "testdata/python-1.1.0.tar.gz"
	files, mods, e := readArchive(archive)
	if e != nil || len(mods) != 3 {
		t.Fatal(mods, e)
	}
	keys := 0
	for name := range files {
		if strings.HasPrefix(name, "keys/") {
			keys++
		}
	}
	if keys != 4 {
		t.Fatalf("fixture must reproduce Python's duplicate pair: %d", keys)
	}
	for i := 0; i < 2; i++ {
		if e = a.Restore(archive, ""); e != nil {
			t.Fatal(e)
		}
	}
	c, e := a.Load()
	if e != nil || c.Identities["fixture"]["email"] != "fixture@example.invalid" || !reflect.DeepEqual(c.Packages["npm"]["packages"], []string{"typescript"}) || !reflect.DeepEqual(c.Tools, []string{"node"}) {
		t.Fatal(c, e)
	}
	entries, e := os.ReadDir(a.Expand("~/.warden/keys"))
	if e != nil || len(entries) != 2 {
		t.Fatal(entries, e)
	}
	sshConfig := string(read(t, a.Expand("~/.ssh/config")))
	if !strings.Contains(sshConfig, strings.TrimSuffix(c.Identities["fixture"]["signing_key"], ".pub")) {
		t.Fatal("Git/SSH references diverged")
	}
}

func TestParityMacHomebrewBootstrapOnDemand(t *testing.T) {
	a := testApp(t)
	a.Platform = "darwin"
	ready := false
	a.LookPath = func(s string) (string, error) {
		if s == "brew" && !ready {
			return "", os.ErrNotExist
		}
		return "/test/" + s, nil
	}
	a.Run = func(args []string) (string, error) {
		if args[0] == "bash" {
			if !strings.Contains(args[4], "Homebrew/install") {
				t.Fatal(args)
			}
			ready = true
			return "", nil
		}
		if args[0] != "brew" || !ready {
			t.Fatal(args)
		}
		return "", nil
	}
	if e := a.Install([]string{"brew:git"}, true, false, false); e != nil || !ready {
		t.Fatal(ready, e)
	}
	a.Dry = true
	ready = false
	if e := a.Install([]string{"brew:git"}, true, false, false); e != nil || ready {
		t.Fatal("dry run bootstrapped Homebrew", e)
	}
}

func TestParitySSHMatchArgumentsPreserveCase(t *testing.T) {
	existing := "Match exec /opt/CaseSensitive/check\n User first\n"
	incoming := "Match exec /opt/casesensitive/check\n User second\n"
	got := mergeSSH(existing, incoming)
	if !strings.Contains(got, "User first") || !strings.Contains(got, "User second") {
		t.Fatal("distinct case-sensitive Match commands merged", got)
	}
}
