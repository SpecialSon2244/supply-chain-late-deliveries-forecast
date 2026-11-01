-- 05_marts.sql
-- Aggregated tables for findings, charts, Tableau and Power BI.
-- Window functions used on purpose: rolling sums (ROWS BETWEEN), LAG, RANK, running totals.

-- 1. Weekly demand per category with rolling 4-week demand, LAG and a running total.
CREATE OR REPLACE TABLE mart_weekly_category_demand AS
WITH weeks AS (
    SELECT DISTINCT week_start FROM mart_weekly_volume
    WHERE week_start >= (SELECT first_week FROM forecast_window)
),
cats AS (SELECT DISTINCT category_name FROM dim_product),
actual AS (
    SELECT d.week_start, p.category_name,
           sum(f.quantity) AS units, count(*) AS lines,
           sum(f.net_sales) AS net_sales, sum(f.profit) AS profit
    FROM fact_order_lines f
    JOIN dim_date d    ON d.date_key = f.order_date_key
    JOIN dim_product p ON p.product_key = f.product_key
    GROUP BY ALL
),
grid AS (
    SELECT w.week_start, c.category_name,
           coalesce(a.units, 0) AS units, coalesce(a.lines, 0) AS lines,
           coalesce(a.net_sales, 0) AS net_sales, coalesce(a.profit, 0) AS profit
    FROM weeks w CROSS JOIN cats c
    LEFT JOIN actual a USING (week_start, category_name)
)
SELECT
    week_start,
    category_name,
    units,
    lines,
    round(net_sales, 2) AS net_sales,
    round(profit, 2)    AS profit,
    SUM(units) OVER (PARTITION BY category_name ORDER BY week_start
                     ROWS BETWEEN 3 PRECEDING AND CURRENT ROW)                     AS units_rolling_4wk,
    round(AVG(units) OVER (PARTITION BY category_name ORDER BY week_start
                     ROWS BETWEEN 3 PRECEDING AND CURRENT ROW), 1)                 AS units_avg_4wk,
    LAG(units, 1)  OVER (PARTITION BY category_name ORDER BY week_start)          AS units_prev_week,
    LAG(units, 52) OVER (PARTITION BY category_name ORDER BY week_start)          AS units_same_week_last_year,
    round(100.0 * (units - LAG(units) OVER (PARTITION BY category_name ORDER BY week_start))
          / nullif(LAG(units) OVER (PARTITION BY category_name ORDER BY week_start), 0), 1) AS wow_change_pct,
    SUM(units) OVER (PARTITION BY category_name, year(week_start) ORDER BY week_start
                     ROWS UNBOUNDED PRECEDING)                                     AS units_ytd_running,
    week_start BETWEEN (SELECT first_week FROM forecast_window)
                   AND (SELECT last_week FROM forecast_window)                     AS in_forecast_window
FROM grid;

-- 2. Category ranking per year with Pareto (cumulative share), comparable window only.
CREATE OR REPLACE TABLE mart_category_rank_year AS
WITH y AS (
    SELECT year(week_start) AS year, category_name,
           sum(units) AS units, sum(net_sales) AS net_sales, sum(profit) AS profit
    FROM mart_weekly_category_demand
    WHERE in_forecast_window
    GROUP BY ALL
    HAVING sum(units) > 0
)
SELECT
    year, category_name, units, round(net_sales, 2) AS net_sales, round(profit, 2) AS profit,
    RANK() OVER (PARTITION BY year ORDER BY units DESC)                                  AS units_rank,
    RANK() OVER (PARTITION BY year ORDER BY net_sales DESC)                              AS sales_rank,
    round(100.0 * units / SUM(units) OVER (PARTITION BY year), 2)                        AS units_share_pct,
    round(100.0 * SUM(units) OVER (PARTITION BY year ORDER BY units DESC, category_name
                                   ROWS UNBOUNDED PRECEDING)
          / SUM(units) OVER (PARTITION BY year), 2)                                      AS units_cum_share_pct
FROM y;

-- 3. Monthly KPIs by shipping mode and market (additive counts and sums only).
CREATE OR REPLACE TABLE mart_monthly_kpis AS
SELECT
    d.year_month,
    CAST(date_trunc('month', min(d.date)) AS DATE)          AS month_start,
    sm.shipping_mode,
    m.market,
    count(*)                                                AS lines,
    count(*) FILTER (WHERE NOT f.is_cancelled)              AS shipped_lines,
    count(*) FILTER (WHERE f.is_late)                       AS late_lines,
    count(*) FILTER (WHERE f.is_on_time)                    AS on_time_lines,
    count(*) FILTER (WHERE f.is_cancelled)                  AS cancelled_lines,
    sum(f.quantity)                                         AS units,
    round(sum(f.gross_sales), 2)                            AS gross_sales,
    round(sum(f.net_sales), 2)                              AS net_sales,
    round(sum(f.profit), 2)                                 AS profit,
    round(sum(f.profit) FILTER (WHERE f.is_late), 2)        AS late_profit,
    round(sum(f.profit) FILTER (WHERE f.is_cancelled), 2)   AS cancelled_profit,
    sum(f.days_scheduled) FILTER (WHERE NOT f.is_cancelled) AS sum_days_scheduled,
    sum(f.days_actual)    FILTER (WHERE NOT f.is_cancelled) AS sum_days_actual
FROM fact_order_lines f
JOIN dim_date d           ON d.date_key = f.order_date_key
JOIN dim_shipping_mode sm ON sm.shipping_mode_key = f.shipping_mode_key
JOIN dim_market m         ON m.market_key = f.market_key
GROUP BY d.year_month, sm.shipping_mode, m.market;

