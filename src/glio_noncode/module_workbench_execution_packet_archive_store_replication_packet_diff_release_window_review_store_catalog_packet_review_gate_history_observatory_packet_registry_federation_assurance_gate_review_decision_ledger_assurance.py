"""Independently assure and gate federation review decision ledgers.

The decision ledger records operational adjudication, but its own closure must
not be accepted merely because the ledger says that it is closed.  This module
recomputes the important invariants outside the decision builder and converts
them into addressed findings and a small release gate.  It keeps the source
review queue authoritative: a completely adjudicated non-ready queue remains
non-promotable until a new verified queue is supplied.

The assurance plane is deliberately public and path-free.  It retains only
content addresses, bounded explanations, fixed-vocabulary states, and
deterministic receipt links.  Its portable handoff contains exactly
``manifest.json``, ``assurance.json``, and ``gate.json``.
"""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
import json
import os
import shutil
import tempfile
from collections.abc import Callable, Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Any

from . import (
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_review_decision_ledger as decision_model,
)
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes

FederationReviewDecisionLedger = decision_model.FederationReviewDecisionLedger
FederationReviewDecisionEntry = decision_model.FederationReviewDecisionEntry

VERSION = decision_model.VERSION + "-assurance-v1"
BOUNDARY = "public_registry_federation_assurance_gate_review_decision_ledger_assurance"
ASSURANCE_PREFIX = decision_model.DECISION_PREFIX + "-assurance"
FINDING_PREFIX = ASSURANCE_PREFIX + "-finding"
GATE_PREFIX = ASSURANCE_PREFIX + "-gate"
CHECK_PREFIX = GATE_PREFIX + "-check"
QUERY_PREFIX = GATE_PREFIX + "-query"
MANIFEST_PREFIX = GATE_PREFIX + "-manifest"
DIFF_ITEM_PREFIX = ASSURANCE_PREFIX + "-diff-item"
DIFF_PREFIX = ASSURANCE_PREFIX + "-diff"
DIFF_QUERY_PREFIX = DIFF_PREFIX + "-query"
DIFF_MANIFEST_PREFIX = DIFF_PREFIX + "-manifest"
MANIFEST_NAME = "manifest.json"
ASSURANCE_NAME = "assurance.json"
GATE_NAME = "gate.json"
DIFF_NAME = "diff.json"
FILES = (MANIFEST_NAME, ASSURANCE_NAME, GATE_NAME)
DIFF_FILES = (MANIFEST_NAME, DIFF_NAME)
MAX_FINDINGS = 32
MAX_CHECKS = 32
MAX_DIFF_ITEMS = MAX_FINDINGS + MAX_CHECKS
MAX_QUERY_ITEMS = 4096
DEFAULT_LIMIT = 50

