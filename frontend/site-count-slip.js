import {h} from '/base.js';

const resolution={verified:'全量签核',record_loss:'留存损失',relay_pending:'待转运核对'};
export function arrivalCard({slip,receipt}) {
  return `<article class="arrival-card"><h3>${h(slip.shelter)} · 出库 #${slip.id}</h3>
    <dl><dt>箱单数量</dt><dd>${h(slip.name_a)} ${slip.units_a}件 + ${h(slip.name_b)} ${slip.units_b}件</dd>
      ${receipt ? `<dt>实点数量</dt><dd>${receipt.counted_a}件 + ${receipt.counted_b}件</dd>
      <dt>差异</dt><dd>${receipt.gap_a}件 + ${receipt.gap_b}件</dd><dt>现场凭证</dt><dd>${h(receipt.proof_ref)}</dd>`:''}</dl>
    <p>${receipt ? receipt.disposition ? h(resolution[receipt.disposition])+' · '+h(receipt.reviewer_note) : '待点收复核' : '等待现场签收'}</p></article>`;
}
