-- CreditLens: staging table (flat, cleaned loans loaded from data/processed/loans_clean.parquet)
CREATE SCHEMA IF NOT EXISTS creditlens;
SET search_path TO creditlens, public;

DROP VIEW  IF EXISTS vw_loans;
DROP TABLE IF EXISTS fact_loans;
DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS dim_grade;
DROP TABLE IF EXISTS dim_purpose;
DROP TABLE IF EXISTS dim_state;
DROP TABLE IF EXISTS dim_borrower_profile;
DROP TABLE IF EXISTS stg_loans;

CREATE TABLE stg_loans (
    loan_id               TEXT,
    loan_amnt             NUMERIC,
    term_months           INTEGER,
    int_rate              NUMERIC,
    installment           NUMERIC,
    grade                 TEXT,
    sub_grade             TEXT,
    emp_length_years      NUMERIC,
    home_ownership        TEXT,
    annual_inc            NUMERIC,
    verification_status   TEXT,
    issue_date            DATE,
    issue_year            INTEGER,
    purpose               TEXT,
    addr_state            TEXT,
    dti                   NUMERIC,
    delinq_2yrs           NUMERIC,
    inq_last_6mths        NUMERIC,
    open_acc              NUMERIC,
    pub_rec               NUMERIC,
    revol_bal             NUMERIC,
    revol_util            NUMERIC,
    total_acc             NUMERIC,
    mort_acc              NUMERIC,
    pub_rec_bankruptcies  NUMERIC,
    application_type      TEXT,
    fico_avg              NUMERIC,
    credit_history_years  NUMERIC,
    loan_to_income        NUMERIC,
    loan_status           TEXT,
    is_default            SMALLINT
);
