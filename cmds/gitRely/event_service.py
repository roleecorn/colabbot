"""Event lifecycle and participant management."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Iterable
from zoneinfo import ZoneInfo

from .models import Event, EventPrivate, EventPublic, EventStatus, EventType, Participant, Topic, event_status
from .repositories import EventRepository
from .storage import new_participant_key, new_topic_key, safe_component


class EventServiceError(RuntimeError):
    pass


class EventService:
    _locks: dict[str, asyncio.Lock] = {}

    def __init__(self, repository: EventRepository, clock=None) -> None:
        self.repository = repository
        self.clock = clock or datetime.now

    @classmethod
    def _lock_for(cls, event_key: str) -> asyncio.Lock:
        return cls._locks.setdefault(event_key, asyncio.Lock())

    async def load_active(self) -> Event:
        public, private = await asyncio.to_thread(self.repository.load_active_event)
        return Event(public, private)

    async def activate_event(self, event_key: str) -> Event:
        try:
            public, private = await asyncio.to_thread(self.repository.activate_event, event_key)
        except (OSError, ValueError) as exc:
            raise EventServiceError("無法啟用活動，請確認活動設定與私密資料完整。") from exc
        return Event(public, private)

    async def create_event(
        self,
        *,
        event_key: str,
        display_name: str,
        event_type: str,
        timezone: str,
        registration_channel_id: str,
        registration_starts_at: datetime,
        registration_ends_at: datetime,
        submission_starts_at: datetime,
        submission_ends_at: datetime,
        topics: Iterable[str | Topic],
        matching_policy: str | None = None,
    ) -> Event:
        safe_component(event_key, label="event key")
        existing_public = None
        existing_private = None
        try:
            existing_public, existing_private = await asyncio.to_thread(
                self.repository.load_event, event_key
            )
        except FileNotFoundError:
            pass
        existing_keys: list[str] = []
        topic_models: list[Topic] = []
        for item in topics:
            if isinstance(item, Topic):
                topic_models.append(item)
                existing_keys.append(item.key)
            else:
                name = str(item).strip()
                if not name:
                    continue
                previous = next(
                    (topic.key for topic in (existing_public.topics if existing_public else [])
                     if topic.name == name),
                    None,
                )
                key = previous or new_topic_key(existing_keys)
                if key in existing_keys:
                    key = new_topic_key(existing_keys)
                existing_keys.append(key)
                topic_models.append(Topic(key=key, name=name))
        public = EventPublic(
            event_key=event_key,
            display_name=display_name,
            event_type=EventType(event_type),
            timezone=timezone,
            topics=topic_models,
        )
        private = EventPrivate(
            event_key=event_key,
            registration_channel_id=str(registration_channel_id),
            registration_starts_at=registration_starts_at,
            registration_ends_at=registration_ends_at,
            submission_starts_at=submission_starts_at,
            submission_ends_at=submission_ends_at,
            matching_policy=matching_policy,
            discussion_channel_id=(
                existing_private.discussion_channel_id if existing_private else None
            ),
            blacklist_ends_at=(existing_private.blacklist_ends_at if existing_private else None),
            max_blacklist_entries=(
                existing_private.max_blacklist_entries if existing_private else None
            ),
            max_blacklist_leaders=(
                existing_private.max_blacklist_leaders if existing_private else None
            ),
            host_user_ids=list(existing_private.host_user_ids) if existing_private else [],
            participants=list(existing_private.participants) if existing_private else [],
        )
        public.validate()
        private.validate(public)
        async with self._lock_for(event_key):
            await asyncio.to_thread(self.repository.save_public, public)
            await asyncio.to_thread(self.repository.save_private, private, public)
        return Event(public, private)

    @staticmethod
    def _now(public: EventPublic, clock) -> datetime:
        value = clock()
        if value.tzinfo is None or value.utcoffset() is None:
            value = value.replace(tzinfo=ZoneInfo(public.timezone))
        return value

    async def status(self) -> EventStatus:
        event = await self.load_active()
        return event_status(event.private, self._now(event.public, self.clock))

    async def participant(self, user_id: str) -> Participant | None:
        event = await self.load_active()
        return next(
            (
                item for item in event.private.participants
                if item.discord_user_id == str(user_id) and not item.withdrawn
            ),
            None,
        )

    async def participant_by_number(
        self, registration_number: int, *, include_withdrawn: bool = False
    ) -> Participant | None:
        event = await self.load_active()
        return next(
            (
                item for item in event.private.participants
                if item.registration_number == registration_number
                and (include_withdrawn or not item.withdrawn)
            ),
            None,
        )

    async def join(
        self,
        user_id: str,
        display_name: str = "",
        *,
        aa_image: str = "",
        team_leader: bool | None = None,
        notes: str = "",
    ) -> Participant:
        user_id = str(user_id)
        event = await self.load_active()
        async with self._lock_for(event.public.event_key):
            # Reload under the lock so two simultaneous joins cannot overwrite
            # each other's participant list.
            public, private = await asyncio.to_thread(
                self.repository.load_event, event.public.event_key
            )
            now = self._now(public, self.clock)
            if event_status(private, now) is not EventStatus.REGISTRATION_OPEN:
                raise EventServiceError("目前不是報名期間。")
            existing = next(
                (item for item in private.participants if item.discord_user_id == user_id),
                None,
            )
            if existing:
                if existing.withdrawn:
                    raise EventServiceError("你已取消報名，請使用恢復報名功能。")
                raise EventServiceError("你已經報名了。")
            participant = Participant(
                discord_user_id=user_id,
                participant_key=new_participant_key(
                    item.participant_key for item in private.participants
                ),
                joined_at=now,
                display_name=display_name,
                aa_image=aa_image,
                team_leader=team_leader,
                notes=notes,
                registration_number=max(
                    (item.registration_number for item in private.participants), default=0
                ) + 1,
            )
            private.participants.append(participant)
            await asyncio.to_thread(self.repository.save_private, private, public)
            return participant

    async def update_registration(
        self,
        user_id: str,
        *,
        display_name: str | None = None,
        aa_image: str | None = None,
        team_leader: bool | None = None,
        notes: str | None = None,
    ) -> Participant:
        """Update supplied signup fields while preserving all omitted values."""
        user_id = str(user_id)
        event = await self.load_active()
        async with self._lock_for(event.public.event_key):
            public, private = await asyncio.to_thread(
                self.repository.load_event, event.public.event_key
            )
            if event_status(private, self._now(public, self.clock)) is not EventStatus.REGISTRATION_OPEN:
                raise EventServiceError("目前不是報名期間。")
            participant = next(
                (
                    item for item in private.participants
                    if item.discord_user_id == user_id and not item.withdrawn
                ),
                None,
            )
            if participant is None:
                raise EventServiceError("找不到有效的報名資料。")
            if display_name is not None:
                if not display_name.strip():
                    raise EventServiceError("活動暱稱不可為空白。")
                participant.display_name = display_name.strip()
            if aa_image is not None:
                participant.aa_image = aa_image.strip()
            if team_leader is not None:
                participant.team_leader = team_leader
            if notes is not None:
                participant.notes = notes.strip()
            await asyncio.to_thread(self.repository.save_private, private, public)
            return participant

    async def set_signup_message(
        self, user_id: str, channel_id: str, message_id: str
    ) -> Participant:
        event = await self.load_active()
        async with self._lock_for(event.public.event_key):
            public, private = await asyncio.to_thread(
                self.repository.load_event, event.public.event_key
            )
            participant = next(
                (
                    item for item in private.participants
                    if item.discord_user_id == str(user_id)
                ),
                None,
            )
            if participant is None:
                raise EventServiceError("找不到有效的報名資料。")
            participant.signup_channel_id = str(channel_id)
            participant.signup_message_id = str(message_id)
            await asyncio.to_thread(self.repository.save_private, private, public)
            return participant

    async def set_discussion_channel(self, channel_id: str) -> None:
        event = await self.load_active()
        async with self._lock_for(event.public.event_key):
            public, private = await asyncio.to_thread(
                self.repository.load_event, event.public.event_key
            )
            private.discussion_channel_id = str(channel_id)
            await asyncio.to_thread(self.repository.save_private, private, public)

    async def set_blacklist_settings(
        self,
        *,
        ends_at: datetime,
        max_entries: int,
        max_leaders: int | None = None,
    ) -> None:
        event = await self.load_active()
        if event.public.event_type not in {EventType.CHRISTMAS, EventType.GROUP}:
            raise EventServiceError("目前活動類型不支援黑名單。")
        if ends_at.tzinfo is None or ends_at.utcoffset() is None:
            raise EventServiceError("黑名單截止時間必須包含時區。")
        if max_entries < 0 or (max_leaders is not None and max_leaders < 0):
            raise EventServiceError("黑名單上限不可為負數。")
        if max_leaders is not None and event.public.event_type is not EventType.GROUP:
            raise EventServiceError("組長黑名單上限只能用於組活。")
        async with self._lock_for(event.public.event_key):
            public, private = await asyncio.to_thread(
                self.repository.load_event, event.public.event_key
            )
            private.blacklist_ends_at = ends_at
            private.max_blacklist_entries = max_entries
            private.max_blacklist_leaders = max_leaders
            await asyncio.to_thread(self.repository.save_private, private, public)

    async def set_event_hosts(self, user_ids: Iterable[str]) -> None:
        event = await self.load_active()
        values = list(dict.fromkeys(str(value).strip() for value in user_ids if str(value).strip()))
        if any(not value.isdigit() for value in values):
            raise EventServiceError("主辦者清單只能包含 Discord 使用者 ID。")
        async with self._lock_for(event.public.event_key):
            public, private = await asyncio.to_thread(
                self.repository.load_event, event.public.event_key
            )
            private.host_user_ids = values
            await asyncio.to_thread(self.repository.save_private, private, public)

    async def leave(self, user_id: str) -> Participant:
        user_id = str(user_id)
        event = await self.load_active()
        async with self._lock_for(event.public.event_key):
            public, private = await asyncio.to_thread(
                self.repository.load_event, event.public.event_key
            )
            if event_status(private, self._now(public, self.clock)) is not EventStatus.REGISTRATION_OPEN:
                raise EventServiceError("目前不是報名期間。")
            participant = next(
                (item for item in private.participants if item.discord_user_id == user_id),
                None,
            )
            if participant is None or participant.withdrawn:
                raise EventServiceError("你尚未報名。")
            participant.withdrawn = True
            await asyncio.to_thread(self.repository.save_private, private, public)
            return participant

    async def restore(self, user_id: str) -> Participant:
        """Restore a withdrawn participant without changing their event number."""
        user_id = str(user_id)
        event = await self.load_active()
        async with self._lock_for(event.public.event_key):
            public, private = await asyncio.to_thread(
                self.repository.load_event, event.public.event_key
            )
            if event_status(private, self._now(public, self.clock)) is not EventStatus.REGISTRATION_OPEN:
                raise EventServiceError("目前不是報名期間。")
            participant = next(
                (item for item in private.participants if item.discord_user_id == user_id),
                None,
            )
            if participant is None:
                raise EventServiceError("找不到已取消的報名資料。")
            if not participant.withdrawn:
                raise EventServiceError("你的報名目前有效，不需要恢復。")
            participant.withdrawn = False
            await asyncio.to_thread(self.repository.save_private, private, public)
            return participant

    async def set_participant_avatar(self, user_id: str, avatar_path: str) -> Participant:
        """Store the public event-relative path for a participant's avatar."""
        user_id = str(user_id)
        event = await self.load_active()
        async with self._lock_for(event.public.event_key):
            public, private = await asyncio.to_thread(
                self.repository.load_event, event.public.event_key
            )
            participant = next(
                (item for item in private.participants if item.discord_user_id == user_id),
                None,
            )
            if participant is None:
                raise EventServiceError("找不到這位活動參賽者。")
            participant.avatar_path = avatar_path
            await asyncio.to_thread(self.repository.save_private, private, public)
            return participant

    async def resolve_topic(self, topic: str | None) -> Topic:
        event = await self.load_active()
        if topic is None or not str(topic).strip():
            if len(event.public.topics) == 1:
                return event.public.topics[0]
            raise EventServiceError("這個活動有多個題目，請指定題目。")
        value = str(topic).strip()
        for item in event.public.topics:
            if item.key == value or item.name == value:
                return item
        raise EventServiceError("指定的題目不在活動題目清單中。")
