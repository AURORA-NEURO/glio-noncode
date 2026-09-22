"""First-class structural event and haplotype representations."""

from __future__ import annotations

import math
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .errors import ValidationError
from .models import ReferenceContext
from .serialization import content_hash, freeze_json, jsonable

MAX_ALTERNATE_EVENT_GRAPH_EDGES = 100_000
MAX_ALTERNATE_EVENT_GRAPH_HOPS = 64
MAX_ALTERNATE_EVENT_GRAPH_PATHS = 10_000
MAX_ALTERNATE_EVENT_GRAPH_EXPANSIONS = 1_000_000
MAX_ALTERNATE_EVENT_GRAPH_IDENTIFIER_CHARS = 256
MAX_STRUCTURAL_ALLELE_CHARS = 100_000


def _validate_event_graph_identifier(value: str, label: str) -> None:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > MAX_ALTERNATE_EVENT_GRAPH_IDENTIFIER_CHARS
        or any(unicodedata.category(character) in {"Cc", "Cs"} for character in value)
    ):
        raise ValidationError(
            f"{label} must be nonempty control-free text of at most "
            f"{MAX_ALTERNATE_EVENT_GRAPH_IDENTIFIER_CHARS} characters"
        )


def _validate_structural_allele(value: str, label: str) -> None:
    if (
        type(value) is not str
        or not value.strip()
        or len(value) > MAX_STRUCTURAL_ALLELE_CHARS
        or any(unicodedata.category(character) in {"Cc", "Cs"} for character in value)
    ):
        raise ValidationError(
            f"{label} must be nonempty control-free text of at most "
            f"{MAX_STRUCTURAL_ALLELE_CHARS} characters"
        )


def _normalized_finite_number(value: object, label: str) -> float:
    if type(value) not in {int, float}:
        raise ValidationError(f"{label} must be a finite number")
    try:
        normalized = float(value)
    except OverflowError as exc:
        raise ValidationError(f"{label} must be a finite number") from exc
    if not math.isfinite(normalized):
        raise ValidationError(f"{label} must be a finite number")
    return normalized


