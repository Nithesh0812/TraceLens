
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.api import incidents as api
from app.detection.incident_manager import IncidentManager
from app.storage.incident_repository import IncidentRepository


def test_live_incident_has_log_evidence(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        api, "repository",
        IncidentRepository(tmp_path / "incidents.db")
    )
    monkeypatch.setattr(
        api, "manager", IncidentManager()
    )

    monkeypatch.setattr(
        api, "get_request_rate", lambda: 10.0
    )
    monkeypatch.setattr(
        api, "get_error_rate", lambda: 12.0
    )
    monkeypatch.setattr(
        api, "get_average_latency", lambda: 200.0
    )

    recent_time = (
        datetime.now(timezone.utc)
        - timedelta(minutes=1)
    ).isoformat()

    logs = [{
        "timestamp": recent_time,
        "level": "ERROR",
        "message": "Database connection failed",
    }]

    monkeypatch.setattr(
        api, "read_jobtracker_logs",
        lambda: logs
    )

    response = TestClient(app).post(
        "/incidents/evaluate-live"
    )

    assert response.status_code == 200

    data = response.json()
    assert data["metrics"]["error_rate"] == 0.12

    assert len(data["events"]) == 1

    event = data["events"][0]

    assert event["event"] == "created"
    assert event["correlated_log_count"] == 1
    assert (
        event["correlated_logs"][0]["message"]
        == "Database connection failed"
    )
