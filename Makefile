VENV=.venv
PY=$(VENV)/bin/python
.PHONY: all setup data build validate forecast findings charts tableau powerbi test clean
all: setup data build validate forecast findings charts tableau powerbi test

setup: $(VENV)/.installed     ## virtual environment with the packages in requirements.txt
$(VENV)/.installed: requirements.txt
	python3 -m venv $(VENV) && $(VENV)/bin/pip install -q -r requirements.txt && touch $@

data:        ## download the DataCo CSV (96 MB) to data/raw/ and check sha256 + row count
	$(PY) src/download.py
build:       ## Polars cleaning + DuckDB star schema and marts -> data/supply_chain.duckdb
	$(PY) src/build.py
validate:    ## data-quality and reconciliation checks -> docs/validation.md
	$(PY) src/validate.py > /dev/null
forecast:    ## ETS vs naive baselines on a 13-week holdout -> docs/forecast.md
	$(PY) src/forecast.py > /dev/null
findings:    ## sql/findings.sql -> docs/findings_results.md, docs/findings.json
	$(PY) src/findings.py > /dev/null
charts:      ## static Plotly PNGs -> images/
	$(PY) src/charts.py
tableau:     ## tableau/supply_chain_late_deliveries.xlsx + exports/*.csv
	$(PY) src/tableau_workbook.py
powerbi:     ## star schema tables -> powerbi/model/
	$(PY) src/export_powerbi.py
test:        ## pytest: data quality, reconciliation, forecast and workbook checks
	$(PY) -m pytest -q
clean:
	rm -rf data/staging data/supply_chain.duckdb