-- 4. Monthly totals with YoY (LAG 12), a rolling 3-month late rate and a running profit total.
CREATE OR REPLACE TABLE mart_monthly_total AS
WITH t AS (
    SELECT year_month, min(month_start) AS month_start,
           sum(lines) AS lines, sum(shipped_lines) AS shipped_lines, sum(late_lines) AS late_lines,
           sum(cancelled_lines) AS cancelled_lines, sum(units) AS units,
           sum(net_sales) AS net_sales, sum(profit) AS profit
    FROM mart_monthly_kpis GROUP BY year_month
)
SELECT
    year_month, month_start, lines, shipped_lines, late_lines, cancelled_lines, units,
    round(net_sales, 2) AS net_sales, round(profit, 2) AS profit,
    round(100.0 * late_lines / shipped_lines, 2)                                     AS late_pct,
    round(100.0 * SUM(late_lines) OVER w3 / SUM(shipped_lines) OVER w3, 2)           AS late_pct_rolling_3m,
    LAG(units, 12) OVER (ORDER BY year_month)                                        AS units_prev_year,
    round(100.0 * (units - LAG(units, 12) OVER (ORDER BY year_month))
          / LAG(units, 12) OVER (ORDER BY year_month), 1)                            AS units_yoy_pct,
    round(SUM(profit) OVER (PARTITION BY left(year_month, 4) ORDER BY year_month
                            ROWS UNBOUNDED PRECEDING), 2)                            AS profit_ytd_running,
    month_start <= (SELECT last_week FROM forecast_window)                           AS before_break
FROM t
WINDOW w3 AS (ORDER BY year_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW);

-- 5. Promise vs reality: distribution of actual shipping days per mode (shipped lines).
CREATE OR REPLACE TABLE mart_schedule_vs_actual AS
WITH c AS (
    SELECT sm.shipping_mode, sm.promised_days, f.days_actual, count(*) AS lines
    FROM fact_order_lines f
    JOIN dim_shipping_mode sm USING (shipping_mode_key)
    WHERE NOT f.is_cancelled
    GROUP BY ALL
)
SELECT
    shipping_mode, promised_days, days_actual, lines,
    days_actual > promised_days                                                       AS is_late,
    round(100.0 * lines / SUM(lines) OVER (PARTITION BY shipping_mode), 2)           AS share_of_mode_pct,
    round(100.0 * SUM(lines) OVER (PARTITION BY shipping_mode ORDER BY days_actual
                                   ROWS UNBOUNDED PRECEDING)
          / SUM(lines) OVER (PARTITION BY shipping_mode), 2)                          AS cum_share_of_mode_pct
FROM c;

-- 6. What-if: late lines per mode if the promise (scheduled days) were p days instead.
--    Assumes actual shipping times stay as they are (only the promise, or the process
--    behind it, changes for that one mode). Uses the running total of the day distribution.
CREATE OR REPLACE TABLE mart_whatif_promise AS
WITH dist AS (
    SELECT shipping_mode, promised_days, days_actual, lines,
           SUM(lines) OVER (PARTITION BY shipping_mode ORDER BY days_actual
                            ROWS UNBOUNDED PRECEDING) AS lines_at_or_below,
           SUM(lines) OVER (PARTITION BY shipping_mode) AS mode_lines
    FROM mart_schedule_vs_actual
),
modes AS (
    SELECT shipping_mode, any_value(promised_days) AS promised_days, any_value(mode_lines) AS shipped_lines,
           sum(lines) FILTER (WHERE days_actual > promised_days) AS late_lines_now
    FROM dist GROUP BY shipping_mode
),
promises AS (SELECT CAST(p AS INTEGER) AS new_promise FROM range(0, 7) r(p)),
covered AS (
    SELECT m.shipping_mode, p.new_promise,
           coalesce(max(d.lines_at_or_below), 0) AS lines_within_promise
    FROM modes m CROSS JOIN promises p
    LEFT JOIN dist d ON d.shipping_mode = m.shipping_mode AND d.days_actual <= p.new_promise
    GROUP BY m.shipping_mode, p.new_promise
)
SELECT
    m.shipping_mode, m.promised_days, c.new_promise,
    c.new_promise - m.promised_days                   AS extra_days,
    m.shipped_lines,
    m.late_lines_now,
    m.shipped_lines - c.lines_within_promise          AS late_lines_if,
    m.late_lines_now - (m.shipped_lines - c.lines_within_promise) AS late_lines_avoided,
    SUM(m.late_lines_now) OVER (PARTITION BY c.new_promise) AS late_lines_all_modes_now
FROM modes m
JOIN covered c USING (shipping_mode);

-- 7. Discount bands vs profit.
CREATE OR REPLACE TABLE mart_discount_bands AS
SELECT
    discount_band,
    min(discount_rate) AS min_rate, max(discount_rate) AS max_rate,
    count(*) AS lines,
    round(sum(gross_sales), 2)                                 AS gross_sales,
    round(sum(discount_amount), 2)                             AS discount_amount,
    round(sum(net_sales), 2)                                   AS net_sales,
    round(sum(profit), 2)                                      AS profit,
    round(100.0 * sum(discount_amount) / sum(gross_sales), 2)  AS discount_pct_of_gross,
    round(100.0 * sum(profit) / sum(gross_sales), 2)           AS profit_pct_of_gross,
    round(100.0 * sum(profit) / sum(net_sales), 2)             AS profit_pct_of_net,
    round(100.0 * avg(is_loss::INT), 2)                        AS loss_lines_pct
FROM fact_order_lines
GROUP BY discount_band;
