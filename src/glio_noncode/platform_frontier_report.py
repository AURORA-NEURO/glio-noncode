"""Human-readable report for platform frontier runtime outputs."""

from __future__ import annotations

from .platform_frontier_contracts import PlatformFrontierEvaluation, PlatformFrontierFixture
from .platform_frontier_metrics import measure_platform_frontier
from .platform_frontier_release import PlatformFrontierReleaseManifest


def render_platform_frontier_report(fixture: PlatformFrontierFixture, evaluation: PlatformFrontierEvaluation, release: PlatformFrontierReleaseManifest | None = None) -> str:
    metrics = measure_platform_frontier(evaluation)
    lines = ["# Platform frontier report", "", f"- Fixture: `{fixture.fixture_id}`", f"- Context: `{fixture.context_key}`", f"- Boundary: `{fixture.evidence_boundary}`", f"- Records: {metrics.record_count}", f"- Positive accepted: {metrics.accepted_count}", f"- Controls retained: {metrics.control_count}", f"- Checks: {metrics.passed_check_count}/{metrics.check_count}", f"- Release accepted: {release.accepted if release else 'not built'}", "", "## Operation states", "", "| Operation | Records | States | Issues |", "| --- | ---: | --- | --- |"]
    for item in metrics.operation_metrics:
        states = ", ".join(f"{key}={value}" for key, value in sorted(item.state_counts.items()))
        issues = ", ".join(f"{key}={value}" for key, value in sorted(item.issue_counts.items())) or "none"
        lines.append(f"| {item.operation.value} | {item.record_count} | {states} | {issues} |")
    lines.extend(("", "This is an aggregate operational receipt. It does not make a scientific or clinical claim."))
    return "\n".join(lines) + "\n"


__all__ = ["render_platform_frontier_report"]
