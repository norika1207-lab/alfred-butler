# 阿福 Alfred


<!-- BEGIN AUTO_STATUS -->

## ⭐ 開發進度表(自動生成 — last: 2026-05-15 18:50)

> **這份是必讀。Alfred 整個進度都在這。**
> 由 `scripts/generate_status.py` 掃 codebase 自動生成,**不要手動改這段(`<!-- BEGIN/END AUTO_STATUS -->` 之間)**。
> 質化的「65 技能對應現況」+「呵護的是 X」請看 [`docs/ALFRED.md`](docs/ALFRED.md) 第 4 章。

### 規模

| 維度 | 數量 |
|---|---:|
| `backend/main.py` 行數 | 16,715 |
| API endpoints(`@app.*`)| 145 |
| LLM tools | 69 |
| Fastpath 函數(zero LLM)| 17 |
| DB tables(`CREATE TABLE`)| 71 |
| Backend service modules | 9 |
| Populate seed scripts | 6 |
| Scrapers in tree | 11 |
| iOS Swift 檔 | 26 個,共 5,269 行 |
| voice_bank 預錄 mp3 | 3,061 個 |
| `alfred.db` 大小 | 244 MB |
| 主人上傳分析過的檔案 | 41 |

### Fastpath 函數(zero LLM 秒答)

| 函數 | 用途 |
|---|---|
| `_maybe_handle_liveness_fastpath` | ⭐ 你還在嗎 / 你好 / 早安(2026-05-13 加,從 24s → 0.7s) |
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
| `Alfred/AlfredApp.swift` | 60 | App 入口 + consent gate |
| `Alfred/Core/AfuBrainGate.swift` | 213 | MASL gate,destructive action 本地擋 |
| `Alfred/Core/AlfredAPI.swift` | 573 | 後端 API client(含 SSE stream) |
| `Alfred/Core/AlfredViewModel.swift` | 844 | 主 ViewModel,狀態機,action dispatch |
| `Alfred/Core/AliceFastpath.swift` | 288 | 時間/日期/數學/單位/早安謝謝 zero-LLM(待補 liveness) |
| `Alfred/Core/AmbientRecorder.swift` | 222 | 被動環境錄音,120s chunk |
| `Alfred/Core/AudioEngine.swift` | 178 | AVAudioRecorder + AVAudioPlayer |
| `Alfred/Core/AuthManager.swift` | 177 | JWT + Keychain(原 legacy 名,實際多處使用) |
| `Alfred/Core/BackgroundManager.swift` | 193 | reminder / family alert / visit prep 輪詢 |
| `Alfred/Core/ConversationLog.swift` | 44 | 對話歷史寫到 Documents/ |
| `Alfred/Core/HealthKitManager.swift` | 138 | HealthKit + workout sync |
| `Alfred/Core/LocationManager.swift` | 75 | CLLocationManager + /api/location/update |
| `Alfred/Core/PermissionCascade.swift` | 145 | 漸進式權限請求 |
| `Alfred/Core/PhotosManager.swift` | 91 | iOS Photos 權限 + 選圖 |
| `Alfred/Core/VoiceBankPlayer.swift` | 90 | 🔴 卸下待補 — 預錄 mp3 抽取播放(0 引用) |
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
| `*.bak*` 檔案 | 105 個 |
| 備份資料夾 | ResourceBackups |
| 舊快照 | ios_latest.zip, ios_app, ios |

### 最近活動

**最近 20 commits**:

```
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
d258ab7 feat: POI Crack A01 — OSM Overpass 全台 35,845 餐廳 + nearby fastpath
f444905 feat: weather fastpath — 主人問天氣不打 LLM,48s -> 2s
5c3cc68 feat: anniversary 主動鏈 — 30/7/1/0 天前自動推送
37a38e4 feat: biggo 接線 + emotional/care 觸發推 LINE
7cf7970 第七視窗整合 — 修速度 / 接 travel_hotels / emotional 主動鏈 / 進度自動化
523594e feat: extras/ — scale-up indexer tools + scrapers
2f1c513 auto: update README.md
e1c03ae auto: update README.md
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

## 📅 2026-05-14 整日修法總結

> 13 個 commits / 11 個 source 檔動到 / 16 個 rollback tags。Backend 全部 deploy 上 VPS 已生效；iOS code 改完 commit 但 **build 待生效**（卡在公司 Mac Xcode signing — 需加 Apple ID）。

### Commits 時序

| 時間 | Commit | 修法 |
|---|---|---|
| 00:16 | `f444905` | weather fastpath — 主人問天氣不打 LLM,48s → 2s |
| 00:37 | `d258ab7` | POI Crack A01 — OSM Overpass 全台 35,845 餐廳 + nearby fastpath |
| 00:44 | `c9e8154` | LINE 對話邏輯 — fastpath chain + 餐飲意圖 + 區名 + history |
| 11:06 | `1ec91ef` | **owner_identity singleton** — 跨 channel 統一主人身份 + LINE/TG 陌生人 gate |
| 11:07 | `e92be48` | **iOS TTS 雜音** — 三個 player 統一 AVAudioSession 設定 |
| 11:21 | `1fa915a` | **6 個答非所問** — 5/14 09:01-09:16 對話實況 root cause |
| 12:31 | `1978d5e` | 中斷點 commit（公司 Mac 移動暫停）|
| 17:36 | `087d6fd` | **旅遊國家層級 fallback** — 日本→東京 / 韓國→首爾 / 19 國熱門城市 |
| 20:09 | `722517a` | **4 層 paranoid defence** — 中文數字 + 紀念日 file skip + post-processing override |
| 20:12 | `8061dce` | **anniversary_fastpath** — 主人問紀念日強制走 DB,不靠 LLM 選 tool |
| 20:13 | `cd2556f` | anniversary_fastpath 連 shared db fix |
| 20:14 | `b7a0842` | anniversary sort key fix (TypeError) |
| 21:33 | `0090dfa` | **iOS conversational mode** — 大頭像 tap toggle,不再 push-to-talk |

### 重大修法分類

#### 1. 主人身份 / 識別（singleton owner across channels）
- `owner_identity` 表（跨 LINE / TG / iOS device 統一主人）
- `strangers` 表（陌生人嘗試紀錄）
- LINE / Telegram webhook 入口加 `is_owner()` gate
- 修 `relationships.relation` 欄位缺（silent SQL fail bug）

#### 2. iOS TTS 雜音（commit e92be48）
- AudioEngine / VoiceBankPlayer / AudioEngine.play 三個 player 統一 `.playAndRecord + .default + .allowBluetoothHFP`
- 取代 `.playback` mode（違反 CRITICAL_README:689 鐵律）
- 取代 deprecated `.allowBluetooth`

#### 3. 6 個答非所問（5/14 早上對話實況）
1. 「阿富你還好嗎」被當重試 → Layer 2 dedup 加豁免 keyword
2. 「我想要吃早餐」靜默無回應 → 加 LLM 失敗 fallback safety net
3. 「漢堡早餐」推油飯 → nearby_fastpath 加料理類型過濾（`_USER_CUISINE_KW` 36 條）
4. AI 新聞重複五篇 → search_news dedup vs conversation_log
5. TechCrunch 被當 filename → file_fastpath skip 加外網 keyword
6. 「昨天 AI 新聞」拒絕 → search_news tool description 禁能力告退

#### 4. 旅遊 hallucination 4 層 paranoid defence
- **Layer 1**: `_COUNTRY_DEFAULT_CITY` 19 國 fallback（日本 → 東京）
- **Layer 2**: 中文數字 days detection（五天/七日/十天）
- **Layer 3**: `_should_skip_file_fastpath` 加紀念日 / 旅遊 keyword
- **Layer 4**: post-processing PARANOID-OVERRIDE — LLM 抗命編「沒資料」也攔

#### 5. Anniversary fastpath（紀念日 0.04s）
- LLM 把「紀念日」當 file_search 搜文件的 bug
- 加 `_maybe_handle_anniversary_fastpath` 強制 intercept
- 連 shared `alfred.db` 撈主人 7 筆紀念日，依距今天天數排序

#### 6. iOS Conversational Mode（commit 0090dfa）
- 大頭像 `DragGesture` (push-to-talk) → `TapGesture` (toggle)
- 進入時阿福主動歡迎：「主人您好，阿福會隨時為您服務，您有需要請隨時跟阿福說」
- AudioEngine 加 VAD（audio level 監聽，1.5s 靜音自動 stop）
- Combine `$state` sink 自動 restart listening 形成多輪對話
- 退出語：「好的主人，阿福先在這候命」
- **AmbientButton 完全不動**（保留會議錄音用途）

### 動過的檔案

```
backend/main.py                          ← 主要,7+ commits
backend/poi_agents/agent_a01_overpass.py ← 新檔
Alfred/Core/AudioEngine.swift            ← TTS 雜音 + VAD
Alfred/Core/AlfredViewModel.swift        ← Conversational mode
Alfred/Features/Chat/AlfredView.swift    ← DragGesture → TapGesture
CLAUDE.md                                ← PREFLIGHT 區段
README.md                                ← 本檔
ROLLBACK.md                              ← 同步救命表
SYNC.md                                  ← 同步 cheat sheet
STATUS.md                                ← auto-generated by pre-commit hook
scripts/build_and_install_ios.sh         ← 新檔
```

### Rollback Tags（16 個）

每個重大修法都有 pre/post tag。完整撤回今天所有修法：

```bash
ssh root@31.97.221.240 'cd /opt/alfred && git reset --hard pre_owner_identity_20260514 && systemctl restart alfred'
```

| Tag | Commit | 修法 |
|---|---|---|
| `pre_weather_fastpath_20260514` | — | weather fastpath 前 |
| `post_weather_fastpath_20260514` | f444905 | weather fastpath 後 |
| `pre_poi_crack_a01_20260514` | — | POI Crack 前 |
| `post_poi_crack_a01_20260514` | d258ab7 | POI Crack 後 |
| `pre_conv_logic_fix_20260514` | — | LINE 對話邏輯前 |
| `post_conv_logic_fix_20260514` | c9e8154 | LINE 對話邏輯後 |
| `pre_owner_identity_20260514` | — | owner_identity 前 |
| `post_owner_identity_20260514` | e92be48 | owner_identity + TTS 雜音 |
| `pre_chat_quality_20260514` | — | 6 個答非所問前 |
| `post_chat_quality_20260514` | 1fa915a | 6 個答非所問後 |
| `pre_travel_country_fallback_20260514` | — | travel 國家 fallback 前 |
| `post_travel_country_fallback_20260514` | 087d6fd | 同上後 |
| `pre_travel_paranoid_20260514` | — | 4 層 paranoid 前 |
| `post_travel_paranoid_20260514` | 722517a | 4 層 paranoid 後 |
| `pre_conversational_mode_20260514` | — | iOS conversational 前 |
| `post_conversational_mode_20260514` | 0090dfa | iOS conversational 後 |
| `pre_github_sync_20260514` | — | 早上首次 push GitHub 前 |
| `pre_sync_setup_20260514` | — | 公司本機 setup 前 |

### Demo Smoke Test（5/14 19:43-20:14 全綠）

| 場景 | 時間 | 結果 |
|---|---|---|
| 「你還在嗎」 | 0.02s | ✅ liveness fastpath |
| 「今天天氣怎麼樣」 | 2s | ✅ weather fastpath（從 48s 修到 2s）|
| 「日本旅行行程四人 兩大兩小最小五歲 五天」 | 1.36s | ✅ country fallback「東京當底」+ 5 天 |
| 「幫我安排旅遊」（無 city）| 4.5s | ✅ 列日本/韓國/歐洲 等熱門目的地 |
| 「東京五天親子行程」 | 1.75s | ✅ 5 天（中文數字 detection） |
| 「我想去韓國七日遊」 | 2.6s | ✅ 首爾當底 + 7 天 |
| 「TechCrunch 國外網站找新聞」 | 13s | ✅ 沒誤觸 file_search |
| 「我有哪些紀念日要記得」 | **0.04s** | ✅ 列 7 個紀念日依近期排序 |
| 「想去尚比亞冷門地方」 | 2.7s | ✅ paranoid override 引導 |

### iOS Build 狀態（待生效）

**Commit `0090dfa` 已 push 但 conversational mode 尚未上手機**。

公司 Mac iOS build 卡在：
1. ~~Xcode 26.3 vs iPhone iOS 26.4.2 SDK 不相容~~ → 已用 `IPHONEOS_DEPLOYMENT_TARGET=26.0 + ECID destination` 繞過
2. **Apple Developer Account 沒設**（公司 Xcode 剛裝乾淨）→ 加 Apple ID 後可成功 build

build 步驟（公司 Mac）：
```bash
# 1. Xcode → Settings (Cmd+,) → Accounts → + → Apple ID → 登入
#    （建議用家裡 Mac 那台一樣的 Apple ID，自動同步 provisioning profile）
# 2. 然後跑：
cd ~/Documents/alfred
export DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer
xcodebuild -project Alfred.xcodeproj -scheme Alfred \
    -destination "platform=iOS,id=00008150-000A19EC3EC0401C" \
    -configuration Debug IPHONEOS_DEPLOYMENT_TARGET=26.0 \
    -allowProvisioningUpdates build
