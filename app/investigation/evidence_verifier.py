
from typing import Any

from pydantic import BaseModel

from app.investigation.llm_client import InvestigationReport


class VerificationResult(BaseModel):
    report: InvestigationReport
    citation_ids_valid: bool
    verified_evidence_ids: list[int]
    warnings: list[str]
    requires_human_review: bool


AUTH_ONLY_WARNING_MARKERS = (
    "invalid login credentials",
    "authentication token expired",
    "invalid password",
    "invalid credentials",
    "expired authentication token",
)


def authentication_warnings_only(
    context: dict[str, Any],
) -> bool:
    """Identify authentication-only warnings for 5xx incidents."""

    incident = context.get("incident") or {}
    evidence = context.get("evidence") or []

    if incident.get("incident_type") != "high_error_rate":
        return False

    if not evidence:
        return False

    return all(
        str(log.get("level", "")).upper()
        in {"WARNING", "WARN"}
        and any(
            marker in str(log.get("message", "")).lower()
            for marker in AUTH_ONLY_WARNING_MARKERS
        )
        for log in evidence
    )

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

        # Authentication warnings alone do not explain
        # an incident measured using HTTP 5xx responses.
        if authentication_warnings_only(context):
            warnings.append(
                "Only authentication warnings were found; "
                "they do not establish the cause of HTTP "
                "5xx failures."
            )

            safe_report = InvestigationReport(
                summary=(
                    "HTTP 5xx error rate is elevated, "
                    "but the available authentication "
                    "warnings do not explain the failures."
                ),
                possible_cause=None,
                confidence="low",
                evidence_ids=[],
                next_steps=[
                    "Inspect HTTP 5xx request logs.",
                    "Check application exceptions and "
                    "server-side failures.",
                    "Correlate failing endpoints with "
                    "dependency and database metrics.",
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
