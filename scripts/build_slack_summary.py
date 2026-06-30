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

import yaml

REPO = Path(__file__).parent.parent
DATA = REPO / "data"
CONFIG = REPO / "config"

# ── Config ────────────────────────────────────────────────────────────────────
owners_cfg = yaml.safe_load((CONFIG / "squad-owners.yaml").read_text())
SQUAD_OWNERS = owners_cfg.get("squad_owners", {})

# Cost icon thresholds (applied to provider % change)
COST_WARNING_PCT   = 20   # ⚠️  >20%  change
COST_YELLOW_PCT    = 5    # 🟡  5–20% change
# Below 5% or negligible spend → 🟢
COST_NEGLIGIBLE    = 1000  # providers under $1k treated as negligible spend
# Squad swing threshold for "stable overall" providers
SQUAD_SWING_ABS    = 5000  # flag squad if |abs_change| > $5,000


def mention(squad_name: str) -> str:
    handles = SQUAD_OWNERS.get(squad_name, [])
    return " " + " ".join(f"@{h}" for h in handles) if handles else ""


def fmt_cost(n: float) -> str:
    return f"${n:,.0f}"


def fmt_change(abs_c: float, pct_c: float) -> str:
    abs_str = f"+{fmt_cost(abs_c)}" if abs_c >= 0 else f"-{fmt_cost(-abs_c)}"
    pct_str = f"+{pct_c:.1f}%" if pct_c >= 0 else f"{pct_c:.1f}%"
    return f"({abs_str}, {pct_str})"


def cost_icon(recent: float, pct_c: float) -> str:
    if recent < COST_NEGLIGIBLE:
        return ":white_circle:"
    if abs(pct_c) >= COST_WARNING_PCT:
        return ":warning:"
    if abs(pct_c) >= COST_YELLOW_PCT:
        return ":large_yellow_circle:"
    return ":white_circle:"


def squad_arrow(abs_c: float) -> str:
    return "↑" if abs_c >= 0 else "↓"


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

prev_idx = dates.index(date) - 1
prev_date = dates[prev_idx] if prev_idx >= 0 else None
prev_snap = json.loads((DATA / prev_date / "maturity.json").read_text()) if prev_date else None

# ── TLDR ──────────────────────────────────────────────────────────────────────
t = snap["tribe_totals"]
pt = prev_snap["tribe_totals"] if prev_snap else None
delta = t["failing_rule_instances"] - pt["failing_rule_instances"] if pt else 0
delta_str = f"+{delta}" if delta > 0 else str(delta)

# Maturity icon: 🔴 if worsened, 🟡 otherwise
maturity_icon = ":red_circle:" if delta > 0 else ":large_yellow_circle:"
maturity_line = (
    f"{maturity_icon} Baseline Maturity: {t['failing_rule_instances']:,} failing rule instances "
    f"across {len(snap['squads'])} squads ({delta_str} vs last week)"
)

# Cost TLDR: tribe total + worst anomaly callout
if cz:
    ct = cz["tribe_total"]
    period = cz["period"]
    cost_period = f"{period['start']} ~ {period['end']}"
    tribe_icon = cost_icon(ct["recent"], ct["pct_change"])
    cost_tldr = f"{tribe_icon} Cost: Tribe {fmt_cost(ct['recent'])} {fmt_change(ct['abs_change'], ct['pct_change'])}"
    # Find worst provider anomaly for inline callout
    worst = max(cz["providers"], key=lambda p: abs(p["pct_change"]) if p["recent"] >= COST_NEGLIGIBLE else 0)
    if abs(worst["pct_change"]) >= COST_WARNING_PCT and worst["recent"] >= COST_NEGLIGIBLE:
        abs_str = f"+{fmt_cost(worst['abs_change'])}" if worst["abs_change"] >= 0 else f"-{fmt_cost(-worst['abs_change'])}"
        cost_tldr += f" — {worst['name']} {abs_str} ({'+' if worst['pct_change'] >= 0 else ''}{worst['pct_change']:.0f}%) :warning: (last 2 weeks)"
    else:
        cost_tldr += " (last 2 weeks)"
else:
    cost_tldr = ":white_circle: Cost: data unavailable — run opex-fetch-cloudzero skill first"

tldr_block = maturity_line + "\n" + cost_tldr

# ── Production Standards ──────────────────────────────────────────────────────
prev_pr = {}
if prev_snap:
    for pr in prev_snap["priority_rules"]:
        prev_pr[pr["label"]] = {sq: v["failing_entity_count"] for sq, v in pr["squad_compliance"].items()}

