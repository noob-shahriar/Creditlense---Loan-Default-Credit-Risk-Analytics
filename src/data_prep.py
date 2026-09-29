"""Step 1: load the raw LendingClub file, clean it, and save a modelling-ready parquet.

Usage:
    python src/data_prep.py                       # auto-detects a file in data/raw/
    python src/data_prep.py --raw path/to/accepted_2007_to_2018Q4.csv.gz
    python src/data_prep.py --sample              # synthetic data, pipeline testing only
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import config as C

# Application-time columns only. Post-origination (leaky) columns are deliberately never loaded.
USECOLS = [
    "id", "loan_amnt", "funded_amnt", "term", "int_rate", "installment", "grade", "sub_grade",
    "emp_length", "home_ownership", "annual_inc", "verification_status", "issue_d", "loan_status",
    "purpose", "addr_state", "dti", "delinq_2yrs", "earliest_cr_line", "fico_range_low",
    "fico_range_high", "inq_last_6mths", "open_acc", "pub_rec", "revol_bal", "revol_util",
    "total_acc", "mort_acc", "pub_rec_bankruptcies", "application_type",
]

# Column order of the cleaned file (and of the PostgreSQL staging table).
CLEAN_COLUMNS = [
    "loan_id", "loan_amnt", "term_months", "int_rate", "installment", "grade", "sub_grade",
    "emp_length_years", "home_ownership", "annual_inc", "verification_status", "issue_date",
    "issue_year", "purpose", "addr_state", "dti", "delinq_2yrs", "inq_last_6mths", "open_acc",
    "pub_rec", "revol_bal", "revol_util", "total_acc", "mort_acc", "pub_rec_bankruptcies",
    "application_type", "fico_avg", "credit_history_years", "loan_to_income", "loan_status",
    "is_default",
]


def find_raw_file(raw_arg=None):
    if raw_arg:
        p = Path(raw_arg)
        if not p.exists():
            raise FileNotFoundError(f"Raw file not found: {p}")
        return p
    candidates = []
    for pattern in ("*.csv", "*.csv.gz", "*.zip"):
        candidates += [p for p in C.DATA_RAW.rglob(pattern) if "reject" not in p.name.lower()]
    accepted = [p for p in candidates if "accept" in p.name.lower()]
    pool = accepted or candidates
    if not pool:
        raise FileNotFoundError(
            "No raw file found in data/raw/. Download the LendingClub 'accepted' CSV from "
            "https://www.kaggle.com/datasets/wordsforthewise/lending-club and place it there, "
            "or run with --sample to test the pipeline on synthetic data."
        )
    return max(pool, key=lambda p: p.stat().st_size)


def _pct_to_float(s):
    if s.dtype == object:
        return pd.to_numeric(s.astype(str).str.replace("%", "", regex=False).str.strip(), errors="coerce")
    return pd.to_numeric(s, errors="coerce")


def clean(df, log):
    """Clean the raw dataframe. `log` is a list that receives (step, rows, note) tuples."""
    def note(step, n, extra=""):
        log.append({"step": step, "rows": int(n), "note": extra})

    note("Raw rows loaded", len(df))
    df = df.copy()

    # 1. keep only finished loans (drops 'Current', 'Late', summary/footer rows with no status)
    df = df[df["loan_status"].notna()]
    note("Rows with a loan_status", len(df), "drops footer/summary rows")
    df = df[df["loan_status"].isin(C.GOOD_STATUS + C.BAD_STATUS)].copy()
    note("Finished loans (Fully Paid / Charged Off / Default)", len(df),
         "Current, Late, In Grace Period and policy-exception statuses excluded")
    df["is_default"] = df["loan_status"].isin(C.BAD_STATUS).astype(int)

    # 2. dates and scope window
    df["issue_date"] = pd.to_datetime(df["issue_d"], format="%b-%Y", errors="coerce")
    df = df[df["issue_date"].notna()].copy()
    df["issue_year"] = df["issue_date"].dt.year.astype(int)
    df = df[df["issue_year"].between(C.MIN_ISSUE_YEAR, C.MAX_ISSUE_YEAR)].copy()
    note(f"Issued {C.MIN_ISSUE_YEAR}-{C.MAX_ISSUE_YEAR}", len(df),
         "later vintages have unfinished 60-month loans (maturity bias)")

    # 3. duplicates
    if "id" in df.columns and df["id"].notna().any():
        before = len(df)
        df = df.drop_duplicates(subset="id")
        note("Duplicate loan ids removed", len(df), f"{before - len(df)} duplicates")

    # 4. parsing
    df["term_months"] = pd.to_numeric(df["term"].astype(str).str.extract(r"(\d+)")[0], errors="coerce")
    df["int_rate"] = _pct_to_float(df["int_rate"])
    df["revol_util"] = _pct_to_float(df["revol_util"])
    emp = df["emp_length"].astype(str).str.extract(r"(\d+)")[0].astype(float)
    emp[df["emp_length"].astype(str).str.contains("<", regex=False)] = 0.0
    emp[df["emp_length"].isna()] = np.nan
    df["emp_length_years"] = emp
    earliest = pd.to_datetime(df["earliest_cr_line"], format="%b-%Y", errors="coerce")
    df["credit_history_years"] = (df["issue_date"] - earliest).dt.days / 365.25
    df["fico_avg"] = (pd.to_numeric(df["fico_range_low"], errors="coerce")
                      + pd.to_numeric(df["fico_range_high"], errors="coerce")) / 2
    df["home_ownership"] = df["home_ownership"].replace({"ANY": "OTHER", "NONE": "OTHER"})
    df["loan_id"] = df["id"].astype(str) if "id" in df.columns else df.index.astype(str)

    # 5. invalid values -> NaN (imputation happens later, inside the model pipeline, to avoid leakage)
    n_bad_inc = int((pd.to_numeric(df["annual_inc"], errors="coerce") <= 0).sum())
    df["annual_inc"] = pd.to_numeric(df["annual_inc"], errors="coerce")
    df.loc[df["annual_inc"] <= 0, "annual_inc"] = np.nan
    df["dti"] = pd.to_numeric(df["dti"], errors="coerce")
    n_bad_dti = int((df["dti"] < 0).sum())
    df.loc[df["dti"] < 0, "dti"] = np.nan
    note("Invalid values set to missing", len(df), f"annual_inc<=0: {n_bad_inc}; dti<0: {n_bad_dti}")

    # 6. outliers: clip at the 99.5th percentile computed on TRAINING years only
    train_mask = df["issue_year"] < C.TEST_YEAR
    ref = df[train_mask] if train_mask.any() else df
    clip_info = []
    for col in ("annual_inc", "dti", "revol_bal"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
        cap = ref[col].quantile(0.995)
        n_clipped = int((df[col] > cap).sum())
        df[col] = df[col].clip(upper=cap)
        clip_info.append(f"{col}>{cap:,.1f}: {n_clipped}")
    df["revol_util"] = df["revol_util"].clip(lower=0, upper=150)
    note("Outliers clipped at 99.5th percentile (train years)", len(df), "; ".join(clip_info))

    for col in ("loan_amnt", "installment", "delinq_2yrs", "inq_last_6mths", "open_acc", "pub_rec",
                "total_acc", "mort_acc", "pub_rec_bankruptcies"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        else:
            df[col] = np.nan

    df["loan_to_income"] = df["loan_amnt"] / df["annual_inc"]

    out = df[CLEAN_COLUMNS].reset_index(drop=True)
    note("Final modelling table", len(out), f"{out['is_default'].mean():.2%} default rate")
    return out


def missing_table(df):
    m = (df.isna().mean() * 100).round(2).rename("missing_pct").to_frame()
    return m[m["missing_pct"] > 0].sort_values("missing_pct", ascending=False)


def write_quality_report(log, out, source):
    lines = ["# Data Quality Log", "", f"Source: `{source}`", ""]
    if source == "SYNTHETIC SAMPLE":
        lines += ["> **SYNTHETIC DATA. Generated only to test the pipeline. Do not report any of these numbers.**", ""]
    lines += ["## Cleaning steps", "", "| Step | Rows after step | Note |", "|---|---:|---|"]
    for r in log:
        lines.append(f"| {r['step']} | {r['rows']:,} | {r['note']} |")
    lines += ["", "## Missing values in the final table (features with any missing)", "",
              "| Column | Missing % |", "|---|---:|"]
    mt = missing_table(out)
    for col, row in mt.iterrows():
        lines.append(f"| {col} | {row['missing_pct']:.2f} |")
    if mt.empty:
        lines.append("| (none) | 0 |")
    lines += ["", "Missing values are kept as-is here and imputed with the training-set median / 'Unknown' inside "
              "the model pipeline, so no test-set information leaks into training.", ""]
    (C.REPORTS / "data_quality.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", help="path to the raw accepted-loans CSV (.csv or .csv.gz)")
    ap.add_argument("--sample", action="store_true", help="use synthetic sample data (pipeline test only)")
    args = ap.parse_args()
    C.ensure_dirs()

    if args.sample:
        import generate_sample_data
        path = generate_sample_data.generate()
        source = "SYNTHETIC SAMPLE"
    else:
        path = find_raw_file(args.raw)
        source = path.name
    print(f"Reading {path} ...")
    df = pd.read_csv(path, usecols=lambda c: c in USECOLS, low_memory=False)
    missing_cols = [c for c in USECOLS if c not in df.columns]
    if missing_cols:
        print(f"Note: columns not found in file (will be NaN or skipped): {missing_cols}")
    for c in ("id", "emp_length", "earliest_cr_line", "fico_range_low", "fico_range_high"):
        if c not in df.columns:
            df[c] = np.nan

    log = []
    out = clean(df, log)
    out.to_parquet(C.CLEAN_FILE, index=False)
    meta = {
        "source": source,
        "is_synthetic": bool(args.sample),
        "rows": int(len(out)),
        "default_rate": float(out["is_default"].mean()),
        "min_issue_year": C.MIN_ISSUE_YEAR,
        "max_issue_year": C.MAX_ISSUE_YEAR,
        "test_year": C.TEST_YEAR,
    }
    C.META_FILE.write_text(json.dumps(meta, indent=2))
    write_quality_report(log, out, source)
    print(f"Saved {len(out):,} rows to {C.CLEAN_FILE}")
    print(f"Default rate: {out['is_default'].mean():.2%}")


if __name__ == "__main__":
    main()
