"""Deterministic transition diffs for certificate-history observatories."""

# ruff: noqa: E501, I001

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory as observatory_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = observatory_model.VERSION + "-diff-v1"
BOUNDARY = observatory_model.BOUNDARY + "_diff"
DIFF_PREFIX = observatory_model.OBSERVATORY_PREFIX + "-diff"
ITEM_PREFIX = DIFF_PREFIX + "-item"
QUERY_PREFIX = DIFF_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESULT_PREFIX = QUERY_PREFIX + "-result"
MAX_TEXT = observatory_model.MAX_TEXT
MAX_ITEMS = observatory_model.MAX_OBSERVATIONS * 2
MAX_ROWS = MAX_ITEMS * 8 + 1
DIFF_ACTIONS = ("added", "removed", "changed", "unchanged")
DIFF_DIRECTIONS = ("unchanged", "improved", "regressed", "mixed")
RESOURCES = ("summary", "items", "added", "removed", "changed", "unchanged", "accepted-gain", "accepted-loss", "failures")
DEFAULT_RESOURCES = RESOURCES


def _text(value: Any, field: str, maximum: int = MAX_TEXT, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 192, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, optional: bool = False) -> str:
    value = _text(value, field, 512, required=not optional)
    if value and ("/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":"))):
        raise ValidationError(f"{field} has an unsupported address")
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
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _resources(value: Any, field: str) -> tuple[str, ...]:
    values = tuple(_label(item, field) for item in _sequence(value, field, len(RESOURCES)))
    if not values or len(values) != len(set(values)) or any(item not in RESOURCES for item in values):
        raise ValidationError(f"{field} contains unsupported resources")
    return tuple(item for item in RESOURCES if item in values)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    forbidden = {"agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "token", "user"}
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and key.lower() not in forbidden and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    if isinstance(value, str):
        lowered = value.lower()
        return all(marker not in lowered for marker in ("c:\\", "d:\\", "/users/", "/home/", "\\users\\", "\\home\\"))
    return value is None or isinstance(value, (bool, int, float))


def _optional_state(value: Any, field: str) -> str:
    value = _label(value, field, required=False)
    if value and value not in observatory_model.STATES:
        raise ValidationError(f"{field} is unsupported")
    return value


def _optional_decision(value: Any, field: str) -> str:
    value = _label(value, field, required=False)
    if value and value not in observatory_model.DECISIONS:
        raise ValidationError(f"{field} is unsupported")
    return value


class RegistryFederationConsensusGateCertificateObservatoryDiffItem:
    """One logical observation transition keyed by history and entry ordinal."""

    FIELDS = ("ordinal", "observation_key", "action", "left_observation_address", "right_observation_address", "certificate_id", "left_state", "right_state", "left_decision", "right_decision", "left_accepted", "right_accepted", "left_failed_count", "right_failed_count", "accepted_change", "failed_delta", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, observation_key: str, action: str, left_observation_address: str, right_observation_address: str, certificate_id: str, left_state: str, right_state: str, left_decision: str, right_decision: str, left_accepted: bool, right_accepted: bool, left_failed_count: int, right_failed_count: int, accepted_change: int, failed_delta: int, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "observatory diff item ordinal", MAX_ITEMS, positive=True)
        self.observation_key = _label(observation_key, "observatory diff observation key")
        if action not in DIFF_ACTIONS:
            raise ValidationError("observatory diff action is unsupported")
        self.action = action
        self.left_observation_address = _address(left_observation_address, "observatory diff left observation address", optional=True)
        self.right_observation_address = _address(right_observation_address, "observatory diff right observation address", optional=True)
        self.certificate_id = _label(certificate_id, "observatory diff certificate ID")
        self.left_state, self.right_state = _optional_state(left_state, "observatory diff left state"), _optional_state(right_state, "observatory diff right state")
        self.left_decision, self.right_decision = _optional_decision(left_decision, "observatory diff left decision"), _optional_decision(right_decision, "observatory diff right decision")
        self.left_accepted, self.right_accepted = _bool(left_accepted, "observatory diff left acceptance"), _bool(right_accepted, "observatory diff right acceptance")
        self.left_failed_count = _count(left_failed_count, "observatory diff left failures", 32)
        self.right_failed_count = _count(right_failed_count, "observatory diff right failures", 32)
        if not isinstance(accepted_change, int) or isinstance(accepted_change, bool) or abs(accepted_change) > 1 or not isinstance(failed_delta, int) or isinstance(failed_delta, bool) or abs(failed_delta) > 64:
            raise ValidationError("observatory diff delta is outside its bound")
        self.accepted_change = accepted_change
        self.failed_delta = failed_delta
        self.evidence_addresses = tuple(_address(item, "observatory diff evidence address") for item in _sequence(evidence_addresses, "observatory diff evidence addresses", 8))
        if len(self.evidence_addresses) != len(set(self.evidence_addresses)):
            raise ValidationError("observatory diff evidence addresses must be unique")
        expected_action = "added" if not self.left_observation_address and self.right_observation_address else "removed" if self.left_observation_address and not self.right_observation_address else "unchanged" if self.left_observation_address == self.right_observation_address else "changed"
        if action != expected_action or self.accepted_change != int(self.right_accepted) - int(self.left_accepted) or self.failed_delta != self.right_failed_count - self.left_failed_count:
            raise ValidationError("observatory diff item transition is not conserved")
        self.content_address = _address(content_address, "observatory diff item address", ITEM_PREFIX)
        if not self.content_address.endswith(":pending") and address_item(self) != self.content_address:
            raise ValidationError("observatory diff item address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("observatory diff item crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryDiffItem:
        value = _mapping(value, "observatory diff item")
        _strict(value, set(cls.FIELDS), "observatory diff item")
        return cls(*(value[field] for field in cls.FIELDS))


def address_item(value: RegistryFederationConsensusGateCertificateObservatoryDiffItem) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryDiffItem):
        raise ValidationError("observatory diff item address requires a typed item")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ITEM_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryDiff:
    """Acceptance-aware comparison of two observatory snapshots."""

    FIELDS = ("diff_id", "left_address", "right_address", "direction", "items", "item_count", "added_count", "removed_count", "changed_count", "unchanged_count", "left_observation_count", "right_observation_count", "left_accepted_count", "right_accepted_count", "accepted_delta", "left_withheld_count", "right_withheld_count", "withheld_delta", "left_failed_count", "right_failed_count", "failed_delta", "content_address")

    def __init__(self, diff_id: str, left_address: str, right_address: str, direction: str, items: Sequence[RegistryFederationConsensusGateCertificateObservatoryDiffItem], item_count: int, added_count: int, removed_count: int, changed_count: int, unchanged_count: int, left_observation_count: int, right_observation_count: int, left_accepted_count: int, right_accepted_count: int, accepted_delta: int, left_withheld_count: int, right_withheld_count: int, withheld_delta: int, left_failed_count: int, right_failed_count: int, failed_delta: int, content_address: str) -> None:
        self.diff_id = _label(diff_id, "observatory diff ID")
        self.left_address = _address(left_address, "observatory diff left address", observatory_model.OBSERVATORY_PREFIX)
        self.right_address = _address(right_address, "observatory diff right address", observatory_model.OBSERVATORY_PREFIX)
        if direction not in DIFF_DIRECTIONS:
            raise ValidationError("observatory diff direction is unsupported")
        self.direction = direction
        self.items = tuple(items)
        if len(self.items) > MAX_ITEMS or any(not isinstance(item, RegistryFederationConsensusGateCertificateObservatoryDiffItem) for item in self.items):
            raise ValidationError("observatory diff items are outside the bound")
        self.item_count = _count(item_count, "observatory diff item count", MAX_ITEMS, positive=True)
        self.added_count, self.removed_count = _count(added_count, "observatory diff added count", self.item_count), _count(removed_count, "observatory diff removed count", self.item_count)
        self.changed_count, self.unchanged_count = _count(changed_count, "observatory diff changed count", self.item_count), _count(unchanged_count, "observatory diff unchanged count", self.item_count)
        self.left_observation_count, self.right_observation_count = _count(left_observation_count, "observatory diff left observations", observatory_model.MAX_OBSERVATIONS), _count(right_observation_count, "observatory diff right observations", observatory_model.MAX_OBSERVATIONS)
        self.left_accepted_count, self.right_accepted_count = _count(left_accepted_count, "observatory diff left accepted", self.left_observation_count), _count(right_accepted_count, "observatory diff right accepted", self.right_observation_count)
        self.left_withheld_count, self.right_withheld_count = _count(left_withheld_count, "observatory diff left withheld", self.left_observation_count), _count(right_withheld_count, "observatory diff right withheld", self.right_observation_count)
        self.left_failed_count, self.right_failed_count = _count(left_failed_count, "observatory diff left failures", self.left_observation_count * 32), _count(right_failed_count, "observatory diff right failures", self.right_observation_count * 32)
        self.accepted_delta, self.withheld_delta, self.failed_delta = accepted_delta, withheld_delta, failed_delta
        for field, bound in (("accepted_delta", observatory_model.MAX_OBSERVATIONS), ("withheld_delta", observatory_model.MAX_OBSERVATIONS), ("failed_delta", observatory_model.MAX_OBSERVATIONS * 32)):
            number = getattr(self, field)
            if not isinstance(number, int) or isinstance(number, bool) or abs(number) > bound:
                raise ValidationError(f"observatory diff {field} is outside its bound")
        if len(self.items) != self.item_count or tuple(item.ordinal for item in self.items) != tuple(range(1, self.item_count + 1)) or self.added_count != sum(item.action == "added" for item in self.items) or self.removed_count != sum(item.action == "removed" for item in self.items) or self.changed_count != sum(item.action == "changed" for item in self.items) or self.unchanged_count != sum(item.action == "unchanged" for item in self.items):
            raise ValidationError("observatory diff item counters are not conserved")
        if self.accepted_delta != self.right_accepted_count - self.left_accepted_count or self.withheld_delta != self.right_withheld_count - self.left_withheld_count or self.failed_delta != self.right_failed_count - self.left_failed_count:
            raise ValidationError("observatory diff metric deltas are not conserved")
        if self.direction == "unchanged" and (self.changed_count or self.added_count or self.removed_count or self.accepted_delta or self.withheld_delta or self.failed_delta):
            raise ValidationError("unchanged observatory diff has changes")
        self.content_address = _address(content_address, "observatory diff address", DIFF_PREFIX)
        if not self.content_address.endswith(":pending") and address_diff(self) != self.content_address:
            raise ValidationError("observatory diff address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("observatory diff crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_id": self.diff_id, "left_address": self.left_address, "right_address": self.right_address, "direction": self.direction, "items": tuple(item.to_dict() for item in self.items), "item_count": self.item_count, "added_count": self.added_count, "removed_count": self.removed_count, "changed_count": self.changed_count, "unchanged_count": self.unchanged_count, "left_observation_count": self.left_observation_count, "right_observation_count": self.right_observation_count, "left_accepted_count": self.left_accepted_count, "right_accepted_count": self.right_accepted_count, "accepted_delta": self.accepted_delta, "left_withheld_count": self.left_withheld_count, "right_withheld_count": self.right_withheld_count, "withheld_delta": self.withheld_delta, "left_failed_count": self.left_failed_count, "right_failed_count": self.right_failed_count, "failed_delta": self.failed_delta, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key != "items"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryDiff:
        value = _mapping(value, "observatory diff")
        _strict(value, set(cls.FIELDS), "observatory diff")
        return cls(value["diff_id"], value["left_address"], value["right_address"], value["direction"], tuple(RegistryFederationConsensusGateCertificateObservatoryDiffItem.from_mapping(item) for item in value["items"]), *(value[field] for field in cls.FIELDS[5:]))


def address_diff(value: RegistryFederationConsensusGateCertificateObservatoryDiff) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryDiff):
        raise ValidationError("observatory diff address requires a typed diff")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_PREFIX)


def _key(item: observatory_model.RegistryFederationConsensusGateCertificateObservation) -> str:
    return f"{item.history_id}:{item.entry_ordinal}"


def _direction(left: observatory_model.RegistryFederationConsensusGateCertificateObservatory, right: observatory_model.RegistryFederationConsensusGateCertificateObservatory, changed: int, added: int, removed: int, accepted_delta: int, failed_delta: int) -> str:
    if not (changed or added or removed or accepted_delta or failed_delta):
        return "unchanged"
    if accepted_delta > 0 and failed_delta <= 0 and not removed:
        return "improved"
    if accepted_delta < 0 or failed_delta > 0 or removed:
        return "regressed"
    return "mixed"


def _item_from(ordinal: int, key: str, left: observatory_model.RegistryFederationConsensusGateCertificateObservation | None, right: observatory_model.RegistryFederationConsensusGateCertificateObservation | None) -> RegistryFederationConsensusGateCertificateObservatoryDiffItem:
    left_address = left.content_address if left else ""
    right_address = right.content_address if right else ""
    provisional = RegistryFederationConsensusGateCertificateObservatoryDiffItem(ordinal, key, "added" if left is None else "removed" if right is None else "changed" if left_address != right_address else "unchanged", left_address, right_address, (right or left).certificate_id, left.state if left else "", right.state if right else "", left.decision if left else "", right.decision if right else "", left.accepted if left else False, right.accepted if right else False, left.failed_count if left else 0, right.failed_count if right else 0, int(right.accepted if right else False) - int(left.accepted if left else False), (right.failed_count if right else 0) - (left.failed_count if left else 0), tuple(dict.fromkeys(((left.certificate_address, left.audit_address) if left else ()) + ((right.certificate_address, right.audit_address) if right else ()))), ITEM_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryDiffItem(provisional.ordinal, provisional.observation_key, provisional.action, provisional.left_observation_address, provisional.right_observation_address, provisional.certificate_id, provisional.left_state, provisional.right_state, provisional.left_decision, provisional.right_decision, provisional.left_accepted, provisional.right_accepted, provisional.left_failed_count, provisional.right_failed_count, provisional.accepted_change, provisional.failed_delta, provisional.evidence_addresses, address_item(provisional))


def build_diff(left: observatory_model.RegistryFederationConsensusGateCertificateObservatory, right: observatory_model.RegistryFederationConsensusGateCertificateObservatory, *, diff_id: str = "consensus-certificate-observatory-diff") -> RegistryFederationConsensusGateCertificateObservatoryDiff:
    left, right = observatory_model.verify_observatory(left), observatory_model.verify_observatory(right)
    left_map = {_key(item): item for item in left.observations}
    right_map = {_key(item): item for item in right.observations}
    keys = tuple(sorted(set(left_map) | set(right_map)))
    items = tuple(_item_from(ordinal, key, left_map.get(key), right_map.get(key)) for ordinal, key in enumerate(keys, start=1))
    provisional = RegistryFederationConsensusGateCertificateObservatoryDiff(diff_id, left.content_address, right.content_address, _direction(left, right, sum(item.action == "changed" for item in items), sum(item.action == "added" for item in items), sum(item.action == "removed" for item in items), right.accepted_count - left.accepted_count, right.total_failed_count - left.total_failed_count), items, len(items), sum(item.action == "added" for item in items), sum(item.action == "removed" for item in items), sum(item.action == "changed" for item in items), sum(item.action == "unchanged" for item in items), left.observation_count, right.observation_count, left.accepted_count, right.accepted_count, right.accepted_count - left.accepted_count, left.held_count, right.held_count, right.held_count - left.held_count, left.total_failed_count, right.total_failed_count, right.total_failed_count - left.total_failed_count, DIFF_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryDiff(provisional.diff_id, provisional.left_address, provisional.right_address, provisional.direction, provisional.items, provisional.item_count, provisional.added_count, provisional.removed_count, provisional.changed_count, provisional.unchanged_count, provisional.left_observation_count, provisional.right_observation_count, provisional.left_accepted_count, provisional.right_accepted_count, provisional.accepted_delta, provisional.left_withheld_count, provisional.right_withheld_count, provisional.withheld_delta, provisional.left_failed_count, provisional.right_failed_count, provisional.failed_delta, address_diff(provisional))


def diff_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryDiff:
    return verify_diff(RegistryFederationConsensusGateCertificateObservatoryDiff.from_mapping(value))


def verify_diff(value: RegistryFederationConsensusGateCertificateObservatoryDiff) -> RegistryFederationConsensusGateCertificateObservatoryDiff:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryDiff) or (not value.content_address.endswith(":pending") and address_diff(value) != value.content_address):
        raise ValidationError("observatory diff is not valid")
    return value


def diff_json(value: RegistryFederationConsensusGateCertificateObservatoryDiff) -> str:
    return canonical_json(verify_diff(value).to_dict())


def diff_csv(value: RegistryFederationConsensusGateCertificateObservatoryDiff) -> str:
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateCertificateObservatoryDiffItem.FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in verify_diff(value).items:
        row = item.to_dict()
        row["evidence_addresses"] = "|".join(item.evidence_addresses)
        writer.writerow(row)
    return stream.getvalue()


def render_diff_markdown(value: RegistryFederationConsensusGateCertificateObservatoryDiff) -> str:
    value = verify_diff(value)
    lines = ["# Certificate Observatory Diff", "", f"- Direction: `{value.direction}`", f"- Added: `{value.added_count}`", f"- Removed: `{value.removed_count}`", f"- Changed: `{value.changed_count}`", f"- Accepted delta: `{value.accepted_delta}`", f"- Failed-check delta: `{value.failed_delta}`", f"- Address: `{value.content_address}`", "", "| ordinal | key | action | left | right | accepted change | failed delta |", "| --- | --- | --- | --- | --- | --- | --- |"]
    lines.extend(f"| `{item.ordinal}` | `{item.observation_key}` | `{item.action}` | `{item.left_observation_address}` | `{item.right_observation_address}` | `{item.accepted_change}` | `{item.failed_delta}` |" for item in value.items)
    return "\n".join(lines) + "\n"


class RegistryFederationConsensusGateCertificateObservatoryDiffQuery:
    FIELDS = ("query_id", "diff_address", "resources", "observation_key", "action", "accepted_change", "offset", "limit", "content_address")

    def __init__(self, query_id: str, diff_address: str, resources: Sequence[str], observation_key: str, action: str, accepted_change: int | None, offset: int, limit: int, content_address: str) -> None:
        self.query_id = _label(query_id, "observatory diff query ID")
        self.diff_address = _address(diff_address, "observatory diff query address", DIFF_PREFIX)
        self.resources = _resources(resources, "observatory diff query resources")
        self.observation_key, self.action = _label(observation_key, "observatory diff query key", required=False), _label(action, "observatory diff query action", required=False)
        if self.action and self.action not in DIFF_ACTIONS:
            raise ValidationError("observatory diff query action is unsupported")
        if accepted_change is not None and (isinstance(accepted_change, bool) or not isinstance(accepted_change, int) or abs(accepted_change) > 1):
            raise ValidationError("observatory diff acceptance filter is unsupported")
        self.accepted_change = accepted_change
        self.offset, self.limit = _count(offset, "observatory diff query offset", MAX_ROWS), _count(limit, "observatory diff query limit", MAX_ROWS, positive=True)
        self.content_address = _address(content_address, "observatory diff query address", QUERY_PREFIX)
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("observatory diff query address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("observatory diff query crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryDiffQuery:
        value = _mapping(value, "observatory diff query")
        _strict(value, set(cls.FIELDS), "observatory diff query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: RegistryFederationConsensusGateCertificateObservatoryDiffQuery) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryDiffQueryRow:
    FIELDS = ("ordinal", "resource", "row_id", "item_ordinal", "observation_key", "action", "left_observation_address", "right_observation_address", "certificate_id", "accepted_change", "failed_delta", "content_address")

    def __init__(self, ordinal: int, resource: str, row_id: str, item_ordinal: int, observation_key: str, action: str, left_observation_address: str, right_observation_address: str, certificate_id: str, accepted_change: int, failed_delta: int, content_address: str) -> None:
        self.ordinal, self.item_ordinal = _count(ordinal, "observatory diff row ordinal", MAX_ROWS, positive=True), _count(item_ordinal, "observatory diff row item ordinal", MAX_ITEMS, positive=True)
        self.resource, self.row_id = _label(resource, "observatory diff row resource"), _label(row_id, "observatory diff row ID")
        if self.resource not in RESOURCES:
            raise ValidationError("observatory diff row resource is unsupported")
        self.observation_key, self.action = _label(observation_key, "observatory diff row key"), _label(action, "observatory diff row action")
        if self.action not in DIFF_ACTIONS:
            raise ValidationError("observatory diff row action is unsupported")
        self.left_observation_address, self.right_observation_address = _address(left_observation_address, "observatory diff row left address", optional=True), _address(right_observation_address, "observatory diff row right address", optional=True)
        self.certificate_id = _label(certificate_id, "observatory diff row certificate ID")
        self.accepted_change, self.failed_delta = accepted_change, failed_delta
        if not isinstance(accepted_change, int) or isinstance(accepted_change, bool) or abs(accepted_change) > 1 or not isinstance(failed_delta, int) or isinstance(failed_delta, bool) or abs(failed_delta) > 64:
            raise ValidationError("observatory diff row delta is outside its bound")
        self.content_address = _address(content_address, "observatory diff row address", ROW_PREFIX)
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("observatory diff row address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("observatory diff row crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}


def address_row(value: RegistryFederationConsensusGateCertificateObservatoryDiffQueryRow) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryDiffQueryResult:
    FIELDS = ("query", "diff_id", "rows", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "content_address")

    def __init__(self, query: RegistryFederationConsensusGateCertificateObservatoryDiffQuery, diff_id: str, rows: Sequence[RegistryFederationConsensusGateCertificateObservatoryDiffQueryRow], total_count: int, matched_count: int, returned_count: int, next_offset: int, truncated: bool, content_address: str) -> None:
        if not isinstance(query, RegistryFederationConsensusGateCertificateObservatoryDiffQuery):
            raise ValidationError("observatory diff result query must be typed")
        self.query, self.diff_id, self.rows = query, _label(diff_id, "observatory diff result ID"), tuple(rows)
        if len(self.rows) > MAX_ROWS or any(not isinstance(item, RegistryFederationConsensusGateCertificateObservatoryDiffQueryRow) for item in self.rows):
            raise ValidationError("observatory diff result rows are outside the bound")
        self.total_count, self.matched_count, self.returned_count = _count(total_count, "observatory diff total count", MAX_ROWS), _count(matched_count, "observatory diff matched count", total_count), _count(returned_count, "observatory diff returned count", matched_count)
        self.next_offset, self.truncated = _count(next_offset, "observatory diff next offset", MAX_ROWS), _bool(truncated, "observatory diff truncation")
        if len(self.rows) != self.returned_count or tuple(item.ordinal for item in self.rows) != tuple(range(query.offset + 1, query.offset + self.returned_count + 1)) or self.truncated != (self.next_offset > 0) or (not self.truncated and self.next_offset != 0):
            raise ValidationError("observatory diff pagination is not conserved")
        self.content_address = _address(content_address, "observatory diff result address", RESULT_PREFIX)
        if not self.content_address.endswith(":pending") and address_result(self) != self.content_address:
            raise ValidationError("observatory diff result address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("observatory diff result crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"query": self.query.to_dict(), "diff_id": self.diff_id, "rows": tuple(item.to_dict() for item in self.rows), "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "next_offset": self.next_offset, "truncated": self.truncated, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key not in {"query", "rows"}}


def address_result(value: RegistryFederationConsensusGateCertificateObservatoryDiffQueryResult) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RESULT_PREFIX)


def _all_rows(value: RegistryFederationConsensusGateCertificateObservatoryDiff, resources: Sequence[str]) -> tuple[RegistryFederationConsensusGateCertificateObservatoryDiffQueryRow, ...]:
    rows: list[RegistryFederationConsensusGateCertificateObservatoryDiffQueryRow] = []
    selected = value.items
    if "summary" in resources:
        rows.append(RegistryFederationConsensusGateCertificateObservatoryDiffQueryRow(len(rows) + 1, "summary", "summary", 1, "summary", "changed" if value.changed_count else "unchanged", value.left_address, value.right_address, "summary", value.accepted_delta, value.failed_delta, ROW_PREFIX + ":pending"))
    for resource, predicate in (("items", lambda item: True), ("added", lambda item: item.action == "added"), ("removed", lambda item: item.action == "removed"), ("changed", lambda item: item.action == "changed"), ("unchanged", lambda item: item.action == "unchanged"), ("accepted-gain", lambda item: item.accepted_change > 0), ("accepted-loss", lambda item: item.accepted_change < 0), ("failures", lambda item: item.failed_delta != 0)):
        if resource in resources:
            for item in filter(predicate, selected):
                rows.append(RegistryFederationConsensusGateCertificateObservatoryDiffQueryRow(len(rows) + 1, resource, f"{resource}-{item.ordinal}", item.ordinal, item.observation_key, item.action, item.left_observation_address, item.right_observation_address, item.certificate_id, item.accepted_change, item.failed_delta, ROW_PREFIX + ":pending"))
    return tuple(RegistryFederationConsensusGateCertificateObservatoryDiffQueryRow(item.ordinal, item.resource, item.row_id, item.item_ordinal, item.observation_key, item.action, item.left_observation_address, item.right_observation_address, item.certificate_id, item.accepted_change, item.failed_delta, address_row(item)) for item in rows)


def build_query(value: RegistryFederationConsensusGateCertificateObservatoryDiff, *, query_id: str = "consensus-certificate-observatory-diff-query", resources: Sequence[str] = DEFAULT_RESOURCES, observation_key: str = "", action: str = "", accepted_change: int | None = None, offset: int = 0, limit: int = 100) -> RegistryFederationConsensusGateCertificateObservatoryDiffQuery:
    value = verify_diff(value)
    provisional = RegistryFederationConsensusGateCertificateObservatoryDiffQuery(query_id, value.content_address, resources, observation_key, action, accepted_change, offset, limit, QUERY_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryDiffQuery(provisional.query_id, provisional.diff_address, provisional.resources, provisional.observation_key, provisional.action, provisional.accepted_change, provisional.offset, provisional.limit, address_query(provisional))


def query_diff(value: RegistryFederationConsensusGateCertificateObservatoryDiff, *, query_id: str = "consensus-certificate-observatory-diff-query", resources: Sequence[str] = DEFAULT_RESOURCES, observation_key: str = "", action: str = "", accepted_change: int | None = None, offset: int = 0, limit: int = 100) -> RegistryFederationConsensusGateCertificateObservatoryDiffQueryResult:
    value = verify_diff(value)
    query = build_query(value, query_id=query_id, resources=resources, observation_key=observation_key, action=action, accepted_change=accepted_change, offset=offset, limit=limit)
    rows = _all_rows(value, query.resources)
    matched = tuple(item for item in rows if (not query.observation_key or item.observation_key == query.observation_key) and (not query.action or item.action == query.action) and (query.accepted_change is None or item.accepted_change == query.accepted_change))
    page = matched[query.offset:query.offset + query.limit]
    truncated = query.offset + len(page) < len(matched)
    next_offset = query.offset + len(page) if truncated else 0
    typed = tuple(RegistryFederationConsensusGateCertificateObservatoryDiffQueryRow(query.offset + index, item.resource, item.row_id, item.item_ordinal, item.observation_key, item.action, item.left_observation_address, item.right_observation_address, item.certificate_id, item.accepted_change, item.failed_delta, ROW_PREFIX + ":pending") for index, item in enumerate(page, start=1))
    provisional = RegistryFederationConsensusGateCertificateObservatoryDiffQueryResult(query, value.diff_id, typed, len(rows), len(matched), len(typed), next_offset, truncated, RESULT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryDiffQueryResult(provisional.query, provisional.diff_id, provisional.rows, provisional.total_count, provisional.matched_count, provisional.returned_count, provisional.next_offset, provisional.truncated, address_result(provisional))


def query_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryDiffQueryResult:
    value = _mapping(value, "observatory diff result")
    _strict(value, set(RegistryFederationConsensusGateCertificateObservatoryDiffQueryResult.FIELDS), "observatory diff result")
    query = RegistryFederationConsensusGateCertificateObservatoryDiffQuery.from_mapping(value["query"]) if hasattr(RegistryFederationConsensusGateCertificateObservatoryDiffQuery, "from_mapping") else RegistryFederationConsensusGateCertificateObservatoryDiffQuery(*(value["query"][field] for field in RegistryFederationConsensusGateCertificateObservatoryDiffQuery.FIELDS))
    rows = tuple(RegistryFederationConsensusGateCertificateObservatoryDiffQueryRow(*(item[field] for field in RegistryFederationConsensusGateCertificateObservatoryDiffQueryRow.FIELDS)) for item in value["rows"])
    return verify_query_result(RegistryFederationConsensusGateCertificateObservatoryDiffQueryResult(query, value["diff_id"], rows, value["total_count"], value["matched_count"], value["returned_count"], value["next_offset"], value["truncated"], value["content_address"]))


def verify_query_result(value: RegistryFederationConsensusGateCertificateObservatoryDiffQueryResult) -> RegistryFederationConsensusGateCertificateObservatoryDiffQueryResult:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryDiffQueryResult) or (not value.content_address.endswith(":pending") and address_result(value) != value.content_address):
        raise ValidationError("observatory diff query result is not valid")
    return value


def query_json(value: RegistryFederationConsensusGateCertificateObservatoryDiffQueryResult) -> str:
    return canonical_json(verify_query_result(value).to_dict())


def query_csv(value: RegistryFederationConsensusGateCertificateObservatoryDiffQueryResult) -> str:
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateCertificateObservatoryDiffQueryRow.FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in verify_query_result(value).rows:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_query_markdown(value: RegistryFederationConsensusGateCertificateObservatoryDiffQueryResult) -> str:
    value = verify_query_result(value)
    lines = ["# Certificate Observatory Diff Query", "", f"- Diff: `{value.diff_id}`", f"- Matched: `{value.matched_count}`", f"- Returned: `{value.returned_count}`", f"- Address: `{value.content_address}`", "", "| resource | row | key | action | accepted change | failed delta |", "| --- | --- | --- | --- | --- | --- |"]
    lines.extend(f"| `{item.resource}` | `{item.row_id}` | `{item.observation_key}` | `{item.action}` | `{item.accepted_change}` | `{item.failed_delta}` |" for item in value.rows)
    return "\n".join(lines) + "\n"


def item_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryDiffItem.FIELDS), "properties": {field: {"type": "array", "items": {"type": "string"}} if field == "evidence_addresses" else {"type": "integer"} if field in {"ordinal", "left_failed_count", "right_failed_count", "accepted_change", "failed_delta"} else {"type": "boolean"} if field in {"left_accepted", "right_accepted"} else {"type": "string"} for field in RegistryFederationConsensusGateCertificateObservatoryDiffItem.FIELDS}}


def diff_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryDiff.FIELDS), "properties": {field: {"type": "array", "items": item_schema()} if field == "items" else {"type": "integer"} if field.endswith("count") or field.endswith("delta") else {"type": "string"} for field in RegistryFederationConsensusGateCertificateObservatoryDiff.FIELDS}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryDiffQuery.FIELDS), "properties": {field: {"type": ["integer", "null"]} if field == "accepted_change" else {"type": "array", "items": {"type": "string"}} if field == "resources" else {"type": "integer"} if field in {"offset", "limit"} else {"type": "string"} for field in RegistryFederationConsensusGateCertificateObservatoryDiffQuery.FIELDS}}


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryDiffQueryRow.FIELDS), "properties": {field: {"type": "integer"} if field in {"ordinal", "item_ordinal", "accepted_change", "failed_delta"} else {"type": "string"} for field in RegistryFederationConsensusGateCertificateObservatoryDiffQueryRow.FIELDS}}


