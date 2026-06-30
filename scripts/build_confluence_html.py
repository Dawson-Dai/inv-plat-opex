"""
Build the full Confluence page HTML for the Opex Report.
Outputs the HTML to stdout.
"""
import json
import re
from pathlib import Path
from urllib.parse import quote

REPO = Path("/Users/dawsondai/ai/inv-plat-opex")
DATA = REPO / "data"

# ── Load data ────────────────────────────────────────────────────────────────
index = json.loads((DATA / "index.json").read_text())
date = index["snapshots"][-1]
prev_date = index["snapshots"][-2]
snap = json.loads((DATA / date / "maturity.json").read_text())
prev_snap = json.loads((DATA / prev_date / "maturity.json").read_text())
cz_path = DATA / date / "cloudzero.json"
cz = json.loads(cz_path.read_text()) if cz_path.exists() else None

# ── Helpers ──────────────────────────────────────────────────────────────────
def delta(curr, prev):
    if prev is None:
        return str(curr)
    d = curr - prev
    if d == 0:
        return f"{curr} (no change)"
    sign = "+" if d > 0 else ""
    return f"{curr} ({sign}{d})"

def cost_bullet(recent, abs_change, pct_change):
    sign = "+" if abs_change >= 0 else "-"
    return f"${recent:,.0f} ({sign}${abs(abs_change):,.0f} / {sign}{abs(pct_change):.1f}%)"

def sc_agg(sc):
    rows = sum(r["failing_entity_count"] for r in sc["rules"])
    rules = len(sc["rules"])
    entities = len({e for r in sc["rules"] for e in r["entities"]})
    return rows, rules, entities

# ── Section 0: Incident ──────────────────────────────────────────────────────
ild_jql = ('statusCategory != Done AND '
           'project IN (AQUA, "Big Yus", "Dancing Penguins", FDA, "Fuel RaTS", '
           'Ganymede, Halo, Kylin, Libra, Orange, Orca, Silver, Tiger, Yellow) AND '
           'labels = ILDAction AND created <= -14d ORDER BY created DESC')
overdue_jql = ('project = "Incident Library" AND text ~ "Inventory Platform" AND '
               'statusCategory != Done AND created >= -14d ORDER BY created DESC')

# ILD Actions results (injected via CLI arg)
import sys
ild_issues_json = sys.argv[1]
overdue_issues_json = sys.argv[2]
ild_issues = json.loads(ild_issues_json)
overdue_issues = json.loads(overdue_issues_json)
# Read workstreams body from a file to avoid shell escaping artifacts
workstreams_body = Path(sys.argv[3]).read_text(encoding="utf-8") if len(sys.argv) > 3 else ""

def render_jira_table(issues):
    if not issues:
        return "<p><em>No issues found.</em></p>"
    rows = ""
    for i in issues:
        f = i["fields"]
        assignee = f.get("assignee") or {}
        rows += (
            f'<tr>'
            f'<td>{f["issuetype"]["name"]}</td>'
            f'<td><a href="https://skyscanner.atlassian.net/browse/{i["key"]}">{i["key"]}</a></td>'
            f'<td>{f["summary"]}</td>'
            f'<td>{assignee.get("displayName", "Unassigned")}</td>'
            f'<td>{f["priority"]["name"]}</td>'
            f'<td>{f["status"]["name"]}</td>'
            f'</tr>'
        )
    return (
        '<table data-layout="full-width">'
        '<tr><th><strong>Type</strong></th><th><strong>Key</strong></th>'
        '<th><strong>Summary</strong></th><th><strong>Assignee</strong></th>'
        '<th><strong>Priority</strong></th><th><strong>Status</strong></th></tr>'
        + rows + '</table>'
    )

incident_html = (
    '<h2>Incident</h2>'
    '<h3>Outdated ILD Actions</h3>'
    + render_jira_table(ild_issues)
    + f'<p><a href="https://skyscanner.atlassian.net/issues/?jql={quote(ild_jql)}">View Outdated ILD Actions in Jira</a></p>'
    '<hr />'
    '<h3>Overdue ILD</h3>'
    + render_jira_table(overdue_issues)
    + f'<p><a href="https://skyscanner.atlassian.net/issues/?jql={quote(overdue_jql)}">View Overdue ILD Issues in Jira</a></p>'
)

