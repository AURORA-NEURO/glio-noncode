"""Bounded queries over the cross-domain release closure."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .frontier_release_closure_bundle import FrontierReleaseSnapshot
from .frontier_release_closure_contracts import (
    FRONTIER_RELEASE_CLOSURE_DEFAULT_LIMIT,
    FRONTIER_RELEASE_CLOSURE_MAX_LIMIT,
    FrontierReleaseQueryResult,
)
from .frontier_release_closure_support import all_rows, csv_text, markdown_table
from .serialization import canonical_json, content_hash, require_non_empty

_ALIASES = {
    "domain": "domains",
    "domains": "domains",
    "artifact": "artifacts",
    "artifacts": "artifacts",
    "dependency": "dependencies",
    "dependencies": "dependencies",
    "gate": "gates",
    "gates": "gates",
    "runtime": "runtime",
    "runtimes": "runtime",
}


def _match(row: Mapping[str, Any], key: str, expected: Any) -> bool:
    if expected in (None, ""):
        return True
    values = expected if isinstance(expected, (list, tuple, set)) else str(expected).split(",")
    wanted = {str(item).casefold().strip() for item in values if str(item).strip()}
    actual = row.get(key, "")
    if isinstance(actual, (list, tuple, set)):
        return bool(wanted & {str(item).casefold() for item in actual})
    return str(actual).casefold() in wanted


def query_frontier_release(
    snapshot: FrontierReleaseSnapshot,
    *,
    resource: str = "domains",
    domain_id: str | None = None,
    gate_type: str | None = None,
    state: str | None = None,
    relation: str | None = None,
    accepted: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = FRONTIER_RELEASE_CLOSURE_DEFAULT_LIMIT,
    filters: Mapping[str, Any] | None = None,
) -> FrontierReleaseQueryResult:
    if offset < 0:
        raise ValueError("frontier release query offset cannot be negative")
    if limit < 1 or limit > FRONTIER_RELEASE_CLOSURE_MAX_LIMIT:
        raise ValueError(
            f"frontier release query limit must be between 1 and {FRONTIER_RELEASE_CLOSURE_MAX_LIMIT}"
        )
    normalized = require_non_empty(resource, "resource").casefold().replace("-", "_")
    try:
        resource_key = _ALIASES[normalized]
    except KeyError as exc:
        raise ValueError(f"unknown frontier release resource: {resource}") from exc
    selected: dict[str, Any] = {
        "domain_id": domain_id,
        "gate_type": gate_type,
        "state": state,
        "relation": relation,
        "accepted": accepted,
        "text": text,
    }
    for key in selected:
        if selected[key] in (None, "") and filters and filters.get(key) not in (None, ""):
            selected[key] = filters[key]
    rows = list(all_rows(snapshot)[resource_key])
    for key, expected in selected.items():
        if key in {"text", "state"} or expected in (None, ""):
            continue
        rows = [row for row in rows if _match(row, key, expected)]
    if selected["state"]:
        state_value = str(selected["state"]).casefold()
        rows = [
            row
            for row in rows
            if state_value
            in {
                ("accepted" if row.get("accepted") is True else "blocked")
                if "accepted" in row
                else ("passed" if row.get("passed") is True else "failed")
                if "passed" in row
                else str(row.get("state", "")).casefold()
            }
        ]
    if selected["text"]:
        wanted = str(selected["text"]).casefold()
        rows = [row for row in rows if wanted in canonical_json(row).casefold()]
    rows.sort(key=lambda row: (str(row.get("ordinal", "")), canonical_json(row)))
    body = {
        "bundle_id": snapshot.bundle_id,
        "resource": resource_key,
        "filters": selected,
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": tuple(rows[offset : offset + limit]),
        "accepted": snapshot.accepted,
    }
    return FrontierReleaseQueryResult(
        **body,
        content_address=content_hash(body, prefix="frontier-release-query"),
    )


def frontier_release_resource_names() -> tuple[str, ...]:
    return tuple(sorted(set(_ALIASES.values())))


def export_frontier_release_csv(result: FrontierReleaseQueryResult) -> str:
    return csv_text(result.items)


def export_frontier_release_markdown(result: FrontierReleaseQueryResult) -> str:
    return markdown_table(result.items, f"Frontier release query: {result.resource}")


__all__ = [
    "export_frontier_release_csv",
    "export_frontier_release_markdown",
    "frontier_release_resource_names",
    "query_frontier_release",
]
