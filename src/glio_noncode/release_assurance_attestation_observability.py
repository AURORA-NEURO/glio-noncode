"""Deterministic aggregate metrics for release-assurance attestations."""

from __future__ import annotations

from typing import Any

from .release_assurance_attestation_contracts import (
    RELEASE_ASSURANCE_ATTESTATION_OBSERVABILITY_VERSION,
    ReleaseAssuranceAttestation,
    ReleaseAssuranceAttestationMetric,
    ReleaseAssuranceAttestationObservability,
    ReleaseAssuranceAttestationRuntimeReport,
)
from .release_assurance_support import forbidden_keys
from .serialization import content_hash, jsonable


def _metric(
    metric_id: str,
    component_id: str,
    name: str,
    value: int | float,
    unit: str,
    source_address: str,
) -> ReleaseAssuranceAttestationMetric:
    body = {
        "metric_id": metric_id,
        "component_id": component_id,
        "name": name,
        "value": value,
        "unit": unit,
        "source_address": source_address,
    }
    return ReleaseAssuranceAttestationMetric(
        **body,
        content_address=content_hash(body, prefix="release-assurance-attestation-metric"),
    )


def build_release_assurance_attestation_observability(
    value: ReleaseAssuranceAttestation,
    runtime: ReleaseAssuranceAttestationRuntimeReport | None = None,
) -> ReleaseAssuranceAttestationObservability:
    """Build conserved component, check, category, and runtime metrics."""

    metrics: list[ReleaseAssuranceAttestationMetric] = []
    for component in value.components:
        metrics.extend(
            (
                _metric(
                    f"component:{component.component_id}:observed",
                    component.component_id,
                    "observed_count",
                    component.observed_count,
                    "count",
                    component.source_address,
                ),
                _metric(
                    f"component:{component.component_id}:expected",
                    component.component_id,
                    "expected_count",
                    component.expected_count,
                    "count",
                    component.source_address,
                ),
                _metric(
                    f"component:{component.component_id}:readiness",
                    component.component_id,
                    "readiness_percent",
                    component.readiness_percent,
                    "percent",
                    component.content_address,
                ),
            )
        )
    metrics.extend(
        (
            _metric(
                "attestation:component-count",
                "cross-plane",
                "component_count",
                value.component_count,
                "count",
                value.content_address,
            ),
            _metric(
                "attestation:check-count",
                "cross-plane",
                "check_count",
                value.check_count,
                "count",
                value.content_address,
            ),
            _metric(
                "attestation:passed-check-count",
                "cross-plane",
                "passed_check_count",
                value.passed_check_count,
                "count",
                value.content_address,
            ),
            _metric(
                "attestation:failed-check-count",
                "cross-plane",
                "failed_check_count",
                value.check_count - value.passed_check_count,
                "count",
                value.content_address,
            ),
            _metric(
                "attestation:overall-percent",
                "cross-plane",
                "overall_percent",
                value.overall_percent,
                "percent",
                value.content_address,
            ),
        )
    )
    for category in sorted({item.category for item in value.checks}):
        rows = tuple(item for item in value.checks if item.category == category)
        metrics.extend(
            (
                _metric(
                    f"category:{category}:check-count",
                    "cross-plane",
                    f"{category}_check_count",
                    len(rows),
                    "count",
                    value.content_address,
                ),
                _metric(
                    f"category:{category}:passed-count",
                    "cross-plane",
                    f"{category}_passed_count",
                    sum(item.passed for item in rows),
                    "count",
                    value.content_address,
                ),
            )
        )
    if runtime is not None:
        metrics.extend(
            (
                _metric(
                    "runtime:stage-count",
                    "runtime",
                    "stage_count",
                    len(runtime.stages),
                    "count",
                    runtime.content_address,
                ),
                _metric(
                    "runtime:ready-stage-count",
                    "runtime",
                    "ready_stage_count",
                    sum(item.state.value == "ready" for item in runtime.stages),
                    "count",
                    runtime.content_address,
                ),
                _metric(
                    "runtime:blocked-stage-count",
                    "runtime",
                    "blocked_stage_count",
                    sum(item.state.value == "blocked" for item in runtime.stages),
                    "count",
                    runtime.content_address,
                ),
                _metric(
                    "runtime:replay-deterministic",
                    "runtime",
                    "replay_deterministic",
                    int(runtime.replay.deterministic),
                    "boolean",
                    runtime.replay.content_address,
                ),
            )
        )
    metric_tuple = tuple(metrics)
    accepted = (
        len(metric_tuple) >= 14
        and len({item.metric_id for item in metric_tuple}) == len(metric_tuple)
        and all(item.value >= 0 for item in metric_tuple if isinstance(item.value, (int, float)))
        and not forbidden_keys(jsonable(metric_tuple))
    )
    body = {
        "attestation_id": value.attestation_id,
        "metrics": metric_tuple,
        "accepted": accepted,
    }
    return ReleaseAssuranceAttestationObservability(
        value.attestation_id,
        metric_tuple,
        accepted,
        content_hash(body, prefix=RELEASE_ASSURANCE_ATTESTATION_OBSERVABILITY_VERSION),
    )


