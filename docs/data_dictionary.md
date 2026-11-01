# Data dictionary

## Raw file

`data/raw/DataCoSupplyChainDataset.csv`: 180,519 rows, 53 columns, Latin-1 encoded,
96 MB, SHA-256 `fa6d022ed437155e1a2f0378710602848703c8a7f203f7ff5d77805bf8480aa6`.
Not in git; `make data` downloads it.

Dropped in `src/build.py`:

- Personal or masked: `Customer Email`, `Customer Password`, `Customer Fname`,
  `Customer Lname`, `Customer Street`, `Customer Zipcode`.
- Not used: `Latitude`, `Longitude` (store coordinates).
- Empty or constant: `Product Description` (empty), `Product Image` (URL),
  `Product Status` (always 0), `Order Zipcode` (mostly empty).
- Exact duplicates (checked equal before dropping): `Benefit per order` (= `Order Profit Per Order`),
  `Sales per customer` (= `Order Item Total`), `Order Customer Id` (= `Customer Id`),
  `Product Category Id` (= `Category Id`), `Order Item Cardprod Id` (= `Product Card Id`),
  `Product Price` (= `Order Item Product Price`).

## fact_order_lines (180,519 rows, one per order line)

| Column | Type | Meaning |
|---|---|---|
| order_line_id | int | `Order Item Id`, primary key |
| order_id | int | `Order Id` (65,752 orders) |
| order_date_key, ship_date_key | int (yyyymmdd) | keys to dim_date |
| order_ts | timestamp | order date and time |
| product_key | int | key to dim_product (`Product Card Id`) |
| customer_key | int | key to dim_customer (`Customer Id`) |
| market_key | int | key to dim_market (market + order region + order country) |
| shipping_mode_key | int | key to dim_shipping_mode |
| payment_type | text | DEBIT, TRANSFER, CASH, PAYMENT |
| order_status | text | COMPLETE, PENDING, CLOSED, SUSPECTED_FRAUD, CANCELED, ... |
| delivery_status | text | Advance shipping, Shipping on time, Late delivery, Shipping canceled |
| days_scheduled | int | promised days for the mode |
| days_actual | int | days from order to shipping |
| delay_days | int | days_actual - days_scheduled |
| is_late, is_on_time, is_cancelled | bool | exactly one is true per line |
| is_suspected_fraud | bool | order_status = SUSPECTED_FRAUD (all cancelled) |
| quantity | int | units |
| unit_price | double | price per unit (USD) |
| gross_sales | double | unit_price x quantity |
| discount_amount, discount_rate | double | discount in USD and as a share (0 to 0.25) |
| discount_band | text | 0%, 1-5%, 6-10%, 11-15%, 16-20%, 25% |
| net_sales | double | gross_sales - discount_amount |
| profit | double | profit on the line (USD) |
| profit_ratio | double | profit / net sales, as given in the source |
| is_loss | bool | profit < 0 |

## Dimensions

| Table | Rows | Columns |
|---|---|---|
| dim_date | 1,133 (1 Jan 2015 to 6 Feb 2018, covers order and ship dates) | date_key, date, year, quarter, quarter_name, month, month_name, year_month, week_start (Monday), iso_year, iso_week, iso_weekday, weekday_name, is_weekend |
| dim_product | 118 | product_key, product_name, list_price, category_id, category_name, department_id, department_name |
| dim_customer | 20,652 | customer_key, segment (Consumer, Corporate, Home Office), city, state, country |
| dim_market | 167 | market_key, market (5), order_region (23), order_country (164, Spanish names) |
| dim_shipping_mode | 4 | shipping_mode_key, shipping_mode, promised_days, n_promises (always 1, a check) |

## Marts (sql/04_regime.sql, sql/05_marts.sql)

| Table | Grain | Notes |
|---|---|---|
| mart_weekly_volume | week | lines, orders, units, trailing 12-week median, is_break |
| forecast_window | 1 row | first_week, last_week, break_week, last_week_in_file |
| mart_weekly_category_demand | category x week (full grid, zeros filled) | units, rolling 4 weeks, LAG 1 and 52, week-on-week %, YTD running total, in_forecast_window |
| mart_category_rank_year | category x year | units and RANK within the year |
| mart_monthly_kpis | month x mode x market | lines, late %, profit |
| mart_monthly_total | month | late %, LAG 12 YoY, rolling 3-month late %, profit YTD |
| mart_schedule_vs_actual | mode x actual days | lines, share and cumulative share of the mode |
| mart_whatif_promise | mode x new promise (0 to 6 days, 28 rows) | late lines now and if, avoided, overall late % after |
| mart_discount_bands | discount band | lines, gross, discount, profit, margins, loss share |
| forecast_weekly | series x week x model | actual, forecast, 80% interval (future weeks) |
| forecast_accuracy | series x model | WAPE, MAPE, bias on the holdout, AICc for ETS |

## Tableau workbook and exports

`tableau/supply_chain_late_deliveries.xlsx` and the matching `exports/<sheet>.csv`:

| Sheet | Rows | Used on dashboard |
|---|---|---|
| kpis | 7 | KPI strip |
| late_by_mode | 4 | yes |
| late_by_market | 5 | yes |
| late_by_region | 23 | no |
| late_by_category | 51 (category x department) | no |
| schedule_vs_actual | 13 | no |
| profit_at_risk | 3 | yes |
| discount_margin | 6 | yes |
| forecast | 1,086 | yes |
| forecast_accuracy | 24 (4 models x 6 series) | no |
| whatif | 4 | no |
| monthly_mode | 132 (33 months x 4 modes, Jan 2015 to Sep 2017) | no |
| about | notes | no |

Column names and meanings are given in [tableau/BUILD_SPEC.md](../tableau/BUILD_SPEC.md)
and in the `about` sheet.

## Power BI model

`powerbi/model/`: the fact and dimension tables above (fact as Parquet, plus a CSV that
is not in git), `dim_discount_band`, `forecast_weekly`, `forecast_accuracy`,
`whatif_promise`. See [powerbi/BUILD_NOTES.md](../powerbi/BUILD_NOTES.md).
