
from datetime import datetime, timezone, timedelta

import pytest

from app.detection.incident_detector import (
    detect_incidents,
)
from app.detection.log_correlator import (
    correlate_logs,
    correlate_incidents,
)


@pytest.fixture
def incident():
    metrics = {
        "error_rate": 0.15,
        "average_latency_ms": 200.0,
    }

    return detect_incidents(metrics)[0]


def make_log(minutes_offset, level, message):
    timestamp = (
        datetime.now(timezone.utc)
        + timedelta(minutes=minutes_offset)
    )

    return {
        "timestamp": timestamp.isoformat(),
        "level": level,
        "message": message,
    }


def test_correlates_error_logs(incident):
    logs = [
        make_log(-2, "ERROR", "Database failure"),
        make_log(-1, "WARNING", "Slow query"),
    ]

    result = correlate_logs(incident, logs)

    assert result["correlated_log_count"] == 2


def test_excludes_info_logs(incident):
    logs = [
        make_log(-1, "INFO", "Request completed"),
        make_log(-1, "ERROR", "Connection failed"),
    ]

    result = correlate_logs(incident, logs)

    assert result["correlated_log_count"] == 1
    assert result["correlated_logs"][0]["level"] == "ERROR"


def test_excludes_old_logs(incident):
    logs = [
        make_log(-15, "ERROR", "Old error"),
    ]

    result = correlate_logs(incident, logs)

    assert result["correlated_log_count"] == 0


def test_excludes_future_logs(incident):
    logs = [
        make_log(10, "ERROR", "Future error"),
    ]

    result = correlate_logs(incident, logs)

    assert result["correlated_log_count"] == 0


def test_prioritizes_error_logs(incident):
    logs = [
        make_log(-1, "WARNING", "Warning"),
        make_log(-2, "ERROR", "Failure"),
    ]

    result = correlate_logs(incident, logs)

    assert result["correlated_logs"][0]["level"] == "ERROR"


def test_limits_correlated_logs(incident):
    logs = [
        make_log(-1, "ERROR", f"Failure {i}")
        for i in range(50)
    ]

    result = correlate_logs(
        incident, logs, max_logs=10
    )

    assert result["correlated_log_count"] == 10


def test_handles_invalid_timestamp(incident):
    logs = [
        {
            "timestamp": "invalid",
            "level": "ERROR",
            "message": "Bad timestamp",
        }
    ]

    result = correlate_logs(incident, logs)

    assert result["correlated_log_count"] == 0


def test_empty_logs(incident):
    result = correlate_logs(incident, [])

    assert result["correlated_logs"] == []
    assert result["correlated_log_count"] == 0


def test_multiple_incidents():
    incidents = detect_incidents({
        "error_rate": 0.15,
        "average_latency_ms": 1500,
    })

    logs = [
        make_log(-1, "ERROR", "Request failed"),
    ]

    results = correlate_incidents(incidents, logs)

    assert len(results) == 2
    assert all(
        result["correlated_log_count"] == 1
        for result in results
    )


def test_rejects_invalid_window(incident):
    with pytest.raises(ValueError):
        correlate_logs(
            incident, [], lookback_minutes=-1
        )


def test_rejects_naive_timestamp(incident):
    logs = [{
        "timestamp": "2026-11-15T10:00:00",
        "level": "ERROR",
        "message": "Missing timezone",
    }]

    result = correlate_logs(incident, logs)

    assert result["correlated_log_count"] == 0
