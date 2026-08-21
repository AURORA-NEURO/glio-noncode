"""Deep structural-variation contracts for phased, graph, and repeat evidence.

This module extends the Domain 02 structural boundary with four independent
operations:

* phased haplotype assembly from explicit genotype and phase-set records;
* allele-aware structural-variant representation with dosage and zygosity;
* projection of interval evidence onto supplied pangenome graph paths; and
* repeat/mobile-element annotation through an indexed interval catalogue.

The operations are intentionally deterministic and source-accounted. They do
not assemble sequence from reads, infer biological phasing where the input is
unphased, claim graph-path equivalence from coordinate proximity, or replace a
repeat annotation source with a de novo classification. Missing, conflicting,
and out-of-context records remain visible in the returned reports.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .identity import normalize_allele, normalize_chromosome
from .serialization import content_hash, jsonable, require_non_empty


class StructuralAlphaState(StrEnum):
    """Evidence state shared by the structural alpha operations."""

    SUPPORTED = "supported"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    ABSTAINED = "abstained"
    INVALID = "invalid"
    OUT_OF_DOMAIN = "out_of_domain"
    CONTRADICTORY = "contradictory"


@dataclass(frozen=True, slots=True)
class StructuralAlphaIssue:
    """An addressable structural issue retained beside successful results."""

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
class PhasedVariantObservation:
    """One variant observation before it is assigned to a haplotype path."""

    observation_id: str
    sample_id: str
    chromosome: str
    start: int
    end: int
    reference: str
    alternate: str
    alternate_alleles: tuple[str, ...]
    genotype: tuple[int | None, ...]
    phase_set: str
    is_phased: bool
    source_id: str
    source_version: str
    context_key: str | None
    raw_hash: str

    def __post_init__(self) -> None:
        require_non_empty(self.observation_id, "observation_id")
        require_non_empty(self.sample_id, "sample_id")
        require_non_empty(self.chromosome, "chromosome")
        require_non_empty(self.phase_set, "phase_set")
        if self.start < 1 or self.end < self.start:
            raise ValidationError("phased observation interval is invalid")
        if not self.genotype:
            raise ValidationError("phased observation genotype must not be empty")
        require_non_empty(self.raw_hash, "raw_hash")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class HaplotypeAlleleCall:
    """A lossless allele call attached to one assembled haplotype."""

    observation_id: str
    haplotype_index: int
    allele_index: int | None
    allele: str | None
    start: int
    end: int
    phase_set: str
    call_state: str
    source_id: str
    raw_hash: str

    def __post_init__(self) -> None:
        if self.haplotype_index < 1:
            raise ValidationError("haplotype_index must be positive")
        if self.start < 1 or self.end < self.start:
            raise ValidationError("haplotype call interval is invalid")
        if self.call_state not in {"reference", "alternate", "missing", "unphased"}:
            raise ValidationError("unsupported haplotype call state")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class HaplotypePath:
    """One ordered phase path; calls remain tied to their source observations."""

    haplotype_id: str
    sample_id: str
    phase_set: str
    haplotype_index: int
    chromosome: str
    start: int
    end: int
    calls: tuple[HaplotypeAlleleCall, ...]
    phase_complete: bool
    state: StructuralAlphaState
    source_ids: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        if self.haplotype_index < 1:
            raise ValidationError("haplotype path index must be positive")
        if self.start < 1 or self.end < self.start:
            raise ValidationError("haplotype path interval is invalid")
        if not self.calls:
            raise ValidationError("haplotype path must retain at least one call")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class HaplotypeAssemblyReport:
    """Phased paths and unresolved observations from one assembly request."""

    input_hash: str
    context_key: str | None
    state: StructuralAlphaState
    haplotypes: tuple[HaplotypePath, ...]
    unphased_observations: tuple[PhasedVariantObservation, ...]
    issues: tuple[StructuralAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class PhasedHaplotypeAssembler:
    """Assemble explicit ``|`` genotype paths without guessing phase."""

    def assemble(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str | None = None,
        max_haplotypes: int = 8,
    ) -> HaplotypeAssemblyReport:
        values = tuple(records)
        input_hash = content_hash(values)
        issues: list[StructuralAlphaIssue] = []
        if max_haplotypes < 1:
            issue = StructuralAlphaIssue(
                "invalid_ploidy_bound",
                "max_haplotypes must be positive",
                input_hash,
                severity="error",
            )
            return self._report(
                input_hash, context_key, StructuralAlphaState.INVALID, (), (), (issue,)
            )
        observations: list[PhasedVariantObservation] = []
        seen_ids: set[str] = set()
        context_mismatch = False
        for row_number, row in enumerate(values, start=1):
            if not isinstance(row, Mapping):
                issues.append(
                    StructuralAlphaIssue(
                        "row_not_object",
                        "phased observation must be an object",
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
                    StructuralAlphaIssue(
                        "context_mismatch",
                        "phased observation is outside the requested reference context",
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                        raw_record=dict(row),
                    )
                )
                continue
            try:
                observation = self._parse_observation(row, raw_hash)
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    StructuralAlphaIssue(
                        "invalid_phased_observation",
                        str(exc),
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                        raw_record=dict(row),
                    )
                )
                continue
            if observation.observation_id in seen_ids:
                issues.append(
                    StructuralAlphaIssue(
                        "duplicate_observation_id",
                        f"phased observation ID is repeated: {observation.observation_id}",
                        raw_hash,
                        row_number,
                        source_id=observation.source_id,
                        severity="error",
                        raw_record=dict(row),
                    )
                )
                continue
            seen_ids.add(observation.observation_id)
            observations.append(observation)
        groups: dict[tuple[str, str, str, str | None], list[PhasedVariantObservation]] = (
            defaultdict(list)
        )
        unphased: list[PhasedVariantObservation] = []
        for observation in observations:
            if not observation.is_phased or observation.phase_set == "UNPHASED":
                unphased.append(observation)
                continue
            groups[
                (
                    observation.sample_id,
                    observation.phase_set,
                    observation.chromosome,
                    observation.context_key,
                )
            ].append(observation)
        paths: list[HaplotypePath] = []
        for group_key, group in sorted(groups.items()):
            ploidy = min(max_haplotypes, max(len(item.genotype) for item in group))
            if any(len(item.genotype) > max_haplotypes for item in group):
                issues.append(
                    StructuralAlphaIssue(
                        "ploidy_truncated",
                        "genotype ploidy exceeded the configured assembly bound",
                        content_hash([item.raw_hash for item in group]),
                        source_id=group[0],
                        severity="warning",
                    )
                )
            for haplotype_index in range(1, ploidy + 1):
                calls: list[HaplotypeAlleleCall] = []
                for observation in sorted(
                    group, key=lambda item: (item.start, item.end, item.observation_id)
                ):
                    allele_index = (
                        observation.genotype[haplotype_index - 1]
                        if haplotype_index <= len(observation.genotype)
                        else None
                    )
                    if allele_index is None:
                        state = "missing"
                        allele = None
                    elif allele_index == 0:
                        state = "reference"
                        allele = observation.reference
                    elif 0 < allele_index <= len(observation.alternate_alleles):
                        state = "alternate"
                        allele = observation.alternate_alleles[allele_index - 1]
                    else:
                        issues.append(
                            StructuralAlphaIssue(
                                "allele_index_out_of_range",
                                "genotype references an absent alternate allele",
                                observation.raw_hash,
                                source_id=observation.source_id,
                                severity="error",
                                raw_record=observation.to_dict(),
                            )
                        )
                        state = "missing"
                        allele = None
                    calls.append(
                        HaplotypeAlleleCall(
                            observation.observation_id,
                            haplotype_index,
                            allele_index,
                            allele,
                            observation.start,
                            observation.end,
                            observation.phase_set,
                            state,
                            observation.source_id,
                            observation.raw_hash,
                        )
                    )
                if calls:
                    body = {
                        "sample_id": group_key[0],
                        "phase_set": group_key[1],
                        "chromosome": group_key[2],
                        "haplotype_index": haplotype_index,
                        "calls": calls,
                    }
                    paths.append(
                        HaplotypePath(
                            haplotype_id="haplotype:" + content_hash(body).split(":", 1)[1][:24],
                            sample_id=group_key[0],
                            phase_set=group_key[1],
                            haplotype_index=haplotype_index,
                            chromosome=group_key[2],
                            start=min(item.start for item in group),
                            end=max(item.end for item in group),
                            calls=tuple(calls),
                            phase_complete=all(
                                item.genotype[haplotype_index - 1] is not None
                                and len(item.genotype) >= haplotype_index
                                for item in group
                            ),
                            state=StructuralAlphaState.SUPPORTED,
                            source_ids=tuple(sorted({item.source_id for item in group})),
                            content_address=content_hash(body),
                        )
                    )
        if context_mismatch and not observations:
            state = StructuralAlphaState.OUT_OF_DOMAIN
        elif not paths and unphased:
            state = StructuralAlphaState.AMBIGUOUS
        elif not paths:
            state = StructuralAlphaState.ABSTAINED
        elif unphased or any(issue.severity == "error" for issue in issues):
            state = StructuralAlphaState.PARTIAL
        elif context_mismatch:
            state = StructuralAlphaState.PARTIAL
        else:
            state = StructuralAlphaState.SUPPORTED
        warnings = (
            "Only explicitly phased genotype fields are assigned to paths; "
            "unphased calls remain separate.",
            "The assembler preserves allele calls but does not reconstruct "
            "sequence or read-backed phase.",
        )
        return self._report(
            input_hash,
            context_key,
            state,
            tuple(paths),
            tuple(sorted(unphased, key=lambda item: item.observation_id)),
            tuple(issues),
            warnings,
        )

    @staticmethod
    def _parse_observation(row: Mapping[str, Any], raw_hash: str) -> PhasedVariantObservation:
        observation_id = str(_value(row, "observation_id", "variant_id", "record_id", "id"))
        sample_id = str(_value(row, "sample_id", "sample", default="unspecified"))
        chromosome = normalize_chromosome(str(_value(row, "chromosome", "chrom", "contig")))
        start = _positive_int(_value(row, "start", "position", "pos"), "start")
        reference = normalize_allele(str(_value(row, "reference", "ref", default="N")))
        alternate_values = _text_tuple(_value(row, "alternates", "alternate", "alt"))
        alternate_alleles = tuple(
            item if item.startswith("<") or "[" in item or "]" in item else normalize_allele(item)
            for item in alternate_values
            if item not in {".", ""}
        )
        if not alternate_alleles:
            raise ValidationError("phased observation requires at least one alternate allele")
        end = _positive_int(_value(row, "end", default=start + max(len(reference), 1) - 1), "end")
        if end < start:
            raise ValidationError("phased observation end must be at or after start")
        genotype_value = _value(row, "genotype", "GT", "allele_indices", default=None)
        genotype, is_phased = _parse_genotype(genotype_value)
        phase_set = str(_value(row, "phase_set", "PS", default="UNPHASED")) or "UNPHASED"
        if not is_phased:
            phase_set = "UNPHASED" if phase_set in {".", "", "None"} else phase_set
        return PhasedVariantObservation(
            observation_id=observation_id,
            sample_id=sample_id,
            chromosome=chromosome,
            start=start,
            end=end,
            reference=reference,
            alternate=alternate_alleles[0]
            if len(alternate_alleles) == 1
            else ",".join(alternate_alleles),
            alternate_alleles=alternate_alleles,
            genotype=genotype,
            phase_set=phase_set,
            is_phased=is_phased,
            source_id=_source_id(row),
            source_version=_source_version(row),
            context_key=_context(row),
            raw_hash=raw_hash,
        )

    @staticmethod
    def _report(
        input_hash: str,
        context_key: str | None,
        state: StructuralAlphaState,
        haplotypes: tuple[HaplotypePath, ...],
        unphased: tuple[PhasedVariantObservation, ...],
        issues: tuple[StructuralAlphaIssue, ...],
        warnings: tuple[str, ...] = (),
    ) -> HaplotypeAssemblyReport:
        body = {
            "input_hash": input_hash,
            "context_key": context_key,
            "state": state,
            "haplotypes": haplotypes,
            "unphased": unphased,
            "issues": issues,
        }
        return HaplotypeAssemblyReport(
            input_hash=input_hash,
            context_key=context_key,
            state=state,
            haplotypes=haplotypes,
            unphased_observations=unphased,
            issues=issues,
            warnings=warnings,
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class AlleleAwareStructuralObservation:
    """Normalized structural observation with its declared allele dosage."""

    event_id: str
    sample_id: str
    phase_set: str
    chromosome: str
    start: int
    end: int
    kind: str
    alternate: str
    genotype: tuple[int | None, ...]
    is_phased: bool
    allele_index: int | None
    copy_number: float | None
    support: float | None
    source_id: str
    source_version: str
    context_key: str | None
    raw_hash: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AlleleAwareStructuralEvent:
    """One structural event projected onto a declared allele."""

    event_id: str
    sample_id: str
    phase_set: str
    allele_index: int | None
    chromosome: str
    start: int
    end: int
    kind: str
    alternate: str
    genotype: tuple[int | None, ...]
    dosage: int | None
    zygosity: str
    copy_number: float | None
    support: float | None
    allele_state: str
    source_ids: tuple[str, ...]
    raw_hashes: tuple[str, ...]
    state: StructuralAlphaState
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AlleleAwareRepresentationReport:
    """Allele-aware events and conflicts retained from one input set."""

    input_hash: str
    context_key: str | None
    state: StructuralAlphaState
    events: tuple[AlleleAwareStructuralEvent, ...]
    issues: tuple[StructuralAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class AlleleAwareSvRepresenter:
    """Represent structural observations without losing haplotype dosage."""

    def represent(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str | None = None,
    ) -> AlleleAwareRepresentationReport:
        values = tuple(records)
        input_hash = content_hash(values)
        issues: list[StructuralAlphaIssue] = []
        parsed: list[AlleleAwareStructuralObservation] = []
        context_mismatch = False
        for row_number, row in enumerate(values, start=1):
            if not isinstance(row, Mapping):
                issues.append(
                    StructuralAlphaIssue(
                        "row_not_object",
                        "structural observation must be an object",
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
                    StructuralAlphaIssue(
                        "context_mismatch",
                        "structural observation is outside the requested reference context",
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                        raw_record=dict(row),
                    )
                )
                continue
            try:
                parsed.append(self._parse(row, raw_hash))
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    StructuralAlphaIssue(
                        "invalid_structural_observation",
                        str(exc),
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                        raw_record=dict(row),
                    )
                )
        grouped: dict[tuple[str, str, int | None], list[AlleleAwareStructuralObservation]] = (
            defaultdict(list)
        )
        for observation in parsed:
            allele_indices = self._allele_indices(observation)
            if not allele_indices:
                allele_indices = (observation.allele_index,)
            for allele_index in allele_indices:
                grouped[(observation.event_id, observation.sample_id, allele_index)].append(
                    observation
                )
        events: list[AlleleAwareStructuralEvent] = []
        for group_key, group in sorted(
            grouped.items(), key=lambda item: (item[0][0], item[0][1], item[0][2] or 0)
        ):
            first = group[0]
            signatures = {
                (item.chromosome, item.start, item.end, item.kind, item.alternate) for item in group
            }
            state = StructuralAlphaState.SUPPORTED
            if len(signatures) > 1:
                state = StructuralAlphaState.CONTRADICTORY
                issues.append(
                    StructuralAlphaIssue(
                        "conflicting_allele_observation",
                        "same event and allele have incompatible structural coordinates or alleles",
                        content_hash([item.raw_hash for item in group]),
                        source_id=first.source_id,
                        severity="error",
                        raw_record={"event_id": first.event_id},
                    )
                )
            genotype = _merge_genotype(group)
            dosage = _dosage(genotype, group_key[2])
            zygosity = _zygosity(dosage, genotype)
            if group_key[2] is None:
                state = StructuralAlphaState.PARTIAL
            if any(item.genotype and not item.is_phased for item in group):
                if state == StructuralAlphaState.SUPPORTED:
                    state = StructuralAlphaState.PARTIAL
            body = {
                "event_id": first.event_id,
                "sample_id": first.sample_id,
                "phase_set": first.phase_set,
                "allele_index": group_key[2],
                "signature": sorted(signatures),
                "genotype": genotype,
            }
            events.append(
                AlleleAwareStructuralEvent(
                    event_id=first.event_id,
                    sample_id=first.sample_id,
                    phase_set=first.phase_set,
                    allele_index=group_key[2],
                    chromosome=first.chromosome,
                    start=min(item.start for item in group),
                    end=max(item.end for item in group),
                    kind=first.kind,
                    alternate=first.alternate,
                    genotype=genotype,
                    dosage=dosage,
                    zygosity=zygosity,
                    copy_number=_median_optional(item.copy_number for item in group),
                    support=_median_optional(item.support for item in group),
                    allele_state="alternate" if group_key[2] not in {None, 0} else "unspecified",
                    source_ids=tuple(sorted({item.source_id for item in group})),
                    raw_hashes=tuple(sorted({item.raw_hash for item in group})),
                    state=state,
                    content_address=content_hash(body | {"state": state}),
                )
            )
        if context_mismatch and not parsed:
            state = StructuralAlphaState.OUT_OF_DOMAIN
        elif any(event.state == StructuralAlphaState.CONTRADICTORY for event in events):
            state = StructuralAlphaState.CONTRADICTORY
        elif any(event.state == StructuralAlphaState.PARTIAL for event in events) or issues:
            state = StructuralAlphaState.PARTIAL
        elif not events:
            state = StructuralAlphaState.ABSTAINED
        elif context_mismatch:
            state = StructuralAlphaState.PARTIAL
        else:
            state = StructuralAlphaState.SUPPORTED
        warnings = (
            "Allele-aware representation retains declared genotype dosage; "
            "it does not infer copy-number phasing.",
            "Conflicting observations are reported beside a bounded representative "
            "and are not silently merged.",
        )
        return AlleleAwareRepresentationReport(
            input_hash=input_hash,
            context_key=context_key,
            state=state,
            events=tuple(events),
            issues=tuple(issues),
            warnings=warnings,
            content_address=content_hash(
                {"input_hash": input_hash, "events": events, "issues": issues, "state": state}
            ),
        )

    @staticmethod
    def _parse(row: Mapping[str, Any], raw_hash: str) -> AlleleAwareStructuralObservation:
        event_id = str(_value(row, "event_id", "variant_id", "record_id", "id"))
        sample_id = str(_value(row, "sample_id", "sample", default="unspecified"))
        chromosome = normalize_chromosome(str(_value(row, "chromosome", "chrom", "contig")))
        start = _positive_int(_value(row, "start", "position", "pos"), "start")
        end = _positive_int(_value(row, "end", default=start), "end")
        if end < start:
            raise ValidationError("structural observation end must be at or after start")
        kind = str(_value(row, "kind", "svtype", "type", default="structural_event"))
        alternate = str(_value(row, "alternate", "alt", "allele", default="<SV>"))
        genotype_value = _value(row, "genotype", "GT", default=None)
        if genotype_value is None:
            genotype, is_phased = (), False
        else:
            genotype, is_phased = _parse_genotype(genotype_value)
        allele_index_value = _value(row, "allele_index", "alt_index", default=None)
        allele_index = _optional_int(allele_index_value)
        return AlleleAwareStructuralObservation(
            event_id=event_id,
            sample_id=sample_id,
            phase_set=str(_value(row, "phase_set", "PS", default="UNPHASED")),
            chromosome=chromosome,
            start=start,
            end=end,
            kind=kind,
            alternate=alternate,
            genotype=genotype,
            is_phased=is_phased,
            allele_index=allele_index,
            copy_number=_optional_float(
                _value(row, "copy_number", "CN", "total_copy_number", default=None)
            ),
            support=_optional_float(_value(row, "support", "quality", "confidence", default=None)),
            source_id=_source_id(row),
            source_version=_source_version(row),
            context_key=_context(row),
            raw_hash=raw_hash,
        )

    @staticmethod
    def _allele_indices(
        observation: AlleleAwareStructuralObservation,
    ) -> tuple[int | None, ...]:
        if observation.allele_index is not None:
            return (observation.allele_index,)
        return tuple(
            sorted({item for item in observation.genotype if item is not None and item > 0})
        )


@dataclass(frozen=True, slots=True)
class PangenomeGraphNode:
    """One supplied graph node on one named reference path."""

    node_id: str
    path_id: str
    chromosome: str
    start: int
    end: int
    sequence: str
    orientation: str
    context_key: str | None
    source_id: str
    raw_hash: str

    def __post_init__(self) -> None:
        require_non_empty(self.node_id, "node_id")
        require_non_empty(self.path_id, "path_id")
        if self.start < 1 or self.end < self.start:
            raise ValidationError("graph node interval is invalid")
        if self.orientation not in {"forward", "reverse", "unknown"}:
            raise ValidationError("graph node orientation is invalid")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GraphProjectionMatch:
    """One query-to-node mapping with explicit interval relationship."""

    query_id: str
    node_id: str
    path_id: str
    relation: str
    overlap_bp: int
    overlap_fraction: float
    query_start: int
    query_end: int
    node_start: int
    node_end: int
    orientation: str
    context_key: str | None
    source_id: str
    raw_hash: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GraphProjectionReport:
    """Pangenome projection report with unmapped and ambiguous queries retained."""

    input_hash: str
    context_key: str | None
    state: StructuralAlphaState
    nodes: tuple[PangenomeGraphNode, ...]
    matches: tuple[GraphProjectionMatch, ...]
    unmapped_query_ids: tuple[str, ...]
    issues: tuple[StructuralAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class PangenomeGraphProjector:
    """Project interval observations onto an explicitly supplied graph index."""

    def project(
        self,
        queries: Iterable[Mapping[str, Any]],
        nodes: Iterable[Mapping[str, Any]],
        *,
        context_key: str | None = None,
        max_candidates_per_query: int = 32,
    ) -> GraphProjectionReport:
        query_values = tuple(queries)
        node_values = tuple(nodes)
        input_hash = content_hash({"queries": query_values, "nodes": node_values})
        issues: list[StructuralAlphaIssue] = []
        if max_candidates_per_query < 1:
            issue = StructuralAlphaIssue(
                "invalid_candidate_bound",
                "max_candidates_per_query must be positive",
                input_hash,
                severity="error",
            )
            return self._report(
                input_hash,
                context_key,
                StructuralAlphaState.INVALID,
                (),
                (),
                (),
                (issue,),
            )
        parsed_nodes: list[PangenomeGraphNode] = []
        context_mismatch = False
        for row_number, row in enumerate(node_values, start=1):
            if not isinstance(row, Mapping):
                issues.append(
                    StructuralAlphaIssue(
                        "node_not_object",
                        "pangenome graph node must be an object",
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
                    StructuralAlphaIssue(
                        "node_context_mismatch",
                        "graph node is outside the requested reference context",
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                    )
                )
                continue
            try:
                parsed_nodes.append(self._parse_node(row, raw_hash))
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    StructuralAlphaIssue(
                        "invalid_graph_node",
                        str(exc),
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                        raw_record=dict(row),
                    )
                )
        index = _GraphIntervalIndex(parsed_nodes)
        matches: list[GraphProjectionMatch] = []
        unmapped: list[str] = []
        parsed_queries = 0
        for row_number, row in enumerate(query_values, start=1):
            if not isinstance(row, Mapping):
                issues.append(
                    StructuralAlphaIssue(
                        "query_not_object",
                        "pangenome projection query must be an object",
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
                query_id = str(
                    _value(
                        row,
                        "query_id",
                        "variant_id",
                        "event_id",
                        "id",
                        default=f"query-{row_number}",
                    )
                )
                unmapped.append(query_id)
                issues.append(
                    StructuralAlphaIssue(
                        "query_context_mismatch",
                        "projection query is outside the requested reference context",
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                    )
                )
                continue
            try:
                query_id, chromosome, start, end = self._parse_query(row, row_number)
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    StructuralAlphaIssue(
                        "invalid_projection_query",
                        str(exc),
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                        raw_record=dict(row),
                    )
                )
                continue
            parsed_queries += 1
            path_hint = _optional_text(_value(row, "path_id", "graph_path", default=None))
            candidates = index.overlaps(chromosome, start, end, path_hint)
            if len(candidates) > max_candidates_per_query:
                issues.append(
                    StructuralAlphaIssue(
                        "projection_candidate_limit",
                        "projection candidates exceeded the configured bound",
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="warning",
                    )
                )
                candidates = candidates[:max_candidates_per_query]
            if not candidates:
                unmapped.append(query_id)
                continue
            for node in candidates:
                overlap = min(end, node.end) - max(start, node.start) + 1
                query_span = end - start + 1
                if start == node.start and end == node.end:
                    relation = "exact"
                elif start >= node.start and end <= node.end:
                    relation = "contained"
                elif start <= node.start and end >= node.end:
                    relation = "spanning"
                else:
                    relation = "overlapping"
                matches.append(
                    GraphProjectionMatch(
                        query_id=query_id,
                        node_id=node.node_id,
                        path_id=node.path_id,
                        relation=relation,
                        overlap_bp=overlap,
                        overlap_fraction=round(overlap / query_span, 6),
                        query_start=start,
                        query_end=end,
                        node_start=node.start,
                        node_end=node.end,
                        orientation=node.orientation,
                        context_key=node.context_key,
                        source_id=node.source_id,
                        raw_hash=node.raw_hash,
                    )
                )
        query_match_counts = defaultdict(int)
        for match in matches:
            query_match_counts[match.query_id] += 1
        ambiguous = any(count > 1 for count in query_match_counts.values())
        if context_mismatch and parsed_queries == 0:
            state = StructuralAlphaState.OUT_OF_DOMAIN
        elif not parsed_queries:
            state = StructuralAlphaState.ABSTAINED
        elif ambiguous:
            state = StructuralAlphaState.AMBIGUOUS
        elif unmapped or issues:
            state = StructuralAlphaState.PARTIAL
        else:
            state = StructuralAlphaState.SUPPORTED
        warnings = (
            "Projection uses supplied coordinate/path overlap only; "
            "it does not establish sequence homology.",
            "Multiple paths remain multiple mappings so callers can inspect graph ambiguity.",
        )
        return self._report(
            input_hash,
            context_key,
            state,
            tuple(
                sorted(parsed_nodes, key=lambda item: (item.chromosome, item.start, item.node_id))
            ),
            tuple(sorted(matches, key=lambda item: (item.query_id, item.path_id, item.node_id))),
            tuple(sorted(set(unmapped))),
            tuple(issues),
            warnings,
        )

    @staticmethod
    def _parse_node(row: Mapping[str, Any], raw_hash: str) -> PangenomeGraphNode:
        start = _positive_int(_value(row, "start", "position", "pos"), "node start")
        end = _positive_int(_value(row, "end", default=start), "node end")
        if end < start:
            raise ValidationError("graph node end must be at or after start")
        return PangenomeGraphNode(
            node_id=str(_value(row, "node_id", "id")),
            path_id=str(_value(row, "path_id", "graph_path", "path")),
            chromosome=normalize_chromosome(str(_value(row, "chromosome", "chrom", "contig"))),
            start=start,
            end=end,
            sequence=str(_value(row, "sequence", "seq", default="")),
            orientation=str(_value(row, "orientation", default="unknown")),
            context_key=_context(row),
            source_id=_source_id(row),
            raw_hash=raw_hash,
        )

    @staticmethod
    def _parse_query(row: Mapping[str, Any], row_number: int) -> tuple[str, str, int, int]:
        query_id = str(
            _value(
                row,
                "query_id",
                "variant_id",
                "event_id",
                "record_id",
                "id",
                default=f"query-{row_number}",
            )
        )
        start = _positive_int(_value(row, "start", "position", "pos"), "query start")
        default_end = start + max(len(str(_value(row, "reference", "ref", default="N"))), 1) - 1
        end = _positive_int(_value(row, "end", default=default_end), "query end")
        if end < start:
            raise ValidationError("projection query end must be at or after start")
        return (
            query_id,
            normalize_chromosome(str(_value(row, "chromosome", "chrom", "contig"))),
            start,
            end,
        )

    @staticmethod
    def _report(
        input_hash: str,
        context_key: str | None,
        state: StructuralAlphaState,
        nodes: tuple[PangenomeGraphNode, ...],
        matches: tuple[GraphProjectionMatch, ...],
        unmapped: tuple[str, ...],
        issues: tuple[StructuralAlphaIssue, ...],
        warnings: tuple[str, ...] = (),
    ) -> GraphProjectionReport:
        body = {
            "input_hash": input_hash,
            "context_key": context_key,
            "state": state,
            "nodes": nodes,
            "matches": matches,
            "unmapped": unmapped,
            "issues": issues,
        }
        return GraphProjectionReport(
            input_hash=input_hash,
            context_key=context_key,
            state=state,
            nodes=nodes,
            matches=matches,
            unmapped_query_ids=unmapped,
            issues=issues,
            warnings=warnings,
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class RepeatFeatureAnnotation:
    """One repeat or mobile-element interval from an annotation source."""

    annotation_id: str
    chromosome: str
    start: int
    end: int
    family: str
    class_name: str
    subfamily: str
    strand: str
    is_mobile: bool
    source_id: str
    source_version: str
    context_key: str | None
    raw_hash: str

    def __post_init__(self) -> None:
        require_non_empty(self.annotation_id, "annotation_id")
        require_non_empty(self.family, "family")
        require_non_empty(self.class_name, "class_name")
        if self.start < 1 or self.end < self.start:
            raise ValidationError("repeat annotation interval is invalid")
        if self.strand not in {"+", "-", ".", "unknown"}:
            raise ValidationError("repeat annotation strand is invalid")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class RepeatFeatureHit:
    """One overlap between an input interval and a repeat annotation."""

    query_id: str
    annotation_id: str
    relation: str
    overlap_bp: int
    overlap_fraction: float
    family: str
    class_name: str
    subfamily: str
    strand: str
    is_mobile: bool
    source_id: str
    source_version: str
    context_key: str | None
    raw_hash: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class RepeatMobileAnnotationReport:
    """Repeat and mobile-element hits with no-hit queries retained."""

    input_hash: str
    context_key: str | None
    state: StructuralAlphaState
    annotations: tuple[RepeatFeatureAnnotation, ...]
    hits: tuple[RepeatFeatureHit, ...]
    unannotated_query_ids: tuple[str, ...]
    issues: tuple[StructuralAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class RepeatMobileElementAnnotator:
    """Annotate structural intervals using an indexed repeat feature catalogue."""

    _MOBILE_CLASSES = frozenset(
        {
            "LINE",
            "SINE",
            "LTR",
            "DNA",
            "RC",
            "MOBILE",
            "MOBILE_ELEMENT",
            "TRANSPOSABLE_ELEMENT",
            "TRANSPOSON",
        }
    )

    def annotate(
        self,
        queries: Iterable[Mapping[str, Any]],
        annotations: Iterable[Mapping[str, Any]],
        *,
        context_key: str | None = None,
        min_overlap_fraction: float = 0.0,
        flank_bp: int = 0,
        include_non_mobile: bool = True,
    ) -> RepeatMobileAnnotationReport:
        query_values = tuple(queries)
        annotation_values = tuple(annotations)
        input_hash = content_hash({"queries": query_values, "annotations": annotation_values})
        issues: list[StructuralAlphaIssue] = []
        if not 0.0 <= min_overlap_fraction <= 1.0 or flank_bp < 0:
            issue = StructuralAlphaIssue(
                "invalid_annotation_parameter",
                "minimum overlap fraction must be between 0 and 1 and flank must be non-negative",
                input_hash,
                severity="error",
            )
            return self._report(
                input_hash,
                context_key,
                StructuralAlphaState.INVALID,
                (),
                (),
                (),
                (issue,),
            )
        parsed_annotations: list[RepeatFeatureAnnotation] = []
        context_mismatch = False
        for row_number, row in enumerate(annotation_values, start=1):
            if not isinstance(row, Mapping):
                issues.append(
                    StructuralAlphaIssue(
                        "annotation_not_object",
                        "repeat annotation must be an object",
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
                    StructuralAlphaIssue(
                        "annotation_context_mismatch",
                        "repeat annotation is outside the requested reference context",
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                    )
                )
                continue
            try:
                parsed_annotations.append(self._parse_annotation(row, raw_hash))
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    StructuralAlphaIssue(
                        "invalid_repeat_annotation",
                        str(exc),
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                        raw_record=dict(row),
                    )
                )
        index = _RepeatIntervalIndex(parsed_annotations)
        hits: list[RepeatFeatureHit] = []
        unannotated: list[str] = []
        parsed_queries = 0
        for row_number, row in enumerate(query_values, start=1):
            if not isinstance(row, Mapping):
                issues.append(
                    StructuralAlphaIssue(
                        "query_not_object",
                        "repeat annotation query must be an object",
                        content_hash({"row": row}),
                        row_number,
                        severity="error",
                    )
                )
                continue
            raw_hash = _raw_hash(row)
            row_context = _context(row)
            query_id = str(
                _value(
                    row,
                    "query_id",
                    "variant_id",
                    "event_id",
                    "record_id",
                    "id",
                    default=f"query-{row_number}",
                )
            )
            if context_key and row_context and row_context != context_key:
                context_mismatch = True
                unannotated.append(query_id)
                issues.append(
                    StructuralAlphaIssue(
                        "query_context_mismatch",
                        "repeat annotation query is outside the requested context",
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                    )
                )
                continue
            try:
                chromosome = normalize_chromosome(str(_value(row, "chromosome", "chrom", "contig")))
                start = _positive_int(_value(row, "start", "position", "pos"), "query start")
                default_end = (
                    start + max(len(str(_value(row, "reference", "ref", default="N"))), 1) - 1
                )
                end = _positive_int(_value(row, "end", default=default_end), "query end")
                if end < start:
                    raise ValidationError("repeat query end must be at or after start")
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    StructuralAlphaIssue(
                        "invalid_repeat_query",
                        str(exc),
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                        raw_record=dict(row),
                    )
                )
                continue
            parsed_queries += 1
            query_start = max(1, start - flank_bp)
            query_end = end + flank_bp
            query_span = query_end - query_start + 1
            query_hits = []
            for annotation in index.overlaps(chromosome, query_start, query_end):
                if not include_non_mobile and not annotation.is_mobile:
                    continue
                overlap = min(query_end, annotation.end) - max(query_start, annotation.start) + 1
                overlap_fraction = overlap / query_span
                if overlap_fraction < min_overlap_fraction:
                    continue
                if query_start == annotation.start and query_end == annotation.end:
                    relation = "exact"
                elif query_start >= annotation.start and query_end <= annotation.end:
                    relation = "contained"
                elif query_start <= annotation.start and query_end >= annotation.end:
                    relation = "spanning"
                else:
                    relation = "overlapping"
                query_hits.append(
                    RepeatFeatureHit(
                        query_id=query_id,
                        annotation_id=annotation.annotation_id,
                        relation=relation,
                        overlap_bp=overlap,
                        overlap_fraction=round(overlap_fraction, 6),
                        family=annotation.family,
                        class_name=annotation.class_name,
                        subfamily=annotation.subfamily,
                        strand=annotation.strand,
                        is_mobile=annotation.is_mobile,
                        source_id=annotation.source_id,
                        source_version=annotation.source_version,
                        context_key=annotation.context_key,
                        raw_hash=annotation.raw_hash,
                    )
                )
            if not query_hits:
                unannotated.append(query_id)
            hits.extend(query_hits)
        query_classes: dict[str, set[str]] = defaultdict(set)
        for hit in hits:
            query_classes[hit.query_id].add(hit.class_name)
        if context_mismatch and parsed_queries == 0:
            state = StructuralAlphaState.OUT_OF_DOMAIN
        elif not parsed_queries:
            state = StructuralAlphaState.ABSTAINED
        elif any(len(classes) > 1 for classes in query_classes.values()):
            state = StructuralAlphaState.AMBIGUOUS
        elif unannotated or issues:
            state = StructuralAlphaState.PARTIAL
        elif context_mismatch:
            state = StructuralAlphaState.PARTIAL
        else:
            state = StructuralAlphaState.SUPPORTED
        warnings = (
            "Repeat and mobile-element labels are inherited from supplied annotation "
            "sources; they are not sequence-derived.",
            "Overlap fractions are calculated against the requested interval "
            "including any configured flank.",
        )
        return self._report(
            input_hash,
            context_key,
            state,
            tuple(
                sorted(
                    parsed_annotations,
                    key=lambda item: (item.chromosome, item.start, item.annotation_id),
                )
            ),
            tuple(sorted(hits, key=lambda item: (item.query_id, item.annotation_id))),
            tuple(sorted(set(unannotated))),
            tuple(issues),
            warnings,
        )

    @classmethod
    def _parse_annotation(cls, row: Mapping[str, Any], raw_hash: str) -> RepeatFeatureAnnotation:
        class_name = str(
            _value(row, "class_name", "class", "repeat_class", "element_class", default="repeat")
        ).strip()
        class_key = class_name.upper().replace("-", "_").replace(" ", "_")
        explicit_mobile = _value(row, "is_mobile", "mobile", default=None)
        is_mobile = (
            _as_bool(explicit_mobile)
            if explicit_mobile is not None
            else class_key in cls._MOBILE_CLASSES
        )
        start = _positive_int(_value(row, "start", "position", "pos"), "annotation start")
        end = _positive_int(_value(row, "end", default=start), "annotation end")
        if end < start:
            raise ValidationError("repeat annotation end must be at or after start")
        strand = str(_value(row, "strand", default="unknown"))
        if strand not in {"+", "-", ".", "unknown"}:
            strand = "unknown"
        return RepeatFeatureAnnotation(
            annotation_id=str(_value(row, "annotation_id", "repeat_id", "id")),
            chromosome=normalize_chromosome(str(_value(row, "chromosome", "chrom", "contig"))),
            start=start,
            end=end,
            family=str(_value(row, "family", "repeat_family", default="unspecified")),
            class_name=class_name,
            subfamily=str(_value(row, "subfamily", "repeat_subfamily", default="unspecified")),
            strand=strand,
            is_mobile=is_mobile,
            source_id=_source_id(row),
            source_version=_source_version(row),
            context_key=_context(row),
            raw_hash=raw_hash,
        )

    @staticmethod
    def _report(
        input_hash: str,
        context_key: str | None,
        state: StructuralAlphaState,
        annotations: tuple[RepeatFeatureAnnotation, ...],
        hits: tuple[RepeatFeatureHit, ...],
        unannotated: tuple[str, ...],
        issues: tuple[StructuralAlphaIssue, ...],
        warnings: tuple[str, ...] = (),
    ) -> RepeatMobileAnnotationReport:
        body = {
            "input_hash": input_hash,
            "context_key": context_key,
            "state": state,
            "annotations": annotations,
            "hits": hits,
            "unannotated": unannotated,
            "issues": issues,
        }
        return RepeatMobileAnnotationReport(
            input_hash=input_hash,
            context_key=context_key,
            state=state,
            annotations=annotations,
            hits=hits,
            unannotated_query_ids=unannotated,
            issues=issues,
            warnings=warnings,
            content_address=content_hash(body),
        )


class _GraphIntervalIndex:
    """Chromosome/path interval index used to bound projection scans."""

    def __init__(self, nodes: Sequence[PangenomeGraphNode]) -> None:
        self._by_chromosome: dict[str, tuple[PangenomeGraphNode, ...]] = {}
        for chromosome in sorted({node.chromosome for node in nodes}):
            self._by_chromosome[chromosome] = tuple(
                sorted(
                    (node for node in nodes if node.chromosome == chromosome),
                    key=lambda item: (item.start, item.end, item.path_id, item.node_id),
                )
            )
        self._starts = {
            chromosome: tuple(node.start for node in values)
            for chromosome, values in self._by_chromosome.items()
        }
        self._prefix_max_ends = {
            chromosome: _prefix_max(item.end for item in values)
            for chromosome, values in self._by_chromosome.items()
        }

    def overlaps(
        self,
        chromosome: str,
        start: int,
        end: int,
        path_id: str | None = None,
    ) -> tuple[PangenomeGraphNode, ...]:
        values = self._by_chromosome.get(chromosome, ())
        starts = self._starts.get(chromosome, ())
        prefix_max_ends = self._prefix_max_ends.get(chromosome, ())
        right = bisect_right(starts, end)
        left = bisect_left(prefix_max_ends, start)
        matches = [
            node
            for node in values[left:right]
            if node.end >= start
            and node.start <= end
            and (path_id is None or node.path_id == path_id)
        ]
        return tuple(
            sorted(matches, key=lambda item: (item.path_id, item.start, item.end, item.node_id))
        )


class _RepeatIntervalIndex:
    """Chromosome interval index for repeat annotations."""

    def __init__(self, annotations: Sequence[RepeatFeatureAnnotation]) -> None:
        self._by_chromosome: dict[str, tuple[RepeatFeatureAnnotation, ...]] = {}
        for chromosome in sorted({item.chromosome for item in annotations}):
            self._by_chromosome[chromosome] = tuple(
                sorted(
                    (item for item in annotations if item.chromosome == chromosome),
                    key=lambda item: (item.start, item.end, item.annotation_id),
                )
            )
        self._starts = {
            chromosome: tuple(item.start for item in values)
            for chromosome, values in self._by_chromosome.items()
        }
        self._prefix_max_ends = {
            chromosome: _prefix_max(item.end for item in values)
            for chromosome, values in self._by_chromosome.items()
        }

    def overlaps(
        self, chromosome: str, start: int, end: int
    ) -> tuple[RepeatFeatureAnnotation, ...]:
        values = self._by_chromosome.get(chromosome, ())
        starts = self._starts.get(chromosome, ())
        prefix_max_ends = self._prefix_max_ends.get(chromosome, ())
        right = bisect_right(starts, end)
        left = bisect_left(prefix_max_ends, start)
        return tuple(
            sorted(
                (item for item in values[left:right] if item.end >= start and item.start <= end),
                key=lambda item: (item.start, item.end, item.annotation_id),
            )
        )


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


def _parse_genotype(value: Any) -> tuple[tuple[int | None, ...], bool]:
    if value is None or (isinstance(value, str) and value in {"", "."}):
        raise ValidationError("genotype is required for allele-aware phasing")
    if isinstance(value, (tuple, list)):
        tokens = [str(item) for item in value]
        phased = False
    else:
        text = str(value).strip()
        phased = "|" in text
        tokens = text.replace("|", "/").split("/")
    if not tokens or any(token == "" for token in tokens):
        raise ValidationError("genotype contains an empty allele")
    parsed: list[int | None] = []
    for token in tokens:
        if token in {".", ""}:
            parsed.append(None)
            continue
        try:
            allele_index = int(token)
        except ValueError as exc:
            raise ValidationError(f"invalid genotype allele index: {token}") from exc
        if allele_index < 0:
            raise ValidationError("genotype allele index cannot be negative")
        parsed.append(allele_index)
    return tuple(parsed), phased


def _merge_genotype(
    observations: Sequence[AlleleAwareStructuralObservation],
) -> tuple[int | None, ...]:
    for observation in observations:
        if observation.genotype:
            return observation.genotype
    return ()


def _dosage(genotype: tuple[int | None, ...], allele_index: int | None) -> int | None:
    if allele_index is None or not genotype:
        return None
    return sum(1 for value in genotype if value == allele_index)


def _zygosity(dosage: int | None, genotype: tuple[int | None, ...]) -> str:
    if dosage is None:
        return "unknown"
    called = len([value for value in genotype if value is not None])
    if called == 0:
        return "unknown"
    if dosage == called:
        return "homozygous_alt"
    if dosage > 0:
        return "heterozygous"
    return "reference"


def _raw_hash(row: Mapping[str, Any]) -> str:
    return content_hash(dict(row))


def _source_id(row: Mapping[str, Any]) -> str:
    return str(row.get("source_id", row.get("source", "unspecified"))) or "unspecified"


def _source_version(row: Mapping[str, Any]) -> str:
    return str(row.get("source_version", row.get("version", "unspecified"))) or "unspecified"


def _context(row: Mapping[str, Any]) -> str | None:
    value = row.get("context_key", row.get("context"))
    return str(value) if value not in {None, "", "."} else None


def _positive_int(value: Any, field: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} must be an integer") from exc
    if parsed < 1:
        raise ValidationError(f"{field} must be positive")
    return parsed


def _optional_int(value: Any) -> int | None:
    if value is None or (isinstance(value, str) and value in {"", "."}):
        return None
    parsed = int(value)
    if parsed < 0:
        raise ValidationError("allele index cannot be negative")
    return parsed


def _optional_float(value: Any) -> float | None:
    if value is None or (isinstance(value, str) and value in {"", "."}):
        return None
    parsed = float(value)
    if parsed < 0:
        raise ValidationError("numeric support values cannot be negative")
    return parsed


def _median_optional(values: Iterable[float | None]) -> float | None:
    parsed = sorted(value for value in values if value is not None)
    if not parsed:
        return None
    middle = len(parsed) // 2
    if len(parsed) % 2:
        return round(parsed[middle], 6)
    return round((parsed[middle - 1] + parsed[middle]) / 2, 6)


def _optional_text(value: Any) -> str | None:
    if value is None or (isinstance(value, str) and value in {"", "."}):
        return None
    return str(value)


def _prefix_max(values: Iterable[int]) -> tuple[int, ...]:
    running = 0
    output: list[int] = []
    for value in values:
        running = max(running, value)
        output.append(running)
    return tuple(output)


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "mobile"}


__all__ = [
    "AlleleAwareRepresentationReport",
    "AlleleAwareStructuralEvent",
    "AlleleAwareStructuralObservation",
    "AlleleAwareSvRepresenter",
    "GraphProjectionMatch",
    "GraphProjectionReport",
    "HaplotypeAlleleCall",
    "HaplotypeAssemblyReport",
    "HaplotypePath",
    "PangenomeGraphNode",
    "PangenomeGraphProjector",
    "PhasedHaplotypeAssembler",
    "PhasedVariantObservation",
    "RepeatFeatureAnnotation",
    "RepeatFeatureHit",
    "RepeatMobileAnnotationReport",
    "RepeatMobileElementAnnotator",
    "StructuralAlphaIssue",
    "StructuralAlphaState",
]
