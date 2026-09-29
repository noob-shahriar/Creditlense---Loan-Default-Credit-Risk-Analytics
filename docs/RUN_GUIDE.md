# Run Guide (VS Code)

Works on Windows, macOS and Linux. Commands marked (Windows) or (macOS/Linux) differ; the rest are identical.

## 0. Install once
1. **Python 3.10 or newer**: https://www.python.org/downloads/ (Windows: tick "Add Python to PATH").
2. **VS Code** and its **Python** extension (Microsoft).
3. **Git**: https://git-scm.com/downloads
4. **PostgreSQL 14+** (optional but recommended, used for the SQL layer): https://www.postgresql.org/download/
   Remember the password you set for the `postgres` user. pgAdmin is installed with it.

## 1. Open the project
1. Unzip the project (or `git clone https://github.com/noob-shahriar/Creditlense---Loan-Default-Credit-Risk-Analytics.git`).
2. VS Code -> **File -> Open Folder** -> select the project folder.
3. Open a terminal: **Terminal -> New Terminal**.

## 2. Create the environment and install packages
(Windows PowerShell)
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
If PowerShell blocks activation: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then activate again.

(macOS/Linux)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
In VS Code press `Ctrl+Shift+P` -> **Python: Select Interpreter** -> choose the one inside `.venv`.

## 3. Get the data
1. Sign in to Kaggle and open https://www.kaggle.com/datasets/wordsforthewise/lending-club
2. Download the dataset and extract it.
3. Copy the **accepted** loans file (its name starts with `accepted_`, `.csv` or `.csv.gz`) into `data/raw/`.
   Do **not** use the "rejected" file. The raw data is large and is git-ignored, so it is never committed.

## 4. Smoke test (2 minutes, no data or database needed)
```bash
python src/run_all.py --sample --skip-sql
python -m pytest -q tests
```
This uses fake generated data purely to confirm your setup works. **Never report or commit its numbers.**
Delete the generated outputs afterwards: remove `reports/data_quality.md`, `reports/executive_summary.md`,
`reports/model_metrics.json`, and the files inside `reports/figures`, `reports/tables`, `dashboard/data`
(keep the `.gitkeep` files), then re-run on the real data.

## 5. Set up PostgreSQL (optional, needed for the SQL layer)
1. Open pgAdmin (or `psql`) and create a database named `creditlens`:
   `CREATE DATABASE creditlens;`
2. Copy `.env.example` to `.env` and put your password in it:
   (Windows) `copy .env.example .env`   (macOS/Linux) `cp .env.example .env`
   Edit `.env` (`PGPASSWORD=...`). `.env` is git-ignored.

## 6. Run on the real data
Everything in one go:
```bash
python src/run_all.py
```
No PostgreSQL? Use `python src/run_all.py --skip-sql`. Data file elsewhere? Use
`python src/run_all.py --raw "path/to/accepted_2007_to_2018Q4.csv.gz"`.

Or step by step (each step reads the previous step's output):
| Step | Command | Produces |
|---|---|---|
| 1 Clean | `python src/data_prep.py` | `data/processed/loans_clean.parquet`, `reports/data_quality.md` |
| 2 Load to PostgreSQL | `python src/load_to_postgres.py` | star schema in schema `creditlens` |
| 3 SQL analysis | `python src/run_sql_analysis.py` | `reports/sql_results/*.csv` |
| 4 EDA | `python src/eda.py` | `reports/figures/*.png`, `reports/tables/`, `dashboard/data/` |
| 5 Models | `python src/model.py` | `reports/model_metrics.json`, scored test set, feature importance |
| 6 Policy | `python src/policy_simulation.py` | `reports/tables/policy_simulation.csv`, tradeoff chart |
| 7 Report | `python src/make_report.py` | `reports/executive_summary.md` |

Expect the full run to take roughly 10-30 minutes on a typical laptop (reading the large CSV and training four models).
If memory is tight, lower `MAX_TRAIN_ROWS` in `src/config.py`.

## 7. Check the results before you publish
- Read `reports/data_quality.md` and `reports/executive_summary.md`; they are generated from your real run.
- Look through `reports/figures/`. Sanity check: default rate should rise from grade A to G.
- Copy your headline numbers into the "Results" section of `README.md`.
- Build the dashboard from `dashboard/data/` using `dashboard/POWERBI_GUIDE.md` and add screenshots to `dashboard/`.

## 8. Push to GitHub
The project already contains a git history and the remote is set. From the VS Code terminal:
```bash
git remote -v                 # should show your GitHub repo URL
git branch -M main
git push -u origin main
```
The first push asks you to sign in to GitHub (browser prompt via Git Credential Manager). If it asks for a
password, use a **Personal Access Token** (GitHub -> Settings -> Developer settings -> Tokens), not your account password.
If the GitHub repo was created with a README, run `git pull origin main --allow-unrelated-histories` first, resolve the
README conflict, then push.

After running on real data, commit your results as new commits:
```bash
git add reports dashboard README.md
git commit -m "docs: add results from full run on LendingClub data"
git push
```

## Troubleshooting
| Problem | Fix |
|---|---|
| `No raw file found in data/raw/` | Put the accepted CSV in `data/raw/`, or pass `--raw path` |
| `Could not connect to PostgreSQL` | Start the PostgreSQL service, check the database exists and `.env` values |
| `ModuleNotFoundError` | Activate `.venv` and run `pip install -r requirements.txt` |
| `MemoryError` | Close other apps; lower `MAX_TRAIN_ROWS` in `src/config.py` |
| Need loans before/in test year error | Check `MIN_ISSUE_YEAR`, `MAX_ISSUE_YEAR`, `TEST_YEAR` in `src/config.py` |
