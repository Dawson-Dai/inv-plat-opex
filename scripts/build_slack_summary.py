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


def mention(squad_name: str) -> str:
    handles = SQUAD_OWNERS.get(squad_name, [])
    return " " + " ".join(f"@{h}" for h in handles) if handles else ""


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


# ── Helpers ───────────────────────────────────────────────────────────────────
def fmt_cost(n):
    return f"${n:,.0f}"


def fmt_change(abs_c, pct_c):
    abs_str = f"+{fmt_cost(abs_c)}" if abs_c >= 0 else f"-{fmt_cost(-abs_c)}"
    pct_str = f"+{pct_c:.1f}%" if pct_c >= 0 else f"{pct_c:.1f}%"
    return f"({abs_str}, {pct_str})"


# ── TLDR ──────────────────────────────────────────────────────────────────────
t = snap["tribe_totals"]
pt = prev_snap["tribe_totals"] if prev_snap else None

maturity_delta = t["failing_rule_instances"] - pt["failing_rule_instances"] if pt else 0
maturity_delta_str = f"+{maturity_delta}" if maturity_delta > 0 else str(maturity_delta)

# Find worst cost anomaly for TLDR callout
cost_tldr = ""
if cz:
    ct = cz["tribe_total"]
    cost_tldr = f"Tribe cost {fmt_cost(ct['recent'])} ({'+' if ct['pct_change'] >= 0 else ''}{ct['pct_change']:.1f}%)"
    # Flag any provider anomaly >20%
    anomaly_flags = [
        f"{p['name']} +{p['pct_change']:.0f}% ⚠️"
        for p in cz["providers"]
        if p["pct_change"] > 20
    ]
    if anomaly_flags:
        cost_tldr += " — " + ", ".join(anomaly_flags)

tldr_lines = [
    f"• Maturity: {t['failing_rule_instances']} failing rule instances across {len(snap['squads'])} squads "
    f"({maturity_delta_str} vs last week)",
]
if cost_tldr:
    tldr_lines.append(f"• Cost: {cost_tldr}")

# ── Production Standards ──────────────────────────────────────────────────────
# Use priority_rules (already the highest-priority standards)
# 🔴 = worsened vs last week (more failing entities), 🟡 = stable/improved

prev_pr_compliance = {}
if prev_snap:
    for pr in prev_snap["priority_rules"]:
        prev_pr_compliance[pr["label"]] = {
            sq: v["failing_entity_count"]
            for sq, v in pr["squad_compliance"].items()
        }

std_lines = []
incident_squads = []

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

    # Detect worsening: any squad's count increased vs last week
    prev_counts = prev_pr_compliance.get(pr["label"], {})
    worsened = any(
        count > prev_counts.get(sq, count)  # count > prev means worse
        for sq, count in failing
    )
    icon = "🔴" if worsened else "🟡"

    # For live/stale incidents, surface squad names directly
    if pr["label"] in ("No Live Incidents", "No Stale Incidents"):
        squads_str = ", ".join(sq for sq, _ in failing)
        incident_squads.append(f"{icon} *{pr['label']}* — {squads_str} (resolve immediately)")
        continue

    # Top 3 worst squads with @mentions
    top3 = failing[:3]
    top3_str = " | ".join(
        f"{sq} [{cnt}]{mention(sq)}" for sq, cnt in top3
    )
    suffix = f" (+{n - 3} more)" if n > 3 else ""
    std_lines.append(f"{icon} *{pr['label']}* — {n} squad(s) failing\n  Worst: {top3_str}{suffix}")

# Prepend incident lines (most urgent)
all_std_lines = incident_squads + std_lines

# Add incident TLDR if any
if incident_squads:
    tldr_lines.append(f"• ⚠️ Live/stale incidents open — immediate action required")

# ── Cost Anomalies ────────────────────────────────────────────────────────────
cost_lines = []
if cz:
    period = cz["period"]
    cost_period = f"{period['start']} ~ {period['end']}"

    for p in cz["providers"]:
        # Only surface providers with significant spend (>$1k) AND notable change (>10%)
        if p["recent"] < 1000 or abs(p["pct_change"]) < 10:
            continue

        icon = "⚠️" if p["pct_change"] > 20 else "🟡"
        header = (
            f"{icon} *{p['name']}* {fmt_cost(p['recent'])} "
            f"{fmt_change(p['abs_change'], p['pct_change'])} — top contributors:"
        )

        top3 = sorted(
            [s for s in p["squads"]
             if s["name"] and not s["name"].startswith("Service Category") and s["abs_change"] != 0],
            key=lambda s: -abs(s["abs_change"])
        )[:3]

        squad_lines = [
            f"  {s['name']} {fmt_cost(s['recent'])} {fmt_change(s['abs_change'], s['pct_change'])}{mention(s['name'])}"
            for s in top3
        ]
        cost_lines.append(header + "\n" + "\n".join(squad_lines))

    # One-liner for stable providers
    stable = [
        f"{p['name']} {fmt_change(p['abs_change'], p['pct_change'])}"
        for p in cz["providers"]
        if not (p["recent"] >= 1000 and abs(p["pct_change"]) >= 10)
    ]
    if stable:
        cost_lines.append("✅ Stable: " + " | ".join(stable))

# ── Assemble ──────────────────────────────────────────────────────────────────
sep = "\n━━━━━━━━━━━━━━━━━━━━━━━━"

parts = [f"*Inventory Platform Opex — {date}*"]
parts.append(f"{sep}\n*TLDR*\n" + "\n".join(tldr_lines))

if all_std_lines:
    parts.append(f"{sep}\n*Production Standards — Action Required*\n\n" + "\n\n".join(all_std_lines))

if cost_lines:
    label = f"Cost Anomalies — {cost_period}" if cz else "Cost Anomalies"
    parts.append(f"{sep}\n*{label}*\n\n" + "\n\n".join(cost_lines))
elif cz:
    parts.append(f"{sep}\n✅ *Cost* — no anomalies this period")
else:
    parts.append(f"{sep}\n_Cost data unavailable — run opex-fetch-cloudzero skill first._")

msg = "\n".join(parts)

print(msg)

out_dir = REPO / "docs" / "data" / date
out_dir.mkdir(parents=True, exist_ok=True)
out_path = out_dir / "slack_summary.md"
out_path.write_text(msg)
print(f"\n--- Written to {out_path.relative_to(REPO)}", file=sys.stderr)
