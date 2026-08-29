# Event 活動營運操作手冊

本手冊是目前 `gitRely` 的實際操作流程，適用於管理員、活動主辦者與維運人員。
架構細節請參考 [event_architecture.md](event_architecture.md)，指令參數請參考
[event_commands.md](event_commands.md)。

## 0. 目前功能範圍

目前已完成：

- 單一 `EventCog`，同一時間只啟用一個活動。
- `submission` 一般投稿活動，支援單題與多題。
- `christmas` 活動的報名、匿名訊息、匿名回覆與黑名單資料邊界。
- 隨機 `participant_key`、私密 JSON、安全解壓與覆蓋式投稿。
- Git 發布失敗時回復舊作品。

目前尚未完成：

- `rules_2026` 的實際送禮配對函式與註冊。Christmas 活動在此函式加入前，
  `/giftshuffle` 不能完成配對。
- 管理員專用的參加者編輯指令。需要修正名單時，請由維運人員依備份流程處理，
  不要直接在公開活動 repository 建立私密資料。

## 1. 活動目錄與資料邊界

從 repository 根目錄執行 Bot。每個活動的公開目錄必須是獨立的 Git clone，且已設定
可 push 的 remote：

```text
<workspace>/
  <event_key>/                    # 公開 Git repository
    event-public.json             # 由 Bot 建立或更新
    pieces/                        # 公開作品
  data/
    active-event.json              # 私密啟用指標，不 commit
    events/<event_key>/            # 私密活動資料，不 commit
      event-private.json
      anonymous-messages.json      # 使用後才會建立
      blacklist.json               # 使用後才會建立
      gift-assignments.json        # 配對後才會建立
  uploads/                         # 暫存上傳檔，不 commit
```

啟動前檢查：

- [ ] `python` 可以載入 `discord`。
- [ ] `data/`、`uploads/` 可寫入。
- [ ] 預計使用的 `<event_key>` 目錄是 Git repository：`git -C <event_key> status` 可執行。
- [ ] `<event_key>` 已設定正確 remote，且 Bot 執行帳號能 push。
- [ ] 公開 repository 工作樹乾淨；`GitPublisher` 會執行 `git add .`，不要把其他未完成變更留在裡面。
- [ ] `.gitignore` 包含 `data/active-event.json`、`data/events/` 與 `uploads/`。
- [ ] 已確認 `Asia/Taipei` 等 IANA timezone 名稱可用。
- [ ] 已備份 `data/events/`。私密資料不在公開 Git 歷史中，遺失後無法從 Pages 還原。

如果活動目錄尚未存在，`/seteventname` 會建立普通資料夾，但不會替你建立 Git remote；
因此必須先準備好 Git clone，否則投稿時 Git 發布會失敗。

## 2. 啟動 Bot

在 workspace 根目錄執行：

```powershell
py .\bot2.py --token <TOKEN> --noBase --ext gitRely
```

啟動檢查：

- [ ] Console 顯示 Bot 已登入。
- [ ] Discord slash command 同步完成。
- [ ] `/seteventname`、`/event`、`/upload`、`/clear` 出現在指令清單。
- [ ] 沒有同時載入 `gitRely.event`、`gitRely.event_multi` 或其他會註冊同名指令的 extension。

若只要直接載入 Cog，也可以使用 `--ext gitRely.event_cog`；兩者擇一即可。

## 3. 建立並啟用活動

由管理員在「活動報名頻道」執行 `/seteventname`。目前所有設定欄位都是必填：

```text
/seteventname
  event_name: 2026-spring
  event_type: submission
  timezone: Asia/Taipei
  registration_starts_at: 2026-09-01T00:00:00+08:00
  registration_ends_at: 2026-09-07T23:59:00+08:00
  submission_starts_at: 2026-09-08T00:00:00+08:00
  submission_ends_at: 2026-09-30T23:59:00+08:00
  topics: A題,B題
```

時間也接受 `yyyymmdd-HHMM`，但建議使用帶有 `+08:00` 的 ISO datetime，避免誤解時區。
`event_name`、topic key 等路徑識別值必須是安全的短字串；topic 的公開名稱可以使用中文。

執行成功後，系統會：

1. 驗證活動設定與四個時間欄位。
2. 寫入 `<event_key>/event-public.json`。
3. 寫入私密 `data/events/<event_key>/event-private.json`。
4. 原子更新 `data/active-event.json`。
5. 將執行指令的頻道記為 `registration_channel_id`。

