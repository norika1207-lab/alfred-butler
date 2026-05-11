"""
indexer/crawler.py — 20 Agent 分工索引爬蟲

每個 site_task 定義一個站點 + 品類組合。
執行時：fetch → normalize → upsert → log
"""
import asyncio
import sys
import time
import logging
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scrapers"))

from indexer.db import init_db, upsert_products, get_stats
from indexer.query_parser import is_accessory

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("crawler")

# ── 品類關鍵字清單 ─────────────────────────────────────────────────────────────
CATEGORIES = {
    "3c_earphone":  ["AirPods Pro", "AirPods", "藍牙耳機", "TWS耳機", "Sony WH", "Sony WF"],
    "3c_phone":     ["iPhone 15", "iPhone 16", "Samsung Galaxy", "小米手機", "ASUS手機"],
    "3c_laptop":    ["MacBook", "ASUS筆電", "Lenovo ThinkPad", "HP筆電", "Dell筆電"],
    "3c_tablet":    ["iPad", "Samsung Galaxy Tab", "小米平板"],
    "3c_watch":     ["Apple Watch", "Galaxy Watch", "小米手環", "Garmin"],
    "appliance_kitchen": ["氣炸鍋", "咖啡機", "電鍋", "果汁機", "烤箱", "麵包機"],
    "appliance_clean":   ["掃地機器人", "吸塵器", "洗碗機", "空氣清淨機"],
    "appliance_bath":    ["電動牙刷", "吹風機", "電動刮鬍刀", "洗臉機"],
    "food_sauce":   ["醬油", "辣椒醬", "沙茶醬", "番茄醬", "魚露"],
    "food_staple":  ["白米", "麵條", "燕麥", "糙米", "義大利麵"],
    "food_snack":   ["洋芋片", "餅乾", "巧克力", "堅果", "果乾"],
    "beauty_skin":  ["面膜", "防曬乳", "乳液", "精華液", "卸妝"],
    "beauty_hair":  ["洗髮精", "護髮素", "造型品"],
    "tools_power":  ["電鑽", "電動起子", "砂輪機", "電鋸", "熱風槍"],
    "tools_hand":   ["螺絲起子", "扳手", "剪刀", "美工刀"],
    "home_light":   ["LED燈泡", "燈管", "吸頂燈", "檯燈"],
    "home_decor":   ["收納盒", "置物架", "掛鉤", "窗簾"],
    "pet":          ["狗飼料", "貓飼料", "貓砂", "寵物零食"],
    "sport":        ["瑜珈墊", "啞鈴", "跳繩", "運動水壺"],
    "book_tech":    ["Python", "JavaScript", "機器學習", "設計"],
}

# ── 20 Agent 分工表 ────────────────────────────────────────────────────────────
AGENT_TASKS = [
    # Agent 1-5: 3C
    {"agent": 1,  "site": "momo",      "categories": ["3c_earphone", "3c_phone"]},
    {"agent": 2,  "site": "pchome",    "categories": ["3c_earphone", "3c_laptop", "3c_tablet"]},
    {"agent": 3,  "site": "coupang",   "categories": ["3c_earphone", "appliance_bath", "appliance_kitchen"]},
    {"agent": 4,  "site": "yahoo",     "categories": ["3c_earphone", "3c_phone", "3c_watch"]},
    {"agent": 5,  "site": "elifemall", "categories": ["3c_earphone", "3c_laptop", "appliance_clean"]},
    # Agent 6-10: 食品/日用
    {"agent": 6,  "site": "carrefour", "categories": ["food_sauce", "food_staple", "food_snack"]},
    {"agent": 7,  "site": "momo",      "categories": ["food_sauce", "food_snack", "beauty_skin"]},
    {"agent": 8,  "site": "yahoo",     "categories": ["food_staple", "beauty_skin", "beauty_hair"]},
    {"agent": 9,  "site": "buy123",    "categories": ["food_sauce", "beauty_skin", "home_decor"]},
    {"agent": 10, "site": "pinecone",  "categories": ["food_snack", "beauty_skin", "pet"]},
    # Agent 11-15: 家電/五金
    {"agent": 11, "site": "momo",      "categories": ["appliance_kitchen", "appliance_clean"]},
    {"agent": 12, "site": "etmall",    "categories": ["appliance_kitchen", "appliance_bath"]},
    {"agent": 13, "site": "trplus",    "categories": ["tools_power", "tools_hand", "home_light"]},
    {"agent": 14, "site": "tkec",      "categories": ["3c_earphone", "3c_laptop", "appliance_kitchen"]},
    {"agent": 15, "site": "pchome",    "categories": ["appliance_kitchen", "appliance_clean", "tools_power"]},
    # Agent 16-20: 特色站
    {"agent": 16, "site": "ruten",     "categories": ["3c_earphone", "3c_phone", "appliance_kitchen"]},
    {"agent": 17, "site": "ruten",     "categories": ["food_sauce", "food_staple", "tools_hand"]},
    {"agent": 18, "site": "books",     "categories": ["book_tech", "appliance_bath", "sport"]},
    {"agent": 19, "site": "pinkoi",    "categories": ["home_decor", "pet", "sport"]},
    {"agent": 20, "site": "biggo",     "categories": ["3c_earphone", "appliance_kitchen", "beauty_skin"]},
]

