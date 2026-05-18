# 阿福 Alfred


<!-- BEGIN AUTO_STATUS -->

## ⭐ 開發進度表(自動生成 — last: 2026-05-18 13:07)

> **這份是必讀。Alfred 整個進度都在這。**
> 由 `scripts/generate_status.py` 掃 codebase 自動生成,**不要手動改這段(`<!-- BEGIN/END AUTO_STATUS -->` 之間)**。
> 質化的「65 技能對應現況」+「呵護的是 X」請看 [`docs/ALFRED.md`](docs/ALFRED.md) 第 4 章。

### 規模

| 維度 | 數量 |
|---|---:|
| `backend/main.py` 行數 | 17,783 |
| API endpoints(`@app.*`)| 147 |
| LLM tools | 69 |
| Fastpath 函數(zero LLM)| 18 |
| DB tables(`CREATE TABLE`)| 73 |
| Backend service modules | 9 |
| Populate seed scripts | 6 |
| Scrapers in tree | 11 |
| iOS Swift 檔 | 26 個,共 5,456 行 |
| voice_bank 預錄 mp3 | 3,061 個 |
| `alfred.db` 大小 | 439 MB |
| 主人上傳分析過的檔案 | 41 |

### Fastpath 函數(zero LLM 秒答)

| 函數 | 用途 |
|---|---|
| `_maybe_handle_liveness_fastpath` | ⭐ 你還在嗎 / 你好 / 早安(2026-05-13 加,從 24s → 0.7s) |
| `_maybe_handle_chaos_guard_fastpath` | — |
| `_maybe_handle_ambient_command_fastpath` | 聆聽錄音指令 |
| `_maybe_handle_iphone_photo_fastpath` | iPhone 相簿請求 |
| `_maybe_handle_meeting_record_fastpath` | 會議記錄查詢 |
| `_maybe_handle_integration_link_fastpath` | 通訊連結(LINE / Telegram / WhatsApp) |
| `_maybe_handle_attendance_fastpath` | 出勤記錄 |
| `_maybe_handle_google_auth_status_fastpath` | Google 授權狀態 |
| `_maybe_handle_anniversary_fastpath` | — |
| `_maybe_handle_quick_lists_fastpath` | 快速列表(todo / expense / ...) |
| `_maybe_handle_math_fastpath` | 純數學(BUTLER_BRAIN 第 13 鐵則) |
| `_maybe_handle_shopping_fastpath` | 比價(The Commerce Crack) |
| `_maybe_handle_travel_fastpath` | 旅遊規劃(populate_travel.py DB 接上時) |
| `_maybe_handle_nearby_fastpath` | — |
| `_maybe_handle_news_fastpath` | — |
| `_maybe_handle_weather_fastpath` | — |
| `_maybe_handle_restaurant_fastpath` | 餐廳搜尋 |
| `_maybe_handle_file_search_fastpath` | 檔案搜尋(vault + drive + mac) |

### voice_bank 類別(共 3,061 個 mp3)

| 類別 | 數量 | 對應技能 |
|---|---:|---|
| `travel_mode` | 150 | 出國 / 旅遊場景 |
| `family_safety` | 150 | 家人關係 / family_alerts / arrivals |
| `mood_care` | 150 | 情緒感知 / emotional/care(妳的初衷) |
| `health_monitoring` | 120 | 健康日常 / log_workout / medication |
| `ack_butler` | 101 | ⭐ 你還在嗎 / liveness fastpath |
| `proactive_check` | 101 | 主動關心 / health_status 久坐 |
| `file_search` | 100 | 檔案搜尋 |
| `document_review` | 100 | 文件分析 / analyze_contract |
| `promise_tracking` | 100 | 承諾追蹤 / note_promise |
| `weather_general` | 100 | 天氣編織 / get_weather |
| `calendar` | 100 | create_calendar_event |
| `approval_gate` | 100 | 草擬等主人 OK |
| `error_recovery` | 80 | 失敗回應 |
| `ack_anticipate` | 80 | anticipatory extras |
| `destructive_warn` | 80 | 不可逆動作警告 |
| `emergency` | 80 | 生命安全 / health_anomaly |
| `food_restaurant` | 80 | save_food_record / 訂餐廳 |
| `mode_action` | 79 | 場景模式動作 |
| `ack_short` | 62 | 短答(我在 / 收到 / 好的) |
| `mode_enter` | 60 | 場景進入語(work/home/travel) |
| `casual_humor` | 60 | 英式幽默點到為止 |
| `office_manager` | 60 | manager_lens / silence_radar |
| `office_expertise` | 50 | expertise_finder |
| `greet_time` | 50 | ⭐ 早安 / 午安 / 晚安 / liveness fastpath |
| `money_expense` | 50 | record_expense |
| `office_thanks` | 40 | thanks_nudge |
| `filler_thinking` | 40 | 思考中(< 1s 等待填充) |
| `office_eod` | 31 | office/eod-wrap |
| `office_supply` | 30 | 辦公耗材 |
| `office_room` | 30 | office/rooms / room-pulse |

