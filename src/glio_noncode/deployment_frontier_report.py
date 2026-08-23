"""Markdown report rendering for deployment frontier evidence."""

from __future__ import annotations

from .deployment_frontier_summary import DeploymentFrontierSummary


def render_deployment_frontier_report(summary: DeploymentFrontierSummary) -> str:
    lines = [
        "# Deployment Frontier Report",
        "",
        f"- Fixture: `{summary.fixture_id}`",
        f"- Release: `{summary.release_id}`",
        f"- Accepted: `{str(summary.accepted).lower()}`",
        f"- Records: `{summary.record_count}`",
        f"- Checks: `{summary.passed_checks}/{summary.check_count}`",
        "",
        "## States",
        "",
    ]
    lines.extend(f"- `{key}`: {value}" for key, value in sorted(summary.state_counts.items()))
    lines.extend(["", "## Issues", ""])
    lines.extend(f"- `{key}`: {value}" for key, value in sorted(summary.issue_counts.items()))
    return "\n".join(lines) + "\n"


__all__ = ["render_deployment_frontier_report"]
