// Command warden manages development environments from a portable configuration.
package main

import (
	"errors"
	"fmt"
	"os"
	"os/exec"

	"github.com/LBYPatrick/warden/internal/app"
	"github.com/LBYPatrick/warden/internal/tui"
	"github.com/charmbracelet/x/term"
)

var version = "dev"

func main() {
	a := app.New(version)
	o, e := a.Parse(os.Args[1:])
	if e == nil {
		explicit := len(o.Args) > 0 && o.Args[0] == "tui"
		if !o.Help && (explicit || (len(o.Args) == 0 && term.IsTerminal(os.Stdin.Fd()) && term.IsTerminal(os.Stdout.Fd()))) {
			if explicit && len(o.Args) > 1 {
				e = fmt.Errorf("tui takes no positional arguments")
			} else if !term.IsTerminal(os.Stdin.Fd()) || !term.IsTerminal(os.Stdout.Fd()) {
				e = fmt.Errorf("TUI requires an interactive terminal")
			} else {
				e = tui.Run(a)
			}
		} else {
			e = a.Execute(o)
		}
	}
	if e != nil {
		fmt.Fprintln(os.Stderr, "\n  ✕ "+e.Error()+"\n")
		var exitErr *exec.ExitError
		if errors.As(e, &exitErr) && exitErr.ExitCode() > 0 {
			os.Exit(exitErr.ExitCode())
		}
		os.Exit(1)
	}
}
