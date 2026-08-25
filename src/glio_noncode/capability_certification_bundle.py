"""Materialize and verify the live 256-capability certification handoff."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable, Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from .capability_certification_bundle_contracts import (
    CAPABILITY_CERTIFICATION_BUNDLE_ARTIFACT_PREFIX,
    CAPABILITY_CERTIFICATION_BUNDLE_BOUNDARY,
    CAPABILITY_CERTIFICATION_BUNDLE_MANIFEST,
    CAPABILITY_CERTIFICATION_BUNDLE_VERSION,
    CapabilityCertificationBundle,
    CertificationBundleArtifact,
    CertificationBundleArtifactKind,
    CertificationBundleCheck,
    CertificationBundleCheckPlane,
    CertificationBundleState,
    CertificationBundleVerification,
    certification_bundle_check,
)
from .capability_certification_bundle_observability import (
    build_capability_certification_bundle_observability,
)
from .capability_certification_bundle_schema import (
    validate_capability_certification_bundle_manifest,
)
from .capability_certification_exports import (
    export_capability_certification_checks_csv,
    export_capability_certification_csv,
    export_capability_certification_domains_csv,
    export_capability_certification_summary_json,
    render_capability_certification_markdown,
)
from .capability_certification_replay import (
    replay_capability_certification,
    run_capability_certification_failure_injections,
)
from .capability_certification_runtime import run_capability_certification
from .capability_registry import CapabilityRegistry, default_capability_registry
from .errors import ValidationError
from .module_fabric_support import contains_private_key
from .run_workspace import _has_forbidden_key
from .serialization import canonical_json, content_hash, hash_bytes, jsonable, require_non_empty

CERTIFICATION_BUNDLE_JSON = "application/json"
CERTIFICATION_BUNDLE_CSV = "text/csv"
CERTIFICATION_BUNDLE_MARKDOWN = "text/markdown"
CERTIFICATION_BUNDLE_ARTIFACT_COUNT = 12

_FORBIDDEN_CERTIFICATION_KEYS = frozenset(
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
    return not path.is_absolute() and bool(path.parts) and all(
        part not in {"", ".", ".."} for part in path.parts
    )


def _public_projection(value: Any) -> Any:
    """Project nested values while removing direct attribution metadata."""

    value = jsonable(value)
    if isinstance(value, Mapping):
        return {
            str(key): _public_projection(item)
            for key, item in value.items()
            if str(key).casefold() not in _FORBIDDEN_CERTIFICATION_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_public_projection(item) for item in value]
    return value


def _public_value(value: Any) -> Any:
    projected = _public_projection(value)
    if _has_forbidden_key(projected) or contains_private_key(projected):
        raise ValidationError("capability certification bundle crosses the public boundary")
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
    kind: CertificationBundleArtifactKind,
) -> CertificationBundleArtifact:
    path = _text(relative_path)
    if not _safe_relative_path(path):
        raise ValidationError(f"unsafe certification bundle path: {relative_path!r}")
    if media_type == CERTIFICATION_BUNDLE_JSON:
        text = _json_text(payload)
    else:
        text = _text(payload).rstrip("\n") + "\n"
    raw = text.encode("utf-8")
    return CertificationBundleArtifact(
        artifact_id=_safe_component(artifact_id, "artifact_id"),
        relative_path=path,
        media_type=media_type,
        kind=kind,
        byte_count=len(raw),
        line_count=_line_count(text),
        content_address=hash_bytes(raw, prefix=CAPABILITY_CERTIFICATION_BUNDLE_ARTIFACT_PREFIX),
        payload=text,
    )


def _check(
    check_id: str,
    plane: CertificationBundleCheckPlane,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> CertificationBundleCheck:
    return certification_bundle_check(check_id, plane, passed, observed, required, detail)


def _base_artifacts(
    runtime: Any,
    replay: Any,
    failures: Any,
    catalog: CapabilityRegistry,
) -> tuple[CertificationBundleArtifact, ...]:
    report = runtime.report
    return (
        _artifact("report", "report.json", CERTIFICATION_BUNDLE_JSON, report, kind=CertificationBundleArtifactKind.REPORT),
        _artifact("summary", "summary.json", CERTIFICATION_BUNDLE_JSON, json.loads(export_capability_certification_summary_json(report)), kind=CertificationBundleArtifactKind.SUMMARY),
        _artifact("certificates", "certificates.csv", CERTIFICATION_BUNDLE_CSV, export_capability_certification_csv(report), kind=CertificationBundleArtifactKind.CERTIFICATES),
        _artifact("checks", "checks.csv", CERTIFICATION_BUNDLE_CSV, export_capability_certification_checks_csv(report), kind=CertificationBundleArtifactKind.CHECKS),
        _artifact("domains", "domains.csv", CERTIFICATION_BUNDLE_CSV, export_capability_certification_domains_csv(report), kind=CertificationBundleArtifactKind.DOMAINS),
        _artifact("runtime", "runtime.json", CERTIFICATION_BUNDLE_JSON, runtime, kind=CertificationBundleArtifactKind.RUNTIME),
        _artifact("quality", "quality.json", CERTIFICATION_BUNDLE_JSON, runtime.quality, kind=CertificationBundleArtifactKind.QUALITY),
        _artifact("replay", "replay.json", CERTIFICATION_BUNDLE_JSON, replay, kind=CertificationBundleArtifactKind.REPLAY),
        _artifact("failures", "failures.json", CERTIFICATION_BUNDLE_JSON, failures, kind=CertificationBundleArtifactKind.FAILURES),
        _artifact("catalog", "catalog.json", CERTIFICATION_BUNDLE_JSON, catalog.manifest(), kind=CertificationBundleArtifactKind.CATALOG),
        _artifact("report-markdown", "report.md", CERTIFICATION_BUNDLE_MARKDOWN, render_capability_certification_markdown(report), kind=CertificationBundleArtifactKind.MARKDOWN),
    )


def _build_observability_artifact(
    bundle_id: str,
    runtime: Any,
    base: tuple[CertificationBundleArtifact, ...],
) -> CertificationBundleArtifact:
    total_bytes = sum(item.byte_count for item in base)
    observation = None
    for _ in range(4):
        observation = build_capability_certification_bundle_observability(
            bundle_id,
            runtime,
            artifact_count=CERTIFICATION_BUNDLE_ARTIFACT_COUNT,
            artifact_bytes=total_bytes,
        )
        artifact = _artifact(
            "observability",
            "observability.json",
            CERTIFICATION_BUNDLE_JSON,
            observation,
            kind=CertificationBundleArtifactKind.OBSERVABILITY,
        )
        updated = sum(item.byte_count for item in base) + artifact.byte_count
        if updated == total_bytes:
            return artifact
        total_bytes = updated
    if observation is None:
        raise ValidationError("unable to construct certification observability")
    return _artifact(
        "observability",
        "observability.json",
        CERTIFICATION_BUNDLE_JSON,
        observation,
        kind=CertificationBundleArtifactKind.OBSERVABILITY,
    )


def _bundle_address(bundle: CapabilityCertificationBundle) -> str:
    return content_hash(bundle.manifest_dict(include_payloads=False), prefix="capability-certification-bundle")


def build_capability_certification_bundle(
    registry: CapabilityRegistry | None = None,
    *,
    bundle_id: str = "capability-certification-public-bundle",
    run_id: str | None = None,
) -> CapabilityCertificationBundle:
    """Run live certification and assemble a public offline artifact set."""

    catalog = registry or default_capability_registry()
    require_non_empty(bundle_id, "bundle_id")
    runtime = run_capability_certification(run_id=run_id, registry=catalog)
    replay = replay_capability_certification(catalog)
    failures = run_capability_certification_failure_injections(catalog)
    base = _base_artifacts(runtime, replay, failures, catalog)
    artifacts = base + (_build_observability_artifact(bundle_id, runtime, base),)
    report = runtime.report
    checks = (
        _check("artifact-inventory", CertificationBundleCheckPlane.MANIFEST, len(artifacts) == CERTIFICATION_BUNDLE_ARTIFACT_COUNT, len(artifacts), CERTIFICATION_BUNDLE_ARTIFACT_COUNT, "certification artifact inventory is closed"),
        _check("artifact-identities-unique", CertificationBundleCheckPlane.CLOSURE, len({item.artifact_id for item in artifacts}) == len(artifacts), len({item.artifact_id for item in artifacts}), len(artifacts), "artifact identifiers are unique"),
        _check("artifact-paths-unique", CertificationBundleCheckPlane.CLOSURE, len({item.relative_path for item in artifacts}) == len(artifacts), len({item.relative_path for item in artifacts}), len(artifacts), "artifact paths are unique"),
        _check("artifact-addresses-present", CertificationBundleCheckPlane.ARTIFACT, all(item.content_address.startswith(f"{CAPABILITY_CERTIFICATION_BUNDLE_ARTIFACT_PREFIX}:") for item in artifacts), sum(item.content_address.startswith(f"{CAPABILITY_CERTIFICATION_BUNDLE_ARTIFACT_PREFIX}:") for item in artifacts), len(artifacts), "every artifact has an exact-byte address"),
        _check("artifact-payloads-present", CertificationBundleCheckPlane.ARTIFACT, all(item.payload is not None for item in artifacts), sum(item.payload is not None for item in artifacts), len(artifacts), "every artifact is materializable"),
        _check("public-json-boundary", CertificationBundleCheckPlane.PUBLIC_BOUNDARY, all(item.media_type != CERTIFICATION_BUNDLE_JSON or (item.payload is not None and not _has_forbidden_key(json.loads(item.payload)) and not contains_private_key(json.loads(item.payload))) for item in artifacts), True, True, "JSON artifacts contain no private or attribution keys"),
        _check("certificate-denominator", CertificationBundleCheckPlane.CERTIFICATION, report.capability_count == 256 and len(report.domain_summaries) == 16, {"capabilities": report.capability_count, "domains": len(report.domain_summaries)}, {"capabilities": 256, "domains": 16}, "the full catalog denominator is retained"),
        _check("check-denominator", CertificationBundleCheckPlane.CERTIFICATION, report.total_checks == 2572, report.total_checks, 2572, "row and global certification checks are conserved"),
        _check("runtime-accepted", CertificationBundleCheckPlane.CERTIFICATION, runtime.accepted, runtime.state, "accepted", "the live certification runtime passed"),
        _check("quality-accepted", CertificationBundleCheckPlane.CERTIFICATION, runtime.quality.accepted, runtime.quality.accepted, True, "the independent quality gate passed"),
        _check("replay-accepted", CertificationBundleCheckPlane.REPLAY, replay.accepted, replay.accepted, True, "the certification replay address is stable"),
        _check("failure-controls-accepted", CertificationBundleCheckPlane.CERTIFICATION, failures.accepted, failures.accepted, True, "missing implementation and test controls remain visible"),
    )
    accepted = all(item.passed for item in checks)
    state = CertificationBundleState.READY if accepted else CertificationBundleState.BLOCKED
    body = {
        "bundle_id": bundle_id,
        "version": CAPABILITY_CERTIFICATION_BUNDLE_VERSION,
        "boundary": CAPABILITY_CERTIFICATION_BUNDLE_BOUNDARY,
        "report_id": report.report_id,
        "run_id": run_id or runtime.run_id,
        "catalog_address": report.catalog_address,
        "runtime_address": runtime.content_address,
        "state": state,
        "accepted": accepted,
        "artifacts": artifacts,
        "checks": checks,
        "certificate_count": report.capability_count,
        "domain_count": len(report.domain_summaries),
        "total_checks": report.total_checks,
        "passed_check_count": report.passed_checks,
        "failed_check_count": report.failed_checks,
        "warning_count": sum(not item.passed for item in checks),
    }
    provisional = CapabilityCertificationBundle(**body, content_address="capability-certification-bundle:provisional")
    return CapabilityCertificationBundle(**body, content_address=_bundle_address(provisional))


def bundle_manifest_text(bundle: CapabilityCertificationBundle) -> str:
    return canonical_json(bundle.to_dict(include_payloads=False)) + "\n"


def write_capability_certification_bundle(
    bundle: CapabilityCertificationBundle,
    destination: str | Path,
) -> Path:
    """Write exact UTF-8 files without deleting unrelated destination files."""

    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    for artifact in bundle.artifacts:
        if artifact.payload is None:
            raise ValidationError(f"artifact {artifact.artifact_id} has no payload")
        target = root / Path(*PurePosixPath(artifact.relative_path).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(artifact.payload.encode("utf-8"))
    (root / CAPABILITY_CERTIFICATION_BUNDLE_MANIFEST).write_bytes(bundle_manifest_text(bundle).encode("utf-8"))
    return root


def _verification(bundle_id: str, checks: Iterable[CertificationBundleCheck]) -> CertificationBundleVerification:
    values = tuple(checks)
    accepted = bool(values) and all(item.passed for item in values)
    body = {"bundle_id": bundle_id, "accepted": accepted, "checks": values}
    return CertificationBundleVerification(bundle_id, accepted, values, content_hash(body, prefix="capability-certification-bundle-verification"))


def _manifest_address_valid(manifest: Mapping[str, Any]) -> bool:
    expected = manifest.get("content_address")
    body = dict(manifest)
    body.pop("content_address", None)
    return isinstance(expected, str) and expected == content_hash(body, prefix="capability-certification-bundle")


def verify_capability_certification_bundle(destination: str | Path) -> CertificationBundleVerification:
    """Verify a bundle directory using only manifest and artifact bytes."""

    root = Path(destination)
    manifest_path = root / CAPABILITY_CERTIFICATION_BUNDLE_MANIFEST
    if not root.exists() or not root.is_dir():
        return _verification("missing-bundle", (_check("bundle-directory", CertificationBundleCheckPlane.MANIFEST, False, str(root), "directory", "bundle directory is missing"),))
    if not manifest_path.exists() or not manifest_path.is_file() or manifest_path.is_symlink():
        return _verification("missing-manifest", (_check("manifest-present", CertificationBundleCheckPlane.MANIFEST, False, False, True, "bundle manifest is missing"),))
    try:
        raw_manifest = manifest_path.read_bytes()
        manifest = json.loads(raw_manifest.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _verification("invalid-manifest", (_check("manifest-readable", CertificationBundleCheckPlane.MANIFEST, False, type(exc).__name__, "UTF-8 JSON object", "bundle manifest cannot be read"),))
    if not isinstance(manifest, Mapping):
        return _verification("invalid-manifest", (_check("manifest-object", CertificationBundleCheckPlane.MANIFEST, False, type(manifest).__name__, "object", "manifest root must be an object"),))
    bundle_id = _text(manifest.get("bundle_id", "unknown-bundle"))
    checks: list[CertificationBundleCheck] = [
        _check("manifest-canonical", CertificationBundleCheckPlane.MANIFEST, raw_manifest.decode("utf-8") == canonical_json(manifest) + "\n", len(raw_manifest), len((canonical_json(manifest) + "\n").encode("utf-8")), "manifest uses canonical UTF-8 JSON"),
        _check("manifest-public-boundary", CertificationBundleCheckPlane.PUBLIC_BOUNDARY, not _has_forbidden_key(manifest) and not contains_private_key(manifest), True, True, "manifest is public-safe"),
        _check("manifest-version", CertificationBundleCheckPlane.MANIFEST, manifest.get("version") == CAPABILITY_CERTIFICATION_BUNDLE_VERSION, manifest.get("version"), CAPABILITY_CERTIFICATION_BUNDLE_VERSION, "bundle version is supported"),
        _check("manifest-boundary", CertificationBundleCheckPlane.PUBLIC_BOUNDARY, manifest.get("boundary") == CAPABILITY_CERTIFICATION_BUNDLE_BOUNDARY, manifest.get("boundary"), CAPABILITY_CERTIFICATION_BUNDLE_BOUNDARY, "bundle boundary is closed"),
        _check("manifest-address", CertificationBundleCheckPlane.MANIFEST, _manifest_address_valid(manifest), manifest.get("content_address"), "reconstructed bundle address", "manifest address reconstructs"),
    ]
    schema_validation = validate_capability_certification_bundle_manifest(manifest)
    checks.append(
        _check(
            "manifest-schema",
            CertificationBundleCheckPlane.SCHEMA,
            schema_validation.accepted,
            schema_validation.failed_check_ids,
            (),
            "manifest conforms to the closed certification bundle schema",
        )
    )
    artifacts = manifest.get("artifacts", ())
    manifest_checks = manifest.get("checks", ())
    if not isinstance(artifacts, list) or not isinstance(manifest_checks, list):
        checks.append(_check("manifest-collections", CertificationBundleCheckPlane.MANIFEST, False, {"artifacts": type(artifacts).__name__, "checks": type(manifest_checks).__name__}, "arrays", "manifest collections must be arrays"))
        return _verification(bundle_id, checks)
    checks.extend(
        (
            _check("manifest-counts", CertificationBundleCheckPlane.CLOSURE, manifest.get("artifact_count") == len(artifacts) and manifest.get("passed_check_count", -1) + manifest.get("failed_check_count", -1) == manifest.get("total_checks", -2), {"artifact_count": manifest.get("artifact_count"), "passed": manifest.get("passed_check_count"), "failed": manifest.get("failed_check_count"), "total": manifest.get("total_checks")}, {"artifacts": len(artifacts), "certification_counts": "passed + failed = total"}, "manifest counts conserve artifact and certification collections"),
            _check("artifact-identities-unique", CertificationBundleCheckPlane.CLOSURE, len([item.get("artifact_id") for item in artifacts if isinstance(item, Mapping)]) == len({item.get("artifact_id") for item in artifacts if isinstance(item, Mapping)}) and len([item.get("relative_path") for item in artifacts if isinstance(item, Mapping)]) == len({item.get("relative_path") for item in artifacts if isinstance(item, Mapping)}), True, True, "artifact IDs and paths are unique"),
            _check("manifest-release-accepted", CertificationBundleCheckPlane.CLOSURE, bool(manifest.get("accepted")) and manifest.get("state") == CertificationBundleState.READY.value and all(isinstance(item, Mapping) and bool(item.get("passed")) for item in manifest_checks), {"accepted": manifest.get("accepted"), "state": manifest.get("state")}, {"accepted": True, "state": CertificationBundleState.READY.value}, "release readiness is retained in the manifest"),
        )
    )
    expected_paths = {CAPABILITY_CERTIFICATION_BUNDLE_MANIFEST}
    for item in artifacts:
        if not isinstance(item, Mapping):
            continue
        artifact_id = _text(item.get("artifact_id", "unknown"))
        relative_path = _text(item.get("relative_path", ""))
        safe = _safe_relative_path(relative_path)
        checks.append(_check(f"path-safe:{artifact_id}", CertificationBundleCheckPlane.ARTIFACT, safe, relative_path, "safe relative path", "artifact path cannot escape bundle root"))
        if not safe:
            continue
        expected_paths.add(relative_path)
        target = root / Path(*PurePosixPath(relative_path).parts)
        regular = target.exists() and target.is_file() and not target.is_symlink()
        checks.append(_check(f"present:{artifact_id}", CertificationBundleCheckPlane.ARTIFACT, regular, str(target) if target.exists() else "missing", "regular file", "manifest artifact is materialized"))
        if not regular:
            continue
        try:
            raw = target.read_bytes()
            text = raw.decode("utf-8")
            address = hash_bytes(raw, prefix=CAPABILITY_CERTIFICATION_BUNDLE_ARTIFACT_PREFIX)
            checks.append(_check(f"bytes:{artifact_id}", CertificationBundleCheckPlane.ARTIFACT, len(raw) == item.get("byte_count") and _line_count(text) == item.get("line_count") and address == item.get("content_address"), {"bytes": len(raw), "lines": _line_count(text), "address": address}, {"bytes": item.get("byte_count"), "lines": item.get("line_count"), "address": item.get("content_address")}, "artifact bytes and address match"))
            if item.get("media_type") == CERTIFICATION_BUNDLE_JSON:
                try:
                    parsed = json.loads(text)
                    public = not _has_forbidden_key(parsed) and not contains_private_key(parsed)
                except json.JSONDecodeError:
                    public = False
                checks.append(_check(f"json-public:{artifact_id}", CertificationBundleCheckPlane.PUBLIC_BOUNDARY, public, public, True, "JSON artifact remains public-safe"))
        except (OSError, UnicodeDecodeError) as exc:
            checks.append(_check(f"readable:{artifact_id}", CertificationBundleCheckPlane.ARTIFACT, False, type(exc).__name__, "UTF-8 file", "artifact cannot be decoded"))
    actual_paths: set[str] = set()
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink() or not path.is_file():
            checks.append(_check(f"regular:{relative}", CertificationBundleCheckPlane.CLOSURE, False, "symlink or directory", "regular file", "bundle tree contains a non-file entry"))
            continue
        actual_paths.add(relative)
    checks.append(_check("unexpected-files", CertificationBundleCheckPlane.CLOSURE, actual_paths == expected_paths, tuple(sorted(actual_paths - expected_paths)), tuple(sorted(expected_paths - actual_paths)), "bundle contains exactly its manifest and artifacts"))
    return _verification(bundle_id, checks)


def certification_bundle_artifact_csv(bundle: CapabilityCertificationBundle) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("artifact_id", "kind", "relative_path", "media_type", "byte_count", "line_count", "content_address"))
    for item in bundle.artifacts:
        writer.writerow((item.artifact_id, item.kind.value, item.relative_path, item.media_type, item.byte_count, item.line_count, item.content_address))
    return output.getvalue()


__all__ = [
    "CERTIFICATION_BUNDLE_ARTIFACT_COUNT",
    "CAPABILITY_CERTIFICATION_BUNDLE_ARTIFACT_PREFIX",
    "CAPABILITY_CERTIFICATION_BUNDLE_BOUNDARY",
    "CERTIFICATION_BUNDLE_CSV",
    "CERTIFICATION_BUNDLE_JSON",
    "CERTIFICATION_BUNDLE_MARKDOWN",
    "build_capability_certification_bundle",
    "bundle_manifest_text",
    "certification_bundle_artifact_csv",
    "verify_capability_certification_bundle",
    "write_capability_certification_bundle",
]
