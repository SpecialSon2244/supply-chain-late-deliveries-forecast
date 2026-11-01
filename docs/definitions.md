# Definitions

| Term | Definition | Source columns |
|---|---|---|
| Order line | One row of the DataCo CSV: one product in one order. 180,519 lines, 65,752 orders. | `Order Item Id`, `Order Id` |
| Promised days | Days the shipping mode promises: Same Day 0, First Class 1, Second Class 2, Standard Class 4. Each mode has exactly one value (checked). | `Days for shipment (scheduled)` |
| Actual days | Days from order to shipping. Equal to ship date minus order date (checked). It is time to *ship*, not time to deliver. | `Days for shipping (real)` |
| Delay days | Actual days minus promised days. Negative = shipped early. | derived |
| Late | Shipped lines with actual days > promised days. Same as `Late_delivery_risk = 1` and `Delivery Status = 'Late delivery'` (checked). | `Late_delivery_risk` |
| On time | Shipped lines that are not late (`Shipping on time` or `Advance shipping`). | `Delivery Status` |
| Cancelled | `Delivery Status = 'Shipping canceled'`. Never shipped, so neither late nor on time. 7,754 lines. | `Delivery Status` |
| Late % | Late lines / shipped lines (cancelled lines left out of the base). 57.3% overall. On all lines it would be 54.8%. | derived |
| Suspected fraud | `Order Status = 'SUSPECTED_FRAUD'`. All of these are cancelled. | `Order Status` |
| Gross sales (list price sales) | Unit price x quantity, before discount. | `Sales` |
| Discount | Discount amount in USD. Discount rate = discount / gross sales, 0 to 25%. | `Order Item Discount`, `Order Item Discount Rate` |
| Discount band | 0%, 1-5%, 6-10%, 11-15%, 16-20%, 25% (the 18 rates in the data are 0, 1, 2, 3, 4, 5, 6, 7, 9, 10, 12, 13, 15, 16, 17, 18, 20 and 25%). | derived |
| Net sales | Gross sales minus discount. | `Order Item Total` |
| Profit | Profit per order line in USD, as given. Can be negative. | `Order Profit Per Order` |
| Margin % | Profit / net sales. | derived |
| Profit % of list price | Profit / gross sales. Shows the full effect of the discount. | derived |
| Loss-making line | Line with profit < 0. | derived |
| Profit at risk | Profit on lines that were late or cancelled: $2,300,534, 58.0% of all profit. An exposure (revenue that depends on a broken promise), not a measured loss. | derived |
| Week | ISO week starting Monday (`dim_date.week_start`). | derived |
| Comparable window | Weeks from 2015-01-05 to 2017-09-25. Detected in `sql/04_regime.sql` as the weeks before the first "break" week (lines < 60% of the trailing 12-week median and < 1.2 lines per order). Used for the forecast and YoY. | derived |
| Holdout | The last 13 weeks of the window (2017-07-03 to 2017-09-25). Models are fitted on the 130 weeks before and never see these weeks. | derived |
| WAPE | Sum of absolute errors / sum of actual units over the holdout. Main accuracy measure. | derived |
| MAPE | Average of weekly absolute % errors. | derived |
| Bias % | Sum of (forecast - actual) / sum of actual. Positive = forecast too high. | derived |
| Naive | Forecast = last training week, for every holdout week. | derived |
| Seasonal naive | Forecast = same week one year (52 weeks) earlier. | derived |
| 4-week moving average | Forecast = mean of the last 4 training weeks. | derived |
| ETS | Exponential smoothing (statsmodels `ETSModel`). Candidates ETS(A,N,N), ETS(A,Ad,N) and ETS(A,N,A) with a 52-week season; the one with the lowest AICc on the training weeks is used. | derived |
| What-if | Late lines if one mode promised a different number of days (0 to 6), with actual days unchanged: lines with actual > new promise. | derived |
