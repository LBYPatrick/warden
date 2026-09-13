VERSION := $(shell cat VERSION)
.PHONY: build format test install uninstall clean release
build:
	go build -trimpath -ldflags="-s -w -X main.version=$(VERSION)" -o build/warden ./cmd/warden
format:
	bash tidy.sh
test:
	go test -race ./...
	go vet ./...
install: build
	mkdir -p "$(HOME)/.local/bin"
	install -m 755 build/warden "$(HOME)/.local/bin/.warden-new"
	mv -f "$(HOME)/.local/bin/.warden-new" "$(HOME)/.local/bin/warden"
	mkdir -p "$(HOME)/.local/share/man/man1" "$(HOME)/.local/share/bash-completion/completions" "$(HOME)/.zsh/completions"
	cp man/warden.1 "$(HOME)/.local/share/man/man1/warden.1"
	cp completions/warden.bash "$(HOME)/.local/share/bash-completion/completions/warden"
	cp completions/warden.zsh "$(HOME)/.zsh/completions/_warden"
uninstall:
	bash scripts/uninstall.sh
clean:
	rm -rf build dist
release:
	bash scripts/release/package.sh darwin arm64
	bash scripts/release/package.sh darwin amd64
	bash scripts/release/package.sh linux arm64
	bash scripts/release/package.sh linux amd64
