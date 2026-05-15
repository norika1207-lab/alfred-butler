# CRITICAL_README — 阿福 (Alfred) iOS App 必讀

> 這份文件記錄血淚教訓和重要架構決策。改動任何東西前請先讀完。

---

## 專案實際路徑（非常重要）

| 路徑 | 說明 |
|------|------|
| `~/Dropbox/Alfred/Alfred/` | **正確路徑** — Xcode 實際 compile 的位置，所有改動在這裡 |
| `~/Dropbox/Mac (2)/Documents/Alfred/` | **舊 clone，不要動** — 跟 build 完全無關 |
| `~/Documents/Alfred/` | **另一個不相關路徑** — 不要在這裡改程式 |

所有 iOS 程式改動必須在 `~/Dropbox/Alfred/Alfred/` 進行。

---

## 架構總覽

### Swift 檔案清單

```
Alfred/Core/
  AlfredViewModel.swift   主 ViewModel，狀態機、action dispatch、photoPicker
  AlfredAPI.swift         API client，所有後端通訊
  AudioEngine.swift       錄音/播音引擎（AVAudioSession 管理）
  AmbientRecorder.swift   被動環境錄音（每30秒上傳一個 chunk）
  PhotosManager.swift     iOS Photos 權限 + 圖片選取邏輯

Alfred/Features/Chat/
  AlfredView.swift        主畫面（語音按鈕、AmbientButton overlay、PhotoGridView sheet）

Alfred/Features/Ambient/
  AmbientButton.swift     金色環形按鈕，長按啟動/停止被動錄音

Alfred/Features/Photos/
  PhotoGridView.swift     相片格狀瀏覽 sheet
  PhotoPickerRequest.swift  PHPickerViewController wrapper
```

### 後端

- **URL**: `https://YOUR_BACKEND_HOST`
- **Port**: `9001`
- **SSH alias**: `YOUR_SERVER`（即 `ssh YOUR_SERVER`）
- **後端 code**: `/opt/alfred/backend/main.py`
- **Restart**: `ssh YOUR_SERVER 'systemctl restart alfred'`

---

## AudioSession 注意事項（血淚教訓）

### 順序很重要
```swift
// 正確順序（缺一不可）
try session.setCategory(.playAndRecord, ...)
try session.setActive(true)
try session.overrideOutputAudioPort(.speaker)  // 必須在 setActive(true) 之後
```

### 不能用 `.playback` 模式
`overrideOutputAudioPort(.speaker)` 在 `.playback` 模式下**無效**，聲音會從耳機出。
必須用 `.playAndRecord` 模式才能成功 override 到 speaker。

### `stopRecording()` 不要動 session
`stopRecording()` 只要 `recorder?.stop()` 就好，**不要切換 session category**，
讓 `play()` 自己管理 session。如果 stopRecording 切換 session，play 時 speaker 會出問題。

```swift
// 正確的 stopRecording
func stopRecording() -> Data? {
    recorder?.stop()
    recorder = nil
    // 不動 session — play() 自己負責
    guard let url = recordingURL else { return nil }
    ...
}
```

---

## API Auth 注意事項

### 所有後端 API call 都要帶 auth
```swift
private func authorized(_ req: inout URLRequest) {
    req.setValue("application/json", forHTTPHeaderField: "Content-Type")
    if let t = token { req.setValue("Bearer \(t)", forHTTPHeaderField: "Authorization") }
}
```

呼叫任何需要後端的 function 都要先呼叫 `authorized(&req)`。

### TTS 特別要帶 auth
`tts()` **必須**呼叫 `authorized(&req)` 並且檢查 HTTP status code。

如果沒有帶 auth，後端會回 JSON 格式的 error response，
AVAudioPlayer 嘗試播放 JSON 時會 throw `'typ?'` error（非常難 debug）。

```swift
// 正確的 tts()
func tts(text: String) async throws -> Data {
    var req = URLRequest(url: URL(string: "\(base)/tts")!)
    req.httpMethod = "POST"
    authorized(&req)          // 必須有！
    req.httpBody = try JSONEncoder().encode(["text": text])
    let (data, resp) = try await session.data(for: req)
    if let http = resp as? HTTPURLResponse, !(200...299).contains(http.statusCode) {
        throw URLError(.badServerResponse)  // 必須有！
    }
    return data
}
```

---

## Sportverse 伺服器注意事項（非常重要）

**絕對不要 kill 不認識的 process！**

| Port | 服務 | 說明 |
|------|------|------|
| 8001 | 賽馬/turfenix backend | 與阿福無關 |
| 9001 | 阿福 backend | `systemctl restart alfred` |

所有 service 都跑在 `YOUR_SERVER` user 下。Kill 任何 process 前先確認是什麼。


---

## App Store / 阿福模式審查策略

阿福模式不可描述成「全天候監聽」。上架版定位是：**使用者主動開啟的私人語音日誌與生活記憶整理工具**。

強制規則：
- 不自動開麥；每次開啟都必須主人進 App 按下並看見宣告。
- 開啟中必須有明確狀態，並每 2 小時發本機透明提醒。
- 沒有聲音的片段本地丟棄，不上傳、不轉逐字稿。
- 主人可按鈕關閉，也可說「阿福你先關閉 / 阿福你先不要聽 / 阿福你去休息」。
- 找文件、寄 Email、傳訊息、改行事曆等對外或敏感動作，必須由主人要求或確認。
- App Store 文案用 personal voice journal / life log / private transcript / meeting notes；不要用 always listening / background monitoring / 整天監聽。

## 已實作功能清單

- **語音對話**：STT → Chat（SSE stream）→ TTS，完整對話流程
- **即時 ack**：「阿福已經收到」— 說完話立刻播放，不等 AI 回應
- **相片分析**：iOS Photos picker → `/api/analyze-photo`，讓阿福看相片
- **被動環境錄音**：AmbientRecorder，金色按鈕啟動，每30秒上傳一個 chunk
- **LINE 傳訊**：後端已有，需主人的 LINE user ID 綁定後才能用
- **Google Calendar**：多帳號切換（工作/個人）
- **Google Drive 查詢**：搜尋文件
- **翻譯模式**：`speak_translation` action，即時口譯
- **位置追蹤**：定期上傳主人位置
- **家庭成員位置**：查看家庭成員的位置和狀態

---

## 開發流程

1. **所有改動在 git worktree（沙盒）進行**，測試通過才 merge 回 main
2. **iOS 改動**：在 `~/Dropbox/Alfred/Alfred/` 編輯，用 Xcode 26.4 build
3. **後端改動**：編輯 `/opt/alfred/backend/main.py`，然後 `ssh YOUR_SERVER 'systemctl restart alfred'`
4. **Commit 前**：確認 `git diff HEAD` 符合預期，不要 commit README.md 以外的雜檔
5. **Merge 前**：在實機上測試語音對話、TTS 聲音從 speaker 出、相片分析

---

## 常見問題排解

### TTS 沒聲音 / 從耳機出
→ 檢查 `play()` 裡 `overrideOutputAudioPort(.speaker)` 是否在 `setActive(true)` 之後

### AVAudioPlayer throw `'typ?'`
→ TTS endpoint 回傳了 JSON（通常是 401 Unauthorized），不是音訊資料
→ 檢查 `tts()` 有沒有呼叫 `authorized(&req)`

### 錄音後無法播放
→ 確認 `stopRecording()` 沒有切換 session category

### 後端 502 / connection refused
→ 先確認 `systemctl status alfred`，可能需要 restart
→ 不要 kill 其他 process

---

*Last updated: 2026-04-28*
