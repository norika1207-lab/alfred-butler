#!/bin/bash
# Alfred 跨裝置同步狀態檢查
# 用法: ssh 進 VPS 後輸入 `alfred`

set +e
DATA=/opt/alfred/data

echo "════════════════════════════════════════════════════════════════"
echo "  ⚙️  阿福同步狀態檢查 (稍等 5-10 秒)"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Service 狀態
echo "▸ Service 狀態"
if systemctl is-active --quiet alfred; then
    echo "  ✅ alfred service: active"
else
    echo "  ❌ alfred service 沒在跑"
fi
HEALTH=$(curl -sS --max-time 3 http://127.0.0.1:9001/health 2>/dev/null)
[ -n "$HEALTH" ] && echo "  health: $HEALTH"
echo ""

# 最近 24h 活躍的 user DB
echo "▸ 最近 24 小時內活躍的 user DB"
RECENT=$(find $DATA/users -name "*.db" -mtime -1 2>/dev/null | sort)
COUNT=$(echo "$RECENT" | grep -c . 2>/dev/null)
[ -z "$COUNT" ] && COUNT=0
echo "  共 $COUNT 顆"
if [ "$COUNT" -eq 0 ]; then
    echo "  （24h 內沒活動，改抓最近 7 天）"
    RECENT=$(find $DATA/users -name "*.db" -mtime -7 2>/dev/null | sort)
fi
echo ""

# 用 cp 到 /tmp 避免 lock
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

query_db() {
    local db="$1"
    local q="$2"
    local copy="$TMPDIR/$(basename $db)"
    if [ ! -f "$copy" ]; then
        cp "$db" "$copy" 2>/dev/null || return
    fi
    sqlite3 "$copy" "$q" 2>/dev/null
}

echo "▸ 詳細對比"
printf "  %-46s %6s %6s %6s %6s %22s\n" "user_db" "size" "files" "memos" "convs" "last_indexed_at"
echo "  $(printf '─%.0s' {1..104})"

for db in $RECENT; do
    fname=$(basename "$db")
    fname_short="${fname:0:42}"
    size=$(du -h "$db" 2>/dev/null | cut -f1)
    files=$(query_db "$db" "SELECT COUNT(*) FROM vault_files")
    memos=$(query_db "$db" "SELECT COUNT(*) FROM memories")
    convs=$(query_db "$db" "SELECT COUNT(*) FROM conversation_log")
    last_idx=$(query_db "$db" "SELECT MAX(indexed_at) FROM vault_files")
    [ -z "$files" ] && files="?"
    [ -z "$memos" ] && memos="?"
    [ -z "$convs" ] && convs="?"
    [ -z "$last_idx" ] && last_idx="-"
    last_short="${last_idx:0:19}"
    printf "  %-46s %6s %6s %6s %6s %22s\n" "$fname_short" "$size" "$files" "$memos" "$convs" "$last_short"
done

echo ""
echo "▸ 解讀提示"
echo "  • 兩個 user_db 都是你的 → 比較 size / files / last_indexed_at"
echo "    last_indexed_at 較新那台 = 最近用的"
echo "  • files 差很多 → 兩邊 Mac index 範圍不同"
echo "  • convs / memos 差很多 → 那邊對話比較多，記憶較豐富"
echo ""
echo "  ⚠️  目前 Alfred 架構「裝置 = 帳號」，兩台機器 = 兩個 user_db"
echo "      真正合併需要 identity 改造（待做）"
echo "════════════════════════════════════════════════════════════════"
