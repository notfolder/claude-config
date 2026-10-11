# claude-config

個人で使っているClaude Codeの設定（`~/.claude`）のうち、複数のマシンで共有しているものです。
自分の作業のやり方に合わせて作ってあるので、そのまま使うよりも、必要な部分だけを拾って使う想定です。

## 中身

| 場所 | 内容 |
|---|---|
| `CLAUDE.md` | 全プロジェクト共通の指示（応答の仕方、作業の進め方、確認の出し方、見積もり、引き継ぎ） |
| `estimate-log.md` | 作業量の見積もりのルールと、見積もりと実績のずれの記録 |
| `hooks/` | SessionStartなどのフック（前回の引き継ぎの表示、同期状態の確認、更新の確認、CLAUDE.mdの行数の確認） |
| `skills/` | スキル（claude.aiの会話の書き出し、Macのスリープ、Qiitaへの投稿と記事の作成、引き継ぎとバックログの運用、日本語のリライト） |
| `settings.example.json` | フックの登録の見本。`settings.json`自体はマシンごとに持ち、同期しない |

`.gitignore`は許可リスト方式で、既定では何も同期しません。
会話履歴、メモリ、計画（`plans/`）、認証情報、`settings.json`はリポジトリに入りません。

## 使い方

### `~/.claude`がまだ無いマシン

次のコマンドで`~/.claude`にcloneします。

```sh
git clone git@github.com:notfolder/claude-config.git ~/.claude
```

### `~/.claude`がすでにあるマシン

Claude Codeを一度でも起動したマシンには`~/.claude`があり、会話履歴や`settings.json`、自分で作ったスキルが入っています。
`git clone`は空でないディレクトリには使えないので、Claude Code自身に取り込みとマージを任せる手順です。
手元のファイルを上書きする前に、Claude Codeが差分を見せて確認を取ります。

ほかに動いているClaude Codeのセッションはすべて終了してください。
そのうえでホームディレクトリでClaude Codeを起動し、次のプロンプトを貼り付けます。

```text
https://github.com/notfolder/claude-config を ~/.claude に取り込み、手元の設定とマージしてください。
次の順に進め、手元のファイルを書き換える前に必ず私の確認を取ってください。

1. 退避: ~/.claude/.git があれば ~/.claude-git-old に移す。
   CLAUDE.md・hooks/・skills/ を ~/.claude-CLAUDE.md.bak・~/.claude-hooks.bak・~/.claude-skills.bak にコピーする。
2. 取り込み: ~/.claude で git init -b main、origin に git@github.com:notfolder/claude-config.git を足し、
   fetch してから git reset --mixed origin/main で HEAD だけを合わせ、git branch --set-upstream-to=origin/main する。
   この時点では手元のファイルに触れない。
3. 差分の一覧: git status と git diff で、リポジトリにしか無いファイル・中身が違うファイル・
   手元にしか無いファイルを分けて表にする。ファイルごとに「リポジトリの版を使う／手元の版を残す／両方を合わせる」
   のどれがよいかを、理由を付けて提案する。
4. マージ: 承認された方針で反映する。
   - リポジトリにしか無いファイルは git checkout -- <パス> で取り出す。
   - CLAUDE.md は、手元にしか無い指示を消さずに両方を合わせる。そのマシンにしか関係しない指示は
     ~/CLAUDE.md に移すことを提案する。
   - 手元にしか無いフックやスキルは消さない。
5. フックの登録: settings.example.json の hooks を、手元の settings.json の hooks に足す。
   同じコマンドが既にあれば足さない。settings.json のほかの設定には触れない。
6. 報告: 最後に git status を見せ、マージで生じた差分（手元で書き換えたファイル）を一覧にする。
   コミットと push はしない。

.credentials.json・projects/・settings.local.json は読まず、変更もしないでください。
```

登録したフックが効くのは、次に起動したセッションからです。
フックの一部は、`~/docs/`に引き継ぎの記録を置く運用を前提にしています。
取り込みが済んで問題が無ければ、退避した`~/.claude-git-old`や`~/.claude-*.bak`は消してかまいません。

## ライセンス

MIT（`LICENSE`）です。ただし、次の節に挙げる他者の著作物は、それぞれのライセンスに従います。

## 他者の著作物

`skills/yomiyasu/`は、[nanaism/yomiyasu](https://github.com/nanaism/yomiyasu)（MIT）を取り込み、リンターに手を加えたものです。
ライセンスは`skills/yomiyasu/LICENSE`に、由来と変更点は`SOURCE.md`にあります。

`skills/qiita-writer/SKILL.md`は、yomiyasuのSKILL.mdの一部を取り込んでいます。
ライセンスは`skills/qiita-writer/LICENSE-yomiyasu`、由来は`SOURCE.md`です。

## 注意

`skills/claude-chat-export/`は、ログイン済みのChromeを操作して、claude.aiの非公開のAPIから会話を取り出します。
公式に提供された方法ではないので、使う場合は自己責任でお願いします。

`skills/mac-sleep/`は、`sudo pmset`をパスワードなしで実行できるsudoersの設定が前提です。
