"""Private anonymous-message, blacklist and gift-matching coordination."""

from __future__ import annotations

import asyncio
import secrets
from datetime import datetime
from typing import Any, Callable

from .event_service import EventService
from .models import EventType, GiftAssignment
from .matching.christmas import ChristmasGiftPolicy
from .matching.protocol import GiftMatchingPolicy


class ChristmasServiceError(RuntimeError):
    pass


class ChristmasService:
    def __init__(self, events: EventService, policy_resolver: Callable[[str], GiftMatchingPolicy] | None = None) -> None:
        self.events = events
        self.repository = events.repository
        self.policy_resolver = policy_resolver or self._resolve_policy
        self._lock = asyncio.Lock()

    @staticmethod
    def _resolve_policy(name: str) -> GiftMatchingPolicy:
        if name == "rules_2026":
            return ChristmasGiftPolicy()
        raise ChristmasServiceError(f"找不到配對規則：{name}")

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

    def _ensure_blacklist_open(self, event) -> None:
        private = event.private
        if private.blacklist_ends_at is None or private.max_blacklist_entries is None:
            raise ChristmasServiceError("管理員尚未設定本次活動的黑名單規則。")
        now = self.events._now(event.public, self.events.clock)
        if now > private.blacklist_ends_at:
            raise ChristmasServiceError("黑名單設定時間已結束。")

    def _read_blacklist(self, event) -> dict[str, list[str]]:
        current = self.repository.load_auxiliary(event.public.event_key, "blacklist.json", {})
        if not isinstance(current, dict):
            raise ChristmasServiceError("黑名單資料異常，請通知管理員。")
        if any(not isinstance(values, list) for values in current.values()):
            raise ChristmasServiceError("黑名單資料異常，請通知管理員。")
        return current

    async def _blacklist_event(self):
        event = await self.events.load_active()
        if event.public.event_type not in {EventType.CHRISTMAS, EventType.GROUP}:
            raise ChristmasServiceError("這個活動不支援黑名單功能。")
        return event

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

    async def _participant_for_number(self, number: int, *, active_only: bool = True):
        if number < 1:
            raise ChristmasServiceError("報名編號必須是正整數。")
        event = await self._blacklist_event()
        participant = next(
            (item for item in event.private.participants
             if item.registration_number == number and (not active_only or not item.withdrawn)),
            None,
        )
        if participant is None:
            raise ChristmasServiceError("找不到這個有效報名編號。")
        return event, participant

    async def _blacklist_owner(self, owner_id: str):
        event = await self._blacklist_event()
        owner = next(
            (item for item in event.private.participants
             if item.discord_user_id == str(owner_id) and not item.withdrawn),
            None,
        )
        if owner is None:
            raise ChristmasServiceError("請先報名才能調整黑名單。")
        return event, owner

    async def blacklist_add(self, owner_id: str, number: int) -> None:
        event, owner = await self._blacklist_owner(owner_id)
        self._ensure_blacklist_open(event)
        _, target = await self._participant_for_number(number)
        if owner.discord_user_id == target.discord_user_id:
            raise ChristmasServiceError("不能將自己加入黑名單。")
        async with self._lock:
            current = self._read_blacklist(event)
            values = {str(value) for value in current.get(owner.discord_user_id, [])}
            if target.discord_user_id in values:
                raise ChristmasServiceError("這位參加者已在你的黑名單中。")
            if len(values) >= event.private.max_blacklist_entries:
                raise ChristmasServiceError(
                    f"黑名單已達上限（{event.private.max_blacklist_entries} 人）。"
                )
            if (
                target.team_leader
                and event.private.max_blacklist_leaders is not None
            ):
                leaders = {
                    str(value) for value in values
                    if any(
                        item.discord_user_id == str(value) and item.team_leader
                        and not item.withdrawn
                        for item in event.private.participants
                    )
                }
                if len(leaders) >= event.private.max_blacklist_leaders:
                    raise ChristmasServiceError(
                        f"黑名單中的組長已達上限（{event.private.max_blacklist_leaders} 人）。"
                    )
            values.add(target.discord_user_id)
            current[owner.discord_user_id] = sorted(values)
            self.repository.save_auxiliary(event.public.event_key, "blacklist.json", current)

    async def blacklist_remove(self, owner_id: str, number: int) -> None:
        event, owner = await self._blacklist_owner(owner_id)
        self._ensure_blacklist_open(event)
        _, target = await self._participant_for_number(number, active_only=False)
        async with self._lock:
            current = self._read_blacklist(event)
            values = {str(value) for value in current.get(owner.discord_user_id, [])}
            if target.discord_user_id not in values:
                raise ChristmasServiceError("這位參加者不在你的黑名單中。")
            values.remove(target.discord_user_id)
            current[owner.discord_user_id] = sorted(values)
            self.repository.save_auxiliary(event.public.event_key, "blacklist.json", current)

    async def blacklist_view(self, owner_id: str) -> list[dict[str, Any]]:
        event, owner = await self._blacklist_owner(owner_id)
        self._ensure_blacklist_open(event)
        current = self._read_blacklist(event)
        ids = {str(value) for value in current.get(owner.discord_user_id, [])}
        return [
            {"registration_number": item.registration_number, "display_name": item.display_name}
            for item in event.private.participants
            if item.discord_user_id in ids
        ]

    async def sudo_view_blacklist(self) -> list[dict[str, Any]]:
        event = await self._blacklist_event()
        current = self._read_blacklist(event)
        participants = {item.discord_user_id: item for item in event.private.participants}
        rows = []
        for owner_id, target_ids in current.items():
            owner = participants.get(str(owner_id))
            for target_id in target_ids:
                target = participants.get(str(target_id))
                rows.append({
                    "owner_number": owner.registration_number if owner else None,
                    "owner_name": owner.display_name if owner else "（已移除參加者）",
                    "target_number": target.registration_number if target else None,
                    "target_name": target.display_name if target else "（已移除參加者）",
                })
        return rows

    async def sudo_change_blacklist(
        self, owner_number: int, target_number: int, *, add: bool
    ) -> None:
        event = await self._blacklist_event()
        if owner_number < 0 or target_number < 0 or (owner_number == target_number == 0):
            raise ChristmasServiceError("編號不可為負數，且兩個編號不能同時為 0。")
        participants = event.private.participants
        by_number = {item.registration_number: item for item in participants}
        owner = by_number.get(owner_number) if owner_number else None
        target = by_number.get(target_number) if target_number else None
        if owner_number and owner is None:
            raise ChristmasServiceError("找不到黑名單持有者的報名編號。")
        if target_number and target is None:
            raise ChristmasServiceError("找不到目標參加者的報名編號。")
        if add and (owner is None or target is None):
            raise ChristmasServiceError("新增黑名單時兩個編號都必須大於 0。")
        async with self._lock:
            current = self._read_blacklist(event)
            if add:
                values = {str(value) for value in current.get(owner.discord_user_id, [])}
                values.add(target.discord_user_id)
                current[owner.discord_user_id] = sorted(values)
            elif owner is None:
                for key, values in current.items():
                    current[key] = [str(value) for value in values
                                    if str(value) != target.discord_user_id]
            elif target is None:
                current[owner.discord_user_id] = []
            else:
                values = {str(value) for value in current.get(owner.discord_user_id, [])}
                values.discard(target.discord_user_id)
                current[owner.discord_user_id] = sorted(values)
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
            now = self.events._now(event.public, self.events.clock)
            locked = (
                now >= event.private.registration_ends_at
                and event.private.blacklist_ends_at is not None
                and now >= event.private.blacklist_ends_at
            )
            if existing is not None and locked:
                raise ChristmasServiceError("送禮配對已存在，為避免覆蓋既有結果，拒絕重新抽籤。")
            active_participants = [
                item for item in event.private.participants if not item.withdrawn
            ]
            policy = self.policy_resolver(event.private.matching_policy)
            blocked_edges = await self._gift_blocked_edges()
            assignments = policy.generate(
                active_participants,
                blocked_edges,
                config or {},
            )
            self._validate_assignments(active_participants, assignments, blocked_edges)
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
        giver_ids = [item.giver_id for item in assignments if isinstance(item, GiftAssignment)]
        receiver_ids = [item.receiver_id for item in assignments if isinstance(item, GiftAssignment)]
        if (
            len(giver_ids) != len(participant_ids)
            or set(giver_ids) != participant_ids
            or len(set(giver_ids)) != len(giver_ids)
            or set(receiver_ids) != participant_ids
            or len(set(receiver_ids)) != len(receiver_ids)
        ):
            raise ChristmasServiceError("送禮配對必須讓每位參加者恰好送出及收到一份禮物。")
        for assignment in assignments:
            if not isinstance(assignment, GiftAssignment):
                raise ChristmasServiceError("送禮配對規則回傳了無效結果，請通知管理員。")
            if assignment.giver_id not in participant_ids or assignment.receiver_id not in participant_ids:
                raise ChristmasServiceError("送禮配對結果包含未知參加者，請通知管理員。")
            if (assignment.giver_id, assignment.receiver_id) in blocked_edges:
                raise ChristmasServiceError("送禮配對結果違反黑名單限制，請通知管理員。")
            if assignment.giver_id == assignment.receiver_id:
                raise ChristmasServiceError("送禮配對結果包含自己配對，請通知管理員。")

    async def _gift_blocked_edges(self) -> set[tuple[str, str]]:
        event = await self._event()
        data = self.repository.load_auxiliary(event.public.event_key, "blacklist.json", {})
        if not isinstance(data, dict):
            raise ChristmasServiceError("黑名單資料異常，請通知管理員。")
        blocked: set[tuple[str, str]] = set()
        for owner, values in data.items():
            if not isinstance(values, list):
                raise ChristmasServiceError("黑名單資料異常，請通知管理員。")
            for value in values:
                owner, value = str(owner), str(value)
                blocked.add((owner, value))
                blocked.add((value, owner))
        return blocked

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

    async def gift_recipient_for(self, user_id: str):
        event = await self._event()
        data = self.repository.load_auxiliary(event.public.event_key, "gift-assignments.json", None)
        if not isinstance(data, dict) or not isinstance(data.get("assignments"), list):
            raise ChristmasServiceError("目前還沒有可查看的送禮配對結果。")
        assignment = next(
            (item for item in data["assignments"]
             if isinstance(item, dict) and item.get("giver_id") == str(user_id)),
            None,
        )
        if assignment is None:
            raise ChristmasServiceError("找不到你的送禮配對資料。")
        recipient = next(
            (item for item in event.private.participants
             if item.discord_user_id == str(assignment.get("receiver_id")) and not item.withdrawn),
            None,
        )
        if recipient is None:
            raise ChristmasServiceError("找不到收禮者資料。")
        return recipient

    async def matching_locked(self) -> bool:
        event = await self._event()
        now = self.events._now(event.public, self.events.clock)
        return (
            now >= event.private.registration_ends_at
            and event.private.blacklist_ends_at is not None
            and now >= event.private.blacklist_ends_at
        )

    async def all_gift_assignments(self) -> list[dict[str, Any]]:
        event = await self._event()
        data = self.repository.load_auxiliary(event.public.event_key, "gift-assignments.json", None)
        if not isinstance(data, dict) or not isinstance(data.get("assignments"), list):
            raise ChristmasServiceError("目前還沒有可公開的送禮配對結果。")
        return data["assignments"]
