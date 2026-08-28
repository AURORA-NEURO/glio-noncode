"""Independent release assurance and gating for registry federations.

This boundary consumes a verified release-registry federation and produces a
reviewable release decision without trusting the federation's own aggregate
decision.  It recomputes source receipts, conservation, state coherence,
public-boundary closure, and runtime acceptance, then applies a separate
promote/hold/block gate.  The output is intentionally path-free and contains
only stable addresses and bounded explanations.

The module is transport-oriented rather than scientific.  It does not merge
or reinterpret the underlying release payloads; it records whether the
already-addressed federation closure is safe for the next review boundary.
"""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Any

from . import assurance_history_series_release_registry_federation as federation_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes

VERSION = federation_model.VERSION + "-gate-v1"
BOUNDARY = federation_model.BOUNDARY + "_gate"
PREFIX = federation_model.PREFIX + "-gate"
ASSURANCE_PREFIX = PREFIX + "-assurance"
FINDING_PREFIX = ASSURANCE_PREFIX + "-finding"
CHECK_PREFIX = PREFIX + "-check"
QUERY_PREFIX = PREFIX + "-query"
MANIFEST_PREFIX = PREFIX + "-manifest"

MANIFEST_NAME = "manifest.json"
ASSURANCE_NAME = "assurance.json"
GATE_NAME = "gate.json"
FILES = (MANIFEST_NAME, ASSURANCE_NAME, GATE_NAME)
DEFAULT_GATE_ID = "glio-noncode-decision-assurance-history-series-release-registry-federation-gate"
MAX_FINDINGS = 32
MAX_CHECKS = 16
MAX_QUERY_ITEMS = 4096

_FORBIDDEN_KEYS = frozenset(
    {
        "agent",
        "assistant",
        "author",
        "email",
        "generated_by",
        "language",
        "model",
        "private",
        "secret",
        "token",
        "user",
    }
)


class GateState(StrEnum):
    PROMOTE = "promote"
    HOLD = "hold"
    BLOCK = "block"


class FindingSeverity(StrEnum):
    BLOCKER = "blocker"
    WARNING = "warning"


class GatePlane(StrEnum):
    SOURCE = "source"
    VERIFICATION = "verification"
    POLICY = "policy"
    RUNTIME = "runtime"
    BOUNDARY = "boundary"
    TRANSPORT = "transport"


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value.strip()