class StructuralEventKind(str, Enum):  # noqa: UP042 - preserve existing str() behavior
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
        _validate_event_graph_identifier(self.breakend_id, "breakend ID")
        _validate_event_graph_identifier(self.mate_id, "breakend mate ID")
        _validate_event_graph_identifier(self.chromosome, "breakend chromosome")
        if type(self.position) is not int or self.position < 1:
            raise ValidationError("breakend position must be positive")
        if type(self.orientation) is not str or self.orientation not in {
            "forward",
            "reverse",
            "unknown",
        }:
            raise ValidationError("breakend orientation must be forward, reverse, or unknown")
        _validate_structural_allele(self.allele, "breakend allele")
        if self.copy_number is not None:
            copy_number = _normalized_finite_number(self.copy_number, "breakend copy number")
            if copy_number < 0.0:
                raise ValidationError("breakend copy number must be nonnegative")
            object.__setattr__(self, "copy_number", copy_number)


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
        _validate_event_graph_identifier(self.segment_id, "haplotype segment ID")
        _validate_event_graph_identifier(self.chromosome, "haplotype chromosome")
        _validate_event_graph_identifier(self.phase_set, "haplotype phase set")
        _validate_structural_allele(self.allele, "haplotype allele")
        if (
            type(self.start) is not int
            or type(self.end) is not int
            or self.start < 1
            or self.end < self.start
        ):
            raise ValidationError("haplotype segment interval is invalid")
        if not isinstance(self.source_variant_ids, (tuple, list)):
            raise ValidationError("haplotype source variant IDs must be a sequence")
        source_variant_ids = tuple(self.source_variant_ids)
        if not source_variant_ids:
            raise ValidationError("haplotype segment must retain source variants")
        for variant_id in source_variant_ids:
            _validate_event_graph_identifier(variant_id, "haplotype source variant ID")
        if len(source_variant_ids) != len(set(source_variant_ids)):
            raise ValidationError("haplotype source variant IDs must be unique")
        object.__setattr__(self, "source_variant_ids", source_variant_ids)


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
        _validate_event_graph_identifier(self.event_id, "structural event ID")
        _validate_event_graph_identifier(self.source_id, "structural event source ID")
        if not isinstance(self.kind, StructuralEventKind):
            raise ValidationError("structural event kind must be a StructuralEventKind")
        if not isinstance(self.context, ReferenceContext):
            raise ValidationError("structural event context must be a ReferenceContext")
        if not isinstance(self.breakends, (tuple, list)):
            raise ValidationError("structural event breakends must be a sequence")
        if not isinstance(self.haplotype_segments, (tuple, list)):
            raise ValidationError("structural event haplotype segments must be a sequence")
        breakends = tuple(self.breakends)
        haplotype_segments = tuple(self.haplotype_segments)
        if not breakends and not haplotype_segments:
            raise ValidationError("structural event requires breakends or phased segments")
        for name in ("reconstruction_support", "uncertainty"):
            value = _normalized_finite_number(getattr(self, name), name)
            if value < 0.0 or value > 1.0:
                raise ValidationError(f"{name} must be between 0 and 1")
            object.__setattr__(self, name, value)
        if any(not isinstance(item, Breakend) for item in breakends):
            raise ValidationError("structural event breakends must contain Breakend objects")
        if any(not isinstance(item, HaplotypeSegment) for item in haplotype_segments):
            raise ValidationError(
                "structural event haplotype segments must contain HaplotypeSegment objects"
            )
        breakend_ids = [item.breakend_id for item in breakends]
        if len(breakend_ids) != len(set(breakend_ids)):
            raise ValidationError("structural event breakend IDs must be unique")
        segment_ids = [item.segment_id for item in haplotype_segments]
        if len(segment_ids) != len(set(segment_ids)):
            raise ValidationError("structural event haplotype segment IDs must be unique")
        source_variant_ids = [
            variant_id
            for segment in haplotype_segments
            for variant_id in segment.source_variant_ids
        ]
        if len(source_variant_ids) != len(set(source_variant_ids)):
            raise ValidationError("structural event source variant IDs must be unique")
        breakends_by_id = {item.breakend_id: item for item in breakends}
        for breakend in breakends:
            mate = breakends_by_id.get(breakend.mate_id)
            if mate is None:
                raise ValidationError(f"breakend mate is missing: {breakend.mate_id}")
            if mate.breakend_id == breakend.breakend_id or mate.mate_id != breakend.breakend_id:
                raise ValidationError("structural event breakend mates must be reciprocal")
        if self.kind is StructuralEventKind.BREAKEND_PAIR and (
            len(breakends) != 2 or haplotype_segments
        ):
            raise ValidationError("breakend_pair events require exactly two paired breakends")
        if self.kind is StructuralEventKind.HAPLOTYPE and not haplotype_segments:
            raise ValidationError("haplotype events require at least one phased segment")
        if not isinstance(self.annotations, Mapping):
            raise ValidationError("structural event annotations must be an object")
        object.__setattr__(self, "breakends", breakends)
        object.__setattr__(self, "haplotype_segments", haplotype_segments)
        object.__setattr__(
            self,
            "annotations",
            freeze_json(self.annotations, field="structural event annotations"),
        )

    @property
    def content_address(self) -> str:
        return content_hash(jsonable(self))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"content_address": self.content_address}


