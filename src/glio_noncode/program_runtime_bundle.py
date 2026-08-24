"""Build, write, and verify a portable offline release for the program runtime."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .module_fabric_support import contains_private_key
from .program_runtime import architecture_program_domain_matrix
from .program_runtime_contracts import ProgramRuntime
from .program_runtime_execution import run_program_runtime
from .program_runtime_exports import (
    architecture_program_checks_csv,
    architecture_program_domains_csv,
    architecture_program_receipts_csv,
    architecture_program_report_json,
    architecture_program_report_markdown,
    architecture_program_runtime_json,
    architecture_program_summary_json,
)
from .program_runtime_release_contracts import (
    ProgramArtifactKind,
    ProgramRelease,
    ProgramReleaseArtifact,
    ProgramReleaseCheck,
    ProgramReleaseCheckCategory,
    ProgramReleaseManifest,
    ProgramReleaseState,
    ProgramReleaseVerification,
    addressed,
)
from .program_runtime_replay import (
    ProgramRuntimeFailureReport,
    ProgramRuntimeReplayReport,
    replay_architecture_program,
    run_program_runtime_failure_injections,
)
from .serialization import hash_bytes

PROGRAM_RELEASE_ARTIFACT_COUNT = 11
PROGRAM_RELEASE_CHECK_COUNT = 18
PROGRAM_RELEASE_MANIFEST_FILENAME = "program-release-manifest.json"
PROGRAM_RELEASE_DESCRIPTOR_FILENAME = "program-release.json"


_ARTIFACT_DEFINITIONS = (
    ("program-runtime", ProgramArtifactKind.RUNTIME, "program-runtime.json", "application/json"),
    ("program-report", ProgramArtifactKind.REPORT, "program-report.json", "application/json"),
    ("program-summary", ProgramArtifactKind.SUMMARY, "program-summary.json", "application/json"),
    ("program-receipts", ProgramArtifactKind.RECEIPTS, "program-receipts.csv", "text/csv"),
    ("program-checks", ProgramArtifactKind.CHECKS, "program-checks.csv", "text/csv"),
    ("program-domains", ProgramArtifactKind.DOMAINS, "program-domains.csv", "text/csv"),
    ("program-report-markdown", ProgramArtifactKind.MARKDOWN, "program-report.md", "text/markdown"),
    ("program-replay", ProgramArtifactKind.REPLAY, "program-replay.json", "application/json"),
    ("program-failures", ProgramArtifactKind.FAILURE_CONTROLS, "program-failures.json", "application/json"),
    ("program-specifications", ProgramArtifactKind.SPECIFICATIONS, "program-specifications.json", "application/json"),
    ("program-matrix", ProgramArtifactKind.MATRIX, "program-matrix.json", "application/json"),
)


def _json_text(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def program_release_payloads(
    runtime: ProgramRuntime,
    *,
    replay: ProgramRuntimeReplayReport | None = None,
    failure_controls: ProgramRuntimeFailureReport | None = None,
) -> dict[str, str]:
    """Return the complete deterministic filename-to-content release map."""

    selected_replay = replay or replay_architecture_program()
    selected_failures = failure_controls or run_program_runtime_failure_injections()
    report = runtime.report
    values = {
        "program-runtime.json": architecture_program_runtime_json(runtime),
        "program-report.json": architecture_program_report_json(report),
        "program-summary.json": architecture_program_summary_json(report),
        "program-receipts.csv": architecture_program_receipts_csv(report),
        "program-checks.csv": architecture_program_checks_csv(report),
        "program-domains.csv": architecture_program_domains_csv(report),
        "program-report.md": architecture_program_report_markdown(report),
        "program-replay.json": _json_text(selected_replay.to_dict()),
        "program-failures.json": _json_text(selected_failures.to_dict()),
        "program-specifications.json": _json_text([item.to_dict() for item in report.specs]),
        "program-matrix.json": _json_text(list(architecture_program_domain_matrix(report))),
    }
    return values


def _artifact(
    artifact_id: str,
    kind: ProgramArtifactKind,
    filename: str,
    media_type: str,
    text: str,
) -> ProgramReleaseArtifact:
    data = text.encode("utf-8")
    return ProgramReleaseArtifact(
        artifact_id=artifact_id,
        kind=kind,
        filename=filename,
        media_type=media_type,
        content_address=hash_bytes(data),
        byte_count=len(data),
        line_count=text.count("\n"),
        required=True,
        public_aggregate=True,
    )


def _check(
    check_id: str,
    category: ProgramReleaseCheckCategory,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ProgramReleaseCheck:
    body = {
        "check_id": check_id,
        "category": category,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return ProgramReleaseCheck(
        **body,
        content_address=addressed(body, "architecture-program-release-check"),
    )


def _json_payloads_are_public(payloads: dict[str, str]) -> bool:
    for filename, text in payloads.items():
        if not filename.endswith(".json"):
            continue
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            return False
        if contains_private_key(value):
            return False
    return True


def build_program_release(
    runtime: ProgramRuntime | None = None,
    *,
    release_id: str = "architecture-program-release-001",
    replay: ProgramRuntimeReplayReport | None = None,
    failure_controls: ProgramRuntimeFailureReport | None = None,
) -> ProgramRelease:
    """Build a publication-gated release descriptor over all runtime projections."""

    selected_runtime = runtime or run_program_runtime()
    selected_replay = replay or replay_architecture_program()
    selected_failures = failure_controls or run_program_runtime_failure_injections()
    payloads = program_release_payloads(
        selected_runtime,
        replay=selected_replay,
        failure_controls=selected_failures,
    )
    artifacts = tuple(
        _artifact(artifact_id, kind, filename, media_type, payloads[filename])
        for artifact_id, kind, filename, media_type in _ARTIFACT_DEFINITIONS
    )
    artifact_ids = tuple(item.artifact_id for item in artifacts)
    filenames = tuple(item.filename for item in artifacts)
    checks = (
        _check(
            "runtime-accepted",
            ProgramReleaseCheckCategory.RUNTIME,
            selected_runtime.accepted,
            selected_runtime.state.value,
            "accepted",
            "the release is sourced from an accepted program runtime",
        ),
        _check(
            "runtime-addressed",
            ProgramReleaseCheckCategory.INTEGRITY,
            ":" in selected_runtime.content_address,
            selected_runtime.content_address,
            "content address",
            "the source runtime is content-addressed",
        ),
        _check(
            "artifact-denominator",
            ProgramReleaseCheckCategory.INVENTORY,
            len(artifacts) == PROGRAM_RELEASE_ARTIFACT_COUNT,
            len(artifacts),
            PROGRAM_RELEASE_ARTIFACT_COUNT,
            "the release contains every required projection",
        ),
        _check(
            "artifact-identities",
            ProgramReleaseCheckCategory.INVENTORY,
            len(artifact_ids) == len(set(artifact_ids)),
            len(artifact_ids),
            len(set(artifact_ids)),
            "artifact identifiers are unique",
        ),
        _check(
            "filename-identities",
            ProgramReleaseCheckCategory.INVENTORY,
            len(filenames) == len(set(filenames)),
            len(filenames),
            len(set(filenames)),
            "artifact filenames are unique",
        ),
        _check(
            "required-artifacts",
            ProgramReleaseCheckCategory.INVENTORY,
            all(item.required for item in artifacts),
            sum(item.required for item in artifacts),
            len(artifacts),
            "every release projection is required for offline review",
        ),
        _check(
            "public-artifacts",
            ProgramReleaseCheckCategory.PUBLIC_BOUNDARY,
            all(item.public_aggregate for item in artifacts),
            sum(item.public_aggregate for item in artifacts),
            len(artifacts),
            "every release projection is marked public aggregate",
        ),
        _check(
            "artifact-addresses",
            ProgramReleaseCheckCategory.INTEGRITY,
            all(":" in item.content_address for item in artifacts),
            sum(":" in item.content_address for item in artifacts),
            len(artifacts),
            "every artifact has a byte-content address",
        ),
        _check(
            "artifact-byte-counts",
            ProgramReleaseCheckCategory.INTEGRITY,
            all(item.byte_count > 0 for item in artifacts),
            min(item.byte_count for item in artifacts),
            ">0",
            "every artifact has non-empty UTF-8 content",
        ),
        _check(
            "artifact-line-counts",
            ProgramReleaseCheckCategory.INTEGRITY,
            all(item.line_count > 0 for item in artifacts),
            min(item.line_count for item in artifacts),
            ">0",
            "every artifact has observable line cardinality",
        ),
        _check(
            "runtime-projection",
            ProgramReleaseCheckCategory.INVENTORY,
            "program-runtime.json" in payloads,
            "program-runtime.json" in payloads,
            True,
            "the complete runtime projection is present",
        ),
        _check(
            "report-projection",
            ProgramReleaseCheckCategory.INVENTORY,
            "program-report.json" in payloads,
            "program-report.json" in payloads,
            True,
            "the complete normalized report is present",
        ),
        _check(
            "summary-projection",
            ProgramReleaseCheckCategory.INVENTORY,
            "program-summary.json" in payloads,
            "program-summary.json" in payloads,
            True,
            "the compact summary projection is present",
        ),
        _check(
            "check-cardinality",
            ProgramReleaseCheckCategory.INTEGRITY,
            payloads["program-checks.csv"].count("\n") == 173,
            payloads["program-checks.csv"].count("\n") - 1,
            172,
            "the checks export retains all 172 checks",
        ),
        _check(
            "receipt-cardinality",
            ProgramReleaseCheckCategory.INTEGRITY,
            payloads["program-receipts.csv"].count("\n") == 17,
            payloads["program-receipts.csv"].count("\n") - 1,
            16,
            "the receipts export retains all sixteen domains",
        ),
        _check(
            "replay-accepted",
            ProgramReleaseCheckCategory.REPLAY,
            selected_replay.accepted,
            selected_replay.to_dict(),
            True,
            "deterministic replay closes before publication",
        ),
        _check(
            "failure-controls-accepted",
            ProgramReleaseCheckCategory.FAILURE_CONTROL,
            selected_failures.accepted,
            selected_failures.to_dict(),
            True,
            "missing-reference controls remain visible and pass their assertions",
        ),
        _check(
            "json-public-boundary",
            ProgramReleaseCheckCategory.PUBLIC_BOUNDARY,
            _json_payloads_are_public(payloads),
            True,
            True,
            "JSON release projections contain no private subject keys",
        ),
    )
    state = ProgramReleaseState.PUBLISHED if all(item.passed for item in checks) else ProgramReleaseState.REVIEW
    manifest_body = {
        "release_id": release_id,
        "runtime_address": selected_runtime.content_address,
        "report_address": selected_runtime.report.content_address,
        "artifact_count": len(artifacts),
        "artifact_ids": artifact_ids,
        "artifact_filenames": filenames,
        "state": state,
    }
    manifest = ProgramReleaseManifest(
        **manifest_body,
        content_address=addressed(manifest_body, "architecture-program-manifest"),
    )
    body = {
        "release_id": release_id,
        "runtime_address": selected_runtime.content_address,
        "report_address": selected_runtime.report.content_address,
        "manifest": manifest,
        "artifacts": artifacts,
        "checks": checks,
        "state": state,
    }
    return ProgramRelease(
        **body,
        content_address=addressed(body, "architecture-program-release"),
    )


def program_release_manifest_json(release: ProgramRelease) -> str:
    """Serialize the portable reopen manifest."""

    return _json_text(release.manifest.to_dict())


def program_release_json(release: ProgramRelease) -> str:
    """Serialize the release descriptor and all inventory checks."""

    return _json_text(release.to_dict())


def _manifest_body(manifest: ProgramReleaseManifest) -> dict[str, Any]:
    return {
        "release_id": manifest.release_id,
        "runtime_address": manifest.runtime_address,
        "report_address": manifest.report_address,
        "artifact_count": manifest.artifact_count,
        "artifact_ids": manifest.artifact_ids,
        "artifact_filenames": manifest.artifact_filenames,
        "state": manifest.state,
    }


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def write_program_release(
    output_dir: str | Path,
    runtime: ProgramRuntime | None = None,
    *,
    release: ProgramRelease | None = None,
) -> ProgramRelease:
    """Write a release directory and its self-describing manifest."""

    selected_runtime = runtime
    replay: ProgramRuntimeReplayReport | None = None
    failure_controls: ProgramRuntimeFailureReport | None = None
    if release is None:
        selected_runtime = selected_runtime or run_program_runtime()
        replay = replay_architecture_program()
        failure_controls = run_program_runtime_failure_injections()
        selected_release = build_program_release(
            selected_runtime,
            replay=replay,
            failure_controls=failure_controls,
        )
    else:
        selected_release = release
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    source_runtime = selected_release_runtime(selected_release, selected_runtime)
    payloads = program_release_payloads(
        source_runtime,
        replay=replay,
        failure_controls=failure_controls,
    )
    for artifact in selected_release.artifacts:
        target = root / artifact.filename
        if target.parent != root:
            raise ValueError("release artifact path escapes the selected output directory")
        _write_text(target, payloads[artifact.filename])
    _write_text(root / PROGRAM_RELEASE_MANIFEST_FILENAME, program_release_manifest_json(selected_release))
    _write_text(root / PROGRAM_RELEASE_DESCRIPTOR_FILENAME, program_release_json(selected_release))
    return selected_release


def selected_release_runtime(release: ProgramRelease, runtime: ProgramRuntime | None) -> ProgramRuntime:
    """Require the source runtime when a caller supplies a detached release."""

    if runtime is None:
        raise ValueError("writing a detached release requires its source runtime")
    if runtime.content_address != release.runtime_address:
        raise ValueError("release runtime does not match the supplied runtime")
    return runtime


def load_program_release_manifest(output_dir: str | Path) -> ProgramReleaseManifest:
    """Load only the portable manifest from a release directory."""

    root = Path(output_dir)
    value = json.loads((root / PROGRAM_RELEASE_MANIFEST_FILENAME).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("program release manifest must be an object")
    return ProgramReleaseManifest.from_mapping(value)


def _artifact_from_mapping(value: dict[str, Any]) -> ProgramReleaseArtifact:
    return ProgramReleaseArtifact(
        artifact_id=str(value["artifact_id"]),
        kind=ProgramArtifactKind(value["kind"]),
        filename=str(value["filename"]),
        media_type=str(value["media_type"]),
        content_address=str(value["content_address"]),
        byte_count=int(value["byte_count"]),
        line_count=int(value["line_count"]),
        required=bool(value["required"]),
        public_aggregate=bool(value["public_aggregate"]),
    )


def _loaded_inventory(root: Path) -> tuple[ProgramReleaseManifest, tuple[ProgramReleaseArtifact, ...]]:
    descriptor = json.loads((root / PROGRAM_RELEASE_DESCRIPTOR_FILENAME).read_text(encoding="utf-8"))
    if not isinstance(descriptor, dict) or not isinstance(descriptor.get("manifest"), dict):
        raise ValueError("program release descriptor is malformed")
    manifest = ProgramReleaseManifest.from_mapping(descriptor["manifest"])
    artifacts = tuple(_artifact_from_mapping(item) for item in descriptor.get("artifacts", ()))
    return manifest, artifacts


def verify_program_release(
    output_dir: str | Path,
    *,
    release: ProgramRelease | None = None,
) -> ProgramReleaseVerification:
    """Reopen a release directory and verify every inventory byte and boundary."""

    root = Path(output_dir)
    checks: list[ProgramReleaseCheck] = []

    def add(
        check_id: str,
        category: ProgramReleaseCheckCategory,
        passed: bool,
        observed: Any,
        required: Any,
        detail: str,
    ) -> None:
        checks.append(_check(check_id, category, passed, observed, required, detail))

    try:
        manifest, artifacts = (
            (release.manifest, release.artifacts)
            if release is not None
            else _loaded_inventory(root)
        )
        descriptor_ok = True
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        manifest = None
        artifacts = ()
        descriptor_ok = False
        add(
            "descriptor-readable",
            ProgramReleaseCheckCategory.PORTABILITY,
            False,
            f"{type(exc).__name__}: {exc}",
            "valid release descriptor",
            "the release descriptor and manifest can be reopened",
        )
    if manifest is not None:
        add(
            "descriptor-readable",
            ProgramReleaseCheckCategory.PORTABILITY,
            descriptor_ok,
            manifest.release_id,
            "valid release descriptor",
            "the release descriptor and manifest can be reopened",
        )
        manifest_path = root / PROGRAM_RELEASE_MANIFEST_FILENAME
        if manifest_path.exists():
            loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
            try:
                loaded_manifest = (
                    ProgramReleaseManifest.from_mapping(loaded)
                    if isinstance(loaded, dict)
                    else None
                )
            except (KeyError, TypeError, ValueError):
                loaded_manifest = None
            add(
                "manifest-address",
                ProgramReleaseCheckCategory.INTEGRITY,
                isinstance(loaded, dict)
                and str(loaded.get("content_address", "")) == manifest.content_address,
                loaded.get("content_address", "") if isinstance(loaded, dict) else "",
                manifest.content_address,
                "the on-disk manifest retains its addressed identity",
            )
            add(
                "manifest-self-address",
                ProgramReleaseCheckCategory.INTEGRITY,
                loaded_manifest is not None
                and addressed(_manifest_body(loaded_manifest), "architecture-program-manifest")
                == loaded_manifest.content_address,
                addressed(_manifest_body(loaded_manifest), "architecture-program-manifest")
                if loaded_manifest is not None
                else "",
                loaded_manifest.content_address if loaded_manifest is not None else "",
                "the manifest address matches its own canonical fields",
            )
        else:
            add(
                "manifest-present",
                ProgramReleaseCheckCategory.PORTABILITY,
                False,
                False,
                True,
                "the release manifest is present",
            )
        add(
            "artifact-denominator",
            ProgramReleaseCheckCategory.INVENTORY,
            len(artifacts) == manifest.artifact_count,
            len(artifacts),
            manifest.artifact_count,
            "descriptor and manifest conserve artifact cardinality",
        )
        for artifact in artifacts:
            safe_name = Path(artifact.filename).name == artifact.filename and ".." not in Path(
                artifact.filename
            ).parts
            path = root / artifact.filename
            present = safe_name and path.exists() and path.is_file()
            add(
                f"{artifact.artifact_id}:present",
                ProgramReleaseCheckCategory.PORTABILITY,
                present,
                str(path) if present else "missing",
                artifact.filename,
                "the required artifact is present inside the release root",
            )
            if not present:
                continue
            data = path.read_bytes()
            text = data.decode("utf-8")
            add(
                f"{artifact.artifact_id}:hash",
                ProgramReleaseCheckCategory.INTEGRITY,
                hash_bytes(data) == artifact.content_address,
                hash_bytes(data),
                artifact.content_address,
                "artifact bytes match the manifest address",
            )
            add(
                f"{artifact.artifact_id}:bytes",
                ProgramReleaseCheckCategory.INTEGRITY,
                len(data) == artifact.byte_count,
                len(data),
                artifact.byte_count,
                "artifact byte cardinality matches the inventory",
            )
            add(
                f"{artifact.artifact_id}:lines",
                ProgramReleaseCheckCategory.INTEGRITY,
                text.count("\n") == artifact.line_count,
                text.count("\n"),
                artifact.line_count,
                "artifact line cardinality matches the inventory",
            )
            if artifact.filename.endswith(".json"):
                try:
                    value = json.loads(text)
                    public = not contains_private_key(value)
                except (UnicodeDecodeError, json.JSONDecodeError):
                    public = False
                add(
                    f"{artifact.artifact_id}:public",
                    ProgramReleaseCheckCategory.PUBLIC_BOUNDARY,
                    public,
                    public,
                    True,
                    "JSON artifact contains no private subject keys",
                )
    accepted = bool(checks) and all(item.passed for item in checks)
    body = {
        "root": str(root),
        "manifest_address": manifest.content_address if manifest is not None else "",
        "checks": tuple(checks),
        "accepted": accepted,
    }
    return ProgramReleaseVerification(
        **body,
        content_address=addressed(body, "architecture-program-verification"),
    )


__all__ = [
    "PROGRAM_RELEASE_ARTIFACT_COUNT",
    "PROGRAM_RELEASE_CHECK_COUNT",
    "PROGRAM_RELEASE_DESCRIPTOR_FILENAME",
    "PROGRAM_RELEASE_MANIFEST_FILENAME",
    "build_program_release",
    "load_program_release_manifest",
    "program_release_json",
    "program_release_manifest_json",
    "program_release_payloads",
    "selected_release_runtime",
    "verify_program_release",
    "write_program_release",
]
