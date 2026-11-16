
import pytest

from app.investigation.evidence_verifier import (
    EvidenceVerifier,
)
from app.investigation.llm_client import InvestigationReport


@pytest.fixture
def context():
    return {
        "incident": {
            "id": "incident-123",
            "incident_type": "high_error_rate",
        },
        "evidence": [{
            "evidence_id": 7,
            "level": "ERROR",
            "message": "Database connection failed",
        }],
    }


def make_report(
    evidence_ids=None,
    confidence="medium",
    insufficient=False,
):
    return InvestigationReport(
        summary="Elevated HTTP errors were detected.",
        possible_cause="Database connectivity issue",
        confidence=confidence,
        evidence_ids=(
            [7] if evidence_ids is None else evidence_ids
        ),
        next_steps=["Inspect database connectivity"],
        insufficient_evidence=insufficient,
    )


def test_valid_citations(context):
    result = EvidenceVerifier().verify(
        make_report(), context
    )

    assert result.citation_ids_valid is True
    assert result.verified_evidence_ids == [7]
    assert result.report.confidence == "medium"


def test_invalid_citations_rejected(context):
    report = make_report(evidence_ids=[999])

    with pytest.raises(ValueError):
        EvidenceVerifier().verify(report, context)


def test_missing_citations_abstains(context):
    report = make_report(evidence_ids=[])

    result = EvidenceVerifier().verify(report, context)

    assert result.report.insufficient_evidence is True
    assert result.report.possible_cause is None
    assert result.report.confidence == "low"


def test_no_log_evidence_abstains():
    report = make_report()

    # A cited ID cannot be valid when no evidence exists.
    context = {"incident": {}, "evidence": []}

    with pytest.raises(ValueError):
        EvidenceVerifier().verify(report, context)

    result = EvidenceVerifier().verify(
        make_report(evidence_ids=[]),
        context,
    )

    assert result.report.insufficient_evidence is True


def test_high_confidence_is_capped(context):
    result = EvidenceVerifier().verify(
        make_report(confidence="high"), context
    )

    assert result.report.confidence == "medium"
    assert result.requires_human_review is True


def test_insufficient_evidence_removes_cause(context):
    result = EvidenceVerifier().verify(
        make_report(insufficient=True), context
    )

    assert result.report.possible_cause is None
    assert result.report.confidence == "low"
    assert result.report.insufficient_evidence is True
