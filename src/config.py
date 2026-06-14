import os
from dataclasses import dataclass


def _read_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _read_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = int(raw)
    if value < 1:
        raise ValueError(f"{name} must be greater than zero")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    environment: str
    log_level: str
    workflow_db_path: str
    api_key: str | None
    max_request_bytes: int
    docs_enabled: bool

    @classmethod
    def from_env(cls) -> "Settings":
        environment = os.getenv("APP_ENV", "development").strip().lower()
        api_key = os.getenv("COMPLIANCE_API_KEY") or None
        if environment == "production" and not api_key:
            raise ValueError("COMPLIANCE_API_KEY is required when APP_ENV=production")
        return cls(
            environment=environment,
            log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
            workflow_db_path=os.getenv(
                "WORKFLOW_DB_PATH",
                ".data/workflows.db",
            ),
            api_key=api_key,
            max_request_bytes=_read_int("MAX_REQUEST_BYTES", 1_048_576),
            docs_enabled=_read_bool(
                "DOCS_ENABLED",
                environment != "production",
            ),
        )
