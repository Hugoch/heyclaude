"""Terminal app detection and activation, and system utilities."""

import logging
import subprocess

import Quartz

logger = logging.getLogger(__name__)


def get_system_idle_time() -> float:
    """
    Get the system idle time in seconds.

    Uses macOS IOKit to get the HID idle time.

    Returns:
        Idle time in seconds, or 0 if detection fails.
    """
    try:
        result = subprocess.run(
            ["ioreg", "-c", "IOHIDSystem", "-d", "4"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        for line in result.stdout.split("\n"):
            if "HIDIdleTime" in line:
                # Extract the number from the line
                # Format: "HIDIdleTime" = 1234567890
                parts = line.split("=")
                if len(parts) >= 2:
                    idle_ns = int(parts[1].strip())
                    return idle_ns / 1_000_000_000  # Convert nanoseconds to seconds
    except Exception as e:
        logger.debug(f"Could not get system idle time: {e}")
    return 0


def is_screen_locked() -> bool:
    """
    Check if the macOS screen is locked.

    Uses Quartz CGSessionCopyCurrentDictionary to check the screen lock state.

    Returns:
        True if screen is locked, False otherwise.
    """
    try:
        session_dict = Quartz.CGSessionCopyCurrentDictionary()
        if session_dict:
            return session_dict.get("CGSSessionScreenIsLocked", False)
    except Exception as e:
        logger.debug(f"Could not check screen lock state: {e}")
    return False


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
