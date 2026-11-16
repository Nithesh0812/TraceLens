
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Severity(str, Enum):
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True)
class DetectionThresholds:
    warning_error_rate: float = 0.05
    critical_error_rate: float = 0.10

    warning_latency_ms: float = 500.0
    critical_latency_ms: float = 1000.0

    def __post_init__(self):
        if not (
            0 <= self.warning_error_rate
            < self.critical_error_rate <= 1
        ):
            raise ValueError("Invalid error-rate thresholds")

        if not (
            0 <= self.warning_latency_ms
            < self.critical_latency_ms
        ):
            raise ValueError("Invalid latency thresholds")


def evaluate_error_rate(
    error_rate: Optional[float],
    thresholds: DetectionThresholds,
) -> Optional[Severity]:
    if error_rate is None:
        return None

    if not 0 <= error_rate <= 1:
        raise ValueError("Error rate must be between 0 and 1")

    if error_rate >= thresholds.critical_error_rate:
        return Severity.CRITICAL

    if error_rate >= thresholds.warning_error_rate:
        return Severity.WARNING

    return Severity.NORMAL


def evaluate_latency(
    latency_ms: Optional[float],
    thresholds: DetectionThresholds,
) -> Optional[Severity]:
    if latency_ms is None:
        return None

    if latency_ms < 0:
        raise ValueError("Latency cannot be negative")

    if latency_ms >= thresholds.critical_latency_ms:
        return Severity.CRITICAL

    if latency_ms >= thresholds.warning_latency_ms:
        return Severity.WARNING

    return Severity.NORMAL
