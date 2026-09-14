package tui

import (
	_ "embed"
	"encoding/json"
	"fmt"
	"strconv"
)

// Generated from the original Textual Theme for every saved preset and mode.
//
//go:embed theme_values.json
var themeJSON []byte
var themeValues = func() map[string]map[string]string {
	var values map[string]map[string]string
	_ = json.Unmarshal(themeJSON, &values)
	return values
}()

func blendColor(top, bottom string, amount float64) string {
	a, _ := strconv.ParseUint(top[1:], 16, 32)
	b, _ := strconv.ParseUint(bottom[1:], 16, 32)
	result := uint64(0)
	for _, shift := range []uint{16, 8, 0} {
		value := uint64(float64((a>>shift)&255)*amount + float64((b>>shift)&255)*(1-amount))
		result |= value << shift
	}
	return fmt.Sprintf("#%06X", result)
}
