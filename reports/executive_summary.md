# CreditLens: Executive Summary

*Source: accepted_2007_to_2018Q4.csv. All figures below are computed by the pipeline from the cleaned data; see `reports/tables/` and `reports/figures/`.*

## 1. Scope

- **786,820** finished loans issued 2012-2015 (Fully Paid, Charged Off or Default).
- Overall default rate: **18.6%**.
- Models trained on 400,000 loans issued before 2015 and tested on 375,546 loans issued in 2015 (test default rate 20.2%).

## 2. Where the risk sits

- **Grade:** default rate rises from 5.5% in grade A to 47.8% in grade G (8.6x). The increase is steady across every grade.
- **Term:** 36 months loans default at 14.0% versus 32.4% for 60 months.
- **Purpose:** highest default rate is 'small_business' at 27.1% (n=8,002); lowest is 'wedding' at 13.6% (n=1,343).
- **Debt-to-income:** default rate ranges from 13.5% (<10) to 27.7% (30-40).
- **FICO:** default rate ranges from 7.6% (750+) to 23.3% (<680).
- **Income:** default rate ranges from 13.2% (150k+) to 22.0% (<30k).
- **Vintage:** default rate moves from 16.2% for 2012 loans to 20.2% for 2015 loans.

## 3. Pricing versus risk

| Grade | Avg interest rate | Default rate | Rate minus default (pp) |
|---|---|---|---|
| A | 7.23% | 5.5% | 1.69 |
| B | 10.85% | 12.0% | -1.19 |
| C | 14.04% | 20.5% | -6.46 |
| D | 17.29% | 28.4% | -11.14 |
| E | 20.10% | 37.3% | -17.21 |
| F | 23.85% | 43.0% | -19.10 |
| G | 26.12% | 47.8% | -21.67 |

Grade G has the thinnest gap between the rate charged and the observed default rate (-21.67 percentage points; the average rate is below the default rate). This ignores recoveries, fees and funding cost, so it is a screening signal, not a profit figure.

## 4. Model performance (held-out test year)

| Model | ROC-AUC | Gini | KS | PR-AUC |
|---|---|---|---|---|
| full__logistic | 0.731 | 0.463 | 0.338 | 0.404 |
| full__gbm | 0.735 | 0.470 | 0.342 | 0.411 |
| borrower_only__logistic | 0.714 | 0.428 | 0.309 | 0.392 |
| borrower_only__gbm | 0.721 | 0.443 | 0.318 | 0.400 |

- Best full model (full__gbm): AUC 0.735. Best borrower-only model (borrower_only__gbm): AUC 0.721. The lender-assigned grade, rate and installment add 1.3 AUC points on top of the borrower's own profile.
- Riskiest decile defaults at 50.3% versus 3.4% in the safest decile; the three riskiest deciles contain 56.1% of all defaults.

## 5. Approval-policy simulation

Rejecting the applicants with the highest predicted default probability (test year):

| Model | Rejected | Defaults avoided | Good loans lost | Approved default rate | Defaulted principal avoided |
|---|---|---|---|---|---|
| full | 10% | 24.9% | 6.2% | 16.8% | 29.7% |
| full | 20% | 42.5% | 14.3% | 14.5% | 48.9% |
| full | 30% | 56.1% | 23.4% | 12.7% | 62.0% |
| borrower_only | 10% | 24.4% | 6.4% | 17.0% | 29.3% |
| borrower_only | 20% | 41.4% | 14.6% | 14.8% | 47.9% |
| borrower_only | 30% | 54.6% | 23.8% | 13.1% | 60.6% |

Defaulted principal is the gross amount lent, not net loss (no recovery data).

## 6. Recommendations

1. **Use the score for triage, not blanket rejection.** Rejecting the riskiest 20% would avoid 42.5% of defaults but also lose 14.3% of good loans. Route the riskiest decile to manual review, a lower limit or higher pricing before rejecting.
2. **Review pricing in grade G**, where the rate charged leaves the smallest gap over observed default rates (before recoveries and costs).
3. **Watch 'small_business' loans** (default rate 27.1%): consider tighter limits or extra verification for this purpose.
4. **Reconsider long terms for weaker grades**: 60 months loans default at 32.4% versus 14.0% for 36 months.
5. **Monitor drift.** Track default rate by issue quarter and compare predicted versus actual default rate by risk decile on each new vintage before trusting the score.

## 7. Limitations

- Only accepted loans are observed, so applicants the lender rejected are missing (selection bias).
- No profit, cost or recovery data: financial impact is gross principal, not net loss.
- Grade, sub-grade and interest rate are lender-assigned; the borrower-only models show the signal without them.
- Loans issued 2012-2015 in the US; results may not transfer to other periods or markets.
- Correlations are associations, not causes. A model score should support, not replace, credit judgement.
