"""Authenticated deployment profiles and an exportable request audit ledger.

The core runtime remains local-first, but a loopback HTTP server is not an
institutional deployment boundary.  This module makes that boundary explicit:
non-loopback profiles require API-key authentication, TLS intent, auditing, and
at least one declared principal.  Credentials are accepted only at process
startup, immediately reduced to in-memory digests, and never enter a public
profile or audit projection.

This is an access and accountability boundary, not an identity provider.  It
does not claim clinical authorization, institutional approval, or scientific
validity.
"""

from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import os
import tempfile
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty

DEPLOYMENT_PROFILE_VERSION = "deployment-profile-v1"
DEPLOYMENT_AUDIT_VERSION = "deployment-audit-v1"
DEPLOYMENT_PROFILE_SCHEMA_VERSION = "deployment-profile-schema-v1"
DEPLOYMENT_AUDIT_FILENAME = "deployment-audit.json"
DEPLOYMENT_DEFAULT_RATE_LIMIT_PER_MINUTE = 60
DEPLOYMENT_MAX_RATE_LIMIT_PER_MINUTE = 10_000
DEPLOYMENT_DEFAULT_AUDIT_RETENTION_LIMIT = 100_000
DEPLOYMENT_MAX_AUDIT_RETENTION_LIMIT = 1_000_000
DEPLOYMENT_DEFAULT_PUBLIC_PATHS = ("/healthz", "/v1/deployment/profile")
DEPLOYMENT_ALL_SCOPES = ("audit", "read", "review", "write")


class DeploymentExposure(StrEnum):
    """Network exposure class used by the deployment gate."""

    LOOPBACK = "loopback"
    PRIVATE_NETWORK = "private_network"
    PUBLIC_NETWORK = "public_network"


class DeploymentAuthentication(StrEnum):
    """Supported dependency-free authentication modes."""

    NONE = "none"
    API_KEY = "api_key"


class DeploymentOperation(StrEnum):
    """Minimum scope required for a request class."""

    READ = "read"
    WRITE = "write"
    REVIEW = "review"
    AUDIT = "audit"


class DeploymentDecision(StrEnum):
    """Authorization result retained in the audit ledger."""

    ALLOWED = "allowed"
    DENIED = "denied"


def _text(value: Any, field: str) -> str:
    return require_non_empty(str(value), field)


def _unique_texts(values: Sequence[Any], field: str) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        item = _text(value, field)
        if item not in result:
            result.append(item)
    return tuple(sorted(result))


