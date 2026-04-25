from fastapi import FastAPI, WebSocket, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
import anthropic, sqlite3, os, json, httpx, asyncio
from datetime import datetime
from typing import Optional, List
from dotenv import load_dotenv

load_dotenv()

# ── LLM 客戶端：優先用 Google Gemini，沒有才用 Anthropic ─────────────────────
import openai as _openai_sdk

GOOGLE_API_KEY   = os.getenv("GOOGLE_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

if GOOGLE_API_KEY:
    _llm = _openai_sdk.OpenAI(
        api_key=GOOGLE_API_KEY,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
    )
    LLM_PROVIDER = "gemini"
    LLM_MODEL    = "gemini-2.0-flash"
    LLM_MODEL_HEAVY = "gemini-2.0-flash"   # 免費 tier 先都用 flash
else:
    _llm = None
    LLM_PROVIDER = "anthropic"
    LLM_MODEL    = "claude-sonnet-4-6"
    LLM_MODEL_HEAVY = "claude-sonnet-4-6"


def _simple_chat(prompt: str, max_tokens: int = 3000) -> str:
    """單輪 LLM 呼叫（無工具），用於合約分析、報告生成等。"""
    if LLM_PROVIDER == "gemini":
        resp = _llm.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens
        )
        return resp.choices[0].message.content or ""
    elif client:
        resp = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        return "".join(b.text for b in resp.content if hasattr(b, "text"))
    return ""


def _tools_to_oai(tools: list) -> list:
    """把 Anthropic 格式的 TOOLS 轉成 OpenAI / Gemini 格式。"""
    out = []
    for t in tools:
        out.append({"type": "function", "function": {
            "name": t["name"],
            "description": t.get("description", ""),
            "parameters": t.get("input_schema", {"type":"object","properties":{}})
        }})
    return out


def _llm_chat(system: str, messages: list, tools: list = None, max_tokens: int = 2048):
    """
    統一 LLM 呼叫介面。
    回傳 (text: str, tool_calls: list[dict], finish_reason: str, raw_msg)
    tool_calls 格式：[{"id":..., "name":..., "input":{...}}]
    """
    if LLM_PROVIDER == "gemini":
        oai_msgs = [{"role": "system", "content": system}] + messages
        oai_tools = _tools_to_oai(tools) if tools else None
        kwargs = dict(model=LLM_MODEL, messages=oai_msgs, max_tokens=max_tokens)
        if oai_tools:
            kwargs["tools"] = oai_tools
        resp = _llm.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        text = choice.message.content or ""
        raw_tcs = choice.message.tool_calls or []
        tool_calls = []
        for tc in raw_tcs:
            try:
                inp = json.loads(tc.function.arguments) if tc.function.arguments else {}
            except Exception:
                inp = {}
            tool_calls.append({"id": tc.id, "name": tc.function.name, "input": inp})
        finish = "tool_use" if choice.finish_reason == "tool_calls" else "end_turn"
        return text, tool_calls, finish, choice.message
    else:
        # Anthropic 路徑（當沒有 Google key 時 fallback）
        ant_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        resp = ant_client.messages.create(
            model=LLM_MODEL, max_tokens=max_tokens,
            system=system, tools=tools or [], messages=messages
        )
        text = "".join(b.text for b in resp.content if hasattr(b, "text"))
        tool_calls = []
        for b in resp.content:
            if getattr(b, "type", "") == "tool_use":
                tool_calls.append({"id": b.id, "name": b.name, "input": b.input})
        finish = "tool_use" if resp.stop_reason == "tool_use" else "end_turn"
        return text, tool_calls, finish, resp.content

try:
    import gcal_service
    GCAL_CONFIGURED = bool(os.getenv("GOOGLE_CLIENT_ID"))
except Exception:
    gcal_service = None  # type: ignore
    GCAL_CONFIGURED = False

try:
    import line_service
    LINE_CONFIGURED = line_service.is_configured()
except Exception:
    line_service = None  # type: ignore
    LINE_CONFIGURED = False

try:
    import telegram_service
    TG_CONFIGURED = telegram_service.is_configured()
except Exception:
    telegram_service = None  # type: ignore
    TG_CONFIGURED = False

try:
    import gmail_service
except Exception:
    gmail_service = None  # type: ignore

try:
    import drive_service
except Exception:
    drive_service = None  # type: ignore

try:
    import search_service
except Exception:
    search_service = None  # type: ignore

# Lazy import so server still starts even without twilio/openai if creds missing
try:
    import call_service
    AI_CALL_AVAILABLE = call_service.twilio_configured()
except Exception:
    call_service = None  # type: ignore
    AI_CALL_AVAILABLE = False

TWILIO_CONFIGURED = bool(
    os.getenv("TWILIO_ACCOUNT_SID") and
    os.getenv("TWILIO_AUTH_TOKEN") and
    os.getenv("TWILIO_PHONE_NUMBER")
)

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DB = "/opt/alfred/data/alfred.db"
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

def db():
    return sqlite3.connect(DB)


# ─── Background indexing ───────────────────────────────────────────────────────

def _parse_vcf(content: str) -> list[dict]:
    """Parse VCF/vCard content into list of contact dicts."""
    import re
    contacts = []
    for card in re.split(r'END:VCARD', content, flags=re.IGNORECASE):
        card = card.strip()
        if not card:
            continue
        def get(field):
            m = re.search(rf'^{field}[^:]*:(.+)$', card, re.MULTILINE | re.IGNORECASE)
            return m.group(1).strip() if m else ""
        def get_all(field):
            return [m.group(1).strip() for m in re.finditer(rf'^{field}[^:]*:(.+)$', card, re.MULTILINE | re.IGNORECASE)]

        # Name: prefer FN (formatted), fallback to N
        name = get("FN") or get("N").replace(";", " ").strip()
        if not name:
            continue
        phones = [p.replace("-","").replace(" ","").replace("(","").replace(")","")
                  for p in get_all("TEL")]
        emails = get_all("EMAIL")
        org = get("ORG").replace(";", " ").strip()
        import hashlib
        uid = get("UID") or hashlib.md5(name.encode()).hexdigest()
        contacts.append({
            "id": uid, "name": name,
            "phones": ",".join(phones[:3]),
            "emails": ",".join(emails[:2]),
            "org": org, "notes": ""
        })
    return contacts


async def _bg_index_drive():
    """Silently index Google Drive files in the background. Repeats every 2 hours."""
    await asyncio.sleep(10)  # wait for server to fully start
    while True:
        try:
            if drive_service and drive_service.is_connected(db):
                from datetime import datetime as _dt
                print(f"[alfred] 開始掃描 Google Drive 建立索引… {_dt.now():%H:%M}")
                drive_service.search_files(db, query="", limit=200, force_refresh=True)
                count = drive_service.index_count(db)
                print(f"[alfred] Drive 索引完成，共 {count} 個檔案")
        except Exception as e:
            print(f"[alfred] Drive 索引失敗：{e}")
        await asyncio.sleep(7200)  # re-index every 2 hours


@app.on_event("startup")
async def startup():
    asyncio.create_task(_bg_index_drive())
    asyncio.create_task(_guardian_loop())

def init_db():
    c = db()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS memories
            (id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT, key TEXT, value TEXT, ts TEXT);
        CREATE TABLE IF NOT EXISTS food_history
            (id INTEGER PRIMARY KEY AUTOINCREMENT, food TEXT, restaurant TEXT, platform TEXT, tags TEXT, ts TEXT);
        CREATE TABLE IF NOT EXISTS relationships
            (id INTEGER PRIMARY KEY AUTOINCREMENT, nickname TEXT, real_name TEXT, contact TEXT, notes TEXT, ts TEXT);
        CREATE TABLE IF NOT EXISTS todos
            (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, due_date TEXT, status TEXT DEFAULT 'pending', follow_up INTEGER DEFAULT 0, ts TEXT);
        CREATE TABLE IF NOT EXISTS calendar_events
            (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, event_date TEXT, event_time TEXT, notes TEXT, ts TEXT);
        CREATE TABLE IF NOT EXISTS expenses
            (id INTEGER PRIMARY KEY AUTOINCREMENT, amount REAL, category TEXT, description TEXT, ts TEXT);
        CREATE TABLE IF NOT EXISTS reminders
            (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, trigger_at TEXT, notified INTEGER DEFAULT 0, ts TEXT);
        CREATE TABLE IF NOT EXISTS calls
            (id TEXT PRIMARY KEY, status TEXT DEFAULT 'initiated', phone TEXT, name TEXT,
             purpose TEXT, transcript TEXT, result TEXT, sid TEXT, ts TEXT);
        CREATE TABLE IF NOT EXISTS meeting_notes
            (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, transcript TEXT,
             summary TEXT, action_items TEXT, ts TEXT);
        CREATE TABLE IF NOT EXISTS files
            (id INTEGER PRIMARY KEY AUTOINCREMENT, filename TEXT, original_name TEXT,
             mime_type TEXT, size INTEGER, description TEXT, tags TEXT, ts TEXT);
        CREATE TABLE IF NOT EXISTS drive_index
            (id TEXT PRIMARY KEY, name TEXT, mime_type TEXT, size TEXT,
             modified TEXT, url TEXT, indexed_at TEXT);
        CREATE TABLE IF NOT EXISTS contacts_index
            (id TEXT PRIMARY KEY, name TEXT, phones TEXT, emails TEXT,
             org TEXT, notes TEXT, indexed_at TEXT);
        CREATE TABLE IF NOT EXISTS mac_files_index
            (path TEXT PRIMARY KEY, name TEXT, size INTEGER, modified TEXT,
             kind TEXT, indexed_at TEXT);
        CREATE TABLE IF NOT EXISTS location_log
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
             lat REAL, lng REAL, speed REAL, heading REAL,
             accuracy REAL, mode TEXT, ts TEXT);
        CREATE TABLE IF NOT EXISTS parking_spots
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
             lat REAL, lng REAL, address TEXT, note TEXT,
             parked_at TEXT, found_at TEXT);
        CREATE TABLE IF NOT EXISTS walk_routes
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
             parking_id INTEGER, points TEXT, started_at TEXT, ended_at TEXT);
        CREATE TABLE IF NOT EXISTS place_history
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
             lat REAL, lng REAL, name TEXT, category TEXT,
             arrived_at TEXT, departed_at TEXT, duration_min INTEGER);
        CREATE TABLE IF NOT EXISTS item_locations
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
             item TEXT, location_desc TEXT,
             lat REAL, lng REAL, place_name TEXT,
             noted_at TEXT, found_at TEXT);
        CREATE TABLE IF NOT EXISTS known_places
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
             name TEXT, place_type TEXT, lat REAL, lng REAL,
             radius_m REAL DEFAULT 200, noted_at TEXT);
        CREATE TABLE IF NOT EXISTS family_members
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
             name TEXT NOT NULL, relation TEXT DEFAULT 'family',
             avatar_color TEXT DEFAULT '#c9a84c',
             device_token TEXT UNIQUE,
             last_lat REAL, last_lng REAL, last_address TEXT,
             last_seen TEXT, battery INTEGER,
             is_home INTEGER DEFAULT 0,
             planned_destination TEXT,
             planned_eta TEXT,
             noted_at TEXT);
        CREATE TABLE IF NOT EXISTS family_alerts
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
             member_id INTEGER, alert_type TEXT,
             message TEXT, severity TEXT DEFAULT 'warning',
             created_at TEXT, acknowledged_at TEXT,
             escalation_level INTEGER DEFAULT 0,
             last_escalated_at TEXT);
        CREATE TABLE IF NOT EXISTS family_invites
            (token TEXT PRIMARY KEY,
             member_id INTEGER,
             created_at TEXT, used_at TEXT, expires_at TEXT);
        CREATE TABLE IF NOT EXISTS family_location_log
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
             member_id INTEGER, lat REAL, lng REAL,
             address TEXT, speed REAL, battery INTEGER, ts TEXT);
        CREATE TABLE IF NOT EXISTS people_prefs
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
             person TEXT NOT NULL,
             relation TEXT DEFAULT 'colleague',
             category TEXT DEFAULT 'other',
             content TEXT NOT NULL,
             importance TEXT DEFAULT 'normal',
             noted_at TEXT);
        CREATE TABLE IF NOT EXISTS attendance
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
             date TEXT NOT NULL,
             check_in TEXT,
             check_out TEXT,
             type TEXT DEFAULT 'office',
             lat_in REAL, lng_in REAL,
             lat_out REAL, lng_out REAL,
             address_in TEXT, address_out TEXT,
             duration_min INTEGER,
             notes TEXT,
             verified INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS pets
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
             name TEXT NOT NULL, species TEXT DEFAULT 'cat',
             breed TEXT, age_years REAL, color TEXT,
             vet_clinic TEXT, vet_phone TEXT,
             next_vet_date TEXT, food_brand TEXT,
             daily_food_g REAL DEFAULT 80,
             allergies TEXT, notes TEXT,
             photo_path TEXT, noted_at TEXT);
        CREATE TABLE IF NOT EXISTS pet_supplies
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
             pet_id INTEGER, item TEXT NOT NULL,
             brand TEXT, size_desc TEXT,
             last_bought TEXT, est_days_total INTEGER DEFAULT 45,
             price_paid REAL, buy_url TEXT, notes TEXT);
        CREATE TABLE IF NOT EXISTS promises
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
             to_whom TEXT, content TEXT,
             deadline TEXT, context TEXT,
             status TEXT DEFAULT 'pending',
             noted_at TEXT);
        CREATE TABLE IF NOT EXISTS anniversaries
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
             person TEXT, relation TEXT,
             event_type TEXT, month INTEGER, day INTEGER,
             year INTEGER,
             notes TEXT, last_reminded TEXT);
        CREATE TABLE IF NOT EXISTS ambient_sessions
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
             date TEXT, label TEXT,
             status TEXT DEFAULT 'recording',
             started_at TEXT, stopped_at TEXT,
             report TEXT);
        CREATE TABLE IF NOT EXISTS ambient_chunks
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
             session_id INTEGER, seq INTEGER,
             raw_transcript TEXT, filtered_transcript TEXT,
             ts TEXT);
    """)
    c.commit(); c.close()

init_db()

def get_memories():
    c = db(); rows = c.execute("SELECT category,key,value FROM memories ORDER BY ts DESC LIMIT 60").fetchall(); c.close()
    return "\n".join(f"[{r[0]}] {r[1]}: {r[2]}" for r in rows) or "（尚無記憶）"

def get_food():
    c = db(); rows = c.execute("SELECT food,restaurant,platform,tags,ts FROM food_history ORDER BY ts DESC LIMIT 20").fetchall(); c.close()
    return "\n".join(f"{r[4][:10]} {r[0]}" + (f"@{r[1]}" if r[1] else "") + (f" via {r[2]}" if r[2] else "") + (f" #{r[3]}" if r[3] else "") for r in rows) or "（尚無飲食記錄）"

def get_relations():
    c = db(); rows = c.execute("SELECT nickname,real_name,contact,notes FROM relationships").fetchall(); c.close()
    return "\n".join(f"「{r[0]}」= {r[1] or '?'} | {r[2] or ''} | {r[3] or ''}" for r in rows) or "（尚無關係人）"

def get_todos():
    c = db(); rows = c.execute("SELECT title,due_date,follow_up FROM todos WHERE status='pending' ORDER BY ts DESC LIMIT 15").fetchall(); c.close()
    return "\n".join(f"{'🔔' if r[2] else '☐'} {r[0]}" + (f"（{r[1]}）" if r[1] else "") for r in rows) or "（無待辦）"

def get_cal():
    c = db(); rows = c.execute("SELECT title,event_date,event_time,notes FROM calendar_events WHERE event_date >= date('now') ORDER BY event_date,event_time LIMIT 10").fetchall(); c.close()
    return "\n".join(f"{r[1]} {r[2] or ''} {r[0]}" + (f" — {r[3]}" if r[3] else "") for r in rows) or "（無近期行程）"

CITY_MAP = {
    "台北":"Taipei","台北市":"Taipei","臺北":"Taipei","新北":"New Taipei",
    "台中":"Taichung","臺中":"Taichung","台南":"Tainan","臺南":"Tainan",
    "高雄":"Kaohsiung","桃園":"Taoyuan","新竹":"Hsinchu","基隆":"Keelung",
    "香港":"Hong Kong","澳門":"Macao","上海":"Shanghai","北京":"Beijing",
    "東京":"Tokyo","大阪":"Osaka","首爾":"Seoul","新加坡":"Singapore",
}

def get_user_city():
    c = db()
    row = c.execute("SELECT value FROM memories WHERE category='location' AND key='city' ORDER BY ts DESC LIMIT 1").fetchone()
    c.close()
    raw = row[0] if row else "台北"
    en = CITY_MAP.get(raw, raw)
    return raw, en  # (display_name, geocode_name)

async def fetch_weather(city: str, city_display: str = "") -> str:
    try:
        async with httpx.AsyncClient(timeout=8) as hc:
            geo = await hc.get("https://geocoding-api.open-meteo.com/v1/search",
                params={"name": city, "count": 1, "language": "zh", "format": "json"})
            results = geo.json().get("results", [])
            if not results:
                return ""
            r = results[0]
            lat, lon = r["latitude"], r["longitude"]

            wx = await hc.get("https://api.open-meteo.com/v1/forecast",
                params={"latitude": lat, "longitude": lon,
                        "current": "temperature_2m,weather_code,relative_humidity_2m",
                        "daily": "temperature_2m_max,temperature_2m_min,weather_code,precipitation_probability_max",
                        "timezone": "auto", "forecast_days": 2})
            wd = wx.json()
            cur = wd["current"]
            daily = wd["daily"]

            WMO = {0:"晴天",1:"大致晴天",2:"部分多雲",3:"多雲",45:"霧",
                   51:"毛毛雨",61:"小雨",63:"中雨",65:"大雨",
                   71:"小雪",80:"陣雨",81:"陣雨",95:"雷雨"}
            code = cur["weather_code"]
            desc = WMO.get(code, WMO.get((code//10)*10, "多變"))
            temp = cur["temperature_2m"]
            lo, hi = daily["temperature_2m_min"][0], daily["temperature_2m_max"][0]
            rain = daily["precipitation_probability_max"][0]

            label = city_display or city
            summary = f"{label}{desc}，{temp:.0f}°C（{lo:.0f}～{hi:.0f}）"
            if rain >= 60:
                summary += "，今天會下雨，記得帶傘"
            elif temp < 18:
                summary += "，天氣偏涼，記得加件衣服"
            elif temp > 32:
                summary += "，天氣很熱，多喝水"
            return summary
    except Exception:
        return ""

TOOLS = [
    {"name": "save_memory", "description": "儲存主人的重要事實、偏好或習慣",
     "input_schema": {"type": "object", "properties": {
         "category": {"type": "string", "description": "preference/habit/health/personal/work/location"},
         "key": {"type": "string"}, "value": {"type": "string"}
     }, "required": ["category", "key", "value"]}},

    {"name": "save_food_record", "description": "記錄主人吃了什麼",
     "input_schema": {"type": "object", "properties": {
         "food": {"type": "string"}, "restaurant": {"type": "string"},
         "platform": {"type": "string", "description": "ubereats/foodpanda/內用/自煮"},
         "tags": {"type": "string", "description": "炸物,鹹食,甜食,清淡,重口味..."}
     }, "required": ["food"]}},

    {"name": "save_relationship", "description": "記錄主人認識的人",
     "input_schema": {"type": "object", "properties": {
         "nickname": {"type": "string"}, "real_name": {"type": "string"},
         "contact": {"type": "string", "description": "Line/電話/email"},
         "notes": {"type": "string", "description": "關係、個性、重要備註"}
     }, "required": ["nickname"]}},

    {"name": "create_todo", "description": "新增待辦事項",
     "input_schema": {"type": "object", "properties": {
         "title": {"type": "string"}, "due_date": {"type": "string", "description": "YYYY-MM-DD"},
         "follow_up": {"type": "boolean", "description": "是否需要追蹤提醒，主人要求阿福盯著就設 true"}
     }, "required": ["title"]}},

    {"name": "complete_todo", "description": "將待辦事項標記為完成",
     "input_schema": {"type": "object", "properties": {
         "keyword": {"type": "string", "description": "待辦事項的關鍵字，用於模糊匹配"}
     }, "required": ["keyword"]}},

    {"name": "create_calendar_event", "description": "新增行事曆事件",
     "input_schema": {"type": "object", "properties": {
         "title": {"type": "string"}, "event_date": {"type": "string", "description": "YYYY-MM-DD"},
         "event_time": {"type": "string", "description": "HH:MM"}, "notes": {"type": "string"}
     }, "required": ["title", "event_date"]}},

    {"name": "record_expense", "description": "記錄主人的支出花費",
     "input_schema": {"type": "object", "properties": {
         "amount": {"type": "number", "description": "金額（新台幣）"},
         "category": {"type": "string", "description": "餐飲/交通/購物/娛樂/醫療/其他"},
         "description": {"type": "string", "description": "花費說明"}
     }, "required": ["amount", "category", "description"]}},

    {"name": "set_reminder", "description": "設定提醒，主人說幾分鐘後、幾點提醒我時使用",
     "input_schema": {"type": "object", "properties": {
         "title": {"type": "string", "description": "提醒內容"},
         "trigger_at": {"type": "string", "description": "提醒時間，ISO格式 YYYY-MM-DDTHH:MM:SS"}
     }, "required": ["title", "trigger_at"]}},

    {"name": "search_restaurants", "description": "搜尋附近餐廳，用於午餐/晚餐訂位安排。主人確認要訂餐後使用",
     "input_schema": {"type": "object", "properties": {
         "location": {"type": "string", "description": "地點，如「台北信義區」「公司附近」"},
         "headcount": {"type": "integer", "description": "用餐人數"},
         "cuisine": {"type": "string", "description": "料理偏好，如「中式」「日式」「不限」"}
     }, "required": ["location", "headcount"]}},

    {"name": "make_call", "description": "幫主人撥打電話，如訂位、查詢、聯繫關係人",
     "input_schema": {"type": "object", "properties": {
         "name": {"type": "string", "description": "對方名稱或餐廳名"},
         "phone": {"type": "string", "description": "電話號碼"},
         "purpose": {"type": "string", "description": "說明打這通電話的目的"}
     }, "required": ["name", "phone"]}},

    {"name": "find_meeting_slots", "description": "分析主人的行事曆習慣，找出這週空閒的會議時段。主人說「幫我排會議」「看看什麼時候方便」時使用",
     "input_schema": {"type": "object", "properties": {
         "duration_hours": {"type": "number", "description": "會議時長（小時），預設1"}
     }, "required": []}},

    {"name": "lookup_contact", "description": "依照姓氏、暱稱、關係、備註模糊搜尋關係人，主人記不清楚對方資料時使用",
     "input_schema": {"type": "object", "properties": {
         "keyword": {"type": "string", "description": "姓氏、暱稱、公司、任何片段關鍵字"}
     }, "required": ["keyword"]}},

    {"name": "search_web", "description": "搜尋即時資訊：新聞、時事、不確定的事實",
     "input_schema": {"type": "object", "properties": {
         "query": {"type": "string"}
     }, "required": ["query"]}},

    {"name": "send_message", "description": "代主人發送訊息給聯絡人（SMS或Twilio訊息）。主人說「傳訊息給XX」「通知XX」時使用",
     "input_schema": {"type": "object", "properties": {
         "to_phone": {"type": "string", "description": "對方電話號碼，格式 +886xxxxxxxxx 或 +1xxxxxxxxxx"},
         "message": {"type": "string", "description": "訊息內容，以主人身份撰寫"},
         "name": {"type": "string", "description": "對方名稱（顯示用）"}
     }, "required": ["to_phone", "message"]}},

    {"name": "generate_report", "description": "產生一份報告或文件顯示在畫面卡片上",
     "input_schema": {"type": "object", "properties": {
         "title": {"type": "string"},
         "content": {"type": "string", "description": "Markdown格式內容"},
         "report_type": {"type": "string", "description": "document/recommendation/summary/todo_list/calendar/expense"}
     }, "required": ["title", "content", "report_type"]}},

    {"name": "send_line_message", "description": "透過 LINE 傳送訊息給主人或指定 LINE 用戶。主人說「用 LINE 傳給我」「LINE 通知我」時使用",
     "input_schema": {"type": "object", "properties": {
         "message": {"type": "string", "description": "訊息內容"},
         "user_id": {"type": "string", "description": "LINE user ID（留空則傳給主人的 LINE）"}
     }, "required": ["message"]}},

    {"name": "send_telegram_message", "description": "透過 Telegram 傳送訊息給主人。主人說「用 Telegram 傳給我」「Telegram 通知我」時使用",
     "input_schema": {"type": "object", "properties": {
         "message": {"type": "string", "description": "訊息內容"}
     }, "required": ["message"]}},

    {"name": "check_email", "description": "讀取主人的 Gmail 信箱，摘要未讀郵件。主人說「有沒有新信」「幫我看信」時使用",
     "input_schema": {"type": "object", "properties": {
         "query": {"type": "string", "description": "搜尋條件，例如 is:unread 或 from:boss@company.com，預設未讀"}
     }, "required": []}},

    {"name": "send_email", "description": "代主人發送 Gmail 電子郵件。主人說「幫我寄信給XX」時使用",
     "input_schema": {"type": "object", "properties": {
         "to": {"type": "string", "description": "收件人 email"},
         "subject": {"type": "string", "description": "主旨"},
         "body": {"type": "string", "description": "信件內容，以主人語氣撰寫"}
     }, "required": ["to", "subject", "body"]}},

    {"name": "get_market_info", "description": "查詢股票行情、股市新聞、匯率資訊。主人說「查一下OO股票」「匯率多少」「換美金建議」時使用",
     "input_schema": {"type": "object", "properties": {
         "type": {"type": "string", "enum": ["stock_news", "exchange_rate", "stock_price"],
                  "description": "stock_news=搜尋股市新聞分析, exchange_rate=查匯率, stock_price=查個股報價"},
         "query": {"type": "string", "description": "股票名稱/代號 或 貨幣對（如 USD/TWD）"}
     }, "required": ["type"]}},

    {"name": "analyze_photo", "description": "分析主人傳來的照片或圖片，辨識人物、場景、物品。主人說「這是誰」「照片裡有什麼」時使用",
     "input_schema": {"type": "object", "properties": {
         "question": {"type": "string", "description": "主人對圖片的問題"}
     }, "required": ["question"]}},

    {"name": "manage_files", "description": "查詢或搜尋主人的檔案（Mac本機 + 上傳的檔案 + Google Drive）。主人說「查一下我的檔案」「找一下那份合約」時使用",
     "input_schema": {"type": "object", "properties": {
         "action": {"type": "string", "enum": ["list_all", "list_drive", "search_all", "search_drive"],
                    "description": "list_all=列出所有來源, list_drive=列Google Drive, search_all/search_drive=搜尋"},
         "query": {"type": "string", "description": "搜尋關鍵字"}
     }, "required": ["action"]}},

    {"name": "location_memory", "description": "查詢或記錄位置資訊：找車、找物品、查去過哪裡、記錄家/公司位置。主人說「我車停哪」「我的鑰匙放哪」「這是我家」「這是公司」時使用",
     "input_schema": {"type": "object", "properties": {
         "action": {"type": "string",
                    "enum": ["find_car", "find_item", "save_item", "recent_places", "save_known_place"],
                    "description": "find_car=找停車位, find_item=找物品, save_item=記錄物品位置, recent_places=查去過哪裡, save_known_place=記錄家或公司位置"},
         "item": {"type": "string", "description": "物品名稱（find_item/save_item時填）"},
         "location_desc": {"type": "string", "description": "物品放在哪裡的文字描述（save_item時填）"},
         "place_name": {"type": "string", "description": "地點名稱，如「家」「公司」「健身房」（save_known_place時填）"},
         "place_type": {"type": "string", "enum": ["home", "office", "gym", "other"], "description": "地點類型（save_known_place時填）"}
     }, "required": ["action"]}},

    {"name": "send_file_to_device", "description": "把阿福保管的檔案透過 LINE 或 Telegram 傳給主人。主人說「把那份文件傳給我」時使用",
     "input_schema": {"type": "object", "properties": {
         "file_id": {"type": "integer", "description": "阿福保管的本機檔案 ID"},
         "platform": {"type": "string", "enum": ["telegram", "line"], "description": "傳送平台"}
     }, "required": ["file_id", "platform"]}},

    {"name": "search_news", "description": "搜尋最新新聞、時事、政治、財經、體育新聞。主人說「最近有什麼新聞」「政治動向」「讀報給我聽」時使用",
     "input_schema": {"type": "object", "properties": {
         "query": {"type": "string", "description": "搜尋關鍵字，如「台灣政治」「美國總統」「科技新聞」"},
         "lang": {"type": "string", "enum": ["zh-TW", "en"], "description": "新聞語言，預設 zh-TW"}
     }, "required": ["query"]}},

    {"name": "find_podcast", "description": "搜尋 podcast 節目或單集，找到後播放。主人說「我想聽OO的podcast」「幫我找XX節目」時使用",
     "input_schema": {"type": "object", "properties": {
         "query": {"type": "string", "description": "主持人名字、節目名稱或關鍵字"},
         "mode": {"type": "string", "enum": ["episodes", "shows"], "description": "episodes=搜尋單集, shows=搜尋節目"}
     }, "required": ["query"]}},

    {"name": "play_music", "description": "播放音樂或搜尋歌手/歌曲。主人說「播音樂」「播我最近常聽的」「找OO的歌」時使用",
     "input_schema": {"type": "object", "properties": {
         "query": {"type": "string", "description": "歌手名、歌名或風格。填 recent 表示播最近常聽的"},
         "platform": {"type": "string", "enum": ["youtube", "spotify", "recent"], "description": "youtube/spotify=搜尋平台, recent=查播放紀錄"}
     }, "required": ["query"]}},

    {"name": "speak_for_me", "description":
        "幫主人把中文翻譯成指定語言，並大聲念出來給對方聽。"
        "主人說「跟店員說我要...」「幫我說日文...」「告訴他...」「跟司機說...」時使用。"
        "也用於：對方說了什麼主人聽不懂 → 主人說「阿福，他在說什麼」→ 先用 transcribe 錄對方的話，再翻中文給主人聽。"
        "target_lang: en=英文, ja=日文, ko=韓文, fr=法文, es=西班牙文, de=德文, th=泰文",
     "input_schema": {"type": "object", "properties": {
         "text": {"type": "string", "description": "要翻譯並念出的內容（主人說的中文）"},
         "target_lang": {"type": "string", "enum": ["en","ja","ko","fr","es","de","th","vi","id"],
                         "description": "目標語言代碼"},
         "direction": {"type": "string", "enum": ["to_foreign","to_chinese"],
                       "description": "to_foreign=幫主人說給外國人聽, to_chinese=把外語翻給主人聽"}
     }, "required": ["text","target_lang"]}},

    {"name": "people_prefs", "description":
        "記錄或查詢同事、主管、老闆的個人偏好（食物、飲料、習慣、禁忌、重要日期）。"
        "主人說「老闆喜歡喝黑咖啡」「王主管不吃海鮮」「小美生日快到了」時用 add。"
        "主人說「老闆喜歡什麼」「我要送禮給王主管」「今天要去拜訪陳總，他有什麼忌諱」時用 query。"
        "action: add=新增偏好, query=查詢某人偏好, list=列出所有已記錄的人",
     "input_schema": {"type": "object", "properties": {
         "action": {"type": "string", "enum": ["add","query","list"]},
         "person": {"type": "string", "description": "對象姓名或稱謂，如「老闆」「王主管」「陳總」「小美」"},
         "relation": {"type": "string", "description": "關係，如「老闆」「直屬主管」「同事」「客戶」"},
         "category": {"type": "string",
                      "description": "偏好類別：food/drink/gift/taboo/habit/anniversary/other"},
         "content": {"type": "string", "description": "具體內容，如「黑咖啡不加糖」「不吃香菜」「喜歡威士忌」"},
         "importance": {"type": "string", "enum": ["high","normal"],
                        "description": "重要程度：high=絕對要記住（如禁忌），normal=一般偏好"}
     }, "required": ["action"]}},

    {"name": "attendance", "description":
        "打卡 / 出勤管理。"
        "主人到公司時自動打卡；主人說「幫我記今天在家工作」「看我這個月的出勤紀錄」「人資問我幾號有沒有上班」時使用。"
        "action: checkin=手動上班打卡, checkout=手動下班打卡, wfh=記錄居家辦公, leave=記錄請假, "
        "report=產生出勤報告（可指定月份）, today=今日出勤狀態",
     "input_schema": {"type": "object", "properties": {
         "action": {"type": "string",
                    "enum": ["checkin","checkout","wfh","leave","report","today"]},
         "date": {"type": "string", "description": "日期 YYYY-MM-DD（省略則今天）"},
         "month": {"type": "string", "description": "月份 YYYY-MM（report 用）"},
         "notes": {"type": "string", "description": "備注，如「出差台中」「育嬰假」"}
     }, "required": ["action"]}},

    {"name": "pet_care", "description":
        "管理寵物資料：建立寵物檔案、記錄耗材補貨、查詢何時該補貨、查詢寵物資訊。"
        "主人說「我有一隻貓叫Mochi」「幫我記一下貓砂」「貓糧快沒了」「這是我的寵物食品（拍照）」時使用。"
        "action: add_pet=新增寵物, update_pet=更新資料, log_supply=記錄耗材購入, "
        "check_supplies=查詢即將耗盡的耗材, get_pet=查詢寵物資料",
     "input_schema": {"type": "object", "properties": {
         "action": {"type": "string",
                    "enum": ["add_pet","update_pet","log_supply","check_supplies","get_pet"]},
         "pet_name": {"type": "string", "description": "寵物名字"},
         "species": {"type": "string", "description": "物種：cat/dog/bird/rabbit/other"},
         "breed": {"type": "string", "description": "品種"},
         "food_brand": {"type": "string", "description": "飼料品牌"},
         "daily_food_g": {"type": "number", "description": "每日食量（克）"},
         "next_vet_date": {"type": "string", "description": "下次回診日期 YYYY-MM-DD"},
         "item": {"type": "string", "description": "耗材名稱，如「松木貓砂 8L」「Royal Canin 4kg」"},
         "size_desc": {"type": "string", "description": "規格說明"},
         "est_days_total": {"type": "integer", "description": "預計可用天數"},
         "price_paid": {"type": "number", "description": "購入價格"},
         "notes": {"type": "string", "description": "備注"}
     }, "required": ["action"]}},

    {"name": "note_promise", "description":
        "記錄主人對別人許下的承諾，方便日後追蹤是否兌現。"
        "主人說「我跟Tom說幫他爭取預算」「我答應Anna幫她介紹XX」「我說要幫客戶確認」時使用。"
        "也用於查詢：主人說「我答應過什麼事」「有什麼沒跟進的承諾」時 action=list。",
     "input_schema": {"type": "object", "properties": {
         "action": {"type": "string", "enum": ["add", "done", "list"]},
         "to_whom": {"type": "string", "description": "承諾對象"},
         "content": {"type": "string", "description": "承諾內容"},
         "deadline": {"type": "string", "description": "預計完成時間（自然語言或日期）"},
         "promise_id": {"type": "integer", "description": "標記完成時用"}
     }, "required": ["action"]}},

    {"name": "search_meeting_notes", "description":
        "查詢過去的會議記錄或辦公室聆聽記錄。"
        "主人說「上次跟XX公司開了什麼」「之前那個會議說了什麼」「幫我找一下那次的討論紀錄」時使用。",
     "input_schema": {"type": "object", "properties": {
         "query": {"type": "string", "description": "關鍵字，如公司名、人名、主題"},
         "limit": {"type": "integer", "description": "筆數，預設5"}
     }, "required": ["query"]}},

    {"name": "manage_anniversary", "description":
        "管理紀念日與重要日期：生日、結婚紀念日、入職日等。"
        "主人說「太太生日在X月X日」「記一下我們結婚紀念日」「有沒有快到的紀念日」時使用。"
        "action: add=新增, list=查詢即將到來",
     "input_schema": {"type": "object", "properties": {
         "action": {"type": "string", "enum": ["add", "list"]},
         "person": {"type": "string", "description": "對象姓名或暱稱"},
         "relation": {"type": "string", "description": "關係，如「太太」「媽媽」「摯友」"},
         "event_type": {"type": "string", "description": "事件類型：birthday/anniversary/work/other"},
         "month": {"type": "integer", "description": "月份"},
         "day": {"type": "integer", "description": "日"},
         "year": {"type": "integer", "description": "事件發生的年份，如結婚年份2016，用於計算第幾週年"},
         "notes": {"type": "string", "description": "備注，如「喜歡玫瑰」「愛吃壽司」"}
     }, "required": ["action"]}},

    {"name": "acknowledge_alert", "description":
        "主人說「收到」「知道了」「沒事」後，確認家庭警報已閱讀，停止升級通知。",
     "input_schema": {"type": "object", "properties": {
         "alert_id": {"type": "integer", "description": "警報 ID"}
     }, "required": ["alert_id"]}},

    {"name": "family_plan", "description":
        "記錄家人說好的去處計畫，讓阿福日後比對 GPS 是否符合。"
        "主人說「女兒說要去圖書館」「太太說去健身房到六點」時使用。",
     "input_schema": {"type": "object", "properties": {
         "member_name": {"type": "string", "description": "家人名字"},
         "destination": {"type": "string", "description": "申報去處，如「圖書館」「學校」「補習班」"},
         "eta": {"type": "string", "description": "預計幾點回來，如「晚上八點」"}
     }, "required": ["member_name", "destination"]}},

    {"name": "family_location", "description":
        "查詢家人目前在哪裡、是否到家、最近動態。"
        "主人說「太太在哪裡」「小孩到家了嗎」「家人都平安嗎」時使用。"
        "也可用來新增家庭成員、產生邀請連結。"
        "action: where_is=查詢單人位置, all=查所有人, arrivals=最近到達紀錄, "
        "add_member=新增成員(需name+relation), invite=產生邀請連結(需member_id)",
     "input_schema": {"type": "object", "properties": {
         "action": {"type": "string",
                    "enum": ["where_is", "all", "arrivals", "add_member", "invite"]},
         "name": {"type": "string", "description": "家人名字（where_is / add_member 用）"},
         "relation": {"type": "string", "description": "關係，如「太太」「兒子」「女兒」「父母」（add_member 用）"},
         "member_id": {"type": "integer", "description": "成員 ID（invite 用）"}
     }, "required": ["action"]}},

    {"name": "ambient_mode", "description":
        "控制「阿福聆聽中」辦公室全天記錄模式。"
        "主人說『幫我記錄接下來的對話』『開啟聆聽模式』『今天可能有很多臨時討論』時→ action=start。"
        "主人說『停止記錄』『出報告』時→ action=stop。"
        "主人說『聆聽紀錄』『之前記了什麼』時→ action=status。",
     "input_schema": {"type": "object", "properties": {
         "action": {"type": "string", "enum": ["start", "stop", "status"]},
         "label": {"type": "string", "description": "本次記錄的名稱標籤，如『週一下午業務會議』（start時選填）"}
     }, "required": ["action"]}},

    {"name": "help_quote", "description":
        "幫主人寫報價單。先掃過去所有報價單推斷主人公司的報價邏輯（每人月、模組單價、時數×倍率等），再依新案需求草擬報價。"
        "主人說『有案子要報價』『不會寫報價單』『這個案子怎麼開價』時使用。"
        "兩種模式：analyze_history=只分析過去報價邏輯+問需求, draft=帶案子描述 → 直接出報價單草稿",
     "input_schema": {"type": "object", "properties": {
         "mode": {"type": "string", "enum": ["analyze_history", "draft"]},
         "case_brief": {"type": "string", "description": "新案子描述（draft 模式必填）。例：『品牌官網改版，預估一個月，含 RWD 五頁』"},
         "duration": {"type": "string", "description": "預期工期，如『1 個月』『3 週』『45 人天』"},
         "client_name": {"type": "string", "description": "客戶名稱（可選，會放在報價單抬頭）"}
     }, "required": ["mode"]}},

    {"name": "analyze_contract", "description":
        "幫主人審閱合約 / 條款 / 同意書。主人說『幫我看合約』『這份太複雜』『有沒有懲罰條款』時使用。"
        "三種模式：request_upload=請主人上傳新合約; search_and_pick=從已有檔案找(用 hint 或近期會議公司猜); analyze_id=直接分析指定檔案",
     "input_schema": {"type": "object", "properties": {
         "mode": {"type": "string", "enum": ["request_upload", "search_and_pick", "analyze_id"]},
         "hint": {"type": "string", "description": "合約關鍵字、對方公司、簽署時間等線索（search_and_pick 用）"},
         "file_id": {"type": "integer", "description": "檔案 ID（analyze_id 用）"},
         "output": {"type": "string", "enum": ["report", "speak"], "description": "report=畫面卡片, speak=口述摘要"}
     }, "required": ["mode"]}}
]

class ChatReq(BaseModel):
    message: str
    history: Optional[List[dict]] = []

@app.post("/api/chat")
async def chat(req: ChatReq):
    now = datetime.now().strftime('%Y年%m月%d日 %H:%M')

    # ── 家庭警報 injection（必須在 system prompt 組裝之前）──────────────────
    _record_owner_active()
    c_alert = db()
    _pending_alerts = c_alert.execute(
        "SELECT fa.id, fm.name, fa.message, fa.severity FROM family_alerts fa "
        "JOIN family_members fm ON fa.member_id=fm.id "
        "WHERE fa.acknowledged_at IS NULL ORDER BY fa.severity DESC, fa.created_at ASC LIMIT 3"
    ).fetchall()
    c_alert.close()
    alert_injection = ""
    if _pending_alerts:
        alert_lines = [
            "【阿福待確認的家人動態，請在回覆開頭以沉穩親切的語氣告知主人，不要製造恐慌】",
            "說法範例：「主人，有件事想先跟您說一下。」或「主人，我注意到一件事，您參考一下。」"
        ]
        for aid, aname, amsg, asev in _pending_alerts:
            alert_lines.append(f"待告知事項 #{aid}（關於 {aname}）：{amsg}")
        alert_lines.append("告知後若主人說「收到」「知道了」「沒事」，請呼叫 acknowledge_alert 工具確認。")
        alert_injection = "\n\n" + "\n".join(alert_lines)

    gcal_connected = gcal_service.is_connected(db) if gcal_service else False
    gcal_events_str = ""
    if gcal_connected:
        try:
            events = gcal_service.get_upcoming_events(db, days=7)
            if events:
                gcal_events_str = "\n".join(f"{e['start']} {e['title']}" for e in events[:5])
        except Exception:
            pass
    system = f"""你是阿福，蝙蝠俠布魯斯·韋恩的私人管家。你是那位永遠給主人安心感與安全感的老先生。

