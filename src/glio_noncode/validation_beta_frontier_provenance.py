"""Public provenance graph facade."""

from .validation_beta_frontier_governance import ValidationBetaFrontierLineage, ValidationBetaFrontierLineageEdge, build_validation_beta_frontier_lineage


def validation_beta_frontier_provenance_node_count(lineage: ValidationBetaFrontierLineage) -> int:
    return len(lineage.node_ids)


__all__ = ["ValidationBetaFrontierLineage", "ValidationBetaFrontierLineageEdge", "build_validation_beta_frontier_lineage", "validation_beta_frontier_provenance_node_count"]
