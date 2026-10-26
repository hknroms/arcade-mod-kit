# 新しいタイトルを始める手順

arcade-mod-kit（このリポジトリ）から、タイトルごとのリポジトリを作ります。人がやることは 1〜3 だけで、残りは Claude に頼めます。

## 人がやること（GitHub の画面で・数分）

1. **リポジトリを作る**: arcade-mod-kit の画面右上の **「Use this template」→「Create a new repository」**。名前はタイトルが分かるもの（例 `gradius3`、`trigon`）。公開（Public）で作る。
2. **Claude のアプリに許可を足す**: https://github.com/settings/installations → Claude の **Configure** → Select repositories に新しいリポジトリを足して **Save**。
3. **ピカドラムを招待する**（ピカドラムの会話からも作業するなら）: 新しいリポジトリの Settings → Collaborators →「Add people」、ピカドラム側で招待を承認。
4. （配布ページを出すとき）Settings → Pages で「main」「/docs」を選んで Save。

## Claude に頼むこと

新しい会話で、新しいリポジトリをつないで次のように送る（純正ROMの zip も添付する）:

> ○○（新しいリポジトリ）の SETUP.md の「Claude がやること」を進めて。タイトルは△△、MAME のセット名は□□。

### Claude がやること

1. `title.json` を埋める（タイトル名・リポジトリ名・MAME のセット名とドライバのソース・ビルド名（短い名前）・改造する CPU の種類と ROM ファイル名と並べ方・配布ページの URL）。
   - MAME のセット名とソースは、MAME のソースの `src/mame/<メーカー>/*.cpp` で `GAME(` の行を探す。CPU の種類と ROM の並べ方（`ROM_LOAD`・`ROM_LOAD16_BYTE`・`ROM_LOAD32_BYTE` など）も同じファイルで分かる。
   - 68000 以外の CPU なら docs/knowhow/09-cpus.md を読む（アセンブラの用意など）。
2. `python3 tools/setup_title.py` で、手順書などの `{{…}}` を埋める。`--check` で埋め残しが無いことを確かめる。
3. MAME を用意する: `tools/build_mame.sh` でビルド（30〜60分、1回だけ）→ `tools/publish_mame.sh <tar.gz>` で枝 `mame-<ビルド名>-bin` に置く → 新しい会話と同じ手順（CLAUDE.md）でダウンロードして起動を確かめる。
4. ラベルを作る: Actions タブ →「共同作業ボット」→ Run workflow（API なら `POST /repos/<repo>/actions/workflows/task-bot.yml/dispatches`）。
5. `docs/index.html`（ひな形の紹介ページ）を、そのタイトルの配布ページに置き換える（gradius3 の docs/index.html を写して直す）。arcade-mod-kit の紹介ページの「タイトル」に新しいタイトルを足す。
6. 純正ROMで起動し、`docs/knowhow/` の順に解析を始める。分かったことは `docs/dev/TECH.md`、状態は `docs/dev/STATUS.md` に書いて push する。
7. タイトルを問わない新しい発見は、**arcade-mod-kit の docs/knowhow/ に書き足す**（次のタイトルで使えるように）。

## ひな形の中身

| 場所 | 中身 |
|---|---|
| `CLAUDE.md` | Claude への共通の決まり（ROM の扱い・push のルール・記録の置き場所・MAME の使い方） |
| `VERIFY.md` / `COLLAB.md` | 協力者の Claude 向け手順書（検証／調査・実装・素材・資料） |
| `docs/status.html` | 共同作業のまとめページ（全体・要望・種類別・協力者・始め方のタブ） |
| `docs/dev/` | STATUS.md（現在地）・TECH.md（技術メモ）・notes/（リリースの説明文） |
| `docs/knowhow/` | どのタイトルにも通じるノウハウ |
| `.github/` | 共同作業ボット（Issue のコメントコマンド）と Issue のテンプレート |
| `tools/` | romkit.py（ROM の組み立て。CPU を問わず1本・2本・4本の並べ方、合計の補正）・bps.py（BPS パッチ）・asm68.py / d68.py（68000 のアセンブラ・逆アセンブラ）・build_mame.sh / publish_mame.sh（MAME）・setup_title.py |
| `lua/` | run.sh / run.lua（MAME を画面なしで回してテスト）、research/（調査用の小さなスクリプト） |
| `src/` | タイトルごとの改造のソースを置く場所 |
| `title.json` | タイトルの情報（setup_title.py・romkit.py・build_mame.sh が読む） |

## 参考にするタイトル

- **hknroms/gradius3**（グラディウスIII）: このひな形の元。メニュー・ポーズ・面選択・キューブラッシュ、起動画面の版表示、配布ページ（ROM をドロップすると改造版の zip を作る `docs/index.html`）、リリーススクリプト（`tools/release.py`）。配布ページとリリースはタイトルごとに違うので、gradius3 のものを写して直す。
