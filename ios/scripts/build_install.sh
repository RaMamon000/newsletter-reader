#!/bin/zsh
# 実機ビルドしてつながっている iPhone に入れる。ロック中は最大10分、解除待ちで再試行。
# 使い方: scripts/build_install.sh [UDID]   （省くと環境変数 MERUMA_UDID）
set -u
UDID=${1:-${MERUMA_UDID:?UDID を引数か MERUMA_UDID で指定してください}}
ROOT=${0:A:h:h}
DERIVED=$ROOT/build/device
cd "$ROOT" || exit 1

[ -f Meruma/Secrets.swift ] || { echo "Secrets.swift がありません（Secrets.swift.example を参照）"; exit 1; }
echo "== xcodegen"
xcodegen generate >/dev/null || { echo "BUILD FAILED (xcodegen)"; exit 1; }

echo "== build"
xcodebuild -project Meruma.xcodeproj -scheme Meruma -configuration Debug \
  -destination "platform=iOS,id=$UDID" -derivedDataPath "$DERIVED" \
  -allowProvisioningUpdates build > "$DERIVED.build.log" 2>&1
grep -E 'error:|BUILD (SUCCEEDED|FAILED)' "$DERIVED.build.log"
# ビルドに失敗したら、前回のアプリを入れずにここで止める
grep -q 'BUILD SUCCEEDED' "$DERIVED.build.log" || { echo "BUILD FAILED（インストールしません）"; exit 1; }
APP=$DERIVED/Build/Products/Debug-iphoneos/Meruma.app
[ -d "$APP" ] || { echo "BUILD FAILED (no app)"; exit 1; }

echo "== install（最大10分、ロック解除待ち）"
END=$((SECONDS+600))
while [ $SECONDS -lt $END ]; do
  if xcrun devicectl device install app --device "$UDID" "$APP" 2>&1 | grep -q "App installed"; then
    echo "INSTALLED"; exit 0
  fi
  echo "install retry (iPhoneのロック解除/接続を待っています)"; sleep 15
done
echo "INSTALL FAILED"; exit 1
