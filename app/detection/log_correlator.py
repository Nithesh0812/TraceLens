
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app.detection.incident_detector import Incident


def parse_timestamp(value: Any) -> Optional[datetime]:
    """Parse a timezone-aware ISO 8601 timestamp."""
    if not isinstance(value, str):
        return None

    try:
        timestamp = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        if timestamp.tzinfo is None:
            return None

        return timestamp.astimezone(timezone.utc)
    except ValueError:
        return None


def correlate_logs(
    incident: Incident,
    logs: list[dict[str, Any]],
    lookback_minutes: int = 5,
    lookahead_minutes: int = 1,
    max_logs: int = 20,
) -> dict[str, Any]:
    """
    Associate warning/error logs with an incident
    using a configurable time window.

    Does not establish root cause.
    """

    if lookback_minutes < 0 or lookahead_minutes < 0:
        raise ValueError("Time windows cannot be negative")

    if max_logs < 0:
        raise ValueError("max_logs cannot be negative")

    incident_time = parse_timestamp(incident.detected_at)

    if incident_time is None:
        raise ValueError("Invalid incident timestamp")

    window_start = incident_time - timedelta(
        minutes=lookback_minutes
    )
    window_end = incident_time + timedelta(
        minutes=lookahead_minutes
    )

    matching_logs = []

    for log in logs:
        if not isinstance(log, dict):
            continue

        log_time = parse_timestamp(log.get("timestamp"))

        if log_time is None:
            continue

        level = str(log.get("level", "")).upper()

        if level not in ("ERROR", "CRITICAL", "WARNING", "WARN"):
            continue

        if not window_start <= log_time <= window_end:
            continue

        message = log.get("message", "")

        if not isinstance(message, str):
            continue

        matching_logs.append({
            "timestamp": log_time.isoformat(),
            "level": level,
            "message": message,
            "seconds_from_incident": round(
                (log_time - incident_time).total_seconds(), 2
            ),
        })

    priority = {
        "CRITICAL": 0,
        "ERROR": 1,
        "WARNING": 2,
        "WARN": 2,
    }

    matching_logs.sort(
        key=lambda log: (
            priority[log["level"]],
            abs(log["seconds_from_incident"]),
        )
    )

    evidence = matching_logs[:max_logs]

    result = incident.to_dict()
    result["correlated_logs"] = evidence
    result["correlated_log_count"] = len(evidence)

    return result


def correlate_incidents(
    incidents: list[Incident],
    logs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Correlate a collection of incidents with logs."""

    return [
        correlate_logs(incident, logs)
        for incident in incidents
    ]
