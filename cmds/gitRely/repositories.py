"""Persistence boundaries for public event data and private event state."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, TypeVar

from .models import EventPrivate, EventPublic


T = TypeVar("T")


def atomic_write_json(path: Path, data: Any) -> None:
    """Write JSON without exposing a partially written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


class EventRepository:
    """Store private state outside the public repository.

    ``public_root`` is the directory containing event repositories (usually
    the bot workspace), while ``data_root`` contains private JSON only.
    """

    _locks: dict[str, threading.RLock] = {}
    _locks_guard = threading.Lock()

    def __init__(self, data_root: str | Path = "data", public_root: str | Path = ".") -> None:
        self.data_root = Path(data_root)
        self.public_root = Path(public_root)
        self.events_root = self.data_root / "events"
        self.active_path = self.data_root / "active-event.json"

    @classmethod
    def _lock_for(cls, event_key: str) -> threading.RLock:
        with cls._locks_guard:
            return cls._locks.setdefault(event_key, threading.RLock())

    @staticmethod
    def _validate_event_key(event_key: str) -> str:
        if not isinstance(event_key, str) or not event_key.strip():
            raise ValueError("event key must be a non-empty string")
        if Path(event_key).name != event_key or event_key in {".", ".."}:
            raise ValueError("event key must be a single path component")
        return event_key

    def private_dir(self, event_key: str) -> Path:
        return self.events_root / self._validate_event_key(event_key)

    def private_path(self, event_key: str) -> Path:
        return self.private_dir(event_key) / "event-private.json"

    def public_dir(self, event_key: str) -> Path:
        return self.public_root / self._validate_event_key(event_key)

    def public_path(self, event_key: str) -> Path:
        return self.public_dir(event_key) / "event-public.json"

    def auxiliary_path(self, event_key: str, name: str) -> Path:
        if Path(name).name != name or not name.endswith(".json"):
            raise ValueError("auxiliary data name must be a JSON file name")
        return self.private_dir(event_key) / name

    def load_public(self, event_key: str) -> EventPublic:
        path = self.public_path(event_key)
        if not path.exists():
            raise FileNotFoundError(f"public event configuration not found: {path}")
        try:
            return EventPublic.from_dict(read_json(path))
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid public event configuration: {path}") from exc

    def save_public(self, public: EventPublic) -> None:
        public.validate()
        with self._lock_for(public.event_key):
            atomic_write_json(self.public_path(public.event_key), public.to_dict())

    def load_private(self, event_key: str) -> EventPrivate:
        path = self.private_path(event_key)
        if not path.exists():
            raise FileNotFoundError(f"private event state not found: {path}")
        try:
            private = EventPrivate.from_dict(read_json(path))
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid private event state: {path}") from exc
        if private.event_key != event_key:
            raise ValueError("private event key does not match its path")
        return private

    def save_private(self, private: EventPrivate, public: EventPublic | None = None) -> None:
        private.validate(public)
        with self._lock_for(private.event_key):
            atomic_write_json(self.private_path(private.event_key), private.to_dict())

    def load_event(self, event_key: str) -> tuple[EventPublic, EventPrivate]:
        public = self.load_public(event_key)
        private = self.load_private(event_key)
        private.validate(public)
        return public, private

    def activate_event(self, event_key: str) -> tuple[EventPublic, EventPrivate]:
        """Validate a complete event before changing the active-event pointer."""
        public, private = self.load_event(event_key)
        with self._lock_for("__active__"):
            atomic_write_json(self.active_path, {"event_key": event_key})
        return public, private

    def active_event_key(self) -> str:
        if not self.active_path.exists():
            raise FileNotFoundError("no active event configured")
        try:
            data = read_json(self.active_path)
            event_key = data["event_key"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ValueError("invalid active-event.json") from exc
        if not isinstance(event_key, str) or not event_key.strip():
            raise ValueError("active event_key must be a non-empty string")
        return event_key

    def load_active_event(self) -> tuple[EventPublic, EventPrivate]:
        return self.load_event(self.active_event_key())

    def load_auxiliary(self, event_key: str, name: str, default: Any) -> Any:
        path = self.auxiliary_path(event_key, name)
        if not path.exists():
            return default
        try:
            return read_json(path)
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            raise ValueError(f"invalid private data: {path}") from exc

    def save_auxiliary(self, event_key: str, name: str, data: Any) -> None:
        with self._lock_for(event_key):
            atomic_write_json(self.auxiliary_path(event_key, name), data)
