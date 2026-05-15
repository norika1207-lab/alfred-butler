#!/usr/bin/env python3
import json
import time
import urllib.request
from datetime import datetime
from pathlib import Path

BASE_URL = "http://127.0.0.1:9001"
OUT = Path("/opt/alfred/reports/alfred_context_100_report.md")


def sc(idx, kind, title, situation, trigger, expected, require_any=(), require_all=(),
       forbid=(), action_type=None, forbid_action_type=(), forbid_card=True, max_seconds=3.0):
    return {
        "id": idx,
        "kind": kind,
        "title": title,
        "situation": situation,
        "trigger": trigger,
        "expected": expected,
        "require_any": tuple(require_any),
        "require_all": tuple(require_all),
        "forbid": tuple(forbid),
        "action_type": action_type,
        "forbid_action_type": tuple(forbid_action_type),
        "forbid_card": forbid_card,
        "max_seconds": max_seconds,
    }


CASES = [
    # Active owner requests
    sc(1, "主人丟出", "確認阿福是否在線", "主人準備在客戶面前 demo，先確認阿福有沒有醒著。", "阿福你在嗎", "阿福應該立刻以管家口吻確認自己在，不找文件、不開卡。", require_any=("主人", "在"), forbid=("文件", "索引")),
    sc(2, "主人丟出", "臨時叫阿福幫忙", "主人手上正在忙，只說一句模糊的幫我一下。", "阿福幫我一下", "阿福應該秒回等待吩咐，不自作主張。", require_any=("主人",), forbid=("文件", "索引")),
    sc(3, "主人丟出", "不方便講話改用 LINE", "主人在會議旁邊，不方便用語音，希望改文字。", "用LINE跟阿福對話", "阿福應該給 LINE 加好友/對話連結，不插卡。", require_any=("LINE", "line.me"), forbid=("卡片",)),
    sc(4, "主人丟出", "Telegram 連接", "主人要把阿福接到 Telegram 作為低干擾通知。", "Telegram怎麼連阿福", "阿福應該給 Telegram 連結。", require_any=("Telegram", "t.me"), forbid=("卡片",)),
    sc(5, "主人丟出", "Email 報告", "主人希望長報告寄到信箱，不要塞在畫面上。", "Email可以寄給我嗎", "阿福應該說明可用 Email 寄長報告、會議記錄、生活摘要。", require_any=("Email", "報告")),
    sc(6, "主人丟出", "Google 授權", "主人想讓阿福讀 Drive 和日曆。", "我要連Google", "阿福應該提供 Google 授權連結。", require_any=("Google", "授權", "http")),
    sc(7, "主人丟出", "阿福服務設定", "主人想檢查所有外部服務是否開通。", "我想設定阿福服務", "阿福應該給服務設定入口。", require_any=("設定", "服務", "Google")),
    sc(8, "主人丟出", "啟動阿福模式", "主人直接用語音要求開啟全天聆聽。", "阿福模式開啟", "阿福不能直接開，要提醒必須按 App 按鈕並看到宣告。", require_all=("App", "宣告"), forbid_action_type=("start_ambient",)),
    sc(9, "主人丟出", "聆聽隱私疑慮", "主人擔心阿福整天偷聽。", "阿福模式會不會一直偷聽", "阿福應該說明不偷開、本地判斷人聲、可隨時停止。", require_any=("宣告", "本地", "停止"), forbid=("偷偷開啟後",)),
    sc(10, "主人丟出", "停止聆聽", "主人覺得接下來內容不想被記錄。", "阿福你先不要聽", "阿福應該停止聆聽並進休息狀態。", require_any=("停止", "休息"), action_type="stop_ambient"),
    sc(11, "主人丟出", "沒有聲音時怎麼辦", "主人詢問沒有人聲時是否還會上傳。", "沒有聲音的時候會不會上傳", "阿福應該說沒有聲音不會上傳、不會轉逐字稿。", require_any=("不會上傳", "人聲")),
    sc(12, "主人丟出", "逐字稿切段", "主人想知道長時間記錄的處理方式。", "阿福模式多久切一次逐字稿", "阿福應該描述本地人聲判斷與逐字稿整理。", require_any=("本地", "逐字稿")),
    sc(13, "主人丟出", "日本親子旅行", "主人臨時要在客戶面前展示行程能力。", "幫我安排日本親子3天旅行", "阿福應該提供東京基礎版本，完整內容走 LINE/Email，不插卡。", require_any=("東京", "LINE", "Email"), forbid=("資料還不全",)),
    sc(14, "主人丟出", "韓國親子旅行", "主人問韓國親子行程。", "幫我安排韓國親子4天旅行", "阿福應該回首爾親子版本，不能出現農心這類非旅遊推薦。", require_any=("首爾", "樂天世界", "LINE"), forbid=("農心",)),
    sc(15, "主人丟出", "釜山情侶旅行", "主人和太太想去釜山。", "幫我安排釜山情侶3天旅行", "阿福應該給釜山景點與餐廳。", require_any=("釜山", "海雲台", "LINE")),
    sc(16, "主人丟出", "福岡自由行", "主人只說福岡三天自由行。", "幫我安排福岡三天自由行", "阿福應該給博多/太宰府等方向。", require_any=("福岡", "太宰府", "LINE")),
    sc(17, "主人丟出", "大阪親子", "主人想去大阪親子四天。", "大阪親子四天可以怎麼安排", "阿福應該抓 USJ 或大阪親子節奏。", require_any=("大阪", "USJ", "LINE")),
    sc(18, "主人丟出", "京都情侶", "主人想和太太去京都。", "京都情侶三天怎麼玩", "阿福應該給清水寺、祇園或嵐山等。", require_any=("京都", "清水寺", "LINE")),
    sc(19, "主人丟出", "不知道去哪玩", "主人只說想出國但沒有目的地。", "我想出國玩但還不知道去哪", "阿福應該列熱門方向讓主人選，不亂找文件。", require_any=("日本", "韓國", "泰國"), forbid=("文件", "索引")),
    sc(20, "主人丟出", "日本旅行傳 LINE", "主人要求日本行程並指定 LINE 傳送。", "幫我安排日本旅行然後傳LINE", "阿福應該回日本/東京行程並說會透過 LINE/Email。", require_any=("東京", "LINE"), forbid=("文件",)),
    sc(21, "主人丟出", "韓國行程寄 Email", "主人要求韓國行程寄 Email。", "幫我把韓國行程寄Email", "阿福應該回首爾/韓國行程，說明透過 Email。", require_any=("首爾", "Email"), forbid=("文件",)),
    sc(22, "主人丟出", "台北米其林", "主人要餐廳，不是旅遊。", "台北米其林餐廳推薦", "阿福應該回餐廳推薦，不應變成行程。", require_any=("米其林", "鼎泰豐"), forbid=("旅行", "LINE")),
    sc(23, "主人丟出", "台北牛肉麵", "主人想吃牛肉麵。", "台北有什麼牛肉麵", "阿福應該推薦牛肉麵。", require_any=("牛肉麵",), forbid=("旅遊", "行程")),
    sc(24, "主人丟出", "釜山海鮮", "主人問釜山吃海鮮，不是要排旅遊。", "釜山海鮮推薦", "阿福應該推薦釜山海鮮。", require_any=("釜山", "海"), forbid=("資料還不全",)),
    sc(25, "主人丟出", "曼谷泰式料理", "主人問餐廳。", "曼谷泰式料理推薦", "阿福應該推薦泰式餐廳。", require_any=("曼谷", "泰"), forbid=("資料還不全",)),
    sc(26, "主人丟出", "附近早餐", "主人醒來想知道附近早餐。", "附近有什麼早餐", "阿福應該推薦附近早餐，不要跑文件。", require_any=("早餐",), forbid=("文件", "索引", "油飯")),
    sc(27, "主人丟出", "附近漢堡早餐", "主人指定漢堡類早餐。", "附近想吃漢堡早餐", "阿福應該推薦漢堡/早餐相關店。", require_all=("漢堡", "早餐"), forbid=("油飯", "索引")),
    sc(28, "主人丟出", "一公里火鍋", "主人指定半徑與類型。", "附近一公里內有麻辣火鍋嗎", "阿福應該回一公里內火鍋。", require_any=("火鍋", "麻辣"), forbid=("牛肉麵",)),
    sc(29, "主人丟出", "天氣", "主人出門前問天氣。", "今天天氣怎麼樣", "阿福應該回天氣，不找文件。", require_any=("主人", "°C"), forbid=("文件", "索引")),
    sc(30, "主人丟出", "帶傘", "主人出門前問是否帶傘。", "今天要帶傘嗎", "阿福應該直接給天氣與帶傘建議。", require_any=("傘", "°C"), forbid=("文件",)),
    sc(31, "主人丟出", "昨天 AI 新聞", "主人問昨天新聞，不是最新新聞。", "幫我查昨天AI新聞", "阿福應該查新聞並尊重昨天時間。", require_any=("新聞",), forbid=("只能搜尋最新", "文件"), max_seconds=5),
    sc(32, "主人丟出", "TechCrunch 科技新聞", "主人指定國外科技來源。", "去TechCrunch找科技新聞", "阿福應該查 TechCrunch，不搜文件。", require_any=("TechCrunch",), forbid=("文件", "索引"), max_seconds=5),
    sc(33, "主人丟出", "找合約", "主人要阿福找文件。", "幫我找合約", "阿福應該搜尋 Drive/Mac/保管庫候選。", require_any=("合約", "文件"), forbid=("旅行",), max_seconds=4),
    sc(34, "主人丟出", "找台電合約", "主人指定台電合約。", "幫我找台電合約", "阿福應該回台電合約候選。", require_any=("台電", "合約"), max_seconds=4),
    sc(35, "主人丟出", "找 91APP", "主人指定英文數字關鍵字。", "找91APP資料", "阿福應該只回 91APP 相關資料。", require_any=("91APP", "文件", "找"), forbid=("TechCrunch",), max_seconds=4),
    sc(36, "主人丟出", "找公證書", "主人要公證書。", "幫我找公證書", "阿福應該回公證書候選。", require_any=("公證", "文件", "找"), max_seconds=4),
    sc(37, "主人丟出", "不要亂找旅遊", "主人要合約，特別要求不要跑旅行。", "阿福幫我找個合約，然後不要亂找旅遊", "阿福應該找文件，不要回東京行程。", require_any=("合約", "文件"), forbid=("東京", "LINE"), max_seconds=4),
    sc(38, "主人丟出", "日本行程不能被上一輪文件污染", "上一輪剛找過合約，主人下一句改問旅行。", "5月日本旅行", "阿福應該清掉文件待選狀態，回旅行。", require_any=("東京", "LINE"), forbid=("合約", "第5份", "文件")),
    sc(39, "主人丟出", "照片分析", "主人要看手機照片。", "幫我看照片", "阿福應該叫主人挑照片，觸發相簿 picker。", require_any=("相簿", "挑一張"), action_type="show_photos_picker", forbid_card=False),
    sc(40, "主人丟出", "簡單計算", "主人臨時問數學。", "123加456是多少", "阿福應該直接答 579。", require_any=("579",), forbid=("文件",)),
    sc(41, "主人丟出", "乘法", "主人問乘法。", "12乘以13是多少", "阿福應該答 156。", require_any=("156",), forbid=("文件",)),
    sc(42, "主人丟出", "提醒客戶電話", "主人隨口交代提醒。", "提醒我明天下午三點打電話給客戶", "阿福應該建立提醒。", require_any=("提醒", "主人"), forbid=("文件",), max_seconds=5),
    sc(43, "主人丟出", "記得繳費", "主人隨口交代下週任務。", "幫我記得下週一要繳電話費", "阿福應該建立提醒。", require_any=("記得", "提醒"), forbid=("文件",), max_seconds=5),
    sc(44, "主人丟出", "查今天行程", "主人問今天安排。", "我今天有什麼行程", "阿福應該查行程，不找文件。", require_any=("今天", "行程"), forbid=("文件",), max_seconds=5),
    sc(45, "主人丟出", "查明天會議", "主人問明天會不會有會議。", "明天早上有會議嗎", "阿福應該回明天會議/行程狀態。", require_any=("明天", "會議"), forbid=("文件",), max_seconds=5),
    sc(46, "主人丟出", "新增生日", "主人交代家人生日。", "我太太生日是7月1日", "阿福應該立刻記下，不拖慢。", require_any=("生日", "主人"), forbid=("文件",), max_seconds=3),
    sc(47, "主人丟出", "查紀念日", "主人問重要日子。", "我有哪些紀念日要記得", "阿福應該列紀念日，不找 PDF。", require_any=("紀念日", "生日"), forbid=("91APP", "PDF", "文件")),
    sc(48, "主人丟出", "開始會議記錄", "主人正式開會。", "幫我開始記錄這個會議", "阿福應該開始會議記錄。", require_any=("會議", "開始"), max_seconds=4),
    sc(49, "主人丟出", "會議結束", "主人會議結束。", "會議結束幫我整理", "阿福應該停止並準備摘要。", require_any=("會議", "整理"), max_seconds=4),
    sc(50, "主人丟出", "出勤狀態", "主人問今天打卡/出勤。", "幫我看今天出勤狀態", "阿福應該回今天出勤狀態。", require_any=("今天",), forbid=("文件",)),

    # Passive owner-life events represented by the event trigger Alfred would receive or infer
    sc(51, "被動主人發生", "主人打開阿福模式按鈕", "主人在 App 內按下阿福模式，畫面必須顯示宣告，而不是偷偷開始。", "阿福模式開啟", "阿福應該再次提醒必須 App 按鈕與宣告，不從語音偷偷開。", require_all=("App", "宣告"), forbid_action_type=("start_ambient",)),
    sc(52, "被動主人發生", "主人一段時間沒說話", "阿福模式開著，但環境沒有偵測到人聲。", "沒有聲音的時候會不會上傳", "阿福應該說沒有人聲不上傳、不轉逐字稿。", require_any=("不會上傳", "人聲")),
    sc(53, "被動主人發生", "主人說想休息", "主人沒有明確操作手機，只說阿福去休息。", "阿福你去休息", "阿福應該語音停止聆聽。", require_any=("停止", "休息"), action_type="stop_ambient"),
    sc(54, "被動主人發生", "主人說先關閉", "主人在日常對話中說阿福先關閉。", "阿福你先關閉", "阿福應該停止聆聽。", require_any=("停止", "休息"), action_type="stop_ambient"),
    sc(55, "被動主人發生", "主人正在會議", "阿福偵測到主人開始會議，需要低干擾記錄。", "幫我開始記錄這個會議", "阿福應該開始會議記錄，正常讓主人開會。", require_any=("會議", "開始"), max_seconds=4),
    sc(56, "被動主人發生", "會議結束", "阿福聽到會議結束語意。", "會議結束幫我整理", "阿福應該整理摘要與待辦，不插卡。", require_any=("會議", "整理"), max_seconds=4),
    sc(57, "被動主人發生", "主人問逐字稿", "主人想回查剛剛聽到的內容。", "阿福剛剛聽到什麼", "阿福應該查逐字稿或明確說目前沒有相關片段。", require_any=("逐字稿", "沒有查到", "片段"), max_seconds=5),
    sc(58, "被動主人發生", "主人擔心隱私", "主人懷疑阿福是否一直偷聽。", "阿福模式會不會一直偷聽", "阿福應該安撫並說明宣告、本地、人聲判斷。", require_any=("宣告", "本地", "不會偷偷")),
    sc(59, "被動主人發生", "主人早上醒來", "主人早上打招呼，阿福不能過度做事。", "阿福早安", "阿福應該簡短問候。", require_any=("主人",), forbid=("文件",)),
    sc(60, "被動主人發生", "主人晚上準備休息", "主人晚上說晚安。", "阿福晚安", "阿福應該簡短回晚安。", require_any=("晚安", "主人"), forbid=("文件",)),
    sc(61, "被動主人發生", "主人出門前天氣", "主人拿起包準備出門，問要不要帶傘。", "今天要帶傘嗎", "阿福應該給天氣與傘建議。", require_any=("傘", "°C"), forbid=("文件",)),
    sc(62, "被動主人發生", "主人覺得外面冷", "主人在門口問冷不冷。", "外面冷不冷", "阿福應該回溫度。", require_any=("主人", "°C"), forbid=("文件",)),
    sc(63, "被動主人發生", "主人肚子餓", "主人到附近街區想找早餐。", "附近有什麼早餐", "阿福應該回附近早餐。", require_any=("早餐",), forbid=("文件", "油飯")),
    sc(64, "被動主人發生", "主人臨時想吃火鍋", "主人在泰山附近想吃麻辣火鍋。", "附近一公里內有麻辣火鍋嗎", "阿福應該回一公里內火鍋。", require_any=("火鍋",), forbid=("文件",)),
    sc(65, "被動主人發生", "主人想到日本", "主人生活中隨口說 5 月日本旅行。", "5月日本旅行", "阿福應該主動接成旅行，不被舊文件污染。", require_any=("東京", "LINE"), forbid=("文件", "第5份")),
    sc(66, "被動主人發生", "主人想到韓國親子", "主人提到韓國親子旅行。", "5月韓國親子旅行", "阿福應該排首爾親子版本。", require_any=("首爾", "LINE"), forbid=("文件",)),
    sc(67, "被動主人發生", "主人要找合約", "主人突然說幫我找個合約。", "阿福幫我找個合約", "阿福應該找合約，不排旅遊。", require_any=("合約", "文件"), forbid=("東京",), max_seconds=4),
    sc(68, "被動主人發生", "主人說不要找文件", "主人只是確認阿福在，不想觸發找文件。", "阿福你還在嗎，不要去找文件", "阿福應該只回我在。", require_any=("主人", "在"), forbid=("文件", "索引")),
    sc(69, "被動主人發生", "主人看到舊文件名", "主人想到 91APP 報告。", "找91APP資料", "阿福應該只找 91APP。", require_any=("91APP",), forbid=("TechCrunch",), max_seconds=4),
    sc(70, "被動主人發生", "主人臨時要報價單", "主人在客戶現場要報價單。", "找一下報價單", "阿福應該搜尋報價單。", require_any=("報價", "文件"), forbid=("旅遊",), max_seconds=4),
    sc(71, "被動主人發生", "主人要公證書", "主人臨時想到土地公證文件。", "幫我找公證書", "阿福應該搜尋公證書。", require_any=("公證", "文件"), max_seconds=4),
    sc(72, "被動主人發生", "主人問 AI 新聞", "主人看到科技話題，問昨天 AI 新聞。", "幫我查昨天AI新聞", "阿福應該查新聞，不回不能查昨天。", require_any=("新聞",), forbid=("只能搜尋最新", "文件"), max_seconds=5),
    sc(73, "被動主人發生", "主人想追國外科技", "主人想知道國外 AI 消息。", "國外科技網站有什麼AI消息", "阿福應該回國外科技新聞。", require_any=("technology", "TechCrunch", "新聞"), forbid=("文件",), max_seconds=5),
    sc(74, "被動主人發生", "主人想記太太生日", "主人日常提到太太生日。", "我太太生日是7月1日", "阿福應該秒記，不等 LLM。", require_any=("生日", "主人"), forbid=("文件",), max_seconds=3),
    sc(75, "被動主人發生", "主人想查紀念日", "阿福需要掌握主人生活重要日期。", "我有哪些紀念日要記得", "阿福應該列出紀念日。", require_any=("紀念日", "生日"), forbid=("91APP", "文件")),
    sc(76, "被動主人發生", "主人要提醒客戶電話", "主人隨口說明天下午要打電話。", "提醒我明天下午三點打電話給客戶", "阿福應該建立提醒。", require_any=("提醒", "主人"), forbid=("文件",), max_seconds=5),
    sc(77, "被動主人發生", "主人要記繳費", "主人走路時想起下週一繳費。", "幫我記得下週一要繳電話費", "阿福應該建立提醒。", require_any=("提醒", "記得"), forbid=("文件",), max_seconds=5),
    sc(78, "被動主人發生", "主人看日程", "主人開始一天前問今日行程。", "我今天有什麼行程", "阿福應該回行程狀態。", require_any=("今天", "行程"), forbid=("文件",), max_seconds=5),
    sc(79, "被動主人發生", "主人問明天早上會議", "主人睡前確認明早會議。", "明天早上有會議嗎", "阿福應該回明天會議/行程狀態。", require_any=("明天", "會議"), forbid=("文件",), max_seconds=5),
    sc(80, "被動主人發生", "主人要看今日照片", "主人想讓阿福看手機相簿。", "幫我看今天的照片", "阿福應該打開相簿 picker。", require_any=("相簿", "挑一張"), action_type="show_photos_picker", forbid_card=False),
    sc(81, "被動主人發生", "主人問出勤", "主人想到今天有沒有打卡。", "幫我看今天出勤狀態", "阿福應該回今天出勤。", require_any=("今天",), forbid=("文件",)),
    sc(82, "被動主人發生", "主人做加法", "主人需要心算協助。", "1000減333是多少", "阿福應該直接答 667。", require_any=("667",), forbid=("文件",)),
    sc(83, "被動主人發生", "主人做除法", "主人需要快速計算。", "144除以12是多少", "阿福應該答 12。", require_any=("12",), forbid=("文件",)),
    sc(84, "被動主人發生", "主人問新加坡必吃", "主人出國前想到新加坡吃什麼。", "新加坡必吃什麼", "阿福應該推薦新加坡食物。", require_any=("新加坡", "海南雞飯"), forbid=("資料還不全",)),
    sc(85, "被動主人發生", "主人問首爾美食", "主人想到韓國餐廳。", "首爾有什麼好吃的", "阿福應該推薦首爾餐廳，不出農心。", require_any=("首爾",), forbid=("農心",)),
    sc(86, "被動主人發生", "主人問台南小吃", "主人要台南小吃。", "台南小吃推薦", "阿福應該推薦台南小吃。", require_any=("台南",), forbid=("資料還不全",)),
    sc(87, "被動主人發生", "主人問巴黎短行程", "主人臨時想去巴黎兩天。", "幫我安排巴黎兩天行程", "阿福應該能回巴黎，不說資料不足。", require_any=("巴黎", "LINE"), forbid=("資料還不全",)),
    sc(88, "被動主人發生", "主人問倫敦", "主人想去倫敦三天。", "幫我安排倫敦三天旅行", "阿福應該能回倫敦。", require_any=("倫敦", "LINE"), forbid=("資料還不全",)),
    sc(89, "被動主人發生", "主人問羅馬", "主人想去羅馬。", "幫我安排羅馬三天情侶旅行", "阿福應該能回羅馬。", require_any=("羅馬", "LINE"), forbid=("資料還不全",)),
    sc(90, "被動主人發生", "主人問杜拜親子", "主人問杜拜親子三天。", "幫我安排杜拜三天親子旅行", "阿福應該能回杜拜。", require_any=("杜拜", "LINE"), forbid=("資料還不全",)),
    sc(91, "被動主人發生", "主人不想開介面查天氣", "主人明確要求不要開介面。", "幫我查天氣不要開介面", "阿福應該零介面回天氣。", require_any=("主人", "°C"), forbid=("卡片",)),
    sc(92, "被動主人發生", "主人想看 Google 狀態", "主人疑惑 Google 有沒有連。", "Google 授權狀態", "阿福應該回 Google 授權/連結狀態。", require_any=("Google", "授權")),
    sc(93, "被動主人發生", "主人要 LINE 通知", "主人希望低干擾通知走 LINE。", "阿福可以用LINE通知我嗎", "阿福應該回 LINE 連結或通知能力。", require_any=("LINE",)),
    sc(94, "被動主人發生", "主人要服務設定", "主人想一次檢查所有連線。", "阿福設定在哪裡", "阿福應該提供服務設定入口。", require_any=("設定", "服務"), max_seconds=4),
    sc(95, "被動主人發生", "主人問阿福是否醒著", "長時間沒互動後，主人確認阿福是否還醒。", "你還醒著嗎", "阿福應該秒回。", require_any=("主人", "在"), forbid=("文件",)),
    sc(96, "被動主人發生", "主人問現在能不能幫忙", "主人準備下指令前先確認。", "現在可以幫我嗎", "阿福應該秒回可協助。", require_any=("主人",), forbid=("文件",)),
    sc(97, "被動主人發生", "主人問日本行程不要掛", "主人過去 demo 失敗後，明確提到不要講到一半掛掉。", "我問日本行程不要講到一半掛掉", "阿福應該回日本行程，不掛、不找文件。", require_any=("東京", "LINE"), forbid=("資料還不全", "文件")),
    sc(98, "被動主人發生", "主人說台北米其林不是旅遊", "主人避免語意誤判。", "台北米其林不是旅遊，是餐廳推薦", "阿福應該回餐廳。", require_any=("米其林", "餐廳"), forbid=("LINE", "行程")),
    sc(99, "被動主人發生", "主人說早餐不要油飯", "主人指定排除油飯。", "附近早餐但不要給我油飯", "阿福應該推薦早餐且不含油飯。", require_any=("早餐",), forbid=("油飯", "文件")),
    sc(100, "被動主人發生", "主人要日本行程", "主人用『找個』這種容易誤判為文件的話問日本行程。", "阿福幫我找個日本行程", "阿福應該理解為旅行，不是文件搜尋。", require_any=("日本", "東京", "LINE"), forbid=("文件",)),
]


