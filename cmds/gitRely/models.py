"""Domain models for the event system.

The models deliberately keep Discord objects and filesystem details out of the
event services.  Private models are serialised separately from the public
event configuration so that a Pages repository can safely be public.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import re
from typing import Any, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class EventType(str, Enum):
    SUBMISSION = "submission"
    CHRISTMAS = "christmas"
    GROUP = "group"


class EventStatus(str, Enum):
    SCHEDULED = "scheduled"
    REGISTRATION_OPEN = "registration_open"
    WAITING_SUBMISSION = "waiting_submission"
    SUBMISSION_OPEN = "submission_open"
    CLOSED = "closed"


def _required_string(data: Mapping[str, Any], name: str) -> str:
    value = data.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _safe_key(value: str, name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", value):
        raise ValueError(f"{name} must be a URL-safe path key")
    return value


def _parse_datetime(value: Any, name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be an ISO datetime")
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{name} is not a valid ISO datetime") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone")
    return result


def _datetime_json(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must include a timezone")
    return value.isoformat()


@dataclass(frozen=True)
class Topic:
    key: str
    name: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Topic":
        if not isinstance(data, Mapping):
            raise ValueError("topic must be an object")
        return cls(_safe_key(_required_string(data, "key"), "topic key"), _required_string(data, "name"))

    def to_dict(self) -> dict[str, str]:
        return {"key": self.key, "name": self.name}


@dataclass
class Participant:
    discord_user_id: str
    participant_key: str
    joined_at: datetime
    display_name: str = ""
    avatar_path: str = ""
    registration_number: int = 0
    withdrawn: bool = False
    aa_image: str = ""
    team_leader: bool | None = None
    notes: str = ""
    signup_channel_id: str = ""
    signup_message_id: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Participant":
        return cls(
            discord_user_id=_required_string(data, "discord_user_id"),
            participant_key=_required_string(data, "participant_key"),
            joined_at=_parse_datetime(data.get("joined_at"), "joined_at"),
            display_name=str(data.get("display_name", "")),
            avatar_path=str(data.get("avatar_path", "")),
            registration_number=int(data.get("registration_number", 0)),
            withdrawn=bool(data.get("withdrawn", False)),
            aa_image=str(data.get("aa_image", "")),
            team_leader=data.get("team_leader") if isinstance(data.get("team_leader"), bool) else None,
            notes=str(data.get("notes", "")),
            signup_channel_id=str(data.get("signup_channel_id", "")),
            signup_message_id=str(data.get("signup_message_id", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        data = {
            "discord_user_id": self.discord_user_id,
            "participant_key": self.participant_key,
            "joined_at": _datetime_json(self.joined_at),
            "registration_number": self.registration_number,
            "withdrawn": self.withdrawn,
        }
        if self.display_name:
            data["display_name"] = self.display_name
        if self.avatar_path:
            data["avatar_path"] = self.avatar_path
        if self.aa_image:
            data["aa_image"] = self.aa_image
        if self.team_leader is not None:
            data["team_leader"] = self.team_leader
        if self.notes:
            data["notes"] = self.notes
        if self.signup_channel_id:
            data["signup_channel_id"] = self.signup_channel_id
        if self.signup_message_id:
            data["signup_message_id"] = self.signup_message_id
        return data


@dataclass
class EventPublic:
    event_key: str
    display_name: str
    event_type: EventType
    timezone: str
    topics: list[Topic]
    schema_version: int = 1

    def validate(self) -> None:
        _safe_key(_required_string({"value": self.event_key}, "value"), "event key")
        _required_string({"value": self.display_name}, "value")
        try:
            self.event_type = EventType(self.event_type)
        except ValueError as exc:
            raise ValueError("event_type must be submission, christmas or group") from exc
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"invalid IANA timezone: {self.timezone}") from exc
        if not self.topics:
            raise ValueError("an event must define at least one topic")
        keys = [topic.key for topic in self.topics]
        if len(keys) != len(set(keys)):
            raise ValueError("topic keys must be unique")
        for key in keys:
            _safe_key(key, "topic key")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "EventPublic":
        if not isinstance(data, Mapping):
            raise ValueError("public event configuration must be an object")
        raw_topics = data.get("topics")
        if not isinstance(raw_topics, list):
            raise ValueError("topics must be a list")
        try:
            event_type = EventType(_required_string(data, "event_type"))
        except ValueError as exc:
            raise ValueError("event_type must be submission, christmas or group") from exc
        result = cls(
            event_key=_required_string(data, "event_key"),
            display_name=_required_string(data, "display_name"),
            event_type=event_type,
            timezone=_required_string(data, "timezone"),
            topics=[Topic.from_dict(topic) for topic in raw_topics],
            schema_version=int(data.get("schema_version", 1)),
        )
        result.validate()
        return result

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema_version": self.schema_version,
            "event_key": self.event_key,
            "display_name": self.display_name,
            "event_type": self.event_type.value,
            "timezone": self.timezone,
            "topics": [topic.to_dict() for topic in self.topics],
        }


@dataclass
class EventPrivate:
    event_key: str
    registration_channel_id: str
    registration_starts_at: datetime
    registration_ends_at: datetime
    submission_starts_at: datetime
    submission_ends_at: datetime
    discussion_channel_id: str | None = None
    blacklist_ends_at: datetime | None = None
    max_blacklist_entries: int | None = None
    max_blacklist_leaders: int | None = None
    participants: list[Participant] = field(default_factory=list)
    matching_policy: str | None = None
    schema_version: int = 1

    def validate(self, public: EventPublic | None = None) -> None:
        _safe_key(_required_string({"value": self.event_key}, "value"), "event key")
        _required_string({"value": self.registration_channel_id}, "value")
        if self.discussion_channel_id is not None:
            _required_string({"value": self.discussion_channel_id}, "value")
        if self.blacklist_ends_at is not None and (
            self.blacklist_ends_at.tzinfo is None or self.blacklist_ends_at.utcoffset() is None
        ):
            raise ValueError("blacklist_ends_at must include a timezone")
        for name, value in (
            ("max_blacklist_entries", self.max_blacklist_entries),
            ("max_blacklist_leaders", self.max_blacklist_leaders),
        ):
            if value is not None and (not isinstance(value, int) or value < 0):
                raise ValueError(f"{name} must be a non-negative integer")
        dates = [
            self.registration_starts_at,
            self.registration_ends_at,
            self.submission_starts_at,
            self.submission_ends_at,
        ]
        if any(value.tzinfo is None or value.utcoffset() is None for value in dates):
            raise ValueError("event datetimes must include a timezone")
        if not (
            self.registration_starts_at
            < self.registration_ends_at
            <= self.submission_starts_at
            < self.submission_ends_at
        ):
            raise ValueError("event times must be in chronological order")
        user_ids = [participant.discord_user_id for participant in self.participants]
        keys = [participant.participant_key for participant in self.participants]
        numbers = [participant.registration_number for participant in self.participants]
        if len(user_ids) != len(set(user_ids)):
            raise ValueError("participant Discord IDs must be unique")
        if len(keys) != len(set(keys)):
            raise ValueError("participant keys must be unique")
        if any(not isinstance(number, int) or number < 1 for number in numbers):
            raise ValueError("participant registration numbers must be positive integers")
        if len(numbers) != len(set(numbers)):
            raise ValueError("participant registration numbers must be unique")
        for key in keys:
            _safe_key(key, "participant key")
        if public and public.event_key != self.event_key:
            raise ValueError("public and private event keys do not match")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "EventPrivate":
        if not isinstance(data, Mapping):
            raise ValueError("private event state must be an object")
        raw_participants = data.get("participants", [])
        if not isinstance(raw_participants, list):
            raise ValueError("participants must be a list")
        result = cls(
            event_key=_required_string(data, "event_key"),
            registration_channel_id=_required_string(data, "registration_channel_id"),
            discussion_channel_id=(
                str(data["discussion_channel_id"])
                if data.get("discussion_channel_id") is not None else None
            ),
            blacklist_ends_at=(
                _parse_datetime(data["blacklist_ends_at"], "blacklist_ends_at")
                if data.get("blacklist_ends_at") else None
            ),
            max_blacklist_entries=(
                int(data["max_blacklist_entries"])
                if data.get("max_blacklist_entries") is not None else None
            ),
            max_blacklist_leaders=(
                int(data["max_blacklist_leaders"])
                if data.get("max_blacklist_leaders") is not None else None
            ),
            registration_starts_at=_parse_datetime(
                data.get("registration_starts_at"), "registration_starts_at"
            ),
            registration_ends_at=_parse_datetime(
                data.get("registration_ends_at"), "registration_ends_at"
            ),
            submission_starts_at=_parse_datetime(
                data.get("submission_starts_at"), "submission_starts_at"
            ),
            submission_ends_at=_parse_datetime(data.get("submission_ends_at"), "submission_ends_at"),
            participants=[
                Participant.from_dict(
                    {**item, "registration_number": item.get("registration_number", index)}
                )
                for index, item in enumerate(raw_participants, start=1)
            ],
            matching_policy=data.get("matching_policy"),
            schema_version=int(data.get("schema_version", 1)),
        )
        result.validate()
        return result

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        data: dict[str, Any] = {
            "schema_version": self.schema_version,
            "event_key": self.event_key,
            "registration_channel_id": self.registration_channel_id,
            "registration_starts_at": _datetime_json(self.registration_starts_at),
            "registration_ends_at": _datetime_json(self.registration_ends_at),
            "submission_starts_at": _datetime_json(self.submission_starts_at),
            "submission_ends_at": _datetime_json(self.submission_ends_at),
            "participants": [participant.to_dict() for participant in self.participants],
        }
        if self.discussion_channel_id:
            data["discussion_channel_id"] = self.discussion_channel_id
        if self.blacklist_ends_at:
            data["blacklist_ends_at"] = _datetime_json(self.blacklist_ends_at)
        if self.max_blacklist_entries is not None:
            data["max_blacklist_entries"] = self.max_blacklist_entries
        if self.max_blacklist_leaders is not None:
            data["max_blacklist_leaders"] = self.max_blacklist_leaders
        if self.matching_policy:
            data["matching_policy"] = self.matching_policy
        return data


@dataclass(frozen=True)
class GiftAssignment:
    giver_id: str
    receiver_id: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"giver_id": self.giver_id, "receiver_id": self.receiver_id, **self.details}


def event_status(event: EventPrivate, now: datetime | None = None) -> EventStatus:
    current = now or datetime.now(event.registration_starts_at.tzinfo)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("now must include a timezone")
    if current < event.registration_starts_at:
        return EventStatus.SCHEDULED
    if current < event.registration_ends_at:
        return EventStatus.REGISTRATION_OPEN
    if current < event.submission_starts_at:
        return EventStatus.WAITING_SUBMISSION
    if current < event.submission_ends_at:
        return EventStatus.SUBMISSION_OPEN
    return EventStatus.CLOSED


@dataclass
class Event:
    public: EventPublic
    private: EventPrivate

    def validate(self) -> None:
        self.public.validate()
        self.private.validate(self.public)

    @property
    def status(self) -> EventStatus:
        return event_status(self.private)
