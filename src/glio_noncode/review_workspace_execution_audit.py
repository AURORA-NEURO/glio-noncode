"""Independent integrity audit for a persisted review-plan execution ledger.

The execution store already fails closed when a ledger cannot be replayed.  An
audit is useful when an operator needs the reasons, exact filesystem facts, and
reconciliation outcomes in one public receipt.  This module therefore inspects
the ledger files independently, reports every bounded finding it can establish,
and never repairs or rewrites the store.  It does not expose raw evidence,
identity, attribution, model metadata, programming-language metadata, or a
scientific decision.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from io import StringIO
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_fabric_support import contains_private_key
from .review_workspace_execution import (
    REVIEW_WORKSPACE_EXECUTION_EVENT_VERSION,
    REVIEW_WORKSPACE_EXECUTION_EVENTS_FILE,
    REVIEW_WORKSPACE_EXECUTION_MANIFEST_FILE,
    REVIEW_WORKSPACE_EXECUTION_VERSION,
    ReviewPlanExecutionEvent,
    ReviewPlanExecutionStore,
    ReviewWorkspaceExecutionReport,
    replay_review_workspace_plan_execution,
    review_plan_execution_event_from_mapping,
    review_workspace_execution_report_from_mapping,
)
from .review_workspace_plan import ReviewWorkspacePlan, build_persisted_review_workspace_plan
from .serialization import canonical_json, content_hash, hash_bytes, jsonable


REVIEW_WORKSPACE_EXECUTION_AUDIT_VERSION = "review-workspace-execution-audit-v1"
REVIEW_WORKSPACE_EXECUTION_AUDIT_SCHEMA_VERSION = "review-workspace-execution-audit-schema-v1"
REVIEW_WORKSPACE_EXECUTION_AUDIT_MAX_FINDINGS = 512

_FORBIDDEN_KEYS = frozenset(
    {
        "agent",
        "agent_id",
        "assistant",
        "author",
        "contact",
        "credential",
        "email",
        "generated_by",
        "individual",
        "language",
        "model",
        "patient",
        "phone",
        "programming_language",
        "sample",
        "secret",
        "subject",
        "token",
    }
)


class ReviewWorkspaceExecutionAuditSeverity(StrEnum):
    """Operator severity for one audit finding."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ReviewWorkspaceExecutionAuditDomain(StrEnum):
    """Independent plane that produced a finding."""

    FILESYSTEM = "filesystem"
    MANIFEST = "manifest"
    EVENTS = "events"
    REPLAY = "replay"
    BOUNDARY = "boundary"


