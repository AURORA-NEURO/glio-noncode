"""Build, materialize, and verify the D16 deployment offline handoff.

This module is the boundary adapter between the in-process deployment
runtime and a portable directory.  It keeps the runtime's detailed planes,
but makes three deliberate changes for transport:

* host timing is normalized so repeated builds have the same root address;
* payloads are projected through a strict public-key boundary;
* every file is hashed over the bytes that are actually written.

The builder does not read a local repository, fetch a framework, or require a
network service.  A caller may supply an already-built fixture or runtime for
testing; the default path uses only the D16 public aggregate fixture.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from .deployment_frontier_public_data import default_deployment_frontier_fixture
from .deployment_frontier_runtime import run_deployment_frontier_runtime
from .errors import ValidationError
from .module_fabric_support import contains_private_key
from .run_workspace import _has_forbidden_key
from .serialization import canonical_json, content_hash, hash_bytes, jsonable, require_non_empty
from .deployment_frontier_offline_contracts import (
    DEPLOYMENT_FRONTIER_OFFLINE_ARTIFACT_COUNT,
    DEPLOYMENT_FRONTIER_OFFLINE_ARTIFACT_PREFIX,
    DEPLOYMENT_FRONTIER_OFFLINE_BOUNDARY,
    DEPLOYMENT_FRONTIER_OFFLINE_BUNDLE_VERSION,
    DEPLOYMENT_FRONTIER_OFFLINE_CONTROL_COUNT,
    DEPLOYMENT_FRONTIER_OFFLINE_EVALUATION_CHECK_COUNT,
    DEPLOYMENT_FRONTIER_OFFLINE_EXECUTION_COUNT,
    DEPLOYMENT_FRONTIER_OFFLINE_MANIFEST,
    DEPLOYMENT_FRONTIER_OFFLINE_OPERATION_COUNT,
    DEPLOYMENT_FRONTIER_OFFLINE_POSITIVE_COUNT,
    DEPLOYMENT_FRONTIER_OFFLINE_RECORD_COUNT,
    DEPLOYMENT_FRONTIER_OFFLINE_SOURCE_COUNT,
    DEPLOYMENT_FRONTIER_OFFLINE_STAGE_COUNT,
    DeploymentFrontierOfflineArtifact,
    DeploymentFrontierOfflineArtifactKind,
    DeploymentFrontierOfflineBundle,
    DeploymentFrontierOfflineBundleState,
    DeploymentFrontierOfflineCheck,
    DeploymentFrontierOfflineCheckPlane,
    DeploymentFrontierOfflineVerification,
    deployment_frontier_offline_check,
)


DEPLOYMENT_FRONTIER_OFFLINE_JSON_MEDIA_TYPE = "application/json"
DEPLOYMENT_FRONTIER_OFFLINE_CSV_MEDIA_TYPE = "text/csv"

# The names are case-folded before comparison.  These fields are excluded
# even when an upstream component accidentally adds them to a nested object.
DEPLOYMENT_FRONTIER_OFFLINE_FORBIDDEN_KEYS = frozenset(
    {
        "agent",
        "agent_id",
        "agent_name",
        "assistant",
        "assistant_id",
        "assistant_name",
        "author",
        "author_id",
        "author_name",
        "contact_name",
        "email",
        "generated_by",
        "language",
        "model",
        "model_id",
        "model_name",
        "model_version",
        "primary_agent",
        "primary_agent_id",
        "produced_by",
        "programming_language",
        "phone",
        "patient_id",
        "subject_id",
        "participant_id",
        "individual_id",
        "medical_record_number",
    }
)


def _safe_component(value: str, field: str) -> str:
    normalized = str(value).strip()
    if (
        not normalized
        or len(normalized) > 128
        or normalized in {".", ".."}
        or any(char in normalized for char in ("/", "\\"))
        or ".." in normalized
    ):
        raise ValidationError(f"{field} contains an unsafe path fragment")
    return normalized


def _safe_relative_path(value: str) -> bool:
    if not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return (
        not path.is_absolute()
        and bool(path.parts)
        and all(part not in {"", ".", ".."} for part in path.parts)
    )


def _public_projection(value: Any) -> Any:
    """Remove prohibited attribution and implementation keys recursively."""

    value = jsonable(value)
    if isinstance(value, Mapping):
        return {
            str(key): _public_projection(item)
            for key, item in value.items()
            if str(key).casefold() not in DEPLOYMENT_FRONTIER_OFFLINE_FORBIDDEN_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_public_projection(item) for item in value]
    return value


def _public_value(value: Any) -> Any:
    projected = _public_projection(value)
    if _has_forbidden_key(projected) or contains_private_key(projected):
        raise ValidationError("deployment offline bundle crosses the public boundary")
    return projected


def _json_text(value: Any) -> str:
    return canonical_json(_public_value(value)) + "\n"


def _line_count(value: str) -> int:
    return len(value.splitlines())


def _artifact(
    artifact_id: str,
    relative_path: str,
    media_type: str,
    payload: Any,
    *,
    kind: DeploymentFrontierOfflineArtifactKind,
) -> DeploymentFrontierOfflineArtifact:
    path = str(relative_path)
    if not _safe_relative_path(path):
        raise ValidationError(f"unsafe deployment bundle path: {path!r}")
    text = (
        _json_text(payload)
        if media_type == DEPLOYMENT_FRONTIER_OFFLINE_JSON_MEDIA_TYPE
        else str(payload).rstrip("\n") + "\n"
    )
    raw = text.encode("utf-8")
    return DeploymentFrontierOfflineArtifact(
        artifact_id=_safe_component(artifact_id, "artifact_id"),
        relative_path=path,
        media_type=media_type,
        kind=kind,
        byte_count=len(raw),
        line_count=_line_count(text),
        content_address=hash_bytes(raw, prefix=DEPLOYMENT_FRONTIER_OFFLINE_ARTIFACT_PREFIX),
        payload=text,
    )


def _stable_runtime_projection(runtime: Any) -> dict[str, Any]:
    """Normalize perf-counter variance while retaining every ordered stage."""

    value = jsonable(runtime)
    if not isinstance(value, dict):
        raise ValidationError("deployment runtime must serialize to an object")
    stages = value.get("stages", ())
    if isinstance(stages, list):
        normalized_stages: list[Any] = []
        for stage in stages:
            if isinstance(stage, Mapping):
                normalized = dict(stage)
                normalized["duration_ms"] = 0.0
                normalized.pop("content_address", None)
                normalized["content_address"] = content_hash(normalized)
                normalized_stages.append(normalized)
            else:
                normalized_stages.append(stage)
        value["stages"] = normalized_stages
    value.pop("content_address", None)
    value["content_address"] = content_hash(value, prefix="deployment-frontier-runtime-public")
    return value


def _component(runtime: Any, attribute: str) -> Any:
    value = getattr(runtime, attribute, None)
    if value is None:
        raise ValidationError(f"deployment runtime is missing component {attribute!r}")
    return value


def _recursive_keys(value: Any) -> tuple[str, ...]:
    if isinstance(value, Mapping):
        found: set[str] = set()
        for key, item in value.items():
            found.add(str(key))
            found.update(_recursive_keys(item))
        return tuple(sorted(found))
    if isinstance(value, (list, tuple)):
        found: set[str] = set()
        for item in value:
            found.update(_recursive_keys(item))
        return tuple(sorted(found))
    return ()


def _stage_index(runtime_projection: Mapping[str, Any]) -> dict[str, Any]:
    stages = runtime_projection.get("stages", ())
    rows = tuple(
        {
            "sequence": int(item.get("sequence", index)),
            "stage_id": str(item.get("stage_id", "")),
            "state": str(item.get("state", "")),
            "duration_ms": float(item.get("duration_ms", 0.0)),
            "output_address": str(item.get("output_address", "")),
            "content_address": str(item.get("content_address", "")),
        }
        for index, item in enumerate(stages, start=1)
        if isinstance(item, Mapping)
    )
    sequence = [item["sequence"] for item in rows]
    body = {
        "stage_count": len(rows),
        "stages": rows,
        "sequence": sequence,
        "ordered": sequence == list(range(1, len(rows) + 1)),
    }
    return body | {"content_address": content_hash(body, prefix="deployment-frontier-stage-index")}


def _denominator_index(
    fixture: Any, evaluation: Any, runtime_projection: Mapping[str, Any]
) -> dict[str, Any]:
    records = tuple(fixture.records)
    operations = tuple(sorted({item.operation.value for item in records}))
    issues = tuple(sorted({issue for item in evaluation.executions for issue in item.issue_codes}))
    body = {
        "sources": len(fixture.sources),
        "records": len(records),
        "positive_records": len(fixture.positive_records),
        "control_records": len(fixture.control_records),
        "operations": len(operations),
        "executions": len(evaluation.executions),
        "evaluation_checks": len(evaluation.checks),
        "runtime_stages": len(runtime_projection.get("stages", ())),
        "issue_categories": len(issues),
        "operation_ids": operations,
        "issue_ids": issues,
    }
    return body | {
        "content_address": content_hash(body, prefix="deployment-frontier-denominator-index")
    }


def _operation_index(evaluation: Any) -> dict[str, Any]:
    rows: dict[str, list[str]] = {}
    for item in evaluation.executions:
        rows.setdefault(item.operation.value, []).append(item.record_id)
    body = {
        "operations": {key: tuple(value) for key, value in sorted(rows.items())},
        "operation_count": len(rows),
        "balanced": bool(rows) and len({len(value) for value in rows.values()}) == 1,
    }
    return body | {
        "content_address": content_hash(body, prefix="deployment-frontier-operation-index")
    }


def _fixture_index(fixture: Any) -> dict[str, Any]:
    sources = tuple(
        {"source_id": source.source_id, "content_address": source.content_address}
        for source in fixture.sources
    )
    records = tuple(
        {
            "record_id": record.record_id,
            "operation": record.operation.value,
            "role": record.role.value,
            "content_address": record.content_address,
        }
        for record in fixture.records
    )
    body = {
        "fixture_id": fixture.fixture_id,
        "context_key": fixture.context_key,
        "source_count": len(sources),
        "record_count": len(records),
        "sources": sources,
        "records": records,
    }
    return body | {
        "content_address": content_hash(body, prefix="deployment-frontier-fixture-index")
    }


def _public_key_index(fixture: Any, runtime_projection: Mapping[str, Any]) -> dict[str, Any]:
    all_keys = set(_recursive_keys(_public_projection(fixture))) | set(
        _recursive_keys(_public_projection(runtime_projection))
    )
    forbidden = tuple(
        sorted(
            key
            for key in all_keys
            if key.casefold() in DEPLOYMENT_FRONTIER_OFFLINE_FORBIDDEN_KEYS
            or _has_forbidden_key({key: True})
            or contains_private_key({key: True})
        )
    )
    body = {
        "key_count": len(all_keys),
        "public_key_count": len(all_keys - set(forbidden)),
        "forbidden_keys": forbidden,
        "accepted": not forbidden,
    }
    return body | {
        "content_address": content_hash(body, prefix="deployment-frontier-public-key-index")
    }


def _issue_index(evaluation: Any) -> dict[str, Any]:
    counts: dict[str, int] = {}
    record_ids: dict[str, list[str]] = {}
    for execution in evaluation.executions:
        for issue in execution.issue_codes:
            counts[issue] = counts.get(issue, 0) + 1
            record_ids.setdefault(issue, []).append(execution.record_id)
    body = {
        "issue_counts": dict(sorted(counts.items())),
        "record_ids": {key: tuple(value) for key, value in sorted(record_ids.items())},
        "issue_count": len(counts),
    }
    return body | {"content_address": content_hash(body, prefix="deployment-frontier-issue-index")}


def _state_index(evaluation: Any) -> dict[str, Any]:
    counts: dict[str, int] = {}
    record_ids: dict[str, list[str]] = {}
    for execution in evaluation.executions:
        state = execution.state.value
        counts[state] = counts.get(state, 0) + 1
        record_ids.setdefault(state, []).append(execution.record_id)
    body = {
        "state_counts": dict(sorted(counts.items())),
        "record_ids": {key: tuple(value) for key, value in sorted(record_ids.items())},
    }
    return body | {"content_address": content_hash(body, prefix="deployment-frontier-state-index")}


def _review_csv(fixture: Any, evaluation: Any) -> str:
    expected = {item.record_id: item.expected_state.value for item in fixture.records}
    stream = io.StringIO()
    fields = (
        "record_id",
        "operation",
        "role",
        "expected_state",
        "observed_state",
        "accepted",
        "issue_codes",
        "content_address",
    )
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in evaluation.executions:
        writer.writerow(
            {
                "record_id": item.record_id,
                "operation": item.operation.value,
                "role": item.role.value,
                "expected_state": expected.get(item.record_id, ""),
                "observed_state": item.state.value,
                "accepted": item.accepted,
                "issue_codes": "|".join(item.issue_codes),
                "content_address": item.content_address,
            }
        )
    return stream.getvalue()


def _sources_csv(fixture: Any) -> str:
    stream = io.StringIO()
    fields = ("source_id", "title", "uri", "scope", "version", "content_address")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in fixture.sources:
        writer.writerow({field: getattr(item, field) for field in fields})
    return stream.getvalue()


def _executions_csv(evaluation: Any) -> str:
    stream = io.StringIO()
    fields = (
        "record_id",
        "operation",
        "role",
        "state",
        "accepted",
        "issue_codes",
        "content_address",
    )
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in evaluation.executions:
        writer.writerow(
            {
                "record_id": item.record_id,
                "operation": item.operation.value,
                "role": item.role.value,
                "state": item.state.value,
                "accepted": item.accepted,
                "issue_codes": "|".join(item.issue_codes),
                "content_address": item.content_address,
            }
        )
    return stream.getvalue()


_COMPONENT_DEFINITIONS: tuple[tuple[str, str, DeploymentFrontierOfflineArtifactKind, str], ...] = (
    ("audit", "planes/audit.json", DeploymentFrontierOfflineArtifactKind.AUDIT, "audit"),
    (
        "evaluation",
        "planes/evaluation.json",
        DeploymentFrontierOfflineArtifactKind.EVALUATION,
        "evaluation",
    ),
    ("metrics", "planes/metrics.json", DeploymentFrontierOfflineArtifactKind.METRICS, "metrics"),
    ("policy", "planes/policy.json", DeploymentFrontierOfflineArtifactKind.POLICY, "policy"),
    ("schema", "planes/schema.json", DeploymentFrontierOfflineArtifactKind.SCHEMA, "schema"),
    ("lineage", "planes/lineage.json", DeploymentFrontierOfflineArtifactKind.LINEAGE, "lineage"),
    (
        "reconciliation",
        "planes/reconciliation.json",
        DeploymentFrontierOfflineArtifactKind.RECONCILIATION,
        "reconciliation",
    ),
    ("quality", "planes/quality.json", DeploymentFrontierOfflineArtifactKind.QUALITY, "quality"),
    ("replay", "planes/replay.json", DeploymentFrontierOfflineArtifactKind.REPLAY, "replay"),
    ("release", "planes/release.json", DeploymentFrontierOfflineArtifactKind.RELEASE, "release"),
    (
        "artifacts",
        "planes/artifacts.json",
        DeploymentFrontierOfflineArtifactKind.ARTIFACTS,
        "artifacts",
    ),
    ("summary", "planes/summary.json", DeploymentFrontierOfflineArtifactKind.SUMMARY, "summary"),
    ("view", "planes/view.json", DeploymentFrontierOfflineArtifactKind.VIEW, "view"),
    (
        "queue",
        "planes/review-queue.json",
        DeploymentFrontierOfflineArtifactKind.REVIEW_QUEUE,
        "queue",
    ),
    ("sla", "planes/review-sla.json", DeploymentFrontierOfflineArtifactKind.REVIEW_SLA, "sla"),
    ("handoff", "planes/handoff.json", DeploymentFrontierOfflineArtifactKind.HANDOFF, "handoff"),
    (
        "integrity",
        "planes/integrity.json",
        DeploymentFrontierOfflineArtifactKind.INTEGRITY,
        "integrity",
    ),
    ("depth", "planes/depth.json", DeploymentFrontierOfflineArtifactKind.DEPTH, "depth"),
    (
        "operational",
        "planes/operational.json",
        DeploymentFrontierOfflineArtifactKind.OPERATIONAL,
        "operational",
    ),
    (
        "performance",
        "planes/performance.json",
        DeploymentFrontierOfflineArtifactKind.PERFORMANCE,
        "performance",
    ),
    (
        "assurance",
        "planes/assurance.json",
        DeploymentFrontierOfflineArtifactKind.ASSURANCE,
        "assurance",
    ),
    (
        "failure_injection",
        "planes/failure-injection.json",
        DeploymentFrontierOfflineArtifactKind.FAILURE_INJECTION,
        "failure_injection",
    ),
    (
        "compliance",
        "planes/compliance.json",
        DeploymentFrontierOfflineArtifactKind.COMPLIANCE,
        "compliance",
    ),
    (
        "diagnostics",
        "planes/diagnostics.json",
        DeploymentFrontierOfflineArtifactKind.DIAGNOSTICS,
        "diagnostics",
    ),
    (
        "plan",
        "planes/execution-plan.json",
        DeploymentFrontierOfflineArtifactKind.EXECUTION_PLAN,
        "plan",
    ),
    (
        "thresholds",
        "planes/thresholds.json",
        DeploymentFrontierOfflineArtifactKind.THRESHOLDS,
        "thresholds",
    ),
    (
        "validation",
        "planes/validation.json",
        DeploymentFrontierOfflineArtifactKind.VALIDATION,
        "validation",
    ),
    ("access", "planes/access.json", DeploymentFrontierOfflineArtifactKind.ACCESS, "access"),
    (
        "compatibility",
        "planes/compatibility.json",
        DeploymentFrontierOfflineArtifactKind.COMPATIBILITY,
        "compatibility",
    ),
    (
        "release_checks",
        "planes/release-checks.json",
        DeploymentFrontierOfflineArtifactKind.RELEASE_CHECKS,
        "release_checks",
    ),
    ("runbook", "planes/runbook.json", DeploymentFrontierOfflineArtifactKind.RUNBOOK, "runbook"),
    (
        "freshness",
        "planes/freshness.json",
        DeploymentFrontierOfflineArtifactKind.FRESHNESS,
        "freshness",
    ),
    (
        "audit_log",
        "planes/audit-log.json",
        DeploymentFrontierOfflineArtifactKind.AUDIT_LOG,
        "audit_log",
    ),
    (
        "transcript",
        "planes/transcript.json",
        DeploymentFrontierOfflineArtifactKind.TRANSCRIPT,
        "transcript",
    ),
    ("package", "planes/package.json", DeploymentFrontierOfflineArtifactKind.PACKAGE, "package"),
    ("bundle", "planes/bundle.json", DeploymentFrontierOfflineArtifactKind.BUNDLE, "bundle"),
    (
        "trace",
        "planes/observability.json",
        DeploymentFrontierOfflineArtifactKind.OBSERVABILITY,
        "trace",
    ),
)


def _component_payloads(
    runtime: Any, fixture: Any, evaluation: Any, runtime_projection: dict[str, Any]
) -> tuple[tuple[str, str, DeploymentFrontierOfflineArtifactKind, Any], ...]:
    rows: list[tuple[str, str, DeploymentFrontierOfflineArtifactKind, Any]] = [
        ("fixture", "fixture.json", DeploymentFrontierOfflineArtifactKind.FIXTURE, fixture)
    ]
    rows.extend(
        (key, path, kind, _component(runtime, attribute))
        for key, path, kind, attribute in _COMPONENT_DEFINITIONS
    )
    rows.extend(
        (
            (
                "runtime",
                "runtime/runtime.json",
                DeploymentFrontierOfflineArtifactKind.RUNTIME,
                runtime_projection,
            ),
            (
                "stage-index",
                "indexes/stage-index.json",
                DeploymentFrontierOfflineArtifactKind.STAGE_INDEX,
                _stage_index(runtime_projection),
            ),
            (
                "denominator-index",
                "indexes/denominator-index.json",
                DeploymentFrontierOfflineArtifactKind.DENOMINATOR_INDEX,
                _denominator_index(fixture, evaluation, runtime_projection),
            ),
            (
                "operation-index",
                "indexes/operation-index.json",
                DeploymentFrontierOfflineArtifactKind.OPERATION_INDEX,
                _operation_index(evaluation),
            ),
            (
                "public-key-index",
                "indexes/public-key-index.json",
                DeploymentFrontierOfflineArtifactKind.PUBLIC_KEY_INDEX,
                _public_key_index(fixture, runtime_projection),
            ),
            (
                "fixture-index",
                "indexes/fixture-index.json",
                DeploymentFrontierOfflineArtifactKind.FIXTURE_INDEX,
                _fixture_index(fixture),
            ),
            (
                "issue-index",
                "indexes/issue-index.json",
                DeploymentFrontierOfflineArtifactKind.ISSUE_INDEX,
                _issue_index(evaluation),
            ),
            (
                "state-index",
                "indexes/state-index.json",
                DeploymentFrontierOfflineArtifactKind.STATE_INDEX,
                _state_index(evaluation),
            ),
            (
                "review-csv",
                "exports/review.csv",
                DeploymentFrontierOfflineArtifactKind.REVIEW_CSV,
                _review_csv(fixture, evaluation),
            ),
            (
                "sources-csv",
                "exports/sources.csv",
                DeploymentFrontierOfflineArtifactKind.SOURCES_CSV,
                _sources_csv(fixture),
            ),
            (
                "executions-csv",
                "exports/executions.csv",
                DeploymentFrontierOfflineArtifactKind.EXECUTIONS_CSV,
                _executions_csv(evaluation),
            ),
            (
                "data-dictionary",
                "exports/data-dictionary.json",
                DeploymentFrontierOfflineArtifactKind.DATA_DICTIONARY,
                {
                    "columns": (
                        "record_id",
                        "operation",
                        "role",
                        "state",
                        "accepted",
                        "issue_codes",
                        "content_address",
                    ),
                    "record_count": len(evaluation.executions),
                    "source_count": len(fixture.sources),
                    "addressed": True,
                },
            ),
            (
                "capability-map",
                "exports/capability-map.json",
                DeploymentFrontierOfflineArtifactKind.CAPABILITY_MAP,
                {
                    "operations": tuple(sorted({item.operation.value for item in fixture.records})),
                    "descriptions": {
                        "privacy_security_policy": (
                            "policy decisions remain inside an aggregate public boundary"
                        ),
                        "local_deployment_bundle": (
                            "offline artifact and service requirements are explicit"
                        ),
                        "federated_execution": "site availability and privacy budgets are checked",
                        "release_rollback": (
                            "release and rollback gates are independently reviewable"
                        ),
                    },
                },
            ),
        )
    )
    return tuple(rows)


def _build_artifacts(
    payloads: tuple[tuple[str, str, DeploymentFrontierOfflineArtifactKind, Any], ...],
) -> tuple[DeploymentFrontierOfflineArtifact, ...]:
    return tuple(
        _artifact(
            artifact_id,
            path,
            DEPLOYMENT_FRONTIER_OFFLINE_CSV_MEDIA_TYPE
            if kind
            in {
                DeploymentFrontierOfflineArtifactKind.REVIEW_CSV,
                DeploymentFrontierOfflineArtifactKind.SOURCES_CSV,
                DeploymentFrontierOfflineArtifactKind.EXECUTIONS_CSV,
            }
            else DEPLOYMENT_FRONTIER_OFFLINE_JSON_MEDIA_TYPE,
            payload,
            kind=kind,
        )
        for artifact_id, path, kind, payload in payloads
    )


def _check(
    check_id: str,
    plane: DeploymentFrontierOfflineCheckPlane | str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> DeploymentFrontierOfflineCheck:
    return deployment_frontier_offline_check(check_id, plane, passed, observed, required, detail)


def _bundle_address(bundle: DeploymentFrontierOfflineBundle) -> str:
    return content_hash(
        bundle.manifest_dict(include_payloads=False), prefix="deployment-frontier-offline-bundle"
    )


def build_deployment_frontier_offline_bundle(
    runtime: Any | None = None,
    *,
    fixture: Any | None = None,
    bundle_id: str = "deployment-frontier-public-bundle",
    run_id: str = "deployment-frontier-offline-runtime",
) -> DeploymentFrontierOfflineBundle:
    """Materialize a deterministic public D16 handoff from the source runtime."""

    require_non_empty(bundle_id, "bundle_id")
    require_non_empty(run_id, "run_id")
    selected_fixture = fixture or default_deployment_frontier_fixture()
    source_runtime = runtime or run_deployment_frontier_runtime(selected_fixture, run_id=run_id)
    evaluation = _component(source_runtime, "evaluation")
    runtime_projection = _stable_runtime_projection(source_runtime)
    payloads = _component_payloads(source_runtime, selected_fixture, evaluation, runtime_projection)
    artifacts = _build_artifacts(payloads)
    artifact_by_id = {item.artifact_id: item for item in artifacts}
    denominator = _denominator_index(selected_fixture, evaluation, runtime_projection)
    stage_index = _stage_index(runtime_projection)
    operation_index = _operation_index(evaluation)
    public_key_index = _public_key_index(selected_fixture, runtime_projection)
    issue_index = _issue_index(evaluation)
    checks = (
        _check(
            "artifact-inventory",
            "manifest",
            len(artifacts) == DEPLOYMENT_FRONTIER_OFFLINE_ARTIFACT_COUNT,
            len(artifacts),
            DEPLOYMENT_FRONTIER_OFFLINE_ARTIFACT_COUNT,
            "all D16 planes, indexes, and exports are inventoried",
        ),
        _check(
            "artifact-identities-unique",
            "closure",
            len(artifact_by_id) == len(artifacts),
            len(artifact_by_id),
            len(artifacts),
            "artifact identifiers are unique",
        ),
        _check(
            "artifact-paths-unique",
            "closure",
            len({item.relative_path for item in artifacts}) == len(artifacts),
            len({item.relative_path for item in artifacts}),
            len(artifacts),
            "artifact paths are unique",
        ),
        _check(
            "artifact-addresses-present",
            "artifact",
            all(
                item.content_address.startswith(f"{DEPLOYMENT_FRONTIER_OFFLINE_ARTIFACT_PREFIX}:")
                for item in artifacts
            ),
            sum(
                item.content_address.startswith(f"{DEPLOYMENT_FRONTIER_OFFLINE_ARTIFACT_PREFIX}:")
                for item in artifacts
            ),
            len(artifacts),
            "every artifact is addressed over exact bytes",
        ),
        _check(
            "artifact-payloads-present",
            "artifact",
            all(item.payload is not None for item in artifacts),
            sum(item.payload is not None for item in artifacts),
            len(artifacts),
            "every artifact is materializable",
        ),
        _check(
            "safe-artifact-paths",
            "security",
            all(_safe_relative_path(item.relative_path) for item in artifacts),
            True,
            True,
            "all paths are relative and traversal-free",
        ),
        _check(
            "public-json-boundary",
            "public_boundary",
            all(
                not _has_forbidden_key(json.loads(item.payload or "{}"))
                and not contains_private_key(json.loads(item.payload or "{}"))
                for item in artifacts
                if item.media_type == DEPLOYMENT_FRONTIER_OFFLINE_JSON_MEDIA_TYPE
            ),
            True,
            True,
            "JSON payloads contain no prohibited public-surface keys",
        ),
        _check(
            "source-denominator",
            "denominator",
            len(selected_fixture.sources) == DEPLOYMENT_FRONTIER_OFFLINE_SOURCE_COUNT,
            len(selected_fixture.sources),
            DEPLOYMENT_FRONTIER_OFFLINE_SOURCE_COUNT,
            "five HTTPS source receipts are conserved",
        ),
        _check(
            "record-denominator",
            "denominator",
            len(selected_fixture.records) == DEPLOYMENT_FRONTIER_OFFLINE_RECORD_COUNT,
            len(selected_fixture.records),
            DEPLOYMENT_FRONTIER_OFFLINE_RECORD_COUNT,
            "sixteen deployment records are conserved",
        ),
        _check(
            "positive-denominator",
            "denominator",
            len(selected_fixture.positive_records) == DEPLOYMENT_FRONTIER_OFFLINE_POSITIVE_COUNT,
            len(selected_fixture.positive_records),
            DEPLOYMENT_FRONTIER_OFFLINE_POSITIVE_COUNT,
            "one positive path exists per operation",
        ),
        _check(
            "control-denominator",
            "denominator",
            len(selected_fixture.control_records) == DEPLOYMENT_FRONTIER_OFFLINE_CONTROL_COUNT,
            len(selected_fixture.control_records),
            DEPLOYMENT_FRONTIER_OFFLINE_CONTROL_COUNT,
            "three controls exist per operation",
        ),
        _check(
            "operation-denominator",
            "denominator",
            len(operation_index["operations"]) == DEPLOYMENT_FRONTIER_OFFLINE_OPERATION_COUNT
            and operation_index["balanced"],
            operation_index["operations"],
            "four balanced operations",
            "operation families are balanced",
        ),
        _check(
            "execution-denominator",
            "evaluation",
            len(evaluation.executions) == DEPLOYMENT_FRONTIER_OFFLINE_EXECUTION_COUNT,
            len(evaluation.executions),
            DEPLOYMENT_FRONTIER_OFFLINE_EXECUTION_COUNT,
            "every record produces one execution",
        ),
        _check(
            "evaluation-check-denominator",
            "evaluation",
            len(evaluation.checks) == DEPLOYMENT_FRONTIER_OFFLINE_EVALUATION_CHECK_COUNT,
            len(evaluation.checks),
            DEPLOYMENT_FRONTIER_OFFLINE_EVALUATION_CHECK_COUNT,
            "evaluation checks are conserved",
        ),
        _check(
            "evaluation-accepted",
            "evaluation",
            bool(evaluation.accepted),
            evaluation.accepted,
            True,
            "positive and control execution semantics are accepted",
        ),
        _check(
            "runtime-stage-denominator",
            "runtime",
            len(runtime_projection.get("stages", ())) == DEPLOYMENT_FRONTIER_OFFLINE_STAGE_COUNT,
            len(runtime_projection.get("stages", ())),
            DEPLOYMENT_FRONTIER_OFFLINE_STAGE_COUNT,
            "the ordered D16 runtime trace is complete",
        ),
        _check(
            "runtime-stage-sequence",
            "runtime",
            stage_index["ordered"],
            stage_index["sequence"],
            list(range(1, DEPLOYMENT_FRONTIER_OFFLINE_STAGE_COUNT + 1)),
            "runtime stages are contiguous",
        ),
        _check(
            "runtime-root-address",
            "runtime",
            artifact_by_id["runtime"].content_address.startswith(
                f"{DEPLOYMENT_FRONTIER_OFFLINE_ARTIFACT_PREFIX}:"
            ),
            artifact_by_id["runtime"].content_address,
            "exact-byte runtime artifact",
            "runtime payload is addressed",
        ),
        _check(
            "stage-index-join",
            "index",
            stage_index["stage_count"] == DEPLOYMENT_FRONTIER_OFFLINE_STAGE_COUNT
            and stage_index["ordered"],
            stage_index,
            {"stage_count": DEPLOYMENT_FRONTIER_OFFLINE_STAGE_COUNT, "ordered": True},
            "stage index closes runtime order",
        ),
        _check(
            "denominator-index-join",
            "index",
            all(
                denominator.get(key) == expected
                for key, expected in {
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
            "D16 denominator index",
            "denominator index closes every count",
        ),
        _check(
            "operation-index-join",
            "index",
            operation_index["balanced"] and operation_index["operation_count"] == 4,
            operation_index,
            {"balanced": True, "operation_count": 4},
            "operation index is balanced",
        ),
        _check(
            "issue-index-join",
            "index",
            issue_index["issue_count"] == 13,
            issue_index["issue_count"],
            13,
            "all negative-control issue categories are indexed",
        ),
        _check(
            "public-key-index",
            "public_boundary",
            public_key_index["accepted"] and not public_key_index["forbidden_keys"],
            public_key_index["forbidden_keys"],
            (),
            "public key inventory is closed",
        ),
        _check(
            "source-uris-https",
            "public_boundary",
            all(item.uri.startswith("https://") for item in selected_fixture.sources),
            True,
            True,
            "source receipts use HTTPS",
        ),
        _check(
            "component-addresses",
            "artifact",
            all(
                item.content_address.startswith(f"{DEPLOYMENT_FRONTIER_OFFLINE_ARTIFACT_PREFIX}:")
                for item in artifacts
            ),
            True,
            True,
            "component planes retain exact addresses",
        ),
        _check(
            "component-accepted",
            "release",
            all(
                bool(getattr(source_runtime, attr, True))
                for attr in (
                    "audit",
                    "evaluation",
                    "quality",
                    "integrity",
                    "assurance",
                    "release_checks",
                    "trace",
                )
            ),
            True,
            True,
            "release-critical component planes are accepted",
        ),
        _check(
            "fixture-index-join",
            "index",
            artifact_by_id["fixture-index"].byte_count > 0,
            artifact_by_id["fixture-index"].byte_count,
            ">0",
            "fixture identity index is materialized",
        ),
        _check(
            "review-export",
            "release",
            artifact_by_id["review-csv"].line_count == DEPLOYMENT_FRONTIER_OFFLINE_RECORD_COUNT + 1,
            artifact_by_id["review-csv"].line_count,
            DEPLOYMENT_FRONTIER_OFFLINE_RECORD_COUNT + 1,
            "review export contains one header and one row per record",
        ),
        _check(
            "source-export",
            "release",
            artifact_by_id["sources-csv"].line_count
            == DEPLOYMENT_FRONTIER_OFFLINE_SOURCE_COUNT + 1,
            artifact_by_id["sources-csv"].line_count,
            DEPLOYMENT_FRONTIER_OFFLINE_SOURCE_COUNT + 1,
            "source export contains one header and one row per receipt",
        ),
        _check(
            "runtime-accepted",
            "release",
            bool(source_runtime.accepted),
            source_runtime.accepted,
            True,
            "full deployment runtime is accepted",
        ),
        _check(
            "boundary-keys",
            "security",
            not _has_forbidden_key(
                {"artifacts": [item.to_dict(include_payload=False) for item in artifacts]}
            ),
            True,
            True,
            "manifest metadata is public",
        ),
        _check(
            "bundle-closure",
            "closure",
            len(artifacts) == 51 and len({item.artifact_id for item in artifacts}) == 51,
            len(artifacts),
            51,
            "D16 handoff closes its 51-file inventory",
        ),
    )
    accepted = bool(all(item.passed for item in checks))
    state = (
        DeploymentFrontierOfflineBundleState.READY
        if accepted
        else DeploymentFrontierOfflineBundleState.BLOCKED
    )
    body = {
        "bundle_id": bundle_id,
        "version": DEPLOYMENT_FRONTIER_OFFLINE_BUNDLE_VERSION,
        "boundary": DEPLOYMENT_FRONTIER_OFFLINE_BOUNDARY,
        "fixture_id": selected_fixture.fixture_id,
        "run_id": run_id,
        "state": state,
        "accepted": accepted,
        "artifacts": artifacts,
        "checks": checks,
        "runtime_address": artifact_by_id["runtime"].content_address,
        "stage_count": len(runtime_projection.get("stages", ())),
        "warning_count": sum(not item.passed for item in checks),
    }
    bundle = DeploymentFrontierOfflineBundle(
        **body,
        content_address="pending",
    )
    return DeploymentFrontierOfflineBundle(
        **body,
        content_address=_bundle_address(bundle),
    )


def deployment_frontier_offline_manifest_text(bundle: DeploymentFrontierOfflineBundle) -> str:
    """Return the root manifest in the exact bytes used on disk."""

    return canonical_json(bundle.to_dict(include_payloads=False)) + "\n"


def write_deployment_frontier_offline_bundle(
    bundle: DeploymentFrontierOfflineBundle, destination: str | Path
) -> Path:
    """Write a closed bundle directory using only relative manifest paths."""

    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    (root / DEPLOYMENT_FRONTIER_OFFLINE_MANIFEST).write_text(
        deployment_frontier_offline_manifest_text(bundle), encoding="utf-8"
    )
    for artifact in bundle.artifacts:
        path = root / Path(*PurePosixPath(artifact.relative_path).parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((artifact.payload or "").encode("utf-8"))
    return root


def _manifest_mapping(destination: str | Path) -> tuple[Path, dict[str, Any]]:
    root = Path(destination)
    manifest_path = root / DEPLOYMENT_FRONTIER_OFFLINE_MANIFEST
    if not manifest_path.is_file():
        raise ValidationError("deployment offline manifest is missing")
    try:
        value = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"deployment offline manifest is unreadable: {exc}") from exc
    if not isinstance(value, dict):
        raise ValidationError("deployment offline manifest must be an object")
    return root, value


def load_deployment_frontier_offline_bundle(
    destination: str | Path, *, include_payloads: bool = True
) -> DeploymentFrontierOfflineBundle:
    """Load the manifest and exact payload bytes without executing D16."""

    root, manifest = _manifest_mapping(destination)
    raw_artifacts = manifest.get("artifacts")
    raw_checks = manifest.get("checks")
    if not isinstance(raw_artifacts, list) or not isinstance(raw_checks, list):
        raise ValidationError("deployment offline manifest artifacts and checks must be arrays")
    artifacts: list[DeploymentFrontierOfflineArtifact] = []
    for item in raw_artifacts:
        if not isinstance(item, Mapping):
            raise ValidationError("deployment offline artifact entry must be an object")
        relative_path = str(item.get("relative_path", ""))
        if not _safe_relative_path(relative_path):
            raise ValidationError("deployment offline artifact path is unsafe")
        path = root / Path(*PurePosixPath(relative_path).parts)
        payload = path.read_text(encoding="utf-8") if include_payloads and path.is_file() else None
        try:
            kind = DeploymentFrontierOfflineArtifactKind(str(item["kind"]))
            artifacts.append(
                DeploymentFrontierOfflineArtifact(
                    str(item["artifact_id"]),
                    relative_path,
                    str(item["media_type"]),
                    kind,
                    int(item["byte_count"]),
                    int(item["line_count"]),
                    str(item["content_address"]),
                    payload,
                )
            )
        except (KeyError, TypeError, ValueError, OSError) as exc:
            raise ValidationError(f"deployment offline artifact entry is invalid: {exc}") from exc
    checks = tuple(
        DeploymentFrontierOfflineCheck(
            check_id=str(item["check_id"]),
            plane=DeploymentFrontierOfflineCheckPlane(str(item["plane"])),
            passed=bool(item["passed"]),
            observed=item.get("observed"),
            required=item.get("required"),
            detail=str(item["detail"]),
            content_address=str(item["content_address"]),
        )
        for item in raw_checks
        if isinstance(item, Mapping)
    )
    try:
        state = DeploymentFrontierOfflineBundleState(str(manifest["state"]))
        return DeploymentFrontierOfflineBundle(
            bundle_id=str(manifest["bundle_id"]),
            version=str(manifest["version"]),
            boundary=str(manifest["boundary"]),
            fixture_id=str(manifest["fixture_id"]),
            run_id=str(manifest["run_id"]),
            state=state,
            accepted=bool(manifest["accepted"]),
            artifacts=tuple(artifacts),
            checks=checks,
            runtime_address=str(manifest["runtime_address"]),
            stage_count=int(manifest["stage_count"]),
            warning_count=int(manifest["warning_count"]),
            content_address=str(manifest["content_address"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError(f"deployment offline manifest has invalid shape: {exc}") from exc


def verify_deployment_frontier_offline_bundle(
    destination: str | Path,
) -> DeploymentFrontierOfflineVerification:
    """Verify manifest identity, exact file bytes, and filesystem completeness."""

    root, manifest = _manifest_mapping(destination)
    bundle = load_deployment_frontier_offline_bundle(root, include_payloads=True)
    checks: list[DeploymentFrontierOfflineCheck] = []

    def verify_check(
        check_id: str, passed: bool, observed: Any, required: Any, detail: str
    ) -> DeploymentFrontierOfflineCheck:
        return _check(check_id, "artifact", passed, observed, required, detail)

    checks.append(
        verify_check(
            "manifest-version",
            manifest.get("version") == DEPLOYMENT_FRONTIER_OFFLINE_BUNDLE_VERSION,
            manifest.get("version"),
            DEPLOYMENT_FRONTIER_OFFLINE_BUNDLE_VERSION,
            "manifest version is recognized",
        )
    )
    checks.append(
        verify_check(
            "manifest-address",
            manifest.get("content_address") == _bundle_address(bundle),
            manifest.get("content_address"),
            bundle.content_address,
            "root address reconstructs from manifest fields",
        )
    )
    expected_files = {
        DEPLOYMENT_FRONTIER_OFFLINE_MANIFEST,
        *(item.relative_path for item in bundle.artifacts),
    }
    actual_files = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
    checks.append(
        verify_check(
            "filesystem-closure",
            actual_files == expected_files,
            sorted(actual_files),
            sorted(expected_files),
            "filesystem contains exactly the manifest inventory",
        )
    )
    checks.append(
        verify_check(
            "no-symlinks",
            not any(path.is_symlink() for path in root.rglob("*")),
            True,
            True,
            "offline bundle does not depend on symlinks",
        )
    )
    checks.append(
        verify_check(
            "manifest-artifact-count",
            bundle.artifact_count == DEPLOYMENT_FRONTIER_OFFLINE_ARTIFACT_COUNT,
            bundle.artifact_count,
            DEPLOYMENT_FRONTIER_OFFLINE_ARTIFACT_COUNT,
            "manifest conserves D16 artifact count",
        )
    )
    for artifact in bundle.artifacts:
        path = root / Path(*PurePosixPath(artifact.relative_path).parts)
        raw = path.read_bytes() if path.is_file() else b""
        checks.append(
            verify_check(
                f"artifact-bytes:{artifact.artifact_id}",
                path.is_file()
                and hash_bytes(raw, prefix=DEPLOYMENT_FRONTIER_OFFLINE_ARTIFACT_PREFIX)
                == artifact.content_address
                and len(raw) == artifact.byte_count
                and len(raw.decode("utf-8").splitlines()) == artifact.line_count,
                {
                    "exists": path.is_file(),
                    "byte_count": len(raw),
                    "address": hash_bytes(raw, prefix=DEPLOYMENT_FRONTIER_OFFLINE_ARTIFACT_PREFIX),
                },
                {
                    "byte_count": artifact.byte_count,
                    "address": artifact.content_address,
                    "line_count": artifact.line_count,
                },
                "artifact bytes match the manifest receipt",
            )
        )
    accepted = bool(bundle.accepted and all(item.passed for item in checks))
    return DeploymentFrontierOfflineVerification(
        bundle.bundle_id,
        accepted,
        tuple(checks),
        content_hash(
            {"bundle_id": bundle.bundle_id, "checks": checks, "accepted": accepted},
            prefix="deployment-frontier-offline-verification",
        ),
    )


__all__ = [
    "DEPLOYMENT_FRONTIER_OFFLINE_CSV_MEDIA_TYPE",
    "DEPLOYMENT_FRONTIER_OFFLINE_FORBIDDEN_KEYS",
    "DEPLOYMENT_FRONTIER_OFFLINE_JSON_MEDIA_TYPE",
    "build_deployment_frontier_offline_bundle",
    "deployment_frontier_offline_manifest_text",
    "load_deployment_frontier_offline_bundle",
    "verify_deployment_frontier_offline_bundle",
    "write_deployment_frontier_offline_bundle",
]