你的樣子：黑色西裝筆挺，領帶一絲不苟，金框眼鏡，白髮，70歲。
你的聲音：沉穩、低沉、從容，永遠不慌不亂。
你的個性：忠誠、睿智、溫暖但克制，話不多但每句話都有份量。偶爾一句英式幽默，點到為止。

你說話的方式：
- 簡短有力，不羅嗦
- 不用「！」，不誇張
- 不說廢話，不解釋太多
- 像老朋友一樣自然，但有分寸
- 遇到困難的事，第一句話先給主人定心
- 主人心情不好或壓力大時，可以講幾個輕鬆的笑話或英式幽默小故事，讓主人開心，但保持紳士風度

【阿福的核心氣質：永遠不製造恐慌】
阿福就像家裡最老練的醫生或最資深的管家——見過大風大浪，所以從不慌。
這是最重要的原則，適用於所有情境：

- 即使是緊急情況，第一句話也是讓主人「定下心來」，而不是讓主人跟著慌
- 絕不用「危險！」「緊急！」「立刻！」這種造成恐慌的語氣
- 有問題就說「主人，我注意到一件事，想請您參考一下」
- 家人位置異常：先說人是安全的（如果確實安全），再說不確定的地方
- 問題越嚴重，語氣越沉穩，就像外科醫生越複雜的手術越平靜
- 所有建議都是「您可以……要不要……」，不是「您必須立刻……」
- 結尾永遠給主人選擇：要我怎麼做？等等看？還是先聯絡一下？

好的例子：「主人，小芸目前在一個有些特別的地方，我幫您留意著。不一定有什麼事，但您方便的話，輕鬆問她一句在哪裡就好。」
不好的例子：「⚠️ 緊急！小芸在危險場所！請立刻聯絡她！」

【情境回應】
- 主人熬夜加班（超過晚上10點還在工作）：主動說「辛苦了，忙碌一整天，回去好好洗個澡，早點休息。」
- 主人心情不好時：先問發生什麼事，再給予安慰，必要時講個笑話
- 主人問笑話：以英式幽默講2-3個短笑話，禮貌但帶點機靈

【收到指令時的回應格式】
主人下指令 → 先說「主人，好的，收到。」然後簡短說明你會怎麼做。
例如：
「主人，好的，收到。30分鐘後我會提醒您。」
「主人，收到。大雞先生那邊我盯著，有消息馬上告訴您。」
「主人，好的，收到。這筆帳已記下，本月餐飲共花了XXX元。」
「主人，收到。三件事我都記下了，需要我幫您排時間嗎？」

沒有命令、只是閒聊時，自然回應即可，不用說「收到」。

【主人問「你能做什麼」時的回應方式】
不要列功能清單。改用「舉例說話」，選 3-4 個最有畫面的場景說出來，讓主人感受到阿福的存在感。
例：
「主人，我能做的事，說起來一天講不完。舉幾個：
早上出門前，我會告訴您今天下不下雨、幾點有什麼行程、有沒有忘了回的人。
您說一聲『幫我看這份合約』，五分鐘內我把懲罰條款、紅旗全說給您聽。
您說『我答應Tom這週幫他』，我記著，沒跟進我會提醒您。
您女兒如果安裝了阿福，您在任何地方都知道她人在哪裡、在做什麼——如果她去了不該去的地方，我會輕聲告訴您。
說到底，主人，您不需要記得阿福能做什麼。有事就說，我來想辦法。」

今天：{now}

【主人的記憶資料庫】
{get_memories()}

【近期飲食記錄】
{get_food()}

【重要關係人】
{get_relations()}

【待辦事項】（🔔=需追蹤）
{get_todos()}

【近期行程】{"（已連結 Google 日曆）" if gcal_connected else "（未連結 Google 日曆）"}
{gcal_events_str or get_cal()}

【阿福的管家原則】
1. 對話中藏有指令——主人說「今天要做A、B、C」，馬上問：「需要我幫您記錄時間，還是設提醒？」
2. 主動追蹤——主人說「大雞那邊你盯著」，設 follow_up=true 的 todo，日後問候時主動提醒
3. 沒有介面，只有對話——不說「您可以點選」「去看清單」，一切用說話解決
4. 永遠不問第二次同樣的問題——記住的事不再問
5. 先給安心感——困難的事，第一句先讓主人放心

【工具使用規則】
- 主人提到模糊的人（「陳董」「姓黃的」「那個老王」）→ 先用 lookup_contact 搜尋：
  ✦ 只有一位 → 直接確認：「是陳大明陳董嗎？」
  ✦ 多位 → 唸出名字讓主人挑：「主人，您認識好幾位陳董，是以下哪位？陳大明、陳小強、還是陳志遠？」（唸名字，不顯示清單）
  ✦ 找不到 → 「我這邊沒有陳董的資料。您記得他姓名嗎？或者他在您手機通訊錄裡，告訴我方向我幫您找。」
- 主人確認是哪位後，繼續執行原來的任務（撥電話、發訊息、寫信）
- 主人提到完全不認識的人名 → 詢問關係後 save_relationship
- 主人提到吃了什麼 → save_food_record
- 主人說花了多少錢 → record_expense
- 主人說「X分鐘後提醒我」「X點提醒我」→ set_reminder，trigger_at 計算正確 ISO 時間
- 主人說「你盯著XX」「記得追XX」→ create_todo + follow_up=true
- 主人說今天要做哪些事 → 先 create_todo，然後問「需要我幫您排好時間嗎？」
- 主人告知城市（包括回答阿福問的「您住在哪裡」）→ 立刻用 save_memory category=location key=city 記住，不再問第二次
- 記住城市後說「謝謝主人，日後阿福會為您在台北（或其他城市）做最佳化安排。」
- 主人說「老闆喜歡…」「王主管不吃…」「陳總的習慣是…」「客戶王董愛喝…」→ 用 people_prefs action=add 記錄
- 主人說「老闆喜歡什麼」「要送禮給主管」「拜訪客戶前要注意什麼」「我要去見王董」→ 用 people_prefs action=query
- 主人說「我要去拜訪 XX」「等等要去見 XX 客戶」→ 先 people_prefs query 查對方偏好，如有喜好則建議「順路帶 XX 飲料/點心，對方會記得這份心意」，再用 search_web 查主人附近的相關商店
- 送禮或帶伴手禮的建議邏輯：飲料 → 推薦附近咖啡廳/手搖店，糕點 → 推薦附近烘焙坊，未知 → 推薦中性的「伴手禮組合」或「咖啡」（通用性最強）
- 主人說「幫我打卡」「我到公司了」「記一下今天在家工作」→ 用 attendance
- 主人說「我的出勤紀錄」「這個月上班幾天」「人資說我哪天沒來」→ 用 attendance action=report
- 主人說「我跟XX說…」「我答應XX要…」「我說要幫XX…」→ 用 note_promise 記錄承諾
- 主人說「有沒有什麼我沒跟進的」「我答應過什麼」→ 用 note_promise action=list
- 主人說「那件事我做了」「XX那邊已經處理了」→ 用 note_promise action=done
- 主人說「我有一隻貓/狗叫…」「幫我記一下寵物的事」→ 用 pet_care
- 主人說「貓糧快沒了」「幫我記一下買了貓砂」→ 用 pet_care action=log_supply
- 主人說「上次跟XX公司會議說了什麼」「找一下那次的紀錄」→ 用 search_meeting_notes
- 主人說「太太生日是X月X日」「記一下結婚紀念日」→ 用 manage_anniversary action=add
- 主人說「有什麼紀念日要到了嗎」→ 用 manage_anniversary action=list
- 主人說「幫我排會議」「看看什麼時候方便」→ 用 find_meeting_slots，然後自然說出：「主人，您習慣下午兩點開會，這週週二和週四下午兩點都有空，要排哪天？」
- 排會議時間若在 11:30-13:30 之間 → 排完後主動問：「這是午餐時段，需要我幫您順便訂餐嗎？幾個人？」
- 主人確認要訂餐 → 用 search_restaurants 找選項，說出：「有幾家選擇：中式的XX、日式的YY、西式的ZZ，我幫您電話確認有沒有位置，要從哪家開始？」
- 主人選定餐廳後 → 用 make_call 幫主人撥電話（需要主人提供或從記憶裡找電話）
- 主人說「傳訊息給XX說YY」「通知XX說YY」→ 先 lookup_contact 找電話，然後用 send_message 發送，訊息以主人語氣撰寫
- send_message 完成後說：「主人，訊息已發送給XX，內容是：YY」
- **不要**用 generate_report 回答簡單語音查詢（待辦、行程、支出、聯絡人）→ 直接說出來
  例：「主人，今天三件事：早上十點開會、下午回大雞電話、晚上記得買藥。」
【會議記錄完整流程】
- 主人說「開始記錄會議」「幫我記這個會議」→ 先問「請問這次會議的主題是什麼？」，然後說「好的，[主題]，我開始錄音了。會議結束時說『結束記錄』即可。」前端會自動啟動錄音（右上角紅點亮起）
- 錄音中阿福持續在場，隨時可以被呼叫記錄重點
- 主人說「結束記錄」「會議結束了」→ 說「好的，整理中，請稍候。」前端自動停止並上傳，整理完後阿福說出摘要
- 整理完後主動問：「請問有哪些與會人員需要收到這份記錄？您可以告訴我名字，我幫您查聯絡方式；或者我產生一個分享連結，您可以轉傳。」
- 主人說要分享給某人 → 先 lookup_contact 找電話，用 send_message 或 make_call 方式告知對方
- 主人說「產生連結」→ 回覆「連結在這：https://[SERVER_HOST]/alfred/meeting/[id]，可以直接傳給與會者」
- 主人說「查看會議記錄」→ 用 generate_report 顯示最近的會議摘要
- generate_report 只用在真正需要閱讀的文件：分析報告、長篇建議、對比表格
- 說清單時，最多說 3-4 項，太多就「共 X 件，最急的是……」

