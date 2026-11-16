
from datetime import datetime, timezone, timedelta

from app.detection.incident_manager import IncidentManager


def snapshot(error_rate=None, latency=None):
    return {
        "error_rate": error_rate,
        "average_latency_ms": latency,
    }


def test_healthy_metrics_create_no_incidents():
    manager = IncidentManager()

    events = manager.process_metrics(
        snapshot(0.01, 100)
    )

    assert events == []
    assert manager.get_active_incidents() == []


def test_creates_incident():
    manager = IncidentManager()

    events = manager.process_metrics(
        snapshot(0.12, 100)
    )

    assert len(events) == 1
    assert events[0]["event"] == "created"
    assert events[0]["incident"]["severity"] == "critical"
    assert events[0]["incident"]["status"] == "active"


def test_deduplicates_incident():
    manager = IncidentManager()

    first = manager.process_metrics(
        snapshot(0.12, 100)
    )
    second = manager.process_metrics(
        snapshot(0.15, 100)
    )

    assert first[0]["incident"]["id"] == (
        second[0]["incident"]["id"]
    )
    assert second[0]["event"] == "updated"
    assert second[0]["incident"]["occurrences"] == 2
    assert len(manager.get_active_incidents()) == 1


def test_severity_change():
    manager = IncidentManager()

    manager.process_metrics(snapshot(0.12, 100))
    events = manager.process_metrics(
        snapshot(0.07, 100)
    )

    assert events[0]["event"] == "severity_changed"
    assert events[0]["incident"]["severity"] == "warning"


def test_resolves_incident():
    manager = IncidentManager()

    manager.process_metrics(snapshot(0.12, 100))
    events = manager.process_metrics(
        snapshot(0.02, 100)
    )

    assert events[0]["event"] == "resolved"
    assert events[0]["incident"]["status"] == "resolved"
    assert events[0]["incident"]["resolved_at"] is not None
    assert manager.get_active_incidents() == []


def test_missing_metrics_do_not_resolve():
    manager = IncidentManager()

    manager.process_metrics(snapshot(0.12, 100))
    events = manager.process_metrics(
        snapshot(None, None)
    )

    assert events == []
    assert len(manager.get_active_incidents()) == 1


def test_recurrence_creates_new_incident():
    manager = IncidentManager()

    first = manager.process_metrics(snapshot(0.12, 100))
    manager.process_metrics(snapshot(0.01, 100))
    second = manager.process_metrics(snapshot(0.15, 100))

    assert second[0]["event"] == "created"
    assert (
        first[0]["incident"]["id"]
        != second[0]["incident"]["id"]
    )


def test_multiple_incidents():
    manager = IncidentManager()

    events = manager.process_metrics(
        snapshot(0.15, 1500)
    )

    assert len(events) == 2
    assert len(manager.get_active_incidents()) == 2


def test_resolves_only_healthy_metric():
    manager = IncidentManager()

    manager.process_metrics(snapshot(0.15, 1500))
    events = manager.process_metrics(
        snapshot(0.01, None)
    )

    assert len(events) == 1
    assert events[0]["event"] == "resolved"
    assert events[0]["incident"]["incident_type"] == (
        "high_error_rate"
    )

    active = manager.get_active_incidents()
    assert len(active) == 1
    assert active[0]["incident_type"] == "high_latency"


def test_uses_utc_timestamps():
    manager = IncidentManager()

    now = datetime(
        2026, 11, 15, 10, 0, tzinfo=timezone.utc
    )

    events = manager.process_metrics(
        snapshot(0.12, 100), now=now
    )

    assert events[0]["incident"]["created_at"] == (
        now.isoformat()
    )
