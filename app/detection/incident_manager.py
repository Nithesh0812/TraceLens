
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from app.detection.incident_detector import detect_incidents
from app.detection.rules import DetectionThresholds, Severity


METRIC_KEYS = {
    "high_error_rate": "error_rate",
    "high_latency": "average_latency_ms",
}


@dataclass
class ManagedIncident:
    id: str
    incident_type: str
    severity: Severity
    status: str
    message: str
    metric_value: float
    created_at: str
    updated_at: str
    resolved_at: Optional[str] = None
    occurrences: int = 1

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["severity"] = self.severity.value
        return data


class IncidentManager:
    def __init__(
        self,
        thresholds: Optional[DetectionThresholds] = None,
    ):
        self.thresholds = (
            thresholds
            if thresholds is not None
            else DetectionThresholds()
        )
        self.incidents: dict[str, ManagedIncident] = {}

    def process_metrics(
        self,
        metrics: dict[str, Any],
        now: Optional[datetime] = None,
    ) -> list[dict[str, Any]]:
        """
        Process one metrics snapshot.

        Returns lifecycle events:
        created, updated, severity_changed, resolved.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")

        timestamp = now.astimezone(timezone.utc).isoformat()

        # Validate and detect before modifying state.
        detected = detect_incidents(metrics, self.thresholds)
        detected_by_type = {
            item.incident_type: item for item in detected
        }

        events = []

        for incident_type, metric_key in METRIC_KEYS.items():
            # Missing data must not resolve an incident.
            if metrics.get(metric_key) is None:
                continue

            detection = detected_by_type.get(incident_type)
            existing = self.incidents.get(incident_type)

            if detection is not None:
                if existing is None or existing.status == "resolved":
                    record = ManagedIncident(
                        id=str(uuid4()),
                        incident_type=incident_type,
                        severity=detection.severity,
                        status="active",
                        message=detection.message,
                        metric_value=detection.metric_value,
                        created_at=timestamp,
                        updated_at=timestamp,
                    )
                    self.incidents[incident_type] = record
                    event_type = "created"

                else:
                    old_severity = existing.severity
                    existing.severity = detection.severity
                    existing.message = detection.message
                    existing.metric_value = detection.metric_value
                    existing.updated_at = timestamp
                    existing.occurrences += 1

                    event_type = (
                        "severity_changed"
                        if old_severity != detection.severity
                        else "updated"
                    )
                    record = existing

                events.append({
                    "event": event_type,
                    "incident": record.to_dict(),
                })

            elif existing is not None and existing.status == "active":
                existing.status = "resolved"
                existing.updated_at = timestamp
                existing.resolved_at = timestamp

                events.append({
                    "event": "resolved",
                    "incident": existing.to_dict(),
                })

        return events

    def get_active_incidents(self) -> list[dict[str, Any]]:
        return [
            incident.to_dict()
            for incident in self.incidents.values()
            if incident.status == "active"
        ]

    def get_all_incidents(self) -> list[dict[str, Any]]:
        return [
            incident.to_dict()
            for incident in self.incidents.values()
        ]
