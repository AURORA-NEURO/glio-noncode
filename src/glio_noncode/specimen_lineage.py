"""Deep specimen lineage and longitudinal context contracts.

This module extends the Domain 03 specimen boundary with four independent
operations:

* multi-region lineage resolution from declared region/parent edges;
* subject-scoped longitudinal specimen linking with explicit ordering;
* primary/recurrence phase mapping from declared phase and event evidence; and
* treatment-exposure contextualization against explicit time intervals.

All operations are deterministic and project-local. They do not identify a
person, authenticate a specimen, infer recurrence from time alone, or convert
temporal proximity into treatment response. Missing dates, missing parents,
conflicting phase declarations, overlapping exposures, and context mismatch
remain visible beside bounded results.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty


class LineageAlphaState(StrEnum):
    """Evidence state shared by the Domain 03 longitudinal adapters."""

    SUPPORTED = "supported"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    ABSTAINED = "abstained"
    INVALID = "invalid"
    OUT_OF_DOMAIN = "out_of_domain"
    CONTRADICTORY = "contradictory"


class SpecimenPhase(StrEnum):
    """Conservative phase vocabulary for longitudinal specimen records."""

    PRIMARY = "primary"
    RECURRENCE = "recurrence"
    INTERVAL = "interval"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class LineageAlphaIssue:
    """A row-addressable longitudinal anomaly retained with its raw hash."""

    code: str
    message: str
    raw_hash: str
    row_number: int | None = None
    source_id: str = "unspecified"
    severity: str = "warning"
    raw_record: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty(self.code, "issue code")
        require_non_empty(self.message, "issue message")
        require_non_empty(self.raw_hash, "issue raw_hash")
        if self.row_number is not None and self.row_number < 1:
            raise ValidationError("issue row_number must be positive")
        if self.severity not in {"warning", "error"}:
            raise ValidationError("issue severity must be warning or error")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class RegionObservation:
    """A region/specimen record used to build subject-local lineage."""

    region_id: str
    sample_id: str
    subject_id: str
    region_label: str
    parent_region_ids: tuple[str, ...]
    relationship: str
    collection_time: str | None
    order_index: int | None
    context_key: str | None
    source_id: str
    source_version: str
    raw_hash: str

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.region_id, "region_id"),
            (self.sample_id, "sample_id"),
            (self.subject_id, "subject_id"),
            (self.region_label, "region_label"),
            (self.relationship, "relationship"),
        ):
            require_non_empty(value, field_name)
        if self.order_index is not None and self.order_index < 0:
            raise ValidationError("region order_index cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class RegionLineageEdge:
    """One declared parent-to-child region relationship."""

    parent_region_id: str
    child_region_id: str
    relationship: str
    evidence: tuple[str, ...]
    source_ids: tuple[str, ...]
    state: LineageAlphaState

    def __post_init__(self) -> None:
        require_non_empty(self.parent_region_id, "parent_region_id")
        require_non_empty(self.child_region_id, "child_region_id")
        if self.parent_region_id == self.child_region_id:
            raise ValidationError("lineage edge cannot point from a region to itself")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class RegionLineage:
    """Resolved region graph for one subject."""

    subject_id: str
    region_ids: tuple[str, ...]
    edges: tuple[RegionLineageEdge, ...]
    roots: tuple[str, ...]
    leaves: tuple[str, ...]
    missing_parent_ids: tuple[str, ...]
    cycle_region_ids: tuple[str, ...]
    state: LineageAlphaState
    source_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MultiRegionLineageReport:
    """All subject-local region graphs and input diagnostics."""

    input_hash: str
    context_key: str | None
    state: LineageAlphaState
    lineages: tuple[RegionLineage, ...]
    observations: tuple[RegionObservation, ...]
    issues: tuple[LineageAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class MultiRegionLineageResolver:
    """Resolve only the region relationships explicitly present in the input."""

    def resolve(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str | None = None,
    ) -> MultiRegionLineageReport:
        values = tuple(records)
        input_hash = content_hash(values)
        issues: list[LineageAlphaIssue] = []
        observations: list[RegionObservation] = []
        seen_ids: set[str] = set()
        context_mismatch = False
        for row_number, row in enumerate(values, start=1):
            if not isinstance(row, Mapping):
                issues.append(
                    LineageAlphaIssue(
                        "row_not_object",
                        "region lineage record must be an object",
                        content_hash({"row": row}),
                        row_number,
                        severity="error",
                    )
                )
                continue
            raw_hash = _raw_hash(row)
            row_context = _context(row)
            if context_key and row_context and row_context != context_key:
                context_mismatch = True
                issues.append(
                    LineageAlphaIssue(
                        "context_mismatch",
                        "region lineage record is outside the requested context",
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                        raw_record=dict(row),
                    )
                )
                continue
            try:
                observation = self._parse_region(row, raw_hash)
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    LineageAlphaIssue(
                        "invalid_region_record",
                        str(exc),
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                        raw_record=dict(row),
                    )
                )
                continue
            if observation.region_id in seen_ids:
                issues.append(
                    LineageAlphaIssue(
                        "duplicate_region_id",
                        f"region ID is repeated: {observation.region_id}",
                        raw_hash,
                        row_number,
                        source_id=observation.source_id,
                        severity="error",
                        raw_record=dict(row),
                    )
                )
                continue
            seen_ids.add(observation.region_id)
            observations.append(observation)
        grouped: dict[str, list[RegionObservation]] = defaultdict(list)
        for observation in observations:
            grouped[observation.subject_id].append(observation)
        lineages = tuple(
            self._resolve_subject(subject_id, group, issues)
            for subject_id, group in sorted(grouped.items())
        )
        if context_mismatch and not observations:
            state = LineageAlphaState.OUT_OF_DOMAIN
        elif any(item.state == LineageAlphaState.CONTRADICTORY for item in lineages):
            state = LineageAlphaState.CONTRADICTORY
        elif any(item.state == LineageAlphaState.PARTIAL for item in lineages) or issues:
            state = LineageAlphaState.PARTIAL
        elif not lineages:
            state = LineageAlphaState.ABSTAINED
        elif context_mismatch:
            state = LineageAlphaState.PARTIAL
        else:
            state = LineageAlphaState.SUPPORTED
        warnings = (
            "Lineage edges are project-local declarations and do not authenticate specimen origin.",
            "A missing parent remains a missing graph node; no relationship is manufactured.",
        )
        return MultiRegionLineageReport(
            input_hash=input_hash,
            context_key=context_key,
            state=state,
            lineages=lineages,
            observations=tuple(observations),
            issues=tuple(issues),
            warnings=warnings,
            content_address=content_hash(
                {"input_hash": input_hash, "state": state, "lineages": lineages, "issues": issues}
            ),
        )

    @staticmethod
    def _parse_region(row: Mapping[str, Any], raw_hash: str) -> RegionObservation:
        parent_values = _text_tuple(
            _value(row, "parent_region_ids", "parent_region_id", "parents", default=())
        )
        order_value = _value(row, "order_index", "region_order", default=None)
        return RegionObservation(
            region_id=str(_value(row, "region_id", "region", "id")),
            sample_id=str(_value(row, "sample_id", "sample", default="unspecified")),
            subject_id=str(_value(row, "subject_id", "subject", "case_id")),
            region_label=str(
                _value(row, "region_label", "region_name", "label", default="unspecified")
            ),
            parent_region_ids=tuple(dict.fromkeys(parent_values)),
            relationship=str(_value(row, "relationship", "relation", default="region")),
            collection_time=_optional_text(
                _value(row, "collection_time", "collected_at", "time", default=None)
            ),
            order_index=_optional_int(order_value),
            context_key=_context(row),
            source_id=_source_id(row),
            source_version=_source_version(row),
            raw_hash=raw_hash,
        )

    @staticmethod
    def _resolve_subject(
        subject_id: str,
        group: Sequence[RegionObservation],
        issues: list[LineageAlphaIssue],
    ) -> RegionLineage:
        known = {item.region_id for item in group}
        by_child: dict[str, list[RegionLineageEdge]] = defaultdict(list)
        missing: set[str] = set()
        for observation in group:
            for parent_id in observation.parent_region_ids:
                edge_state = LineageAlphaState.SUPPORTED
                if parent_id not in known:
                    missing.add(parent_id)
                    edge_state = LineageAlphaState.PARTIAL
                    issues.append(
                        LineageAlphaIssue(
                            "missing_parent_region",
                            f"parent region is absent from the snapshot: {parent_id}",
                            observation.raw_hash,
                            source_id=observation.source_id,
                            severity="warning",
                            raw_record=observation.to_dict(),
                        )
                    )
                edge = RegionLineageEdge(
                    parent_region_id=parent_id,
                    child_region_id=observation.region_id,
                    relationship=observation.relationship,
                    evidence=("declared_parent_region",),
                    source_ids=(observation.source_id,),
                    state=edge_state,
                )
                by_child[observation.region_id].append(edge)
        edges = tuple(
            edge
            for child in sorted(by_child)
            for edge in sorted(
                by_child[child], key=lambda item: (item.parent_region_id, item.relationship)
            )
        )
        cycles = _cycle_nodes(tuple(item.region_id for item in group), edges)
        if cycles:
            issues.append(
                LineageAlphaIssue(
                    "lineage_cycle",
                    "region relationships contain a directed cycle",
                    content_hash(cycles),
                    source_id=group[0].source_id,
                    severity="error",
                    raw_record={"subject_id": subject_id, "region_ids": cycles},
                )
            )
        children = {edge.child_region_id for edge in edges}
        parents = {edge.parent_region_id for edge in edges if edge.parent_region_id in known}
        roots = tuple(sorted(known - children))
        leaves = tuple(sorted(known - parents))
        if cycles:
            state = LineageAlphaState.CONTRADICTORY
        elif missing:
            state = LineageAlphaState.PARTIAL
        elif len(known) < 2:
            state = LineageAlphaState.PARTIAL
        else:
            state = LineageAlphaState.SUPPORTED
        body = {
            "subject_id": subject_id,
            "region_ids": tuple(sorted(known)),
            "edges": edges,
            "missing": tuple(sorted(missing)),
            "cycles": cycles,
        }
        return RegionLineage(
            subject_id=subject_id,
            region_ids=tuple(sorted(known)),
            edges=edges,
            roots=roots,
            leaves=leaves,
            missing_parent_ids=tuple(sorted(missing)),
            cycle_region_ids=cycles,
            state=state,
            source_ids=tuple(sorted({item.source_id for item in group})),
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class LongitudinalSpecimenObservation:
    """A specimen observation with normalized subject and temporal fields."""

    specimen_id: str
    sample_id: str
    subject_id: str
    tissue: str
    timepoint: str
    collection_time: str | None
    time_sort_key: tuple[int, str]
    predecessor_specimen_id: str | None
    phase_hint: str | None
    context_key: str | None
    source_id: str
    source_version: str
    raw_hash: str

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.specimen_id, "specimen_id"),
            (self.sample_id, "sample_id"),
            (self.subject_id, "subject_id"),
            (self.tissue, "tissue"),
            (self.timepoint, "timepoint"),
        ):
            require_non_empty(value, field_name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LongitudinalSpecimenLink:
    """One same-subject specimen link with explicit or inferred basis."""

    link_id: str
    subject_id: str
    predecessor_specimen_id: str
    successor_specimen_id: str
    relation: str
    ordering_basis: str
    gap_label: str
    source_ids: tuple[str, ...]
    state: LineageAlphaState
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LongitudinalLinkReport:
    """Ordered specimen links and unresolved temporal diagnostics."""

    input_hash: str
    context_key: str | None
    state: LineageAlphaState
    observations: tuple[LongitudinalSpecimenObservation, ...]
    links: tuple[LongitudinalSpecimenLink, ...]
    unlinked_specimen_ids: tuple[str, ...]
    issues: tuple[LineageAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class LongitudinalSpecimenLinker:
    """Link specimens within a subject without crossing subject boundaries."""

    def link(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str | None = None,
        link_singleton: bool = False,
    ) -> LongitudinalLinkReport:
        values = tuple(records)
        input_hash = content_hash(values)
        issues: list[LineageAlphaIssue] = []
        observations: list[LongitudinalSpecimenObservation] = []
        context_mismatch = False
        seen_ids: set[str] = set()
        for row_number, row in enumerate(values, start=1):
            if not isinstance(row, Mapping):
                issues.append(
                    LineageAlphaIssue(
                        "row_not_object",
                        "longitudinal specimen record must be an object",
                        content_hash({"row": row}),
                        row_number,
                        severity="error",
                    )
                )
                continue
            raw_hash = _raw_hash(row)
            row_context = _context(row)
            if context_key and row_context and row_context != context_key:
                context_mismatch = True
                issues.append(
                    LineageAlphaIssue(
                        "context_mismatch",
                        "longitudinal specimen record is outside the requested context",
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                        raw_record=dict(row),
                    )
                )
                continue
            try:
                observation = self._parse(row, raw_hash)
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    LineageAlphaIssue(
                        "invalid_longitudinal_specimen",
                        str(exc),
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                        raw_record=dict(row),
                    )
                )
                continue
            if observation.specimen_id in seen_ids:
                issues.append(
                    LineageAlphaIssue(
                        "duplicate_specimen_id",
                        f"specimen ID is repeated: {observation.specimen_id}",
                        raw_hash,
                        row_number,
                        source_id=observation.source_id,
                        severity="error",
                        raw_record=dict(row),
                    )
                )
                continue
            seen_ids.add(observation.specimen_id)
            observations.append(observation)
        grouped: dict[str, list[LongitudinalSpecimenObservation]] = defaultdict(list)
        for observation in observations:
            grouped[observation.subject_id].append(observation)
        links: list[LongitudinalSpecimenLink] = []
        unlinked: set[str] = set()
        for subject_id, group in sorted(grouped.items()):
            ordered = sorted(group, key=lambda item: (item.time_sort_key, item.specimen_id))
            by_id = {item.specimen_id: item for item in ordered}
            explicit_successors: set[str] = set()
            for observation in ordered:
                predecessor = observation.predecessor_specimen_id
                if predecessor:
                    if predecessor not in by_id:
                        issues.append(
                            LineageAlphaIssue(
                                "missing_predecessor_specimen",
                                f"predecessor specimen is absent: {predecessor}",
                                observation.raw_hash,
                                source_id=observation.source_id,
                                severity="warning",
                                raw_record=observation.to_dict(),
                            )
                        )
                        unlinked.add(observation.specimen_id)
                        continue
                    if predecessor == observation.specimen_id:
                        issues.append(
                            LineageAlphaIssue(
                                "self_predecessor",
                                "specimen cannot be its own predecessor",
                                observation.raw_hash,
                                source_id=observation.source_id,
                                severity="error",
                                raw_record=observation.to_dict(),
                            )
                        )
                        unlinked.add(observation.specimen_id)
                        continue
                    explicit_successors.add(observation.specimen_id)
                    links.append(
                        self._link(
                            subject_id,
                            by_id[predecessor],
                            observation,
                            "declared_predecessor",
                        )
                    )
            if not any(item.predecessor_specimen_id for item in ordered):
                if len(ordered) >= 2:
                    for index in range(len(ordered) - 1):
                        predecessor = ordered[index]
                        successor = ordered[index + 1]
                        if predecessor.tissue != successor.tissue:
                            issues.append(
                                LineageAlphaIssue(
                                    "cross_tissue_inferred_link",
                                    "adjacent specimens have different tissue labels; "
                                    "link is retained as partial",
                                    successor.raw_hash,
                                    source_id=successor.source_id,
                                    severity="warning",
                                    raw_record=successor.to_dict(),
                                )
                            )
                        links.append(self._link(subject_id, predecessor, successor, "ordered_time"))
                        explicit_successors.add(successor.specimen_id)
                elif ordered and not link_singleton:
                    unlinked.add(ordered[0].specimen_id)
            for observation in ordered:
                if (
                    observation.specimen_id not in explicit_successors
                    and observation.specimen_id
                    not in {
                        link.successor_specimen_id
                        for link in links
                        if link.subject_id == subject_id
                    }
                ):
                    if len(ordered) > 1 and observation.specimen_id != ordered[0].specimen_id:
                        unlinked.add(observation.specimen_id)
        links = sorted(
            links,
            key=lambda item: (
                item.subject_id,
                item.predecessor_specimen_id,
                item.successor_specimen_id,
            ),
        )
        if context_mismatch and not observations:
            state = LineageAlphaState.OUT_OF_DOMAIN
        elif not observations:
            state = LineageAlphaState.ABSTAINED
        elif any(issue.severity == "error" for issue in issues):
            state = LineageAlphaState.CONTRADICTORY
        elif any(item.state == LineageAlphaState.PARTIAL for item in links) or unlinked or issues:
            state = LineageAlphaState.PARTIAL
        elif context_mismatch:
            state = LineageAlphaState.PARTIAL
        else:
            state = LineageAlphaState.SUPPORTED
        warnings = (
            "Links use same-subject declarations and declared or ordered temporal evidence only.",
            "An ordered link does not establish biological evolution or treatment response.",
        )
        return LongitudinalLinkReport(
            input_hash=input_hash,
            context_key=context_key,
            state=state,
            observations=tuple(observations),
            links=tuple(links),
            unlinked_specimen_ids=tuple(sorted(unlinked)),
            issues=tuple(issues),
            warnings=warnings,
            content_address=content_hash(
                {"input_hash": input_hash, "state": state, "links": links, "issues": issues}
            ),
        )

    @staticmethod
    def _parse(row: Mapping[str, Any], raw_hash: str) -> LongitudinalSpecimenObservation:
        collection_time = _optional_text(
            _value(row, "collection_time", "collected_at", "date", "time", default=None)
        )
        timepoint = str(_value(row, "timepoint", "visit", default="unspecified"))
        time_sort_key = _time_sort_key(collection_time, timepoint)
        return LongitudinalSpecimenObservation(
            specimen_id=str(_value(row, "specimen_id", "sample_id", "id")),
            sample_id=str(_value(row, "sample_id", "sample", "specimen_id", default="unspecified")),
            subject_id=str(_value(row, "subject_id", "subject", "case_id")),
            tissue=str(
                _value(row, "tissue", "tissue_type", "anatomic_site", default="unspecified")
            ),
            timepoint=timepoint,
            collection_time=collection_time,
            time_sort_key=time_sort_key,
            predecessor_specimen_id=_optional_text(
                _value(
                    row,
                    "predecessor_specimen_id",
                    "previous_specimen_id",
                    "parent_specimen_id",
                    default=None,
                )
            ),
            phase_hint=_optional_text(_value(row, "phase", "disease_phase", default=None)),
            context_key=_context(row),
            source_id=_source_id(row),
            source_version=_source_version(row),
            raw_hash=raw_hash,
        )

    @staticmethod
    def _link(
        subject_id: str,
        predecessor: LongitudinalSpecimenObservation,
        successor: LongitudinalSpecimenObservation,
        basis: str,
    ) -> LongitudinalSpecimenLink:
        gap_label = _gap_label(predecessor.collection_time, successor.collection_time)
        body = {
            "subject_id": subject_id,
            "predecessor": predecessor.specimen_id,
            "successor": successor.specimen_id,
            "basis": basis,
        }
        state = (
            LineageAlphaState.PARTIAL
            if predecessor.collection_time is None or successor.collection_time is None
            else LineageAlphaState.SUPPORTED
        )
        return LongitudinalSpecimenLink(
            link_id="longitudinal:" + content_hash(body).split(":", 1)[1][:24],
            subject_id=subject_id,
            predecessor_specimen_id=predecessor.specimen_id,
            successor_specimen_id=successor.specimen_id,
            relation="same_subject_temporal",
            ordering_basis=basis,
            gap_label=gap_label,
            source_ids=tuple(sorted({predecessor.source_id, successor.source_id})),
            state=state,
            content_address=content_hash(body | {"state": state}),
        )


@dataclass(frozen=True, slots=True)
class PhaseAssignment:
    """One specimen phase assignment with retained evidence basis."""

    specimen_id: str
    subject_id: str
    phase: SpecimenPhase
    phase_state: LineageAlphaState
    evidence: tuple[str, ...]
    conflicting_labels: tuple[str, ...]
    collection_time: str | None
    source_ids: tuple[str, ...]
    raw_hashes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PrimaryRecurrenceMappingReport:
    """Primary/recurrence phase assignments and unresolved records."""

    input_hash: str
    context_key: str | None
    state: LineageAlphaState
    assignments: tuple[PhaseAssignment, ...]
    unknown_specimen_ids: tuple[str, ...]
    issues: tuple[LineageAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class PrimaryRecurrencePhaseMapper:
    """Map only declared phase evidence and explicit primary relationships."""

    _PRIMARY_LABELS = frozenset({"primary", "diagnosis", "initial", "new_diagnosis"})
    _RECURRENCE_LABELS = frozenset(
        {"recurrence", "recurrent", "relapse", "progression", "secondary"}
    )
    _INTERVAL_LABELS = frozenset({"interval", "maintenance", "surveillance", "follow_up"})

    def map(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str | None = None,
    ) -> PrimaryRecurrenceMappingReport:
        values = tuple(records)
        input_hash = content_hash(values)
        issues: list[LineageAlphaIssue] = []
        observations: list[LongitudinalSpecimenObservation] = []
        context_mismatch = False
        for row_number, row in enumerate(values, start=1):
            if not isinstance(row, Mapping):
                issues.append(
                    LineageAlphaIssue(
                        "row_not_object",
                        "phase mapping record must be an object",
                        content_hash({"row": row}),
                        row_number,
                        severity="error",
                    )
                )
                continue
            raw_hash = _raw_hash(row)
            row_context = _context(row)
            if context_key and row_context and row_context != context_key:
                context_mismatch = True
                issues.append(
                    LineageAlphaIssue(
                        "context_mismatch",
                        "phase mapping record is outside the requested context",
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                    )
                )
                continue
            try:
                observations.append(LongitudinalSpecimenLinker._parse(row, raw_hash))
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    LineageAlphaIssue(
                        "invalid_phase_record",
                        str(exc),
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                        raw_record=dict(row),
                    )
                )
        grouped: dict[str, list[LongitudinalSpecimenObservation]] = defaultdict(list)
        for observation in observations:
            grouped[observation.subject_id].append(observation)
        assignments: list[PhaseAssignment] = []
        unknown: set[str] = set()
        for subject_id, group in sorted(grouped.items()):
            ordered = sorted(group, key=lambda item: (item.time_sort_key, item.specimen_id))
            explicit_primary_ids = {
                item.specimen_id
                for item in ordered
                if _phase_label(item.phase_hint) == SpecimenPhase.PRIMARY
            }
            if len(explicit_primary_ids) > 1:
                issues.append(
                    LineageAlphaIssue(
                        "multiple_primary_declarations",
                        "multiple specimens are explicitly labeled primary for one subject",
                        content_hash(sorted(explicit_primary_ids)),
                        source_id=ordered[0].source_id,
                        severity="warning",
                        raw_record={"subject_id": subject_id},
                    )
                )
            for observation in ordered:
                labels = _phase_labels(observation.phase_hint)
                conflicting = tuple(sorted(labels)) if len(labels) > 1 else ()
                if conflicting:
                    phase = SpecimenPhase.UNKNOWN
                    state = LineageAlphaState.CONTRADICTORY
                    evidence = ("conflicting_phase_labels",)
                    issues.append(
                        LineageAlphaIssue(
                            "conflicting_phase_labels",
                            "phase labels map to more than one phase",
                            observation.raw_hash,
                            source_id=observation.source_id,
                            severity="error",
                            raw_record=observation.to_dict(),
                        )
                    )
                elif labels:
                    phase = next(iter(labels))
                    state = LineageAlphaState.SUPPORTED
                    evidence = ("declared_phase_label",)
                elif observation.predecessor_specimen_id in explicit_primary_ids:
                    phase = SpecimenPhase.RECURRENCE
                    state = LineageAlphaState.SUPPORTED
                    evidence = ("declared_predecessor_is_primary",)
                else:
                    phase = SpecimenPhase.UNKNOWN
                    state = LineageAlphaState.PARTIAL
                    evidence = ("no_explicit_primary_or_recurrence_evidence",)
                    unknown.add(observation.specimen_id)
                body = {
                    "specimen_id": observation.specimen_id,
                    "subject_id": subject_id,
                    "phase": phase,
                    "evidence": evidence,
                    "raw_hash": observation.raw_hash,
                }
                assignments.append(
                    PhaseAssignment(
                        specimen_id=observation.specimen_id,
                        subject_id=subject_id,
                        phase=phase,
                        phase_state=state,
                        evidence=evidence,
                        conflicting_labels=conflicting,
                        collection_time=observation.collection_time,
                        source_ids=(observation.source_id,),
                        raw_hashes=(observation.raw_hash,),
                        content_address=content_hash(body),
                    )
                )
        if context_mismatch and not observations:
            state = LineageAlphaState.OUT_OF_DOMAIN
        elif any(item.phase_state == LineageAlphaState.CONTRADICTORY for item in assignments):
            state = LineageAlphaState.CONTRADICTORY
        elif not assignments:
            state = LineageAlphaState.ABSTAINED
        elif (
            unknown
            or issues
            or any(item.phase_state == LineageAlphaState.PARTIAL for item in assignments)
        ):
            state = LineageAlphaState.PARTIAL
        elif context_mismatch:
            state = LineageAlphaState.PARTIAL
        else:
            state = LineageAlphaState.SUPPORTED
        warnings = (
            "A later collection date alone is not treated as recurrence evidence.",
            "Phase assignments are research context labels and do not establish "
            "clinical disease status.",
        )
        return PrimaryRecurrenceMappingReport(
            input_hash=input_hash,
            context_key=context_key,
            state=state,
            assignments=tuple(assignments),
            unknown_specimen_ids=tuple(sorted(unknown)),
            issues=tuple(issues),
            warnings=warnings,
            content_address=content_hash(
                {
                    "input_hash": input_hash,
                    "state": state,
                    "assignments": assignments,
                    "issues": issues,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class TreatmentExposure:
    """One explicit therapy interval for one subject."""

    exposure_id: str
    subject_id: str
    therapy_id: str
    therapy_class: str
    start_time: str
    end_time: str | None
    start_sort_key: tuple[int, str]
    end_sort_key: tuple[int, str] | None
    status: str
    source_id: str
    source_version: str
    context_key: str | None
    raw_hash: str

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.exposure_id, "exposure_id"),
            (self.subject_id, "subject_id"),
            (self.therapy_id, "therapy_id"),
            (self.therapy_class, "therapy_class"),
            (self.start_time, "start_time"),
        ):
            require_non_empty(value, field_name)
        if self.end_sort_key is not None and self.end_sort_key < self.start_sort_key:
            raise ValidationError("treatment exposure end precedes start")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ExposureContext:
    """One specimen-to-exposure temporal relationship."""

    specimen_id: str
    subject_id: str
    exposure_id: str
    therapy_id: str
    relation: str
    temporal_basis: str
    specimen_time: str | None
    exposure_start: str
    exposure_end: str | None
    gap_label: str
    overlapping_exposure_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    state: LineageAlphaState
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TreatmentExposureReport:
    """Exposure contexts and uncontextualized specimens."""

    input_hash: str
    context_key: str | None
    state: LineageAlphaState
    specimens: tuple[LongitudinalSpecimenObservation, ...]
    exposures: tuple[TreatmentExposure, ...]
    contexts: tuple[ExposureContext, ...]
    uncontextualized_specimen_ids: tuple[str, ...]
    issues: tuple[LineageAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class TreatmentExposureContextualizer:
    """Join specimens to explicit therapy intervals within one subject."""

    def contextualize(
        self,
        specimens: Iterable[Mapping[str, Any]],
        exposures: Iterable[Mapping[str, Any]],
        *,
        context_key: str | None = None,
    ) -> TreatmentExposureReport:
        specimen_values = tuple(specimens)
        exposure_values = tuple(exposures)
        input_hash = content_hash({"specimens": specimen_values, "exposures": exposure_values})
        issues: list[LineageAlphaIssue] = []
        parsed_specimens: list[LongitudinalSpecimenObservation] = []
        parsed_exposures: list[TreatmentExposure] = []
        context_mismatch = False
        for row_number, row in enumerate(specimen_values, start=1):
            if not isinstance(row, Mapping):
                issues.append(
                    LineageAlphaIssue(
                        "specimen_not_object",
                        "treatment context specimen must be an object",
                        content_hash({"row": row}),
                        row_number,
                        severity="error",
                    )
                )
                continue
            raw_hash = _raw_hash(row)
            row_context = _context(row)
            if context_key and row_context and row_context != context_key:
                context_mismatch = True
                issues.append(
                    LineageAlphaIssue(
                        "specimen_context_mismatch",
                        "specimen is outside the requested treatment context",
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                    )
                )
                continue
            try:
                parsed_specimens.append(LongitudinalSpecimenLinker._parse(row, raw_hash))
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    LineageAlphaIssue(
                        "invalid_treatment_specimen",
                        str(exc),
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                        raw_record=dict(row),
                    )
                )
        for row_number, row in enumerate(exposure_values, start=1):
            if not isinstance(row, Mapping):
                issues.append(
                    LineageAlphaIssue(
                        "exposure_not_object",
                        "treatment exposure must be an object",
                        content_hash({"row": row}),
                        row_number,
                        severity="error",
                    )
                )
                continue
            raw_hash = _raw_hash(row)
            row_context = _context(row)
            if context_key and row_context and row_context != context_key:
                context_mismatch = True
                issues.append(
                    LineageAlphaIssue(
                        "exposure_context_mismatch",
                        "treatment exposure is outside the requested context",
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                    )
                )
                continue
            try:
                parsed_exposures.append(self._parse_exposure(row, raw_hash))
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    LineageAlphaIssue(
                        "invalid_treatment_exposure",
                        str(exc),
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                        raw_record=dict(row),
                    )
                )
        exposure_by_subject: dict[str, list[TreatmentExposure]] = defaultdict(list)
        for exposure in parsed_exposures:
            exposure_by_subject[exposure.subject_id].append(exposure)
        contexts: list[ExposureContext] = []
        uncontextualized: set[str] = set()
        seen_specimens: set[str] = set()
        for specimen in parsed_specimens:
            if specimen.specimen_id in seen_specimens:
                issues.append(
                    LineageAlphaIssue(
                        "duplicate_specimen_id",
                        f"specimen ID is repeated: {specimen.specimen_id}",
                        specimen.raw_hash,
                        source_id=specimen.source_id,
                        severity="error",
                    )
                )
                continue
            seen_specimens.add(specimen.specimen_id)
            specimen_key = _parse_time(specimen.collection_time)
            if specimen_key is None:
                uncontextualized.add(specimen.specimen_id)
                issues.append(
                    LineageAlphaIssue(
                        "missing_specimen_time",
                        "specimen cannot be placed against exposure intervals without "
                        "a collection time",
                        specimen.raw_hash,
                        source_id=specimen.source_id,
                        severity="warning",
                    )
                )
                continue
            candidates = []
            for exposure in exposure_by_subject.get(specimen.subject_id, ()):
                if _exposure_relation(specimen_key, exposure) is not None:
                    candidates.append(exposure)
            if not candidates:
                uncontextualized.add(specimen.specimen_id)
                continue
            for exposure in sorted(candidates, key=lambda item: item.exposure_id):
                relation = _exposure_relation(specimen_key, exposure)
                if relation is None:
                    continue
                overlapping = tuple(
                    sorted(
                        other.exposure_id
                        for other in candidates
                        if other.exposure_id != exposure.exposure_id
                        and _exposure_relation(specimen_key, other) == "on_treatment"
                    )
                )
                state = LineageAlphaState.AMBIGUOUS if overlapping else LineageAlphaState.SUPPORTED
                body = {
                    "specimen_id": specimen.specimen_id,
                    "exposure_id": exposure.exposure_id,
                    "relation": relation,
                    "specimen_time": specimen.collection_time,
                }
                contexts.append(
                    ExposureContext(
                        specimen_id=specimen.specimen_id,
                        subject_id=specimen.subject_id,
                        exposure_id=exposure.exposure_id,
                        therapy_id=exposure.therapy_id,
                        relation=relation,
                        temporal_basis=(
                            "specimen collection time compared with declared exposure interval"
                        ),
                        specimen_time=specimen.collection_time,
                        exposure_start=exposure.start_time,
                        exposure_end=exposure.end_time,
                        gap_label=_gap_label(exposure.start_time, specimen.collection_time),
                        overlapping_exposure_ids=overlapping,
                        source_ids=tuple(sorted({specimen.source_id, exposure.source_id})),
                        state=state,
                        content_address=content_hash(body | {"state": state}),
                    )
                )
        if context_mismatch and not parsed_specimens and not parsed_exposures:
            state = LineageAlphaState.OUT_OF_DOMAIN
        elif not parsed_specimens:
            state = LineageAlphaState.ABSTAINED
        elif any(item.state == LineageAlphaState.AMBIGUOUS for item in contexts):
            state = LineageAlphaState.AMBIGUOUS
        elif uncontextualized or issues:
            state = LineageAlphaState.PARTIAL
        elif context_mismatch:
            state = LineageAlphaState.PARTIAL
        else:
            state = LineageAlphaState.SUPPORTED
        warnings = (
            "Exposure context is temporal bookkeeping and does not establish response, "
            "resistance, or causality.",
            "Only same-subject exposure intervals are joined to specimens.",
        )
        return TreatmentExposureReport(
            input_hash=input_hash,
            context_key=context_key,
            state=state,
            specimens=tuple(parsed_specimens),
            exposures=tuple(parsed_exposures),
            contexts=tuple(sorted(contexts, key=lambda item: (item.specimen_id, item.exposure_id))),
            uncontextualized_specimen_ids=tuple(sorted(uncontextualized)),
            issues=tuple(issues),
            warnings=warnings,
            content_address=content_hash(
                {"input_hash": input_hash, "state": state, "contexts": contexts, "issues": issues}
            ),
        )

    @staticmethod
    def _parse_exposure(row: Mapping[str, Any], raw_hash: str) -> TreatmentExposure:
        start_time = str(_value(row, "start_time", "start", "treatment_start"))
        start_key = _parse_time(start_time)
        if start_key is None:
            raise ValidationError("treatment exposure start time must be parseable")
        end_time = _optional_text(_value(row, "end_time", "end", "treatment_end", default=None))
        end_key = _parse_time(end_time)
        if end_time is not None and end_key is None:
            raise ValidationError("treatment exposure end time must be parseable")
        return TreatmentExposure(
            exposure_id=str(_value(row, "exposure_id", "id")),
            subject_id=str(_value(row, "subject_id", "subject", "case_id")),
            therapy_id=str(_value(row, "therapy_id", "treatment_id", "drug_id")),
            therapy_class=str(
                _value(row, "therapy_class", "class", "treatment_class", default="unspecified")
            ),
            start_time=start_time,
            end_time=end_time,
            start_sort_key=start_key,
            end_sort_key=end_key,
            status=str(_value(row, "status", default="declared")),
            source_id=_source_id(row),
            source_version=_source_version(row),
            context_key=_context(row),
            raw_hash=raw_hash,
        )


def _parse_time(value: str | None) -> tuple[int, str] | None:
    if value is None or not str(value).strip():
        return None
    text = str(value).strip()
    try:
        numeric = float(text)
    except ValueError:
        numeric = None
    if numeric is not None:
        return (int(numeric * 1_000_000), text)
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        try:
            parsed_date = date.fromisoformat(text)
        except ValueError:
            return None
        parsed = datetime(parsed_date.year, parsed_date.month, parsed_date.day)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return (int(parsed.timestamp() * 1_000_000), text)


def _time_sort_key(collection_time: str | None, timepoint: str) -> tuple[int, str]:
    parsed = _parse_time(collection_time)
    if parsed is not None:
        return parsed
    return (9_223_372_036_854_775_807, str(timepoint))


def _exposure_relation(specimen_key: tuple[int, str], exposure: TreatmentExposure) -> str | None:
    if specimen_key < exposure.start_sort_key:
        return "pre_treatment"
    if exposure.end_sort_key is None or specimen_key <= exposure.end_sort_key:
        return "on_treatment"
    return "post_treatment"


def _gap_label(first: str | None, second: str | None) -> str:
    first_key = _parse_time(first)
    second_key = _parse_time(second)
    if first_key is None or second_key is None:
        return "unknown_gap"
    delta_days = abs(second_key[0] - first_key[0]) / 86_400_000_000
    if delta_days < 1:
        return "same_day"
    return f"{round(delta_days, 3)}_days"


def _cycle_nodes(
    region_ids: tuple[str, ...], edges: tuple[RegionLineageEdge, ...]
) -> tuple[str, ...]:
    parents: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        if edge.parent_region_id in region_ids:
            parents[edge.child_region_id].add(edge.parent_region_id)
    visiting: set[str] = set()
    visited: set[str] = set()
    cycle: set[str] = set()

    def visit(region_id: str, stack: tuple[str, ...]) -> None:
        if region_id in visiting:
            cycle.update(stack[stack.index(region_id) :])
            return
        if region_id in visited:
            return
        visiting.add(region_id)
        for parent_id in sorted(parents.get(region_id, ())):
            visit(parent_id, stack + (region_id,))
        visiting.remove(region_id)
        visited.add(region_id)

    for region_id in sorted(region_ids):
        visit(region_id, ())
    return tuple(sorted(cycle))


_MISSING = object()


def _value(row: Mapping[str, Any], *keys: str, default: Any = _MISSING) -> Any:
    for key in keys:
        if key not in row:
            continue
        value = row[key]
        if value is not None and value != "":
            return value
    if default is not _MISSING:
        return default
    raise ValidationError(f"missing required field; expected one of {keys}")


def _text_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        values = value.replace(";", "|").replace(",", "|").split("|")
    elif isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, Mapping)):
        values = [str(item) for item in value]
    else:
        values = [str(value)]
    return tuple(item.strip() for item in values if item.strip())


def _optional_int(value: Any) -> int | None:
    if value is None or (isinstance(value, str) and value in {"", "."}):
        return None
    parsed = int(value)
    if parsed < 0:
        raise ValidationError("integer value cannot be negative")
    return parsed


def _optional_text(value: Any) -> str | None:
    if value is None or (isinstance(value, str) and value in {"", "."}):
        return None
    return str(value)


def _phase_labels(value: str | None) -> set[SpecimenPhase]:
    if value is None:
        return set()
    labels = {part.strip().lower().replace("-", "_") for part in _text_tuple(value)}
    mapped: set[SpecimenPhase] = set()
    for label in labels:
        if label in PrimaryRecurrencePhaseMapper._PRIMARY_LABELS:
            mapped.add(SpecimenPhase.PRIMARY)
        elif label in PrimaryRecurrencePhaseMapper._RECURRENCE_LABELS:
            mapped.add(SpecimenPhase.RECURRENCE)
        elif label in PrimaryRecurrencePhaseMapper._INTERVAL_LABELS:
            mapped.add(SpecimenPhase.INTERVAL)
    return mapped


def _phase_label(value: str | None) -> SpecimenPhase | None:
    labels = _phase_labels(value)
    return next(iter(labels)) if len(labels) == 1 else None


def _raw_hash(row: Mapping[str, Any]) -> str:
    return content_hash(dict(row))


def _source_id(row: Mapping[str, Any]) -> str:
    return str(row.get("source_id", row.get("source", "unspecified"))) or "unspecified"


def _source_version(row: Mapping[str, Any]) -> str:
    return str(row.get("source_version", row.get("version", "unspecified"))) or "unspecified"


def _context(row: Mapping[str, Any]) -> str | None:
    value = row.get("context_key", row.get("context"))
    return str(value) if value not in {None, "", "."} else None


__all__ = [
    "ExposureContext",
    "LineageAlphaIssue",
    "LineageAlphaState",
    "RegionLineageEdge",
    "LongitudinalLinkReport",
    "LongitudinalSpecimenLink",
    "LongitudinalSpecimenObservation",
    "LongitudinalSpecimenLinker",
    "MultiRegionLineageReport",
    "MultiRegionLineageResolver",
    "PhaseAssignment",
    "PrimaryRecurrenceMappingReport",
    "PrimaryRecurrencePhaseMapper",
    "RegionLineage",
    "RegionObservation",
    "SpecimenPhase",
    "TreatmentExposure",
    "TreatmentExposureContextualizer",
    "TreatmentExposureReport",
]
