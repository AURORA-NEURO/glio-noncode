"""Deterministic reconstruction of symbolic, breakend, and phased events.

This module consumes the deferred records emitted by :mod:`glio_noncode.intake`.
It never turns an unsupported structural record into a point mutation.  A
paired breakend requires reciprocal mate metadata; a symbolic event requires
an explicit END coordinate; and a phased group remains a set of segments
rather than being flattened into a single allele.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .identity import normalize_chromosome
from .intake import IntakeBatch, RawVariantRecord
from .models import ReferenceContext
from .serialization import content_hash, jsonable
from .variation import (
    Breakend,
    HaplotypeSegment,
    StructuralEvent,
    StructuralEventKind,
)


class StructuralIssueSeverity(StrEnum):
    """Severity of a structural reconstruction issue."""

    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class StructuralIssue:
    """Addressable reconstruction issue with no hidden fallback."""

    code: str
    severity: StructuralIssueSeverity
    message: str
    record_ids: tuple[str, ...] = ()
    remediation: str = "Inspect the structural record and route it for review."

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ParsedBreakend:
    """The local and remote sides encoded by a VCF breakend ALT."""

    remote_chromosome: str
    remote_position: int
    local_orientation: str
    remote_orientation: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReconstructionResult:
    """Reconstructed events and issues retained as a content-addressed result."""

    source_id: str
    events: tuple[StructuralEvent, ...]
    issues: tuple[StructuralIssue, ...]
    deferred_count: int
    content_address: str

    @property
    def has_errors(self) -> bool:
        return any(issue.severity == StructuralIssueSeverity.ERROR for issue in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class BreakendNotation:
    """Parse the four VCF breakend bracket forms."""

    _patterns = (
        (re.compile(r"\]([^:\[\]]+):(\d+)\]"), "]"),
        (re.compile(r"\[([^:\[\]]+):(\d+)\["), "["),
    )

    def parse(self, alternate: str) -> ParsedBreakend:
        text = alternate.strip()
        if not text:
            raise ValidationError("breakend ALT must not be empty")
        for pattern, bracket in self._patterns:
            match = pattern.search(text)
            if match:
                remote_chromosome = normalize_chromosome(match.group(1))
                remote_position = int(match.group(2))
                local_orientation = "forward" if text[0] not in "[]" else "reverse"
                remote_orientation = "reverse" if bracket == "]" else "forward"
                return ParsedBreakend(
                    remote_chromosome,
                    remote_position,
                    local_orientation,
                    remote_orientation,
                )
        raise ValidationError(f"unsupported VCF breakend ALT: {alternate!r}")


class StructuralReconstructor:
    """Reconstruct explicit structural event objects from deferred records."""

    def __init__(self, *, notation: BreakendNotation | None = None) -> None:
        self.notation = notation or BreakendNotation()

    def reconstruct_batch(
        self,
        batch: IntakeBatch,
        *,
        context: ReferenceContext,
        source_id: str | None = None,
    ) -> ReconstructionResult:
        return self.reconstruct(
            batch.deferred_records,
            context=context,
            source_id=source_id or batch.source_id,
        )

    def reconstruct(
        self,
        records: Iterable[RawVariantRecord],
        *,
        context: ReferenceContext,
        source_id: str,
    ) -> ReconstructionResult:
        values = tuple(records)
        if not source_id.strip():
            raise ValidationError("source_id must not be empty")
        events: list[StructuralEvent] = []
        issues: list[StructuralIssue] = []
        records_by_id = {record.record_id: record for record in values}
        if len(records_by_id) != len(values):
            issues.append(
                StructuralIssue(
                    "duplicate_structural_record_id",
                    StructuralIssueSeverity.ERROR,
                    "structural records must have unique IDs before pairing",
                )
            )
        handled: set[str] = set()
        for record in values:
            alternate = record.alternate.strip()
            if record.record_id in handled:
                continue
            if alternate.startswith("<"):
                event, issue = self._symbolic_event(record, context, source_id)
                if event is not None:
                    events.append(event)
                    handled.add(record.record_id)
                if issue is not None:
                    issues.append(issue)
                continue
            if "[" not in alternate and "]" not in alternate:
                issues.append(
                    StructuralIssue(
                        "not_structural",
                        StructuralIssueSeverity.WARNING,
                        "deferred record is not symbolic or breakend syntax",
                        (record.record_id,),
                        "Return the record to canonical point-variant intake.",
                    )
                )
                handled.add(record.record_id)
                continue
            event, issue, paired_ids = self._breakend_event(
                record,
                records_by_id,
                context,
                source_id,
            )
            if event is not None:
                events.append(event)
                handled.update(paired_ids)
            if issue is not None:
                issues.append(issue)
                handled.add(record.record_id)
        haplotype_events, haplotype_issues = self._haplotype_events(values, context, source_id)
        events.extend(haplotype_events)
        issues.extend(haplotype_issues)
        payload = {
            "source_id": source_id,
            "deferred_count": len(values),
            "events": events,
            "issues": issues,
        }
        return ReconstructionResult(
            source_id=source_id,
            events=tuple(sorted(events, key=lambda item: item.event_id)),
            issues=tuple(issues),
            deferred_count=len(values),
            content_address=content_hash(payload),
        )

    def _breakend_event(
        self,
        record: RawVariantRecord,
        records_by_id: Mapping[str, RawVariantRecord],
        context: ReferenceContext,
        source_id: str,
    ) -> tuple[StructuralEvent | None, StructuralIssue | None, tuple[str, ...]]:
        mate_id = self._mate_id(record.info)
        if not mate_id:
            return (
                None,
                StructuralIssue(
                    "missing_mate_id",
                    StructuralIssueSeverity.ERROR,
                    "breakend has no MATEID and cannot be paired safely",
                    (record.record_id,),
                    (
                        "Add reciprocal MATEID metadata or route the breakend for "
                        "manual reconstruction."
                    ),
                ),
                (),
            )
        mate = records_by_id.get(mate_id)
        if mate is None:
            return (
                None,
                StructuralIssue(
                    "missing_mate_record",
                    StructuralIssueSeverity.ERROR,
                    f"breakend mate record is absent: {mate_id}",
                    (record.record_id, mate_id),
                    "Provide both records from the same source snapshot.",
                ),
                (),
            )
        mate_mate_id = self._mate_id(mate.info)
        if mate_mate_id != record.record_id:
            return (
                None,
                StructuralIssue(
                    "non_reciprocal_mate",
                    StructuralIssueSeverity.ERROR,
                    "MATEID metadata is not reciprocal",
                    (record.record_id, mate.record_id),
                    "Do not form an event until both breakends reference each other.",
                ),
                (),
            )
        try:
            local = self.notation.parse(record.alternate)
            remote = self.notation.parse(mate.alternate)
        except ValidationError as exc:
            return (
                None,
                StructuralIssue(
                    "invalid_breakend_alt",
                    StructuralIssueSeverity.ERROR,
                    str(exc),
                    (record.record_id, mate.record_id),
                    "Correct the VCF breakend grammar before reconstruction.",
                ),
                (),
            )
        breakends = (
            Breakend(
                breakend_id=record.record_id,
                chromosome=normalize_chromosome(record.chromosome),
                position=record.position,
                orientation=local.local_orientation,
                mate_id=mate.record_id,
                allele=record.alternate,
            ),
            Breakend(
                breakend_id=mate.record_id,
                chromosome=normalize_chromosome(mate.chromosome),
                position=mate.position,
                orientation=remote.local_orientation,
                mate_id=record.record_id,
                allele=mate.alternate,
            ),
        )
        event_id = (
            "sv:"
            + content_hash(
                {"records": (record.record_id, mate.record_id), "source_id": source_id}
            ).split(":", 1)[1][:24]
        )
        event = StructuralEvent(
            event_id=event_id,
            kind=StructuralEventKind.BREAKEND_PAIR,
            breakends=breakends,
            haplotype_segments=(),
            context=context,
            source_id=source_id,
            reconstruction_support=1.0,
            uncertainty=0.0,
            annotations={
                "record_ids": [record.record_id, mate.record_id],
                "remote_locus_from_first_alt": {
                    "chromosome": local.remote_chromosome,
                    "position": local.remote_position,
                    "orientation": local.remote_orientation,
                },
                "remote_locus_from_second_alt": {
                    "chromosome": remote.remote_chromosome,
                    "position": remote.remote_position,
                    "orientation": remote.remote_orientation,
                },
            },
        )
        return event, None, (record.record_id, mate.record_id)

    def _symbolic_event(
        self,
        record: RawVariantRecord,
        context: ReferenceContext,
        source_id: str,
    ) -> tuple[StructuralEvent | None, StructuralIssue | None]:
        symbolic = record.alternate.strip().upper()
        end_value = record.info.get("END")
        if isinstance(end_value, (list, tuple)):
            end_value = end_value[0] if end_value else None
        try:
            end = int(str(end_value))
        except (TypeError, ValueError):
            return None, StructuralIssue(
                "missing_symbolic_end",
                StructuralIssueSeverity.ERROR,
                "symbolic structural event requires an integer END field",
                (record.record_id,),
                "Add END in INFO or route the event for manual reconstruction.",
            )
        if end < record.position:
            return None, StructuralIssue(
                "invalid_symbolic_interval",
                StructuralIssueSeverity.ERROR,
                "symbolic event END must be at or after POS",
                (record.record_id,),
            )
        kind = {
            "<DEL>": StructuralEventKind.DELETION,
            "<DUP>": StructuralEventKind.DUPLICATION,
            "<INV>": StructuralEventKind.INVERSION,
            "<CNV>": StructuralEventKind.COPY_NUMBER,
        }.get(symbolic)
        if kind is None:
            return None, StructuralIssue(
                "unsupported_symbolic_type",
                StructuralIssueSeverity.WARNING,
                f"symbolic type is not supported: {symbolic}",
                (record.record_id,),
                "Add a typed reconstruction handler for this SVTYPE.",
            )
        left_id = f"{record.record_id}:left"
        right_id = f"{record.record_id}:right"
        copy_number = self._float_info(record.info.get("CN"))
        breakends = (
            Breakend(
                left_id,
                normalize_chromosome(record.chromosome),
                record.position,
                "forward",
                right_id,
                record.alternate,
                copy_number,
            ),
            Breakend(
                right_id,
                normalize_chromosome(record.chromosome),
                end,
                "reverse",
                left_id,
                record.alternate,
                copy_number,
            ),
        )
        event_id = (
            "sv:"
            + content_hash({"record": record.record_id, "source_id": source_id}).split(":", 1)[1][
                :24
            ]
        )
        return StructuralEvent(
            event_id=event_id,
            kind=kind,
            breakends=breakends,
            haplotype_segments=(),
            context=context,
            source_id=source_id,
            reconstruction_support=1.0,
            uncertainty=0.0,
            annotations={"svtype": symbolic[1:-1], "info": dict(record.info)},
        ), None

    def _haplotype_events(
        self,
        records: Iterable[RawVariantRecord],
        context: ReferenceContext,
        source_id: str,
    ) -> tuple[tuple[StructuralEvent, ...], tuple[StructuralIssue, ...]]:
        groups: dict[tuple[str, str], list[RawVariantRecord]] = defaultdict(list)
        for record in records:
            phase_set = record.sample.get("PS") or record.info.get("PS")
            sample_id = str(record.sample.get("sample_id", "unspecified"))
            if phase_set not in {None, "", "."}:
                groups[(sample_id, str(phase_set))].append(record)
        events: list[StructuralEvent] = []
        issues: list[StructuralIssue] = []
        for (sample_id, phase_set), group in sorted(groups.items()):
            if len(group) < 2:
                issues.append(
                    StructuralIssue(
                        "singleton_phase_set",
                        StructuralIssueSeverity.WARNING,
                        "phase set contains only one record; no haplotype path was formed",
                        tuple(record.record_id for record in group),
                    )
                )
                continue
            segments = tuple(
                HaplotypeSegment(
                    segment_id=f"{sample_id}:{phase_set}:{index}",
                    chromosome=normalize_chromosome(record.chromosome),
                    start=record.position,
                    end=record.position + max(len(record.reference), 1) - 1,
                    phase_set=phase_set,
                    allele=record.alternate,
                    source_variant_ids=(record.record_id,),
                )
                for index, record in enumerate(
                    sorted(group, key=lambda item: (item.chromosome, item.position, item.record_id))
                )
            )
            event_id = (
                "hap:"
                + content_hash(
                    {"sample_id": sample_id, "phase_set": phase_set, "records": segments}
                ).split(":", 1)[1][:24]
            )
            events.append(
                StructuralEvent(
                    event_id=event_id,
                    kind=StructuralEventKind.HAPLOTYPE,
                    breakends=(),
                    haplotype_segments=segments,
                    context=context,
                    source_id=source_id,
                    reconstruction_support=1.0,
                    uncertainty=0.0,
                    annotations={"sample_id": sample_id, "phase_set": phase_set},
                )
            )
        return tuple(events), tuple(issues)

    @staticmethod
    def _mate_id(info: Mapping[str, Any]) -> str | None:
        value = info.get("MATEID")
        if isinstance(value, (list, tuple)):
            value = value[0] if value else None
        if value in {None, "", "."}:
            return None
        return str(value)

    @staticmethod
    def _float_info(value: object) -> float | None:
        if isinstance(value, (list, tuple)):
            value = value[0] if value else None
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None
