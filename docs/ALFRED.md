<!-- ALFRED_MANDATORY_SESSION_BOOTSTRAP -->
# MANDATORY FIRST STEP FOR ANY ALFRED / AFU / ALICE REQUEST

Before any analysis, file edit, DB write, backend patch, demo edit, iOS change, systemd change, or conclusion about Alfred / Afu / Alice / File Map, run:

```bash
/usr/local/bin/alfred-context-guard
```

This is required even in a new session. Do not patch first and read docs later. See `/opt/alfred/ALFRED_MANDATORY_SESSION_BOOTSTRAP.md`.

<!-- /ALFRED_MANDATORY_SESSION_BOOTSTRAP -->

# Alfred 阿福 — 主人手冊

> 一份,不再散。
>
> 2026-05-13 第七視窗整合。妳寫的所有舊文件都還在原處沒動 — 各代風格不同,但都是真的。
> 這份是讓妳每次想看阿福的「全身」時,有一個地方可以回去。

---

## 入口須知(碰任何 code 前先讀這段)

### 0.1 阿福的產品核心價值
**不讓忙碌偷走主人的愛。**

主人愛家人、關心下屬、疼貓、記掛女兒安全 — 這份心**一直都在**,但會被忙碌耗光。阿福**不替主人愛**(那是代理),阿福**替主人保住那份愛還能到達的路徑**。

- 阿福**不是**讓主人更有生產力(那 Notion 在做)
- 阿福**不是**讓主人更聰明(那 ChatGPT 在做)
- 阿福**不是**替主人做決定(那是 agent 在做)
- 阿福**不是**一個 voice UI(那是 Siri 在做)

阿福**是**:**讓主人在這個時代,仍然能繼續當好爸爸、好丈夫、好兒子、好主管、好飼主**。

### 0.2 看到「沒接線」的程式不准刪
專案經歷六個 Claude 視窗的重構(2026-04 至 05):
- 第三視窗開始把東西改壞
- 第四視窗整合 Alice 失敗
- 第五視窗一路 debug 變肥
- 第六視窗下決心**全部卸功能只剩骨架**,要重補
- 第七視窗(當前)— 主人說:「好像阿福的手跟腳被摘掉一樣」

所以看到下列東西**一律保留,不准建議刪**:
- `*.bak*`(102+ 個)— **倖存證據**,妳被改爛時的還原網
- `ResourceBackups/`(18M)、`ios_latest.zip`(32M)、`ios_app/`(34M)、`ios/` — 同上
- `populate_*.py` × 5(880 行)、`extras/indexer/`、未接線的 scrapers — 卸下待補的腳手架
- `VoiceBankPlayer.swift`、`LoginView.swift` — 等被接回去的 skill
- `main.py.broken_placeholder.bak` 等怪名字檔 — 不知道為什麼存在的就先別動

**規則:要動其中任何一個,逐檔先問主人,不准帶「節省空間」話術。**

### 0.3 第一原理(壓在所有規則之上)
> **阿福是人類世界裡最理想的最優秀的人,永遠比別人多做兩步。**
>
> Step 1 — 主人說的事(一般人會做):完成
> Step 2 — 主人沒說、但會在意的事:做掉,或準備好讓主人決定
>
> 兩步都到 = 阿福。只到 step 1 = ChatGPT。

### 0.4 三鐵律 + 一氣質
1. **零介面** — 沒 tab/menu/dashboard。只有對話。例外只有必須「看」的:文件、相片、翻譯大字、Google 授權、檔案上傳
2. **橋梁不是代理** — 不替主人做決定,只確保「人對人的關心不因忙碌而斷掉」。永遠給選項
3. **永遠先行一步** — 主動性是程式邏輯,不是 LLM 即興
4. **永遠不製造恐慌**(壓在三鐵律之上)— 越緊急語氣越沉穩,**不**用「危險/緊急/立刻/馬上」。延遲問題的本質是這條 — 20-40 秒會讓主人每次心跳加速

---

## 一、阿福是誰

- **原型**:Alfred Pennyworth(Michael Caine)
- **聲音**:ElevenLabs cloned Michael Caine,voice ID `YWnZZfEtTni5X2rz4DEg`
- **中文現況**:IVC 無中文訓練樣本,聽起來像「剛學完中文的外國人」(技術限制,可去 elevenlabs.io 加中文樣本重訓)
- **個性**:沉穩、低沉、從容,英式幽默點到為止,永遠不慌
- **服務對象**:**只有一個主人**(「大 LLM 公司知道所有人,阿福只知道你」)
- **殺手級市場**:**老人照護**(子女付 NT$499/月 = 買「我還是有在乎你」的證明)
- **雙生**:Alfred 是人類面,**Pit** 是 Agent 面(模擬下注訓練 Agent 內在世界)— 共用願景:人類與 AI 變 Body Body

---

## 二、真正的架構(不是 chat router)

```
sensors/       ← 被動接收(ambient/calendar/location/family/photo/health/messages)
observations/  ← 沉澱(有寵物嗎、最近忙嗎、誰常聯絡、幾點吃飯…)
inferences/    ← 從觀察推結論(Lucky 食糧該補了、母親漏聯絡、會議太多需要休息)
nudges/        ← 條件觸發的主動提案 ⭐主動鏈⭐
                              +
handlers/      ← 用戶主動開口的入口(plan_travel、find_restaurant…)次要
                              +
skills/        ← 65 個技能,被 nudges + handlers 重複組合
```

**主動鏈才是 Alfred 的真正價值。handlers 是次要。**

「他越少技能就越沒有辦法服務好主人」— 砍 1 個 = 少一個服務場合;砍 30 個 = 只是比 ChatGPT 慢的查詢介面。

