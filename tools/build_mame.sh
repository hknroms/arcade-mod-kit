#!/bin/bash
# そのタイトルのドライバだけを入れた小さな MAME をビルドし、SDL 同梱・ラッパー付きの tar.gz にまとめる。
# 新しいタイトルを始めたときに「1回だけ」使う。できた tar.gz は枝 mame-<subtarget>-bin に置き、以後はそれを使う（CLAUDE.md）。
#
# usage: [TOOLS=1] tools/build_mame.sh [作業フォルダ]  （title.json の mame.source / mame.subtarget を読む）
#   TOOLS=1 で、どの CPU でも逆アセンブルできる unidasm も一緒に作る（時間が延びる。docs/knowhow/09-cpus.md）
# 所要時間: SDL 数分 + MAME 30〜60分（2コア）。apt が使えず GitHub だけつながる環境で動作確認済み（2026-10, MAME 0.289）
set -euo pipefail
HERE=$(cd "$(dirname "$0")/.." && pwd)
W=${1:-$HOME/mamebuild}
SRC=$(python3 -c "import json;print(json.load(open('$HERE/title.json',encoding='utf-8'))['mame']['source'])")
ST=$(python3 -c "import json;print(json.load(open('$HERE/title.json',encoding='utf-8'))['mame']['subtarget'])")
PREFIX=/opt/sdl
mkdir -p "$W" && cd "$W"
log(){ echo "[$(date +%H:%M:%S)] $*"; }

# 1) SDL2 / SDL2_ttf をソースから（/opt/sdl へ）
if [ ! -f "$PREFIX/lib/libSDL2.so" ]; then
  log SDL2
  [ -d SDL ] || git clone -q --depth 1 -b release-2.30.x https://github.com/libsdl-org/SDL.git
  cmake -S SDL -B SDL/build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=$PREFIX -DSDL_STATIC=OFF -DSDL_TEST=OFF >/dev/null
  cmake --build SDL/build -j"$(nproc)" >/dev/null && cmake --install SDL/build >/dev/null
fi
if [ ! -f "$PREFIX/lib/libSDL2_ttf.so" ]; then
  log SDL2_ttf
  [ -d SDL_ttf ] || git clone -q --depth 1 -b release-2.22.x https://github.com/libsdl-org/SDL_ttf.git
  cmake -S SDL_ttf -B SDL_ttf/build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=$PREFIX -DCMAKE_PREFIX_PATH=$PREFIX \
    -DSDL2TTF_VENDORED=OFF -DSDL2TTF_HARFBUZZ=OFF -DSDL2TTF_SAMPLES=OFF >/dev/null
  cmake --build SDL_ttf/build -j"$(nproc)" >/dev/null && cmake --install SDL_ttf/build >/dev/null
fi
export PKG_CONFIG_PATH=$PREFIX/lib/pkgconfig:${PKG_CONFIG_PATH:-} PATH=$PREFIX/bin:$PATH

# 2) MAME
log "MAME clone"
[ -d mame ] || git clone -q --depth 1 https://github.com/mamedev/mame.git
# GL/gl.h・EGL・libEGL.so（開発用リンク）が無い環境向けの用意（bgfx がヘッダを要求する）
if [ ! -e /usr/include/GL/gl.h ] && [ ! -e /usr/local/include/GL/gl.h ]; then
  mkdir -p /usr/local/include/GL
  printf '#ifndef KIT_GL_H\n#define KIT_GL_H\n#include <SDL2/SDL_opengl.h>\n#endif\n' > /usr/local/include/GL/gl.h
  K=mame/3rdparty/bgfx/3rdparty/khronos
  cp -n $K/gl/glext.h /usr/local/include/GL/ 2>/dev/null || true
  cp -rn $K/EGL $K/KHR /usr/local/include/
  ln -sfn $PREFIX/include/SDL2 /usr/local/include/SDL2
fi
[ -e /usr/local/lib/libEGL.so ] || { [ -e /lib/x86_64-linux-gnu/libEGL.so.1 ] && ln -s /lib/x86_64-linux-gnu/libEGL.so.1 /usr/local/lib/libEGL.so; } || true
cd mame
log "MAME build start ($(git rev-parse --short HEAD)) $SRC"
make SUBTARGET="$ST" SOURCES="$SRC" NOWERROR=1 NO_USE_MIDI=1 NO_X11=1 NO_USE_XINPUT=1 NO_OPENGL=1 \
  NO_USE_PORTAUDIO=1 NO_USE_PULSEAUDIO=1 NO_USE_PIPEWIRE=1 USE_QTDEBUG=0 OPTIMIZE=2 SYMBOLS=0 TOOLS=${TOOLS:-0} \
  -j"$(nproc)" > ../make.log 2>&1 || { tail -30 ../make.log; exit 1; }
log "MAME build done"

# 3) まとめる（SDL 同梱、ライブラリの場所と画面なしの設定をするラッパー）
OUT="$W/pkg/$ST"; rm -rf "$W/pkg"; mkdir -p "$OUT/lib"
cp "$ST" "$OUT/$ST.bin"; strip "$OUT/$ST.bin" || true
[ -x unidasm ] && cp unidasm "$OUT/unidasm" && strip "$OUT/unidasm" || true
for lib in $(ldd "$OUT/$ST.bin" | awk '/=> \//{print $3}'); do case "$lib" in /opt/*) cp -L "$lib" "$OUT/lib/";; esac; done
cat > "$OUT/$ST" <<EOF
#!/bin/bash
D=\$(cd "\$(dirname "\$(readlink -f "\$0")")" && pwd)
export LD_LIBRARY_PATH="\$D/lib\${LD_LIBRARY_PATH:+:\$LD_LIBRARY_PATH}"
export SDL_VIDEODRIVER=\${SDL_VIDEODRIVER:-dummy} SDL_AUDIODRIVER=\${SDL_AUDIODRIVER:-dummy}
exec "\$D/$ST.bin" "\$@"
EOF
chmod +x "$OUT/$ST"
cat > "$OUT/BUILD.md" <<EOF
# $ST — $SRC だけを入れた MAME（Linux x86-64）
- MAME: $("$OUT/$ST" -version | head -1)（https://github.com/mamedev/mame のコミット $(git rev-parse HEAD)）
- ライセンス: MAME は GPL-2.0-or-later（一部 BSD-3-Clause）。同梱の SDL2 / SDL2_ttf は zlib ライセンス
- 作り方: arcade-mod-kit の tools/build_mame.sh
EOF
tar czf "$W/$ST-linux-x64.tar.gz" -C "$W/pkg" "$ST"
log "package: $W/$ST-linux-x64.tar.gz ($(du -h "$W/$ST-linux-x64.tar.gz" | cut -f1))"
echo "次: tools/publish_mame.sh $W/$ST-linux-x64.tar.gz  （枝 mame-$ST-bin に置く）"
