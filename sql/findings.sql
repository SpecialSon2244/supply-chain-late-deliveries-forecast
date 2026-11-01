-- name: q1_overall
-- Late-delivery rate overall. Base = shipped lines (cancelled lines are never late or on time).
SELECT count(*)                                                        AS order_lines,
       count(DISTINCT order_id)                                        AS orders,
       count(*) FILTER (WHERE NOT is_cancelled)                        AS shipped_lines,
       count(*) FILTER (WHERE is_late)                                 AS late_lines,
       count(*) FILTER (WHERE is_cancelled)                            AS cancelled_lines,
       round(100.0 * count(*) FILTER (WHERE is_late) / count(*) FILTER (WHERE NOT is_cancelled), 1) AS late_pct_of_shipped,
       round(100.0 * count(*) FILTER (WHERE is_late) / count(*), 1)    AS late_pct_of_all_lines,
       round(100.0 * count(DISTINCT order_id) FILTER (WHERE is_late)
             / count(DISTINCT order_id) FILTER (WHERE NOT is_cancelled), 1) AS late_pct_of_shipped_orders,
       round(avg(days_scheduled) FILTER (WHERE NOT is_cancelled), 2)   AS avg_days_scheduled,
       round(avg(days_actual) FILTER (WHERE NOT is_cancelled), 2)      AS avg_days_actual,
       round(avg(delay_days) FILTER (WHERE is_late), 2)                AS avg_days_late_when_late
FROM fact_order_lines;

-- name: q1_by_mode
SELECT sm.shipping_mode, sm.promised_days,
       count(*) FILTER (WHERE NOT f.is_cancelled)                     AS shipped_lines,
       round(100.0 * count(*) FILTER (WHERE NOT f.is_cancelled) / sum(count(*) FILTER (WHERE NOT f.is_cancelled)) OVER (), 1) AS share_of_shipped_pct,
       count(*) FILTER (WHERE f.is_late)                              AS late_lines,
       round(100.0 * count(*) FILTER (WHERE f.is_late) / count(*) FILTER (WHERE NOT f.is_cancelled), 1) AS late_pct,
       round(avg(f.days_actual) FILTER (WHERE NOT f.is_cancelled), 2) AS avg_days_actual,
       min(f.days_actual) FILTER (WHERE NOT f.is_cancelled)           AS min_days_actual,
       max(f.days_actual) FILTER (WHERE NOT f.is_cancelled)           AS max_days_actual,
       round(avg(f.delay_days) FILTER (WHERE f.is_late), 2)           AS avg_days_late_when_late,
       round(100.0 * count(*) FILTER (WHERE f.is_late) / sum(count(*) FILTER (WHERE f.is_late)) OVER (), 1) AS share_of_all_late_pct
FROM fact_order_lines f JOIN dim_shipping_mode sm USING (shipping_mode_key)
GROUP BY ALL ORDER BY sm.promised_days;

-- name: q1_by_market
SELECT m.market,
       count(*) FILTER (WHERE NOT f.is_cancelled) AS shipped_lines,
       round(100.0 * count(*) FILTER (WHERE f.is_late) / count(*) FILTER (WHERE NOT f.is_cancelled), 1) AS late_pct,
       strftime(min(f.order_ts), '%Y-%m') AS first_order_month,
       strftime(max(f.order_ts), '%Y-%m') AS last_order_month
FROM fact_order_lines f JOIN dim_market m USING (market_key)
GROUP BY ALL ORDER BY late_pct DESC;

-- name: q1_by_region_spread
-- Spread of the late rate across the 23 order regions.
WITH r AS (
    SELECT m.order_region,
           100.0 * count(*) FILTER (WHERE f.is_late) / count(*) FILTER (WHERE NOT f.is_cancelled) AS late_pct
    FROM fact_order_lines f JOIN dim_market m USING (market_key) GROUP BY 1)
SELECT count(*) AS regions, round(min(late_pct), 1) AS min_late_pct, round(max(late_pct), 1) AS max_late_pct,
       arg_min(order_region, late_pct) AS best_region, arg_max(order_region, late_pct) AS worst_region
FROM r;

-- name: q1_by_category
-- Categories with at least 1,000 shipped lines.
SELECT p.category_name,
       count(*) FILTER (WHERE NOT f.is_cancelled) AS shipped_lines,
       round(100.0 * count(*) FILTER (WHERE f.is_late) / count(*) FILTER (WHERE NOT f.is_cancelled), 1) AS late_pct,
       RANK() OVER (ORDER BY count(*) FILTER (WHERE f.is_late) * 1.0 / count(*) FILTER (WHERE NOT f.is_cancelled) DESC) AS late_rank
