# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo does

Processes manually-exported Cortex maturity CSVs into:
1. A sorted CSV + Excel report (saved under `snapshots/`)
2. A `maturity.json` snapshot (saved under `data/` and mirrored to `docs/data/`)
3. A `cloudzero.json` cost snapshot (via `scripts/fetch_cloudzero.py` or the `opex-fetch-cloudzero` skill)
4. A Confluence Opex Report (via the `opex-confluence-publish` skill) combining maturity + cost data
5. A GitHub Pages trend site at https://dawson-dai.github.io/inv-plat-opex/

**Goal:** Surface specific Baseline maturity gaps (failing rules per entity per squad) for the Inventory Platform tribe, in support of the company target to reach Baseline by end of 2026.

## Quick Reference

| Task | Command / Skill |
|---|---|
| Process a new CSV export | `python3 scripts/run.py <path-to-csv>` |
| Fetch CloudZero cost data | `python3 scripts/fetch_cloudzero.py [YYYY-MM-DD]` or say "fetch cloudzero" |
| Publish Opex Report to Confluence | Say "publish opex report" (uses `opex-confluence-publish` skill) |
| Re-generate Excel only | `python3 scripts/build_report.py <sorted_csv> <output.xlsx>` |
| Re-generate JSON only | `python3 scripts/build_json.py <sorted_csv> <YYYY-MM-DD>` |

## Dependencies

```bash
pip install openpyxl pyyaml
```

Python 3.9+. No other dependencies.

## Pipeline (`scripts/run.py`)

All output filenames use a canonical stem regardless of input filename: `Inventory-platform-maturity-YYYY-MM-DD`.

```
Input CSV
  → sort_csv.py        snapshots/YYYY-MM-DD/Inventory-platform-maturity-YYYY-MM-DD-sorted-raw.csv
  → build_report.py    snapshots/YYYY-MM-DD/Inventory-platform-maturity-YYYY-MM-DD-report.xlsx
  → build_json.py      data/YYYY-MM-DD/maturity.json
                       docs/data/YYYY-MM-DD/maturity.json  (GitHub Pages mirror)
                       data/index.json + docs/data/index.json  (updated)
```

`build_json.py` also reads `config/priority-rules.yaml` and `config/squads.yaml` to populate the `priority_rules` section and derive Cortex team tags.

## CloudZero pipeline (`scripts/fetch_cloudzero.py`)

Run separately after `run.py` to add cost data for the same snapshot date.

```
fetch_cloudzero.py [YYYY-MM-DD]
  → CloudZero API    data/YYYY-MM-DD/cloudzero.json
                     docs/data/YYYY-MM-DD/cloudzero.json  (GitHub Pages mirror)
```

Requires `CLOUDZERO_API_TOKEN` env var (or `.env` file at repo root). If absent, the script exits with a clear error. The `opex-confluence-publish` skill reads `cloudzero.json` when present; if missing, it renders a warning panel instead.

## Configuration

**`config/priority-rules.yaml`** — rules shown in the Priority Standards spotlight. The `rule` value must match exactly as it appears in the Cortex CSV export. The script prints a warning if a configured rule isn't found.

**`config/squads.yaml`** — squad name → Cortex tag overrides. Standard derivation: lowercase + hyphens + `-squad` (e.g. `"Halo"` → `"halo-squad"`). Add entries here only for exceptions.

## Excluded squads

`astral-squad` and `bamboo-squad` (and common display-name variants) are hardcoded in `EXCLUDED_SQUADS` in both `sort_csv.py` and `build_json.py`.

## maturity.json schema

Key top-level fields: `date`, `tribe_totals`, `tribe_by_scorecard`, `squads`, `priority_rules`.

- `tribe_by_scorecard[].squads_affected` — sorted by `failing_rule_instances` desc; `all_squads: true` when every squad has ≥1 failure
- `squads[].scorecards[].rules` — sorted by `failing_entity_count` desc
- `priority_rules[].squad_compliance` — keyed by squad display name; all squads included even with 0 failures

## Excel report styling

The report matches the 2026-06-20 reference format. Key non-obvious detail: `build_report.py` saves the workbook to a buffer, then `_patch_chart_xml()` post-processes the ZIP to inject `<delete val="0"/>` and `<tickLblPos val="nextTo"/>` into the chart's `catAx` — openpyxl omits these, which causes Excel to hide the squad name axis labels.

Squad sheets use a side-by-side layout: Scorecard Summary (cols A–F) | Rule Breakdown (cols H–L) | Entity Detail (cols N–Q), all starting at row 5.

## GitHub Pages

Served from the `docs/` folder on `main`. Requires `docs/.nojekyll` to prevent Jekyll from processing the static site. The `docs/data/` directory is the Pages-served mirror of `data/` — both are updated by `build_json.py` (maturity) and `fetch_cloudzero.py` (cost) on each run.

After adding a new snapshot, commit and push `data/` and `docs/data/` to update the live site.

## Confluence publishing

Uses the `opex-confluence-publish` skill (`.claude/skills/opex-confluence-publish/SKILL.md`). Publishes to the `~dawsondai` personal space (parent page ID `2047672627`) for review, then manually moved to the IP space.

The Squad Detail section is capped at the top 5 squads — the full breakdown is linked to the GitHub Pages site — because the full HTML exceeds practical MCP payload limits.

## Skills

All three skills are checked into `.claude/skills/` and load automatically:

- **`inventory-maturity-report`** — trigger: "maturity report", "maturity CSV", "baseline failures", or providing a CSV path
- **`opex-fetch-cloudzero`** — trigger: "fetch cloudzero", "refresh cost data", "cloudzero costs", "cost data missing"
- **`opex-confluence-publish`** — trigger: "publish opex report", "publish maturity report to confluence"
