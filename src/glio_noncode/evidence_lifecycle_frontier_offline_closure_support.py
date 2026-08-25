"""Shared deterministic D14 closure projections.

The helpers consume hydrated offline artifacts only.  They retain public
identifiers and addresses, never operation payload text, and keep every
resource ordered so the same handoff produces the same closure address.
"""

from __future__ import annotations

import csv
import io
import json
from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Any

from .evidence_lifecycle_frontier_offline_contracts import EvidenceLifecycleOfflineBundle
from .module_fabric_support import contains_private_key
from .run_workspace import _has_forbidden_key
from .serialization import canonical_json, content_hash

_DIRECT_IDENTITY_KEYS = frozenset(
    {
        "agent",
        "agent_id",
        "agent_name",
        "assistant",
        "assistant_id",
        "assistant_name",
        "author",
        "author_id",
        "author_name",
        "contact_name",
        "email",
        "email_address",
        "generated_by",
        "individual_id",
        "language",
        "medical_record_number",
        "medical_record_no",
        "model",
        "model_id",
        "model_name",
        "model_version",
        "participant_id",
        "patient_id",
        "phone",
        "phone_number",
        "primary_agent",
        "primary_agent_id",
        "programming_language",
        "produced_by",
        "sample_id",
        "subject_id",
    }
)


def payload(bundle: EvidenceLifecycleOfflineBundle, artifact_id: str) -> Any:
    artifact = next((item for item in bundle.artifacts if item.artifact_id == artifact_id), None)
    if artifact is None or artifact.payload is None or artifact.media_type != "application/json":
        return {}
    try:
        return json.loads(artifact.payload)
    except json.JSONDecodeError:
        return {}


def csv_payload(bundle: EvidenceLifecycleOfflineBundle, artifact_id: str) -> str:
    artifact = next((item for item in bundle.artifacts if item.artifact_id == artifact_id), None)
    return artifact.payload if artifact is not None and artifact.payload is not None else ""


def _list(value: Any, field: str) -> list[dict[str, Any]]:
    if not isinstance(value, Mapping) or not isinstance(value.get(field), list):
        return []
    return [dict(item) for item in value[field] if isinstance(item, Mapping)]


def artifact_rows(bundle: EvidenceLifecycleOfflineBundle) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "resource": "artifact",
            "artifact_id": item.artifact_id,
            "relative_path": item.relative_path,
            "media_type": item.media_type,
            "kind": item.kind.value,
            "byte_count": item.byte_count,
            "line_count": item.line_count,
            "content_address": item.content_address,
        }
        for item in bundle.artifacts
    )


def record_rows(bundle: EvidenceLifecycleOfflineBundle) -> tuple[dict[str, Any], ...]:
    fixture = payload(bundle, "fixture")
    evaluation = payload(bundle, "evaluation")
    records = _list(fixture, "records")
    executions = {str(item.get("record_id")): item for item in _list(evaluation, "executions")}
    rows: list[dict[str, Any]] = []
    for ordinal, record in enumerate(records, start=1):
        record_id = str(record.get("record_id", ""))
        execution = executions.get(record_id, {})
        rows.append(
            {
                "resource": "record",
                "ordinal": ordinal,
                "record_id": record_id,
                "operation": record.get("operation"),
                "role": record.get("role"),
                "expected_state": record.get("expected_state"),
                "observed_state": execution.get("state"),
                "accepted": bool(execution.get("accepted")),
                "issue_codes": tuple(
                    sorted(str(item) for item in execution.get("issue_codes", ()) or ())
                ),
                "source_ids": tuple(
                    sorted(str(item) for item in record.get("source_ids", ()) or ())
                ),
                "content_address": execution.get(
                    "content_address", record.get("content_address", "")
                ),
            }
        )
    return tuple(
        sorted(rows, key=lambda row: (str(row.get("operation")), str(row.get("record_id"))))
    )


