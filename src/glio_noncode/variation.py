"""First-class structural event and haplotype representations."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable

from .errors import ValidationError
from .models import ReferenceContext
from .serialization import content_hash, jsonable


class StructuralEventKind(str, Enum):
    BREAKEND_PAIR = "breakend_pair"
    DELETION = "deletion"
    DUPLICATION = "duplication"
    INVERSION = "inversion"
    TRANSLOCATION = "translocation"
    COPY_NUMBER = "copy_number"
    EC_DNA = "ec_dna"
    HAPLOTYPE = "haplotype"


@dataclass(frozen=True, slots=True)
class Breakend:
    """One side of a structural event with orientation and phasing metadata."""

    breakend_id: str
    chromosome: str
    position: int
    orientation: str
    mate_id: str
    allele: str = "N"
    copy_number: float | None = None

    def __post_init__(self) -> None:
        if not self.breakend_id or not self.mate_id or not self.chromosome:
            raise ValidationError("breakend identifiers and chromosome are required")
        if self.position < 1:
            raise ValidationError("breakend position must be positive")
        if self.orientation not in {"forward", "reverse", "unknown"}:
            raise ValidationError("breakend orientation must be forward, reverse, or unknown")


@dataclass(frozen=True, slots=True)
class HaplotypeSegment:
    """A phased segment retained as a path component rather than flattened."""

    segment_id: str
    chromosome: str
    start: int
    end: int
    phase_set: str
    allele: str
    source_variant_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.start < 1 or self.end < self.start:
            raise ValidationError("haplotype segment interval is invalid")
        if not self.source_variant_ids:
            raise ValidationError("haplotype segment must retain source variants")


@dataclass(frozen=True, slots=True)
class StructuralEvent:
    """A structural or phased event with explicit reconstruction uncertainty."""

    event_id: str
    kind: StructuralEventKind
    breakends: tuple[Breakend, ...]
    haplotype_segments: tuple[HaplotypeSegment, ...]
    context: ReferenceContext
    source_id: str
    reconstruction_support: float
    uncertainty: float
    annotations: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.event_id or not self.source_id:
            raise ValidationError("structural event ID and source are required")
        if not self.breakends and not self.haplotype_segments:
            raise ValidationError("structural event requires breakends or phased segments")
        for name in ("reconstruction_support", "uncertainty"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValidationError(f"{name} must be between 0 and 1")
        breakend_ids = {item.breakend_id for item in self.breakends}
        for breakend in self.breakends:
            if breakend.mate_id not in breakend_ids:
                raise ValidationError(f"breakend mate is missing: {breakend.mate_id}")

    @property
    def content_address(self) -> str:
        return content_hash(jsonable(self))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"content_address": self.content_address}


@dataclass(frozen=True, slots=True)
class EventPath:
    """A possible regulatory path through an alternate event graph."""

    path_id: str
    node_ids: tuple[str, ...]
    edge_ids: tuple[str, ...]
    support: float
    uncertainty: float
    explanation: str

    def __post_init__(self) -> None:
        if not self.node_ids or len(self.node_ids) < 2:
            raise ValidationError("event path requires at least two nodes")
        if not 0.0 <= self.support <= 1.0 or not 0.0 <= self.uncertainty <= 1.0:
            raise ValidationError("event path values must be between 0 and 1")


class AlternateEventGraph:
    """Directed graph used to preserve alternate topology explanations."""

    def __init__(self) -> None:
        self._edges: dict[str, list[tuple[str, float, str]]] = {}

    def add_edge(self, source_id: str, target_id: str, support: float, edge_id: str) -> None:
        if not source_id or not target_id or not edge_id:
            raise ValidationError("event graph edge IDs are required")
        if not 0.0 <= support <= 1.0:
            raise ValidationError("event edge support must be between 0 and 1")
        self._edges.setdefault(source_id, []).append((target_id, support, edge_id))

    def paths(self, source_id: str, target_id: str, *, max_hops: int = 5) -> tuple[EventPath, ...]:
        found: list[EventPath] = []

        def visit(node: str, nodes: tuple[str, ...], edges: tuple[str, ...], supports: tuple[float, ...]) -> None:
            if len(edges) > max_hops:
                return
            if node == target_id:
                product = 1.0
                for support in supports:
                    product *= support
                path_id = "path-" + content_hash({"nodes": nodes, "edges": edges}).split(":", 1)[1][:20]
                found.append(
                    EventPath(
                        path_id=path_id,
                        node_ids=nodes,
                        edge_ids=edges,
                        support=round(product ** (1 / max(1, len(supports))), 6),
                        uncertainty=round(1.0 - product, 6),
                        explanation="Alternate topology path retained for review.",
                    )
                )
                return
            for next_node, support, edge_id in self._edges.get(node, ()):
                if next_node in nodes:
                    continue
                visit(next_node, nodes + (next_node,), edges + (edge_id,), supports + (support,))

        visit(source_id, (source_id,), (), ())
        return tuple(sorted(found, key=lambda path: (-path.support, path.path_id)))

    def node_count(self) -> int:
        nodes = set(self._edges)
        nodes.update(target for edges in self._edges.values() for target, _, _ in edges)
        return len(nodes)
