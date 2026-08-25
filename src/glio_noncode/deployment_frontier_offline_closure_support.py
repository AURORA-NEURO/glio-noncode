"""Deterministic row projections shared by the D16 closure planes."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable, Mapping
from pathlib import PurePosixPath
from typing import Any

from .deployment_frontier_offline_contracts import DeploymentFrontierOfflineBundle
from .deployment_frontier_offline_query import _payload, _rows
from .serialization import canonical_json, content_hash, jsonable

_ARTIFACT_BY_RESOURCE = {
    "artifacts": "artifacts",
    "records": "fixture",
    "executions": "evaluation",
    "checks": "evaluation",
    "sources": "fixture",
    "validation": "validation",
    "evidence": "evaluation",
    "edges": "lineage",
    "views": "view",
    "queue": "queue",
    "diagnostics": "diagnostics",
    "stages": "runtime",
    "stage_index": "stage-index",
    "operations": "operation-index",
    "controls": "fixture",
    "failures": "failure_injection",
    "audit_events": "audit_log",
    "transcript_events": "transcript",
    "trace_observations": "trace",
}

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
        "generated_by",
        "language",
        "model",
        "model_id",
        "model_name",
        "model_version",
        "phone",
        "patient_id",
        "subject_id",
        "participant_id",
        "individual_id",
        "medical_record_number",
        "primary_agent",
        "primary_agent_id",
        "programming_language",
        "produced_by",
        "sample_id",
    }
)


def payload(bundle: DeploymentFrontierOfflineBundle, artifact_id: str) -> Any:
    return _payload(bundle, artifact_id)


def _list(value: Any, key: str) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, Mapping) or not isinstance(value.get(key), list):
        return ()
    return tuple(dict(item) for item in value[key] if isinstance(item, Mapping))


def _address_rows(rows: Iterable[Mapping[str, Any]], resource: str) -> tuple[dict[str, Any], ...]:
    addressed: list[dict[str, Any]] = []
    for ordinal, source in enumerate(rows, 1):
        row = {str(key): jsonable(value) for key, value in source.items()}
        source_address = row.get("content_address")
        row["resource"] = resource
        row["ordinal"] = ordinal
        if source_address:
            row["source_address"] = source_address
        row["content_address"] = content_hash(
            {key: value for key, value in row.items() if key != "content_address"},
            prefix="deployment-frontier-closure-row",
        )
        addressed.append(row)
    return tuple(addressed)


def artifact_rows(bundle: DeploymentFrontierOfflineBundle) -> tuple[dict[str, Any], ...]:
    return _address_rows(
        (item.to_dict(include_payload=False) for item in bundle.artifacts), "artifact"
    )


def record_rows(bundle: DeploymentFrontierOfflineBundle) -> tuple[dict[str, Any], ...]:
    rows = []
    for row in _rows(bundle, "fixture", "records"):
        item = dict(row)
        item["expected_issue_codes"] = tuple(
            sorted(str(code) for code in item.get("expected_issue_codes", ()) or ())
        )
        item["issue_codes"] = item["expected_issue_codes"]
        rows.append(item)
    return _address_rows(sorted(rows, key=lambda item: str(item.get("record_id"))), "record")


def execution_rows(bundle: DeploymentFrontierOfflineBundle) -> tuple[dict[str, Any], ...]:
    rows = []
    for row in _rows(bundle, "evaluation", "executions"):
        item = dict(row)
        item["issue_codes"] = tuple(sorted(str(code) for code in item.get("issue_codes", ()) or ()))
        item["accepted"] = not bool(item["issue_codes"])
        rows.append(item)
    return _address_rows(sorted(rows, key=lambda item: str(item.get("record_id"))), "execution")


def check_rows(bundle: DeploymentFrontierOfflineBundle) -> tuple[dict[str, Any], ...]:
    return _address_rows(
        sorted(_rows(bundle, "evaluation", "checks"), key=lambda item: str(item.get("check_id"))),
        "check",
    )


def source_rows(bundle: DeploymentFrontierOfflineBundle) -> tuple[dict[str, Any], ...]:
    return _address_rows(
        sorted(_rows(bundle, "fixture", "sources"), key=lambda item: str(item.get("source_id"))),
        "source",
    )


def validation_rows(bundle: DeploymentFrontierOfflineBundle) -> tuple[dict[str, Any], ...]:
    return _address_rows(
        sorted(
            _rows(bundle, "validation", "cells"),
            key=lambda item: (str(item.get("record_id")), str(item.get("cell_id"))),
        ),
        "validation",
    )


def evidence_rows(bundle: DeploymentFrontierOfflineBundle) -> tuple[dict[str, Any], ...]:
    records = {str(row.get("record_id")): row for row in record_rows(bundle)}
    executions = {str(row.get("record_id")): row for row in execution_rows(bundle)}
    rows = []
    for record_id in sorted(records):
        record = records[record_id]
        execution = executions.get(record_id, {})
        rows.append(
            {
                "record_id": record_id,
                "operation": record.get("operation"),
                "state": execution.get("observed_state"),
                "input_address": record.get("content_address", ""),
                "output_address": execution.get("content_address", ""),
                "issue_codes": execution.get("issue_codes", ()),
            }
        )
    return _address_rows(rows, "evidence")


def lineage_rows(bundle: DeploymentFrontierOfflineBundle) -> tuple[dict[str, Any], ...]:
    rows = []
    for row in _list(payload(bundle, "lineage"), "edges"):
        rows.append(
            {
                "parent_id": str(row.get("parent_id")),
                "child_id": str(row.get("child_id")),
                "relation": str(row.get("relation")),
                "source_address": row.get("content_address", ""),
            }
        )
    addressed = list(
        _address_rows(
            sorted(rows, key=lambda item: (item["parent_id"], item["child_id"], item["relation"])),
            "edge",
        )
    )
    for row in addressed:
        row["edge_id"] = f"{row['parent_id']}->{row['child_id']}:{row['relation']}"
    return tuple(addressed)


def view_rows(bundle: DeploymentFrontierOfflineBundle) -> tuple[dict[str, Any], ...]:
    return _address_rows(
        sorted(
            _list(payload(bundle, "view"), "entries"), key=lambda item: str(item.get("record_id"))
        ),
        "view",
    )


def queue_rows(bundle: DeploymentFrontierOfflineBundle) -> tuple[dict[str, Any], ...]:
    return _address_rows(
        sorted(
            _list(payload(bundle, "queue"), "items"),
            key=lambda item: (int(item.get("priority", 0)), str(item.get("record_id"))),
        ),
        "queue",
    )


def diagnostic_rows(bundle: DeploymentFrontierOfflineBundle) -> tuple[dict[str, Any], ...]:
    return _address_rows(
        sorted(
            _list(payload(bundle, "diagnostics"), "findings"),
            key=lambda item: str(item.get("finding_id")),
        ),
        "diagnostic",
    )


def stage_rows(bundle: DeploymentFrontierOfflineBundle) -> tuple[dict[str, Any], ...]:
    return _address_rows(
        sorted(
            _list(payload(bundle, "runtime"), "stages"),
            key=lambda item: int(item.get("sequence", 0)),
        ),
        "stage",
    )


def stage_index_rows(bundle: DeploymentFrontierOfflineBundle) -> tuple[dict[str, Any], ...]:
    return _address_rows(
        sorted(
            _list(payload(bundle, "stage-index"), "stages"),
            key=lambda item: int(item.get("sequence", 0)),
        ),
        "stage_index",
    )


def operation_rows(bundle: DeploymentFrontierOfflineBundle) -> tuple[dict[str, Any], ...]:
    value = payload(bundle, "operation-index")
    operations = value.get("operations", {}) if isinstance(value, Mapping) else {}
    return _address_rows(
        (
            {"operation": operation, "record_ids": tuple(str(item) for item in record_ids)}
            for operation, record_ids in sorted(operations.items())
        ),
        "operation",
    )


def control_rows(bundle: DeploymentFrontierOfflineBundle) -> tuple[dict[str, Any], ...]:
    return _address_rows(
        (row for row in record_rows(bundle) if row.get("role") == "control"), "control"
    )


def failure_rows(bundle: DeploymentFrontierOfflineBundle) -> tuple[dict[str, Any], ...]:
    return _address_rows(
        sorted(
            _list(payload(bundle, "failure_injection"), "probes"),
            key=lambda item: str(item.get("control_id", item.get("probe_id", ""))),
        ),
        "failure",
    )


def audit_event_rows(bundle: DeploymentFrontierOfflineBundle) -> tuple[dict[str, Any], ...]:
    return _address_rows(
        sorted(
            _list(payload(bundle, "audit_log"), "events"),
            key=lambda item: int(item.get("sequence", 0)),
        ),
        "audit_event",
    )


def transcript_event_rows(bundle: DeploymentFrontierOfflineBundle) -> tuple[dict[str, Any], ...]:
    return _address_rows(
        sorted(
            _list(payload(bundle, "transcript"), "events"),
            key=lambda item: int(item.get("sequence", 0)),
        ),
        "transcript_event",
    )


def trace_observation_rows(bundle: DeploymentFrontierOfflineBundle) -> tuple[dict[str, Any], ...]:
    return _address_rows(
        sorted(
            _list(payload(bundle, "trace"), "observations"),
            key=lambda item: int(item.get("sequence", 0)),
        ),
        "trace_observation",
    )


def all_rows(bundle: DeploymentFrontierOfflineBundle) -> dict[str, tuple[dict[str, Any], ...]]:
    return {
        "artifacts": artifact_rows(bundle),
        "records": record_rows(bundle),
        "executions": execution_rows(bundle),
        "checks": check_rows(bundle),
        "sources": source_rows(bundle),
        "validation": validation_rows(bundle),
        "evidence": evidence_rows(bundle),
        "edges": lineage_rows(bundle),
        "views": view_rows(bundle),
        "queue": queue_rows(bundle),
        "diagnostics": diagnostic_rows(bundle),
        "stages": stage_rows(bundle),
        "stage_index": stage_index_rows(bundle),
        "operations": operation_rows(bundle),
        "controls": control_rows(bundle),
        "failures": failure_rows(bundle),
        "audit_events": audit_event_rows(bundle),
        "transcript_events": transcript_event_rows(bundle),
        "trace_observations": trace_observation_rows(bundle),
    }


def _walk_keys(value: Any, prefix: str = "") -> Iterable[str]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            yield path
            yield from _walk_keys(child, path)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_keys(child, prefix)


def discover_keys(bundle: DeploymentFrontierOfflineBundle) -> tuple[str, ...]:
    keys: set[str] = set()
    for artifact in bundle.artifacts:
        if artifact.payload:
            try:
                keys.update(_walk_keys(json.loads(artifact.payload)))
            except json.JSONDecodeError:
                continue
    return tuple(sorted(keys))


def forbidden_keys(value: Any) -> tuple[str, ...]:
    found: set[str] = set()
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).casefold() in _DIRECT_IDENTITY_KEYS:
                found.add(str(key))
            found.update(forbidden_keys(child))
    elif isinstance(value, list):
        for child in value:
            found.update(forbidden_keys(child))
    return tuple(sorted(found))


def safe_relative_path(value: str) -> bool:
    if not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return (
        not path.is_absolute()
        and bool(path.parts)
        and all(part not in {"", ".", ".."} for part in path.parts)
    )


def csv_text(rows: Iterable[Mapping[str, Any]]) -> str:
    materialized = tuple(rows)
    fields = tuple(sorted({str(key) for row in materialized for key in row})) or (
        "resource",
        "content_address",
    )
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in materialized:
        writer.writerow(
            {
                key: canonical_json(row.get(key))
                if isinstance(row.get(key), (dict, list, tuple))
                else row.get(key, "")
                for key in fields
            }
        )
    return stream.getvalue()


def markdown_table(rows: Iterable[Mapping[str, Any]], title: str) -> str:
    materialized = tuple(rows)
    fields = tuple(sorted({str(key) for row in materialized for key in row})) or (
        "resource",
        "content_address",
    )
    lines = [
        f"# {title}",
        "",
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join("---" for _ in fields) + " |",
    ]
    for row in materialized:
        lines.append(
            "| " + " | ".join(str(row.get(key, "")).replace("|", "\\|") for key in fields) + " |"
        )
    return "\n".join(lines) + "\n"


def count_map(rows: Mapping[str, Iterable[Mapping[str, Any]]]) -> dict[str, int]:
    return {str(key): len(tuple(value)) for key, value in rows.items()}


__all__ = [
    "all_rows",
    "artifact_rows",
    "audit_event_rows",
    "control_rows",
    "count_map",
    "csv_text",
    "diagnostic_rows",
    "discover_keys",
    "evidence_rows",
    "execution_rows",
    "failure_rows",
    "forbidden_keys",
    "lineage_rows",
    "markdown_table",
    "operation_rows",
    "payload",
    "queue_rows",
    "record_rows",
    "safe_relative_path",
    "source_rows",
    "stage_index_rows",
    "stage_rows",
    "trace_observation_rows",
    "transcript_event_rows",
    "validation_rows",
    "view_rows",
]
