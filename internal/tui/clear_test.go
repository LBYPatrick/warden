package tui

import (
	"github.com/charmbracelet/x/cellbuf"
	"testing"
)

func assertClearFrame(t *testing.T, view string, w, h int) {
	t.Helper()
	b := cellbuf.NewBuffer(w, h)
	cellbuf.SetContent(b, view)
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			c := b.Cell(x, y)
			if c != nil && (c.Style.Bg != nil || c.Style.Attrs&cellbuf.ReverseAttr != 0) {
				t.Fatalf("opaque cell at %d,%d: %+v", x, y, c.Style)
			}
		}
	}
}