def _addressed(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(body, prefix=prefix)


def _atomic_json_write(destination: Path, value: Mapping[str, Any]) -> None:
    """Durably replace one JSON object without exposing partial audit state."""

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=str(destination.parent),
    )
    temporary = Path(temporary_name)
    try:
        payload = json.dumps(
            jsonable(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8") + b"\n"
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except BaseException as exc:
        try:
            temporary.unlink(missing_ok=True)
        finally:
            if isinstance(exc, (OSError, UnicodeError, TypeError, ValueError)):
                raise ValidationError("deployment audit store write failed") from exc
            raise


def api_key_digest(api_key: str) -> str:
    """Reduce a startup credential to a non-secret comparison digest."""

    if not isinstance(api_key, str) or len(api_key) < 16:
        raise ValidationError("deployment API keys must be at least 16 characters")
    return "sha256:" + hashlib.sha256(api_key.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class DeploymentPrincipal:
    """Public principal descriptor; no credential material is retained."""

    principal_id: str
    role: str
    scopes: tuple[str, ...]
    credential_id: str
    enabled: bool
    content_address: str

    def __post_init__(self) -> None:
        _text(self.principal_id, "principal_id")
        _text(self.role, "role")
        _text(self.credential_id, "credential_id")
        if not self.scopes:
            raise ValidationError("deployment principal must declare at least one scope")
        if any(scope not in DEPLOYMENT_ALL_SCOPES for scope in self.scopes):
            raise ValidationError("deployment principal contains an unsupported scope")
        if len(set(self.scopes)) != len(self.scopes):
            raise ValidationError("deployment principal scopes must be unique")
        if not self.content_address:
            raise ValidationError("deployment principal content address is required")

    def body(self) -> dict[str, Any]:
        return {
            "principal_id": self.principal_id,
            "role": self.role,
            "scopes": self.scopes,
            "credential_id": self.credential_id,
            "enabled": self.enabled,
        }

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_deployment_principal(
    principal_id: str,
    *,
    role: str = "operator",
    scopes: Sequence[str] = DEPLOYMENT_ALL_SCOPES,
    credential_id: str | None = None,
    enabled: bool = True,
) -> DeploymentPrincipal:
    """Build a public principal descriptor without accepting a secret."""

    normalized_scopes = _unique_texts(scopes, "scope")
    body = {
        "principal_id": _text(principal_id, "principal_id"),
        "role": _text(role, "role"),
        "scopes": normalized_scopes,
        "credential_id": _text(credential_id or f"{principal_id}:api-key", "credential_id"),
        "enabled": bool(enabled),
    }
    return DeploymentPrincipal(**body, content_address=_addressed(body, "deployment-principal"))


def _principal_address(principal: DeploymentPrincipal) -> str:
    return _addressed(principal.body(), "deployment-principal")


@dataclass(frozen=True, slots=True)
class DeploymentProfile:
    """Validated public deployment policy and principal inventory."""

    profile_id: str
    version: str
    host: str
    exposure: DeploymentExposure
    authentication: DeploymentAuthentication
    tls_required: bool
    audit_enabled: bool
    rate_limit_per_minute: int
    public_paths: tuple[str, ...]
    principals: tuple[DeploymentPrincipal, ...]
    content_address: str

    def __post_init__(self) -> None:
        issues = deployment_profile_issues(self)
        if issues:
            raise ValidationError("invalid deployment profile: " + "; ".join(issues))

    @property
    def accepted(self) -> bool:
        return not deployment_profile_issues(self)

    @property
    def principal_ids(self) -> tuple[str, ...]:
        return tuple(item.principal_id for item in self.principals)

    def body(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "version": self.version,
            "host": self.host,
            "exposure": self.exposure,
            "authentication": self.authentication,
            "tls_required": self.tls_required,
            "audit_enabled": self.audit_enabled,
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "public_paths": self.public_paths,
            "principals": self.principals,
        }

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self.body() | {"content_address": self.content_address})


def deployment_profile_issues(profile: DeploymentProfile) -> tuple[str, ...]:
    """Return every profile policy failure without exposing credentials."""

    issues: list[str] = []
    if profile.version != DEPLOYMENT_PROFILE_VERSION:
        issues.append("unsupported_version")
    if not profile.profile_id.strip():
        issues.append("missing_profile_id")
    if not profile.host.strip() or any(char.isspace() for char in profile.host):
        issues.append("invalid_host")
    if profile.rate_limit_per_minute < 1 or profile.rate_limit_per_minute > DEPLOYMENT_MAX_RATE_LIMIT_PER_MINUTE:
        issues.append("invalid_rate_limit")
    if not profile.public_paths or any(
        not path.startswith("/") or ".." in path for path in profile.public_paths
    ):
        issues.append("invalid_public_paths")
    principal_ids = [item.principal_id for item in profile.principals]
    if len(principal_ids) != len(set(principal_ids)):
        issues.append("duplicate_principals")
    if profile.authentication is DeploymentAuthentication.API_KEY and not profile.principals:
        issues.append("api_key_requires_principal")
    if profile.authentication is DeploymentAuthentication.API_KEY and not any(item.enabled for item in profile.principals):
        issues.append("api_key_requires_enabled_principal")
    if profile.exposure is not DeploymentExposure.LOOPBACK:
        if profile.authentication is not DeploymentAuthentication.API_KEY:
            issues.append("non_loopback_requires_api_key")
        if not profile.tls_required:
            issues.append("non_loopback_requires_tls")
        if not profile.audit_enabled:
            issues.append("non_loopback_requires_audit")
        if not profile.principals:
            issues.append("non_loopback_requires_principal")
        if not any(item.enabled for item in profile.principals):
            issues.append("non_loopback_requires_enabled_principal")
    if profile.authentication is DeploymentAuthentication.NONE and profile.principals:
        issues.append("none_auth_cannot_declare_principals")
    return tuple(issues)


def _profile_address(profile: DeploymentProfile) -> str:
    return _addressed(profile.body(), "deployment-profile")


def build_deployment_profile(
    profile_id: str = "glio-noncode-local",
    *,
    host: str = "127.0.0.1",
    exposure: DeploymentExposure | str | None = None,
    authentication: DeploymentAuthentication | str | None = None,
    tls_required: bool | None = None,
    audit_enabled: bool = True,
    rate_limit_per_minute: int = DEPLOYMENT_DEFAULT_RATE_LIMIT_PER_MINUTE,
    public_paths: Sequence[str] = DEPLOYMENT_DEFAULT_PUBLIC_PATHS,
    principals: Sequence[DeploymentPrincipal] = (),
) -> DeploymentProfile:
    """Create a profile whose address is derived from its public policy."""

    loopback = host in {"127.0.0.1", "localhost", "::1"}
    selected_exposure = DeploymentExposure(exposure or (DeploymentExposure.LOOPBACK if loopback else DeploymentExposure.PRIVATE_NETWORK))
    selected_authentication = DeploymentAuthentication(
        authentication or (DeploymentAuthentication.NONE if loopback else DeploymentAuthentication.API_KEY)
    )
    selected_tls = bool(tls_required) if tls_required is not None else not loopback
    body = {
        "profile_id": _text(profile_id, "profile_id"),
        "version": DEPLOYMENT_PROFILE_VERSION,
        "host": _text(host, "host"),
        "exposure": selected_exposure,
        "authentication": selected_authentication,
        "tls_required": selected_tls,
        "audit_enabled": bool(audit_enabled),
        "rate_limit_per_minute": int(rate_limit_per_minute),
        "public_paths": _unique_texts(public_paths, "public_path"),
        "principals": tuple(principals),
    }
    provisional = DeploymentProfile(**body, content_address="deployment-profile:provisional")
    return replace(provisional, content_address=_profile_address(provisional))


def default_deployment_profile(host: str = "127.0.0.1") -> DeploymentProfile:
    """Build the safe default for the requested bind address."""

    return build_deployment_profile(host=host)


def deployment_profile_from_dict(value: Mapping[str, Any]) -> DeploymentProfile:
    """Reopen a public profile and verify its content address."""

    raw_principals = value.get("principals", ())
    if not isinstance(raw_principals, list):
        raise ValidationError("deployment profile principals must be an array")
    principals = tuple(
        DeploymentPrincipal(
            principal_id=str(item.get("principal_id", "")),
            role=str(item.get("role", "")),
            scopes=tuple(str(scope) for scope in item.get("scopes", ())),
            credential_id=str(item.get("credential_id", "")),
            enabled=bool(item.get("enabled", False)),
            content_address=str(item.get("content_address", "")),
        )
        for item in raw_principals
        if isinstance(item, Mapping)
    )
    if any(item.content_address != _principal_address(item) for item in principals):
        raise ValidationError("deployment principal content address does not match its policy")
    profile = DeploymentProfile(
        profile_id=str(value.get("profile_id", "")),
        version=str(value.get("version", "")),
        host=str(value.get("host", "")),
        exposure=DeploymentExposure(str(value.get("exposure", ""))),
        authentication=DeploymentAuthentication(str(value.get("authentication", ""))),
        tls_required=bool(value.get("tls_required", False)),
        audit_enabled=bool(value.get("audit_enabled", False)),
        rate_limit_per_minute=int(value.get("rate_limit_per_minute", 0)),
        public_paths=tuple(str(item) for item in value.get("public_paths", ())),
        principals=principals,
        content_address=str(value.get("content_address", "")),
    )
    if profile.content_address != _profile_address(profile):
        raise ValidationError("deployment profile content address does not match its policy")
    return profile


def deployment_profile_schema() -> dict[str, Any]:
    """Return the closed public JSON schema for deployment profiles."""

    body: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": DEPLOYMENT_PROFILE_SCHEMA_VERSION,
        "type": "object",
        "additionalProperties": False,
        "required": [
            "profile_id",
            "version",
            "host",
            "exposure",
            "authentication",
            "tls_required",
            "audit_enabled",
            "rate_limit_per_minute",
            "public_paths",
            "principals",
            "content_address",
        ],
        "properties": {
            "profile_id": {"type": "string", "minLength": 1},
            "version": {"const": DEPLOYMENT_PROFILE_VERSION},
            "host": {"type": "string", "minLength": 1},
            "exposure": {"enum": [item.value for item in DeploymentExposure]},
            "authentication": {"enum": [item.value for item in DeploymentAuthentication]},
            "tls_required": {"type": "boolean"},
            "audit_enabled": {"type": "boolean"},
            "rate_limit_per_minute": {"type": "integer", "minimum": 1, "maximum": DEPLOYMENT_MAX_RATE_LIMIT_PER_MINUTE},
            "public_paths": {"type": "array", "items": {"type": "string", "pattern": "^/"}, "minItems": 1},
            "principals": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["principal_id", "role", "scopes", "credential_id", "enabled", "content_address"],
                    "properties": {
                        "principal_id": {"type": "string", "minLength": 1},
                        "role": {"type": "string", "minLength": 1},
                        "scopes": {"type": "array", "items": {"enum": list(DEPLOYMENT_ALL_SCOPES)}, "minItems": 1},
                        "credential_id": {"type": "string", "minLength": 1},
                        "enabled": {"type": "boolean"},
                        "content_address": {"type": "string", "minLength": 1},
                    },
                },
            },
            "content_address": {"type": "string", "minLength": 1},
        },
    }
    return body | {"content_address": _addressed(body, "deployment-profile-schema")}


