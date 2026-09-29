"""Step 5: train default-prediction models with a time-based split.

Two feature sets:
  full           : application-time fields incl. lender-assigned grade / sub_grade / int_rate / installment
  borrower_only  : same, WITHOUT the lender-assigned fields (how much signal is in the borrower profile?)
Two models per set: logistic regression (interpretable) and gradient boosting (non-linear).

Usage: python src/model.py
"""
import json
import sys

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score, roc_curve
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler

import config as C

NUM_BASE = ["loan_amnt", "term_months", "annual_inc", "dti", "fico_avg", "emp_length_years", "delinq_2yrs",
            "inq_last_6mths", "open_acc", "pub_rec", "revol_bal", "revol_util", "total_acc", "mort_acc",
            "pub_rec_bankruptcies", "credit_history_years", "loan_to_income"]
CAT_BASE = ["home_ownership", "verification_status", "purpose", "application_type", "addr_state"]
LENDER_NUM = ["int_rate", "installment"]
LENDER_CAT = ["grade", "sub_grade"]

FEATURE_SETS = {
    "full": (NUM_BASE + LENDER_NUM, CAT_BASE + LENDER_CAT),
    "borrower_only": (NUM_BASE, CAT_BASE),
}
plt.rcParams.update({"figure.dpi": 110, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": 0.25, "font.size": 10})


def build_pipeline(kind, num, cat):
    if kind == "logistic":
        pre = ColumnTransformer([
            ("num", Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler())]), num),
            ("cat", Pipeline([("imp", SimpleImputer(strategy="constant", fill_value="Unknown")),
                              ("oh", OneHotEncoder(handle_unknown="ignore"))]), cat),
        ])
        model = LogisticRegression(max_iter=500, C=1.0)
    else:
        pre = ColumnTransformer([
            ("num", "passthrough", num),
            ("cat", Pipeline([("imp", SimpleImputer(strategy="constant", fill_value="Unknown")),
                              ("oe", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1))]), cat),
        ])
        mask = [False] * len(num) + [True] * len(cat)
        model = HistGradientBoostingClassifier(
            max_iter=300, learning_rate=0.06, max_leaf_nodes=31, l2_regularization=1.0,
            early_stopping=True, validation_fraction=0.1, categorical_features=mask,
            random_state=C.RANDOM_STATE)
    return Pipeline([("pre", pre), ("model", model)])


def evaluate(y, p):
    fpr, tpr, _ = roc_curve(y, p)
    auc = roc_auc_score(y, p)
    return {
        "roc_auc": float(auc), "gini": float(2 * auc - 1), "ks": float(np.max(tpr - fpr)),
        "pr_auc": float(average_precision_score(y, p)), "brier": float(brier_score_loss(y, p)),
        "base_rate": float(np.mean(y)),
    }, (fpr, tpr)


def decile_table(y, p):
    d = pd.DataFrame({"y": np.asarray(y), "p": np.asarray(p)})
    d["risk_decile"] = pd.qcut(d["p"].rank(method="first"), 10, labels=range(1, 11)).astype(int)  # 10 = riskiest
    t = d.groupby("risk_decile").agg(loans=("y", "size"), defaults=("y", "sum"),
                                     actual_default_rate=("y", "mean"), avg_predicted=("p", "mean")).reset_index()
    t["pct_of_all_defaults"] = t["defaults"] / t["defaults"].sum()
    t = t.sort_values("risk_decile", ascending=False)
    t["cumulative_pct_of_defaults_captured"] = t["pct_of_all_defaults"].cumsum()
    return t.sort_values("risk_decile")


