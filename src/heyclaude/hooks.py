"""Hook installation utilities."""

import json
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

HOOK_SCRIPT = """#!/bin/bash
# HeyClaude hook for Claude Code
# Sends notifications to HeyClaude app

# Read JSON from stdin
INPUT=$(cat)

# POST to HeyClaude server (ignore errors if server is down)
curl -s -X POST "http://127.0.0.1:8765/notification" \\
    -H "Content-Type: application/json" \\
    -d "$INPUT" \\
    --connect-timeout 2 \\
    --max-time 5 \\
    >/dev/null 2>&1 || true

exit 0
"""

PERMISSION_HOOK_SCRIPT = """#!/bin/bash
# HeyClaude permission hook for Claude Code
# Sends permission requests to HeyClaude app and waits for response

# Read JSON from stdin
INPUT=$(cat)

# Generate a unique request ID
REQUEST_ID="perm_$(date +%s)_$$"

# Add request_id to the input JSON
INPUT_WITH_ID=$(echo "$INPUT" | jq --arg id "$REQUEST_ID" '. + {request_id: $id}')

# POST to HeyClaude server and wait for response (5 minute timeout)
RESPONSE=$(curl -s -X POST "http://127.0.0.1:8765/permission" \\
    -H "Content-Type: application/json" \\
    -d "$INPUT_WITH_ID" \\
    --connect-timeout 2 \\
    --max-time 300 \\
    2>/dev/null)

# Extract decision from response
DECISION=$(echo "$RESPONSE" | jq -r '.decision // empty')

if [ "$DECISION" = "allow" ]; then
    # Output JSON to approve the action
    echo '{"decision": "allow"}'
elif [ "$DECISION" = "deny" ]; then
    # Output JSON to deny the action
    echo '{"decision": "deny"}'
fi

# Exit with success regardless (Claude handles the decision)
exit 0
"""


def get_hook_path() -> Path:
    """Get the notification hook script path."""
    return Path.home() / ".claude" / "hooks" / "heyclaude-hook.sh"


def get_permission_hook_path() -> Path:
    """Get the permission hook script path."""
    return Path.home() / ".claude" / "hooks" / "heyclaude-permission-hook.sh"


def get_settings_path() -> Path:
    """Get the Claude Code settings path."""
    return Path.home() / ".claude" / "settings.json"


def install_hook(
    idle_notifications: bool = True,
    permission_notifications: bool = True,
) -> tuple[bool, str]:
    """
    Install the HeyClaude hooks for Claude Code.

    Args:
        idle_notifications: If True, receive idle_prompt notifications.
        permission_notifications: If True, receive permission_prompt notifications.

    Returns:
        Tuple of (success, message)
    """
    try:
        # Install notification hook
        hook_path = get_hook_path()
        hook_path.parent.mkdir(parents=True, exist_ok=True)

        with open(hook_path, "w") as f:
            f.write(HOOK_SCRIPT)
        hook_path.chmod(0o755)

        # Install permission hook
        perm_hook_path = get_permission_hook_path()
        with open(perm_hook_path, "w") as f:
            f.write(PERMISSION_HOOK_SCRIPT)
        perm_hook_path.chmod(0o755)

        settings_path = get_settings_path()
        settings = {}

        if settings_path.exists():
            with open(settings_path) as f:
                settings = json.load(f)

        if "hooks" not in settings:
            settings["hooks"] = {}

        # Build hook config for notifications
        hook_entry = {
            "type": "command",
            "command": str(hook_path),
        }

        # Build hook config for permission requests (uses different script)
        perm_hook_entry = {
            "type": "command",
            "command": str(perm_hook_path),
        }

        # Build notification hooks based on settings
        notification_hooks = []
        modes = []

        if idle_notifications:
            notification_hooks.append({
                "matcher": "idle_prompt",
                "hooks": [hook_entry]
            })
            modes.append("idle")

        if permission_notifications:
            # Only add PermissionRequest hook (not Notification hook for permission_prompt
            # to avoid duplicate notifications)
            modes.append("permission")
            settings["hooks"]["PermissionRequest"] = [
                {
                    "hooks": [perm_hook_entry]
                }
            ]
        else:
            # Remove PermissionRequest hook if exists
            settings["hooks"].pop("PermissionRequest", None)

        if notification_hooks:
            settings["hooks"]["Notification"] = notification_hooks
        else:
            settings["hooks"].pop("Notification", None)

        settings_path.parent.mkdir(parents=True, exist_ok=True)
        with open(settings_path, "w") as f:
            json.dump(settings, f, indent=2)

        mode = " + ".join(modes) if modes else "none"
        logger.info(f"Hook installed successfully ({mode})")
        return True, f"Hook installed ({mode})"

    except Exception as e:
        logger.error(f"Failed to install hook: {e}")
        return False, f"Failed to install hook: {e}"


def uninstall_hook() -> tuple[bool, str]:
    """
    Uninstall the HeyClaude hooks.

    Returns:
        Tuple of (success, message)
    """
    try:
        # Remove notification hook
        hook_path = get_hook_path()
        if hook_path.exists():
            hook_path.unlink()

        # Remove permission hook
        perm_hook_path = get_permission_hook_path()
        if perm_hook_path.exists():
            perm_hook_path.unlink()

        settings_path = get_settings_path()
        if settings_path.exists():
            with open(settings_path) as f:
                settings = json.load(f)

            if "hooks" in settings:
                # Remove Notification hooks
                if "Notification" in settings["hooks"]:
                    notifications = settings["hooks"]["Notification"]
                    settings["hooks"]["Notification"] = [
                        n for n in notifications
                        if not any(str(hook_path) in h.get("command", "") for h in n.get("hooks", []))
                    ]

                    if not settings["hooks"]["Notification"]:
                        del settings["hooks"]["Notification"]

                # Remove PermissionRequest hooks
                if "PermissionRequest" in settings["hooks"]:
                    perm_hooks = settings["hooks"]["PermissionRequest"]
                    settings["hooks"]["PermissionRequest"] = [
                        h for h in perm_hooks
                        if str(perm_hook_path) not in h.get("command", "")
                    ]

                    if not settings["hooks"]["PermissionRequest"]:
                        del settings["hooks"]["PermissionRequest"]

            with open(settings_path, "w") as f:
                json.dump(settings, f, indent=2)

        logger.info("Hooks uninstalled successfully")
        return True, "Hooks uninstalled"

    except Exception as e:
        logger.error(f"Failed to uninstall hooks: {e}")
        return False, f"Failed to uninstall hooks: {e}"


def is_hook_installed() -> bool:
    """Check if the HeyClaude hook is installed."""
    hook_path = get_hook_path()
    if not hook_path.exists():
        return False

    settings_path = get_settings_path()
    if not settings_path.exists():
        return False

    try:
        with open(settings_path) as f:
            settings = json.load(f)

        notifications = settings.get("hooks", {}).get("Notification", [])
        for notification in notifications:
            # Check for heyclaude hook (with or without matcher)
            for hook in notification.get("hooks", []):
                if str(hook_path) in hook.get("command", ""):
                    return True

    except Exception:
        pass

    return False
