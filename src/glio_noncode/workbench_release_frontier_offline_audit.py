"""Independent cross-artifact audit for D15 offline workbench bundles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .module_fabric_support import contains_private_key
from .run_workspace import _has_forbidden_key
from .serialization import content_hash, jsonable
from .workbench_release_frontier_offline_contracts import WorkbenchReleaseOfflineBundle
from .workbench_release_frontier_offline_query import _payload, _rows


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseOfflineAuditCheck:
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
class WorkbenchReleaseOfflineAudit:
    bundle_id: str
    checks: tuple[WorkbenchReleaseOfflineAuditCheck, ...]
    accepted: bool
    content_address: str

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_count(self) -> int:
        return len(self.checks) - self.passed_count

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
        }


def _check(
    check_id: str, plane: str, passed: bool, observed: Any, required: Any, detail: str
) -> WorkbenchReleaseOfflineAuditCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return WorkbenchReleaseOfflineAuditCheck(
        **body, content_address=content_hash(body, prefix="workbench-release-offline-audit-check")
    )


def _value(bundle: WorkbenchReleaseOfflineBundle, artifact_id: str) -> Mapping[str, Any]:
    value = _payload(bundle, artifact_id)
    return value if isinstance(value, Mapping) else {}


def audit_workbench_release_offline_bundle(
    bundle: WorkbenchReleaseOfflineBundle,
) -> WorkbenchReleaseOfflineAudit:
    """Reconcile independent payload joins and all public denominators."""

    fixture = _value(bundle, "fixture")
    evaluation = _value(bundle, "evaluation")
    runtime = _value(bundle, "runtime")
    stage_index = _value(bundle, "stage-index")
    denominator = _value(bundle, "denominator-index")
    operation_index = _value(bundle, "operation-index")
    public_keys = _value(bundle, "public-key-index")
    records = _rows(bundle, "fixture", "records")
    sources = _rows(bundle, "fixture", "sources")
    executions = _rows(bundle, "evaluation", "executions")
    checks = _rows(bundle, "evaluation", "checks")
    stages = _rows(bundle, "runtime", "stages")
    operations = tuple(sorted({str(item.get("operation")) for item in records}))
    record_ids = tuple(str(item.get("record_id")) for item in records)
    execution_ids = tuple(str(item.get("record_id")) for item in executions)
    source_ids = tuple(str(item.get("source_id")) for item in sources)
    component_artifacts = tuple(
        item
        for item in bundle.artifacts
        if item.artifact_id not in {"fixture", "evaluation", "runtime", "review-csv"}
    )
    audit_checks = (
        _check(
            "bundle-ready", "closure", bundle.ready, bundle.accepted, True, "root bundle is ready"
        ),
        _check(
            "fixture-records",
            "denominator",
            len(records) == 16,
            len(records),
            16,
            "fixture records are conserved",
        ),
        _check(
            "fixture-sources",
            "denominator",
            len(sources) == 5,
            len(sources),
            5,
            "fixture sources are conserved",
        ),
        _check(
            "fixture-roles",
            "denominator",
            sum(item.get("role") == "positive" for item in records) == 4
            and sum(item.get("role") == "control" for item in records) == 12,
            {
                "positive": sum(item.get("role") == "positive" for item in records),
                "control": sum(item.get("role") == "control" for item in records),
            },
            {"positive": 4, "control": 12},
            "positive and control records are balanced",
        ),
        _check(
            "fixture-record-identities",
            "identity",
            len(record_ids) == len(set(record_ids)),
            len(set(record_ids)),
            len(record_ids),
            "record identities are unique",
        ),
        _check(
            "fixture-source-identities",
            "identity",
            len(source_ids) == len(set(source_ids)),
            len(set(source_ids)),
            len(source_ids),
            "source identities are unique",
        ),
        _check(
            "fixture-https",
            "security",
            all(str(item.get("uri", "")).startswith("https://") for item in sources),
            True,
            True,
            "source receipts use HTTPS",
        ),
        _check(
            "catalog-boundary",
            "security",
            not _has_forbidden_key(fixture) and not contains_private_key(fixture),
            True,
            True,
            "fixture payload is public",
        ),
        _check(
            "evaluation-records",
            "join",
            execution_ids == record_ids,
            execution_ids,
            record_ids,
            "every fixture record has exactly one execution",
        ),
        _check(
            "evaluation-checks",
            "denominator",
            len(checks) == 80,
            len(checks),
            80,
            "evaluation check denominator is conserved",
        ),
        _check(
            "evaluation-addresses",
            "address",
            all(str(item.get("content_address", "")).startswith("sha256:") for item in executions),
            sum(str(item.get("content_address", "")).startswith("sha256:") for item in executions),
            16,
            "execution addresses are retained",
        ),
        _check(
            "evaluation-accepted",
            "runtime",
            bool(evaluation.get("accepted")),
            evaluation.get("accepted"),
            True,
            "evaluation remains accepted",
        ),
        _check(
            "runtime-stages",
            "runtime",
            len(stages) == 49 and [item.get("sequence") for item in stages] == list(range(1, 50)),
            len(stages),
            49,
            "runtime stages are complete and ordered",
        ),
        _check(
            "runtime-address-join",
            "join",
            runtime.get("content_address") == bundle.runtime_address,
            runtime.get("content_address"),
            bundle.runtime_address,
            "runtime artifact joins root manifest",
        ),
        _check(
            "runtime-stage-addresses",
            "runtime",
            all(str(item.get("content_address", "")).startswith("sha256:") for item in stages),
            True,
            True,
            "runtime stages are addressed",
        ),
        _check(
            "stage-index-count",
            "index",
            stage_index.get("stage_count") == 49,
            stage_index.get("stage_count"),
            49,
            "stage index conserves stages",
        ),
        _check(
            "stage-index-order",
            "index",
            stage_index.get("ordered") is True
            and stage_index.get("sequence") == list(range(1, 50)),
            stage_index.get("sequence"),
            list(range(1, 50)),
            "stage index preserves dependency order",
        ),
        _check(
            "denominator-index-records",
            "index",
            denominator.get("records") == 16,
            denominator.get("records"),
            16,
            "denominator index joins records",
        ),
        _check(
            "denominator-index-checks",
            "index",
            denominator.get("evaluation_checks") == 80,
            denominator.get("evaluation_checks"),
            80,
            "denominator index joins checks",
        ),
        _check(
            "operation-index-count",
            "index",
            len(operation_index.get("operations", {})) == 4,
            len(operation_index.get("operations", {})),
            4,
            "operation index retains four families",
        ),
        _check(
            "operation-index-balance",
            "index",
            operation_index.get("balanced") is True
            and all(len(value) == 4 for value in operation_index.get("operations", {}).values()),
            operation_index.get("operations"),
            "four rows per operation",
            "operation partitions are balanced",
        ),
        _check(
            "public-key-index",
            "security",
            public_keys.get("accepted") is True and public_keys.get("forbidden_keys") == [],
            public_keys.get("forbidden_keys"),
            [],
            "public key audit has no forbidden keys",
        ),
        _check(
            "component-inventory",
            "manifest",
            len(component_artifacts) == 52,
            len(component_artifacts),
            52,
            "all runtime planes and indexes are inventoried",
        ),
        _check(
            "component-addresses",
            "address",
            all(
                item.content_address.startswith("workbench-release-bundle-artifact:")
                for item in component_artifacts
            ),
            True,
            True,
            "component artifacts have exact-byte addresses",
        ),
        _check(
            "operation-denominator",
            "denominator",
            len(operations) == 4
            and all(
                sum(item.get("operation") == operation for item in records) == 4
                for operation in operations
            ),
            {
                operation: sum(item.get("operation") == operation for item in records)
                for operation in operations
            },
            "four each",
            "operation rows are conserved",
        ),
        _check(
            "source-joins",
            "join",
            all(set(item.get("source_ids", ())) <= set(source_ids) for item in records),
            True,
            True,
            "record source references resolve",
        ),
        _check(
            "observability-join",
            "join",
            bool(_value(bundle, "observability").get("values")),
            _value(bundle, "observability").get("values"),
            "non-empty values",
            "observability receipt is materialized",
        ),
        _check(
            "release-plane",
            "closure",
            bool(_value(bundle, "release").get("accepted")),
            _value(bundle, "release").get("accepted"),
            True,
            "release plane is accepted",
        ),
        _check(
            "claim-boundary",
            "security",
            _value(bundle, "claim-boundary").get("values", {}).get("research_only", True) is True,
            _value(bundle, "claim-boundary"),
            True,
            "claim boundary remains research-only",
        ),
        _check(
            "public-manifest",
            "security",
            not _has_forbidden_key(bundle.manifest_dict())
            and not contains_private_key(bundle.manifest_dict()),
            True,
            True,
            "manifest projection remains public",
        ),
    )
    accepted = all(item.passed for item in audit_checks)
    body = {"bundle_id": bundle.bundle_id, "checks": audit_checks, "accepted": accepted}
    return WorkbenchReleaseOfflineAudit(
        **body, content_address=content_hash(body, prefix="workbench-release-offline-audit")
    )


__all__ = [
    "WorkbenchReleaseOfflineAudit",
    "WorkbenchReleaseOfflineAuditCheck",
    "audit_workbench_release_offline_bundle",
]
