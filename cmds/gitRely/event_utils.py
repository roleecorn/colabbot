import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

DATETIME_FORMAT = "%Y%m%d-%H%M"


def hash_user_id(user_id: str) -> str:
    # Use SHA256 and first 8 chars for folder name
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:8]


def parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value or value == "TBD":
        return None
    try:
        return datetime.strptime(value, DATETIME_FORMAT)
    except (ValueError, TypeError):
        return None


def format_datetime(value: datetime) -> str:
    return value.strftime(DATETIME_FORMAT)


def is_past_deadline(value: Optional[str]) -> bool:
    parsed = parse_datetime(value)
    if parsed is None:
        return False
    return datetime.now() > parsed


def event_info_path(event_name: str) -> str:
    return os.path.join(f"./{event_name}/", "eventInfo.json")


@dataclass
class EventInfo:
    event_name: str = "TBD"
    participants: list = field(default_factory=list)
    registration: str = "TBD"
    event_start: str = "TBD"
    registration_end: str = "TBD"
    upload_end: str = "TBD"
    is_team_event: bool = False
    topics: list = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "EventInfo":
        return cls(
            event_name=data.get("eventName", "TBD"),
            participants=data.get("participants", []),
            registration=data.get("Registration", "TBD"),
            event_start=data.get("eventStart", "TBD"),
            registration_end=data.get("registrationEnd", "TBD"),
            upload_end=data.get("uploadEnd", "TBD"),
            is_team_event=data.get("isTeamEvent", False),
            topics=data.get("topics", []) or [],
        )

    def to_dict(self) -> dict:
        return {
            "eventName": self.event_name,
            "participants": self.participants,
            "Registration": self.registration,
            "eventStart": self.event_start,
            "registrationEnd": self.registration_end,
            "uploadEnd": self.upload_end,
            "isTeamEvent": self.is_team_event,
            "topics": self.topics,
        }


def is_new_participant(participants: list, user_id: str) -> bool:
    if not participants:
        return True
    for p in participants:
        if p.get("id") == user_id:
            return False
    return True


def make_index(folder_path: str, title: str) -> None:
    html_content = ""
    with open("template.html", "r", encoding="utf-8") as file:
        html_content = file.read()

    if not html_content:
        return

    tmp_html = html_content.replace("123標題預留位321", title)

    image_files = [
        f
        for f in os.listdir(folder_path)
        if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))
    ]
    image_tags = ""
    for idx, fname in enumerate(sorted(image_files), start=1):
        image_path = fname
        image_tags += (
            f'<img src="{image_path}" alt="Image {idx}" '
            f'style="max-width:100%; height:auto;"><br>\n'
        )

    tmp_html = tmp_html.replace("456圖片預留位654", image_tags)

    output_path = os.path.join(folder_path, f"{title}.html")
    with open(output_path, "w", encoding="utf-8") as out:
        out.write(tmp_html)


def normalize_topic_name(value: str) -> str:
    name = (value or "").strip()
    if not name:
        return "TBD"
    name = name.replace("/", "_").replace("\\", "_")
    name = name.replace("..", "_")
    return name


def read_event_info(event_name: str) -> Optional[EventInfo]:
    path = event_info_path(event_name)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="UTF-8") as f:
        return EventInfo.from_dict(json.load(f))


def write_event_info(event_name: str, info: EventInfo, extra: Optional[dict] = None) -> None:
    data = info.to_dict()
    if extra:
        data.update(extra)
    path = event_info_path(event_name)
    with open(path, "w", encoding="UTF-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


async def setup(bot):
    # No-op setup so extension loader doesn't error; utilities only.
    return
