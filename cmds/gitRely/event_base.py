import os
from typing import Optional, Tuple

import discord

from core.classes import Cog_extension
from .event_utils import (
    EventInfo,
    format_datetime,
    is_new_participant,
    parse_datetime,
    read_event_info,
    write_event_info,
)


class EventBase(Cog_extension):
    def __init__(self, bot):
        super().__init__(bot)
        self.upload_dir = "./uploads"
        os.makedirs(self.upload_dir, exist_ok=True)
        self.participants = []
        self.eventName = "TBD"
        self.registration = "TBD"
        self.eventStart = "TBD"
        self.registrationEnd = "TBD"
        self.uploadEnd = "TBD"
        self.isTeamEvent = False
        self.topics = []
        self.recent_event_file = os.path.join("./data/", "RecentEvent.txt")
        if os.path.exists(self.recent_event_file):
            with open(self.recent_event_file, "r", encoding="utf-8") as f:
                name = f.read().strip()
                if name:
                    self.eventName = name
                    self.loadData()

    def loadData(self) -> bool:
        info = read_event_info(self.eventName)
        if not info:
            return False
        self.participants = info.participants
        self.eventName = info.event_name
        self.registration = info.registration
        self.eventStart = info.event_start
        self.registrationEnd = info.registration_end
        self.uploadEnd = info.upload_end
        self.isTeamEvent = info.is_team_event
        self.topics = info.topics
        return True

    def save_event_info(self, extra: Optional[dict] = None) -> None:
        info = EventInfo(
            event_name=self.eventName,
            participants=self.participants,
            registration=self.registration,
            event_start=self.eventStart,
            registration_end=self.registrationEnd,
            upload_end=self.uploadEnd,
            is_team_event=self.isTeamEvent,
            topics=self.topics,
        )
        write_event_info(self.eventName, info, extra=extra)

    def isNewParticipant(self, user_id: str) -> bool:
        return is_new_participant(self.participants, user_id)

    async def _send(self, interaction: discord.Interaction, content: str, *, ephemeral: bool = False):
        if interaction.response.is_done():
            await interaction.followup.send(content, ephemeral=ephemeral)
        else:
            await interaction.response.send_message(content, ephemeral=ephemeral)

    async def _send_error(self, interaction: discord.Interaction, content: str):
        await self._send(interaction, content, ephemeral=True)

    async def _parse_time_arg(
        self, interaction: discord.Interaction, label: str, value: Optional[str]
    ) -> Tuple[bool, Optional[str]]:
        if value is None:
            return True, None
        parsed = parse_datetime(value)
        if parsed is None:
            await self._send_error(
                interaction,
                f"{label} format invalid. Use yyyymmdd-HHMM, e.g. 20260206-2030",
            )
            return False, None
        return True, format_datetime(parsed)

    async def _set_event_name_common(
        self,
        interaction: discord.Interaction,
        event_name: str,
        start_time: Optional[str] = None,
        registration_deadline: Optional[str] = None,
        upload_deadline: Optional[str] = None,
        is_team_event: Optional[bool] = None,
        topics: Optional[str] = None,
    ) -> bool:
        # if not interaction.guild or not self.bIsAAFanclub(interaction):
        #     await self._send_error(interaction, "Wrong guild.")
        #     return False
        if not self.bIsAdmin(interaction.user) and not self.bIsDeveloper(interaction.user.id):
            await self._send_error(interaction, "Admin only.")
            return False

        folder_path = os.path.join("./", event_name)
        if not os.path.exists(folder_path):
            await self._send_error(interaction, f"Event folder not found: `{event_name}`")
            return False

        self.eventName = event_name
        self.loadData()
        self.registration = str(interaction.channel_id)

        ok, parsed = await self._parse_time_arg(interaction, "event_start", start_time)
        if not ok:
            return False
        if parsed is not None:
            self.eventStart = parsed

        ok, parsed = await self._parse_time_arg(interaction, "registration_deadline", registration_deadline)
        if not ok:
            return False
        if parsed is not None:
            self.registrationEnd = parsed

        ok, parsed = await self._parse_time_arg(interaction, "upload_deadline", upload_deadline)
        if not ok:
            return False
        if parsed is not None:
            self.uploadEnd = parsed

        if is_team_event is not None:
            self.isTeamEvent = is_team_event

        if topics is not None:
            parsed_topics = [t.strip() for t in topics.split(",") if t.strip()]
            self.topics = parsed_topics

        os.makedirs(os.path.dirname(self.recent_event_file), exist_ok=True)
        with open(self.recent_event_file, "w", encoding="utf-8") as f:
            f.write(self.eventName)

        self.save_event_info()
        await self._send(interaction, f"Event set: `{self.eventName}`")
        return True
