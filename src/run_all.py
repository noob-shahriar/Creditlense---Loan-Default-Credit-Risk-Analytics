"""Run the whole CreditLens pipeline in order.

Examples:
    python src/run_all.py                      # real data in data/raw/ + PostgreSQL steps
    python src/run_all.py --skip-sql           # everything except PostgreSQL
    python src/run_all.py --sample --skip-sql  # smoke test on SYNTHETIC data (never report its numbers)
    python src/run_all.py --raw "C:/data/accepted_2007_to_2018Q4.csv.gz"
"""
import argparse
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent


def run(script, *extra):
    cmd = [sys.executable, str(SRC / script), *extra]
    print(f"\n=== {' '.join(['python', 'src/' + script, *extra])} ===", flush=True)
    r = subprocess.run(cmd)
    if r.returncode != 0:
        sys.exit(f"Step failed: {script}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", help="path to the raw accepted-loans CSV")
    ap.add_argument("--sample", action="store_true", help="use synthetic data (pipeline test only)")
    ap.add_argument("--skip-sql", action="store_true", help="skip the PostgreSQL steps")
    a = ap.parse_args()

    prep_args = ["--sample"] if a.sample else (["--raw", a.raw] if a.raw else [])
    run("data_prep.py", *prep_args)
    if not a.skip_sql:
        run("load_to_postgres.py")
        run("run_sql_analysis.py")
    run("eda.py")
    run("model.py")
    run("policy_simulation.py")
    run("make_report.py")
    print("\nAll steps finished. Open reports/executive_summary.md and reports/figures/.")
    if a.sample:
        print("REMINDER: outputs were generated from SYNTHETIC data. Do not commit or publish them.")


if __name__ == "__main__":
    main()
