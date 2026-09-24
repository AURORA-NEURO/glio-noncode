"""Evaluate strict and release policies over packet catalog diffs."""

# ruff: noqa: E501, F403, F405

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ._safe_persistence import _validate_parent, atomic_write_bytes, read_bytes
from .errors import ValidationError
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff import (
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_value,
)
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_contracts import (
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiff,
)
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_contracts import *
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash

_UTF8 = "utf-8"
_MAX_JSON_BYTES = 16 * 1024 * 1024


def build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy(*, policy_id: str = "glio-noncode-module-workbench-release-bundle-packet-catalog-diff-strict", maximum_added_count: int = 0, maximum_changed_count: int = 0, maximum_removed_count: int = 0, allowed_directions: tuple[str, ...] = ("improved", "unchanged"), allowed_state_transitions: tuple[str, ...] = ("blocked_to_accepted", "unchanged"), require_accepted_catalogs: bool = True, allow_unchanged: bool = True) -> Any:
    body = {"policy_id": policy_id, "maximum_added_count": maximum_added_count, "maximum_changed_count": maximum_changed_count, "maximum_removed_count": maximum_removed_count, "allowed_directions": tuple(sorted(allowed_directions)), "allowed_state_transitions": tuple(sorted(allowed_state_transitions)), "require_accepted_catalogs": require_accepted_catalogs, "allow_unchanged": allow_unchanged}
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicy(**body, content_address="pending")
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicy(**body, content_address=address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy(provisional))


def default_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy() -> Any:
    """Return a no-change policy for protected baselines."""
    return build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy()


def release_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy() -> Any:
    """Return a bounded policy for ordinary accepted catalog growth."""
    return build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy(policy_id="glio-noncode-module-workbench-release-bundle-packet-catalog-diff-release", maximum_added_count=2, maximum_changed_count=2, maximum_removed_count=1, allowed_directions=("changed", "improved", "unchanged"), allowed_state_transitions=("added", "blocked_to_accepted", "changed", "unchanged"), require_accepted_catalogs=True, allow_unchanged=True)


def _check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> Any:
    body = {"check_id": check_id, "passed": bool(passed), "observed": observed, "required": required, "detail": detail}
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyCheck(**body, content_address="pending")
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyCheck(**body, content_address=address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_check(provisional))


def evaluate_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy(value: Any, policy: Any = None) -> Any:
    """Evaluate every budget and retain failed evidence instead of discarding it."""
    if not isinstance(value, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiff):
        raise ValidationError("packet catalog diff policy requires a typed comparison")
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_value(value)
    selected = policy or default_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy()
    if not isinstance(selected, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicy):
        raise ValidationError("packet catalog diff policy must be typed")
    checks = (_check("accepted-catalogs", not selected.require_accepted_catalogs or (value.previous_catalog_state == "accepted" and value.current_catalog_state == "accepted"), (value.previous_catalog_state, value.current_catalog_state), "accepted/accepted" if selected.require_accepted_catalogs else "not-required", "both compared catalogs are accepted when required"), _check("added-count", value.added_count <= selected.maximum_added_count, value.added_count, f"<={selected.maximum_added_count}", "candidate-only packets remain within the addition budget"), _check("changed-count", value.changed_count <= selected.maximum_changed_count, value.changed_count, f"<={selected.maximum_changed_count}", "changed packet descriptors remain within the change budget"), _check("classification-conservation", value.added_count + value.changed_count + value.removed_count + value.unchanged_count == len(value.changes), len(value.changes), value.added_count + value.changed_count + value.removed_count + value.unchanged_count, "classification counts conserve every packet identity"), _check("direction", value.direction.value in selected.allowed_directions, value.direction.value, selected.allowed_directions, "aggregate direction is admitted by the policy"), _check("removed-count", value.removed_count <= selected.maximum_removed_count, value.removed_count, f"<={selected.maximum_removed_count}", "baseline-only packets remain within the removal budget"), _check("state-transition", value.state_transition.value in selected.allowed_state_transitions, value.state_transition.value, selected.allowed_state_transitions, "aggregate catalog transition is admitted by the policy"), _check("unchanged-control", selected.allow_unchanged or value.unchanged_count == 0, value.unchanged_count, "allowed" if selected.allow_unchanged else 0, "unchanged packet descriptors follow the policy control"), _check("public-boundary", not _has_forbidden_key(value.to_dict()) and not _has_forbidden_key(selected.to_dict()), "clean" if not _has_forbidden_key(value.to_dict()) and not _has_forbidden_key(selected.to_dict()) else "forbidden-key", "clean", "policy and comparison contain only public aggregate fields"))
    ordered = tuple(sorted(checks, key=lambda item: item.check_id))
    body = {"diff_address": value.content_address, "policy": selected, "checks": ordered, "accepted": all(item.passed for item in ordered)}
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyGate(**body, content_address="pending")
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyGate(**body, content_address=address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_gate(provisional))


def verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy(value: Any) -> Any:
    if not isinstance(value, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicy):
        raise ValidationError("typed packet catalog diff policy verification requires a policy")
    if address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy(value) != value.content_address:
        raise ValidationError("packet catalog diff policy address mismatch")
    return value


def verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_gate(value: Any) -> Any:
    if not isinstance(value, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyGate):
        raise ValidationError("typed packet catalog diff gate verification requires a gate")
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy(value.policy)
    for check in value.checks:
        if address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_check(check) != check.content_address:
            raise ValidationError(f"packet catalog diff policy check address mismatch: {check.check_id}")
    if address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_gate(value) != value.content_address:
        raise ValidationError("packet catalog diff policy gate address mismatch")
    return value


def _policy_from_mapping(value: Mapping[str, Any]) -> Any:
    return verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy(ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicy(policy_id=str(value.get("policy_id", "")), maximum_added_count=value.get("maximum_added_count"), maximum_changed_count=value.get("maximum_changed_count"), maximum_removed_count=value.get("maximum_removed_count"), allowed_directions=tuple(value.get("allowed_directions", ())), allowed_state_transitions=tuple(value.get("allowed_state_transitions", ())), require_accepted_catalogs=value.get("require_accepted_catalogs"), allow_unchanged=value.get("allow_unchanged"), content_address=str(value.get("content_address", ""))))


def _gate_from_mapping(value: Mapping[str, Any]) -> Any:
    raw_policy, raw_checks = value.get("policy"), value.get("checks")
    if not isinstance(raw_policy, Mapping) or not isinstance(raw_checks, list):
        raise ValidationError("packet catalog diff policy gate payload is invalid")
    checks = tuple(ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyCheck(check_id=str(item.get("check_id", "")), passed=item.get("passed"), observed=item.get("observed"), required=item.get("required"), detail=str(item.get("detail", "")), content_address=str(item.get("content_address", ""))) for item in raw_checks if isinstance(item, Mapping))
    return verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_gate(ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyGate(diff_address=str(value.get("diff_address", "")), policy=_policy_from_mapping(raw_policy), checks=checks, accepted=value.get("accepted"), content_address=str(value.get("content_address", ""))))


def load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_gate(value: bytes | bytearray | str | Path | Mapping[str, Any]) -> Any:
    if isinstance(value, Mapping):
        return _gate_from_mapping(value)
    raw = bytes(value) if isinstance(value, (bytes, bytearray)) else read_bytes(value, field="packet catalog diff policy gate", max_bytes=_MAX_JSON_BYTES)
    try:
        parsed = _strict_json_loads(raw.decode(_UTF8))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValidationError(f"cannot parse packet catalog diff policy gate: {exc}") from exc
    if not isinstance(parsed, Mapping) or raw != (canonical_json(parsed) + "\n").encode(_UTF8):
        raise ValidationError("packet catalog diff policy gate must be canonical JSON object")
    return _gate_from_mapping(parsed)


