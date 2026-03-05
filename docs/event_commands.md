# Event 指令文檔

本文件整理 `cmds/gitRely/event.py` 與 `cmds/gitRely/event_multi.py` 的斜線指令。

## 載入方式

只建議同時載入其中一個模組，因為兩者有多個同名指令（如 `/event`、`/upload`）。

```powershell
# 單題版（含匿名與送禮功能）
py .\bot2.py --token <TOKEN> --noBase --ext gitRely.event

# 多題版（upload/clear 需題目）
py .\bot2.py --token <TOKEN> --noBase --ext gitRely.event_multi
```

## 共用指令

| 指令 | 參數 | 說明 |
|---|---|---|
| `/seteventname` | `event_name` 必填；`start_time`、`registration_deadline`、`upload_deadline`、`is_team_event`、`topics` 選填 | 設定活動名稱與設定值，會更新 `RecentEvent.txt` 與 `eventInfo.json`。 |
| `/event` | `action=join/leave` | 報名或退出活動。 |
| `/upload` | `title` 必填；其餘依模式不同 | 上傳壓縮檔（`.zip/.rar/.7z`），解壓後發布預覽連結。現在是追加模式，不會先清空資料夾。 |
| `/clear` | 依模式不同 | 清空自己的作品資料夾。 |

## `event.py`（單題版）

### upload/clear 路徑

- `/upload` 路徑：`<event>/pieces/<user_hash>/`
- `/clear` 路徑：`<event>/pieces/<user_hash>/`

### 額外指令

| 指令 | 參數 | 說明 |
|---|---|---|
| `/blacklist` | `ids`（以空白分隔） | 寫入黑名單資料。 |
| `/blacklist` | `ids`（以空白分隔） | 寫入黑名單資料。 |
| `/anonsay` | `content` | 匿名發言。 |
| `/anonreply` | `message_id`、`content` | 匿名回覆指定訊息。 |
| `/giftshuffle` | 無 | 管理員整理隱藏送禮配對。 |
| `/giftme` | 無 | 查看自己的送禮對象與送你的人。 |

## `event_multi.py`（多題版）

### topics 設定

`/seteventname` 的 `topics` 參數用逗號分隔，例如：`A題,B題,C題`。

### upload/clear 路徑

- `/upload topic:<題目>` 路徑：`<event>/pieces/<user_hash>/<topic>/`
- `/clear topic:<題目>` 路徑：`<event>/pieces/<user_hash>/<topic>/`

`topic` 會用 autocomplete（來自 `topics` 清單）並做名稱正規化（去除 `/`、`\`、`..`）。

### 額外指令

| 指令 | 參數 | 說明 |
|---|---|---|
| `/blacklist` | `ids`（以空白分隔） | 寫入黑名單資料。 |


## 錯誤提示顯示

目前 `event_multi.py` 內多數錯誤提示是 ephemeral，只有操作者看得到。

## 注意事項

1. `upload` 是「追加」不是覆蓋，舊檔案會保留。
2. 要清空資料請用 `/clear`。
3. `seteventname`、`event`、`upload` 等同名指令在兩個模組都有，避免同時載入。
