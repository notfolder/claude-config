"""qiita-writer と yomiyasu の SKILL.md を統合する。
原文の節を切り出して並べ、衝突する文だけを置換する。置換元は原文に 1 回だけ現れることを確かめる。"""
import re, sys
HOME = sys.argv[1]
qw = open(f"{HOME}/.claude/skills/qiita-writer/SKILL.md", encoding="utf-8").read() if len(sys.argv) < 3 else open(sys.argv[2], encoding="utf-8").read()
yo = open(f"{HOME}/.claude/skills/yomiyasu/SKILL.md", encoding="utf-8").read()

def sections(text):
    """'## ' 見出しごとに切る（コードブロック内の行は見出しとみなさない）"""
    out, cur, name, fence = {}, [], None, False
    for line in text.split("\n"):
        if line.startswith("```"):
            fence = not fence
        if not fence and line.startswith("## "):
            if name: out[name] = "\n".join(cur).rstrip("\n").rstrip("-").rstrip("\n")
            name, cur = line[3:].strip(), [line]
        elif name:
            cur.append(line)
    out[name] = "\n".join(cur).rstrip("\n").rstrip("-").rstrip("\n")
    return out

def sub(text, old, new):
    assert text.count(old) == 1, f"置換元が {text.count(old)} 回: {old[:40]}"
    return text.replace(old, new)

Q = sections(qw)
Y = sections(yo)
front = qw[: qw.index("# qiita-writer")]
intro = "# qiita-writer\n\nQiita 向けの日本語技術記事を作成・整理・改善するための skill です。"
assert intro in qw

# --- yomiyasu 1章: 日本語の書き方 -------------------------------------------------
y1 = Y["1. コア設計思想"]
yintro = "AI特有のスカスカな文体、不自然な比喩、壊れたSVOCM（主述関係）を解体し、人間が引っかかりなく読める自然な日本語へ加工するスキルです。"
assert yo.count(yintro) == 1
y1 = sub(y1, "## 1. コア設計思想", "## 日本語の書き方（yomiyasu 由来）\n\n" + yintro)
# 衝突 7: 記事化では「元の文」が素材になり、構成は組み直す
y1 = sub(y1, "他の原則は、この4点を変えない範囲でのみ適用します。",
         "他の原則は、この4点を変えない範囲でのみ適用します。\n"
         "メモや README から記事を起こすときは、素材の文を「元の文」として扱います。4点の保持は文の単位で守り、"
         "記事全体の構成や説明順を組み直すことは Qiita Article Shape と Output Patterns の規則に従います。")
# 衝突 8: front matter はコロンの規則の対象外
y1 = sub(y1, "和欧文間の不自然な半角空白を完全に排除します。",
         "和欧文間の不自然な半角空白を完全に排除します。front matter（`title:` など）はこの規則の対象外とし、書き換えません。")

# --- yomiyasu 2章: 実行手順 --------------------------------------------------------
y2 = Y["2. 実行手順"]
y2 = sub(y2, "## 2. 実行手順", "## 実行手順（yomiyasu 由来）")
# 衝突 2・3: ドメインは tech 固定。箇条書きの上限は Step 2 の 9 に委ねる
y2 = sub(y2, y2[y2.index("入力されたテキストや指示文"): y2.index("明示的な指定がない場合は、文脈から自動判別します。") + len("明示的な指定がない場合は、文脈から自動判別します。")],
         "Qiita 記事は常に `tech`（技術記事）として扱います。business・essay の仕様は使いません。\n\n"
         "- `tech` (技術記事): 技術ブログや設計書。元の文や資料にある情報の範囲で手順を整理します（元にないコマンドやコード片を勝手に作って足しません）。箇条書きの扱いは Step 2 の 9 に従います。")
y2 = sub(y2, "### Step 1: ドメインとモードの判定", "### Step 1: ドメインの判定")
# 資料の場所（yomiyasu の references を直接読む）
y2 = sub(y2, "`references/gemini-syntax.md` およびドメイン別仕様に従い、以下の手順で変換します。",
         "執筆や書き直しの前に `~/.claude/skills/yomiyasu/references/gemini-syntax.md` と "
         "`~/.claude/skills/yomiyasu/references/domains/tech.md` を読み、それらに従って以下の手順で変換します。"
         "資料と本ファイルが食い違うときは、冒頭の「優先順位」に従います。")
# 衝突 3: 並列データの箇条書きは残す
y2 = sub(y2, "9. 無駄な太字を外し、箇条書きを地の文の段落へ統合します。",
         "9. 無駄な太字を外し、思考の流れや理由を並べただけの箇条書きは地の文の段落へ統合します。"
         "変更点・手順・パラメータ・比較のような並列データは、箇条書きや表のまま残します。")
# 衝突 6: 毎回、実際のパスで検査する
y2 = sub(y2, "フルモード指定時やファイル保存時は、同梱のリンターを実行して静的検査を行います。",
         "article.md を書き出したら、毎回リンターを実行して静的検査を行います。")
