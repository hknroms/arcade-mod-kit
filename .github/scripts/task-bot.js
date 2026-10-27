// 共同作業ボット: Issue コメントのコマンドで、作業タスクの状態・確認項目・提出物を記録する。
// .github/workflows/task-bot.yml から actions/github-script で呼ばれる。
//
// 作業の種類（ラベル）: 検証 / 調査 / 実装 / 素材 / 資料
// 状態（ラベル）      : 未着手 → 担当中 → 確認待ち → 完了（人の確認が必要なものは 要人間確認）
//
// コマンド（コメントの行頭に書く。1つのコメントに複数行書いてよい）
//   /claim                   担当する
//   /check 番号 ok|ng|hold   確認項目に結果を付ける（hold = 人の目で確認が必要）
//   /submit URL [ひとこと]   成果物を提出する（自分のフォークの枝・コミット・PR などの GitHub の URL）
//   /done [ひとこと]         終わり。検証は ok だけなら完了、ng/hold/未チェックがあれば要人間確認。
//                            検証以外は「確認待ち」（管理者が /accept すると完了）
//   /human [ひとこと]        人の判断が必要なので「要人間確認」にする
//   /release                 担当をやめて「未着手」に戻す
//   ── 管理者のみ ──
//   /items                   次の行からの箇条書きを確認項目として追加し、タスクにする
//   /type 種類               作業の種類を変える（検証・調査・実装・素材・資料）
//   /accept [ひとこと]       提出物を取り込んだ／確認できた → 完了
//   /reject ひとこと         直してほしい点を伝えて「担当中」に戻す

const TYPES = ['検証', '調査', '実装', '素材', '資料'];
const REQUEST = '要望';
const REQUEST_ITEMS = [
  '書かれている現象・要望について、今の版での動きを確かめる（再現手順も書く）',
  '純正（改造なし）ではどうなるかと比べる',
  '直し方・変え方の案と、影響しそうなところをまとめる',
];

const L = { todo: '未着手', doing: '担当中', review: '確認待ち', human: '要人間確認', done: '完了' };
const STATUS = [L.todo, L.doing, L.review, L.human, L.done];
const LABEL_DEFS = [
  { name: '検証', color: '1f6feb', description: '作業: テストプレイ・動作の検証' },
  { name: '調査', color: '8250df', description: '作業: ROMの解析・原因調査' },
  { name: '実装', color: '0e8a16', description: '作業: 改造・修正のコードを書く' },
  { name: '素材', color: 'e16f24', description: '作業: 画像・パレット・タイル・文字など' },
  { name: '資料', color: '0969da', description: '作業: 説明書・翻訳・ページ' },
  { name: REQUEST, color: 'fbca04', description: '改善したいこと（協力者の声・人から聞いた話）。自動で検証タスクになる' },
  { name: L.todo, color: 'bfbfbf', description: 'まだ誰も担当していない' },
  { name: L.doing, color: 'd29922', description: '担当者が作業中' },
  { name: L.review, color: '1d76db', description: '提出済み・管理者の確認待ち' },
  { name: L.human, color: 'f85149', description: '人の目・判断が必要' },
  { name: L.done, color: '3fb950', description: '完了' },
];
const RENAMES = [['検証済み', L.done]];
const STALE_DAYS = 3;
const MARK = /<!-- (?:verify|task)-state (\{[^]*?\}) -->/;
const ITEM = /^(\s*)- \[( |x|X)\] (.*)$/;
const MARKS = { ok: '✅', ng: '❌', hold: '⚠️' };
const MARK_PREFIX = /^(✅|❌|⚠️) /;
const HIST_MAX = 40;