def _text(value: Any, field: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValidationError(f"{field} must not be empty")
    return normalized


def _optional_text(value: Any, field: str) -> str | None:
    if value in (None, ""):
        return None
    return _text(value, field)


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return {str(key): item for key, item in value.items()}


def _text_sequence(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValidationError(f"{field} must be an array")
    values = tuple(_text(item, f"{field}[]") for item in value)
    if len(values) != len(set(values)):
        raise ValidationError(f"{field} must not contain duplicates")
    return values


def _private_key_paths(value: Any, path: str = "") -> tuple[str, ...]:
    if isinstance(value, Mapping):
        paths: list[str] = []
        for key, item in value.items():
            key_text = str(key)
            child = f"{path}.{key_text}" if path else key_text
            if key_text.casefold() in _FORBIDDEN_KEYS:
                paths.append(child)
            paths.extend(_private_key_paths(item, child))
        return tuple(paths)
    if isinstance(value, (list, tuple)):
        paths: list[str] = []
        for index, item in enumerate(value):
            paths.extend(_private_key_paths(item, f"{path}[{index}]"))
        return tuple(paths)
    return ()


def _address(value: Any, prefix: str) -> str:
    return content_hash(value, prefix=prefix)


def _address_without_content(body: Mapping[str, Any], prefix: str, field: str) -> str:
    address = _text(body.get("content_address"), field)
    source = {key: item for key, item in body.items() if key != "content_address"}
    if _address(source, prefix) != address:
        raise ValidationError(f"{field} address mismatch")
    return address


def _relative_ledger_path(plan: ReviewWorkspacePlan) -> str:
    prefix, _, digest = plan.content_address.partition(":")
    if prefix != "review-workspace-plan" or not digest:
        raise ValidationError("execution audit requires a safe review plan address")
    return f"review-plan-execution/{digest}"


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceExecutionAuditFinding:
    """One independently established ledger audit outcome."""

    check_id: str
    domain: ReviewWorkspaceExecutionAuditDomain
    severity: ReviewWorkspaceExecutionAuditSeverity
    accepted: bool
    path: str
    expected: Any
    observed: Any
    message: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceExecutionAudit:
    """Bounded audit receipt for one plan's persisted execution ledger."""

    audit_version: str
    plan_id: str
    plan_address: str
    workspace_id: str
    run_id: str
    case_id: str
    ledger_path: str
    events_path: str
    manifest_path: str
    directory_exists: bool
    ledger_present: bool
    exact_bytes: bool
    manifest_accepted: bool
    replay_accepted: bool
    boundary_accepted: bool
    accepted: bool
    event_count: int
    byte_count: int
    line_count: int
    events_address: str | None
    manifest_address: str | None
    first_event_address: str | None
    last_event_address: str | None
    findings: tuple[ReviewWorkspaceExecutionAuditFinding, ...]
    warnings: tuple[str, ...]
    report: ReviewWorkspaceExecutionReport | None
    content_address: str

    def _summary_body(self) -> dict[str, Any]:
        return {
            "audit_version": self.audit_version,
            "plan_id": self.plan_id,
            "plan_address": self.plan_address,
            "workspace_id": self.workspace_id,
            "run_id": self.run_id,
            "case_id": self.case_id,
            "ledger_path": self.ledger_path,
            "events_path": self.events_path,
            "manifest_path": self.manifest_path,
            "directory_exists": self.directory_exists,
            "ledger_present": self.ledger_present,
            "exact_bytes": self.exact_bytes,
            "manifest_accepted": self.manifest_accepted,
            "replay_accepted": self.replay_accepted,
            "boundary_accepted": self.boundary_accepted,
            "accepted": self.accepted,
            "event_count": self.event_count,
            "byte_count": self.byte_count,
            "line_count": self.line_count,
            "events_address": self.events_address,
            "manifest_address": self.manifest_address,
            "first_event_address": self.first_event_address,
            "last_event_address": self.last_event_address,
            "findings": self.findings,
            "warnings": self.warnings,
        }

    @property
    def finding_count(self) -> int:
        return len(self.findings)

    @property
    def passed_finding_count(self) -> int:
        return sum(item.accepted for item in self.findings)

    @property
    def failed_finding_count(self) -> int:
        return self.finding_count - self.passed_finding_count

    @property
    def error_count(self) -> int:
        return sum(
            item.severity is ReviewWorkspaceExecutionAuditSeverity.ERROR
            and not item.accepted
            for item in self.findings
        )

    def to_dict(self, *, include_report: bool = False) -> dict[str, Any]:
        body = self._summary_body() | {"content_address": self.content_address}
        if include_report and self.report is not None:
            body["report"] = self.report
        return jsonable(body)


def _finding(
    check_id: str,
    domain: ReviewWorkspaceExecutionAuditDomain,
    accepted: bool,
    path: str,
    expected: Any,
    observed: Any,
    message: str,
    *,
    severity: ReviewWorkspaceExecutionAuditSeverity | None = None,
) -> ReviewWorkspaceExecutionAuditFinding:
    selected_severity = severity or (
        ReviewWorkspaceExecutionAuditSeverity.INFO
        if accepted
        else ReviewWorkspaceExecutionAuditSeverity.ERROR
    )
    body = {
        "check_id": check_id,
        "domain": domain,
        "severity": selected_severity,
        "accepted": accepted,
        "path": path,
        "expected": expected,
        "observed": observed,
        "message": message,
    }
    return ReviewWorkspaceExecutionAuditFinding(
        **body,
        content_address=_address(body, "review-workspace-execution-audit-finding"),
    )


def _expected_manifest(
    plan: ReviewWorkspacePlan,
    events: tuple[ReviewPlanExecutionEvent, ...],
    event_bytes: bytes,
) -> dict[str, Any]:
    return {
        "execution_version": REVIEW_WORKSPACE_EXECUTION_VERSION,
        "event_version": REVIEW_WORKSPACE_EXECUTION_EVENT_VERSION,
        "plan_id": plan.plan_id,
        "plan_address": plan.content_address,
        "workspace_id": plan.workspace_id,
        "run_id": plan.run_id,
        "case_id": plan.case_id,
        "event_count": len(events),
        "byte_count": len(event_bytes),
        "line_count": len(event_bytes.splitlines()),
        "first_event_address": events[0].content_address if events else None,
        "last_event_address": events[-1].content_address if events else None,
        "events_address": hash_bytes(event_bytes, prefix="review-plan-execution-events"),
    }


def _canonical_event_line(event: ReviewPlanExecutionEvent) -> bytes:
    return (canonical_json(event.to_dict()) + "\n").encode("utf-8")


def _safe_read(path: Path) -> tuple[bytes | None, str | None]:
    try:
        return path.read_bytes(), None
    except (OSError, UnicodeError) as exc:
        return None, str(exc)


def _safe_manifest(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, str(exc)
    if not isinstance(value, Mapping):
        return None, "manifest root is not an object"
    return {str(key): item for key, item in value.items()}, None


def _parse_events(
    event_bytes: bytes,
) -> tuple[tuple[ReviewPlanExecutionEvent, ...], bool, str | None]:
    if not event_bytes:
        return (), True, None
    if not event_bytes.endswith(b"\n"):
        return (), False, "event file does not end with a newline"
    events: list[ReviewPlanExecutionEvent] = []
    for sequence, line in enumerate(event_bytes.splitlines()):
        try:
            raw = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return (), False, f"event line {sequence} is invalid JSON: {exc}"
        if not isinstance(raw, Mapping):
            return (), False, f"event line {sequence} is not an object"
        try:
            events.append(review_plan_execution_event_from_mapping(raw))
        except ValidationError as exc:
            return (), False, f"event line {sequence} failed validation: {exc}"
    return tuple(events), True, None


def audit_review_workspace_plan_execution(
    plan: ReviewWorkspacePlan,
    store: ReviewPlanExecutionStore,
) -> ReviewWorkspaceExecutionAudit:
    """Audit a ledger without using its store read/replay convenience path."""

    if not isinstance(plan, ReviewWorkspacePlan):
        raise ValidationError("execution audit requires a typed review workspace plan")
    if not plan.accepted:
        raise ValidationError("execution audit requires an accepted review workspace plan")
    if not isinstance(store, ReviewPlanExecutionStore):
        raise ValidationError("execution audit requires a typed execution store")
    directory, events_file, manifest_file = store.paths(plan)
    relative_directory = _relative_ledger_path(plan)
    events_relative = f"{relative_directory}/{REVIEW_WORKSPACE_EXECUTION_EVENTS_FILE}"
    manifest_relative = f"{relative_directory}/{REVIEW_WORKSPACE_EXECUTION_MANIFEST_FILE}"
    findings: list[ReviewWorkspaceExecutionAuditFinding] = []
    warnings: list[str] = []
    directory_exists = directory.exists()
    event_bytes = b""
    events: tuple[ReviewPlanExecutionEvent, ...] = ()
    manifest: dict[str, Any] | None = None
    exact_bytes = True
    manifest_accepted = True
    replay_accepted = True
    boundary_accepted = True
    report: ReviewWorkspaceExecutionReport | None = None
    if not directory_exists:
        warnings.append("no persisted execution ledger exists; empty replay is valid")
        findings.append(
            _finding(
                "ledger:absent-is-empty",
                ReviewWorkspaceExecutionAuditDomain.FILESYSTEM,
                True,
                relative_directory,
                "absent or complete ledger directory",
                "absent",
                "no ledger files exist; the persisted execution is an empty replay",
                severity=ReviewWorkspaceExecutionAuditSeverity.WARNING,
            )
        )
    else:
        directory_safe = directory.is_dir() and not directory.is_symlink()
        findings.append(
            _finding(
                "ledger:directory-safe",
                ReviewWorkspaceExecutionAuditDomain.FILESYSTEM,
                directory_safe,
                relative_directory,
                "directory",
                "directory" if directory_safe else "unsafe filesystem entry",
                "ledger directory is a non-symlink directory"
                if directory_safe
                else "ledger directory is missing, symlinked, or not a directory",
            )
        )
        if not directory_safe:
            manifest_accepted = False
            replay_accepted = False
        else:
            allowed = {
                REVIEW_WORKSPACE_EXECUTION_EVENTS_FILE,
                REVIEW_WORKSPACE_EXECUTION_MANIFEST_FILE,
            }
            unexpected = sorted(path.name for path in directory.iterdir() if path.name not in allowed)
            findings.append(
                _finding(
                    "ledger:allowed-files",
                    ReviewWorkspaceExecutionAuditDomain.FILESYSTEM,
                    not unexpected,
                    relative_directory,
                    sorted(allowed),
                    unexpected,
                    "ledger contains only its event and manifest files"
                    if not unexpected
                    else "ledger contains unexpected files",
                )
            )
            if unexpected:
                manifest_accepted = False
            if not events_file.is_file() or events_file.is_symlink():
                exact_bytes = False
                manifest_accepted = False
                findings.append(
                    _finding(
                        "events:file-present",
                        ReviewWorkspaceExecutionAuditDomain.FILESYSTEM,
                        False,
                        events_relative,
                        "regular file",
                        "missing or symlink",
                        "event file is missing or symlinked",
                    )
                )
            else:
                raw_bytes, error = _safe_read(events_file)
                if raw_bytes is None:
                    exact_bytes = False
                    manifest_accepted = False
                    findings.append(
                        _finding(
                            "events:readable",
                            ReviewWorkspaceExecutionAuditDomain.EVENTS,
                            False,
                            events_relative,
                            "readable UTF-8 bytes",
                            error,
                            "event file could not be read",
                        )
                    )
                else:
                    event_bytes = raw_bytes
                    events, parsed, parse_error = _parse_events(event_bytes)
                    if not parsed:
                        exact_bytes = False
                        replay_accepted = False
                        manifest_accepted = False
                    findings.append(
                        _finding(
                            "events:parseable",
                            ReviewWorkspaceExecutionAuditDomain.EVENTS,
                            parsed,
                            events_relative,
                            "valid event JSONL",
                            parse_error or "valid event JSONL",
                            "event stream parses into typed events"
                            if parsed
                            else "event stream cannot be parsed into typed events",
                        )
                    )
                    if parsed:
                        canonical_bytes = b"".join(_canonical_event_line(item) for item in events)
                        exact_bytes = canonical_bytes == event_bytes
                        findings.append(
                            _finding(
                                "events:exact-canonical-bytes",
                                ReviewWorkspaceExecutionAuditDomain.EVENTS,
                                exact_bytes,
                                events_relative,
                                len(canonical_bytes),
                                len(event_bytes),
                                "event bytes match canonical UTF-8 serialization"
                                if exact_bytes
                                else "event bytes differ from canonical serialization",
                            )
                        )
                        if not exact_bytes:
                            manifest_accepted = False
                    else:
                        findings.append(
                            _finding(
                                "events:canonical-bytes-unavailable",
                                ReviewWorkspaceExecutionAuditDomain.EVENTS,
                                False,
                                events_relative,
                                "typed events",
                                "unavailable",
                                "canonical event bytes cannot be independently reconstructed",
                            )
                        )
            if not manifest_file.is_file() or manifest_file.is_symlink():
                exact_bytes = False
                manifest_accepted = False
                findings.append(
                    _finding(
                        "manifest:file-present",
                        ReviewWorkspaceExecutionAuditDomain.FILESYSTEM,
                        False,
                        manifest_relative,
                        "regular file",
                        "missing or symlink",
                        "manifest file is missing or symlinked",
                    )
                )
            else:
                manifest_bytes, manifest_read_error = _safe_read(manifest_file)
                manifest, error = _safe_manifest(manifest_file)
                if manifest is None:
                    exact_bytes = False
                    manifest_accepted = False
                    findings.append(
                        _finding(
                            "manifest:parseable",
                            ReviewWorkspaceExecutionAuditDomain.MANIFEST,
                            False,
                            manifest_relative,
                            "JSON object",
                            error,
                            "manifest cannot be parsed as a JSON object",
                        )
                    )
                else:
                    findings.append(
                        _finding(
                            "manifest:parseable",
                            ReviewWorkspaceExecutionAuditDomain.MANIFEST,
                            True,
                            manifest_relative,
                            "JSON object",
                            "JSON object",
                            "manifest parses as a JSON object",
                        )
                    )
                    expected_manifest = _expected_manifest(plan, events, event_bytes)
                    for key, expected in expected_manifest.items():
                        observed = manifest.get(key)
                        matches = observed == expected
                        if not matches:
                            manifest_accepted = False
                        findings.append(
                            _finding(
                                f"manifest:{key}",
                                ReviewWorkspaceExecutionAuditDomain.MANIFEST,
                                matches,
                                f"{manifest_relative}#{key}",
                                expected,
                                observed,
                                f"manifest {key} reconciles"
                                if matches
                                else f"manifest {key} does not reconcile",
                            )
                        )
                    expected_manifest_address = _address(
                        expected_manifest,
                        "review-plan-execution-manifest",
                    )
                    manifest_address = manifest.get("manifest_address")
                    matches = manifest_address == expected_manifest_address
                    if not matches:
                        manifest_accepted = False
                    findings.append(
                        _finding(
                            "manifest:address",
                            ReviewWorkspaceExecutionAuditDomain.MANIFEST,
                            matches,
                            f"{manifest_relative}#manifest_address",
                            expected_manifest_address,
                            manifest_address,
                            "manifest content address reconciles"
                            if matches
                            else "manifest content address does not reconcile",
                        )
                    )
                    expected_manifest_bytes = (
                        canonical_json(
                            expected_manifest
                            | {"manifest_address": expected_manifest_address}
                        )
                    ).encode("utf-8")
                    manifest_exact = manifest_read_error is None and manifest_bytes == expected_manifest_bytes
                    exact_bytes = exact_bytes and manifest_exact
                    findings.append(
                        _finding(
                            "manifest:exact-canonical-bytes",
                            ReviewWorkspaceExecutionAuditDomain.MANIFEST,
                            manifest_exact,
                            manifest_relative,
                            len(expected_manifest_bytes),
                            None if manifest_bytes is None else len(manifest_bytes),
                            "manifest bytes match canonical UTF-8 serialization"
                            if manifest_exact
                            else "manifest bytes differ from canonical serialization",
                        )
                    )
                    if not manifest_exact:
                        manifest_accepted = False
            if events:
                replayed = True
                try:
                    report = replay_review_workspace_plan_execution(plan, events)
                except ValidationError as exc:
                    replayed = False
                    findings.append(
                        _finding(
                            "replay:accepted",
                            ReviewWorkspaceExecutionAuditDomain.REPLAY,
                            False,
                            events_relative,
                            "accepted replay",
                            str(exc),
                            "event stream fails typed plan replay",
                        )
                    )
                else:
                    findings.append(
                        _finding(
                            "replay:accepted",
                            ReviewWorkspaceExecutionAuditDomain.REPLAY,
                            report.accepted,
                            events_relative,
                            True,
                            report.accepted,
                            "event stream replays against the supplied plan"
                            if report.accepted
                            else "event stream replay is not accepted",
                        )
                    )
                    if not report.accepted:
                        replayed = False
                replay_accepted = replayed
            else:
                findings.append(
                    _finding(
                        "replay:empty-or-readable",
                        ReviewWorkspaceExecutionAuditDomain.REPLAY,
                        True,
                        events_relative,
                        "empty or typed event stream",
                        "empty",
                        "empty event stream has a valid open replay",
                    )
                )
    if not events and not directory_exists:
        event_bytes = b""
    event_count = len(events)
    byte_count = len(event_bytes)
    line_count = len(event_bytes.splitlines())
    events_address = hash_bytes(event_bytes, prefix="review-plan-execution-events")
    manifest_address = None if manifest is None else _optional_text(
        manifest.get("manifest_address"),
        "manifest.manifest_address",
    )
    first_event_address = events[0].content_address if events else None
    last_event_address = events[-1].content_address if events else None
    public_payload = {
        "events": events,
        "manifest": manifest,
        "findings": findings,
    }
    boundary_accepted = not (_private_key_paths(jsonable(public_payload)) or contains_private_key(public_payload))
    findings.append(
        _finding(
            "boundary:public-keys",
            ReviewWorkspaceExecutionAuditDomain.BOUNDARY,
            boundary_accepted,
            f"{relative_directory}/public",
            "no forbidden public keys",
            "safe" if boundary_accepted else "forbidden key present",
            "audit inputs contain only public execution fields"
            if boundary_accepted
            else "audit inputs contain a forbidden private or attribution key",
        )
    )
    if len(findings) > REVIEW_WORKSPACE_EXECUTION_AUDIT_MAX_FINDINGS:
        raise ValidationError("execution audit finding count exceeds the bound")
    accepted = all(item.accepted for item in findings) and boundary_accepted
    body = {
        "audit_version": REVIEW_WORKSPACE_EXECUTION_AUDIT_VERSION,
        "plan_id": plan.plan_id,
        "plan_address": plan.content_address,
        "workspace_id": plan.workspace_id,
        "run_id": plan.run_id,
        "case_id": plan.case_id,
        "ledger_path": relative_directory,
        "events_path": events_relative,
        "manifest_path": manifest_relative,
        "directory_exists": directory_exists,
        "ledger_present": directory_exists and (events_file.exists() or manifest_file.exists()),
        "exact_bytes": exact_bytes,
        "manifest_accepted": manifest_accepted,
        "replay_accepted": replay_accepted,
        "boundary_accepted": boundary_accepted,
        "accepted": accepted,
        "event_count": event_count,
        "byte_count": byte_count,
        "line_count": line_count,
        "events_address": events_address,
        "manifest_address": manifest_address,
        "first_event_address": first_event_address,
        "last_event_address": last_event_address,
        "findings": tuple(findings),
        "warnings": tuple(warnings),
    }
    if contains_private_key(body):
        raise ValidationError("execution audit failed the public boundary")
    return ReviewWorkspaceExecutionAudit(
        **body,
        report=report,
        content_address=_address(body, "review-workspace-execution-audit"),
    )


def audit_persisted_review_workspace_plan_execution(
    runtime: Any,
    run_id: str,
    *,
    baseline_run_id: str | None = None,
    plan_config: Any | None = None,
    execution_store: ReviewPlanExecutionStore | None = None,
) -> ReviewWorkspaceExecutionAudit:
    """Build an independent audit for one persisted run."""

    plan = build_persisted_review_workspace_plan(
        runtime,
        run_id,
        baseline_run_id=baseline_run_id,
        config=plan_config,
    )
    store = execution_store or ReviewPlanExecutionStore(runtime.store.root)
    return audit_review_workspace_plan_execution(plan, store)


def _finding_from_mapping(value: Any) -> ReviewWorkspaceExecutionAuditFinding:
    body = _mapping(value, "execution audit finding")
    content_address = _address_without_content(
        body,
        "review-workspace-execution-audit-finding",
        "finding.content_address",
    )
    try:
        domain = ReviewWorkspaceExecutionAuditDomain(_text(body.get("domain"), "finding.domain"))
        severity = ReviewWorkspaceExecutionAuditSeverity(
            _text(body.get("severity"), "finding.severity")
        )
    except ValueError as exc:
        raise ValidationError("execution audit finding enum is invalid") from exc
    return ReviewWorkspaceExecutionAuditFinding(
        check_id=_text(body.get("check_id"), "finding.check_id"),
        domain=domain,
        severity=severity,
        accepted=bool(body.get("accepted")),
        path=_text(body.get("path"), "finding.path"),
        expected=body.get("expected"),
        observed=body.get("observed"),
        message=_text(body.get("message"), "finding.message"),
        content_address=content_address,
    )


def review_workspace_execution_audit_from_mapping(
    value: Mapping[str, Any],
) -> ReviewWorkspaceExecutionAudit:
    """Hydrate and verify an audit summary artifact."""

    body = _mapping(value, "execution audit")
    if _private_key_paths(body) or contains_private_key(body):
        raise ValidationError("execution audit violates the public boundary")
    version = _text(body.get("audit_version"), "audit.audit_version")
    if version != REVIEW_WORKSPACE_EXECUTION_AUDIT_VERSION:
        raise ValidationError("execution audit version is invalid")
    raw_findings = body.get("findings", ())
    if not isinstance(raw_findings, (list, tuple)):
        raise ValidationError("execution audit findings must be an array")
    findings = tuple(_finding_from_mapping(item) for item in raw_findings)
    if len(findings) > REVIEW_WORKSPACE_EXECUTION_AUDIT_MAX_FINDINGS:
        raise ValidationError("execution audit finding count exceeds the bound")
    warnings = _text_sequence(body.get("warnings", ()), "audit.warnings")
    report = None
    if "report" in body:
        report = review_workspace_execution_report_from_mapping(
            _mapping(body.get("report"), "audit.report")
        )
    values = {
        "audit_version": version,
        "plan_id": _text(body.get("plan_id"), "audit.plan_id"),
        "plan_address": _text(body.get("plan_address"), "audit.plan_address"),
        "workspace_id": _text(body.get("workspace_id"), "audit.workspace_id"),
        "run_id": _text(body.get("run_id"), "audit.run_id"),
        "case_id": _text(body.get("case_id"), "audit.case_id"),
        "ledger_path": _text(body.get("ledger_path"), "audit.ledger_path"),
        "events_path": _text(body.get("events_path"), "audit.events_path"),
        "manifest_path": _text(body.get("manifest_path"), "audit.manifest_path"),
        "directory_exists": bool(body.get("directory_exists")),
        "ledger_present": bool(body.get("ledger_present")),
        "exact_bytes": bool(body.get("exact_bytes")),
        "manifest_accepted": bool(body.get("manifest_accepted")),
        "replay_accepted": bool(body.get("replay_accepted")),
        "boundary_accepted": bool(body.get("boundary_accepted")),
        "accepted": bool(body.get("accepted")),
        "event_count": int(body.get("event_count")),
        "byte_count": int(body.get("byte_count")),
        "line_count": int(body.get("line_count")),
        "events_address": _optional_text(body.get("events_address"), "audit.events_address"),
        "manifest_address": _optional_text(body.get("manifest_address"), "audit.manifest_address"),
        "first_event_address": _optional_text(
            body.get("first_event_address"),
            "audit.first_event_address",
        ),
        "last_event_address": _optional_text(
            body.get("last_event_address"),
            "audit.last_event_address",
        ),
        "findings": findings,
        "warnings": warnings,
    }
    if any(value < 0 for value in (values["event_count"], values["byte_count"], values["line_count"])):
        raise ValidationError("execution audit numeric counts must be non-negative")
    expected_accepted = all(item.accepted for item in findings)
    if values["accepted"] != expected_accepted:
        raise ValidationError("execution audit accepted flag does not reconcile")
    if report is not None and values["event_count"]:
        if report.event_count != values["event_count"]:
            raise ValidationError("execution audit report event count does not reconcile")
    source = dict(body)
    source.pop("content_address", None)
    source.pop("report", None)
    content_address = _text(body.get("content_address"), "audit.content_address")
    if _address(source, "review-workspace-execution-audit") != content_address:
        raise ValidationError("execution audit content address does not reconcile")
    return ReviewWorkspaceExecutionAudit(
        **values,
        report=report,
        content_address=content_address,
    )


def review_workspace_execution_audit_json(
    audit: ReviewWorkspaceExecutionAudit,
    *,
    include_report: bool = False,
) -> str:
    """Render canonical audit JSON."""

    return canonical_json(audit.to_dict(include_report=include_report)) + "\n"


def review_workspace_execution_audit_csv(
    audit: ReviewWorkspaceExecutionAudit,
) -> str:
    """Render all findings as a deterministic CSV."""

    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        (
            "check_id",
            "domain",
            "severity",
            "accepted",
            "path",
            "expected",
            "observed",
            "message",
            "content_address",
        )
    )
    for item in audit.findings:
        writer.writerow(
            (
                item.check_id,
                item.domain.value,
                item.severity.value,
                item.accepted,
                item.path,
                canonical_json(item.expected),
                canonical_json(item.observed),
                item.message,
                item.content_address,
            )
        )
    return output.getvalue()


def render_review_workspace_execution_audit_markdown(
    audit: ReviewWorkspaceExecutionAudit,
) -> str:
    """Render a compact but complete operator audit report."""

    lines = [
        "# Review workspace execution audit",
        "",
        f"- Accepted: `{audit.accepted}`",
        f"- Ledger present: `{audit.ledger_present}`",
        f"- Exact bytes: `{audit.exact_bytes}`",
        f"- Manifest accepted: `{audit.manifest_accepted}`",
        f"- Replay accepted: `{audit.replay_accepted}`",
        f"- Boundary accepted: `{audit.boundary_accepted}`",
        f"- Events: `{audit.event_count}` ({audit.byte_count} bytes)",
        f"- Findings: `{audit.passed_finding_count}/{audit.finding_count}` passed",
        "",
        "| Check | Domain | Severity | Accepted | Message |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in audit.findings:
        lines.append(
            f"| `{item.check_id}` | `{item.domain.value}` | `{item.severity.value}` | "
            f"{item.accepted} | {item.message} |"
        )
    if audit.warnings:
        lines.extend(("", "Warnings:", ""))
        lines.extend(f"- {warning}" for warning in audit.warnings)
    lines.extend(
        (
            "",
            "This audit is read-only. It reports integrity state and never repairs the ledger.",
            "",
        )
    )
    return "\n".join(lines)


def review_workspace_execution_audit_export_payloads(
    audit: ReviewWorkspaceExecutionAudit,
) -> dict[str, str]:
    """Return deterministic JSON, Markdown, and CSV audit artifacts."""

    return {
        "review-workspace-execution-audit.json": review_workspace_execution_audit_json(audit),
        "review-workspace-execution-audit.md": render_review_workspace_execution_audit_markdown(audit),
        "review-workspace-execution-audit.csv": review_workspace_execution_audit_csv(audit),
    }


def review_workspace_execution_audit_schema() -> dict[str, Any]:
    """Return the machine-readable ledger-audit contract."""

    return {
        "version": REVIEW_WORKSPACE_EXECUTION_AUDIT_SCHEMA_VERSION,
        "audit_version": REVIEW_WORKSPACE_EXECUTION_AUDIT_VERSION,
        "type": "object",
        "required": [
            "audit_version",
            "plan_address",
            "ledger_path",
            "exact_bytes",
            "manifest_accepted",
            "replay_accepted",
            "boundary_accepted",
            "accepted",
            "event_count",
            "findings",
            "content_address",
        ],
        "properties": {
            "audit_version": {"const": REVIEW_WORKSPACE_EXECUTION_AUDIT_VERSION},
            "plan_id": {"type": "string"},
            "plan_address": {"type": "string"},
            "workspace_id": {"type": "string"},
            "run_id": {"type": "string"},
            "case_id": {"type": "string"},
            "ledger_path": {"type": "string"},
            "events_path": {"type": "string"},
            "manifest_path": {"type": "string"},
            "directory_exists": {"type": "boolean"},
            "ledger_present": {"type": "boolean"},
            "exact_bytes": {"type": "boolean"},
            "manifest_accepted": {"type": "boolean"},
            "replay_accepted": {"type": "boolean"},
            "boundary_accepted": {"type": "boolean"},
            "accepted": {"type": "boolean"},
            "event_count": {"type": "integer", "minimum": 0},
            "byte_count": {"type": "integer", "minimum": 0},
            "line_count": {"type": "integer", "minimum": 0},
            "findings": {"type": "array", "maxItems": REVIEW_WORKSPACE_EXECUTION_AUDIT_MAX_FINDINGS},
            "warnings": {"type": "array"},
            "content_address": {"type": "string"},
        },
        "checks": {
            "filesystem": ["ledger:absent-is-empty", "ledger:directory-safe", "ledger:allowed-files"],
            "events": ["events:file-present", "events:readable", "events:parseable", "events:exact-canonical-bytes"],
            "manifest": [
                "manifest:file-present",
                "manifest:parseable",
                "manifest:<field>",
                "manifest:address",
                "manifest:exact-canonical-bytes",
            ],
            "replay": ["replay:accepted"],
            "boundary": ["boundary:public-keys"],
        },
        "boundary": {
            "raw_evidence": False,
            "reviewer_identity": False,
            "agent_identity": False,
            "model_metadata": False,
            "programming_language_metadata": False,
            "scientific_decision": False,
        },
        "limits": {"max_findings": REVIEW_WORKSPACE_EXECUTION_AUDIT_MAX_FINDINGS},
    }


def review_workspace_execution_audit_capabilities() -> dict[str, Any]:
    """Return capabilities for independent execution-ledger auditing."""

    return {
        "version": REVIEW_WORKSPACE_EXECUTION_AUDIT_VERSION,
        "independent_filesystem_inspection": True,
        "safe_path_checks": True,
        "unexpected_file_detection": True,
        "event_jsonl_parsing": True,
        "canonical_byte_reconciliation": True,
        "manifest_field_reconciliation": True,
        "manifest_address_reconciliation": True,
        "typed_replay_verification": True,
        "public_boundary_audit": True,
        "read_only": True,
        "missing_ledger_empty_replay": True,
        "structured_findings": True,
        "json_export": True,
        "csv_export": True,
        "markdown_export": True,
        "bounded_findings": True,
        "content_addressed": True,
        "cli_surface": True,
        "api_surface": True,
    }


__all__ = [
    "REVIEW_WORKSPACE_EXECUTION_AUDIT_MAX_FINDINGS",
    "REVIEW_WORKSPACE_EXECUTION_AUDIT_SCHEMA_VERSION",
    "REVIEW_WORKSPACE_EXECUTION_AUDIT_VERSION",
    "ReviewWorkspaceExecutionAudit",
    "ReviewWorkspaceExecutionAuditDomain",
    "ReviewWorkspaceExecutionAuditFinding",
    "ReviewWorkspaceExecutionAuditSeverity",
    "audit_persisted_review_workspace_plan_execution",
    "audit_review_workspace_plan_execution",
    "render_review_workspace_execution_audit_markdown",
    "review_workspace_execution_audit_capabilities",
    "review_workspace_execution_audit_csv",
    "review_workspace_execution_audit_export_payloads",
    "review_workspace_execution_audit_from_mapping",
    "review_workspace_execution_audit_json",
    "review_workspace_execution_audit_schema",
]
