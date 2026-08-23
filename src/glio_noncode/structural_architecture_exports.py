"""Stable bounded export helpers for structural architecture reports."""

from __future__ import annotations

from .serialization import canonical_json
from .structural_architecture_bundle import (
    render_structural_architecture_markdown,
    render_structural_architecture_review_csv,
)
from .structural_architecture_contracts import (
    StructuralArchitectureEvaluation,
    StructuralArchitectureRelease,
)


def export_structural_architecture_json(value: object) -> str:
    """Serialize a report without preserving Python implementation details."""

    to_dict = getattr(value, "to_dict", None)
    return canonical_json(to_dict() if callable(to_dict) else value)


def export_structural_architecture_review_csv(evaluation: StructuralArchitectureEvaluation) -> str:
    return render_structural_architecture_review_csv(evaluation)


def render_structural_architecture_release_markdown(release: StructuralArchitectureRelease) -> str:
    return render_structural_architecture_markdown(release)


__all__ = [
    "export_structural_architecture_json",
    "export_structural_architecture_review_csv",
    "render_structural_architecture_release_markdown",
]
