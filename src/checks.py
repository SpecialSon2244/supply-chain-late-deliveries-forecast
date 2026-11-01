"""Data quality and reconciliation checks, shared by src/validate.py and tests/.

Each check is a SQL query returning one row with one value that must equal `expect`
(or be True). Reconciliation checks compare the star schema with totals computed
by Polars straight from the raw CSV, so a broken join or filter shows up.
"""
import io
import pathlib

import polars as pl

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "DataCoSupplyChainDataset.csv"

CHECKS = [
    # (name, sql, expected value)
    ("fact has one row per order line", "SELECT count(*) = count(DISTINCT order_line_id) FROM fact_order_lines", True),
    ("fact row count", "SELECT count(*) FROM fact_order_lines", 180_519),
    ("no null keys in fact",
     "SELECT count(*) FROM fact_order_lines WHERE order_date_key IS NULL OR ship_date_key IS NULL "
     "OR product_key IS NULL OR customer_key IS NULL OR market_key IS NULL OR shipping_mode_key IS NULL", 0),
    ("every order date is in dim_date",
     "SELECT count(*) FROM fact_order_lines f ANTI JOIN dim_date d ON d.date_key = f.order_date_key", 0),
    ("every ship date is in dim_date",
     "SELECT count(*) FROM fact_order_lines f ANTI JOIN dim_date d ON d.date_key = f.ship_date_key", 0),
    ("every product is in dim_product",
     "SELECT count(*) FROM fact_order_lines f ANTI JOIN dim_product p ON p.product_key = f.product_key", 0),
    ("every customer is in dim_customer",
     "SELECT count(*) FROM fact_order_lines f ANTI JOIN dim_customer c ON c.customer_key = f.customer_key", 0),
    ("dim_product key unique", "SELECT count(*) = count(DISTINCT product_key) FROM dim_product", True),
    ("dim_customer key unique", "SELECT count(*) = count(DISTINCT customer_key) FROM dim_customer", True),
    ("dim_market key unique", "SELECT count(*) = count(DISTINCT market_key) FROM dim_market", True),
    ("each shipping mode has exactly one promise", "SELECT max(n_promises) FROM dim_shipping_mode", 1),
    ("one delivery status per order",
     "SELECT count(*) FROM (SELECT order_id FROM fact_order_lines GROUP BY 1 HAVING count(DISTINCT delivery_status) > 1)", 0),
    ("one product name per product",
     "SELECT count(*) FROM (SELECT product_card_id FROM stg_order_lines GROUP BY 1 HAVING count(DISTINCT product_name) > 1)", 0),
    ("one segment per customer",
     "SELECT count(*) FROM (SELECT customer_id FROM stg_order_lines GROUP BY 1 HAVING count(DISTINCT customer_segment) > 1)", 0),
    ("ship date - order date = actual shipping days",
     "SELECT count(*) FROM fact_order_lines f JOIN dim_date o ON o.date_key = f.order_date_key "
     "JOIN dim_date s ON s.date_key = f.ship_date_key WHERE s.date - o.date <> f.days_actual", 0),
    ("late flag = actual > scheduled (shipped lines)",
     "SELECT count(*) FROM fact_order_lines WHERE NOT is_cancelled AND is_late <> (days_actual > days_scheduled)", 0),
    ("cancelled lines are never flagged late",
     "SELECT count(*) FROM fact_order_lines WHERE is_cancelled AND is_late", 0),
    ("late + on time + cancelled = all lines",
     "SELECT count(*) FILTER (WHERE is_late) + count(*) FILTER (WHERE is_on_time) "
     "+ count(*) FILTER (WHERE is_cancelled) = count(*) FROM fact_order_lines", True),
    ("gross sales = unit price x quantity (1 cent)",
     "SELECT count(*) FROM fact_order_lines WHERE abs(gross_sales - unit_price * quantity) > 0.01", 0),
    ("net sales = gross - discount (5 cents, float rounding in source)",
     "SELECT count(*) FROM fact_order_lines WHERE abs(net_sales - (gross_sales - discount_amount)) > 0.05", 0),
    ("discount rate between 0 and 25%",
     "SELECT count(*) FROM fact_order_lines WHERE discount_rate < 0 OR discount_rate > 0.25", 0),
    ("quantity positive", "SELECT count(*) FROM fact_order_lines WHERE quantity <= 0", 0),
    ("ship date not before order date",
     "SELECT count(*) FROM fact_order_lines WHERE ship_date_key < order_date_key", 0),
    ("monthly mart reconciles to fact (lines)",
     "SELECT (SELECT sum(lines) FROM mart_monthly_kpis) = (SELECT count(*) FROM fact_order_lines)", True),
    ("monthly mart reconciles to fact (profit, 1 unit)",
     "SELECT abs((SELECT sum(profit) FROM mart_monthly_kpis) - (SELECT sum(profit) FROM fact_order_lines)) < 1", True),
    ("weekly category mart reconciles to fact in window (units)",
     "SELECT (SELECT sum(units) FROM mart_weekly_category_demand WHERE in_forecast_window) = "
     "(SELECT sum(f.quantity) FROM fact_order_lines f JOIN dim_date d ON d.date_key = f.order_date_key, forecast_window w "
     " WHERE d.week_start BETWEEN w.first_week AND w.last_week)", True),
    ("discount bands reconcile to fact (lines)",
     "SELECT (SELECT sum(lines) FROM mart_discount_bands) = (SELECT count(*) FROM fact_order_lines)", True),
    ("what-if at current promise = current late lines",
     "SELECT count(*) FROM mart_whatif_promise WHERE extra_days = 0 AND late_lines_if <> late_lines_now", 0),
    ("break week detected in Oct 2017", "SELECT strftime(break_week, '%Y-%m') FROM forecast_window", "2017-10"),
]


def raw_totals() -> dict:
    """Totals straight from the raw CSV, without any of the project's SQL."""
    text = RAW.read_bytes().decode("latin-1").encode("utf-8")
    df = pl.read_csv(io.BytesIO(text), infer_schema_length=None)
    return {
        "rows": df.height,
        "orders": df["Order Id"].n_unique(),
        "sales": round(df["Sales"].sum(), 2),
        "net_sales": round(df["Order Item Total"].sum(), 2),
        "profit": round(df["Order Profit Per Order"].sum(), 2),
        "late_lines": int(df["Late_delivery_risk"].sum()),
        "cancelled_lines": int((df["Delivery Status"] == "Shipping canceled").sum()),
        "units": int(df["Order Item Quantity"].sum()),
    }


FACT_TOTALS_SQL = """
SELECT count(*) AS rows, count(DISTINCT order_id) AS orders,
       round(sum(gross_sales), 2) AS sales, round(sum(net_sales), 2) AS net_sales,
       round(sum(profit), 2) AS profit, count(*) FILTER (WHERE is_late) AS late_lines,
       count(*) FILTER (WHERE is_cancelled) AS cancelled_lines, sum(quantity)::BIGINT AS units
FROM fact_order_lines
"""
