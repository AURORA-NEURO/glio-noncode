"""Short operator handbook for inspecting a released link run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_runbook import LinkGraphAlphaFrontierRunbook
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierHandbook:
    title: str
    principles: tuple[str, ...]
    commands: tuple[str, ...]
    escalation: tuple[str, ...]
    runbook_address: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"title": self.title, "principles": self.principles, "commands": self.commands, "escalation": self.escalation, "runbook_address": self.runbook_address}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_alpha_frontier_handbook(runbook: LinkGraphAlphaFrontierRunbook) -> LinkGraphAlphaFrontierHandbook:
    return LinkGraphAlphaFrontierHandbook("Link graph alpha frontier handbook", ("preserve context", "retain alternatives", "inspect source receipts", "treat candidate edges as descriptive"), ("fixture", "evaluate", "metrics", "review", "release"), ("context mismatch", "contradictory evidence", "missing components", "failed replay"), runbook.content_address)


__all__ = ["LinkGraphAlphaFrontierHandbook", "build_link_graph_alpha_frontier_handbook"]
