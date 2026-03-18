from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import uuid
from typing import Any, Iterable

from astrapy import DataAPIClient

from .config import Settings
from .models import HomeResponse, Rail, RecommendationsResponse, SearchResponse, SessionEventRequest, SessionEventResponse, ShowCard


RAIL_TITLES: OrderedDict[str, str] = OrderedDict(
    {
        "trending": "Trending Now",
        "new_release": "New Releases",
        "sci_fi": "Sci-Fi Picks",
        "drama": "Critically Acclaimed Drama",
        "binge": "Binge-Worthy Series",
    }
)


@dataclass
class AstraRepository:
    settings: Settings

    def __post_init__(self) -> None:
        self._database = None

    @property
    def configured(self) -> bool:
        return self.settings.astra_configured

    def _db(self):
        if not self.settings.astra_configured:
            raise RuntimeError("Astra DB credentials are not configured.")
        if self._database is None:
            client = DataAPIClient(self.settings.astra_db_application_token)
            self._database = client.get_database(
                self.settings.astra_db_api_endpoint,
                keyspace=self.settings.astra_db_keyspace,
            )
        return self._database

    def _shows_collection(self):
        return self._db().get_collection("shows")

    def _sessions_table(self):
        return self._db().get_table("user_session_events")

    def _rails_table(self):
        return self._db().get_table("home_rails_by_profile")

    def home(self, profile_id: str) -> HomeResponse:
        rails: list[Rail] = []

        continue_items = self._continue_watching(profile_id, limit=12)
        if continue_items:
            rails.append(Rail(rail_id="continue_watching", title="Continue Watching", items=continue_items))

        for rail_id, title in RAIL_TITLES.items():
            rows = list(self._rails_table().find({"profile_id": profile_id, "rail_id": rail_id}, limit=12))
            if not rows:
                continue
            rows_sorted = sorted(rows, key=lambda row: int(row.get("rank", 9999)))
            show_ids = [str(row["show_id"]) for row in rows_sorted if row.get("show_id")]
            cards = self._fetch_show_cards(show_ids)
            if cards:
                rails.append(Rail(rail_id=rail_id, title=title, items=cards))

        return HomeResponse(profile_id=profile_id, rails=rails)

    def search(self, query: str, limit: int = 24) -> SearchResponse:
        cursor = self._shows_collection().find(
            {},
            sort={"$vectorize": query},
            include_similarity=True,
            limit=limit,
        )
        cards = [self._doc_to_show_card(doc) for doc in cursor]
        return SearchResponse(query=query, total=len(cards), results=cards)

    def recommendations(self, profile_id: str, limit: int = 12) -> RecommendationsResponse:
        events = self._recent_events(profile_id, days=14, max_events=120)
        watched_ids: list[str] = []
        for event in events:
            show_id = str(event.get("show_id", "")).strip()
            if show_id and show_id not in watched_ids:
                watched_ids.append(show_id)
            if len(watched_ids) >= 8:
                break

        basis = "popular engaging television series"
        if watched_ids:
            watched_docs = self._fetch_show_docs(watched_ids[:4])
            basis_chunks: list[str] = []
            for doc in watched_docs:
                basis_chunks.append(str(doc.get("title", "")))
                basis_chunks.extend(doc.get("genres", []))
                basis_chunks.extend(doc.get("tags", [])[:5])
                basis_chunks.append(str(doc.get("synopsis", ""))[:180])
                basis_chunks.extend([str(name) for name in doc.get("creator_names", [])[:2]])
                basis_chunks.extend([str(name) for name in doc.get("cast_names", [])[:4]])
            basis = " ".join(chunk for chunk in basis_chunks if chunk).strip() or basis

        filter_query: dict[str, Any] = {}
        if watched_ids:
            filter_query = {"_id": {"$nin": watched_ids}}

        cursor = self._shows_collection().find(
            filter_query,
            sort={"$vectorize": basis},
            include_similarity=True,
            limit=limit,
        )
        cards = [self._doc_to_show_card(doc) for doc in cursor]
        return RecommendationsResponse(profile_id=profile_id, basis=basis, items=cards)

    def log_session_event(self, event: SessionEventRequest) -> SessionEventResponse:
        now = datetime.now(timezone.utc)
        row = {
            "profile_id": event.profile_id,
            "event_day": now.strftime("%Y-%m-%d"),
            "event_ts": int(now.timestamp() * 1000),
            "event_id": str(uuid.uuid4()),
            "show_id": event.show_id,
            "event_type": event.event_type,
            "progress_seconds": int(event.progress_seconds),
            "device_type": event.device_type,
            "locale": event.locale,
        }
        self._sessions_table().insert_one(row)
        return SessionEventResponse(status="ok", continue_watching_updated=True)

    def _continue_watching(self, profile_id: str, limit: int) -> list[ShowCard]:
        events = self._recent_events(profile_id, days=7, max_events=200)
        progress_by_show: dict[str, int] = {}

        for event in events:
            show_id = str(event.get("show_id", "")).strip()
            if not show_id or show_id in progress_by_show:
                continue
            progress = int(event.get("progress_seconds", 0) or 0)
            if progress <= 0:
                continue
            progress_by_show[show_id] = progress
            if len(progress_by_show) >= limit:
                break

        if not progress_by_show:
            return []

        return self._fetch_show_cards(list(progress_by_show.keys()), progress_by_show=progress_by_show)

    def _recent_events(self, profile_id: str, *, days: int, max_events: int) -> list[dict[str, Any]]:
        table = self._sessions_table()
        rows: list[dict[str, Any]] = []
        utc_now = datetime.now(timezone.utc)

        for offset in range(days):
            day = (utc_now - timedelta(days=offset)).strftime("%Y-%m-%d")
            day_rows = list(table.find({"profile_id": profile_id, "event_day": day}, limit=max_events))
            rows.extend(day_rows)

        rows.sort(key=lambda row: int(row.get("event_ts", 0)), reverse=True)
        return rows[:max_events]

    def _fetch_show_docs(self, show_ids: Iterable[str]) -> list[dict[str, Any]]:
        unique_ids = list(dict.fromkeys(show_ids))
        if not unique_ids:
            return []
        cursor = self._shows_collection().find({"_id": {"$in": unique_ids}}, limit=len(unique_ids))
        docs = [doc for doc in cursor if doc.get("_id")]
        return docs

    def _fetch_show_cards(self, show_ids: list[str], progress_by_show: dict[str, int] | None = None) -> list[ShowCard]:
        docs = self._fetch_show_docs(show_ids)
        doc_map = {str(doc["_id"]): doc for doc in docs}

        cards: list[ShowCard] = []
        for show_id in show_ids:
            doc = doc_map.get(show_id)
            if not doc:
                continue
            card = self._doc_to_show_card(doc)
            if progress_by_show and show_id in progress_by_show:
                card.progress_seconds = progress_by_show[show_id]
            cards.append(card)
        return cards

    @staticmethod
    def _doc_to_show_card(doc: dict[str, Any]) -> ShowCard:
        rating = doc.get("rating")
        similarity = doc.get("$similarity")
        return ShowCard(
            show_id=str(doc.get("_id", "")),
            title=str(doc.get("title", "Untitled")),
            poster_url=str(doc.get("poster_url", "")),
            synopsis=str(doc.get("synopsis", "")),
            genres=[str(genre) for genre in doc.get("genres", [])],
            year=int(doc["year"]) if doc.get("year") is not None else None,
            rating=float(rating) if rating is not None else None,
            network=str(doc["network"]) if doc.get("network") is not None else None,
            runtime=int(doc["runtime"]) if doc.get("runtime") is not None else None,
            language=str(doc["language"]) if doc.get("language") is not None else None,
            status=str(doc["status"]) if doc.get("status") is not None else None,
            premiered_date=str(doc["premiered_date"]) if doc.get("premiered_date") is not None else None,
            tags=[str(tag) for tag in (doc.get("tags") or [])],
            creator_names=[str(name) for name in (doc.get("creator_names") or [])],
            director_names=[str(name) for name in (doc.get("director_names") or [])],
            cast_names=[str(name) for name in (doc.get("cast_names") or [])],
            similarity=float(similarity) if similarity is not None else None,
        )
