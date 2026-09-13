// Package tui provides an Ashley-inspired interactive Warden dashboard.
package tui

import (
	"bytes"
	"fmt"
	"os"
	"os/exec"
	"sort"
	"strings"

	"github.com/LBYPatrick/warden/internal/app"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/charmbracelet/x/ansi"
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
}

var tabs = []string{"Overview", "Identities", "Packages", "Archives", "Maintenance"}

func newModel(a *app.App) model {
	c, e := a.Load()
	return model{app: a, config: c, width: 80, height: 24, err: e}
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
			m.tab = (m.tab + 1) % len(tabs)
			m.cursor = 0
			m.filter = ""
		case "shift+tab", "left", "h":
			m.tab = (m.tab + len(tabs) - 1) % len(tabs)
			m.cursor = 0
			m.filter = ""
		case "1", "2", "3", "4", "5":
			m.tab = int(key[0] - '1')
			m.cursor = 0
			m.filter = ""
		case "up", "k":
			m.cursor = max(0, m.cursor-1)
		case "down", "j":
			m.cursor = min(max(0, len(m.items())-1), m.cursor+1)
		case "/":
			m.filtering = true
		case "esc":
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
			case 0:
				switch m.cursor {
				case 0:
					m.tab = 1
				case 1:
					m.tab = 2
				case 2:
					m.confirm = "backup:all"
				case 3:
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
				if m.cursor == 0 {
					m.confirm = "update"
				} else {
					m.confirm = "mole:" + strings.ToLower(strings.TrimPrefix(item, "Mole "))
				}
			}
		}
	}
	return m, nil
}
func (m model) paint(s, color string, bold bool) string {
	if m.app.NoColor {
		return s
	}
	return lipgloss.NewStyle().Foreground(lipgloss.Color(color)).Bold(bold).Render(s)
}
func (m model) View() string {
	w, h := max(1, m.width), max(1, m.height)
	if w < 38 || h < 12 {
		return ansi.Truncate("Warden · enlarge terminal (38×12) · q quit", w, "")
	}
	rows := make([]string, h)
	for i := range rows {
		rows[i] = strings.Repeat(" ", w)
	}
	put := func(y int, s string) {
		if y >= 0 && y < h {
			rows[y] = ansi.Truncate(s, w, "")
		}
	}
	put(0, m.paint("  Warden v"+m.app.Version+"  /  "+tabs[m.tab], "#EDEDED", true))
	nav := "  "
	for i, t := range tabs {
		label := fmt.Sprintf("%d %s", i+1, t)
		if i == m.tab {
			label = m.paint("["+label+"]", "#4A9EFF", true)
		}
		nav += label + "  "
	}
	if w < 85 {
		nav = fmt.Sprintf("  ‹  %d / %d   %s  ›", m.tab+1, len(tabs), tabs[m.tab])
	}
	put(2, nav)
	footer := "  ←→ Sections  ↑↓ Move  enter Open  / Filter  q Quit"
	if m.tab == 2 {
		footer = "  s Scan  a Apply  / Filter  r Refresh  ←→ Sections  q Quit"
	}
	content := []string{}
	if m.busy {
		content = []string{"Working…", "", "The result will appear here when the operation finishes."}
	}
	if m.confirm != "" {
		content = []string{"Review action", "", m.confirm, "", "This will update the selected configuration or system state.", "Press enter to proceed, or esc to go back."}
		if m.app.Dry {
			content[4] = "Dry run is enabled. This previews the operation."
		}
		footer = "  enter Proceed  esc Cancel"
	}
	if m.form != "" {
		content = []string{"Restore an archive", "", "Archive path", "> " + m.input + "▏", "", "Existing identities, SSH hosts, and packages will be merged."}
		footer = "  enter Review  esc Cancel"
	}
	if m.output != "" || m.err != nil {
		body := m.output
		if m.err != nil {
			body += "\nError: " + m.err.Error()
		}
		content = strings.Split(ansi.Wrap(body, w-6, ""), "\n")
		offset := min(m.offset, max(0, len(content)-(h-8)))
		content = content[offset:]
		footer = "  ↑↓ Scroll  enter / esc Back  q Quit"
	}
	if len(content) > 0 {
		put(4, m.paint("  ╭"+strings.Repeat("─", w-6)+"╮", "#3E3E3E", false))
		for i := 0; i < h-8; i++ {
			line := ""
			if i < len(content) {
				line = content[i]
			}
			put(5+i, "  │ "+ansi.Truncate(line, w-8, "…"))
		}
		put(h-3, m.paint("  ╰"+strings.Repeat("─", w-6)+"╯", "#3E3E3E", false))
	} else {
		items := m.items()
		heading := tabs[m.tab]
		if m.tab == 0 {
			heading = "Your environment, in one place"
		}
		put(4, "  "+m.paint(heading, "#4A9EFF", true))
		put(5, "  "+m.paint(m.app.ConfigPath(), "#999999", false))
		start := max(0, m.cursor-(h-12))
		limit := h - 11
		for i := start; i < min(len(items), start+limit); i++ {
			prefix := "    "
			line := items[i]
			if i == m.cursor {
				prefix = "  › "
				line = m.paint(line, "#4A9EFF", true)
			}
			if w >= 95 && (m.tab == 1 || m.tab == 2) {
				line = ansi.Truncate(line, w/2-8, "…")
			}
			put(7+i-start, prefix+line)
		}
		if len(items) == 0 {
			put(8, "  No entries. "+map[int]string{1: "Add identities to your config.", 2: "Press s to scan installed packages."}[m.tab])
		}
		if m.filter != "" || m.filtering {
			put(h-3, "  Filter: "+m.filter+"▏")
		} else if m.tab == 0 {
			count := 0
			for _, sec := range m.config.Packages {
				for _, p := range sec {
					count += len(p)
				}
			}
			put(h-3, fmt.Sprintf("  %d identities   %d packages   %d tools", len(m.config.Identities), count, len(m.config.Tools)))
		} else if m.tab == 1 && len(items) > 0 {
			selected := items[min(m.cursor, len(items)-1)]
			id := m.config.Identities[selected]
			put(h-3, "  "+id["name"]+" <"+id["email"]+">")
		}
	}
	if len(content) == 0 && w >= 95 && (m.tab == 0 || m.tab == 1 || m.tab == 2) {
		x := w / 2
		right := []string{"Selection", ""}
		items := m.items()
		if len(items) > 0 {
			item := items[min(m.cursor, len(items)-1)]
			if m.tab == 0 {
				right = []string{"Environment", "", fmt.Sprintf("%d identities", len(m.config.Identities)), fmt.Sprintf("%d package managers", len(m.config.Packages)), fmt.Sprintf("%d developer tools", len(m.config.Tools)), "", "Selected action", item, ""}
				descriptions := []string{"Inspect and switch your global Git identity.", "Snapshot installed software or apply your saved environment.", "Archive identities, SSH keys, packages, and tools.", "Merge a portable archive into this computer."}
				right = append(right, strings.Split(ansi.Wrap(descriptions[min(m.cursor, 3)], w-x-4, ""), "\n")...)
			} else if m.tab == 1 {
				id := m.config.Identities[item]
				right = append(right, item, "", "Name", id["name"], "", "Email", id["email"], "", "Signing key", id["signing_key"], "", "enter  Switch identity")
			} else {
				right = append(right, strings.Split(item, " / ")...)
				right = append(right, "", "s  Scan this computer", "a  Apply configuration")
			}
		}
		for y := 4; y < h-4; y++ {
			left := ansi.Truncate(rows[y], x-2, "")
			left += strings.Repeat(" ", max(0, x-2-ansi.StringWidth(left)))
			text := ""
			if y-4 < len(right) {
				text = right[y-4]
			}
			rows[y] = left + m.paint("│ ", "#3E3E3E", false) + ansi.Truncate(text, w-x-2, "…")
		}
	}
	if len(content) == 0 {
		border := func(s string) string { return m.paint(s, "#3E3E3E", false) }
		put(3, " "+border("╭"+strings.Repeat("─", w-4)+"╮"))
		for y := 4; y < h-2; y++ {
			inside := ansi.Cut(rows[y], 2, w-2)
			inside += strings.Repeat(" ", max(0, w-4-ansi.StringWidth(inside)))
			rows[y] = " " + border("│") + inside + border("│") + " "
		}
		put(h-2, " "+border("╰"+strings.Repeat("─", w-4)+"╯"))
	}
	if m.app.Dry {
		footer = "  DRY RUN · " + strings.TrimSpace(footer)
	}
	put(h-1, m.paint(footer, "#999999", false))
	if !m.app.NoColor {
		for i, row := range rows {
			bg := "#1E1E1E"
			if i == 0 || i == h-1 {
				bg = "#2A323C"
			}
			style := lipgloss.NewStyle().Background(lipgloss.Color(bg)).Foreground(lipgloss.Color("#EDEDED"))
			rows[i] = style.Render(row + strings.Repeat(" ", max(0, w-ansi.StringWidth(row))))
		}
	}
	return strings.Join(rows, "\n")
}

// Run starts the alternate-screen dashboard.
func Run(a *app.App) error { _, e := tea.NewProgram(newModel(a), tea.WithAltScreen()).Run(); return e }
