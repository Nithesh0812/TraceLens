import os
import logging
import httpx

from threading import Lock

from fastapi import APIRouter, HTTPException,Query
from pydantic import BaseModel, Field

from app.detection.incident_manager import IncidentManager
from app.storage.incident_repository import IncidentRepository
from app.services.metrics_service import (get_request_rate,get_error_rate,get_average_latency,)
from app.ingestion.jobtracker_logs import read_jobtracker_logs
from app.detection.log_correlator import correlate_logs
from app.detection.incident_detector import Incident
from app.detection.rules import Severity
from app.investigation.context_builder import (InvestigationContextBuilder,IncidentNotFoundError,)
from app.investigation.llm_client import (LLMInvestigator,LLMInvestigationError,)
from app.investigation.evidence_verifier import (EvidenceVerifier,VerificationResult,)
from app.api.schemas import IncidentListResponse

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


@router.get("", response_model=IncidentListResponse)
def list_incidents(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    incidents = repository.list_all()

    return {
        "incidents": incidents[offset:offset + limit],
        "total": len(incidents),
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

            repository.save(
            incident=event["incident"],
            evidence=event.get("correlated_logs", []),
            )

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

    evidence = repository.list_evidence(incident_id)

    return {
        **incident,
        "correlated_logs": evidence,
        "correlated_log_count": len(evidence),
    }


@router.post(
    "/{incident_id}/investigate",
    response_model=VerificationResult,
)
def investigate_incident(incident_id: str):
    """
    Build context, investigate with an LLM,
    and verify the resulting report.
    """
    builder = InvestigationContextBuilder(repository)

    try:
        context = builder.build(incident_id)
    except IncidentNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Incident not found",
        ) from exc

    investigator = LLMInvestigator()

    try:
        report = investigator.investigate(context)
    except LLMInvestigationError as exc:
        message = str(exc)

        if "not configured" in message:
            raise HTTPException(
                status_code=503,
                detail="LLM provider is not configured",
            ) from exc

        raise HTTPException(
            status_code=502,
            detail="LLM investigation failed",
        ) from exc

    verifier = EvidenceVerifier()

    try:
        result = verifier.verify(report, context)
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="Investigation verification failed",
        ) from exc

    repository.save_investigation(
    incident_id=incident_id,
    report=result.model_dump(mode="json"),
    )

    return result

@router.get("/{incident_id}/investigation")
def get_saved_investigation(incident_id: str):
    """Retrieve a previously verified AI investigation."""

    incident = repository.get_by_id(incident_id)

    if incident is None:
        raise HTTPException(
            status_code=404,
            detail="Incident not found",
        )

    investigation = repository.get_investigation(
        incident_id
    )

    if investigation is None:
        raise HTTPException(
            status_code=404,
            detail="No investigation found for this incident",
        )

    return investigation
