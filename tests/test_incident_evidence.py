
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.api import incidents as incidents_api
from app.detection.incident_manager import IncidentManager
from app.storage.incident_repository import IncidentRepository


def test_evidence_survives_restart(tmp_path):
    db_path = tmp_path / "evidence.db"
    repository = IncidentRepository(db_path)

    manager = IncidentManager()

    events = manager.process_metrics({
        "error_rate": 0.12,
        "average_latency_ms": 100,
    })

    incident = events[0]["incident"]

    evidence = [{
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "level": "ERROR",
        "message": "Database connection failed",
        "seconds_from_incident": -10.0,
    }]

    repository.save(incident, evidence)

    # Reopen the database, simulating a restart.
    reopened = IncidentRepository(db_path)

    saved = reopened.get_by_id(incident["id"])
    logs = reopened.list_evidence(incident["id"])

    assert saved is not None
    assert len(logs) == 1
    assert logs[0]["message"] == (
        "Database connection failed"
    )


def test_duplicate_evidence_is_not_inserted(tmp_path):
    repository = IncidentRepository(tmp_path / "test.db")
    manager = IncidentManager()

    incident = manager.process_metrics({
        "error_rate": 0.12,
    })[0]["incident"]

    evidence = [{
        "timestamp": "2026-11-16T06:00:00+00:00",
        "level": "ERROR",
        "message": "Database unavailable",
        "seconds_from_incident": -5.0,
    }]

    repository.save(incident, evidence)
    repository.save(incident, evidence)

    assert len(
        repository.list_evidence(incident["id"])
    ) == 1


def test_live_api_persists_evidence(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "live.db"
    repository = IncidentRepository(db_path)

    monkeypatch.setattr(
        incidents_api, "repository", repository
    )
    monkeypatch.setattr(
        incidents_api, "manager", IncidentManager()
    )

    monkeypatch.setattr(
        incidents_api, "get_request_rate",
        lambda: 10.0
    )
    monkeypatch.setattr(
        incidents_api, "get_error_rate",
        lambda: 12.0  # Percentage from Prometheus service
    )
    monkeypatch.setattr(
        incidents_api, "get_average_latency",
        lambda: 200.0
    )

    timestamp = (
        datetime.now(timezone.utc)
        - timedelta(minutes=1)
    ).isoformat()

    monkeypatch.setattr(
        incidents_api,
        "read_jobtracker_logs",
        lambda: [{
            "timestamp": timestamp,
            "level": "ERROR",
            "message": "Database connection failed",
        }],
    )

    client = TestClient(app)

    response = client.post(
        "/incidents/evaluate-live"
    )

    assert response.status_code == 200

    data = response.json()
    assert len(data["events"]) == 1

    incident_id = data["events"][0]["incident"]["id"]

    # Simulate a new database connection after restart.
    reopened = IncidentRepository(db_path)

    evidence = reopened.list_evidence(incident_id)

    assert len(evidence) == 1
    assert evidence[0]["message"] == (
        "Database connection failed"
    )

    # Verify the incident details API.
    details = client.get(f"/incidents/{incident_id}")

    assert details.status_code == 200

    body = details.json()
    assert body["correlated_log_count"] == 1
    assert len(body["correlated_logs"]) == 1
