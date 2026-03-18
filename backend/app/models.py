from __future__ import annotations

from pydantic import BaseModel, Field


class ShowCard(BaseModel):
    show_id: str
    title: str
    poster_url: str
    synopsis: str
    genres: list[str] = Field(default_factory=list)
    year: int | None = None
    rating: float | None = None
    network: str | None = None
    runtime: int | None = None
    language: str | None = None
    status: str | None = None
    premiered_date: str | None = None
    tags: list[str] = Field(default_factory=list)
    creator_names: list[str] = Field(default_factory=list)
    director_names: list[str] = Field(default_factory=list)
    cast_names: list[str] = Field(default_factory=list)
    progress_seconds: int | None = None
    similarity: float | None = None


class Rail(BaseModel):
    rail_id: str
    title: str
    items: list[ShowCard]


class HomeResponse(BaseModel):
    profile_id: str
    rails: list[Rail]


class SearchResponse(BaseModel):
    query: str
    total: int
    results: list[ShowCard]


class RecommendationsResponse(BaseModel):
    profile_id: str
    basis: str
    items: list[ShowCard]


class SessionEventRequest(BaseModel):
    profile_id: str
    show_id: str
    event_type: str = "progress"
    progress_seconds: int = 0
    device_type: str = "web"
    locale: str = "en-US"


class SessionEventResponse(BaseModel):
    status: str
    continue_watching_updated: bool
