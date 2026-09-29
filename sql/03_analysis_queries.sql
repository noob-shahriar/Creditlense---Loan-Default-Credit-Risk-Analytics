-- CreditLens: SQL risk analysis. Run with: python src/run_sql_analysis.py
-- Each query starts with a "-- name:" marker; results are saved to reports/sql_results/<name>.csv
-- default_rate = share of finished loans that were Charged Off or Default.

-- name: q01_portfolio_overview
SELECT COUNT(*) AS loans,
       SUM(is_default) AS defaults,
       ROUND(AVG(is_default::NUMERIC), 4) AS default_rate,
       ROUND(AVG(loan_amnt), 0) AS avg_loan_amnt,
       ROUND(SUM(loan_amnt) / 1e6, 1) AS total_principal_musd,
       ROUND(AVG(int_rate), 2) AS avg_int_rate
FROM vw_loans;

-- name: q02_default_by_grade
SELECT grade,
       COUNT(*) AS loans,
       ROUND(AVG(is_default::NUMERIC), 4) AS default_rate,
       ROUND(AVG(int_rate), 2) AS avg_int_rate
FROM vw_loans
GROUP BY grade
ORDER BY grade;

-- name: q03_pricing_vs_risk
-- Rough pricing check: average rate charged minus observed default rate (in percentage points).
-- Ignores recoveries, fees and funding cost, so it is a screening signal, not profit.
SELECT grade,
       ROUND(AVG(int_rate), 2) AS avg_int_rate_pct,
       ROUND(100 * AVG(is_default::NUMERIC), 2) AS default_rate_pct,
       ROUND(AVG(int_rate) - 100 * AVG(is_default::NUMERIC), 2) AS rate_minus_default_pp
FROM vw_loans
GROUP BY grade
ORDER BY grade;

-- name: q04_default_by_purpose_ranked
SELECT purpose,
       COUNT(*) AS loans,
       ROUND(AVG(is_default::NUMERIC), 4) AS default_rate,
       RANK() OVER (ORDER BY AVG(is_default::NUMERIC) DESC) AS risk_rank
FROM vw_loans
GROUP BY purpose
HAVING COUNT(*) >= 500
ORDER BY risk_rank;

-- name: q05_default_by_term
SELECT term_months,
       COUNT(*) AS loans,
       ROUND(AVG(is_default::NUMERIC), 4) AS default_rate,
       ROUND(AVG(int_rate), 2) AS avg_int_rate
FROM vw_loans
GROUP BY term_months
ORDER BY term_months;

-- name: q06_default_by_income_band
SELECT CASE WHEN annual_inc IS NULL THEN '0 Unknown'
            WHEN annual_inc < 30000 THEN '1 <30k'
            WHEN annual_inc < 50000 THEN '2 30-50k'
            WHEN annual_inc < 75000 THEN '3 50-75k'
            WHEN annual_inc < 100000 THEN '4 75-100k'
            WHEN annual_inc < 150000 THEN '5 100-150k'
            ELSE '6 150k+' END AS income_band,
       COUNT(*) AS loans,
       ROUND(AVG(is_default::NUMERIC), 4) AS default_rate
FROM vw_loans
GROUP BY 1
ORDER BY 1;

-- name: q07_default_by_dti_band
SELECT CASE WHEN dti IS NULL THEN '0 Unknown'
            WHEN dti < 10 THEN '1 <10'
            WHEN dti < 20 THEN '2 10-20'
            WHEN dti < 30 THEN '3 20-30'
            WHEN dti < 40 THEN '4 30-40'
            ELSE '5 40+' END AS dti_band,
       COUNT(*) AS loans,
       ROUND(AVG(is_default::NUMERIC), 4) AS default_rate
FROM vw_loans
GROUP BY 1
ORDER BY 1;

-- name: q08_default_by_fico_band
SELECT CASE WHEN fico_avg IS NULL THEN '0 Unknown'
            WHEN fico_avg < 680 THEN '1 <680'
            WHEN fico_avg < 700 THEN '2 680-699'
            WHEN fico_avg < 720 THEN '3 700-719'
            WHEN fico_avg < 750 THEN '4 720-749'
            ELSE '5 750+' END AS fico_band,
       COUNT(*) AS loans,
       ROUND(AVG(is_default::NUMERIC), 4) AS default_rate
FROM vw_loans
GROUP BY 1
ORDER BY 1;

-- name: q09_home_ownership_x_verification
SELECT home_ownership, verification_status,
       COUNT(*) AS loans,
       ROUND(AVG(is_default::NUMERIC), 4) AS default_rate
FROM vw_loans
GROUP BY home_ownership, verification_status
HAVING COUNT(*) >= 200
ORDER BY default_rate DESC;

