
import pytest

from app.services import metrics_service


@pytest.fixture
def mock_metric_query(monkeypatch):
    def _mock(value):
        def fake_query(query):
            if value is None:
                return {
                    "resultType": "vector",
                    "result": [],
                }

            return {
                "resultType": "vector",
                "result": [
                    {
                        "metric": {},
                        "value": [1794783220, str(value)],
                    }
                ],
            }

        monkeypatch.setattr(
            metrics_service,
            "query_prometheus",
            fake_query,
        )

    return _mock


def test_get_request_rate(mock_metric_query):
    mock_metric_query(2.5)

    result = metrics_service.get_request_rate()

    assert result == 2.5


def test_get_error_rate(mock_metric_query):
    mock_metric_query(5.0)

    result = metrics_service.get_error_rate()

    assert result == 5.0


def test_get_average_latency(mock_metric_query):
    mock_metric_query(150.0)

    result = metrics_service.get_average_latency()

    assert result == 150.0


def test_empty_metric_result(mock_metric_query):
    mock_metric_query(None)

    result = metrics_service.get_request_rate()

    assert result is None


def test_zero_error_rate(mock_metric_query):
    mock_metric_query(0.0)

    result = metrics_service.get_error_rate()

    assert result == 0.0


def test_invalid_metric_value(mock_metric_query):
    mock_metric_query("NaN")

    result = metrics_service.get_average_latency()

    assert result is None

def test_metrics_service_promql_queries(monkeypatch):
    captured_queries = []

    def fake_query(query):
        captured_queries.append(query)
        return {
            "resultType": "vector",
            "result": [
                {
                    "metric": {},
                    "value": [1794783220, "1.0"],
                }
            ],
        }

    monkeypatch.setattr(
        metrics_service,
        "query_prometheus",
        fake_query,
    )

    metrics_service.get_request_rate()
    metrics_service.get_error_rate()
    metrics_service.get_average_latency()

    assert len(captured_queries) == 3

    assert "http_requests_total" in captured_queries[0]
    assert 'status_code=~"5.."' in captured_queries[1]
    assert "http_request_duration_seconds_sum" in captured_queries[2]
    assert "http_request_duration_seconds_count" in captured_queries[2]

    for query in captured_queries:
        assert 'path!~"/metrics|/health/live|/health/ready"' in query
        assert "[5m]" in query
