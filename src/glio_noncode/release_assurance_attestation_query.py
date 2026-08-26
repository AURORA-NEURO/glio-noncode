"""Bounded, address-only queries over a release attestation."""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping
from io import StringIO
from typing import Any

from .errors import ValidationError
from .release_assurance_attestation_contracts import (
    RELEASE_ASSURANCE_ATTESTATION_DEFAULT_LIMIT,
    RELEASE_ASSURANCE_ATTESTATION_MAX_LIMIT,
    RELEASE_ASSURANCE_ATTESTATION_RESOURCE_NAMES,
    ReleaseAssuranceAttestation,
    ReleaseAssuranceAttestationQueryResult,
)
from .release_assurance_support import markdown_payload, text_matches
from .serialization import canonical_json, content_hash, jsonable


def _rows(value: ReleaseAssuranceAttestation, resource: str) -> list[dict[str, Any]]:
    if resource == "components":
        return [item.to_dict() for item in value.components]
    if resource == "checks":
        return [item.to_dict() for item in value.checks]
    raise ValidationError(f"unsupported release-assurance attestation resource: {resource}")


def _matches(
    row: Mapping[str, Any],
    *,
    component_id: str | None,
    category: str | None,
    passed_only: bool,
    accepted_only: bool,
    text: str | None,
) -> bool:
    if component_id and str(row.get("component_id", "")) != component_id:
        return False
    if category and str(row.get("category", "")).casefold() != category.casefold():
        return False
    if passed_only and not bool(row.get("passed", False)):
        return False
    if accepted_only and not bool(row.get("accepted", False)):
        return False
    return text_matches(row, text)


def query_release_assurance_attestation(
    value: ReleaseAssuranceAttestation,
    *,
    resource: str = "components",
    component_id: str | None = None,
    category: str | None = None,
    passed_only: bool = False,
    accepted_only: bool = False,
    text: str | None = None,
    offset: int = 0,
    limit: int = RELEASE_ASSURANCE_ATTESTATION_DEFAULT_LIMIT,
) -> ReleaseAssuranceAttestationQueryResult:
    """Return one deterministic, bounded result page."""

    if resource not in RELEASE_ASSURANCE_ATTESTATION_RESOURCE_NAMES:
        raise ValidationError(f"unsupported release-assurance attestation resource: {resource}")
    if offset < 0 or limit < 1 or limit > RELEASE_ASSURANCE_ATTESTATION_MAX_LIMIT:
        raise ValidationError("release-assurance attestation pagination is outside its contract")
    rows = [
        row
        for row in _rows(value, resource)
        if _matches(
            row,
            component_id=component_id,
            category=category,
            passed_only=passed_only,
            accepted_only=accepted_only,
            text=text,
        )
    ]
    rows.sort(
        key=lambda row: (
            str(row.get("component_id", row.get("check_id", "")))
            + ":"
            + str(row.get("check_id", row.get("component_id", "")))
        )
    )
    page = tuple(rows[offset : offset + limit])
    filters = {
        "component_id": component_id,
        "category": category,
        "passed_only": passed_only,
        "accepted_only": accepted_only,
        "text": text,
    }
    body = {
        "attestation_id": value.attestation_id,
        "resource": resource,
        "filters": filters,
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": page,
        "accepted": value.accepted,
    }
    return ReleaseAssuranceAttestationQueryResult(
        value.attestation_id,
        resource,
        filters,
        len(rows),
        offset,
        limit,
        page,
        value.accepted,
        content_hash(body, prefix="release-assurance-attestation-query"),
    )


def release_assurance_attestation_query_csv(
    result: ReleaseAssuranceAttestationQueryResult,
) -> bytes:
    """Export a bounded query page as deterministic CSV."""

    output = StringIO()
    rows = result.items
    if not rows:
        output.write("item\n")
        return output.getvalue().encode("utf-8")
    fields = tuple(sorted({key for row in rows for key in row}))
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                key: canonical_json(row.get(key))
                if isinstance(row.get(key), (dict, list, tuple))
                else row.get(key, "")
                for key in fields
            }
        )
    return output.getvalue().encode("utf-8")


def release_assurance_attestation_query_markdown(
    result: ReleaseAssuranceAttestationQueryResult,
) -> bytes:
    """Export a bounded query page as reviewer-readable Markdown."""

    return markdown_payload(f"Release assurance attestation: {result.resource}", result.items)


def release_assurance_attestation_query_json(result: ReleaseAssuranceAttestationQueryResult) -> str:
    """Return stable JSON for a query result."""

    return json.dumps(jsonable(result), ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def release_assurance_attestation_query_export_payloads(
    result: ReleaseAssuranceAttestationQueryResult,
) -> dict[str, bytes]:
    """Return all supported query exports."""

    return {
        "query.json": release_assurance_attestation_query_json(result).encode("utf-8"),
        "query.csv": release_assurance_attestation_query_csv(result),
        "query.md": release_assurance_attestation_query_markdown(result),
    }


def release_assurance_attestation_query_schema() -> dict[str, Any]:
    """Describe query resources, filters, and pagination bounds."""

    return {
        "version": "release-assurance-attestation-query-schema-v1",
        "resources": list(RELEASE_ASSURANCE_ATTESTATION_RESOURCE_NAMES),
        "filters": ["component_id", "category", "passed_only", "accepted_only", "text"],
        "pagination": {
            "default_limit": RELEASE_ASSURANCE_ATTESTATION_DEFAULT_LIMIT,
            "max_limit": RELEASE_ASSURANCE_ATTESTATION_MAX_LIMIT,
        },
        "bounded": True,
        "source_payloads": False,
    }


def release_assurance_attestation_query_capabilities() -> dict[str, Any]:
    """Describe bounded query guarantees."""

    return {
        "version": "release-assurance-attestation-query-capabilities-v1",
        "components": True,
        "checks": True,
        "pagination": True,
        "text_filter": True,
        "csv_export": True,
        "markdown_export": True,
        "json_export": True,
        "address_only": True,
        "source_payloads": False,
        "handler_execution": False,
    }


__all__ = [
    "query_release_assurance_attestation",
    "release_assurance_attestation_query_capabilities",
    "release_assurance_attestation_query_csv",
    "release_assurance_attestation_query_export_payloads",
    "release_assurance_attestation_query_json",
    "release_assurance_attestation_query_markdown",
    "release_assurance_attestation_query_schema",
]
