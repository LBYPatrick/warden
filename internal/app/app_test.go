package app

import (
	"archive/tar"
	"bytes"
	"compress/gzip"
	"crypto/ed25519"
	"crypto/rand"
	"encoding/pem"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"reflect"
	"strings"
	"testing"

	"golang.org/x/crypto/ssh"
)

func testApp(t *testing.T) *App {
	t.Helper()
	a := New("1.1.0")
	a.Stream = nil
	a.Home = t.TempDir()
	a.Out = &bytes.Buffer{}
	a.Err = &bytes.Buffer{}
	a.NoColor = true
	a.Run = func(args []string) (string, error) { return "", fmt.Errorf("unexpected process: %v", args) }
	return a
}
func put(t *testing.T, p string, b []byte) {
	t.Helper()
	if e := writeAtomic(p, b, 0600); e != nil {
		t.Fatal(e)
	}
}
func read(t *testing.T, p string) []byte {
	t.Helper()
	b, e := os.ReadFile(p)
	if e != nil {
		t.Fatal(e)
	}
	return b
}
func pair(t *testing.T) ([]byte, []byte) {
	t.Helper()
	pub, priv, e := ed25519.GenerateKey(rand.Reader)
	if e != nil {
		t.Fatal(e)
	}
	block, e := ssh.MarshalPrivateKey(priv, "")
	if e != nil {
		t.Fatal(e)
	}
	key, e := ssh.NewPublicKey(pub)
	if e != nil {
		t.Fatal(e)
	}
	return pem.EncodeToMemory(block), ssh.MarshalAuthorizedKey(key)
}
func fixtureArchive(t *testing.T, p string, files map[string][]byte) {
	t.Helper()
	var b bytes.Buffer
	gz := gzip.NewWriter(&b)
	tw := tar.NewWriter(gz)
	for _, name := range sortedKeys(files) {
		v := files[name]
		if e := tw.WriteHeader(&tar.Header{Name: name, Mode: 0600, Size: int64(len(v))}); e != nil {
			t.Fatal(e)
		}
		if _, e := tw.Write(v); e != nil {
			t.Fatal(e)
		}
	}
	tw.Close()
	gz.Close()
	put(t, p, b.Bytes())
}
func TestConfigJSON5LegacyAndMerge(t *testing.T) {
	for _, s := range []string{`{personal:{name:'Pat',email:'p@example.com',},}`, `{// comment
 identities:{personal:{name:'Pat',email:'p@example.com'}}, packages:{brew:{formulae:['git',]}},}`} {
		c, e := ParseConfig([]byte(s))
		if e != nil {
			t.Fatal(e)
		}
		if c.Identities["personal"]["name"] != "Pat" {
			t.Fatalf("%+v", c)
		}
	}
	a, e := ParseConfig([]byte(`{packages:{npm:{packages:['a']}}}`))
	if e != nil {
		t.Fatal(e)
	}
	if len(a.Identities) != 0 {
		t.Fatal("package-only config interpreted as identities")
	}
	b := emptyConfig()
	b.Packages = map[string]map[string][]string{"npm": {"packages": {"b", "a"}}}
	r := Merge(a, b)
	if !reflect.DeepEqual(r.Packages["npm"]["packages"], []string{"a", "b"}) {
		t.Fatal(r)
	}
	for _, s := range []string{"null", "[]", "{broken", `{identities:{a:42}}`} {
		if _, e = ParseConfig([]byte(s)); e == nil {
			t.Fatalf("accepted %s", s)
		}
	}
}
func TestBackupRestoreReusesLocalPairAndIsIdempotent(t *testing.T) {
	a := testApp(t)
	priv, pub := pair(t)
	put(t, a.Expand("~/.ssh/id_ed25519"), priv)
	put(t, a.Expand("~/.ssh/id_ed25519.pub"), pub)
	put(t, a.Expand("~/.ssh/copy"), priv)
	put(t, a.Expand("~/.ssh/copy.pub"), append(bytes.TrimSpace(pub), []byte(" another comment\n")...))
	put(t, a.Expand("~/.ssh/config"), []byte("Host github\n  IdentityFile ~/.ssh/copy\n"))
	c := emptyConfig()
	c.Identities["personal"] = map[string]string{"name": "Pat", "signing_key": "~/.ssh/id_ed25519.pub"}
	if e := a.Save(c); e != nil {
		t.Fatal(e)
	}
	archive := filepath.Join(t.TempDir(), "backup.tar.gz")
	if e := a.Backup("git,ssh", archive, true, false); e != nil {
		t.Fatal(e)
	}
	files, _, e := readArchive(archive)
	if e != nil {
		t.Fatal(e)
	}
	count := 0
	for p := range files {
		if strings.HasPrefix(p, "keys/") {
			count++
		}
	}
	if count != 2 {
		t.Fatalf("wanted one pair, got %d key files", count)
	}
	dest := testApp(t)
	put(t, dest.Expand("~/.ssh/local"), priv)
	put(t, dest.Expand("~/.ssh/local.pub"), pub)
	for i := 0; i < 2; i++ {
		if e = dest.Restore(archive, ""); e != nil {
			t.Fatal(e)
		}
	}
	restored, e := dest.Load()
	if e != nil {
		t.Fatal(e)
	}
	if restored.Identities["personal"]["signing_key"] != dest.Expand("~/.ssh/local.pub") {
		t.Fatal(restored)
	}
	if _, e = os.Stat(dest.Expand("~/.warden/keys")); !os.IsNotExist(e) {
		t.Fatal("duplicate keys created")
	}
	if !strings.Contains(string(read(t, dest.Expand("~/.ssh/config"))), dest.Expand("~/.ssh/local")) {
		t.Fatal("SSH reference not remapped")
	}
	fresh := testApp(t)
	for i := 0; i < 2; i++ {
		if e = fresh.Restore(archive, ""); e != nil {
			t.Fatal(e)
		}
	}
	entries, e := os.ReadDir(fresh.Expand("~/.warden/keys"))
	if e != nil || len(entries) != 2 {
		t.Fatalf("%v %v", entries, e)
	}
	st, _ := os.Stat(fresh.ConfigPath())
	if st.Mode().Perm() != 0600 {
		t.Fatal(st.Mode())
	}
}
func TestRestoreLegacyCollisionAndModuleIsolation(t *testing.T) {
	a := testApp(t)
	priv, pub := pair(t)
	other, _ := pair(t)
	put(t, a.Expand("~/.warden/keys/id_abc123"), other)
	put(t, a.Expand("~/.ssh/config"), []byte("Host local\n  HostName local.test\n"))
	archive := filepath.Join(t.TempDir(), "old.tar.gz")
	files := map[string][]byte{".warden-marker": []byte(`{"type":"all"}`), "warden.jsonc": []byte(`{identities:{work:{signing_key:'~/.warden/keys/id_abc123.pub'}},packages:{npm:{packages:['hello']}}}`), "ssh_config": []byte("Host incoming\n  IdentityFile ~/.warden/keys/id_abc123\n"), "keys/id_abc123": priv, "keys/id_abc123.pub": pub}
	fixtureArchive(t, archive, files)
	if e := a.Restore(archive, "pkg"); e != nil {
		t.Fatal(e)
	}
	c, _ := a.Load()
	if len(c.Identities) != 0 || len(c.Packages["npm"]["packages"]) != 1 {
		t.Fatal(c)
	}
	if string(read(t, a.Expand("~/.warden/keys/id_abc123"))) != string(other) {
		t.Fatal("overwrote key")
	}
	if e := a.Restore(archive, "git"); e != nil {
		t.Fatal(e)
	}
	c, _ = a.Load()
	key := c.Identities["work"]["signing_key"]
	if key == a.Expand("~/.warden/keys/id_abc123.pub") {
		t.Fatal("collision not renamed")
	}
	if !sameKey(read(t, strings.TrimSuffix(key, ".pub")), priv, false) {
		t.Fatal("wrong private key")
	}
	if strings.Contains(string(read(t, a.Expand("~/.ssh/config"))), "incoming") {
		t.Fatal("restored unselected SSH module")
	}
}
func TestRestoreRejectsUnsafeArchiveBeforeWriting(t *testing.T) {
	for _, bad := range []string{"../escape", "/absolute", "keys/../../escape"} {
		t.Run(bad, func(t *testing.T) {
			a := testApp(t)
			archive := filepath.Join(t.TempDir(), "bad.tar.gz")
			fixtureArchive(t, archive, map[string][]byte{".warden-marker": []byte(`{"modules":["git"]}`), "warden.jsonc": []byte(`{}`), bad: []byte("bad")})
			if e := a.Restore(archive, ""); e == nil {
				t.Fatal("accepted unsafe archive")
			}
			if _, e := os.Stat(a.ConfigPath()); !os.IsNotExist(e) {
				t.Fatal("wrote before validation")
			}
		})
	}
}
func TestDryRunDoesNotCreateFiles(t *testing.T) {
	a := testApp(t)
	a.Dry = true
	a.ConfigFile = filepath.Join(a.Home, "custom", "config.jsonc")
	if e := a.Save(emptyConfig()); e != nil {
		t.Fatal(e)
	}
	if e := a.Backup("git", filepath.Join(a.Home, "backup.tar.gz"), true, false); e != nil {
		t.Fatal(e)
	}
	entries, _ := os.ReadDir(a.Home)
	if len(entries) != 0 {
		t.Fatal(entries)
	}
}
func TestSwitchQuotesKeyAndParsesGlobalFlags(t *testing.T) {
	a := testApp(t)
	c := emptyConfig()
	c.Identities["Work"] = map[string]string{"name": "Pat", "email": "x@y", "signing_key": "~/.ssh/key with 'quotes'.pub"}
	a.Save(c)
	var calls [][]string
	a.Run = func(args []string) (string, error) { calls = append(calls, args); return "", nil }
	o, e := a.Parse([]string{"id", "switch", "work", "--no-color"})
	if e != nil {
		t.Fatal(e)
	}
	if e = a.Execute(o); e != nil {
		t.Fatal(e)
	}
	found := false
	for _, args := range calls {
		if args[3] == "core.sshCommand" {
			found = true
			if !strings.Contains(args[4], "'\"'\"'") {
				t.Fatal(args)
			}
		}
	}
	if !found {
		t.Fatal("missing ssh command")
	}
}
func TestScanParsers(t *testing.T) {
	cases := []struct {
		name, input string
		want        []string
	}{{"npm", `{"dependencies":{"npm":{},"@scope/pkg":{}}}`, []string{"@scope/pkg"}}, {"pnpm", `[{"dependencies":{"foo":{}}}]`, []string{"foo"}}, {"cargo", "bat v1:\n    bat\n", []string{"bat"}}, {"apk", "curl-8.5.0-r0 x86_64\n", []string{"curl"}}, {"mas", "123 App Name (1.0)\n", []string{"123:App Name"}}, {"snap", "Name Version\ncore22 1\nhello 2\n", []string{"hello"}}}
	for _, tc := range cases {
		got, e := parsePackages(tc.name, tc.input)
		if e != nil || !reflect.DeepEqual(got, tc.want) {
			t.Fatalf("%s: %v %v", tc.name, got, e)
		}
	}
}
func TestInstallValidationSaveAndFailure(t *testing.T) {
	a := testApp(t)
	a.Run = func(args []string) (string, error) {
		if len(args) > 1 && args[1] == "list" {
			return `{"dependencies":{}}`, nil
		}
		if strings.Contains(strings.Join(args, " "), "bad") {
			return "", fmt.Errorf("failed")
		}
		return "", nil
	}
	if e := a.Install([]string{"npm:good", "npm:bad"}, true, true, false); e == nil {
		t.Fatal("failure not propagated")
	}
	c, _ := a.Load()
	if !reflect.DeepEqual(c.Packages["npm"]["packages"], []string{"good"}) {
		t.Fatal(c)
	}
	for _, p := range []string{"npm:--help", "unknown:hello", "npm:", "hello"} {
		if e := a.Install([]string{p}, true, false, false); e == nil {
			t.Fatalf("accepted %s", p)
		}
	}
}
func TestSSHMergeAndRewrite(t *testing.T) {
	s, e := rewriteSSH("Host *\n identityfile=\"~/key with spaces\"\n IdentityFile ~/second\n", func(p string) (string, error) { return "/new/" + pathBase(p), nil })
	if e != nil || !strings.Contains(s, `IdentityFile "/new/key with spaces"`) {
		t.Fatalf("%s %v", s, e)
	}
	got := mergeSSH("# local\nHost a\n HostName old\n", "Host a\n HostName new\nHost b\n HostName other\n")
	if strings.Count(got, "Host a") != 1 || !strings.HasPrefix(got, "# local") || strings.Contains(got, "old") {
		t.Fatal(got)
	}
}
func pathBase(s string) string { return filepath.Base(s) }

