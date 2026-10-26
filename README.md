# arcade-mod-kit

アーケードゲームの非公式改造パッチ（CPU は問わない。68000・Z80・6809・SH-2 など）を作るための **ひな形** と **ノウハウ集**。
hknroms/gradius3（グラディウスIII）で作った仕組みを、どのタイトルでも使える形にしたもの。

- 紹介ページ: https://hknroms.github.io/arcade-mod-kit/
- 新しいタイトルを始める: [SETUP.md](SETUP.md)（このリポジトリの「Use this template」から作る）
- ノウハウ集: [docs/knowhow/](docs/knowhow/README.md)
- Claude への決まり: [CLAUDE.md](CLAUDE.md)

## 入っているもの

| 場所 | 中身 |
|---|---|
| `CLAUDE.md` / `VERIFY.md` / `COLLAB.md` | Claude への共通の決まり、協力者の Claude 向け手順書（`{{…}}` は setup_title.py で埋める） |
| `docs/status.html` / `docs/collaborators.json` | 共同作業のまとめページ |
| `docs/dev/` | STATUS.md（現在地）・TECH.md（技術メモ）のひな形 |
| `docs/knowhow/` | どのタイトルにも通じるノウハウ（タイトルのリポジトリにも写るが、書き足すのはここ） |
| `docs/index.html` | このひな形の紹介ページ（タイトルのリポジトリでは配布ページに置き換える） |
| `.github/` | 共同作業ボットと Issue のテンプレート |
| `tools/` | asm68.py・d68.py・bps.py・romkit.py・build_mame.sh・publish_mame.sh・setup_title.py |
| `lua/` | run.sh / run.lua（MAME を画面なしで回す）、research/ |
| `src/` | タイトルの改造のソースを置く場所 |
| `title.json` | タイトルの情報 |

ROM はどこにも含まれていません。各ゲームの著作権は各社にあります。
