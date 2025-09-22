import os
import json
from discord.ext import commands
from Module_a.unzip import extract_archive
import shutil
from core.classes import Cog_extension

class event(Cog_extension):
    def __init__(self, bot):
        self.bot = bot
        self.data_file = os.path.join("./data/", "eventInfo.json")
        self.upload_dir = "./uploads"       # 暫存壓縮檔
        os.makedirs(self.upload_dir, exist_ok=True)
        self.participants = []
        self.eventName = "TBD"

        if os.path.exists(self.data_file):
            with open(self.data_file, "r", encoding="UTF-8") as f:
                eventInfo = json.load(f)
                self.participants = eventInfo.get("participants", [])
                self.eventName = eventInfo.get("eventName", "TBD")
    def isNewParticipant(self, user_id: str) -> bool:
        """檢查 user_id 是否尚未登記"""
        if not self.participants:
            return True

        for p in self.participants:
            if p["id"] == user_id:
                return False
        return True
    @staticmethod
    def madeIndex(folderPath: str, title: str):
        html_content = ""
        with open('template.html', 'r', encoding='utf-8') as file:
            html_content = file.read()

        if not html_content:
            return

        # 替換標題
        tmp_Html = html_content.replace("123標題預留位321", title)

        # 過濾圖片檔
        image_files = [f for f in os.listdir(folderPath) 
                    if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))]
        image_tags = ""
        for idx, fname in enumerate(sorted(image_files), start=1):  # 排序後輸出
            image_path = fname  # 保留相對路徑
            image_tags += f'<img src="{image_path}" alt="Image {idx}" style="max-width:100%; height:auto;"><br>\n'

        # 把圖片列表插進 template
        tmp_Html = tmp_Html.replace("456圖片預留位654", image_tags)

        # 輸出到 index.html
        output_path = os.path.join(folderPath, f"{title}.html")
        with open(output_path, 'w', encoding='utf-8') as out:
            out.write(tmp_Html)

    def save_event_info(self, extra: dict = None):
        eventInfo = {
            "eventName": self.eventName,
            "participants": self.participants
        }
        if extra:
            eventInfo.update(extra)  # 允許額外附加欄位（例如 lastUpload）
        with open(self.data_file, "w", encoding="UTF-8") as f:
            json.dump(eventInfo, f, ensure_ascii=False, indent=2)

    @commands.command()
    async def setEventName(self, ctx, strEventName: str = None):
        if not self.bIsAAFanclub(ctx):
            await ctx.send(f"請在同好會操作")
            return
        if(not self.bIsAdmin(ctx.author) and not self.bIsDeveloper(ctx.author.id)):
            await ctx.send(f"你不是群管也不是開發者")
            return
        folder_path = os.path.join("./", strEventName)

        if not os.path.exists(folder_path):
            await ctx.send(f"❌ 資料夾 `{strEventName}` 不存在，請聯繫開發者或維護者。")
            return
        self.eventName = strEventName
        self.save_event_info()
        await ctx.send(f"✅ 已更新活動名稱`{self.eventName}`")
        return
    @commands.command()
    async def event(self, ctx, action: str = None):
        """
        參加或退賽
        """
        hint = '⚠️ 請輸入動作：`&&event 參加` 或 `退賽`'
        user_id = str(ctx.author.id)

        if action is None:
            await ctx.send(hint)
            return

        # === 報名 ===
        if action.lower() in ["join", "add", "enter", "參加"]:
            if not self.isNewParticipant(user_id):
                await ctx.send(f"⚠️ 參賽者 <@{user_id}> 已經存在！")
                return

            max_uid = max((p["uid"] for p in self.participants), default=0)
            new_uid = max_uid + 1

            self.participants.append({
                "uid": new_uid,
                "id": user_id,
                "name": ctx.author.name,
            })

            self.save_event_info()
            await ctx.send(f"✅ <@{user_id}> 已報名成功，分配編號：`{new_uid}`")

        # === 退賽 ===
        elif action.lower() in ["leave", "remove", "quit", "退賽"]:
            found = False
            for p in self.participants:
                if p["id"] == user_id:
                    self.participants.remove(p)
                    found = True
                    break

            if not found:
                await ctx.send(f"⚠️ <@{user_id}> 目前不在參賽名單中！")
                return

            self.save_event_info()
            await ctx.send(f"✅ <@{user_id}> 已退出比賽")

        else:
            await ctx.send(hint)

    @commands.command()
    async def Upload(self, ctx, title:str ="TBD"):
        """接收一個壓縮檔，下載並解壓縮"""
        user_id = str(ctx.author.id)
        folderName = user_id #等之後確認是否要hash以避免有人提前看到頁面
        if self.isNewParticipant(user_id):
            await ctx.send(f"⚠️ 你還未報名！ 輸入`&&event 參加`")
            return
        if not ctx.message.attachments:
            await ctx.send("⚠️ 請附加一個壓縮檔 (.zip/.rar/.7z)")
            return

        attachment = ctx.message.attachments[0]
        filename = attachment.filename
        filepath = os.path.join(self.upload_dir, filename)
        # === 作品資料夾 ===
        target_folder = os.path.join(self.eventName, "pieces", folderName)
        if not filename.lower().endswith((".zip", ".rar", ".7z")):
            await ctx.send("⚠️ 不支援的檔案格式，只接受 .zip/.rar/.7z")
            return
        try:
            await attachment.save(filepath)
            await ctx.send(f"📥 已下載 `{filename}`")
            
            # 如果資料夾已存在 → 刪除後重建
            if os.path.exists(target_folder):
                shutil.rmtree(target_folder)  # 整個刪除
            os.makedirs(target_folder, exist_ok=True)

            # 執行解壓縮
            extract_archive(filepath, target_folder)
            await ctx.send(f"✅ 已成功解壓縮 `{filename}` 到 `{target_folder}`")
                    # === 新增檢查檔案類型邏輯 ===
            files = os.listdir(target_folder)
            html_files = [f for f in files if f.lower().endswith(".html")]
            image_files = [f for f in files if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))]

            if html_files:
                await ctx.send(f"請稍後確認連結 https://aafanclubdc.github.io/{self.eventName}/pieces/{folderName}/{html_files[0]}")
            elif image_files:
                await ctx.send(f"🖼 偵測到圖片檔案，共 {len(image_files)} 張，正在建立 index ...")
                try:
                    self.madeIndex(target_folder,title)
                    await ctx.send(f"請稍後確認連結 https://aafanclubdc.github.io/{self.eventName}/pieces/{folderName}/{title}.html")
                except Exception as e:
                    await ctx.send(f"❌ 建立目錄失敗：{e}")
            else:
                await ctx.send("⚠️ 未找到可辨識的 HTML 或圖片檔案")
        except Exception as e:
            await ctx.send(f"❌ 解壓縮失敗：{e}")
            return
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)
        
async def setup(bot):
    await bot.add_cog(event(bot))
