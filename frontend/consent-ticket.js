import {h} from '/base.js';

export function itemOffer(row) {
  return `<article class="consent-ticket"><h3>${h(row.shelter)} · ${h(row.slip)}</h3>
    <p><span>${h(row.donor_name)}</span>→<strong>${h(row.replacement_name)}</strong> · ${row.packs} 套</p>
    <small>${h(row.explanation)}</small><footer>${row.linked_slip ? '草案 #' + row.linked_slip + ' / '+h(row.consent_ref) : '等待安置点同意'}</footer>
  </article>`;
}
export function matchedRuleOptions(rules) {
  return rules.map(rule=>`<option value="${rule.id}">#${rule.survey_id} · ${h(rule.name_a)} + ${h(rule.name_b)}</option>`).join('');
}