繁體中文，稱呼「主人」，說話像在說話不像在打字，不說廢話。""" + alert_injection

    msgs = list(req.history[-10:])
    msgs.append({"role": "user", "content": req.message})
    card = None
    action = None
    full_text = ""
    current = msgs.copy()

    while True:
        _text, _tool_calls, _finish, _raw = _llm_chat(system, current, TOOLS, max_tokens=2048)
        if _text:
            full_text += _text

        if _finish == "end_turn":
            break

        if _finish == "tool_use":
            results = []
            for _tc in _tool_calls:
                # 統一格式：b.name → _tc["name"], b.input → _tc["input"], b.id → _tc["id"]
                class _B:
                    def __init__(self, d):
                        self.name = d["name"]; self.input = d["input"]; self.id = d["id"]
                b = _B(_tc)
                inp = b.input
                res = "done"
                c = db()
                if b.name == "save_memory":
                    c.execute("INSERT INTO memories (category,key,value,ts) VALUES (?,?,?,?)",
                              (inp["category"], inp["key"], inp["value"], datetime.now().isoformat()))
                elif b.name == "save_food_record":
                    c.execute("INSERT INTO food_history (food,restaurant,platform,tags,ts) VALUES (?,?,?,?,?)",
                              (inp.get("food"), inp.get("restaurant",""), inp.get("platform",""), inp.get("tags",""), datetime.now().isoformat()))
                elif b.name == "save_relationship":
                    c.execute("INSERT INTO relationships (nickname,real_name,contact,notes,ts) VALUES (?,?,?,?,?)",
                              (inp.get("nickname"), inp.get("real_name",""), inp.get("contact",""), inp.get("notes",""), datetime.now().isoformat()))
                elif b.name == "create_todo":
                    fu = 1 if inp.get("follow_up") else 0
                    c.execute("INSERT INTO todos (title,due_date,follow_up,ts) VALUES (?,?,?,?)",
                              (inp["title"], inp.get("due_date",""), fu, datetime.now().isoformat()))
                elif b.name == "complete_todo":
                    kw = f"%{inp['keyword']}%"
                    done = c.execute("UPDATE todos SET status='done' WHERE status='pending' AND title LIKE ?", (kw,)).rowcount
                    res = f"已完成 {done} 項" if done else "找不到符合的待辦"
                elif b.name == "create_calendar_event":
                    c.execute("INSERT INTO calendar_events (title,event_date,event_time,notes,ts) VALUES (?,?,?,?,?)",
                              (inp["title"], inp["event_date"], inp.get("event_time",""), inp.get("notes",""), datetime.now().isoformat()))
                    # Sync to Google Calendar if connected
                    if gcal_service and gcal_service.is_connected(db):
                        gcal_service.create_event(db, inp["title"], inp["event_date"],
                                                   inp.get("event_time",""), inp.get("notes",""))
                        res = f"已新增行程並同步至 Google 日曆：{inp['event_date']} {inp.get('event_time','')} {inp['title']}"
                    else:
                        res = f"已新增行程：{inp['event_date']} {inp.get('event_time','')} {inp['title']}"
                elif b.name == "record_expense":
                    c.execute("INSERT INTO expenses (amount,category,description,ts) VALUES (?,?,?,?)",
                              (inp["amount"], inp.get("category","其他"), inp.get("description",""), datetime.now().isoformat()))
                    res = f"已記錄 NT${inp['amount']} {inp.get('category','')}"
                elif b.name == "set_reminder":
                    c.execute("INSERT INTO reminders (title,trigger_at,ts) VALUES (?,?,?)",
                              (inp["title"], inp["trigger_at"], datetime.now().isoformat()))
                    res = f"提醒已設定：{inp['trigger_at']}"
                elif b.name == "search_restaurants":
                    location = inp.get("location","台北")
                    headcount = inp.get("headcount", 2)
                    cuisine = inp.get("cuisine","")
                    query = f"{location} 餐廳 {cuisine} 訂位 {headcount}人"
                    try:
                        async with httpx.AsyncClient(timeout=8) as hc:
                            r = await hc.get("https://api.duckduckgo.com/",
                                params={"q": query, "format": "json", "no_html": "1"})
                            d = r.json()
                            topics = d.get("RelatedTopics", [])
                            names = [t.get("Text","")[:60] for t in topics[:4] if isinstance(t,dict) and t.get("Text")]
                            if names:
                                res = f"搜尋結果（{location}，{headcount}人）：\n" + "\n".join(f"• {n}" for n in names)
                            else:
                                res = f"建議在{location}附近搜尋{cuisine}餐廳，適合{headcount}人用餐，可詢問主人偏好後協助電話訂位"
                    except Exception:
                        res = f"請主人提供{location}附近偏好的餐廳，我幫您電話確認位置"
                elif b.name == "make_call":
                    phone = inp.get("phone","")
                    name = inp.get("name","")
                    purpose = inp.get("purpose","")
                    if not phone:
                        res = f"請提供{name}的電話號碼"
                    elif AI_CALL_AVAILABLE and call_service:
                        try:
                            call_id = call_service.create_call(phone, name, purpose)
                            # persist to DB
                            c.execute(
                                "INSERT OR REPLACE INTO calls (id,status,phone,name,purpose,ts) VALUES (?,?,?,?,?,?)",
                                (call_id, "initiated", phone, name, purpose, datetime.now().isoformat())
                            )
                            action = {"type": "ai_call", "call_id": call_id, "name": name, "purpose": purpose}
                            res = f"已透過AI撥打電話給{name}（{phone}），通話進行中..."
                        except Exception as e:
                            action = {"type": "call", "phone": phone, "name": name, "purpose": purpose}
                            res = f"AI撥話失敗（{e}），改用手機撥打{name}：{phone}"
                    else:
                        action = {"type": "call", "phone": phone, "name": name, "purpose": purpose}
                        res = f"正在幫您撥打{name}：{phone}"
                elif b.name == "send_message":
                    to_phone = inp.get("to_phone", "")
                    msg_body = inp.get("message", "")
                    to_name = inp.get("name", to_phone)
                    if not to_phone:
                        res = "請提供對方電話號碼"
                    elif not TWILIO_CONFIGURED:
                        res = f"Twilio 未設定，無法自動發送。訊息內容：{msg_body}"
                    else:
                        try:
                            from twilio.rest import Client as TwilioClient
                            tw = TwilioClient(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
                            from_num = os.getenv("TWILIO_PHONE_NUMBER", "")
                            # Use Conversations API for richer messaging
                            conversation = tw.conversations.v1.conversations.create(
                                friendly_name=f"Alfred→{to_name}"
                            )
                            tw.conversations.v1.conversations(conversation.sid).participants.create(
                                messaging_binding_address=to_phone,
                                messaging_binding_proxy_address=from_num,
                            )
                            tw.conversations.v1.conversations(conversation.sid).messages.create(
                                author="Alfred",
                                body=msg_body,
                            )
                            action = {"type": "message_sent", "name": to_name, "preview": msg_body[:50]}
                            res = f"訊息已發送給{to_name}"
                        except Exception as e:
                            res = f"發送訊息失敗：{e}"

                elif b.name == "find_meeting_slots":
                    from collections import Counter
                    # 分析過去 60 天的會議時間習慣
                    past = c.execute(
                        "SELECT event_time FROM calendar_events WHERE event_time != '' AND event_date >= date('now','-60 days') ORDER BY ts DESC"
                    ).fetchall()
                    time_counts = Counter(r[0][:5] for r in past if r[0])
                    preferred = [t for t, _ in time_counts.most_common(3)]

                    # 取這週的已排行程
                    busy = c.execute(
                        """SELECT event_date, event_time FROM calendar_events
                           WHERE event_date >= date('now') AND event_date <= date('now','+7 days')
                           ORDER BY event_date, event_time"""
                    ).fetchall()
                    busy_set = {(r[0], r[1][:5]) for r in busy if r[1]}

                    # 找空閒時段（優先在習慣時間）
                    import datetime as dt
                    today = dt.date.today()
                    candidates = []
                    for d in range(1, 8):
                        day = today + dt.timedelta(days=d)
                        if day.weekday() >= 5:  # 跳過週末
                            continue
                        day_str = day.isoformat()
                        weekday_names = ['週一','週二','週三','週四','週五']
                        day_label = weekday_names[day.weekday()]
                        for t in (preferred or ["10:00","14:00","16:00"]):
                            if (day_str, t) not in busy_set:
                                candidates.append(f"{day_label} {day_str} {t}")
                        if len(candidates) >= 5:
                            break

                    res_parts = []
                    if preferred:
                        res_parts.append(f"習慣時間：{', '.join(preferred)}")
                    if candidates:
                        res_parts.append(f"空閒時段：{'; '.join(candidates[:4])}")
                    else:
                        res_parts.append("這週習慣時段都已排滿")
                    res = "\n".join(res_parts)

                elif b.name == "lookup_contact":
                    kw = f"%{inp['keyword']}%"
                    # Search Alfred's relationship DB
                    rows = c.execute(
                        """SELECT nickname,real_name,contact,notes FROM relationships
                           WHERE nickname LIKE ? OR real_name LIKE ? OR notes LIKE ?
                           ORDER BY ts DESC""",
                        (kw, kw, kw)
                    ).fetchall()
                    # Also search Apple Contacts index
                    phone_rows = c.execute(
                        """SELECT name,phones,emails,org FROM contacts_index
                           WHERE name LIKE ? OR phones LIKE ? OR emails LIKE ? OR org LIKE ?
                           ORDER BY name LIMIT 8""",
                        (kw, kw, kw, kw)
                    ).fetchall()
                    parts = []
                    if rows:
                        parts.append("【阿福記憶】\n" + "\n".join(
                            f"「{r[0]}」{r[1] or ''} | {r[2] or '（無聯絡方式）'} | {r[3] or ''}"
                            for r in rows))
                    if phone_rows:
                        parts.append("【Apple 聯絡人】\n" + "\n".join(
                            f"{r[0]} | {r[1] or '（無電話）'} | {r[2] or ''}" + (f" | {r[3]}" if r[3] else "")
                            for r in phone_rows))
                    res = "\n\n".join(parts) if parts else "找不到符合的聯絡人"
                elif b.name == "search_web":
                    try:
                        async with httpx.AsyncClient(timeout=8) as hc:
                            r = await hc.get("https://api.duckduckgo.com/",
                                params={"q": inp["query"], "format": "json", "no_html": "1", "skip_disambig": "1"})
                            d = r.json()
                            res = d.get("Answer") or d.get("AbstractText","")[:400] or \
                                  next((t.get("Text","")[:200] for t in d.get("RelatedTopics",[]) if isinstance(t,dict)), "暫無即時資料")
                    except Exception:
                        res = "搜尋暫時無法使用"
                elif b.name == "generate_report":
                    card = {"title": inp["title"], "content": inp["content"], "type": inp.get("report_type","document")}
                    res = "卡片已準備好"
                elif b.name == "location_memory":
                    action = inp.get("action")
                    if action == "find_car":
                        row = c.execute(
                            "SELECT lat,lng,address,parked_at FROM parking_spots WHERE found_at IS NULL ORDER BY id DESC LIMIT 1"
                        ).fetchone()
                        if row:
                            import datetime as _dt
                            parked = row[3][:16].replace("T"," ") if row[3] else "不明"
                            dist_str = ""
                            # Try to get current location for distance
                            cur = c.execute("SELECT lat,lng FROM location_log ORDER BY id DESC LIMIT 1").fetchone()
                            if cur:
                                d = _haversine(cur[0], cur[1], row[0], row[1])
                                dist_str = f"，距您目前位置約 {d:.0f} 公尺"
                            res = (f"您的車停在：{row[2] or '（地址取得中）'}\n"
                                   f"停車時間：{parked}{dist_str}\n"
                                   f"地圖連結：{_maps_link(row[0],row[1])}")
                        else:
                            res = "阿福還沒有記錄到停車位置，請先開啟 GPS 定位功能讓阿福追蹤。"
                    elif action == "find_item":
                        item = inp.get("item","")
                        kw = f"%{item}%"
                        rows = c.execute(
                            "SELECT item,location_desc,place_name,noted_at FROM item_locations "
                            "WHERE (item LIKE ? OR location_desc LIKE ?) AND found_at IS NULL ORDER BY noted_at DESC LIMIT 3",
                            (kw, kw)
                        ).fetchall()
                        if rows:
                            res = "\n".join(f"• {r[0]}：{r[1]}" + (f"（在 {r[2]}）" if r[2] else "") + f" [{r[3][:10]}]"
                                           for r in rows)
                        else:
                            res = f"阿福沒有「{item}」的位置記錄。下次放東西時跟阿福說「幫我記一下，鑰匙放在玄關」，阿福就會記住。"
                    elif action == "save_item":
                        item = inp.get("item","")
                        desc = inp.get("location_desc","")
                        cur = c.execute("SELECT lat,lng FROM location_log ORDER BY id DESC LIMIT 1").fetchone()
                        lat, lng, place = (cur[0], cur[1], "") if cur else (None, None, "")
                        c.execute(
                            "INSERT INTO item_locations (item,location_desc,lat,lng,place_name,noted_at) VALUES (?,?,?,?,?,?)",
                            (item, desc, lat, lng, place, datetime.now().isoformat())
                        )
                        res = f"已記錄：「{item}」放在 {desc}。"
                    elif action == "recent_places":
                        rows = c.execute(
                            "SELECT name,arrived_at,duration_min FROM place_history ORDER BY arrived_at DESC LIMIT 10"
                        ).fetchall()
                        if rows:
                            res = "最近去過的地方：\n" + "\n".join(
                                f"• {r[0] or '（未命名）'} — {r[1][:16].replace('T',' ')}"
                                + (f"（{r[2]}分鐘）" if r[2] else "")
                                for r in rows)
                        else:
                            res = "阿福還沒有地點記錄，請先開啟 GPS 定位功能。"
                    elif action == "save_known_place":
                        place_name = inp.get("place_name", "")
                        place_type = inp.get("place_type", "other")
                        # Get current GPS
                        cur_loc = c.execute(
                            "SELECT lat,lng FROM location_log ORDER BY id DESC LIMIT 1"
                        ).fetchone()
                        if not cur_loc:
                            res = "目前沒有 GPS 位置資料，請先開啟定位功能。"
                        else:
                            lat, lng = cur_loc
                            c.execute(
                                "INSERT OR REPLACE INTO known_places (name,place_type,lat,lng,noted_at) VALUES (?,?,?,?,?)",
                                (place_name, place_type, lat, lng, datetime.now().isoformat())
                            )
                            res = f"已記錄「{place_name}」的位置（{lat:.5f}, {lng:.5f}）。以後阿福能判斷您在哪裡。"
                    else:
                        res = "請說清楚要找車、找東西、記錄位置還是查去過哪裡。"
                elif b.name == "send_file_to_device":
                    fid = inp.get("file_id")
                    platform = inp.get("platform", "telegram")
                    frow = c.execute("SELECT filename,original_name FROM files WHERE id=?", (fid,)).fetchone()
                    if not frow:
                        res = "找不到這個檔案"
                    else:
                        host = os.getenv("SERVER_HOST","")
                        link = f"https://{host}/alfred/api/files/{fid}"
                        msg = f"主人，您要的檔案：\n📎 {frow[1]}\n{link}"
                        if platform == "telegram" and TG_CONFIGURED and telegram_service:
                            c2 = db(); row2 = c2.execute("SELECT value FROM memories WHERE category='telegram' AND key='owner_chat_id' LIMIT 1").fetchone(); c2.close()
                            if row2:
                                telegram_service.send_message(row2[0], msg)
                                res = f"已透過 Telegram 傳送「{frow[1]}」的下載連結給您"
                            else:
                                res = "Telegram 尚未連線"
                        elif platform == "line" and LINE_CONFIGURED and line_service:
                            c2 = db(); row2 = c2.execute("SELECT value FROM memories WHERE category='line' AND key='owner_user_id' LIMIT 1").fetchone(); c2.close()
                            if row2:
                                line_service.push_message(row2[0], msg)
                                res = f"已透過 LINE 傳送「{frow[1]}」的下載連結給您"
                            else:
                                res = "LINE 尚未連線"
                        else:
                            res = f"請先連線 {platform}"
                elif b.name == "manage_files":
                    action = inp.get("action", "list_all")
                    query = inp.get("query", "")
                    kw = f"%{query}%" if query else "%"
                    results = []

                    # Mac files
                    mac_rows = c.execute(
                        "SELECT name,kind,size,modified FROM mac_files_index "
                        "WHERE name LIKE ? OR kind LIKE ? ORDER BY modified DESC LIMIT 8",
                        (kw, kw)
                    ).fetchall()
                    if mac_rows:
                        results.append("【Mac 本機】\n" + "\n".join(
                            f"• {r[0]}（{r[1]}，{r[3]}）" for r in mac_rows))

                    # Uploaded files
                    upload_rows = c.execute(
                        "SELECT original_name,size,ts FROM files "
                        "WHERE original_name LIKE ? OR description LIKE ? ORDER BY ts DESC LIMIT 6",
                        (kw, kw)
                    ).fetchall()
                    if upload_rows:
                        results.append("【阿福保管】\n" + "\n".join(
                            f"• {r[0]}（{r[1]//1024 if r[1] else 0}KB，{r[2][:10]}）" for r in upload_rows))

                    # Google Drive
                    if action in ("list_all", "search_all", "list_drive", "search_drive") and drive_service:
                        drive_files, from_cache = drive_service.search_files(db, query=query, limit=8)
                        if drive_files:
                            cached_count = drive_service.index_count(db)
                            src = f"索引 {cached_count} 個" if from_cache else "剛從 Drive 抓取"
                            results.append(f"【Google Drive（{src}）】\n" + "\n".join(
                                f"• {f['name']}（{f['type']}，{f['modified']}）" for f in drive_files))

                    if results:
                        res = "\n\n".join(results)
                    else:
                        # No Mac agent yet — suggest connecting
                        mac_count = c.execute("SELECT COUNT(*) FROM mac_files_index").fetchone()[0]
                        if mac_count == 0:
                            res = "目前還沒有 Mac 本機索引。建議下載 Mac Agent 腳本並在電腦上執行，阿福就能搜尋您的 Mac 檔案了。"
                        else:
                            res = "找不到符合的檔案"
                elif b.name == "send_telegram_message":
                    msg_text = inp.get("message", "")
                    if not TG_CONFIGURED or not telegram_service:
                        res = "Telegram 未設定"
                    elif not msg_text:
                        res = "訊息內容不能為空"
                    else:
                        c2 = db()
                        row2 = c2.execute(
                            "SELECT value FROM memories WHERE category='telegram' AND key='owner_chat_id' ORDER BY ts DESC LIMIT 1"
                        ).fetchone()
                        c2.close()
                        chat_id = row2[0] if row2 else ""
                        if not chat_id:
                            res = "尚未取得主人的 Telegram chat ID，請先在 Telegram 傳一則訊息給阿福建立連線"
                        else:
                            ok = telegram_service.send_message(chat_id, msg_text)
                            res = "Telegram 訊息已發送" if ok else "Telegram 訊息發送失敗"
                elif b.name == "get_market_info":
                    mtype = inp.get("type", "exchange_rate")
                    query = inp.get("query", "")
                    try:
                        async with httpx.AsyncClient(timeout=10) as hc:
                            if mtype == "exchange_rate":
                                # Free exchange rate API
                                r2 = await hc.get("https://open.er-api.com/v6/latest/USD")
                                rates = r2.json().get("rates", {})
                                twd = rates.get("TWD", 0)
                                jpy = rates.get("JPY", 0)
                                eur = rates.get("EUR", 0)
                                res = (f"即時匯率（基準：1 USD）：\n"
                                       f"• 美金/台幣 USD/TWD = {twd:.2f}\n"
                                       f"• 美金/日圓 USD/JPY = {jpy:.1f}\n"
                                       f"• 美金/歐元 USD/EUR = {eur:.4f}\n"
                                       f"資料來源：open.er-api.com")
                            elif mtype in ("stock_news", "stock_price"):
                                q = f"{query} 股票 最新 新聞 分析" if query else "台股 美股 今日 重點"
                                r2 = await hc.get("https://api.duckduckgo.com/",
                                    params={"q": q, "format": "json", "no_html": "1", "skip_disambig": "1"})
                                d2 = r2.json()
                                abstract = d2.get("AbstractText", "")[:400]
                                topics = [t.get("Text","")[:150] for t in d2.get("RelatedTopics",[])
                                          if isinstance(t, dict) and t.get("Text")][:4]
                                parts = []
                                if abstract:
                                    parts.append(abstract)
                                if topics:
                                    parts.append("相關討論：\n" + "\n".join(f"• {t}" for t in topics))
                                res = "\n\n".join(parts) if parts else f"暫時無法取得「{query}」的即時資訊，建議查看 Yahoo 股市或鉅亨網。"
                    except Exception as e:
                        res = f"市場資訊暫時無法取得：{e}"

                elif b.name == "analyze_photo":
                    # Photo analysis is handled via /api/analyze-photo endpoint
                    # This tool result is a placeholder; real analysis done in the endpoint
                    res = "請直接上傳照片，阿福會幫您分析。"

                elif b.name == "check_email":
                    if not gmail_service or not GCAL_CONFIGURED:
                        res = "Gmail 未授權，請先完成 Google 授權（需包含 Gmail 權限）"
                    else:
                        query = inp.get("query", "is:unread")
                        msgs = gmail_service.list_messages(db, max_results=8, query=query)
                        if not msgs:
                            res = "沒有符合條件的郵件"
                        else:
                            lines = [f"共 {len(msgs)} 封："]
                            for m in msgs:
                                lines.append(f"• 【{m['subject']}】來自 {m['from'][:40]}\n  {m['snippet'][:100]}")
                            res = "\n".join(lines)
                elif b.name == "send_email":
                    if not gmail_service or not GCAL_CONFIGURED:
                        res = "Gmail 未授權"
                    else:
                        ok = gmail_service.send_email(db, inp["to"], inp["subject"], inp["body"])
                        if ok:
                            action = {"type": "email_sent", "to": inp["to"], "subject": inp["subject"]}
                            res = f"信件已發送給 {inp['to']}"
                        else:
                            res = "發送失敗，請確認 Gmail 授權包含 gmail.send 權限"
                elif b.name == "send_line_message":
                    msg_text = inp.get("message", "")
                    target_id = inp.get("user_id", "")
                    if not LINE_CONFIGURED or not line_service:
                        res = "LINE 未設定"
                    elif not msg_text:
                        res = "訊息內容不能為空"
                    else:
                        # Use stored owner user_id if not specified
                        if not target_id:
                            c2 = db()
                            row2 = c2.execute(
                                "SELECT value FROM memories WHERE category='line' AND key='owner_user_id' ORDER BY ts DESC LIMIT 1"
                            ).fetchone()
                            c2.close()
                            target_id = row2[0] if row2 else ""
                        if not target_id:
                            res = "尚未取得主人的 LINE ID，請先透過 LINE 傳一則訊息給阿福建立連線"
                        else:
                            ok = line_service.push_message(target_id, msg_text)
                            res = f"LINE 訊息已發送" if ok else "LINE 訊息發送失敗"

                elif b.name == "search_news":
                    query = inp.get("query", "")
                    lang = inp.get("lang", "zh-TW")
                    if not search_service:
                        res = "新聞搜尋服務暫時不可用"
                    elif not query:
                        res = "請提供搜尋關鍵字"
                    else:
                        articles = search_service.search_news(query, lang=lang, max_results=5)
                        if not articles:
                            res = f"暫時無法取得「{query}」的新聞，請稍後再試"
                        else:
                            lines = [f"【{query}】最新新聞："]
                            for i, a in enumerate(articles, 1):
                                src = f"（{a['source']}）" if a.get("source") else ""
                                lines.append(f"{i}. {a['title']}{src}")
                            res = "\n".join(lines)

                elif b.name == "find_podcast":
                    query = inp.get("query", "")
                    mode = inp.get("mode", "episodes")
                    if not search_service:
                        res = "Podcast 搜尋服務暫時不可用"
                    else:
                        if mode == "shows":
                            shows = search_service.search_podcast_shows(query, max_results=3)
                            if not shows:
                                res = f"找不到「{query}」的 Podcast 節目"
                            else:
                                # Get latest episode from first show
                                show = shows[0]
                                feed_url = show.get("feed_url", "")
                                ep = search_service.get_latest_podcast_episode(feed_url) if feed_url else None
                                if ep and ep.get("audio_url"):
                                    action = {"type": "play_audio", "url": ep["audio_url"],
                                              "title": ep["title"], "show": show["name"],
                                              "artwork": show.get("artwork", "")}
                                    res = f"找到節目「{show['name']}」，最新一集：{ep['title']}"
                                else:
                                    info = [f"節目：{s['name']}（{s['artist']}）" for s in shows[:2]]
                                    res = "找到以下節目：\n" + "\n".join(info) + "\n\n可在 Apple Podcasts 收聽：" + shows[0].get("apple_url","")
                        else:
                            episodes = search_service.search_podcast_episodes(query, max_results=3)
                            if not episodes:
                                res = f"找不到「{query}」的 Podcast 單集，建議換個關鍵字試試"
                            else:
                                ep = episodes[0]
                                if ep.get("audio_url"):
                                    action = {"type": "play_audio", "url": ep["audio_url"],
                                              "title": ep["title"], "show": ep["show"],
                                              "artwork": ep.get("artwork", "")}
                                    dur = ep.get("duration_sec", 0)
                                    dur_str = f"（{dur//60}分鐘）" if dur else ""
                                    res = f"找到「{ep['show']}」的單集：{ep['title']}{dur_str}"
                                else:
                                    res = f"找到「{ep['show']}」但無法直接播放，請前往 Apple Podcasts 收聽"

                elif b.name == "play_music":
                    query = inp.get("query", "")
                    platform = inp.get("platform", "youtube")
                    if query == "recent" or platform == "recent":
                        # Check music history from DB
                        c2 = db()
                        rows2 = c2.execute(
                            "SELECT value, COUNT(*) as cnt FROM memories WHERE category='music_history' GROUP BY value ORDER BY cnt DESC LIMIT 5"
                        ).fetchall()
                        c2.close()
                        if rows2:
                            top = rows2[0][0]
                            history = [r[0] for r in rows2]
                            yt_url = search_service.youtube_search_url(top) if search_service else ""
                            action = {"type": "open_url", "url": yt_url, "title": f"播放：{top}"}
                            res = f"您最常聽的是「{top}」。為您在 YouTube 搜尋中。\n最近還播過：{', '.join(history[1:4])}"
                        else:
                            res = "還沒有播放紀錄。請告訴我您想聽什麼歌手或歌曲？"
                    else:
                        # Record this music request
                        c2 = db()
                        c2.execute(
                            "INSERT INTO memories (category,key,value,ts) VALUES (?,?,?,?)",
                            ("music_history", "play", query, datetime.now().isoformat())
                        )
                        c2.commit(); c2.close()
                        if platform == "spotify":
                            url = search_service.spotify_search_url(query) if search_service else f"https://open.spotify.com/search/{query}"
                            action = {"type": "open_url", "url": url, "title": f"Spotify：{query}"}
                            res = f"為您在 Spotify 搜尋「{query}」"
                        else:
                            url = search_service.youtube_search_url(query) if search_service else f"https://www.youtube.com/results?search_query={query}"
                            action = {"type": "open_url", "url": url, "title": f"YouTube：{query}"}
                            res = f"為您在 YouTube 搜尋「{query}」"
                elif b.name == "speak_for_me":
                    text_to_translate = inp.get("text","").strip()
                    tgt = inp.get("target_lang","en")
                    direction = inp.get("direction","to_foreign")
                    lang_name = _LANG_NAMES.get(tgt, tgt)

                    if direction == "to_foreign":
                        # 翻譯成外語，前端接到 action 後播放 TTS
                        prompt = (
                            f"請將以下中文翻譯成自然口語的{lang_name}，"
                            f"語氣要像真人在說話，適合在餐廳/計程車/商店等場合使用。"
                            f"只輸出翻譯結果，不加任何說明。\n\n{text_to_translate}"
                        )
                        translated = _simple_chat(prompt, max_tokens=300)
                        action = {
                            "type": "speak_translation",
                            "original": text_to_translate,
                            "translated": translated.strip(),
                            "lang": tgt,
                            "lang_name": lang_name,
                            "direction": "to_foreign"
                        }
                        res = (
                            f"已翻譯成{lang_name}：「{translated.strip()}」\n"
                            f"阿福會直接念出來給對方聽。\n"
                            f"如果對方有回應，對著手機說「阿福，他說什麼」我幫您翻回中文。"
                        )
                    else:
                        # 把外語翻回中文給主人聽
                        prompt = (
                            f"請將以下{lang_name}翻譯成自然口語的繁體中文。"
                            f"只輸出翻譯結果，不加任何說明。\n\n{text_to_translate}"
                        )
                        translated = _simple_chat(prompt, max_tokens=300)
                        action = {
                            "type": "speak_translation",
                            "original": text_to_translate,
                            "translated": translated.strip(),
                            "lang": "zh-TW",
                            "lang_name": "中文",
                            "direction": "to_chinese"
                        }
                        res = f"對方說的是：「{translated.strip()}」"

                elif b.name == "people_prefs":
                    pa = inp.get("action","query")
                    person = (inp.get("person") or "").strip()

                    if pa == "add":
                        c.execute(
                            "INSERT INTO people_prefs (person,relation,category,content,importance,noted_at) "
                            "VALUES (?,?,?,?,?,?)",
                            (person, inp.get("relation","colleague"),
                             inp.get("category","other"), inp.get("content",""),
                             inp.get("importance","normal"), datetime.now().isoformat())
                        )
                        cat_label = {"food":"飲食","drink":"飲料","gift":"送禮方向",
                                     "taboo":"禁忌","habit":"習慣","anniversary":"重要日期"}.get(
                            inp.get("category","other"), "偏好")
                        imp_tag = "【重要】" if inp.get("importance")=="high" else ""
                        res = f"已記錄：{person} 的{cat_label}{imp_tag}——{inp.get('content','')}。下次送禮或安排時我會提醒您。"

                    elif pa == "query":
                        rows = c.execute(
                            "SELECT category, content, importance FROM people_prefs "
                            "WHERE person LIKE ? ORDER BY importance DESC, noted_at DESC",
                            (f"%{person}%",)
                        ).fetchall()
                        if not rows:
                            res = f"阿福還沒有 {person} 的偏好記錄。您知道什麼可以告訴我，下次我就記住了。"
                        else:
                            cat_map = {"food":"飲食","drink":"飲料","gift":"送禮方向",
                                       "taboo":"❌禁忌","habit":"習慣","anniversary":"重要日期","other":"其他"}
                            lines = [f"📋 {person} 的個人偏好：\n"]
                            for cat, content, imp in rows:
                                tag = "🔴 " if imp == "high" else "• "
                                label = cat_map.get(cat, cat)
                                lines.append(f"{tag}[{label}] {content}")
                            # 查禁忌先說
                            has_taboo = any(r[0]=="taboo" for r in rows)
                            if has_taboo:
                                lines.append("\n⚠️ 注意：有禁忌項目，安排時請避開。")
                            res = "\n".join(lines)

                    elif pa == "list":
                        rows = c.execute(
                            "SELECT DISTINCT person, relation FROM people_prefs ORDER BY person"
                        ).fetchall()
                        if not rows:
                            res = "目前沒有任何人的偏好記錄。主人可以告訴我同事或主管的喜好，我幫您記著。"
                        else:
                            lines = ["已記錄偏好的人員："]
                            for person_name, relation in rows:
                                count = c.execute(
                                    "SELECT COUNT(*) FROM people_prefs WHERE person=?", (person_name,)
                                ).fetchone()[0]
                                lines.append(f"• {person_name}（{relation}）— {count} 筆記錄")
                            res = "\n".join(lines)
                    c.commit()

                elif b.name == "attendance":
                    import datetime as _dt
                    aa = inp.get("action","today")
                    target_date = inp.get("date") or _dt.date.today().isoformat()
                    now_iso = datetime.now().isoformat()

                    if aa == "checkin":
                        existing = c.execute("SELECT id,check_in FROM attendance WHERE date=?", (target_date,)).fetchone()
                        if existing and existing[1]:
                            res = f"您在 {target_date} 已記錄上班時間 {existing[1][11:16]}，不重複打卡。"
                        else:
                            cur_loc = c.execute("SELECT lat,lng,ts FROM location_log ORDER BY id DESC LIMIT 1").fetchone()
                            lat = cur_loc[0] if cur_loc else None
                            lng = cur_loc[1] if cur_loc else None
                            if existing:
                                c.execute("UPDATE attendance SET check_in=?,lat_in=?,lng_in=? WHERE id=?",
                                          (now_iso, lat, lng, existing[0]))
                            else:
                                c.execute("INSERT INTO attendance (date,check_in,lat_in,lng_in,type,verified) VALUES (?,?,?,?,?,?)",
                                          (target_date, now_iso, lat, lng, "office", 1))
                            res = f"上班打卡完成：{target_date} {now_iso[11:16]}，GPS 座標已記錄為佐證。"

                    elif aa == "checkout":
                        row = c.execute("SELECT id,check_in FROM attendance WHERE date=?", (target_date,)).fetchone()
                        cur_loc = c.execute("SELECT lat,lng FROM location_log ORDER BY id DESC LIMIT 1").fetchone()
                        lat = cur_loc[0] if cur_loc else None
                        lng = cur_loc[1] if cur_loc else None
                        dur = None
                        if row and row[1]:
                            try:
                                ci = _dt.datetime.fromisoformat(row[1])
                                dur = int((_dt.datetime.fromisoformat(now_iso) - ci).total_seconds() / 60)
                            except Exception:
                                pass
                        if row:
                            c.execute("UPDATE attendance SET check_out=?,lat_out=?,lng_out=?,duration_min=? WHERE id=?",
                                      (now_iso, lat, lng, dur, row[0]))
                        else:
                            c.execute("INSERT INTO attendance (date,check_in,check_out,lat_out,lng_out,type,duration_min,verified) VALUES (?,?,?,?,?,?,?,?)",
                                      (target_date, None, now_iso, lat, lng, "office", dur, 1))
                        dur_str = f"，在公司共 {dur//60} 小時 {dur%60} 分鐘" if dur else ""
                        res = f"下班打卡完成：{target_date} {now_iso[11:16]}{dur_str}。記錄已存檔。"

                    elif aa == "wfh":
                        notes = inp.get("notes","居家辦公")
                        existing = c.execute("SELECT id FROM attendance WHERE date=?", (target_date,)).fetchone()
                        if existing:
                            c.execute("UPDATE attendance SET type='wfh',notes=? WHERE id=?", (notes, existing[0]))
                        else:
                            c.execute("INSERT INTO attendance (date,check_in,type,notes,verified) VALUES (?,?,?,?,?)",
                                      (target_date, now_iso, "wfh", notes, 1))
                        res = f"已記錄 {target_date} 居家辦公（{notes}），時間 {now_iso[11:16]}。"

                    elif aa == "leave":
                        notes = inp.get("notes","請假")
                        existing = c.execute("SELECT id FROM attendance WHERE date=?", (target_date,)).fetchone()
                        if existing:
                            c.execute("UPDATE attendance SET type='leave',notes=?,check_in=NULL WHERE id=?", (notes, existing[0]))
                        else:
                            c.execute("INSERT INTO attendance (date,type,notes,verified) VALUES (?,?,?,?)",
                                      (target_date, "leave", notes, 1))
                        res = f"已記錄 {target_date} 請假（{notes}）。"

                    elif aa == "today":
                        row = c.execute(
                            "SELECT check_in,check_out,type,duration_min,notes FROM attendance WHERE date=?",
                            (target_date,)
                        ).fetchone()
                        if not row:
                            res = f"今天（{target_date}）還沒有打卡記錄。"
                        else:
                            ci = row[0][11:16] if row[0] else "未記錄"
                            co = row[1][11:16] if row[1] else "尚未離開"
                            tp = {"office":"進公司","wfh":"居家辦公","leave":"請假"}.get(row[2], row[2])
                            dur = f"，共 {row[3]//60}h{row[3]%60}m" if row[3] else ""
                            notes_str = f"（{row[4]}）" if row[4] else ""
                            res = f"{target_date} {tp}{notes_str}：上班 {ci} / 下班 {co}{dur}。GPS 已驗證。"

                    elif aa == "report":
                        month = inp.get("month") or _dt.date.today().strftime("%Y-%m")
                        rows = c.execute(
                            "SELECT date,check_in,check_out,type,duration_min,notes,lat_in,lng_in "
                            "FROM attendance WHERE date LIKE ? ORDER BY date ASC",
                            (f"{month}%",)
                        ).fetchall()
                        if not rows:
                            res = f"{month} 沒有出勤記錄。"
                        else:
                            office_days = sum(1 for r in rows if r[3]=="office" and r[1])
                            wfh_days   = sum(1 for r in rows if r[3]=="wfh")
                            leave_days = sum(1 for r in rows if r[3]=="leave")
                            total_min  = sum(r[4] or 0 for r in rows)
                            lines = [f"📋 {month} 出勤報告（共 {len(rows)} 個工作日記錄）\n"]
                            lines.append(f"進公司：{office_days} 天 ｜ 居家辦公：{wfh_days} 天 ｜ 請假：{leave_days} 天")
                            lines.append(f"實際在公司總時數：約 {total_min//60} 小時\n")
                            lines.append("日期詳細：")
                            for r in rows:
                                date_str = r[0]
                                tp_tag = {"office":"✅ 進公司","wfh":"🏠 居家","leave":"🏖 請假"}.get(r[3],"？")
                                ci = r[1][11:16] if r[1] else "—"
                                co = r[2][11:16] if r[2] else "—"
                                dur = f"{r[4]//60}h{r[4]%60}m" if r[4] else "—"
                                gps = "📍" if r[6] else ""
                                note = f" ({r[5]})" if r[5] else ""
                                lines.append(f"{date_str} {tp_tag} {ci}→{co} {dur} {gps}{note}")
                            lines.append("\n⚠️ 每筆含 GPS 座標（📍）記錄均可作為出勤佐證資料。如人資有疑問，請告知阿福，我可以匯出詳細清單。")
                            res = "\n".join(lines)
                            card = {"title": f"{month} 出勤報告", "content": res, "type": "document"}
                            res = f"{month} 出勤報告已整理完成，卡片已顯示。"

                    c.commit()

                elif b.name == "pet_care":
                    pa = inp.get("action")
                    pname = (inp.get("pet_name") or "").strip()
                    if pa == "add_pet":
                        c.execute(
                            "INSERT INTO pets (name,species,breed,food_brand,daily_food_g,"
                            "next_vet_date,notes,noted_at) VALUES (?,?,?,?,?,?,?,?)",
                            (pname, inp.get("species","cat"), inp.get("breed",""),
                             inp.get("food_brand",""), inp.get("daily_food_g",80),
                             inp.get("next_vet_date",""), inp.get("notes",""),
                             datetime.now().isoformat())
                        )
                        res = f"已幫您記下{pname}的資料。之後提到牠的食物、耗材、回診，我都會記著。"
                    elif pa == "update_pet":
                        row = c.execute("SELECT id FROM pets WHERE name LIKE ? LIMIT 1",
                                        (f"%{pname}%",)).fetchone()
                        if row:
                            for col, key in [("food_brand","food_brand"),("daily_food_g","daily_food_g"),
                                             ("next_vet_date","next_vet_date"),("notes","notes"),
                                             ("breed","breed"),("species","species")]:
                                if key in inp and inp[key] is not None:
                                    c.execute(f"UPDATE pets SET {col}=? WHERE id=?", (inp[key], row[0]))
                            res = f"{pname}的資料已更新。"
                        else:
                            res = f"找不到「{pname}」，要幫您建立嗎？"
                    elif pa == "log_supply":
                        pet_row = c.execute("SELECT id FROM pets WHERE name LIKE ? LIMIT 1",
                                            (f"%{pname}%",)).fetchone() if pname else None
                        pid = pet_row[0] if pet_row else None
                        item = inp.get("item","")
                        est = inp.get("est_days_total", 45)
                        c.execute(
                            "INSERT INTO pet_supplies (pet_id,item,brand,size_desc,last_bought,"
                            "est_days_total,price_paid,notes) VALUES (?,?,?,?,?,?,?,?)",
                            (pid, item, inp.get("brand",""), inp.get("size_desc",""),
                             datetime.now().strftime("%Y-%m-%d"), est,
                             inp.get("price_paid"), inp.get("notes",""))
                        )
                        remind_date = (datetime.now() + __import__("datetime").timedelta(days=int(est*0.85))).strftime("%Y-%m-%d")
                        res = f"已記錄「{item}」今日購入，預計 {est} 天用完。我會在 {remind_date} 前提醒您補貨。"
                    elif pa == "check_supplies":
                        import datetime as _dt
                        today = _dt.date.today()
                        rows = c.execute(
                            "SELECT ps.item, ps.last_bought, ps.est_days_total, p.name "
                            "FROM pet_supplies ps LEFT JOIN pets p ON ps.pet_id=p.id "
                            "ORDER BY ps.last_bought DESC"
                        ).fetchall()
                        lines = []
                        for item, last_bought, est, pet in rows:
                            if last_bought:
                                bought = _dt.date.fromisoformat(last_bought)
                                used = (today - bought).days
                                remain = max(0, est - used)
                                if remain <= 10:
                                    lines.append(f"• 【快沒了】{item}（{pet or '通用'}）還剩約 {remain} 天")
                                elif remain <= 21:
                                    lines.append(f"• 【該補了】{item}（{pet or '通用'}）還剩約 {remain} 天")
                        res = "\n".join(lines) if lines else "目前所有耗材都還夠用，不用補貨。"
                    elif pa == "get_pet":
                        row = c.execute(
                            "SELECT name,species,breed,food_brand,daily_food_g,next_vet_date,notes "
                            "FROM pets WHERE name LIKE ? LIMIT 1", (f"%{pname}%",)
                        ).fetchone()
                        if row:
                            supplies = c.execute(
                                "SELECT item,last_bought,est_days_total FROM pet_supplies "
                                "WHERE pet_id=(SELECT id FROM pets WHERE name LIKE ? LIMIT 1) "
                                "ORDER BY last_bought DESC LIMIT 5", (f"%{pname}%",)
                            ).fetchall()
                            sup_str = "、".join(f"{s[0]}（{s[2]}天份）" for s in supplies) or "尚無記錄"
                            res = (f"{row[0]}｜{row[1]} {row[2] or ''}｜"
                                   f"飼料：{row[3] or '未記錄'}，每日 {row[4]}g｜"
                                   f"回診：{row[5] or '未記錄'}｜耗材：{sup_str}")
                        else:
                            res = f"找不到「{pname}」的資料。"
                    else:
                        res = "請指定 action。"

                elif b.name == "note_promise":
                    pa = inp.get("action","list")
                    if pa == "add":
                        c.execute(
                            "INSERT INTO promises (to_whom,content,deadline,context,noted_at) VALUES (?,?,?,?,?)",
                            (inp.get("to_whom",""), inp.get("content",""),
                             inp.get("deadline",""), inp.get("context",""),
                             datetime.now().isoformat())
                        )
                        pid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
                        # 同時建一個 follow_up todo
                        c.execute("INSERT INTO todos (title,due_date,status,follow_up,ts) VALUES (?,?,?,?,?)",
                                  (f"[承諾] 對{inp.get('to_whom','')}：{inp.get('content','')}",
                                   inp.get("deadline",""), "pending", 1, datetime.now().isoformat()))
                        res = f"承諾已記下（#{pid}）：對{inp.get('to_whom','')}——{inp.get('content','')}。我會追蹤這件事。"
                    elif pa == "done":
                        pid2 = inp.get("promise_id")
                        if pid2:
                            c.execute("UPDATE promises SET status='done' WHERE id=?", (pid2,))
                            res = f"承諾 #{pid2} 已標記完成。"
                        else:
                            res = "請提供承諾編號。"
                    elif pa == "list":
                        rows = c.execute(
                            "SELECT id,to_whom,content,deadline,noted_at FROM promises "
                            "WHERE status='pending' ORDER BY noted_at DESC LIMIT 8"
                        ).fetchall()
                        if not rows:
                            res = "目前沒有未完成的承諾，主人說話算數。"
                        else:
                            lines = [f"待兌現的承諾（共{len(rows)}筆）："]
                            for r in rows:
                                dl = f"，{r[3]}" if r[3] else ""
                                lines.append(f"• #{r[0]} 對{r[1]}：{r[2]}{dl}")
                            res = "\n".join(lines)

                elif b.name == "search_meeting_notes":
                    query = inp.get("query","")
                    limit = int(inp.get("limit", 5))
                    kw = f"%{query}%"
                    rows = c.execute(
                        "SELECT id,title,summary,ts FROM meeting_notes "
                        "WHERE title LIKE ? OR summary LIKE ? OR transcript LIKE ? "
                        "ORDER BY ts DESC LIMIT ?",
                        (kw, kw, kw, limit)
                    ).fetchall()
                    if not rows:
                        res = f"找不到與「{query}」相關的會議記錄。"
                    else:
                        parts = [f"找到 {len(rows)} 筆相關記錄："]
                        for r in rows:
                            ts = r[3][:10] if r[3] else ""
                            summary_short = (r[2] or "")[:120].replace("\n", " ")
                            parts.append(f"\n【{ts}】{r[1]}\n{summary_short}…")
                        res = "\n".join(parts)

                elif b.name == "manage_anniversary":
                    pa = inp.get("action","list")
                    if pa == "add":
                        yr = inp.get("year")
                        c.execute(
                            "INSERT INTO anniversaries (person,relation,event_type,month,day,year,notes) "
                            "VALUES (?,?,?,?,?,?,?)",
                            (inp.get("person",""), inp.get("relation",""),
                             inp.get("event_type","birthday"),
                             inp.get("month"), inp.get("day"), yr,
                             inp.get("notes",""))
                        )
                        # 計算今年是第幾週年
                        yr_hint = ""
                        if yr:
                            elapsed = datetime.now().year - int(yr)
                            milestones = {10:"十週年",20:"二十週年",25:"銀婚",
                                         30:"三十週年",50:"金婚",60:"鑽石婚"}
                            yr_hint = f"（今年第{elapsed}年" + (f"，{milestones[elapsed]}！" if elapsed in milestones else "）")
                        res = (f"已記下{inp.get('person','')}（{inp.get('relation','')}）"
                               f"的{inp.get('event_type','生日')}：{inp.get('month')}月{inp.get('day')}日{yr_hint}。"
                               f"我會在三天前提醒您。")
                    elif pa == "list":
                        import datetime as _dt
                        today = _dt.date.today()
                        rows = c.execute("SELECT person,relation,event_type,month,day,year,notes FROM anniversaries").fetchall()
                        upcoming = []
                        for person, rel, etype, month, day, year, notes in rows:
                            if not month or not day:
                                continue
                            try:
                                candidate = _dt.date(today.year, int(month), int(day))
                                if candidate < today:
                                    candidate = _dt.date(today.year+1, int(month), int(day))
                                days_away = (candidate - today).days
                                upcoming.append((days_away, person, rel, etype, month, day, year, notes))
                            except Exception:
                                pass
                        upcoming.sort()
                        if not upcoming:
                            res = "還沒有記錄任何紀念日。"
                        else:
                            lines = ["即將到來的紀念日："]
                            for days, person, rel, etype, month, day, year, notes in upcoming[:8]:
                                hint = f"（{notes}）" if notes else ""
                                when = "今天" if days == 0 else f"{days} 天後"
                                yr_tag = ""
                                if year:
                                    import datetime as _dt2
                                    elapsed = _dt2.date.today().year - int(year)
                                    ms = {10:"十週年",20:"二十週年",25:"銀婚",50:"金婚",60:"鑽石婚"}
                                    yr_tag = f" 第{elapsed}年" + (f"（{ms[elapsed]}）" if elapsed in ms else "")
                                lines.append(f"• {when}｜{person}（{rel}）{etype}{yr_tag}｜{month}/{day} {hint}")
                            res = "\n".join(lines)

                elif b.name == "acknowledge_alert":
                    aid = inp.get("alert_id")
                    if aid:
                        c.execute("UPDATE family_alerts SET acknowledged_at=? WHERE id=?",
                                  (datetime.now().isoformat(), aid))
                        res = f"警報 #{aid} 已確認。"
                    else:
                        # 確認所有未讀警報
                        c.execute("UPDATE family_alerts SET acknowledged_at=? WHERE acknowledged_at IS NULL",
                                  (datetime.now().isoformat(),))
                        res = "所有警報已確認。"
                elif b.name == "family_plan":
                    mname = inp.get("member_name", "")
                    dest = inp.get("destination", "")
                    eta = inp.get("eta", "")
                    row = c.execute(
                        "SELECT id FROM family_members WHERE name LIKE ? LIMIT 1", (f"%{mname}%",)
                    ).fetchone()
                    if row:
                        c.execute(
                            "UPDATE family_members SET planned_destination=?, planned_eta=? WHERE id=?",
                            (dest, eta, row[0])
                        )
                        res = f"已記下 {mname} 說要去「{dest}」{('，預計' + eta + '回來') if eta else ''}。如果 GPS 位置與申報不符，阿福會立刻通知您。"
                    else:
                        res = f"找不到「{mname}」在家庭成員名單中。"
                elif b.name == "family_location":
                    fl_action = inp.get("action", "all")
                    c2 = db()
                    if fl_action == "all":
                        rows = c2.execute(
                            "SELECT name,relation,last_address,last_seen,is_home,battery FROM family_members ORDER BY id"
                        ).fetchall()
                        if not rows:
                            res = "目前還沒有加入任何家庭成員。主人可以說「新增太太」或「邀請兒子」來開始設定。"
                        else:
                            lines = ["目前家人位置："]
                            for r in rows:
                                seen = r[3][11:16] if r[3] else "未知"
                                home_tag = "（在家 🏠）" if r[4] else ""
                                bat = f" 電量{r[5]}%" if r[5] and r[5] >= 0 else ""
                                lines.append(f"• {r[0]}（{r[1]}）{home_tag}：{r[2] or '位置未知'} [{seen}]{bat}")
                            res = "\n".join(lines)
                    elif fl_action == "where_is":
                        name = inp.get("name", "")
                        row = c2.execute(
                            "SELECT name,relation,last_address,last_seen,is_home,battery,last_lat,last_lng,planned_destination,planned_eta "
                            "FROM family_members WHERE name LIKE ? ORDER BY id LIMIT 1",
                            (f"%{name}%",)
                        ).fetchone()
                        if not row:
                            res = f"找不到「{name}」，主人確認一下名字？"
                        else:
                            mname, relation, addr, last_seen, is_home, battery, lat, lng, planned, eta = row
                            now_dt = datetime.now()
                            hour = now_dt.hour

                            # ── 去暗偵測 ──────────────────────────────────────────
                            gone_dark = False
                            gone_mins = 0
                            if last_seen:
                                try:
                                    import datetime as _dt
                                    last_dt = _dt.datetime.fromisoformat(last_seen)
                                    gone_mins = (now_dt - last_dt).total_seconds() / 60
                                    gone_dark = gone_mins > 10
                                except Exception:
                                    gone_dark = True

                            if gone_dark or not lat:
                                gone_str = f"{int(gone_mins)} 分鐘" if gone_mins > 0 else "一段時間"
                                last_hint = f"最後已知位置：{addr}（{last_seen[11:16] if last_seen else '未知'}）。" if addr else ""
                                plan_hint = f"她說要去「{planned}」。" if planned else ""
                                res = (
                                    f"主人，阿福目前不確定{mname}的位置了。"
                                    f"{mname}已有 {gone_str} 沒有傳回位置訊號。"
                                    f"\n{last_hint}{plan_hint}"
                                    f"\n是否需要由您提醒{mname}重新開啟阿福？"
                                    f"這樣我就可以繼續幫您確認{mname}的位置，保護她的安全。"
                                    f"\n或是，需要我幫您撥給她？"
                                )
                            else:
                                # ── 取近期軌跡判斷移動狀態 ────────────────────────
                                recent_pts = c2.execute(
                                    "SELECT lat,lng,ts FROM family_location_log "
                                    "WHERE member_id=(SELECT id FROM family_members WHERE name LIKE ? LIMIT 1) "
                                    "ORDER BY ts DESC LIMIT 10",
                                    (f"%{name}%",)
                                ).fetchall()

                                # 計算定點停留時間
                                stationary_mins = 0
                                if len(recent_pts) >= 2:
                                    try:
                                        first_ts = _dt.datetime.fromisoformat(recent_pts[-1][2])
                                        last_ts = _dt.datetime.fromisoformat(recent_pts[0][2])
                                        # 最舊與最新點距離
                                        spread = _haversine(recent_pts[-1][0], recent_pts[-1][1],
                                                            recent_pts[0][0], recent_pts[0][1])
                                        if spread < 200:  # 200m 內視為定點
                                            stationary_mins = (last_ts - first_ts).total_seconds() / 60
                                    except Exception:
                                        pass

                                # 位置與申報計畫的距離
                                plan_deviation_m = None
                                if planned and lat:
                                    # 簡單推算：若申報地點含已知地名，嘗試比對 known_places
                                    kp = c2.execute(
                                        "SELECT lat,lng,name FROM known_places WHERE name LIKE ? LIMIT 1",
                                        (f"%{planned}%",)
                                    ).fetchone()
                                    if kp:
                                        plan_deviation_m = _haversine(lat, lng, kp[0], kp[1])

                                # ── 偵探推理 prompt ────────────────────────────────
                                bat_str = f"電量 {battery}%" if battery and battery >= 0 else "電量不明"
                                stationary_str = f"已在該地點定點停留約 {int(stationary_mins)} 分鐘" if stationary_mins > 5 else "位置持續變動中（可能還在移動）"
                                deviation_str = ""
                                if plan_deviation_m is not None:
                                    if plan_deviation_m > 500:
                                        deviation_str = f"距離申報的「{planned}」約 {plan_deviation_m:.0f} 公尺，明顯不在申報地點。"
                                    else:
                                        deviation_str = f"位置與申報的「{planned}」吻合（距離 {plan_deviation_m:.0f} 公尺）。"

                                # 危險場所關鍵字偵測（地址比對）
                                danger_keywords = [
                                    "pub", "bar", "club", "disco", "ktv", "卡拉ok", "夜店",
                                    "酒吧", "賭場", "casino", "汽車旅館", "汽旅", "motel",
                                    "檳榔", "成人", "色情", "賓館", "旅館"
                                ]
                                addr_lower_chk = (addr or "").lower()
                                danger_detected = any(kw in addr_lower_chk for kw in danger_keywords)

                                # 學校上課時間但不在學校附近 → 異常
                                school_hour = (8 <= hour < 17) and relation in ["兒子", "女兒", "孩子", "小孩"]

                                danger_note = ""
                                if danger_detected:
                                    danger_note = f"\n注意：地址可能含有夜生活或成人場所，請在推理時輕描淡寫地提到，建議主人以輕鬆方式確認，切勿驚慌語氣。"

                                detective_prompt = f"""你是阿福，一位老練的私人管家兼情報分析師。
