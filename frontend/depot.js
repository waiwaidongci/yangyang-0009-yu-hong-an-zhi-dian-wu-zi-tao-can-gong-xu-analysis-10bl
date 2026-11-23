import {api, badge, empty, h, mount, notice, waitJob} from '/base.js';

import {lotsPage} from './lots-page.js';
import {alternatesPage} from './alternates-page.js';
import {shelterArrival} from './shelter-arrival.js';

const pages = { requests: '安置点需求', overlap: '共需搭配', packing: '整箱筹备', dispatch: '出库复核', lots:'批次拣配', alternates:'备选换品', arrivals:'到点点收' };
const requestPhase = { submitted: '待核单', confirmed: '已核单' };
const slipPhase = { draft: '待复核', approved: '已出库', shelved: '已搁置', voided: '已停用' };
const surveyPhase = { queued: '分析中', ready: '已出结果', voided: '已停用' };
const state = { request: null, run: null, pair: null, slip: null };
const responsePath = '/api/flood-responses';
const percent = value => (value * 100).toFixed(0) + '%';

function heading(title, text, incident) {
  return `<header class="depot-heading"><div><h1>${h(title)}</h1><p>${h(text)}</p></div>
    <div class="incident-ribbon"><span>${h(incident.response_code)} / ${h(incident.river_sector)}</span><strong>${h(incident.warehouse)}</strong></div></header>`;
}

function action(outlet, selector, submit, redraw) {
  const target = outlet.querySelector(selector);
  if (!target) return;
  const form = target instanceof HTMLFormElement;
  target.addEventListener(form ? 'submit' : 'click', async event => {
    event.preventDefault();
    const button = form ? target.querySelector('[type=submit]') : target;
    button.disabled = true;
    try {
      await submit(form ? new FormData(target) : null);
      await redraw();
    } catch (error) {
      notice(outlet.querySelector('[data-feedback]'), error.message, true);
      button.disabled = false;
    }
  });
}

function selectRows(outlet, key, redraw) {
  for (const button of outlet.querySelectorAll('[data-select]')) {
    button.onclick = () => { state[key] = Number(button.dataset.select); redraw(); };
  }
}

async function requestDesk(outlet, base, incident, user, redraw) {
  const {requests, stock} = await api(base + '/requests');
  const selected = requests.find(row => row.id === state.request) ?? requests[0];
  outlet.innerHTML = heading('安置点需求', '按单确认户数和物资明细。只有已核单的记录进入共需样本。', incident)
    + `<div class="intake-board"><section class="paper-sheet"><h2>来单登记簿</h2>
      <ol class="depot-queue">${requests.map(row => `<li><button class="queue-button" type="button" data-select="${row.id}" aria-pressed="${selected.id === row.id}">
       <span><span class="depot-mono">${h(row.slip)}</span> · ${h(row.shelter)}</span>${badge(requestPhase[row.phase],row.phase)}</button></li>`).join('')}</ol>
      ${requests.length ? '' : empty('尚无需求单。录入一条安置点现场申报。')}</section>
      <section class="paper-sheet"><h2>${selected ? h(selected.shelter) : '核单明细'}</h2>
      ${selected ? `<p>${h(selected.slip)} · 覆盖 ${selected.households} 户 · ${badge(requestPhase[selected.phase],selected.phase)}</p>
      <ul class="goods-list">${selected.lines.map(line => `<li><span>${h(line.name)}</span><strong>${line.units} 件</strong></li>`).join('')}</ul>
      ${selected.phase === 'confirmed' ? `<p class="subdued">核单人 ${h(selected.confirm_by)} · 更正 ${selected.revision} 次</p>`
       : user.role === 'reviewer' ? '<button id="confirm" type="button">核对需求并确认</button>' : ''}
      ${selected.phase === 'confirmed' && user.role === 'reviewer' ? `<details class="receipt-form"><summary>更正已核物资</summary><form id="correction-form">
        <p class="subdued">更正会即时停用含本单的共需场次，草案与换品同意随之失效。</p>
        <fieldset><legend>更正后申报件数</legend><div class="depot-two">${stock.map(item => { const line = selected.lines.find(row => row.item_id === item.id);
          return `<label>${h(item.name)}<input name="qty-${item.id}" type="number" min="0" max="3600" value="${line ? line.units : 0}"></label>`; }).join('')}</div></fieldset>
        <label>更正原因<input name="reason" minlength="4" maxlength="200" required placeholder="来电更正覆盖户数与物资"></label>
        <button type="submit">保存更正并重算共需</button></form></details>` : ''}
      ${selected.corrections?.length ? `<details class="receipt-form"><summary>更正记录（${selected.corrections.length}）</summary>
        <ol class="depot-queue">${selected.corrections.map(row => `<li><span>${h(row.reason)}</span><small>${h(row.corrected_by)} · ${h(row.created_at)}</small></li>`).join('')}</ol></details>` : ''}
      ` : '<p>选中现场来单后核查申报件数。</p>'}
      ${user.role === 'operator' ? `<details class="receipt-form"><summary>录入安置点来单</summary><form id="request-form">
        <div class="depot-two"><label>来单号<input name="slip" pattern="[A-Z0-9-]{3,28}" required placeholder="RV-W09"></label><label>覆盖户数<input name="households" type="number" min="1" max="600" required></label></div>
        <label>安置点<input name="shelter" required placeholder="河西小学"></label>
        <fieldset><legend>申报物资件数</legend><div class="depot-two">${stock.map(item => `<label>${h(item.name)}<input name="qty-${item.id}" type="number" min="0" max="3600" placeholder="0"></label>`).join('')}</div></fieldset>
        <button type="submit">提交需求单</button></form></details>` : ''}
      <p role="status" data-feedback></p></section></div>`;
  selectRows(outlet, 'request', redraw);
  action(outlet, '#confirm', () => api(base + '/requests/' + selected.id + '/confirm', 'POST'), redraw);
  action(outlet, '#correction-form', async form => {
    const lines = stock.map(item => ({item_id:item.id, units:Number(form.get('qty-' + item.id))})).filter(line => line.units > 0);
    if (!lines.length) throw Error('至少填写一种物资的申报件数。');
    await api(base + '/requests/' + selected.id + '/corrections', 'POST', {reason:form.get('reason'), lines});
  }, redraw);
  action(outlet, '#request-form', async form => {
    const lines = stock.map(item => ({item_id:item.id, units:Number(form.get('qty-' + item.id))})).filter(line => line.units > 0);
    if (!lines.length) throw Error('至少填写一种物资的申报件数。');
    const receipt = await api(base + '/requests', 'POST', {slip:form.get('slip'),
      shelter:form.get('shelter'), households:Number(form.get('households')), lines});
    state.request = receipt.id;
  }, redraw);
}

