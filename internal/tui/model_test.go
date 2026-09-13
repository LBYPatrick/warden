package tui

import (
	"bytes"
	"strings"
	"testing"

	"github.com/LBYPatrick/warden/internal/app"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/x/ansi"
)

func TestResponsiveViewsAndNavigation(t *testing.T) {
	a := app.New("test")
	a.Home = t.TempDir()
	a.Out = &bytes.Buffer{}
	a.NoColor = true
	m := newModel(a)
	for _, size := range [][2]int{{120, 36}, {80, 24}, {40, 12}, {20, 8}} {
		m.width, m.height = size[0], size[1]
		for tab := range tabs {
			m.tab = tab
			view := m.View()
			lines := strings.Split(view, "\n")
			if len(lines) > m.height {
				t.Fatal("height overflow")
			}
			for _, line := range lines {
				if ansi.StringWidth(line) > m.width {
					t.Fatalf("width overflow %q", line)
				}
			}
		}
	}
	m.width = 80
	m.height = 24
	m.tab = 0
	next, _ := m.Update(tea.KeyMsg{Type: tea.KeyTab})
	m = next.(model)
	if m.tab != 1 {
		t.Fatal("tab did not navigate")
	}
	next, _ = m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'b'}})
	m = next.(model)
	if m.confirm != "backup:all" {
		t.Fatal("backup must be reviewed")
	}
	next, cmd := m.Update(tea.KeyMsg{Type: tea.KeyEsc})
	if next.(model).confirm != "" || cmd != nil {
		t.Fatal("escape must cancel")
	}
}
func TestRestoreFormAndEmptyIdentities(t *testing.T) {
	a := app.New("test")
	a.Home = t.TempDir()
	m := newModel(a)
	m.tab = 1
	if !strings.Contains(m.View(), "No entries") {
		t.Fatal("missing empty state")
	}
	m.tab = 3
	m.cursor = 3
	v, _ := m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	m = v.(model)
	if m.form != "restore" {
		t.Fatal("no restore form")
	}
	v, _ = m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune("/tmp/my backup.tar.gz")})
	m = v.(model)
	v, cmd := m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	m = v.(model)
	if cmd != nil || m.confirm != "restore:/tmp/my backup.tar.gz" {
		t.Fatal("restore must review the complete path")
	}
}
