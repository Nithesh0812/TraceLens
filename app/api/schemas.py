
from datetime import datetime

from pydantic import BaseModel, Field


class IncidentSummary(BaseModel):
    id: str
    incident_type: str
    severity: str
    status: str
    message: str
    metric_value: float
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None
    occurrences: int


class IncidentListResponse(BaseModel):
    incidents: list[IncidentSummary]
    total: int


class IncidentEvidence(BaseModel):
    id: int
    incident_id: str
    timestamp: datetime
    level: str
    message: str
    seconds_from_incident: float


class IncidentDetailResponse(IncidentSummary):
    correlated_logs: list[IncidentEvidence] = Field(
        default_factory=list
    )
    correlated_log_count: int = 0
