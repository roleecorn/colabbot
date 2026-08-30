# 活動系統目標架構

> 狀態：架構提案，尚未實作。
>
> 本文件描述 `cmds/gitRely` 重構後的目標，不代表目前的 `event.py` 與
> `event_multi.py` 已經具備以下行為。現行指令請參考
> [event_commands.md](event_commands.md)。

## 1. 目標

活動系統只保留兩種互斥的活動類型：

1. **一般投稿活動（submission）**
   - 提供報名、退出、上傳與清除作品。
   - 每個題目每位參加者最多一份作品。
   - 只有一個題目時，就是原本的「獨立活動」。
   - 有多個題目時，就是原本的「複合活動」。
2. **聖誕交換活動（christmas）**
   - 提供報名、退出、匿名對話、匿名投稿、黑名單與送禮配對。
   - 每位參加者只會有一份投稿，不支援複合活動的多題投稿。
   - 配對限制因活動而異，由活動專用規則提供；具體配對演算法不屬於本次重構範圍。

同一時間全系統只能啟用一個活動。兩種活動不會同時成立，也不應同時載入兩套
Discord Cog。

## 2. 核心設計原則

### 2.1 一個 Cog、兩種活動類型

`event.py` 與 `event_multi.py` 應合併成單一 `EventCog`。活動差異由設定與服務決定，
而不是由兩份具有相同 slash command 的 Cog 決定。

```text
EventCog
  └─ EventService
       ├─ SubmissionEventPolicy
       └─ ChristmasEventPolicy
```

`EventCog` 只負責 Discord 輸入、權限檢查與訊息回覆，不直接讀寫 JSON、解壓縮或執行
Git 指令。

### 2.2 題目就是投稿槽位

一般投稿活動不需要另外區分「獨立」和「複合」模式。活動設定中的 `topics` 就是可用的
投稿槽位：

- `topics` 只有一項：每人最多上傳一份作品。
- `topics` 有多項：每人可對每個題目各上傳一份作品。

同一位參加者再次上傳同一題目時，必須完整覆蓋舊版本，不保留或疊加舊檔案。

每份作品不建立額外的 `submission_id`。作品以「參加者公開代碼 + 題目代碼」唯一識別，
避免預覽網址過長。

### 2.3 公開資料與私密資料分離

活動 repository 會由 GitHub Pages 公開。為避免從公開索引直接把預覽網址對回使用者，
`participant_key` 與 Discord ID 的對照不可放入 repository；匿名訊息作者、黑名單與
聖誕配對對照也屬於後台資料。

資料必須分成兩個邊界：

```text
本機私密資料（不 commit）
  ├─ Discord ID ↔ participant_key
  ├─ 報名名單
  ├─ 匿名訊息作者
  ├─ 黑名單
  └─ 聖誕配對結果

活動 Git repository（可公開）
  ├─ 公開活動設定
  ├─ 已發布作品
  └─ 不含身分的作品索引
```

`participant_key` 應在報名時隨機產生，並限制為適合網址的短字串。不得繼續使用
`SHA256(discord_id + event_name)` 作為匿名代碼，因為知道 Discord ID 和活動名稱的人可以
自行重算並反查作者。

## 3. 活動生命週期

活動只需要以下四個時間欄位：

- `registration_starts_at`
- `registration_ends_at`
- `submission_starts_at`
- `submission_ends_at`

系統依目前時間推導狀態，不另外保存容易不同步的狀態欄位：

| 狀態 | 條件 | 允許操作 |
|---|---|---|
| `scheduled` | 報名尚未開始 | 管理員設定活動 |
| `registration_open` | 報名期間 | 報名、退出 |
| `waiting_submission` | 報名結束、投稿尚未開始 | 管理員操作 |
| `submission_open` | 投稿期間 | 上傳、覆蓋、清除作品 |
| `closed` | 投稿截止 | 查詢與管理員操作 |

管理員可在所有階段修正參加者資料。一般參加者只能在 `registration_open` 階段報名或
退出，避免報名截止後更動名單影響聖誕配對。

所有時間使用具時區的 datetime；活動設定必須明確保存 `Asia/Taipei` 或其他 IANA 時區，
不得依賴執行機器的本地時間。