_FORBIDDEN_KEYS = frozenset({"agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "token", "user"})


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


class AssurancePlane(StrEnum):
    LEDGER = "ledger"
    QUEUE = "queue"
    ENTRIES = "entries"
    POLICY = "policy"
    PUBLIC = "public"
    PERSISTENCE = "persistence"


class AssuranceDiffAction(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    UNCHANGED = "unchanged"
    CHANGED = "changed"


class AssuranceDiffState(StrEnum):
    UNCHANGED = "unchanged"
    IMPROVED = "improved"
    REGRESSED = "regressed"
    CHANGED = "changed"


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value.strip()


def _address(value: Any, field: str) -> str:
    value = _text(value, field)
    if ":" not in value or value.endswith(":"):
        raise ValidationError(f"{field} must be an address")
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
        raise ValidationError(f"{field} has unknown fields: {sorted(unknown)}")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in _FORBIDDEN_KEYS and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    return True


def _severity(value: Any, field: str = "assurance severity") -> str:
    value = _text(value, field, 32)
    if value not in {item.value for item in AssuranceSeverity}:
        raise ValidationError(f"{field} is invalid")
    return value


def _state(value: Any, field: str = "assurance state") -> str:
    value = _text(value, field, 32)
    if value not in {item.value for item in AssuranceState}:
        raise ValidationError(f"{field} is invalid")
    return value


def _gate_state(value: Any, field: str = "gate state") -> str:
    value = _text(value, field, 32)
    if value not in {item.value for item in GateState}:
        raise ValidationError(f"{field} is invalid")
    return value


class DecisionAssuranceFinding:
    """One independently recomputed decision-ledger finding."""

    def __init__(self, ordinal: int, finding_id: str, plane: str, kind: str, severity: str, required: bool, passed: bool, detail: str, remediation: str, evidence_address: str, content_address: str) -> None:
        self.ordinal = ordinal
        self.finding_id = finding_id
        self.plane = plane
        self.kind = kind
        self.severity = severity
        self.required = required
        self.passed = passed
        self.detail = detail
        self.remediation = remediation
        self.evidence_address = evidence_address
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "assurance finding ordinal", MAX_FINDINGS)
        _text(self.finding_id, "assurance finding ID", 256)
        if self.plane not in {item.value for item in AssurancePlane}:
            raise ValidationError("assurance finding plane is invalid")
        _text(self.kind, "assurance finding kind", 128)
        severity = _severity(self.severity)
        _bool(self.required, "assurance finding required flag")
        _bool(self.passed, "assurance finding passed flag")
        if self.passed and severity != AssuranceSeverity.PASS.value:
            raise ValidationError("passed finding must have pass severity")
        if not self.passed and severity == AssuranceSeverity.PASS.value:
            raise ValidationError("failed finding cannot have pass severity")
        if not self.passed and self.required and severity != AssuranceSeverity.BLOCKER.value:
            raise ValidationError("required failed finding must be a blocker")
        if not self.passed and not self.required and severity != AssuranceSeverity.WARNING.value:
            raise ValidationError("optional failed finding must be a warning")
        _text(self.detail, "assurance finding detail", 2048)
        _text(self.remediation, "assurance finding remediation", 2048)
        _address(self.evidence_address, "assurance finding evidence address")
        _address(self.content_address, "assurance finding address")
        if not _public(self.to_dict()):
            raise ValidationError("assurance finding crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "finding_id": self.finding_id, "plane": self.plane, "kind": self.kind, "severity": self.severity, "required": self.required, "passed": self.passed, "detail": self.detail, "remediation": self.remediation, "evidence_address": self.evidence_address, "content_address": self.content_address}


def address_assurance_finding(value: DecisionAssuranceFinding) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=FINDING_PREFIX)


class DecisionAssurance:
    """Independent finding report for one decision ledger."""

    def __init__(self, assurance_id: str, version: str, boundary: str, ledger_id: str, ledger_address: str, queue_address: str, finding_count: int, passed_count: int, warning_count: int, blocker_count: int, state: str, accepted: bool, release_ready: bool, findings: Sequence[DecisionAssuranceFinding], content_address: str) -> None:
        self.assurance_id = assurance_id
        self.version = version
        self.boundary = boundary
        self.ledger_id = ledger_id
        self.ledger_address = ledger_address
        self.queue_address = queue_address
        self.finding_count = finding_count
        self.passed_count = passed_count
        self.warning_count = warning_count
        self.blocker_count = blocker_count
        self.state = state
        self.accepted = accepted
        self.release_ready = release_ready
        self.findings = tuple(findings)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.assurance_id, "assurance ID", 256)
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("decision assurance contract is invalid")
        _text(self.ledger_id, "assurance ledger ID", 256)
        _address(self.ledger_address, "assurance ledger address")
        _address(self.queue_address, "assurance queue address")
        _count(self.finding_count, "assurance finding count", MAX_FINDINGS, positive=True)
        if self.finding_count != len(self.findings):
            raise ValidationError("assurance finding count is not conserved")
        for count, field in ((self.passed_count, "passed count"), (self.warning_count, "warning count"), (self.blocker_count, "blocker count")):
            _count(count, f"assurance {field}", MAX_FINDINGS)
        if self.passed_count + self.warning_count + self.blocker_count != self.finding_count:
            raise ValidationError("assurance severity counts are not conserved")
        for ordinal, finding in enumerate(self.findings):
            if not isinstance(finding, DecisionAssuranceFinding) or finding.ordinal != ordinal:
                raise ValidationError("assurance finding ordinals are not contiguous")
            if address_assurance_finding(finding) != finding.content_address:
                raise ValidationError("assurance finding address mismatch")
        expected_state = AssuranceState.BLOCKED.value if self.blocker_count else AssuranceState.WARNING.value if self.warning_count else AssuranceState.PASSED.value
        if self.state != expected_state:
            raise ValidationError("assurance state is invalid")
        if self.accepted != (self.blocker_count == 0):
            raise ValidationError("assurance acceptance is invalid")
        if self.release_ready != (self.state == AssuranceState.PASSED.value):
            raise ValidationError("assurance readiness is invalid")
        _address(self.content_address, "assurance address")
        if not _public(self.to_dict()):
            raise ValidationError("decision assurance crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {"assurance_id": self.assurance_id, "version": self.version, "boundary": self.boundary, "ledger_id": self.ledger_id, "ledger_address": self.ledger_address, "queue_address": self.queue_address, "finding_count": self.finding_count, "passed_count": self.passed_count, "warning_count": self.warning_count, "blocker_count": self.blocker_count, "state": self.state, "accepted": self.accepted, "release_ready": self.release_ready, "content_address": self.content_address}

    def to_dict(self, *, include_findings: bool = True) -> dict[str, Any]:
        body = self.summary()
        if include_findings:
            body["findings"] = [finding.to_dict() for finding in self.findings]
        return body


def address_decision_assurance(value: DecisionAssurance) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ASSURANCE_PREFIX)


class DecisionGateCheck:
    """One required or optional check in the decision assurance gate."""

    def __init__(self, ordinal: int, check_id: str, plane: str, kind: str, required: bool, passed: bool, detail: str, evidence_address: str, content_address: str) -> None:
        self.ordinal = ordinal
        self.check_id = check_id
        self.plane = plane
        self.kind = kind
        self.required = required
        self.passed = passed
        self.detail = detail
        self.evidence_address = evidence_address
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "gate check ordinal", MAX_CHECKS)
        _text(self.check_id, "gate check ID", 256)
        if self.plane not in {item.value for item in AssurancePlane}:
            raise ValidationError("gate check plane is invalid")
        _text(self.kind, "gate check kind", 128)
        _bool(self.required, "gate check required flag")
        _bool(self.passed, "gate check passed flag")
        _text(self.detail, "gate check detail", 2048)
        _address(self.evidence_address, "gate check evidence address")
        _address(self.content_address, "gate check address")
        if not _public(self.to_dict()):
            raise ValidationError("gate check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "check_id": self.check_id, "plane": self.plane, "kind": self.kind, "required": self.required, "passed": self.passed, "detail": self.detail, "evidence_address": self.evidence_address, "content_address": self.content_address}


def address_gate_check(value: DecisionGateCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DecisionReleaseGate:
    """Promote/hold/block decision for an assured review ledger."""

    def __init__(self, gate_id: str, version: str, boundary: str, ledger_id: str, ledger_address: str, assurance_address: str, source_queue_release_ready: bool, check_count: int, passed_count: int, warning_count: int, blocker_count: int, state: str, accepted: bool, release_ready: bool, checks: Sequence[DecisionGateCheck], content_address: str) -> None:
        self.gate_id = gate_id
        self.version = version
        self.boundary = boundary
        self.ledger_id = ledger_id
        self.ledger_address = ledger_address
        self.assurance_address = assurance_address
        self.source_queue_release_ready = source_queue_release_ready
        self.check_count = check_count
        self.passed_count = passed_count
        self.warning_count = warning_count
        self.blocker_count = blocker_count
        self.state = state
        self.accepted = accepted
        self.release_ready = release_ready
        self.checks = tuple(checks)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.gate_id, "decision gate ID", 256)
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("decision gate contract is invalid")
        _text(self.ledger_id, "decision gate ledger ID", 256)
        _address(self.ledger_address, "decision gate ledger address")
        _address(self.assurance_address, "decision gate assurance address")
        _bool(self.source_queue_release_ready, "decision gate source readiness")
        _count(self.check_count, "decision gate check count", MAX_CHECKS, positive=True)
        if self.check_count != len(self.checks):
            raise ValidationError("decision gate check count is not conserved")
        for count, field in ((self.passed_count, "passed count"), (self.warning_count, "warning count"), (self.blocker_count, "blocker count")):
            _count(count, f"decision gate {field}", MAX_CHECKS)
        if self.passed_count + self.warning_count + self.blocker_count != self.check_count:
            raise ValidationError("decision gate counts are not conserved")
        for ordinal, check in enumerate(self.checks):
            if not isinstance(check, DecisionGateCheck) or check.ordinal != ordinal:
                raise ValidationError("decision gate check ordinals are not contiguous")
            if address_gate_check(check) != check.content_address:
                raise ValidationError("decision gate check address mismatch")
        required_failures = sum(not check.passed and check.required for check in self.checks)
        optional_failures = sum(not check.passed and not check.required for check in self.checks)
        expected_state = GateState.BLOCK.value if required_failures else GateState.HOLD.value if optional_failures else GateState.PROMOTE.value
        if self.state != expected_state:
            raise ValidationError("decision gate state is invalid")
        if self.accepted != (required_failures == 0):
            raise ValidationError("decision gate acceptance is invalid")
        if self.release_ready != (self.state == GateState.PROMOTE.value):
            raise ValidationError("decision gate readiness is invalid")
        _address(self.content_address, "decision gate address")
        if not _public(self.to_dict()):
            raise ValidationError("decision gate crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {"gate_id": self.gate_id, "version": self.version, "boundary": self.boundary, "ledger_id": self.ledger_id, "ledger_address": self.ledger_address, "assurance_address": self.assurance_address, "source_queue_release_ready": self.source_queue_release_ready, "check_count": self.check_count, "passed_count": self.passed_count, "warning_count": self.warning_count, "blocker_count": self.blocker_count, "state": self.state, "accepted": self.accepted, "release_ready": self.release_ready, "content_address": self.content_address}

    def to_dict(self, *, include_checks: bool = True) -> dict[str, Any]:
        body = self.summary()
        if include_checks:
            body["checks"] = [check.to_dict() for check in self.checks]
        return body


def address_decision_gate(value: DecisionReleaseGate) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=GATE_PREFIX)


class DecisionAssuranceGate:
    """Combined independent assurance and release gate projection."""

    def __init__(self, assurance: DecisionAssurance, gate: DecisionReleaseGate, content_address: str) -> None:
        self.assurance = assurance
        self.gate = gate
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        verify_decision_assurance(self.assurance)
        verify_decision_gate(self.gate)
        if self.gate.assurance_address != self.assurance.content_address or self.gate.ledger_address != self.assurance.ledger_address:
            raise ValidationError("decision assurance and gate linkage is invalid")
        _address(self.content_address, "decision assurance gate address")
        if not _public(self.to_dict()):
            raise ValidationError("decision assurance gate crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {"assurance": self.assurance.summary(), "gate": self.gate.summary(), "content_address": self.content_address}

    def to_dict(self) -> dict[str, Any]:
        return {"assurance": self.assurance.to_dict(), "gate": self.gate.to_dict(), "content_address": self.content_address}


def address_decision_assurance_gate(value: DecisionAssuranceGate) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ASSURANCE_PREFIX + "-gate-bundle")


def _check_finding(ordinal: int, ledger: FederationReviewDecisionLedger, kind: str, plane: str, passed: bool, required: bool, detail: str, remediation: str) -> DecisionAssuranceFinding:
    severity = AssuranceSeverity.PASS.value if passed else AssuranceSeverity.BLOCKER.value if required else AssuranceSeverity.WARNING.value
    body = {"ordinal": ordinal, "finding_id": f"{ledger.ledger_id}:assurance:{ordinal}", "plane": plane, "kind": kind, "severity": severity, "required": required, "passed": passed, "detail": detail, "remediation": remediation, "evidence_address": ledger.content_address}
    provisional = DecisionAssuranceFinding(**body, content_address="pending:finding")
    return DecisionAssuranceFinding(**body, content_address=address_assurance_finding(provisional))


def _safe_check(operation: Callable[[], bool]) -> bool:
    try:
        return bool(operation())
    except (ValidationError, KeyError, TypeError, AttributeError):
        return False


def build_decision_assurance(ledger: FederationReviewDecisionLedger, *, assurance_id: str = "glio-noncode-observatory-registry-federation-review-decision-assurance") -> DecisionAssurance:
    if not isinstance(ledger, FederationReviewDecisionLedger):
        raise ValidationError("decision assurance requires a typed ledger")
    findings: list[DecisionAssuranceFinding] = []
    findings.append(_check_finding(0, ledger, "ledger-address", AssurancePlane.LEDGER.value, _safe_check(lambda: decision_model.address_decision_ledger(ledger) == ledger.content_address), True, "ledger content address recomputes", "rebuild the ledger with its canonical address"))
    findings.append(_check_finding(1, ledger, "queue-linkage", AssurancePlane.QUEUE.value, _safe_check(lambda: bool(ledger.queue_address and ledger.queue_id and ledger.item_count == len(ledger.items))), True, "queue identity and item count are linked", "restore the queue linkage and conserved item count"))
    findings.append(_check_finding(2, ledger, "item-addresses", AssurancePlane.QUEUE.value, _safe_check(lambda: all(decision_model.address_decision_item(item) == item.content_address for item in ledger.items)), True, "every queue item address recomputes", "repair or regenerate the queue-item snapshot"))
    findings.append(_check_finding(3, ledger, "entry-chain", AssurancePlane.ENTRIES.value, _safe_check(lambda: all(decision_model.address_decision_entry(entry) == entry.content_address and (entry.ordinal == 0 and entry.previous_head_address is None or entry.ordinal > 0 and entry.previous_head_address == ledger.entries[entry.ordinal - 1].content_address) for entry in ledger.entries)), True, "entry addresses and previous-head links form one chain", "repair the append-only decision chain"))
    findings.append(_check_finding(4, ledger, "entry-item-linkage", AssurancePlane.ENTRIES.value, _safe_check(lambda: all(any(item.content_address == entry.item_address and item.record_id == entry.record_id and item.kind == entry.kind for item in ledger.items) for entry in ledger.entries)), True, "every decision entry matches a queue item", "append decisions only against the retained queue snapshot"))
    findings.append(_check_finding(5, ledger, "evidence-rules", AssurancePlane.POLICY.value, _safe_check(lambda: all(entry.action != "remediate" or entry.evidence_address is not None for entry in ledger.entries)), True, "remediation entries carry evidence addresses", "add a valid evidence address before remediation"))
    findings.append(_check_finding(6, ledger, "waiver-policy", AssurancePlane.POLICY.value, _safe_check(lambda: all(entry.action != "waive" or entry.source_state == "review" and entry.source_priority != "critical" for entry in ledger.entries)), True, "waivers remain limited to non-critical warnings", "replace the invalid waiver with remediation or escalation"))
    findings.append(_check_finding(7, ledger, "head-closure", AssurancePlane.ENTRIES.value, _safe_check(lambda: ledger.head_address == (ledger.entries[-1].content_address if ledger.entries else None)), True, "ledger head matches its terminal entry", "recompute the ledger head"))
    findings.append(_check_finding(8, ledger, "count-conservation", AssurancePlane.LEDGER.value, _safe_check(lambda: ledger.open_count + ledger.closed_count == ledger.item_count and ledger.entry_count == len(ledger.entries)), True, "open, closed, and entry counts are conserved", "replay entries and restore conserved counters"))
    findings.append(_check_finding(9, ledger, "closure-readiness", AssurancePlane.POLICY.value, _safe_check(lambda: ledger.release_ready == (ledger.queue_release_ready and ledger.state == "closed")), False, "ledger readiness preserves source queue authority", "supply a release-ready source queue before promotion"))
    findings.append(_check_finding(10, ledger, "public-boundary", AssurancePlane.PUBLIC.value, _safe_check(lambda: _public(ledger.to_dict())), True, "ledger projection contains only public fields", "remove private or identity-like fields from the projection"))
    findings.append(_check_finding(11, ledger, "state-replay", AssurancePlane.LEDGER.value, _safe_check(lambda: ledger.state in {"open", "closed", "blocked"} and ledger.accepted == (ledger.blocked_count == 0) and ledger.accepted), True, "effective state is accepted and replay-consistent", "resolve the active blocker before accepting the ledger"))
    passed = sum(finding.passed for finding in findings)
    warning = sum(not finding.passed and not finding.required for finding in findings)
    blocker = sum(not finding.passed and finding.required for finding in findings)
    state = AssuranceState.BLOCKED.value if blocker else AssuranceState.WARNING.value if warning else AssuranceState.PASSED.value
    body = {"assurance_id": _text(assurance_id, "assurance ID", 256), "version": VERSION, "boundary": BOUNDARY, "ledger_id": ledger.ledger_id, "ledger_address": ledger.content_address, "queue_address": ledger.queue_address, "finding_count": len(findings), "passed_count": passed, "warning_count": warning, "blocker_count": blocker, "state": state, "accepted": blocker == 0, "release_ready": state == AssuranceState.PASSED.value, "findings": tuple(findings)}
    provisional = DecisionAssurance(**body, content_address="pending:assurance")
    return DecisionAssurance(**body, content_address=address_decision_assurance(provisional))


def _check_gate(ordinal: int, gate_id: str, kind: str, passed: bool, required: bool, detail: str, evidence_address: str) -> DecisionGateCheck:
    body = {"ordinal": ordinal, "check_id": f"{gate_id}:check:{ordinal}", "plane": AssurancePlane.POLICY.value if kind in {"source-queue-readiness", "ledger-closure", "no-unreviewed", "no-escalated"} else AssurancePlane.LEDGER.value, "kind": kind, "required": required, "passed": passed, "detail": detail, "evidence_address": evidence_address}
    provisional = DecisionGateCheck(**body, content_address="pending:check")
    return DecisionGateCheck(**body, content_address=address_gate_check(provisional))


def build_decision_gate(ledger: FederationReviewDecisionLedger, assurance: DecisionAssurance, *, gate_id: str = "glio-noncode-observatory-registry-federation-review-decision-gate") -> DecisionReleaseGate:
    if not isinstance(ledger, FederationReviewDecisionLedger) or not isinstance(assurance, DecisionAssurance):
        raise ValidationError("decision gate requires typed ledger and assurance")
    verify_decision_assurance(assurance)
    checks = (
        _check_gate(0, gate_id, "assurance-accepted", assurance.accepted, True, "independent assurance has no blocker findings", assurance.content_address),
        _check_gate(1, gate_id, "assurance-release-ready", assurance.release_ready, True, "independent assurance is warning-free", assurance.content_address),
        _check_gate(2, gate_id, "source-queue-readiness", ledger.queue_release_ready, False, "source queue remains authoritative for promotion", ledger.content_address),
        _check_gate(3, gate_id, "ledger-closure", ledger.state == "closed", False, "all operationally required items are closed", ledger.content_address),
        _check_gate(4, gate_id, "no-unreviewed", ledger.unreviewed_count == 0, False, "no open source item lacks a decision entry", ledger.content_address),
        _check_gate(5, gate_id, "no-escalated", ledger.escalated_count == 0, False, "no item remains escalated", ledger.content_address),
        _check_gate(6, gate_id, "head-continuity", ledger.head_address == (ledger.entries[-1].content_address if ledger.entries else None), True, "decision head is terminal", ledger.content_address),
        _check_gate(7, gate_id, "public-boundary", _public(ledger.to_dict()) and _public(assurance.to_dict()), True, "ledger and assurance projections are public", assurance.content_address),
    )
    passed = sum(check.passed for check in checks)
    warning = sum(not check.passed and not check.required for check in checks)
    blocker = sum(not check.passed and check.required for check in checks)
    state = GateState.BLOCK.value if blocker else GateState.HOLD.value if warning else GateState.PROMOTE.value
    body = {"gate_id": _text(gate_id, "gate ID", 256), "version": VERSION, "boundary": BOUNDARY, "ledger_id": ledger.ledger_id, "ledger_address": ledger.content_address, "assurance_address": assurance.content_address, "source_queue_release_ready": ledger.queue_release_ready, "check_count": len(checks), "passed_count": passed, "warning_count": warning, "blocker_count": blocker, "state": state, "accepted": blocker == 0, "release_ready": state == GateState.PROMOTE.value, "checks": checks}
    provisional = DecisionReleaseGate(**body, content_address="pending:gate")
    return DecisionReleaseGate(**body, content_address=address_decision_gate(provisional))


def build_decision_assurance_gate(ledger: FederationReviewDecisionLedger, *, assurance_id: str = "glio-noncode-observatory-registry-federation-review-decision-assurance", gate_id: str = "glio-noncode-observatory-registry-federation-review-decision-gate") -> DecisionAssuranceGate:
    assurance = build_decision_assurance(ledger, assurance_id=assurance_id)
    gate = build_decision_gate(ledger, assurance, gate_id=gate_id)
    provisional = DecisionAssuranceGate(assurance, gate, content_address="pending:bundle")
    return DecisionAssuranceGate(assurance, gate, content_address=address_decision_assurance_gate(provisional))


def verify_decision_assurance(value: DecisionAssurance) -> DecisionAssurance:
    if not isinstance(value, DecisionAssurance):
        raise ValidationError("decision assurance verification requires a typed assurance")
    for finding in value.findings:
        if address_assurance_finding(finding) != finding.content_address:
            raise ValidationError("decision assurance finding address mismatch")
    if address_decision_assurance(value) != value.content_address:
        raise ValidationError("decision assurance address mismatch")
    return value


def verify_decision_gate(value: DecisionReleaseGate) -> DecisionReleaseGate:
    if not isinstance(value, DecisionReleaseGate):
        raise ValidationError("decision gate verification requires a typed gate")
    for check in value.checks:
        if address_gate_check(check) != check.content_address:
            raise ValidationError("decision gate check address mismatch")
    if address_decision_gate(value) != value.content_address:
        raise ValidationError("decision gate address mismatch")
    return value


def verify_decision_assurance_gate(value: DecisionAssuranceGate) -> DecisionAssuranceGate:
    if not isinstance(value, DecisionAssuranceGate):
        raise ValidationError("decision assurance gate verification requires a typed bundle")
    value._validate()
    if address_decision_assurance_gate(value) != value.content_address:
        raise ValidationError("decision assurance gate address mismatch")
    return value


def _optional_bool(value: Any, field: str) -> bool | None:
    if value is None:
        return None
    return _bool(value, field)


class DecisionAssuranceDiffItem:
    """One stable assurance or gate record in a snapshot comparison."""

    def __init__(self, ordinal: int, action: str, key: str, plane: str, kind: str, baseline_severity: str | None, candidate_severity: str | None, baseline_required: bool | None, candidate_required: bool | None, baseline_passed: bool | None, candidate_passed: bool | None, baseline_address: str | None, candidate_address: str | None, detail: str, content_address: str) -> None:
        self.ordinal = ordinal
        self.action = action
        self.key = key
        self.plane = plane
        self.kind = kind
        self.baseline_severity = baseline_severity
        self.candidate_severity = candidate_severity
        self.baseline_required = baseline_required
        self.candidate_required = candidate_required
        self.baseline_passed = baseline_passed
        self.candidate_passed = candidate_passed
        self.baseline_address = baseline_address
        self.candidate_address = candidate_address
        self.detail = detail
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "assurance diff item ordinal", MAX_DIFF_ITEMS)
        action = _text(self.action, "assurance diff item action", 32)
        if action not in {item.value for item in AssuranceDiffAction}:
            raise ValidationError("assurance diff item action is invalid")
        _text(self.key, "assurance diff item key", 256)
        _text(self.plane, "assurance diff item plane", 64)
        _text(self.kind, "assurance diff item kind", 128)
        for value, field in ((self.baseline_severity, "baseline severity"), (self.candidate_severity, "candidate severity")):
            if value is not None:
                _severity(value, field)
        for value, field in ((self.baseline_required, "baseline required"), (self.candidate_required, "candidate required"), (self.baseline_passed, "baseline passed"), (self.candidate_passed, "candidate passed")):
            _optional_bool(value, field)
        for value, field in ((self.baseline_address, "baseline assurance address"), (self.candidate_address, "candidate assurance address")):
            if value is not None:
                _address(value, field)
        _text(self.detail, "assurance diff item detail", 2048)
        _address(self.content_address, "assurance diff item address")
        if action == AssuranceDiffAction.ADDED.value and self.candidate_address is None:
            raise ValidationError("added assurance diff item requires a candidate")
        if action == AssuranceDiffAction.REMOVED.value and self.baseline_address is None:
            raise ValidationError("removed assurance diff item requires a baseline")
        if action in {AssuranceDiffAction.UNCHANGED.value, AssuranceDiffAction.CHANGED.value} and (self.baseline_address is None or self.candidate_address is None):
            raise ValidationError("matched assurance diff item requires both snapshots")
        if not _public(self.to_dict()):
            raise ValidationError("assurance diff item crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "action": self.action, "key": self.key, "plane": self.plane, "kind": self.kind, "baseline_severity": self.baseline_severity, "candidate_severity": self.candidate_severity, "baseline_required": self.baseline_required, "candidate_required": self.candidate_required, "baseline_passed": self.baseline_passed, "candidate_passed": self.candidate_passed, "baseline_address": self.baseline_address, "candidate_address": self.candidate_address, "detail": self.detail, "content_address": self.content_address}


def address_decision_assurance_diff_item(value: DecisionAssuranceDiffItem) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_ITEM_PREFIX)


