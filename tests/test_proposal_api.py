
import pytest

from fastapi.testclient import TestClient

from app.main import app
from app.api import incidents as api
from app.detection.incident_manager import IncidentManager
from app.storage.incident_repository import IncidentRepository

from app.investigation.llm_client import InvestigationReport
from app.investigation.evidence_verifier import VerificationResult

from app.remediation.schemas import FixProposal
from app.remediation.proposal_generator import FixProposalError


@pytest.fixture
def setup_api(tmp_path, monkeypatch):
    repository = IncidentRepository(
        tmp_path / "proposal_api.db"
    )

    monkeypatch.setattr(api, "repository", repository)

    manager = IncidentManager()
    monkeypatch.setattr(api, "manager", manager)

    incident = manager.process_metrics({
        "error_rate": 0.12,
        "average_latency_ms": 200,
    })[0]["incident"]

    repository.save(incident)

    evidence = [{
        "timestamp": incident["created_at"],
        "level": "ERROR",
        "message": "Database connection failed",
        "seconds_from_incident": 0.0,
    }]

    repository.save(incident, evidence)

    evidence_id = repository.list_evidence(
        incident["id"]
    )[0]["id"]

    return TestClient(app), repository, incident, evidence_id


def save_investigation(
    repository,
    incident_id,
    evidence_id,
    insufficient=False,
):
    report = InvestigationReport(
        summary="Elevated HTTP errors detected.",
        possible_cause=(
            None if insufficient
            else "Database connectivity may be involved."
        ),
        confidence="low" if insufficient else "medium",
        evidence_ids=[] if insufficient else [evidence_id],
        next_steps=["Inspect database connections"],
        insufficient_evidence=insufficient,
    )

    investigation = VerificationResult(
        report=report,
        citation_ids_valid=True,
        verified_evidence_ids=(
            [] if insufficient else [evidence_id]
        ),
        warnings=[],
        requires_human_review=True,
    )

    repository.save_investigation(
        incident_id,
        investigation.model_dump(mode="json"),
    )


def mock_proposal(self, investigation, context):
    evidence_id = investigation.verified_evidence_ids[0]

    return FixProposal(
        title="Investigate database connectivity",
        description="Review database connection failures.",
        rationale="Connection errors may contribute to failures.",
        confidence="high",
        risk_level="medium",
        evidence_ids=[evidence_id],
        proposed_steps=[
            "Inspect connection pool utilization"
        ],
        validation_steps=[
            "Confirm HTTP error rates return to baseline"
        ],
        rollback_steps=[
            "Restore previous configuration if modified"
        ],
    )


def test_proposal_success(setup_api, monkeypatch):
    client, repository, incident, evidence_id = setup_api

    save_investigation(
        repository,
        incident["id"],
        evidence_id,
    )

    monkeypatch.setattr(
        api.FixProposalGenerator,
        "generate",
        mock_proposal,
    )

    response = client.post(
        f"/incidents/{incident['id']}/propose-fix"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "proposed"
    assert data["proposal"] is not None
    assert data["proposal"]["confidence"] == "medium"
    assert data["requires_human_review"] is True


def test_missing_incident(setup_api):
    client, _, _, _ = setup_api

    response = client.post(
        "/incidents/nonexistent/propose-fix"
    )

    assert response.status_code == 404


def test_investigation_required(setup_api):
    client, _, incident, _ = setup_api

    response = client.post(
        f"/incidents/{incident['id']}/propose-fix"
    )

    assert response.status_code == 409


def test_insufficient_evidence_abstains(
    setup_api,
    monkeypatch,
):
    client, repository, incident, evidence_id = setup_api

    save_investigation(
        repository,
        incident["id"],
        evidence_id,
        insufficient=True,
    )

    def should_not_generate(self, investigation, context):
        raise AssertionError("LLM should not be called")

    monkeypatch.setattr(
        api.FixProposalGenerator,
        "generate",
        should_not_generate,
    )

    response = client.post(
        f"/incidents/{incident['id']}/propose-fix"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "needs_more_evidence"
    assert response.json()["proposal"] is None


def test_provider_failure(setup_api, monkeypatch):
    client, repository, incident, evidence_id = setup_api

    save_investigation(
        repository,
        incident["id"],
        evidence_id,
    )

    def fail(self, investigation, context):
        raise FixProposalError("Provider unavailable")

    monkeypatch.setattr(
        api.FixProposalGenerator,
        "generate",
        fail,
    )

    response = client.post(
        f"/incidents/{incident['id']}/propose-fix"
    )

    assert response.status_code == 502


def test_invalid_saved_citation(
    setup_api,
    monkeypatch,
):
    client, repository, incident, evidence_id = setup_api

    save_investigation(
        repository,
        incident["id"],
        evidence_id + 999,
    )

    def should_not_generate(self, investigation, context):
        raise AssertionError("LLM should not be called")

    monkeypatch.setattr(
        api.FixProposalGenerator,
        "generate",
        should_not_generate,
    )

    response = client.post(
        f"/incidents/{incident['id']}/propose-fix"
    )

    assert response.status_code == 409


def test_unsafe_proposal_rejected(setup_api, monkeypatch):
    client, repository, incident, evidence_id = setup_api

    save_investigation(
        repository,
        incident["id"],
        evidence_id,
    )

    def unsafe_generate(self, investigation, context):
        proposal = mock_proposal(self, investigation, context)

        return proposal.model_copy(
            update={
                "proposed_steps": [
                    "Disable authentication temporarily"
                ]
            }
        )

    monkeypatch.setattr(
        api.FixProposalGenerator,
        "generate",
        unsafe_generate,
    )

    response = client.post(
        f"/incidents/{incident['id']}/propose-fix"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "needs_more_evidence"
    assert response.json()["proposal"] is None