FROM fact_order_lines f JOIN dim_product p USING (product_key)
GROUP BY 1 HAVING count(*) FILTER (WHERE NOT f.is_cancelled) >= 1000
ORDER BY late_pct DESC;

-- name: q1_schedule_vs_actual
SELECT shipping_mode, promised_days, days_actual, lines, is_late, share_of_mode_pct, cum_share_of_mode_pct
FROM mart_schedule_vs_actual ORDER BY promised_days, days_actual;

-- name: q2_profit_by_status
SELECT CASE WHEN is_cancelled THEN 'Cancelled' WHEN is_late THEN 'Late' ELSE 'On time or early' END AS status_group,
       count(*) AS lines,
       round(sum(net_sales), 0) AS net_sales,
       round(sum(profit), 0) AS profit,
       round(100.0 * sum(profit) / sum(sum(profit)) OVER (), 1) AS share_of_profit_pct,
       round(100.0 * sum(profit) / sum(net_sales), 2) AS profit_margin_pct,
       round(100.0 * avg(is_loss::INT), 1) AS loss_lines_pct
FROM fact_order_lines GROUP BY 1 ORDER BY 1;

-- name: q2_profit_at_risk
-- Profit at risk = profit booked on late lines (customer promise broken) + on cancelled lines (not realised).
SELECT round(sum(profit), 0)                                                AS total_profit,
       round(sum(profit) FILTER (WHERE is_late), 0)                         AS late_profit,
       round(sum(profit) FILTER (WHERE is_cancelled), 0)                    AS cancelled_profit,
       round(sum(profit) FILTER (WHERE is_cancelled AND is_suspected_fraud), 0) AS suspected_fraud_profit,
       round(sum(profit) FILTER (WHERE is_late OR is_cancelled), 0)         AS profit_at_risk,
       round(100.0 * sum(profit) FILTER (WHERE is_late OR is_cancelled) / sum(profit), 1) AS profit_at_risk_pct,
       round(sum(net_sales) FILTER (WHERE is_late OR is_cancelled), 0)      AS net_sales_at_risk,
       round(-sum(profit) FILTER (WHERE is_loss), 0)                        AS losses_on_loss_lines,
       round(100.0 * avg(is_loss::INT), 1)                                  AS loss_lines_pct
FROM fact_order_lines;

-- name: q2_late_profit_by_mode
SELECT sm.shipping_mode,
       round(sum(f.profit) FILTER (WHERE f.is_late), 0) AS late_profit,
       round(100.0 * sum(f.profit) FILTER (WHERE f.is_late) / sum(sum(f.profit) FILTER (WHERE f.is_late)) OVER (), 1) AS share_of_late_profit_pct
FROM fact_order_lines f JOIN dim_shipping_mode sm USING (shipping_mode_key)
GROUP BY 1 ORDER BY late_profit DESC;

-- name: q2_discount_bands
SELECT discount_band, min_rate, max_rate, lines, gross_sales, discount_amount, profit,
       profit_pct_of_gross, profit_pct_of_net, loss_lines_pct
FROM mart_discount_bands ORDER BY min_rate;

-- name: q2_discount_correlation
-- Line-level correlation of the discount rate with profit as % of gross (list) sales and of net sales,
-- and how evenly the 18 discount rates are spread over the lines (a sign of generated data).
WITH per_rate AS (SELECT discount_rate, count(*) AS n FROM fact_order_lines GROUP BY 1)
SELECT (SELECT round(corr(discount_rate, profit / gross_sales), 3) FROM fact_order_lines) AS corr_discount_vs_profit_pct_gross,
       (SELECT round(corr(discount_rate, profit / net_sales), 3) FROM fact_order_lines)   AS corr_discount_vs_profit_pct_net,
       (SELECT round(min(profit_ratio), 2) FROM fact_order_lines) AS min_profit_ratio,
       (SELECT round(max(profit_ratio), 2) FROM fact_order_lines) AS max_profit_ratio,
       count(*) AS distinct_discount_rates, min(n) AS min_lines_per_rate, max(n) AS max_lines_per_rate
FROM per_rate;

-- name: q2_discount_0_vs_25
-- The 0% and 25% bands have almost the same gross sales, so their profit can be compared directly.
SELECT max(gross_sales) FILTER (WHERE discount_band = '0%')  AS gross_sales_0pct,
       max(gross_sales) FILTER (WHERE discount_band = '25%') AS gross_sales_25pct,
       max(profit) FILTER (WHERE discount_band = '0%')       AS profit_0pct,
       max(profit) FILTER (WHERE discount_band = '25%')      AS profit_25pct,
       round(100.0 * (max(profit) FILTER (WHERE discount_band = '25%') / max(profit) FILTER (WHERE discount_band = '0%') - 1), 1) AS profit_change_pct