def query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy(value: Any, *, passed: bool | None = None, text: str | None = None, offset: int = 0, limit: int = MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_DEFAULT_LIMIT) -> dict[str, Any]:
    if offset < 0 or limit < 1 or limit > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_MAX_LIMIT:
        raise ValidationError("packet catalog diff policy paging is invalid")
    gate = value if isinstance(value, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyGate) else load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_gate(value)
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_gate(gate)
    rows = [item.to_dict() for item in gate.checks]
    if passed is not None:
        rows = [item for item in rows if item["passed"] is passed]
    if text:
        rows = [item for item in rows if text.casefold() in canonical_json(item).casefold()]
    body = {"gate_address": gate.content_address, "diff_address": gate.diff_address, "policy_address": gate.policy_address, "passed": passed, "text": text, "total": len(rows), "offset": offset, "limit": limit, "items": rows, "accepted": gate.accepted}
    return body | {"content_address": content_hash(body, prefix=MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PREFIX + "-query")}


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_json(value: Any) -> str:
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_gate(value)
    return canonical_json(value.to_dict()) + "\n"


def write_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy(value: Any, destination: str | Path, *, allow_existing: bool = False) -> Any:
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_gate(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("packet catalog diff policy destination already exists")
    if path.exists() and not path.is_file():
        raise ValidationError("packet catalog diff policy destination is not a file")
    _validate_parent(path.parent, "packet catalog diff policy destination")
    atomic_write_bytes(path, module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_json(value).encode(_UTF8), field="packet catalog diff policy destination")
    return value


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_csv(value: Any, *, passed: bool | None = None, text: str | None = None, offset: int = 0, limit: int = MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_DEFAULT_LIMIT) -> str:
    result = query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy(value, passed=passed, text=text, offset=offset, limit=limit)
    output = io.StringIO(newline="")
    fields = ("check_id", "passed", "observed", "required", "detail", "content_address")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(result["items"])
    return output.getvalue()


def render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_markdown(value: Any) -> str:
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_gate(value)
    lines = ["# Packet Review Catalog Diff Policy", "", f"- Gate: `{value.content_address}`", f"- Diff: `{value.diff_address}`", f"- Policy: `{value.policy.policy_id}`", f"- Passed / failed: **{value.passed_count} / {value.failed_count}**", f"- Accepted: **{str(value.accepted).lower()}**", "", "| Check | Passed | Observed | Required | Detail |", "| --- | --- | --- | --- | --- |"]
    lines.extend(f"| `{item.check_id}` | {str(item.passed).lower()} | `{item.observed}` | `{item.required}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_schema() -> dict[str, Any]:
    return {"version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_VERSION, "boundary": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_BOUNDARY, "resources": ["checks", "summary"], "thresholds": ["maximum_added_count", "maximum_changed_count", "maximum_removed_count", "allowed_directions", "allowed_state_transitions", "require_accepted_catalogs", "allow_unchanged"], "depends_on": "public_aggregate_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff", "source_free": True, "path_free": True, "timestamp_free": True}


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_capabilities() -> dict[str, Any]:
    operations = ("build_policy", "evaluate_added_budget", "evaluate_changed_budget", "evaluate_removed_budget", "evaluate_direction", "evaluate_state_transition", "evaluate_accepted_catalogs", "evaluate_unchanged_control", "query_checks", "export_json", "export_csv", "render_markdown", "verify_addresses")
    return {"version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_VERSION, "operation_count": len(operations), "operations": list(operations), "deterministic": True, "source_free": True, "read_only": True}


__all__ = [name for name in globals() if name.startswith("build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy") or name.startswith("default_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy") or name.startswith("evaluate_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy") or name.startswith("load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy") or name.startswith("module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy") or name.startswith("query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy") or name.startswith("release_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy") or name.startswith("render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy") or name.startswith("verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy") or name.startswith("write_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy")]
