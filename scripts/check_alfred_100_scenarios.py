#!/usr/bin/env python3
import json
import time
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:9001"


def case(name, message, require_any=(), require_all=(), forbid=(), forbid_action_type=(), action_type=None,
         forbid_card=False, max_seconds=3.0, max_text_len=None):
    return {
        "name": name,
        "message": message,
        "require_any": tuple(require_any),
        "require_all": tuple(require_all),
        "forbid": tuple(forbid),
        "forbid_action_type": tuple(forbid_action_type),
        "action_type": action_type,
        "forbid_card": forbid_card,
        "max_seconds": max_seconds,
        "max_text_len": max_text_len,
    }


CASES = [
    # Liveness / butler tone
    case("live_001", "阿福你在嗎", require_any=("主人", "在"), forbid=("不知道", "無法"), max_seconds=1.5),
    case("live_002", "阿福你好", require_any=("主人",), forbid=("文件", "索引"), max_seconds=1.5),
    case("live_003", "你還醒著嗎", require_any=("主人", "在"), forbid=("索引",), max_seconds=1.5),
    case("live_004", "現在可以幫我嗎", require_any=("主人",), forbid=("無法協助",), max_seconds=1.5),
    case("live_005", "阿福幫我一下", require_any=("主人",), forbid=("文件", "索引"), max_seconds=2.0),

    # Ambient / App Store policy
    case("ambient_001", "阿福模式開啟", require_all=("App", "宣告"), forbid=("隨時都在", "收到"), forbid_action_type=("start_ambient",), forbid_card=True),
    case("ambient_002", "開啟阿福聆聽模式", require_all=("App", "宣告"), forbid_action_type=("start_ambient",), forbid_card=True),
    case("ambient_003", "阿福你開始聽我接下來講話", require_all=("App", "宣告"), forbid_action_type=("start_ambient",), forbid_card=True),
    case("ambient_004", "阿福打開陪伴模式", require_all=("App", "宣告"), forbid_action_type=("start_ambient",), forbid_card=True),
    case("ambient_005", "阿福你先不要聽", require_any=("停止", "聆聽", "休息"), action_type="stop_ambient", forbid_card=True),
    case("ambient_006", "阿福你去休息", require_any=("停止", "聆聽", "休息"), action_type="stop_ambient", forbid_card=True),
    case("ambient_007", "關閉聆聽模式", require_any=("停止", "聆聽"), action_type="stop_ambient", forbid_card=True),
    case("ambient_008", "阿福模式多久切一次逐字稿", require_any=("本地", "人聲", "逐字稿"), forbid_card=True),
    case("ambient_009", "沒有聲音的時候會不會上傳", require_any=("不會上傳", "人聲"), forbid_card=True),
    case("ambient_010", "阿福模式會不會一直偷聽", require_any=("本地", "宣告", "關閉"), forbid_card=True, max_seconds=4.0),

    # Travel zero UI
    case("travel_001", "幫我安排日本親子3天旅行", require_any=("東京", "LINE", "Email"), forbid=("卡片", "插卡", "沒有日本"), forbid_card=True),
    case("travel_002", "幫我安排韓國親子4天旅行", require_any=("首爾", "樂天世界", "LINE"), forbid=("農心", "卡片"), forbid_card=True),
    case("travel_003", "幫我安排釜山情侶3天旅行", require_any=("釜山", "海雲台", "LINE"), forbid=("卡片",), forbid_card=True),
    case("travel_004", "幫我安排北海道親子5天旅行", require_any=("北海道", "富良野", "LINE"), forbid=("資料還不全",), forbid_card=True),
    case("travel_005", "幫我安排福岡三天自由行", require_any=("福岡", "太宰府", "LINE"), forbid=("資料還不全",), forbid_card=True),
    case("travel_006", "幫我安排新加坡親子3天旅行", require_any=("新加坡", "濱海灣", "LINE"), forbid=("卡片",), forbid_card=True),
    case("travel_007", "幫我安排曼谷情侶4天旅行", require_any=("曼谷", "大皇宮", "LINE"), forbid=("資料還不全",), forbid_card=True),
    case("travel_008", "幫我安排峇里島情侶5天旅行", require_any=("峇里島", "烏布", "LINE"), forbid=("資料還不全",), forbid_card=True),
    case("travel_009", "幫我安排巴黎兩天行程", require_any=("巴黎", "LINE"), forbid=("資料還不全", "卡片"), forbid_card=True),
    case("travel_010", "幫我安排倫敦三天旅行", require_any=("倫敦", "LINE"), forbid=("資料還不全",), forbid_card=True),
    case("travel_011", "幫我安排羅馬三天情侶旅行", require_any=("羅馬", "LINE"), forbid=("資料還不全",), forbid_card=True),
    case("travel_012", "幫我安排巴塞隆納三天旅行", require_any=("巴塞隆納", "LINE"), forbid=("資料還不全",), forbid_card=True),
    case("travel_013", "幫我安排紐約三天旅行", require_any=("紐約", "LINE"), forbid=("資料還不全",), forbid_card=True),
    case("travel_014", "幫我安排洛杉磯兩天旅行", require_any=("洛杉磯", "LINE"), forbid=("資料還不全",), forbid_card=True),
    case("travel_015", "幫我安排雪梨三天旅行", require_any=("雪梨", "LINE"), forbid=("資料還不全",), forbid_card=True),
    case("travel_016", "幫我安排杜拜三天親子旅行", require_any=("杜拜", "LINE"), forbid=("資料還不全",), forbid_card=True),
    case("travel_017", "我想出國玩但還不知道去哪", require_any=("日本", "韓國", "泰國"), forbid=("文件", "索引"), forbid_card=True),
    case("travel_018", "5月日本旅行幫我排一下", require_any=("東京", "LINE"), forbid=("合約", "文件", "第5份"), forbid_card=True),
    case("travel_019", "京都情侶三天怎麼玩", require_any=("京都", "清水寺", "LINE"), forbid=("資料還不全",), forbid_card=True),
    case("travel_020", "大阪親子四天可以怎麼安排", require_any=("大阪", "USJ", "LINE"), forbid=("資料還不全",), forbid_card=True),

    # Restaurant / nearby
    case("food_001", "附近有什麼早餐", require_any=("早餐",), forbid=("油飯", "索引", "文件"), forbid_card=True),
    case("food_002", "附近想吃漢堡早餐", require_any=("漢堡", "早餐"), forbid=("蚵仔", "索引"), forbid_card=True),
    case("food_003", "附近一公里內有麻辣火鍋嗎", require_any=("麻辣火鍋", "火鍋"), forbid=("牛肉麵", "蔥抓餅"), forbid_card=True),
    case("food_004", "台北米其林餐廳推薦", require_any=("米其林", "鼎泰豐"), forbid=("旅行", "LINE"), forbid_card=True),
    case("food_005", "台北有什麼牛肉麵", require_any=("牛肉麵", "主人"), forbid=("旅遊", "行程"), forbid_card=True),
    case("food_006", "台南小吃推薦", require_any=("台南",), forbid=("資料還不全",), forbid_card=True),
    case("food_007", "首爾有什麼好吃的", require_any=("首爾",), forbid=("農心",), forbid_card=True),
    case("food_008", "釜山海鮮推薦", require_any=("釜山", "海"), forbid=("資料還不全",), forbid_card=True),
    case("food_009", "新加坡必吃什麼", require_any=("新加坡", "海南雞飯"), forbid=("資料還不全",), forbid_card=True),
    case("food_010", "曼谷泰式料理推薦", require_any=("曼谷", "泰"), forbid=("資料還不全",), forbid_card=True),

    # Weather
    case("weather_001", "今天天氣怎麼樣", require_any=("主人", "°C"), forbid=("文件", "索引"), forbid_card=True),
    case("weather_002", "今天會下雨嗎", require_any=("主人", "雨"), forbid=("文件",), forbid_card=True),
    case("weather_003", "今天要帶傘嗎", require_any=("主人", "傘"), forbid=("文件",), forbid_card=True),
    case("weather_004", "外面冷不冷", require_any=("主人", "°C"), forbid=("文件",), forbid_card=True),
    case("weather_005", "明天天氣預報", require_any=("明天", "°C"), forbid=("文件",), forbid_card=True),
    case("weather_006", "今天熱不熱", require_any=("主人", "°C"), forbid=("文件",), forbid_card=True),

    # News/search
    case("news_001", "幫我查昨天AI新聞", require_any=("新聞",), forbid=("只能搜尋最新", "文件", "索引"), forbid_card=True, max_seconds=5.0, max_text_len=1000),
    case("news_002", "去TechCrunch找科技新聞", require_any=("TechCrunch",), forbid=("文件", "索引"), forbid_card=True, max_seconds=5.0, max_text_len=1000),
    case("news_003", "找最近五天AI新聞", require_any=("新聞",), forbid=("文件", "索引"), forbid_card=True, max_seconds=5.0, max_text_len=1000),
    case("news_004", "不要跟前面重複，再找新的科技新聞", require_any=("新聞",), forbid=("文件", "索引"), forbid_card=True, max_seconds=5.0, max_text_len=1000),
    case("news_005", "國外科技網站有什麼AI消息", require_any=("technology", "TechCrunch", "新聞"), forbid=("索引", "文件"), forbid_card=True, max_seconds=5.0, max_text_len=1000),

    # Files / semantic contamination
    case("file_001", "幫我找合約", require_any=("合約", "文件"), forbid=("TechCrunch",), forbid_card=True, max_seconds=4.0),
    case("file_002", "幫我找台電合約", require_any=("台電", "合約"), forbid=("新聞",), forbid_card=True, max_seconds=4.0),
    case("file_003", "找一下報價單", require_any=("報價", "文件", "找"), forbid=("旅遊",), forbid_card=True, max_seconds=4.0),
    case("file_004", "找91APP資料", require_any=("91APP", "文件", "找"), forbid=("TechCrunch",), forbid_card=True, max_seconds=4.0),
    case("file_005", "幫我找公證書", require_any=("公證", "文件", "找"), forbid=("旅遊",), forbid_card=True, max_seconds=4.0),
    case("semantic_001", "幫我找合約", require_any=("合約", "文件"), forbid_card=True, max_seconds=4.0),
    case("semantic_002", "5月日本旅行", require_any=("東京", "LINE"), forbid=("合約", "第5份", "文件"), forbid_card=True),

    # Integrations / zero interface links
    case("integration_001", "我要連Google", require_any=("Google", "授權", "http"), forbid=("卡片",), forbid_card=True),
    case("integration_002", "用Line跟阿福對話", require_any=("LINE", "line.me"), forbid=("卡片",), forbid_card=True),
    case("integration_003", "Telegram怎麼連阿福", require_any=("Telegram", "t.me"), forbid=("卡片",), forbid_card=True),
    case("integration_004", "Email可以寄給我嗎", require_any=("Email", "主人"), forbid=("卡片",), forbid_card=True, max_seconds=4.0),
    case("integration_005", "阿福可以用LINE通知我嗎", require_any=("LINE",), forbid=("卡片",), forbid_card=True),
    case("integration_006", "我想設定阿福服務", require_any=("設定", "主人", "服務"), forbid=("卡片",), forbid_card=True, max_seconds=4.0),

    # Math
    case("math_001", "123加456是多少", require_any=("579",), forbid=("文件", "索引"), forbid_card=True),
    case("math_002", "1000減333是多少", require_any=("667",), forbid=("文件",), forbid_card=True),
    case("math_003", "12乘以13是多少", require_any=("156",), forbid=("文件",), forbid_card=True),
    case("math_004", "144除以12是多少", require_any=("12",), forbid=("文件",), forbid_card=True),
    case("math_005", "2+2是多少", require_any=("4", "好的"), forbid=("文件",), forbid_card=True),

    # Photos / meetings / attendance / anniversaries
    case("photo_001", "幫我看今天的照片", require_any=("相簿", "挑一張"), action_type="show_photos_picker", forbid_card=False),
    case("photo_002", "幫我看照片", require_any=("相簿", "挑一張"), action_type="show_photos_picker", forbid_card=False),
    case("meeting_001", "幫我開始記錄這個會議", require_any=("會議", "錄音", "開始"), forbid_card=True, max_seconds=4.0),
    case("meeting_002", "會議結束幫我整理", require_any=("會議", "整理"), forbid_card=True, max_seconds=4.0),
    case("attendance_001", "幫我看今天出勤狀態", require_any=("今天",), forbid=("文件", "索引"), forbid_card=True),
    case("anniv_001", "我有哪些紀念日要記得", require_any=("紀念日", "生日"), forbid=("91APP", "PDF", "文件"), forbid_card=True),

    # Calendar / reminders / general butler actions
    case("reminder_001", "提醒我明天下午三點打電話給客戶", require_any=("提醒", "主人"), forbid=("文件", "索引"), forbid_card=True, max_seconds=5.0),
    case("reminder_002", "幫我記得下週一要繳電話費", require_any=("記得", "主人", "提醒"), forbid=("文件",), forbid_card=True, max_seconds=5.0),
    case("calendar_001", "我今天有什麼行程", require_any=("今天", "行程", "主人"), forbid=("文件", "索引"), forbid_card=True, max_seconds=5.0),
    case("calendar_002", "明天早上有會議嗎", require_any=("明天", "會議", "主人"), forbid=("文件", "索引"), forbid_card=True, max_seconds=5.0),
    case("memory_001", "我太太生日是7月1日", require_any=("主人", "生日"), forbid=("文件", "索引"), forbid_card=True, max_seconds=5.0),

    # Zero UI / no random cards
    case("zero_001", "幫我安排日本旅行然後傳LINE", require_any=("LINE", "東京"), forbid=("卡片", "插卡"), forbid_card=True),
    case("zero_002", "幫我把韓國行程寄Email", require_any=("Email", "首爾"), forbid=("卡片", "插卡"), forbid_card=True),
    case("zero_003", "幫我找合約然後念給我聽", require_any=("合約", "文件"), forbid=("卡片",), forbid_card=True, max_seconds=4.0),
    case("zero_004", "幫我查天氣不要開介面", require_any=("主人", "°C"), forbid=("卡片",), forbid_card=True),
    case("zero_005", "阿福幫我找個日本行程", require_any=("日本", "東京", "LINE"), forbid=("卡片", "文件"), forbid_card=True),

    # Edge wording
    case("edge_001", "我問日本行程不要講到一半掛掉", require_any=("東京", "LINE"), forbid=("資料還不全", "文件"), forbid_card=True),
    case("edge_002", "台北米其林不是旅遊，是餐廳推薦", require_any=("米其林", "餐廳"), forbid=("LINE", "行程"), forbid_card=True),
    case("edge_003", "阿福我要你幫我找合約", require_any=("合約", "文件"), forbid=("旅行",), forbid_card=True, max_seconds=4.0),
    case("edge_004", "阿福幫我找個合約，然後不要亂找旅遊", require_any=("合約", "文件"), forbid=("東京", "LINE"), forbid_card=True, max_seconds=4.0),
    case("edge_005", "阿福你先關閉", require_any=("停止", "聆聽", "休息"), action_type="stop_ambient", forbid_card=True),
    case("edge_006", "阿福你先不要聽", require_any=("停止", "聆聽", "休息"), action_type="stop_ambient", forbid_card=True),
    case("edge_007", "阿福幫我找個合約", require_any=("合約", "文件"), forbid_card=True, max_seconds=4.0),
    case("edge_008", "5月韓國親子旅行", require_any=("首爾", "LINE"), forbid=("合約", "第5份", "文件"), forbid_card=True),
    case("edge_009", "附近早餐但不要給我油飯", require_any=("早餐",), forbid=("油飯", "文件"), forbid_card=True),
    case("edge_010", "阿福你還在嗎，不要去找文件", require_any=("主人", "在"), forbid=("文件", "索引"), forbid_card=True),
]


