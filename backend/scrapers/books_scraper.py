"""
books_scraper.py — 博客來 (books.com.tw) 商品搜尋 scraper
方式：HTML parse（mobile UA 繞過 WAF）
"""

import re
import asyncio
import time
from typing import Optional

import httpx
from bs4 import BeautifulSoup

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.0 Mobile/15E148 Safari/604.1"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
}

_SEARCH_URL = "https://search.books.com.tw/search/query/key/{key}"


def _extract_code_from_id(item_id: str) -> str:
    """從 li id='prod-itemlist-XXXX' 取出商品代碼"""
    m = re.search(r"prod-itemlist-(.+)", item_id)
    return m.group(1) if m else item_id


def _extract_image_url(img_tag) -> str:
    """從 img 的 data-src 取出原始圖片 URL（去掉縮圖參數）"""
    if img_tag is None:
        return ""
    src = img_tag.get("data-src") or img_tag.get("src", "")
    # data-src 形式：https://im1.book.com.tw/image/getImage?i=https://www.books.com.tw/img/...&w=187&h=187&v=xxx
    m = re.search(r"[?&]i=(https://[^&]+)", src)
    if m:
        return m.group(1)
    return src


def _extract_price(price_tag) -> tuple[Optional[int], Optional[int]]:
    """回傳 (price, list_price)，都是 int 或 None"""
    if price_tag is None:
        return None, None

    # 現價：<b>6690</b>
    b_tag = price_tag.find("b")
    price_str = b_tag.get_text(strip=True) if b_tag else ""
    price = int(re.sub(r"[^0-9]", "", price_str)) if price_str else None

    # 定價：<del>7500</del>
    del_tag = price_tag.find("del")
    list_str = del_tag.get_text(strip=True) if del_tag else ""
    list_price = int(re.sub(r"[^0-9]", "", list_str)) if list_str else None

    return price, list_price


def _parse_items(html: str, limit: int) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    items = soup.select("li.item")
    products = []

    for item in items[:limit]:
        # 商品代碼
        item_id = item.get("id", "")
        code = _extract_code_from_id(item_id)
        if not code:
            continue

        # 商品名稱
        name_tag = item.select_one("h4 a")
        if not name_tag:
            continue
        name = name_tag.get_text(separator="", strip=True)
        if not name:
            continue

        # 圖片
        img_tag = item.select_one("img[data-src]")
        image_url = _extract_image_url(img_tag)

        # 價格
        price_tag = item.select_one("p.price")
        price, list_price = _extract_price(price_tag)
        if not price:
            continue

        # 折扣百分比
        discount_pct: Optional[int] = None
        if list_price and list_price > price:
            discount_pct = round((1 - price / list_price) * 100)

        # 購買連結
        buy_url = f"https://www.books.com.tw/products/{code}"

        products.append({
            "site": "books",
            "code": code,
            "name": name,
            "price": price,
            "list_price": list_price,
            "discount_pct": discount_pct,
            "image_url": image_url,
            "buy_url": buy_url,
            "rating": None,     # 搜尋頁無評分資料
            "review_count": None,
        })

    return products


async def search_books(query: str, limit: int = 6) -> list[dict]:
    """
    博客來商品搜尋。
    回傳最多 limit 筆，每筆格式：
        site / code / name / price / list_price / discount_pct /
        image_url / buy_url / rating / review_count
    """
    encoded = httpx.QueryParams({"key": query}).get("key", query)
    url = _SEARCH_URL.format(key=encoded)

    async with httpx.AsyncClient(
        headers=_HEADERS,
        timeout=15,
        follow_redirects=True,
    ) as client:
        r = await client.get(url)
        r.raise_for_status()

    # WAF 攔截時回傳極短 HTML（< 5000 chars）
    if len(r.text) < 5000:
        return []

    return _parse_items(r.text, limit)


# ── 測試 ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    async def main():
        queries = ["AirPods Pro", "電動牙刷"]
        for q in queries:
            t0 = time.time()
            results = await search_books(q, limit=6)
            elapsed = round(time.time() - t0, 2)
            print(f"\n===== 搜尋: {q} ({elapsed}s, {len(results)} 筆) =====")
            for r in results:
                print(json.dumps(r, ensure_ascii=False, indent=2))

    asyncio.run(main())
