import { useEffect, useState } from "react";
import { api, type IncidentListResponse } from "./services/api";

function App() {
  const [data, setData] = useState<IncidentListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getIncidents()
      .then(setData)
      .catch((err: unknown) => {
        setError(
          err instanceof Error ? err.message : "Unknown error"
        );
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="min-h-screen bg-slate-950 p-8 text-white">
      <div className="mx-auto max-w-6xl">
        <h1 className="text-4xl font-bold">TraceLens</h1>
        <p className="mt-2 text-slate-400">
          AI-powered observability and incident investigation
        </p>

        <section className="mt-10 rounded-xl border border-slate-800 bg-slate-900 p-6">
          <h2 className="text-xl font-semibold">
            Incident Overview
          </h2>

          {loading && (
            <p className="mt-4">Loading incidents...</p>
          )}

          {error && (
            <p className="mt-4 text-red-400">{error}</p>
          )}

          {data && (
            <>
              <p className="mt-4 text-slate-400">
                Total incidents: {data.total}
              </p>

              <div className="mt-6 space-y-3">
                {data.incidents.map((incident) => (
                  <div
                    key={incident.id}
                    className="rounded-lg border border-slate-700 p-4"
                  >
                    <div className="flex items-center justify-between gap-4">
                      <h3 className="font-medium">
                        {incident.incident_type.replaceAll("_", " ")}
                      </h3>

                      <span
                        className={
                          incident.status === "active"
                            ? "text-red-400"
                            : "text-green-400"
                        }
                      >
                        {incident.status}
                      </span>
                    </div>

                    <p className="mt-2 text-sm text-slate-400">
                      {incident.message}
                    </p>

                    <p className="mt-2 text-xs text-slate-500">
                      Severity: {incident.severity}
                    </p>
                  </div>
                ))}

                {data.incidents.length === 0 && (
                  <p className="text-slate-400">
                    No incidents detected.
                  </p>
                )}
              </div>
            </>
          )}
        </section>
      </div>
    </main>
  );
}

export default App;