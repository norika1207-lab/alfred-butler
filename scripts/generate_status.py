#!/usr/bin/env python3
"""阿福 Alfred — 開發進度自動更新腳本

掃 codebase + 對照 65 技能 + 生成檔案地圖 + 寫進 STATUS.md / README.md

用法:
  python3 scripts/generate_status.py                  # 寫 STATUS.md
  python3 scripts/generate_status.py --readme         # 同時更新 README.md 內 AUTO_STATUS 區塊
  python3 scripts/generate_status.py --check          # dry run,只印不寫

每次 commit 自動跑 — 把這個放進 .git/hooks/pre-commit:
  #!/usr/bin/env bash
  python3 /opt/alfred/scripts/generate_status.py --readme
  git add /opt/alfred/STATUS.md /opt/alfred/README.md

定時跑(可選)— crontab:
  */30 * * * * cd /opt/alfred && python3 scripts/generate_status.py --readme >> /var/log/alfred_status.log 2>&1
"""
import os, re, subprocess, datetime, sys
from pathlib import Path
from collections import Counter

ROOT = Path("/opt/alfred")
README_PATH = ROOT / "README.md"
STATUS_PATH = ROOT / "STATUS.md"
README_BEGIN = "<!-- BEGIN AUTO_STATUS -->"
README_END = "<!-- END AUTO_STATUS -->"


def scan_backend():
    main_path = ROOT / "backend" / "main.py"
    src = main_path.read_text()
    return {
        "lines": len(src.splitlines()),
        "size": main_path.stat().st_size,
        "endpoints": re.findall(r'^@app\.(get|post|put|delete|patch)\("(/[^"]+)"', src, re.M),
        "tools": sorted(set(re.findall(r'"name":\s*"([a-z_]+)"', src))),
        "fastpaths": re.findall(r'def (_maybe_handle_\w+_fastpath)', src),
        "tables": re.findall(r'CREATE TABLE IF NOT EXISTS (\w+)', src),
        "services": sorted([p.name for p in (ROOT / "backend").glob("*.py")
                           if not p.name.startswith("populate") and p.name != "main.py"]),
        "populate": sorted([p.name for p in (ROOT / "backend").glob("populate_*.py")]),
        "scrapers": sorted([p.name for p in (ROOT / "backend/scrapers").glob("*.py")
                           if not p.name.startswith("_")]),
        "extras_indexer": sorted([p.name for p in (ROOT / "extras/indexer").iterdir()
                                 if p.is_file()]) if (ROOT / "extras/indexer").exists() else [],
        "extras_scrapers": sorted([p.name for p in (ROOT / "extras/scrapers").iterdir()
                                  if p.is_file()]) if (ROOT / "extras/scrapers").exists() else [],
    }


def scan_ios():
    alfred_dir = ROOT / "Alfred"
    swift_files = []
    for p in alfred_dir.rglob("*.swift"):
        try:
            lc = len(p.read_text(errors="ignore").splitlines())
        except Exception:
            lc = 0
        swift_files.append((str(p.relative_to(alfred_dir)), lc))
    swift_files.sort()

    vb_dir = alfred_dir / "Resources/voice_bank"
    vb_files = list(vb_dir.glob("*.mp3")) if vb_dir.exists() else []

    c = Counter()
    for f in vb_files:
        stem = f.stem
        m = re.match(r'^(.+?)(_\d+)?$', stem)
        c[m.group(1) if m else stem] += 1

    return {
        "swift_files": swift_files,
        "swift_total_lines": sum(lc for _, lc in swift_files),
        "voice_bank_count": len(vb_files),
        "voice_bank_categories": c.most_common(),
    }


def scan_db():
    db_path = ROOT / "data" / "alfred.db"
    if not db_path.exists():
        return {"size": 0}
    return {"size": db_path.stat().st_size}


def scan_data_files():
    files_dir = ROOT / "data" / "files"
    return {
        "uploaded_files": len(list(files_dir.iterdir())) if files_dir.exists() else 0,
    }


