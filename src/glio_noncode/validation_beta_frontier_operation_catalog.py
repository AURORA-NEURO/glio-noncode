"""Operation catalog with capability and consumer metadata."""

from typing import Any

from .validation_beta_frontier_public_data import ValidationBetaFrontierOperation


def default_validation_beta_frontier_operation_catalog() -> tuple[dict[str, Any], ...]:
    labels = {ValidationBetaFrontierOperation.CRISPR_DESIGN: "CRISPRi/CRISPRa design", ValidationBetaFrontierOperation.BASE_EDITING: "base-editing design", ValidationBetaFrontierOperation.PRIME_EDITING: "prime-editing design", ValidationBetaFrontierOperation.ALLELE_REPORTER: "allele-specific reporter", ValidationBetaFrontierOperation.MODEL_ELIGIBILITY: "model-system eligibility", ValidationBetaFrontierOperation.GUIDE_OLIGO: "guide/oligo adaptation", ValidationBetaFrontierOperation.CONTROLS_RANDOMIZATION: "controls and randomization", ValidationBetaFrontierOperation.POWER_REPLICATION: "power and replication"}
    return tuple({"operation": operation.value, "capability_id": f"GNC-D13-C{index:02d}", "label": labels[operation], "research_only": True} for index, operation in enumerate(ValidationBetaFrontierOperation, start=5))


__all__ = ["default_validation_beta_frontier_operation_catalog"]
