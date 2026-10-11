// Chrome の検出・起動と、依存ゼロの CDP クライアント。
// Node 22+ の組み込み WebSocket を使うので puppeteer/playwright は不要。
import {existsSync, rmSync, mkdtempSync} from 'fs';
import {execSync, spawn} from 'child_process';
import {tmpdir} from 'os';
import {join} from 'path';

const sh = c => { try { return execSync(c, {stdio:['ignore','pipe','ignore']}).toString().trim() || null; } catch { return null; } };

/** 4段フォールバックで Chrome の実行ファイルを探す。見つからなければ throw。 */
export function findChrome() {
  const P = process.platform, tried = [];
  const check = (label, p) => { if (!p) return null; tried.push(`${label}: ${p}`); return existsSync(p) ? p : null; };

  // 1) 環境変数
  let hit = check('CHROME_PATH', process.env.CHROME_PATH);
  if (hit) return {path: hit, how: 'CHROME_PATH', tried};

  // 2) 既知パス
  const known = {
    darwin: ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
             `${process.env.HOME}/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`,
             '/Applications/Chromium.app/Contents/MacOS/Chromium'],
    linux:  ['/opt/google/chrome/chrome', '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable',
             '/usr/bin/chromium', '/usr/bin/chromium-browser', '/snap/bin/chromium'],
    win32:  [`${process.env.PROGRAMFILES || ''}\\Google\\Chrome\\Application\\chrome.exe`,
             `${process.env['PROGRAMFILES(X86)'] || ''}\\Google\\Chrome\\Application\\chrome.exe`,
             `${process.env.LOCALAPPDATA || ''}\\Google\\Chrome\\Application\\chrome.exe`],
  }[P] || [];
  for (const p of known) { hit = check('既知パス', p); if (hit) return {path: hit, how: '既知パス', tried}; }

  // 3) PATH 検索
  const names = P === 'win32' ? ['chrome.exe']
              : ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'chrome'];
  for (const n of names) {
    const p = sh(`${P === 'win32' ? 'where' : 'command -v'} ${n}`)?.split('\n')[0];
    hit = check('PATH', p); if (hit) return {path: hit, how: 'PATH', tried};
  }

  // 4) OS への問い合わせ
  if (P === 'darwin') {
    const app = sh(`mdfind "kMDItemCFBundleIdentifier == 'com.google.Chrome'" | head -1`);
    hit = check('mdfind', app ? `${app}/Contents/MacOS/Google Chrome` : null);
    if (hit) return {path: hit, how: 'mdfind', tried};
  } else if (P === 'win32') {
    const out = sh(`reg query "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\chrome.exe" /ve`);
    const m = out && out.match(/REG_SZ\s+(.+chrome\.exe)/i);
    hit = check('registry', m && m[1].trim()); if (hit) return {path: hit, how: 'registry', tried};
  }

  throw new Error(
    `Chrome が見つかりません (platform=${P})。環境変数 CHROME_PATH に実行ファイルのパスを設定してください。\n` +
    `試したもの:\n  ${tried.join('\n  ') || '(候補なし)'}`);
}

/** 使い捨てプロファイルで Chrome を起動する。Chrome 136+ は既定プロファイルでのデバッグを拒否するため必須。 */
export function launchChrome(url, {port = 9222} = {}) {
  const {path: bin, how} = findChrome();
  const profile = mkdtempSync(join(tmpdir(), 'cce-chrome-'));
  const child = spawn(bin, [
    `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`,
    '--no-first-run', '--no-default-browser-check', '--window-size=1400,1000', url,
  ], {detached: true, stdio: 'ignore'});
  child.unref();
  return {
    bin, how, profile, port, pid: child.pid,
    async close() {
      try { child.kill('SIGTERM'); } catch {}
      await new Promise(r => setTimeout(r, 800));
      try { rmSync(profile, {recursive: true, force: true}); } catch {}
    },
  };
}

/** CDP に接続し、ページターゲットで JS を評価できるようにする。 */
export async function connect({port = 9222, match = 'claude.ai', timeoutMs = 60000} = {}) {
  const deadline = Date.now() + timeoutMs;
  let target = null;
  while (Date.now() < deadline) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      target = list.find(t => t.type === 'page' && (t.url || '').includes(match));
      if (target) break;
    } catch {}
    await new Promise(r => setTimeout(r, 500));
  }
  if (!target) throw new Error(`CDP のページターゲットが見つかりません (match=${match})`);

  const ws = new WebSocket(target.webSocketDebuggerUrl);
  const pending = new Map(); let id = 0;
  ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });

  const send = (method, params = {}) => new Promise(r => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({id: i, method, params})); });
  const evaluate = async (expression, awaitPromise = false) => {
    const r = await send('Runtime.evaluate', {expression, returnByValue: true, awaitPromise});
    if (r.result?.exceptionDetails) throw new Error('評価に失敗: ' + JSON.stringify(r.result.exceptionDetails).slice(0, 300));
    return r.result?.result?.value;
  };
  /** ページのコンテキストから fetch する。Cookie と Cloudflare クリアランスが要るため外部 curl では不可。 */
  const apiGet = async (path) => {
    const raw = await evaluate(
      `fetch(${JSON.stringify(path)},{headers:{accept:'application/json'}})
         .then(async r => JSON.stringify({status: r.status, body: await r.text()}))`, true);
    return JSON.parse(raw);
  };
  return {evaluate, apiGet, navigate: u => send('Page.navigate', {url: u}), close: () => ws.close()};
}