def scan_git():
    log = subprocess.run(["git", "-C", str(ROOT), "log", "--oneline", "-20"],
                         capture_output=True, text=True).stdout.strip().splitlines()
    tags = subprocess.run(["git", "-C", str(ROOT), "tag", "--sort=-creatordate"],
                          capture_output=True, text=True).stdout.strip().splitlines()
    return {"recent_commits": log[:20], "tags": tags[:10]}


def scan_survival_evidence():
    """倖存證據 — 絕對不准刪"""
    bak_count = len(list(ROOT.rglob("*.bak*")))
    backup_dirs = [p for p in [ROOT / "ResourceBackups"] if p.exists()]
    snapshot_files = []
    for name in ["ios_latest.zip", "ios_app", "ios"]:
        p = ROOT / name
        if p.exists():
            snapshot_files.append(name)
    return {
        "bak_files_count": bak_count,
        "backup_dirs": [str(p.relative_to(ROOT)) for p in backup_dirs],
        "snapshots": snapshot_files,
    }


SWIFT_ROLES = {
    "AlfredApp.swift": "App 入口 + consent gate",
    "Core/AlfredViewModel.swift": "主 ViewModel,狀態機,action dispatch",
    "Core/AlfredAPI.swift": "後端 API client(含 SSE stream)",
    "Core/AudioEngine.swift": "AVAudioRecorder + AVAudioPlayer",
    "Core/AmbientRecorder.swift": "被動環境錄音,120s chunk",
    "Core/PhotosManager.swift": "iOS Photos 權限 + 選圖",
    "Core/AuthManager.swift": "JWT + Keychain(原 legacy 名,實際多處使用)",
    "Core/BackgroundManager.swift": "reminder / family alert / visit prep 輪詢",
    "Core/ConversationLog.swift": "對話歷史寫到 Documents/",
    "Core/HealthKitManager.swift": "HealthKit + workout sync",
    "Core/LocationManager.swift": "CLLocationManager + /api/location/update",
    "Core/AfuBrainGate.swift": "MASL gate,destructive action 本地擋",
    "Core/AliceFastpath.swift": "時間/日期/數學/單位/早安謝謝 zero-LLM(待補 liveness)",
    "Core/PermissionCascade.swift": "漸進式權限請求",
    "Core/VoiceBankPlayer.swift": "✅ 已接線 — bundle voice_bank / Resources/voices 本地 mp3 播放,fastpath/action 優先使用",
    "Features/Chat/AlfredView.swift": "主畫面,語音按鈕 + AmbientButton overlay",
    "Features/Auth/ConsentView.swift": "第三方 AI 同意聲明(首次啟動)",
    "Features/Auth/LoginView.swift": "🔴 legacy email 登入,平時不顯示",
    "Features/Ambient/AmbientButton.swift": "金色環,長按啟動 ambient",
    "Features/Photos/PhotoGridView.swift": "相片格狀瀏覽 sheet",
    "Features/Photos/PhotoPickerRequest.swift": "PHPickerViewController wrapper",
    "Features/Office/OfficeViewModel.swift": "Office API client",
    "Features/Office/OfficeDashboardView.swift": "Office dashboard(eod/rooms/...)",
    "Features/Family/FamilyView.swift": "家人狀態 view",
    "Features/Translate/TranslateView.swift": "即時翻譯大字 view",
    "Features/Attendance/AttendanceView.swift": "出勤記錄 view",
}

BACKEND_ROLES = {
    "main.py": "FastAPI app entry — 所有 endpoint + tool + chat handler + fastpath chain",
    "office_service.py": "辦公室 dashboard 邏輯(eod/rooms/supplies/colleagues)",
    "shop_service.py": "13 站並發比價引擎(The Commerce Crack)",
    "drive_service.py": "Google Drive index + search(含共用雲端硬碟)",
    "gcal_service.py": "Google Calendar 多帳號 OAuth + events",
    "gmail_service.py": "Gmail 收發 / 草擬",
    "line_service.py": "LINE webhook + 主動推送",
    "telegram_service.py": "Telegram bot",
    "call_service.py": "Twilio 通話 / TwiML",
    "search_service.py": "語意檔案搜尋(vault + drive + mac)",
    "populate_global.py": "🟡 待補(第六視窗卸下)— 全球景點 seed",
    "populate_travel.py": "🟡 待補 — 旅遊行程 seed(BUTLER_BRAIN 第 4 經典案例)",
    "populate_michelin_hotels.py": "🟡 待補 — 米其林飯店 seed",
    "populate_hotels_fixed.py": "🟡 待補 — 飯店 seed",
    "populate_taiwan_restaurants.py": "🟡 待補 — 台灣餐廳 seed",
}

