"""Independently assure and gate an observatory packet-registry federation.

This module is the release boundary above a registry federation.  It never
recomputes scientific claims and it never merges member records.  Instead it
replays the federation verifier and runtime, checks every addressed linkage,
classifies warnings separately from blockers, and emits a small release gate
that a reviewer can carry without the source directories.

The two projections deliberately have different responsibilities:

* assurance records independent findings and remediation text;
* the release gate converts those findings and component states into a
  promote, hold, or block decision.

All public projections are deterministic, bounded, path-free, and safe to
persist as canonical UTF-8 JSON.  A persisted gate package contains exactly
three files: ``manifest.json``, ``assurance.json``, and ``gate.json``.
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

from . import (
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation as federation_model,
)
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes

FEDERATION = federation_model
Federation = federation_model.ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederation
FederationVerification = federation_model.ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederationVerification
FederationRuntime = federation_model.ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederationRuntime

FEDERATION_PREFIX = federation_model.MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_PREFIX
VERSION = FEDERATION_PREFIX + "-assurance-gate-v1"
BOUNDARY = "public_registry_federation_assurance_gate"
ASSURANCE_PREFIX = FEDERATION_PREFIX + "-assurance"
FINDING_PREFIX = ASSURANCE_PREFIX + "-finding"
GATE_PREFIX = FEDERATION_PREFIX + "-release-gate"
CHECK_PREFIX = GATE_PREFIX + "-check"
QUERY_PREFIX = GATE_PREFIX + "-query"
MANIFEST_PREFIX = GATE_PREFIX + "-manifest"
DEFAULT_ASSURANCE_ID = "glio-noncode-observatory-registry-federation-assurance"
DEFAULT_GATE_ID = "glio-noncode-observatory-registry-federation-release-gate"
MAX_FINDINGS = 64
MAX_CHECKS = 64
MAX_QUERY_ITEMS = 4096
DEFAULT_LIMIT = 50
MANIFEST_NAME = "manifest.json"
ASSURANCE_NAME = "assurance.json"
GATE_NAME = "gate.json"
FILES = (MANIFEST_NAME, ASSURANCE_NAME, GATE_NAME)

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


class AssuranceSeverity(StrEnum):
    PASS = "pass"
    WARNING = "warning"
    BLOCKER = "blocker"


class AssuranceState(StrEnum):
    PASSED = "passed"
    WARNING = "warning"
    BLOCKED = "blocked"


class GateState(StrEnum):
    PROMOTE = "promote"
    HOLD = "hold"
    BLOCK = "block"


class GatePlane(StrEnum):
    FEDERATION = "federation"
    REGISTRIES = "registries"
    PACKETS = "packets"
    VERIFICATION = "verification"
    RUNTIME = "runtime"
    POLICY = "policy"
    PUBLIC = "public"
    PERSISTENCE = "persistence"


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value.strip()


def _address(value: Any, field: str) -> str:
    value = _text(value, field, 4096)
    if ":" not in value or value.endswith(":"):
        raise ValidationError(f"{field} must be a content address")
    return value


def _optional_address(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return _address(value, field)


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _count(value: Any, field: str, maximum: int = MAX_QUERY_ITEMS, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{field} must be an integer")
    if value < (1 if positive else 0) or value > maximum:
        raise ValidationError(f"{field} is outside its bounded range")
    return value


def _json_value(value: Any, field: str) -> Any:
    try:
        encoded = canonical_bytes(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} must be JSON-compatible") from exc
    if len(encoded) > 1_000_000:
        raise ValidationError(f"{field} is too large")
    return value


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(
            str(key).casefold() not in _FORBIDDEN_KEYS and _public(item)
            for key, item in value.items()
        )
    if isinstance(value, (tuple, list)):
        return all(_public(item) for item in value)
    return True


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _strict_mapping(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unknown fields")


def _file_address(name: str, raw: bytes) -> str:
    return hash_bytes(raw, prefix=f"{MANIFEST_PREFIX}:{name.removesuffix('.json')}")


def _safe_recompute(call: Any) -> tuple[Any | None, bool]:
    try:
        return call(), True
    except (AttributeError, KeyError, TypeError, ValueError, ValidationError):
        return None, False


def address_federation_assurance_finding(
    value: FederationAssuranceFinding,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=FINDING_PREFIX,
    )


class FederationAssuranceFinding:
    """One independent federation assurance observation."""

    def __init__(
        self,
        ordinal: int,
        finding_id: str,
        plane: str,
        kind: str,
        severity: str,
        passed: bool,
        expected: Any,
        observed: Any,
        detail: str,
        remediation: str,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.finding_id = finding_id
        self.plane = plane
        self.kind = kind
        self.severity = severity
        self.passed = passed
        self.expected = expected
        self.observed = observed
        self.detail = detail
        self.remediation = remediation
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "assurance finding ordinal", MAX_FINDINGS)
        _text(self.finding_id, "assurance finding ID", 256)
        if self.plane not in {item.value for item in GatePlane}:
            raise ValidationError("assurance finding plane is invalid")
        _text(self.kind, "assurance finding kind", 256)
        if self.severity not in {item.value for item in AssuranceSeverity}:
            raise ValidationError("assurance finding severity is invalid")
        _bool(self.passed, "assurance finding passed flag")
        _json_value(self.expected, "assurance finding expected value")
        _json_value(self.observed, "assurance finding observed value")
        _text(self.detail, "assurance finding detail")
        _text(self.remediation, "assurance finding remediation")
        _address(self.content_address, "assurance finding address")
        if self.passed and self.severity != AssuranceSeverity.PASS.value:
            raise ValidationError("passed findings must have pass severity")
        if not self.passed and self.severity == AssuranceSeverity.PASS.value:
            raise ValidationError("failed findings cannot have pass severity")
        if not _public(self.to_dict()):
            raise ValidationError("assurance finding crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "finding_id": self.finding_id,
            "plane": self.plane,
            "kind": self.kind,
            "severity": self.severity,
            "passed": self.passed,
            "expected": self.expected,
            "observed": self.observed,
            "detail": self.detail,
            "remediation": self.remediation,
            "content_address": self.content_address,
        }


def _finding(
    ordinal: int,
    *,
    plane: str,
    kind: str,
    passed: bool,
    expected: Any,
    observed: Any,
    detail: str,
    remediation: str,
    severity: str | None = None,
) -> FederationAssuranceFinding:
    resolved = AssuranceSeverity.PASS.value if passed else severity or AssuranceSeverity.BLOCKER.value
    body = {
        "ordinal": ordinal,
        "finding_id": f"{ASSURANCE_PREFIX}:{ordinal}:{kind}",
        "plane": plane,
        "kind": kind,
        "severity": resolved,
        "passed": passed,
        "expected": expected,
        "observed": observed,
        "detail": detail,
        "remediation": remediation,
    }
    provisional = FederationAssuranceFinding(**body, content_address="pending:finding")
    return FederationAssuranceFinding(
        **body,
        content_address=address_federation_assurance_finding(provisional),
    )


def address_federation_assurance(value: FederationAssurance) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=ASSURANCE_PREFIX,
    )


class FederationAssurance:
    """Independent federation findings with warning/blocker conservation."""

    def __init__(
        self,
        assurance_id: str,
        version: str,
        boundary: str,
        federation_id: str,
        federation_address: str,
        verification_address: str,
        runtime_address: str,
        finding_count: int,
        passed_count: int,
        warning_count: int,
        blocker_count: int,
        state: str,
        release_ready: bool,
        accepted: bool,
        findings: Sequence[FederationAssuranceFinding],
        content_address: str,
    ) -> None:
        self.assurance_id = assurance_id
        self.version = version
        self.boundary = boundary
        self.federation_id = federation_id
        self.federation_address = federation_address
        self.verification_address = verification_address
        self.runtime_address = runtime_address
        self.finding_count = finding_count
        self.passed_count = passed_count
        self.warning_count = warning_count
        self.blocker_count = blocker_count
        self.state = state
        self.release_ready = release_ready
        self.accepted = accepted
        self.findings = tuple(findings)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.assurance_id, "assurance ID", 256)
        if self.version != VERSION:
            raise ValidationError("assurance version is invalid")
        if self.boundary != BOUNDARY:
            raise ValidationError("assurance boundary is invalid")
        _text(self.federation_id, "assurance federation ID", 256)
        _address(self.federation_address, "assurance federation address")
        _address(self.verification_address, "assurance verification address")
        _address(self.runtime_address, "assurance runtime address")
        _count(self.finding_count, "assurance finding count", MAX_FINDINGS, positive=True)
        _count(self.passed_count, "assurance passed count", MAX_FINDINGS)
        _count(self.warning_count, "assurance warning count", MAX_FINDINGS)
        _count(self.blocker_count, "assurance blocker count", MAX_FINDINGS)
        if self.finding_count != len(self.findings):
            raise ValidationError("assurance finding count is not conserved")
        for ordinal, finding in enumerate(self.findings):
            if not isinstance(finding, FederationAssuranceFinding) or finding.ordinal != ordinal:
                raise ValidationError("assurance findings are not contiguous")
            if address_federation_assurance_finding(finding) != finding.content_address:
                raise ValidationError("assurance finding address mismatch")
        counts = (
            sum(item.passed for item in self.findings),
            sum(not item.passed and item.severity == AssuranceSeverity.WARNING.value for item in self.findings),
            sum(not item.passed and item.severity == AssuranceSeverity.BLOCKER.value for item in self.findings),
        )
        if counts != (self.passed_count, self.warning_count, self.blocker_count):
            raise ValidationError("assurance finding severity counts are not conserved")
        if self.state not in {item.value for item in AssuranceState}:
            raise ValidationError("assurance state is invalid")
        _bool(self.release_ready, "assurance release-ready flag")
        _bool(self.accepted, "assurance accepted flag")
        expected_state = (
            AssuranceState.BLOCKED.value
            if self.blocker_count
            else AssuranceState.WARNING.value
            if self.warning_count
            else AssuranceState.PASSED.value
        )
        if self.state != expected_state:
            raise ValidationError("assurance state does not follow findings")
        if self.accepted != (self.blocker_count == 0):
            raise ValidationError("assurance acceptance does not conserve")
        if self.release_ready != (self.accepted and self.warning_count == 0):
            raise ValidationError("assurance readiness does not conserve")
        _address(self.content_address, "assurance content address")
        if not _public(self.to_dict()):
            raise ValidationError("assurance crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "assurance_id": self.assurance_id,
            "version": self.version,
            "boundary": self.boundary,
            "federation_id": self.federation_id,
            "federation_address": self.federation_address,
            "verification_address": self.verification_address,
            "runtime_address": self.runtime_address,
            "finding_count": self.finding_count,
            "passed_count": self.passed_count,
            "warning_count": self.warning_count,
            "blocker_count": self.blocker_count,
            "state": self.state,
            "release_ready": self.release_ready,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }

    def to_dict(self, *, include_findings: bool = True) -> dict[str, Any]:
        body = self.summary()
        if include_findings:
            body["findings"] = [item.to_dict() for item in self.findings]
        return body


def address_federation_gate_check(value: FederationGateCheck) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=CHECK_PREFIX,
    )


class FederationGateCheck:
    """One release-gate check, with required checks becoming blockers."""

    def __init__(
        self,
        ordinal: int,
        check_id: str,
        plane: str,
        kind: str,
        severity: str,
        required: bool,
        passed: bool,
        expected: Any,
        observed: Any,
        detail: str,
        remediation: str,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.check_id = check_id
        self.plane = plane
        self.kind = kind
        self.severity = severity
        self.required = required
        self.passed = passed
        self.expected = expected
        self.observed = observed
        self.detail = detail
        self.remediation = remediation
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "gate check ordinal", MAX_CHECKS)
        _text(self.check_id, "gate check ID", 256)
        if self.plane not in {item.value for item in GatePlane}:
            raise ValidationError("gate check plane is invalid")
        _text(self.kind, "gate check kind", 256)
        if self.severity not in {item.value for item in AssuranceSeverity}:
            raise ValidationError("gate check severity is invalid")
        _bool(self.required, "gate check required flag")
        _bool(self.passed, "gate check passed flag")
        _json_value(self.expected, "gate check expected value")
        _json_value(self.observed, "gate check observed value")
        _text(self.detail, "gate check detail")
        _text(self.remediation, "gate check remediation")
        _address(self.content_address, "gate check address")
        if self.passed and self.severity != AssuranceSeverity.PASS.value:
            raise ValidationError("passed gate checks must have pass severity")
        if not self.passed and self.severity == AssuranceSeverity.PASS.value:
            raise ValidationError("failed gate checks cannot have pass severity")
        if not self.passed and self.required and self.severity != AssuranceSeverity.BLOCKER.value:
            raise ValidationError("failed required gate checks must be blockers")
        if not self.passed and not self.required and self.severity != AssuranceSeverity.WARNING.value:
            raise ValidationError("failed optional gate checks must be warnings")
        if not _public(self.to_dict()):
            raise ValidationError("gate check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "check_id": self.check_id,
            "plane": self.plane,
            "kind": self.kind,
            "severity": self.severity,
            "required": self.required,
            "passed": self.passed,
            "expected": self.expected,
            "observed": self.observed,
            "detail": self.detail,
            "remediation": self.remediation,
            "content_address": self.content_address,
        }


def _gate_check(
    ordinal: int,
    *,
    plane: str,
    kind: str,
    required: bool,
    passed: bool,
    expected: Any,
    observed: Any,
    detail: str,
    remediation: str,
) -> FederationGateCheck:
    severity = AssuranceSeverity.PASS.value if passed else AssuranceSeverity.BLOCKER.value if required else AssuranceSeverity.WARNING.value
    body = {
        "ordinal": ordinal,
        "check_id": f"{GATE_PREFIX}:{ordinal}:{kind}",
        "plane": plane,
        "kind": kind,
        "severity": severity,
        "required": required,
        "passed": passed,
        "expected": expected,
        "observed": observed,
        "detail": detail,
        "remediation": remediation,
    }
    provisional = FederationGateCheck(**body, content_address="pending:check")
    return FederationGateCheck(**body, content_address=address_federation_gate_check(provisional))


def address_federation_release_gate(value: FederationReleaseGate) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=GATE_PREFIX,
    )


class FederationReleaseGate:
    """A promote/hold/block result for one assured federation."""

    def __init__(
        self,
        gate_id: str,
        version: str,
        boundary: str,
        federation_id: str,
        federation_address: str,
        assurance_address: str,
        verification_address: str,
        runtime_address: str,
        registry_count: int,
        total_packet_count: int,
        check_count: int,
        passed_count: int,
        warning_count: int,
        blocker_count: int,
        state: str,
        release_ready: bool,
        accepted: bool,
        checks: Sequence[FederationGateCheck],
        content_address: str,
    ) -> None:
        self.gate_id = gate_id
        self.version = version
        self.boundary = boundary
        self.federation_id = federation_id
        self.federation_address = federation_address
        self.assurance_address = assurance_address
        self.verification_address = verification_address
        self.runtime_address = runtime_address
        self.registry_count = registry_count
        self.total_packet_count = total_packet_count
        self.check_count = check_count
        self.passed_count = passed_count
        self.warning_count = warning_count
        self.blocker_count = blocker_count
        self.state = state
        self.release_ready = release_ready
        self.accepted = accepted
        self.checks = tuple(checks)
        self.content_address = content_address
        self.assurance: FederationAssurance | None = None
        self.federation: Federation | None = None
        self.verification: Any | None = None
        self.runtime: Any | None = None
        self._validate()

    def _validate(self) -> None:
        _text(self.gate_id, "gate ID", 256)
        if self.version != VERSION:
            raise ValidationError("gate version is invalid")
        if self.boundary != BOUNDARY:
            raise ValidationError("gate boundary is invalid")
        _text(self.federation_id, "gate federation ID", 256)
        for value, field in (
            (self.federation_address, "gate federation address"),
            (self.assurance_address, "gate assurance address"),
            (self.verification_address, "gate verification address"),
            (self.runtime_address, "gate runtime address"),
        ):
            _address(value, field)
        _count(self.registry_count, "gate registry count", federation_model.MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MAX_REGISTRIES)
        _count(self.total_packet_count, "gate total packet count", federation_model.MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MAX_PACKETS)
        _count(self.check_count, "gate check count", MAX_CHECKS, positive=True)
        _count(self.passed_count, "gate passed count", MAX_CHECKS)
        _count(self.warning_count, "gate warning count", MAX_CHECKS)
        _count(self.blocker_count, "gate blocker count", MAX_CHECKS)
        if self.check_count != len(self.checks):
            raise ValidationError("gate check count is not conserved")
        for ordinal, check in enumerate(self.checks):
            if not isinstance(check, FederationGateCheck) or check.ordinal != ordinal:
                raise ValidationError("gate checks are not contiguous")
            if address_federation_gate_check(check) != check.content_address:
                raise ValidationError("gate check address mismatch")
        counts = (
            sum(item.passed for item in self.checks),
            sum(not item.passed and item.severity == AssuranceSeverity.WARNING.value for item in self.checks),
            sum(not item.passed and item.severity == AssuranceSeverity.BLOCKER.value for item in self.checks),
        )
        if counts != (self.passed_count, self.warning_count, self.blocker_count):
            raise ValidationError("gate check counts are not conserved")
        if self.state not in {item.value for item in GateState}:
            raise ValidationError("gate state is invalid")
        _bool(self.release_ready, "gate release-ready flag")
        _bool(self.accepted, "gate accepted flag")
        expected_state = (
            GateState.BLOCK.value
            if self.blocker_count
            else GateState.HOLD.value
            if self.warning_count
            else GateState.PROMOTE.value
        )
        if self.state != expected_state:
            raise ValidationError("gate state does not follow checks")
        if self.accepted != (self.blocker_count == 0):
            raise ValidationError("gate acceptance does not conserve")
        if self.release_ready != (self.accepted and self.warning_count == 0):
            raise ValidationError("gate readiness does not conserve")
        _address(self.content_address, "gate content address")
        if not _public(self.to_dict()):
            raise ValidationError("gate crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "version": self.version,
            "boundary": self.boundary,
            "federation_id": self.federation_id,
            "federation_address": self.federation_address,
            "assurance_address": self.assurance_address,
            "verification_address": self.verification_address,
            "runtime_address": self.runtime_address,
            "registry_count": self.registry_count,
            "total_packet_count": self.total_packet_count,
            "check_count": self.check_count,
            "passed_count": self.passed_count,
            "warning_count": self.warning_count,
            "blocker_count": self.blocker_count,
            "state": self.state,
            "release_ready": self.release_ready,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }

    def to_dict(self, *, include_checks: bool = True) -> dict[str, Any]:
        body = self.summary()
        if include_checks:
            body["checks"] = [item.to_dict() for item in self.checks]
        return body


def _component_values(
    federation: Federation,
    verification: Any | None,
    runtime: Any | None,
) -> tuple[Any | None, Any | None, bool, bool]:
    stored_verification = verification if verification is not None else getattr(federation, "verification", None)
    stored_runtime = runtime if runtime is not None else getattr(federation, "runtime", None)
    verification_typed = isinstance(stored_verification, FederationVerification)
    runtime_typed = isinstance(stored_runtime, FederationRuntime)
    return stored_verification, stored_runtime, verification_typed, runtime_typed


def _hydrated_registry_check(federation: Federation) -> tuple[bool, dict[str, Any]]:
    registries = tuple(getattr(federation, "registries", ()))
    if not registries:
        return (
            True,
            {
                "declared": federation.registry_count,
                "hydrated": 0,
                "unique_ids": True,
                "addresses_match": True,
                "offline_entry_projection": True,
            },
        )
    by_id = {getattr(item, "registry_id", None): item for item in registries}
    unique_ids = len(by_id) == len(registries)
    matched = all(
        entry.registry_id in by_id
        and getattr(by_id[entry.registry_id], "content_address", None) == entry.registry_address
        for entry in federation.entries
    )
    return (
        len(registries) == federation.registry_count and unique_ids and matched,
        {"declared": federation.registry_count, "hydrated": len(registries), "unique_ids": unique_ids, "addresses_match": matched},
    )


def _packet_conservation_check(federation: Federation) -> tuple[bool, dict[str, int]]:
    observed = sum(entry.packet_count for entry in federation.entries)
    return observed == federation.total_packet_count, {"declared": federation.total_packet_count, "sum_of_registries": observed}


def build_federation_assurance(
    federation: Federation,
    *,
    assurance_id: str = DEFAULT_ASSURANCE_ID,
    verification: Any | None = None,
    runtime: Any | None = None,
    registries: Sequence[Any] | None = None,
    policy: Any | None = None,
) -> FederationAssurance:
    """Independently recompute and classify one registry federation."""

    if not isinstance(federation, Federation):
        raise ValidationError("federation assurance requires a typed federation")
    stored_verification, stored_runtime, verification_typed, runtime_typed = _component_values(federation, verification, runtime)
    member_values = tuple(registries if registries is not None else getattr(federation, "registries", ()))
    selected_policy = policy if policy is not None else getattr(federation, "policy", None)
    recomputed_verification, verification_replayed = _safe_recompute(
        lambda: federation_model.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
            federation,
            registries=member_values,
            policy=selected_policy,
        )
    )
    if recomputed_verification is None:
        verification_replayed = False
    recomputed_runtime, runtime_replayed = _safe_recompute(
        lambda: federation_model.run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_runtime(
            federation,
            policy=selected_policy,
            verification=recomputed_verification,
        )
    ) if recomputed_verification is not None else (None, False)
    hydration_ok, hydration_observed = _hydrated_registry_check(federation)
    packets_ok, packet_observed = _packet_conservation_check(federation)
    stored_verification_address = getattr(stored_verification, "content_address", None)
    stored_runtime_address = getattr(stored_runtime, "content_address", None)
    verification_address_ok = verification_typed and federation.verification_address == stored_verification_address
    runtime_address_ok = runtime_typed and federation.runtime_address == stored_runtime_address
    verification_result_ok = (
        verification_replayed
        and verification_typed
        and recomputed_verification is not None
        and recomputed_verification.to_dict() == stored_verification.to_dict()
    )
    runtime_result_ok = (
        runtime_replayed
        and runtime_typed
        and recomputed_runtime is not None
        and recomputed_runtime.to_dict() == stored_runtime.to_dict()
    )
    member_addresses_ok = all(
        ":" in entry.registry_address and ":" in entry.content_address
        for entry in federation.entries
    )
    verification_checks_ok = bool(stored_verification) and all(
        ":" in getattr(check, "content_address", "")
        for check in getattr(stored_verification, "checks", ())
    )
    runtime_stages_ok = bool(stored_runtime) and all(
        ":" in getattr(stage, "content_address", "")
        for stage in getattr(stored_runtime, "stages", ())
    )
    no_paths = "source_path" not in canonical_json(federation.to_dict()).casefold()
    findings = (
        _finding(0, plane=GatePlane.FEDERATION.value, kind="federation-address", passed=federation_model.address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(federation) == federation.content_address, expected="recomputed federation address", observed=federation.content_address, detail="the federation aggregate address is recomputed outside the federation builder", remediation="rebuild the federation from canonical registry entries"),
        _finding(1, plane=GatePlane.FEDERATION.value, kind="version-boundary", passed=federation.version == federation_model.MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_VERSION and bool(federation.boundary), expected="published federation version and boundary", observed={"version": federation.version, "boundary": federation.boundary}, detail="the federation remains on its published contract", remediation="rebuild with the current federation contract"),
        _finding(2, plane=GatePlane.REGISTRIES.value, kind="registry-conservation", passed=federation.registry_count == len(federation.entries) and federation.ready_registry_count + federation.held_registry_count + federation.blocked_registry_count == federation.registry_count, expected={"entry_count": federation.registry_count, "state_count": federation.registry_count}, observed={"entry_count": len(federation.entries), "state_count": federation.ready_registry_count + federation.held_registry_count + federation.blocked_registry_count}, detail="registry entries and state rollups are conserved", remediation="rebuild registry entries and state counters"),
        _finding(3, plane=GatePlane.REGISTRIES.value, kind="hydrated-members", passed=hydration_ok, expected="each declared registry is hydrated exactly once", observed=hydration_observed, detail="independent assurance reconciles hydrated registries to addressed federation entries", remediation="hydrate the exact registry directories used to build the federation"),
        _finding(4, plane=GatePlane.REGISTRIES.value, kind="registry-addresses", passed=member_addresses_ok and len({entry.registry_address for entry in federation.entries}) == federation.registry_count, expected="unique addressed registry entries", observed={"unique_addresses": len({entry.registry_address for entry in federation.entries}), "declared": federation.registry_count}, detail="registry and entry addresses are present and unique", remediation="rebuild duplicate or malformed registry entries"),
        _finding(5, plane=GatePlane.PACKETS.value, kind="packet-conservation", passed=packets_ok, expected={"total_packet_count": federation.total_packet_count}, observed=packet_observed, detail="packet totals equal the sum of member registry packet counts", remediation="recompute packet rollups from registry members"),
        _finding(6, plane=GatePlane.VERIFICATION.value, kind="verification-type", passed=verification_typed, expected=True, observed=type(stored_verification).__name__ if stored_verification is not None else None, detail="the federation carries a typed independent verification receipt", remediation="rebuild the federation verification receipt"),
        _finding(7, plane=GatePlane.VERIFICATION.value, kind="verification-address", passed=verification_address_ok, expected=federation.verification_address, observed=stored_verification_address, detail="the federation verification link points to the hydrated receipt", remediation="rebuild the federation with its verification receipt"),
        _finding(8, plane=GatePlane.VERIFICATION.value, kind="verification-replay", passed=verification_result_ok, expected="recomputed verification equals stored verification", observed={"replayed": verification_replayed, "stored": verification_typed}, detail="verification is replayed independently and compared byte-for-byte", remediation="repair changed registry, policy, or verification data"),
        _finding(9, plane=GatePlane.VERIFICATION.value, kind="verification-check-addresses", passed=verification_checks_ok, expected=True, observed=verification_checks_ok, detail="nested verification checks retain addressed receipts", remediation="rebuild nested verification checks"),
        _finding(10, plane=GatePlane.RUNTIME.value, kind="runtime-type", passed=runtime_typed, expected=True, observed=type(stored_runtime).__name__ if stored_runtime is not None else None, detail="the federation carries a typed policy runtime", remediation="replay the federation runtime"),
        _finding(11, plane=GatePlane.RUNTIME.value, kind="runtime-address", passed=runtime_address_ok, expected=federation.runtime_address, observed=stored_runtime_address, detail="the federation runtime link points to the hydrated runtime", remediation="rebuild the federation with its runtime receipt"),
        _finding(12, plane=GatePlane.RUNTIME.value, kind="runtime-replay", passed=runtime_result_ok, expected="recomputed runtime equals stored runtime", observed={"replayed": runtime_replayed, "stored": runtime_typed}, detail="policy runtime is replayed independently and compared byte-for-byte", remediation="repair changed policy, verification, or runtime data"),
        _finding(13, plane=GatePlane.RUNTIME.value, kind="runtime-stage-addresses", passed=runtime_stages_ok, expected=True, observed=runtime_stages_ok, detail="runtime stages retain their addressed receipts", remediation="rebuild nested runtime stages"),
        _finding(14, plane=GatePlane.POLICY.value, kind="policy-closure", passed=runtime_typed and bool(stored_runtime) and getattr(stored_runtime, "policy_failed_count", 1) == 0, expected=0, observed=getattr(stored_runtime, "policy_failed_count", None), detail="all federation policy checks pass for promotion", remediation="resolve the failed federation policy checks"),
        _finding(15, plane=GatePlane.FEDERATION.value, kind="federation-accepted", passed=federation.accepted, expected=True, observed=federation.accepted, detail="the federation structural projection is accepted", remediation="repair federation metadata and member conservation"),
        _finding(16, plane=GatePlane.FEDERATION.value, kind="federation-release-ready", passed=federation.release_ready, expected=True, observed=federation.release_ready, detail="the federation is release-ready without member holds", remediation="resolve held or blocked federation members", severity=AssuranceSeverity.WARNING.value),
        _finding(17, plane=GatePlane.RUNTIME.value, kind="runtime-release-ready", passed=runtime_typed and bool(stored_runtime) and getattr(stored_runtime, "release_ready", False), expected=True, observed=getattr(stored_runtime, "release_ready", None), detail="the policy runtime reaches release readiness", remediation="resolve runtime readiness holds", severity=AssuranceSeverity.WARNING.value),
        _finding(18, plane=GatePlane.FEDERATION.value, kind="empty-boundary", passed=federation.registry_count > 0, expected="at least one registry for promotion", observed=federation.registry_count, detail="empty federations remain visible but cannot be promoted", remediation="register at least one verified observatory registry", severity=AssuranceSeverity.WARNING.value),
        _finding(19, plane=GatePlane.PUBLIC.value, kind="public-boundary", passed=_public(federation.to_dict()) and (stored_verification is None or _public(stored_verification.to_dict())) and (stored_runtime is None or _public(stored_runtime.to_dict())), expected=True, observed=True, detail="federation components contain no forbidden identity or private metadata", remediation="remove forbidden fields from public projections"),
        _finding(20, plane=GatePlane.PUBLIC.value, kind="path-free-output", passed=no_paths, expected=True, observed=no_paths, detail="source directories remain input-only and do not enter public output", remediation="remove source path fields before publication"),
    )
    body = {
        "assurance_id": _text(assurance_id, "assurance ID", 256),
        "version": VERSION,
        "boundary": BOUNDARY,
        "federation_id": federation.federation_id,
        "federation_address": federation.content_address,
        "verification_address": federation.verification_address,
        "runtime_address": federation.runtime_address,
        "finding_count": len(findings),
        "passed_count": sum(item.passed for item in findings),
        "warning_count": sum(not item.passed and item.severity == AssuranceSeverity.WARNING.value for item in findings),
        "blocker_count": sum(not item.passed and item.severity == AssuranceSeverity.BLOCKER.value for item in findings),
        "state": "blocked" if any(not item.passed and item.severity == AssuranceSeverity.BLOCKER.value for item in findings) else "warning" if any(not item.passed for item in findings) else "passed",
        "release_ready": all(item.passed for item in findings),
        "accepted": not any(not item.passed and item.severity == AssuranceSeverity.BLOCKER.value for item in findings),
        "findings": findings,
    }
    provisional = FederationAssurance(**body, content_address="pending:assurance")
    assurance = FederationAssurance(**body, content_address=address_federation_assurance(provisional))
    assurance.federation = federation
    assurance.verification = stored_verification
    assurance.runtime = stored_runtime
    assurance.policy = selected_policy
    assurance.registries = member_values
    return assurance


def _gate_checks(
    federation: Federation,
    assurance: FederationAssurance,
    verification: Any | None,
    runtime: Any | None,
) -> tuple[FederationGateCheck, ...]:
    stored_verification, stored_runtime, verification_typed, runtime_typed = _component_values(federation, verification, runtime)
    return (
        _gate_check(0, plane=GatePlane.FEDERATION.value, kind="federation-assurance-linkage", required=True, passed=assurance.federation_address == federation.content_address and assurance.federation_id == federation.federation_id, expected={"id": federation.federation_id, "address": federation.content_address}, observed={"id": assurance.federation_id, "address": assurance.federation_address}, detail="assurance is bound to the selected federation", remediation="rebuild assurance from this federation"),
        _gate_check(1, plane=GatePlane.FEDERATION.value, kind="federation-accepted", required=True, passed=federation.accepted, expected=True, observed=federation.accepted, detail="the federation is structurally accepted", remediation="repair federation structure"),
        _gate_check(2, plane=GatePlane.REGISTRIES.value, kind="registry-conservation", required=True, passed=federation.registry_count == federation.ready_registry_count + federation.held_registry_count + federation.blocked_registry_count, expected=federation.registry_count, observed=federation.ready_registry_count + federation.held_registry_count + federation.blocked_registry_count, detail="registry states are conserved", remediation="rebuild federation state rollups"),
        _gate_check(3, plane=GatePlane.PACKETS.value, kind="packet-conservation", required=True, passed=federation.total_packet_count == sum(entry.packet_count for entry in federation.entries), expected=federation.total_packet_count, observed=sum(entry.packet_count for entry in federation.entries), detail="packet totals are conserved across registries", remediation="recompute packet totals"),
        _gate_check(4, plane=GatePlane.VERIFICATION.value, kind="verification-linkage", required=True, passed=verification_typed and federation.verification_address == getattr(stored_verification, "content_address", None), expected=federation.verification_address, observed=getattr(stored_verification, "content_address", None), detail="the gate uses the federation verification receipt", remediation="rebuild verification linkage"),
        _gate_check(5, plane=GatePlane.VERIFICATION.value, kind="verification-accepted", required=True, passed=verification_typed and getattr(stored_verification, "accepted", False), expected=True, observed=getattr(stored_verification, "accepted", None), detail="independent federation verification accepts all structural checks", remediation="resolve failed verification checks"),
        _gate_check(6, plane=GatePlane.RUNTIME.value, kind="runtime-linkage", required=True, passed=runtime_typed and federation.runtime_address == getattr(stored_runtime, "content_address", None), expected=federation.runtime_address, observed=getattr(stored_runtime, "content_address", None), detail="the gate uses the federation runtime receipt", remediation="rebuild runtime linkage"),
        _gate_check(7, plane=GatePlane.RUNTIME.value, kind="runtime-accepted", required=True, passed=runtime_typed and getattr(stored_runtime, "accepted", False), expected=True, observed=getattr(stored_runtime, "accepted", None), detail="the policy runtime has no blocking policy failure", remediation="resolve blocked federation policy checks"),
        _gate_check(8, plane=GatePlane.POLICY.value, kind="assurance-accepted", required=True, passed=assurance.accepted, expected=True, observed=assurance.accepted, detail="independent assurance has no blocker findings", remediation="resolve assurance blockers"),
        _gate_check(9, plane=GatePlane.POLICY.value, kind="assurance-warning-free", required=False, passed=assurance.warning_count == 0, expected=0, observed=assurance.warning_count, detail="assurance has no readiness warnings", remediation="resolve assurance warnings before promotion"),
        _gate_check(10, plane=GatePlane.FEDERATION.value, kind="federation-release-ready", required=False, passed=federation.release_ready, expected=True, observed=federation.release_ready, detail="all registries are ready for release", remediation="resolve member readiness holds"),
        _gate_check(11, plane=GatePlane.RUNTIME.value, kind="runtime-release-ready", required=False, passed=runtime_typed and getattr(stored_runtime, "release_ready", False), expected=True, observed=getattr(stored_runtime, "release_ready", None), detail="runtime reaches release readiness", remediation="resolve runtime readiness holds"),
        _gate_check(12, plane=GatePlane.PUBLIC.value, kind="public-boundary", required=True, passed=_public(federation.to_dict()) and _public(assurance.to_dict()) and (stored_verification is None or _public(stored_verification.to_dict())) and (stored_runtime is None or _public(stored_runtime.to_dict())), expected=True, observed=True, detail="the gate remains safe at the public boundary", remediation="remove forbidden metadata"),
        _gate_check(13, plane=GatePlane.PUBLIC.value, kind="path-free-output", required=True, passed="source_path" not in canonical_json({"federation": federation.to_dict(), "assurance": assurance.to_dict()}).casefold(), expected=True, observed=True, detail="source paths are not carried into the release decision", remediation="remove path-bearing fields"),
        _gate_check(14, plane=GatePlane.PERSISTENCE.value, kind="addressed-components", required=True, passed=all(":" in address for address in (federation.content_address, assurance.content_address, federation.verification_address, federation.runtime_address)), expected=True, observed=True, detail="all gate component references are addressed", remediation="rebuild missing component addresses"),
    )


def build_federation_release_gate(
    federation: Federation,
    assurance: FederationAssurance,
    *,
    gate_id: str = DEFAULT_GATE_ID,
    verification: Any | None = None,
    runtime: Any | None = None,
) -> FederationReleaseGate:
    """Convert independent assurance and federation state into a gate."""

    if not isinstance(federation, Federation):
        raise ValidationError("release gate requires a typed federation")
    if not isinstance(assurance, FederationAssurance):
        raise ValidationError("release gate requires typed assurance")
    if address_federation_assurance(assurance) != assurance.content_address:
        raise ValidationError("release gate assurance address is invalid")
    checks = _gate_checks(federation, assurance, verification, runtime)
    body = {
        "gate_id": _text(gate_id, "gate ID", 256),
        "version": VERSION,
        "boundary": BOUNDARY,
        "federation_id": federation.federation_id,
        "federation_address": federation.content_address,
        "assurance_address": assurance.content_address,
        "verification_address": federation.verification_address,
        "runtime_address": federation.runtime_address,
        "registry_count": federation.registry_count,
        "total_packet_count": federation.total_packet_count,
        "check_count": len(checks),
        "passed_count": sum(item.passed for item in checks),
        "warning_count": sum(not item.passed and item.severity == AssuranceSeverity.WARNING.value for item in checks),
        "blocker_count": sum(not item.passed and item.severity == AssuranceSeverity.BLOCKER.value for item in checks),
        "state": GateState.BLOCK.value if any(not item.passed and item.severity == AssuranceSeverity.BLOCKER.value for item in checks) else GateState.HOLD.value if any(not item.passed for item in checks) else GateState.PROMOTE.value,
        "release_ready": all(item.passed for item in checks),
        "accepted": not any(not item.passed and item.severity == AssuranceSeverity.BLOCKER.value for item in checks),
        "checks": checks,
    }
    provisional = FederationReleaseGate(**body, content_address="pending:gate")
    gate = FederationReleaseGate(**body, content_address=address_federation_release_gate(provisional))
    gate.assurance = assurance
    gate.federation = federation
    gate.verification = verification if verification is not None else getattr(federation, "verification", None)
    gate.runtime = runtime if runtime is not None else getattr(federation, "runtime", None)
    return gate


def build_federation_assurance_gate(
    federation: Federation,
    *,
    assurance_id: str = DEFAULT_ASSURANCE_ID,
    gate_id: str = DEFAULT_GATE_ID,
    verification: Any | None = None,
    runtime: Any | None = None,
    registries: Sequence[Any] | None = None,
    policy: Any | None = None,
) -> FederationReleaseGate:
    assurance = build_federation_assurance(federation, assurance_id=assurance_id, verification=verification, runtime=runtime, registries=registries, policy=policy)
    return build_federation_release_gate(federation, assurance, gate_id=gate_id, verification=verification, runtime=runtime)


def build_federation_assurance_gate_from_directory(
    directory: str | Path,
    *,
    assurance_id: str = DEFAULT_ASSURANCE_ID,
    gate_id: str = DEFAULT_GATE_ID,
) -> FederationReleaseGate:
    federation = federation_model.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(directory)
    return build_federation_assurance_gate(federation, assurance_id=assurance_id, gate_id=gate_id)


def verify_federation_assurance(value: FederationAssurance) -> FederationAssurance:
    if not isinstance(value, FederationAssurance):
        raise ValidationError("assurance verification requires typed assurance")
    for finding in value.findings:
        if address_federation_assurance_finding(finding) != finding.content_address:
            raise ValidationError("assurance finding address mismatch")
    if address_federation_assurance(value) != value.content_address:
        raise ValidationError("assurance address mismatch")
    return value


def verify_federation_release_gate(value: FederationReleaseGate) -> FederationReleaseGate:
    if not isinstance(value, FederationReleaseGate):
        raise ValidationError("gate verification requires typed gate")
    for check in value.checks:
        if address_federation_gate_check(check) != check.content_address:
            raise ValidationError("gate check address mismatch")
    if address_federation_release_gate(value) != value.content_address:
        raise ValidationError("gate address mismatch")
    return value


def verify_federation_assurance_gate(value: FederationReleaseGate) -> FederationReleaseGate:
    if not isinstance(value, FederationReleaseGate):
        raise ValidationError("assurance-gate verification requires typed gate")
    verify_federation_release_gate(value)
    if not isinstance(value.assurance, FederationAssurance):
        raise ValidationError("assurance-gate verification requires attached assurance")
    verify_federation_assurance(value.assurance)
    if value.assurance.content_address != value.assurance_address:
        raise ValidationError("assurance-gate assurance linkage mismatch")
    if value.assurance.federation_id != value.federation_id or value.assurance.federation_address != value.federation_address:
        raise ValidationError("assurance-gate federation linkage mismatch")
    return value


def _allowed_finding_keys() -> set[str]:
    return {"ordinal", "finding_id", "plane", "kind", "severity", "passed", "expected", "observed", "detail", "remediation", "content_address"}


def federation_assurance_finding_from_mapping(value: Mapping[str, Any]) -> FederationAssuranceFinding:
    value = _mapping(value, "assurance finding")
    _strict_mapping(value, _allowed_finding_keys(), "assurance finding")
    return FederationAssuranceFinding(**dict(value))


def federation_assurance_from_mapping(value: Mapping[str, Any]) -> FederationAssurance:
    value = _mapping(value, "assurance")
    allowed = {"assurance_id", "version", "boundary", "federation_id", "federation_address", "verification_address", "runtime_address", "finding_count", "passed_count", "warning_count", "blocker_count", "state", "release_ready", "accepted", "findings", "content_address"}
    _strict_mapping(value, allowed, "assurance")
    findings = value.get("findings")
    if not isinstance(findings, Sequence) or isinstance(findings, (str, bytes)):
        raise ValidationError("assurance findings must be an array")
    body = dict(value)
    body["findings"] = tuple(federation_assurance_finding_from_mapping(item) for item in findings)
    return FederationAssurance(**body)


def federation_gate_check_from_mapping(value: Mapping[str, Any]) -> FederationGateCheck:
    value = _mapping(value, "gate check")
    _strict_mapping(value, {"ordinal", "check_id", "plane", "kind", "severity", "required", "passed", "expected", "observed", "detail", "remediation", "content_address"}, "gate check")
    return FederationGateCheck(**dict(value))


def federation_release_gate_from_mapping(value: Mapping[str, Any]) -> FederationReleaseGate:
    value = _mapping(value, "release gate")
    allowed = {"gate_id", "version", "boundary", "federation_id", "federation_address", "assurance_address", "verification_address", "runtime_address", "registry_count", "total_packet_count", "check_count", "passed_count", "warning_count", "blocker_count", "state", "release_ready", "accepted", "checks", "content_address"}
    _strict_mapping(value, allowed, "release gate")
    checks = value.get("checks")
    if not isinstance(checks, Sequence) or isinstance(checks, (str, bytes)):
        raise ValidationError("gate checks must be an array")
    body = dict(value)
    body["checks"] = tuple(federation_gate_check_from_mapping(item) for item in checks)
    return FederationReleaseGate(**body)


def assurance_gate_from_mapping(value: Mapping[str, Any]) -> FederationReleaseGate:
    value = _mapping(value, "assurance-gate bundle")
    _strict_mapping(value, {"assurance", "gate"}, "assurance-gate bundle")
    assurance = federation_assurance_from_mapping(_mapping(value.get("assurance"), "assurance-gate assurance"))
    gate = federation_release_gate_from_mapping(_mapping(value.get("gate"), "assurance-gate gate"))
    gate.assurance = assurance
    if gate.assurance_address != assurance.content_address:
        raise ValidationError("assurance-gate bundle linkage mismatch")
    return gate


def assurance_json(value: FederationAssurance) -> str:
    verify_federation_assurance(value)
    return canonical_json(value.to_dict())


def gate_json(value: FederationReleaseGate) -> str:
    verify_federation_release_gate(value)
    return canonical_json(value.to_dict())


def assurance_gate_json(value: FederationReleaseGate) -> str:
    verify_federation_assurance_gate(value)
    return canonical_json({"assurance": value.assurance.to_dict(), "gate": value.to_dict()})


def _csv_text(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field) for field in fields})
    return stream.getvalue()


def assurance_csv(value: FederationAssurance) -> str:
    verify_federation_assurance(value)
    fields = ("ordinal", "finding_id", "plane", "kind", "severity", "passed", "detail", "remediation", "content_address")
    return _csv_text([item.to_dict() for item in value.findings], fields)


def gate_csv(value: FederationReleaseGate) -> str:
    verify_federation_release_gate(value)
    fields = ("ordinal", "check_id", "plane", "kind", "severity", "required", "passed", "detail", "remediation", "content_address")
    return _csv_text([item.to_dict() for item in value.checks], fields)


def assurance_gate_csv(value: FederationReleaseGate) -> str:
    verify_federation_assurance_gate(value)
    fields = ("kind", "plane", "severity", "passed", "required", "detail", "remediation", "content_address")
    rows = [
        {"kind": item.kind, "plane": item.plane, "severity": item.severity, "passed": item.passed, "required": None, "detail": item.detail, "remediation": item.remediation, "content_address": item.content_address}
        for item in value.assurance.findings
    ] + [
        {"kind": item.kind, "plane": item.plane, "severity": item.severity, "passed": item.passed, "required": item.required, "detail": item.detail, "remediation": item.remediation, "content_address": item.content_address}
        for item in value.checks
    ]
    return _csv_text(rows, fields)


def render_assurance_markdown(value: FederationAssurance) -> str:
    verify_federation_assurance(value)
    lines = [
        "# Observatory Packet Registry Federation Assurance",
        "",
        f"- Federation: `{value.federation_id}`",
        f"- State: `{value.state}`",
        f"- Accepted: `{str(value.accepted).lower()}`",
        f"- Release ready: `{str(value.release_ready).lower()}`",
        f"- Findings: `{value.finding_count}` (passed `{value.passed_count}`, warnings `{value.warning_count}`, blockers `{value.blocker_count}`)",
        "",
        "| # | Plane | Kind | Severity | Passed | Detail |",
        "|---:|---|---|---|:---:|---|",
    ]
    lines.extend(f"| {item.ordinal} | {item.plane} | {item.kind} | {item.severity} | {str(item.passed).lower()} | {item.detail} |" for item in value.findings)
    return "\n".join(lines) + "\n"


def render_gate_markdown(value: FederationReleaseGate) -> str:
    verify_federation_release_gate(value)
    lines = [
        "# Observatory Packet Registry Federation Release Gate",
        "",
        f"- Federation: `{value.federation_id}`",
        f"- Decision: `{value.state}`",
        f"- Accepted: `{str(value.accepted).lower()}`",
        f"- Release ready: `{str(value.release_ready).lower()}`",
        f"- Checks: `{value.check_count}` (passed `{value.passed_count}`, warnings `{value.warning_count}`, blockers `{value.blocker_count}`)",
        "",
        "| # | Plane | Kind | Required | Severity | Passed | Detail |",
        "|---:|---|---|:---:|---|:---:|---|",
    ]
    lines.extend(f"| {item.ordinal} | {item.plane} | {item.kind} | {str(item.required).lower()} | {item.severity} | {str(item.passed).lower()} | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def render_assurance_gate_markdown(value: FederationReleaseGate) -> str:
    verify_federation_assurance_gate(value)
    return render_assurance_markdown(value.assurance) + "\n" + render_gate_markdown(value)


class AssuranceGateQuery:
    """Bounded query over assurance findings and gate checks."""

    def __init__(
        self,
        resource: str = "summary",
        *,
        severity: str | None = None,
        passed: bool | None = None,
        required: bool | None = None,
        plane: str | None = None,
        text: str | None = None,
        offset: int = 0,
        limit: int = DEFAULT_LIMIT,
    ) -> None:
        self.resource = _text(resource, "query resource", 64)
        if self.resource not in {"summary", "findings", "blockers", "warnings", "checks", "failed"}:
            raise ValidationError("query resource is invalid")
        if severity is not None and severity not in {item.value for item in AssuranceSeverity}:
            raise ValidationError("query severity is invalid")
        if passed is not None:
            _bool(passed, "query passed")
        if required is not None:
            _bool(required, "query required")
        self.severity = severity
        self.passed = passed
        self.required = required
        self.plane = _text(plane, "query plane", 64) if plane is not None else None
        self.text = _text(text, "query text", 256).casefold() if text is not None else None
        self.offset = _count(offset, "query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "query limit", MAX_QUERY_ITEMS, positive=True)
        self._validate()

    def _validate(self) -> None:
        if self.offset + self.limit > MAX_QUERY_ITEMS:
            raise ValidationError("query window is too large")

    def to_dict(self) -> dict[str, Any]:
        return {"resource": self.resource, "severity": self.severity, "passed": self.passed, "required": self.required, "plane": self.plane, "text": self.text, "offset": self.offset, "limit": self.limit}


def address_assurance_gate_query(value: AssuranceGateQuery) -> str:
    return content_hash(value.to_dict(), prefix=QUERY_PREFIX)


class AssuranceGateQueryResult:
    def __init__(self, query: AssuranceGateQuery, total_count: int, items: Sequence[Mapping[str, Any]], gate_address: str, assurance_address: str) -> None:
        self.query = query
        self.total_count = total_count
        self.items = tuple(dict(item) for item in items)
        self.returned_count = len(self.items)
        self.gate_address = gate_address
        self.assurance_address = assurance_address
        self.content_address = "pending:query"
        self.content_address = address_assurance_gate_query_result(self)
        self._validate()

    def _validate(self) -> None:
        _count(self.total_count, "query total count", MAX_QUERY_ITEMS)
        _count(self.returned_count, "query returned count", MAX_QUERY_ITEMS)
        if self.returned_count > self.total_count:
            raise ValidationError("query returned count exceeds total")
        _address(self.gate_address, "query gate address")
        _address(self.assurance_address, "query assurance address")
        if not _public(self.to_dict()):
            raise ValidationError("query crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"query": self.query.to_dict(), "total_count": self.total_count, "returned_count": self.returned_count, "items": list(self.items), "gate_address": self.gate_address, "assurance_address": self.assurance_address, "content_address": self.content_address}


def address_assurance_gate_query_result(value: AssuranceGateQueryResult) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX + "-result")


def _query_item_matches(item: Mapping[str, Any], query: AssuranceGateQuery) -> bool:
    if query.severity is not None and item.get("severity") != query.severity:
        return False
    if query.passed is not None and item.get("passed") != query.passed:
        return False
    if query.required is not None and item.get("required") != query.required:
        return False
    if query.plane is not None and item.get("plane") != query.plane:
        return False
    if query.text is not None:
        searchable = canonical_json({"kind": item.get("kind"), "detail": item.get("detail"), "remediation": item.get("remediation")}).casefold()
        if query.text not in searchable:
            return False
    return True


def _query_items(value: FederationReleaseGate, query: AssuranceGateQuery) -> tuple[dict[str, Any], ...]:
    verify_federation_assurance_gate(value)
    assurance = value.assurance
    if query.resource == "summary":
        return ({"assurance": assurance.summary(), "gate": value.summary()},)
    if query.resource in {"findings", "blockers", "warnings"}:
        items = [item.to_dict() | {"record_type": "finding"} for item in assurance.findings]
        if query.resource == "blockers":
            items = [item for item in items if item["severity"] == AssuranceSeverity.BLOCKER.value]
        elif query.resource == "warnings":
            items = [item for item in items if item["severity"] == AssuranceSeverity.WARNING.value]
    else:
        items = [item.to_dict() | {"record_type": "check"} for item in value.checks]
        if query.resource == "failed":
            items = [item for item in items if not item["passed"]]
    return tuple(item for item in items if _query_item_matches(item, query))


def query_assurance_gate(value: FederationReleaseGate, query: AssuranceGateQuery | None = None, **kwargs: Any) -> AssuranceGateQueryResult:
    if not isinstance(value, FederationReleaseGate):
        raise ValidationError("assurance-gate query requires typed gate")
    selected = query if query is not None else AssuranceGateQuery(**kwargs)
    if query is not None and kwargs:
        raise ValidationError("query object and keyword filters cannot be combined")
    all_items = _query_items(value, selected)
    page = all_items[selected.offset : selected.offset + selected.limit]
    return AssuranceGateQueryResult(selected, len(all_items), page, value.content_address, value.assurance_address)


def verify_assurance_gate_query(value: AssuranceGateQueryResult) -> AssuranceGateQueryResult:
    if not isinstance(value, AssuranceGateQueryResult):
        raise ValidationError("query verification requires typed query result")
    if address_assurance_gate_query_result(value) != value.content_address:
        raise ValidationError("query result address mismatch")
    return value


def query_json(value: AssuranceGateQueryResult) -> str:
    verify_assurance_gate_query(value)
    return canonical_json(value.to_dict())


def query_csv(value: AssuranceGateQueryResult) -> str:
    verify_assurance_gate_query(value)
    if not value.items:
        return ""
    keys = sorted({key for item in value.items for key in item})
    return _csv_text(value.items, keys)


def render_query_markdown(value: AssuranceGateQueryResult) -> str:
    verify_assurance_gate_query(value)
    lines = ["# Observatory Packet Registry Federation Assurance Gate Query", "", f"- Resource: `{value.query.resource}`", f"- Total: `{value.total_count}`", f"- Returned: `{value.returned_count}`", ""]
    if not value.items:
        return "\n".join(lines + ["No matching records.", ""])
    fields = sorted({key for item in value.items for key in item})
    lines.append("| " + " | ".join(fields) + " |")
    lines.append("|" + "|".join("---" for _ in fields) + "|")
    for item in value.items:
        lines.append("| " + " | ".join(str(item.get(field, "")) for field in fields) + " |")
    return "\n".join(lines) + "\n"


def _document_bytes(value: FederationReleaseGate) -> dict[str, bytes]:
    verify_federation_assurance_gate(value)
    return {ASSURANCE_NAME: canonical_bytes(value.assurance.to_dict()), GATE_NAME: canonical_bytes(value.to_dict())}


def _manifest_body(value: FederationReleaseGate, documents: Mapping[str, bytes]) -> dict[str, Any]:
    artifacts = tuple({"name": name, "bytes": len(documents[name]), "byte_address": hash_bytes(documents[name]), "file_address": _file_address(name, documents[name])} for name in (ASSURANCE_NAME, GATE_NAME))
    return {"version": VERSION, "boundary": BOUNDARY, "gate_id": value.gate_id, "federation_id": value.federation_id, "gate_address": value.content_address, "assurance_address": value.assurance_address, "artifact_count": len(artifacts), "artifacts": artifacts, "files": list(FILES), "manifest_address": None}


def _manifest_address(value: Mapping[str, Any]) -> str:
    return content_hash(dict(value), prefix=MANIFEST_PREFIX)


def write_federation_assurance_gate(value: FederationReleaseGate, directory: str | Path, *, overwrite: bool = False) -> Path:
    verify_federation_assurance_gate(value)
    destination = Path(directory)
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())) and not overwrite:
        raise ValidationError("assurance-gate destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    documents = _document_bytes(value)
    body = _manifest_body(value, documents)
    body["manifest_address"] = _manifest_address(body)
    manifest = canonical_bytes(body)
    temporary = Path(tempfile.mkdtemp(prefix=f".{GATE_PREFIX}-", dir=str(destination.parent)))
    try:
        for name, raw in ((ASSURANCE_NAME, documents[ASSURANCE_NAME]), (GATE_NAME, documents[GATE_NAME]), (MANIFEST_NAME, manifest)):
            (temporary / name).write_bytes(raw)
        if destination.exists():
            if not destination.is_dir() or any(destination.iterdir()):
                if not overwrite:
                    raise ValidationError("assurance-gate destination already exists")
                shutil.rmtree(destination)
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def _read_json(path: Path, field: str) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise ValidationError(f"{field} must be a regular file")
    raw = path.read_bytes()
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"{field} is not canonical JSON") from exc
    if canonical_bytes(value) != raw:
        raise ValidationError(f"{field} is not canonical JSON")
    return _mapping(value, field)  # type: ignore[return-value]


def load_federation_assurance_gate(directory: str | Path) -> FederationReleaseGate:
    source = Path(directory)
    if not source.is_dir() or source.is_symlink():
        raise ValidationError("assurance-gate input must be a directory")
    children = tuple(source.iterdir())
    if any(child.is_symlink() for child in children):
        raise ValidationError("assurance-gate directories cannot contain symlinks")
    if {child.name for child in children} != set(FILES):
        raise ValidationError("assurance-gate file set is invalid")
    manifest = _read_json(source / MANIFEST_NAME, "assurance-gate manifest")
    _strict_mapping(manifest, {"version", "boundary", "gate_id", "federation_id", "gate_address", "assurance_address", "artifact_count", "artifacts", "files", "manifest_address"}, "assurance-gate manifest")
    expected_manifest = dict(manifest)
    actual_manifest_address = expected_manifest.pop("manifest_address")
    expected_manifest["manifest_address"] = None
    if actual_manifest_address != _manifest_address(expected_manifest):
        raise ValidationError("assurance-gate manifest address mismatch")
    if manifest["version"] != VERSION or manifest["boundary"] != BOUNDARY or manifest["files"] != list(FILES) or manifest["artifact_count"] != 2:
        raise ValidationError("assurance-gate manifest metadata is invalid")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, Sequence) or isinstance(artifacts, (str, bytes)) or len(artifacts) != 2:
        raise ValidationError("assurance-gate artifacts are invalid")
    documents: dict[str, bytes] = {}
    for artifact in artifacts:
        item = _mapping(artifact, "assurance-gate artifact")
        _strict_mapping(item, {"name", "bytes", "byte_address", "file_address"}, "assurance-gate artifact")
        name = _text(item.get("name"), "artifact name", 64)
        if name not in {ASSURANCE_NAME, GATE_NAME} or name in documents:
            raise ValidationError("assurance-gate artifact name is invalid")
        raw = (source / name).read_bytes()
        if item.get("bytes") != len(raw) or item.get("byte_address") != hash_bytes(raw) or item.get("file_address") != _file_address(name, raw):
            raise ValidationError("assurance-gate artifact address mismatch")
        documents[name] = raw
    assurance = federation_assurance_from_mapping(_read_json(source / ASSURANCE_NAME, "assurance"))
    gate = federation_release_gate_from_mapping(_read_json(source / GATE_NAME, "gate"))
    gate.assurance = assurance
    if gate.content_address != manifest["gate_address"] or gate.assurance_address != manifest["assurance_address"] or assurance.content_address != gate.assurance_address:
        raise ValidationError("assurance-gate manifest linkage mismatch")
    verify_federation_assurance_gate(gate)
    return gate


def federation_assurance_gate_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Observatory Packet Registry Federation Assurance Gate", "type": "object", "additionalProperties": False, "required": ["assurance", "gate"], "properties": {"assurance": {"$ref": "#/$defs/assurance"}, "gate": {"$ref": "#/$defs/gate"}}, "$defs": {"address": {"type": "string", "pattern": "^[^:]+:.+$"}, "assurance": {"type": "object", "additionalProperties": True, "required": ["assurance_id", "federation_id", "findings", "content_address"]}, "gate": {"type": "object", "additionalProperties": True, "required": ["gate_id", "federation_id", "checks", "state", "content_address"]}}}


def federation_assurance_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Observatory Packet Registry Federation Assurance", "type": "object", "additionalProperties": False, "required": ["assurance_id", "version", "boundary", "federation_id", "federation_address", "verification_address", "runtime_address", "finding_count", "findings", "state", "release_ready", "accepted", "content_address"], "properties": {"assurance_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "federation_id": {"type": "string"}, "federation_address": {"type": "string"}, "verification_address": {"type": "string"}, "runtime_address": {"type": "string"}, "finding_count": {"type": "integer", "minimum": 1}, "findings": {"type": "array"}, "state": {"enum": [item.value for item in AssuranceState]}, "release_ready": {"type": "boolean"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def federation_gate_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Observatory Packet Registry Federation Release Gate", "type": "object", "additionalProperties": False, "required": ["gate_id", "version", "boundary", "federation_id", "federation_address", "assurance_address", "verification_address", "runtime_address", "registry_count", "total_packet_count", "check_count", "checks", "state", "release_ready", "accepted", "content_address"], "properties": {"gate_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "federation_id": {"type": "string"}, "federation_address": {"type": "string"}, "assurance_address": {"type": "string"}, "verification_address": {"type": "string"}, "runtime_address": {"type": "string"}, "registry_count": {"type": "integer", "minimum": 0}, "total_packet_count": {"type": "integer", "minimum": 0}, "check_count": {"type": "integer", "minimum": 1}, "checks": {"type": "array"}, "state": {"enum": [item.value for item in GateState]}, "release_ready": {"type": "boolean"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def federation_query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Observatory Packet Registry Federation Assurance Gate Query", "type": "object", "additionalProperties": False, "properties": {"resource": {"enum": ["summary", "findings", "blockers", "warnings", "checks", "failed"]}, "severity": {"enum": [item.value for item in AssuranceSeverity]}, "passed": {"type": ["boolean", "null"]}, "required": {"type": ["boolean", "null"]}, "plane": {"type": ["string", "null"]}, "text": {"type": ["string", "null"]}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}}}


def federation_assurance_gate_capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "assurance": {"independent_replay": True, "finding_count": 21, "severity_classes": [item.value for item in AssuranceSeverity], "states": [item.value for item in AssuranceState]}, "gate": {"decision_states": [item.value for item in GateState], "required_checks_block": True, "optional_checks_hold": True, "check_count": 15}, "persistence": {"exact_files": list(FILES), "canonical_json": True, "atomic_write": True, "symlink_rejected": True, "offline_load": True}, "queries": {"resources": ["summary", "findings", "blockers", "warnings", "checks", "failed"], "pagination": True, "text_filter": True, "csv": True, "markdown": True}, "public_boundary": {"path_free": True, "forbidden_keys": sorted(_FORBIDDEN_KEYS)}}


def federation_assurance_capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "independent_replay": True, "severity_classes": [item.value for item in AssuranceSeverity], "states": [item.value for item in AssuranceState], "finding_count": 21}


def federation_gate_capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "decision_states": [item.value for item in GateState], "required_checks_block": True, "optional_checks_hold": True, "check_count": 15}


def federation_query_capabilities() -> dict[str, Any]:
    return {"resources": ["summary", "findings", "blockers", "warnings", "checks", "failed"], "pagination": True, "severity_filter": True, "passed_filter": True, "required_filter": True, "plane_filter": True, "text_filter": True, "csv": True, "markdown": True}


# Descriptive long aliases retain the repository's module-boundary naming
# convention while the compact names above keep integrations readable.
module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance = build_federation_assurance
module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_gate = build_federation_release_gate
build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance = build_federation_assurance
build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_release_gate = build_federation_release_gate
build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate = build_federation_assurance_gate
build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_from_directory = build_federation_assurance_gate_from_directory
verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance = verify_federation_assurance
verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_release_gate = verify_federation_release_gate
verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate = verify_federation_assurance_gate
write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate = write_federation_assurance_gate
load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate = load_federation_assurance_gate
module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_schema = federation_assurance_gate_schema
module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_schema = federation_assurance_schema
module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_gate_schema = federation_gate_schema
module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_query_schema = federation_query_schema
module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_capabilities = federation_assurance_gate_capabilities
module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_capabilities = federation_assurance_capabilities
module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_gate_capabilities = federation_gate_capabilities
module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_query_capabilities = federation_query_capabilities
assurance_gate_capabilities = federation_assurance_gate_capabilities
assurance_gate_schema = federation_assurance_gate_schema


__all__ = [
    "AssuranceGateQuery",
    "AssuranceGateQueryResult",
    "AssuranceSeverity",
    "AssuranceState",
    "FederationAssurance",
    "FederationAssuranceFinding",
    "FederationGateCheck",
    "FederationReleaseGate",
    "GatePlane",
    "GateState",
    "address_assurance_gate_query",
    "address_assurance_gate_query_result",
    "address_federation_assurance",
    "address_federation_assurance_finding",
    "address_federation_gate_check",
    "address_federation_release_gate",
    "assurance_csv",
    "assurance_gate_csv",
    "assurance_gate_from_mapping",
    "assurance_gate_json",
    "assurance_json",
    "build_federation_assurance",
    "build_federation_assurance_gate",
    "build_federation_assurance_gate_from_directory",
    "build_federation_release_gate",
    "federation_assurance_capabilities",
    "federation_assurance_finding_from_mapping",
    "federation_assurance_from_mapping",
    "federation_assurance_gate_capabilities",
    "federation_assurance_gate_schema",
    "federation_assurance_schema",
    "federation_gate_capabilities",
    "federation_gate_check_from_mapping",
    "federation_gate_schema",
    "federation_query_capabilities",
    "federation_query_schema",
    "federation_release_gate_from_mapping",
    "gate_csv",
    "gate_json",
    "load_federation_assurance_gate",
    "query_assurance_gate",
    "query_csv",
    "query_json",
    "render_assurance_gate_markdown",
    "render_assurance_markdown",
    "render_gate_markdown",
    "render_query_markdown",
    "verify_assurance_gate_query",
    "verify_federation_assurance",
    "verify_federation_assurance_gate",
    "verify_federation_release_gate",
    "write_federation_assurance_gate",
]
