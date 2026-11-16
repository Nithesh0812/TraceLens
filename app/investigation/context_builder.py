
from typing import Any

from app.storage.incident_repository import IncidentRepository


class IncidentNotFoundError(Exception):
    pass


class InvestigationContextBuilder:
    """
    Build a structured investigation context from
    persisted incident records and log evidence.
    """

    def __init__(
        self,
        repository: IncidentRepository,
        max_evidence: int = 20,
        max_message_chars: int = 1000,
    ):
        if max_evidence < 0:
            raise ValueError("max_evidence cannot be negative")

        if max_message_chars <= 0:
            raise ValueError("max_message_chars must be positive")

        self.repository = repository
        self.max_evidence = max_evidence
        self.max_message_chars = max_message_chars

    def build(self, incident_id: str) -> dict[str, Any]:
        incident = self.repository.get_by_id(incident_id)

        if incident is None:
            raise IncidentNotFoundError(
                f"Incident not found: {incident_id}"
            )

        stored_logs = self.repository.list_evidence(incident_id)
        selected_logs = stored_logs[:self.max_evidence]

        evidence = []

        for log in selected_logs:
            evidence.append({
                "evidence_id": log["id"],
                "timestamp": log["timestamp"],
                "level": log["level"],
                "message": log["message"][
                    :self.max_message_chars
                ],
                "seconds_from_incident": log[
                    "seconds_from_incident"
                ],
            })

        return {
            "incident": {
                "id": incident["id"],
                "incident_type": incident["incident_type"],
                "severity": incident["severity"],
                "status": incident["status"],
                "message": incident["message"],
                "metric_value": incident["metric_value"],
                "created_at": incident["created_at"],
                "updated_at": incident["updated_at"],
                "resolved_at": incident["resolved_at"],
                "occurrences": incident["occurrences"],
            },
            "evidence": evidence,
            "evidence_count": len(evidence),
            "total_stored_evidence": len(stored_logs),
            "evidence_truncated": (
                len(stored_logs) > len(evidence)
                or any(
                    len(log["message"]) > self.max_message_chars
                    for log in selected_logs
                )
            ),
            "has_evidence": bool(evidence),
            "investigation_ready": bool(evidence),
        }
