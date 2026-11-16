
import json

import pytest

from app.ingestion.jobtracker_logs import (
    normalize_log,
    read_jobtracker_logs,
)


def test_normalize_error_log():
    raw = {
        "timestamp": "2026-11-16T06:26:11.712Z",
        "service": "jobtracker-api",
        "level": "ERROR",
        "event": "http_request",
        "request_id": "req-123",
        "method": "GET",
        "path": "/jobs",
        "status_code": 500,
        "duration_ms": 1200,
    }

    result = normalize_log(raw)

    assert result["level"] == "ERROR"
    assert result["request_id"] == "req-123"
    assert "http_request" in result["message"]
    assert "status_code=500" in result["message"]


def test_read_logs(tmp_path):
    log_file = tmp_path / "app.log"

    records = [
        {
            "timestamp": "2026-11-16T06:26:11Z",
            "level": "INFO",
            "event": "http_request",
        },
        {
            "timestamp": "2026-11-16T06:26:12Z",
            "level": "ERROR",
            "event": "db_unavailable",
        },
    ]

    with log_file.open("w") as file:
        for record in records:
            file.write(json.dumps(record) + "\n")

    logs = read_jobtracker_logs(log_file)

    assert len(logs) == 2
    assert logs[1]["level"] == "ERROR"
    assert logs[1]["message"] == "db_unavailable"


def test_skips_invalid_json(tmp_path):
    log_file = tmp_path / "app.log"

    log_file.write_text(
        '{"level":"ERROR","event":"failure"}\n'
        'invalid json\n'
    )

    logs = read_jobtracker_logs(log_file)

    assert len(logs) == 1


def test_max_lines(tmp_path):
    log_file = tmp_path / "app.log"

    with log_file.open("w") as file:
        for index in range(10):
            file.write(
                json.dumps({
                    "level": "ERROR",
                    "event": f"event_{index}",
                }) + "\n"
            )

    logs = read_jobtracker_logs(log_file, max_lines=3)

    assert len(logs) == 3
    assert logs[0]["message"] == "event_7"


def test_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_jobtracker_logs(
            tmp_path / "missing.log"
        )
