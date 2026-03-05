import os
import json
import random
import re
import shutil
from typing import Optional, List, Dict

import aiohttp
import discord
from discord import app_commands

from Module_a.unzip import extract_archive
import push2Git

from .event_base import EventBase
from .event_utils import hash_user_id, make_index


class event(EventBase):
    def __init__(self, bot):
        super().__init__(bot)

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

        if not interaction.guild or not self.bIsAAFanclub(interaction):
            await self._send(interaction, "此指令只能在指定伺服器使用。")
            return
        if str(interaction.channel_id) != self.registration:
            await self._send(interaction, f"請在 <#{self.registration}> 使用。")
            return

        await interaction.response.defer(thinking=True)

        if action.lower() == "join":
            if not self.isNewParticipant(user_id):
                await self._send(interaction, "你已經報名了。")
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
                await self._send(interaction, "你尚未報名。")
                return

            self.save_event_info()
            await self._send(interaction, "已退出活動。")

        else:
            await self._send(interaction, "請選擇 join 或 leave。")
            return

        success, msg = push2Git.git_commit_and_push(
            f"./{self.eventName}",
            f"{interaction.user.name} join/leave",
        )

    @app_commands.command(name="upload", description="上傳作品")
    @app_commands.describe(file="壓縮檔 (.zip/.rar/.7z)", title="作品標題")
    async def upload(
        self,
        interaction: discord.Interaction,
        file: discord.Attachment,
        title: str,
    ):
        user_id = str(interaction.user.id)
        folder_name = hash_user_id(user_id + self.eventName)

        if self.isNewParticipant(user_id):
            await self._send(interaction, "請先使用 /event join 報名。")
            return
        if not title.strip():
            await self._send_error(interaction, "title 不能為空。")
            return

        filename = file.filename
        if not filename.lower().endswith((".zip", ".rar", ".7z")):
            await self._send(interaction, "請上傳 .zip/.rar/.7z 檔案。")
            return

        filepath = os.path.join(self.upload_dir, filename)
        target_folder = os.path.join(self.eventName, "pieces", folder_name)

        try:
            await interaction.response.defer(thinking=True)
            await file.save(filepath)
            await self._send(interaction, f"已收到 `{filename}`")

            # Keep previous uploads and add new files on top.
            os.makedirs(target_folder, exist_ok=True)

            extract_archive(filepath, target_folder)
            await self._send(interaction, f"解壓完成：`{target_folder}`")

            files = os.listdir(target_folder)
            html_files = [f for f in files if f.lower().endswith(".html")]
            image_files = [
                f for f in files if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))
            ]

            if html_files:
                await self._send(
                    interaction,
                    f"預覽： https://aafanclubdc.github.io/{self.eventName}/pieces/{folder_name}/{html_files[0]}",
                )
            elif image_files:
                try:
                    make_index(target_folder, title)
                    await self._send(
                        interaction,
                        f"預覽： https://aafanclubdc.github.io/{self.eventName}/pieces/{folder_name}/{title}.html",
                    )
                except Exception as e:
                    await self._send(interaction, f"產生索引失敗：{e}")
            else:
                await self._send(interaction, "找不到 HTML 或圖片檔案。")
                return

            success, msg = push2Git.git_commit_and_push(
                f"./{self.eventName}",
                f"Upload {title}",
            )
            await self._send(interaction, msg)

        except Exception as e:
            await self._send(interaction, f"上傳失敗：{e}")
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)

    @app_commands.command(name="clear", description="清空自己的上傳資料夾")
    async def clear(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        folder_name = hash_user_id(user_id + self.eventName)

        if self.isNewParticipant(user_id):
            await self._send_error(interaction, "請先使用 /event join 報名。")
            return

        target_folder = os.path.join(self.eventName, "pieces", folder_name)
        if not os.path.exists(target_folder):
            await self._send_error(interaction, "找不到對應資料夾可清空。")
            return

        await interaction.response.defer(thinking=True)
        shutil.rmtree(target_folder)
        os.makedirs(target_folder, exist_ok=True)
        await self._send(interaction, f"已清空：`{target_folder}`")

        success, msg = push2Git.git_commit_and_push(
            f"./{self.eventName}",
            f"Clear folder ({interaction.user.name})",
        )
        await self._send(interaction, msg)

    @app_commands.command(name="blacklist", description="新增黑名單")
    @app_commands.describe(ids="使用空白分隔 ID")
    async def blacklist(self, interaction: discord.Interaction, ids: str):
        args = [part for part in ids.split() if part]
        if not args:
            await self._send(interaction, "請輸入至少一個 ID。")
            return

        data_file = os.path.join(f"./{self.eventName}/", "data", "blacklist.json")
        if len(args) > 5:
            await self._send(interaction, "一次最多 5 個 ID。")
            return

        blacklist = {}
        if os.path.exists(data_file):
            with open(data_file, "r", encoding="UTF-8") as f:
                try:
                    blacklist = json.load(f)
                except json.JSONDecodeError:
                    await self._send(interaction, "黑名單檔案格式錯誤。")
                    return

        blacklist[str(interaction.user.id)] = args
        os.makedirs(os.path.dirname(data_file), exist_ok=True)
        with open(data_file, "w", encoding="UTF-8") as f:
            json.dump(blacklist, f, indent=4, ensure_ascii=False)

        await self._send(interaction, "已更新黑名單。")

    @app_commands.command(name="anonsay", description="匿名發言")
    @app_commands.describe(content="內容")
    async def anon_say(self, interaction: discord.Interaction, content: str):
        if not interaction.guild or not self.bIsAAFanclub(interaction):
            await self._send(interaction, "此指令只能在指定伺服器使用。", ephemeral=True)
            return
        if str(interaction.channel_id) != self.registration:
            await self._send(interaction, f"請在 <#{self.registration}> 使用。", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        await interaction.channel.send(content)
        await interaction.followup.send("已匿名發言。", ephemeral=True)

    @app_commands.command(name="anonreply", description="匿名回覆")
    @app_commands.describe(message_id="訊息 ID 或連結", content="回覆內容")
    async def anon_reply(self, interaction: discord.Interaction, message_id: str, content: str):
        if not interaction.guild or not self.bIsAAFanclub(interaction):
            await self._send(interaction, "此指令只能在指定伺服器使用。", ephemeral=True)
            return
        if str(interaction.channel_id) != self.registration:
            await self._send(interaction, f"請在 <#{self.registration}> 使用。", ephemeral=True)
            return

        match = re.findall(r"\d{15,20}", message_id)
        if not match:
            await self._send(interaction, "找不到有效的訊息 ID。", ephemeral=True)
            return

        target_id = int(match[-1])
        try:
            target = await interaction.channel.fetch_message(target_id)
        except Exception:
            await self._send(interaction, "無法取得該訊息。", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        await target.reply(content, mention_author=False)
        await interaction.followup.send("已匿名回覆。", ephemeral=True)

    def _gift_file_path(self) -> str:
        return os.path.join(f"./{self.eventName}/", "data", "gifts.json")

    def _build_gift_pairs(self) -> Optional[List[Dict]]:
        ids = [p.get("id") for p in self.participants if p.get("id")]
        if len(ids) < 2:
            return None

        receivers = ids[:]
        if len(ids) == 2:
            receivers = ids[::-1]
        else:
            for _ in range(50):
                random.shuffle(receivers)
                if all(giver != receiver for giver, receiver in zip(ids, receivers)):
                    break
            else:
                return None

        name_by_id = {p.get("id"): p.get("name", "") for p in self.participants}
        pairs = []
        for giver, receiver in zip(ids, receivers):
            pairs.append(
                {
                    "giver_id": giver,
                    "giver_name": name_by_id.get(giver, ""),
                    "receiver_id": receiver,
                    "receiver_name": name_by_id.get(receiver, ""),
                }
            )
        return pairs

    @app_commands.command(name="giftshuffle", description="整理隱藏的送禮對象")
    async def gift_shuffle(self, interaction: discord.Interaction):
        if not self.bIsAdmin(interaction.user) and not self.bIsDeveloper(interaction.user.id):
            await self._send(interaction, "需要管理員權限。", ephemeral=True)
            return

        pairs = self._build_gift_pairs()
        if not pairs:
            await self._send(interaction, "人數不足或無法建立配對。", ephemeral=True)
            return

        data = {"pairs": pairs}
        path = self._gift_file_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="UTF-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        await self._send(interaction, "已整理完成（隱藏）。", ephemeral=True)

    @app_commands.command(name="giftme", description="查看送禮對象與被送禮對象")
    async def gift_me(self, interaction: discord.Interaction):
        path = self._gift_file_path()
        if not os.path.exists(path):
            await self._send(interaction, "尚未整理送禮對象。", ephemeral=True)
            return

        with open(path, "r", encoding="UTF-8") as f:
            data = json.load(f)

        pairs = data.get("pairs", []) if isinstance(data, dict) else data
        user_id = str(interaction.user.id)

        give_to = next((p for p in pairs if p.get("giver_id") == user_id), None)
        receive_from = next((p for p in pairs if p.get("receiver_id") == user_id), None)

        if not give_to and not receive_from:
            await self._send(interaction, "找不到你的配對資料。", ephemeral=True)
            return

        lines = []
        if give_to:
            lines.append(f"你要送給：<@{give_to.get('receiver_id')}>")
        if receive_from:
            lines.append(f"送給你的人：<@{receive_from.get('giver_id')}>")

        await self._send(interaction, "\n".join(lines), ephemeral=True)


async def setup(bot):
    await bot.add_cog(event(bot))
