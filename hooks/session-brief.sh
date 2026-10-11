#!/bin/bash
# SessionStart hook: 前回セッションの1行概要と未完バックログを表示する。
#
# cwd で切り替える:
#   - cwd == $HOME   → ~/docs/*-brief.md と ~/docs/BACKLOG.md（ホームの引き継ぎ）
#   - それ以外       → $cwd/.history/ を使う（個別プロジェクトの引き継ぎ。skills/session-handover/SKILL.md 参照）。
#                      無ければ作る（ユーザー指示 2026-09-06）。作れない場所なら何もしない
input=$(cat)
cwd=$(printf '%s' "$input" | /usr/bin/jq -r '.cwd // ""' 2>/dev/null)
if [ "$cwd" = "$HOME" ]; then
  exec /usr/bin/python3 "$HOME/.claude/hooks/session-brief.py"
elif [ -n "$cwd" ] && [ -d "$cwd" ]; then
  created=""
  if [ ! -d "$cwd/.history" ]; then
    mkdir "$cwd/.history" 2>/dev/null && created="--created"
  fi
  if [ -d "$cwd/.history" ]; then
    exec /usr/bin/python3 "$HOME/.claude/hooks/session-brief.py" --history "$cwd/.history" $created
  fi
fi
exit 0
