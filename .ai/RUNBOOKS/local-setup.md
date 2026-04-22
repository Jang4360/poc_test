# Local Setup

## Goal

Document the minimal steps a contributor needs to run the project and its harness locally.

## Prerequisites

- Docker Desktop or compatible Docker Engine with Compose v2
- Java 21
- Python 3.11 or newer
- Git Bash on Windows for the repository guard scripts
- Review `AGENTS.md` and `CLAUDE.md` before editing code

## Local bootstrap

```bash
cp .env .env.local  # optional local override copy if you do not want to edit .env directly
```

## Standard flow

```bash
# 1. Verify the harness and generated adapters
scripts/verify.sh

# 2. Prepare the Python ETL environment
cd etl
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ..

# 3. Start PostGIS, GraphHopper, and the backend
docker compose up --build -d postgresql graphhopper backend

# 4. Run the repository smoke check
scripts/smoke.sh
```

## Notes

- `etl/sql/schema.sql` is mounted into the PostGIS container and is the stage-01 bootstrap schema source.
- `graphhopper/` is intentionally a runtime scaffold in stage 01. The custom encoded-value plugin lives under `graphhopper-plugin/` and is completed in workstream 04.
- The canonical places CSV for ETL is `etl/data/raw/place_merged_broad_category_final.csv`.