def execution_rows(bundle: EvidenceLifecycleOfflineBundle) -> tuple[dict[str, Any], ...]:
    evaluation = payload(bundle, "evaluation")
    return tuple(
        {
            "resource": "execution",
            "record_id": item.get("record_id"),
            "operation": item.get("operation"),
            "role": item.get("role"),
            "state": item.get("state"),
            "accepted": bool(item.get("accepted")),
            "issue_codes": tuple(sorted(str(code) for code in item.get("issue_codes", ()) or ())),
            "content_address": item.get("content_address"),
        }
        for item in _list(evaluation, "executions")
    )


def check_rows(bundle: EvidenceLifecycleOfflineBundle) -> tuple[dict[str, Any], ...]:
    evaluation = payload(bundle, "evaluation")
    return tuple(
        {
            "resource": "check",
            "ordinal": ordinal,
            "check_id": item.get("check_id"),
            "record_id": item.get("record_id"),
            "passed": bool(item.get("passed")),
            "observed": item.get("observed"),
            "required": item.get("required"),
            "detail": item.get("detail"),
            "content_address": item.get("content_address"),
        }
        for ordinal, item in enumerate(_list(evaluation, "checks"), start=1)
    )


def source_rows(bundle: EvidenceLifecycleOfflineBundle) -> tuple[dict[str, Any], ...]:
    fixture = payload(bundle, "fixture")
    return tuple(
        {"resource": "source", "ordinal": ordinal, **item}
        for ordinal, item in enumerate(_list(fixture, "sources"), start=1)
    )


def event_rows(bundle: EvidenceLifecycleOfflineBundle) -> tuple[dict[str, Any], ...]:
    observability = payload(bundle, "observability")
    return tuple({"resource": "event", **item} for item in _list(observability, "events"))


def stage_rows(bundle: EvidenceLifecycleOfflineBundle) -> tuple[dict[str, Any], ...]:
    runtime = payload(bundle, "runtime")
    return tuple({"resource": "stage", **item} for item in _list(runtime, "stages"))


def lineage_rows(bundle: EvidenceLifecycleOfflineBundle) -> tuple[dict[str, Any], ...]:
    lineage = payload(bundle, "lineage")
    rows = []
    for item in _list(lineage, "edges"):
        edge = dict(item)
        edge["edge_id"] = (
            f"{edge.get('parent_id', '')}->{edge.get('child_id', '')}:{edge.get('relation', '')}"
        )
        rows.append({"resource": "edge", **edge})
    return tuple(rows)


def queue_rows(bundle: EvidenceLifecycleOfflineBundle) -> tuple[dict[str, Any], ...]:
    queue = payload(bundle, "review-queue")
    return tuple({"resource": "queue", **item} for item in _list(queue, "items"))


def review_rows(bundle: EvidenceLifecycleOfflineBundle) -> tuple[dict[str, Any], ...]:
    review = payload(bundle, "review")
    return tuple(
        {"resource": "review", "ordinal": ordinal, **item}
        for ordinal, item in enumerate(_list(review, "rows"), start=1)
    )


def scenario_rows(bundle: EvidenceLifecycleOfflineBundle) -> tuple[dict[str, Any], ...]:
    matrix = payload(bundle, "scenario-matrix")
    return tuple({"resource": "scenario", **item} for item in _list(matrix, "scenarios"))


def operation_rows(bundle: EvidenceLifecycleOfflineBundle) -> tuple[dict[str, Any], ...]:
    records = record_rows(bundle)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in records:
        grouped.setdefault(str(row.get("operation")), []).append(row)
    return tuple(
        {
            "resource": "operation",
            "operation": operation,
            "record_count": len(items),
            "record_ids": tuple(str(item.get("record_id")) for item in items),
            "content_address": content_hash(
                {
                    "operation": operation,
                    "record_ids": tuple(str(item.get("record_id")) for item in items),
                },
                prefix="evidence-lifecycle-closure-operation",
            ),
        }
        for operation, items in sorted(grouped.items())
    )