## 4. 指令介面

保留現有 slash command 名稱，降低使用者重新學習的成本。

### 4.1 共用指令

| 指令 | 目標行為 |
|---|---|
| `/seteventname` | 啟用並設定唯一的全域活動。內部函式應改名為 `activate_event`。 |
| `/event action:join` | 在報名期間加入目前活動。 |
| `/event action:leave` | 在報名期間退出目前活動。 |
| `/upload` | 上傳並完整覆蓋該題目的既有作品。 |
| `/clear` | 清除自己的指定題目作品。 |

一般投稿活動的 `/upload` 與 `/clear` 都接受 `topic`。即使活動只有一個題目，也由同一套
服務處理；介面層可在只有一個選項時自動選取，不要求使用者重複輸入。

### 4.2 聖誕活動指令

| 指令 | 目標行為 |
|---|---|
| `/anonsay` | 匿名發言；公開訊息不含作者，私密資料保存作者對照。 |
| `/anonreply` | 匿名回覆；套用相同的作者保存與黑名單規則。 |
| `/blacklist` | 設定不接受匿名互動且不可配對的參加者。 |
| `/giftshuffle` | 依本次活動指定的配對規則產生結果。 |
| `/giftme` | 顯示配對策略允許公開給目前使用者的結果。 |

`/blacklist` 應採完整覆蓋語意，避免「新增黑名單」與實際覆蓋資料的行為不一致。實作時
應在 Discord 說明中明確寫成「設定黑名單」。

## 5. 投稿識別與目錄

### 5.1 一般投稿活動

```text
<event_repo>/
  event-public.json
  pieces/
    <participant_key>/
      <topic_key>/
        index.html
        001.png
        002.png
```

預覽網址：

```text
https://<pages-host>/<event>/<participant_key>/<topic_key>/
```

`topic_key` 由活動建立時產生並保存，不應在每次上傳時臨時把題目名稱替換成資料夾名稱。
它必須短、穩定且通過 Windows、Git 與 URL 的共同限制。

### 5.3 靜態作品頁公開索引

作品頁不應依賴掃描目錄來決定顯示順序。一般投稿活動可在公開 repository 保存兩份不含
Discord ID 的索引：

```text
<event_repo>/
  data/
    playerHashMap.json   # uid、隨機 participant key、公開顯示名稱
    workUserMap.json     # participant key、topic key、標題與預覽 URL
```

`playerHashMap.json` 的 `uid` 由報名順序決定；`workUserMap.json` 必須以
`uid` 再以 `topics` 的設定順序排序。這樣前端可以選擇按題目分組（SpringEvent 的模式），
也可以按參加者分組；例如 SummerEvent 固定顯示 User A 的第一至第五篇，再顯示 User B
的第一至第五篇。上傳、覆蓋與清除作品時，索引必須和作品目錄一起納入同一個可回復的發布交易。

### 5.2 聖誕交換活動

```text
<event_repo>/
  event-public.json
  pieces/
    <random_participant_key>/
      gift/
        index.html
        001.png
```

匿名投稿在此只表示：**無法從預覽網址本身看出投稿者是誰**。網址中的
`random_participant_key` 不得包含 Discord ID、Discord 名稱，亦不得使用外部使用者可以
自行重算的雜湊值。這項需求不限制投稿檔案內容、檔名、圖片 metadata 或 Git commit。

## 6. 覆蓋式上傳流程

上傳不能直接解壓到正式作品目錄，否則失敗時會留下半套檔案。正確流程如下：

1. 以 UUID 建立本次請求專用的暫存目錄。
2. 驗證副檔名、檔案大小、解壓後大小、檔案數量與路徑。
3. 解壓到暫存目錄，拒絕絕對路徑與 `..` 路徑穿越。
4. 若作品內已有 HTML，優先使用 `index.html`；沒有時使用名稱排序第一個 HTML。只有完全沒有 HTML
   時，才依圖片產生預覽頁並驗證結果。
5. 使用該參加者既有的隨機 `participant_key` 組合正式路徑。
6. 將既有 `<participant_key>/<topic_key>` 移到可回復的備份位置。
7. 原子性地以新目錄替換正式作品目錄。
8. Git commit、pull --rebase、push。
9. Git 失敗時回復舊目錄，並向使用者回報失敗。
10. 清除暫存與備份目錄。

