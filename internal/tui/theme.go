package tui

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

type theme struct {
	Mode   string `json:"mode"`
	Preset string `json:"preset"`
}

var modes = []string{"clear", "dark", "light"}

var presets = []string{"blue", "green", "purple", "orange", "rose", "cyan", "ocean", "sunset", "grape", "forest"}

func themePath(home string) string { return filepath.Join(home, ".warden", "theme.json") }
func readThemeData(home string) (map[string]json.RawMessage, error) {
	data := map[string]json.RawMessage{}
	b, err := os.ReadFile(themePath(home))
	if os.IsNotExist(err) {
		return data, nil
	}
	if err != nil {
		return nil, err
	}
	if err = json.Unmarshal(b, &data); err != nil {
		return nil, fmt.Errorf("read appearance settings: %w", err)
	}
	if data == nil {
		return nil, fmt.Errorf("appearance settings must be a JSON object")
	}
	return data, nil
}
func loadTheme(home string) (theme, error) {
	t := theme{"clear", "blue"}
	data, err := readThemeData(home)
	if err != nil {
		return t, err
	}
	var mode, preset string
	_ = json.Unmarshal(data["mode"], &mode)
	_ = json.Unmarshal(data["preset"], &preset)
	if mode == "clear" || mode == "dark" || mode == "light" {
		t.Mode = mode
	}
	if themeValues["dark-"+preset] != nil {
		t.Preset = preset
	}
	return t, nil
}
func saveTheme(home string, t theme) error {
	if (t.Mode != "clear" && t.Mode != "dark" && t.Mode != "light") || themeValues["dark-"+t.Preset] == nil {
		return fmt.Errorf("invalid appearance: %s/%s", t.Mode, t.Preset)
	}
	data, err := readThemeData(home)
	if err != nil {
		return err
	}
	data["mode"], _ = json.Marshal(t.Mode)
	data["preset"], _ = json.Marshal(t.Preset)
	b, err := json.MarshalIndent(data, "", "  ")
	if err != nil {
		return err
	}
	path := themePath(home)
	if err := os.MkdirAll(filepath.Dir(path), 0700); err != nil {
		return err
	}
	f, err := os.CreateTemp(filepath.Dir(path), ".theme-*")
	if err != nil {
		return err
	}
	defer os.Remove(f.Name())
	if _, err = f.Write(append(b, '\n')); err != nil {
		f.Close()
		return err
	}
	if err = f.Close(); err != nil {
		return err
	}
	return os.Rename(f.Name(), path)
}
