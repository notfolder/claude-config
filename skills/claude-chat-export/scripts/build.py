#!/usr/bin/env python3
"""会話 JSON から逐語の Markdown を組み立てる。

  python3 build.py --in conv.json --out out.md [--from 0] [--to 48]

本文は content ブロックの type:"text" をそのまま転記する（text フィールドは空なので使わない）。
挿入する足場は見出しと区切り線だけ。図表は「［原文にない追記］」と明示して追加する。
出力後は必ず verify.py をかけること。
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import visuals  # noqa: E402

SCAFFOLD_SEP = '\n---\n\n## '
VISUAL_MARK = '［原文にない追記］'


def text_blocks(msg):
    return [b['text'] for b in (msg.get('content') or [])
            if isinstance(b, dict) and b.get('type') == 'text' and b.get('text', '').strip()]


def build(data, lo, hi):
    msgs = [m for m in sorted(data['chat_messages'], key=lambda x: x.get('index', 0))
            if lo <= m.get('index', 0) <= hi]
    if not msgs:
        raise SystemExit(f'指定範囲にメッセージがありません (from={lo} to={hi})')

    vis = {t: (k, md) for _, t, k, md in visuals.collect(msgs)}
    nh = sum(1 for m in msgs if m.get('sender') == 'human')
    idx = [m.get('index', 0) for m in msgs]

    parts = [f"""# {data.get('name', '(無題)')}

- 会話 UUID: `{data.get('uuid', '')}`
- 対象範囲: msg{idx[0]} 〜 msg{idx[-1]}（{len(msgs)} 件 / あなた {nh} / Claude {len(msgs) - nh}）
- 取得方法: ログイン済み Chrome を CDP で操作し、ページ内から会話 API の生 JSON を取得

> **本文は逐語です。** 各発言は API の `content` テキストブロックを無加工で転記しています。
> 見出し（`## N. あなた` / `## N. Claude`）と区切り線 `---` だけが機械的に挿入した足場です。
> ツール実行と思考ブロックは対象外です。
>
> 図表は元会話から実データを取得して変換し、`{VISUAL_MARK}` と明示して挿入しています。
> 棒グラフ → mermaid `xychart-beta` / ヒートマップ → Markdown 表（mermaid に該当図種が無いため）/
> 図 → SVG をそのまま埋め込み（無損失）。
"""]

    used = set()
    turn = 0
    for m in msgs:
        who = 'あなた' if m.get('sender') == 'human' else 'Claude'
        texts = text_blocks(m)
        if texts:
            turn += 1
            parts.append(f'{SCAFFOLD_SEP}{turn}. {who}\n\n')
            for t in texts:
                parts.append(t)
                parts.append('\n')
        for b in (m.get('content') or []):
            if not isinstance(b, dict) or b.get('type') != 'tool_use':
                continue
            title = (b.get('input') or {}).get('title')
            if title in vis and title not in used:
                used.add(title)
                kind, md = vis[title]
                parts.append(f'\n> **{VISUAL_MARK}{kind}: `{title}`**\n\n{md}\n')

    return ''.join(parts), len(msgs), turn, len(used), len(vis)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--in', dest='inp', required=True)
    ap.add_argument('--out', dest='out', required=True)
    ap.add_argument('--from', dest='lo', type=int, default=0)
    ap.add_argument('--to', dest='hi', type=int, default=10 ** 9)
    a = ap.parse_args()

    with open(a.inp, encoding='utf-8') as f:
        data = json.load(f)
    md, nmsg, turns, nvis, nvis_total = build(data, a.lo, a.hi)
    with open(a.out, 'w', encoding='utf-8') as f:
        f.write(md)

    print(f'出力    : {a.out}')
    print(f'メッセージ: {nmsg}  見出し: {turns}')
    print(f'図表    : {nvis} / {nvis_total}')
    print(f'サイズ  : {len(md.encode())} bytes')
    print('\n次にこれを実行して逐語性を確認してください:')
    print(f'  python3 verify.py --in {a.inp} --md {a.out} --from {a.lo} --to {a.hi}')


if __name__ == '__main__':
    main()