# ── Section 0b: CloudZero ────────────────────────────────────────────────────
if cz:
    t = cz["tribe_total"]
    period = cz["period"]
    tribe_item = f'<li><strong>Tribe total:</strong> {cost_bullet(t["recent"], t["abs_change"], t["pct_change"])}</li>'
    provider_items = "".join(
        f'<li>{p["name"]}: {cost_bullet(p["recent"], p["abs_change"], p["pct_change"])}</li>'
        for p in cz["providers"]
    )
    summary_html = f'<ul>{tribe_item}<ul>{provider_items}</ul></ul>'

    thresholds_html = (
        '<details><summary>Cost Alert Thresholds (Tier-Based)</summary>'
        '<table data-layout="full-width">'
        '<tr><th><strong>Tier</strong></th><th><strong>Squad 14d Spend</strong></th>'
        '<th><strong>Abs Change Threshold</strong></th><th><strong>% Change Threshold</strong></th></tr>'
        '<tr><td>1</td><td>&lt; $5,000</td><td>$500</td><td>20%</td></tr>'
        '<tr><td>2</td><td>$5,000 – $19,999</td><td>$1,000</td><td>15%</td></tr>'
        '<tr><td>3</td><td>$20,000 – $49,999</td><td>$3,000</td><td>10%</td></tr>'
        '<tr><td>4</td><td>&#8805; $50,000</td><td>$5,000</td><td>10%</td></tr>'
        '</table>'
        '<p><em>A squad is flagged if |abs change| &gt; threshold OR |% change| &gt; threshold.</em></p>'
        '</details>'
    )

    provider_groups = {}
    for p in cz["providers"]:
        rows = [s for s in sorted(p["squads"], key=lambda x: -abs(x["abs_change"]))
                if s["anomaly"] and s["name"] and not s["name"].startswith("Service Category")]
        if rows:
            provider_groups[p["name"]] = rows

    if provider_groups:
        anomaly_rows = ""
        for provider_name, squads in provider_groups.items():
            for i, s in enumerate(squads):
                s_sign = "+" if s["abs_change"] >= 0 else "-"
                cost_cell = f'${s["recent"]:,.0f}'
                change_cell = f'{s_sign}${abs(s["abs_change"]):,.0f} ({s_sign}{abs(s["pct_change"]):.1f}%)'
                provider_cell = f'<td rowspan="{len(squads)}">{provider_name}</td>' if i == 0 else ""
                anomaly_rows += f'<tr>{provider_cell}<td>{s["name"]}</td><td>{cost_cell}</td><td>{change_cell}</td></tr>'
        anomaly_html = (
            '<table data-layout="full-width">'
            '<tr><th><strong>Provider</strong></th><th><strong>Squad</strong></th>'
            '<th><strong>14d Cost</strong></th><th><strong>Change</strong></th></tr>'
            + anomaly_rows + '</table>'
        )
    else:
        anomaly_html = '<p><span style="color:#217a45;">&#x2705; No anomalous cost changes detected.</span></p>'

    cz_html = (
        '<h2>CloudZero Cost Insights</h2>'
        f'<p><em>Period: {period["start"]} to {period["end"]} ({period["lookback_days"]}-day comparison) | Fetched: {cz["fetched_at"][:10]}</em></p>'
        + summary_html + thresholds_html + anomaly_html
    )
else:
    cz_html = (
        '<h2>CloudZero Cost Insights</h2>'
        f'<div data-type="panel-warning"><p>&#x26A0;&#xFE0F; Cost data unavailable for {snap["date"]}. '
        'Run the <strong>opex-fetch-cloudzero</strong> skill to populate this section, then republish.</p></div>'
    )

# ── Section 1: Tribe Overview ────────────────────────────────────────────────
t = snap["tribe_totals"]
pt = prev_snap["tribe_totals"]
prev_sc_tribe = {sc["scorecard"]: sc for sc in prev_snap["tribe_by_scorecard"]}
prev_squad_totals = {sq["name"]: sq for sq in prev_snap["squads"]}

tribe_html = (
    '<h2>Tribe Overview</h2>'
    f'<p><em>Date: {snap["date"]} | Failing Rows: {delta(t["failing_rule_instances"], pt["failing_rule_instances"])} | '
    f'Failing Rules: {delta(t["unique_rules"], pt["unique_rules"])} | '
    f'Affected Entities: {delta(t["affected_entities"], pt["affected_entities"])} | '
    f'Compared to: {prev_date}</em></p>'
    '<h3>By Scorecard</h3>'
    '<table data-layout="full-width">'
    '<tr><th><strong>Scorecard</strong></th><th><strong>Squads Affected</strong></th>'
    '<th><strong>Failing Rows</strong></th><th><strong>Failing Rules</strong></th>'
    '<th><strong>Affected Entities</strong></th></tr>'
)
for sc in snap["tribe_by_scorecard"]:
    if sc.get("all_squads"):
        squads_text = "All squads"
    else:
        names = [s["name"] for s in sc["squads_affected"]]
        squads_text = ", ".join(names[:5])
        if len(names) > 5:
            squads_text += f" (+{len(names)-5} more)"
    psc = prev_sc_tribe.get(sc["scorecard"])
    tribe_html += (
        f'<tr><td>{sc["scorecard"]}</td><td>{squads_text}</td>'
        f'<td>{delta(sc["failing_rule_instances"], psc["failing_rule_instances"] if psc else None)}</td>'
        f'<td>{delta(sc["unique_rules"], psc["unique_rules"] if psc else None)}</td>'
        f'<td>{delta(sc["affected_entities"], psc["affected_entities"] if psc else None)}</td></tr>'
    )
tribe_html += '</table>'

