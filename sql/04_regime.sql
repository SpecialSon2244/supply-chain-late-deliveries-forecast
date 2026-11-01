-- 04_regime.sql
-- Detect where the data changes character, so the forecast only uses comparable weeks.
-- From early October 2017 the file has about 480 lines a week with exactly one line per
-- order (before: about 1,200 lines a week, about 3 lines per order) and only a handful of
-- products. That looks like an extract cut-off, not real demand, so it is excluded.

CREATE OR REPLACE TABLE mart_weekly_volume AS
WITH weekly AS (
    SELECT d.week_start,
           count(*)                         AS lines,
           count(DISTINCT f.order_id)       AS orders,
           sum(f.quantity)                  AS units,
           count(DISTINCT d.date)           AS days_with_orders,
           count(DISTINCT f.product_key)    AS products
    FROM fact_order_lines f
    JOIN dim_date d ON d.date_key = f.order_date_key
    GROUP BY d.week_start
)
SELECT
    week_start,
    lines,
    orders,
    units,
    days_with_orders,
    products,
    round(lines / orders, 2)                                                   AS lines_per_order,
    LAG(lines) OVER w                                                          AS lines_prev_week,
    median(lines) OVER (ORDER BY week_start ROWS BETWEEN 12 PRECEDING AND 1 PRECEDING) AS lines_trailing_12wk_median,
    -- a "break" week: volume below 60% of the trailing 12-week median and almost one line per order
    lines < 0.6 * median(lines) OVER (ORDER BY week_start ROWS BETWEEN 12 PRECEDING AND 1 PRECEDING)
        AND lines / orders < 1.2                                               AS is_break
FROM weekly
WINDOW w AS (ORDER BY week_start);

-- One-row table with the comparable window: first full week up to the last full week before the break.
CREATE OR REPLACE TABLE forecast_window AS
WITH brk AS (SELECT min(week_start) AS break_week FROM mart_weekly_volume WHERE is_break)
SELECT
    (SELECT min(week_start) FROM mart_weekly_volume WHERE days_with_orders = 7)            AS first_week,
    (SELECT max(week_start) FROM mart_weekly_volume, brk
      WHERE days_with_orders = 7 AND week_start < brk.break_week)                          AS last_week,
    brk.break_week,
    (SELECT max(week_start) FROM mart_weekly_volume)                                        AS last_week_in_file
FROM brk;
