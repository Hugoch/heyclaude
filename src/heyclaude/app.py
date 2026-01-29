"""Main HeyClaude menubar application."""

import logging
import sys
from pathlib import Path

import rumps

from .config import get_config, get_log_path
from .hooks import install_hook, is_hook_installed
from .notifier import check_terminal_notifier_installed, send_notification
from .server import NotificationServer
from .telegram_bot import TelegramNotifier
from .terminal import activate_terminal, get_system_idle_time
from .transcript import get_project_name, parse_transcript

logger = logging.getLogger(__name__)


class HeyClaude(rumps.App):
    """HeyClaude menubar application."""

    def __init__(self):
        super().__init__("HeyClaude", icon=self._get_icon_path(), quit_button=None, template=True)

        self.config = get_config()
        self._setup_logging()

        self.server = NotificationServer(
            host=self.config.server_host,
            port=self.config.server_port,
        )
        self.server.set_notification_handler(self._handle_notification)
        self.server.set_permission_handler(self._handle_permission_request)

        self._telegram: TelegramNotifier | None = None

        self._build_menu()

    def _get_icon_path(self) -> str | None:
        """Get the menubar icon path."""
        if getattr(sys, "frozen", False):
            resources = Path(sys._MEIPASS) / "resources"
        else:
            resources = Path(__file__).parent.parent.parent / "resources"

        icon = resources / "icon.png"
        if icon.exists():
            return str(icon)
        return None

    def _setup_logging(self):
        """Set up logging configuration."""
        log_path = get_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)

        level = logging.DEBUG if self.config.debug else logging.INFO

        logging.basicConfig(
            level=level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(log_path),
                logging.StreamHandler(),
            ],
        )

    def _build_menu(self):
        """Build the menubar menu."""
        self.menu = [
            rumps.MenuItem("Status: Running", callback=None),
            None,
            rumps.MenuItem("Preferences...", callback=self._show_preferences),
            None,
            rumps.MenuItem("Install Hook", callback=self._install_hook),
            rumps.MenuItem("Test Notification", callback=self._test_notification),
            None,
            rumps.MenuItem("Quit", callback=self._quit),
        ]

        self._update_status()

    def _update_status(self):
        """Update the status menu item."""
        if self.server.is_running:
            status = f"Status: Running on port {self.config.server_port}"
        else:
            status = "Status: Stopped"

        self.menu["Status: Running"].title = status

    def _handle_notification(self, data: dict):
        """Handle incoming notification from Claude Code."""
        notification_type = data.get("notification_type", "")

        # Check if we should process this notification based on type
        if notification_type == "idle_prompt" and not self.config.idle_notifications:
            logger.debug("Ignoring idle_prompt notification (disabled in settings)")
            return
        if notification_type == "permission_prompt" and not self.config.permission_notifications:
            logger.debug("Ignoring permission_prompt notification (disabled in settings)")
            return

        logger.info(f"Processing notification: {notification_type}")

        cwd = data.get("cwd", "")
        transcript_path = data.get("transcript_path", "")
        message = data.get("message", "Claude needs your input")

        project = get_project_name(cwd) if cwd else "Claude Code"

        context = None
        if transcript_path:
            context = parse_transcript(
                transcript_path, max_lines=self.config.telegram_context_lines
            )

        # Always send macOS notification
        if self.config.macos_enabled:
            self._send_macos_notification(project, message, cwd, context)

        # Only send Telegram notification if idle time requirement is met
        if self.config.telegram_enabled:
            idle_required = self.config.telegram_idle_time_required
            if idle_required > 0:
                system_idle = get_system_idle_time()
                if system_idle < idle_required:
                    logger.debug(f"Skipping Telegram: system idle {system_idle:.0f}s < required {idle_required}s")
                else:
                    logger.info(f"System idle {system_idle:.0f}s >= {idle_required}s, sending Telegram")
                    self._send_telegram_notification(
                        project, cwd, message, context, notification_type
                    )
            else:
                self._send_telegram_notification(
                    project, cwd, message, context, notification_type
                )

    def _send_macos_notification(self, project: str, message: str, cwd: str, context: str | None = None):
        """Send a macOS notification."""
        if not check_terminal_notifier_installed():
            logger.warning("terminal-notifier not installed")
            return

        title = f"Claude Code - {project}"

        # Build notification body with context
        if context:
            # Truncate context for notification (max ~200 chars)
            truncated_context = context[:200] + "..." if len(context) > 200 else context
            body = truncated_context
        elif message:
            body = message
        else:
            body = "Claude needs your input"

        send_notification(
            title=title,
            message=body,
            subtitle=None,
            sound=self.config.macos_sound,
            sound_enabled=self.config.macos_sound_enabled,
            terminal_app=self.config.terminal_app,
        )

    def _send_telegram_notification(
        self,
        project: str,
        cwd: str,
        message: str,
        context: str | None,
        notification_type: str = "",
    ):
        """Send a Telegram notification."""
        if not self.config.telegram_bot_token or not self.config.telegram_chat_id:
            logger.warning("Telegram not configured")
            return

        if self._telegram is None:
            server_url = f"http://{self.config.server_host}:{self.config.server_port}"
            self._telegram = TelegramNotifier(
                bot_token=self.config.telegram_bot_token,
                chat_id=self.config.telegram_chat_id,
                on_open_terminal=lambda: activate_terminal(self.config.terminal_app),
                server_url=server_url,
            )
            # Start polling for button callbacks
            self._telegram.start_polling()

        self._telegram.send_notification_sync(
            project=project,
            cwd=cwd,
            message=message,
            context=context,
            include_context=self.config.telegram_include_context,
            notification_type=notification_type,
        )

    def _handle_permission_request(self, data: dict, request_id: str):
        """Handle incoming permission request from Claude Code (blocking endpoint)."""
        logger.info(f"Processing permission request: {request_id}")

        cwd = data.get("cwd", "")
        tool_name = data.get("tool_name", "")
        tool_input = data.get("tool_input", {})

        project = get_project_name(cwd) if cwd else "Claude Code"

        # Format message and context based on tool type
        if tool_name == "Bash":
            # Special formatting for Bash commands
            message = ""
            command = tool_input.get("command", "")
            description = tool_input.get("description", "")
            if description:
                context = f"# {description}\n$ {command}"
            else:
                context = f"$ {command}"
        else:
            message = data.get("message", f"Claude wants to use: {tool_name}")
            # Format context from tool input
            context = None
            if tool_input:
                context_parts = []
                for key, value in tool_input.items():
                    if isinstance(value, str) and len(value) > 200:
                        value = value[:200] + "..."
                    context_parts.append(f"{key}: {value}")
                context = "\n".join(context_parts)

        if self.config.macos_enabled:
            self._send_macos_notification(project, message, cwd, context)

        # Only send Telegram notification if idle time requirement is met
        if self.config.telegram_enabled:
            idle_required = self.config.telegram_idle_time_required
            if idle_required > 0:
                system_idle = get_system_idle_time()
                if system_idle < idle_required:
                    logger.debug(f"Skipping Telegram permission: system idle {system_idle:.0f}s < required {idle_required}s")
                else:
                    logger.info(f"System idle {system_idle:.0f}s >= {idle_required}s, sending Telegram permission")
                    self._send_telegram_permission(project, cwd, message, context, request_id)
            else:
                self._send_telegram_permission(project, cwd, message, context, request_id)

    def _send_telegram_permission(
        self,
        project: str,
        cwd: str,
        message: str,
        context: str | None,
        request_id: str,
    ):
        """Send a Telegram notification for permission request with action buttons."""
        if not self.config.telegram_bot_token or not self.config.telegram_chat_id:
            logger.warning("Telegram not configured")
            return

        if self._telegram is None:
            server_url = f"http://{self.config.server_host}:{self.config.server_port}"
            self._telegram = TelegramNotifier(
                bot_token=self.config.telegram_bot_token,
                chat_id=self.config.telegram_chat_id,
                on_open_terminal=lambda: activate_terminal(self.config.terminal_app),
                server_url=server_url,
            )
            self._telegram.start_polling()

        self._telegram.send_notification_sync(
            project=project,
            cwd=cwd,
            message=message,
            context=context,
            include_context=self.config.telegram_include_context,
            notification_type="permission_prompt",
            request_id=request_id,
        )

    @rumps.clicked("Preferences...")
    def _show_preferences(self, sender):
        """Show the preferences window."""
        from .ui.preferences import show_preferences

        def on_changed():
            self.config.load()
            self._update_status()

        show_preferences(self.config, on_changed=on_changed)

    @rumps.clicked("Install Hook")
    def _install_hook(self, sender):
        """Install the Claude Code hook."""
        # Install hooks based on notification settings
        install_permission = self.config.permission_notifications
        install_idle = self.config.idle_notifications
        success, message = install_hook(
            idle_notifications=install_idle,
            permission_notifications=install_permission,
        )

        if success:
            rumps.alert("Hook Installed", message)
        else:
            rumps.alert("Installation Failed", message)

    @rumps.clicked("Test Notification")
    def _test_notification(self, sender):
        """Send a test notification."""
        test_data = {
            "notification_type": "idle_prompt",
            "cwd": "/Users/test/project",
            "message": "This is a test notification from HeyClaude",
            "session_id": "test",
            "transcript_path": "",
        }
        self._handle_notification(test_data)

    @rumps.clicked("Quit")
    def _quit(self, sender):
        """Quit the application."""
        self.server.stop()
        rumps.quit_application()

    def run(self):
        """Start the application."""
        self.server.start()
        logger.info("HeyClaude started")
        super().run()


def main():
    """Entry point for the application."""
    # Hide from Dock, show only in menubar
    from AppKit import NSApp, NSApplication, NSApplicationActivationPolicyAccessory
    NSApplication.sharedApplication()
    NSApp.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

    app = HeyClaude()
    app.run()


if __name__ == "__main__":
    main()
