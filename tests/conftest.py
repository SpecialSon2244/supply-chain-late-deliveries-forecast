import pathlib
import sys

import duckdb
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture(scope="session")
def con():
    db = ROOT / "data" / "supply_chain.duckdb"
    if not db.exists():
        pytest.skip("run `make build` first")
    c = duckdb.connect(str(db), read_only=True)
    yield c
    c.close()


def scalar(con, sql):
    return con.sql(sql).fetchall()[0][0]