function getState(body) {
  const m = (body || '').match(MARK);
  if (!m) return {};
  try { return JSON.parse(m[1]); } catch { return {}; }
}
function cleanStr(v) { return String(v).replace(/--/g, '—').replace(/[<>]/g, '').slice(0, 300); }
function setState(body, st) {
  const clean = JSON.parse(JSON.stringify(st, (k, v) => (typeof v === 'string' ? cleanStr(v) : v)));
  const s = `<!-- task-state ${JSON.stringify(clean)} -->`;
  body = body || '';
  return MARK.test(body) ? body.replace(MARK, s) : body.replace(/\s*$/, '') + '\n\n' + s + '\n';
}
function items(body) {
  const out = [];
  (body || '').split('\n').forEach((line, i) => {
    const m = line.match(ITEM);
    if (m) {
      const text = m[3];
      const mk = (text.match(MARK_PREFIX) || [])[1] || '';
      out.push({ line: i, checked: m[2] !== ' ', mark: mk, text: text.replace(MARK_PREFIX, '') });
    }
  });
  return out;
}
function checkItem(body, n, result) {
  const lines = body.split('\n');
  const it = items(body)[n - 1];
  if (!it) return null;
  const indent = lines[it.line].match(ITEM)[1];
  lines[it.line] = `${indent}- [${result === 'hold' ? ' ' : 'x'}] ${MARKS[result]} ${it.text}`;
  return lines.join('\n');
}
function summary(body) {
  const list = items(body);
  return {
    total: list.length,
    ok: list.filter(i => i.mark === '✅' || (i.checked && !i.mark)).length,
    ng: list.filter(i => i.mark === '❌').length,
    hold: list.filter(i => i.mark === '⚠️').length,
    open: list.filter(i => !i.checked && i.mark !== '⚠️').length,
  };
}
function section(body, name) {
  const m = (body || '').match(new RegExp('^### ' + name + '\\s*\\n+([^]*?)(?=\\n### |\\n<!--|$)', 'm'));
  const v = m ? m[1].trim() : '';
  return v === '_No response_' ? '' : v;
}
function parseCommands(text) {
  const lines = (text || '').split('\n');
  const cmds = [];
  lines.forEach((raw, i) => {
    // Windows の Git Bash（MSYS）から送ると「/claim」が「C:/Program Files/Git/claim」に化ける → 元に戻す
    const line = raw.trim().replace(/^[A-Za-z]:\/Program Files(?: \(x86\))?\/Git\//i, '/');
    const m = line.match(/^\/(claim|check|submit|done|human|release|items|type|accept|reject)\b\s*(.*)$/i);
    if (!m) return;
    const c = { name: m[1].toLowerCase(), arg: m[2].trim() };
    if (c.name === 'items') {
      const rest = [];
      for (let j = i + 1; j < lines.length; j++) {
        const t = lines[j].trim();
        if (t.startsWith('/') || /^(-{3,}|\*{3,}|_{3,})$/.test(t)) break;
        const im = t.match(/^(?:[-*]\s+|・\s*|\d+[.)]\s+)(?:\[[ xX]\]\s*)?(.+)$/);
        if (im) rest.push(im[1].trim());
      }
      c.items = rest;
    }
    cmds.push(c);
  });
  return cmds;
}
function typeOf(labels) { return TYPES.find(t => labels.includes(t)) || null; }