@dataclass(frozen=True, slots=True)
class DeploymentAuthorization:
    """Public authorization result for one request."""

    decision: DeploymentDecision
    operation: DeploymentOperation
    principal_id: str
    role: str
    reason: str
    audit_sequence: int
    content_address: str

    @property
    def allowed(self) -> bool:
        return self.decision is DeploymentDecision.ALLOWED

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentAuditEvent:
    """One redacted, hash-chained request decision."""

    sequence: int
    observed_at: str
    method: str
    path: str
    operation: DeploymentOperation
    principal_id: str
    role: str
    decision: DeploymentDecision
    reason: str
    previous_address: str
    content_address: str

    def body(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "observed_at": self.observed_at,
            "method": self.method,
            "path": self.path,
            "operation": self.operation,
            "principal_id": self.principal_id,
            "role": self.role,
            "decision": self.decision,
            "reason": self.reason,
            "previous_address": self.previous_address,
        }

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self.body() | {"content_address": self.content_address})


@dataclass(frozen=True, slots=True)
class DeploymentAuditLog:
    """Immutable public request ledger suitable for offline export."""

    version: str
    profile_id: str
    events: tuple[DeploymentAuditEvent, ...]
    accepted: bool
    content_address: str

    @property
    def event_count(self) -> int:
        return len(self.events)

    @property
    def denied_count(self) -> int:
        return sum(item.decision is DeploymentDecision.DENIED for item in self.events)

    def body(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "profile_id": self.profile_id,
            "events": self.events,
            "accepted": self.accepted,
        }

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self.body() | {"content_address": self.content_address}) | {
            "event_count": self.event_count,
            "denied_count": self.denied_count,
        }