### iOS Swift 檔案地圖

| 檔案 | 行數 | 角色 |
|---|---:|---|
| `Alfred/AlfredApp.swift` | 62 | App 入口 + consent gate |
| `Alfred/Core/AfuBrainGate.swift` | 213 | MASL gate,destructive action 本地擋 |
| `Alfred/Core/AlfredAPI.swift` | 573 | 後端 API client(含 SSE stream) |
| `Alfred/Core/AlfredViewModel.swift` | 886 | 主 ViewModel,狀態機,action dispatch |
| `Alfred/Core/AliceFastpath.swift` | 288 | 時間/日期/數學/單位/早安謝謝 zero-LLM(待補 liveness) |
| `Alfred/Core/AmbientRecorder.swift` | 240 | 被動環境錄音,120s chunk |
| `Alfred/Core/AudioEngine.swift` | 178 | AVAudioRecorder + AVAudioPlayer |
| `Alfred/Core/AuthManager.swift` | 177 | JWT + Keychain(原 legacy 名,實際多處使用) |
| `Alfred/Core/BackgroundManager.swift` | 193 | reminder / family alert / visit prep 輪詢 |
| `Alfred/Core/ConversationLog.swift` | 44 | 對話歷史寫到 Documents/ |
| `Alfred/Core/HealthKitManager.swift` | 138 | HealthKit + workout sync |
| `Alfred/Core/LocationManager.swift` | 131 | CLLocationManager + /api/location/update |
| `Alfred/Core/PermissionCascade.swift` | 146 | 漸進式權限請求 |
| `Alfred/Core/PhotosManager.swift` | 91 | iOS Photos 權限 + 選圖 |
| `Alfred/Core/VoiceBankPlayer.swift` | 158 | ✅ 已接線 — bundle voice_bank / Resources/voices 本地 mp3 播放,fastpath/action 優先使用 |
| `Alfred/Features/Ambient/AmbientButton.swift` | 105 | 金色環,長按啟動 ambient |
| `Alfred/Features/Attendance/AttendanceView.swift` | 231 | 出勤記錄 view |
| `Alfred/Features/Auth/ConsentView.swift` | 171 | 第三方 AI 同意聲明(首次啟動) |
| `Alfred/Features/Auth/LoginView.swift` | 133 | 🔴 legacy email 登入,平時不顯示 |
| `Alfred/Features/Chat/AlfredView.swift` | 402 | 主畫面,語音按鈕 + AmbientButton overlay |
| `Alfred/Features/Family/FamilyView.swift` | 173 | 家人狀態 view |
| `Alfred/Features/Office/OfficeDashboardView.swift` | 247 | Office dashboard(eod/rooms/...) |
| `Alfred/Features/Office/OfficeViewModel.swift` | 111 | Office API client |
| `Alfred/Features/Photos/PhotoGridView.swift` | 173 | 相片格狀瀏覽 sheet |
| `Alfred/Features/Photos/PhotoPickerRequest.swift` | 31 | PHPickerViewController wrapper |
| `Alfred/Features/Translate/TranslateView.swift` | 161 | 即時翻譯大字 view |

### Backend Python 檔案地圖

