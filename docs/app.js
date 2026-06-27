const DATA_BASE = '../data';
const COLORS = ['#1F4E79','#2E75B6','#70AD47','#ED7D31','#FFC000','#FF0000','#7030A0','#00B0F0','#92D050','#FF7575'];
let snapshots = [];

async function init() {
  const index = await fetch(`${DATA_BASE}/index.json`).then(r => r.json());
  snapshots = await Promise.all(
    index.snapshots.map(async d => ({ date: d, data: await fetch(`${DATA_BASE}/${d}/maturity.json`).then(r => r.json()) }))
  );
  if (!snapshots.length) { document.getElementById('loading').textContent = 'No snapshots found.'; return; }
  document.getElementById('loading').style.display = 'none';
  document.getElementById('app').style.display = 'block';
  renderTrend(); renderCompliance(); renderExplorer();
  document.querySelectorAll('nav button').forEach(btn =>
    btn.addEventListener('click', () => {
      document.querySelectorAll('nav button, .tab').forEach(el => el.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById(btn.dataset.tab).classList.add('active');
    })
  );
}

function renderTrend() {
  const dates = snapshots.map(s => s.date);
  const scNames = [...new Set(snapshots.flatMap(s => s.data.tribe_by_scorecard.map(sc => sc.scorecard)))].sort();
  const ctx = document.getElementById('trendChart').getContext('2d');
  new Chart(ctx, {
    type: 'line',
    data: {
      labels: dates,
      datasets: scNames.map((sc, i) => ({
        label: sc,
        data: snapshots.map(s => (s.data.tribe_by_scorecard.find(x => x.scorecard === sc) || {}).failing_rule_instances ?? null),
        borderColor: COLORS[i % COLORS.length],
        tension: 0.3, fill: false
      }))
    },
    options: { responsive: true, plugins: { legend: { position: 'bottom' } },
      scales: { y: { beginAtZero: true, title: { display: true, text: 'Failing rule-instances' } } } }
  });
  const tbl = document.getElementById('totalsTrendTable');
  const hdr = tbl.insertRow();
  ['Date','Rule-instances','Unique Rules','Entities','Squads'].forEach(h => { const th = document.createElement('th'); th.textContent = h; hdr.appendChild(th); });
  snapshots.slice().reverse().forEach(s => {
    const t = s.data.tribe_totals, row = tbl.insertRow();
    [s.date, t.failing_rule_instances, t.unique_rules, t.affected_entities, s.data.squads.length].forEach(v => { row.insertCell().textContent = v; });
  });
}

function renderCompliance() {
  const latest = snapshots[snapshots.length - 1];
  document.getElementById('complianceDate').textContent = `Latest snapshot: ${latest.date}`;
  const tbl = document.getElementById('complianceTable');
  const hdr = tbl.insertRow();
  ['Standard','Failing Squads'].forEach(h => { const th = document.createElement('th'); th.textContent = h; hdr.appendChild(th); });
  latest.data.priority_rules.forEach(pr => {
    const row = tbl.insertRow();
    row.insertCell().textContent = pr.label || pr.rule;
    const td = row.insertCell();
    const failing = Object.entries(pr.squad_compliance).filter(([,v]) => v.failing_entity_count > 0).sort((a,b) => b[1].failing_entity_count - a[1].failing_entity_count);
    if (!failing.length) { td.innerHTML = '<span class="pass">✅ All squads compliant</span>'; return; }
    const ul = document.createElement('ul'); ul.className = 'squad-list';
    failing.forEach(([sq, v]) => { const li = document.createElement('li'); li.className = 'fail'; li.textContent = `• ${sq} (${v.failing_entity_count})`; ul.appendChild(li); });
    td.appendChild(ul);
  });
}

function renderExplorer() {
  const sel = document.getElementById('snapshotSelect');
  snapshots.slice().reverse().forEach(s => { const o = document.createElement('option'); o.value = s.date; o.textContent = s.date; sel.appendChild(o); });
  sel.addEventListener('change', () => renderSnapshot(sel.value));
  renderSnapshot(sel.value);
}

function renderSnapshot(date) {
  const container = document.getElementById('snapshotContent');
  container.innerHTML = '';
  const snap = snapshots.find(s => s.date === date);
  if (!snap) return;
  const d = snap.data;
  const h2 = document.createElement('h2'); h2.textContent = `Tribe Overview — ${date}`; container.appendChild(h2);
  const tbl = document.createElement('table'); container.appendChild(tbl);
  const hdr = tbl.insertRow();
  ['Scorecard','Squads Affected','Rule-instances','Unique Rules','Entities'].forEach(h => { const th = document.createElement('th'); th.textContent = h; hdr.appendChild(th); });
  d.tribe_by_scorecard.forEach(sc => {
    const row = tbl.insertRow();
    row.insertCell().textContent = sc.scorecard;
    const sqCell = row.insertCell();
    if (sc.all_squads) { sqCell.textContent = 'All squads'; }
    else { const top5 = sc.squads_affected.slice(0,5).map(s=>s.name).join(', '); sqCell.textContent = top5 + (sc.squads_affected.length > 5 ? ` (+${sc.squads_affected.length-5} more)` : ''); }
    row.insertCell().textContent = sc.failing_rule_instances;
    row.insertCell().textContent = sc.unique_rules;
    row.insertCell().textContent = sc.affected_entities;
  });
  const h2sq = document.createElement('h2'); h2sq.textContent = 'Squad Detail'; h2sq.style.marginTop = '28px'; container.appendChild(h2sq);
  d.squads.slice().sort((a, b) => b.total_failing_rule_instances - a.total_failing_rule_instances).forEach(squad => {
    const sec = document.createElement('div'); sec.className = 'squad-section'; container.appendChild(sec);
    const h3 = document.createElement('h3');
    const a = document.createElement('a');
    a.href = squad.cortex_url;
    a.target = '_blank';
    a.textContent = squad.name;
    h3.appendChild(a);
    h3.appendChild(document.createTextNode(` — ${squad.total_failing_rule_instances} rule-instances, ${squad.total_affected_entities} entities`));
    sec.appendChild(h3);
    const t2 = document.createElement('table'); sec.appendChild(t2);
    const hdr2 = t2.insertRow();
    ['Scorecard','Rule','Failing Entities'].forEach(h => { const th = document.createElement('th'); th.textContent = h; hdr2.appendChild(th); });
    squad.scorecards.forEach(sc => sc.rules.forEach((rule, ri) => {
      const row = t2.insertRow();
      const scCell = row.insertCell(); if (ri === 0) { scCell.textContent = sc.name; scCell.style.fontWeight = '600'; }
      row.insertCell().textContent = rule.rule;
      const cnt = row.insertCell(); const a = document.createElement('a'); a.href = squad.cortex_url; a.target = '_blank'; a.textContent = rule.failing_entity_count; cnt.appendChild(a);
    }));
  });
}

document.addEventListener('DOMContentLoaded', init);
