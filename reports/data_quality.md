# Data Quality Log

Source: `accepted_2007_to_2018Q4.csv`

## Cleaning steps

| Step | Rows after step | Note |
|---|---:|---|
| Raw rows loaded | 2,260,701 |  |
| Rows with a loan_status | 2,260,668 | drops footer/summary rows |
| Finished loans (Fully Paid / Charged Off / Default) | 1,345,350 | Current, Late, In Grace Period and policy-exception statuses excluded |
| Issued 2012-2015 | 786,820 | later vintages have unfinished 60-month loans (maturity bias) |
| Duplicate loan ids removed | 786,820 | 0 duplicates |
| Invalid values set to missing | 786,820 | annual_inc<=0: 2; dti<0: 0 |
| Outliers clipped at 99.5th percentile (train years) | 786,820 | annual_inc>300,000.0: 3927; dti>36.5: 11180; revol_bal>115,501.8: 5033 |
| Final modelling table | 786,820 | 18.64% default rate |

## Missing values in the final table (features with any missing)

| Column | Missing % |
|---|---:|
| emp_length_years | 5.27 |
| mort_acc | 0.95 |
| revol_util | 0.05 |

Missing values are kept as-is here and imputed with the training-set median / 'Unknown' inside the model pipeline, so no test-set information leaks into training.
