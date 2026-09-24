"""Apply strict and release gates to packet-package catalog diffs."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff as diff_model
from . import downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_contracts as contract_model
from ._safe_persistence import _validate_parent, atomic_write_text, read_text
from .errors import ValidationError
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash

VERSION = contract_model.VERSION
BOUNDARY = contract_model.BOUNDARY
POLICY_PREFIX = contract_model.POLICY_PREFIX
CHECK_PREFIX = contract_model.CHECK_PREFIX
DEFAULT_POLICY_ID = contract_model.DEFAULT_POLICY_ID
STATES = contract_model.STATES
POLICY_CHECK_IDS = contract_model.POLICY_CHECK_IDS
POLICY_FIELDS = contract_model.POLICY_FIELDS
CHECK_FIELDS = contract_model.CHECK_FIELDS
MAX_LIMIT = contract_model.MAX_LIMIT


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    return contract_model._count(value, field, maximum, positive=positive)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    return contract_model._text(value, field, maximum, required=required)


def _ordered_labels(value: Any, field: str, allowed: Sequence[str], *, allow_empty: bool = False) -> tuple[str, ...]:
    return contract_model._ordered_labels(value, field, allowed, allow_empty=allow_empty)


def _settings(maximum_added: int, maximum_removed: int, maximum_changed: int, maximum_total_changes: int, allowed_changes: Sequence[str], allowed_directions: Sequence[str], allowed_transitions: Sequence[str], allowed_left_postures: Sequence[str], allowed_right_postures: Sequence[str], required_changes: Sequence[str], require_ready: bool, require_change: bool, allow_unchanged: bool) -> dict[str, Any]:
    return {
        "maximum_added": _count(maximum_added, "maximum added packet-package catalog entries", diff_model.MAX_ITEMS),
        "maximum_removed": _count(maximum_removed, "maximum removed packet-package catalog entries", diff_model.MAX_ITEMS),
        "maximum_changed": _count(maximum_changed, "maximum changed packet-package catalog entries", diff_model.MAX_ITEMS),
        "maximum_total_changes": _count(maximum_total_changes, "maximum total packet-package catalog changes", diff_model.MAX_ITEMS),
        "allowed_changes": _ordered_labels(allowed_changes, "allowed packet-package catalog entry changes", diff_model.CHANGES),
        "allowed_directions": _ordered_labels(allowed_directions, "allowed packet-package catalog diff directions", diff_model.DIRECTIONS),
        "allowed_transitions": _ordered_labels(allowed_transitions, "allowed packet-package catalog posture transitions", diff_model.STATE_TRANSITIONS),
        "allowed_left_postures": _ordered_labels(allowed_left_postures, "allowed left packet-package catalog postures", diff_model.POSTURES),
        "allowed_right_postures": _ordered_labels(allowed_right_postures, "allowed right packet-package catalog postures", diff_model.POSTURES),
        "required_changes": _ordered_labels(required_changes, "required packet-package catalog entry changes", diff_model.CHANGES, allow_empty=True),
        "require_ready": contract_model._bool(require_ready, "require ready"),
        "require_change": contract_model._bool(require_change, "require change"),
        "allow_unchanged": contract_model._bool(allow_unchanged, "allow unchanged"),
    }


def _check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> contract_model.PolicyCheck:
    body = {"check_id": check_id, "passed": bool(passed), "observed": observed, "required": required, "detail": detail, "content_address": CHECK_PREFIX + ":pending"}
    provisional = contract_model.PolicyCheck(**body)
    return contract_model.PolicyCheck(**(body | {"content_address": contract_model.address_check(provisional)}))


def _checks(diff: Any, settings: Mapping[str, Any]) -> tuple[contract_model.PolicyCheck, ...]:
    active = diff.added_count + diff.removed_count + diff.changed_count
    observed_changes = tuple(sorted({item.change for item in diff.items}, key=diff_model.CHANGES.index))
    return (
        _check("policy-diff-address", diff_model.address_diff(diff) == diff.content_address, diff.content_address, "replayable", "packet-package catalog diff address is valid"),
        _check("policy-diff-replay", diff_model.verify_diff(diff).content_address == diff.content_address, "replayed", "replayed", "typed packet-package catalog diff reload is valid"),
        _check("policy-added-budget", diff.added_count <= settings["maximum_added"], diff.added_count, settings["maximum_added"], "added packet-package catalog entries remain within budget"),
        _check("policy-removed-budget", diff.removed_count <= settings["maximum_removed"], diff.removed_count, settings["maximum_removed"], "removed packet-package catalog entries remain within budget"),
        _check("policy-changed-budget", diff.changed_count <= settings["maximum_changed"], diff.changed_count, settings["maximum_changed"], "changed packet-package catalog entries remain within budget"),
        _check("policy-total-change-budget", active <= settings["maximum_total_changes"], active, settings["maximum_total_changes"], "active packet-package catalog changes remain within the total budget"),
        _check("policy-change-allowlist", all(item.change in settings["allowed_changes"] for item in diff.items), observed_changes, settings["allowed_changes"], "all packet-package catalog entry changes are allowed"),
        _check("policy-direction-allowlist", diff.direction in settings["allowed_directions"], diff.direction, settings["allowed_directions"], "packet-package catalog diff direction is allowed"),
        _check("policy-transition-allowlist", diff.state_transition in settings["allowed_transitions"], diff.state_transition, settings["allowed_transitions"], "packet-package catalog posture transition is allowed"),
        _check("policy-left-posture-allowlist", diff.left_posture in settings["allowed_left_postures"], diff.left_posture, settings["allowed_left_postures"], "left packet-package catalog posture is allowed"),
        _check("policy-right-posture-allowlist", diff.right_posture in settings["allowed_right_postures"], diff.right_posture, settings["allowed_right_postures"], "right packet-package catalog posture is allowed"),
        _check("policy-ready-requirement", not settings["require_ready"] or diff.right_posture == "ready", diff.right_posture, "ready" if settings["require_ready"] else "not required", "right packet-package catalog satisfies the release-ready requirement"),
        _check("policy-change-requirement", not settings["require_change"] or active > 0, active, "greater than zero" if settings["require_change"] else "not required", "required packet-package catalog change posture is satisfied"),
        _check("policy-required-changes", set(settings["required_changes"]).issubset(set(observed_changes)), observed_changes, settings["required_changes"], "required packet-package catalog change kinds are present"),
        _check("policy-unchanged-control", settings["allow_unchanged"] or diff.unchanged_count == 0, diff.unchanged_count, "allowed" if settings["allow_unchanged"] else 0, "unchanged packet-package catalog evidence is explicitly controlled"),
    )


def build_policy(diff: Any, *, policy_id: str = DEFAULT_POLICY_ID, maximum_added: int = 0, maximum_removed: int = 0, maximum_changed: int = 0, maximum_total_changes: int = 0, allowed_changes: Sequence[str] = diff_model.CHANGES, allowed_directions: Sequence[str] = diff_model.DIRECTIONS, allowed_transitions: Sequence[str] = diff_model.STATE_TRANSITIONS, allowed_left_postures: Sequence[str] = diff_model.POSTURES, allowed_right_postures: Sequence[str] = diff_model.POSTURES, required_changes: Sequence[str] = (), require_ready: bool = True, require_change: bool = False, allow_unchanged: bool = True) -> contract_model.Policy:
    value = diff_model.verify_diff(diff)
    settings = _settings(maximum_added, maximum_removed, maximum_changed, maximum_total_changes, allowed_changes, allowed_directions, allowed_transitions, allowed_left_postures, allowed_right_postures, required_changes, require_ready, require_change, allow_unchanged)
    checks = _checks(value, settings)
    accepted = all(item.passed for item in checks)
    body = {"policy_id": policy_id, "version": VERSION, "boundary": BOUNDARY, "diff_address": value.content_address, **settings, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": accepted, "state": "ready" if accepted else "blocked", "checks": checks, "content_address": POLICY_PREFIX + ":pending"}
    provisional = contract_model.Policy(**body)
    return contract_model.Policy(**(body | {"content_address": contract_model.address_policy(provisional)}))


def strict_policy(diff: Any, *, policy_id: str = "strict-" + DEFAULT_POLICY_ID) -> contract_model.Policy:
    return build_policy(diff, policy_id=policy_id, maximum_added=0, maximum_removed=0, maximum_changed=0, maximum_total_changes=0, allowed_changes=("unchanged",), allowed_directions=("unchanged",), allowed_transitions=("same-ready", "same-blocked"), allowed_left_postures=("ready", "blocked"), allowed_right_postures=("ready",), require_ready=True, require_change=False, allow_unchanged=True)


def release_policy(diff: Any, *, policy_id: str = "release-" + DEFAULT_POLICY_ID, maximum_added: int = 32, maximum_removed: int = 32, maximum_changed: int = 256, maximum_total_changes: int = 256, allowed_changes: Sequence[str] = diff_model.CHANGES, allowed_directions: Sequence[str] = diff_model.DIRECTIONS, allowed_transitions: Sequence[str] = diff_model.STATE_TRANSITIONS, allowed_left_postures: Sequence[str] = diff_model.POSTURES, allowed_right_postures: Sequence[str] = diff_model.POSTURES, required_changes: Sequence[str] = (), require_ready: bool = True, require_change: bool = False, allow_unchanged: bool = True) -> contract_model.Policy:
    return build_policy(diff, policy_id=policy_id, maximum_added=maximum_added, maximum_removed=maximum_removed, maximum_changed=maximum_changed, maximum_total_changes=maximum_total_changes, allowed_changes=allowed_changes, allowed_directions=allowed_directions, allowed_transitions=allowed_transitions, allowed_left_postures=allowed_left_postures, allowed_right_postures=allowed_right_postures, required_changes=required_changes, require_ready=require_ready, require_change=require_change, allow_unchanged=allow_unchanged)


def verify_policy(value: Any) -> contract_model.Policy:
    policy = value if isinstance(value, contract_model.Policy) else load_policy(value)
    if contract_model.address_policy(policy) != policy.content_address or _has_forbidden_key(policy.to_dict()):
        raise ValidationError("packet-package catalog diff policy address or public boundary does not replay")
    return contract_model.Policy.from_mapping(policy.to_dict())


def load_policy(value: bytes | bytearray | str | Path | Mapping[str, Any]) -> contract_model.Policy:
    if isinstance(value, Mapping):
        raw = value
    elif isinstance(value, (bytes, bytearray)):
        raw = _strict_json_loads(bytes(value).decode("utf-8"))
    else:
        raw = _strict_json_loads(read_text(value, field="packet-package catalog diff policy", max_bytes=16 * 1024 * 1024))
    return contract_model.Policy.from_mapping(raw)


def policy_from_mapping(value: Mapping[str, Any]) -> contract_model.Policy:
    return contract_model.Policy.from_mapping(value)


def policy_json(value: Any) -> str:
    return canonical_json(verify_policy(value).to_dict()) + "\n"


def write_policy(value: Any, destination: str | Path, *, allow_existing: bool = False) -> contract_model.Policy:
    policy = verify_policy(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("packet-package catalog diff policy destination already exists")
    if path.exists() and not path.is_file():
        raise ValidationError("packet-package catalog diff policy destination is not a file")
    _validate_parent(path.parent, "packet-package catalog diff policy destination")
    atomic_write_text(path, policy_json(policy), field="packet-package catalog diff policy destination")
    return policy


def query_policy(value: Any, *, passed: bool | None = None, check_id: str = "", text: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    policy = verify_policy(value)
    if passed is not None and not isinstance(passed, bool):
        raise ValidationError("packet-package catalog diff policy passed filter must be boolean")
    check_id = _text(check_id, "packet-package catalog diff policy check filter", 256, required=False)
    if check_id and check_id not in POLICY_CHECK_IDS:
        raise ValidationError("packet-package catalog diff policy check filter is unsupported")
    text = _text(text, "packet-package catalog diff policy text filter", required=False)
    offset = _count(offset, "packet-package catalog diff policy query offset", len(policy.checks))
    limit = _count(limit, "packet-package catalog diff policy query limit", MAX_LIMIT, positive=True)
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
    lines = ["# Packet-Package Catalog Diff Policy", "", f"- Policy: `{policy.policy_id}`", f"- State: **{policy.state}**", f"- Passed / failed: **{policy.passed_count} / {policy.failed_count}**", f"- Diff: `{policy.diff_address}`", f"- Address: `{policy.content_address}`", "", "| check | passed | detail |", "| --- | --- | --- |"]
    lines.extend(f"| `{item.check_id}` | {str(item.passed).lower()} | {item.detail} |" for item in policy.checks)
    return "\n".join(lines) + "\n"


__all__ = ["BOUNDARY", "CHECK_FIELDS", "CHECK_PREFIX", "DEFAULT_POLICY_ID", "POLICY_CHECK_IDS", "POLICY_FIELDS", "POLICY_PREFIX", "STATES", "VERSION", "Policy", "PolicyCheck", "address_check", "address_policy", "build_policy", "capabilities", "check_schema", "load_policy", "policy_csv", "policy_from_mapping", "policy_json", "policy_schema", "query_policy", "release_policy", "render_policy_markdown", "strict_policy", "verify_policy", "write_policy"]

address_check = contract_model.address_check
address_policy = contract_model.address_policy
Policy = contract_model.Policy
PolicyCheck = contract_model.PolicyCheck
capabilities = contract_model.capabilities
check_schema = contract_model.check_schema
policy_schema = contract_model.policy_schema