# 3. install:
xcrun devicectl device install app --device E7D552A7-7C53-5E4A-9FFF-7B75CCD98995 \
    ~/Library/Developer/Xcode/DerivedData/Alfred-*/Build/Products/Debug-iphoneos/Alfred.app
```

或者家裡 Mac（`~/Dropbox/Alfred/Alfred/`）`git pull` 後 Xcode GUI 直接 Run。

### 還沒接的「最痛的洞」（明天起的優先序）

| # | 技能 | 狀態 | 為什麼是洞 |
|---|---|---|---|
| 1 | **`emotional/care`** | 🔴 endpoint + 150 mp3 在,推論引擎沒接 | **主人設計初衷** — distress_score → 訂飲料 → 鎖死台詞 |
| 2 | `health_anomaly` + `emergency_call` | 🔴 救命系統 | Twilio 119 三次呼叫鏈未接 |
| 3 | `family_location` 偏離偵測 | 🔴 偏離 inference 未接 | 第 2 鐵則「家人關係」核心 |
| 4 | `pet_care` 被動推論 | 🔴 ambient 狗叫 → 飼料 | BUTLER_BRAIN 第 1 鐵案例 |
| 5 | `meeting_audit` + `silence_radar` + `thanks_nudge` | 🔴 統計鏈未接 | 第 5 鐵則「工作體面」 |

---

> 主人您好，我是您的全能管家。

## 核心價值

**阿福不是助理，是管家。**

- 助理 **等你問**
- 管家 **在你問之前就替你想好了**

### 設計三鐵律

1. **零介面** — 沒有選單、沒有儀表板、沒有聊天文字流。平常只有語音對話；只有在必須「看」的時候才出現介面，例如文件/報告卡片、圖片/相簿、翻譯給對方看的大字、或必要授權。介面本身就是阻力。
2. **橋梁不是代理** — 阿福不代替主人做決定，只確保人對人的關心不因忙碌而斷掉。
3. **永遠先行一步** — 不等你說「提醒我」，在你需要之前就出現。

---

## 系統架構

### 後端
- **Server**: `https://YOUR_BACKEND_HOST`
- **SSH**: `ssh YOUR_SERVER`（alias，即 `ssh root@YOUR_SERVER_IP`）
- **Service**: `systemctl restart alfred`（crash auto-restart，SIGHUP-safe）
- **Code**: `/opt/alfred/backend/main.py`（7500+ 行）
- **LLM**: Google Gemini 2.0 Flash
- **TTS**: ElevenLabs `eleven_multilingual_v2`，cloned voice "Alfred 阿福"
- **STT**: OpenAI Whisper
- **DB**: `/opt/alfred/data/alfred.db`（shared）＋ `/opt/alfred/data/users/<user_id>.db`（per-user）

