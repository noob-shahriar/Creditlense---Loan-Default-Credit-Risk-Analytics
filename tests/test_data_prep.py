import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import config as C  # noqa: E402
import data_prep  # noqa: E402
import generate_sample_data  # noqa: E402


def _clean_sample(tmp_path):
    path = generate_sample_data.generate(n=6000, seed=1, path=tmp_path / "s.csv")
    raw = pd.read_csv(path, usecols=lambda c: c in data_prep.USECOLS, low_memory=False)
    for c in ("id", "emp_length", "earliest_cr_line", "fico_range_low", "fico_range_high"):
        if c not in raw.columns:
            raw[c] = None
    log = []
    return data_prep.clean(raw, log), log


def test_target_is_binary_and_only_finished_loans(tmp_path):
    out, _ = _clean_sample(tmp_path)
    assert set(out["is_default"].unique()) <= {0, 1}
    assert not out["loan_status"].isin(["Current", "Late (31-120 days)"]).any()


def test_scope_window_and_columns(tmp_path):
    out, _ = _clean_sample(tmp_path)
    assert out["issue_year"].between(C.MIN_ISSUE_YEAR, C.MAX_ISSUE_YEAR).all()
    assert list(out.columns) == data_prep.CLEAN_COLUMNS
    assert set(out["term_months"].dropna().unique()) <= {36, 60}


def test_invalid_values_become_missing_and_no_duplicates(tmp_path):
    out, _ = _clean_sample(tmp_path)
    assert (out["annual_inc"].dropna() > 0).all()
    assert (out["dti"].dropna() >= 0).all()
    assert out["loan_id"].is_unique


def test_no_leaky_columns_loaded():
    leaky = {"total_pymnt", "total_rec_prncp", "recoveries", "last_pymnt_amnt", "out_prncp"}
    assert leaky.isdisjoint(data_prep.USECOLS)
