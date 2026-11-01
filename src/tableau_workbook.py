"""Build tableau/supply_chain_late_deliveries.xlsx (one tidy, small sheet per chart).

Rates are stored as numbers from 0 to 100 (57.3 means 57.3%), so no calculated
fields are needed in Tableau Public web authoring. Every sheet has one row per
mark. Also writes the same tables as CSV to exports/.
"""
import pathlib

import duckdb
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "tableau" / "supply_chain_late_deliveries.xlsx"
EXPORTS = ROOT / "exports"
STATUS = "CASE WHEN is_cancelled THEN 'Cancelled' WHEN is_late THEN 'Late' ELSE 'On time or early' END"

SHEETS = {
    "kpis": """
        WITH k AS (
            SELECT count(*) AS lines,
                   count(*) FILTER (WHERE NOT is_cancelled) AS shipped,
                   count(*) FILTER (WHERE is_late) AS late,
                   count(*) FILTER (WHERE is_cancelled) AS cancelled,
                   sum(profit) AS profit,
                   sum(profit) FILTER (WHERE is_late OR is_cancelled) AS at_risk,
                   avg(days_scheduled) FILTER (WHERE NOT is_cancelled) AS sched,
                   avg(days_actual) FILTER (WHERE NOT is_cancelled) AS act
            FROM fact_order_lines),
        f AS (SELECT
                max(wape_pct) FILTER (WHERE model LIKE 'ETS, AICc%') AS ets,
                max(wape_pct) FILTER (WHERE model LIKE 'Seasonal naive%') AS snaive
              FROM forecast_accuracy WHERE series = 'All categories')
        SELECT * FROM (
          SELECT 1 AS "Sort", 'Order lines' AS "KPI", lines::DOUBLE AS "Value", format('{:,}', lines) AS "Value label" FROM k
          UNION ALL SELECT 2, 'Late (% of shipped lines)', round(100.0 * late / shipped, 1), printf('%.1f%%', 100.0 * late / shipped) FROM k
          UNION ALL SELECT 3, 'Avg days: promised vs actual', round(act - sched, 2), printf('%.1f vs %.1f', sched, act) FROM k
          UNION ALL SELECT 4, 'Cancelled lines', cancelled, format('{:,}', cancelled) FROM k
          UNION ALL SELECT 5, 'Profit (USD)', round(profit, 0), printf('$%.2fM', profit / 1e6) FROM k
          UNION ALL SELECT 6, 'Profit at risk (late + cancelled)', round(100.0 * at_risk / profit, 1),
                           printf('$%.2fM (%.0f%%)', at_risk / 1e6, 100.0 * at_risk / profit) FROM k
          UNION ALL SELECT 7, 'Forecast WAPE: ETS vs seasonal naive', ets, printf('%.1f%% vs %.1f%%', ets, snaive) FROM f
        ) ORDER BY 1""",
    "late_by_mode": """
        SELECT sm.shipping_mode AS "Shipping mode", sm.shipping_mode_key AS "Mode order",
               sm.promised_days AS "Promised days",
               round(avg(days_actual) FILTER (WHERE NOT is_cancelled), 2) AS "Avg actual days",
               count(*) FILTER (WHERE NOT is_cancelled) AS "Shipped lines",
               count(*) FILTER (WHERE is_late) AS "Late lines",
               round(100.0 * count(*) FILTER (WHERE is_late) / count(*) FILTER (WHERE NOT is_cancelled), 1) AS "Late %",
               round(100.0 * count(*) FILTER (WHERE is_on_time) / count(*) FILTER (WHERE NOT is_cancelled), 1) AS "On time %",
               round(100.0 * count(*) FILTER (WHERE is_late) / sum(count(*) FILTER (WHERE is_late)) OVER (), 1) AS "Share of all late %"
        FROM fact_order_lines JOIN dim_shipping_mode sm USING (shipping_mode_key)
        GROUP BY ALL ORDER BY 2""",
    "late_by_market": """
        SELECT m.market AS "Market",
               count(*) FILTER (WHERE NOT is_cancelled) AS "Shipped lines",
               count(*) FILTER (WHERE is_late) AS "Late lines",
               round(100.0 * count(*) FILTER (WHERE is_late) / count(*) FILTER (WHERE NOT is_cancelled), 1) AS "Late %",
               round(sum(profit), 0) AS "Profit",
               round(sum(profit) FILTER (WHERE is_late), 0) AS "Late profit"
        FROM fact_order_lines JOIN dim_market m USING (market_key)
        GROUP BY 1 ORDER BY 4 DESC""",
    "late_by_region": """
        SELECT m.market AS "Market", m.order_region AS "Region",
               count(*) FILTER (WHERE NOT is_cancelled) AS "Shipped lines",
               round(100.0 * count(*) FILTER (WHERE is_late) / count(*) FILTER (WHERE NOT is_cancelled), 1) AS "Late %"
        FROM fact_order_lines JOIN dim_market m USING (market_key)
        GROUP BY 1, 2 ORDER BY 4 DESC""",
    "late_by_category": """
        SELECT p.category_name AS "Category", p.department_name AS "Department",
               count(*) FILTER (WHERE NOT is_cancelled) AS "Shipped lines",
               round(100.0 * count(*) FILTER (WHERE is_late) / count(*) FILTER (WHERE NOT is_cancelled), 1) AS "Late %",
               CASE WHEN count(*) FILTER (WHERE NOT is_cancelled) >= 1000 THEN 'Yes' ELSE 'No' END AS "1,000+ lines"
        FROM fact_order_lines JOIN dim_product p USING (product_key)
        GROUP BY 1, 2 ORDER BY 3 DESC""",
    "schedule_vs_actual": """
        SELECT shipping_mode AS "Shipping mode", promised_days AS "Promised days", days_actual AS "Actual days",
               days_actual::VARCHAR || ' d' AS "Actual days label",
               CASE WHEN is_late THEN 'Late' ELSE 'Within promise' END AS "Outcome",
               lines AS "Shipped lines", share_of_mode_pct AS "Share of mode %"
        FROM mart_schedule_vs_actual ORDER BY promised_days, days_actual""",
    "profit_at_risk": f"""
        SELECT {STATUS} AS "Delivery outcome",
               CASE {STATUS} WHEN 'On time or early' THEN 1 WHEN 'Late' THEN 2 ELSE 3 END AS "Outcome order",
               count(*) AS "Order lines", round(sum(net_sales), 0) AS "Net sales", round(sum(profit), 0) AS "Profit",
               round(100.0 * sum(profit) / sum(sum(profit)) OVER (), 1) AS "Share of profit %",
               round(100.0 * sum(profit) / sum(net_sales), 2) AS "Margin %"
        FROM fact_order_lines GROUP BY 1, 2 ORDER BY 2""",
    "discount_margin": """
        SELECT discount_band AS "Discount band", row_number() OVER (ORDER BY min_rate) AS "Band order",
               lines AS "Order lines", round(gross_sales, 0) AS "List-price sales", round(discount_amount, 0) AS "Discount",
               round(profit, 0) AS "Profit", profit_pct_of_gross AS "Profit % of list price",
               profit_pct_of_net AS "Profit % after discount", loss_lines_pct AS "Loss-making lines %"
        FROM mart_discount_bands ORDER BY min_rate""",
    "forecast": """
        SELECT week_start AS "Week start", series AS "Series",
               CASE WHEN split = 'train' THEN 'Actual'
                    WHEN split = 'holdout' AND model = 'ETS' THEN 'ETS forecast (holdout)'
                    WHEN split = 'holdout' AND model = 'Seasonal naive' THEN 'Seasonal naive (holdout)'
                    WHEN split = 'future' THEN 'ETS forecast (next 12 weeks)' END AS "Line",
               split AS "Period",
               coalesce(forecast, actual) AS "Units",
               lower_80 AS "Lower 80", upper_80 AS "Upper 80"
        FROM forecast_weekly
        WHERE split <> 'holdout' OR model IN ('ETS', 'Seasonal naive')
        UNION ALL
        SELECT week_start, series, 'Actual', 'holdout', actual, NULL, NULL
        FROM forecast_weekly WHERE split = 'holdout' AND model = 'ETS'
        ORDER BY 2, 1, 3""",
    "forecast_accuracy": """
        SELECT series AS "Series",
               CASE WHEN model LIKE 'ETS, AICc%' THEN 'ETS (AICc-selected)' ELSE model END AS "Model",
               replace(model, 'ETS, AICc-selected: ', '') AS "Model detail",
               wape_pct AS "WAPE %", mape_pct AS "MAPE %", bias_pct AS "Bias %"
        FROM forecast_accuracy WHERE model NOT LIKE 'ETS (not selected)%'
        ORDER BY series = 'All categories' DESC, 1, 4""",
    "whatif": """
        SELECT shipping_mode AS "Shipping mode",
               shipping_mode || ': ' || promised_days || ' -> ' || new_promise || ' days' AS "Change",
               late_lines_now AS "Late lines now", late_lines_avoided AS "Late lines avoided",
               round(100.0 * late_lines_avoided / late_lines_all_modes_now, 1) AS "Share of all late avoided %",
               round(100.0 * (late_lines_all_modes_now - late_lines_avoided)
                     / (SELECT count(*) FROM fact_order_lines WHERE NOT is_cancelled), 1) AS "Overall late % after"
        FROM mart_whatif_promise WHERE extra_days = 1 ORDER BY 4 DESC""",
    "monthly_mode": """
        SELECT CAST(strptime(year_month || '-01', '%Y-%m-%d') AS DATE) AS "Month start", year_month AS "Month",
               shipping_mode AS "Shipping mode",
               sum(shipped_lines) AS "Shipped lines",
               round(100.0 * sum(late_lines) / sum(shipped_lines), 1) AS "Late %",
               round(sum(profit), 0) AS "Profit"
        FROM mart_monthly_kpis WHERE year_month <= '2017-09'
        GROUP BY 1, 2, 3 ORDER BY 1, 3""",
}

