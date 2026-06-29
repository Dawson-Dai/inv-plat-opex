"""
Fetch CloudZero cost data for the Inventory Platform tribe and write
data/YYYY-MM-DD/cloudzero.json alongside the maturity snapshot.

Usage:
    python3 scripts/fetch_cloudzero.py [YYYY-MM-DD]

    If date is omitted, uses the latest snapshot date from data/index.json.

Requires:
    CLOUDZERO_API_TOKEN environment variable (or .env file in repo root)

Output schema (data/YYYY-MM-DD/cloudzero.json):
    {
      "date": "2026-06-25",
      "fetched_at": "2026-06-29T10:00:00Z",
      "period": {"start": "...", "end": "...", "lookback_days": 14},
      "tribe_total": {"recent": 0, "old": 0, "abs_change": 0, "pct_change": 0},
      "providers": [
        {
          "name": "AWS",
          "recent": 0, "old": 0, "abs_change": 0, "pct_change": 0,
          "squads": [
            {
              "name": "Halo",
              "recent": 0, "old": 0, "abs_change": 0, "pct_change": 0,
              "tier": 2, "anomaly": true
            }
          ]
        }
      ]
    }
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode, quote

import requests
import yaml

REPO_ROOT = Path(__file__).parent.parent
CONFIG_DIR = REPO_ROOT / "config"
DATA_DIR = REPO_ROOT / "data"

API_BASE = "https://api.cloudzero.com"
TRIBE_NAME = "Inventory Platform"
LOOKBACK_DAYS = 14
DATA_DELAY_DAYS = 2
API_TIMEOUT = 30


def _load_tiers() -> list[dict]:
    path = CONFIG_DIR / "cost-thresholds.yaml"
    with open(path) as f:
        return yaml.safe_load(f)["tiers"]


def _get_tier(cost: float, tiers: list[dict]) -> dict:
    for tier in tiers:
        if cost < tier["max_cost"]:
            return tier
    return tiers[-1]


def _is_anomaly(abs_change: float, pct_change: float, tier: dict) -> bool:
    return abs(abs_change) > tier["abs_threshold"] or abs(pct_change) > tier["pct_threshold"]


def _fetch(token: str, start_date: str, end_date: str, group_by: str, filters: dict) -> dict:
    params = {
        "start_date": start_date,
        "end_date": end_date,
        "granularity": "daily",
        "group_by": group_by,
        "cost_type": "real_cost",
        "filters": json.dumps(filters, separators=(",", ":")),
    }
    query_string = urlencode(params, quote_via=quote)
    url = f"{API_BASE}/v2/billing/costs?{query_string}"
    resp = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=API_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def _period_costs(entries: list[dict], dim_key: str, lookback: int) -> dict[str, tuple]:
    """
    Split daily entries into two equal periods and return per-dimension cost tuples.
    Returns {name: (old_cost, recent_cost, abs_change, pct_change)}
    """
    by_dim: dict[str, dict[str, float]] = {}
    for entry in entries:
        name = entry.get(dim_key)
        date = entry.get("usage_date", "")[:10]  # trim ISO timestamp to YYYY-MM-DD
        cost = float(entry.get("cost", 0.0))
        if name not in by_dim:
            by_dim[name] = {}
        by_dim[name][date] = by_dim[name].get(date, 0.0) + cost

    results = {}
    for name, date_costs in by_dim.items():
        sorted_dates = sorted(date_costs)
        old_dates = sorted_dates[:lookback]
        recent_dates = sorted_dates[-lookback:]
        old = sum(date_costs[d] for d in old_dates)
        recent = sum(date_costs[d] for d in recent_dates)
        abs_change = recent - old
        pct_change = (abs_change / old * 100) if old > 0 else 0.0
        results[name] = (old, recent, abs_change, pct_change)
    return results


def fetch_cloudzero(date: str) -> None:
    token = os.environ.get("CLOUDZERO_API_TOKEN", "").strip()
    if not token:
        print("Error: CLOUDZERO_API_TOKEN is not set.")
        sys.exit(1)

    tiers = _load_tiers()

    # Date window: 2*lookback days ending at today-DATA_DELAY_DAYS
    now = datetime.now(timezone.utc)
    end_dt = now - timedelta(days=DATA_DELAY_DAYS)
    start_dt = end_dt - timedelta(days=LOOKBACK_DAYS * 2)
    start_str = start_dt.strftime("%Y-%m-%d")
    end_str = end_dt.strftime("%Y-%m-%d")

    print(f"  Fetching cost data {start_str} → {end_str}")

    # Request 1: tribe totals by provider
    tribe_resp = _fetch(
        token, start_str, end_str,
        group_by="CloudProvider",
        filters={"User:Defined:Tribe": [TRIBE_NAME]},
    )
    provider_costs = _period_costs(tribe_resp.get("costs", []), "CloudProvider", LOOKBACK_DAYS)
    print(f"  Providers found: {list(provider_costs)}")

    # Tribe total — sum across all providers
    tribe_old = sum(v[0] for v in provider_costs.values())
    tribe_recent = sum(v[1] for v in provider_costs.values())
    tribe_abs = tribe_recent - tribe_old
    tribe_pct = (tribe_abs / tribe_old * 100) if tribe_old > 0 else 0.0

    # Request 2+: per-provider squad breakdown
    providers_out = []
    for provider, (p_old, p_recent, p_abs, p_pct) in sorted(provider_costs.items(), key=lambda x: -x[1][1]):
        print(f"  Fetching squads for {provider}...")
        squad_resp = _fetch(
            token, start_str, end_str,
            group_by="User:Defined:Squad",
            filters={"User:Defined:Tribe": [TRIBE_NAME], "CloudProvider": [provider]},
        )
        squad_costs = _period_costs(squad_resp.get("costs", []), "User:Defined:Squad", LOOKBACK_DAYS)

        squads_out = []
        for squad_name, (s_old, s_recent, s_abs, s_pct) in sorted(squad_costs.items(), key=lambda x: -x[1][1]):
            if not squad_name:
                continue
            tier = _get_tier(s_recent, tiers)
            squads_out.append({
                "name": squad_name,
                "recent": round(s_recent, 2),
                "old": round(s_old, 2),
                "abs_change": round(s_abs, 2),
                "pct_change": round(s_pct, 1),
                "tier": tier["tier"],
                "anomaly": _is_anomaly(s_abs, s_pct, tier),
            })

        providers_out.append({
            "name": provider,
            "recent": round(p_recent, 2),
            "old": round(p_old, 2),
            "abs_change": round(p_abs, 2),
            "pct_change": round(p_pct, 1),
            "squads": squads_out,
        })

    result = {
        "date": date,
        "fetched_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "period": {"start": start_str, "end": end_str, "lookback_days": LOOKBACK_DAYS},
        "tribe_total": {
            "recent": round(tribe_recent, 2),
            "old": round(tribe_old, 2),
            "abs_change": round(tribe_abs, 2),
            "pct_change": round(tribe_pct, 1),
        },
        "providers": providers_out,
    }

    out_dir = DATA_DIR / date
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "cloudzero.json"
    out_path.write_text(json.dumps(result, indent=2))

    anomaly_count = sum(s["anomaly"] for p in providers_out for s in p["squads"])
    print(f"  Written: {out_path.relative_to(REPO_ROOT)}")
    print(f"  Tribe total (recent 14d): ${tribe_recent:,.0f} ({tribe_abs:+,.0f} / {tribe_pct:+.1f}%)")
    print(f"  Anomalous squads: {anomaly_count}")


if __name__ == "__main__":
    # Load .env from repo root if present
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

    if len(sys.argv) > 1:
        date_arg = sys.argv[1]
    else:
        index = json.loads((DATA_DIR / "index.json").read_text())
        date_arg = index["snapshots"][-1]
        print(f"  Using latest snapshot date: {date_arg}")

    print(f"\nFetching CloudZero cost data for {date_arg}...")
    fetch_cloudzero(date_arg)
    print("Done.\n")
