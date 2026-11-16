from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_incidents_response_structure():
    response = client.get("/incidents")

    assert response.status_code == 200

    data = response.json()

    assert "incidents" in data
    assert "total" in data
    assert isinstance(data["incidents"], list)
    assert isinstance(data["total"], int)


def test_incidents_pagination():
    response = client.get(
        "/incidents?limit=5&offset=0"
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data["incidents"]) <= 5


def test_invalid_pagination():
    response = client.get(
        "/incidents?limit=-1"
    )

    assert response.status_code == 422