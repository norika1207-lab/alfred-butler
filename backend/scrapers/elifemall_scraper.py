"""
elifemall_scraper.py — 全國電子 (ec.elifemall.com.tw) 商品搜尋 scraper
方式：直接呼叫 Nuxt SPA 後端 REST API
  GET https://ec.elifemall.com.tw/api/product?search=<query>&limit=<n>&page=1
  需帶 Accept: application/json，否則回傳空 body
回傳格式含 id / title / list_price / price / stock / main_images 等欄位。
"""

import asyncio
import json
import time
from typing import Optional

import httpx

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://ec.elifemall.com.tw/",
    "Origin": "https://ec.elifemall.com.tw",
}

_SEARCH_URL = "https://ec.elifemall.com.tw/api/product"
_PRODUCT_BASE = "https://ec.elifemall.com.tw/products"


def _parse_product(item: dict) -> Optional[dict]:
    """將 API 單筆商品資料轉成標準格式，失敗回傳 None。"""
    product_id = str(item.get("id", "")).strip()
    name = item.get("title", "").strip()
    if not product_id or not name:
        return None

    price = item.get("price")
    if price is None:
        return None
    try:
        price = int(price)
    except (ValueError, TypeError):
        return None

    list_price_raw = item.get("list_price")
    try:
        list_price: Optional[int] = int(list_price_raw) if list_price_raw is not None else None
    except (ValueError, TypeError):
        list_price = None

    # 若 list_price 等於 price，表示無折扣，設為 None
    if list_price is not None and list_price <= price:
        list_price = None

    discount_pct: Optional[int] = None
    if list_price and list_price > price:
        discount_pct = round((1 - price / list_price) * 100)

    # 商品主圖：優先取 medium，fallback thumb
    image_url = ""
    images_data = (item.get("main_images") or {}).get("data") or []
    if images_data:
        first = images_data[0]
        image_url = first.get("medium") or first.get("thumb") or ""

    buy_url = f"{_PRODUCT_BASE}/{product_id}"

    return {
        "site": "elifemall",
        "code": product_id,
        "name": name,
        "price": price,
        "list_price": list_price,
        "discount_pct": discount_pct,
        "image_url": image_url,
        "buy_url": buy_url,
        "rating": None,
        "review_count": None,
    }


async def search_elifemall(query: str, limit: int = 6) -> list[dict]:
    """
    全國電子商品搜尋。
    方式：直接呼叫 ec.elifemall.com.tw REST API（Nuxt SPA 後端），
          GET /api/product?search=<query>&limit=<n>&page=1
          需帶 Accept: application/json。
    回傳最多 limit 筆，每筆格式：
        site / code / name / price / list_price / discount_pct /
        image_url / buy_url / rating / review_count
    """
    async with httpx.AsyncClient(
        headers=_HEADERS,
        timeout=15,
        follow_redirects=True,
    ) as client:
        r = await client.get(
            _SEARCH_URL,
            params={"search": query, "limit": limit, "page": 1},
        )
        r.raise_for_status()

    try:
        data = r.json()
    except Exception:
        return []

    raw_items = data.get("data") or []
    products: list[dict] = []
    for item in raw_items[:limit]:
        parsed = _parse_product(item)
        if parsed:
            products.append(parsed)

    return products


# ── 測試 ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    async def main():
        queries = ["AirPods Pro", "電動牙刷"]
        for q in queries:
            t0 = time.time()
            results = await search_elifemall(q, limit=6)
            elapsed = round(time.time() - t0, 2)
            print(f"\n===== 搜尋: {q} ({elapsed}s, {len(results)} 筆) =====")
            for item in results:
                print(json.dumps(item, ensure_ascii=False, indent=2))

    asyncio.run(main())