class DecisionAssuranceDiff:
    """Addressed structural diff for two independently assured snapshots."""

    def __init__(self, diff_id: str, version: str, boundary: str, baseline_address: str, candidate_address: str, baseline_ledger_address: str, candidate_ledger_address: str, baseline_state: str, candidate_state: str, item_count: int, added_count: int, removed_count: int, unchanged_count: int, changed_count: int, improved_count: int, regressed_count: int, state: str, items: Sequence[DecisionAssuranceDiffItem], content_address: str) -> None:
        self.diff_id = diff_id
        self.version = version
        self.boundary = boundary
        self.baseline_address = baseline_address
        self.candidate_address = candidate_address
        self.baseline_ledger_address = baseline_ledger_address
        self.candidate_ledger_address = candidate_ledger_address
        self.baseline_state = baseline_state
        self.candidate_state = candidate_state
        self.item_count = item_count
        self.added_count = added_count
        self.removed_count = removed_count
        self.unchanged_count = unchanged_count
        self.changed_count = changed_count
        self.improved_count = improved_count
        self.regressed_count = regressed_count
        self.state = state
        self.items = tuple(items)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.diff_id, "assurance diff ID", 256)
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("assurance diff contract is invalid")
        for value, field in ((self.baseline_address, "baseline assurance gate address"), (self.candidate_address, "candidate assurance gate address"), (self.baseline_ledger_address, "baseline ledger address"), (self.candidate_ledger_address, "candidate ledger address")):
            _address(value, field)
        _state(self.baseline_state, "baseline assurance state")
        _state(self.candidate_state, "candidate assurance state")
        _count(self.item_count, "assurance diff item count", MAX_DIFF_ITEMS)
        if self.item_count != len(self.items):
            raise ValidationError("assurance diff item count is not conserved")
        counts = {item.value: 0 for item in AssuranceDiffAction}
        for ordinal, item in enumerate(self.items):
            if not isinstance(item, DecisionAssuranceDiffItem) or item.ordinal != ordinal:
                raise ValidationError("assurance diff item ordinals are not contiguous")
            if address_decision_assurance_diff_item(item) != item.content_address:
                raise ValidationError("assurance diff item address mismatch")
            counts[item.action] += 1
        if (self.added_count, self.removed_count, self.unchanged_count, self.changed_count) != tuple(counts[item.value] for item in (AssuranceDiffAction.ADDED, AssuranceDiffAction.REMOVED, AssuranceDiffAction.UNCHANGED, AssuranceDiffAction.CHANGED)):
            raise ValidationError("assurance diff action counts are not conserved")
        for count, field in ((self.added_count, "added count"), (self.removed_count, "removed count"), (self.unchanged_count, "unchanged count"), (self.changed_count, "changed count"), (self.improved_count, "improved count"), (self.regressed_count, "regressed count")):
            _count(count, f"assurance diff {field}", MAX_DIFF_ITEMS)
        if self.improved_count + self.regressed_count > self.item_count:
            raise ValidationError("assurance diff outcome counts exceed item count")
        expected_state = _diff_state(self.items, self.improved_count, self.regressed_count)
        if self.state != expected_state:
            raise ValidationError("assurance diff state is invalid")
        _address(self.content_address, "assurance diff address")
        if not _public(self.to_dict()):
            raise ValidationError("assurance diff crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {"diff_id": self.diff_id, "version": self.version, "boundary": self.boundary, "baseline_address": self.baseline_address, "candidate_address": self.candidate_address, "baseline_ledger_address": self.baseline_ledger_address, "candidate_ledger_address": self.candidate_ledger_address, "baseline_state": self.baseline_state, "candidate_state": self.candidate_state, "item_count": self.item_count, "added_count": self.added_count, "removed_count": self.removed_count, "unchanged_count": self.unchanged_count, "changed_count": self.changed_count, "improved_count": self.improved_count, "regressed_count": self.regressed_count, "state": self.state, "content_address": self.content_address}

    def to_dict(self, *, include_items: bool = True) -> dict[str, Any]:
        body = self.summary()
        if include_items:
            body["items"] = [item.to_dict() for item in self.items]
        return body


def address_decision_assurance_diff(value: DecisionAssuranceDiff) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_PREFIX)


