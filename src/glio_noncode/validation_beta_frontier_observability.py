"""Structured runtime event projections."""

from .validation_beta_frontier_governance import ValidationBetaFrontierObservabilityEvent, ValidationBetaFrontierObservabilityReport, observe_validation_beta_frontier


def validation_beta_frontier_event_kinds(report: ValidationBetaFrontierObservabilityReport) -> tuple[str, ...]:
    return tuple(item.event_kind for item in report.events)


__all__ = ["ValidationBetaFrontierObservabilityEvent", "ValidationBetaFrontierObservabilityReport", "observe_validation_beta_frontier", "validation_beta_frontier_event_kinds"]
