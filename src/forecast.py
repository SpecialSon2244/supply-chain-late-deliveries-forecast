"""Weekly demand forecast per category with a 13-week holdout.

Series: total units (all categories) and the 5 largest categories by units.
Window: the comparable weeks from sql/04_regime.sql (5 Jan 2015 to the week of
25 Sep 2017). The weeks after the break (Oct 2017 onwards) are not used: the file
changes to one line per order and about 40% of the volume, which is a data cut-off,
not demand.

Models
- naive: the last training week, repeated.
- seasonal naive: the same week one year earlier (lag 52).
- 4-week moving average: mean of the last 4 training weeks.
- ETS (statsmodels ETSModel): the specification is picked on the training data
  only, by lowest AICc among ANN, AAdN (damped trend) and ANA (additive weekly-of-year
  seasonality, 52 periods). The holdout is not used to choose the model.

Accuracy on the holdout: WAPE = sum|actual - forecast| / sum(actual); MAPE = mean of
|actual - forecast| / actual; bias = sum(forecast - actual) / sum(actual).
Writes forecast_weekly and forecast_accuracy into data/supply_chain.duckdb and
docs/forecast.md.
"""
import pathlib
import warnings

import duckdb
import numpy as np
import pandas as pd
from statsmodels.tsa.exponential_smoothing.ets import ETSModel

warnings.filterwarnings("ignore")
ROOT = pathlib.Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "supply_chain.duckdb"
HOLDOUT = 13
FUTURE = 12
TOP_N = 5
SPECS = {
    "ETS(A,N,N)": dict(error="add", trend=None, seasonal=None),
    "ETS(A,Ad,N)": dict(error="add", trend="add", damped_trend=True, seasonal=None),
    "ETS(A,N,A) s=52": dict(error="add", trend=None, seasonal="add", seasonal_periods=52),
}


def metrics(actual: np.ndarray, fc: np.ndarray) -> dict:
    err = fc - actual
    return {"wape_pct": 100 * np.abs(err).sum() / actual.sum(),
            "mape_pct": 100 * np.mean(np.abs(err) / actual),
            "bias_pct": 100 * err.sum() / actual.sum()}


def fit_best(y: pd.Series):
    fits = {}
    for name, kw in SPECS.items():
        try:
            res = ETSModel(y, initialization_method="estimated" if not kw.get("seasonal") else "heuristic",
                           **kw).fit(disp=False, maxiter=2000)
            fits[name] = res
        except Exception as exc:  # pragma: no cover - logged, not fatal
            print(f"  {name} failed: {exc}")
    best = min(fits, key=lambda k: fits[k].aicc)
    return best, fits