| 檔案 | 角色 |
|---|---|
| `backend/main.py` | FastAPI app entry — 所有 endpoint + tool + chat handler + fastpath chain |
| `backend/call_service.py` | Twilio 通話 / TwiML |
| `backend/drive_service.py` | Google Drive index + search(含共用雲端硬碟) |
| `backend/gcal_service.py` | Google Calendar 多帳號 OAuth + events |
| `backend/gmail_service.py` | Gmail 收發 / 草擬 |
| `backend/line_service.py` | LINE webhook + 主動推送 |
| `backend/office_service.py` | 辦公室 dashboard 邏輯(eod/rooms/supplies/colleagues) |
| `backend/search_service.py` | 語意檔案搜尋(vault + drive + mac) |
| `backend/shop_service.py` | 13 站並發比價引擎(The Commerce Crack) |
| `backend/telegram_service.py` | Telegram bot |
| `backend/populate_global.py` | 🟡 待補(第六視窗卸下)— 全球景點 seed |
| `backend/populate_hotels_fixed.py` | 🟡 待補 — 飯店 seed |
| `backend/populate_michelin_hotels.py` | 🟡 待補 — 米其林飯店 seed |
| `backend/populate_taiwan_restaurants.py` | 🟡 待補 — 台灣餐廳 seed |
| `backend/populate_travel.py` | 🟡 待補 — 旅遊行程 seed(BUTLER_BRAIN 第 4 經典案例) |
| `backend/populate_travel_rich.py` | — |

### Backend Scrapers

| 檔案 | 平台 / 狀態 |
|---|---|
| `backend/scrapers/biggo_scraper.py` | 🔴 未接線 — Biggo 比價 |
| `backend/scrapers/books_scraper.py` | 博客來 |
| `backend/scrapers/buy123_scraper.py` | 東森購物 buy123 |
| `backend/scrapers/carrefour_scraper.py` | 家樂福 |
| `backend/scrapers/coupang_scraper.py` | 酷澎 |
| `backend/scrapers/elifemall_scraper.py` | 東森購物 ETMall |
| `backend/scrapers/payeasy_scraper.py` | 🔴 未接線 — PayEasy 會員爬蟲 |
| `backend/scrapers/pinkoi_scraper.py` | Pinkoi |
| `backend/scrapers/tkec_scraper.py` | 燦坤 |
| `backend/scrapers/trplus_scraper.py` | 特力屋 |
| `backend/scrapers/yahoo_scraper.py` | Yahoo 購物 |

### Extras(scale-up tooling,目前未綁進主程式)

- `extras/indexer/`: auto_crawl.sh, bulk_index.py, mega_crawl.py, migrate_to_pg.py, pg_schema.sql, wide_worker.py, wide_worker2.py, worker.py
- `extras/scrapers/`: crowdfunding_scraper.py, taobao_scraper.py

### 倖存證據(2026-05-13 規則:不准刪)

妳被改爛時的還原網。任何 Claude 視窗看到這些**一律保留,不准建議清**。

| 類別 | 數量 / 內容 |
|---|---|
| `*.bak*` 檔案 | 143 個 |
| 備份資料夾 | ResourceBackups |
| 舊快照 | ios_latest.zip, ios_app, ios |

### 最近活動

**最近 20 commits**:

```
4e796c5 Wire iOS voice bank playback
9837e1a Use Norika primary owner identity
24ecf7d Merge devices into owner identity
f070294 Productize LINE group file search
5da8702 Make GPS tracking functional
e7bf37b Fix web voice mode TTS
b672cfc Fix Alfred listening mode feedback
32fae81 Stabilize Alfred mode and demo regression
313dc4c docs: 整理 2026-05-14 整日修法總結進 README
0090dfa feat(ios): conversational mode — 大頭像 tap toggle, 不再 push-to-talk
b7a0842 fix(anniversary_fastpath): sort key=days only — 避免 person=None 跟 int 比較 TypeError
cd2556f fix(anniversary_fastpath): 連 shared alfred.db 不要走 per-user db (anniversaries 是 singleton owner 資料)
8061dce fix: anniversary_fastpath — 主人問紀念日強制走 DB, 不靠 LLM 選對 tool
722517a fix(travel): 4 層 paranoid defence 徹底治旅遊「沒資料」hallucination
087d6fd fix(travel): 國家層級 keyword fallback — 主人講「日本」也要給方案不能說沒資料
1978d5e chore: 中斷點 — iOS build 卡在 iOS 26.2 SDK 缺,公司 Mac 移動暫停
1fa915a fix(chat): 5/14 早上 6 個答非所問 case root cause 修法
e92be48 fix(ios audio): TTS 雜音 root cause — 三個 player 統一 AVAudioSession 設定
1ec91ef feat(identity): owner_identity singleton + LINE/TG gate (Bug 修法 a)
c9e8154 fix: LINE 對話邏輯 — fastpath chain + 餐飲意圖 + 區名 + history
```