@dataclass(frozen=True, slots=True)
class EventPath:
    """A descriptive path score, not a calibrated probability of mechanism.

    Path support is the geometric mean of declared edge supports. Uncertainty
    is one minus their product; both values remain descriptive summaries.
    """

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
        self._edge_ids: set[str] = set()
        self._edge_count = 0

    def add_edge(self, source_id: str, target_id: str, support: float, edge_id: str) -> None:
        _validate_event_graph_identifier(source_id, "event graph source ID")
        _validate_event_graph_identifier(target_id, "event graph target ID")
        _validate_event_graph_identifier(edge_id, "event graph edge ID")
        if isinstance(support, bool) or not isinstance(support, (int, float)):
            raise ValidationError("event edge support must be finite and between 0 and 1")
        try:
            support = float(support)
        except OverflowError as exc:
            raise ValidationError("event edge support must be finite and between 0 and 1") from exc
        if not math.isfinite(support) or not 0.0 <= support <= 1.0:
            raise ValidationError("event edge support must be between 0 and 1")
        if edge_id in self._edge_ids:
            raise ValidationError("event graph edge IDs must be unique")
        if self._edge_count >= MAX_ALTERNATE_EVENT_GRAPH_EDGES:
            raise ValidationError(
                f"event graph exceeds the {MAX_ALTERNATE_EVENT_GRAPH_EDGES}-edge limit"
            )
        self._edges.setdefault(source_id, []).append((target_id, support, edge_id))
        self._edge_ids.add(edge_id)
        self._edge_count += 1

    def paths(
        self,
        source_id: str,
        target_id: str,
        *,
        max_hops: int = 5,
        max_paths: int = 1_000,
        max_expansions: int = 100_000,
    ) -> tuple[EventPath, ...]:
        """Enumerate simple paths within explicit work, depth, and output budgets.

        Enumeration fails closed if an additional path or edge expansion would
        exceed its budget. It never returns an apparently complete partial set.
        """

        _validate_event_graph_identifier(source_id, "event graph source endpoint")
        _validate_event_graph_identifier(target_id, "event graph target endpoint")
        for value, label, maximum in (
            (max_hops, "max_hops", MAX_ALTERNATE_EVENT_GRAPH_HOPS),
            (max_paths, "max_paths", MAX_ALTERNATE_EVENT_GRAPH_PATHS),
            (max_expansions, "max_expansions", MAX_ALTERNATE_EVENT_GRAPH_EXPANSIONS),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
                raise ValidationError(f"{label} must be an integer between 1 and {maximum}")
        if source_id == target_id:
            return ()

        found: list[EventPath] = []
        expansion_count = 0

        def visit(
            node: str,
            nodes: tuple[str, ...],
            edges: tuple[str, ...],
            supports: tuple[float, ...],
        ) -> None:
            nonlocal expansion_count
            if len(edges) > max_hops:
                return
            if node == target_id:
                if len(found) >= max_paths:
                    raise ValidationError(
                        f"event graph path enumeration exceeds the {max_paths}-path limit"
                    )
                if any(support == 0.0 for support in supports):
                    path_support = 0.0
                    path_uncertainty = 1.0
                else:
                    log_product = math.fsum(math.log(support) for support in supports)
                    path_support = math.exp(log_product / len(supports))
                    path_uncertainty = -math.expm1(log_product)
                path_digest = content_hash({"nodes": nodes, "edges": edges}).split(":", 1)[1]
                path_id = "path-" + path_digest[:20]
                found.append(
                    EventPath(
                        path_id=path_id,
                        node_ids=nodes,
                        edge_ids=edges,
                        support=round(path_support, 6),
                        uncertainty=round(path_uncertainty, 6),
                        explanation="Alternate topology path retained for review.",
                    )
                )
                return
            if len(edges) == max_hops:
                return
            for next_node, support, edge_id in self._edges.get(node, ()):
                if next_node in nodes:
                    continue
                if expansion_count >= max_expansions:
                    raise ValidationError(
                        "event graph path enumeration exceeds the "
                        f"{max_expansions}-expansion limit"
                    )
                expansion_count += 1
                visit(next_node, nodes + (next_node,), edges + (edge_id,), supports + (support,))

        visit(source_id, (source_id,), (), ())
        return tuple(sorted(found, key=lambda path: (-path.support, path.path_id)))

    def node_count(self) -> int:
        nodes = set(self._edges)
        nodes.update(target for edges in self._edges.values() for target, _, _ in edges)
        return len(nodes)

    def edge_count(self) -> int:
        """Return the number of directed edges admitted to the graph."""

        return self._edge_count
