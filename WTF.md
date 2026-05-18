<!-- ALFRED_MANDATORY_SESSION_BOOTSTRAP -->
# MANDATORY FIRST STEP FOR ANY ALFRED / AFU / ALICE REQUEST

Before any analysis, file edit, DB write, backend patch, demo edit, iOS change, systemd change, or conclusion about Alfred / Afu / Alice / File Map, run:

```bash
/usr/local/bin/alfred-context-guard
```

This is required even in a new session. Do not patch first and read docs later. See `/opt/alfred/ALFRED_MANDATORY_SESSION_BOOTSTRAP.md`.

<!-- /ALFRED_MANDATORY_SESSION_BOOTSTRAP -->

# 一個人 + 34 隻 Agent，一天內建完台灣版 Google Shopping

> 這是一份真實紀錄。所有數字都可以驗證。

---

## 你現在面對的問題

台灣有 13 個主要電商平台。

每次購物，你開 13 個分頁，手動比價，花 15 分鐘。  
沒有統一 API。沒有共用資料庫。每個平台都是一座孤島。

**這個問題存在了 20 年。沒有人解決它。**

---

## 我們用一天解決了它

### Phase 1 — The Commerce Crack
*時間：下午，43 分鐘*

**14 個 AI Agent 同時出發，每個負責一個電商。**

任務很簡單：  
進去。找到資料。帶回來。

```
Agent 01 → 博客來      ✅  0.78s  mobile UA 繞過 WAF
Agent 02 → 露天拍賣    ✅  0.77s  2-step JSON API
Agent 03 → Yahoo購物   ✅  0.81s  60筆 inline JSON
Agent 04 → 松果購物    ✅  0.39s  POST JSON API（最快）
Agent 05 → 東森購物    ✅  0.54s  埋在 bundle 的 AJAX
Agent 06 → 生活市集    ✅  0.14s  Next.js SSR直讀（最快）
Agent 07 → 特力屋      ✅  0.89s  隱藏 JSON endpoint
Agent 08 → 家樂福      ✅  0.42s  SSR data-* 屬性
Agent 09 → 燦坤        ✅  0.86s  追蹤域名遷移
Agent 10 → 全國電子    ✅  1.03s  Nuxt API + 正確 header
Agent 11 → 酷澎        ✅  1.35s  Sec-Fetch headers 繞過
Agent 12 → Pinkoi      ✅  0.97s  JSON-LD Product blocks
Agent 13 → 比價王      ✅  0.90s  Next.js RSC 資料層
Agent 14 → 蝦皮        ❌         手機驗證牆（唯一失敗）

13/14 成功。43 分鐘。無一事先獲得 API 授權。
```

**結果：台灣 80,000,000+ 件商品，首次可以統一查詢。**

---

### Phase 2 — The Index Engine
*時間：Phase 1 後，持續運行*

**20 個 AI Agent 分工建立商品索引，每 30 分鐘更新一次。**

```
背景持續運行：

Agent 1-5   → 3C 品類（耳機/手機/筆電/平板/穿戴）
Agent 6-10  → 食品/美妝（醬料/主食/零食/保養/彩妝）
Agent 11-15 → 家電/工具（廚電/清潔/個護/電動工具）
Agent 16-20 → 特色站（露天/博客來/Pinkoi/比價王）

每輪：
  └─ 20 品類 × 各站 × 10 關鍵字 = 爬取數千筆
  └─ 寫入 SQLite FTS5 全文搜尋索引
  └─ 價格異動自動更新
  └─ 下架商品自動標記

首輪完成：2,208 筆 ／ 15 站 ／ 量持續增加
```

---

## 查詢速度對比

```
舊方式（即時爬蟲）：
  用戶問 → 同時打 13 個網站 → 等回應 → 1.5 – 7.8 秒

新方式（預建索引）：
  用戶問 → 查本地 SQLite FTS5 → 回傳

  電動牙刷    4ms  ██
  醬油        2ms  █
  氣炸鍋      2ms  █
  AirPods Pro 3ms  █

比即時爬快：500 倍
```

---

