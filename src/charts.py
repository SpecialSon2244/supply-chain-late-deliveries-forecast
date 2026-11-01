"""Static Plotly charts for the README -> images/*.png (all numbers come from data/supply_chain.duckdb)."""
import pathlib

import duckdb
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

ROOT = pathlib.Path(__file__).resolve().parents[1]
IMG = ROOT / "images"
IMG.mkdir(exist_ok=True)
con = duckdb.connect(str(ROOT / "data" / "supply_chain.duckdb"), read_only=True)

MODE_COLORS = {"Same Day": "#2A9D8F", "First Class": "#E76F51", "Second Class": "#F4A261", "Standard Class": "#264653"}
LATE, ONTIME, CANCEL, GREY = "#C0392B", "#2A9D8F", "#8D99AE", "#6C757D"
SOURCE = "Data: DataCo Smart Supply Chain (Mendeley Data, CC BY 4.0), 2015-2018 order lines."
FONT = dict(family="Arial", size=13, color="#222")


def style(fig, title, subtitle, h=520, w=1000, legend=True):
    fig.update_layout(title=dict(text=f"<b>{title}</b><br><span style='font-size:13px;color:{GREY}'>{subtitle}</span>",
                                 x=0.01, xanchor="left", y=0.97, yanchor="top"),
                      font=FONT, template="simple_white", height=h, width=w,
                      margin=dict(t=130 if legend else 110, b=100, l=80, r=30),
                      legend=dict(orientation="h", y=1.01, yanchor="bottom", x=0, xanchor="left"),
                      showlegend=legend)
    fig.add_annotation(text=SOURCE, xref="paper", yref="paper", x=0, y=0, yshift=-80, yanchor="top",
                       showarrow=False, font=dict(size=10, color=GREY), xanchor="left")
    return fig


def save(fig, name):
    fig.write_image(IMG / name, scale=2)
    print(f"wrote images/{name}")


# 1. Late rate by shipping mode, with promise vs actual days.
d = con.sql("""SELECT sm.shipping_mode, sm.promised_days,
                      100.0 * count(*) FILTER (WHERE is_late) / count(*) FILTER (WHERE NOT is_cancelled) AS late_pct,
                      avg(days_actual) FILTER (WHERE NOT is_cancelled) AS avg_actual,
                      count(*) FILTER (WHERE NOT is_cancelled) AS shipped
               FROM fact_order_lines JOIN dim_shipping_mode sm USING (shipping_mode_key)
               GROUP BY ALL ORDER BY promised_days""").df()
overall = con.sql("SELECT 100.0 * count(*) FILTER (WHERE is_late) / count(*) FILTER (WHERE NOT is_cancelled) FROM fact_order_lines").fetchall()[0][0]
fig = go.Figure(go.Bar(x=d.shipping_mode, y=d.late_pct, marker_color=[MODE_COLORS[m] for m in d.shipping_mode],
                       text=[f"{v:.1f}%<br><span style='font-size:11px'>promise {p} d, actual avg {a:.1f} d</span>"
                             for v, p, a in zip(d.late_pct, d.promised_days, d.avg_actual)],
                       textposition="outside"))
fig.add_hline(y=overall, line_dash="dash", line_color=GREY, annotation_text=f"All modes {overall:.1f}%",
              annotation_position="top right")
fig.update_yaxes(range=[0, 115], title="Shipped order lines late (%)")
save(style(fig, "Every First Class order line ships late",
           "Late = actual shipping days above the scheduled days. Base: shipped (not cancelled) lines.", legend=False),
     "01_late_rate_by_mode.png")

# 2. Promise vs reality: distribution of actual shipping days per mode.
d = con.sql("SELECT * FROM mart_schedule_vs_actual ORDER BY promised_days, days_actual").df()
fig = go.Figure()
for day in sorted(d.days_actual.unique()):
    s = d[d.days_actual == day]
    fig.add_trace(go.Bar(y=[f"{m} (promise {p} d)" for m, p in zip(s.shipping_mode, s.promised_days)],
                         x=s.share_of_mode_pct, orientation="h", name=f"{day} d",
                         marker_color=[LATE if late else ONTIME for late in s.is_late],
                         marker_opacity=0.45 + 0.09 * day, text=[f"{day} d" for _ in s.index],
                         textposition="inside", insidetextanchor="middle", showlegend=False))
fig.update_layout(barmode="stack")
fig.update_xaxes(title="Share of the mode's shipped lines (%)", range=[0, 100])
fig.update_yaxes(categoryorder="array", categoryarray=list(dict.fromkeys(
    f"{m} (promise {p} d)" for m, p in zip(d.shipping_mode[::-1], d.promised_days[::-1]))))
