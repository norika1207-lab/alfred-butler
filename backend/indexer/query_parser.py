"""
indexer/query_parser.py — 查詢理解引擎（零 LLM）

把「幫我找最便宜的AirPods Pro」拆成：
  brand=Apple, product=AirPods Pro, category=3C, min_price=3000
"""
import re
from dataclasses import dataclass, field

# 品牌辨識表
BRAND_MAP = {
    "apple": ["airpods", "iphone", "ipad", "macbook", "apple watch", "mac mini"],
    "sony": ["wh-", "wf-", "xm4", "xm5", "playstation", "ps5"],
    "samsung": ["galaxy", "samsung"],
    "panasonic": ["panasonic", "國際牌"],
    "philips": ["philips", "飛利浦", "sonicare"],
    "oral-b": ["oral-b", "歐樂b", "braun"],
    "xiaomi": ["xiaomi", "小米", "mijia", "米家"],
    "bosch": ["bosch", "博世"],
    "makita": ["makita", "牧田"],
    "dyson": ["dyson", "戴森"],
    "lg": ["lg"],
    "asus": ["asus", "華碩"],
    "lenovo": ["lenovo", "聯想"],
}

# 品類最低合理價格（過濾明顯配件）
CATEGORY_PRICE_FLOOR = {
    "耳機": 300,
    "airpods": 2000,
    "iphone": 5000,
    "ipad": 3000,
    "macbook": 15000,
    "筆電": 8000,
    "電視": 3000,
    "冰箱": 5000,
    "洗衣機": 5000,
    "氣炸鍋": 500,
    "咖啡機": 800,
    "掃地機": 1000,
    "電鑽": 500,
    "電動牙刷": 150,
    "吹風機": 300,
}

# 配件訊號
ACCESSORY_SUFFIXES = [
    "瓶", "瓶蓋", "罐", "架", "盒", "袋", "膜", "套", "殼", "紙", "布",
    "線", "頭", "按壓", "噴嘴", "蓋子", "掛鉤", "置物", "收納", "托盤",
    "轉換頭", "轉角器", "起子頭", "鑽頭", "鋸片", "砂輪片",
]
ACCESSORY_KEYWORDS = [
    "專用", "適用", "保護殼", "保護套", "替換", "配件", "週邊",
    "刷頭", "烘焙紙", "耐油紙", "噴霧油", "客製", "耳機殼", "手機殼",
    "矽膠套", "耳塞套", "掛繩", "通用保護", "鑰匙圈", "掛件",
    "蛋糕模", "烤盤", "食譜", "全書", "圖解", "副廠", "相容",
    "原廠品質體驗", "仿", "通用型",
]

INTENT_VERBS = {"幫我", "找", "買", "查", "要", "想要", "幫", "請", "我要", "我想"}
MODIFIER_WORDS = {"最", "便宜", "優惠", "划算", "CP值", "好的", "一個", "台", "支",
                  "件", "顆", "組", "入", "條", "罐", "瓶", "箱", "包", "袋"}


@dataclass
class ParsedQuery:
    raw: str
    core_terms: list[str] = field(default_factory=list)   # 核心商品詞
    brand: str | None = None
    category: str | None = None
    min_price: int = 0
    fts_query: str = ""                                     # 給 SQLite FTS5 用


def parse(query: str) -> ParsedQuery:
    pq = ParsedQuery(raw=query)
    q = query.strip()

    # 1. 去掉動詞/修飾詞
    for v in sorted(INTENT_VERBS | MODIFIER_WORDS, key=len, reverse=True):
        q = q.replace(v, " ")
    q = re.sub(r"\s+", " ", q).strip()

    # 2. 拆詞
    tokens = [t for t in re.split(r"[\s，。、/\-]+", q) if t and len(t) > 0]
    pq.core_terms = tokens

    # 3. 品牌辨識
    q_lower = query.lower()
    for brand, hints in BRAND_MAP.items():
        if brand in q_lower or any(h in q_lower for h in hints):
            pq.brand = brand
            break

    # 4. 類別與最低價
    for cat, floor in CATEGORY_PRICE_FLOOR.items():
        if cat in q_lower:
            pq.category = cat
            pq.min_price = floor
            break

    # 5. 組 FTS 查詢（任一詞命中即可）
    fts_parts = []
    for t in tokens:
        if len(t) >= 2:
            fts_parts.append(f'"{t}"')
    pq.fts_query = " OR ".join(fts_parts) if fts_parts else query

    return pq


def is_accessory(product_name: str, query_terms: list[str]) -> bool:
    name_l = product_name.lower()

    if any(kw in name_l for kw in ACCESSORY_KEYWORDS):
        return True

    for term in query_terms:
        t = term.lower()
        idx = name_l.find(t)
        if idx >= 0:
            after = name_l[idx + len(t):]
            if any(after.startswith(s) for s in ACCESSORY_SUFFIXES):
                return True
    return False
