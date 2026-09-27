# 活動系統現行機制盤點

盤點日期：2026-09-27。依據目前工作樹與已提交的需求實作；不是只依 README 或舊架構提案。本文件描述已存在的程式行為；後續未完成需求另見原始需求文件。未連線 Discord、Git remote 或啟動新的 Web Server。

## 1. 入口、活動設定與權限

| 機制 | 現行行為 | 程式依據 |
|---|---|---|
| 載入 | 套件、event.py、event_multi.py 都建立同一 EventCog；後兩者是相容入口，不是待合併的舊實作 | `cmds/gitRely/__init__.py`、`event.py`、`event_multi.py` |
| 活動選擇 | 全域只保存一個 active-event.json；每次服務操作載入目前活動 | `repositories.py:EventRepository`、`event_service.py:load_active` |
| 活動種類 | submission、christmas、group；共用 topics 與投稿流程 | `models.py:EventType` |
| 設定活動 | `/seteventname` 接受活動名、類型、時區、四個時間與逗號分隔題目；執行頻道記為報名頻道 | `event_cog.py:activate_event` |
| 更新設定 | 同活動保留 participants；同名題目盡可能沿用 key；切換 active 前驗證設定 | `event_service.py:create_event`、`repositories.py:activate_event` |
| 時間 | 有時區；強制報名開始 < 報名截止 ≤ 投稿開始 < 投稿截止；依時間推導五個狀態 | `models.py:EventPrivate.validate`、`event_status` |
| 管理員／主辦人 | `/seteventadmins` 由 Bot 管理員設定當期主辦者 ID；活動操作指令依 private state 白名單檢查 | `event_cog.py:_is_admin`、`_is_event_host`、`event_service.py:set_event_hosts` |
| 群組限制 | `/event` 明確檢查指定 guild 及報名頻道；其他指令不能據此推定具有相同檢查 | `event_cog.py:event` |

目前 Christmas 模型沒有強制只能一題；架構提案中「聖誕只能一份」不能當作已存在的驗證。

## 2. 報名、編號、頭像與公開索引

1. `/event action:join` 取得 `interaction.user.id` 與 `interaction.user.name`，没有活動暱稱／AA 形象表單。
2. 報名期間才可加入，重複加入會拒絕；產生隨機 participant_key，保存 joined_at、display_name、avatar_path 等欄位。
3. `/event action:leave` 從 participants 陣列刪除紀錄；無取消狀態、恢復操作或原編號保留機制，也沒有立即同步公開索引的步驟。
4. 報名後下載 Discord 頭像、同步公開索引、Git 發布；下載失敗有保留報名並提示的處理。另有管理員 `/eventsyncicons` 重同步。
5. 頭像寫至 `images/players/<名單位置+1>.png`；公開 `uid` 也由名單位置計算，不是獨立持久編號。刪除中間參加者後，下一次同步可能重排編號；這亦影響頭像路徑與作品索引。
6. Discord 頭像不同於需求中的「AA 形象」。不能用已有頭像同步當作已完成 AA 形象欄位。

依據：`event_service.py:join/leave`、`models.py:Participant`、`avatar_service.py:sync_participant`、`event_cog.py:_publish_participant_avatar/sync_event_icons`。

`PublicEventIndex` 公開輸出：

| 檔案 | 主要內容 |
|---|---|
| `data/playerHashMap.json` | 一般投稿活動包含 uid、hashId、name、可選 image；Christmas 留空以避免公開作者對照 |
| `data/workUserMap.json` | hashId、topicKey、topic、title、file、url、overtime；一般活動另有 uid、name，Christmas 不寫作者欄位 |

一般活動作品依 uid、題目設定順序排序；上傳或清除會同步索引。Christmas 依活動類型不輸出作者名稱／編號對照；由 `/christmas publishworks` 以收禮者順序另行發布作品。隨機 participant key 與作品路徑仍屬公開索引資料。

## 3. 投稿內容與處理流程

