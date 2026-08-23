"""Safe aggregate queries over a completed D01 runtime."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .intake_architecture_contracts import IntakeArchitectureRuntime, addressed


def query_intake_architecture(runtime: IntakeArchitectureRuntime, query: str) -> Mapping[str, Any]:
    term = query.strip().casefold()
    if not term:
        return {"query": query, "matched": 0, "results": (), "content_address": addressed({"query": query, "matched": 0}, "intake-query")}
    results = []
    for item in runtime.evaluation.results:
        haystack = " ".join((item.case_id, item.operation_id, item.capability_id, item.scenario.value, item.observed_state.value)).casefold()
        if term in haystack:
            results.append({"case_id": item.case_id, "operation_id": item.operation_id, "scenario": item.scenario.value, "state": item.observed_state.value, "issue_codes": list(item.issue_codes), "content_address": item.content_address})
    body = {"query": query, "matched": len(results), "results": tuple(results)}
    return body | {"content_address": addressed(body, "intake-query")}


__all__ = ["query_intake_architecture"]
