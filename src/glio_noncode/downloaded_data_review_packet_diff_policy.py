"""Deterministic release policy gates for source-free review packet diffs."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import downloaded_data_review_packet_diff as diff_model
from ._safe_persistence import _validate_parent, atomic_write_text, read_text
from .errors import ValidationError
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash

VERSION = "downloaded-data-review-packet-diff-policy-v1"
BOUNDARY = "public_downloaded_data_review_packet_diff_policy"
POLICY_PREFIX = "glio-noncode-download-review-packet-diff-policy"
CHECK_PREFIX = POLICY_PREFIX + "-check"
DEFAULT_POLICY_ID = POLICY_PREFIX
STATES = ("ready", "blocked")
POLICY_CHECK_IDS = (
    "policy-diff-address",
    "policy-diff-replay",
    "policy-added-budget",
    "policy-removed-budget",
    "policy-changed-budget",
    "policy-member-budget",
    "policy-field-budget",
    "policy-type-budget",
    "policy-resource-allowlist",
    "policy-change-allowlist",
    "policy-runtime-change",
    "policy-change-requirement",
)
POLICY_FIELDS = (
    "policy_id", "version", "boundary", "diff_address", "maximum_added", "maximum_removed", "maximum_changed",
    "maximum_member_changed", "maximum_field_changed", "maximum_type_changed", "allowed_resources", "allowed_changes",
    "allow_runtime_change", "require_change", "check_count", "passed_count", "failed_count", "accepted", "state", "checks", "content_address",
)
CHECK_FIELDS = ("check_id", "passed", "observed", "required", "detail", "content_address")
MAX_LIMIT = 256


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
    value = _text(value, field, 4096)
    if ":" not in value or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a content address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
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


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _ordered_labels(value: Any, field: str, allowed: Sequence[str]) -> tuple[str, ...]:
    result = tuple(_label(item, field) for item in _sequence(value, field, len(allowed)))
    if not result or len(set(result)) != len(result) or any(item not in allowed for item in result) or result != tuple(sorted(result, key=allowed.index)):
        raise ValidationError(f"{field} contains unsupported, duplicate, or unordered values")
    return result


def _public(value: Any) -> bool:
    return not _has_forbidden_key(value)


class DownloadedDataReviewPacketDiffPolicyCheck:
    """One deterministic policy condition and its retained evidence."""

    FIELDS = CHECK_FIELDS

    def __init__(self, check_id: str, passed: bool, observed: Any, required: Any, detail: str, content_address: str) -> None:
        self.check_id = _label(check_id, "review packet diff policy check ID")
        if self.check_id not in POLICY_CHECK_IDS:
            raise ValidationError("review packet diff policy check ID is unsupported")
        self.passed = _bool(passed, "review packet diff policy check result")
        self.observed = observed
        self.required = required
        self.detail = _text(detail, "review packet diff policy check detail", 2048)
        self.content_address = _address(content_address, "review packet diff policy check address", CHECK_PREFIX) if not content_address.endswith(":pending") else content_address
        if not content_address.endswith(":pending") and address_check(self) != content_address:
            raise ValidationError("review packet diff policy check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataReviewPacketDiffPolicyCheck:
        if not isinstance(value, Mapping):
            raise ValidationError("review packet diff policy check must be an object")
        _strict(value, set(cls.FIELDS), "review packet diff policy check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataReviewPacketDiffPolicyCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataReviewPacketDiffPolicy:
    """A source-free ready or blocked policy decision over one packet diff."""

    FIELDS = POLICY_FIELDS

    def __init__(self, policy_id: str, version: str, boundary: str, diff_address: str, maximum_added: int, maximum_removed: int, maximum_changed: int, maximum_member_changed: int, maximum_field_changed: int, maximum_type_changed: int, allowed_resources: Sequence[str], allowed_changes: Sequence[str], allow_runtime_change: bool, require_change: bool, check_count: int, passed_count: int, failed_count: int, accepted: bool, state: str, checks: Sequence[DownloadedDataReviewPacketDiffPolicyCheck | Mapping[str, Any]], content_address: str) -> None:
        self.policy_id = _label(policy_id, "review packet diff policy ID")
        self.version = _text(version, "review packet diff policy version")
        self.boundary = _text(boundary, "review packet diff policy boundary", 512)
        self.diff_address = _address(diff_address, "review packet diff policy diff address", diff_model.DIFF_PREFIX)
        for field in ("maximum_added", "maximum_removed", "maximum_changed", "maximum_member_changed", "maximum_field_changed", "maximum_type_changed"):
            setattr(self, field, _count(locals()[field], f"review packet diff policy {field}", diff_model.MAX_ITEMS))
        self.allowed_resources = _ordered_labels(allowed_resources, "review packet diff policy resources", diff_model.RESOURCES)
        self.allowed_changes = _ordered_labels(allowed_changes, "review packet diff policy changes", diff_model.CHANGES)
        self.allow_runtime_change = _bool(allow_runtime_change, "review packet diff policy runtime-change control")
        self.require_change = _bool(require_change, "review packet diff policy required-change control")
        self.check_count = _count(check_count, "review packet diff policy check count", len(POLICY_CHECK_IDS))
        self.passed_count = _count(passed_count, "review packet diff policy passed count", len(POLICY_CHECK_IDS))
        self.failed_count = _count(failed_count, "review packet diff policy failed count", len(POLICY_CHECK_IDS))
        self.accepted = _bool(accepted, "review packet diff policy acceptance")
        self.state = _label(state, "review packet diff policy state")
        if self.state not in STATES:
            raise ValidationError("review packet diff policy state is unsupported")
        self.checks = tuple(item if isinstance(item, DownloadedDataReviewPacketDiffPolicyCheck) else DownloadedDataReviewPacketDiffPolicyCheck.from_mapping(item) for item in _sequence(checks, "review packet diff policy checks", len(POLICY_CHECK_IDS)))
        self.content_address = _address(content_address, "review packet diff policy address", POLICY_PREFIX) if not content_address.endswith(":pending") else _text(content_address, "review packet diff policy address")
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("review packet diff policy version or boundary is not current")
        if self.check_count != len(self.checks) or self.check_count != len(POLICY_CHECK_IDS) or tuple(item.check_id for item in self.checks) != POLICY_CHECK_IDS or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0) or self.state != ("ready" if self.accepted else "blocked"):
            raise ValidationError("review packet diff policy decision aggregates do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("review packet diff policy crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_policy(self) != self.content_address:
            raise ValidationError("review packet diff policy address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS if field != "checks"} | {"checks": tuple(item.to_dict() for item in self.checks)}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataReviewPacketDiffPolicy:
        if not isinstance(value, Mapping):
            raise ValidationError("downloaded data review packet diff policy must be an object")
        _strict(value, set(cls.FIELDS), "downloaded data review packet diff policy")
        return cls(*(value[field] for field in cls.FIELDS))


def address_policy(value: DownloadedDataReviewPacketDiffPolicy) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=POLICY_PREFIX)


def _check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> DownloadedDataReviewPacketDiffPolicyCheck:
    body = {"check_id": check_id, "passed": bool(passed), "observed": observed, "required": required, "detail": detail, "content_address": CHECK_PREFIX + ":pending"}
    provisional = DownloadedDataReviewPacketDiffPolicyCheck(**body)
    return DownloadedDataReviewPacketDiffPolicyCheck(**(body | {"content_address": address_check(provisional)}))


def _settings(maximum_added: int, maximum_removed: int, maximum_changed: int, maximum_member_changed: int, maximum_field_changed: int, maximum_type_changed: int, allowed_resources: Sequence[str], allowed_changes: Sequence[str], allow_runtime_change: bool, require_change: bool) -> dict[str, Any]:
    return {"maximum_added": _count(maximum_added, "maximum added rows", diff_model.MAX_ITEMS), "maximum_removed": _count(maximum_removed, "maximum removed rows", diff_model.MAX_ITEMS), "maximum_changed": _count(maximum_changed, "maximum changed rows", diff_model.MAX_ITEMS), "maximum_member_changed": _count(maximum_member_changed, "maximum member changes", diff_model.MAX_ITEMS), "maximum_field_changed": _count(maximum_field_changed, "maximum field changes", diff_model.MAX_ITEMS), "maximum_type_changed": _count(maximum_type_changed, "maximum type changes", diff_model.MAX_ITEMS), "allowed_resources": _ordered_labels(allowed_resources, "allowed resources", diff_model.RESOURCES), "allowed_changes": _ordered_labels(allowed_changes, "allowed changes", diff_model.CHANGES), "allow_runtime_change": _bool(allow_runtime_change, "allow runtime change"), "require_change": _bool(require_change, "require change")}


def _checks(diff: diff_model.DownloadedDataReviewPacketDiff, settings: Mapping[str, Any]) -> tuple[DownloadedDataReviewPacketDiffPolicyCheck, ...]:
    added = sum(item.change == "added" for item in diff.items)
    removed = sum(item.change == "removed" for item in diff.items)
    changed = sum(item.change == "changed" for item in diff.items)
    member_changed = sum(item.resource == "members" and item.change == "changed" for item in diff.items)
    field_changed = sum(item.resource == "fields" and item.change == "changed" for item in diff.items)
    type_changed = sum(item.resource == "types" and item.change == "changed" for item in diff.items)
    runtime_changed = sum(item.resource == "runtime" and item.change == "changed" for item in diff.items)
    checks = (
        _check("policy-diff-address", diff_model.address_diff(diff) == diff.content_address, diff.content_address, "replayable", "diff address is valid"),
        _check("policy-diff-replay", diff_model.verify_diff(diff).content_address == diff.content_address, "replayed", "replayed", "typed diff reload is valid"),
        _check("policy-added-budget", added <= settings["maximum_added"], added, settings["maximum_added"], "added rows remain within budget"),
        _check("policy-removed-budget", removed <= settings["maximum_removed"], removed, settings["maximum_removed"], "removed rows remain within budget"),
        _check("policy-changed-budget", changed <= settings["maximum_changed"], changed, settings["maximum_changed"], "changed rows remain within budget"),
        _check("policy-member-budget", member_changed <= settings["maximum_member_changed"], member_changed, settings["maximum_member_changed"], "changed member rows remain within budget"),
        _check("policy-field-budget", field_changed <= settings["maximum_field_changed"], field_changed, settings["maximum_field_changed"], "changed field rows remain within budget"),
        _check("policy-type-budget", type_changed <= settings["maximum_type_changed"], type_changed, settings["maximum_type_changed"], "changed type rows remain within budget"),
        _check("policy-resource-allowlist", all(item.resource in settings["allowed_resources"] for item in diff.items), sorted({item.resource for item in diff.items}), settings["allowed_resources"], "all diff resources are allowed"),
        _check("policy-change-allowlist", all(item.change in settings["allowed_changes"] for item in diff.items), sorted({item.change for item in diff.items}, key=diff_model.CHANGES.index), settings["allowed_changes"], "all diff changes are allowed"),
        _check("policy-runtime-change", runtime_changed == 0 or settings["allow_runtime_change"], runtime_changed, settings["allow_runtime_change"], "runtime changes require explicit permission"),
        _check("policy-change-requirement", not settings["require_change"] or changed > 0, changed, "greater than zero" if settings["require_change"] else "not required", "required change posture is satisfied"),
    )
    return checks


def build_policy(diff: Any, *, policy_id: str = DEFAULT_POLICY_ID, maximum_added: int = 0, maximum_removed: int = 0, maximum_changed: int = 0, maximum_member_changed: int = 0, maximum_field_changed: int = 0, maximum_type_changed: int = 0, allowed_resources: Sequence[str] = diff_model.RESOURCES, allowed_changes: Sequence[str] = diff_model.CHANGES, allow_runtime_change: bool = False, require_change: bool = False) -> DownloadedDataReviewPacketDiffPolicy:
    value = diff_model.verify_diff(diff)
    settings = _settings(maximum_added, maximum_removed, maximum_changed, maximum_member_changed, maximum_field_changed, maximum_type_changed, allowed_resources, allowed_changes, allow_runtime_change, require_change)
    checks = _checks(value, settings)
    body = {"policy_id": policy_id, "version": VERSION, "boundary": BOUNDARY, "diff_address": value.content_address, **settings, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": all(item.passed for item in checks), "state": "ready" if all(item.passed for item in checks) else "blocked", "checks": checks, "content_address": POLICY_PREFIX + ":pending"}
    provisional = DownloadedDataReviewPacketDiffPolicy(**body)
    return DownloadedDataReviewPacketDiffPolicy(**(body | {"content_address": address_policy(provisional)}))


def strict_policy(diff: Any, *, policy_id: str = "strict-" + DEFAULT_POLICY_ID) -> DownloadedDataReviewPacketDiffPolicy:
    return build_policy(diff, policy_id=policy_id)


def release_policy(diff: Any, *, policy_id: str = "release-" + DEFAULT_POLICY_ID, maximum_added: int = 0, maximum_removed: int = 0, maximum_changed: int = 256, maximum_member_changed: int = 64, maximum_field_changed: int = 128, maximum_type_changed: int = 64, allow_runtime_change: bool = True, require_change: bool = False) -> DownloadedDataReviewPacketDiffPolicy:
    return build_policy(diff, policy_id=policy_id, maximum_added=maximum_added, maximum_removed=maximum_removed, maximum_changed=maximum_changed, maximum_member_changed=maximum_member_changed, maximum_field_changed=maximum_field_changed, maximum_type_changed=maximum_type_changed, allowed_resources=diff_model.RESOURCES, allowed_changes=diff_model.CHANGES, allow_runtime_change=allow_runtime_change, require_change=require_change)


def verify_policy(value: Any) -> DownloadedDataReviewPacketDiffPolicy:
    policy = value if isinstance(value, DownloadedDataReviewPacketDiffPolicy) else load_policy(value)
    if address_policy(policy) != policy.content_address:
        raise ValidationError("review packet diff policy address does not replay")
    return DownloadedDataReviewPacketDiffPolicy.from_mapping(policy.to_dict())


def load_policy(value: bytes | bytearray | str | Path | Mapping[str, Any]) -> DownloadedDataReviewPacketDiffPolicy:
    if isinstance(value, Mapping):
        raw = value
    elif isinstance(value, (bytes, bytearray)):
        raw = _strict_json_loads(bytes(value).decode("utf-8"))
    else:
        raw = _strict_json_loads(read_text(value, field="downloaded data review packet diff policy", max_bytes=16 * 1024 * 1024))
    return DownloadedDataReviewPacketDiffPolicy.from_mapping(raw)


def policy_from_mapping(value: Mapping[str, Any]) -> DownloadedDataReviewPacketDiffPolicy:
    return DownloadedDataReviewPacketDiffPolicy.from_mapping(value)


def policy_json(value: Any) -> str:
    return canonical_json(verify_policy(value).to_dict()) + "\n"


def write_policy(value: Any, destination: str | Path, *, allow_existing: bool = False) -> DownloadedDataReviewPacketDiffPolicy:
    policy = verify_policy(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("review packet diff policy destination already exists")
    if path.exists() and not path.is_file():
        raise ValidationError("review packet diff policy destination is not a file")
    _validate_parent(path.parent, "review packet diff policy destination")
    atomic_write_text(path, policy_json(policy), field="review packet diff policy destination")
    return policy


def query_policy(value: Any, *, passed: bool | None = None, check_id: str = "", text: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    policy = verify_policy(value)
    if passed is not None and not isinstance(passed, bool):
        raise ValidationError("review packet diff policy passed filter must be boolean")
    check_id = _label(check_id, "review packet diff policy check filter", required=False)
    if check_id and check_id not in POLICY_CHECK_IDS:
        raise ValidationError("review packet diff policy check filter is unsupported")
    text = _text(text, "review packet diff policy text filter", required=False)
    offset = _count(offset, "review packet diff policy query offset", len(policy.checks))
    limit = _count(limit, "review packet diff policy query limit", MAX_LIMIT, positive=True)
    matches = tuple(item for item in policy.checks if (passed is None or item.passed == passed) and (not check_id or item.check_id == check_id) and (not text or text.casefold() in " ".join((item.check_id, item.detail, str(item.observed))).casefold()))
    selected = matches[offset:offset + limit]
    result = {"policy_address": policy.content_address, "passed": passed, "check_id": check_id, "text": text, "offset": offset, "limit": limit, "total": len(policy.checks), "matched": len(matches), "returned": len(selected), "truncated": offset + len(selected) < len(matches), "checks": tuple(item.to_dict() for item in selected)}
    return result | {"content_address": content_hash(result, prefix=POLICY_PREFIX + "-query")}


def policy_csv(value: Any, *, passed: bool | None = None, check_id: str = "", text: str = "", offset: int = 0, limit: int = 50) -> str:
    result = query_policy(value, passed=passed, check_id=check_id, text=text, offset=offset, limit=limit)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in result["checks"]:
        writer.writerow({field: canonical_json(item[field]) if field in {"observed", "required"} else item[field] for field in CHECK_FIELDS})
    return stream.getvalue()


def render_policy_markdown(value: Any) -> str:
    policy = verify_policy(value)
    lines = ["# Downloaded Data Review Packet Diff Policy", "", f"- Policy: `{policy.policy_id}`", f"- State: **{policy.state}**", f"- Passed / failed: **{policy.passed_count} / {policy.failed_count}**", f"- Diff: `{policy.diff_address}`", f"- Address: `{policy.content_address}`", "", "| check | passed | detail |", "| --- | --- | --- |"]
    lines.extend(f"| `{item.check_id}` | {str(item.passed).lower()} | {item.detail} |" for item in policy.checks)
    return "\n".join(lines) + "\n"


def policy_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data review packet diff policy", "type": "object", "additionalProperties": False, "required": list(POLICY_FIELDS), "properties": {field: {"type": "array" if field in {"allowed_resources", "allowed_changes", "checks"} else "boolean" if field in {"allow_runtime_change", "require_change", "accepted"} else "integer" if field in {"maximum_added", "maximum_removed", "maximum_changed", "maximum_member_changed", "maximum_field_changed", "maximum_type_changed", "check_count", "passed_count", "failed_count"} else "string"} for field in POLICY_FIELDS}}


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data review packet diff policy check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"check_id": {"enum": list(POLICY_CHECK_IDS)}, "passed": {"type": "boolean"}, "observed": {}, "required": {}, "detail": {"type": "string"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    operations = ("build_policy", "strict_policy", "release_policy", "verify_policy", "load_source_free", "query_checks", "export_json", "export_csv", "render_markdown", "write_atomic")
    return {"public": True, "independent": True, "source_free": True, "version": VERSION, "boundary": BOUNDARY, "states": list(STATES), "check_count": len(POLICY_CHECK_IDS), "operation_count": len(operations), "operations": list(operations), "profiles": ["strict", "release"]}


__all__ = [
    "BOUNDARY", "CHECK_FIELDS", "CHECK_PREFIX", "DEFAULT_POLICY_ID", "POLICY_CHECK_IDS", "POLICY_FIELDS", "POLICY_PREFIX", "STATES", "VERSION", "DownloadedDataReviewPacketDiffPolicy", "DownloadedDataReviewPacketDiffPolicyCheck", "address_check", "address_policy", "build_policy", "capabilities", "check_schema", "load_policy", "policy_csv", "policy_from_mapping", "policy_json", "policy_schema", "query_policy", "release_policy", "render_policy_markdown", "strict_policy", "verify_policy", "write_policy",
]