def _assurance_diff_records(value: DecisionAssuranceGate) -> dict[str, Mapping[str, Any]]:
    records: dict[str, Mapping[str, Any]] = {}
    for finding in value.assurance.findings:
        key = f"assurance:{finding.plane}:{finding.kind}"
        if key in records:
            raise ValidationError("assurance diff finding keys are not unique")
        records[key] = {"plane": finding.plane, "kind": finding.kind, "severity": finding.severity, "required": finding.required, "passed": finding.passed, "address": finding.content_address}
    for check in value.gate.checks:
        key = f"gate:{check.plane}:{check.kind}"
        if key in records:
            raise ValidationError("assurance diff check keys are not unique")
        records[key] = {"plane": check.plane, "kind": check.kind, "severity": AssuranceSeverity.PASS.value if check.passed else AssuranceSeverity.BLOCKER.value if check.required else AssuranceSeverity.WARNING.value, "required": check.required, "passed": check.passed, "address": check.content_address}
    return records


def _outcome_score(record: Mapping[str, Any] | None) -> int | None:
    if record is None:
        return None
    if record.get("passed") is True:
        return 2
    return 0 if record.get("severity") == AssuranceSeverity.BLOCKER.value or record.get("required") is True else 1


def _diff_state(items: Sequence[DecisionAssuranceDiffItem], improved_count: int, regressed_count: int) -> str:
    if not items or all(item.action == AssuranceDiffAction.UNCHANGED.value for item in items):
        return AssuranceDiffState.UNCHANGED.value
    if improved_count and not regressed_count:
        return AssuranceDiffState.IMPROVED.value
    if regressed_count and not improved_count:
        return AssuranceDiffState.REGRESSED.value
    return AssuranceDiffState.CHANGED.value


