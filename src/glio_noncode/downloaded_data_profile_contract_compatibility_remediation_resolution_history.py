"""Append-only, value-free history for remediation resolution snapshots."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution as resolution_model,
)
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-v1"
BOUNDARY = "public_downloaded_data_profile_contract_compatibility_remediation_resolution_history"
HISTORY_PREFIX = "glio-noncode-download-profile-contract-compatibility-remediation-resolution-history"
ENTRY_PREFIX = HISTORY_PREFIX + "-entry"
DEFAULT_HISTORY_ID = HISTORY_PREFIX
TRANSITIONS = ("initial", "improved", "regressed", "unchanged")
STATES = ("empty", "clear", "review", "blocked")
DECISIONS = ("promote", "hold", "block")
ENTRY_FIELDS = ("ordinal", "resolution_id", "plan_id", "resolution_address", "required_open_count", "pending_count", "resolved_count", "waived_count", "rejected_count", "not_applicable_count", "state", "decision", "release_ready", "transition", "previous_resolution_address", "content_address")
HISTORY_FIELDS = ("history_id", "version", "boundary", "entries", "entry_count", "latest_resolution_address", "latest_required_open_count", "initial_count", "improved_count", "regressed_count", "unchanged_count", "state", "decision", "accepted", "release_ready", "content_address")
MAX_ENTRIES = resolution_model.MAX_ENTRIES


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 256, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = True) -> str:
    value = _text(value, field, 2048, required=required)
    if value and ("/" in value or "\\" in value or '"' in value or ":" not in value or (prefix is not None and not value.startswith(prefix + ":"))):
        raise ValidationError(f"{field} has an unsupported address")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > maximum:
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


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def address_entry(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryEntry) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryEntry):
        raise ValidationError("history entry address requires a typed entry")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ENTRY_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryEntry:
    """One addressed resolution snapshot and its derived trend transition."""

    FIELDS = ENTRY_FIELDS

    def __init__(self, ordinal: int, resolution_id: str, plan_id: str, resolution_address: str, required_open_count: int, pending_count: int, resolved_count: int, waived_count: int, rejected_count: int, not_applicable_count: int, state: str, decision: str, release_ready: bool, transition: str, previous_resolution_address: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "history entry ordinal", MAX_ENTRIES, positive=True)
        self.resolution_id = _label(resolution_id, "history resolution ID")
        self.plan_id = _label(plan_id, "history plan ID")
        self.resolution_address = _address(resolution_address, "history resolution address", resolution_model.RESOLUTION_PREFIX)
        self.required_open_count = _count(required_open_count, "history open count", resolution_model.MAX_ENTRIES)
        self.pending_count = _count(pending_count, "history pending count", resolution_model.MAX_ENTRIES)
        self.resolved_count = _count(resolved_count, "history resolved count", resolution_model.MAX_ENTRIES)
        self.waived_count = _count(waived_count, "history waived count", resolution_model.MAX_ENTRIES)
        self.rejected_count = _count(rejected_count, "history rejected count", resolution_model.MAX_ENTRIES)
        self.not_applicable_count = _count(not_applicable_count, "history not-applicable count", resolution_model.MAX_ENTRIES)
        self.state = _label(state, "history entry state")
        if self.state not in resolution_model.STATES:
            raise ValidationError("history entry state is unsupported")
        self.decision = _label(decision, "history entry decision")
        if self.decision not in resolution_model.DECISIONS:
            raise ValidationError("history entry decision is unsupported")
        self.release_ready = _bool(release_ready, "history entry release readiness")
        self.transition = _label(transition, "history transition")
        if self.transition not in TRANSITIONS:
            raise ValidationError("history transition is unsupported")
        self.previous_resolution_address = _address(previous_resolution_address, "history previous resolution address", resolution_model.RESOLUTION_PREFIX, required=False)
        self.content_address = _address(content_address, "history entry address", ENTRY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.ordinal == 1 and (self.transition != "initial" or self.previous_resolution_address):
            raise ValidationError("first history entry must be initial")
        if self.ordinal > 1 and (self.transition == "initial" or not self.previous_resolution_address):
            raise ValidationError("later history entries require a previous resolution")
        if self.required_open_count > self.pending_count + self.waived_count + self.rejected_count:
            raise ValidationError("history open count exceeds unresolved statuses")
        if self.release_ready != (self.required_open_count == 0 and self.state == "clear"):
            raise ValidationError("history entry readiness does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("history entry crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_entry(self) != self.content_address:
            raise ValidationError("history entry address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryEntry:
        value = _mapping(value, "history entry")
        _strict(value, set(cls.FIELDS), "history entry")
        return cls(*(value[field] for field in cls.FIELDS))


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistory:
    """An ordered history of addressed remediation-resolution snapshots."""

    FIELDS = HISTORY_FIELDS

    def __init__(self, history_id: str, version: str, boundary: str, entries: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryEntry | Mapping[str, Any]], entry_count: int, latest_resolution_address: str, latest_required_open_count: int, initial_count: int, improved_count: int, regressed_count: int, unchanged_count: int, state: str, decision: str, accepted: bool, release_ready: bool, content_address: str) -> None:
        self.history_id = _label(history_id, "history ID")
        self.version = _text(version, "history version")
        self.boundary = _text(boundary, "history boundary", 512)
        self.entries = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryEntry) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryEntry.from_mapping(item) for item in _sequence(entries, "history entries", MAX_ENTRIES))
        self.entry_count = _count(entry_count, "history entry count", MAX_ENTRIES)
        self.latest_resolution_address = _address(latest_resolution_address, "latest resolution address", resolution_model.RESOLUTION_PREFIX, required=False)
        self.latest_required_open_count = _count(latest_required_open_count, "latest history open count", resolution_model.MAX_ENTRIES)
        self.initial_count = _count(initial_count, "history initial count", MAX_ENTRIES)
        self.improved_count = _count(improved_count, "history improved count", MAX_ENTRIES)
        self.regressed_count = _count(regressed_count, "history regressed count", MAX_ENTRIES)
        self.unchanged_count = _count(unchanged_count, "history unchanged count", MAX_ENTRIES)
        self.state = _label(state, "history state")
        if self.state not in STATES:
            raise ValidationError("history state is unsupported")
        self.decision = _label(decision, "history decision")
        if self.decision not in DECISIONS:
            raise ValidationError("history decision is unsupported")
        self.accepted = _bool(accepted, "history acceptance")
        self.release_ready = _bool(release_ready, "history release readiness")
        self.content_address = _address(content_address, "history address", HISTORY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("history version or boundary is not current")
        if len(self.entries) != self.entry_count or tuple(item.ordinal for item in self.entries) != tuple(range(1, self.entry_count + 1)):
            raise ValidationError("history entry order is not conserved")
        if len({item.resolution_address for item in self.entries}) != len(self.entries):
            raise ValidationError("history resolution addresses must be unique")
        ranks = {"clear": 0, "review": 1, "blocked": 2}
        for index, item in enumerate(self.entries):
            if index == 0:
                expected_transition = "initial"
            else:
                previous = self.entries[index - 1]
                if item.previous_resolution_address != previous.resolution_address:
                    raise ValidationError("history ancestry does not link to the previous snapshot")
                if item.required_open_count < previous.required_open_count:
                    expected_transition = "improved"
                elif item.required_open_count > previous.required_open_count:
                    expected_transition = "regressed"
                elif ranks[item.state] < ranks[previous.state]:
                    expected_transition = "improved"
                elif ranks[item.state] > ranks[previous.state]:
                    expected_transition = "regressed"
                else:
                    expected_transition = "unchanged"
            if item.transition != expected_transition:
                raise ValidationError("history transition does not replay")
        if self.entry_count:
            latest = self.entries[-1]
            if self.latest_resolution_address != latest.resolution_address or self.latest_required_open_count != latest.required_open_count:
                raise ValidationError("history latest snapshot does not replay")
        elif self.latest_resolution_address or self.latest_required_open_count:
            raise ValidationError("empty history has latest snapshot data")
        transitions = tuple(sum(item.transition == transition for item in self.entries) for transition in TRANSITIONS)
        if transitions != (self.initial_count, self.improved_count, self.regressed_count, self.unchanged_count):
            raise ValidationError("history transition counts do not replay")
        expected_state = "empty" if not self.entries else "blocked" if self.entries[-1].state == "blocked" else "clear" if self.entries[-1].release_ready else "review"
        expected_decision = {"empty": "hold", "clear": "promote", "review": "hold", "blocked": "block"}[expected_state]
        if (self.state, self.decision, self.accepted, self.release_ready) != (expected_state, expected_decision, expected_state == "clear", expected_state == "clear"):
            raise ValidationError("history disposition does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("history crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_history(self) != self.content_address:
            raise ValidationError("history address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"history_id": self.history_id, "version": self.version, "boundary": self.boundary, "entries": tuple(item.to_dict() for item in self.entries), "entry_count": self.entry_count, "latest_resolution_address": self.latest_resolution_address, "latest_required_open_count": self.latest_required_open_count, "initial_count": self.initial_count, "improved_count": self.improved_count, "regressed_count": self.regressed_count, "unchanged_count": self.unchanged_count, "state": self.state, "decision": self.decision, "accepted": self.accepted, "release_ready": self.release_ready, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "entries"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistory:
        value = _mapping(value, "history")
        _strict(value, set(cls.FIELDS), "history")
        return cls(*(value[field] for field in cls.FIELDS))


def address_history(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistory) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistory):
        raise ValidationError("history address requires a typed history")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=HISTORY_PREFIX)


def _transition(current: resolution_model.DownloadedDataProfileContractCompatibilityRemediationResolution, previous: resolution_model.DownloadedDataProfileContractCompatibilityRemediationResolution | None) -> tuple[str, str]:
    if previous is None:
        return "initial", ""
    if current.required_open_count < previous.required_open_count:
        return "improved", previous.content_address
    if current.required_open_count > previous.required_open_count:
        return "regressed", previous.content_address
    ranks = {"clear": 0, "review": 1, "blocked": 2}
    transition = "improved" if ranks[current.state] < ranks[previous.state] else "regressed" if ranks[current.state] > ranks[previous.state] else "unchanged"
    return transition, previous.content_address


def _entry(value: resolution_model.DownloadedDataProfileContractCompatibilityRemediationResolution, ordinal: int, transition: str, previous_address: str) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryEntry:
    body = {"ordinal": ordinal, "resolution_id": value.resolution_id, "plan_id": value.plan_id, "resolution_address": value.content_address, "required_open_count": value.required_open_count, "pending_count": value.pending_count, "resolved_count": value.resolved_count, "waived_count": value.waived_count, "rejected_count": value.rejected_count, "not_applicable_count": value.not_applicable_count, "state": value.state, "decision": value.decision, "release_ready": value.release_ready, "transition": transition, "previous_resolution_address": previous_address, "content_address": ENTRY_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryEntry(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryEntry(**(body | {"content_address": address_entry(provisional)}))


def build_history(resolutions: Sequence[resolution_model.DownloadedDataProfileContractCompatibilityRemediationResolution], *, history_id: str = DEFAULT_HISTORY_ID) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistory:
    if isinstance(resolutions, (str, bytes)) or not isinstance(resolutions, Sequence) or len(resolutions) > MAX_ENTRIES:
        raise ValidationError("history resolutions must be a bounded sequence")
    typed = tuple(resolutions)
    if any(not isinstance(item, resolution_model.DownloadedDataProfileContractCompatibilityRemediationResolution) for item in typed):
        raise ValidationError("history requires typed resolution snapshots")
    if len({item.content_address for item in typed}) != len(typed):
        raise ValidationError("history cannot repeat a resolution address")
    entries = []
    previous = None
    for ordinal, value in enumerate(typed, 1):
        transition, previous_address = _transition(value, previous)
        entries.append(_entry(value, ordinal, transition, previous_address))
        previous = value
    counts = tuple(sum(item.transition == transition for item in entries) for transition in TRANSITIONS)
    latest = typed[-1] if typed else None
    state = "empty" if latest is None else "blocked" if latest.state == "blocked" else "clear" if latest.release_ready else "review"
    body = {"history_id": history_id, "version": VERSION, "boundary": BOUNDARY, "entries": tuple(entries), "entry_count": len(entries), "latest_resolution_address": latest.content_address if latest else "", "latest_required_open_count": latest.required_open_count if latest else 0, "initial_count": counts[0], "improved_count": counts[1], "regressed_count": counts[2], "unchanged_count": counts[3], "state": state, "decision": {"empty": "hold", "clear": "promote", "review": "hold", "blocked": "block"}[state], "accepted": state == "clear", "release_ready": state == "clear", "content_address": HISTORY_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistory(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistory(**(body | {"content_address": address_history(provisional)}))


def history_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistory:
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistory.from_mapping(value)


def history_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistory) -> str:
    return canonical_json(DownloadedDataProfileContractCompatibilityRemediationResolutionHistory.from_mapping(value.to_dict()).to_dict())


def history_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistory) -> str:
    value = DownloadedDataProfileContractCompatibilityRemediationResolutionHistory.from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(ENTRY_FIELDS)
    writer.writerows(tuple(item.to_dict()[field] for field in ENTRY_FIELDS) for item in value.entries)
    return stream.getvalue()


def render_history_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistory) -> str:
    value = DownloadedDataProfileContractCompatibilityRemediationResolutionHistory.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Contract Compatibility Remediation Resolution History", "", f"- History: `{value.history_id}`", f"- Entries: `{value.entry_count}`", f"- Latest open required: `{value.latest_required_open_count}`", f"- State: `{value.state}`", f"- Decision: `{value.decision}`", f"- Release ready: `{value.release_ready}`", f"- Address: `{value.content_address}`", "", "| # | resolution | open | transition | state |", "| ---: | --- | ---: | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.resolution_id}` | `{item.required_open_count}` | `{item.transition}` | `{item.state}` |" for item in value.entries)
    return "\n".join(lines) + "\n"


def entry_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation resolution history entry", "type": "object", "additionalProperties": False, "required": list(ENTRY_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "resolution_id": {"type": "string"}, "plan_id": {"type": "string"}, "resolution_address": {"type": "string"}, "required_open_count": {"type": "integer", "minimum": 0}, "pending_count": {"type": "integer", "minimum": 0}, "resolved_count": {"type": "integer", "minimum": 0}, "waived_count": {"type": "integer", "minimum": 0}, "rejected_count": {"type": "integer", "minimum": 0}, "not_applicable_count": {"type": "integer", "minimum": 0}, "state": {"enum": list(resolution_model.STATES)}, "decision": {"enum": list(resolution_model.DECISIONS)}, "release_ready": {"type": "boolean"}, "transition": {"enum": list(TRANSITIONS)}, "previous_resolution_address": {"type": "string"}, "content_address": {"type": "string"}}}


def history_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation resolution history", "type": "object", "additionalProperties": False, "required": list(HISTORY_FIELDS), "properties": {"history_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "entries": {"type": "array", "items": entry_schema(), "maxItems": MAX_ENTRIES}, "entry_count": {"type": "integer", "minimum": 0}, "latest_resolution_address": {"type": "string"}, "latest_required_open_count": {"type": "integer", "minimum": 0}, "initial_count": {"type": "integer", "minimum": 0}, "improved_count": {"type": "integer", "minimum": 0}, "regressed_count": {"type": "integer", "minimum": 0}, "unchanged_count": {"type": "integer", "minimum": 0}, "state": {"enum": list(STATES)}, "decision": {"enum": list(DECISIONS)}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "transitions": TRANSITIONS, "states": STATES, "decisions": DECISIONS, "operations": ("build_history", "history_from_mapping", "history_json", "history_csv", "render_history_markdown"), "limits": {"max_entries": MAX_ENTRIES}}


__all__ = ["BOUNDARY", "DECISIONS", "DEFAULT_HISTORY_ID", "ENTRY_FIELDS", "ENTRY_PREFIX", "HISTORY_FIELDS", "HISTORY_PREFIX", "MAX_ENTRIES", "STATES", "TRANSITIONS", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistory", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryEntry", "address_entry", "address_history", "build_history", "capabilities", "entry_schema", "history_csv", "history_from_mapping", "history_json", "history_schema", "render_history_markdown"]