def _address(value: Any, field: str) -> str:
    value = _text(value, field, 1024)
    if ":" not in value or value.startswith(":") or value.endswith(":"):
        raise ValidationError(f"{field} must be a content address")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _count(value: Any, field: str, maximum: int = MAX_QUERY_ITEMS) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside its bounded range")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _mapping_sequence(value: Any, field: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, (list, tuple)):
        raise ValidationError(f"{field} must be an array")
    return tuple(_mapping(item, field) for item in value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unknown fields: {sorted(unknown)}")


def _required(value: Mapping[str, Any], required: set[str], field: str) -> None:
    missing = required - set(value)
    if missing:
        raise ValidationError(f"{field} is missing required fields: {sorted(missing)}")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(
            str(key).casefold() not in _FORBIDDEN_KEYS and _public(key) and _public(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    return True


def _severity(value: Any, field: str = "finding severity") -> str:
    value = _text(value, field, 32)
    if value not in {item.value for item in FindingSeverity}:
        raise ValidationError(f"{field} is invalid")
    return value


def _plane(value: Any, field: str = "finding plane") -> str:
    value = _text(value, field, 32)
    if value not in {item.value for item in GatePlane}:
        raise ValidationError(f"{field} is invalid")
    return value


def _state(value: Any, field: str = "gate state") -> str:
    value = _text(value, field, 32)
    if value not in {item.value for item in GateState}:
        raise ValidationError(f"{field} is invalid")
    return value


def _file_address(name: str, raw: bytes) -> str:
    return hash_bytes(raw, prefix=f"{PREFIX}-file-{name.removesuffix('.json')}")


def _require_directory(path: Path, field: str) -> None:
    if path.is_symlink() or not path.is_dir():
        raise ValidationError(f"{field} must be a regular directory")


def _require_regular_file(path: Path, field: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise ValidationError(f"{field} must be a regular file")


def _read_json(path: Path, field: str) -> dict[str, Any]:
    _require_regular_file(path, field)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"{field} is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ValidationError(f"{field} must be a JSON object")
    return value


def _safe(call: Any) -> tuple[Any | None, bool]:
    try:
        value = call()
    except Exception:
        return None, False
    return value, True


class FederationAssuranceFinding:
    """One independently recomputed assurance finding."""

    def __init__(
        self,
        ordinal: int,
        finding_id: str,
        plane: str,
        severity: str,
        passed: bool,
        detail: str,
        evidence_address: str,
        content_address: str,
    ) -> None:
        self.ordinal, self.finding_id, self.plane = ordinal, finding_id, plane
        self.severity, self.passed, self.detail = severity, passed, detail
        self.evidence_address, self.content_address = evidence_address, content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "assurance finding ordinal", MAX_FINDINGS - 1)
        _text(self.finding_id, "assurance finding ID", 128)
        _plane(self.plane)
        _severity(self.severity)
        _bool(self.passed, "assurance finding passed")
        _text(self.detail, "assurance finding detail", 2048)
        _address(self.evidence_address, "assurance finding evidence address")
        _address(self.content_address, "assurance finding address")
        if not self.content_address.startswith("pending:") and address_finding(self) != self.content_address:
            raise ValidationError("assurance finding address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("assurance finding crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "finding_id": self.finding_id,
            "plane": self.plane,
            "severity": self.severity,
            "passed": self.passed,
            "detail": self.detail,
            "evidence_address": self.evidence_address,
            "content_address": self.content_address,
        }


def address_finding(value: FederationAssuranceFinding) -> str:
    body = value.to_dict() | {"ordinal": None, "content_address": None}
    return content_hash(body, prefix=FINDING_PREFIX)


def _make_finding(
    ordinal: int,
    finding_id: str,
    plane: str,
    severity: str,
    passed: bool,
    detail: str,
    evidence_address: str,
) -> FederationAssuranceFinding:
    body = {
        "ordinal": ordinal,
        "finding_id": finding_id,
        "plane": plane,
        "severity": severity,
        "passed": passed,
        "detail": detail,
        "evidence_address": evidence_address,
        "content_address": "pending:assurance-finding",
    }
    provisional = FederationAssuranceFinding(**body)
    body["content_address"] = address_finding(provisional)
    return FederationAssuranceFinding(**body)


class FederationAssurance:
    """Independent assurance projection for one federation bundle."""

    def __init__(
        self,
        federation_address: str,
        runtime_address: str,
        finding_count: int,
        passed_count: int,
        failed_count: int,
        blocker_count: int,
        warning_count: int,
        accepted: bool,
        release_ready: bool,
        state: str,
        findings: Sequence[FederationAssuranceFinding],
        content_address: str,
    ) -> None:
        self.federation_address, self.runtime_address = federation_address, runtime_address
        self.finding_count, self.passed_count, self.failed_count = finding_count, passed_count, failed_count
        self.blocker_count, self.warning_count = blocker_count, warning_count
        self.accepted, self.release_ready, self.state = accepted, release_ready, state
        self.findings, self.content_address = tuple(findings), content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.federation_address, "assurance federation address")
        _address(self.runtime_address, "assurance runtime address")
        for name, value in (
            ("finding", self.finding_count),
            ("passed", self.passed_count),
            ("failed", self.failed_count),
            ("blocker", self.blocker_count),
            ("warning", self.warning_count),
        ):
            _count(value, f"assurance {name} count", MAX_FINDINGS)
        _bool(self.accepted, "assurance accepted")
        _bool(self.release_ready, "assurance release-ready")
        _state(self.state, "assurance state")
        if self.finding_count != len(self.findings) or self.passed_count + self.failed_count != self.finding_count:
            raise ValidationError("assurance finding counts are not conserved")
        if self.failed_count != self.blocker_count + self.warning_count:
            raise ValidationError("assurance severity counts are not conserved")
        for ordinal, finding in enumerate(self.findings):
            if not isinstance(finding, FederationAssuranceFinding) or finding.ordinal != ordinal:
                raise ValidationError("assurance findings must have contiguous ordinals")
        if self.passed_count != sum(finding.passed for finding in self.findings):
            raise ValidationError("assurance passed count does not match findings")
        if self.failed_count != sum(not finding.passed for finding in self.findings):
            raise ValidationError("assurance failed count does not match findings")
        if self.blocker_count != sum(not finding.passed and finding.severity == FindingSeverity.BLOCKER.value for finding in self.findings):
            raise ValidationError("assurance blocker count does not match findings")
        if self.warning_count != sum(not finding.passed and finding.severity == FindingSeverity.WARNING.value for finding in self.findings):
            raise ValidationError("assurance warning count does not match findings")
        expected_state = GateState.BLOCK.value if self.blocker_count else GateState.HOLD.value if self.warning_count else GateState.PROMOTE.value
        if self.state != expected_state:
            raise ValidationError("assurance state does not match findings")
        if self.accepted != (self.blocker_count == 0):
            raise ValidationError("assurance acceptance does not match blockers")
        if self.release_ready != (self.accepted and self.warning_count == 0):
            raise ValidationError("assurance release readiness does not match warnings")
        _address(self.content_address, "assurance address")
        if not self.content_address.startswith("pending:") and address_assurance(self) != self.content_address:
            raise ValidationError("assurance address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("assurance crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "version": VERSION,
            "boundary": BOUNDARY,
            "federation_address": self.federation_address,
            "runtime_address": self.runtime_address,
            "finding_count": self.finding_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "blocker_count": self.blocker_count,
            "warning_count": self.warning_count,
            "accepted": self.accepted,
            "release_ready": self.release_ready,
            "state": self.state,
            "content_address": self.content_address,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.summary() | {"findings": [finding.to_dict() for finding in self.findings]}


def address_assurance(value: FederationAssurance) -> str:
    return content_hash(value.summary() | {"content_address": None}, prefix=ASSURANCE_PREFIX)


class FederationGateCheck:
    """One independently recomputed promote/hold/block check."""

    def __init__(
        self,
        ordinal: int,
        check_id: str,
        severity: str,
        passed: bool,
        detail: str,
        evidence_address: str,
        content_address: str,
    ) -> None:
        self.ordinal, self.check_id, self.severity = ordinal, check_id, severity
        self.passed, self.detail = passed, detail
        self.evidence_address, self.content_address = evidence_address, content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "gate check ordinal", MAX_CHECKS - 1)
        _text(self.check_id, "gate check ID", 128)
        _severity(self.severity, "gate check severity")
        _bool(self.passed, "gate check passed")
        _text(self.detail, "gate check detail", 2048)
        _address(self.evidence_address, "gate check evidence address")
        _address(self.content_address, "gate check address")
        if not self.content_address.startswith("pending:") and address_gate_check(self) != self.content_address:
            raise ValidationError("gate check address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("gate check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "check_id": self.check_id,
            "severity": self.severity,
            "passed": self.passed,
            "detail": self.detail,
            "evidence_address": self.evidence_address,
            "content_address": self.content_address,
        }


def address_gate_check(value: FederationGateCheck) -> str:
    return content_hash(value.to_dict() | {"ordinal": None, "content_address": None}, prefix=CHECK_PREFIX)


def _make_gate_check(
    ordinal: int,
    check_id: str,
    severity: str,
    passed: bool,
    detail: str,
    evidence_address: str,
) -> FederationGateCheck:
    body = {
        "ordinal": ordinal,
        "check_id": check_id,
        "severity": severity,
        "passed": passed,
        "detail": detail,
        "evidence_address": evidence_address,
        "content_address": "pending:gate-check",
    }
    provisional = FederationGateCheck(**body)
    body["content_address"] = address_gate_check(provisional)
    return FederationGateCheck(**body)


class FederationReleaseGate:
    """Independent release decision over a federation assurance report."""

    def __init__(
        self,
        gate_id: str,
        version: str,
        boundary: str,
        federation_address: str,
        runtime_address: str,
        assurance_address: str,
        state: str,
        decision: str,
        check_count: int,
        passed_count: int,
        failed_count: int,
        required_failure_count: int,
        optional_failure_count: int,
        accepted: bool,
        release_ready: bool,
        checks: Sequence[FederationGateCheck],
        content_address: str,
    ) -> None:
        self.gate_id, self.version, self.boundary = gate_id, version, boundary
        self.federation_address, self.runtime_address = federation_address, runtime_address
        self.assurance_address = assurance_address
        self.state, self.decision = state, decision
        self.check_count, self.passed_count, self.failed_count = check_count, passed_count, failed_count
        self.required_failure_count, self.optional_failure_count = required_failure_count, optional_failure_count
        self.accepted, self.release_ready = accepted, release_ready
        self.checks, self.content_address = tuple(checks), content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.gate_id, "gate ID", 256)
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("gate contract is invalid")
        _address(self.federation_address, "gate federation address")
        _address(self.runtime_address, "gate runtime address")
        _address(self.assurance_address, "gate assurance address")
        _state(self.state, "gate state")
        if self.decision != self.state:
            raise ValidationError("gate decision must equal gate state")
        for name, value in (
            ("check", self.check_count),
            ("passed", self.passed_count),
            ("failed", self.failed_count),
            ("required failure", self.required_failure_count),
            ("optional failure", self.optional_failure_count),
        ):
            _count(value, f"gate {name} count", MAX_CHECKS)
        _bool(self.accepted, "gate accepted")
        _bool(self.release_ready, "gate release-ready")
        if self.check_count != len(self.checks) or self.passed_count + self.failed_count != self.check_count:
            raise ValidationError("gate check counts are not conserved")
        if self.failed_count != self.required_failure_count + self.optional_failure_count:
            raise ValidationError("gate failure severities are not conserved")
        for ordinal, check in enumerate(self.checks):
            if not isinstance(check, FederationGateCheck) or check.ordinal != ordinal:
                raise ValidationError("gate checks must have contiguous ordinals")
        if self.passed_count != sum(check.passed for check in self.checks):
            raise ValidationError("gate passed count does not match checks")
        if self.failed_count != sum(not check.passed for check in self.checks):
            raise ValidationError("gate failed count does not match checks")
        if self.required_failure_count != sum(not check.passed and check.severity == FindingSeverity.BLOCKER.value for check in self.checks):
            raise ValidationError("gate required failure count does not match checks")
        if self.optional_failure_count != sum(not check.passed and check.severity == FindingSeverity.WARNING.value for check in self.checks):
            raise ValidationError("gate optional failure count does not match checks")
        expected_state = GateState.BLOCK.value if self.required_failure_count else GateState.HOLD.value if self.optional_failure_count else GateState.PROMOTE.value
        if self.state != expected_state:
            raise ValidationError("gate state does not match checks")
        if self.accepted != (self.required_failure_count == 0):
            raise ValidationError("gate acceptance does not match required failures")
        if self.release_ready != (self.state == GateState.PROMOTE.value and self.accepted):
            raise ValidationError("gate release readiness does not match state")
        _address(self.content_address, "gate address")
        if not self.content_address.startswith("pending:") and address_gate(self) != self.content_address:
            raise ValidationError("gate address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("gate crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "version": self.version,
            "boundary": self.boundary,
            "federation_address": self.federation_address,
            "runtime_address": self.runtime_address,
            "assurance_address": self.assurance_address,
            "state": self.state,
            "decision": self.decision,
            "check_count": self.check_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "required_failure_count": self.required_failure_count,
            "optional_failure_count": self.optional_failure_count,
            "accepted": self.accepted,
            "release_ready": self.release_ready,
            "content_address": self.content_address,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.summary() | {"checks": [check.to_dict() for check in self.checks]}


def address_gate(value: FederationReleaseGate) -> str:
    return content_hash(value.summary() | {"content_address": None}, prefix=PREFIX)


class FederationAssuranceGateBundle:
    """The assurance and release-gate documents retained for review."""

    def __init__(self, assurance: FederationAssurance, gate: FederationReleaseGate) -> None:
        self.assurance, self.gate = assurance, gate
        self._validate()

    def _validate(self) -> None:
        verify_federation_assurance(self.assurance)
        verify_federation_release_gate(self.gate)
        if self.gate.federation_address != self.assurance.federation_address or self.gate.runtime_address != self.assurance.runtime_address:
            raise ValidationError("assurance gate source linkage is invalid")
        if self.gate.assurance_address != self.assurance.content_address:
            raise ValidationError("assurance gate assurance linkage is invalid")
        if self.gate.accepted != self.assurance.accepted:
            raise ValidationError("assurance and gate acceptance are not conserved")
        if self.gate.release_ready != self.assurance.release_ready:
            raise ValidationError("assurance and gate readiness are not conserved")
        if not _public(self.to_dict()):
            raise ValidationError("assurance gate bundle crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return self.gate.summary() | {
            "assurance_state": self.assurance.state,
            "assurance_accepted": self.assurance.accepted,
            "assurance_release_ready": self.assurance.release_ready,
            "assurance_finding_count": self.assurance.finding_count,
            "assurance_failed_count": self.assurance.failed_count,
            "assurance_blocker_count": self.assurance.blocker_count,
            "assurance_warning_count": self.assurance.warning_count,
        }

    def to_dict(self) -> dict[str, Any]:
        return {"assurance": self.assurance.to_dict(), "gate": self.gate.to_dict()}


def _source_address(value: federation_model.DecisionAssuranceHistorySeriesReleaseRegistryFederationBundle) -> str:
    return value.federation.content_address


def _assurance_findings(
    value: federation_model.DecisionAssuranceHistorySeriesReleaseRegistryFederationBundle,
) -> tuple[FederationAssuranceFinding, ...]:
    source_address = _source_address(value)
    runtime_address = value.runtime.content_address
    verified, bundle_ok = _safe(lambda: federation_model.verify_federation_bundle(value))
    expected_verification, verification_ok = _safe(lambda: federation_model.build_federation_verification(value.federation))
    expected_policy, policy_ok = _safe(lambda: federation_model.build_policy_evaluation(value.federation, value.policy))
    expected_runtime, runtime_ok = _safe(
        lambda: federation_model.build_federation_runtime(
            value.federation,
            value.policy,
            expected_verification,
            expected_policy,
        )
    ) if verification_ok and policy_ok else (None, False)
    federation_address_ok = False
    if verified is not None:
        federation_address_ok = federation_model.address_federation(value.federation) == source_address
    verification_receipt_ok = expected_verification is not None and expected_verification.to_dict() == value.verification.to_dict()
    policy_receipt_ok = expected_policy is not None and expected_policy.to_dict() == value.policy_evaluation.to_dict()
    runtime_receipt_ok = expected_runtime is not None and expected_runtime.to_dict() == value.runtime.to_dict()
    package_counts_ok = (
        value.federation.package_count == sum(member.entry_count for member in value.federation.members)
        and value.federation.ready_count + value.federation.hold_count + value.federation.blocked_count == value.federation.package_count
        and value.federation.accepted_count <= value.federation.package_count
        and value.federation.release_ready_count <= value.federation.accepted_count
    )
    expected_federation_state = (
        "empty"
        if not value.federation.member_count
        else "blocked"
        if value.federation.blocked_count
        else "held"
        if value.federation.hold_count
        else "ready"
    )
    state_ok = (
        value.federation.state == expected_federation_state
        and value.runtime.accepted == (value.verification.accepted and value.policy_evaluation.accepted)
        and value.runtime.release_ready == (value.policy_evaluation.release_ready and value.runtime.accepted)
    )
    checks = (
        ("source-bundle-verified", GatePlane.SOURCE.value, FindingSeverity.BLOCKER.value, bundle_ok, "source federation bundle independently verifies", source_address),
        ("federation-address", GatePlane.SOURCE.value, FindingSeverity.BLOCKER.value, federation_address_ok, "federation content address recomputes from its public projection", source_address),
        ("verification-recomputed", GatePlane.VERIFICATION.value, FindingSeverity.BLOCKER.value, verification_receipt_ok, f"verification receipt {value.verification.content_address} recomputes from federation {source_address}", value.verification.content_address),
        ("policy-recomputed", GatePlane.POLICY.value, FindingSeverity.BLOCKER.value, policy_receipt_ok, f"policy evaluation receipt {value.policy_evaluation.content_address} recomputes from federation {source_address} and policy", value.policy_evaluation.content_address),
        ("runtime-recomputed", GatePlane.RUNTIME.value, FindingSeverity.BLOCKER.value, runtime_receipt_ok, f"runtime receipt {runtime_address} recomputes from independent verification and policy", runtime_address),
        ("runtime-accepted", GatePlane.RUNTIME.value, FindingSeverity.BLOCKER.value, value.runtime.accepted, "source runtime is accepted by its own closure", runtime_address),
        ("aggregate-counts", GatePlane.SOURCE.value, FindingSeverity.BLOCKER.value, package_counts_ok, "member, package, state, and readiness counts are conserved", source_address),
        ("state-coherent", GatePlane.RUNTIME.value, FindingSeverity.BLOCKER.value, state_ok, "source federation and runtime states agree with their projections", runtime_address),
        ("public-boundary", GatePlane.BOUNDARY.value, FindingSeverity.BLOCKER.value, _public(value.to_dict()), "federation closure contains no private transport fields", source_address),
        ("source-release-ready", GatePlane.RUNTIME.value, FindingSeverity.WARNING.value, value.runtime.release_ready, "source runtime is release-ready for promotion", runtime_address),
    )
    return tuple(_make_finding(ordinal, finding_id, plane, severity, passed, detail, evidence) for ordinal, (finding_id, plane, severity, passed, detail, evidence) in enumerate(checks))


def build_federation_assurance(
    value: federation_model.DecisionAssuranceHistorySeriesReleaseRegistryFederationBundle,
) -> FederationAssurance:
    federation_model.verify_federation_bundle(value)
    findings = _assurance_findings(value)
    blocker_count = sum(not finding.passed and finding.severity == FindingSeverity.BLOCKER.value for finding in findings)
    warning_count = sum(not finding.passed and finding.severity == FindingSeverity.WARNING.value for finding in findings)
    body = {
        "federation_address": value.federation.content_address,
        "runtime_address": value.runtime.content_address,
        "finding_count": len(findings),
        "passed_count": sum(finding.passed for finding in findings),
        "failed_count": sum(not finding.passed for finding in findings),
        "blocker_count": blocker_count,
        "warning_count": warning_count,
        "accepted": blocker_count == 0,
        "release_ready": blocker_count == 0 and warning_count == 0,
        "state": GateState.BLOCK.value if blocker_count else GateState.HOLD.value if warning_count else GateState.PROMOTE.value,
        "findings": findings,
        "content_address": "pending:federation-assurance",
    }
    provisional = FederationAssurance(**body)
    body["content_address"] = address_assurance(provisional)
    return FederationAssurance(**body)


def _gate_checks(
    value: federation_model.DecisionAssuranceHistorySeriesReleaseRegistryFederationBundle,
    assurance: FederationAssurance,
) -> tuple[FederationGateCheck, ...]:
    evidence = value.federation.content_address
    checks = (
        ("assurance-accepted", FindingSeverity.BLOCKER.value, assurance.accepted, "independent assurance has no blocker findings", assurance.content_address),
        ("assurance-no-blockers", FindingSeverity.BLOCKER.value, assurance.blocker_count == 0, "independent assurance blocker count is zero", assurance.content_address),
        ("source-runtime-accepted", FindingSeverity.BLOCKER.value, value.runtime.accepted, "source federation runtime is accepted", value.runtime.content_address),
        ("source-state-allowed", FindingSeverity.BLOCKER.value, value.runtime.state != federation_model.FederationState.BLOCKED.value, "blocked source runtime cannot be promoted", value.runtime.content_address),
        ("aggregate-counts-conserved", FindingSeverity.BLOCKER.value, value.federation.ready_count + value.federation.hold_count + value.federation.blocked_count == value.federation.package_count, "federation package state counts are conserved", evidence),
        ("public-boundary-closed", FindingSeverity.BLOCKER.value, _public(value.to_dict()), "source federation bundle remains public-boundary closed", evidence),
        ("source-release-ready", FindingSeverity.WARNING.value, value.runtime.release_ready, "source runtime reports release readiness", value.runtime.content_address),
        ("assurance-warning-free", FindingSeverity.WARNING.value, assurance.warning_count == 0, "independent assurance has no warning findings", assurance.content_address),
    )
    return tuple(_make_gate_check(ordinal, check_id, severity, passed, detail, evidence_address) for ordinal, (check_id, severity, passed, detail, evidence_address) in enumerate(checks))


def build_federation_release_gate(
    value: federation_model.DecisionAssuranceHistorySeriesReleaseRegistryFederationBundle,
    assurance: FederationAssurance,
    *,
    gate_id: str = DEFAULT_GATE_ID,
) -> FederationReleaseGate:
    federation_model.verify_federation_bundle(value)
    verify_federation_assurance(assurance)
    if assurance.federation_address != value.federation.content_address or assurance.runtime_address != value.runtime.content_address:
        raise ValidationError("assurance does not link to source federation")
    checks = _gate_checks(value, assurance)
    required_failure_count = sum(not check.passed and check.severity == FindingSeverity.BLOCKER.value for check in checks)
    optional_failure_count = sum(not check.passed and check.severity == FindingSeverity.WARNING.value for check in checks)
    state = GateState.BLOCK.value if required_failure_count else GateState.HOLD.value if optional_failure_count else GateState.PROMOTE.value
    body = {
        "gate_id": gate_id,
        "version": VERSION,
        "boundary": BOUNDARY,
        "federation_address": value.federation.content_address,
        "runtime_address": value.runtime.content_address,
        "assurance_address": assurance.content_address,
        "state": state,
        "decision": state,
        "check_count": len(checks),
        "passed_count": sum(check.passed for check in checks),
        "failed_count": sum(not check.passed for check in checks),
        "required_failure_count": required_failure_count,
        "optional_failure_count": optional_failure_count,
        "accepted": required_failure_count == 0,
        "release_ready": state == GateState.PROMOTE.value,
        "checks": checks,
        "content_address": "pending:federation-gate",
    }
    provisional = FederationReleaseGate(**body)
    body["content_address"] = address_gate(provisional)
    return FederationReleaseGate(**body)


def build_federation_assurance_gate(
    value: federation_model.DecisionAssuranceHistorySeriesReleaseRegistryFederationBundle,
    *,
    gate_id: str = DEFAULT_GATE_ID,
) -> FederationAssuranceGateBundle:
    assurance = build_federation_assurance(value)
    gate = build_federation_release_gate(value, assurance, gate_id=gate_id)
    return FederationAssuranceGateBundle(assurance, gate)


def verify_federation_assurance(value: FederationAssurance) -> FederationAssurance:
    if not isinstance(value, FederationAssurance):
        raise ValidationError("federation assurance requires a typed assurance")
    value._validate()
    if address_assurance(value) != value.content_address:
        raise ValidationError("federation assurance address mismatch")
    return value


def verify_federation_release_gate(value: FederationReleaseGate) -> FederationReleaseGate:
    if not isinstance(value, FederationReleaseGate):
        raise ValidationError("federation release gate requires a typed gate")
    value._validate()
    if address_gate(value) != value.content_address:
        raise ValidationError("federation release gate address mismatch")
    return value


def verify_federation_assurance_gate(value: FederationAssuranceGateBundle) -> FederationAssuranceGateBundle:
    if not isinstance(value, FederationAssuranceGateBundle):
        raise ValidationError("federation assurance gate requires a typed bundle")
    value._validate()
    return value


def finding_from_mapping(value: Mapping[str, Any]) -> FederationAssuranceFinding:
    body = dict(_mapping(value, "assurance finding"))
    allowed = {"ordinal", "finding_id", "plane", "severity", "passed", "detail", "evidence_address", "content_address"}
    _strict(body, allowed, "assurance finding")
    _required(body, allowed, "assurance finding")
    return FederationAssuranceFinding(**body)


def assurance_from_mapping(value: Mapping[str, Any]) -> FederationAssurance:
    body = dict(_mapping(value, "federation assurance"))
    allowed = {"version", "boundary", "federation_address", "runtime_address", "finding_count", "passed_count", "failed_count", "blocker_count", "warning_count", "accepted", "release_ready", "state", "findings", "content_address"}
    _strict(body, allowed, "federation assurance")
    _required(body, allowed, "federation assurance")
    if body.pop("version") != VERSION or body.pop("boundary") != BOUNDARY:
        raise ValidationError("federation assurance contract is invalid")
    body["findings"] = tuple(finding_from_mapping(item) for item in _mapping_sequence(body["findings"], "assurance findings"))
    return verify_federation_assurance(FederationAssurance(**body))


def gate_check_from_mapping(value: Mapping[str, Any]) -> FederationGateCheck:
    body = dict(_mapping(value, "gate check"))
    allowed = {"ordinal", "check_id", "severity", "passed", "detail", "evidence_address", "content_address"}
    _strict(body, allowed, "gate check")
    _required(body, allowed, "gate check")
    return FederationGateCheck(**body)


def gate_from_mapping(value: Mapping[str, Any]) -> FederationReleaseGate:
    body = dict(_mapping(value, "federation release gate"))
    allowed = {"gate_id", "version", "boundary", "federation_address", "runtime_address", "assurance_address", "state", "decision", "check_count", "passed_count", "failed_count", "required_failure_count", "optional_failure_count", "accepted", "release_ready", "checks", "content_address"}
    _strict(body, allowed, "federation release gate")
    _required(body, allowed, "federation release gate")
    body["checks"] = tuple(gate_check_from_mapping(item) for item in _mapping_sequence(body["checks"], "gate checks"))
    return verify_federation_release_gate(FederationReleaseGate(**body))


def assurance_gate_from_mapping(value: Mapping[str, Any]) -> FederationAssuranceGateBundle:
    body = dict(_mapping(value, "federation assurance gate"))
    allowed = {"assurance", "gate"}
    _strict(body, allowed, "federation assurance gate")
    _required(body, allowed, "federation assurance gate")
    return FederationAssuranceGateBundle(
        assurance_from_mapping(body["assurance"]),
        gate_from_mapping(body["gate"]),
    )


def assurance_json(value: FederationAssurance) -> str:
    verify_federation_assurance(value)
    return canonical_json(value.to_dict())


def gate_json(value: FederationReleaseGate) -> str:
    verify_federation_release_gate(value)
    return canonical_json(value.to_dict())


def assurance_gate_json(value: FederationAssuranceGateBundle) -> str:
    verify_federation_assurance_gate(value)
    return canonical_json(value.to_dict())


def _csv_text(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> str:
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=tuple(fields), extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def assurance_csv(value: FederationAssurance) -> str:
    verify_federation_assurance(value)
    return _csv_text(
        (finding.to_dict() for finding in value.findings),
        ("ordinal", "finding_id", "plane", "severity", "passed", "detail", "evidence_address", "content_address"),
    )


def gate_csv(value: FederationReleaseGate) -> str:
    verify_federation_release_gate(value)
    return _csv_text(
        (check.to_dict() for check in value.checks),
        ("ordinal", "check_id", "severity", "passed", "detail", "evidence_address", "content_address"),
    )


def assurance_gate_csv(value: FederationAssuranceGateBundle) -> str:
    verify_federation_assurance_gate(value)
    return gate_csv(value.gate)


def _markdown(title: str, summary: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> str:
    lines = [f"# {title}", "", "## Summary", ""]
    lines.extend(f"- **{key}:** {json.dumps(item, ensure_ascii=False, sort_keys=True)}" for key, item in summary.items())
    if rows:
        fields = tuple(rows[0].keys())
        lines.extend(("", "## Items", "", "| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"))
        lines.extend("| " + " | ".join(json.dumps(row.get(field), ensure_ascii=False, sort_keys=True) for field in fields) + " |" for row in rows)
    return "\n".join(lines) + "\n"


def render_assurance_markdown(value: FederationAssurance) -> str:
    verify_federation_assurance(value)
    return _markdown("Decision Assurance History Series Release Registry Federation Assurance", value.summary(), [finding.to_dict() for finding in value.findings])


def render_gate_markdown(value: FederationReleaseGate) -> str:
    verify_federation_release_gate(value)
    return _markdown("Decision Assurance History Series Release Registry Federation Release Gate", value.summary(), [check.to_dict() for check in value.checks])


def render_assurance_gate_markdown(value: FederationAssuranceGateBundle) -> str:
    verify_federation_assurance_gate(value)
    return _markdown("Decision Assurance History Series Release Registry Federation Assurance Gate", value.summary(), [check.to_dict() for check in value.gate.checks])


def _documents(value: FederationAssuranceGateBundle) -> dict[str, bytes]:
    verify_federation_assurance_gate(value)
    return {
        ASSURANCE_NAME: canonical_bytes(value.assurance.to_dict()),
        GATE_NAME: canonical_bytes(value.gate.to_dict()),
    }


def _manifest_body(value: FederationAssuranceGateBundle, documents: Mapping[str, bytes]) -> dict[str, Any]:
    body = {
        "version": VERSION,
        "boundary": BOUNDARY,
        "federation_address": value.gate.federation_address,
        "runtime_address": value.gate.runtime_address,
        "assurance_address": value.assurance.content_address,
        "gate_address": value.gate.content_address,
        "files": list(FILES),
        "artifact_count": len(FILES) - 1,
        "artifacts": [{"name": name, "bytes": len(documents[name]), "byte_address": _file_address(name, documents[name])} for name in FILES if name != MANIFEST_NAME],
        "content_address": "pending:federation-gate-manifest",
    }
    return body | {"content_address": content_hash(body | {"content_address": None}, prefix=MANIFEST_PREFIX)}


def _manifest_address(value: Mapping[str, Any]) -> str:
    return content_hash(dict(value) | {"content_address": None}, prefix=MANIFEST_PREFIX)


def write_federation_assurance_gate(
    value: FederationAssuranceGateBundle,
    directory: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    documents = _documents(value)
    destination = Path(directory)
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.is_symlink() or not destination.is_dir():
            raise ValidationError("federation gate destination must be a regular directory")
        if any(destination.iterdir()) and not overwrite:
            raise ValidationError("federation gate destination already exists")
    temporary = Path(tempfile.mkdtemp(prefix=".glio-federation-gate-", dir=str(parent)))
    try:
        for name, raw in documents.items():
            (temporary / name).write_bytes(raw)
        (temporary / MANIFEST_NAME).write_bytes(canonical_bytes(_manifest_body(value, documents)))
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return destination


def load_federation_assurance_gate(directory: str | Path) -> FederationAssuranceGateBundle:
    destination = Path(directory)
    _require_directory(destination, "federation gate directory")
    if {item.name for item in destination.iterdir()} != set(FILES):
        raise ValidationError("federation gate file set is invalid")
    parsed: dict[str, dict[str, Any]] = {}
    raw_documents: dict[str, bytes] = {}
    for name in FILES:
        path = destination / name
        _require_regular_file(path, f"federation gate {name}")
        raw = path.read_bytes()
        parsed[name] = _read_json(path, f"federation gate {name}")
        if raw != canonical_bytes(parsed[name]):
            raise ValidationError(f"federation gate {name} is not canonical JSON")
        raw_documents[name] = raw
    value = assurance_gate_from_mapping({"assurance": parsed[ASSURANCE_NAME], "gate": parsed[GATE_NAME]})
    manifest = parsed[MANIFEST_NAME]
    allowed = {"version", "boundary", "federation_address", "runtime_address", "assurance_address", "gate_address", "files", "artifact_count", "artifacts", "content_address"}
    _strict(manifest, allowed, "federation gate manifest")
    _required(manifest, allowed, "federation gate manifest")
    if manifest["version"] != VERSION or manifest["boundary"] != BOUNDARY or tuple(manifest["files"]) != FILES or manifest["artifact_count"] != len(FILES) - 1 or _manifest_address(manifest) != manifest["content_address"]:
        raise ValidationError("federation gate manifest contract is invalid")
    if manifest["federation_address"] != value.gate.federation_address or manifest["runtime_address"] != value.gate.runtime_address or manifest["assurance_address"] != value.assurance.content_address or manifest["gate_address"] != value.gate.content_address:
        raise ValidationError("federation gate manifest linkage is invalid")
    artifacts = _mapping_sequence(manifest["artifacts"], "federation gate artifacts")
    if len(artifacts) != len(FILES) - 1 or {item.get("name") for item in artifacts} != set(FILES) - {MANIFEST_NAME}:
        raise ValidationError("federation gate artifact set is invalid")
    for artifact in artifacts:
        _strict(artifact, {"name", "bytes", "byte_address"}, "federation gate artifact")
        name = _text(artifact["name"], "federation gate artifact name", 128)
        if artifact["bytes"] != len(raw_documents[name]) or artifact["byte_address"] != _file_address(name, raw_documents[name]):
            raise ValidationError(f"federation gate artifact receipt mismatch: {name}")
    return value


def verify_federation_assurance_gate_directory(directory: str | Path) -> FederationAssuranceGateBundle:
    return load_federation_assurance_gate(directory)


class FederationGateQuery:
    """Bounded query over assurance findings and gate checks."""

    RESOURCES = (
        "summary",
        "findings",
        "blockers",
        "warnings",
        "failed-findings",
        "checks",
        "failed-checks",
        "required-failures",
        "optional-failures",
    )

    def __init__(
        self,
        resource: str = "summary",
        *,
        plane: str | None = None,
        severity: str | None = None,
        passed: bool | None = None,
        text: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> None:
        self.resource = _text(resource, "gate query resource", 48)
        if self.resource not in self.RESOURCES:
            raise ValidationError("gate query resource is invalid")
        self.plane = None if plane is None else _plane(plane, "gate query plane")
        self.severity = None if severity is None else _severity(severity, "gate query severity")
        self.passed = None if passed is None else _bool(passed, "gate query passed")
        self.text = None if text is None else _text(text, "gate query text", 256)
        self.offset, self.limit = _count(offset, "gate query offset"), _count(limit, "gate query limit")
        if self.limit < 1:
            raise ValidationError("gate query limit must be positive")

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource": self.resource,
            "plane": self.plane,
            "severity": self.severity,
            "passed": self.passed,
            "text": self.text,
            "offset": self.offset,
            "limit": self.limit,
        }


class FederationGateQueryResult:
    def __init__(
        self,
        gate_address: str,
        assurance_address: str,
        query: FederationGateQuery,
        total_count: int,
        returned_count: int,
        items: Sequence[Mapping[str, Any]],
        content_address: str,
    ) -> None:
        self.gate_address, self.assurance_address = gate_address, assurance_address
        self.query = query
        self.total_count, self.returned_count = total_count, returned_count
        self.items, self.content_address = tuple(dict(item) for item in items), content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.gate_address, "gate query gate address")
        _address(self.assurance_address, "gate query assurance address")
        if not isinstance(self.query, FederationGateQuery):
            raise ValidationError("gate query must be typed")
        _count(self.total_count, "gate query total count", MAX_QUERY_ITEMS)
        _count(self.returned_count, "gate query returned count", MAX_QUERY_ITEMS)
        if self.returned_count != len(self.items) or self.returned_count > self.total_count or self.returned_count > self.query.limit:
            raise ValidationError("gate query counts are invalid")
        _address(self.content_address, "gate query address")
        if not self.content_address.startswith("pending:") and address_query(self) != self.content_address:
            raise ValidationError("gate query address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("gate query crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_address": self.gate_address,
            "assurance_address": self.assurance_address,
            "query": self.query.to_dict(),
            "total_count": self.total_count,
            "returned_count": self.returned_count,
            "items": list(self.items),
            "content_address": self.content_address,
        }


def address_query(value: FederationGateQueryResult) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _query_items(value: FederationAssuranceGateBundle, query: FederationGateQuery) -> list[dict[str, Any]]:
    if query.resource == "summary":
        rows = [value.summary()]
    elif query.resource in {"findings", "blockers", "warnings", "failed-findings"}:
        rows = [finding.to_dict() for finding in value.assurance.findings]
        if query.resource == "blockers":
            rows = [row for row in rows if row["severity"] == FindingSeverity.BLOCKER.value and not row["passed"]]
        elif query.resource == "warnings":
            rows = [row for row in rows if row["severity"] == FindingSeverity.WARNING.value and not row["passed"]]
        elif query.resource == "failed-findings":
            rows = [row for row in rows if not row["passed"]]
    else:
        rows = [check.to_dict() for check in value.gate.checks]
        if query.resource == "failed-checks":
            rows = [row for row in rows if not row["passed"]]
        elif query.resource == "required-failures":
            rows = [row for row in rows if not row["passed"] and row["severity"] == FindingSeverity.BLOCKER.value]
        elif query.resource == "optional-failures":
            rows = [row for row in rows if not row["passed"] and row["severity"] == FindingSeverity.WARNING.value]
    if query.plane is not None:
        rows = [row for row in rows if row.get("plane") == query.plane]
    if query.severity is not None:
        rows = [row for row in rows if row.get("severity") == query.severity]
    if query.passed is not None:
        rows = [row for row in rows if row.get("passed") is query.passed]
    if query.text:
        needle = query.text.casefold()
        rows = [row for row in rows if needle in canonical_json(row).casefold()]
    return rows


def query_federation_assurance_gate(
    value: FederationAssuranceGateBundle,
    query: FederationGateQuery | None = None,
    **kwargs: Any,
) -> FederationGateQueryResult:
    verify_federation_assurance_gate(value)
    if query is not None and kwargs:
        raise ValidationError("gate query cannot combine typed query and keyword filters")
    selected = query or FederationGateQuery(**kwargs)
    rows = _query_items(value, selected)
    page = rows[selected.offset : selected.offset + selected.limit]
    body = {
        "gate_address": value.gate.content_address,
        "assurance_address": value.assurance.content_address,
        "query": selected,
        "total_count": len(rows),
        "returned_count": len(page),
        "items": page,
        "content_address": "pending:federation-gate-query",
    }
    provisional = FederationGateQueryResult(**body)
    body["content_address"] = address_query(provisional)
    return FederationGateQueryResult(**body)


def verify_federation_gate_query(value: FederationGateQueryResult) -> FederationGateQueryResult:
    if not isinstance(value, FederationGateQueryResult):
        raise ValidationError("gate query verification requires a typed result")
    value._validate()
    if address_query(value) != value.content_address:
        raise ValidationError("gate query address mismatch")
    return value


def gate_query_from_mapping(value: Mapping[str, Any]) -> FederationGateQueryResult:
    body = dict(_mapping(value, "gate query result"))
    allowed = {"gate_address", "assurance_address", "query", "total_count", "returned_count", "items", "content_address"}
    _strict(body, allowed, "gate query result")
    _required(body, allowed, "gate query result")
    query_body = dict(_mapping(body["query"], "gate query"))
    query_allowed = {"resource", "plane", "severity", "passed", "text", "offset", "limit"}
    _strict(query_body, query_allowed, "gate query")
    _required(query_body, query_allowed, "gate query")
    body["query"] = FederationGateQuery(**query_body)
    body["items"] = tuple(_mapping_sequence(body["items"], "gate query items"))
    return verify_federation_gate_query(FederationGateQueryResult(**body))


def query_json(value: FederationGateQueryResult) -> str:
    verify_federation_gate_query(value)
    return canonical_json(value.to_dict())


def query_csv(value: FederationGateQueryResult) -> str:
    verify_federation_gate_query(value)
    fields = tuple(value.items[0].keys()) if value.items else ("gate_address", "resource", "total_count", "returned_count")
    return _csv_text(value.items, fields)


def render_query_markdown(value: FederationGateQueryResult) -> str:
    verify_federation_gate_query(value)
    return _markdown("Decision Assurance History Series Release Registry Federation Gate Query", {"gate_address": value.gate_address, "resource": value.query.resource, "total_count": value.total_count, "returned_count": value.returned_count}, value.items)


def finding_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "FederationAssuranceFinding",
        "type": "object",
        "additionalProperties": False,
        "required": ["ordinal", "finding_id", "plane", "severity", "passed", "detail", "evidence_address", "content_address"],
        "properties": {
            "ordinal": {"type": "integer", "minimum": 0, "maximum": MAX_FINDINGS - 1},
            "finding_id": {"type": "string"},
            "plane": {"enum": list(GatePlane)},
            "severity": {"enum": list(FindingSeverity)},
            "passed": {"type": "boolean"},
            "detail": {"type": "string"},
            "evidence_address": {"type": "string"},
            "content_address": {"type": "string"},
        },
    }


def assurance_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "FederationAssurance",
        "type": "object",
        "additionalProperties": False,
        "required": ["version", "boundary", "federation_address", "runtime_address", "finding_count", "passed_count", "failed_count", "blocker_count", "warning_count", "accepted", "release_ready", "state", "findings", "content_address"],
        "properties": {
            "version": {"const": VERSION},
            "boundary": {"const": BOUNDARY},
            "federation_address": {"type": "string"},
            "runtime_address": {"type": "string"},
            "finding_count": {"type": "integer", "minimum": 0, "maximum": MAX_FINDINGS},
            "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_FINDINGS},
            "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_FINDINGS},
            "blocker_count": {"type": "integer", "minimum": 0, "maximum": MAX_FINDINGS},
            "warning_count": {"type": "integer", "minimum": 0, "maximum": MAX_FINDINGS},
            "accepted": {"type": "boolean"},
            "release_ready": {"type": "boolean"},
            "state": {"enum": list(GateState)},
            "findings": {"type": "array", "maxItems": MAX_FINDINGS, "items": {"$ref": "#/$defs/finding"}},
            "content_address": {"type": "string"},
        },
        "$defs": {"finding": finding_schema()},
    }


def gate_check_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "FederationGateCheck",
        "type": "object",
        "additionalProperties": False,
        "required": ["ordinal", "check_id", "severity", "passed", "detail", "evidence_address", "content_address"],
        "properties": {
            "ordinal": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS - 1},
            "check_id": {"type": "string"},
            "severity": {"enum": list(FindingSeverity)},
            "passed": {"type": "boolean"},
            "detail": {"type": "string"},
            "evidence_address": {"type": "string"},
            "content_address": {"type": "string"},
        },
    }


