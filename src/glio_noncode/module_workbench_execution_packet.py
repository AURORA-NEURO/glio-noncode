"""Build, persist, verify, and load exact-byte execution handoff packets."""

from __future__ import annotations

import csv
import io
import json
import os
import tempfile
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_workbench_contracts import ModuleWorkbenchReport
from .module_workbench_execution import (
    apply_module_workbench_execution_commands,
    build_module_workbench_execution,
    module_workbench_execution_csv,
    module_workbench_execution_json,
)
from .module_workbench_execution_audit import (
    audit_module_workbench_execution,
    module_workbench_execution_audit_json,
)
from .module_workbench_execution_contracts import (
    ModuleWorkbenchExecutionCommand,
    ModuleWorkbenchExecutionLedger,
)
from .module_workbench_execution_packet_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARTIFACT_COUNT,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARTIFACT_PREFIX,
    MODULE_WORKBENCH_EXECUTION_PACKET_BOUNDARY,
    MODULE_WORKBENCH_EXECUTION_PACKET_CHECK_PREFIX,
    MODULE_WORKBENCH_EXECUTION_PACKET_MANIFEST,
    MODULE_WORKBENCH_EXECUTION_PACKET_MAX_ARTIFACTS,
    MODULE_WORKBENCH_EXECUTION_PACKET_MAX_CHECKS,
    MODULE_WORKBENCH_EXECUTION_PACKET_VERSION,
    ModuleWorkbenchExecutionPacket,
    ModuleWorkbenchExecutionPacketArtifact,
    ModuleWorkbenchExecutionPacketArtifactKind,
    ModuleWorkbenchExecutionPacketCheck,
    ModuleWorkbenchExecutionPacketCheckPlane,
    ModuleWorkbenchExecutionPacketState,
    ModuleWorkbenchExecutionPacketVerification,
    address_module_workbench_execution_packet,
    address_module_workbench_execution_packet_verification,
)
from .module_workbench_execution_policy import (
    default_module_workbench_execution_policy,
    evaluate_module_workbench_execution_policy,
)
from .module_workbench_execution_policy_contracts import (
    ModuleWorkbenchExecutionPolicy,
    ModuleWorkbenchExecutionPolicyGate,
)
from .module_workbench_execution_review import (
    build_module_workbench_execution_review,
    module_workbench_execution_review_json,
)
from .module_workbench_execution_review_contracts import ModuleWorkbenchExecutionReview
from .module_workbench_execution_runtime import (
    module_workbench_execution_runtime_json,
    run_module_workbench_execution,
)
from .module_workbench_execution_runtime_contracts import ModuleWorkbenchExecutionRuntime
from .module_workbench_portfolio import (
    build_module_workbench_portfolio,
    module_workbench_portfolio_json,
)
from .module_workbench_portfolio_contracts import ModuleWorkbenchPortfolio
from .run_workspace import _has_forbidden_key
from .serialization import canonical_json, content_hash, hash_bytes

_JSON = "application/json"
_CSV = "text/csv"
_UTF8 = "utf-8"
_PACKET_PREFIX = "module-workbench-execution-packet"


def _safe_path(value: str) -> bool:
    if not isinstance(value, str) or not value or "\\" in value or value.startswith("/"):
        return False
    parts = tuple(value.split("/"))
    return bool(parts) and all(part not in {"", ".", ".."} for part in parts)


def _atomic_write(path: Path, payload: bytes) -> None:
    """Replace one packet file only after the complete bytes are durable."""

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _public_json(value: Any) -> str:
    projected = value.to_dict() if hasattr(value, "to_dict") else value
    if _has_forbidden_key(projected):
        raise ValidationError("execution packet crosses the public boundary")
    return canonical_json(projected) + "\n"


def _artifact(
    artifact_id: str,
    relative_path: str,
    kind: ModuleWorkbenchExecutionPacketArtifactKind,
    media_type: str,
    payload: str,
) -> ModuleWorkbenchExecutionPacketArtifact:
    if not _safe_path(relative_path):
        raise ValidationError(f"unsafe execution packet path: {relative_path}")
    encoded = payload.encode(_UTF8)
    body = {
        "artifact_id": artifact_id,
        "relative_path": relative_path,
        "media_type": media_type,
        "kind": kind,
        "byte_count": len(encoded),
        "line_count": len(payload.splitlines()),
        "content_address": hash_bytes(
            encoded, prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARTIFACT_PREFIX
        ),
    }
    return ModuleWorkbenchExecutionPacketArtifact(**body, payload=payload)