# By Squad sub-section
tribe_html += (
    '<h3>By Squad</h3>'
    '<table data-layout="full-width">'
    '<tr><th><strong>Squad</strong></th><th><strong>Failing Rows</strong></th>'
    '<th><strong>Failing Rules</strong></th><th><strong>Affected Entities</strong></th></tr>'
)
for squad in sorted(snap["squads"], key=lambda s: -s["total_failing_rule_instances"]):
    psq = prev_squad_totals.get(squad["name"])
    tribe_html += (
        f'<tr><td>{squad["name"]}</td>'
        f'<td>{delta(squad["total_failing_rule_instances"], psq["total_failing_rule_instances"] if psq else None)}</td>'
        f'<td>{delta(squad["total_unique_rules"], psq.get("total_unique_rules") if psq else None)}</td>'
        f'<td>{delta(squad["total_affected_entities"], psq["total_affected_entities"] if psq else None)}</td></tr>'
    )
tribe_html += '</table>'

# ── Section 2: Priority Standards ───────────────────────────────────────────
CORTEX_RULE_URL = "https://app.getcortexapp.com/admin/plugins/4033?engineeringExcellenceOverviewPluginRoute=%2Fmaturity%3Flv%3D0%26hp%3D1%26hh%3D1%26rl%3D{id}"

priority_html = (
    '<h2>Priority Standards Compliance</h2>'
    '<table data-layout="full-width">'
    '<tr><th><strong>Standard</strong></th><th><strong>Failing Squads</strong></th></tr>'
)
for pr in snap["priority_rules"]:
    failing = [(sq, v["failing_entity_count"]) for sq, v in pr["squad_compliance"].items() if v["failing_entity_count"] > 0]
    failing.sort(key=lambda x: -x[1])
    if failing:
        squads_text = ", ".join(f"{sq} ({cnt})" for sq, cnt in failing)
    else:
        squads_text = '<span style="color:#217a45;">&#x2705; All squads compliant</span>'
    if pr.get("id"):
        standard_cell = f'<a href="{CORTEX_RULE_URL.format(id=pr["id"])}">{pr["label"]}</a>'
    else:
        standard_cell = pr["label"]
    priority_html += f'<tr><td>{standard_cell}</td><td>{squads_text}</td></tr>'
priority_html += '</table>'

# ── Section 3: Squad Detail ──────────────────────────────────────────────────
prev_lookup = {}
for sq in prev_snap["squads"]:
    prev_lookup[sq["name"]] = {sc["name"]: sc_agg(sc) for sc in sq["scorecards"]}

squad_html = '<h2>Squad Detail</h2>'
for squad in sorted(snap["squads"], key=lambda s: -s["total_failing_rule_instances"]):
    squad_html += (
        f'<h3>{squad["name"]}</h3>'
        '<table data-layout="full-width">'
        '<tr><th><strong>Scorecard</strong></th><th><strong>Failing Rows</strong></th>'
        '<th><strong>Failing Rules</strong></th><th><strong>Affected Entities</strong></th></tr>'
    )
    sorted_scs = sorted(squad["scorecards"], key=lambda sc: -sum(r["failing_entity_count"] for r in sc["rules"]))
    for sc in sorted_scs:
        curr_rows, curr_rules, curr_entities = sc_agg(sc)
        prev_sc = prev_lookup.get(squad["name"], {}).get(sc["name"])
        squad_html += (
            f'<tr>'
            f'<td><a href="{squad["cortex_url"]}">{sc["name"]}</a></td>'
            f'<td>{delta(curr_rows, prev_sc[0] if prev_sc else None)}</td>'
            f'<td>{delta(curr_rules, prev_sc[1] if prev_sc else None)}</td>'
            f'<td>{delta(curr_entities, prev_sc[2] if prev_sc else None)}</td>'
            f'</tr>'
        )
    squad_html += '</table>'

# ── Section 4: Workstreams ───────────────────────────────────────────────────
match = re.search(
    r'data-extension-key="excerpt"[^>]*workstreams-2026[^>]*>(.*?)</div>',
    workstreams_body, re.DOTALL
)
if match:
    inner = match.group(1)
    table_match = re.search(r'(<table.*?</table>)', inner, re.DOTALL)
    table_html = table_match.group(1) if table_match else inner
    table_html = re.sub(r' data-local-id="[^"]*"', '', table_html)
    workstreams_html = (
        '<h2>Workstreams</h2>'
        + table_html
        + '<p><em>Source: <a href="https://skyscanner.atlassian.net/wiki/spaces/IP/pages/2018508986/Opex+Governance+-+2026">Opex Governance - 2026</a></em></p>'
    )
else:
    workstreams_html = (
        '<h2>Workstreams</h2>'
        '<div data-type="panel-warning"><p>Workstreams content unavailable. See '
        '<a href="https://skyscanner.atlassian.net/wiki/spaces/IP/pages/2018508986/Opex+Governance+-+2026">'
        'Opex Governance - 2026</a>.</p></div>'
    )

# ── Combine ──────────────────────────────────────────────────────────────────
full_html = incident_html + cz_html + tribe_html + priority_html + squad_html + workstreams_html
print(full_html)
