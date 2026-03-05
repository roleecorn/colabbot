import os
import json
import shutil
from typing import Optional, List

import aiohttp
import discord
from discord import app_commands

from Module_a.unzip import extract_archive
import push2Git
from core.classes import GUILD_ID

from .event_base import EventBase
from .event_utils import (
    hash_user_id,
    is_past_deadline,
    make_index,
    normalize_topic_name,
)


class event(EventBase):
    def __init__(self, bot):
        super().__init__(bot)

    @staticmethod
    def _next_available_path(folder: str, filename: str) -> str:
        base, ext = os.path.splitext(filename)
        candidate = os.path.join(folder, filename)
        idx = 1
        while os.path.exists(candidate):
            candidate = os.path.join(folder, f"{base}_{idx}{ext}")
            idx += 1
        return candidate

    def _flatten_extracted_files(self, target_folder: str) -> None:
        # Move nested extracted files to target root.
        for root, _, files in os.walk(target_folder):
            if os.path.abspath(root) == os.path.abspath(target_folder):
                continue
            for name in files:
                src = os.path.join(root, name)
                dst = os.path.join(target_folder, name)
                if os.path.exists(dst):
                    dst = self._next_available_path(target_folder, name)
                shutil.move(src, dst)

        # Remove empty subdirectories left by extraction.
        for root, dirs, _ in os.walk(target_folder, topdown=False):
            for d in dirs:
                dir_path = os.path.join(root, d)
                if os.path.abspath(dir_path) == os.path.abspath(target_folder):
                    continue
                if not os.listdir(dir_path):
                    os.rmdir(dir_path)

    @app_commands.command(name="seteventname", description="設定活動名稱")
    @app_commands.describe(
        event_name="活動資料夾名稱",
        start_time="yyyymmdd-HHMM (可留空)",
        registration_deadline="yyyymmdd-HHMM (可留空)",
        upload_deadline="yyyymmdd-HHMM (可留空)",
        is_team_event="是否為團體活動 (可留空)",
        topics="題目清單，用逗號分隔 (可留空)",
    )
    async def set_event_name(
        self,
        interaction: discord.Interaction,
        event_name: str,
        start_time: Optional[str] = None,
        registration_deadline: Optional[str] = None,
        upload_deadline: Optional[str] = None,
        is_team_event: Optional[bool] = None,
        topics: Optional[str] = None,
    ):
        await self._set_event_name_common(
            interaction,
            event_name,
            start_time=start_time,
            registration_deadline=registration_deadline,
            upload_deadline=upload_deadline,
            is_team_event=is_team_event,
            topics=topics,
        )

    @app_commands.command(name="event", description="報名或退出活動")
    @app_commands.choices(
        action=[
            app_commands.Choice(name="join", value="join"),
            app_commands.Choice(name="leave", value="leave"),
        ]
    )
    async def event(self, interaction: discord.Interaction, action: str):
        user_id = str(interaction.user.id)

        # if not interaction.guild or not self.bIsAAFanclub(interaction):
        #     await self._send_error(interaction, "此指令只能在指定伺服器使用。")
        #     return
        if str(interaction.channel_id) != self.registration:
            await self._send_error(interaction, f"請在 <#{self.registration}> 使用。")
            return
        if is_past_deadline(self.registrationEnd):
            await self._send_error(interaction, "報名已截止。")
            return

        await interaction.response.defer(thinking=True)

        if action.lower() == "join":
            if not self.isNewParticipant(user_id):
                await self._send_error(interaction, "你已經報名了。")
                return

            max_uid = max((p.get("uid", 0) for p in self.participants), default=0)
            new_uid = max_uid + 1

            self.participants.append(
                {
                    "uid": new_uid,
                    "id": user_id,
                    "name": interaction.user.name,
                }
            )

            img_dir = os.path.join(self.eventName, "images", "players")
            os.makedirs(img_dir, exist_ok=True)

            avatar_url = interaction.user.display_avatar.with_size(128).url
            img_path = os.path.join(img_dir, f"{new_uid}.png")

            async with aiohttp.ClientSession() as session:
                async with session.get(avatar_url) as resp:
                    if resp.status == 200:
                        with open(img_path, "wb") as f:
                            f.write(await resp.read())

            self.save_event_info()
            await self._send(interaction, f"報名成功，編號 `{new_uid}`")

        elif action.lower() == "leave":
            found = False
            for p in list(self.participants):
                if p.get("id") == user_id:
                    self.participants.remove(p)
                    found = True
                    break

            if not found:
                await self._send_error(interaction, "你尚未報名。")
                return

            self.save_event_info()
            await self._send(interaction, "已退出活動。")

        else:
            await self._send_error(interaction, "請選擇 join 或 leave。")
            return

        success, msg = push2Git.git_commit_and_push(
            f"./{self.eventName}",
            f"{interaction.user.name} join/leave",
        )

    async def _topic_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        try:
            topics = self.topics if isinstance(self.topics, list) else []
            if not topics:
                return []

            current_lower = (current or "").lower()
            results: List[app_commands.Choice[str]] = []
            for raw_topic in topics:
                topic = str(raw_topic).strip()
                if not topic:
                    continue
                if current_lower and current_lower not in topic.lower():
                    continue

                # Discord autocomplete choice name/value max length is 100.
                safe_topic = topic[:100]
                results.append(app_commands.Choice(name=safe_topic, value=safe_topic))
                if len(results) >= 25:
                    break
            return results
        except Exception:
            return []

    @app_commands.command(name="upload", description="上傳作品")
    @app_commands.describe(
        file="壓縮檔 (.zip/.rar/.7z)",
        title="作品標題",
        topic="題目",
    )
    @app_commands.autocomplete(topic=_topic_autocomplete)
    async def upload(
        self,
        interaction: discord.Interaction,
        file: discord.Attachment,
        topic: str,
        title: str,
    ):
        user_id = str(interaction.user.id)
        folder_name = hash_user_id(user_id + self.eventName)

        if self.isNewParticipant(user_id):
            await self._send_error(interaction, "請先使用 /event join 報名。")
            return
        if is_past_deadline(self.uploadEnd):
            await self._send_error(interaction, "上傳已截止。")
            return
        if not self.topics:
            await self._send_error(interaction, "尚未設定題目清單。")
            return
        if topic not in self.topics:
            await self._send_error(interaction, "題目不在清單內。")
            return
        if not title.strip():
            await self._send_error(interaction, "title 不能為空。")
            return

        filename = file.filename
        if not filename.lower().endswith((".zip", ".rar", ".7z")):
            await self._send_error(interaction, "請上傳 .zip/.rar/.7z 檔案。")
            return

        filepath = os.path.join(self.upload_dir, filename)
        topic_folder = normalize_topic_name(topic)
        target_folder = os.path.join(self.eventName, "pieces", folder_name, topic_folder)

        try:
            await interaction.response.defer(thinking=True)
            await file.save(filepath)
            await self._send(interaction, f"已收到 `{filename}`")

            # Keep previous uploads and add new files on top.
            os.makedirs(target_folder, exist_ok=True)

            extract_archive(filepath, target_folder)
            self._flatten_extracted_files(target_folder)
            await self._send(interaction, f"解壓完成：`{target_folder}`")

            files = os.listdir(target_folder)
            html_files = [f for f in files if f.lower().endswith(".html")]
            image_files = [
                f for f in files if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))
            ]
            preview_url = None
            if html_files:
                preview_url = (
                    f"https://aafanclubdc.github.io/{self.eventName}/pieces/"
                    f"{folder_name}/{topic_folder}/{html_files[0]}"
                )
            elif image_files:
                try:
                    make_index(target_folder, title)
                    index_name = f"{title}.html"
                    if os.path.exists(os.path.join(target_folder, index_name)):
                        preview_url = (
                            f"https://aafanclubdc.github.io/{self.eventName}/pieces/"
                            f"{folder_name}/{topic_folder}/{index_name}"
                        )
                except Exception as e:
                    await self._send(interaction, f"未產生預覽頁：{e}")

            if preview_url:
                await self._send(interaction, f"預覽： {preview_url}")

            success, msg = push2Git.git_commit_and_push(
                f"./{self.eventName}",
                f"Upload {title} ({topic})",
            )
            await self._send(interaction, msg)

        except Exception as e:
            await self._send_error(interaction, f"上傳失敗：{e}")
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)

    @app_commands.command(name="clear", description="清空自己的題目資料夾")
    @app_commands.describe(topic="題目")
    @app_commands.autocomplete(topic=_topic_autocomplete)
    async def clear(self, interaction: discord.Interaction, topic: str):
        user_id = str(interaction.user.id)
        folder_name = hash_user_id(user_id + self.eventName)

        if self.isNewParticipant(user_id):
            await self._send_error(interaction, "請先使用 /event join 報名。")
            return
        if not self.topics:
            await self._send_error(interaction, "尚未設定題目清單。")
            return
        if topic not in self.topics:
            await self._send_error(interaction, "題目不在清單內。")
            return

        topic_folder = normalize_topic_name(topic)
        target_folder = os.path.join(self.eventName, "pieces", folder_name, topic_folder)
        if not os.path.exists(target_folder):
            await self._send_error(interaction, "找不到對應資料夾可清空。")
            return

        await interaction.response.defer(thinking=True)
        shutil.rmtree(target_folder)
        os.makedirs(target_folder, exist_ok=True)
        await self._send(interaction, f"已清空：`{target_folder}`")

        success, msg = push2Git.git_commit_and_push(
            f"./{self.eventName}",
            f"Clear folder ({interaction.user.name}) {topic}",
        )
        await self._send(interaction, msg)


async def setup(bot):
    await bot.add_cog(event(bot))
