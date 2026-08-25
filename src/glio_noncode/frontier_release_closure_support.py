"""Shared projections and public-boundary helpers for the D13-D16 release."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Mapping
from pathlib import PurePosixPath
from typing import Any

from .frontier_release_closure_bundle import FrontierReleaseSnapshot
from .serialization import canonical_json, content_hash, jsonable

_FORBIDDEN_KEYS = frozenset(
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
        "individual_id",
        "language",
        "medical_record_number",
        "model",
        "model_id",
        "model_name",
        "model_version",
        "participant_id",
        "patient_id",
        "phone",
        "primary_agent",
        "primary_agent_id",
        "programming_language",
        "produced_by",
        "sample_id",
        "subject_id",
    }
)


def snapshot_payload(snapshot: FrontierReleaseSnapshot) -> dict[str, Any]:
    return snapshot.to_dict()


def domain_rows(snapshot: FrontierReleaseSnapshot) -> tuple[dict[str, Any], ...]:
    return tuple(item.to_dict() for item in snapshot.domains)


def artifact_rows(snapshot: FrontierReleaseSnapshot) -> tuple[dict[str, Any], ...]:
    return tuple(item.to_dict() for item in snapshot.artifacts)


def dependency_rows(snapshot: FrontierReleaseSnapshot) -> tuple[dict[str, Any], ...]:
    return tuple(item.to_dict() for item in snapshot.dependencies)


def gate_rows(snapshot: FrontierReleaseSnapshot) -> tuple[dict[str, Any], ...]:
    return tuple(item.to_dict() for item in snapshot.gates)


def runtime_rows(snapshot: FrontierReleaseSnapshot) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "domain_id": domain.domain_id,
            "bundle_id": domain.bundle_id,
            "runtime_content_address": domain.runtime_content_address,
            "closure_stage_count": domain.closure_stage_count,
            "source_stage_count": domain.source_stage_count,
            "deterministic_replay": domain.deterministic_replay,
            "accepted": domain.accepted,
            "content_address": content_hash(
                {
                    "domain_id": domain.domain_id,
                    "runtime_content_address": domain.runtime_content_address,
                    "closure_stage_count": domain.closure_stage_count,
                    "deterministic_replay": domain.deterministic_replay,
                    "accepted": domain.accepted,
                },
                prefix="frontier-release-runtime-row",
            ),
        }
        for domain in snapshot.domains
    )


def all_rows(snapshot: FrontierReleaseSnapshot) -> dict[str, tuple[dict[str, Any], ...]]:
    return {
        "domains": domain_rows(snapshot),
        "artifacts": artifact_rows(snapshot),
        "dependencies": dependency_rows(snapshot),
        "gates": gate_rows(snapshot),
        "runtime": runtime_rows(snapshot),
    }


def release_counts(snapshot: FrontierReleaseSnapshot) -> dict[str, int]:
    rows = all_rows(snapshot)
    return {key: len(value) for key, value in rows.items()} | {
        "accepted_domains": sum(bool(row.get("accepted")) for row in rows["domains"]),
        "passed_gates": sum(bool(row.get("passed")) for row in rows["gates"]),
        "deterministic_domains": sum(
            bool(row.get("deterministic_replay")) for row in rows["runtime"]
        ),
    }


def _walk_keys(value: Any, prefix: str = "") -> Iterable[str]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            name = str(key)
            path = f"{prefix}.{name}" if prefix else name
            yield path
            yield from _walk_keys(child, path)
    elif isinstance(value, (list, tuple)):
        for ordinal, child in enumerate(value):
            yield from _walk_keys(child, f"{prefix}[{ordinal}]")


def discover_keys(value: Any) -> tuple[str, ...]:
    return tuple(sorted(set(_walk_keys(jsonable(value)))))


def forbidden_keys(value: Any) -> tuple[str, ...]:
    found: set[str] = set()

    def visit(item: Any) -> None:
        if isinstance(item, Mapping):
            for key, child in item.items():
                if str(key).casefold() in _FORBIDDEN_KEYS:
                    found.add(str(key))
                visit(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                visit(child)

    visit(jsonable(value))
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


def canonical_rows(rows: Iterable[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    return tuple(
        sorted(
            (jsonable(dict(row)) for row in rows),
            key=lambda row: (str(row.get("ordinal", "")), canonical_json(row)),
        )
    )


def csv_text(rows: Iterable[Mapping[str, Any]]) -> str:
    materialized = canonical_rows(rows)
    fields = tuple(sorted({str(key) for row in materialized for key in row})) or (
        "resource",
        "content_address",
    )
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in materialized:
        writer.writerow({field: row.get(field, "") for field in fields})
    return stream.getvalue()


def markdown_table(rows: Iterable[Mapping[str, Any]], title: str) -> str:
    materialized = canonical_rows(rows)
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
    lines.extend(
        "| " + " | ".join(str(row.get(field, "")).replace("|", "\\|") for field in fields) + " |"
        for row in materialized
    )
    return "\n".join(lines) + "\n"


def public_release_manifest(snapshot: FrontierReleaseSnapshot) -> dict[str, Any]:
    rows = all_rows(snapshot)
    body = {
        "version": "frontier-release-public-manifest-v1",
        "bundle_id": snapshot.bundle_id,
        "run_id": snapshot.run_id,
        "boundary": snapshot.boundary,
        "accepted": snapshot.accepted,
        "counts": release_counts(snapshot),
        "domain_addresses": {row["domain_id"]: row["content_address"] for row in rows["domains"]},
        "artifact_addresses": {
            row["artifact_ref"]: row["content_address"] for row in rows["artifacts"]
        },
        "content_address": snapshot.content_address,
    }
    return body | {
        "manifest_address": content_hash(body, prefix="frontier-release-public-manifest")
    }


def public_runtime_manifest(snapshot: FrontierReleaseSnapshot) -> dict[str, Any]:
    rows = runtime_rows(snapshot)
    body = {
        "bundle_id": snapshot.bundle_id,
        "run_id": snapshot.run_id,
        "domains": rows,
        "accepted": all(bool(item.get("accepted")) for item in rows),
    }
    return body | {
        "content_address": content_hash(body, prefix="frontier-release-runtime-manifest")
    }


__all__ = [
    "all_rows",
    "artifact_rows",
    "canonical_rows",
    "csv_text",
    "dependency_rows",
    "discover_keys",
    "domain_rows",
    "forbidden_keys",
    "gate_rows",
    "markdown_table",
    "public_release_manifest",
    "public_runtime_manifest",
    "release_counts",
    "runtime_rows",
    "safe_relative_path",
    "snapshot_payload",
]
