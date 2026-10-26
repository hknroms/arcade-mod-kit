# src — このタイトルの改造のソース

- 改造ごとに Python のファイル（例 `mod_menu.py`）を作り、`tools/romkit.py` の `Rom` に `put()` / `asm()` で書き込む。
- ビルドの入口（例 `build_all.py`）は `VERSION=<版> ROMBASE=<純正ROMの置き場> python3 src/build_all.py <出力>` の形にする。
- 前の会話の作業フォルダのパスを書き込まない。ROM 由来のデータは置かず、作るスクリプトにする（docs/knowhow/06）。
- 参考: hknroms/gradius3 の `src/mods/`（build_all.py・mod_main.py・mod_boot.py など）。
