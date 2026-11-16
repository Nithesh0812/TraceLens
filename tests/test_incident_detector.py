
from datetime import datetime

from app.detection.incident_detector import (
    detect_incidents,
)
from app.detection.rules import (
    DetectionThresholds,
    Severity,
)


def test_normal_metrics():
    metrics = {
        "error_rate": 0.01,
        "average_latency_ms": 200.0,
    }

    assert detect_incidents(metrics) == []


def test_high_error_rate():
    metrics = {
        "error_rate": 0.12,
        "average_latency_ms": 200.0,
    }

    incidents = detect_incidents(metrics)

    assert len(incidents) == 1
    assert incidents[0].incident_type == "high_error_rate"
    assert incidents[0].severity == Severity.CRITICAL
    assert incidents[0].threshold == 0.10


def test_high_latency():
    metrics = {
        "error_rate": 0.01,
        "average_latency_ms": 700.0,
    }

    incidents = detect_incidents(metrics)

    assert len(incidents) == 1
    assert incidents[0].incident_type == "high_latency"
    assert incidents[0].severity == Severity.WARNING


def test_multiple_incidents():
    metrics = {
        "error_rate": 0.15,
        "average_latency_ms": 1500.0,
    }

    incidents = detect_incidents(metrics)

    assert len(incidents) == 2
    assert all(
        incident.severity == Severity.CRITICAL
        for incident in incidents
    )


def test_missing_metrics():
    metrics = {
        "error_rate": 0.0,
        "average_latency_ms": None,
    }

    assert detect_incidents(metrics) == []


def test_empty_metrics():
    assert detect_incidents({}) == []


def test_custom_thresholds():
    thresholds = DetectionThresholds(
        warning_error_rate=0.02,
        critical_error_rate=0.04,
    )

    metrics = {
        "error_rate": 0.03,
        "average_latency_ms": 100.0,
    }

    incidents = detect_incidents(metrics, thresholds)

    assert len(incidents) == 1
    assert incidents[0].severity == Severity.WARNING
    assert incidents[0].threshold == 0.02


def test_incident_serialization():
    incidents = detect_incidents({
        "error_rate": 0.12,
        "average_latency_ms": 100.0,
    })

    data = incidents[0].to_dict()

    assert data["severity"] == "critical"
    assert data["metric_value"] == 0.12
    assert data["incident_type"] == "high_error_rate"
    assert datetime.fromisoformat(data["detected_at"])


def test_incident_timestamp_is_timezone_aware():
    incidents = detect_incidents({
        "error_rate": 0.12,
    })

    timestamp = datetime.fromisoformat(
        incidents[0].detected_at
    )

    assert timestamp.tzinfo is not None
