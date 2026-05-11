#!/bin/bash
# 阿福 iOS Build Script
# 在 Mac 上執行：在 Claude Code 輸入 ! bash /tmp/alfred_build.sh
# 或：! curl -s root@YOUR_SERVER:/tmp/alfred_build.sh | bash

set -e

XCODE_PROJ="/Users/YOUR_USER/Dropbox/Alfred/Alfred"
VPS="root@YOUR_SERVER"
VPS_SRC="/opt/alfred/ios_app/Alfred"

echo "=== Alfred iOS Build ==="
echo "目標專案: $XCODE_PROJ"

# 1. 同步 Swift 檔案 from VPS
echo "[1/4] 同步 Swift 檔案..."
rsync -avz --include="*.swift" --include="*.mp3" --include="*.plist" \
  --include="*/" --exclude="*" \
  "$VPS:$VPS_SRC/" "$XCODE_PROJ/" 2>/dev/null || {
  echo "rsync 失敗，改用 scp..."
  mkdir -p "$XCODE_PROJ/Core" "$XCODE_PROJ/Features/Chat" \
            "$XCODE_PROJ/Features/Family" "$XCODE_PROJ/Features/Office" \
            "$XCODE_PROJ/Features/Attendance" "$XCODE_PROJ/Features/Auth" \
            "$XCODE_PROJ/Features/Translate" "$XCODE_PROJ/Features/SubApps" \
            "$XCODE_PROJ/Resources/voices"
  scp "$VPS:$VPS_SRC/AlfredApp.swift" "$XCODE_PROJ/"
  scp "$VPS:$VPS_SRC/Core/*.swift" "$XCODE_PROJ/Core/"
  scp "$VPS:$VPS_SRC/Features/Chat/*.swift" "$XCODE_PROJ/Features/Chat/"
  scp "$VPS:$VPS_SRC/Features/Family/*.swift" "$XCODE_PROJ/Features/Family/"
  scp "$VPS:$VPS_SRC/Features/Office/*.swift" "$XCODE_PROJ/Features/Office/"
  scp "$VPS:$VPS_SRC/Features/Attendance/*.swift" "$XCODE_PROJ/Features/Attendance/"
  scp "$VPS:$VPS_SRC/Features/Auth/*.swift" "$XCODE_PROJ/Features/Auth/"
  scp "$VPS:$VPS_SRC/Features/Translate/*.swift" "$XCODE_PROJ/Features/Translate/"
  scp "$VPS:$VPS_SRC/Features/SubApps/*.swift" "$XCODE_PROJ/Features/SubApps/"
  scp "$VPS:$VPS_SRC/Resources/Info.plist" "$XCODE_PROJ/Resources/"
  scp "$VPS:$VPS_SRC/Resources/onboarding_greeting.mp3" "$XCODE_PROJ/Resources/"
}

echo "[2/4] 檔案同步完成，清單："
find "$XCODE_PROJ" -name "*.swift" | sort

echo ""
echo "[3/4] 開啟 Xcode..."
find "$XCODE_PROJ/../.." -name "*.xcodeproj" 2>/dev/null | head -3
XCODEPROJ=$(find "$XCODE_PROJ/../.." -name "*.xcodeproj" 2>/dev/null | head -1)
if [ -n "$XCODEPROJ" ]; then
  open "$XCODEPROJ"
  echo "Xcode 已開啟: $XCODEPROJ"
else
  echo "找不到 .xcodeproj，請手動開啟 Xcode"
fi

echo ""
echo "[4/4] 請在 Xcode 中："
echo "  1. 選擇你的 iPhone 作為 target"
echo "  2. 按 Cmd+R 或點 ▶ 按鈕 build & run"
echo ""
echo "=== 完成 ==="
