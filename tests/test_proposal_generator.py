
import json

import httpx
import pytest

from app.investigation.llm_client import InvestigationReport
from app.investigation.evidence_verifier import VerificationResult

from app.remediation.proposal_generator import (
    FixProposalGenerator,
    FixProposalError,
)


def make_context():
    return {
        "incident": {
            "id": "incident-123",
            "incident_type": "high_error_rate",
        },
        "evidence": [
            {
                "evidence_id": 1,
                "level": "ERROR",
                "message": "Database connection failed",
            },
        ],
    }


def make_investigation(insufficient=False):
    report = InvestigationReport(
        summary="Elevated HTTP errors.",
        possible_cause=(
            None if insufficient
            else "Database connectivity may be contributing."
        ),
        confidence="medium" if not insufficient else "low",
        evidence_ids=[] if insufficient else [1],
        next_steps=["Inspect database connectivity"],
        insufficient_evidence=insufficient,
    )

    return VerificationResult(
        report=report,
        citation_ids_valid=True,
        verified_evidence_ids=[] if insufficient else [1],
        warnings=[],
        requires_human_review=True,
    )


def make_proposal():
    return {
        "title": "Investigate database connectivity",
        "description": "Review database connection failures.",
        "rationale": "Connection errors coincide with HTTP errors.",
        "confidence": "high",
        "risk_level": "low",
        "evidence_ids": [1],
        "proposed_steps": [
            "Inspect database connection pool metrics"
        ],
        "validation_steps": [
            "Confirm HTTP error rate returns to baseline"
        ],
        "rollback_steps": [
            "Restore previous configuration if changed"
        ],
    }


def make_client(proposal):
    def handler(request):
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(proposal)
                        }
                    }
                ]
            },
        )

    return httpx.Client(
        transport=httpx.MockTransport(handler)
    )


def test_proposal_generation():
    with make_client(make_proposal()) as client:
        generator = FixProposalGenerator(
            api_key="test",
            model="test-model",
            client=client,
        )

        proposal = generator.generate(
            make_investigation(),
            make_context(),
        )

    assert proposal is not None
    assert proposal.evidence_ids == [1]

    # High confidence must be capped at medium.
    assert proposal.confidence == "medium"
    assert proposal.validation_steps
    assert proposal.rollback_steps


def test_insufficient_evidence_abstains():
    generator = FixProposalGenerator()

    proposal = generator.generate(
        make_investigation(insufficient=True),
        make_context(),
    )

    assert proposal is None


def test_invalid_evidence_id_rejected():
    bad_proposal = make_proposal()
    bad_proposal["evidence_ids"] = [999]

    with make_client(bad_proposal) as client:
        generator = FixProposalGenerator(
            api_key="test",
            model="test-model",
            client=client,
        )

        with pytest.raises(FixProposalError):
            generator.generate(
                make_investigation(),
                make_context(),
            )


def test_missing_rollback_rejected():
    bad_proposal = make_proposal()
    bad_proposal["rollback_steps"] = []

    with make_client(bad_proposal) as client:
        generator = FixProposalGenerator(
            api_key="test",
            model="test-model",
            client=client,
        )

        with pytest.raises(FixProposalError):
            generator.generate(
                make_investigation(),
                make_context(),
            )


def test_context_evidence_mismatch_rejected():
    context = make_context()
    context["evidence"] = [
        {"evidence_id": 2, "message": "Unrelated log"}
    ]

    generator = FixProposalGenerator(
        api_key="test",
        model="test-model",
    )

    with pytest.raises(FixProposalError):
        generator.generate(
            make_investigation(),
            context,
        )
