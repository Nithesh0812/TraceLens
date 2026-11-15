from app.ingestion.log_filter import filter_logs
from app.ingestion.schemas import LogEvent
from datetime import datetime, timezone
import pytest

@pytest.fixture
def sample_logs():
    return [
        LogEvent(
            timestamp="2026-11-15T10:00:00Z",
            service="jobtracker-api",
            level="INFO",
            event="http_request",
            request_id="req-001",
        ),
        LogEvent(
            timestamp="2026-11-15T10:01:00Z",
            service="jobtracker-api",
            level="ERROR",
            event="db_error",
            request_id="req-002",
        ),
        LogEvent(
            timestamp="2026-11-15T10:02:00Z",
            service="jobtracker-api",
            level="ERROR",
            event="http_request",
            request_id="req-003",
        ),
    ]

def test_filter_by_level(sample_logs):
    result=filter_logs(sample_logs, level ="ERROR")

    assert len(result) == 2
    assert all(log.level == "ERROR" for log in result)

def test_filter_by_event(sample_logs):
    result = filter_logs(sample_logs, event="http_request")

    assert len(result) == 2
    assert all(log.event == "http_request" for log in result)

def test_filter_by_request_id(sample_logs):
    result = filter_logs(sample_logs, request_id="req-002")

    assert len(result) == 1
    assert all(log.request_id =="req-002" for log in result)

def test_filter_no_conditions(sample_logs):
    result = filter_logs(sample_logs)

    assert len(result) == 3

def test_filter_no_matches(sample_logs):
    result = filter_logs(sample_logs,level= "CRITICAL")

    assert len(result) == 0

def test_filter_combined(sample_logs):
    result = filter_logs(sample_logs,level="ERROR",event="db_error")

    assert len(result) == 1

    assert all(log.level== "ERROR" and log.event=="db_error" for log in result)

def test_filter_by_time_range(sample_logs):
    start = datetime(2026, 11, 15, 10, 0, tzinfo=timezone.utc)
    end = datetime(2026, 11, 15, 10, 1, tzinfo=timezone.utc)

    result = filter_logs(
        sample_logs,
        start_time=start,
        end_time=end,
    )

    assert len(result) == 2
    assert all(start <= log.timestamp <= end for log in result)

def test_filter_start_time_only(sample_logs):
    start = datetime(2026, 11, 15, 10, 1, tzinfo=timezone.utc)

    result = filter_logs(sample_logs, start_time=start)

    assert len(result) == 2
    assert all(log.timestamp >= start for log in result)

def test_filter_end_time_only(sample_logs):
    end = datetime(2026, 11, 15, 10, 1, tzinfo=timezone.utc)

    result= filter_logs(sample_logs,end_time = end)

    assert len(result) == 2
    assert all(log.timestamp <= end for log in result)

def test_filter_by_no_time_matches(sample_logs):
    start = datetime(2026, 11, 15, 11, 0, tzinfo=timezone.utc)
    end = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)

    result = filter_logs(
        sample_logs,
        start_time=start,
        end_time=end,
    )

    assert len(result) == 0

def test_filter_by_time_and_severity(sample_logs):
    start = datetime(2026, 11, 15, 10, 1, tzinfo=timezone.utc)
    end = datetime(2026, 11, 15, 10, 2, tzinfo=timezone.utc)

    result = filter_logs(
        sample_logs,
        start_time=start,
        end_time=end,
        level="ERROR",
    )

    assert len(result) == 2

    assert all(
        start <= log.timestamp <= end and log.level == "ERROR"
        for log in result
    )
