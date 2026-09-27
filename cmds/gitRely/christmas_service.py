"""Private anonymous-message, blacklist and gift-matching coordination."""

from __future__ import annotations

import asyncio
import secrets
from datetime import datetime
from typing import Any, Callable

from .event_service import EventService
from .models import EventType, GiftAssignment
from .matching.protocol import GiftMatchingPolicy


class ChristmasServiceError(RuntimeError):
    pass


class ChristmasService:
    def __init__(self, events: EventService, policy_resolver: Callable[[str], GiftMatchingPolicy] | None = None) -> None:
        self.events = events
        self.repository = events.repository
        self.policy_resolver = policy_resolver
        self._lock = asyncio.Lock()

    async def _event(self):
        event = await self.events.load_active()
        if event.public.event_type is not EventType.CHRISTMAS:
            raise ChristmasServiceError("這個指令只能在 Christmas 活動中使用。")
        return event

    async def _participant_ids(self) -> set[str]:
        event = await self._event()
        return {
            item.discord_user_id for item in event.private.participants
            if not item.withdrawn
        }

    async def say(self, author_id: str, content: str, *, channel_id: str | None = None) -> dict[str, Any]:
        if not content.strip():
            raise ChristmasServiceError("匿名內容不可為空白。")
        event = await self._event()
        if channel_id is not None and str(channel_id) != event.private.registration_channel_id:
            raise ChristmasServiceError("匿名訊息只能在活動報名頻道使用。")
        participant_ids = await self._participant_ids()
        if str(author_id) not in participant_ids:
            raise ChristmasServiceError("請先使用 `/event join` 報名，再使用匿名功能。")
        async with self._lock:
            messages = self.repository.load_auxiliary(event.public.event_key, "anonymous-messages.json", [])
            if not isinstance(messages, list):
                raise ChristmasServiceError("匿名訊息資料異常，請通知管理員。")
            message = {
                "message_id": secrets.token_urlsafe(12),
                "author_id": str(author_id),
                "content": content.strip(),
                "created_at": datetime.now(event.private.registration_starts_at.tzinfo).isoformat(),
            }
            messages.append(message)
            self.repository.save_auxiliary(event.public.event_key, "anonymous-messages.json", messages)
            return {"message_id": message["message_id"], "content": message["content"]}

    async def bind_discord_message(self, message_id: str, discord_message_id: str) -> None:
        """Bind the public Discord message ID in private state only."""
        event = await self._event()
        async with self._lock:
            messages = self.repository.load_auxiliary(event.public.event_key, "anonymous-messages.json", [])
            if not isinstance(messages, list):
                raise ChristmasServiceError("匿名訊息資料異常，請通知管理員。")
            message = next((item for item in messages if item.get("message_id") == message_id), None)
            if not isinstance(message, dict):
                raise ChristmasServiceError("找不到指定的匿名訊息，請確認訊息 ID 或連結。")
            message["discord_message_id"] = str(discord_message_id)
            self.repository.save_auxiliary(event.public.event_key, "anonymous-messages.json", messages)

    async def reply(self, author_id: str, message_id: str, content: str) -> dict[str, Any]:
        if not content.strip():
            raise ChristmasServiceError("匿名內容不可為空白。")
        event = await self._event()
        participant_ids = await self._participant_ids()
        if str(author_id) not in participant_ids:
            raise ChristmasServiceError("請先使用 `/event join` 報名，再使用匿名功能。")
        async with self._lock:
            messages = self.repository.load_auxiliary(event.public.event_key, "anonymous-messages.json", [])
            if not isinstance(messages, list):
                raise ChristmasServiceError("匿名訊息資料異常，請通知管理員。")
            original = next(
                (
                    item
                    for item in messages
                    if item.get("message_id") == message_id
                    or item.get("discord_message_id") == str(message_id)
                ),
                None,
            )
            if not isinstance(original, dict):
                raise ChristmasServiceError("找不到指定的匿名訊息，請確認訊息 ID 或連結。")
            blocked = await self._blocked_edges()
            if (str(author_id), str(original.get("author_id"))) in blocked:
                raise ChristmasServiceError("你無法對這位參加者發起匿名互動。")
            message = {
                "message_id": secrets.token_urlsafe(12),
                "author_id": str(author_id),
                "reply_to": message_id,
                "content": content.strip(),
                "created_at": datetime.now(event.private.registration_starts_at.tzinfo).isoformat(),
            }
            messages.append(message)
            self.repository.save_auxiliary(event.public.event_key, "anonymous-messages.json", messages)
            return {
                "message_id": message["message_id"],
                "content": message["content"],
                "reply_to_discord_message_id": original.get("discord_message_id"),
            }

    async def set_blacklist(self, owner_id: str, blocked_ids: list[str]) -> None:
        event = await self._event()
        participant_ids = await self._participant_ids()
        owner_id = str(owner_id)
        if owner_id not in participant_ids:
            raise ChristmasServiceError("請先使用 `/event join` 報名，再設定黑名單。")
        values = {str(value) for value in blocked_ids if str(value).strip()}
        unknown = values - participant_ids
        if unknown:
            raise ChristmasServiceError("黑名單中包含尚未報名的使用者。")
        values.discard(owner_id)
        async with self._lock:
            current = self.repository.load_auxiliary(event.public.event_key, "blacklist.json", {})
            if not isinstance(current, dict):
                raise ChristmasServiceError("黑名單資料異常，請通知管理員。")
            # Complete replacement semantics: an empty list clears the owner.
            current[owner_id] = sorted(values)
            self.repository.save_auxiliary(event.public.event_key, "blacklist.json", current)

    async def _blocked_edges(self) -> set[tuple[str, str]]:
        event = await self._event()
        data = self.repository.load_auxiliary(event.public.event_key, "blacklist.json", {})
        if not isinstance(data, dict):
            raise ChristmasServiceError("黑名單資料異常，請通知管理員。")
        blocked: set[tuple[str, str]] = set()
        for owner, values in data.items():
            if isinstance(values, list):
                blocked.update((str(value), str(owner)) for value in values)
        return blocked

    async def gift_shuffle(self, config: dict[str, Any] | None = None) -> dict[str, Any]:
        event = await self._event()
        if not event.private.matching_policy or not self.policy_resolver:
            raise ChristmasServiceError("尚未設定送禮配對規則，請通知管理員。")
        async with self._lock:
            existing = self.repository.load_auxiliary(event.public.event_key, "gift-assignments.json", None)
            if existing is not None:
                raise ChristmasServiceError("送禮配對已存在，為避免覆蓋既有結果，拒絕重新抽籤。")
            active_participants = [
                item for item in event.private.participants if not item.withdrawn
            ]
            policy = self.policy_resolver(event.private.matching_policy)
            assignments = policy.generate(
                active_participants,
                await self._blocked_edges(),
                config or {},
            )
            self._validate_assignments(active_participants, assignments, await self._blocked_edges())
            result = {
                "schema_version": 1,
                "matching_policy": event.private.matching_policy,
                "generated_at": datetime.now(event.private.registration_starts_at.tzinfo).isoformat(),
                "assignments": [item.to_dict() for item in assignments],
            }
            self.repository.save_auxiliary(event.public.event_key, "gift-assignments.json", result)
            return result

    @staticmethod
    def _validate_assignments(participants, assignments, blocked_edges) -> None:
        participant_ids = {item.discord_user_id for item in participants}
        for assignment in assignments:
            if not isinstance(assignment, GiftAssignment):
                raise ChristmasServiceError("送禮配對規則回傳了無效結果，請通知管理員。")
            if assignment.giver_id not in participant_ids or assignment.receiver_id not in participant_ids:
                raise ChristmasServiceError("送禮配對結果包含未知參加者，請通知管理員。")
            if (assignment.giver_id, assignment.receiver_id) in blocked_edges:
                raise ChristmasServiceError("送禮配對結果違反黑名單限制，請通知管理員。")

    async def gift_for(self, user_id: str) -> list[dict[str, Any]]:
        event = await self._event()
        data = self.repository.load_auxiliary(event.public.event_key, "gift-assignments.json", None)
        if not isinstance(data, dict):
            raise ChristmasServiceError("目前還沒有可查看的送禮配對結果。")
        assignments = data.get("assignments")
        if not isinstance(assignments, list):
            raise ChristmasServiceError("送禮配對資料異常，請通知管理員。")
        user_id = str(user_id)
        return [item for item in assignments if item.get("giver_id") == user_id or item.get("receiver_id") == user_id]
