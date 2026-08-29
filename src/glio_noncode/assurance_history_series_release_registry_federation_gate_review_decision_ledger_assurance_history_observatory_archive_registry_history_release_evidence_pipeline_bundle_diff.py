"""Deterministic baseline/candidate diffs for release-evidence bundles.

This boundary compares two independently verified five-file evidence bundles.
It reports semantic pipeline transitions and per-file byte changes without
copying source paths or private metadata into the result.  The diff is a
review projection, not a replacement evidence source: both directories must
pass the strict bundle loader before a comparison is produced.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline as pipeline_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle as bundle_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_query as query_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash, hash_bytes


VERSION = bundle_model.VERSION + "-diff-v1"
BOUNDARY = bundle_model.BOUNDARY + "_diff"
DIFF_PREFIX = bundle_model.BUNDLE_PREFIX + "-diff"
DIFF_ITEM_PREFIX = DIFF_PREFIX + "-item"
DIFF_ARTIFACT_PREFIX = DIFF_PREFIX + "-artifact"
DEFAULT_DIFF_ID = bundle_model.BUNDLE_PREFIX + "-diff"
MAX_ITEMS = len(bundle_model.FILES)
MAX_TEXT = 1024
ACTIONS = ("changed", "unchanged")
STATES = ("unchanged", "improved", "regressed", "mixed")
BUNDLE_FIELDS = (
    "pipeline_address",
    "pipeline_state",
    "pipeline_accepted",
    "query_addresses",
    "artifact_count",
    "manifest_address",
    "content_address",
)
ITEM_FIELDS = ("size", "hash")


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
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unsupported fields: {sorted(unknown)}")


def _public(value: Any) -> bool:
    return bundle_model._public(value)


def _changed_fields(before: Mapping[str, Any], after: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(field for field in BUNDLE_FIELDS if before[field] != after[field])


def _quality_vector(state: str, accepted: bool) -> tuple[int, int]:
    return (int(accepted), {"blocked": 0, "held": 1, "ready": 2}[state])


def _aggregate_state(before_state: str, after_state: str, before_accepted: bool, after_accepted: bool, changed: bool) -> str:
    if not changed:
        return "unchanged"
    before = _quality_vector(before_state, before_accepted)
    after = _quality_vector(after_state, after_accepted)
    if after > before:
        return "improved"
    if after < before:
        return "regressed"
    return "mixed"


class RegistryHistoryReleaseEvidencePipelineBundleDiffItem:
    """One file-level transition in a verified evidence bundle diff."""

    def __init__(self, ordinal: int, name: str, action: str, baseline_size: int, candidate_size: int, baseline_hash: str, candidate_hash: str, changed_fields: Sequence[str], detail: str, content_address: str) -> None:
        self.ordinal = ordinal
        self.name = name
        self.action = action
        self.baseline_size = baseline_size
        self.candidate_size = candidate_size
        self.baseline_hash = baseline_hash
        self.candidate_hash = candidate_hash
        self.changed_fields = tuple(changed_fields)
        self.detail = detail
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "release evidence bundle diff item ordinal", MAX_ITEMS, positive=True)
        if self.name not in bundle_model.FILES:
            raise ValidationError("release evidence bundle diff item file is unsupported")
        if self.action not in ACTIONS:
            raise ValidationError("release evidence bundle diff item action is unsupported")
        _count(self.baseline_size, "release evidence bundle diff baseline size", bundle_model.MAX_ARTIFACT_BYTES)
        _count(self.candidate_size, "release evidence bundle diff candidate size", bundle_model.MAX_ARTIFACT_BYTES)
        _text(self.baseline_hash, "release evidence bundle diff baseline hash", 2048)
        _text(self.candidate_hash, "release evidence bundle diff candidate hash", 2048)
        if tuple(field for field in ITEM_FIELDS if field in self.changed_fields) != self.changed_fields or len(set(self.changed_fields)) != len(self.changed_fields):
            raise ValidationError("release evidence bundle diff item changed fields are not canonically ordered")
        if any(field not in ITEM_FIELDS for field in self.changed_fields):
            raise ValidationError("release evidence bundle diff item contains an unsupported changed field")
        actually_changed = self.baseline_size != self.candidate_size or self.baseline_hash != self.candidate_hash
        if self.action != ("changed" if actually_changed else "unchanged") or tuple(field for field in ITEM_FIELDS if (field == "size" and self.baseline_size != self.candidate_size) or (field == "hash" and self.baseline_hash != self.candidate_hash)) != self.changed_fields:
            raise ValidationError("release evidence bundle diff item does not conserve byte changes")
        _text(self.detail, "release evidence bundle diff item detail", MAX_TEXT)
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "release evidence bundle diff item content address")
        else:
            _address(self.content_address, "release evidence bundle diff item content address", DIFF_ITEM_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_diff_item(self) != self.content_address):
            raise ValidationError("release evidence bundle diff item address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "name": self.name, "action": self.action, "baseline_size": self.baseline_size, "candidate_size": self.candidate_size, "baseline_hash": self.baseline_hash, "candidate_hash": self.candidate_hash, "changed_fields": self.changed_fields, "detail": self.detail, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "name": self.name, "action": self.action, "baseline_size": self.baseline_size, "candidate_size": self.candidate_size, "changed_fields": self.changed_fields, "detail": self.detail, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineBundleDiffItem:
        value = _mapping(value, "release evidence bundle diff item")
        _strict(value, {"ordinal", "name", "action", "baseline_size", "candidate_size", "baseline_hash", "candidate_hash", "changed_fields", "detail", "content_address"}, "release evidence bundle diff item")
        return cls(value["ordinal"], value["name"], value["action"], value["baseline_size"], value["candidate_size"], value["baseline_hash"], value["candidate_hash"], _sequence(value["changed_fields"], "release evidence bundle diff item changed fields", len(ITEM_FIELDS)), value["detail"], value["content_address"])


class RegistryHistoryReleaseEvidencePipelineBundleDiff:
    """Path-free semantic and file-level diff between two bundle snapshots."""

    def __init__(self, diff_id: str, baseline_address: str, candidate_address: str, baseline_manifest_address: str, candidate_manifest_address: str, baseline_pipeline_address: str, candidate_pipeline_address: str, baseline_pipeline_state: str, candidate_pipeline_state: str, baseline_pipeline_accepted: bool, candidate_pipeline_accepted: bool, baseline_query_addresses: Sequence[str], candidate_query_addresses: Sequence[str], baseline_artifact_count: int, candidate_artifact_count: int, changed_fields: Sequence[str], item_count: int, changed_count: int, unchanged_count: int, state: str, items: Sequence[RegistryHistoryReleaseEvidencePipelineBundleDiffItem], content_address: str) -> None:
        self.diff_id = _text(diff_id, "release evidence bundle diff ID")
        self.baseline_address = _address(baseline_address, "release evidence bundle diff baseline address", bundle_model.BUNDLE_PREFIX)
        self.candidate_address = _address(candidate_address, "release evidence bundle diff candidate address", bundle_model.BUNDLE_PREFIX)
        self.baseline_manifest_address = _address(baseline_manifest_address, "release evidence bundle diff baseline manifest address", bundle_model.MANIFEST_PREFIX)
        self.candidate_manifest_address = _address(candidate_manifest_address, "release evidence bundle diff candidate manifest address", bundle_model.MANIFEST_PREFIX)
        self.baseline_pipeline_address = _address(baseline_pipeline_address, "release evidence bundle diff baseline pipeline address", pipeline_model.PIPELINE_PREFIX)
        self.candidate_pipeline_address = _address(candidate_pipeline_address, "release evidence bundle diff candidate pipeline address", pipeline_model.PIPELINE_PREFIX)
        self.baseline_pipeline_state = _text(baseline_pipeline_state, "release evidence bundle diff baseline pipeline state", 32)
        self.candidate_pipeline_state = _text(candidate_pipeline_state, "release evidence bundle diff candidate pipeline state", 32)
        self.baseline_pipeline_accepted = _bool(baseline_pipeline_accepted, "release evidence bundle diff baseline pipeline acceptance")
        self.candidate_pipeline_accepted = _bool(candidate_pipeline_accepted, "release evidence bundle diff candidate pipeline acceptance")
        if not isinstance(baseline_query_addresses, tuple) or not isinstance(candidate_query_addresses, tuple):
            raise ValidationError("release evidence bundle diff query addresses must be tuples")
        self.baseline_query_addresses = tuple(_address(value, "release evidence bundle diff baseline query address", query_model.QUERY_PREFIX) for value in baseline_query_addresses)
        self.candidate_query_addresses = tuple(_address(value, "release evidence bundle diff candidate query address", query_model.QUERY_PREFIX) for value in candidate_query_addresses)
        self.baseline_artifact_count = _count(baseline_artifact_count, "release evidence bundle diff baseline artifact count", len(bundle_model.ARTIFACT_FILES))
        self.candidate_artifact_count = _count(candidate_artifact_count, "release evidence bundle diff candidate artifact count", len(bundle_model.ARTIFACT_FILES))
        self.changed_fields = tuple(changed_fields)
        self.item_count = item_count
        self.changed_count = changed_count
        self.unchanged_count = unchanged_count
        self.state = state
        self.items = tuple(items)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if self.baseline_pipeline_state not in pipeline_model.STATES or self.candidate_pipeline_state not in pipeline_model.STATES:
            raise ValidationError("release evidence bundle diff pipeline state is unsupported")
        if len(self.baseline_query_addresses) != len(bundle_model.QUERY_ARTIFACTS) or len(self.candidate_query_addresses) != len(bundle_model.QUERY_ARTIFACTS):
            raise ValidationError("release evidence bundle diff query address count is invalid")
        if self.baseline_artifact_count != len(bundle_model.ARTIFACT_FILES) or self.candidate_artifact_count != len(bundle_model.ARTIFACT_FILES):
            raise ValidationError("release evidence bundle diff artifact count is invalid")
        if tuple(field for field in BUNDLE_FIELDS if field in self.changed_fields) != self.changed_fields or len(set(self.changed_fields)) != len(self.changed_fields) or any(field not in BUNDLE_FIELDS for field in self.changed_fields):
            raise ValidationError("release evidence bundle diff changed fields are not canonically ordered")
        if self.item_count != MAX_ITEMS or len(self.items) != MAX_ITEMS or tuple(item.ordinal for item in self.items) != tuple(range(1, MAX_ITEMS + 1)) or tuple(item.name for item in self.items) != bundle_model.FILES:
            raise ValidationError("release evidence bundle diff item set is invalid")
        _count(self.changed_count, "release evidence bundle diff changed count", MAX_ITEMS)
        _count(self.unchanged_count, "release evidence bundle diff unchanged count", MAX_ITEMS)
        if self.changed_count + self.unchanged_count != self.item_count or self.changed_count != sum(item.action == "changed" for item in self.items) or self.unchanged_count != sum(item.action == "unchanged" for item in self.items):
            raise ValidationError("release evidence bundle diff item counts are not conserved")
        expected_state = _aggregate_state(self.baseline_pipeline_state, self.candidate_pipeline_state, self.baseline_pipeline_accepted, self.candidate_pipeline_accepted, bool(self.changed_fields) or self.changed_count > 0)
        if self.state not in STATES or self.state != expected_state:
            raise ValidationError("release evidence bundle diff state is not derived from transitions")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "release evidence bundle diff content address")
        else:
            _address(self.content_address, "release evidence bundle diff content address", DIFF_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_diff(self) != self.content_address):
            raise ValidationError("release evidence bundle diff address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_id": self.diff_id, "baseline_address": self.baseline_address, "candidate_address": self.candidate_address, "baseline_manifest_address": self.baseline_manifest_address, "candidate_manifest_address": self.candidate_manifest_address, "baseline_pipeline_address": self.baseline_pipeline_address, "candidate_pipeline_address": self.candidate_pipeline_address, "baseline_pipeline_state": self.baseline_pipeline_state, "candidate_pipeline_state": self.candidate_pipeline_state, "baseline_pipeline_accepted": self.baseline_pipeline_accepted, "candidate_pipeline_accepted": self.candidate_pipeline_accepted, "baseline_query_addresses": self.baseline_query_addresses, "candidate_query_addresses": self.candidate_query_addresses, "baseline_artifact_count": self.baseline_artifact_count, "candidate_artifact_count": self.candidate_artifact_count, "changed_fields": self.changed_fields, "item_count": self.item_count, "changed_count": self.changed_count, "unchanged_count": self.unchanged_count, "state": self.state, "items": tuple(item.to_dict() for item in self.items), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("diff_id", "baseline_address", "candidate_address", "baseline_manifest_address", "candidate_manifest_address", "baseline_pipeline_address", "candidate_pipeline_address", "baseline_pipeline_state", "candidate_pipeline_state", "baseline_pipeline_accepted", "candidate_pipeline_accepted", "changed_fields", "item_count", "changed_count", "unchanged_count", "state", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineBundleDiff:
        value = _mapping(value, "release evidence bundle diff")
        fields = {"diff_id", "baseline_address", "candidate_address", "baseline_manifest_address", "candidate_manifest_address", "baseline_pipeline_address", "candidate_pipeline_address", "baseline_pipeline_state", "candidate_pipeline_state", "baseline_pipeline_accepted", "candidate_pipeline_accepted", "baseline_query_addresses", "candidate_query_addresses", "baseline_artifact_count", "candidate_artifact_count", "changed_fields", "item_count", "changed_count", "unchanged_count", "state", "items", "content_address"}
        _strict(value, fields, "release evidence bundle diff")
        items = tuple(RegistryHistoryReleaseEvidencePipelineBundleDiffItem.from_mapping(item) for item in _sequence(value["items"], "release evidence bundle diff items", MAX_ITEMS))
        result = cls(value["diff_id"], value["baseline_address"], value["candidate_address"], value["baseline_manifest_address"], value["candidate_manifest_address"], value["baseline_pipeline_address"], value["candidate_pipeline_address"], value["baseline_pipeline_state"], value["candidate_pipeline_state"], value["baseline_pipeline_accepted"], value["candidate_pipeline_accepted"], tuple(_sequence(value["baseline_query_addresses"], "release evidence bundle diff baseline query addresses", len(bundle_model.QUERY_ARTIFACTS))), tuple(_sequence(value["candidate_query_addresses"], "release evidence bundle diff candidate query addresses", len(bundle_model.QUERY_ARTIFACTS))), value["baseline_artifact_count"], value["candidate_artifact_count"], _sequence(value["changed_fields"], "release evidence bundle diff changed fields", len(BUNDLE_FIELDS)), value["item_count"], value["changed_count"], value["unchanged_count"], value["state"], items, value["content_address"])
        return result


def address_diff_item(value: RegistryHistoryReleaseEvidencePipelineBundleDiffItem) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineBundleDiffItem):
        raise ValidationError("release evidence bundle diff item address requires a typed item")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_ITEM_PREFIX)


def address_diff(value: RegistryHistoryReleaseEvidencePipelineBundleDiff) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineBundleDiff):
        raise ValidationError("release evidence bundle diff address requires a typed diff")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_PREFIX)


def _snapshot(source: str | Path) -> tuple[bundle_model.RegistryHistoryReleaseEvidencePipelineBundle, dict[str, bytes]]:
    loaded = bundle_model.load_bundle(source)
    directory = Path(source)
    return loaded, {name: (directory / name).read_bytes() for name in bundle_model.FILES}


def _artifact(value: bytes) -> tuple[int, str]:
    return len(value), hash_bytes(value, prefix=DIFF_ARTIFACT_PREFIX)


def _bundle_projection(value: bundle_model.RegistryHistoryReleaseEvidencePipelineBundle) -> dict[str, Any]:
    return {"pipeline_address": value.pipeline_address, "pipeline_state": value.pipeline_state, "pipeline_accepted": value.pipeline_accepted, "query_addresses": value.query_addresses, "artifact_count": value.artifact_count, "manifest_address": value.manifest_address, "content_address": value.content_address}


def _build_diff(baseline: bundle_model.RegistryHistoryReleaseEvidencePipelineBundle, candidate: bundle_model.RegistryHistoryReleaseEvidencePipelineBundle, baseline_payload: Mapping[str, bytes], candidate_payload: Mapping[str, bytes], diff_id: str) -> RegistryHistoryReleaseEvidencePipelineBundleDiff:
    before = _bundle_projection(baseline)
    after = _bundle_projection(candidate)
    changed_fields = _changed_fields(before, after)
    items = []
    for ordinal, name in enumerate(bundle_model.FILES, start=1):
        baseline_size, baseline_hash = _artifact(baseline_payload[name])
        candidate_size, candidate_hash = _artifact(candidate_payload[name])
        item_changed_fields = tuple(field for field in ITEM_FIELDS if (field == "size" and baseline_size != candidate_size) or (field == "hash" and baseline_hash != candidate_hash))
        action = "changed" if item_changed_fields else "unchanged"
        detail = f"{name} is {'changed' if action == 'changed' else 'unchanged'} between the verified bundles"
        provisional = RegistryHistoryReleaseEvidencePipelineBundleDiffItem(ordinal, name, action, baseline_size, candidate_size, baseline_hash, candidate_hash, item_changed_fields, detail, "pending:item")
        items.append(RegistryHistoryReleaseEvidencePipelineBundleDiffItem(**provisional.to_dict() | {"content_address": address_diff_item(provisional)}))
    changed_count = sum(item.action == "changed" for item in items)
    provisional = RegistryHistoryReleaseEvidencePipelineBundleDiff(diff_id, baseline.content_address, candidate.content_address, baseline.manifest_address, candidate.manifest_address, baseline.pipeline_address, candidate.pipeline_address, baseline.pipeline_state, candidate.pipeline_state, baseline.pipeline_accepted, candidate.pipeline_accepted, baseline.query_addresses, candidate.query_addresses, baseline.artifact_count, candidate.artifact_count, changed_fields, MAX_ITEMS, changed_count, MAX_ITEMS - changed_count, _aggregate_state(baseline.pipeline_state, candidate.pipeline_state, baseline.pipeline_accepted, candidate.pipeline_accepted, bool(changed_fields) or changed_count > 0), tuple(items), "pending:diff")
    final_payload = provisional.to_dict()
    final_payload["items"] = provisional.items
    final_payload["content_address"] = address_diff(provisional)
    return RegistryHistoryReleaseEvidencePipelineBundleDiff(**final_payload)


def build_diff(baseline_source: str | Path, candidate_source: str | Path, *, diff_id: str = DEFAULT_DIFF_ID) -> RegistryHistoryReleaseEvidencePipelineBundleDiff:
    """Compare two strict, persisted release-evidence bundles."""

    baseline, baseline_payload = _snapshot(baseline_source)
    candidate, candidate_payload = _snapshot(candidate_source)
    return _build_diff(baseline, candidate, baseline_payload, candidate_payload, diff_id)


def diff_bundle_directories(baseline_source: str | Path, candidate_source: str | Path, *, diff_id: str = DEFAULT_DIFF_ID) -> RegistryHistoryReleaseEvidencePipelineBundleDiff:
    return build_diff(baseline_source, candidate_source, diff_id=diff_id)


def diff_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineBundleDiff:
    return RegistryHistoryReleaseEvidencePipelineBundleDiff.from_mapping(value)


def verify_diff(value: RegistryHistoryReleaseEvidencePipelineBundleDiff) -> RegistryHistoryReleaseEvidencePipelineBundleDiff:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineBundleDiff):
        raise ValidationError("release evidence bundle diff verification requires a typed diff")
    value._validate()
    return value


def diff_json(value: RegistryHistoryReleaseEvidencePipelineBundleDiff) -> str:
    verify_diff(value)
    return canonical_json(value.to_dict())


def diff_csv(value: RegistryHistoryReleaseEvidencePipelineBundleDiff) -> str:
    verify_diff(value)
    output = io.StringIO(newline="")
    fields = ("ordinal", "name", "action", "baseline_size", "candidate_size", "changed_fields", "detail", "content_address")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in value.items:
        row = item.summary()
        writer.writerow({field: canonical_json(row[field]) if isinstance(row.get(field), (dict, list, tuple)) else row.get(field, "") for field in fields})
    return output.getvalue()


def render_diff_markdown(value: RegistryHistoryReleaseEvidencePipelineBundleDiff) -> str:
    verify_diff(value)
    lines = ["# Assurance History Observatory Archive Registry History Release Evidence Pipeline Bundle Diff", "", f"- State: `{value.state}`", f"- Baseline: `{value.baseline_address}`", f"- Candidate: `{value.candidate_address}`", f"- Pipeline state: `{value.baseline_pipeline_state}` -> `{value.candidate_pipeline_state}`", f"- Pipeline acceptance: `{str(value.baseline_pipeline_accepted).lower()}` -> `{str(value.candidate_pipeline_accepted).lower()}`", f"- Changed fields: `{len(value.changed_fields)}`", f"- Files: `{value.changed_count}` changed, `{value.unchanged_count}` unchanged", f"- Content address: `{value.content_address}`", "", "| File | Action | Changed fields | Baseline bytes | Candidate bytes | Detail |", "| --- | --- | --- | ---: | ---: | --- |"]
    lines.extend(f"| `{item.name}` | `{item.action}` | `{', '.join(item.changed_fields) or 'none'}` | `{item.baseline_size}` | `{item.candidate_size}` | {item.detail} |" for item in value.items)
    return "\n".join(lines) + "\n"


def item_schema() -> dict[str, Any]:
    fields = {"ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_ITEMS}, "name": {"type": "string", "enum": list(bundle_model.FILES)}, "action": {"type": "string", "enum": list(ACTIONS)}, "baseline_size": {"type": "integer", "minimum": 0, "maximum": bundle_model.MAX_ARTIFACT_BYTES}, "candidate_size": {"type": "integer", "minimum": 0, "maximum": bundle_model.MAX_ARTIFACT_BYTES}, "baseline_hash": {"type": "string"}, "candidate_hash": {"type": "string"}, "changed_fields": {"type": "array", "items": {"type": "string", "enum": list(ITEM_FIELDS)}, "maxItems": len(ITEM_FIELDS)}, "detail": {"type": "string", "maxLength": MAX_TEXT}, "content_address": {"type": "string", "pattern": "^" + DIFF_ITEM_PREFIX + ":"}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def diff_schema() -> dict[str, Any]:
    fields = {"diff_id": {"type": "string"}, "baseline_address": {"type": "string", "pattern": "^" + bundle_model.BUNDLE_PREFIX + ":"}, "candidate_address": {"type": "string", "pattern": "^" + bundle_model.BUNDLE_PREFIX + ":"}, "baseline_manifest_address": {"type": "string", "pattern": "^" + bundle_model.MANIFEST_PREFIX + ":"}, "candidate_manifest_address": {"type": "string", "pattern": "^" + bundle_model.MANIFEST_PREFIX + ":"}, "baseline_pipeline_address": {"type": "string", "pattern": "^" + pipeline_model.PIPELINE_PREFIX + ":"}, "candidate_pipeline_address": {"type": "string", "pattern": "^" + pipeline_model.PIPELINE_PREFIX + ":"}, "baseline_pipeline_state": {"type": "string", "enum": list(pipeline_model.STATES)}, "candidate_pipeline_state": {"type": "string", "enum": list(pipeline_model.STATES)}, "baseline_pipeline_accepted": {"type": "boolean"}, "candidate_pipeline_accepted": {"type": "boolean"}, "baseline_query_addresses": {"type": "array", "minItems": len(bundle_model.QUERY_ARTIFACTS), "maxItems": len(bundle_model.QUERY_ARTIFACTS)}, "candidate_query_addresses": {"type": "array", "minItems": len(bundle_model.QUERY_ARTIFACTS), "maxItems": len(bundle_model.QUERY_ARTIFACTS)}, "baseline_artifact_count": {"type": "integer", "const": len(bundle_model.ARTIFACT_FILES)}, "candidate_artifact_count": {"type": "integer", "const": len(bundle_model.ARTIFACT_FILES)}, "changed_fields": {"type": "array", "items": {"type": "string", "enum": list(BUNDLE_FIELDS)}, "maxItems": len(BUNDLE_FIELDS)}, "item_count": {"type": "integer", "const": MAX_ITEMS}, "changed_count": {"type": "integer", "minimum": 0, "maximum": MAX_ITEMS}, "unchanged_count": {"type": "integer", "minimum": 0, "maximum": MAX_ITEMS}, "state": {"type": "string", "enum": list(STATES)}, "items": {"type": "array", "minItems": MAX_ITEMS, "maxItems": MAX_ITEMS, "items": item_schema()}, "content_address": {"type": "string", "pattern": "^" + DIFF_PREFIX + ":"}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "files": bundle_model.FILES, "actions": ACTIONS, "states": STATES, "fields": BUNDLE_FIELDS, "item_fields": ITEM_FIELDS, "limits": {"max_items": MAX_ITEMS, "max_artifact_bytes": bundle_model.MAX_ARTIFACT_BYTES}, "features": ("strict verified bundle comparison", "pipeline state and acceptance transitions", "manifest and query address transitions", "per-file byte size and hash changes", "deterministic changed-field ordering", "improved regressed mixed and unchanged state", "content-addressed diff and items", "path-free JSON CSV and Markdown exports"), "schemas": ("diff", "item")}


__all__ = [
    "ACTIONS",
    "BOUNDARY",
    "BUNDLE_FIELDS",
    "DEFAULT_DIFF_ID",
    "DIFF_ARTIFACT_PREFIX",
    "DIFF_ITEM_PREFIX",
    "DIFF_PREFIX",
    "ITEM_FIELDS",
    "MAX_ITEMS",
    "STATES",
    "VERSION",
    "RegistryHistoryReleaseEvidencePipelineBundleDiff",
    "RegistryHistoryReleaseEvidencePipelineBundleDiffItem",
    "address_diff",
    "address_diff_item",
    "build_diff",
    "capabilities",
    "diff_bundle_directories",
    "diff_csv",
    "diff_from_mapping",
    "diff_json",
    "diff_schema",
    "item_schema",
    "render_diff_markdown",
    "verify_diff",
]
