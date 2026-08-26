"""Read-only queries, diffs, and replay checks over impact packets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_impact import verify_module_impact_diff
from .module_impact_audit import audit_module_impact
from .module_impact_packet import load_module_impact_packet, verify_module_impact_packet
from .module_impact_policy import evaluate_module_impact_gate
from .module_impact_query import (
    impact_diff_from_mapping,
    impact_gate_from_mapping,
    impact_plan_from_mapping,
    impact_report_from_mapping,
    query_module_impact,
)
from .module_impact_verification import query_module_impact_tasks
from .serialization import content_hash


def _json_artifact(directory: str | Path, filename: str) -> dict[str, Any]:
    path = Path(directory) / filename
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"impact packet artifact is unreadable: {filename}") from exc
    if not isinstance(value, dict):
        raise ValidationError(f"impact packet artifact is not an object: {filename}")
    return value


def _closure(directory: str | Path):
    verify = verify_module_impact_packet(directory)
    if not verify.accepted:
        raise ValidationError("impact packet must verify before query")
    diff = impact_diff_from_mapping(_json_artifact(directory, "diff.json"))
    report = impact_report_from_mapping(_json_artifact(directory, "impacts.json"))
    plan = impact_plan_from_mapping(_json_artifact(directory, "verification.json"))
    gate = impact_gate_from_mapping(_json_artifact(directory, "gate.json"))
    return diff, report, plan, gate


def query_module_impact_packet(
    directory: str | Path,
    *,
    resource: str = "impacts",
    module_id: str | None = None,
    kind: str | None = None,
    severity: str | None = None,
    min_risk: float | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    """Query verified diff, impact, dependency, or task rows offline."""

    diff, report, plan, _gate = _closure(directory)
    if str(resource).casefold() == "tasks":
        result = query_module_impact_tasks(
            plan,
            module_id=module_id,
            kind=kind,
            min_priority=None,
            text=text,
            offset=offset,
            limit=limit,
        )
        return result | {"packet_directory": str(directory)}
    return query_module_impact(
        diff=diff,
        report=report,
        plan=plan,
        resource=resource,
        module_id=module_id,
        kind=kind,
        severity=severity,
        min_risk=min_risk,
        text=text,
        offset=offset,
        limit=limit,
    ) | {"packet_directory": str(directory)}


def diff_module_impact_packets(
    left_directory: str | Path,
    right_directory: str | Path,
) -> dict[str, Any]:
    """Compare verified packet manifests and artifact addresses."""

    left = load_module_impact_packet(left_directory)
    right = load_module_impact_packet(right_directory)
    left_rows = {item.artifact_id: item for item in left.artifacts}
    right_rows = {item.artifact_id: item for item in right.artifacts}
    common = set(left_rows) & set(right_rows)
    body = {
        "left_packet_id": left.packet_id,
        "right_packet_id": right.packet_id,
        "left_packet_address": left.content_address,
        "right_packet_address": right.content_address,
        "added_artifacts": tuple(sorted(set(right_rows) - set(left_rows))),
        "removed_artifacts": tuple(sorted(set(left_rows) - set(right_rows))),
        "changed_artifacts": tuple(
            sorted(
                artifact_id
                for artifact_id in common
                if left_rows[artifact_id].content_address != right_rows[artifact_id].content_address
            )
        ),
        "accepted": left.accepted and right.accepted,
    }
    return body | {"content_address": content_hash(body, prefix="module-impact-packet-diff")}


def replay_module_impact_packet(directory: str | Path) -> dict[str, Any]:
    """Replay packet-level addresses and closure references without source access."""

    packet = load_module_impact_packet(directory)
    diff, report, plan, gate = _closure(directory)
    verify_module_impact_diff(diff)
    audit = audit_module_impact(diff, report, plan, gate)
    policy_replay = evaluate_module_impact_gate(diff, report, plan, gate.policy)
    body = {
        "packet_id": packet.packet_id,
        "packet_address": packet.content_address,
        "diff_address": diff.content_address,
        "impact_address": report.content_address,
        "plan_address": plan.content_address,
        "gate_address": gate.content_address,
        "audit_address": audit.content_address,
        "policy_address": policy_replay.content_address,
        "accepted": packet.accepted and audit.accepted and policy_replay.accepted,
        "verification": "offline exact-byte packet replay",
    }
    return body | {"content_address": content_hash(body, prefix="module-impact-packet-replay")}


def module_impact_packet_query_schema() -> dict[str, Any]:
    return {
        "version": "module-impact-packet-query-v1",
        "boundary": "public_aggregate_module_impact_packet_query",
        "resources": ["changes", "dependencies", "impacts", "tasks"],
        "filters": ["module_id", "kind", "severity", "min_risk", "text", "offset", "limit"],
        "verification": "packet must pass independent exact-byte verification before query",
        "stable_order": "source artifact order or module identifier order",
    }


def module_impact_packet_query_capabilities() -> dict[str, Any]:
    operations = (
        "query_verified_changes",
        "query_verified_dependencies",
        "query_verified_impacts",
        "query_verified_tasks",
        "diff_verified_packets",
        "replay_verified_packet",
    )
    return {
        "version": "module-impact-packet-query-v1",
        "operation_count": len(operations),
        "operations": list(operations),
        "offline": True,
        "read_only": True,
        "requires_verification": True,
    }


__all__ = [
    "diff_module_impact_packets",
    "module_impact_packet_query_capabilities",
    "module_impact_packet_query_schema",
    "query_module_impact_packet",
    "replay_module_impact_packet",
]
