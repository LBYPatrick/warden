package app

import (
	"archive/tar"
	"bytes"
	"compress/gzip"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path"
	"path/filepath"
	"strings"
	"time"

	"golang.org/x/crypto/ssh"
)

// Modules validates a module selection; an empty spec means all modules.
func Modules(spec string) ([]string, error) {
	if spec == "" {
		return []string{"git", "pkg", "ssh"}, nil
	}
	var out []string
	for _, m := range strings.Split(spec, ",") {
		m = strings.ToLower(strings.TrimSpace(m))
		if m == "all" {
			return []string{"git", "pkg", "ssh"}, nil
		}
	}
	for _, m := range strings.Split(spec, ",") {
		m = strings.ToLower(strings.TrimSpace(m))
		if m == "" {
			continue
		}
		if !contains([]string{"git", "ssh", "pkg"}, m) {
			return nil, fmt.Errorf("unknown module %q (choose git, ssh, pkg, all)", m)
		}
		out = union(out, []string{m})
	}
	if len(out) == 0 {
		return nil, fmt.Errorf("select at least one module")
	}
	return out, nil
}
func contains(s []string, v string) bool {
	for _, x := range s {
		if x == v {
			return true
		}
	}
	return false
}
func digest(b []byte) string { h := sha256.Sum256(b); return hex.EncodeToString(h[:]) }
func keyIdentity(b []byte, pub bool) string {
	if pub {
		if k, _, _, _, e := ssh.ParseAuthorizedKey(b); e == nil {
			return "public:" + string(k.Marshal())
		}
	} else {
		if k, e := ssh.ParseRawPrivateKey(b); e == nil {
			if signer, e := ssh.NewSignerFromKey(k); e == nil {
				return "private:" + string(signer.PublicKey().Marshal())
			}
		}
	}
	return string(bytes.TrimSpace(b))
}
func sameKey(a, b []byte, pub bool) bool { return keyIdentity(a, pub) == keyIdentity(b, pub) }

type keyCollector struct {
	a     *App
	files map[string][]byte
	pairs map[string]string
}

func (k *keyCollector) collect(ref string) (string, error) {
	pubRef := strings.HasSuffix(ref, ".pub")
	base := strings.TrimSuffix(k.a.Expand(ref), ".pub")
	priv, pe := os.ReadFile(base)
	pub, ue := os.ReadFile(base + ".pub")
	if pe != nil && !os.IsNotExist(pe) {
		return "", pe
	}
	if ue != nil && !os.IsNotExist(ue) {
		return "", ue
	}
	if pe != nil && ue != nil {
		k.a.Row("Missing key", ref)
		return ref, nil
	}
	identity := keyIdentity(priv, false)
	if len(priv) == 0 {
		identity = keyIdentity(pub, true)
	}
	id := digest([]byte(identity))
	dest, ok := k.pairs[id]
	if !ok {
		dest = "key_" + id[:24]
		k.pairs[id] = dest
	}
	if len(priv) > 0 {
		k.files["keys/"+dest] = priv
	}
	if len(pub) > 0 {
		k.files["keys/"+dest+".pub"] = pub
	}
	if pubRef {
		dest += ".pub"
	}
	return "~/.warden/keys/" + dest, nil
}