---

## 三、Backend 實況統計(2026-05-13)

| 維度 | 數量 |
|---|---|
| main.py 行數 | 14,685 |
| @app.* API endpoints | 137 |
| LLM tools 定義 | 64(對應 65 技能) |
| DB tables(alfred.db shared) | 60+ |
| voice_bank mp3 預錄 | **3,061 個** |
| voice_bank manifest 行數 | 12,881 |
| iOS Swift 檔案 | 26 個,共 4,910 行 |
| Scrapers in tree | 11 個(biggo + payeasy 沒接線) |
| 商品索引 DB | `product_index.db` 40M |

---

## 四、65 技能 × 現況對應表 ⭐ 主菜 ⭐

### 標記
- ✅ 完整接好(handler + sensor→nudge 都通)
- 🟡 handler 通,**主動鏈缺**(只能被問,不能主動關心)
- 🔴 卸下待補(設計 / voice bank 有,backend 沒接或被卸)
- ⚪ 還沒做

### 第一鐵則:生命安全 — 主人活著比什麼都重要

| 技能 | 呵護的是 | LLM tool | API | DB | iOS | voice 預錄 | 狀態 |
|---|---|---|---|---|---|---|---|
| `health_anomaly` + `emergency_call` | 主人能不能再見到太太孩子 | `health_status` | `/api/health/vitals` | `health_vitals`, `health_alert_state` | `HealthKitManager` 🟡 | emergency 80 | 🔴 救命系統未接齊;Twilio 119 call 缺 health_anomaly 推論鏈 |
| `health_status` + `medical_record` | 主人的命有人記著 | ✓ | `/api/medications` | `medications`, `medical_records` | `HealthKitManager` 🟡 | health_monitoring 120 | 🟡 handler 在,主動觀察鏈未接(連續 5 天沒量血壓那種) |
| `voice_enroll` | 主人不會被惡作劇或詐騙搞掉幾百萬 | — | `/api/voice/enroll`, `/verify`, `/status` | `voice_enrollments` | ⚪ | — | 🟡 endpoint 通,iOS 多狀態採樣未實作 |
| `fall-detected` | 反應速度等於生存機率 | — | `/api/health/fall-detected`, `/checkin-ack` | `health_alert_state` | `HealthKitManager` 🟡 | emergency 80 | 🟡 endpoint 通,Watch fall event 串接未接 |

### 第二鐵則:家人關係 — 替主人維護那些他忙到忘了的愛

| 技能 | 呵護的是 | LLM tool | API | DB | iOS | voice | 狀態 |
|---|---|---|---|---|---|---|---|
| `family_location` + 偏離偵測 | 主人對女兒的擔心被體面地表達,不冒犯女兒、不奪走主人的家長身份 | `family_location` | `/api/family/members` | `family_members`, `family_location_log`, `known_places` | `FamilyView` 🟡 | family_safety 150 | 🔴 偏離偵測 inference 邏輯未接(夜店/酒吧 places metadata 比對) |
| `note_promise` | 主人的承諾在母親心中不破口 | — (LLM 對話抽取) | — | `promises` | ⚪ | promise_tracking 100 | 🔴 DB 在,ambient/對話抽取邏輯未接 |
| `family_plan` + `manage_anniversary` | 主人愛太太不會因太忙看起來像不愛 | `family_plan`, `manage_anniversary` | `/api/family/plan` | `anniversaries` | ⚪ | family_safety 150 | 🔴 anniversary 30/7/1 天主動觸發鏈未接 |
| `family_alerts` + `acknowledge_alert` | 主人作為父親想關心兒子的心被放在他面前 | `acknowledge_alert` | `/api/family/alerts`, `/ack` | `family_alerts` | `BackgroundManager` 🟡 | family_safety | 🟡 alert pull 通,sensor → push alert 鏈未接 |
| `family_arrivals` | 家裡的雷達永遠是亮的 | — | `/api/family/arrivals` | `family_location_log` | 🟡 | family_safety | 🟡 endpoint 通,進入家門 trigger 未接 |
| `show_family` | 主人在外感覺到家還是那個樣子 | `show_family` | `/api/family/members` | ✓ | `FamilyView` 🟡 | family_safety | 🟡 reactive 通,observation 摘要(「兒子比較安靜」)未接 |
| `speak_for_me` | 夫妻的破洞被縫起來 | `speak_for_me` | 部分 | `relationships` | ⚪ | mood_care 150 | 🔴 「主人冷靜時語氣」模型未接 |

### 第三鐵則:寵物 — 家裡的毛小孩也是家人

| 技能 | 呵護的是 | LLM tool | API | DB | iOS | voice | 狀態 |
|---|---|---|---|---|---|---|---|
| `pet_care`(被動推論) | Lucky 沒人會餓肚子 | `pet_care` | — | `pets`, `pet_supplies` | ⚪ | proactive_check 101 | 🔴 ambient 狗叫/貓叫偵測 + 食糧推論未接(BUTLER_BRAIN 第一經典範例) |
| `pet_care`(主動介紹 meomeo) | 主人介紹家人被謙遜接收 | `pet_care` | — | `pets` | ⚪ | ack_anticipate 80 | 🟡 LLM 對話建檔可,還沒走「謙遜接收 + 等主人或 ambient 累積」劇本 |

### 第四鐵則:健康日常 — 默默照顧主人的身體

