-- CreditLens: build a star schema from stg_loans
SET search_path TO creditlens, public;

CREATE TABLE dim_date (
    date_key   INTEGER PRIMARY KEY,          -- yyyymm
    issue_date DATE NOT NULL,
    year       INTEGER NOT NULL,
    quarter    INTEGER NOT NULL,
    month      INTEGER NOT NULL
);
INSERT INTO dim_date
SELECT DISTINCT to_char(issue_date, 'YYYYMM')::INT,
       date_trunc('month', issue_date)::DATE,
       EXTRACT(YEAR FROM issue_date)::INT,
       EXTRACT(QUARTER FROM issue_date)::INT,
       EXTRACT(MONTH FROM issue_date)::INT
FROM stg_loans;

CREATE TABLE dim_grade (
    grade_key INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    grade     TEXT NOT NULL,
    sub_grade TEXT NOT NULL,
    UNIQUE (grade, sub_grade)
);
INSERT INTO dim_grade (grade, sub_grade)
SELECT DISTINCT grade, sub_grade FROM stg_loans WHERE grade IS NOT NULL AND sub_grade IS NOT NULL
ORDER BY 1, 2;

CREATE TABLE dim_purpose (
    purpose_key INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    purpose     TEXT NOT NULL UNIQUE
);
INSERT INTO dim_purpose (purpose)
SELECT DISTINCT purpose FROM stg_loans WHERE purpose IS NOT NULL ORDER BY 1;

CREATE TABLE dim_state (
    state_key  INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    state_code TEXT NOT NULL UNIQUE
);
INSERT INTO dim_state (state_code)
SELECT DISTINCT addr_state FROM stg_loans WHERE addr_state IS NOT NULL ORDER BY 1;

CREATE TABLE dim_borrower_profile (
    profile_key         INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    home_ownership      TEXT NOT NULL,
    verification_status TEXT NOT NULL,
    application_type    TEXT NOT NULL,
    UNIQUE (home_ownership, verification_status, application_type)
);
INSERT INTO dim_borrower_profile (home_ownership, verification_status, application_type)
SELECT DISTINCT COALESCE(home_ownership, 'UNKNOWN'), COALESCE(verification_status, 'UNKNOWN'),
                COALESCE(application_type, 'UNKNOWN')
FROM stg_loans;

CREATE TABLE fact_loans (
    loan_id              TEXT PRIMARY KEY,
    date_key             INTEGER NOT NULL REFERENCES dim_date (date_key),
    grade_key            INTEGER REFERENCES dim_grade (grade_key),
    purpose_key          INTEGER REFERENCES dim_purpose (purpose_key),
    state_key            INTEGER REFERENCES dim_state (state_key),
    profile_key          INTEGER REFERENCES dim_borrower_profile (profile_key),
    loan_amnt            NUMERIC,
    term_months          INTEGER,
    int_rate             NUMERIC,
    installment          NUMERIC,
    annual_inc           NUMERIC,
    dti                  NUMERIC,
    fico_avg             NUMERIC,
    revol_util           NUMERIC,
    credit_history_years NUMERIC,
    emp_length_years     NUMERIC,
    loan_to_income       NUMERIC,
    loan_status          TEXT,
    is_default           SMALLINT NOT NULL
);
INSERT INTO fact_loans
SELECT s.loan_id,
       to_char(s.issue_date, 'YYYYMM')::INT,
       g.grade_key, p.purpose_key, st.state_key, bp.profile_key,
       s.loan_amnt, s.term_months, s.int_rate, s.installment, s.annual_inc, s.dti, s.fico_avg,
       s.revol_util, s.credit_history_years, s.emp_length_years, s.loan_to_income,
       s.loan_status, s.is_default
FROM stg_loans s
LEFT JOIN dim_grade g ON g.grade = s.grade AND g.sub_grade = s.sub_grade
LEFT JOIN dim_purpose p ON p.purpose = s.purpose
LEFT JOIN dim_state st ON st.state_code = s.addr_state
LEFT JOIN dim_borrower_profile bp
       ON bp.home_ownership = COALESCE(s.home_ownership, 'UNKNOWN')
      AND bp.verification_status = COALESCE(s.verification_status, 'UNKNOWN')
      AND bp.application_type = COALESCE(s.application_type, 'UNKNOWN');

CREATE INDEX idx_fact_date    ON fact_loans (date_key);
CREATE INDEX idx_fact_grade   ON fact_loans (grade_key);
CREATE INDEX idx_fact_purpose ON fact_loans (purpose_key);
CREATE INDEX idx_fact_state   ON fact_loans (state_key);
CREATE INDEX idx_fact_default ON fact_loans (is_default);

CREATE VIEW vw_loans AS
SELECT f.loan_id, d.issue_date, d.year AS issue_year, d.quarter AS issue_quarter,
       g.grade, g.sub_grade, p.purpose, s.state_code, bp.home_ownership,
       bp.verification_status, bp.application_type,
       f.loan_amnt, f.term_months, f.int_rate, f.installment, f.annual_inc, f.dti, f.fico_avg,
       f.revol_util, f.credit_history_years, f.emp_length_years, f.loan_to_income,
       f.loan_status, f.is_default
FROM fact_loans f
JOIN dim_date d ON d.date_key = f.date_key
LEFT JOIN dim_grade g ON g.grade_key = f.grade_key
LEFT JOIN dim_purpose p ON p.purpose_key = f.purpose_key
LEFT JOIN dim_state s ON s.state_key = f.state_key
LEFT JOIN dim_borrower_profile bp ON bp.profile_key = f.profile_key;
