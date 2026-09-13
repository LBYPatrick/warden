package app

import "strings"

type sshBlock struct {
	name  string
	lines []string
}

func parseSSH(s string) ([]string, []sshBlock) {
	var pre []string
	var blocks []sshBlock
	for _, line := range strings.Split(strings.TrimSuffix(s, "\n"), "\n") {
		f := strings.Fields(line)
		if len(f) > 1 && (strings.EqualFold(f[0], "Host") || strings.EqualFold(f[0], "Match")) {
			blocks = append(blocks, sshBlock{name: strings.ToLower(f[0]) + " " + strings.Join(f[1:], " ")})
		}
		if len(blocks) == 0 {
			pre = append(pre, line)
		} else {
			i := len(blocks) - 1
			blocks[i].lines = append(blocks[i].lines, line)
		}
	}
	return pre, blocks
}
func mergeSSH(existing, incoming string) string {
	if strings.TrimSpace(existing) == "" {
		return incoming
	}
	pre, blocks := parseSSH(existing)
	_, in := parseSSH(incoming)
	for _, b := range in {
		found := false
		for i := range blocks {
			if blocks[i].name == b.name {
				blocks[i] = b
				found = true
				break
			}
		}
		if !found {
			blocks = append(blocks, b)
		}
	}
	for _, b := range blocks {
		pre = append(pre, b.lines...)
	}
	return strings.Join(pre, "\n") + "\n"
}
func rewriteSSH(s string, convert func(string) (string, error)) (string, error) {
	lines := strings.Split(s, "\n")
	for i, line := range lines {
		trim := strings.TrimSpace(line)
		f := strings.Fields(strings.Replace(trim, "=", " ", 1))
		if len(f) < 2 || !strings.EqualFold(f[0], "IdentityFile") {
			continue
		}
		value := strings.TrimSpace(trim[len(f[0]):])
		value = strings.TrimSpace(strings.TrimPrefix(value, "="))
		value, suffix := sshValue(value)
		p, e := convert(value)
		if e != nil {
			return "", e
		}
		if strings.ContainsAny(p, " \t") {
			p = "\"" + strings.ReplaceAll(p, "\"", "\\\"") + "\""
		}
		lines[i] = line[:len(line)-len(strings.TrimLeft(line, " \t"))] + "IdentityFile " + p + suffix
	}
	return strings.Join(lines, "\n"), nil
}

// sshValue separates a quoted or bare path from an inline comment.
func sshValue(s string) (string, string) {
	if s == "" {
		return "", ""
	}
	quote := byte(0)
	start := 0
	if s[0] == '"' || s[0] == 39 {
		quote = s[0]
		start = 1
	}
	var value strings.Builder
	for i := start; i < len(s); i++ {
		ch := s[i]
		if ch == '\\' && i+1 < len(s) && quote != 0 {
			i++
			value.WriteByte(s[i])
			continue
		}
		if quote != 0 && ch == quote {
			return value.String(), s[i+1:]
		}
		if quote == 0 && (ch == ' ' || ch == '\t') {
			return value.String(), s[i:]
		}
		value.WriteByte(ch)
	}
	return value.String(), ""
}
