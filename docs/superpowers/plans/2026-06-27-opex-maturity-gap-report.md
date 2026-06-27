# Opex Maturity Gap Report — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a skill-driven pipeline that turns a manually-exported Cortex maturity CSV into a `maturity.json` snapshot, publishes a Confluence Opex Report (tribe overview + priority standards + squad detail), and serves a GitHub Pages trend site — all with zero live Cortex MCP calls.

**Architecture:** Three loosely-coupled pieces sharing a JSON contract: (1) `inventory-maturity-report` skill runs Python scripts to process the CSV and emit `data/YYYY-MM-DD/maturity.json`; (2) `opex-confluence-publish` skill reads that JSON and publishes to Confluence via Atlassian MCP; (3) a static `docs/` site loads all snapshot JSONs from the repo and renders trend charts and compliance grids.

**Tech Stack:** Python 3 (stdlib + `openpyxl` + `pyyaml`), vanilla HTML/JS/CSS, Chart.js CDN, Atlassian MCP for Confluence publishing.

## Global Constraints

- All Python scripts run from `/Users/dawsondai/ai/inv-plat-opex/` as working directory
- Excluded squads: `astral-squad`, `bamboo-squad` — filter from ALL outputs
- Input CSV columns (case-sensitive): `Entity`, `Scorecard`, `Squad`, `Level`, `Status`, `Rule`, `Description`, `Failure Message`, `Last Evaluated`
- Sorted CSV column order: `Squad`, `Entity`, `Scorecard`, `Rule`, `Level`, `Status`, `Description`, `Failure Message`, `Last Evaluated`
- All rows in the export are `Status=Fail`, `Level=Baseline`
- Cortex app base URL: `https://app.getcortexapp.com/admin/plugins/4033?engineeringExcellenceOverviewPluginRoute=%2Fmaturity%3Flv%3D0%26hp%3D1%26hh%3D1%26tm%3D`
- Squad tag derivation: lowercase, spaces/special-chars → hyphens, collapse hyphens, append `-squad`; exceptions in `config/squads.yaml`
- `data/index.json` keeps `snapshots` array sorted ascending by date string
- GitHub Pages serves from `docs/` folder on `main` branch
- Skills live in `~/.claude/skills/`

---

## File Map

| File | Status | Responsibility |
|---|---|---|
| `snapshots/YYYY-MM-DD/` | New (migrated) | Raw CSV + sorted CSV + Excel per run |
| `config/priority-rules.yaml` | Create | Configurable high-priority rules list |
| `config/squads.yaml` | Create | Squad name → Cortex tag exceptions |
| `scripts/sort_csv.py` | Create | Sort input CSV → sorted CSV in snapshots/ |
| `scripts/build_report.py` | Create | Sorted CSV → Excel report in snapshots/ |
| `scripts/build_json.py` | Create | Sorted CSV + configs → data/YYYY-MM-DD/maturity.json + update data/index.json |
| `scripts/run.py` | Create | Entry point: orchestrates all three scripts |
| `data/index.json` | Create | Manifest of available snapshot dates |
| `data/YYYY-MM-DD/maturity.json` | Generated | JSON contract for publisher + site |
| `docs/index.html` | Create | GitHub Pages site: three-tab layout |
| `docs/app.js` | Create | Data loading + Chart.js rendering + table rendering |
| `docs/style.css` | Create | Minimal site styling |
| `~/.claude/skills/inventory-maturity-report/SKILL.md` | Modify | Update to document new scripts + JSON output |
| `~/.claude/skills/opex-confluence-publish/SKILL.md` | Create | New skill: reads JSON, publishes to Confluence |

---

## Task 1: Repo Setup, Migration, and Config Files

**Files:**
- Create: `snapshots/2026-06-20/` (migrate from `2026-06-20/`)
- Create: `snapshots/2026-06-25/` (migrate from `2026-06-25/`)
- Create: `config/priority-rules.yaml`
- Create: `config/squads.yaml`
- Create: `data/index.json`
- Create: `.gitignore`

**Interfaces:**
- Produces: `config/priority-rules.yaml` consumed by `build_json.py` (Task 4)
- Produces: `config/squads.yaml` consumed by `build_json.py` (Task 4)
- Produces: `data/index.json` consumed by `docs/app.js` (Task 6)

- [ ] **Step 1: Initialise git repo**

```bash
cd /Users/dawsondai/ai/inv-plat-opex
git init
```

Expected: `Initialized empty Git repository in /Users/dawsondai/ai/inv-plat-opex/.git/`

- [ ] **Step 2: Create snapshots/ and migrate existing date folders**

```bash
mkdir -p snapshots
mv 2026-06-20 snapshots/
mv 2026-06-25 snapshots/
ls snapshots/
```

Expected: `2026-06-20  2026-06-25`

- [ ] **Step 3: Create config/priority-rules.yaml**

```bash
mkdir -p config
```

Write `config/priority-rules.yaml`:

```yaml
priority_rules:
  - rule: "Components must be deployed regularly"
    label: "Regular Deployments"
    reason: "Deployment health indicator"
  - rule: "Repositories must have recent commits scanned by SonarQube"
    label: "SonarQube Scanning"
    reason: "Security baseline requirement"
  - rule: "Privacy and Consent Adoption"
    label: "Privacy & Consent"
    reason: "Company-wide privacy compliance programme"
```

