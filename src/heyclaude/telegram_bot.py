"""Telegram bot integration for Claude Code notifications."""

import asyncio
import logging
import threading
from typing import Callable

import requests

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Send notifications to Telegram with inline keyboards."""

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        on_open_terminal: Callable | None = None,
        server_url: str = "http://127.0.0.1:8765",
    ):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self._on_open_terminal = on_open_terminal
        self._server_url = server_url
        self._bot = None
        self._app = None
        self._polling_thread: threading.Thread | None = None
        self._polling = False

    async def _get_bot(self):
        """Get or create the bot instance."""
        # Always create a fresh bot to avoid event loop issues
        from telegram import Bot
        return Bot(token=self.bot_token)

    async def send_notification(
        self,
        project: str,
        cwd: str,
        message: str = "",
        context: str | None = None,
        include_context: bool = True,
        notification_type: str = "",
        request_id: str | None = None,
    ) -> bool:
        """
        Send a notification to Telegram.

        Args:
            project: Project name
            cwd: Current working directory
            message: The notification message/question from Claude
            context: Additional context (questions with options)
            include_context: Whether to include context in the message
            notification_type: Type of notification (idle_prompt, permission_prompt)
            request_id: For permission requests, the ID to respond with

        Returns:
            True if message was sent successfully
        """
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        try:
            bot = await self._get_bot()

            # Different formatting based on notification type
            if notification_type == "permission_prompt":
                title = f"\U0001F6A8 *Permission Required - {self._escape_markdown(project)}*"
            else:
                title = f"*Claude Code - {self._escape_markdown(project)}*"

            text_parts = [title]

            # Add the notification message (question)
            if message:
                text_parts.append(f"\n\U0001F4AC {self._escape_markdown(message)}")

            # Add context (questions with options)
            if include_context and context:
                truncated = context[:1000] + "..." if len(context) > 1000 else context
                truncated = self._escape_markdown(truncated)
                text_parts.append(f"\n```\n{truncated}\n```")

            text = "\n".join(text_parts)

            # Build keyboard based on notification type
            if notification_type == "permission_prompt" and request_id:
                keyboard = [
                    [
                        InlineKeyboardButton(
                            "\u2705 Allow",
                            callback_data=f"perm_allow:{request_id}",
                        ),
                        InlineKeyboardButton(
                            "\u274C Deny",
                            callback_data=f"perm_deny:{request_id}",
                        ),
                    ],
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
            else:
                reply_markup = None

            await bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode="Markdown",
                reply_markup=reply_markup,
            )

            logger.info(f"Telegram notification sent for project: {project} (type: {notification_type})")
            return True

        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            return False

    def _escape_markdown(self, text: str) -> str:
        """Escape special Markdown characters."""
        for char in ['*', '_', '`', '[']:
            text = text.replace(char, '\\' + char)
        return text

    def send_notification_sync(
        self,
        project: str,
        cwd: str,
        message: str = "",
        context: str | None = None,
        include_context: bool = True,
        notification_type: str = "",
        request_id: str | None = None,
    ) -> bool:
        """Synchronous wrapper for send_notification."""
        try:
            # Create a fresh event loop for each call to avoid closed loop issues
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(
                    self.send_notification(
                        project, cwd, message, context, include_context, notification_type, request_id
                    )
                )
            finally:
                # Clean up pending tasks before closing
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                loop.close()
        except Exception as e:
            logger.error(f"Error in sync notification: {e}")
            return False

    def start_polling(self):
        """Start polling for button callback updates in a background thread."""
        if self._polling:
            return

        self._polling = True
        self._polling_thread = threading.Thread(target=self._poll_updates, daemon=True)
        self._polling_thread.start()
        logger.info("Telegram polling started")

    def stop_polling(self):
        """Stop polling for updates."""
        self._polling = False
        if self._polling_thread:
            self._polling_thread.join(timeout=2)
        logger.info("Telegram polling stopped")

    def _poll_updates(self):
        """Poll for Telegram updates and handle button callbacks."""
        import time

        offset = 0
        while self._polling:
            try:
                url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
                params = {"offset": offset, "timeout": 30, "allowed_updates": ["callback_query"]}
                response = requests.get(url, params=params, timeout=35)
                data = response.json()

                if data.get("ok"):
                    for update in data.get("result", []):
                        offset = update["update_id"] + 1
                        callback = update.get("callback_query")
                        if callback:
                            self._handle_callback(callback)
            except requests.exceptions.Timeout:
                continue
            except Exception as e:
                logger.error(f"Error polling Telegram updates: {e}")
                time.sleep(5)

    def _handle_callback(self, callback: dict):
        """Handle a button callback from Telegram."""
        callback_id = callback.get("id")
        data = callback.get("data", "")
        message = callback.get("message", {})

        # Handle different callback types
        if data.startswith("perm_allow:"):
            request_id = data.split(":", 1)[1]
            self._respond_permission(request_id, "allow", message, callback_id)
        elif data.startswith("perm_deny:"):
            request_id = data.split(":", 1)[1]
            self._respond_permission(request_id, "deny", message, callback_id)
        else:
            # Answer unknown callbacks
            try:
                url = f"https://api.telegram.org/bot{self.bot_token}/answerCallbackQuery"
                requests.post(url, json={"callback_query_id": callback_id}, timeout=5)
            except Exception as e:
                logger.error(f"Error answering callback: {e}")

    def _respond_permission(self, request_id: str, decision: str, message: dict, callback_id: str):
        """Send permission response to HeyClaude server."""
        decision_text = "\u2705 Allowed" if decision == "allow" else "\u274C Denied"

        try:
            url = f"{self._server_url}/permission/respond"
            response = requests.post(
                url,
                json={"request_id": request_id, "decision": decision},
                timeout=5,
            )
            if response.ok:
                logger.info(f"Permission {request_id} responded: {decision}")
                # Answer the callback with the decision as a toast notification
                self._answer_callback(callback_id, decision_text)
                # Remove the buttons from the message
                self._remove_buttons(message)
            else:
                logger.error(f"Failed to respond to permission: {response.text}")
                self._answer_callback(callback_id, "Error: Request expired or not found")
        except Exception as e:
            logger.error(f"Error responding to permission: {e}")
            self._answer_callback(callback_id, f"Error: {e}")

    def _answer_callback(self, callback_id: str, text: str):
        """Answer a callback query with a toast notification."""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/answerCallbackQuery"
            requests.post(
                url,
                json={"callback_query_id": callback_id, "text": text, "show_alert": True},
                timeout=5,
            )
        except Exception as e:
            logger.error(f"Error answering callback: {e}")

    def _remove_buttons(self, message: dict):
        """Remove inline keyboard buttons from a message."""
        chat_id = message.get("chat", {}).get("id")
        message_id = message.get("message_id")

        if not chat_id or not message_id:
            return

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/editMessageReplyMarkup"
            requests.post(
                url,
                json={
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "reply_markup": {"inline_keyboard": []},
                },
                timeout=5,
            )
        except Exception as e:
            logger.error(f"Error removing buttons: {e}")


async def test_telegram_connection(bot_token: str, chat_id: str) -> tuple[bool, str]:
    """
    Test the Telegram bot connection.

    Returns:
        Tuple of (success, message)
    """
    try:
        from telegram import Bot

        bot = Bot(token=bot_token)
        me = await bot.get_me()

        await bot.send_message(
            chat_id=chat_id,
            text="\u2705 *HeyClaude Connected*\nTelegram notifications are working!",
            parse_mode="Markdown",
        )

        return True, f"Connected as @{me.username}"
    except Exception as e:
        return False, str(e)


def test_telegram_connection_sync(bot_token: str, chat_id: str) -> tuple[bool, str]:
    """Synchronous wrapper for test_telegram_connection."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(test_telegram_connection(bot_token, chat_id))
    except Exception as e:
        return False, str(e)
    finally:
        loop.close()
