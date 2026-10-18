---
name: mac-sleep
description: Put this MacBook Air to sleep on demand, releasing Amphetamine's closed-display hold so a lid-closed Mac running on battery actually sleeps. Use when the user asks to sleep/suspend this Mac, or to end a remote work session and let the machine rest - typically from a Claude Code Remote Control session on iPhone with the lid closed. Triggers on "スリープして", "寝かせて", "スリープさせて", "作業終わり寝かせて", "sleep the mac", "put the mac to sleep", "終了してスリープ". Do NOT use for shutdown, restart, or display-only sleep.
---

# mac-sleep

蓋を閉じたままの MacBook Air を、iPhone などの遠隔セッションから明示的にスリープさせる skill。

## 最重要の禁止事項

**Amphetamine のセッションが動いている間に `sudo pmset -a disablesleep 0` を実行してはならない。**

Closed-Display Mode の実体は `pmset disablesleep` だが、これを Amphetamine の背後から書き換えると
**Amphetamine の内部状態がシステムの実態とずれる**。Amphetamine 自身がこれを異常として検知する
警告文を持っている（"An Amphetamine session is not currently active, but Power Protect is enabled
and is keeping your Mac awake"）。

これを実行すると、**Amphetamine が蓋閉じ動作の制御を握ったまま解放せず、
通常のクラムシェルモード（外部ディスプレイ+AC電源）が使えなくなる。**
Amphetamine を再起動するまで復旧しない。永続設定には痕跡が残らないため原因特定も難しい。

解除は必ず **Amphetamine 自身にやらせる**こと。

## 手順

### 1. 状態を確認する

```bash
echo "SleepDisabled : $(pmset -g | awk '/SleepDisabled/{print $2}')"
echo "session       : $(osascript -e 'tell application "Amphetamine" to session time remaining' 2>&1)"
echo "BT HID 接続数 : $(hidutil list | grep -ci bluetooth)"
pmset -g batt | tail -1
```

`session time remaining`: `0`=無期限 / `-1`=Trigger セッション / `-2`=アプリ・時刻ベース / `-3`=なし

分岐:
- **`-3`（セッションなし）かつ `SleepDisabled=0`** → 手順4へ（そのまま寝られる）
- **`-3` なのに `SleepDisabled=1`** → 異常状態。手順3の最終手段を使う
- **それ以外（セッションあり）** → 手順2へ

### 2. Amphetamine にセッションを終了させる

```bash
osascript -e 'tell application "Amphetamine" to end session'
sleep 3
pmset -g | awk '/SleepDisabled/{print $2}'
```

Amphetamine が自分で `disablesleep` を `0` に戻す。**これが正しい解除経路。**

`0` になったら手順4へ。

### 3. `1` のままだった場合（Trigger セッションが即座に再開している）

`end session` は Trigger を無効化しない。対象の Bluetooth デバイスが接続され続けている限り、
Amphetamine はセッションを再開する（公式ドキュメント: "Trigger sessions will also end with
this command, **but may immediately restart**"）。

**ここでユーザーに選択を仰ぐこと。黙って次に進まない。**

**選択肢A（推奨）: リモコンの電源を物理スイッチで切ってもらう**
条件が外れてセッションが自然終了し、`disablesleep` も Amphetamine が解除する。
最も安全で、次回の起動にも影響しない。

**選択肢B: Trigger を一時的に無効化する**
```bash
osascript -e 'tell application "Amphetamine" to disable Triggers'
osascript -e 'tell application "Amphetamine" to end session'
```
**このとき必ず伝えること: 「次にリモコンのキーを押しても保持が掛からず、
復帰後45秒ほどで再スリープします。遠隔からは元に戻せません」**
再有効化には物理アクセスか、別途 launchd の再武装ジョブが必要。
ユーザーが承知したうえで選んだ場合のみ実行する。

**最終手段（セッションが `-3` なのに `SleepDisabled=1` の異常時のみ）**
```bash
sudo -n pmset -a disablesleep 0
```
Amphetamine がクラッシュしたか、外部から書き換えられた場合の後始末。
**セッションが動いているときには絶対に使わない。**
使った場合は Amphetamine の内部状態がずれている可能性があるため、
ユーザーに **Amphetamine の再起動**を勧めること。

### 4. スリープさせる

```bash
pmset sleepnow
```

`sleepnow` は明示的なスリープ要求なので、`PreventUserIdleSystemSleep` 系のアサーションが
あっても実行される。ただし `SleepDisabled=1` は veto するため、必ず先に `0` にしておくこと。

**AC電源接続時の注意**: AC では `sleep 0`（アイドルスリープしない）設定のため、
一度寝ても Bluetooth/Wi-Fi のメンテナンス復帰でそのまま起き続ける。
持ち出す前提なら電源アダプタを抜くよう伝えること。

## 実行前に必ず伝えること

`pmset sleepnow` を実行するとこのセッションの通信は即座に切れる。実行前に、

- **接続が切れること**
- **復帰方法**（BLE リモコンのキーを押す、または蓋を開ける）
- 復帰後 Claude Code Remote Control は自動再接続すること

を伝える。実行後の応答は返らない前提で、メッセージを**先に**出しておくこと。

## やってはいけないこと

- **セッション実行中の `sudo pmset -a disablesleep 0`**（最重要。上記参照）
- `shutdown` / `reboot`。スリープ要求のみ
- ユーザーに断りなく `disable Triggers` を実行すること
- `sudo pmset` を `disablesleep 0|1` 以外の用途で実行すること
  （sudoers ルールがこの2つだけを許可している）

## 逆操作

```bash
osascript -e 'tell application "Amphetamine" to enable Triggers'   # Trigger を戻す
```

手動で `disablesleep 1` を立てるのは避ける。どうしても必要なら Amphetamine の
セッション機能を使うこと。蓋を閉じた鞄の中で起きたままになると発熱とバッテリー消耗を招く
（実測: 起きたまま約5〜6時間で尽きる。スリープ中は約0.25%/時）。

## 確認用ワンライナー

```bash
echo "SD=$(pmset -g|awk '/SleepDisabled/{print $2}') bt=$(hidutil list|grep -ci bluetooth) sess=$(osascript -e 'tell application "Amphetamine" to session time remaining' 2>/dev/null)"
```
