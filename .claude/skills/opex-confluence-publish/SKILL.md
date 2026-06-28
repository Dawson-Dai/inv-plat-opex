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

#### Section 1: Tribe Overview

```html
<h2>Tribe Overview</h2>
<p><em>Date: {snap['date']} | Failing Rows: {snap['tribe_totals']['failing_rule_instances']} | Failing Rules: {snap['tribe_totals']['unique_rules']} | Affected Entities: {snap['tribe_totals']['affected_entities']}</em></p>
```

**Sub-section: By Scorecard** — emit this heading then the scorecard table:

```html
<h3>By Scorecard</h3>
<table data-layout="full-width">
<tr><th><strong>Scorecard</strong></th><th><strong>Squads Affected</strong></th><th><strong>Failing Rows</strong></th><th><strong>Failing Rules</strong></th><th><strong>Affected Entities</strong></th></tr>
```

For each `sc` in `snap['tribe_by_scorecard']` (already sorted by `failing_rule_instances` desc):
- If `sc['all_squads']` is true: squads cell = `All squads`
- Otherwise: take `sc['squads_affected']` (sorted by `failing_rule_instances` desc), show top-5 names comma-separated + `(+N more)` if needed

```html
<tr>
  <td>{sc['scorecard']}</td>
  <td>{squads_text}</td>
  <td>{sc['failing_rule_instances']}</td>
  <td>{sc['unique_rules']}</td>
  <td>{sc['affected_entities']}</td>
</tr>
```

Close `</table>`.

**Sub-section: By Squad** — immediately after the scorecard table, emit this heading then the squad table:

```html
<h3>By Squad</h3>
<table data-layout="full-width">
<tr><th><strong>Squad</strong></th><th><strong>Failing Rows</strong></th><th><strong>Failing Rules</strong></th><th><strong>Affected Entities</strong></th></tr>
```

For each `squad` in `snap['squads']` sorted by `total_failing_rule_instances` desc:

```html
<tr>
  <td>{squad['name']}</td>
  <td>{squad['total_failing_rule_instances']}</td>
  <td>{squad['total_unique_rules']}</td>
  <td>{squad['total_affected_entities']}</td>
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
- Otherwise: `• Squad Name (N)<br>• Squad Name (N)<br>…`

```html
<tr>
  <td>{pr['label']}</td>
  <td>{failing_squads_html}</td>
</tr>
```

Close `</table>`.

#### Section 3: Squad Detail

```html
<h2>Squad Detail</h2>
```

**Show top 5 squads only** (full breakdown is on the GitHub Pages site). Add this note after the `<h2>Squad Detail</h2>` heading:
```html
<p><em>Top 5 squads by failing rule-instances (top 10 rules each). <a href="https://dawson-dai.github.io/inv-plat-opex/">Full breakdown on the live site.</a></em></p>
```

For each `squad` in the top 5 of `snap['squads']` sorted by `total_failing_rule_instances` desc, show at most 10 rules per squad:

```html
<h3>{squad['name']} — {squad['total_failing_rule_instances']} rule-instances, {squad['total_affected_entities']} entities</h3>
<table data-layout="full-width">
<tr><th><strong>Scorecard</strong></th><th><strong>Rule</strong></th><th><strong>Affected Entities</strong></th></tr>
```

For each `sc` in `squad['scorecards']`, for each `rule` in `sc['rules']` (already sorted by `failing_entity_count` desc):
- Scorecard name: show only on the first rule row for each scorecard, empty string for subsequent rows

```html
<tr>
  <td><strong>{sc_name_or_empty}</strong></td>
  <td>{rule['rule']}</td>
  <td><a href="{squad['cortex_url']}">{rule['failing_entity_count']}</a></td>
</tr>
```

Close `</table>` after each squad.

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
