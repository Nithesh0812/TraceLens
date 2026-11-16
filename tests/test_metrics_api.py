

import httpx
import pytest

from fastapi.testclient import TestClient
from app.main import app
from app.api import metrics as metrics_api


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_metrics(monkeypatch):
    """Replace Prometheus-backed functions with test values."""

    monkeypatch.setattr(
        metrics_api, "get_request_rate", lambda: 0.15
    )
    monkeypatch.setattr(
        metrics_api, "get_error_rate", lambda: 2.5
    )
    monkeypatch.setattr(
        metrics_api, "get_average_latency", lambda: 12.3
    )


# Test 1: Health endpoint
def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


# Test 2: Successful metrics response
def test_metrics_summary_success(client, mock_metrics):
    response = client.get("/metrics/summary")

    assert response.status_code == 200
    assert response.json() == {
        "request_rate": 0.15,
        "error_rate": 2.5,
        "average_latency_ms": 12.3,
    }


# Test 3: No metrics available
def test_metrics_summary_empty(client, monkeypatch):
    monkeypatch.setattr(
        metrics_api, "get_request_rate", lambda: None
    )
    monkeypatch.setattr(
        metrics_api, "get_error_rate", lambda: None
    )
    monkeypatch.setattr(
        metrics_api, "get_average_latency", lambda: None
    )

    response = client.get("/metrics/summary")

    assert response.status_code == 200
    assert response.json() == {
        "request_rate": None,
        "error_rate": None,
        "average_latency_ms": None,
    }


# Test 4: Prometheus connection failure
def test_metrics_summary_connection_error(client, monkeypatch):
    def fail():
        raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr(
        metrics_api, "get_request_rate", fail
    )

    response = client.get("/metrics/summary")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Prometheus metrics temporarily unavailable"
    }


# Test 5: Invalid Prometheus response
def test_metrics_summary_invalid_data(client, monkeypatch):
    def fail():
        raise ValueError("Invalid Prometheus response")

    monkeypatch.setattr(
        metrics_api, "get_request_rate", fail
    )

    response = client.get("/metrics/summary")

    assert response.status_code == 503


# Test 6: Partial metrics availability
def test_metrics_summary_partial_data(client, monkeypatch):
    monkeypatch.setattr(
        metrics_api, "get_request_rate", lambda: 0.10
    )
    monkeypatch.setattr(
        metrics_api, "get_error_rate", lambda: 0.0
    )
    monkeypatch.setattr(
        metrics_api, "get_average_latency", lambda: None
    )

    response = client.get("/metrics/summary")

    assert response.status_code == 200
    assert response.json() == {
        "request_rate": 0.10,
        "error_rate": 0.0,
        "average_latency_ms": None,
    }