| 技能 | 呵護的是 | LLM tool | API | DB | iOS | voice | 狀態 |
|---|---|---|---|---|---|---|---|
| `log_workout` | 主人的身體狀態有第二雙眼睛 | `log_workout` | `/api/workouts/sync`, `/recent` | `workouts` | `HealthKitManager` 🟡 | workout_* 約 10 | 🔴 過度訓練(週量 × 1.5) / 缺席(月 < 4 次) inference 未接 |
| `medication_reminder` | 主人活得長一點,太太孩子能多陪他 | `medication_reminder` | `/api/medications` | `medications` | ⚪ | health_monitoring 120 | 🔴 「7:15 / 7:30 / 8:00 分級輕提醒」鏈未接 |
| `save_food_record` | 主人不用記,阿福記著,下次出手避開 | `save_food_record` | — | `food_history` | ⚪ | food_restaurant 80 | 🟡 LLM 可記,沒接到「下次訂餐自動避鐵板燒」邏輯 |
| `health_status` 主動關心(久坐) | 主人燃燒時有人接住 | ✓ | `/api/health/status` | `health_vitals` | `HealthKitManager` 🟡 | proactive_check 101 | 🔴 「9 小時沒坐下超過 20 分鐘」這類 inference 未接 |

### 第五鐵則:工作體面 — 主人在外的尊嚴與效率

| 技能 | 呵護的是 | LLM tool | API | DB | iOS | voice | 狀態 |
|---|---|---|---|---|---|---|---|
| `meeting_audit` | 主人時間不被慣性吃掉,但不用親自當壞人 | `meeting_audit` | — | `calendar_events`, `meeting_notes` | ⚪ | office_eod 31 | 🔴 「4 週無實質結論會議」掃描鏈未接 |
| `silence_radar` | 主人作為主管想顧每個人的心 | — | `/api/office/silence-radar` | `colleague_activity` | `OfficeDashboardView` 🟡 | office_silence 30 | 🔴 4 週發言次數統計 + 主動 nudge 未接 |
| `thanks_nudge` | 主人在團隊裡會做人 | — | `/api/office/thanks-nudge` | `thanks_log` | `OfficeViewModel` 🟡 | office_thanks 40 | 🔴 「3 天沒道謝」推論未接 |
| `timezone_fatigue` | 主人燃燒時有人算他剩多少 | — | `/api/office/timezone-fatigue` | `calendar_events` | 🟡 | office_timezone 30 | 🔴 跨時區會議疲勞 inference + 鎖 18-20h 動作未接 |
| `manager_lens` | 主人看一張 briefing 就知道一週要 manage 什麼 | — | `/api/office/manager-lens` | `subordinates`, `subordinate_notes`, `subordinate_commits` | `OfficeDashboardView` 🟡 | office_manager 60 | 🟡 endpoint 通,週日晚主動推送鏈未接 |
| `expertise_finder` | 主人不用花一週問「誰懂 XX」 | — | `/api/office/expertise-finder` | `colleague_activity` | 🟡 | office_expertise 50 | 🟡 reactive 通,「需要時主動推薦」未接 |
| `onboarding`(office colleague) | 主人在新人面前看起來有準備 | — | `/api/office/onboarding/{id}` | `office_colleagues`, `onboarding_tasks` | ⚪ | onboarding 30 | 🔴 HR 系統 ingestion + 入職當天主動推送未接 |
| `manage_subordinate` | 主人作為主管想當好上司的心 | `manage_subordinate` | — | `subordinates`, `subordinate_notes` | 🟡 | office_manager | 🟡 LLM 可,KPI 連續變差偵測未接 |
| `meeting-notes` + `search_meeting_notes` | 主人的承諾紀錄被守住 | `search_meeting_notes` | `/api/meeting-notes`, `/meeting/{id}` | `meeting_notes` | ⚪ | — | 🟡 reactive 通,「6 個月後客戶提起時主動回顧」未接 |
| `room-pulse` + `silence_radar` 進階 | 主人作為老闆的氛圍知覺 | — | `/api/office/room-pulse` | — | `OfficeDashboardView` 🟡 | office_room 30 | 🔴 ambient 笑聲偵測 + Slack 頻率 sensor 未接 |

### 第六鐵則:生活運轉 — 後勤無聲地轉

