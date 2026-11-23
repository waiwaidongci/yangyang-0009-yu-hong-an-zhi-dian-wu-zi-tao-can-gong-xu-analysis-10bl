import {api,h} from '/base.js';
import {arrivalCard} from './site-count-slip.js';

export async function shelterArrival(outlet,base,incident,user,redraw,ui) {
  const rows=await api(base+'/handovers');
  const list=rows.filter(row=>user.role==='operator' ? !row.receipt : row.receipt && !row.receipt.disposition);
  outlet.innerHTML=ui.heading('到点点收','逐单核对出库与现场实点箱件的差异。缺件保留运输损失或待转运记载。',incident)
    +`<div class="arrival-layout"><section class="paper-sheet"><h2>交接回执</h2>
    ${rows.length ? rows.map(arrivalCard).join('') : '<p>批准出库后，箱件在此登记现场签收与短少原因。</p>'}</section>
    <aside class="paper-sheet"><h2>现场实点与签核</h2>${list.length && user.role!=='viewer' ? `<form id="site-sign">
    <label>配发凭证<select name="slip">${list.map(row=>`<option value="${row.slip.id}">#${row.slip.id} · ${h(row.slip.shelter)} · ${h(row.slip.name_a)} + ${h(row.slip.name_b)}</option>`).join('')}</select></label>
    ${user.role==='operator' ? `<div class="depot-two"><label>第一项实点<input type="number" name="counted_a" min="0" required></label>
    <label>第二项实点<input type="number" name="counted_b" min="0" required></label></div>
    <label>回执凭证<input name="proof_ref" minlength="4" required></label>` :
    `<label>处置<select name="disposition"><option value="verified">全量签收</option><option value="record_loss">登记短少损失</option><option value="relay_pending">另立转运联络</option></select></label>
    <label>现场核对说明<input name="note" minlength="4" required></label>`}
    <button type="submit">提交到点记录</button></form>` : '<p>暂无需要当前角色处理的到点记录。</p>'}
    <p role="status" data-feedback></p></aside></div>`;
  ui.action(outlet,'#site-sign',form=>{
    const {slip,...data}=Object.fromEntries(form);
    if (user.role==='operator') {
      data.counted_a=Number(data.counted_a);
      data.counted_b=Number(data.counted_b);
    }
    return api(base+'/handovers/'+slip+(user.role==='reviewer'?'/verify':''),'POST',data);
  },redraw);
}
