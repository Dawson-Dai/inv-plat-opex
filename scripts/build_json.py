"""
Generate data/YYYY-MM-DD/maturity.json from a sorted maturity CSV.
Also updates data/index.json manifest.
"""
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
import yaml

EXCLUDED_SQUADS = {"astral-squad", "bamboo-squad", "Astral", "Bamboo", "Astral Squad", "Bamboo Squad"}
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