// Backup creates a portable, content-deduplicated archive compatible with Python backups.
func (a *App) Backup(spec, output string, skipScan, includeMissing bool) error {
	mods, e := Modules(spec)
	if e != nil {
		return e
	}
	c, e := a.Load()
	if e != nil {
		return e
	}
	if contains(mods, "pkg") && !skipScan {
		c, e = a.Scan(c)
		if e != nil {
			return e
		}
	}
	files := map[string][]byte{}
	k := keyCollector{a: a, files: files, pairs: map[string]string{}}
	out := emptyConfig()
	if contains(mods, "git") {
		for _, name := range sortedKeys(c.Identities) {
			id := c.Identities[name]
			copyID := map[string]string{}
			for x, v := range id {
				copyID[x] = v
			}
			if ref := id["signing_key"]; ref != "" {
				copyID["signing_key"], e = k.collect(ref)
				if e != nil {
					return e
				}
			}
			out.Identities[name] = copyID
		}
	}
	if contains(mods, "pkg") {
		out.Packages = c.Packages
		out.Tools = c.Tools
		if e = collectAPT(files); e != nil {
			return e
		}
	}
	if contains(mods, "git") || contains(mods, "pkg") {
		files["warden.jsonc"] = encode(out)
	}
	if contains(mods, "ssh") {
		b, err := os.ReadFile(a.Expand("~/.ssh/config"))
		if err != nil && !os.IsNotExist(err) {
			return err
		}
		s, err := a.backupSSH(string(b), &k, includeMissing)
		if err != nil {
			return err
		}
		files["ssh_config"] = []byte(s)
	}
	files[".warden-marker"] = encode(map[string]any{"modules": mods, "version": a.Version, "created": time.Now().UTC().Format(time.RFC3339)})
	if output == "" {
		output = "warden-backup-" + strings.Join(mods, "+") + "-" + time.Now().Format("2006-01-02") + ".tar.gz"
	}
	output = a.Expand(output)
	a.Header("Backup")
	a.Row("Modules", strings.Join(mods, ", "))
	a.Row("Archive", output)
	a.Row("Files", fmt.Sprint(len(files)))
	if a.Dry {
		a.Success("Preview complete; no changes made")
		return nil
	}
	var buf bytes.Buffer
	gz := gzip.NewWriter(&buf)
	tw := tar.NewWriter(gz)
	for _, name := range sortedKeys(files) {
		b := files[name]
		if e = tw.WriteHeader(&tar.Header{Name: name, Mode: 0600, Size: int64(len(b)), Typeflag: tar.TypeReg}); e != nil {
			return e
		}
		if _, e = tw.Write(b); e != nil {
			return e
		}
	}
	if e = tw.Close(); e != nil {
		return e
	}
	if e = gz.Close(); e != nil {
		return e
	}
	if e = writeAtomic(output, buf.Bytes(), 0600); e != nil {
		return e
	}
	if contains(mods, "pkg") && !skipScan {
		if e = a.Save(c); e != nil {
			return e
		}
	}
	a.Success("Backup created")
	return nil
}
func readArchive(filename string) (map[string][]byte, []string, error) {
	f, e := os.Open(filename)
	if e != nil {
		return nil, nil, e
	}
	defer f.Close()
	gz, e := gzip.NewReader(f)
	if e != nil {
		return nil, nil, e
	}
	defer gz.Close()
	tr := tar.NewReader(gz)
	files := map[string][]byte{}
	var total int64
	for {
		h, err := tr.Next()
		if err == io.EOF {
			break
		}
		if err != nil {
			return nil, nil, err
		}
		n := h.Name
		if path.IsAbs(n) || strings.Contains(n, "\\") || path.Clean(n) != n || n == ".." || strings.HasPrefix(n, "../") {
			return nil, nil, fmt.Errorf("unsafe archive path %q", n)
		}
		if h.Typeflag == tar.TypeDir {
			continue
		}
		if h.Typeflag != tar.TypeReg && h.Typeflag != tar.TypeRegA {
			return nil, nil, fmt.Errorf("archive links and special files are not supported: %s", n)
		}
		if _, ok := files[n]; ok {
			return nil, nil, fmt.Errorf("duplicate archive entry %s", n)
		}
		total += h.Size
		if h.Size < 0 || h.Size > 32<<20 || total > 128<<20 {
			return nil, nil, fmt.Errorf("archive exceeds size limit")
		}
		b, err := io.ReadAll(tr)
		if err != nil {
			return nil, nil, err
		}
		files[n] = b
	}
	var marker struct {
		Modules []string `json:"modules"`
		Type    string   `json:"type"`
	}
	if e = json.Unmarshal(files[".warden-marker"], &marker); e != nil {
		return nil, nil, fmt.Errorf("missing or invalid Warden marker: %w", e)
	}
	if len(marker.Modules) == 0 && marker.Type != "" {
		marker.Modules, e = Modules(marker.Type)
		if e != nil {
			return nil, nil, e
		}
	}
	if len(marker.Modules) == 0 {
		return nil, nil, fmt.Errorf("archive has no modules")
	}
	for _, m := range marker.Modules {
		if !contains([]string{"git", "ssh", "pkg"}, m) {
			return nil, nil, fmt.Errorf("invalid archive module %q", m)
		}
	}
	for _, m := range marker.Modules {
		required := "warden.jsonc"
		if m == "ssh" {
			required = "ssh_config"
		}
		if _, ok := files[required]; !ok {
			return nil, nil, fmt.Errorf("archive missing %s", required)
		}
	}
	return files, marker.Modules, nil
}

