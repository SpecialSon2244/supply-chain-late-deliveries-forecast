# LinkedIn post (draft, not posted)

Why are more than half of all orders late? This week I dug into the DataCo supply chain dataset (180,519 order lines, 2015 to 2018) to find out, and to see how well weekly demand can be forecast.

What I found:
→ 57.3% of shipped order lines are late, and the shipping mode explains almost all of it. Every market sits between 56.8% and 57.7%.
→ First Class promises 1 day but always takes 2, so it is late 100% of the time. Promising 2 days (or really shipping in 1) would remove 26.8% of all late lines and bring the late rate down to 41.9%, the biggest single change I tested.
→ 58% of profit ($2.30M of $3.97M) sits on late or cancelled lines.
→ Discounts come straight out of profit: profit as a share of list price falls from 13.1% with no discount to 9.4% at 25%, with no extra volume to make up for it.
→ A simple exponential smoothing model missed weekly units by 2.9% (WAPE) on a 13-week holdout, against 6.8% for "same week last year". Before forecasting I had to find and cut a break in October 2017, where volume halves and every order suddenly has one line.

Stack: Python, Polars and DuckDB for a star schema built in SQL (window functions for rolling demand, year-on-year and the break detection), statsmodels for the forecast, pytest for 51 data quality and reconciliation tests, Plotly charts, a Tableau Public dashboard and a Power BI model with DAX measures. One `make all` runs it from download to dashboard file.

Biggest lesson: check the data before you trust a model. The dataset is synthetic, and some patterns (like identical late rates everywhere) say more about how it was made than about logistics. I wrote those limits into the README.

Dashboard: [TODO: Tableau Public link]
Code: https://github.com/SpecialSon2244/supply-chain-late-deliveries-forecast

If you work in logistics: would you fix the promise or fix the shipping first?

#DataAnalytics #SupplyChain #SQL #DuckDB #Forecasting #Python #Tableau #PowerBI
