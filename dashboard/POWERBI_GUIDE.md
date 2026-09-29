# Dashboard Guide (Power BI or Tableau)

The pipeline exports dashboard-ready files into `dashboard/data/` (created by steps 4-6):

| File | Grain | Use |
|---|---|---|
| `segment_summary.csv` | one row per segment of each dimension (`dimension`, `segment`, `loans`, `defaults`, `default_rate`, ...) | portfolio and risk pages |
| `model_deciles.csv` | one row per risk decile and feature set | model page |
| `policy_simulation.csv` | one row per reject rate and model | policy page |
| `scored_test_sample.csv` | up to 100k scored test loans | drill-down, score distribution |

This guide describes how to build the dashboard yourself in Power BI Desktop (Windows). The `.pbix` file is not
included because it has to be built on your machine from your run's data.

## Steps
1. **Get Data -> Text/CSV**, import the four files. Keep types: `default_rate` as decimal, `loans` as whole number.
2. Create a small table `Dimension` for a slicer: `Enter Data` with values `grade, term, purpose, state, dti_band,
   fico_band, income_band, home_ownership, verification_status, loan_size, issue_year`.

## DAX measures
```DAX
Loans = SUM(segment_summary[loans])
Defaults = SUM(segment_summary[defaults])
Default Rate = DIVIDE([Defaults], [Loans])
Avg Interest Rate = DIVIDE(SUMX(segment_summary, segment_summary[avg_int_rate] * segment_summary[loans]), [Loans])
Principal (USD M) = SUM(segment_summary[total_principal]) / 1000000
Defaults Avoided % = AVERAGE(policy_simulation[defaults_avoided_pct])
Good Loans Lost % = AVERAGE(policy_simulation[good_loans_lost_pct])
```
Note: for the KPI cards, filter `segment_summary[dimension] = "grade"` so totals are not counted once per dimension.

## Pages
1. **Portfolio overview**: KPI cards (Loans, Default Rate, Principal), default rate by issue year (line), by grade (column).
2. **Risk drivers**: slicer on `dimension`; bar chart of `Default Rate` by `segment`; table with loans, default rate,
   average interest rate. Add a constant line at the overall default rate.
3. **Pricing vs risk**: clustered column of `Avg Interest Rate` vs `Default Rate` by grade.
4. **Model performance**: column chart of `actual_default_rate` and line of `avg_predicted` by `risk_decile`
   (filter `feature_set` = full); cumulative defaults captured by decile.
5. **Policy simulator**: line chart of `defaults_avoided_pct` and `good_loans_lost_pct` against `reject_rate`,
   slicer on `score` (full / borrower_only).

Publish to Power BI Service or export screenshots (File -> Export) into `dashboard/` and link them from the README.
Tableau users: connect to the same CSVs and rebuild the five pages with the same fields.
