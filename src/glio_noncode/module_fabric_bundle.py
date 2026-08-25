"""Build and verify a portable offline module-fabric release bundle.

The in-memory module-fabric runtime is useful for CI, but operators need a
handoff that survives process boundaries.  This module materializes the
runtime's public projections as deterministic UTF-8 files and verifies the
directory without importing the producing implementation.  Every file is
addressed by its exact bytes; the root manifest is addressed by its exact
metadata projection; and a blocked bundle remains inspectable instead of
being silently discarded.

The bundle is intentionally aggregate and operational.  It proves declared
module and test references, release checks, and reproducibility.  It does not
prove scientific validity, clinical utility, authorship, model provenance, or
any treatment conclusion.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable, Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from .capability_registry import CapabilityRegistry, default_capability_registry
from .errors import ValidationError
from .module_fabric_bundle_contracts import (
    MODULE_FABRIC_BUNDLE_ARTIFACT_PREFIX,
    MODULE_FABRIC_BUNDLE_MANIFEST,
    MODULE_FABRIC_BUNDLE_VERSION,
    FabricBundle,
    FabricBundleArtifact,
    FabricBundleArtifactKind,
    FabricBundleCheck,
    FabricBundleCheckPlane,
    FabricBundleState,
    FabricBundleVerification,
    bundle_check,
)
from .module_fabric_bundle_schema import validate_module_fabric_bundle_manifest
from .module_fabric_catalog import default_module_fabric_catalog
from .module_fabric_contracts import FabricFixture
from .module_fabric_data_dictionary import default_module_fabric_data_dictionary
from .module_fabric_exports import (
    export_module_fabric_review_csv,
    module_fabric_checks_csv,
    module_fabric_summary,
    render_module_fabric_review_markdown,
)
from .module_fabric_observability import build_module_fabric_trace
from .module_fabric_public_data import default_module_fabric_fixture
from .module_fabric_reports import module_fabric_report, render_module_fabric_runtime_markdown
from .module_fabric_runtime import ModuleFabricRuntimeOptions, run_module_fabric_runtime
from .module_fabric_schema import default_module_fabric_schema, validate_module_fabric_schema
from .module_fabric_source_registry import build_module_fabric_source_registry
from .module_fabric_support import contains_private_key
from .run_workspace import _has_forbidden_key, _public_projection
from .serialization import canonical_json, content_hash, hash_bytes, jsonable, require_non_empty

MODULE_FABRIC_BUNDLE_BOUNDARY = "public_aggregate_module_fabric_bundle"
MODULE_FABRIC_BUNDLE_JSON_MEDIA_TYPE = "application/json"
MODULE_FABRIC_BUNDLE_CSV_MEDIA_TYPE = "text/csv"
MODULE_FABRIC_BUNDLE_MARKDOWN_MEDIA_TYPE = "text/markdown"


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
    if path.is_absolute() or not path.parts:
        return False
    if any(part in {"", ".", ".."} for part in path.parts):
        return False
    return all(len(part) <= 160 for part in path.parts)


def _public_value(value: Any) -> Any:
    """Return a JSON-compatible public projection or fail closed."""

    projected = _public_projection(jsonable(value))
    if _has_forbidden_key(projected) or contains_private_key(projected):
        raise ValidationError("module-fabric bundle projection crosses the public boundary")
    return projected


def _json_text(value: Any) -> str:
    return canonical_json(_public_value(value)) + "\n"


def _line_count(payload: str) -> int:
    return len(payload.splitlines())


def _artifact(
    artifact_id: str,
    relative_path: str,
    media_type: str,
    payload: Any,
    *,
    kind: FabricBundleArtifactKind,
) -> FabricBundleArtifact:
    path = _text(relative_path)
    if not _safe_relative_path(path):
        raise ValidationError(f"unsafe module-fabric bundle path: {relative_path!r}")
    if media_type == MODULE_FABRIC_BUNDLE_JSON_MEDIA_TYPE:
        text = _json_text(payload)
    else:
        text = _text(payload)
        if media_type in {MODULE_FABRIC_BUNDLE_CSV_MEDIA_TYPE, MODULE_FABRIC_BUNDLE_MARKDOWN_MEDIA_TYPE}:
            text = text.rstrip("\n") + "\n"
    encoded = text.encode("utf-8")
    return FabricBundleArtifact(
        artifact_id=_safe_component(artifact_id, "artifact_id"),
        relative_path=path,
        media_type=_text(media_type),
        kind=kind,
        byte_count=len(encoded),
        line_count=_line_count(text),
        content_address=hash_bytes(encoded, prefix=MODULE_FABRIC_BUNDLE_ARTIFACT_PREFIX),
        payload=text,
    )


def _json_artifact(
    artifact_id: str,
    relative_path: str,
    kind: FabricBundleArtifactKind,
    value: Any,
) -> FabricBundleArtifact:
    return _artifact(artifact_id, relative_path, MODULE_FABRIC_BUNDLE_JSON_MEDIA_TYPE, value, kind=kind)


def _check(
    check_id: str,
    plane: FabricBundleCheckPlane,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> FabricBundleCheck:
    return bundle_check(check_id, plane, passed, observed, required, detail)


def _artifact_specs(
    fixture: FabricFixture,
    runtime: Any,
    registry: CapabilityRegistry,
) -> tuple[FabricBundleArtifact, ...]:
    """Build the complete, stable artifact inventory for one runtime."""

    source_registry = build_module_fabric_source_registry(fixture)
    catalog = default_module_fabric_catalog(registry)
    schema = default_module_fabric_schema()
    dictionary = default_module_fabric_data_dictionary()
    trace = build_module_fabric_trace(runtime)
    report = module_fabric_report(runtime)
    summary = module_fabric_summary(fixture, runtime.evaluation)
    compliance = runtime.compliance.to_dict() if runtime.compliance is not None else {
        "accepted": False,
        "checks": (),
    }
    return (
        _json_artifact("fixture", "fixture.json", FabricBundleArtifactKind.FIXTURE, fixture),
        _json_artifact("evaluation", "evaluation.json", FabricBundleArtifactKind.EVALUATION, runtime.evaluation),
        _json_artifact("metrics", "metrics.json", FabricBundleArtifactKind.METRICS, runtime.metrics),
        _json_artifact("depth", "depth.json", FabricBundleArtifactKind.DEPTH, runtime.depth),
        _json_artifact("lineage", "lineage.json", FabricBundleArtifactKind.LINEAGE, runtime.lineage),
        _json_artifact("replay", "replay.json", FabricBundleArtifactKind.REPLAY, runtime.replay),
        _json_artifact("quality", "quality.json", FabricBundleArtifactKind.QUALITY, runtime.quality),
        _json_artifact("release", "release.json", FabricBundleArtifactKind.RELEASE, runtime.release),
        _json_artifact("runtime", "runtime.json", FabricBundleArtifactKind.RUNTIME, runtime),
        _json_artifact("compliance", "compliance.json", FabricBundleArtifactKind.COMPLIANCE, compliance),
        _json_artifact("catalog", "catalog.json", FabricBundleArtifactKind.CATALOG, catalog),
        _json_artifact("schema", "schema.json", FabricBundleArtifactKind.SCHEMA, schema),
        _json_artifact("dictionary", "data-dictionary.json", FabricBundleArtifactKind.DICTIONARY, dictionary),
        _json_artifact("sources", "sources.json", FabricBundleArtifactKind.SOURCES, source_registry),
        _json_artifact("summary", "summary.json", FabricBundleArtifactKind.SUMMARY, summary),
        _json_artifact("trace", "observability.json", FabricBundleArtifactKind.REPORT, trace),
        _json_artifact("report-summary", "report-summary.json", FabricBundleArtifactKind.REPORT, report),
        _artifact(
            "review",
            "review.csv",
            MODULE_FABRIC_BUNDLE_CSV_MEDIA_TYPE,
            export_module_fabric_review_csv(fixture, runtime.evaluation),
            kind=FabricBundleArtifactKind.REVIEW,
        ),
        _artifact(
            "checks",
            "checks.csv",
            MODULE_FABRIC_BUNDLE_CSV_MEDIA_TYPE,
            module_fabric_checks_csv(runtime),
            kind=FabricBundleArtifactKind.CHECKS,
        ),
        _artifact(
            "review-report",
            "review-report.md",
            MODULE_FABRIC_BUNDLE_MARKDOWN_MEDIA_TYPE,
            render_module_fabric_review_markdown(fixture, runtime.evaluation),
            kind=FabricBundleArtifactKind.REPORT,
        ),
        _artifact(
            "runtime-report",
            "runtime-report.md",
            MODULE_FABRIC_BUNDLE_MARKDOWN_MEDIA_TYPE,
            render_module_fabric_runtime_markdown(runtime),
            kind=FabricBundleArtifactKind.REPORT,
        ),
    )


def _manifest_body(bundle: FabricBundle) -> dict[str, Any]:
    return bundle.manifest_dict(include_payloads=False)


def _bundle_address(bundle: FabricBundle) -> str:
    return content_hash(_manifest_body(bundle), prefix="module-fabric-bundle")


def _verification(
    bundle_id: str,
    checks: Iterable[FabricBundleCheck],
) -> FabricBundleVerification:
    values = tuple(checks)
    accepted = bool(values) and all(item.passed for item in values)
    body = {"bundle_id": bundle_id, "accepted": accepted, "checks": values}
    return FabricBundleVerification(
        bundle_id=bundle_id,
        accepted=accepted,
        checks=values,
        content_address=content_hash(body, prefix="module-fabric-bundle-verification"),
    )


def build_module_fabric_bundle(
    fixture: FabricFixture | None = None,
    registry: CapabilityRegistry | None = None,
    *,
    bundle_id: str = "module-fabric-public-bundle",
    run_id: str = "module-fabric-bundle-runtime",
) -> FabricBundle:
    """Run the module-fabric runtime and assemble its public file inventory."""

    value = fixture or default_module_fabric_fixture(registry)
    catalog = registry or default_capability_registry()
    require_non_empty(bundle_id, "bundle_id")
    require_non_empty(run_id, "run_id")
    runtime = run_module_fabric_runtime(
        value,
        catalog,
        options=ModuleFabricRuntimeOptions(run_id=run_id),
    )
    artifacts = _artifact_specs(value, runtime, catalog)
    checks = (
        _check(
            "artifact-inventory",
            FabricBundleCheckPlane.MANIFEST,
            len(artifacts) == 21,
            len(artifacts),
            21,
            "the public bundle inventory is closed",
        ),
        _check(
            "artifact-identities-unique",
            FabricBundleCheckPlane.CLOSURE,
            len({item.artifact_id for item in artifacts}) == len(artifacts),
            len({item.artifact_id for item in artifacts}),
            len(artifacts),
            "artifact identifiers are unique",
        ),
        _check(
            "artifact-paths-unique",
            FabricBundleCheckPlane.CLOSURE,
            len({item.relative_path for item in artifacts}) == len(artifacts),
            len({item.relative_path for item in artifacts}),
            len(artifacts),
            "artifact paths are unique",
        ),
        _check(
            "artifact-addresses-present",
            FabricBundleCheckPlane.ARTIFACT,
            all(item.content_address.startswith(f"{MODULE_FABRIC_BUNDLE_ARTIFACT_PREFIX}:") for item in artifacts),
            sum(item.content_address.startswith(f"{MODULE_FABRIC_BUNDLE_ARTIFACT_PREFIX}:") for item in artifacts),
            len(artifacts),
            "every artifact is addressed by exact bytes",
        ),
        _check(
            "artifact-payloads-present",
            FabricBundleCheckPlane.ARTIFACT,
            all(item.payload is not None for item in artifacts),
            sum(item.payload is not None for item in artifacts),
            len(artifacts),
            "every in-memory artifact has materializable bytes",
        ),
        _check(
            "public-json-boundary",
            FabricBundleCheckPlane.PUBLIC_BOUNDARY,
            all(
                item.media_type != MODULE_FABRIC_BUNDLE_JSON_MEDIA_TYPE
                or (
                    item.payload is not None
                    and not _has_forbidden_key(json.loads(item.payload))
                    and not contains_private_key(json.loads(item.payload))
                )
                for item in artifacts
            ),
            True,
            True,
            "JSON artifacts contain no direct identifiers or attribution keys",
        ),
        _check(
            "schema-closed",
            FabricBundleCheckPlane.SCHEMA,
            not validate_module_fabric_schema(default_module_fabric_schema()),
            validate_module_fabric_schema(default_module_fabric_schema()),
            (),
            "the module-fabric public schema has no structural issues",
        ),
        _check(
            "runtime-accepted",
            FabricBundleCheckPlane.RUNTIME,
            runtime.state.value == "accepted",
            runtime.state,
            "accepted",
            "the source runtime passed all required stages",
        ),
        _check(
            "runtime-address-present",
            FabricBundleCheckPlane.RUNTIME,
            bool(runtime.content_address),
            runtime.content_address,
            "addressed runtime",
            "the runtime receipt is retained",
        ),
        _check(
            "release-accepted",
            FabricBundleCheckPlane.CLOSURE,
            runtime.release.state.value == "accepted",
            runtime.release.state,
            "accepted",
            "the underlying module-fabric release gate passed",
        ),
        _check(
            "replay-accepted",
            FabricBundleCheckPlane.REPLAY,
            runtime.replay.accepted,
            runtime.replay.accepted,
            True,
            "the source runtime replay receipt passed",
        ),
    )
    accepted = all(item.passed for item in checks)
    state = FabricBundleState.READY if accepted else FabricBundleState.BLOCKED
    body = {
        "bundle_id": bundle_id,
        "version": MODULE_FABRIC_BUNDLE_VERSION,
        "boundary": MODULE_FABRIC_BUNDLE_BOUNDARY,
        "fixture_id": value.fixture_id,
        "run_id": run_id,
        "state": state,
        "accepted": accepted,
        "artifacts": artifacts,
        "checks": checks,
        "runtime_address": runtime.content_address,
        "warning_count": sum(not item.passed for item in checks),
    }
    provisional = FabricBundle(
        **body,
        content_address="module-fabric-bundle:provisional",
    )
    return FabricBundle(
        **body,
        content_address=_bundle_address(provisional),
    )


def bundle_manifest_text(bundle: FabricBundle) -> str:
    """Render the root manifest with no artifact payloads."""

    return canonical_json(bundle.to_dict(include_payloads=False)) + "\n"


def write_module_fabric_bundle(
    bundle: FabricBundle,
    destination: str | Path,
) -> Path:
    """Write a bundle without deleting unrelated files from the destination."""

    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    for artifact in bundle.artifacts:
        if artifact.payload is None:
            raise ValidationError(f"artifact {artifact.artifact_id} has no payload")
        target = root / Path(*PurePosixPath(artifact.relative_path).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(artifact.payload.encode("utf-8"))
    (root / MODULE_FABRIC_BUNDLE_MANIFEST).write_bytes(bundle_manifest_text(bundle).encode("utf-8"))
    return root


def _check_manifest_address(manifest: Mapping[str, Any]) -> bool:
    expected = manifest.get("content_address")
    body = dict(manifest)
    body.pop("content_address", None)
    return isinstance(expected, str) and expected == content_hash(body, prefix="module-fabric-bundle")


def _manifest_value(manifest: Mapping[str, Any], name: str, default: Any = None) -> Any:
    value = manifest.get(name, default)
    return value


def verify_module_fabric_bundle(destination: str | Path) -> FabricBundleVerification:
    """Verify a materialized bundle using only its files and manifest."""

    root = Path(destination)
    checks: list[FabricBundleCheck] = []
    manifest_path = root / MODULE_FABRIC_BUNDLE_MANIFEST
    if not root.exists() or not root.is_dir():
        return _verification(
            "missing-bundle",
            (_check("bundle-directory", FabricBundleCheckPlane.MANIFEST, False, str(root), "directory", "bundle directory is missing"),),
        )
    if not manifest_path.exists() or not manifest_path.is_file() or manifest_path.is_symlink():
        return _verification(
            "missing-manifest",
            (_check("manifest-present", FabricBundleCheckPlane.MANIFEST, False, False, True, "bundle manifest is missing or is not a regular file"),),
        )
    try:
        raw_manifest = manifest_path.read_bytes()
        manifest = json.loads(raw_manifest.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _verification(
            "invalid-manifest",
            (_check("manifest-readable", FabricBundleCheckPlane.MANIFEST, False, type(exc).__name__, "valid UTF-8 JSON", "bundle manifest cannot be decoded"),),
        )
    if not isinstance(manifest, Mapping):
        return _verification(
            "invalid-manifest",
            (_check("manifest-object", FabricBundleCheckPlane.MANIFEST, False, type(manifest).__name__, "object", "bundle manifest root must be an object"),),
        )
    bundle_id = _text(_manifest_value(manifest, "bundle_id", "unknown-bundle"))
    schema_validation = validate_module_fabric_bundle_manifest(dict(manifest))
    checks.append(
        _check(
            "manifest-schema",
            FabricBundleCheckPlane.SCHEMA,
            schema_validation.accepted,
            schema_validation.failed_check_ids,
            (),
            "manifest satisfies the closed module-fabric bundle schema",
        )
    )
    checks.append(
        _check(
            "manifest-utf8",
            FabricBundleCheckPlane.MANIFEST,
            raw_manifest.decode("utf-8", errors="strict") == canonical_json(manifest) + "\n",
            len(raw_manifest),
            len((canonical_json(manifest) + "\n").encode("utf-8")),
            "manifest uses canonical UTF-8 JSON bytes",
        )
    )
    checks.append(
        _check(
            "manifest-public-boundary",
            FabricBundleCheckPlane.PUBLIC_BOUNDARY,
            not _has_forbidden_key(manifest) and not contains_private_key(manifest),
            True,
            True,
            "manifest contains no prohibited public-boundary keys",
        )
    )
    checks.append(
        _check(
            "manifest-version",
            FabricBundleCheckPlane.MANIFEST,
            manifest.get("version") == MODULE_FABRIC_BUNDLE_VERSION,
            manifest.get("version"),
            MODULE_FABRIC_BUNDLE_VERSION,
            "bundle version is supported",
        )
    )
    checks.append(
        _check(
            "manifest-boundary",
            FabricBundleCheckPlane.PUBLIC_BOUNDARY,
            manifest.get("boundary") == MODULE_FABRIC_BUNDLE_BOUNDARY,
            manifest.get("boundary"),
            MODULE_FABRIC_BUNDLE_BOUNDARY,
            "bundle boundary is the public aggregate module-fabric boundary",
        )
    )
    checks.append(
        _check(
            "manifest-address",
            FabricBundleCheckPlane.MANIFEST,
            _check_manifest_address(manifest),
            manifest.get("content_address"),
            "reconstructed module-fabric-bundle address",
            "manifest address reconstructs from exact metadata",
        )
    )
    artifacts = manifest.get("artifacts", ())
    manifest_checks = manifest.get("checks", ())
    if not isinstance(artifacts, list) or not isinstance(manifest_checks, list):
        checks.append(
            _check(
                "manifest-collections",
                FabricBundleCheckPlane.MANIFEST,
                False,
                {"artifacts": type(artifacts).__name__, "checks": type(manifest_checks).__name__},
                "arrays",
                "manifest artifact and check collections must be arrays",
            )
        )
        return _verification(bundle_id, checks)
    checks.append(
        _check(
            "manifest-counts",
            FabricBundleCheckPlane.CLOSURE,
            manifest.get("artifact_count") == len(artifacts)
            and manifest.get("passed_check_count") == sum(bool(item.get("passed")) for item in manifest_checks if isinstance(item, Mapping))
            and manifest.get("failed_check_count") == len(manifest_checks) - sum(bool(item.get("passed")) for item in manifest_checks if isinstance(item, Mapping)),
            {
                "artifact_count": manifest.get("artifact_count"),
                "passed_check_count": manifest.get("passed_check_count"),
                "failed_check_count": manifest.get("failed_check_count"),
            },
            {"artifact_count": len(artifacts), "check_count": len(manifest_checks)},
            "manifest counts conserve listed artifacts and checks",
        )
    )
    artifact_ids = [item.get("artifact_id") for item in artifacts if isinstance(item, Mapping)]
    artifact_paths = [item.get("relative_path") for item in artifacts if isinstance(item, Mapping)]
    checks.append(
        _check(
            "manifest-identities-unique",
            FabricBundleCheckPlane.CLOSURE,
            len(artifact_ids) == len(set(artifact_ids)) and len(artifact_paths) == len(set(artifact_paths)),
            {"artifact_ids": len(set(artifact_ids)), "paths": len(set(artifact_paths))},
            {"artifact_ids": len(artifact_ids), "paths": len(artifact_paths)},
            "artifact identifiers and paths are unique",
        )
    )
    manifest_checks_pass = all(
        isinstance(item, Mapping) and bool(item.get("passed"))
        for item in manifest_checks
    )
    checks.append(
        _check(
            "manifest-release-accepted",
            FabricBundleCheckPlane.CLOSURE,
            bool(manifest.get("accepted"))
            and manifest.get("state") == FabricBundleState.READY.value
            and manifest_checks_pass,
            {
                "accepted": manifest.get("accepted"),
                "state": manifest.get("state"),
                "checks_pass": manifest_checks_pass,
            },
            {"accepted": True, "state": FabricBundleState.READY.value, "checks_pass": True},
            "a verified bundle is release-ready only when its manifest gates pass",
        )
    )
    expected_paths = {MODULE_FABRIC_BUNDLE_MANIFEST}
    for item in artifacts:
        if not isinstance(item, Mapping):
            continue
        path_value = _text(item.get("relative_path", ""))
        path_ok = _safe_relative_path(path_value)
        checks.append(
            _check(
                f"path-safe:{item.get('artifact_id', 'unknown')}",
                FabricBundleCheckPlane.ARTIFACT,
                path_ok,
                path_value,
                "safe relative POSIX path",
                "artifact path cannot escape the bundle root",
            )
        )
        if not path_ok:
            continue
        expected_paths.add(path_value)
        target = root / Path(*PurePosixPath(path_value).parts)
        regular = target.exists() and target.is_file() and not target.is_symlink()
        checks.append(
            _check(
                f"present:{item.get('artifact_id', 'unknown')}",
                FabricBundleCheckPlane.ARTIFACT,
                regular,
                str(target) if target.exists() else "missing",
                "regular file",
                "every manifest artifact is materialized as a regular file",
            )
        )
        if not regular:
            continue
        try:
            raw = target.read_bytes()
            text = raw.decode("utf-8")
            exact = (
                len(raw) == item.get("byte_count")
                and _line_count(text) == item.get("line_count")
                and hash_bytes(raw, prefix=MODULE_FABRIC_BUNDLE_ARTIFACT_PREFIX) == item.get("content_address")
            )
            checks.append(
                _check(
                    f"bytes:{item.get('artifact_id', 'unknown')}",
                    FabricBundleCheckPlane.ARTIFACT,
                    exact,
                    {"bytes": len(raw), "lines": _line_count(text), "address": hash_bytes(raw, prefix=MODULE_FABRIC_BUNDLE_ARTIFACT_PREFIX)},
                    {"bytes": item.get("byte_count"), "lines": item.get("line_count"), "address": item.get("content_address")},
                    "artifact bytes, line count, and content address match the manifest",
                )
            )
            if item.get("media_type") == MODULE_FABRIC_BUNDLE_JSON_MEDIA_TYPE:
                try:
                    parsed = json.loads(text)
                    public = not _has_forbidden_key(parsed) and not contains_private_key(parsed)
                except json.JSONDecodeError:
                    public = False
                checks.append(
                    _check(
                        f"json-public:{item.get('artifact_id', 'unknown')}",
                        FabricBundleCheckPlane.PUBLIC_BOUNDARY,
                        public,
                        public,
                        True,
                        "JSON artifact is valid and remains within the public boundary",
                    )
                )
        except (OSError, UnicodeDecodeError) as exc:
            checks.append(
                _check(
                    f"readable:{item.get('artifact_id', 'unknown')}",
                    FabricBundleCheckPlane.ARTIFACT,
                    False,
                    type(exc).__name__,
                    "readable UTF-8 file",
                    "artifact cannot be read as UTF-8",
                )
            )
    actual_paths: set[str] = set()
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink() or not path.is_file():
            checks.append(
                _check(
                    f"regular:{relative}",
                    FabricBundleCheckPlane.CLOSURE,
                    False,
                    "symlink or directory",
                    "regular file",
                    "bundle trees cannot contain symlinks or unlisted directories as artifacts",
                )
            )
            continue
        actual_paths.add(relative)
    checks.append(
        _check(
            "unexpected-files",
            FabricBundleCheckPlane.CLOSURE,
            actual_paths == expected_paths,
            tuple(sorted(actual_paths - expected_paths)),
            tuple(sorted(expected_paths - actual_paths)),
            "the materialized tree has no unexpected or missing files",
        )
    )
    return _verification(bundle_id, checks)


def bundle_artifact_bytes(bundle: FabricBundle, artifact_id: str) -> bytes:
    """Return one artifact's exact bytes from an in-memory bundle."""

    for artifact in bundle.artifacts:
        if artifact.artifact_id == artifact_id:
            if artifact.payload is None:
                raise ValidationError(f"artifact {artifact_id} has no payload")
            return artifact.payload.encode("utf-8")
    raise ValidationError(f"unknown module-fabric bundle artifact: {artifact_id}")


def bundle_artifact_csv(bundle: FabricBundle) -> str:
    """Render the manifest artifact inventory as deterministic CSV."""

    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("artifact_id", "kind", "relative_path", "media_type", "byte_count", "line_count", "content_address"))
    for item in bundle.artifacts:
        writer.writerow((item.artifact_id, item.kind.value, item.relative_path, item.media_type, item.byte_count, item.line_count, item.content_address))
    return output.getvalue()


__all__ = [
    "MODULE_FABRIC_BUNDLE_BOUNDARY",
    "MODULE_FABRIC_BUNDLE_CSV_MEDIA_TYPE",
    "MODULE_FABRIC_BUNDLE_JSON_MEDIA_TYPE",
    "MODULE_FABRIC_BUNDLE_MARKDOWN_MEDIA_TYPE",
    "bundle_artifact_bytes",
    "bundle_artifact_csv",
    "bundle_manifest_text",
    "build_module_fabric_bundle",
    "verify_module_fabric_bundle",
    "write_module_fabric_bundle",
]