func TestLegacyDuplicatePairsCollapseDuringRestore(t *testing.T) {
	a := testApp(t)
	priv, pub := pair(t)
	archive := filepath.Join(t.TempDir(), "duplicate.tar.gz")
	files := map[string][]byte{".warden-marker": []byte(`{"modules":["git","ssh"]}`), "warden.jsonc": []byte(`{identities:{work:{signing_key:'~/.warden/keys/git_hash.pub'}}}`), "ssh_config": []byte("Host work\n IdentityFile ~/.warden/keys/ssh_hash\n"), "keys/git_hash": priv, "keys/git_hash.pub": pub, "keys/ssh_hash": priv, "keys/ssh_hash.pub": pub}
	fixtureArchive(t, archive, files)
	if e := a.Restore(archive, ""); e != nil {
		t.Fatal(e)
	}
	entries, e := os.ReadDir(a.Expand("~/.warden/keys"))
	if e != nil || len(entries) != 2 {
		t.Fatalf("expected one pair: %v %v", entries, e)
	}
}
func TestMalformedConfigNeverOverwritten(t *testing.T) {
	a := testApp(t)
	put(t, a.ConfigPath(), []byte("{broken"))
	archive := filepath.Join(t.TempDir(), "valid.tar.gz")
	fixtureArchive(t, archive, map[string][]byte{".warden-marker": []byte(`{"modules":["git"]}`), "warden.jsonc": []byte(`{identities:{work:{name:'New'}}}`)})
	if e := a.Restore(archive, ""); e == nil {
		t.Fatal("accepted broken destination config")
	}
	if string(read(t, a.ConfigPath())) != "{broken" {
		t.Fatal("overwrote malformed config")
	}
}
func TestToolRecipesHaveValidShellSyntax(t *testing.T) {
	for name, script := range toolScripts {
		c := exec.Command("bash", "-n")
		c.Stdin = strings.NewReader(script)
		if b, e := c.CombinedOutput(); e != nil {
			t.Fatalf("%s: %v %s", name, e, b)
		}
	}
}
func TestUpdatePinValidationAndDryRun(t *testing.T) {
	a := testApp(t)
	a.Dry = true
	if e := a.Update("main"); e == nil {
		t.Fatal("accepted branch")
	}
	if e := a.Update("v2.0.0"); e != nil {
		t.Fatal(e)
	}
	if _, e := a.Parse([]string{"--force=false"}); e == nil {
		t.Fatal("ignored boolean flag value")
	}
}

func TestSSHInlineCommentRetained(t *testing.T) {
	got, e := rewriteSSH("Host work\n IdentityFile \"~/key path\" # keep comment\n", func(p string) (string, error) {
		if p != "~/key path" {
			t.Fatalf("incorrect path: %s", p)
		}
		return "/new/key path", nil
	})
	if e != nil || !strings.Contains(got, `IdentityFile "/new/key path" # keep comment`) {
		t.Fatalf("%s %v", got, e)
	}
}
