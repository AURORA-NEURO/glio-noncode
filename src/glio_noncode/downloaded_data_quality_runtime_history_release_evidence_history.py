"""Append-only history of downloaded-data quality release evidence packages."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import downloaded_data_quality_runtime_history_release_evidence as evidence_model
from ._safe_persistence import _validate_parent, read_text
from .errors import ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash


VERSION = evidence_model.VERSION + "-history-v1"
BOUNDARY = evidence_model.BOUNDARY + "_history"
HISTORY_PREFIX = evidence_model.EVIDENCE_PREFIX + "-history"
ENTRY_PREFIX = HISTORY_PREFIX + "-entry"
ENTRIES_PREFIX = HISTORY_PREFIX + "-entries"
MANIFEST_PREFIX = HISTORY_PREFIX + "-manifest"
SUMMARY_PREFIX = HISTORY_PREFIX + "-summary"
DEFAULT_HISTORY_ID = HISTORY_PREFIX
FILES = ("manifest.json", "history.json", "entries.json", "summary.json")
ARTIFACT_FILES = ("entries.json", "summary.json")
MANIFEST_ARTIFACT_FILES = ARTIFACT_FILES
TRANSITIONS = ("initial", "improved", "regressed", "unchanged", "changed")
STATES = evidence_model.STATES
MAX_ENTRIES = 64
MAX_HISTORY_BYTES = 64 * 1024 * 1024
ENTRY_FIELDS = (
    "ordinal",
    "snapshot_id",
    "evidence_id",
    "evidence_address",
    "gate_id",
    "source_history_id",
    "state",
    "evidence_ready",
    "transition",
    "previous_address",
    "check_count",
    "passed_count",
    "row_count",
    "total_row_count",
    "content_address",
)
ENTRIES_FIELDS = ("entries", "content_address")
MANIFEST_FIELDS = ("history_id", "gate_id", "source_history_id", "version", "boundary", "files", "artifact_addresses", "content_address")
SUMMARY_FIELDS = (
    "history_id",
    "gate_id",
    "source_history_id",
    "entry_count",
    "initial_count",
    "improved_count",
    "regressed_count",
    "unchanged_count",
    "changed_count",
    "latest_state",
    "latest_ready",
    "accepted",
    "content_address",
)
HISTORY_FIELDS = (
    "history_id",
    "gate_id",
    "source_history_id",
    "version",
    "boundary",
    "entries",
    "entry_count",
    "initial_count",
    "improved_count",
    "regressed_count",
    "unchanged_count",
    "changed_count",
    "latest_state",
    "latest_ready",
    "accepted",
    "manifest",
    "summary",
    "content_address",
)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 512, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = True) -> str:
    value = _text(value, field, 4096, required=required)
    if not value:
        return value
    if value.startswith("pending:") or value.endswith(":pending"):
        return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int, *, lower: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < lower or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    return evidence_model.gate_model.history_model._public(value)


def _address_for(value: Any, prefix: str) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)


def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value)
    value._validate()
    return value


class EvidenceHistoryEntry:
    """One immutable release-evidence snapshot and its transition classification."""

    FIELDS = ENTRY_FIELDS

    def __init__(self, ordinal: int, snapshot_id: str, evidence_id: str, evidence_address: str, gate_id: str, source_history_id: str, state: str, evidence_ready: bool, transition: str, previous_address: str, check_count: int, passed_count: int, row_count: int, total_row_count: int, content_address: str) -> None:
        self.ordinal = _count(ordinal, "evidence history entry ordinal", MAX_ENTRIES, lower=1)
        self.snapshot_id = _label(snapshot_id, "evidence history snapshot ID")
        self.evidence_id = _label(evidence_id, "evidence history evidence ID")
        self.evidence_address = _address(evidence_address, "evidence history evidence address", evidence_model.EVIDENCE_PREFIX)
        self.gate_id = _label(gate_id, "evidence history gate ID")
        self.source_history_id = _label(source_history_id, "evidence history source history ID")
        if state not in STATES:
            raise ValidationError("evidence history entry state is unsupported")
        self.state = state
        self.evidence_ready = _bool(evidence_ready, "evidence history entry readiness")
        if transition not in TRANSITIONS:
            raise ValidationError("evidence history transition is unsupported")
        self.transition = transition
        self.previous_address = _address(previous_address, "evidence history previous address", ENTRY_PREFIX, required=False)
        self.check_count = _count(check_count, "evidence history check count", evidence_model.gate_model.MAX_CHECKS)
        self.passed_count = _count(passed_count, "evidence history passed count", evidence_model.gate_model.MAX_CHECKS)
        self.row_count = _count(row_count, "evidence history row count", evidence_model.query_model.MAX_ROWS)
        self.total_row_count = _count(total_row_count, "evidence history total row count", evidence_model.query_model.MAX_ROWS)
        self.content_address = _address(content_address, "evidence history entry address", ENTRY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.passed_count > self.check_count or self.row_count > self.total_row_count:
            raise ValidationError("evidence history entry counters are inconsistent")
        if self.transition == "initial" and self.previous_address:
            raise ValidationError("initial evidence history entry cannot have a predecessor")
        if self.transition != "initial" and not self.previous_address:
            raise ValidationError("non-initial evidence history entry requires a predecessor")
        if not self.content_address.startswith("pending:") and _address_for(self, ENTRY_PREFIX) != self.content_address:
            raise ValidationError("evidence history entry address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("evidence history entry crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "EvidenceHistoryEntry":
        value = _mapping(value, "evidence history entry")
        _strict(value, set(cls.FIELDS), "evidence history entry")
        return cls(*(value[field] for field in cls.FIELDS))


def address_entry(value: EvidenceHistoryEntry) -> str:
    if not isinstance(value, EvidenceHistoryEntry):
        raise ValidationError("evidence history entry address requires a typed entry")
    return _address_for(value, ENTRY_PREFIX)


def address_entries(value: Sequence[EvidenceHistoryEntry]) -> str:
    entries = tuple(value)
    if any(not isinstance(item, EvidenceHistoryEntry) for item in entries):
        raise ValidationError("evidence history entries address requires typed entries")
    return content_hash({"entries": [item.to_dict() for item in entries]}, prefix=ENTRIES_PREFIX)


class EvidenceHistoryManifest:
    FIELDS = MANIFEST_FIELDS

    def __init__(self, history_id: str, gate_id: str, source_history_id: str, version: str, boundary: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.history_id = _label(history_id, "evidence history manifest ID")
        self.gate_id = _label(gate_id, "evidence history manifest gate ID")
        self.source_history_id = _label(source_history_id, "evidence history manifest source history ID")
        self.version = _text(version, "evidence history manifest version", 1024)
        self.boundary = _text(boundary, "evidence history manifest boundary", 2048)
        self.files = tuple(_text(item, "evidence history manifest file", 128) for item in _sequence(files, "evidence history manifest files", len(FILES)))
        self.artifact_addresses = tuple(_address(item, "evidence history manifest artifact address") for item in _sequence(artifact_addresses, "evidence history manifest artifact addresses", len(ARTIFACT_FILES)))
        self.content_address = _address(content_address, "evidence history manifest address", MANIFEST_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.files != FILES or len(self.artifact_addresses) != len(ARTIFACT_FILES):
            raise ValidationError("evidence history manifest is not canonical")
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("evidence history manifest version or boundary is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, MANIFEST_PREFIX) != self.content_address:
            raise ValidationError("evidence history manifest address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("evidence history manifest crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "EvidenceHistoryManifest":
        value = _mapping(value, "evidence history manifest")
        _strict(value, set(cls.FIELDS), "evidence history manifest")
        return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: EvidenceHistoryManifest) -> str:
    if not isinstance(value, EvidenceHistoryManifest):
        raise ValidationError("evidence history manifest address requires a typed manifest")
    return _address_for(value, MANIFEST_PREFIX)


class EvidenceHistorySummary:
    FIELDS = SUMMARY_FIELDS

    def __init__(self, history_id: str, gate_id: str, source_history_id: str, entry_count: int, initial_count: int, improved_count: int, regressed_count: int, unchanged_count: int, changed_count: int, latest_state: str, latest_ready: bool, accepted: bool, content_address: str) -> None:
        self.history_id = _label(history_id, "evidence history summary ID")
        self.gate_id = _label(gate_id, "evidence history summary gate ID")
        self.source_history_id = _label(source_history_id, "evidence history summary source history ID")
        self.entry_count = _count(entry_count, "evidence history entry count", MAX_ENTRIES)
        self.initial_count = _count(initial_count, "evidence history initial count", MAX_ENTRIES)
        self.improved_count = _count(improved_count, "evidence history improved count", MAX_ENTRIES)
        self.regressed_count = _count(regressed_count, "evidence history regressed count", MAX_ENTRIES)
        self.unchanged_count = _count(unchanged_count, "evidence history unchanged count", MAX_ENTRIES)
        self.changed_count = _count(changed_count, "evidence history changed count", MAX_ENTRIES)
        if latest_state not in STATES:
            raise ValidationError("evidence history latest state is unsupported")
        self.latest_state = latest_state
        self.latest_ready = _bool(latest_ready, "evidence history latest readiness")
        self.accepted = _bool(accepted, "evidence history acceptance")
        self.content_address = _address(content_address, "evidence history summary address", SUMMARY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if sum((self.initial_count, self.improved_count, self.regressed_count, self.unchanged_count, self.changed_count)) != self.entry_count:
            raise ValidationError("evidence history summary transitions do not conserve entries")
        if not self.content_address.startswith("pending:") and _address_for(self, SUMMARY_PREFIX) != self.content_address:
            raise ValidationError("evidence history summary address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("evidence history summary crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "EvidenceHistorySummary":
        value = _mapping(value, "evidence history summary")
        _strict(value, set(cls.FIELDS), "evidence history summary")
        return cls(*(value[field] for field in cls.FIELDS))


def address_summary(value: EvidenceHistorySummary) -> str:
    if not isinstance(value, EvidenceHistorySummary):
        raise ValidationError("evidence history summary address requires a typed summary")
    return _address_for(value, SUMMARY_PREFIX)


class EvidenceHistory:
    """Content-addressed append-only release-evidence history."""

    FIELDS = HISTORY_FIELDS

    def __init__(self, history_id: str, gate_id: str, source_history_id: str, version: str, boundary: str, entries: Sequence[EvidenceHistoryEntry | Mapping[str, Any]], entry_count: int, initial_count: int, improved_count: int, regressed_count: int, unchanged_count: int, changed_count: int, latest_state: str, latest_ready: bool, accepted: bool, manifest: Mapping[str, Any] | EvidenceHistoryManifest, summary: Mapping[str, Any] | EvidenceHistorySummary, content_address: str) -> None:
        self.history_id = _label(history_id, "evidence history ID")
        self.gate_id = _label(gate_id, "evidence history gate ID")
        self.source_history_id = _label(source_history_id, "evidence history source history ID")
        self.version = _text(version, "evidence history version", 1024)
        self.boundary = _text(boundary, "evidence history boundary", 2048)
        self.entries = tuple(item if isinstance(item, EvidenceHistoryEntry) else EvidenceHistoryEntry.from_mapping(_mapping(item, "evidence history entry")) for item in _sequence(entries, "evidence history entries", MAX_ENTRIES))
        self.entry_count = _count(entry_count, "evidence history entry count", MAX_ENTRIES)
        self.initial_count = _count(initial_count, "evidence history initial count", MAX_ENTRIES)
        self.improved_count = _count(improved_count, "evidence history improved count", MAX_ENTRIES)
        self.regressed_count = _count(regressed_count, "evidence history regressed count", MAX_ENTRIES)
        self.unchanged_count = _count(unchanged_count, "evidence history unchanged count", MAX_ENTRIES)
        self.changed_count = _count(changed_count, "evidence history changed count", MAX_ENTRIES)
        if latest_state not in STATES:
            raise ValidationError("evidence history latest state is unsupported")
        self.latest_state = latest_state
        self.latest_ready = _bool(latest_ready, "evidence history latest readiness")
        self.accepted = _bool(accepted, "evidence history acceptance")
        self.manifest = manifest if isinstance(manifest, EvidenceHistoryManifest) else EvidenceHistoryManifest.from_mapping(_mapping(manifest, "evidence history manifest"))
        self.summary = summary if isinstance(summary, EvidenceHistorySummary) else EvidenceHistorySummary.from_mapping(_mapping(summary, "evidence history summary"))
        self.content_address = _address(content_address, "evidence history address", HISTORY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("evidence history version or boundary is unsupported")
        if self.entry_count != len(self.entries) or self.entry_count < 1:
            raise ValidationError("evidence history must contain its declared entries")
        if tuple(item.ordinal for item in self.entries) != tuple(range(1, self.entry_count + 1)):
            raise ValidationError("evidence history ordinals do not replay")
        if len({item.snapshot_id for item in self.entries}) != self.entry_count or len({item.evidence_address for item in self.entries}) != self.entry_count:
            raise ValidationError("evidence history contains duplicate snapshots")
        if any(item.gate_id != self.gate_id or item.source_history_id != self.source_history_id for item in self.entries):
            raise ValidationError("evidence history identity does not replay")
        if any(item.content_address != address_entry(item) for item in self.entries):
            raise ValidationError("evidence history entry address does not replay")
        counts = tuple(sum(item.transition == transition for item in self.entries) for transition in TRANSITIONS)
        if counts != (self.initial_count, self.improved_count, self.regressed_count, self.unchanged_count, self.changed_count):
            raise ValidationError("evidence history transition counters do not replay")
        latest = self.entries[-1]
        if (self.latest_state, self.latest_ready) != (latest.state, latest.evidence_ready):
            raise ValidationError("evidence history latest projection does not replay")
        expected_summary = (self.history_id, self.gate_id, self.source_history_id, self.entry_count, self.initial_count, self.improved_count, self.regressed_count, self.unchanged_count, self.changed_count, self.latest_state, self.latest_ready, self.accepted)
        actual_summary = tuple(getattr(self.summary, field) for field in SUMMARY_FIELDS[:-1])
        if actual_summary != expected_summary or self.summary.content_address != address_summary(self.summary):
            raise ValidationError("evidence history summary does not replay")
        expected_manifest = (self.history_id, self.gate_id, self.source_history_id, VERSION, BOUNDARY, FILES, (address_entries(self.entries), self.summary.content_address))
        actual_manifest = (self.manifest.history_id, self.manifest.gate_id, self.manifest.source_history_id, self.manifest.version, self.manifest.boundary, self.manifest.files, self.manifest.artifact_addresses)
        if actual_manifest != expected_manifest or self.manifest.content_address != address_manifest(self.manifest):
            raise ValidationError("evidence history manifest does not replay")
        if not self.accepted:
            raise ValidationError("valid evidence history must be accepted")
        if not self.content_address.startswith("pending:") and _address_for(self, HISTORY_PREFIX) != self.content_address:
            raise ValidationError("evidence history address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("evidence history crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "history_id": self.history_id,
            "gate_id": self.gate_id,
            "source_history_id": self.source_history_id,
            "version": self.version,
            "boundary": self.boundary,
            "entries": [item.to_dict() for item in self.entries],
            "entry_count": self.entry_count,
            "initial_count": self.initial_count,
            "improved_count": self.improved_count,
            "regressed_count": self.regressed_count,
            "unchanged_count": self.unchanged_count,
            "changed_count": self.changed_count,
            "latest_state": self.latest_state,
            "latest_ready": self.latest_ready,
            "accepted": self.accepted,
            "manifest": self.manifest.to_dict(),
            "summary": self.summary.to_dict(),
            "content_address": self.content_address,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "EvidenceHistory":
        value = _mapping(value, "evidence history")
        _strict(value, set(cls.FIELDS), "evidence history")
        return cls(*(value[field] for field in cls.FIELDS))


def address_history(value: EvidenceHistory) -> str:
    if not isinstance(value, EvidenceHistory):
        raise ValidationError("evidence history address requires a typed history")
    return _address_for(value, HISTORY_PREFIX)


def _fingerprint(value: evidence_model.ReleaseEvidence | EvidenceHistoryEntry) -> tuple[Any, ...]:
    if isinstance(value, evidence_model.ReleaseEvidence):
        return (value.gate_id, value.history_id, value.summary.gate_state, value.summary.evidence_ready, value.summary.check_count, value.summary.passed_count, value.summary.row_count, value.summary.total_row_count)
    return (value.gate_id, value.source_history_id, value.state, value.evidence_ready, value.check_count, value.passed_count, value.row_count, value.total_row_count)


def _transition(previous: EvidenceHistoryEntry | None, evidence: evidence_model.ReleaseEvidence) -> str:
    if previous is None:
        return "initial"
    if previous.evidence_ready is False and evidence.summary.evidence_ready is True:
        return "improved"
    if previous.evidence_ready is True and evidence.summary.evidence_ready is False:
        return "regressed"
    return "unchanged" if _fingerprint(previous) == _fingerprint(evidence) else "changed"


def _entry_for(evidence: evidence_model.ReleaseEvidence, ordinal: int, snapshot_id: str, previous: EvidenceHistoryEntry | None) -> EvidenceHistoryEntry:
    transition = _transition(previous, evidence)
    return _seal(EvidenceHistoryEntry(ordinal, snapshot_id, evidence.evidence_id, evidence.content_address, evidence.gate_id, evidence.history_id, evidence.summary.gate_state, evidence.summary.evidence_ready, transition, "" if previous is None else previous.content_address, evidence.summary.check_count, evidence.summary.passed_count, evidence.summary.row_count, evidence.summary.total_row_count, f"pending:{ENTRY_PREFIX}"), address_entry)


def _assemble(history_id: str, entries: Sequence[EvidenceHistoryEntry]) -> EvidenceHistory:
    entries = tuple(entries)
    if not entries:
        raise ValidationError("evidence history requires at least one entry")
    gate_id = entries[0].gate_id
    source_history_id = entries[0].source_history_id
    summary = _seal(EvidenceHistorySummary(history_id, gate_id, source_history_id, len(entries), *(sum(item.transition == transition for item in entries) for transition in TRANSITIONS), entries[-1].state, entries[-1].evidence_ready, True, f"pending:{SUMMARY_PREFIX}"), address_summary)
    manifest = _seal(EvidenceHistoryManifest(history_id, gate_id, source_history_id, VERSION, BOUNDARY, FILES, (address_entries(entries), summary.content_address), f"pending:{MANIFEST_PREFIX}"), address_manifest)
    return _seal(EvidenceHistory(history_id, gate_id, source_history_id, VERSION, BOUNDARY, entries, len(entries), *(sum(item.transition == transition for item in entries) for transition in TRANSITIONS), entries[-1].state, entries[-1].evidence_ready, True, manifest, summary, f"pending:{HISTORY_PREFIX}"), address_history)


def build_history(evidence: evidence_model.ReleaseEvidence, *, history_id: str = DEFAULT_HISTORY_ID, snapshot_id: str = "initial") -> EvidenceHistory:
    evidence_model.verify_evidence(evidence)
    history_id = _label(history_id, "evidence history ID")
    snapshot_id = _label(snapshot_id, "evidence history snapshot ID")
    return _assemble(history_id, (_entry_for(evidence, 1, snapshot_id, None),))


def append_history(history: EvidenceHistory, evidence: evidence_model.ReleaseEvidence, *, snapshot_id: str | None = None, expected_head: str | None = None) -> EvidenceHistory:
    if not isinstance(history, EvidenceHistory):
        raise ValidationError("evidence history append requires a typed history")
    evidence_model.verify_evidence(evidence)
    history._validate()
    if evidence.gate_id != history.gate_id or evidence.history_id != history.source_history_id:
        raise ValidationError("evidence history identity does not match appended evidence")
    if expected_head is not None and expected_head != history.entries[-1].content_address:
        raise ValidationError("evidence history append head is stale")
    if evidence.content_address in {item.evidence_address for item in history.entries}:
        raise ValidationError("evidence history rejects duplicate evidence address")
    snapshot_id = snapshot_id or f"snapshot-{history.entry_count + 1}"
    snapshot_id = _label(snapshot_id, "evidence history snapshot ID")
    if snapshot_id in {item.snapshot_id for item in history.entries}:
        raise ValidationError("evidence history rejects duplicate snapshot ID")
    if history.entry_count >= MAX_ENTRIES:
        raise ValidationError("evidence history reached its entry bound")
    return _assemble(history.history_id, history.entries + (_entry_for(evidence, history.entry_count + 1, snapshot_id, history.entries[-1]),))


def verify_history(value: EvidenceHistory) -> EvidenceHistory:
    if not isinstance(value, EvidenceHistory):
        raise ValidationError("evidence history verification requires a typed history")
    value._validate()
    return value


def history_from_mapping(value: Mapping[str, Any]) -> EvidenceHistory:
    return EvidenceHistory.from_mapping(value)


def history_json(value: EvidenceHistory) -> str:
    return canonical_json(verify_history(value).to_dict())


def entries_json(value: EvidenceHistory | Sequence[EvidenceHistoryEntry]) -> str:
    entries = value.entries if isinstance(value, EvidenceHistory) else tuple(value)
    return canonical_json({"entries": [item.to_dict() for item in entries], "content_address": address_entries(entries)})


def manifest_json(value: EvidenceHistory) -> str:
    return canonical_json(verify_history(value).manifest.to_dict())


def summary_json(value: EvidenceHistory) -> str:
    return canonical_json(verify_history(value).summary.to_dict())


def history_csv(value: EvidenceHistory) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=ENTRY_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(item.to_dict() for item in verify_history(value).entries)
    return output.getvalue()


def render_history_markdown(value: EvidenceHistory) -> str:
    value = verify_history(value)
    lines = [f"# Downloaded-data quality release-evidence history {value.history_id}", "", f"- Latest state: {value.latest_state}", f"- Latest ready: {str(value.latest_ready).lower()}", f"- Entries: {value.entry_count}", f"- Transitions: initial={value.initial_count}, improved={value.improved_count}, regressed={value.regressed_count}, unchanged={value.unchanged_count}, changed={value.changed_count}", "", "| Ordinal | Snapshot | Transition | State | Ready |", "| --- | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | {item.snapshot_id} | {item.transition} | {item.state} | {str(item.evidence_ready).lower()} |" for item in value.entries)
    return "\n".join(lines) + "\n"


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def persist_history(value: EvidenceHistory, destination: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_history(value)
    destination = Path(destination)
    _validate_parent(destination.parent, "evidence history destination")
    if destination.is_symlink() or (destination.exists() and (not destination.is_dir() or not overwrite)):
        raise ValidationError("evidence history destination exists or is not a directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".downloaded-data-quality-release-evidence-history-", dir=str(destination.parent)))
    documents = {"manifest.json": value.manifest.to_dict(), "history.json": value.to_dict(), "entries.json": {"entries": [item.to_dict() for item in value.entries], "content_address": address_entries(value.entries)}, "summary.json": value.summary.to_dict()}
    try:
        for name in FILES:
            _write(temporary / name, documents[name])
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ValidationError("evidence history destination could not be written") from error
    return destination


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        value = _strict_json_loads(read_text(path, field="evidence history artifact"))
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise ValidationError("evidence history artifact is not valid JSON") from error
    return _mapping(value, "evidence history artifact")


def load_history(destination: str | Path) -> EvidenceHistory:
    destination = Path(destination)
    _validate_parent(destination.parent, "evidence history input")
    if not destination.is_dir() or destination.is_symlink():
        raise ValidationError("evidence history source must be a regular directory")
    children = tuple(destination.iterdir())
    if tuple(sorted(item.name for item in children)) != tuple(sorted(FILES)) or any(item.is_symlink() or not item.is_file() for item in children):
        raise ValidationError("evidence history directory must contain the exact regular file set")
    documents = {name: _read_json(destination / name) for name in FILES}
    for name, document in documents.items():
        serialized = canonical_json(document)
        if read_text(destination / name, field="evidence history artifact") != serialized:
            raise ValidationError("evidence history artifact is not canonical")
        if len(serialized.encode("utf-8")) > MAX_HISTORY_BYTES:
            raise ValidationError("evidence history artifact exceeds its size bound")
    value = history_from_mapping(documents["history.json"])
    checks = {"manifest.json": value.manifest.to_dict(), "entries.json": {"entries": [item.to_dict() for item in value.entries], "content_address": address_entries(value.entries)}, "summary.json": value.summary.to_dict()}
    if any(canonical_json(documents[name]) != canonical_json(expected) for name, expected in checks.items()):
        raise ValidationError("evidence history component documents do not replay history.json")
    return value


def run_history(evidence: evidence_model.ReleaseEvidence, *, history_id: str = DEFAULT_HISTORY_ID, snapshot_id: str = "initial", destination: str | Path | None = None, overwrite: bool = False) -> EvidenceHistory:
    value = build_history(evidence, history_id=history_id, snapshot_id=snapshot_id)
    if destination is not None:
        persist_history(value, destination, overwrite=overwrite)
    return value


def entry_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "EvidenceHistoryEntry", "type": "object", "additionalProperties": False, "required": list(ENTRY_FIELDS), "properties": {field: {"type": "integer" if field in ("ordinal", "check_count", "passed_count", "row_count", "total_row_count") else "boolean" if field == "evidence_ready" else "string"} for field in ENTRY_FIELDS}}


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "EvidenceHistoryManifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {field: {"type": "array" if field in ("files", "artifact_addresses") else "string"} for field in MANIFEST_FIELDS}}


def summary_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "EvidenceHistorySummary", "type": "object", "additionalProperties": False, "required": list(SUMMARY_FIELDS), "properties": {field: {"type": "integer" if field.endswith("count") else "boolean" if field in ("latest_ready", "accepted") else "string"} for field in SUMMARY_FIELDS}}


def history_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "EvidenceHistory", "type": "object", "additionalProperties": False, "required": list(HISTORY_FIELDS), "properties": {field: {"type": "array" if field == "entries" else "integer" if field.endswith("count") else "boolean" if field in ("latest_ready", "accepted") else "object" if field in ("manifest", "summary") else "string"} for field in HISTORY_FIELDS}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "files": FILES, "transitions": TRANSITIONS, "states": STATES, "max_entries": MAX_ENTRIES, "features": ("append-only evidence snapshots", "optimistic head checking", "duplicate address and snapshot rejection", "initial improved regressed unchanged and changed transitions", "exact four-file persistence", "canonical reload and tamper rejection", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "HISTORY_PREFIX", "ENTRY_PREFIX", "ENTRIES_PREFIX", "MANIFEST_PREFIX", "SUMMARY_PREFIX", "DEFAULT_HISTORY_ID", "FILES", "ARTIFACT_FILES", "MANIFEST_ARTIFACT_FILES", "TRANSITIONS", "STATES", "MAX_ENTRIES", "MAX_HISTORY_BYTES", "ENTRY_FIELDS", "ENTRIES_FIELDS", "MANIFEST_FIELDS", "SUMMARY_FIELDS", "HISTORY_FIELDS", "EvidenceHistoryEntry", "EvidenceHistoryManifest", "EvidenceHistorySummary", "EvidenceHistory", "address_entry", "address_entries", "address_manifest", "address_summary", "address_history", "build_history", "append_history", "verify_history", "history_from_mapping", "history_json", "entries_json", "manifest_json", "summary_json", "history_csv", "render_history_markdown", "persist_history", "load_history", "run_history", "entry_schema", "manifest_schema", "summary_schema", "history_schema", "capabilities"]