def _diff_item(ordinal: int, key: str, baseline: Mapping[str, Any] | None, candidate: Mapping[str, Any] | None) -> tuple[DecisionAssuranceDiffItem, int, int]:
    source = candidate or baseline
    if source is None:
        raise ValidationError("assurance diff item has no source")
    if baseline is None:
        action = AssuranceDiffAction.ADDED.value
        detail = "record appears in the candidate assurance snapshot"
    elif candidate is None:
        action = AssuranceDiffAction.REMOVED.value
        detail = "record is absent from the candidate assurance snapshot"
    else:
        semantic = tuple(baseline.get(field) for field in ("plane", "kind", "severity", "required", "passed"))
        candidate_semantic = tuple(candidate.get(field) for field in ("plane", "kind", "severity", "required", "passed"))
        action = AssuranceDiffAction.UNCHANGED.value if semantic == candidate_semantic else AssuranceDiffAction.CHANGED.value
        detail = "record is unchanged" if action == AssuranceDiffAction.UNCHANGED.value else "record severity, requirement, or pass state changed"
    body = {"ordinal": ordinal, "action": action, "key": key, "plane": source["plane"], "kind": source["kind"], "baseline_severity": baseline.get("severity") if baseline else None, "candidate_severity": candidate.get("severity") if candidate else None, "baseline_required": baseline.get("required") if baseline else None, "candidate_required": candidate.get("required") if candidate else None, "baseline_passed": baseline.get("passed") if baseline else None, "candidate_passed": candidate.get("passed") if candidate else None, "baseline_address": baseline.get("address") if baseline else None, "candidate_address": candidate.get("address") if candidate else None, "detail": detail}
    provisional = DecisionAssuranceDiffItem(**body, content_address="pending:diff-item")
    value = DecisionAssuranceDiffItem(**body, content_address=address_decision_assurance_diff_item(provisional))
    baseline_score = _outcome_score(baseline)
    candidate_score = _outcome_score(candidate)
    improved = int(baseline_score is None and candidate_score is not None and candidate_score > 0 or baseline_score is not None and candidate_score is None and baseline_score == 0 or baseline_score is not None and candidate_score is not None and candidate_score > baseline_score)
    regressed = int(baseline_score is None and candidate_score == 0 or baseline_score is not None and candidate_score is None and baseline_score > 0 or baseline_score is not None and candidate_score is not None and candidate_score < baseline_score)
    return value, improved, regressed


def build_decision_assurance_diff(baseline: DecisionAssuranceGate, candidate: DecisionAssuranceGate, *, diff_id: str = "glio-noncode-observatory-registry-federation-review-decision-assurance-diff") -> DecisionAssuranceDiff:
    if not isinstance(baseline, DecisionAssuranceGate) or not isinstance(candidate, DecisionAssuranceGate):
        raise ValidationError("assurance diff requires typed assurance gates")
    verify_decision_assurance_gate(baseline)
    verify_decision_assurance_gate(candidate)
    baseline_records = _assurance_diff_records(baseline)
    candidate_records = _assurance_diff_records(candidate)
    items: list[DecisionAssuranceDiffItem] = []
    improved = 0
    regressed = 0
    for ordinal, key in enumerate(sorted(set(baseline_records) | set(candidate_records))):
        item, item_improved, item_regressed = _diff_item(ordinal, key, baseline_records.get(key), candidate_records.get(key))
        items.append(item)
        improved += item_improved
        regressed += item_regressed
    action_counts = {item.value: sum(row.action == item.value for row in items) for item in AssuranceDiffAction}
    body = {"diff_id": _text(diff_id, "assurance diff ID", 256), "version": VERSION, "boundary": BOUNDARY, "baseline_address": baseline.content_address, "candidate_address": candidate.content_address, "baseline_ledger_address": baseline.gate.ledger_address, "candidate_ledger_address": candidate.gate.ledger_address, "baseline_state": baseline.assurance.state, "candidate_state": candidate.assurance.state, "item_count": len(items), "added_count": action_counts[AssuranceDiffAction.ADDED.value], "removed_count": action_counts[AssuranceDiffAction.REMOVED.value], "unchanged_count": action_counts[AssuranceDiffAction.UNCHANGED.value], "changed_count": action_counts[AssuranceDiffAction.CHANGED.value], "improved_count": improved, "regressed_count": regressed, "items": tuple(items)}
    body["state"] = _diff_state(items, improved, regressed)
    provisional = DecisionAssuranceDiff(**body, content_address="pending:diff")
    return DecisionAssuranceDiff(**body, content_address=address_decision_assurance_diff(provisional))


def verify_decision_assurance_diff(value: DecisionAssuranceDiff) -> DecisionAssuranceDiff:
    if not isinstance(value, DecisionAssuranceDiff):
        raise ValidationError("assurance diff verification requires a typed diff")
    for item in value.items:
        if address_decision_assurance_diff_item(item) != item.content_address:
            raise ValidationError("assurance diff item address mismatch")
    if address_decision_assurance_diff(value) != value.content_address:
        raise ValidationError("assurance diff address mismatch")
    return value


def decision_assurance_diff_item_from_mapping(value: Mapping[str, Any]) -> DecisionAssuranceDiffItem:
    body = dict(_mapping(value, "assurance diff item"))
    _strict(body, {"ordinal", "action", "key", "plane", "kind", "baseline_severity", "candidate_severity", "baseline_required", "candidate_required", "baseline_passed", "candidate_passed", "baseline_address", "candidate_address", "detail", "content_address"}, "assurance diff item")
    return DecisionAssuranceDiffItem(**body)


def decision_assurance_diff_from_mapping(value: Mapping[str, Any]) -> DecisionAssuranceDiff:
    body = dict(_mapping(value, "assurance diff"))
    _strict(body, {"diff_id", "version", "boundary", "baseline_address", "candidate_address", "baseline_ledger_address", "candidate_ledger_address", "baseline_state", "candidate_state", "item_count", "added_count", "removed_count", "unchanged_count", "changed_count", "improved_count", "regressed_count", "state", "items", "content_address"}, "assurance diff")
    items = tuple(decision_assurance_diff_item_from_mapping(item) for item in _mapping_sequence(body.pop("items"), "assurance diff items"))
    return verify_decision_assurance_diff(DecisionAssuranceDiff(**body, items=items))


