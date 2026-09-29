"""Central configuration for CreditLens."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
DATA_SAMPLE = ROOT / "data" / "sample"
SQL_DIR = ROOT / "sql"
REPORTS = ROOT / "reports"
FIGURES = REPORTS / "figures"
TABLES = REPORTS / "tables"
SQL_RESULTS = REPORTS / "sql_results"
DASH_DATA = ROOT / "dashboard" / "data"
MODELS = ROOT / "models"

CLEAN_FILE = DATA_PROCESSED / "loans_clean.parquet"
SCORED_FILE = DATA_PROCESSED / "test_scored.parquet"
META_FILE = DATA_PROCESSED / "run_meta.json"
METRICS_FILE = REPORTS / "model_metrics.json"

# Scope (see docs/PROJECT_SCOPE.md)
MIN_ISSUE_YEAR = 2012
MAX_ISSUE_YEAR = 2015
TEST_YEAR = 2015            # train: issue_year < TEST_YEAR, test: issue_year == TEST_YEAR
GOOD_STATUS = ["Fully Paid"]
BAD_STATUS = ["Charged Off", "Default"]
RANDOM_STATE = 42
MAX_TRAIN_ROWS = 400_000    # random subsample of the training set to keep laptops happy

PG = {
    "host": os.getenv("PGHOST", "localhost"),
    "port": int(os.getenv("PGPORT", "5432")),
    "dbname": os.getenv("PGDATABASE", "creditlens"),
    "user": os.getenv("PGUSER", "postgres"),
    "password": os.getenv("PGPASSWORD", ""),
}
PG_SCHEMA = "creditlens"


def ensure_dirs():
    for d in (DATA_PROCESSED, DATA_SAMPLE, FIGURES, TABLES, SQL_RESULTS, DASH_DATA, MODELS):
        d.mkdir(parents=True, exist_ok=True)