async function overlapView(outlet, base, incident, user, redraw) {
  const {surveys} = await api(base + '/surveys');
  const run = surveys.find(item => item.id === state.run) ?? surveys[0];
  outlet.innerHTML = heading('共需搭配', '从已核单安置点的物资交集筛选成对搭配，并保留每次分析的样本范围。', incident)
    + `<div class="mining-bench"><aside class="paper-sheet threshold-panel"><h2>样本与门槛</h2>
       ${surveys.length ? `<label>查看场次<select id="survey-choice">${surveys.map(item => `
       <option value="${item.id}" ${run.id === item.id ? 'selected' : ''}>第 ${item.id} 次 · ${item.sample_ids.length} 单 · ${surveyPhase[item.status]}</option>`).join('')}</select></label>` : ''}
       ${user.role !== 'viewer' ? `<form id="survey-form">
         <label>最低共同出现率（%）<input name="min_support_pct" type="number" value="30" min="1" max="100" required></label>
         <label>最低提升度<input name="min_lift" type="number" value="1.10" min="1" max="25" step="0.01" required></label>
         <button type="submit">冻结样本并分析</button></form>` : ''}
       <p role="status" data-feedback></p></aside>
       <section class="paper-sheet"><h2>成对共需</h2>
       ${run?.status === 'voided' ? `<p class="subdued">此场次已停用：${h(run.voided_reason)}</p>
         <p>停用时间 ${h(run.voided_at)}${run.superseded_by ? ` · 新结果见第 ${run.superseded_by} 次分析 <button type="button" class="quiet" id="view-replacement" data-survey="${run.superseded_by}">查看</button>` : ''}</p>
         ${run.pairs.length ? `<h3 class="subdued">停用前的旧结果（仅供查阅）</h3><div class="rule-sheets">${run.pairs.map(pair => `<article class="joint-rule stale">
           <h3>${h(pair.name_a)} <span>＋</span> ${h(pair.name_b)}</h3>
           <p>共 ${pair.intersection} 单 · 支持度 ${percent(pair.support)} · 提升度 ${pair.lift.toFixed(2)}</p>
           <small>旧搭配已停用，不可用于新的整箱筹备。</small></article>`).join('')}</div>`
           : empty('此场次停用前没有成对共需结果。')}`
        : run?.status === 'ready' ? `<p>样本 ${run.sample_ids.length} 单 · 共同出现率至少 ${run.min_support_pct}% · 提升度至少 ${run.min_lift}</p>
         ${run.pairs.length ? `<div class="rule-sheets">${run.pairs.map(pair => `<article class="joint-rule">
           <h3>${h(pair.name_a)} <span>＋</span> ${h(pair.name_b)}</h3>
           <meter min="0" max="${run.sample_ids.length}" value="${pair.intersection}" aria-label="共同出现次数"></meter>
           <p>共 ${pair.intersection} 单 · 支持度 ${percent(pair.support)} · 提升度 ${pair.lift.toFixed(2)}</p>
           <small>从 ${h(pair.name_a)} 到 ${h(pair.name_b)} ${percent(pair.conf_ab)} · 反向 ${percent(pair.conf_ba)}</small>
           <a href="#packing" data-pair="${pair.id}">查看整箱筹备</a></article>`).join('')}</div>`
           : empty('当前门槛下未找到成对共需。可核对样本或降低门槛后重新分析。')}`
        : empty(run ? (run.job_status === 'failed' ? '后台计算失败。可按原门槛重试。' : '后台正在计算，此次样本已冻结。')
                    : '生成分析后可查看支持度与方向置信度。')}
        ${run?.status === 'queued' ? '<button type="button" id="refresh-survey">刷新状态</button>' : ''}
        ${run && run.job_status === 'failed' ? `<p class="subdued">${h(run.job_error)}</p><button type="button" id="retry-survey">按原门槛重试</button>` : ''}</section></div>`;
  outlet.querySelector('#survey-choice')?.addEventListener('change', event => { state.run = Number(event.target.value); redraw(); });
  outlet.querySelector('#view-replacement')?.addEventListener('click', event => {
    state.run = Number(event.currentTarget.dataset.survey); redraw();
  });
  for (const link of outlet.querySelectorAll('[data-pair]')) link.onclick = () => { state.pair = Number(link.dataset.pair); };
  action(outlet, '#refresh-survey', () => {}, redraw);
  action(outlet, '#retry-survey', async () => {
    const {job_id} = await api(base + '/surveys/' + run.id + '/retry', 'POST');
    notice(outlet.querySelector('[data-feedback]'), '已按原门槛重新排队。');
    await waitJob(job_id);
  }, redraw);
  action(outlet, '#survey-form', async form => {
    const {survey, job_id} = await api(base + '/surveys', 'POST', {
      min_support_pct:Number(form.get('min_support_pct')), min_lift:Number(form.get('min_lift')),
    });
    state.run = survey.id;
    notice(outlet.querySelector('[data-feedback]'), '已冻结来单，后台执行交集计算。');
    await waitJob(job_id);
  }, redraw);
}

