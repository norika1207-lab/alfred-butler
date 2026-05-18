<!-- ALFRED_MANDATORY_SESSION_BOOTSTRAP -->
# MANDATORY FIRST STEP FOR ANY ALFRED / AFU / ALICE REQUEST

Before any analysis, file edit, DB write, backend patch, demo edit, iOS change, systemd change, or conclusion about Alfred / Afu / Alice / File Map, run:

```bash
/usr/local/bin/alfred-context-guard
```

This is required even in a new session. Do not patch first and read docs later. See `/opt/alfred/ALFRED_MANDATORY_SESSION_BOOTSTRAP.md`.

<!-- /ALFRED_MANDATORY_SESSION_BOOTSTRAP -->

# Rollback 救命表 — 同步 setup 出問題時

> **時間**：2026-05-14 10:30 的 sync setup
> **動作**：VPS push GitHub / 公司本機加 github remote / CLAUDE.md PREFLIGHT / hook 升級

## 還原點清單

### VPS 上的 git tag
| Tag | 對應狀態 |
|---|---|
| `pre_github_sync_20260514` | 今天 setup 前的 HEAD（含 6 unpushed commits） |
| `github_origin_before_sync` | GitHub `origin/main` push 前的 commit（523594e） |

### 公司本機 backup（時間戳 `20260514_103041`）
| 檔案 | Backup 位置 |
|---|---|
| `~/.claude/settings.json` | `~/.claude/settings.json.bak_20260514_103041` |
| `~/.claude/alfred_keyword_hook.sh` | `~/.claude/alfred_keyword_hook.sh.bak_20260514_103041` |
| `~/.claude/alfred_keyword_map.txt` | `~/.claude/alfred_keyword_map.txt.bak_20260514_103041` |
| `~/Documents/alfred/CLAUDE.md` | `~/Documents/alfred/CLAUDE.md.bak_20260514_103041` |

### 公司本機 git tag
- `pre_sync_setup_20260514` ← clone 完成那一刻

---

## 個別動作的 Rollback

### A. GitHub push 想撤回（不推薦，除非真的有問題）

```bash
ssh root@31.97.221.240 'cd /opt/alfred && git push --force-with-lease origin github_origin_before_sync:main'
```

**注意**：force push 會改 GitHub 歷史，如果別人已經 pull 過會打架。但這個 repo 只有你自己，安全。

### B. VPS denyCurrentBranch 想撤回（變回擋 push）

```bash
ssh root@31.97.221.240 'cd /opt/alfred && git config receive.denyCurrentBranch refuse'
```

### C. CLAUDE.md PREFLIGHT 區塊想拿掉

```bash
cp ~/Documents/alfred/CLAUDE.md.bak_20260514_103041 ~/Documents/alfred/CLAUDE.md
```

### D. Hook 自動灌入 PREFLIGHT 想關掉

```bash
cp ~/.claude/alfred_keyword_hook.sh.bak_20260514_103041 ~/.claude/alfred_keyword_hook.sh
```

要徹底關閉 hook（連 keyword 觸發都不要）：

```bash
cp ~/.claude/settings.json.bak_20260514_103041 ~/.claude/settings.json
```

### E. 公司本機 github remote 想拿掉

```bash
cd ~/Documents/alfred && git remote remove github
```

---

## 完全回到 2026-05-14 早上 10:30 的狀態

**VPS：**
```bash
ssh root@31.97.221.240 '
cd /opt/alfred
git push --force-with-lease origin github_origin_before_sync:main
git config receive.denyCurrentBranch refuse
git reset --hard pre_github_sync_20260514
'
```

**公司本機：**
```bash
cp ~/.claude/settings.json.bak_20260514_103041 ~/.claude/settings.json
cp ~/.claude/alfred_keyword_hook.sh.bak_20260514_103041 ~/.claude/alfred_keyword_hook.sh
cp ~/.claude/alfred_keyword_map.txt.bak_20260514_103041 ~/.claude/alfred_keyword_map.txt
cp ~/Documents/alfred/CLAUDE.md.bak_20260514_103041 ~/Documents/alfred/CLAUDE.md
cd ~/Documents/alfred && git remote remove github
rm -rf /tmp/alfred_preflight_flags  # 清 hook flag
```

---

## 同步打架時的救命

### 公司想 push 但被擋（家裡也改了）

```bash
cd ~/Documents/alfred
git pull --rebase origin main   # 把家裡的 commit 接到你的之前
# 如果有 conflict → 編輯衝突檔 → git add → git rebase --continue
git push origin main
```

### Pull 進來把本機未 commit 改動弄丟了

```bash
cd ~/Documents/alfred
git reflog                       # 找 pull 前的 HEAD
git reset --hard <pull前HEAD>    # 回到 pull 前
git stash                        # 暫存本機改動
git pull
git stash pop                    # 改動拿回來
```

### VPS 上 work 完忘了 commit，公司 push 把它覆蓋了

不會發生 — `receive.denyCurrentBranch=updateInstead` 會檢查 VPS working tree 有沒有未 commit 的改動，有的話會擋 push 並印錯誤訊息。

---

## 緊急時找誰

主人本人。她比 Claude 更知道哪一條 .bak 是哪個視窗失敗的還原網。
