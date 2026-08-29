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
            (item for item in event.private.participants if item.discord_user_id == str(user_id)),
            None,
        )

    async def join(self, user_id: str, display_name: str = "") -> Participant:
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
            if any(item.discord_user_id == user_id for item in private.participants):
                raise EventServiceError("你已經報名了。")
            participant = Participant(
                discord_user_id=user_id,
                participant_key=new_participant_key(
                    item.participant_key for item in private.participants
                ),
                joined_at=now,
                display_name=display_name,
            )
            private.participants.append(participant)
            await asyncio.to_thread(self.repository.save_private, private, public)
            return participant

    async def leave(self, user_id: str) -> None:
        user_id = str(user_id)
        event = await self.load_active()
        async with self._lock_for(event.public.event_key):
            public, private = await asyncio.to_thread(
                self.repository.load_event, event.public.event_key
            )
            if event_status(private, self._now(public, self.clock)) is not EventStatus.REGISTRATION_OPEN:
                raise EventServiceError("目前不是報名期間。")
            before = len(private.participants)
            private.participants[:] = [
                item for item in private.participants if item.discord_user_id != user_id
            ]
            if len(private.participants) == before:
                raise EventServiceError("你尚未報名。")
            await asyncio.to_thread(self.repository.save_private, private, public)

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
