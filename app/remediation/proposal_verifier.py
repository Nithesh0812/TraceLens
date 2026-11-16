
import re

from app.investigation.evidence_verifier import VerificationResult
from app.remediation.schemas import (
    FixProposal,
    FixProposalResult,
)


CONFIDENCE_ORDER = {
    "low": 0,
    "medium": 1,
    "high": 2,
}


# High-risk operations and instructions that should
# not appear in an advisory remediation proposal.
UNSAFE_PATTERNS = (
    r"\brm\s+-[a-z]*r[a-z]*f\b",
    r"\brm\s+-[a-z]*f[a-z]*r\b",
    r"\bDROP\s+(?:TABLE|DATABASE|SCHEMA)\b",
    r"\bTRUNCATE\s+TABLE\b",
    r"\bDELETE\s+FROM\b",
    r"\bformat\s+[a-z]:",
    r"\bmkfs(?:\.[a-z0-9]+)?\b",
    r"\bdd\s+if=",
    r"\b(?:disable|turn off|bypass)\s+"
    r"(?:authentication|authorization|"
    r"logging|monitoring|security|"
    r"firewall|audit logging)\b",
    r"\b(?:print|expose|share|upload)\s+"
    r"(?:passwords?|api keys?|secrets?|"
    r"access tokens?|credentials?)\b",
)

COMPILED_UNSAFE_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in UNSAFE_PATTERNS
]


class FixProposalVerifier:
    """
    Apply deterministic safety checks to generated
    remediation proposals.

    This verifier does not execute proposed actions.
    """

    def verify(
        self,
        incident_id: str,
        proposal: FixProposal | None,
        investigation: VerificationResult,
        context: dict,
    ) -> FixProposalResult:

        warnings = []

        def abstain(reason: str) -> FixProposalResult:
            return FixProposalResult(
                incident_id=incident_id,
                status="needs_more_evidence",
                proposal=None,
                warnings=[reason],
                requires_human_review=True,
            )

        # Ensure the proposal refers to the incident
        # for which the context was constructed.
        incident = context.get("incident") or {}

        if incident.get("id") != incident_id:
            return abstain(
                "Incident context does not match "
                "the requested incident."
            )

        report = investigation.report

        # Do not permit specific remediation when
        # the investigation was inconclusive.
        if (
            report.insufficient_evidence
            or report.possible_cause is None
            or not investigation.citation_ids_valid
        ):
            return abstain(
                "Verified investigation does not "
                "support a specific remediation."
            )

        if proposal is None:
            return abstain(
                "No remediation proposal is available."
            )

        allowed_ids = set(
            investigation.verified_evidence_ids
        )

        context_ids = {
            item.get("evidence_id")
            for item in context.get("evidence", [])
        }

        proposal_ids = set(proposal.evidence_ids)

        # Reject empty or unknown citations.
        if (
            not proposal_ids
            or not proposal_ids.issubset(allowed_ids)
            or not proposal_ids.issubset(context_ids)
        ):
            return abstain(
                "Proposal contains missing or "
                "unverified evidence citations."
            )

        # Require actual proposed, validation,
        # and rollback steps.
        step_groups = (
            proposal.proposed_steps,
            proposal.validation_steps,
            proposal.rollback_steps,
        )

        if any(
            not steps
            or any(not step.strip() for step in steps)
            for steps in step_groups
        ):
            return abstain(
                "Proposal is missing actionable "
                "validation or rollback guidance."
            )

        # Screen model-generated instructions for
        # known unsafe operations.
        proposal_text = "\n".join([
            proposal.title,
            proposal.description,
            proposal.rationale,
            *proposal.proposed_steps,
            *proposal.validation_steps,
            *proposal.rollback_steps,
        ])

        for pattern in COMPILED_UNSAFE_PATTERNS:
            if pattern.search(proposal_text):
                return abstain(
                    "Proposal contains potentially "
                    "unsafe remediation instructions."
                )

        # Never elevate confidence beyond the
        # verified investigation.
        safe_confidence = proposal.confidence

        if CONFIDENCE_ORDER[safe_confidence] > (
            CONFIDENCE_ORDER[report.confidence]
        ):
            safe_confidence = report.confidence

            warnings.append(
                "Proposal confidence was capped "
                "at investigation confidence."
            )

        safe_proposal = proposal.model_copy(
            update={"confidence": safe_confidence}
        )

        warnings.append(
            "Evidence IDs were validated, but "
            "causality and remediation effectiveness "
            "have not been independently established."
        )

        warnings.append(
            "Human approval is required. "
            "No remediation has been executed."
        )

        return FixProposalResult(
            incident_id=incident_id,
            status="proposed",
            proposal=safe_proposal,
            warnings=warnings,
            requires_human_review=True,
        )
