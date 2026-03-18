# StreamFlix Quick Start

## 1) Prepare environment

```bash
cp .env.example .env
```

Edit `.env` and set:

- `ASTRA_DB_API_ENDPOINT`
- `ASTRA_DB_APPLICATION_TOKEN`
- `ASTRA_DB_KEYSPACE` (usually `default_keyspace`)

## 2) Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r backend/requirements.txt jupyterlab
cd frontend && npm install && cd ..
```

## 3) Run notebook ingestion (important env-loading step)

Start Jupyter from the same shell after exporting `.env`:

```bash
source .venv/bin/activate
set -a
source .env
set +a
jupyter lab notebook/streamflix_astra_workshop.ipynb
```

In Jupyter, run all cells in order.

Expected checks in output:

- non-zero `shows` count
- seeded rows for `home_rails_by_profile` and `user_session_events`
- non-empty semantic search sample results

## 4) Start backend + frontend

```bash
./scripts/start_workshop.sh
```

Default ports:

- frontend: `http://localhost:5174`
- backend: `http://localhost:8010`

If port `5174` is occupied, update `.env` first:

```bash
FRONTEND_PORT=5175
CORS_ORIGINS=http://localhost:5175,http://127.0.0.1:5175
VITE_API_BASE_URL=http://localhost:8010
```

Then rerun:

```bash
./scripts/start_workshop.sh
```

## 5) Verify app behavior

- rails render on home page
- semantic search returns results
- click a search result to pin featured details
- click `Watch`/`Watch Now` and refresh rails to see continue-watching updates
