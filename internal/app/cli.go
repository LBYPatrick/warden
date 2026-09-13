package app

import (
	"fmt"
	"strings"
)

// Options contains parsed CLI arguments shared with the TUI launcher.
type Options struct {
	Args                                                          []string
	Output, Modules                                               string
	Force, Save, Any, SkipScan, IncludeMissing, JSON, Names, Help bool
}

// Parse accepts global flags before or after subcommands.
func (a *App) Parse(args []string) (Options, error) {
	o := Options{}
	for i := 0; i < len(args); i++ {
		arg := args[i]
		if arg == "--" {
			o.Args = append(o.Args, args[i+1:]...)
			break
		}
		value := ""
		if len(arg) > 2 && (strings.HasPrefix(arg, "-c") || strings.HasPrefix(arg, "-m") || strings.HasPrefix(arg, "-o")) && !strings.HasPrefix(arg, "--") {
			value = arg[2:]
			arg = arg[:2]
		}
		if strings.HasPrefix(arg, "--") {
			if key, v, ok := strings.Cut(arg, "="); ok {
				arg = key
				if !contains([]string{"--config", "--output", "--modules"}, key) {
					return o, fmt.Errorf("%s does not accept a value", key)
				}
				value = v
			}
		}
		switch arg {
		case "-c", "--config", "-o", "--output", "-m", "--modules":
			if value == "" {
				i++
				if i >= len(args) {
					return o, fmt.Errorf("%s requires a value", arg)
				}
				value = args[i]
			}
			switch arg {
			case "-c", "--config":
				a.ConfigFile = value
			case "-o", "--output":
				o.Output = value
			default:
				o.Modules = value
			}
		case "--dry-run":
			a.Dry = true
		case "--no-color":
			a.NoColor = true
		case "-f", "--force":
			o.Force = true
		case "--save":
			o.Save = true
		case "--any":
			o.Any = true
		case "--skip-scan":
			o.SkipScan = true
		case "--include-missing":
			o.IncludeMissing = true
		case "--json":
			o.JSON = true
		case "--names":
			o.Names = true
		case "-h", "--help":
			o.Help = true
		case "--version", "-v":
			o.Args = []string{"version"}
			return o, nil
		default:
			if strings.HasPrefix(arg, "-") {
				return o, fmt.Errorf("unknown option %s", arg)
			}
			o.Args = append(o.Args, arg)
		}
	}
	return o, nil
}

// Help displays the complete command surface.
func (a *App) Help() {
	a.Header("Describe the system you live in")
	for _, row := range [][2]string{
		{"warden / tui", "Open the interactive dashboard"}, {"id list", "List configured identities [--names | --json]"}, {"id show [NAME]", "Inspect current Git settings or an identity"}, {"id switch NAME", "Apply a global Git identity"}, {"pkg scan", "Snapshot installed packages and developer tools"}, {"pkg apply [-f]", "Install the configured environment"}, {"pkg install SPEC…", "Install manager:package [--save] [--any]"}, {"pkg deps [-o FILE]", "Export Homebrew dependencies as JSON"}, {"backup [-m MODULES]", "Create archive [-o FILE] [--skip-scan]"}, {"restore ARCHIVE", "Merge archive contents [-m MODULES]"}, {"update [VERSION]", "Install latest release or pin X.Y.Z"}, {"mole ACTION", "macOS: clean, optimize, analyze [PATH], status [--json]"}} {
		if row[0] == "mole ACTION" && a.Platform != "darwin" {
			continue
		}
		a.Row(row[0], row[1])
	}
	fmt.Fprint(a.Out, "\n  Global options  -c PATH  --dry-run  --no-color  --version\n  Modules         all | git,ssh,pkg\n")
}

