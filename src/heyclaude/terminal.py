"""Terminal app detection and activation."""

import logging
import subprocess

logger = logging.getLogger(__name__)

TERMINAL_APPS = {
    "iTerm": "com.googlecode.iterm2",
    "Terminal": "com.apple.Terminal",
    "Warp": "dev.warp.Warp-Stable",
    "Alacritty": "org.alacritty",
    "Kitty": "net.kovidgoyal.kitty",
}


def detect_terminal() -> str:
    """
    Detect the currently running terminal application.

    Returns:
        Terminal app name (iTerm, Terminal, Warp, etc.) or "iTerm" as default
    """
    script = """
    tell application "System Events"
        set frontApp to name of first application process whose frontmost is true
        return frontApp
    end tell
    """

    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=5,
        )
        front_app = result.stdout.strip()

        if "iTerm" in front_app:
            return "iTerm"
        elif "Terminal" in front_app:
            return "Terminal"
        elif "Warp" in front_app:
            return "Warp"
        elif "Alacritty" in front_app:
            return "Alacritty"
        elif "kitty" in front_app.lower():
            return "Kitty"
    except Exception as e:
        logger.debug(f"Could not detect terminal: {e}")

    return "iTerm"


def get_bundle_id(terminal_app: str) -> str:
    """Get the bundle ID for a terminal application."""
    if terminal_app == "auto":
        terminal_app = detect_terminal()
    return TERMINAL_APPS.get(terminal_app, TERMINAL_APPS["iTerm"])


def activate_terminal(terminal_app: str = "iTerm"):
    """
    Bring the specified terminal application to the foreground.

    Args:
        terminal_app: Terminal app name (iTerm, Terminal, Warp, auto)
    """
    if terminal_app == "auto":
        terminal_app = detect_terminal()

    bundle_id = TERMINAL_APPS.get(terminal_app, TERMINAL_APPS["iTerm"])

    script = f"""
    tell application id "{bundle_id}"
        activate
    end tell
    """

    try:
        subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            timeout=5,
        )
        logger.debug(f"Activated terminal: {terminal_app}")
    except Exception as e:
        logger.error(f"Failed to activate terminal: {e}")
