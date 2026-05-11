"""
indexer/scheduler.py — 每 30 分鐘自動更新索引

執行：python3 -m indexer.scheduler
nohup python3 backend/indexer/scheduler.py &
"""
import asyncio
import logging
import time
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scrapers"))

from indexer.db import init_db, get_stats
from indexer.crawler import run_all_agents

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [scheduler] %(message)s",
    handlers=[
        logging.FileHandler("/opt/alfred/data/indexer.log"),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger("scheduler")

UPDATE_INTERVAL = 30 * 60   # 30 分鐘


async def run_cycle():
    start = datetime.now()
    log.info(f"=== 索引更新開始 {start.strftime('%H:%M:%S')} ===")
    t0 = time.time()

    results = await run_all_agents()

    elapsed = time.time() - t0
    stats = get_stats()
    total_indexed = sum(r.get("indexed", 0) for r in results if isinstance(r, dict))
    total_errors  = sum(r.get("errors",  0) for r in results if isinstance(r, dict))

    log.info(
        f"=== 完成 | 耗時 {elapsed:.0f}s | "
        f"本輪寫入 {total_indexed:,} 筆 | "
        f"DB 總量 {stats['total_products']:,} 筆 | "
        f"失敗 {total_errors} 次 ==="
    )
    return stats


async def main():
    init_db()
    log.info("索引排程器啟動")
    log.info(f"更新間隔: 每 {UPDATE_INTERVAL//60} 分鐘")

    while True:
        try:
            await run_cycle()
        except Exception as e:
            log.error(f"更新失敗: {e}")
        log.info(f"下次更新: {UPDATE_INTERVAL//60} 分鐘後")
        await asyncio.sleep(UPDATE_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