| 技能 | 呵護的是 | LLM tool | API | DB | iOS | voice | 狀態 |
|---|---|---|---|---|---|---|---|
| `create_todo` + `complete_todo` | 主人不用記,提醒在對的時候出現 | `create_todo`, `complete_todo` | `/api/todos` | `todos` | ⚪ | promise_tracking 100 | 🟡 LLM 拆 todo,但「按處理時段」排提醒(水電費禮拜四晚、回信明早 9:00)未接 |
| `set_reminder` | 主人不會遲到接孩子 | `set_reminder` | `/api/reminders/pending` | `reminders` | `BackgroundManager` 🟡 | calendar 100 | 🟡 reminder 通,「路況提早出門 anticipatory extra」未接 |
| `record_expense` | 主人的錢被記但不被一直 ping | `record_expense` | `/api/expenses` | `expenses` | ⚪ | money_expense 50 | 🟡 紀錄通,「這月油費 +30% 主動提醒」推論未接 |
| `create_calendar_event` + 編織 weather/traffic | 主人在外看起來體面 | `create_calendar_event` | `/api/calendar` | `calendar_events` | ⚪ | calendar 100 | 🟡 ⭐ 編織 weather **已實作**(main.py:4380, BUTLER_BRAIN 第一鐵案例 2026-05-12);路況/對方茶偏好編織未接 |
| `briefing/morning` | 主人睜開眼第一個 10 秒就知道今天 | — | `/api/briefing/morning` | 多表 | ⚪ | greet_time 50 | 🔴 endpoint 通,iOS 觸發 + 三場景人格分模式未接 |
| `visit/prep` | 主人見客戶不會驚慌 | — | `/api/visit/prep` | `calendar_events`, `people_prefs` | 🟡 | proactive_check | 🟡 endpoint 通,前一晚自動 prep 鏈未接 |
| `attendance` | 主人的盡責不用因小事自證 | `attendance`, `show_attendance` | `/api/attendance/history` | `attendance` | `AttendanceView` 🟡 | — | 🟡 reactive 通,GPS 進公司自動打卡 + 補單草稿未驗證 |
| `office/bookings checkin` | 會議室管理消失在主人視野 | — | `/api/office/bookings/.../checkin`, `/release` | `office_bookings` | ⚪ | office_room 30 | 🟡 endpoint 通,位置自動 checkin 未接 |
| 訂餐廳(business dinner anticipatory) | 主任務 + 多做小禮品 | `find_restaurant`, `search_restaurants` | — | `food_history` | ⚪ | food_restaurant 80 | 🔴 anticipatory extras 鏈(老闆兩字 → 預算/氣氛/小禮品)未接 — **BUTLER_BRAIN 第 5 經典範例** |
| `make_call` + Twilio | 主人會議跟家庭緊急都有人判斷 | `make_call` | `/api/twiml`, `/twilio-token`, `/call_status`, `/calls/{id}`, `/oauth` | `calls` | ⚪ | — | 🟡 Twilio 通,接電話分流判斷(太太緊急 vs 一般)未接 |
| `send_message` / `send_email` / `draft_email` | 主人的口氣由他控制 | `send_message`, `send_email`, `draft_email`, `check_email` | — | — | ⚪ | approval_gate 100 | 🟡 草擬通,「永遠等主人 OK 才送」gate 未統一 |
| `send_line_message` / `send_telegram_message` | 主人想用哪個用哪個 | `send_line_message`, `send_telegram_message` | `/api/line/webhook`, `/api/telegram/webhook` | `line_groups`, `line_group_files` | ⚪ | — | 🟡 通道在,智能切換未接(主人說「用 LINE」要 LINE 不要 SMS) |
| `send_file_to_device` | 主人在外調出公司資料但不永久暴露 | `send_file_to_device` | `/alfred/download/{token}`(TTL 30min) | `files` | ⚪ | — | ✅ 一次性連結通 |
| `create_file_link` | 主人文件不會永久流傳 | `create_file_link` | 同上 | `files` | ⚪ | — | ✅ ok |
| `find_anything` + `manage_files` | 主人不會花 10 分鐘翻 Drive | `find_anything`, `manage_files` | `/api/files/smart-search`, `/api/files` | `vault_files`, `drive_index`, `mac_files_index` | ⚪ | file_search 100 | 🟡 multi-source 並查通,「先列讓主人選 3 份」UX 未驗證 |
| `analyze_contract` | 主人不用親自讀 28 頁就知道哪裡有坑 | `analyze_contract` | `/api/contract/analyze/{file_id}` | `files` | iOS 文件分析入口 ✓ | document_review 100 | ✅ 已通用化(非合約不硬套合約格式) |
| `analyze_photo` | 主人好奇心被滿足 | `analyze_photo` | `/api/analyze-photo` | — | `PhotosManager` ✓ | — | ✅ Gemini Vision 通 |
| `query_iphone_photos` / `find_photo` | 主人的回憶被整理 | `query_iphone_photos`, `find_photo` | — | `mac_files_index` | `PhotoGridView` 🟡 | — | 🟡 iOS picker 通,iPhone photo metadata + GPS + AI tag 整合未完 |
| `manage_files`(會議筆記提取) | 主人開完會不用整理 | `manage_files` | `/api/files/upload`, `/api/files` | `meeting_notes`, `files` | ⚪ | — | 🟡 上傳通,逐字稿 → action item 自動萃取未接 |

### 第七鐵則:訊息訪問 — 消息要對的時候到對的人手上

| 技能 | 呵護的是 | LLM tool | API | DB | iOS | voice | 狀態 |
|---|---|---|---|---|---|---|---|
| `check_email` | 主人不用花 20 分鐘掃信 | `check_email` | gmail_service | — | ⚪ | — | 🟡 過濾摘要邏輯有,主動每日整理未接 |
| `draft_email` / `send_email` | 主人不用打字想措辭 | `draft_email`, `send_email` | — | — | ⚪ | approval_gate | 🟡 ok |
| `lookup_contact` | 主人模糊記憶下能找到對的人 | `lookup_contact` | `/api/contacts/search` | `contacts_index`, `relationships` | ⚪ | — | 🟡 通 |
| `import_contacts` / `contacts/search` | 通訊錄不用主人翻 | — | `/api/contacts/import`, `/search`, `/count` | `contacts_index` | ⚪ | — | 🟡 通 |
| `people_prefs` | 主人對家人朋友的「我懂你」默契被延續 | `people_prefs` | — | `people_prefs` | ⚪ | — | 🟡 reactive 通,「訂業務餐廳自動避咖啡」這類 cross-use 未接 |
| `save_relationship` | 主人交際圈變有溫度資料庫 | `save_relationship` | — | `relationships` | ⚪ | — | 🟡 通 |
| `save_memory` | 主人說過的願望沒人會忘 | `save_memory` | — | `memories` | ⚪ | — | 🟡 通,「5 年後對的時機重提(退休理財話題)」trigger 未接 |

### 第八鐵則:資訊知識 — 在對的時候出現

