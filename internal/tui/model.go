// Package tui provides an Ashley-inspired interactive Warden dashboard.
package tui

import (
	"bytes"
	"os"
	"os/exec"
	"sort"
	"strings"

	"github.com/LBYPatrick/warden/internal/app"
	tea "github.com/charmbracelet/bubbletea"
)

type resultMsg struct {
	output string
	err    error
}
type model struct {
	app                                  *app.App
	config                               app.Config
	width, height, tab, cursor, offset   int
	filter, input, form, confirm, output string
	busy, filtering                      bool
	err                                  error
	theme                                theme
	previousTab                          int
}

var tabs = []string{"Overview", "Identities", "Packages", "Archives", "Maintenance", "Settings"}

func newModel(a *app.App) model {
	c, e := a.Load()
	t, themeErr := loadTheme(a.Home)
	if e == nil {
		e = themeErr
	}
	return model{app: a, config: c, width: 80, height: 24, err: e, theme: t}
}
func (m *model) changeTab(next int) {
	if next == 5 && m.tab != 5 {
		m.previousTab = m.tab
	}
	m.tab = next
}
func (m model) Init() tea.Cmd { return nil }
func (m model) items() []string {
	var items []string
	switch m.tab {
	case 0:
		items = []string{"Browse identities", "Browse packages", "Create a backup", "Restore an archive"}
	case 1:
		for name := range m.config.Identities {
			items = append(items, name)
		}
		sort.Strings(items)
	case 2:
		for mgr, section := range m.config.Packages {
			for kind, pkgs := range section {
				for _, p := range pkgs {
					items = append(items, mgr+" / "+kind+" / "+p)
				}
			}
		}
		for _, t := range m.config.Tools {
			items = append(items, "tool / "+t)
		}
		sort.Strings(items)
	case 3:
		items = []string{"Create backup · all modules", "Create backup · identities + SSH", "Create backup · packages", "Restore an archive"}
	case 4:
		items = []string{"Update Warden"}
		if m.app.Platform == "darwin" {
			items = append(items, "Mole clean", "Mole optimize", "Mole analyze", "Mole status")
		}
	}
	if m.tab == 5 {
		return append([]string{"Dark mode", "Light mode"}, presets...)
	}
	if m.filter == "" {
		return items
	}
	out := []string{}
	for _, item := range items {
		if strings.Contains(strings.ToLower(item), strings.ToLower(m.filter)) {
			out = append(out, item)
		}
	}
	return out
}
func (m model) operation(args ...string) tea.Cmd {
	a := *m.app
	return func() tea.Msg {
		var out bytes.Buffer
		a.Out = &out
		a.Err = &out
		a.NoColor = true
		o, e := a.Parse(args)
		if e == nil {
			e = a.Execute(o)
		}
		return resultMsg{out.String(), e}
	}
}
func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch v := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = v.Width
		m.height = v.Height
		return m, nil
	case resultMsg:
		m.busy = false
		m.confirm = ""
		m.output = v.output
		m.err = v.err
		c, e := m.app.Load()
		if e == nil {
			m.config = c
		} else if m.err == nil {
			m.err = e
		}
		return m, nil
	case tea.KeyMsg:
		key := v.String()
		if m.busy {
			if key == "ctrl+c" {
				return m, tea.Quit
			}
			return m, nil
		}
		if m.form != "" || m.filtering {
			switch key {
			case "esc":
				m.form = ""
				m.filtering = false
				m.input = ""
			case "enter":
				if m.filtering {
					m.filtering = false
				} else {
					if strings.TrimSpace(m.input) == "" {
						return m, nil
					}
					form := m.form
					m.form = ""
					m.confirm = form + ":" + m.input
					m.input = ""
				}
			case "backspace":
				if m.filtering {
					r := []rune(m.filter)
					if len(r) > 0 {
						m.filter = string(r[:len(r)-1])
					}
				} else {
					r := []rune(m.input)
					if len(r) > 0 {
						m.input = string(r[:len(r)-1])
					}
				}
			default:
				if v.Type == tea.KeyRunes {
					if m.filtering {
						m.filter += string(v.Runes)
						m.cursor = 0
					} else {
						m.input += string(v.Runes)
					}
				}
			}
			return m, nil
		}
		if m.confirm != "" {
			switch key {
			case "esc", "n":
				m.confirm = ""
			case "enter", "y":
				action := m.confirm
				m.confirm = ""
				m.busy = true
				m.err = nil
				m.output = ""
				if strings.HasPrefix(action, "switch:") {
					return m, m.operation("id", "switch", strings.TrimPrefix(action, "switch:"))
				}
				if strings.HasPrefix(action, "restore:") {
					return m, m.operation("restore", strings.TrimPrefix(action, "restore:"))
				}
				if strings.HasPrefix(action, "backup:") {
					return m, m.operation("backup", "-m", strings.TrimPrefix(action, "backup:"))
				}
				if action == "apply" {
					return m, m.operation("pkg", "apply")
				}
				if action == "update" {
					return m, m.operation("update")
				}
				if strings.HasPrefix(action, "mole:") {
					m.busy = false
					sub := strings.TrimPrefix(action, "mole:")
					exe, e := os.Executable()
					if e != nil {
						m.err = e
						return m, nil
					}
					args := []string{"mole", sub}
					if m.app.Dry {
						args = append(args, "--dry-run")
					}
					return m, tea.ExecProcess(exec.Command(exe, args...), func(e error) tea.Msg { return resultMsg{"Mole finished", e} })
				}
			}
			return m, nil
		}
		if m.output != "" || m.err != nil {
			switch key {
			case "esc", "enter":
				m.output = ""
				m.err = nil
				m.offset = 0
			case "down", "j":
				m.offset++
			case "up", "k":
				m.offset = max(0, m.offset-1)
			case "pgdown":
				m.offset += 10
			case "pgup":
				m.offset = max(0, m.offset-10)
			case "q", "ctrl+c":
				return m, tea.Quit
			}
			return m, nil
		}
		switch key {
		case "q", "ctrl+c":
			return m, tea.Quit
		case "tab", "right", "l":
			m.changeTab((m.tab + 1) % len(tabs))
			m.cursor = 0
			m.filter = ""
		case "shift+tab", "left", "h":
			m.changeTab((m.tab + len(tabs) - 1) % len(tabs))
			m.cursor = 0
			m.filter = ""
		case "1", "2", "3", "4", "5", "6":
			m.changeTab(int(key[0] - '1'))
			m.cursor = 0
			m.filter = ""
		case "up", "k":
			m.cursor = max(0, m.cursor-1)
		case "down", "j":
			m.cursor = min(max(0, len(m.items())-1), m.cursor+1)
		case "t":
			if m.tab != 5 {
				m.previousTab = m.tab
			}
			m.tab, m.cursor, m.filter = 5, 0, ""
		case "/":
			if m.tab != 5 {
				m.filtering = true
			}
		case "esc":
			if m.tab == 5 {
				m.tab, m.cursor = m.previousTab, 0
			}
			m.filter = ""
		case "r":
			c, e := m.app.Load()
			m.config = c
			m.err = e
		case "s":
			if m.tab == 2 {
				m.busy = true
				return m, m.operation("pkg", "scan")
			}
		case "a":
			if m.tab == 2 {
				m.confirm = "apply"
			}
		case "b":
			m.confirm = "backup:all"
		case "enter":
			items := m.items()
			if len(items) == 0 {
				return m, nil
			}
			m.cursor = min(m.cursor, len(items)-1)
			item := items[m.cursor]
			switch m.tab {
			case 5:
				next := m.theme
				if m.cursor < 2 {
					next.Mode = []string{"dark", "light"}[m.cursor]
				} else {
					next.Preset = presets[m.cursor-2]
				}
				if m.app.Dry {
					m.theme = next
				} else if e := saveTheme(m.app.Home, next); e != nil {
					m.err = e
				} else {
					m.theme = next
				}
			case 0:
				switch item {
				case "Browse identities":
					m.tab = 1
				case "Browse packages":
					m.tab = 2
				case "Create a backup":
					m.confirm = "backup:all"
				case "Restore an archive":
					m.form = "restore"
				}
				m.cursor = 0
			case 1:
				m.confirm = "switch:" + item
			case 3:
				if strings.HasPrefix(item, "Restore") {
					m.form = "restore"
				} else {
					mods := "all"
					if strings.Contains(item, "identities") {
						mods = "git,ssh"
					}
					if strings.Contains(item, "packages") {
						mods = "pkg"
					}
					m.confirm = "backup:" + mods
				}
			case 4:
				if item == "Update Warden" {
					m.confirm = "update"
				} else {
					m.confirm = "mole:" + strings.ToLower(strings.TrimPrefix(item, "Mole "))
				}
			}
		}
	}
	return m, nil
}

// Run starts the alternate-screen dashboard.
func Run(a *app.App) error { _, e := tea.NewProgram(newModel(a), tea.WithAltScreen()).Run(); return e }
