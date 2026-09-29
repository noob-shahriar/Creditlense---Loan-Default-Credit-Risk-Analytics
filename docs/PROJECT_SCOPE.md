# CreditLens: Project Scope

## Business problem
A lender wants to approve good borrowers and avoid loans that go bad. Which borrower and
loan characteristics predict default, how much risk does each segment carry, and what
approval policy would cut defaults without rejecting too many good customers?

## Objectives
1. Measure portfolio risk: default rate by grade, term, purpose, income, DTI, state and issue year.
2. Check pricing versus risk: does the interest rate charged rise in line with actual default rates?
3. Build interpretable and non-linear default models, evaluated on a later time period.
4. Show how much of the model's signal comes from borrower data alone (no lender-assigned grade or rate).
5. Simulate approval cutoffs and quantify the trade-off between defaults avoided and good loans lost.

## Data
- LendingClub accepted loans 2007-2018Q4: https://www.kaggle.com/datasets/wordsforthewise/lending-club
- File used: the "accepted" loans CSV (about 2.2 million rows, about 150 columns).

## Target definition
| loan_status | is_default |
|---|---|
| Fully Paid | 0 |
| Charged Off, Default | 1 |
| Current, Late, In Grace Period, other | excluded (outcome not final) |

## Scope decisions
- **Issue years 2012-2015.** Loans issued later have many unfinished 60-month terms, which
  would bias the sample toward loans that resolved early.
- **Time-based split.** Train on 2012-2014, test on 2015. Random splits overstate performance in credit data.
- **Application-time features only.** Anything recorded after the loan was issued is excluded (see leakage list below).

## Leakage policy
The raw file contains fields that are only known after the loan starts and directly reveal the
outcome. These are never loaded: `out_prncp`, `out_prncp_inv`, `total_pymnt`, `total_pymnt_inv`,
`total_rec_prncp`, `total_rec_int`, `total_rec_late_fee`, `recoveries`, `collection_recovery_fee`,
`last_pymnt_d`, `last_pymnt_amnt`, `next_pymnt_d`, `last_credit_pull_d`, `last_fico_range_high`,
`last_fico_range_low`, `debt_settlement_flag*`, `hardship_*`, `settlement_*`, `pymnt_plan`.

## Known limitations (stated up front)
- Only accepted loans are observed, so the model cannot learn about applicants LendingClub rejected (selection bias).
- The dataset has no cost, profit or recovery-adjusted loss field, so financial impact is reported as
  gross principal exposure, not profit.
- Grade, sub-grade and interest rate are assigned by the lender. Models are reported with and without them.
- US peer-to-peer consumer loans from 2012-2015; findings do not automatically transfer to other markets or periods.
