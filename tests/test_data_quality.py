"""Data-quality and reconciliation tests on the star schema (same checks as docs/validation.md)."""
import pytest

from checks import CHECKS, FACT_TOTALS_SQL, raw_totals
from conftest import scalar


@pytest.mark.parametrize("name,sql,expect", CHECKS, ids=[c[0] for c in CHECKS])
def test_check(con, name, sql, expect):
    assert scalar(con, sql) == expect


def test_raw_csv_reconciles_with_fact(con):
    raw = raw_totals()
    rel = con.sql(FACT_TOTALS_SQL)
    fact = dict(zip(rel.columns, rel.fetchall()[0]))
    for k, v in raw.items():
        assert float(fact[k]) == pytest.approx(float(v), abs=0.05), k


def test_no_personal_columns(con):
    cols = {r[0] for r in con.sql("SELECT column_name FROM information_schema.columns").fetchall()}
    for banned in ["customer_email", "customer_password", "customer_fname", "customer_lname", "customer_street"]:
        assert banned not in cols


def test_rolling_4wk_matches_manual_sum(con):
    # Window function check: rolling 4-week units = sum of the current and 3 previous weeks.
    bad = scalar(con, """
        SELECT count(*) FROM mart_weekly_category_demand a
        WHERE a.units_rolling_4wk <> (
            SELECT sum(b.units) FROM mart_weekly_category_demand b
            WHERE b.category_name = a.category_name
              AND b.week_start BETWEEN a.week_start - INTERVAL 21 DAY AND a.week_start)""")
    assert bad == 0


def test_lag_52_is_same_week_last_year(con):
    bad = scalar(con, """
        SELECT count(*) FROM mart_weekly_category_demand a
        JOIN mart_weekly_category_demand b
          ON b.category_name = a.category_name AND b.week_start = a.week_start - INTERVAL 364 DAY
        WHERE a.units_same_week_last_year <> b.units""")
    assert bad == 0
