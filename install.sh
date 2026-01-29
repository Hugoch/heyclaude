#!/bin/bash
# HeyClaude Installation Script

set -e

echo "🔔 HeyClaude Installer"
echo "======================"
echo ""

# Check for Homebrew
if ! command -v brew &> /dev/null; then
    echo "❌ Homebrew not found. Please install Homebrew first:"
    echo "   https://brew.sh"
    exit 1
fi

# Install terminal-notifier if not present
if ! command -v terminal-notifier &> /dev/null; then
    echo "📦 Installing terminal-notifier..."
    brew install terminal-notifier
else
    echo "✓ terminal-notifier already installed"
fi

# Create virtual environment if not in one
if [ -z "$VIRTUAL_ENV" ]; then
    echo ""
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
    source .venv/bin/activate
fi

# Install dependencies
echo ""
echo "📦 Installing Python dependencies..."
pip install -e ".[build]"

# Create config directory
echo ""
echo "📁 Creating config directory..."
mkdir -p ~/.heyclaude

# Install hook
echo ""
echo "🔗 Installing Claude Code hook..."
HOOK_DIR="$HOME/.claude/hooks"
SETTINGS_FILE="$HOME/.claude/settings.json"

mkdir -p "$HOOK_DIR"

# Copy hook script
cp hooks/heyclaude-hook.sh "$HOOK_DIR/"
chmod +x "$HOOK_DIR/heyclaude-hook.sh"

# Update settings.json
if [ -f "$SETTINGS_FILE" ]; then
    # Use Python to merge JSON
    python3 << 'EOF'
import json
from pathlib import Path

settings_path = Path.home() / ".claude" / "settings.json"
hook_path = Path.home() / ".claude" / "hooks" / "heyclaude-hook.sh"

with open(settings_path) as f:
    settings = json.load(f)

if "hooks" not in settings:
    settings["hooks"] = {}

settings["hooks"]["idle_prompt"] = [
    {
        "type": "command",
        "command": str(hook_path),
    }
]

with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2)

print(f"✓ Hook configured in {settings_path}")
EOF
else
    # Create new settings file
    cat > "$SETTINGS_FILE" << EOF
{
  "hooks": {
    "idle_prompt": [
      {
        "type": "command",
        "command": "$HOME/.claude/hooks/heyclaude-hook.sh"
      }
    ]
  }
}
EOF
    echo "✓ Created settings file with hook"
fi

echo ""
echo "✅ Installation complete!"
echo ""
echo "To run HeyClaude:"
echo "  heyclaude"
echo ""
echo "Or build the .app bundle:"
echo "  python setup.py py2app"
echo ""
echo "Then move dist/HeyClaude.app to /Applications/"
