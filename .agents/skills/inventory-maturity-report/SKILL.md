---
name: inventory-maturity-report
description: >
  Processes an Inventory Platform Cortex maturity CSV export into: a re-sorted CSV,
  a polished Excel report, and a data/YYYY-MM-DD/maturity.json snapshot for the
  Confluence publisher and GitHub Pages site. Use when the user mentions "maturity report",
  "maturity CSV", "inventory platform report", "scorecard report", "baseline failures",
  "cortex maturity", or provides a CSV file path with squads/scorecards/rules context.
---

# Inventory Platform Maturity Report

## What this skill does

Takes one raw maturity export CSV and produces three outputs:

1. **Sorted CSV** — re-sorted by Squad → Entity → Scorecard → Rule, with those columns at the front.
2. **Excel report** — multi-sheet `.xlsx`: Tribe Overview (summary table + bar chart) + one sheet per squad (KPI strip, Scorecard Summary, Rule Breakdown, Entity Detail).
3. **JSON snapshot** — `data/YYYY-MM-DD/maturity.json` with tribe totals, per-scorecard breakdown, per-squad rule failures, and priority-rules compliance. Also updates `data/index.json`.

## Input format

CSV columns (case-sensitive): `Entity`, `Scorecard`, `Squad`, `Level`, `Status`, `Rule`, `Description`, `Failure Message`, `Last Evaluated`

All rows are expected to be Baseline-level Fails.

## Squads to exclude

`astral-squad` and `bamboo-squad` are excluded automatically.

## How to run

```bash
cd /Users/dawsondai/ai/inv-plat-opex
python3 scripts/run.py <input_csv>
```

The script derives the date from the filename, creates `snapshots/YYYY-MM-DD/`, runs sort → Excel → JSON, and prints tribe totals.

## Output location

```
snapshots/YYYY-MM-DD/
  <name>.csv                    ← input copy
  <name>-sorted-raw.csv
  <name>-report.xlsx
data/YYYY-MM-DD/
  maturity.json
data/index.json                 ← updated manifest
```

## After running

Report to the user: output folder, files produced, tribe totals (rule-instances, unique rules, entities, squads).

## Priority rules config

Edit `config/priority-rules.yaml` to change the Priority Standards spotlight. The `rule` value must match exactly as it appears in the CSV.

## Next step

To publish to Confluence: use the `opex-confluence-publish` skill.
