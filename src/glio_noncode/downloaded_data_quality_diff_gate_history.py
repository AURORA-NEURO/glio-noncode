"""Append-only history of downloaded-data quality diff gate decisions."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_quality_diff_gate_runtime as runtime_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-quality-diff-gate-history-v1"
BOUNDARY = "public_downloaded_data_quality_diff_gate_history"
HISTORY_PREFIX = "glio-noncode-download-quality-diff-gate-history"
ENTRY_PREFIX = HISTORY_PREFIX + "-entry"
DEFAULT_HISTORY_ID = HISTORY_PREFIX
INITIAL_HEAD = HISTORY_PREFIX + ":initial"
MAX_ENTRIES = 256
STATES = ("empty", "eligible", "review", "blocked")
DECISIONS = ("promote", "hold", "block")
TRANSITIONS = ("initial", "improved", "regressed", "unchanged", "changed")
STATE_SCORE = {"eligible": 3, "review": 2, "blocked": 1}
ENTRY_FIELDS = (
    "ordinal", "snapshot_id", "gate_id", "gate_address", "runtime_address", "decision",
    "state", "accepted", "release_ready", "finding_count", "safe_count", "review_count",
    "blocked_count", "policy_address", "previous_entry_address", "transition", "content_address",
)
HISTORY_FIELDS = (
    "history_id", "version", "boundary", "gate_id", "head_address", "entry_count",
    "promote_count", "hold_count", "block_count", "accepted_count", "release_ready_count",
    "state", "accepted", "release_ready", "entries", "content_address",
)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 256, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 2048)
    if "/" in value or "\\" in value or '"' in value or ":" not in value:
        raise ValidationError(f"{field} must be a content address")
    namespace, digest = value.split(":", 1)
    if not namespace or (digest != "initial" and (len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest))):
        raise ValidationError(f"{field} must be a canonical content address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


class DownloadedDataQualityDiffGateHistoryEntry:
    FIELDS = ENTRY_FIELDS

    def __init__(self, ordinal: int, snapshot_id: str, gate_id: str, gate_address: str, runtime_address: str, decision: str, state: str, accepted: bool, release_ready: bool, finding_count: int, safe_count: int, review_count: int, blocked_count: int, policy_address: str, previous_entry_address: str, transition: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "quality gate history entry ordinal", MAX_ENTRIES)
        if self.ordinal < 1:
            raise ValidationError("quality gate history entry ordinal must be positive")
        self.snapshot_id = _label(snapshot_id, "quality gate history snapshot ID")
        self.gate_id = _label(gate_id, "quality gate history gate ID")
        self.gate_address = _address(gate_address, "quality gate history gate address", "glio-noncode-download-quality-diff-gate")
        self.runtime_address = _address(runtime_address, "quality gate history runtime address", runtime_model.RUNTIME_PREFIX)
        self.decision = _label(decision, "quality gate history decision")
        if self.decision not in DECISIONS:
            raise ValidationError("quality gate history decision is unsupported")
        self.state = _label(state, "quality gate history state")
        if self.state not in STATES[1:]:
            raise ValidationError("quality gate history entry state is unsupported")
        self.accepted = _bool(accepted, "quality gate history entry acceptance")
        self.release_ready = _bool(release_ready, "quality gate history entry release readiness")
        for field in ("finding_count", "safe_count", "review_count", "blocked_count"):
            setattr(self, field, _count(locals()[field], f"quality gate history entry {field}", runtime_model.gate_model.MAX_FINDINGS))
        self.policy_address = _address(policy_address, "quality gate history policy address", "glio-noncode-download-quality-diff-gate-policy")
        self.previous_entry_address = _address(previous_entry_address, "quality gate history previous entry address")
        self.transition = _label(transition, "quality gate history transition")
        if self.transition not in TRANSITIONS:
            raise ValidationError("quality gate history transition is unsupported")
        self.content_address = _address(content_address, "quality gate history entry address", ENTRY_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "quality gate history entry address")
        self._validate()

    def _validate(self) -> None:
        if self.decision == "promote" and self.state != "eligible":
            raise ValidationError("promote history entry must be eligible")
        if self.decision == "hold" and self.state != "review":
            raise ValidationError("hold history entry must be review")
        if self.decision == "block" and self.state != "blocked":
            raise ValidationError("block history entry must be blocked")
        if self.accepted != (self.decision == "promote") or self.release_ready != self.accepted:
            raise ValidationError("quality gate history entry readiness does not replay")
        if self.finding_count != self.safe_count + self.review_count + self.blocked_count:
            raise ValidationError("quality gate history entry counts are not conserved")
        if self.transition == "initial" and self.previous_entry_address != INITIAL_HEAD:
            raise ValidationError("initial history entry must point to the initial head")
        if not _public(self.to_dict()):
            raise ValidationError("quality gate history entry crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_entry(self) != self.content_address:
            raise ValidationError("quality gate history entry address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffGateHistoryEntry":
        value = _mapping(value, "quality gate history entry")
        _strict(value, set(cls.FIELDS), "quality gate history entry")
        return cls(*(value[field] for field in cls.FIELDS))


def address_entry(value: DownloadedDataQualityDiffGateHistoryEntry) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ENTRY_PREFIX)


class DownloadedDataQualityDiffGateHistory:
    FIELDS = HISTORY_FIELDS

    def __init__(self, history_id: str, version: str, boundary: str, gate_id: str, head_address: str, entry_count: int, promote_count: int, hold_count: int, block_count: int, accepted_count: int, release_ready_count: int, state: str, accepted: bool, release_ready: bool, entries: Sequence[DownloadedDataQualityDiffGateHistoryEntry | Mapping[str, Any]], content_address: str) -> None:
        self.history_id = _label(history_id, "quality gate history ID")
        self.version = _text(version, "quality gate history version")
        self.boundary = _text(boundary, "quality gate history boundary", 512)
        self.gate_id = _label(gate_id, "quality gate history gate ID")
        self.head_address = _address(head_address, "quality gate history head address")
        self.entry_count = _count(entry_count, "quality gate history entry count", MAX_ENTRIES)
        for field in ("promote_count", "hold_count", "block_count", "accepted_count", "release_ready_count"):
            setattr(self, field, _count(locals()[field], f"quality gate history {field}", MAX_ENTRIES))
        self.state = _label(state, "quality gate history state")
        if self.state not in STATES:
            raise ValidationError("quality gate history state is unsupported")
        self.accepted = _bool(accepted, "quality gate history acceptance")
        self.release_ready = _bool(release_ready, "quality gate history release readiness")
        self.entries = tuple(item if isinstance(item, DownloadedDataQualityDiffGateHistoryEntry) else DownloadedDataQualityDiffGateHistoryEntry.from_mapping(item) for item in _sequence(entries, "quality gate history entries", MAX_ENTRIES))
        self.content_address = _address(content_address, "quality gate history address", HISTORY_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "quality gate history address")
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("quality gate history version or boundary is not current")
        if self.entry_count != len(self.entries):
            raise ValidationError("quality gate history entry count does not replay")
        if tuple(item.ordinal for item in self.entries) != tuple(range(1, self.entry_count + 1)):
            raise ValidationError("quality gate history entry ordinals are not contiguous")
        if any(item.gate_id != self.gate_id for item in self.entries):
            raise ValidationError("quality gate history gate IDs do not match")
        if len({item.snapshot_id for item in self.entries}) != self.entry_count:
            raise ValidationError("quality gate history snapshot IDs must be unique")
        if self.entry_count == 0:
            if self.head_address != INITIAL_HEAD or self.state != "empty" or self.accepted or self.release_ready:
                raise ValidationError("empty quality gate history does not replay")
        else:
            if self.entries[0].previous_entry_address != INITIAL_HEAD or self.head_address != self.entries[-1].content_address:
                raise ValidationError("quality gate history head does not replay")
            if any(item.previous_entry_address != self.entries[index - 1].content_address for index, item in enumerate(self.entries) if index > 0):
                raise ValidationError("quality gate history ancestry is not contiguous")
            latest = self.entries[-1]
            if self.state != latest.state or self.accepted != (self.entry_count > 0) or self.release_ready != latest.release_ready:
                raise ValidationError("quality gate history latest projection does not replay")
        counts = (sum(item.decision == "promote" for item in self.entries), sum(item.decision == "hold" for item in self.entries), sum(item.decision == "block" for item in self.entries), sum(item.accepted for item in self.entries), sum(item.release_ready for item in self.entries))
        if (self.promote_count, self.hold_count, self.block_count, self.accepted_count, self.release_ready_count) != counts:
            raise ValidationError("quality gate history decision counts are not conserved")
        if not _public(self.to_dict()):
            raise ValidationError("quality gate history crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_history(self) != self.content_address:
            raise ValidationError("quality gate history address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"history_id": self.history_id, "version": self.version, "boundary": self.boundary, "gate_id": self.gate_id, "head_address": self.head_address, "entry_count": self.entry_count, "promote_count": self.promote_count, "hold_count": self.hold_count, "block_count": self.block_count, "accepted_count": self.accepted_count, "release_ready_count": self.release_ready_count, "state": self.state, "accepted": self.accepted, "release_ready": self.release_ready, "entries": tuple(item.to_dict() for item in self.entries), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "entries"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffGateHistory":
        value = _mapping(value, "quality gate history")
        _strict(value, set(cls.FIELDS), "quality gate history")
        return cls(*(value[field] for field in cls.FIELDS))


def address_history(value: DownloadedDataQualityDiffGateHistory) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=HISTORY_PREFIX)


def _transition(previous: DownloadedDataQualityDiffGateHistoryEntry | None, current: DownloadedDataQualityDiffGateHistoryEntry) -> str:
    if previous is None:
        return "initial"
    previous_score = STATE_SCORE[previous.state]
    current_score = STATE_SCORE[current.state]
    if current_score > previous_score:
        return "improved"
    if current_score < previous_score:
        return "regressed"
    comparable = ("gate_id", "decision", "state", "accepted", "release_ready", "finding_count", "safe_count", "review_count", "blocked_count", "policy_address")
    return "unchanged" if all(getattr(previous, field) == getattr(current, field) for field in comparable) else "changed"


def _entry(runtime: runtime_model.DownloadedDataQualityDiffGateRuntime, ordinal: int, snapshot_id: str, previous: DownloadedDataQualityDiffGateHistoryEntry | None) -> DownloadedDataQualityDiffGateHistoryEntry:
    gate = runtime.gate
    body = {"ordinal": ordinal, "snapshot_id": snapshot_id, "gate_id": gate.gate_id, "gate_address": gate.content_address, "runtime_address": runtime.content_address, "decision": gate.decision, "state": gate.state, "accepted": gate.accepted, "release_ready": runtime.release_ready, "finding_count": gate.finding_count, "safe_count": gate.safe_count, "review_count": gate.review_count, "blocked_count": gate.blocked_count, "policy_address": gate.policy.content_address, "previous_entry_address": INITIAL_HEAD if previous is None else previous.content_address}
    placeholder = DownloadedDataQualityDiffGateHistoryEntry(**body, transition="initial" if previous is None else "changed", content_address=ENTRY_PREFIX + ":pending")
    transition = _transition(previous, placeholder)
    provisional = DownloadedDataQualityDiffGateHistoryEntry(**body, transition=transition, content_address=ENTRY_PREFIX + ":pending")
    return DownloadedDataQualityDiffGateHistoryEntry(**body, transition=transition, content_address=address_entry(provisional))


def _history_body(history_id: str, gate_id: str, entries: Sequence[DownloadedDataQualityDiffGateHistoryEntry]) -> dict[str, Any]:
    entries = tuple(entries)
    latest = entries[-1] if entries else None
    return {"history_id": history_id, "version": VERSION, "boundary": BOUNDARY, "gate_id": gate_id, "head_address": INITIAL_HEAD if latest is None else latest.content_address, "entry_count": len(entries), "promote_count": sum(item.decision == "promote" for item in entries), "hold_count": sum(item.decision == "hold" for item in entries), "block_count": sum(item.decision == "block" for item in entries), "accepted_count": sum(item.accepted for item in entries), "release_ready_count": sum(item.release_ready for item in entries), "state": "empty" if latest is None else latest.state, "accepted": bool(entries), "release_ready": False if latest is None else latest.release_ready, "entries": entries}


def _finalize(body: Mapping[str, Any]) -> DownloadedDataQualityDiffGateHistory:
    provisional = DownloadedDataQualityDiffGateHistory(**body, content_address=HISTORY_PREFIX + ":pending")
    return DownloadedDataQualityDiffGateHistory(**body, content_address=address_history(provisional))


def empty_history(*, history_id: str = DEFAULT_HISTORY_ID, gate_id: str = runtime_model.gate_model.DEFAULT_GATE_ID) -> DownloadedDataQualityDiffGateHistory:
    return _finalize(_history_body(history_id, gate_id, ()))


def build_history(runtime: runtime_model.DownloadedDataQualityDiffGateRuntime, *, history_id: str = DEFAULT_HISTORY_ID, snapshot_id: str = "snapshot-1") -> DownloadedDataQualityDiffGateHistory:
    if not isinstance(runtime, runtime_model.DownloadedDataQualityDiffGateRuntime):
        raise ValidationError("quality gate history requires a typed gate runtime")
    entry = _entry(runtime, 1, snapshot_id, None)
    return _finalize(_history_body(history_id, runtime.gate.gate_id, (entry,)))


def append_history(history: DownloadedDataQualityDiffGateHistory, runtime: runtime_model.DownloadedDataQualityDiffGateRuntime, *, snapshot_id: str, expected_head: str | None = None) -> DownloadedDataQualityDiffGateHistory:
    if not isinstance(history, DownloadedDataQualityDiffGateHistory) or not isinstance(runtime, runtime_model.DownloadedDataQualityDiffGateRuntime):
        raise ValidationError("quality gate history append requires typed history and runtime")
    if expected_head is not None and expected_head != history.head_address:
        raise ValidationError("quality gate history expected head is stale")
    if runtime.gate.gate_id != history.gate_id:
        raise ValidationError("quality gate history gate identity does not match")
    if any(item.snapshot_id == snapshot_id for item in history.entries):
        raise ValidationError("quality gate history snapshot ID already exists")
    if history.entry_count >= MAX_ENTRIES:
        raise ValidationError("quality gate history has reached its entry limit")
    entry = _entry(runtime, history.entry_count + 1, snapshot_id, history.entries[-1] if history.entries else None)
    return _finalize(_history_body(history.history_id, history.gate_id, history.entries + (entry,)))


def history_from_mapping(value: Mapping[str, Any]) -> DownloadedDataQualityDiffGateHistory:
    return DownloadedDataQualityDiffGateHistory.from_mapping(value)


def history_json(value: DownloadedDataQualityDiffGateHistory) -> str:
    return canonical_json(DownloadedDataQualityDiffGateHistory.from_mapping(value.to_dict()).to_dict())


def history_csv(value: DownloadedDataQualityDiffGateHistory) -> str:
    value = DownloadedDataQualityDiffGateHistory.from_mapping(value.to_dict())
    stream = io.StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(ENTRY_FIELDS)
    writer.writerows(tuple(";".join(getattr(item, field)) if field == "" else getattr(item, field) for field in ENTRY_FIELDS) for item in value.entries)
    return stream.getvalue()


def render_history_markdown(value: DownloadedDataQualityDiffGateHistory) -> str:
    value = DownloadedDataQualityDiffGateHistory.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Quality Diff Gate History", "", f"- History: `{value.history_id}`", f"- Entries: `{value.entry_count}`", f"- State: `{value.state}`", f"- Latest release ready: `{value.release_ready}`", f"- Head: `{value.head_address}`", f"- Address: `{value.content_address}`", "", "| # | snapshot | decision | state | transition | release ready |", "| ---: | --- | --- | --- | --- | :---: |"]
    lines.extend(f"| {item.ordinal} | `{item.snapshot_id}` | `{item.decision}` | `{item.state}` | `{item.transition}` | {item.release_ready} |" for item in value.entries)
    return "\n".join(lines) + "\n"


def entry_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality diff gate history entry", "type": "object", "additionalProperties": False, "required": list(ENTRY_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "snapshot_id": {"type": "string"}, "gate_id": {"type": "string"}, "gate_address": {"type": "string"}, "runtime_address": {"type": "string"}, "decision": {"enum": list(DECISIONS)}, "state": {"enum": list(STATES[1:])}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "finding_count": {"type": "integer", "minimum": 0}, "safe_count": {"type": "integer", "minimum": 0}, "review_count": {"type": "integer", "minimum": 0}, "blocked_count": {"type": "integer", "minimum": 0}, "policy_address": {"type": "string"}, "previous_entry_address": {"type": "string"}, "transition": {"enum": list(TRANSITIONS)}, "content_address": {"type": "string"}}}


def history_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality diff gate history", "type": "object", "additionalProperties": False, "required": list(HISTORY_FIELDS), "properties": {"history_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "gate_id": {"type": "string"}, "head_address": {"type": "string"}, "entry_count": {"type": "integer", "minimum": 0}, "promote_count": {"type": "integer", "minimum": 0}, "hold_count": {"type": "integer", "minimum": 0}, "block_count": {"type": "integer", "minimum": 0}, "accepted_count": {"type": "integer", "minimum": 0}, "release_ready_count": {"type": "integer", "minimum": 0}, "state": {"enum": list(STATES)}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "entries": {"type": "array", "items": entry_schema(), "maxItems": MAX_ENTRIES}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "states": STATES, "decisions": DECISIONS, "transitions": TRANSITIONS, "operations": ("empty_history", "build_history", "append_history", "history_from_mapping", "history_json", "history_csv", "render_history_markdown"), "limits": {"max_entries": MAX_ENTRIES}}


__all__ = ["BOUNDARY", "DECISIONS", "DEFAULT_HISTORY_ID", "ENTRY_FIELDS", "ENTRY_PREFIX", "HISTORY_FIELDS", "HISTORY_PREFIX", "INITIAL_HEAD", "MAX_ENTRIES", "STATES", "TRANSITIONS", "DownloadedDataQualityDiffGateHistory", "DownloadedDataQualityDiffGateHistoryEntry", "address_entry", "address_history", "append_history", "build_history", "capabilities", "empty_history", "entry_schema", "history_csv", "history_from_mapping", "history_json", "history_schema", "render_history_markdown"]
