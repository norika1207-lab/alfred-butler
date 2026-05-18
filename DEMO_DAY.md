<!-- ALFRED_MANDATORY_SESSION_BOOTSTRAP -->
# MANDATORY FIRST STEP FOR ANY ALFRED / AFU / ALICE REQUEST

Before any analysis, file edit, DB write, backend patch, demo edit, iOS change, systemd change, or conclusion about Alfred / Afu / Alice / File Map, run:

```bash
/usr/local/bin/alfred-context-guard
```

This is required even in a new session. Do not patch first and read docs later. See `/opt/alfred/ALFRED_MANDATORY_SESSION_BOOTSTRAP.md`.

<!-- /ALFRED_MANDATORY_SESSION_BOOTSTRAP -->

# Demo Day 即時應變手冊

> **核心：邊 demo 邊改，遇到 bug 不慌。**

## Demo 前 5 分鐘檢查（一次完成）

打開 terminal 跑：
```
bash /tmp/alfred_emergency.sh status
```
應該看到：
- `/api/greet → HTTP 200` ✅
- iPhone device 在 list ✅
- alfred app pid 在跑 ✅
- git log 含 `c5dd5dc 零介面：拿掉 4 個 sheet`

任何一項 ❌ 就跑：
```
bash /tmp/alfred_emergency.sh restart-server  # 後端死 → 重啟
bash /tmp/alfred_emergency.sh reset            # 從頭跑 onboarding
```

---

## Demo 中遇到 bug 的 3 條反應路徑

### 🟢 微小 bug（可以靠話術 cover）
- 阿福某句話奇怪
- TTS 有點怪音

→ **不要停**：「阿福剛在學新東西，繼續」自然帶過。Demo 結束後再修。

### 🟡 中等 bug（需要立刻 fix）
- 阿福念啟動語自己念完了 → onboarding 卡住
- 阿福「我這邊還沒連結 Google 日曆」沒推 OAuth card
- 某句話又有「小芸」出現

→ **30 秒處理**：
1. 對老闆說：「請給我一分鐘，阿福剛遇到一個小狀況」
2. Cmd+Tab 切到 Mac
3. 切到 **Claude Code 視窗**，type 一句話描述 bug：
   > **「阿福剛剛 X，要改成 Y」**
4. 我會立刻 patch + 自動 redeploy（約 20-30s）
5. 你 iPhone 上 force quit alfred，重開 → 繼續 demo

### 🔴 大 bug（rollback 才能救）
- App 直接 crash launch 不起來
- LLM response 完全亂掉
- 整個 backend service 死

→ **30 秒救：**
```bash
# 1. 後端死 → 重啟
bash /tmp/alfred_emergency.sh restart-server

# 2. App 死 → 重 build install
bash /tmp/alfred_emergency.sh reinstall

# 3. 整個壞掉 → rollback 到 demo-ready 穩定版
bash /tmp/alfred_emergency.sh rollback-stable
```

`rollback-stable` 會回到 commit **c5dd5dc**（零介面 demo-ready 版），含 anti-lie + onboarding 修好。

---

## 跟 Claude Code（我）溝通的 3 種句型

直接 type 在這個 Claude Code 視窗，不需要解釋背景，我都記得。

**回報 bug：** 直接形容你看到/聽到什麼
- 「阿福念啟動語會自己念完」
- 「我說『有什麼會』他說沒有但沒推 OAuth card」
- 「按頭像沒反應」
- 「阿福說了『大安森林公園』之類的假位置」

**改設計：** 直接說新需求
- 「啟動語改成『阿福，我準備好了』」
- 「翻譯模式不要說『請稍候』，直接開始聽」
- 「行事曆失敗訊息改溫和一點」

**Rollback：**
- 「rollback 上一版」
- 「回到有 voice bank 的版本」

我修完會回你「裝好了 PID xxx」+ 改了什麼，你 force quit alfred app 重開繼續。

---

## Demo 中可能遇到的「已知 bug pattern」+ 快速應對

| 你說了 | 阿福做了 | 應對 |
|---|---|---|
| 「我明天有什麼會」 | 念了「下午三點開會」假時間 | 我這邊 anti-lie 應該會擋。如果漏了 → 跟我說，我加 pattern |
| 「家人在哪」 | 念了「最後位置在 X」 | 後端 hallucination。跟我說立刻清 |
| 「幫我看出勤」 | 念了「本月 18 天」 | 這目前 anti-lie 沒擋（會 hallucinate）— demo 前要不要擋？跟我說 |
| 「翻譯」 | 沒進入翻譯狀態 | 後端 LLM 沒 call tool — 跟我說，我看 prompt |
| 任何 | App crash 退到 home screen | `bash /tmp/alfred_emergency.sh reinstall` |

---

## 這個 Claude Code 視窗會 stay active 多久？

Anthropic conversation persistence ~90 天。**不要關 terminal、不要關這個視窗**。

如果不小心關了：在 terminal 重啟 `claude` 命令，前面對話 context 會有部分自動恢復（auto-memory 系統 + git log）。

---

## Demo 順序建議（穩中求快）

1. **開 app（已 --reset 過）** → onboarding 文字 + 黑底頭像（**無聲**）
2. **念啟動語** → 認證 → 阿福確認語
3. **「幫我看辦公室狀況」** → 阿福口頭講（**沒 sheet**）
4. **「家人現在在哪」** → 阿福口頭講
5. **「翻譯模式」** → 阿福進入翻譯
6. **「我的出勤記錄」** → 阿福口頭講
7. **Highlight：「幫我加會議」** → OAuth card → 點按鈕 → Safari → 同意 → 切回 → 「我明天有什麼會」 → 阿福查真實 calendar
8. **拿出 mail：「阿福把出勤紀錄寄 email 給我」** → 收 email
9. （如果有時間）**文件：「幫我看上次那份合約」** → CardView 顯示

**不要 demo 的 prompt**（容易踩雷）：
- 「找我電腦的檔案」（會 hallucinate sample_contract）
- 連續問 calendar 4-5 次（anti-lie 邊角 case）
- 涉及具體人名（會編「小張」「小李」之類）

---

## Backup：完全離線 demo（萬一 server / wifi 都死）

iPhone 上 onboarding 是純本地（不靠 server），所以即使 server 全死，**你仍可以 demo**:
- 開 app → 念啟動語 → 認證進入
- 但之後 chat 會 fail（沒 server）

如果現場 wifi 不穩，告訴我，我準備 offline mode（純語音 fallback 用 voice bank mp3 取代 TTS）。

---

**最重要：放心 demo。任何 bug 我這邊在。**
