"""Clean the raw CSV with Polars, then build the DuckDB star schema from sql/*.sql.

Steps
1. Polars reads the CSV (latin-1, decoded in Python), renames columns to snake_case,
   parses the two timestamp columns and checks that the columns we drop as duplicates
   really are duplicates.
2. Personal or useless columns are dropped (masked e-mail and password, customer
   names and street, empty product description, image URL, constant product status,
   mostly empty order zip code, store coordinates).
3. The cleaned table is written to data/staging/order_lines.parquet.
4. DuckDB runs sql/01_staging.sql ... sql/05_marts.sql into data/supply_chain.duckdb.
"""
import io
import os
import pathlib
import re
import time

import duckdb
import polars as pl

ROOT = pathlib.Path(__file__).resolve().parents[1]
os.chdir(ROOT)
RAW = ROOT / "data" / "raw" / "DataCoSupplyChainDataset.csv"
STAGING = ROOT / "data" / "staging" / "order_lines.parquet"
DB = ROOT / "data" / "supply_chain.duckdb"

# Columns that repeat another column (checked below before they are dropped).
DUPLICATES = {
    "benefit_per_order": "order_profit_per_order",
    "sales_per_customer": "order_item_total",
    "order_customer_id": "customer_id",
    "product_category_id": "category_id",
    "order_item_cardprod_id": "product_card_id",
    "product_price": "order_item_product_price",
}
DROP_PERSONAL_OR_EMPTY = [
    "customer_email", "customer_password", "customer_fname", "customer_lname",
    "customer_street", "customer_zipcode", "product_description", "product_image",
    "product_status", "order_zipcode", "latitude", "longitude",
]


def snake(name: str) -> str:
    name = name.replace("(DateOrders)", "").replace("(real)", "real").replace("(scheduled)", "scheduled")
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")


def clean() -> pl.DataFrame:
    text = RAW.read_bytes().decode("latin-1")
    df = pl.read_csv(io.StringIO(text).read().encode("utf-8"), infer_schema_length=None)
    df = df.rename({c: snake(c) for c in df.columns})
    df = df.rename({"days_for_shipping_real": "days_actual", "days_for_shipment_scheduled": "days_scheduled",
                    "order_date": "order_ts", "shipping_date": "ship_ts"})
    for dup, keep in DUPLICATES.items():
        a, b = df[dup], df[keep]
        same = ((a - b).abs() < 0.01) if a.dtype.is_float() else (a == b)
        assert same.all(), f"{dup} is not a copy of {keep}"
    df = df.drop(list(DUPLICATES) + DROP_PERSONAL_OR_EMPTY)
    df = df.with_columns(
        pl.col("order_ts").str.strptime(pl.Datetime, "%m/%d/%Y %H:%M"),
        pl.col("ship_ts").str.strptime(pl.Datetime, "%m/%d/%Y %H:%M"),
        pl.col("order_item_discount_rate").round(2),
        pl.col("order_item_profit_ratio").round(2),
        pl.col("product_name").str.strip_chars(),
        pl.col("category_name").str.strip_chars().str.replace_all(r"\s+", " "),
        pl.col("order_region").str.replace_all(r"\s+", " "),
    )
    return df


def main() -> None:
    t0 = time.time()
    df = clean()
    STAGING.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(STAGING)
    print(f"staging: {df.height:,} rows x {df.width} columns -> {STAGING.relative_to(ROOT)}")
    if DB.exists():
        DB.unlink()
    con = duckdb.connect(str(DB))
    for f in sorted((ROOT / "sql").glob("0*.sql")):
        con.execute(f.read_text())
        print(f"ran {f.name}")
    for (t,) in con.execute("SELECT table_name FROM information_schema.tables "
                            "WHERE table_type = 'BASE TABLE' ORDER BY 1").fetchall():
        n = con.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0]
        print(f"  {t:<34} {n:>9,} rows")
    con.close()
    print(f"built {DB.relative_to(ROOT)} in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
