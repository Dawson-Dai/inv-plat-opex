"""
Build an Excel maturity report from a sorted Cortex maturity CSV.
Produces: Tribe Overview sheet + one sheet per squad.

NOTE: Input must be the sorted/filtered CSV (output of sort_csv.py).
Passing the raw Cortex export directly may include excluded squads.

Format matches the 2026-06-20 reference report:
  Tribe Overview: title row, per-scorecard pivot matrix, footnote,
                  Tribe Scorecard Summary with % columns, bar chart.
  Squad sheets:   title, KPI strip, Scorecard Summary with % columns,
                  Rule Breakdown with entity names, Entity Detail with
                  Last Evaluated.
"""
import csv
import sys
from collections import defaultdict
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.chart import BarChart, Reference
from openpyxl.utils import get_column_letter

# Colours
DARK_BLUE_FILL = PatternFill("solid", fgColor="1F4E79")
MID_BLUE_FILL  = PatternFill("solid", fgColor="2E75B6")
LIGHT_FILL     = PatternFill("solid", fgColor="D6E4F0")
TOTAL_FILL     = PatternFill("solid", fgColor="BDD7EE")
WHITE_FILL     = PatternFill("solid", fgColor="FFFFFF")

WHITE_BOLD  = Font(bold=True, color="FFFFFF")
DARK_BOLD   = Font(bold=True)
ITALIC_FONT = Font(italic=True, size=9)
TITLE_FONT  = Font(bold=True, size=13)
SECTION_FONT = Font(bold=True, size=11)

THIN = Side(style="thin", color="AAAAAA")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

# Abbreviated scorecard labels (matches 2026-06-20 reference)
SC_ABBREV = {
    "Anyone Can Contribute Safely":        "Contribute Safely",
    "Changes Ship Reliably":               "Ship Reliably",
    "Customer Data Stays Protected":       "Data Protected",
    "Data, AI, and ML Governed":           "AI/ML Governed",
    "Production Observable and Resilient": "Observable",
    "Technology Stays Current":            "Tech Current",
}


def _abbrev(sc_name: str) -> str:
    return SC_ABBREV.get(sc_name, sc_name)


def _hdr(ws, row, col, value, fill=None):
    c = ws.cell(row=row, column=col, value=value)
    c.font = WHITE_BOLD
    c.fill = fill or DARK_BLUE_FILL
    c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    c.border = BORDER
    return c


def _cell(ws, row, col, value, alt=False, bold=False, align="left", wrap=True):
    c = ws.cell(row=row, column=col, value=value)
    if bold:
        c.font = DARK_BOLD
        c.fill = TOTAL_FILL
    elif alt:
        c.fill = LIGHT_FILL
    c.border = BORDER
    c.alignment = Alignment(horizontal=align, vertical="center", wrap_text=wrap)
    return c


def _auto_width(ws, min_w=8, max_w=60):
    for col in ws.columns:
        length = max((len(str(c.value or "")) for c in col), default=min_w)
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(max(length + 2, min_w), max_w)


