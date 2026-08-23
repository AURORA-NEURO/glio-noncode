"""Declared negative-boundary probes."""

from .validation_beta_frontier_governance import ValidationBetaFrontierFailureInjectionReport, ValidationBetaFrontierFailureProbe, run_validation_beta_frontier_failure_injections


def validation_beta_frontier_probe_count(report: ValidationBetaFrontierFailureInjectionReport) -> int:
    return len(report.probes)


__all__ = ["ValidationBetaFrontierFailureInjectionReport", "ValidationBetaFrontierFailureProbe", "run_validation_beta_frontier_failure_injections", "validation_beta_frontier_probe_count"]