啟用後在本機驗證：

```powershell
Get-Content .\data\active-event.json
Get-Content .\2026-spring\event-public.json
Get-Content .\data\events\2026-spring\event-private.json
```

檢查清單：

- [ ] `active-event.json` 的 `event_key` 正確。
- [ ] public JSON 沒有 Discord ID、participant key 對照或匿名作者資料。
- [ ] private JSON 的四個時間都有 timezone offset。
- [ ] `registration_channel_id` 是預期頻道。
- [ ] 活動目錄仍是有效 Git repository。

如果要重新啟用同一個已存在的活動，請用同一組完整設定再次執行 `/seteventname`。
系統會保留既有 participant 與同名 topic 的穩定 key；不要手動把上一個活動的 private JSON
複製到新 `event_key`。

## 4. 活動生命週期與操作權限

系統不保存額外的狀態欄位，而是用目前時間推導：

| 狀態 | 時間條件 | 參加者可做的事 |
|---|---|---|
| `scheduled` | 報名開始前 | 無 |
| `registration_open` | 報名開始後、報名截止前 | `/event join`、`/event leave` |
| `waiting_submission` | 報名截止後、投稿開始前 | 無 |
| `submission_open` | 投稿開始後、投稿截止前 | `/upload`、`/clear` |
| `closed` | 投稿截止後 | 查詢；不能上傳或清除 |

截止時間的瞬間即進入下一個狀態。例如目前時間等於 `submission_ends_at` 時，
`/upload` 與 `/clear` 都會被拒絕。

## 5. 報名階段 checklist

管理員在報名開始前：

- [ ] 在活動頻道公告報名開始與截止時間。
- [ ] 公告活動類型與 topic 名稱。
- [ ] 確認 Bot 正在執行且活動已啟用。

參加者操作：

```text
/event action:join
/event action:leave
```

注意：

- 必須在設定活動時使用的報名頻道執行。
- `/event join` 只能在 `registration_open` 使用。
- 回覆為 ephemeral，不會公開 `participant_key`。
- `participant_key` 只存在 private JSON 與作品路徑，不要貼到公開頻道。
- 報名截止後不能退出，避免影響後續配對或名單一致性。

管理員在報名結束後確認：

- [ ] private JSON 的 participants 數量符合預期。
- [ ] 每位參加者的 `discord_user_id` 與 `participant_key` 唯一。
- [ ] 已完成名單備份，再進入投稿階段。

## 6. 投稿階段 checklist

投稿前，主辦者確認：

- [ ] 目前已到 `submission_open`。
- [ ] 公開 Git repository 工作樹乾淨。
- [ ] Git remote 可 push。
- [ ] Pages host 已可服務該 repository。

參加者上傳：

```text
# 單題活動，topic 可留空
/upload file:<作品.zip> title:<作品標題>

# 多題活動
/upload file:<作品.zip> title:<作品標題> topic:<題目>
```

目前支援 `.zip`、`.rar`、`.7z`。部署環境必須同時具備對應的解壓套件；不確定時優先使用
`.zip`。系統限制包括：上傳檔案最多 100 MB、解壓後最多 100 MB、最多 500 個檔案。

壓縮檔安全要求：

- [ ] 不含絕對路徑。
- [ ] 不含 `..` 路徑穿越。
- [ ] 不含 symbolic link。
- [ ] 至少包含圖片或 `index.html`。
- [ ] 不要依賴上一版作品中的檔案；每次上傳是完整覆蓋。

系統流程：

1. 儲存到 UUID 暫存目錄。
2. 驗證並解壓到暫存目錄。
3. 建立或驗證 `index.html`。
4. 將 `<participant_key>/<topic_key>` 舊目錄移到可回復備份。
5. 以新目錄替換舊目錄。
6. 執行 Git `add`、`commit`、`pull --rebase`、`push`。
7. Git 成功後刪除備份；失敗則回復舊作品。

成功回覆的預覽網址格式：

```text
https://aafanclubdc.github.io/<event_key>/pieces/<participant_key>/<topic_key>/
```

主辦者驗收：

- [ ] Discord 回覆顯示上傳完成與預覽網址。
- [ ] Pages 可以開啟 `index.html`。
- [ ] 新作品內容完整，沒有殘留舊版本檔案。
- [ ] `git log` 有本次 commit，remote 已更新。

