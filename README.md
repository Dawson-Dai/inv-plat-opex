# Inventory Platform — Baseline Maturity Gaps

Tracks the Inventory Platform tribe's progress toward [Skyscanner Baseline maturity](https://skyscanner.atlassian.net/wiki/spaces/Blogs/blog/2026/05/19/2561704882) by end of 2026.

**Live site:** https://dawson-dai.github.io/inv-plat-opex/

---

## What this repo does

Each time a maturity export is run, one command processes the raw CSV into:

- A **sorted CSV** and **Excel report** (per-squad breakdown) saved under `snapshots/`
- A **JSON snapshot** saved under `docs/data/` that powers the live site
- A **Confluence Opex Report** (via Claude skill) published to your personal space for review

The GitHub Pages site shows:
- **Trend** — failing rule-instances per scorecard over time
- **Priority Standards** — which squads are failing the highest-priority rules
- **Snapshot Explorer** — full tribe and squad detail for any historical snapshot

---

## Workflow

### 1. Export maturity data from Cortex

In Cortex, export the failing Baseline rules to CSV. The file must be named with a date: `maturity-export-YYYY-MM-DD.csv`.

### 2. Process the export

```bash
cd /Users/dawsondai/ai/inv-plat-opex
python3 scripts/run.py ~/Downloads/maturity-export-YYYY-MM-DD.csv
```

This produces:
```
snapshots/YYYY-MM-DD/
  maturity-export-YYYY-MM-DD.csv
  maturity-export-YYYY-MM-DD-sorted-raw.csv
  maturity-export-YYYY-MM-DD-report.xlsx
docs/data/YYYY-MM-DD/
  maturity.json
docs/data/index.json          ← updated
```

### 3. Publish the Opex Report to Confluence

In Claude Code, say:

> publish opex report

The `opex-confluence-publish` skill reads the latest snapshot and publishes a page titled `Opex-Report-YYYY-MM-DD` under your personal AI space. Review it there, then move to the IP space.

### 4. Update the live site

Commit and push the new `docs/data/` files:

```bash
git add docs/data/ snapshots/
git commit -m "data: add maturity snapshot YYYY-MM-DD"
git push
```

GitHub Pages rebuilds automatically — the trend chart and tables update within ~60 seconds.

---

## Priority rules

Edit `config/priority-rules.yaml` to change which standards appear in the Priority Standards tab and Confluence section. The `rule` value must match the rule name exactly as it appears in the Cortex export.

```yaml
priority_rules:
  - rule: "Repositories must have recent commits scanned by SonarQube"
    label: "SonarQube Scanning"
    reason: "Security baseline requirement"
```

## Squad tags

`config/squads.yaml` maps squad display names to their Cortex team tags for the Cortex deep-link URLs. Standard names are auto-derived (e.g. `"Halo"` → `"halo-squad"`). Add overrides here for exceptions.

---

## Repo structure

```
inv-plat-opex/
├── snapshots/              # Raw CSVs and Excel reports per run date
├── docs/
│   ├── data/               # JSON snapshots served by GitHub Pages
│   ├── index.html          # GitHub Pages site
│   ├── app.js
│   └── style.css
├── config/
│   ├── priority-rules.yaml # Configurable high-priority standards
│   └── squads.yaml         # Squad name → Cortex tag overrides
├── scripts/
│   ├── run.py              # Entry point — runs the full pipeline
│   ├── sort_csv.py         # Sort and filter the raw CSV
│   ├── build_report.py     # Generate Excel report
│   └── build_json.py       # Generate maturity.json snapshot
└── data/                   # Canonical JSON store (mirrored to docs/data/)
```

## Requirements

```bash
pip install openpyxl pyyaml
```

Python 3.9+. No other dependencies.

---

## Future extensions

This repo is designed to accept additional data sources alongside `maturity.json`:

- `docs/data/YYYY-MM-DD/incidents.json` — overdue incident actions
- `docs/data/YYYY-MM-DD/ild-actions.json` — ILD action items
- `docs/data/YYYY-MM-DD/cost.json` — CloudZero cost insights

A future orchestrator skill will compose these into a single unified Opex Report.
