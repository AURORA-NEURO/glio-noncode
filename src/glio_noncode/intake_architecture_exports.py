"""JSON, CSV, and Markdown projections for D01 review and release."""

from __future__ import annotations

import json

from .intake_architecture_contracts import IntakeArchitectureRuntime
from .intake_architecture_review import intake_review_csv


def intake_architecture_runtime_json(runtime: IntakeArchitectureRuntime) -> str:
    return json.dumps(runtime.to_dict(), indent=2, sort_keys=True) + "\n"


def intake_architecture_quality_json(report) -> str:
    return json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"


def intake_architecture_report_markdown(runtime: IntakeArchitectureRuntime) -> str:
    positive = sum(item.scenario.value == "positive" for item in runtime.evaluation.results)
    held = len(runtime.review_queue.items)
    lines = [
        "# D01 Variant Identity and Intake Architecture",
        "",
        "This report is a deterministic public-aggregate intake receipt.",
        "",
        f"- Runtime state: `{runtime.state.value}`",
        f"- Fixture: `{runtime.fixture_id}`",
        f"- Cases: `{len(runtime.evaluation.results)}` ({positive} positive, {held} held controls)",
        f"- Stages: `{len(runtime.stages)}`",
        f"- Artifacts: `{len(runtime.artifacts)}` offline-capable",
        f"- Release: `{runtime.release.version}` / `{runtime.release.state.value}`",
        "",
        "No subject-level fields or clinical interpretation are represented by this receipt.",
        "",
    ]
    return "\n".join(lines)


__all__ = ["intake_architecture_runtime_json", "intake_architecture_quality_json", "intake_architecture_report_markdown", "intake_review_csv"]