def audit_release_assurance_attestation_observability(
    value: ReleaseAssuranceAttestationObservability,
    attestation: ReleaseAssuranceAttestation,
) -> tuple[dict[str, Any], ...]:
    """Audit metric uniqueness and conservation against the source attestation."""

    rows = {item.metric_id: item for item in value.metrics}
    checks = (
        {
            "check_id": "observability:attestation-id",
            "passed": value.attestation_id == attestation.attestation_id,
            "observed": value.attestation_id,
            "expected": attestation.attestation_id,
        },
        {
            "check_id": "observability:unique-metrics",
            "passed": len(rows) == len(value.metrics),
            "observed": len(rows),
            "expected": len(value.metrics),
        },
        {
            "check_id": "observability:component-count",
            "passed": rows.get("attestation:component-count", _zero()).value
            == attestation.component_count,
            "observed": rows.get("attestation:component-count", _zero()).value,
            "expected": attestation.component_count,
        },
        {
            "check_id": "observability:check-count",
            "passed": rows.get("attestation:check-count", _zero()).value == attestation.check_count,
            "observed": rows.get("attestation:check-count", _zero()).value,
            "expected": attestation.check_count,
        },
        {
            "check_id": "observability:passed-count",
            "passed": rows.get("attestation:passed-check-count", _zero()).value
            == attestation.passed_check_count,
            "observed": rows.get("attestation:passed-check-count", _zero()).value,
            "expected": attestation.passed_check_count,
        },
        {
            "check_id": "observability:boundary",
            "passed": not forbidden_keys(value.to_dict()),
            "observed": (),
            "expected": "no restricted public metadata",
        },
        {
            "check_id": "observability:accepted",
            "passed": value.accepted,
            "observed": value.accepted,
            "expected": True,
        },
    )
    return checks


def _zero() -> ReleaseAssuranceAttestationMetric:
    return _metric("zero", "cross-plane", "zero", 0, "count", "zero")


def release_assurance_attestation_observability_json(
    value: ReleaseAssuranceAttestationObservability,
) -> str:
    """Return canonical JSON for aggregate metrics."""

    from .serialization import canonical_json

    return canonical_json(value.to_dict()) + "\n"


def release_assurance_attestation_observability_csv(
    value: ReleaseAssuranceAttestationObservability,
) -> str:
    """Return stable metric rows as CSV."""

    import csv
    from io import StringIO

    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        ("metric_id", "component_id", "name", "value", "unit", "source_address", "content_address")
    )
    for item in value.metrics:
        writer.writerow(
            (
                item.metric_id,
                item.component_id,
                item.name,
                item.value,
                item.unit,
                item.source_address,
                item.content_address,
            )
        )
    return output.getvalue()


def release_assurance_attestation_observability_markdown(
    value: ReleaseAssuranceAttestationObservability,
) -> str:
    """Render deterministic reviewer-facing metrics."""

    lines = [
        "# Release assurance attestation observability",
        "",
        f"- Attestation: `{value.attestation_id}`",
        f"- Accepted: `{str(value.accepted).lower()}`",
        f"- Metrics: `{len(value.metrics)}`",
        "",
        "| Metric | Component | Value | Unit |",
        "| --- | --- | ---: | --- |",
    ]
    lines.extend(
        f"| {item.name} | {item.component_id} | {item.value} | {item.unit} |"
        for item in value.metrics
    )
    return "\n".join(lines) + "\n"


def release_assurance_attestation_observability_export_payloads(
    value: ReleaseAssuranceAttestationObservability,
) -> dict[str, bytes]:
    """Return deterministic observability exports."""

    return {
        "observability.json": release_assurance_attestation_observability_json(value).encode(
            "utf-8"
        ),
        "observability.csv": release_assurance_attestation_observability_csv(value).encode("utf-8"),
        "observability.md": release_assurance_attestation_observability_markdown(value).encode(
            "utf-8"
        ),
    }


def release_assurance_attestation_observability_schema() -> dict[str, Any]:
    """Describe metric dimensions and aggregation rules."""

    return {
        "version": "release-assurance-attestation-observability-schema-v1",
        "dimensions": ["component_id", "name", "unit", "source_address"],
        "aggregate_only": True,
        "timestamp_free": True,
        "source_payloads": False,
    }


def release_assurance_attestation_observability_capabilities() -> dict[str, Any]:
    """Describe aggregate observability guarantees."""

    return {
        "version": "release-assurance-attestation-observability-capabilities-v1",
        "component_metrics": True,
        "check_metrics": True,
        "category_metrics": True,
        "runtime_metrics": True,
        "conservation_audit": True,
        "json_export": True,
        "csv_export": True,
        "markdown_export": True,
        "source_payloads": False,
    }


__all__ = [
    "audit_release_assurance_attestation_observability",
    "build_release_assurance_attestation_observability",
    "release_assurance_attestation_observability_capabilities",
    "release_assurance_attestation_observability_csv",
    "release_assurance_attestation_observability_export_payloads",
    "release_assurance_attestation_observability_json",
    "release_assurance_attestation_observability_markdown",
    "release_assurance_attestation_observability_schema",
]
