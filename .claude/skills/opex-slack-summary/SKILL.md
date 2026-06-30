---
name: opex-slack-summary
description: >
  Generates a Slack summary message for the Inventory Platform weekly opex update,
  combining maturity scorecard alerts and CloudZero cost changes. Writes the draft
  to docs/data/YYYY-MM-DD/slack_summary.md and prints it for review.
  Use when the user says "slack summary", "draft slack message", "weekly opex summary",
  "slack update", or "opex Slack draft".
---

# Opex Slack Summary Generator

## What this skill does

Reads the latest `maturity.json` and `cloudzero.json` snapshots and produces a
Slack-ready markdown message covering:

1. **Scorecard alerts** — each scorecard, how many squads are affected, and week-on-week trend
2. **Cost Changes** — tribe total + per-provider summary with direction
3. **Squad Alerts Summary** — brief note pointing to Squad Performance detail
4. **Cost Summary** — per-provider top-3 squads by cost change, with Slack @mentions

## Repo location

`/Users/dawsondai/ai/inv-plat-opex`

## Step-by-step instructions

### Step 1 — Run the script

```bash
python3 scripts/build_slack_summary.py [YYYY-MM-DD]
```

If no date is given, the latest snapshot date from `data/index.json` is used.

The script:
- Reads `data/YYYY-MM-DD/maturity.json` and `data/YYYY-MM-DD/cloudzero.json`
- Compares against the previous snapshot for scorecard deltas
- Reads squad Slack handles from `config/squad-owners.yaml`
- Prints the message to stdout
- Writes it to `docs/data/YYYY-MM-DD/slack_summary.md`

### Step 2 — Read and present the draft

Read the generated file and display its contents to the user:

```bash
cat docs/data/YYYY-MM-DD/slack_summary.md
```

Present it as a draft for the user to review and copy into Slack.

### Step 3 — Offer refinements

After presenting, ask the user if they want any adjustments:
- Add/remove squads from highlights
- Change the threshold for (UP)/(DOWN) trend markers
- Update squad owners in `config/squad-owners.yaml`

## Configuration

**`config/squad-owners.yaml`** — maps squad display names to Slack handles.
Edit this file to keep mentions current. Handles are written without `@`; the
script adds the `@` prefix automatically.

## Output format

```
Scorecard alerts:
- Target: all components at least meet the Baseline maturity

- {scorecard}: {N} squad(s) alerted (avg {X}%, {change})
...

Cost Changes:

The overall cost is ${X} ({+/-$abs}, {+/-pct}%).
The {provider} cost is ${X} ({change}).
...

Squad Alerts Summary ({period})

There are quite a lot, please check the Squad Performance for details

Cost Summary ({period})
{Provider}: ${X} ({change}) Top 3 squads by cost change:
  {Squad}: ${X} ({change}) - @handle
...
```

Trend markers:
- `(UP)` — entity count increased more than 0.5% vs previous snapshot
- `(DOWN)` — entity count decreased more than 0.5% vs previous snapshot
- No marker — stable

## Notes

- Requires both `maturity.json` and `cloudzero.json` for the full message.
  If `cloudzero.json` is missing, the cost sections show a placeholder warning.
- `pyyaml` must be installed (`pip install pyyaml`).
- The script always uses the two most recent snapshots for the delta comparison.
  To compare against a specific date, edit `data/index.json` temporarily or pass
  the target date explicitly.
