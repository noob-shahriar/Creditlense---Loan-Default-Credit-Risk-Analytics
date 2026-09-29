"""Step 2: load the cleaned parquet into PostgreSQL and build the star schema.

Prerequisites: PostgreSQL running, a database created (default name: creditlens), and a .env file
(copy .env.example). Usage:
    python src/load_to_postgres.py
"""
import io
import sys

import pandas as pd
import psycopg2

import config as C
from data_prep import CLEAN_COLUMNS

CHUNK = 100_000


def run_sql_file(cur, name):
    sql = (C.SQL_DIR / name).read_text(encoding="utf-8")
    cur.execute(sql)
    print(f"  ran {name}")


def main():
    if not C.CLEAN_FILE.exists():
        sys.exit("Cleaned file not found. Run: python src/data_prep.py first.")
    try:
        conn = psycopg2.connect(**C.PG)
    except psycopg2.OperationalError as e:
        sys.exit(
            f"Could not connect to PostgreSQL ({e}).\n"
            "Check that PostgreSQL is running, the database exists, and .env has the right credentials."
        )
    conn.autocommit = False
    df = pd.read_parquet(C.CLEAN_FILE)[CLEAN_COLUMNS]
    df["issue_date"] = pd.to_datetime(df["issue_date"]).dt.strftime("%Y-%m-%d")
    print(f"Loading {len(df):,} rows into {C.PG['dbname']}.{C.PG_SCHEMA}.stg_loans ...")

    with conn, conn.cursor() as cur:
        run_sql_file(cur, "01_schema.sql")
        cols = ", ".join(CLEAN_COLUMNS)
        for start in range(0, len(df), CHUNK):
            buf = io.StringIO()
            df.iloc[start:start + CHUNK].to_csv(buf, index=False, header=False, na_rep="")
            buf.seek(0)
            cur.copy_expert(
                f"COPY {C.PG_SCHEMA}.stg_loans ({cols}) FROM STDIN WITH (FORMAT csv, NULL '')", buf
            )
            print(f"  copied {min(start + CHUNK, len(df)):,} / {len(df):,}")
        run_sql_file(cur, "02_star_schema.sql")
        cur.execute(f"SELECT COUNT(*), SUM(is_default) FROM {C.PG_SCHEMA}.fact_loans")
        n, d = cur.fetchone()
        print(f"fact_loans: {n:,} rows, {int(d):,} defaults")
    with conn.cursor() as cur:
        conn.autocommit = True
        cur.execute("ANALYZE")
    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
