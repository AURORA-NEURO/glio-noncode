"""Build and verify an exact-byte D15 workbench-release handoff.

The builder is intentionally independent from filesystem state.  It executes
the existing public aggregate runtime, normalizes only host timing variance,
projects every component through the public boundary, and writes a closed
manifest plus immutable payload files.  A reviewer can therefore inspect the
fixture, every release plane, the 49-stage trace, and the derived indexes
without importing a producer process.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from .errors import ValidationError
from .module_fabric_support import contains_private_key
from .run_workspace import _has_forbidden_key
from .serialization import canonical_json, content_hash, hash_bytes, jsonable, require_non_empty
from .workbench_release_frontier_offline_contracts import (
    WORKBENCH_RELEASE_OFFLINE_ARTIFACT_COUNT,
    WORKBENCH_RELEASE_OFFLINE_ARTIFACT_PREFIX,
    WORKBENCH_RELEASE_OFFLINE_BOUNDARY,
    WORKBENCH_RELEASE_OFFLINE_MANIFEST,
    WORKBENCH_RELEASE_OFFLINE_BUNDLE_VERSION,
    WorkbenchReleaseOfflineArtifact,
    WorkbenchReleaseOfflineArtifactKind,
    WorkbenchReleaseOfflineBundle,
    WorkbenchReleaseOfflineBundleState,
    WorkbenchReleaseOfflineCheck,
    WorkbenchReleaseOfflineCheckPlane,
    workbench_release_offline_check,
)
from .workbench_release_frontier_public_data import default_workbench_release_frontier_fixture
from .workbench_release_frontier_runtime import run_workbench_release_runtime

WORKBENCH_RELEASE_OFFLINE_JSON_MEDIA_TYPE = "application/json"
WORKBENCH_RELEASE_OFFLINE_CSV_MEDIA_TYPE = "text/csv"

_FORBIDDEN_OFFLINE_KEYS = frozenset(
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
        "individual_id",
        "language",
        "medical_record_number",
        "model",
        "model_id",
        "model_name",
        "model_version",
        "participant_id",
        "patient_id",
        "phone",
        "primary_agent",
        "primary_agent_id",
        "produced_by",
        "programming_language",
        "sample_id",
        "subject_id",
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
    value = jsonable(value)
    if isinstance(value, Mapping):
        return {
            str(key): _public_projection(item)
            for key, item in value.items()
            if str(key).casefold() not in _FORBIDDEN_OFFLINE_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_public_projection(item) for item in value]
    return value


def _public_value(value: Any) -> Any:
    projected = _public_projection(value)
    if _has_forbidden_key(projected) or contains_private_key(projected):
        raise ValidationError("workbench release offline bundle crosses the public boundary")
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
    kind: WorkbenchReleaseOfflineArtifactKind,
) -> WorkbenchReleaseOfflineArtifact:
    path = str(relative_path)
    if not _safe_relative_path(path):
        raise ValidationError(f"unsafe workbench bundle path: {path!r}")
    text = (
        _json_text(payload)
        if media_type == WORKBENCH_RELEASE_OFFLINE_JSON_MEDIA_TYPE
        else str(payload).rstrip("\n") + "\n"
    )
    raw = text.encode("utf-8")
    return WorkbenchReleaseOfflineArtifact(
        artifact_id=_safe_component(artifact_id, "artifact_id"),
        relative_path=path,
        media_type=media_type,
        kind=kind,
        byte_count=len(raw),
        line_count=_line_count(text),
        content_address=hash_bytes(raw, prefix=WORKBENCH_RELEASE_OFFLINE_ARTIFACT_PREFIX),
        payload=text,
    )


def _stable_runtime_projection(runtime: Any) -> dict[str, Any]:
    """Remove perf-counter variance while retaining the full ordered trace."""

    value = jsonable(runtime)
    if not isinstance(value, dict):
        raise ValidationError("workbench runtime must serialize to an object")
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
    value["content_address"] = content_hash(value, prefix="workbench-release-runtime-public")
    return value


def _component(runtime: Any, attribute: str) -> Any:
    value = getattr(runtime, attribute, None)
    if value is None:
        raise ValidationError(f"workbench runtime is missing component {attribute!r}")
    return value


def _stage_index(runtime_projection: Mapping[str, Any]) -> dict[str, Any]:
    stages = runtime_projection.get("stages", ())
    rows = tuple(
        {
            "sequence": int(item.get("sequence", index)),
            "stage_id": str(item.get("stage_id", "")),
            "state": str(item.get("state", "")),
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
    return body | {"content_address": content_hash(body, prefix="workbench-release-stage-index")}


def _denominator_index(
    fixture: Any, evaluation: Any, runtime_projection: Mapping[str, Any], observability: Any
) -> dict[str, Any]:
    records = tuple(fixture.records)
    operations = tuple(sorted({item.operation.value for item in records}))
    body = {
        "sources": len(fixture.sources),
        "records": len(records),
        "positive_records": len(fixture.positive_records),
        "control_records": len(fixture.control_records),
        "operations": len(operations),
        "executions": len(evaluation.executions),
        "evaluation_checks": len(evaluation.checks),
        "runtime_stages": len(runtime_projection.get("stages", ())),
        "observability_events": len(getattr(observability, "observations", ())),
        "operation_ids": operations,
    }
    return body | {
        "content_address": content_hash(body, prefix="workbench-release-denominator-index")
    }


def _operation_index(evaluation: Any) -> dict[str, Any]:
    rows: dict[str, list[str]] = {}
    for item in evaluation.executions:
        rows.setdefault(item.operation.value, []).append(item.record_id)
    body = {
        "operations": {key: tuple(value) for key, value in sorted(rows.items())},
        "balanced": len({len(value) for value in rows.values()}) == 1,
    }
    return body | {
        "content_address": content_hash(body, prefix="workbench-release-operation-index")
    }


def _public_key_index(fixture: Any, runtime_projection: Mapping[str, Any]) -> dict[str, Any]:
    def keys(value: Any) -> tuple[str, ...]:
        if isinstance(value, Mapping):
            result: set[str] = set()
            for key, item in value.items():
                result.add(str(key))
                result.update(keys(item))
            return tuple(sorted(result))
        if isinstance(value, (list, tuple)):
            result: set[str] = set()
            for item in value:
                result.update(keys(item))
            return tuple(sorted(result))
        return ()

    all_keys = set(keys(fixture)) | set(keys(runtime_projection))
    forbidden = tuple(sorted(key for key in all_keys if key.casefold() in _FORBIDDEN_OFFLINE_KEYS))
    body = {
        "key_count": len(all_keys),
        "public_key_count": len(all_keys - set(forbidden)),
        "forbidden_keys": forbidden,
        "accepted": not forbidden,
    }
    return body | {
        "content_address": content_hash(body, prefix="workbench-release-public-key-index")
    }


def _fixture_index(fixture: Any) -> dict[str, Any]:
    """Build a small address-only index for the public fixture identity set."""

    sources = tuple(
        {"source_id": source.source_id, "content_address": source.content_address}
        for source in fixture.sources
    )
    records = tuple(
        {
            "record_id": record.record_id,
            "operation": record.operation.value,
            "content_address": record.content_address,
        }
        for record in fixture.records
    )
    body = {
        "fixture_id": fixture.fixture_id,
        "source_count": len(sources),
        "record_count": len(records),
        "sources": sources,
        "records": records,
    }
    return body | {"content_address": content_hash(body, prefix="workbench-release-fixture-index")}


def _review_csv(evaluation: Any) -> str:
    stream = io.StringIO()
    fields = (
        "record_id",
        "capability",
        "operation",
        "role",
        "expected_state",
        "observed_state",
        "issue_codes",
        "content_address",
    )
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in evaluation.executions:
        writer.writerow(
            {
                "record_id": row.record_id,
                "capability": row.capability,
                "operation": row.operation.value,
                "role": row.role.value,
                "expected_state": row.expected_state.value,
                "observed_state": row.observed_state.value,
                "issue_codes": "|".join(row.issue_codes),
                "content_address": row.content_address,
            }
        )
    return stream.getvalue()


def _component_payloads(
    runtime: Any, fixture: Any, evaluation: Any, runtime_projection: dict[str, Any]
) -> tuple[tuple[str, str, WorkbenchReleaseOfflineArtifactKind, Any], ...]:
    """Return the stable public payload inventory in dependency order."""

    definitions: tuple[tuple[str, str, WorkbenchReleaseOfflineArtifactKind, str], ...] = (
        ("fixture", "fixture.json", WorkbenchReleaseOfflineArtifactKind.FIXTURE, "fixture"),
        (
            "data-audit",
            "planes/data-audit.json",
            WorkbenchReleaseOfflineArtifactKind.DATA_AUDIT,
            "audit",
        ),
        (
            "adapters",
            "planes/adapters.json",
            WorkbenchReleaseOfflineArtifactKind.ADAPTERS,
            "adapters",
        ),
        ("schema", "planes/schema.json", WorkbenchReleaseOfflineArtifactKind.SCHEMA, "schema"),
        (
            "evaluation",
            "planes/evaluation.json",
            WorkbenchReleaseOfflineArtifactKind.EVALUATION,
            "evaluation",
        ),
        ("metrics", "planes/metrics.json", WorkbenchReleaseOfflineArtifactKind.METRICS, "metrics"),
        ("policy", "planes/policy.json", WorkbenchReleaseOfflineArtifactKind.POLICY, "policy"),
        ("lineage", "planes/lineage.json", WorkbenchReleaseOfflineArtifactKind.LINEAGE, "lineage"),
        (
            "reconciliation",
            "planes/reconciliation.json",
            WorkbenchReleaseOfflineArtifactKind.RECONCILIATION,
            "reconciliation",
        ),
        ("quality", "planes/quality.json", WorkbenchReleaseOfflineArtifactKind.QUALITY, "quality"),
        ("replay", "planes/replay.json", WorkbenchReleaseOfflineArtifactKind.REPLAY, "replay"),
        ("view", "planes/view.json", WorkbenchReleaseOfflineArtifactKind.VIEW, "view"),
        (
            "review-queue",
            "planes/review-queue.json",
            WorkbenchReleaseOfflineArtifactKind.REVIEW_QUEUE,
            "queue",
        ),
        ("handoff", "planes/handoff.json", WorkbenchReleaseOfflineArtifactKind.HANDOFF, "handoff"),
        (
            "integrity",
            "planes/integrity.json",
            WorkbenchReleaseOfflineArtifactKind.INTEGRITY,
            "integrity",
        ),
        ("depth", "planes/depth.json", WorkbenchReleaseOfflineArtifactKind.DEPTH, "depth"),
        (
            "controls",
            "planes/controls.json",
            WorkbenchReleaseOfflineArtifactKind.CONTROLS,
            "controls",
        ),
        (
            "validation",
            "planes/validation.json",
            WorkbenchReleaseOfflineArtifactKind.VALIDATION,
            "validation",
        ),
        (
            "evidence",
            "planes/evidence.json",
            WorkbenchReleaseOfflineArtifactKind.EVIDENCE,
            "evidence",
        ),
        ("access", "planes/access.json", WorkbenchReleaseOfflineArtifactKind.ACCESS, "access"),
        (
            "failure-injection",
            "planes/failure-injection.json",
            WorkbenchReleaseOfflineArtifactKind.FAILURE_INJECTION,
            "failure_injection",
        ),
        (
            "diagnostics",
            "planes/diagnostics.json",
            WorkbenchReleaseOfflineArtifactKind.DIAGNOSTICS,
            "diagnostics",
        ),
        (
            "artifacts",
            "planes/artifacts.json",
            WorkbenchReleaseOfflineArtifactKind.ARTIFACTS,
            "artifacts",
        ),
        ("release", "planes/release.json", WorkbenchReleaseOfflineArtifactKind.RELEASE, "release"),
        ("summary", "planes/summary.json", WorkbenchReleaseOfflineArtifactKind.SUMMARY, "summary"),
        (
            "provenance",
            "planes/provenance.json",
            WorkbenchReleaseOfflineArtifactKind.PROVENANCE,
            "provenance",
        ),
        (
            "source-registry",
            "planes/source-registry.json",
            WorkbenchReleaseOfflineArtifactKind.SOURCE_REGISTRY,
            "source_registry",
        ),
        (
            "freshness",
            "planes/freshness.json",
            WorkbenchReleaseOfflineArtifactKind.FRESHNESS,
            "freshness",
        ),
        (
            "compatibility",
            "planes/compatibility.json",
            WorkbenchReleaseOfflineArtifactKind.COMPATIBILITY,
            "compatibility",
        ),
        (
            "release-checks",
            "planes/release-checks.json",
            WorkbenchReleaseOfflineArtifactKind.RELEASE_CHECKS,
            "release_checks",
        ),
        (
            "execution-plan",
            "planes/execution-plan.json",
            WorkbenchReleaseOfflineArtifactKind.EXECUTION_PLAN,
            "execution_plan",
        ),
        (
            "run-manifest",
            "planes/run-manifest.json",
            WorkbenchReleaseOfflineArtifactKind.RUN_MANIFEST,
            "run_manifest",
        ),
        (
            "audit-log",
            "planes/audit-log.json",
            WorkbenchReleaseOfflineArtifactKind.AUDIT_LOG,
            "audit_log",
        ),
        (
            "transcript",
            "planes/transcript.json",
            WorkbenchReleaseOfflineArtifactKind.TRANSCRIPT,
            "transcript",
        ),
        ("report", "planes/report.json", WorkbenchReleaseOfflineArtifactKind.REPORT, "report"),
        (
            "review-sla",
            "planes/review-sla.json",
            WorkbenchReleaseOfflineArtifactKind.REVIEW_SLA,
            "review_sla",
        ),
        (
            "review-protocol",
            "planes/review-protocol.json",
            WorkbenchReleaseOfflineArtifactKind.REVIEW_PROTOCOL,
            "review_protocol",
        ),
        (
            "claim-boundary",
            "planes/claim-boundary.json",
            WorkbenchReleaseOfflineArtifactKind.CLAIM_BOUNDARY,
            "claim_boundary",
        ),
        (
            "recovery",
            "planes/recovery.json",
            WorkbenchReleaseOfflineArtifactKind.RECOVERY,
            "recovery",
        ),
        (
            "performance",
            "planes/performance.json",
            WorkbenchReleaseOfflineArtifactKind.PERFORMANCE,
            "performance",
        ),
        (
            "operational",
            "planes/operational.json",
            WorkbenchReleaseOfflineArtifactKind.OPERATIONAL,
            "operational",
        ),
        (
            "compliance",
            "planes/compliance.json",
            WorkbenchReleaseOfflineArtifactKind.COMPLIANCE,
            "compliance",
        ),
        ("query", "planes/query.json", WorkbenchReleaseOfflineArtifactKind.QUERY, "query"),
        (
            "partitions",
            "planes/partitions.json",
            WorkbenchReleaseOfflineArtifactKind.PARTITIONS,
            "partitions",
        ),
        (
            "scenario",
            "planes/scenario.json",
            WorkbenchReleaseOfflineArtifactKind.SCENARIO,
            "scenario",
        ),
        (
            "resources",
            "planes/resources.json",
            WorkbenchReleaseOfflineArtifactKind.RESOURCES,
            "resources",
        ),
        ("bundle", "planes/bundle.json", WorkbenchReleaseOfflineArtifactKind.BUNDLE, "bundle"),
        (
            "observability",
            "planes/observability.json",
            WorkbenchReleaseOfflineArtifactKind.OBSERVABILITY,
            "observability",
        ),
    )
    rows: list[tuple[str, str, WorkbenchReleaseOfflineArtifactKind, Any]] = [
        (key, path, kind, fixture if key == "fixture" else _component(runtime, attribute))
        for key, path, kind, attribute in definitions
    ]
    rows.extend(
        (
            (
                "runtime",
                "runtime/runtime.json",
                WorkbenchReleaseOfflineArtifactKind.RUNTIME,
                runtime_projection,
            ),
            (
                "stage-index",
                "indexes/stage-index.json",
                WorkbenchReleaseOfflineArtifactKind.STAGE_INDEX,
                _stage_index(runtime_projection),
            ),
            (
                "denominator-index",
                "indexes/denominator-index.json",
                WorkbenchReleaseOfflineArtifactKind.DENOMINATOR_INDEX,
                _denominator_index(
                    fixture, evaluation, runtime_projection, _component(runtime, "observability")
                ),
            ),
            (
                "operation-index",
                "indexes/operation-index.json",
                WorkbenchReleaseOfflineArtifactKind.OPERATION_INDEX,
                _operation_index(evaluation),
            ),
            (
                "public-key-index",
                "indexes/public-key-index.json",
                WorkbenchReleaseOfflineArtifactKind.PUBLIC_KEY_INDEX,
                _public_key_index(fixture, runtime_projection),
            ),
            (
                "fixture-index",
                "indexes/fixture-index.json",
                WorkbenchReleaseOfflineArtifactKind.FIXTURE_INDEX,
                _fixture_index(fixture),
            ),
            (
                "review-csv",
                "exports/review.csv",
                WorkbenchReleaseOfflineArtifactKind.REVIEW_CSV,
                _review_csv(evaluation),
            ),
            (
                "data-dictionary",
                "exports/data-dictionary.json",
                WorkbenchReleaseOfflineArtifactKind.DATA_DICTIONARY,
                {
                    "columns": (
                        "record_id",
                        "capability",
                        "operation",
                        "role",
                        "expected_state",
                        "observed_state",
                        "issue_codes",
                        "content_address",
                    ),
                    "row_count": len(evaluation.executions),
                    "addressed": True,
                },
            ),
        )
    )
    return tuple(rows)


def _build_artifacts(
    payloads: tuple[tuple[str, str, WorkbenchReleaseOfflineArtifactKind, Any], ...],
) -> tuple[WorkbenchReleaseOfflineArtifact, ...]:
    return tuple(
        _artifact(
            artifact_id,
            path,
            WORKBENCH_RELEASE_OFFLINE_CSV_MEDIA_TYPE
            if kind is WorkbenchReleaseOfflineArtifactKind.REVIEW_CSV
            else WORKBENCH_RELEASE_OFFLINE_JSON_MEDIA_TYPE,
            payload,
            kind=kind,
        )
        for artifact_id, path, kind, payload in payloads
    )


def _check(
    check_id: str,
    plane: WorkbenchReleaseOfflineCheckPlane,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> WorkbenchReleaseOfflineCheck:
    return workbench_release_offline_check(check_id, plane, passed, observed, required, detail)


def _bundle_address(bundle: WorkbenchReleaseOfflineBundle) -> str:
    return content_hash(
        bundle.manifest_dict(include_payloads=False), prefix="workbench-release-offline-bundle"
    )


def build_workbench_release_offline_bundle(
    runtime: Any | None = None,
    *,
    fixture: Any | None = None,
    bundle_id: str = "workbench-release-public-bundle",
    run_id: str = "workbench-release-offline-runtime",
) -> WorkbenchReleaseOfflineBundle:
    """Materialize a deterministic public D15 bundle from the existing runtime."""

    require_non_empty(bundle_id, "bundle_id")
    require_non_empty(run_id, "run_id")
    selected_fixture = fixture or default_workbench_release_frontier_fixture()
    source_runtime = runtime or run_workbench_release_runtime(selected_fixture, run_id=run_id)
    evaluation = _component(source_runtime, "evaluation")
    runtime_projection = _stable_runtime_projection(source_runtime)
    payloads = _component_payloads(source_runtime, selected_fixture, evaluation, runtime_projection)
    artifacts = _build_artifacts(payloads)
    checks = (
        _check(
            "artifact-inventory",
            WorkbenchReleaseOfflineCheckPlane.MANIFEST,
            len(artifacts) == WORKBENCH_RELEASE_OFFLINE_ARTIFACT_COUNT,
            len(artifacts),
            WORKBENCH_RELEASE_OFFLINE_ARTIFACT_COUNT,
            "all D15 runtime and index artifacts are inventoried",
        ),
        _check(
            "artifact-identities-unique",
            WorkbenchReleaseOfflineCheckPlane.CLOSURE,
            len({item.artifact_id for item in artifacts}) == len(artifacts),
            len({item.artifact_id for item in artifacts}),
            len(artifacts),
            "artifact identifiers are unique",
        ),
        _check(
            "artifact-paths-unique",
            WorkbenchReleaseOfflineCheckPlane.CLOSURE,
            len({item.relative_path for item in artifacts}) == len(artifacts),
            len({item.relative_path for item in artifacts}),
            len(artifacts),
            "artifact paths are unique",
        ),
        _check(
            "artifact-addresses-present",
            WorkbenchReleaseOfflineCheckPlane.ARTIFACT,
            all(
                item.content_address.startswith(f"{WORKBENCH_RELEASE_OFFLINE_ARTIFACT_PREFIX}:")
                for item in artifacts
            ),
            sum(
                item.content_address.startswith(f"{WORKBENCH_RELEASE_OFFLINE_ARTIFACT_PREFIX}:")
                for item in artifacts
            ),
            len(artifacts),
            "every artifact is addressed over exact bytes",
        ),
        _check(
            "artifact-payloads-present",
            WorkbenchReleaseOfflineCheckPlane.ARTIFACT,
            all(item.payload is not None for item in artifacts),
            sum(item.payload is not None for item in artifacts),
            len(artifacts),
            "every artifact is materializable",
        ),
        _check(
            "safe-artifact-paths",
            WorkbenchReleaseOfflineCheckPlane.SECURITY,
            all(_safe_relative_path(item.relative_path) for item in artifacts),
            True,
            True,
            "all artifact paths are relative and traversal-free",
        ),
        _check(
            "public-json-boundary",
            WorkbenchReleaseOfflineCheckPlane.PUBLIC_BOUNDARY,
            all(
                not _has_forbidden_key(json.loads(item.payload or "{}"))
                and not contains_private_key(json.loads(item.payload or "{}"))
                for item in artifacts
                if item.media_type == WORKBENCH_RELEASE_OFFLINE_JSON_MEDIA_TYPE
            ),
            True,
            True,
            "JSON artifacts contain no private or attribution keys",
        ),
        _check(
            "fixture-source-denominator",
            WorkbenchReleaseOfflineCheckPlane.DENOMINATOR,
            len(selected_fixture.sources) == 5,
            len(selected_fixture.sources),
            5,
            "five HTTPS public source receipts are conserved",
        ),
        _check(
            "fixture-record-denominator",
            WorkbenchReleaseOfflineCheckPlane.DENOMINATOR,
            len(selected_fixture.records) == 16,
            len(selected_fixture.records),
            16,
            "sixteen workbench records are conserved",
        ),
        _check(
            "fixture-positive-denominator",
            WorkbenchReleaseOfflineCheckPlane.DENOMINATOR,
            len(selected_fixture.positive_records) == 4,
            len(selected_fixture.positive_records),
            4,
            "one positive path exists per operation",
        ),
        _check(
            "fixture-control-denominator",
            WorkbenchReleaseOfflineCheckPlane.DENOMINATOR,
            len(selected_fixture.control_records) == 12,
            len(selected_fixture.control_records),
            12,
            "three controls exist per operation",
        ),
        _check(
            "operation-denominator",
            WorkbenchReleaseOfflineCheckPlane.DENOMINATOR,
            len({item.operation for item in selected_fixture.records}) == 4,
            len({item.operation for item in selected_fixture.records}),
            4,
            "four operation families are retained",
        ),
        _check(
            "evaluation-execution-denominator",
            WorkbenchReleaseOfflineCheckPlane.RUNTIME,
            len(evaluation.executions) == 16,
            len(evaluation.executions),
            16,
            "every fixture row has one execution",
        ),
        _check(
            "evaluation-check-denominator",
            WorkbenchReleaseOfflineCheckPlane.RUNTIME,
            len(evaluation.checks) == 80,
            len(evaluation.checks),
            80,
            "all evaluation checks are retained",
        ),
        _check(
            "evaluation-accepted",
            WorkbenchReleaseOfflineCheckPlane.RUNTIME,
            evaluation.accepted,
            evaluation.accepted,
            True,
            "source evaluation is accepted",
        ),
        _check(
            "runtime-stage-denominator",
            WorkbenchReleaseOfflineCheckPlane.RUNTIME,
            len(source_runtime.stages) == 49,
            len(source_runtime.stages),
            49,
            "the ordered D15 runtime has 49 stages",
        ),
        _check(
            "runtime-address-present",
            WorkbenchReleaseOfflineCheckPlane.RUNTIME,
            str(runtime_projection.get("content_address", "")).startswith(
                "workbench-release-runtime-public:"
            ),
            runtime_projection.get("content_address"),
            "workbench-release-runtime-public address",
            "normalized runtime identity is retained",
        ),
        _check(
            "stage-index-closed",
            WorkbenchReleaseOfflineCheckPlane.INDEX,
            _stage_index(runtime_projection)["ordered"] is True,
            _stage_index(runtime_projection)["stage_count"],
            49,
            "stage index preserves complete order",
        ),
        _check(
            "denominator-index-closed",
            WorkbenchReleaseOfflineCheckPlane.INDEX,
            _denominator_index(
                selected_fixture,
                evaluation,
                runtime_projection,
                _component(source_runtime, "observability"),
            )["records"]
            == 16,
            16,
            16,
            "denominator index conserves records",
        ),
        _check(
            "operation-index-balanced",
            WorkbenchReleaseOfflineCheckPlane.INDEX,
            _operation_index(evaluation)["balanced"],
            _operation_index(evaluation)["operations"],
            "four equal operation partitions",
            "operation index preserves balanced partitions",
        ),
        _check(
            "public-key-index-closed",
            WorkbenchReleaseOfflineCheckPlane.SECURITY,
            _public_key_index(selected_fixture, runtime_projection)["accepted"],
            _public_key_index(selected_fixture, runtime_projection)["forbidden_keys"],
            (),
            "public key index rejects forbidden keys",
        ),
        _check(
            "component-addresses",
            WorkbenchReleaseOfflineCheckPlane.CLOSURE,
            all(
                str(
                    getattr(getattr(source_runtime, attribute, None), "content_address", "")
                ).startswith("sha256:")
                for attribute in (
                    "evaluation",
                    "metrics",
                    "lineage",
                    "reconciliation",
                    "quality",
                    "replay",
                    "view",
                    "queue",
                    "handoff",
                    "integrity",
                    "depth",
                    "controls",
                    "validation",
                    "evidence",
                    "access",
                    "failure_injection",
                    "diagnostics",
                    "artifacts",
                )
            ),
            True,
            True,
            "major runtime planes retain source addresses",
        ),
        _check(
            "release-accepted",
            WorkbenchReleaseOfflineCheckPlane.CLOSURE,
            bool(getattr(source_runtime.release, "accepted", False)),
            getattr(source_runtime.release, "accepted", False),
            True,
            "release plane is accepted",
        ),
        _check(
            "summary-accepted",
            WorkbenchReleaseOfflineCheckPlane.CLOSURE,
            bool(getattr(source_runtime.summary, "accepted", False)),
            getattr(source_runtime.summary, "accepted", False),
            True,
            "summary plane is accepted",
        ),
        _check(
            "compliance-accepted",
            WorkbenchReleaseOfflineCheckPlane.SECURITY,
            bool(getattr(source_runtime.compliance, "accepted", False)),
            getattr(source_runtime.compliance, "accepted", False),
            True,
            "research-use compliance boundary is accepted",
        ),
        _check(
            "runtime-stage-addresses",
            WorkbenchReleaseOfflineCheckPlane.RUNTIME,
            all(
                str(item.get("content_address", "")).startswith("sha256:")
                for item in runtime_projection.get("stages", ())
                if isinstance(item, Mapping)
            ),
            len(runtime_projection.get("stages", ())),
            49,
            "every normalized runtime stage is addressed",
        ),
    )
    accepted = all(item.passed for item in checks)
    state = (
        WorkbenchReleaseOfflineBundleState.READY
        if accepted
        else WorkbenchReleaseOfflineBundleState.BLOCKED
    )
    body = {
        "bundle_id": _safe_component(bundle_id, "bundle_id"),
        "version": WORKBENCH_RELEASE_OFFLINE_BUNDLE_VERSION,
        "boundary": WORKBENCH_RELEASE_OFFLINE_BOUNDARY,
        "fixture_id": selected_fixture.fixture_id,
        "run_id": _safe_component(run_id, "run_id"),
        "state": state,
        "accepted": accepted,
        "artifacts": artifacts,
        "checks": checks,
        "runtime_address": str(runtime_projection["content_address"]),
        "stage_count": len(source_runtime.stages),
        "warning_count": sum(not item.passed for item in checks),
    }
    provisional = WorkbenchReleaseOfflineBundle(
        **body, content_address="workbench-release-offline-bundle:provisional"
    )
    return WorkbenchReleaseOfflineBundle(**body, content_address=_bundle_address(provisional))


def workbench_release_offline_manifest_text(bundle: WorkbenchReleaseOfflineBundle) -> str:
    return canonical_json(bundle.to_dict(include_payloads=False)) + "\n"


def write_workbench_release_offline_bundle(
    bundle: WorkbenchReleaseOfflineBundle, destination: str | Path
) -> Path:
    """Write exact payload bytes and a canonical root manifest."""

    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    for artifact in bundle.artifacts:
        if artifact.payload is None:
            raise ValidationError(f"artifact {artifact.artifact_id} has no payload")
        target = root / Path(*PurePosixPath(artifact.relative_path).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(artifact.payload.encode("utf-8"))
    (root / WORKBENCH_RELEASE_OFFLINE_MANIFEST).write_bytes(
        workbench_release_offline_manifest_text(bundle).encode("utf-8")
    )
    return root


def _verification(
    bundle_id: str,
    checks: tuple[WorkbenchReleaseOfflineCheck, ...] | list[WorkbenchReleaseOfflineCheck],
) -> Any:
    from .workbench_release_frontier_offline_contracts import WorkbenchReleaseOfflineVerification

    materialized = tuple(checks)
    body = {
        "bundle_id": bundle_id,
        "accepted": all(item.passed for item in materialized),
        "checks": materialized,
    }
    return WorkbenchReleaseOfflineVerification(
        **body, content_address=content_hash(body, prefix="workbench-release-offline-verification")
    )


def verify_workbench_release_offline_bundle(destination: str | Path) -> Any:
    """Verify manifest shape, exact bytes, addresses, and public closure."""

    from .workbench_release_frontier_offline_query import load_workbench_release_offline_bundle

    bundle = load_workbench_release_offline_bundle(destination, include_payloads=True)
    checks: list[WorkbenchReleaseOfflineCheck] = []
    checks.append(
        _check(
            "root-address",
            WorkbenchReleaseOfflineCheckPlane.MANIFEST,
            bundle.content_address == _bundle_address(bundle),
            bundle.content_address,
            _bundle_address(bundle),
            "root manifest address reconstructs",
        )
    )
    checks.append(
        _check(
            "root-state",
            WorkbenchReleaseOfflineCheckPlane.CLOSURE,
            bundle.ready,
            bundle.state.value,
            WorkbenchReleaseOfflineBundleState.READY.value,
            "root bundle is ready",
        )
    )
    checks.append(
        _check(
            "artifact-count",
            WorkbenchReleaseOfflineCheckPlane.MANIFEST,
            bundle.artifact_count == WORKBENCH_RELEASE_OFFLINE_ARTIFACT_COUNT,
            bundle.artifact_count,
            WORKBENCH_RELEASE_OFFLINE_ARTIFACT_COUNT,
            "manifest artifact count is closed",
        )
    )
    checks.append(
        _check(
            "artifact-identities",
            WorkbenchReleaseOfflineCheckPlane.CLOSURE,
            len({item.artifact_id for item in bundle.artifacts}) == bundle.artifact_count,
            bundle.artifact_count,
            bundle.artifact_count,
            "artifact identities are unique",
        )
    )
    checks.append(
        _check(
            "artifact-paths",
            WorkbenchReleaseOfflineCheckPlane.CLOSURE,
            len({item.relative_path for item in bundle.artifacts}) == bundle.artifact_count,
            bundle.artifact_count,
            bundle.artifact_count,
            "artifact paths are unique",
        )
    )
    checks.append(
        _check(
            "artifact-bytes",
            WorkbenchReleaseOfflineCheckPlane.ARTIFACT,
            all(
                item.payload is not None
                and len(item.payload.encode("utf-8")) == item.byte_count
                and hash_bytes(
                    item.payload.encode("utf-8"), prefix=WORKBENCH_RELEASE_OFFLINE_ARTIFACT_PREFIX
                )
                == item.content_address
                for item in bundle.artifacts
            ),
            True,
            True,
            "payload byte lengths and addresses reconcile",
        )
    )
    checks.append(
        _check(
            "artifact-files",
            WorkbenchReleaseOfflineCheckPlane.ARTIFACT,
            all(
                (Path(destination) / Path(*PurePosixPath(item.relative_path).parts))
                .read_bytes()
                .decode("utf-8")
                == item.payload
                for item in bundle.artifacts
            ),
            True,
            True,
            "filesystem bytes equal manifest payloads",
        )
    )
    checks.append(
        _check(
            "manifest-boundary",
            WorkbenchReleaseOfflineCheckPlane.PUBLIC_BOUNDARY,
            not _has_forbidden_key(bundle.manifest_dict())
            and not contains_private_key(bundle.manifest_dict()),
            True,
            True,
            "root manifest contains no forbidden keys",
        )
    )
    checks.append(
        _check(
            "runtime-stage-count",
            WorkbenchReleaseOfflineCheckPlane.RUNTIME,
            bundle.stage_count == 49,
            bundle.stage_count,
            49,
            "runtime stage denominator is conserved",
        )
    )
    checks.append(
        _check(
            "warning-count",
            WorkbenchReleaseOfflineCheckPlane.CLOSURE,
            bundle.warning_count == bundle.failed_check_count,
            bundle.warning_count,
            bundle.failed_check_count,
            "warning count equals failed checks",
        )
    )
    return _verification(bundle.bundle_id, checks)


__all__ = [
    "WORKBENCH_RELEASE_OFFLINE_CSV_MEDIA_TYPE",
    "WORKBENCH_RELEASE_OFFLINE_JSON_MEDIA_TYPE",
    "build_workbench_release_offline_bundle",
    "verify_workbench_release_offline_bundle",
    "workbench_release_offline_manifest_text",
    "write_workbench_release_offline_bundle",
]
