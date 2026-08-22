"""Small deterministic query API over the release bundle."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_alpha_frontier_bundle import CausalAlphaFrontierReleaseBundle
from .causal_alpha_frontier_public_data import CausalAlphaFrontierOperation
from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierQueryResult:
    query_id: str
    filters: dict[str, str]
    record_ids: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"query_id": self.query_id, "filters": dict(self.filters), "record_ids": self.record_ids, "rows": self.rows, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def query_causal_alpha_frontier(bundle: CausalAlphaFrontierReleaseBundle, *, operation: CausalAlphaFrontierOperation | str | None = None, state: str | None = None, disposition: str | None = None) -> CausalAlphaFrontierQueryResult:
    operation_value = None if operation is None else CausalAlphaFrontierOperation(str(operation))
    decision_map = {item.record_id: item for item in bundle.decisions}
    rows: list[dict[str, Any]] = []
    for result in bundle.evaluation.evaluation.results:
        decision = decision_map[result.record_id]
        if operation_value is not None and result.operation is not operation_value:
            continue
        if state is not None and result.observed_state.value != state:
            continue
        if disposition is not None and decision.disposition.value != disposition:
            continue
        rows.append({"record_id": result.record_id, "operation": result.operation, "state": result.observed_state, "disposition": decision.disposition, "accepted": result.accepted})
    filters = {key: value for key, value in (("operation", operation_value.value if operation_value else ""), ("state", state or ""), ("disposition", disposition or "")) if value}
    return CausalAlphaFrontierQueryResult("causal-alpha-frontier-query", filters, tuple(item["record_id"] for item in rows), tuple(rows), True)


__all__ = ["CausalAlphaFrontierQueryResult", "query_causal_alpha_frontier"]
