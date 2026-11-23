import {h} from '/base.js';

export function itemOffer(row) {
  const state=row.revoked_reason ? `<span class="status-chip voided">已停用</span> · ${h(row.revoked_reason)}`
    : row.linked_slip ? '草案 #' + row.linked_slip + ' / '+h(row.consent_ref) : '等待安置点同意';
  return `<article class="consent-ticket${row.revoked_reason ? ' stale' : ''}"><h3>${h(row.shelter)} · ${h(row.slip)}</h3>
    <p><span>${h(row.donor_name)}</span>→<strong>${h(row.replacement_name)}</strong> · ${row.packs} 套</p>
    <small>${h(row.explanation)}</small><footer>${state}</footer>
  </article>`;
}
export function matchedRuleOptions(rules) {
  return rules.map(rule=>`<option value="${rule.id}">#${rule.survey_id} · ${h(rule.name_a)} + ${h(rule.name_b)}</option>`).join('');
}
