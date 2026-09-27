"""The single Discord Cog for both submission and Christmas events."""

from __future__ import annotations

import asyncio
import io
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
from .avatar_service import AvatarService, AvatarServiceError
from .event_service import EventService, EventServiceError
from .models import EventType
from .repositories import EventRepository
from .submission_service import SubmissionService, SubmissionServiceError

logger = logging.getLogger(__name__)


class EventCog(Cog_extension):
    guess_group = app_commands.Group(
        name="guess",
        description="私訊提交、查看 Christmas 作者猜測",
    )
    group_group = app_commands.Group(
        name="group",
        description="私訊查看活動配對或分組結果",
    )
    sudo_group = app_commands.Group(
        name="sudo",
        description="目前活動主辦者工具",
    )
    blacklist_group = app_commands.Group(
        name="blacklist",
        description="管理 Christmas 活動黑名單（請在私訊使用）",
    )
    christmas_group = app_commands.Group(
        name="christmas",
        description="Christmas 活動指令",
    )

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
        self.avatar_service = AvatarService(self.event_service)

    async def _send(self, interaction: discord.Interaction, content: str, *, ephemeral: bool = False):
        if interaction.response.is_done():
            return await interaction.followup.send(content, ephemeral=ephemeral)
        return await interaction.response.send_message(content, ephemeral=ephemeral)

    async def _error(self, interaction: discord.Interaction, content: str):
        await self._send(interaction, content, ephemeral=interaction.guild is not None)

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

    async def _is_event_host(self, interaction: discord.Interaction) -> bool:
        try:
            event = await self.event_service.load_active()
        except (OSError, ValueError, EventServiceError):
            return False
        return str(interaction.user.id) in event.private.host_user_ids

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
        event_type="submission、christmas 或 group",
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
            app_commands.Choice(name="group", value="group"),
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

    @app_commands.command(name="seteventadmins", description="更新目前活動主辦人權限名單")
    @app_commands.describe(user_ids="主辦者 Discord ID 或提及，空白或逗號分隔；留空可清空")
    async def set_event_admins(self, interaction: discord.Interaction, user_ids: str = ""):
        if not self._is_admin(interaction):
            await self._error(interaction, "只有 Bot 管理員可以更新活動主辦人名單。")
            return
        parsed = list(dict.fromkeys(re.findall(r"\d{15,20}", user_ids)))
        if user_ids.strip() and not parsed:
            await self._error(interaction, "找不到有效的 Discord 使用者 ID。")
            return
        try:
            await self.event_service.set_event_hosts(parsed)
            await self._send(interaction, f"已更新主辦人名單，共 {len(parsed)} 人。")
        except (EventServiceError, OSError, ValueError) as exc:
            await self._error(interaction, self._user_error(exc))
        except Exception as exc:
            await self._unexpected_error(interaction, "seteventadmins", exc)

    @app_commands.command(name="seteventchannels", description="設定活動雜談區")
    @app_commands.describe(discussion_channel="活動雜談與狀態更新要發送的頻道")
    async def set_event_channels(
        self, interaction: discord.Interaction, discussion_channel: discord.TextChannel
    ):
        if not await self._is_event_host(interaction):
            await self._error(interaction, "只有目前活動的主辦人可以設定活動頻道。")
            return
        try:
            await self.event_service.set_discussion_channel(str(discussion_channel.id))
            await self._send(interaction, f"活動雜談區已設定為 {discussion_channel.mention}。")
        except (EventServiceError, OSError, ValueError) as exc:
            await self._error(interaction, self._user_error(exc))
        except Exception as exc:
            await self._unexpected_error(interaction, "seteventchannels", exc)

    @app_commands.command(name="setblacklistsettings", description="設定目前活動的黑名單截止時間與人數上限")
    @app_commands.describe(
        ends_at="黑名單截止時間（ISO datetime 或 yyyymmdd-HHMM）",
        max_entries="每人可封鎖的參加者數量上限",
        max_leaders="組活中可封鎖的組長數量上限（選填）",
    )
    async def set_blacklist_settings(
        self,
        interaction: discord.Interaction,
        ends_at: str,
        max_entries: int,
        max_leaders: Optional[int] = None,
    ):
        if not await self._is_event_host(interaction):
            await self._error(interaction, "只有目前活動的主辦人可以設定黑名單規則。")
            return
        try:
            event = await self.event_service.load_active()
            deadline = self._parse_datetime(ends_at, event.public.timezone)
            await self.event_service.set_blacklist_settings(
                ends_at=deadline,
                max_entries=max_entries,
                max_leaders=max_leaders,
            )
            leader_note = (
                f"組長上限 {max_leaders} 人；" if max_leaders is not None else ""
            )
            await self._send(
                interaction,
                f"已設定黑名單截止時間 {deadline.isoformat()}、每人上限 {max_entries} 人，{leader_note}可開始使用。",
            )
        except (EventServiceError, OSError, ValueError) as exc:
            await self._error(interaction, self._user_error(exc))
        except Exception as exc:
            await self._unexpected_error(interaction, "setblacklistsettings", exc)

    @app_commands.command(name="event", description="報名、修改、退出或恢復活動報名")
    @app_commands.choices(
        action=[
            app_commands.Choice(name="join", value="join"),
            app_commands.Choice(name="edit", value="edit"),
            app_commands.Choice(name="leave", value="leave"),
            app_commands.Choice(name="restore", value="restore"),
        ]
    )
    async def event(self, interaction: discord.Interaction, action: str):
        await self._signup_action(interaction, action)

    @app_commands.command(name="signup", description="報名、修改、退出或恢復活動報名")
    @app_commands.choices(
        action=[
            app_commands.Choice(name="join", value="join"),
            app_commands.Choice(name="edit", value="edit"),
            app_commands.Choice(name="quit", value="quit"),
            app_commands.Choice(name="restore", value="restore"),
        ]
    )
    async def signup(self, interaction: discord.Interaction, action: str):
        await self._signup_action(interaction, action)

    async def _signup_action(self, interaction: discord.Interaction, action: str):
        if not interaction.guild or not self.bIsAAFanclub(interaction):
            await self._error(interaction, "此指令只能在指定伺服器使用。")
            return
        try:
            if action in {"join", "edit"}:
                active = await self.event_service.load_active()
                existing = await self.event_service.participant(str(interaction.user.id))
                if action == "join" and existing:
                    raise EventServiceError("你已經報名；請使用 `/signup action:edit` 修改資料。")
                if action == "edit" and existing is None:
                    raise EventServiceError("找不到有效的報名資料，請先報名。")
                await interaction.response.send_modal(
                    SignupModal(self, active.public.event_type, existing)
                )
                return
            await interaction.response.defer(thinking=True)
            if action in {"leave", "quit"}:
                participant = await self.event_service.leave(str(interaction.user.id))
                await self._publish_signup_record(participant)
                await self._post_registration_status(participant, "取消了報名")
                synced = await self._sync_participant_index(participant)
                message = f"編號 {participant.registration_number} 已取消報名；恢復時會保留原編號。"
                if not synced:
                    message += "公開名單同步失敗，請通知管理員。"
                await self._send(interaction, message, ephemeral=True)
            elif action == "restore":
                participant = await self.event_service.restore(str(interaction.user.id))
                await self._publish_signup_record(participant)
                await self._post_registration_status(participant, "恢復了報名")
                synced = await self._sync_participant_index(participant)
                message = f"已恢復報名，沿用編號 {participant.registration_number}。"
                if not synced:
                    message += "公開名單同步失敗，請通知管理員。"
                await self._send(interaction, message, ephemeral=True)
            else:
                raise EventServiceError("請選擇 join、edit、quit 或 restore。")
        except (EventServiceError, OSError, ValueError) as exc:
            await self._error(interaction, self._user_error(exc))
        except Exception as exc:
            await self._unexpected_error(interaction, "event", exc)

    async def _publish_participant_avatar(self, participant, user) -> None:
        await self.avatar_service.sync_participant(participant.discord_user_id, user.display_avatar)
        await self._publish_participant_index(
            participant, f"Update participant avatar ({participant.registration_number})"
        )

    async def _publish_participant_index(self, participant, message: str) -> None:
        event = await self.event_service.load_active()
        index = self.submission_service.public_index
        snapshot = await asyncio.to_thread(index.sync_participants, event)
        try:
            await self.submission_service.publisher.publish(
                self.repository.public_dir(event.public.event_key),
                message,
            )
        except Exception:
            await asyncio.to_thread(index.restore, snapshot)
            raise

    async def _publish_signup_record(self, participant) -> None:
        event = await self.event_service.load_active()
        channel_id = int(event.private.registration_channel_id)
        channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
        if participant.withdrawn:
            content = (
                f"[{participant.registration_number}]的報名者"
                f"{participant.display_name}取消了報名。"
            )
        else:
            lines = [
            f"[{participant.registration_number}]",
            f"暱稱：{participant.display_name}",
            ]
            if participant.aa_image:
                lines.append(f"AA形象：{participant.aa_image}")
            if participant.team_leader is not None:
                lines.append(f"是否報名組長：{'是' if participant.team_leader else '否'}")
            if participant.notes:
                lines.append(f"備註：{participant.notes}")
            content = "\n".join(lines)
        if participant.signup_message_id and participant.signup_channel_id:
            try:
                previous_channel = (
                    self.bot.get_channel(int(participant.signup_channel_id))
                    or await self.bot.fetch_channel(int(participant.signup_channel_id))
                )
                previous = await previous_channel.fetch_message(int(participant.signup_message_id))
                await previous.edit(content=content, allowed_mentions=discord.AllowedMentions.none())
                return
            except discord.NotFound:
                logger.info(
                    "Signup message %s is missing; posting a replacement",
                    participant.signup_message_id,
                )
        sent = await channel.send(
            content,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        await self.event_service.set_signup_message(
            participant.discord_user_id, str(channel.id), str(sent.id)
        )

    async def _post_registration_status(self, participant, status: str) -> None:
        event = await self.event_service.load_active()
        channel_id = event.private.discussion_channel_id
        if not channel_id:
            raise EventServiceError("尚未設定活動雜談區，請通知管理員。")
        channel = self.bot.get_channel(int(channel_id)) or await self.bot.fetch_channel(int(channel_id))
        await channel.send(
            f"[{participant.registration_number}]的報名者{participant.display_name}{status}。",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    async def _post_overtime_status(self, author_id: str) -> None:
        event = await self.event_service.load_active()
        if not event.private.discussion_channel_id:
            raise EventServiceError("尚未設定活動雜談區。")
        assignments = await self.christmas_service.gift_for(author_id)
        assignment = next(
            (item for item in assignments if item.get("giver_id") == str(author_id)),
            None,
        )
        if assignment is None:
            raise ChristmasServiceError("找不到你的收禮者配對，無法發布超時通知。")
        recipient = next(
            (item for item in event.private.participants
             if item.discord_user_id == str(assignment.get("receiver_id")) and not item.withdrawn),
            None,
        )
        if recipient is None:
            raise ChristmasServiceError("找不到收禮者資料，無法發布超時通知。")
        channel_id = int(event.private.discussion_channel_id)
        channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
        await channel.send(
            f"[{recipient.registration_number}]的作品有了超時更新。",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    async def _sync_participant_index(self, participant) -> bool:
        event = await self.event_service.load_active()
        index = self.submission_service.public_index
        snapshot = await asyncio.to_thread(index.sync_participants, event)
        try:
            await self.submission_service.publisher.publish(
                self.repository.public_dir(event.public.event_key),
                f"Update participant status ({participant.registration_number})",
            )
        except Exception:
            await asyncio.to_thread(index.restore, snapshot)
            logger.warning(
                "Could not publish participant status for registration %s",
                participant.registration_number,
                exc_info=True,
            )
            return False
        return True

    @app_commands.command(name="eventsyncicons", description="同步目前活動所有參賽者的 Discord 頭像")
    async def sync_event_icons(self, interaction: discord.Interaction):
        if not await self._is_event_host(interaction):
            await self._error(interaction, "只有目前活動的主辦人可以同步活動頭像。")
            return
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            event = await self.event_service.load_active()
            synced = 0
            failed = []
            for participant in event.private.participants:
                if participant.withdrawn:
                    continue
                try:
                    user = await self.bot.fetch_user(int(participant.discord_user_id))
                    await self.avatar_service.sync_participant(
                        participant.discord_user_id, user.display_avatar
                    )
                    synced += 1
                except Exception:
                    failed.append(participant.display_name or participant.discord_user_id)
                    logger.warning(
                        "Could not sync avatar for participant %s",
                        participant.discord_user_id,
                        exc_info=True,
                    )
            event = await self.event_service.load_active()
            index = self.submission_service.public_index
            snapshot = await asyncio.to_thread(index.sync_participants, event)
            try:
                await self.submission_service.publisher.publish(
                    self.repository.public_dir(event.public.event_key),
                    "Sync event participant avatars",
                )
            except Exception:
                await asyncio.to_thread(index.restore, snapshot)
                raise
            summary = f"已同步 {synced} 位參賽者的頭像。"
            if failed:
                summary += "\n同步失敗：" + "、".join(failed)
            await self._send(interaction, summary, ephemeral=True)
        except Exception as exc:
            await self._unexpected_error(interaction, "eventsyncicons", exc)

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

    @app_commands.command(name="upload", description="上傳並覆蓋指定題目的作品；help 可看說明")
    @app_commands.describe(
        file="壓縮檔 (.zip/.rar/.7z)", title="作品標題",
        topic="題目（單題活動可留空）", help="顯示上傳格式與限制",
    )
    @app_commands.autocomplete(topic=_topic_autocomplete)
    async def upload(
        self,
        interaction: discord.Interaction,
        file: Optional[discord.Attachment] = None,
        title: Optional[str] = None,
        topic: Optional[str] = None,
        help: bool = False,
    ):
        if help:
            await self._send(
                interaction,
                "`/upload`：在投稿期間，上傳 .zip/.rar/.7z 壓縮檔並覆蓋指定題目作品。"
                "需填作品標題；多題活動需選 topic，單題可留空。單檔上限 100 MB。"
                "再次上傳會完整取代該題目前版本。截止後如需補交或更新，使用 `/uploadovertime`；"
                "作品會標記為超時投稿。",
                ephemeral=True,
            )
            return
        if file is None or title is None:
            await self._error(interaction, "請提供壓縮檔與作品標題；也可使用 `/upload help:true` 查看說明。")
            return
        await self._upload_archive(interaction, file, title, topic)

    @app_commands.command(name="uploadovertime", description="投稿截止後上傳或更新作品（標記超時）")
    @app_commands.describe(file="壓縮檔 (.zip/.rar/.7z)", title="作品標題", topic="題目（單題活動可留空）")
    @app_commands.autocomplete(topic=_topic_autocomplete)
    async def upload_overtime(
        self,
        interaction: discord.Interaction,
        file: discord.Attachment,
        title: str,
        topic: Optional[str] = None,
    ):
        await self._upload_archive(interaction, file, title, topic, overtime=True)

    async def _upload_archive(
        self,
        interaction: discord.Interaction,
        file: discord.Attachment,
        title: str,
        topic: Optional[str],
        *,
        overtime: bool = False,
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
                str(interaction.user.id), temporary, topic=topic, title=title,
                overtime=overtime,
            )
            message = (
                f"已完成{'超時' if result.overtime else ''}覆蓋式上傳。預覽：{result.preview_url}"
            )
            if overtime:
                event = await self.event_service.load_active()
                if event.public.event_type is EventType.CHRISTMAS:
                    try:
                        await self._post_overtime_status(str(interaction.user.id))
                    except Exception:
                        logger.warning("Could not post overtime submission status", exc_info=True)
                        message += "\n作品已上傳，但活動雜談區狀態通知失敗，請通知主辦者。"
            await self._send(interaction, message)
        except (SubmissionServiceError, EventServiceError, OSError, ValueError) as exc:
            await self._error(interaction, self._user_error(exc))
        except Exception as exc:
            await self._unexpected_error(interaction, "uploadovertime" if overtime else "upload", exc)
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

    @christmas_group.command(name="anonsay", description="匿名發言")
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

    @christmas_group.command(name="anonreply", description="匿名回覆")
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

    @christmas_group.command(name="blacklist", description="設定黑名單（完整覆蓋）")
    @app_commands.describe(ids="要封鎖的 Discord ID，以空白分隔；留空可清除")
    async def blacklist(self, interaction: discord.Interaction, ids: str = ""):
        await self._error(
            interaction,
            "此舊指令已停用。請私訊機器人使用 `/blacklist add`、`/blacklist view` 或 `/blacklist remove`。",
        )

    async def _require_blacklist_dm(self, interaction: discord.Interaction) -> bool:
        if interaction.guild is not None:
            await self._error(interaction, "請私訊機器人使用 `/blacklist`。")
            return False
        return True

    @blacklist_group.command(name="add", description="將報名編號加入你的黑名單")
    @app_commands.describe(registration_number="要加入黑名單的報名編號")
    async def blacklist_add(
        self, interaction: discord.Interaction, registration_number: int
    ):
        if not await self._require_blacklist_dm(interaction):
            return
        try:
            await self.christmas_service.blacklist_add(
                str(interaction.user.id), registration_number
            )
            await self._send(interaction, f"已將編號 {registration_number} 加入黑名單。")
        except (ChristmasServiceError, OSError, ValueError) as exc:
            await self._error(interaction, self._user_error(exc))
        except Exception as exc:
            await self._unexpected_error(interaction, "blacklist add", exc)

    @blacklist_group.command(name="view", description="查看你的黑名單")
    async def blacklist_view(self, interaction: discord.Interaction):
        if not await self._require_blacklist_dm(interaction):
            return
        try:
            entries = await self.christmas_service.blacklist_view(str(interaction.user.id))
            if not entries:
                content = "你的黑名單目前是空的。"
            else:
                content = "你的黑名單：\n" + "\n".join(
                    f"[{entry['registration_number']}] {entry['display_name']}"
                    for entry in entries
                )
            await self._send(interaction, content)
        except (ChristmasServiceError, OSError, ValueError) as exc:
            await self._error(interaction, self._user_error(exc))
        except Exception as exc:
            await self._unexpected_error(interaction, "blacklist view", exc)

    @blacklist_group.command(name="remove", description="將報名編號從你的黑名單移除")
    @app_commands.describe(registration_number="要移除的報名編號")
    async def blacklist_remove(
        self, interaction: discord.Interaction, registration_number: int
    ):
        if not await self._require_blacklist_dm(interaction):
            return
        try:
            await self.christmas_service.blacklist_remove(
                str(interaction.user.id), registration_number
            )
            await self._send(interaction, f"已將編號 {registration_number} 從黑名單移除。")
        except (ChristmasServiceError, OSError, ValueError) as exc:
            await self._error(interaction, self._user_error(exc))
        except Exception as exc:
            await self._unexpected_error(interaction, "blacklist remove", exc)

    async def _defer_sudo(self, interaction: discord.Interaction) -> bool:
        if not await self._is_event_host(interaction):
            await self._error(interaction, "只有目前活動的主辦人可以使用此指令。")
            return False
        await interaction.response.defer(thinking=True, ephemeral=True)
        return True

    @sudo_group.command(name="viewblacklist", description="查看目前所有人的黑名單")
    async def sudo_viewblacklist(self, interaction: discord.Interaction):
        if not await self._defer_sudo(interaction):
            return
        try:
            rows = await self.christmas_service.sudo_view_blacklist()
            if not rows:
                await self._send(interaction, "目前沒有人設定黑名單。", ephemeral=True)
                return
            lines = [
                f"[{row['owner_number'] or '?'}] {row['owner_name']} → "
                f"[{row['target_number'] or '?'}] {row['target_name']}"
                for row in rows
            ]
            page = ""
            for line in lines:
                if len(page) + len(line) + 1 > 1800:
                    await self._send(interaction, page, ephemeral=True)
                    page = ""
                page += line + "\n"
            if page:
                await self._send(interaction, page, ephemeral=True)
        except (ChristmasServiceError, OSError, ValueError) as exc:
            await self._error(interaction, self._user_error(exc))
        except Exception as exc:
            await self._unexpected_error(interaction, "sudo viewblacklist", exc)

    @sudo_group.command(name="addblacklist", description="手動加入黑名單（可覆蓋一般上限）")
    @app_commands.describe(owner_number="黑名單持有者編號", target_number="被封鎖者編號")
    async def sudo_addblacklist(
        self, interaction: discord.Interaction, owner_number: int, target_number: int
    ):
        if not await self._defer_sudo(interaction):
            return
        try:
            await self.christmas_service.sudo_change_blacklist(
                owner_number, target_number, add=True
            )
            await self._send(interaction, "已手動加入黑名單。", ephemeral=True)
        except (ChristmasServiceError, OSError, ValueError) as exc:
            await self._error(interaction, self._user_error(exc))
        except Exception as exc:
            await self._unexpected_error(interaction, "sudo addblacklist", exc)

    @sudo_group.command(name="removeblacklist", description="手動移除黑名單項目")
    @app_commands.describe(owner_number="黑名單持有者編號（0 表示所有人）", target_number="被封鎖者編號（0 表示該持有者全部）")
    async def sudo_removeblacklist(
        self, interaction: discord.Interaction, owner_number: int, target_number: int
    ):
        if not await self._defer_sudo(interaction):
            return
        try:
            await self.christmas_service.sudo_change_blacklist(
                owner_number, target_number, add=False
            )
            await self._send(interaction, "已手動移除黑名單項目。", ephemeral=True)
        except (ChristmasServiceError, OSError, ValueError) as exc:
            await self._error(interaction, self._user_error(exc))
        except Exception as exc:
            await self._unexpected_error(interaction, "sudo removeblacklist", exc)

    @sudo_group.command(name="kick", description="取消指定編號的報名")
    @app_commands.describe(registration_number="要取消報名的編號")
    async def sudo_kick(self, interaction: discord.Interaction, registration_number: int):
        if not await self._defer_sudo(interaction):
            return
        try:
            participant = await self.event_service.participant_by_number(registration_number)
            if participant is None:
                raise EventServiceError("找不到有效的報名編號。")
            participant = await self.event_service.leave(participant.discord_user_id)
            await self._publish_signup_record(participant)
            await self._post_registration_status(participant, "取消了報名")
            synced = await self._sync_participant_index(participant)
            note = "" if synced else "公開名單同步失敗，請通知管理員。"
            await self._send(interaction, f"已取消編號 {registration_number} 的報名。{note}", ephemeral=True)
        except (ChristmasServiceError, EventServiceError, OSError, ValueError) as exc:
            await self._error(interaction, self._user_error(exc))
        except Exception as exc:
            await self._unexpected_error(interaction, "sudo kick", exc)

    @sudo_group.command(name="revertkick", description="恢復 kick 取消的報名")
    @app_commands.describe(registration_number="要恢復報名的編號")
    async def sudo_revertkick(self, interaction: discord.Interaction, registration_number: int):
        if not await self._defer_sudo(interaction):
            return
        try:
            participant = await self.event_service.participant_by_number(
                registration_number, include_withdrawn=True
            )
            if participant is None:
                raise EventServiceError("找不到這個報名編號。")
            participant = await self.event_service.restore(participant.discord_user_id)
            await self._publish_signup_record(participant)
            await self._post_registration_status(participant, "恢復了報名")
            synced = await self._sync_participant_index(participant)
            note = "" if synced else "公開名單同步失敗，請通知管理員。"
            await self._send(interaction, f"已恢復編號 {registration_number} 的報名。{note}", ephemeral=True)
        except (ChristmasServiceError, EventServiceError, OSError, ValueError) as exc:
            await self._error(interaction, self._user_error(exc))
        except Exception as exc:
            await self._unexpected_error(interaction, "sudo revertkick", exc)

    @sudo_group.command(name="submitcount", description="在目前頻道公布已提交作品數量")
    async def sudo_submitcount(self, interaction: discord.Interaction):
        if not await self._is_event_host(interaction):
            await self._error(interaction, "只有目前活動的主辦人可以公布投稿數量。")
            return
        await interaction.response.defer(thinking=True)
        try:
            counts = await self.submission_service.count_submissions()
            details = [
                f"{name}：{count}"
                for name, count in counts.items()
                if name not in {"total", "expected"}
            ]
            content = (
                f"目前已提交 {counts['total']} 件作品，"
                f"共 {counts['expected']} 個投稿名額。"
            )
            if len(details) > 1:
                content += "\n" + "\n".join(details)
            await self._send(interaction, content)
        except (SubmissionServiceError, EventServiceError, OSError, ValueError) as exc:
            await self._error(interaction, self._user_error(exc))
        except Exception as exc:
            await self._unexpected_error(interaction, "sudo submitcount", exc)

    @christmas_group.command(name="giftshuffle", description="依活動規則產生送禮配對")
    async def gift_shuffle(self, interaction: discord.Interaction):
        if not await self._is_event_host(interaction):
            await self._error(interaction, "只有目前活動的主辦人可以執行配對。")
            return
        try:
            await interaction.response.defer(ephemeral=True)
            await self.christmas_service.gift_shuffle()
            await self._send(interaction, "已產生配對（隱藏）。", ephemeral=True)
        except (ChristmasServiceError, OSError, ValueError) as exc:
            await self._error(interaction, self._user_error(exc))
        except Exception as exc:
            await self._unexpected_error(interaction, "giftshuffle", exc)

    @christmas_group.command(name="finalize", description="鎖定猜測並產生結算 CSV")
    async def finalize_christmas(self, interaction: discord.Interaction):
        if not await self._is_event_host(interaction):
            await self._error(interaction, "只有目前活動的主辦人可以結算猜測。")
            return
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            names: dict[str, str] = {}
            for user_id in await self.christmas_service.guess_owner_ids():
                if await self.event_service.participant(user_id):
                    continue
                user = self.bot.get_user(int(user_id))
                if user is None:
                    try:
                        user = await self.bot.fetch_user(int(user_id))
                    except discord.HTTPException:
                        continue
                names[user_id] = getattr(user, "global_name", None) or user.name
            result = await self.christmas_service.finalize_guesses(names)
            file = discord.File(
                io.BytesIO(result["csv"].encode("utf-8-sig")),
                filename="christmas-guess-scores.csv",
            )
            await interaction.followup.send(
                f"猜測已鎖定，結算完成，共 {len(result['rows'])} 位猜測者。",
                file=file,
                ephemeral=True,
            )
        except (ChristmasServiceError, EventServiceError, OSError, ValueError) as exc:
            await self._error(interaction, self._user_error(exc))
        except Exception as exc:
            await self._unexpected_error(interaction, "christmas finalize", exc)

    @christmas_group.command(name="giftme", description="查看活動允許公開的配對結果")
    async def gift_me(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            recipient = await self.christmas_service.gift_recipient_for(
                str(interaction.user.id)
            )
            await self._send(
                interaction,
                f"你的收禮者是 [{recipient.registration_number}]{recipient.display_name}。",
                ephemeral=True,
            )
        except (ChristmasServiceError, OSError, ValueError) as exc:
            await self._error(interaction, self._user_error(exc))
        except Exception as exc:
            await self._unexpected_error(interaction, "giftme", exc)

    async def _require_group_dm(self, interaction: discord.Interaction) -> bool:
        if interaction.guild is not None:
            await self._error(interaction, "請私訊機器人使用 `/group` 查看配對結果。")
            return False
        return True

    @group_group.command(name="view", description="查看自己的 Christmas 收禮者報名資料")
    async def group_view(self, interaction: discord.Interaction):
        if not await self._require_group_dm(interaction):
            return
        await interaction.response.defer(thinking=True)
        try:
            recipient = await self.christmas_service.gift_recipient_for(
                str(interaction.user.id)
            )
            content = "\n".join(
                [
                    f"[{recipient.registration_number}]",
                    f"暱稱：{recipient.display_name}",
                    *([f"AA形象：{recipient.aa_image}"] if recipient.aa_image else []),
                    *([f"是否報名組長：{'是' if recipient.team_leader else '否'}"]
                      if recipient.team_leader is not None else []),
                    *([f"備註：{recipient.notes}"] if recipient.notes else []),
                ]
            )
            if recipient.signup_channel_id and recipient.signup_message_id:
                channel = (
                    self.bot.get_channel(int(recipient.signup_channel_id))
                    or await self.bot.fetch_channel(int(recipient.signup_channel_id))
                )
                message = await channel.fetch_message(int(recipient.signup_message_id))
                content = message.content
            await self._send(
                interaction,
                f"你的收禮者報名表：\n{content}",
            )
        except (ChristmasServiceError, EventServiceError, OSError, ValueError) as exc:
            await self._error(interaction, self._user_error(exc))
        except Exception as exc:
            await self._unexpected_error(interaction, "group view", exc)

    @group_group.command(name="viewall", description="查看所有 Christmas 配對（截止鎖定前）")
    async def group_viewall(self, interaction: discord.Interaction):
        if not await self._require_group_dm(interaction):
            return
        await interaction.response.defer(thinking=True)
        try:
            if await self.christmas_service.matching_locked():
                raise ChristmasServiceError("報名表已鎖定，不能查看完整配對名單。")
            event = await self.event_service.load_active()
            participants = {item.discord_user_id: item for item in event.private.participants}
            assignments = await self.christmas_service.all_gift_assignments()
            lines = ["完整配對名單："]
            for item in assignments:
                giver = participants.get(str(item.get("giver_id")))
                receiver = participants.get(str(item.get("receiver_id")))
                if giver and receiver:
                    lines.append(
                        f"[{giver.registration_number}]{giver.display_name} → "
                        f"[{receiver.registration_number}]{receiver.display_name}"
                    )
            page = ""
            for line in lines:
                if len(page) + len(line) + 1 > 1800:
                    await self._send(interaction, page)
                    page = ""
                page += line + "\n"
            if page:
                await self._send(interaction, page)
        except (ChristmasServiceError, EventServiceError, OSError, ValueError) as exc:
            await self._error(interaction, self._user_error(exc))
        except Exception as exc:
            await self._unexpected_error(interaction, "group viewall", exc)

    @group_group.command(name="downloadall", description="下載已結算的所有猜測與計分 CSV")
    async def group_downloadall(self, interaction: discord.Interaction):
        if not await self._require_group_dm(interaction):
            return
        await interaction.response.defer(thinking=True)
        try:
            content = await self.christmas_service.finalized_guess_csv()
            await interaction.followup.send(
                "活動猜測與計分表：",
                file=discord.File(
                    io.BytesIO(content.encode("utf-8-sig")),
                    filename="christmas-guess-scores.csv",
                ),
            )
        except (ChristmasServiceError, OSError, ValueError) as exc:
            await self._error(interaction, self._user_error(exc))
        except Exception as exc:
            await self._unexpected_error(interaction, "group downloadall", exc)

    async def _require_guess_dm(self, interaction: discord.Interaction) -> bool:
        if interaction.guild is not None:
            await self._error(interaction, "猜作者指令請私訊機器人使用。")
            return False
        return True

    @staticmethod
    def _guess_line(entry) -> str:
        recipient = entry["recipient"]
        author = entry["author"]
        guessed = (
            f"[{author.registration_number}][{author.display_name}]"
            if author else "未猜測"
        )
        return f"[{recipient.registration_number}][{recipient.display_name}]：{guessed}"

    async def _send_dm_lines(self, interaction: discord.Interaction, heading: str, lines: list[str]):
        page = heading + "\n"
        for line in lines:
            if len(page) + len(line) + 1 > 1800:
                await self._send(interaction, page)
                page = ""
            page += line + "\n"
        if page:
            await self._send(interaction, page)

    @guess_group.command(name="set", description="提交或移除一筆作者猜測")
    @app_commands.describe(recipient_number="收禮者編號", author_number="猜測作者編號；0 表示移除猜測")
    async def guess_set(
        self, interaction: discord.Interaction, recipient_number: int, author_number: int
    ):
        if not await self._require_guess_dm(interaction):
            return
        await interaction.response.defer(thinking=True)
        try:
            change = await self.christmas_service.set_guess(
                str(interaction.user.id), recipient_number, author_number
            )
            if change:
                await self._sync_second_guess(change)
            result = (
                f"已移除對編號 {recipient_number} 作品的猜測。"
                if author_number == 0
                else f"已更新對編號 {recipient_number} 作品的猜測。"
            )
            await self._send(interaction, result)
        except (ChristmasServiceError, OSError, ValueError) as exc:
            await self._error(interaction, self._user_error(exc))
        except Exception as exc:
            await self._unexpected_error(interaction, "guess set", exc)

    @guess_group.command(name="viewall", description="查看自己的所有作者猜測")
    async def guess_viewall(self, interaction: discord.Interaction):
        if not await self._require_guess_dm(interaction):
            return
        await interaction.response.defer(thinking=True)
        try:
            entries = await self.christmas_service.guesses_for(str(interaction.user.id))
            await self._send_dm_lines(
                interaction, "你的所有猜測：", [self._guess_line(item) for item in entries]
            )
        except (ChristmasServiceError, OSError, ValueError) as exc:
            await self._error(interaction, self._user_error(exc))
        except Exception as exc:
            await self._unexpected_error(interaction, "guess viewall", exc)

    @guess_group.command(name="seeinvalid", description="查看未猜測、猜自己或重複作者的項目")
    async def guess_seeinvalid(self, interaction: discord.Interaction):
        if not await self._require_guess_dm(interaction):
            return
        await interaction.response.defer(thinking=True)
        try:
            entries = await self.christmas_service.invalid_guesses_for(
                str(interaction.user.id)
            )
            lines = [self._guess_line(item) for item in entries]
            await self._send_dm_lines(interaction, "你的未完成猜測：", lines or ["沒有未完成猜測。"])
        except (ChristmasServiceError, OSError, ValueError) as exc:
            await self._error(interaction, self._user_error(exc))
        except Exception as exc:
            await self._unexpected_error(interaction, "guess seeinvalid", exc)

    @guess_group.command(name="seesecond", description="查看所有作品或指定作品的第二多猜測")
    @app_commands.describe(recipient_number="收禮者編號（留空查看全部）")
    async def guess_seesecond(
        self, interaction: discord.Interaction, recipient_number: Optional[int] = None
    ):
        if not await self._require_guess_dm(interaction):
            return
        await interaction.response.defer(thinking=True)
        try:
            entries = await self.christmas_service.second_guesses(recipient_number)
            lines = []
            for entry in entries:
                recipient, author = entry["recipient"], entry["author"]
                guessed = (
                    f"[{author.registration_number}][{author.display_name}]"
                    if author else "無"
                )
                lines.append(
                    f"[{recipient.registration_number}][{recipient.display_name}]：{guessed}"
                )
            heading = (
                "所有第二高猜測：" if recipient_number is None
                else f"[{recipient_number}]的第二高猜測："
            )
            await self._send_dm_lines(interaction, heading, lines)
        except (ChristmasServiceError, OSError, ValueError) as exc:
            await self._error(interaction, self._user_error(exc))
        except Exception as exc:
            await self._unexpected_error(interaction, "guess seesecond", exc)

    async def _sync_second_guess(self, change: dict) -> None:
        recipient = change["recipient"]
        def label(participant):
            return (
                f"[{participant.registration_number}][{participant.display_name}]"
                if participant else "無"
            )
        replacement = f"第二多猜測：{label(change['new'])}"
        for ref in await self.christmas_service.published_work_messages(
            recipient.registration_number
        ):
            channel = self.bot.get_channel(int(ref["channel_id"])) or await self.bot.fetch_channel(
                int(ref["channel_id"])
            )
            message = await channel.fetch_message(int(ref["message_id"]))
            lines = message.content.splitlines()
            lines = [
                replacement if line.startswith("第二多猜測：") else line
                for line in lines
            ]
            await message.edit(
                content="\n".join(lines),
                allowed_mentions=discord.AllowedMentions.none(),
            )
        event = await self.event_service.load_active()
        if event.private.discussion_channel_id:
            channel_id = int(event.private.discussion_channel_id)
            channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
            await channel.send(
                f"致[{recipient.registration_number}][{recipient.display_name}]的作品的第二高猜測已更新："
                f"{label(change['old'])}->{label(change['new'])}。",
                allowed_mentions=discord.AllowedMentions.none(),
            )

    @christmas_group.command(name="publishworks", description="依收禮者編號公開 Christmas 投稿作品")
    @app_commands.describe(channel="作品連結公開頻道")
    async def publish_christmas_works(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        if not await self._is_event_host(interaction):
            await self._error(interaction, "只有目前活動的主辦人可以公開作品。")
            return
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            event = await self.event_service.load_active()
            if datetime.now(event.private.submission_ends_at.tzinfo) < event.private.submission_ends_at:
                raise ChristmasServiceError("投稿截止後才能公開作品。")
            assignments = await self.christmas_service.all_gift_assignments()
            second_guesses = await self.christmas_service.second_guesses()
            second_by_recipient = {
                item["recipient"].registration_number: item["author"]
                for item in second_guesses
            }
            authors = {
                item.discord_user_id: item for item in event.private.participants
                if not item.withdrawn
            }
            works_path = self.submission_service.public_index._paths(
                event.public.event_key
            )[1]
            works = await asyncio.to_thread(
                self.submission_service.public_index._read_list, works_path
            )
            published = 0
            for assignment in assignments:
                author = authors.get(str(assignment.get("giver_id")))
                recipient = authors.get(str(assignment.get("receiver_id")))
                if author is None or recipient is None:
                    continue
                author_works = sorted(
                    (work for work in works if work.get("hashId") == author.participant_key),
                    key=lambda work: str(work.get("topic", "")),
                )
                if not author_works:
                    await channel.send(
                        f"[{recipient.registration_number}][{recipient.display_name}]被咕了。",
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
                    published += 1
                    continue
                for work in author_works:
                    overtime_label = "（超時投稿）" if work.get("overtime") else ""
                    second = second_by_recipient.get(recipient.registration_number)
                    second_label = (
                        f"[{second.registration_number}][{second.display_name}]"
                        if second else "無"
                    )
                    work_path = self.submission_service.public_index.work_url(
                        author.participant_key,
                        str(work.get("topicKey", "")),
                        str(work.get("file", "index.html")),
                    )
                    url = (
                        f"{self.submission_service.pages_host}/"
                        f"{event.public.event_key}/{work_path}"
                    )
                    content = (
                        "-----\n"
                        f"[{recipient.registration_number}][{str(work.get('title', ''))[:300]}] / "
                        f"致：[{recipient.display_name}]{overtime_label}\n"
                        f"第二多猜測：{second_label}\n"
                        f"{url}\n-----"
                    )
                    sent = await channel.send(
                        content,
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
                    await self.christmas_service.bind_published_work(
                        recipient.registration_number, str(channel.id), str(sent.id)
                    )
                    published += 1
            await self._send(interaction, f"已在 {channel.mention} 公開 {published} 則作品留言。", ephemeral=True)
        except (ChristmasServiceError, EventServiceError, OSError, ValueError) as exc:
            await self._error(interaction, self._user_error(exc))
        except Exception as exc:
            await self._unexpected_error(interaction, "christmas publishworks", exc)


class SignupModal(discord.ui.Modal):
    def __init__(self, cog: EventCog, event_type: EventType, participant=None) -> None:
        self.cog = cog
        self.event_type = event_type
        self.participant = participant
        super().__init__(
            title="修改活動報名" if participant else "活動報名",
            timeout=300,
        )
        self.nickname = discord.ui.TextInput(
            label="活動暱稱",
            placeholder=("留空表示不修改" if participant else "請填寫活動中使用的暱稱"),
            required=participant is None,
            max_length=80,
        )
        self.add_item(self.nickname)
        self.aa_image = None
        if event_type in {EventType.CHRISTMAS, EventType.GROUP}:
            self.aa_image = discord.ui.TextInput(
                label="AA形象",
                placeholder=("留空表示不修改" if participant else "請填寫本次活動使用的 AA 形象"),
                required=participant is None,
                max_length=100,
            )
            self.add_item(self.aa_image)
        self.team_leader = None
        if event_type is EventType.GROUP:
            self.team_leader = discord.ui.TextInput(
                label="是否報名組長？請填是或否",
                placeholder=("留空表示不修改；填是或否" if participant else "是 / 否"),
                required=participant is None,
                max_length=2,
            )
            self.add_item(self.team_leader)
        self.notes = discord.ui.TextInput(
            label="備註（選填）",
            placeholder=("留空表示不修改" if participant else "沒有備註可留空"),
            required=False,
            max_length=500,
            style=discord.TextStyle.paragraph,
        )
        self.add_item(self.notes)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not self.cog.bIsAAFanclub(interaction):
            await self.cog._error(interaction, "此表單只能在指定伺服器提交。")
            return
        nickname = self.nickname.value.strip()
        if not nickname and self.participant is None:
            await self.cog._error(interaction, "活動暱稱不可為空白。")
            return
        aa_image = self.aa_image.value.strip() if self.aa_image else None
        if self.aa_image and self.participant is None and not aa_image:
            await self.cog._error(interaction, "AA形象不可為空白。")
            return
        team_leader = None
        if self.team_leader:
            answer = self.team_leader.value.strip()
            if answer and answer not in {"是", "否"}:
                await self.cog._error(interaction, "組長意願請填「是」或「否」。")
                return
            team_leader = (answer == "是") if answer else None
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            if self.participant is None:
                participant = await self.cog.event_service.join(
                    str(interaction.user.id),
                    nickname,
                    aa_image=aa_image or "",
                    team_leader=team_leader,
                    notes=self.notes.value,
                )
            else:
                participant = await self.cog.event_service.update_registration(
                    str(interaction.user.id),
                    display_name=nickname or None,
                    aa_image=aa_image,
                    team_leader=team_leader,
                    notes=self.notes.value or None,
                )
            try:
                await self.cog._publish_signup_record(participant)
            except (discord.HTTPException, OSError, ValueError, EventServiceError):
                logger.warning(
                    "Could not publish signup message for registration %s",
                    participant.registration_number,
                    exc_info=True,
                )
                await self.cog._send(
                    interaction,
                    f"報名資料已保存，編號為 {participant.registration_number}，但報名區留言同步失敗，請通知管理員。",
                    ephemeral=True,
                )
                return
            if self.participant is None:
                try:
                    await self.cog._publish_participant_avatar(participant, interaction.user)
                except (AvatarServiceError, EventServiceError, OSError, ValueError):
                    logger.warning(
                        "Could not sync avatar for participant %s",
                        participant.discord_user_id,
                        exc_info=True,
                    )
                    await self.cog._send(
                        interaction,
                        f"報名成功，編號為 {participant.registration_number}；頭像同步失敗，管理員可稍後重新同步。",
                        ephemeral=True,
                    )
                    return
            else:
                await self.cog._post_registration_status(participant, "更改了報名表")
                try:
                    await self.cog._publish_participant_index(
                        participant,
                        f"Update participant signup ({participant.registration_number})",
                    )
                except Exception:
                    logger.warning(
                        "Could not publish updated participant index for registration %s",
                        participant.registration_number,
                        exc_info=True,
                    )
            verb = "報名成功" if self.participant is None else "報名資料已更新"
            await self.cog._send(
                interaction,
                f"{verb}，編號為 {participant.registration_number}。",
                ephemeral=True,
            )
        except (EventServiceError, OSError, ValueError) as exc:
            await self.cog._error(interaction, self.cog._user_error(exc))
        except Exception as exc:
            await self.cog._unexpected_error(interaction, "signup", exc)


async def setup(bot):
    await bot.add_cog(EventCog(bot))
