const API_BASE_URL = "/api";



export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}


async function handleApiError(
  response: Response
): Promise<never> {
  let detail = "";

  try {
    const body: unknown = await response.json();

    if (
      typeof body === "object" &&
      body !== null &&
      "detail" in body &&
      typeof body.detail === "string"
    ) {
      detail = body.detail;
    }
  } catch {
    // The server may return a non-JSON error.
  }

  const messages: Record<number, string> = {
    404: "The requested resource was not found.",
    409: "The investigation is missing or outdated. Run a new investigation first.",
    429: "Too many requests. Please try again later.",
    502: "The AI investigation provider failed.",
    503: "A required backend service is unavailable.",
  };

  throw new ApiError(
    response.status,
    detail || messages[response.status] ||
      `Request failed with status ${response.status}`
  );
}

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


export interface InvestigationReport {
  summary: string;
  possible_cause: string | null;
  confidence: "low" | "medium" | "high";
  evidence_ids: number[];
  next_steps: string[];
  insufficient_evidence: boolean;
}

export interface VerificationResult {
  report: InvestigationReport;
  citation_ids_valid: boolean;
  verified_evidence_ids: number[];
  warnings: string[];
  requires_human_review: boolean;
}

export interface FixProposal {
  title: string;
  description: string;
  rationale: string;
  confidence: "low" | "medium" | "high";
  risk_level: "low" | "medium" | "high";
  evidence_ids: number[];
  proposed_steps: string[];
  validation_steps: string[];
  rollback_steps: string[];
}

export interface FixProposalResult {
  incident_id: string;
  status: "proposed" | "needs_more_evidence";
  proposal: FixProposal | null;
  warnings: string[];
  requires_human_review: boolean;
}

export interface IncidentListResponse {
  incidents: Incident[];
  total: number;
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);

  if (!response.ok) {
    return handleApiError(response);
  }

  return response.json() as Promise<T>;
}



async function postJson<T>(
  path: string,
  signal?: AbortSignal
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    signal,
  });

  if (!response.ok) {
    return handleApiError(response);
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
  
  getInvestigation: async (
  incidentId: string,
  signal?: AbortSignal
): Promise<VerificationResult | null> => {
  const response = await fetch(
    `${API_BASE_URL}/incidents/${encodeURIComponent(incidentId)}/investigation`,
    { signal }
  );

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    return handleApiError(response);
  }

  return response.json() as Promise<VerificationResult>;
},

runInvestigation: (
  incidentId: string,
  signal?: AbortSignal
) =>
  postJson<VerificationResult>(
    `/incidents/${encodeURIComponent(incidentId)}/investigate`,
    signal
  ),


  getFixProposal: async (
    incidentId: string,
    signal?: AbortSignal
  ): Promise<FixProposalResult | null> => {
    const response = await fetch(
      `${API_BASE_URL}/incidents/${encodeURIComponent(incidentId)}/fix-proposal`,
      { signal }
    );

    if (response.status === 404) {
      return null;
    }

    if (!response.ok) {
      return handleApiError(response);
    }

    return response.json() as Promise<FixProposalResult>;
  },

  generateFixProposal: (
    incidentId: string,
    signal?: AbortSignal
  ) =>
    postJson<FixProposalResult>(
      `/incidents/${encodeURIComponent(incidentId)}/propose-fix`,
      signal
    ),

};