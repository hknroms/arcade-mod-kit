# CLAUDE.md — このリポジトリで作業する Claude への共通の決まり

アーケードゲーム（主に 68000 系の基板）の非公式改造パッチを作るためのリポジトリです。
**どちらのリポジトリかを最初に見分ける：**

- **arcade-mod-kit そのもの、またはまだ設定していないタイトル**（`title.json` の title が「（ゲームの名前…）」のまま）
  → ひな形とノウハウ集。新しいタイトルを始めるときは [SETUP.md](SETUP.md)。ノウハウを足すときは `docs/knowhow/`。
- **設定済みのタイトルのリポジトリ**（`title.json` が埋まっている）
  → 下の決まりに従う。タイトル：**{{TITLE}}**（{{REPO}}）。

管理者は {{OWNER}}（作業用アカウント pikadrum）。管理者本人のチャットでも、協力者のチャットでも、最初にこのファイルの内容に従ってください。

## 0. ユーザー（管理者）の決まりごと

- 返事は必ず日本語で、短く（スマホで読むことが多い）。音声入力をよく使うので聞き間違いに注意（例:「豆」「メーム」=MAME）。
- **push の前にユーザーに確認するのは、配布ページ（docs/index.html・docs/versions.json・docs/patches/）に新しい版を公開するときだけ。** それ以外は確認なしで commit・push してよい。
- 新しい版を公開したら、配布ページのリンク {{PAGES}} を伝える。

## 0.5 記録はすべてこのリポジトリに置く（チャットに分散させない）

| 何を | どこに |
|---|---|
| いまの状態・次にやること・保留・決定事項 | [docs/dev/STATUS.md](docs/dev/STATUS.md) |
| メモリ番地・ROM の空き・ビルドとテストの方法 | [docs/dev/TECH.md](docs/dev/TECH.md) |
| 調べること・直すこと・頼むこと（1件ずつ） | GitHub の Issue（まとめページに出る） |
| リリースの説明文 | docs/dev/notes/<版>.json |
| 調査用スクリプト | lua/research/ |
| **どのタイトルにも通じるノウハウ** | **hknroms/arcade-mod-kit の docs/knowhow/**（タイトルのリポジトリではなく、ひな形の方に書き足す） |

- 会話を始めたら、この CLAUDE.md の次に **docs/dev/STATUS.md を読む**。新しい解析・改造を始める前に、arcade-mod-kit の docs/knowhow/ も読む。
- 作業の節目（何かが分かった・決まった・終わった）ごとに STATUS.md・TECH.md を更新して push する。まとめて最後に書くのではなく、その都度書く。
- 引き継ぎ用のファイル（HANDOFF.md や zip）は作らない。チャットを替えるときは、新しい会話でこのリポジトリをつなぐだけでよい。

## 1. 何をする会話かで手順書を選ぶ

| 頼まれたこと | 読む手順書 |
|---|---|
| テストプレイの検証（「VERIFY.md に従って…」） | [VERIFY.md](VERIFY.md) |
| 調査・実装・素材・資料（「COLLAB.md に従って…」） | [COLLAB.md](COLLAB.md) |
| 管理者の改造・修正・リリース作業 | docs/dev/STATUS.md・TECH.md と `src/` |
| 新しいタイトルを始める | [SETUP.md](SETUP.md)（arcade-mod-kit で） |

作業の担当・進み具合・提出物は Issue のコメントコマンドで記録する（一覧は `.github/scripts/task-bot.js` の先頭）。まとめページ：{{PAGES}}status.html

## 2. MAME はビルドしない（ビルド済みを使う）

このタイトルのドライバだけを入れた MAME（`{{SUBTARGET}}`、SDL 同梱）のビルド済みを、このリポジトリの枝 **`mame-{{SUBTARGET}}-bin`** に置いてある。**自分でビルドしないこと**（数十分かかるうえ、環境によっては失敗する）。

```bash
# 準備（その会話で1回だけ・数秒）
git clone -q --depth 1 -b mame-{{SUBTARGET}}-bin https://github.com/{{REPO}}.git mamepkg
tar xzf mamepkg/{{SUBTARGET}}-linux-x64.tar.gz -C "$HOME"
export MAMEBIN="$HOME/{{SUBTARGET}}/{{SUBTARGET}}"   # ライブラリの場所と画面なしの設定はこのラッパーがする
"$MAMEBIN" -version
```

- 動かし方は `lua/run.sh` と `lua/run.lua` の先頭のコメント。画面・音なしで高速に回せる。
- 枝がまだ無い（新しいタイトルの最初）ときだけ、`tools/build_mame.sh` でビルドして `tools/publish_mame.sh` で枝に置く（SETUP.md）。

## 3. ROM の扱い（必ず守る）

- ROM はこのリポジトリに**含まれていない**。作業に要る場合は、会話に添付された zip を使う（改造版は配布ページで作った zip、純正は名前を変えて添付してもらう）。
- ROM の中身・ダンプ・RAM ダンプ・ステートセーブ・ROM から切り出した画像などを、**リポジトリ・フォーク・Issue・コメントなど公開の場所に置かない**。必要なら「再現するスクリプトと手順」を共有する。
- ビルドに ROM 由来のデータが要るなら、それを作るスクリプトをリポジトリに置き、ビルドのたびに作る（docs/knowhow/06-reproducible-build.md）。
- 添付ファイルは元を直接いじらず、作業用フォルダにコピーして使う。

## 4. 書き込みのルール

- **共同編集者（{{OWNER}}・pikadrum・招待された人）**：誰でも main に直接 push してよい。push の前に必ず `git fetch origin main` して最新に合わせる（rebase）。協力者の提出物（`/submit` のリンク先）は、取り寄せて中身を確かめてから取り込み、Issue に `/accept` か `/reject` を書く。
- **それ以外の協力者**：このリポジトリには push しない。書くのは Issue のコメントと、自分のフォーク（枝 `task-<Issue番号>`）だけ。

### リリース（パッチの公開）

- リリースできるのは **{{OWNER}} と pikadrum**（どちらの会話からでもよい）。
- 始める前に main を最新にし、`docs/versions.json` の最新の版を確かめて、その次の番号を付ける。
- ビルドは必ず版を指定し、起動画面に版とビルド日時を書き込む（docs/knowhow/03-rom-check-and-boot.md）。リリースのスクリプトは ROM の版とリリースの版が違えば止める。
- push が拒否された（先に誰かが push していた）ときは、**上書きしない**。最新を取り込み、版番号を付け直してからやり直す。
- 配布ページへの公開（docs/index.html・versions.json・patches の push）の前に、**ユーザーに確認する**。
- 終わったら、関係する Issue に版番号を書き、STATUS.md を更新する。

## 5. チャットを替えるとき（引き継ぎ）

引き継ぎファイルは作らず、STATUS.md を最新にして push しておく。
それでも要約を書くことになった場合は、**1行目に必ず次の文を書く**。

> この作業は GitHub の {{REPO}} で行う。最初にこのリポジトリをつなぎ、CLAUDE.md と docs/dev/STATUS.md を読んでから続けること。

## 6. エミュレータで分かること・分からないこと

確かめられるのは CPU・RAM の動きと静止画まで。色の微妙さ・音・体感速度・ちらつきは「人の目で確認が必要」として扱い、断定しない。