def main():
    if not C.CLEAN_FILE.exists():
        sys.exit("Cleaned file not found. Run: python src/data_prep.py first.")
    C.ensure_dirs()
    df = pd.read_parquet(C.CLEAN_FILE)
    meta = json.loads(C.META_FILE.read_text()) if C.META_FILE.exists() else {}
    train = df[df["issue_year"] < C.TEST_YEAR]
    test = df[df["issue_year"] == C.TEST_YEAR].reset_index(drop=True)
    if train.empty or test.empty:
        sys.exit(f"Need loans issued before {C.TEST_YEAR} (train) and in {C.TEST_YEAR} (test). "
                 "Check MIN/MAX_ISSUE_YEAR and TEST_YEAR in src/config.py.")
    n_train_full = len(train)
    if len(train) > C.MAX_TRAIN_ROWS:
        train = train.sample(C.MAX_TRAIN_ROWS, random_state=C.RANDOM_STATE)
    print(f"Train: {len(train):,} rows (of {n_train_full:,}), issue years < {C.TEST_YEAR}. "
          f"Test: {len(test):,} rows, issue year {C.TEST_YEAR}.")

    results = {"meta": {"source": meta.get("source"), "is_synthetic": meta.get("is_synthetic", False),
                        "train_rows": int(len(train)), "train_rows_available": int(n_train_full),
                        "test_rows": int(len(test)), "test_year": C.TEST_YEAR,
                        "train_default_rate": float(train["is_default"].mean()),
                        "test_default_rate": float(test["is_default"].mean())},
               "models": []}
    scored = test[["loan_id", "issue_year", "loan_amnt", "grade", "term_months", "is_default"]].copy()
    curves, fitted = {}, {}

    for fs_name, (num, cat) in FEATURE_SETS.items():
        for kind in ("logistic", "gbm"):
            name = f"{fs_name}__{kind}"
            print(f"Training {name} ...")
            pipe = build_pipeline(kind, num, cat)
            pipe.fit(train[num + cat], train["is_default"])
            p = pipe.predict_proba(test[num + cat])[:, 1]
            metrics, curve = evaluate(test["is_default"], p)
            results["models"].append({"name": name, "feature_set": fs_name, "model": kind, **metrics})
            curves[name] = curve
            fitted[name] = (pipe, num, cat, p)
            joblib.dump(pipe, C.MODELS / f"{name}.joblib")
            print(f"  AUC {metrics['roc_auc']:.3f}  Gini {metrics['gini']:.3f}  KS {metrics['ks']:.3f}")

    # best model per feature set -> scored file, deciles, feature importance
    dec_frames = []
    for fs_name in FEATURE_SETS:
        cands = [m for m in results["models"] if m["feature_set"] == fs_name]
        best = max(cands, key=lambda m: m["roc_auc"])
        results.setdefault("best_by_feature_set", {})[fs_name] = best["name"]
        pipe, num, cat, p = fitted[best["name"]]
        scored[f"score_{fs_name}"] = p
        dt = decile_table(test["is_default"], p)
        dt.insert(0, "feature_set", fs_name)
        dec_frames.append(dt)

        # permutation importance on a test subsample
        sub = test.sample(min(20_000, len(test)), random_state=C.RANDOM_STATE)
        pi = permutation_importance(pipe, sub[num + cat], sub["is_default"], scoring="roc_auc",
                                    n_repeats=3, random_state=C.RANDOM_STATE, n_jobs=1)
        imp = pd.Series(pi.importances_mean, index=num + cat).sort_values()
        imp.rename("auc_drop_when_shuffled").to_csv(C.TABLES / f"feature_importance_{fs_name}.csv")
        fig, ax = plt.subplots(figsize=(7, 5.5))
        top = imp.tail(15)
        ax.barh(top.index, top.values, color="#2b6cb0")
        ax.set_xlabel("Drop in test ROC-AUC when the feature is shuffled")
        ax.set_title(f"Feature importance ({fs_name}, {best['model']})", loc="left", fontweight="bold")
        fig.tight_layout()
        fig.savefig(C.FIGURES / f"feature_importance_{fs_name}.png")
        plt.close(fig)

    dec = pd.concat(dec_frames, ignore_index=True)
    dec.to_csv(C.TABLES / "model_deciles.csv", index=False)
    dec.to_csv(C.DASH_DATA / "model_deciles.csv", index=False)

    # ROC curves
    fig, ax = plt.subplots(figsize=(6, 5.5))
    for name, (fpr, tpr) in curves.items():
        auc = next(m["roc_auc"] for m in results["models"] if m["name"] == name)
        ax.plot(fpr, tpr, label=f"{name} (AUC {auc:.3f})")
    ax.plot([0, 1], [0, 1], ls="--", color="grey")
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.set_title("ROC curves on the held-out test year", loc="left", fontweight="bold")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(C.FIGURES / "roc_curves.png")
    plt.close(fig)

    # decile chart for the full model
    d = dec[dec["feature_set"] == "full"]
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    ax.bar(d["risk_decile"], d["actual_default_rate"] * 100, color="#2b6cb0", label="Actual default rate")
    ax.plot(d["risk_decile"], d["avg_predicted"] * 100, color="#c53030", marker="o", label="Average predicted")
    ax.set_xlabel("Risk decile (10 = riskiest)")
    ax.set_ylabel("Default rate (%)")
    ax.set_xticks(range(1, 11))
    ax.set_title("Actual vs predicted default rate by risk decile (full model)", loc="left", fontweight="bold")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(C.FIGURES / "decile_calibration.png")
    plt.close(fig)

    # logistic coefficients (full set)
    pipe, num, cat, _ = fitted["full__logistic"]
    names = pipe.named_steps["pre"].get_feature_names_out()
    coefs = pd.Series(pipe.named_steps["model"].coef_[0], index=names).sort_values()
    coefs.rename("coefficient").to_csv(C.TABLES / "logistic_coefficients_full.csv")

    C.METRICS_FILE.write_text(json.dumps(results, indent=2))
    scored.to_parquet(C.SCORED_FILE, index=False)
    sample_n = min(100_000, len(scored))
    scored.sample(sample_n, random_state=C.RANDOM_STATE).to_csv(C.DASH_DATA / "scored_test_sample.csv", index=False)
    print(f"Saved metrics to {C.METRICS_FILE}")
    if meta.get("is_synthetic"):
        print("WARNING: these outputs come from SYNTHETIC data. Do not commit or report them.")


if __name__ == "__main__":
    main()
