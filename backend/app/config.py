from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    astra_db_api_endpoint: str
    astra_db_application_token: str
    astra_db_keyspace: str
    default_profile_id: str
    cors_origins: str
    vector_provider: str
    vector_model: str
    notebook_host: str
    notebook_port: int

    @property
    def astra_configured(self) -> bool:
        return bool(self.astra_db_api_endpoint and self.astra_db_application_token)


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        return int(raw)
    except ValueError:
        return default


def load_settings() -> Settings:
    return Settings(
        astra_db_api_endpoint=os.getenv("ASTRA_DB_API_ENDPOINT", "").strip(),
        astra_db_application_token=os.getenv("ASTRA_DB_APPLICATION_TOKEN", "").strip(),
        astra_db_keyspace=os.getenv("ASTRA_DB_KEYSPACE", "default_keyspace").strip(),
        default_profile_id=os.getenv("DEFAULT_PROFILE_ID", "profile_alex").strip(),
        cors_origins=os.getenv("CORS_ORIGINS", "http://localhost:5174,http://127.0.0.1:5174").strip(),
        vector_provider=os.getenv("ASTRA_VECTOR_PROVIDER", "nvidia").strip(),
        vector_model=os.getenv("ASTRA_VECTOR_MODEL", "NV-Embed-QA").strip(),
        notebook_host=os.getenv("NOTEBOOK_HOST", "127.0.0.1").strip(),
        notebook_port=_int_env("NOTEBOOK_PORT", 8888),
    )
