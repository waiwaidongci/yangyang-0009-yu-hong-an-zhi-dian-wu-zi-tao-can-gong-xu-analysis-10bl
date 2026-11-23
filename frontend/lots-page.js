import {api,h} from '/base.js';
import {manifestTable,stockTickets} from './lot-slip.js';

export async function lotsPage(outlet,base,incident,user,redraw,ui) {
  const [lots,book]=await Promise.all([api(base+'/lots'),api(base+'/issue-slips')]);
  const drafts=book.slips.filter(row=>row.phase==='draft');
  outlet.innerHTML=ui.heading('批次拣配','按有效期最早的可用批次拣配，到点过期的批号留仓停发。',incident)
    +`<div class="lot-layout"><section class="paper-sheet"><h2>到货批号</h2>
    ${lots.lots.length ? stockTickets(lots.lots) : '<p>老库仅登记散存。新到货可以录入独立批号，按到点日拣配。</p>'}
    <h3>已审看拣配单</h3><div class="depot-overflow">${lots.manifests.length ? manifestTable(lots.manifests) : '<p>暂无箱件批号单。</p>'}</div>
    </section><aside class="paper-sheet"><h2>批次作业</h2>${user.role==='operator'? `<form id="add-lot">
    <label>到货物资<select name="item_id">${book.stock.map(row=>`<option value="${row.id}">${h(row.name)}</option>`).join('')}</select></label>
    <label>批号<input name="label" required></label>
    <div class="depot-two"><label>保质日<input type="date" name="use_by" required></label>
      <label>实收件数<input type="number" name="units" min="1" max="3600" required></label></div>
    <button type="submit">登记实物批次</button></form>
    ${drafts.length ? `<form id="pick-lot"><label>配发草案<select name="slip">${drafts.map(row=>`<option value="${row.id}">${h(row.slip)} · ${h(row.shelter)} / #${row.id}</option>`).join('')}</select></label>
    <label>到点日<input type="date" name="arrival_day" required></label><button type="submit">拣出优先有效批号</button></form>` : ''}`:
    '<p>录入员维护实收批号与到点拣配，审批时以实际批号余额复核。</p>'}<p role="status" data-feedback></p></aside></div>`;
  ui.action(outlet,'#add-lot',form=>{
    const body=Object.fromEntries(form);
    return api(base+'/lots','POST',{...body,item_id:Number(body.item_id),units:Number(body.units)});
  },redraw);
  ui.action(outlet,'#pick-lot',form=>api(base+'/lots/manifest/'+form.get('slip'),'POST',{arrival_day:form.get('arrival_day')}),redraw);
}