`/upload file title [topic]` 已存在；單題可省略 topic，多題必須指定，可用題目 key 或名稱。每人每題最多一份，重傳完整覆蓋。

目前實際流程：

```text
Discord 附件（檢查 100 MiB）
  → uploads/ 下的臨時壓縮檔
  → 檢查投稿期間、報名資格、題目、標題、zip/rar/7z
  → request 專屬暫存目錄與安全解壓
  → 選取原有 HTML 或產生圖片 Gallery
  → 替換 <event_key>/pieces/<participant_key>/<topic_key>/
  → 保存公開索引快照、更新索引
  → GitPublisher 發布
  → 回覆 GitHub Pages 作品網址、清理暫存
```

依據：`event_cog.py:upload`、`submission_service.py:upload_archive`、`storage.py:SubmissionStorage`。

既有處理能力：

- 壓縮檔支援 zip、rar、7z；RAR 需 rarfile 與外部解壓工具，7z 需 py7zr。
- 展開容量預設 100 MiB、最多 500 檔；具有路徑檢查、容量檢查及連結防護。各格式實作不同，本次沒有重新認證所有格式的完整安全性。
- HTML 搜尋遞迴涵蓋 `.html`／`.htm`；优先選 `index.html`，否則用依路徑排序第一個 HTML。保留內容，不移除 JavaScript。
- 完全沒有 HTML 才用 png、jpg、jpeg、gif、webp 產生圖片 Gallery；只有音訊或影片而沒有 HTML／圖片不符合目前入口要求。
- 記錄實際 HTML 相對路徑，支援非 index.html 和子目錄入口，網址做 URL 編碼。
- 投稿包内的 CSS、JS、字型、影音及其他附屬檔案隨解壓保留；不是只挑圖片發布。
- `/upload` 的 defer 與成功回覆目前未設 ephemeral；在群頻道執行時預覽網址是公開回覆。

既有作品的靜態證據（不是新功能）：

| 範例路徑（相對 repository） | 已使用的內容 |
|---|---|
| `2026SummerEvent/pieces/f6LUgnmm/7AsVCD/index.html` | 內嵌 JavaScript 翻頁、iframe、pageN.html 相對路徑 |
| `2026SummerEvent/pieces/wZ-yH_pW/7AsVCD/即使如此开学仍会到来/` | 外部 episode_order.js、多頁閱讀、MP3 |
| `2026SummerEvent/pieces/kJlBMX3M/nmTbtD/小小人偶与梦.html` | MP4 影片 |
| `2026SummerEvent/pieces/yuapP54F/z8010G/aa.css` | 本機 WOFF2 字型 |
| `2026SummerEvent/pieces/uPNq2hg9/7AsVCD/index.html` | 圖片 Gallery |

## 4. 發布、清除與失敗處理

- Git 是發布機制，作品本來就已存本機；不是從 GitHub 下載後才有作品。
- GitPublisher 以 repository 層級 async lock 序列化，在背景執行 Git；包含 add、commit、pull --rebase、push，排除內部未追蹤備份，失敗時有回復本機新 commit 的處理。
- 替換作品時備份放在 request 暫存處，不放公開作品 repository；上傳發布失敗的處理會還原索引與作品。
- `/clear [topic]` 在投稿期間才能執行；用空目錄替換作品、更新索引並 Git 發布，發布失敗亦走回復流程。
- Git 發布呼叫點至少包含投稿、清除、報名頭像同步、管理員頭像重同步；只移除 upload 的 publish 不足以停止匿名流程公開身分資料。
- 這些是現有正常成功／錯誤流程，不代表已有檔案系統、JSON、Git 三者跨崩潰的原子交易或自動災難恢復。

依據：`submission_service.py`、`publisher.py`、`storage.py:replace_directory/rollback`、`event_cog.py`。

## 5. 黑名單、匿名訊息與配對

