"""Startup validation for the active event configuration."""

from __future__ import annotations

from .repositories import EventRepository


class EventStartupError(RuntimeError):
    """Raised when the bot must not start with an invalid active event."""


def validate_active_event_configuration(repository: EventRepository | None = None):
    """Validate the active event before the bot connects to Discord."""
    repository = repository or EventRepository()
    try:
        public, private = repository.load_active_event()
    except FileNotFoundError:
        print("[event] startup check: no active event configured; continuing.")
        return None
    except (OSError, ValueError) as exc:
        raise EventStartupError(f"活動設定檢查失敗，停止啟動：{exc}") from exc

    print(f"[event] startup check passed: {public.event_key}")
    return public, private
