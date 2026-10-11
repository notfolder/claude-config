#!/usr/bin/env python3
"""Qiita API v2 で Markdown 記事を投稿・更新する（標準ライブラリのみ）。

- 既定は private=True（限定共有）。公開は --public を明示したときだけ。
- front matter の title / tags を使う。本文先頭の「# タイトル」行は Qiita 側で
  タイトルが別表示されるため除く。
- 投稿結果は記事と同じディレクトリの .qiita-post.json に記録し、再実行時は
  その item_id を PATCH で更新する（重複投稿を防ぐ）。--new で強制新規。
- トークンは環境変数 QIITA_TOKEN、無ければ ~/.env → ~/.env.txt の
  QIITA-KEY / QIITA_KEY / QIITA_TOKEN を読む。値は一切表示しない。
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://qiita.com/api/v2"
RECORD = ".qiita-post.json"
ENV_FILES = ["~/.env", "~/.env.txt"]
KEY_NAMES = ("QIITA-KEY", "QIITA_KEY", "QIITA_TOKEN")
MAX_BODY = 100_000
MAX_TITLE = 255


def load_token():
    tok = os.environ.get("QIITA_TOKEN")
    if tok:
        return tok, "env:QIITA_TOKEN"
    pat = re.compile(r"""\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_-]*)\s*=\s*["']?([^"'\s]+)""")
    for f in ENV_FILES:
        p = Path(f).expanduser()
        if not p.is_file():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            m = pat.match(line)
            if m and m.group(1).upper() in KEY_NAMES:
                return m.group(2), f"{f}:{m.group(1)}"
    sys.exit("QIITA トークンが見つかりません。環境変数 QIITA_TOKEN か、"
             + " / ".join(ENV_FILES) + " に " + " / ".join(KEY_NAMES) + " を置いてください")


def parse_article(path: Path):
    text = path.read_text(encoding="utf-8")
    meta = {}
    m = re.match(r"^---\n(.*?)\n---\n", text, flags=re.S)
    if m:
        for line in m.group(1).splitlines():
            k, _, v = line.partition(":")
            if _:
                meta[k.strip()] = v.strip()
        text = text[m.end():]
    body = text.lstrip("\n")
    title = meta.get("title", "")
    # 先頭の H1 がタイトルと同じなら除く（Qiita はタイトルを別に表示する）
    first = body.split("\n", 1)[0].strip()
    if first.startswith("# "):
        h1 = first[2:].strip()
        if not title:
            title = h1
        if h1 == title:
            body = body.split("\n", 1)[1].lstrip("\n") if "\n" in body else ""
    tags = [t for t in re.split(r"[\s,]+", meta.get("tags", "")) if t]
    return title, tags, body


def request(method, url, token, payload=None):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "qiita-post-skill/1.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(body)
        except ValueError:
            pass
        return e.code, body


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("article", help="投稿する Markdown（front matter に title / tags）")
    ap.add_argument("--public", action="store_true", help="公開記事として投稿（既定は限定共有）")
    ap.add_argument("--new", action="store_true", help=".qiita-post.json があっても新規投稿する")
    ap.add_argument("--item-id", help="更新対象の item id を明示する")
    ap.add_argument("--title", help="front matter の title を上書き")
    ap.add_argument("--tags", help="front matter の tags を上書き（空白区切り）")
    ap.add_argument("--dry-run", action="store_true", help="送信せずに payload の概要だけ表示")
    a = ap.parse_args()

    path = Path(a.article).expanduser().resolve()
    if not path.is_file():
        sys.exit(f"ファイルがありません: {path}")
    title, tags, body = parse_article(path)
    if a.title:
        title = a.title
    if a.tags:
        tags = a.tags.split()

    errs = []
    if not title:
        errs.append("title が空です（front matter か --title で指定）")
    if len(title) > MAX_TITLE:
        errs.append(f"title が {MAX_TITLE} 文字を超えています")
    if not 1 <= len(tags) <= 5:
        errs.append(f"tags は 1〜5 個です（現在 {len(tags)}）")
    if any(re.search(r"\s", t) for t in tags):
        errs.append("tag に空白は使えません")
    if not body.strip():
        errs.append("本文が空です")
    if len(body) > MAX_BODY:
        errs.append(f"本文が {MAX_BODY} 文字を超えています（{len(body)}）")
    if errs:
        sys.exit("\n".join("ERROR: " + e for e in errs))

    payload = {
        "title": title,
        "body": body,
        "tags": [{"name": t, "versions": []} for t in tags],
        "private": not a.public,
        "tweet": False,
    }

    record_path = path.parent / RECORD
    record = {}
    if record_path.is_file():
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
        except ValueError:
            record = {}
    item_id = a.item_id or (None if a.new else record.get("item_id"))

    print(f"title : {title}")
    print(f"tags  : {' '.join(tags)}")
    print(f"body  : {len(body)} 文字")
    print(f"mode  : {'公開' if a.public else '限定共有（private）'}")
    print(f"action: {'更新 ' + item_id if item_id else '新規投稿'}")
    if a.dry_run:
        print("dry-run: 送信しません")
        return

    token, src = load_token()
    print(f"token : {src}")

    if item_id:
        status, res = request("PATCH", f"{API}/items/{item_id}", token, payload)
    else:
        status, res = request("POST", f"{API}/items", token, payload)

    if status not in (200, 201):
        sys.exit(f"ERROR: HTTP {status}\n{json.dumps(res, ensure_ascii=False, indent=2)}")

    record = {
        "item_id": res.get("id"),
        "url": res.get("url"),
        "private": res.get("private"),
        "title": res.get("title"),
        "article": str(path),
        "updated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    }
    record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"result: HTTP {status} {'更新' if item_id else '作成'}")
    print(f"url   : {res.get('url')}")
    print(f"record: {record_path}")


if __name__ == "__main__":
    main()