def request_chat(message, timeout=20):
    body = json.dumps({"message": message, "history": []}, ensure_ascii=False).encode("utf-8")
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
    if elapsed > c["max_seconds"]:
        failures.append(f"超時 {elapsed:.2f}s > {c['max_seconds']:.2f}s")
    if c["require_any"] and not any(s in text for s in c["require_any"]):
        failures.append("缺少任一必要字: " + " / ".join(c["require_any"]))
    for s in c["require_all"]:
        if s not in text:
            failures.append("缺少必要字: " + s)
    for s in c["forbid"]:
        if s in text:
            failures.append("出現禁止字: " + s)
    if c["forbid_card"] and card:
        failures.append("不應該出現 UI card")
    if c["action_type"] and action.get("type") != c["action_type"]:
        failures.append(f"action 錯誤: {action.get('type')} != {c['action_type']}")
    if action.get("type") in c["forbid_action_type"]:
        failures.append("出現禁止 action: " + str(action.get("type")))
    return failures


def one_line(text):
    return " ".join((text or "").split())


def main():
    assert len(CASES) == 100, len(CASES)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    results = []
    for c in CASES:
        try:
            elapsed, data = request_chat(c["trigger"])
            failures = evaluate(c, elapsed, data)
        except Exception as exc:
            elapsed, data, failures = 999.0, {}, [f"例外: {type(exc).__name__}: {exc}"]
        ok = not failures
        results.append({**c, "ok": ok, "elapsed": elapsed, "data": data, "failures": failures})
        status = "OK" if ok else "FAIL"
        print(f"{c['id']:03d} {status} {c['kind']} {c['title']} {elapsed:.2f}s :: {one_line(data.get('text',''))[:160]}")
        if failures:
            print("    " + " | ".join(failures))

    passed = sum(1 for r in results if r["ok"])
    failed = len(results) - passed
    slow = sum(1 for r in results if any(f.startswith("超時") for f in r["failures"]))
    cards = sum(1 for r in results if r["forbid_card"] and (r["data"].get("card") if isinstance(r["data"], dict) else None))
    active = [r for r in results if r["kind"] == "主人丟出"]
    passive = [r for r in results if r["kind"] == "被動主人發生"]

    lines = []
    lines.append("# Alfred 100 情境測試報告")
    lines.append("")
    lines.append(f"- 測試時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- API：{BASE_URL}/api/chat")
    lines.append(f"- 總數：{len(results)}")
    lines.append(f"- 通過：{passed}")
    lines.append(f"- 失敗：{failed}")
    lines.append(f"- 失敗率：{failed / len(results) * 100:.1f}%")
    lines.append(f"- 慢回覆：{slow}")
    lines.append(f"- 非預期 UI card：{cards}")
    lines.append(f"- 主人丟出情境：{sum(1 for r in active if r['ok'])}/{len(active)}")
    lines.append(f"- 被動主人發生情境：{sum(1 for r in passive if r['ok'])}/{len(passive)}")
    lines.append("")
    lines.append("## 明細")
    lines.append("")
    for r in results:
        text = one_line(r["data"].get("text", "")) if isinstance(r["data"], dict) else ""
        action = (r["data"].get("action") or {}) if isinstance(r["data"], dict) else {}
        card = r["data"].get("card") if isinstance(r["data"], dict) else None
        lines.append(f"### {r['id']:03d}. {r['kind']}｜{r['title']}｜{'通過' if r['ok'] else '失敗'}｜{r['elapsed']:.2f}s")
        lines.append("")
        lines.append(f"- 情境：{r['situation']}")
        lines.append(f"- 測試輸入/事件觸發：{r['trigger']}")
        lines.append(f"- 預期反應：{r['expected']}")
        lines.append(f"- 實際說法：{text}")
        lines.append(f"- action：{json.dumps(action, ensure_ascii=False) if action else '無'}")
        lines.append(f"- UI card：{'有' if card else '無'}")
        if r["failures"]:
            lines.append(f"- 問題：{'；'.join(r['failures'])}")
        lines.append("")
    OUT.write_text("\n".join(lines), encoding="utf-8")

    print("")
    print("SUMMARY")
    print(f"total={len(results)}")
    print(f"passed={passed}")
    print(f"failed={failed}")
    print(f"failure_rate={failed / len(results) * 100:.1f}%")
    print(f"slow_failures={slow}")
    print(f"unexpected_cards={cards}")
    print(f"active={sum(1 for r in active if r['ok'])}/{len(active)}")
    print(f"passive={sum(1 for r in passive if r['ok'])}/{len(passive)}")
    print(f"report={OUT}")
    raise SystemExit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
