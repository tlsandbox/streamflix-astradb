from __future__ import annotations

from functools import lru_cache

from astrapy.exceptions import DataAPIResponseException
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import Settings, load_settings
from .models import HomeResponse, RecommendationsResponse, SearchResponse, SessionEventRequest, SessionEventResponse
from .repository import AstraRepository


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


@lru_cache(maxsize=1)
def get_repository() -> AstraRepository:
    return AstraRepository(get_settings())


app = FastAPI(title="StreamFlix Workshop API", version="0.1.0")

settings = get_settings()
origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.exception_handler(DataAPIResponseException)
def handle_data_api_error(_, exc: DataAPIResponseException) -> JSONResponse:
    message = str(exc)
    if "COLLECTION_NOT_EXIST" in message:
        return JSONResponse(
            status_code=503,
            content={
                "detail": (
                    "Astra schema not found (shows/user_session_events/home_rails_by_profile). "
                    "Run notebook/streamflix_astra_workshop.ipynb top-to-bottom to create and seed data."
                )
            },
        )
    return JSONResponse(status_code=502, content={"detail": f"Astra Data API error: {message}"})


@app.get("/health")
def health(repo: AstraRepository = Depends(get_repository)) -> dict[str, object]:
    return {
        "status": "ok",
        "astra_configured": repo.configured,
        "keyspace": get_settings().astra_db_keyspace,
    }


@app.get("/api/home", response_model=HomeResponse)
def get_home(
    profile_id: str = Query(default=get_settings().default_profile_id),
    repo: AstraRepository = Depends(get_repository),
) -> HomeResponse:
    _ensure_configured(repo)
    return repo.home(profile_id)


@app.get("/api/search", response_model=SearchResponse)
def get_search(
    q: str = Query(min_length=2),
    repo: AstraRepository = Depends(get_repository),
) -> SearchResponse:
    _ensure_configured(repo)
    return repo.search(q)


@app.get("/api/recommendations", response_model=RecommendationsResponse)
def get_recommendations(
    profile_id: str = Query(default=get_settings().default_profile_id),
    repo: AstraRepository = Depends(get_repository),
) -> RecommendationsResponse:
    _ensure_configured(repo)
    return repo.recommendations(profile_id)


@app.post("/api/session/events", response_model=SessionEventResponse)
def post_session_event(
    payload: SessionEventRequest,
    repo: AstraRepository = Depends(get_repository),
) -> SessionEventResponse:
    _ensure_configured(repo)
    return repo.log_session_event(payload)



def _ensure_configured(repo: AstraRepository) -> None:
    if not repo.configured:
        raise HTTPException(
            status_code=503,
            detail="Astra DB environment variables are missing. Set ASTRA_DB_API_ENDPOINT and ASTRA_DB_APPLICATION_TOKEN.",
        )