y2 = sub(y2, "# スキル配置先（${CLAUDE_SKILL_DIR}等）を基準にスクリプトの絶対パスを解決して実行\n"
             "python3 <スキル配置ディレクトリ>/scripts/yomiyasu_lint.py <対象ファイル>",
         "python3 ~/.claude/skills/yomiyasu/scripts/yomiyasu_lint.py docs/qiita/<YYYY-MM-DD>-<slug>/article.md")
y2 = sub(y2, "警告を消すためだけの過剰な言い換えループを防止します。",
         "警告を消すためだけの過剰な言い換えループを防止します。"
         "回数に数えるのはリンターの指摘に応じた修正だけで、意味を元の文に戻すための修正は数えません。\n\n"
         "指摘を直す前に `~/.claude/skills/yomiyasu/references/slop-catalog.md` を読み、その言い換え方針に従います。"
         "箇条書き比率の警告は、並列データの箇条書きなら無視してかまいません。"
         "front matter・コードブロック（Mermaid を含む）・表はリンターの対象外なので、指摘を理由に書き換えません。"
         "残した警告は、残した理由を添えてユーザーに報告します。スクリプトが無い環境では検査を省略し、その旨を報告します。")

# --- qiita-writer 側の置換 ---------------------------------------------------------
op = Q["Output Patterns"]
# 衝突 5: yomiyasu の対話用出力フォーマットは使わず、記事と報告に振り分ける
op = sub(op, "2. article.md を出力（front matter → 本文 → 補足・未確認事項）\n3. 作成したファイルパスをユーザーに報告",
         "2. 「日本語の書き方」と「実行手順」に従って article.md を出力（front matter → 本文 → 補足・未確認事項）。"
         "「補足・未確認事項」には、実行手順の終了後確認で出た「書き手に確かめたい点」も入れる\n"
         "3. 実行手順の Step 3 でリンターを実行する\n"
         "4. 作成したファイルパスと、残した警告とその理由をユーザーに報告")
op = sub(op, "原稿の事実関係を増やさず、構成・見出し・説明順・読みやすさを中心に整える",
         "原稿の事実関係を増やさず、構成・見出し・説明順・読みやすさを中心に整える。"
         "文の書き直しは「日本語の書き方」と「実行手順」に従い、終えたら Step 3 のリンターを実行する。"
         "会話では、実際に変更した点を簡潔に報告する")
donot = sub(Q["Do Not"], "- Mermaid の構文エラーを出さない（シンプルな構文を優先する）",
            "- Mermaid の構文エラーを出さない（シンプルな構文を優先する）\n"
            "- Mermaid のラベルに `--` や括弧などの記号を含むときは、`B{\"--write を指定したか\"}` のように `\"…\"` で囲む")
shape = Q["Qiita Article Shape"]
# 衝突 10・4
shape = sub(shape, "1. はじめに\n", "1. はじめに（空疎な前置きを書かず、解決したい課題や前提から書き始める）\n")
shape = sub(shape, "7. おわりに", "7. おわりに（「いかがでしたか」のような定型の締めを書かず、次の一歩や未対応事項を書く）")

priority = """## 優先順位

日本語の書き方と実行手順は yomiyasu（MIT, https://github.com/nanaism/yomiyasu）の SKILL.md を取り込んでいる。由来と書き換えた箇所は同じディレクトリの SOURCE.md にある。

- このスキルを使っている間は、yomiyasu スキルを別途起動しない。規則は本ファイルに取り込み済みで、両方を読み込むと Qiita 向けに書き換える前の規則が並んでしまう。
- 実行手順で読む yomiyasu の資料（gemini-syntax.md・domains/tech.md・slop-catalog.md）と本ファイルが食い違うときは、本ファイルに従う。既知の食い違いは次のとおり。

| 資料の記述 | 従う規則 |
|---|---|
| tech.md「箇条書きの比率は全体の15%以下」「思考の流れや論理展開を箇条書きに頼らず、地の文の段落で記述」 | 並列データ（変更点・手順・パラメータ・比較）は箇条書きや表のまま残す（実行手順 Step 2 の 9） |
| tech.md「短い記事では「まとめ」見出しを配置しません」 | 「おわりに」は残し、定型の締めを書かない（Qiita Article Shape） |
| 文末コロン・絵文字の完全排除 | front matter は対象外とし、書き換えない |
| slop-catalog.md の言い換え（`既定`→「初めの設定」、`要点`→「大事なところ」など） | ソフトウェアの用語として使われている語（既定値・既定のエンコーディングなど）には当てず、そのまま残す |"""

parts = [front.rstrip("\n"), "", intro, "", priority, "",
         Q["Output Location"], "", op, "", donot, "",
         y1, "", Q["Purpose"], "", shape, "", Q["Writing Rules"], "", Q["Front Matter Rules"], "",
         y2, "", Q["Diagrams"], "", Q["Practical Notes"], ""]
out = "\n".join(parts)
# 取りこぼし検査: qiita-writer の全節と yomiyasu の 1・2 章が入っていること
for k in Q: assert Q[k].split("\n")[0] in out or k in ("Output Patterns", "Qiita Article Shape"), k
print(out)