module.exports = async ({ github, context, core }) => {
  const { owner, repo } = context.repo;
  const now = new Date().toISOString();

  async function ensureLabels() {
    for (const [from, to] of RENAMES) {
      try { await github.rest.issues.updateLabel({ owner, repo, name: from, new_name: to }); core.info(`renamed ${from} -> ${to}`); } catch {}
    }
    for (const d of LABEL_DEFS) {
      try { await github.rest.issues.createLabel({ owner, repo, ...d }); }
      catch (e) { if (e.status === 422) { try { await github.rest.issues.updateLabel({ owner, repo, ...d }); } catch {} } else throw e; }
    }
  }
  async function setLabels(num, labels, { status, type }) {
    const drop = [];
    if (status) drop.push(...STATUS.filter(l => l !== status));
    if (type) drop.push(...TYPES.filter(t => t !== type));
    for (const l of drop) if (labels.includes(l)) {
      try { await github.rest.issues.removeLabel({ owner, repo, issue_number: num, name: l }); } catch {}
    }
    const add = [status, type].filter(Boolean).filter(l => !labels.includes(l));
    if (add.length) await github.rest.issues.addLabels({ owner, repo, issue_number: num, labels: add });
  }
  const reply = (num, body) => github.rest.issues.createComment({ owner, repo, issue_number: num, body });
  const react = (id, content) => github.rest.reactions.createForIssueComment({ owner, repo, comment_id: id, content }).catch(() => {});
  const push = (st, who, what, extra) => {
    st.history = (st.history || []).concat([{ who, what, at: now, ...(extra || {}) }]).slice(-HIST_MAX);
  };

  const ev = context.eventName;

  if (ev === 'workflow_dispatch') { await ensureLabels(); core.info('labels ok'); }

  if (ev === 'schedule' || ev === 'workflow_dispatch') {
    const list = await github.paginate(github.rest.issues.listForRepo, { owner, repo, state: 'open', labels: L.doing, per_page: 100 });
    for (const is of list) {
      const st = getState(is.body);
      const last = Date.parse(st.updated_at || st.claimed_at || is.updated_at);
      if (Date.now() - last > STALE_DAYS * 86400e3) {
        const who = st.claimer;
        delete st.claimer; delete st.claimed_at; st.updated_at = now;
        push(st, 'bot', 'timeout', { prev: who });
        await github.rest.issues.update({ owner, repo, issue_number: is.number, body: setState(is.body, st) });
        await setLabels(is.number, is.labels.map(l => l.name), { status: L.todo });
        await reply(is.number, `${STALE_DAYS}日間報告がなかったので「未着手」に戻しました${who ? `（前の担当: @${who}）` : ''}。続ける場合はもう一度 \`/claim\` してください。`);
      }
    }
    return;
  }

  const issue = context.payload.issue;
  if (!issue || issue.pull_request) return;
  const num = issue.number;
  const labels = issue.labels.map(l => l.name);
  let body = issue.body || '';

  if (ev === 'issues') {
    // テンプレートから作られた・種類ラベルが付いた → 種類と「未着手」を整え、状態欄を用意
    let type = typeOf(labels);
    const picked = section(body, '作業の種類');
    const fromForm = TYPES.find(t => picked.startsWith(t));
    if (fromForm) type = fromForm;
    // 「要望」（改善したいこと）は自動で検証タスクにし、確認項目が無ければ基本の3項目を付ける
    if (labels.includes(REQUEST) && !type) {
      type = '検証';
      if (!items(body).length) {
        body = body.replace(MARK, '').replace(/\s*$/, '') + '\n\n### 確認項目\n' + REQUEST_ITEMS.map(t => '- [ ] ' + t).join('\n') + '\n';
        await github.rest.issues.update({ owner, repo, issue_number: num, body });
      }
    }
    if (!type) return;
    const status = STATUS.find(s => labels.includes(s)) ? null : L.todo;
    await setLabels(num, labels, { status, type });
    if (!MARK.test(body)) await github.rest.issues.update({ owner, repo, issue_number: num, body: setState(body, { created_at: now, history: [{ who: issue.user.login, what: 'open', at: now }] }) });
    return;
  }

  if (ev !== 'issue_comment') return;
  const c = context.payload.comment;
  const actor = c.user.login;
  if (c.user.type === 'Bot') return;
  const isAdmin = ['OWNER', 'MEMBER', 'COLLABORATOR'].includes(c.author_association);
  const cmds = parseCommands(c.body);
  if (!cmds.length) return;

  const st = getState(body);
  const errors = [];
  let status = STATUS.find(s => labels.includes(s)) || null;
  let type = typeOf(labels);
  let changed = false;
  const canEdit = () => isAdmin || st.claimer === actor;
  const isTask = () => !!type || status !== null;
  const did = new Set();

  for (const cmd of cmds) {
    const n = cmd.name;
    if (n === 'items' || n === 'type') {
      if (!isAdmin) { errors.push(`\`/${n}\` は管理者だけが使えます`); continue; }
      if (n === 'type') {
        const t = TYPES.find(x => cmd.arg.startsWith(x));
        if (!t) { errors.push(`種類は ${TYPES.join('・')} のどれかです（例: \`/type 調査\`）`); continue; }
        type = t; if (!status) status = L.todo; changed = true; continue;
      }
      if (!cmd.items.length) { errors.push('`/items` の次の行に「- やること」の形で項目を書いてください'); continue; }
      const block = cmd.items.map(t => `- [ ] ${t}`).join('\n');
      if (/^### 確認項目\s*$/m.test(body)) {
        const ls = body.split('\n');
        let at = ls.findIndex(l => /^### 確認項目\s*$/.test(l)) + 1;
        while (at < ls.length && (ITEM.test(ls[at]) || ls[at].trim() === '')) at++;
        while (at > 0 && ls[at - 1].trim() === '') at--;
        ls.splice(at, 0, block);
        body = ls.join('\n');
      } else {
        body = body.replace(MARK, '').replace(/\s*$/, '') + `\n\n### 確認項目\n${block}\n`;
      }
      if (!type) type = '検証';
      if (!status) status = L.todo;
      changed = true;
      continue;
    }
    if (!isTask()) { errors.push('このIssueはまだ作業タスクではありません（管理者が `/items` か `/type` で始められます）'); break; }

    if (n === 'claim') {
      if (status === L.doing && st.claimer && st.claimer !== actor) { errors.push(`すでに @${st.claimer} さんが担当中です。別の「未着手」を選んでください`); continue; }
      if (status === L.done) { errors.push('このタスクは「完了」しています'); continue; }
      st.claimer = actor; st.claimed_at = now; status = L.doing; changed = true; did.add('claim');
    } else if (n === 'check') {
      if (!canEdit()) { errors.push('`/check` は担当者（先に `/claim`）か管理者だけが使えます'); continue; }
      const m = cmd.arg.match(/^(\d+)\s+(ok|ng|hold)\b/i);
      if (!m) { errors.push(`\`/check ${cmd.arg}\` が読めません。例: \`/check 2 ok\``); continue; }
      const nb = checkItem(body, Number(m[1]), m[2].toLowerCase());
      if (nb === null) { errors.push(`確認項目 ${m[1]} 番はありません（全${items(body).length}件）`); continue; }
      body = nb; changed = true; did.add('check');
    } else if (n === 'submit') {
      if (!canEdit()) { errors.push('`/submit` は担当者（先に `/claim`）か管理者だけが使えます'); continue; }
      const m = cmd.arg.match(/^(https:\/\/github\.com\/\S+)\s*(.*)$/);
      if (!m) { errors.push('`/submit` の後に GitHub の URL を書いてください（例: `/submit https://github.com/あなた/{{REPO_NAME}}/tree/task-7 解析メモ`）'); continue; }
      st.submissions = (st.submissions || []).concat([{ url: m[1], by: actor, at: now, note: m[2] || '' }]).slice(-10);
      if (m[2]) st.note = m[2];
      status = L.review; changed = true; did.add('submit');
    } else if (n === 'done') {
      if (!canEdit()) { errors.push('`/done` は担当者か管理者だけが使えます'); continue; }
      if (type === '検証') { const s = summary(body); status = (s.ng || s.hold || s.open) ? L.human : L.done; }
      else status = L.review;
      st.done_at = now; st.done_by = actor; if (cmd.arg) st.note = cmd.arg; changed = true; did.add('done');
    } else if (n === 'human') {
      if (!canEdit()) { errors.push('`/human` は担当者か管理者だけが使えます'); continue; }
      status = L.human; if (cmd.arg) st.note = cmd.arg; changed = true; did.add('human');
    } else if (n === 'release') {
      if (!canEdit()) { errors.push('`/release` は担当者か管理者だけが使えます'); continue; }
      delete st.claimer; delete st.claimed_at; status = L.todo; changed = true; did.add('release');
    } else if (n === 'accept') {
      if (!isAdmin) { errors.push('`/accept` は管理者だけが使えます'); continue; }
      status = L.done; st.accepted_at = now; st.accepted_by = actor; if (cmd.arg) st.note = cmd.arg; changed = true; did.add('accept');
    } else if (n === 'reject') {
      if (!isAdmin) { errors.push('`/reject` は管理者だけが使えます'); continue; }
      if (!cmd.arg) { errors.push('`/reject` の後に直してほしい点を書いてください'); continue; }
      status = st.claimer ? L.doing : L.todo; st.note = '差し戻し: ' + cmd.arg; changed = true; did.add('reject');
    }
  }

  if (changed) {
    st.updated_at = now;
    st.last_by = actor;
    st.last_comment = c.html_url;
    for (const what of did) push(st, actor, what);
    await github.rest.issues.update({ owner, repo, issue_number: num, body: setState(body, st) });
    await setLabels(num, labels, { status, type });
  }
  if (errors.length) { await react(c.id, 'confused'); await reply(num, `@${actor} ` + errors.map(e => `- ${e}`).join('\n')); }
  else if (changed) await react(c.id, '+1');
};

module.exports._test = { getState, setState, items, checkItem, summary, parseCommands, section, TYPES, L };
