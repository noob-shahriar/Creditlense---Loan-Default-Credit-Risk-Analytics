"""Step 3: run every query in sql/03_analysis_queries.sql and save results as CSV.

Usage: python src/run_sql_analysis.py
"""
import re
import sys

import pandas as pd
import psycopg2

import config as C


def parse_queries(text):
    """Split the SQL file on '-- name:' markers -> {name: sql}."""
    parts = re.split(r"^-- name:\s*(\S+)\s*$", text, flags=re.MULTILINE)
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}


def main():
    C.ensure_dirs()
    queries = parse_queries((C.SQL_DIR / "03_analysis_queries.sql").read_text(encoding="utf-8"))
    try:
        conn = psycopg2.connect(**C.PG)
    except psycopg2.OperationalError as e:
        sys.exit(f"Could not connect to PostgreSQL ({e}). Run src/load_to_postgres.py first and check .env.")
    with conn, conn.cursor() as cur:
        cur.execute(f"SET search_path TO {C.PG_SCHEMA}, public")
        for name, sql in queries.items():
            cur.execute(sql)
            cols = [d[0] for d in cur.description]
            df = pd.DataFrame(cur.fetchall(), columns=cols)
            df.to_csv(C.SQL_RESULTS / f"{name}.csv", index=False)
            print(f"{name}: {len(df)} rows")
    conn.close()
    print(f"Saved results to {C.SQL_RESULTS}")


if __name__ == "__main__":
    main()