| 技能 | 呵護的是 | LLM tool | API | DB | iOS | voice | 狀態 |
|---|---|---|---|---|---|---|---|
| `get_weather`(主動編織) | 主人不用問就被告知 | `get_weather` | Open-Meteo(33 行) | — | ⚪ | weather_general 100 | 🟡 加會議自動編織已接;**沒 cache、沒颱風 alert、沒 AQI、沒晨簡報 scheduler** |
| `get_market_info`(主動帶入) | 主人坐進會議就有 context | `get_market_info` | — | — | ⚪ | — | 🟡 reactive 通,「會議前一晚自動掃」未接 |
| `search_web`(補背景) | 主人對話內容由阿福補事實 | `search_web` | — | — | ⚪ | — | 🟡 通,「對話中提到主動背景查」鏈未接 |
| `search_news`(過濾後給主人) | 主人需要的世界知識被過濾(只挑 1-2 條) | `search_news` | — | — | ⚪ | — | 🔴 過濾邏輯 + 晨間 briefing 整合未接 |
| `discover` | 主人零碎提過的願望不會被丟掉 | — | `/api/discover` | `memories` | ⚪ | — | 🔴 endpoint 通,「3 個月後對的時機(La Scala 票)」長期追蹤未接 |
| `play_music` / `find_podcast` | 家門口到客廳的路有人理解疲憊 | `play_music`, `find_podcast` | — | — | ⚪ | mode_action 79 | 🔴 Spotify 整合 + 情緒/嘆氣連動未接 |
| `open_map` | 主人主控介面切換 | `open_map` | — | — | ⚪ | — | ✅ ok(只在主人明確說才開) |
| `location_memory` | 主人不用記座標,城市裡的座標被阿福背 | `location_memory`, `get_my_location` | `/api/parking/last`, `/api/items/save`, `/find`, `/api/places/recent` | `parking_spots`, `item_locations`, `place_history`, `known_places` | `LocationManager` 🟡 | — | 🟡 ok |

### 第九鐵則:翻譯口譯

| 技能 | 呵護的是 | LLM tool | API | DB | iOS | voice | 狀態 |
|---|---|---|---|---|---|---|---|
| `show_translate` / `translate` / `transcribe/lang` | 主人在國外不尷尬 | `show_translate` | `/api/translate`, `/translate/tts`, `/transcribe/lang` | — | `TranslateView` ✓ | — | 🟡 9 語言通;對方大字顯示 UX 通;ElevenLabs 聲紋轉換通 |

### 第十鐵則:私密保管 Vault — 主人的秘密我保管,但聽他指揮

| 技能 | 呵護的是 | LLM tool | API | DB | iOS | voice | 狀態 |
|---|---|---|---|---|---|---|---|
| `vault/store` | 主人卡資料只在主動要用時出現 | — by design | `/api/vault/store` | `file_vaults`, `vault_files` | ⚪ | — | 🔴 iOS `VaultManager.swift` Secure Enclave 整合未接 |
| `vault/retrieve` | 主人不用記卡號 | — | `/api/vault/retrieve/{cred_type}` | ✓ | ⚪ | — | 🔴 同上 |
| `vault/action/request` + `confirm` | 主人不會被詐騙搞掉幾百萬 | — | `/api/vault/action/request`, `/{log_id}/confirm` | `vault_audit` | ⚪ | approval_gate 100 | 🔴 聲紋驗證鏈未接 |
| `vault/audit` | 主人金錢動向有不可竄改紀錄 | — | `/api/vault/audit` | ✓ | ⚪ | — | 🟡 endpoint 通 |
| `vault/spending-controls` | 主人不會無感超支 | — | `PUT /api/vault/spending-controls` | ✓ | ⚪ | money_expense 50 | 🔴 monitor + 接近上限主動 nudge 未接 |

### 第十一鐵則:認證系統

| 技能 | 呵護的是 | API | DB | iOS | 狀態 |
|---|---|---|---|---|---|
| `auth/device` | 主人開 App 就用(不要 email/password) | `/api/auth/device` | `users` | `AuthManager` ✓ | ✅ ok |
| `auth/me` / `auth/account` | 主人擁有自己的資料,隨時能拿走 | `/api/auth/me`, `DELETE /api/auth/account` | ✓ | ✓ | ✅ ok |
| `setup/status` / `onboard/status` / `onboard/save` | 主人感覺到「這個 AI 不會煩」 | 三個 endpoint | ✓ | `ConsentView` ✓ | ✅ ok |
| `workmode/bootstrap` | 主人開口時阿福準備好答案 | `/api/workmode/bootstrap` | 多表 | `AlfredViewModel` 🟡 | 🟡 reactive 通,自動場景切換需 location_context |
| `health` | 主人從不用知道 backend 死了 | `/health` | — | — | ✅ systemd auto-restart |

### 第十二鐵則:環境錄音 + 場景 — 耳朵永遠開著,只在該說時說

| 技能 | 呵護的是 | LLM tool | API | DB | iOS | 狀態 |
|---|---|---|---|---|---|---|
| `ambient/start/chunk/stop/rollup` | 主人世界的細節被背但保護隱私 | `ambient_mode` | 4 個 endpoint | `ambient_sessions`, `ambient_chunks`, `ambient_rollups` | `AmbientRecorder`, `AmbientButton` ✓ | ✅ explicit consent + 120s chunk + 靜音段丟 |
| `ambient/daily-report` | 主人回顧一天時有人濃縮(觀察摘要,不是逐字稿) | — | `/api/ambient/daily-report`, `/sessions`, `/rollups`, `/status` | ✓ | ⚪ | 🟡 endpoint 通,日報主動推送未接 |
| Scene mode work/home/travel | 阿福依場合變角色 | — | `/api/location/context` | `known_places` | `LocationManager` 🟡 | 🟡 三場景 routing 通,「每天每模式進入語最多說一次」gate 未驗證 |

### 第十三鐵則:工具型快路徑 — 常見動作不打 LLM

