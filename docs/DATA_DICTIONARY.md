# Data Dictionary (cleaned table `loans_clean`)

Only fields available **at application/origination time** are used. Every column is derived from the
LendingClub accepted-loans file.

| Column | Description | Notes |
|---|---|---|
| loan_id | LendingClub loan id | unique after de-duplication |
| loan_amnt | Requested loan amount (USD) | |
| term_months | 36 or 60 | parsed from text like " 36 months" |
| int_rate | Interest rate (%) | lender-assigned |
| installment | Monthly payment (USD) | depends on amount, term and rate |
| grade / sub_grade | Lender risk grade A-G, A1-G5 | lender-assigned |
| emp_length_years | Years employed (0-10) | "< 1 year" = 0, "10+ years" = 10; missing kept missing |
| home_ownership | RENT / MORTGAGE / OWN / OTHER | ANY and NONE merged into OTHER |
| annual_inc | Self-reported income (USD) | <= 0 set to missing; clipped at train-year 99.5th percentile |
| verification_status | Income verification status | |
| issue_date / issue_year | Loan issue month / year | |
| purpose | Stated loan purpose | |
| addr_state | Borrower state | |
| dti | Debt-to-income ratio | < 0 set to missing; clipped at 99.5th percentile |
| delinq_2yrs, inq_last_6mths, pub_rec, pub_rec_bankruptcies | Credit history counts | |
| open_acc, total_acc, mort_acc | Account counts | |
| revol_bal, revol_util | Revolving balance and utilisation (%) | util clipped to 0-150 |
| application_type | Individual / Joint | |
| fico_avg | Mean of FICO low and high at origination | |
| credit_history_years | Years between earliest credit line and issue date | |
| loan_to_income | loan_amnt / annual_inc | engineered |
| loan_status | Final status | only Fully Paid, Charged Off, Default kept |
| is_default | Target: 1 = Charged Off or Default, 0 = Fully Paid | |

## Excluded on purpose (leakage)
Payments received, outstanding principal, recoveries, late fees, last payment and last credit pull
dates, last FICO range, settlement and hardship fields. They are recorded after the loan starts and
reveal the outcome. See `docs/PROJECT_SCOPE.md`.

## Feature sets used in modelling
- **full**: all application-time fields including lender-assigned grade, sub_grade, int_rate and installment.
- **borrower_only**: the same without grade, sub_grade, int_rate and installment, to show how much signal
  comes from the borrower's own profile rather than the lender's assessment.
