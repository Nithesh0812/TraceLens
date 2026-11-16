
import os
from threading import Lock

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.detection.incident_manager import IncidentManager
from app.storage.incident_repository import IncidentRepository

import httpx

from app.services.metrics_service import (get_request_rate,get_error_rate,get_average_latency,)
import logging

from app.ingestion.jobtracker_logs import read_jobtracker_logs
from app.detection.log_correlator import correlate_logs
from app.detection.incident_detector import Incident
from app.detection.rules import Severity

router = APIRouter(
    prefix="/incidents",
    tags=["Incidents"],
)

repository = IncidentRepository(
    os.getenv("TRACELENS_DB_PATH", "tracelens.db")
)

manager = IncidentManager()
repository.load_manager_state(manager)

processing_lock = Lock()


class MetricsInput(BaseModel):
    request_rate: float | None = Field(default=None, ge=0)
    error_rate: float | None = Field(default=None, ge=0, le=1)
    average_latency_ms: float | None = Field(
        default=None, ge=0
    )


def attach_log_evidence(event: dict, logs: list[dict]) -> dict:
    """Attach time-correlated log evidence to an incident event."""

    incident = event["incident"]

    # Recovery events do not represent a newly detected problem.
    if event["event"] == "resolved":
        return event

    detection = Incident(
        incident_type=incident["incident_type"],
        severity=Severity(incident["severity"]),
        message=incident["message"],
        metric_value=incident["metric_value"],
        threshold=0.0,
        detected_at=incident["updated_at"],
    )

    correlated = correlate_logs(
        detection,
        logs,
        lookback_minutes=5,
        lookahead_minutes=0,
        max_logs=20,
    )

    event["correlated_logs"] = correlated["correlated_logs"]
    event["correlated_log_count"] = (
        correlated["correlated_log_count"]
    )

    return event

@router.post("/evaluate")
def evaluate_incidents(metrics: MetricsInput):
    """Evaluate a supplied metrics snapshot."""
    with processing_lock:
        try:
            events = manager.process_metrics(
                metrics.model_dump()
            )

            for event in events:
                repository.save(event["incident"])

            return {
                "events": events,
                "active_incidents": repository.list_active(),
            }

        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=str(exc),
            ) from exc


@router.get("")
def list_incidents():
    return {
        "incidents": repository.list_all()
    }


@router.get("/active")
def active_incidents():
    return {
        "incidents": repository.list_active()
    }


@router.post("/evaluate-live")
def evaluate_live_incidents():
    try:
        request_rate = get_request_rate()
        error_percent = get_error_rate()
        latency = get_average_latency()

        metrics = {
            "request_rate": request_rate,
            "error_rate": (
                error_percent / 100.0
                if error_percent is not None
                else None
            ),
            "average_latency_ms": latency,
        }

    except (httpx.HTTPError, ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Prometheus metrics temporarily unavailable",
        ) from exc

    # Read logs before modifying incident state.
    try:
        logs = read_jobtracker_logs()
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail="JobTracker logs temporarily unavailable",
        ) from exc

    with processing_lock:
        events = manager.process_metrics(metrics)

        for event in events:
            attach_log_evidence(event, logs)
            repository.save(event["incident"])

        return {
            "metrics": metrics,
            "events": events,
            "active_incidents": repository.list_active(),
        }

@router.get("/{incident_id}")
def get_incident(incident_id: str):
    incident = repository.get_by_id(incident_id)

    if incident is None:
        raise HTTPException(
            status_code=404,
            detail="Incident not found",
        )

    return incident