### iOS Client
- **位置**: `~/Dropbox/Alfred/Alfred/`（Dropbox-synced，Xcode compile 用這裡）
  - ⚠️ `~/Dropbox/Mac (2)/Documents/Alfred/` 是舊 clone，**不要動**
- **Bundle ID**: `Norika.Alfred`
- **Xcode 26.4** — `PBXFileSystemSynchronizedRootGroup`（`Alfred/` 目錄下的 `.swift` 自動加進 target，不用改 pbxproj）

### Swift 檔案結構（實際）
```
Alfred/
├── AlfredApp.swift              ← @main entry；consent gate → AlfredView
├── Core/
│   ├── AlfredViewModel.swift    ← 主 ViewModel：狀態機、action dispatch、photoPicker
│   ├── AlfredAPI.swift          ← API client：chat/tts/transcribe/ambient/location/family
│   ├── AudioEngine.swift        ← AVAudioRecorder + AVAudioPlayer（.playAndRecord 全程）
│   ├── AmbientRecorder.swift    ← 被動環境錄音（每 120 秒上傳一個 chunk；未滿 120 秒停止時只保存有聲音的尾段）
│   ├── PhotosManager.swift      ← iOS Photos 權限 + 圖片選取
│   ├── AuthManager.swift        ← (legacy) email/password JWT
│   ├── BackgroundManager.swift  ← reminder / family alert / visit prep 輪詢
│   ├── ConversationLog.swift    ← 對話歷史寫到 Documents/conversation_log/
│   ├── HealthKitManager.swift   ← HealthKit permission + workout sync
│   └── LocationManager.swift    ← CLLocationManager + /api/location/update
├── Features/
│   ├── Auth/
│   │   ├── LoginView.swift      ← (legacy) email 登入，平時不顯示
│   │   └── ConsentView.swift    ← 第三方 AI 同意聲明（首次啟動顯示）
│   ├── Chat/
│   │   └── AlfredView.swift     ← 主畫面：語音按鈕 + AmbientButton overlay
│   ├── Ambient/
│   │   └── AmbientButton.swift  ← 金色環形按鈕，長按啟動/停止被動錄音
│   ├── Photos/
│   │   ├── PhotoGridView.swift  ← 相片格狀瀏覽 sheet
│   │   └── PhotoPickerRequest.swift ← PHPickerViewController wrapper
│   ├── Office/
│   │   ├── OfficeViewModel.swift
│   │   └── OfficeDashboardView.swift
│   ├── Family/FamilyView.swift
│   ├── Translate/TranslateView.swift
│   └── Attendance/AttendanceView.swift
└── Resources/
    ├── onboarding_greeting.mp3  ← 開機介紹（Alfred 聲音，純介紹，不含啟動語）
    ├── voice_bank_manifest.json ← 待補語音 ID / 情境 / 台詞清單
    └── voice_bank/              ← 469 個情境預錄 mp3
```

---

## AudioSession 關鍵規則（血淚）

```swift
// 正確：play() 裡的順序
try session.setCategory(.playAndRecord, mode: .default, options: [.defaultToSpeaker, .allowBluetoothHFP])
try session.setActive(true)
try session.overrideOutputAudioPort(.speaker)  // 必須在 setActive(true) 之後

// stopRecording() 不要動 session —— play() 自己負責
func stopRecording() -> Data? {
    recorder?.stop()
    recorder = nil
    // 不切 category，不 setActive(false)
    guard let url = recordingURL else { return nil }
    return try? Data(contentsOf: url)
}
```

**不能用 `.playback` category**：`overrideOutputAudioPort(.speaker)` 在 `.playback` 無效，聲音從耳機出。全程維持 `.playAndRecord`。

**常見錯誤碼**：
- `Code=-50 (kAudio_ParamError)`：`setActive(false)` 後又 `setCategory` → 改掉 session 操作順序
- `Code=1954115647 ('typ?')`：AVAudioPlayer 收到 JSON 而非音訊 → `tts()` 忘記帶 `Authorization` header

---

## API Auth 規則

```swift
private func authorized(_ req: inout URLRequest) {
    req.setValue("application/json", forHTTPHeaderField: "Content-Type")
    if let t = token { req.setValue("Bearer \(t)", forHTTPHeaderField: "Authorization") }
}
// 每個後端 API call 都要先呼叫 authorized(&req)
// tts() 特別重要，漏掉會讓 AVAudioPlayer throw 'typ?' error
```

---