save(style(fig, "Promise vs reality: actual shipping days per mode",
           "Green = within the promise, red = late. Second and Standard Class take 2 to 6 days in almost equal shares.", legend=False),
     "02_promise_vs_actual.png")

# 3. Late rate by market (and region spread).
d = con.sql("""SELECT m.market, 100.0 * count(*) FILTER (WHERE is_late) / count(*) FILTER (WHERE NOT is_cancelled) AS late_pct
               FROM fact_order_lines JOIN dim_market m USING (market_key) GROUP BY 1 ORDER BY 2""").df()
fig = go.Figure(go.Bar(y=d.market, x=d.late_pct, orientation="h", marker_color="#264653",
                       text=[f"{v:.1f}%" for v in d.late_pct], textposition="outside"))
fig.update_xaxes(range=[0, 70], title="Shipped order lines late (%)")
save(style(fig, "Late rates are almost the same in every market",
           f"56.8% to 57.7% across the five markets: the problem is the shipping mode, not the region.", h=440, legend=False),
     "03_late_rate_by_market.png")

# 4. Profit by delivery outcome (profit at risk).
d = con.sql("""SELECT CASE WHEN is_cancelled THEN 'Cancelled' WHEN is_late THEN 'Late' ELSE 'On time or early' END AS g,
                      sum(profit) AS profit, 100.0 * sum(profit) / sum(net_sales) AS margin
               FROM fact_order_lines GROUP BY 1""").df().set_index("g").loc[["On time or early", "Late", "Cancelled"]]
total = d.profit.sum()
fig = go.Figure(go.Bar(x=d.index, y=d.profit / 1e6, marker_color=[ONTIME, LATE, CANCEL],
                       text=[f"${p / 1e6:.2f}M ({100 * p / total:.0f}% of profit)<br>margin {m:.1f}%"
                             for p, m in zip(d.profit, d.margin)], textposition="outside"))
fig.update_yaxes(title="Profit (USD millions)", range=[0, 2.8])
save(style(fig, f"58% of profit sits on late or cancelled order lines",
           f"Total profit ${total / 1e6:.2f}M. Profit at risk = profit on late lines + profit on cancelled lines.", legend=False),
     "04_profit_at_risk.png")

# 5. Discount bands vs margin.
d = con.sql("SELECT * FROM mart_discount_bands ORDER BY min_rate").df()
fig = go.Figure()
fig.add_trace(go.Bar(x=d.discount_band, y=d.profit_pct_of_gross, name="Profit as % of list-price sales",
                     marker_color="#E76F51", text=[f"{v:.1f}%" for v in d.profit_pct_of_gross], textposition="outside"))
fig.add_trace(go.Bar(x=d.discount_band, y=d.profit_pct_of_net, name="Profit as % of sales after discount",
                     marker_color="#264653", text=[f"{v:.1f}%" for v in d.profit_pct_of_net], textposition="outside"))
fig.update_layout(barmode="group")
fig.update_xaxes(title="Discount band (rate on the order line)")
fig.update_yaxes(title="Profit margin (%)", range=[0, 16])
save(style(fig, "Discounts come straight out of profit",
           "Margin on list price falls from 13.1% (no discount) to 9.4% (25% off). Margin after discount stays near 12%."),
     "05_discount_vs_margin.png")

# 6. Weekly volume and the detected break.
d = con.sql("SELECT * FROM mart_weekly_volume ORDER BY week_start").df()
w = con.sql("SELECT * FROM forecast_window").df().iloc[0]
fig = go.Figure(go.Scatter(x=d.week_start, y=d.lines, mode="lines", line=dict(color="#264653", width=2), name="Order lines per week"))
fig.add_vrect(x0=w.break_week, x1=d.week_start.max(), fillcolor=CANCEL, opacity=0.25, line_width=0,
              annotation_text="Excluded: ~480 lines a week,<br>one line per order", annotation_position="top left")
fig.update_yaxes(title="Order lines per week", range=[0, 1500])
save(style(fig, "The file changes character in October 2017",
           f"From the week of {w.break_week:%d %b %Y} volume drops by 60% and every order has one line. "
           "Trend and forecast use 5 Jan 2015 to 1 Oct 2017.", h=460, legend=False),
     "06_weekly_volume_break.png")