async function packingDesk(outlet, base, incident, user, redraw) {
  const [inventory, results] = await Promise.all([api(base + '/requests'), api(base + '/surveys')]);
  const ruleRows = results.surveys.filter(survey => survey.status === 'ready').flatMap(survey => survey.pairs);
  const chosen = ruleRows.find(row => row.id === state.pair) ?? ruleRows[0];
  const details = chosen ? [chosen.id_a, chosen.id_b].map(id => inventory.stock.find(row => row.id === id)) : [];
  const narrowed = chosen ? inventory.requests.filter(row => row.phase === 'confirmed' &&
    details.every(stock => row.lines.some(line => stock.id === line.item_id))) : [];
  outlet.innerHTML = heading('整箱筹备', '按一个搭配各取一整箱，起草给单个安置点的配发单。草案提交后等待出库复核。', incident)
    + `<section class="packing-sheet"><div class="package-components">
       ${details.map(stock => `<article class="crate-label"><small>${h(stock.sku)}</small><h2>${h(stock.name)}</h2>
       <strong>${stock.case_size} 件 / 箱</strong><p>当前可配 ${stock.available_cases} 箱</p></article>`).join('')}
       ${details.length ? '' : empty('暂无搭配。先完成共需分析，再选择一组物资。')}
       </div><section class="paper-sheet"><h2>配发草案</h2>
       ${chosen ? `<label>成对搭配<select id="packing-pair">${ruleRows.map(row => `<option value="${row.id}" ${row.id === chosen.id ? 'selected' : ''}>
        ${h(row.name_a)} ＋ ${h(row.name_b)} / 第 ${row.survey_id} 次</option>`).join('')}</select></label>
       ${narrowed.length && user.role === 'operator' ? `<form id="draft-form">
        <label>对应已核单安置点<select name="request_id">${narrowed.map(row =>
          `<option value="${row.id}">${h(row.slip)} · ${h(row.shelter)} · ${row.households} 户</option>`).join('')}</select></label>
        <label>套数<input name="packs" type="number" value="1" min="1" max="200" required></label>
        <button type="submit">起草配发单</button></form>`
        : narrowed.length ? `<p>当前有 ${narrowed.length} 个已核单安置点同时申报了这两项。请由录入员起草。</p>`
        : empty('未有核定申报这两种物资的安置点。')}
        ` : ''}<p role="status" data-feedback></p></section></section>`;
  outlet.querySelector('#packing-pair')?.addEventListener('change', event => { state.pair = Number(event.target.value); redraw(); });
  action(outlet, '#draft-form', async form => {
    const draft = await api(base + '/issue-slips', 'POST', {
      pair_id:chosen.id, request_id:Number(form.get('request_id')), packs:Number(form.get('packs')),
    });
    state.slip = draft.id;
    location.hash = 'dispatch';
  }, () => {});
}

