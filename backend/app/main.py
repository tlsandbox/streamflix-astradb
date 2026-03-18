from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import socket
import subprocess
import sys
import time

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


@app.post("/api/admin/notebook")
def open_notebook() -> dict[str, str]:
    settings = get_settings()
    notebook_url = _ensure_notebook_server(
        host=settings.notebook_host,
        port=settings.notebook_port,
        notebook_relative_path=settings.notebook_relative_path,
    )
    return {"status": "ok", "url": notebook_url}


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


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _notebook_public_host(host: str) -> str:
    if host in {"127.0.0.1", "0.0.0.0"}:
        return "localhost"
    return host


def _is_port_open(host: str, port: int) -> bool:
    target_host = "127.0.0.1" if host == "0.0.0.0" else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex((target_host, port)) == 0


def _ensure_notebook_server(*, host: str, port: int, notebook_relative_path: str) -> str:
    notebook_relative_path = notebook_relative_path.lstrip("/")
    public_host = _notebook_public_host(host)
    notebook_url = f"http://{public_host}:{port}/lab/tree/{notebook_relative_path}"
    if _is_port_open(host, port):
        return notebook_url

    root = _repo_root()
    command = [
        sys.executable,
        "-m",
        "jupyter",
        "lab",
        "--no-browser",
        "--ServerApp.token=",
        "--ServerApp.password=",
        f"--ServerApp.root_dir={root}",
        f"--ip={host}",
        f"--port={port}",
    ]
    subprocess.Popen(
        command,
        cwd=root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    deadline = time.time() + 8.0
    while time.time() < deadline:
        if _is_port_open(host, port):
            return notebook_url
        time.sleep(0.25)

    raise HTTPException(
        status_code=503,
        detail=(
            "Unable to start Jupyter server automatically. "
            "Install jupyterlab and run: set -a && source .env && set +a && jupyter lab notebook/streamflix_astra_workshop.ipynb"
        ),
    )
