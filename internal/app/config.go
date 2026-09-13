// Package app implements Warden's configuration and system operations.
package app

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/titanous/json5"
)

// Config preserves identity fields and package sections from existing JSON5 files.
type Config struct {
	Identities map[string]map[string]string   `json:"identities"`
	Packages   map[string]map[string][]string `json:"packages,omitempty"`
	Tools      []string                       `json:"tools,omitempty"`
}

func emptyConfig() Config {
	return Config{Identities: map[string]map[string]string{}, Packages: map[string]map[string][]string{}}
}

// ParseConfig accepts unified and legacy flat JSON5 configurations.
func ParseConfig(data []byte) (Config, error) {
	var raw map[string]json.RawMessage
	if err := json5.Unmarshal(data, &raw); err != nil {
		return Config{}, fmt.Errorf("parse config: %w", err)
	}
	if raw == nil {
		return Config{}, fmt.Errorf("config must be an object")
	}
	c := emptyConfig()
	if v, ok := raw["identities"]; ok {
		if err := json5.Unmarshal(v, &c.Identities); err != nil {
			return c, err
		}
	} else {
		for k, v := range raw {
			if k == "packages" || k == "tools" {
				continue
			}
			var id map[string]string
			if err := json5.Unmarshal(v, &id); err != nil {
				return c, fmt.Errorf("identity %s: %w", k, err)
			}
			c.Identities[k] = id
		}
	}
	if v, ok := raw["packages"]; ok {
		if err := json5.Unmarshal(v, &c.Packages); err != nil {
			return c, err
		}
	}
	if v, ok := raw["tools"]; ok {
		if err := json5.Unmarshal(v, &c.Tools); err != nil {
			return c, err
		}
	}
	if c.Identities == nil {
		c.Identities = map[string]map[string]string{}
	}
	if c.Packages == nil {
		c.Packages = map[string]map[string][]string{}
	}
	return c, nil
}

// Expand resolves home-relative paths.
func (a *App) Expand(p string) string {
	if p == "~" {
		return a.Home
	}
	if strings.HasPrefix(p, "~/") {
		return filepath.Join(a.Home, p[2:])
	}
	return p
}

// ConfigPath returns the explicit path or first existing default path.
func (a *App) ConfigPath() string {
	if a.ConfigFile != "" {
		return a.Expand(a.ConfigFile)
	}
	for _, p := range []string{"~/.warden/warden.jsonc", "~/.ssh/warden.jsonc", "~/warden.jsonc", "warden.jsonc"} {
		p = a.Expand(p)
		if st, e := os.Stat(p); e == nil && !st.IsDir() {
			return p
		}
	}
	return filepath.Join(a.Home, ".warden", "warden.jsonc")
}

// Load reads configuration without creating files when none exists.
func (a *App) Load() (Config, error) {
	b, e := os.ReadFile(a.ConfigPath())
	if os.IsNotExist(e) {
		return emptyConfig(), nil
	}
	if e != nil {
		return Config{}, e
	}
	return ParseConfig(b)
}

func encode(v any) []byte { b, _ := json.MarshalIndent(v, "", "  "); return append(b, '\n') }

func writeAtomic(path string, b []byte, mode os.FileMode) error {
	if err := os.MkdirAll(filepath.Dir(path), 0700); err != nil {
		return err
	}
	f, err := os.CreateTemp(filepath.Dir(path), ".warden-*")
	if err != nil {
		return err
	}
	defer os.Remove(f.Name())
	if err = f.Chmod(mode); err == nil {
		_, err = f.Write(b)
	}
	if err == nil {
		err = f.Sync()
	}
	closeErr := f.Close()
	if err != nil {
		return err
	}
	if closeErr != nil {
		return closeErr
	}
	return os.Rename(f.Name(), path)
}

// Save writes configuration atomically with private permissions.
func (a *App) Save(c Config) error {
	if a.Dry {
		a.Row("Preview", "Would save "+a.ConfigPath())
		return nil
	}
	return writeAtomic(a.ConfigPath(), encode(c), 0600)
}

func union(a, b []string) []string {
	m := map[string]bool{}
	for _, v := range append(append([]string{}, a...), b...) {
		m[v] = true
	}
	return sortedKeys(m)
}
func sortedKeys[V any](m map[string]V) []string {
	r := make([]string, 0, len(m))
	for k := range m {
		r = append(r, k)
	}
	sort.Strings(r)
	return r
}

// Merge combines identities by name and package/tool lists by sorted union.
func Merge(a, b Config) Config {
	r := emptyConfig()
	for k, v := range a.Identities {
		r.Identities[k] = v
	}
	for k, v := range b.Identities {
		r.Identities[k] = v
	}
	for _, c := range []Config{a, b} {
		for mgr, sec := range c.Packages {
			if r.Packages[mgr] == nil {
				r.Packages[mgr] = map[string][]string{}
			}
			for k, v := range sec {
				r.Packages[mgr][k] = union(r.Packages[mgr][k], v)
			}
		}
	}
	r.Tools = union(a.Tools, b.Tools)
	return r
}
