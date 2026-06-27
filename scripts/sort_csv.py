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
