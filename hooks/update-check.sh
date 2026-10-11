#!/bin/bash
# SessionStart hook（startup|clear）: Claude Code の更新が出ていれば 1 行で知らせる。
#
# 設計方針（ユーザー判断 2026-10-09）:
#   - 知らせるだけで、更新はしない。作業中のセッションの裏で本体を差し替えると、
#     動いている Claude Code と中身の版がずれる。更新はユーザーが `claude update` で行う
#   - 毎回確認する（キャッシュしない）。配布元は版番号だけを返すので約 0.6 秒で済み、
#     間隔を空けるための状態ファイルを持つ手間の方が大きい
#   - 比べる相手は手元と同じ配布系統（settings.json の autoUpdatesChannel、既定は latest）。
#     違う系統と比べると、知らせる版と実際に入る版がずれる
#   - **更新が無いとき・確認できないときは何も出さない。** sync-check.sh の「必ず何か表示する」
#     とは逆。毎回「最新です」と出ると読み飛ばす癖がつき、本当に出たときに気づけないため
#
# 配布元はネイティブ版の公式インストーラ（https://claude.ai/install.sh）が参照するものと同じ。
set -u
cat > /dev/null   # フック入力を捨てる

BASE="https://downloads.claude.ai/claude-code-releases"

channel=$(/usr/bin/python3 -c '
import json, os
try:
    print(json.load(open(os.path.expanduser("~/.claude/settings.json"))).get("autoUpdatesChannel") or "latest")
except Exception:
    print("latest")
' 2>/dev/null)
[ "$channel" = "stable" ] || channel="latest"

bin="$HOME/.local/bin/claude"
[ -x "$bin" ] || bin=$(command -v claude 2>/dev/null) || exit 0
current=$("$bin" --version 2>/dev/null | awk 'NR==1{print $1}')
latest=$(/usr/bin/curl -fsS -m 3 "$BASE/$channel" 2>/dev/null | tr -d '[:space:]')

# 版番号の形をしていなければ（オフライン・エラーページ等）黙って終わる
case "$current$latest" in *[!0-9.]*) exit 0 ;; esac
[ -n "$current" ] && [ -n "$latest" ] || exit 0

# 配布元の方が新しいときだけ知らせる（手元が先行している場合は黙る）
/usr/bin/python3 - "$current" "$latest" "$channel" <<'EOF'
import json, sys
cur, new, ch = sys.argv[1:4]
key = lambda v: tuple(int(x) for x in v.split("."))
if key(new) <= key(cur):
    sys.exit(0)
text = f"[Claude Code] 更新があります: {cur} → {new}（{ch} 系統）。`claude update` で更新できます"
print(json.dumps({
    "systemMessage": text,
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": "Claude Code の更新状況(update-check フックより自動確認):\n" + text,
    },
    "suppressOutput": True,
}, ensure_ascii=False))
EOF
exit 0
