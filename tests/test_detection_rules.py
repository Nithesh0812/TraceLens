
import pytest

from app.detection.rules import (
    DetectionThresholds,
    Severity,
    evaluate_error_rate,
    evaluate_latency,
)


@pytest.fixture
def thresholds():
    return DetectionThresholds()


@pytest.mark.parametrize(
    "value, expected",
    [
        (0.0, Severity.NORMAL),
        (0.04, Severity.NORMAL),
        (0.05, Severity.WARNING),
        (0.09, Severity.WARNING),
        (0.10, Severity.CRITICAL),
        (0.20, Severity.CRITICAL),
    ],
)
def test_error_rate(value, expected, thresholds):
    assert evaluate_error_rate(value, thresholds) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        (100, Severity.NORMAL),
        (499, Severity.NORMAL),
        (500, Severity.WARNING),
        (999, Severity.WARNING),
        (1000, Severity.CRITICAL),
        (2000, Severity.CRITICAL),
    ],
)
def test_latency(value, expected, thresholds):
    assert evaluate_latency(value, thresholds) == expected


def test_missing_metrics(thresholds):
    assert evaluate_error_rate(None, thresholds) is None
    assert evaluate_latency(None, thresholds) is None


def test_invalid_error_rate(thresholds):
    with pytest.raises(ValueError):
        evaluate_error_rate(-0.1, thresholds)

    with pytest.raises(ValueError):
        evaluate_error_rate(1.5, thresholds)


def test_invalid_latency(thresholds):
    with pytest.raises(ValueError):
        evaluate_latency(-100, thresholds)


def test_invalid_threshold_configuration():
    with pytest.raises(ValueError):
        DetectionThresholds(
            warning_error_rate=0.20,
            critical_error_rate=0.10,
        )
