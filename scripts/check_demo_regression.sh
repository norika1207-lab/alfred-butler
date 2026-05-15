#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:9001}"

run_case() {
  local name="$1"
  local msg="$2"
  shift 2
  echo "== $name =="
  local body
  body="$(python3 - "$msg" <<'PY'
import json, sys
print(json.dumps({"message": sys.argv[1], "history": []}, ensure_ascii=False))
PY
)"
  local out
  out="$(curl -sS --max-time 45 -X POST "$BASE_URL/api/chat" \
    -H 'Content-Type: application/json' \
    -d "$body")"
  local text
  text="$(python3 - "$out" <<'PY'
import json, sys
data = json.loads(sys.argv[1])
text = data.get("text", "")
print(text.replace("\n", " "))
PY
)"
  printf '%s\n' "${text:0:900}"
  for forbidden in "$@"; do
    if printf '%s' "$text" | grep -q "$forbidden"; then
      echo "FAIL: forbidden phrase hit in spoken text: $forbidden" >&2
      exit 1
    fi
  done
}

run_case "breakfast_no_silence" "我想要吃早餐" "處理完了,但這次沒有可回報" "好的，主人。$" "查不到"
run_case "burger_breakfast_no_oil_rice" "我想吃有關漢堡類的早餐" "油飯" "蚵仔"
run_case "yesterday_ai_news_no_refusal" "我想要聽昨天的AI新聞" "只能搜尋最新" "無法精確指定"
run_case "techcrunch_no_file_search" "阿弗那你到國外的網站像TechCrunch或是相關的科技網站去找" "索引裡沒有找到" "文件"
run_case "japan_travel_no_no_data" "阿甫,幫我安排5月下週的日本旅行行程四個人,兩大、兩小、最小的5歲,幫我安排" "沒有日本的完整旅遊資料" "目前資料庫還沒有 日本" "講日本範圍太大，我先以東京當底替您草擬" "卡片" "放在卡片" "合約" "文件"
run_case "nearby_hotpot_not_ack_only" "這個阿福我現在在新北市泰山信華六街5號這邊告訴我這邊一公里內的麻辣火鍋店有哪些" "^好的，主人。$" "處理完了,但這次沒有可回報" "蔥抓餅" "牛肉麵" "水餃" "張記小吃"

echo "demo regression ok"


echo "== travel_zero_ui_no_card =="
python3 - <<'PY'
import json, sys, urllib.request
msg = "阿甫,幫我安排5月下週的日本旅行行程四個人,兩大、兩小、最小的5歲,幫我安排"
body = json.dumps({"message": msg, "history": []}, ensure_ascii=False).encode()
req = urllib.request.Request("http://127.0.0.1:9001/api/chat", data=body, headers={"Content-Type": "application/json"})
data = json.loads(urllib.request.urlopen(req, timeout=45).read().decode())
if data.get("card") is not None:
    print("FAIL: travel returned a UI card", file=sys.stderr)
    sys.exit(1)
text = data.get("text", "")
if "LINE" not in text and "Email" not in text:
    print("FAIL: travel did not mention quiet delivery channel", file=sys.stderr)
    sys.exit(1)
print("travel zero-ui ok")
PY
