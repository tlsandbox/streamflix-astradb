# 60-Minute Workshop Runbook

## 0-15 min: Provision Astra and Credentials

1. Open [Astra Portal](https://www.datastax.com/products/datastax-astra-db).
2. Create Astra DB Serverless database.
3. Recommended region for this lab: AWS `us-east-2` (Astra-hosted NVIDIA vectorize compatibility).
4. From the database page, copy:
   - Data API endpoint
   - Application token
5. Create local `.env` from `.env.example` and fill credentials.

## 15-35 min: Notebook Data Loading

1. Launch Jupyter from a shell that has loaded `.env`:

```bash
set -a
source .env
set +a
jupyter lab notebook/streamflix_astra_workshop.ipynb
```

2. Open `notebook/streamflix_astra_workshop.ipynb`.
3. Run cells in order:
   - Connect to Astra Data API
   - Create `shows` collection (vectorized)
   - Create `user_session_events` and `home_rails_by_profile` tables
   - Insert `data/tv_shows_300.json`
   - Insert `data/seed_profiles.json`
   - Run validation counts + semantic query
4. Confirm output has non-zero counts for collection and both tables.

## 35-55 min: Run App + Explore NoSQL + Vector

1. Start stack:

```bash
./scripts/start_workshop.sh
```

2. Open frontend (`5174`) and verify:
   - Home rails render
   - Semantic search returns relevant shows
   - Clicking a card writes a session event
   - Continue Watching rail updates after interaction

3. Highlight query patterns:
   - Rails table reads by `(profile_id, rail_id)`
   - Session table reads by `(profile_id, event_day)`
   - Vector query over show synopsis/title via `$vectorize`

## 55-60 min: Recap and Q&A

- Why collections + tables together are useful
- How vector retrieval complements denormalized tables
- Suggested extensions:
  - Add a new rail type
  - Hybrid lexical + vector search
  - Multi-profile A/B personalization
