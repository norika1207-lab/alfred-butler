# CLAUDE.md — 阿福 Alfred 專案強制規則

## ⚠️ 開工前必做第一件事

**每次開始任何開發工作，必須先讀：**

```
/Users/norikaoda/Dropbox/Alfred/Alfred/CRITICAL_README.md
```

不讀不准動任何檔案。這是強制規定。

## 最重要的三條規則

1. **正確專案路徑是 `~/Dropbox/Alfred/Alfred/`**
   - `~/Dropbox/Mac (2)/Documents/Alfred/` 是舊 clone，跟 build 完全無關，絕對不要動
   - `~/Documents/Alfred/` 也是錯的
   - 如果 UI 不是黑金零介面、帽子 icon、正上方金色狀態點，先懷疑你開錯專案
   - 錯專案不准 build、不准安裝、不准 commit

2. **所有程式改動必須在 git worktree（沙盒）裡進行**
   - 用 `isolation: "worktree"` 參數
   - 測試確認沒問題才 merge 回 main
   - 不准直接改 main branch 的工作目錄

3. **Sportverse 伺服器上絕對不要 kill 不認識的 process**
   - port 8001 = 賽馬 backend（不是阿福！）
   - port 9001 = 阿福 backend
   - kill 前先確認 PID 對應的是什麼服務
