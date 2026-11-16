const API_BASE_URL = "/api";

export interface MetricsSummary {
  request_rate: number | null;
  error_rate: number | null;
  average_latency_ms: number | null;
}

export interface Incident {
  id: string;
  incident_type: string;
  severity: string;
  status: string;
  message: string;
  metric_value: number;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
  occurrences: number;
}


export interface IncidentEvidence {
  id: number;
  incident_id: string;
  timestamp: string;
  level: string;
  message: string;
  seconds_from_incident: number;
}

export interface IncidentDetails extends Incident {
  correlated_logs: IncidentEvidence[];
  correlated_log_count: number;
}

export interface IncidentListResponse {
  incidents: Incident[];
  total: number;
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export const api = {
  getMetrics: () =>
    getJson<MetricsSummary>("/metrics/summary"),

  getIncidents: (limit = 20, offset = 0) =>
    getJson<IncidentListResponse>(
      `/incidents?limit=${limit}&offset=${offset}`
    ),

  getIncident: (id: string) =>
    getJson<IncidentDetails>(
      `/incidents/${encodeURIComponent(id)}`
    ),
};