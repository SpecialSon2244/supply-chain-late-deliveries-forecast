# Tableau Public build spec

This file describes how to build the dashboard in Tableau Public web authoring
from `supply_chain_late_deliveries.xlsx`. Every chart uses one sheet of that
file as is. No calculated fields, joins or table calculations are needed.

The web editor is slow, so build one sheet at a time, save after each one
(File, Save to Tableau Public As), and only then build the dashboard.

Facts about the file:

- Size: about 0.05 MB (Tableau Public accepts up to 1 GB).
- All percentages are stored as numbers from 0 to 100 (57.3 means 57.3%).
  Do not use Tableau's "Percentage" format, it would show 5730%.
- Money is in US dollars, rounded to whole dollars.
- "Late" means the line shipped in more days than the shipping mode promised
  (`Late_delivery_risk = 1` in the source). Cancelled lines (7,754) never
  shipped and are left out of the late %.
- Order dates: 1 Jan 2015 to 31 Jan 2018. The forecast sheet stops at the
  week of 25 Sep 2017 because the data changes shape after that (see README).
- The `about` sheet holds notes only. Do not chart it.
- Extra sheets that are not on the dashboard but are there if you want more:
  `late_by_region`, `late_by_category`, `schedule_vs_actual`,
  `forecast_accuracy`, `whatif`, `monthly_mode`.

## Colours

| Value | Hex | Used in |
|---|---|---|
| Same Day | `#2A9D8F` (teal) | late by mode |
| First Class | `#E76F51` (coral) | late by mode |
| Second Class | `#F4A261` (sand) | late by mode |
| Standard Class | `#264653` (dark blue) | late by mode |
| Late | `#C0392B` (red) | profit at risk |
| On time or early | `#2A9D8F` (teal) | profit at risk |
| Cancelled | `#8D99AE` (grey) | profit at risk |
| Single-colour bars | `#264653` (dark blue) | late by market, discount bars |
| Line: Profit % of list price | `#C0392B` (red) | discount vs margin |
| Line: Actual | `#264653` | forecast |
| Line: ETS forecast (holdout) | `#E76F51` | forecast |
| Line: Seasonal naive (holdout) | `#8D99AE` | forecast |
| Line: ETS forecast (next 12 weeks) | `#2A9D8F` | forecast |

These are the same colours as the PNG charts in `images/`. To set them: click
the Color legend menu, Edit Colors, click a value, type the hex. If the web
editor offers no hex input, pick the closest swatch and note which one.
Do not leave the default blue: every sheet below says which colour to use.

## Number formats

| Field | Format |
|---|---|
| Any "%" field | Number (Custom), 1 decimal, suffix `%` |
| Order lines, Shipped lines, Late lines, Units, Lower 80, Upper 80 | Number (Custom), 0 decimals, thousands separator on |
| Profit, Late profit, Net sales, List-price sales, Discount | Currency (Custom), 0 decimals, prefix `$`, Display Units Thousands (K) for axes |
| Promised days, Avg actual days | Number (Custom), 1 decimal |

Set it once per field: Data pane, field menu, Default Properties, Number
Format. If that menu is missing, use the pill menu on Label or axis, Format.

## Step 0. Connect the data

1. Sign in to public.tableau.com, My Profile, Create, Web Authoring.
2. Connect to Data, Files, upload `supply_chain_late_deliveries.xlsx`.
3. Drag `kpis` onto the canvas. Rename the data source (top left) to `kpis`.
4. For each of `late_by_mode`, `late_by_market`, `profit_at_risk`,
   `discount_margin`, `forecast`: Data pane, New Data Source, upload the same
   file, drag only that sheet onto the canvas, rename the data source to the
   sheet name. You end with 6 data sources.
5. Do not join or relate the sheets. They have different grains and a join
   would double count.

Field roles to check (field menu, Convert to Dimension / Discrete if needed):

- Text fields (KPI, Value label, Shipping mode, Market, Delivery outcome,
  Discount band, Series, Line, Period) are dimensions.
- Sort, Mode order, Outcome order and Band order are numbers used only to sort.
- `Week start` in `forecast` must be a Date (calendar icon). If it shows as
  text: field menu, Change Data Type, Date.

