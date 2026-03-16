.PHONY: help install uninstall clean build test format tidy
SHELL := /bin/bash
VERSION := $(shell cat VERSION 2>/dev/null | tr -d '\n' || echo "0.1.0")

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install warden and symlink to /usr/local/bin
	@bash scripts/install.sh

uninstall: ## Remove warden symlink and caches
	@bash scripts/uninstall.sh

clean: ## Remove .venv, caches, and build artifacts
	@rm -rf .venv __pycache__ .ruff_cache warden/__pycache__ dist build *.egg-info
	@echo "  Cleaned"

build: ## Verify the project runs
	@uv run python -m warden --help > /dev/null
	@echo "  Build OK"

test: ## Run tests
	@uv run python -m pytest tests/ -v

format: ## Run formatter and linter
	@bash tidy.sh

tidy: format ## Alias for format

setup: install ## Alias for install
