"""Materialize and verify the public D14 evidence lifecycle handoff."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from .errors import ValidationError
from .evidence_lifecycle_frontier_artifacts import build_evidence_lifecycle_artifact_inventory
from .evidence_lifecycle_frontier_bundle import EvidenceLifecycleReleaseBundle
from .evidence_lifecycle_frontier_contracts import default_evidence_lifecycle_contracts
from .evidence_lifecycle_frontier_fixture_eval import evaluate_evidence_lifecycle_fixture
from .evidence_lifecycle_frontier_lineage import build_evidence_lifecycle_lineage
from .evidence_lifecycle_frontier_metrics import measure_evidence_lifecycle
from .evidence_lifecycle_frontier_observability import observe_evidence_lifecycle
from .evidence_lifecycle_frontier_policy import default_evidence_lifecycle_policy
from .evidence_lifecycle_frontier_public_data import (
    audit_evidence_lifecycle_data,
    build_evidence_lifecycle_catalog,
    default_evidence_lifecycle_fixture,
)
from .evidence_lifecycle_frontier_quality_gate import evaluate_evidence_lifecycle_quality
from .evidence_lifecycle_frontier_reconciliation import reconcile_evidence_lifecycle
from .evidence_lifecycle_frontier_release import build_evidence_lifecycle_release_manifest
from .evidence_lifecycle_frontier_replay import replay_evidence_lifecycle
from .evidence_lifecycle_frontier_review_queue import build_evidence_lifecycle_review_queue
from .evidence_lifecycle_frontier_runtime import run_evidence_lifecycle_runtime
from .evidence_lifecycle_frontier_scenario_matrix import build_evidence_lifecycle_scenario_matrix
from .evidence_lifecycle_frontier_schema import default_evidence_lifecycle_schema
from .evidence_lifecycle_frontier_views import build_evidence_lifecycle_review_view
from .module_fabric_support import contains_private_key
from .run_workspace import _has_forbidden_key
from .serialization import canonical_json, content_hash, hash_bytes, jsonable, require_non_empty
from .evidence_lifecycle_frontier_offline_contracts import (
    EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_ARTIFACT_COUNT,
    EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_ARTIFACT_PREFIX,
    EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_BOUNDARY,
    EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_MANIFEST,
    EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_VERSION,
    EvidenceLifecycleOfflineArtifact,
    EvidenceLifecycleOfflineArtifactKind,
    EvidenceLifecycleOfflineBundle,
    EvidenceLifecycleOfflineBundleState,
    EvidenceLifecycleOfflineCheck,
    EvidenceLifecycleOfflineCheckPlane,
    EvidenceLifecycleOfflineVerification,
    evidence_lifecycle_offline_check,
)

EVIDENCE_LIFECYCLE_OFFLINE_JSON_MEDIA_TYPE = "application/json"
EVIDENCE_LIFECYCLE_OFFLINE_CSV_MEDIA_TYPE = "text/csv"

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
        "programming_language",
        "produced_by",
        "sample_id",
        "subject_id",
    }
)


def _text(value: Any) -> str:
    return str(value).strip()


def _safe_component(value: str, field: str) -> str:
    normalized = _text(value)
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
    return not path.is_absolute() and bool(path.parts) and all(part not in {"", ".", ".."} for part in path.parts)


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
        raise ValidationError("evidence lifecycle offline bundle crosses the public boundary")
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
    kind: EvidenceLifecycleOfflineArtifactKind,
) -> EvidenceLifecycleOfflineArtifact:
    path = _text(relative_path)
    if not _safe_relative_path(path):
        raise ValidationError(f"unsafe evidence lifecycle bundle path: {relative_path!r}")
    text = _json_text(payload) if media_type == EVIDENCE_LIFECYCLE_OFFLINE_JSON_MEDIA_TYPE else _text(payload).rstrip("\n") + "\n"
    raw = text.encode("utf-8")
    return EvidenceLifecycleOfflineArtifact(
        artifact_id=_safe_component(artifact_id, "artifact_id"),
        relative_path=path,
        media_type=media_type,
        kind=kind,
        byte_count=len(raw),
        line_count=_line_count(text),
        content_address=hash_bytes(raw, prefix=EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_ARTIFACT_PREFIX),
        payload=text,
    )


def _stable_runtime_projection(runtime: Any) -> dict[str, Any]:
    """Remove host timing variance while retaining the ordered runtime trace."""

    value = jsonable(runtime)
    if not isinstance(value, dict):
        raise ValidationError("evidence lifecycle runtime must serialize to an object")
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
    value["content_address"] = content_hash(value, prefix="evidence-lifecycle-runtime-public")
    return value


def _stable_inventory_projection(inventory: Any, stable_runtime_address: str) -> dict[str, Any]:
    value = jsonable(inventory)
    if not isinstance(value, dict):
        raise ValidationError("evidence lifecycle artifact inventory must serialize to an object")
    artifacts = value.get("artifacts", ())
    if isinstance(artifacts, list):
        normalized: list[Any] = []
        for artifact in artifacts:
            if isinstance(artifact, Mapping) and artifact.get("kind") == "runtime":
                item = dict(artifact)
                item["content_address"] = stable_runtime_address
                normalized.append(item)
            else:
                normalized.append(artifact)
        value["artifacts"] = normalized
    value.pop("content_address", None)
    value["content_address"] = content_hash(value)
    return value


def _component_payloads(
    runtime: Any,
    *,
    fixture: Any,
    evaluation: Any,
    metrics: Any,
    policy: Any,
    lineage: Any,
    reconciliation: Any,
    quality: Any,
    release_bundle: EvidenceLifecycleReleaseBundle,
    replay: Any,
    release: Any,
    review: Any,
    queue: Any,
    inventory: Any,
    observability: Any,
) -> tuple[tuple[str, str, EvidenceLifecycleOfflineArtifactKind, Any], ...]:
    stable_runtime = _stable_runtime_projection(runtime)
    stable_inventory = _stable_inventory_projection(inventory, str(stable_runtime["content_address"]))
    return (
        ("fixture", "fixture.json", EvidenceLifecycleOfflineArtifactKind.FIXTURE, fixture),
        ("catalog", "catalog.json", EvidenceLifecycleOfflineArtifactKind.CATALOG, build_evidence_lifecycle_catalog(fixture)),
        ("data-audit", "data-audit.json", EvidenceLifecycleOfflineArtifactKind.DATA_AUDIT, audit_evidence_lifecycle_data(fixture)),
        ("contracts", "contracts.json", EvidenceLifecycleOfflineArtifactKind.CONTRACTS, default_evidence_lifecycle_contracts()),
        ("schema", "schema.json", EvidenceLifecycleOfflineArtifactKind.SCHEMA, default_evidence_lifecycle_schema()),
        ("evaluation", "evaluation.json", EvidenceLifecycleOfflineArtifactKind.EVALUATION, evaluation),
        ("metrics", "metrics.json", EvidenceLifecycleOfflineArtifactKind.METRICS, metrics),
        ("policy", "policy.json", EvidenceLifecycleOfflineArtifactKind.POLICY, policy),
        ("lineage", "lineage.json", EvidenceLifecycleOfflineArtifactKind.LINEAGE, lineage),
        ("reconciliation", "reconciliation.json", EvidenceLifecycleOfflineArtifactKind.RECONCILIATION, reconciliation),
        ("quality", "quality.json", EvidenceLifecycleOfflineArtifactKind.QUALITY, quality),
        ("bundle", "bundle.json.payload", EvidenceLifecycleOfflineArtifactKind.BUNDLE, release_bundle),
        ("replay", "replay.json", EvidenceLifecycleOfflineArtifactKind.REPLAY, replay),
        ("release", "release.json", EvidenceLifecycleOfflineArtifactKind.RELEASE, release),
        ("review", "review.json", EvidenceLifecycleOfflineArtifactKind.REVIEW, review),
        ("review-queue", "review-queue.json", EvidenceLifecycleOfflineArtifactKind.REVIEW_QUEUE, queue),
        ("artifacts", "artifacts.json", EvidenceLifecycleOfflineArtifactKind.ARTIFACTS, stable_inventory),
        ("scenario-matrix", "scenario-matrix.json", EvidenceLifecycleOfflineArtifactKind.SCENARIO_MATRIX, build_evidence_lifecycle_scenario_matrix()),
        ("observability", "observability.json", EvidenceLifecycleOfflineArtifactKind.OBSERVABILITY, observability),
        ("review-csv", "review.csv", EvidenceLifecycleOfflineArtifactKind.REVIEW_CSV, _review_csv(review)),
        ("runtime", "runtime.json", EvidenceLifecycleOfflineArtifactKind.RUNTIME, stable_runtime),
    )


def _review_csv(view: Any) -> str:
    stream = io.StringIO()
    fields = ("record_id", "operation", "role", "state", "accepted", "issue_codes", "source_ids", "release_state")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in view.rows:
        writer.writerow(
            {
                "record_id": row.record_id,
                "operation": row.operation.value,
                "role": row.role.value,
                "state": row.state,
                "accepted": row.accepted,
                "issue_codes": "|".join(row.issue_codes),
                "source_ids": "|".join(row.source_ids),
                "release_state": row.release_state,
            }
        )
    return stream.getvalue()


def _build_artifacts(payloads: tuple[tuple[str, str, EvidenceLifecycleOfflineArtifactKind, Any], ...]) -> tuple[EvidenceLifecycleOfflineArtifact, ...]:
    return tuple(
        _artifact(
            artifact_id,
            path,
            EVIDENCE_LIFECYCLE_OFFLINE_CSV_MEDIA_TYPE if kind is EvidenceLifecycleOfflineArtifactKind.REVIEW_CSV else EVIDENCE_LIFECYCLE_OFFLINE_JSON_MEDIA_TYPE,
            payload,
            kind=kind,
        )
        for artifact_id, path, kind, payload in payloads
    )


def _check(
    check_id: str,
    plane: EvidenceLifecycleOfflineCheckPlane,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> EvidenceLifecycleOfflineCheck:
    return evidence_lifecycle_offline_check(check_id, plane, passed, observed, required, detail)


def _bundle_address(bundle: EvidenceLifecycleOfflineBundle) -> str:
    return content_hash(bundle.manifest_dict(include_payloads=False), prefix="evidence-lifecycle-offline-bundle")


def build_evidence_lifecycle_offline_bundle(
    runtime: Any | None = None,
    *,
    fixture: Any | None = None,
    bundle_id: str = "evidence-lifecycle-public-bundle",
    run_id: str = "evidence-lifecycle-offline-runtime",
) -> EvidenceLifecycleOfflineBundle:
    """Run D14 once and assemble a closed, public, deterministic artifact set."""

    require_non_empty(bundle_id, "bundle_id")
    require_non_empty(run_id, "run_id")
    selected_fixture = fixture or default_evidence_lifecycle_fixture()
    source_runtime = runtime or run_evidence_lifecycle_runtime(selected_fixture, run_id=run_id)
    evaluation = evaluate_evidence_lifecycle_fixture(selected_fixture)
    metrics = measure_evidence_lifecycle(evaluation)
    policy = default_evidence_lifecycle_policy()
    lineage = build_evidence_lifecycle_lineage(selected_fixture, evaluation)
    reconciliation = reconcile_evidence_lifecycle(selected_fixture, evaluation, policy)
    contracts = default_evidence_lifecycle_contracts()
    schema = default_evidence_lifecycle_schema()
    quality = evaluate_evidence_lifecycle_quality(selected_fixture, evaluation, contracts, schema, lineage, reconciliation)
    release_bundle = source_runtime.bundle
    replay = replay_evidence_lifecycle(selected_fixture, replay_id=f"{run_id}:replay")
    release = build_evidence_lifecycle_release_manifest(release_bundle, quality, replay, release_id=f"{bundle_id}:release")
    decisions = release_bundle.policy_decisions
    review = build_evidence_lifecycle_review_view(selected_fixture, evaluation, decisions, release)
    queue = build_evidence_lifecycle_review_queue(selected_fixture, evaluation, decisions, queue_id=f"{bundle_id}:queue")
    inventory = build_evidence_lifecycle_artifact_inventory(selected_fixture, evaluation, metrics, quality, source_runtime, release, release_bundle)
    observability = observe_evidence_lifecycle(source_runtime, evaluation)
    payloads = _component_payloads(
        source_runtime,
        fixture=selected_fixture,
        evaluation=evaluation,
        metrics=metrics,
        policy=policy,
        lineage=lineage,
        reconciliation=reconciliation,
        quality=quality,
        release_bundle=release_bundle,
        replay=replay,
        release=release,
        review=review,
        queue=queue,
        inventory=inventory,
        observability=observability,
    )
    artifacts = _build_artifacts(payloads)
    stable_runtime_address = str(_stable_runtime_projection(source_runtime)["content_address"])
    json_artifacts = tuple(item for item in artifacts if item.media_type == EVIDENCE_LIFECYCLE_OFFLINE_JSON_MEDIA_TYPE)
    checks = (
        _check("artifact-inventory", EvidenceLifecycleOfflineCheckPlane.MANIFEST, len(artifacts) == EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_ARTIFACT_COUNT, len(artifacts), EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_ARTIFACT_COUNT, "the D14 offline artifact inventory is closed"),
        _check("artifact-identities-unique", EvidenceLifecycleOfflineCheckPlane.CLOSURE, len({item.artifact_id for item in artifacts}) == len(artifacts), len({item.artifact_id for item in artifacts}), len(artifacts), "artifact identifiers are unique"),
        _check("artifact-paths-unique", EvidenceLifecycleOfflineCheckPlane.CLOSURE, len({item.relative_path for item in artifacts}) == len(artifacts), len({item.relative_path for item in artifacts}), len(artifacts), "artifact paths are unique"),
        _check("artifact-addresses-present", EvidenceLifecycleOfflineCheckPlane.ARTIFACT, all(item.content_address.startswith(f"{EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_ARTIFACT_PREFIX}:") for item in artifacts), sum(item.content_address.startswith(f"{EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_ARTIFACT_PREFIX}:") for item in artifacts), len(artifacts), "every artifact has an exact-byte address"),
        _check("artifact-payloads-present", EvidenceLifecycleOfflineCheckPlane.ARTIFACT, all(item.payload is not None for item in artifacts), sum(item.payload is not None for item in artifacts), len(artifacts), "every artifact is materializable"),
        _check("public-json-boundary", EvidenceLifecycleOfflineCheckPlane.PUBLIC_BOUNDARY, all(not _has_forbidden_key(json.loads(item.payload or "{}")) and not contains_private_key(json.loads(item.payload or "{}")) for item in json_artifacts), True, True, "JSON artifacts contain no private or attribution keys"),
        _check("fixture-record-denominator", EvidenceLifecycleOfflineCheckPlane.RUNTIME, len(selected_fixture.records) == 16, len(selected_fixture.records), 16, "sixteen lifecycle records are conserved"),
        _check("fixture-source-denominator", EvidenceLifecycleOfflineCheckPlane.RUNTIME, len(selected_fixture.sources) == 5, len(selected_fixture.sources), 5, "five public source receipts are conserved"),
        _check("fixture-positive-denominator", EvidenceLifecycleOfflineCheckPlane.RUNTIME, len(selected_fixture.positive_records) == 4, len(selected_fixture.positive_records), 4, "one positive path exists per operation"),
        _check("fixture-control-denominator", EvidenceLifecycleOfflineCheckPlane.RUNTIME, len(selected_fixture.control_records) == 12, len(selected_fixture.control_records), 12, "three controls exist per operation"),
        _check("operation-denominator", EvidenceLifecycleOfflineCheckPlane.RUNTIME, len(set(item.operation for item in selected_fixture.records)) == 4, len(set(item.operation for item in selected_fixture.records)), 4, "all four lifecycle operations are retained"),
        _check("evaluation-execution-denominator", EvidenceLifecycleOfflineCheckPlane.RUNTIME, len(evaluation.executions) == 16, len(evaluation.executions), 16, "every record has one execution"),
        _check("evaluation-check-denominator", EvidenceLifecycleOfflineCheckPlane.RUNTIME, len(evaluation.checks) == 120, len(evaluation.checks), 120, "all seven per-record and global checks are retained"),
        _check("runtime-stage-denominator", EvidenceLifecycleOfflineCheckPlane.RUNTIME, len(source_runtime.stages) == 10, len(source_runtime.stages), 10, "the ordered D14 runtime has ten stages"),
        _check("runtime-address-present", EvidenceLifecycleOfflineCheckPlane.RUNTIME, bool(stable_runtime_address), stable_runtime_address, "addressed runtime", "the normalized runtime receipt is retained"),
        _check("observability-event-denominator", EvidenceLifecycleOfflineCheckPlane.RUNTIME, len(observability.events) == 26, len(observability.events), 26, "ten runtime and sixteen execution events are retained"),
        _check("runtime-accepted", EvidenceLifecycleOfflineCheckPlane.RUNTIME, source_runtime.accepted, source_runtime.accepted, True, "source D14 runtime is accepted"),
        _check("replay-accepted", EvidenceLifecycleOfflineCheckPlane.REPLAY, replay.accepted, replay.accepted, True, "source evaluation replay is accepted"),
        _check("reconciliation-accepted", EvidenceLifecycleOfflineCheckPlane.CLOSURE, reconciliation.reconciled, reconciliation.reconciled, True, "expected lifecycle states reconcile"),
        _check("quality-accepted", EvidenceLifecycleOfflineCheckPlane.CLOSURE, quality.accepted, quality.accepted, True, "quality gate is accepted"),
        _check("release-accepted", EvidenceLifecycleOfflineCheckPlane.CLOSURE, release.accepted, release.accepted, True, "release remains research scoped and accepted"),
        _check("review-row-denominator", EvidenceLifecycleOfflineCheckPlane.CLOSURE, len(review.rows) == 16, len(review.rows), 16, "review projection has one row per record"),
        _check("queue-row-denominator", EvidenceLifecycleOfflineCheckPlane.CLOSURE, len(queue.items) == 16, len(queue.items), 16, "review queue has one item per record"),
        _check("queue-accepted", EvidenceLifecycleOfflineCheckPlane.CLOSURE, queue.accepted, queue.accepted, True, "review queue invariants pass"),
    )
    accepted = all(item.passed for item in checks)
    state = EvidenceLifecycleOfflineBundleState.READY if accepted else EvidenceLifecycleOfflineBundleState.BLOCKED
    body = {
        "bundle_id": _safe_component(bundle_id, "bundle_id"),
        "version": EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_VERSION,
        "boundary": EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_BOUNDARY,
        "fixture_id": selected_fixture.fixture_id,
        "run_id": _safe_component(run_id, "run_id"),
        "state": state,
        "accepted": accepted,
        "artifacts": artifacts,
        "checks": checks,
        "runtime_address": stable_runtime_address,
        "warning_count": sum(not item.passed for item in checks),
    }
    provisional = EvidenceLifecycleOfflineBundle(**body, content_address="evidence-lifecycle-offline-bundle:provisional")
    return EvidenceLifecycleOfflineBundle(**body, content_address=_bundle_address(provisional))


def evidence_lifecycle_offline_manifest_text(bundle: EvidenceLifecycleOfflineBundle) -> str:
    return canonical_json(bundle.to_dict(include_payloads=False)) + "\n"


def write_evidence_lifecycle_offline_bundle(bundle: EvidenceLifecycleOfflineBundle, destination: str | Path) -> Path:
    """Write exact artifact bytes and the canonical root manifest."""

    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    for artifact in bundle.artifacts:
        if artifact.payload is None:
            raise ValidationError(f"artifact {artifact.artifact_id} has no payload")
        target = root / Path(*PurePosixPath(artifact.relative_path).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(artifact.payload.encode("utf-8"))
    (root / EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_MANIFEST).write_bytes(evidence_lifecycle_offline_manifest_text(bundle).encode("utf-8"))
    return root


def _verification(bundle_id: str, checks: tuple[EvidenceLifecycleOfflineCheck, ...] | list[EvidenceLifecycleOfflineCheck]) -> EvidenceLifecycleOfflineVerification:
    values = tuple(checks)
    body = {"bundle_id": bundle_id, "accepted": all(item.passed for item in values), "checks": values}
    return EvidenceLifecycleOfflineVerification(bundle_id, body["accepted"], values, content_hash(body, prefix="evidence-lifecycle-offline-verification"))


def _check_manifest_address(manifest: Mapping[str, Any]) -> bool:
    expected = manifest.get("content_address")
    body = dict(manifest)
    body.pop("content_address", None)
    return isinstance(expected, str) and expected == content_hash(body, prefix="evidence-lifecycle-offline-bundle")


def _path_for(root: Path, relative_path: str) -> Path:
    if not _safe_relative_path(relative_path):
        raise ValidationError(f"unsafe evidence lifecycle artifact path: {relative_path!r}")
    return root / Path(*PurePosixPath(relative_path).parts)


def verify_evidence_lifecycle_offline_bundle(destination: str | Path) -> EvidenceLifecycleOfflineVerification:
    """Verify a materialized bundle from its manifest and exact artifact bytes."""

    root = Path(destination)
    manifest_path = root / EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_MANIFEST
    if not root.exists() or not root.is_dir():
        return _verification("missing-bundle", [_check("bundle-directory", EvidenceLifecycleOfflineCheckPlane.MANIFEST, False, str(root), "directory", "bundle directory is missing")])
    if not manifest_path.exists() or not manifest_path.is_file() or manifest_path.is_symlink():
        return _verification("missing-manifest", [_check("manifest-present", EvidenceLifecycleOfflineCheckPlane.MANIFEST, False, False, True, "bundle manifest is missing or is not a regular file")])
    try:
        raw_manifest = manifest_path.read_bytes()
        manifest = json.loads(raw_manifest.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _verification("invalid-manifest", [_check("manifest-readable", EvidenceLifecycleOfflineCheckPlane.MANIFEST, False, type(exc).__name__, "canonical UTF-8 JSON", "bundle manifest cannot be decoded")])
    if not isinstance(manifest, Mapping):
        return _verification("invalid-manifest", [_check("manifest-object", EvidenceLifecycleOfflineCheckPlane.MANIFEST, False, type(manifest).__name__, "object", "bundle manifest root must be an object")])
    bundle_id = _text(manifest.get("bundle_id", "unknown-bundle"))
    checks: list[EvidenceLifecycleOfflineCheck] = []
    checks.append(_check("manifest-utf8", EvidenceLifecycleOfflineCheckPlane.MANIFEST, raw_manifest.decode("utf-8") == canonical_json(manifest) + "\n", len(raw_manifest), len((canonical_json(manifest) + "\n").encode("utf-8")), "manifest is canonical UTF-8 JSON"))
    checks.append(_check("manifest-address", EvidenceLifecycleOfflineCheckPlane.MANIFEST, _check_manifest_address(manifest), manifest.get("content_address"), "reconstructed bundle address", "manifest address reconstructs from exact metadata"))
    checks.append(_check("manifest-version", EvidenceLifecycleOfflineCheckPlane.SCHEMA, manifest.get("version") == EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_VERSION, manifest.get("version"), EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_VERSION, "manifest version is closed"))
    checks.append(_check("manifest-boundary", EvidenceLifecycleOfflineCheckPlane.PUBLIC_BOUNDARY, manifest.get("boundary") == EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_BOUNDARY, manifest.get("boundary"), EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_BOUNDARY, "public aggregate boundary is exact"))
    checks.append(_check("manifest-public-keys", EvidenceLifecycleOfflineCheckPlane.PUBLIC_BOUNDARY, not _has_forbidden_key(manifest) and not contains_private_key(manifest), True, True, "manifest has no forbidden or private keys"))
    artifacts_value = manifest.get("artifacts", ())
    manifest_checks = manifest.get("checks", ())
    if not isinstance(artifacts_value, list) or not isinstance(manifest_checks, list):
        checks.append(_check("manifest-collections", EvidenceLifecycleOfflineCheckPlane.MANIFEST, False, {"artifacts": type(artifacts_value).__name__, "checks": type(manifest_checks).__name__}, "arrays", "manifest collections must be arrays"))
        return _verification(bundle_id, checks)
    checks.append(_check("manifest-artifact-count", EvidenceLifecycleOfflineCheckPlane.CLOSURE, manifest.get("artifact_count") == len(artifacts_value), manifest.get("artifact_count"), len(artifacts_value), "artifact count reconciles"))
    passed_count = sum(bool(item.get("passed")) for item in manifest_checks if isinstance(item, Mapping))
    checks.append(_check("manifest-check-counts", EvidenceLifecycleOfflineCheckPlane.CLOSURE, manifest.get("passed_check_count") == passed_count and manifest.get("failed_check_count") == len(manifest_checks) - passed_count, {"passed": manifest.get("passed_check_count"), "failed": manifest.get("failed_check_count")}, {"passed": passed_count, "failed": len(manifest_checks) - passed_count}, "check counts conserve manifest checks"))
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for raw in artifacts_value:
        if not isinstance(raw, Mapping):
            checks.append(_check("artifact-entry-object", EvidenceLifecycleOfflineCheckPlane.ARTIFACT, False, type(raw).__name__, "object", "artifact entries are objects"))
            continue
        artifact_id = _text(raw.get("artifact_id"))
        relative_path = _text(raw.get("relative_path"))
        seen_ids.add(artifact_id)
        seen_paths.add(relative_path)
        checks.append(_check(f"artifact:{artifact_id}:path", EvidenceLifecycleOfflineCheckPlane.ARTIFACT, _safe_relative_path(relative_path), relative_path, "safe relative path", "artifact path is portable"))
        try:
            target = _path_for(root, relative_path)
            raw_bytes = target.read_bytes()
            expected_address = str(raw.get("content_address", ""))
            expected_bytes = int(raw.get("byte_count", -1))
            expected_lines = int(raw.get("line_count", -1))
            checks.append(_check(f"artifact:{artifact_id}:bytes", EvidenceLifecycleOfflineCheckPlane.ARTIFACT, hash_bytes(raw_bytes, prefix=EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_ARTIFACT_PREFIX) == expected_address and len(raw_bytes) == expected_bytes, {"bytes": len(raw_bytes), "address": hash_bytes(raw_bytes, prefix=EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_ARTIFACT_PREFIX)}, {"bytes": expected_bytes, "address": expected_address}, "artifact bytes and address match manifest"))
            checks.append(_check(f"artifact:{artifact_id}:lines", EvidenceLifecycleOfflineCheckPlane.ARTIFACT, raw_bytes.decode("utf-8").count("\n") == expected_lines, raw_bytes.decode("utf-8").count("\n"), expected_lines, "artifact line count matches manifest"))
            if str(raw.get("media_type")) == EVIDENCE_LIFECYCLE_OFFLINE_JSON_MEDIA_TYPE:
                parsed = json.loads(raw_bytes.decode("utf-8"))
                checks.append(_check(f"artifact:{artifact_id}:public", EvidenceLifecycleOfflineCheckPlane.PUBLIC_BOUNDARY, not _has_forbidden_key(parsed) and not contains_private_key(parsed), True, True, "JSON artifact remains public"))
        except (OSError, UnicodeDecodeError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            checks.append(_check(f"artifact:{artifact_id}:readable", EvidenceLifecycleOfflineCheckPlane.ARTIFACT, False, type(exc).__name__, "UTF-8 regular file", "artifact cannot be read or decoded"))
    checks.append(_check("artifact-identities", EvidenceLifecycleOfflineCheckPlane.CLOSURE, len(seen_ids) == len(artifacts_value), len(seen_ids), len(artifacts_value), "artifact identifiers are unique"))
    checks.append(_check("artifact-paths", EvidenceLifecycleOfflineCheckPlane.CLOSURE, len(seen_paths) == len(artifacts_value), len(seen_paths), len(artifacts_value), "artifact paths are unique"))
    checks.append(_check("manifest-accepted", EvidenceLifecycleOfflineCheckPlane.CLOSURE, bool(manifest.get("accepted")) and manifest.get("state") == EvidenceLifecycleOfflineBundleState.READY.value, {"accepted": manifest.get("accepted"), "state": manifest.get("state")}, {"accepted": True, "state": EvidenceLifecycleOfflineBundleState.READY.value}, "manifest release state is ready"))
    return _verification(bundle_id, checks)


__all__ = [
    "EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_ARTIFACT_COUNT",
    "EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_BOUNDARY",
    "EVIDENCE_LIFECYCLE_OFFLINE_CSV_MEDIA_TYPE",
    "EVIDENCE_LIFECYCLE_OFFLINE_JSON_MEDIA_TYPE",
    "EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_VERSION",
    "build_evidence_lifecycle_offline_bundle",
    "evidence_lifecycle_offline_manifest_text",
    "verify_evidence_lifecycle_offline_bundle",
    "write_evidence_lifecycle_offline_bundle",
]