def state_rows(bundle: EvidenceLifecycleOfflineBundle) -> tuple[dict[str, Any], ...]:
    states = Counter(str(row.get("observed_state", "unknown")) for row in record_rows(bundle))
    return tuple(
        {
            "resource": "state",
            "state": state,
            "record_count": count,
            "content_address": content_hash(
                {"state": state, "record_count": count}, prefix="evidence-lifecycle-closure-state"
            ),
        }
        for state, count in sorted(states.items())
    )


def all_rows(bundle: EvidenceLifecycleOfflineBundle) -> dict[str, tuple[dict[str, Any], ...]]:
    return {
        "artifacts": artifact_rows(bundle),
        "records": record_rows(bundle),
        "executions": execution_rows(bundle),
        "checks": check_rows(bundle),
        "sources": source_rows(bundle),
        "events": event_rows(bundle),
        "stages": stage_rows(bundle),
        "edges": lineage_rows(bundle),
        "queue": queue_rows(bundle),
        "reviews": review_rows(bundle),
        "scenarios": scenario_rows(bundle),
        "operations": operation_rows(bundle),
        "states": state_rows(bundle),
    }


def discover_keys(value: Any, prefix: str = "") -> tuple[str, ...]:
    keys: set[str] = set()
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            path = f"{prefix}.{key_text}" if prefix else key_text
            keys.add(path)
            keys.update(discover_keys(item, path))
    elif isinstance(value, (list, tuple)):
        for item in value:
            keys.update(discover_keys(item, prefix))
    return tuple(sorted(keys))


def forbidden_keys(value: Any) -> tuple[str, ...]:
    found: set[str] = set()
    for path in discover_keys(value):
        key = path.rsplit(".", 1)[-1].casefold()
        if (
            key in _DIRECT_IDENTITY_KEYS
            or _has_forbidden_key({key: True})
            or contains_private_key({key: True})
        ):
            found.add(key)
    return tuple(sorted(found))


def safe_relative_path(value: str) -> bool:
    if not value or "\\" in value or value.startswith("/"):
        return False
    return all(part not in {"", ".", ".."} for part in value.split("/"))


def addressed(value: Any, prefix: str | None = None) -> bool:
    text = str(value or "")
    return bool(text) and (prefix is None or text.startswith(prefix))


def csv_text(rows: Iterable[Mapping[str, Any]]) -> str:
    materialized = tuple(rows)
    fields = tuple(sorted({str(key) for row in materialized for key in row})) or (
        "resource",
        "content_address",
    )
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(fields)
    for row in materialized:
        values = []
        for field in fields:
            value = row.get(field, "")
            if isinstance(value, (list, tuple)):
                value = ";".join(str(item) for item in value)
            elif isinstance(value, Mapping):
                value = canonical_json(value)
            values.append(value)
        writer.writerow(values)
    return stream.getvalue()


def markdown_table(rows: Iterable[Mapping[str, Any]], title: str) -> str:
    materialized = tuple(rows)
    fields = tuple(sorted({str(key) for row in materialized for key in row})) or ("status",)
    lines = [
        f"# {title}",
        "",
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join("---" for _ in fields) + " |",
    ]
    for row in materialized:
        values = []
        for field in fields:
            value = row.get(field, "")
            if isinstance(value, (list, tuple)):
                value = ", ".join(str(item) for item in value)
            values.append(str(value).replace("|", "\\|"))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines) + "\n"


def count_map(bundle: EvidenceLifecycleOfflineBundle) -> dict[str, int]:
    rows = all_rows(bundle)
    return {
        "artifacts": len(bundle.artifacts),
        "manifest_checks": len(bundle.checks),
        **{key: len(value) for key, value in rows.items()},
    }


__all__ = [
    "_DIRECT_IDENTITY_KEYS",
    "addressed",
    "all_rows",
    "artifact_rows",
    "check_rows",
    "count_map",
    "csv_payload",
    "csv_text",
    "discover_keys",
    "event_rows",
    "execution_rows",
    "forbidden_keys",
    "lineage_rows",
    "markdown_table",
    "operation_rows",
    "payload",
    "queue_rows",
    "record_rows",
    "review_rows",
    "safe_relative_path",
    "scenario_rows",
    "source_rows",
    "stage_rows",
    "state_rows",
]
