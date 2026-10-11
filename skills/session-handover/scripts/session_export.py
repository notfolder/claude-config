#!/usr/bin/env python3
"""Claude Code のセッションログ（~/.claude/projects/<cwd>/<id>.jsonl）を Markdown に書き出す。

- ユーザー発言と Claude の本文（text ブロック）は逐語で転記する
- ツール呼び出しは 1 行（ツール名 + 説明/コマンド冒頭）に要約し、ツール結果と思考ブロックは出さない
- <system-reminder> などの付加情報は除く。/clear 等のコマンドと「Request interrupted」は残す

使い方:
  session_export.py [--cwd DIR] [--session ID] [--out FILE] [--full-tools]
  省略時は「現在の cwd に対応するプロジェクトの、最後に更新された .jsonl」＝現在のセッション。
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECTS = Path("~/.claude/projects").expanduser()
STRIP_TAGS = ("system-reminder", "local-command-caveat", "local-command-stdout", "ide_selection", "ide_opened_file")
TOOL_LINE_MAX = 160


def encode_cwd(cwd: str) -> str:
    """Claude Code が projects/ 配下のディレクトリ名に使う変換（英数字以外を '-' に）。"""
    return re.sub(r"[^A-Za-z0-9]", "-", cwd)


def find_session(cwd: str, session_id: str | None):
    d = PROJECTS / encode_cwd(cwd)
    if not d.is_dir():
        sys.exit(f"プロジェクトのログディレクトリがありません: {d}")
    if session_id:
        p = d / f"{session_id}.jsonl"
        if not p.is_file():
            sys.exit(f"セッションログがありません: {p}")
        return p
    files = sorted(d.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        sys.exit(f".jsonl がありません: {d}")
    return files[0]


def clean_user_text(t: str) -> str:
    for tag in STRIP_TAGS:
        t = re.sub(rf"<{tag}>.*?</{tag}>", "", t, flags=re.S)
    # /clear などのローカルコマンドは 1 行に
    m = re.search(r"<command-name>(.*?)</command-name>", t, flags=re.S)
    if m:
        args = re.search(r"<command-args>(.*?)</command-args>", t, flags=re.S)
        t = re.sub(r"<command-[a-z]+>.*?</command-[a-z]+>", "", t, flags=re.S)
        t = f"（コマンド: {m.group(1).strip()} {args.group(1).strip() if args else ''}）".rstrip() + "\n" + t
    return t.strip()


def tool_line(block: dict, full: bool) -> str:
    name = block.get("name", "?")
    inp = block.get("input") or {}
    desc = inp.get("description") or inp.get("command") or inp.get("file_path") or inp.get("prompt") or inp.get("query") or inp.get("url") or ""
    if isinstance(desc, str):
        desc = " ".join(desc.split())
        if not full and len(desc) > TOOL_LINE_MAX:
            desc = desc[:TOOL_LINE_MAX] + "…"
    return f"> 🔧 `{name}` {desc}".rstrip()


def fmt_ts(ts: str) -> str:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ts


def export(path: Path, full_tools: bool) -> tuple[str, dict]:
    out, n = [], 0
    who = None          # 直前に見出しを出した側: "user" / "assistant"
    first_ts = last_ts = None
    session_id = path.stem
    cwd = version = branch = None
    stats = {"user": 0, "assistant": 0, "tools": 0}

    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        t = d.get("type")
        if t not in ("user", "assistant"):
            continue
        if d.get("isMeta"):
            continue
        cwd = cwd or d.get("cwd"); version = version or d.get("version"); branch = branch or d.get("gitBranch")
        ts = d.get("timestamp")
        if ts:
            first_ts = first_ts or ts
            last_ts = ts
        m = d.get("message") or {}
        c = m.get("content")

        if t == "user":
            texts = []
            if isinstance(c, str):
                texts.append(c)
            elif isinstance(c, list):
                for b in c:
                    if isinstance(b, dict) and b.get("type") == "text":
                        texts.append(b.get("text", ""))
            txt = "\n\n".join(clean_user_text(x) for x in texts if x and x.strip()).strip()
            if not txt:
                continue
            n += 1; stats["user"] += 1
            out.append(f"## {n}. ユーザー（{fmt_ts(ts)}）\n\n{txt}\n")
            who = "user"
        else:
            if not isinstance(c, list):
                continue
            parts = []
            for b in c:
                if not isinstance(b, dict):
                    continue
                bt = b.get("type")
                if bt == "text" and b.get("text", "").strip():
                    parts.append(b["text"].strip())
                elif bt == "tool_use":
                    parts.append(tool_line(b, full_tools)); stats["tools"] += 1
            if not parts:
                continue
            if who != "assistant":
                n += 1; stats["assistant"] += 1
                out.append(f"## {n}. Claude\n")
                who = "assistant"
            out.append("\n".join(parts) + "\n")

    header = [
        f"# セッションログ {session_id[:8]}",
        "",
        f"- セッション: `{session_id}`",
        f"- cwd: `{cwd}`" + (f"（branch: {branch}）" if branch else ""),
        f"- 期間: {fmt_ts(first_ts)} 〜 {fmt_ts(last_ts)}" if first_ts else "- 期間: 不明",
        f"- Claude Code: {version}" if version else "",
        f"- 発言: ユーザー {stats['user']} / Claude {stats['assistant']} / ツール呼び出し {stats['tools']}",
        f"- 書き出し: {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z')}",
        "",
        "> ユーザー発言と Claude の本文は逐語。ツール呼び出しは `🔧` の 1 行に要約し、ツール結果・思考ブロックは含まない。",
        "",
        "---",
        "",
    ]
    return "\n".join(x for x in header if x is not None) + "\n".join(out), {
        "session_id": session_id, "first_ts": first_ts, "last_ts": last_ts, **stats}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cwd", default=os.getcwd(), help="プロジェクトディレクトリ（既定: カレント）")
    ap.add_argument("--session", help="セッション ID（既定: 最後に更新された .jsonl）")
    ap.add_argument("--out", help="出力ファイル（既定: 標準出力）")
    ap.add_argument("--full-tools", action="store_true", help="ツール行を切り詰めない")
    a = ap.parse_args()

    path = find_session(os.path.abspath(a.cwd), a.session)
    md, info = export(path, a.full_tools)
    if a.out:
        outp = Path(a.out).expanduser()
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(md, encoding="utf-8")
        print(f"source : {path}")
        print(f"session: {info['session_id']}")
        print(f"range  : {fmt_ts(info['first_ts'])} 〜 {fmt_ts(info['last_ts'])}")
        print(f"counts : user {info['user']} / claude {info['assistant']} / tools {info['tools']}")
        print(f"out    : {outp} ({len(md)} chars)")
    else:
        sys.stdout.write(md)


if __name__ == "__main__":
    main()