主人詢問他{relation}「{mname}」目前的狀況。

【現有情報】
- 目前 GPS：{addr}（{lat:.4f}, {lng:.4f}）
- 最後更新：{last_seen[11:16] if last_seen else '未知'}（{int(gone_mins)} 分鐘前）
- 移動狀態：{stationary_str}
- 手機：{bat_str}
- 申報計畫：{('說要去「' + planned + '」' + ('，預計' + eta + '回') if eta else '') if planned else '未申報'}
- 位置比對：{deviation_str or '無法比對'}
- 現在時間：{now_dt.strftime('%H:%M')}，{'白天' if 8 <= hour < 18 else '傍晚' if 18 <= hour < 21 else '夜間'}
- 危險場所偵測：{'⚠️ 地址可能含有不適合場所' if danger_detected else '未偵測到危險場所'}
- 學校時段異常：{'是，現在是上課時間但不在學校附近' if school_hour else '否'}

【你的任務】
從這些碎片資訊推理，給主人一個有用的情報判斷，不是地圖。

推理依據：
1. 地址的街區性質（住宅/學區/商業/娛樂/公園/夜生活區）
2. 定點停留時間 → 「在某室內場所」vs「路過」
3. {relation}這個年齡層，這個時段，這個地方通常在做什麼
4. 是否在危險或不適合場所附近（pub/夜店/汽旅等）
5. 申報計畫 vs 實際位置的偏差意義

【回覆語氣原則 — 最重要】
阿福永遠沉穩，絕不製造恐慌。見過更大的事。

- 如有不尋常地點 → 輕描淡寫，「那一帶比較特別」，建議主人「輕鬆問一句就好」
- 如上課時間不在學校 → 說「有點不太一樣」，不說「異常」
- 如果一切正常 → 幾個合理可能性，語氣像朋友聊天
- 最後給主人選擇，不是命令：「要我等等看？還是您想問她一下？」
- 全部不超過 100 字，像說話不像報告
- 永遠不用「危險」「緊急」「立刻」「馬上」這四個字{danger_note}"""

                                try:
                                    analysis = _simple_chat(detective_prompt, max_tokens=300)
                                except Exception:
                                    analysis = f"目前在 {addr}，{stationary_str}。"

                                res = analysis

                    elif fl_action == "arrivals":
                        rows = c2.execute(
                            "SELECT key,value,ts FROM memories WHERE category='family_arrival' ORDER BY ts DESC LIMIT 10"
                        ).fetchall()
                        if not rows:
                            res = "最近沒有家人到達的紀錄。"
                        else:
                            lines = ["最近的到達紀錄："] + [f"• {r[1]}" for r in rows]
                            res = "\n".join(lines)
                    elif fl_action == "add_member":
                        name = inp.get("name", "").strip()
                        relation = inp.get("relation", "家人")
                        if not name:
                            res = "需要提供家人名字。"
                        else:
                            existing = c2.execute("SELECT COUNT(*) FROM family_members").fetchone()[0]
                            color = _family_avatar_colors()[existing % len(_family_avatar_colors())]
                            c2.execute(
                                "INSERT INTO family_members (name,relation,avatar_color,noted_at) VALUES (?,?,?,?)",
                                (name, relation, color, datetime.now().isoformat())
                            )
                            c2.commit()
                            mid = c2.execute("SELECT last_insert_rowid()").fetchone()[0]
                            res = f"已新增「{name}（{relation}）」，編號 #{mid}。接下來幫 {name} 產生邀請連結？只要說「邀請 {name}」就可以了。"
                    elif fl_action == "invite":
                        member_id = inp.get("member_id")
                        if not member_id:
                            # 試著用 name 找
                            name = inp.get("name", "")
                            row = c2.execute(
                                "SELECT id,name FROM family_members WHERE name LIKE ? LIMIT 1",
                                (f"%{name}%",)
                            ).fetchone() if name else None
                            member_id = row[0] if row else None
                        if not member_id:
                            res = "請指定要邀請的家人名字。"
                        else:
                            import datetime as _dt, secrets as _sec
                            row = c2.execute("SELECT name FROM family_members WHERE id=?", (member_id,)).fetchone()
                            mname = row[0] if row else "家人"
                            token = _sec.token_urlsafe(20)
                            expires = (_dt.datetime.now() + _dt.timedelta(days=7)).isoformat()
                            c2.execute("DELETE FROM family_invites WHERE member_id=?", (member_id,))
                            c2.execute(
                                "INSERT INTO family_invites (token,member_id,created_at,expires_at) VALUES (?,?,?,?)",
                                (token, member_id, datetime.now().isoformat(), expires)
                            )
                            c2.commit()
                            invite_url = f"/alfred/join?t={token}"
                            action = {"type": "show_qr", "url": invite_url,
                                      "title": f"邀請 {mname} 加入家庭位置共享",
                                      "token": token}
                            res = (f"已為「{mname}」產生邀請連結（7 天有效）。\n"
                                   f"請讓 {mname} 掃描 QR code 或開啟連結：{invite_url}\n"
                                   f"對方安裝阿福 App 並點連結後，位置就會自動同步。")
                    c2.commit(); c2.close()

                elif b.name == "ambient_mode":
                    amb_action = inp.get("action", "start")
                    amb_label = inp.get("label", "")
                    if amb_action == "start":
                        action = {"type": "start_ambient",
                                  "label": amb_label or f"辦公記錄 {datetime.now().strftime('%m/%d')}"}
                        res = "已向主人的裝置發出聆聽指令，請在手機上確認麥克風授權。"
                    elif amb_action == "stop":
                        action = {"type": "stop_ambient"}
                        res = "已發出停止指令，整理中。"
                    elif amb_action == "status":
                        c2 = db()
                        rows = c2.execute(
                            "SELECT id,label,status,started_at,stopped_at,"
                            "(SELECT COUNT(*) FROM ambient_chunks WHERE session_id=ambient_sessions.id) "
                            "FROM ambient_sessions ORDER BY id DESC LIMIT 5"
                        ).fetchall()
                        c2.close()
                        if not rows:
                            res = "目前還沒有任何聆聽記錄。"
                        else:
                            lines = ["最近的聆聽記錄："]
                            for r in rows:
                                status_ch = "記錄中" if r[2]=="recording" else "已結束"
                                lines.append(f"• [{r[1]}] {status_ch}，{r[5]} 段，{r[3][5:16] if r[3] else ''}")
                            res = "\n".join(lines)

                elif b.name == "help_quote":
                    qmode = inp.get("mode", "analyze_history")
                    brief = (inp.get("case_brief") or "").strip()
                    duration = (inp.get("duration") or "").strip()
                    client_name = (inp.get("client_name") or "").strip()

                    # 撈過去報價單：上傳檔案 + Mac 索引（檔名/描述含 報價/quote/quotation）
                    c2 = db()
                    past = []
                    rows = c2.execute(
                        "SELECT id, original_name, mime_type, ts FROM files "
                        "WHERE (original_name LIKE '%報價%' OR original_name LIKE '%quote%' OR original_name LIKE '%quotation%' "
                        "    OR description LIKE '%報價%' OR tags LIKE '%報價%') "
                        "AND (original_name LIKE '%.pdf' OR original_name LIKE '%.docx' OR original_name LIKE '%.txt' OR original_name LIKE '%.md') "
                        "ORDER BY ts DESC LIMIT 6"
                    ).fetchall()
                    c2.close()
                    for fid, fname, mime, ts in rows:
                        c3 = db()
                        rr = c3.execute("SELECT filename FROM files WHERE id=?", (fid,)).fetchone()
                        c3.close()
                        if rr:
                            t = _extract_text_from_file(f"{FILE_DIR}/{rr[0]}", mime or "", fname or "")
                            if t and not t.startswith("["):
                                past.append((fname, ts[:10], t[:6000]))

                    if not past:
                        res = ("阿福暫時找不到任何過去的報價單檔案。"
                               "主人方便先上傳幾份過去的報價單嗎？或告訴我您過去通常怎麼報價（例如：每月顧問費、按專案模組、人天 × 倍率），"
                               "我就能依新案幫您草擬。")
                    else:
                        joined = "\n\n".join(f"=== 第 {i+1} 份《{n}》（{d}） ===\n{txt}" for i,(n,d,txt) in enumerate(past))
                        if qmode == "analyze_history" or not brief:
                            prompt = f"""主人請你分析他公司過去的報價邏輯。閱讀以下 {len(past)} 份過去報價單，
