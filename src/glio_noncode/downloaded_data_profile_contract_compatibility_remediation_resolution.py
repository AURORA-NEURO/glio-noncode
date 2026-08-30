"""Value-free remediation resolutions for closing compatibility action plans."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_compatibility_remediation as remediation_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-compatibility-remediation-resolution-v1"
BOUNDARY = "public_downloaded_data_profile_contract_compatibility_remediation_resolution"
RESOLUTION_PREFIX = "glio-noncode-download-profile-contract-compatibility-remediation-resolution"
ENTRY_PREFIX = RESOLUTION_PREFIX + "-entry"
DEFAULT_RESOLUTION_ID = RESOLUTION_PREFIX
STATUSES = ("pending", "resolved", "waived", "rejected", "not_applicable")
STATES = ("clear", "review", "blocked")
DECISIONS = ("promote", "hold", "block")
ENTRY_FIELDS = (
    "ordinal",
    "action_address",
    "identity",
    "action",
    "priority",
    "required",
    "status",
    "evidence_addresses",
    "rationale",
    "content_address",
)
RESOLUTION_FIELDS = (
    "resolution_id",
    "version",
    "boundary",
    "plan_id",
    "plan_address",
    "plan",
    "entries",
    "resolution_count",
    "pending_count",
    "resolved_count",
    "waived_count",
    "rejected_count",
    "not_applicable_count",
    "required_open_count",
    "state",
    "decision",
    "accepted",
    "release_ready",
    "content_address",
)
MAX_ENTRIES = remediation_model.MAX_ACTIONS


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
    if "/" in value or "\\" in value or '"' in value or ":" not in value or (prefix is not None and not value.startswith(prefix + ":")):
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


def _addresses(value: Any, field: str) -> tuple[str, ...]:
    addresses = tuple(sorted({_address(item, field) for item in _sequence(value, field, 8)}))
    if not addresses:
        raise ValidationError(f"{field} must not be empty")
    return addresses


def address_entry(value: DownloadedDataProfileContractCompatibilityRemediationResolutionEntry) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionEntry):
        raise ValidationError("resolution entry address requires a typed entry")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ENTRY_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionEntry:
    """One value-free disposition for one planned remediation action."""

    FIELDS = ENTRY_FIELDS

    def __init__(self, ordinal: int, action_address: str, identity: str, action: str, priority: str, required: bool, status: str, evidence_addresses: Sequence[str], rationale: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "resolution entry ordinal", MAX_ENTRIES, positive=True)
        self.action_address = _address(action_address, "resolution entry action address", remediation_model.ACTION_PREFIX)
        self.identity = _text(identity, "resolution entry identity", 4096)
        self.action = _label(action, "resolution entry action")
        if self.action not in remediation_model.ACTION_KINDS:
            raise ValidationError("resolution entry action is unsupported")
        self.priority = _label(priority, "resolution entry priority")
        if self.priority not in remediation_model.PRIORITIES:
            raise ValidationError("resolution entry priority is unsupported")
        self.required = _bool(required, "resolution entry requiredness")
        self.status = _label(status, "resolution entry status")
        if self.status not in STATUSES:
            raise ValidationError("resolution entry status is unsupported")
        self.evidence_addresses = _addresses(evidence_addresses, "resolution entry evidence addresses")
        self.rationale = _text(rationale, "resolution entry rationale", 1024)
        self.content_address = _address(content_address, "resolution entry address", ENTRY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.required and self.status == "not_applicable":
            raise ValidationError("required remediation actions cannot be not applicable")
        if not self.required and self.status != "not_applicable":
            raise ValidationError("non-required remediation actions must be not applicable")
        if self.action == "none" and (self.required or self.status != "not_applicable"):
            raise ValidationError("none actions must be not applicable")
        if self.status == "pending" and not self.rationale:
            raise ValidationError("pending resolutions require rationale")
        if not _public(self.to_dict()):
            raise ValidationError("resolution entry crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_entry(self) != self.content_address:
            raise ValidationError("resolution entry address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionEntry:
        value = _mapping(value, "resolution entry")
        _strict(value, set(cls.FIELDS), "resolution entry")
        return cls(*(value[field] for field in cls.FIELDS))


class DownloadedDataProfileContractCompatibilityRemediationResolution:
    """A complete, addressed disposition ledger for one remediation plan."""

    FIELDS = RESOLUTION_FIELDS

    def __init__(self, resolution_id: str, version: str, boundary: str, plan_id: str, plan_address: str, plan: remediation_model.DownloadedDataProfileContractCompatibilityRemediationPlan | Mapping[str, Any], entries: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionEntry | Mapping[str, Any]], resolution_count: int, pending_count: int, resolved_count: int, waived_count: int, rejected_count: int, not_applicable_count: int, required_open_count: int, state: str, decision: str, accepted: bool, release_ready: bool, content_address: str) -> None:
        self.resolution_id = _label(resolution_id, "resolution ID")
        self.version = _text(version, "resolution version")
        self.boundary = _text(boundary, "resolution boundary", 512)
        self.plan_id = _label(plan_id, "resolution plan ID")
        self.plan_address = _address(plan_address, "resolution plan address", remediation_model.PLAN_PREFIX)
        self.plan = plan if isinstance(plan, remediation_model.DownloadedDataProfileContractCompatibilityRemediationPlan) else remediation_model.plan_from_mapping(plan)
        self.entries = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionEntry) else DownloadedDataProfileContractCompatibilityRemediationResolutionEntry.from_mapping(item) for item in _sequence(entries, "resolution entries", MAX_ENTRIES))
        self.resolution_count = _count(resolution_count, "resolution count", MAX_ENTRIES)
        self.pending_count = _count(pending_count, "pending resolution count", MAX_ENTRIES)
        self.resolved_count = _count(resolved_count, "resolved resolution count", MAX_ENTRIES)
        self.waived_count = _count(waived_count, "waived resolution count", MAX_ENTRIES)
        self.rejected_count = _count(rejected_count, "rejected resolution count", MAX_ENTRIES)
        self.not_applicable_count = _count(not_applicable_count, "not-applicable resolution count", MAX_ENTRIES)
        self.required_open_count = _count(required_open_count, "open resolution count", MAX_ENTRIES)
        self.state = _label(state, "resolution state")
        if self.state not in STATES:
            raise ValidationError("resolution state is unsupported")
        self.decision = _label(decision, "resolution decision")
        if self.decision not in DECISIONS:
            raise ValidationError("resolution decision is unsupported")
        self.accepted = _bool(accepted, "resolution acceptance")
        self.release_ready = _bool(release_ready, "resolution release readiness")
        self.content_address = _address(content_address, "resolution address", RESOLUTION_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("resolution version or boundary is not current")
        if (self.plan_id, self.plan_address) != (self.plan.plan_id, self.plan.content_address):
            raise ValidationError("resolution plan linkage does not replay")
        if len(self.entries) != self.resolution_count or tuple(item.ordinal for item in self.entries) != tuple(range(1, self.resolution_count + 1)):
            raise ValidationError("resolution entry order is not conserved")
        actions = self.plan.actions
        if len(actions) != len(self.entries) or tuple(item.action_address for item in self.entries) != tuple(item.content_address for item in actions):
            raise ValidationError("resolution entries do not conserve plan actions")
        if any((entry.identity, entry.action, entry.priority, entry.required) != (action.identity, action.action, action.priority, action.required) for entry, action in zip(self.entries, actions, strict=True)):
            raise ValidationError("resolution entry metadata does not replay")
        counts = tuple(sum(item.status == status for item in self.entries) for status in STATUSES)
        if counts != (self.pending_count, self.resolved_count, self.waived_count, self.rejected_count, self.not_applicable_count):
            raise ValidationError("resolution status counts do not replay")
        if self.required_open_count != sum(item.required and item.status != "resolved" for item in self.entries):
            raise ValidationError("resolution open count does not replay")
        expected_state = "blocked" if self.rejected_count else "review" if self.required_open_count else "clear"
        expected_decision = {"clear": "promote", "review": "hold", "blocked": "block"}[expected_state]
        if (self.state, self.decision, self.accepted, self.release_ready) != (expected_state, expected_decision, expected_state == "clear", expected_state == "clear"):
            raise ValidationError("resolution disposition does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("resolution crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_resolution(self) != self.content_address:
            raise ValidationError("resolution address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"resolution_id": self.resolution_id, "version": self.version, "boundary": self.boundary, "plan_id": self.plan_id, "plan_address": self.plan_address, "plan": self.plan.to_dict(), "entries": tuple(item.to_dict() for item in self.entries), "resolution_count": self.resolution_count, "pending_count": self.pending_count, "resolved_count": self.resolved_count, "waived_count": self.waived_count, "rejected_count": self.rejected_count, "not_applicable_count": self.not_applicable_count, "required_open_count": self.required_open_count, "state": self.state, "decision": self.decision, "accepted": self.accepted, "release_ready": self.release_ready, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field not in {"plan", "entries"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolution:
        value = _mapping(value, "resolution")
        _strict(value, set(cls.FIELDS), "resolution")
        return cls(*(value[field] for field in cls.FIELDS))


def address_resolution(value: DownloadedDataProfileContractCompatibilityRemediationResolution) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolution):
        raise ValidationError("resolution address requires a typed resolution")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RESOLUTION_PREFIX)


def _status_maps(plan: remediation_model.DownloadedDataProfileContractCompatibilityRemediationPlan, statuses: Mapping[str, str] | None, rationales: Mapping[str, str] | None, evidence: Mapping[str, Sequence[str]] | None) -> tuple[dict[str, str], dict[str, str], dict[str, tuple[str, ...]]]:
    addresses = {item.content_address for item in plan.actions}
    status_map = dict(statuses or {})
    rationale_map = dict(rationales or {})
    evidence_map = {key: tuple(value) for key, value in (evidence or {}).items()}
    for name, mapping in (("status", status_map), ("rationale", rationale_map), ("evidence", evidence_map)):
        if any(key not in addresses for key in mapping):
            raise ValidationError(f"{name} mapping contains an unknown action address")
    if any(not isinstance(value, str) for value in status_map.values()):
        raise ValidationError("status mapping values must be text labels")
    return status_map, rationale_map, evidence_map


def _entry(action: remediation_model.DownloadedDataProfileContractCompatibilityRemediationAction, ordinal: int, status: str, rationale: str, evidence: Sequence[str]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionEntry:
    body = {"ordinal": ordinal, "action_address": action.content_address, "identity": action.identity, "action": action.action, "priority": action.priority, "required": action.required, "status": status, "evidence_addresses": tuple(evidence), "rationale": rationale, "content_address": ENTRY_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionEntry(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionEntry(**(body | {"content_address": address_entry(provisional)}))


def build_resolution(plan: remediation_model.DownloadedDataProfileContractCompatibilityRemediationPlan, *, resolution_id: str = DEFAULT_RESOLUTION_ID, statuses: Mapping[str, str] | None = None, rationales: Mapping[str, str] | None = None, evidence: Mapping[str, Sequence[str]] | None = None) -> DownloadedDataProfileContractCompatibilityRemediationResolution:
    if not isinstance(plan, remediation_model.DownloadedDataProfileContractCompatibilityRemediationPlan):
        raise ValidationError("resolution requires a typed remediation plan")
    status_map, rationale_map, evidence_map = _status_maps(plan, statuses, rationales, evidence)
    entries = []
    for ordinal, action in enumerate(plan.actions, 1):
        status = "not_applicable" if not action.required else status_map.get(action.content_address, "pending")
        if status not in STATUSES:
            raise ValidationError(f"unsupported resolution status: {status}")
        if not action.required and action.content_address in status_map and status_map[action.content_address] != "not_applicable":
            raise ValidationError("none actions can only be not applicable")
        defaults = {"pending": "No disposition supplied.", "resolved": "Structural remediation is recorded as complete.", "waived": "Structural remediation is explicitly waived pending policy review.", "rejected": "Structural remediation disposition is rejected.", "not_applicable": "No structural remediation is required."}
        entries.append(_entry(action, ordinal, status, rationale_map.get(action.content_address, defaults[status]), evidence_map.get(action.content_address, action.evidence_addresses)))
    counts = tuple(sum(item.status == status for item in entries) for status in STATUSES)
    required_open_count = sum(item.required and item.status != "resolved" for item in entries)
    state = "blocked" if counts[3] else "review" if required_open_count else "clear"
    body = {"resolution_id": resolution_id, "version": VERSION, "boundary": BOUNDARY, "plan_id": plan.plan_id, "plan_address": plan.content_address, "plan": plan, "entries": tuple(entries), "resolution_count": len(entries), "pending_count": counts[0], "resolved_count": counts[1], "waived_count": counts[2], "rejected_count": counts[3], "not_applicable_count": counts[4], "required_open_count": required_open_count}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolution(**body, state=state, decision={"clear": "promote", "review": "hold", "blocked": "block"}[state], accepted=state == "clear", release_ready=state == "clear", content_address=RESOLUTION_PREFIX + ":pending")
    return DownloadedDataProfileContractCompatibilityRemediationResolution(**body, state=provisional.state, decision=provisional.decision, accepted=provisional.accepted, release_ready=provisional.release_ready, content_address=address_resolution(provisional))


def resolution_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolution:
    return DownloadedDataProfileContractCompatibilityRemediationResolution.from_mapping(value)


def resolution_json(value: DownloadedDataProfileContractCompatibilityRemediationResolution) -> str:
    return canonical_json(DownloadedDataProfileContractCompatibilityRemediationResolution.from_mapping(value.to_dict()).to_dict())


def resolution_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolution) -> str:
    value = DownloadedDataProfileContractCompatibilityRemediationResolution.from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(ENTRY_FIELDS)
    writer.writerows(tuple(";".join(item.evidence_addresses) if field == "evidence_addresses" else item.to_dict()[field] for field in ENTRY_FIELDS) for item in value.entries)
    return stream.getvalue()


def render_resolution_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolution) -> str:
    value = DownloadedDataProfileContractCompatibilityRemediationResolution.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Contract Compatibility Remediation Resolution", "", f"- Resolution: `{value.resolution_id}`", f"- Plan: `{value.plan_address}`", f"- Entries: `{value.resolution_count}`", f"- Open required: `{value.required_open_count}`", f"- State: `{value.state}`", f"- Decision: `{value.decision}`", f"- Release ready: `{value.release_ready}`", f"- Address: `{value.content_address}`", "", "| # | identity | action | status | required |", "| ---: | --- | --- | --- | ---: |"]
    lines.extend(f"| {item.ordinal} | `{item.identity}` | `{item.action}` | `{item.status}` | `{item.required}` |" for item in value.entries)
    return "\n".join(lines) + "\n"


def entry_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation resolution entry", "type": "object", "additionalProperties": False, "required": list(ENTRY_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "action_address": {"type": "string"}, "identity": {"type": "string"}, "action": {"enum": list(remediation_model.ACTION_KINDS)}, "priority": {"enum": list(remediation_model.PRIORITIES)}, "required": {"type": "boolean"}, "status": {"enum": list(STATUSES)}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 8}, "rationale": {"type": "string"}, "content_address": {"type": "string"}}}


def resolution_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation resolution", "type": "object", "additionalProperties": False, "required": list(RESOLUTION_FIELDS), "properties": {"resolution_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "plan_id": {"type": "string"}, "plan_address": {"type": "string"}, "plan": remediation_model.plan_schema(), "entries": {"type": "array", "items": entry_schema(), "maxItems": MAX_ENTRIES}, "resolution_count": {"type": "integer", "minimum": 0}, "pending_count": {"type": "integer", "minimum": 0}, "resolved_count": {"type": "integer", "minimum": 0}, "waived_count": {"type": "integer", "minimum": 0}, "rejected_count": {"type": "integer", "minimum": 0}, "not_applicable_count": {"type": "integer", "minimum": 0}, "required_open_count": {"type": "integer", "minimum": 0}, "state": {"enum": list(STATES)}, "decision": {"enum": list(DECISIONS)}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "statuses": STATUSES, "states": STATES, "decisions": DECISIONS, "operations": ("build_resolution", "resolution_from_mapping", "resolution_json", "resolution_csv", "render_resolution_markdown"), "limits": {"max_entries": MAX_ENTRIES}}


__all__ = ["BOUNDARY", "DECISIONS", "DEFAULT_RESOLUTION_ID", "ENTRY_FIELDS", "ENTRY_PREFIX", "MAX_ENTRIES", "RESOLUTION_FIELDS", "RESOLUTION_PREFIX", "STATES", "STATUSES", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolution", "DownloadedDataProfileContractCompatibilityRemediationResolutionEntry", "address_entry", "address_resolution", "build_resolution", "capabilities", "entry_schema", "render_resolution_markdown", "resolution_csv", "resolution_from_mapping", "resolution_json", "resolution_schema"]