// Restore validates first, reuses local key pairs, then merges selected modules.
func (a *App) Restore(filename, spec string) error {
	files, available, e := readArchive(a.Expand(filename))
	if e != nil {
		return e
	}
	mods := available
	if spec != "" {
		mods, e = Modules(spec)
		if e != nil {
			return e
		}
	}
	for _, m := range mods {
		if !contains(available, m) {
			return fmt.Errorf("archive does not contain %s", m)
		}
	}
	incoming := emptyConfig()
	if contains(mods, "git") || contains(mods, "pkg") {
		incoming, e = ParseConfig(files["warden.jsonc"])
		if e != nil {
			return e
		}
	}
	if !contains(mods, "git") {
		incoming.Identities = map[string]map[string]string{}
	}
	if !contains(mods, "pkg") {
		incoming.Packages = map[string]map[string][]string{}
		incoming.Tools = nil
	}
	existing, e := a.Load()
	if e != nil {
		return e
	}
	writes := map[string][]byte{}
	mapping := map[string]string{}
	candidates := []string{}
	for _, dir := range []string{a.Expand("~/.ssh"), a.Expand("~/.warden/keys")} {
		_ = filepath.WalkDir(dir, func(p string, d os.DirEntry, err error) error {
			if err == nil && !d.IsDir() && !strings.HasSuffix(p, ".pub") {
				candidates = append(candidates, p)
			}
			return nil
		})
	}
	for _, id := range existing.Identities {
		if id["signing_key"] != "" {
			candidates = append(candidates, strings.TrimSuffix(a.Expand(id["signing_key"]), ".pub"))
		}
	}
	localSSH, err := os.ReadFile(a.Expand("~/.ssh/config"))
	if err != nil && !os.IsNotExist(err) {
		return err
	}
	_, e = rewriteSSH(string(localSSH), func(p string) (string, error) {
		candidates = append(candidates, strings.TrimSuffix(a.Expand(p), ".pub"))
		return p, nil
	})
	if e != nil {
		return e
	}
	a.Header("Restore")
	a.Row("Modules", strings.Join(mods, ", "))
	needed := map[string]bool{}
	for _, id := range incoming.Identities {
		if p := id["signing_key"]; strings.HasPrefix(p, "~/.warden/keys/") {
			needed[strings.TrimSuffix(path.Base(p), ".pub")] = true
		}
	}
	if contains(mods, "ssh") {
		_, e = rewriteSSH(string(files["ssh_config"]), func(p string) (string, error) {
			if strings.HasPrefix(p, "~/.warden/keys/") {
				needed[strings.TrimSuffix(path.Base(p), ".pub")] = true
			}
			return p, nil
		})
		if e != nil {
			return e
		}
	}
	for _, base := range sortedKeys(needed) {
		priv, pok := files["keys/"+base]
		pub, uok := files["keys/"+base+".pub"]
		if !pok && !uok {
			continue
		}
		dest := ""
		for _, candidate := range union(candidates, nil) {
			cp, ce := os.ReadFile(candidate)
			cu, ue := os.ReadFile(candidate + ".pub")
			if b, ok := writes[candidate]; ok {
				cp = b
				ce = nil
			}
			if b, ok := writes[candidate+".pub"]; ok {
				cu = b
				ue = nil
			}
			if pok && (ce != nil || !sameKey(priv, cp, false)) {
				continue
			}
			if uok && ue == nil && !sameKey(pub, cu, true) {
				continue
			}
			if !pok && (ue != nil || !sameKey(pub, cu, true)) {
				continue
			}
			dest = candidate
			break
		}
		if dest == "" {
			dest = a.Expand("~/.warden/keys/" + base)
			for n := 0; ; n++ {
				conflict := false
				for _, suffix := range []string{"", ".pub"} {
					b, ok := files["keys/"+base+suffix]
					if !ok {
						continue
					}
					old, err := os.ReadFile(dest + suffix)
					if err != nil && !os.IsNotExist(err) {
						return err
					}
					if w, yes := writes[dest+suffix]; yes {
						old = w
						err = nil
					}
					if err == nil && !sameKey(old, b, suffix == ".pub") {
						conflict = true
					}
				}
				if !conflict {
					break
				}
				dest = a.Expand(fmt.Sprintf("~/.warden/keys/%s_%s_%d", base, digest(append(append([]byte{}, priv...), pub...))[:12], n))
			}
		}
		for _, suffix := range []string{"", ".pub"} {
			b, ok := files["keys/"+base+suffix]
			if !ok {
				continue
			}
			if old, err := os.ReadFile(dest + suffix); err == nil && sameKey(old, b, suffix == ".pub") {
				continue
			}
			writes[dest+suffix] = b
		}
		candidates = append(candidates, dest)
		mapping["~/.warden/keys/"+base] = dest
		mapping["~/.warden/keys/"+base+".pub"] = dest + ".pub"
		a.Row("Key pair", filepath.Base(dest))
	}
	for _, id := range incoming.Identities {
		if p, ok := mapping[id["signing_key"]]; ok {
			id["signing_key"] = p
		}
	}
	if contains(mods, "git") || contains(mods, "pkg") {
		writes[a.ConfigPath()] = encode(Merge(existing, incoming))
	}
	if contains(mods, "ssh") {
		s, err := rewriteSSH(string(files["ssh_config"]), func(p string) (string, error) {
			if dest, ok := mapping[p]; ok {
				return dest, nil
			}
			return p, nil
		})
		if err != nil {
			return err
		}
		if len(localSSH) > 0 {
			writes[a.Expand("~/.ssh/config.bak")] = localSSH
		}
		writes[a.Expand("~/.ssh/config")] = []byte(mergeSSH(string(localSSH), s))
	}
	if contains(mods, "pkg") {
		for name, b := range files {
			if strings.HasPrefix(name, "apt-sources/") {
				rel := strings.TrimPrefix(name, "apt-sources/")
				if !validAPT(rel) {
					return fmt.Errorf("invalid apt source path %s", rel)
				}
				if runtimeOS() == "linux" {
					writes["/etc/apt/"+rel] = b
				}
			}
		}
	}
	a.Row("Files to write", fmt.Sprint(len(writes)))
	if a.Dry {
		a.Success("Preview complete; no changes made")
		return nil
	}
	for _, p := range sortedKeys(writes) {
		if e = a.writeRestoredFile(p, writes[p]); e != nil {
			return fmt.Errorf("restore %s: %w", p, e)
		}
	}
	a.Success("Restored and merged")
	return nil
}
func validAPT(p string) bool {
	return p == "sources.list" || (path.Dir(p) == "sources.list.d" && (strings.HasSuffix(p, ".list") || strings.HasSuffix(p, ".sources")))
}
func collectAPT(files map[string][]byte) error {
	if runtimeOS() != "linux" {
		return nil
	}
	paths := []string{"/etc/apt/sources.list"}
	for _, pattern := range []string{"/etc/apt/sources.list.d/*.list", "/etc/apt/sources.list.d/*.sources"} {
		p, e := filepath.Glob(pattern)
		if e != nil {
			return e
		}
		paths = append(paths, p...)
	}
	for _, p := range paths {
		b, e := os.ReadFile(p)
		if os.IsNotExist(e) {
			continue
		}
		if e != nil {
			return e
		}
		files["apt-sources/"+strings.TrimPrefix(p, "/etc/apt/")] = b
	}
	return nil
}

