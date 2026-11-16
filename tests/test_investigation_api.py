
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api import incidents as api
from app.detection.incident_manager import IncidentManager
from app.storage.incident_repository import IncidentRepository
from app.investigation.llm_client import (
    InvestigationReport,
    LLMInvestigationError,
)


@pytest.fixture
def setup_api(tmp_path, monkeypatch):
    repository = IncidentRepository(
        tmp_path / "investigation.db"
    )

    monkeypatch.setattr(api, "repository", repository)

    manager = IncidentManager()
    monkeypatch.setattr(api, "manager", manager)

    incident = manager.process_metrics({
        "error_rate": 0.12,
        "average_latency_ms": 200,
    })[0]["incident"]

    repository.save(incident)

    return TestClient(app), repository, incident


def add_evidence(repository, incident):
    repository.save(incident, [{
        "timestamp": incident["created_at"],
        "level": "ERROR",
        "message": "Database connection failed",
        "seconds_from_incident": 0.0,
    }])

    return repository.list_evidence(incident["id"])[0]["id"]


def test_investigation_success(setup_api, monkeypatch):
    client, repository, incident = setup_api

    evidence_id = add_evidence(repository, incident)

    def mock_investigate(self, context):
        assert context["incident"]["id"] == incident["id"]

        return InvestigationReport(
            summary="Elevated HTTP errors detected.",
            possible_cause="Database connectivity issue",
            confidence="high",
            evidence_ids=[evidence_id],
            next_steps=["Inspect database connectivity"],
            insufficient_evidence=False,
        )

    monkeypatch.setattr(
        api.LLMInvestigator,
        "investigate",
        mock_investigate,
    )

    response = client.post(
        f"/incidents/{incident['id']}/investigate"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["report"]["confidence"] == "medium"
    assert data["report"]["evidence_ids"] == [evidence_id]
    assert data["citation_ids_valid"] is True
    assert data["requires_human_review"] is True


def test_missing_incident(setup_api):
    client, _, _ = setup_api

    response = client.post(
        "/incidents/nonexistent/investigate"
    )

    assert response.status_code == 404


def test_no_evidence_abstains(setup_api, monkeypatch):
    client, _, incident = setup_api

    def should_not_call_provider(self, context):
        assert context["evidence"] == []
        return InvestigationReport(
            summary="No correlated logs available.",
            possible_cause=None,
            confidence="low",
            evidence_ids=[],
            next_steps=["Inspect application logs"],
            insufficient_evidence=True,
        )

    monkeypatch.setattr(
        api.LLMInvestigator,
        "investigate",
        should_not_call_provider,
    )

    response = client.post(
        f"/incidents/{incident['id']}/investigate"
    )

    assert response.status_code == 200
    assert response.json()["report"]["insufficient_evidence"]
    assert response.json()["report"]["possible_cause"] is None


def test_llm_failure(setup_api, monkeypatch):
    client, repository, incident = setup_api

    add_evidence(repository, incident)

    def fail(self, context):
        raise LLMInvestigationError("Provider unavailable")

    monkeypatch.setattr(
        api.LLMInvestigator,
        "investigate",
        fail,
    )

    response = client.post(
        f"/incidents/{incident['id']}/investigate"
    )

    assert response.status_code == 502


def test_llm_not_configured(setup_api, monkeypatch):
    client, repository, incident = setup_api

    add_evidence(repository, incident)

    def fail(self, context):
        raise LLMInvestigationError(
            "LLM API key or model is not configured"
        )

    monkeypatch.setattr(
        api.LLMInvestigator,
        "investigate",
        fail,
    )

    response = client.post(
        f"/incidents/{incident['id']}/investigate"
    )

    assert response.status_code == 503


def test_invalid_citation_rejected(setup_api, monkeypatch):
    client, repository, incident = setup_api

    add_evidence(repository, incident)

    def invalid_report(self, context):
        return InvestigationReport(
            summary="Possible database issue",
            possible_cause="Database connection failure",
            confidence="medium",
            evidence_ids=[999999],
            next_steps=["Inspect database"],
            insufficient_evidence=False,
        )

    monkeypatch.setattr(
        api.LLMInvestigator,
        "investigate",
        invalid_report,
    )

    response = client.post(
        f"/incidents/{incident['id']}/investigate"
    )

    assert response.status_code == 502
