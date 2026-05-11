"""
shop_service.py — 台灣電商比價引擎
純演算法，零 LLM。抓商品名稱、價格、折扣、規格、一張圖。
目前支援：momo、PChome 24h、蝦皮（需登入 cookies）、松果購物 (pcone.com.tw)、博客來
"""
import re
import json
import asyncio
import httpx
from typing import Optional
from pathlib import Path

from scrapers.books_scraper import search_books

# 蝦皮 session cookies 存放路徑（登入後由 /api/shop/shopee-login 寫入）
_SHOPEE_COOKIE_FILE = Path(__file__).parent.parent / "data" / "shopee_session.json"

_HEADERS_MOBILE = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.0 Mobile/15E148 Safari/604.1"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_HEADERS_DESKTOP = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-TW,zh;q=0.9",
    "Referer": "https://24h.pchome.com.tw/",
}

_PCHOME_IMG_BASE = "https://cs-b.ecimg.tw"


# ── momo ──────────────────────────────────────────────────────────────────────

def _extract_momo_products(html: str, limit: int = 6) -> list[dict]:
    m = re.search(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.DOTALL
    )
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except Exception:
        return []

    graph = data if isinstance(data, list) else data.get("@graph", [data])
    items = []
    for node in graph:
        if node.get("@type") == "ItemList":
            items = node.get("itemListElement", [])
            break

    products = []
    for item in items[:limit]:
        name = item.get("name", "")
        image_url = item.get("image", "")
        buy_url = item.get("url", "")
        price = int(item.get("offers", {}).get("price", 0))
        rating = item.get("aggregateRating", {})

        code_m = re.search(r"i_code=(\d+)", buy_url)
        code = code_m.group(1) if code_m else ""
        canonical_url = f"https://www.momoshop.com.tw/goods/GoodsDetail.jsp?i_code={code}" if code else buy_url

        list_price = _extract_momo_list_price(html, code) if code else None
        discount_pct = None
        if list_price and list_price > price:
            discount_pct = round((1 - price / list_price) * 100)

        if not price or not name:
            continue

        products.append({
            "site": "momo",
            "code": code,
            "name": name,
            "price": price,
            "list_price": list_price,
            "discount_pct": discount_pct,
            "image_url": image_url,
            "buy_url": canonical_url,
            "rating": rating.get("ratingValue"),
            "review_count": rating.get("reviewCount"),
        })
    return products


def _extract_momo_list_price(html: str, code: str) -> Optional[int]:
    m = re.search(
        rf'\\\\?"goodsCode\\\\?":\\\\?"0*{code}\\\\?".*?\\\\?"listPrice\\\\?":\\\\?"([^"\\\\]+)',
        html
    )
    if m:
        digits = re.sub(r"[^0-9]", "", m.group(1))
        return int(digits) if digits else None
    return None


async def search_momo(query: str, limit: int = 6) -> list[dict]:
    params = httpx.QueryParams({"keyword": query, "searchType": "1", "ent": "k", "curPage": "1"})
    url = f"https://www.momoshop.com.tw/search/searchShop.jsp?{params}"
    async with httpx.AsyncClient(headers=_HEADERS_MOBILE, timeout=15, follow_redirects=True) as client:
        r = await client.get(url)
        r.raise_for_status()
    return _extract_momo_products(r.text, limit)


# ── PChome 24h ────────────────────────────────────────────────────────────────

def _pchome_image_url(pic_path: str) -> str:
    if not pic_path:
        return ""
    if pic_path.startswith("http"):
        return pic_path
    return f"{_PCHOME_IMG_BASE}{pic_path}"


def _extract_pchome_products(data: dict, limit: int = 6) -> list[dict]:
    prods = data.get("prods", [])
    products = []
    for p in prods[:limit]:
        pid = p.get("Id", "")
        name = p.get("name", "")
        price = int(p.get("price", 0))
        origin_price = int(p.get("originPrice", 0))
        pic = _pchome_image_url(p.get("picS", ""))

        if not price or not name:
            continue

        discount_pct = None
        if origin_price and origin_price > price:
            discount_pct = round((1 - price / origin_price) * 100)

        products.append({
            "site": "pchome",
            "code": pid,
            "name": name,
            "price": price,
            "list_price": origin_price if origin_price != price else None,
            "discount_pct": discount_pct,
            "image_url": pic,
            "buy_url": f"https://24h.pchome.com.tw/prod/{pid}",
            "rating": None,
            "review_count": None,
        })
    return products


async def search_pchome(query: str, limit: int = 6) -> list[dict]:
    url = (
        "https://ecshweb.pchome.com.tw/search/v3.3/all/results"
        f"?q={httpx.QueryParams({'q': query}).get('q', query)}&page=1&sort=rnk/dc"
    )
    async with httpx.AsyncClient(headers=_HEADERS_DESKTOP, timeout=12) as client:
        r = await client.get(url)
        r.raise_for_status()
    return _extract_pchome_products(r.json(), limit)


