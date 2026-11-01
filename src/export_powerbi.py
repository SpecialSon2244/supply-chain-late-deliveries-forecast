"""Export the star schema for Power BI Desktop -> powerbi/model/*.csv (UTF-8, ISO dates, true/false).

The fact table is also written as Parquet (Power BI: Get data > Parquet), which is the copy kept in git.
"""
import pathlib

import duckdb

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "powerbi" / "model"
OUT.mkdir(parents=True, exist_ok=True)

TABLES = {
    "fact_order_lines": """
        SELECT order_line_id, order_id, order_date_key, ship_date_key, product_key, customer_key, market_key,
               shipping_mode_key, payment_type, order_status, delivery_status, days_scheduled, days_actual,
               delay_days, is_late, is_on_time, is_cancelled, is_suspected_fraud, quantity, round(unit_price, 2) AS unit_price,
               round(gross_sales, 2) AS gross_sales, round(discount_amount, 2) AS discount_amount, discount_rate,
               discount_band, round(net_sales, 2) AS net_sales, round(profit, 2) AS profit, is_loss
        FROM fact_order_lines ORDER BY order_line_id""",
    "dim_date": """
        SELECT d.*, d.week_start BETWEEN w.first_week AND w.last_week + 6 AS in_comparable_window
        FROM dim_date d, forecast_window w ORDER BY date_key""",
    "dim_product": "SELECT * FROM dim_product ORDER BY product_key",
    "dim_customer": "SELECT * FROM dim_customer ORDER BY customer_key",
    "dim_market": "SELECT * FROM dim_market ORDER BY market_key",
    "dim_shipping_mode": "SELECT shipping_mode_key, shipping_mode, promised_days FROM dim_shipping_mode ORDER BY 1",
    "dim_discount_band": """
        SELECT discount_band, row_number() OVER (ORDER BY min_rate) AS band_order, min_rate, max_rate
        FROM mart_discount_bands""",
    "forecast_weekly": """
        SELECT series, week_start, CAST(strftime(week_start, '%Y%m%d') AS INTEGER) AS week_date_key,
               split, model, actual, forecast, lower_80, upper_80
        FROM forecast_weekly ORDER BY series, week_start, model""",
    "forecast_accuracy": "SELECT * FROM forecast_accuracy ORDER BY series, wape_pct",
    "whatif_promise": "SELECT * FROM mart_whatif_promise ORDER BY promised_days, new_promise",
}


def main() -> None:
    con = duckdb.connect(str(ROOT / "data" / "supply_chain.duckdb"), read_only=True)
    for name, sql in TABLES.items():
        path = OUT / f"{name}.csv"
        con.sql(sql).write_csv(str(path))
        if name == "fact_order_lines":
            # The CSV is about 29 MB and is not kept in git; the Parquet copy (a few MB) is.
            con.execute(f"COPY ({sql}) TO '{OUT / (name + '.parquet')}' (FORMAT parquet, COMPRESSION zstd)")
        n = con.sql(f"SELECT count(*) FROM ({sql})").fetchall()[0][0]
        print(f"  {name:<20} {n:>8,} rows  {path.stat().st_size / 1e6:6.2f} MB")


if __name__ == "__main__":
    main()
