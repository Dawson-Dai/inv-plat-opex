---
name: opex-confluence-publish
description: >
  Reads the latest data/YYYY-MM-DD/maturity.json from the inv-plat-opex repo and publishes
  the Inventory Platform Opex Report to Confluence with three sections: Tribe Overview,
  Priority Standards Compliance, and Squad Detail. Use when the user says "publish opex
  report", "publish maturity report to confluence", "update opex confluence page", or
  "publish the maturity gaps to confluence".
---

# Opex Confluence Publisher

## What this skill does

Reads a processed `maturity.json` snapshot and publishes a Confluence page with:

1. **Tribe Overview** — per-scorecard breakdown table (scorecard | squads affected | rule-instances | unique rules | entities)
2. **Priority Standards Compliance** — standards as rows, failing squads as bullet list with counts
3. **Squad Detail** — per-squad tables (scorecard | rule | failing entity count linked to Cortex)

## Repo location

`/Users/dawsondai/ai/inv-plat-opex`

## Confluence target

- **Space key:** `~dawsondai` (Dawson's personal space)
- **Page title format:** `Opex-Report-YYYY-MM-DD`
- **Cloud ID:** `skyscanner.atlassian.net`
- **Parent page ID:** `2047672627` (the "AI" page at https://skyscanner.atlassian.net/wiki/spaces/~dawsondai/pages/2047672627/AI)

The report is published here for review, then manually moved to the IP space.

## Step-by-step instructions

### Step 1 — Load the snapshot

```bash
python3 -c "
import json
from pathlib import Path
data_dir = Path('/Users/dawsondai/ai/inv-plat-opex/data')
index = json.loads((data_dir / 'index.json').read_text())
latest = index['snapshots'][-1]
snap = json.loads((data_dir / latest / 'maturity.json').read_text())
print('Date:', snap['date'])
print('Tribe totals:', snap['tribe_totals'])
print('Squads:', len(snap['squads']))
print('Priority rules:', [p['label'] for p in snap['priority_rules']])
"
```

Store the loaded `snap` dict in context for HTML generation.

### Step 2 — Build the page HTML

Build the full page body as Confluence storage-format HTML. Construct each section in Python/inline, then combine.

#### Section 0: Incident

This section goes **first** on the page, before Tribe Overview. It has two subsections, each backed by a live Jira JQL query via `mcp__plugin_atlassian_atlassian__searchJiraIssuesUsingJql`.

```html
<h2>Incident</h2>
```

**Subsection A — Outdated ILD Actions**

JQL (fetch up to 50 issues, fields: `issuetype,summary,assignee,priority,status`):

```
statusCategory != Done AND
project IN (AQUA, "Big Yus", "Dancing Penguins", FDA, "Fuel RaTS",
  Ganymede, Halo, Kylin, Libra, Orange, Orca, Silver, Tiger, Yellow) AND
labels = ILDAction AND
created <= -14d
ORDER BY created DESC
```

Call:
```
mcp__plugin_atlassian_atlassian__searchJiraIssuesUsingJql:
  cloudId: skyscanner.atlassian.net
  jql: <above>
  maxResults: 50
  fields: ["issuetype", "summary", "assignee", "priority", "status"]
```

Render the results as an HTML table:

```html
<h3>Outdated ILD Actions</h3>
```

If issues returned, render:
```html
<table data-layout="full-width">
<tr><th><strong>Type</strong></th><th><strong>Key</strong></th><th><strong>Summary</strong></th><th><strong>Assignee</strong></th><th><strong>Priority</strong></th><th><strong>Status</strong></th></tr>
<!-- one <tr> per issue -->
<tr>
  <td>{issuetype.name}</td>
  <td><a href="https://skyscanner.atlassian.net/browse/{key}">{key}</a></td>
  <td>{summary}</td>
  <td>{assignee.displayName or "Unassigned"}</td>
  <td>{priority.name}</td>
  <td>{status.name}</td>
</tr>
</table>
```

If no issues: `<p><em>No outdated ILD actions found.</em></p>`

Always append a fallback link (JQL URL-encoded):
```html
<p><a href="https://skyscanner.atlassian.net/issues/?jql={url_encoded_jql}">View Outdated ILD Actions in Jira</a></p>
```

Then add `<hr />` between the two subsections.

**Subsection B — Overdue ILD**

JQL:

```
project = "Incident Library" AND
text ~ "Inventory Platform" AND
statusCategory != Done AND
created >= -14d
ORDER BY created DESC
```

Call:
```
mcp__plugin_atlassian_atlassian__searchJiraIssuesUsingJql:
  cloudId: skyscanner.atlassian.net
  jql: <above>
  maxResults: 50
  fields: ["issuetype", "summary", "assignee", "priority", "status"]
```

Render identically to Subsection A, with heading and fallback link:

```html
<h3>Overdue ILD</h3>
<!-- table or "No issues found" -->
<p><a href="https://skyscanner.atlassian.net/issues/?jql={url_encoded_jql}">View Overdue ILD Issues in Jira</a></p>
```

#### Section 1: Tribe Overview

Load the previous snapshot too (`prev_snap`) for delta comparisons:

```python
prev_date = index['snapshots'][-2]
prev_snap = json.loads((data_dir / prev_date / 'maturity.json').read_text())
prev_sc_tribe = {sc['scorecard']: sc for sc in prev_snap['tribe_by_scorecard']}
prev_squad_totals = {sq['name']: sq for sq in prev_snap['squads']}
```

```html
<h2>Tribe Overview</h2>
<p><em>Date: {snap['date']} | Failing Rows: {delta(t['failing_rule_instances'], pt['failing_rule_instances'])} | Failing Rules: {delta(t['unique_rules'], pt['unique_rules'])} | Affected Entities: {delta(t['affected_entities'], pt['affected_entities'])} | Compared to: {prev_date}</em></p>
```

Where `t = snap['tribe_totals']` and `pt = prev_snap['tribe_totals']`.

**Sub-section: By Scorecard** — emit this heading then the scorecard table:

```html
<h3>By Scorecard</h3>
<table data-layout="full-width">
<tr><th><strong>Scorecard</strong></th><th><strong>Squads Affected</strong></th><th><strong>Failing Rows</strong></th><th><strong>Failing Rules</strong></th><th><strong>Affected Entities</strong></th></tr>
```

For each `sc` in `snap['tribe_by_scorecard']` (already sorted by `failing_rule_instances` desc):
- If `sc['all_squads']` is true: squads cell = `All squads`
- Otherwise: take `sc['squads_affected']` (sorted by `failing_rule_instances` desc), show top-5 names comma-separated + `(+N more)` if needed

Look up `psc = prev_sc_tribe.get(sc['scorecard'])` for the delta:

```html
<tr>
  <td>{sc['scorecard']}</td>
  <td>{squads_text}</td>
  <td>{delta(sc['failing_rule_instances'], psc['failing_rule_instances'] if psc else None)}</td>
  <td>{delta(sc['unique_rules'], psc['unique_rules'] if psc else None)}</td>
  <td>{delta(sc['affected_entities'], psc['affected_entities'] if psc else None)}</td>
</tr>
```

Close `</table>`.

**Sub-section: By Squad** — immediately after the scorecard table, emit this heading then the squad table:

```html
<h3>By Squad</h3>
<table data-layout="full-width">
<tr><th><strong>Squad</strong></th><th><strong>Failing Rows</strong></th><th><strong>Failing Rules</strong></th><th><strong>Affected Entities</strong></th></tr>
```

Look up `psq = prev_squad_totals.get(squad['name'])` for the delta. Note: `total_unique_rules` was not in snapshots before it was added to `build_json.py`, so use `psq.get('total_unique_rules')` which returns `None` if absent — `delta()` will then show the raw value with no comparison.

For each `squad` in `snap['squads']` sorted by `total_failing_rule_instances` desc:

```html
<tr>
  <td>{squad['name']}</td>
  <td>{delta(squad['total_failing_rule_instances'], psq['total_failing_rule_instances'] if psq else None)}</td>
  <td>{delta(squad['total_unique_rules'], psq.get('total_unique_rules') if psq else None)}</td>
  <td>{delta(squad['total_affected_entities'], psq['total_affected_entities'] if psq else None)}</td>
</tr>
```

Close `</table>`.

#### Section 2: Priority Standards Compliance

```html
<h2>Priority Standards Compliance</h2>
<table data-layout="full-width">
<tr><th><strong>Standard</strong></th><th><strong>Failing Squads</strong></th></tr>
```

For each `pr` in `snap['priority_rules']`:
- Collect failing squads: `[(squad, v['failing_entity_count']) for squad, v in pr['squad_compliance'].items() if v['failing_entity_count'] > 0]`, sorted by count desc
- If none: `<span style="color:#217a45;">✅ All squads compliant</span>`
- Otherwise: comma-separated inline, e.g. `Squad A (3), Squad B (2), Squad C (1)`
- For the Standard cell: if `pr` has an `id` field, render a hyperlink to the Cortex maturity filter; otherwise plain text:

```python
CORTEX_RULE_URL = "https://app.getcortexapp.com/admin/plugins/4033?engineeringExcellenceOverviewPluginRoute=%2Fmaturity%3Flv%3D0%26hp%3D1%26hh%3D1%26rl%3D{id}"

if pr.get("id"):
    standard_cell = f'<a href="{CORTEX_RULE_URL.format(id=pr["id"])}">{pr["label"]}</a>'
else:
    standard_cell = pr["label"]
```

```html
<tr>
  <td>{standard_cell}</td>
  <td>{failing_squads_html}</td>
</tr>
```

Close `</table>`.

#### Section 3: Squad Detail

```html
<h2>Squad Detail</h2>
```

**Show every squad** sorted by `total_failing_rule_instances` desc. Each squad gets one scorecard-level summary table (no rule-level rows).

**Delta helper** — build a lookup from the previous snapshot before rendering:

```python
prev_snap = json.loads((data_dir / prev_date / 'maturity.json').read_text())
# prev_date = second-to-last entry in index['snapshots']

def sc_agg(sc):
    rows = sum(r['failing_entity_count'] for r in sc['rules'])
    rules = len(sc['rules'])
    entities = len({e for r in sc['rules'] for e in r['entities']})
    return rows, rules, entities

prev_lookup = {}  # squad_name -> scorecard_name -> (rows, rules, entities)
for sq in prev_snap['squads']:
    prev_lookup[sq['name']] = {sc['name']: sc_agg(sc) for sc in sq['scorecards']}

def delta(curr, prev):
    """Return 'N (+D)', 'N (no change)', 'N (-D)', or just 'N' if no prev."""
    if prev is None:
        return str(curr)
    d = curr - prev
    if d == 0:
        return f'{curr} (no change)'
    sign = '+' if d > 0 else ''
    return f'{curr} ({sign}{d})'
```

For each `squad` in `snap['squads']` sorted by `total_failing_rule_instances` desc:

```html
<h3>{squad['name']}</h3>
<table data-layout="full-width">
<tr><th><strong>Scorecard</strong></th><th><strong>Failing Rows</strong></th><th><strong>Failing Rules</strong></th><th><strong>Affected Entities</strong></th></tr>
```

Sort `squad['scorecards']` by `sum(r['failing_entity_count'] for r in sc['rules'])` descending before iterating.

For each `sc` in the sorted scorecards:
- Compute `curr_rows, curr_rules, curr_entities = sc_agg(sc)`
- Look up `prev_sc = prev_lookup.get(squad['name'], {}).get(sc['name'])` — this is `(rows, rules, entities)` or `None`
- Scorecard name links to `squad['cortex_url']`

```html
<tr>
  <td><a href="{squad['cortex_url']}">{sc['name']}</a></td>
  <td>{delta(curr_rows, prev_sc[0] if prev_sc else None)}</td>
  <td>{delta(curr_rules, prev_sc[1] if prev_sc else None)}</td>
  <td>{delta(curr_entities, prev_sc[2] if prev_sc else None)}</td>
</tr>
```

Close `</table>` after each squad.

**New squads** (present in current snapshot but not in previous) have no prev data — `delta()` will just show the raw number with no comparison, which is correct.

### Step 3 — Find or create the Confluence page

Search for existing page:

```
mcp__plugin_atlassian_atlassian__searchConfluenceUsingCql:
  cloudId: skyscanner.atlassian.net
  cql: title = "Opex-Report-{date}" AND space = "~dawsondai" AND type = page
```

- **Found:** call `mcp__plugin_atlassian_atlassian__updateConfluencePage` with the found `pageId`, passing `body` (the HTML) and `contentFormat: "html"`, `title: "Opex-Report-{date}"`
- **Not found:** call `mcp__plugin_atlassian_atlassian__createConfluencePage`:
  - Get `spaceId` from `mcp__plugin_atlassian_atlassian__getConfluenceSpaces` filtering key `~dawsondai`
  - `parentId`: `2047672627` (hardcoded — the "AI" page in Dawson's personal space)
  - Pass `title`, `body`, `spaceId`, `parentId`, `contentFormat: "html"`

### Step 4 — Report back

Print:
- Confluence page URL (from the response)
- Date published
- Tribe totals (rule-instances, unique rules, entities, squads)

## Important rules

- Squad names in JSON use exact display names (e.g., `"Dancing Penguins"`) — use as-is
- Failing entity count links go to `squad['cortex_url']`
- Squads in Squad Detail sorted by `total_failing_rule_instances` descending
- Scorecard name shown bold only on first rule row for that scorecard; empty string for the rest
- Use `<br>` for line breaks inside `<td>`, not newlines
- `data-layout="full-width"` on all tables
