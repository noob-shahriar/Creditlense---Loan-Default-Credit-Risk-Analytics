"""Step 6: simulate approval cutoffs on the held-out test year.

For each reject rate, reject the riskiest applicants (highest predicted default probability) and measure:
  - share of all defaults avoided
  - share of good (fully paid) loans lost
  - default rate of the approved book
  - share of defaulted principal avoided (gross principal issued, NOT profit or net loss)

Limits: the data has no interest income, fees or recoveries, so this is a risk trade-off, not a profit model.

Usage: python src/policy_simulation.py
"""
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config as C

REJECT_RATES = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50]


def simulate(df, score_col):
    d = df.sort_values(score_col, ascending=False).reset_index(drop=True)
    n = len(d)
    total_def = d["is_default"].sum()
    total_good = n - total_def
    def_principal = (d["loan_amnt"] * d["is_default"]).sum()
    base_rate = d["is_default"].mean()
    rows = []
    for r in REJECT_RATES:
        k = int(round(n * r))
        rej, app = d.iloc[:k], d.iloc[k:]
        rows.append({
            "score": score_col.replace("score_", ""),
            "reject_rate": r,
            "cutoff_score": float(rej[score_col].min()),
            "applicants_rejected": k,
            "defaults_avoided_pct": rej["is_default"].sum() / total_def,
            "good_loans_lost_pct": (k - rej["is_default"].sum()) / total_good,
            "baseline_default_rate": base_rate,
            "approved_default_rate": app["is_default"].mean(),
            "default_rate_reduction_pp": (base_rate - app["is_default"].mean()) * 100,
            "defaulted_principal_avoided_pct": (rej["loan_amnt"] * rej["is_default"]).sum() / def_principal,
            "lift": (rej["is_default"].sum() / total_def) / r,
        })
    return pd.DataFrame(rows)


def main():
    if not C.SCORED_FILE.exists():
        sys.exit("Scored test file not found. Run: python src/model.py first.")
    C.ensure_dirs()
    df = pd.read_parquet(C.SCORED_FILE)
    score_cols = [c for c in df.columns if c.startswith("score_")]
    sim = pd.concat([simulate(df, c) for c in score_cols], ignore_index=True)
    sim.to_csv(C.TABLES / "policy_simulation.csv", index=False)
    sim.to_csv(C.DASH_DATA / "policy_simulation.csv", index=False)

    fig, axes = plt.subplots(1, len(score_cols), figsize=(6.2 * len(score_cols), 4.4), squeeze=False)
    for ax, col in zip(axes[0], score_cols):
        s = sim[sim["score"] == col.replace("score_", "")]
        ax.plot(s["reject_rate"] * 100, s["defaults_avoided_pct"] * 100, marker="o", color="#2b6cb0",
                label="Defaults avoided")
        ax.plot(s["reject_rate"] * 100, s["good_loans_lost_pct"] * 100, marker="o", color="#c53030",
                label="Good loans lost")
        ax.plot(s["reject_rate"] * 100, s["reject_rate"] * 100, ls="--", color="grey", label="Random rejection")
        ax.set_xlabel("Applicants rejected (%)")
        ax.set_ylabel("% of all defaults / all good loans")
        ax.set_title(f"Cutoff trade-off ({col.replace('score_', '')} model)", loc="left", fontweight="bold")
        ax.grid(alpha=0.25)
        ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(C.FIGURES / "policy_tradeoff.png")
    plt.close(fig)
    print(sim.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