class AssuranceDiffQuery:
    def __init__(self, resource: str = "summary", *, action: str | None = None, plane: str | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> None:
        self.resource = _text(resource, "assurance diff query resource", 64)
        if self.resource not in {"summary", "actions", "added", "removed", "changed", "unchanged", "improved", "regressed"}:
            raise ValidationError("assurance diff query resource is invalid")
        if action is not None and _text(action, "assurance diff query action", 32) not in {item.value for item in AssuranceDiffAction}:
            raise ValidationError("assurance diff query action is invalid")
        self.action = action
        self.plane = _text(plane, "assurance diff query plane", 64) if plane is not None else None
        self.text = _text(text, "assurance diff query text", 256).casefold() if text is not None else None
        self.offset = _count(offset, "assurance diff query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "assurance diff query limit", MAX_QUERY_ITEMS, positive=True)
        if self.offset + self.limit > MAX_QUERY_ITEMS:
            raise ValidationError("assurance diff query window is too large")

    def to_dict(self) -> dict[str, Any]:
        return {"resource": self.resource, "action": self.action, "plane": self.plane, "text": self.text, "offset": self.offset, "limit": self.limit}


class AssuranceDiffQueryResult:
    def __init__(self, query: AssuranceDiffQuery, total_count: int, items: Sequence[Mapping[str, Any]], source_address: str) -> None:
        self.query = query
        self.total_count = _count(total_count, "assurance diff query total count", MAX_QUERY_ITEMS)
        self.items = tuple(dict(item) for item in items)
        self.returned_count = _count(len(self.items), "assurance diff query returned count", MAX_QUERY_ITEMS)
        if self.returned_count > self.total_count:
            raise ValidationError("assurance diff query returned count exceeds total")
        self.source_address = _address(source_address, "assurance diff query source address")
        self.content_address = "pending:diff-query"
        self.content_address = content_hash(self.to_dict() | {"content_address": None}, prefix=DIFF_QUERY_PREFIX + "-result")
        if not _public(self.to_dict()):
            raise ValidationError("assurance diff query crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"query": self.query.to_dict(), "total_count": self.total_count, "returned_count": self.returned_count, "items": list(self.items), "source_address": self.source_address, "content_address": self.content_address}


def _diff_outcome(item: DecisionAssuranceDiffItem) -> str | None:
    baseline_score = _outcome_score({"passed": item.baseline_passed, "severity": item.baseline_severity, "required": item.baseline_required}) if item.baseline_address is not None else None
    candidate_score = _outcome_score({"passed": item.candidate_passed, "severity": item.candidate_severity, "required": item.candidate_required}) if item.candidate_address is not None else None
    if baseline_score is None and candidate_score is None:
        return None
    if baseline_score is None:
        return "improved" if candidate_score and candidate_score > 0 else "regressed"
    if candidate_score is None:
        return "improved" if baseline_score == 0 else "regressed"
    if candidate_score > baseline_score:
        return "improved"
    if candidate_score < baseline_score:
        return "regressed"
    return None


def query_decision_assurance_diff(value: DecisionAssuranceDiff, query: AssuranceDiffQuery | None = None, **kwargs: Any) -> AssuranceDiffQueryResult:
    verify_decision_assurance_diff(value)
    selected = query if query is not None else AssuranceDiffQuery(**kwargs)
    if query is not None and kwargs:
        raise ValidationError("query object and keyword filters cannot be combined")
    if selected.resource == "summary":
        records: tuple[Mapping[str, Any], ...] = (value.summary(),)
    else:
        records = tuple(item.to_dict() for item in value.items)
        if selected.resource != "actions":
            if selected.resource in {item.value for item in AssuranceDiffAction}:
                records = tuple(item for item in records if item["action"] == selected.resource)
            else:
                records = tuple(item for item in records if _diff_outcome(decision_assurance_diff_item_from_mapping(item)) == selected.resource)
    matched = tuple(item for item in records if (selected.action is None or item.get("action") == selected.action) and (selected.plane is None or item.get("plane") == selected.plane) and (selected.text is None or selected.text in canonical_json(item).casefold()))
    return AssuranceDiffQueryResult(selected, len(matched), matched[selected.offset : selected.offset + selected.limit], value.content_address)


def decision_assurance_diff_json(value: DecisionAssuranceDiff) -> str:
    verify_decision_assurance_diff(value)
    return canonical_json(value.to_dict())


def decision_assurance_diff_csv(value: DecisionAssuranceDiff) -> str:
    verify_decision_assurance_diff(value)
    rows = [item.to_dict() for item in value.items]
    return _csv_text(rows, ("ordinal", "action", "key", "plane", "kind", "baseline_severity", "candidate_severity", "baseline_required", "candidate_required", "baseline_passed", "candidate_passed", "baseline_address", "candidate_address", "detail", "content_address")) if rows else ""


def decision_assurance_diff_query_json(value: AssuranceDiffQueryResult) -> str:
    return canonical_json(value.to_dict())


def decision_assurance_diff_query_csv(value: AssuranceDiffQueryResult) -> str:
    if not value.items:
        return ""
    fields = tuple(sorted({key for item in value.items for key in item}))
    return _csv_text(value.items, fields)


def render_decision_assurance_diff_markdown(value: DecisionAssuranceDiff) -> str:
    verify_decision_assurance_diff(value)
    return _markdown("Federation Review Decision Assurance Diff", value.summary(), [item.to_dict() for item in value.items])


def render_decision_assurance_diff_query_markdown(value: AssuranceDiffQueryResult) -> str:
    return _markdown("Federation Review Decision Assurance Diff Query", {"resource": value.query.resource, "total_count": value.total_count, "returned_count": value.returned_count}, value.items)


def decision_assurance_diff_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Federation Review Decision Assurance Diff", "type": "object", "additionalProperties": False, "properties": {"diff_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "baseline_address": {"type": "string"}, "candidate_address": {"type": "string"}, "item_count": {"type": "integer", "minimum": 0, "maximum": MAX_DIFF_ITEMS}, "state": {"enum": [item.value for item in AssuranceDiffState]}, "items": {"type": "array"}, "content_address": {"type": "string"}}, "required": ["diff_id", "version", "boundary", "baseline_address", "candidate_address", "item_count", "state", "content_address"]}


def decision_assurance_diff_query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Federation Review Decision Assurance Diff Query", "type": "object", "additionalProperties": False, "properties": {"resource": {"enum": ["summary", "actions", "added", "removed", "changed", "unchanged", "improved", "regressed"]}, "action": {"type": ["string", "null"]}, "plane": {"type": ["string", "null"]}, "text": {"type": ["string", "null"]}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}}, "required": ["resource", "offset", "limit"]}


def _diff_manifest_body(value: DecisionAssuranceDiff, diff_raw: bytes) -> dict[str, Any]:
    byte_address = hash_bytes(diff_raw)
    return {"version": VERSION, "boundary": BOUNDARY, "diff_id": value.diff_id, "baseline_address": value.baseline_address, "candidate_address": value.candidate_address, "artifact_count": 1, "files": list(DIFF_FILES), "artifact": {"name": DIFF_NAME, "bytes": len(diff_raw), "byte_address": byte_address, "file_address": content_hash({"name": DIFF_NAME, "byte_address": byte_address}, prefix=DIFF_PREFIX + "-file")}, "manifest_address": None}


def _diff_manifest_address(value: Mapping[str, Any]) -> str:
    return content_hash(dict(value), prefix=DIFF_MANIFEST_PREFIX)


def write_decision_assurance_diff(value: DecisionAssuranceDiff, directory: str | Path, *, overwrite: bool = False) -> Path:
    verify_decision_assurance_diff(value)
    destination = Path(directory)
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())) and not overwrite:
        raise ValidationError("decision assurance diff destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    diff_raw = canonical_bytes(value.to_dict())
    manifest = _diff_manifest_body(value, diff_raw)
    manifest["manifest_address"] = _diff_manifest_address(manifest)
    manifest_raw = canonical_bytes(manifest)
    temporary = Path(tempfile.mkdtemp(prefix=f".{DIFF_PREFIX}-", dir=str(destination.parent)))
    try:
        (temporary / DIFF_NAME).write_bytes(diff_raw)
        (temporary / MANIFEST_NAME).write_bytes(manifest_raw)
        if destination.exists():
            if not overwrite:
                raise ValidationError("decision assurance diff destination already exists")
            if not destination.is_dir():
                raise ValidationError("decision assurance diff destination is not a directory")
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def _check_diff_artifact(manifest: Mapping[str, Any], path: Path) -> None:
    artifact = _mapping(manifest.get("artifact"), "decision assurance diff artifact")
    if artifact.get("name") != DIFF_NAME:
        raise ValidationError("decision assurance diff artifact name is invalid")
    raw = path.read_bytes()
    byte_address = hash_bytes(raw)
    if artifact.get("bytes") != len(raw) or artifact.get("byte_address") != byte_address:
        raise ValidationError("decision assurance diff bytes are not addressed")
    expected = content_hash({"name": DIFF_NAME, "byte_address": byte_address}, prefix=DIFF_PREFIX + "-file")
    if artifact.get("file_address") != expected:
        raise ValidationError("decision assurance diff file address is invalid")


def load_decision_assurance_diff(directory: str | Path) -> DecisionAssuranceDiff:
    source = Path(directory)
    if source.is_symlink() or not source.is_dir():
        raise ValidationError("decision assurance diff input must be a directory")
    children = tuple(source.iterdir())
    if any(item.is_symlink() for item in children) or {item.name for item in children} != set(DIFF_FILES):
        raise ValidationError("decision assurance diff file set is invalid")
    manifest = _read_json(source / MANIFEST_NAME, "decision assurance diff manifest")
    _strict(manifest, {"version", "boundary", "diff_id", "baseline_address", "candidate_address", "artifact_count", "files", "artifact", "manifest_address"}, "decision assurance diff manifest")
    if manifest["version"] != VERSION or manifest["boundary"] != BOUNDARY or manifest["artifact_count"] != 1 or tuple(manifest["files"]) != DIFF_FILES:
        raise ValidationError("decision assurance diff manifest contract is invalid")
    if manifest["manifest_address"] != _diff_manifest_address({**manifest, "manifest_address": None}):
        raise ValidationError("decision assurance diff manifest address mismatch")
    _check_diff_artifact(manifest, source / DIFF_NAME)
    value = decision_assurance_diff_from_mapping(_read_json(source / DIFF_NAME, "decision assurance diff"))
    if manifest["diff_id"] != value.diff_id or manifest["baseline_address"] != value.baseline_address or manifest["candidate_address"] != value.candidate_address:
        raise ValidationError("decision assurance diff manifest linkage is invalid")
    return verify_decision_assurance_diff(value)


def decision_assurance_finding_from_mapping(value: Mapping[str, Any]) -> DecisionAssuranceFinding:
    body = dict(_mapping(value, "assurance finding"))
    _strict(body, {"ordinal", "finding_id", "plane", "kind", "severity", "required", "passed", "detail", "remediation", "evidence_address", "content_address"}, "assurance finding")
    return DecisionAssuranceFinding(**body)


def decision_assurance_from_mapping(value: Mapping[str, Any]) -> DecisionAssurance:
    body = dict(_mapping(value, "decision assurance"))
    _strict(body, {"assurance_id", "version", "boundary", "ledger_id", "ledger_address", "queue_address", "finding_count", "passed_count", "warning_count", "blocker_count", "state", "accepted", "release_ready", "findings", "content_address"}, "decision assurance")
    findings = tuple(decision_assurance_finding_from_mapping(item) for item in _mapping_sequence(body.pop("findings"), "assurance findings"))
    return verify_decision_assurance(DecisionAssurance(**body, findings=findings))


def decision_gate_check_from_mapping(value: Mapping[str, Any]) -> DecisionGateCheck:
    body = dict(_mapping(value, "gate check"))
    _strict(body, {"ordinal", "check_id", "plane", "kind", "required", "passed", "detail", "evidence_address", "content_address"}, "gate check")
    return DecisionGateCheck(**body)


def decision_gate_from_mapping(value: Mapping[str, Any]) -> DecisionReleaseGate:
    body = dict(_mapping(value, "decision gate"))
    _strict(body, {"gate_id", "version", "boundary", "ledger_id", "ledger_address", "assurance_address", "source_queue_release_ready", "check_count", "passed_count", "warning_count", "blocker_count", "state", "accepted", "release_ready", "checks", "content_address"}, "decision gate")
    checks = tuple(decision_gate_check_from_mapping(item) for item in _mapping_sequence(body.pop("checks"), "gate checks"))
    return verify_decision_gate(DecisionReleaseGate(**body, checks=checks))


def decision_assurance_gate_from_mapping(value: Mapping[str, Any]) -> DecisionAssuranceGate:
    body = dict(_mapping(value, "decision assurance gate"))
    _strict(body, {"assurance", "gate", "content_address"}, "decision assurance gate")
    assurance = decision_assurance_from_mapping(_mapping(body.pop("assurance"), "assurance"))
    gate = decision_gate_from_mapping(_mapping(body.pop("gate"), "gate"))
    return verify_decision_assurance_gate(DecisionAssuranceGate(assurance, gate, **body))


class AssuranceQuery:
    def __init__(self, resource: str = "summary", *, severity: str | None = None, passed: bool | None = None, required: bool | None = None, plane: str | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> None:
        self.resource = _text(resource, "assurance query resource", 64)
        if self.resource not in {"summary", "findings", "blockers", "warnings", "checks", "failed"}:
            raise ValidationError("assurance query resource is invalid")
        if severity is not None:
            _severity(severity)
        if passed is not None:
            _bool(passed, "assurance query passed")
        if required is not None:
            _bool(required, "assurance query required")
        self.severity = severity
        self.passed = passed
        self.required = required
        self.plane = _text(plane, "assurance query plane", 128) if plane is not None else None
        self.text = _text(text, "assurance query text", 256).casefold() if text is not None else None
        self.offset = _count(offset, "assurance query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "assurance query limit", MAX_QUERY_ITEMS, positive=True)
        if self.offset + self.limit > MAX_QUERY_ITEMS:
            raise ValidationError("assurance query window is too large")

    def to_dict(self) -> dict[str, Any]:
        return {"resource": self.resource, "severity": self.severity, "passed": self.passed, "required": self.required, "plane": self.plane, "text": self.text, "offset": self.offset, "limit": self.limit}


class AssuranceQueryResult:
    def __init__(self, query: AssuranceQuery, total_count: int, items: Sequence[Mapping[str, Any]], source_address: str) -> None:
        self.query = query
        self.total_count = total_count
        self.items = tuple(dict(item) for item in items)
        self.returned_count = len(self.items)
        self.source_address = _address(source_address, "assurance query source address")
        self.content_address = "pending:query"
        self.content_address = content_hash(self.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX + "-result")
        self._validate()

    def _validate(self) -> None:
        _count(self.total_count, "assurance query total count", MAX_QUERY_ITEMS)
        _count(self.returned_count, "assurance query returned count", MAX_QUERY_ITEMS)
        if self.returned_count > self.total_count:
            raise ValidationError("assurance query returned count exceeds total")
        if not _public(self.to_dict()):
            raise ValidationError("assurance query crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"query": self.query.to_dict(), "total_count": self.total_count, "returned_count": self.returned_count, "items": list(self.items), "source_address": self.source_address, "content_address": self.content_address}


def _query_matches(value: Mapping[str, Any], query: AssuranceQuery) -> bool:
    if query.severity is not None and value.get("severity") != query.severity:
        return False
    if query.passed is not None and value.get("passed") != query.passed:
        return False
    if query.required is not None and value.get("required") != query.required:
        return False
    if query.plane is not None and value.get("plane") != query.plane:
        return False
    return query.text is None or query.text in canonical_json(value).casefold()


def query_decision_assurance(value: DecisionAssuranceGate, query: AssuranceQuery | None = None, **kwargs: Any) -> AssuranceQueryResult:
    verify_decision_assurance_gate(value)
    selected = query if query is not None else AssuranceQuery(**kwargs)
    if query is not None and kwargs:
        raise ValidationError("query object and keyword filters cannot be combined")
    if selected.resource == "summary":
        records = (value.assurance.summary() | {"gate_state": value.gate.state, "gate_release_ready": value.gate.release_ready},)
    elif selected.resource in {"findings", "blockers", "warnings", "failed"}:
        records = tuple(item.to_dict() for item in value.assurance.findings)
        if selected.resource == "blockers":
            records = tuple(item for item in records if item["severity"] == AssuranceSeverity.BLOCKER.value)
        elif selected.resource == "warnings":
            records = tuple(item for item in records if item["severity"] == AssuranceSeverity.WARNING.value)
        elif selected.resource == "failed":
            records = tuple(item for item in records if not item["passed"])
    else:
        records = tuple(item.to_dict() for item in value.gate.checks)
        if selected.resource == "checks":
            records = tuple(records)
    matched = tuple(item for item in records if _query_matches(item, selected))
    return AssuranceQueryResult(selected, len(matched), matched[selected.offset : selected.offset + selected.limit], value.content_address)


def assurance_json(value: DecisionAssurance) -> str:
    verify_decision_assurance(value)
    return canonical_json(value.to_dict())


def gate_json(value: DecisionReleaseGate) -> str:
    verify_decision_gate(value)
    return canonical_json(value.to_dict())


def assurance_gate_json(value: DecisionAssuranceGate) -> str:
    verify_decision_assurance_gate(value)
    return canonical_json(value.to_dict())


def query_json(value: AssuranceQueryResult) -> str:
    return canonical_json(value.to_dict())


def _csv_text(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows({field: row.get(field) for field in fields} for row in rows)
    return output.getvalue()


def assurance_csv(value: DecisionAssurance) -> str:
    verify_decision_assurance(value)
    rows = [finding.to_dict() for finding in value.findings]
    return _csv_text(rows, ("ordinal", "finding_id", "plane", "kind", "severity", "required", "passed", "detail", "remediation", "evidence_address", "content_address")) if rows else ""


def gate_csv(value: DecisionReleaseGate) -> str:
    verify_decision_gate(value)
    rows = [check.to_dict() for check in value.checks]
    return _csv_text(rows, ("ordinal", "check_id", "plane", "kind", "required", "passed", "detail", "evidence_address", "content_address")) if rows else ""


def query_csv(value: AssuranceQueryResult) -> str:
    if not value.items:
        return ""
    return _csv_text(value.items, tuple(sorted({key for item in value.items for key in item})))


def _markdown(title: str, summary: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> str:
    lines = [f"# {title}", "", "## Summary", ""]
    lines.extend(f"- {key}: `{summary[key]}`" for key in sorted(summary))
    lines.extend(["", "## Records", ""])
    if not rows:
        lines.append("No records.")
        return "\n".join(lines) + "\n"
    fields = tuple(sorted({key for row in rows for key in row}))
    lines.append("| " + " | ".join(fields) + " |")
    lines.append("| " + " | ".join("---" for _ in fields) + " |")
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(field, "")).replace("|", "\\|").replace("\n", " ") for field in fields) + " |")
    return "\n".join(lines) + "\n"


def render_assurance_markdown(value: DecisionAssurance) -> str:
    verify_decision_assurance(value)
    return _markdown("Federation Review Decision Assurance", value.summary(), [finding.to_dict() for finding in value.findings])


def render_gate_markdown(value: DecisionReleaseGate) -> str:
    verify_decision_gate(value)
    return _markdown("Federation Review Decision Release Gate", value.summary(), [check.to_dict() for check in value.checks])


def render_assurance_gate_markdown(value: DecisionAssuranceGate) -> str:
    verify_decision_assurance_gate(value)
    return _markdown("Federation Review Decision Assurance Gate", {"assurance_state": value.assurance.state, "gate_state": value.gate.state, "release_ready": value.gate.release_ready, "ledger_address": value.gate.ledger_address}, [*({"plane": "assurance", **finding.to_dict()} for finding in value.assurance.findings), *({"plane": "gate", **check.to_dict()} for check in value.gate.checks)])


def render_query_markdown(value: AssuranceQueryResult) -> str:
    return _markdown("Federation Review Decision Assurance Query", {"resource": value.query.resource, "total_count": value.total_count, "returned_count": value.returned_count}, value.items)


def assurance_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Federation Review Decision Assurance", "type": "object", "additionalProperties": False, "properties": {"assurance_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "ledger_address": {"type": "string"}, "finding_count": {"type": "integer", "minimum": 1}, "state": {"enum": [item.value for item in AssuranceState]}, "release_ready": {"type": "boolean"}, "findings": {"type": "array"}, "content_address": {"type": "string"}}, "required": ["assurance_id", "version", "boundary", "ledger_address", "finding_count", "state", "release_ready", "content_address"]}


def gate_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Federation Review Decision Release Gate", "type": "object", "additionalProperties": False, "properties": {"gate_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "ledger_address": {"type": "string"}, "assurance_address": {"type": "string"}, "check_count": {"type": "integer", "minimum": 1}, "state": {"enum": [item.value for item in GateState]}, "release_ready": {"type": "boolean"}, "checks": {"type": "array"}, "content_address": {"type": "string"}}, "required": ["gate_id", "version", "boundary", "ledger_address", "assurance_address", "check_count", "state", "release_ready", "content_address"]}


