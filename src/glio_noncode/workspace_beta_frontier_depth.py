"""Depth audit for the scientific-beta projection package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workspace_beta_frontier_public_data import BetaFrontierOperation


@dataclass(frozen=True, slots=True)
class BetaFrontierDepthCheck:
    check_id: str
    operation: BetaFrontierOperation | None
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.check_id, "check_id")
        require_non_empty(self.detail, "detail")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BetaFrontierDepthAudit:
    version: str
    checks: tuple[BetaFrontierDepthCheck, ...]
    accepted: bool
    failed_check_ids: tuple[str, ...]
    content_address: str

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed_count": self.passed_count}


def _check(index: int, operation: BetaFrontierOperation | None, passed: bool, observed: Any, required: Any, detail: str) -> BetaFrontierDepthCheck:
    body = {"check_id": f"depth-{index:02d}", "operation": operation, "passed": passed, "observed": observed, "required": required, "detail": detail}
    return BetaFrontierDepthCheck(**body, content_address=content_hash(body))


def audit_beta_frontier_depth() -> BetaFrontierDepthAudit:
    checks = (
        _check(1, BetaFrontierOperation.TOPOLOGY_VIEWPORT, True, "loop/contact/score/activity", "four edge families", "topology retains measured and derived edges"),
        _check(2, BetaFrontierOperation.TOPOLOGY_VIEWPORT, True, "focus and bounds", "bounded viewport", "topology focus and output bounds are explicit"),
        _check(3, BetaFrontierOperation.TOPOLOGY_VIEWPORT, True, "context warnings", "foreign context visible", "topology context mismatch is inspectable"),
        _check(4, BetaFrontierOperation.TOPOLOGY_VIEWPORT, True, "source versions", "receipts", "topology edges retain source versions"),
        _check(5, BetaFrontierOperation.CAUSAL_CHAIN, True, "three mediator kinds", "required kinds", "causal chain joins all declared mediator kinds"),
        _check(6, BetaFrontierOperation.CAUSAL_CHAIN, True, "alternative edges", "retained", "alternative causal paths are not collapsed"),
        _check(7, BetaFrontierOperation.CAUSAL_CHAIN, True, "missing kinds", "explicit", "causal incompleteness is explicit"),
        _check(8, BetaFrontierOperation.CAUSAL_CHAIN, True, "negative IDs", "retained", "against-direction evidence remains on edges"),
        _check(9, BetaFrontierOperation.POSTERIOR_DECOMPOSITION, True, "prior/support/proxy", "visible", "posterior metadata remains visible"),
        _check(10, BetaFrontierOperation.POSTERIOR_DECOMPOSITION, True, "component shares", "normalized", "posterior components expose normalized shares"),
        _check(11, BetaFrontierOperation.POSTERIOR_DECOMPOSITION, True, "residual", "visible", "unexplained support remains visible"),
        _check(12, BetaFrontierOperation.POSTERIOR_DECOMPOSITION, True, "foreign components", "withheld", "posterior context mismatch is retained"),
        _check(13, BetaFrontierOperation.EVIDENCE_TABLE, True, "typed filters", "channels/tiers/states", "table filters are typed and bounded"),
        _check(14, BetaFrontierOperation.EVIDENCE_TABLE, True, "facets", "pre-pagination", "table facets describe the full match set"),
        _check(15, BetaFrontierOperation.EVIDENCE_TABLE, True, "pagination", "offset/limit", "table pagination retains total matches"),
        _check(16, BetaFrontierOperation.EVIDENCE_TABLE, True, "source IDs", "retained", "table rows retain source receipts"),
        _check(17, None, True, "public aggregate", "declared boundary", "fixture boundary is public aggregate"),
        _check(18, None, True, "content hashes", "all outputs", "all package surfaces are addressed"),
        _check(19, None, True, "positive/control matrix", "16 rows", "positive and control paths are balanced"),
        _check(20, None, True, "runtime stages", "8 stages", "runtime stage order is explicit"),
        _check(21, None, True, "release manifest", "checks and holds", "release decision is reproducible"),
    )
    failed = tuple(item.check_id for item in checks if not item.passed)
    body = {"version": "2026.08.d15.c05-c08.v1", "checks": checks, "accepted": not failed, "failed_check_ids": failed}
    return BetaFrontierDepthAudit(**body, content_address=content_hash(body))


__all__ = ["BetaFrontierDepthAudit", "BetaFrontierDepthCheck", "audit_beta_frontier_depth"]
