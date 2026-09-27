"""Download Discord participant avatars into the public event repository."""

from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path

from .event_service import EventService, EventServiceError


class AvatarServiceError(RuntimeError):
    pass


class AvatarService:
    def __init__(self, events: EventService, *, size: int = 128) -> None:
        self.events = events
        self.size = size

    @staticmethod
    def _write_bytes(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with temporary.open("wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()

    async def sync_participant(self, user_id: str, asset) -> str:
        """Fetch an Asset and return its event-relative public path."""
        event = await self.events.load_active()
        participant = next(
            (item for item in event.private.participants if item.discord_user_id == str(user_id)),
            None,
        )
        if participant is None:
            raise EventServiceError("找不到這位活動參賽者。")
        if participant.withdrawn:
            raise EventServiceError("取消報名者無法同步公開頭像。")
        uid = participant.registration_number
        try:
            avatar = asset.with_format("png").with_size(self.size)
            content = await avatar.read()
        except Exception as exc:
            raise AvatarServiceError("無法從 Discord 取得參賽者頭像。") from exc
        if not content:
            raise AvatarServiceError("Discord 回傳了空白頭像。")

        relative_path = f"images/players/{uid}.png"
        target = self.events.repository.public_dir(event.public.event_key) / relative_path
        try:
            await asyncio.to_thread(self._write_bytes, target, content)
            await self.events.set_participant_avatar(str(user_id), relative_path)
        except (OSError, ValueError, EventServiceError) as exc:
            raise AvatarServiceError("無法保存參賽者頭像。") from exc
        return relative_path
