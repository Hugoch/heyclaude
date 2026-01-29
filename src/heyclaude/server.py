"""HTTP server for receiving Claude Code notifications."""

import logging
import threading
import time
from typing import Callable

from flask import Flask, jsonify, request

logger = logging.getLogger(__name__)


class NotificationServer:
    """HTTP server that receives notifications from Claude Code hooks."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host = host
        self.port = port
        self.app = Flask(__name__)
        self._thread: threading.Thread | None = None
        self._running = False
        self._notification_handler: Callable | None = None
        self._permission_handler: Callable | None = None
        # Pending permission requests: request_id -> {"event": Event, "decision": None}
        self._pending_permissions: dict = {}
        self._permissions_lock = threading.Lock()

        self._setup_routes()

    def _setup_routes(self):
        """Set up Flask routes."""

        @self.app.route("/notification", methods=["POST"])
        def notification():
            try:
                data = request.get_json(force=True, silent=True) or {}
                logger.info(f"Received notification: {data}")

                if self._notification_handler:
                    self._notification_handler(data)

                return jsonify({"status": "ok"})
            except Exception as e:
                logger.error(f"Error handling notification: {e}")
                return jsonify({"status": "error", "message": str(e)}), 500

        @self.app.route("/health", methods=["GET"])
        def health():
            return jsonify({"status": "healthy"})

        @self.app.route("/permission", methods=["POST"])
        def permission():
            """Handle permission request from Claude Code hook.

            This endpoint blocks until a decision is made via /permission/respond
            or timeout occurs.
            """
            try:
                data = request.get_json(force=True, silent=True) or {}
                request_id = data.get("request_id", str(time.time()))
                timeout = data.get("timeout", 300)  # 5 minute default timeout

                logger.info(f"Received permission request: {request_id}")

                # Create event for waiting
                event = threading.Event()
                with self._permissions_lock:
                    self._pending_permissions[request_id] = {
                        "event": event,
                        "decision": None,
                        "data": data,
                    }

                # Notify handler (sends to Telegram)
                if self._permission_handler:
                    self._permission_handler(data, request_id)

                # Wait for response or timeout
                event.wait(timeout=timeout)

                with self._permissions_lock:
                    pending = self._pending_permissions.pop(request_id, None)

                if pending and pending.get("decision"):
                    decision = pending["decision"]
                    logger.info(f"Permission {request_id} decided: {decision}")
                    return jsonify({"decision": decision})
                else:
                    logger.info(f"Permission {request_id} timed out")
                    return jsonify({"decision": None, "timeout": True})

            except Exception as e:
                logger.error(f"Error handling permission: {e}")
                return jsonify({"status": "error", "message": str(e)}), 500

        @self.app.route("/permission/respond", methods=["POST"])
        def permission_respond():
            """Handle response to a pending permission request."""
            try:
                data = request.get_json(force=True, silent=True) or {}
                request_id = data.get("request_id")
                decision = data.get("decision")  # "allow", "deny", or specific option

                if not request_id:
                    return jsonify({"status": "error", "message": "request_id required"}), 400

                with self._permissions_lock:
                    pending = self._pending_permissions.get(request_id)
                    if pending:
                        pending["decision"] = decision
                        pending["event"].set()
                        logger.info(f"Permission {request_id} responded: {decision}")
                        return jsonify({"status": "ok"})
                    else:
                        return jsonify({"status": "error", "message": "Request not found or expired"}), 404

            except Exception as e:
                logger.error(f"Error responding to permission: {e}")
                return jsonify({"status": "error", "message": str(e)}), 500

    def set_notification_handler(self, handler: Callable):
        """Set the handler function for incoming notifications."""
        self._notification_handler = handler

    def set_permission_handler(self, handler: Callable):
        """Set the handler function for incoming permission requests."""
        self._permission_handler = handler

    def start(self):
        """Start the server in a background thread."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info(f"Server started on {self.host}:{self.port}")

    def _run(self):
        """Run the Flask server."""
        import warnings

        warnings.filterwarnings("ignore", message=".*development server.*")

        from werkzeug.serving import make_server

        self._server = make_server(self.host, self.port, self.app, threaded=True)
        self._server.serve_forever()

    def stop(self):
        """Stop the server."""
        if not self._running:
            return

        self._running = False
        if hasattr(self, "_server"):
            self._server.shutdown()
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("Server stopped")

    @property
    def is_running(self) -> bool:
        return self._running
