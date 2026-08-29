"""Ordered, deterministic history of verified observatory registry snapshots.

Pairwise registry diffs explain one transition. This boundary records an
explicit sequence of verified snapshots and the derived transition summaries
between adjacent snapshots, allowing repeated downloaded-data runs to be
replayed as a timeline without storing source paths or mutable process state.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
import json
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry as registry_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_diff as diff_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes


VERSION = diff_model.VERSION + "-history-v1"
BOUNDARY = diff_model.BOUNDARY + "_history"
HISTORY_PREFIX = registry_model.REGISTRY_PREFIX + "-history"
SNAPSHOT_PREFIX = HISTORY_PREFIX + "-snapshot"
TRANSITION_PREFIX = HISTORY_PREFIX + "-transition"
MANIFEST_PREFIX = HISTORY_PREFIX + "-manifest"
DEFAULT_HISTORY_ID = "glio-noncode-observatory-archive-registry-history"
MANIFEST_NAME = "manifest.json"
HISTORY_NAME = "history.json"
SNAPSHOTS_NAME = "snapshots.json"
TRANSITIONS_NAME = "transitions.json"
FILES = (MANIFEST_NAME, HISTORY_NAME, SNAPSHOTS_NAME, TRANSITIONS_NAME)
MAX_SNAPSHOTS = 64
MAX_TRANSITIONS = MAX_SNAPSHOTS - 1
STATES = tuple(item.value for item in diff_model.RegistryDiffState)


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a non-empty string of at most {maximum} characters")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > maximum:
        raise ValidationError(f"{field} is outside its declared bound")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field, 2048)
    if ":" not in value or value.startswith(("/", "\\")) or "\\" in value or not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has an invalid public namespace")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be a mapping")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if not isinstance(value, (list, tuple)) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unsupported fields: {sorted(unknown)}")


def _public(value: Any) -> bool:
    return diff_model._public(value)


def _metrics(value: Mapping[str, Any]) -> dict[str, int]:
    value = _mapping(value, "registry history snapshot metrics")
    fields = set(registry_model.RegistryMetrics.FIELDS)
    _strict(value, fields, "registry history snapshot metrics")
    result = {field: _count(value[field], f"registry history snapshot metric {field}", 2**63 - 1) for field in registry_model.RegistryMetrics.FIELDS}
    return result


class RegistryHistorySnapshot:
    """A public point-in-time projection of one verified registry."""

    def __init__(self, ordinal: int, registry_id: str, registry_address: str, state: str, accepted: bool, release_ready: bool, entry_count: int, metrics: Mapping[str, Any], verification_address: str, snapshot_address: str) -> None:
        self.ordinal = ordinal
        self.registry_id = registry_id
        self.registry_address = registry_address
        self.state = state
        self.accepted = accepted
        self.release_ready = release_ready
        self.entry_count = entry_count
        self.metrics = _metrics(metrics)
        self.verification_address = verification_address
        self.snapshot_address = snapshot_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "registry history snapshot ordinal", MAX_SNAPSHOTS, positive=True)
        _text(self.registry_id, "registry history snapshot registry ID")
        _address(self.registry_address, "registry history snapshot registry address", registry_model.REGISTRY_PREFIX)
        if self.state not in tuple(item.value for item in registry_model.RegistryState):
            raise ValidationError("registry history snapshot state is invalid")
        _bool(self.accepted, "registry history snapshot accepted")
        _bool(self.release_ready, "registry history snapshot release-ready")
        _count(self.entry_count, "registry history snapshot entry count", registry_model.MAX_ENTRIES)
        _address(self.verification_address, "registry history snapshot verification address", registry_model.REGISTRY_VERIFICATION_PREFIX)
        if self.snapshot_address.startswith("pending:"):
            _text(self.snapshot_address, "registry history snapshot address")
        else:
            _address(self.snapshot_address, "registry history snapshot address", SNAPSHOT_PREFIX)
        if not _public(self.to_dict()) or (not self.snapshot_address.startswith("pending:") and address_snapshot(self) != self.snapshot_address):
            raise ValidationError("registry history snapshot address or public boundary is invalid")

    @classmethod
    def from_registry(cls, value: registry_model.ObservatoryArchiveRegistry, ordinal: int) -> RegistryHistorySnapshot:
        registry_model.verify_registry(value)
        body = {"ordinal": ordinal, "registry_id": value.registry_id, "registry_address": value.content_address, "state": value.state, "accepted": value.accepted, "release_ready": value.release_ready, "entry_count": value.entry_count, "metrics": value.metrics.to_dict(), "verification_address": value.verification_address}
        provisional = cls(**body, snapshot_address="pending:snapshot")
        return cls(**body, snapshot_address=address_snapshot(provisional))

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistorySnapshot:
        value = _mapping(value, "registry history snapshot")
        _strict(value, {"ordinal", "registry_id", "registry_address", "state", "accepted", "release_ready", "entry_count", "metrics", "verification_address", "snapshot_address"}, "registry history snapshot")
        return cls(**value)

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "registry_id": self.registry_id, "registry_address": self.registry_address, "state": self.state, "accepted": self.accepted, "release_ready": self.release_ready, "entry_count": self.entry_count, "metrics": self.metrics, "verification_address": self.verification_address, "snapshot_address": self.snapshot_address}


def address_snapshot(value: RegistryHistorySnapshot) -> str:
    if not isinstance(value, RegistryHistorySnapshot):
        raise ValidationError("registry history snapshot address requires a typed snapshot")
    return content_hash(value.to_dict() | {"snapshot_address": None}, prefix=SNAPSHOT_PREFIX)


class RegistryHistoryTransition:
    """A derived adjacent-snapshot diff summary."""

    def __init__(self, ordinal: int, baseline_ordinal: int, candidate_ordinal: int, baseline_registry_address: str, candidate_registry_address: str, diff_address: str, state: str, item_count: int, added_count: int, removed_count: int, changed_count: int, unchanged_count: int, registry_changed_fields: Sequence[str], transition_address: str) -> None:
        self.ordinal = ordinal
        self.baseline_ordinal = baseline_ordinal
        self.candidate_ordinal = candidate_ordinal
        self.baseline_registry_address = baseline_registry_address
        self.candidate_registry_address = candidate_registry_address
        self.diff_address = diff_address
        self.state = state
        self.item_count = item_count
        self.added_count = added_count
        self.removed_count = removed_count
        self.changed_count = changed_count
        self.unchanged_count = unchanged_count
        self.registry_changed_fields = tuple(registry_changed_fields)
        self.transition_address = transition_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "registry history transition ordinal", MAX_TRANSITIONS, positive=True)
        if self.baseline_ordinal != self.ordinal or self.candidate_ordinal != self.ordinal + 1:
            raise ValidationError("registry history transition ordinals are not adjacent")
        _address(self.baseline_registry_address, "registry history transition baseline address", registry_model.REGISTRY_PREFIX)
        _address(self.candidate_registry_address, "registry history transition candidate address", registry_model.REGISTRY_PREFIX)
        _address(self.diff_address, "registry history transition diff address", diff_model.DIFF_PREFIX)
        if self.state not in STATES:
            raise ValidationError("registry history transition state is invalid")
        _count(self.item_count, "registry history transition item count", diff_model.MAX_DIFF_ITEMS)
        for field, value in (("added", self.added_count), ("removed", self.removed_count), ("changed", self.changed_count), ("unchanged", self.unchanged_count)):
            _count(value, f"registry history transition {field} count", diff_model.MAX_DIFF_ITEMS)
        if self.added_count + self.removed_count + self.changed_count + self.unchanged_count != self.item_count:
            raise ValidationError("registry history transition counts are not conserved")
        if any(field not in diff_model.REGISTRY_FIELDS for field in self.registry_changed_fields) or len(set(self.registry_changed_fields)) != len(self.registry_changed_fields) or tuple(field for field in diff_model.REGISTRY_FIELDS if field in self.registry_changed_fields) != self.registry_changed_fields:
            raise ValidationError("registry history transition registry fields are invalid")
        if self.transition_address.startswith("pending:"):
            _text(self.transition_address, "registry history transition address")
        else:
            _address(self.transition_address, "registry history transition address", TRANSITION_PREFIX)
        if not _public(self.to_dict()) or (not self.transition_address.startswith("pending:") and address_transition(self) != self.transition_address):
            raise ValidationError("registry history transition address or public boundary is invalid")

    @classmethod
    def from_diff(cls, value: diff_model.RegistryDiff, ordinal: int) -> RegistryHistoryTransition:
        diff_model.verify_diff(value)
        body = {"ordinal": ordinal, "baseline_ordinal": ordinal, "candidate_ordinal": ordinal + 1, "baseline_registry_address": value.baseline_address, "candidate_registry_address": value.candidate_address, "diff_address": value.content_address, "state": value.state, "item_count": value.item_count, "added_count": value.added_count, "removed_count": value.removed_count, "changed_count": value.changed_count, "unchanged_count": value.unchanged_count, "registry_changed_fields": value.registry_changed_fields}
        provisional = cls(**body, transition_address="pending:transition")
        return cls(**body, transition_address=address_transition(provisional))

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryTransition:
        value = _mapping(value, "registry history transition")
        _strict(value, {"ordinal", "baseline_ordinal", "candidate_ordinal", "baseline_registry_address", "candidate_registry_address", "diff_address", "state", "item_count", "added_count", "removed_count", "changed_count", "unchanged_count", "registry_changed_fields", "transition_address"}, "registry history transition")
        return cls(**value)

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "baseline_ordinal": self.baseline_ordinal, "candidate_ordinal": self.candidate_ordinal, "baseline_registry_address": self.baseline_registry_address, "candidate_registry_address": self.candidate_registry_address, "diff_address": self.diff_address, "state": self.state, "item_count": self.item_count, "added_count": self.added_count, "removed_count": self.removed_count, "changed_count": self.changed_count, "unchanged_count": self.unchanged_count, "registry_changed_fields": self.registry_changed_fields, "transition_address": self.transition_address}


def address_transition(value: RegistryHistoryTransition) -> str:
    if not isinstance(value, RegistryHistoryTransition):
        raise ValidationError("registry history transition address requires a typed transition")
    return content_hash(value.to_dict() | {"transition_address": None}, prefix=TRANSITION_PREFIX)


class RegistryHistory:
    """A content-addressed ordered sequence of verified registry snapshots."""

    def __init__(self, history_id: str, snapshots: Sequence[RegistryHistorySnapshot], transitions: Sequence[RegistryHistoryTransition], content_address: str) -> None:
        self.history_id = history_id
        self.version = VERSION
        self.boundary = BOUNDARY
        self.snapshots = tuple(snapshots)
        self.transitions = tuple(transitions)
        self.snapshot_count = len(self.snapshots)
        self.transition_count = len(self.transitions)
        self.start_registry_address = self.snapshots[0].registry_address if self.snapshots else registry_model.REGISTRY_PREFIX + ":empty"
        self.end_registry_address = self.snapshots[-1].registry_address if self.snapshots else registry_model.REGISTRY_PREFIX + ":empty"
        self.state_counts = {state: sum(item.state == state for item in self.transitions) for state in STATES}
        self.accepted = bool(self.snapshots) and all(item.accepted for item in self.snapshots)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.history_id, "registry history ID")
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("registry history version or boundary is invalid")
        if not 1 <= self.snapshot_count <= MAX_SNAPSHOTS or self.transition_count != self.snapshot_count - 1:
            raise ValidationError("registry history snapshot and transition counts are invalid")
        if any(not isinstance(item, RegistryHistorySnapshot) for item in self.snapshots) or tuple(item.ordinal for item in self.snapshots) != tuple(range(1, self.snapshot_count + 1)):
            raise ValidationError("registry history snapshot order is invalid")
        if any(not isinstance(item, RegistryHistoryTransition) for item in self.transitions) or tuple(item.ordinal for item in self.transitions) != tuple(range(1, self.transition_count + 1)):
            raise ValidationError("registry history transition order is invalid")
        for transition in self.transitions:
            baseline = self.snapshots[transition.baseline_ordinal - 1]
            candidate = self.snapshots[transition.candidate_ordinal - 1]
            if transition.baseline_registry_address != baseline.registry_address or transition.candidate_registry_address != candidate.registry_address:
                raise ValidationError("registry history transition linkage is invalid")
        expected_counts = {state: sum(item.state == state for item in self.transitions) for state in STATES}
        if self.state_counts != expected_counts or sum(self.state_counts.values()) != self.transition_count:
            raise ValidationError("registry history state counts are not conserved")
        if self.start_registry_address != self.snapshots[0].registry_address or self.end_registry_address != self.snapshots[-1].registry_address:
            raise ValidationError("registry history endpoints are invalid")
        if self.accepted != all(item.accepted for item in self.snapshots):
            raise ValidationError("registry history acceptance is not derived from snapshots")
        _bool(self.accepted, "registry history accepted")
        _address(self.start_registry_address, "registry history start address", registry_model.REGISTRY_PREFIX)
        _address(self.end_registry_address, "registry history end address", registry_model.REGISTRY_PREFIX)
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "registry history content address")
        else:
            _address(self.content_address, "registry history content address", HISTORY_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_history(self) != self.content_address):
            raise ValidationError("registry history address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"history_id": self.history_id, "version": self.version, "boundary": self.boundary, "snapshot_count": self.snapshot_count, "transition_count": self.transition_count, "start_registry_address": self.start_registry_address, "end_registry_address": self.end_registry_address, "snapshots": tuple(item.to_dict() for item in self.snapshots), "transitions": tuple(item.to_dict() for item in self.transitions), "state_counts": self.state_counts, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("history_id", "version", "boundary", "snapshot_count", "transition_count", "start_registry_address", "end_registry_address", "state_counts", "accepted", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistory:
        value = _mapping(value, "registry history")
        _strict(value, {"history_id", "version", "boundary", "snapshot_count", "transition_count", "start_registry_address", "end_registry_address", "snapshots", "transitions", "state_counts", "accepted", "content_address"}, "registry history")
        snapshots = tuple(RegistryHistorySnapshot.from_mapping(item) for item in _sequence(value["snapshots"], "registry history snapshots", MAX_SNAPSHOTS))
        transitions = tuple(RegistryHistoryTransition.from_mapping(item) for item in _sequence(value["transitions"], "registry history transitions", MAX_TRANSITIONS))
        result = cls(value["history_id"], snapshots, transitions, value["content_address"])
        if result.version != value["version"] or result.boundary != value["boundary"] or result.snapshot_count != value["snapshot_count"] or result.transition_count != value["transition_count"] or result.start_registry_address != value["start_registry_address"] or result.end_registry_address != value["end_registry_address"] or result.state_counts != value["state_counts"] or result.accepted != value["accepted"]:
            raise ValidationError("registry history derived fields are not conserved")
        return result


def address_history(value: RegistryHistory) -> str:
    if not isinstance(value, RegistryHistory):
        raise ValidationError("registry history address requires a typed history")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=HISTORY_PREFIX)


def build_history(registries: Sequence[registry_model.ObservatoryArchiveRegistry], *, history_id: str = DEFAULT_HISTORY_ID) -> RegistryHistory:
    if isinstance(registries, (str, bytes)):
        raise ValidationError("registry history requires a sequence of registries")
    registries = tuple(registries)
    if not 1 <= len(registries) <= MAX_SNAPSHOTS:
        raise ValidationError("registry history snapshot count is outside its bound")
    if any(not isinstance(value, registry_model.ObservatoryArchiveRegistry) for value in registries):
        raise ValidationError("registry history requires typed registries")
    for value in registries:
        registry_model.verify_registry(value)
    snapshots = tuple(RegistryHistorySnapshot.from_registry(value, ordinal) for ordinal, value in enumerate(registries, 1))
    diffs = tuple(diff_model.build_diff(registries[index], registries[index + 1], diff_id=f"{history_id}:transition:{index + 1}") for index in range(len(registries) - 1))
    transitions = tuple(RegistryHistoryTransition.from_diff(value, index) for index, value in enumerate(diffs, 1))
    provisional = RegistryHistory(history_id, snapshots, transitions, "pending:history")
    return RegistryHistory(history_id, snapshots, transitions, address_history(provisional))


def build_history_from_directories(directories: Sequence[str | Path], *, history_id: str = DEFAULT_HISTORY_ID) -> RegistryHistory:
    if isinstance(directories, (str, bytes)):
        raise ValidationError("registry history directories require a sequence")
    directories = tuple(directories)
    return build_history(tuple(registry_model.load_registry(directory) for directory in directories), history_id=history_id)


def verify_history(value: RegistryHistory) -> RegistryHistory:
    if not isinstance(value, RegistryHistory):
        raise ValidationError("registry history verification requires a typed history")
    value._validate()
    return value


def history_from_mapping(value: Mapping[str, Any]) -> RegistryHistory:
    return RegistryHistory.from_mapping(value)


def history_json(value: RegistryHistory) -> str:
    verify_history(value)
    return canonical_json(value.to_dict())


def _history_payload(value: RegistryHistory) -> dict[str, bytes]:
    verify_history(value)
    payload = {
        HISTORY_NAME: canonical_bytes(value.to_dict()),
        SNAPSHOTS_NAME: canonical_bytes({"history_id": value.history_id, "version": VERSION, "boundary": BOUNDARY, "snapshots": tuple(item.to_dict() for item in value.snapshots)}),
        TRANSITIONS_NAME: canonical_bytes({"history_id": value.history_id, "version": VERSION, "boundary": BOUNDARY, "transitions": tuple(item.to_dict() for item in value.transitions)}),
    }
    manifest = {"history_id": value.history_id, "version": VERSION, "boundary": BOUNDARY, "history_address": value.content_address, "snapshot_count": value.snapshot_count, "transition_count": value.transition_count, "artifact_count": len(payload), "files": tuple(payload), "artifacts": tuple({"name": name, "size": len(payload[name]), "hash": hash_bytes(payload[name], prefix=HISTORY_PREFIX + "-artifact")} for name in payload)}
    manifest["manifest_address"] = content_hash(manifest | {"manifest_address": None}, prefix=MANIFEST_PREFIX)
    payload[MANIFEST_NAME] = canonical_bytes(manifest)
    return {name: payload[name] for name in FILES}


def history_bytes(value: RegistryHistory) -> Mapping[str, bytes]:
    return dict(_history_payload(value))


def history_manifest_json(value: RegistryHistory) -> str:
    return _history_payload(value)[MANIFEST_NAME].decode("utf-8")


def _write_atomic_directory(destination: Path, payload: Mapping[str, bytes], *, overwrite: bool) -> Path:
    if destination.exists():
        if not overwrite:
            raise ValidationError("registry history destination exists; explicit overwrite is required")
        if destination.is_symlink() or not destination.is_dir() or {item.name for item in destination.iterdir()} != set(FILES) or any(item.is_symlink() or not item.is_file() for item in destination.iterdir()):
            raise ValidationError("registry history destination is not an exact compatible directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".gnd-observatory-history-", dir=str(destination.parent)))
    try:
        for name in FILES:
            (temporary / name).write_bytes(payload[name])
        if destination.exists():
            shutil.rmtree(destination)
        temporary.replace(destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def write_history(value: RegistryHistory, destination: str | Path, *, overwrite: bool = False) -> Path:
    return _write_atomic_directory(Path(destination), _history_payload(value), overwrite=overwrite)


def _read_directory(source: str | Path) -> dict[str, bytes]:
    directory = Path(source)
    if directory.is_symlink() or not directory.is_dir():
        raise ValidationError("registry history input must be a regular directory")
    if {item.name for item in directory.iterdir()} != set(FILES) or any(item.is_symlink() or not item.is_file() for item in directory.iterdir()):
        raise ValidationError("registry history directory member set is invalid")
    return {name: (directory / name).read_bytes() for name in FILES}


def load_history(source: str | Path) -> RegistryHistory:
    payload = _read_directory(source)
    try:
        documents = {name: json.loads(payload[name].decode("utf-8")) for name in FILES}
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("registry history contains invalid JSON") from error
    if any(canonical_bytes(documents[name]) != payload[name] for name in FILES):
        raise ValidationError("registry history artifacts are not canonical")
    value = RegistryHistory.from_mapping(documents[HISTORY_NAME])
    expected = _history_payload(value)
    if any(expected[name] != payload[name] for name in FILES):
        raise ValidationError("registry history package linkage or artifact receipt is invalid")
    snapshot_document = {"history_id": value.history_id, "version": VERSION, "boundary": BOUNDARY, "snapshots": tuple(item.to_dict() for item in value.snapshots)}
    transition_document = {"history_id": value.history_id, "version": VERSION, "boundary": BOUNDARY, "transitions": tuple(item.to_dict() for item in value.transitions)}
    if canonical_bytes(documents[SNAPSHOTS_NAME]) != canonical_bytes(snapshot_document) or canonical_bytes(documents[TRANSITIONS_NAME]) != canonical_bytes(transition_document):
        raise ValidationError("registry history projection documents are not linked")
    return value


def history_csv(value: RegistryHistory) -> str:
    verify_history(value)
    fields = ("ordinal", "registry_id", "registry_address", "state", "accepted", "release_ready", "entry_count", "verification_address", "snapshot_address")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for snapshot in value.snapshots:
        writer.writerow({field: snapshot.to_dict()[field] for field in fields})
    return output.getvalue()


def render_markdown(value: RegistryHistory) -> str:
    verify_history(value)
    lines = ["# Assurance History Observatory Archive Registry History", "", f"- History: `{value.history_id}`", f"- Snapshots: `{value.snapshot_count}`", f"- Transitions: `{value.transition_count}`", f"- Accepted: `{str(value.accepted).lower()}`", f"- Content address: `{value.content_address}`", "", "## Snapshots", "", "| Ordinal | Registry | State | Accepted | Release ready | Entries | Snapshot address |", "| ---: | --- | --- | --- | --- | ---: | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.registry_id}` | `{item.state}` | `{str(item.accepted).lower()}` | `{str(item.release_ready).lower()}` | {item.entry_count} | `{item.snapshot_address}` |" for item in value.snapshots)
    lines.extend(("", "## Transitions", "", "| Ordinal | State | Items | Added | Removed | Changed | Unchanged | Diff address |", "| ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |"))
    lines.extend(f"| {item.ordinal} | `{item.state}` | {item.item_count} | {item.added_count} | {item.removed_count} | {item.changed_count} | {item.unchanged_count} | `{item.diff_address}` |" for item in value.transitions)
    return "\n".join(lines) + "\n"


def snapshot_schema() -> dict[str, Any]:
    fields = {"ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_SNAPSHOTS}, "registry_id": {"type": "string"}, "registry_address": {"type": "string"}, "state": {"type": "string", "enum": [item.value for item in registry_model.RegistryState]}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "entry_count": {"type": "integer", "minimum": 0, "maximum": registry_model.MAX_ENTRIES}, "metrics": {"type": "object", "additionalProperties": False, "required": list(registry_model.RegistryMetrics.FIELDS), "properties": {field: {"type": "integer", "minimum": 0} for field in registry_model.RegistryMetrics.FIELDS}}, "verification_address": {"type": "string"}, "snapshot_address": {"type": "string", "pattern": "^" + SNAPSHOT_PREFIX + ":"}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def transition_schema() -> dict[str, Any]:
    fields = {"ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_TRANSITIONS}, "baseline_ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_SNAPSHOTS}, "candidate_ordinal": {"type": "integer", "minimum": 2, "maximum": MAX_SNAPSHOTS}, "baseline_registry_address": {"type": "string"}, "candidate_registry_address": {"type": "string"}, "diff_address": {"type": "string"}, "state": {"type": "string", "enum": list(STATES)}, "item_count": {"type": "integer", "minimum": 0, "maximum": diff_model.MAX_DIFF_ITEMS}, "added_count": {"type": "integer", "minimum": 0, "maximum": diff_model.MAX_DIFF_ITEMS}, "removed_count": {"type": "integer", "minimum": 0, "maximum": diff_model.MAX_DIFF_ITEMS}, "changed_count": {"type": "integer", "minimum": 0, "maximum": diff_model.MAX_DIFF_ITEMS}, "unchanged_count": {"type": "integer", "minimum": 0, "maximum": diff_model.MAX_DIFF_ITEMS}, "registry_changed_fields": {"type": "array", "maxItems": len(diff_model.REGISTRY_FIELDS), "items": {"type": "string", "enum": list(diff_model.REGISTRY_FIELDS)}}, "transition_address": {"type": "string", "pattern": "^" + TRANSITION_PREFIX + ":"}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def history_schema() -> dict[str, Any]:
    fields = {"history_id": {"type": "string"}, "version": {"const": VERSION, "type": "string"}, "boundary": {"const": BOUNDARY, "type": "string"}, "snapshot_count": {"type": "integer", "minimum": 1, "maximum": MAX_SNAPSHOTS}, "transition_count": {"type": "integer", "minimum": 0, "maximum": MAX_TRANSITIONS}, "start_registry_address": {"type": "string"}, "end_registry_address": {"type": "string"}, "snapshots": {"type": "array", "minItems": 1, "maxItems": MAX_SNAPSHOTS, "items": snapshot_schema()}, "transitions": {"type": "array", "maxItems": MAX_TRANSITIONS, "items": transition_schema()}, "state_counts": {"type": "object", "additionalProperties": False, "required": list(STATES), "properties": {state: {"type": "integer", "minimum": 0, "maximum": MAX_TRANSITIONS} for state in STATES}}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + HISTORY_PREFIX + ":"}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "files": FILES, "limits": {"max_snapshots": MAX_SNAPSHOTS, "max_transitions": MAX_TRANSITIONS, "max_diff_items_per_transition": diff_model.MAX_DIFF_ITEMS}, "states": STATES, "features": ("ordered verified registry snapshots", "adjacent deterministic diff summaries", "state-count conservation", "endpoint and ordinal linkage", "exact four-file persistence", "atomic writes", "canonical artifact receipts", "JSON CSV and Markdown exports", "path-free public output"), "schemas": ("snapshot", "transition", "history")}


__all__ = [
    "BOUNDARY",
    "DEFAULT_HISTORY_ID",
    "FILES",
    "HISTORY_NAME",
    "HISTORY_PREFIX",
    "MANIFEST_NAME",
    "MANIFEST_PREFIX",
    "MAX_SNAPSHOTS",
    "MAX_TRANSITIONS",
    "SNAPSHOTS_NAME",
    "SNAPSHOT_PREFIX",
    "STATES",
    "TRANSITIONS_NAME",
    "TRANSITION_PREFIX",
    "VERSION",
    "RegistryHistory",
    "RegistryHistorySnapshot",
    "RegistryHistoryTransition",
    "address_history",
    "address_snapshot",
    "address_transition",
    "build_history",
    "build_history_from_directories",
    "capabilities",
    "history_bytes",
    "history_csv",
    "history_from_mapping",
    "history_json",
    "history_manifest_json",
    "history_schema",
    "load_history",
    "render_markdown",
    "snapshot_schema",
    "transition_schema",
    "verify_history",
    "write_history",
]
