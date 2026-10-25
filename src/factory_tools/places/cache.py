import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

CACHE_ENV = "PLACES_CACHE_DIR"
DEFAULT_DIR = "/tmp/places-cache"
MAX_AGE = timedelta(hours=24)


def cache_key(latitude: float, longitude: float, radius_m: int, limit: int) -> str:
    return f"{latitude:.4f}_{longitude:.4f}_{radius_m}_{limit}"


def read_cached(key: str, now: datetime | None = None) -> dict | None:
    path = _path(key)
    try:
        stored = json.loads(path.read_text())
        stored_at = datetime.fromisoformat(stored["stored_at"])
    except (OSError, ValueError, KeyError):
        return None
    if (now or datetime.now(UTC)) - stored_at > MAX_AGE:
        return None
    return {**stored["result"], "cached_at": stored["stored_at"]}


def write_cached(key: str, result: dict, now: datetime | None = None) -> None:
    path = _path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = (now or datetime.now(UTC)).isoformat(timespec="seconds")
    staging = path.with_suffix(".tmp")
    staging.write_text(json.dumps({"stored_at": stamp, "result": result}))
    staging.replace(path)


def _path(key: str) -> Path:
    return Path(os.environ.get(CACHE_ENV, DEFAULT_DIR)) / f"{key}.json"