SCRAPER_ROLES = {
    "biggo_scraper.py": "🔴 未接線 — Biggo 比價",
    "books_scraper.py": "博客來",
    "buy123_scraper.py": "東森購物 buy123",
    "carrefour_scraper.py": "家樂福",
    "coupang_scraper.py": "酷澎",
    "elifemall_scraper.py": "東森購物 ETMall",
    "payeasy_scraper.py": "🔴 未接線 — PayEasy 會員爬蟲",
    "pinkoi_scraper.py": "Pinkoi",
    "tkec_scraper.py": "燦坤",
    "trplus_scraper.py": "特力屋",
    "yahoo_scraper.py": "Yahoo 購物",
}

FASTPATH_DESC = {
    "_maybe_handle_liveness_fastpath": "⭐ 你還在嗎 / 你好 / 早安(2026-05-13 加,從 24s → 0.7s)",
    "_maybe_handle_ambient_command_fastpath": "聆聽錄音指令",
    "_maybe_handle_iphone_photo_fastpath": "iPhone 相簿請求",
    "_maybe_handle_meeting_record_fastpath": "會議記錄查詢",
    "_maybe_handle_integration_link_fastpath": "通訊連結(LINE / Telegram / WhatsApp)",
    "_maybe_handle_attendance_fastpath": "出勤記錄",
    "_maybe_handle_google_auth_status_fastpath": "Google 授權狀態",
    "_maybe_handle_quick_lists_fastpath": "快速列表(todo / expense / ...)",
    "_maybe_handle_math_fastpath": "純數學(BUTLER_BRAIN 第 13 鐵則)",
    "_maybe_handle_shopping_fastpath": "比價(The Commerce Crack)",
    "_maybe_handle_travel_fastpath": "旅遊規劃(populate_travel.py DB 接上時)",
    "_maybe_handle_restaurant_fastpath": "餐廳搜尋",
    "_maybe_handle_file_search_fastpath": "檔案搜尋(vault + drive + mac)",
}

VB_SKILL_MAP = {
    "mood_care": "情緒感知 / emotional/care(妳的初衷)",
    "family_safety": "家人關係 / family_alerts / arrivals",
    "travel_mode": "出國 / 旅遊場景",
    "health_monitoring": "健康日常 / log_workout / medication",
    "proactive_check": "主動關心 / health_status 久坐",
    "ack_butler": "⭐ 你還在嗎 / liveness fastpath",
    "weather_general": "天氣編織 / get_weather",
    "promise_tracking": "承諾追蹤 / note_promise",
    "file_search": "檔案搜尋",
    "document_review": "文件分析 / analyze_contract",
    "calendar": "create_calendar_event",
    "approval_gate": "草擬等主人 OK",
    "food_restaurant": "save_food_record / 訂餐廳",
    "error_recovery": "失敗回應",
    "emergency": "生命安全 / health_anomaly",
    "destructive_warn": "不可逆動作警告",
    "ack_anticipate": "anticipatory extras",
    "mode_action": "場景模式動作",
    "ack_short": "短答(我在 / 收到 / 好的)",
    "office_manager": "manager_lens / silence_radar",
    "mode_enter": "場景進入語(work/home/travel)",
    "casual_humor": "英式幽默點到為止",
    "office_expertise": "expertise_finder",
    "money_expense": "record_expense",
    "greet_time": "⭐ 早安 / 午安 / 晚安 / liveness fastpath",
    "office_thanks": "thanks_nudge",
    "filler_thinking": "思考中(< 1s 等待填充)",
    "office_eod": "office/eod-wrap",
    "shutdown_idle": "閒置 / 休眠回應",
    "onboarding": "新人入職 / 首次認證",
    "office_timezone": "timezone_fatigue",
    "office_supply": "辦公耗材",
    "office_silence": "辦公室氣氛 silence radar",
    "office_room": "office/rooms / room-pulse",
}


