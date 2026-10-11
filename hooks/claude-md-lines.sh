#!/bin/bash
# PostToolUse フック: CLAUDE.md を書き換えたあとに行数を測り、上限以上なら Claude に警告を返す。
# ユーザー指示 2026-09-24「CLAUDE.md は 200 行未満で」。
#
# **session-handover スキルを起動したセッションでだけ鳴る**（ユーザー指示 2026-09-24）。
# 整理は引き継ぎ準備のときにまとめて行う前提で、通常の編集では黙る。
# 判定は transcript を見て {"name":"Skill","input":{"skill":"session-handover"}} を探す。
#
# 上限は環境変数 CLAUDE_MD_MAX_LINES で変えられる（既定 200）。
# 終了コード 2 + stderr で Claude に伝わる（書き換え自体は済んでいるので取り消さない）。

LIMIT="${CLAUDE_MD_MAX_LINES:-200}"
SKILL="session-handover"
input="$(cat)"

# 対象ファイルを決める。ただし、このセッションで session-handover スキルが
# 起動していなければ何も出さずに終わる。
targets="$(printf '%s' "$input" | SKILL="$SKILL" python3 -c '
import json, os, sys

d = json.load(sys.stdin)
skill = os.environ["SKILL"]

# --- スキルが起動しているセッションかを見る ---
tp = d.get("transcript_path") or ""
if not tp or not os.path.isfile(tp):
    sys.exit(0)
found = False
with open(tp, encoding="utf-8", errors="replace") as fh:
    for line in fh:
        if '"'"'"Skill"'"'"' not in line or skill not in line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        for c in (rec.get("message", {}) or {}).get("content", []) or []:
            if (isinstance(c, dict) and c.get("name") == "Skill"
                    and (c.get("input") or {}).get("skill") == skill):
                found = True
                break
        if found:
            break
if not found:
    sys.exit(0)

# --- 測る対象を決める。Edit/Write は file_path、Bash は既知の 3 か所 ---
ti = d.get("tool_input", {}) or {}
fp = ti.get("file_path") or ""
cmd = ti.get("command") or ""
out = []
if os.path.basename(fp) == "CLAUDE.md":
    out.append(fp)
elif "CLAUDE.md" in cmd:
    home = os.path.expanduser("~")
    proj = os.environ.get("CLAUDE_PROJECT_DIR") or d.get("cwd") or os.getcwd()
    for p in (os.path.join(proj, "CLAUDE.md"),
              os.path.join(home, ".claude", "CLAUDE.md"),
              os.path.join(home, "CLAUDE.md")):
        if os.path.isfile(p) and p not in out:
            out.append(p)
print("\n".join(out))
' 2>/dev/null)"

[ -z "$targets" ] && exit 0

over=0
while IFS= read -r f; do
  [ -f "$f" ] || continue
  n="$(wc -l < "$f" | tr -d ' ')"
  b="$(wc -c < "$f" | tr -d ' ')"
  if [ "$n" -ge "$LIMIT" ]; then
    over=1
    echo "[claude-md-lines] $f は $n 行（$b バイト）で、上限 $LIMIT 行以上です。" >&2
    echo "  毎回読む必要がある決まりだけを 1 項目 1 行で残し、経緯・引用・具体例・失った時間は" >&2
    echo "  docs/rules/ に移してリンクにしてください（skills/session-handover/SKILL.md 手順 4）。" >&2
  fi
done <<< "$targets"

[ "$over" = 1 ] && exit 2
exit 0
