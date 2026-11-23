import {h} from '/base.js';

export function manifestTable(rows) {
  return `<table class="lot-table"><thead><tr><th>配发单</th><th>批号</th><th>到点</th><th>保质日</th><th>件数</th></tr></thead>
  <tbody>${rows.map(row=>`<tr><td>#${row.slip_id}</td><td>${h(row.label)}</td><td>${h(row.arrival_day)}</td>
   <td>${h(row.use_by)}</td><td>${row.units}</td></tr>`).join('')}</tbody></table>`;
}

export function stockTickets(rows) {
  return `<ul class="lot-cards">${rows.map(row=>`<li><strong>${h(row.label)}</strong><span>${h(row.name)} · ${h(row.use_by)} 前有效</span>
   <span>余 ${row.balance} 件</span></li>`).join('')}</ul>`;
}
