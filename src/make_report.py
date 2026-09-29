"""Step 7: build reports/executive_summary.md from the real outputs of the earlier steps.

Every number in the summary is read from the generated tables / metrics, nothing is typed in by hand.
Usage: python src/make_report.py
"""
import json
import sys

import pandas as pd

import config as C


def pct(x, d=1):
    return f"{x * 100:.{d}f}%"


def seg(df, dimension):
    return df[df["dimension"] == dimension].copy()


def md_table(df, cols, headers, fmts):
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(f(r[c]) for c, f in zip(cols, fmts)) + " |")
    return "\n".join(lines)


def main():
    need = [C.TABLES / "segment_summary.csv", C.METRICS_FILE, C.TABLES / "policy_simulation.csv",
            C.TABLES / "model_deciles.csv"]
    missing = [p.name for p in need if not p.exists()]
    if missing:
        sys.exit(f"Missing outputs: {missing}. Run eda.py, model.py and policy_simulation.py first.")

    meta = json.loads(C.META_FILE.read_text()) if C.META_FILE.exists() else {}
    S = pd.read_csv(C.TABLES / "segment_summary.csv")
    M = json.loads(C.METRICS_FILE.read_text())
    P = pd.read_csv(C.TABLES / "policy_simulation.csv")
    D = pd.read_csv(C.TABLES / "model_deciles.csv")

    n_loans, overall = meta.get("rows"), meta.get("default_rate")
    if n_loans is None:
        g = seg(S, "grade")
        n_loans, overall = int(g["loans"].sum()), g["defaults"].sum() / g["loans"].sum()

    L = ["# CreditLens: Executive Summary", ""]
    if meta.get("is_synthetic"):
        L += ["> **SYNTHETIC DATA. This summary was generated from fake data to test the pipeline. "
              "Do not publish or quote any number in it.**", ""]
    L += [f"*Source: {meta.get('source', 'unknown')}. All figures below are computed by the pipeline from the "
          "cleaned data; see `reports/tables/` and `reports/figures/`.*", ""]

    L += ["## 1. Scope", "",
          f"- **{n_loans:,}** finished loans issued {meta.get('min_issue_year', C.MIN_ISSUE_YEAR)}-"
          f"{meta.get('max_issue_year', C.MAX_ISSUE_YEAR)} (Fully Paid, Charged Off or Default).",
          f"- Overall default rate: **{pct(overall)}**.",
          f"- Models trained on {M['meta']['train_rows']:,} loans issued before {M['meta']['test_year']} "
          f"and tested on {M['meta']['test_rows']:,} loans issued in {M['meta']['test_year']} "
          f"(test default rate {pct(M['meta']['test_default_rate'])}).", ""]

    L += ["## 2. Where the risk sits", ""]
    g = seg(S, "grade").sort_values("segment")
    if len(g) >= 2:
        lo, hi = g.iloc[0], g.iloc[-1]
        mono = bool((g["default_rate"].diff().dropna() > 0).all())
        L.append(f"- **Grade:** default rate rises from {pct(lo['default_rate'])} in grade {lo['segment']} to "
                 f"{pct(hi['default_rate'])} in grade {hi['segment']} "
                 f"({hi['default_rate'] / lo['default_rate']:.1f}x). "
                 f"{'The increase is steady across every grade.' if mono else 'The increase is not perfectly monotonic across grades.'}")
    t = seg(S, "term")
    if len(t) == 2:
        a, b = t.iloc[0], t.iloc[1]
        L.append(f"- **Term:** {a['segment']} loans default at {pct(a['default_rate'])} versus "
                 f"{pct(b['default_rate'])} for {b['segment']}.")
    p = seg(S, "purpose")
    p = p[p["loans"] >= 500].sort_values("default_rate", ascending=False)
    if len(p) >= 2:
        L.append(f"- **Purpose:** highest default rate is '{p.iloc[0]['segment']}' at {pct(p.iloc[0]['default_rate'])} "
                 f"(n={int(p.iloc[0]['loans']):,}); lowest is '{p.iloc[-1]['segment']}' at "
                 f"{pct(p.iloc[-1]['default_rate'])} (n={int(p.iloc[-1]['loans']):,}).")
    for dim, label in (("dti_band", "Debt-to-income"), ("fico_band", "FICO"), ("income_band", "Income")):
        x = seg(S, dim)
        x = x[x["loans"] >= 200]          # ignore tiny segments
        if len(x) >= 2:
            L.append(f"- **{label}:** default rate ranges from {pct(x['default_rate'].min())} "
                     f"({x.loc[x['default_rate'].idxmin(), 'segment']}) to {pct(x['default_rate'].max())} "
                     f"({x.loc[x['default_rate'].idxmax(), 'segment']}).")
    v = seg(S, "issue_year")
    if len(v) >= 2:
        L.append(f"- **Vintage:** default rate moves from {pct(v.iloc[0]['default_rate'])} for {v.iloc[0]['segment']} "
                 f"loans to {pct(v.iloc[-1]['default_rate'])} for {v.iloc[-1]['segment']} loans.")
    L.append("")

    L += ["## 3. Pricing versus risk", ""]
    if len(g):
        g = g.copy()
        g["spread"] = g["avg_int_rate"] - g["default_rate"] * 100
        thin = g.loc[g["spread"].idxmin()]
        L += [md_table(g, ["segment", "avg_int_rate", "default_rate", "spread"],
                       ["Grade", "Avg interest rate", "Default rate", "Rate minus default (pp)"],
                       [str, lambda x: f"{x:.2f}%", pct, lambda x: f"{x:.2f}"]), "",
              f"Grade {thin['segment']} has the thinnest gap between the rate charged and the observed default rate "
              f"({thin['spread']:.2f} percentage points"
              f"{'; the average rate is below the default rate' if thin['spread'] < 0 else ''}). "
              "This ignores recoveries, fees and funding cost, so it is a screening signal, not a profit figure.", ""]

    L += ["## 4. Model performance (held-out test year)", ""]
    mm = pd.DataFrame(M["models"])
    L += [md_table(mm, ["name", "roc_auc", "gini", "ks", "pr_auc"], ["Model", "ROC-AUC", "Gini", "KS", "PR-AUC"],
                   [str, lambda x: f"{x:.3f}"] * 1 + [lambda x: f"{x:.3f}"] * 3), ""]
    best = M.get("best_by_feature_set", {})
    if "full" in best and "borrower_only" in best:
        af = mm.loc[mm["name"] == best["full"], "roc_auc"].iloc[0]
        ab = mm.loc[mm["name"] == best["borrower_only"], "roc_auc"].iloc[0]
        L.append(f"- Best full model ({best['full']}): AUC {af:.3f}. Best borrower-only model "
                 f"({best['borrower_only']}): AUC {ab:.3f}. The lender-assigned grade, rate and installment add "
                 f"{(af - ab) * 100:.1f} AUC points on top of the borrower's own profile.")
    df_full = D[D["feature_set"] == "full"].sort_values("risk_decile")
    if len(df_full) == 10:
        top, bot = df_full.iloc[-1], df_full.iloc[0]
        top3 = df_full.iloc[-3:]["pct_of_all_defaults"].sum()
        L.append(f"- Riskiest decile defaults at {pct(top['actual_default_rate'])} versus "
                 f"{pct(bot['actual_default_rate'])} in the safest decile; the three riskiest deciles contain "
                 f"{pct(top3)} of all defaults.")
    L += [""]

    L += ["## 5. Approval-policy simulation", "",
          "Rejecting the applicants with the highest predicted default probability (test year):", ""]
    sel = P[P["reject_rate"].round(2).isin([0.10, 0.20, 0.30])]
    L += [md_table(sel, ["score", "reject_rate", "defaults_avoided_pct", "good_loans_lost_pct",
                         "approved_default_rate", "defaulted_principal_avoided_pct"],
                   ["Model", "Rejected", "Defaults avoided", "Good loans lost", "Approved default rate",
                    "Defaulted principal avoided"],
                   [str, lambda x: pct(x, 0), pct, pct, pct, pct]), "",
          "Defaulted principal is the gross amount lent, not net loss (no recovery data).", ""]

    L += ["## 6. Recommendations", ""]
    recs = []
    fs = P[(P["score"] == "full") & (P["reject_rate"].round(2) == 0.20)]
    if len(fs):
        r = fs.iloc[0]
        recs.append(f"**Use the score for triage, not blanket rejection.** Rejecting the riskiest 20% would avoid "
                    f"{pct(r['defaults_avoided_pct'])} of defaults but also lose {pct(r['good_loans_lost_pct'])} of good "
                    "loans. Route the riskiest decile to manual review, a lower limit or higher pricing before rejecting.")
    if len(g):
        recs.append(f"**Review pricing in grade {thin['segment']}**, where the rate charged leaves the smallest "
                    "gap over observed default rates (before recoveries and costs).")
    if len(p) >= 2:
        recs.append(f"**Watch '{p.iloc[0]['segment']}' loans** (default rate {pct(p.iloc[0]['default_rate'])}): "
                    "consider tighter limits or extra verification for this purpose.")
    if len(t) == 2:
        recs.append(f"**Reconsider long terms for weaker grades**: {b['segment']} loans default at "
                    f"{pct(b['default_rate'])} versus {pct(a['default_rate'])} for {a['segment']}.")
    recs.append("**Monitor drift.** Track default rate by issue quarter and compare predicted versus actual "
                "default rate by risk decile on each new vintage before trusting the score.")
    L += [f"{i}. {r}" for i, r in enumerate(recs, 1)] + [""]

    L += ["## 7. Limitations", "",
          "- Only accepted loans are observed, so applicants the lender rejected are missing (selection bias).",
          "- No profit, cost or recovery data: financial impact is gross principal, not net loss.",
          "- Grade, sub-grade and interest rate are lender-assigned; the borrower-only models show the signal without them.",
          "- Loans issued 2012-2015 in the US; results may not transfer to other periods or markets.",
          "- Correlations are associations, not causes. A model score should support, not replace, credit judgement.", ""]

    (C.REPORTS / "executive_summary.md").write_text("\n".join(L), encoding="utf-8")
    print(f"Wrote {C.REPORTS / 'executive_summary.md'}")


if __name__ == "__main__":
    main()
