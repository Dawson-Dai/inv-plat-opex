---
name: opex-slack-summary
description: >
  Generates the Inventory Platform weekly opex Slack summary and sends it as a
  DM to Dawson for review before forwarding to the channel. Combines maturity
  scorecard alerts and CloudZero cost anomalies. Use when the user says "slack
  summary", "draft slack message", "weekly opex summary", "slack update", or
  "opex Slack draft".
---

# Opex Slack Summary

## What this skill does

1. Runs `build_slack_summary.py` to generate the message from the latest maturity
   and CloudZero snapshots
2. Sends the message as a Slack DM to Dawson (`dawson.dai@skyscanner.net`) via
   the Slack MCP so he can review it before forwarding to the channel

## Repo location

`/Users/dawsondai/ai/inv-plat-opex`

## Step-by-step instructions

### Step 1 — Build the message

```bash
python3 scripts/build_slack_summary.py [YYYY-MM-DD]
```

If no date is given, uses the latest snapshot. The script:
- Reads `data/YYYY-MM-DD/maturity.json` and `data/YYYY-MM-DD/cloudzero.json`
- Compares against the previous snapshot for week-on-week deltas
- Reads squad Slack handles from `config/squad-owners.yaml`
- Prints the message to stdout
- Writes it to `docs/data/YYYY-MM-DD/slack_summary.txt`

Capture stdout as the message text.

### Step 2 — Send as DM via Slack MCP

Use the Slack MCP to send the message as a direct message to Dawson:

```
slack_post_message:
  channel: "@dawson.dai"   (or Dawson's Slack user ID if known)
  text: {full message text from Step 1}
```

If the Slack MCP requires a channel ID rather than a name, first call:
```
slack_lookup_user_by_email:
  email: dawson.dai@skyscanner.net
```
to get Dawson's user ID, then use that as the channel.

### Step 3 — Confirm and prompt

Tell the user:
- "DM sent — review it in Slack and forward to the channel when ready."
- Offer to regenerate with a different date or adjust any thresholds.

## Configuration

**`config/squad-owners.yaml`** — squad display name → Slack handles (without `@`).
Edit to keep mentions current.

**Thresholds in `scripts/build_slack_summary.py`:**
- `COST_WARNING_PCT = 20` — ⚠️ icon threshold (% change)
- `COST_YELLOW_PCT = 5` — 🟡 icon threshold (% change)
- `COST_NEGLIGIBLE = 1000` — providers below $1k treated as negligible
- `SQUAD_SWING_ABS = 5000` — flag squad under stable provider if |change| > $5k

## Icon rules

| Icon | Meaning |
|---|---|
| 🔴 | Incident rule OR worsened vs last week |
| 🟡 | Stable/improving but still has failures; cost 5–20% change |
| ⚠️ | Cost >20% change on provider with >$1k spend |
| ⚪ | Cost <5% change or negligible spend |
