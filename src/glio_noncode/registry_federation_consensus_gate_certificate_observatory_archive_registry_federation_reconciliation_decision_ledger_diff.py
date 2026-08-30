"""Content-addressed transitions between reconciliation decision ledgers."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import (
    registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_decision_ledger as ledger_model,
)
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = ledger_model.VERSION + "-diff-v1"
BOUNDARY = ledger_model.BOUNDARY + "_diff"
DIFF_PREFIX = ledger_model.LEDGER_PREFIX + "-diff"
ITEM_PREFIX = DIFF_PREFIX + "-item"
DEFAULT_DIFF_ID = "consensus-certificate-observatory-archive-registry-federation-reconciliation-decision-ledger-diff"
MAX_ITEMS = ledger_model.MAX_DECISIONS * 2
CHANGES = ("added", "removed", "unchanged", "changed")
CHANGED_FIELDS = ("operation", "disposition", "status", "note", "evidence_addresses")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
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


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
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
    return ledger_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffItem:
    """One operation-level transition classification."""

    FIELDS = (
        "ordinal",
        "operation_address",
        "peer_id",
        "entry_id",
        "package_id",
        "action",
        "priority",
        "left_disposition",
        "right_disposition",
        "left_status",
        "right_status",
        "left_note",
        "right_note",
        "change",
        "changed_fields",
        "evidence_addresses",
        "content_address",
    )

    def __init__(self, ordinal: int, operation_address: str, peer_id: str, entry_id: str, package_id: str, action: str, priority: str, left_disposition: str, right_disposition: str, left_status: str, right_status: str, left_note: str, right_note: str, change: str, changed_fields: Sequence[str], evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "ledger diff item ordinal", MAX_ITEMS, positive=True)
        self.operation_address = _address(operation_address, "ledger diff operation address", ledger_model.plan_model.OPERATION_PREFIX)
        self.peer_id = _label(peer_id, "ledger diff peer ID")
        self.entry_id = _label(entry_id, "ledger diff entry ID")
        self.package_id = _label(package_id, "ledger diff package ID", required=False)
        self.action = _label(action, "ledger diff action", required=False)
        self.priority = _label(priority, "ledger diff priority", required=False)
        self.left_disposition = _label(left_disposition, "ledger diff left disposition", required=False)
        self.right_disposition = _label(right_disposition, "ledger diff right disposition", required=False)
        self.left_status = _label(left_status, "ledger diff left status", required=False)
        self.right_status = _label(right_status, "ledger diff right status", required=False)
        self.left_note = _text(left_note, "ledger diff left note", 2048, required=False)
        self.right_note = _text(right_note, "ledger diff right note", 2048, required=False)
        self.change = _label(change, "ledger diff change")
        self.changed_fields = tuple(_label(item, "ledger diff changed field") for item in _sequence(changed_fields, "ledger diff changed fields", len(CHANGED_FIELDS)))
        self.evidence_addresses = tuple(_text(item, "ledger diff evidence address", 2048) for item in _sequence(evidence_addresses, "ledger diff evidence", 8))
        self.content_address = _address(content_address, "ledger diff item address", ITEM_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "ledger diff item address")
        self._validate()

    def _validate(self) -> None:
        if self.change not in CHANGES or any(item not in CHANGED_FIELDS for item in self.changed_fields) or len(set(self.changed_fields)) != len(self.changed_fields) or not self.evidence_addresses:
            raise ValidationError("ledger diff item vocabulary is invalid")
        if self.change == "added" and (self.left_disposition or self.left_status or self.left_note or not self.right_disposition or self.changed_fields != ("operation",)):
            raise ValidationError("added ledger diff item is not conserved")
        if self.change == "removed" and (not self.left_disposition or not self.left_status or self.right_disposition or self.right_status or self.right_note or self.changed_fields != ("operation",)):
            raise ValidationError("removed ledger diff item is not conserved")
        if self.change == "unchanged" and (not self.left_disposition or self.left_disposition != self.right_disposition or self.left_status != self.right_status or self.left_note != self.right_note or self.changed_fields):
            raise ValidationError("unchanged ledger diff item is not conserved")
        if self.change == "changed" and (not self.left_disposition or not self.right_disposition or not self.changed_fields or (self.left_disposition == self.right_disposition and self.left_status == self.right_status and self.left_note == self.right_note and self.evidence_addresses == ())):
            raise ValidationError("changed ledger diff item is not conserved")
        if not _public(self.to_dict()):
            raise ValidationError("ledger diff item crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_item(self) != self.content_address:
            raise ValidationError("ledger diff item address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffItem:
        value = _mapping(value, "ledger diff item")
        _strict(value, set(cls.FIELDS), "ledger diff item")
        return cls(*(value[field] for field in cls.FIELDS))


def address_item(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffItem) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ITEM_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiff:
    """A complete deterministic diff between two decision ledgers."""

    FIELDS = (
        "diff_id",
        "version",
        "boundary",
        "left_ledger_id",
        "left_ledger_address",
        "right_ledger_id",
        "right_ledger_address",
        "left_plan_address",
        "right_plan_address",
        "items",
        "item_count",
        "added_count",
        "removed_count",
        "changed_count",
        "unchanged_count",
        "left_accepted",
        "right_accepted",
        "left_release_ready",
        "right_release_ready",
        "content_address",
    )

    def __init__(self, diff_id: str, version: str, boundary: str, left_ledger_id: str, left_ledger_address: str, right_ledger_id: str, right_ledger_address: str, left_plan_address: str, right_plan_address: str, items: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffItem], item_count: int, added_count: int, removed_count: int, changed_count: int, unchanged_count: int, left_accepted: bool, right_accepted: bool, left_release_ready: bool, right_release_ready: bool, content_address: str) -> None:
        self.diff_id = _label(diff_id, "ledger diff ID")
        self.version = _text(version, "ledger diff version")
        self.boundary = _text(boundary, "ledger diff boundary", 512)
        self.left_ledger_id = _label(left_ledger_id, "ledger diff left ledger ID")
        self.left_ledger_address = _address(left_ledger_address, "ledger diff left ledger address", ledger_model.LEDGER_PREFIX)
        self.right_ledger_id = _label(right_ledger_id, "ledger diff right ledger ID")
        self.right_ledger_address = _address(right_ledger_address, "ledger diff right ledger address", ledger_model.LEDGER_PREFIX)
        self.left_plan_address = _address(left_plan_address, "ledger diff left plan address", ledger_model.plan_model.PLAN_PREFIX)
        self.right_plan_address = _address(right_plan_address, "ledger diff right plan address", ledger_model.plan_model.PLAN_PREFIX)
        self.items = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffItem) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffItem.from_mapping(item) for item in _sequence(items, "ledger diff items", MAX_ITEMS))
        self.item_count = _count(item_count, "ledger diff item count", MAX_ITEMS, positive=True)
        self.added_count = _count(added_count, "ledger diff added count", self.item_count)
        self.removed_count = _count(removed_count, "ledger diff removed count", self.item_count)
        self.changed_count = _count(changed_count, "ledger diff changed count", self.item_count)
        self.unchanged_count = _count(unchanged_count, "ledger diff unchanged count", self.item_count)
        self.left_accepted = _bool(left_accepted, "ledger diff left acceptance")
        self.right_accepted = _bool(right_accepted, "ledger diff right acceptance")
        self.left_release_ready = _bool(left_release_ready, "ledger diff left release readiness")
        self.right_release_ready = _bool(right_release_ready, "ledger diff right release readiness")
        self.content_address = _address(content_address, "ledger diff address", DIFF_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "ledger diff address")
        self._validate()

    def _validate(self) -> None:
        if self.item_count != len(self.items) or self.item_count != self.added_count + self.removed_count + self.changed_count + self.unchanged_count:
            raise ValidationError("ledger diff counts do not replay")
        if tuple(item.ordinal for item in self.items) != tuple(range(1, self.item_count + 1)) or len({item.operation_address for item in self.items}) != self.item_count:
            raise ValidationError("ledger diff items are not canonical")
        if (self.added_count, self.removed_count, self.changed_count, self.unchanged_count) != tuple(sum(item.change == change for item in self.items) for change in ("added", "removed", "changed", "unchanged")):
            raise ValidationError("ledger diff classification counters do not replay")
        if self.left_ledger_address == self.right_ledger_address:
            if self.changed_count or self.added_count or self.removed_count:
                raise ValidationError("identical ledgers cannot have changed diff items")
        if not _public(self.to_dict()):
            raise ValidationError("ledger diff crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_diff(self) != self.content_address:
            raise ValidationError("ledger diff address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_id": self.diff_id, "version": self.version, "boundary": self.boundary, "left_ledger_id": self.left_ledger_id, "left_ledger_address": self.left_ledger_address, "right_ledger_id": self.right_ledger_id, "right_ledger_address": self.right_ledger_address, "left_plan_address": self.left_plan_address, "right_plan_address": self.right_plan_address, "items": tuple(item.to_dict() for item in self.items), "item_count": self.item_count, "added_count": self.added_count, "removed_count": self.removed_count, "changed_count": self.changed_count, "unchanged_count": self.unchanged_count, "left_accepted": self.left_accepted, "right_accepted": self.right_accepted, "left_release_ready": self.left_release_ready, "right_release_ready": self.right_release_ready, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "items"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiff:
        value = _mapping(value, "ledger diff")
        _strict(value, set(cls.FIELDS), "ledger diff")
        items = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffItem.from_mapping(item) for item in _sequence(value["items"], "ledger diff items", MAX_ITEMS))
        return cls(value["diff_id"], value["version"], value["boundary"], value["left_ledger_id"], value["left_ledger_address"], value["right_ledger_id"], value["right_ledger_address"], value["left_plan_address"], value["right_plan_address"], items, value["item_count"], value["added_count"], value["removed_count"], value["changed_count"], value["unchanged_count"], value["left_accepted"], value["right_accepted"], value["left_release_ready"], value["right_release_ready"], value["content_address"])


def address_diff(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiff) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_PREFIX)


def _item(ordinal: int, left: ledger_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecision | None, right: ledger_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecision | None, left_ledger: ledger_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedger, right_ledger: ledger_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedger) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffItem:
    current = right or left
    if current is None:
        raise ValidationError("ledger diff item requires a side")
    if left is None:
        change, changed = "added", ("operation",)
    elif right is None:
        change, changed = "removed", ("operation",)
    else:
        changed = tuple(field for field in CHANGED_FIELDS if field != "operation" and getattr(left, field) != getattr(right, field))
        change = "unchanged" if not changed else "changed"
    body = {"ordinal": ordinal, "operation_address": current.operation_address, "peer_id": current.peer_id, "entry_id": current.entry_id, "package_id": current.package_id, "action": current.action, "priority": current.priority, "left_disposition": left.disposition if left else "", "right_disposition": right.disposition if right else "", "left_status": left.status if left else "", "right_status": right.status if right else "", "left_note": left.note if left else "", "right_note": right.note if right else "", "change": change, "changed_fields": changed, "evidence_addresses": (left_ledger.content_address, right_ledger.content_address, current.operation_address),}
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffItem(**body, content_address=ITEM_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffItem(**body, content_address=address_item(provisional))


def build_diff(left: ledger_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedger, right: ledger_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedger, *, diff_id: str = DEFAULT_DIFF_ID) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiff:
    left = ledger_model.verify_ledger(left)
    right = ledger_model.verify_ledger(right)
    left_by_address = {item.operation_address: item for item in left.decisions}
    right_by_address = {item.operation_address: item for item in right.decisions}
    addresses = tuple(sorted(set(left_by_address) | set(right_by_address)))
    items = tuple(_item(index, left_by_address.get(address), right_by_address.get(address), left, right) for index, address in enumerate(addresses, 1))
    counts = {change: sum(item.change == change for item in items) for change in CHANGES}
    body = {"diff_id": diff_id, "version": VERSION, "boundary": BOUNDARY, "left_ledger_id": left.ledger_id, "left_ledger_address": left.content_address, "right_ledger_id": right.ledger_id, "right_ledger_address": right.content_address, "left_plan_address": left.plan_address, "right_plan_address": right.plan_address, "items": items, "item_count": len(items), "added_count": counts["added"], "removed_count": counts["removed"], "changed_count": counts["changed"], "unchanged_count": counts["unchanged"], "left_accepted": left.accepted, "right_accepted": right.accepted, "left_release_ready": left.release_ready, "right_release_ready": right.release_ready}
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiff(**body, content_address=DIFF_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiff(**body, content_address=address_diff(provisional))


def diff_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiff:
    return verify_diff(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiff.from_mapping(value))


def verify_diff(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiff) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiff:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiff):
        raise ValidationError("ledger diff verification requires a typed diff")
    value._validate()
    if not value.content_address.endswith(":pending") and address_diff(value) != value.content_address:
        raise ValidationError("ledger diff address verification failed")
    return value


def diff_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiff) -> str:
    return canonical_json(verify_diff(value).to_dict())


def diff_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiff) -> str:
    value = verify_diff(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffItem.FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.items:
        row = item.to_dict()
        for field in ("changed_fields", "evidence_addresses"):
            row[field] = ",".join(row[field])
        writer.writerow(row)
    return stream.getvalue()


def render_diff_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiff) -> str:
    value = verify_diff(value)
    lines = ["# Archive Registry Federation Reconciliation Decision Ledger Diff", "", f"- Added: `{value.added_count}`", f"- Removed: `{value.removed_count}`", f"- Changed: `{value.changed_count}`", f"- Unchanged: `{value.unchanged_count}`", f"- Left release ready: `{value.left_release_ready}`", f"- Right release ready: `{value.right_release_ready}`", "", "| # | peer | entry | change | left | right | fields |", "| ---: | --- | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.peer_id}` | `{item.entry_id}` | `{item.change}` | `{item.left_disposition}` | `{item.right_disposition}` | `{','.join(item.changed_fields)}` |" for item in value.items)
    return "\n".join(lines) + "\n"


def item_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffItem.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "operation_address": {"type": "string"}, "peer_id": {"type": "string"}, "entry_id": {"type": "string"}, "package_id": {"type": "string"}, "action": {"type": "string"}, "priority": {"type": "string"}, "left_disposition": {"type": "string"}, "right_disposition": {"type": "string"}, "left_status": {"type": "string"}, "right_status": {"type": "string"}, "left_note": {"type": "string"}, "right_note": {"type": "string"}, "change": {"enum": list(CHANGES)}, "changed_fields": {"type": "array", "items": {"type": "string"}}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def diff_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiff.FIELDS), "properties": {"diff_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "left_ledger_id": {"type": "string"}, "left_ledger_address": {"type": "string"}, "right_ledger_id": {"type": "string"}, "right_ledger_address": {"type": "string"}, "left_plan_address": {"type": "string"}, "right_plan_address": {"type": "string"}, "items": {"type": "array", "items": item_schema()}, "item_count": {"type": "integer", "minimum": 1}, "added_count": {"type": "integer", "minimum": 0}, "removed_count": {"type": "integer", "minimum": 0}, "changed_count": {"type": "integer", "minimum": 0}, "unchanged_count": {"type": "integer", "minimum": 0}, "left_accepted": {"type": "boolean"}, "right_accepted": {"type": "boolean"}, "left_release_ready": {"type": "boolean"}, "right_release_ready": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "public": True, "bounded": True, "content_addressed": True, "operations": ("build_diff", "diff_from_mapping", "diff_json", "diff_csv", "render_diff_markdown", "verify_diff"), "changes": CHANGES, "changed_fields": CHANGED_FIELDS, "max_items": MAX_ITEMS}


__all__ = [
    "BOUNDARY",
    "CHANGES",
    "CHANGED_FIELDS",
    "DEFAULT_DIFF_ID",
    "DIFF_PREFIX",
    "ITEM_PREFIX",
    "MAX_ITEMS",
    "VERSION",
    "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiff",
    "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerDiffItem",
    "address_diff",
    "address_item",
    "build_diff",
    "capabilities",
    "diff_csv",
    "diff_from_mapping",
    "diff_json",
    "diff_schema",
    "item_schema",
    "render_diff_markdown",
    "verify_diff",
]
