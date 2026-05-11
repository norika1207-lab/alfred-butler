"""
indexer/search.py — 索引查詢引擎（< 100ms）

優先查本地索引；索引量不足時自動 fallback 到即時爬蟲。
"""
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scrapers"))

from indexer.db import search_index, get_stats
from indexer.query_parser import parse, is_accessory


INDEX_MIN_THRESHOLD = 1000   # 至少 1000 筆才走索引路徑
STALE_SECONDS = 3600 * 2     # 超過 2 小時未更新視為過舊


async def search_from_index(query: str, limit: int = 8) -> dict:
    """
    主查詢入口。回傳：
    {
        "products": [...],
        "elapsed_ms": 42,
        "source": "index" | "realtime",
        "total_in_index": 12345,
        "query_parsed": {...}
    }
    """
    t0 = time.time()
    pq = parse(query)

    stats = get_stats()
    total = stats.get("total_products", 0)
    use_index = total >= INDEX_MIN_THRESHOLD

    if use_index:
        results = search_index(
            pq.fts_query,
            limit=limit * 2,          # 多拿一些，過濾後再截
            min_price=pq.min_price,
        )
        # 再過一次配件過濾
        results = [
            r for r in results
            if not is_accessory(r["name"], pq.core_terms)
        ][:limit]
        source = "index"
    else:
        # Fallback：即時爬蟲
        from shop_service import search_products
        results = await search_products(query, limit=limit)
        source = "realtime"

    elapsed_ms = int((time.time() - t0) * 1000)

    return {
        "products": results,
        "elapsed_ms": elapsed_ms,
        "source": source,
        "total_in_index": total,
        "query_parsed": {
            "core_terms": pq.core_terms,
            "brand": pq.brand,
            "category": pq.category,
            "min_price": pq.min_price,
        },
    }
