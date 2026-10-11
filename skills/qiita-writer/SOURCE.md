# yomiyasu の取り込み

SKILL.md の「日本語の書き方」「実行手順」の 2 節は、yomiyasu の SKILL.md の 1 章・2 章を
要約せずに取り込んだもの（2026-10-02）。

- 上流: https://github.com/nanaism/yomiyasu （MIT / nanaism）
- ライセンス文: 同じディレクトリの `LICENSE-yomiyasu`（上流の LICENSE をそのまま写したもの）
- 取り込んだ版: `~/.claude/skills/yomiyasu/` にある版（上流コミット 7b61b2f。詳細は yomiyasu/SOURCE.md）
- 取り込まなかった部分: frontmatter、類似スキルの無効化を勧める注意書き（統合したので意味を失う）、
  3 章の対話用出力フォーマット（qiita-writer はファイルに出力する）
- 参照資料（gemini-syntax.md・domains/tech.md・slop-catalog.md）とリンターはコピーせず、
  yomiyasu の場所を直接読む。資料側の食い違いは SKILL.md 冒頭の「優先順位」の表で上書きしている

## Qiita 向けに書き換えた箇所

原文と食い違う文だけを置き換えた。それ以外は 1 字も変えていない。

| # | 箇所 | 書き換え |
|---|---|---|
| 2 | 実行手順 Step 1 | ドメインを tech に固定し、business・essay を外す |
| 3 | Step 1 の tech、Step 2 の 9 | 箇条書き 15% 以下・地の文へ統合 → 並列データ（変更点・手順・パラメータ・比較）は残す |
| 4 | Qiita Article Shape の 7 | 「おわりに」は残し、定型の締めを書かない（tech.md の「まとめ見出しを置かない」は優先順位の表で上書き） |
| 5 | Output Patterns | 3 章の出力フォーマットの代わりに、「書き手に確かめたい点」を article.md の補足・未確認事項へ入れる |
| 6 | Step 3 | 「フルモード指定時やファイル保存時」→ 毎回。仮のパスを実際のパスに |
| 7 | 意味の保持 | 素材の文を「元の文」とし、記事構成の組み直しは qiita-writer の規則に従う |
| 8 | 装飾記号の排除 | front matter を対象外とする |
| 10 | Qiita Article Shape の 1 | 「はじめに」は課題や前提から書き始める |

| a | 優先順位の表 | slop-catalog の言い換え（`既定`→「初めの設定」など）を、ソフトウェアの用語には当てない |
| b | Step 3 | slop-catalog を「直すときに参照」→「直す前に読む」 |
| c | Step 3 | 「修正は最大 2 回」に数えるのはリンターの指摘への修正だけ、と 1 文足す |

和欧文間の半角空白は yomiyasu に従って空けない（ユーザー判断 2026-10-02）。

a〜c と、qiita-writer 側の Do Not への 1 行（Mermaid のラベルに記号を含むときは `"…"` で囲む）は、
2026-10-02 の試験で出た迷いを受けて足した。試験は、衝突しやすい箇所を仕込んだ架空の README から
新しいサブエージェントに記事を書かせ、13 項目で採点した（12 項目合格、Mermaid の描画だけ未検証）。

## yomiyasu を更新したとき

`build-merge.py` は、統合前の qiita-writer の SKILL.md と yomiyasu の SKILL.md から
この SKILL.md を組み立てるスクリプト。置換元が原文に 1 回だけ現れることを確かめるので、
上流で該当の文が変わっていれば、そこで止まって知らせる。

    python3 build-merge.py "$HOME" <統合前の qiita-writer SKILL.md> > SKILL.md

統合前の SKILL.md は git の 632929c 時点の `skills/qiita-writer/SKILL.md`
（`git -C ~/.claude show 632929c:skills/qiita-writer/SKILL.md`）。