def _event_address(event: DeploymentAuditEvent) -> str:
    return _addressed(event.body(), "deployment-audit-event")


def build_deployment_audit_log(
    profile_id: str,
    events: Sequence[DeploymentAuditEvent] = (),
) -> DeploymentAuditLog:
    """Build an immutable ledger after checking its event chain."""

    normalized = tuple(events)
    issues = verify_deployment_audit_events(normalized)
    body = {
        "version": DEPLOYMENT_AUDIT_VERSION,
        "profile_id": _text(profile_id, "profile_id"),
        "events": normalized,
        "accepted": not issues,
    }
    provisional = DeploymentAuditLog(**body, content_address="deployment-audit:provisional")
    return replace(provisional, content_address=_addressed(provisional.body(), "deployment-audit"))


def verify_deployment_audit_events(events: Sequence[DeploymentAuditEvent]) -> tuple[str, ...]:
    """Verify sequence, redaction, previous-address, and event addresses."""

    issues: list[str] = []
    previous = "deployment-audit:genesis"
    for expected_sequence, event in enumerate(events, start=1):
        if event.sequence != expected_sequence:
            issues.append(f"sequence:{event.sequence}")
        if event.previous_address != previous:
            issues.append(f"previous-address:{event.sequence}")
        if event.content_address != _event_address(event):
            issues.append(f"content-address:{event.sequence}")
        if event.reason not in {
            "allowed",
            "public_path",
            "loopback_policy",
            "missing_or_invalid_credential",
            "scope_denied",
            "scope_allowed",
            "rate_limit_exceeded",
        }:
            issues.append(f"reason:{event.sequence}")
        previous = event.content_address
    return tuple(issues)