def assurance_gate_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Federation Review Decision Assurance Gate", "type": "object", "additionalProperties": False, "properties": {"assurance": {"type": "object"}, "gate": {"type": "object"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "content_address": {"type": "string"}}, "required": ["assurance", "gate", "content_address"]}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Federation Review Decision Assurance Query", "type": "object", "additionalProperties": False, "properties": {"resource": {"enum": ["summary", "findings", "blockers", "warnings", "checks", "failed"]}, "severity": {"type": ["string", "null"]}, "passed": {"type": ["boolean", "null"]}, "required": {"type": ["boolean", "null"]}, "plane": {"type": ["string", "null"]}, "text": {"type": ["string", "null"]}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}}, "required": ["resource", "offset", "limit"]}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "assurance": {"findings": 12, "severities": [item.value for item in AssuranceSeverity], "states": [item.value for item in AssuranceState]}, "gate": {"checks": 8, "states": [item.value for item in GateState], "source_queue_authoritative": True}, "diff": {"maximum_items": MAX_DIFF_ITEMS, "actions": [item.value for item in AssuranceDiffAction], "states": [item.value for item in AssuranceDiffState], "persistence_files": list(DIFF_FILES)}, "persistence": {"files": list(FILES), "atomic_write": True, "canonical_json": True}, "queries": {"resources": ["summary", "findings", "blockers", "warnings", "checks", "failed"], "pagination": True, "filters": ["severity", "passed", "required", "plane", "text"]}, "diff_queries": {"resources": ["summary", "actions", "added", "removed", "changed", "unchanged", "improved", "regressed"], "pagination": True, "filters": ["action", "plane", "text"]}}