def _check(
    check_id: str,
    plane: ModuleWorkbenchExecutionPacketCheckPlane,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ModuleWorkbenchExecutionPacketCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return ModuleWorkbenchExecutionPacketCheck(
        **body,
        content_address=content_hash(body, prefix=MODULE_WORKBENCH_EXECUTION_PACKET_CHECK_PREFIX),
    )


def _packet_address(
    packet_id: str,
    report_address: str,
    portfolio_address: str,
    initial_ledger_address: str,
    ledger_address: str,
    review_address: str,
    audit_address: str,
    policy_address: str,
    gate_address: str,
    runtime_address: str,
    state: ModuleWorkbenchExecutionPacketState,
    accepted: bool,
    artifacts: tuple[ModuleWorkbenchExecutionPacketArtifact, ...],
    checks: tuple[ModuleWorkbenchExecutionPacketCheck, ...],
) -> str:
    body = {
        "packet_id": packet_id,
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_BOUNDARY,
        "report_address": report_address,
        "portfolio_address": portfolio_address,
        "initial_ledger_address": initial_ledger_address,
        "ledger_address": ledger_address,
        "review_address": review_address,
        "audit_address": audit_address,
        "policy_address": policy_address,
        "gate_address": gate_address,
        "runtime_address": runtime_address,
        "state": state,
        "accepted": accepted,
        "artifact_count": len(artifacts),
        "artifacts": [item.to_dict() for item in artifacts],
        "checks": [item.to_dict() for item in checks],
        "passed_check_count": sum(item.passed for item in checks),
        "failed_check_count": sum(not item.passed for item in checks),
    }
    return content_hash(body, prefix=_PACKET_PREFIX)


def _packet_summary(report: ModuleWorkbenchReport) -> str:
    return _public_json(report.to_dict(include_rows=False))


def _blockers_csv(value: ModuleWorkbenchExecutionLedger) -> str:
    fields = (
        "task_id",
        "module_id",
        "family",
        "kind",
        "state",
        "blockers",
        "detail",
        "content_address",
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for item in value.items:
        if not item.blockers:
            continue
        row = item.to_dict()
        row["blockers"] = ";".join(item.blockers)
        writer.writerow(row)
    return output.getvalue()


def _capability_payload() -> str:
    return _public_json(module_workbench_execution_packet_capabilities())


def _schema_payload() -> str:
    return _public_json(module_workbench_execution_packet_schema())


def _artifact_specs(
    report: ModuleWorkbenchReport,
    portfolio: ModuleWorkbenchPortfolio,
    initial: ModuleWorkbenchExecutionLedger,
    current: ModuleWorkbenchExecutionLedger,
    review: ModuleWorkbenchExecutionReview,
    audit: Any,
    policy: ModuleWorkbenchExecutionPolicy,
    gate: ModuleWorkbenchExecutionPolicyGate,
    runtime: ModuleWorkbenchExecutionRuntime,
) -> tuple[ModuleWorkbenchExecutionPacketArtifact, ...]:
    artifacts = (
        _artifact(
            "audit",
            "audit.json",
            ModuleWorkbenchExecutionPacketArtifactKind.AUDIT,
            _JSON,
            module_workbench_execution_audit_json(audit),
        ),
        _artifact(
            "blockers",
            "blockers.csv",
            ModuleWorkbenchExecutionPacketArtifactKind.BLOCKERS,
            _CSV,
            _blockers_csv(current),
        ),
        _artifact(
            "capabilities",
            "capabilities.json",
            ModuleWorkbenchExecutionPacketArtifactKind.CAPABILITIES,
            _JSON,
            _capability_payload(),
        ),
        _artifact(
            "events",
            "events.csv",
            ModuleWorkbenchExecutionPacketArtifactKind.EVENTS,
            _CSV,
            module_workbench_execution_csv(current, "events"),
        ),
        _artifact(
            "initial-ledger",
            "initial-ledger.json",
            ModuleWorkbenchExecutionPacketArtifactKind.INITIAL_LEDGER,
            _JSON,
            module_workbench_execution_json(initial),
        ),
        _artifact(
            "items",
            "items.csv",
            ModuleWorkbenchExecutionPacketArtifactKind.ITEMS,
            _CSV,
            module_workbench_execution_csv(current, "items"),
        ),
        _artifact(
            "ledger",
            "ledger.json",
            ModuleWorkbenchExecutionPacketArtifactKind.LEDGER,
            _JSON,
            module_workbench_execution_json(current),
        ),
        _artifact(
            "policy",
            "policy.json",
            ModuleWorkbenchExecutionPacketArtifactKind.POLICY,
            _JSON,
            _public_json({"policy": policy.to_dict(), "gate": gate.to_dict()}),
        ),
        _artifact(
            "portfolio",
            "portfolio.json",
            ModuleWorkbenchExecutionPacketArtifactKind.PORTFOLIO,
            _JSON,
            module_workbench_portfolio_json(portfolio),
        ),
        _artifact(
            "review",
            "review.json",
            ModuleWorkbenchExecutionPacketArtifactKind.REVIEW,
            _JSON,
            module_workbench_execution_review_json(review),
        ),
        _artifact(
            "runtime",
            "runtime.json",
            ModuleWorkbenchExecutionPacketArtifactKind.RUNTIME,
            _JSON,
            module_workbench_execution_runtime_json(runtime),
        ),
        _artifact(
            "schema",
            "schema.json",
            ModuleWorkbenchExecutionPacketArtifactKind.SCHEMA,
            _JSON,
            _schema_payload(),
        ),
        _artifact(
            "workbench-summary",
            "workbench-summary.json",
            ModuleWorkbenchExecutionPacketArtifactKind.WORKBENCH_SUMMARY,
            _JSON,
            _packet_summary(report),
        ),
    )
    return tuple(sorted(artifacts, key=lambda item: item.artifact_id))


def _link_checks(
    report: ModuleWorkbenchReport,
    portfolio: ModuleWorkbenchPortfolio,
    initial: ModuleWorkbenchExecutionLedger,
    current: ModuleWorkbenchExecutionLedger,
    review: ModuleWorkbenchExecutionReview,
    audit: Any,
    policy: ModuleWorkbenchExecutionPolicy,
    gate: ModuleWorkbenchExecutionPolicyGate,
    runtime: ModuleWorkbenchExecutionRuntime,
) -> tuple[ModuleWorkbenchExecutionPacketCheck, ...]:
    checks = (
        _check(
            "report-link",
            ModuleWorkbenchExecutionPacketCheckPlane.LINKAGE,
            report.accepted and runtime.report_address == report.content_address,
            runtime.report_address,
            report.content_address,
            "runtime points to the packaged workbench report",
        ),
        _check(
            "portfolio-link",
            ModuleWorkbenchExecutionPacketCheckPlane.LINKAGE,
            runtime.portfolio_address == portfolio.content_address,
            runtime.portfolio_address,
            portfolio.content_address,
            "runtime points to the packaged portfolio",
        ),
        _check(
            "initial-ledger-link",
            ModuleWorkbenchExecutionPacketCheckPlane.LINKAGE,
            runtime.initial_ledger_address == initial.content_address,
            runtime.initial_ledger_address,
            initial.content_address,
            "runtime retains the initial plan address",
        ),
        _check(
            "ledger-link",
            ModuleWorkbenchExecutionPacketCheckPlane.LINKAGE,
            runtime.ledger_address == current.content_address,
            runtime.ledger_address,
            current.content_address,
            "runtime retains the post-replay ledger address",
        ),
        _check(
            "review-link",
            ModuleWorkbenchExecutionPacketCheckPlane.LINKAGE,
            review.ledger_address == current.content_address,
            review.ledger_address,
            current.content_address,
            "review projection uses the packaged ledger",
        ),
        _check(
            "audit-link",
            ModuleWorkbenchExecutionPacketCheckPlane.SEMANTIC,
            audit.ledger_address == current.content_address and audit.accepted,
            audit.ledger_address,
            current.content_address,
            "independent audit accepts the packaged ledger",
        ),
        _check(
            "policy-link",
            ModuleWorkbenchExecutionPacketCheckPlane.SEMANTIC,
            gate.ledger_address == current.content_address
            and gate.policy_address == policy.content_address,
            gate.ledger_address,
            current.content_address,
            "policy gate evaluates the packaged ledger",
        ),
        _check(
            "runtime-link",
            ModuleWorkbenchExecutionPacketCheckPlane.SEMANTIC,
            runtime.accepted == (report.accepted and portfolio.accepted and audit.accepted),
            runtime.accepted,
            report.accepted and portfolio.accepted and audit.accepted,
            "runtime acceptance conserves upstream acceptance",
        ),
    )
    return checks


def build_module_workbench_execution_packet(
    report: ModuleWorkbenchReport,
    portfolio: ModuleWorkbenchPortfolio | None = None,
    commands: Iterable[ModuleWorkbenchExecutionCommand] = (),
    policy: ModuleWorkbenchExecutionPolicy | None = None,
    *,
    packet_id: str = "glio-noncode-module-workbench-execution-packet",
) -> ModuleWorkbenchExecutionPacket:
    """Build a fixed, self-contained packet from one deterministic workbench run."""

    if not isinstance(report, ModuleWorkbenchReport):
        raise ValidationError("execution packet requires a typed workbench report")
    if not isinstance(packet_id, str) or not packet_id.strip():
        raise ValidationError("execution packet ID is required")
    selected_portfolio = portfolio or build_module_workbench_portfolio(report)
    if not isinstance(selected_portfolio, ModuleWorkbenchPortfolio):
        raise ValidationError("execution packet portfolio must be typed")
    selected_commands = tuple(commands)
    initial = build_module_workbench_execution(report, selected_portfolio)
    current = apply_module_workbench_execution_commands(initial, selected_commands)
    audit = audit_module_workbench_execution(current)
    selected_policy = policy or default_module_workbench_execution_policy()
    gate = evaluate_module_workbench_execution_policy(current, selected_policy, audit)
    runtime = run_module_workbench_execution(
        report,
        selected_portfolio,
        commands=selected_commands,
        policy=selected_policy,
    )
    review = build_module_workbench_execution_review(current)
    artifacts = _artifact_specs(
        report,
        selected_portfolio,
        initial,
        current,
        review,
        audit,
        selected_policy,
        gate,
        runtime,
    )
    checks = (
        _check(
            "artifact-count",
            ModuleWorkbenchExecutionPacketCheckPlane.MANIFEST,
            len(artifacts) == MODULE_WORKBENCH_EXECUTION_PACKET_ARTIFACT_COUNT,
            len(artifacts),
            MODULE_WORKBENCH_EXECUTION_PACKET_ARTIFACT_COUNT,
            "packet has the fixed artifact count",
        ),
        _check(
            "artifact-identities",
            ModuleWorkbenchExecutionPacketCheckPlane.MANIFEST,
            len({item.artifact_id for item in artifacts}) == len(artifacts),
            len({item.artifact_id for item in artifacts}),
            len(artifacts),
            "artifact identifiers are unique",
        ),
        _check(
            "artifact-paths",
            ModuleWorkbenchExecutionPacketCheckPlane.PATH,
            all(_safe_path(item.relative_path) for item in artifacts),
            "safe",
            "safe",
            "artifact paths are relative and traversal-free",
        ),
        _check(
            "artifact-byte-addresses",
            ModuleWorkbenchExecutionPacketCheckPlane.BYTES,
            all(
                item.payload is not None
                and hash_bytes(
                    item.payload.encode(_UTF8),
                    prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARTIFACT_PREFIX,
                )
                == item.content_address
                for item in artifacts
            ),
            "verified",
            "verified",
            "artifact addresses match exact UTF-8 bytes",
        ),
        *_link_checks(
            report,
            selected_portfolio,
            initial,
            current,
            review,
            audit,
            selected_policy,
            gate,
            runtime,
        ),
        _check(
            "public-boundary",
            ModuleWorkbenchExecutionPacketCheckPlane.PUBLIC,
            not _has_forbidden_key(
                {"artifacts": [item.to_dict(include_payload=True) for item in artifacts]}
            ),
            "clean",
            "clean",
            "packet artifacts contain only public aggregate fields",
        ),
        _check(
            "runtime-stage-order",
            ModuleWorkbenchExecutionPacketCheckPlane.REPLAY,
            tuple(item.kind.value for item in runtime.stages)
            == (
                "portfolio",
                "plan",
                "replay",
                "policy",
                "audit",
                "handoff",
            ),
            tuple(item.kind.value for item in runtime.stages),
            ("portfolio", "plan", "replay", "policy", "audit", "handoff"),
            "runtime stages retain the declared handoff order",
        ),
    )
    accepted = (
        report.accepted
        and selected_portfolio.accepted
        and current.accepted
        and review.accepted
        and audit.accepted
        and gate.accepted
        and runtime.accepted
        and all(item.passed for item in checks)
    )
    state = (
        ModuleWorkbenchExecutionPacketState.ACCEPTED
        if accepted
        else ModuleWorkbenchExecutionPacketState.BLOCKED
    )
    address = _packet_address(
        packet_id,
        report.content_address,
        selected_portfolio.content_address,
        initial.content_address,
        current.content_address,
        review.content_address,
        audit.content_address,
        selected_policy.content_address,
        gate.content_address,
        runtime.content_address,
        state,
        accepted,
        artifacts,
        checks,
    )
    return ModuleWorkbenchExecutionPacket(
        packet_id=packet_id,
        version=MODULE_WORKBENCH_EXECUTION_PACKET_VERSION,
        boundary=MODULE_WORKBENCH_EXECUTION_PACKET_BOUNDARY,
        report_address=report.content_address,
        portfolio_address=selected_portfolio.content_address,
        initial_ledger_address=initial.content_address,
        ledger_address=current.content_address,
        review_address=review.content_address,
        audit_address=audit.content_address,
        policy_address=selected_policy.content_address,
        gate_address=gate.content_address,
        runtime_address=runtime.content_address,
        state=state,
        accepted=accepted,
        artifacts=artifacts,
        checks=checks,
        content_address=address,
    )


def verify_module_workbench_execution_packet(
    directory: str | Path,
) -> ModuleWorkbenchExecutionPacketVerification:
    """Verify packet manifest, files, exact bytes, links, and public fields."""

    root = Path(directory)
    checks: list[ModuleWorkbenchExecutionPacketCheck] = []
    manifest: Mapping[str, Any] = {}
    try:
        raw = (root / MODULE_WORKBENCH_EXECUTION_PACKET_MANIFEST).read_text(encoding=_UTF8)
        loaded = json.loads(raw)
        if isinstance(loaded, Mapping):
            manifest = loaded
        else:
            raise ValueError("manifest must be an object")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        checks.append(
            _check(
                "manifest-readable",
                ModuleWorkbenchExecutionPacketCheckPlane.STORAGE,
                False,
                str(exc),
                "readable JSON object",
                "packet manifest could not be loaded",
            )
        )
        return _verification(str(manifest.get("packet_id", "unknown")), 0, 0, 0, checks)

    packet_id = str(manifest.get("packet_id", "unknown"))
    raw_artifacts = manifest.get("artifacts")
    artifact_rows = (
        tuple(row for row in raw_artifacts if isinstance(row, Mapping))
        if isinstance(raw_artifacts, list)
        else ()
    )
    checks.append(
        _check(
            "manifest-shape",
            ModuleWorkbenchExecutionPacketCheckPlane.MANIFEST,
            isinstance(raw_artifacts, list),
            type(raw_artifacts).__name__,
            "list",
            "manifest artifact collection is an array",
        )
    )
    checks.append(
        _check(
            "manifest-version-boundary",
            ModuleWorkbenchExecutionPacketCheckPlane.MANIFEST,
            manifest.get("version") == MODULE_WORKBENCH_EXECUTION_PACKET_VERSION
            and manifest.get("boundary") == MODULE_WORKBENCH_EXECUTION_PACKET_BOUNDARY,
            {"version": manifest.get("version"), "boundary": manifest.get("boundary")},
            {
                "version": MODULE_WORKBENCH_EXECUTION_PACKET_VERSION,
                "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_BOUNDARY,
            },
            "manifest version and public boundary are recognized",
        )
    )
    paths = tuple(str(row.get("relative_path", "")) for row in artifact_rows)
    ids = tuple(str(row.get("artifact_id", "")) for row in artifact_rows)
    checks.append(
        _check(
            "safe-paths",
            ModuleWorkbenchExecutionPacketCheckPlane.PATH,
            all(_safe_path(path) for path in paths),
            "safe" if all(_safe_path(path) for path in paths) else "unsafe",
            "safe",
            "manifest paths are relative and traversal-free",
        )
    )
    checks.append(
        _check(
            "artifact-count",
            ModuleWorkbenchExecutionPacketCheckPlane.MANIFEST,
            len(artifact_rows) == MODULE_WORKBENCH_EXECUTION_PACKET_ARTIFACT_COUNT,
            len(artifact_rows),
            MODULE_WORKBENCH_EXECUTION_PACKET_ARTIFACT_COUNT,
            "manifest has the fixed artifact count",
        )
    )
    checks.append(
        _check(
            "unique-artifacts",
            ModuleWorkbenchExecutionPacketCheckPlane.MANIFEST,
            len(set(ids)) == len(ids)
            and len(set(paths)) == len(paths)
            and tuple(sorted(ids)) == ids
            and tuple(sorted(paths)) == paths,
            {"ids": len(set(ids)), "paths": len(set(paths))},
            {"ids": len(ids), "paths": len(paths), "sorted": True},
            "artifact identifiers and paths are unique and sorted",
        )
    )
    present = 0
    missing = 0
    payloads: dict[str, str] = {}
    for row in artifact_rows:
        artifact_id = str(row.get("artifact_id", ""))
        path_value = str(row.get("relative_path", ""))
        path = root.joinpath(*path_value.split("/")) if _safe_path(path_value) else root
        try:
            payload = path.read_text(encoding=_UTF8)
            present += 1
            payloads[artifact_id] = payload
        except (OSError, UnicodeDecodeError):
            missing += 1
    checks.append(
        _check(
            "artifact-presence",
            ModuleWorkbenchExecutionPacketCheckPlane.STORAGE,
            missing == 0,
            {"present": present, "missing": missing},
            {"missing": 0},
            "every manifest artifact is present and UTF-8 readable",
        )
    )
    byte_failures: list[str] = []
    line_failures: list[str] = []
    descriptor_failures: list[str] = []
    for row in artifact_rows:
        artifact_id = str(row.get("artifact_id", ""))
        payload = payloads.get(artifact_id)
        if payload is None:
            continue
        encoded = payload.encode(_UTF8)
        if hash_bytes(encoded, prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARTIFACT_PREFIX) != row.get(
            "content_address"
        ):
            byte_failures.append(artifact_id)
        if len(encoded) != row.get("byte_count"):
            byte_failures.append(f"{artifact_id}:byte_count")
        if len(payload.splitlines()) != row.get("line_count"):
            line_failures.append(artifact_id)
        try:
            kind = ModuleWorkbenchExecutionPacketArtifactKind(str(row.get("kind")))
            ModuleWorkbenchExecutionPacketArtifact(
                artifact_id=artifact_id,
                relative_path=str(row.get("relative_path")),
                media_type=str(row.get("media_type")),
                kind=kind,
                byte_count=int(row.get("byte_count")),
                line_count=int(row.get("line_count")),
                content_address=str(row.get("content_address")),
            )
        except (TypeError, ValueError, ValidationError):
            descriptor_failures.append(artifact_id)
    checks.append(
        _check(
            "artifact-byte-addresses",
            ModuleWorkbenchExecutionPacketCheckPlane.BYTES,
            not byte_failures and not line_failures and not descriptor_failures,
            {
                "byte_failures": tuple(sorted(byte_failures)),
                "line_failures": tuple(sorted(line_failures)),
                "descriptor_failures": tuple(sorted(descriptor_failures)),
            },
            "empty failure lists",
            "artifact bytes, line counts, and descriptors match the manifest",
        )
    )
    expected_files = {MODULE_WORKBENCH_EXECUTION_PACKET_MANIFEST, *paths}
    actual_files: set[str] = set()
    try:
        actual_files = {
            path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()
        }
    except OSError:
        actual_files = set()
    checks.append(
        _check(
            "no-unlisted-files",
            ModuleWorkbenchExecutionPacketCheckPlane.STORAGE,
            actual_files == expected_files,
            tuple(sorted(actual_files - expected_files)),
            tuple(sorted(expected_files - actual_files)),
            "packet directory contains only the manifest and declared artifacts",
        )
    )
    checks.append(
        _check(
            "canonical-json",
            ModuleWorkbenchExecutionPacketCheckPlane.SEMANTIC,
            _canonical_json_artifacts(artifact_rows, payloads),
            "verified",
            "verified",
            "JSON artifacts round-trip to canonical UTF-8 bytes",
        )
    )
    checks.append(
        _check(
            "public-boundary",
            ModuleWorkbenchExecutionPacketCheckPlane.PUBLIC,
            not _has_forbidden_key(manifest) and not _has_forbidden_key({"payloads": payloads}),
            "clean" if not _has_forbidden_key(manifest) else "forbidden",
            "clean",
            "manifest and artifact payloads contain only public aggregate fields",
        )
    )
    expected_manifest_address = dict(manifest)
    manifest_address = expected_manifest_address.pop("content_address", None)
    checks.append(
        _check(
            "manifest-address",
            ModuleWorkbenchExecutionPacketCheckPlane.BYTES,
            isinstance(manifest_address, str)
            and content_hash(expected_manifest_address, prefix=_PACKET_PREFIX) == manifest_address,
            manifest_address,
            content_hash(expected_manifest_address, prefix=_PACKET_PREFIX),
            "manifest content address matches the canonical descriptor",
        )
    )
    return _verification(packet_id, len(artifact_rows), present, missing, checks)


def _canonical_json_artifacts(
    artifact_rows: tuple[Mapping[str, Any], ...], payloads: Mapping[str, str]
) -> bool:
    for row in artifact_rows:
        if row.get("media_type") != _JSON:
            continue
        artifact_id = str(row.get("artifact_id", ""))
        payload = payloads.get(artifact_id)
        if payload is None:
            return False
        try:
            if canonical_json(json.loads(payload)) + "\n" != payload:
                return False
        except (json.JSONDecodeError, TypeError):
            return False
    return True


def _verification(
    packet_id: str,
    artifact_count: int,
    present_count: int,
    missing_count: int,
    checks: Iterable[ModuleWorkbenchExecutionPacketCheck],
) -> ModuleWorkbenchExecutionPacketVerification:
    selected = tuple(checks)
    accepted = bool(selected) and all(item.passed for item in selected)
    body = {
        "packet_id": packet_id,
        "artifact_count": artifact_count,
        "present_count": present_count,
        "missing_count": missing_count,
        "checks": selected,
        "accepted": accepted,
    }
    provisional = ModuleWorkbenchExecutionPacketVerification(**body, content_address="pending")
    return ModuleWorkbenchExecutionPacketVerification(
        **body,
        content_address=address_module_workbench_execution_packet_verification(provisional),
    )


def verify_module_workbench_execution_packet_value(
    value: ModuleWorkbenchExecutionPacket,
) -> ModuleWorkbenchExecutionPacketVerification:
    """Verify a typed packet without requiring a filesystem directory."""

    if not isinstance(value, ModuleWorkbenchExecutionPacket):
        raise ValidationError("typed execution packet verification requires a packet")
    byte_failures = tuple(
        sorted(
            item.artifact_id
            for item in value.artifacts
            if item.payload is None
            or hash_bytes(
                item.payload.encode(_UTF8),
                prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARTIFACT_PREFIX,
            )
            != item.content_address
        )
    )
    checks = (
        _check(
            "packet-address",
            ModuleWorkbenchExecutionPacketCheckPlane.BYTES,
            address_module_workbench_execution_packet(value) == value.content_address,
            value.content_address,
            "canonical-address",
            "packet address matches its manifest descriptor",
        ),
        _check(
            "artifact-bytes",
            ModuleWorkbenchExecutionPacketCheckPlane.BYTES,
            not byte_failures,
            byte_failures,
            (),
            "typed artifact payloads match their exact-byte addresses",
        ),
        _check(
            "packet-accepted",
            ModuleWorkbenchExecutionPacketCheckPlane.SEMANTIC,
            value.accepted,
            value.accepted,
            True,
            "typed packet is accepted before storage",
        ),
        _check(
            "public-boundary",
            ModuleWorkbenchExecutionPacketCheckPlane.PUBLIC,
            not _has_forbidden_key(value.to_dict(include_payloads=True)),
            "clean"
            if not _has_forbidden_key(value.to_dict(include_payloads=True))
            else "forbidden",
            "clean",
            "typed packet contains only public aggregate fields",
        ),
    )
    return _verification(value.packet_id, value.artifact_count, value.artifact_count, 0, checks)


def _manifest_mapping(directory: str | Path) -> tuple[Path, Mapping[str, Any]]:
    root = Path(directory)
    try:
        loaded = json.loads(
            (root / MODULE_WORKBENCH_EXECUTION_PACKET_MANIFEST).read_text(encoding=_UTF8)
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"cannot load execution packet manifest: {exc}") from exc
    if not isinstance(loaded, Mapping):
        raise ValidationError("execution packet manifest must be an object")
    return root, loaded


def write_module_workbench_execution_packet(
    packet: ModuleWorkbenchExecutionPacket,
    destination: str | Path,
    *,
    allow_existing: bool = False,
) -> ModuleWorkbenchExecutionPacket:
    """Write the manifest and every artifact atomically into one directory."""

    if not isinstance(packet, ModuleWorkbenchExecutionPacket):
        raise ValidationError("execution packet writer requires a typed packet")
    root = Path(destination)
    if root.exists() and not allow_existing:
        raise ValidationError("execution packet destination already exists")
    if root.exists() and not root.is_dir():
        raise ValidationError("execution packet destination is not a directory")
    root.mkdir(parents=True, exist_ok=True)
    _atomic_write(
        root / MODULE_WORKBENCH_EXECUTION_PACKET_MANIFEST,
        (canonical_json(packet.to_dict(include_payloads=False)) + "\n").encode(_UTF8),
    )
    for artifact in packet.artifacts:
        if artifact.payload is None:
            raise ValidationError(
                f"execution packet artifact has no payload: {artifact.artifact_id}"
            )
        path = root.joinpath(*artifact.relative_path.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(path, artifact.payload.encode(_UTF8))
    return packet


def load_module_workbench_execution_packet(
    directory: str | Path,
) -> ModuleWorkbenchExecutionPacket:
    """Load a verified packet and restore payloads for offline querying."""

    verification = verify_module_workbench_execution_packet(directory)
    if not verification.accepted:
        raise ValidationError("cannot load a blocked execution packet")
    root, manifest = _manifest_mapping(directory)
    raw_artifacts = manifest.get("artifacts")
    raw_checks = manifest.get("checks")
    if not isinstance(raw_artifacts, list) or not isinstance(raw_checks, list):
        raise ValidationError("execution packet manifest collections are invalid")
    artifacts: list[ModuleWorkbenchExecutionPacketArtifact] = []
    for row in raw_artifacts:
        if not isinstance(row, Mapping):
            raise ValidationError("execution packet artifact row is invalid")
        relative_path = str(row.get("relative_path", ""))
        payload = root.joinpath(*relative_path.split("/")).read_text(encoding=_UTF8)
        artifacts.append(
            ModuleWorkbenchExecutionPacketArtifact(
                artifact_id=str(row.get("artifact_id", "")),
                relative_path=relative_path,
                media_type=str(row.get("media_type", "")),
                kind=ModuleWorkbenchExecutionPacketArtifactKind(str(row.get("kind"))),
                byte_count=int(row.get("byte_count")),
                line_count=int(row.get("line_count")),
                content_address=str(row.get("content_address", "")),
                payload=payload,
            )
        )
    checks: list[ModuleWorkbenchExecutionPacketCheck] = []
    for row in raw_checks:
        if not isinstance(row, Mapping):
            raise ValidationError("execution packet check row is invalid")
        checks.append(
            ModuleWorkbenchExecutionPacketCheck(
                check_id=str(row.get("check_id", "")),
                plane=ModuleWorkbenchExecutionPacketCheckPlane(str(row.get("plane"))),
                passed=bool(row.get("passed")),
                observed=row.get("observed"),
                required=row.get("required"),
                detail=str(row.get("detail", "")),
                content_address=str(row.get("content_address", "")),
            )
        )
    packet = ModuleWorkbenchExecutionPacket(
        packet_id=str(manifest.get("packet_id", "")),
        version=str(manifest.get("version", "")),
        boundary=str(manifest.get("boundary", "")),
        report_address=str(manifest.get("report_address", "")),
        portfolio_address=str(manifest.get("portfolio_address", "")),
        initial_ledger_address=str(manifest.get("initial_ledger_address", "")),
        ledger_address=str(manifest.get("ledger_address", "")),
        review_address=str(manifest.get("review_address", "")),
        audit_address=str(manifest.get("audit_address", "")),
        policy_address=str(manifest.get("policy_address", "")),
        gate_address=str(manifest.get("gate_address", "")),
        runtime_address=str(manifest.get("runtime_address", "")),
        state=ModuleWorkbenchExecutionPacketState(str(manifest.get("state"))),
        accepted=bool(manifest.get("accepted")),
        artifacts=tuple(artifacts),
        checks=tuple(checks),
        content_address=str(manifest.get("content_address", "")),
    )
    if address_module_workbench_execution_packet(packet) != packet.content_address:
        raise ValidationError("execution packet manifest address mismatch after load")
    return packet


def module_workbench_execution_packet_json(
    packet: ModuleWorkbenchExecutionPacket,
    *,
    include_payloads: bool = False,
) -> str:
    """Return canonical manifest JSON, optionally with embedded payloads."""

    if not isinstance(packet, ModuleWorkbenchExecutionPacket):
        raise ValidationError("execution packet JSON requires a typed packet")
    return canonical_json(packet.to_dict(include_payloads=include_payloads)) + "\n"


def module_workbench_execution_packet_csv(packet: ModuleWorkbenchExecutionPacket) -> str:
    """Return one stable row per declared artifact."""

    if not isinstance(packet, ModuleWorkbenchExecutionPacket):
        raise ValidationError("execution packet CSV requires a typed packet")
    fields = (
        "artifact_id",
        "relative_path",
        "media_type",
        "kind",
        "byte_count",
        "line_count",
        "content_address",
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for item in packet.artifacts:
        writer.writerow(item.to_dict())
    return output.getvalue()


def render_module_workbench_execution_packet_markdown(
    packet: ModuleWorkbenchExecutionPacket,
    *,
    max_rows: int = 32,
) -> str:
    """Render a bounded handoff summary without embedding artifact payloads."""

    if not isinstance(packet, ModuleWorkbenchExecutionPacket):
        raise ValidationError("execution packet Markdown requires a typed packet")
    if max_rows < 1 or max_rows > MODULE_WORKBENCH_EXECUTION_PACKET_MAX_ARTIFACTS:
        raise ValidationError("execution packet Markdown row limit is invalid")
    lines = [
        "# Module Workbench Execution Packet",
        "",
        "Portable exact-byte handoff for offline module execution review.",
        "",
        f"- Packet: `{packet.packet_id}`",
        f"- Address: `{packet.content_address}`",
        f"- State: **{packet.state.value}**",
        f"- Accepted: **{str(packet.accepted).lower()}**",
        f"- Artifacts: **{packet.artifact_count}**",
        f"- Checks: **{packet.passed_check_count}/{len(packet.checks)} passed**",
        "",
        "## Address chain",
        "",
        "| Stage | Address |",
        "| --- | --- |",
        f"| Report | `{packet.report_address}` |",
        f"| Portfolio | `{packet.portfolio_address}` |",
        f"| Initial ledger | `{packet.initial_ledger_address}` |",
        f"| Current ledger | `{packet.ledger_address}` |",
        f"| Review | `{packet.review_address}` |",
        f"| Audit | `{packet.audit_address}` |",
        f"| Policy | `{packet.policy_address}` |",
        f"| Gate | `{packet.gate_address}` |",
        f"| Runtime | `{packet.runtime_address}` |",
        "",
        "## Artifacts",
        "",
        "| ID | Kind | Path | Bytes | Lines | Address |",
        "| --- | --- | --- | ---: | ---: | --- |",
    ]
    for artifact in packet.artifacts[:max_rows]:
        lines.append(
            f"| `{artifact.artifact_id}` | {artifact.kind.value} | `{artifact.relative_path}` | "
            f"{artifact.byte_count:,} | {artifact.line_count:,} | `{artifact.content_address}` |"
        )
    if len(packet.artifacts) > max_rows:
        lines.append(f"| … | … | … | … | … | {len(packet.artifacts) - max_rows:,} more artifacts |")
    lines.extend(
        [
            "",
            "## Checks",
            "",
            "| Check | Plane | Result | Detail |",
            "| --- | --- | --- | --- |",
        ]
    )
    for check in packet.checks[:max_rows]:
        lines.append(
            f"| `{check.check_id}` | {check.plane.value} | "
            f"{'pass' if check.passed else 'fail'} | {check.detail} |"
        )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_schema() -> dict[str, Any]:
    """Describe packet resources and verification guarantees."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_BOUNDARY,
        "manifest": MODULE_WORKBENCH_EXECUTION_PACKET_MANIFEST,
        "artifact_count": MODULE_WORKBENCH_EXECUTION_PACKET_ARTIFACT_COUNT,
        "artifact_kinds": [item.value for item in ModuleWorkbenchExecutionPacketArtifactKind],
        "check_planes": [item.value for item in ModuleWorkbenchExecutionPacketCheckPlane],
        "states": [item.value for item in ModuleWorkbenchExecutionPacketState],
        "resources": ["manifest", "artifacts", "checks", "links", "summary"],
        "operations": [
            "build",
            "write",
            "verify",
            "load",
            "query",
            "replay",
            "diff",
            "release",
        ],
        "limits": {
            "maximum_artifacts": MODULE_WORKBENCH_EXECUTION_PACKET_MAX_ARTIFACTS,
            "maximum_checks": MODULE_WORKBENCH_EXECUTION_PACKET_MAX_CHECKS,
        },
        "exact_utf8_bytes": True,
        "path_free": True,
        "timestamp_free": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_capabilities() -> dict[str, Any]:
    """Declare packet operations for CLI, API, and offline clients."""

    operations = (
        "build_packet",
        "derive_workbench_summary",
        "select_portfolio",
        "retain_initial_and_current_ledger",
        "package_review_projection",
        "package_independent_audit",
        "package_policy_gate",
        "package_runtime_handoff",
        "address_artifact_bytes",
        "write_atomic_files",
        "verify_manifest_shape",
        "verify_safe_paths",
        "verify_exact_bytes",
        "verify_canonical_json",
        "verify_link_chain",
        "verify_public_boundary",
        "load_verified_packet",
        "query_artifacts",
        "query_checks",
        "query_links",
        "replay_packet",
        "diff_packets",
        "release_gate",
        "export_manifest_json",
        "export_artifact_csv",
        "render_markdown",
    )
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "artifact_count": MODULE_WORKBENCH_EXECUTION_PACKET_ARTIFACT_COUNT,
        "deterministic": True,
        "offline": True,
        "read_only_verification": True,
        "atomic_writes": True,
        "exact_byte_addresses": True,
        "identity_free": True,
    }


__all__ = [
    "build_module_workbench_execution_packet",
    "load_module_workbench_execution_packet",
    "module_workbench_execution_packet_capabilities",
    "module_workbench_execution_packet_csv",
    "module_workbench_execution_packet_json",
    "module_workbench_execution_packet_schema",
    "render_module_workbench_execution_packet_markdown",
    "verify_module_workbench_execution_packet",
    "verify_module_workbench_execution_packet_value",
    "write_module_workbench_execution_packet",
]
