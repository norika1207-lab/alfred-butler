# Alfred iOS App — 後端 API 交接文件

> 給本地 Claude Code session 讀的。VPS 後端已完成，iOS App 只需接 API。

## 後端位置
```
Base URL: https://YOUR_BACKEND_HOST/alfred/api
Auth: 無（單人 App，直接打）
```

## 核心 API（按優先順序）

### 1. 語音對話（最核心）
```
POST /chat
Body: { "message": "string", "history": [{"role":"user","content":"string"}] }
Response: {
  "text": "string",          // 阿福回應文字
  "card": { "title":"", "content":"", "type":"" } | null,
  "action": { "type":"speak_translation"|"request_upload"|"start_ambient"|... } | null
}
```

### 2. 問安（App 開啟時呼叫）
```
GET /greet
Response: { "text": "string", "first_time": bool }
```
first_time=true 時，text 是自我介紹 + 問城市，App 需顯示並等用戶回覆。

### 3. TTS（文字轉語音）
```
POST /tts
Body: { "text": "string" }
Response: audio/mpeg binary
```
中文自動用 Michael Caine 聲音（ElevenLabs eleven_multilingual_v2）

### 4. 語音轉文字
```
POST /transcribe
Body: multipart/form-data, file=<audio m4a/wav/webm>
Response: { "transcript": "string" }
```

### 5. 即時翻譯
```
POST /translate
Body: { "text": "string", "target_lang": "en|ja|ko|fr|es|de|th", "mode": "interpret" }
Response: { "original": "string", "translated": "string", "target_lang": "string" }

POST /translate/tts  ← 翻譯 + 直接回音頻
Body: multipart/form-data: text, target_lang, mode
Response: audio/mpeg
```

### 6. GPS 位置上傳（背景持續）
```
POST /location/update
Body: { "points": [{ "lat": 0.0, "lng": 0.0, "speed": 0.0, "heading": 0.0, "accuracy": 0.0, "ts": "ISO8601" }] }
```

### 7. 情境感知（到公司/回家觸發）
```
GET /location/context
Response: {
  "context": "office|home|gym|unknown",
  "name": "string",
  "greeting": "string",          // 非空時主動說出來
  "checkin_recorded": bool       // 是否自動打卡了
}
```

### 8. 家人位置
```
GET /family/members
Response: [{ "id", "name", "relation", "lat", "lng", "address",
             "last_seen", "battery", "is_home" }]

GET /family/alerts   ← 未確認警報
Response: [{ "id", "name", "message", "severity": "warning|critical" }]

POST /family/alerts/{id}/ack   ← 主人確認看到
```

### 9. 家人加入（QR 邀請流程）
```
POST /family/member
Body: { "name": "string", "relation": "string" }
Response: { "ok": true, "id": int, "name": "string" }

POST /family/invite/{member_id}
Response: { "token": "string", "invite_path": "/alfred/join?t=TOKEN" }

GET /family/join/{token}   ← 家人裝置掃碼
Response: { "ok": bool, "member_id": int, "name": "string" }

POST /family/activate
Body: { "token": "string" }
Response: { "ok": bool, "device_token": "string", "name": "string" }

POST /family/location   ← 家人裝置持續上報
Body: { "device_token": "string", "lat": float, "lng": float, "battery": int }
```

### 10. 打卡（透過對話觸發，不需要獨立 API）
說「幫我打卡」「今天在家工作」「出勤報告」給 /chat 即可。
但也可以直接叫 /chat 的 attendance tool。

### 11. 提醒輪詢
```
GET /reminders/pending
Response: [{ "id", "title", "trigger_at" }]
```
每 60 秒輪詢一次，有待推送的提醒就本地顯示。

### 12. 拜訪前提醒
```
GET /visit/prep
Response: { "reminders": [{ "event_title", "person", "suggestion", "minutes_away", "message" }] }
```
每 30 分鐘輪詢，有結果就主動推播。

### 13. 未使用功能提示
```
GET /discover
Response: { "suggestions": [{ "id", "trigger", "desc" }], "tried_count": int }
```

---

## iOS App 要做的事（按優先順序）

1. **語音對話主流程**
   - 按住 → AVAudioRecorder 錄音
   - 放開 → POST /transcribe
   - transcript → POST /chat
   - text → POST /tts → 播音

2. **App 啟動**
   - GET /greet → 顯示文字 + 播 TTS
   - 如果 first_time=true → 等用戶說城市 → POST /chat

3. **背景 GPS**
   - CoreLocation significantLocationChangeMonitoringService
   - 每 30 秒批次 POST /location/update
   - App 進入前景 → GET /location/context，有 greeting 就說出來

4. **家人位置**
   - 輪詢 GET /family/members 每 60 秒
   - 輪詢 GET /family/alerts 每 30 秒，有警報 → push notification

5. **提醒**
   - GET /reminders/pending 每 60 秒
   - 本地 UNUserNotificationCenter 觸發

6. **翻譯模式**
   - 用戶說「跟他說...」→ POST /chat → 收到 action.type=speak_translation
   - action.translated + action.lang → POST /translate/tts → 播音
   - 同時大字顯示翻譯文字給對方看

---

## 注意事項

- 所有 API 無需 auth header，直接打
- TTS 回傳 audio/mpeg binary，直接 AVAudioPlayer 播放
- /chat 的 history 格式：`[{"role":"user"|"assistant","content":"string"}]`
- 最多傳最近 10 筆 history
- 城市設定完成後 first_time 就不會再 true

## Git Repo
VPS: `/opt/alfred/`
Web PWA 參考實作: `/opt/alfred/frontend/index.html`（1200 行，有所有 API 呼叫的 JS 範例）
