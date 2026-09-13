package app

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"time"

	"github.com/charmbracelet/lipgloss"
	"github.com/charmbracelet/x/term"
)

// App holds invocation settings and injectable process execution.
type App struct {
	Home, ConfigFile, Version string
	Platform                  string
	LookPath                  func(string) (string, error)
	Stream                    func([]string, time.Duration, io.Writer, io.Writer) error
	Dry, NoColor              bool
	Out, Err                  io.Writer
	Run                       func([]string) (string, error)
}

// New creates an application without changing the user's environment.
func New(version string) *App {
	home, _ := os.UserHomeDir()
	a := &App{Platform: runtime.GOOS, LookPath: lookupExecutable, Home: home, Version: version, Out: os.Stdout, Err: os.Stderr, NoColor: truthy(os.Getenv("WARDEN_NO_COLOR")) || os.Getenv("NO_COLOR") != "" || !term.IsTerminal(os.Stdout.Fd())}
	a.Run = func(args []string) (string, error) {
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Minute)
		defer cancel()
		binary, err := lookupExecutable(args[0])
		if err != nil {
			return "", err
		}
		c := exec.CommandContext(ctx, binary, args[1:]...)
		c.Env = mirrorEnv()
		var stderr bytes.Buffer
		c.Stderr = &stderr
		b, e := c.Output()
		if e != nil {
			return string(b), fmt.Errorf("%s: %w\n%s", args[0], e, strings.TrimSpace(string(b)+"\n"+stderr.String()))
		}
		return strings.TrimSpace(string(b)), nil
	}
	a.Stream = func(args []string, timeout time.Duration, out, errOut io.Writer) error {
		ctx := context.Background()
		cancel := func() {}
		if timeout > 0 {
			ctx, cancel = context.WithTimeout(ctx, timeout)
		}
		defer cancel()
		binary, err := lookupExecutable(args[0])
		if err != nil {
			return err
		}
		cmd := exec.CommandContext(ctx, binary, args[1:]...)
		cmd.Stdin = os.Stdin
		cmd.Stdout = out
		cmd.Stderr = errOut
		cmd.Env = mirrorEnv()
		return cmd.Run()
	}
	return a
}
func truthy(s string) bool {
	s = strings.ToLower(strings.TrimSpace(s))
	return s == "1" || s == "true" || s == "yes"
}
func (a *App) style(s, color string, bold bool) string {
	if a.NoColor {
		return s
	}
	return lipgloss.NewStyle().Foreground(lipgloss.Color(color)).Bold(bold).Render(s)
}

// Header renders a restrained Ashley-style command heading.
func (a *App) Header(s string) {
	fmt.Fprintf(a.Out, "\n  %s  %s\n\n", a.style("Warden", "#4A9EFF", true), a.style("/ "+s, "#999999", false))
}

// Row renders aligned label/value output without interpreting markup.
func (a *App) Row(k, v string) { fmt.Fprintf(a.Out, "  %-22s %s\n", k, v) }

// Success reports a completed operation.
func (a *App) Success(s string) {
	fmt.Fprintf(a.Out, "\n  %s %s\n\n", a.style("✓", "#3FB950", true), s)
}
func shellQuote(s string) string { return "'" + strings.ReplaceAll(s, "'", "'\"'\"'") + "'" }

// Switch applies an identity to global Git settings.
func (a *App) Switch(name string) error {
	c, e := a.Load()
	if e != nil {
		return e
	}
	var id map[string]string
	for _, k := range sortedKeys(c.Identities) {
		if strings.EqualFold(name, k) {
			name = k
			id = c.Identities[k]
			break
		}
	}
	if id == nil {
		return fmt.Errorf("identity %q not found", name)
	}
	a.Header("Identity · " + name)
	settings := [][2]string{}
	for _, p := range [][2]string{{"name", "user.name"}, {"email", "user.email"}, {"signing_key", "user.signingkey"}} {
		if v, ok := id[p[0]]; ok {
			if p[0] == "signing_key" {
				v = a.Expand(v)
			}
			settings = append(settings, [2]string{p[1], v})
		}
	}
	if key, ok := id["signing_key"]; ok {
		ssh := a.sshCommand(key)
		settings = append(settings, [2]string{"core.sshCommand", ssh})
	}
	settings = append(settings, [2]string{"gpg.format", "ssh"}, [2]string{"commit.gpgsign", "true"})
	for _, p := range settings {
		a.Row(p[0], p[1])
		if a.Dry {
			continue
		}
		args := []string{"git", "config", "--global", p[0], p[1]}
		if p[0] == "core.sshCommand" && p[1] == "" {
			args = []string{"git", "config", "--global", "--unset-all", p[0]}
		}
		if _, e = a.Run(args); e != nil {
			if p[0] == "core.sshCommand" && p[1] == "" {
				if _, getErr := a.Run([]string{"git", "config", "--global", "--get", p[0]}); getErr != nil {
					continue
				}
			}
			return e
		}
	}
	if a.Dry {
		a.Success("Preview complete; no changes made")
	} else {
		a.Success("Switched to " + name)
	}
	return nil
}

func (a *App) sshCommand(key string) string {
	priv := strings.TrimSuffix(a.Expand(key), ".pub")
	if priv == a.Expand("~/.ssh/id_ed25519") {
		return ""
	}
	return "ssh -o IdentitiesOnly=yes -i " + shellQuote(priv)
}
func (a *App) runLive(args []string, timeout time.Duration) error {
	if a.Stream != nil {
		return a.Stream(args, timeout, a.Out, a.Err)
	}
	out, err := a.Run(args)
	if out != "" {
		fmt.Fprintln(a.Out, out)
	}
	return err
}

// Find Homebrew-installed executables after bootstrapping, before shell startup files are reloaded.
func lookupExecutable(name string) (string, error) {
	found, err := exec.LookPath(name)
	if err == nil || strings.ContainsRune(name, os.PathSeparator) {
		return found, err
	}
	for _, dir := range []string{"/opt/homebrew/bin", "/usr/local/bin", "/home/linuxbrew/.linuxbrew/bin"} {
		p := filepath.Join(dir, name)
		if st, e := os.Stat(p); e == nil && !st.IsDir() && st.Mode()&0111 != 0 {
			return p, nil
		}
	}
	return "", err
}
