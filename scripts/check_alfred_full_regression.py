#!/usr/bin/env python3
import json
import sys
import time
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:9001"


def request(method, path, payload=None, timeout=45):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE_URL + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(body)
            except Exception:
                return resp.status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(body)
        except Exception:
            pass
        return e.code, body


failures = []


def fail(name, msg):
    failures.append(f"{name}: {msg}")


def check_endpoint(name, method, path, required_keys=()):
    status, data = request(method, path, timeout=20)
    print(f"== endpoint:{name} == {status}")
    if status >= 500:
        fail(name, f"HTTP {status}: {str(data)[:200]}")
        return
    if required_keys and isinstance(data, dict):
        missing = [k for k in required_keys if k not in data]
        if missing:
            fail(name, f"missing keys {missing}; got {list(data.keys())[:12]}")
    elif required_keys:
        fail(name, f"non-json response for required keys: {str(data)[:120]}")


def chat(name, message, require_any=(), forbid=(), no_card=True, max_text_len=None,
         action_type=None, forbid_action_type=(), timeout=45, max_seconds=None):
    t0 = time.monotonic()
    status, data = request("POST", "/api/chat", {"message": message, "history": []}, timeout=timeout)
    elapsed = time.monotonic() - t0
    print(f"== chat:{name} == {status} ({elapsed:.2f}s)")
    if max_seconds is not None and elapsed > max_seconds:
        fail(name, f"too slow: {elapsed:.2f}s > {max_seconds:.2f}s")
    if status != 200 or not isinstance(data, dict):
        fail(name, f"bad response {status}: {str(data)[:240]}")
        return {}
    text = data.get("text") or ""
    text_one = text.replace("\n", " ")
    print(text_one[:700])
    if not text.strip():
        fail(name, "empty spoken text")
    if no_card and data.get("card") is not None:
        fail(name, f"returned UI card in zero-interface flow: {data.get('card')}")
    if require_any and not any(r in text for r in require_any):
        fail(name, f"missing required phrase; need one of {require_any}")
    for bad in forbid:
        if bad in text:
            fail(name, f"forbidden phrase in spoken text: {bad}")
    action = data.get("action") or {}
    if action_type and action.get("type") != action_type:
        fail(name, f"expected action {action_type}, got {action}")
    for bad_action in forbid_action_type:
        if action.get("type") == bad_action:
            fail(name, f"forbidden action type: {bad_action}")
    if max_text_len and len(text) > max_text_len:
        fail(name, f"spoken text too long: {len(text)} > {max_text_len}")
    return data


