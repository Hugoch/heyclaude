"""macOS native notifications via UserNotifications framework."""

import logging
import threading

logger = logging.getLogger(__name__)

# Global notification delegate
_delegate = None
_center = None
_terminal_app = "iTerm"


def _get_notification_center():
    """Get the shared UNUserNotificationCenter."""
    global _center, _delegate

    if _center is not None:
        return _center

    try:
        import objc
        from Foundation import NSObject
        import UserNotifications

        # Create delegate to handle notification actions
        class NotificationDelegate(NSObject):
            def userNotificationCenter_didReceiveNotificationResponse_withCompletionHandler_(
                self, center, response, handler
            ):
                # User clicked the notification - activate terminal
                from .terminal import activate_terminal
                activate_terminal(_terminal_app)
                handler()

            def userNotificationCenter_willPresentNotification_withCompletionHandler_(
                self, center, notification, handler
            ):
                # Show notification even if app is in foreground
                UNNotificationPresentationOptionSound = 1 << 1
                UNNotificationPresentationOptionBanner = 1 << 4
                handler(UNNotificationPresentationOptionSound | UNNotificationPresentationOptionBanner)

        _center = UserNotifications.UNUserNotificationCenter.currentNotificationCenter()
        _delegate = NotificationDelegate.alloc().init()
        _center.setDelegate_(_delegate)

        # Request authorization
        def auth_handler(granted, error):
            if granted:
                logger.info("Notification permission granted")
            else:
                logger.warning(f"Notification permission denied: {error}")

        _center.requestAuthorizationWithOptions_completionHandler_(
            UserNotifications.UNAuthorizationOptionAlert
            | UserNotifications.UNAuthorizationOptionSound
            | UserNotifications.UNAuthorizationOptionBadge,
            auth_handler,
        )

        return _center

    except Exception as e:
        logger.error(f"Failed to initialize notification center: {e}")
        return None


def send_notification(
    title: str,
    message: str,
    subtitle: str | None = None,
    sound: str = "Ping",
    terminal_app: str = "iTerm",
    group: str = "heyclaude",
) -> bool:
    """
    Send a native macOS notification.

    Args:
        title: Notification title
        message: Notification message body
        subtitle: Optional subtitle
        sound: Sound name (default system sound used)
        terminal_app: Terminal app to activate on click
        group: Notification identifier (for replacing notifications)

    Returns:
        True if notification was sent successfully
    """
    global _terminal_app
    _terminal_app = terminal_app

    logger.info(f"Sending notification: {title}")

    try:
        import UserNotifications

        center = _get_notification_center()
        if center is None:
            logger.error("Notification center not available")
            return False

        # Create notification content
        content = UserNotifications.UNMutableNotificationContent.alloc().init()
        content.setTitle_(title)
        content.setBody_(message)
        if subtitle:
            content.setSubtitle_(subtitle)
        content.setSound_(UserNotifications.UNNotificationSound.defaultSound())

        # Create request with identifier (allows replacing)
        request = UserNotifications.UNNotificationRequest.requestWithIdentifier_content_trigger_(
            group, content, None  # None trigger = deliver immediately
        )

        # Track completion
        result = {"success": False, "error": None}
        done_event = threading.Event()

        def completion_handler(error):
            if error:
                result["error"] = str(error)
                logger.error(f"Notification failed: {error}")
            else:
                result["success"] = True
                logger.info(f"Notification sent: {title}")
            done_event.set()

        center.addNotificationRequest_withCompletionHandler_(request, completion_handler)

        # Wait for completion (with timeout)
        done_event.wait(timeout=5.0)
        return result["success"]

    except ImportError:
        logger.error("UserNotifications framework not available")
        return _send_via_osascript(title, message, subtitle, sound)
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
        return _send_via_osascript(title, message, subtitle, sound)


def _send_via_osascript(
    title: str,
    message: str,
    subtitle: str | None,
    sound: str,
) -> bool:
    """Fallback: Send notification via osascript."""
    import subprocess

    full_message = message
    if subtitle:
        full_message = f"{subtitle}\n{message}"

    title = title.replace('"', '\\"')
    full_message = full_message.replace('"', '\\"')

    script = f'display notification "{full_message}" with title "{title}" sound name "{sound}"'

    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            timeout=5,
            text=True,
        )
        if result.returncode == 0:
            logger.info(f"Notification sent via osascript: {title}")
            return True
        logger.error(f"osascript failed: {result.stderr}")
        return False
    except Exception as e:
        logger.error(f"osascript error: {e}")
        return False


def check_terminal_notifier_installed() -> bool:
    """Check if native notifications are available."""
    try:
        import UserNotifications
        return True
    except ImportError:
        return False
