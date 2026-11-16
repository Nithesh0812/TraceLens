import pytest

from app.storage.incident_repository import IncidentRepository


@pytest.fixture
def repository(tmp_path):
    return IncidentRepository(
        tmp_path / "test_investigations.db"
    )


@pytest.fixture
def sample_incident():
    return {
        "id": "test-incident-001",
        "incident_type": "high_latency",
        "severity": "critical",
        "status": "active",
        "message": "Latency exceeded threshold",
        "metric_value": 1200.0,
        "created_at": "2026-11-16T10:00:00+00:00",
        "updated_at": "2026-11-16T10:00:00+00:00",
        "resolved_at": None,
        "occurrences": 1,
    }


@pytest.fixture
def sample_report():
    return {
        "summary": "High latency detected",
        "possible_cause": "Database queries are slow",
        "confidence": "high",
        "evidence_ids": [1, 2],
        "next_steps": [
            "Inspect slow queries",
            "Check database indexes",
        ],
    }


def test_save_and_retrieve_investigation(
    repository, sample_incident, sample_report
):
    repository.save(sample_incident)

    repository.save_investigation(
        sample_incident["id"],
        sample_report,
    )

    saved = repository.get_investigation(
        sample_incident["id"]
    )

    assert saved == sample_report


def test_update_existing_investigation(
    repository, sample_incident, sample_report
):
    repository.save(sample_incident)

    repository.save_investigation(
        sample_incident["id"],
        sample_report,
    )

    updated_report = {
        **sample_report,
        "confidence": "medium",
    }

    repository.save_investigation(
        sample_incident["id"],
        updated_report,
    )

    saved = repository.get_investigation(
        sample_incident["id"]
    )

    assert saved["confidence"] == "medium"


def test_missing_investigation_returns_none(repository):
    assert repository.get_investigation("missing-id") is None


def test_cannot_save_for_missing_incident(
    repository, sample_report
):
    with pytest.raises(ValueError, match="Incident not found"):
        repository.save_investigation(
            "missing-id",
            sample_report,
        )


def test_investigation_persists_after_restart(
    repository, sample_incident, sample_report
):
    repository.save(sample_incident)

    repository.save_investigation(
        sample_incident["id"],
        sample_report,
    )

    restarted_repository = IncidentRepository(
        repository.db_path
    )

    saved = restarted_repository.get_investigation(
        sample_incident["id"]
    )

    assert saved == sample_report