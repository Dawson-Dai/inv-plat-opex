# Opex Maturity Gap Report — Design Spec
**Date:** 2026-06-27
**Author:** Dawson Dai
**Status:** Approved

---

## Problem

The existing Opex Report surfaces scorecard *scores* (e.g., "APIs Are Well-Defined: 45%"). Scores are aggregates that hide whether a squad is 1 rule away from Baseline or 20 rules away. With the company target of reaching Baseline maturity by end of 2026, the report needs to surface actual gaps — specific failing rules and affected entities — so squads can act directly.

---

## Goals

- Replace score-based Tribe Summary and Squad Performance sections with maturity-gap sections driven by the Cortex CSV export
- Show tribe-level and squad-level failing rules grouped by scorecard
- Highlight configurable priority rules with per-squad compliance detail
- Publish to Confluence and visualise trends on a GitHub Pages site
- No live Cortex MCP calls — data is manually exported to keep token costs zero
- Designed to be one skill in a future suite (incidents, cost, ILD actions)

---

## Out of Scope (for now)

- Jira overdue incidents and ILD actions (separate future skill)
- CloudZero cost insights (separate future skill)
- Fetching rule pass/fail totals from Cortex (failures-only from export)

---

## Architecture: Approach B

Three loosely coupled pieces with a clean JSON contract between them:

```
[Manual export] → snapshots/YYYY-MM-DD/
                        ↓
              inventory-maturity-report skill
                        ↓
                 data/YYYY-MM-DD/maturity.json
                /                             \
   opex-confluence-publish skill         GitHub Pages site
          ↓                                    ↓
   Confluence Opex Report             Trend charts + compliance grid
```

---

## Repository Structure

```
inv-plat-opex/
├── snapshots/                          ← renamed from date-folders at root
│   ├── 2026-06-20/
│   │   ├── maturity-export-2026-06-20.csv
│   │   ├── maturity-export-2026-06-20-sorted-raw.csv
│   │   └── maturity-export-2026-06-20-report.xlsx
│   └── 2026-06-25/
│       └── …
├── data/                               ← processed JSON snapshots
│   ├── index.json                      ← manifest listing available dates
│   ├── 2026-06-20/
│   │   └── maturity.json
│   └── 2026-06-25/
│       └── maturity.json
├── config/
│   ├── priority-rules.yaml             ← configurable high-priority rules
│   └── squads.yaml                     ← squad name → Cortex tag mapping
├── docs/                               ← GitHub Pages site root
│   ├── index.html
│   ├── app.js
│   └── style.css
└── scripts/
    ├── run.py                          ← entry point (enhanced)
    ├── sort_csv.py                     ← existing
    ├── build_report.py                 ← existing (Excel)
    └── build_json.py                   ← NEW: generates maturity.json
```

Existing date-folders at root (`2026-06-20/`, `2026-06-25/`) are migrated into `snapshots/` during implementation.

---

## JSON Schema (`data/YYYY-MM-DD/maturity.json`)

This is the contract between the analysis skill, the Confluence publisher, and the GitHub Pages site.

```json
{
  "date": "2026-06-25",
  "tribe_totals": {
    "failing_rule_instances": 1225,
    "unique_rules": 56,
    "affected_entities": 310
  },
  "tribe_by_scorecard": [
    {
      "scorecard": "Data, AI, and ML Governed",
      "all_squads": false,
      "squads_affected": [
        { "name": "Dancing Penguins", "failing_rule_instances": 208 },
        { "name": "Halo", "failing_rule_instances": 86 },
        { "name": "Big Yus", "failing_rule_instances": 102 }
      ],
      "failing_rule_instances": 584,
      "unique_rules": 9,
      "affected_entities": 87
    }
  ],
  "squads": [
    {
      "name": "Halo",
      "cortex_tag": "halo-squad",
      "cortex_url": "https://app.getcortexapp.com/admin/plugins/4033?engineeringExcellenceOverviewPluginRoute=%2Fmaturity%3Flv%3D0%26hp%3D1%26hh%3D1%26tm%3Dhalo-squad",
      "total_failing_rule_instances": 86,
      "total_affected_entities": 46,
      "scorecards": [
        {
          "name": "Data, AI, and ML Governed",
          "rules": [
            {
              "rule": "Datasets must have column descriptions",
              "failing_entity_count": 18,
              "entities": ["halo-dataset-a", "halo-dataset-b"]
            }
          ]
        }
      ]
    }
  ],
  "priority_rules": [
    {
      "rule": "Repositories must have recent commits scanned by SonarQube",
      "label": "SonarQube Scanning",
      "squad_compliance": {
        "Halo": { "failing_entity_count": 8, "entities": ["egressor", "redirects-service"] },
        "Aqua": { "failing_entity_count": 0, "entities": [] }
      }
    }
  ]
}
```

