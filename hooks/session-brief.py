#!/usr/bin/env python3
"""前回セッションの1行概要と、未完バックログを表示する。

2 つのモードがあり、session-brief.sh が cwd を見て切り替える。

- ホーム（引数なし）: ~/docs/*-brief.md（名前降順で先頭）を 1 行に、
  未完は ~/docs/BACKLOG.md だけから拾う。
- 個別プロジェクト（--history DIR）: DIR/*/summary.md（ディレクトリ名降順で先頭）を 1 行に、
  未完は DIR/BACKLOG.md だけから拾う。無ければ「まだありません」と出す（無言にしない）。
  --created は .history をこの起動で作ったことの表示用。

共通:
- 概要は **1 行だけ**（タイトル・更新日時・`## 概要`）。詳細パスは出さない。
- 未完は BACKLOG.md の `## 見出し` ごとに `- [ ]` 行だけを拾う。BACKLOG.md が無ければ出さない。
  全テーマを通して優先度順に上位 SHOW_TOP 件を出し、その下に件数だけ出す。
  優先度は項目末尾の `期限 YYYY-MM-DD` と `重要 高/低` から毎回計算する（手で書かせない）:
  1 = 重要かつ緊急 / 2 = 緊急だけ / 3 = 重要だけ / 4 = どちらでもない。緊急 = 期限まで URGENT_DAYS 日以内か期限切れ。
- 同じ場所の IDEAS.md は件数と最新（末尾）3 件だけ出す。BACKLOG-archive.md は読まない。
- 未完・1 テーマの件数・BACKLOG.md の容量が上限を超えたら、棚卸しを促す警告を出す。
- 整理・書き出しはこのフックの仕事ではない（引き継ぎ準備の作業として手で行う）。
"""
import argparse, datetime, json, os, re, sys

HOME = os.path.expanduser("~")
SHOW_TOP = 10             # 優先度順に出す件数
URGENT_DAYS = 7           # 期限までこの日数以内なら緊急
THEME_WIDTH = 20          # テーマごとの件数の行で見出しを切り詰める文字数
LIMIT_TOTAL = 30          # 未完の上限（session-handover スキルの「引き継ぎ準備での整理」と揃える）
LIMIT_THEME = 10          # 1 テーマの未完の上限
LIMIT_BYTES = 50 * 1024   # BACKLOG.md の容量の上限
IDEAS_SHOWN = 3
IDEA_WIDTH = 60           # アイデア 1 件の表示を切り詰める文字数


def read(path):
    try:
        raw = open(path, encoding="utf-8").read()
    except OSError:
        return None
    return re.sub(r"<!--.*?-->", "", raw, flags=re.S)


def brief_line(raw, fallback_title):
    """brief / summary の本文から「📋 前回セッション: タイトル（更新）— 概要」を作る。"""
    title = next((l[2:].strip() for l in raw.splitlines() if l.startswith("# ")), fallback_title)
    updated = dict(re.findall(r"^(更新):\s*(.+)$", raw, flags=re.M)).get("更新", "日時不明")
    m = re.search(r"^##\s*概要\s*$(.*?)(?=^##\s|\Z)", raw, flags=re.M | re.S)
    summary = " ".join(m.group(1).split()) if m else ""
    line = "📋 前回セッション: %s（%s）" % (title, updated)
    return line + (" — " + summary if summary else "")


def latest_home_brief(docs_dir, suffix="-brief.md"):
    try:
        names = sorted((n for n in os.listdir(docs_dir) if n.endswith(suffix)), reverse=True)
    except OSError:
        return None
    for name in names:
        raw = read(os.path.join(docs_dir, name))
        if raw is not None:
            return brief_line(raw, name)
    return None


def latest_history_summary(hist_dir):
    try:
        names = sorted((n for n in os.listdir(hist_dir)
                        if os.path.isfile(os.path.join(hist_dir, n, "summary.md"))), reverse=True)
    except OSError:
        return None
    for name in names:
        raw = read(os.path.join(hist_dir, name, "summary.md"))
        if raw is not None:
            return brief_line(raw, name)
    return None


def backlog_groups(backlog_path):
    """BACKLOG.md を `## 見出し` ごとに分け、未完 `- [ ]` があるものだけ返す。"""
    raw = read(backlog_path)
    if raw is None:
        return []
    groups = []
    for head, body in re.findall(r"^##\s*(.+?)\s*$(.*?)(?=^##\s|\Z)", raw, flags=re.M | re.S):
        items = [re.sub(r"^-\s*\[ \]\s*", "", l.strip())
                 for l in body.splitlines() if l.strip().startswith("- [ ]")]
        if items:
            groups.append((head, items))
    return groups


META_RE = re.compile(r"\s*[（(][^（）()]*(?:追加|期限|重要)[^（）()]*[）)]\s*$")


def prioritize(groups, today):
    """全テーマの未完を (優先度, 期限, ファイル順) で並べ、表示用の dict のリストを返す。"""
    rows = []
    for head, items in groups:
        for text in items:
            m = re.search(r"期限\s*(\d{4}-\d{2}-\d{2})", text)
            due = None
            if m:
                try:
                    due = datetime.date.fromisoformat(m.group(1))
                except ValueError:
                    pass
            imp = re.search(r"重要\s*([高低])", text)
            urgent = due is not None and (due - today).days <= URGENT_DAYS
            important = bool(imp) and imp.group(1) == "高"
            prio = 1 if important and urgent else 2 if urgent else 3 if important else 4
            rows.append({"head": head, "text": META_RE.sub("", text), "due": due,
                         "prio": prio, "marked": bool(imp), "order": len(rows)})
    rows.sort(key=lambda r: (r["prio"], r["due"] or datetime.date.max, r["order"]))
    return rows


