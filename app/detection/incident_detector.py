
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from app.detection.rules import (
    DetectionThresholds,
    Severity,
    evaluate_error_rate,
    evaluate_latency,
)


@dataclass
class Incident:
    incident_type: str
    severity: Severity
    message: str
    metric_value: float
    threshold: float
    detected_at: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["severity"] = self.severity.value
        return data


def detect_incidents(
    metrics: dict[str, Any],
    thresholds: Optional[DetectionThresholds] = None,
) -> list[Incident]:
    if thresholds is None:
        thresholds = DetectionThresholds()

    incidents = []
    timestamp = datetime.now(timezone.utc).isoformat()

    error_rate = metrics.get("error_rate")
    latency_ms = metrics.get("average_latency_ms")

    error_severity = evaluate_error_rate(
        error_rate, thresholds
    )

    if error_severity in (
        Severity.WARNING,
        Severity.CRITICAL,
    ):
        threshold = (
            thresholds.critical_error_rate
            if error_severity == Severity.CRITICAL
            else thresholds.warning_error_rate
        )

        incidents.append(
            Incident(
                incident_type="high_error_rate",
                severity=error_severity,
                message=(
                    f"HTTP error rate is {error_rate:.2%}, "
                    f"exceeding the {threshold:.0%} threshold"
                ),
                metric_value=error_rate,
                threshold=threshold,
                detected_at=timestamp,
            )
        )

    latency_severity = evaluate_latency(
        latency_ms, thresholds
    )

    if latency_severity in (
        Severity.WARNING,
        Severity.CRITICAL,
    ):
        threshold = (
            thresholds.critical_latency_ms
            if latency_severity == Severity.CRITICAL
            else thresholds.warning_latency_ms
        )

        incidents.append(
            Incident(
                incident_type="high_latency",
                severity=latency_severity,
                message=(
                    f"Average request latency is "
                    f"{latency_ms:.2f} ms, exceeding "
                    f"the {threshold:.0f} ms threshold"
                ),
                metric_value=latency_ms,
                threshold=threshold,
                detected_at=timestamp,
            )
        )

    return incidents
