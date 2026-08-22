"""Machine-readable operation catalog for Domain 08 C01-C04."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_frontier_public_data import CellContextFrontierOperation
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextFrontierCatalogEntry:
    capability_id: str
    operation: CellContextFrontierOperation
    primitive: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    states: tuple[str, ...]
    controls: tuple[str, ...]
    limitations: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if (
            not self.capability_id
            or not self.primitive
            or not self.inputs
            or not self.outputs
            or not self.states
            or not self.controls
            or not self.limitations
        ):
            raise ValidationError("cell catalog entry is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextFrontierCatalog:
    entries: tuple[CellContextFrontierCatalogEntry, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if len(self.entries) != 4:
            raise ValidationError("cell catalog requires four entries")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def get(self, capability_id: str) -> CellContextFrontierCatalogEntry:
        for item in self.entries:
            if item.capability_id == capability_id:
                return item
        raise KeyError(capability_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cell_context_frontier_catalog() -> CellContextFrontierCatalog:
    states = ("supported", "partial", "ambiguous", "contradictory", "out_of_domain", "abstained")
    common_controls = ("malformed_row", "context_mismatch", "missing_dimension", "uncertainty")
    entries = (
        CellContextFrontierCatalogEntry(
            "GNC-D08-C01",
            CellContextFrontierOperation.DISEASE_ONTOLOGY,
            "DiseaseOntologyContextualizer.resolve",
            ("observation_text", "context_key"),
            ("candidate", "state", "uncertainty"),
            states,
            common_controls,
            ("taxonomy does not diagnose", "external calibration remains"),
        ),
        CellContextFrontierCatalogEntry(
            "GNC-D08-C02",
            CellContextFrontierOperation.AGE_ROUTE,
            "AdultPediatricRouter.route",
            ("observation_text", "age_group", "context_key"),
            ("route", "conflict", "state"),
            states,
            common_controls + ("unknown_age",),
            ("route is not clinical behavior", "mixed-age extension remains"),
        ),
        CellContextFrontierCatalogEntry(
            "GNC-D08-C03",
            CellContextFrontierOperation.MOLECULAR_STATE,
            "MolecularClassStateContextualizer.resolve",
            ("observation_text", "context_key"),
            ("class", "state", "uncertainty"),
            states,
            common_controls,
            ("class and state are separate", "no actionability claim"),
        ),
        CellContextFrontierCatalogEntry(
            "GNC-D08-C04",
            CellContextFrontierOperation.TERRITORY_ASSEMBLY,
            "CellStateContextAssembler.assemble",
            ("observation_text", "context_key"),
            ("territory", "assembled_context", "weakest_component"),
            states,
            common_controls + ("ambiguous_territory",),
            ("assembly is research context", "territory does not establish identity"),
        ),
    )
    return CellContextFrontierCatalog(entries, len({item.operation for item in entries}) == 4)


__all__ = [
    "CellContextFrontierCatalog",
    "CellContextFrontierCatalogEntry",
    "build_cell_context_frontier_catalog",
]