def main() -> None:
    con = duckdb.connect(str(DB))
    weekly = con.sql("""
        SELECT week_start, category_name, units FROM mart_weekly_category_demand
        WHERE in_forecast_window ORDER BY week_start""").df()
    top = (weekly.groupby("category_name")["units"].sum().sort_values(ascending=False).head(TOP_N).index.tolist())
    series = {"All categories": weekly.groupby("week_start")["units"].sum()}
    for c in top:
        series[c] = weekly[weekly.category_name == c].set_index("week_start")["units"]

    rows, acc, notes = [], [], []
    for name, y in series.items():
        y = y.astype(float).sort_index()
        y.index = pd.DatetimeIndex(y.index, freq="W-MON")
        train, test = y.iloc[:-HOLDOUT], y.iloc[-HOLDOUT:]
        best, fits = fit_best(train)
        preds = {
            "Naive (last week)": np.repeat(train.iloc[-1], HOLDOUT),
            "Seasonal naive (same week last year)": y.shift(52).iloc[-HOLDOUT:].to_numpy(),
            "4-week moving average": np.repeat(train.iloc[-4:].mean(), HOLDOUT),
            f"ETS, AICc-selected: {best}": fits[best].forecast(HOLDOUT).to_numpy(),
        }
        for spec, res in fits.items():
            if spec != best:
                preds[f"ETS (not selected): {spec}"] = res.forecast(HOLDOUT).to_numpy()
        for model, fc in preds.items():
            m = metrics(test.to_numpy(), fc)
            acc.append({"series": name, "model": model, "holdout_weeks": HOLDOUT,
                        "holdout_start": test.index[0].date(), "holdout_end": test.index[-1].date(),
                        "aicc": round(fits[model.split(": ")[1]].aicc, 1) if model.startswith("ETS") else None,
                        **{k: round(v, 2) for k, v in m.items()}})
            if model.startswith("ETS, AICc") or model.startswith("Seasonal") or model.startswith("Naive"):
                kind = "ETS" if model.startswith("ETS") else ("Seasonal naive" if model.startswith("Seasonal") else "Naive")
                rows += [{"series": name, "week_start": d.date(), "split": "holdout", "model": kind,
                          "actual": a, "forecast": round(float(f), 1), "lower_80": None, "upper_80": None}
                         for d, a, f in zip(test.index, test.to_numpy(), fc)]
        rows += [{"series": name, "week_start": d.date(), "split": "train", "model": "Actual",
                  "actual": a, "forecast": None, "lower_80": None, "upper_80": None}
                 for d, a in zip(train.index, train.to_numpy())]
        # Refit the selected spec on the whole window and forecast the next 12 weeks.
        full = ETSModel(y, initialization_method="estimated" if "s=52" not in best else "heuristic",
                        **SPECS[best]).fit(disp=False, maxiter=2000)
        pr = full.get_prediction(start=len(y), end=len(y) + FUTURE - 1).summary_frame(alpha=0.2)
        fut_idx = pd.date_range(y.index[-1] + pd.Timedelta(weeks=1), periods=FUTURE, freq="W-MON")
        rows += [{"series": name, "week_start": d.date(), "split": "future", "model": "ETS",
                  "actual": None, "forecast": round(float(r["mean"]), 1),
                  "lower_80": round(float(r["pi_lower"]), 1), "upper_80": round(float(r["pi_upper"]), 1)}
                 for d, (_, r) in zip(fut_idx, pr.iterrows())]
        notes.append(f"- {name}: AICc-selected {best} "
                     f"(AICc {', '.join(f'{k} {v.aicc:.1f}' for k, v in fits.items())}).")
        print(f"{name}: selected {best}")

    fw = pd.DataFrame(rows)
    fa = pd.DataFrame(acc)
    con.register("fw", fw)
    con.register("fa", fa)
    con.execute("CREATE OR REPLACE TABLE forecast_weekly AS SELECT * FROM fw")
    con.execute("CREATE OR REPLACE TABLE forecast_accuracy AS SELECT * FROM fa")
    con.close()

    md = ["# Demand forecast", "", "Generated by `src/forecast.py`. Do not edit by hand.", "",
          f"- Unit of forecast: units ordered per ISO week (Monday start).",
          f"- Training weeks: {fw[fw.split == 'train'].week_start.min()} to {fw[fw.split == 'train'].week_start.max()} "
          f"({(fw[(fw.split == 'train') & (fw.series == 'All categories')]).shape[0]} weeks).",
          f"- Holdout: the last {HOLDOUT} weeks, {fa.holdout_start.iloc[0]} to {fa.holdout_end.iloc[0]}.",
          "- The weeks from 2 Oct 2017 are excluded (data cut-off, see docs/validation.md).",
          "- The ETS specification is chosen on the training data by AICc. The holdout is only used to score.", "",
          "## Model selection", "", *notes, "", "## Holdout accuracy", "",
          "| Series | Model | WAPE % | MAPE % | Bias % |", "|---|---|---|---|---|"]
    for r in fa.itertuples():
        md.append(f"| {r.series} | {r.model} | {r.wape_pct:.2f} | {r.mape_pct:.2f} | {r.bias_pct:+.2f} |")
    (ROOT / "docs" / "forecast.md").write_text("\n".join(md) + "\n")
    print("\n".join(md[-(len(fa) + 2):]))


if __name__ == "__main__":
    main()
