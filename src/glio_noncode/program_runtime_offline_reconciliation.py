"""Cross-artifact denominator and identity reconciliation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .program_runtime_offline_contracts import (
    PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT,
    PROGRAM_RUNTIME_OFFLINE_PROGRAM_CHECK_COUNT,
    PROGRAM_RUNTIME_OFFLINE_RECONCILIATION_VERSION,
    PROGRAM_RUNTIME_OFFLINE_RUNTIME_STAGE_COUNT,
    ProgramRuntimeOfflineBundle,
)
from .program_runtime_offline_query import _payload, _rows
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ProgramRuntimeOfflineReconciliationCheck:
    check_id: str
    plane: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramRuntimeOfflineReconciliationReport:
    version: str
    bundle_id: str
    checks: tuple[ProgramRuntimeOfflineReconciliationCheck, ...]
    accepted: bool
    content_address: str

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed_count": self.passed_count,
            "failed_count": len(self.checks) - self.passed_count,
            "failed_check_ids": list(self.failed_check_ids),
        }


@dataclass(frozen=True, slots=True)
class ProgramRuntimeOfflineReconciliationDelta:
    left_bundle_id: str
    right_bundle_id: str
    left_address: str
    right_address: str
    changed_artifacts: tuple[str, ...]
    changed_counts: dict[str, tuple[int, int]]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _check(check_id: str, plane: str, passed: bool, observed: Any, required: Any, detail: str):
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return ProgramRuntimeOfflineReconciliationCheck(
        **body,
        content_address=content_hash(body, prefix="program-runtime-offline-reconciliation-check"),
    )


def reconcile_program_runtime_offline_bundle(
    bundle: ProgramRuntimeOfflineBundle,
) -> ProgramRuntimeOfflineReconciliationReport:
    """Close the joins between source runtime, release, and portable rows."""

    runtime = _payload(bundle, "runtime") or {}
    report = _payload(bundle, "report") or {}
    operational = _payload(bundle, "operational") or {}
    operations = _rows(bundle, "operations")
    checks = _rows(bundle, "checks")
    stages = _rows(bundle, "stages")
    quality = _payload(bundle, "quality") or {}
    release_checks = _rows(bundle, "release_checks")
    specifications = _rows(bundle, "specifications")
    capabilities = _rows(bundle, "capabilities")
    domain_ids = tuple(str(item.get("domain_id")) for item in operations)
    report_domain_ids = tuple(str(item.get("domain_id")) for item in report.get("receipts", ()))
    rows = (
        _check(
            "bundle-state",
            "manifest",
            bundle.ready,
            bundle.state.value,
            "ready",
            "bundle state is ready",
        ),
        _check(
            "runtime-state",
            "runtime",
            runtime.get("accepted") is True,
            runtime.get("state"),
            "accepted",
            "runtime payload is accepted",
        ),
        _check(
            "runtime-root",
            "address",
            runtime.get("content_address") == bundle.runtime_address,
            runtime.get("content_address"),
            bundle.runtime_address,
            "runtime payload joins manifest address",
        ),
        _check(
            "report-state",
            "runtime",
            report.get("accepted") is True,
            report.get("state"),
            "accepted",
            "report payload is accepted",
        ),
        _check(
            "domain-count",
            "denominator",
            len(operations) == PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT,
            len(operations),
            PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT,
            "operation rows are conserved",
        ),
        _check(
            "domain-identities",
            "identity",
            domain_ids == report_domain_ids,
            domain_ids,
            report_domain_ids,
            "operation rows join report receipts",
        ),
        _check(
            "domain-unique",
            "identity",
            len(domain_ids) == len(set(domain_ids)),
            len(set(domain_ids)),
            len(domain_ids),
            "domain identities are unique",
        ),
        _check(
            "check-count",
            "denominator",
            len(checks) == PROGRAM_RUNTIME_OFFLINE_PROGRAM_CHECK_COUNT,
            len(checks),
            PROGRAM_RUNTIME_OFFLINE_PROGRAM_CHECK_COUNT,
            "program checks are conserved",
        ),
        _check(
            "check-addresses",
            "address",
            all(
                str(item.get("content_address", "")).startswith("architecture-program-check:")
                for item in checks
            ),
            True,
            True,
            "program checks retain addresses",
        ),
        _check(
            "stage-count",
            "denominator",
            len(stages) == PROGRAM_RUNTIME_OFFLINE_RUNTIME_STAGE_COUNT,
            len(stages),
            PROGRAM_RUNTIME_OFFLINE_RUNTIME_STAGE_COUNT,
            "stages are conserved",
        ),
        _check(
            "stage-sequence",
            "runtime",
            [item.get("ordinal") for item in stages] == list(range(1, 13)),
            [item.get("ordinal") for item in stages],
            list(range(1, 13)),
            "stage sequence is contiguous",
        ),
        _check(
            "stage-addresses",
            "address",
            all(item.get("content_address") and item.get("output_address") for item in stages),
            True,
            True,
            "stage outputs are addressed",
        ),
        _check(
            "quality-state",
            "quality",
            quality.get("accepted") is True,
            quality.get("accepted"),
            True,
            "quality gate is accepted",
        ),
        _check(
            "quality-checks",
            "denominator",
            len(quality.get("checks", ())) == 18,
            len(quality.get("checks", ())),
            18,
            "quality checks are conserved",
        ),
        _check(
            "release-checks",
            "release",
            len(release_checks) == 18
            and all(str(item.get("passed")).casefold() == "true" for item in release_checks),
            len(release_checks),
            18,
            "release checks are closed",
        ),
        _check(
            "operational-state",
            "operational",
            operational.get("accepted") is True,
            operational.get("accepted"),
            True,
            "operational trace is accepted",
        ),
        _check(
            "operational-stages",
            "operational",
            operational.get("stage_count") == 12,
            operational.get("stage_count"),
            12,
            "operational trace covers runtime stages",
        ),
        _check(
            "specification-count",
            "catalog",
            len(specifications) == PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT,
            len(specifications),
            PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT,
            "specification catalog is conserved",
        ),
        _check(
            "capability-count",
            "catalog",
            len(capabilities) == PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT,
            len(capabilities),
            PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT,
            "capability matrix is conserved",
        ),
        _check(
            "specification-addresses",
            "address",
            all(
                str(item.get("content_address", "")).startswith("architecture-program-spec:")
                for item in specifications
            ),
            True,
            True,
            "specifications retain addresses",
        ),
        _check(
            "report-check-join",
            "join",
            report.get("failed_checks") == 0
            and report.get("passed_checks") == PROGRAM_RUNTIME_OFFLINE_PROGRAM_CHECK_COUNT,
            report.get("passed_checks"),
            PROGRAM_RUNTIME_OFFLINE_PROGRAM_CHECK_COUNT,
            "report counters join exported checks",
        ),
        _check(
            "runtime-stage-join",
            "join",
            runtime.get("stage_count") == len(stages),
            runtime.get("stage_count"),
            len(stages),
            "runtime stage count joins stage export",
        ),
        _check(
            "manifest-artifact-join",
            "address",
            bundle.artifact_count == len(bundle.artifacts),
            bundle.artifact_count,
            len(bundle.artifacts),
            "manifest artifact counter joins inventory",
        ),
    )
    accepted = all(item.passed for item in rows)
    body = {
        "version": PROGRAM_RUNTIME_OFFLINE_RECONCILIATION_VERSION,
        "bundle_id": bundle.bundle_id,
        "checks": rows,
        "accepted": accepted,
    }
    return ProgramRuntimeOfflineReconciliationReport(
        version=PROGRAM_RUNTIME_OFFLINE_RECONCILIATION_VERSION,
        bundle_id=bundle.bundle_id,
        checks=rows,
        accepted=accepted,
        content_address=content_hash(body, prefix="program-runtime-offline-reconciliation"),
    )


def compare_program_runtime_offline_bundles(
    left: ProgramRuntimeOfflineBundle,
    right: ProgramRuntimeOfflineBundle,
) -> ProgramRuntimeOfflineReconciliationDelta:
    """Compare artifact addresses and the principal runtime denominators."""

    left_map = {item.artifact_id: item for item in left.artifacts}
    right_map = {item.artifact_id: item for item in right.artifacts}
    changed = tuple(
        sorted(
            key
            for key in set(left_map) | set(right_map)
            if key not in left_map
            or key not in right_map
            or left_map[key].content_address != right_map[key].content_address
        )
    )
    changed_counts: dict[str, tuple[int, int]] = {}
    for key in ("domain_count", "stage_count", "warning_count", "artifact_count"):
        left_value = left.artifact_count if key == "artifact_count" else int(getattr(left, key))
        right_value = right.artifact_count if key == "artifact_count" else int(getattr(right, key))
        if left_value != right_value:
            changed_counts[key] = (left_value, right_value)
    accepted = left.ready and right.ready and not changed and not changed_counts
    body = {
        "left_bundle_id": left.bundle_id,
        "right_bundle_id": right.bundle_id,
        "left_address": left.content_address,
        "right_address": right.content_address,
        "changed_artifacts": changed,
        "changed_counts": changed_counts,
        "accepted": accepted,
    }
    return ProgramRuntimeOfflineReconciliationDelta(
        **body,
        content_address=content_hash(body, prefix="program-runtime-offline-reconciliation-delta"),
    )


def program_runtime_offline_reconciliation_markdown(
    report: ProgramRuntimeOfflineReconciliationReport,
) -> str:
    lines = [
        "# Architecture program offline reconciliation",
        "",
        f"Bundle: `{report.bundle_id}`",
        f"Accepted: `{str(report.accepted).lower()}`",
        "",
        "| Check | Plane | State | Detail |",
        "| --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| `{item.check_id}` | `{item.plane}` | "
        f"`{('pass' if item.passed else 'hold')}` | {item.detail} |"
        for item in report.checks
    )
    return "\n".join(lines) + "\n"


__all__ = [
    "ProgramRuntimeOfflineReconciliationCheck",
    "ProgramRuntimeOfflineReconciliationDelta",
    "ProgramRuntimeOfflineReconciliationReport",
    "compare_program_runtime_offline_bundles",
    "program_runtime_offline_reconciliation_markdown",
    "reconcile_program_runtime_offline_bundle",
]
