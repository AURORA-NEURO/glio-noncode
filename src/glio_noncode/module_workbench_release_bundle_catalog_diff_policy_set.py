"""Evaluate a catalog diff against a deterministic policy set."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ._safe_persistence import _validate_parent, atomic_write_bytes, read_bytes
from .errors import ValidationError
from .module_workbench_release_bundle_catalog_diff_contracts import (
    ModuleWorkbenchReleaseBundleCatalogDiff,
)
from .module_workbench_release_bundle_catalog_diff_policy import (
    default_module_workbench_release_bundle_catalog_diff_policy,
    evaluate_module_workbench_release_bundle_catalog_diff_policy,
    release_module_workbench_release_bundle_catalog_diff_policy,
    verify_module_workbench_release_bundle_catalog_diff_policy,
)
from .module_workbench_release_bundle_catalog_diff_policy_contracts import (
    ModuleWorkbenchReleaseBundleCatalogDiffPolicy,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicyGate,
)
from .module_workbench_release_bundle_catalog_diff_policy_set_contracts import (
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_BOUNDARY,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_DEFAULT_LIMIT,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_MAX_LIMIT,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_VERSION,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySet,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetGate,
    address_module_workbench_release_bundle_catalog_diff_policy_set,
    address_module_workbench_release_bundle_catalog_diff_policy_set_gate,
)
from .serialization import _strict_json_loads, canonical_json, content_hash

_UTF8 = "utf-8"
_MAX_JSON_BYTES = 32 * 1024 * 1024


def build_module_workbench_release_bundle_catalog_diff_policy_set(
    policies: Sequence[ModuleWorkbenchReleaseBundleCatalogDiffPolicy],
    *,
    policy_set_id: str = "module-workbench-release-bundle-catalog-diff-policy-set",
    selection_mode: str = "all",
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySet:
    """Build a sorted policy set with a stable content address."""

    if not isinstance(policies, (tuple, list)):
        raise ValidationError("policy set policies must be a sequence")
    ordered = tuple(sorted(policies, key=lambda item: item.policy_id))
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicySet(
        policy_set_id=policy_set_id,
        selection_mode=selection_mode,
        policies=ordered,
        content_address="pending",
    )
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySet(
        policy_set_id=policy_set_id,
        selection_mode=selection_mode,
        policies=ordered,
        content_address=address_module_workbench_release_bundle_catalog_diff_policy_set(
            provisional
        ),
    )


def default_module_workbench_release_bundle_catalog_diff_policy_set() -> (
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySet
):
    """Return a one-policy strict set with conjunctive semantics."""

    return build_module_workbench_release_bundle_catalog_diff_policy_set(
        (default_module_workbench_release_bundle_catalog_diff_policy(),),
        policy_set_id="module-workbench-release-bundle-catalog-diff-strict-set",
    )


def strict_release_module_workbench_release_bundle_catalog_diff_policy_set() -> (
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySet
):
    """Return strict and release policies with explicit alternative admission."""

    return build_module_workbench_release_bundle_catalog_diff_policy_set(
        (
            default_module_workbench_release_bundle_catalog_diff_policy(),
            release_module_workbench_release_bundle_catalog_diff_policy(),
        ),
        policy_set_id="module-workbench-release-bundle-catalog-diff-strict-or-release-set",
        selection_mode="any",
    )


def evaluate_module_workbench_release_bundle_catalog_diff_policy_set(
    value: ModuleWorkbenchReleaseBundleCatalogDiff,
    policy_set: ModuleWorkbenchReleaseBundleCatalogDiffPolicySet | None = None,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetGate:
    """Evaluate every policy and conserve the selected any/all aggregate decision."""

    if not isinstance(value, ModuleWorkbenchReleaseBundleCatalogDiff):
        raise ValidationError("policy-set evaluation requires a typed catalog diff")
    selected = policy_set or default_module_workbench_release_bundle_catalog_diff_policy_set()
    verify_module_workbench_release_bundle_catalog_diff_policy_set(selected)
    gates = tuple(
        evaluate_module_workbench_release_bundle_catalog_diff_policy(value, policy)
        for policy in selected.policies
    )
    body = {
        "diff_address": value.content_address,
        "policy_set": selected,
        "gates": gates,
        "accepted": (
            any(item.accepted for item in gates)
            if selected.selection_mode == "any"
            else all(item.accepted for item in gates)
        ),
    }
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetGate(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetGate(
        **body,
        content_address=address_module_workbench_release_bundle_catalog_diff_policy_set_gate(
            provisional
        ),
    )


def verify_module_workbench_release_bundle_catalog_diff_policy_set(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySet,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySet:
    if not isinstance(value, ModuleWorkbenchReleaseBundleCatalogDiffPolicySet):
        raise ValidationError("policy-set verification requires a typed policy set")
    for policy in value.policies:
        verify_module_workbench_release_bundle_catalog_diff_policy(policy)
    if (
        address_module_workbench_release_bundle_catalog_diff_policy_set(value)
        != value.content_address
    ):
        raise ValidationError("policy-set address mismatch")
    return value


def verify_module_workbench_release_bundle_catalog_diff_policy_set_gate(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetGate,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetGate:
    if not isinstance(value, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetGate):
        raise ValidationError("policy-set gate verification requires a typed gate")
    verify_module_workbench_release_bundle_catalog_diff_policy_set(value.policy_set)
    for gate in value.gates:
        from .module_workbench_release_bundle_catalog_diff_policy import (
            verify_module_workbench_release_bundle_catalog_diff_policy_gate,
        )

        verify_module_workbench_release_bundle_catalog_diff_policy_gate(gate)
    if (
        address_module_workbench_release_bundle_catalog_diff_policy_set_gate(value)
        != value.content_address
    ):
        raise ValidationError("policy-set gate address mismatch")
    return value


def _policy_from_mapping(value: Mapping[str, Any]) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicy:
    return verify_module_workbench_release_bundle_catalog_diff_policy(
        ModuleWorkbenchReleaseBundleCatalogDiffPolicy(
            policy_id=str(value.get("policy_id", "")),
            maximum_added_count=value.get("maximum_added_count"),
            maximum_changed_count=value.get("maximum_changed_count"),
            maximum_removed_count=value.get("maximum_removed_count"),
            allowed_directions=tuple(value.get("allowed_directions", ())),
            allowed_state_transitions=tuple(value.get("allowed_state_transitions", ())),
            require_accepted_catalogs=value.get("require_accepted_catalogs"),
            allow_unchanged=value.get("allow_unchanged"),
            content_address=str(value.get("content_address", "")),
        )
    )


def _set_from_mapping(value: Mapping[str, Any]) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySet:
    raw_policies = value.get("policies")
    if not isinstance(raw_policies, list) or not raw_policies:
        raise ValidationError("policy-set payload policies are invalid")
    if any(not isinstance(item, Mapping) for item in raw_policies):
        raise ValidationError("policy-set payload contains an invalid policy")
    policies = tuple(_policy_from_mapping(item) for item in raw_policies)
    selected = build_module_workbench_release_bundle_catalog_diff_policy_set(
        policies,
        policy_set_id=str(value.get("policy_set_id", "")),
        selection_mode=str(value.get("selection_mode", "")),
    )
    if selected.content_address != value.get("content_address"):
        raise ValidationError("policy-set persisted address mismatch")
    return verify_module_workbench_release_bundle_catalog_diff_policy_set(selected)


def _gate_from_mapping(
    value: Mapping[str, Any],
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetGate:
    raw_set = value.get("policy_set")
    raw_gates = value.get("gates")
    if not isinstance(raw_set, Mapping) or not isinstance(raw_gates, list):
        raise ValidationError("policy-set gate payload is invalid")
    gates: list[ModuleWorkbenchReleaseBundleCatalogDiffPolicyGate] = []
    from .module_workbench_release_bundle_catalog_diff_policy import (
        load_module_workbench_release_bundle_catalog_diff_policy_gate,
    )

    for raw_gate in raw_gates:
        if not isinstance(raw_gate, Mapping):
            raise ValidationError("policy-set gate entry is invalid")
        gates.append(load_module_workbench_release_bundle_catalog_diff_policy_gate(raw_gate))
    result = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetGate(
        diff_address=str(value.get("diff_address", "")),
        policy_set=_set_from_mapping(raw_set),
        gates=tuple(gates),
        accepted=value.get("accepted"),
        content_address=str(value.get("content_address", "")),
    )
    return verify_module_workbench_release_bundle_catalog_diff_policy_set_gate(result)


def load_module_workbench_release_bundle_catalog_diff_policy_set_gate(
    value: bytes | bytearray | str | Path | Mapping[str, Any],
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetGate:
    if isinstance(value, Mapping):
        return _gate_from_mapping(value)
    raw = (
        bytes(value)
        if isinstance(value, (bytes, bytearray))
        else read_bytes(value, field="catalog-diff policy-set gate", max_bytes=_MAX_JSON_BYTES)
    )
    try:
        parsed = _strict_json_loads(raw.decode(_UTF8))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValidationError(f"cannot parse catalog-diff policy-set gate: {exc}") from exc
    if not isinstance(parsed, Mapping):
        raise ValidationError("catalog-diff policy-set gate must be a JSON object")
    if raw != (canonical_json(parsed) + "\n").encode(_UTF8):
        raise ValidationError("catalog-diff policy-set gate is not canonical JSON")
    return _gate_from_mapping(parsed)


def query_module_workbench_release_bundle_catalog_diff_policy_set(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetGate
    | bytes
    | bytearray
    | str
    | Path
    | Mapping[str, Any],
    *,
    accepted: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_DEFAULT_LIMIT,
) -> dict[str, Any]:
    if (
        offset < 0
        or limit < 1
        or limit > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_MAX_LIMIT
    ):
        raise ValidationError("policy-set paging is invalid")
    gate = (
        value
        if isinstance(value, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetGate)
        else load_module_workbench_release_bundle_catalog_diff_policy_set_gate(value)
    )
    verify_module_workbench_release_bundle_catalog_diff_policy_set_gate(gate)
    rows = [
        {
            "policy_id": item.policy.policy_id,
            "gate_address": item.content_address,
            "accepted": item.accepted,
            "passed_count": item.passed_count,
            "failed_count": item.failed_count,
            "policy_address": item.policy_address,
        }
        for item in gate.gates
    ]
    if accepted is not None:
        rows = [item for item in rows if item["accepted"] is accepted]
    if text:
        rows = [item for item in rows if text.casefold() in canonical_json(item).casefold()]
    body = {
        "policy_set_gate_address": gate.content_address,
        "diff_address": gate.diff_address,
        "policy_set_address": gate.policy_set_address,
        "selection_mode": gate.policy_set.selection_mode,
        "accepted": accepted,
        "text": text,
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": rows[offset : offset + limit],
        "aggregate_accepted": gate.accepted,
    }
    return body | {
        "content_address": content_hash(
            body,
            prefix="module-workbench-release-bundle-catalog-diff-policy-set-query",
        )
    }


def module_workbench_release_bundle_catalog_diff_policy_set_json(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetGate,
) -> str:
    verify_module_workbench_release_bundle_catalog_diff_policy_set_gate(value)
    return canonical_json(value.to_dict()) + "\n"


def write_module_workbench_release_bundle_catalog_diff_policy_set(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetGate,
    destination: str | Path,
    *,
    allow_existing: bool = False,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetGate:
    verify_module_workbench_release_bundle_catalog_diff_policy_set_gate(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("policy-set destination already exists")
    if path.exists() and not path.is_file():
        raise ValidationError("policy-set destination is not a file")
    _validate_parent(path.parent, "policy-set destination")
    atomic_write_bytes(
        path,
        module_workbench_release_bundle_catalog_diff_policy_set_json(value).encode(_UTF8),
        field="policy-set destination",
    )
    return value


def module_workbench_release_bundle_catalog_diff_policy_set_csv(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetGate,
    *,
    accepted: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_DEFAULT_LIMIT,
) -> str:
    result = query_module_workbench_release_bundle_catalog_diff_policy_set(
        value, accepted=accepted, text=text, offset=offset, limit=limit
    )
    output = io.StringIO(newline="")
    fields = (
        "policy_id",
        "gate_address",
        "accepted",
        "passed_count",
        "failed_count",
        "policy_address",
    )
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(result["items"])
    return output.getvalue()


def render_module_workbench_release_bundle_catalog_diff_policy_set_markdown(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetGate,
) -> str:
    verify_module_workbench_release_bundle_catalog_diff_policy_set_gate(value)
    lines = [
        "# Module Workbench Release Bundle Catalog Diff Policy Set",
        "",
        f"- Gate: `{value.content_address}`",
        f"- Diff: `{value.diff_address}`",
        f"- Selection: **{value.policy_set.selection_mode}**",
        f"- Passed / failed policies: **{value.passed_policy_count} / "
        f"{value.failed_policy_count}**",
        f"- Accepted: **{str(value.accepted).lower()}**",
        "",
        "| Policy | Accepted | Passed checks | Failed checks | Gate |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    lines.extend(
        f"| `{item.policy.policy_id}` | {str(item.accepted).lower()} | {item.passed_count} "
        f"| {item.failed_count} | `{item.content_address}` |"
        for item in value.gates
    )
    return "\n".join(lines) + "\n"


def module_workbench_release_bundle_catalog_diff_policy_set_schema() -> dict[str, Any]:
    return {
        "version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_VERSION,
        "boundary": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_BOUNDARY,
        "resources": ["policy_set", "gates", "summary"],
        "selection_modes": ["all", "any"],
        "maximum_policies": 8,
        "depends_on": "public_aggregate_module_workbench_release_bundle_catalog_diff_policy",
        "source_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_release_bundle_catalog_diff_policy_set_capabilities() -> dict[str, Any]:
    operations = (
        "build_policy_set",
        "evaluate_all_policies",
        "select_any_policy",
        "select_all_policies",
        "query_policy_gates",
        "export_json",
        "export_csv",
        "render_markdown",
        "verify_addresses",
    )
    return {
        "version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "deterministic": True,
        "source_free": True,
        "read_only": True,
    }


__all__ = [
    "build_module_workbench_release_bundle_catalog_diff_policy_set",
    "default_module_workbench_release_bundle_catalog_diff_policy_set",
    "evaluate_module_workbench_release_bundle_catalog_diff_policy_set",
    "load_module_workbench_release_bundle_catalog_diff_policy_set_gate",
    "module_workbench_release_bundle_catalog_diff_policy_set_capabilities",
    "module_workbench_release_bundle_catalog_diff_policy_set_csv",
    "module_workbench_release_bundle_catalog_diff_policy_set_json",
    "module_workbench_release_bundle_catalog_diff_policy_set_schema",
    "query_module_workbench_release_bundle_catalog_diff_policy_set",
    "render_module_workbench_release_bundle_catalog_diff_policy_set_markdown",
    "strict_release_module_workbench_release_bundle_catalog_diff_policy_set",
    "verify_module_workbench_release_bundle_catalog_diff_policy_set",
    "verify_module_workbench_release_bundle_catalog_diff_policy_set_gate",
    "write_module_workbench_release_bundle_catalog_diff_policy_set",
]