def _load(sorted_csv: str):
    with open(sorted_csv, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_report(sorted_csv: str, output_xlsx: str) -> dict:
    rows = _load(sorted_csv)
    wb = Workbook()

    # Build data tree: squad → scorecard → rule → {entities: set, rows: int, last_evaluated: {entity: ts}}
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(
        lambda: {"entities": set(), "rows": 0, "last_eval": {}}
    )))
    for r in rows:
        d = data[r["Squad"]][r["Scorecard"]][r["Rule"]]
        d["entities"].add(r["Entity"])
        d["rows"] += 1
        d["last_eval"][r["Entity"]] = r.get("Last Evaluated", "")

    squads = sorted(data.keys())

    # Canonical scorecard order (alphabetical, matches reference)
    all_scorecards = sorted({sc for sq in data.values() for sc in sq})

    # ── Tribe Overview ────────────────────────────────────────────────────
    ws = wb.active
    ws.title = "Tribe Overview"

    # Date from filename — derive from first row's Last Evaluated or use today
    import re
    date_match = re.search(r"\d{4}-\d{2}-\d{2}", sorted_csv)
    report_date = date_match.group() if date_match else "unknown"

    # Row 1: full-width title
    title = f"Inventory Platform  –  Baseline Maturity Failures  |  Tribe Overview  |  {report_date}"
    ws.cell(row=1, column=1, value=title).font = TITLE_FONT
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=3 + len(all_scorecards) * 3)

    # Row 2: scorecard group headers (merged over Rules/Entities/Rows triplets)
    # Col layout: col1=Squad, col2=Entities, then 3 cols per scorecard, then 3 Grand Total cols
    col_squad = 1
    col_entities = 2
    sc_start_cols = {}
    col = 3
    for sc in all_scorecards:
        sc_start_cols[sc] = col
        abbr = _abbrev(sc)
        ws.cell(row=2, column=col, value=abbr).font = WHITE_BOLD
        ws.cell(row=2, column=col).fill = MID_BLUE_FILL
        ws.cell(row=2, column=col).alignment = Alignment(horizontal="center")
        ws.merge_cells(start_row=2, start_column=col, end_row=2, end_column=col + 2)
        col += 3
    gt_col = col  # Grand Total starts here
    ws.cell(row=2, column=gt_col, value="Grand Total").font = WHITE_BOLD
    ws.cell(row=2, column=gt_col).fill = DARK_BLUE_FILL
    ws.cell(row=2, column=gt_col).alignment = Alignment(horizontal="center")
    ws.merge_cells(start_row=2, start_column=gt_col, end_row=2, end_column=gt_col + 2)

    # Row 3: sub-headers
    _hdr(ws, 3, col_squad, "Squad")
    _hdr(ws, 3, col_entities, "Entities")
    for sc in all_scorecards:
        c = sc_start_cols[sc]
        _hdr(ws, 3, c,     "Rules",    fill=MID_BLUE_FILL)
        _hdr(ws, 3, c + 1, "Entities", fill=MID_BLUE_FILL)
        _hdr(ws, 3, c + 2, "Rows",     fill=MID_BLUE_FILL)
    _hdr(ws, 3, gt_col,     "Rules")
    _hdr(ws, 3, gt_col + 1, "Entities")
    _hdr(ws, 3, gt_col + 2, "Rows")

    # Data rows
    ri = 4
    tribe_entities = set()
    tribe_total_rows = 0
    tribe_sc_agg = defaultdict(lambda: {"rules": set(), "entities": set(), "rows": 0})

    for squad in squads:
        alt = (ri % 2 == 0)
        sq_data = data[squad]
        sq_entities = {e for sc in sq_data.values() for rd in sc.values() for e in rd["entities"]}
        sq_rows = sum(rd["rows"] for sc in sq_data.values() for rd in sc.values())
        sq_rules = sum(len(sc) for sc in sq_data.values())

        _cell(ws, ri, col_squad, squad, alt)
        _cell(ws, ri, col_entities, len(sq_entities), alt, align="center")

        for sc in all_scorecards:
            c = sc_start_cols[sc]
            sc_rules = sq_data.get(sc, {})
            ru = len(sc_rules)
            en = len({e for rd in sc_rules.values() for e in rd["entities"]})
            ro = sum(rd["rows"] for rd in sc_rules.values())
            _cell(ws, ri, c,     ru if ru else 0, alt, align="center")
            _cell(ws, ri, c + 1, en if en else 0, alt, align="center")
            _cell(ws, ri, c + 2, ro if ro else 0, alt, align="center")
            if ru:
                tribe_sc_agg[sc]["rules"].update(sc_rules.keys())
                tribe_sc_agg[sc]["entities"].update(e for rd in sc_rules.values() for e in rd["entities"])
                tribe_sc_agg[sc]["rows"] += ro

        _cell(ws, ri, gt_col,     sq_rules,          alt, align="center")
        _cell(ws, ri, gt_col + 1, len(sq_entities),  alt, align="center")
        _cell(ws, ri, gt_col + 2, sq_rows,            alt, align="center")

        tribe_entities.update(sq_entities)
        tribe_total_rows += sq_rows
        ri += 1

    # TOTAL row
    tribe_rules = {r for sc in data.values() for rules in sc.values() for r in rules}
    _cell(ws, ri, col_squad, "TOTAL", bold=True)
    _cell(ws, ri, col_entities, len(tribe_entities), bold=True, align="center")
    for sc in all_scorecards:
        c = sc_start_cols[sc]
        agg = tribe_sc_agg[sc]
        _cell(ws, ri, c,     len(agg["rules"]),    bold=True, align="center")
        _cell(ws, ri, c + 1, len(agg["entities"]), bold=True, align="center")
        _cell(ws, ri, c + 2, agg["rows"],          bold=True, align="center")
    _cell(ws, ri, gt_col,     len(tribe_rules),      bold=True, align="center")
    _cell(ws, ri, gt_col + 1, len(tribe_entities),   bold=True, align="center")
    _cell(ws, ri, gt_col + 2, tribe_total_rows,      bold=True, align="center")

    # Footnote
    footnote_row = ri + 2
    ws.cell(row=footnote_row, column=1,
            value="All entries are Baseline-level Fails.  "
                  "Rules = distinct failing rules;  "
                  "Entities = distinct services/components;  "
                  "Rows = total failing rows.").font = ITALIC_FONT

    # Tribe Scorecard Summary
    tss_row = footnote_row + 2
    ws.cell(row=tss_row, column=1, value="Tribe Scorecard Summary").font = SECTION_FONT
    tss_hdrs = ["Scorecard", "Failing Rules", "Affected Entities",
                "% of Tribe Entities", "Total Rows", "% of Tribe Rows"]
    for ci, h in enumerate(tss_hdrs, 1):
        _hdr(ws, tss_row + 1, ci, h)
    ri2 = tss_row + 2
    for sc in all_scorecards:
        agg = tribe_sc_agg[sc]
        pct_ent = f"{len(agg['entities'])/len(tribe_entities)*100:.1f}%" if tribe_entities else "0.0%"
        pct_row = f"{agg['rows']/tribe_total_rows*100:.1f}%" if tribe_total_rows else "0.0%"
        alt = (ri2 % 2 == 0)
        _cell(ws, ri2, 1, sc, alt)
        _cell(ws, ri2, 2, len(agg["rules"]), alt, align="center")
        _cell(ws, ri2, 3, len(agg["entities"]), alt, align="center")
        _cell(ws, ri2, 4, pct_ent, alt, align="center")
        _cell(ws, ri2, 5, agg["rows"], alt, align="center")
        _cell(ws, ri2, 6, pct_row, alt, align="center")
        ri2 += 1
    # Grand Total row for summary
    _cell(ws, ri2, 1, "Grand Total", bold=True)
    _cell(ws, ri2, 2, len(tribe_rules), bold=True, align="center")
    _cell(ws, ri2, 3, len(tribe_entities), bold=True, align="center")
    _cell(ws, ri2, 4, "100%", bold=True, align="center")
    _cell(ws, ri2, 5, tribe_total_rows, bold=True, align="center")
    _cell(ws, ri2, 6, "100%", bold=True, align="center")

    # Bar chart (Rows & Entities per squad)
    chart = BarChart()
    chart.type = "col"
    chart.grouping = "clustered"
    chart.title = "Failing Rows & Entities per Squad"
    chart.y_axis.title = "Count"
    chart.width = 28
    chart.height = 16
    rows_ref = Reference(ws, min_col=gt_col + 2, min_row=3, max_row=3 + len(squads))
    ents_ref = Reference(ws, min_col=gt_col + 1, min_row=3, max_row=3 + len(squads))
    cats_ref = Reference(ws, min_col=col_squad,   min_row=4, max_row=3 + len(squads))
    chart.add_data(rows_ref, titles_from_data=True)
    chart.add_data(ents_ref, titles_from_data=True)
    chart.set_categories(cats_ref)
    chart_anchor_col = get_column_letter(gt_col + 5)
    ws.add_chart(chart, f"{chart_anchor_col}2")

    _auto_width(ws)
    ws.freeze_panes = "B4"

    # ── Per-squad sheets ──────────────────────────────────────────────────
    for squad in squads:
        safe = (squad[:28]
                .replace("/", "-").replace("\\", "-").replace("*", "")
                .replace("?", "").replace("[", "").replace("]", "").replace(":", ""))
        ws2 = wb.create_sheet(title=safe)
        sq_data = data[squad]

        sq_entities = {e for sc in sq_data.values() for rd in sc.values() for e in rd["entities"]}
        sq_rows = sum(rd["rows"] for sc in sq_data.values() for rd in sc.values())
        sq_rules = sum(len(sc) for sc in sq_data.values())
        sq_scorecards = len(sq_data)

        # Row 1: title
        ws2.cell(row=1, column=1,
                 value=f"Squad: {squad}  –  Baseline Maturity Failures  |  {report_date}").font = TITLE_FONT
        ws2.merge_cells(start_row=1, start_column=1, end_row=1, end_column=6)

        # Row 2: KPI strip
        kpi_hdrs = ["Entities", "Scorecards", "Failing Rules", "Total Rows"]
        kpi_vals = [len(sq_entities), sq_scorecards, sq_rules, sq_rows]
        for ci, (h, v) in enumerate(zip(kpi_hdrs, kpi_vals), 1):
            ws2.cell(row=2, column=ci, value=h).font = WHITE_BOLD
            ws2.cell(row=2, column=ci).fill = DARK_BLUE_FILL
            ws2.cell(row=2, column=ci).alignment = Alignment(horizontal="center")
            ws2.cell(row=3, column=ci, value=v).font = DARK_BOLD
            ws2.cell(row=3, column=ci).alignment = Alignment(horizontal="center")
            ws2.cell(row=3, column=ci).border = BORDER

        # Row 5: Scorecard Summary
        ws2.cell(row=5, column=1, value="Scorecard Summary").font = SECTION_FONT
        sc_hdrs = ["Scorecard", "Failing Rules", "Affected Entities",
                   "% of Squad Entities", "Total Rows", "% of Squad Rows"]
        for ci, h in enumerate(sc_hdrs, 1):
            _hdr(ws2, 6, ci, h)
        ri3 = 7
        for sc in all_scorecards:
            rules = sq_data.get(sc, {})
            ru = len(rules)
            en = len({e for rd in rules.values() for e in rd["entities"]})
            ro = sum(rd["rows"] for rd in rules.values())
            pct_en = f"{en/len(sq_entities)*100:.1f}%" if sq_entities else "0.0%"
            pct_ro = f"{ro/sq_rows*100:.1f}%" if sq_rows else "0.0%"
            abbr = _abbrev(sc)
            alt = (ri3 % 2 == 0)
            _cell(ws2, ri3, 1, abbr, alt)
            _cell(ws2, ri3, 2, ru, alt, align="center")
            _cell(ws2, ri3, 3, en, alt, align="center")
            _cell(ws2, ri3, 4, pct_en, alt, align="center")
            _cell(ws2, ri3, 5, ro, alt, align="center")
            _cell(ws2, ri3, 6, pct_ro, alt, align="center")
            ri3 += 1
        # Total row
        _cell(ws2, ri3, 1, "Total", bold=True)
        _cell(ws2, ri3, 2, sq_rules, bold=True, align="center")
        _cell(ws2, ri3, 3, len(sq_entities), bold=True, align="center")
        _cell(ws2, ri3, 4, "–", bold=True, align="center")
        _cell(ws2, ri3, 5, sq_rows, bold=True, align="center")
        _cell(ws2, ri3, 6, "100%", bold=True, align="center")
        ri3 += 1

        # Rule Breakdown
        rb_row = ri3 + 1
        ws2.cell(row=rb_row, column=1,
                 value="Rule Breakdown  –  distinct rules failing and how many entities are affected"
                 ).font = SECTION_FONT
        rb_hdrs = ["Scorecard", "Rule", "Failing Entities", "% of Squad", "Affected Entities (names)"]
        for ci, h in enumerate(rb_hdrs, 1):
            _hdr(ws2, rb_row + 1, ci, h)
        ri4 = rb_row + 2
        for sc in all_scorecards:
            rules = sq_data.get(sc, {})
            if not rules:
                continue
            abbr = _abbrev(sc)
            for rule, rd in sorted(rules.items(), key=lambda x: -len(x[1]["entities"])):
                en = len(rd["entities"])
                pct = f"{en/len(sq_entities)*100:.1f}%" if sq_entities else "0.0%"
                names = ", ".join(sorted(rd["entities"]))
                alt = (ri4 % 2 == 0)
                _cell(ws2, ri4, 1, abbr, alt)
                _cell(ws2, ri4, 2, rule, alt)
                _cell(ws2, ri4, 3, en, alt, align="center")
                _cell(ws2, ri4, 4, pct, alt, align="center")
                _cell(ws2, ri4, 5, names, alt)
                ri4 += 1

        # Entity Detail
        ed_row = ri4 + 1
        ws2.cell(row=ed_row, column=1,
                 value="Entity Detail  –  every failing rule per entity").font = SECTION_FONT
        ed_hdrs = ["Entity", "Scorecard", "Rule", "Last Evaluated"]
        for ci, h in enumerate(ed_hdrs, 1):
            _hdr(ws2, ed_row + 1, ci, h)
        ri5 = ed_row + 2
        for sc in all_scorecards:
            rules = sq_data.get(sc, {})
            if not rules:
                continue
            abbr = _abbrev(sc)
            for rule, rd in sorted(rules.items()):
                for ent in sorted(rd["entities"]):
                    alt = (ri5 % 2 == 0)
                    _cell(ws2, ri5, 1, ent, alt)
                    _cell(ws2, ri5, 2, abbr, alt)
                    _cell(ws2, ri5, 3, rule, alt)
                    _cell(ws2, ri5, 4, rd["last_eval"].get(ent, ""), alt)
                    ri5 += 1

        _auto_width(ws2)
        ws2.column_dimensions["E"].width = 60  # entity names column — keep wide
        ws2.freeze_panes = "A7"

    wb.save(output_xlsx)
    total_rows = sum(rd["rows"] for sq in data.values() for sc in sq.values() for rd in sc.values())
    return {"squads": len(squads), "rows": total_rows}


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: build_report.py <sorted_csv> <output_xlsx>")
        sys.exit(1)
    result = build_report(sys.argv[1], sys.argv[2])
    print(f"Excel report written: {result['squads']} squads, {result['rows']} rows → {sys.argv[2]}")