Each sheet below has one row per mark, so SUM() of a % just returns the stored
value. Keep the default SUM aggregation.

## Dashboard: "Why are 57% of orders late, and what would fix it?"

### Sheet 1. KPI strip

- Data source: `kpis` (7 rows)
- Columns: KPI (discrete). Sort: field Sort, Sum, Ascending.
- Rows: nothing
- Marks: Text
- Text: Value label, then KPI. Edit the Text: line 1 `<Value label>` bold
  20 pt `#264653`, line 2 `<KPI>` 9 pt grey `#555555`. Centre aligned.
- Hide the column header (KPI pill menu, untick Show Header), because the KPI
  name is already in the text.
- Format, Borders: Column Divider, thin light grey.
- Tooltip: off.
- View: Fit, Entire View. This is what stops the cut-off seen in the HR
  dashboard: the strip gets its own 110 px height on the dashboard (see
  Layout) and the text scales into it. If a label still wraps, drop the value
  to 18 pt.
- Title: hide (sheet menu, untick Show Title).

Expected values, left to right: 180,519 · 57.3% · 2.9 vs 3.5 · 7,754 ·
$3.97M · $2.30M (58%) · 2.9% vs 6.8%.

### Sheet 2. Late by shipping mode

- Data source: `late_by_mode` (4 rows)
- Rows: Shipping mode. Sort: field Mode order, Sum, Ascending
  (Same Day, First Class, Second Class, Standard Class).
- Columns: SUM(Late %)
- Marks: Bar
- Color: Shipping mode (colours above)
- Label: SUM(Late %), shown at the bar end
- Tooltip: Promised days, Avg actual days, Shipped lines, Late lines,
  Share of all late %
- Axis: fixed 0 to 100, title "Shipped lines late (%)"
- Hide the colour legend (the row labels already name the modes)
- Title: "First Class is late 100% of the time: it promises 1 day and always takes 2"
- Caption (optional): "Standard Class ships 59.7% of lines and causes 41.4% of all late lines."

### Sheet 3. Late by market

- Data source: `late_by_market` (5 rows)
- Rows: Market. Sort: field Late %, Sum, Descending.
- Columns: SUM(Late %)
- Marks: Bar, colour `#264653`
- Label: SUM(Late %)
- Tooltip: Shipped lines, Late lines, Profit, Late profit
- Axis: fixed 0 to 100, title "Shipped lines late (%)"
- Title: "Every market is late 57 to 58% of the time, so geography is not the cause"

### Sheet 4. Profit at risk

- Data source: `profit_at_risk` (3 rows)
- Rows: Delivery outcome. Sort: field Outcome order, Sum, Ascending
  (On time or early, Late, Cancelled).
- Columns: SUM(Profit)
- Marks: Bar
- Color: Delivery outcome (On time or early `#2A9D8F`, Late `#C0392B`,
  Cancelled `#8D99AE`)
- Label: SUM(Profit) and SUM(Share of profit %). Edit the label to
  `<SUM(Profit)>  (<SUM(Share of profit %)>)`, e.g. "$2,140,052 (53.9%)".
- Tooltip: Order lines, Net sales, Margin %
- Axis: title "Profit (USD)", Display Units Thousands
- Hide the colour legend
- Title: "$2.30M of $3.97M profit (58%) sits on late or cancelled lines"

### Sheet 5. Discount vs margin

- Data source: `discount_margin` (6 rows)
- Columns: Discount band. Sort: field Band order, Sum, Ascending
  (0%, 1-5%, 6-10%, 11-15%, 16-20%, 25%).
- Rows: SUM(Profit % of list price)
- Marks: Line with markers (Marks card, Path, then Color, Markers: all),
  colour `#C0392B`
- Label: SUM(Profit % of list price), all marks
- Tooltip: Order lines, List-price sales, Discount, Profit,
  Profit % after discount, Loss-making lines %
- Axis: fixed 8 to 14, title "Profit as % of list price"
- Title: "Profit falls from 13.1% of list price at no discount to 9.4% at 25%"
- Caption (optional): "After the discount the margin stays at 11.7 to 13.1%:
  the discount comes straight out of profit, volume does not rise to make up for it."
