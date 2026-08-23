"""Consumer disposition matrix."""

from .validation_beta_frontier_governance import ValidationBetaFrontierOperationalCell, ValidationBetaFrontierOperationalMatrix, build_validation_beta_frontier_operational_matrix


def validation_beta_frontier_publish_cells(matrix: ValidationBetaFrontierOperationalMatrix) -> tuple[ValidationBetaFrontierOperationalCell, ...]:
    return tuple(item for item in matrix.cells if item.disposition == "publish")


__all__ = ["ValidationBetaFrontierOperationalCell", "ValidationBetaFrontierOperationalMatrix", "build_validation_beta_frontier_operational_matrix", "validation_beta_frontier_publish_cells"]
