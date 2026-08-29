# Event 指令文檔

目前實作由 `cmds/gitRely/event_cog.py` 提供唯一的 `EventCog`。活動設定與服務依
[活動系統目標架構](event_architecture.md) 分離；`event.py` 和 `event_multi.py` 只保留
相容入口，不應再同時載入。

## 載入方式

推薦載入套件入口：

```powershell
py .\bot2.py --token <TOKEN> --noBase --ext gitRely
```

也可以直接載入 `gitRely.event_cog`；兩者只能擇一。

## 共用指令

| 指令 | 參數 | 說明 |
|---|---|---|
| `/seteventname` | `event_name`、`event_type`、`timezone`、四個時間欄位、`topics` | 驗證並啟用唯一活動；時間接受 ISO datetime 或 `yyyymmdd-HHMM`。 |
| `/event` | `action=join/leave` | 在報名期間報名或退出；報名時產生隨機 `participant_key`。 |
| `/upload` | `file`、`title` 必填；`topic` 單題時可留空 | 安全解壓、建立預覽並完整覆蓋指定題目的作品；Git 發布失敗會回復舊版本。 |
| `/clear` | `topic` 單題時可留空 | 清除自己的指定題目作品；Git 發布失敗會回復舊版本。 |

## 額外指令（僅 `christmas` 活動）

| 指令 | 參數 | 說明 |
|---|---|---|
| `/blacklist` | `ids`（以空白分隔，可留空） | 設定黑名單；每次是完整覆蓋，不是追加。 |
| `/anonsay` | `content` | 匿名發言；作者只保存於私密資料。 |
| `/anonreply` | `message_id`、`content` | 匿名回覆指定訊息。 |
| `/giftshuffle` | 無 | 管理員依活動指定策略產生一次配對；已有結果時拒絕重抽。 |
| `/giftme` | 無 | 查看配對策略允許目前使用者看到的結果。 |

## 注意事項

1. `/upload` 是覆蓋指定題目的交易流程，不會與舊檔案疊加。
2. 私密資料位於 `data/events/<event_key>/`，不會寫入公開活動 repository。
3. `participant_key` 是報名時產生的隨機短碼，不可由 Discord ID 重算。
4. 使用者錯誤與配對結果使用 ephemeral 回覆；公開匿名訊息不包含作者。