- If you prefer bars, use Bar with colour `#264653` and the same fields.

### Sheet 6. Forecast vs actual

- Data source: `forecast` (1,086 rows, 6 series)
- Filter: Series. Show filter, Single value (dropdown), default "All categories".
  The options are All categories, Cleats, Women's Apparel,
  Indoor/Outdoor Games, Cardio Equipment, Shop By Sport.
- Filter: Week start, range 4 Jul 2016 to 18 Dec 2017 (shows the last year
  of training, the 13-week holdout and the 12 future weeks; use the full
  range if you like).
- Columns: WEEK(Week start), continuous (green pill: pill menu, Week Number
  under the second list of date parts, i.e. the continuous one)
- Rows: SUM(Units)
- Marks: Line
- Color: Line (Actual `#264653`, ETS forecast (holdout) `#E76F51`,
  Seasonal naive (holdout) `#8D99AE`, ETS forecast (next 12 weeks) `#2A9D8F`)
- Tooltip: Week start, Series, Line, Period, Units, Lower 80, Upper 80
- Optional band: drag SUM(Lower 80) and SUM(Upper 80) to the Rows shelf as a
  second axis is fiddly in the web editor. Skip it unless it works first time;
  the numbers are in the tooltip.
- Axis: untick "Include zero", title "Units per week"
- Show the colour legend, place it above the chart
- Title: "A simple ETS model misses weekly demand by 2.9% (WAPE); same-week-last-year misses by 6.8%"
- Caption (optional): "13-week holdout, 3 Jul to 25 Sep 2017. The week of 2
  Oct 2017 onwards is excluded because order volume drops by more than half
  and every order has one line."

## Layout

- Size: Fixed, 1200 x 1100 (Dashboard pane, Size, Custom).
- Use **Floating** objects and type the position and size of each one in the
  Layout pane (x, y, w, h). Dragging is unreliable in the web editor.
- Background: white. Each sheet: Format, Shading, white; no borders except
  the KPI strip dividers.

| Object | x | y | w | h | Notes |
|---|---|---|---|---|---|
| Text: title | 0 | 0 | 1200 | 50 | "Why are 57% of orders late, and what would fix it?" bold 22 pt `#264653` |
| Text: subtitle | 0 | 50 | 1200 | 40 | 11 pt grey: "DataCo Smart Supply Chain, 180,519 order lines, Jan 2015 to Jan 2018. Late = shipped in more days than the mode promised." |
| Sheet 1. KPI strip | 0 | 90 | 1200 | 110 | title hidden |
| Sheet 2. Late by mode | 0 | 200 | 600 | 280 | |
| Sheet 3. Late by market | 600 | 200 | 600 | 280 | |
| Sheet 4. Profit at risk | 0 | 480 | 600 | 280 | |
| Sheet 5. Discount vs margin | 600 | 480 | 600 | 280 | |
| Sheet 6. Forecast vs actual | 0 | 760 | 1000 | 300 | |
| Series filter (Sheet 6) | 1000 | 770 | 200 | 60 | floating dropdown |
| Line colour legend (Sheet 6) | 1000 | 840 | 200 | 120 | |
| Text: footer | 0 | 1060 | 1200 | 40 | 9 pt grey: "Data: Constante, Silva & Pereira (2019), DataCo Smart Supply Chain for Big Data Analysis, Mendeley Data, CC BY 4.0. Synthetic dataset. Code: github.com/SpecialSon2244/supply-chain-late-deliveries-forecast" |

- Remove every other legend and filter card Tableau adds automatically.
- Rename the dashboard tab to "Late deliveries" (not "Dashboard 1") and the
  sheet tabs to the names above.

## Before publishing

1. Check the KPI strip shows all 7 values with nothing cut off.
2. Check no sheet still uses the default blue.
3. Check the numbers against the "Expected values" line in Sheet 1 and the
   titles above (they are copied from `docs/findings_results.md`).
4. File, Save to Tableau Public As: "Supply chain late deliveries and demand forecast".
5. In the workbook settings on the profile, tick "Show workbook sheets as tabs" off,
   and set the dashboard as the thumbnail.
6. Copy the link into the README (Dashboard section) and LINKEDIN_POST.md.