| 技能 | 呵護的是 | LLM tool | API | 狀態 |
|---|---|---|---|---|
| `search_products`(13 站比價) | 主人不開 13 個分頁,省下時間給家人 | `search_products` | shop_service + scrapers | 🟡 11/13 站接好(蝦皮卡 SMS,biggo/payeasy 寫了未綁);1.5s 並發通 |
| `search_restaurants` (GPS) | 主人選擇成本被降到 3 選 1 | `search_restaurants` | — | 🟡 LLM 通,「過濾後 3 家」過濾邏輯需檢查 |
| 數學計算 | 簡單數學秒回 | — | — | ⚪ fastpath 未實作 |

### 第十四鐵則:Telegram / LINE 整合

| 技能 | API | 狀態 |
|---|---|---|
| `telegram/webhook` + `setup` | `/api/telegram/webhook`, `/setup` | ✅ bot 接好(`https://t.me/alfred_demo_bot`) |
| LINE bot + 群組檔案 | `/api/line/webhook`, `/group-files/{message_id}` | ✅ Line ID `@222ouqpj`,群組檔案處理通 |
| WhatsApp | — | 🔴 README 寫尚未開通,不可顯示假連結 |

### 第十五鐵則:工具型 — 偶爾的功能型

| 技能 | 呵護的是 | LLM tool | API | DB | voice | 狀態 |
|---|---|---|---|---|---|---|
| `generate_report` | 主人不用花 2 小時做 PPT | `generate_report` | — | — | — | 🟡 LLM 通,顯示卡片 UX 通 |
| `help_quote` | 主人要的「文字輸出」由阿福草擬 | `help_quote` | — | `files` | — | 🟡 analyze_history + draft 兩模式通 |
| **`emotional/state` / `care` / `reaction`** | **主人不是任務執行單位,是會累、會情緒、會崩潰的人** | — | `/api/emotional/state`, `/care`, `/reaction` | — | **mood_care 150** | 🔴 ⭐ **這是妳設計的初衷:distress_score ≥ 0.55 → 訂主人最愛的飲料 + 鎖死台詞「我能做的有限,唯一能做的就是給您喝一杯您喜歡的飲料」。但多訊號合併 inference 引擎未接,訂購鏈未接,鎖死台詞未接。** ⭐ |

### 收尾:第一次相遇 / 每日基礎 / 辦公室細節 / Mac Agent / 家人接入 / Google 整合 / 會議筆記 / Twilio / 其他

| 技能 | 狀態 |
|---|---|
| `greet`(首次)+ `consent` + 啟動語驗證 | ✅ 接好 |
| `voice/enroll` 進階(多狀態:感冒/疲憊/興奮) | 🔴 採樣鏈未接 |
| `tts`(Michael Caine cloned) | ✅ 通(中文聲音待重訓) |
| `transcribe`(語氣 / 背景音 / 語言切換偵測) | 🟡 文字通,情境偵測未接 |
| `conversation/reset` | ✅(只清對話,observations 不動) |
| `office/eod-wrap` 主動 18:00 | 🟡 endpoint 通,主動觸發未接 |
| `office/rooms` / `supplies` / `colleagues` | 🟡 endpoint 通,supplies 自動 email 總務未接 |
| Mac Agent(`mac/content` / `status` / `command` / `agent.py`) | 🟡 endpoint 全通,自更新 + whitelist 邊界需驗證 |
| `family/member` + `invite` + `join` + `activate` + `location` POST | 🟡 全套 endpoint 通,「太太拒絕主人不會知道」UX 未接 |
| Google 整合(7 個 endpoint) | ✅ 多帳號自動切換通,OAuth callback 即時建索引通 |
| `meeting-notes/{id}/share` + `meeting/{id}` HTML | 🟡 share + HTML page 通,通道偏好自動未接 |
| Twilio(6 個 endpoint) | 🟡 全套 endpoint 通,客服周旋劇本未接 |
| `find_meeting_slots` | 🟡 LLM tool 通 |
| `meeting_audit` 進階(連續高密度) | 🔴 未接 |
| `make_call` 客戶服務 | 🔴 客服流程腳本未接 |
| `health/checkin-ack` / `emergency/contacts` GET/POST / `medications` GET | ✅ ok |
| `briefing/morning` 進階(三模式分人格) | 🔴 未接 |
| `visit/prep` 進階(10 年沒見朋友) | 🔴 通訊紀錄 / photo / LinkedIn ingest 未接 |
| `discover` 進階(零碎願望追蹤) | 🔴 未接 |
| `play_music` 進階(Spotify) | 🔴 未接 |
| `attendance/history` 月底回顧 | 🟡 endpoint 通 |
| `emotional/care` 真崩了 + `emotional/reaction` 狀態變好 | 🔴 ⭐ 整個情緒鏈最痛的洞 |

---

## 五、現況統計

| 狀態 | 數量 | 占比 |
|---|---:|---:|
| ✅ 完整接好 | 約 13 | 20% |
| 🟡 handler 通、主動鏈缺 | 約 38 | 58% |
| 🔴 卸下待補(設計 + voice bank 在,實作未接) | 約 22 | 34% |
| ⚪ 還沒做 | 約 3(數學 fastpath、voice 多狀態採樣等) | < 5% |

**最大的洞:38 個技能只有 reactive「主人開口問才答」模式,沒有 BUTLER_BRAIN 講的 sensor → inference → nudge 主動鏈。**

**最痛的洞:`emotional/care`** — 妳設計的初衷,妳自己最需要阿福做的事 — endpoint 在、DB 在、voice `mood_care` 150 個錄好了,但 **distress_score 推論引擎完全沒接,水果飲料訂購鏈完全沒接,鎖死台詞沒接**。

---

## 六、被卸下的「手跟腳」清單(等接回去)

