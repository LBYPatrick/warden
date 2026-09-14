package tui

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/LBYPatrick/warden/internal/app"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/charmbracelet/x/ansi"
	"github.com/muesli/termenv"
)

func TestAppearanceChoicesPersistAndRender(t *testing.T) {
	old := lipgloss.ColorProfile()
	lipgloss.SetColorProfile(termenv.TrueColor)
	defer lipgloss.SetColorProfile(old)
	a := app.New("test")
	a.Home = t.TempDir()
	a.NoColor = false
	m := newModel(a)
	if m.theme.Mode != "clear" {
		t.Fatal("default must be clear")
	}
	if _, err := os.Stat(themePath(a.Home)); !os.IsNotExist(err) {
		t.Fatal("opening TUI wrote preferences")
	}
	next, _ := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune("t")})
	m = next.(model)
	for mode := 0; mode < len(modes); mode++ {
		m.cursor = mode
		next, _ = m.Update(tea.KeyMsg{Type: tea.KeyEnter})
		m = next.(model)
		for i, preset := range presets {
			m.cursor = i + len(modes)
			next, _ = m.Update(tea.KeyMsg{Type: tea.KeyEnter})
			m = next.(model)
			if m.err != nil {
				t.Fatal(m.err)
			}
			if got := newModel(a).theme; got != m.theme || got.Preset != preset {
				t.Fatal("theme did not persist", got, m.theme)
			}
			for _, size := range [][2]int{{120, 32}, {80, 24}, {40, 12}, {20, 8}, {1, 1}} {
				m.width, m.height = size[0], size[1]
				for tab := range tabs {
					m.tab = tab
					view := m.View()
					if m.theme.Mode == "clear" {
						assertClearFrame(t, view, m.width, m.height)
					}
					if len(strings.Split(view, "\n")) != m.height {
						t.Fatal("incorrect frame height")
					}
					for _, line := range strings.Split(view, "\n") {
						if ansi.StringWidth(line) != m.width {
							t.Fatal("incorrect frame width", size, line)
						}
					}
				}
			}
			m.tab = 5
		}
	}
	info, err := os.Stat(themePath(a.Home))
	if err != nil || info.Mode().Perm() != 0600 {
		t.Fatal("theme file must be private", err)
	}
	m.width, m.height = 120, 32
	m.tab = 5
	if view := m.View(); !strings.Contains(view, "\x1b[") {
		t.Fatal("missing colors")
	}
	a.NoColor = true
	if view := m.View(); strings.Contains(view, "\x1b") {
		t.Fatal("NO_COLOR emitted ANSI")
	}
}
func TestThemeFailuresPreserveUserData(t *testing.T) {
	home := t.TempDir()
	os.MkdirAll(filepath.Join(home, ".warden"), 0700)
	path := themePath(home)
	os.WriteFile(path, []byte(`{"custom":{"keep":true},"mode":"dark","preset":"blue"}`), 0600)
	if err := saveTheme(home, theme{"light", "rose"}); err != nil {
		t.Fatal(err)
	}
	b, _ := os.ReadFile(path)
	var data map[string]json.RawMessage
	json.Unmarshal(b, &data)
	if !strings.Contains(string(data["custom"]), "true") {
		t.Fatal("lost unknown setting")
	}
	malformed := []byte("{invalid")
	os.WriteFile(path, malformed, 0600)
	if err := saveTheme(home, theme{"dark", "green"}); err == nil {
		t.Fatal("overwrote malformed settings")
	}
	b, _ = os.ReadFile(path)
	if string(b) != string(malformed) {
		t.Fatal("changed malformed file")
	}
	a := app.New("test")
	a.Home = t.TempDir()
	m := newModel(a)
	m.tab = 5
	m.cursor = 2
	os.WriteFile(filepath.Join(a.Home, ".warden"), []byte("blocked directory"), 0600)
	next, _ := m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	got := next.(model)
	if got.err == nil || got.theme != m.theme {
		t.Fatal("failed save changed appearance")
	}
}
func TestFilteredOverviewAndSettingsEscape(t *testing.T) {
	a := app.New("test")
	a.Home = t.TempDir()
	m := newModel(a)
	m.filter = "Restore"
	next, _ := m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	if next.(model).form != "restore" {
		t.Fatal("filtered action mismatch")
	}
	m.filter = ""
	m.tab = 2
	for range 2 {
		next, _ = m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune("t")})
		m = next.(model)
	}
	next, _ = m.Update(tea.KeyMsg{Type: tea.KeyEsc})
	if next.(model).tab != 2 {
		t.Fatal("settings did not return to previous section")
	}
}

func TestDryRunThemePreviewDoesNotWrite(t *testing.T) {
	a := app.New("test")
	a.Home = t.TempDir()
	a.Dry = true
	m := newModel(a)
	m.tab = 5
	m.cursor = 2
	next, _ := m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	m = next.(model)
	if m.theme.Mode != "light" || m.err != nil {
		t.Fatal("missing dry run preview", m.err)
	}
	if _, err := os.Stat(themePath(a.Home)); !os.IsNotExist(err) {
		t.Fatal("dry run wrote theme")
	}
}
