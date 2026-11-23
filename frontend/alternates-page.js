import {api,h} from '/base.js';
import {itemOffer,matchedRuleOptions} from './consent-ticket.js';

export async function alternatesPage(outlet,base,incident,user,redraw,ui) {
  const [offers,surveys,requests]=await Promise.all([api(base+'/alternates'),api(base+'/surveys'),api(base+'/requests')]);
  const rules=surveys.surveys.filter(r=>r.status==='ready').flatMap(r=>r.pairs);
  const pending=offers.filter(row=>!row.linked_slip && !row.revoked_reason);
  outlet.innerHTML=ui.heading('备选换品','从相同共需场次选择另一个搭配。只调换一个同箱规物资，保留原需求抵扣。',incident)
    +`<div class="alternate-desk"><section class="paper-sheet"><h2>替换确认簿</h2>
    ${offers.length ? offers.map(itemOffer).join('') : '<p>旧值班记录暂无换品。调拨前先核对配发意向和安置点回执。</p>'}</section>
    <aside class="paper-sheet"><h2>换品与安置点同意</h2>
    ${user.role==='operator' && rules.length>=2 ? `<form id="alternative-kit"><label>安置点需求<select name="request_id">
      ${requests.requests.filter(row=>row.phase==='confirmed').map(row=>`<option value="${row.id}">${h(row.slip)} · ${h(row.shelter)}</option>`).join('')}</select></label>
      <label>原定套餐<select name="wanted_pair">${matchedRuleOptions(rules)}</select></label>
      <label>同场次替代套餐<select name="alternate_pair">${matchedRuleOptions(rules)}</select></label>
      <label>按同箱规替换套数<input name="packs" type="number" min="1" max="200" required></label>
      <label>现场换品依据<input name="explanation" minlength="4" required></label><button type="submit">发起换品沟通</button></form>` :
     user.role==='reviewer' && pending.length ? `<form id="kit-consent"><label>换品沟通<select name="offer">
        ${pending.map(row=>`<option value="${row.id}">${h(row.shelter)} · ${h(row.replacement_name)}</option>`).join('')}</select></label>
        <label>现场同意凭证<input name="consent_ref" minlength="4" required></label>
        <button type="submit">登记同意并形成草案</button></form>` : '<p>需同场次两个共需搭配及一个可等量替换的物资。</p>'}
    <p role="status" data-feedback></p></aside></div>`;
  ui.action(outlet,'#alternative-kit',form=>{
    const data=Object.fromEntries(form);
    for(const key of ['request_id','wanted_pair','alternate_pair','packs']) data[key]=Number(data[key]);
    return api(base+'/alternates','POST',data);
  },redraw);
  ui.action(outlet,'#kit-consent',form=>api(base+'/alternates/'+form.get('offer')+'/consent','POST',{consent_ref:form.get('consent_ref')}),redraw);
}
