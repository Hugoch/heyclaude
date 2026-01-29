.PHONY: build clean release install dev

VERSION ?= 0.1.0

# Build the app
build:
	source .venv/bin/activate && pyinstaller HeyClaude.spec

# Clean build artifacts
clean:
	rm -rf build/ dist/HeyClaude dist/HeyClaude.app

# Build release ZIP
release:
	./scripts/release.sh $(VERSION)

# Install for development (run from source)
dev:
	source .venv/bin/activate && python -m heyclaude

# Install dependencies
install:
	python -m venv .venv
	source .venv/bin/activate && pip install -e ".[build]"
