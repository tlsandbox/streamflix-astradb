from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app, get_repository
from app.models import HomeResponse, Rail, RecommendationsResponse, SearchResponse, SessionEventRequest, SessionEventResponse, ShowCard


class FakeRepository:
    configured = True

    def home(self, profile_id: str) -> HomeResponse:
        return HomeResponse(
            profile_id=profile_id,
            rails=[
                Rail(
                    rail_id="trending",
                    title="Trending Now",
                    items=[
                        ShowCard(
                            show_id="show_1",
                            title="Example Show",
                            poster_url="https://example.com/poster.jpg",
                            synopsis="Demo synopsis",
                            genres=["Drama"],
                            year=2023,
                            rating=8.5,
                            network="CBS",
                            runtime=45,
                            language="English",
                            status="Running",
                            premiered_date="2023-01-02",
                            tags=["drama", "trending"],
                            creator_names=["Jane Creator"],
                            director_names=[],
                            cast_names=["Actor One", "Actor Two"],
                        )
                    ],
                )
            ],
        )

    def search(self, query: str) -> SearchResponse:
        return SearchResponse(query=query, total=1, results=self.home("x").rails[0].items)

    def recommendations(self, profile_id: str) -> RecommendationsResponse:
        return RecommendationsResponse(profile_id=profile_id, basis="demo", items=self.home(profile_id).rails[0].items)

    def log_session_event(self, event: SessionEventRequest) -> SessionEventResponse:
        return SessionEventResponse(status="ok", continue_watching_updated=True)


app.dependency_overrides[get_repository] = lambda: FakeRepository()
client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"


def test_home_contract() -> None:
    response = client.get("/api/home", params={"profile_id": "profile_alex"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["profile_id"] == "profile_alex"
    assert payload["rails"][0]["items"][0]["show_id"] == "show_1"


def test_search_contract() -> None:
    response = client.get("/api/search", params={"q": "space thriller"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "space thriller"
    assert payload["total"] == 1
    assert payload["results"][0]["creator_names"] == ["Jane Creator"]


def test_recommendations_contract() -> None:
    response = client.get("/api/recommendations", params={"profile_id": "profile_mia"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["profile_id"] == "profile_mia"
    assert payload["basis"] == "demo"


def test_session_event_contract() -> None:
    response = client.post(
        "/api/session/events",
        json={
            "profile_id": "profile_mia",
            "show_id": "show_99",
            "event_type": "progress",
            "progress_seconds": 240,
            "device_type": "web",
            "locale": "en-US",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload == {"status": "ok", "continue_watching_updated": True}


def test_showcard_optional_metadata_defaults() -> None:
    # Backward compatibility: optional metadata can be omitted.
    card = ShowCard(
        show_id="show_x",
        title="Legacy Shape",
        poster_url="https://example.com/legacy.jpg",
        synopsis="Legacy synopsis",
        genres=["Drama"],
    )
    assert card.creator_names == []
    assert card.director_names == []
    assert card.cast_names == []
    assert card.tags == []


def test_showcard_optional_metadata_serialization() -> None:
    card = ShowCard(
        show_id="show_minimal",
        title="Minimal Card",
        poster_url="https://example.com/min.jpg",
        synopsis="Minimal payload",
        genres=[],
    )
    dumped = card.model_dump()
    assert dumped["network"] is None
    assert dumped["runtime"] is None
    assert dumped["premiered_date"] is None
    assert dumped["creator_names"] == []
