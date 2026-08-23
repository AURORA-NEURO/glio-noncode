"""Human-readable execution transcript."""

from .validation_beta_frontier_runtime import ValidationBetaFrontierRuntimeReport


def render_validation_beta_frontier_transcript(report: ValidationBetaFrontierRuntimeReport) -> str:
    lines = [f"run={report.run_id}", f"accepted={str(report.accepted).lower()}", f"fixture={report.fixture.fixture_id}"]
    lines.extend(f"{stage.sequence:02d} {stage.stage_id} {str(stage.accepted).lower()} {stage.detail}" for stage in report.stages)
    lines.append(f"release={report.release.state}")
    return "\n".join(lines) + "\n"


__all__ = ["render_validation_beta_frontier_transcript"]