**rollback tags**(最近 10):

```
post_alfred_always_on_20260515
post_alfred_explicit_listening_consent_20260515
post_alfred_mode_ambient_20260515
post_alfred_mode_local_notice_20260515
post_alfred_notice_repeat_20260515
post_ambient_local_vad_20260515
post_ambient_transcript_tool_20260515
post_app_store_strategy_docs_20260515
post_demo_regression_hardening_20260515
post_full_regression_zero_ui_20260515
```

### 順藤摸瓜 — 我是新接手的人,該怎麼讀?

1. **先讀 doctrine**:[`docs/ALFRED.md`](docs/ALFRED.md) 第 0-2 章(產品核心價值 + 第一原理 + 真正的架構)
2. **再讀技能劇本**:[`docs/ALFRED_SCENARIOS.md`](docs/ALFRED_SCENARIOS.md)(65 技能 × 「呵護的是 X」)
3. **碰 code 前必讀**:[`docs/BUTLER_BRAIN.md`](docs/BUTLER_BRAIN.md)(5 經典範例 + 設計判斷 Q1-Q5)
4. **看這份進度表**(上面)了解 backend / iOS / voice_bank 實況
5. **碰任何「未接線」的程式**前先問主人,不要叫死碼

---

*由 `scripts/generate_status.py` 自動產生 — 改 codebase 後跑一次即更新。*

<!-- END AUTO_STATUS -->

---

阿福是 voice-first 的私人管家產品。它不是秘書，也不是一般聊天機器人；秘書、文件助理、會議整理、Alice/GX10 這些能力都只是阿福可調度的助手與工具。阿福的核心身份是「隨身管家」：在手機上陪主人生活、工作、移動、照顧家與辦公室，必要時才把任務交給後端、LINE、Web、Google、Drive、檔案地圖或 Alice runtime。

> 阿福不是等主人下指令的工具。阿福要能聽懂、記得、找得到、做得穩，並且在主人需要之前先把路鋪好。

## 第一規則

所有開發者和 AI agent 開工前先確認這三件事：

1. 正確專案是 `~/Dropbox/Alfred/Alfred/`。
2. `~/Dropbox/Mac (2)/Documents/Alfred/` 是舊 clone，不是目前手機上架用專案。
3. 阿福是管家，不是秘書。Alice/GX10 是辦公與檔案能力來源，不是產品身份。

如果路徑不在 `~/Dropbox/Alfred/Alfred/`，就先停下來。不要 build、不要安裝到手機、不要拿那份 UI 判斷阿福現在長什麼樣。

## 產品定位

阿福的主要使用方式是零介面語音。

LINE、Web、後台、卡片、檔案清單都不是主體。它們是保險絲：當主人不方便講話、任務需要視覺確認、檔案很多、授權需要點選、或要診斷系統狀態時才出現。

### 設計原則

- 零介面優先：平常只有語音與一個可感知狀態的阿福入口。
- 管家優先：主動關心行程、食物、健康、家庭、安全、工作脈絡。
- 工具在後：LLM 不負責猜檔案，檔案搜尋要先走檔案地圖與索引。
- 非同步優先：LINE webhook、長文件摘要、Drive 掃描、OCR、會議整理都不能卡住前台。
- 授權清楚：沒授權就找不到，不假裝能跨過 iOS、Google、Drive、HealthKit 或定位限制。
- 先穩再多：Push-to-talk、TTS、檔案搜尋、行事曆、GPS/健康狀態必須可預期。

