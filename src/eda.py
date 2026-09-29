"""Step 4: exploratory analysis. Saves segment tables (CSV) and charts (PNG).

Usage: python src/eda.py
"""
import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config as C

PALETTE = {"bar": "#2b6cb0", "line": "#c53030", "muted": "#a0aec0"}
plt.rcParams.update({"figure.dpi": 110, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": 0.25, "font.size": 10})


def summarize(df, col, dimension, order=None):
    g = df.groupby(col, observed=True).agg(
        loans=("is_default", "size"), defaults=("is_default", "sum"),
        default_rate=("is_default", "mean"), avg_int_rate=("int_rate", "mean"),
        avg_loan_amnt=("loan_amnt", "mean"), total_principal=("loan_amnt", "sum"),
    ).reset_index().rename(columns={col: "segment"})
    g["segment"] = g["segment"].astype(str)
    if order is not None:
        g["_o"] = g["segment"].map({str(k): i for i, k in enumerate(order)})
        g = g.sort_values("_o").drop(columns="_o")
    g.insert(0, "dimension", dimension)
    return g


def bar_chart(tbl, title, fname, overall, xlabel="", rotate=0):
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.bar(tbl["segment"], tbl["default_rate"] * 100, color=PALETTE["bar"])
    ax.axhline(overall * 100, color=PALETTE["line"], ls="--", lw=1.4, label=f"Overall {overall:.1%}")
    for i, (rate, n) in enumerate(zip(tbl["default_rate"], tbl["loans"])):
        ax.text(i, rate * 100 + 0.3, f"{rate:.1%}", ha="center", fontsize=8)
        ax.text(i, 0.4, f"n={n:,}", ha="center", fontsize=7, color="white", rotation=90, va="bottom")
    ax.set_ylabel("Default rate (%)")
    ax.set_xlabel(xlabel)
    ax.set_title(title, loc="left", fontweight="bold")
    ax.legend(frameon=False)
    plt.setp(ax.get_xticklabels(), rotation=rotate, ha="right" if rotate else "center")
    fig.tight_layout()
    fig.savefig(C.FIGURES / fname)
    plt.close(fig)


def main():
    if not C.CLEAN_FILE.exists():
        sys.exit("Cleaned file not found. Run: python src/data_prep.py first.")
    C.ensure_dirs()
    df = pd.read_parquet(C.CLEAN_FILE)
    meta = json.loads(C.META_FILE.read_text()) if C.META_FILE.exists() else {}
    overall = df["is_default"].mean()
    print(f"{len(df):,} loans, overall default rate {overall:.2%}")

    grade_order = sorted(df["grade"].dropna().unique())
    df["income_band"] = pd.cut(df["annual_inc"], [0, 30e3, 50e3, 75e3, 100e3, 150e3, np.inf],
                               labels=["<30k", "30-50k", "50-75k", "75-100k", "100-150k", "150k+"])
    df["dti_band"] = pd.cut(df["dti"], [-0.01, 10, 20, 30, 40, np.inf],
                            labels=["<10", "10-20", "20-30", "30-40", "40+"])
    df["fico_band"] = pd.cut(df["fico_avg"], [0, 680, 700, 720, 750, 900],
                             labels=["<680", "680-699", "700-719", "720-749", "750+"])
    df["term_label"] = df["term_months"].astype("Int64").astype(str) + " months"
    df["loan_size_band"] = pd.qcut(df["loan_amnt"], 4, labels=["Q1 (small)", "Q2", "Q3", "Q4 (large)"])

    specs = [
        ("grade", "grade", grade_order, "Default rate by LendingClub grade", "default_by_grade.png", "Grade", 0),
        ("term_label", "term", None, "Default rate by loan term", "default_by_term.png", "", 0),
        ("income_band", "income_band", list(df["income_band"].cat.categories),
         "Default rate by annual income", "default_by_income.png", "Annual income", 0),
        ("dti_band", "dti_band", list(df["dti_band"].cat.categories),
         "Default rate by debt-to-income", "default_by_dti.png", "DTI", 0),
        ("fico_band", "fico_band", list(df["fico_band"].cat.categories),
         "Default rate by FICO band", "default_by_fico.png", "FICO", 0),
        ("home_ownership", "home_ownership", None, "Default rate by home ownership",
         "default_by_home.png", "", 0),
        ("verification_status", "verification_status", None, "Default rate by income verification",
         "default_by_verification.png", "", 0),
        ("loan_size_band", "loan_size", list(df["loan_size_band"].cat.categories),
         "Default rate by loan size quartile", "default_by_loan_size.png", "", 0),
    ]
    frames = []
    for col, dim, order, title, fname, xlabel, rot in specs:
        t = summarize(df, col, dim, order)
        frames.append(t)
        bar_chart(t, title, fname, overall, xlabel, rot)

    # purpose and state: only segments with enough volume, sorted by risk
    for col, dim, minn, title, fname in [
        ("purpose", "purpose", 500, "Default rate by loan purpose", "default_by_purpose.png"),
        ("addr_state", "state", 1000, "Default rate by state (top 15 riskiest, n>=1000)", "default_by_state.png"),
    ]:
        t = summarize(df, col, dim)
        t = t[t["loans"] >= minn].sort_values("default_rate", ascending=False)
        frames.append(t)
        bar_chart(t.head(15), title, fname, overall, rotate=45)

    # vintage
    vint = summarize(df, "issue_year", "issue_year", order=sorted(df["issue_year"].unique()))
    frames.append(vint)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(vint["segment"], vint["default_rate"] * 100, marker="o", color=PALETTE["bar"])
    ax2 = ax.twinx()
    ax2.bar(vint["segment"], vint["loans"], alpha=0.15, color=PALETTE["muted"])
    ax2.set_ylabel("Loans issued")
    ax2.grid(False)
    ax.set_ylabel("Default rate (%)")
    ax.set_title("Default rate by issue year (vintage)", loc="left", fontweight="bold")
    fig.tight_layout()
    fig.savefig(C.FIGURES / "default_by_vintage.png")
    plt.close(fig)

    # pricing vs risk
    g = summarize(df, "grade", "grade", grade_order)
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    x = np.arange(len(g))
    ax.bar(x - 0.2, g["avg_int_rate"], 0.4, label="Average interest rate (%)", color=PALETTE["bar"])
    ax.bar(x + 0.2, g["default_rate"] * 100, 0.4, label="Observed default rate (%)", color=PALETTE["line"])
    ax.set_xticks(x)
    ax.set_xticklabels(g["segment"])
    ax.set_title("Pricing vs risk by grade", loc="left", fontweight="bold")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(C.FIGURES / "pricing_vs_risk.png")
    plt.close(fig)

    # numeric drivers: correlation with default
    num = ["loan_amnt", "int_rate", "annual_inc", "dti", "fico_avg", "revol_util", "revol_bal",
           "open_acc", "total_acc", "delinq_2yrs", "inq_last_6mths", "pub_rec", "credit_history_years",
           "emp_length_years", "loan_to_income", "term_months"]
    corr = df[num + ["is_default"]].corr(method="spearman")["is_default"].drop("is_default")
    corr = corr.reindex(corr.abs().sort_values().index)
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.barh(corr.index, corr.values, color=[PALETTE["line"] if v > 0 else PALETTE["bar"] for v in corr.values])
    ax.set_title("Spearman correlation with default", loc="left", fontweight="bold")
    fig.tight_layout()
    fig.savefig(C.FIGURES / "correlation_with_default.png")
    plt.close(fig)
    corr.rename("spearman_with_default").to_csv(C.TABLES / "correlation_with_default.csv")

    seg = pd.concat(frames, ignore_index=True)
    seg.to_csv(C.TABLES / "segment_summary.csv", index=False)
    seg.to_csv(C.DASH_DATA / "segment_summary.csv", index=False)
    print(f"Saved {len(seg)} segment rows and charts to {C.REPORTS}")
    if meta.get("is_synthetic"):
        print("WARNING: these outputs come from SYNTHETIC data. Do not commit or report them.")


if __name__ == "__main__":
    main()
