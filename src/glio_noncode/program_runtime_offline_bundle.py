"""Build and materialize the architecture-program offline handoff.

The builder turns the accepted in-process runtime into a finite directory of
JSON, CSV, and Markdown artifacts.  It keeps the producer's useful detail,
but makes the transport rules explicit:

* all paths are relative and normalized;
* JSON is serialized canonically;
* artifact addresses cover the bytes that are written;
* manifest addresses cover the complete inventory and checks;
* projections are recursively filtered to public aggregate keys.

No network access or mutable service state is required.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from .errors import ValidationError
from .module_fabric_support import contains_private_key
from .program_runtime_bundle import build_program_release, program_release_payloads
from .program_runtime_contracts import ProgramRuntime
from .program_runtime_execution import run_program_runtime
from .program_runtime import architecture_program_domain_matrix
from .program_runtime_offline_contracts import (
    PROGRAM_RUNTIME_OFFLINE_ARTIFACT_COUNT,
    PROGRAM_RUNTIME_OFFLINE_ARTIFACT_PREFIX,
    PROGRAM_RUNTIME_OFFLINE_BOUNDARY,
    PROGRAM_RUNTIME_OFFLINE_BUNDLE_VERSION,
    PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT,
    PROGRAM_RUNTIME_OFFLINE_MANIFEST_FILENAME,
    PROGRAM_RUNTIME_OFFLINE_OPERATION_COUNT,
    PROGRAM_RUNTIME_OFFLINE_PROGRAM_CHECK_COUNT,
    PROGRAM_RUNTIME_OFFLINE_QUALITY_CHECK_COUNT,
    PROGRAM_RUNTIME_OFFLINE_RELEASE_ARTIFACT_COUNT,
    PROGRAM_RUNTIME_OFFLINE_RUNTIME_STAGE_COUNT,
    ProgramRuntimeOfflineArtifact,
    ProgramRuntimeOfflineArtifactKind,
    ProgramRuntimeOfflineBundle,
    ProgramRuntimeOfflineBundleState,
    ProgramRuntimeOfflineCheckPlane,
    program_runtime_offline_check,
)
from .program_runtime_operational import build_program_operational_trace
from .program_runtime_replay import (
    replay_architecture_program,
    run_program_runtime_failure_injections,
)
from .serialization import canonical_json, content_hash, hash_bytes, jsonable, require_non_empty


PROGRAM_RUNTIME_OFFLINE_JSON_MEDIA_TYPE = "application/json"
PROGRAM_RUNTIME_OFFLINE_CSV_MEDIA_TYPE = "text/csv"
PROGRAM_RUNTIME_OFFLINE_MARKDOWN_MEDIA_TYPE = "text/markdown"

PROGRAM_RUNTIME_OFFLINE_FORBIDDEN_KEYS = frozenset(
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
        "phone",
        "primary_agent",
        "primary_agent_id",
        "produced_by",
        "programming_language",
        "patient_id",
        "subject_id",
        "participant_id",
        "individual_id",
        "medical_record_number",
    }
)

_BASE_ARTIFACTS: tuple[tuple[str, ProgramRuntimeOfflineArtifactKind, str, str], ...] = (
    (
        "runtime",
        ProgramRuntimeOfflineArtifactKind.RUNTIME,
        "program-runtime.json",
        PROGRAM_RUNTIME_OFFLINE_JSON_MEDIA_TYPE,
    ),
    (
        "report",
        ProgramRuntimeOfflineArtifactKind.REPORT,
        "program-report.json",
        PROGRAM_RUNTIME_OFFLINE_JSON_MEDIA_TYPE,
    ),
    (
        "summary",
        ProgramRuntimeOfflineArtifactKind.SUMMARY,
        "program-summary.json",
        PROGRAM_RUNTIME_OFFLINE_JSON_MEDIA_TYPE,
    ),
    (
        "receipts",
        ProgramRuntimeOfflineArtifactKind.RECEIPTS,
        "program-receipts.csv",
        PROGRAM_RUNTIME_OFFLINE_CSV_MEDIA_TYPE,
    ),
    (
        "checks",
        ProgramRuntimeOfflineArtifactKind.CHECKS,
        "program-checks.csv",
        PROGRAM_RUNTIME_OFFLINE_CSV_MEDIA_TYPE,
    ),
    (
        "domains",
        ProgramRuntimeOfflineArtifactKind.DOMAINS,
        "program-domains.csv",
        PROGRAM_RUNTIME_OFFLINE_CSV_MEDIA_TYPE,
    ),
    (
        "markdown",
        ProgramRuntimeOfflineArtifactKind.MARKDOWN,
        "program-report.md",
        PROGRAM_RUNTIME_OFFLINE_MARKDOWN_MEDIA_TYPE,
    ),
    (
        "replay",
        ProgramRuntimeOfflineArtifactKind.REPLAY,
        "program-replay.json",
        PROGRAM_RUNTIME_OFFLINE_JSON_MEDIA_TYPE,
    ),
    (
        "failure-controls",
        ProgramRuntimeOfflineArtifactKind.FAILURE_CONTROLS,
        "program-failures.json",
        PROGRAM_RUNTIME_OFFLINE_JSON_MEDIA_TYPE,
    ),
    (
        "specifications",
        ProgramRuntimeOfflineArtifactKind.SPECIFICATIONS,
        "program-specifications.json",
        PROGRAM_RUNTIME_OFFLINE_JSON_MEDIA_TYPE,
    ),
    (
        "matrix",
        ProgramRuntimeOfflineArtifactKind.MATRIX,
        "program-matrix.json",
        PROGRAM_RUNTIME_OFFLINE_JSON_MEDIA_TYPE,
    ),
)

_DERIVED_ARTIFACTS: tuple[tuple[str, ProgramRuntimeOfflineArtifactKind, str], ...] = (
    ("operational", ProgramRuntimeOfflineArtifactKind.OPERATIONAL, "program-operational.json"),
    ("operations", ProgramRuntimeOfflineArtifactKind.OPERATIONS, "program-operations.json"),
    ("stages", ProgramRuntimeOfflineArtifactKind.STAGES, "program-stages.json"),
    ("quality", ProgramRuntimeOfflineArtifactKind.QUALITY, "program-quality.json"),
    (
        "release-checks",
        ProgramRuntimeOfflineArtifactKind.RELEASE_CHECKS,
        "program-release-checks.json",
    ),
    ("sources", ProgramRuntimeOfflineArtifactKind.SOURCES, "program-sources.json"),
    ("capabilities", ProgramRuntimeOfflineArtifactKind.CAPABILITIES, "program-capabilities.json"),
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
            if str(key).casefold() not in PROGRAM_RUNTIME_OFFLINE_FORBIDDEN_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_public_projection(item) for item in value]
    return value


def public_program_projection(value: Any) -> Any:
    """Return a public projection or fail closed when a private key remains."""

    projected = _public_projection(value)
    if contains_private_key(projected):
        raise ValidationError("program offline bundle crosses the public boundary")
    return projected


def _json_text(value: Any) -> str:
    return canonical_json(public_program_projection(value)) + "\n"


def _line_count(value: str) -> int:
    return len(value.splitlines())


def _artifact(
    artifact_id: str,
    kind: ProgramRuntimeOfflineArtifactKind,
    filename: str,
    media_type: str,
    payload: Any,
) -> ProgramRuntimeOfflineArtifact:
    path = str(filename)
    if not _safe_relative_path(path):
        raise ValidationError(f"unsafe program bundle path: {path!r}")
    if media_type == PROGRAM_RUNTIME_OFFLINE_JSON_MEDIA_TYPE:
        text = _json_text(payload)
    else:
        text = str(payload).rstrip("\n") + "\n"
    raw = text.encode("utf-8")
    return ProgramRuntimeOfflineArtifact(
        artifact_id=_safe_component(artifact_id, "artifact_id"),
        relative_path=path,
        media_type=media_type,
        kind=kind,
        byte_count=len(raw),
        line_count=_line_count(text),
        content_address=hash_bytes(raw, prefix=PROGRAM_RUNTIME_OFFLINE_ARTIFACT_PREFIX),
        payload=text,
    )


def _json_value(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"program release projection is not JSON: {exc}") from exc


def _derived_values(runtime: ProgramRuntime, release: Any, operational: Any) -> dict[str, Any]:
    report = runtime.report
    return {
        "operational": operational.to_dict(),
        "operations": [item.to_dict() for item in report.receipts],
        "stages": [item.to_dict() for item in runtime.stages],
        "quality": runtime.quality.to_dict(),
        "release-checks": [item.to_dict() for item in release.checks],
        "sources": [item.to_dict() for item in report.specs],
        "capabilities": list(public_program_projection(architecture_program_domain_matrix(report))),
    }


def program_runtime_offline_payloads(
    runtime: ProgramRuntime,
    *,
    release: Any | None = None,
    operational: Any | None = None,
) -> dict[str, tuple[ProgramRuntimeOfflineArtifactKind, str, Any]]:
    """Build the complete deterministic artifact map before addressing it."""

    selected_release = release or build_program_release(runtime)
    selected_operational = operational or build_program_operational_trace(runtime, selected_release)
    base_text = program_release_payloads(
        runtime,
        replay=replay_architecture_program(),
        failure_controls=run_program_runtime_failure_injections(),
    )
    values: dict[str, tuple[ProgramRuntimeOfflineArtifactKind, str, Any]] = {}
    derived = _derived_values(runtime, selected_release, selected_operational)
    for artifact_id, kind, filename, media_type in _BASE_ARTIFACTS:
        text = base_text[filename]
        values[artifact_id] = (
            kind,
            filename,
            text if media_type != PROGRAM_RUNTIME_OFFLINE_JSON_MEDIA_TYPE else _json_value(text),
        )
    for artifact_id, kind, filename in _DERIVED_ARTIFACTS:
        values[artifact_id] = (
            kind,
            filename,
            derived[artifact_id],
        )
    return values


def _make_checks(
    runtime: ProgramRuntime,
    release: Any,
    operational: Any,
    artifacts: tuple[ProgramRuntimeOfflineArtifact, ...],
) -> tuple[Any, ...]:
    report = runtime.report
    artifact_ids = tuple(item.artifact_id for item in artifacts)
    paths = tuple(item.relative_path for item in artifacts)
    json_artifacts = tuple(
        item for item in artifacts if item.media_type == PROGRAM_RUNTIME_OFFLINE_JSON_MEDIA_TYPE
    )
    checks = (
        program_runtime_offline_check(
            "runtime-accepted",
            ProgramRuntimeOfflineCheckPlane.RUNTIME,
            runtime.accepted,
            runtime.state.value,
            "accepted",
            "source runtime is accepted",
        ),
        program_runtime_offline_check(
            "runtime-addressed",
            ProgramRuntimeOfflineCheckPlane.RUNTIME,
            runtime.content_address.startswith("architecture-program-runtime:"),
            runtime.content_address,
            "architecture-program-runtime:<digest>",
            "source runtime has a stable root address",
        ),
        program_runtime_offline_check(
            "domain-denominator",
            ProgramRuntimeOfflineCheckPlane.DENOMINATOR,
            len(report.receipts) == PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT,
            len(report.receipts),
            PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT,
            "sixteen domain receipts are retained",
        ),
        program_runtime_offline_check(
            "program-check-denominator",
            ProgramRuntimeOfflineCheckPlane.DENOMINATOR,
            len(report.checks) == PROGRAM_RUNTIME_OFFLINE_PROGRAM_CHECK_COUNT,
            len(report.checks),
            PROGRAM_RUNTIME_OFFLINE_PROGRAM_CHECK_COUNT,
            "program checks are conserved",
        ),
        program_runtime_offline_check(
            "quality-denominator",
            ProgramRuntimeOfflineCheckPlane.DENOMINATOR,
            len(runtime.quality.checks) == PROGRAM_RUNTIME_OFFLINE_QUALITY_CHECK_COUNT,
            len(runtime.quality.checks),
            PROGRAM_RUNTIME_OFFLINE_QUALITY_CHECK_COUNT,
            "quality checks are conserved",
        ),
        program_runtime_offline_check(
            "stage-denominator",
            ProgramRuntimeOfflineCheckPlane.DENOMINATOR,
            len(runtime.stages) == PROGRAM_RUNTIME_OFFLINE_RUNTIME_STAGE_COUNT,
            len(runtime.stages),
            PROGRAM_RUNTIME_OFFLINE_RUNTIME_STAGE_COUNT,
            "runtime stages are conserved",
        ),
        program_runtime_offline_check(
            "release-denominator",
            ProgramRuntimeOfflineCheckPlane.RELEASE,
            len(release.artifacts) == PROGRAM_RUNTIME_OFFLINE_RELEASE_ARTIFACT_COUNT,
            len(release.artifacts),
            PROGRAM_RUNTIME_OFFLINE_RELEASE_ARTIFACT_COUNT,
            "source release projections are conserved",
        ),
        program_runtime_offline_check(
            "artifact-denominator",
            ProgramRuntimeOfflineCheckPlane.MANIFEST,
            len(artifacts) == PROGRAM_RUNTIME_OFFLINE_ARTIFACT_COUNT,
            len(artifacts),
            PROGRAM_RUNTIME_OFFLINE_ARTIFACT_COUNT,
            "portable artifact inventory is closed",
        ),
        program_runtime_offline_check(
            "artifact-identities",
            ProgramRuntimeOfflineCheckPlane.MANIFEST,
            len(artifact_ids) == len(set(artifact_ids)),
            len(set(artifact_ids)),
            len(artifact_ids),
            "artifact identifiers are unique",
        ),
        program_runtime_offline_check(
            "path-identities",
            ProgramRuntimeOfflineCheckPlane.MANIFEST,
            len(paths) == len(set(paths)),
            len(set(paths)),
            len(paths),
            "artifact paths are unique",
        ),
        program_runtime_offline_check(
            "artifact-addresses",
            ProgramRuntimeOfflineCheckPlane.ARTIFACT,
            all(
                item.content_address.startswith(f"{PROGRAM_RUNTIME_OFFLINE_ARTIFACT_PREFIX}:")
                for item in artifacts
            ),
            sum(
                item.content_address.startswith(f"{PROGRAM_RUNTIME_OFFLINE_ARTIFACT_PREFIX}:")
                for item in artifacts
            ),
            len(artifacts),
            "every artifact is exact-byte addressed",
        ),
        program_runtime_offline_check(
            "artifact-content",
            ProgramRuntimeOfflineCheckPlane.ARTIFACT,
            all(
                item.payload is not None and item.byte_count == len(item.payload.encode("utf-8"))
                for item in artifacts
            ),
            min(item.byte_count for item in artifacts),
            ">0 and exact",
            "manifest counts equal payload bytes",
        ),
        program_runtime_offline_check(
            "artifact-lines",
            ProgramRuntimeOfflineCheckPlane.ARTIFACT,
            all(item.line_count > 0 for item in artifacts),
            min(item.line_count for item in artifacts),
            ">0",
            "every artifact has a line count",
        ),
        program_runtime_offline_check(
            "report-join",
            ProgramRuntimeOfflineCheckPlane.RECONCILIATION,
            any(item.artifact_id == "report" for item in artifacts) and report.accepted,
            report.accepted,
            True,
            "accepted report is present",
        ),
        program_runtime_offline_check(
            "quality-join",
            ProgramRuntimeOfflineCheckPlane.RECONCILIATION,
            any(item.artifact_id == "quality" for item in artifacts) and runtime.quality.accepted,
            runtime.quality.accepted,
            True,
            "quality gate is present",
        ),
        program_runtime_offline_check(
            "operational-join",
            ProgramRuntimeOfflineCheckPlane.OPERATIONAL,
            operational.accepted,
            operational.to_dict().get("accepted"),
            True,
            "operational trace is accepted",
        ),
        program_runtime_offline_check(
            "operational-stage-join",
            ProgramRuntimeOfflineCheckPlane.OPERATIONAL,
            len(operational.stages) == PROGRAM_RUNTIME_OFFLINE_RUNTIME_STAGE_COUNT,
            len(operational.stages),
            PROGRAM_RUNTIME_OFFLINE_RUNTIME_STAGE_COUNT,
            "operational trace covers every stage",
        ),
        program_runtime_offline_check(
            "release-accepted",
            ProgramRuntimeOfflineCheckPlane.RELEASE,
            release.state.value == "published",
            release.state.value,
            "published",
            "source release is published",
        ),
        program_runtime_offline_check(
            "release-checks",
            ProgramRuntimeOfflineCheckPlane.RELEASE,
            len(release.checks) == 18 and all(item.passed for item in release.checks),
            sum(item.passed for item in release.checks),
            18,
            "release checks close without holds",
        ),
        program_runtime_offline_check(
            "stage-order",
            ProgramRuntimeOfflineCheckPlane.RUNTIME,
            [item.ordinal for item in runtime.stages] == list(range(1, 13)),
            [item.ordinal for item in runtime.stages],
            list(range(1, 13)),
            "runtime stage ordinals are contiguous",
        ),
        program_runtime_offline_check(
            "stage-addresses",
            ProgramRuntimeOfflineCheckPlane.RUNTIME,
            all(item.content_address and item.output_address for item in runtime.stages),
            True,
            True,
            "runtime stage outputs are addressed",
        ),
        program_runtime_offline_check(
            "domain-acceptance",
            ProgramRuntimeOfflineCheckPlane.RUNTIME,
            all(item.accepted for item in report.receipts),
            sum(item.accepted for item in report.receipts),
            len(report.receipts),
            "every domain receipt is accepted",
        ),
        program_runtime_offline_check(
            "program-acceptance",
            ProgramRuntimeOfflineCheckPlane.RUNTIME,
            report.accepted,
            report.state.value,
            "accepted",
            "program report is accepted",
        ),
        program_runtime_offline_check(
            "public-json",
            ProgramRuntimeOfflineCheckPlane.PUBLIC_BOUNDARY,
            all(
                contains_private_key(_json_value(item.payload or "{}")) is False
                for item in json_artifacts
            ),
            True,
            True,
            "JSON projections contain no private keys",
        ),
        program_runtime_offline_check(
            "base-projections",
            ProgramRuntimeOfflineCheckPlane.MANIFEST,
            all(
                any(item.artifact_id == name for item in artifacts) for name, *_ in _BASE_ARTIFACTS
            ),
            11,
            11,
            "all source release projections are transported",
        ),
        program_runtime_offline_check(
            "derived-projections",
            ProgramRuntimeOfflineCheckPlane.MANIFEST,
            all(
                any(item.artifact_id == name for item in artifacts)
                for name, *_ in _DERIVED_ARTIFACTS
            ),
            7,
            7,
            "all offline derived projections are transported",
        ),
        program_runtime_offline_check(
            "operation-denominator",
            ProgramRuntimeOfflineCheckPlane.DENOMINATOR,
            len(report.receipts) == PROGRAM_RUNTIME_OFFLINE_OPERATION_COUNT,
            len(report.receipts),
            PROGRAM_RUNTIME_OFFLINE_OPERATION_COUNT,
            "one operation receipt exists for each domain",
        ),
        program_runtime_offline_check(
            "runtime-release-join",
            ProgramRuntimeOfflineCheckPlane.RECONCILIATION,
            release.runtime_address == runtime.content_address,
            release.runtime_address,
            runtime.content_address,
            "release points at the source runtime",
        ),
        program_runtime_offline_check(
            "failure-controls-present",
            ProgramRuntimeOfflineCheckPlane.RELEASE,
            any(item.artifact_id == "failure-controls" for item in artifacts),
            True,
            True,
            "failure controls remain inspectable",
        ),
        program_runtime_offline_check(
            "specification-catalog-present",
            ProgramRuntimeOfflineCheckPlane.RELEASE,
            any(item.artifact_id == "specifications" for item in artifacts),
            True,
            True,
            "the specification catalog remains inspectable",
        ),
        program_runtime_offline_check(
            "public-boundary-state",
            ProgramRuntimeOfflineCheckPlane.PUBLIC_BOUNDARY,
            not any(item.issue_codes for item in report.receipts),
            True,
            True,
            "domain receipts have no public-boundary issue codes",
        ),
    )
    return checks


def build_program_runtime_offline_bundle(
    runtime: ProgramRuntime | None = None,
    *,
    bundle_id: str = "architecture-program-public-bundle",
    run_id: str = "architecture-program-offline-runtime",
) -> ProgramRuntimeOfflineBundle:
    """Build a deterministic, public aggregate architecture-program bundle."""

    require_non_empty(bundle_id, "bundle_id")
    require_non_empty(run_id, "run_id")
    selected_runtime = runtime or run_program_runtime(run_id=run_id)
    release = build_program_release(selected_runtime)
    operational = build_program_operational_trace(selected_runtime, release)
    payloads = program_runtime_offline_payloads(
        selected_runtime,
        release=release,
        operational=operational,
    )
    artifacts = tuple(
        _artifact(artifact_id, kind, filename, media_type, payload)
        for artifact_id, (kind, filename, payload) in payloads.items()
        for media_type in (
            PROGRAM_RUNTIME_OFFLINE_JSON_MEDIA_TYPE
            if kind
            not in {
                ProgramRuntimeOfflineArtifactKind.RECEIPTS,
                ProgramRuntimeOfflineArtifactKind.CHECKS,
                ProgramRuntimeOfflineArtifactKind.DOMAINS,
                ProgramRuntimeOfflineArtifactKind.MARKDOWN,
            }
            else PROGRAM_RUNTIME_OFFLINE_MARKDOWN_MEDIA_TYPE
            if kind is ProgramRuntimeOfflineArtifactKind.MARKDOWN
            else PROGRAM_RUNTIME_OFFLINE_CSV_MEDIA_TYPE,
        )
    )
    checks = _make_checks(selected_runtime, release, operational, artifacts)
    accepted = all(item.passed for item in checks)
    state = (
        ProgramRuntimeOfflineBundleState.READY
        if accepted
        else ProgramRuntimeOfflineBundleState.BLOCKED
    )
    warning_count = sum(bool(item.issue_codes) for item in selected_runtime.report.receipts)
    manifest_body = {
        "bundle_id": bundle_id,
        "version": PROGRAM_RUNTIME_OFFLINE_BUNDLE_VERSION,
        "boundary": PROGRAM_RUNTIME_OFFLINE_BOUNDARY,
        "run_id": run_id,
        "state": state,
        "accepted": accepted,
        "artifacts": tuple(item.to_dict(include_payload=False) for item in artifacts),
        "checks": tuple(item.to_dict() for item in checks),
        "runtime_address": selected_runtime.content_address,
        "domain_count": len(selected_runtime.report.receipts),
        "stage_count": len(selected_runtime.stages),
        "warning_count": warning_count,
        "artifact_count": len(artifacts),
        "passed_check_count": sum(item.passed for item in checks),
        "failed_check_count": len(checks) - sum(item.passed for item in checks),
    }
    bundle_fields = {
        key: value
        for key, value in manifest_body.items()
        if key not in {"artifact_count", "passed_check_count", "failed_check_count"}
    }
    bundle_fields["artifacts"] = artifacts
    bundle_fields["checks"] = checks
    return ProgramRuntimeOfflineBundle(
        **bundle_fields,
        content_address=content_hash(manifest_body, prefix="program-runtime-offline-bundle"),
    )


def write_program_runtime_offline_bundle(
    bundle: ProgramRuntimeOfflineBundle,
    destination: str | Path,
    *,
    include_payloads: bool = False,
) -> Path:
    """Materialize the bundle using only validated relative paths."""

    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    for artifact in bundle.artifacts:
        path = root / PurePosixPath(artifact.relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if artifact.payload is None:
            raise ValidationError(f"artifact {artifact.artifact_id!r} has no payload")
        path.write_bytes(artifact.payload.encode("utf-8"))
    manifest = bundle.to_dict(include_payloads=include_payloads)
    (root / PROGRAM_RUNTIME_OFFLINE_MANIFEST_FILENAME).write_text(
        _json_text(manifest), encoding="utf-8"
    )
    return root


def _artifact_from_manifest(root: Path, value: Mapping[str, Any]) -> ProgramRuntimeOfflineArtifact:
    relative_path = str(value.get("relative_path", ""))
    if not _safe_relative_path(relative_path):
        raise ValidationError("manifest contains an unsafe artifact path")
    path = root / PurePosixPath(relative_path)
    if not path.is_file():
        raise ValidationError(f"missing program artifact: {relative_path}")
    payload = path.read_text(encoding="utf-8")
    kind = ProgramRuntimeOfflineArtifactKind(str(value["kind"]))
    return ProgramRuntimeOfflineArtifact(
        artifact_id=str(value["artifact_id"]),
        relative_path=relative_path,
        media_type=str(value["media_type"]),
        kind=kind,
        byte_count=int(value["byte_count"]),
        line_count=int(value["line_count"]),
        content_address=str(value["content_address"]),
        payload=payload,
    )


def load_program_runtime_offline_bundle(
    destination: str | Path,
    *,
    include_payloads: bool = True,
) -> ProgramRuntimeOfflineBundle:
    """Load a manifest and its files without importing producer state."""

    root = Path(destination)
    manifest_path = root / PROGRAM_RUNTIME_OFFLINE_MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise ValidationError("program offline manifest is missing")
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValidationError("program offline manifest must be an object")
    artifacts = tuple(
        _artifact_from_manifest(root, item)
        for item in raw.get("artifacts", ())
        if isinstance(item, Mapping)
    )
    checks = tuple(
        program_runtime_offline_check(
            str(item["check_id"]),
            str(item["plane"]),
            bool(item["passed"]),
            item.get("observed"),
            item.get("required"),
            str(item["detail"]),
        )
        for item in raw.get("checks", ())
        if isinstance(item, Mapping)
    )
    bundle = ProgramRuntimeOfflineBundle(
        bundle_id=str(raw["bundle_id"]),
        version=str(raw["version"]),
        boundary=str(raw["boundary"]),
        run_id=str(raw["run_id"]),
        state=ProgramRuntimeOfflineBundleState(str(raw["state"])),
        accepted=bool(raw["accepted"]),
        artifacts=artifacts,
        checks=checks,
        runtime_address=str(raw["runtime_address"]),
        domain_count=int(raw["domain_count"]),
        stage_count=int(raw["stage_count"]),
        warning_count=int(raw["warning_count"]),
        content_address=str(raw.get("content_address", "")),
    )
    if not include_payloads:
        bundle = ProgramRuntimeOfflineBundle(
            bundle_id=bundle.bundle_id,
            version=bundle.version,
            boundary=bundle.boundary,
            run_id=bundle.run_id,
            state=bundle.state,
            accepted=bundle.accepted,
            artifacts=tuple(
                ProgramRuntimeOfflineArtifact(
                    artifact_id=item.artifact_id,
                    relative_path=item.relative_path,
                    media_type=item.media_type,
                    kind=item.kind,
                    byte_count=item.byte_count,
                    line_count=item.line_count,
                    content_address=item.content_address,
                    payload=None,
                )
                for item in bundle.artifacts
            ),
            checks=bundle.checks,
            runtime_address=bundle.runtime_address,
            domain_count=bundle.domain_count,
            stage_count=bundle.stage_count,
            warning_count=bundle.warning_count,
            content_address=bundle.content_address,
        )
    return bundle


__all__ = [
    "PROGRAM_RUNTIME_OFFLINE_CSV_MEDIA_TYPE",
    "PROGRAM_RUNTIME_OFFLINE_FORBIDDEN_KEYS",
    "PROGRAM_RUNTIME_OFFLINE_JSON_MEDIA_TYPE",
    "PROGRAM_RUNTIME_OFFLINE_MARKDOWN_MEDIA_TYPE",
    "build_program_runtime_offline_bundle",
    "load_program_runtime_offline_bundle",
    "program_runtime_offline_payloads",
    "public_program_projection",
    "write_program_runtime_offline_bundle",
]
