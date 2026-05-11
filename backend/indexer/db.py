"""
indexer/db.py — 商品索引資料庫管理
"""
import sqlite3
import os
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent.parent.parent / "data" / "product_index.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=10000")
    return conn


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_db()
    schema = SCHEMA_PATH.read_text()
    conn.executescript(schema)
    conn.commit()
    conn.close()


def upsert_products(products: list[dict]) -> int:
    """批量寫入/更新商品。回傳成功筆數。"""
    if not products:
        return 0
    now = datetime.now().isoformat()
    conn = get_db()
    count = 0
    try:
        for p in products:
            conn.execute("""
                INSERT INTO products
                    (site, code, name, brand, category, price, list_price,
                     discount_pct, image_url, buy_url, rating, review_count,
                     is_accessory, is_active, indexed_at, price_updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?)
                ON CONFLICT(site, code) DO UPDATE SET
                    name             = excluded.name,
                    price            = excluded.price,
                    list_price       = excluded.list_price,
                    discount_pct     = excluded.discount_pct,
                    image_url        = excluded.image_url,
                    rating           = excluded.rating,
                    review_count     = excluded.review_count,
                    is_active        = 1,
                    price_updated_at = excluded.price_updated_at
            """, (
                p.get("site", ""),
                p.get("code", ""),
                p.get("name", ""),
                p.get("brand"),
                p.get("category"),
                p.get("price", 0),
                p.get("list_price"),
                p.get("discount_pct"),
                p.get("image_url", ""),
                p.get("buy_url", ""),
                p.get("rating"),
                p.get("review_count"),
                int(p.get("is_accessory", 0)),
                now, now,
            ))
            count += 1
        conn.commit()
    finally:
        conn.close()
    return count


def search_index(query: str, limit: int = 8, min_price: int = 0,
                 sites: list[str] | None = None) -> list[dict]:
    """從本地索引搜尋商品，< 50ms。"""
    conn = get_db()
    try:
        # FTS5 全文搜尋
        fts_query = " OR ".join(f'"{t}"' for t in query.split() if t)
        site_filter = ""
        params: list = [fts_query, min_price]
        if sites:
            site_filter = f"AND p.site IN ({','.join('?'*len(sites))})"
            params.extend(sites)
        params.append(limit)

        rows = conn.execute(f"""
            SELECT p.site, p.code, p.name, p.brand, p.category,
                   p.price, p.list_price, p.discount_pct,
                   p.image_url, p.buy_url, p.rating, p.review_count,
                   p.price_updated_at
            FROM products_fts f
            JOIN products p ON p.id = f.rowid
            WHERE products_fts MATCH ?
              AND p.is_active = 1
              AND p.is_accessory = 0
              AND p.price >= ?
              {site_filter}
            ORDER BY p.price ASC
            LIMIT ?
        """, params).fetchall()

        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_stats() -> dict:
    conn = get_db()
    try:
        total = conn.execute("SELECT COUNT(*) FROM products WHERE is_active=1").fetchone()[0]
        sites = conn.execute(
            "SELECT site, COUNT(*) as cnt FROM products WHERE is_active=1 GROUP BY site ORDER BY cnt DESC"
        ).fetchall()
        last_update = conn.execute(
            "SELECT MAX(price_updated_at) FROM products"
        ).fetchone()[0]
        return {
            "total_products": total,
            "sites": {r["site"]: r["cnt"] for r in sites},
            "last_update": last_update,
        }
    finally:
        conn.close()