解壓縮失敗必須拋出錯誤，不可只寫入 console 後繼續顯示「解壓完成」。

## 7. 聖誕活動的匿名邊界

匿名投稿只保證預覽 URL 不直接暴露投稿者：

- 使用短而隨機的 `participant_key` 作為網址路徑。
- Discord ID 與 `participant_key` 的對照只存在本機私密 JSON。
- 公開作品索引不可同時列出 `participant_key` 與 Discord 身分。
- 私密對照必須位於活動 repository 之外，並由 `.gitignore` 防止誤提交。

匿名投稿**不保證**以下資訊匿名：

- 作品內容中的簽名、文字或浮水印。
- 使用者提供的檔名與圖片 metadata。
- Git commit message 或 repository history。
- 管理員後台所保存的真實作者資料。

因此不需要為匿名投稿增加圖片重新編碼、檔名重寫或人工審核流程。這與匿名對話是不同的
需求：匿名對話仍須隱藏公開訊息作者，並在後台保存真實作者對照。

## 8. 黑名單與送禮配對

黑名單同時影響：

1. 匿名訊息：被封鎖者不能對設定者發起匿名互動。
2. 送禮配對：配對規則不得產生黑名單禁止的方向。

配對規則每次活動可能不同，因此核心只定義介面：

```python
class GiftMatchingPolicy(Protocol):
    def generate(
        self,
        participants: list[Participant],
        blocked_edges: set[tuple[str, str]],
        config: dict,
    ) -> list[GiftAssignment]: ...
```

活動設定以 `matching_policy` 指定規則名稱，實際函式由活動專用模組註冊。核心服務負責：

- 驗證所有參加者與輸出資料。
- 確認結果沒有違反 blacklist。
- 保存配對版本、產生時間與規則名稱。
- 防止無意間重抽並覆蓋已通知的結果。

核心不假設每人送幾份、是否互送，或 `/giftme` 應顯示哪些欄位；這些都是策略輸出的一部分。

## 9. 資料模型

### 9.1 公開活動設定

`<event_repo>/event-public.json`：

```json
{
  "schema_version": 1,
  "event_key": "2026-christmas",
  "display_name": "2026 Christmas Event",
  "event_type": "christmas",
  "timezone": "Asia/Taipei",
  "topics": [
    {"key": "gift", "name": "交換禮物"}
  ]
}
```

### 9.2 私密活動狀態

`./data/events/<event_key>/event-private.json`，位於活動 Git repository 之外：

```json
{
  "schema_version": 1,
  "event_key": "2026-christmas",
  "registration_channel_id": "1234567890",
  "registration_starts_at": "2026-11-01T00:00:00+08:00",
  "registration_ends_at": "2026-11-15T23:59:00+08:00",
  "submission_starts_at": "2026-11-16T00:00:00+08:00",
  "submission_ends_at": "2026-12-20T23:59:00+08:00",
  "matching_policy": "rules_2026",
  "participants": [
    {
      "discord_user_id": "1234567890",
      "participant_key": "k7m2q9",
      "joined_at": "2026-11-02T10:30:00+08:00"
    }
  ]
}
```

匿名訊息、黑名單與配對結果應拆成獨立檔案，避免每次更新其中一項時重寫整份活動資料：

```text
data/events/<event_key>/
  event-private.json
  anonymous-messages.json
  blacklist.json
  gift-assignments.json
```

JSON 寫入必須採「寫入暫存檔後原子替換」，並以活動層級的 async lock 防止同時報名、
退出或上傳造成遺失更新。

### 9.3 全域啟用活動

以 `data/active-event.json` 取代語意不清的 `RecentEvent.txt`：

```json
{
  "event_key": "2026-christmas"
}
```

啟用活動時必須先完整載入並驗證新設定，成功後才替換目前活動，避免新活動缺少設定時
沿用上一個活動的參加者與期限。

## 10. 模組規劃

