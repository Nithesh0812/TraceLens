
from datetime import datetime
import pytest

from pydantic import ValidationError

from app.ingestion.log_reader import read_logs
from app.ingestion.schemas import LogEvent

def test_valid_log_event():
    log_data={
        "timestamp": "2026-11-15T03:43:51Z",
        "service": "jobtracker-api",
        "level": "INFO",
        "event": "http_request",
        "status_code": 200,
        "duration_ms": 5.2,
    }

    log=LogEvent.model_validate(log_data)

    assert log.service == "jobtracker-api"
    assert log.level == "INFO"
    assert log.status_code == 200
    assert log.duration_ms == 5.2
    assert isinstance(log.timestamp,datetime)

def test_reader_skips_invalid_logs(tmp_path):
    # Arrange
    log_file = tmp_path / "test.jsonl"

    log_file.write_text(
        '{"timestamp":"2026-11-15T03:43:51Z",'
        '"service":"jobtracker-api",'
        '"level":"INFO",'
        '"event":"http_request"}\n'
        '{invalid json}\n'
        '{"timestamp":"2026-11-15T03:44:00Z",'
        '"service":"jobtracker-api",'
        '"level":"ERROR",'
        '"event":"db_error"}\n',
        encoding="utf-8",
    )

    # Act
    logs = read_logs(str(log_file))

    # Assert
    assert len(logs) == 2
    assert logs[0].level == "INFO"
    assert logs[1].event == "db_error"
def test_missing_required_field():
    log_data = {
        "timestamp": "2026-11-15T03:43:51Z",
        "level": "INFO",
        "event": "http_request",
    }
    # service is missing
    with pytest.raises(ValidationError):
        LogEvent.model_validate(log_data)

@pytest.mark.parametrize(
    "field,value",
    [
        ("timestamp", "invalid-date"),
        ("level", "UNKNOWN"),
        ("duration_ms", -10),
        ("status_code", 999),
        ("service", None),
    ],
)
def test_invalid_fields(field, value):
    log_data = {
        "timestamp": "2026-11-15T03:43:51Z",
        "service": "jobtracker-api",
        "level": "INFO",
        "event": "http_request",
    }

    log_data[field] = value

    with pytest.raises(ValidationError):
        LogEvent.model_validate(log_data)