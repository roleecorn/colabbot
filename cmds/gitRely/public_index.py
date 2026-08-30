"""Build the public, identity-safe index consumed by event pages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import quote

from .models import Event, Participant, Topic
from .repositories import atomic_write_json, read_json


@dataclass(frozen=True)
class PublicIndexSnapshot:
    """The previous state of the two public index files."""

    files: tuple[tuple[Path, bytes | None], ...]


class PublicEventIndex:
    """Persist the small public manifest used by the static event UI.

    The public manifest deliberately contains only the random participant key
    and display name.  Discord IDs and the private participant list stay in
    ``data/events`` outside the event repository.
    """

    PARTICIPANTS_FILE = "playerHashMap.json"
    WORKS_FILE = "workUserMap.json"

    def __init__(self, event_repository) -> None:
        self.event_repository = event_repository

    def _paths(self, event_key: str) -> tuple[Path, Path]:
        data_dir = self.event_repository.public_dir(event_key) / "data"
        return data_dir / self.PARTICIPANTS_FILE, data_dir / self.WORKS_FILE

    def snapshot(self, event_key: str) -> PublicIndexSnapshot:
        return PublicIndexSnapshot(
            tuple(
                (path, path.read_bytes() if path.exists() else None)
                for path in self._paths(event_key)
            )
        )

    @staticmethod
    def _read_list(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        value = read_json(path)
        if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
            raise ValueError(f"public index must be a list of objects: {path}")
        return value

    @staticmethod
    def _participant_rows(participants: list[Participant]) -> list[dict[str, Any]]:
        return [
            {
                "uid": uid,
                "hashId": participant.participant_key,
                "name": participant.display_name or f"參加者 {uid}",
            }
            for uid, participant in enumerate(participants, start=1)
        ]

    @classmethod
    def _participant_rows_with_avatars(
        cls, participants: list[Participant]
    ) -> list[dict[str, Any]]:
        rows = cls._participant_rows(participants)
        for row, participant in zip(rows, participants):
            if participant.avatar_path:
                row["image"] = participant.avatar_path
        return rows

    @staticmethod
    def _topic_position(topics: list[Topic], topic_key: str) -> int:
        for position, topic in enumerate(topics):
            if topic.key == topic_key:
                return position
        return len(topics)

    @staticmethod
    def work_url(participant_key: str, topic_key: str, file_path: str = "index.html") -> str:
        relative = PurePosixPath(file_path)
        if (
            relative.is_absolute()
            or not relative.parts
            or any(part in {"", ".", ".."} for part in relative.parts)
            or "\\" in file_path
        ):
            raise ValueError("invalid submission HTML path")
        encoded_file = quote(relative.as_posix(), safe="/:@-._~!$&'()*+,;=")
        suffix = "" if relative.parts == ("index.html",) else encoded_file
        return f"pieces/{participant_key}/{topic_key}/" + suffix

    def _normalise_works(
        self,
        works: list[dict[str, Any]],
        participants: list[Participant],
        topics: list[Topic],
    ) -> list[dict[str, Any]]:
        rows_by_key = {
            participant.participant_key: (uid, participant)
            for uid, participant in enumerate(participants, start=1)
        }
        result: list[dict[str, Any]] = []
        for work in works:
            participant_key = work.get("hashId") or work.get("participantKey")
            topic_key = work.get("topicKey")
            if not isinstance(participant_key, str) or not isinstance(topic_key, str):
                continue
            participant_row = rows_by_key.get(participant_key)
            topic = next((item for item in topics if item.key == topic_key), None)
            if participant_row is None or topic is None:
                continue
            uid, participant = participant_row
            title = str(work.get("title", "")).strip()
            if not title:
                continue
            file_path = str(work.get("file", "index.html"))
            result.append(
                {
                    "hashId": participant_key,
                    "topicKey": topic.key,
                    "topic": topic.name,
                    "title": title,
                    "file": file_path,
                    "url": self.work_url(participant_key, topic.key, file_path),
                    "uid": uid,
                    "name": participant.display_name or f"參加者 {uid}",
                }
            )
        return result

    def _sort_works(self, works: list[dict[str, Any]], topics: list[Topic]) -> list[dict[str, Any]]:
        return sorted(
            works,
            key=lambda work: (
                int(work.get("uid", 0)),
                self._topic_position(topics, str(work.get("topicKey", ""))),
                str(work.get("title", "")),
            ),
        )

    def _write(
        self,
        event: Event,
        participants: list[dict[str, Any]],
        works: list[dict[str, Any]],
    ) -> None:
        participant_path, work_path = self._paths(event.public.event_key)
        atomic_write_json(participant_path, participants)
        atomic_write_json(work_path, works)

    def sync_participants(self, event: Event) -> PublicIndexSnapshot:
        """Refresh public participant names and icons without changing works."""
        snapshot = self.snapshot(event.public.event_key)
        _, work_path = self._paths(event.public.event_key)
        works = self._normalise_works(
            self._read_list(work_path), event.private.participants, event.public.topics
        )
        self._write(
            event,
            self._participant_rows_with_avatars(event.private.participants),
            self._sort_works(works, event.public.topics),
        )
        return snapshot

    def upsert_work(
        self,
        event: Event,
        participant: Participant,
        topic: Topic,
        title: str,
        file_path: str = "index.html",
    ) -> PublicIndexSnapshot:
        snapshot = self.snapshot(event.public.event_key)
        participant_rows = self._participant_rows_with_avatars(event.private.participants)
        participant_keys = {row["hashId"] for row in participant_rows}
        if participant.participant_key not in participant_keys:
            raise ValueError("participant is not in the event participant list")
        _, work_path = self._paths(event.public.event_key)
        works = self._normalise_works(
            self._read_list(work_path), event.private.participants, event.public.topics
        )
        works = [
            work
            for work in works
            if not (
                work["hashId"] == participant.participant_key
                and work["topicKey"] == topic.key
            )
        ]
        uid = next(
            uid for uid, item in enumerate(event.private.participants, start=1)
            if item.participant_key == participant.participant_key
        )
        works.append(
            {
                "hashId": participant.participant_key,
                "topicKey": topic.key,
                "topic": topic.name,
                "title": title.strip(),
                "file": file_path,
                "url": self.work_url(participant.participant_key, topic.key, file_path),
                "uid": uid,
                "name": participant.display_name or f"參加者 {uid}",
            }
        )
        self._write(
            event,
            participant_rows,
            self._sort_works(works, event.public.topics),
        )
        return snapshot

    def remove_work(self, event: Event, participant: Participant, topic: Topic) -> PublicIndexSnapshot:
        snapshot = self.snapshot(event.public.event_key)
        _, work_path = self._paths(event.public.event_key)
        participant_rows = self._participant_rows_with_avatars(event.private.participants)
        works = self._normalise_works(
            self._read_list(work_path), event.private.participants, event.public.topics
        )
        works = [
            work
            for work in works
            if not (
                work["hashId"] == participant.participant_key
                and work["topicKey"] == topic.key
            )
        ]
        self._write(
            event,
            participant_rows,
            self._sort_works(works, event.public.topics),
        )
        return snapshot

    @staticmethod
    def restore(snapshot: PublicIndexSnapshot) -> None:
        for path, content in snapshot.files:
            if content is None:
                path.unlink(missing_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