def result_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryDiffQueryResult.FIELDS), "properties": {field: query_schema() if field == "query" else {"type": "array", "items": row_schema()} if field == "rows" else {"type": "boolean"} if field == "truncated" else {"type": "integer"} if field.endswith("count") or field == "next_offset" else {"type": "string"} for field in RegistryFederationConsensusGateCertificateObservatoryDiffQueryResult.FIELDS}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "diff_prefix": DIFF_PREFIX, "item_prefix": ITEM_PREFIX, "query_prefix": QUERY_PREFIX, "row_prefix": ROW_PREFIX, "result_prefix": RESULT_PREFIX, "actions": DIFF_ACTIONS, "directions": DIFF_DIRECTIONS, "resources": RESOURCES, "features": ("logical observation transitions", "acceptance-aware direction", "failed-check deltas", "bounded diff queries", "content-addressed diff rows", "JSON CSV and Markdown exports"), "schemas": ("item", "diff", "query", "row", "result")}


__all__ = ["BOUNDARY", "DEFAULT_RESOURCES", "DIFF_ACTIONS", "DIFF_DIRECTIONS", "DIFF_PREFIX", "ITEM_PREFIX", "MAX_ITEMS", "MAX_ROWS", "QUERY_PREFIX", "RESOURCES", "RESULT_PREFIX", "ROW_PREFIX", "RegistryFederationConsensusGateCertificateObservatoryDiff", "RegistryFederationConsensusGateCertificateObservatoryDiffItem", "RegistryFederationConsensusGateCertificateObservatoryDiffQuery", "RegistryFederationConsensusGateCertificateObservatoryDiffQueryResult", "RegistryFederationConsensusGateCertificateObservatoryDiffQueryRow", "VERSION", "address_diff", "address_item", "address_query", "address_result", "address_row", "build_diff", "build_query", "capabilities", "diff_csv", "diff_from_mapping", "diff_json", "diff_schema", "item_schema", "query_csv", "query_diff", "query_from_mapping", "query_json", "query_schema", "render_diff_markdown", "render_query_markdown", "result_schema", "row_schema", "verify_diff", "verify_query_result"]