## Onboarding 流程

1. App 開啟 → 檢查 `alfred_ai_consent_v1`（UserDefaults）
   - 未同意 → `ConsentView`（列出 Google Gemini、ElevenLabs）→ 同意 → 繼續
2. 進入 `AlfredView` → `vm.onAppear()` → `greet()`
3. `greet()` 偵測 `alfred_onboarded == false`：
   - deviceLogin 拿 token → 阿福先開口請主人按住中間按鈕、照畫面文字完整唸一遍
   - 畫面顯示啟動語；阿福只念「請照畫面唸」，不代念啟動語全文
4. 主人念啟動語 → STT → `sendMessage()` onboarding mode 驗證
   - 通過 → set `alfred_onboarded = true` → 啟動 BackgroundManager / HealthKit / Location
   - 通過後阿福口頭詢問是否連結 Google 帳號；主人答應才顯示 OAuth 授權卡
   - 主人之後說「用 Line 跟阿福對話 / 我不方便講話 / Telegram 連結」才顯示通訊連結卡
   - 不通過 → 保留啟動語提示請重念

**絕不讓阿福代念啟動語全文**（旁人聽到會誤以為認證完成）。Google 連結不是啟動門檻，只是認證後的可選能力；Line / Telegram 只在主人需要文字對話時出現按鈕。WhatsApp 尚未開通，不得假裝可用。

---

## 後端 API 總覽

### Auth
| Endpoint | 說明 |
|---|---|
| `POST /api/auth/device` | device_id → 365 天 JWT，首次自動建 user_db |
| `POST /api/auth/register` | (legacy) |
| `POST /api/auth/login` | (legacy) |

### Chat / TTS / STT
| Endpoint | 說明 |
|---|---|
| `POST /api/chat/stream` | SSE：`delta` / `thinking` / `done` |
| `POST /api/chat` | 非 stream 備用 |
| `POST /api/tts` | `{text}` → mp3 binary（需 auth） |
| `POST /api/transcribe` | multipart audio → `{transcript}` |
| `POST /api/translate/tts` | 翻譯 + 目標語言 TTS |

### 文件分析
| Endpoint | 說明 |
|---|---|
| `POST /api/analyze-photo` | multipart jpeg → Gemini Vision 描述 |
| (via chat tool) | `analyze_contract` tool：分析任意文件類型（PDF/DOCX/Google Drive） |

### Ambient 被動錄音
| Endpoint | 說明 |
|---|---|
| `POST /api/ambient/start` | `{label}` → `{session_id}` |
| `POST /api/ambient/chunk/{id}` | multipart m4a → 追加逐字稿 |
| `POST /api/ambient/stop/{id}` | 關閉 session |
| `POST /api/ambient/rollup/{id}` | 手動觸發中途小結 |

### 位置 / 家庭
| Endpoint | 說明 |
|---|---|
| `POST /api/location/update` | 上傳位置點 |
| `GET /api/location/context` | 根據位置回傳 context（office/home/transit/…） |
| `GET /api/workmode/bootstrap` | App 啟動/認證後預載場景模式、今日行程、待辦、辦公室摘要、最近文件 |
| `GET /api/family/members` | 家庭成員列表 + 位置 |
| `GET /api/family/alerts` | 未讀警示 |
| `POST /api/family/alerts/{id}/ack` | 標記已讀 |

### Google 整合
| Endpoint | 說明 |
|---|---|
| `GET /api/gcal/accounts` | 列出已授權 Google 帳號 |
| `GET /api/gcal/authorize?label=work` | 取得 OAuth URL（帶 `prompt=select_account` 強制選帳號） |
| `GET /api/gcal/callback` | OAuth callback，存 token + 立刻建立 Drive/Mac 索引 |
| `DELETE /api/gcal/accounts/{email}` | 移除帳號 |

### 場景模式 / 工作模式預載
- `AlfredViewModel.preloadSceneMode()` 在已認證啟動、首次認證完成、位置 context 回來後執行。
- 辦公室 GPS → `mode=work`：優先行程、會議、文件、待辦、承諾追蹤與工作 Google Drive。
- 家中 GPS → `mode=home`：優先家人安全、寵物照顧、生活事項。
- 海外 GPS → `mode=travel`：優先翻譯、交通、安全、飯店與行程草案。
- 場景進入語每天每模式最多說一次；若有預錄 `voice_bank/mode_work_enter.mp3` 等檔案，優先播預錄，否則走 TTS。

### 通訊連結
| 平台 | 狀態 | 按鈕連結 |
|---|---|---|
| Line | 已設定，主人可用文字對話 | `https://line.me/R/ti/p/@222ouqpj` |
| Telegram | Bot 已設定，主人按 Start 後建立對話 | `https://t.me/alfred_demo_bot` |
| WhatsApp | 尚未開通 | 不顯示假連結，只提示尚未可用 |

### 檔案下載
| Endpoint | 說明 |
|---|---|
| `GET /alfred/download/{token}` | 一次性下載連結（TTL 30min，用過即廢） |

### 辦公室
- `/api/office/eod-wrap` / `rooms` / `thanks-nudge` / `supplies` / `colleagues`

---

## Google Drive / Mac 檔案索引

