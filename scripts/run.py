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
