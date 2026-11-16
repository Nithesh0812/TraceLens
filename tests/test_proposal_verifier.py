
from app.investigation.llm_client import InvestigationReport
from app.investigation.evidence_verifier import VerificationResult

from app.remediation.schemas import FixProposal
from app.remediation.proposal_verifier import FixProposalVerifier


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
            }
        ],
    }


def make_investigation(insufficient=False):
    return VerificationResult(
        report=InvestigationReport(
            summary="Elevated HTTP errors detected.",
            possible_cause=(
                None if insufficient
                else "Database connectivity may be involved."
            ),
            confidence="medium" if not insufficient else "low",
            evidence_ids=[] if insufficient else [1],
            next_steps=["Inspect database metrics"],
            insufficient_evidence=insufficient,
        ),
        citation_ids_valid=True,
        verified_evidence_ids=[] if insufficient else [1],
        warnings=[],
        requires_human_review=True,
    )


def make_proposal():
    return FixProposal(
        title="Investigate database connections",
        description="Review database connection failures.",
        rationale="Connection failures coincide with errors.",
        confidence="high",
        risk_level="low",
        evidence_ids=[1],
        proposed_steps=[
            "Inspect database connection pool usage"
        ],
        validation_steps=[
            "Check HTTP error rates after review"
        ],
        rollback_steps=[
            "Restore the previous configuration if changed"
        ],
    )


def verify(proposal, investigation=None, context=None):
    return FixProposalVerifier().verify(
        incident_id="incident-123",
        proposal=proposal,
        investigation=investigation or make_investigation(),
        context=context or make_context(),
    )


def test_valid_proposal():
    result = verify(make_proposal())

    assert result.status == "proposed"
    assert result.proposal is not None
    assert result.requires_human_review is True


def test_confidence_capped():
    result = verify(make_proposal())

    assert result.proposal.confidence == "medium"


def test_insufficient_evidence_abstains():
    result = verify(
        make_proposal(),
        investigation=make_investigation(insufficient=True),
    )

    assert result.status == "needs_more_evidence"
    assert result.proposal is None


def test_invalid_citation_rejected():
    proposal = make_proposal().model_copy(
        update={"evidence_ids": [999]}
    )

    result = verify(proposal)

    assert result.status == "needs_more_evidence"
    assert result.proposal is None


def test_destructive_command_rejected():
    proposal = make_proposal().model_copy(
        update={
            "proposed_steps": [
                "Run rm -rf /var/lib/database"
            ]
        }
    )

    result = verify(proposal)

    assert result.status == "needs_more_evidence"
    assert result.proposal is None


def test_security_disable_rejected():
    proposal = make_proposal().model_copy(
        update={
            "proposed_steps": [
                "Disable authentication temporarily"
            ]
        }
    )

    result = verify(proposal)

    assert result.status == "needs_more_evidence"
    assert result.proposal is None


def test_missing_rollback_rejected():
    proposal = make_proposal().model_copy(
        update={"rollback_steps": []}
    )

    result = verify(proposal)

    assert result.status == "needs_more_evidence"


def test_missing_proposal_abstains():
    result = verify(None)

    assert result.status == "needs_more_evidence"
    assert result.proposal is None


def test_context_mismatch_rejected():
    context = make_context()
    context["incident"]["id"] = "different-incident"

    result = verify(
        make_proposal(),
        context=context,
    )

    assert result.status == "needs_more_evidence"
    assert result.proposal is None
