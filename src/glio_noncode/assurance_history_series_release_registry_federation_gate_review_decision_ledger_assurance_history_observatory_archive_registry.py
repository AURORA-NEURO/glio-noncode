"""Deterministic registry for independently verified observatory archives.

An observatory archive represents one cross-run review view. This module adds a
public, path-free registry for coordinating several such archives without
merging their source records or inventing a new evidence source. Registry
entries retain each archive address and a bounded observatory posture summary.
Aggregate state, counters, verification, persistence, queries, and reports are
all recomputed from those entries.

The registry is intentionally strict. It accepts only archive envelopes that
have already passed the archive loader, rejects duplicate archive identities,
persists an exact five-file package, and never stores the input path. A mapped
public registry is useful for inspection but cannot be treated as a
byte-backed archive source unless it is loaded from the exact registry package.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

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

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory as observatory_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive as archive_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes


VERSION = archive_model.VERSION + "-registry-v1"
BOUNDARY = archive_model.BOUNDARY + "_registry"
REGISTRY_PREFIX = archive_model.ARCHIVE_PREFIX + "-registry"
REGISTRY_QUERY_PREFIX = REGISTRY_PREFIX + "-query"
REGISTRY_ENTRY_PREFIX = REGISTRY_PREFIX + "-entry"
REGISTRY_CHECK_PREFIX = REGISTRY_PREFIX + "-check"
REGISTRY_VERIFICATION_PREFIX = REGISTRY_PREFIX + "-verification"
REGISTRY_MANIFEST_PREFIX = REGISTRY_PREFIX + "-manifest"
MANIFEST_NAME = "manifest.json"
REGISTRY_NAME = "registry.json"
ENTRIES_NAME = "entries.json"
VERIFICATION_NAME = "verification.json"
METRICS_NAME = "metrics.json"
FILES = (MANIFEST_NAME, REGISTRY_NAME, ENTRIES_NAME, VERIFICATION_NAME, METRICS_NAME)
DEFAULT_REGISTRY_ID = "glio-noncode-assurance-history-observatory-archive-registry"
DEFAULT_LIMIT = 50
MAX_ENTRIES = 128
MAX_QUERY_ITEMS = min(4096, MAX_ENTRIES * 8)
MAX_ARCHIVE_BYTES = archive_model.MAX_FILES * 32 * 1024 * 1024


class RegistryState(StrEnum):
    EMPTY = "empty"
    READY = "ready"
    HELD = "held"
    BLOCKED = "blocked"
    MIXED = "mixed"


class RegistryVerificationState(StrEnum):
    PROMOTE = "promote"
    HOLD = "hold"
    BLOCK = "block"


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a non-empty string of at most {maximum} characters")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
        raise ValidationError(f"{field} is outside its declared bound")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 2048)
    if ":" not in value or value.startswith(("/", "\\")) or "\\" in value:
        raise ValidationError(f"{field} must be a public content address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be a mapping")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unsupported fields: {sorted(unknown)}")


def _public(value: Any) -> bool:
    return archive_model._public(value)


def _state(value: Any, field: str = "registry state") -> str:
    value = _text(value, field, 32)
    if value not in tuple(item.value for item in RegistryState):
        raise ValidationError(f"{field} is not supported")
    return value


def _verification_state(value: Any) -> str:
    value = _text(value, "verification state", 32)
    if value not in tuple(item.value for item in RegistryVerificationState):
        raise ValidationError("verification state is not supported")
    return value


class RegistryEntry:
    """Public bounded receipt for one verified observatory archive."""

    def __init__(self, entry_id: str, archive_id: str, archive_address: str, observatory_id: str, observatory_address: str, verification_address: str, archive_size: int, state: str, accepted: bool, release_ready: bool, member_count: int, observatory_entry_count: int, finding_count: int, check_count: int, content_address: str) -> None:
        self.entry_id = entry_id
        self.archive_id = archive_id
        self.archive_address = archive_address
        self.observatory_id = observatory_id
        self.observatory_address = observatory_address
        self.verification_address = verification_address
        self.archive_size = archive_size
        self.state = state
        self.accepted = accepted
        self.release_ready = release_ready
        self.member_count = member_count
        self.observatory_entry_count = observatory_entry_count
        self.finding_count = finding_count
        self.check_count = check_count
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.entry_id, "registry entry ID")
        _text(self.archive_id, "registry archive ID")
        _address(self.archive_address, "registry archive address", archive_model.ARCHIVE_PREFIX)
        _text(self.observatory_id, "registry observatory ID")
        _address(self.observatory_address, "registry observatory address")
        _address(self.verification_address, "registry verification address")
        _count(self.archive_size, "registry archive size", MAX_ARCHIVE_BYTES, positive=True)
        _state(self.state, "entry state")
        _bool(self.accepted, "entry accepted")
        _bool(self.release_ready, "entry release-ready")
        _count(self.member_count, "entry member count", observatory_model.MAX_MEMBERS)
        _count(self.observatory_entry_count, "entry observatory entry count", observatory_model.MAX_MEMBERS * observatory_model.history_model.MAX_ENTRIES)
        _count(self.finding_count, "entry finding count", observatory_model.MAX_MEMBERS * observatory_model.history_model.MAX_ENTRIES * observatory_model.history_model.assurance_model.MAX_FINDINGS)
        _count(self.check_count, "entry check count", observatory_model.MAX_MEMBERS * observatory_model.history_model.MAX_ENTRIES * observatory_model.history_model.assurance_model.MAX_CHECKS)
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "registry entry content address")
        else:
            _address(self.content_address, "registry entry content address", REGISTRY_ENTRY_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_entry(self) != self.content_address):
            raise ValidationError("registry entry address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"entry_id": self.entry_id, "archive_id": self.archive_id, "archive_address": self.archive_address, "observatory_id": self.observatory_id, "observatory_address": self.observatory_address, "verification_address": self.verification_address, "archive_size": self.archive_size, "state": self.state, "accepted": self.accepted, "release_ready": self.release_ready, "member_count": self.member_count, "observatory_entry_count": self.observatory_entry_count, "finding_count": self.finding_count, "check_count": self.check_count, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("entry_id", "archive_id", "archive_address", "observatory_id", "archive_size", "state", "accepted", "release_ready", "member_count", "observatory_entry_count", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryEntry":
        value = _mapping(value, "registry entry")
        _strict(value, {"entry_id", "archive_id", "archive_address", "observatory_id", "observatory_address", "verification_address", "archive_size", "state", "accepted", "release_ready", "member_count", "observatory_entry_count", "finding_count", "check_count", "content_address"}, "registry entry")
        result = cls(**value)
        return result


def address_entry(value: RegistryEntry) -> str:
    if not isinstance(value, RegistryEntry):
        raise ValidationError("registry entry address requires a typed entry")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=REGISTRY_ENTRY_PREFIX)


def _entry_from_archive(value: archive_model.ObservatoryArchive, entry_id: str, archive_size: int) -> RegistryEntry:
    if not isinstance(value, archive_model.ObservatoryArchive):
        raise ValidationError("registry entry builder requires a typed archive")
    archive_model.verify_archive(value)
    package = value._package
    if package is None:
        raise ValidationError("registry entry requires a byte-backed archive package")
    observatory = package.observatory
    body = {"entry_id": _text(entry_id, "registry entry ID"), "archive_id": value.archive_id, "archive_address": value.content_address, "observatory_id": value.observatory_id, "observatory_address": value.observatory_address, "verification_address": value.verification_address, "archive_size": _count(archive_size, "registry archive size", MAX_ARCHIVE_BYTES, positive=True), "state": observatory.state, "accepted": observatory.accepted, "release_ready": observatory.release_ready, "member_count": observatory.member_count, "observatory_entry_count": observatory.entry_count, "finding_count": observatory.finding_count, "check_count": observatory.check_count}
    provisional = RegistryEntry(**body, content_address="pending:entry")
    return RegistryEntry(**body, content_address=address_entry(provisional))


def entry_from_archive(value: archive_model.ObservatoryArchive, *, entry_id: str | None = None, archive_size: int | None = None) -> RegistryEntry:
    if not isinstance(value, archive_model.ObservatoryArchive):
        raise ValidationError("registry entry builder requires a typed archive")
    selected_id = value.archive_id if entry_id is None else entry_id
    selected_size = len(archive_model.archive_bytes(value)) if archive_size is None else archive_size
    return _entry_from_archive(value, selected_id, selected_size)


def entry_from_archive_file(source: str | Path, *, entry_id: str | None = None) -> RegistryEntry:
    path = Path(source)
    if path.is_symlink() or not path.is_file():
        raise ValidationError("archive input must be a regular file")
    value = archive_model.load_archive(path)
    return _entry_from_archive(value, value.archive_id if entry_id is None else entry_id, path.stat().st_size)


class RegistryMetrics:
    """Conserved registry rollup derived from entry records."""

    FIELDS = ("entry_count", "archive_bytes", "member_count", "observatory_entry_count", "accepted_count", "release_ready_count", "empty_count", "ready_count", "held_count", "blocked_count", "mixed_count", "finding_count", "check_count")

    def __init__(self, values: Mapping[str, Any]) -> None:
        values = _mapping(values, "registry metrics")
        _strict(values, set(self.FIELDS), "registry metrics")
        for field in self.FIELDS:
            _count(values[field], f"registry metric {field}", MAX_ARCHIVE_BYTES if field == "archive_bytes" else MAX_ENTRIES * observatory_model.MAX_MEMBERS * observatory_model.history_model.MAX_ENTRIES * max(observatory_model.history_model.assurance_model.MAX_FINDINGS, observatory_model.history_model.assurance_model.MAX_CHECKS))
        self._values = {field: values[field] for field in self.FIELDS}
        for field in self.FIELDS:
            setattr(self, field, self._values[field])
        self._validate()

    def _validate(self) -> None:
        if self._values["entry_count"] != sum(self._values[field] for field in ("empty_count", "ready_count", "held_count", "blocked_count", "mixed_count")):
            raise ValidationError("registry state counts are not conserved")
        if self._values["accepted_count"] > self._values["entry_count"] or self._values["release_ready_count"] > self._values["entry_count"]:
            raise ValidationError("registry boolean counts exceed entries")

    def to_dict(self) -> dict[str, Any]:
        return dict(self._values)


def _metrics(entries: Sequence[RegistryEntry]) -> RegistryMetrics:
    values = {field: 0 for field in RegistryMetrics.FIELDS}
    values["entry_count"] = len(entries)
    for entry in entries:
        values["archive_bytes"] += entry.archive_size
        values["member_count"] += entry.member_count
        values["observatory_entry_count"] += entry.observatory_entry_count
        values["accepted_count"] += int(entry.accepted)
        values["release_ready_count"] += int(entry.release_ready)
        values[f"{entry.state}_count"] += 1
        values["finding_count"] += entry.finding_count
        values["check_count"] += entry.check_count
    return RegistryMetrics(values)


def _aggregate_state(entries: Sequence[RegistryEntry]) -> str:
    if not entries:
        return RegistryState.EMPTY.value
    states = {entry.state for entry in entries}
    if RegistryState.BLOCKED.value in states:
        return RegistryState.BLOCKED.value
    if RegistryState.HELD.value in states:
        return RegistryState.HELD.value
    if states == {RegistryState.READY.value} and all(entry.accepted and entry.release_ready for entry in entries):
        return RegistryState.READY.value
    return RegistryState.MIXED.value


class RegistryVerificationCheck:
    """One independently addressed registry check."""

    def __init__(self, check_id: str, passed: bool, detail: str, evidence_address: str) -> None:
        self.check_id = _text(check_id, "registry check ID", 128)
        self.passed = _bool(passed, "registry check passed")
        self.detail = _text(detail, "registry check detail", 1024)
        self.evidence_address = _text(evidence_address, "registry check evidence address", 2048)
        self.content_address = content_hash({"check_id": self.check_id, "passed": self.passed, "detail": self.detail, "evidence_address": self.evidence_address}, prefix=REGISTRY_CHECK_PREFIX)

    def to_dict(self) -> dict[str, Any]:
        return {"check_id": self.check_id, "passed": self.passed, "detail": self.detail, "evidence_address": self.evidence_address, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryVerificationCheck":
        value = _mapping(value, "registry verification check")
        _strict(value, {"check_id", "passed", "detail", "evidence_address", "content_address"}, "registry verification check")
        result = cls(value["check_id"], value["passed"], value["detail"], value["evidence_address"])
        if result.content_address != value["content_address"]:
            raise ValidationError("registry verification check address mismatch")
        return result


class RegistryVerification:
    """Independent eight-check registry verification artifact."""

    CHECK_IDS = ("entry-identities", "entry-addresses", "archive-identities", "state-projection", "readiness-projection", "counter-conservation", "public-boundary", "content-address")

    def __init__(self, verification_id: str, registry_id: str, registry_address: str, state: str, release_ready: bool, checks: Sequence[RegistryVerificationCheck], content_address: str) -> None:
        self.verification_id = verification_id
        self.registry_id = registry_id
        self.registry_address = registry_address
        self.state = state
        self.release_ready = release_ready
        self.checks = tuple(checks)
        self.check_count = len(self.checks)
        self.passed_count = sum(check.passed for check in self.checks)
        self.failed_count = self.check_count - self.passed_count
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.verification_id, "registry verification ID")
        _text(self.registry_id, "registry verification registry ID")
        _address(self.registry_address, "registry verification registry address", REGISTRY_PREFIX)
        _verification_state(self.state)
        _bool(self.release_ready, "registry verification release-ready")
        if tuple(check.check_id for check in self.checks) != self.CHECK_IDS:
            raise ValidationError("registry verification check set is invalid")
        if self.check_count != len(self.CHECK_IDS) or self.failed_count != self.check_count - self.passed_count:
            raise ValidationError("registry verification counts are invalid")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "registry verification content address")
        else:
            _address(self.content_address, "registry verification content address", REGISTRY_VERIFICATION_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_verification(self) != self.content_address):
            raise ValidationError("registry verification address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"verification_id": self.verification_id, "registry_id": self.registry_id, "registry_address": self.registry_address, "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "state": self.state, "release_ready": self.release_ready, "checks": tuple(check.to_dict() for check in self.checks), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("verification_id", "registry_id", "registry_address", "check_count", "passed_count", "failed_count", "state", "release_ready", "content_address")}


def address_verification(value: RegistryVerification) -> str:
    if not isinstance(value, RegistryVerification):
        raise ValidationError("registry verification address requires a typed verification")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=REGISTRY_VERIFICATION_PREFIX)


class ObservatoryArchiveRegistry:
    """Public aggregate of several independently verified archive entries."""

    def __init__(self, registry_id: str, version: str, boundary: str, entry_count: int, state: str, accepted: bool, release_ready: bool, metrics: RegistryMetrics, entries: Sequence[RegistryEntry], verification_address: str, content_address: str, verification: RegistryVerification | None = None, payload: Mapping[str, bytes] | None = None) -> None:
        self.registry_id = registry_id
        self.version = version
        self.boundary = boundary
        self.entry_count = entry_count
        self.state = state
        self.accepted = accepted
        self.release_ready = release_ready
        self.metrics = metrics
        self.entries = tuple(entries)
        self.verification_address = verification_address
        self.content_address = content_address
        self._verification = verification
        self._payload = dict(payload or {})
        self._validate()

    def _validate(self) -> None:
        _text(self.registry_id, "registry ID")
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("registry contract version or boundary is invalid")
        _count(self.entry_count, "registry entry count", MAX_ENTRIES)
        if self.entry_count != len(self.entries):
            raise ValidationError("registry entry count is not conserved")
        _state(self.state)
        _bool(self.accepted, "registry accepted")
        _bool(self.release_ready, "registry release-ready")
        if tuple(entry.entry_id for entry in self.entries) != tuple(sorted(entry.entry_id for entry in self.entries)):
            raise ValidationError("registry entries are not canonically ordered")
        if len({entry.entry_id for entry in self.entries}) != self.entry_count or len({entry.archive_address for entry in self.entries}) != self.entry_count or len({entry.observatory_address for entry in self.entries}) != self.entry_count:
            raise ValidationError("registry entry identities are not unique")
        if self.state != _aggregate_state(self.entries) or self.metrics.to_dict() != _metrics(self.entries).to_dict():
            raise ValidationError("registry aggregate projection is not derived from entries")
        expected_accepted = bool(self.entries) and all(entry.accepted for entry in self.entries)
        expected_ready = bool(self.entries) and self.state == RegistryState.READY.value and all(entry.release_ready for entry in self.entries)
        if self.accepted != expected_accepted or self.release_ready != expected_ready:
            raise ValidationError("registry acceptance or readiness projection is invalid")
        _address(self.verification_address, "registry verification address", REGISTRY_VERIFICATION_PREFIX)
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "registry content address")
        else:
            _address(self.content_address, "registry content address", REGISTRY_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_registry(self) != self.content_address):
            raise ValidationError("registry address or public boundary is invalid")
        if self._verification is not None:
            if self._verification.registry_address != self.content_address or self._verification.registry_id != self.registry_id:
                raise ValidationError("registry verification linkage is invalid")
        if self._payload and set(self._payload) != set(FILES):
            raise ValidationError("registry payload is incomplete")

    def to_dict(self) -> dict[str, Any]:
        return {"registry_id": self.registry_id, "version": self.version, "boundary": self.boundary, "entry_count": self.entry_count, "state": self.state, "accepted": self.accepted, "release_ready": self.release_ready, "metrics": self.metrics.to_dict(), "entries": tuple(entry.to_dict() for entry in self.entries), "verification_address": self.verification_address, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("registry_id", "version", "boundary", "entry_count", "state", "accepted", "release_ready", "verification_address", "content_address")}

    def payload_bytes(self) -> Mapping[str, bytes]:
        if not self._payload:
            raise ValidationError("registry payload bytes are unavailable")
        return dict(self._payload)


def address_registry(value: ObservatoryArchiveRegistry) -> str:
    if not isinstance(value, ObservatoryArchiveRegistry):
        raise ValidationError("registry address requires a typed registry")
    # The verification link is deliberately excluded from the registry identity.
    # Verification points back to this address, so including both fields would
    # create a circular content-address dependency.
    return content_hash(value.to_dict() | {"verification_address": None, "content_address": None}, prefix=REGISTRY_PREFIX)


def _build_verification(value: ObservatoryArchiveRegistry, verification_id: str | None = None) -> RegistryVerification:
    entries = value.entries
    checks = (
        RegistryVerificationCheck("entry-identities", len({entry.entry_id for entry in entries}) == len(entries), "entry IDs are unique and count-conserved", value.content_address),
        RegistryVerificationCheck("entry-addresses", all(address_entry(entry) == entry.content_address for entry in entries), "every entry address reproduces", value.content_address),
        RegistryVerificationCheck("archive-identities", len({entry.archive_address for entry in entries}) == len(entries), "archive addresses are unique", value.content_address),
        RegistryVerificationCheck("state-projection", value.state == _aggregate_state(entries), "registry state is folded from entry states", value.content_address),
        RegistryVerificationCheck("readiness-projection", value.release_ready == (bool(entries) and value.state == RegistryState.READY.value and all(entry.release_ready for entry in entries)), "release readiness is conjunctive across entries", value.content_address),
        RegistryVerificationCheck("counter-conservation", value.metrics.to_dict() == _metrics(entries).to_dict(), "registry metrics equal recomputed entry totals", value.content_address),
        RegistryVerificationCheck("public-boundary", _public(value.to_dict()), "registry projection contains no private or attribution metadata", value.content_address),
        RegistryVerificationCheck("content-address", address_registry(value) == value.content_address, "registry content address reproduces", value.content_address),
    )
    state = RegistryVerificationState.BLOCK.value if value.state == RegistryState.BLOCKED.value else RegistryVerificationState.PROMOTE.value if value.release_ready else RegistryVerificationState.HOLD.value
    body = {"verification_id": DEFAULT_REGISTRY_ID + "-verification" if verification_id is None else _text(verification_id, "registry verification ID"), "registry_id": value.registry_id, "registry_address": value.content_address, "state": state, "release_ready": value.release_ready, "checks": checks}
    provisional = RegistryVerification(**body, content_address="pending:verification")
    return RegistryVerification(**body, content_address=address_verification(provisional))


def build_registry(entries: Sequence[RegistryEntry], *, registry_id: str | None = None, verification_id: str | None = None) -> ObservatoryArchiveRegistry:
    entries = tuple(entries)
    if len(entries) > MAX_ENTRIES:
        raise ValidationError("registry has too many entries")
    if any(not isinstance(entry, RegistryEntry) for entry in entries):
        raise ValidationError("registry builder requires typed entries")
    entries = tuple(sorted(entries, key=lambda entry: entry.entry_id))
    if len({entry.entry_id for entry in entries}) != len(entries) or len({entry.archive_address for entry in entries}) != len(entries):
        raise ValidationError("registry entries contain duplicate identities")
    selected_id = DEFAULT_REGISTRY_ID if registry_id is None else _text(registry_id, "registry ID")
    metrics = _metrics(entries)
    state = _aggregate_state(entries)
    accepted = bool(entries) and all(entry.accepted for entry in entries)
    release_ready = bool(entries) and state == RegistryState.READY.value and all(entry.release_ready for entry in entries)
    verification_address = REGISTRY_VERIFICATION_PREFIX + ":pending"
    body = {"registry_id": selected_id, "version": VERSION, "boundary": BOUNDARY, "entry_count": len(entries), "state": state, "accepted": accepted, "release_ready": release_ready, "metrics": metrics, "entries": entries, "verification_address": verification_address}
    provisional = ObservatoryArchiveRegistry(**body, content_address="pending:registry")
    registry = ObservatoryArchiveRegistry(**(body | {"verification_address": REGISTRY_VERIFICATION_PREFIX + ":placeholder"}), content_address=address_registry(provisional))
    verification = _build_verification(registry, verification_id)
    registry.verification_address = verification.content_address
    registry._verification = verification
    registry.content_address = address_registry(registry)
    registry._validate()
    return registry


def build_registry_from_archives(values: Sequence[archive_model.ObservatoryArchive], *, entry_ids: Sequence[str] | None = None, registry_id: str | None = None, verification_id: str | None = None) -> ObservatoryArchiveRegistry:
    values = tuple(values)
    if entry_ids is not None and len(entry_ids) != len(values):
        raise ValidationError("registry entry IDs must align with archives")
    selected_ids = tuple(entry_ids) if entry_ids is not None else tuple(value.archive_id for value in values)
    entries = tuple(entry_from_archive(value, entry_id=selected_ids[index]) for index, value in enumerate(values))
    return build_registry(entries, registry_id=registry_id, verification_id=verification_id)


def build_registry_from_archive_files(sources: Sequence[str | Path], *, entry_ids: Sequence[str] | None = None, registry_id: str | None = None, verification_id: str | None = None) -> ObservatoryArchiveRegistry:
    sources = tuple(sources)
    if entry_ids is not None and len(entry_ids) != len(sources):
        raise ValidationError("registry entry IDs must align with archive files")
    selected_ids = tuple(entry_ids) if entry_ids is not None else None
    entries = tuple(entry_from_archive_file(source, entry_id=None if selected_ids is None else selected_ids[index]) for index, source in enumerate(sources))
    return build_registry(entries, registry_id=registry_id, verification_id=verification_id)


def registry_from_mapping(value: Mapping[str, Any]) -> ObservatoryArchiveRegistry:
    value = _mapping(value, "observatory archive registry")
    _strict(value, {"registry_id", "version", "boundary", "entry_count", "state", "accepted", "release_ready", "metrics", "entries", "verification_address", "content_address"}, "observatory archive registry")
    entries = tuple(RegistryEntry.from_mapping(item) for item in _sequence(value["entries"], "registry entries", MAX_ENTRIES))
    return ObservatoryArchiveRegistry(value["registry_id"], value["version"], value["boundary"], value["entry_count"], value["state"], value["accepted"], value["release_ready"], RegistryMetrics(value["metrics"]), entries, value["verification_address"], value["content_address"])


def verify_registry(value: ObservatoryArchiveRegistry) -> ObservatoryArchiveRegistry:
    if not isinstance(value, ObservatoryArchiveRegistry):
        raise ValidationError("registry verification requires a typed registry")
    value._validate()
    if value._verification is not None:
        expected = _build_verification(ObservatoryArchiveRegistry(value.registry_id, value.version, value.boundary, value.entry_count, value.state, value.accepted, value.release_ready, value.metrics, value.entries, value.verification_address, value.content_address), value._verification.verification_id)
        if expected.to_dict() != value._verification.to_dict():
            raise ValidationError("registry verification is not reproducible")
    return value


def _artifact(name: str, raw: bytes) -> dict[str, Any]:
    return {"name": name, "size": len(raw), "hash": hash_bytes(raw, prefix=REGISTRY_PREFIX + "-artifact")}


def _registry_payload(value: ObservatoryArchiveRegistry) -> dict[str, bytes]:
    if value._verification is None:
        raise ValidationError("registry verification is unavailable")
    return {REGISTRY_NAME: canonical_bytes(value.to_dict()), ENTRIES_NAME: canonical_bytes({"version": VERSION, "boundary": BOUNDARY, "registry_id": value.registry_id, "entry_count": value.entry_count, "entries": tuple(entry.to_dict() for entry in value.entries)}), VERIFICATION_NAME: canonical_bytes(value._verification.to_dict()), METRICS_NAME: canonical_bytes(value.metrics.to_dict())}


def _manifest(value: ObservatoryArchiveRegistry, payload: Mapping[str, bytes]) -> dict[str, Any]:
    body = {"version": VERSION, "boundary": BOUNDARY, "registry_id": value.registry_id, "registry_address": value.content_address, "verification_address": value.verification_address, "artifact_count": len(payload), "files": tuple(payload), "artifacts": tuple(_artifact(name, payload[name]) for name in payload)}
    body["manifest_address"] = content_hash(body | {"manifest_address": None}, prefix=REGISTRY_MANIFEST_PREFIX)
    return body


def _package_payload(value: ObservatoryArchiveRegistry) -> dict[str, bytes]:
    payload = _registry_payload(value)
    payload[MANIFEST_NAME] = canonical_bytes(_manifest(value, payload))
    return {name: payload[name] for name in FILES}


def registry_bytes(value: ObservatoryArchiveRegistry) -> Mapping[str, bytes]:
    verify_registry(value)
    return dict(_package_payload(value))


def _write_atomic_directory(destination: Path, payload: Mapping[str, bytes], *, overwrite: bool) -> Path:
    if destination.exists():
        if not overwrite:
            raise ValidationError("registry destination exists; explicit overwrite is required")
        if destination.is_symlink() or not destination.is_dir() or {item.name for item in destination.iterdir()} != set(FILES) or any(item.is_symlink() or not item.is_file() for item in destination.iterdir()):
            raise ValidationError("registry destination is not an exact compatible directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".gnd-observatory-registry-", dir=str(destination.parent)))
    try:
        for name in FILES:
            (temporary / name).write_bytes(payload[name])
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def write_registry(value: ObservatoryArchiveRegistry, destination: str | Path, *, overwrite: bool = False) -> Path:
    return _write_atomic_directory(Path(destination), registry_bytes(value), overwrite=overwrite)


def _read_directory(source: str | Path) -> dict[str, bytes]:
    directory = Path(source)
    if directory.is_symlink() or not directory.is_dir():
        raise ValidationError("registry input must be a regular directory")
    if {item.name for item in directory.iterdir()} != set(FILES) or any(item.is_symlink() or not item.is_file() for item in directory.iterdir()):
        raise ValidationError("registry directory member set is invalid")
    return {name: (directory / name).read_bytes() for name in FILES}


def load_registry(source: str | Path) -> ObservatoryArchiveRegistry:
    payload = _read_directory(source)
    try:
        manifest = json.loads(payload[MANIFEST_NAME].decode("utf-8"))
        registry = json.loads(payload[REGISTRY_NAME].decode("utf-8"))
        entries = json.loads(payload[ENTRIES_NAME].decode("utf-8"))
        verification = json.loads(payload[VERIFICATION_NAME].decode("utf-8"))
        metrics = json.loads(payload[METRICS_NAME].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("registry package contains invalid JSON") from error
    decoded = {MANIFEST_NAME: _mapping(manifest, "registry manifest"), REGISTRY_NAME: _mapping(registry, "registry document"), ENTRIES_NAME: _mapping(entries, "registry entries"), VERIFICATION_NAME: _mapping(verification, "registry verification"), METRICS_NAME: _mapping(metrics, "registry metrics")}
    for name, document in decoded.items():
        if canonical_bytes(document) != payload[name]:
            raise ValidationError(f"registry artifact {name} is not canonical JSON")
    _strict(decoded[MANIFEST_NAME], {"version", "boundary", "registry_id", "registry_address", "verification_address", "artifact_count", "files", "artifacts", "manifest_address"}, "registry manifest")
    expected_manifest_address = content_hash(dict(decoded[MANIFEST_NAME]) | {"manifest_address": None}, prefix=REGISTRY_MANIFEST_PREFIX)
    if decoded[MANIFEST_NAME].get("version") != VERSION or decoded[MANIFEST_NAME].get("boundary") != BOUNDARY or decoded[MANIFEST_NAME].get("manifest_address") != expected_manifest_address or decoded[MANIFEST_NAME].get("files") != list(FILES[1:]) or decoded[MANIFEST_NAME].get("artifact_count") != len(FILES) - 1:
        raise ValidationError("registry manifest contract is invalid")
    for name in (REGISTRY_NAME, ENTRIES_NAME, VERIFICATION_NAME, METRICS_NAME):
        receipt = next((item for item in decoded[MANIFEST_NAME]["artifacts"] if item.get("name") == name), None)
        if receipt != _artifact(name, payload[name]):
            raise ValidationError("registry artifact receipt mismatch")
    _strict(decoded[ENTRIES_NAME], {"version", "boundary", "registry_id", "entry_count", "entries"}, "registry entries")
    if decoded[ENTRIES_NAME]["version"] != VERSION or decoded[ENTRIES_NAME]["boundary"] != BOUNDARY or decoded[ENTRIES_NAME]["registry_id"] != decoded[REGISTRY_NAME].get("registry_id") or decoded[ENTRIES_NAME]["entry_count"] != decoded[REGISTRY_NAME].get("entry_count") or decoded[ENTRIES_NAME]["entries"] != decoded[REGISTRY_NAME].get("entries"):
        raise ValidationError("registry entries linkage is invalid")
    value = registry_from_mapping(decoded[REGISTRY_NAME])
    loaded_verification = RegistryVerification(decoded[VERIFICATION_NAME]["verification_id"], decoded[VERIFICATION_NAME]["registry_id"], decoded[VERIFICATION_NAME]["registry_address"], decoded[VERIFICATION_NAME]["state"], decoded[VERIFICATION_NAME]["release_ready"], tuple(RegistryVerificationCheck.from_mapping(item) for item in _sequence(decoded[VERIFICATION_NAME]["checks"], "registry checks", len(RegistryVerification.CHECK_IDS))), decoded[VERIFICATION_NAME]["content_address"])
    if canonical_bytes(loaded_verification.to_dict()) != canonical_bytes(decoded[VERIFICATION_NAME]) or loaded_verification.registry_address != value.content_address or loaded_verification.registry_id != value.registry_id:
        raise ValidationError("registry verification linkage is invalid")
    if decoded[MANIFEST_NAME]["registry_id"] != value.registry_id or decoded[MANIFEST_NAME]["registry_address"] != value.content_address or decoded[MANIFEST_NAME]["verification_address"] != loaded_verification.content_address or decoded[METRICS_NAME] != value.metrics.to_dict():
        raise ValidationError("registry metrics or address linkage is invalid")
    loaded = ObservatoryArchiveRegistry(value.registry_id, value.version, value.boundary, value.entry_count, value.state, value.accepted, value.release_ready, value.metrics, value.entries, value.verification_address, value.content_address, verification=loaded_verification, payload=payload)
    verify_registry(loaded)
    return loaded


def verify_registry_directory(source: str | Path) -> ObservatoryArchiveRegistry:
    return load_registry(source)


def registry_json(value: ObservatoryArchiveRegistry) -> str:
    verify_registry(value)
    return canonical_json(value.to_dict())


def registry_manifest_json(value: ObservatoryArchiveRegistry) -> str:
    verify_registry(value)
    return canonical_json(_manifest(value, _registry_payload(value)))


class RegistryQuery:
    """Bounded query over registry entry posture."""

    RESOURCES = ("summary", "entries", "empty", "ready", "held", "blocked", "mixed", "accepted", "rejected")

    def __init__(self, resource: str = "summary", state: str | None = None, accepted: bool | None = None, release_ready: bool | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> None:
        self.resource = _text(resource, "registry query resource", 64)
        if self.resource not in self.RESOURCES:
            raise ValidationError("registry query resource is not supported")
        self.state = None if state is None else _state(state, "registry query state")
        self.accepted = None if accepted is None else _bool(accepted, "registry query accepted")
        self.release_ready = None if release_ready is None else _bool(release_ready, "registry query release-ready")
        self.text = None if text is None else _text(text, "registry query text", 512)
        self.offset = _count(offset, "registry query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "registry query limit", MAX_QUERY_ITEMS, positive=True)

    def to_dict(self) -> dict[str, Any]:
        return {"resource": self.resource, "state": self.state, "accepted": self.accepted, "release_ready": self.release_ready, "text": self.text, "offset": self.offset, "limit": self.limit}


class RegistryQueryResult:
    def __init__(self, registry_address: str, query: RegistryQuery, total_count: int, records: Sequence[Mapping[str, Any]], content_address: str) -> None:
        self.registry_address = registry_address
        self.query = query
        self.total_count = total_count
        self.returned_count = len(records)
        self.records = tuple(dict(record) for record in records)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.registry_address, "registry query registry address", REGISTRY_PREFIX)
        _count(self.total_count, "registry query total count", MAX_QUERY_ITEMS)
        _count(self.returned_count, "registry query returned count", MAX_QUERY_ITEMS)
        if self.returned_count > self.total_count or self.returned_count > self.query.limit:
            raise ValidationError("registry query result window is invalid")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "registry query content address")
        else:
            _address(self.content_address, "registry query content address", REGISTRY_QUERY_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_query(self) != self.content_address):
            raise ValidationError("registry query address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"registry_address": self.registry_address, "query": self.query.to_dict(), "total_count": self.total_count, "returned_count": self.returned_count, "records": self.records, "content_address": self.content_address}


def address_query(value: RegistryQueryResult) -> str:
    if not isinstance(value, RegistryQueryResult):
        raise ValidationError("registry query address requires a typed result")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=REGISTRY_QUERY_PREFIX)


def _matches(entry: RegistryEntry, query: RegistryQuery) -> bool:
    if query.state is not None and entry.state != query.state:
        return False
    if query.accepted is not None and entry.accepted != query.accepted:
        return False
    if query.release_ready is not None and entry.release_ready != query.release_ready:
        return False
    return query.text is None or query.text.lower() in canonical_json(entry.to_dict()).lower()


def query_registry(value: ObservatoryArchiveRegistry, query: RegistryQuery | None = None, *, resource: str = "summary", state: str | None = None, accepted: bool | None = None, release_ready: bool | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> RegistryQueryResult:
    verify_registry(value)
    if query is not None and any(argument != default for argument, default in ((resource, "summary"), (state, None), (accepted, None), (release_ready, None), (text, None), (offset, 0), (limit, DEFAULT_LIMIT))):
        raise ValidationError("registry query accepts either a query object or keyword filters")
    query = query or RegistryQuery(resource=resource, state=state, accepted=accepted, release_ready=release_ready, text=text, offset=offset, limit=limit)
    if query.resource == "summary":
        records = (value.summary(),)
    else:
        records = tuple(entry.summary() for entry in value.entries)
        if query.resource in tuple(item.value for item in RegistryState):
            records = tuple(record for record in records if record["state"] == query.resource)
        elif query.resource == "accepted":
            records = tuple(record for record in records if record["accepted"])
        elif query.resource == "rejected":
            records = tuple(record for record in records if not record["accepted"])
        if query.state is not None or query.accepted is not None or query.release_ready is not None or query.text is not None:
            entries = tuple(entry for entry in value.entries if _matches(entry, query))
            records = tuple(entry.summary() for entry in entries)
    total_count = len(records)
    window = records[query.offset:query.offset + query.limit]
    provisional = RegistryQueryResult(value.content_address, query, total_count, window, "pending:query")
    return RegistryQueryResult(value.content_address, query, total_count, window, address_query(provisional))


def _csv_text(result: RegistryQueryResult) -> str:
    output = io.StringIO()
    records = list(result.records)
    fieldnames = sorted({str(key) for record in records for key in record}) or ["content_address"]
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for record in records:
        writer.writerow({key: canonical_json(record[key]) if isinstance(record.get(key), (dict, list, tuple)) else record.get(key, "") for key in fieldnames})
    return output.getvalue()


def query_json(value: RegistryQueryResult) -> str:
    if not isinstance(value, RegistryQueryResult):
        raise ValidationError("registry query JSON requires a typed result")
    return canonical_json(value.to_dict())


def query_csv(value: RegistryQueryResult) -> str:
    if not isinstance(value, RegistryQueryResult):
        raise ValidationError("registry query CSV requires a typed result")
    return _csv_text(value)


def render_markdown(value: ObservatoryArchiveRegistry) -> str:
    verify_registry(value)
    return "\n".join(("# Assurance history observatory archive registry", "", f"- Registry: `{value.registry_id}`", f"- Entries: `{value.entry_count}`", f"- State: `{value.state}`", f"- Release ready: `{str(value.release_ready).lower()}`", f"- Content address: `{value.content_address}`", ""))


def render_query_markdown(value: RegistryQueryResult) -> str:
    if not isinstance(value, RegistryQueryResult):
        raise ValidationError("registry query Markdown requires a typed result")
    lines = ["# Assurance history observatory archive registry query", "", f"- Resource: `{value.query.resource}`", f"- Returned: `{value.returned_count}` of `{value.total_count}`", f"- Content address: `{value.content_address}`", ""]
    if value.records:
        keys = sorted({str(key) for record in value.records for key in record})
        lines.extend(("| " + " | ".join(keys) + " |", "| " + " | ".join("---" for _ in keys) + " |"))
        lines.extend("| " + " | ".join(str(record.get(key, "")) for key in keys) + " |" for record in value.records)
    return "\n".join(lines) + "\n"


def entry_schema() -> dict[str, Any]:
    fields = {"entry_id": {"type": "string", "minLength": 1, "maxLength": 512}, "archive_id": {"type": "string"}, "archive_address": {"type": "string"}, "observatory_id": {"type": "string"}, "observatory_address": {"type": "string"}, "verification_address": {"type": "string"}, "archive_size": {"type": "integer", "minimum": 1, "maximum": MAX_ARCHIVE_BYTES}, "state": {"type": "string", "enum": [item.value for item in RegistryState]}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "member_count": {"type": "integer", "minimum": 0, "maximum": observatory_model.MAX_MEMBERS}, "observatory_entry_count": {"type": "integer", "minimum": 0}, "finding_count": {"type": "integer", "minimum": 0}, "check_count": {"type": "integer", "minimum": 0}, "content_address": {"type": "string"}}
    return {"type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def metrics_schema() -> dict[str, Any]:
    fields = {field: {"type": "integer", "minimum": 0} for field in RegistryMetrics.FIELDS}
    return {"type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def verification_check_schema() -> dict[str, Any]:
    fields = {"check_id": {"type": "string"}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_address": {"type": "string"}, "content_address": {"type": "string"}}
    return {"type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def verification_schema() -> dict[str, Any]:
    fields = {"verification_id": {"type": "string"}, "registry_id": {"type": "string"}, "registry_address": {"type": "string"}, "check_count": {"type": "integer", "minimum": len(RegistryVerification.CHECK_IDS), "maximum": len(RegistryVerification.CHECK_IDS)}, "passed_count": {"type": "integer", "minimum": 0, "maximum": len(RegistryVerification.CHECK_IDS)}, "failed_count": {"type": "integer", "minimum": 0, "maximum": len(RegistryVerification.CHECK_IDS)}, "state": {"type": "string", "enum": [item.value for item in RegistryVerificationState]}, "release_ready": {"type": "boolean"}, "checks": {"type": "array", "minItems": len(RegistryVerification.CHECK_IDS), "maxItems": len(RegistryVerification.CHECK_IDS), "items": verification_check_schema()}, "content_address": {"type": "string"}}
    return {"type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def registry_schema() -> dict[str, Any]:
    fields = {"registry_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "entry_count": {"type": "integer", "minimum": 0, "maximum": MAX_ENTRIES}, "state": {"type": "string", "enum": [item.value for item in RegistryState]}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "metrics": metrics_schema(), "entries": {"type": "array", "maxItems": MAX_ENTRIES, "items": entry_schema()}, "verification_address": {"type": "string"}, "content_address": {"type": "string"}}
    return {"type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def query_schema() -> dict[str, Any]:
    fields = {"resource": {"type": "string", "enum": list(RegistryQuery.RESOURCES)}, "state": {"anyOf": [{"type": "string", "enum": [item.value for item in RegistryState]}, {"type": "null"}]}, "accepted": {"anyOf": [{"type": "boolean"}, {"type": "null"}]}, "release_ready": {"anyOf": [{"type": "boolean"}, {"type": "null"}]}, "text": {"anyOf": [{"type": "string", "maxLength": 512}, {"type": "null"}]}, "offset": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_QUERY_ITEMS}}
    return {"type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def query_result_schema() -> dict[str, Any]:
    fields = {"registry_address": {"type": "string"}, "query": query_schema(), "total_count": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "returned_count": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "records": {"type": "array", "maxItems": MAX_QUERY_ITEMS, "items": {"type": "object"}}, "content_address": {"type": "string"}}
    return {"type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "files": FILES, "limits": {"max_entries": MAX_ENTRIES, "max_query_items": MAX_QUERY_ITEMS, "max_archive_bytes_per_entry": MAX_ARCHIVE_BYTES}, "states": tuple(item.value for item in RegistryState), "verification_states": tuple(item.value for item in RegistryVerificationState), "verification_checks": RegistryVerification.CHECK_IDS, "resources": RegistryQuery.RESOURCES, "features": ("verified archive-only inputs", "duplicate identity rejection", "conserved posture and byte metrics", "independent eight-check verification", "exact five-file persistence", "bounded state acceptance and readiness queries", "deterministic JSON CSV and Markdown projections", "path-free public registry output"), "schemas": ("entry", "metrics", "registry", "verification", "verification-check", "query", "query-result")}


__all__ = [
    "BOUNDARY",
    "DEFAULT_LIMIT",
    "DEFAULT_REGISTRY_ID",
    "ENTRIES_NAME",
    "FILES",
    "MANIFEST_NAME",
    "MAX_ARCHIVE_BYTES",
    "MAX_ENTRIES",
    "MAX_QUERY_ITEMS",
    "METRICS_NAME",
    "REGISTRY_CHECK_PREFIX",
    "REGISTRY_ENTRY_PREFIX",
    "REGISTRY_MANIFEST_PREFIX",
    "REGISTRY_PREFIX",
    "REGISTRY_QUERY_PREFIX",
    "REGISTRY_VERIFICATION_PREFIX",
    "REGISTRY_NAME",
    "RegistryEntry",
    "RegistryMetrics",
    "RegistryQuery",
    "RegistryQueryResult",
    "RegistryState",
    "RegistryVerification",
    "RegistryVerificationCheck",
    "RegistryVerificationState",
    "ObservatoryArchiveRegistry",
    "VERSION",
    "address_entry",
    "address_query",
    "address_registry",
    "address_verification",
    "build_registry",
    "build_registry_from_archive_files",
    "build_registry_from_archives",
    "capabilities",
    "entry_from_archive",
    "entry_from_archive_file",
    "entry_schema",
    "load_registry",
    "metrics_schema",
    "query_csv",
    "query_json",
    "query_registry",
    "query_result_schema",
    "query_schema",
    "registry_bytes",
    "registry_from_mapping",
    "registry_json",
    "registry_manifest_json",
    "registry_schema",
    "render_markdown",
    "render_query_markdown",
    "verification_check_schema",
    "verification_schema",
    "verify_registry",
    "verify_registry_directory",
    "write_registry",
]
