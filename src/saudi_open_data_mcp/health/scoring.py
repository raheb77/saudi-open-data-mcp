"""Health scoring scaffold."""

from .models import HealthReport, HealthStatus


def score_health(report: HealthReport) -> int:
    """Return a deterministic placeholder score."""

    if report.status is HealthStatus.OK:
        return 100
    if report.status is HealthStatus.WARN:
        return 50
    return 0
