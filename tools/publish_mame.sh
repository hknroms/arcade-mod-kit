#!/bin/bash
# build_mame.sh で作った tar.gz を、このリポジトリの枝 mame-<subtarget>-bin に置く（履歴を持たない枝。差し替えも同じ手順）。
# usage: tools/publish_mame.sh <tar.gz>
# ※ GitHub の Releases は Claude のクラウドの会話からは作れないため、枝に置く（2026-10 時点）
set -euo pipefail
HERE=$(cd "$(dirname "$0")/.." && pwd)
TGZ=$(readlink -f "$1")
ST=$(python3 -c "import json;print(json.load(open('$HERE/title.json',encoding='utf-8'))['mame']['subtarget'])")
REPO=$(python3 -c "import json;print(json.load(open('$HERE/title.json',encoding='utf-8'))['repo'])")
W=$(mktemp -d)
cd "$W" && git init -q -b "mame-$ST-bin"
cp "$TGZ" "$ST-linux-x64.tar.gz"
tar xzf "$TGZ" -O "$ST/BUILD.md" > BUILD.md 2>/dev/null || true
cat > README.md <<EOF
# mame-$ST-bin
検証・開発用の MAME（$REPO のタイトルのドライバだけ、Linux x86-64、SDL 同梱）。ゲームの改造パッチではありません。ROM は含まれていません。

\`\`\`bash
git clone -q --depth 1 -b mame-$ST-bin https://github.com/$REPO.git mamepkg
tar xzf mamepkg/$ST-linux-x64.tar.gz -C "\$HOME"
export MAMEBIN="\$HOME/$ST/$ST"; "\$MAMEBIN" -version
\`\`\`
EOF
sha256sum "$ST-linux-x64.tar.gz" > SHA256SUMS
git add -A && git -c user.name="${GIT_NAME:-Claude}" -c user.email="${GIT_EMAIL:-noreply@anthropic.com}" commit -q -m "MAME $ST のビルド済み"
git push -f "https://github.com/$REPO.git" "mame-$ST-bin"
echo "置きました: 枝 mame-$ST-bin"