## 7. 清除作品

只能在 `submission_open` 執行：

```text
/clear topic:<題目>
```

單題活動可省略 `topic`。清除也會經過備份、目錄替換與 Git push；Git 失敗會回復作品。
投稿截止後即使作品存在，`/clear` 也會被拒絕。

## 8. Christmas 活動流程

建立活動時使用：

```text
/seteventname
  event_name: 2026-christmas
  event_type: christmas
  timezone: Asia/Taipei
  registration_starts_at: 2026-11-01T00:00:00+08:00
  registration_ends_at: 2026-11-15T23:59:00+08:00
  submission_starts_at: 2026-11-16T00:00:00+08:00
  submission_ends_at: 2026-12-20T23:59:00+08:00
  topics: 交換禮物
```

報名與投稿階段依一般流程執行。Christmas 額外指令：

```text
/anonsay content:<內容>
/anonreply message_id:<訊息 ID 或連結> content:<內容>
/blacklist ids:<以空白分隔的 Discord ID>
/giftshuffle
/giftme
```

操作規則：

- `/blacklist` 是完整覆蓋；傳入空白清單可清除自己的黑名單。
- 匿名作者、匿名訊息、黑名單與配對結果只寫入 private data。
- `/giftshuffle` 有既有結果時會拒絕重抽，避免覆蓋已通知的配對。
- 目前尚未註冊 `rules_2026` 配對策略，因此在配對策略完成前，`/giftshuffle` 預期會失敗；
  不要把失敗當成活動設定或參加者名單遺失。

## 9. 活動結束 checklist

投稿截止時不需要額外切換狀態；系統會依時間進入 `closed`：

- [ ] `/upload` 與 `/clear` 已被截止檢查拒絕。
- [ ] Pages 上的作品可正常瀏覽。
- [ ] 公開 repository 的最新 commit 已 push。
- [ ] 備份 `data/events/<event_key>/`。
- [ ] 備份 private JSON 時確認檔案權限與儲存位置安全。
- [ ] 不要把 `data/events/` 或 `data/active-event.json` 上傳到公開 repository。
- [ ] 活動結束後再考慮停止 Bot；停止不會刪除活動或私密資料。

## 10. 故障處理

### `/seteventname` 失敗

先檢查時間格式、時間先後、timezone、topic 是否為空，以及 `event_key` 是否含有路徑字元。
啟用指標只有在完整設定驗證成功後才會更新；不要用上一個活動的 private JSON 補檔。

### 上傳顯示 Git 發布失敗

1. 確認活動目錄是 Git clone。
2. 執行 `git -C <event_key> remote -v` 確認 remote。
3. 執行 `git -C <event_key> status` 確認沒有其他未提交變更。
4. 確認 Bot 執行身份具有 push 權限。
5. 確認 pull/rebase 沒有被遠端衝突阻擋。
6. 確認本機作品目錄仍是舊版本，再重新上傳。

Git 失敗時服務會嘗試回復舊目錄；若人工檢查發現新舊版本不一致，先停止重試並備份整個
活動目錄與 `data/events/<event_key>/`，再由維運人員處理。

### JSON 格式錯誤

- 不要以空 JSON 覆蓋原檔。
- 先複製損壞檔案與整個 `data/events/<event_key>/` 作為事故備份。
- 從最近一次受信任的私密備份恢復，確認 `event_key`、時間與 participants 後再啟動 Bot。
- 如果是 `active-event.json` 損壞，只有在確認目標活動的 public/private JSON 都完整後，才重新執行
  `/seteventname` 啟用活動。

### 看不到 slash command 或出現重複指令

- 確認只載入 `gitRely` 或 `gitRely.event_cog` 其中一個。
- 不要同時載入舊的 `gitRely.event` 與 `gitRely.event_multi`。
- 重啟 Bot 等待 slash command sync 完成。

## 11. 每次活動結案紀錄

每場活動結束後保存以下資訊，供下次營運與事故追蹤：

- 活動 key、活動類型、timezone、四個時間欄位。
- 報名頻道 ID 與參加者數量。
- 公開 repository 最後 commit SHA。
- Pages 預覽網址與抽查結果。
- private data 備份位置與備份時間。
- Git 發布失敗、回復或人工介入紀錄。
