"""Strict and release policy gates for source-free release-bundle diffs."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff as diff_model
from . import downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_contracts as contract_model
from ._safe_persistence import _validate_parent, atomic_write_text, read_text
from .errors import ValidationError
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


def _ordered_labels(value: Any, field: str, allowed: Sequence[str]) -> tuple[str, ...]:
    return contract_model._ordered_labels(value, field, allowed)


def _settings(maximum_added: int, maximum_removed: int, maximum_changed: int, maximum_member_changed: int, allowed_resources: Sequence[str], allowed_changes: Sequence[str], allowed_directions: Sequence[str], allowed_transitions: Sequence[str], require_ready: bool, require_change: bool, allow_unchanged: bool) -> dict[str, Any]:
    return {
        "maximum_added": _count(maximum_added, "maximum added rows", diff_model.MAX_ITEMS),
        "maximum_removed": _count(maximum_removed, "maximum removed rows", diff_model.MAX_ITEMS),
        "maximum_changed": _count(maximum_changed, "maximum changed rows", diff_model.MAX_ITEMS),
        "maximum_member_changed": _count(maximum_member_changed, "maximum member changes", diff_model.MAX_ITEMS),
        "allowed_resources": _ordered_labels(allowed_resources, "allowed resources", diff_model.RESOURCES),
        "allowed_changes": _ordered_labels(allowed_changes, "allowed changes", diff_model.CHANGES),
        "allowed_directions": _ordered_labels(allowed_directions, "allowed directions", diff_model.DIRECTIONS),
        "allowed_transitions": _ordered_labels(allowed_transitions, "allowed transitions", diff_model.STATE_TRANSITIONS),
        "require_ready": contract_model._bool(require_ready, "require ready"),
        "require_change": contract_model._bool(require_change, "require change"),
        "allow_unchanged": contract_model._bool(allow_unchanged, "allow unchanged"),
    }


def _check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> contract_model.DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyCheck:
    body = {"check_id": check_id, "passed": bool(passed), "observed": observed, "required": required, "detail": detail, "content_address": CHECK_PREFIX + ":pending"}
    provisional = contract_model.DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyCheck(**body)
    return contract_model.DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyCheck(**(body | {"content_address": contract_model.address_check(provisional)}))


def _checks(diff: Any, settings: Mapping[str, Any]) -> tuple[contract_model.DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyCheck, ...]:
    added = sum(item.change == "added" for item in diff.items)
    removed = sum(item.change == "removed" for item in diff.items)
    changed = sum(item.change == "changed" for item in diff.items)
    member_changed = sum(item.resource == "members" and item.change == "changed" for item in diff.items)
    active = added + removed + changed
    return (
        _check("policy-diff-address", contract_model._address(diff.content_address, "diff address", diff_model.DIFF_PREFIX) == diff.content_address, diff.content_address, "replayable", "diff address is valid"),
        _check("policy-diff-replay", diff_model.verify_diff(diff).content_address == diff.content_address, "replayed", "replayed", "typed diff reload is valid"),
        _check("policy-added-budget", added <= settings["maximum_added"], added, settings["maximum_added"], "added rows remain within budget"),
        _check("policy-removed-budget", removed <= settings["maximum_removed"], removed, settings["maximum_removed"], "removed rows remain within budget"),
        _check("policy-changed-budget", changed <= settings["maximum_changed"], changed, settings["maximum_changed"], "changed rows remain within budget"),
        _check("policy-member-budget", member_changed <= settings["maximum_member_changed"], member_changed, settings["maximum_member_changed"], "changed member rows remain within budget"),
        _check("policy-resource-allowlist", all(item.resource in settings["allowed_resources"] for item in diff.items), sorted({item.resource for item in diff.items}, key=diff_model.RESOURCES.index), settings["allowed_resources"], "all diff resources are allowed"),
        _check("policy-change-allowlist", all(item.change in settings["allowed_changes"] for item in diff.items), sorted({item.change for item in diff.items}, key=diff_model.CHANGES.index), settings["allowed_changes"], "all diff changes are allowed"),
        _check("policy-direction-allowlist", diff.direction in settings["allowed_directions"], diff.direction, settings["allowed_directions"], "diff direction is allowed"),
        _check("policy-transition-allowlist", diff.state_transition in settings["allowed_transitions"], diff.state_transition, settings["allowed_transitions"], "state transition is allowed"),
        _check("policy-ready-requirement", not settings["require_ready"] or (diff.right_release_state == "ready" and diff.right_release_eligible), {"state": diff.right_release_state, "eligible": diff.right_release_eligible}, "ready" if settings["require_ready"] else "not required", "right release posture satisfies the gate"),
        _check("policy-change-requirement", not settings["require_change"] or active > 0, active, "greater than zero" if settings["require_change"] else "not required", "required change posture is satisfied"),
        _check("policy-unchanged-control", settings["allow_unchanged"] or diff.unchanged_count == 0, diff.unchanged_count, "allowed" if settings["allow_unchanged"] else 0, "unchanged evidence is explicitly controlled"),
    )


def build_policy(diff: Any, *, policy_id: str = DEFAULT_POLICY_ID, maximum_added: int = 0, maximum_removed: int = 0, maximum_changed: int = 0, maximum_member_changed: int = 0, allowed_resources: Sequence[str] = diff_model.RESOURCES, allowed_changes: Sequence[str] = diff_model.CHANGES, allowed_directions: Sequence[str] = diff_model.DIRECTIONS, allowed_transitions: Sequence[str] = diff_model.STATE_TRANSITIONS, require_ready: bool = True, require_change: bool = False, allow_unchanged: bool = True) -> contract_model.DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicy:
    value = diff_model.verify_diff(diff)
    settings = _settings(maximum_added, maximum_removed, maximum_changed, maximum_member_changed, allowed_resources, allowed_changes, allowed_directions, allowed_transitions, require_ready, require_change, allow_unchanged)
    checks = _checks(value, settings)
    body = {"policy_id": policy_id, "version": VERSION, "boundary": BOUNDARY, "diff_address": value.content_address, **settings, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": all(item.passed for item in checks), "state": "ready" if all(item.passed for item in checks) else "blocked", "checks": checks, "content_address": POLICY_PREFIX + ":pending"}
    provisional = contract_model.DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicy(**body)
    return contract_model.DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicy(**(body | {"content_address": contract_model.address_policy(provisional)}))


def strict_policy(diff: Any, *, policy_id: str = "strict-" + DEFAULT_POLICY_ID) -> contract_model.DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicy:
    return build_policy(diff, policy_id=policy_id, maximum_added=0, maximum_removed=0, maximum_changed=0, maximum_member_changed=0, allowed_changes=("unchanged",), allowed_directions=("unchanged",), allowed_transitions=("same-ready", "same-blocked"), require_ready=True, require_change=False, allow_unchanged=True)


def release_policy(diff: Any, *, policy_id: str = "release-" + DEFAULT_POLICY_ID, maximum_added: int = 32, maximum_removed: int = 32, maximum_changed: int = 256, maximum_member_changed: int = 64, allowed_resources: Sequence[str] = diff_model.RESOURCES, allowed_changes: Sequence[str] = diff_model.CHANGES, allowed_directions: Sequence[str] = diff_model.DIRECTIONS, allowed_transitions: Sequence[str] = diff_model.STATE_TRANSITIONS, require_ready: bool = True, require_change: bool = False, allow_unchanged: bool = True) -> contract_model.DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicy:
    return build_policy(diff, policy_id=policy_id, maximum_added=maximum_added, maximum_removed=maximum_removed, maximum_changed=maximum_changed, maximum_member_changed=maximum_member_changed, allowed_resources=allowed_resources, allowed_changes=allowed_changes, allowed_directions=allowed_directions, allowed_transitions=allowed_transitions, require_ready=require_ready, require_change=require_change, allow_unchanged=allow_unchanged)


def verify_policy(value: Any) -> contract_model.DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicy:
    policy = value if isinstance(value, contract_model.DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicy) else load_policy(value)
    if contract_model.address_policy(policy) != policy.content_address:
        raise ValidationError("release bundle diff policy address does not replay")
    return contract_model.DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicy.from_mapping(policy.to_dict())


def load_policy(value: bytes | bytearray | str | Path | Mapping[str, Any]) -> contract_model.DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicy:
    if isinstance(value, Mapping):
        raw = value
    elif isinstance(value, (bytes, bytearray)):
        raw = _strict_json_loads(bytes(value).decode("utf-8"))
    else:
        raw = _strict_json_loads(read_text(value, field="downloaded data release bundle diff policy", max_bytes=16 * 1024 * 1024))
    return contract_model.DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicy.from_mapping(raw)


def policy_from_mapping(value: Mapping[str, Any]) -> contract_model.DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicy:
    return contract_model.DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicy.from_mapping(value)


def policy_json(value: Any) -> str:
    return canonical_json(verify_policy(value).to_dict()) + "\n"


def write_policy(value: Any, destination: str | Path, *, allow_existing: bool = False) -> contract_model.DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicy:
    policy = verify_policy(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("release bundle diff policy destination already exists")
    if path.exists() and not path.is_file():
        raise ValidationError("release bundle diff policy destination is not a file")
    _validate_parent(path.parent, "release bundle diff policy destination")
    atomic_write_text(path, policy_json(policy), field="release bundle diff policy destination")
    return policy


def query_policy(value: Any, *, passed: bool | None = None, check_id: str = "", text: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    policy = verify_policy(value)
    if passed is not None and not isinstance(passed, bool):
        raise ValidationError("release bundle diff policy passed filter must be boolean")
    check_id = _text(check_id, "release bundle diff policy check filter", 256, required=False)
    if check_id and check_id not in POLICY_CHECK_IDS:
        raise ValidationError("release bundle diff policy check filter is unsupported")
    text = _text(text, "release bundle diff policy text filter", required=False)
    offset = _count(offset, "release bundle diff policy query offset", len(policy.checks))
    limit = _count(limit, "release bundle diff policy query limit", MAX_LIMIT, positive=True)
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
    lines = ["# Downloaded Data Release Bundle Diff Policy", "", f"- Policy: `{policy.policy_id}`", f"- State: **{policy.state}**", f"- Passed / failed: **{policy.passed_count} / {policy.failed_count}**", f"- Diff: `{policy.diff_address}`", f"- Address: `{policy.content_address}`", "", "| check | passed | detail |", "| --- | --- | --- |"]
    lines.extend(f"| `{item.check_id}` | {str(item.passed).lower()} | {item.detail} |" for item in policy.checks)
    return "\n".join(lines) + "\n"


def policy_schema() -> dict[str, Any]:
    return contract_model.policy_schema()


def check_schema() -> dict[str, Any]:
    return contract_model.check_schema()


def capabilities() -> dict[str, Any]:
    return contract_model.capabilities()


__all__ = [
    "BOUNDARY", "CHECK_FIELDS", "CHECK_PREFIX", "DEFAULT_POLICY_ID", "POLICY_CHECK_IDS", "POLICY_FIELDS", "POLICY_PREFIX", "STATES", "VERSION", "DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicy", "DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyCheck", "address_check", "address_policy", "build_policy", "capabilities", "check_schema", "load_policy", "policy_csv", "policy_from_mapping", "policy_json", "policy_schema", "query_policy", "release_policy", "render_policy_markdown", "strict_policy", "verify_policy", "write_policy",
]

address_check = contract_model.address_check
address_policy = contract_model.address_policy
DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicy = contract_model.DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicy
DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyCheck = contract_model.DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyCheck
