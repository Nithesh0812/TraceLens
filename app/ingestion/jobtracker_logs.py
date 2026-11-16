
import json
import os
from collections import deque
from pathlib import Path
from typing import Any


DEFAULT_LOG_PATH = Path(
    os.getenv(
        "JOBTRACKER_LOG_PATH",
        "logs/app.log",
    )
)


def normalize_log(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Convert JobTracker structured logs into
    the normalized TraceLens log format.
    """

    event = str(raw.get("event", "unknown_event"))
    level = str(raw.get("level", "INFO")).upper()

    details = []

    for field in (
        "method",
        "path",
        "status_code",
        "error_type",
        "duration_ms",
    ):
        value = raw.get(field)
        if value is not None:
            details.append(f"{field}={value}")

    message = str(raw.get("message") or event)

    if details:
        message += " | " + " ".join(details)

    return {
        "timestamp": raw.get("timestamp"),
        "level": level,
        "message": message,
        "service": raw.get("service"),
        "event": event,
        "request_id": raw.get("request_id"),
    }


def read_jobtracker_logs(
    log_path: str | Path | None = None,
    max_lines: int = 2000,
) -> list[dict[str, Any]]:
    """Read and normalize recent JSON log entries."""

    if max_lines <= 0:
        raise ValueError("max_lines must be positive")

    path = Path(log_path) if log_path is not None else (
        DEFAULT_LOG_PATH
    )

    if not path.is_file():
        raise FileNotFoundError(
            f"JobTracker log file not found: {path}"
        )

    normalized = []

    with path.open("r", encoding="utf-8", errors="replace") as file:
        recent_lines = deque(file, maxlen=max_lines)

    for line in recent_lines:
        if not line.strip():
            continue

        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue

        if not isinstance(raw, dict):
            continue

        normalized.append(normalize_log(raw))

    return normalized
