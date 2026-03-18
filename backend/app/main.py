from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from astrapy.exceptions import DataAPIResponseException
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import Settings, load_settings
from .models import HomeResponse, RecommendationsResponse, SearchResponse, SessionEventRequest, SessionEventResponse
from .repository import AstraRepository

WORKSHOP_NOTEBOOK_RELATIVE_PATH = "notebook/streamflix_astra_workshop.ipynb"


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


def _run_jupyter_cmd(args: list[str], *, capture_output: bool = False) -> subprocess.CompletedProcess | None:
    candidate_prefixes = [
        [sys.executable, "-m", "jupyter"],
        ["jupyter"],
    ]
    for prefix in candidate_prefixes:
        try:
            if capture_output:
                result = subprocess.run(
                    prefix + args,
                    cwd=_repo_root(),
                    capture_output=True,
                    text=True,
                    check=False,
                )
            else:
                result = subprocess.run(
                    prefix + args,
                    cwd=_repo_root(),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            if result.returncode == 0:
                return result
        except OSError:
            continue
    return None


def _jupyter_cli_available() -> bool:
    result = _run_jupyter_cmd(["--version"])
    return bool(result and result.returncode == 0)


def _list_running_jupyter_servers() -> list[dict]:
    if not _jupyter_cli_available():
        return []
    result = _run_jupyter_cmd(["server", "list", "--json"], capture_output=True)
    if result is None:
        return []
    if result.returncode != 0:
        return []

    servers: list[dict] = []
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            servers.append(payload)
    return servers


def _discover_running_server(host: str, port: int) -> dict | None:
    host_candidates = {host, _notebook_public_host(host), "127.0.0.1", "localhost", "::1", "0.0.0.0"}
    for server in _list_running_jupyter_servers():
        if int(server.get("port", -1)) != port:
            continue
        server_host = str(server.get("hostname") or "").strip()
        if server_host in host_candidates or not server_host:
            return server
    return None


def _build_notebook_relative_path_for_server(notebook_abs_path: Path, server: dict | None) -> tuple[str, str]:
    if not server:
        return WORKSHOP_NOTEBOOK_RELATIVE_PATH, ""

    root_dir = Path(str(server.get("root_dir") or "")).expanduser().resolve()
    notebook_abs_path = notebook_abs_path.resolve()
    try:
        relative_path = notebook_abs_path.relative_to(root_dir).as_posix()
    except ValueError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Jupyter is running on the configured port but not rooted to this workshop directory. "
                "Stop the existing Jupyter on port 8888 and retry from StreamFlix Admin."
            ),
        ) from exc

    token = str(server.get("token") or "")
    return relative_path, token


def _assert_notebook_contents_resolves(*, host: str, port: int, relative_path: str, token: str) -> None:
    host_for_request = _notebook_public_host(host)
    encoded_path = quote(relative_path, safe="/")
    query = f"?{urlencode({'token': token})}" if token else ""
    api_url = f"http://{host_for_request}:{port}/api/contents/{encoded_path}{query}"
    request = Request(api_url, headers={"User-Agent": "streamflix-workshop/1.0"})
    try:
        with urlopen(request, timeout=3):  # noqa: S310
            return
    except HTTPError as exc:
        if exc.code == 404:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Jupyter server is running, but workshop notebook file is not available under its root. "
                    f"Expected notebook: {WORKSHOP_NOTEBOOK_RELATIVE_PATH}."
                ),
            ) from exc
        if exc.code in {401, 403}:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Jupyter server rejected backend access (auth/token mismatch). "
                    "Stop the existing Jupyter on port 8888 and relaunch via StreamFlix Admin."
                ),
            ) from exc
        raise HTTPException(
            status_code=503,
            detail=f"Jupyter server responded with HTTP {exc.code} while resolving workshop notebook.",
        ) from exc
    except URLError as exc:
        raise HTTPException(
            status_code=503,
            detail="Jupyter server started, but notebook API was unreachable from backend.",
        ) from exc


def _ensure_notebook_server(*, host: str, port: int) -> str:
    public_host = _notebook_public_host(host)
    notebook_file = _repo_root() / WORKSHOP_NOTEBOOK_RELATIVE_PATH
    if not notebook_file.is_file():
        raise HTTPException(
            status_code=503,
            detail=f"Workshop notebook not found at {WORKSHOP_NOTEBOOK_RELATIVE_PATH}.",
        )

    if _is_port_open(host, port):
        running_server = _discover_running_server(host, port)
        relative_path, token = _build_notebook_relative_path_for_server(notebook_file, running_server)
        _assert_notebook_contents_resolves(host=host, port=port, relative_path=relative_path, token=token)
        notebook_url = f"http://{public_host}:{port}/lab/tree/{quote(relative_path, safe='/')}"
        if token:
            notebook_url = f"{notebook_url}?{urlencode({'token': token})}"
        return notebook_url

    root = _repo_root()
    if not _jupyter_cli_available():
        raise HTTPException(
            status_code=503,
            detail=(
                "Jupyter is not available in this Python environment. "
                "Install with `python3 -m pip install jupyterlab` and retry."
            ),
        )

    command = [
        "lab",
        "--no-browser",
        "--ServerApp.token=",
        "--ServerApp.password=",
        f"--ServerApp.root_dir={root}",
        f"--ip={host}",
        f"--port={port}",
    ]

    popen_variants = [
        [sys.executable, "-m", "jupyter"] + command,
        ["jupyter"] + command,
    ]
    launched = False
    for cmd in popen_variants:
        try:
            subprocess.Popen(
                cmd,
                cwd=root,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            launched = True
            break
        except OSError:
            continue
    if not launched:
        raise HTTPException(
            status_code=503,
            detail="Unable to execute Jupyter launcher command on this system.",
        )

    deadline = time.time() + 8.0
    while time.time() < deadline:
        if _is_port_open(host, port):
            _assert_notebook_contents_resolves(
                host=host,
                port=port,
                relative_path=WORKSHOP_NOTEBOOK_RELATIVE_PATH,
                token="",
            )
            notebook_url = f"http://{public_host}:{port}/lab/tree/{WORKSHOP_NOTEBOOK_RELATIVE_PATH}"
            return notebook_url
        time.sleep(0.25)

    raise HTTPException(
        status_code=503,
        detail=(
            "Unable to start Jupyter server automatically. "
            "Install jupyterlab and run: set -a && source .env && set +a && jupyter lab notebook/streamflix_astra_workshop.ipynb"
        ),
    )