async function dispatchDesk(outlet, base, incident, user, redraw) {
  const {stock, slips} = await api(base + '/issue-slips');
  const selected = slips.find(row => row.id === state.slip) ?? slips[0];
  outlet.innerHTML = heading('出库复核', '同批草案可能争用库存。复核时重新核对尚未配发量和保留库存。', incident)
    + `<section class="warehouse"><h2>库存台账</h2><div class="depot-overflow"><table>
      <thead><tr><th>物资</th><th>库存件数</th><th>应急保留</th><th>可配整箱</th></tr></thead><tbody>
      ${stock.map(item => `<tr><th scope="row">${h(item.name)}</th><td>${item.on_hand}</td><td>${item.protected_units}</td><td>${item.available_cases}</td></tr>`).join('')}
      </tbody></table></div></section>
      <div class="intake-board signoff"><section class="paper-sheet"><h2>配发凭证</h2>
      ${slips.length ? `<ol class="depot-queue">${slips.map(row => `<li><button class="queue-button" type="button" data-select="${row.id}" aria-pressed="${selected.id === row.id}">
        <span>${h(row.slip)} / ${h(row.shelter)}</span>${badge(slipPhase[row.phase],row.phase)}</button></li>`).join('')}</ol>`
        : empty('先在整箱筹备中起草配发单。')}</section>
      <section class="paper-sheet"><h2>${selected ? h(selected.shelter) : '出库明细'}</h2>
      ${selected ? `<p>${selected.packs} 套 · ${h(selected.name_a)} ${selected.units_a} 件 · ${h(selected.name_b)} ${selected.units_b} 件</p>
        ${selected.phase === 'voided' ? `<p class="subdued">因需求更正停用：${h(selected.voided_reason)} · ${h(selected.voided_at)}</p>`
         : selected.phase !== 'draft' ? `<p>经办人 ${h(selected.disposition_by)} · ${h(selected.disposition_note)}</p>`
        : user.role !== 'viewer' ? `<form id="disposition">
          <label>复核或搁置说明<input name="note" minlength="4" required placeholder="按 16 户优先配发"></label><label>处理<select name="kind">
            ${user.role === 'reviewer' ? '<option value="approve">批准出库</option>' : ''}<option value="shelve">搁置草案</option>
          </select></label><button type="submit">提交出库处理</button></form>` : ''}
        ` : ''}<p role="status" data-feedback></p></section></div>`;
  selectRows(outlet, 'slip', redraw);
  action(outlet, '#disposition', form => api(base + '/issue-slips/' + selected.id + '/' + form.get('kind'),
    'POST', {note:form.get('note')}), redraw);
}

async function render(slug, outlet, user) {
  const [incident] = await api(responsePath);
  if (!incident) {
    outlet.innerHTML = empty('当前未登记雨洪响应。请联系库房值班员核查启动数据。');
    return;
  }
  const views = {requests:requestDesk, overlap:overlapView, packing:packingDesk, dispatch:dispatchDesk,
    lots:lotsPage, alternates:alternatesPage, arrivals:shelterArrival};
  const redraw = () => render(slug, outlet, user);
  await views[slug](outlet, responsePath + '/' + incident.id, incident, user, redraw,{heading,action});
}

mount({ title:'雨洪安置点', kicker:'清桥应急中转库', pages, render });
