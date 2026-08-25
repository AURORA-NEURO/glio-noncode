"""Materialize and verify the public D13 validation-design handoff."""

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
from .validation_design_frontier_bundle_contracts import (
    VALIDATION_DESIGN_BUNDLE_ARTIFACT_PREFIX,
    VALIDATION_DESIGN_BUNDLE_MANIFEST,
    VALIDATION_DESIGN_BUNDLE_VERSION,
    ValidationDesignBundle,
    ValidationDesignBundleArtifact,
    ValidationDesignBundleArtifactKind,
    ValidationDesignBundleCheck,
    ValidationDesignBundleCheckPlane,
    ValidationDesignBundleState,
    ValidationDesignBundleVerification,
    validation_design_bundle_check,
)
from .validation_design_frontier_data_dictionary import build_validation_design_data_dictionary
from .validation_design_frontier_exports import export_validation_design_review_csv
from .validation_design_frontier_public_data import default_validation_design_frontier_fixture
from .validation_design_frontier_runtime import run_validation_design_runtime

VALIDATION_DESIGN_BUNDLE_JSON_MEDIA_TYPE = "application/json"
VALIDATION_DESIGN_BUNDLE_CSV_MEDIA_TYPE = "text/csv"
VALIDATION_DESIGN_BUNDLE_ARTIFACT_COUNT = 27
VALIDATION_DESIGN_BUNDLE_BOUNDARY = "public_aggregate_validation_design_planning_offline_handoff"

_FORBIDDEN_BUNDLE_KEYS = frozenset(
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
        "programming_language",
        "produced_by",
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
            if str(key).casefold() not in _FORBIDDEN_BUNDLE_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_public_projection(item) for item in value]
    return value


def _public_value(value: Any) -> Any:
    projected = _public_projection(value)
    if _has_forbidden_key(projected) or contains_private_key(projected):
        raise ValidationError("validation-design bundle crosses the public boundary")
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
    kind: ValidationDesignBundleArtifactKind,
) -> ValidationDesignBundleArtifact:
    path = _text(relative_path)
    if not _safe_relative_path(path):
        raise ValidationError(f"unsafe validation-design bundle path: {relative_path!r}")
    text = _json_text(payload) if media_type == VALIDATION_DESIGN_BUNDLE_JSON_MEDIA_TYPE else _text(payload).rstrip("\n") + "\n"
    raw = text.encode("utf-8")
    return ValidationDesignBundleArtifact(
        artifact_id=_safe_component(artifact_id, "artifact_id"),
        relative_path=path,
        media_type=media_type,
        kind=kind,
        byte_count=len(raw),
        line_count=_line_count(text),
        content_address=hash_bytes(raw, prefix=VALIDATION_DESIGN_BUNDLE_ARTIFACT_PREFIX),
        payload=text,
    )