```text
cmds/gitRely/
  event_cog.py                 # 唯一的 Discord Cog 與 slash commands
  models.py                    # Event、Participant、Topic、GiftAssignment
  event_service.py             # 活動生命週期、報名與退出
  submission_service.py        # 上傳、覆蓋、清除、預覽
  christmas_service.py         # 匿名訊息、黑名單、配對協調
  repositories.py              # 公開與私密 JSON repository
  storage.py                   # 安全路徑、暫存目錄、原子替換
  public_index.py              # 公開參加者／作品索引與排序
  publisher.py                 # 非同步 Git 發布
  matching/
    protocol.py                # GiftMatchingPolicy
    rules_2026.py              # 活動專用規則，另案實作
```

建議類別責任：

| 類別 | 責任 | 不應負責 |
|---|---|---|
| `EventCog` | Discord 參數、權限、defer、回覆 | JSON、檔案、Git |
| `EventService` | 啟用活動、生命週期、報名名單 | Discord API |
| `SubmissionService` | 每題一份、覆蓋交易、預覽 | Slash command |
| `ChristmasService` | 匿名對話、黑名單、配對策略協調 | 配對演算法細節 |
| `EventRepository` | 私密 JSON 的驗證與原子讀寫 | Git 發布 |
| `SubmissionStorage` | 安全解壓、路徑與目錄替換 | Discord 回覆 |
| `GitPublisher` | 序列化 commit/pull/push | 活動業務規則 |

耗時的解壓縮與 Git 操作必須使用 `asyncio.to_thread` 或工作佇列，不能阻塞
Discord event loop。同一活動的 Git 發布需序列化執行。

## 11. 命名規範

Python 內部統一使用 snake_case：

| 舊名稱 | 新名稱 |
|---|---|
| `class event` | `EventCog` |
| `eventName` | `event_key` 或 `display_name` |
| `registration` | `registration_channel_id` |
| `eventStart` | 移除，改用明確的報名／投稿開始時間 |
| `registrationEnd` | `registration_ends_at` |
| `uploadEnd` | `submission_ends_at` |
| `isTeamEvent` | 移除；沒有對應的既定行為 |
| `isNewParticipant` | `is_registered` |
| `set_event_name` | `activate_event` |
| `make_index` | `generate_gallery` |
| `hash_user_id` | 移除，改用隨機 `participant_key` |
| `clear` 方法 | `clear_submission` |

slash command 名稱維持不變；只有內部函式與資料欄位改名。

## 12. 錯誤與一致性要求

- 所有預期中的使用者錯誤使用 ephemeral 回覆。
- 所有 Git 結果都必須回報，不得忽略 `success`。
- 對需要 icon 的活動（例如 SummerEvent），報名後必須從 Discord 下載並發布參賽者 icon；下載失敗
  不應丟失報名資料，但必須可由管理員重新同步，直到公開活動頁的 icon 完整。
- 上傳成功必須代表檔案驗證、替換及 Git push 全部完成。
- `/clear` 必須可在 Git 失敗時回復原作品。
- JSON 格式錯誤時不得以空資料覆蓋原檔。
- 不使用裸 `except Exception` 吞掉錯誤；內部記錄完整 traceback，使用者只收到安全訊息。

## 13. 重構階段

目前不需要遷移已截止的舊活動資料。新架構可從下一個活動使用新 schema。

1. 建立 models、repository 與新的公開／私密資料邊界。
2. 合併為單一 `EventCog`，保留既有 slash command 名稱。
3. 實作一般活動的單題／多題統一投稿流程。
4. 實作覆蓋式、安全且可回復的上傳與 Git 發布。
5. 搬移聖誕匿名訊息與 blacklist，確保資料不進入公開 repository。
6. 定義 `GiftMatchingPolicy`，但不在本階段實作特定活動的配對函式。
7. 驗證匿名投稿網址不含身分，且公開資料不存在 `participant_key` 到 Discord ID 的對照。
8. 移除 `event.py`、`event_multi.py`、舊 `EventBase` 和無作用的 extension setup。

每一階段都應先有單元測試，再移除舊程式。至少需要覆蓋：活動切換不污染狀態、每題
最多一份、覆蓋失敗可回復、期限邊界、路徑穿越、身分對照與匿名訊息作者不進 Git，
以及同時上傳的序列化行為。
