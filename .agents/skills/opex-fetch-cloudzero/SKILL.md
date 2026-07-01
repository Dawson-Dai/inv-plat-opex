---
name: opex-fetch-cloudzero
description: >
  Fetches CloudZero cost data for the Inventory Platform tribe, analyses period-over-period
  changes with tier-based anomaly detection, and writes data/YYYY-MM-DD/cloudzero.json.
  Run this before publishing the Opex Report when cost data is missing or stale.
  Use when the user says "fetch cloudzero", "refresh cost data", "cloudzero costs",
  "cost data missing", or when the Confluence report shows the cost data unavailable warning.
---

# CloudZero Cost Fetcher

## What this skill does

Calls the CloudZero billing API, computes 14-day period-over-period cost changes per squad
per cloud provider, and writes a structured `cloudzero.json` snapshot into the same
`data/YYYY-MM-DD/` folder as the maturity snapshot.

The `opex-confluence-publish` skill reads this file when building the Confluence page.
If this file is absent, that skill renders a warning panel instead.

## Repo location

`/Users/dawsondai/ai/inv-plat-opex`

## Requires

`CLOUDZERO_API_TOKEN` must be set as an environment variable (or in a `.env` file at
the repo root). If absent, the script exits with a clear error.

## Step-by-step instructions

### Step 1 — Determine target date

```bash
python3 -c "
import json
from pathlib import Path
index = json.loads(Path('data/index.json').read_text())
print(index['snapshots'][-1])
"
```

Use the printed date as `{date}`. If the user specified a date explicitly, use that instead.

### Step 2 — Run the fetch script

```bash
python3 scripts/fetch_cloudzero.py {date}
```

The script:
- Calls `GET https://api.cloudzero.com/v2/billing/costs` with `Authorization: Bearer $CLOUDZERO_API_TOKEN`
- Fetches 28 days of daily data (14-day window × 2 periods) ending 2 days ago (data delay)
- Makes 2+ requests: tribe totals by CloudProvider, then per-squad breakdown per provider
- Computes `(old_14d, recent_14d, abs_change, pct_change)` per squad
- Applies tier-based anomaly thresholds from `config/cost-thresholds.yaml`
- Writes `data/{date}/cloudzero.json`

### Step 3 — Verify output

```bash
python3 -c "
import json
from pathlib import Path
snap = json.loads(Path('data/{date}/cloudzero.json').read_text())
t = snap['tribe_total']
anomalies = [(s['name'], p['name']) for p in snap['providers'] for s in p['squads'] if s['anomaly']]
print('Period:', snap['period']['start'], '->', snap['period']['end'])
print(f'Tribe total: \${t[\"recent\"]:,.0f} ({t[\"abs_change\"]:+,.0f} / {t[\"pct_change\"]:+.1f}%)')
print(f'Anomalous squads ({len(anomalies)}):', anomalies)
"
```

### Step 4 — Report back

Print:
- Date and period fetched
- Tribe total cost and change
- Count of anomalous squads (and their names)
- Path written: `data/{date}/cloudzero.json`
- Prompt: "Run 'publish opex report' to include this in the Confluence page."

## Error handling

| Situation | Action |
|---|---|
| `CLOUDZERO_API_TOKEN` not set | Script exits with error — ask user to set it |
| API returns 401/403 | Token is invalid or expired — report the HTTP error, do not retry |
| API returns 5xx / timeout | Report the error — user can re-run the skill to retry |
| No cost data returned for a provider | That provider is omitted from output silently |
| `data/{date}/` does not exist | Script creates it; if `{date}` has no maturity snapshot, warn the user |

## Output schema (`data/YYYY-MM-DD/cloudzero.json`)

```json
{
  "date": "2026-06-25",
  "fetched_at": "2026-06-29T10:00:00Z",
  "period": {"start": "2026-05-28", "end": "2026-06-25", "lookback_days": 14},
  "tribe_total": {"recent": 45230.00, "old": 41800.00, "abs_change": 3430.00, "pct_change": 8.2},
  "providers": [
    {
      "name": "AWS",
      "recent": 38000.00, "old": 35000.00, "abs_change": 3000.00, "pct_change": 8.6,
      "squads": [
        {
          "name": "Dancing Penguins",
          "recent": 5200.00, "old": 4100.00,
          "abs_change": 1100.00, "pct_change": 26.8,
          "tier": 3, "anomaly": true
        }
      ]
    }
  ]
}
```

## Anomaly thresholds (`config/cost-thresholds.yaml`)

| Tier | Squad 14d spend | Abs threshold | % threshold |
|------|----------------|---------------|-------------|
| 1 | < $1,000 | $100 | 20% |
| 2 | $1,000 – $4,999 | $500 | 15% |
| 3 | $5,000 – $19,999 | $1,000 | 10% |
| 4 | ≥ $20,000 | $2,000 | 10% |

A squad is flagged if `|abs_change| > abs_threshold` **OR** `|pct_change| > pct_threshold`.
