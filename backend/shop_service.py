"""
shop_service.py — 台灣電商比價引擎
純演算法，零 LLM。抓商品名稱、價格、折扣、規格、一張圖。
目前支援：momo
"""
import re
import json
import asyncio
import httpx
from typing import Optional

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.0 Mobile/15E148 Safari/604.1"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _extract_momo_products(html: str, limit: int = 6) -> list[dict]:
    """從 momo JSON-LD 抽商品清單（結構最穩定）"""
    # 找 application/ld+json 裡的 ItemList
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

    # JSON-LD 結構是 @graph 陣列，找 ItemList 那個節點
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

        # 從 buy_url 取 i_code
        code_m = re.search(r"i_code=(\d+)", buy_url)
        code = code_m.group(1) if code_m else ""
        canonical_url = f"https://www.momoshop.com.tw/goods/GoodsDetail.jsp?i_code={code}" if code else buy_url

        # 嘗試從 escaped JS 抽原價（有就有，沒有不影響）
        list_price = _extract_list_price(html, code) if code else None
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


def _extract_list_price(html: str, code: str) -> Optional[int]:
    """嘗試從 Next.js hydration data 抽原價"""
    m = re.search(
        rf'\\\\?"goodsCode\\\\?":\\\\?"0*{code}\\\\?".*?\\\\?"listPrice\\\\?":\\\\?"([^"\\\\]+)',
        html
    )
    if m:
        raw = m.group(1)
        digits = re.sub(r"[^0-9]", "", raw)
        return int(digits) if digits else None
    return None


async def search_momo(query: str, limit: int = 6) -> list[dict]:
    params = httpx.QueryParams({"keyword": query, "searchType": "1", "ent": "k", "curPage": "1"})
    url = f"https://www.momoshop.com.tw/search/searchShop.jsp?{params}"
    async with httpx.AsyncClient(headers=_HEADERS, timeout=15, follow_redirects=True) as client:
        r = await client.get(url)
        r.raise_for_status()
    return _extract_momo_products(r.text, limit)


async def search_products(query: str, sites: Optional[list[str]] = None, limit: int = 6) -> list[dict]:
    """跨平台搜尋，回傳依價格排序的結果"""
    sites = sites or ["momo"]
    tasks = []
    if "momo" in sites:
        tasks.append(search_momo(query, limit))
    results_nested = await asyncio.gather(*tasks, return_exceptions=True)
    all_products = []
    for r in results_nested:
        if isinstance(r, list):
            all_products.extend(r)
    all_products.sort(key=lambda x: x["price"])
    return all_products[:limit]


def format_for_alfred(products: list[dict]) -> str:
    """把商品清單格式化成 Alfred 語音摘要"""
    if not products:
        return "找不到相關商品，換個關鍵字試試。"
    lines = []
    for i, p in enumerate(products[:3], 1):
        disc = f"，省 {p['discount_pct']}%" if p.get("discount_pct") else ""
        rating = f"，評分 {p['rating']}" if p.get("rating") else ""
        lines.append(f"{i}. {p['name'][:28]}　{p['price']:,} 元{disc}{rating}")
    return "\n".join(lines)
