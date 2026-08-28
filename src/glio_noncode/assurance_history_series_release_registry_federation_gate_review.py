"""Operational review routing for release-registry federation gates.

This boundary turns an independently verified federation gate into a durable,
path-free review queue.  Every assurance finding and release check becomes an
addressed review item with explicit severity, priority, and initial state.
The second half of the boundary is an append-only decision ledger.  Ledger
actions are evidence-aware and replayed from the queue snapshot; they cannot
silently override the source gate's release decision.  The module is a review
and transport layer, not a scientific ranking system.
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

from . import assurance_history_series_release_registry_federation_gate as gate_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes

VERSION = gate_model.VERSION + "-review-v1"
BOUNDARY = gate_model.BOUNDARY + "_review"
PREFIX = gate_model.PREFIX + "-review"
QUEUE_PREFIX = PREFIX + "-queue"
ITEM_PREFIX = QUEUE_PREFIX + "-item"
VERIFICATION_PREFIX = QUEUE_PREFIX + "-verification"
VERIFICATION_FINDING_PREFIX = VERIFICATION_PREFIX + "-finding"
QUERY_PREFIX = PREFIX + "-query"
MANIFEST_PREFIX = PREFIX + "-manifest"
LEDGER_PREFIX = PREFIX + "-decision-ledger"
DECISION_PREFIX = LEDGER_PREFIX + "-decision"
REPLAY_PREFIX = LEDGER_PREFIX + "-replay"
DIFF_PREFIX = PREFIX + "-diff"
DIFF_ITEM_PREFIX = DIFF_PREFIX + "-item"

MANIFEST_NAME = "manifest.json"
QUEUE_NAME = "queue.json"
ITEMS_NAME = "items.json"
VERIFICATION_NAME = "verification.json"
QUEUE_FILES = (MANIFEST_NAME, QUEUE_NAME, ITEMS_NAME, VERIFICATION_NAME)

LEDGER_NAME = "ledger.json"
ENTRIES_NAME = "entries.json"
REPLAY_NAME = "replay.json"
LEDGER_FILES = (MANIFEST_NAME, LEDGER_NAME, ENTRIES_NAME, REPLAY_NAME)

DIFF_NAME = "diff.json"
DIFF_FILES = (MANIFEST_NAME, DIFF_NAME)

DEFAULT_QUEUE_ID = "glio-noncode-decision-assurance-history-series-release-registry-federation-review-queue"
DEFAULT_LEDGER_ID = "glio-noncode-decision-assurance-history-series-release-registry-federation-review-decision-ledger"
DEFAULT_DIFF_ID = "glio-noncode-decision-assurance-history-series-release-registry-federation-review-decision-diff"
NO_EVIDENCE = "none:review-evidence"
INITIAL_HEAD = "none:review-head"
MAX_ITEMS = 128
MAX_FINDINGS = 32
MAX_DECISIONS = 4096
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


class ReviewQueueState(StrEnum):
    CLEAR = "clear"
    REVIEW = "review"
    BLOCKED = "blocked"


class ReviewItemState(StrEnum):
    CLEAR = "clear"
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    WAIVED = "waived"
    ESCALATED = "escalated"
    BLOCKED = "blocked"


class ReviewPriority(StrEnum):
    NONE = "none"
    HIGH = "high"
    CRITICAL = "critical"


class ReviewRecordType(StrEnum):
    FINDING = "finding"
    CHECK = "check"


class ReviewAction(StrEnum):
    ACKNOWLEDGE = "acknowledge"
    REMEDIATE = "remediate"
    WAIVE = "waive"
    ESCALATE = "escalate"
    REOPEN = "reopen"


class DiffAction(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    UNCHANGED = "unchanged"
    CHANGED = "changed"


class DiffDirection(StrEnum):
    NONE = "none"
    IMPROVED = "improved"
    REGRESSED = "regressed"


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value.strip()


def _address(value: Any, field: str) -> str:
    value = _text(value, field, 2048)
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


def _enum(value: Any, field: str, enum_type: type[StrEnum]) -> str:
    value = _text(value, field, 64)
    if value not in {item.value for item in enum_type}:
        raise ValidationError(f"{field} is invalid")
    return value


def _queue_state(value: Any, field: str = "review queue state") -> str:
    return _enum(value, field, ReviewQueueState)


def _item_state(value: Any, field: str = "review item state") -> str:
    return _enum(value, field, ReviewItemState)


def _priority(value: Any, field: str = "review priority") -> str:
    return _enum(value, field, ReviewPriority)


def _record_type(value: Any, field: str = "review record type") -> str:
    return _enum(value, field, ReviewRecordType)


def _action(value: Any, field: str = "review action") -> str:
    return _enum(value, field, ReviewAction)


def _diff_action(value: Any, field: str = "diff action") -> str:
    return _enum(value, field, DiffAction)


def _diff_direction(value: Any, field: str = "diff direction") -> str:
    return _enum(value, field, DiffDirection)


def _gate_plane(value: Any, field: str = "review plane") -> str:
    value = _text(value, field, 64)
    if value not in {item.value for item in gate_model.GatePlane}:
        raise ValidationError(f"{field} is invalid")
    return value


def _severity(value: Any, field: str = "review severity") -> str:
    value = _text(value, field, 64)
    if value not in {item.value for item in gate_model.FindingSeverity}:
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
        return call(), True
    except Exception:
        return None, False


class FederationReviewItem:
    """One finding or release check routed into the operational queue."""

    def __init__(
        self,
        ordinal: int,
        item_id: str,
        record_type: str,
        source_id: str,
        plane: str,
        severity: str,
        required: bool,
        passed: bool,
        state: str,
        priority: str,
        detail: str,
        evidence_address: str,
        source_address: str,
        content_address: str,
    ) -> None:
        self.ordinal, self.item_id, self.record_type = ordinal, item_id, record_type
        self.source_id, self.plane, self.severity = source_id, plane, severity
        self.required, self.passed = required, passed
        self.state, self.priority = state, priority
        self.detail, self.evidence_address = detail, evidence_address
        self.source_address, self.content_address = source_address, content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "review item ordinal", MAX_ITEMS - 1)
        _text(self.item_id, "review item ID", 256)
        _record_type(self.record_type)
        _text(self.source_id, "review source ID", 256)
        _gate_plane(self.plane)
        _severity(self.severity)
        _bool(self.required, "review item required")
        _bool(self.passed, "review item passed")
        _item_state(self.state)
        _priority(self.priority)
        _text(self.detail, "review item detail", 4096)
        _address(self.evidence_address, "review evidence address")
        _address(self.source_address, "review source address")
        _address(self.content_address, "review item address")
        if self.required != (self.severity == gate_model.FindingSeverity.BLOCKER.value):
            raise ValidationError("review required state does not match severity")
        expected_state = ReviewItemState.CLEAR.value if self.passed else ReviewItemState.BLOCKED.value if self.required else ReviewItemState.OPEN.value
        expected_priority = ReviewPriority.NONE.value if self.passed else ReviewPriority.CRITICAL.value if self.required else ReviewPriority.HIGH.value
        if self.state != expected_state or self.priority != expected_priority:
            raise ValidationError("review item initial state does not match source result")
        if not _public(self.to_dict()):
            raise ValidationError("review item crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_review_item(self) != self.content_address:
            raise ValidationError("review item address mismatch")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "item_id": self.item_id,
            "record_type": self.record_type,
            "source_id": self.source_id,
            "plane": self.plane,
            "severity": self.severity,
            "required": self.required,
            "passed": self.passed,
            "state": self.state,
            "priority": self.priority,
            "detail": self.detail,
            "evidence_address": self.evidence_address,
            "source_address": self.source_address,
            "content_address": self.content_address,
        }


def address_review_item(value: FederationReviewItem) -> str:
    return content_hash(value.to_dict() | {"ordinal": None, "content_address": None}, prefix=ITEM_PREFIX)


def _make_item(
    ordinal: int,
    item_id: str,
    record_type: str,
    source_id: str,
    plane: str,
    severity: str,
    passed: bool,
    detail: str,
    evidence_address: str,
    source_address: str,
) -> FederationReviewItem:
    body = {
        "ordinal": ordinal,
        "item_id": item_id,
        "record_type": record_type,
        "source_id": source_id,
        "plane": plane,
        "severity": severity,
        "required": severity == gate_model.FindingSeverity.BLOCKER.value,
        "passed": passed,
        "state": ReviewItemState.CLEAR.value if passed else ReviewItemState.BLOCKED.value if severity == gate_model.FindingSeverity.BLOCKER.value else ReviewItemState.OPEN.value,
        "priority": ReviewPriority.NONE.value if passed else ReviewPriority.CRITICAL.value if severity == gate_model.FindingSeverity.BLOCKER.value else ReviewPriority.HIGH.value,
        "detail": detail,
        "evidence_address": evidence_address,
        "source_address": source_address,
        "content_address": "pending:review-item",
    }
    provisional = FederationReviewItem(**body)
    body["content_address"] = address_review_item(provisional)
    return FederationReviewItem(**body)


class FederationReviewQueue:
    """Stable operational queue projected from one verified source gate."""

    def __init__(
        self,
        queue_id: str,
        version: str,
        boundary: str,
        federation_address: str,
        runtime_address: str,
        assurance_address: str,
        gate_address: str,
        item_count: int,
        passed_count: int,
        failed_count: int,
        open_count: int,
        blocker_count: int,
        warning_count: int,
        accepted: bool,
        release_ready: bool,
        state: str,
        items: Sequence[FederationReviewItem],
        content_address: str,
    ) -> None:
        self.queue_id, self.version, self.boundary = queue_id, version, boundary
        self.federation_address, self.runtime_address = federation_address, runtime_address
        self.assurance_address, self.gate_address = assurance_address, gate_address
        self.item_count, self.passed_count, self.failed_count = item_count, passed_count, failed_count
        self.open_count, self.blocker_count, self.warning_count = open_count, blocker_count, warning_count
        self.accepted, self.release_ready, self.state = accepted, release_ready, state
        self.items, self.content_address = tuple(items), content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.queue_id, "review queue ID", 256)
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("review queue contract is invalid")
        for name, value in (("federation", self.federation_address), ("runtime", self.runtime_address), ("assurance", self.assurance_address), ("gate", self.gate_address)):
            _address(value, f"review queue {name} address")
        for name, value in (("item", self.item_count), ("passed", self.passed_count), ("failed", self.failed_count), ("open", self.open_count), ("blocker", self.blocker_count), ("warning", self.warning_count)):
            _count(value, f"review queue {name} count", MAX_ITEMS)
        _bool(self.accepted, "review queue accepted")
        _bool(self.release_ready, "review queue release-ready")
        _queue_state(self.state)
        if self.item_count != len(self.items) or self.passed_count + self.failed_count != self.item_count:
            raise ValidationError("review queue item counts are not conserved")
        if self.failed_count != self.blocker_count + self.warning_count or self.open_count != self.failed_count:
            raise ValidationError("review queue failure counts are not conserved")
        for ordinal, item in enumerate(self.items):
            if not isinstance(item, FederationReviewItem) or item.ordinal != ordinal:
                raise ValidationError("review queue items must have contiguous ordinals")
        if self.passed_count != sum(item.passed for item in self.items):
            raise ValidationError("review queue passed count does not match items")
        if self.failed_count != sum(not item.passed for item in self.items):
            raise ValidationError("review queue failed count does not match items")
        if self.open_count != sum(not item.passed for item in self.items):
            raise ValidationError("review queue open count does not match items")
        if self.blocker_count != sum(not item.passed and item.required for item in self.items):
            raise ValidationError("review queue blocker count does not match items")
        if self.warning_count != sum(not item.passed and not item.required for item in self.items):
            raise ValidationError("review queue warning count does not match items")
        expected_state = ReviewQueueState.BLOCKED.value if self.blocker_count else ReviewQueueState.REVIEW.value if self.warning_count else ReviewQueueState.CLEAR.value
        if self.state != expected_state:
            raise ValidationError("review queue state does not match items")
        if self.accepted != (self.blocker_count == 0) or self.release_ready != (self.accepted and self.warning_count == 0):
            raise ValidationError("review queue readiness does not match items")
        if len({item.item_id for item in self.items}) != len(self.items) or len({item.content_address for item in self.items}) != len(self.items):
            raise ValidationError("review queue item identities must be unique")
        _address(self.content_address, "review queue address")
        if not self.content_address.startswith("pending:") and address_review_queue(self) != self.content_address:
            raise ValidationError("review queue address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("review queue crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "queue_id": self.queue_id,
            "version": self.version,
            "boundary": self.boundary,
            "federation_address": self.federation_address,
            "runtime_address": self.runtime_address,
            "assurance_address": self.assurance_address,
            "gate_address": self.gate_address,
            "item_count": self.item_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "open_count": self.open_count,
            "blocker_count": self.blocker_count,
            "warning_count": self.warning_count,
            "accepted": self.accepted,
            "release_ready": self.release_ready,
            "state": self.state,
            "content_address": self.content_address,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.summary() | {"items": [item.to_dict() for item in self.items]}


def address_review_queue(value: FederationReviewQueue) -> str:
    return content_hash(value.summary() | {"content_address": None}, prefix=QUEUE_PREFIX)


class ReviewVerificationFinding:
    """One independently recomputed queue verification finding."""

    def __init__(self, ordinal: int, finding_id: str, severity: str, passed: bool, detail: str, evidence_address: str, content_address: str) -> None:
        self.ordinal, self.finding_id, self.severity = ordinal, finding_id, severity
        self.passed, self.detail = passed, detail
        self.evidence_address, self.content_address = evidence_address, content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "review verification finding ordinal", MAX_FINDINGS - 1)
        _text(self.finding_id, "review verification finding ID", 256)
        _severity(self.severity)
        _bool(self.passed, "review verification finding passed")
        _text(self.detail, "review verification finding detail", 4096)
        _address(self.evidence_address, "review verification evidence address")
        _address(self.content_address, "review verification finding address")
        if not self.content_address.startswith("pending:") and address_verification_finding(self) != self.content_address:
            raise ValidationError("review verification finding address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("review verification finding crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "finding_id": self.finding_id,
            "severity": self.severity,
            "passed": self.passed,
            "detail": self.detail,
            "evidence_address": self.evidence_address,
            "content_address": self.content_address,
        }


def address_verification_finding(value: ReviewVerificationFinding) -> str:
    return content_hash(value.to_dict() | {"ordinal": None, "content_address": None}, prefix=VERIFICATION_FINDING_PREFIX)


def _make_verification_finding(ordinal: int, finding_id: str, severity: str, passed: bool, detail: str, evidence_address: str) -> ReviewVerificationFinding:
    body = {
        "ordinal": ordinal,
        "finding_id": finding_id,
        "severity": severity,
        "passed": passed,
        "detail": detail,
        "evidence_address": evidence_address,
        "content_address": "pending:review-verification-finding",
    }
    provisional = ReviewVerificationFinding(**body)
    body["content_address"] = address_verification_finding(provisional)
    return ReviewVerificationFinding(**body)


class FederationReviewVerification:
    """Independent structural verification of one review queue."""

    def __init__(self, queue_address: str, gate_address: str, finding_count: int, passed_count: int, failed_count: int, blocker_count: int, warning_count: int, accepted: bool, release_ready: bool, state: str, findings: Sequence[ReviewVerificationFinding], content_address: str) -> None:
        self.queue_address, self.gate_address = queue_address, gate_address
        self.finding_count, self.passed_count, self.failed_count = finding_count, passed_count, failed_count
        self.blocker_count, self.warning_count = blocker_count, warning_count
        self.accepted, self.release_ready, self.state = accepted, release_ready, state
        self.findings, self.content_address = tuple(findings), content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.queue_address, "review verification queue address")
        _address(self.gate_address, "review verification gate address")
        for name, value in (("finding", self.finding_count), ("passed", self.passed_count), ("failed", self.failed_count), ("blocker", self.blocker_count), ("warning", self.warning_count)):
            _count(value, f"review verification {name} count", MAX_FINDINGS)
        _bool(self.accepted, "review verification accepted")
        _bool(self.release_ready, "review verification release-ready")
        _queue_state(self.state, "review verification state")
        if self.finding_count != len(self.findings) or self.passed_count + self.failed_count != self.finding_count or self.failed_count != self.blocker_count + self.warning_count:
            raise ValidationError("review verification finding counts are not conserved")
        for ordinal, finding in enumerate(self.findings):
            if not isinstance(finding, ReviewVerificationFinding) or finding.ordinal != ordinal:
                raise ValidationError("review verification findings must have contiguous ordinals")
        if self.passed_count != sum(finding.passed for finding in self.findings) or self.failed_count != sum(not finding.passed for finding in self.findings):
            raise ValidationError("review verification counts do not match findings")
        if self.blocker_count != sum(not finding.passed and finding.severity == gate_model.FindingSeverity.BLOCKER.value for finding in self.findings):
            raise ValidationError("review verification blocker count does not match findings")
        if self.warning_count != sum(not finding.passed and finding.severity == gate_model.FindingSeverity.WARNING.value for finding in self.findings):
            raise ValidationError("review verification warning count does not match findings")
        expected_state = ReviewQueueState.BLOCKED.value if self.blocker_count else ReviewQueueState.REVIEW.value if self.warning_count else ReviewQueueState.CLEAR.value
        if self.state != expected_state or self.accepted != (self.blocker_count == 0) or self.release_ready != (self.accepted and self.warning_count == 0):
            raise ValidationError("review verification state does not match findings")
        _address(self.content_address, "review verification address")
        if not self.content_address.startswith("pending:") and address_review_verification(self) != self.content_address:
            raise ValidationError("review verification address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("review verification crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "queue_address": self.queue_address,
            "gate_address": self.gate_address,
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


def address_review_verification(value: FederationReviewVerification) -> str:
    return content_hash(value.summary() | {"content_address": None}, prefix=VERIFICATION_PREFIX)


class FederationReviewBundle:
    """Queue plus independent verification receipt."""

    def __init__(self, queue: FederationReviewQueue, verification: FederationReviewVerification) -> None:
        self.queue, self.verification = queue, verification
        self._validate()

    def _validate(self) -> None:
        verify_review_queue(self.queue)
        verify_review_verification(self.verification)
        if self.verification.queue_address != self.queue.content_address or self.verification.gate_address != self.queue.gate_address:
            raise ValidationError("review verification linkage is invalid")
        # Verification readiness describes the health of this review
        # projection itself.  Queue readiness remains the source gate's
        # decision and may legitimately be false while every routing check
        # passes (for example, a source warning is awaiting review).
        if self.verification.gate_address != self.queue.gate_address:
            raise ValidationError("review queue and verification gate linkage is not conserved")
        if not _public(self.to_dict()):
            raise ValidationError("review bundle crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return self.queue.summary() | {
            "verification_address": self.verification.content_address,
            "verification_finding_count": self.verification.finding_count,
            "verification_failed_count": self.verification.failed_count,
            "verification_state": self.verification.state,
        }

    def to_dict(self) -> dict[str, Any]:
        return {"queue": self.queue.to_dict(), "verification": self.verification.to_dict()}


def _queue_items_from_gate(value: gate_model.FederationAssuranceGateBundle) -> tuple[FederationReviewItem, ...]:
    items: list[FederationReviewItem] = []
    for finding in value.assurance.findings:
        items.append(_make_item(len(items), f"finding:{finding.finding_id}", ReviewRecordType.FINDING.value, finding.finding_id, finding.plane, finding.severity, finding.passed, finding.detail, finding.evidence_address, finding.content_address))
    for check in value.gate.checks:
        items.append(_make_item(len(items), f"check:{check.check_id}", ReviewRecordType.CHECK.value, check.check_id, gate_model.GatePlane.TRANSPORT.value, check.severity, check.passed, check.detail, check.evidence_address, check.content_address))
    if not items or len(items) > MAX_ITEMS:
        raise ValidationError("source gate produces an invalid review item count")
    if len({item.item_id for item in items}) != len(items):
        raise ValidationError("source gate produces duplicate review item IDs")
    return tuple(items)


def build_review_queue(value: gate_model.FederationAssuranceGateBundle, *, queue_id: str = DEFAULT_QUEUE_ID) -> FederationReviewQueue:
    """Build the deterministic review queue from a verified source gate."""

    gate_model.verify_federation_assurance_gate(value)
    items = _queue_items_from_gate(value)
    failed = tuple(item for item in items if not item.passed)
    body = {
        "queue_id": queue_id,
        "version": VERSION,
        "boundary": BOUNDARY,
        "federation_address": value.gate.federation_address,
        "runtime_address": value.gate.runtime_address,
        "assurance_address": value.assurance.content_address,
        "gate_address": value.gate.content_address,
        "item_count": len(items),
        "passed_count": sum(item.passed for item in items),
        "failed_count": len(failed),
        "open_count": len(failed),
        "blocker_count": sum(item.required for item in failed),
        "warning_count": sum(not item.required for item in failed),
        "accepted": not any(item.required for item in failed),
        "release_ready": not failed,
        "state": ReviewQueueState.BLOCKED.value if any(item.required for item in failed) else ReviewQueueState.REVIEW.value if failed else ReviewQueueState.CLEAR.value,
        "items": items,
        "content_address": "pending:review-queue",
    }
    provisional = FederationReviewQueue(**body)
    body["content_address"] = address_review_queue(provisional)
    return FederationReviewQueue(**body)


def _review_verification_findings(queue: FederationReviewQueue, source: gate_model.FederationAssuranceGateBundle | None = None) -> tuple[ReviewVerificationFinding, ...]:
    source_gate_ok = source is not None and source.gate.content_address == queue.gate_address
    source_link_ok = source is not None and source.gate.federation_address == queue.federation_address and source.gate.runtime_address == queue.runtime_address and source.assurance.content_address == queue.assurance_address
    expected_items = _queue_items_from_gate(source) if source is not None and source_gate_ok else queue.items
    item_addresses_ok = all(address_review_item(item) == item.content_address for item in queue.items)
    item_count_ok = queue.item_count == len(expected_items) and queue.passed_count == sum(item.passed for item in expected_items) and queue.failed_count == sum(not item.passed for item in expected_items)
    findings_ok = tuple(item.record_type for item in queue.items).count(ReviewRecordType.FINDING.value) == (source.assurance.finding_count if source is not None and source_gate_ok else sum(item.record_type == ReviewRecordType.FINDING.value for item in queue.items))
    checks_ok = tuple(item.record_type for item in queue.items).count(ReviewRecordType.CHECK.value) == (source.gate.check_count if source is not None and source_gate_ok else sum(item.record_type == ReviewRecordType.CHECK.value for item in queue.items))
    state_ok = all(item.state == (ReviewItemState.CLEAR.value if item.passed else ReviewItemState.BLOCKED.value if item.required else ReviewItemState.OPEN.value) and item.priority == (ReviewPriority.NONE.value if item.passed else ReviewPriority.CRITICAL.value if item.required else ReviewPriority.HIGH.value) for item in queue.items)
    public_ok = _public(queue.to_dict())
    authoritative_ok = source is None or (queue.accepted == source.gate.accepted and queue.release_ready == source.gate.release_ready)
    checks = (
        ("source-gate-verified", gate_model.FindingSeverity.BLOCKER.value, source_gate_ok or source is None, "source gate address is available for independent review verification", queue.gate_address),
        ("source-linkage", gate_model.FindingSeverity.BLOCKER.value, source_link_ok or source is None, "source federation, runtime, and assurance links are conserved", queue.gate_address),
        ("item-counts", gate_model.FindingSeverity.BLOCKER.value, item_count_ok, "review item and pass/fail counts are conserved", queue.content_address),
        ("finding-projection", gate_model.FindingSeverity.BLOCKER.value, findings_ok, "all source assurance findings are routed once", queue.assurance_address),
        ("check-projection", gate_model.FindingSeverity.BLOCKER.value, checks_ok, "all source gate checks are routed once", queue.gate_address),
        ("item-addresses", gate_model.FindingSeverity.BLOCKER.value, item_addresses_ok, "review item addresses recompute from public projections", queue.content_address),
        ("state-priority", gate_model.FindingSeverity.BLOCKER.value, state_ok, "initial item state and priority follow severity and pass state", queue.content_address),
        ("queue-public-boundary", gate_model.FindingSeverity.BLOCKER.value, public_ok, "review queue has no private transport fields", queue.content_address),
        ("gate-authoritative", gate_model.FindingSeverity.WARNING.value, authoritative_ok, "source gate readiness remains authoritative", queue.gate_address),
        ("queue-address", gate_model.FindingSeverity.BLOCKER.value, address_review_queue(queue) == queue.content_address, "review queue address recomputes from its summary", queue.content_address),
    )
    return tuple(_make_verification_finding(i, finding_id, severity, passed, detail, evidence) for i, (finding_id, severity, passed, detail, evidence) in enumerate(checks))


def build_review_verification(queue: FederationReviewQueue, source: gate_model.FederationAssuranceGateBundle | None = None) -> FederationReviewVerification:
    findings = _review_verification_findings(queue, source)
    failed = tuple(item for item in findings if not item.passed)
    body = {
        "queue_address": queue.content_address,
        "gate_address": queue.gate_address,
        "finding_count": len(findings),
        "passed_count": len(findings) - len(failed),
        "failed_count": len(failed),
        "blocker_count": sum(item.severity == gate_model.FindingSeverity.BLOCKER.value for item in failed),
        "warning_count": sum(item.severity == gate_model.FindingSeverity.WARNING.value for item in failed),
        "accepted": not any(item.severity == gate_model.FindingSeverity.BLOCKER.value for item in failed),
        "release_ready": not failed,
        "state": ReviewQueueState.BLOCKED.value if any(item.severity == gate_model.FindingSeverity.BLOCKER.value for item in failed) else ReviewQueueState.REVIEW.value if failed else ReviewQueueState.CLEAR.value,
        "findings": findings,
        "content_address": "pending:review-verification",
    }
    provisional = FederationReviewVerification(**body)
    body["content_address"] = address_review_verification(provisional)
    return FederationReviewVerification(**body)


def build_review(value: gate_model.FederationAssuranceGateBundle, *, queue_id: str = DEFAULT_QUEUE_ID) -> FederationReviewBundle:
    queue = build_review_queue(value, queue_id=queue_id)
    return FederationReviewBundle(queue, build_review_verification(queue, value))


def build_review_from_gate_directory(directory: str | Path, *, queue_id: str = DEFAULT_QUEUE_ID) -> FederationReviewBundle:
    return build_review(gate_model.load_federation_assurance_gate(directory), queue_id=queue_id)


def verify_review_queue(value: FederationReviewQueue) -> FederationReviewQueue:
    if not isinstance(value, FederationReviewQueue):
        raise ValidationError("review queue verification requires a typed queue")
    value._validate()
    return value


def verify_review_verification(value: FederationReviewVerification) -> FederationReviewVerification:
    if not isinstance(value, FederationReviewVerification):
        raise ValidationError("review verification requires a typed verification")
    value._validate()
    return value


def verify_review(value: FederationReviewBundle) -> FederationReviewBundle:
    if not isinstance(value, FederationReviewBundle):
        raise ValidationError("review verification requires a typed bundle")
    value._validate()
    return value


def verify_review_against_gate(value: FederationReviewBundle, source: gate_model.FederationAssuranceGateBundle) -> FederationReviewBundle:
    gate_model.verify_federation_assurance_gate(source)
    expected = build_review(source, queue_id=value.queue.queue_id)
    if value.to_dict() != expected.to_dict():
        raise ValidationError("review bundle differs from its source gate")
    return verify_review(value)


def verify_review_directory_against_gate(directory: str | Path, gate_directory: str | Path) -> FederationReviewBundle:
    return verify_review_against_gate(load_review(directory), gate_model.load_federation_assurance_gate(gate_directory))


def item_from_mapping(value: Mapping[str, Any]) -> FederationReviewItem:
    body = dict(_mapping(value, "review item"))
    allowed = {"ordinal", "item_id", "record_type", "source_id", "plane", "severity", "required", "passed", "state", "priority", "detail", "evidence_address", "source_address", "content_address"}
    _strict(body, allowed, "review item")
    _required(body, allowed, "review item")
    return FederationReviewItem(**body)


def queue_from_mapping(value: Mapping[str, Any]) -> FederationReviewQueue:
    body = dict(_mapping(value, "review queue"))
    allowed = {"queue_id", "version", "boundary", "federation_address", "runtime_address", "assurance_address", "gate_address", "item_count", "passed_count", "failed_count", "open_count", "blocker_count", "warning_count", "accepted", "release_ready", "state", "items", "content_address"}
    _strict(body, allowed, "review queue")
    _required(body, allowed, "review queue")
    body["items"] = tuple(item_from_mapping(item) for item in _mapping_sequence(body["items"], "review queue items"))
    return FederationReviewQueue(**body)


def verification_finding_from_mapping(value: Mapping[str, Any]) -> ReviewVerificationFinding:
    body = dict(_mapping(value, "review verification finding"))
    allowed = {"ordinal", "finding_id", "severity", "passed", "detail", "evidence_address", "content_address"}
    _strict(body, allowed, "review verification finding")
    _required(body, allowed, "review verification finding")
    return ReviewVerificationFinding(**body)


def verification_from_mapping(value: Mapping[str, Any]) -> FederationReviewVerification:
    body = dict(_mapping(value, "review verification"))
    allowed = {"queue_address", "gate_address", "finding_count", "passed_count", "failed_count", "blocker_count", "warning_count", "accepted", "release_ready", "state", "findings", "content_address"}
    _strict(body, allowed, "review verification")
    _required(body, allowed, "review verification")
    body["findings"] = tuple(verification_finding_from_mapping(item) for item in _mapping_sequence(body["findings"], "review verification findings"))
    return FederationReviewVerification(**body)


def review_from_mapping(value: Mapping[str, Any]) -> FederationReviewBundle:
    body = _mapping(value, "review bundle")
    _strict(body, {"queue", "verification"}, "review bundle")
    _required(body, {"queue", "verification"}, "review bundle")
    return FederationReviewBundle(queue_from_mapping(body["queue"]), verification_from_mapping(body["verification"]))


class ReviewQuery:
    """Bounded query over review items and verification findings."""

    RESOURCES = ("summary", "items", "findings", "checks", "open", "blockers", "warnings", "clear", "passed", "failed")

    def __init__(self, resource: str, record_type: str | None, plane: str | None, severity: str | None, state: str | None, priority: str | None, passed: bool | None, required: bool | None, text: str | None, offset: int, limit: int) -> None:
        self.resource, self.record_type, self.plane, self.severity = resource, record_type, plane, severity
        self.state, self.priority, self.passed, self.required = state, priority, passed, required
        self.text, self.offset, self.limit = text, offset, limit
        self._validate()

    def _validate(self) -> None:
        if self.resource not in self.RESOURCES:
            raise ValidationError("review query resource is invalid")
        if self.record_type is not None:
            _record_type(self.record_type, "review query record type")
        if self.plane is not None:
            _gate_plane(self.plane, "review query plane")
        if self.severity is not None:
            _severity(self.severity, "review query severity")
        if self.state is not None:
            _item_state(self.state, "review query state")
        if self.priority is not None:
            _priority(self.priority, "review query priority")
        if self.passed is not None:
            _bool(self.passed, "review query passed")
        if self.required is not None:
            _bool(self.required, "review query required")
        if self.text is not None:
            _text(self.text, "review query text", 512)
        _count(self.offset, "review query offset", MAX_QUERY_ITEMS)
        _count(self.limit, "review query limit", MAX_QUERY_ITEMS)
        if self.limit == 0:
            raise ValidationError("review query limit must be positive")

    def to_dict(self) -> dict[str, Any]:
        return {"resource": self.resource, "record_type": self.record_type, "plane": self.plane, "severity": self.severity, "state": self.state, "priority": self.priority, "passed": self.passed, "required": self.required, "text": self.text, "offset": self.offset, "limit": self.limit}


def address_review_query(value: ReviewQuery) -> str:
    return content_hash(value.to_dict(), prefix=QUERY_PREFIX)


class ReviewQueryResult:
    def __init__(self, query: ReviewQuery, source_address: str, returned: Sequence[Mapping[str, Any]], total_count: int, content_address: str) -> None:
        self.query, self.source_address = query, source_address
        self.returned, self.total_count, self.content_address = tuple(dict(item) for item in returned), total_count, content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.source_address, "review query source address")
        _count(self.total_count, "review query total count")
        if len(self.returned) > self.query.limit:
            raise ValidationError("review query returned more than its limit")
        if not all(_public(item) for item in self.returned):
            raise ValidationError("review query crosses the public boundary")
        _address(self.content_address, "review query result address")
        if not self.content_address.startswith("pending:") and address_query_result(self) != self.content_address:
            raise ValidationError("review query result address mismatch")

    def to_dict(self) -> dict[str, Any]:
        return {"query": self.query.to_dict(), "query_address": address_review_query(self.query), "source_address": self.source_address, "total_count": self.total_count, "returned_count": len(self.returned), "items": list(self.returned), "content_address": self.content_address}


def address_query_result(value: ReviewQueryResult) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX + "-result")


def _matches_item(item: Mapping[str, Any], query: ReviewQuery) -> bool:
    if query.record_type is not None and item.get("record_type") != query.record_type:
        return False
    if query.plane is not None and item.get("plane") != query.plane:
        return False
    if query.severity is not None and item.get("severity") != query.severity:
        return False
    if query.state is not None and item.get("state") != query.state:
        return False
    if query.priority is not None and item.get("priority") != query.priority:
        return False
    if query.passed is not None and item.get("passed") != query.passed:
        return False
    if query.required is not None and item.get("required") != query.required:
        return False
    if query.text is not None:
        needle = query.text.casefold()
        if needle not in " ".join(str(item.get(field, "")) for field in ("item_id", "source_id", "detail", "source_address")).casefold():
            return False
    return True


def query_review(value: FederationReviewBundle, *, resource: str = "summary", record_type: str | None = None, plane: str | None = None, severity: str | None = None, state: str | None = None, priority: str | None = None, passed: bool | None = None, required: bool | None = None, text: str | None = None, offset: int = 0, limit: int = 50) -> ReviewQueryResult:
    verify_review(value)
    query = ReviewQuery(resource, record_type, plane, severity, state, priority, passed, required, text, offset, limit)
    if resource == "summary":
        rows: tuple[Mapping[str, Any], ...] = (value.summary(),)
    elif resource == "findings":
        rows = tuple(item for item in value.verification.findings)
        rows = tuple(item.to_dict() for item in rows)
    else:
        rows = tuple(item.to_dict() for item in value.queue.items)
        if resource == "checks":
            rows = tuple(item for item in rows if item["record_type"] == ReviewRecordType.CHECK.value)
        elif resource == "open":
            rows = tuple(item for item in rows if not item["passed"])
        elif resource == "blockers":
            rows = tuple(item for item in rows if not item["passed"] and item["required"])
        elif resource == "warnings":
            rows = tuple(item for item in rows if not item["passed"] and not item["required"])
        elif resource == "clear" or resource == "passed":
            rows = tuple(item for item in rows if item["passed"])
        elif resource == "failed":
            rows = tuple(item for item in rows if not item["passed"])
    filtered = tuple(item for item in rows if resource == "summary" or _matches_item(item, query))
    returned = filtered[offset : offset + limit]
    body = {"query": query, "source_address": value.queue.content_address, "returned": returned, "total_count": len(filtered), "content_address": "pending:review-query-result"}
    provisional = ReviewQueryResult(**body)
    body["content_address"] = address_query_result(provisional)
    return ReviewQueryResult(**body)


def verify_review_query(value: ReviewQueryResult) -> ReviewQueryResult:
    if not isinstance(value, ReviewQueryResult):
        raise ValidationError("review query verification requires a typed result")
    value._validate()
    return value


def review_json(value: FederationReviewBundle) -> str:
    verify_review(value)
    return canonical_json(value.to_dict())


def review_csv(value: FederationReviewBundle) -> str:
    verify_review(value)
    output = io.StringIO()
    rows = [item.to_dict() for item in value.queue.items]
    fields = ("ordinal", "item_id", "record_type", "source_id", "plane", "severity", "required", "passed", "state", "priority", "detail", "evidence_address", "source_address", "content_address")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def query_json(value: ReviewQueryResult) -> str:
    return canonical_json(verify_review_query(value).to_dict())


def query_csv(value: ReviewQueryResult) -> str:
    result = verify_review_query(value)
    output = io.StringIO()
    rows = list(result.returned)
    fields = tuple(sorted({key for row in rows for key in row})) if rows else ("content_address", "detail", "item_id", "passed", "record_type", "severity", "source_address", "source_id", "state")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def render_review_markdown(value: FederationReviewBundle) -> str:
    verify_review(value)
    summary = value.summary()
    lines = ["# Federation gate review", "", f"- Queue: `{summary['queue_id']}`", f"- State: **{summary['state']}**", f"- Items: {summary['item_count']} ({summary['failed_count']} open)", f"- Gate release-ready: `{summary['release_ready']}`", "", "| Type | ID | Severity | State | Priority | Passed |", "| --- | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {item.record_type} | `{item.source_id}` | {item.severity} | {item.state} | {item.priority} | {str(item.passed).lower()} |" for item in value.queue.items)
    return "\n".join(lines) + "\n"


def render_query_markdown(value: ReviewQueryResult) -> str:
    result = verify_review_query(value)
    lines = ["# Federation gate review query", "", f"- Resource: `{result.query.resource}`", f"- Total: {result.total_count}", f"- Returned: {len(result.returned)}", ""]
    if not result.returned:
        return "\n".join(lines + ["No matching records.", ""])
    fields = tuple(sorted({key for row in result.returned for key in row}))
    lines.append("| " + " | ".join(fields) + " |")
    lines.append("| " + " | ".join("---" for _ in fields) + " |")
    for row in result.returned:
        lines.append("| " + " | ".join(str(row.get(field, "")).replace("|", "\\|") for field in fields) + " |")
    return "\n".join(lines) + "\n"


def _queue_documents(value: FederationReviewBundle) -> dict[str, bytes]:
    return {
        QUEUE_NAME: canonical_bytes(value.queue.summary()),
        ITEMS_NAME: canonical_bytes({"items": [item.to_dict() for item in value.queue.items]}),
        VERIFICATION_NAME: canonical_bytes(value.verification.to_dict()),
    }


def _manifest_body(version: str, boundary: str, linkage: Mapping[str, Any], files: Sequence[str], documents: Mapping[str, bytes], prefix: str) -> dict[str, Any]:
    body = {"version": version, "boundary": boundary, **dict(linkage), "files": list(files), "artifact_count": len(files) - 1, "artifacts": [{"name": name, "bytes": len(documents[name]), "byte_address": _file_address(name, documents[name])} for name in files if name != MANIFEST_NAME], "content_address": "pending:review-manifest"}
    return body | {"content_address": content_hash(body | {"content_address": None}, prefix=prefix)}


def _manifest_address(value: Mapping[str, Any], prefix: str) -> str:
    return content_hash(dict(value) | {"content_address": None}, prefix=prefix)


def _write_exact(destination: str | Path, documents: Mapping[str, bytes], manifest: Mapping[str, Any], files: Sequence[str], label: str, overwrite: bool) -> Path:
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        _require_directory(target, f"{label} destination")
        if any(target.iterdir()) and not overwrite:
            raise ValidationError(f"{label} destination already exists")
    # Keep the private staging name short enough for Windows while retaining
    # the public, fully-qualified namespace in every persisted address.
    temporary = Path(tempfile.mkdtemp(prefix=".glio-review-", dir=str(target.parent)))
    try:
        for name in files:
            raw = canonical_bytes(manifest) if name == MANIFEST_NAME else documents[name]
            (temporary / name).write_bytes(raw)
        if target.exists():
            shutil.rmtree(target)
        os.replace(temporary, target)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return target


def write_review(value: FederationReviewBundle, directory: str | Path, *, overwrite: bool = False) -> Path:
    verify_review(value)
    documents = _queue_documents(value)
    manifest = _manifest_body(VERSION, BOUNDARY, {"federation_address": value.queue.federation_address, "runtime_address": value.queue.runtime_address, "assurance_address": value.queue.assurance_address, "gate_address": value.queue.gate_address, "queue_address": value.queue.content_address, "verification_address": value.verification.content_address}, QUEUE_FILES, documents, MANIFEST_PREFIX)
    return _write_exact(directory, documents, manifest, QUEUE_FILES, "review", overwrite)


def _load_documents(directory: str | Path, files: Sequence[str], label: str) -> tuple[dict[str, dict[str, Any]], dict[str, bytes]]:
    target = Path(directory)
    _require_directory(target, f"{label} directory")
    if {item.name for item in target.iterdir()} != set(files):
        raise ValidationError(f"{label} file set is invalid")
    parsed: dict[str, dict[str, Any]] = {}
    raw_documents: dict[str, bytes] = {}
    for name in files:
        path = target / name
        _require_regular_file(path, f"{label} {name}")
        raw = path.read_bytes()
        parsed[name] = _read_json(path, f"{label} {name}")
        if raw != canonical_bytes(parsed[name]):
            raise ValidationError(f"{label} {name} is not canonical JSON")
        raw_documents[name] = raw
    return parsed, raw_documents


def _verify_manifest(manifest: Mapping[str, Any], files: Sequence[str], documents: Mapping[str, bytes], linkage: Mapping[str, Any], label: str, prefix: str) -> None:
    allowed = set(linkage) | {"version", "boundary", "files", "artifact_count", "artifacts", "content_address"}
    _strict(manifest, allowed, label + " manifest")
    _required(manifest, allowed, label + " manifest")
    if manifest["version"] != VERSION or manifest["boundary"] != BOUNDARY or tuple(manifest["files"]) != tuple(files) or manifest["artifact_count"] != len(files) - 1 or _manifest_address(manifest, prefix) != manifest["content_address"]:
        raise ValidationError(f"{label} manifest contract is invalid")
    for key, expected in linkage.items():
        if manifest[key] != expected:
            raise ValidationError(f"{label} manifest linkage is invalid: {key}")
    artifacts = _mapping_sequence(manifest["artifacts"], label + " artifacts")
    if len(artifacts) != len(files) - 1 or {item.get("name") for item in artifacts} != set(files) - {MANIFEST_NAME}:
        raise ValidationError(f"{label} artifact set is invalid")
    for artifact in artifacts:
        _strict(artifact, {"name", "bytes", "byte_address"}, label + " artifact")
        name = _text(artifact["name"], label + " artifact name", 128)
        if artifact["bytes"] != len(documents[name]) or artifact["byte_address"] != _file_address(name, documents[name]):
            raise ValidationError(f"{label} artifact receipt mismatch: {name}")


def load_review(directory: str | Path) -> FederationReviewBundle:
    parsed, raw_documents = _load_documents(directory, QUEUE_FILES, "review")
    queue_document = parsed[QUEUE_NAME] | {"items": parsed[ITEMS_NAME]["items"]}
    value = review_from_mapping({"queue": queue_document, "verification": parsed[VERIFICATION_NAME]})
    _verify_manifest(parsed[MANIFEST_NAME], QUEUE_FILES, raw_documents, {"federation_address": value.queue.federation_address, "runtime_address": value.queue.runtime_address, "assurance_address": value.queue.assurance_address, "gate_address": value.queue.gate_address, "queue_address": value.queue.content_address, "verification_address": value.verification.content_address}, "review", MANIFEST_PREFIX)
    return value


def verify_review_directory(directory: str | Path) -> FederationReviewBundle:
    return load_review(directory)


def item_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "FederationReviewItem", "type": "object", "additionalProperties": False, "required": list(FederationReviewItem(0, "pending:item", "finding", "pending", "source", "blocker", True, True, "clear", "none", "pending", NO_EVIDENCE, "pending:source", "pending:item-address").to_dict().keys()), "properties": {"ordinal": {"type": "integer", "minimum": 0}, "item_id": {"type": "string"}, "record_type": {"enum": list(ReviewRecordType)}, "source_id": {"type": "string"}, "plane": {"enum": list(gate_model.GatePlane)}, "severity": {"enum": list(gate_model.FindingSeverity)}, "required": {"type": "boolean"}, "passed": {"type": "boolean"}, "state": {"enum": list(ReviewItemState)}, "priority": {"enum": list(ReviewPriority)}, "detail": {"type": "string"}, "evidence_address": {"type": "string"}, "source_address": {"type": "string"}, "content_address": {"type": "string"}}}


def queue_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "FederationReviewQueue", "type": "object", "additionalProperties": False, "required": ["queue_id", "version", "boundary", "federation_address", "runtime_address", "assurance_address", "gate_address", "item_count", "passed_count", "failed_count", "open_count", "blocker_count", "warning_count", "accepted", "release_ready", "state", "items", "content_address"], "properties": {"queue_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "federation_address": {"type": "string"}, "runtime_address": {"type": "string"}, "assurance_address": {"type": "string"}, "gate_address": {"type": "string"}, "item_count": {"type": "integer", "minimum": 0, "maximum": MAX_ITEMS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_ITEMS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_ITEMS}, "open_count": {"type": "integer", "minimum": 0, "maximum": MAX_ITEMS}, "blocker_count": {"type": "integer", "minimum": 0, "maximum": MAX_ITEMS}, "warning_count": {"type": "integer", "minimum": 0, "maximum": MAX_ITEMS}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "state": {"enum": list(ReviewQueueState)}, "items": {"type": "array", "maxItems": MAX_ITEMS, "items": {"$ref": "#/$defs/item"}}, "content_address": {"type": "string"}}, "$defs": {"item": item_schema()}}


def verification_finding_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "FederationReviewVerificationFinding", "type": "object", "additionalProperties": False, "required": ["ordinal", "finding_id", "severity", "passed", "detail", "evidence_address", "content_address"], "properties": {"ordinal": {"type": "integer", "minimum": 0}, "finding_id": {"type": "string"}, "severity": {"enum": list(gate_model.FindingSeverity)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_address": {"type": "string"}, "content_address": {"type": "string"}}}


def verification_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "FederationReviewVerification", "type": "object", "additionalProperties": False, "required": ["queue_address", "gate_address", "finding_count", "passed_count", "failed_count", "blocker_count", "warning_count", "accepted", "release_ready", "state", "findings", "content_address"], "properties": {"queue_address": {"type": "string"}, "gate_address": {"type": "string"}, "finding_count": {"type": "integer", "minimum": 0, "maximum": MAX_FINDINGS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_FINDINGS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_FINDINGS}, "blocker_count": {"type": "integer", "minimum": 0, "maximum": MAX_FINDINGS}, "warning_count": {"type": "integer", "minimum": 0, "maximum": MAX_FINDINGS}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "state": {"enum": list(ReviewQueueState)}, "findings": {"type": "array", "maxItems": MAX_FINDINGS, "items": {"$ref": "#/$defs/finding"}}, "content_address": {"type": "string"}}, "$defs": {"finding": verification_finding_schema()}}


def review_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "FederationReviewBundle", "type": "object", "additionalProperties": False, "required": ["queue", "verification"], "properties": {"queue": {"$ref": "#/$defs/queue"}, "verification": {"$ref": "#/$defs/verification"}}, "$defs": {"queue": queue_schema(), "verification": verification_schema()}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "FederationReviewQuery", "type": "object", "additionalProperties": False, "required": ["resource", "record_type", "plane", "severity", "state", "priority", "passed", "required", "text", "offset", "limit"], "properties": {"resource": {"enum": list(ReviewQuery.RESOURCES)}, "record_type": {"type": ["string", "null"]}, "plane": {"type": ["string", "null"]}, "severity": {"type": ["string", "null"]}, "state": {"type": ["string", "null"]}, "priority": {"type": ["string", "null"]}, "passed": {"type": ["boolean", "null"]}, "required": {"type": ["boolean", "null"]}, "text": {"type": ["string", "null"]}, "offset": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_QUERY_ITEMS}}}


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "FederationReviewManifest", "type": "object", "additionalProperties": False, "required": ["version", "boundary", "federation_address", "runtime_address", "assurance_address", "gate_address", "queue_address", "verification_address", "files", "artifact_count", "artifacts", "content_address"], "properties": {"version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "federation_address": {"type": "string"}, "runtime_address": {"type": "string"}, "assurance_address": {"type": "string"}, "gate_address": {"type": "string"}, "queue_address": {"type": "string"}, "verification_address": {"type": "string"}, "files": {"const": list(QUEUE_FILES)}, "artifact_count": {"const": len(QUEUE_FILES) - 1}, "artifacts": {"type": "array", "maxItems": len(QUEUE_FILES) - 1}, "content_address": {"type": "string"}}}


def review_capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "queue": {"max_items": MAX_ITEMS, "files": list(QUEUE_FILES), "states": list(ReviewQueueState), "priorities": list(ReviewPriority), "record_types": list(ReviewRecordType)}, "verification": {"finding_count": 10, "max_findings": MAX_FINDINGS}, "queries": {"resources": list(ReviewQuery.RESOURCES), "max_limit": MAX_QUERY_ITEMS, "filters": ["record_type", "plane", "severity", "state", "priority", "passed", "required", "text"]}, "public_boundary": {"source_paths": False, "private_metadata": False, "identity_free": True}}


class FederationReviewDecision:
    """One immutable, evidence-aware action in the review ledger."""

    def __init__(self, ordinal: int, decision_id: str, item_id: str, item_address: str, action: str, rationale: str, evidence_address: str, previous_address: str, content_address: str) -> None:
        self.ordinal, self.decision_id = ordinal, decision_id
        self.item_id, self.item_address = item_id, item_address
        self.action, self.rationale, self.evidence_address = action, rationale, evidence_address
        self.previous_address, self.content_address = previous_address, content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "review decision ordinal", MAX_DECISIONS - 1)
        _text(self.decision_id, "review decision ID", 256)
        _text(self.item_id, "review decision item ID", 256)
        _address(self.item_address, "review decision item address")
        _action(self.action)
        _text(self.rationale, "review decision rationale", 4096)
        _address(self.evidence_address, "review decision evidence address")
        _address(self.previous_address, "review decision previous address")
        _address(self.content_address, "review decision address")
        if self.action in {ReviewAction.REMEDIATE.value, ReviewAction.WAIVE.value} and self.evidence_address == NO_EVIDENCE:
            raise ValidationError("review decision action requires evidence")
        if self.action not in {ReviewAction.REMEDIATE.value, ReviewAction.WAIVE.value} and self.evidence_address != NO_EVIDENCE:
            raise ValidationError("review decision carries unexpected evidence")
        if not self.content_address.startswith("pending:") and address_decision(self) != self.content_address:
            raise ValidationError("review decision address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("review decision crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "decision_id": self.decision_id, "item_id": self.item_id, "item_address": self.item_address, "action": self.action, "rationale": self.rationale, "evidence_address": self.evidence_address, "previous_address": self.previous_address, "content_address": self.content_address}


def address_decision(value: FederationReviewDecision) -> str:
    return content_hash(value.to_dict() | {"ordinal": None, "content_address": None}, prefix=DECISION_PREFIX)


def decision_from_mapping(value: Mapping[str, Any]) -> FederationReviewDecision:
    body = dict(_mapping(value, "review decision"))
    allowed = {"ordinal", "decision_id", "item_id", "item_address", "action", "rationale", "evidence_address", "previous_address", "content_address"}
    _strict(body, allowed, "review decision")
    _required(body, allowed, "review decision")
    return FederationReviewDecision(**body)


class FederationReviewReplayItem:
    """Current state of one queue item after ledger replay."""

    def __init__(self, ordinal: int, item_id: str, item_address: str, initial_state: str, state: str, last_action: str | None, last_decision_address: str | None, content_address: str) -> None:
        self.ordinal, self.item_id, self.item_address = ordinal, item_id, item_address
        self.initial_state, self.state = initial_state, state
        self.last_action, self.last_decision_address = last_action, last_decision_address
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "replay item ordinal", MAX_ITEMS - 1)
        _text(self.item_id, "replay item ID", 256)
        _address(self.item_address, "replay item address")
        _item_state(self.initial_state, "replay initial state")
        _item_state(self.state, "replay item state")
        if self.last_action is not None:
            _action(self.last_action, "replay last action")
        if self.last_decision_address is not None:
            _address(self.last_decision_address, "replay last decision address")
        _address(self.content_address, "replay item address")
        if not self.content_address.startswith("pending:") and address_replay_item(self) != self.content_address:
            raise ValidationError("replay item address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("replay item crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "item_id": self.item_id, "item_address": self.item_address, "initial_state": self.initial_state, "state": self.state, "last_action": self.last_action, "last_decision_address": self.last_decision_address, "content_address": self.content_address}


def address_replay_item(value: FederationReviewReplayItem) -> str:
    return content_hash(value.to_dict() | {"ordinal": None, "content_address": None}, prefix=REPLAY_PREFIX + "-item")


def replay_item_from_mapping(value: Mapping[str, Any]) -> FederationReviewReplayItem:
    body = dict(_mapping(value, "review replay item"))
    allowed = {"ordinal", "item_id", "item_address", "initial_state", "state", "last_action", "last_decision_address", "content_address"}
    _strict(body, allowed, "review replay item")
    _required(body, allowed, "review replay item")
    return FederationReviewReplayItem(**body)


def _initial_replay_item(item: FederationReviewItem) -> FederationReviewReplayItem:
    body = {"ordinal": item.ordinal, "item_id": item.item_id, "item_address": item.content_address, "initial_state": item.state, "state": item.state, "last_action": None, "last_decision_address": None, "content_address": "pending:replay-item"}
    provisional = FederationReviewReplayItem(**body)
    body["content_address"] = address_replay_item(provisional)
    return FederationReviewReplayItem(**body)


def _next_item_state(item: FederationReviewItem, current: str, action: str, evidence_address: str) -> str:
    if action == ReviewAction.ACKNOWLEDGE.value:
        if current in {ReviewItemState.CLEAR.value, ReviewItemState.RESOLVED.value, ReviewItemState.WAIVED.value}:
            raise ValidationError("acknowledge requires an open review item")
        return ReviewItemState.ACKNOWLEDGED.value
    if action == ReviewAction.REMEDIATE.value:
        if evidence_address == NO_EVIDENCE:
            raise ValidationError("remediation requires evidence")
        if current in {ReviewItemState.CLEAR.value, ReviewItemState.RESOLVED.value, ReviewItemState.WAIVED.value}:
            raise ValidationError("remediation requires an unresolved review item")
        return ReviewItemState.RESOLVED.value
    if action == ReviewAction.WAIVE.value:
        if item.required:
            raise ValidationError("blocker review items cannot be waived")
        if evidence_address == NO_EVIDENCE:
            raise ValidationError("waiver requires evidence")
        if current in {ReviewItemState.CLEAR.value, ReviewItemState.RESOLVED.value, ReviewItemState.WAIVED.value}:
            raise ValidationError("waiver requires an unresolved review item")
        return ReviewItemState.WAIVED.value
    if action == ReviewAction.ESCALATE.value:
        if current in {ReviewItemState.CLEAR.value, ReviewItemState.RESOLVED.value, ReviewItemState.WAIVED.value}:
            raise ValidationError("escalation requires an unresolved review item")
        return ReviewItemState.ESCALATED.value
    if action == ReviewAction.REOPEN.value:
        if current not in {ReviewItemState.ACKNOWLEDGED.value, ReviewItemState.RESOLVED.value, ReviewItemState.WAIVED.value, ReviewItemState.ESCALATED.value}:
            raise ValidationError("reopen requires a previously handled review item")
        return ReviewItemState.BLOCKED.value if item.required else ReviewItemState.OPEN.value
    raise ValidationError("review action is invalid")


class FederationReviewReplay:
    """Deterministic replay projection for a decision ledger."""

    def __init__(self, queue_address: str, gate_address: str, source_accepted: bool, source_release_ready: bool, entry_count: int, item_count: int, clear_count: int, open_count: int, blocked_count: int, acknowledged_count: int, resolved_count: int, waived_count: int, escalated_count: int, state: str, accepted: bool, release_ready: bool, items: Sequence[FederationReviewReplayItem], content_address: str) -> None:
        self.queue_address, self.gate_address = queue_address, gate_address
        self.source_accepted, self.source_release_ready = source_accepted, source_release_ready
        self.entry_count, self.item_count = entry_count, item_count
        self.clear_count, self.open_count, self.blocked_count = clear_count, open_count, blocked_count
        self.acknowledged_count, self.resolved_count = acknowledged_count, resolved_count
        self.waived_count, self.escalated_count = waived_count, escalated_count
        self.state, self.accepted, self.release_ready = state, accepted, release_ready
        self.items, self.content_address = tuple(items), content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.queue_address, "replay queue address")
        _address(self.gate_address, "replay gate address")
        _bool(self.source_accepted, "replay source accepted")
        _bool(self.source_release_ready, "replay source release-ready")
        _count(self.entry_count, "replay entry count", MAX_DECISIONS)
        for name, value in (("item", self.item_count), ("clear", self.clear_count), ("open", self.open_count), ("blocked", self.blocked_count), ("acknowledged", self.acknowledged_count), ("resolved", self.resolved_count), ("waived", self.waived_count), ("escalated", self.escalated_count)):
            _count(value, f"replay {name} count", MAX_ITEMS)
        _queue_state(self.state, "replay state")
        _bool(self.accepted, "replay accepted")
        _bool(self.release_ready, "replay release-ready")
        if self.item_count != len(self.items) or sum((self.clear_count, self.open_count, self.blocked_count, self.acknowledged_count, self.resolved_count, self.waived_count, self.escalated_count)) != self.item_count:
            raise ValidationError("replay item state counts are not conserved")
        for ordinal, item in enumerate(self.items):
            if not isinstance(item, FederationReviewReplayItem) or item.ordinal != ordinal:
                raise ValidationError("replay items must have contiguous ordinals")
        expected_state = ReviewQueueState.BLOCKED.value if not self.source_accepted or self.blocked_count else ReviewQueueState.REVIEW.value if not self.source_release_ready or any(item.state in {ReviewItemState.OPEN.value, ReviewItemState.ACKNOWLEDGED.value, ReviewItemState.ESCALATED.value} for item in self.items) else ReviewQueueState.CLEAR.value
        if self.state != expected_state or self.accepted != self.source_accepted or self.release_ready != (self.source_release_ready and self.state == ReviewQueueState.CLEAR.value):
            raise ValidationError("replay state does not match source and item states")
        _address(self.content_address, "replay address")
        if not self.content_address.startswith("pending:") and address_replay(self) != self.content_address:
            raise ValidationError("replay address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("replay crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {"queue_address": self.queue_address, "gate_address": self.gate_address, "source_accepted": self.source_accepted, "source_release_ready": self.source_release_ready, "entry_count": self.entry_count, "item_count": self.item_count, "clear_count": self.clear_count, "open_count": self.open_count, "blocked_count": self.blocked_count, "acknowledged_count": self.acknowledged_count, "resolved_count": self.resolved_count, "waived_count": self.waived_count, "escalated_count": self.escalated_count, "state": self.state, "accepted": self.accepted, "release_ready": self.release_ready, "content_address": self.content_address}

    def to_dict(self) -> dict[str, Any]:
        return self.summary() | {"items": [item.to_dict() for item in self.items]}


def address_replay(value: FederationReviewReplay) -> str:
    return content_hash(value.summary() | {"content_address": None}, prefix=REPLAY_PREFIX)


def replay_from_mapping(value: Mapping[str, Any]) -> FederationReviewReplay:
    body = dict(_mapping(value, "review replay"))
    allowed = {"queue_address", "gate_address", "source_accepted", "source_release_ready", "entry_count", "item_count", "clear_count", "open_count", "blocked_count", "acknowledged_count", "resolved_count", "waived_count", "escalated_count", "state", "accepted", "release_ready", "items", "content_address"}
    _strict(body, allowed, "review replay")
    _required(body, allowed, "review replay")
    body["items"] = tuple(replay_item_from_mapping(item) for item in _mapping_sequence(body["items"], "review replay items"))
    return FederationReviewReplay(**body)


def _build_replay(items: Sequence[FederationReviewItem], entries: Sequence[FederationReviewDecision], queue_address: str, gate_address: str, source_accepted: bool, source_release_ready: bool) -> FederationReviewReplay:
    replayed = [_initial_replay_item(item) for item in items]
    by_id = {item.item_id: item for item in items}
    for entry in entries:
        item = by_id.get(entry.item_id)
        if item is None or item.content_address != entry.item_address:
            raise ValidationError("decision ledger item linkage is invalid")
        current = replayed[item.ordinal]
        new_state = _next_item_state(item, current.state, entry.action, entry.evidence_address)
        body = current.to_dict() | {"state": new_state, "last_action": entry.action, "last_decision_address": entry.content_address, "content_address": "pending:replay-item"}
        provisional = FederationReviewReplayItem(**body)
        body["content_address"] = address_replay_item(provisional)
        replayed[item.ordinal] = FederationReviewReplayItem(**body)
    counts = {state.value: 0 for state in ReviewItemState}
    for item in replayed:
        counts[item.state] += 1
    state = ReviewQueueState.BLOCKED.value if not source_accepted or counts[ReviewItemState.BLOCKED.value] else ReviewQueueState.REVIEW.value if not source_release_ready or any(item.state in {ReviewItemState.OPEN.value, ReviewItemState.ACKNOWLEDGED.value, ReviewItemState.ESCALATED.value} for item in replayed) else ReviewQueueState.CLEAR.value
    body = {"queue_address": queue_address, "gate_address": gate_address, "source_accepted": source_accepted, "source_release_ready": source_release_ready, "entry_count": len(entries), "item_count": len(replayed), "clear_count": counts[ReviewItemState.CLEAR.value], "open_count": counts[ReviewItemState.OPEN.value], "blocked_count": counts[ReviewItemState.BLOCKED.value], "acknowledged_count": counts[ReviewItemState.ACKNOWLEDGED.value], "resolved_count": counts[ReviewItemState.RESOLVED.value], "waived_count": counts[ReviewItemState.WAIVED.value], "escalated_count": counts[ReviewItemState.ESCALATED.value], "state": state, "accepted": source_accepted, "release_ready": source_release_ready and state == ReviewQueueState.CLEAR.value, "items": tuple(replayed), "content_address": "pending:replay"}
    provisional = FederationReviewReplay(**body)
    body["content_address"] = address_replay(provisional)
    return FederationReviewReplay(**body)


class FederationReviewDecisionLedger:
    """Append-only decisions over a frozen review queue snapshot."""

    def __init__(self, ledger_id: str, version: str, boundary: str, queue_address: str, gate_address: str, assurance_address: str, head_address: str, entry_count: int, acknowledge_count: int, remediate_count: int, waive_count: int, escalate_count: int, reopen_count: int, accepted: bool, release_ready: bool, state: str, items: Sequence[FederationReviewItem], entries: Sequence[FederationReviewDecision], replay: FederationReviewReplay, content_address: str) -> None:
        self.ledger_id, self.version, self.boundary = ledger_id, version, boundary
        self.queue_address, self.gate_address, self.assurance_address = queue_address, gate_address, assurance_address
        self.head_address = head_address
        self.entry_count = entry_count
        self.acknowledge_count, self.remediate_count = acknowledge_count, remediate_count
        self.waive_count, self.escalate_count, self.reopen_count = waive_count, escalate_count, reopen_count
        self.accepted, self.release_ready, self.state = accepted, release_ready, state
        self.items, self.entries, self.replay = tuple(items), tuple(entries), replay
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.ledger_id, "decision ledger ID", 256)
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("decision ledger contract is invalid")
        for name, value in (("queue", self.queue_address), ("gate", self.gate_address), ("assurance", self.assurance_address), ("head", self.head_address)):
            _address(value, f"decision ledger {name} address")
        _count(self.entry_count, "decision ledger entry count", MAX_DECISIONS)
        for name, value in (("acknowledge", self.acknowledge_count), ("remediate", self.remediate_count), ("waive", self.waive_count), ("escalate", self.escalate_count), ("reopen", self.reopen_count)):
            _count(value, f"decision ledger {name} count", MAX_DECISIONS)
        _bool(self.accepted, "decision ledger accepted")
        _bool(self.release_ready, "decision ledger release-ready")
        _queue_state(self.state, "decision ledger state")
        if self.entry_count != len(self.entries) or self.entry_count != sum((self.acknowledge_count, self.remediate_count, self.waive_count, self.escalate_count, self.reopen_count)):
            raise ValidationError("decision ledger entry counts are not conserved")
        if len(self.items) == 0 or len(self.items) > MAX_ITEMS:
            raise ValidationError("decision ledger item count is invalid")
        for ordinal, item in enumerate(self.items):
            if not isinstance(item, FederationReviewItem) or item.ordinal != ordinal:
                raise ValidationError("decision ledger items must be contiguous")
        item_ids = {item.item_id for item in self.items}
        item_addresses = {item.content_address for item in self.items}
        if len(item_ids) != len(self.items) or len(item_addresses) != len(self.items):
            raise ValidationError("decision ledger item identities must be unique")
        decision_ids: set[str] = set()
        for ordinal, entry in enumerate(self.entries):
            if not isinstance(entry, FederationReviewDecision) or entry.ordinal != ordinal:
                raise ValidationError("decision ledger entries must be contiguous")
            if entry.decision_id in decision_ids or entry.item_id not in item_ids or entry.item_address not in item_addresses:
                raise ValidationError("decision ledger entry identity is invalid")
            decision_ids.add(entry.decision_id)
            expected_previous = INITIAL_HEAD if ordinal == 0 else self.entries[ordinal - 1].content_address
            if entry.previous_address != expected_previous:
                raise ValidationError("decision ledger ancestry is not contiguous")
        expected_head = INITIAL_HEAD if not self.entries else self.entries[-1].content_address
        if self.head_address != expected_head:
            raise ValidationError("decision ledger head is invalid")
        replay = _build_replay(self.items, self.entries, self.queue_address, self.gate_address, self.accepted, self.release_ready if self.entry_count == 0 else self.replay.source_release_ready)
        if replay.to_dict() != self.replay.to_dict():
            raise ValidationError("decision ledger replay is stale")
        if self.accepted != replay.accepted or self.release_ready != replay.release_ready or self.state != replay.state:
            raise ValidationError("decision ledger state does not match replay")
        _address(self.replay.content_address, "decision ledger replay address")
        _address(self.content_address, "decision ledger address")
        if not self.content_address.startswith("pending:") and address_ledger(self) != self.content_address:
            raise ValidationError("decision ledger address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("decision ledger crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {"ledger_id": self.ledger_id, "version": self.version, "boundary": self.boundary, "queue_address": self.queue_address, "gate_address": self.gate_address, "assurance_address": self.assurance_address, "head_address": self.head_address, "entry_count": self.entry_count, "acknowledge_count": self.acknowledge_count, "remediate_count": self.remediate_count, "waive_count": self.waive_count, "escalate_count": self.escalate_count, "reopen_count": self.reopen_count, "accepted": self.accepted, "release_ready": self.release_ready, "state": self.state, "replay_address": self.replay.content_address, "content_address": self.content_address}

    def to_dict(self) -> dict[str, Any]:
        return self.summary() | {"items": [item.to_dict() for item in self.items], "entries": [entry.to_dict() for entry in self.entries], "replay": self.replay.to_dict()}


def address_ledger(value: FederationReviewDecisionLedger) -> str:
    return content_hash(value.summary() | {"content_address": None}, prefix=LEDGER_PREFIX)


def build_decision_ledger(value: FederationReviewBundle, *, ledger_id: str = DEFAULT_LEDGER_ID) -> FederationReviewDecisionLedger:
    verify_review(value)
    replay = _build_replay(value.queue.items, (), value.queue.content_address, value.queue.gate_address, value.queue.accepted, value.queue.release_ready)
    body = {"ledger_id": ledger_id, "version": VERSION, "boundary": BOUNDARY, "queue_address": value.queue.content_address, "gate_address": value.queue.gate_address, "assurance_address": value.queue.assurance_address, "head_address": INITIAL_HEAD, "entry_count": 0, "acknowledge_count": 0, "remediate_count": 0, "waive_count": 0, "escalate_count": 0, "reopen_count": 0, "accepted": value.queue.accepted, "release_ready": value.queue.release_ready, "state": value.queue.state, "items": value.queue.items, "entries": (), "replay": replay, "content_address": "pending:decision-ledger"}
    provisional = FederationReviewDecisionLedger(**body)
    body["content_address"] = address_ledger(provisional)
    return FederationReviewDecisionLedger(**body)


def build_decision_ledger_from_directory(directory: str | Path, *, ledger_id: str = DEFAULT_LEDGER_ID) -> FederationReviewDecisionLedger:
    return build_decision_ledger(load_review(directory), ledger_id=ledger_id)


def verify_decision_ledger(value: FederationReviewDecisionLedger) -> FederationReviewDecisionLedger:
    if not isinstance(value, FederationReviewDecisionLedger):
        raise ValidationError("decision ledger verification requires a typed ledger")
    value._validate()
    return value


def append_decision(value: FederationReviewDecisionLedger, *, item_id: str | None = None, item_address: str | None = None, action: str, rationale: str, evidence_address: str = NO_EVIDENCE, decision_id: str | None = None, expected_head_address: str | None = None) -> FederationReviewDecisionLedger:
    verify_decision_ledger(value)
    if expected_head_address != value.head_address:
        raise ValidationError("decision ledger expected head does not match")
    selected = [item for item in value.items if (item_id is None or item.item_id == item_id) and (item_address is None or item.content_address == item_address)]
    if len(selected) != 1:
        raise ValidationError("decision ledger action must identify exactly one item")
    item = selected[0]
    _action(action)
    evidence_address = _text(evidence_address, "decision evidence address", 2048)
    _address(evidence_address, "decision evidence address")
    current = value.replay.items[item.ordinal].state
    _next_item_state(item, current, action, evidence_address)
    ordinal = len(value.entries)
    body = {"ordinal": ordinal, "decision_id": decision_id or f"{value.ledger_id}-decision-{ordinal}", "item_id": item.item_id, "item_address": item.content_address, "action": action, "rationale": rationale, "evidence_address": evidence_address, "previous_address": value.head_address, "content_address": "pending:decision"}
    provisional = FederationReviewDecision(**body)
    body["content_address"] = address_decision(provisional)
    entry = FederationReviewDecision(**body)
    entries = value.entries + (entry,)
    replay = _build_replay(value.items, entries, value.queue_address, value.gate_address, value.replay.source_accepted, value.replay.source_release_ready)
    counts = {member.value: 0 for member in ReviewAction}
    for existing in entries:
        counts[existing.action] += 1
    ledger_body = value.summary() | {"head_address": entry.content_address, "entry_count": len(entries), "acknowledge_count": counts[ReviewAction.ACKNOWLEDGE.value], "remediate_count": counts[ReviewAction.REMEDIATE.value], "waive_count": counts[ReviewAction.WAIVE.value], "escalate_count": counts[ReviewAction.ESCALATE.value], "reopen_count": counts[ReviewAction.REOPEN.value], "accepted": replay.accepted, "release_ready": replay.release_ready, "state": replay.state, "items": value.items, "entries": entries, "replay": replay, "content_address": "pending:decision-ledger"}
    ledger_body.pop("replay_address", None)
    provisional_ledger = FederationReviewDecisionLedger(**ledger_body)
    ledger_body["content_address"] = address_ledger(provisional_ledger)
    return FederationReviewDecisionLedger(**ledger_body)


def decision_ledger_from_mapping(value: Mapping[str, Any]) -> FederationReviewDecisionLedger:
    body = dict(_mapping(value, "decision ledger"))
    allowed = {"ledger_id", "version", "boundary", "queue_address", "gate_address", "assurance_address", "head_address", "entry_count", "acknowledge_count", "remediate_count", "waive_count", "escalate_count", "reopen_count", "accepted", "release_ready", "state", "replay_address", "content_address", "items", "entries", "replay"}
    _strict(body, allowed, "decision ledger")
    _required(body, allowed - {"replay_address"}, "decision ledger")
    body.pop("replay_address", None)
    body["items"] = tuple(item_from_mapping(item) for item in _mapping_sequence(body["items"], "decision ledger items"))
    body["entries"] = tuple(decision_from_mapping(item) for item in _mapping_sequence(body["entries"], "decision ledger entries"))
    body["replay"] = replay_from_mapping(body["replay"])
    return FederationReviewDecisionLedger(**body)


def _ledger_documents(value: FederationReviewDecisionLedger) -> dict[str, bytes]:
    ledger_document = value.summary() | {"items": [item.to_dict() for item in value.items]}
    return {LEDGER_NAME: canonical_bytes(ledger_document), ENTRIES_NAME: canonical_bytes({"entries": [entry.to_dict() for entry in value.entries]}), REPLAY_NAME: canonical_bytes(value.replay.to_dict())}


def write_decision_ledger(value: FederationReviewDecisionLedger, directory: str | Path, *, overwrite: bool = False) -> Path:
    verify_decision_ledger(value)
    documents = _ledger_documents(value)
    manifest = _manifest_body(VERSION, BOUNDARY, {"queue_address": value.queue_address, "gate_address": value.gate_address, "assurance_address": value.assurance_address, "ledger_address": value.content_address, "replay_address": value.replay.content_address}, LEDGER_FILES, documents, MANIFEST_PREFIX + "-ledger")
    return _write_exact(directory, documents, manifest, LEDGER_FILES, "decision ledger", overwrite)


def load_decision_ledger(directory: str | Path) -> FederationReviewDecisionLedger:
    parsed, raw_documents = _load_documents(directory, LEDGER_FILES, "decision ledger")
    entries_document = parsed[ENTRIES_NAME]
    _strict(entries_document, {"entries"}, "decision ledger entries document")
    _required(entries_document, {"entries"}, "decision ledger entries document")
    ledger_document = parsed[LEDGER_NAME] | {"entries": entries_document["entries"], "replay": parsed[REPLAY_NAME]}
    value = decision_ledger_from_mapping(ledger_document)
    _verify_manifest(parsed[MANIFEST_NAME], LEDGER_FILES, raw_documents, {"queue_address": value.queue_address, "gate_address": value.gate_address, "assurance_address": value.assurance_address, "ledger_address": value.content_address, "replay_address": value.replay.content_address}, "decision ledger", MANIFEST_PREFIX + "-ledger")
    return value


def verify_decision_ledger_directory(directory: str | Path) -> FederationReviewDecisionLedger:
    return load_decision_ledger(directory)


class DecisionQuery:
    RESOURCES = ("summary", "items", "entries", "decisions", "open", "resolved", "waived", "escalated")

    def __init__(self, resource: str, item_id: str | None, action: str | None, state: str | None, text: str | None, offset: int, limit: int) -> None:
        self.resource, self.item_id, self.action, self.state = resource, item_id, action, state
        self.text, self.offset, self.limit = text, offset, limit
        self._validate()

    def _validate(self) -> None:
        if self.resource not in self.RESOURCES:
            raise ValidationError("decision query resource is invalid")
        if self.item_id is not None:
            _text(self.item_id, "decision query item ID", 256)
        if self.action is not None:
            _action(self.action, "decision query action")
        if self.state is not None:
            _item_state(self.state, "decision query state")
        if self.text is not None:
            _text(self.text, "decision query text", 512)
        _count(self.offset, "decision query offset", MAX_QUERY_ITEMS)
        _count(self.limit, "decision query limit", MAX_QUERY_ITEMS)
        if self.limit == 0:
            raise ValidationError("decision query limit must be positive")

    def to_dict(self) -> dict[str, Any]:
        return {"resource": self.resource, "item_id": self.item_id, "action": self.action, "state": self.state, "text": self.text, "offset": self.offset, "limit": self.limit}


def address_decision_query(value: DecisionQuery) -> str:
    return content_hash(value.to_dict(), prefix=QUERY_PREFIX + "-decisions")


class DecisionQueryResult:
    def __init__(self, query: DecisionQuery, source_address: str, returned: Sequence[Mapping[str, Any]], total_count: int, content_address: str) -> None:
        self.query, self.source_address = query, source_address
        self.returned, self.total_count, self.content_address = tuple(dict(row) for row in returned), total_count, content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.source_address, "decision query source address")
        _count(self.total_count, "decision query total count")
        if len(self.returned) > self.query.limit or not all(_public(row) for row in self.returned):
            raise ValidationError("decision query result is invalid")
        _address(self.content_address, "decision query result address")
        if not self.content_address.startswith("pending:") and address_decision_query_result(self) != self.content_address:
            raise ValidationError("decision query result address mismatch")

    def to_dict(self) -> dict[str, Any]:
        return {"query": self.query.to_dict(), "query_address": address_decision_query(self.query), "source_address": self.source_address, "total_count": self.total_count, "returned_count": len(self.returned), "items": list(self.returned), "content_address": self.content_address}


def address_decision_query_result(value: DecisionQueryResult) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX + "-decision-result")


def _matches_decision(row: Mapping[str, Any], query: DecisionQuery) -> bool:
    if query.item_id is not None and row.get("item_id") != query.item_id:
        return False
    if query.action is not None and row.get("action") != query.action:
        return False
    if query.state is not None and row.get("state") != query.state:
        return False
    if query.text is not None and query.text.casefold() not in " ".join(str(row.get(field, "")) for field in ("item_id", "action", "rationale", "item_address")).casefold():
        return False
    return True


def query_decision_ledger(value: FederationReviewDecisionLedger, *, resource: str = "summary", item_id: str | None = None, action: str | None = None, state: str | None = None, text: str | None = None, offset: int = 0, limit: int = 50) -> DecisionQueryResult:
    verify_decision_ledger(value)
    query = DecisionQuery(resource, item_id, action, state, text, offset, limit)
    if resource == "summary":
        rows: tuple[Mapping[str, Any], ...] = (value.summary(),)
    elif resource == "items":
        rows = tuple(item.to_dict() | {"last_action": value.replay.items[item.ordinal].last_action, "last_state": value.replay.items[item.ordinal].state} for item in value.items)
    elif resource in {"entries", "decisions"}:
        rows = tuple(entry.to_dict() for entry in value.entries)
    else:
        allowed = {"open": {ReviewItemState.OPEN.value, ReviewItemState.ACKNOWLEDGED.value}, "resolved": {ReviewItemState.RESOLVED.value}, "waived": {ReviewItemState.WAIVED.value}, "escalated": {ReviewItemState.ESCALATED.value}}[resource]
        rows = tuple(item.to_dict() | {"last_action": value.replay.items[item.ordinal].last_action, "last_state": value.replay.items[item.ordinal].state} for item in value.items if value.replay.items[item.ordinal].state in allowed)
    filtered = tuple(row for row in rows if resource == "summary" or _matches_decision(row, query))
    returned = filtered[offset : offset + limit]
    body = {"query": query, "source_address": value.content_address, "returned": returned, "total_count": len(filtered), "content_address": "pending:decision-query"}
    provisional = DecisionQueryResult(**body)
    body["content_address"] = address_decision_query_result(provisional)
    return DecisionQueryResult(**body)


def verify_decision_query(value: DecisionQueryResult) -> DecisionQueryResult:
    if not isinstance(value, DecisionQueryResult):
        raise ValidationError("decision query verification requires a typed result")
    value._validate()
    return value


def decision_ledger_json(value: FederationReviewDecisionLedger) -> str:
    return canonical_json(verify_decision_ledger(value).to_dict())


def decision_ledger_csv(value: FederationReviewDecisionLedger) -> str:
    rows = [entry.to_dict() for entry in verify_decision_ledger(value).entries]
    output = io.StringIO()
    fields = ("ordinal", "decision_id", "item_id", "item_address", "action", "rationale", "evidence_address", "previous_address", "content_address")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def decision_query_json(value: DecisionQueryResult) -> str:
    return canonical_json(verify_decision_query(value).to_dict())


def decision_query_csv(value: DecisionQueryResult) -> str:
    result = verify_decision_query(value)
    output = io.StringIO()
    rows = list(result.returned)
    fields = tuple(sorted({key for row in rows for key in row})) if rows else ("action", "content_address", "item_id", "state")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def render_decision_ledger_markdown(value: FederationReviewDecisionLedger) -> str:
    verify_decision_ledger(value)
    lines = ["# Federation review decision ledger", "", f"- Ledger: `{value.ledger_id}`", f"- State: **{value.state}**", f"- Entries: {value.entry_count}", f"- Release-ready: `{value.release_ready}`", "", "| Ordinal | Item | Action | Evidence |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {entry.ordinal} | `{entry.item_id}` | {entry.action} | `{entry.evidence_address}` |" for entry in value.entries)
    if not value.entries:
        lines.append("| — | — | no decisions | — |")
    return "\n".join(lines) + "\n"


def render_decision_query_markdown(value: DecisionQueryResult) -> str:
    result = verify_decision_query(value)
    lines = ["# Federation decision query", "", f"- Resource: `{result.query.resource}`", f"- Total: {result.total_count}", f"- Returned: {len(result.returned)}", ""]
    if not result.returned:
        return "\n".join(lines + ["No matching records.", ""])
    fields = tuple(sorted({key for row in result.returned for key in row}))
    lines.extend(["| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"])
    lines.extend("| " + " | ".join(str(row.get(field, "")).replace("|", "\\|") for field in fields) + " |" for row in result.returned)
    return "\n".join(lines) + "\n"


class FederationReviewDiffItem:
    """One stable final-state comparison between two decision ledgers."""

    def __init__(self, ordinal: int, item_id: str, item_address: str, action: str, direction: str, baseline_state: str | None, candidate_state: str | None, baseline_decision_address: str | None, candidate_decision_address: str | None, content_address: str) -> None:
        self.ordinal, self.item_id, self.item_address = ordinal, item_id, item_address
        self.action, self.direction = action, direction
        self.baseline_state, self.candidate_state = baseline_state, candidate_state
        self.baseline_decision_address, self.candidate_decision_address = baseline_decision_address, candidate_decision_address
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "review diff item ordinal", MAX_ITEMS * 2 - 1)
        _text(self.item_id, "review diff item ID", 256)
        _address(self.item_address, "review diff item address")
        _diff_action(self.action)
        _diff_direction(self.direction)
        if self.baseline_state is not None:
            _item_state(self.baseline_state, "review diff baseline state")
        if self.candidate_state is not None:
            _item_state(self.candidate_state, "review diff candidate state")
        for name, value in (("baseline decision", self.baseline_decision_address), ("candidate decision", self.candidate_decision_address)):
            if value is not None:
                _address(value, f"review diff {name} address")
        _address(self.content_address, "review diff item address")
        if not self.content_address.startswith("pending:") and address_diff_item(self) != self.content_address:
            raise ValidationError("review diff item address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("review diff item crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "item_id": self.item_id, "item_address": self.item_address, "action": self.action, "direction": self.direction, "baseline_state": self.baseline_state, "candidate_state": self.candidate_state, "baseline_decision_address": self.baseline_decision_address, "candidate_decision_address": self.candidate_decision_address, "content_address": self.content_address}


def address_diff_item(value: FederationReviewDiffItem) -> str:
    return content_hash(value.to_dict() | {"ordinal": None, "content_address": None}, prefix=DIFF_ITEM_PREFIX)


def diff_item_from_mapping(value: Mapping[str, Any]) -> FederationReviewDiffItem:
    body = dict(_mapping(value, "review diff item"))
    allowed = {"ordinal", "item_id", "item_address", "action", "direction", "baseline_state", "candidate_state", "baseline_decision_address", "candidate_decision_address", "content_address"}
    _strict(body, allowed, "review diff item")
    _required(body, allowed, "review diff item")
    return FederationReviewDiffItem(**body)


def _state_score(value: str | None) -> int:
    return {None: -1, ReviewItemState.BLOCKED.value: 0, ReviewItemState.OPEN.value: 1, ReviewItemState.ESCALATED.value: 2, ReviewItemState.ACKNOWLEDGED.value: 3, ReviewItemState.WAIVED.value: 4, ReviewItemState.RESOLVED.value: 5, ReviewItemState.CLEAR.value: 6}[value]


class FederationReviewDecisionDiff:
    """Addressed comparison of two verified decision ledgers."""

    def __init__(self, diff_id: str, version: str, boundary: str, baseline_address: str, candidate_address: str, item_count: int, added_count: int, removed_count: int, unchanged_count: int, changed_count: int, improved_count: int, regressed_count: int, accepted: bool, release_ready: bool, state: str, items: Sequence[FederationReviewDiffItem], content_address: str) -> None:
        self.diff_id, self.version, self.boundary = diff_id, version, boundary
        self.baseline_address, self.candidate_address = baseline_address, candidate_address
        self.item_count, self.added_count, self.removed_count = item_count, added_count, removed_count
        self.unchanged_count, self.changed_count = unchanged_count, changed_count
        self.improved_count, self.regressed_count = improved_count, regressed_count
        self.accepted, self.release_ready, self.state = accepted, release_ready, state
        self.items, self.content_address = tuple(items), content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.diff_id, "review diff ID", 256)
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("review diff contract is invalid")
        _address(self.baseline_address, "review diff baseline address")
        _address(self.candidate_address, "review diff candidate address")
        for name, value in (("item", self.item_count), ("added", self.added_count), ("removed", self.removed_count), ("unchanged", self.unchanged_count), ("changed", self.changed_count), ("improved", self.improved_count), ("regressed", self.regressed_count)):
            _count(value, f"review diff {name} count", MAX_ITEMS * 2)
        _bool(self.accepted, "review diff accepted")
        _bool(self.release_ready, "review diff release-ready")
        _diff_direction(self.state, "review diff state")
        if self.item_count != len(self.items) or self.item_count != self.added_count + self.removed_count + self.unchanged_count + self.changed_count:
            raise ValidationError("review diff counts are not conserved")
        if self.improved_count > self.changed_count or self.regressed_count > self.changed_count:
            raise ValidationError("review diff direction counts are invalid")
        for ordinal, item in enumerate(self.items):
            if not isinstance(item, FederationReviewDiffItem) or item.ordinal != ordinal:
                raise ValidationError("review diff items must be contiguous")
        if len({item.item_id for item in self.items}) != len(self.items):
            raise ValidationError("review diff item identities must be unique")
        expected_state = DiffDirection.IMPROVED.value if self.improved_count and not self.regressed_count else DiffDirection.REGRESSED.value if self.regressed_count and not self.improved_count else DiffDirection.NONE.value
        if self.state != expected_state:
            raise ValidationError("review diff state does not match directions")
        _address(self.content_address, "review diff address")
        if not self.content_address.startswith("pending:") and address_diff(self) != self.content_address:
            raise ValidationError("review diff address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("review diff crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {"diff_id": self.diff_id, "version": self.version, "boundary": self.boundary, "baseline_address": self.baseline_address, "candidate_address": self.candidate_address, "item_count": self.item_count, "added_count": self.added_count, "removed_count": self.removed_count, "unchanged_count": self.unchanged_count, "changed_count": self.changed_count, "improved_count": self.improved_count, "regressed_count": self.regressed_count, "accepted": self.accepted, "release_ready": self.release_ready, "state": self.state, "content_address": self.content_address}

    def to_dict(self) -> dict[str, Any]:
        return self.summary() | {"items": [item.to_dict() for item in self.items]}


def address_diff(value: FederationReviewDecisionDiff) -> str:
    return content_hash(value.summary() | {"content_address": None}, prefix=DIFF_PREFIX)


def build_decision_diff(baseline: FederationReviewDecisionLedger, candidate: FederationReviewDecisionLedger, *, diff_id: str = DEFAULT_DIFF_ID) -> FederationReviewDecisionDiff:
    verify_decision_ledger(baseline)
    verify_decision_ledger(candidate)
    left = {item.item_id: (item, baseline.replay.items[item.ordinal]) for item in baseline.items}
    right = {item.item_id: (item, candidate.replay.items[item.ordinal]) for item in candidate.items}
    items: list[FederationReviewDiffItem] = []
    for item_id in sorted(set(left) | set(right)):
        left_value, right_value = left.get(item_id), right.get(item_id)
        if left_value is None:
            action, direction, baseline_state, candidate_state = DiffAction.ADDED.value, DiffDirection.NONE.value, None, right_value[1].state
            item_address, baseline_decision, candidate_decision = right_value[0].content_address, None, right_value[1].last_decision_address
        elif right_value is None:
            action, direction, baseline_state, candidate_state = DiffAction.REMOVED.value, DiffDirection.NONE.value, left_value[1].state, None
            item_address, baseline_decision, candidate_decision = left_value[0].content_address, left_value[1].last_decision_address, None
        else:
            baseline_state, candidate_state = left_value[1].state, right_value[1].state
            action = DiffAction.UNCHANGED.value if baseline_state == candidate_state and left_value[1].last_decision_address == right_value[1].last_decision_address else DiffAction.CHANGED.value
            direction = DiffDirection.IMPROVED.value if _state_score(candidate_state) > _state_score(baseline_state) else DiffDirection.REGRESSED.value if _state_score(candidate_state) < _state_score(baseline_state) else DiffDirection.NONE.value
            item_address, baseline_decision, candidate_decision = right_value[0].content_address, left_value[1].last_decision_address, right_value[1].last_decision_address
        body = {"ordinal": len(items), "item_id": item_id, "item_address": item_address, "action": action, "direction": direction, "baseline_state": baseline_state, "candidate_state": candidate_state, "baseline_decision_address": baseline_decision, "candidate_decision_address": candidate_decision, "content_address": "pending:review-diff-item"}
        provisional = FederationReviewDiffItem(**body)
        body["content_address"] = address_diff_item(provisional)
        items.append(FederationReviewDiffItem(**body))
    improved = sum(item.direction == DiffDirection.IMPROVED.value for item in items)
    regressed = sum(item.direction == DiffDirection.REGRESSED.value for item in items)
    body = {"diff_id": diff_id, "version": VERSION, "boundary": BOUNDARY, "baseline_address": baseline.content_address, "candidate_address": candidate.content_address, "item_count": len(items), "added_count": sum(item.action == DiffAction.ADDED.value for item in items), "removed_count": sum(item.action == DiffAction.REMOVED.value for item in items), "unchanged_count": sum(item.action == DiffAction.UNCHANGED.value for item in items), "changed_count": sum(item.action == DiffAction.CHANGED.value for item in items), "improved_count": improved, "regressed_count": regressed, "accepted": candidate.accepted, "release_ready": candidate.release_ready, "state": DiffDirection.IMPROVED.value if improved and not regressed else DiffDirection.REGRESSED.value if regressed and not improved else DiffDirection.NONE.value, "items": tuple(items), "content_address": "pending:review-diff"}
    provisional = FederationReviewDecisionDiff(**body)
    body["content_address"] = address_diff(provisional)
    return FederationReviewDecisionDiff(**body)


def diff_from_mapping(value: Mapping[str, Any]) -> FederationReviewDecisionDiff:
    body = dict(_mapping(value, "review decision diff"))
    allowed = {"diff_id", "version", "boundary", "baseline_address", "candidate_address", "item_count", "added_count", "removed_count", "unchanged_count", "changed_count", "improved_count", "regressed_count", "accepted", "release_ready", "state", "items", "content_address"}
    _strict(body, allowed, "review decision diff")
    _required(body, allowed, "review decision diff")
    body["items"] = tuple(diff_item_from_mapping(item) for item in _mapping_sequence(body["items"], "review decision diff items"))
    return FederationReviewDecisionDiff(**body)


def diff_json(value: FederationReviewDecisionDiff) -> str:
    return canonical_json(verify_decision_diff(value).to_dict())


def diff_csv(value: FederationReviewDecisionDiff) -> str:
    rows = [item.to_dict() for item in verify_decision_diff(value).items]
    output = io.StringIO()
    fields = ("ordinal", "item_id", "item_address", "action", "direction", "baseline_state", "candidate_state", "baseline_decision_address", "candidate_decision_address", "content_address")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def render_diff_markdown(value: FederationReviewDecisionDiff) -> str:
    verify_decision_diff(value)
    lines = ["# Federation review decision diff", "", f"- State: **{value.state}**", f"- Changed: {value.changed_count}", f"- Improved: {value.improved_count}", f"- Regressed: {value.regressed_count}", "", "| Item | Action | Direction | Baseline | Candidate |", "| --- | --- | --- | --- | --- |"]
    lines.extend(f"| `{item.item_id}` | {item.action} | {item.direction} | {item.baseline_state or '—'} | {item.candidate_state or '—'} |" for item in value.items)
    return "\n".join(lines) + "\n"


def verify_decision_diff(value: FederationReviewDecisionDiff) -> FederationReviewDecisionDiff:
    if not isinstance(value, FederationReviewDecisionDiff):
        raise ValidationError("review diff verification requires a typed diff")
    value._validate()
    return value


def write_decision_diff(value: FederationReviewDecisionDiff, directory: str | Path, *, overwrite: bool = False) -> Path:
    verify_decision_diff(value)
    documents = {DIFF_NAME: canonical_bytes(value.to_dict())}
    manifest = _manifest_body(VERSION, BOUNDARY, {"baseline_address": value.baseline_address, "candidate_address": value.candidate_address, "diff_address": value.content_address}, DIFF_FILES, documents, MANIFEST_PREFIX + "-diff")
    return _write_exact(directory, documents, manifest, DIFF_FILES, "decision diff", overwrite)


def load_decision_diff(directory: str | Path) -> FederationReviewDecisionDiff:
    parsed, raw_documents = _load_documents(directory, DIFF_FILES, "decision diff")
    value = diff_from_mapping(parsed[DIFF_NAME])
    _verify_manifest(parsed[MANIFEST_NAME], DIFF_FILES, raw_documents, {"baseline_address": value.baseline_address, "candidate_address": value.candidate_address, "diff_address": value.content_address}, "decision diff", MANIFEST_PREFIX + "-diff")
    return value


def verify_decision_diff_directory(directory: str | Path) -> FederationReviewDecisionDiff:
    return load_decision_diff(directory)


def decision_diff_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "FederationReviewDecisionDiff", "type": "object", "additionalProperties": False, "required": ["diff_id", "version", "boundary", "baseline_address", "candidate_address", "item_count", "added_count", "removed_count", "unchanged_count", "changed_count", "improved_count", "regressed_count", "accepted", "release_ready", "state", "items", "content_address"], "properties": {"diff_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "baseline_address": {"type": "string"}, "candidate_address": {"type": "string"}, "item_count": {"type": "integer", "minimum": 0}, "added_count": {"type": "integer", "minimum": 0}, "removed_count": {"type": "integer", "minimum": 0}, "unchanged_count": {"type": "integer", "minimum": 0}, "changed_count": {"type": "integer", "minimum": 0}, "improved_count": {"type": "integer", "minimum": 0}, "regressed_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "state": {"enum": list(DiffDirection)}, "items": {"type": "array", "items": {"$ref": "#/$defs/item"}}, "content_address": {"type": "string"}}, "$defs": {"item": {"type": "object", "additionalProperties": False, "required": ["ordinal", "item_id", "item_address", "action", "direction", "baseline_state", "candidate_state", "baseline_decision_address", "candidate_decision_address", "content_address"], "properties": {"ordinal": {"type": "integer"}, "item_id": {"type": "string"}, "item_address": {"type": "string"}, "action": {"enum": list(DiffAction)}, "direction": {"enum": list(DiffDirection)}, "baseline_state": {"type": ["string", "null"]}, "candidate_state": {"type": ["string", "null"]}, "baseline_decision_address": {"type": ["string", "null"]}, "candidate_decision_address": {"type": ["string", "null"]}, "content_address": {"type": "string"}}}}}


def decision_diff_item_schema() -> dict[str, Any]:
    """Return the standalone schema for one ledger comparison row."""

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "FederationReviewDiffItem",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "ordinal",
            "item_id",
            "item_address",
            "action",
            "direction",
            "baseline_state",
            "candidate_state",
            "baseline_decision_address",
            "candidate_decision_address",
            "content_address",
        ],
        "properties": {
            "ordinal": {"type": "integer", "minimum": 0},
            "item_id": {"type": "string"},
            "item_address": {"type": "string"},
            "action": {"enum": list(DiffAction)},
            "direction": {"enum": list(DiffDirection)},
            "baseline_state": {"type": ["string", "null"]},
            "candidate_state": {"type": ["string", "null"]},
            "baseline_decision_address": {"type": ["string", "null"]},
            "candidate_decision_address": {"type": ["string", "null"]},
            "content_address": {"type": "string"},
        },
    }


def ledger_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "FederationReviewDecisionLedger", "type": "object", "additionalProperties": False, "required": ["ledger_id", "version", "boundary", "queue_address", "gate_address", "assurance_address", "head_address", "entry_count", "acknowledge_count", "remediate_count", "waive_count", "escalate_count", "reopen_count", "accepted", "release_ready", "state", "items", "entries", "replay", "content_address"], "properties": {"ledger_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "queue_address": {"type": "string"}, "gate_address": {"type": "string"}, "assurance_address": {"type": "string"}, "head_address": {"type": "string"}, "entry_count": {"type": "integer", "minimum": 0}, "acknowledge_count": {"type": "integer", "minimum": 0}, "remediate_count": {"type": "integer", "minimum": 0}, "waive_count": {"type": "integer", "minimum": 0}, "escalate_count": {"type": "integer", "minimum": 0}, "reopen_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "state": {"enum": list(ReviewQueueState)}, "items": {"type": "array"}, "entries": {"type": "array"}, "replay": {"type": "object"}, "content_address": {"type": "string"}}}


def decision_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "FederationReviewDecision", "type": "object", "additionalProperties": False, "required": ["ordinal", "decision_id", "item_id", "item_address", "action", "rationale", "evidence_address", "previous_address", "content_address"], "properties": {"ordinal": {"type": "integer"}, "decision_id": {"type": "string"}, "item_id": {"type": "string"}, "item_address": {"type": "string"}, "action": {"enum": list(ReviewAction)}, "rationale": {"type": "string"}, "evidence_address": {"type": "string"}, "previous_address": {"type": "string"}, "content_address": {"type": "string"}}}


def replay_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "FederationReviewReplay", "type": "object", "additionalProperties": False, "required": ["queue_address", "gate_address", "source_accepted", "source_release_ready", "entry_count", "item_count", "clear_count", "open_count", "blocked_count", "acknowledged_count", "resolved_count", "waived_count", "escalated_count", "state", "accepted", "release_ready", "items", "content_address"], "properties": {"queue_address": {"type": "string"}, "gate_address": {"type": "string"}, "source_accepted": {"type": "boolean"}, "source_release_ready": {"type": "boolean"}, "entry_count": {"type": "integer"}, "item_count": {"type": "integer"}, "clear_count": {"type": "integer"}, "open_count": {"type": "integer"}, "blocked_count": {"type": "integer"}, "acknowledged_count": {"type": "integer"}, "resolved_count": {"type": "integer"}, "waived_count": {"type": "integer"}, "escalated_count": {"type": "integer"}, "state": {"enum": list(ReviewQueueState)}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "items": {"type": "array"}, "content_address": {"type": "string"}}}


def decision_query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "FederationDecisionQuery", "type": "object", "additionalProperties": False, "required": ["resource", "item_id", "action", "state", "text", "offset", "limit"], "properties": {"resource": {"enum": list(DecisionQuery.RESOURCES)}, "item_id": {"type": ["string", "null"]}, "action": {"type": ["string", "null"]}, "state": {"type": ["string", "null"]}, "text": {"type": ["string", "null"]}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}}}


def diff_capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "actions": list(DiffAction), "directions": list(DiffDirection), "decision_actions": list(ReviewAction), "packages": {"queue_files": list(QUEUE_FILES), "ledger_files": list(LEDGER_FILES), "diff_files": list(DIFF_FILES), "atomic_write": True, "canonical_json": True, "exact_file_set": True}, "ledger": {"max_decisions": MAX_DECISIONS, "evidence_required_for": [ReviewAction.REMEDIATE.value, ReviewAction.WAIVE.value], "blocker_waiver": False, "source_gate_authoritative": True}, "queries": {"queue_resources": list(ReviewQuery.RESOURCES), "decision_resources": list(DecisionQuery.RESOURCES), "max_limit": MAX_QUERY_ITEMS}, "public_boundary": {"source_paths": False, "private_metadata": False, "identity_free": True}}


__all__ = [name for name in globals() if not name.startswith("_")]