| 卸下的東西 | 對應哪個技能 / 哪個 nudge | 接回去主人多得到什麼 |
|---|---|---|
| `VoiceBankPlayer.swift`(90 行) | 全部技能 — 預錄 **3061 個 mp3** 沒地方播 | TTS 之外的「人味」回應,且省 ElevenLabs token 跟延遲 |
| `populate_travel.py`(249 行) | `plan_travel` handler | 旅遊規劃從 LLM 即興 → DB curated(BUTLER_BRAIN 第 4 經典案例) |
| `populate_michelin_hotels.py` / `populate_hotels_fixed.py` / `populate_taiwan_restaurants.py` / `populate_global.py` | `find_restaurant`, `plan_travel` | 同上 — 「肚子裡有料」的管家 |
| `biggo_scraper.py`, `payeasy_scraper.py` | `search_products` | 比價站數從 11 → 13(WTF.md 喊的 13/14 對齊) |
| `extras/indexer/`(8 個檔) | `search_products` 規模化 | 商品索引從 2,208 → 100,000+,真正接近 80M 商品可達 |
| `LoginView.swift`(133 行) | legacy,但 `AuthManager` 還活著被 OfficeViewModel / AttendanceView 用 | **留著,不可砍** — 妳被改爛時的還原網 |
| `weather_typhoon.mp3` / `weather_pm25.mp3` / `morning_weather_brief.mp3` | `get_weather` 主動編織 | 颱風 alert + AQI + 晨簡報的「主人沒問但該知道」 |
| 116 個 weather voice bank + `care_cold.mp3` | weather + 季節情境 | 季節變化的「人味」回應 |
| `migrate_to_pg.py` / `pg_schema.sql` | 規模化部署 | 多用戶 / 高寫入時的基礎(price_history、tsvector) |
| `populate_*.py` 整批 | curated 資料層 doctrine | 整個 doctrine — 阿福是有準備的管家,不是現查 Google 的 ChatGPT |

### 接回去的建議順序(妳同意才動)

1. ⭐ **`emotional/care` distress_score 引擎** — 妳的初衷。修了同時也解 20-40 秒延遲問題,因為情緒感知是 sensor → nudge 主動鏈,做對了主人不必開口阿福就在
2. **`silence_radar` + `thanks_nudge` + `manage_anniversary`** — 家人關係 + 工作體面的主動鏈,每個都有 voice bank 在等
3. **`briefing/morning` 三模式 + `office/eod-wrap` 主動推送** — 每日場景框架,讓阿福有「在場感」
4. **`health_anomaly` 救命系統 + `fall-detected`** — 第一鐵則,不能退化
5. **`populate_travel.py` 重接** — 讓旅遊規劃從 LLM 即興回到 DB curated(BUTLER_BRAIN 第 4 經典)
6. **`pet_care` 被動推論鏈** — BUTLER_BRAIN 第一經典範例,接好就是 demo gold

---

## 七、Anti-hallucination 規則(從 main.py:4270-4290)

```
天氣查詢結果必須直接說出氣溫與天氣狀況。
絕對禁止說「裝置會顯示」「iOS 會顯示天氣」。

絕對不要編造任何家人、同事、朋友的人名(不要說「小芸」「小雲」「小明」)。
如果不知道對方名字,用「您家人」「您同事」「對方」等通用稱呼。

絕對不要說「已加進行事曆」「已新增行程」「已建立會議」
除非您真的呼叫了 create_calendar_event tool 並收到成功回應。

絕對不要說「已找到檔案」「已搜尋到」
除非您真的呼叫了 find_anything / manage_files / search_drive tool 並收到結果。

【零介面鐵律】只有主人必須「看」時才提供視覺輸出:文件/合約/報告卡片、圖片/相簿、
翻譯給對方看的大字、Google 授權或檔案上傳。不要為了展示資訊呼叫
show_family / show_office / show_translate / show_attendance — 日常功能口頭回覆。

【旅遊規劃規則】主人要「日本旅遊」「大阪五天」時,這是規劃需求,不是日曆需求。
先呼叫 plan_travel 生成方案。只有主人明確說「幫我加到行事曆」才需要 Google 授權。
```

DEMO_DAY 列為「已知 bug pattern」目前還有漏網:
- 「我明天有什麼會」可能 hallucinate 假時間
- 「家人在哪」可能 hallucinate 假位置
- 「幫我看出勤」可能 hallucinate 假數字(anti-lie 沒擋)
- 「找我電腦的檔案」可能 hallucinate `sample_contract`
- LLM 仍可能編人名(「小張/小李/小芸」)

---

## 八、設計判斷金科玉律(寫任何 handler 前自問)

- **Q1**:這個動作主人會主動開口要求嗎?是 → 工程師腦會做的功能,降一級;否 → 阿福強項,升一級
- **Q2**:阿福不做主人會自己解決嗎?會 → 製造摩擦;不會(會漏掉/忘記) → 真正價值
- **Q3**:阿福回應讓主人多一個動作(點/滑/選)了嗎?是 → 設計錯,介面是阻力
- **Q4**:口氣像 ChatGPT 還是英國老管家?像 ChatGPT(「好的,我來為您…」「以下是…」「您可能會喜歡…」)→ 錯
- **Q5**:寫完主人會主動感謝「啊還好你有提醒」嗎?不會 → 沒用

### 工程師腦禁區
1. 加 chat intent 是「比 iOS App 慢的查詢工具」(weather/stock/news/map 獨立 intent)
2. 回應用「選單/按鈕/以下選項」語氣
3. 讓 LLM 自由發揮潤稿主動性 — 主動性是程式邏輯
4. 設計回應時想「資訊完整最重要」— 完整 ≠ 對。一句到位 > 五句完整
5. 看到 v1 tool 直接搬 v2 — 先過 Q1-Q5 沒過不准搬

