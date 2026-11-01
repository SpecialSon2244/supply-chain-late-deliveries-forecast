"""Tests for the forecast, the Tableau workbook and the charts."""
import json
import pathlib

import openpyxl
import pytest

from conftest import ROOT, scalar

XLSX = ROOT / "tableau" / "supply_chain_late_deliveries.xlsx"
FINDINGS = json.loads((ROOT / "docs" / "findings.json").read_text())


def sheet(name):
    ws = openpyxl.load_workbook(XLSX, read_only=True)[name]
    rows = list(ws.iter_rows(values_only=True))
    return [dict(zip(rows[0], r)) for r in rows[1:]]


def test_forecast_does_not_use_weeks_after_break(con):
    assert scalar(con, """SELECT count(*) FROM forecast_weekly, forecast_window w
                          WHERE split IN ('train', 'holdout') AND week_start > w.last_week""") == 0


def test_holdout_is_last_13_weeks(con):
    assert scalar(con, "SELECT count(DISTINCT week_start) FROM forecast_weekly WHERE split = 'holdout'") == 13
    assert scalar(con, """SELECT max(week_start) = (SELECT last_week FROM forecast_window)
                          FROM forecast_weekly WHERE split = 'holdout'""")


def test_ets_beats_seasonal_naive_on_total(con):
    rows = dict(con.sql("""SELECT model, wape_pct FROM forecast_accuracy
                           WHERE series = 'All categories'""").fetchall())
    ets = next(v for k, v in rows.items() if k.startswith("ETS, AICc"))
    assert ets < rows["Seasonal naive (same week last year)"]


def test_xlsx_small_enough_for_tableau_public():
    assert XLSX.stat().st_size < 5 * 1024 * 1024


def test_xlsx_mode_matches_findings():
    x = {r["Shipping mode"]: r["Late %"] for r in sheet("late_by_mode")}
    f = {r["shipping_mode"]: r["late_pct"] for r in FINDINGS["q1_by_mode"]}
    assert x == pytest.approx(f)


def test_xlsx_market_matches_findings():
    x = {r["Market"]: r["Late %"] for r in sheet("late_by_market")}
    f = {r["market"]: r["late_pct"] for r in FINDINGS["q1_by_market"]}
    assert x == pytest.approx(f)


def test_xlsx_kpis_match_findings():
    k = {r["KPI"]: r for r in sheet("kpis")}
    o = FINDINGS["q1_overall"][0]
    assert k["Late (% of shipped lines)"]["Value"] == o["late_pct_of_shipped"]
    assert k["Order lines"]["Value"] == o["order_lines"]
    assert k["Profit at risk (late + cancelled)"]["Value"] == FINDINGS["q2_profit_at_risk"][0]["profit_at_risk_pct"]


def test_xlsx_profit_and_discount_match_findings():
    x = {r["Delivery outcome"]: r["Profit"] for r in sheet("profit_at_risk")}
    f = {r["status_group"]: r["profit"] for r in FINDINGS["q2_profit_by_status"]}
    assert x == pytest.approx(f)
    xd = {r["Discount band"]: r["Profit % of list price"] for r in sheet("discount_margin")}
    fd = {r["discount_band"]: r["profit_pct_of_gross"] for r in FINDINGS["q2_discount_bands"]}
    assert xd == pytest.approx(fd)


def test_xlsx_whatif_matches_findings():
    x = {r["Shipping mode"]: r["Late lines avoided"] for r in sheet("whatif")}
    f = {r["shipping_mode"]: r["late_lines_avoided"] for r in FINDINGS["q4_whatif_one_day"]}
    assert x == f


@pytest.mark.parametrize("png", ["01_late_rate_by_mode", "02_promise_vs_actual", "03_late_rate_by_market",
                                 "04_profit_at_risk", "05_discount_vs_margin", "06_weekly_volume_break",
                                 "07_forecast_vs_actual", "08_forecast_accuracy", "09_whatif_one_day"])
def test_chart_exists(png):
    p = ROOT / "images" / f"{png}.png"
    assert p.exists() and p.stat().st_size > 10_000
