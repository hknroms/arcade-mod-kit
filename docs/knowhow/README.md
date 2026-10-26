# ノウハウ集（どのタイトルにも通じる話）

アーケード基板の ROM 改造で分かったことを、タイトルを問わない形でまとめたもの。
新しいタイトルを始めるときは、上から順に読む。01〜05 は 68000 の例で書いてあるので、ほかの CPU では 09 も読む。タイトル固有の番地や事情は、各タイトルのリポジトリの `docs/dev/TECH.md` に書く。

| ファイル | 内容 |
|---|---|
| [01-analysis.md](01-analysis.md) | 解析の進め方（ROM の並べ方・状態機械・RAM の特定・書き込み元の追跡） |
| [02-patching.md](02-patching.md) | パッチの入れ方（空き領域・アセンブラ・フック・テーブル拡張・レジスタ） |
| [03-rom-check-and-boot.md](03-rom-check-and-boot.md) | 起動時の ROM チェックを通す・起動画面に版と日時を書く |
| [04-emulator-testing.md](04-emulator-testing.md) | MAME での検証（画面なしで回す・入力列・スナップ・分からないこと） |
| [05-ui-menus.md](05-ui-menus.md) | メニュー・ポーズ・設定を足すときの定石 |
| [06-reproducible-build.md](06-reproducible-build.md) | 誰でも同じものをビルドできるようにする（ROM 由来データの扱い） |
| [07-release-distribution.md](07-release-distribution.md) | リリースと配布（BPS・配布ページ・版の管理・環境ごとの注意） |
| [08-collaboration.md](08-collaboration.md) | 共同作業の仕組み（Issue のコマンド・まとめページ・要望） |
| [09-cpus.md](09-cpus.md) | CPU ごとの違い（68000 以外の基板で変わるところ） |
| [cases/](cases/) | タイトルごとの実例（何をどう作ったか） |

**書き足すルール**: 新しく分かったことは、そのタイトルの TECH.md に書いたうえで、他のタイトルにも通じる部分をここに足す（例・番地は「実例」として cases/ に）。