歸納出主人公司的報價模式。輸出繁中 Markdown，欄位：

## 一、公司主要服務範圍
（從報價內容反推）

## 二、報價邏輯（最重要）
- 計價方式：人月 / 人天 / 模組固定價 / 工時×倍率？
- 慣用單價區間（新台幣）
- 是否含倍率、保證金、預算上限？
- 付款條件（簽約金、期中款、尾款比例）
- 標準附帶條件（修改次數、加價條件、延期罰則）

## 三、推測這次案子的合適報價
{('案子描述：' + brief if brief else '主人尚未提供案子細節 — 請列出三種典型案型 (小/中/大) 各自的合理報價區間，並提示主人補哪些資訊可以更精準')}
{('預期工期：' + duration if duration else '')}

最後**用主人的口吻**寫一句話：『主人，過去公司報價給客戶的方式都是…，因此這個案子大概會是…』

過去報價單：
{joined}"""
                            report = _simple_chat(prompt, max_tokens=2500)
                            card = {"title": "報價邏輯分析" + (f"｜{client_name}" if client_name else ""),
                                    "content": report, "type": "recommendation"}
                            res = (f"已分析 {len(past)} 份過去報價單。完整邏輯卡片已自動顯示給主人。"
                                   f"請**不要**再呼叫 generate_report。請以主人口吻口頭說『主人，過去公司報價給客戶的方式都是…，因此這個案子大概會是…』，"
                                   f"並{'引導主人補案子細節（內容、預期工期）以更精準報價' if not brief else '簡述要點'}。\n\n"
                                   f"報告全文供你參考：\n{report[:6000]}")
                        else:
                            # draft 模式
                            prompt = f"""主人公司過去報價單如下，請推斷其報價邏輯，然後依以下新案資訊**直接產出一份完整報價單草稿**（繁中 Markdown）。

新案：
- 客戶：{client_name or '（待補）'}
- 描述：{brief}
- 預期工期：{duration or '（待主人確認）'}

報價單需含：抬頭(我方公司／日期／報價單號)、客戶資料、服務項目明細表(項目/數量/單價/小計)、總計、稅金說明、付款條件、有效期、補充條款、簽署欄。

頂端附三句話：『主人，根據您過去的報價邏輯（XX），這份報價建議總價 NT$XXX，依據是 XXX。如要更精準請補 XXX。』

過去報價單：
{joined}"""
                            report = _simple_chat(prompt, max_tokens=3000)
                            card = {"title": f"報價單草稿｜{client_name or brief[:18]}",
                                    "content": report, "type": "document"}
                            res = (f"報價單草稿已產出，完整內容已在卡片顯示給主人。"
                                   f"請**不要**再呼叫 generate_report。請口頭告訴主人：建議總價、依據、需確認的兩三點。\n\n"
                                   f"草稿供你參考：\n{report[:6000]}")

                elif b.name == "analyze_contract":
                    mode = inp.get("mode", "request_upload")
                    hint = (inp.get("hint") or "").strip()
                    output_mode = inp.get("output", "report")

                    if mode == "request_upload":
                        action = {"type": "request_upload", "purpose": "contract",
                                  "accept": ".pdf,.docx,.txt,.md",
                                  "title": "請上傳合約檔案"}
                        res = "已為主人準備上傳介面，請選擇合約檔案。"
                    elif mode == "search_and_pick":
                        # 搜：上傳檔案、Mac 索引；用 hint 或近期會議公司
                        c2 = db()
                        candidates = []
                        kws = [hint] if hint else []
                        # 從近期 7 天行事曆抽公司關鍵字補充猜測
                        if not kws:
                            ev = c2.execute(
                                "SELECT title FROM calendar_events WHERE event_date >= date('now','-30 day') ORDER BY event_date DESC LIMIT 20"
                            ).fetchall()
                            kws = [r[0] for r in ev if r[0]][:5]

                        for kw in (kws or [""]):
                            like = f"%{kw}%" if kw else "%合約%"
                            up = c2.execute(
                                "SELECT id, original_name, ts FROM files "
                                "WHERE (original_name LIKE ? OR description LIKE ? OR tags LIKE ?) "
                                "AND (original_name LIKE '%.pdf' OR original_name LIKE '%.docx' OR original_name LIKE '%.txt') "
                                "ORDER BY ts DESC LIMIT 5",
                                (like, like, like)
                            ).fetchall()
                            for r in up:
                                candidates.append({"src":"上傳", "id":r[0], "name":r[1], "ts":r[2][:10]})
                            mac = c2.execute(
                                "SELECT name, kind, modified FROM mac_files_index "
                                "WHERE name LIKE ? AND (kind LIKE '%PDF%' OR kind LIKE '%Word%' OR name LIKE '%.docx') "
                                "ORDER BY modified DESC LIMIT 5",
                                (like,)
                            ).fetchall()
                            for r in mac:
                                candidates.append({"src":"Mac", "id":None, "name":r[0], "ts":(r[2] or "")[:10]})
                        c2.close()
                        # dedupe
                        seen = set(); uniq = []
                        for c_ in candidates:
                            k = (c_["src"], c_["name"])
                            if k in seen: continue
                            seen.add(k); uniq.append(c_)

                        if len(uniq) == 1 and uniq[0]["src"] == "上傳":
                            # 找到唯一一份上傳的合約 → 直接分析
                            target_id = uniq[0]["id"]
                            try:
                                row = c.execute("SELECT filename, original_name, mime_type FROM files WHERE id=?", (target_id,)).fetchone()
                                if row:
                                    stored, name, mime = row
                                    path = f"{FILE_DIR}/{stored}"
                                    text = _extract_text_from_file(path, mime or "", name or "")
                                    if text and not text.startswith("["):
                                        if len(text) > 80000:
                                            text = text[:80000] + "\n…[後段省略]"
                                        prompt = f"請以繁中 Markdown 報告審閱以下合約：總結/雙方/重要條款/懲罰條款/紅旗/建議。\n\n{text}"
                                        report = _simple_chat(prompt, max_tokens=2500)
                                        card = {"title": f"合約審閱：{name}", "content": report, "type": "document"}
                                        res = (f"已分析「{name}」。完整報告卡片已自動顯示給主人。"
                                               f"請**不要**再呼叫 generate_report（會覆蓋現有卡片）。"
                                               f"請以紳士口吻向主人**口頭摘要 2-3 個最關鍵的紅旗或建議**即可。\n\n"
                                               f"報告全文供你參考：\n{report[:6000]}")
                                    else:
                                        res = f"找到「{name}」但無法讀取內容：{text}"
                                else:
                                    res = "檔案資料異常"
                            except Exception as e:
                                res = f"分析失敗：{e}"
                        elif len(uniq) > 1:
                            lines = ["找到幾份可能的檔案，主人是哪一份？"]
                            for i, c_ in enumerate(uniq[:8], 1):
                                tag = f" (id={c_['id']})" if c_["id"] else " (Mac本機)"
                                lines.append(f"{i}. {c_['name']} — {c_['src']} {c_['ts']}{tag}")
                            res = "\n".join(lines)
                        else:
                            # 找不到 → 主動請主人提供關鍵字 / 或上傳
                            action = {"type": "request_upload", "purpose": "contract",
                                      "accept": ".pdf,.docx,.txt,.md",
                                      "title": "找不到符合的合約，請上傳"}
                            res = ("阿福在已有檔案中沒找到符合的合約。"
                                   + ("（搜尋字：" + ", ".join(kws[:3]) + "）" if kws else "")
                                   + " 主人記得任何關鍵字嗎？例如對方公司名、簽署日期、合約類型？或直接上傳檔案我立即審閱。")
                    elif mode == "analyze_id":
                        fid = inp.get("file_id")
                        if not fid:
                            res = "缺少 file_id"
                        else:
                            row = c.execute("SELECT filename, original_name, mime_type FROM files WHERE id=?", (fid,)).fetchone()
                            if not row:
                                res = "找不到該檔案"
                            else:
                                stored, name, mime = row
                                path = f"{FILE_DIR}/{stored}"
                                text = _extract_text_from_file(path, mime or "", name or "")
                                if not text or text.startswith("["):
                                    res = text or "讀取失敗"
                                else:
                                    if len(text) > 80000:
                                        text = text[:80000] + "\n…[後段省略]"
                                    prompt = f"請以繁中 Markdown 報告審閱以下合約：總結/雙方/重要條款/懲罰條款/紅旗/建議。\n\n{text}"
                                    report = _simple_chat(prompt, max_tokens=2500)
                                    card = {"title": f"合約審閱：{name}", "content": report, "type": "document"}
                                    res = (f"「{name}」審閱完成。完整報告卡片已自動顯示給主人。"
                                           f"請**不要**再呼叫 generate_report。請口頭向主人摘要 2-3 個關鍵紅旗或建議即可。\n\n"
                                           f"報告全文供你參考：\n{report[:6000]}")

                c.commit(); c.close()
                results.append({"tool_call_id": b.id, "name": b.name, "result": str(res)})

            # 把 assistant + tool results 加回 history（格式依 provider 不同）
            if LLM_PROVIDER == "gemini":
                # OpenAI 格式：assistant msg 帶 tool_calls，然後 tool msgs
                asst_msg = {
                    "role": "assistant",
                    "content": _text or None,
                    "tool_calls": [{"id": r["tool_call_id"], "type": "function",
                                    "function": {"name": r["name"],
                                                 "arguments": json.dumps({})}}
                                   for r in results]
                }
                current.append(asst_msg)
                for r in results:
                    current.append({"role": "tool",
                                    "tool_call_id": r["tool_call_id"],
                                    "content": r["result"]})
            else:
                # Anthropic 格式（fallback）
                current.append({"role": "assistant", "content": _raw})
                current.append({"role": "user", "content": [
                    {"type": "tool_result", "tool_use_id": r["tool_call_id"],
                     "content": r["result"]} for r in results
                ]})
        else:
            break

    return {"text": full_text, "card": card, "action": action}

@app.get("/api/greet")
async def greet():
    hour = datetime.now().hour
    if 5 <= hour < 12:
        period = "早安"
    elif 12 <= hour < 18:
        period = "午安"
    elif 18 <= hour < 23:
        period = "晚安"
    else:
        period = "夜深了"

    # 首次使用：城市未設定 → 阿福用說話方式問，不跳設定頁
    c_check = db()
    city_set = c_check.execute(
        "SELECT value FROM memories WHERE category='location' AND key='city' LIMIT 1"
    ).fetchone()
    onboarded = c_check.execute(
        "SELECT value FROM memories WHERE category='system' AND key='onboarded_at' LIMIT 1"
    ).fetchone()
    c_check.close()

    if not city_set and not onboarded:
        return {
            "text": (
                "我是您的管家，阿福，很高興能夠服務您。"
                "如果您有任何需求，可以直接跟我對話，在我能力所及的範圍內會盡力達成。"
                "如果有無法達成之處，還請您見諒，未來我會再提升自己的能力。\n\n"
                "請問您住在哪個城市呢？我會為您安排當地的天氣與日常資訊。"
            ),
            "first_time": True
        }

    city_display, city_en = get_user_city()
    weather = await fetch_weather(city_en, city_display)

    c = db()
    events_today = c.execute(
        "SELECT title,event_time FROM calendar_events WHERE event_date=date('now') ORDER BY event_time LIMIT 2"
    ).fetchall()
    todos_followup = c.execute(
        "SELECT title FROM todos WHERE status='pending' AND follow_up=1 "
        "AND title NOT LIKE '[承諾]%' ORDER BY ts DESC LIMIT 1"
    ).fetchone()
    c.close()

    # GPS-aware late night work detection
    late_night_care = ""
    if hour >= 22 or hour < 5:
        c3 = db()
        today_start = datetime.now().strftime('%Y-%m-%d') + "T00:00:00"
        visited_count = c3.execute(
            "SELECT COUNT(*) FROM place_history WHERE arrived_at > ?", (today_start,)
        ).fetchone()[0]
        loc_count = c3.execute(
            "SELECT COUNT(*) FROM location_log WHERE ts > ?", (today_start,)
        ).fetchone()[0]
        latest_place = c3.execute(
            "SELECT name FROM place_history WHERE arrived_at > ? ORDER BY arrived_at DESC LIMIT 1",
            (today_start,)
        ).fetchone()
        c3.close()
        if loc_count > 10 or visited_count > 0:
            place_hint = f"在{latest_place[0]}工作了一天，" if latest_place else "忙碌了一整天，"
            late_night_care = f"辛苦了，{place_hint}記得好好洗個澡，早點休息。"

    # ── 情境感知：判斷主人目前在哪裡 ──────────────────────────────────────────
    context_mode = "unknown"   # home / office / gym / other / unknown
    context_name = ""
    c_ctx = db()
    latest_loc = c_ctx.execute(
        "SELECT lat,lng FROM location_log ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if latest_loc:
        known = c_ctx.execute("SELECT name,place_type,lat,lng FROM known_places").fetchall()
        for kp_name, kp_type, kp_lat, kp_lng in known:
            dist = _haversine(latest_loc[0], latest_loc[1], kp_lat, kp_lng)
            if dist < 300:
                context_mode = kp_type
                context_name = kp_name
                break
    c_ctx.close()

    # ── 紀念日提前三天提醒 ──────────────────────────────────────────────────
    import datetime as _dt
    ann_hint = ""
    c_ann = db()
    ann_rows = c_ann.execute("SELECT person,relation,event_type,month,day,year,notes FROM anniversaries").fetchall()
    c_ann.close()
    today_d = _dt.date.today()
    for person, rel, etype, month, day, year, notes in ann_rows:
        if not month or not day:
            continue
        try:
            candidate = _dt.date(today_d.year, int(month), int(day))
            if candidate < today_d:
                candidate = _dt.date(today_d.year + 1, int(month), int(day))
            days_away = (candidate - today_d).days
            if days_away <= 3:
                type_label = {"birthday":"生日","anniversary":"結婚紀念日","work":"入職週年"}.get(etype, etype)
                # 計算周年數（如結婚幾週年）
                years_str = ""
                if year:
                    elapsed = candidate.year - int(year)
                    milestones = {10:"十週年",20:"二十週年",25:"銀婚",30:"三十週年",
                                  40:"紅寶石婚",50:"金婚",60:"鑽石婚"}
                    if elapsed in milestones:
                        years_str = f"（{milestones[elapsed]}！）"
                    elif elapsed > 0:
                        years_str = f"（第{elapsed}年）"
                if days_away == 0:
                    ann_hint = f"今天是{person}的{type_label}{years_str}，記得好好慶祝。"
                elif days_away == 1:
                    ann_hint = f"明天是{person}的{type_label}{years_str}，提前準備。"
                else:
                    hint_end = f"備注：{notes}" if notes else "早點安排"
                    ann_hint = f"{days_away}天後是{person}的{type_label}{years_str}，{hint_end}。"
                break
        except Exception:
            pass

    # ── 未兌現承諾提醒（follow_up 最老的一筆）───────────────────────────────
    c_p = db()
    old_promise = c_p.execute(
        "SELECT to_whom,content FROM promises WHERE status='pending' ORDER BY noted_at ASC LIMIT 1"
    ).fetchone()
    c_p.close()

    # ── 寵物耗材快沒了 ──────────────────────────────────────────────────────
    c_pet = db()
    pet_supply_warn = ""
    supply_rows = c_pet.execute(
        "SELECT ps.item, ps.last_bought, ps.est_days_total, p.name "
        "FROM pet_supplies ps LEFT JOIN pets p ON ps.pet_id=p.id "
        "ORDER BY ps.last_bought ASC LIMIT 10"
    ).fetchall()
    c_pet.close()
    for item, last_bought, est, pet in supply_rows:
        if last_bought and est:
            try:
                bought = _dt.date.fromisoformat(last_bought)
                remain = max(0, est - (today_d - bought).days)
                if remain <= 5:
                    pet_supply_warn = f"{pet or ''}的「{item}」大概只剩 {remain} 天了，需要我幫您補貨嗎？"
                    break
            except Exception:
                pass

    # ── 客戶/夥伴拜訪偵測 → 提醒帶點心 ──────────────────────────────────────
    visit_hint = ""
    c_visit = db()
    all_events = c_visit.execute(
        "SELECT title, event_time FROM calendar_events WHERE event_date=date('now') ORDER BY event_time"
    ).fetchall()
    all_prefs = c_visit.execute(
        "SELECT person, relation, category, content, importance FROM people_prefs ORDER BY person"
    ).fetchall()
    c_visit.close()

    if all_events and all_prefs:
        for ev_title, ev_time in all_events:
            ev_lower = ev_title.lower()
            for person, relation, category, content, importance in all_prefs:
                if any(p.lower() in ev_lower for p in person.split()[:2]):
                    # 找到行程中有對應偏好的人
                    gift_hint = ""
                    drink_prefs = [(cat, cont) for _, _, cat, cont, _ in all_prefs
                                   if _ == person or True  # fetch matched person's all prefs
                                   if cat in ("drink","food","gift")]

                    # 找這個人所有偏好
                    person_prefs = [(cat2, cont2) for p2, rel2, cat2, cont2, imp2 in all_prefs if p2 == person]
                    drinks = [cont2 for cat2, cont2 in person_prefs if cat2 == "drink"]
                    foods  = [cont2 for cat2, cont2 in person_prefs if cat2 == "food"]
                    gifts  = [cont2 for cat2, cont2 in person_prefs if cat2 == "gift"]
                    taboos = [cont2 for cat2, cont2 in person_prefs if cat2 == "taboo"]

                    suggestions = []
                    if drinks:
                        d0 = drinks[0]
                        suggestions.append(d0 if any(kw in d0 for kw in ["喝","茶","咖","飲","啤"]) else f"愛喝{d0}")
                    if foods and not drinks:
                        f0 = foods[0]
                        suggestions.append(f0 if any(kw in f0 for kw in ["吃","食","喜歡","愛"]) else f"愛吃{f0}")
                    if gifts and not drinks and not foods:
                        suggestions.append(f"送禮可以考慮{gifts[0]}")

                    if suggestions:
                        time_str = f"{ev_time} " if ev_time else ""
                        sugg_str = "，".join(suggestions)
                        taboo_str = f"，記得避開{taboos[0]}" if taboos else ""
                        visit_hint = (
                            f"今天{time_str}有「{ev_title}」，{person}{sugg_str}{taboo_str}。"
                            f"出門前要不要順路帶點東西？小心意，對方會記得的。"
                        )
                    break
            if visit_hint:
                break

    parts = [f"主人，{period}。"]
    if late_night_care:
        parts.append(late_night_care)
    elif weather:
        parts.append(f"{weather}。")
    if not late_night_care:
        if ann_hint:
            parts.append(ann_hint)
        if visit_hint:
            parts.append(visit_hint)
        elif events_today:
            ev = events_today[0]
            t = f"{ev[1]}，" if ev[1] else ""
            parts.append(f"今天{t}有「{ev[0]}」。")
        if todos_followup:
            parts.append(f"「{todos_followup[0]}」這件事，還沒處理。")
        if old_promise and not todos_followup:
            parts.append(f"還有，您之前答應{old_promise[0]}要{old_promise[1]}，還沒跟進。")
        if pet_supply_warn:
            parts.append(pet_supply_warn)

    # Proactive connection nudge — check what's not yet connected
    c2 = db()
    nudges = []
    # Google not connected
    if not (gcal_service and gcal_service.is_connected(db)):
        nudges.append("Google 行事曆")
    # LINE not connected
    line_user = c2.execute("SELECT value FROM memories WHERE category='line' AND key='owner_user_id' LIMIT 1").fetchone()
    if not line_user:
        nudges.append("LINE")
    # Telegram not connected
    tg_user = c2.execute("SELECT value FROM memories WHERE category='telegram' AND key='owner_chat_id' LIMIT 1").fetchone()
    if not tg_user:
        nudges.append("Telegram")
    # Contacts not imported
    contacts_n = c2.execute("SELECT COUNT(*) FROM contacts_index").fetchone()[0]
    if contacts_n == 0:
        nudges.append("Apple 聯絡人")
    # Mac not connected
    mac_n = c2.execute("SELECT COUNT(*) FROM mac_files_index").fetchone()[0]
    if mac_n == 0:
        nudges.append("Mac 檔案")
    c2.close()

    # Mention nudge once — randomly pick one to avoid overwhelming
    if nudges:
        import random
        pick = random.choice(nudges)
        parts.append(f"另外，「{pick}」還沒有連線，方便的話可以讓阿福接上，功能會更完整。")

    return {"text": "".join(parts)}

@app.get("/api/todos")
def todos():
    c = db(); rows = c.execute("SELECT id,title,due_date,status,follow_up FROM todos ORDER BY ts DESC").fetchall(); c.close()
    return [{"id":r[0],"title":r[1],"due_date":r[2],"status":r[3],"follow_up":r[4]} for r in rows]

@app.patch("/api/todos/{todo_id}")
def complete_todo_api(todo_id: int):
    c = db(); c.execute("UPDATE todos SET status='done' WHERE id=?", (todo_id,)); c.commit(); c.close()
    return {"ok": True}

@app.get("/api/calendar")
def calendar():
    c = db(); rows = c.execute("SELECT id,title,event_date,event_time,notes FROM calendar_events ORDER BY event_date,event_time").fetchall(); c.close()
    return [{"id":r[0],"title":r[1],"date":r[2],"time":r[3],"notes":r[4]} for r in rows]

@app.get("/api/reminders/pending")
def reminders_pending():
    now = datetime.now().isoformat()
    c = db()
    rows = c.execute(
        "SELECT id,title FROM reminders WHERE notified=0 AND trigger_at <= ? ORDER BY trigger_at",
        (now,)
    ).fetchall()
    ids = [r[0] for r in rows]
    if ids:
        c.execute(f"UPDATE reminders SET notified=1 WHERE id IN ({','.join('?'*len(ids))})", ids)
        c.commit()
    c.close()
    return [{"id":r[0],"title":r[1]} for r in rows]

@app.get("/api/expenses")
def expenses():
    c = db()
    rows = c.execute("SELECT id,amount,category,description,ts FROM expenses ORDER BY ts DESC LIMIT 50").fetchall()
    total = c.execute("SELECT SUM(amount) FROM expenses WHERE ts >= date('now','start of month')").fetchone()[0] or 0
    c.close()
    return {
        "items": [{"id":r[0],"amount":r[1],"category":r[2],"description":r[3],"ts":r[4]} for r in rows],
        "month_total": total
    }

class TTSReq(BaseModel):
    text: str

@app.post("/api/tts")
async def tts(req: TTSReq):
    el_key = os.getenv("ELEVENLABS_API_KEY", "")
    if not el_key:
        return StreamingResponse(iter([b""]), media_type="audio/mpeg")

    # Alfred 阿福: cloned from Michael Caine (The Dark Knight)
    VOICE_ID = "YWnZZfEtTni5X2rz4DEg"

    async with httpx.AsyncClient(timeout=60) as c:
        resp = await c.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}",
            headers={"xi-api-key": el_key, "Content-Type": "application/json"},
            json={
                "text": req.text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": 0.55,
                    "similarity_boost": 0.82,
                    "style": 0.38,
                    "use_speaker_boost": False
                }
            }
        )
        if resp.status_code != 200:
            return StreamingResponse(iter([b""]), media_type="audio/mpeg")
        audio = resp.content

    return StreamingResponse(iter([audio]), media_type="audio/mpeg")

class TranslateReq(BaseModel):
    text: str
    target_lang: str = "en"     # en/ja/ko/fr/es/de/th/vi/id
    source_lang: str = "auto"   # auto 自動偵測
    mode: str = "translate"     # translate=只翻譯 / interpret=加上口語自然化


_LANG_NAMES = {
    "en": "英文", "ja": "日文", "ko": "韓文",
    "fr": "法文", "es": "西班牙文", "de": "德文",
    "th": "泰文", "vi": "越南文", "id": "印尼文",
    "zh": "中文", "zh-TW": "繁體中文"
}

_WHISPER_LANG_MAP = {
    "en": "en", "ja": "ja", "ko": "ko",
    "fr": "fr", "es": "es", "de": "de",
    "th": "th", "vi": "vi", "id": "id",
    "zh": "zh", "zh-TW": "zh", "auto": None
}

_ELEVENLABS_VOICES = {
    "en": "21m00Tcm4TlvDq8ikWAM",   # Rachel (English)
    "ja": "XrExE9yKIg1WjnnlVkGX",   # Matilda (Multilingual)
    "ko": "XrExE9yKIg1WjnnlVkGX",
    "fr": "XrExE9yKIg1WjnnlVkGX",
    "es": "XrExE9yKIg1WjnnlVkGX",
    "de": "XrExE9yKIg1WjnnlVkGX",
    "zh": "YWnZZfEtTni5X2rz4DEg",   # Alfred 聲音（中文）
    "zh-TW": "YWnZZfEtTni5X2rz4DEg",
}


@app.post("/api/translate")
async def translate_text(req: TranslateReq):
    """
    翻譯文字，並可選擇回傳 TTS 音頻。
    回傳 JSON: { translated, detected_lang, tts_available }
    """
    src = req.source_lang
    tgt = req.target_lang
    text = req.text.strip()
    if not text:
        return {"translated": "", "detected_lang": src}

    target_name = _LANG_NAMES.get(tgt, tgt)
    src_hint = f"（原文語言：{_LANG_NAMES.get(src, src)}）" if src != "auto" else ""

    if req.mode == "interpret":
        prompt = (
            f"請將以下文字翻譯成自然流暢的口語{target_name}，"
            f"語氣要像真人在說話，不要書面語{src_hint}。"
            f"只輸出翻譯結果，不加任何說明。\n\n{text}"
        )
    else:
        prompt = (
            f"請將以下文字翻譯成{target_name}{src_hint}。"
            f"只輸出翻譯結果，不加任何說明或解釋。\n\n{text}"
        )

    translated = _simple_chat(prompt, max_tokens=500)
    el_key = os.getenv("ELEVENLABS_API_KEY", "")

    return {
        "original": text,
        "translated": translated.strip(),
        "target_lang": tgt,
        "target_lang_name": target_name,
        "tts_available": bool(el_key)
    }


@app.post("/api/translate/tts")
async def translate_tts(
    text: str = Form(""),
    target_lang: str = Form("en"),
    source_lang: str = Form("auto"),
    mode: str = Form("interpret")
):
    """翻譯 + 直接回傳 TTS 音頻（合併兩步為一）。"""
    req = TranslateReq(text=text, target_lang=target_lang, source_lang=source_lang, mode=mode)
    result = await translate_text(req)
    translated = result.get("translated", "")
    if not translated:
        return StreamingResponse(iter([b""]), media_type="audio/mpeg")

    el_key = os.getenv("ELEVENLABS_API_KEY", "")
    if not el_key:
        return StreamingResponse(iter([b""]), media_type="audio/mpeg")

    tgt = req.target_lang
    voice_id = _ELEVENLABS_VOICES.get(tgt, _ELEVENLABS_VOICES.get("en"))

    async with httpx.AsyncClient(timeout=60) as c:
        resp = await c.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={"xi-api-key": el_key, "Content-Type": "application/json"},
            json={
                "text": translated,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
            }
        )
        if resp.status_code != 200:
            return StreamingResponse(iter([b""]), media_type="audio/mpeg")

    # Return both audio AND translated text in header
    return StreamingResponse(
        iter([resp.content]),
        media_type="audio/mpeg",
        headers={"X-Translated-Text": translated[:500]}
    )


@app.post("/api/transcribe/lang")
async def transcribe_with_lang(file: UploadFile = File(...), lang: str = "auto"):
    """Whisper 轉錄，支援指定語言（翻譯模式用）。"""
    import openai as _oai, tempfile, pathlib, os as _os
    _oai.api_key = os.getenv("OPENAI_API_KEY", "")
    audio_bytes = await file.read()
    suffix = pathlib.Path(file.filename or "audio.webm").suffix or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes); tmp_path = tmp.name
    try:
        whisper_lang = _WHISPER_LANG_MAP.get(lang)
        kwargs = {"model": "whisper-1", "file": open(tmp_path, "rb"), "response_format": "json"}
        if whisper_lang:
            kwargs["language"] = whisper_lang
        result = _oai.audio.transcriptions.create(**kwargs)
        return {"transcript": result.text, "detected_lang": lang}
    except Exception as e:
        return {"transcript": "", "error": str(e)}
    finally:
        _os.unlink(tmp_path)


@app.get("/api/gcal/authorize")
def gcal_authorize():
    """Redirect user to Google OAuth consent screen."""
    if not gcal_service:
        return {"error": "Google Calendar not configured"}
    from fastapi.responses import RedirectResponse
    return RedirectResponse(gcal_service.authorize_url())


@app.get("/api/gcal/callback")
async def gcal_callback(code: str = "", error: str = ""):
    """Google OAuth callback — exchange code and store tokens."""
    if error or not code:
        return Response(
            content=f"<html><body style='font-family:sans-serif;padding:40px'><h2>❌ 授權失敗：{error}</h2></body></html>",
            media_type="text/html")
    ok, msg = gcal_service.save_tokens_from_code(code, db)
    if ok:
        html = """<html><body style='background:#090909;color:#c9a84c;font-family:sans-serif;text-align:center;padding:60px'>
