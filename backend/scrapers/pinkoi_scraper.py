"""
pinkoi_scraper.py — Pinkoi 設計師商品搜尋 scraper
方式：抓搜尋頁 HTML，解析 application/ld+json (Schema.org Product) 資料
每頁約 60 筆 Product，資料完整（productID / name / price / image / rating）
list_price 與 discount_pct：Pinkoi JSON-LD 不含原價資訊，統一回傳 None
"""

import re
import json
import asyncio
import time
from typing import Optional

import httpx

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.pinkoi.com/",
}

_SEARCH_URL = "https://www.pinkoi.com/search"


def _extract_products(html: str) -> list[dict]:
    """從搜尋頁 HTML 取出所有 Schema.org Product JSON-LD block"""
    ld_blocks = re.findall(
        r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    )
    products = []
    for block in ld_blocks:
        try:
            data = json.loads(block.strip())
            if data.get("@type") == "Product":
                products.append(data)
        except (json.JSONDecodeError, ValueError):
            continue
    return products


def _parse_product(data: dict) -> Optional[dict]:
    """把單筆 JSON-LD Product 轉成標準格式"""
    name = data.get("name", "").strip()
    code = data.get("productID", "").strip()
    if not name or not code:
        return None

    offers = data.get("offers", {})
    price_raw = offers.get("price")
    if price_raw is None:
        return None
    try:
        price = int(price_raw)
    except (TypeError, ValueError):
        return None

    # 商品圖片（取第一張）
    images = data.get("image", [])
    image_url = images[0] if images else ""

    # 商品頁 URL
    buy_url = offers.get("url", "") or f"https://www.pinkoi.com/product/{code}"

    # 評分
    rating: Optional[float] = None
    review_count: Optional[int] = None
    agg = data.get("aggregateRating", {})
    if agg:
        try:
            rating = float(agg["ratingValue"])
        except (KeyError, TypeError, ValueError):
            pass
        try:
            review_count = int(agg["reviewCount"])
        except (KeyError, TypeError, ValueError):
            pass

    return {
        "site": "pinkoi",
        "code": code,
        "name": name,
        "price": price,
        "list_price": None,       # Pinkoi JSON-LD 不提供原價
        "discount_pct": None,     # 同上
        "image_url": image_url,
        "buy_url": buy_url,
        "rating": rating,
        "review_count": review_count,
    }


async def search_pinkoi(query: str, limit: int = 6) -> list[dict]:
    """
    Pinkoi 設計師商品搜尋。

    Args:
        query: 搜尋關鍵字（中英文皆可，例如「手工皮革」「插畫印刷」）
        limit: 最多回傳幾筆，預設 6（單頁約 60 筆可選）

    Returns:
        list[dict]，每筆格式：
        {
            "site": "pinkoi",
            "code": "商品ID (8字元)",
            "name": "商品名稱",
            "price": 1280,             # 台幣整數
            "list_price": None,        # Pinkoi 無原價資料
            "discount_pct": None,      # Pinkoi 無折扣資料
            "image_url": "https://cdn01.pinkoi.com/...",
            "buy_url": "https://www.pinkoi.com/product/...",
            "rating": 4.8,             # 無評分時 None
            "review_count": 17,        # 無評論數時 None
        }
    """
    params = {"q": query}
    async with httpx.AsyncClient(
        headers=_HEADERS, timeout=15, follow_redirects=True
    ) as client:
        r = await client.get(_SEARCH_URL, params=params)
        r.raise_for_status()

    raw_products = _extract_products(r.text)

    results = []
    for raw in raw_products:
        p = _parse_product(raw)
        if p:
            results.append(p)
        if len(results) >= limit:
            break

    return results


# ── 快速測試 ──────────────────────────────────────────────────────────────────

async def _run_tests():
    queries = ["手工皮革", "插畫印刷"]
    for q in queries:
        t0 = time.perf_counter()
        results = await search_pinkoi(q, limit=6)
        elapsed = time.perf_counter() - t0
        print(f"\n=== {q} ({len(results)} 筆, {elapsed:.2f}s) ===")
        for p in results:
            rating_str = f"  ⭐{p['rating']}({p['review_count']})" if p.get("rating") else ""
            print(f"  [{p['code']}] {p['name'][:45]}  NT${p['price']:,}{rating_str}")
            print(f"         img: {p['image_url'][:70]}")
            print(f"         url: {p['buy_url'][:70]}")


if __name__ == "__main__":
    asyncio.run(_run_tests())