def verify_deployment_audit_log(log: DeploymentAuditLog) -> tuple[str, ...]:
    """Return all independent audit-log failures."""

    issues = list(verify_deployment_audit_events(log.events))
    if log.version != DEPLOYMENT_AUDIT_VERSION:
        issues.append("version")
    if not log.profile_id.strip():
        issues.append("profile-id")
    if log.accepted != (not issues):
        issues.append("accepted-state")
    expected = _addressed(log.body(), "deployment-audit")
    if log.content_address != expected:
        issues.append("content-address:log")
    return tuple(issues)


def deployment_audit_log_from_dict(value: Mapping[str, Any]) -> DeploymentAuditLog:
    raw_events = value.get("events", ())
    if not isinstance(raw_events, list):
        raise ValidationError("deployment audit events must be an array")
    events = tuple(
        DeploymentAuditEvent(
            sequence=int(item.get("sequence", 0)),
            observed_at=str(item.get("observed_at", "")),
            method=str(item.get("method", "")),
            path=str(item.get("path", "")),
            operation=DeploymentOperation(str(item.get("operation", ""))),
            principal_id=str(item.get("principal_id", "")),
            role=str(item.get("role", "")),
            decision=DeploymentDecision(str(item.get("decision", ""))),
            reason=str(item.get("reason", "")),
            previous_address=str(item.get("previous_address", "")),
            content_address=str(item.get("content_address", "")),
        )
        for item in raw_events
        if isinstance(item, Mapping)
    )
    log = DeploymentAuditLog(
        version=str(value.get("version", "")),
        profile_id=str(value.get("profile_id", "")),
        events=events,
        accepted=bool(value.get("accepted", False)),
        content_address=str(value.get("content_address", "")),
    )
    issues = verify_deployment_audit_log(log)
    if issues:
        raise ValidationError("invalid deployment audit log: " + ", ".join(issues))
    return log