def render(be, ios, db, data, git, survival):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    L = []
    L.append(f"## ⭐ 開發進度表(自動生成 — last: {now})")
    L.append("")
    L.append("> **這份是必讀。Alfred 整個進度都在這。**")
    L.append("> 由 `scripts/generate_status.py` 掃 codebase 自動生成,**不要手動改這段(`<!-- BEGIN/END AUTO_STATUS -->` 之間)**。")
    L.append("> 質化的「65 技能對應現況」+「呵護的是 X」請看 [`docs/ALFRED.md`](docs/ALFRED.md) 第 4 章。")
    L.append("")

    # 規模
    L.append("### 規模")
    L.append("")
    L.append("| 維度 | 數量 |")
    L.append("|---|---:|")
    L.append(f"| `backend/main.py` 行數 | {be['lines']:,} |")
    L.append(f"| API endpoints(`@app.*`)| {len(be['endpoints'])} |")
    L.append(f"| LLM tools | {len(be['tools'])} |")
    L.append(f"| Fastpath 函數(zero LLM)| {len(be['fastpaths'])} |")
    L.append(f"| DB tables(`CREATE TABLE`)| {len(be['tables'])} |")
    L.append(f"| Backend service modules | {len(be['services'])} |")
    L.append(f"| Populate seed scripts | {len(be['populate'])} |")
    L.append(f"| Scrapers in tree | {len(be['scrapers'])} |")
    L.append(f"| iOS Swift 檔 | {len(ios['swift_files'])} 個,共 {ios['swift_total_lines']:,} 行 |")
    L.append(f"| voice_bank 預錄 mp3 | {ios['voice_bank_count']:,} 個 |")
    L.append(f"| `alfred.db` 大小 | {db['size']/(1024*1024):.0f} MB |")
    L.append(f"| 主人上傳分析過的檔案 | {data['uploaded_files']} |")
    L.append("")

    # Fastpath
    L.append("### Fastpath 函數(zero LLM 秒答)")
    L.append("")
    L.append("| 函數 | 用途 |")
    L.append("|---|---|")
    for fp in be["fastpaths"]:
        L.append(f"| `{fp}` | {FASTPATH_DESC.get(fp, '—')} |")
    L.append("")

    # voice_bank
    L.append(f"### voice_bank 類別(共 {ios['voice_bank_count']:,} 個 mp3)")
    L.append("")
    L.append("| 類別 | 數量 | 對應技能 |")
    L.append("|---|---:|---|")
    for cat, n in ios["voice_bank_categories"][:30]:
        L.append(f"| `{cat}` | {n} | {VB_SKILL_MAP.get(cat, '—')} |")
    L.append("")

    # iOS file map
    L.append("### iOS Swift 檔案地圖")
    L.append("")
    L.append("| 檔案 | 行數 | 角色 |")
    L.append("|---|---:|---|")
    for path, lc in ios["swift_files"]:
        L.append(f"| `Alfred/{path}` | {lc} | {SWIFT_ROLES.get(path, '—')} |")
    L.append("")

    # Backend
    L.append("### Backend Python 檔案地圖")
    L.append("")
    L.append("| 檔案 | 角色 |")
    L.append("|---|---|")
    L.append(f"| `backend/main.py` | {BACKEND_ROLES['main.py']} |")
    for fn in be["services"]:
        L.append(f"| `backend/{fn}` | {BACKEND_ROLES.get(fn, '—')} |")
    for fn in be["populate"]:
        L.append(f"| `backend/{fn}` | {BACKEND_ROLES.get(fn, '—')} |")
    L.append("")

    # Scrapers
    L.append("### Backend Scrapers")
    L.append("")
    L.append("| 檔案 | 平台 / 狀態 |")
    L.append("|---|---|")
    for fn in be["scrapers"]:
        L.append(f"| `backend/scrapers/{fn}` | {SCRAPER_ROLES.get(fn, '—')} |")
    L.append("")

    # Extras
    if be["extras_indexer"] or be["extras_scrapers"]:
        L.append("### Extras(scale-up tooling,目前未綁進主程式)")
        L.append("")
        if be["extras_indexer"]:
            L.append(f"- `extras/indexer/`: {', '.join(be['extras_indexer'])}")
        if be["extras_scrapers"]:
            L.append(f"- `extras/scrapers/`: {', '.join(be['extras_scrapers'])}")
        L.append("")

    # Survival
    L.append("### 倖存證據(2026-05-13 規則:不准刪)")
    L.append("")
    L.append("妳被改爛時的還原網。任何 Claude 視窗看到這些**一律保留,不准建議清**。")
    L.append("")
    L.append("| 類別 | 數量 / 內容 |")
    L.append("|---|---|")
    L.append(f"| `*.bak*` 檔案 | {survival['bak_files_count']} 個 |")
    L.append(f"| 備份資料夾 | {', '.join(survival['backup_dirs']) or '—'} |")
    L.append(f"| 舊快照 | {', '.join(survival['snapshots']) or '—'} |")
    L.append("")

    # Git
    L.append("### 最近活動")
    L.append("")
    L.append("**最近 20 commits**:")
    L.append("")
    L.append("```")
    for c in git["recent_commits"]:
        L.append(c)
    L.append("```")
    L.append("")
    L.append("**rollback tags**(最近 10):")
    L.append("")
    L.append("```")
    for t in git["tags"]:
        L.append(t)
    L.append("```")
    L.append("")

    # Onboarding map
    L.append("### 順藤摸瓜 — 我是新接手的人,該怎麼讀?")
    L.append("")
    L.append("1. **先讀 doctrine**:[`docs/ALFRED.md`](docs/ALFRED.md) 第 0-2 章(產品核心價值 + 第一原理 + 真正的架構)")
    L.append("2. **再讀技能劇本**:[`docs/ALFRED_SCENARIOS.md`](docs/ALFRED_SCENARIOS.md)(65 技能 × 「呵護的是 X」)")
    L.append("3. **碰 code 前必讀**:[`docs/BUTLER_BRAIN.md`](docs/BUTLER_BRAIN.md)(5 經典範例 + 設計判斷 Q1-Q5)")
    L.append("4. **看這份進度表**(上面)了解 backend / iOS / voice_bank 實況")
    L.append("5. **碰任何「未接線」的程式**前先問主人,不要叫死碼")
    L.append("")
    L.append("---")
    L.append("")
    L.append("*由 `scripts/generate_status.py` 自動產生 — 改 codebase 後跑一次即更新。*")

    return "\n".join(L)


def update_readme(content):
    text = README_PATH.read_text()
    block = README_BEGIN + "\n\n" + content + "\n\n" + README_END

    if README_BEGIN in text and README_END in text:
        before, _, rest = text.partition(README_BEGIN)
        _, _, after = rest.partition(README_END)
        new = before + block + after
    else:
        # Insert after first H1
        m = re.search(r'^(# [^\n]*\n+)', text)
        if m:
            insert_at = m.end()
            new = text[:insert_at] + "\n" + block + "\n\n---\n\n" + text[insert_at:]
        else:
            new = block + "\n\n---\n\n" + text

    README_PATH.write_text(new)


def main():
    write_readme = "--readme" in sys.argv
    dry_run = "--check" in sys.argv

    be = scan_backend()
    ios = scan_ios()
    db = scan_db()
    data = scan_data_files()
    git = scan_git()
    survival = scan_survival_evidence()

    content = render(be, ios, db, data, git, survival)

    if dry_run:
        print(content)
        return

    STATUS_PATH.write_text(content)
    print(f"Wrote {STATUS_PATH} ({len(content):,} chars)")

    if write_readme:
        update_readme(content)
        print(f"Updated {README_PATH} with AUTO_STATUS block")


if __name__ == "__main__":
    main()
