"""Human-readable report projection."""

from __future__ import annotations

from .validation_release_frontier_exports import export_validation_release_report_markdown
from .validation_release_frontier_summary import ValidationReleaseSummary


def render_validation_release_report(summary: ValidationReleaseSummary) -> str:
    return export_validation_release_report_markdown(summary)


__all__ = ["render_validation_release_report"]