# ── 蝦皮 ──────────────────────────────────────────────────────────────────────

def _load_shopee_cookies() -> Optional[dict]:
    """讀取已儲存的蝦皮 session cookies"""
    try:
        if _SHOPEE_COOKIE_FILE.exists():
            return json.loads(_SHOPEE_COOKIE_FILE.read_text())
    except Exception:
        pass
    return None


def _extract_shopee_products(items: list, limit: int = 6) -> list[dict]:
    products = []
    for item in items[:limit]:
        b = item.get("item_basic", item)
        name = b.get("name", "")
        # 蝦皮價格單位是 /100000
        raw_price = b.get("price") or b.get("price_min") or 0
        price = int(raw_price / 100000) if raw_price > 10000 else int(raw_price)
        raw_list = b.get("price_before_discount") or 0
        list_price = int(raw_list / 100000) if raw_list > 10000 else None

        discount_pct = None
        if list_price and list_price > price:
            discount_pct = round((1 - price / list_price) * 100)

        images = b.get("images", [])
        img_hash = images[0] if images else ""
        image_url = f"https://down-tw.img.susercontent.com/file/{img_hash}" if img_hash else ""

        shopid = b.get("shopid", "")
        itemid = b.get("itemid", "")
        buy_url = f"https://shopee.tw/product/{shopid}/{itemid}" if shopid and itemid else ""

        rating = b.get("item_rating", {})
        rating_val = rating.get("rating_star", None)

        if not price or not name:
            continue

        products.append({
            "site": "shopee",
            "code": str(itemid),
            "name": name,
            "price": price,
            "list_price": list_price,
            "discount_pct": discount_pct,
            "image_url": image_url,
            "buy_url": buy_url,
            "rating": f"{rating_val:.1f}" if rating_val else None,
            "review_count": str(b.get("sold", "")),
        })
    return products


async def search_shopee(query: str, limit: int = 6) -> list[dict]:
    """蝦皮搜尋，需要已儲存的 session cookies"""
    session = _load_shopee_cookies()
    if not session:
        return []  # 尚未登入，靜默略過

    cookie_str = "; ".join(f"{k}={v}" for k, v in session.get("cookies", {}).items())
    csrf = session.get("csrftoken", "")

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "zh-TW,zh;q=0.9",
        "Referer": f"https://shopee.tw/search?keyword={query}",
        "x-csrftoken": csrf,
        "Cookie": cookie_str,
    }
    url = (
        "https://shopee.tw/api/v4/search/search_items"
        f"?by=relevancy&keyword={httpx.QueryParams({'q': query}).get('q', query)}"
        "&limit=10&newest=0&order=desc&page_type=search&scenario=PAGE_GLOBAL_SEARCH&version=2"
    )
    async with httpx.AsyncClient(timeout=12) as client:
        r = await client.get(url, headers=headers)
        if r.status_code != 200:
            return []
        d = r.json()
        if d.get("error"):
            return []
        return _extract_shopee_products(d.get("items", []), limit)


# ── 跨站整合 ──────────────────────────────────────────────────────────────────

async def search_products(query: str, sites: Optional[list[str]] = None, limit: int = 6) -> list[dict]:
    """跨平台搜尋，momo + PChome + 博客來 + 蝦皮（有 session 時）同時跑，依價格排序"""
    if sites is None:
        sites = ["momo", "pchome", "books"]
        if _load_shopee_cookies():
            sites.append("shopee")
    tasks = []
    if "momo" in sites:
        tasks.append(search_momo(query, limit))
    if "pchome" in sites:
        tasks.append(search_pchome(query, limit))
    if "books" in sites:
        tasks.append(search_books(query, limit))
    if "shopee" in sites:
        tasks.append(search_shopee(query, limit))

    results_nested = await asyncio.gather(*tasks, return_exceptions=True)
    all_products = []
    for r in results_nested:
        if isinstance(r, list):
            all_products.extend(r)

    all_products.sort(key=lambda x: x["price"])
    return all_products[:limit]


def format_for_alfred(products: list[dict]) -> str:
    if not products:
        return "找不到相關商品，換個關鍵字試試。"
    lines = []
    for i, p in enumerate(products[:3], 1):
        disc = f"，省{p['discount_pct']}%" if p.get("discount_pct") else ""
        rating = f" ⭐{p['rating']}" if p.get("rating") else ""
        lines.append(f"{i}. [{p['site']}] {p['name'][:26]}　{p['price']:,}元{disc}{rating}")
    return "\n".join(lines)
