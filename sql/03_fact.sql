-- 03_fact.sql
-- fact_order_lines: one row per order line (grain = Order Item Id).
-- Late rule in the source: late_delivery_risk = 1 when actual shipping days > scheduled days,
-- except cancelled lines, which are always 0. Rates in this project use shipped
-- (not cancelled) lines as the base. See docs/definitions.md.
CREATE OR REPLACE TABLE fact_order_lines AS
SELECT
    s.order_line_id,
    s.order_id,
    CAST(strftime(s.order_date, '%Y%m%d') AS INTEGER) AS order_date_key,
    CAST(strftime(s.ship_date,  '%Y%m%d') AS INTEGER) AS ship_date_key,
    s.order_ts,
    s.product_card_id                     AS product_key,
    s.customer_id                         AS customer_key,
    m.market_key,
    sm.shipping_mode_key,
    s.payment_type,
    s.order_status,
    s.delivery_status,
    s.days_scheduled,
    s.days_actual,
    s.days_actual - s.days_scheduled      AS delay_days,
    s.delivery_status = 'Shipping canceled'                        AS is_cancelled,
    s.order_status = 'SUSPECTED_FRAUD'                             AS is_suspected_fraud,
    CAST(s.late_delivery_risk AS BOOLEAN)                          AS is_late,
    s.delivery_status <> 'Shipping canceled' AND s.late_delivery_risk = 0 AS is_on_time,
    s.quantity,
    s.unit_price,
    s.gross_sales,
    s.discount_amount,
    s.discount_rate,
    s.net_sales,
    s.profit,
    s.profit_ratio,
    s.profit < 0                          AS is_loss,
    CASE
        WHEN s.discount_rate = 0      THEN '0%'
        WHEN s.discount_rate <= 0.05  THEN '1-5%'
        WHEN s.discount_rate <= 0.10  THEN '6-10%'
        WHEN s.discount_rate <= 0.15  THEN '11-15%'
        WHEN s.discount_rate <= 0.20  THEN '16-20%'
        ELSE '25%'
    END                                   AS discount_band
FROM stg_order_lines s
JOIN dim_market m
  ON m.market = s.market AND m.order_region = s.order_region AND m.order_country = s.order_country
JOIN dim_shipping_mode sm
  ON sm.shipping_mode = s.shipping_mode;