def _manifest_body(value: DecisionAssuranceGate, assurance_raw: bytes, gate_raw: bytes) -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "ledger_id": value.gate.ledger_id, "ledger_address": value.gate.ledger_address, "assurance_address": value.assurance.content_address, "gate_address": value.gate.content_address, "artifact_count": 2, "files": list(FILES), "artifacts": [{"name": ASSURANCE_NAME, "bytes": len(assurance_raw), "byte_address": hash_bytes(assurance_raw), "file_address": content_hash({"name": ASSURANCE_NAME, "byte_address": hash_bytes(assurance_raw)}, prefix=ASSURANCE_PREFIX + "-file")}, {"name": GATE_NAME, "bytes": len(gate_raw), "byte_address": hash_bytes(gate_raw), "file_address": content_hash({"name": GATE_NAME, "byte_address": hash_bytes(gate_raw)}, prefix=ASSURANCE_PREFIX + "-file")}], "manifest_address": None}


def _manifest_address(value: Mapping[str, Any]) -> str:
    return content_hash(dict(value), prefix=MANIFEST_PREFIX)


def write_decision_assurance_gate(value: DecisionAssuranceGate, directory: str | Path, *, overwrite: bool = False) -> Path:
    verify_decision_assurance_gate(value)
    destination = Path(directory)
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())) and not overwrite:
        raise ValidationError("decision assurance gate destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    assurance_raw = canonical_bytes(value.assurance.to_dict())
    gate_raw = canonical_bytes(value.gate.to_dict())
    manifest = _manifest_body(value, assurance_raw, gate_raw)
    manifest["manifest_address"] = _manifest_address(manifest)
    manifest_raw = canonical_bytes(manifest)
    temporary = Path(tempfile.mkdtemp(prefix=f".{ASSURANCE_PREFIX}-", dir=str(destination.parent)))
    try:
        (temporary / ASSURANCE_NAME).write_bytes(assurance_raw)
        (temporary / GATE_NAME).write_bytes(gate_raw)
        (temporary / MANIFEST_NAME).write_bytes(manifest_raw)
        if destination.exists():
            if not destination.is_dir() or any(destination.iterdir()):
                if not overwrite:
                    raise ValidationError("decision assurance gate destination already exists")
                shutil.rmtree(destination)
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def _read_json(path: Path, field: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValidationError(f"{field} must be a regular file")
    raw = path.read_bytes()
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"{field} is invalid JSON") from exc
    if canonical_bytes(value) != raw:
        raise ValidationError(f"{field} is not canonical JSON")
    return dict(_mapping(value, field))


def _check_artifact(manifest: Mapping[str, Any], path: Path, name: str) -> None:
    artifact = next((item for item in manifest["artifacts"] if item.get("name") == name), None)
    if artifact is None:
        raise ValidationError(f"decision assurance manifest is missing {name}")
    raw = path.read_bytes()
    if artifact.get("bytes") != len(raw) or artifact.get("byte_address") != hash_bytes(raw):
        raise ValidationError(f"decision assurance {name} bytes are not addressed")
    expected = content_hash({"name": name, "byte_address": hash_bytes(raw)}, prefix=ASSURANCE_PREFIX + "-file")
    if artifact.get("file_address") != expected:
        raise ValidationError(f"decision assurance {name} file address is invalid")


def load_decision_assurance_gate(directory: str | Path) -> DecisionAssuranceGate:
    source = Path(directory)
    if source.is_symlink() or not source.is_dir():
        raise ValidationError("decision assurance gate input must be a directory")
    children = tuple(source.iterdir())
    if any(item.is_symlink() for item in children) or {item.name for item in children} != set(FILES):
        raise ValidationError("decision assurance gate file set is invalid")
    manifest = _read_json(source / MANIFEST_NAME, "decision assurance manifest")
    _strict(manifest, {"version", "boundary", "ledger_id", "ledger_address", "assurance_address", "gate_address", "artifact_count", "files", "artifacts", "manifest_address"}, "decision assurance manifest")
    if manifest["version"] != VERSION or manifest["boundary"] != BOUNDARY or manifest["artifact_count"] != 2 or tuple(manifest["files"]) != FILES or len(manifest["artifacts"]) != 2:
        raise ValidationError("decision assurance manifest contract is invalid")
    if manifest["manifest_address"] != _manifest_address({**manifest, "manifest_address": None}):
        raise ValidationError("decision assurance manifest address mismatch")
    _check_artifact(manifest, source / ASSURANCE_NAME, ASSURANCE_NAME)
    _check_artifact(manifest, source / GATE_NAME, GATE_NAME)
    assurance = decision_assurance_from_mapping(_read_json(source / ASSURANCE_NAME, "decision assurance"))
    gate = decision_gate_from_mapping(_read_json(source / GATE_NAME, "decision gate"))
    value = DecisionAssuranceGate(assurance, gate, address_decision_assurance_gate(DecisionAssuranceGate(assurance, gate, "pending:bundle")))
    if manifest["ledger_id"] != gate.ledger_id or manifest["ledger_address"] != gate.ledger_address or manifest["assurance_address"] != assurance.content_address or manifest["gate_address"] != gate.content_address:
        raise ValidationError("decision assurance manifest linkage is invalid")
    return verify_decision_assurance_gate(value)


__all__ = [
    "ASSURANCE_NAME",
    "AssuranceDiffAction",
    "AssuranceDiffQuery",
    "AssuranceDiffQueryResult",
    "AssuranceDiffState",
    "AssurancePlane",
    "AssuranceQuery",
    "AssuranceQueryResult",
    "AssuranceSeverity",
    "AssuranceState",
    "BOUNDARY",
    "DIFF_FILES",
    "DIFF_NAME",
    "DecisionAssurance",
    "DecisionAssuranceDiff",
    "DecisionAssuranceDiffItem",
    "DecisionAssuranceFinding",
    "DecisionAssuranceGate",
    "DecisionGateCheck",
    "DecisionReleaseGate",
    "FILES",
    "GATE_NAME",
    "GateState",
    "address_assurance_finding",
    "address_decision_assurance",
    "address_decision_assurance_diff",
    "address_decision_assurance_diff_item",
    "address_decision_assurance_gate",
    "address_decision_gate",
    "address_gate_check",
    "assurance_csv",
    "assurance_gate_json",
    "assurance_gate_schema",
    "assurance_json",
    "assurance_schema",
    "build_decision_assurance",
    "build_decision_assurance_diff",
    "build_decision_assurance_gate",
    "build_decision_gate",
    "capabilities",
    "decision_assurance_diff_csv",
    "decision_assurance_diff_from_mapping",
    "decision_assurance_diff_item_from_mapping",
    "decision_assurance_diff_json",
    "decision_assurance_diff_query_csv",
    "decision_assurance_diff_query_json",
    "decision_assurance_diff_query_schema",
    "decision_assurance_diff_schema",
    "decision_assurance_finding_from_mapping",
    "decision_assurance_from_mapping",
    "decision_assurance_gate_from_mapping",
    "decision_gate_check_from_mapping",
    "decision_gate_from_mapping",
    "gate_csv",
    "gate_json",
    "gate_schema",
    "load_decision_assurance_diff",
    "load_decision_assurance_gate",
    "query_csv",
    "query_decision_assurance",
    "query_decision_assurance_diff",
    "query_json",
    "query_schema",
    "render_assurance_gate_markdown",
    "render_assurance_markdown",
    "render_decision_assurance_diff_markdown",
    "render_decision_assurance_diff_query_markdown",
    "render_gate_markdown",
    "render_query_markdown",
    "verify_decision_assurance",
    "verify_decision_assurance_diff",
    "verify_decision_assurance_gate",
    "verify_decision_gate",
    "write_decision_assurance_gate",
    "write_decision_assurance_diff",
]
