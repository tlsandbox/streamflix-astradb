#!/usr/bin/env python3
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHOWS_PATH = ROOT / "data" / "tv_shows_300.json"
OUT_PATH = ROOT / "data" / "seed_profiles.json"

PROFILE_CONFIG = {
    "profile_alex": ["sci_fi", "binge", "trending", "new_release", "drama"],
    "profile_mia": ["drama", "new_release", "trending", "binge", "sci_fi"],
    "profile_liam": ["binge", "trending", "sci_fi", "drama", "new_release"],
}

RAIL_IDS = ["trending", "new_release", "sci_fi", "drama", "binge"]



def pick_for_rail(shows: list[dict], rail_id: str, profile_bias: str, n: int = 12) -> list[dict]:
    pool = [show for show in shows if rail_id in show.get("row_tags", [])]
    if profile_bias in {"sci_fi", "drama", "binge"}:
        bias_pool = [show for show in pool if profile_bias in show.get("row_tags", [])]
        if len(bias_pool) >= n:
            pool = bias_pool + [show for show in pool if show not in bias_pool]

    pool_sorted = sorted(pool, key=lambda show: (show.get("rating") or 0.0), reverse=True)
    if len(pool_sorted) < n:
        extras = [show for show in shows if show not in pool_sorted]
        pool_sorted.extend(extras)
    return pool_sorted[:n]



def main() -> None:
    random.seed(42)
    shows = json.loads(SHOWS_PATH.read_text(encoding="utf-8"))

    rails_rows: list[dict] = []
    session_rows: list[dict] = []
    now = datetime.now(timezone.utc)

    for profile_id, preferences in PROFILE_CONFIG.items():
        primary_bias = preferences[0]

        for rail_id in RAIL_IDS:
            selected = pick_for_rail(shows, rail_id, primary_bias, n=12)
            for rank, show in enumerate(selected, start=1):
                rails_rows.append(
                    {
                        "profile_id": profile_id,
                        "rail_id": rail_id,
                        "rank": rank,
                        "show_id": show["_id"],
                        "reason": f"Matched rail tag {rail_id}",
                    }
                )

        watched = random.sample(shows, k=8)
        for idx, show in enumerate(watched):
            event_time = now - timedelta(hours=idx * 5 + random.randint(1, 4))
            session_rows.append(
                {
                    "profile_id": profile_id,
                    "event_day": event_time.strftime("%Y-%m-%d"),
                    "event_ts": int(event_time.timestamp() * 1000),
                    "event_id": f"seed-{profile_id}-{idx}",
                    "show_id": show["_id"],
                    "event_type": "progress",
                    "progress_seconds": random.randint(240, 3200),
                    "device_type": random.choice(["web", "mobile", "tv"]),
                    "locale": "en-US",
                }
            )

    payload = {
        "profiles": [
            {"profile_id": "profile_alex", "display_name": "Alex"},
            {"profile_id": "profile_mia", "display_name": "Mia"},
            {"profile_id": "profile_liam", "display_name": "Liam"},
        ],
        "rails_rows": rails_rows,
        "session_rows": sorted(session_rows, key=lambda row: row["event_ts"], reverse=True),
    }

    OUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