# 站點搜尋函數映射
async def _get_search_fn(site: str):
    if site == "momo":
        from shop_service import search_momo
        return search_momo
    elif site == "pchome":
        from shop_service import search_pchome
        return search_pchome
    elif site == "coupang":
        from scrapers.coupang_scraper import search_coupang
        return search_coupang
    elif site == "yahoo":
        from scrapers.yahoo_scraper import search_yahoo_shopping
        return search_yahoo_shopping
    elif site == "elifemall":
        from scrapers.elifemall_scraper import search_elifemall
        return search_elifemall
    elif site == "carrefour":
        from scrapers.carrefour_scraper import search_carrefour
        return search_carrefour
    elif site == "buy123":
        from scrapers.buy123_scraper import search_buy123
        return search_buy123
    elif site == "pinecone":
        from shop_service import search_pinecone
        return search_pinecone
    elif site == "etmall":
        from shop_service import search_etmall
        return search_etmall
    elif site == "trplus":
        from scrapers.trplus_scraper import search_trplus
        return search_trplus
    elif site == "tkec":
        from scrapers.tkec_scraper import search_tkec
        return search_tkec
    elif site == "ruten":
        from shop_service import search_ruten
        return search_ruten
    elif site == "books":
        from scrapers.books_scraper import search_books
        return search_books
    elif site == "pinkoi":
        from scrapers.pinkoi_scraper import search_pinkoi
        return search_pinkoi
    elif site == "biggo":
        from scrapers.biggo_scraper import search_biggo
        return search_biggo
    return None


async def run_agent(agent_id: int, site: str, categories: list[str],
                    log_cb=None) -> dict:
    """單一 Agent 執行：爬取指定站點的所有品類關鍵字，寫入索引。"""
    result = {"agent": agent_id, "site": site, "indexed": 0,
              "categories": len(categories), "errors": 0, "elapsed": 0}
    t0 = time.time()

    search_fn = await _get_search_fn(site)
    if not search_fn:
        result["errors"] = 1
        return result

    for cat_key in categories:
        keywords = CATEGORIES.get(cat_key, [])
        for kw in keywords:
            try:
                products = await search_fn(kw, limit=10)
                # 標記配件
                for p in products:
                    p["category"] = cat_key
                    p["is_accessory"] = 1 if is_accessory(
                        p.get("name", ""), kw.split()
                    ) else 0
                n = upsert_products(products)
                result["indexed"] += n
                if log_cb:
                    log_cb(agent_id, site, kw, n)
                await asyncio.sleep(0.2)  # 避免打爆站點
            except Exception as e:
                result["errors"] += 1
                log.warning(f"Agent {agent_id} [{site}] {kw}: {e}")

    result["elapsed"] = round(time.time() - t0, 1)
    return result


async def run_all_agents(log_cb=None) -> list[dict]:
    """20 個 Agent 全部並發執行。"""
    tasks = [
        run_agent(t["agent"], t["site"], t["categories"], log_cb)
        for t in AGENT_TASKS
    ]
    return await asyncio.gather(*tasks, return_exceptions=False)


async def run_price_update() -> dict:
    """快速價格更新模式：只更新已索引商品的最新價格。"""
    stats = get_stats()
    log.info(f"Price update start. Current index: {stats['total_products']:,} products")
    results = await run_all_agents()
    new_stats = get_stats()
    return {
        "before": stats["total_products"],
        "after": new_stats["total_products"],
        "delta": new_stats["total_products"] - stats["total_products"],
        "agent_results": results,
    }


if __name__ == "__main__":
    init_db()
    log.info("Index DB initialized")

    printed = []
    def on_index(agent_id, site, kw, n):
        msg = f"  Agent {agent_id:2d} [{site:10}] {kw:20} → {n} 筆"
        print(msg)
        printed.append(msg)

    print(f"\n{'='*60}")
    print(f"Operation Phase 2 — Index Engine Boot")
    print(f"20 Agents deploying at {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}\n")

    t0 = time.time()
    results = asyncio.run(run_all_agents(on_index))
    elapsed = time.time() - t0

    stats = get_stats()
    total_indexed = sum(r.get("indexed", 0) for r in results if isinstance(r, dict))
    total_errors = sum(r.get("errors", 0) for r in results if isinstance(r, dict))

    print(f"\n{'='*60}")
    print(f"完成時間: {datetime.now().strftime('%H:%M:%S')}")
    print(f"總耗時:   {elapsed:.1f}s")
    print(f"寫入商品: {total_indexed:,} 筆")
    print(f"DB 總量:  {stats['total_products']:,} 筆")
    print(f"失敗次數: {total_errors}")
    print(f"\n各站商品數:")
    for site, cnt in sorted(stats["sites"].items(), key=lambda x: -x[1]):
        bar = "█" * min(cnt // 10, 40)
        print(f"  {site:12} {cnt:6,} {bar}")
    print(f"{'='*60}\n")
