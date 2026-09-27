"""Submission upload, overwrite and clear workflows."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .event_service import EventService
from .models import EventStatus, event_status
from .publisher import GitPublishError, GitPublisher
from .public_index import PublicEventIndex, PublicIndexSnapshot
from .storage import SubmissionStorage, safe_component


class SubmissionServiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class SubmissionResult:
    event_key: str
    participant_key: str
    topic_key: str
    preview_url: str


class SubmissionService:
    _locks: dict[str, asyncio.Lock] = {}

    def __init__(
        self,
        events: EventService,
        storage: SubmissionStorage | None = None,
        publisher: GitPublisher | None = None,
        pages_host: str = "https://aafanclubdc.github.io",
        public_index: PublicEventIndex | None = None,
    ) -> None:
        self.events = events
        self.storage = storage or SubmissionStorage()
        self.publisher = publisher or GitPublisher()
        self.pages_host = pages_host.rstrip("/")
        self.public_index = public_index or PublicEventIndex(events.repository)

    @classmethod
    def _lock_for(cls, event_key: str) -> asyncio.Lock:
        return cls._locks.setdefault(event_key, asyncio.Lock())

    async def upload_archive(
        self,
        user_id: str,
        archive_path: str | Path,
        *,
        topic: str | None = None,
        title: str,
        commit_message: str | None = None,
        now: datetime | None = None,
    ) -> SubmissionResult:
        event = await self.events.load_active()
        current = now or datetime.now(event.private.submission_starts_at.tzinfo)
        current_status = event_status(event.private, current)
        if current_status is not EventStatus.SUBMISSION_OPEN:
            raise SubmissionServiceError("目前不是投稿期間，無法上傳作品。")
        participant = next(
            (
                item for item in event.private.participants
                if item.discord_user_id == str(user_id) and not item.withdrawn
            ),
            None,
        )
        if participant is None:
            raise SubmissionServiceError("請先使用 `/event join` 報名，再上傳作品。")
        selected_topic = await self.events.resolve_topic(topic)
        safe_component(participant.participant_key, label="participant key")
        safe_component(selected_topic.key, label="topic key")
        if not title.strip():
            raise SubmissionServiceError("作品標題不可為空白。")
        source = Path(archive_path)
        if source.suffix.lower() not in (".zip", ".rar", ".7z"):
            raise SubmissionServiceError("不支援這種檔案格式，請使用 .zip、.rar 或 .7z。")

        event_key = event.public.event_key
        repo = self.events.repository.public_dir(event_key)
        target = repo / "pieces" / participant.participant_key / selected_topic.key
        async with self._lock_for(event_key):
            request_dir = await asyncio.to_thread(self.storage.create_request_directory)
            staged = request_dir / "submission"
            backup = None
            index_backup: PublicIndexSnapshot | None = None
            try:
                try:
                    await asyncio.to_thread(self.storage.extract_archive, source, staged)
                    gallery_path = await asyncio.to_thread(
                        self.storage.generate_gallery, staged, title
                    )
                    gallery_file = gallery_path.relative_to(staged).as_posix()
                except (OSError, ValueError, RuntimeError) as exc:
                    raise SubmissionServiceError(
                        "作品檔案無法處理，請確認壓縮檔格式、內容與檔案大小限制。"
                    ) from exc
                try:
                    backup = await asyncio.to_thread(self.storage.replace_directory, staged, target)
                except (OSError, ValueError) as exc:
                    raise SubmissionServiceError("無法替換作品目錄，作品尚未發布，請稍後再試。") from exc
                try:
                    index_backup = await asyncio.to_thread(
                        self.public_index.snapshot, event_key
                    )
                    await asyncio.to_thread(
                        self.public_index.upsert_work,
                        event,
                        participant,
                        selected_topic,
                        title,
                        gallery_file,
                    )
                    await self.publisher.publish(
                        repo,
                        commit_message or f"Upload {title} ({selected_topic.name})",
                    )
                except (GitPublishError, OSError, RuntimeError, ValueError) as exc:
                    if index_backup is not None:
                        await asyncio.to_thread(self.public_index.restore, index_backup)
                    await asyncio.to_thread(self.storage.rollback, target, backup)
                    raise SubmissionServiceError("作品發布失敗，已還原上一個版本，請稍後再試。") from exc
                await asyncio.to_thread(self.storage.discard_backup, backup)
                return SubmissionResult(
                    event_key=event_key,
                    participant_key=participant.participant_key,
                    topic_key=selected_topic.key,
                    preview_url=(
                        f"{self.pages_host}/{event_key}/"
                        f"{self.public_index.work_url(participant.participant_key, selected_topic.key, gallery_file)}"
                    ),
                )
            finally:
                if backup and Path(backup).exists():
                    await asyncio.to_thread(self.storage.discard_backup, backup)
                await asyncio.to_thread(self.storage.cleanup, request_dir)

    async def clear_submission(
        self,
        user_id: str,
        *,
        topic: str | None = None,
        commit_message: str | None = None,
        now: datetime | None = None,
    ) -> None:
        event = await self.events.load_active()
        current = now or datetime.now(event.private.submission_starts_at.tzinfo)
        if event_status(event.private, current) is not EventStatus.SUBMISSION_OPEN:
            raise SubmissionServiceError("目前不是投稿期間，無法清除作品。")
        selected_topic = await self.events.resolve_topic(topic)
        participant = next(
            (
                item for item in event.private.participants
                if item.discord_user_id == str(user_id) and not item.withdrawn
            ),
            None,
        )
        if participant is None:
            raise SubmissionServiceError("請先使用 `/event join` 報名，再清除作品。")
        safe_component(participant.participant_key, label="participant key")
        target = (
            self.events.repository.public_dir(event.public.event_key)
            / "pieces"
            / participant.participant_key
            / selected_topic.key
        )
        if not target.exists():
            raise SubmissionServiceError("找不到指定題目的作品。")
        async with self._lock_for(event.public.event_key):
            request_dir = await asyncio.to_thread(self.storage.create_request_directory)
            empty = request_dir / "empty"
            empty.mkdir()
            backup = None
            index_backup: PublicIndexSnapshot | None = None
            try:
                try:
                    backup = await asyncio.to_thread(self.storage.replace_directory, empty, target)
                except (OSError, ValueError) as exc:
                    raise SubmissionServiceError("無法清除作品目錄，作品尚未變更，請稍後再試。") from exc
                try:
                    index_backup = await asyncio.to_thread(
                        self.public_index.snapshot, event.public.event_key
                    )
                    await asyncio.to_thread(
                        self.public_index.remove_work,
                        event,
                        participant,
                        selected_topic,
                    )
                    await self.publisher.publish(
                        self.events.repository.public_dir(event.public.event_key),
                        commit_message or f"Clear submission ({selected_topic.name})",
                    )
                except (GitPublishError, OSError, RuntimeError, ValueError) as exc:
                    if index_backup is not None:
                        await asyncio.to_thread(self.public_index.restore, index_backup)
                    await asyncio.to_thread(self.storage.rollback, target, backup)
                    raise SubmissionServiceError("作品清除發布失敗，已還原原作品，請稍後再試。") from exc
                await asyncio.to_thread(self.storage.discard_backup, backup)
            finally:
                if backup and Path(backup).exists():
                    await asyncio.to_thread(self.storage.discard_backup, backup)
                await asyncio.to_thread(self.storage.cleanup, request_dir)
