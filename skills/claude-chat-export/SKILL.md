---
name: claude-chat-export
description: Use when the user wants to export a claude.ai conversation to Markdown - "このチャットをmarkdownにして", "claude.aiの会話を書き出して", "共有リンクをmdにして", "会話を逐語で保存", "図はmermaidにして". Drives a logged-in Chrome via CDP to fetch the conversation API, converts charts and widgets to mermaid/tables, and verifies the output is verbatim. Do not use for exporting Claude Code session transcripts (those live in ~/.claude/projects/*.jsonl).
---

# claude-chat-export

claude.ai の会話を**逐語の Markdown** に書き出す。図表（棒グラフ・ヒートマップ・図）も復元する。

この文書は単体で読める手順書でもある。Claude Code の無い環境でも、これを読めば手作業で再現できる。

## 結論だけ先に

**共有リンク（`/share/`）を本文取得に使ってはいけない。** ログイン済みブラウザから
**会話 API を1回叩く**のが唯一まともな方法。所要は数秒。

```
node scripts/fetch.mjs <URL>              # Chrome起動→手動ログイン待ち→conv.json 取得
python3 scripts/build.py --in conv.json --out out.md [--from 0 --to 48]
python3 scripts/verify.py --in conv.json --md out.md [--from 0 --to 48]
```

`<URL>` は `https://claude.ai/chat/<uuid>` でも `https://claude.ai/share/<uuid>` でもよい。
share を渡した場合はスナップショットから `conversation_uuid` を取り出し、
自動で会話 API に切り替える（share のままでは図表が失われるため）。

## ユーザーへの確認（毎回必須）

fetch.mjs は**使い捨てプロファイルの Chrome を起動し、ユーザーに手動ログインしてもらう**。
認証情報はスキルが一切扱わず、常用プロファイルにも触れない。
それでも**ログイン済みブラウザを自動操作下に置く**行為なので、起動前に必ず確認を取ること。

終了時に Chrome を終了し、一時プロファイルを削除する。

## API 仕様（手作業で再現する場合）

ログイン済みのページコンテキストから fetch する。ページ内から叩くこと（Cookie と
Cloudflare クリアランスが必要。外から curl すると 403）。

```
GET /api/organizations
    → [{uuid, ...}, ...]   複数返るので 200 が返る方を使う（片方は 403 のことがある）

GET /api/organizations/<org_uuid>/chat_conversations/<conversation_uuid>
        ?tree=True&rendering_mode=messages&render_all_tools=true
    → {name, uuid, chat_messages:[{index, sender, created_at, content:[...]}, ...]}

GET /api/organizations/<org_uuid>/files/<file_uuid>/contents
    → 会話に添付されたファイルの本文（メッセージの files[].file_uuid）
```

**`render_all_tools=true` を省くと `tool_use` / `tool_result` が丸ごと返らない**
（エラーにはならず `text` と `thinking` だけになる）。`fetch.mjs` は付けているが、
手で叩くときに落としやすい。チャット側の Claude が書いたファイルの本文は
`tool_use`（`name:"Write"`）の `input.content` に残っている。

共有スナップショットは `GET /api/chat_snapshots/<share_uuid>`。
**本文取得には使わない**が、`conversation_uuid` を得るためと、検証用の第2ソースとしては有用。

## 落とし穴（全部踏んだ）

1. **`text` フィールドは空。** 会話 API（`rendering_mode=messages`）では本文は
   `content` ブロックの `type:"text"` にしかない。共有スナップショット API とは形式が違う。
   共有側の形式を前提にすると全件空になる。

2. **共有リンクは図表を失う。** 検証したケースでは図表9点のうち3点が画像化、
   6点が「共有チャットではインタラクティブなビジュアルが非表示」で消え、
   JSON 上は全点が `This block is not supported on your current device yet.` に化けていた。
   `content` も `null` で復元不能。

3. **図表は本文ではなくツール呼び出しの中にある。**
   - `chart_display_v0` … 棒グラフ。`series` / `x_axis`（`xAxis` の表記ゆれあり）に生の数値
   - `visualize:show_widget` … `widget_code` に HTML か SVG

4. **DOM スクレイピングは使わない。** `transcript-list` は仮想リストで、表示中の
   メッセージしか DOM に置かない。スクロール中に過去分が遅延ロードされてページ高が
   伸び続けるため、数え上げは必ず過小になり、書式も壊れる。遅い上に不正確。

5. **ヘッドレスは Cloudflare に弾かれる。** `--headless --dump-dom` は
   ボット検証で止まる。表示ありの実 Chrome なら通る。

6. **Chrome 136 以降は既定プロファイルでのリモートデバッグを拒否する。**
   `--user-data-dir` に別ディレクトリを渡すこと。

7. **ヒートマップは mermaid にできない。** mermaid に該当図種が無い。
   無理に xychart 等へ寄せると上三角行列の構造が壊れる。**Markdown 表が正解。**

8. **検証コード自体が壊れる。** 実際に2回やった（sha256 を同じ値同士で自己比較、
   存在しない `text` フィールドの比較で全件不一致）。
   **PASS したら、わざと1文字壊して FAIL するか確かめること。**

9. **Claude in Chrome の `javascript_tool` では大きな本文を持ち出せない。**
   API はページ内から叩けるが、戻り値に Base64 や URL のクエリ文字列が含まれると
   拡張の安全フィルタが `[BLOCKED: ...]` に差し替える（2026-10-10 に確認）。
   構造の確認や SHA-256 の計算には使えるので、本文は `fetch.mjs` か画面の
   ダウンロードで取り、ページ内で計算したハッシュと突き合わせる。

## 検証の考え方

「ソースの各ブロックがファイル内に**存在するか**」では不十分。ブロック間への混入を
検出できない。**足場（見出し・区切り線・追記ブロック）を機械的に剥がし、残りが
ソースと完全一致するか**を見る。これで追加・削除・改変・並べ替えが全て検出できる。
`verify.py` がこれを行う。

さらに強くするなら、**共有 API（未ログイン）と会話 API（ログイン）の2経路**を
突き合わせる。取得ミスや転送破損があれば、まず一致しない。

## 図表の変換方針

| 種別 | 変換先 | 保証 |
|---|---|---|
| `chart_display_v0` | mermaid `xychart-beta` | 数値は原データそのまま |
| `show_widget` のヒートマップ（CSS grid） | **Markdown 表** | 全セルを機械パース。逐語 |
| `show_widget` の SVG | **SVG をそのまま埋め込み** | 無損失 |

**SVG の mermaid 化は自動化しない。** 任意の SVG を機械的に mermaid へ落とすことは
できないため、スクリプトは SVG を無損失で埋め込むに留める。
ユーザーが mermaid を望む場合は、埋め込まれた SVG の `<title>` / `<desc>` /
`<text>` と図形の配置を読み、**Claude が手で `flowchart` を書く**こと。
その場合、機械的同一性の保証は無い旨を出力に明記する。

ヒートマップのパースは、`grid-template-columns: <幅> repeat(N, ...)` の直下に
`1+N` 個ずつセルが並ぶ構造を利用する。正規表現ではなく**深さを数えて直下の子だけ**を
取ること。入れ子の `<div>` があるため。

## Chrome の検出

`scripts/chrome.mjs` が4段フォールバックで解決する。

1. 環境変数 `CHROME_PATH`
2. プラットフォーム別の既知パス（macOS `/Applications/…` と `~/Applications/…`、
   Windows `%PROGRAMFILES%` / `%PROGRAMFILES(X86)%` / `%LOCALAPPDATA%`、
   Linux `/opt/google/chrome/chrome`, `/usr/bin/google-chrome*`, snap）
3. `PATH` 検索（`command -v google-chrome` / `where chrome.exe` 等）
4. OS への問い合わせ（macOS は `mdfind` でバンドルID `com.google.Chrome`、
   Windows は `reg query …\App Paths\chrome.exe`）

見つからなければ**黙って進まず停止**し、`CHROME_PATH` の設定を促す。
macOS では検証済み。Windows / Linux は未検証なので、初回はパス解決の出力を確認すること。

## 依存

**なし。** Node 22+ の組み込み `WebSocket` で CDP を喋る。
Playwright も puppeteer も不要。Python は標準ライブラリのみ。
