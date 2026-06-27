"""
Build an Excel maturity report from a sorted Cortex maturity CSV.
Produces: Tribe Overview sheet + one sheet per squad.

NOTE: Input must be the sorted/filtered CSV (output of sort_csv.py).
Passing the raw Cortex export directly may include excluded squads.
"""
import csv
import sys
from collections import defaultdict
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.chart import BarChart, Reference
from openpyxl.utils import get_column_letter

HDR_FILL = PatternFill("solid", fgColor="1F4E79")
HDR_FONT = Font(bold=True, color="FFFFFF")
ALT_FILL = PatternFill("solid", fgColor="D6E4F0")
TOTAL_FILL = PatternFill("solid", fgColor="BDD7EE")
TOTAL_FONT = Font(bold=True)
THIN = Side(style="thin", color="AAAAAA")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def _load(sorted_csv: str):
    with open(sorted_csv, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _hdr(ws, row, col, value):
    c = ws.cell(row=row, column=col, value=value)
    c.font = HDR_FONT
    c.fill = HDR_FILL
    c.alignment = Alignment(horizontal="center", wrap_text=True)
    c.border = BORDER


def _cell(ws, row, col, value, alt=False, bold=False):
    c = ws.cell(row=row, column=col, value=value)
    if alt:
        c.fill = ALT_FILL
    if bold:
        c.font = TOTAL_FONT
        c.fill = TOTAL_FILL
    c.border = BORDER
    c.alignment = Alignment(wrap_text=True)
    return c


def _auto_width(ws, min_w=10, max_w=50):
    for col in ws.columns:
        length = max((len(str(c.value or "")) for c in col), default=min_w)
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(max(length + 2, min_w), max_w)


def build_report(sorted_csv: str, output_xlsx: str) -> dict:
    rows = _load(sorted_csv)
    wb = Workbook()

    # --- aggregate data ---
    # squad → scorecard → rule → {"entities": set, "rows": count}
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {"entities": set(), "rows": 0})))
    for r in rows:
        data[r["Squad"]][r["Scorecard"]][r["Rule"]]["entities"].add(r["Entity"])
        data[r["Squad"]][r["Scorecard"]][r["Rule"]]["rows"] += 1

    squads = sorted(data.keys())

    # --- Tribe Overview sheet ---
    ws = wb.active
    ws.title = "Tribe Overview"
    headers = ["Squad", "Scorecards Failing", "Rules Failing", "Entities Failing", "Rows (rule-instances)"]
    for ci, h in enumerate(headers, 1):
        _hdr(ws, 1, ci, h)

    ri = 2
    total_sc, total_ru, total_en, total_ro = set(), set(), set(), 0
    for squad in squads:
        scorecards = data[squad]
        sc_count = len(scorecards)
        ru_count = sum(len(rules) for rules in scorecards.values())
        en_count = len({e for rules in scorecards.values() for rule_data in rules.values() for e in rule_data["entities"]})
        ro_count = sum(rule_data["rows"] for rules in scorecards.values() for rule_data in rules.values())
        alt = (ri % 2 == 0)
        _cell(ws, ri, 1, squad, alt)
        _cell(ws, ri, 2, sc_count, alt)
        _cell(ws, ri, 3, ru_count, alt)
        _cell(ws, ri, 4, en_count, alt)
        _cell(ws, ri, 5, ro_count, alt)
        total_sc.update(scorecards.keys())
        total_ru.update(r for rules in scorecards.values() for r in rules)
        total_en.update(e for rules in scorecards.values() for rule_data in rules.values() for e in rule_data["entities"])
        total_ro += ro_count
        ri += 1

    # Grand total row
    _cell(ws, ri, 1, "TOTAL", bold=True)
    _cell(ws, ri, 2, len(total_sc), bold=True)
    _cell(ws, ri, 3, len(total_ru), bold=True)
    _cell(ws, ri, 4, len(total_en), bold=True)
    _cell(ws, ri, 5, total_ro, bold=True)

    # Bar chart
    data_rows = len(squads)
    chart = BarChart()
    chart.type = "col"
    chart.grouping = "clustered"
    chart.title = "Failing Rows & Entities per Squad"
    chart.y_axis.title = "Count"
    chart.width = 24
    chart.height = 14
    rows_ref = Reference(ws, min_col=5, min_row=1, max_row=1 + data_rows)
    ents_ref = Reference(ws, min_col=4, min_row=1, max_row=1 + data_rows)
    cats_ref = Reference(ws, min_col=1, min_row=2, max_row=1 + data_rows)
    chart.add_data(rows_ref, titles_from_data=True)
    chart.add_data(ents_ref, titles_from_data=True)
    chart.set_categories(cats_ref)
    ws.add_chart(chart, f"G2")

    _auto_width(ws)

    # --- Per-squad sheets ---
    for squad in squads:
        safe = squad[:28].replace("/", "-").replace("\\", "-").replace("*", "").replace("?", "").replace("[", "").replace("]", "").replace(":", "")
        ws2 = wb.create_sheet(title=safe)
        scorecards = data[squad]

        # KPI strip
        total_rows_sq = sum(rule_data["rows"] for sc in scorecards.values() for rule_data in sc.values())
        total_ents_sq = len({e for sc in scorecards.values() for rule_data in sc.values() for e in rule_data["entities"]})
        total_rules_sq = sum(len(sc) for sc in scorecards.values())
        ws2["A1"] = f"Squad: {squad}"
        ws2["A1"].font = Font(bold=True, size=13)
        ws2["A2"] = f"Total rule-instances: {total_rows_sq}   |   Entities: {total_ents_sq}   |   Unique rules: {total_rules_sq}"
        ws2["A2"].font = Font(italic=True)
        ws2.row_dimensions[1].height = 20

        # Scorecard Summary
        ws2["A4"] = "Scorecard Summary"
        ws2["A4"].font = Font(bold=True, size=11)
        sc_hdrs = ["Scorecard", "Rules Failing", "Entities Failing", "Rows (rule-instances)"]
        for ci, h in enumerate(sc_hdrs, 1):
            _hdr(ws2, 5, ci, h)
        ri2 = 6
        for sc_name, rules in sorted(scorecards.items()):
            ru_c = len(rules)
            en_c = len({e for rule_data in rules.values() for e in rule_data["entities"]})
            ro_c = sum(rule_data["rows"] for rule_data in rules.values())
            alt = (ri2 % 2 == 0)
            _cell(ws2, ri2, 1, sc_name, alt)
            _cell(ws2, ri2, 2, ru_c, alt)
            _cell(ws2, ri2, 3, en_c, alt)
            _cell(ws2, ri2, 4, ro_c, alt)
            ri2 += 1

        # Rule Breakdown
        rb_start = ri2 + 2
        ws2.cell(row=rb_start - 1, column=1, value="Rule Breakdown").font = Font(bold=True, size=11)
        rb_hdrs = ["Scorecard", "Rule", "Entities Failing", "Rows"]
        for ci, h in enumerate(rb_hdrs, 1):
            _hdr(ws2, rb_start, ci, h)
        ri3 = rb_start + 1
        for sc_name, rules in sorted(scorecards.items()):
            for rule, rule_data in sorted(rules.items(), key=lambda x: -len(x[1]["entities"])):
                alt = (ri3 % 2 == 0)
                _cell(ws2, ri3, 1, sc_name, alt)
                _cell(ws2, ri3, 2, rule, alt)
                _cell(ws2, ri3, 3, len(rule_data["entities"]), alt)
                _cell(ws2, ri3, 4, rule_data["rows"], alt)
                ri3 += 1

        # Entity Detail
        ed_start = ri3 + 2
        ws2.cell(row=ed_start - 1, column=1, value="Entity Detail").font = Font(bold=True, size=11)
        ed_hdrs = ["Entity", "Scorecard", "Rule"]
        for ci, h in enumerate(ed_hdrs, 1):
            _hdr(ws2, ed_start, ci, h)
        ri4 = ed_start + 1
        for sc_name, rules in sorted(scorecards.items()):
            for rule, rule_data in sorted(rules.items()):
                for ent in sorted(rule_data["entities"]):
                    alt = (ri4 % 2 == 0)
                    _cell(ws2, ri4, 1, ent, alt)
                    _cell(ws2, ri4, 2, sc_name, alt)
                    _cell(ws2, ri4, 3, rule, alt)
                    ri4 += 1

        _auto_width(ws2)

    wb.save(output_xlsx)
    return {"squads": len(squads), "rows": sum(rule_data["rows"] for sq in data.values() for sc in sq.values() for rule_data in sc.values())}


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: build_report.py <sorted_csv> <output_xlsx>")
        sys.exit(1)
    result = build_report(sys.argv[1], sys.argv[2])
    print(f"Excel report written: {result['squads']} squads, {result['rows']} rows → {sys.argv[2]}")