`data/index.json` is a simple manifest updated on each run:
```json
{ "snapshots": ["2026-06-20", "2026-06-25"] }
```

---

## Config Files

### `config/priority-rules.yaml`

```yaml
priority_rules:
  - rule: "Teams must not have live incidents"
    label: "No Live Incidents"
    reason: "P0 reliability standard"
  - rule: "Repositories must have recent commits scanned by SonarQube"
    label: "SonarQube Scanning"
    reason: "Security baseline requirement"
  - rule: "Components must be deployed regularly"
    label: "Regular Deployments"
    reason: "Deployment health indicator"
```

The `rule` field must match the rule name exactly as it appears in the Cortex export. The skill warns if a configured rule isn't found in the current snapshot.

### `config/squads.yaml`

```yaml
# Maps squad display names to their Cortex team tags
# Derived automatically for standard names; override here for exceptions
squad_tags:
  "Fuel RaTS": "fuel-rats-squad"
  "Big Yus": "big-yus-squad"
  # Standard pattern (auto-derived): "Halo" -> "halo-squad"
```

---

## Enhanced `inventory-maturity-report` Skill

### Updated `scripts/run.py` flow

```
1. Derive date from input filename
2. Create snapshots/YYYY-MM-DD/ and copy input CSV there
3. Run sort_csv.py  → snapshots/YYYY-MM-DD/maturity-export-YYYY-MM-DD-sorted-raw.csv
4. Run build_report.py → snapshots/YYYY-MM-DD/maturity-export-YYYY-MM-DD-report.xlsx
5. NEW: Run build_json.py → data/YYYY-MM-DD/maturity.json + update data/index.json
6. Print summary: output paths + tribe totals
```

### `scripts/build_json.py` responsibilities

- Read sorted CSV from `snapshots/YYYY-MM-DD/`
- Exclude `astral-squad` and `bamboo-squad` rows
- Compute tribe totals and per-scorecard breakdown (with "All squads" detection)
- Group by squad → scorecard → rule, counting failing entities
- Read `config/priority-rules.yaml` — build `priority_rules` section; warn if a rule isn't found
- Read `config/squads.yaml` — derive Cortex tags; auto-derive for standard names
- Write `data/YYYY-MM-DD/maturity.json`
- Update `data/index.json` (add date if not already present, keep sorted)

---

## New `opex-confluence-publish` Skill

**Location:** `~/.claude/skills/opex-confluence-publish/SKILL.md`

**Trigger phrases:** "publish opex report", "publish maturity report to confluence", "update opex confluence page"

**Input:** Latest `data/YYYY-MM-DD/maturity.json` (or accepts a `--date` arg)

**Confluence page structure:**

```
Opex Report YYYY-MM-DD
│
├── 1. Tribe Overview
│   └── Per-scorecard breakdown table
│
├── 2. Priority Standards Compliance
│   └── Grid: squads as rows, priority rules as columns
│
└── 3. Squad Detail
    └── Per squad: scorecard → rule → failing entity count (linked)
```

### Table specifications

**Tribe Overview table:**

| Scorecard | Squads Affected | Failing Rule-instances | Unique Rules Failing | Affected Entities |
|---|---|---|---|---|
| Data, AI, and ML Governed | All squads | 584 | 9 | 87 |
| Production Observable and Resilient | Big Yus, Dancing Penguins … (11) | 268 | 12 | 94 |

- "All squads" when every squad has at least one failure in the scorecard
- Otherwise list squad names ordered by failing rule-instances descending; if > 5, show top 5 then "(+N more)"

**Priority Standards Compliance table:**

