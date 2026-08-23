"""Operator runbook facade."""

from .validation_beta_frontier_governance import ValidationBetaFrontierRunbook, ValidationBetaFrontierRunbookStep, build_validation_beta_frontier_runbook


def validation_beta_frontier_runbook_commands(runbook: ValidationBetaFrontierRunbook) -> tuple[str, ...]:
    return tuple(item.command for item in runbook.steps)


__all__ = ["ValidationBetaFrontierRunbook", "ValidationBetaFrontierRunbookStep", "build_validation_beta_frontier_runbook", "validation_beta_frontier_runbook_commands"]
