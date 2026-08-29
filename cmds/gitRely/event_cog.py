"""The single Discord Cog for both submission and Christmas events."""

from __future__ import annotations

import logging
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import discord
from discord import app_commands

from core.classes import Cog_extension

from .christmas_service import ChristmasService, ChristmasServiceError
from .event_service import EventService, EventServiceError
from .models import EventType
from .repositories import EventRepository
from .submission_service import SubmissionService, SubmissionServiceError

logger = logging.getLogger(__name__)


class EventCog(Cog_extension):
    def __init__(
        self,
        bot,
        *,
        repository: EventRepository | None = None,
        event_service: EventService | None = None,
        submission_service: SubmissionService | None = None,
        christmas_service: ChristmasService | None = None,
    ) -> None:
        super().__init__(bot)
        self.repository = repository or EventRepository()
        self.event_service = event_service or EventService(self.repository)
        self.submission_service = submission_service or SubmissionService(self.event_service)
        self.christmas_service = christmas_service or ChristmasService(self.event_service)

    async def _send(self, interaction: discord.Interaction, content: str, *, ephemeral: bool = False):
        if interaction.response.is_done():
            return await interaction.followup.send(content, ephemeral=ephemeral)
        return await interaction.response.send_message(content, ephemeral=ephemeral)

    async def _error(self, interaction: discord.Interaction, content: str):
        await self._send(interaction, content, ephemeral=True)

    @staticmethod
    def _user_error(exc: Exception, fallback: str = "處理指令時發生錯誤，請稍後再試或通知管理員。") -> str:
        if isinstance(exc, (EventServiceError, SubmissionServiceError, ChristmasServiceError)):
            return str(exc)
        if isinstance(exc, ValueError) and any("\u4e00" <= char <= "\u9fff" for char in str(exc)):
            return str(exc)
        return fallback

    async def _unexpected_error(self, interaction: discord.Interaction, command: str, exc: Exception):
        logger.error("Unhandled error in /%s", command, exc_info=(type(exc), exc, exc.__traceback__))
        try:
            await self._error(interaction, "處理指令時發生未預期錯誤，請稍後再試或通知管理員。")
        except (discord.HTTPException, discord.InteractionResponded) as response_error:
            logger.error("Could not send /%s error response", command, exc_info=response_error)

    def _is_admin(self, interaction: discord.Interaction) -> bool:
        return self.bIsAdmin(interaction.user) or self.bIsDeveloper(interaction.user.id)

    @staticmethod
    def _parse_datetime(value: str, timezone: str) -> datetime:
        raw = value.strip()
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            try:
                parsed = datetime.strptime(raw, "%Y%m%d-%H%M")
            except ValueError as exc:
                raise ValueError("時間格式需為 ISO datetime 或 yyyymmdd-HHMM") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            parsed = parsed.replace(tzinfo=ZoneInfo(timezone))
        return parsed

    async def activate_event(
        self,
        interaction: discord.Interaction,
        event_name: str,
        *,
        event_type: str,
        timezone: str,
        registration_starts_at: str,
        registration_ends_at: str,
        submission_starts_at: str,
        submission_ends_at: str,
        topics: str,
    ):
        parsed_topics = [item.strip() for item in topics.split(",") if item.strip()]
        if not parsed_topics:
            raise EventServiceError("至少需要一個題目")
        values = {
            name: self._parse_datetime(value, timezone)
            for name, value in {
                "registration_starts_at": registration_starts_at,
                "registration_ends_at": registration_ends_at,
                "submission_starts_at": submission_starts_at,
                "submission_ends_at": submission_ends_at,
            }.items()
        }
        try:
            await self.event_service.create_event(
                event_key=event_name,
                display_name=event_name,
                event_type=event_type,
                timezone=timezone,
                registration_channel_id=str(interaction.channel_id),
                topics=parsed_topics,
                matching_policy="rules_2026" if event_type == EventType.CHRISTMAS.value else None,
                **values,
            )
            return await self.event_service.activate_event(event_name)
        except (OSError, ValueError) as exc:
            raise EventServiceError("活動設定無效或無法儲存") from exc

    @app_commands.command(name="seteventname", description="啟用並設定唯一活動")
    @app_commands.describe(
        event_name="活動代碼（也會作為公開顯示名稱）",
        event_type="submission 或 christmas",
        timezone="IANA 時區，例如 Asia/Taipei",
        registration_starts_at="報名開始（ISO 時間或 yyyymmdd-HHMM）",
        registration_ends_at="報名截止（ISO 時間或 yyyymmdd-HHMM）",
        submission_starts_at="投稿開始（ISO 時間或 yyyymmdd-HHMM）",
        submission_ends_at="投稿截止（ISO 時間或 yyyymmdd-HHMM）",
        topics="題目名稱，用逗號分隔",
    )
    @app_commands.choices(
        event_type=[
            app_commands.Choice(name="submission", value="submission"),
            app_commands.Choice(name="christmas", value="christmas"),
        ]
    )
    async def set_event_name(
        self,
        interaction: discord.Interaction,
        event_name: str,
        event_type: str,
        timezone: str,
        registration_starts_at: str,
        registration_ends_at: str,
        submission_starts_at: str,
        submission_ends_at: str,
        topics: str,
    ):
        if not self._is_admin(interaction):
            await self._error(interaction, "只有管理員可以設定活動。")
            return
        try:
            event = await self.activate_event(
                interaction,
                event_name,
                event_type=event_type,
                timezone=timezone,
                registration_starts_at=registration_starts_at,
                registration_ends_at=registration_ends_at,
                submission_starts_at=submission_starts_at,
                submission_ends_at=submission_ends_at,
                topics=topics,
            )
        except (EventServiceError, ValueError) as exc:
            await self._error(interaction, self._user_error(exc))
        except Exception as exc:
            await self._unexpected_error(interaction, "seteventname", exc)
            return
        await self._send(interaction, f"已啟用活動 `{event.public.event_key}`。")

    @app_commands.command(name="event", description="報名或退出活動")
    @app_commands.choices(
        action=[
            app_commands.Choice(name="join", value="join"),
            app_commands.Choice(name="leave", value="leave"),
        ]
    )
    async def event(self, interaction: discord.Interaction, action: str):
        if not interaction.guild or not self.bIsAAFanclub(interaction):
            await self._error(interaction, "此指令只能在指定伺服器使用。")
            return
        try:
            active = await self.event_service.load_active()
            if str(interaction.channel_id) != active.private.registration_channel_id:
                raise EventServiceError(f"請在 <#{active.private.registration_channel_id}> 使用。")
            await interaction.response.defer(thinking=True)
            if action == "join":
                participant = await self.event_service.join(str(interaction.user.id), interaction.user.name)
                # The participant key is private mapping data and must never
                # be exposed in a public channel.
                await self._send(interaction, "報名成功。", ephemeral=True)
            elif action == "leave":
                await self.event_service.leave(str(interaction.user.id))
                await self._send(interaction, "已退出活動。")
            else:
                raise EventServiceError("請選擇 join 或 leave。")
        except (EventServiceError, OSError, ValueError) as exc:
            await self._error(interaction, self._user_error(exc))
        except Exception as exc:
            await self._unexpected_error(interaction, "event", exc)

    async def _topic_autocomplete(self, interaction: discord.Interaction, current: str):
        try:
            active = await self.event_service.load_active()
        except (OSError, ValueError):
            return []
        value = (current or "").lower()
        return [
            app_commands.Choice(name=topic.name[:100], value=topic.key)
            for topic in active.public.topics
            if not value or value in topic.name.lower() or value in topic.key.lower()
        ][:25]

    @app_commands.command(name="upload", description="上傳並覆蓋指定題目的作品")
    @app_commands.describe(file="壓縮檔 (.zip/.rar/.7z)", title="作品標題", topic="題目（單題活動可留空）")
    @app_commands.autocomplete(topic=_topic_autocomplete)
    async def upload(
        self,
        interaction: discord.Interaction,
        file: discord.Attachment,
        title: str,
        topic: Optional[str] = None,
    ):
        Path("uploads").mkdir(parents=True, exist_ok=True)
        if file.size and file.size > 100 * 1024 * 1024:
            await self._error(interaction, "檔案超過 100 MB。")
            return
        await interaction.response.defer(thinking=True)
        suffix = Path(file.filename).suffix.lower()
        descriptor, temporary_name = tempfile.mkstemp(
            prefix="event-upload-", suffix=suffix, dir="uploads"
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            await file.save(temporary)
            result = await self.submission_service.upload_archive(
                str(interaction.user.id), temporary, topic=topic, title=title
            )
            await self._send(interaction, f"已完成覆蓋式上傳。預覽：{result.preview_url}")
        except (SubmissionServiceError, EventServiceError, OSError, ValueError) as exc:
            await self._error(interaction, self._user_error(exc))
        except Exception as exc:
            await self._unexpected_error(interaction, "upload", exc)
        finally:
            temporary.unlink(missing_ok=True)

    @app_commands.command(name="clear", description="清除自己的指定題目作品")
    @app_commands.describe(topic="題目（單題活動可留空）")
    @app_commands.autocomplete(topic=_topic_autocomplete)
    async def clear(self, interaction: discord.Interaction, topic: Optional[str] = None):
        await interaction.response.defer(thinking=True)
        try:
            await self.submission_service.clear_submission(str(interaction.user.id), topic=topic)
            await self._send(interaction, "已清除指定題目作品。")
        except (SubmissionServiceError, EventServiceError, OSError, ValueError) as exc:
            await self._error(interaction, self._user_error(exc))
        except Exception as exc:
            await self._unexpected_error(interaction, "clear", exc)

    @app_commands.command(name="anonsay", description="匿名發言")
    @app_commands.describe(content="內容")
    async def anon_say(self, interaction: discord.Interaction, content: str):
        try:
            await interaction.response.defer(ephemeral=True)
            record = await self.christmas_service.say(
                str(interaction.user.id), content, channel_id=str(interaction.channel_id)
            )
            sent = await interaction.channel.send(record["content"])
            await self.christmas_service.bind_discord_message(record["message_id"], str(sent.id))
            await self._send(interaction, "已匿名發言。", ephemeral=True)
        except (ChristmasServiceError, OSError, ValueError) as exc:
            await self._error(interaction, self._user_error(exc))
        except Exception as exc:
            await self._unexpected_error(interaction, "anonsay", exc)

    @app_commands.command(name="anonreply", description="匿名回覆")
    @app_commands.describe(message_id="訊息 ID 或系統匿名訊息 ID", content="回覆內容")
    async def anon_reply(self, interaction: discord.Interaction, message_id: str, content: str):
        try:
            await interaction.response.defer(ephemeral=True)
            matches = re.findall(r"\d{15,20}", message_id)
            lookup_id = matches[-1] if matches else message_id
            record = await self.christmas_service.reply(str(interaction.user.id), lookup_id, content)
            target_id = record.get("reply_to_discord_message_id")
            if target_id:
                target = await interaction.channel.fetch_message(int(target_id))
                await target.reply(record["content"], mention_author=False)
            else:
                # Internal IDs are useful in tests and for clients that do not
                # expose Discord links; public replies remain authorless.
                await interaction.channel.send(record["content"])
            await self._send(interaction, "已匿名回覆。", ephemeral=True)
        except (ChristmasServiceError, OSError, ValueError) as exc:
            await self._error(interaction, self._user_error(exc))
        except Exception as exc:
            await self._unexpected_error(interaction, "anonreply", exc)

    @app_commands.command(name="blacklist", description="設定黑名單（完整覆蓋）")
    @app_commands.describe(ids="要封鎖的 Discord ID，以空白分隔；留空可清除")
    async def blacklist(self, interaction: discord.Interaction, ids: str = ""):
        try:
            await interaction.response.defer(ephemeral=True)
            await self.christmas_service.set_blacklist(
                str(interaction.user.id), [value for value in ids.split() if value]
            )
            await self._send(interaction, "已設定黑名單。", ephemeral=True)
        except (ChristmasServiceError, OSError, ValueError) as exc:
            await self._error(interaction, self._user_error(exc))
        except Exception as exc:
            await self._unexpected_error(interaction, "blacklist", exc)

    @app_commands.command(name="giftshuffle", description="依活動規則產生送禮配對")
    async def gift_shuffle(self, interaction: discord.Interaction):
        if not self._is_admin(interaction):
            await self._error(interaction, "需要管理員權限。")
            return
        try:
            await interaction.response.defer(ephemeral=True)
            await self.christmas_service.gift_shuffle()
            await self._send(interaction, "已產生配對（隱藏）。", ephemeral=True)
        except (ChristmasServiceError, OSError, ValueError) as exc:
            await self._error(interaction, self._user_error(exc))
        except Exception as exc:
            await self._unexpected_error(interaction, "giftshuffle", exc)

    @app_commands.command(name="giftme", description="查看活動允許公開的配對結果")
    async def gift_me(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            assignments = await self.christmas_service.gift_for(str(interaction.user.id))
            if not assignments:
                raise ChristmasServiceError("找不到你的配對資料。")
            lines = []
            for item in assignments:
                if item.get("giver_id") == str(interaction.user.id):
                    lines.append(f"你要送給：<@{item.get('receiver_id')}>")
                if item.get("receiver_id") == str(interaction.user.id):
                    lines.append(f"送給你的人：<@{item.get('giver_id')}>")
            await self._send(interaction, "\n".join(lines), ephemeral=True)
        except (ChristmasServiceError, OSError, ValueError) as exc:
            await self._error(interaction, self._user_error(exc))
        except Exception as exc:
            await self._unexpected_error(interaction, "giftme", exc)


async def setup(bot):
    await bot.add_cog(EventCog(bot))
