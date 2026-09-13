package app

import (
	"archive/tar"
	"bytes"
	"compress/gzip"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
	"time"
)

func stdin() *os.File { return os.Stdin }

var releaseVersion = regexp.MustCompile(`^[0-9]+\.[0-9]+\.[0-9]+(-[a-z]+\.[0-9]+)?$`)

func fetch(url string, limit int64) ([]byte, error) {
	client := http.Client{Timeout: 2 * time.Minute}
	r, e := client.Get(url)
	if e != nil {
		return nil, e
	}
	defer r.Body.Close()
	if r.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("download %s: HTTP %d", url, r.StatusCode)
	}
	b, e := io.ReadAll(io.LimitReader(r.Body, limit+1))
	if int64(len(b)) > limit {
		return nil, fmt.Errorf("download exceeds size limit")
	}
	return b, e
}

// Update atomically replaces the executable from a checksum-verified release.
func (a *App) Update(version string) error {
	version = strings.TrimPrefix(version, "v")
	if version != "" && !releaseVersion.MatchString(version) {
		return fmt.Errorf("invalid release version %q; use X.Y.Z (branch updates are no longer supported)", version)
	}
	if a.Dry {
		if version == "" {
			version = "latest"
		}
		a.Row("Would install", "Warden "+version+" binary release")
		return nil
	}
	repo := os.Getenv("WARDEN_REPO")
	if repo == "" {
		repo = "LBYPatrick/warden"
	}
	if !regexp.MustCompile(`^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$`).MatchString(repo) {
		return fmt.Errorf("invalid WARDEN_REPO")
	}
	if version == "" {
		b, e := fetch("https://api.github.com/repos/"+repo+"/releases/latest", 1<<20)
		if e != nil {
			return e
		}
		var data struct {
			Tag string `json:"tag_name"`
		}
		if e = json.Unmarshal(b, &data); e != nil {
			return e
		}
		version = strings.TrimPrefix(data.Tag, "v")
		if !releaseVersion.MatchString(version) {
			return fmt.Errorf("invalid latest release version")
		}
	}
	name := fmt.Sprintf("warden-%s-%s-%s.tar.gz", version, runtime.GOOS, runtime.GOARCH)
	url := "https://github.com/" + repo + "/releases/download/v" + version + "/"
	if truthy(os.Getenv("WARDEN_USE_CN")) {
		url = mirrorScript(url)
	}
	a.Header("Update")
	a.Row("Release", version)
	data, e := fetch(url+name, 128<<20)
	if e != nil {
		return e
	}
	checksum, e := fetch(url+name+".sha256", 1024)
	if e != nil {
		return e
	}
	fields := strings.Fields(string(checksum))
	sum := sha256.Sum256(data)
	if len(fields) != 2 || fields[1] != name || !strings.EqualFold(fields[0], hex.EncodeToString(sum[:])) {
		return fmt.Errorf("release checksum mismatch")
	}
	gz, e := gzip.NewReader(bytes.NewReader(data))
	if e != nil {
		return e
	}
	defer gz.Close()
	tr := tar.NewReader(gz)
	var binary []byte
	for {
		h, err := tr.Next()
		if err == io.EOF {
			break
		}
		if err != nil {
			return err
		}
		if h.Name != "warden" {
			continue
		}
		if binary != nil || h.Typeflag != tar.TypeReg || h.Size > 128<<20 {
			return fmt.Errorf("invalid executable in release")
		}
		binary, err = io.ReadAll(tr)
		if err != nil {
			return err
		}
	}
	if len(binary) == 0 {
		return fmt.Errorf("release has no warden executable")
	}
	dest, e := os.Executable()
	if e != nil {
		return e
	}
	dest, e = filepath.EvalSymlinks(dest)
	if e != nil {
		return e
	}
	candidate, e := os.CreateTemp(filepath.Dir(dest), ".warden-update-*")
	if e != nil {
		return e
	}
	p := candidate.Name()
	candidate.Close()
	defer os.Remove(p)
	if e = os.WriteFile(p, binary, 0755); e != nil {
		return e
	}
	if e = os.Chmod(p, 0755); e != nil {
		return e
	}
	actual, e := a.Run([]string{p, "--version"})
	if e != nil {
		return e
	}
	if strings.TrimSpace(actual) != "warden "+version {
		return fmt.Errorf("downloaded binary version mismatch")
	}
	if e = os.Rename(p, dest); e != nil {
		return e
	}
	a.Success("Updated to " + version)
	return nil
}