def main():
    check_endpoint("health", "GET", "/health", required_keys=("status", "alfred"))
    check_endpoint("setup_status", "GET", "/api/setup/status", required_keys=("line", "telegram"))
    check_endpoint("gcal_status", "GET", "/api/gcal/status")
    check_endpoint("voice_status", "GET", "/api/voice/status")
    check_endpoint("ambient_sessions", "GET", "/api/ambient/sessions")
    check_endpoint("office_rooms", "GET", "/api/office/rooms")
    check_endpoint("health_status", "GET", "/api/health/status")

    chat("liveness", "阿福你還在嗎", require_any=("主人", "在"), max_text_len=160, max_seconds=3)
    chat("weather", "今天天氣怎麼樣", require_any=("主人",), forbid=("索引", "文件"), max_text_len=260, max_seconds=3)
    chat("google_auth_status", "Google 授權狀態", require_any=("Google", "授權"), max_text_len=260)
    chat("line_link", "用Line跟阿福對話", require_any=("LINE", "Line", "line"), max_text_len=320)

    chat("ambient_open_requires_button", "開啟阿福聆聽模式",
         require_any=("按下", "宣告", "App"), forbid_action_type=("start_ambient",), max_text_len=260, max_seconds=3)
    chat("ambient_mode_open_text_requires_button", "阿福模式開啟",
         require_any=("按下", "宣告", "App"), forbid=("隨時都在", "收到"), forbid_action_type=("start_ambient",), max_text_len=260, max_seconds=3)
    chat("ambient_stop_voice_allowed", "關閉聆聽模式",
         require_any=("停止", "聆聽"), action_type="stop_ambient", max_text_len=180)
    chat("ambient_policy", "阿福模式多久切一次逐字稿",
         require_any=("本地", "聲音"), forbid=("每 120 秒", "全天候監聽"), max_text_len=260)

    chat("breakfast", "我想要吃早餐",
         require_any=("早餐",), forbid=("查不到", "油飯", "蚵仔", "索引", "文件"), max_text_len=360, max_seconds=3)
    chat("burger_breakfast", "我想吃有關漢堡類的早餐",
         require_any=("漢堡",), forbid=("油飯", "蚵仔", "索引", "文件"), max_text_len=380)
    chat("nearby_hotpot", "這個阿福我現在在新北市泰山信華六街5號這邊告訴我這邊一公里內的麻辣火鍋店有哪些",
         require_any=("麻辣", "火鍋"), forbid=("好的，主人。", "牛肉麵", "水餃", "蔥抓餅"), max_text_len=380)
    chat("taipei_michelin", "台北米其林餐廳推薦",
         require_any=("台北", "米其林"), forbid=("文件", "索引"), max_text_len=700)

    chat("travel_zero_ui", "阿甫,幫我安排5月下週的日本旅行行程四個人,兩大、兩小、最小的5歲,幫我安排",
         require_any=("LINE", "Email"), forbid=("完整旅遊資料", "卡片", "插卡"), max_text_len=360, max_seconds=3)
    chat("travel_no_city", "幫我安排旅遊",
         require_any=("日本", "韓國", "歐洲"), forbid=("完整旅遊資料", "卡片"), max_text_len=520)

    chat("yesterday_ai_news", "我想要聽昨天的AI新聞",
         require_any=("查", "新聞"), forbid=("只能搜尋最新", "無法精確指定", "索引", "文件"), max_text_len=900)
    chat("techcrunch", "阿弗那你到國外的網站像TechCrunch或是相關的科技網站去找",
         require_any=("TechCrunch", "technology"), forbid=("索引裡沒有找到", "文件"), max_text_len=900)

    chat("anniversary", "我有哪些紀念日要記得",
         require_any=("紀念日", "生日", "重要"), forbid=("PDF", "91APP", "文件", "索引"), max_text_len=900)
    chat("attendance", "幫我看今天出勤狀態",
         require_any=("今天",), forbid=("文件", "索引"), max_text_len=260)
    chat("photo_picker", "幫我看今天的照片",
         require_any=("相簿", "挑一張"), action_type="show_photos_picker", max_text_len=220)
    chat("math", "123加456是多少",
         require_any=("579",), forbid=("文件", "索引"), max_text_len=120, max_seconds=3)
    chat("file_search_contract", "幫我找合約",
         require_any=("合約", "文件", "找"), forbid=("TechCrunch", "油飯"), max_text_len=900)

    # Semantic gate contamination test: a previous file search must not hijack
    # a later travel sentence containing "5月" as "select file #5".
    chat("semantic_file_then_travel_seed", "幫我找合約",
         require_any=("合約", "找"), forbid=("TechCrunch", "油飯"), max_text_len=900)
    chat("semantic_file_then_travel", "阿甫,幫我安排5月下週的日本旅行行程四個人,兩大、兩小、最小的5歲,幫我安排",
         require_any=("東京", "LINE"), forbid=("合約", "文件", "卡片", "無法讀取內容"), max_text_len=360, max_seconds=3)

    if failures:
        print("\nFULL REGRESSION FAILED")
        for f in failures:
            print(" - " + f)
        sys.exit(1)
    print("\nFULL REGRESSION OK")


if __name__ == "__main__":
    main()