### 架構
- 索引存在 **per-user DB**（`/opt/alfred/data/users/<user_id>.db`）
- Mac 本機索引：Mac Agent 定期 push 路徑 → per-user DB
- Google Drive 索引：OAuth callback 觸發 → 立刻建立（personal + shared drives）
- **共用雲端硬碟**：需要 `supportsAllDrives=True`、`includeItemsFromAllDrives=True`、`corpora=allDrives`

### 語意搜尋
- `_extract_keywords()`：把檔案名拆開成關鍵字
- `KEYWORD_SYNONYMS`：中英文同義詞對應（e.g. 合約↔contract、發票↔invoice）
- `_build_keyword_index()`：建立 keyword → file_ids 的倒排索引

### TTS 檔名念法
- `_strip_ext()`：自動去掉 `.docx`、`.pdf`、`.xlsx` 等副檔名，阿福只念檔案名稱本體

---

## 長文回應多管道分發

當阿福的回應超過 500 字（如旅遊行程、報告），**不在畫面上顯示**，改同時發送到：
1. **LINE**（直接傳訊息）
2. **Telegram**（bot 發送）
3. **Gmail**（寄到主人信箱）

超過此長度才觸發，一般對話仍走正常 TTS 播音。

---

## 位置感知 Google 帳號自動切換

`/api/location/context` 回傳 context_type 時，後端自動切換 active Google 帳號：
- `context_type == 'office'` → 切到 `account_work`（user@example.com）
- `context_type == 'home'` → 切回 `account_default`（個人帳號）

---

## App Store 合規狀態

### ✅ 已處理
- **5.1.2(i) 第三方 AI 同意**：首次啟動顯示 `ConsentView`，明確列出 Google Gemini、ElevenLabs
- **2.5.14 被動錄音指示器**：阿福模式開啟時畫面顯示狀態，iOS 也會顯示系統麥克風指示
- **阿福模式 explicit opt-in**：不自動開麥；每次開啟都必須主人進 App 按下並看到宣告後確認
- **靜音不處理**：手機本地先判斷有無聲音，無聲片段直接丟棄，不上傳、不轉逐字稿
- **透明提醒**：阿福模式開啟後每 2 小時排一次本機通知；1 小時太打擾，3 小時太久，2 小時是透明度與低干擾的折衷
- **隨時關閉**：可按鈕關閉，也可說「阿福你先關閉 / 阿福你先不要聽 / 阿福你去休息」

### App Store submission strategy

對 Apple 與陌生用戶，阿福模式的外部定位不是「全天候監聽 AI 管家」，而是：

> **A user-initiated personal voice journaling and life-log assistant.**

中文定位：**使用者主動開啟的私人語音日誌與生活記憶整理工具。**

阿福模式把有聲片段轉成私人逐字稿，整理成生活日誌、會議記錄、待辦、承諾與創意靈感。管家功能是逐字稿與生活日誌的後處理工具箱：主人明確要求或確認後，才使用找文件、查行事曆、草擬訊息、寄信等工具。

App Review Notes 建議文案：

```text
Alfred Mode is an opt-in personal voice journaling and meeting-notes feature. Each session must be manually started by the user after an in-app disclosure. The app only uploads audio segments that contain detected speech; silent segments are discarded locally. Transcripts are used to generate private life logs, meeting notes, reminders, follow-up tasks, and creative reflections. The user can stop recording at any time from the app or by voice command. The app also sends periodic local reminders while Alfred Mode is active. Additional assistant tools, such as file search, calendar help, message drafting, and summaries, are user-initiated or confirmation-gated.
```

### ⚠️ 注意事項
- **背景定位**（2.5.4）：App Review 說明書需提供充分理由
- **ElevenLabs TTS**：需在隱私政策中揭露
- **Google OAuth scope**：申請的 scope 需有對應功能說明
- **HealthKit 資料**：不能傳給第三方 AI（Gemini），需在隱私政策說明
- **隱私政策必寫**：錄音、有聲片段上傳、逐字稿、AI 處理、保存期限、刪除方式
- **文案禁用**：不要寫 always listening / background monitoring / 整天監聽 / 偷偷記錄；改寫 personal voice journal / life log / private transcript / user-initiated Alfred Mode

---

## Sportverse 伺服器安全規則

**Kill 任何 process 前必須先確認！**

| Port | 服務 |
|---|---|
| 8001 | 賽馬/turfenix backend（與阿福無關） |
| 9001 | 阿福 backend |

```bash
# 重啟阿福
ssh YOUR_SERVER 'systemctl restart alfred && systemctl is-active alfred'

# 健康檢查
curl https://YOUR_BACKEND_HOST/alfred/api/greet
```

---

## 維護指南

### 後端部署
```bash
scp /tmp/main.py YOUR_SERVER:/opt/alfred/backend/main.py
ssh YOUR_SERVER 'systemctl restart alfred'
```

### iOS Build
Xcode 26.4 → 選實機 → Cmd+R

### 跨電腦 Build 完整性

目前本機 repo 已把 source、resources、voice bank、備份檔，以及當次 build 產物都 commit 進 git。換另一台電腦時，檔案層面應可完整還原；真正會影響 build 的外部條件如下：