| Standard | Failing Squads |
|---|---|
| SonarQube Scanning | • Halo (8)<br>• Dancing Penguins (11)<br>• Big Yus (7)<br>• Falcon (4) |
| Regular Deployments | • Halo (3)<br>• Ganymede (1)<br>• Big Yus (2) |
| No Live Incidents | ✅ All squads compliant |

- Standards as rows, failing squads as the single "Failing Squads" column
- Each failing squad listed as `• Squad Name (N)` where N = number of failing entities
- Squads sorted by failing entity count descending
- "✅ All squads compliant" when no squad has failures for that standard
- Entity names not shown in this table (kept in Squad Detail for brevity)

**Squad Detail table (one per squad):**

| Scorecard | Rule | Failing Entities |
|---|---|---|
| **Data, AI, and ML Governed** | Datasets must have column descriptions | [18](cortex_url) |
| | Datasets must have SOX scope flag | [14](cortex_url) |

- Failing entity count is a hyperlink to the squad's Cortex maturity view
- Rule UUID not in export → link filters by squad only (`&tm=<squad-tag>`)
- Scorecard name shown once, merged visually via bold + empty cells below

**Publishing:** Uses Atlassian MCP (`mcp__plugin_atlassian_atlassian__*`). Creates page if it doesn't exist; updates (new version) if it does. Parent page ID configured in the skill or passed as arg.

---

## GitHub Pages Site (`docs/`)

**No build step** — static HTML + JS served directly by GitHub Pages.

### Pages / Sections

1. **Trend** — line chart (Chart.js via CDN) showing failing rule-instances per scorecard over time. X-axis = snapshot dates from `data/index.json`. One line per scorecard, coloured distinctly.

2. **Compliance Grid** — Priority Standards table from the latest snapshot. Same structure as Confluence version. Auto-updates when a new snapshot is committed.

3. **Snapshot Explorer** — date dropdown to view any historical snapshot. Shows tribe overview table and all squad detail tables for the selected date.

### Data loading

```javascript
// 1. Fetch manifest
const index = await fetch('../data/index.json').then(r => r.json())
// 2. Fetch all snapshots for trend chart
const snapshots = await Promise.all(
  index.snapshots.map(d => fetch(`../data/${d}/maturity.json`).then(r => r.json()))
)
// 3. Latest snapshot drives compliance grid and default explorer view
const latest = snapshots[snapshots.length - 1]
```

### Files

```
docs/
├── index.html    ← three-tab layout (Trend | Compliance | Explorer)
├── app.js        ← ~200 lines, all data logic
└── style.css     ← minimal, no framework
```

---

## Squad Tag Derivation

Cortex tag derived from squad display name:
1. Lowercase
2. Replace spaces and special chars with hyphens
3. Collapse multiple hyphens
4. Append `-squad`

Examples: `"Halo"` → `"halo-squad"`, `"Dancing Penguins"` → `"dancing-penguins-squad"`

Exceptions (e.g., `"Fuel RaTS"` → `"fuel-rats-squad"`) are listed in `config/squads.yaml`.

---

## Extensibility

Future skills (incidents, cost, ILD) add their own JSON files alongside `maturity.json`:
```
data/YYYY-MM-DD/
├── maturity.json      ← this spec
├── incidents.json     ← future
├── cost.json          ← future
└── ild-actions.json   ← future
```

A future orchestrator skill reads all available JSON files for a date and composes a single unified Confluence page. The `opex-confluence-publish` skill remains standalone — it only requires `maturity.json`.

---

## Implementation Order

1. Migrate existing date-folders to `snapshots/`
2. Create `config/priority-rules.yaml` and `config/squads.yaml`
3. Write `scripts/build_json.py`
4. Enhance `scripts/run.py` to call `build_json.py` and update `data/index.json`
5. Update `inventory-maturity-report` SKILL.md
6. Initialise git repo, enable GitHub Pages on `docs/`
7. Build `docs/index.html`, `app.js`, `style.css`
8. Write `~/.claude/skills/opex-confluence-publish/SKILL.md`
9. Implement Confluence publishing (test with a draft page first)
10. Backfill `data/` JSON for existing snapshots (2026-06-20, 2026-06-25)