-- name: q10_vintage_default_with_yoy_change
WITH by_year AS (
    SELECT issue_year, COUNT(*) AS loans, AVG(is_default::NUMERIC) AS default_rate
    FROM vw_loans GROUP BY issue_year
)
SELECT issue_year, loans,
       ROUND(default_rate, 4) AS default_rate,
       ROUND(default_rate - LAG(default_rate) OVER (ORDER BY issue_year), 4) AS change_vs_prior_year
FROM by_year
ORDER BY issue_year;

-- name: q11_monthly_rolling_default_rate
WITH monthly AS (
    SELECT date_trunc('month', issue_date)::DATE AS month,
           COUNT(*) AS loans, SUM(is_default) AS defaults
    FROM vw_loans GROUP BY 1
)
SELECT month, loans, defaults,
       ROUND(defaults::NUMERIC / loans, 4) AS default_rate,
       ROUND(SUM(defaults) OVER w::NUMERIC / SUM(loans) OVER w, 4) AS rolling_3m_default_rate
FROM monthly
WINDOW w AS (ORDER BY month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)
ORDER BY month;

-- name: q12_state_risk_ranking
SELECT state_code,
       COUNT(*) AS loans,
       ROUND(AVG(is_default::NUMERIC), 4) AS default_rate,
       RANK() OVER (ORDER BY AVG(is_default::NUMERIC) DESC) AS risk_rank
FROM vw_loans
GROUP BY state_code
HAVING COUNT(*) >= 1000
ORDER BY risk_rank;

-- name: q13_riskiest_purpose_within_each_grade
WITH seg AS (
    SELECT grade, purpose, COUNT(*) AS loans, AVG(is_default::NUMERIC) AS default_rate
    FROM vw_loans GROUP BY grade, purpose HAVING COUNT(*) >= 300
), ranked AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY grade ORDER BY default_rate DESC) AS rn FROM seg
)
SELECT grade, purpose, loans, ROUND(default_rate, 4) AS default_rate
FROM ranked WHERE rn = 1 ORDER BY grade;

-- name: q14_default_concentration_by_state
-- Where do the defaults sit? Running share of all defaults, biggest contributors first.
WITH s AS (
    SELECT state_code, SUM(is_default) AS defaults FROM vw_loans GROUP BY state_code
)
SELECT state_code, defaults,
       ROUND(100.0 * defaults / SUM(defaults) OVER (), 2) AS pct_of_all_defaults,
       ROUND(100.0 * SUM(defaults) OVER (ORDER BY defaults DESC, state_code) / SUM(defaults) OVER (), 2)
           AS cumulative_pct
FROM s
ORDER BY defaults DESC, state_code;

-- name: q15_loan_size_quartiles
WITH q AS (
    SELECT is_default, loan_amnt, NTILE(4) OVER (ORDER BY loan_amnt) AS size_quartile FROM vw_loans
)
SELECT size_quartile,
       MIN(loan_amnt) AS min_amnt, MAX(loan_amnt) AS max_amnt,
       COUNT(*) AS loans,
       ROUND(AVG(is_default::NUMERIC), 4) AS default_rate
FROM q GROUP BY size_quartile ORDER BY size_quartile;

-- name: q16_risk_matrix_grade_group_x_dti
SELECT CASE WHEN grade IN ('A', 'B') THEN 'A-B (prime)'
            WHEN grade IN ('C', 'D') THEN 'C-D (mid)'
            ELSE 'E-G (subprime)' END AS grade_group,
       CASE WHEN dti IS NULL THEN 'Unknown'
            WHEN dti < 15 THEN 'DTI <15'
            WHEN dti < 25 THEN 'DTI 15-25'
            ELSE 'DTI 25+' END AS dti_group,
       COUNT(*) AS loans,
       ROUND(AVG(is_default::NUMERIC), 4) AS default_rate
FROM vw_loans
GROUP BY 1, 2
ORDER BY 1, 2;

-- name: q17_principal_exposure_by_grade
-- Gross principal issued on loans that later defaulted (not net loss: recoveries are not in this data).
SELECT grade,
       SUM(is_default) AS defaults,
       ROUND(SUM(loan_amnt) FILTER (WHERE is_default = 1) / 1e6, 2) AS defaulted_principal_musd,
       ROUND(100.0 * SUM(loan_amnt) FILTER (WHERE is_default = 1)
             / SUM(SUM(loan_amnt) FILTER (WHERE is_default = 1)) OVER (), 2) AS pct_of_defaulted_principal
FROM vw_loans
GROUP BY grade
ORDER BY grade;

-- name: q18_missing_value_audit
SELECT COUNT(*) AS loans,
       COUNT(*) FILTER (WHERE annual_inc IS NULL) AS missing_income,
       COUNT(*) FILTER (WHERE dti IS NULL) AS missing_dti,
       COUNT(*) FILTER (WHERE revol_util IS NULL) AS missing_revol_util,
       COUNT(*) FILTER (WHERE emp_length_years IS NULL) AS missing_emp_length,
       COUNT(*) FILTER (WHERE fico_avg IS NULL) AS missing_fico
FROM vw_loans;