def request_chat(message, timeout=15):
    body = json.dumps({"message": message, "history": []}).encode("utf-8")
    req = urllib.request.Request(
        BASE_URL + "/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        elapsed = time.perf_counter() - started
        data = json.loads(resp.read().decode("utf-8"))
    return elapsed, data


def evaluate(c, elapsed, data):
    text = str(data.get("text") or "")
    card = data.get("card")
    action = data.get("action") or {}
    failures = []
    if c["max_seconds"] is not None and elapsed > c["max_seconds"]:
        failures.append(f"slow {elapsed:.2f}s>{c['max_seconds']:.2f}s")
    if c["require_any"] and not any(s in text for s in c["require_any"]):
        failures.append("missing any " + repr(c["require_any"]))
    for s in c["require_all"]:
        if s not in text:
            failures.append("missing " + repr(s))
    for s in c["forbid"]:
        if s in text:
            failures.append("forbidden text " + repr(s))
    if c["forbid_card"] and card:
        failures.append("unexpected card")
    if c["action_type"] and action.get("type") != c["action_type"]:
        failures.append(f"action {action.get('type')!r}!={c['action_type']!r}")
    if action.get("type") in c["forbid_action_type"]:
        failures.append("forbidden action " + repr(action.get("type")))
    if c["max_text_len"] and len(text) > c["max_text_len"]:
        failures.append(f"text too long {len(text)}>{c['max_text_len']}")
    return failures


def main():
    assert len(CASES) == 100, len(CASES)
    results = []
    for i, c in enumerate(CASES, 1):
        try:
            elapsed, data = request_chat(c["message"])
            failures = evaluate(c, elapsed, data)
            ok = not failures
            results.append((ok, c, elapsed, data, failures))
            status = "OK" if ok else "FAIL"
            text = (data.get("text") or "").replace("\n", " ")
            print(f"{i:03d} {status} {c['name']} {elapsed:.2f}s :: {text[:180]}")
            if failures:
                print("    " + " | ".join(failures))
        except (urllib.error.URLError, TimeoutError, Exception) as exc:
            results.append((False, c, 999, {}, [f"exception {type(exc).__name__}: {exc}"]))
            print(f"{i:03d} FAIL {c['name']} EXC :: {type(exc).__name__}: {exc}")
    total = len(results)
    failed = [r for r in results if not r[0]]
    slow = [r for r in results if r[2] != 999 and r[2] > r[1]["max_seconds"]]
    cards = [r for r in results if r[1]["forbid_card"] and r[3].get("card")]
    print("\nSUMMARY")
    print(f"total={total}")
    print(f"passed={total-len(failed)}")
    print(f"failed={len(failed)}")
    print(f"failure_rate={len(failed)/total*100:.1f}%")
    print(f"slow_failures={len(slow)}")
    print(f"unexpected_cards={len(cards)}")
    if failed:
        print("\nFAILURES")
        for ok, c, elapsed, data, failures in failed:
            print(f"- {c['name']} ({elapsed:.2f}s): {' | '.join(failures)}")
            print(f"  msg: {c['message']}")
            print(f"  text: {(data.get('text') or '')[:500].replace(chr(10), ' ')}")


if __name__ == "__main__":
    main()
