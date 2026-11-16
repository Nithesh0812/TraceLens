
from typing import Any

from pydantic import BaseModel

from app.investigation.llm_client import InvestigationReport


class VerificationResult(BaseModel):
    report: InvestigationReport
    citation_ids_valid: bool
    verified_evidence_ids: list[int]
    warnings: list[str]
    requires_human_review: bool


class EvidenceVerifier:
    """Apply deterministic safeguards to AI investigations."""

    def verify(
        self,
        report: InvestigationReport,
        context: dict[str, Any],
    ) -> VerificationResult:

        evidence = context.get("evidence") or []
        allowed_ids = {
            item["evidence_id"]
            for item in evidence
        }

        supplied_ids = set(report.evidence_ids)
        unknown_ids = supplied_ids - allowed_ids
        warnings = []

        # Invalid citations must fail closed.
        if unknown_ids:
            raise ValueError(
                "Report contains unknown evidence IDs"
            )

        # No evidence means there cannot be a
        # supported root-cause hypothesis.
        if not evidence or not supplied_ids:
            warnings.append(
                "No cited log evidence supports a cause."
            )

            safe_report = InvestigationReport(
                summary=(
                    "An incident was detected, but the "
                    "available cited logs are insufficient "
                    "to identify a possible cause."
                ),
                possible_cause=None,
                confidence="low",
                evidence_ids=[],
                next_steps=[
                    "Inspect application logs.",
                    "Check relevant metrics and timestamps.",
                ],
                insufficient_evidence=True,
            )

            return VerificationResult(
                report=safe_report,
                citation_ids_valid=True,
                verified_evidence_ids=[],
                warnings=warnings,
                requires_human_review=True,
            )

        # A valid citation does not prove causality.
        # Conservatively cap model confidence.
        safe_confidence = report.confidence

        if safe_confidence == "high":
            safe_confidence = "medium"
            warnings.append(
                "Confidence capped at medium because "
                "citation validity does not prove causality."
            )

        if report.insufficient_evidence:
            warnings.append(
                "The model reports insufficient evidence."
            )

            safe_report = report.model_copy(
                update={
                    "confidence": "low",
                    "possible_cause": None,
                }
            )
        else:
            safe_report = report.model_copy(
                update={"confidence": safe_confidence}
            )

        warnings.append(
            "Citation IDs were checked, but factual "
            "support and causality are not independently "
            "verified."
        )

        return VerificationResult(
            report=safe_report,
            citation_ids_valid=True,
            verified_evidence_ids=sorted(supplied_ids),
            warnings=warnings,
            requires_human_review=True,
        )