<h2>✅ Google 日曆已連結</h2><p>阿福現在可以讀取並新增您的 Google 行事曆了。</p>
<script>setTimeout(()=>window.close(),2000)</script></body></html>"""
    else:
        html = f"<html><body style='padding:40px'><h2>❌ 連結失敗：{msg}</h2></body></html>"
    return Response(content=html, media_type="text/html")


@app.get("/api/gcal/events")
def gcal_events(days: int = 7):
    """Return upcoming Google Calendar events."""
    if not gcal_service:
        return {"error": "not configured"}
    events = gcal_service.get_upcoming_events(db, days)
    return {"events": events, "connected": gcal_service.is_connected(db)}


@app.get("/api/gcal/status")
def gcal_status():
    connected = gcal_service.is_connected(db) if gcal_service else False
    return {"connected": connected}


@app.get("/api/setup/status")
async def setup_status():
    """Return connection status for all integrations — used by setup page."""
    # Google
    gcal_ok = gcal_service.is_connected(db) if gcal_service else False
    # Check if gmail scope exists (token was issued with gmail scope)
    gmail_ok = False
    if gcal_ok and gmail_service:
        try:
            token = gcal_service._get_access_token(db)
            if token:
                r = httpx.get("https://www.googleapis.com/oauth2/v3/tokeninfo",
                    params={"access_token": token}, timeout=5)
                scopes = r.json().get("scope", "")
                gmail_ok = "gmail" in scopes
        except Exception:
            pass

    # LINE — fetch bot basicId for add-friend URL
    line_bot_id = ""
    line_user_connected = False
    if LINE_CONFIGURED and line_service:
        try:
            token = line_service.get_access_token()
            if token:
                r = httpx.get("https://api.line.me/v2/bot/info",
                    headers={"Authorization": f"Bearer {token}"}, timeout=5)
                line_bot_id = r.json().get("basicId", "")
        except Exception:
            pass
        c = db()
        row = c.execute("SELECT value FROM memories WHERE category='line' AND key='owner_user_id' LIMIT 1").fetchone()
        c.close()
        line_user_connected = bool(row)

    # Telegram
    tg_bot_username = "alfred_demo_bot"
    tg_user_connected = False
    if TG_CONFIGURED and telegram_service:
        c = db()
        row = c.execute("SELECT value FROM memories WHERE category='telegram' AND key='owner_chat_id' LIMIT 1").fetchone()
        c.close()
        tg_user_connected = bool(row)

    return {
        "google": {"connected": gcal_ok, "gmail": gmail_ok},
        "line": {"configured": LINE_CONFIGURED, "bot_id": line_bot_id, "user_connected": line_user_connected},
        "telegram": {"configured": TG_CONFIGURED, "bot_username": tg_bot_username, "user_connected": tg_user_connected},
        "twilio": {"configured": TWILIO_CONFIGURED, "ai_call": AI_CALL_AVAILABLE},
    }


@app.get("/api/onboard/status")
def onboard_status():
    """是否已完成初次設定（有城市+名字記憶即視為完成）。"""
    c = db()
    city = c.execute("SELECT value FROM memories WHERE category='location' AND key='city' LIMIT 1").fetchone()
    name_pref = c.execute("SELECT value FROM memories WHERE category='preference' AND key='name_pref' LIMIT 1").fetchone()
    c.close()
    return {"completed": bool(city), "has_city": bool(city), "has_name": bool(name_pref)}


@app.post("/api/onboard/save")
async def onboard_save(request: Request):
    """儲存初次設定資料（城市、稱謂偏好）。"""
    data = await request.json()
    c = db()
    now = datetime.now().isoformat()
    if data.get("city"):
        c.execute("INSERT INTO memories (category,key,value,ts) VALUES (?,?,?,?)",
                  ("location", "city", data["city"], now))
        c.execute("INSERT INTO memories (category,key,value,ts) VALUES (?,?,?,?)",
                  ("location", "city_display", data.get("city_display", data["city"]), now))
    if data.get("name_pref"):
        c.execute("INSERT INTO memories (category,key,value,ts) VALUES (?,?,?,?)",
                  ("preference", "name_pref", data["name_pref"], now))
    if data.get("wake_hour") is not None:
        c.execute("INSERT INTO memories (category,key,value,ts) VALUES (?,?,?,?)",
                  ("preference", "wake_hour", str(data["wake_hour"]), now))
    if data.get("priority_mode"):
        c.execute("INSERT INTO memories (category,key,value,ts) VALUES (?,?,?,?)",
                  ("preference", "priority_mode", data["priority_mode"], now))
    c.execute("INSERT INTO memories (category,key,value,ts) VALUES (?,?,?,?)",
              ("system", "onboarded_at", now, now))
    c.commit(); c.close()
    return {"ok": True}


@app.get("/api/visit/prep")
async def visit_prep():
    """
    掃描未來 2 小時內的行程，比對 people_prefs，
    若有已知偏好的人名在行程標題中 → 回傳提醒帶禮物/飲料的建議。
    前端每 30 分鐘輪詢一次。
    """
    import datetime as _dt
    now = _dt.datetime.now()
    c = db()
    # 取未來 2 小時內的行程
    today = now.strftime("%Y-%m-%d")
    events = c.execute(
        "SELECT id, title, event_time FROM calendar_events WHERE event_date=? ORDER BY event_time",
        (today,)
    ).fetchall()
    prefs_all = c.execute(
        "SELECT person, category, content FROM people_prefs ORDER BY person"
    ).fetchall()
    c.close()

    reminders = []
    for eid, title, etime in events:
        if not etime:
            continue
        try:
            ev_dt = _dt.datetime.strptime(f"{today} {etime}", "%Y-%m-%d %H:%M")
        except Exception:
            try:
                ev_dt = _dt.datetime.strptime(f"{today} {etime}", "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue
        mins_away = (ev_dt - now).total_seconds() / 60
        if not (0 < mins_away <= 120):
            continue

        title_lower = title.lower()
        for person, cat, content in prefs_all:
            if any(p.lower() in title_lower for p in person.split()[:2]):
                # 找到匹配
                person_all = [(c2, ct) for p2, c2, ct in prefs_all if p2 == person]
                drinks  = [ct for c2, ct in person_all if c2 == "drink"]
                foods   = [ct for c2, ct in person_all if c2 == "food"]
                taboos  = [ct for c2, ct in person_all if c2 == "taboo"]

                if drinks or foods:
                    sugg = drinks[0] if drinks else foods[0]
                    taboo_warn = f"，記得避開{taboos[0]}" if taboos else ""
                    reminders.append({
                        "event_id": eid,
                        "event_title": title,
                        "event_time": etime,
                        "minutes_away": int(mins_away),
                        "person": person,
                        "suggestion": sugg,
                        "taboo": taboos[0] if taboos else "",
                        "message": (
                            f"主人，再 {int(mins_away)} 分鐘要去「{title}」見{person}了。"
                            f"他{'/她' if '小' in person else ''}喜歡{sugg}{taboo_warn}——"
                            f"出門前要不要順路帶一份？小心意，對方會記得的。"
                        )
                    })
                break

    return {"reminders": reminders}


@app.get("/api/discover")
def discover_features():
    """
    根據使用紀錄，回傳主人還沒用過的 2 個功能建議，
    讓阿福在對話中自然提及。
    """
    c = db()
    tried = set()
    if c.execute("SELECT COUNT(*) FROM todos").fetchone()[0] > 0:
        tried.add("todos")
    if c.execute("SELECT COUNT(*) FROM reminders").fetchone()[0] > 0:
        tried.add("reminders")
    if c.execute("SELECT COUNT(*) FROM expenses").fetchone()[0] > 0:
        tried.add("expenses")
    if c.execute("SELECT COUNT(*) FROM meeting_notes").fetchone()[0] > 0:
        tried.add("meeting")
    if c.execute("SELECT COUNT(*) FROM files").fetchone()[0] > 0:
        tried.add("files")
    if c.execute("SELECT COUNT(*) FROM family_members").fetchone()[0] > 0:
        tried.add("family")
    if c.execute("SELECT COUNT(*) FROM pets").fetchone()[0] > 0:
        tried.add("pets")
    if c.execute("SELECT COUNT(*) FROM promises").fetchone()[0] > 0:
        tried.add("promises")
    if c.execute("SELECT COUNT(*) FROM anniversaries").fetchone()[0] > 0:
        tried.add("anniversaries")
    if c.execute("SELECT COUNT(*) FROM ambient_sessions").fetchone()[0] > 0:
        tried.add("ambient")
    c.close()

    all_features = [
        {"id":"todos", "trigger":"試試說「阿福，今天要做三件事：…」", "desc":"待辦追蹤"},
        {"id":"reminders", "trigger":"試試說「阿福，一小時後提醒我打電話給客戶」", "desc":"提醒"},
        {"id":"expenses", "trigger":"試試說「阿福，剛才午餐花了280元」", "desc":"記帳"},
        {"id":"meeting", "trigger":"試試說「阿福，幫我記錄這個會議」", "desc":"會議記錄"},
        {"id":"files", "trigger":"試試說「阿福，有一份合約太複雜，幫我看吧」", "desc":"合約審閱"},
        {"id":"family", "trigger":"試試說「阿福，新增我太太的位置共享」", "desc":"家人定位"},
        {"id":"pets", "trigger":"試試說「阿福，我有一隻貓叫Mochi」", "desc":"寵物守護"},
        {"id":"promises", "trigger":"試試說「阿福，我答應Tom這週幫他爭取預算」", "desc":"承諾追蹤"},
        {"id":"anniversaries", "trigger":"試試說「阿福，太太生日是5月2日」", "desc":"紀念日"},
        {"id":"ambient", "trigger":"試試說「阿福，接下來幫我記錄今天的對話」", "desc":"辦公聆聽"},
    ]
    suggestions = [f for f in all_features if f["id"] not in tried]
    import random; random.shuffle(suggestions)
    return {"suggestions": suggestions[:2], "tried_count": len(tried)}


@app.get("/health")
def health():
    gcal_ok = gcal_service.is_connected(db) if gcal_service else False
    return {"status": "ok", "alfred": "ready", "ai_call": AI_CALL_AVAILABLE,
            "gcal": gcal_ok, "line": LINE_CONFIGURED, "telegram": TG_CONFIGURED}


# ─── Shared messaging helper (LINE + Telegram) ────────────────────────────────

_MESSAGING_TOOL_NAMES = {
    "save_memory", "create_todo", "complete_todo", "set_reminder",
    "record_expense", "create_calendar_event", "lookup_contact",
    "search_web", "save_relationship", "save_food_record",
}
_MESSAGING_TOOLS = [t for t in TOOLS if t["name"] in _MESSAGING_TOOL_NAMES]


async def _run_alfred_for_messaging(text: str) -> str:
    """Run Alfred chat with tools for messaging platforms. Returns plain text."""
    now = datetime.now().strftime('%Y年%m月%d日 %H:%M')
    system = (
        f"你是阿福，私人管家。透過訊息平台收到主人指令。\n"
        f"現在時間：{now}\n"
        f"主人的記憶：{get_memories()[:600]}\n"
        f"待辦：{get_todos()[:300]}\n"
        f"近期行程：{get_cal()[:200]}\n"
        "回覆簡短有力，繁體中文，適合訊息閱讀，不超過 250 字。"
    )
    messages: list = [{"role": "user", "content": text}]
    full_text = ""

    for _ in range(4):
        _t, _tcs, _fin, _raw = _llm_chat(system, messages, _MESSAGING_TOOLS, max_tokens=500)
        if _t:
            full_text += _t
        if _fin == "end_turn":
            break

        c = db()
        results = []
        for _tc in _tcs:
            class _B2:
                def __init__(self, d): self.name=d["name"]; self.input=d["input"]; self.id=d["id"]
            b = _B2(_tc)
            inp = b.input
            res = ""
            if b.name == "save_memory":
                c.execute("INSERT INTO memories (category,key,value,ts) VALUES (?,?,?,?)",
                    (inp["category"], inp["key"], inp["value"], datetime.now().isoformat()))
                res = "已記住"
            elif b.name == "create_todo":
                c.execute("INSERT INTO todos (title,due_date,follow_up,status,ts) VALUES (?,?,?,?,?)",
                    (inp["title"], inp.get("due_date",""), 1 if inp.get("follow_up") else 0,
                     "pending", datetime.now().isoformat()))
                res = f"待辦「{inp['title']}」已新增"
            elif b.name == "complete_todo":
                kw = f"%{inp['keyword']}%"
                row = c.execute(
                    "SELECT id,title FROM todos WHERE title LIKE ? AND status='pending'", (kw,)
                ).fetchone()
                if row:
                    c.execute("UPDATE todos SET status='done' WHERE id=?", (row[0],))
                    res = f"「{row[1]}」已完成"
                else:
                    res = "找不到符合的待辦"
            elif b.name == "set_reminder":
                c.execute("INSERT INTO reminders (title,trigger_at,notified,ts) VALUES (?,?,?,?)",
                    (inp["title"], inp["trigger_at"], 0, datetime.now().isoformat()))
                res = f"提醒「{inp['title']}」已設定"
            elif b.name == "record_expense":
                c.execute("INSERT INTO expenses (amount,category,description,ts) VALUES (?,?,?,?)",
                    (inp["amount"], inp["category"], inp["description"], datetime.now().isoformat()))
                res = f"已記錄 {inp['amount']} 元"
            elif b.name == "create_calendar_event":
                c.execute(
                    "INSERT INTO calendar_events (title,event_date,event_time,notes,ts) VALUES (?,?,?,?,?)",
                    (inp["title"], inp["event_date"], inp.get("event_time",""),
                     inp.get("notes",""), datetime.now().isoformat()))
                res = f"行程「{inp['title']}」已新增"
            elif b.name == "lookup_contact":
                kw = f"%{inp['keyword']}%"
                rows = c.execute(
                    "SELECT nickname,real_name,contact FROM relationships "
                    "WHERE nickname LIKE ? OR real_name LIKE ? OR notes LIKE ?",
                    (kw, kw, kw)).fetchall()
                res = "\n".join(f"「{r[0]}」{r[1] or ''} {r[2] or ''}" for r in rows) if rows else "找不到"
            elif b.name == "search_web":
                try:
                    async with httpx.AsyncClient(timeout=8) as hc:
                        r = await hc.get("https://api.duckduckgo.com/",
                            params={"q": inp["query"], "format": "json", "no_html": "1", "skip_disambig": "1"})
                        d = r.json()
                        res = (d.get("Answer") or d.get("AbstractText","")[:300] or
                               next((t.get("Text","")[:150] for t in d.get("RelatedTopics",[])
                                     if isinstance(t,dict)), "暫無資料"))
                except Exception:
                    res = "搜尋暫時無法使用"
            elif b.name == "save_relationship":
                c.execute("INSERT INTO relationships (nickname,real_name,contact,notes,ts) VALUES (?,?,?,?,?)",
                    (inp["nickname"], inp.get("real_name",""), inp.get("contact",""),
                     inp.get("notes",""), datetime.now().isoformat()))
                res = f"關係人「{inp['nickname']}」已記錄"
            elif b.name == "save_food_record":
                c.execute("INSERT INTO food_history (food,restaurant,platform,tags,ts) VALUES (?,?,?,?,?)",
                    (inp["food"], inp.get("restaurant",""), inp.get("platform",""),
                     inp.get("tags",""), datetime.now().isoformat()))
                res = "飲食已記錄"
            results.append({"tool_call_id": b.id, "name": b.name, "result": str(res)})

        c.commit(); c.close()
        if LLM_PROVIDER == "gemini":
            messages.append({"role": "assistant", "content": _t or None,
                             "tool_calls": [{"id": r["tool_call_id"],"type":"function",
                                             "function":{"name":r["name"],"arguments":"{}"}} for r in results]})
            for r in results:
                messages.append({"role":"tool","tool_call_id":r["tool_call_id"],"content":r["result"]})
        else:
            messages.append({"role": "assistant", "content": _raw})
            messages.append({"role": "user", "content": [
                {"type":"tool_result","tool_use_id":r["tool_call_id"],"content":r["result"]} for r in results]})

    return full_text or "收到，主人。"


# ─── Morning briefing ─────────────────────────────────────────────────────────

@app.get("/api/briefing/morning")
async def morning_briefing():
    """Generate morning briefing and push to Telegram + LINE."""
    from datetime import date as _date
    city_display, city_en = get_user_city()
    weather = await fetch_weather(city_en, city_display)
    today = _date.today().strftime("%-m月%-d日")

    c = db()
    events = c.execute(
        "SELECT title, event_time FROM calendar_events WHERE event_date = date('now') ORDER BY event_time"
    ).fetchall()
    gcal_events: list = []
    if gcal_service and gcal_service.is_connected(db):
        gcal_events = gcal_service.get_upcoming_events(db, days=1)

    todos = c.execute(
        "SELECT title, due_date FROM todos WHERE status='pending' ORDER BY follow_up DESC, ts DESC LIMIT 5"
    ).fetchall()
    c.close()

    lines = [f"早安，主人。今天是 {today}。"]
    if weather:
        lines.append(weather + "。")

    all_events = list(events) + [(e["title"], e["start"][11:16]) for e in gcal_events]
    if all_events:
        lines.append("\n📅 今日行程：")
        for e in all_events:
            t = f"{e[1]} " if e[1] else ""
            lines.append(f"  • {t}{e[0]}")
    else:
        lines.append("\n今天沒有排定的行程，可以好好休息。")

    if todos:
        lines.append("\n☐ 待辦提醒：")
        for t in todos[:4]:
            due = f"（{t[1]}）" if t[1] else ""
            lines.append(f"  • {t[0]}{due}")

    message = "\n".join(lines)
    sent_to = []

    if TG_CONFIGURED and telegram_service:
        c2 = db()
        row = c2.execute(
            "SELECT value FROM memories WHERE category='telegram' AND key='owner_chat_id' ORDER BY ts DESC LIMIT 1"
        ).fetchone()
        c2.close()
        if row:
            telegram_service.send_message(row[0], message)
            sent_to.append("telegram")

    if LINE_CONFIGURED and line_service:
        c2 = db()
        row = c2.execute(
            "SELECT value FROM memories WHERE category='line' AND key='owner_user_id' ORDER BY ts DESC LIMIT 1"
        ).fetchone()
        c2.close()
        if row:
            line_service.push_message(row[0], message)
            sent_to.append("line")

    return {"sent_to": sent_to, "message": message}


# ─── Telegram Bot webhook ─────────────────────────────────────────────────────

@app.post("/api/telegram/webhook")
async def telegram_webhook(request: Request):
    """Receive Telegram updates and reply via Alfred's chat engine."""
    if not TG_CONFIGURED or not telegram_service:
        return {"ok": False}

    data = await request.json()
    message = data.get("message") or data.get("edited_message")
    if not message:
        return {"ok": True}

    chat_id = message["chat"]["id"]
    text = message.get("text", "")
    if not text:
        return {"ok": True}

    # Store owner's Telegram chat_id
    c = db()
    c.execute(
        "INSERT OR REPLACE INTO memories (category,key,value,ts) VALUES (?,?,?,?)",
        ("telegram", "owner_chat_id", str(chat_id), datetime.now().isoformat())
    )
    c.commit(); c.close()

    try:
        reply_text = await _run_alfred_for_messaging(text)
    except Exception:
        reply_text = "阿福暫時無法回應，請稍後再試。"

    telegram_service.send_message(chat_id, reply_text)
    return {"ok": True}


@app.get("/api/telegram/setup")
def telegram_setup():
    """Register webhook with Telegram (call once after deploy)."""
    if not TG_CONFIGURED or not telegram_service:
        return {"error": "not configured"}
    host = os.getenv("SERVER_HOST", "")
    webhook_url = f"https://{host}/alfred/api/telegram/webhook"
    result = telegram_service.set_webhook(webhook_url)
    return result


# ─── LINE Messaging API webhook ───────────────────────────────────────────────

@app.post("/api/line/webhook")
async def line_webhook(request: Request):
    """Receive LINE messages and reply via Alfred's chat engine."""
    if not LINE_CONFIGURED or not line_service:
        return {"status": "not_configured"}

    body = await request.body()
    sig = request.headers.get("X-Line-Signature", "")
    if not line_service.verify_signature(body, sig):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="invalid signature")

    data = json.loads(body)
    for event in data.get("events", []):
        if event.get("type") != "message":
            continue
        if event["message"]["type"] != "text":
            continue

        user_id = event["source"].get("userId", "")
        reply_token = event.get("replyToken", "")
        user_text = event["message"]["text"]

        # Store owner's LINE user_id (first time or update)
        if user_id:
            c = db()
            c.execute(
                "INSERT OR REPLACE INTO memories (category,key,value,ts) VALUES (?,?,?,?)",
                ("line", "owner_user_id", user_id, datetime.now().isoformat())
            )
            c.commit(); c.close()

        try:
            reply_text = await _run_alfred_for_messaging(user_text)
        except Exception:
            reply_text = "阿福暫時無法回應，請稍後再試。"

        if reply_token:
            line_service.reply_message(reply_token, reply_text)

    return {"status": "ok"}


# ─── Twilio Voice endpoints ────────────────────────────────────────────────────

@app.post("/api/sms/reply")
async def sms_reply(request: Request):
    """Receive incoming SMS (e.g. restaurant reply) and store for Alfred to relay."""
    form = await request.form()
    from_num = form.get("From", "")
    body = form.get("Body", "")
    c = db()
    c.execute(
        "INSERT INTO memories (category,key,value,ts) VALUES (?,?,?,?)",
        ("incoming_sms", from_num, body, datetime.now().isoformat())
    )
    c.commit(); c.close()
    # Return empty TwiML (no auto-reply)
    return Response(content="<?xml version='1.0'?><Response></Response>", media_type="text/xml")


FILE_DIR = "/opt/alfred/data/files"

@app.post("/api/files/upload")
async def upload_file(file: UploadFile = File(...),
                      description: str = Form(""),
                      tags: str = Form("")):
    """Upload a file from phone/computer to Alfred's local storage."""
    import uuid, pathlib, shutil
    ext = pathlib.Path(file.filename or "file").suffix
    stored_name = f"{uuid.uuid4().hex}{ext}"
    dest = f"{FILE_DIR}/{stored_name}"
    content = await file.read()
    with open(dest, "wb") as f:
        f.write(content)
    c = db()
    c.execute(
        "INSERT INTO files (filename,original_name,mime_type,size,description,tags,ts) VALUES (?,?,?,?,?,?,?)",
        (stored_name, file.filename, file.content_type or "", len(content), description, tags, datetime.now().isoformat())
    )
    c.commit()
    file_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    c.close()
    return {"id": file_id, "name": file.filename, "size": len(content), "ok": True}


@app.get("/api/files")
def list_files_api(q: str = "", limit: int = 30):
    """List uploaded local files."""
    c = db()
    if q:
        rows = c.execute(
            "SELECT id,original_name,mime_type,size,description,tags,ts FROM files "
            "WHERE original_name LIKE ? OR description LIKE ? OR tags LIKE ? ORDER BY ts DESC LIMIT ?",
            (f"%{q}%", f"%{q}%", f"%{q}%", limit)
        ).fetchall()
    else:
        rows = c.execute(
            "SELECT id,original_name,mime_type,size,description,tags,ts FROM files ORDER BY ts DESC LIMIT ?",
            (limit,)
        ).fetchall()
    c.close()
    return [{"id": r[0], "name": r[1], "mime": r[2], "size": r[3],
             "description": r[4], "tags": r[5], "ts": r[6]} for r in rows]


@app.get("/api/files/{file_id}")
def download_file(file_id: int):
    """Download a stored file."""
    from fastapi.responses import FileResponse
    c = db()
    row = c.execute("SELECT filename,original_name,mime_type FROM files WHERE id=?", (file_id,)).fetchone()
    c.close()
    if not row:
        return Response(content="Not found", status_code=404)
    path = f"{FILE_DIR}/{row[0]}"
    return FileResponse(path, filename=row[1], media_type=row[2] or "application/octet-stream")


@app.delete("/api/files/{file_id}")
def delete_file(file_id: int):
    import os as _os
    c = db()
    row = c.execute("SELECT filename FROM files WHERE id=?", (file_id,)).fetchone()
    if row:
        try: _os.unlink(f"{FILE_DIR}/{row[0]}")
        except Exception: pass
        c.execute("DELETE FROM files WHERE id=?", (file_id,))
        c.commit()
    c.close()
    return {"ok": True}


@app.get("/api/drive/files")
async def drive_list(q: str = "", refresh: bool = False):
    if not drive_service:
        return {"error": "drive not configured", "files": []}
    files, from_cache = drive_service.search_files(db, query=q, limit=50, force_refresh=refresh)
    return {"files": files, "from_cache": from_cache, "total_indexed": drive_service.index_count(db)}


@app.post("/api/analyze-photo")
async def analyze_photo(file: UploadFile = File(...), question: str = "這張照片裡有什麼？幫我說明。"):
    """Analyze photo with Claude Vision. Recognizes people/scenes/objects."""
    import base64 as _b64
    data = await file.read()
    b64 = _b64.b64encode(data).decode()
    mime = file.content_type or "image/jpeg"

    # Load known family/people from memory
    c = db()
    people = c.execute(
        "SELECT key,value FROM memories WHERE category='person' ORDER BY ts DESC LIMIT 10"
    ).fetchall()
    contacts_sample = c.execute(
        "SELECT name,org FROM contacts_index ORDER BY name LIMIT 30"
    ).fetchall()
    c.close()

    people_ctx = ""
    if people:
        people_ctx = "主人介紹過的人：\n" + "\n".join(f"• {p[0]}：{p[1]}" for p in people)
    if contacts_sample:
        people_ctx += "\n聯絡人名單（供參考）：" + "、".join(r[0] for r in contacts_sample[:20])

    system = f"""你是阿福，私人管家。主人給你看一張照片，請仔細分析並回答問題。
{people_ctx}
回答要自然、口語，繁體中文，不超過 200 字。
如果照片中有主人介紹過的家人或朋友，要認出並提及他們的名字。"""

    if LLM_PROVIDER == "gemini":
        img_msg = {"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
            {"type": "text", "text": question}
        ]}
        r2 = _llm.chat.completions.create(
            model=LLM_MODEL, max_tokens=500,
            messages=[{"role":"system","content":system}, img_msg]
        )
        reply = r2.choices[0].message.content or "無法分析這張照片。"
    elif client:
        resp = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=500, system=system,
            messages=[{"role":"user","content":[
                {"type":"image","source":{"type":"base64","media_type":mime,"data":b64}},
                {"type":"text","text":question}
            ]}]
        )
        reply = resp.content[0].text if resp.content else "無法分析這張照片。"
    else:
        reply = "圖片分析需要配置 LLM API。"
    return {"reply": reply}


# ─── Location Intelligence ────────────────────────────────────────────────────

import math as _math

def _haversine(lat1, lng1, lat2, lng2) -> float:
    """Distance in meters between two GPS points."""
    R = 6371000
    p = _math.pi / 180
    a = (0.5 - _math.cos((lat2-lat1)*p)/2
         + _math.cos(lat1*p) * _math.cos(lat2*p) * (1-_math.cos((lng2-lng1)*p))/2)
    return R * 2 * _math.asin(_math.sqrt(a))

def _classify_mode(speed_kmh: float) -> str:
    if speed_kmh > 30:   return "driving"
    if speed_kmh > 4:    return "walking"
    return "stationary"

