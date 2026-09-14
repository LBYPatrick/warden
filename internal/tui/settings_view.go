package tui

import (
	"strings"

	"github.com/charmbracelet/x/ansi"
)

// Keep mode and accent selections in separate groups, with persistent headings
// while the accent list scrolls on shorter terminals.
func (m model) settingsList(f *frame, r rect, a appearance) {
	items := m.items()
	choice := func(index, y int, category string) {
		selected := (index < len(modes) && modes[index] == m.theme.Mode) || (index >= len(modes) && presets[index-len(modes)] == m.theme.Preset)
		marker := "○ "
		if selected {
			marker = "● "
		}
		prefix := "  "
		style := a.base
		if index == m.cursor {
			prefix = "› "
			style = a.selected
		}
		text := items[index]
		text = category + prefix + marker + strings.ToUpper(text[:1]) + text[1:]
		text = ansi.Truncate(text, r.w, "…")
		f.put(r.x, y, style.Render(text+strings.Repeat(" ", max(0, r.w-ansi.StringWidth(text)))))
	}
	heading := func(y int, text string) { f.put(r.x, y, a.title.Render(ansi.Truncate(text, r.w, "…"))) }
	if r.h < 7 {
		title, start, end := "Mode", 0, len(modes)
		if m.cursor >= len(modes) {
			title, start, end = "Accent color", len(modes), len(items)
		}
		if r.h == 1 {
			choice(m.cursor, r.y, title+" · ")
			return
		}
		heading(r.y, title)
		start = max(start, m.cursor-(r.h-2))
		for i := start; i < min(end, start+r.h-1); i++ {
			choice(i, r.y+1+i-start, "")
		}
		return
	}
	heading(r.y, "Mode")
	for i := range modes {
		choice(i, r.y+1+i, "")
	}
	heading(r.y+5, "Accent color")
	available := r.h - 6
	start := max(len(modes), m.cursor-available+1)
	for i := start; i < min(len(items), start+available); i++ {
		choice(i, r.y+6+i-start, "")
	}
}
