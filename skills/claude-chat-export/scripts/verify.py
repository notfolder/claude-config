#!/usr/bin/env python3
"""生成した Markdown が逐語であることを検証する。

  python3 verify.py --in conv.json --md out.md [--from 0] [--to 48] [--no-self-test]

「ソースの各ブロックがファイル内に存在するか」では不十分（ブロック間への混入を検出できない）。
足場（見出し・区切り線・図表の追記）を機械的に剥がし、残りがソースと**完全一致**するかを見る。
これで追加・削除・改変・並べ替えが全て検出できる。

検証コード自体が壊れることがあるため、既定で自己テストを行う。
本文を1文字壊したコピーを同じ検査にかけ、FAIL することを確認する。
"""
import argparse
import hashlib
import json
import re
import sys

SCAFFOLD_SEP = '\n---\n\n## '
VISUAL_MARK = '［原文にない追記］'
HEAD_RE = re.compile(r'\d+\. (あなた|Claude)')


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def expected_chunks(data, lo, hi):
    """build.py が出力したはずの本文チャンクを、ソースから独立に組み立て直す。"""
    out = []
    for m in sorted(data['chat_messages'], key=lambda x: x.get('index', 0)):
        if not (lo <= m.get('index', 0) <= hi):
            continue
        texts = [b['text'] for b in (m.get('content') or [])
                 if isinstance(b, dict) and b.get('type') == 'text' and b.get('text', '').strip()]
        if texts:
            out.append(''.join(t + '\n' for t in texts))
    return out


def actual_chunks(md):
    """ファイルから足場を剥がして本文チャンクを取り出す。"""
    if SCAFFOLD_SEP not in md:
        raise ValueError('見出しが見つかりません。build.py の出力ではない可能性があります。')
    _head, rest = md.split(SCAFFOLD_SEP, 1)
    chunks, bad = [], []
    for c in (SCAFFOLD_SEP + rest).split(SCAFFOLD_SEP)[1:]:
        head, after = c.split('\n\n', 1)
        if not HEAD_RE.fullmatch(head):
            bad.append(head)
        after = re.split(r'\n> \*\*' + re.escape(VISUAL_MARK), after)[0]
        chunks.append(after)
    return chunks, bad


def check(data, md, lo, hi):
    exp = expected_chunks(data, lo, hi)
    got, bad_heads = actual_chunks(md)
    same_count = len(exp) == len(got)
    mismatches = [i for i, (a, b) in enumerate(zip(exp, got)) if a != b]
    ok = same_count and not mismatches and not bad_heads and sha(''.join(exp)) == sha(''.join(got))
    return ok, dict(exp=len(exp), got=len(got), mismatches=mismatches,
                    bad_heads=bad_heads, sha_src=sha(''.join(exp)), sha_file=sha(''.join(got)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--in', dest='inp', required=True)
    ap.add_argument('--md', dest='md', required=True)
    ap.add_argument('--from', dest='lo', type=int, default=0)
    ap.add_argument('--to', dest='hi', type=int, default=10 ** 9)
    ap.add_argument('--no-self-test', action='store_true')
    a = ap.parse_args()

    with open(a.inp, encoding='utf-8') as f:
        data = json.load(f)
    with open(a.md, encoding='utf-8') as f:
        md = f.read()

    ok, info = check(data, md, a.lo, a.hi)
    print(f'チャンク数   : ソース {info["exp"]} / ファイル {info["got"]}')
    print(f'不一致       : {len(info["mismatches"])} {info["mismatches"][:5]}')
    print(f'不正な見出し : {len(info["bad_heads"])} {info["bad_heads"][:3]}')
    print(f'sha256       : {info["sha_src"][:16]} (ソース) / {info["sha_file"][:16]} (ファイル)')
    print(f'判定         : {"PASS" if ok else "FAIL"}')

    if not a.no_self_test:
        # 本文の1文字を壊したコピーが FAIL することを確認する（検証コード自体の健全性チェック）
        chunks, _ = actual_chunks(md)
        target = next((c for c in chunks if len(c.strip()) > 20), None)
        if target:
            broken = md.replace(target, target.replace(target.strip()[0], '〇', 1), 1)
            ok2, _ = check(data, broken, a.lo, a.hi)
            print(f'自己テスト   : 1文字改変で {"FAIL を検出（正常）" if not ok2 else "PASS のまま → 検証が機能していません"}')
            if ok2:
                sys.exit(3)

    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
