from datetime import datetime, timezone

import httpx
import pytest

from app.ingestion.prometheus_client import (query_prometheus,query_prometheus_range,)

@pytest.fixture
def mock_prometheus_get(monkeypatch):
    def _mock(status_code=200, json_data=None, exc=None):
        def fake_get(url, params=None, **kwargs):
            if exc:
                raise exc
            return httpx.Response(
                status_code=status_code,
                json=json_data,
                request=httpx.Request("GET", url, params=params),
            )

        monkeypatch.setattr(httpx, "get", fake_get)

    return _mock


def test_successful_prometheus_query(mock_prometheus_get):
    mock_prometheus_get(
        json_data={
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [
                    {
                        "metric": {"job": "jobtracker-api"},
                        "value": [1794783220.290, "1"],
                    }
                ],
            },
        }
    )

    result = query_prometheus("up")
    assert result["resultType"] == "vector"
    assert len(result["result"]) == 1
    assert result["result"][0]["metric"]["job"] == "jobtracker-api"
    assert result["result"][0]["value"][1] == "1"


def test_empty_result(mock_prometheus_get):
    mock_prometheus_get(
        json_data={
            "status": "success",
            "data": {"resultType": "vector", "result": []},
        }
    )

    result = query_prometheus("nonexistent_metric")
    assert result == {"resultType": "vector", "result": []}


def test_http_error(mock_prometheus_get):
    mock_prometheus_get(status_code=500, json_data={"error": "Internal Server Error"})

    with pytest.raises(httpx.HTTPStatusError):
        query_prometheus("up")


def test_prometheus_query_error(mock_prometheus_get):
    mock_prometheus_get(
        json_data={
            "status": "error",
            "errorType": "bad_data",
            "error": "Invalid PromQL expression",
        }
    )

    with pytest.raises(ValueError, match="Invalid PromQL expression"):
        query_prometheus("invalid_query")


def test_connection_error(mock_prometheus_get):
    mock_prometheus_get(exc=httpx.ConnectError("Connection refused"))

    with pytest.raises(httpx.ConnectError, match="Connection refused"):
        query_prometheus("up")


def test_successful_prometheus_range_query(mock_prometheus_get):
    mock_prometheus_get(
        json_data={
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [
                    {
                        "metric": {"job": "jobtracker-api"},
                        "values": [
                            [1794783600, "1"],
                            [1794783660, "1"],
                            [1794783720, "0"],
                        ],
                    }
                ],
            },
        }
    )

    start = datetime(2026, 11, 15, 10, 0, tzinfo=timezone.utc)
    end = datetime(2026, 11, 15, 10, 5, tzinfo=timezone.utc)

    result = query_prometheus_range("up", start, end)

    assert result["resultType"] == "matrix"
    assert len(result["result"]) == 1
    assert result["result"][0]["metric"]["job"] == "jobtracker-api"
    assert len(result["result"][0]["values"]) == 3
    assert result["result"][0]["values"][2][1] == "0"


def test_empty_range_result(mock_prometheus_get):
    mock_prometheus_get(
        json_data={
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [],
            },
        }
    )

    start = datetime(2026, 11, 15, 10, 0, tzinfo=timezone.utc)
    end = datetime(2026, 11, 15, 11, 0, tzinfo=timezone.utc)

    result = query_prometheus_range(
        "nonexistent_metric", start, end
    )

    assert result == {"resultType": "matrix", "result": []}


def test_range_http_error(mock_prometheus_get):
    mock_prometheus_get(
        status_code=500,
        json_data={"error": "Internal Server Error"},
    )

    start = datetime(2026, 11, 15, 10, 0, tzinfo=timezone.utc)
    end = datetime(2026, 11, 15, 11, 0, tzinfo=timezone.utc)

    with pytest.raises(httpx.HTTPStatusError):
        query_prometheus_range("up", start, end)


def test_range_prometheus_query_error(mock_prometheus_get):
    mock_prometheus_get(
        json_data={
            "status": "error",
            "errorType": "bad_data",
            "error": "Invalid PromQL expression",
        }
    )

    start = datetime(2026, 11, 15, 10, 0, tzinfo=timezone.utc)
    end = datetime(2026, 11, 15, 11, 0, tzinfo=timezone.utc)

    with pytest.raises(ValueError, match="Invalid PromQL expression"):
        query_prometheus_range("invalid_query", start, end)


def test_range_connection_error(mock_prometheus_get):
    mock_prometheus_get(
        exc=httpx.ConnectError("Connection refused")
    )

    start = datetime(2026, 11, 15, 10, 0, tzinfo=timezone.utc)
    end = datetime(2026, 11, 15, 11, 0, tzinfo=timezone.utc)

    with pytest.raises(httpx.ConnectError, match="Connection refused"):
        query_prometheus_range("up", start, end)


def test_range_invalid_time_range():
    start = datetime(
        2026, 11, 15, 11, 0, tzinfo=timezone.utc
    )
    end = datetime(
        2026, 11, 15, 10, 0, tzinfo=timezone.utc
    )

    with pytest.raises(ValueError, match="start cannot be after end"):
        query_prometheus_range("up", start, end)


def test_range_naive_datetime():
    start = datetime(2026, 11, 15, 10, 0)
    end = datetime(
        2026, 11, 15, 11, 0, tzinfo=timezone.utc
    )

    with pytest.raises(ValueError, match="timezone-aware"):
        query_prometheus_range("up", start, end)


    start = datetime(
        2026, 11, 15, 10, 0, tzinfo=timezone.utc
    )
    end = datetime(2026, 11, 15, 11, 0)

    with pytest.raises(ValueError, match="timezone-aware"):
        query_prometheus_range("up", start, end)


# Test 13: Verify request parameters
def test_range_request_parameters(monkeypatch):
    start = datetime(
        2026, 11, 15, 10, 0, tzinfo=timezone.utc
    )
    end = datetime(
        2026, 11, 15, 11, 0, tzinfo=timezone.utc
    )

    captured = {}

    def fake_get(url, params=None, **kwargs):
        captured["url"] = url
        captured["params"] = params
        captured["timeout"] = kwargs.get("timeout")

        return httpx.Response(
            status_code=200,
            json={
                "status": "success",
                "data": {
                    "resultType": "matrix",
                    "result": [],
                },
            },
            request=httpx.Request("GET", url, params=params),
        )

    monkeypatch.setattr(httpx, "get", fake_get)

    query_prometheus_range(
        query="rate(http_requests_total[5m])",
        start=start,
        end=end,
        step="30s",
        base_url="http://localhost:9090/",
    )

    assert captured["url"] == (
        "http://localhost:9090/api/v1/query_range"
    )

    assert captured["params"] == {
        "query": "rate(http_requests_total[5m])",
        "start": start.timestamp(),
        "end": end.timestamp(),
        "step": "30s",
    }

    assert captured["timeout"] == 10.0
