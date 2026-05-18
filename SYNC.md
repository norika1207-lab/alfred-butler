<!-- ALFRED_MANDATORY_SESSION_BOOTSTRAP -->
# MANDATORY FIRST STEP FOR ANY ALFRED / AFU / ALICE REQUEST

Before any analysis, file edit, DB write, backend patch, demo edit, iOS change, systemd change, or conclusion about Alfred / Afu / Alice / File Map, run:

```bash
/usr/local/bin/alfred-context-guard
```

This is required even in a new session. Do not patch first and read docs later. See `/opt/alfred/ALFRED_MANDATORY_SESSION_BOOTSTRAP.md`.

<!-- /ALFRED_MANDATORY_SESSION_BOOTSTRAP -->

# 同步 Cheat Sheet — 兩台電腦永遠對齊

## 每天只記這兩條

```bash
cd ~/Documents/alfred
git pull         # 開工前 — 拿家裡昨晚的進度
# ... 改東西、commit ...
git push         # 收工前 — 推到 VPS（VPS working tree 會自動更新）
```

如果 push 時 git 擋你（「remote has new commits」）→ 表示家裡那邊也動了，先 `git pull --rebase` 再 push。

## Remote 設定（已配好）

| Remote | 指向 | 用途 |
|---|---|---|
| `origin` | `root@31.97.221.240:/opt/alfred` | **主同步點**（VPS，內網快） |
| `github` | `git@github.com:norika1207-lab/alfred-butler.git` | 對外備份 / 公開展示 |

平常只跟 `origin` 同步即可。對外要展示 commerce crack / butler brain 那種，再 `git push github main`。

## 為什麼選 VPS 當主同步（不是 GitHub）

1. **家中模式 = 直接在 VPS 上 work**（透過 SSH + Claude）— commit 直接落在 VPS local
2. **VPS 已設 `receive.denyCurrentBranch=updateInstead`** — 公司本機 push → VPS working tree 自動跟著動
3. 內網 SSH 比 GitHub 快，且不依賴 GitHub status
4. GitHub 保留當公開門面 / 災難備份

## 三邊狀態

```
        GitHub (origin/main on GitHub, 對外門面)
           ↑ 偶爾 push（展示時）
           │
        VPS /opt/alfred  ←─── 中央同步點
        origin/main 跟 working tree 永遠同步（denyCurrentBranch=updateInstead）
           ↑↓                
        公司 ~/Documents/alfred (B 模式 working copy)
        origin = VPS / github = GitHub
```

## 萬一打架怎麼辦

git 設計就是防打架的：
- push 時遠端有新 commit → **git 擋你**，要你先 pull
- pull 時同一行兩邊都改 → **跳 merge conflict**，手動選
- 從來不會默默覆蓋

真要出事看 [ROLLBACK.md](ROLLBACK.md)。

## VPS 上家中模式的工作流

家裡晚上直接 SSH 到 VPS work：
```bash
ssh root@31.97.221.240
cd /opt/alfred
# 改東西、commit
git commit -am "fix: xxx"
# VPS 不需要 push（它就是 origin），但要推 GitHub 對外的話：
git push github main  # 或 push origin (no-op, 本地就是 origin)
```

隔天到公司：`git pull` 就拿到。

## 新 session 自動讀 doctrine

公司本機 Claude session 在 `~/Documents/alfred/` 啟動會自動：
1. 讀 `CLAUDE.md` 看到 PREFLIGHT
2. 透過 `~/.claude/alfred_keyword_hook.sh` 自動灌入第 0 章 cheat card

新 Claude 一啟動就知道：第一原理 / 三鐵律 / 5 鐵案例 / 「沒接線不准刪」。

不用你再從零解釋。
