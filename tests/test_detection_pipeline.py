
from datetime import datetime, timedelta, timezone

from app.detection.incident_detector import detect_incidents
from app.detection.log_correlator import correlate_incidents


def test_detection_and_correlation_pipeline():
    metrics = {
        "request_rate": 15.0,
        "error_rate": 0.12,
        "average_latency_ms": 1200.0,
    }

    incidents = detect_incidents(metrics)

    timestamp = (
        datetime.now(timezone.utc) - timedelta(minutes=1)
    ).isoformat()

    logs = [
        {
            "timestamp": timestamp,
            "level": "ERROR",
            "message": "Database connection failed",
        },
        {
            "timestamp": timestamp,
            "level": "WARNING",
            "message": "Request taking too long",
        },
    ]

    correlated = correlate_incidents(incidents, logs)

    assert len(correlated) == 2

    for incident in correlated:
        assert incident["severity"] == "critical"
        assert incident["correlated_log_count"] == 2
        assert len(incident["correlated_logs"]) == 2
