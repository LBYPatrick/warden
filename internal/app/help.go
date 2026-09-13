package app

import (
	"fmt"
	"strings"
)

type commandDoc struct {
	usage, description string
	options            [][2]string
}

var commandDocs = map[string]commandDoc{
	"id":            {"warden id <switch|list|show>", "Inspect or apply global Git identities.", nil},
	"id switch":     {"warden id switch NAME", "Apply name, email, SSH signing key, and derived SSH command globally.", nil},
	"id list":       {"warden id list [--names | --json]", "List configured identity targets.", [][2]string{{"--names", "Print one target name per line"}, {"--json", "Print identity JSON"}}},
	"id show":       {"warden id show [NAME] [--json]", "Show current Git settings or a target with its derived SSH command.", [][2]string{{"--json", "Print JSON without decorative output"}}},
	"pkg":           {"warden pkg <scan|apply|install|deps>", "Snapshot, install, and inspect your system packages.", nil},
	"pkg scan":      {"warden pkg scan", "Replace package/tool snapshots while preserving identities.", nil},
	"pkg apply":     {"warden pkg apply [-f]", "Install configured packages and developer tools; skip entries already present.", [][2]string{{"-f, --force", "Reinstall configured packages"}}},
	"pkg deps":      {"warden pkg deps [-o FILE]", "Export Homebrew dependencies, leaves, casks, and summary counts as JSON.", [][2]string{{"-o, --output FILE", "Write JSON to a file (default: stdout)"}}},
	"backup":        {"warden backup [-m MODULES] [-o FILE]", "Create a portable archive. Defaults to all modules; packages are scanned first.", [][2]string{{"-m MODULES", "git, ssh, pkg, or all (comma-separated)"}, {"-o, --output FILE", "Destination .tar.gz archive"}, {"--skip-scan", "Use the existing package snapshot"}, {"--include-missing", "Retain SSH hosts whose key files are missing"}}},
	"restore":       {"warden restore ARCHIVE [-m MODULES]", "Merge selected modules, reusing matching local key pairs.", [][2]string{{"-m MODULES", "Override modules auto-detected from archive"}}},
	"update":        {"warden update [VERSION]", "Install latest binary release, or choose an exact published X.Y.Z version.", nil},
	"mole":          {"warden mole <clean|optimize|analyze|status>", "macOS maintenance through Mole; installs via Homebrew if needed.", nil},
	"mole clean":    {"warden mole clean [--dry-run]", "Deep system cleanup. Dry run invokes Mole's native preview when installed.", nil},
	"mole optimize": {"warden mole optimize [--dry-run]", "Optimize system databases and services. Supports Mole's native preview.", nil},
	"mole analyze":  {"warden mole analyze [PATH]", "Open the interactive disk space explorer.", nil},
	"mole status":   {"warden mole status [--json]", "Show system health.", [][2]string{{"--json", "Machine-readable Mole status"}}},
	"tui":           {"warden tui", "Open the interactive dashboard. Tab changes sections; enter opens actions; q quits.", nil},
}

func (a *App) commandHelp(args []string) error {
	if len(args) == 0 {
		a.Help()
		return nil
	}
	key := args[0]
	if len(args) > 1 && (key == "id" || key == "pkg" || key == "mole") {
		key += " " + args[1]
	}
	if key == "pkg install" {
		return a.managerHelp(false)
	}
	doc, ok := commandDocs[key]
	if !ok {
		return fmt.Errorf("unknown command %q", key)
	}
	if strings.HasPrefix(key, "mole") && a.Platform != "darwin" {
		return fmt.Errorf("Mole requires macOS")
	}
	a.Header(key)
	a.Row("Usage", doc.usage)
	fmt.Fprintln(a.Out, "\n  "+doc.description)
	for _, row := range doc.options {
		a.Row(row[0], row[1])
	}
	fmt.Fprintln(a.Out, "\n  Global options: -c PATH  --dry-run  --no-color")
	return nil
}
func (a *App) managerHelp(anyPlatform bool) error {
	a.Header("Package managers")
	a.Row("Usage", "warden pkg install MANAGER:PKG [MANAGER:PKG ...]")
	for _, m := range managers {
		if !anyPlatform && m.platform != "" && m.platform != a.Platform {
			continue
		}
		status := "not installed"
		if _, e := a.LookPath(managerBinary(m)); e == nil {
			status = "available"
		}
		a.Row(m.name, status)
	}
	tools := []string{}
	for _, slug := range sortedKeys(toolScripts) {
		if slug == "xcode" && a.Platform != "darwin" {
			continue
		}
		tools = append(tools, slug)
	}
	a.Row("tool", strings.Join(tools, ", "))
	for _, row := range [][2]string{{"--save", "Save installed and already-present packages to config"}, {"--any", "Allow package managers for another platform"}, {"-f, --force", "Reinstall packages"}, {"--dry-run", "Preview without installing"}, {"-c PATH", "Config path"}, {"--no-color", "Plain terminal output"}} {
		a.Row(row[0], row[1])
	}
	return nil
}