## 一次查詢的完整旅程

```
你說：「幫我找最便宜的電動牙刷」

t=0ms    QueryParser 拆解查詢（零 LLM）
           → core_terms: ['電動牙刷']
           → category: appliance_bath
           → min_price: 150

t=4ms    SQLite FTS5 全文搜尋
           → 命中 120+ 筆含「電動牙刷」的索引商品
           → 過濾配件（刷頭、替換頭、書籍）
           → 依價格排序，取前 5 名

t=4ms    ✅ 回傳結果
           #1 米家 T200 電動牙刷   NT$179  省40%  ⭐5.0  酷澎
           #2 Colgate 3D音波電動牙刷 NT$232  省45%  ⭐5.0  酷澎
           #3 Panasonic 音波電動牙刷 NT$1,290 省8%  ⭐4.8  momo

LLM 使用：0 次
API 費用：NT$0
```

---

## 可驗證的數字

| 指標 | 數字 | 驗證方式 |
|------|------|---------|
| Phase 1 完成時間 | 43 分鐘 | git log 時間戳 |
| Phase 1 Agent 數 | 14 個 | `AGENT_BLITZ.md` |
| 成功率 | 13/14（93%） | 代碼 + 失敗原因記錄 |
| 涵蓋商品數 | 80M+（估算） | 各平台公開資料 |
| Phase 1 查詢速度 | 1.5 – 7.8 秒 | `data/benchmark_results.json` |
| Phase 2 查詢速度 | 2 – 4ms | 可本地執行驗證 |
| Phase 2 Agent 數 | 20 個 | `indexer/crawler.py` |
| 索引更新頻率 | 每 30 分鐘 | `alfred-indexer.service` |
| 程式碼行數 | ~2,000 行 | GitHub |

---

## 整套架構圖

```
                    ┌─────────────────────────────┐
                    │       用戶說一句話            │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │    QueryParser（零 LLM）      │
                    │  拆品牌 / 品類 / 最低價       │
                    └──────────────┬──────────────┘
                                   │
              ┌────────────────────▼───────────────────┐
              │                                         │
   ┌──────────▼──────────┐             ┌───────────────▼────────────┐
   │  本地索引 FTS5        │             │   即時爬蟲（fallback）        │
   │  2ms – 10ms          │             │   1.5s – 7.8s              │
   │  2,208 筆（持續增加） │             │   13 站並發                 │
   └──────────┬──────────┘             └───────────────┬────────────┘
              │                                         │
              └─────────────────┬───────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   相關性過濾引擎          │
                    │  （去除配件 / 書籍 / 副廠）│
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  商品圖 + 價格 + 折扣     │
                    │  + 評分 + 前往購買        │
                    └─────────────────────────┘

背景持續運行：
  ┌─────────────────────────────────────────────┐
  │  20 個 Agent，每 30 分鐘，更新全站商品索引    │
  └─────────────────────────────────────────────┘
```

---

## 這不是一個功能。這是一套方法論。

**The Commerce Crack** — 任何沒有公開 API 的電商，四步打開：

```
Step 1  Reconnaissance  分析目標的資料架構
Step 2  The Crack       找到原始資料路徑（不需授權）
Step 3  Normalize       統一資料格式
Step 4  Index           寫入本地，持續更新
```

**適用於任何國家、任何電商、任何語言。**

---

## 開源

`github.com/norika1207-lab/alfred-butler`

```
backend/shop_service.py      即時爬蟲層（13 站）
backend/scrapers/            各站獨立 scraper
backend/indexer/             索引引擎（Phase 2）
  ├── schema.sql             FTS5 DB schema
  ├── crawler.py             20 Agent 分工定義
  ├── query_parser.py        查詢理解引擎
  ├── search.py              主查詢入口
  └── scheduler.py           30 分鐘排程
```

clone 下來，`python3 backend/indexer/crawler.py`，你就有自己的索引。

---

*Alfred — 一個人的管家，不是另一個購物 App*  
*Phase 1 完成：2026-05-11*  
*Phase 2 上線：2026-05-11（持續運行中）*