Note: `"Teams must not have live incidents"` is not in the maturity CSV export (it's a Jira-sourced rule) — use rules that actually appear in the CSV. These three are present in the 2026-06-25 export. Update this file at any time to change the priority spotlight.

- [ ] **Step 4: Create config/squads.yaml**

Write `config/squads.yaml`:

```yaml
# Squad display name → Cortex team tag exceptions.
# Auto-derived rule: lowercase, spaces/special-chars→hyphens, collapse, append -squad
# e.g. "Halo" → "halo-squad", "Dancing Penguins" → "dancing-penguins-squad"
# Add overrides here when auto-derivation produces the wrong tag.
squad_tags:
  "Fuel RaTS": "fuel-rats-squad"
  "Big Yus": "big-yus-squad"
  "Ollivander": "ollivander-squad"
  "Spyro": "spyro-squad"
```

- [ ] **Step 5: Create data/ directory and empty index**

```bash
mkdir -p data
```

Write `data/index.json`:

```json
{
  "snapshots": []
}
```

- [ ] **Step 6: Create .gitignore**

Write `.gitignore`:

```
__pycache__/
*.pyc
.DS_Store
*.egg-info/
venv/
.env
```

- [ ] **Step 7: Verify structure**

```bash
ls -1 /Users/dawsondai/ai/inv-plat-opex/
```

Expected output includes: `config/  data/  docs/  snapshots/  scripts/` (docs/ and scripts/ don't exist yet — that's fine at this stage)

- [ ] **Step 8: Initial commit**

```bash
cd /Users/dawsondai/ai/inv-plat-opex
git add config/ data/ snapshots/ .gitignore
git commit -m "chore: initialise repo structure, migrate snapshots, add config files"
```

---

## Task 2: `scripts/sort_csv.py`

**Files:**
- Create: `scripts/sort_csv.py`

**Interfaces:**
- Consumes: `snapshots/YYYY-MM-DD/<input>.csv` (path passed as arg)
- Produces: `snapshots/YYYY-MM-DD/<input>-sorted-raw.csv` (path returned as string)
- Exposes: `def sort_csv(input_path: str, output_path: str) -> int` — returns row count written

- [ ] **Step 1: Create scripts/ directory**

```bash
mkdir -p /Users/dawsondai/ai/inv-plat-opex/scripts
```

- [ ] **Step 2: Write sort_csv.py**

Write `scripts/sort_csv.py`:

```python
"""
Sort a Cortex maturity export CSV by Squad → Entity → Scorecard → Rule.
Moves Squad, Entity, Scorecard, Rule to the front columns.
Excludes astral-squad and bamboo-squad rows.
"""
import csv
import sys

EXCLUDED_SQUADS = {"astral-squad", "bamboo-squad"}
FRONT_COLS = ["Squad", "Entity", "Scorecard", "Rule"]


def sort_csv(input_path: str, output_path: str) -> int:
    with open(input_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [r for r in reader if r.get("Squad", "").strip() not in EXCLUDED_SQUADS]

    rows.sort(key=lambda r: (r["Squad"], r["Entity"], r["Scorecard"], r["Rule"]))

    all_cols = list(rows[0].keys()) if rows else []
    remaining = [c for c in all_cols if c not in FRONT_COLS]
    out_cols = FRONT_COLS + remaining

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_cols)
        writer.writeheader()
        writer.writerows(rows)

    return len(rows)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: sort_csv.py <input_csv> <output_csv>")
        sys.exit(1)
    count = sort_csv(sys.argv[1], sys.argv[2])
    print(f"Wrote {count} rows to {sys.argv[2]}")
```

- [ ] **Step 3: Smoke test**

```bash
cd /Users/dawsondai/ai/inv-plat-opex
python3 scripts/sort_csv.py \
  snapshots/2026-06-25/maturity-export-2026-06-25.csv \
  /tmp/sorted-test.csv
head -3 /tmp/sorted-test.csv
```

Expected: first line is header starting with `Squad,Entity,Scorecard,Rule,…`; second line starts with `Aqua,` (first squad alphabetically).

- [ ] **Step 4: Verify exclusion works**

```bash
grep -c "astral-squad" /tmp/sorted-test.csv || echo "0 astral-squad rows — correct"
```

Expected: `0 astral-squad rows — correct`

- [ ] **Step 5: Commit**

```bash
cd /Users/dawsondai/ai/inv-plat-opex
git add scripts/sort_csv.py
git commit -m "feat: add sort_csv.py — sort maturity export by Squad→Entity→Scorecard→Rule"
```

---

## Task 3: `scripts/build_report.py` (Excel)

**Files:**
- Create: `scripts/build_report.py`

**Interfaces:**
- Consumes: sorted CSV path (string), output xlsx path (string)
- Produces: Excel workbook at output path
- Exposes: `def build_report(sorted_csv: str, output_xlsx: str) -> dict` — returns `{"squads": int, "rows": int}`

The Excel workbook has:
- **Tribe Overview sheet**: per-squad summary table (squad | scorecards failing | rules failing | entities failing | rows failing) + grand total row + clustered bar chart
- **One sheet per squad**: KPI strip (total rows / entities / rules) + Scorecard Summary table (scorecard | rules | entities | rows) + Rule Breakdown table (scorecard | rule | entities | rows) + Entity Detail table (entity | scorecard | rule)

- [ ] **Step 1: Write build_report.py**

Write `scripts/build_report.py`:

```python
"""
Build an Excel maturity report from a sorted Cortex maturity CSV.
Produces: Tribe Overview sheet + one sheet per squad.
"""
import csv
import sys
from collections import defaultdict
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.chart import BarChart, Reference
from openpyxl.utils import get_column_letter

HDR_FILL = PatternFill("solid", fgColor="1F4E79")
HDR_FONT = Font(bold=True, color="FFFFFF")
ALT_FILL = PatternFill("solid", fgColor="D6E4F0")
TOTAL_FILL = PatternFill("solid", fgColor="BDD7EE")
TOTAL_FONT = Font(bold=True)
THIN = Side(style="thin", color="AAAAAA")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def _load(sorted_csv: str):
    with open(sorted_csv, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _hdr(ws, row, col, value):
    c = ws.cell(row=row, column=col, value=value)
    c.font = HDR_FONT
    c.fill = HDR_FILL
    c.alignment = Alignment(horizontal="center", wrap_text=True)
    c.border = BORDER


def _cell(ws, row, col, value, alt=False, bold=False):
    c = ws.cell(row=row, column=col, value=value)
    if alt:
        c.fill = ALT_FILL
    if bold:
        c.font = TOTAL_FONT
        c.fill = TOTAL_FILL
    c.border = BORDER
    c.alignment = Alignment(wrap_text=True)
    return c


def _auto_width(ws, min_w=10, max_w=50):
    for col in ws.columns:
        length = max((len(str(c.value or "")) for c in col), default=min_w)
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(max(length + 2, min_w), max_w)


def build_report(sorted_csv: str, output_xlsx: str) -> dict:
    rows = _load(sorted_csv)
    wb = Workbook()

    # --- aggregate data ---
    # squad → scorecard → rule → set of entities
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))
    for r in rows:
        data[r["Squad"]][r["Scorecard"]][r["Rule"]].add(r["Entity"])

    squads = sorted(data.keys())

    # --- Tribe Overview sheet ---
    ws = wb.active
    ws.title = "Tribe Overview"
    headers = ["Squad", "Scorecards Failing", "Rules Failing", "Entities Failing", "Rows (rule-instances)"]
    for ci, h in enumerate(headers, 1):
        _hdr(ws, 1, ci, h)

    chart_rows = []  # (squad, rows_count, entities_count)
    ri = 2
    total_sc, total_ru, total_en, total_ro = set(), set(), set(), 0
    for squad in squads:
        scorecards = data[squad]
        sc_count = len(scorecards)
        ru_count = sum(len(rules) for rules in scorecards.values())
        en_count = len({e for rules in scorecards.values() for ents in rules.values() for e in ents})
        ro_count = sum(len(ents) for rules in scorecards.values() for ents in rules.values())
        alt = (ri % 2 == 0)
        _cell(ws, ri, 1, squad, alt)
        _cell(ws, ri, 2, sc_count, alt)
        _cell(ws, ri, 3, ru_count, alt)
        _cell(ws, ri, 4, en_count, alt)
        _cell(ws, ri, 5, ro_count, alt)
        chart_rows.append((squad, ro_count, en_count))
        total_sc.update(scorecards.keys())
        total_ru.update(r for rules in scorecards.values() for r in rules)
        total_en.update(e for rules in scorecards.values() for ents in rules.values() for e in ents)
        total_ro += ro_count
        ri += 1

    # Grand total row
    _cell(ws, ri, 1, "TOTAL", bold=True)
    _cell(ws, ri, 2, len(total_sc), bold=True)
    _cell(ws, ri, 3, len(total_ru), bold=True)
    _cell(ws, ri, 4, len(total_en), bold=True)
    _cell(ws, ri, 5, total_ro, bold=True)

    # Bar chart
    data_rows = len(squads)
    chart = BarChart()
    chart.type = "col"
    chart.grouping = "clustered"
    chart.title = "Failing Rows & Entities per Squad"
    chart.y_axis.title = "Count"
    chart.width = 24
    chart.height = 14
    rows_ref = Reference(ws, min_col=5, min_row=1, max_row=1 + data_rows)
    ents_ref = Reference(ws, min_col=4, min_row=1, max_row=1 + data_rows)
    cats_ref = Reference(ws, min_col=1, min_row=2, max_row=1 + data_rows)
    chart.add_data(rows_ref, titles_from_data=True)
    chart.add_data(ents_ref, titles_from_data=True)
    chart.set_categories(cats_ref)
    ws.add_chart(chart, f"G2")

    _auto_width(ws)

    # --- Per-squad sheets ---
    for squad in squads:
        safe = squad[:28].replace("/", "-").replace("\\", "-").replace("*", "").replace("?", "").replace("[", "").replace("]", "").replace(":", "")
        ws2 = wb.create_sheet(title=safe)
        scorecards = data[squad]

        # KPI strip
        total_rows_sq = sum(len(e) for sc in scorecards.values() for e in sc.values())
        total_ents_sq = len({e for sc in scorecards.values() for ents in sc.values() for e in ents})
        total_rules_sq = sum(len(sc) for sc in scorecards.values())
        ws2["A1"] = f"Squad: {squad}"
        ws2["A1"].font = Font(bold=True, size=13)
        ws2["A2"] = f"Total rule-instances: {total_rows_sq}   |   Entities: {total_ents_sq}   |   Unique rules: {total_rules_sq}"
        ws2["A2"].font = Font(italic=True)
        ws2.row_dimensions[1].height = 20

        # Scorecard Summary
        ws2["A4"] = "Scorecard Summary"
        ws2["A4"].font = Font(bold=True, size=11)
        sc_hdrs = ["Scorecard", "Rules Failing", "Entities Failing", "Rows (rule-instances)"]
        for ci, h in enumerate(sc_hdrs, 1):
            _hdr(ws2, 5, ci, h)
        ri2 = 6
        for sc_name, rules in sorted(scorecards.items()):
            ru_c = len(rules)
            en_c = len({e for ents in rules.values() for e in ents})
            ro_c = sum(len(ents) for ents in rules.values())
            alt = (ri2 % 2 == 0)
            _cell(ws2, ri2, 1, sc_name, alt)
            _cell(ws2, ri2, 2, ru_c, alt)
            _cell(ws2, ri2, 3, en_c, alt)
            _cell(ws2, ri2, 4, ro_c, alt)
            ri2 += 1

        # Rule Breakdown
        rb_start = ri2 + 2
        ws2.cell(row=rb_start - 1, column=1, value="Rule Breakdown").font = Font(bold=True, size=11)
        rb_hdrs = ["Scorecard", "Rule", "Entities Failing", "Rows"]
        for ci, h in enumerate(rb_hdrs, 1):
            _hdr(ws2, rb_start, ci, h)
        ri3 = rb_start + 1
        for sc_name, rules in sorted(scorecards.items()):
            for rule, ents in sorted(rules.items(), key=lambda x: -len(x[1])):
                alt = (ri3 % 2 == 0)
                _cell(ws2, ri3, 1, sc_name, alt)
                _cell(ws2, ri3, 2, rule, alt)
                _cell(ws2, ri3, 3, len(ents), alt)
                _cell(ws2, ri3, 4, len(ents), alt)
                ri3 += 1

        # Entity Detail
        ed_start = ri3 + 2
        ws2.cell(row=ed_start - 1, column=1, value="Entity Detail").font = Font(bold=True, size=11)
        ed_hdrs = ["Entity", "Scorecard", "Rule"]
        for ci, h in enumerate(ed_hdrs, 1):
            _hdr(ws2, ed_start, ci, h)
        ri4 = ed_start + 1
        for sc_name, rules in sorted(scorecards.items()):
            for rule, ents in sorted(rules.items()):
                for ent in sorted(ents):
                    alt = (ri4 % 2 == 0)
                    _cell(ws2, ri4, 1, ent, alt)
                    _cell(ws2, ri4, 2, sc_name, alt)
                    _cell(ws2, ri4, 3, rule, alt)
                    ri4 += 1

        _auto_width(ws2)

    wb.save(output_xlsx)
    return {"squads": len(squads), "rows": sum(len(e) for sq in data.values() for sc in sq.values() for e in sc.values())}


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: build_report.py <sorted_csv> <output_xlsx>")
        sys.exit(1)
    result = build_report(sys.argv[1], sys.argv[2])
    print(f"Excel report written: {result['squads']} squads, {result['rows']} rows → {sys.argv[2]}")
```

- [ ] **Step 2: Smoke test**

```bash
cd /Users/dawsondai/ai/inv-plat-opex
python3 scripts/build_report.py \
  snapshots/2026-06-25/maturity-export-2026-06-25-sorted-raw.csv \
  /tmp/test-report.xlsx
```

Expected: `Excel report written: 17 squads, 1225 rows → /tmp/test-report.xlsx`

- [ ] **Step 3: Verify file is valid**

```bash
python3 -c "
from openpyxl import load_workbook
wb = load_workbook('/tmp/test-report.xlsx')
print('Sheets:', wb.sheetnames[:5], '...')
print('Tribe Overview rows:', wb.active.max_row)
"
```

Expected: `Sheets: ['Tribe Overview', 'Aqua', 'Big Yus', 'Dancing Penguins', 'Falcon'] ...` and row count > 17.

- [ ] **Step 4: Commit**

```bash
cd /Users/dawsondai/ai/inv-plat-opex
git add scripts/build_report.py
git commit -m "feat: add build_report.py — generate Excel maturity report with tribe overview and per-squad sheets"
```

---

## Task 4: `scripts/build_json.py`

**Files:**
- Create: `scripts/build_json.py`

**Interfaces:**
- Consumes: sorted CSV path, `config/priority-rules.yaml`, `config/squads.yaml`
- Produces: `data/YYYY-MM-DD/maturity.json`, updates `data/index.json`
- Exposes: `def build_json(sorted_csv: str, date: str, config_dir: str = "config", data_dir: str = "data") -> dict` — returns the written JSON object

- [ ] **Step 1: Write build_json.py**

Write `scripts/build_json.py`:

```python
"""
Generate data/YYYY-MM-DD/maturity.json from a sorted maturity CSV.
Also updates data/index.json manifest.
"""
import csv
import json
import re
import sys
import os
from collections import defaultdict
from pathlib import Path
import yaml

EXCLUDED_SQUADS = {"astral-squad", "bamboo-squad"}
CORTEX_BASE = (
    "https://app.getcortexapp.com/admin/plugins/4033"
    "?engineeringExcellenceOverviewPluginRoute="
    "%2Fmaturity%3Flv%3D0%26hp%3D1%26hh%3D1%26tm%3D"
)


def _derive_tag(name: str) -> str:
    tag = name.lower()
    tag = re.sub(r"[^a-z0-9]+", "-", tag)
    tag = re.sub(r"-+", "-", tag).strip("-")
    return tag + "-squad"


def _load_squads_config(config_dir: str) -> dict:
    path = Path(config_dir) / "squads.yaml"
    if not path.exists():
        return {}
    with open(path) as f:
        data = yaml.safe_load(f)
    return data.get("squad_tags", {}) if data else {}


def _load_priority_rules(config_dir: str) -> list:
    path = Path(config_dir) / "priority-rules.yaml"
    if not path.exists():
        return []
    with open(path) as f:
        data = yaml.safe_load(f)
    return data.get("priority_rules", []) if data else []


def build_json(sorted_csv: str, date: str, config_dir: str = "config", data_dir: str = "data") -> dict:
    squad_tag_overrides = _load_squads_config(config_dir)
    priority_rule_configs = _load_priority_rules(config_dir)

    # Load rows
    with open(sorted_csv, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r.get("Squad", "").strip() not in EXCLUDED_SQUADS]

    # Build squad → scorecard → rule → [entities]
    tree = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))
    for r in rows:
        tree[r["Squad"]][r["Scorecard"]][r["Rule"]].add(r["Entity"])

    all_squads = sorted(tree.keys())
    total_squads = len(all_squads)

    # Tribe totals
    all_entities = {e for sq in tree.values() for sc in sq.values() for ents in sc.values() for e in ents}
    all_rules = {rule for sq in tree.values() for sc in sq.values() for rule in sc}
    tribe_totals = {
        "failing_rule_instances": len(rows),
        "unique_rules": len(all_rules),
        "affected_entities": len(all_entities),
    }

    # tribe_by_scorecard
    sc_map = defaultdict(lambda: defaultdict(int))  # scorecard → squad → row_count
    sc_ent_map = defaultdict(set)   # scorecard → entities
    sc_rule_map = defaultdict(set)  # scorecard → rules
    for r in rows:
        sc_map[r["Scorecard"]][r["Squad"]] += 1
        sc_ent_map[r["Scorecard"]].add(r["Entity"])
        sc_rule_map[r["Scorecard"]].add(r["Rule"])

    tribe_by_scorecard = []
    for sc_name in sorted(sc_map.keys()):
        squad_counts = sc_map[sc_name]
        all_sq = squad_counts.keys() == set(all_squads)
        squads_affected = sorted(squad_counts.items(), key=lambda x: -x[1])
        tribe_by_scorecard.append({
            "scorecard": sc_name,
            "all_squads": all_sq,
            "squads_affected": [{"name": s, "failing_rule_instances": c} for s, c in squads_affected],
            "failing_rule_instances": sum(squad_counts.values()),
            "unique_rules": len(sc_rule_map[sc_name]),
            "affected_entities": len(sc_ent_map[sc_name]),
        })
    tribe_by_scorecard.sort(key=lambda x: -x["failing_rule_instances"])

    # squads
    squads_out = []
    for squad in all_squads:
        tag = squad_tag_overrides.get(squad, _derive_tag(squad))
        cortex_url = CORTEX_BASE + tag
        sc_data = tree[squad]
        scorecards_out = []
        for sc_name in sorted(sc_data.keys()):
            rules_out = []
            for rule, ents in sorted(sc_data[sc_name].items(), key=lambda x: -len(x[1])):
                rules_out.append({
                    "rule": rule,
                    "failing_entity_count": len(ents),
                    "entities": sorted(ents),
                })
            scorecards_out.append({"name": sc_name, "rules": rules_out})
        total_ri = sum(len(e) for sc in sc_data.values() for e in sc.values())
        total_ent = len({e for sc in sc_data.values() for ents in sc.values() for e in ents})
        squads_out.append({
            "name": squad,
            "cortex_tag": tag,
            "cortex_url": cortex_url,
            "total_failing_rule_instances": total_ri,
            "total_affected_entities": total_ent,
            "scorecards": scorecards_out,
        })

    # priority_rules
    priority_rules_out = []
    priority_rule_names = {p["rule"] for p in priority_rule_configs}
    for p_cfg in priority_rule_configs:
        rule_name = p_cfg["rule"]
        if rule_name not in all_rules:
            print(f"  ⚠️  Priority rule not found in snapshot: '{rule_name}'", file=sys.stderr)
        squad_compliance = {}
        for squad in all_squads:
            ents = sorted(tree[squad].get("__any__", {}).get(rule_name, set()))
            # search all scorecards
            failing = set()
            for sc_data in tree[squad].values():
                if rule_name in sc_data:
                    failing.update(sc_data[rule_name])
            squad_compliance[squad] = {
                "failing_entity_count": len(failing),
                "entities": sorted(failing),
            }
        priority_rules_out.append({
            "rule": rule_name,
            "label": p_cfg.get("label", rule_name),
            "squad_compliance": squad_compliance,
        })

    result = {
        "date": date,
        "tribe_totals": tribe_totals,
        "tribe_by_scorecard": tribe_by_scorecard,
        "squads": squads_out,
        "priority_rules": priority_rules_out,
    }

    # Write data/YYYY-MM-DD/maturity.json
    out_dir = Path(data_dir) / date
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "maturity.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"  Written: {out_path}")

    # Update data/index.json
    index_path = Path(data_dir) / "index.json"
    if index_path.exists():
        with open(index_path) as f:
            index = json.load(f)
    else:
        index = {"snapshots": []}
    if date not in index["snapshots"]:
        index["snapshots"].append(date)
        index["snapshots"].sort()
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)
    print(f"  Updated: {index_path} → {index['snapshots']}")

    return result


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4, 5):
        print("Usage: build_json.py <sorted_csv> <date YYYY-MM-DD> [config_dir] [data_dir]")
        sys.exit(1)
    sorted_csv = sys.argv[1]
    date = sys.argv[2]
    config_dir = sys.argv[3] if len(sys.argv) > 3 else "config"
    data_dir = sys.argv[4] if len(sys.argv) > 4 else "data"
    build_json(sorted_csv, date, config_dir, data_dir)
    print("Done.")
```

- [ ] **Step 2: Smoke test**

```bash
cd /Users/dawsondai/ai/inv-plat-opex
python3 scripts/build_json.py \
  snapshots/2026-06-25/maturity-export-2026-06-25-sorted-raw.csv \
  2026-06-25
```

Expected output:
```
  Written: data/2026-06-25/maturity.json
  Updated: data/index.json → ['2026-06-25']
Done.
```

- [ ] **Step 3: Verify JSON structure**

```bash
python3 -c "
import json
with open('data/2026-06-25/maturity.json') as f:
    d = json.load(f)
print('date:', d['date'])
print('tribe_totals:', d['tribe_totals'])
print('scorecards:', [s['scorecard'] for s in d['tribe_by_scorecard']])
print('squads:', [s['name'] for s in d['squads']])
print('priority_rules:', [p['rule'] for p in d['priority_rules']])
# Spot-check Halo
halo = next(s for s in d['squads'] if s['name'] == 'Halo')
print('Halo cortex_tag:', halo['cortex_tag'])
print('Halo total_failing_rule_instances:', halo['total_failing_rule_instances'])
print('Halo first scorecard rules count:', len(halo['scorecards'][0]['rules']))
"
```

Expected: `date: 2026-06-25`, `tribe_totals: {'failing_rule_instances': 1225, ...}`, `Halo cortex_tag: halo-squad`, `Halo total_failing_rule_instances: 86`

- [ ] **Step 4: Check priority rules warnings**

The test output should show warnings for any priority rules not in the export. If "Regular Deployments" or "SonarQube Scanning" are missing, update `config/priority-rules.yaml` to use rule names that actually appear in the CSV:

```bash
python3 -c "
import csv
with open('snapshots/2026-06-25/maturity-export-2026-06-25-sorted-raw.csv') as f:
    rules = sorted(set(r['Rule'] for r in csv.DictReader(f)))
for r in rules:
    print(r)
" | grep -i -E "deploy|sonar|privacy"
```

Use the exact rule names from this output to update `config/priority-rules.yaml` if needed.

- [ ] **Step 5: Commit**

```bash
cd /Users/dawsondai/ai/inv-plat-opex
git add scripts/build_json.py data/
git commit -m "feat: add build_json.py — generate maturity.json snapshot from sorted CSV"
```

---

## Task 5: `scripts/run.py` (entry point)

**Files:**
- Create: `scripts/run.py`

**Interfaces:**
- Consumes: raw input CSV path (arg)
- Calls: `sort_csv.sort_csv()`, `build_report.build_report()`, `build_json.build_json()`
- Produces: all outputs in `snapshots/YYYY-MM-DD/` and `data/YYYY-MM-DD/`

- [ ] **Step 1: Write run.py**

Write `scripts/run.py`:

```python
"""
Entry point for the Inventory Platform maturity report pipeline.

Usage:
    python3 scripts/run.py <input_csv>

Example:
    python3 scripts/run.py ~/Downloads/maturity-export-2026-06-27.csv

Steps:
  1. Derive date from filename (YYYY-MM-DD)
  2. Copy input CSV to snapshots/YYYY-MM-DD/
  3. Sort CSV → snapshots/YYYY-MM-DD/<name>-sorted-raw.csv
  4. Build Excel report → snapshots/YYYY-MM-DD/<name>-report.xlsx
  5. Build JSON snapshot → data/YYYY-MM-DD/maturity.json + update data/index.json
  6. Print summary
"""
import re
import shutil
import sys
from pathlib import Path

# Run from repo root
REPO_ROOT = Path(__file__).parent.parent

sys.path.insert(0, str(Path(__file__).parent))
from sort_csv import sort_csv
from build_report import build_report
from build_json import build_json


def _extract_date(filename: str) -> str:
    match = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
    if match:
        return match.group(1)
    from datetime import date
    return date.today().isoformat()


def run(input_csv: str):
    input_path = Path(input_csv).expanduser().resolve()
    if not input_path.exists():
        print(f"Error: file not found: {input_path}")
        sys.exit(1)

    date = _extract_date(input_path.name)
    print(f"\n📅 Date: {date}")

    # Step 2: Copy to snapshots/
    snap_dir = REPO_ROOT / "snapshots" / date
    snap_dir.mkdir(parents=True, exist_ok=True)
    dest_csv = snap_dir / input_path.name
    if not dest_csv.exists():
        shutil.copy2(input_path, dest_csv)
        print(f"✓ Copied input → {dest_csv.relative_to(REPO_ROOT)}")
    else:
        print(f"  (input already in snapshots, skipping copy)")

    # Step 3: Sort
    stem = input_path.stem  # e.g. maturity-export-2026-06-27
    sorted_path = snap_dir / f"{stem}-sorted-raw.csv"
    row_count = sort_csv(str(dest_csv), str(sorted_path))
    print(f"✓ Sorted CSV ({row_count} rows) → {sorted_path.relative_to(REPO_ROOT)}")

    # Step 4: Excel
    xlsx_path = snap_dir / f"{stem}-report.xlsx"
    result = build_report(str(sorted_path), str(xlsx_path))
    print(f"✓ Excel report ({result['squads']} squads) → {xlsx_path.relative_to(REPO_ROOT)}")

    # Step 5: JSON
    print(f"✓ Building JSON snapshot...")
    json_data = build_json(
        str(sorted_path),
        date,
        config_dir=str(REPO_ROOT / "config"),
        data_dir=str(REPO_ROOT / "data"),
    )

    # Summary
    t = json_data["tribe_totals"]
    print(f"\n{'='*60}")
    print(f"  Tribe totals for {date}:")
    print(f"  Rule-instances: {t['failing_rule_instances']}")
    print(f"  Unique rules:   {t['unique_rules']}")
    print(f"  Entities:       {t['affected_entities']}")
    print(f"  Squads:         {len(json_data['squads'])}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 scripts/run.py <input_csv>")
        sys.exit(1)
    run(sys.argv[1])
```

- [ ] **Step 2: End-to-end test with 2026-06-25 export**

```bash
cd /Users/dawsondai/ai/inv-plat-opex
python3 scripts/run.py snapshots/2026-06-25/maturity-export-2026-06-25.csv
```

Expected:
```
📅 Date: 2026-06-25
  (input already in snapshots, skipping copy)
✓ Sorted CSV (1225 rows) → snapshots/2026-06-25/maturity-export-2026-06-25-sorted-raw.csv
✓ Excel report (17 squads) → snapshots/2026-06-25/maturity-export-2026-06-25-report.xlsx
✓ Building JSON snapshot...
  Written: data/2026-06-25/maturity.json
  Updated: data/index.json → ['2026-06-25']
============================================================
  Tribe totals for 2026-06-25:
  Rule-instances: 1225
  Unique rules:   56
  Entities:       310
  Squads:         17
============================================================
```

- [ ] **Step 3: Backfill 2026-06-20 snapshot**

```bash
cd /Users/dawsondai/ai/inv-plat-opex
python3 scripts/run.py snapshots/2026-06-20/Inventory-platform-maturity-2026-06-20.csv
```

Verify `data/index.json` now contains both dates:
```bash
cat data/index.json
```
Expected: `{"snapshots": ["2026-06-20", "2026-06-25"]}`

- [ ] **Step 4: Commit**

```bash
cd /Users/dawsondai/ai/inv-plat-opex
git add scripts/run.py data/
git commit -m "feat: add run.py entry point, backfill JSON snapshots for 2026-06-20 and 2026-06-25"
```

---

## Task 6: GitHub Pages Site (`docs/`)

**Files:**
- Create: `docs/index.html`
- Create: `docs/app.js`
- Create: `docs/style.css`

**Interfaces:**
- Consumes: `../data/index.json`, `../data/YYYY-MM-DD/maturity.json` (fetched at runtime via `fetch()`)
- Produces: three-tab static site — Trend | Priority Standards | Snapshot Explorer

- [ ] **Step 1: Write docs/style.css**

Write `/Users/dawsondai/ai/inv-plat-opex/docs/style.css`:

```css
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; font-size: 14px; background: #f5f7fa; color: #1a1a2e; }
header { background: #1F4E79; color: #fff; padding: 16px 24px; }
header h1 { font-size: 20px; font-weight: 600; }
header p { font-size: 12px; opacity: 0.75; margin-top: 2px; }
nav { display: flex; gap: 0; border-bottom: 2px solid #1F4E79; background: #fff; padding: 0 24px; }
nav button { padding: 10px 20px; border: none; background: none; cursor: pointer; font-size: 14px; color: #555; border-bottom: 3px solid transparent; margin-bottom: -2px; }
nav button.active { color: #1F4E79; border-bottom-color: #1F4E79; font-weight: 600; }
nav button:hover:not(.active) { background: #f0f4f8; }
main { padding: 24px; max-width: 1400px; }
.tab { display: none; }
.tab.active { display: block; }
h2 { font-size: 16px; font-weight: 600; margin-bottom: 12px; color: #1F4E79; }
h3 { font-size: 14px; font-weight: 600; margin: 20px 0 8px; color: #333; }
.chart-wrap { background: #fff; border-radius: 8px; padding: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); margin-bottom: 24px; }
table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,0.08); margin-bottom: 24px; }
th { background: #1F4E79; color: #fff; padding: 10px 12px; text-align: left; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }
td { padding: 8px 12px; border-bottom: 1px solid #e8edf2; vertical-align: top; }
tr:nth-child(even) td { background: #f0f4f8; }
tr:last-child td { border-bottom: none; }
.pass { color: #217a45; font-weight: 600; }
.fail { color: #c0392b; }
ul.squad-list { list-style: none; padding: 0; margin: 0; }
ul.squad-list li { padding: 1px 0; }
select { padding: 6px 10px; border: 1px solid #ccd; border-radius: 4px; font-size: 13px; }
.meta { font-size: 12px; color: #888; margin-bottom: 16px; }
.squad-section { margin-bottom: 32px; }
a { color: #1F4E79; }
```

- [ ] **Step 2: Write docs/app.js**

Write `/Users/dawsondai/ai/inv-plat-opex/docs/app.js`:

```javascript
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
  d.squads.forEach(squad => {
    const sec = document.createElement('div'); sec.className = 'squad-section'; container.appendChild(sec);
    const h3 = document.createElement('h3');
    h3.innerHTML = `<a href="${squad.cortex_url}" target="_blank">${squad.name}</a> — ${squad.total_failing_rule_instances} rule-instances, ${squad.total_affected_entities} entities`;
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
```

- [ ] **Step 3: Write docs/index.html**

Write `/Users/dawsondai/ai/inv-plat-opex/docs/index.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Inventory Platform — Maturity Gaps</title>
  <link rel="stylesheet" href="style.css">
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
</head>
<body>
<header>
  <h1>Inventory Platform — Baseline Maturity Gaps</h1>
  <p>Track the tribe's progress toward Skyscanner Baseline maturity by end of 2026</p>
</header>
<nav>
  <button class="active" data-tab="tab-trend">Trend</button>
  <button data-tab="tab-compliance">Priority Standards</button>
  <button data-tab="tab-explorer">Snapshot Explorer</button>
</nav>
<main>
  <div id="loading">Loading snapshots…</div>
  <div id="app" style="display:none">
    <div id="tab-trend" class="tab active">
      <div class="chart-wrap"><canvas id="trendChart" height="100"></canvas></div>
      <h2>Tribe Totals Over Time</h2>
      <table id="totalsTrendTable"></table>
    </div>
    <div id="tab-compliance" class="tab">
      <p class="meta" id="complianceDate"></p>
      <h2>Priority Standards Compliance</h2>
      <table id="complianceTable"></table>
    </div>
    <div id="tab-explorer" class="tab">
      <p class="meta">Snapshot: <select id="snapshotSelect"></select></p>
      <div id="snapshotContent"></div>
    </div>
  </div>
</main>
<script src="app.js"></script>
</body>
</html>
```

- [ ] **Step 4: Test locally**

```bash
cd /Users/dawsondai/ai/inv-plat-opex/docs
python3 -m http.server 8765
```

Open `http://localhost:8765` in a browser. Verify:
- Trend tab: line chart with scorecard lines across 2026-06-20 and 2026-06-25
- Priority Standards tab: table with failing squad bullet lists
- Snapshot Explorer: dropdown with both dates, tribe and squad tables render

Kill with `Ctrl+C`.

- [ ] **Step 5: Commit**

```bash
cd /Users/dawsondai/ai/inv-plat-opex
git add docs/index.html docs/app.js docs/style.css
git commit -m "feat: add GitHub Pages site — trend chart, priority standards, snapshot explorer"
```

---

## Task 7: Update `inventory-maturity-report` Skill

**Files:**
- Modify: `~/.claude/skills/inventory-maturity-report/SKILL.md`

- [ ] **Step 1: Overwrite SKILL.md**

Write `~/.claude/skills/inventory-maturity-report/SKILL.md`:

```markdown
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
```

- [ ] **Step 2: Verify**

```bash
head -5 ~/.claude/skills/inventory-maturity-report/SKILL.md
```

Expected: `---` frontmatter start.

---

## Task 8: `opex-confluence-publish` Skill

**Files:**
- Create: `~/.claude/skills/opex-confluence-publish/SKILL.md`

- [ ] **Step 1: Create skill directory**

```bash
mkdir -p ~/.claude/skills/opex-confluence-publish
```

- [ ] **Step 2: Write SKILL.md**

Write `~/.claude/skills/opex-confluence-publish/SKILL.md`:

````markdown
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

- **Space key:** `IP`
- **Page title format:** `Opex-Report-YYYY-MM-DD`
- **Cloud ID:** `skyscanner.atlassian.net`
- **Parent page:** search for a page titled "Opex Reports" in the IP space, or ask the user for the parent page ID

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
<p><em>Date: {snap['date']} | Rule-instances: {snap['tribe_totals']['failing_rule_instances']} | Unique rules: {snap['tribe_totals']['unique_rules']} | Entities: {snap['tribe_totals']['affected_entities']}</em></p>
<table data-layout="full-width">
<tr><th><strong>Scorecard</strong></th><th><strong>Squads Affected</strong></th><th><strong>Failing Rule-instances</strong></th><th><strong>Unique Rules Failing</strong></th><th><strong>Affected Entities</strong></th></tr>
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

For each `squad` in `snap['squads']` sorted by `total_failing_rule_instances` desc:

```html
<h3>{squad['name']} — {squad['total_failing_rule_instances']} rule-instances, {squad['total_affected_entities']} entities</h3>
<table data-layout="full-width">
<tr><th><strong>Scorecard</strong></th><th><strong>Rule</strong></th><th><strong>Failing Entities</strong></th></tr>
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
  cql: title = "Opex-Report-{date}" AND space = "IP" AND type = page
```

- **Found:** call `mcp__plugin_atlassian_atlassian__updateConfluencePage` with the found `pageId`, passing `body` (the HTML) and `contentFormat: "html"`, `title: "Opex-Report-{date}"`
- **Not found:** call `mcp__plugin_atlassian_atlassian__createConfluencePage`:
  - Get `spaceId` from `mcp__plugin_atlassian_atlassian__getConfluenceSpaces` filtering key `IP`
  - Get `parentId` by searching for a page titled "Opex Reports" in IP space, or ask the user
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
````

- [ ] **Step 3: Verify**

```bash
ls ~/.claude/skills/opex-confluence-publish/
```

Expected: `SKILL.md`

---

## Task 9: Git and GitHub Pages Setup

**Files:**
- Commit all remaining files

- [ ] **Step 1: Final commit of all remaining files**

```bash
cd /Users/dawsondai/ai/inv-plat-opex
git add -A
git status
git commit -m "docs: add implementation plan and updated specs"
```

- [ ] **Step 2: Create GitHub repo and push**

```bash
gh repo create skyscanner/inv-plat-opex --private --source=. --remote=origin --push
```

If the repo already exists or you need a different org/name, adjust the command:
```bash
# Alternative: create under your personal account
gh repo create inv-plat-opex --private --source=. --remote=origin --push
```

- [ ] **Step 3: Enable GitHub Pages on docs/ folder**

```bash
gh api repos/{owner}/inv-plat-opex/pages \
  --method POST \
  --field source='{"branch":"main","path":"/docs"}'
```

Replace `{owner}` with `skyscanner` or your GitHub username as appropriate.

Expected: JSON response containing `"html_url"`.

- [ ] **Step 4: Verify Pages site is live**

Wait ~60 seconds, then:
```bash
gh api repos/{owner}/inv-plat-opex/pages --jq '.html_url'
```

Open the URL — the site should show the Trend tab with two data points (2026-06-20, 2026-06-25) and the Priority Standards table.

---

## Self-Review Checklist

**Spec coverage:**
- ✅ `snapshots/` repo structure + migration — Task 1
- ✅ `config/priority-rules.yaml` — Task 1
- ✅ `config/squads.yaml` — Task 1
- ✅ `scripts/sort_csv.py` — Task 2
- ✅ `scripts/build_report.py` — Task 3
- ✅ `scripts/build_json.py` — Task 4 (tribe totals, per-scorecard, per-squad, priority rules, index.json)
- ✅ `scripts/run.py` entry point — Task 5
- ✅ Backfill 2026-06-20 and 2026-06-25 snapshots — Task 5 Step 3
- ✅ GitHub Pages site (Trend, Priority Standards, Snapshot Explorer) — Task 6
- ✅ `inventory-maturity-report` skill updated — Task 7
- ✅ `opex-confluence-publish` skill created — Task 8
- ✅ Git repo + GitHub Pages setup — Task 9

**Type consistency:**
- `build_json.py` writes `squad.cortex_url`, `squad.cortex_tag`, `squad.name`, `squad.total_failing_rule_instances`, `squad.total_affected_entities`, `squad.scorecards[].name`, `squad.scorecards[].rules[].rule`, `squad.scorecards[].rules[].failing_entity_count`
- `app.js` reads the same field names — consistent
- `opex-confluence-publish` SKILL.md references the same field names — consistent
- `tribe_by_scorecard[].squads_affected[].name` and `[].failing_rule_instances` — used in app.js and skill — consistent

**No placeholders found.**
