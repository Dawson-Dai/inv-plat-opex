"""
Build a Slack summary message for the Inventory Platform weekly opex update.

Usage:
    python3 scripts/build_slack_summary.py [YYYY-MM-DD]

    Date defaults to the latest snapshot in data/index.json.

Output:
    Prints the Slack message to stdout.
    Also writes it to docs/data/YYYY-MM-DD/slack_summary.md
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent
DATA = REPO / "data"
CONFIG = REPO / "config"

# ── Load config ───────────────────────────────────────────────────────────────
import yaml
owners_cfg = yaml.safe_load((CONFIG / "squad-owners.yaml").read_text())
SQUAD_OWNERS = owners_cfg.get("squad_owners", {})


def owners_str(squad_name: str) -> str:
    handles = SQUAD_OWNERS.get(squad_name, [])
    if not handles:
        return ""
    return " - " + " / ".join(f"@{h}" for h in handles)


# ── Load snapshots ────────────────────────────────────────────────────────────
index = json.loads((DATA / "index.json").read_text())
dates = index["snapshots"]

if len(sys.argv) > 1:
    date = sys.argv[1]
    if date not in dates:
        print(f"Error: no snapshot for {date}. Available: {dates}", file=sys.stderr)
        sys.exit(1)
else:
    date = dates[-1]

snap = json.loads((DATA / date / "maturity.json").read_text())
cz_path = DATA / date / "cloudzero.json"
cz = json.loads(cz_path.read_text()) if cz_path.exists() else None

# Load previous snapshot for maturity deltas
prev_date = dates[dates.index(date) - 1] if dates.index(date) > 0 else None
prev_snap = json.loads((DATA / prev_date / "maturity.json").read_text()) if prev_date else None


# ── Helpers ───────────────────────────────────────────────────────────────────
def pct(value, total):
    return (value / total * 100) if total else 0


def sign(n):
    return "+" if n >= 0 else ""


def fmt_cost(n):
    return f"${n:,.0f}"


def fmt_change(abs_c, pct_c):
    abs_str = f"+{fmt_cost(abs_c)}" if abs_c >= 0 else f"-{fmt_cost(-abs_c)}"
    pct_str = f"+{pct_c:.1f}%" if pct_c >= 0 else f"{pct_c:.1f}%"
    return f"({abs_str}, {pct_str})"


# ── Section 1: Scorecard alerts ───────────────────────────────────────────────
# Build scorecard → total entities per scorecard (tribe-level)
# "alerted" = squads with ≥1 failing rule for that scorecard
# "avg %" = average compliance rate across failing squads (entities failing / total entities)
# We approximate compliance rate as: failing_entities / total tribe entities * 100

# tribe_by_scorecard gives us squads_affected and counts
# For the alert format: sort by failing_rule_instances desc, show top ones

sc_lines = []
prev_sc = {}
if prev_snap:
    prev_sc = {sc["scorecard"]: sc for sc in prev_snap["tribe_by_scorecard"]}

for sc in snap["tribe_by_scorecard"]:
    name = sc["scorecard"]
    affected = sc["squads_affected"]
    n_squads = len(affected)
    # avg "alert rate" = avg of (failing_rule_instances / squad entity count) across affected squads
    # Simpler proxy: failing_rule_instances / affected_entities as a % of all entities
    total_entities = sc["affected_entities"]
    total_rows = sc["failing_rule_instances"]
    # Use failing entity % as alert severity proxy
    psc = prev_sc.get(name)
    delta_entities = sc["affected_entities"] - psc["affected_entities"] if psc else 0

    pct_val = pct(sc["affected_entities"], snap["tribe_totals"]["affected_entities"]) if snap["tribe_totals"]["affected_entities"] else 0
    prev_pct = pct(psc["affected_entities"], prev_snap["tribe_totals"]["affected_entities"]) if (psc and prev_snap) else None

    if prev_pct is not None:
        delta_pct = pct_val - prev_pct
        change_str = f"no change" if abs(delta_pct) < 0.1 else f"change: {sign(delta_pct)}{delta_pct:.2f}%"
        trend = "(DOWN) " if delta_pct < -0.5 else ("(UP) " if delta_pct > 0.5 else "")
    else:
        change_str = "no prior data"
        trend = ""

    sc_lines.append(
        f"{trend}{name}: {n_squads} squad(s) alerted "
        f"(avg {pct_val:.0f}%, {change_str})"
    )

# ── Section 2: Cost summary ───────────────────────────────────────────────────
cost_section = ""
cost_detail = ""

if cz:
    t = cz["tribe_total"]
    period = cz["period"]
    cost_period = f"{period['start']} ~ {period['end']}"

    # Overall + per-provider summary
    cost_lines = [
        f"The overall cost is {fmt_cost(t['recent'])} {fmt_change(t['abs_change'], t['pct_change'])}."
    ]
    for p in cz["providers"]:
        cost_lines.append(
            f"The {p['name']} cost is {fmt_cost(p['recent'])} {fmt_change(p['abs_change'], p['pct_change'])}."
        )
    cost_section = "\n".join(cost_lines)

    # Per-provider top-3 squad breakdown
    detail_parts = [f"Cost Summary ({cost_period})"]
    for p in cz["providers"]:
        top3 = sorted(
            [s for s in p["squads"] if s["name"] and not s["name"].startswith("Service Category")
             and s["abs_change"] != 0],
            key=lambda s: -abs(s["abs_change"])
        )[:3]
        if not top3:
            continue
        detail_parts.append(
            f"{p['name']}: {fmt_cost(p['recent'])} {fmt_change(p['abs_change'], p['pct_change'])} "
            f"Top 3 squads by cost change:"
        )
        for s in top3:
            ow = owners_str(s["name"])
            detail_parts.append(
                f"  {s['name']}: {fmt_cost(s['recent'])} {fmt_change(s['abs_change'], s['pct_change'])}{ow}"
            )
    cost_detail = "\n".join(detail_parts)
else:
    cost_section = "_Cost data unavailable — run opex-fetch-cloudzero skill first._"
    cost_detail = ""

# ── Assemble message ──────────────────────────────────────────────────────────
sc_block = "\n".join(f"- {line}" for line in sc_lines)
squad_period = f"{cz['period']['start']} ~ {cz['period']['end']}" if cz else date

msg = f"""Scorecard alerts:
- Target: all components at least meet the Baseline maturity

{sc_block}

Cost Changes:

{cost_section}

Squad Alerts Summary ({squad_period})

There are quite a lot, please check the Squad Performance for details

{cost_detail}"""

print(msg)

# Write to docs/data/YYYY-MM-DD/
out_dir = REPO / "docs" / "data" / date
out_dir.mkdir(parents=True, exist_ok=True)
out_path = out_dir / "slack_summary.md"
out_path.write_text(msg)
print(f"\n--- Written to {out_path.relative_to(REPO)}", file=sys.stderr)
