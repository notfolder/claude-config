---
name: qiita-post
description: Use when the user wants to post or update a Markdown article on Qiita via the API - "Qiitaに下書きで投稿して", "限定共有で投稿して", "Qiitaに投稿して", "Qiitaの記事を更新して", "この記事をQiitaに上げて". Posts as a private (限定共有) item by default since Qiita's API has no draft endpoint; publishes only when the user explicitly asks. Reads the token from ~/.env or ~/.env.txt (QIITA-KEY). Do not use for writing the article itself (use qiita-writer for that).
---

# qiita-post

Qiita API v2 で Markdown 記事を投稿・更新するスキル。実体は `scripts/qiita_post.py`（Python 3 標準ライブラリのみ）。

## 前提と制約

- **Qiita API に「下書き」は無い。** 代わりに `private: true`（限定共有記事）で投稿する。
  URL を知る人だけが読め、一覧・検索・タグページに出ない。Qiita の編集画面から
  後で公開に切り替えられる。ユーザーが「下書き」と言ったらこれを指す。
- **公開投稿は、ユーザーが明示的に「公開して」と言ったときだけ `--public` を付ける。**
  迷ったら限定共有。
- トークンの探索順: 環境変数 `QIITA_TOKEN` → `~/.env` → `~/.env.txt`。
  キー名は `QIITA-KEY` / `QIITA_KEY` / `QIITA_TOKEN`。**トークンの値は絶対に表示・出力しない。**
- 記事は front matter（`title:` / `tags:` 空白区切り）を持つ Markdown を想定
  （qiita-writer の出力形式）。front matter が無ければ先頭の `# 見出し` をタイトルにする。
- 本文先頭の `# タイトル` 行は Qiita 側でタイトルが別表示されるため自動で除く。
- 制約: タグ 1〜5 個・空白不可、本文 100,000 文字以内、タイトル 255 文字以内。

## 重複投稿の防止

投稿すると記事と同じディレクトリに `.qiita-post.json`（item_id, url, private, 日時）を書く。
再実行時はこのファイルの `item_id` を **PATCH で更新**する。新規に別記事として
投稿したいときだけ `--new`。別の既存記事を更新したいときは `--item-id <id>`。

## 手順

1. 記事のパスを確認する。無ければ聞く。
2. `--dry-run` で title / tags / 文字数 / 更新か新規かを確認し、ユーザーに見せる。
   ```
   python3 ~/.claude/skills/qiita-post/scripts/qiita_post.py <article.md> --dry-run
   ```
3. 問題なければ投稿する（既定で限定共有）。
   ```
   python3 ~/.claude/skills/qiita-post/scripts/qiita_post.py <article.md>
   ```
   公開する場合のみ `--public` を付ける。
4. 出力の `url` をユーザーに伝える。限定共有なら「Qiita の編集画面で公開に切り替えられる」と添える。
5. 失敗時（HTTP 4xx/5xx）は API のエラー本文をそのまま示す。
   よくある原因: 401=トークン無効、403=スコープ不足（`write_qiita` が必要）、
   422=タグ不正・本文超過。

## mermaid について

Qiita の mermaid は `xychart-beta` を描画しない（2025-04 時点の確認）。記事に含まれていたら
投稿前にユーザーに知らせる。`flowchart` / `sequenceDiagram` / `graph` は問題ない。

## 投稿後の確認

限定共有記事は本人がログインしていれば `url` を開いて確認できる。表示崩れ（表、mermaid、
`:::note`）は Qiita 上で見ないと分からないので、ユーザーに確認を促す。
