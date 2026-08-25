"""Independent cross-artifact audit for D16 offline handoffs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .deployment_frontier_offline_bundle import load_deployment_frontier_offline_bundle
from .deployment_frontier_offline_contracts import (
    DEPLOYMENT_FRONTIER_OFFLINE_ARTIFACT_COUNT,
    DEPLOYMENT_FRONTIER_OFFLINE_CONTROL_COUNT,
    DEPLOYMENT_FRONTIER_OFFLINE_EVALUATION_CHECK_COUNT,
    DEPLOYMENT_FRONTIER_OFFLINE_EXECUTION_COUNT,
    DEPLOYMENT_FRONTIER_OFFLINE_OPERATION_COUNT,
    DEPLOYMENT_FRONTIER_OFFLINE_POSITIVE_COUNT,
    DEPLOYMENT_FRONTIER_OFFLINE_RECORD_COUNT,
    DEPLOYMENT_FRONTIER_OFFLINE_SOURCE_COUNT,
    DEPLOYMENT_FRONTIER_OFFLINE_STAGE_COUNT,
    DeploymentFrontierOfflineBundle,
)
from .deployment_frontier_offline_query import _payload, _rows
from .deployment_frontier_offline_schema import validate_deployment_frontier_offline_manifest
from .module_fabric_support import contains_private_key
from .run_workspace import _has_forbidden_key
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierOfflineAuditCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierOfflineAudit:
    bundle_id: str
    checks: tuple[DeploymentFrontierOfflineAuditCheck, ...]
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


def _check(
    check_id: str, passed: bool, observed: Any, required: Any, detail: str
) -> DeploymentFrontierOfflineAuditCheck:
    body = {
        "check_id": check_id,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return DeploymentFrontierOfflineAuditCheck(
        **body, content_address=content_hash(body, prefix="deployment-frontier-offline-audit-check")
    )


def _mapping(bundle: DeploymentFrontierOfflineBundle, artifact_id: str) -> Mapping[str, Any]:
    value = _payload(bundle, artifact_id)
    return value if isinstance(value, Mapping) else {}


def audit_deployment_frontier_offline_bundle(
    bundle: DeploymentFrontierOfflineBundle,
) -> DeploymentFrontierOfflineAudit:
    """Recompute joins from stored bytes; do not call the D16 producer."""

    manifest_report = validate_deployment_frontier_offline_manifest(
        bundle.to_dict(include_payloads=False)
    )
    records = _rows(bundle, "fixture", "records")
    sources = _rows(bundle, "fixture", "sources")
    executions = _rows(bundle, "evaluation", "executions")
    evaluation_checks = _rows(bundle, "evaluation", "checks")
    runtime = _mapping(bundle, "runtime")
    stages = runtime.get("stages", ()) if isinstance(runtime.get("stages", ()), list) else ()
    operation_index = _mapping(bundle, "operation-index")
    denominator = _mapping(bundle, "denominator-index")
    fixture_index = _mapping(bundle, "fixture-index")
    key_index = _mapping(bundle, "public-key-index")
    issue_index = _mapping(bundle, "issue-index")
    record_ids = tuple(str(item.get("record_id")) for item in records)
    execution_ids = tuple(str(item.get("record_id")) for item in executions)
    source_ids = tuple(str(item.get("source_id")) for item in sources)
    checks = (
        _check(
            "schema",
            manifest_report.accepted,
            manifest_report.failed_check_ids,
            (),
            "stored root manifest satisfies the closed shape",
        ),
        _check(
            "accepted", bundle.accepted, bundle.accepted, True, "source bundle declares acceptance"
        ),
        _check(
            "artifact-count",
            bundle.artifact_count == DEPLOYMENT_FRONTIER_OFFLINE_ARTIFACT_COUNT,
            bundle.artifact_count,
            DEPLOYMENT_FRONTIER_OFFLINE_ARTIFACT_COUNT,
            "artifact inventory is conserved",
        ),
        _check(
            "source-count",
            len(sources) == DEPLOYMENT_FRONTIER_OFFLINE_SOURCE_COUNT,
            len(sources),
            DEPLOYMENT_FRONTIER_OFFLINE_SOURCE_COUNT,
            "source receipts are conserved",
        ),
        _check(
            "record-count",
            len(records) == DEPLOYMENT_FRONTIER_OFFLINE_RECORD_COUNT,
            len(records),
            DEPLOYMENT_FRONTIER_OFFLINE_RECORD_COUNT,
            "fixture records are conserved",
        ),
        _check(
            "positive-count",
            sum(item.get("role") == "positive" for item in records)
            == DEPLOYMENT_FRONTIER_OFFLINE_POSITIVE_COUNT,
            sum(item.get("role") == "positive" for item in records),
            DEPLOYMENT_FRONTIER_OFFLINE_POSITIVE_COUNT,
            "positive records are conserved",
        ),
        _check(
            "control-count",
            sum(item.get("role") == "control" for item in records)
            == DEPLOYMENT_FRONTIER_OFFLINE_CONTROL_COUNT,
            sum(item.get("role") == "control" for item in records),
            DEPLOYMENT_FRONTIER_OFFLINE_CONTROL_COUNT,
            "control records are conserved",
        ),
        _check(
            "operation-count",
            len({item.get("operation") for item in records})
            == DEPLOYMENT_FRONTIER_OFFLINE_OPERATION_COUNT,
            len({item.get("operation") for item in records}),
            DEPLOYMENT_FRONTIER_OFFLINE_OPERATION_COUNT,
            "operation families are conserved",
        ),
        _check(
            "execution-count",
            len(executions) == DEPLOYMENT_FRONTIER_OFFLINE_EXECUTION_COUNT
            and execution_ids == record_ids,
            {"count": len(executions), "identity_match": execution_ids == record_ids},
            DEPLOYMENT_FRONTIER_OFFLINE_EXECUTION_COUNT,
            "every fixture record has one matching execution",
        ),
        _check(
            "evaluation-check-count",
            len(evaluation_checks) == DEPLOYMENT_FRONTIER_OFFLINE_EVALUATION_CHECK_COUNT,
            len(evaluation_checks),
            DEPLOYMENT_FRONTIER_OFFLINE_EVALUATION_CHECK_COUNT,
            "evaluation checks are conserved",
        ),
        _check(
            "runtime-count",
            len(stages) == DEPLOYMENT_FRONTIER_OFFLINE_STAGE_COUNT,
            len(stages),
            DEPLOYMENT_FRONTIER_OFFLINE_STAGE_COUNT,
            "runtime stages are conserved",
        ),
        _check(
            "runtime-sequence",
            [item.get("sequence") for item in stages]
            == list(range(1, DEPLOYMENT_FRONTIER_OFFLINE_STAGE_COUNT + 1)),
            [item.get("sequence") for item in stages],
            list(range(1, DEPLOYMENT_FRONTIER_OFFLINE_STAGE_COUNT + 1)),
            "runtime sequence is contiguous",
        ),
        _check(
            "source-identities",
            len(source_ids) == len(set(source_ids))
            and all(str(item.get("uri", "")).startswith("https://") for item in sources),
            source_ids,
            "unique HTTPS source ids",
            "source identities and transport are valid",
        ),
        _check(
            "fixture-index-join",
            fixture_index.get("record_count") == len(records)
            and fixture_index.get("source_count") == len(sources),
            fixture_index,
            {"record_count": len(records), "source_count": len(sources)},
            "fixture index joins its source arrays",
        ),
        _check(
            "operation-index-join",
            operation_index.get("operation_count") == DEPLOYMENT_FRONTIER_OFFLINE_OPERATION_COUNT
            and operation_index.get("balanced") is True,
            operation_index,
            {"operation_count": 4, "balanced": True},
            "operation index is balanced",
        ),
        _check(
            "denominator-index-join",
            all(
                denominator.get(key) == value
                for key, value in {
                    "sources": 5,
                    "records": 16,
                    "positive_records": 4,
                    "control_records": 12,
                    "operations": 4,
                    "executions": 16,
                    "evaluation_checks": 80,
                    "runtime_stages": 38,
                }.items()
            ),
            denominator,
            "D16 denominators",
            "denominator index joins all planes",
        ),
        _check(
            "issue-index-join",
            issue_index.get("issue_count") == 13,
            issue_index.get("issue_count"),
            13,
            "issue index retains every control category",
        ),
        _check(
            "public-key-join",
            key_index.get("accepted") is True and not key_index.get("forbidden_keys"),
            key_index.get("forbidden_keys"),
            (),
            "public key index is clean",
        ),
        _check(
            "manifest-public",
            not _has_forbidden_key(bundle.manifest_dict())
            and not contains_private_key(bundle.manifest_dict()),
            True,
            True,
            "root manifest has no prohibited fields",
        ),
        _check(
            "artifact-metadata-public",
            not any(
                _has_forbidden_key(item.to_dict(include_payload=False))
                or contains_private_key(item.to_dict(include_payload=False))
                for item in bundle.artifacts
            ),
            True,
            True,
            "artifact metadata remains public",
        ),
        _check(
            "runtime-address",
            bool(bundle.runtime_address)
            and bundle.runtime_address
            == next(
                (
                    item.content_address
                    for item in bundle.artifacts
                    if item.artifact_id == "runtime"
                ),
                "",
            ),
            bundle.runtime_address,
            "runtime artifact address",
            "root points to exact runtime bytes",
        ),
        _check(
            "component-addresses",
            all(item.content_address for item in bundle.artifacts),
            True,
            True,
            "all component receipts are addressed",
        ),
        _check(
            "bundle-checks",
            all(item.content_address for item in bundle.checks),
            True,
            True,
            "all root checks are addressed",
        ),
        _check(
            "ready-state",
            bundle.ready,
            bundle.state.value,
            "ready",
            "accepted bundle is ready for offline review",
        ),
    )
    accepted = bool(all(item.passed for item in checks))
    body = {"bundle_id": bundle.bundle_id, "checks": checks, "accepted": accepted}
    return DeploymentFrontierOfflineAudit(
        **body, content_address=content_hash(body, prefix="deployment-frontier-offline-audit")
    )


def audit_deployment_frontier_offline_directory(
    destination: str | Path,
) -> DeploymentFrontierOfflineAudit:
    """Load and audit a directory handoff after exact-byte verification."""

    verification = __import__(
        "glio_noncode.deployment_frontier_offline_bundle",
        fromlist=["verify_deployment_frontier_offline_bundle"],
    ).verify_deployment_frontier_offline_bundle(destination)
    bundle = load_deployment_frontier_offline_bundle(destination, include_payloads=True)
    base = audit_deployment_frontier_offline_bundle(bundle)
    checks = tuple(base.checks) + tuple(
        _check(item.check_id, item.passed, item.observed, item.required, item.detail)
        for item in verification.checks
    )
    accepted = bool(base.accepted and verification.accepted)
    body = {"bundle_id": bundle.bundle_id, "checks": checks, "accepted": accepted}
    return DeploymentFrontierOfflineAudit(
        **body,
        content_address=content_hash(body, prefix="deployment-frontier-offline-directory-audit"),
    )


__all__ = [
    "DeploymentFrontierOfflineAudit",
    "DeploymentFrontierOfflineAuditCheck",
    "audit_deployment_frontier_offline_bundle",
    "audit_deployment_frontier_offline_directory",
]