def _check(
    check_id: str,
    plane: ValidationDesignBundleCheckPlane,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ValidationDesignBundleCheck:
    return validation_design_bundle_check(check_id, plane, passed, observed, required, detail)


def _stable_runtime_projection(runtime: Any) -> dict[str, Any]:
    """Normalize host-timing fields before publishing runtime bytes."""

    value = jsonable(runtime)
    if not isinstance(value, dict):
        raise ValidationError("validation-design runtime must serialize to an object")
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
    value["content_address"] = content_hash(value, prefix="validation-design-runtime-public")
    return value


def _artifact_payloads(runtime: Any) -> tuple[tuple[str, str, ValidationDesignBundleArtifactKind, Any], ...]:
    planes = runtime.planes
    dictionary = build_validation_design_data_dictionary(
        fixture=runtime.fixture,
        evaluation=runtime.evaluation,
        schema=runtime.schema,
    )
    return (
        ("fixture", "fixture.json", ValidationDesignBundleArtifactKind.FIXTURE, runtime.fixture),
        ("audit", "audit.json", ValidationDesignBundleArtifactKind.AUDIT, runtime.audit),
        ("adapters", "adapters.json", ValidationDesignBundleArtifactKind.ADAPTERS, runtime.adapters),
        ("schema", "schema.json", ValidationDesignBundleArtifactKind.SCHEMA, runtime.schema),
        ("evaluation", "evaluation.json", ValidationDesignBundleArtifactKind.EVALUATION, runtime.evaluation),
        ("metrics", "metrics.json", ValidationDesignBundleArtifactKind.METRICS, runtime.metrics),
        ("policy", "policy.json", ValidationDesignBundleArtifactKind.POLICY, runtime.policy),
        ("lineage", "lineage.json", ValidationDesignBundleArtifactKind.LINEAGE, runtime.lineage),
        ("reconciliation", "reconciliation.json", ValidationDesignBundleArtifactKind.RECONCILIATION, runtime.reconciliation),
        ("quality", "quality.json", ValidationDesignBundleArtifactKind.QUALITY, runtime.quality),
        ("replay", "replay.json", ValidationDesignBundleArtifactKind.REPLAY, runtime.replay),
        ("review", "review.json", ValidationDesignBundleArtifactKind.REVIEW, runtime.view),
        ("handoff", "handoff.json", ValidationDesignBundleArtifactKind.HANDOFF, runtime.handoff),
        ("integrity", "integrity.json", ValidationDesignBundleArtifactKind.INTEGRITY, runtime.integrity),
        ("depth", "depth.json", ValidationDesignBundleArtifactKind.DEPTH, runtime.depth),
        ("validation", "validation.json", ValidationDesignBundleArtifactKind.VALIDATION, runtime.validation),
        ("evidence", "evidence.json", ValidationDesignBundleArtifactKind.EVIDENCE, runtime.evidence),
        ("access", "access.json", ValidationDesignBundleArtifactKind.ACCESS, runtime.access),
        ("failure-injection", "failure-injection.json", ValidationDesignBundleArtifactKind.FAILURE_INJECTION, runtime.failure_injection),
        ("diagnostics", "diagnostics.json", ValidationDesignBundleArtifactKind.DIAGNOSTICS, runtime.diagnostics),
        ("release", "release.json", ValidationDesignBundleArtifactKind.RELEASE, planes["release"]),
        ("summary", "summary.json", ValidationDesignBundleArtifactKind.SUMMARY, planes["summary"]),
        ("data-dictionary", "data-dictionary.json", ValidationDesignBundleArtifactKind.DATA_DICTIONARY, dictionary),
        ("observability", "observability.json", ValidationDesignBundleArtifactKind.OBSERVABILITY, planes["observability"]),
        ("report", "report.json", ValidationDesignBundleArtifactKind.REPORT, planes["report"]),
        ("review-csv", "review.csv", ValidationDesignBundleArtifactKind.REVIEW_CSV, export_validation_design_review_csv(runtime.evaluation)),
        ("runtime", "runtime.json", ValidationDesignBundleArtifactKind.RUNTIME, _stable_runtime_projection(runtime)),
    )


def _build_artifacts(runtime: Any) -> tuple[ValidationDesignBundleArtifact, ...]:
    return tuple(
        _artifact(artifact_id, path, VALIDATION_DESIGN_BUNDLE_CSV_MEDIA_TYPE if kind is ValidationDesignBundleArtifactKind.REVIEW_CSV else VALIDATION_DESIGN_BUNDLE_JSON_MEDIA_TYPE, payload, kind=kind)
        for artifact_id, path, kind, payload in _artifact_payloads(runtime)
    )


def _bundle_address(bundle: ValidationDesignBundle) -> str:
    return content_hash(bundle.manifest_dict(include_payloads=False), prefix="validation-design-bundle")


def build_validation_design_offline_bundle(
    runtime: Any | None = None,
    *,
    fixture: Any | None = None,
    bundle_id: str = "validation-design-public-bundle",
    run_id: str = "validation-design-bundle-runtime",
) -> ValidationDesignBundle:
    """Run the D13 runtime and assemble its closed public artifact set."""

    require_non_empty(bundle_id, "bundle_id")
    if runtime is None:
        runtime = run_validation_design_runtime(
            fixture or default_validation_design_frontier_fixture(),
            run_id=run_id,
        )
    artifacts = _build_artifacts(runtime)
    stable_runtime_address = str(_stable_runtime_projection(runtime)["content_address"])
    checks = (
        _check("artifact-inventory", ValidationDesignBundleCheckPlane.MANIFEST, len(artifacts) == VALIDATION_DESIGN_BUNDLE_ARTIFACT_COUNT, len(artifacts), VALIDATION_DESIGN_BUNDLE_ARTIFACT_COUNT, "the D13 artifact inventory is closed"),
        _check("artifact-identities-unique", ValidationDesignBundleCheckPlane.CLOSURE, len({item.artifact_id for item in artifacts}) == len(artifacts), len({item.artifact_id for item in artifacts}), len(artifacts), "artifact identifiers are unique"),
        _check("artifact-paths-unique", ValidationDesignBundleCheckPlane.CLOSURE, len({item.relative_path for item in artifacts}) == len(artifacts), len({item.relative_path for item in artifacts}), len(artifacts), "artifact paths are unique"),
        _check("artifact-addresses-present", ValidationDesignBundleCheckPlane.ARTIFACT, all(item.content_address.startswith(f"{VALIDATION_DESIGN_BUNDLE_ARTIFACT_PREFIX}:") for item in artifacts), sum(item.content_address.startswith(f"{VALIDATION_DESIGN_BUNDLE_ARTIFACT_PREFIX}:") for item in artifacts), len(artifacts), "every artifact has an exact-byte address"),
        _check("artifact-payloads-present", ValidationDesignBundleCheckPlane.ARTIFACT, all(item.payload is not None for item in artifacts), sum(item.payload is not None for item in artifacts), len(artifacts), "every artifact is materializable"),
        _check("public-json-boundary", ValidationDesignBundleCheckPlane.PUBLIC_BOUNDARY, all(item.media_type != VALIDATION_DESIGN_BUNDLE_JSON_MEDIA_TYPE or (item.payload is not None and not _has_forbidden_key(json.loads(item.payload)) and not contains_private_key(json.loads(item.payload))) for item in artifacts), True, True, "JSON artifacts contain no private or attribution keys"),
        _check("fixture-record-denominator", ValidationDesignBundleCheckPlane.RUNTIME, len(runtime.fixture.records) == 16, len(runtime.fixture.records), 16, "all four planning operations retain four scenario rows"),
        _check("fixture-source-denominator", ValidationDesignBundleCheckPlane.RUNTIME, len(runtime.fixture.sources) == 5, len(runtime.fixture.sources), 5, "public source receipt count is conserved"),
        _check("evaluation-check-denominator", ValidationDesignBundleCheckPlane.RUNTIME, len(runtime.evaluation.checks) == 80, len(runtime.evaluation.checks), 80, "five evaluation checks remain present per record"),
        _check("runtime-stage-denominator", ValidationDesignBundleCheckPlane.RUNTIME, len(runtime.stages) == 79, len(runtime.stages), 79, "the complete D13 runtime stage sequence is retained"),
        _check("runtime-accepted", ValidationDesignBundleCheckPlane.RUNTIME, runtime.accepted, runtime.accepted, True, "the source validation-design runtime passed"),
        _check("runtime-address-present", ValidationDesignBundleCheckPlane.RUNTIME, bool(stable_runtime_address), stable_runtime_address, "addressed runtime", "the normalized runtime receipt is retained"),
        _check("replay-deterministic", ValidationDesignBundleCheckPlane.REPLAY, runtime.replay.deterministic, runtime.replay.deterministic, True, "the source evaluation replay is deterministic"),
        _check("bundle-plane-accepted", ValidationDesignBundleCheckPlane.CLOSURE, bool(runtime.planes["bundle"].accepted), runtime.planes["bundle"].accepted, True, "the D13 in-memory bundle plane passed"),
    )
    accepted = all(item.passed for item in checks)
    state = ValidationDesignBundleState.READY if accepted else ValidationDesignBundleState.BLOCKED
    body = {
        "bundle_id": bundle_id,
        "version": VALIDATION_DESIGN_BUNDLE_VERSION,
        "boundary": VALIDATION_DESIGN_BUNDLE_BOUNDARY,
        "fixture_id": runtime.fixture.fixture_id,
        "run_id": run_id,
        "state": state,
        "accepted": accepted,
        "artifacts": artifacts,
        "checks": checks,
        "runtime_address": stable_runtime_address,
        "warning_count": sum(not item.passed for item in checks),
    }
    provisional = ValidationDesignBundle(**body, content_address="validation-design-bundle:provisional")
    return ValidationDesignBundle(**body, content_address=_bundle_address(provisional))


def validation_design_bundle_manifest_text(bundle: ValidationDesignBundle) -> str:
    return canonical_json(bundle.to_dict(include_payloads=False)) + "\n"


def write_validation_design_offline_bundle(bundle: ValidationDesignBundle, destination: str | Path) -> Path:
    """Write exact artifact bytes and the root manifest without hidden files."""

    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    for artifact in bundle.artifacts:
        if artifact.payload is None:
            raise ValidationError(f"artifact {artifact.artifact_id} has no payload")
        target = root / Path(*PurePosixPath(artifact.relative_path).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(artifact.payload.encode("utf-8"))
    (root / VALIDATION_DESIGN_BUNDLE_MANIFEST).write_bytes(validation_design_bundle_manifest_text(bundle).encode("utf-8"))
    return root


def _verification(bundle_id: str, checks: tuple[ValidationDesignBundleCheck, ...] | list[ValidationDesignBundleCheck]) -> ValidationDesignBundleVerification:
    values = tuple(checks)
    body = {"bundle_id": bundle_id, "accepted": all(item.passed for item in values), "checks": values}
    return ValidationDesignBundleVerification(bundle_id, body["accepted"], values, content_hash(body, prefix="validation-design-bundle-verification"))


def _check_manifest_address(manifest: Mapping[str, Any]) -> bool:
    expected = manifest.get("content_address")
    body = dict(manifest)
    body.pop("content_address", None)
    return isinstance(expected, str) and expected == content_hash(body, prefix="validation-design-bundle")


def verify_validation_design_offline_bundle(destination: str | Path) -> ValidationDesignBundleVerification:
    """Verify a materialized D13 bundle from its files and manifest alone."""

    root = Path(destination)
    manifest_path = root / VALIDATION_DESIGN_BUNDLE_MANIFEST
    if not root.exists() or not root.is_dir():
        return _verification("missing-bundle", [_check("bundle-directory", ValidationDesignBundleCheckPlane.MANIFEST, False, str(root), "directory", "bundle directory is missing")])
    if not manifest_path.exists() or not manifest_path.is_file() or manifest_path.is_symlink():
        return _verification("missing-manifest", [_check("manifest-present", ValidationDesignBundleCheckPlane.MANIFEST, False, False, True, "bundle manifest is missing or is not a regular file")])
    checks: list[ValidationDesignBundleCheck] = []
    try:
        raw_manifest = manifest_path.read_bytes()
        manifest = json.loads(raw_manifest.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _verification("invalid-manifest", [_check("manifest-readable", ValidationDesignBundleCheckPlane.MANIFEST, False, type(exc).__name__, "valid UTF-8 JSON", "bundle manifest cannot be decoded")])
    if not isinstance(manifest, Mapping):
        return _verification("invalid-manifest", [_check("manifest-object", ValidationDesignBundleCheckPlane.MANIFEST, False, type(manifest).__name__, "object", "bundle manifest root must be an object")])
    bundle_id = _text(manifest.get("bundle_id", "unknown-bundle"))
    from .validation_design_frontier_bundle_schema import validate_validation_design_bundle_manifest

    schema = validate_validation_design_bundle_manifest(dict(manifest))
    checks.append(_check("manifest-schema", ValidationDesignBundleCheckPlane.SCHEMA, schema.accepted, schema.failed_check_ids, (), "manifest satisfies the closed D13 bundle schema"))
    checks.append(_check("manifest-utf8", ValidationDesignBundleCheckPlane.MANIFEST, raw_manifest.decode("utf-8") == canonical_json(manifest) + "\n", len(raw_manifest), len(canonical_json(manifest).encode("utf-8")) + 1, "manifest is canonical UTF-8 JSON"))
    checks.append(_check("manifest-address", ValidationDesignBundleCheckPlane.MANIFEST, _check_manifest_address(manifest), manifest.get("content_address"), "reconstructed validation-design-bundle address", "manifest address reconstructs from exact metadata"))
    artifacts = manifest.get("artifacts", ())
    manifest_checks = manifest.get("checks", ())
    if not isinstance(artifacts, list) or not isinstance(manifest_checks, list):
        checks.append(_check("manifest-collections", ValidationDesignBundleCheckPlane.MANIFEST, False, {"artifacts": type(artifacts).__name__, "checks": type(manifest_checks).__name__}, "arrays", "manifest collections must be arrays"))
        return _verification(bundle_id, checks)
    passed_count = sum(bool(item.get("passed")) for item in manifest_checks if isinstance(item, Mapping))
    checks.append(_check("manifest-counts", ValidationDesignBundleCheckPlane.CLOSURE, manifest.get("artifact_count") == len(artifacts) and manifest.get("passed_check_count") == passed_count and manifest.get("failed_check_count") == len(manifest_checks) - passed_count, {"artifact_count": manifest.get("artifact_count"), "passed_check_count": manifest.get("passed_check_count"), "failed_check_count": manifest.get("failed_check_count")}, {"artifact_count": len(artifacts), "check_count": len(manifest_checks)}, "manifest counts conserve artifacts and checks"))
    checks.append(_check("manifest-release-accepted", ValidationDesignBundleCheckPlane.CLOSURE, bool(manifest.get("accepted")) and manifest.get("state") == ValidationDesignBundleState.READY.value and all(isinstance(item, Mapping) and bool(item.get("passed")) for item in manifest_checks), {"accepted": manifest.get("accepted"), "state": manifest.get("state")}, {"accepted": True, "state": ValidationDesignBundleState.READY.value}, "a release-ready bundle has no failed manifest checks"))
    artifact_ids = [item.get("artifact_id") for item in artifacts if isinstance(item, Mapping)]
    artifact_paths = [item.get("relative_path") for item in artifacts if isinstance(item, Mapping)]
    checks.append(_check("artifact-identities-unique", ValidationDesignBundleCheckPlane.CLOSURE, len(artifact_ids) == len(set(artifact_ids)) and len(artifact_paths) == len(set(artifact_paths)), {"ids": len(set(artifact_ids)), "paths": len(set(artifact_paths))}, {"ids": len(artifact_ids), "paths": len(artifact_paths)}, "artifact identifiers and paths are unique"))
    expected_paths = {VALIDATION_DESIGN_BUNDLE_MANIFEST}
    for item in artifacts:
        if not isinstance(item, Mapping):
            continue
        artifact_id = _text(item.get("artifact_id", "unknown"))
        relative_path = _text(item.get("relative_path", ""))
        safe = _safe_relative_path(relative_path)
        checks.append(_check(f"path-safe:{artifact_id}", ValidationDesignBundleCheckPlane.ARTIFACT, safe, relative_path, "safe relative POSIX path", "artifact path cannot escape the bundle root"))
        if not safe:
            continue
        expected_paths.add(relative_path)
        target = root / Path(*PurePosixPath(relative_path).parts)
        regular = target.exists() and target.is_file() and not target.is_symlink()
        checks.append(_check(f"present:{artifact_id}", ValidationDesignBundleCheckPlane.ARTIFACT, regular, str(target) if target.exists() else "missing", "regular file", "every manifest artifact is materialized"))
        if not regular:
            continue
        try:
            raw = target.read_bytes()
            text = raw.decode("utf-8")
            address = hash_bytes(raw, prefix=VALIDATION_DESIGN_BUNDLE_ARTIFACT_PREFIX)
            exact = len(raw) == item.get("byte_count") and _line_count(text) == item.get("line_count") and address == item.get("content_address")
            checks.append(_check(f"bytes:{artifact_id}", ValidationDesignBundleCheckPlane.ARTIFACT, exact, {"bytes": len(raw), "lines": _line_count(text), "address": address}, {"bytes": item.get("byte_count"), "lines": item.get("line_count"), "address": item.get("content_address")}, "artifact bytes and address match the manifest"))
            if item.get("media_type") == VALIDATION_DESIGN_BUNDLE_JSON_MEDIA_TYPE:
                try:
                    parsed = json.loads(text)
                    public = not _has_forbidden_key(parsed) and not contains_private_key(parsed)
                except json.JSONDecodeError:
                    public = False
                checks.append(_check(f"json-public:{artifact_id}", ValidationDesignBundleCheckPlane.PUBLIC_BOUNDARY, public, public, True, "JSON artifact is valid and public-boundary safe"))
        except (OSError, UnicodeDecodeError) as exc:
            checks.append(_check(f"readable:{artifact_id}", ValidationDesignBundleCheckPlane.ARTIFACT, False, type(exc).__name__, "readable UTF-8 file", "artifact cannot be decoded"))
    actual_paths: set[str] = set()
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink() or not path.is_file():
            checks.append(_check(f"regular:{relative}", ValidationDesignBundleCheckPlane.CLOSURE, False, "symlink or directory", "regular file", "bundle trees cannot contain symlinks or unlisted directories as artifacts"))
            continue
        actual_paths.add(relative)
    checks.append(_check("unexpected-files", ValidationDesignBundleCheckPlane.CLOSURE, actual_paths == expected_paths, tuple(sorted(actual_paths - expected_paths)), tuple(sorted(expected_paths - actual_paths)), "materialized tree has no unexpected or missing files"))
    if actual_paths == expected_paths and all(item.passed for item in checks):
        try:
            from .validation_design_frontier_bundle_audit import (
                audit_validation_design_offline_bundle,
            )
            from .validation_design_frontier_bundle_query import (
                load_validation_design_offline_bundle,
            )

            loaded = load_validation_design_offline_bundle(root, include_payloads=True)
            audit = audit_validation_design_offline_bundle(loaded)
            checks.append(_check("cross-artifact-audit", ValidationDesignBundleCheckPlane.CLOSURE, audit.accepted, audit.failed_check_ids, (), "fixture, evaluation, runtime, release, replay, and projection artifacts reconcile"))
        except (OSError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            checks.append(_check("cross-artifact-audit", ValidationDesignBundleCheckPlane.CLOSURE, False, type(exc).__name__, "accepted audit", "cross-artifact reconciliation could not be completed"))
    return _verification(bundle_id, checks)


def validation_design_bundle_artifact_bytes(bundle: ValidationDesignBundle, artifact_id: str) -> bytes:
    for artifact in bundle.artifacts:
        if artifact.artifact_id == artifact_id:
            if artifact.payload is None:
                raise ValidationError(f"artifact {artifact_id} has no payload")
            return artifact.payload.encode("utf-8")
    raise ValidationError(f"unknown validation-design bundle artifact: {artifact_id}")


def validation_design_bundle_artifact_csv(bundle: ValidationDesignBundle) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("artifact_id", "kind", "relative_path", "media_type", "byte_count", "line_count", "content_address"))
    for item in bundle.artifacts:
        writer.writerow((item.artifact_id, item.kind.value, item.relative_path, item.media_type, item.byte_count, item.line_count, item.content_address))
    return output.getvalue()


__all__ = [
    "VALIDATION_DESIGN_BUNDLE_ARTIFACT_COUNT",
    "VALIDATION_DESIGN_BUNDLE_BOUNDARY",
    "VALIDATION_DESIGN_BUNDLE_CSV_MEDIA_TYPE",
    "VALIDATION_DESIGN_BUNDLE_JSON_MEDIA_TYPE",
    "build_validation_design_offline_bundle",
    "validation_design_bundle_artifact_bytes",
    "validation_design_bundle_artifact_csv",
    "validation_design_bundle_manifest_text",
    "verify_validation_design_offline_bundle",
    "write_validation_design_offline_bundle",
]
