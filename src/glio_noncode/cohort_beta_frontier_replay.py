"""Same-input replay and address comparison for release reproducibility."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_beta_frontier_fixture_eval import evaluate_cohort_beta_frontier_fixture
from .cohort_beta_frontier_public_data import CohortBetaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierReplayReceipt:
    replay_id: str
    original_address: str
    replay_address: str
    deterministic: bool
    row_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def replay_cohort_beta_frontier(fixture: CohortBetaFrontierFixture, *, replay_id: str = "cohort-beta-frontier-replay") -> CohortBetaFrontierReplayReceipt:
    first = evaluate_cohort_beta_frontier_fixture(fixture)
    second = evaluate_cohort_beta_frontier_fixture(fixture)
    deterministic = first.content_address == second.content_address and first.rows == second.rows
    body = {"replay_id": replay_id, "original": first.content_address, "replay": second.content_address, "deterministic": deterministic, "row_count": len(first.rows)}
    return CohortBetaFrontierReplayReceipt(replay_id, first.content_address, second.content_address, deterministic, len(first.rows), content_hash(body, prefix="replay"))


def replay_is_deterministic(receipt: CohortBetaFrontierReplayReceipt) -> bool:
    return receipt.deterministic and receipt.original_address == receipt.replay_address


__all__ = ["CohortBetaFrontierReplayReceipt", "replay_cohort_beta_frontier", "replay_is_deterministic"]
