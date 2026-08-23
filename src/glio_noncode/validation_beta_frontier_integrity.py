"""Integrity checks for the fixture and execution results."""

from .validation_beta_frontier_governance import ValidationBetaFrontierIntegrityReport, evaluate_validation_beta_frontier_integrity


def validation_beta_frontier_integrity_is_closed(report: ValidationBetaFrontierIntegrityReport) -> bool:
    return report.accepted and report.unique_record_addresses and report.unique_result_addresses and report.source_closure


__all__ = ["ValidationBetaFrontierIntegrityReport", "evaluate_validation_beta_frontier_integrity", "validation_beta_frontier_integrity_is_closed"]