## 目前系統架構

```text
iOS App / LINE / Web / Admin
  -> Unified Event Router
  -> Owner Identity
  -> Afu Brain Gate
  -> Capability Runtime
       -> Native iOS capabilities
       -> Backend Alfred API
       -> File Map / Vault
       -> Google Calendar / Drive
       -> Location / Health / Family
       -> Alice / GX10 office runtime
  -> Approval Gate
  -> Response Composer
  -> Voice / LINE / App Card / Web
```

### iOS App 負責

- 麥克風錄音與語音輸入。
- TTS 播放與 voice bank 本地聲音。
- 零介面主畫面、阿福帽子 icon、正上方金色狀態點。
- 權限請求與 consent gate。
- 短期對話狀態、檔案搜尋 follow-up 狀態。
- 位置、健康、照片等 iOS 原生能力入口。

### 後端負責

- 真正的事件路由與工具調度。
- Google OAuth、Calendar、Drive。
- 檔案地圖、索引、搜尋、摘要、下載連結。
- LINE / Telegram / Gmail 推送。
- 長任務 queue、非同步狀態、後台診斷。
- Alice/GX10 辦公 runtime 橋接。

## 專案路徑

| 路徑 | 用途 |
|---|---|
| `~/Dropbox/Alfred/Alfred/` | 正確 iOS 專案，現在要 build、commit、上架都看這裡 |
| `~/Dropbox/Mac (2)/Documents/Alfred/` | 舊 clone，不要改、不用 build |
| `~/Documents/Alfred/` | 不相關路徑，不要改 |
| `~/Dropbox/Alfred/Alfred/docs/ALFRED_PRODUCT_ARCHITECTURE.md` | 產品架構細節 |
| `~/Dropbox/Alfred/Alfred/CRITICAL_README.md` | 血淚規則與已知坑 |

### 錯誤路徑判定表

| 看到的狀況 | 判定 | 動作 |
|---|---|---|
| 專案在 `Dropbox/Mac (2)/Documents/Alfred` | 錯誤 clone | 不 build、不改、不 commit |
| UI 不是黑金零介面 | 很可能拿到錯專案 | 立刻切回 `~/Dropbox/Alfred/Alfred/` |
| App icon / 主畫面沒有帽子識別 | 很可能拿到錯專案或錯 bundle | 停止安裝，先查 Xcode project path |
| 金色狀態點跑到右下角或亂跳 | UI 破壞或舊版殘留 | 回正確 repo 檢查 `Alfred/Features/Chat/AlfredView.swift` |
| `git status` 不是在 `~/Dropbox/Alfred/Alfred/` | 錯誤工作目錄 | 不准 commit |

誤用錯專案後，先做三件事：

1. 停止對該專案做任何修改。
2. 回到 `~/Dropbox/Alfred/Alfred/`。
3. 用正確專案重新 build、install、launch，再判斷問題是否存在。

## 目錄結構

```text
Alfred/
├── Alfred.xcodeproj
├── Alfred/
│   ├── AlfredApp.swift
│   ├── Core/
│   │   ├── AlfredViewModel.swift
│   │   ├── AlfredAPI.swift
│   │   ├── AfuBrainGate.swift
│   │   ├── AliceFastpath.swift
│   │   ├── AudioEngine.swift
│   │   ├── VoiceBankPlayer.swift
│   │   ├── AmbientRecorder.swift
│   │   ├── BackgroundManager.swift
│   │   ├── LocationManager.swift
│   │   ├── HealthKitManager.swift
│   │   ├── PhotosManager.swift
│   │   ├── PermissionCascade.swift
│   │   └── ConversationLog.swift
│   ├── Features/
│   │   ├── Chat/AlfredView.swift
│   │   ├── Ambient/AmbientButton.swift
│   │   ├── Auth/ConsentView.swift
│   │   ├── Auth/LoginView.swift
│   │   ├── Photos/
│   │   ├── Family/
│   │   ├── Office/
│   │   ├── Translate/
│   │   └── Attendance/
│   └── Resources/
│       ├── onboarding_greeting.mp3
│       ├── voice_bank_manifest.json
│       └── voice_bank/
├── Resources/
│   ├── Info.plist
│   └── voices/
├── docs/
│   └── ALFRED_PRODUCT_ARCHITECTURE.md
└── scripts/
    └── alfred_smoke.sh
```