FROM mart_discount_bands;

-- name: q3_window
SELECT w.first_week, w.last_week, w.break_week, w.last_week_in_file,
       (SELECT round(avg(lines), 0) FROM mart_weekly_volume v WHERE v.week_start BETWEEN w.first_week AND w.last_week) AS avg_lines_per_week_before,
       (SELECT round(avg(lines_per_order), 2) FROM mart_weekly_volume v WHERE v.week_start BETWEEN w.first_week AND w.last_week) AS lines_per_order_before,
       (SELECT round(avg(lines), 0) FROM mart_weekly_volume v WHERE v.week_start > w.break_week AND v.days_with_orders = 7) AS avg_lines_per_week_after,
       (SELECT round(avg(lines_per_order), 2) FROM mart_weekly_volume v WHERE v.week_start > w.break_week) AS lines_per_order_after,
       (SELECT count(*) FROM fact_order_lines f JOIN dim_date d ON d.date_key = f.order_date_key WHERE d.week_start >= w.break_week) AS lines_excluded_after_break
FROM forecast_window w;

-- name: q3_annual_units
-- Units by order year. Jan-Sep is used for a fair YoY because 2017 stops at the break.
SELECT d.year,
       sum(f.quantity) FILTER (WHERE d.month <= 9) AS units_jan_sep,
       round(100.0 * (sum(f.quantity) FILTER (WHERE d.month <= 9)
             / LAG(sum(f.quantity) FILTER (WHERE d.month <= 9)) OVER (ORDER BY d.year) - 1), 1) AS yoy_jan_sep_pct,
       sum(f.quantity) AS units_full_year_in_file
FROM fact_order_lines f JOIN dim_date d ON d.date_key = f.order_date_key
GROUP BY d.year ORDER BY d.year;

-- name: q3_volatility
-- Weekly demand volatility (coefficient of variation) for categories with 100+ units a week on average.
SELECT category_name, round(avg(units), 0) AS avg_weekly_units, round(stddev_samp(units), 1) AS sd_weekly_units,
       round(100.0 * stddev_samp(units) / avg(units), 1) AS cv_pct
FROM mart_weekly_category_demand WHERE in_forecast_window
GROUP BY 1 HAVING avg(units) >= 100 ORDER BY cv_pct DESC;

-- name: q3_forecast_accuracy
SELECT series, model, wape_pct, mape_pct, bias_pct
FROM forecast_accuracy WHERE model NOT LIKE 'ETS (not selected)%'
ORDER BY series = 'All categories' DESC, series, wape_pct;

-- name: q3_forecast_summary
-- Average holdout WAPE across the 6 series, per model family.
SELECT CASE WHEN model LIKE 'ETS, AICc%' THEN 'ETS (AICc-selected)' ELSE model END AS model,
       round(avg(wape_pct), 2) AS avg_wape_pct,
       round(avg(wape_pct) FILTER (WHERE series = 'All categories'), 2) AS wape_all_categories_pct,
       count(*) AS series
FROM forecast_accuracy WHERE model NOT LIKE 'ETS (not selected)%'
GROUP BY 1 ORDER BY avg_wape_pct;

-- name: q3_future_total
SELECT min(week_start) AS first_week, max(week_start) AS last_week, round(avg(forecast), 0) AS avg_weekly_units_forecast,
       round(avg(lower_80), 0) AS avg_lower_80, round(avg(upper_80), 0) AS avg_upper_80
FROM forecast_weekly WHERE split = 'future' AND series = 'All categories';

-- name: q4_whatif_one_day
-- One extra promised day (or one day faster shipping) for a single mode, everything else unchanged.
SELECT shipping_mode, promised_days, new_promise, late_lines_now, late_lines_if, late_lines_avoided,
       round(100.0 * late_lines_avoided / late_lines_all_modes_now, 1) AS pct_of_all_late_avoided,
       round(100.0 * (late_lines_all_modes_now - late_lines_avoided)
             / (SELECT count(*) FROM fact_order_lines WHERE NOT is_cancelled), 1) AS overall_late_pct_after,
       RANK() OVER (ORDER BY late_lines_avoided DESC) AS rank
FROM mart_whatif_promise WHERE extra_days = 1 ORDER BY rank;

-- name: q4_whatif_full_grid
SELECT shipping_mode, promised_days, new_promise, extra_days, shipped_lines, late_lines_if, late_lines_avoided
FROM mart_whatif_promise WHERE extra_days >= 0 ORDER BY promised_days, new_promise;
