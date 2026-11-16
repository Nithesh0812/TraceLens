
from fastapi.testclient import TestClient

from app.main import app
from app.api import incidents as incidents_api
from app.detection.incident_manager import IncidentManager
from app.storage.incident_repository import IncidentRepository


def test_incident_api_lifecycle(tmp_path, monkeypatch):
    database = tmp_path / "incidents.db"
    repository = IncidentRepository(database)
    manager = IncidentManager()

    monkeypatch.setattr(incidents_api, "repository", repository)
    monkeypatch.setattr(incidents_api, "manager", manager)

    client = TestClient(app)

    # 1. Trigger a critical incident
    response = client.post(
        "/incidents/evaluate",
        json={
            "request_rate": 10,
            "error_rate": 0.15,
            "average_latency_ms": 200,
        },
    )

    assert response.status_code == 200

    event = response.json()["events"][0]
    assert event["event"] == "created"
    assert event["incident"]["severity"] == "critical"

    incident_id = event["incident"]["id"]

    # 2. Check active incidents
    response = client.get("/incidents/active")
    assert response.status_code == 200
    assert len(response.json()["incidents"]) == 1

    # 3. Verify deduplication
    response = client.post(
        "/incidents/evaluate",
        json={"error_rate": 0.16},
    )
    assert response.json()["events"][0]["event"] == "updated"

    # 4. Resolve the incident
    response = client.post(
        "/incidents/evaluate",
        json={"error_rate": 0.01},
    )
    assert response.json()["events"][0]["event"] == "resolved"

    # 5. Check history
    response = client.get(f"/incidents/{incident_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "resolved"

    # 6. Simulate restart
    restored_manager = IncidentManager()
    repository.load_manager_state(restored_manager)

    assert restored_manager.get_active_incidents() == []

    # 7. Verify history survives
    assert repository.get_by_id(incident_id) is not None

    # 8. A new failure gets a new ID
    response = client.post(
        "/incidents/evaluate",
        json={"error_rate": 0.15},
    )

    new_id = response.json()["events"][0]["incident"]["id"]
    assert new_id != incident_id


def test_invalid_metrics(tmp_path, monkeypatch):
    repository = IncidentRepository(tmp_path / "test.db")

    monkeypatch.setattr(incidents_api, "repository", repository)
    monkeypatch.setattr(
        incidents_api, "manager", IncidentManager()
    )

    client = TestClient(app)

    response = client.post(
        "/incidents/evaluate",
        json={"error_rate": 1.5},
    )

    assert response.status_code == 422


def test_unknown_incident(tmp_path, monkeypatch):
    repository = IncidentRepository(tmp_path / "test.db")
    monkeypatch.setattr(incidents_api, "repository", repository)

    client = TestClient(app)
    response = client.get("/incidents/nonexistent")

    assert response.status_code == 404