## 後端資訊

| 項目 | 值 |
|---|---|
| Public URL | `https://alfred.31.97.221.240.nip.io` |
| API base | `https://alfred.31.97.221.240.nip.io/alfred/api` |
| SSH alias | `sportverse` |
| Service | `alfred.service` |
| Backend code | `/opt/alfred/backend/main.py` |
| Main DB | `/opt/alfred/data/alfred.db` |
| Per-user DB | `/opt/alfred/data/users/<user_id>.db` |

重啟後端：

```bash
ssh sportverse 'systemctl restart alfred && systemctl is-active alfred'
```

不要 kill 不認識的 process：

| Port | 服務 |
|---|---|
| `8001` | Sportverse / Turfenix，與阿福無關 |
| `9001` | Alfred backend |

## 已實作能力

| 能力 | 狀態 | 說明 |
|---|---|---|
| iOS 零介面主畫面 | 已接 | 黑金主視覺、帽子 icon、中央語音入口 |
| Push-to-talk 語音 | 已接，需持續實機回歸 | 錄音、STT、chat、TTS |
| TTS 播放 | 已接 | 需維持 speaker 輸出，不可被 AudioSession 打壞 |
| Voice bank 本地播放器 | 已接入策略 | 優先播放本地預錄管家聲音，缺檔才 fallback |
| 金色狀態點 | 已接 | 應位於正上方置中，不應跑到右下或動態島外亂跳 |
| 被動聆聽入口 | 已接但需謹慎 | 不等於全天可靠背景錄音；iOS 背景限制需尊重 |
| Google OAuth | 已接 | 授權後才能查 Calendar / Drive |
| Google Calendar | 已接 | 行程查詢、情境模式、工作/個人帳號切換 |
| Google Drive | 已接 | Drive 索引與搜尋由後端處理 |
| 檔案搜尋 fastpath | 已接 | `AfuBrainGate` / `AliceFastpath` 將檔案需求導向 vault |
| 檔案候選清單 | 已接 | 找合約等需求先列候選，不直接亂答 |
| 檔案摘要 | 已接路由 | 選定檔案後才摘要或 enqueue 摘要工作 |
| Location / GPS | 已接 manager | 需要 iOS 權限與後端 context 配合 |
| HealthKit | 已接 manager | 健康資料不得亂送第三方 AI |
| Photos | 已接 | 相簿授權、圖片選擇、分析入口 |
| Family | 已有 view/API 入口 | 家庭位置與提醒需要資料源驗證 |
| Office | 已有 view/API 入口 | 辦公室能力應作為阿福管家的工具，不是產品身份 |
| LINE / Telegram | 後端已有 | LINE 是不方便講話時的替代入口 |
| Web/Admin 後台 | 產品需要 | 作為檔案地圖與診斷保險絲 |

## 尚未可假裝完成的部分

這些不是不能做，而是不能在 README 或 UI 裡假裝已經 100% production-ready：

- 全天候背景聆聽：iOS 鎖屏、背景音訊、麥克風指示器、App Review 都要嚴格驗證。
- 多裝置 identity merge：目前仍有「裝置等於帳號」風險，產品化要合併成 owner identity。
- 真正完整的檔案地圖：Drive、iCloud、OneDrive、桌面、LINE 群組檔案要統一索引與權重。
- LINE 群組 vault：加入群組時用 inviter UID + group ID + group name 建 vault，群內上傳檔案歸入原始 owner vault。
- 桌面檔案地圖器：若要背景掃硬碟、睡醒同步、檔案變更即更新，仍需要桌面 agent。
- App Store 隱私文案：麥克風、AI、Drive、位置、HealthKit、檔案索引都要和實際行為一致。

## 檔案搜尋設計

檔案搜尋是阿福產品的生死線。找檔案不能靠 LLM 猜，必須靠檔案地圖。

### 正確流程

