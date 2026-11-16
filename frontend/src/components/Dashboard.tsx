
import { useCallback, useEffect, useRef, useState } from "react";

import MetricCard from "./MetricCard";
import {
  api,
  type MetricsSummary,
  type IncidentListResponse,
} from "../services/api";

const REFRESH_INTERVAL_MS = 10_000;

export default function Dashboard() {
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null);
  const [incidentData, setIncidentData] =
    useState<IncidentListResponse | null>(null);

  const [metricsError, setMetricsError] = useState<string | null>(null);
  const [incidentsError, setIncidentsError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const mounted = useRef(true);
  const inFlight = useRef(false);

  const refreshData = useCallback(async () => {
    if (inFlight.current) return;

    inFlight.current = true;
    if (mounted.current) setRefreshing(true);

    try {
      const [metricsResult, incidentsResult] =
        await Promise.allSettled([
          api.getMetrics(),
          api.getIncidents(100, 0),
        ]);

      if (!mounted.current) return;

      if (metricsResult.status === "fulfilled") {
        setMetrics(metricsResult.value);
        setMetricsError(null);
      } else {
        setMetricsError("Unable to retrieve Prometheus metrics.");
      }

      if (incidentsResult.status === "fulfilled") {
        setIncidentData(incidentsResult.value);
        setIncidentsError(null);
      } else {
        setIncidentsError("Unable to retrieve incidents.");
      }

      if (
        metricsResult.status === "fulfilled" ||
        incidentsResult.status === "fulfilled"
      ) {
        setLastUpdated(new Date());
      }
    } finally {
      inFlight.current = false;

      if (mounted.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    void refreshData();

    const interval = window.setInterval(() => {
      void refreshData();
    }, REFRESH_INTERVAL_MS);

    return () => {
      mounted.current = false;
      window.clearInterval(interval);
    };
  }, [refreshData]);

  const incidents = incidentData?.incidents ?? [];

  const activeCount = incidents.filter(
    (incident) => incident.status === "active"
  ).length;

  const resolvedCount = incidents.filter(
    (incident) => incident.status === "resolved"
  ).length;

  const criticalCount = incidents.filter(
    (incident) =>
      incident.status === "active" &&
      incident.severity === "critical"
  ).length;

  const formatMetric = (value: number | null | undefined) =>
    value == null ? "N/A" : value.toFixed(2);

  const monitoringStatus =
    metricsError && incidentsError
      ? "Disconnected"
      : metricsError || incidentsError
        ? "Degraded"
        : loading
          ? "Connecting"
          : "Connected";

  const statusColor =
    monitoringStatus === "Connected"
      ? "text-emerald-400"
      : monitoringStatus === "Disconnected"
        ? "text-red-400"
        : "text-amber-400";

  return (
    <main className="min-h-screen bg-slate-950 px-5 py-8 text-white md:px-10">
      <div className="mx-auto max-w-7xl space-y-8">

        {/* Header */}
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">
              TraceLens
            </h1>
            <p className="mt-1 text-sm text-slate-400">
              AI-powered observability and incident investigation
            </p>
          </div>

          <div className="flex items-center gap-4">
            <div className="text-right text-xs">
              <p className={statusColor}>
                {monitoringStatus}
              </p>
              <p className="mt-1 text-slate-500">
                Updated: {lastUpdated
                  ? lastUpdated.toLocaleTimeString()
                  : "Never"}
              </p>
            </div>

            <button
              type="button"
              onClick={() => void refreshData()}
              disabled={refreshing}
              className="rounded-lg border border-slate-700 px-4 py-2 text-sm font-medium transition hover:bg-slate-800 disabled:opacity-50"
            >
              {refreshing ? "Refreshing..." : "Refresh"}
            </button>
          </div>
        </header>

        {loading && (
          <p className="text-sm text-slate-400">
            Loading dashboard data...
          </p>
        )}

        {/* Live metrics */}
        <section>
          <h2 className="mb-4 text-lg font-semibold">
            Live Metrics
          </h2>

          {metricsError && (
            <p role="alert" className="mb-4 text-sm text-amber-400">
              {metricsError}
              {metrics && " Showing last available values."}
            </p>
          )}

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <MetricCard
              title="Request Rate"
              value={formatMetric(metrics?.request_rate)}
              unit="req/s"
              description="Average over the past 5 minutes"
            />

            <MetricCard
              title="HTTP 5xx Error Rate"
              value={
                metrics?.error_rate == null
                  ? "N/A"
                  : `${metrics.error_rate.toFixed(2)}%`
              }
              description="Percentage of requests returning 5xx"
            />

            <MetricCard
              title="Average Latency"
              value={formatMetric(metrics?.average_latency_ms)}
              unit="ms"
              description="Average over the past 5 minutes"
            />
          </div>
        </section>

        {/* Incident statistics */}
        <section>
          <h2 className="mb-4 text-lg font-semibold">
            Incident Statistics
          </h2>

          {incidentsError && (
            <p role="alert" className="mb-4 text-sm text-amber-400">
              {incidentsError}
              {incidentData && " Showing last available incidents."}
            </p>
          )}

          {incidentData && incidentData.total > incidents.length && (
            <p className="mb-4 text-sm text-amber-400">
              Status counts cover the latest {incidents.length} of{" "}
              {incidentData.total} incidents.
            </p>
          )}

          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <MetricCard
              title="Total Incidents"
              value={incidentData?.total ?? "N/A"}
            />

            <MetricCard
              title="Active"
              value={incidentData ? activeCount : "N/A"}
              status={activeCount > 0 ? "warning" : "normal"}
            />

            <MetricCard
              title="Resolved"
              value={incidentData ? resolvedCount : "N/A"}
            />

            <MetricCard
              title="Critical Active"
              value={incidentData ? criticalCount : "N/A"}
              status={criticalCount > 0 ? "critical" : "normal"}
            />
          </div>
        </section>

        {/* Incident overview */}
        <section className="rounded-xl border border-slate-800 bg-slate-900 p-6">
          <div className="mb-5 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-lg font-semibold">
              Recent Incidents
            </h2>
            <span className="text-xs text-slate-500">
              Latest {incidents.length} incidents
            </span>
          </div>

          {!incidentData && !loading && (
            <p className="text-sm text-slate-400">
              Incident data is unavailable.
            </p>
          )}

          {incidentData && incidents.length === 0 && (
            <p className="text-sm text-slate-400">
              No incidents detected.
            </p>
          )}

          <div className="space-y-3">
            {incidents.map((incident) => (
              <div
                key={incident.id}
                className="rounded-lg border border-slate-800 bg-slate-950 p-4"
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <h3 className="font-medium capitalize">
                    {incident.incident_type.replaceAll("_", " ")}
                  </h3>

                  <span
                    className={`rounded-full px-3 py-1 text-xs font-medium ${
                      incident.status === "active"
                        ? "bg-red-500/10 text-red-400"
                        : "bg-emerald-500/10 text-emerald-400"
                    }`}
                  >
                    {incident.status}
                  </span>
                </div>

                <p className="mt-2 text-sm text-slate-400">
                  {incident.message}
                </p>

                <div className="mt-3 flex flex-wrap gap-4 text-xs text-slate-500">
                  <span>Severity: {incident.severity}</span>
                  <span>
                    Detected: {new Date(
                      incident.created_at
                    ).toLocaleString()}
                  </span>
                  <span>
                    Occurrences: {incident.occurrences}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </section>

        <footer className="text-center text-xs text-slate-600">
          TraceLens · Automatically refreshes every 10 seconds
        </footer>
      </div>
    </main>
  );
}
