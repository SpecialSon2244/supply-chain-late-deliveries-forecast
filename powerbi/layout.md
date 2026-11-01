# Power BI page layout

Canvas: 16:9, 1280 x 720 (Format, Canvas settings). Theme colours, so the
report matches the PNG charts and the Tableau dashboard:

| Use | Hex |
|---|---|
| Same Day / On time | `#2A9D8F` |
| First Class | `#E76F51` |
| Second Class | `#F4A261` |
| Standard Class / default bars | `#264653` |
| Late | `#C0392B` |
| Cancelled | `#8D99AE` |

Positions are x, y, width, height in pixels (Format pane, General, Properties).

## Page 1. Late deliveries

| Visual | x | y | w | h | Fields |
|---|---|---|---|---|---|
| Text box: title | 20 | 10 | 900 | 45 | "Why are 57% of orders late?" 24 pt bold |
| Slicer: year | 940 | 10 | 320 | 45 | dim_date[year], tile style |
| Card | 20 | 65 | 240 | 95 | Order Lines |
| Card | 270 | 65 | 240 | 95 | Late % |
| Card | 520 | 65 | 240 | 95 | Avg Promised Days |
| Card | 770 | 65 | 240 | 95 | Avg Actual Days |
| Card | 1020 | 65 | 240 | 95 | Cancelled Lines |
| Clustered bar | 20 | 175 | 620 | 260 | Y: dim_shipping_mode[shipping_mode]; X: Late %; tooltip: Shipped Lines, Share of All Late %; data colours per mode |
| Clustered bar | 660 | 175 | 600 | 260 | Y: dim_market[market]; X: Late %; sort by Late % descending; X axis 0 to 1 |
| Line chart | 20 | 450 | 1240 | 255 | X: dim_date[year_month]; Y: Late %; legend: dim_shipping_mode[shipping_mode]; page filter dim_date[in_comparable_window] = True |

## Page 2. Profit at risk

| Visual | x | y | w | h | Fields |
|---|---|---|---|---|---|
| Text box: title | 20 | 10 | 1240 | 45 | "58% of profit sits on late or cancelled lines" |
| Card | 20 | 65 | 300 | 95 | Profit |
| Card | 330 | 65 | 300 | 95 | Profit at Risk |
| Card | 640 | 65 | 300 | 95 | Profit at Risk % |
| Card | 950 | 65 | 310 | 95 | Margin % |
| Clustered bar | 20 | 175 | 620 | 260 | Y: fact_order_lines[delivery_status]; X: Profit; tooltip: Margin % |
| Line and clustered column | 660 | 175 | 600 | 260 | X: dim_discount_band[discount_band]; columns: Profit; line: Profit % of List Price |
| Matrix | 20 | 450 | 1240 | 255 | Rows: dim_product[department_name], dim_product[category_name]; values: Shipped Lines, Late %, Profit, Profit at Risk %, Loss-making Lines % |

## Page 3. Forecast and what-if

| Visual | x | y | w | h | Fields |
|---|---|---|---|---|---|
| Text box: title | 20 | 10 | 900 | 45 | "Weekly demand forecast, 13-week holdout" |
| Slicer: series | 940 | 10 | 320 | 45 | forecast_weekly[series], dropdown, single select, default "All categories" |
| Line chart | 20 | 65 | 900 | 330 | X: forecast_weekly[week_start] (continuous); Y: Actual Units (forecast table), ETS Forecast, Seasonal Naive Forecast, ETS Lower 80, ETS Upper 80 (dashed, grey) |
| Card | 940 | 65 | 320 | 100 | ETS WAPE % |
| Card | 940 | 175 | 320 | 100 | Seasonal Naive WAPE % |
| Card | 940 | 285 | 320 | 110 | ETS Bias % |
| Table | 20 | 410 | 620 | 295 | forecast_accuracy: series, model, wape_pct, mape_pct, bias_pct (sort series, then wape_pct) |
| Clustered bar | 660 | 410 | 600 | 295 | whatif_promise filtered to extra_days = 1; Y: shipping_mode; X: late_lines_avoided; title "Add one promised day: late lines avoided" |
