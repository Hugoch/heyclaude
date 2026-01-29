#!/bin/bash
# Build and package HeyClaude for release

set -e

VERSION="${1:-0.1.0}"
DIST_DIR="dist"
APP_NAME="HeyClaude"
ZIP_NAME="${APP_NAME}-${VERSION}.zip"

echo "Building HeyClaude v${VERSION}..."

# Activate venv and build
source .venv/bin/activate
rm -rf dist/HeyClaude dist/HeyClaude.app build/
pyinstaller HeyClaude.spec

# Create ZIP for distribution
cd "$DIST_DIR"
zip -r "$ZIP_NAME" "${APP_NAME}.app"
cd ..

# Calculate SHA256
SHA256=$(shasum -a 256 "$DIST_DIR/$ZIP_NAME" | awk '{print $1}')

echo ""
echo "=== Release Built ==="
echo "File: $DIST_DIR/$ZIP_NAME"
echo "SHA256: $SHA256"
echo ""
echo "Next steps:"
echo "1. Create GitHub release with tag v${VERSION}"
echo "2. Upload $DIST_DIR/$ZIP_NAME to the release"
echo "3. Update the cask formula with the new version and SHA256"
