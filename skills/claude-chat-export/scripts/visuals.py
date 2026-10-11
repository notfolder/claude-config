"""会話 JSON のツール呼び出しブロックを Markdown に変換する。

図表は本文ではなく tool_use ブロックに入っている:
  chart_display_v0        棒グラフ。series / x_axis に生の数値
  visualize:show_widget   widget_code に HTML(CSS grid のヒートマップ) か SVG

変換方針:
  棒グラフ   -> mermaid xychart-beta   (数値は原データそのまま)
  ヒートマップ -> Markdown 表           (全セルを機械パース。mermaid に該当図種が無い)
  SVG        -> SVG をそのまま埋め込み  (無損失。mermaid 化は自動化しない)
"""
import re
import html

VISUAL_TOOLS = ('chart_display_v0', 'visualize:show_widget')


def _strip_tags(s):
    return html.unescape(re.sub(r'<[^>]*>', '', s)).strip()


def _direct_children(inner):
    """入れ子の <div> があるので、深さを数えて直下の子だけを取り出す。"""
    out, depth, start = [], 0, 0
    for m in re.finditer(r'<div\b[^>]*>|</div>', inner):
        if m.group().startswith('</'):
            depth -= 1
            if depth == 0:
                out.append(_strip_tags(inner[start:m.start()]))
        else:
            if depth == 0:
                start = m.end()
            depth += 1
    return out


def parse_heatmap(code):
    """CSS grid のヒートマップを (見出し行, データ行) に分解する。失敗したら None。"""
    m = re.search(r'grid-template-columns:\s*[^;]*repeat\((\d+)', code)
    if not m:
        return None
    n = int(m.group(1))
    g = re.search(r'(<div style="display:grid;.*)$', code, re.S)
    if not g:
        return None
    inner = g.group(1)
    cells = _direct_children(inner[inner.index('>') + 1:])
    rows = [cells[i:i + n + 1] for i in range(0, len(cells), n + 1)]
    if len(rows) < 2:
        return None
    return rows[0], rows[1:]


def heatmap_to_table(code):
    parsed = parse_heatmap(code)
    if not parsed:
        return None
    header, body = parsed
    n = len(header) - 1
    out = ['| ' + ' | '.join([''] + header[1:]) + ' |', '|' + '---|' * (n + 1)]
    for r in body:
        out.append('| **' + r[0] + '** | ' + ' | '.join(c if c else '' for c in r[1:]) + ' |')
    return '\n'.join(out)


def bar_to_mermaid(inp):
    title = inp.get('title', '')
    axis = inp.get('x_axis') or inp.get('xAxis') or {}
    labels = axis.get('data', [])
    series = inp.get('series') or []
    if not series:
        return None
    ymax = max(max(s.get('values') or [0]) for s in series)
    out = ['```mermaid', 'xychart-beta', f'    title "{title}"',
           '    x-axis [' + ', '.join(f'"{l}"' for l in labels) + ']',
           f'    y-axis 0 --> {ymax}']
    for s in series:
        out.append('    bar [' + ', '.join(str(v) for v in s.get('values') or []) + ']')
    out.append('```')
    names = [s.get('name') for s in series if s.get('name')]
    if len(names) > 1:
        out.append('\n凡例（bar の順）: ' + ' / '.join(names))
    return '\n'.join(out)


def convert(name, inp):
    """(種別ラベル, markdown) を返す。変換できなければ None。"""
    if name == 'chart_display_v0':
        md = bar_to_mermaid(inp)
        return ('棒グラフ（mermaid）', md) if md else None

    if name == 'visualize:show_widget':
        code = inp.get('widget_code') or ''
        title = inp.get('title', '')
        if '<svg' in code:
            svg = re.search(r'(?s)<svg.*</svg>', code)
            if not svg:
                return None
            desc = re.search(r'<desc>(.*?)</desc>', code, re.S)
            note = f'\n\n{_strip_tags(desc.group(1))}' if desc else ''
            # SVG は無損失でそのまま埋め込む。mermaid 化は自動化しない（SKILL.md 参照）。
            return ('図（SVG をそのまま埋め込み）', svg.group(0) + note)
        table = heatmap_to_table(code)
        if table:
            return ('ヒートマップ（表に変換）', table)
        return None

    return None


def collect(messages):
    """会話 JSON の全メッセージから図表を集める。[(msg_index, title, 種別, markdown)]"""
    out = []
    for m in messages:
        for b in (m.get('content') or []):
            if not isinstance(b, dict) or b.get('type') != 'tool_use':
                continue
            if b.get('name') not in VISUAL_TOOLS:
                continue
            inp = b.get('input') or {}
            got = convert(b['name'], inp)
            if got:
                out.append((m.get('index', 0), inp.get('title', ''), got[0], got[1]))
    return out