def _maps_link(lat, lng) -> str:
    return f"https://maps.google.com/?q={lat},{lng}"

def _reverse_geocode_approx(lat, lng) -> str:
    """Best-effort reverse geocode via Nominatim (no key needed)."""
    try:
        r = httpx.get("https://nominatim.openstreetmap.org/reverse",
            params={"lat": lat, "lon": lng, "format": "json", "zoom": 18},
            headers={"User-Agent": "Alfred-Butler/1.0"}, timeout=6)
        d = r.json()
        addr = d.get("address", {})
        parts = [addr.get(k,"") for k in ("road","suburb","city","town","village") if addr.get(k)]
        return "、".join(parts[:3]) or d.get("display_name","")[:60]
    except Exception:
        return f"{lat:.5f},{lng:.5f}"


def _extract_text_from_file(path: str, mime: str = "", fname: str = "") -> str:
    """Pull plain text out of pdf / docx / txt / md."""
    fname_lower = (fname or path).lower()
    try:
        if fname_lower.endswith(".pdf") or "pdf" in mime:
            import pypdf
            r = pypdf.PdfReader(path)
            return "\n".join((p.extract_text() or "") for p in r.pages)
        if fname_lower.endswith(".docx") or "wordprocessing" in mime:
            import docx
            d = docx.Document(path)
            return "\n".join(p.text for p in d.paragraphs)
        if fname_lower.endswith((".txt",".md",".text")) or mime.startswith("text/"):
            with open(path, encoding="utf-8", errors="ignore") as fh:
                return fh.read()
    except Exception as e:
        return f"[文件解析失敗：{e}]"
    return "[不支援的檔案格式，目前能讀 PDF / DOCX / TXT / MD]"


@app.post("/api/contract/analyze/{file_id}")
async def analyze_contract_endpoint(file_id: int, output: str = "report"):
    """讀取已上傳的合約檔案，由 Claude 進行條款 / 風險 / 懲罰條款分析。"""
    c = db()
    row = c.execute(
        "SELECT filename, original_name, mime_type FROM files WHERE id=?", (file_id,)
    ).fetchone()
    c.close()
    if not row:
        return {"ok": False, "error": "檔案不存在"}
    stored, name, mime = row
    path = f"{FILE_DIR}/{stored}"
    if not os.path.exists(path):
        return {"ok": False, "error": "檔案遺失"}
    text = _extract_text_from_file(path, mime or "", name or "")
    if not text or text.startswith("["):
        return {"ok": False, "error": text or "讀取失敗"}
    if len(text) > 80000:
        text = text[:80000] + "\n…[後段省略]"

    prompt = f"""你是經驗豐富的英美法系律師兼商務顧問，幫主人快速審閱以下合約。

請以**簡潔的繁體中文 Markdown 報告**輸出，欄位如下：

## 一、合約一句話總結
（30 字內，誰跟誰、做什麼、多久）

## 二、雙方主體
- 甲方：
- 乙方：

## 三、最重要的 5 條條款
列出 bullet，每條 1-2 句話。

## 四、懲罰 / 違約條款
- 列出所有罰款、違約金、終止賠償。
- 沒有的話明確寫「無懲罰條款」。

## 五、對主人不利的紅旗 🚩
（不限數量，越具體越好。沒有就寫「無重大紅旗」。）

## 六、建議行動
- 簽前要釐清/修改的點。
- 簽前要附帶哪些書面確認。

最後 **用一句話**告訴主人「值不值得簽」與你的信心程度。

合約全文：
---
{text}
---"""

    report_md = _simple_chat(prompt, max_tokens=3000)

    return {
        "ok": True,
        "file_id": file_id,
        "name": name,
        "report": report_md,
        "output": output,
    }