// Execute dispatches a parsed noninteractive invocation.
func (a *App) Execute(o Options) error {
	if o.Help || len(o.Args) == 0 {
		return a.commandHelp(o.Args)
	}
	args := o.Args
	cmd := args[0]
	args = args[1:]
	switch cmd {
	case "version":
		fmt.Fprintln(a.Out, "warden "+a.Version)
		return nil
	case "id":
		if len(args) == 0 {
			return a.commandHelp(o.Args)
		}
		sub := args[0]
		args = args[1:]
		if len(args) > 1 {
			return fmt.Errorf("too many identity arguments")
		}
		if sub == "switch" {
			if len(args) != 1 {
				return fmt.Errorf("usage: warden id switch NAME")
			}
			return a.Switch(args[0])
		}
		c, e := a.Load()
		if e != nil {
			return e
		}
		switch sub {
		case "list":
			if len(args) > 0 {
				return fmt.Errorf("id list takes no arguments")
			}
			if o.JSON {
				_, e = a.Out.Write(encode(c.Identities))
				return e
			}
			if !o.Names {
				a.Header("Identities")
			}
			for _, name := range sortedKeys(c.Identities) {
				if o.Names {
					fmt.Fprintln(a.Out, name)
				} else {
					id := c.Identities[name]
					a.Row(name, id["name"]+" <"+id["email"]+">")
				}
			}
			if len(c.Identities) == 0 && !o.Names {
				a.Row("No identities", "Add an identity to "+a.ConfigPath())
			}
			return nil
		case "show":
			if len(args) == 0 {
				fields := map[string]string{}
				for _, key := range []string{"user.name", "user.email", "user.signingkey", "core.sshCommand", "gpg.format", "commit.gpgsign"} {
					v, _ := a.Run([]string{"git", "config", "--global", "--get", key})
					fields[key] = v
				}
				if o.JSON {
					_, e = a.Out.Write(encode(fields))
					return e
				}
				a.Header("Current identity")
				for _, k := range sortedKeys(fields) {
					v := fields[k]
					if v == "" {
						v = "(not set)"
					}
					a.Row(k, v)
				}
				return nil
			}
			for _, name := range sortedKeys(c.Identities) {
				if strings.EqualFold(name, args[0]) {
					if o.JSON {
						_, e = a.Out.Write(encode(c.Identities[name]))
						return e
					}
					a.Header("Identity · " + name)
					for _, key := range sortedKeys(c.Identities[name]) {
						value := c.Identities[name][key]
						if key == "signing_key" {
							value = a.Expand(value)
						}
						a.Row(key, value)
					}
					if key, ok := c.Identities[name]["signing_key"]; ok {
						derived := a.sshCommand(key)
						if derived == "" {
							derived = "(default key, unset)"
						}
						a.Row("ssh_command (derived)", derived)
					}
					return nil
				}
			}
			return fmt.Errorf("identity %q not found", args[0])
		}
		return fmt.Errorf("unknown identity command %q", sub)
	case "pkg":
		if len(args) == 0 {
			return a.commandHelp(o.Args)
		}
		sub := args[0]
		args = args[1:]
		if sub != "install" && len(args) != 0 {
			return fmt.Errorf("pkg %s takes no positional arguments", sub)
		}
		switch sub {
		case "scan":
			c, e := a.Load()
			if e != nil {
				return e
			}
			c, e = a.Scan(c)
			if e != nil {
				return e
			}
			if e = a.Save(c); e != nil {
				return e
			}
			a.Success("Package snapshot ready")
			return nil
		case "apply":
			return a.Apply(o.Force)
		case "install":
			if len(args) == 0 {
				return a.managerHelp(o.Any)
			}
			return a.Install(args, o.Force, o.Save, o.Any)
		case "deps":
			return a.Deps(o.Output)
		}
		return fmt.Errorf("unknown package command %q", sub)
	case "backup":
		if len(args) != 0 {
			return fmt.Errorf("backup takes no positional arguments")
		}
		return a.Backup(o.Modules, o.Output, o.SkipScan, o.IncludeMissing)
	case "restore":
		if len(args) != 1 {
			return fmt.Errorf("usage: warden restore ARCHIVE [-m MODULES]")
		}
		return a.Restore(args[0], o.Modules)
	case "update":
		if len(args) > 1 {
			return fmt.Errorf("usage: warden update [VERSION]")
		}
		v := ""
		if len(args) == 1 {
			v = args[0]
		}
		return a.Update(v)
	case "mole":
		if a.Platform != "darwin" {
			return fmt.Errorf("Mole requires macOS")
		}
		if len(args) == 0 {
			return a.commandHelp(o.Args)
		}
		if !contains([]string{"clean", "optimize", "analyze", "status"}, args[0]) {
			return fmt.Errorf("unknown Mole command %q", args[0])
		}
		if len(args) > 2 || (len(args) > 1 && args[0] != "analyze") {
			return fmt.Errorf("unexpected Mole arguments")
		}
		if o.JSON {
			args = append(args, "--json")
		}
		_, lookupErr := a.LookPath("mo")
		if a.Dry {
			if lookupErr != nil {
				a.Row("Would set up", "Mole via Homebrew")
				a.Row("Would run", "mo "+strings.Join(args, " "))
				return nil
			}
			if args[0] == "clean" || args[0] == "optimize" {
				args = append(args, "--dry-run")
			}
		} else if lookupErr != nil {
			if e := a.ensureHomebrew(); e != nil {
				return e
			}
			if _, e := a.Run([]string{"brew", "install", "mole"}); e != nil {
				return e
			}
		}
		return a.runLive(append([]string{"mo"}, args...), 0)
	}
	return fmt.Errorf("unknown command %q; run warden --help", cmd)
}
