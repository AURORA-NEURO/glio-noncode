"""Reviewer-facing reports for whole-product release assurance."""

from __future__ import annotations

from .release_assurance_runtime import ReleaseAssuranceRuntimeReport
from .release_assurance_support import canonical_payload, csv_payload, public_value
from .release_assurance_summary import release_assurance_status


def release_assurance_report_rows(runtime: ReleaseAssuranceRuntimeReport) -> tuple[dict[str, object], ...]:
    """Return one stable row per runtime stage for CSV or table consumers."""

    return tuple(
        {
            "ordinal": item.ordinal,
            "stage_id": item.stage_id,
            "state": item.state,
            "input_address": item.input_address,
            "output_address": item.output_address,
            "detail": item.detail,
            "content_address": item.content_address,
        }
        for item in runtime.stages
    )


def export_release_assurance_report_json(runtime: ReleaseAssuranceRuntimeReport) -> bytes:
    """Export a canonical public runtime report."""

    return canonical_payload(runtime.to_dict())


def export_release_assurance_report_csv(runtime: ReleaseAssuranceRuntimeReport) -> bytes:
    """Export the ordered runtime stages as deterministic CSV."""

    return csv_payload(release_assurance_report_rows(runtime))


def render_release_assurance_report_markdown(runtime: ReleaseAssuranceRuntimeReport) -> bytes:
    """Render a compact but detailed reviewer report."""

    status = release_assurance_status(runtime.snapshot)
    lines = [
        "# GLIO-NONCODE whole-product release assurance",
        "",
        f"- Bundle: `{runtime.snapshot.bundle_id}`",
        f"- Run: `{runtime.run_id}`",
        f"- State: `{runtime.state}`",
        f"- Accepted: `{runtime.accepted}`",
        f"- Overall readiness: `{status['overall_percent']}%`",
        f"- Snapshot: `{runtime.snapshot.content_address}`",
        f"- Runtime: `{runtime.content_address}`",
        "",
        "## Denominators",
        "",
        "| Plane | Rows | Accepted | Readiness |",
        "| --- | ---: | ---: | ---: |",
    ]
    for domain in runtime.snapshot.domains:
        lines.append(
            f"| {domain.domain_id} | {domain.denominator} | {domain.accepted_count} | {domain.readiness_percent}% |"
        )
    lines.extend((
        "",
        "## Runtime stages",
        "",
        "| # | Stage | State | Input | Output |",
        "| ---: | --- | --- | --- | --- |",
    ))
    for stage in runtime.stages:
        lines.append(
            f"| {stage.ordinal} | {stage.stage_id} | {stage.state} | `{stage.input_address}` | `{stage.output_address}` |"
        )
    lines.extend((
        "",
        "## Replay",
        "",
        f"- First address: `{runtime.replay.first_address}`",
        f"- Second address: `{runtime.replay.second_address}`",
        f"- Expected address: `{runtime.replay.expected_address}`",
        f"- Deterministic: `{runtime.replay.deterministic}`",
        "",
        "## Boundary",
        "",
        "This report contains aggregate readiness, counters, checks, and content addresses only.",
        "",
    ))
    payload = "\n".join(lines).encode("utf-8")
    public_value({"runtime": runtime.to_dict(), "status": status})
    return payload


def report_release_assurance_text(runtime: ReleaseAssuranceRuntimeReport) -> str:
    """Return the Markdown report as text for local callers."""

    return render_release_assurance_report_markdown(runtime).decode("utf-8")


__all__ = [
    "export_release_assurance_report_csv",
    "export_release_assurance_report_json",
    "release_assurance_report_rows",
    "render_release_assurance_report_markdown",
    "report_release_assurance_text",
]