def gate_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "FederationReleaseGate",
        "type": "object",
        "additionalProperties": False,
        "required": ["gate_id", "version", "boundary", "federation_address", "runtime_address", "assurance_address", "state", "decision", "check_count", "passed_count", "failed_count", "required_failure_count", "optional_failure_count", "accepted", "release_ready", "checks", "content_address"],
        "properties": {
            "gate_id": {"type": "string"},
            "version": {"const": VERSION},
            "boundary": {"const": BOUNDARY},
            "federation_address": {"type": "string"},
            "runtime_address": {"type": "string"},
            "assurance_address": {"type": "string"},
            "state": {"enum": list(GateState)},
            "decision": {"enum": list(GateState)},
            "check_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS},
            "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS},
            "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS},
            "required_failure_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS},
            "optional_failure_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS},
            "accepted": {"type": "boolean"},
            "release_ready": {"type": "boolean"},
            "checks": {"type": "array", "maxItems": MAX_CHECKS, "items": {"$ref": "#/$defs/check"}},
            "content_address": {"type": "string"},
        },
        "$defs": {"check": gate_check_schema()},
    }


def assurance_gate_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "FederationAssuranceGateBundle",
        "type": "object",
        "additionalProperties": False,
        "required": ["assurance", "gate"],
        "properties": {"assurance": {"$ref": "#/$defs/assurance"}, "gate": {"$ref": "#/$defs/gate"}},
        "$defs": {"assurance": assurance_schema(), "gate": gate_schema()},
    }