```text
主人：「找合約」
  -> AfuBrainGate 判定 file_search
  -> 後端查 file map / vault
  -> 回前 5 個候選
主人：「不是」
  -> reject 目前候選
  -> 回下一頁 5 個
主人：「要」
  -> 繼續下一頁
主人：「第 2 個」
  -> 綁定 selected_file_id
主人：「唸摘要」
  -> 讀 cached summary 或 enqueue summary job
  -> 阿福用語音摘要
```

### 搜尋契約

```json
{
  "search_session_id": "stable-session-id",
  "intent": "file_search",
  "query": "找合約",
  "category": "contract",
  "fallback_level": 0,
  "page_size": 5,
  "candidates": [
    {
      "file_key": "stable-file-id",
      "title": "filename.pdf",
      "source": "google_drive",
      "path_hint": "safe display path",
      "score": 123.4,
      "matched_keywords": ["合約", "客戶", "簽約"],
      "summary": "短摘要"
    }
  ]
}
```

### 權重原則

- 檔案至少要能連到多個關鍵字，不只靠檔名。
- 關鍵字重疊比例越高，排序越前。
- 使用者說「不是」時，當頁候選要降權。
- 主類別耗盡後才切到二號關鍵字組，例如合約 -> 公證書 / 授權書 / MOU / 簽證。
- 搜尋中可以先回候選，同時後端繼續補索引與補摘要。

## LINE 群組檔案 vault 設計

當阿福被加入 LINE 群組時：

1. 取得 inviter UID、group ID、group name。
2. 在 inviter owner vault 建立群組資料夾。
3. 群組內任何人上傳的檔案，都歸入該 inviter owner vault 的 group folder。
4. 群組成員找檔案時，查這個 group folder。
5. VPS 端保留 group vault metadata，並定期同步索引。

建議 vault key：

```text
owner_uid/<line_group_id>/<normalized_group_name>/
```

## 權限與隱私

阿福要找得到，就要有授權。沒有授權就找不到。

| 權限 | 用途 |
|---|---|
| Microphone | 語音指令、push-to-talk |
| Speech / STT | 轉文字 |
| Audio playback | TTS / voice bank |
| Location | GPS context、附近餐廳、出行與安全 |
| HealthKit | 健康與急救照顧 |
| Photos | 圖片分析 |
| Google OAuth | Calendar / Drive |
| Files / Drive providers | 檔案索引與搜尋 |
| Background modes | 長任務、音訊、定位相關能力 |

HealthKit 資料不得直接送進第三方 AI 做自由推理。需要明確資料最小化與用途限制。

## AudioSession 規則

這段不要再改壞。

```swift
try session.setCategory(.playAndRecord, mode: .default, options: [.defaultToSpeaker, .allowBluetoothHFP])
try session.setActive(true)
try session.overrideOutputAudioPort(.speaker)
```

規則：

- `overrideOutputAudioPort(.speaker)` 必須在 `setActive(true)` 之後。
- 不要在 `stopRecording()` 裡切 `.playback` 或 `setActive(false)`。
- 阿福播放 TTS 時，不應同時把自己的聲音當成新指令錄進去。
- `tts()` 要檢查 HTTP status；如果收到 JSON error，不要丟給 `AVAudioPlayer`。

常見錯誤：

| 錯誤 | 原因 |
|---|---|
| `Code=-50` | AudioSession 操作順序錯 |
| `'typ?'` | `AVAudioPlayer` 收到 JSON，不是 mp3 |
| 沒聲音 | speaker override 失效或 TTS API 失敗 |
| 鎖屏切斷 | 背景音訊/聆聽策略沒有被 iOS 接受 |

## Build

### Generic build

```bash
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
xcodebuild \
  -project /Users/norikaoda/Dropbox/Alfred/Alfred/Alfred.xcodeproj \
  -scheme Alfred \
  -configuration Debug \
  -destination 'generic/platform=iOS' \
  build
```

### 實機 build

```bash
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
xcodebuild \
  -project /Users/norikaoda/Dropbox/Alfred/Alfred/Alfred.xcodeproj \
  -scheme Alfred \
  -configuration Debug \
  -destination 'id=<xcode-device-id>' \
  -derivedDataPath /private/tmp/alfred-dd \
  DEVELOPMENT_TEAM=<team-id> \
  CODE_SIGN_STYLE=Automatic \
  -allowProvisioningUpdates \
  build
```

