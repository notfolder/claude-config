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
- 整理・書き出しはこのフックの仕事ではない（引き継ぎ準備の作業として手で行う）。
"""
import argparse, json, os, re, sys

HOME = os.path.expanduser("~")
MAX_ITEMS = 20  # これを超えたら末尾を「ほか N 件」に畳む


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
if brief is None and not groups and not a.history:
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
    out.append("🗒  未完バックログ 全%d件（%s）:" % (total, source))
    shown = 0
    for head, items in groups:
        if shown >= MAX_ITEMS:
            out.append("   … ほか %d 件（%s 参照）" % (total - shown, source))
            break
        out.append("   [%s]" % head)
        for t in items[:MAX_ITEMS - shown]:
            out.append("     - %s" % t)
        shown += min(len(items), MAX_ITEMS - shown)
elif os.path.exists(backlog) and out:
    out.append("")
    out.append("🗒  未完バックログはありません（%s）" % source)

text = "\n".join(out)
print(json.dumps({
    "systemMessage": text,
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": "%s（%s より自動読み込み）:\n%s" % (scope, origin, text),
    },
    "suppressOutput": True,
}, ensure_ascii=False))