def query_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "FederationGateQuery",
        "type": "object",
        "additionalProperties": False,
        "required": ["resource", "plane", "severity", "passed", "text", "offset", "limit"],
        "properties": {
            "resource": {"enum": list(FederationGateQuery.RESOURCES)},
            "plane": {"enum": list(GatePlane) + [None]},
            "severity": {"enum": list(FindingSeverity) + [None]},
            "passed": {"type": ["boolean", "null"]},
            "text": {"type": ["string", "null"]},
            "offset": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS},
            "limit": {"type": "integer", "minimum": 1, "maximum": MAX_QUERY_ITEMS},
        },
    }


def manifest_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "FederationAssuranceGateManifest",
        "type": "object",
        "additionalProperties": False,
        "required": ["version", "boundary", "federation_address", "runtime_address", "assurance_address", "gate_address", "files", "artifact_count", "artifacts", "content_address"],
        "properties": {
            "version": {"const": VERSION},
            "boundary": {"const": BOUNDARY},
            "federation_address": {"type": "string"},
            "runtime_address": {"type": "string"},
            "assurance_address": {"type": "string"},
            "gate_address": {"type": "string"},
            "files": {"const": list(FILES)},
            "artifact_count": {"const": len(FILES) - 1},
            "artifacts": {"type": "array", "maxItems": len(FILES) - 1},
            "content_address": {"type": "string"},
        },
    }


def federation_assurance_gate_capabilities() -> dict[str, Any]:
    return {
        "version": VERSION,
        "boundary": BOUNDARY,
        "states": list(GateState),
        "severities": list(FindingSeverity),
        "planes": list(GatePlane),
        "assurance": {"finding_count": 10, "max_findings": MAX_FINDINGS, "files": [MANIFEST_NAME, ASSURANCE_NAME]},
        "gate": {"check_count": 8, "max_checks": MAX_CHECKS, "files": [MANIFEST_NAME, GATE_NAME]},
        "package": {"files": list(FILES), "artifact_count": len(FILES) - 1, "atomic_write": True, "canonical_json": True, "exact_file_set": True},
        "queries": {"resources": list(FederationGateQuery.RESOURCES), "max_limit": MAX_QUERY_ITEMS, "filters": ["plane", "severity", "passed", "text"]},
        "public_boundary": {"source_paths": False, "nested_payloads": False, "identity_free": True},
    }
