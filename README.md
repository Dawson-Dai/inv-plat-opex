# Inventory Platform — Baseline Maturity Gaps

Tracks the Inventory Platform tribe's progress toward [Skyscanner Baseline maturity](https://skyscanner.atlassian.net/wiki/spaces/Blogs/blog/2026/05/19/2561704882) by end of 2026.

**Live site:** https://dawson-dai.github.io/inv-plat-opex/

---

## What this repo does

Each time a maturity export is run, one command processes the raw CSV into:

- A **sorted CSV** and **Excel report** (per-squad breakdown) saved under `snapshots/`
- A **JSON snapshot** (`maturity.json`) saved under `data/` and mirrored to `docs/data/` for the live site
- A **Confluence Opex Report** (via Claude skill) published to your personal space for review

Optionally, CloudZero cost data can be fetched and stored alongside the maturity snapshot as `cloudzero.json`, which the Confluence publisher includes as a cost section.

The GitHub Pages site shows:
- **Trend** — failing rule-instances per scorecard over time
- **Priority Standards** — which squads are failing the highest-priority rules
- **Snapshot Explorer** — full tribe and squad detail for any historical snapshot

---

## Workflow

### 1. Export maturity data from Cortex

In Cortex, export the failing Baseline rules to CSV. The file must include a date in its name: `*YYYY-MM-DD*.csv`.

### 2. Process the export

```bash
cd /Users/dawsondai/ai/inv-plat-opex
python3 scripts/run.py ~/Downloads/maturity-export-YYYY-MM-DD.csv
```

This produces:
```
snapshots/YYYY-MM-DD/
  Inventory-platform-maturity-YYYY-MM-DD.csv
  Inventory-platform-maturity-YYYY-MM-DD-sorted-raw.csv
  Inventory-platform-maturity-YYYY-MM-DD-report.xlsx
data/YYYY-MM-DD/
  maturity.json
data/index.json              ← updated
docs/data/YYYY-MM-DD/
  maturity.json              ← mirrored for GitHub Pages
docs/data/index.json         ← updated
```

### 3. Fetch CloudZero cost data (optional)

```bash
python3 scripts/fetch_cloudzero.py [YYYY-MM-DD]
```

If the date is omitted, it uses the latest snapshot date from `data/index.json`. Requires `CLOUDZERO_API_TOKEN` set as an environment variable (or in `.env` at the repo root).

This adds:
```
data/YYYY-MM-DD/
  cloudzero.json
docs/data/YYYY-MM-DD/
  cloudzero.json             ← mirrored for GitHub Pages
```

The Confluence publisher reads this file when building the cost section. If absent, it renders a warning panel instead.

Alternatively, say `fetch cloudzero` in Claude Code to run this via the `opex-fetch-cloudzero` skill.

### 4. Publish the Opex Report to Confluence

In Claude Code, say:

> publish opex report

The `opex-confluence-publish` skill reads the latest `maturity.json` (and `cloudzero.json` if present) and publishes a page titled `Opex-Report-YYYY-MM-DD` under your personal AI space. Review it there, then move to the IP space.

### 5. Update the live site

Commit and push the new `data/` and `docs/data/` files:

```bash
git add data/ docs/data/ snapshots/
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
├── data/                   # Canonical JSON store (maturity.json + cloudzero.json per date)
├── docs/
│   ├── data/               # GitHub Pages mirror of data/
│   ├── index.html          # GitHub Pages site
│   ├── app.js
│   └── style.css
├── config/
│   ├── priority-rules.yaml # Configurable high-priority standards
│   └── squads.yaml         # Squad name → Cortex tag overrides
└── scripts/
    ├── run.py              # Entry point — runs the full maturity pipeline
    ├── sort_csv.py         # Sort and filter the raw CSV
    ├── build_report.py     # Generate Excel report
    ├── build_json.py       # Generate maturity.json snapshot
    └── fetch_cloudzero.py  # Fetch CloudZero cost data → cloudzero.json
```

## Requirements

```bash
pip install openpyxl pyyaml
```

Python 3.9+. No other dependencies.

---

## Planned extensions

Additional data sources that could extend the Opex Report:

- `data/YYYY-MM-DD/incidents.json` — overdue incident actions
- `data/YYYY-MM-DD/ild-actions.json` — ILD action items
