"""Step ledger for auditing one end-to-end beta pipeline run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_beta_frontier_pipeline import TopologyBetaFrontierPipelineReport


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierLedgerEntry:
    sequence: int
    stage_id: str
    status: str
    input_count: int
    output_count: int
    detail: str
    run_id: str
    stage_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierReplayLedger:
    run_id: str
    entries: tuple[TopologyBetaFrontierLedgerEntry, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def entry(self, stage_id: str) -> TopologyBetaFrontierLedgerEntry:
        for item in self.entries:
            if item.stage_id == stage_id:
                return item
        raise KeyError(stage_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"run_id": self.run_id, "entries": [item.to_dict() for item in self.entries], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_beta_frontier_replay_ledger(pipeline: TopologyBetaFrontierPipelineReport) -> TopologyBetaFrontierReplayLedger:
    entries = tuple(TopologyBetaFrontierLedgerEntry(index, stage.stage_id, stage.status, stage.input_count, stage.output_count, stage.detail, pipeline.run_id, content_hash({"run_id": pipeline.run_id, "sequence": index, "stage": stage})) for index, stage in enumerate(pipeline.stages, start=1))
    accepted = len(entries) == 12 and tuple(item.sequence for item in entries) == tuple(range(1, 13)) and all(item.status == "passed" and item.stage_address.startswith("sha256:") for item in entries)
    return TopologyBetaFrontierReplayLedger(pipeline.run_id, entries, accepted)


def compare_topology_beta_frontier_ledgers(first: TopologyBetaFrontierReplayLedger, second: TopologyBetaFrontierReplayLedger) -> dict[str, Any]:
    first_stages = tuple((item.stage_id, item.status, item.input_count, item.output_count) for item in first.entries)
    second_stages = tuple((item.stage_id, item.status, item.input_count, item.output_count) for item in second.entries)
    return {"same_run": first.run_id == second.run_id, "same_stages": first_stages == second_stages, "first_address": first.content_address, "second_address": second.content_address, "accepted": first_stages == second_stages and first.accepted and second.accepted}


__all__ = ["TopologyBetaFrontierLedgerEntry", "TopologyBetaFrontierReplayLedger", "build_topology_beta_frontier_replay_ledger", "compare_topology_beta_frontier_ledgers"]