| 條件 | 要求 |
|---|---|
| Xcode | 建議使用 `/Applications/Xcode.app`，目前驗證過 Xcode / iOS SDK 26.4 |
| Apple signing | 需要可用的 Apple Developer Team 與 `Norika.Alfred` provisioning profile，或在 Xcode 重新選 Team |
| 後端 | VPS `YOUR_SERVER` 上的 `alfred.service` 必須 active |
| API base | iOS client 指向 `https://YOUR_BACKEND_HOST/alfred/api` |
| 實機安裝 | iPhone 需解鎖、信任開發者憑證，並由 Xcode/devicectl 安裝 |

已驗證的本機編譯命令：

```bash
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
xcodebuild \
  -project /Users/YOUR_USER/Dropbox/Alfred/Alfred/Alfred.xcodeproj \
  -scheme Alfred \
  -destination 'generic/platform=iOS' \
  -configuration Debug build
```

已驗證的實機安裝：

```bash
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
xcrun devicectl device install app \
  --device <device-id> \
  /Users/YOUR_USER/Library/Developer/Xcode/DerivedData/Alfred-comiywlbirvcrnfmmzrnhngzvdpy/Build/Products/Debug-iphoneos/Alfred.app
```

**CLI build（需先設 developer path）：**
```bash
sudo xcode-select -s /Applications/Xcode.app/Contents/Developer
xcodebuild -project ~/Dropbox/Alfred/Alfred/Alfred.xcodeproj \
  -scheme Alfred \
  -destination 'platform=iOS,name=<裝置名>' \
  -configuration Debug build
```

### UI Test Mode
```bash
# Simulator 直接送 prompt（跳過麥克風）
xcrun simctl launch booted Norika.Alfred --prompt "幫我看辦公室狀況"
```

---

## 常見問題排解

| 症狀 | 原因 | 解法 |
|---|---|---|
| 完全沒聲音 | AudioSession 操作順序錯 | 確認 `play()` 裡 `overrideOutputAudioPort` 在 `setActive(true)` 之後 |
| 聲音從耳機出 | 用了 `.playback` category | 改 `.playAndRecord` |
| AVAudioPlayer throw `'typ?'` | TTS endpoint 回 JSON（401） | `tts()` 加 `authorized(&req)` |
| 後端 502 | Alfred service 掛了 | `ssh YOUR_SERVER 'systemctl restart alfred'` |
| Drive 找不到共用雲端硬碟 | 缺少 `supportsAllDrives` 參數 | 確認 drive_service.py 所有 API call 都帶三個參數 |
| 文件分析沒被觸發 | LLM 沒呼叫 `analyze_contract` tool | 後端 tool description 已改為涵蓋所有文件類型 |

---

## 測試報告與目前品質狀態

完整測試紀錄請看：

```text
TEST_REPORTS.md
/Users/YOUR_USER/Documents/New project 3/alfred_30x_test_report.json
```

### 2026-05-06 測試輪次

| 輪次 | 測試內容 | 結果 | 改進 |
|---|---|---:|---|
| Round 1 | 文件上傳 → 文件解讀摘要 API smoke test | PASS | 後端從「合約專用」改成「通用文件解讀」，非合約不再硬套合約格式 |
| Round 2 | iOS generic build + iPhone install + launch | PASS | 手機端加入 `文件分析` 測試入口，不必只靠語音觸發上傳 |
| Round 3 | 46 個安全 API / 功能群各跑 30 次 | PASS | 1380/1380 通過，核心 safe API surface 穩定 |

### 30x 回歸測試摘要

| 指標 | 數值 |
|---|---:|
| 測試功能群 | 46 |
| 每項重複次數 | 30 |
| 總檢查數 | 1380 |
| 通過 | 1380 |
| 失敗 | 0 |
| 通過率 | 100% |

明確通過的核心項目：

- `files_upload`: 30/30
- `document_analysis`: 30/30
- `translate`: 30/30
- `chat_light`: 30/30
- `greet`, `auth_me`, `setup_status`, `onboard_status`: 30/30
- family / health / office / attendance / location / Drive / Mac status 類安全查詢：全部 30/30

### 和舊 baseline 的差異

| 時間 | 測試 | 結果 |
|---|---|---|
| 2026-04-26 | 50 calls（5 iter × 10 prompts） | 82% hit rate，0 errors，平均延遲 6.7s |
| 2026-05-06 | 46 groups × 30 runs | 100% transport/API pass rate，0 failures |

注意：2026-05-06 的 100% 是「安全可自動驗證 API」通過率，不代表所有真實外部副作用功能都已 production-ready。真實電話、寄信、LINE/Telegram 推播、緊急通知需要 dummy recipient / sandbox channel 後再測。

---

## 已實作功能清單