# 7. Forecast vs actual (all categories).
fw = con.sql("SELECT * FROM forecast_weekly WHERE series = 'All categories' ORDER BY week_start").df()
tr = fw[(fw.split == "train") & (fw.week_start >= fw[fw.split == "holdout"].week_start.min() - pd.Timedelta(weeks=52))]
ho = fw[fw.split == "holdout"]
fu = fw[fw.split == "future"]
acc = con.sql("SELECT model, wape_pct FROM forecast_accuracy WHERE series = 'All categories'").df().set_index("model").wape_pct
ets_name = [m for m in acc.index if m.startswith("ETS, AICc")][0]
fig = go.Figure()
fig.add_trace(go.Scatter(x=tr.week_start, y=tr.actual, name="Actual (training)", line=dict(color="#264653")))
act = ho[ho.model == "ETS"]
fig.add_trace(go.Scatter(x=act.week_start, y=act.actual, name="Actual (holdout)", line=dict(color="#000", width=3)))
fig.add_trace(go.Scatter(x=act.week_start, y=act.forecast, name=f"ETS forecast (WAPE {acc[ets_name]:.1f}%)",
                         line=dict(color="#E76F51", width=3, dash="dash")))
sn = ho[ho.model == "Seasonal naive"]
fig.add_trace(go.Scatter(x=sn.week_start, y=sn.forecast,
                         name=f"Seasonal naive (WAPE {acc['Seasonal naive (same week last year)']:.1f}%)",
                         line=dict(color=GREY, dash="dot")))
fig.add_trace(go.Scatter(x=list(fu.week_start) + list(fu.week_start[::-1]), y=list(fu.upper_80) + list(fu.lower_80[::-1]),
                         fill="toself", fillcolor="rgba(231,111,81,0.18)", line=dict(width=0), name="Next 12 weeks, 80% interval"))
fig.add_trace(go.Scatter(x=fu.week_start, y=fu.forecast, name="Next 12 weeks (ETS)", line=dict(color="#E76F51")))
fig.update_yaxes(title="Units ordered per week (axis starts at 1,800)", range=[1800, 3100])
save(style(fig, "Weekly demand: ETS beats the seasonal naive baseline on a 13-week holdout",
           "All categories. Holdout 3 Jul to 1 Oct 2017. The next 12 weeks cannot be checked: the file's later weeks are a cut-off extract.",
           h=540, w=1100), "07_forecast_vs_actual.png")

# 8. Holdout WAPE by series and model.
a = con.sql("""SELECT series, CASE WHEN model LIKE 'ETS, AICc%' THEN 'ETS (AICc-selected)' ELSE model END AS model, wape_pct
               FROM forecast_accuracy WHERE model NOT LIKE 'ETS (not selected)%'""").df()
order = ["All categories"] + sorted(s for s in a.series.unique() if s != "All categories")
colors = {"ETS (AICc-selected)": "#E76F51", "Naive (last week)": "#8D99AE",
          "4-week moving average": "#2A9D8F", "Seasonal naive (same week last year)": "#264653"}
fig = go.Figure()
for m, c in colors.items():
    s = a[a.model == m].set_index("series").reindex(order)
    fig.add_trace(go.Bar(x=order, y=s.wape_pct, name=m, marker_color=c, text=[f"{v:.1f}" for v in s.wape_pct],
                         textposition="outside", textfont=dict(size=10)))
fig.update_layout(barmode="group")
fig.update_yaxes(title="Holdout WAPE (%), lower is better", range=[0, 18])
save(style(fig, "Forecast error on the 13-week holdout",
           "ETS has the lowest average WAPE (7.2%) across the six series; seasonal naive is worst (10.3%). "
           "For Indoor/Outdoor Games AICc picked a seasonal ETS that overfits.", h=540, w=1100),
     "08_forecast_accuracy.png")

# 9. What-if: one more promised day per mode.
d = con.sql("SELECT * FROM mart_whatif_promise WHERE extra_days = 1 ORDER BY late_lines_avoided").df()
fig = go.Figure(go.Bar(y=[f"{m}: {p} -> {n} d" for m, p, n in zip(d.shipping_mode, d.promised_days, d.new_promise)],
                       x=d.late_lines_avoided, orientation="h", marker_color=[MODE_COLORS[m] for m in d.shipping_mode],
                       text=[f"{int(v):,} fewer late lines ({100 * v / t:.1f}% of all late)"
                             for v, t in zip(d.late_lines_avoided, d.late_lines_all_modes_now)], textposition="outside"))
fig.update_xaxes(title="Late order lines avoided", range=[0, 38000])
save(style(fig, "The single biggest lever: First Class, promised 1 day, always takes 2",
           "What-if per mode, one day added to the promise (same as shipping one day faster), all else unchanged. "
           "Overall late rate 57.3% -> 41.9%.", h=440, w=1100, legend=False), "09_whatif_one_day.png")