def due_note(due, today):
    if due is None:
        return ""
    days = (due - today).days
    if days < 0:
        return "（期限切れ %d 日）" % -days
    if days == 0:
        return "（期限は今日）"
    return "（期限 %s まで %d 日）" % (due.strftime("%m-%d"), days)


def idea_items(ideas_path):
    """IDEAS.md の素の `- ` 行（字下げなし・チェックボックスなし）をファイル順に返す。"""
    raw = read(ideas_path)
    if raw is None:
        return []
    return [l[2:].strip() for l in raw.splitlines()
            if l.startswith("- ") and not re.match(r"^-\s*\[", l)]


def clip(text, width):
    return text if len(text) <= width else text[:width - 1] + "…"


def overflow_warning(groups, backlog_path, source):
    """上限を超えていたら棚卸しを促す 1 行を返す。超えていなければ None。"""
    total = sum(len(items) for _, items in groups)
    reasons = []
    if total > LIMIT_TOTAL:
        reasons.append("未完 %d 件 > %d" % (total, LIMIT_TOTAL))
    big = ["%s %d 件" % (head, len(items)) for head, items in groups if len(items) > LIMIT_THEME]
    if big:
        reasons.append("1 テーマ %d 件超: %s" % (LIMIT_THEME, " / ".join(big)))
    try:
        size = os.path.getsize(backlog_path)
    except OSError:
        size = 0
    if size > LIMIT_BYTES:
        reasons.append("%s %dKB > %dKB" % (os.path.basename(backlog_path), size // 1024, LIMIT_BYTES // 1024))
    if not reasons:
        return None
    return ("⚠  棚卸しが必要（%s）。引き継ぎ準備で完了・見送りを BACKLOG-archive.md へ、"
            "案を IDEAS.md へ移し、見送り候補をユーザーに確認する: %s" % ("、".join(reasons), source))


ap = argparse.ArgumentParser()
ap.add_argument("--history", help="個別プロジェクトの .history ディレクトリ")
ap.add_argument("--created", action="store_true", help=".history をこの起動で作成した")
a = ap.parse_args()

if a.history:
    hist = os.path.abspath(a.history)
    brief = latest_history_summary(hist)
    backlog = os.path.join(hist, "BACKLOG.md")
    source = os.path.relpath(backlog, os.path.dirname(hist))          # ".history/BACKLOG.md"
    origin = "%s/*/summary.md と %s" % (os.path.relpath(hist, os.path.dirname(hist)), source)
    scope = "このプロジェクト（%s）の引き継ぎ情報" % os.path.dirname(hist)
else:
    docs = os.path.join(HOME, "docs")
    brief = latest_home_brief(docs)
    backlog = os.path.join(docs, "BACKLOG.md")
    source = backlog.replace(HOME, "~")
    origin = "最新ブリーフ %s/*-brief.md とバックログ %s" % (docs.replace(HOME, "~"), source)
    scope = "ホームの引き継ぎ情報（他プロジェクトには適用されない）"

groups = backlog_groups(backlog)
ideas_path = os.path.join(os.path.dirname(backlog), "IDEAS.md")
ideas = idea_items(ideas_path)
ideas_source = os.path.join(os.path.dirname(source), "IDEAS.md")
if brief is None and not groups and not ideas and not a.history:
    sys.exit(0)

out = []
if a.created:
    out.append("📁 .history/ を作成しました（このプロジェクトの引き継ぎ置き場。"
               "「セッションの引き継ぎ準備」で summary.md / session.md / BACKLOG.md が入る）")
if brief:
    out.append(brief)
elif a.history:
    out.append("📋 .history/ に引き継ぎ情報はまだありません（セッションの引き継ぎ準備で作られます）")

total = sum(len(items) for _, items in groups)
if total:
    if out:
        out.append("")
    today = datetime.date.today()
    rows = prioritize(groups, today)
    out.append("🔥 未完バックログ 優先度順 上位 %d 件（1 重要かつ緊急 / 2 緊急 / 3 重要 / 4 その他）:"
               % min(SHOW_TOP, total))
    for r in rows[:SHOW_TOP]:
        out.append("   %d [%s] %s%s" % (r["prio"], r["head"], r["text"], due_note(r["due"], today)))
    unmarked = sum(1 for r in rows if not r["marked"])
    out.append("🗒  全%d件（重要度の印なし %d 件）。%s" % (total, unmarked, source))
    out.append("   内訳: " + " / ".join("%s %d" % (clip(head, THEME_WIDTH), len(items))
                                       for head, items in groups))
elif os.path.exists(backlog) and out:
    out.append("")
    out.append("🗒  未完バックログはありません（%s）" % source)

warning = overflow_warning(groups, backlog, source)
if warning:
    out.append(warning)

if ideas:
    out.append("")
    out.append("💡 アイデア 全%d件（%s）。最新 %d 件:" % (len(ideas), ideas_source, min(IDEAS_SHOWN, len(ideas))))
    for t in ideas[-IDEAS_SHOWN:]:
        out.append("     - %s" % clip(t, IDEA_WIDTH))

text = "\n".join(out)
print(json.dumps({
    "systemMessage": text,
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": "%s（%s より自動読み込み）:\n%s" % (scope, origin, text),
    },
    "suppressOutput": True,
}, ensure_ascii=False))