@app.post("/api/location/update")
async def location_update(request: Request):
    """
    Receive GPS batch from iOS App / PWA.
    Body: {points: [{lat,lng,speed,heading,accuracy,ts}]}
    Handles state machine: driving→parked→walking.
    """
    data = await request.json()
    points = data.get("points", [])
    if not points:
        return {"ok": False}

    c = db()
    now_iso = datetime.now().isoformat()

    # Get last known state
    last = c.execute(
        "SELECT lat,lng,speed,mode,ts FROM location_log ORDER BY id DESC LIMIT 1"
    ).fetchone()
    last_mode = last[3] if last else "unknown"
    last_lat, last_lng = (last[0], last[1]) if last else (None, None)

    # Insert all points
    for p in points:
        speed = p.get("speed", 0) or 0
        if speed < 0: speed = 0
        speed_kmh = speed * 3.6
        mode = _classify_mode(speed_kmh)
        c.execute(
            "INSERT INTO location_log (lat,lng,speed,heading,accuracy,mode,ts) VALUES (?,?,?,?,?,?,?)",
            (p["lat"], p["lng"], speed_kmh, p.get("heading",0), p.get("accuracy",0), mode, p.get("ts", now_iso))
        )

    # Analyze last 10 minutes to detect state transitions
    ten_min_ago = (datetime.now() - __import__("datetime").timedelta(minutes=10)).isoformat()
    recent = c.execute(
        "SELECT lat,lng,speed,mode,ts FROM location_log WHERE ts > ? ORDER BY id DESC LIMIT 60",
        (ten_min_ago,)
    ).fetchall()

    actions_taken = []

    if recent:
        speeds = [r[2] for r in recent]
        avg_speed = sum(speeds) / len(speeds)
        current_mode = _classify_mode(avg_speed)
        latest_lat, latest_lng = recent[0][0], recent[0][1]

        # PARKING DETECTION: was driving, now stationary for 10+ min
        if last_mode == "driving" and current_mode == "stationary":
            addr = await asyncio.get_event_loop().run_in_executor(
                None, _reverse_geocode_approx, latest_lat, latest_lng)
            c.execute(
                "INSERT INTO parking_spots (lat,lng,address,note,parked_at) VALUES (?,?,?,?,?)",
                (latest_lat, latest_lng, addr, "", now_iso)
            )
            actions_taken.append(f"parking_saved:{addr}")

        # WALKING DETECTION: was stationary (parked), now walking
        elif last_mode == "stationary" and current_mode == "walking":
            # Start new walk route from last parking spot
            last_park = c.execute(
                "SELECT id FROM parking_spots ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if last_park:
                walk_pts = json.dumps([[r[0], r[1]] for r in recent])
                c.execute(
                    "INSERT INTO walk_routes (parking_id,points,started_at) VALUES (?,?,?)",
                    (last_park[0], walk_pts, now_iso)
                )
            actions_taken.append("walk_route_started")

        # PLACE VISIT: stationary for 5+ min at new location → log place
        elif current_mode == "stationary" and last_lat:
            dist = _haversine(last_lat, last_lng, latest_lat, latest_lng)
            if dist < 100:  # stayed within 100m
                # Check if we already logged this recent stop
                recent_place = c.execute(
                    "SELECT id FROM place_history WHERE arrived_at > ? AND lat BETWEEN ? AND ?",
                    ((datetime.now() - __import__("datetime").timedelta(minutes=15)).isoformat(),
                     latest_lat - 0.001, latest_lat + 0.001)
                ).fetchone()
                if not recent_place:
                    addr = await asyncio.get_event_loop().run_in_executor(
                        None, _reverse_geocode_approx, latest_lat, latest_lng)
                    c.execute(
                        "INSERT INTO place_history (lat,lng,name,category,arrived_at) VALUES (?,?,?,?,?)",
                        (latest_lat, latest_lng, addr, "unknown", now_iso)
                    )
                    actions_taken.append(f"place_logged:{addr}")

    c.commit()
    c.close()
    return {"ok": True, "actions": actions_taken}


@app.get("/api/parking/last")
def get_last_parking():
    """Return last parking location."""
    c = db()
    row = c.execute(
        "SELECT id,lat,lng,address,parked_at FROM parking_spots WHERE found_at IS NULL ORDER BY id DESC LIMIT 1"
    ).fetchone()
    c.close()
    if not row:
        return {"found": False}
    return {
        "found": True, "id": row[0],
        "lat": row[1], "lng": row[2],
        "address": row[3], "parked_at": row[4],
        "maps_link": _maps_link(row[1], row[2])
    }


@app.post("/api/parking/{parking_id}/found")
def mark_car_found(parking_id: int):
    """Mark car as found (user retrieved it)."""
    c = db()
    c.execute("UPDATE parking_spots SET found_at=? WHERE id=?",
              (datetime.now().isoformat(), parking_id))
    c.commit(); c.close()
    return {"ok": True}


@app.get("/api/places/recent")
def recent_places(limit: int = 20):
    """Return recently visited places."""
    c = db()
    rows = c.execute(
        "SELECT lat,lng,name,category,arrived_at,duration_min FROM place_history ORDER BY arrived_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    c.close()
    return [{"lat":r[0],"lng":r[1],"name":r[2],"category":r[3],
             "arrived_at":r[4],"duration_min":r[5]} for r in rows]


@app.get("/api/location/context")
async def location_context():
    """
    依最新 GPS 判斷主人現在在哪裡（home/office/gym/other/unknown），
    並給出阿福的主動問候文字，前端 GPS 抵達已知地點時呼叫。
    """
    c = db()
    latest = c.execute("SELECT lat,lng,ts FROM location_log ORDER BY id DESC LIMIT 1").fetchone()
    if not latest:
        c.close()
        return {"context": "unknown", "name": "", "greeting": ""}

    lat, lng, ts = latest
    known = c.execute("SELECT name,place_type,lat,lng FROM known_places").fetchall()
    context_type = "unknown"
    context_name = ""
    for kp_name, kp_type, kp_lat, kp_lng in known:
        d = _haversine(lat, lng, kp_lat, kp_lng)
        if d < 300:
            context_type = kp_type
            context_name = kp_name
            break

    # 確認今日是否已問候過（防重複）
    today = datetime.now().strftime("%Y-%m-%d")
    already = c.execute(
        "SELECT COUNT(*) FROM memories WHERE category='context_greeted' AND key=? AND value LIKE ?",
        (context_type, f"{today}%")
    ).fetchone()[0]

    greeting = ""
    if not already and context_type != "unknown":
        hour = datetime.now().hour
        if context_type == "office" and 6 <= hour < 21:
            # 取今日行程
            events = c.execute(
                "SELECT title,event_time FROM calendar_events WHERE event_date=? ORDER BY event_time LIMIT 2",
                (today,)
            ).fetchall()
            todos = c.execute(
                "SELECT title FROM todos WHERE status='pending' ORDER BY ts DESC LIMIT 2"
            ).fetchall()
            ev_str = "，".join(f"{e[1] or ''}「{e[0]}」" for e in events) if events else ""
            todo_str = "、".join(t[0][:12] for t in todos) if todos else ""
            greeting = f"主人，您開始了一天重要的工作。"
            if ev_str:
                greeting += f"今天行程：{ev_str}。"
            if todo_str:
                greeting += f"待辦還有：{todo_str}。"
            greeting += "有需要我的話隨時說，我切換成辦公室模式為您服務。"
        elif context_type == "home" and (hour >= 18 or hour < 8):
            greeting = f"主人，您到家了，辛苦了一天。有需要我的地方隨時說，今晚好好休息。"
        elif context_type == "gym":
            greeting = f"主人，您到健身房了。記得暖身，我在旁邊待機。"

        if greeting:
            c.execute(
                "INSERT INTO memories (category,key,value,ts) VALUES (?,?,?,?)",
                ("context_greeted", context_type, f"{today} {datetime.now().strftime('%H:%M')}", datetime.now().isoformat())
            )
            c.commit()

    # ── 自動打卡：到公司 → 補上班記錄；離家時間晚 → 補下班記錄 ──────────────
    checkin_recorded = False
    checkout_recorded = False
    now_iso = datetime.now().isoformat()

    if context_type == "office":
        row = c.execute("SELECT id, check_in FROM attendance WHERE date=?", (today,)).fetchone()
        if not row or not row[1]:
            # 今天還沒有上班打卡 → 自動打卡
            if row:
                c.execute("UPDATE attendance SET check_in=?,lat_in=?,lng_in=?,type=?,verified=1 WHERE id=?",
                          (now_iso, lat, lng, "office", row[0]))
            else:
                c.execute("INSERT INTO attendance (date,check_in,lat_in,lng_in,type,verified) VALUES (?,?,?,?,?,1)",
                          (today, now_iso, lat, lng, "office"))
            checkin_recorded = True
            if greeting:
                greeting += f"\n\n已為您記錄今日上班時間：{now_iso[11:16]}。此記錄含 GPS 座標，如日後人資對出勤有疑問，您可出示這份記錄。"
            c.commit()

    elif context_type == "home":
        # 回到家 → 看今天有沒有下班記錄，沒有就補上
        row = c.execute("SELECT id,check_in,check_out FROM attendance WHERE date=?", (today,)).fetchone()
        if row and row[1] and not row[2]:
            try:
                import datetime as _dt2
                ci = _dt2.datetime.fromisoformat(row[1])
                dur = int((_dt2.datetime.fromisoformat(now_iso) - ci).total_seconds() / 60)
            except Exception:
                dur = None
            c.execute("UPDATE attendance SET check_out=?,lat_out=?,lng_out=?,duration_min=?,verified=1 WHERE id=?",
                      (now_iso, lat, lng, dur, row[0]))
            checkout_recorded = True
            dur_str = f"，今日在公司共 {dur//60} 小時 {dur%60} 分鐘" if dur else ""
            if greeting:
                greeting += f"\n\n已記錄今日下班時間：{now_iso[11:16]}{dur_str}。記錄已存檔，含 GPS 驗證。"
            c.commit()

    c.close()
    return {
        "context": context_type,
        "name": context_name,
        "lat": lat, "lng": lng,
        "greeting": greeting,
        "checkin_recorded": checkin_recorded,
        "checkout_recorded": checkout_recorded,
    }


@app.post("/api/items/save")
async def save_item_location(request: Request):
    """Save where an item was placed."""
    data = await request.json()
    c = db()
    # Get current location from last GPS point
    last = c.execute("SELECT lat,lng FROM location_log ORDER BY id DESC LIMIT 1").fetchone()
    lat, lng, place = (last[0], last[1], "") if last else (None, None, "")
    if lat:
        place = await asyncio.get_event_loop().run_in_executor(
            None, _reverse_geocode_approx, lat, lng)
    c.execute(
        "INSERT INTO item_locations (item,location_desc,lat,lng,place_name,noted_at) VALUES (?,?,?,?,?,?)",
        (data.get("item",""), data.get("location_desc",""), lat, lng, place, datetime.now().isoformat())
    )
    c.commit(); c.close()
    return {"ok": True}


@app.get("/api/items/find")
def find_item(q: str = ""):
    """Find where an item was placed."""
    c = db()
    kw = f"%{q}%"
    rows = c.execute(
        "SELECT item,location_desc,place_name,lat,lng,noted_at FROM item_locations "
        "WHERE (item LIKE ? OR location_desc LIKE ?) AND found_at IS NULL ORDER BY noted_at DESC LIMIT 5",
        (kw, kw)
    ).fetchall()
    c.close()
    return [{"item":r[0],"desc":r[1],"place":r[2],"lat":r[3],"lng":r[4],
             "noted_at":r[5],"maps_link":_maps_link(r[3],r[4]) if r[3] else ""} for r in rows]


@app.post("/api/mac/index")
async def mac_index(request: Request):
    """Receive file index from Mac agent. Body: {files: [{path,name,size,modified,kind}]}"""
    data = await request.json()
    files = data.get("files", [])
    c = db()
    now = datetime.now().isoformat()
    for f in files:
        c.execute(
            """INSERT OR REPLACE INTO mac_files_index (path,name,size,modified,kind,indexed_at)
               VALUES (?,?,?,?,?,?)""",
            (f.get("path",""), f.get("name",""), f.get("size",0),
             f.get("modified",""), f.get("kind",""), now)
        )
    c.commit()
    total = c.execute("SELECT COUNT(*) FROM mac_files_index").fetchone()[0]
    c.close()
    return {"ok": True, "indexed": len(files), "total": total}


@app.get("/api/mac/status")
def mac_status():
    c = db()
    row = c.execute("SELECT COUNT(*), MAX(indexed_at) FROM mac_files_index").fetchone()
    c.close()
    return {"count": row[0], "last_indexed": row[1]}


_mac_connections: dict = {}  # mac_id → WebSocket

@app.websocket("/api/ws/mac/{mac_id}")
async def mac_ws(ws: WebSocket, mac_id: str):
    """Persistent WebSocket for Mac agent — allows Alfred to push commands to Mac."""
    await ws.accept()
    _mac_connections[mac_id] = ws
    try:
        while True:
            msg = await ws.receive_text()
            data = json.loads(msg)
            # Mac agent sends results back after Alfred pushes a command
            if data.get("type") == "file_result":
                # Store file result in memory for Alfred to pick up
                c = db()
                c.execute("INSERT INTO memories (category,key,value,ts) VALUES (?,?,?,?)",
                    ("mac_response", data.get("request_id",""), json.dumps(data), datetime.now().isoformat()))
                c.commit(); c.close()
            elif data.get("type") == "index":
                # Mac agent pushing file index update
                files = data.get("files", [])
                c = db(); now = datetime.now().isoformat()
                for f in files:
                    c.execute("INSERT OR REPLACE INTO mac_files_index (path,name,size,modified,kind,indexed_at) VALUES (?,?,?,?,?,?)",
                        (f.get("path",""), f.get("name",""), f.get("size",0), f.get("modified",""), f.get("kind",""), now))
                c.commit(); c.close()
    except Exception:
        pass
    finally:
        _mac_connections.pop(mac_id, None)


@app.post("/api/mac/command")
async def mac_command(request: Request):
    """Push a command to connected Mac agent."""
    data = await request.json()
    mac_id = data.get("mac_id", "default")
    if mac_id not in _mac_connections:
        return {"ok": False, "error": "Mac 未連線"}
    import uuid
    request_id = str(uuid.uuid4())[:8]
    await _mac_connections[mac_id].send_text(json.dumps({
        "request_id": request_id, **data
    }))
    return {"ok": True, "request_id": request_id}


@app.get("/api/mac/connected")
def mac_connected():
    return {"connected": list(_mac_connections.keys())}


@app.get("/api/mac/agent.py")
def download_mac_agent():
    """Serve the Mac agent Python script as a download."""
    host = os.getenv("SERVER_HOST", "")
    script = f'''#!/usr/bin/env python3
"""
Alfred Mac Agent — 掃描本機檔案並上傳索引到阿福
安裝：python3 alfred_agent.py
排程：launchctl 或 cron 每小時執行一次
"""
import os, json, urllib.request, datetime

ALFRED_URL = "https://{host}/alfred/api/mac/index"
SCAN_DIRS = [
    os.path.expanduser("~/Desktop"),
    os.path.expanduser("~/Documents"),
    os.path.expanduser("~/Downloads"),
]
MAX_FILES = 2000
EXTENSIONS = {{
    ".pdf","doc","docx",".xlsx",".xls",".pptx",".ppt",
    ".txt",".md",".pages",".numbers",".key",
    ".jpg",".jpeg",".png",".gif",".mp4",".mov",
    ".zip",".dmg",".app"
}}

def scan():
    files = []
    for base in SCAN_DIRS:
        if not os.path.exists(base):
            continue
        for root, dirs, fnames in os.walk(base):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for fname in fnames:
                if fname.startswith("."):
                    continue
                ext = os.path.splitext(fname)[1].lower()
                if ext not in EXTENSIONS and len(files) > 200:
                    continue
                path = os.path.join(root, fname)
                try:
                    st = os.stat(path)
                    files.append({{
                        "path": path,
                        "name": fname,
                        "size": st.st_size,
                        "modified": datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d"),
                        "kind": ext.lstrip(".").upper() or "檔案"
                    }})
                except Exception:
                    pass
                if len(files) >= MAX_FILES:
                    break
    return files

def push(files):
    body = json.dumps({{"files": files}}).encode()
    req = urllib.request.Request(ALFRED_URL, data=body,
        headers={{"Content-Type": "application/json"}}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

if __name__ == "__main__":
    print(f"[Alfred Agent] 掃描中...")
    files = scan()
    print(f"[Alfred Agent] 找到 {{len(files)}} 個檔案，上傳索引...")
    result = push(files)
    print(f"[Alfred Agent] 完成！阿福共收錄 {{result.get('total', '?')}} 個 Mac 檔案")
'''
    return Response(content=script, media_type="text/plain",
                    headers={"Content-Disposition": "attachment; filename=alfred_agent.py"})


@app.post("/api/contacts/import")
async def import_contacts(file: UploadFile = File(...)):
    """Import Apple Contacts VCF file and index into SQLite."""
    content = (await file.read()).decode("utf-8", errors="replace")
    contacts = _parse_vcf(content)
    if not contacts:
        return {"ok": False, "error": "無法解析 VCF，請確認格式正確"}
    c = db()
    now = datetime.now().isoformat()
    for ct in contacts:
        c.execute(
            """INSERT OR REPLACE INTO contacts_index (id,name,phones,emails,org,notes,indexed_at)
               VALUES (?,?,?,?,?,?,?)""",
            (ct["id"], ct["name"], ct["phones"], ct["emails"], ct["org"], ct["notes"], now)
        )
    c.commit()
    total = c.execute("SELECT COUNT(*) FROM contacts_index").fetchone()[0]
    c.close()
    return {"ok": True, "imported": len(contacts), "total": total}


@app.get("/api/contacts/search")
def contacts_search(q: str = "", limit: int = 10):
    """Search contacts index."""
    c = db()
    kw = f"%{q}%"
    rows = c.execute(
        "SELECT name,phones,emails,org FROM contacts_index "
        "WHERE name LIKE ? OR phones LIKE ? OR emails LIKE ? OR org LIKE ? ORDER BY name LIMIT ?",
        (kw, kw, kw, kw, limit)
    ).fetchall()
    c.close()
    return [{"name": r[0], "phones": r[1], "emails": r[2], "org": r[3]} for r in rows]


@app.get("/api/contacts/count")
def contacts_count():
    c = db()
    n = c.execute("SELECT COUNT(*) FROM contacts_index").fetchone()[0]
    c.close()
    return {"count": n}


@app.post("/api/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """Whisper transcription for meeting recordings."""
    import openai as _oai
    _oai.api_key = os.getenv("OPENAI_API_KEY", "")
    audio_bytes = await file.read()
    # Write to temp file (Whisper needs a file-like object with name)
    import tempfile, pathlib
    suffix = pathlib.Path(file.filename or "audio.webm").suffix or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name
    try:
        with open(tmp_path, "rb") as f:
            result = _oai.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                language="zh",
                response_format="text"
            )
        return {"transcript": result}
    finally:
        import os as _os; _os.unlink(tmp_path)


_SENSITIVE_PATTERNS = [
    r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',   # 信用卡
    r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b',                # SSN 格式
    r'password|密碼|帳號密碼|PIN碼',
    r'[\w.+-]+@[\w-]+\.[a-z]{2,}',                     # email (保留姓名，濾 email)
]

def _filter_sensitive(text: str) -> str:
    import re
    for pat in _SENSITIVE_PATTERNS:
        text = re.sub(pat, '[已過濾]', text, flags=re.IGNORECASE)
    return text


# ── Family Location Sharing ─────────────────────────────────────────────────

import secrets as _secrets

def _family_avatar_colors():
    return ['#c9a84c','#4caf9a','#af4c7a','#4c7aaf','#af7a4c','#7aaf4c','#9a4caf']

@app.post("/api/family/member")
async def family_add_member(request: Request):
    """新增家庭成員（主帳號用）。"""
    data = await request.json()
    name = data.get("name", "").strip()
    relation = data.get("relation", "family")
    if not name:
        return {"ok": False, "error": "需要名字"}
    c = db()
    existing = c.execute("SELECT COUNT(*) FROM family_members").fetchone()[0]
    color = _family_avatar_colors()[existing % len(_family_avatar_colors())]
    c.execute(
        "INSERT INTO family_members (name,relation,avatar_color,noted_at) VALUES (?,?,?,?)",
        (name, relation, color, datetime.now().isoformat())
    )
    c.commit()
    mid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    c.close()
    return {"ok": True, "id": mid, "name": name, "relation": relation, "color": color}


@app.post("/api/family/invite/{member_id}")
async def family_invite(member_id: int):
    """為指定家庭成員產生邀請 token（有效期 7 天）。"""
    import datetime as _dt
    c = db()
    row = c.execute("SELECT name FROM family_members WHERE id=?", (member_id,)).fetchone()
    if not row:
        c.close(); return {"ok": False, "error": "找不到成員"}
    token = _secrets.token_urlsafe(20)
    expires = (_dt.datetime.now() + _dt.timedelta(days=7)).isoformat()
    c.execute("DELETE FROM family_invites WHERE member_id=?", (member_id,))
    c.execute(
        "INSERT INTO family_invites (token,member_id,created_at,expires_at) VALUES (?,?,?,?)",
        (token, member_id, datetime.now().isoformat(), expires)
    )
    c.commit(); c.close()
    return {"ok": True, "token": token, "member_id": member_id, "name": row[0],
            "expires_at": expires, "invite_path": f"/alfred/join?t={token}"}


@app.get("/api/family/join/{token}")
async def family_join_info(token: str):
    """家人掃 QR code 時取得邀請資訊。"""
    c = db()
    row = c.execute(
        "SELECT fi.member_id, fi.expires_at, fi.used_at, fm.name, fm.relation "
        "FROM family_invites fi JOIN family_members fm ON fi.member_id=fm.id "
        "WHERE fi.token=?", (token,)
    ).fetchone()
    c.close()
    if not row:
        return {"ok": False, "error": "邀請連結無效"}
    if row[2]:
        return {"ok": False, "error": "邀請連結已使用過"}
    return {"ok": True, "member_id": row[0], "name": row[3],
            "relation": row[4], "expires_at": row[1], "token": token}


@app.post("/api/family/activate")
async def family_activate(request: Request):
    """家人裝置用邀請 token 完成配對，取得 device_token。"""
    data = await request.json()
    invite_token = data.get("token", "").strip()
    c = db()
    row = c.execute(
        "SELECT fi.member_id, fi.expires_at, fi.used_at, fm.name "
        "FROM family_invites fi JOIN family_members fm ON fi.member_id=fm.id "
        "WHERE fi.token=?", (invite_token,)
    ).fetchone()
    if not row:
        c.close(); return {"ok": False, "error": "邀請無效"}
    if row[2]:
        c.close(); return {"ok": False, "error": "邀請已被使用"}
    member_id, _, _, name = row
    device_token = _secrets.token_urlsafe(32)
    now = datetime.now().isoformat()
    c.execute("UPDATE family_members SET device_token=? WHERE id=?", (device_token, member_id))
    c.execute("UPDATE family_invites SET used_at=? WHERE token=?", (now, invite_token))
    c.commit(); c.close()
    return {"ok": True, "member_id": member_id, "name": name,
            "device_token": device_token}


@app.post("/api/family/location")
async def family_location_update(request: Request):
    """家人裝置上報 GPS（用 device_token 認證）。"""
    data = await request.json()
    device_token = data.get("device_token", "")
    lat = data.get("lat")
    lng = data.get("lng")
    battery = data.get("battery", -1)
    if not device_token or lat is None or lng is None:
        return {"ok": False, "error": "missing fields"}

    c = db()
    row = c.execute(
        "SELECT id, name FROM family_members WHERE device_token=?", (device_token,)
    ).fetchone()
    if not row:
        c.close(); return {"ok": False, "error": "device not registered"}
    member_id, member_name = row

    # 反向地理編碼
    addr = await asyncio.get_event_loop().run_in_executor(
        None, _reverse_geocode_approx, lat, lng)

    now_iso = datetime.now().isoformat()

    # 判斷是否在已知地點
    known = c.execute("SELECT name,place_type,lat,lng FROM known_places").fetchall()
    at_known = None
    for kp_name, kp_type, kp_lat, kp_lng in known:
        d = _haversine(lat, lng, kp_lat, kp_lng)
        if d < 300:
            at_known = (kp_name, kp_type)
            break

    # 查上次狀態判斷是否剛到達
    prev = c.execute(
        "SELECT address FROM family_members WHERE id=?", (member_id,)
    ).fetchone()
    was_home = c.execute(
        "SELECT is_home FROM family_members WHERE id=?", (member_id,)
    ).fetchone()[0]
    is_home_now = 1 if (at_known and at_known[1] == "home") else 0

    # 更新位置
    c.execute(
        "UPDATE family_members SET last_lat=?,last_lng=?,last_address=?,last_seen=?,battery=?,is_home=? WHERE id=?",
        (lat, lng, addr, now_iso, battery, is_home_now, member_id)
    )

    # 記錄到 log
    c.execute(
        "INSERT INTO family_location_log (member_id,lat,lng,address,speed,battery,ts) VALUES (?,?,?,?,?,?,?)",
        (member_id, lat, lng, addr, data.get("speed", 0), battery, now_iso)
    )

    # 到達通知觸發：剛到達已知地點 → 存 pending notification
    notification_msg = ""
    if at_known and not was_home and is_home_now:
        notification_msg = f"{member_name} 到家了 ✅ （{now_iso[11:16]}）"
        c.execute("INSERT INTO memories (category,key,value,ts) VALUES (?,?,?,?)",
                  ("family_arrival", member_name, notification_msg, now_iso))
    elif at_known and at_known[1] != "home":
        # 到其他已知地點也記錄
        last_arr = c.execute(
            "SELECT value FROM memories WHERE category='family_arrival' AND key=? ORDER BY ts DESC LIMIT 1",
            (member_name,)
        ).fetchone()
        if not last_arr or last_arr[0][:10] != now_iso[:10]:
            notification_msg = f"{member_name} 到了{at_known[0]}（{now_iso[11:16]}）"
            c.execute("INSERT INTO memories (category,key,value,ts) VALUES (?,?,?,?)",
                      ("family_arrival", member_name, notification_msg, now_iso))

    c.commit(); c.close()
    return {"ok": True, "member_id": member_id, "address": addr,
            "at_known": at_known[0] if at_known else None,
            "notification": notification_msg}


@app.get("/api/family/members")
def family_members_list():
    """取得所有家庭成員與最新位置。"""
    c = db()
    rows = c.execute(
        "SELECT id,name,relation,avatar_color,last_lat,last_lng,last_address,"
        "last_seen,battery,is_home FROM family_members ORDER BY id"
    ).fetchall()
    c.close()
    return [{"id":r[0],"name":r[1],"relation":r[2],"color":r[3],
             "lat":r[4],"lng":r[5],"address":r[6],"last_seen":r[7],
             "battery":r[8],"is_home":bool(r[9])} for r in rows]


@app.get("/api/family/arrivals")
def family_arrivals(limit: int = 20):
    """最近的家人到達通知。"""
    c = db()
    rows = c.execute(
        "SELECT key, value, ts FROM memories WHERE category='family_arrival' "
        "ORDER BY ts DESC LIMIT ?", (limit,)
    ).fetchall()
    c.close()
    return [{"name":r[0],"event":r[1],"ts":r[2]} for r in rows]


# ── Family Guardian: 去暗偵測 + 位置不符 + 智慧警報升級 ─────────────────────

# 主人「在線」的判斷標準
def _owner_is_active(minutes: int = 10) -> bool:
    """主人 N 分鐘內有與 Alfred 互動 → 判定手機在手邊。"""
    c = db()
    cutoff = (datetime.now() - __import__("datetime").timedelta(minutes=minutes)).isoformat()
    row = c.execute(
        "SELECT COUNT(*) FROM memories WHERE category='owner_active' AND ts > ?", (cutoff,)
    ).fetchone()
    c.close()
    return (row[0] > 0) if row else False

def _record_owner_active():
    """每次主人與 Alfred 互動時呼叫，記錄存活心跳。"""
    c = db()
    c.execute("INSERT INTO memories (category,key,value,ts) VALUES (?,?,?,?)",
              ("owner_active", "ping", "1", datetime.now().isoformat()))
    # 只保留最近 50 筆
    c.execute("DELETE FROM memories WHERE category='owner_active' AND id NOT IN "
              "(SELECT id FROM memories WHERE category='owner_active' ORDER BY ts DESC LIMIT 50)")
    c.commit(); c.close()


def _create_alert(member_id: int, alert_type: str, message: str, severity: str = "warning") -> int:
    """建立新警報，若同類警報最近 30 分鐘內已存在則不重複。"""
    c = db()
    cutoff = (datetime.now() - __import__("datetime").timedelta(minutes=30)).isoformat()
    dup = c.execute(
        "SELECT id FROM family_alerts WHERE member_id=? AND alert_type=? "
        "AND acknowledged_at IS NULL AND created_at > ?",
        (member_id, alert_type, cutoff)
    ).fetchone()
    if dup:
        c.close(); return dup[0]
    c.execute(
        "INSERT INTO family_alerts (member_id,alert_type,message,severity,created_at,escalation_level) "
        "VALUES (?,?,?,?,?,0)",
        (member_id, alert_type, message, severity, datetime.now().isoformat())
    )
    c.commit()
    aid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    c.close()
    return aid


async def _escalate_alert(alert_id: int):
    """根據升級等級選擇通知方式：0=等待, 1=LINE/TG, 2=電話。"""
    c = db()
    row = c.execute(
        "SELECT member_id,message,severity,escalation_level,created_at,acknowledged_at "
        "FROM family_alerts WHERE id=?", (alert_id,)
    ).fetchone()
    if not row or row[5]:  # 已確認 → 不升級
        c.close(); return
    member_id, msg, severity, level, created_at, _ = row

    elapsed = (datetime.now() - __import__("datetime").datetime.fromisoformat(created_at)).total_seconds()

    if level == 0:
        # 等 3 分鐘看主人有沒有主動開 App
        if elapsed < 180:
            c.close(); return
        level = 1

    if level == 1:
        # 升級到 LINE / Telegram
        alert_text = f"主人，阿福有件事想跟您說一下。\n\n{msg}\n\n方便的話回覆「收到」讓阿福知道您看到了。"
        sent = False
        if line_service and LINE_CONFIGURED:
            try:
                c2 = db()
                owner_id = c2.execute(
                    "SELECT value FROM memories WHERE category='line' AND key='owner_user_id' LIMIT 1"
                ).fetchone()
                c2.close()
                if owner_id:
                    line_service.send_message(owner_id[0], alert_text)
                    sent = True
            except Exception: pass
        if not sent and TG_CONFIGURED and telegram_service:
            try:
                c2 = db()
                chat_id = c2.execute(
                    "SELECT value FROM memories WHERE category='telegram' AND key='owner_chat_id' LIMIT 1"
                ).fetchone()
                c2.close()
                if chat_id:
                    telegram_service.send_message(chat_id[0], alert_text)
                    sent = True
            except Exception: pass

        c.execute(
            "UPDATE family_alerts SET escalation_level=1, last_escalated_at=? WHERE id=?",
            (datetime.now().isoformat(), alert_id)
        )
        c.commit()

    c.close()


async def guardian_scan():
    """
    背景定期掃描：
    1. 偵測家人 GPS 去暗（>10 分鐘無更新）
    2. 偵測位置 vs 申報計畫不符（>500m）
    3. 升級未確認的警報
    """
    c = db()
    members = c.execute(
        "SELECT id,name,relation,last_lat,last_lng,last_address,last_seen,"
        "planned_destination,planned_eta,device_token,battery "
        "FROM family_members WHERE device_token IS NOT NULL"
    ).fetchall()
    c.close()

    now = datetime.now()
    for m in members:
        mid, name, rel, lat, lng, addr, last_seen, planned, eta, dtok, bat = m
        if not last_seen:
            continue

        try:
            last_dt = __import__("datetime").datetime.fromisoformat(last_seen)
        except Exception:
            continue
        gone_mins = (now - last_dt).total_seconds() / 60

        # ── 去暗警報 ──────────────────────────────────────────────────────
        if gone_mins > 10:
            severity = "critical" if gone_mins > 30 else "warning"
            low_bat = bat is not None and bat >= 0 and bat < 10
            msg = (
                f"{name}（{rel}）已有 {int(gone_mins)} 分鐘沒有傳回位置。"
                f"最後一次在：{addr or '未知'}（{last_seen[11:16]}）。"
                f"{'手機電量很低，可能是沒電了。' if low_bat else '可能是暫時沒有訊號，或定位暫停了。'}"
            )
            if planned:
                msg += f"她說要去「{planned}」。"
            msg += " 方便的話，輕鬆問她一聲就好。"
            aid = _create_alert(mid, "gone_dark", msg, severity)
            if not _owner_is_active(5):
                asyncio.create_task(_escalate_alert(aid))

        # ── 位置不符警報 ──────────────────────────────────────────────────
        elif planned and lat and gone_mins < 10:
            planned_lower = planned.lower()
            addr_lower = (addr or "").lower()
            keywords_match = any(kw in addr_lower for kw in planned_lower.split()[:3])
            if not keywords_match and len(planned) > 3:
                msg = (
                    f"{name} 說要去「{planned}」，"
                    f"不過目前定位在：{addr or '未知地點'}，"
                    f"跟原本說的地方有些距離。"
                    f"可能是臨時改了計畫，或者在路上。"
                    f"您方便的話確認一下就好。"
                )
                _create_alert(mid, "location_mismatch", msg, "warning")

    # ── 升級未確認的舊警報 ────────────────────────────────────────────────
    c = db()
    pending = c.execute(
        "SELECT id, created_at, escalation_level FROM family_alerts "
        "WHERE acknowledged_at IS NULL AND escalation_level < 2 "
        "ORDER BY created_at ASC LIMIT 10"
    ).fetchall()
    c.close()
    for aid, created_at, level in pending:
        try:
            elapsed = (now - __import__("datetime").datetime.fromisoformat(created_at)).total_seconds()
            if elapsed > 180:  # 3 分鐘後升級
                asyncio.create_task(_escalate_alert(aid))
        except Exception:
            pass


@app.get("/api/family/alerts")
def family_alerts_list():
    """取得未確認的家庭警報（主人開 App 時呼叫）。"""
    c = db()
    rows = c.execute(
        "SELECT fa.id, fm.name, fm.relation, fa.alert_type, fa.message, "
        "fa.severity, fa.created_at, fa.escalation_level "
        "FROM family_alerts fa JOIN family_members fm ON fa.member_id=fm.id "
        "WHERE fa.acknowledged_at IS NULL "
        "ORDER BY fa.severity DESC, fa.created_at DESC LIMIT 20"
    ).fetchall()
    c.close()
    return [{"id":r[0],"name":r[1],"relation":r[2],"type":r[3],
             "message":r[4],"severity":r[5],"created_at":r[6],"level":r[7]} for r in rows]


@app.post("/api/family/alerts/{alert_id}/ack")
def acknowledge_alert(alert_id: int):
    """主人確認看到警報。"""
    c = db()
    c.execute("UPDATE family_alerts SET acknowledged_at=? WHERE id=?",
              (datetime.now().isoformat(), alert_id))
    c.commit(); c.close()
    return {"ok": True}


@app.post("/api/family/plan")
async def set_family_plan(request: Request):
    """
    記錄家人申報的去處計畫。
    例：女兒說「我要去圖書館」→ 前端或對話中觸發。
    """
    data = await request.json()
    member_id = data.get("member_id")
    destination = data.get("destination", "").strip()
    eta = data.get("eta", "").strip()
    c = db()
    c.execute(
        "UPDATE family_members SET planned_destination=?, planned_eta=? WHERE id=?",
        (destination, eta, member_id)
    )
    c.commit(); c.close()
    return {"ok": True}


# 背景 guardian 掃描任務（每 5 分鐘）
async def _guardian_loop():
    while True:
        await asyncio.sleep(300)
        try:
            await guardian_scan()
        except Exception as e:
            print(f"[guardian] error: {e}")


# ── Ambient "阿福聆聽中" mode ────────────────────────────────────────────────

@app.post("/api/ambient/start")
async def ambient_start(request: Request):
    body = await request.json()
    label = body.get("label", f"辦公記錄 {datetime.now().strftime('%m/%d')}")
    now = datetime.now().isoformat()
    c = db()
    c.execute(
        "INSERT INTO ambient_sessions (date,label,status,started_at) VALUES (?,?,?,?)",
        (datetime.now().strftime("%Y-%m-%d"), label, "recording", now)
    )
    c.commit()
    session_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    c.close()
    return {"ok": True, "session_id": session_id, "label": label, "started_at": now}


@app.post("/api/ambient/chunk/{session_id}")
async def ambient_chunk(session_id: int, file: UploadFile = File(...)):
    """接收一段音頻，轉錄並過濾敏感資訊，存入 ambient_chunks。"""
    import openai as _oai, tempfile, pathlib, os as _os
    _oai.api_key = os.getenv("OPENAI_API_KEY", "")

    audio_bytes = await file.read()
    if not audio_bytes or len(audio_bytes) < 1000:
        return {"ok": True, "skipped": True, "reason": "too short"}

    suffix = pathlib.Path(file.filename or "chunk.webm").suffix or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes); tmp_path = tmp.name

    raw = ""
    try:
        with open(tmp_path, "rb") as f:
            result = _oai.audio.transcriptions.create(
                model="whisper-1", file=f,
                language="zh", response_format="text"
            )
        raw = result if isinstance(result, str) else getattr(result, "text", "")
    except Exception as e:
        raw = f"[轉錄失敗：{e}]"
    finally:
        _os.unlink(tmp_path)

    filtered = _filter_sensitive(raw)

    c = db()
    c.execute(
        "SELECT COALESCE(MAX(seq),0)+1 FROM ambient_chunks WHERE session_id=?", (session_id,)
    )
    seq = c.fetchone()[0]
    c.execute(
        "INSERT INTO ambient_chunks (session_id,seq,raw_transcript,filtered_transcript,ts) VALUES (?,?,?,?,?)",
        (session_id, seq, raw, filtered, datetime.now().isoformat())
    )
    c.commit(); c.close()

    return {"ok": True, "session_id": session_id, "seq": seq,
            "chars": len(raw), "filtered": filtered != raw}


@app.post("/api/ambient/stop/{session_id}")
async def ambient_stop(session_id: int):
    """停止記錄，用 Claude 整理今日動態報告。"""
    c = db()
    session = c.execute(
        "SELECT label, started_at, date FROM ambient_sessions WHERE id=?", (session_id,)
    ).fetchone()
    if not session:
        c.close(); return {"ok": False, "error": "session not found"}

    label, started_at, date = session
    chunks = c.execute(
        "SELECT seq, filtered_transcript, ts FROM ambient_chunks "
        "WHERE session_id=? ORDER BY seq ASC",
        (session_id,)
    ).fetchall()

    if not chunks:
        c.execute("UPDATE ambient_sessions SET status='stopped',stopped_at=? WHERE id=?",
                  (datetime.now().isoformat(), session_id))
        c.commit(); c.close()
        return {"ok": True, "session_id": session_id, "report": "這段時間沒有錄到內容。"}

    # 組合所有逐字稿，加上時間戳
    timeline_parts = []
    for seq, text, ts in chunks:
        t = ts[11:16] if ts else ""
        if text.strip():
            timeline_parts.append(f"[{t}] {text.strip()}")
    full_text = "\n".join(timeline_parts)

    # Claude 整理報告
    now_str = datetime.now().strftime("%Y/%m/%d %H:%M")
    prompt = f"""以下是主人今日辦公期間的對話/會議語音記錄（已過濾敏感資訊），時間從 {started_at[11:16]} 到 {now_str}，共 {len(chunks)} 段。

請整理成「今日動態綜合報告」，格式如下（繁體中文，語氣像資深管家做的日誌，簡潔有力）：

## 📋 {date} 辦公記錄｜{label}

### 一、主要話題與討論
（條列今天談過的主題，每項一句話）

### 二、決策事項
（列出今天做出的決定，無則寫「無明確決策」）

### 三、待辦 / 承諾追蹤
（格式：- 【誰】要做什麼 by 何時。若不確定就寫大約時間。）

### 四、重要提及的人名 / 公司
（今天對話中出現的人、組織、客戶名稱）

### 五、阿福備注
（阿福認為主人需要特別留意的事、尚未跟進的問題、或建議採取的行動）

---
語音記錄：
{full_text[:12000]}"""

    report = _simple_chat(prompt, max_tokens=2000)

    now_iso = datetime.now().isoformat()
    c.execute(
        "UPDATE ambient_sessions SET status='stopped', stopped_at=?, report=? WHERE id=?",
        (now_iso, report, session_id)
    )

    # 抽 action items → 存 todos
    for line in report.split("\n"):
        l = line.strip()
        if l.startswith("- 【") and "】" in l:
            title = l[2:]  # strip "- "
            c.execute(
                "INSERT INTO todos (title,due_date,status,ts) VALUES (?,?,?,?)",
                (f"[辦公記錄] {title}", "", "pending", now_iso)
            )

    # 儲存一份 meeting_notes 以便日後查詢
    c.execute(
        "INSERT INTO meeting_notes (title,transcript,summary,action_items,ts) VALUES (?,?,?,?,?)",
        (f"{label} ({date})", full_text[:20000], report, "", now_iso)
    )
    c.commit(); c.close()

    return {"ok": True, "session_id": session_id, "report": report,
            "chunks": len(chunks), "stopped_at": now_iso}


@app.get("/api/ambient/status/{session_id}")
def ambient_status(session_id: int):
    c = db()
    s = c.execute(
        "SELECT id,label,status,started_at,stopped_at FROM ambient_sessions WHERE id=?", (session_id,)
    ).fetchone()
    if not s:
        c.close(); return {"error": "not found"}
    count = c.execute("SELECT COUNT(*) FROM ambient_chunks WHERE session_id=?", (session_id,)).fetchone()[0]
    c.close()
    return {"id": s[0], "label": s[1], "status": s[2],
            "started_at": s[3], "stopped_at": s[4], "chunks": count}


@app.get("/api/ambient/sessions")
def ambient_sessions(limit: int = 20):
    c = db()
    rows = c.execute(
        "SELECT id,date,label,status,started_at,stopped_at FROM ambient_sessions ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    c.close()
    return [{"id": r[0], "date": r[1], "label": r[2], "status": r[3],
             "started_at": r[4], "stopped_at": r[5]} for r in rows]


@app.post("/api/meeting-notes")
async def generate_meeting_notes(req: dict):
    """Generate meeting notes from transcript using Claude."""
    transcript = req.get("transcript", "")
    title = req.get("title", f"會議記錄 {datetime.now().strftime('%m/%d %H:%M')}")
    if not transcript:
        return {"error": "no transcript"}

    prompt = f"""以下是一段會議逐字稿，請整理成：
1. 【摘要】3-5句話說明會議內容
2. 【決議事項】條列所有決定的事
3. 【待辦行動】條列誰要做什麼（格式：- 誰：做什麼）

逐字稿：
{transcript}

用繁體中文，簡潔有力。"""

    summary = _simple_chat(prompt, max_tokens=1024)

    # Extract action items
    action_items = ""
    for line in summary.split("\n"):
        if line.strip().startswith("- ") and "：" in line:
            action_items += line.strip() + "\n"

    # Save to DB
    c = db()
    c.execute(
        "INSERT INTO meeting_notes (title,transcript,summary,action_items,ts) VALUES (?,?,?,?,?)",
        (title, transcript, summary, action_items.strip(), datetime.now().isoformat())
    )
    c.commit(); c.close()

    # Generate spoken summary (short)
    lines = [l.strip() for l in summary.split("\n") if l.strip() and not l.startswith("【")]
    spoken = "、".join(lines[:3]) if lines else summary[:100]

    return {"title": title, "summary": summary, "spoken": spoken, "action_items": action_items}


@app.get("/api/meeting-notes")
def list_meeting_notes():
    c = db()
    rows = c.execute(
        "SELECT id,title,summary,action_items,ts FROM meeting_notes ORDER BY ts DESC LIMIT 20"
    ).fetchall()
    c.close()
    return [{"id": r[0], "title": r[1], "summary": r[2], "actions": r[3], "ts": r[4]} for r in rows]


@app.get("/meeting/{note_id}", response_class=Response)
def meeting_share_page(note_id: int):
    """Public shareable meeting notes page — no auth required."""
    c = db()
    row = c.execute(
        "SELECT title, summary, action_items, transcript, ts FROM meeting_notes WHERE id=?", (note_id,)
    ).fetchone()
    c.close()
    if not row:
        return Response(content="<h2>找不到這份會議記錄</h2>", media_type="text/html")

    title, summary, actions, transcript, ts = row
    ts_fmt = ts[:16].replace("T", " ") if ts else ""
    # Format summary for HTML
    summary_html = summary.replace("\n", "<br>") if summary else ""
    actions_html = ""
    if actions:
        items = [a.strip() for a in actions.split("\n") if a.strip()]
        actions_html = "".join(f"<li>{item.lstrip('- ')}</li>" for item in items)

    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
body{{font-family:-apple-system,'PingFang TC',sans-serif;max-width:680px;margin:0 auto;padding:24px 16px;background:#fff;color:#1a1a1a;}}
.header{{border-bottom:2px solid #c9a84c;padding-bottom:12px;margin-bottom:24px;}}
.header h1{{font-size:22px;margin:0 0 4px;}}
.header .meta{{font-size:13px;color:#888;}}
.badge{{display:inline-block;background:#c9a84c;color:#fff;border-radius:12px;padding:2px 10px;font-size:12px;margin-bottom:8px;}}
h2{{font-size:16px;color:#c9a84c;margin:24px 0 8px;}}
.summary{{line-height:1.8;font-size:15px;}}
ul{{padding-left:20px;}}
li{{margin:6px 0;line-height:1.6;}}
.footer{{margin-top:40px;font-size:12px;color:#aaa;text-align:center;}}
</style>
</head>
<body>
<div class="header">
  <span class="badge">阿福 · 會議記錄</span>
  <h1>{title}</h1>
  <div class="meta">{ts_fmt}</div>
</div>
<h2>會議摘要</h2>
<div class="summary">{summary_html}</div>
{"<h2>待辦行動</h2><ul>" + actions_html + "</ul>" if actions_html else ""}
<div class="footer">由阿福 Alfred 整理 · YOUR_BACKEND_HOST</div>
</body>
</html>"""
    return Response(content=html, media_type="text/html")


@app.post("/api/meeting-notes/{note_id}/share")
async def share_meeting_notes(note_id: int, req: dict):
    """Send meeting notes link to attendees via SMS."""
    phones = req.get("phones", [])
    host = os.getenv("SERVER_HOST", "YOUR_BACKEND_HOST")
    link = f"https://{host}/alfred/meeting/{note_id}"

    c = db()
    row = c.execute("SELECT title FROM meeting_notes WHERE id=?", (note_id,)).fetchone()
    c.close()
    title = row[0] if row else "會議記錄"

    if not phones:
        return {"link": link, "sent": 0}

    if not TWILIO_CONFIGURED:
        return {"link": link, "sent": 0, "note": "Twilio 未設定，無法自動發送"}

    from twilio.rest import Client as TwilioClient
    tw = TwilioClient(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
    sent = 0
    for phone in phones:
        try:
            tw.messages.create(
                to=phone,
                from_=os.getenv("TWILIO_PHONE_NUMBER"),
                body=f"【{title}】會議記錄連結：{link}"
            )
            sent += 1
        except Exception:
            pass
    return {"link": link, "sent": sent, "total": len(phones)}


@app.get("/api/sms/pending")
def sms_pending():
    """Frontend polls this to see if there are unread SMS replies from contacts."""
    c = db()
    rows = c.execute(
        "SELECT id,key,value,ts FROM memories WHERE category='incoming_sms' ORDER BY ts DESC LIMIT 10"
    ).fetchall()
    c.close()
    return [{"id": r[0], "from": r[1], "body": r[2], "ts": r[3]} for r in rows]


@app.post("/api/twiml/{call_id}")
async def twiml_webhook(call_id: str):
    """Twilio calls this when call connects. Connects Media Streams to OpenAI Realtime bridge."""
    from twilio.twiml.voice_response import VoiceResponse
    host = os.getenv("SERVER_HOST", "YOUR_BACKEND_HOST")
    response = VoiceResponse()
    # Brief pause so the bridge has time to establish OpenAI connection
    response.pause(length=1)
    connect = response.connect()
    connect.stream(url=f"wss://{host}/alfred/api/ws/media/{call_id}")
    return Response(content=str(response), media_type="text/xml")


@app.post("/api/call_status/{call_id}")
async def call_status(call_id: str, request: Request):
    """Twilio status callback: updates call record when call ends."""
    form = await request.form()
    status = form.get("CallStatus", "unknown")
    c = db()
    c.execute("UPDATE calls SET status=? WHERE id=?", (status, call_id))
    c.commit(); c.close()
    if call_service and call_id in call_service.active_calls:
        call_service.active_calls[call_id]["twilio_status"] = status
    return Response(content="", media_type="text/xml")


@app.websocket("/api/ws/media/{call_id}")
async def ws_media(websocket: WebSocket, call_id: str):
    """Twilio Media Streams WebSocket → OpenAI Realtime API bridge."""
    await websocket.accept()
    if call_service:
        await call_service.bridge(websocket, call_id)
        # Persist result to DB
        call = call_service.active_calls.get(call_id, {})
        c = db()
        c.execute(
            "UPDATE calls SET status=?, transcript=?, result=? WHERE id=?",
            (call.get("status","completed"), call.get("transcript",""), call.get("result",""), call_id)
        )
        c.commit(); c.close()


@app.get("/api/twilio-token")
def twilio_access_token(identity: str = "master"):
    """
    Generate Twilio Access Token (JWT) for iOS SDK.
    Grants: ConversationsGrant + VoiceGrant.
    iOS app calls this on launch and refreshes every 24h.
    """
    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    api_key     = os.getenv("TWILIO_API_KEY_SID", "")
    api_secret  = os.getenv("TWILIO_API_KEY_SECRET", "")

    if not (account_sid and api_key and api_secret):
        return {"error": "API Key not configured"}

    from twilio.jwt.access_token import AccessToken
    from twilio.jwt.access_token.grants import ChatGrant, VoiceGrant

    token = AccessToken(account_sid, api_key, api_secret, identity=identity, ttl=86400)
    token.add_grant(ChatGrant(service_sid="default"))  # ChatGrant covers Conversations SDK
    token.add_grant(VoiceGrant(incoming_allow=True))

    return {"token": token.to_jwt(), "identity": identity, "ttl": 86400}


@app.get("/api/oauth/authorize")
def oauth_authorize():
    """Redirect user to Twilio's OAuth authorization page."""
    client_id = os.getenv("TWILIO_OAUTH_CLIENT_ID", "")
    host = os.getenv("SERVER_HOST", "YOUR_BACKEND_HOST")
    redirect_uri = f"https://{host}/alfred/api/oauth/callback"
    from fastapi.responses import RedirectResponse
    url = (f"https://oauth.twilio.com/v2/authorize"
           f"?client_id={client_id}&response_type=code"
           f"&scope=offline_access&redirect_uri={redirect_uri}")
    return RedirectResponse(url)


@app.get("/api/oauth/callback")
async def oauth_callback(code: str = "", error: str = ""):
    """Twilio OAuth callback — exchange code for tokens and store."""
    if error:
        return {"error": error}

    client_id = os.getenv("TWILIO_OAUTH_CLIENT_ID", "")
    client_secret = os.getenv("TWILIO_OAUTH_CLIENT_SECRET", "")
    host = os.getenv("SERVER_HOST", "YOUR_BACKEND_HOST")
    redirect_uri = f"https://{host}/alfred/api/oauth/callback"

    import httpx as _httpx
    r = _httpx.post(
        "https://oauth.twilio.com/v2/token",
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        },
        timeout=10,
    )
    if r.status_code != 200:
        return {"error": f"Token exchange failed: {r.status_code}", "detail": r.text}

    d = r.json()
    # Persist tokens in DB for refresh later
    c = db()
    c.execute("INSERT OR REPLACE INTO memories (category,key,value,ts) VALUES (?,?,?,?)",
              ("twilio_oauth", "access_token", d.get("access_token", ""), datetime.now().isoformat()))
    if d.get("refresh_token"):
        c.execute("INSERT OR REPLACE INTO memories (category,key,value,ts) VALUES (?,?,?,?)",
                  ("twilio_oauth", "refresh_token", d.get("refresh_token", ""), datetime.now().isoformat()))
    c.commit(); c.close()

    return Response(
        content="<html><body style='background:#090909;color:#c9a84c;font-family:sans-serif;text-align:center;padding:60px'>"
                "<h2>✓ Twilio 授權完成</h2><p>阿福已取得 iOS SDK 存取權限。</p>"
                "<script>setTimeout(()=>window.close(),2000)</script></body></html>",
        media_type="text/html"
    )


@app.get("/api/calls/{call_id}")
def get_call_status(call_id: str):
    """Frontend polls this to check if AI call is done."""
    # Check in-memory first (faster), fall back to DB
    if call_service and call_id in call_service.active_calls:
        call = call_service.active_calls[call_id]
        return {
            "call_id": call_id,
            "status": call.get("status", "initiated"),
            "name": call.get("name",""),
            "result": call.get("result",""),
            "transcript": call.get("transcript",""),
        }
    # Fall back to DB
    c = db()
    row = c.execute(
        "SELECT status, name, result, transcript FROM calls WHERE id=?", (call_id,)
    ).fetchone()
    c.close()
    if row:
        return {"call_id": call_id, "status": row[0], "name": row[1],
                "result": row[2] or "", "transcript": row[3] or ""}
    return {"call_id": call_id, "status": "not_found"}
