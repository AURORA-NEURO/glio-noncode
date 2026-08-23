"""Power estimate assumption inventory."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class PowerAssumptionInventory:
    assumptions: tuple[str, ...]
    excluded_guarantees: tuple[str, ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def default_power_assumptions() -> PowerAssumptionInventory:
    assumptions = ("two-sided normal approximation", "independent variance proxy", "blocking factor multiplies requirement", "effect size is supplied rather than measured here")
    excluded = ("guaranteed power", "assay validity", "clinical utility", "safety")
    body = {"assumptions": assumptions, "excluded_guarantees": excluded, "accepted": True}
    return PowerAssumptionInventory(**body, content_address=content_hash(body, prefix="power-assumptions"))
__all__ = ["PowerAssumptionInventory", "default_power_assumptions"]
