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
| `/seteventadmins` | `user_ids`（使用者 ID 或提及） | Bot 管理員設定當期主辦者白名單；其餘活動管理指令僅限名單成員。 |
| `/seteventchannels` | `discussion_channel` | 設定活動雜談區；報名修改、退出及恢復的狀態通知會發到這裡。 |
| `/setblacklistsettings` | `ends_at`、`max_entries`、`max_leaders`（選填） | 設定黑名單截止時間與每人上限；`max_leaders` 僅能用於組活。 |
| `/signup` | `action=join/edit/quit/restore` | `join` 開啟活動表單；`edit` 修改欄位並更新原報名留言；`quit` 保留原編號取消；`restore` 用原編號恢復。可在指定伺服器內任何文字頻道使用。 |
| `/event` | `action=join/edit/leave/restore` | `/signup` 的相容入口；`leave` 等同 `quit`。 |
| `/blacklist add` | `registration_number` | 私訊機器人，依報名編號加入黑名單。 |
| `/blacklist view` | 無 | 私訊機器人，查看黑名單編號與暱稱。 |
| `/blacklist remove` | `registration_number` | 私訊機器人，移除指定編號。 |
| `/sudo viewblacklist` | 無 | 主辦者私下查看全體黑名單。 |
| `/sudo addblacklist` | `owner_number`、`target_number` | 主辦者手動加入黑名單，可超過一般使用者上限。 |
| `/sudo removeblacklist` | `owner_number`、`target_number` | 編號為 0 時可批次清除；兩者不可同時為 0。 |
| `/sudo kick` | `registration_number` | 取消指定報名，沿用原編號並同步報名留言。 |
| `/sudo revertkick` | `registration_number` | 恢復已取消報名，沿用原編號並同步報名留言。 |
| `/upload` | `file`、`title`；`topic` 單題時可留空；`help=true` 顯示說明 | 投稿期間安全解壓、建立預覽並完整覆蓋指定題目的作品；Git 發布失敗會回復舊版本。 |
| `/uploadovertime` | `file`、`title`；`topic` 單題時可留空 | 投稿截止後上傳或更新作品；公開索引標記超時，Christmas 活動並通知雜談區。 |
| `/clear` | `topic` 單題時可留空 | 清除自己的指定題目作品；Git 發布失敗會回復舊版本。 |

管理員需先執行 `/setblacklistsettings`；截止後 `/blacklist add/view/remove` 都會拒絕操作。

## Christmas 指令群組（僅 `christmas` 活動）

Christmas 專用指令會集中在 `/christmas` 群組下：

| 指令 | 參數 | 說明 |
|---|---|---|
| `/christmas blacklist` | 舊指令，停用 | 相容入口，會提示改用頂層 `/blacklist` 操作。 |
| `/christmas anonsay` | `content` | 匿名發言；作者只保存於私密資料。 |
| `/christmas anonreply` | `message_id`、`content` | 匿名回覆指定訊息。 |
| `/christmas giftshuffle` | 無 | 管理員依活動指定策略產生一次配對；已有結果時拒絕重抽。 |
| `/christmas giftme` | 無 | 查看配對策略允許目前使用者看到的結果。 |

## 報名表單欄位

| 活動類型 | 必填欄位 | 選填欄位 |
|---|---|---|
| `submission` | 活動暱稱 | 備註 |
| `christmas` | 活動暱稱、AA 形象 | 備註 |
| `group` | 活動暱稱、AA 形象、是否報名組長（是／否） | 備註 |

Discord ID 由 Discord 自動取得。首次成功報名時發固定編號，公開報名留言送到活動設定時指定的報名頻道；再次使用 `edit` 時只填要修改的欄位、留白欄位保留原值，並修改原留言及在活動雜談區通知。取消時原留言和雜談區都會標示取消；恢復時原留言還原為完整報名表並通知雜談區。取消者不參與投稿與新配對名單，恢復時保留原編號。管理員須先執行 `/seteventchannels` 設定雜談區。

## 注意事項

1. `/upload` 是覆蓋指定題目的交易流程，不會與舊檔案疊加。
2. 私密資料位於 `data/events/<event_key>/`，不會寫入公開活動 repository。
3. `participant_key` 是報名時產生的隨機短碼，不可由 Discord ID 重算。
4. 使用者錯誤與配對結果使用 ephemeral 回覆；公開匿名訊息不包含作者。
