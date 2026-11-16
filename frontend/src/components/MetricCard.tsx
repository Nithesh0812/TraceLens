
type MetricCardProps = {
  title: string;
  value: string | number;
  unit?: string;
  description?: string;
  status?: "normal" | "warning" | "critical";
};

export default function MetricCard({
  title,
  value,
  unit,
  description,
  status = "normal",
}: MetricCardProps) {
  const colors = {
    normal: "text-white",
    warning: "text-amber-400",
    critical: "text-red-400",
  };

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-5 shadow-sm">
      <p className="text-sm font-medium text-slate-400">
        {title}
      </p>

      <div className="mt-3 flex flex-wrap items-baseline gap-2">
        <span
          className={`text-3xl font-bold tracking-tight ${colors[status]}`}
        >
          {value}
        </span>

        {unit && (
          <span className="text-sm text-slate-500">
            {unit}
          </span>
        )}
      </div>

      {description && (
        <p className="mt-3 text-xs text-slate-500">
          {description}
        </p>
      )}
    </div>
  );
}
