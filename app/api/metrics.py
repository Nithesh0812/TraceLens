
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx

from app.services.metrics_service import (
    get_request_rate,
    get_error_rate,
    get_average_latency,
)

router = APIRouter(
    prefix="/metrics",
    tags=["Metrics"],
)


class MetricsSummary(BaseModel):
    request_rate: float | None
    error_rate: float | None
    average_latency_ms: float | None


@router.get("/summary", response_model=MetricsSummary)
def get_metrics_summary():
    try:
        return MetricsSummary(
            request_rate=get_request_rate(),
            error_rate=get_error_rate(),
            average_latency_ms=get_average_latency(),
        )
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Prometheus metrics temporarily unavailable",
        ) from exc
