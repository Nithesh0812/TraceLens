
import pytest

from app.detection.incident_manager import IncidentManager
from app.investigation.context_builder import (
    IncidentNotFoundError,
    InvestigationContextBuilder,
)
from app.storage.incident_repository import IncidentRepository


@pytest.fixture
def incident_data(tmp_path):
    repository = IncidentRepository(
        tmp_path / "investigation.db"
    )

    manager = IncidentManager()

    events = manager.process_metrics({
        "error_rate": 0.12,
        "average_latency_ms": 200.0,
    })

    incident = events[0]["incident"]

    evidence = [{
        "timestamp": incident["created_at"],
        "level": "ERROR",
        "message": "Database connection failed",
        "seconds_from_incident": 0.0,
    }]

    repository.save(incident, evidence)

    return repository, incident


def test_build_context(incident_data):
    repository, incident = incident_data

    builder = InvestigationContextBuilder(repository)
    context = builder.build(incident["id"])

    assert context["incident"]["id"] == incident["id"]
    assert context["incident"]["severity"] == "critical"
    assert context["evidence_count"] == 1
    assert context["has_evidence"] is True
    assert context["investigation_ready"] is True
    assert context["evidence"][0]["evidence_id"] > 0
    assert (
        context["evidence"][0]["message"]
        == "Database connection failed"
    )


def test_missing_incident(tmp_path):
    repository = IncidentRepository(tmp_path / "empty.db")
    builder = InvestigationContextBuilder(repository)

    with pytest.raises(IncidentNotFoundError):
        builder.build("nonexistent")


def test_incident_without_evidence(tmp_path):
    repository = IncidentRepository(tmp_path / "empty.db")
    manager = IncidentManager()

    incident = manager.process_metrics({
        "error_rate": 0.12,
    })[0]["incident"]

    repository.save(incident)

    context = InvestigationContextBuilder(
        repository
    ).build(incident["id"])

    assert context["has_evidence"] is False
    assert context["investigation_ready"] is False
    assert context["evidence"] == []


def test_evidence_limit(incident_data):
    repository, incident = incident_data

    for index in range(5):
        repository.save(incident, [{
            "timestamp": incident["created_at"],
            "level": "ERROR",
            "message": f"Additional failure {index}",
            "seconds_from_incident": 0.0,
        }])

    builder = InvestigationContextBuilder(
        repository,
        max_evidence=2,
    )

    context = builder.build(incident["id"])

    assert context["evidence_count"] == 2
    assert context["total_stored_evidence"] == 6
    assert context["evidence_truncated"] is True


def test_message_truncation(incident_data):
    repository, incident = incident_data

    builder = InvestigationContextBuilder(
        repository,
        max_message_chars=10,
    )

    context = builder.build(incident["id"])

    assert len(context["evidence"][0]["message"]) == 10
    assert context["evidence_truncated"] is True


def test_invalid_configuration(incident_data):
    repository, _ = incident_data

    with pytest.raises(ValueError):
        InvestigationContextBuilder(
            repository, max_evidence=-1
        )

    with pytest.raises(ValueError):
        InvestigationContextBuilder(
            repository, max_message_chars=0
        )