### 實機安裝

```bash
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
xcrun devicectl device install app \
  --device <devicectl-device-id> \
  /private/tmp/alfred-dd/Build/Products/Debug-iphoneos/Alfred.app
```

### 實機啟動

```bash
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
xcrun devicectl device process launch \
  --device <devicectl-device-id> \
  <bundle-id>
```

## 測試

### 後端 smoke

```bash
cd /Users/norikaoda/Dropbox/Alfred/Alfred
ALFRED_SSH_HOST=sportverse ./scripts/alfred_smoke.sh
```

### 必跑實機情境

- 打開 app，確認是原本黑金零介面，不是舊 clone 的醜 UI。
- 帽子 icon 存在。
- 金色狀態點在正上方置中。
- 按住中央入口說話，阿福能收到。
- 阿福回話要從手機 speaker 出聲。
- 阿福播放時不要把自己的聲音錄成新指令。
- 問「我這週有什麼行程」，要走 Calendar。
- 問「我肚子餓了附近吃什麼」，要需要 GPS context。
- 問「找合約」，要走檔案候選，不可直接亂答。
- 說「不是」，要下一頁。
- 選候選後說「唸摘要」，要摘要該候選。
- 鎖屏、解鎖、切背景後，狀態不能亂跳或無限閃麥克風。

### Chaos 測試方向

人類不會照腳本用，所以要亂測：

- 很短的話：「欸」、「不是」、「要」、「第 2 個」。
- 模糊需求：「那份文件」、「上次那個」、「公司那個合約」。
- 連續打斷：錄音、播放、再錄音、鎖屏、回前景。
- 無授權：沒 Google、沒 GPS、沒 HealthKit 時要明確失敗。
- 長任務：摘要大型文件時先回狀態，不卡前台。
- 錯誤檔案：候選錯了要能翻頁，不要一直回同一份。

## App Store 前檢查

| 項目 | 要求 |
|---|---|
| 麥克風 | 明確用途，錄音時有系統/介面指示 |
| 背景音訊 | 只宣告實際需要的模式 |
| 定位 | 說明附近建議、行程、安全與情境用途 |
| HealthKit | 不得做不符合 Apple 規範的 AI 資料外送 |
| Google OAuth | scope 必須和功能一致 |
| AI 第三方揭露 | Gemini / TTS / STT 服務需在隱私政策揭露 |
| 使用者刪除資料 | owner vault、索引、token 要能撤回 |
| 危險動作 | 發送、刪除、分享、撥打、付款都要 approval gate |

## Git 規則

- Commit 前先確認在 `~/Dropbox/Alfred/Alfred/`。
- 不要提交舊 clone。
- 不要把 build artifacts、DerivedData、臨時測試 HTML 塞進 repo。
- 如果同檔案已有別人改動，先看 diff，不要直接覆蓋。
- 每個 commit message 要能說明產品行為變更。

## 相關文件

- `CRITICAL_README.md`：開工必讀，路徑與血淚坑。
- `docs/ALFRED_PRODUCT_ARCHITECTURE.md`：產品架構與 file-vault contract。
- `TEST_REPORTS.md`：舊測試報告。
- `DEMO_DAY.md`：展示相關筆記。
- `PITCH.md`：產品敘事。
- `scripts/alfred_smoke.sh`：後端 smoke 測試。

## 現在的產品目標

下一個可賣錢版本不是堆更多功能，而是把管家主線做穩：

1. 語音永遠能聽、能回、能出聲。
2. 行程、附近餐廳、GPS、健康照顧要能走正確工具。
3. 檔案搜尋必須用檔案地圖，候選、翻頁、選取、摘要要 100% 成立。
4. LINE/Web/Admin 只是替代入口與保險絲，不取代阿福作為手機管家的核心。
5. 所有長任務都非同步，所有危險動作都要主人確認。

阿福的方向很清楚：讓主人少想一步，但永遠知道阿福正在做什麼。
