# FORME.md

## 1. The Big Picture (Project Overview)

### Executive summary (plain-English version)
This project is a hands-on teaching app called **StreamFlix**. It looks like a streaming homepage, but its real purpose is to teach how to use **Astra DB** for two different jobs at once: classic app data (rows/tables) and smart semantic search (vector search). A participant can load demo content through a notebook, open the web app, search with natural language, and see personalized rails update after watch actions. Think of it as a workshop-in-a-box: data setup, backend, frontend, and demo journey are all bundled together.

### What problem this solves and for whom
This solves a very specific problem: **“How do I teach NoSQL + vector concepts quickly to non-experts and developers in one hour?”**

It is built for:
- Workshop instructors running live sessions
- Participants learning Astra DB for the first time
- Product/technical leads who want a concrete demo of tables + vectors in one flow

### How users interact with it (user journey)
A participant journey looks like this:
1. Create Astra DB and copy API endpoint + token.
2. Run the notebook to create schema and seed data.
3. Start backend and frontend locally.
4. Open the StreamFlix page, run semantic search, click a show, and trigger “continue watching” updates.

### If this were a restaurant
Imagine a themed restaurant:
- **Dining room (frontend)**: where guests browse dishes and place requests.
- **Kitchen pass (backend API)**: where all requests are translated into actions.
- **Pantry shelves (Astra tables)**: organized bins for predictable items (rails, session events).
- **Chef’s intuition board (vector collection)**: helps find similar dishes by meaning, not exact keywords.
- **Training manual (notebook)**: sets up the kitchen before service starts.

---

## 2. Technical Architecture — The Blueprint

### Simple architecture diagram (text)

```text
[Browser / React App]
        |
        | HTTP (/api/*)
        v
[FastAPI Backend]
        |
        | Astra Data API
        v
[Astra DB Serverless]
   |            |
   |            +--> Table: user_session_events
   +--> Table: home_rails_by_profile
   +--> Collection: shows (vector search)

[Notebook + Seed Files] --> (create schema + seed data) --> [Astra DB]
```

### Building tour (restaurant style)

#### Front desk: Frontend UI
- File: [frontend/src/App.jsx](frontend/src/App.jsx)
- This is what users touch: hero panel, rails, search panel, admin menu.
- It calls backend APIs through [frontend/src/lib/api.js](frontend/src/lib/api.js).

**What could go wrong?**
- Backend URL mismatch (`VITE_API_BASE_URL`) causes “Failed to fetch”.
- Port mismatch (`5173` vs `5174`) can make pages open but data fail to load.

#### Kitchen: Backend API layer
- File: [backend/app/main.py](backend/app/main.py)
- Routes like `/api/home`, `/api/search`, `/api/recommendations`, `/api/session/events`.
- Delegates business/data logic to repository class.

**What could go wrong?**
- Missing Astra env vars => API returns 503.
- Missing schema (`shows` collection/tables not created) => Data API errors.

#### Head chef: Repository logic
- File: [backend/app/repository.py](backend/app/repository.py)
- Handles query logic, assembling rails, semantic search, recommendations, and session writes.
- Converts raw DB documents into stable API payload (`ShowCard`).

**What could go wrong?**
- If seed data is incomplete or types are malformed, card mapping can fail or return weak metadata.
- Recommendation quality depends heavily on session event freshness and metadata quality.

#### Filing cabinets: Data model in Astra
- Defined in notebook: [notebook/streamflix_astra_workshop.ipynb](notebook/streamflix_astra_workshop.ipynb)
- Uses **hybrid persistence model**:
  - tables for deterministic/profile-based rails and events
  - collection for flexible show docs + vectors

**What could go wrong?**
- Table queries without partition keys can cause warnings/performance penalties.
- If collection isn’t vectorized correctly, semantic search relevance drops.

#### Training room: Notebook and scripts
- Notebook: [notebook/streamflix_astra_workshop.ipynb](notebook/streamflix_astra_workshop.ipynb)
- Data generation scripts:
  - [scripts/fetch_tvmaze_snapshot.py](scripts/fetch_tvmaze_snapshot.py)
  - [scripts/generate_seed_profiles.py](scripts/generate_seed_profiles.py)

