package tui

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/lipgloss"
	"github.com/charmbracelet/x/ansi"
)

type appearance struct{ base, border, title, muted, selected, panel lipgloss.Style }

func (m model) appearance() appearance {
	v := themeValues[m.theme.Mode+"-"+m.theme.Preset]
	if v == nil {
		v = themeValues["dark-blue"]
	}
	contrast := "#FFFFFF"
	if m.theme.Mode == "light" {
		contrast = "#000000"
	}
	base := lipgloss.NewStyle()
	if m.app.NoColor {
		return appearance{base, base, base.Bold(true), base, base.Bold(true), base}
	}
	bg, accent := v["surface"], v["accent"]
	base = base.Background(lipgloss.Color(bg)).Foreground(lipgloss.Color(blendColor(contrast, bg, .87)))
	return appearance{base, base.Foreground(lipgloss.Color(v["surface-lighten-2"])), base.Foreground(lipgloss.Color(accent)).Bold(true), base.Foreground(lipgloss.Color(blendColor(contrast, bg, .60))), base.Background(lipgloss.Color(blendColor(accent, bg, .20))).Bold(true), base.Background(lipgloss.Color(v["panel"]))}
}
func label(s string) string {
	if s == "" {
		return "—"
	}
	return s
}
func (m model) details() string {
	items := m.items()
	if len(items) == 0 {
		return "No selection"
	}
	item := items[min(m.cursor, len(items)-1)]
	switch m.tab {
	case 0:
		descriptions := []string{"Inspect and switch your global Git identity.", "Snapshot installed software or apply your saved environment.", "Archive identities, SSH keys, packages, and tools.", "Merge a portable archive into this computer."}
		// Filtering changes the index; use the action name to select its description.
		actions := []string{"Browse identities", "Browse packages", "Create a backup", "Restore an archive"}
		description := ""
		for i, action := range actions {
			if action == item {
				description = descriptions[i]
			}
		}
		return fmt.Sprintf("Your environment\n\n%d identities\n%d package managers\n%d developer tools\n\n%s\n\n%s", len(m.config.Identities), len(m.config.Packages), len(m.config.Tools), item, description)
	case 1:
		id := m.config.Identities[item]
		return item + "\n\nName\n" + label(id["name"]) + "\n\nEmail\n" + label(id["email"]) + "\n\nSigning key\n" + label(id["signing_key"]) + "\n\nenter  Review identity switch"
	case 2:
		return "Package details\n\n" + strings.ReplaceAll(item, " / ", "\n") + "\n\ns  Scan this computer\na  Apply configuration"
	case 3:
		return "Portable archives\n\nBack up your environment or restore it on another computer.\n\nExisting identities, SSH hosts, and packages are merged.\n\nenter  Review action"
	case 4:
		return "Maintenance\n\n" + item + "\n\nReview the action before making changes to this computer."
	case 5:
		return "Appearance\n\n" + strings.ToUpper(m.theme.Mode[:1]) + m.theme.Mode[1:] + " mode\n" + strings.ToUpper(m.theme.Preset[:1]) + m.theme.Preset[1:] + " accent\n\nChanges apply immediately and are saved for your next session.\n\nChoose a mode or accent, then press enter."
	}
	return ""
}
func (m model) View() string {
	w, h := max(1, m.width), max(1, m.height)
	a := m.appearance()
	f := newFrame(w, h, a.base)
	if w < 38 || h < 12 {
		f.text(rect{0, 0, w, h}, "Warden · enlarge terminal (38×12) · q quit", a.muted, 0)
		return f.String()
	}
	f.fill(rect{0, 0, w, 1}, a.panel)
	f.put(2, 0, a.panel.Bold(true).Render(ansi.Truncate("Warden v"+m.app.Version+"  /  "+tabs[m.tab], w-4, "…")))
	// Match Ashley's sidebar and rounded detail panel; collapse the sidebar on
	// narrow terminals so action text and forms retain useful space.
	pane := rect{2, 3, w - 4, h - 5}
	if w >= 78 {
		sidebar := min(28, w/4)
		f.put(2, 3, a.title.Render("Workspace"))
		for i, tab := range tabs {
			style := a.base
			prefix := "  "
			if i == m.tab {
				style = a.selected
				prefix = "› "
			}
			text := ansi.Truncate(fmt.Sprintf("%s%d  %s", prefix, i+1, tab), sidebar, "")
			f.put(2, 5+i, style.Render(text+strings.Repeat(" ", max(0, sidebar-ansi.StringWidth(text)))))
		}
		if h >= 19 {
			f.text(rect{3, 14, sidebar - 2, 3}, "tab  Next section\nt    Appearance\nr    Refresh", a.muted, 0)
		}
		pane = rect{sidebar + 5, 2, w - sidebar - 7, h - 4}
	} else {
		f.put(2, 2, a.title.Render(fmt.Sprintf("‹  %d/%d  %s  ›", m.tab+1, len(tabs), tabs[m.tab])))
	}
	f.box(pane, a.border)
	inner := rect{pane.x + 2, pane.y + 1, pane.w - 4, pane.h - 2}
	footer := "enter Open  ↑↓ Move  tab Sections  t Theme  q Quit"
	if m.tab == 2 {
		footer = "s Scan  a Apply  / Filter  tab Sections  t Theme  q Quit"
	}
	if m.tab == 5 {
		footer = "enter Select  ↑↓ Move  esc Done  tab Sections  q Quit"
	}
	var content string
	switch {
	case m.err != nil || m.output != "":
		content = m.output
		if m.err != nil {
			content += "\nError: " + m.err.Error()
		}
		footer = "↑↓ Scroll  enter / esc Back  q Quit"
	case m.busy:
		content = "Working…\n\nThe result will appear here when the operation finishes."
	case m.confirm != "":
		explanation := "This updates the selected configuration or system state."
		if m.app.Dry {
			explanation = "Dry run is enabled. This previews the operation."
		}
		content = "Review action\n\n" + m.confirm + "\n\n" + explanation + "\n\nPress enter to proceed, or esc to go back."
		footer = "enter Proceed  esc Cancel"
	case m.form != "":
		content = "Restore an archive\n\nArchive path\n› " + m.input + "▏\n\nExisting identities, SSH hosts, and packages will be merged."
		footer = "enter Review  esc Cancel"
	}
	if content != "" {
		lines := strings.Split(ansi.Wrap(content, inner.w, ""), "\n")
		offset := min(m.offset, max(0, len(lines)-inner.h))
		f.text(inner, content, a.base, offset)
	} else {
		f.put(inner.x, inner.y, a.title.Render(tabs[m.tab]))
		subtitle := m.app.ConfigPath()
		if m.app.Home != "" {
			subtitle = strings.Replace(subtitle, m.app.Home, "~", 1)
		}
		if m.tab == 5 {
			subtitle = "Choose a mode or accent · enter to apply"
		}
		f.put(inner.x, inner.y+1, a.muted.Render(ansi.Truncate(subtitle, inner.w, "…")))
		list := rect{inner.x, inner.y + 3, inner.w, max(1, inner.h-4)}
		if w >= 110 {
			list.w = min(40, inner.w/2)
			detail := rect{list.x + list.w + 3, list.y, inner.w - list.w - 3, list.h}
			for y := list.y; y < list.y+list.h; y++ {
				f.put(detail.x-2, y, a.border.Render("│"))
			}
			f.text(detail, m.details(), a.base, 0)
		}
		items := m.items()
		if m.tab == 5 {
			m.settingsList(f, list, a)
		} else {
			start := max(0, m.cursor-list.h+1)
			for i := start; i < min(len(items), start+list.h); i++ {
				text := items[i]
				prefix := "  "
				style := a.base

				if i == m.cursor {
					prefix = "› "
					style = a.selected
				}
				text = ansi.Truncate(prefix+text, list.w, "…")
				f.put(list.x, list.y+i-start, style.Render(text+strings.Repeat(" ", max(0, list.w-ansi.StringWidth(text)))))
			}
		}
		if len(items) == 0 {
			f.text(list, "No entries. "+map[int]string{1: "Add identities to your config.", 2: "Press s to scan installed packages."}[m.tab], a.muted, 0)
		}
		status := ""
		if m.filter != "" || m.filtering {
			status = "Filter: " + m.filter + "▏"
		} else if m.tab == 5 {
			status = m.theme.Mode + " / " + m.theme.Preset + " · enter to apply"
			if m.app.Dry {
				status += " · preview only"
			}
		} else if m.tab == 1 && len(items) > 0 {
			id := m.config.Identities[items[min(m.cursor, len(items)-1)]]
			status = id["name"] + " <" + id["email"] + ">"
		}
		f.put(inner.x, inner.y+inner.h-1, a.muted.Render(ansi.Truncate(status, inner.w, "…")))
	}
	if m.app.Dry {
		footer = "DRY RUN · " + footer
	}
	f.fill(rect{0, h - 1, w, 1}, a.panel)
	f.put(1, h-1, a.panel.Render(ansi.Truncate(footer, w-2, "…")))
	if !m.app.NoColor {
		x := 1
		for _, binding := range strings.Split(footer, "  ") {
			parts := strings.Fields(binding)
			if len(parts) > 0 && x+ansi.StringWidth(parts[0]) < w-1 {
				f.put(x, h-1, a.title.Background(a.panel.GetBackground()).Render(parts[0]))
			}
			x += ansi.StringWidth(binding) + 2
		}
	}
	if m.app.NoColor {
		return ansi.Strip(f.String())
	}
	return f.String()
}
