"""Configuration management for HeyClaude."""

import os
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG = {
    "server": {
        "host": "127.0.0.1",
        "port": 8765,
    },
    "notifications": {
        "macos": {
            "enabled": True,
            "sound": "Ping",
            "terminal_app": "iTerm",
        },
        "telegram": {
            "enabled": False,
            "bot_token": "",
            "chat_id": "",
            "include_context": True,
            "context_lines": 20,
        },
    },
    "filters": {
        "notification_types": ["idle_prompt"],
        "all_notifications": False,  # If True, receive all Claude notifications (not just idle)
    },
    "debug": False,
    "launch_at_login": False,
}


def get_config_dir() -> Path:
    """Get the configuration directory path."""
    return Path.home() / ".heyclaude"


def get_config_path() -> Path:
    """Get the configuration file path."""
    return get_config_dir() / "config.yaml"


def get_log_path() -> Path:
    """Get the log file path."""
    return get_config_dir() / "heyclaude.log"


def deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override into base dict."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class Config:
    """Configuration manager for HeyClaude."""

    def __init__(self):
        self._config = DEFAULT_CONFIG.copy()
        self._config_path = get_config_path()
        self._ensure_config_dir()
        self.load()

    def _ensure_config_dir(self):
        """Ensure the config directory exists."""
        self._config_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self):
        """Load configuration from file."""
        if self._config_path.exists():
            with open(self._config_path) as f:
                user_config = yaml.safe_load(f) or {}
                self._config = deep_merge(DEFAULT_CONFIG, user_config)
        else:
            self._config = DEFAULT_CONFIG.copy()
            self.save()

    def save(self):
        """Save configuration to file."""
        # Convert any PyObjC strings to regular Python strings
        clean_config = self._convert_to_python_types(self._config)
        with open(self._config_path, "w") as f:
            yaml.dump(clean_config, f, default_flow_style=False)

    def _convert_to_python_types(self, obj):
        """Convert PyObjC types to Python native types for YAML serialization."""
        if isinstance(obj, dict):
            return {k: self._convert_to_python_types(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_to_python_types(v) for v in obj]
        elif hasattr(obj, '__class__') and 'NSString' in obj.__class__.__name__:
            return str(obj)
        elif hasattr(obj, '__class__') and 'NSNumber' in obj.__class__.__name__:
            return int(obj) if float(obj) == int(obj) else float(obj)
        elif not isinstance(obj, (str, int, float, bool, type(None))):
            return str(obj)
        return obj

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value by dot-separated key."""
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def set(self, key: str, value: Any):
        """Set a config value by dot-separated key."""
        keys = key.split(".")
        config = self._config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        self.save()

    @property
    def server_host(self) -> str:
        return self.get("server.host", "127.0.0.1")

    @property
    def server_port(self) -> int:
        return self.get("server.port", 8765)

    @property
    def macos_enabled(self) -> bool:
        return self.get("notifications.macos.enabled", True)

    @property
    def macos_sound(self) -> str:
        return self.get("notifications.macos.sound", "Ping")

    @property
    def terminal_app(self) -> str:
        return self.get("notifications.macos.terminal_app", "iTerm")

    @property
    def telegram_enabled(self) -> bool:
        return self.get("notifications.telegram.enabled", False)

    @property
    def telegram_bot_token(self) -> str:
        return self.get("notifications.telegram.bot_token", "")

    @property
    def telegram_chat_id(self) -> str:
        return self.get("notifications.telegram.chat_id", "")

    @property
    def telegram_include_context(self) -> bool:
        return self.get("notifications.telegram.include_context", True)

    @property
    def telegram_context_lines(self) -> int:
        return self.get("notifications.telegram.context_lines", 20)

    @property
    def notification_types(self) -> list:
        return self.get("filters.notification_types", ["idle_prompt"])

    @property
    def all_notifications(self) -> bool:
        return self.get("filters.all_notifications", False)

    @property
    def debug(self) -> bool:
        return self.get("debug", False)

    @property
    def launch_at_login(self) -> bool:
        return self.get("launch_at_login", False)


# Global config instance
_config: Config | None = None


def get_config() -> Config:
    """Get the global config instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config
