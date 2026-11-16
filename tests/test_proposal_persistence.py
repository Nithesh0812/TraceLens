
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api import incidents as api
from app.detection.incident_manager import IncidentManager
from app.storage.incident_repository import IncidentRepository
from app.investigation.llm_client import InvestigationReport
from app.investigation.evidence_verifier import VerificationResult
from app.remediation.schemas import FixProposal


@pytest.fixture
def setup_api(tmp_path, monkeypatch):
    db_path = tmp_path / "proposal_persistence.db"
    repository = IncidentRepository(db_path)

    monkeypatch.setattr(api, "repository", repository)
    monkeypatch.setattr(api, "manager", IncidentManager())

    incident = api.manager.process_metrics({
        "error_rate": 0.12,
        "average_latency_ms": 200,
    })[0]["incident"]

    repository.save(incident)

    repository.save(incident, [{
        "timestamp": incident["created_at"],
        "level": "ERROR",
        "message": "Database connection failed",
        "seconds_from_incident": 0.0,
    }])

    evidence_id = repository.list_evidence(
        incident["id"]
    )[0]["id"]

    investigation = VerificationResult(
        report=InvestigationReport(
            summary="High HTTP error rate",
            possible_cause="Database connectivity may be involved.",
            confidence="medium",
            evidence_ids=[evidence_id],
            next_steps=["Inspect database connections"],
            insufficient_evidence=False,
        ),
        citation_ids_valid=True,
        verified_evidence_ids=[evidence_id],
        warnings=[],
        requires_human_review=True,
    )

    repository.save_investigation(
        incident["id"],
        investigation.model_dump(mode="json"),
    )

    return (
        TestClient(app),
        repository,
        db_path,
        incident["id"],
        evidence_id,
    )


def mock_generate(self, investigation, context):
    evidence_id = investigation.verified_evidence_ids[0]

    return FixProposal(
        title="Investigate database connections",
        description="Review failed database connections.",
        rationale="Database errors may contribute to HTTP failures.",
        confidence="medium",
        risk_level="low",
        evidence_ids=[evidence_id],
        proposed_steps=["Inspect connection pool metrics"],
        validation_steps=["Verify HTTP error rate recovers"],
        rollback_steps=["Restore previous settings if changed"],
    )


def test_proposal_saved(setup_api, monkeypatch):
    client, repository, _, incident_id, _ = setup_api

    monkeypatch.setattr(
        api.FixProposalGenerator,
        "generate",
        mock_generate,
    )

    response = client.post(
        f"/incidents/{incident_id}/propose-fix"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "proposed"

    saved = repository.get_fix_proposal(incident_id)

    assert saved is not None
    assert saved == response.json()


def test_proposal_retrieval(setup_api, monkeypatch):
    client, _, _, incident_id, _ = setup_api

    monkeypatch.setattr(
        api.FixProposalGenerator,
        "generate",
        mock_generate,
    )

    post_response = client.post(
        f"/incidents/{incident_id}/propose-fix"
    )

    get_response = client.get(
        f"/incidents/{incident_id}/fix-proposal"
    )

    assert get_response.status_code == 200
    assert get_response.json() == post_response.json()


def test_proposal_survives_restart(setup_api, monkeypatch):
    client, _, db_path, incident_id, _ = setup_api

    monkeypatch.setattr(
        api.FixProposalGenerator,
        "generate",
        mock_generate,
    )

    response = client.post(
        f"/incidents/{incident_id}/propose-fix"
    )

    assert response.status_code == 200

    reopened_repository = IncidentRepository(db_path)

    saved = reopened_repository.get_fix_proposal(
        incident_id
    )

    assert saved is not None
    assert saved["status"] == "proposed"


def test_reinvestigation_invalidates_proposal(
    setup_api, monkeypatch
):
    client, repository, _, incident_id, evidence_id = setup_api

    monkeypatch.setattr(
        api.FixProposalGenerator,
        "generate",
        mock_generate,
    )

    response = client.post(
        f"/incidents/{incident_id}/propose-fix"
    )
    assert response.status_code == 200

    old_investigation = repository.get_investigation(
        incident_id
    )

    repository.save_investigation(
        incident_id,
        old_investigation,
    )

    assert repository.get_fix_proposal(incident_id) is None

    get_response = client.get(
        f"/incidents/{incident_id}/fix-proposal"
    )

    assert get_response.status_code == 404


def test_missing_proposal_returns_404(setup_api):
    client, _, _, incident_id, _ = setup_api

    response = client.get(
        f"/incidents/{incident_id}/fix-proposal"
    )

    assert response.status_code == 404


def test_missing_incident_returns_404(setup_api):
    client, _, _, _, _ = setup_api

    response = client.get(
        "/incidents/unknown-id/fix-proposal"
    )

    assert response.status_code == 404


def test_abstention_does_not_persist(
    setup_api, monkeypatch
):
    client, repository, _, incident_id, _ = setup_api

    def abstain(self, investigation, context):
        return None

    monkeypatch.setattr(
        api.FixProposalGenerator,
        "generate",
        abstain,
    )

    response = client.post(
        f"/incidents/{incident_id}/propose-fix"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "needs_more_evidence"

    assert repository.get_fix_proposal(incident_id) is None


def test_regeneration_replaces_proposal(
    setup_api, monkeypatch
):
    client, repository, _, incident_id, _ = setup_api

    monkeypatch.setattr(
        api.FixProposalGenerator,
        "generate",
        mock_generate,
    )

    first = client.post(
        f"/incidents/{incident_id}/propose-fix"
    )

    assert first.status_code == 200

    def revised_generate(self, investigation, context):
        return mock_generate(
            self, investigation, context
        ).model_copy(
            update={"title": "Review database capacity"}
        )

    monkeypatch.setattr(
        api.FixProposalGenerator,
        "generate",
        revised_generate,
    )

    second = client.post(
        f"/incidents/{incident_id}/propose-fix"
    )

    assert second.status_code == 200

    saved = repository.get_fix_proposal(incident_id)

    assert saved["proposal"]["title"] == (
        "Review database capacity"
    )


def test_investigation_change_during_generation(
    setup_api, monkeypatch
):
    client, repository, _, incident_id, _ = setup_api

    def change_investigation(self, investigation, context):
        # Simulate a new investigation arriving while
        # the LLM is generating a proposal.
        updated = investigation.model_dump(mode="json")
        updated["report"]["summary"] = (
            "New investigation result"
        )

        repository.save_investigation(
            incident_id,
            updated,
        )

        return mock_generate(
            self, investigation, context
        )

    monkeypatch.setattr(
        api.FixProposalGenerator,
        "generate",
        change_investigation,
    )

    response = client.post(
        f"/incidents/{incident_id}/propose-fix"
    )

    assert response.status_code == 409
    assert repository.get_fix_proposal(incident_id) is None
