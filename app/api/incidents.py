
import os
from threading import Lock

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.detection.incident_manager import IncidentManager
from app.storage.incident_repository import IncidentRepository


import httpx

from app.services.metrics_service import (
    get_request_rate,
    get_error_rate,
    get_average_latency,
)

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
    """
    Fetch metrics from Prometheus,
    detect incidents, and persist lifecycle changes.
    """

    try:
        metrics = {
            "request_rate": get_request_rate(),
            "error_rate": get_error_rate(),
            "average_latency_ms": get_average_latency(),
        }
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Prometheus metrics temporarily unavailable",
        ) from exc

    with processing_lock:
        events = manager.process_metrics(metrics)

        for event in events:
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
