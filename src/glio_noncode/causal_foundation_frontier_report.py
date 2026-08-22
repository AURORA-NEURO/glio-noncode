"""Human-readable reports derived from the deterministic release runtime."""

from __future__ import annotations

from .causal_foundation_frontier_runtime import CausalFoundationFrontierRuntimeReport


def render_causal_foundation_frontier_report(runtime: CausalFoundationFrontierRuntimeReport) -> str:
    lines = [
        "Causal foundation release report",
        f"run_id: {runtime.run_id}",
        f"accepted: {runtime.accepted}",
        f"fixture: {runtime.fixture.fixture_id}",
        f"records: {runtime.metrics.record_count}",
        f"positive_rows: {runtime.metrics.positive_count}",
        f"control_rows: {runtime.metrics.control_count}",
        f"retained: {runtime.review.retained_count}",
        f"review: {runtime.review.review_count}",
        f"blocked_or_abstained: {runtime.review.blocked_count}",
        f"quality_checks_passed: {runtime.gate.passed_count}/{len(runtime.gate.checks)}",
        f"depth_checks_passed: {runtime.depth.passed_count}/{runtime.depth.required_count}",
        f"release_state: {runtime.release.state.value}",
        f"artifact_count: {len(runtime.artifacts.artifacts)}",
        "limitations:",
        "- bounded proxies are not calibrated clinical probabilities",
        "- public aggregate evidence does not establish individual causality",
        "- foreign contexts remain quarantined",
    ]
    return "\n".join(lines) + "\n"


def render_causal_foundation_frontier_report_markdown(runtime: CausalFoundationFrontierRuntimeReport) -> str:
    lines = [
        "# Causal foundation release report",
        "",
        f"- Run: `{runtime.run_id}`",
        f"- Accepted: `{runtime.accepted}`",
        f"- Release state: `{runtime.release.state.value}`",
        f"- Records: `{runtime.metrics.record_count}` ({runtime.metrics.positive_count} positive, {runtime.metrics.control_count} control)",
        f"- Retained rows: `{runtime.review.retained_count}`",
        f"- Review rows: `{runtime.review.review_count}`",
        f"- Blocked or abstained rows: `{runtime.review.blocked_count}`",
        f"- Quality checks: `{runtime.gate.passed_count}/{len(runtime.gate.checks)}`",
        f"- Depth checks: `{runtime.depth.passed_count}/{runtime.depth.required_count}`",
        f"- Artifacts: `{len(runtime.artifacts.artifacts)}`",
        "",
        "## Operation metrics",
        "",
        "| Operation | Rows | Positive | Controls | State exact | Issue exact |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    lines.extend(f"| {item.operation} | {item.record_count} | {item.positive_count} | {item.control_count} | {item.state_matches} | {item.issue_matches} |" for item in runtime.metrics.operations)
    lines.extend(("", "## Limitations", "", "- Proxies are bounded research outputs, not calibrated clinical probabilities.", "- Public aggregate evidence does not establish individual causality.", "- Foreign contexts remain quarantined.", ""))
    return "\n".join(lines)


__all__ = ["render_causal_foundation_frontier_report", "render_causal_foundation_frontier_report_markdown"]
