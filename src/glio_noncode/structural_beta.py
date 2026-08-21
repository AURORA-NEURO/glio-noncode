"""Scientific-beta structural variation detectors with explicit evidence limits.

This module extends the Domain 02 reconstruction and harmonization boundary
with four independent, source-accounted operations:

* focal-amplification boundary mapping from copy-number segments;
* chromothripsis candidate detection from clustered breakpoint patterns;
* extrachromosomal-DNA candidate detection from declared circular evidence; and
* enhancer-hijacking candidate detection from context-matched structural links.

The detectors report inspectable patterns, not clinical interpretations. They
never manufacture circularity, infer a target gene from proximity alone, turn
an evidence index into a probability, or merge incompatible reference
contexts. Every accepted row retains a raw hash, source identity, and version.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from statistics import median
from typing import Any

from .errors import ValidationError
from .identity import normalize_chromosome
from .serialization import content_hash, jsonable, require_non_empty


class StructuralBetaState(StrEnum):
    """Evidence state shared by the Domain 02 beta detectors."""

    SUPPORTED = "supported"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    ABSTAINED = "abstained"
    INVALID = "invalid"
    OUT_OF_DOMAIN = "out_of_domain"
    CONTRADICTORY = "contradictory"


@dataclass(frozen=True, slots=True)
class StructuralBetaIssue:
    """A row-addressable anomaly that remains beside the detector output."""

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
class FocalAmplificationBoundary:
    """One merged focal-amplification interval and its boundary provenance."""

    candidate_id: str
    chromosome: str
    start: int
    end: int
    segment_ids: tuple[str, ...]
    caller_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    max_copy_number: float
    median_copy_number: float
    baseline_copy_number: float
    left_boundary_support: tuple[int, ...]
    right_boundary_support: tuple[int, ...]
    boundary_disagreement_bp: int
    state: StructuralBetaState
    criteria: tuple[str, ...]
    raw_hashes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FocalAmplificationMap:
    """Focal-amplification boundary map with unresolved rows retained."""

    input_hash: str
    context_key: str | None
    state: StructuralBetaState
    candidates: tuple[FocalAmplificationBoundary, ...]
    issues: tuple[StructuralBetaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class FocalAmplificationBoundaryMapper:
    """Map high-copy segments into boundary candidates without smoothing truth."""

    def map(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str | None = None,
        baseline_copy_number: float = 2.0,
        amplification_threshold: float = 6.0,
        minimum_gain: float = 2.0,
        merge_gap_bp: int = 0,
        boundary_tolerance_bp: int = 50,
    ) -> FocalAmplificationMap:
        raw_values = tuple(records)
        input_hash = content_hash(raw_values)
        issues: list[StructuralBetaIssue] = []
        if baseline_copy_number < 0 or amplification_threshold < 0 or minimum_gain < 0:
            issue = StructuralBetaIssue(
                "invalid_threshold",
                "copy-number thresholds must be non-negative",
                input_hash,
                severity="error",
            )
            return self._report(input_hash, context_key, StructuralBetaState.INVALID, (), (issue,))
        if merge_gap_bp < 0 or boundary_tolerance_bp < 0:
            issue = StructuralBetaIssue(
                "invalid_boundary_parameter",
                "merge gap and boundary tolerance must be non-negative",
                input_hash,
                severity="error",
            )
            return self._report(input_hash, context_key, StructuralBetaState.INVALID, (), (issue,))
        parsed: list[dict[str, Any]] = []
        context_mismatch = False
        for row_number, row in enumerate(raw_values, start=1):
            if not isinstance(row, Mapping):
                issues.append(
                    StructuralBetaIssue(
                        "row_not_object",
                        "copy-number record must be an object",
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
                    StructuralBetaIssue(
                        "context_mismatch",
                        "copy-number record is outside the requested reference context",
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                    )
                )
                continue
            try:
                chromosome = normalize_chromosome(str(_value(row, "chromosome", "chrom", "contig")))
                start = _positive_int(_value(row, "start", "position", "pos"), "start")
                end = _positive_int(_value(row, "end", default=start), "end")
                if end < start:
                    raise ValidationError("copy-number end must be at or after start")
                copy_number = _number(
                    _value(row, "copy_number", "total_copy_number", "CN", "cn"),
                    "copy_number",
                )
                if copy_number < 0:
                    raise ValidationError("copy number cannot be negative")
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    StructuralBetaIssue(
                        "invalid_copy_number_record",
                        str(exc),
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                        raw_record=dict(row),
                    )
                )
                continue
            try:
                baseline = _number(
                    _value(
                        row,
                        "baseline_copy_number",
                        "baseline_cn",
                        default=baseline_copy_number,
                    ),
                    "baseline_copy_number",
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    StructuralBetaIssue(
                        "invalid_baseline_copy_number",
                        str(exc),
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                        raw_record=dict(row),
                    )
                )
                continue
            parsed.append(
                {
                    "record_id": str(
                        _value(row, "segment_id", "record_id", "id", default=f"row-{row_number}")
                    ),
                    "caller_id": str(_value(row, "caller_id", "caller", default="unspecified")),
                    "source_id": _source_id(row),
                    "source_version": _source_version(row),
                    "chromosome": chromosome,
                    "start": start,
                    "end": end,
                    "copy_number": copy_number,
                    "baseline": baseline,
                    "raw_hash": raw_hash,
                    "is_amplified": copy_number >= amplification_threshold
                    or copy_number - baseline >= minimum_gain,
                }
            )
        amplified = [item for item in parsed if item["is_amplified"]]
        clusters: list[list[dict[str, Any]]] = []
        by_chromosome: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in amplified:
            by_chromosome[item["chromosome"]].append(item)
        for chromosome in sorted(by_chromosome):
            current: list[dict[str, Any]] = []
            current_end = 0
            for item in sorted(
                by_chromosome[chromosome], key=lambda value: (value["start"], value["end"])
            ):
                if current and item["start"] > current_end + merge_gap_bp + 1:
                    clusters.append(current)
                    current = []
                current.append(item)
                current_end = max(current_end, item["end"])
            if current:
                clusters.append(current)
        candidates: list[FocalAmplificationBoundary] = []
        for cluster in clusters:
            candidate = self._candidate(cluster, boundary_tolerance_bp)
            candidates.append(candidate)
        if context_mismatch:
            state = StructuralBetaState.OUT_OF_DOMAIN
        elif not candidates:
            state = StructuralBetaState.ABSTAINED
        elif any(candidate.state == StructuralBetaState.AMBIGUOUS for candidate in candidates):
            state = StructuralBetaState.AMBIGUOUS
        elif any(candidate.state == StructuralBetaState.PARTIAL for candidate in candidates):
            state = StructuralBetaState.PARTIAL
        else:
            state = StructuralBetaState.SUPPORTED
        warnings = (
            "A focal amplification boundary is a copy-number observation, not a gene-level "
            "or clinical claim.",
            "Merged intervals use only observed segments; uncovered sequence is not imputed.",
        )
        return self._report(
            input_hash, context_key, state, tuple(candidates), tuple(issues), warnings
        )

    @staticmethod
    def _candidate(
        cluster: list[dict[str, Any]],
        boundary_tolerance_bp: int,
    ) -> FocalAmplificationBoundary:
        chromosome = cluster[0]["chromosome"]
        start = min(item["start"] for item in cluster)
        end = max(item["end"] for item in cluster)
        left = tuple(sorted({item["start"] for item in cluster}))
        right = tuple(sorted({item["end"] for item in cluster}))
        boundary_disagreement = max(
            max(left) - min(left) if left else 0,
            max(right) - min(right) if right else 0,
        )
        caller_ids = tuple(sorted({item["caller_id"] for item in cluster}))
        state = (
            StructuralBetaState.AMBIGUOUS
            if boundary_disagreement > boundary_tolerance_bp
            else StructuralBetaState.SUPPORTED
            if len(caller_ids) >= 2
            else StructuralBetaState.PARTIAL
        )
        body = {
            "chromosome": chromosome,
            "start": start,
            "end": end,
            "segment_ids": tuple(item["record_id"] for item in cluster),
            "raw_hashes": tuple(item["raw_hash"] for item in cluster),
        }
        return FocalAmplificationBoundary(
            candidate_id="focal-amp:" + content_hash(body).split(":", 1)[1][:24],
            chromosome=chromosome,
            start=start,
            end=end,
            segment_ids=tuple(sorted(item["record_id"] for item in cluster)),
            caller_ids=caller_ids,
            source_ids=tuple(sorted({item["source_id"] for item in cluster})),
            max_copy_number=round(max(item["copy_number"] for item in cluster), 6),
            median_copy_number=round(float(median(item["copy_number"] for item in cluster)), 6),
            baseline_copy_number=round(float(median(item["baseline"] for item in cluster)), 6),
            left_boundary_support=left,
            right_boundary_support=right,
            boundary_disagreement_bp=boundary_disagreement,
            state=state,
            criteria=(
                "copy number crossed the configured amplification threshold or gain threshold",
                "segments were merged only when their observed intervals touched the "
                "configured gap",
                "caller boundary positions remain available for disagreement review",
            ),
            raw_hashes=tuple(sorted(item["raw_hash"] for item in cluster)),
            content_address=content_hash(body | {"state": state}),
        )

    @staticmethod
    def _report(
        input_hash: str,
        context_key: str | None,
        state: StructuralBetaState,
        candidates: tuple[FocalAmplificationBoundary, ...],
        issues: tuple[StructuralBetaIssue, ...],
        warnings: tuple[str, ...] = (),
    ) -> FocalAmplificationMap:
        body = {
            "input_hash": input_hash,
            "context_key": context_key,
            "state": state,
            "candidates": candidates,
            "issues": issues,
        }
        return FocalAmplificationMap(
            input_hash=input_hash,
            context_key=context_key,
            state=state,
            candidates=candidates,
            issues=issues,
            warnings=warnings,
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class ChromothripsisPattern:
    """One breakpoint-cluster pattern with descriptive, non-probabilistic metrics."""

    candidate_id: str
    chromosome: str
    start: int
    end: int
    breakpoint_ids: tuple[str, ...]
    breakpoint_positions: tuple[int, ...]
    breakpoint_count: int
    cluster_span_bp: int
    orientation_switches: int
    copy_number_states: tuple[str, ...]
    copy_number_switches: int
    evidence_index: float
    criteria: tuple[str, ...]
    state: StructuralBetaState
    raw_hashes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromothripsisDetectionReport:
    """Chromothripsis pattern candidates and their input-bound limitations."""

    input_hash: str
    context_key: str | None
    state: StructuralBetaState
    candidates: tuple[ChromothripsisPattern, ...]
    issues: tuple[StructuralBetaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ChromothripsisPatternDetector:
    """Detect clustered breakpoint patterns while preserving missing modalities."""

    def detect(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str | None = None,
        min_breakpoints: int = 6,
        max_cluster_span_bp: int = 10_000_000,
        max_gap_bp: int = 2_000_000,
        min_orientation_switches: int = 3,
        require_copy_number_oscillation: bool = False,
    ) -> ChromothripsisDetectionReport:
        raw_values = tuple(records)
        input_hash = content_hash(raw_values)
        issues: list[StructuralBetaIssue] = []
        if min_breakpoints < 2 or max_cluster_span_bp < 1 or max_gap_bp < 0:
            issue = StructuralBetaIssue(
                "invalid_pattern_parameter",
                "breakpoint pattern parameters are outside their valid bounds",
                input_hash,
                severity="error",
            )
            return self._report(input_hash, context_key, StructuralBetaState.INVALID, (), (issue,))
        breakpoints: list[dict[str, Any]] = []
        context_mismatch = False
        for row_number, row in enumerate(raw_values, start=1):
            if not isinstance(row, Mapping):
                issues.append(
                    StructuralBetaIssue(
                        "row_not_object",
                        "structural breakpoint record must be an object",
                        content_hash({"row": row}),
                        row_number,
                        severity="error",
                    )
                )
                continue
            row_hash = _raw_hash(row)
            row_context = _context(row)
            if context_key and row_context and row_context != context_key:
                context_mismatch = True
                issues.append(
                    StructuralBetaIssue(
                        "context_mismatch",
                        "breakpoint record is outside the requested reference context",
                        row_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                    )
                )
                continue
            nested = row.get("breakpoints")
            nested_values = (
                nested
                if isinstance(nested, Iterable) and not isinstance(nested, (str, bytes, Mapping))
                else (row,)
            )
            for nested_index, item in enumerate(nested_values, start=1):
                if not isinstance(item, Mapping):
                    issues.append(
                        StructuralBetaIssue(
                            "breakpoint_not_object",
                            "nested breakpoint must be an object",
                            content_hash({"row": row, "nested_index": nested_index}),
                            row_number,
                            source_id=_source_id(row),
                        )
                    )
                    continue
                try:
                    chromosome = normalize_chromosome(
                        str(
                            _value(
                                item,
                                "chromosome",
                                "chrom",
                                default=_value(row, "chromosome", "chrom"),
                            )
                        )
                    )
                    position = _positive_int(
                        _value(
                            item,
                            "position",
                            "pos",
                            "start",
                            default=_value(row, "position", "pos", "start"),
                        ),
                        "position",
                    )
                except (TypeError, ValueError, ValidationError) as exc:
                    issues.append(
                        StructuralBetaIssue(
                            "invalid_breakpoint",
                            str(exc),
                            content_hash(item),
                            row_number,
                            source_id=_source_id(row),
                            severity="error",
                            raw_record=dict(item),
                        )
                    )
                    continue
                event_id = str(
                    _value(row, "event_id", "record_id", "id", default=f"row-{row_number}")
                )
                breakpoints.append(
                    {
                        "breakpoint_id": str(
                            _value(
                                item,
                                "breakpoint_id",
                                "id",
                                default=f"{event_id}:bp:{nested_index}",
                            )
                        ),
                        "event_id": event_id,
                        "chromosome": chromosome,
                        "position": position,
                        "orientation": _orientation(
                            _value(
                                item,
                                "orientation",
                                "strand",
                                default=_value(row, "orientation", "strand"),
                            )
                        ),
                        "copy_number_state": _copy_state(
                            _value(
                                item,
                                "copy_number_state",
                                "cn_state",
                                default=_value(row, "copy_number_state", "cn_state"),
                            )
                        ),
                        "raw_hash": content_hash({"row": row_hash, "item": item}),
                    }
                )
        by_chromosome: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for breakpoint in breakpoints:
            by_chromosome[breakpoint["chromosome"]].append(breakpoint)
        clusters: list[list[dict[str, Any]]] = []
        for chromosome in sorted(by_chromosome):
            current: list[dict[str, Any]] = []
            for breakpoint in sorted(
                by_chromosome[chromosome], key=lambda value: value["position"]
            ):
                if current and (
                    breakpoint["position"] - current[-1]["position"] > max_gap_bp
                    or breakpoint["position"] - current[0]["position"] > max_cluster_span_bp
                ):
                    clusters.append(current)
                    current = []
                current.append(breakpoint)
            if current:
                clusters.append(current)
        candidates: list[ChromothripsisPattern] = []
        for cluster in clusters:
            if len(cluster) < min_breakpoints:
                continue
            candidates.append(
                self._candidate(cluster, min_orientation_switches, require_copy_number_oscillation)
            )
        if context_mismatch:
            state = StructuralBetaState.OUT_OF_DOMAIN
        elif not candidates:
            state = StructuralBetaState.ABSTAINED
        elif any(candidate.state == StructuralBetaState.SUPPORTED for candidate in candidates):
            state = StructuralBetaState.SUPPORTED
        else:
            state = StructuralBetaState.PARTIAL
        warnings = (
            "The evidence index is descriptive and is not a calibrated probability of "
            "chromothripsis.",
            "Breakpoint clustering is local to the supplied records and does not establish "
            "a biological mechanism.",
        )
        return self._report(
            input_hash, context_key, state, tuple(candidates), tuple(issues), warnings
        )

    @staticmethod
    def _candidate(
        cluster: list[dict[str, Any]],
        min_orientation_switches: int,
        require_copy_number_oscillation: bool,
    ) -> ChromothripsisPattern:
        positions = tuple(item["position"] for item in cluster)
        orientations = tuple(item["orientation"] for item in cluster if item["orientation"])
        orientation_switches = sum(
            left != right for left, right in zip(orientations, orientations[1:], strict=False)
        )
        copy_states = tuple(
            dict.fromkeys(
                item["copy_number_state"] for item in cluster if item["copy_number_state"]
            )
        )
        ordered_copy_states = tuple(
            item["copy_number_state"] for item in cluster if item["copy_number_state"]
        )
        copy_switches = sum(
            left != right
            for left, right in zip(ordered_copy_states, ordered_copy_states[1:], strict=False)
        )
        span = positions[-1] - positions[0]
        criteria = [
            "breakpoints form a bounded local cluster",
            f"at least {len(cluster)} breakpoints were retained",
        ]
        if orientation_switches >= min_orientation_switches:
            criteria.append("orientation switches meet the configured pattern threshold")
        else:
            criteria.append("orientation evidence is incomplete or below the configured threshold")
        if copy_switches >= 2:
            criteria.append("copy-number states oscillate across the ordered cluster")
        elif not copy_states:
            criteria.append("copy-number state evidence was not supplied")
        else:
            criteria.append(
                "copy-number state variation is insufficient for an oscillation criterion"
            )
        score = round(
            min(
                1.0,
                0.35 * min(1.0, len(cluster) / 12.0)
                + 0.35 * min(1.0, orientation_switches / max(1, min_orientation_switches))
                + 0.30 * min(1.0, copy_switches / 2.0),
            ),
            6,
        )
        sufficient_orientation = orientation_switches >= min_orientation_switches
        sufficient_copy = copy_switches >= 2
        state = (
            StructuralBetaState.SUPPORTED
            if sufficient_orientation
            and (sufficient_copy or not require_copy_number_oscillation)
            and copy_states
            else StructuralBetaState.PARTIAL
        )
        body = {
            "chromosome": cluster[0]["chromosome"],
            "positions": positions,
            "breakpoint_ids": tuple(item["breakpoint_id"] for item in cluster),
            "raw_hashes": tuple(item["raw_hash"] for item in cluster),
        }
        return ChromothripsisPattern(
            candidate_id="chromothripsis:" + content_hash(body).split(":", 1)[1][:24],
            chromosome=cluster[0]["chromosome"],
            start=positions[0],
            end=positions[-1],
            breakpoint_ids=tuple(item["breakpoint_id"] for item in cluster),
            breakpoint_positions=positions,
            breakpoint_count=len(cluster),
            cluster_span_bp=span,
            orientation_switches=orientation_switches,
            copy_number_states=copy_states,
            copy_number_switches=copy_switches,
            evidence_index=score,
            criteria=tuple(criteria),
            state=state,
            raw_hashes=tuple(sorted(item["raw_hash"] for item in cluster)),
            content_address=content_hash(body | {"state": state, "evidence_index": score}),
        )

    @staticmethod
    def _report(
        input_hash: str,
        context_key: str | None,
        state: StructuralBetaState,
        candidates: tuple[ChromothripsisPattern, ...],
        issues: tuple[StructuralBetaIssue, ...],
        warnings: tuple[str, ...] = (),
    ) -> ChromothripsisDetectionReport:
        body = {
            "input_hash": input_hash,
            "context_key": context_key,
            "state": state,
            "candidates": candidates,
            "issues": issues,
        }
        return ChromothripsisDetectionReport(
            input_hash=input_hash,
            context_key=context_key,
            state=state,
            candidates=candidates,
            issues=issues,
            warnings=warnings,
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class EcDnaCandidate:
    """One ecDNA candidate supported by explicit circular structural evidence."""

    candidate_id: str
    component_id: str
    chromosomes: tuple[str, ...]
    intervals: tuple[tuple[str, int, int], ...]
    junction_count: int
    maximum_copy_number: float | None
    caller_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    circular_evidence: tuple[str, ...]
    amplification_evidence: tuple[str, ...]
    conflicting_linear_evidence: tuple[str, ...]
    state: StructuralBetaState
    criteria: tuple[str, ...]
    raw_hashes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EcDnaDetectionReport:
    """ecDNA candidates with explicit confirmation limits."""

    input_hash: str
    context_key: str | None
    state: StructuralBetaState
    candidates: tuple[EcDnaCandidate, ...]
    issues: tuple[StructuralBetaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ExtrachromosomalDnaCandidateDetector:
    """Detect declared circular amplicon candidates without inferring circularity."""

    def detect(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str | None = None,
        minimum_copy_number: float = 6.0,
        minimum_junctions: int = 2,
    ) -> EcDnaDetectionReport:
        raw_values = tuple(records)
        input_hash = content_hash(raw_values)
        issues: list[StructuralBetaIssue] = []
        if minimum_copy_number < 0 or minimum_junctions < 1:
            issue = StructuralBetaIssue(
                "invalid_ecdna_parameter",
                "ecDNA thresholds are outside their valid bounds",
                input_hash,
                severity="error",
            )
            return self._report(input_hash, context_key, StructuralBetaState.INVALID, (), (issue,))
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        context_mismatch = False
        for row_number, row in enumerate(raw_values, start=1):
            if not isinstance(row, Mapping):
                issues.append(
                    StructuralBetaIssue(
                        "row_not_object",
                        "ecDNA evidence record must be an object",
                        content_hash({"row": row}),
                        row_number,
                        severity="error",
                    )
                )
                continue
            row_hash = _raw_hash(row)
            row_context = _context(row)
            if context_key and row_context and row_context != context_key:
                context_mismatch = True
                issues.append(
                    StructuralBetaIssue(
                        "context_mismatch",
                        "ecDNA evidence is outside the requested reference context",
                        row_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                    )
                )
                continue
            try:
                component_id = str(
                    _value(row, "component_id", "cycle_id", "amplicon_id", "event_id", "id")
                )
                require_non_empty(component_id, "component_id")
                copy_number_value = _value(row, "copy_number", "CN", "cn")
                copy_number = (
                    _number(copy_number_value, "copy_number")
                    if copy_number_value not in {None, ""}
                    else None
                )
                intervals = _intervals(row)
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    StructuralBetaIssue(
                        "invalid_ecdna_record",
                        str(exc),
                        row_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                        raw_record=dict(row),
                    )
                )
                continue
            nested_breakpoints = row.get("breakpoints")
            nested_count = (
                len(tuple(nested_breakpoints))
                if isinstance(nested_breakpoints, Iterable)
                and not isinstance(nested_breakpoints, (str, bytes, Mapping))
                else 0
            )
            junction_count = int(
                _value(row, "junction_count", "junctions", default=max(nested_count, 0))
            )
            groups[component_id].append(
                {
                    "component_id": component_id,
                    "chromosomes": tuple(sorted({interval[0] for interval in intervals})),
                    "intervals": intervals,
                    "junction_count": junction_count,
                    "copy_number": copy_number,
                    "circular": _bool(_value(row, "is_circular", "circular", "circle_evidence")),
                    "linear": _bool(_value(row, "linear_evidence", "linear_path")),
                    "circular_label": str(
                        _value(
                            row,
                            "circular_evidence_id",
                            "circle_method",
                            default="declared_circularity",
                        )
                    ),
                    "amplification_label": str(
                        _value(
                            row,
                            "amplification_evidence_id",
                            "copy_number_method",
                            default="copy_number",
                        )
                    ),
                    "caller_id": str(_value(row, "caller_id", "caller", default="unspecified")),
                    "source_id": _source_id(row),
                    "raw_hash": row_hash,
                }
            )
        candidates: list[EcDnaCandidate] = []
        for component_id, group in sorted(groups.items()):
            if not any(item["circular"] for item in group):
                continue
            candidates.append(
                self._candidate(component_id, group, minimum_copy_number, minimum_junctions)
            )
        if context_mismatch:
            state = StructuralBetaState.OUT_OF_DOMAIN
        elif not candidates:
            state = StructuralBetaState.ABSTAINED
        elif any(candidate.state == StructuralBetaState.AMBIGUOUS for candidate in candidates):
            state = StructuralBetaState.AMBIGUOUS
        elif all(candidate.state == StructuralBetaState.SUPPORTED for candidate in candidates):
            state = StructuralBetaState.SUPPORTED
        else:
            state = StructuralBetaState.PARTIAL
        warnings = (
            "An ecDNA result is a structural candidate; orthogonal imaging, molecule, or "
            "assembly evidence is not inferred.",
            "Explicit circular evidence is required; high copy number alone never creates "
            "an ecDNA candidate.",
        )
        return self._report(
            input_hash, context_key, state, tuple(candidates), tuple(issues), warnings
        )

    @staticmethod
    def _candidate(
        component_id: str,
        group: list[dict[str, Any]],
        minimum_copy_number: float,
        minimum_junctions: int,
    ) -> EcDnaCandidate:
        circular_evidence = tuple(
            sorted({item["circular_label"] for item in group if item["circular"]})
        )
        conflicting_linear = tuple(sorted({item["source_id"] for item in group if item["linear"]}))
        copy_numbers = tuple(
            item["copy_number"] for item in group if item["copy_number"] is not None
        )
        maximum_copy_number = max(copy_numbers) if copy_numbers else None
        total_junctions = max(item["junction_count"] for item in group)
        has_amplification = any(
            item["copy_number"] is not None and item["copy_number"] >= minimum_copy_number
            for item in group
        )
        independent_callers = len({item["caller_id"] for item in group})
        criteria = ["explicit circular evidence was supplied"]
        if total_junctions >= minimum_junctions:
            criteria.append("circular junction count meets the configured minimum")
        else:
            criteria.append("circular junction count is below the configured minimum")
        if has_amplification:
            criteria.append("copy number meets the configured amplification threshold")
        else:
            criteria.append("copy-number amplification evidence is missing or below threshold")
        if independent_callers >= 2:
            criteria.append("circular evidence is contributed by multiple callers")
        else:
            criteria.append("circular evidence has one or fewer independent callers")
        if conflicting_linear:
            criteria.append("linear-path evidence conflicts with circular evidence")
        state = (
            StructuralBetaState.AMBIGUOUS
            if conflicting_linear
            else StructuralBetaState.SUPPORTED
            if total_junctions >= minimum_junctions
            and has_amplification
            and independent_callers >= 2
            else StructuralBetaState.PARTIAL
        )
        intervals = tuple(sorted({interval for item in group for interval in item["intervals"]}))
        body = {
            "component_id": component_id,
            "intervals": intervals,
            "raw_hashes": tuple(item["raw_hash"] for item in group),
        }
        return EcDnaCandidate(
            candidate_id="ecdna:" + content_hash(body).split(":", 1)[1][:24],
            component_id=component_id,
            chromosomes=tuple(
                sorted({chromosome for item in group for chromosome in item["chromosomes"]})
            ),
            intervals=intervals,
            junction_count=total_junctions,
            maximum_copy_number=(
                round(maximum_copy_number, 6) if maximum_copy_number is not None else None
            ),
            caller_ids=tuple(sorted({item["caller_id"] for item in group})),
            source_ids=tuple(sorted({item["source_id"] for item in group})),
            circular_evidence=circular_evidence,
            amplification_evidence=tuple(
                sorted(
                    {
                        item["amplification_label"]
                        for item in group
                        if item["copy_number"] is not None
                    }
                )
            ),
            conflicting_linear_evidence=conflicting_linear,
            state=state,
            criteria=tuple(criteria),
            raw_hashes=tuple(sorted(item["raw_hash"] for item in group)),
            content_address=content_hash(
                body | {"state": state, "junction_count": total_junctions}
            ),
        )

    @staticmethod
    def _report(
        input_hash: str,
        context_key: str | None,
        state: StructuralBetaState,
        candidates: tuple[EcDnaCandidate, ...],
        issues: tuple[StructuralBetaIssue, ...],
        warnings: tuple[str, ...] = (),
    ) -> EcDnaDetectionReport:
        body = {
            "input_hash": input_hash,
            "context_key": context_key,
            "state": state,
            "candidates": candidates,
            "issues": issues,
        }
        return EcDnaDetectionReport(
            input_hash=input_hash,
            context_key=context_key,
            state=state,
            candidates=candidates,
            issues=issues,
            warnings=warnings,
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class EnhancerHijackingCandidate:
    """One context-matched enhancer-to-gene structural bridge candidate."""

    candidate_id: str
    event_id: str
    enhancer_id: str
    target_gene_id: str
    context_key: str
    enhancer_interval: tuple[str, int, int] | None
    promoter_interval: tuple[str, int, int] | None
    breakpoint_bridge: bool
    evidence_channels: tuple[str, ...]
    source_ids: tuple[str, ...]
    source_versions: tuple[str, ...]
    state: StructuralBetaState
    alternatives_for_event: tuple[str, ...]
    criteria: tuple[str, ...]
    raw_hashes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EnhancerHijackingDetectionReport:
    """Enhancer-hijacking candidates with alternative genes retained."""

    input_hash: str
    context_key: str | None
    state: StructuralBetaState
    candidates: tuple[EnhancerHijackingCandidate, ...]
    issues: tuple[StructuralBetaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class EnhancerHijackingCandidateDetector:
    """Detect declared SV-to-enhancer-to-gene bridges without nearest-gene inference."""

    def detect(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
        minimum_evidence_channels: int = 2,
    ) -> EnhancerHijackingDetectionReport:
        raw_values = tuple(records)
        input_hash = content_hash(raw_values)
        issues: list[StructuralBetaIssue] = []
        if not context_key.strip() or minimum_evidence_channels < 1:
            issue = StructuralBetaIssue(
                "invalid_hijacking_parameter",
                "enhancer-hijacking detection requires a context and positive evidence threshold",
                input_hash,
                severity="error",
            )
            return self._report(input_hash, context_key, StructuralBetaState.INVALID, (), (issue,))
        grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
        context_mismatch = False
        for row_number, row in enumerate(raw_values, start=1):
            if not isinstance(row, Mapping):
                issues.append(
                    StructuralBetaIssue(
                        "row_not_object",
                        "enhancer-hijacking evidence record must be an object",
                        content_hash({"row": row}),
                        row_number,
                        severity="error",
                    )
                )
                continue
            row_hash = _raw_hash(row)
            row_context = _context(row)
            if row_context != context_key:
                context_mismatch = True
                issues.append(
                    StructuralBetaIssue(
                        "context_mismatch",
                        "enhancer and promoter evidence must share the requested exact context",
                        row_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                        raw_record=dict(row),
                    )
                )
                continue
            event_id = str(_value(row, "event_id", "structural_event_id", "sv_id"))
            enhancer_id = str(_value(row, "enhancer_id", "element_id", "regulatory_element_id"))
            gene_id = str(_value(row, "target_gene_id", "gene_id", "gene"))
            if not event_id or not enhancer_id or not gene_id:
                issues.append(
                    StructuralBetaIssue(
                        "incomplete_hijacking_key",
                        "event_id, enhancer_id, and target_gene_id are all required",
                        row_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                        raw_record=dict(row),
                    )
                )
                continue
            breakpoint_bridge = _bool(
                _value(
                    row,
                    "breakpoint_supported",
                    "event_connects",
                    "bridge_supported",
                    "structural_bridge",
                )
            )
            channels = set(_text_tuple(row.get("evidence_channels", ())))
            for key, label in (
                ("activity_supported", "enhancer_activity"),
                ("contact_supported", "contact"),
                ("expression_supported", "expression"),
                ("breakpoint_supported", "breakpoint"),
            ):
                if _bool(row.get(key)):
                    channels.add(label)
            if breakpoint_bridge:
                channels.add("breakpoint")
            grouped[(event_id, enhancer_id, gene_id)].append(
                {
                    "event_id": event_id,
                    "enhancer_id": enhancer_id,
                    "gene_id": gene_id,
                    "context_key": context_key,
                    "breakpoint_bridge": breakpoint_bridge,
                    "channels": tuple(sorted(channels)),
                    "enhancer_interval": _single_interval(row, "enhancer"),
                    "promoter_interval": _single_interval(row, "promoter"),
                    "source_id": _source_id(row),
                    "source_version": _source_version(row),
                    "raw_hash": row_hash,
                }
            )
        by_event_enhancer: dict[tuple[str, str], set[str]] = defaultdict(set)
        for event_id, enhancer_id, gene_id in grouped:
            by_event_enhancer[(event_id, enhancer_id)].add(gene_id)
        candidates: list[EnhancerHijackingCandidate] = []
        for key, group in sorted(grouped.items()):
            event_id, enhancer_id, gene_id = key
            if not any(item["breakpoint_bridge"] for item in group):
                issues.append(
                    StructuralBetaIssue(
                        "missing_structural_bridge",
                        "candidate was not formed because no declared structural bridge "
                        "was present",
                        content_hash(group),
                        source_id=group[0]["source_id"],
                        severity="warning",
                    )
                )
                continue
            candidates.append(
                self._candidate(
                    event_id,
                    enhancer_id,
                    gene_id,
                    group,
                    tuple(sorted(by_event_enhancer[(event_id, enhancer_id)] - {gene_id})),
                    minimum_evidence_channels,
                )
            )
        if context_mismatch:
            state = StructuralBetaState.OUT_OF_DOMAIN
        elif not candidates:
            state = StructuralBetaState.ABSTAINED
        elif any(candidate.state == StructuralBetaState.AMBIGUOUS for candidate in candidates):
            state = StructuralBetaState.AMBIGUOUS
        elif any(candidate.state == StructuralBetaState.PARTIAL for candidate in candidates):
            state = StructuralBetaState.PARTIAL
        else:
            state = StructuralBetaState.SUPPORTED
        warnings = (
            "A structural bridge plus activity or contact evidence is a candidate "
            "relationship, not proof of enhancer causality.",
            "Nearest-gene proximity is not used to create a target; alternatives remain explicit.",
        )
        return self._report(
            input_hash, context_key, state, tuple(candidates), tuple(issues), warnings
        )

    @staticmethod
    def _candidate(
        event_id: str,
        enhancer_id: str,
        gene_id: str,
        group: list[dict[str, Any]],
        alternatives: tuple[str, ...],
        minimum_evidence_channels: int,
    ) -> EnhancerHijackingCandidate:
        channels = tuple(sorted({channel for item in group for channel in item["channels"]}))
        bridge = any(item["breakpoint_bridge"] for item in group)
        if alternatives:
            state = StructuralBetaState.AMBIGUOUS
        elif len(channels) >= minimum_evidence_channels:
            state = StructuralBetaState.SUPPORTED
        else:
            state = StructuralBetaState.PARTIAL
        criteria = [
            "enhancer and target gene were supplied as explicit identifiers",
            "structural bridge was declared by the input evidence",
            f"{len(channels)} independent evidence channels were retained",
        ]
        if alternatives:
            criteria.append("multiple target-gene alternatives share the same event and enhancer")
        body = {
            "event_id": event_id,
            "enhancer_id": enhancer_id,
            "gene_id": gene_id,
            "context_key": group[0]["context_key"],
            "raw_hashes": tuple(item["raw_hash"] for item in group),
        }
        return EnhancerHijackingCandidate(
            candidate_id="hijack:" + content_hash(body).split(":", 1)[1][:24],
            event_id=event_id,
            enhancer_id=enhancer_id,
            target_gene_id=gene_id,
            context_key=group[0]["context_key"],
            enhancer_interval=next(
                (
                    item["enhancer_interval"]
                    for item in group
                    if item["enhancer_interval"] is not None
                ),
                None,
            ),
            promoter_interval=next(
                (
                    item["promoter_interval"]
                    for item in group
                    if item["promoter_interval"] is not None
                ),
                None,
            ),
            breakpoint_bridge=bridge,
            evidence_channels=channels,
            source_ids=tuple(sorted({item["source_id"] for item in group})),
            source_versions=tuple(sorted({item["source_version"] for item in group})),
            state=state,
            alternatives_for_event=alternatives,
            criteria=tuple(criteria),
            raw_hashes=tuple(sorted(item["raw_hash"] for item in group)),
            content_address=content_hash(body | {"state": state, "channels": channels}),
        )

    @staticmethod
    def _report(
        input_hash: str,
        context_key: str | None,
        state: StructuralBetaState,
        candidates: tuple[EnhancerHijackingCandidate, ...],
        issues: tuple[StructuralBetaIssue, ...],
        warnings: tuple[str, ...] = (),
    ) -> EnhancerHijackingDetectionReport:
        body = {
            "input_hash": input_hash,
            "context_key": context_key,
            "state": state,
            "candidates": candidates,
            "issues": issues,
        }
        return EnhancerHijackingDetectionReport(
            input_hash=input_hash,
            context_key=context_key,
            state=state,
            candidates=candidates,
            issues=issues,
            warnings=warnings,
            content_address=content_hash(body),
        )


def _value(row: Mapping[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        value = row.get(name)
        if value is not None and value != "":
            return value
    return default


def _positive_int(value: Any, field_name: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field_name} must be an integer") from exc
    if result < 1:
        raise ValidationError(f"{field_name} must be positive")
    return result


def _number(value: Any, field_name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field_name} must be numeric") from exc
    if result != result or result in {float("inf"), float("-inf")}:
        raise ValidationError(f"{field_name} must be finite")
    return result


def _raw_hash(row: Mapping[str, Any]) -> str:
    return str(row.get("raw_hash") or content_hash(dict(row)))


def _source_id(row: Mapping[str, Any]) -> str:
    return str(_value(row, "source_id", "source", "dataset_id", default="unspecified"))


def _source_version(row: Mapping[str, Any]) -> str:
    return str(_value(row, "source_version", "version", "release", default="unspecified"))


def _context(row: Mapping[str, Any]) -> str:
    return str(_value(row, "context_key", "reference_context", "context", default="")).strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "supported", "present"}


def _orientation(value: Any) -> str | None:
    if value in {None, "", "."}:
        return None
    text = str(value).strip().lower()
    if text in {"+", "plus", "forward", "fwd", "1"}:
        return "forward"
    if text in {"-", "minus", "reverse", "rev", "-1"}:
        return "reverse"
    return "unknown"


def _copy_state(value: Any) -> str | None:
    if value in {None, "", "."}:
        return None
    return str(value).strip().lower()


def _intervals(row: Mapping[str, Any]) -> tuple[tuple[str, int, int], ...]:
    nested = row.get("intervals")
    if isinstance(nested, Iterable) and not isinstance(nested, (str, bytes, Mapping)):
        output: list[tuple[str, int, int]] = []
        for item in nested:
            if not isinstance(item, Mapping):
                continue
            chromosome = normalize_chromosome(str(_value(item, "chromosome", "chrom", "contig")))
            start = _positive_int(_value(item, "start", "position", "pos"), "interval start")
            end = _positive_int(_value(item, "end", default=start), "interval end")
            if end < start:
                raise ValidationError("interval end must be at or after start")
            output.append((chromosome, start, end))
        return tuple(sorted(set(output)))
    if _value(row, "chromosome", "chrom", "contig") is None:
        return ()
    chromosome = normalize_chromosome(str(_value(row, "chromosome", "chrom", "contig")))
    start = _positive_int(_value(row, "start", "position", "pos"), "interval start")
    end = _positive_int(_value(row, "end", default=start), "interval end")
    if end < start:
        raise ValidationError("interval end must be at or after start")
    return ((chromosome, start, end),)


def _single_interval(row: Mapping[str, Any], prefix: str) -> tuple[str, int, int] | None:
    chromosome = _value(row, f"{prefix}_chromosome", f"{prefix}_chrom", f"{prefix}_contig")
    start = _value(row, f"{prefix}_start", f"{prefix}_position", f"{prefix}_pos")
    end = _value(row, f"{prefix}_end", default=start)
    if chromosome is None or start is None:
        return None
    return (
        normalize_chromosome(str(chromosome)),
        _positive_int(start, f"{prefix}_start"),
        _positive_int(end, f"{prefix}_end"),
    )


def _text_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        values = value.replace(";", "|").replace(",", "|").split("|")
    elif isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, Mapping)):
        values = [str(item) for item in value]
    else:
        values = [str(value)]
    return tuple(dict.fromkeys(item.strip() for item in values if item.strip()))


__all__ = [
    "ChromothripsisPattern",
    "ChromothripsisDetectionReport",
    "ChromothripsisPatternDetector",
    "EcDnaCandidate",
    "EcDnaDetectionReport",
    "EnhancerHijackingCandidate",
    "EnhancerHijackingDetectionReport",
    "EnhancerHijackingCandidateDetector",
    "ExtrachromosomalDnaCandidateDetector",
    "FocalAmplificationBoundary",
    "FocalAmplificationBoundaryMapper",
    "FocalAmplificationMap",
    "StructuralBetaIssue",
    "StructuralBetaState",
]
