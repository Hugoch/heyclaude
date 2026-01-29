"""py2app setup script for HeyClaude."""

from setuptools import setup

APP = ["src/heyclaude/app.py"]

DATA_FILES = [
    ("resources", ["resources/icon.png"]),
]

OPTIONS = {
    "argv_emulation": False,
    "iconfile": "resources/icon.icns",
    "plist": {
        "CFBundleName": "HeyClaude",
        "CFBundleDisplayName": "HeyClaude",
        "CFBundleIdentifier": "com.heyclaude.app",
        "CFBundleVersion": "0.1.0",
        "CFBundleShortVersionString": "0.1.0",
        "LSUIElement": True,  # Hide from Dock
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "12.0",
    },
    "packages": [
        "rumps",
        "flask",
        "yaml",
        "telegram",
        "objc",
        "AppKit",
        "Foundation",
    ],
    "includes": [
        "heyclaude",
        "heyclaude.app",
        "heyclaude.server",
        "heyclaude.config",
        "heyclaude.notifier",
        "heyclaude.telegram_bot",
        "heyclaude.transcript",
        "heyclaude.terminal",
        "heyclaude.hooks",
        "heyclaude.ui",
        "heyclaude.ui.preferences",
    ],
    "resources": ["resources"],
}

setup(
    name="HeyClaude",
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
)