| 項目 | 現行機制 | 尚不能當成已具備的行為 |
|---|---|---|
| 黑名單 | `/blacklist add/view/remove` 私訊操作，以固定報名編號解析參加者；管理員 `/setblacklistsettings` 設定截止、每人上限及可選組長上限 | 管理員批次修正 |
| 匿名發言 | 已報名者在報名頻道使用；Bot 將內容送入頻道，後台保存作者及 Discord 訊息對照 | 配對雙方的私人轉送對話 |
| 匿名回覆 | 找內部 ID 或 Discord 訊息 ID，检查對方黑名單後以 Bot 回覆 | 完整 DM 工作流程、所有訊息鏈行為已驗證 |
| 黑名單方向 | owner 封鎖 blocked，產生 blocked → owner 的禁止邊 | 聖誕配對要求的雙向禁止尚未完整實作 |
| 抽籤 | 管理員 `/christmas giftshuffle` 呼叫注入的策略，保存結果；有結果即拒絕重抽 | 實際 rules_2026；預設 Cog 未注入 policy_resolver，正常路徑目前無法抽籤 |
| 結果驗證 | 檢查類型、參加者身分及給定方向的黑名單 | 一人一送一收、禁止自配、雙向封鎖等完整聖誕規則 |
| 查看配對 | `/christmas giftme` 取出與本人相關的兩個方向，顯示送給誰及誰送給自己 | 揭曉前隱藏送禮者、只顯示收禮者報名表 |

黑名單、匿名訊息、抽籤／查詢目前沒有完整按活動階段限制。依據：`christmas_service.py`、`event_cog.py`、`matching/protocol.py`、`matching/__init__.py`。

## 6. 資料保存

```text
data/active-event.json
data/events/<event>/event-private.json
data/events/<event>/anonymous-messages.json
data/events/<event>/blacklist.json
data/events/<event>/gift-assignments.json
data/events/<event>/guesses.json
data/events/<event>/published-works.json
<event>/event-public.json
<event>/data/playerHashMap.json
<event>/data/workUserMap.json
<event>/pieces/...
<event>/images/players/...
uploads/...
```

EventRepository 使用原子 JSON 替換與程序內鎖，各服務另有 async lock。這不是已使用 SQLite 的活動系統；其他遊戲模組的 `.db` 不能當作活動 SQLite 已完成。也尚無活動 Web Server、preview token、OAuth session、猜作者資料表。

## 7. 原始需求實作狀態

已完成：分活動類型的 `/signup` modal、修改／退出／恢復及固定編號；報名留言與活動雜談通知；私訊 `/blacklist add/view/remove`、活動黑名單額度與獨立截止、主辦者白名單、`/sudo` 黑名單維護與 kick/revertkick。

仍待完成：`/sudo rollgroup`（需要本期實際組活規則）、`/group` 組活結果查看／下載，以及最後揭曉流程。

以上在原始需求文字中已存在，屬於補齊舊需求，不是新提出的業務需求。舊文「沿用去年私信」僅有文字指涉，目前檢視的活動模組不能證明已具備該完整流程。

## 8. 驗證與文件落差

本次執行 `python -m unittest discover -s tests -p test_git_rely_refactor.py`：15 項通過。涵蓋部分時間邊界、隨機 key、活動切換、ZIP 路徑穿越、HTML 優先、備份位置、模擬 Git 失敗回復、索引排序、截止後 clear 與部分匿名／黑名單錯誤流程。

測試不等於已驗證真實 Discord、RAR／7z 環境、GitHub Pages、Funnel、完整匿名性、Web 登入或瀏覽器影音相容性。

既有文檔存在落差，實作前應依本盤點同步修訂：

- README 仍寫 discord.py 1.7.3，但 requirements 固定 2.3.2。
- event_architecture.md 標「尚未實作」，但其中多數模組與單一 Cog 已存在；其中不限制 Git 歷史的匿名邊界已不符合補充需求。
- event_commands.md／event_operations.md 未完整反映頭像同步、HTML 實際入口等行為；「不含 Discord ID」不等於作者匿名。

本次僅建立盤點與修訂變更文件；不改活動程式、資料、公開作品或其他既有文件，以免把預定行為寫成已上線功能。