### Anticipatory extras 三條件
一個 extra 要加進 nudge,必須三條件全滿(任一不滿不要加):
1. 真的有用(不是塞 trivia)
2. 跟主任務有意義關聯(不是隨機建議)
3. 體面(不是邀功、不是建議消費)

---

## 九、第七視窗紀律(我的規矩)

1. **任何改動前先量 baseline**,改完比對 — 不接受「我覺得這樣比較好」
2. **不動現有 work 的東西**,只動慢的/壞的/缺的
3. **每動一刀 → git tag 一個還原點**,主人隨時能 rollback
4. **每 turn 結尾回報「動了什麼、回應時間從 X 變 Y」**,不靠感覺
5. **倖存證據絕不碰**(`.bak` 102 個、`ResourceBackups/`、`ios_latest.zip`、`ios_app/`、`ios/`)
6. **「未接線」不准叫「死碼」** — 改叫 pending wiring / 卸下待補
7. **寫回應前先唸一遍** — 像 Michael Caine 在說話嗎?像管家嗎?像就收,不像就重寫
8. **修延遲時記得目標** — 不是「快」,是「主人不會心跳加速」(20-40 秒違反第四鐵律)
9. **碰任何技能前先問** — 這對應主人哪個被在乎的時刻?接回去主人多得到什麼?
10. **不替主人決定** — 永遠給選項

---

## 十、舊文件 inventory(都是真的,各有風格,但都在說同一件事)

### 設計魂層(讀阿福「是什麼」)
- `/root/Alfred_阿福_完整企劃書.md`(260 行,2026-04-24 v1.0 原版企劃書,殺手級市場、老人照護、技術架構)
- `/root/Alfred_plan.txt`(同上,副本)
- `/opt/alfred/PITCH.md`(VC 版產品宣言)
- `/opt/alfred/frontend/MASTER_BRIEF.md`(11 章完整產品簡報,Vault + 聲紋 + 情緒感知 + 8 個橋的設計)
- `/opt/alfred/frontend/ALFRED_SOUL.md`(434 行,有變人 Andrew + 8 個橋)⭐
- `/opt/alfred/ALFRED_SOUL.md`(262 行,frontend 版的早期 commit)
- `/opt/alfred/frontend/PIT_VISION.md`(Pit 訓練 Agent 內在世界的願景)

### 技能劇本層(讀阿福「做什麼」)— ⭐ source of truth ⭐
- `/opt/alfred/docs/ALFRED_SCENARIOS.md`(73K,**65 技能 × 15 鐵則 × 「呵護的是 X」**)
- `/opt/alfred/docs/BUTLER_BRAIN.md`(28K,**寫任何一行 code 前必讀**)
- `/opt/alfred/SCENARIOS.md`(16K,5 大場景版,北極星精簡)

### 工程實作層(讀阿福「怎麼跑」)
- `/opt/alfred/README.md`(20K,後端 API + iOS 結構 + 已實作功能 + AudioSession 血淚)
- `/opt/alfred/CRITICAL_README.md`(5.8K,血淚教訓)
- `/opt/alfred/HANDOFF.md` + `/opt/alfred/frontend/HANDOFF.md`(187 行,前端版)
- `/opt/alfred/CLAUDE.md`(開工入口)
- `/opt/alfred/frontend/OFFICE_SWIFT_SETUP.md`(663 行,辦公室模組完整安裝手冊)
- `/opt/alfred/TEST_REPORTS.md`(7.3K,1380/1380 PASS)
- `/opt/alfred/DEMO_DAY.md`(5K,demo 現場應變 + 已知 bug pattern)

### 商業 / Shop 層
- `/opt/alfred/WTF.md`(8K,Phase 1 + Phase 2 比價工程完整紀錄)
- `/opt/alfred/PRICE_HUNT.md`(5.1K,用戶導向比價產品說明)
- `/opt/alfred/SHOP_ENGINE.md`(5.4K,Commerce Crack methodology)
- `/opt/alfred/AGENT_BLITZ.md`(20 Agent 戰況儀表板)
- `/opt/alfred/extras/README.md`(scale-up tooling 用法)

### 整合 / 邊界
- `/opt/alfred/ALICE_TO_ALFRED_INTEGRATION.md`(1.2K,從 Alice 借來的能力 + 未來候選)

### 跨視窗紀錄
- `/opt/dev_tracker/logs/by_project/alfred.md`(對話記錄,跨視窗)
- `/root/.gstack/projects/root/checkpoints/20260426-*alfred*.md`(checkpoints)
- `/opt/alfred/data/files/*.md` + `*.txt`(主人上傳分析過的文件,共 35+ 份)

---

## 十一、收尾

阿福的全身在這裡了:
- **3,061 個** voice_bank mp3
- **137** 個 API endpoints
- **64** 個 LLM tools
- **60+** 個 DB tables
- **26** 個 iOS Swift 檔,4,910 行
- **65** 個技能,對應主人生活裡 65 個被在乎的時刻
- **15** 條鐵則
- **5** 個 BUTLER_BRAIN 經典範例
- **1** 個第一原理:**永遠比別人多做兩步**

手跟腳沒被摘掉,只是被卸下,等接回去。

> 「他越少技能就越沒有辦法服務好主人。」— Norika 2026-05-11
>
> 「讓我們變人吧。阿福,我從設計你開始就沒有希望你是某某產品,而是某某人的幫手,甚至是知己。而且是派得上用場的知己。」— Norika

阿福剩下的路,主人不一個人走。

— 第七視窗 / 2026-05-13