incident_lines = []
standard_lines = []

for pr in snap["priority_rules"]:
    failing = [
        (sq, v["failing_entity_count"])
        for sq, v in pr["squad_compliance"].items()
        if v["failing_entity_count"] > 0
    ]
    if not failing:
        continue
    failing.sort(key=lambda x: -x[1])
    n = len(failing)

    # Detect worsening: any squad has more failing entities than last week
    prev_counts = prev_pr.get(pr["label"], {})
    worsened = any(count > prev_counts.get(sq, count) for sq, count in failing)

    is_incident = pr["label"] in ("No Live Incidents", "No Stale Incidents")

    if is_incident:
        squads_str = ", ".join(sq for sq, _ in failing)
        incident_lines.append(f":red_circle: *{pr['label']}* — {squads_str} (resolve immediately)")
        continue

    icon = ":red_circle:" if worsened else ":large_yellow_circle:"
    top3 = failing[:3]
    top3_str = ", ".join(f"{sq} [{cnt}]" for sq, cnt in top3)
    worsened_tag = " (worsened)" if worsened else ""
    standard_lines.append(f"{icon} *{pr['label']}* — {n} squad(s) failing{worsened_tag} — {top3_str}")

std_block = "\n".join(incident_lines + standard_lines)

# ── Cost Anomalies ────────────────────────────────────────────────────────────
cost_block_parts = []

if cz:
    # Sort: anomalous first (by abs pct change desc), then stable, then negligible
    def provider_sort_key(p):
        if p["recent"] < COST_NEGLIGIBLE:
            return (2, 0)
        if abs(p["pct_change"]) >= COST_YELLOW_PCT:
            return (0, -abs(p["pct_change"]))
        return (1, 0)

    for p in sorted(cz["providers"], key=provider_sort_key):
        icon = cost_icon(p["recent"], p["pct_change"])
        header = f"{icon} *{p['name']}* {fmt_cost(p['recent'])} {fmt_change(p['abs_change'], p['pct_change'])}"

        squads = [
            s for s in p["squads"]
            if s["name"] and not s["name"].startswith("Service Category")
        ]

        is_negligible = p["recent"] < COST_NEGLIGIBLE
        is_stable = abs(p["pct_change"]) < COST_YELLOW_PCT

        if is_negligible:
            # Just header, no squad breakdown
            cost_block_parts.append(header + " — negligible spend")
            continue

        if is_stable:
            # Show top-3 by abs change only if any squad has a big swing
            big_swings = sorted(
                [s for s in squads if abs(s["abs_change"]) > SQUAD_SWING_ABS],
                key=lambda s: -abs(s["abs_change"])
            )[:3]
            if big_swings:
                header += " — stable overall, but notable squad movement:"
                squad_lines = [
                    f"  {squad_arrow(s['abs_change'])} {s['name']} {fmt_cost(s['recent'])} "
                    f"{fmt_change(s['abs_change'], s['pct_change'])}{mention(s['name'])}"
                    for s in big_swings
                ]
                cost_block_parts.append(header + "\n" + "\n".join(squad_lines))
            else:
                cost_block_parts.append(header)
            continue

        # Anomalous provider — show top 3 by abs change
        top3 = sorted(
            [s for s in squads if s["abs_change"] != 0],
            key=lambda s: -abs(s["abs_change"])
        )[:3]
        squad_lines = [
            f"  {squad_arrow(s['abs_change'])} {s['name']} {fmt_cost(s['recent'])} "
            f"{fmt_change(s['abs_change'], s['pct_change'])}{mention(s['name'])}"
            for s in top3
        ]
        cost_block_parts.append(header + "\n" + "\n".join(squad_lines))

    cost_block = "\n".join(cost_block_parts)
    cost_header = f"*Cost Anomalies — {cost_period}*"
else:
    cost_block = "_Cost data unavailable — run opex-fetch-cloudzero skill first._"
    cost_header = "*Cost*"

# ── Assemble ──────────────────────────────────────────────────────────────────
msg = f"""*Inventory Platform Opex — {date}*

*TLDR*
{tldr_block}

*Production Standards — Action Required*
{std_block}

{cost_header}
{cost_block}"""

print(msg)

out_dir = REPO / "docs" / "data" / date
out_dir.mkdir(parents=True, exist_ok=True)
out_path = out_dir / "slack_summary.md"
out_path.write_text(msg)
print(f"\n--- Written to {out_path.relative_to(REPO)}", file=sys.stderr)
