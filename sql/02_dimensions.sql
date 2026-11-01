-- 02_dimensions.sql
-- Dimensions of the star schema.

-- dim_date: one row per calendar day from the first order to the last shipment.
CREATE OR REPLACE TABLE dim_date AS
WITH bounds AS (
    SELECT min(order_date) AS d0, max(ship_date) AS d1 FROM stg_order_lines
)
SELECT
    CAST(strftime(d, '%Y%m%d') AS INTEGER)       AS date_key,
    CAST(d AS DATE)                               AS date,
    year(d)                                       AS year,
    quarter(d)                                    AS quarter,
    'Q' || quarter(d)                             AS quarter_name,
    month(d)                                      AS month,
    strftime(d, '%b')                             AS month_name,
    strftime(d, '%Y-%m')                          AS year_month,
    CAST(date_trunc('week', d) AS DATE)           AS week_start,   -- ISO week, Monday start
    isoyear(d)                                    AS iso_year,
    weekofyear(d)                                 AS iso_week,
    isodow(d)                                     AS iso_weekday,
    strftime(d, '%a')                             AS weekday_name,
    isodow(d) >= 6                                AS is_weekend
FROM bounds, generate_series(d0, d1, INTERVAL 1 DAY) AS g(d);

-- dim_product: 118 products with their category and department.
CREATE OR REPLACE TABLE dim_product AS
SELECT
    product_card_id          AS product_key,
    any_value(product_name)  AS product_name,
    any_value(unit_price)    AS list_price,
    any_value(category_id)   AS category_id,
    any_value(category_name) AS category_name,
    any_value(department_id) AS department_id,
    any_value(department_name) AS department_name
FROM stg_order_lines
GROUP BY product_card_id;

-- dim_customer: customer attributes without personal data.
CREATE OR REPLACE TABLE dim_customer AS
SELECT
    customer_id                 AS customer_key,
    any_value(customer_segment) AS segment,
    any_value(customer_city)    AS city,
    any_value(customer_state)   AS state,
    any_value(customer_country) AS country
FROM stg_order_lines
GROUP BY customer_id;

-- dim_market: where the order is delivered (market > region > country).
CREATE OR REPLACE TABLE dim_market AS
SELECT
    CAST(row_number() OVER (ORDER BY market, order_region, order_country) AS INTEGER) AS market_key,
    market,
    order_region,
    order_country
FROM (SELECT DISTINCT market, order_region, order_country FROM stg_order_lines);

-- dim_shipping_mode: the four modes with the delivery promise (scheduled days).
CREATE OR REPLACE TABLE dim_shipping_mode AS
SELECT
    CAST(row_number() OVER (ORDER BY min(days_scheduled)) AS INTEGER) AS shipping_mode_key,
    shipping_mode,
    min(days_scheduled) AS promised_days,
    count(DISTINCT days_scheduled) AS n_promises   -- validated = 1 in src/validate.py
FROM stg_order_lines
GROUP BY shipping_mode;
