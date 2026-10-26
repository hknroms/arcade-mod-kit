#!/bin/bash
# usage: lua/run.sh <ROMのフォルダ> <luaスクリプト> <出力フォルダ> [MAME の追加オプション]
#   環境変数 MAMEBIN（ビルド済み MAME のラッパー。CLAUDE.md の手順で用意）、GAME（既定は title.json の mame.driver）
#   lua の環境変数（SEQ POKE WATCH SNAP END …）は lua/run.lua の先頭を参照
HERE=$(cd "$(dirname "$0")/.." && pwd)
RP=$1; LUA=$2; OUT=$3; shift 3
GAME=${GAME:-$(python3 -c "import json;print(json.load(open('$HERE/title.json',encoding='utf-8'))['mame']['driver'])")}
MAMEBIN=${MAMEBIN:?MAMEBIN を設定してください（CLAUDE.md の「MAME はビルドしない」）}
TMP=$(mktemp -d)
rm -rf "$OUT"; mkdir -p "$OUT"; export DUMPPREFIX="$OUT/dump"
"$MAMEBIN" "$GAME" -rompath "$RP" -video none -sound none -nothrottle -skip_gameinfo \
  -snapshot_directory "$OUT" -snapname "%i" -autoboot_script "$LUA" \
  -homepath "$TMP" -cfg_directory "$TMP/cfg" -nvram_directory "$TMP/nv" "$@"
rm -rf "$TMP"
