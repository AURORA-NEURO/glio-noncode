"""Public source closure registry."""

from .validation_beta_frontier_governance import ValidationBetaFrontierSourceRegistry, build_validation_beta_frontier_source_registry


def validation_beta_frontier_source_count(registry: ValidationBetaFrontierSourceRegistry) -> int:
    return len(registry.source_ids)


__all__ = ["ValidationBetaFrontierSourceRegistry", "build_validation_beta_frontier_source_registry", "validation_beta_frontier_source_count"]