@dataclass(frozen=True, slots=True)
class DeploymentAuditStoreStatus:
    """Addressed status for a durable audit directory."""

    profile_id: str
    file_name: str
    durable: bool
    event_count: int
    retention_limit: int
    remaining_capacity: int
    blocked: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class DeploymentAuditStore:
    """Atomic append-only storage for one profile's redacted audit chain."""

    def __init__(
        self,
        root: str | Path,
        profile_id: str,
        *,
        retention_limit: int = DEPLOYMENT_DEFAULT_AUDIT_RETENTION_LIMIT,
    ) -> None:
        if retention_limit < 1 or retention_limit > DEPLOYMENT_MAX_AUDIT_RETENTION_LIMIT:
            raise ValidationError("deployment audit retention limit is outside the supported range")
        self.root = Path(root)
        if self.root.exists() and self.root.is_symlink():
            raise ValidationError("deployment audit root cannot be a symlink")
        try:
            self.root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ValidationError("cannot create deployment audit root") from exc
        if not self.root.is_dir():
            raise ValidationError("deployment audit root must be a directory")
        self.path = self.root / DEPLOYMENT_AUDIT_FILENAME
        if self.path.is_symlink():
            raise ValidationError("deployment audit file cannot be a symlink")
        self.profile_id = _text(profile_id, "profile_id")
        self.retention_limit = retention_limit
        self._lock = threading.RLock()
        self._events: tuple[DeploymentAuditEvent, ...] = ()
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValidationError("deployment audit file cannot be decoded") from exc
        if not isinstance(value, Mapping):
            raise ValidationError("deployment audit file must contain an object")
        log = deployment_audit_log_from_dict(value)
        if log.profile_id != self.profile_id:
            raise ValidationError("deployment audit profile does not match the deployment profile")
        if len(log.events) > self.retention_limit:
            raise ValidationError("deployment audit history exceeds its retention limit")
        if value.get("event_count", log.event_count) != log.event_count:
            raise ValidationError("deployment audit event count does not match its events")
        if value.get("denied_count", log.denied_count) != log.denied_count:
            raise ValidationError("deployment audit denied count does not match its events")
        self._events = log.events

    @property
    def events(self) -> tuple[DeploymentAuditEvent, ...]:
        with self._lock:
            return self._events

    @property
    def audit_log(self) -> DeploymentAuditLog:
        with self._lock:
            return build_deployment_audit_log(self.profile_id, self._events)

    @property
    def status(self) -> DeploymentAuditStoreStatus:
        with self._lock:
            body = {
                "profile_id": self.profile_id,
                "file_name": DEPLOYMENT_AUDIT_FILENAME,
                "durable": True,
                "event_count": len(self._events),
                "retention_limit": self.retention_limit,
                "remaining_capacity": max(self.retention_limit - len(self._events), 0),
                "blocked": len(self._events) >= self.retention_limit,
            }
            return DeploymentAuditStoreStatus(
                **body,
                content_address=_addressed(body, "deployment-audit-store-status"),
            )

    def append(self, event: DeploymentAuditEvent) -> DeploymentAuditLog:
        """Persist one next event, refusing to delete history at capacity."""

        with self._lock:
            if len(self._events) >= self.retention_limit:
                raise ValidationError("deployment audit retention limit reached")
            expected_sequence = len(self._events) + 1
            previous_address = self._events[-1].content_address if self._events else "deployment-audit:genesis"
            if event.sequence != expected_sequence or event.previous_address != previous_address:
                raise ValidationError("deployment audit event is not the next chain event")
            candidate = build_deployment_audit_log(self.profile_id, (*self._events, event))
            _atomic_json_write(self.path, candidate.to_dict())
            self._events = candidate.events
            return candidate


def deployment_audit_csv(log: DeploymentAuditLog) -> str:
    """Export redacted events with stable columns."""

    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("sequence", "observed_at", "method", "path", "operation", "principal_id", "role", "decision", "reason", "previous_address", "content_address"))
    for event in log.events:
        writer.writerow((event.sequence, event.observed_at, event.method, event.path, event.operation.value, event.principal_id, event.role, event.decision.value, event.reason, event.previous_address, event.content_address))
    return output.getvalue()