ABOUT = [
    ("About", "Supply chain late deliveries and demand forecast. Built by src/tableau_workbook.py from data/supply_chain.duckdb."),
    ("Source", "DataCo Smart Supply Chain for Big Data Analysis (Constante, Silva, Pereira 2019), Mendeley Data v5, CC BY 4.0."),
    ("Grain", "Each sheet has one row per mark. Rates are 0-100 (57.3 = 57.3%). Do not use Tableau's Percentage format."),
    ("Late", "Late = actual shipping days > scheduled days. Base for rates = shipped (not cancelled) lines."),
    ("Profit at risk", "Profit on late lines plus profit on cancelled lines (CANCELED and SUSPECTED_FRAUD)."),
    ("Forecast", "Weekly units, 5 Jan 2015 to week of 25 Sep 2017. Holdout = last 13 weeks. From 2 Oct 2017 the file is a cut-off extract (excluded)."),
    ("monthly_mode", "Months before Oct 2017 only. Markets appear in date blocks in this dataset, so monthly market trends are not meaningful."),
]


def main() -> None:
    con = duckdb.connect(str(ROOT / "data" / "supply_chain.duckdb"), read_only=True)
    wb = Workbook()
    wb.remove(wb.active)
    EXPORTS.mkdir(exist_ok=True)
    for name, sql in SHEETS.items():
        rel = con.sql(sql)
        cols, rows = rel.columns, rel.fetchall()
        ws = wb.create_sheet(name)
        ws.append(cols)
        for c in ws[1]:
            c.font = Font(bold=True)
        for r in rows:
            ws.append([float(v) if hasattr(v, "is_finite") else v for v in r])
        for i, col in enumerate(cols, 1):
            ws.column_dimensions[get_column_letter(i)].width = max(12, len(col) + 2)
        con.sql(sql).write_csv(str(EXPORTS / f"{name}.csv"))
        print(f"  {name:<20} {len(rows):>5} rows")
    ws = wb.create_sheet("about")
    ws.append(["Topic", "Note"])
    for r in ABOUT:
        ws.append(list(r))
    ws.column_dimensions["B"].width = 120
    OUT.parent.mkdir(exist_ok=True)
    wb.save(OUT)
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
