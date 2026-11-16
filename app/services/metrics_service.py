
import math

from app.ingestion.prometheus_client import query_prometheus


# Ignore monitoring endpoints when measuring application traffic
EXCLUDED_PATHS = 'path!~"/metrics|/health/live|/health/ready"'


def extract_metric_value(data: dict) -> float | None:
    """Extract one numeric value from a Prometheus instant query."""
    results = data.get("result", [])

    if not results:
        return None

    value = float(results[0]["value"][1])

    if not math.isfinite(value):
        return None

    return value


def get_request_rate() -> float | None:
    """Return application requests per second over 5 minutes."""

    query = (
        "sum(rate("
        f"http_requests_total{{{EXCLUDED_PATHS}}}[5m]"
        "))"
    )

    data = query_prometheus(query)
    return extract_metric_value(data)


def get_error_rate() -> float | None:
    """Return the percentage of application requests with 5xx responses."""

    errors = (
        "sum(rate("
        f'http_requests_total{{{EXCLUDED_PATHS},status_code=~"5.."}}[5m]'
        "))"
    )

    total = (
        "sum(rate("
        f"http_requests_total{{{EXCLUDED_PATHS}}}[5m]"
        "))"
    )

    query = (
        f"100 * ({errors} or vector(0)) "
        f"/ clamp_min({total}, 1e-9)"
    )

    data = query_prometheus(query)
    return extract_metric_value(data)


def get_average_latency() -> float | None:
    """Return average request latency in milliseconds over 5 minutes."""

    duration_sum = (
        "sum(rate("
        f"http_request_duration_seconds_sum{{{EXCLUDED_PATHS}}}[5m]"
        "))"
    )

    duration_count = (
        "sum(rate("
        f"http_request_duration_seconds_count{{{EXCLUDED_PATHS}}}[5m]"
        "))"
    )

    query = (
        f"1000 * {duration_sum} "
        f"/ {duration_count}"
    )

    data = query_prometheus(query)
    return extract_metric_value(data)