**What could go wrong?**
- Notebook started without env vars loaded => connection errors.
- TMDB enrichment key missing/invalid => lower metadata quality or generation failures.

### Why these choices (and not obvious alternatives)

1. **FastAPI instead of a heavier backend framework**
- Why: very fast to build/read, automatic API docs, good for workshop speed.
- Alternative: Django/Flask.
- Trade-off: less built-in “enterprise guardrails” unless explicitly added.

2. **Astra collection + tables together (hybrid)**
- Why: teaches both classic NoSQL access patterns and vector search in one app.
- Alternative: only tables or only documents.
- Trade-off: more moving parts, but much better educational value.

3. **Pre-enriched local snapshot instead of runtime live API calls**
- Why: workshop reliability; no external metadata dependency during demo.
- Alternative: live TV APIs at runtime.
- Trade-off: data can age; snapshot refresh is a maintenance task.

4. **Notebook-first ingestion**
- Why: easier for workshop participants to follow step-by-step with visible outputs.
- Alternative: hidden seed script only.
- Trade-off: notebook environment/setup can confuse first-time users.

### Clever/unusual choices worth noting
- Backend notebook launcher tries to detect running Jupyter server root and token dynamically ([backend/app/main.py](backend/app/main.py)).
- Recommendation “basis” text is built from recent watched shows + metadata, then used for vector search ([backend/app/repository.py#L96](backend/app/repository.py#L96)).
- Notebook reseeds deterministically and avoids zero-filter table scans in validation cells.

---

## 3. Codebase Structure — The Filing System

### Folder tree (top levels)

```text
.
├── backend/
│   ├── app/
│   │   ├── config.py
│   │   ├── main.py
│   │   ├── models.py
│   │   └── repository.py
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── lib/
│   │   ├── App.jsx
│   │   └── styles.css
│   ├── tests/e2e/
│   └── package.json
├── data/
│   ├── tv_shows_300.json
│   └── seed_profiles.json
├── notebook/
│   └── streamflix_astra_workshop.ipynb
├── scripts/
│   ├── start_workshop.sh
│   ├── fetch_tvmaze_snapshot.py
│   └── generate_seed_profiles.py
├── README.md
├── QUICKSTART.md
└── WORKSHOP.md
```

### Major folders explained

#### `backend/`
- **What lives here:** API server and Astra data access logic.
- **When to open it:** any behavior/API/data issue.
- **How it relates:** frontend talks to these routes; notebook seeds the data this layer reads.

#### `frontend/`
- **What lives here:** user interface, API calls, visual styles, E2E smoke tests.
- **When to open it:** UI changes, interaction bugs, failed fetches.
- **How it relates:** depends on backend endpoint contracts (`ShowCard`, home/search/reco payloads).

#### `data/`
- **What lives here:** prebuilt show dataset and profile/session seed fixtures.
- **When to open it:** content quality adjustments, workshop repeatability, metadata improvements.
- **How it relates:** notebook ingests this directly into Astra.

#### `notebook/`
- **What lives here:** guided setup and ingestion playbook.
- **When to open it:** workshop runtime and data initialization troubleshooting.
- **How it relates:** creates all schema the backend expects.

#### `scripts/`
- **What lives here:** local startup and offline data generation tooling.
- **When to open it:** automate local runs or refresh seed datasets.
- **How it relates:** feeds `data/` and launches both app tiers.

### Non-obvious naming conventions
- `home_rails_by_profile` and `user_session_events` use descriptive table names for workshop readability.
- `ShowCard` in backend models is the “universal card contract” for home/search/recommendations.
- `DEFAULT_PROFILE_ID` is used to make the demo work even without auth/login.

### Entry points (where things start)
- Backend runtime: [backend/app/main.py](backend/app/main.py)
- Frontend runtime: [frontend/src/main.jsx](frontend/src/main.jsx)
- Workshop setup: [notebook/streamflix_astra_workshop.ipynb](notebook/streamflix_astra_workshop.ipynb)
- Local orchestration: [scripts/start_workshop.sh](scripts/start_workshop.sh)

---

## 4. Connections & Data Flow — How Things Talk to Each Other

Below are three core actions told as “what happens behind the curtain.”

### Action A: User opens homepage rails

1. **User opens the page** at frontend URL.
2. `App.jsx` runs `loadHome()` and `loadRecommendations()` ([frontend/src/App.jsx](frontend/src/App.jsx)).
3. Those call `getHome`/`getRecommendations` in [frontend/src/lib/api.js](frontend/src/lib/api.js).
4. Requests hit FastAPI routes in [backend/app/main.py](backend/app/main.py).
5. Backend calls `AstraRepository.home()` and `AstraRepository.recommendations()` ([backend/app/repository.py](backend/app/repository.py)).
6. Repository reads rails/events tables, then fetches show docs from collection.
7. Backend sends JSON response; frontend renders rows using [frontend/src/components/RailRow.jsx](frontend/src/components/RailRow.jsx).

**If this fails:**
- Missing env/schema => 503 + error banner in UI.
- API unreachable => “Failed to fetch” style error surfaced by `parseResponse`.

### Action B: User performs semantic search and clicks a title

1. User types in search input in [SearchPanel](frontend/src/components/SearchPanel.jsx).
2. `App.jsx` waits ~320ms (debounce) then calls `searchShows(query)`.
3. Backend `GET /api/search` forwards to `repository.search(query)`.
4. Repository runs Astra vector query (`sort={"$vectorize": query}`) in `shows` collection.
5. Results are normalized to `ShowCard` and returned.
6. Frontend auto-selects first result, and click-select changes the featured card.

**If this fails:**
- Collection not created => backend catches Data API error and returns actionable response.
- Weak metadata/vector text => results may feel irrelevant, even if technically successful.

### Action C: User clicks “Watch”

1. Watch button triggers `handleWatch(show)` in [frontend/src/App.jsx](frontend/src/App.jsx).
2. Frontend posts session payload to `POST /api/session/events`.
3. Backend validates shape with `SessionEventRequest` ([backend/app/models.py](backend/app/models.py)).
4. Repository inserts event row into `user_session_events` table.
5. Frontend reloads home+recommendations, so “Continue Watching” reflects the new event.

**If this fails:**
- Session write error => UI error banner appears; state may look stale.
- Event data quality issues (bad progress values) => recommendation/continue logic can become noisy.

### External services and failure behavior

- **Astra DB Data API**
  - Core runtime dependency for reads/writes.
  - Failure effect: app mostly unusable; routes return 502/503.

- **TVMaze + TMDB (scripts only, not runtime)**
  - Used to build/refresh local seed JSON.
  - Failure effect: refresh script can degrade metadata quality or stop before writing complete output.

- **Jupyter server (admin helper route)**
  - Backend can launch/discover Jupyter and open workshop notebook.
  - Failure effect: admin action returns explicit errors for missing server/path/token mismatches.

### Authentication flow (how app knows who you are)
There is currently **no end-user authentication**. The app uses a configured default profile (`DEFAULT_PROFILE_ID`) for personalization demo behavior. This is intentional for workshop speed, but in production terms it means: no login, no access control, no user identity guarantees.

---

## 5. Technology Choices — The Toolbox

| Technology | What It Does Here | Why This One | Watch Out For |
|-----------|------------------|-------------|---------------|
| **FastAPI** | Builds backend HTTP routes quickly | Great developer speed + auto docs + simple typing model | No built-in auth policy here; must add explicitly. Cost: open-source/free. |
| **Uvicorn** | Runs the FastAPI app locally | Standard ASGI server, lightweight | Need proper process supervision in real production. Cost: free. |
| **Astra DB Serverless** | Stores rails/session data + vectorized show docs | Perfect fit for workshop goal: table + vector in one platform | Usage-based billing; schema/region/provider choices matter. |
| **astrapy** | Python client for Astra Data API | Clean SDK for both tables and collection operations | Some command differences between tables/collections can surprise users. |
| **React** | Renders interactive StreamFlix UI | Familiar, component-based, ideal for demo UX | State can get messy if features grow fast. Cost: free. |
| **Vite** | Fast frontend dev/build tooling | Extremely quick startup and iteration | Port/config mismatches can confuse users. Cost: free. |
| **Pydantic** | Validates API request/response schemas | Keeps contracts clear and structured | Validation is only as strict as you define. Cost: free. |
| **JupyterLab** | Guided ingestion/teaching experience | Ideal for workshop step-by-step visibility | Environment loading is a frequent failure point. Cost: free. |
| **Playwright** | Browser smoke tests for UI contracts | Good confidence for key UI paths | Needs stable mocks and local browser deps. Cost: free tool; CI runtime cost if automated. |
| **TVMaze API** | Source metadata/images for seed generation | Fast way to obtain real-world show catalog | External API limits/terms; not runtime-safe dependency. |
| **TMDB API (optional)** | Improves metadata completeness offline | Better creator/director/tag coverage | Requires API key and matching logic quality. Usage terms apply. |
| **Devcontainer** | Reproducible setup in Codespaces/dev containers | Reduces “works on my machine” friction for workshops | If image/deps drift, setup can still break. Codespaces minutes can cost money. |

---

## 6. Environment & Configuration

### Environment variables in plain language
Primary template: [.env.example](.env.example)

- `ASTRA_DB_API_ENDPOINT` — “Which Astra database door should we knock on?”
- `ASTRA_DB_APPLICATION_TOKEN` — “What key proves we’re allowed in?”
- `ASTRA_DB_KEYSPACE` — “Which workspace/drawer inside Astra to use?”
- `DEFAULT_PROFILE_ID` — “Which demo user persona should the app behave as by default?”
- `ASTRA_VECTOR_PROVIDER`, `ASTRA_VECTOR_MODEL` — “Which embedding/vector service profile we assume in workshop setup.”
- `BACKEND_PORT`, `FRONTEND_PORT` — local ports for API and UI.
- `CORS_ORIGINS` — which browser origins are allowed to call backend APIs.
- `VITE_API_BASE_URL` — frontend’s pointer to backend URL.
- `VITE_DEFAULT_PROFILE_ID` — frontend-side fallback profile.
- `VITE_ASTRA_PORTAL_URL`, `VITE_GITHUB_REPO_URL` — links shown in Admin dropdown.
- `NOTEBOOK_HOST`, `NOTEBOOK_PORT` — where backend expects Jupyter server.
- `TMDB_API_KEY`, `TMDB_BEARER_TOKEN` — maintainer-only keys for offline data enrichment.

### Development vs other environments
The repository is primarily configured for **local workshop development**.

There is no dedicated staging/production config folder. In practice:
- “Environment switching” is done by changing `.env` values.
- Launch path is script-driven ([scripts/start_workshop.sh](scripts/start_workshop.sh)).

### Change examples (with caution)
- If you need to change frontend port:
  - update `FRONTEND_PORT` and `CORS_ORIGINS` in `.env`
  - optionally align [frontend/vite.config.js](frontend/vite.config.js)
  - otherwise UI may load but API calls may fail due origin mismatch.

- If you need to change Astra keyspace:
  - update `ASTRA_DB_KEYSPACE`
  - rerun notebook to create schema in that keyspace
  - otherwise backend routes fail because expected tables/collection are absent.

### Secrets and service links
- Astra token connects backend/notebook to Astra DB.
- TMDB keys only needed when rebuilding local dataset.
- `.env` is ignored by git ([.gitignore](.gitignore)).

---

## 7. Lessons Learned — The War Stories

### Bugs & Fixes

#### 1) “Notebook link opens, but file says Not Found”
- **Cause (simple):** Jupyter was running from a different root directory than backend expected.
- **Fix:** backend now discovers running server metadata and computes correct relative path ([backend/app/main.py](backend/app/main.py)).
- **Avoid next time:** always standardize Jupyter launch path or keep the backend auto-detection logic tested.

#### 2) “Table validation throws unsupported command errors”
- **Cause:** using collection-style `countDocuments` against Astra tables.
- **Fix:** notebook validation switched to partition-key reads and count-from-insert payload approach.
- **Avoid next time:** treat tables and collections as similar cousins, not identical twins.

#### 3) “Frontend opens, but API calls fail”
- **Cause:** port/config drift (`5173` vs `5174`, CORS, API base URL mismatch).
- **Fix:** clear quickstart instructions and env-driven startup script.
- **Avoid next time:** use one source of truth for ports, then generate both frontend/backend config from it.

### Pitfalls & Landmines

- **Landmine: Notebook environment inheritance**
  - If Jupyter is launched from a shell without sourced `.env`, Astra vars are “invisible.”

- **Landmine: Hybrid data model coupling**
  - Changing `show_id` conventions in one place affects rails table, session events, and collection lookups.

- **Landmine: Admin notebook launcher behavior**
  - Useful for workshops, risky if app is exposed broadly without access controls.

- **Landmine: Data quality controls are mostly script-level**
  - Recommendation quality and metadata completeness depend on seed refresh quality.

### Discoveries

- Combining structured rails tables with vector search gives a very teachable story:
  - “predictable homepage rails” + “meaning-based discovery.”
- Click-to-select featured search item (instead of hover-to-select) significantly improves UX stability.
- Pre-enriched local snapshots reduce workshop chaos compared with live third-party runtime dependencies.

### Engineering Wisdom

- **Determinism beats cleverness in workshops.** If a demo must work in one hour, local snapshots and predictable seeds are your friend.
- **Teach with visible layers.** Notebook + API + UI makes architecture tangible.
- **Guard the seams.** Most real failures happen at boundaries: env vars, ports, schema assumptions, and service connectivity.
- **Design for graceful failure.** User-facing errors should be actionable (“what to check next”), not cryptic stack traces.

### If starting over
- Add explicit environment profiles (`dev`, `staging`) and shared config validation at startup.
- Add authentication/authorization boundaries for admin actions.
- Add CI workflow to run backend tests + frontend smoke automatically.

---

## 8. Quick Reference Card

### Zero-to-running local setup (assume nothing installed)

1. **Clone and enter project**
```bash
git clone <repo-url>
cd astradb_handson_tvshow
```

2. **Create env file**
```bash
cp .env.example .env
# fill ASTRA_DB_API_ENDPOINT + ASTRA_DB_APPLICATION_TOKEN (+ keyspace)
```

3. **Install backend deps + Jupyter**
```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r backend/requirements.txt jupyterlab
```

4. **Install frontend deps**
```bash
cd frontend
npm install
cd ..
```

5. **Run notebook ingestion**
```bash
source .venv/bin/activate
set -a
source .env
set +a
jupyter lab notebook/streamflix_astra_workshop.ipynb
```
Run cells top-to-bottom.

6. **Start app stack**
```bash
./scripts/start_workshop.sh
```

### Key URLs
- Frontend: `http://localhost:5174` (or your configured `FRONTEND_PORT`)
- Backend health: `http://localhost:8010/health`
- Backend docs (FastAPI): `http://localhost:8010/docs`
- Astra portal: `https://astra.datastax.com/`
- Admin Jupyter launcher endpoint: `POST http://localhost:8010/api/admin/notebook`

### Most commonly needed commands

```bash
# Start both services
./scripts/start_workshop.sh

# Start backend only
source .venv/bin/activate
set -a && source .env && set +a
python3 -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8010

# Backend tests
cd backend
python3 -m pytest -q

# Frontend tests
cd frontend
npm run test:e2e
```

### When something breaks: where to go first

1. Check [QUICKSTART.md](QUICKSTART.md) and [README.md](README.md) for known setup gotchas.
2. Verify `.env` values and schema creation in notebook.
3. Hit `/health` and `/docs` on backend to isolate frontend-vs-backend issues.
4. If notebook launcher fails, inspect guidance in [README.md](README.md) and restart backend.

If your organization has no designated owner yet, the practical owner is usually the **workshop facilitator or product owner** for this repo.