func (a *App) writeRestoredFile(p string, b []byte) error {
	if !strings.HasPrefix(p, "/etc/apt/") {
		return writeAtomic(p, b, 0600)
	}
	err := writeAtomic(p, b, 0644)
	if err == nil || !os.IsPermission(err) {
		return err
	}
	temp, err := os.CreateTemp("", "warden-apt-*")
	if err != nil {
		return err
	}
	defer os.Remove(temp.Name())
	if _, err = temp.Write(b); err != nil {
		temp.Close()
		return err
	}
	if err = temp.Close(); err != nil {
		return err
	}
	_, err = a.Run([]string{"sudo", "install", "-D", "-m", "0644", temp.Name(), p})
	return err
}

func (a *App) backupSSH(text string, k *keyCollector, includeMissing bool) (string, error) {
	pre, blocks := parseSSH(text)
	prefix, err := rewriteSSH(strings.Join(pre, "\n"), k.collect)
	if err != nil {
		return "", err
	}
	parts := []string{prefix}
	for _, block := range blocks {
		missing := false
		_, err := rewriteSSH(strings.Join(block.lines, "\n"), func(ref string) (string, error) {
			p := strings.TrimSuffix(a.Expand(ref), ".pub")
			if _, err := os.Stat(p); os.IsNotExist(err) {
				missing = true
			} else if err != nil {
				return "", err
			}
			return ref, nil
		})
		if err != nil {
			return "", err
		}
		if missing && !includeMissing {
			a.Row("Skipped SSH host", block.name+" (missing key; use --include-missing)")
			continue
		}
		rewritten, err := rewriteSSH(strings.Join(block.lines, "\n"), k.collect)
		if err != nil {
			return "", err
		}
		parts = append(parts, rewritten)
	}
	return strings.TrimSuffix(strings.Join(parts, "\n"), "\n") + "\n", nil
}
