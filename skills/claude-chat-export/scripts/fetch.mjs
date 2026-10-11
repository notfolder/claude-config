#!/usr/bin/env node
// claude.ai の会話 JSON を取得する。
//   node fetch.mjs <URL|uuid> [--out conv.json] [--port 9222] [--keep-open]
//
// 使い捨てプロファイルの Chrome を起動し、ユーザーの手動ログインを待ってから
// ページコンテキスト経由で会話 API を叩く。認証情報はこのスクリプトが一切扱わない。
import {writeFileSync} from 'fs';
import {launchChrome, connect} from './chrome.mjs';

const args = process.argv.slice(2);
const flag = (n, d) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1] : d; };
const has = n => args.includes(n);
const input = args.find(a => !a.startsWith('--') && args[args.indexOf(a) - 1] !== '--out' && args[args.indexOf(a) - 1] !== '--port');
const OUT = flag('--out', 'conv.json');
const PORT = Number(flag('--port', '9222'));

if (!input) {
  console.error('使い方: node fetch.mjs <https://claude.ai/chat/UUID | https://claude.ai/share/UUID | UUID> [--out conv.json]');
  process.exit(2);
}

const UUID_RE = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;
const uuid = (input.match(UUID_RE) || [])[0];
if (!uuid) { console.error(`UUID を取り出せません: ${input}`); process.exit(2); }
const isShare = /\/share\//.test(input);

const chrome = launchChrome('https://claude.ai/', {port: PORT});
console.error(`Chrome 起動: ${chrome.bin}\n  検出方法: ${chrome.how}\n  一時プロファイル: ${chrome.profile}`);
console.error('ブラウザで claude.ai にログインしてください。ログインを検知したら自動で続行します。');

let cdp;
try {
  cdp = await connect({port: PORT});

  // --- ログイン待ち（/api/organizations が 200 を返すまで） ---
  let orgs = null;
  const deadline = Date.now() + 10 * 60 * 1000;
  while (Date.now() < deadline) {
    const r = await cdp.apiGet('/api/organizations').catch(() => null);
    if (r && r.status === 200) { try { orgs = JSON.parse(r.body).map(o => o.uuid); } catch {} }
    if (orgs && orgs.length) break;
    await new Promise(r2 => setTimeout(r2, 3000));
  }
  if (!orgs) throw new Error('ログインを確認できませんでした（10分でタイムアウト）');
  console.error(`ログイン確認。組織 ${orgs.length} 件。`);

  // --- 共有リンクなら、スナップショットから会話 UUID を取り出す ---
  let convUuid = uuid;
  if (isShare) {
    const r = await cdp.apiGet(`/api/chat_snapshots/${uuid}`);
    if (r.status !== 200) throw new Error(`共有スナップショットを取得できません (status=${r.status})`);
    convUuid = JSON.parse(r.body).conversation_uuid;
    console.error(`共有リンクから会話 UUID を解決: ${convUuid}`);
    console.error('注意: 共有スナップショットは図表を失うため、本文は会話 API から取得します。');
  }

  // --- 会話 API（組織が複数返るので 200 が来る方を使う） ---
  let saved = false;
  for (const org of orgs) {
    const path = `/api/organizations/${org}/chat_conversations/${convUuid}`
               + `?tree=True&rendering_mode=messages&render_all_tools=true`;
    const r = await cdp.apiGet(path);
    console.error(`  org ${org.slice(0, 8)} -> ${r.status}`);
    if (r.status !== 200) continue;
    const data = JSON.parse(r.body);
    writeFileSync(OUT, JSON.stringify(data, null, 1));
    const n = (data.chat_messages || []).length;
    console.error(`\n保存: ${OUT}\n  タイトル: ${data.name}\n  メッセージ数: ${n}`);
    saved = true;
    break;
  }
  if (!saved) throw new Error('どの組織でも会話を取得できませんでした');
} finally {
  try { cdp?.close(); } catch {}
  if (!has('--keep-open')) { await chrome.close(); console.error('Chrome を終了し、一時プロファイルを削除しました。'); }
  else console.error(`Chrome は起動したままです（プロファイル: ${chrome.profile}）。`);
}
