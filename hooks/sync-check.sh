#!/bin/bash
# SessionStart hook: ~/.claude の同期状態を報告する。
#
# 設計方針:
#   - fetch は読み取りのみ。作業ツリーには触れない
#   - 曖昧さのない場合(作業ツリーが綺麗 かつ 純粋に behind)だけ pull --ff-only する
#   - 分岐・汚れ・オフラインでは一切触らず報告のみ
#   - **必ず何か表示する**。「確認できなかった」も含めて無言になる経路を作らない
#
# 無言で pull を試みると、失敗が見えないまま古い土台で作業してしまう。
# それを避けるのがこのフックの目的なので、自動処理より報告を優先する。
#
# 出力は session-brief.py と同じ JSON 形式(systemMessage + additionalContext)にする。
# プレーンな stdout だと「hook success: ...」の1行に埋もれて読み飛ばされるため。
#
# session-brief.sh と違い cwd を問わない。~/.claude は全プロジェクト共通のため。
set -u
R="$HOME/.claude"
cat > /dev/null   # フック入力を捨てる(cwd は見ない)

MSGS=""
say() {
  if [ -n "$MSGS" ]; then
    MSGS="$MSGS
$1"
  else
    MSGS="$1"
  fi
}

# 集めたメッセージをまとめて出して終わる。
# 無言の経路を作らないため、どの分岐からもここを通って抜ける。
emit() {
  [ -n "$MSGS" ] || MSGS="[.claude] 同期状態を確認できませんでした(想定外の経路)"
  if [ -x /usr/bin/python3 ]; then
    if printf '%s' "$MSGS" | /usr/bin/python3 -c '
import json, sys
text = sys.stdin.read().rstrip("\n")
print(json.dumps({
    "systemMessage": text,
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": "~/.claude の同期状態(sync-check フックより自動確認):\n" + text,
    },
    "suppressOutput": True,
}, ensure_ascii=False))
'; then
      exit 0
    fi
  fi
  # python3 が無い / JSON 化に失敗したときは、黙るよりプレーンで出す方がまし
  printf '%s\n' "$MSGS"
  exit 0
}

command -v git > /dev/null 2>&1 || { say "[.claude] git が無いため同期状態を確認できません"; emit; }
git -C "$R" rev-parse --git-dir > /dev/null 2>&1 || { say "[.claude] git リポジトリではないため確認をスキップします"; emit; }

# パスフレーズ待ちでハングしないよう、即失敗させる
export GIT_SSH_COMMAND="ssh -o BatchMode=yes -o ConnectTimeout=3"
export GIT_TERMINAL_PROMPT=0

if ! git -C "$R" fetch --quiet origin 2>/dev/null; then
  say "[.claude] 同期状態を確認できませんでした(リモートに接続不可。オフライン?)"
  emit
fi

behind=$(git -C "$R" rev-list --count HEAD..@{u} 2>/dev/null || echo "?")
ahead=$(git -C "$R" rev-list --count @{u}..HEAD 2>/dev/null || echo "?")
if [ "$behind" = "?" ] || [ "$ahead" = "?" ]; then
  say "[.claude] 上流ブランチを解決できず、同期状態を確認できませんでした"
  emit
fi

# 追跡済みの変更と未追跡ファイルは分けて数える。
# 自動 fast-forward の可否は追跡済みの変更だけで決める(未追跡ファイルは
# 衝突しない限り ff を妨げず、妨げる場合は git 側が失敗して下で報告される)。
dirty=$(git -C "$R" status --porcelain --untracked-files=no | wc -l | tr -d ' ')
untracked=$(git -C "$R" status --porcelain --untracked-files=normal | grep -c '^??')

if [ "$behind" -gt 0 ] && [ "$ahead" -eq 0 ] && [ "$dirty" -eq 0 ]; then
  # 曖昧さのない fast-forward のみ自動実行し、実行したことを必ず報告する
  if git -C "$R" merge --ff-only --quiet '@{u}' 2>/dev/null; then
    say "[.claude] リモートの $behind コミットを取り込みました(fast-forward)"
  else
    say "[.claude] $behind コミット遅れています。取り込みに失敗したので手動で確認してください: git -C ~/.claude pull"
  fi
elif [ "$behind" -gt 0 ] && [ "$ahead" -gt 0 ]; then
  say "[.claude] 履歴が分岐しています(behind $behind / ahead $ahead)。手動マージが必要です: git -C ~/.claude pull"
elif [ "$behind" -gt 0 ]; then
  say "[.claude] リモートが $behind コミット先行しています。未コミットの変更を整理してから: git -C ~/.claude pull"
elif [ "$ahead" -gt 0 ]; then
  say "[.claude] ローカルが $ahead コミット先行しています: git -C ~/.claude push"
else
  say "[.claude] リモートとは同期しています"
fi

# 未コミットの変更は、リモートと同期していても必ず報告する。
# 「同期OK」だけ見て別PCへ移ると、この変更は向こうに届かない。
# 未追跡ファイル(新しい hooks / skills など)も同じ理由で数える。
if [ "$dirty" -gt 0 ] || [ "$untracked" -gt 0 ]; then
  say "[.claude] 未コミットの変更があります(変更 $dirty 件 / 未追跡 $untracked 件): git -C ~/.claude status"
fi

# 同期対象か判断していない第1階層のエントリを報告する。
#
# .gitignore は許可リスト方式(既定は同期しない)なので、除外の書き足し漏れで
# ゴミが混ざる事故は起きない。代わりに逆の事故が起きる: 同期すべき設定が
# 新設されても黙って除外され、片方のマシンにしか無いまま気づかない。
# それを拾うのがこのチェック。既知のマシンローカルは sync-known-local.txt に
# 列挙してあり、そこにも許可リストにも無いものだけを挙げる。
#
# 空ディレクトリは git に載らないので対象外。中身が入った時点で報告される。
KNOWN="$R/hooks/sync-known-local.txt"
unknown=""
n_unknown=0
for e in $(ls -A "$R" 2>/dev/null); do
  [ "$e" = ".git" ] && continue
  if [ -d "$R/$e" ] && [ -z "$(find "$R/$e" -type f -print -quit 2>/dev/null)" ]; then
    continue
  fi
  # 無視されていない = 許可リストに入っている = 判断済み
  git -C "$R" check-ignore -q "$e" 2>/dev/null || continue
  if [ -f "$KNOWN" ] && grep -v '^[[:space:]]*#' "$KNOWN" | grep -qxF -- "$e"; then
    continue
  fi
  n_unknown=$((n_unknown + 1))
  # 名前の列挙は 5 件まで。多いときは件数だけ伝える
  if [ "$n_unknown" -le 5 ]; then
    unknown="${unknown:+$unknown, }$e"
  fi
done
if [ "$n_unknown" -gt 0 ]; then
  [ "$n_unknown" -gt 5 ] && unknown="$unknown ほか$((n_unknown - 5))件"
  say "[.claude] 同期するか判断していないエントリが $n_unknown 件あります: $unknown"
  say "          同期するなら ~/.claude/.gitignore の許可リストに、しないなら hooks/sync-known-local.txt に足してください"
fi

emit
