-- 商品主表
CREATE TABLE IF NOT EXISTS products (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    site             TEXT NOT NULL,
    code             TEXT NOT NULL,
    name             TEXT NOT NULL,
    brand            TEXT,
    category         TEXT,
    price            INTEGER NOT NULL,
    list_price       INTEGER,
    discount_pct     INTEGER,
    image_url        TEXT,
    buy_url          TEXT NOT NULL,
    rating           REAL,
    review_count     INTEGER,
    is_accessory     INTEGER DEFAULT 0,
    is_active        INTEGER DEFAULT 1,
    indexed_at       TEXT NOT NULL,
    price_updated_at TEXT NOT NULL,
    UNIQUE(site, code)
);

-- 全文搜尋索引
CREATE VIRTUAL TABLE IF NOT EXISTS products_fts USING fts5(
    name,
    brand,
    category,
    content=products,
    content_rowid=id,
    tokenize="unicode61"
);

-- FTS 觸發器（自動同步）
CREATE TRIGGER IF NOT EXISTS products_ai AFTER INSERT ON products BEGIN
    INSERT INTO products_fts(rowid, name, brand, category)
    VALUES (new.id, new.name, COALESCE(new.brand,''), COALESCE(new.category,''));
END;

CREATE TRIGGER IF NOT EXISTS products_au AFTER UPDATE ON products BEGIN
    INSERT INTO products_fts(products_fts, rowid, name, brand, category)
    VALUES('delete', old.id, old.name, COALESCE(old.brand,''), COALESCE(old.category,''));
    INSERT INTO products_fts(rowid, name, brand, category)
    VALUES (new.id, new.name, COALESCE(new.brand,''), COALESCE(new.category,''));
END;

-- 索引任務紀錄
CREATE TABLE IF NOT EXISTS index_jobs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    site       TEXT NOT NULL,
    category   TEXT,
    status     TEXT DEFAULT 'pending',
    products_indexed INTEGER DEFAULT 0,
    started_at TEXT,
    finished_at TEXT,
    error      TEXT
);

-- 索引統計
CREATE TABLE IF NOT EXISTS index_stats (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    recorded_at TEXT NOT NULL,
    total_products INTEGER,
    total_sites    INTEGER,
    last_full_update TEXT
);

CREATE INDEX IF NOT EXISTS idx_price ON products(price);
CREATE INDEX IF NOT EXISTS idx_site ON products(site);
CREATE INDEX IF NOT EXISTS idx_active ON products(is_active);
CREATE INDEX IF NOT EXISTS idx_updated ON products(price_updated_at);
CREATE INDEX IF NOT EXISTS idx_discount ON products(discount_pct);
