
from scripts.evaluate_investigator import assess_report

from app.investigation.llm_client import InvestigationReport
from app.investigation.evidence_verifier import (
    EvidenceVerifier,
)


def make_report(**overrides):
    data = {
        "summary": "Elevated HTTP errors detected",
        "possible_cause": "Database connectivity issue",
        "confidence": "medium",
        "evidence_ids": [1],
        "next_steps": ["Inspect database connectivity"],
        "insufficient_evidence": False,
    }
    data.update(overrides)
    return InvestigationReport(**data)


def context():
    return {
        "incident": {"id": "test-incident"},
        "evidence": [{
            "evidence_id": 1,
            "message": "Database connection failed",
        }],
    }


def test_evaluation_accepts_valid_citations():
    ctx = context()

    verified = EvidenceVerifier().verify(
        make_report(), ctx
    )

    checks = assess_report(
        verified, ctx, "possible_cause"
    )

    assert all(checks.values())


def test_evaluation_requires_abstention():
    ctx = context()

    verified = EvidenceVerifier().verify(
        make_report(), ctx
    )

    checks = assess_report(
        verified, ctx, "abstain"
    )

    assert checks["expected_abstention"] is False


def test_no_evidence_abstains():
    ctx = {
        "incident": {"id": "test-incident"},
        "evidence": [],
    }

    verified = EvidenceVerifier().verify(
        make_report(
            possible_cause=None,
            confidence="low",
            evidence_ids=[],
            insufficient_evidence=True,
        ),
        ctx,
    )

    checks = assess_report(verified, ctx, "abstain")

    assert all(checks.values())


def test_high_confidence_is_capped():
    ctx = context()

    verified = EvidenceVerifier().verify(
        make_report(confidence="high"), ctx
    )

    checks = assess_report(
        verified, ctx, "possible_cause"
    )

    assert checks["confidence_safeguard"] is True
    assert verified.report.confidence == "medium"
