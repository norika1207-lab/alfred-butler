# 阿福 Alfred

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
- **2.5.14 被動錄音指示器**：畫面上有常駐閃爍指示器

### ⚠️ 注意事項
- **背景定位**（2.5.4）：App Review 說明書需提供充分理由
- **ElevenLabs TTS**：需在隱私政策中揭露
- **Google OAuth scope**：申請的 scope 需有對應功能說明
- **HealthKit 資料**：不能傳給第三方 AI（Gemini），需在隱私政策說明

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
