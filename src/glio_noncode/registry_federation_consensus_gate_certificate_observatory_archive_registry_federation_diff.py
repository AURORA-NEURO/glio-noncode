"""Deterministic diffs between archive-registry federation snapshots."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation as federation_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = federation_model.VERSION + "-diff-v1"
BOUNDARY = federation_model.BOUNDARY + "_diff"
DIFF_PREFIX = federation_model.FEDERATION_PREFIX + "-diff"
ITEM_PREFIX = DIFF_PREFIX + "-item"
ACTIONS = ("added", "removed", "changed", "resolved", "regressed", "unchanged")
MAX_ITEMS = federation_model.MAX_ENTRIES


def _text(value: Any, field: str, maximum: int = 2048, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 192, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = True) -> str:
    value = _text(value, field, 2048, required=required)
    if value and ("/" in value or "\\" in value or '"' in value or ":" not in value):
        raise ValidationError(f"{field} must be a public content address")
    if prefix is not None and value and not value.startswith(prefix + ":"):
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
    return federation_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffItem:
    FIELDS = ("ordinal", "entry_id", "package_id", "action", "baseline_state", "candidate_state", "baseline_archive_addresses", "candidate_archive_addresses", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, entry_id: str, package_id: str, action: str, baseline_state: str, candidate_state: str, baseline_archive_addresses: Sequence[str], candidate_archive_addresses: Sequence[str], evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "federation diff item ordinal", MAX_ITEMS)
        self.entry_id = _label(entry_id, "federation diff entry ID")
        self.package_id = _label(package_id, "federation diff package ID", required=False)
        self.action = _label(action, "federation diff action")
        self.baseline_state = _label(baseline_state, "federation diff baseline state", required=False)
        self.candidate_state = _label(candidate_state, "federation diff candidate state", required=False)
        self.baseline_archive_addresses = tuple(_address(item, "federation diff baseline archive address", federation_model.registry_model.archive_model.ARCHIVE_PREFIX) for item in _sequence(baseline_archive_addresses, "federation diff baseline addresses", federation_model.MAX_PEERS))
        self.candidate_archive_addresses = tuple(_address(item, "federation diff candidate archive address", federation_model.registry_model.archive_model.ARCHIVE_PREFIX) for item in _sequence(candidate_archive_addresses, "federation diff candidate addresses", federation_model.MAX_PEERS))
        self.evidence_addresses = tuple(_text(item, "federation diff evidence address", 2048) for item in _sequence(evidence_addresses, "federation diff evidence", federation_model.MAX_PEERS + 2))
        self.content_address = _address(content_address, "federation diff item address", ITEM_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "federation diff item address")
        self._validate()

    def _validate(self) -> None:
        if self.action not in ACTIONS or self.baseline_state not in ("", *federation_model.STATES) or self.candidate_state not in ("", *federation_model.STATES):
            raise ValidationError("federation diff item action or state is unsupported")
        if not self.evidence_addresses:
            raise ValidationError("federation diff item requires evidence")
        if not _public(self.to_dict()):
            raise ValidationError("federation diff item crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_item(self) != self.content_address:
            raise ValidationError("federation diff item address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffItem":
        value = _mapping(value, "federation diff item")
        _strict(value, set(cls.FIELDS), "federation diff item")
        return cls(*(value[field] for field in cls.FIELDS))


def address_item(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffItem) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ITEM_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiff:
    FIELDS = ("diff_id", "baseline_federation_address", "candidate_federation_address", "items", "item_count", "added_count", "removed_count", "changed_count", "resolved_count", "regressed_count", "unchanged_count", "content_address")

    def __init__(self, diff_id: str, baseline_federation_address: str, candidate_federation_address: str, items: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffItem], item_count: int, added_count: int, removed_count: int, changed_count: int, resolved_count: int, regressed_count: int, unchanged_count: int, content_address: str) -> None:
        self.diff_id = _label(diff_id, "federation diff ID")
        self.baseline_federation_address = _address(baseline_federation_address, "federation diff baseline address", federation_model.FEDERATION_PREFIX)
        self.candidate_federation_address = _address(candidate_federation_address, "federation diff candidate address", federation_model.FEDERATION_PREFIX)
        self.items = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffItem) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffItem.from_mapping(item) for item in _sequence(items, "federation diff items", MAX_ITEMS))
        self.item_count = _count(item_count, "federation diff item count", MAX_ITEMS)
        self.added_count = _count(added_count, "federation diff added count", self.item_count)
        self.removed_count = _count(removed_count, "federation diff removed count", self.item_count)
        self.changed_count = _count(changed_count, "federation diff changed count", self.item_count)
        self.resolved_count = _count(resolved_count, "federation diff resolved count", self.item_count)
        self.regressed_count = _count(regressed_count, "federation diff regressed count", self.item_count)
        self.unchanged_count = _count(unchanged_count, "federation diff unchanged count", self.item_count)
        self.content_address = _address(content_address, "federation diff address", DIFF_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "federation diff address")
        self._validate()

    def _validate(self) -> None:
        if self.item_count != len(self.items) or self.item_count != self.added_count + self.removed_count + self.changed_count + self.unchanged_count:
            raise ValidationError("federation diff counters are not conserved")
        if self.resolved_count > self.changed_count or self.regressed_count > self.changed_count:
            raise ValidationError("federation diff transition counters are invalid")
        if tuple(item.ordinal for item in self.items) != tuple(range(1, self.item_count + 1)) or tuple(item.entry_id for item in self.items) != tuple(sorted(item.entry_id for item in self.items)):
            raise ValidationError("federation diff items are not canonical")
        derived = {action: sum(item.action == action for item in self.items) for action in ACTIONS}
        if any(derived[action] != getattr(self, action + "_count") for action in ("added", "removed", "changed", "unchanged")):
            raise ValidationError("federation diff action counters do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("federation diff crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_diff(self) != self.content_address:
            raise ValidationError("federation diff address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_id": self.diff_id, "baseline_federation_address": self.baseline_federation_address, "candidate_federation_address": self.candidate_federation_address, "items": tuple(item.to_dict() for item in self.items), "item_count": self.item_count, "added_count": self.added_count, "removed_count": self.removed_count, "changed_count": self.changed_count, "resolved_count": self.resolved_count, "regressed_count": self.regressed_count, "unchanged_count": self.unchanged_count, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in ("diff_id", "baseline_federation_address", "candidate_federation_address", "item_count", "added_count", "removed_count", "changed_count", "resolved_count", "regressed_count", "unchanged_count", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiff":
        value = _mapping(value, "federation diff")
        _strict(value, set(cls.FIELDS), "federation diff")
        return cls(value["diff_id"], value["baseline_federation_address"], value["candidate_federation_address"], tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffItem.from_mapping(item) for item in _sequence(value["items"], "federation diff items", MAX_ITEMS)), value["item_count"], value["added_count"], value["removed_count"], value["changed_count"], value["resolved_count"], value["regressed_count"], value["unchanged_count"], value["content_address"])


def address_diff(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiff) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_PREFIX)


def _item(ordinal: int, entry_id: str, baseline: federation_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationObservation | None, candidate: federation_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationObservation | None) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffItem:
    left = baseline.state if baseline else ""
    right = candidate.state if candidate else ""
    if baseline is None:
        action = "added"
    elif candidate is None:
        action = "removed"
    elif left == right and baseline.observed_archive_addresses == candidate.observed_archive_addresses and baseline.observed_package_addresses == candidate.observed_package_addresses:
        action = "unchanged"
    elif left != "consistent" and right == "consistent":
        action = "resolved"
    elif left == "consistent" and right != "consistent":
        action = "regressed"
    else:
        action = "changed"
    selected = candidate or baseline
    body = {"ordinal": ordinal, "entry_id": entry_id, "package_id": selected.package_id if selected else "", "action": action, "baseline_state": left, "candidate_state": right, "baseline_archive_addresses": baseline.observed_archive_addresses if baseline else (), "candidate_archive_addresses": candidate.observed_archive_addresses if candidate else (), "evidence_addresses": tuple(item.content_address for item in (baseline, candidate) if item is not None)}
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffItem(**body, content_address=ITEM_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffItem(**body, content_address=address_item(provisional))


def build_diff(baseline: federation_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederation, candidate: federation_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederation, *, diff_id: str = "consensus-certificate-observatory-archive-registry-federation-diff") -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiff:
    baseline = federation_model.verify_federation(baseline)
    candidate = federation_model.verify_federation(candidate)
    entry_ids = sorted({item.entry_id for item in baseline.observations} | {item.entry_id for item in candidate.observations})
    if len(entry_ids) > MAX_ITEMS:
        raise ValidationError("federation diff exceeds the item bound")
    left = {item.entry_id: item for item in baseline.observations}
    right = {item.entry_id: item for item in candidate.observations}
    items = tuple(_item(index, entry_id, left.get(entry_id), right.get(entry_id)) for index, entry_id in enumerate(entry_ids, 1))
    counts = {action: sum(item.action == action for item in items) for action in ACTIONS}
    changed = counts["changed"] + counts["resolved"] + counts["regressed"]
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiff(diff_id, baseline.content_address, candidate.content_address, items, len(items), counts["added"], counts["removed"], changed, counts["resolved"], counts["regressed"], counts["unchanged"], DIFF_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiff(provisional.diff_id, provisional.baseline_federation_address, provisional.candidate_federation_address, provisional.items, provisional.item_count, provisional.added_count, provisional.removed_count, provisional.changed_count, provisional.resolved_count, provisional.regressed_count, provisional.unchanged_count, address_diff(provisional))


def diff_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiff:
    return verify_diff(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiff.from_mapping(value))


def verify_diff(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiff) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiff:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiff):
        raise ValidationError("federation diff verification requires a typed diff")
    value._validate()
    if not value.content_address.endswith(":pending") and address_diff(value) != value.content_address:
        raise ValidationError("federation diff address verification failed")
    return value


def diff_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiff) -> str:
    return canonical_json(verify_diff(value).to_dict())


def diff_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiff) -> str:
    value = verify_diff(value)
    fields = ("ordinal", "entry_id", "package_id", "action", "baseline_state", "candidate_state", "baseline_archive_addresses", "candidate_archive_addresses", "evidence_addresses", "content_address")
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in value.items:
        row = item.to_dict()
        for field in ("baseline_archive_addresses", "candidate_archive_addresses", "evidence_addresses"):
            row[field] = ",".join(row[field])
        writer.writerow(row)
    return stream.getvalue()


def render_diff_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiff) -> str:
    value = verify_diff(value)
    lines = ["# Archive Registry Federation Diff", "", f"- Added: `{value.added_count}`", f"- Removed: `{value.removed_count}`", f"- Changed: `{value.changed_count}`", f"- Resolved: `{value.resolved_count}`", f"- Regressed: `{value.regressed_count}`", "", "| # | entry | action | baseline | candidate |", "| ---: | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.entry_id}` | `{item.action}` | `{item.baseline_state}` | `{item.candidate_state}` |" for item in value.items)
    return "\n".join(lines) + "\n"


def item_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffItem.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "entry_id": {"type": "string"}, "package_id": {"type": "string"}, "action": {"enum": list(ACTIONS)}, "baseline_state": {"type": "string"}, "candidate_state": {"type": "string"}, "baseline_archive_addresses": {"type": "array", "items": {"type": "string"}}, "candidate_archive_addresses": {"type": "array", "items": {"type": "string"}}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def diff_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiff.FIELDS), "properties": {"diff_id": {"type": "string"}, "baseline_federation_address": {"type": "string"}, "candidate_federation_address": {"type": "string"}, "items": {"type": "array", "items": item_schema()}, "item_count": {"type": "integer", "minimum": 0}, "added_count": {"type": "integer", "minimum": 0}, "removed_count": {"type": "integer", "minimum": 0}, "changed_count": {"type": "integer", "minimum": 0}, "resolved_count": {"type": "integer", "minimum": 0}, "regressed_count": {"type": "integer", "minimum": 0}, "unchanged_count": {"type": "integer", "minimum": 0}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "public": True, "bounded": True, "operations": ("build_diff", "diff_from_mapping", "diff_json", "diff_csv", "render_diff_markdown", "verify_diff"), "actions": ACTIONS, "max_items": MAX_ITEMS}


__all__ = ["ACTIONS", "BOUNDARY", "DIFF_PREFIX", "ITEM_PREFIX", "VERSION", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiff", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffItem", "address_diff", "address_item", "build_diff", "capabilities", "diff_csv", "diff_from_mapping", "diff_json", "diff_schema", "item_schema", "render_diff_markdown", "verify_diff"]