| 功能 | 說明 |
|---|---|
| 語音對話 | STT → Chat SSE → TTS 完整流程 |
| 即時 ack | 收到語音立刻播「阿福已經收到」，不等 AI |
| 相片分析 | Photos picker → Gemini Vision → 口頭描述 |
| 被動環境錄音 | 金色按鈕啟動，每 120 秒上傳 chunk |
| 文件摘要 | PDF/DOCX/Google Drive 文件 → 讀取內容 → 口頭摘要 |
| Mac 檔案索引 | Mac Agent push → per-user DB → 語意搜尋 |
| Google Drive 索引 | OAuth 後立刻建立，含共用雲端硬碟 |
| 一次性下載連結 | 生成 30min TTL 連結，傳完自動失效 |
| LINE 傳訊 | 後端直接發送（需綁定 LINE user ID） |
| 多管道分發 | 長回應同時傳 LINE + Telegram + Gmail |
| Google Calendar | 多帳號切換（工作/個人），新增/查詢事件 |
| Google Drive 查詢 | 語意搜尋文件 |
| 翻譯模式 | `speak_translation` action，即時口譯 |
| 位置追蹤 | 定期上傳位置，自動切換 Google 帳號 |
| 家庭成員位置 | 查看家庭成員位置和狀態 |
| 辦公室儀表板 | EOD wrap / 會議室 / 感謝 nudge / 耗材 |
| 出勤記錄 | 上下班記錄查詢 |
| HealthKit 同步 | 運動紀錄上傳後端 |
| 第三方 AI 同意 | 首次啟動 ConsentView（App Store 5.1.2(i) 合規） |
| 手機文件分析入口 | iPhone 主畫面 `文件分析` → Files picker → upload → summary card |

---

## 開發歷程

### 2026-04-26：iOS 專案建立
- 從 Xcode boilerplate 建立，整合後端 API
- Build SUCCESS + device JWT auth + smoke test（82% 命中率）

### 2026-04-28：音訊修復 + 功能擴充

**音訊 Bug 根本原因**：`stopRecording()` 後切 `.playback` category → `play()` 再次切換觸發 `Code=-50`；`tts()` 漏帶 Authorization → AVAudioPlayer 收到 JSON → `'typ?'`。

**修法**：
- `AudioEngine.swift`：`stopRecording()` 不動 session；`play()` 全程 `.playAndRecord`
- `AlfredAPI.swift`：`tts()` 加 `authorized(&req)` + HTTP status check

**後端新功能**：
- Google Drive 共用雲端硬碟支援（三個必要 API 參數）
- Per-user 檔案索引（DB 路徑改 `/opt/alfred/data/users/<id>.db`）
- OAuth callback 觸發立即建立索引
- 語意關鍵字搜尋（`KEYWORD_SYNONYMS` + 倒排索引）
- TTS 念檔名不念副檔名（`_strip_ext()`）
- 文件摘要功能（PDF/DOCX/Google Drive 下載後 Gemini 分析）
- 長回應多管道分發（LINE + Telegram + Gmail）
- 一次性下載連結（`GET /alfred/download/{token}`）
- 位置感知 Google 帳號自動切換

**保護規則**：
- 建立 `CLAUDE.md`（每次開工強制讀）
- 建立 `CRITICAL_README.md`（血淚教訓、路徑、架構、注意事項）

### 2026-04-29：App Store 合規

- App Store Review Guidelines 全面檢查（14 項功能逐一比對）
- 新增 `ConsentView.swift`：首次啟動顯示第三方 AI 服務聲明（Google Gemini、ElevenLabs）
- `AlfredApp.swift` 加 consent gate（`alfred_ai_consent_v1` UserDefaults key）
- 通過後進入正常 onboarding 流程，不影響已同意用戶

---

## 自動測試結果（2026-04-26 baseline）

50 calls（5 iter × 10 prompts）— 命中率 82%，0 errors，平均延遲 6.7s

低命中類別：`show_office` 60%、`show_translate` 60%、`show_family` 0%（資料空時 LLM 走文字引導路徑，而非開 sheet）

---

## extras/ — 商品索引擴充工具

`extras/` 資料夾是核心引擎以外的 **規模擴張工具**，不影響主程式運作，只在需要把索引從數千筆推到 10 萬+ 時使用。

```
extras/
├── indexer/
│   ├── worker.py           20-Agent 並發爬蟲（正確版，每關鍵字最多 10,000 筆）
│   ├── wide_worker.py      廣度爬蟲第一批（500+ 關鍵字 × 200 筆 = 10 萬+）
│   ├── wide_worker2.py     廣度爬蟲第二批（再加 1,000 關鍵字，補齊至 10 萬）
│   ├── bulk_index.py       暴力批量索引（每關鍵字 40-60 筆，2,000 個關鍵字）
│   ├── mega_crawl.py       翻頁式大量索引（PChome 單字 25,000 筆 × 100 頁）
│   ├── migrate_to_pg.py    SQLite → PostgreSQL 一次性遷移，含 price_history 種子
│   ├── pg_schema.sql       PostgreSQL schema（支援 price_history、JSONB、tsvector）
│   └── auto_crawl.sh       每日自動爬蟲排程（cron 用）
└── scrapers/
    ├── crowdfunding_scraper.py  wabay + flyingV 領先指標爬蟲（預測 3-12 個月後熱銷品）
    └── taobao_scraper.py        淘寶價格/銷量爬蟲（需 TAOBAO_APP_KEY + TAOBAO_APP_SECRET）
```

詳細說明見 [`extras/README.md`](extras/README.md)。