def deployment_audit_markdown(log: DeploymentAuditLog) -> str:
    """Render a reviewer-facing, credential-free audit summary."""

    lines = [
        "# Deployment Audit",
        "",
        f"- Profile: `{log.profile_id}`",
        f"- Events: `{log.event_count}`",
        f"- Denied: `{log.denied_count}`",
        f"- Accepted chain: `{str(log.accepted).lower()}`",
        f"- Content address: `{log.content_address}`",
        "",
        "| Sequence | Method | Path | Principal | Operation | Decision | Reason |",
        "| ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for event in log.events:
        cells = (
            str(event.sequence),
            event.method,
            event.path,
            event.principal_id,
            event.operation.value,
            event.decision.value,
            event.reason.replace("|", "\\|"),
        )
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def _operation_for_request(method: str, path: str) -> DeploymentOperation:
    normalized_method = method.upper()
    normalized_path = path.split("?", 1)[0]
    if "/audit" in normalized_path:
        return DeploymentOperation.AUDIT
    if "/review" in normalized_path or "/assignment" in normalized_path:
        return DeploymentOperation.REVIEW
    return DeploymentOperation.READ if normalized_method in {"GET", "HEAD", "OPTIONS"} else DeploymentOperation.WRITE


class DeploymentGuard:
    """Thread-safe request gate with redacted hash-chained audit events."""

    def __init__(
        self,
        profile: DeploymentProfile,
        credentials: Mapping[str, str] | None = None,
        *,
        audit_store: DeploymentAuditStore | None = None,
    ) -> None:
        if not profile.accepted:
            raise ValidationError("deployment profile is not accepted")
        supplied = credentials or {}
        self.profile = profile
        self._credential_digests = {
            str(principal_id): api_key_digest(str(secret))
            for principal_id, secret in supplied.items()
        }
        unknown = tuple(sorted(set(self._credential_digests) - set(profile.principal_ids)))
        if unknown:
            raise ValidationError("credentials reference unknown principals: " + ", ".join(unknown))
        if profile.authentication is DeploymentAuthentication.API_KEY:
            missing = tuple(
                item.principal_id
                for item in profile.principals
                if item.enabled and item.principal_id not in self._credential_digests
            )
            if missing:
                raise ValidationError("missing deployment credentials for: " + ", ".join(missing))
        if audit_store is not None and audit_store.profile_id != profile.profile_id:
            raise ValidationError("deployment audit store profile does not match the deployment profile")
        self._audit_store = audit_store
        self._audit_store_error: str | None = None
        self._events: list[DeploymentAuditEvent] = list(audit_store.events if audit_store else ())
        self._rate_windows: dict[tuple[str, int], int] = {}
        self._lock = threading.Lock()

    @property
    def audit_log(self) -> DeploymentAuditLog:
        with self._lock:
            return build_deployment_audit_log(self.profile.profile_id, tuple(self._events))

    @property
    def audit_store_status(self) -> dict[str, Any]:
        with self._lock:
            if self._audit_store is None:
                return {
                    "mode": "memory",
                    "durable": False,
                    "event_count": len(self._events),
                    "blocked": self._audit_store_error is not None,
                    "content_address": content_hash(
                        {"mode": "memory", "event_count": len(self._events)},
                        prefix="deployment-audit-store-status",
                    ),
                }
            status = self._audit_store.status.to_dict()
            status["write_blocked"] = self._audit_store_error is not None
            status["mode"] = "durable"
            status["content_address"] = content_hash(
                {key: value for key, value in status.items() if key != "content_address"},
                prefix="deployment-audit-store-status",
            )
            return status

    def _principal_for_token(self, token: str | None) -> DeploymentPrincipal | None:
        if not token:
            return None
        try:
            digest = api_key_digest(token)
        except ValidationError:
            return None
        for principal in self.profile.principals:
            expected = self._credential_digests.get(principal.principal_id)
            if expected and hmac.compare_digest(expected, digest) and principal.enabled:
                return principal
        return None

    def authorize(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        observed_at: datetime | None = None,
    ) -> DeploymentAuthorization:
        """Authorize one request and append only redacted public metadata."""

        operation = _operation_for_request(method, path)
        normalized_path = path.split("?", 1)[0]
        principal = self._principal_for_token(token) if self.profile.authentication is DeploymentAuthentication.API_KEY else None
        principal_id = principal.principal_id if principal else ("local-loopback" if self.profile.authentication is DeploymentAuthentication.NONE else "anonymous")
        role = principal.role if principal else ("local_operator" if self.profile.authentication is DeploymentAuthentication.NONE else "anonymous")
        reason = "allowed"
        allowed = False
        if normalized_path in self.profile.public_paths:
            allowed = True
            reason = "public_path"
        elif self.profile.authentication is DeploymentAuthentication.NONE:
            allowed = True
            reason = "loopback_policy"
        elif principal is None:
            reason = "missing_or_invalid_credential"
        elif operation.value not in principal.scopes:
            reason = "scope_denied"
        else:
            allowed = True
            reason = "scope_allowed"
        if self._audit_store_error is not None:
            allowed = False
            reason = "audit_store_blocked"

        def authorization_result(decision: DeploymentDecision, result_reason: str, result_sequence: int) -> DeploymentAuthorization:
            return DeploymentAuthorization(
                decision=decision,
                operation=operation,
                principal_id=principal_id,
                role=role,
                reason=result_reason,
                audit_sequence=result_sequence,
                content_address=content_hash(
                    {
                        "decision": decision,
                        "operation": operation,
                        "principal_id": principal_id,
                        "role": role,
                        "reason": result_reason,
                        "audit_sequence": result_sequence,
                    },
                    prefix="deployment-authorization",
                ),
            )

        current_time = observed_at or datetime.now(timezone.utc)
        timestamp = current_time.astimezone(timezone.utc).isoformat()
        bucket = int(current_time.timestamp()) // 60
        with self._lock:
            window_key = (principal_id, bucket)
            for key in tuple(self._rate_windows):
                if key[0] == principal_id and key[1] < bucket - 1:
                    del self._rate_windows[key]
            count = self._rate_windows.get(window_key, 0)
            if allowed and count >= self.profile.rate_limit_per_minute:
                allowed = False
                reason = "rate_limit_exceeded"
            self._rate_windows[window_key] = count + 1
            sequence = len(self._events) + 1
            previous = self._events[-1].content_address if self._events else "deployment-audit:genesis"
            event_body = {
                "sequence": sequence,
                "observed_at": timestamp,
                "method": method.upper(),
                "path": normalized_path,
                "operation": operation,
                "principal_id": principal_id,
                "role": role,
                "decision": DeploymentDecision.ALLOWED if allowed else DeploymentDecision.DENIED,
                "reason": reason,
                "previous_address": previous,
            }
            event = DeploymentAuditEvent(
                **event_body,
                content_address=_addressed(event_body, "deployment-audit-event"),
            )
            if self._audit_store is not None:
                try:
                    self._audit_store.append(event)
                except ValidationError:
                    self._audit_store_error = "audit_store_blocked"
                    return authorization_result(DeploymentDecision.DENIED, "audit_store_blocked", sequence)
            self._events.append(event)
        return authorization_result(event.decision, event.reason, sequence)


def load_deployment_credentials(path: str) -> dict[str, str]:
    """Load credentials without ever serializing them into a public artifact."""

    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = handle.read().strip()
    except OSError as exc:
        raise ValidationError(f"cannot read deployment credential file: {exc}") from exc
    if not raw:
        raise ValidationError("deployment credential file is empty")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {"default": raw}
    if not isinstance(value, Mapping):
        raise ValidationError("deployment credential JSON must be an object")
    return {str(key): str(secret) for key, secret in value.items()}


__all__ = [
    "DEPLOYMENT_ALL_SCOPES",
    "DEPLOYMENT_AUDIT_FILENAME",
    "DEPLOYMENT_AUDIT_VERSION",
    "DEPLOYMENT_DEFAULT_AUDIT_RETENTION_LIMIT",
    "DEPLOYMENT_DEFAULT_PUBLIC_PATHS",
    "DEPLOYMENT_DEFAULT_RATE_LIMIT_PER_MINUTE",
    "DEPLOYMENT_MAX_AUDIT_RETENTION_LIMIT",
    "DEPLOYMENT_MAX_RATE_LIMIT_PER_MINUTE",
    "DEPLOYMENT_PROFILE_SCHEMA_VERSION",
    "DEPLOYMENT_PROFILE_VERSION",
    "DeploymentAuthentication",
    "DeploymentAuthorization",
    "DeploymentAuditEvent",
    "DeploymentAuditLog",
    "DeploymentAuditStore",
    "DeploymentAuditStoreStatus",
    "DeploymentDecision",
    "DeploymentExposure",
    "DeploymentGuard",
    "DeploymentOperation",
    "DeploymentPrincipal",
    "DeploymentProfile",
    "api_key_digest",
    "build_deployment_audit_log",
    "build_deployment_principal",
    "build_deployment_profile",
    "default_deployment_profile",
    "deployment_audit_csv",
    "deployment_audit_log_from_dict",
    "deployment_audit_markdown",
    "deployment_profile_from_dict",
    "deployment_profile_issues",
    "deployment_profile_schema",
    "load_deployment_credentials",
    "verify_deployment_audit_events",
    "verify_deployment_audit_log",
]
