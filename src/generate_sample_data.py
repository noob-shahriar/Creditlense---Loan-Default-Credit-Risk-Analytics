"""Generate a SYNTHETIC LendingClub-like CSV so the pipeline can be tested without the Kaggle file.

The numbers it produces are fake and must never be reported as findings.
"""
import numpy as np
import pandas as pd

import config as C

GRADES = list("ABCDEFG")
PURPOSES = ["debt_consolidation", "credit_card", "home_improvement", "other", "major_purchase",
            "small_business", "car", "medical", "moving", "vacation"]
STATES = ["CA", "NY", "TX", "FL", "IL", "NJ", "PA", "OH", "GA", "VA", "NC", "MI", "WA", "MA", "AZ"]


def generate(n=40_000, seed=7, path=None):
    rng = np.random.default_rng(seed)
    C.ensure_dirs()
    path = path or (C.DATA_SAMPLE / "sample_accepted.csv")

    latent = rng.normal(size=n)                                   # hidden credit quality
    grade_idx = np.clip(np.round(3 + latent * 1.4 + rng.normal(0, 0.6, n)), 0, 6).astype(int)
    int_rate = 6 + grade_idx * 3.2 + rng.normal(0, 0.8, n)
    term = rng.choice([36, 60], size=n, p=[0.72, 0.28])
    loan_amnt = np.round(rng.gamma(4.0, 3800, n), -2).clip(1000, 40000)
    annual_inc = np.exp(rng.normal(11.05, 0.55, n))
    dti = np.clip(rng.normal(17, 8, n), -1, 60)
    fico = np.clip(np.round(700 - grade_idx * 9 + rng.normal(0, 18, n)), 620, 845)
    revol_util = np.clip(rng.normal(52, 25, n), 0, 130)
    logit = (-1.75 + grade_idx * 0.42 + (term == 60) * 0.45 + (dti - 17) * 0.018
             - (fico - 690) * 0.006 + np.log(loan_amnt / annual_inc) * 0.25 + rng.normal(0, 0.35, n))
    p_bad = 1 / (1 + np.exp(-logit))
    bad = rng.random(n) < p_bad

    years = rng.choice([2011, 2012, 2013, 2014, 2015, 2016], size=n, p=[0.04, 0.10, 0.20, 0.28, 0.30, 0.08])
    months = rng.integers(1, 13, n)
    mon = np.array(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
    issue_d = [f"{mon[m - 1]}-{y}" for m, y in zip(months, years)]
    cr_years = rng.integers(3, 30, n)
    earliest = [f"{mon[rng.integers(0, 12)]}-{y - c}" for y, c in zip(years, cr_years)]

    status = np.where(bad, "Charged Off", "Fully Paid").astype(object)
    current = rng.random(n) < 0.05
    status[current] = "Current"
    emp_choices = ["< 1 year", "1 year", "2 years", "3 years", "5 years", "8 years", "10+ years", None]

    df = pd.DataFrame({
        "id": np.arange(100000, 100000 + n).astype(str),
        "loan_amnt": loan_amnt, "funded_amnt": loan_amnt,
        "term": [f" {t} months" for t in term],
        "int_rate": np.round(int_rate, 2),
        "installment": np.round(loan_amnt * (int_rate / 1200) / (1 - (1 + int_rate / 1200) ** -term), 2),
        "grade": [GRADES[i] for i in grade_idx],
        "sub_grade": [f"{GRADES[i]}{rng.integers(1, 6)}" for i in grade_idx],
        "emp_length": rng.choice(emp_choices, size=n),
        "home_ownership": rng.choice(["RENT", "MORTGAGE", "OWN", "ANY"], size=n, p=[0.45, 0.42, 0.12, 0.01]),
        "annual_inc": np.round(annual_inc, 0),
        "verification_status": rng.choice(["Verified", "Source Verified", "Not Verified"], size=n),
        "issue_d": issue_d, "loan_status": status,
        "purpose": rng.choice(PURPOSES, size=n, p=[0.55, 0.18, 0.06, 0.07, 0.03, 0.03, 0.02, 0.02, 0.02, 0.02]),
        "addr_state": rng.choice(STATES, size=n),
        "dti": np.round(dti, 2),
        "delinq_2yrs": rng.poisson(0.3, n), "earliest_cr_line": earliest,
        "fico_range_low": fico, "fico_range_high": fico + 4,
        "inq_last_6mths": rng.poisson(0.7, n), "open_acc": rng.poisson(11, n),
        "pub_rec": rng.poisson(0.15, n), "revol_bal": np.round(rng.gamma(2, 8000, n), 0),
        "revol_util": np.round(revol_util, 1), "total_acc": rng.poisson(25, n),
        "mort_acc": rng.poisson(1.2, n), "pub_rec_bankruptcies": rng.poisson(0.08, n),
        "application_type": "Individual",
    })
    # messy real-world quirks to exercise the cleaner
    df.loc[rng.random(n) < 0.03, "annual_inc"] = 0
    df.loc[rng.random(n) < 0.01, "dti"] = -1
    df.loc[rng.random(n) < 0.02, "revol_util"] = np.nan
    df.loc[rng.random(n) < 0.04, "mort_acc"] = np.nan
    footer = pd.DataFrame({"id": ["Total amount funded in policy code 1: 123"]})
    df = pd.concat([df, footer], ignore_index=True)
    df.to_csv(path, index=False)
    print(f"Synthetic sample written to {path} ({n:,} rows). NOT REAL DATA.")
    return path


if __name__ == "__main__":
    generate()
