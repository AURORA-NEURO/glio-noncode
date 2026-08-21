"""Deep sequence-regulatory contracts for Domain 06.

This module keeps four sequence operations explicit and inspectable:

* a deterministic nucleosome sequence-propensity index;
* a splice-regulatory noncoding motif scanner;
* a 5'/3' UTR regulatory scanner with bounded uORF discovery; and
* a promoter core-grammar evaluator over declared motif-spacing rules.

Every operation is sequence evidence, not a calibrated occupancy, splicing,
translation, promoter-activity, causal, or clinical claim. Alternate alleles
are compared only when both sequence windows are supplied. Missing context,
ambiguous bases, unsupported rows, and competing grammar matches remain
visible in typed result objects.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite
from statistics import mean
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty


class SequenceAlphaState(StrEnum):
    """Evidence state shared by the Domain 06 sequence-alpha contracts."""

    SUPPORTED = "supported"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    ABSTAINED = "abstained"
    INVALID = "invalid"
    OUT_OF_DOMAIN = "out_of_domain"
    CONTRADICTORY = "contradictory"


@dataclass(frozen=True, slots=True)
class SequenceAlphaIssue:
    """Row-addressable sequence issue with a source receipt."""

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
class NucleosomePropensityWindow:
    """One sequence window with transparent propensity features."""

    window_id: str
    sequence_id: str
    chromosome: str
    start: int
    end: int
    context_key: str
    sequence_hash: str
    sequence_length: int
    gc_fraction: float
    periodicity_score: float
    gc_balance_score: float
    propensity_score: float
    positioning_label: str
    state: SequenceAlphaState
    source_id: str
    source_version: str
    raw_hash: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class NucleosomePropensityReport:
    """Sequence windows and issues from the nucleosome propensity model."""

    input_hash: str
    context_key: str | None
    state: SequenceAlphaState
    windows: tuple[NucleosomePropensityWindow, ...]
    issues: tuple[SequenceAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class NucleosomeSequencePropensityModel:
    """Calculate a bounded, deterministic sequence propensity index.

    The index uses a phase-maximized dinucleotide periodicity feature and a
    GC-balance feature. It is intentionally a transparent proxy, not a
    physical nucleosome-occupancy model and not a trained predictor.
    """

    def predict(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str | None = None,
        minimum_length: int = 147,
        periodicity_period: int = 10,
        favored_threshold: float = 0.65,
        depleted_threshold: float = 0.35,
    ) -> NucleosomePropensityReport:
        values = tuple(records)
        input_hash = content_hash(values)
        issues: list[SequenceAlphaIssue] = []
        windows: list[NucleosomePropensityWindow] = []
        context_mismatch = False
        if (
            minimum_length < 1
            or periodicity_period < 2
            or not 0 <= depleted_threshold < favored_threshold <= 1
        ):
            issue = SequenceAlphaIssue(
                "invalid_nucleosome_parameter",
                "nucleosome parameters are outside valid bounds",
                input_hash,
                severity="error",
            )
            return self._report(input_hash, context_key, SequenceAlphaState.INVALID, (), (issue,))
        for row_number, row in enumerate(values, start=1):
            if not isinstance(row, Mapping):
                issues.append(
                    SequenceAlphaIssue(
                        "row_not_object",
                        "nucleosome row must be an object",
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
                    SequenceAlphaIssue(
                        "context_mismatch",
                        "nucleosome sequence is outside the requested context",
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                    )
                )
                continue
            try:
                sequence = _sequence(row, "sequence", "seq")
                chromosome, start, end = _coordinates(row, len(sequence))
                normalized = sequence.upper()
                if any(base not in "ACGTN" for base in normalized):
                    raise ValidationError("sequence must contain only A/C/G/T/N")
                gc_fraction, periodicity, gc_balance = _nucleosome_features(
                    normalized, periodicity_period
                )
                score = round(0.65 * periodicity + 0.35 * gc_balance, 6)
                label = (
                    "favored"
                    if score >= favored_threshold
                    else "depleted"
                    if score <= depleted_threshold
                    else "neutral"
                )
                state = (
                    SequenceAlphaState.PARTIAL
                    if len(normalized) < minimum_length or "N" in normalized
                    else SequenceAlphaState.SUPPORTED
                )
                body = {
                    "sequence_id": str(
                        _value(row, "sequence_id", "id", "name", default=f"row-{row_number}")
                    ),
                    "chromosome": chromosome,
                    "start": start,
                    "end": end,
                    "context_key": row_context or context_key or "unspecified",
                    "sequence_hash": content_hash(normalized),
                    "score": score,
                }
                windows.append(
                    NucleosomePropensityWindow(
                        window_id="nuc:" + content_hash(body).split(":", 1)[1][:24],
                        sequence_id=body["sequence_id"],
                        chromosome=chromosome,
                        start=start,
                        end=end,
                        context_key=body["context_key"],
                        sequence_hash=body["sequence_hash"],
                        sequence_length=len(normalized),
                        gc_fraction=round(gc_fraction, 9),
                        periodicity_score=round(periodicity, 9),
                        gc_balance_score=round(gc_balance, 9),
                        propensity_score=score,
                        positioning_label=label,
                        state=state,
                        source_id=_source_id(row),
                        source_version=_source_version(row),
                        raw_hash=raw_hash,
                        content_address=content_hash(body | {"state": state}),
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    SequenceAlphaIssue(
                        "invalid_nucleosome_row",
                        str(exc),
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                        raw_record=dict(row),
                    )
                )
        if context_mismatch and not windows:
            state = SequenceAlphaState.OUT_OF_DOMAIN
        elif issues or any(item.state == SequenceAlphaState.PARTIAL for item in windows):
            state = SequenceAlphaState.PARTIAL
        elif not windows:
            state = SequenceAlphaState.ABSTAINED
        else:
            state = SequenceAlphaState.SUPPORTED
        return self._report(input_hash, context_key, state, tuple(windows), tuple(issues))

    @staticmethod
    def _report(
        input_hash: str,
        context_key: str | None,
        state: SequenceAlphaState,
        windows: tuple[NucleosomePropensityWindow, ...],
        issues: tuple[SequenceAlphaIssue, ...],
    ) -> NucleosomePropensityReport:
        return NucleosomePropensityReport(
            input_hash=input_hash,
            context_key=context_key,
            state=state,
            windows=windows,
            issues=issues,
            warnings=(
                "Propensity is a transparent sequence index, not a calibrated occupancy model.",
                (
                    "Sequence propensity does not establish chromatin occupancy, activity, "
                    "or causality."
                ),
            ),
            content_address=content_hash(
                {"input_hash": input_hash, "state": state, "windows": windows, "issues": issues}
            ),
        )


@dataclass(frozen=True, slots=True)
class SpliceMotifDefinition:
    """Declared splice-regulatory consensus motif."""

    motif_id: str
    name: str
    consensus: str
    role: str
    source_id: str
    source_version: str
    threshold: float = 0.8
    strand_aware: bool = True

    def __post_init__(self) -> None:
        for name in ("motif_id", "name", "consensus", "role", "source_id", "source_version"):
            require_non_empty(str(getattr(self, name)), name)
        if any(base not in _IUPAC for base in self.consensus.upper()):
            raise ValidationError("splice consensus contains unsupported IUPAC symbols")
        if not 0 < self.threshold <= 1:
            raise ValidationError("splice motif threshold must be between zero and one")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpliceMotifHit:
    """One splice motif match in a reference or alternate window."""

    motif_id: str
    name: str
    role: str
    start: int
    end: int
    strand: str
    matched_sequence: str
    score: float
    allele: str
    source_id: str
    source_version: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.motif_id, "motif_id")
        if self.start < 1 or self.end < self.start:
            raise ValidationError("splice hit interval is invalid")
        if self.strand not in {"+", "-"}:
            raise ValidationError("splice hit strand must be + or -")
        if self.allele not in {"observed", "reference", "alternate"}:
            raise ValidationError("splice hit allele is unsupported")
        if not 0 <= self.score <= 1:
            raise ValidationError("splice hit score must be between zero and one")

    @property
    def signature(self) -> tuple[str, str, int, int, str]:
        return (self.motif_id, self.strand, self.start, self.end, self.matched_sequence)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpliceRegulatoryWindow:
    """Splice motif evidence for one noncoding sequence window."""

    window_id: str
    sequence_id: str
    chromosome: str
    start: int
    end: int
    context_key: str
    reference_hits: tuple[SpliceMotifHit, ...]
    alternate_hits: tuple[SpliceMotifHit, ...]
    created_hits: tuple[SpliceMotifHit, ...]
    disrupted_hits: tuple[SpliceMotifHit, ...]
    state: SequenceAlphaState
    source_ids: tuple[str, ...]
    source_versions: tuple[str, ...]
    raw_hashes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpliceRegulatoryScanReport:
    """Splice motif windows and row-level issues."""

    input_hash: str
    context_key: str | None
    state: SequenceAlphaState
    windows: tuple[SpliceRegulatoryWindow, ...]
    issues: tuple[SequenceAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class SpliceRegulatoryNoncodingScanner:
    """Scan declared splice motifs without interpreting splice effect."""

    def scan(
        self,
        records: Iterable[Mapping[str, Any]],
        motifs: Iterable[SpliceMotifDefinition],
        *,
        context_key: str | None = None,
    ) -> SpliceRegulatoryScanReport:
        values = tuple(records)
        definitions = tuple(motifs)
        input_hash = content_hash(values)
        issues: list[SequenceAlphaIssue] = []
        windows: list[SpliceRegulatoryWindow] = []
        context_mismatch = False
        if not definitions:
            issue = SequenceAlphaIssue(
                "missing_splice_motifs",
                "at least one splice motif definition is required",
                input_hash,
                severity="error",
            )
            return self._report(input_hash, context_key, SequenceAlphaState.INVALID, (), (issue,))
        for row_number, row in enumerate(values, start=1):
            if not isinstance(row, Mapping):
                issues.append(
                    SequenceAlphaIssue(
                        "row_not_object",
                        "splice row must be an object",
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
                    SequenceAlphaIssue(
                        "context_mismatch",
                        "splice sequence is outside the requested context",
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                    )
                )
                continue
            try:
                reference_sequence = _sequence(row, "reference_sequence", "sequence", "seq")
                alternate_value = row.get("alternate_sequence")
                alternate_sequence = (
                    str(alternate_value).upper() if alternate_value not in {None, ""} else None
                )
                if alternate_sequence is not None and any(
                    base not in "ACGTN" for base in alternate_sequence
                ):
                    raise ValidationError("alternate sequence must contain only A/C/G/T/N")
                if any(base not in "ACGTN" for base in reference_sequence.upper()):
                    raise ValidationError("reference sequence must contain only A/C/G/T/N")
                chromosome, start, end = _coordinates(row, len(reference_sequence))
                reference_hits = _splice_hits(
                    reference_sequence,
                    definitions,
                    genomic_start=start,
                    allele="reference" if alternate_sequence is not None else "observed",
                )
                alternate_hits = (
                    _splice_hits(
                        alternate_sequence,
                        definitions,
                        genomic_start=start,
                        allele="alternate",
                    )
                    if alternate_sequence is not None
                    else reference_hits
                )
                ref_by_signature = {hit.signature: hit for hit in reference_hits}
                alt_by_signature = {hit.signature: hit for hit in alternate_hits}
                created = tuple(
                    alt_by_signature[key]
                    for key in sorted(set(alt_by_signature) - set(ref_by_signature))
                )
                disrupted = tuple(
                    ref_by_signature[key]
                    for key in sorted(set(ref_by_signature) - set(alt_by_signature))
                )
                state = (
                    SequenceAlphaState.AMBIGUOUS
                    if created and disrupted
                    else SequenceAlphaState.PARTIAL
                    if "N" in reference_sequence.upper()
                    or alternate_sequence is not None
                    and "N" in alternate_sequence
                    else SequenceAlphaState.SUPPORTED
                    if reference_hits
                    else SequenceAlphaState.ABSTAINED
                )
                body = {
                    "sequence_id": str(
                        _value(row, "sequence_id", "id", "name", default=f"row-{row_number}")
                    ),
                    "chromosome": chromosome,
                    "start": start,
                    "end": end,
                    "context_key": row_context or context_key or "unspecified",
                    "reference_hits": reference_hits,
                    "alternate_hits": alternate_hits,
                    "raw_hash": raw_hash,
                }
                windows.append(
                    SpliceRegulatoryWindow(
                        window_id="splice:" + content_hash(body).split(":", 1)[1][:24],
                        sequence_id=body["sequence_id"],
                        chromosome=chromosome,
                        start=start,
                        end=end,
                        context_key=body["context_key"],
                        reference_hits=reference_hits,
                        alternate_hits=alternate_hits,
                        created_hits=created,
                        disrupted_hits=disrupted,
                        state=state,
                        source_ids=tuple(sorted({item.source_id for item in definitions})),
                        source_versions=tuple(
                            sorted({item.source_version for item in definitions})
                        ),
                        raw_hashes=(raw_hash,),
                        content_address=content_hash(body | {"state": state}),
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    SequenceAlphaIssue(
                        "invalid_splice_row",
                        str(exc),
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                        raw_record=dict(row),
                    )
                )
        if context_mismatch and not windows:
            state = SequenceAlphaState.OUT_OF_DOMAIN
        elif any(item.state == SequenceAlphaState.AMBIGUOUS for item in windows):
            state = SequenceAlphaState.AMBIGUOUS
        elif issues or any(item.state == SequenceAlphaState.PARTIAL for item in windows):
            state = SequenceAlphaState.PARTIAL
        elif not windows:
            state = SequenceAlphaState.ABSTAINED
        else:
            state = SequenceAlphaState.SUPPORTED
        return self._report(input_hash, context_key, state, tuple(windows), tuple(issues))

    @staticmethod
    def _report(
        input_hash: str,
        context_key: str | None,
        state: SequenceAlphaState,
        windows: tuple[SpliceRegulatoryWindow, ...],
        issues: tuple[SequenceAlphaIssue, ...],
    ) -> SpliceRegulatoryScanReport:
        return SpliceRegulatoryScanReport(
            input_hash=input_hash,
            context_key=context_key,
            state=state,
            windows=windows,
            issues=issues,
            warnings=(
                "Splice motif hits are sequence-pattern observations, not splicing predictions.",
                (
                    "Noncoding sequence evidence does not establish exon usage or transcript "
                    "consequence."
                ),
            ),
            content_address=content_hash(
                {"input_hash": input_hash, "state": state, "windows": windows, "issues": issues}
            ),
        )


@dataclass(frozen=True, slots=True)
class UtrMotifDefinition:
    """Declared UTR regulatory motif or sequence element."""

    motif_id: str
    name: str
    consensus: str
    element_kind: str
    region: str
    source_id: str
    source_version: str
    threshold: float = 0.8
    strand_aware: bool = True

    def __post_init__(self) -> None:
        for name in (
            "motif_id",
            "name",
            "consensus",
            "element_kind",
            "region",
            "source_id",
            "source_version",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if self.region not in {"5utr", "3utr", "both"}:
            raise ValidationError("UTR motif region must be 5utr, 3utr, or both")
        if any(base not in _IUPAC for base in self.consensus.upper()):
            raise ValidationError("UTR consensus contains unsupported IUPAC symbols")
        if not 0 < self.threshold <= 1:
            raise ValidationError("UTR motif threshold must be between zero and one")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class UtrRegulatoryHit:
    """One UTR motif or sequence-element hit."""

    motif_id: str
    name: str
    element_kind: str
    region: str
    start: int
    end: int
    strand: str
    matched_sequence: str
    score: float
    allele: str
    source_id: str
    source_version: str
    content_address: str

    @property
    def signature(self) -> tuple[str, str, int, int, str]:
        return (self.motif_id, self.strand, self.start, self.end, self.matched_sequence)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class UtrOpenReadingFrame:
    """Bounded sequence observation of a 5' UTR start/stop pattern."""

    start: int
    end: int
    frame: int
    stop_codon: str
    codon_length: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class UtrRegulatoryWindow:
    """UTR hits, alternate deltas, and bounded uORF observations."""

    window_id: str
    sequence_id: str
    chromosome: str
    start: int
    end: int
    region: str
    context_key: str
    reference_hits: tuple[UtrRegulatoryHit, ...]
    alternate_hits: tuple[UtrRegulatoryHit, ...]
    created_hits: tuple[UtrRegulatoryHit, ...]
    disrupted_hits: tuple[UtrRegulatoryHit, ...]
    upstream_orfs: tuple[UtrOpenReadingFrame, ...]
    state: SequenceAlphaState
    source_ids: tuple[str, ...]
    source_versions: tuple[str, ...]
    raw_hashes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class UtrRegulatoryScanReport:
    """UTR windows and issues from the regulatory scanner."""

    input_hash: str
    context_key: str | None
    state: SequenceAlphaState
    windows: tuple[UtrRegulatoryWindow, ...]
    issues: tuple[SequenceAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class UtrRegulatoryScanner:
    """Scan declared UTR elements and bounded uORF sequence patterns."""

    def scan(
        self,
        records: Iterable[Mapping[str, Any]],
        motifs: Iterable[UtrMotifDefinition],
        *,
        context_key: str | None = None,
        minimum_uorf_codons: int = 2,
    ) -> UtrRegulatoryScanReport:
        values = tuple(records)
        definitions = tuple(motifs)
        input_hash = content_hash(values)
        issues: list[SequenceAlphaIssue] = []
        windows: list[UtrRegulatoryWindow] = []
        context_mismatch = False
        if minimum_uorf_codons < 1:
            issue = SequenceAlphaIssue(
                "invalid_utr_parameter",
                "minimum uORF codons must be positive",
                input_hash,
                severity="error",
            )
            return self._report(input_hash, context_key, SequenceAlphaState.INVALID, (), (issue,))
        if not definitions:
            issue = SequenceAlphaIssue(
                "missing_utr_motifs",
                "at least one UTR motif definition is required",
                input_hash,
                severity="error",
            )
            return self._report(input_hash, context_key, SequenceAlphaState.INVALID, (), (issue,))
        for row_number, row in enumerate(values, start=1):
            if not isinstance(row, Mapping):
                issues.append(
                    SequenceAlphaIssue(
                        "row_not_object",
                        "UTR row must be an object",
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
                    SequenceAlphaIssue(
                        "context_mismatch",
                        "UTR sequence is outside the requested context",
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                    )
                )
                continue
            try:
                region = str(_value(row, "region", "utr_region")).lower()
                if region not in {"5utr", "3utr"}:
                    raise ValidationError("UTR record region must be 5utr or 3utr")
                reference_sequence = _sequence(row, "reference_sequence", "sequence", "seq")
                alternate_value = row.get("alternate_sequence")
                alternate_sequence = (
                    str(alternate_value).upper() if alternate_value not in {None, ""} else None
                )
                for sequence_value, label in (
                    ((reference_sequence, "reference"), (alternate_sequence, "alternate"))
                    if alternate_sequence is not None
                    else ((reference_sequence, "observed"),)
                ):
                    if sequence_value is not None and any(
                        base not in "ACGTN" for base in sequence_value.upper()
                    ):
                        raise ValidationError(f"{label} sequence must contain only A/C/G/T/N")
                chromosome, start, end = _coordinates(row, len(reference_sequence))
                applicable = tuple(item for item in definitions if item.region in {region, "both"})
                reference_hits = _utr_hits(
                    reference_sequence,
                    applicable,
                    region=region,
                    genomic_start=start,
                    allele="reference" if alternate_sequence is not None else "observed",
                )
                alternate_hits = (
                    _utr_hits(
                        alternate_sequence,
                        applicable,
                        region=region,
                        genomic_start=start,
                        allele="alternate",
                    )
                    if alternate_sequence is not None
                    else reference_hits
                )
                ref_by_signature = {hit.signature: hit for hit in reference_hits}
                alt_by_signature = {hit.signature: hit for hit in alternate_hits}
                created = tuple(
                    alt_by_signature[key]
                    for key in sorted(set(alt_by_signature) - set(ref_by_signature))
                )
                disrupted = tuple(
                    ref_by_signature[key]
                    for key in sorted(set(ref_by_signature) - set(alt_by_signature))
                )
                upstream_orfs = (
                    _find_upstream_orfs(reference_sequence, start, minimum_uorf_codons)
                    if region == "5utr"
                    else ()
                )
                state = (
                    SequenceAlphaState.AMBIGUOUS
                    if created and disrupted
                    else SequenceAlphaState.PARTIAL
                    if "N" in reference_sequence.upper()
                    or alternate_sequence is not None
                    and "N" in alternate_sequence
                    else SequenceAlphaState.SUPPORTED
                    if reference_hits or upstream_orfs
                    else SequenceAlphaState.ABSTAINED
                )
                sequence_id = str(
                    _value(row, "sequence_id", "utr_id", "id", "name", default=f"row-{row_number}")
                )
                body = {
                    "sequence_id": sequence_id,
                    "chromosome": chromosome,
                    "start": start,
                    "end": end,
                    "region": region,
                    "context_key": row_context or context_key or "unspecified",
                    "reference_hits": reference_hits,
                    "alternate_hits": alternate_hits,
                    "upstream_orfs": upstream_orfs,
                    "raw_hash": raw_hash,
                }
                windows.append(
                    UtrRegulatoryWindow(
                        window_id="utr:" + content_hash(body).split(":", 1)[1][:24],
                        sequence_id=sequence_id,
                        chromosome=chromosome,
                        start=start,
                        end=end,
                        region=region,
                        context_key=body["context_key"],
                        reference_hits=reference_hits,
                        alternate_hits=alternate_hits,
                        created_hits=created,
                        disrupted_hits=disrupted,
                        upstream_orfs=upstream_orfs,
                        state=state,
                        source_ids=tuple(sorted({item.source_id for item in applicable})),
                        source_versions=tuple(sorted({item.source_version for item in applicable})),
                        raw_hashes=(raw_hash,),
                        content_address=content_hash(body | {"state": state}),
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    SequenceAlphaIssue(
                        "invalid_utr_row",
                        str(exc),
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                        raw_record=dict(row),
                    )
                )
        if context_mismatch and not windows:
            state = SequenceAlphaState.OUT_OF_DOMAIN
        elif any(item.state == SequenceAlphaState.AMBIGUOUS for item in windows):
            state = SequenceAlphaState.AMBIGUOUS
        elif issues or any(item.state == SequenceAlphaState.PARTIAL for item in windows):
            state = SequenceAlphaState.PARTIAL
        elif not windows:
            state = SequenceAlphaState.ABSTAINED
        else:
            state = SequenceAlphaState.SUPPORTED
        return self._report(input_hash, context_key, state, tuple(windows), tuple(issues))

    @staticmethod
    def _report(
        input_hash: str,
        context_key: str | None,
        state: SequenceAlphaState,
        windows: tuple[UtrRegulatoryWindow, ...],
        issues: tuple[SequenceAlphaIssue, ...],
    ) -> UtrRegulatoryScanReport:
        return UtrRegulatoryScanReport(
            input_hash=input_hash,
            context_key=context_key,
            state=state,
            windows=windows,
            issues=issues,
            warnings=(
                (
                    "UTR motifs and uORF patterns are sequence observations, not translation "
                    "estimates."
                ),
                (
                    "A UTR hit does not establish RNA binding, stability, or allele-specific "
                    "expression."
                ),
            ),
            content_address=content_hash(
                {"input_hash": input_hash, "state": state, "windows": windows, "issues": issues}
            ),
        )


@dataclass(frozen=True, slots=True)
class PromoterMotifDefinition:
    """Declared core-promoter motif."""

    motif_id: str
    name: str
    consensus: str
    element_kind: str
    source_id: str
    source_version: str
    threshold: float = 0.8
    strand_aware: bool = True

    def __post_init__(self) -> None:
        for name in (
            "motif_id",
            "name",
            "consensus",
            "element_kind",
            "source_id",
            "source_version",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if any(base not in _IUPAC for base in self.consensus.upper()):
            raise ValidationError("promoter consensus contains unsupported IUPAC symbols")
        if not 0 < self.threshold <= 1:
            raise ValidationError("promoter motif threshold must be between zero and one")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PromoterMotifHit:
    """One core-promoter motif match."""

    motif_id: str
    name: str
    element_kind: str
    start: int
    end: int
    strand: str
    matched_sequence: str
    score: float
    source_id: str
    source_version: str
    content_address: str

    @property
    def signature(self) -> tuple[str, str, int, int, str]:
        return (self.motif_id, self.strand, self.start, self.end, self.matched_sequence)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PromoterGrammarRule:
    """Declared spacing and orientation relationship between two motifs."""

    rule_id: str
    motif_a: str
    motif_b: str
    minimum_spacing: int
    maximum_spacing: int
    allowed_orientations: tuple[str, ...] = ("same", "opposite", "any")
    weight: float = 1.0
    source_id: str = "promoter-grammar"
    source_version: str = "unspecified"

    def __post_init__(self) -> None:
        for name in (
            "rule_id",
            "motif_a",
            "motif_b",
            "source_id",
            "source_version",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if self.minimum_spacing < 0 or self.maximum_spacing < self.minimum_spacing:
            raise ValidationError("promoter grammar spacing bounds are invalid")
        if not set(self.allowed_orientations) <= {"same", "opposite", "any"}:
            raise ValidationError("promoter grammar orientation is unsupported")
        if not isfinite(self.weight) or self.weight <= 0:
            raise ValidationError("promoter grammar weight must be positive and finite")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PromoterGrammarPair:
    """One compatible pair under a declared promoter rule."""

    rule_id: str
    motif_a_hit: PromoterMotifHit
    motif_b_hit: PromoterMotifHit
    spacing: int
    orientation_relation: str
    pair_score: float
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PromoterGrammarEvaluation:
    """One promoter's grammar coverage and all compatible pairs."""

    promoter_id: str
    chromosome: str
    start: int
    end: int
    context_key: str
    hits: tuple[PromoterMotifHit, ...]
    compatible_pairs: tuple[PromoterGrammarPair, ...]
    matched_rule_ids: tuple[str, ...]
    unmatched_rule_ids: tuple[str, ...]
    weighted_coverage: float
    state: SequenceAlphaState
    source_ids: tuple[str, ...]
    source_versions: tuple[str, ...]
    raw_hash: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PromoterCoreGrammarReport:
    """Promoter grammar evaluations and source-addressable issues."""

    input_hash: str
    context_key: str | None
    state: SequenceAlphaState
    evaluations: tuple[PromoterGrammarEvaluation, ...]
    issues: tuple[SequenceAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class PromoterCoreGrammarModel:
    """Evaluate declared core-promoter grammar rules over observed sequences."""

    def evaluate(
        self,
        records: Iterable[Mapping[str, Any]],
        motifs: Iterable[PromoterMotifDefinition],
        rules: Iterable[PromoterGrammarRule],
        *,
        context_key: str | None = None,
        minimum_coverage: float = 0.5,
    ) -> PromoterCoreGrammarReport:
        values = tuple(records)
        definitions = tuple(motifs)
        grammar = tuple(rules)
        input_hash = content_hash(values)
        issues: list[SequenceAlphaIssue] = []
        evaluations: list[PromoterGrammarEvaluation] = []
        context_mismatch = False
        if not definitions or not grammar:
            issue = SequenceAlphaIssue(
                "missing_promoter_contract",
                "promoter grammar requires motif definitions and rules",
                input_hash,
                severity="error",
            )
            return self._report(input_hash, context_key, SequenceAlphaState.INVALID, (), (issue,))
        if not 0 < minimum_coverage <= 1:
            issue = SequenceAlphaIssue(
                "invalid_promoter_coverage",
                "minimum promoter coverage must be between zero and one",
                input_hash,
                severity="error",
            )
            return self._report(input_hash, context_key, SequenceAlphaState.INVALID, (), (issue,))
        motif_ids = {item.motif_id for item in definitions}
        for rule in grammar:
            if rule.motif_a not in motif_ids or rule.motif_b not in motif_ids:
                issue = SequenceAlphaIssue(
                    "rule_references_unknown_motif",
                    f"promoter rule {rule.rule_id} references an undefined motif",
                    content_hash(rule),
                    source_id=rule.source_id,
                    severity="error",
                    raw_record=rule.to_dict(),
                )
                issues.append(issue)
        if issues:
            return self._report(
                input_hash, context_key, SequenceAlphaState.INVALID, (), tuple(issues)
            )
        for row_number, row in enumerate(values, start=1):
            if not isinstance(row, Mapping):
                issues.append(
                    SequenceAlphaIssue(
                        "row_not_object",
                        "promoter row must be an object",
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
                    SequenceAlphaIssue(
                        "context_mismatch",
                        "promoter sequence is outside the requested context",
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                    )
                )
                continue
            try:
                sequence = _sequence(row, "sequence", "promoter_sequence", "seq")
                if any(base not in "ACGTN" for base in sequence.upper()):
                    raise ValidationError("promoter sequence must contain only A/C/G/T/N")
                chromosome, start, end = _coordinates(row, len(sequence))
                hits = _promoter_hits(sequence, definitions, genomic_start=start)
                pairs: list[PromoterGrammarPair] = []
                matched_rules: set[str] = set()
                for rule in grammar:
                    for hit_a in hits:
                        if hit_a.motif_id != rule.motif_a:
                            continue
                        for hit_b in hits:
                            if hit_b.motif_id != rule.motif_b or hit_a is hit_b:
                                continue
                            spacing = max(0, hit_b.start - hit_a.end - 1)
                            relation = "same" if hit_a.strand == hit_b.strand else "opposite"
                            if not rule.minimum_spacing <= spacing <= rule.maximum_spacing:
                                continue
                            if (
                                "any" not in rule.allowed_orientations
                                and relation not in rule.allowed_orientations
                            ):
                                continue
                            matched_rules.add(rule.rule_id)
                            body = {
                                "rule_id": rule.rule_id,
                                "a": hit_a.signature,
                                "b": hit_b.signature,
                                "spacing": spacing,
                            }
                            pairs.append(
                                PromoterGrammarPair(
                                    rule_id=rule.rule_id,
                                    motif_a_hit=hit_a,
                                    motif_b_hit=hit_b,
                                    spacing=spacing,
                                    orientation_relation=relation,
                                    pair_score=round(
                                        rule.weight * mean((hit_a.score, hit_b.score)), 9
                                    ),
                                    content_address=content_hash(body),
                                )
                            )
                total_weight = sum(rule.weight for rule in grammar)
                matched_weight = sum(
                    rule.weight for rule in grammar if rule.rule_id in matched_rules
                )
                coverage = round(matched_weight / total_weight, 9) if total_weight else 0.0
                unmatched = tuple(
                    rule.rule_id for rule in grammar if rule.rule_id not in matched_rules
                )
                if not pairs:
                    state = SequenceAlphaState.ABSTAINED
                elif len({pair.rule_id for pair in pairs}) < len(pairs):
                    state = SequenceAlphaState.AMBIGUOUS
                elif "N" in sequence.upper():
                    state = SequenceAlphaState.PARTIAL
                elif coverage >= minimum_coverage:
                    state = SequenceAlphaState.SUPPORTED
                else:
                    state = SequenceAlphaState.PARTIAL
                promoter_id = str(
                    _value(
                        row, "promoter_id", "sequence_id", "id", "name", default=f"row-{row_number}"
                    )
                )
                body = {
                    "promoter_id": promoter_id,
                    "chromosome": chromosome,
                    "start": start,
                    "end": end,
                    "context_key": row_context or context_key or "unspecified",
                    "hits": hits,
                    "pairs": pairs,
                    "coverage": coverage,
                }
                evaluations.append(
                    PromoterGrammarEvaluation(
                        promoter_id=promoter_id,
                        chromosome=chromosome,
                        start=start,
                        end=end,
                        context_key=body["context_key"],
                        hits=hits,
                        compatible_pairs=tuple(pairs),
                        matched_rule_ids=tuple(sorted(matched_rules)),
                        unmatched_rule_ids=unmatched,
                        weighted_coverage=coverage,
                        state=state,
                        source_ids=tuple(sorted({item.source_id for item in definitions})),
                        source_versions=tuple(
                            sorted({item.source_version for item in definitions})
                        ),
                        raw_hash=raw_hash,
                        content_address=content_hash(body | {"state": state}),
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    SequenceAlphaIssue(
                        "invalid_promoter_row",
                        str(exc),
                        raw_hash,
                        row_number,
                        source_id=_source_id(row),
                        severity="error",
                        raw_record=dict(row),
                    )
                )
        if context_mismatch and not evaluations:
            state = SequenceAlphaState.OUT_OF_DOMAIN
        elif any(item.state == SequenceAlphaState.AMBIGUOUS for item in evaluations):
            state = SequenceAlphaState.AMBIGUOUS
        elif issues or any(item.state == SequenceAlphaState.PARTIAL for item in evaluations):
            state = SequenceAlphaState.PARTIAL
        elif not evaluations or all(
            item.state == SequenceAlphaState.ABSTAINED for item in evaluations
        ):
            state = SequenceAlphaState.ABSTAINED
        else:
            state = SequenceAlphaState.SUPPORTED
        return self._report(input_hash, context_key, state, tuple(evaluations), tuple(issues))

    @staticmethod
    def _report(
        input_hash: str,
        context_key: str | None,
        state: SequenceAlphaState,
        evaluations: tuple[PromoterGrammarEvaluation, ...],
        issues: tuple[SequenceAlphaIssue, ...],
    ) -> PromoterCoreGrammarReport:
        return PromoterCoreGrammarReport(
            input_hash=input_hash,
            context_key=context_key,
            state=state,
            evaluations=evaluations,
            issues=issues,
            warnings=(
                "Promoter grammar coverage is a declared rule comparison, not an activity model.",
                "Compatible motif pairs do not establish transcription initiation or causality.",
            ),
            content_address=content_hash(
                {
                    "input_hash": input_hash,
                    "state": state,
                    "evaluations": evaluations,
                    "issues": issues,
                }
            ),
        )


_IUPAC: dict[str, frozenset[str]] = {
    "A": frozenset("A"),
    "C": frozenset("C"),
    "G": frozenset("G"),
    "T": frozenset("T"),
    "R": frozenset("AG"),
    "Y": frozenset("CT"),
    "S": frozenset("GC"),
    "W": frozenset("AT"),
    "K": frozenset("GT"),
    "M": frozenset("AC"),
    "B": frozenset("CGT"),
    "D": frozenset("AGT"),
    "H": frozenset("ACT"),
    "V": frozenset("ACG"),
    "N": frozenset("ACGT"),
}


def _nucleosome_features(sequence: str, period: int) -> tuple[float, float, float]:
    informative = [base for base in sequence if base != "N"]
    if not informative:
        return 0.0, 0.0, 0.0
    gc_fraction = (informative.count("G") + informative.count("C")) / len(informative)
    gc_balance = 1 - min(1.0, abs(gc_fraction - 0.5) * 2)
    if len(sequence) < 2:
        return gc_fraction, 0.0, gc_balance
    phase_scores: list[float] = []
    for phase in range(period):
        pairs = [
            sequence[index : index + 2]
            for index in range(phase, len(sequence) - 1, period)
            if "N" not in sequence[index : index + 2]
        ]
        if not pairs:
            continue
        ww_ss = sum(pair in {"AA", "TT", "CC", "GG"} for pair in pairs)
        phase_scores.append(ww_ss / len(pairs))
    return gc_fraction, max(phase_scores, default=0.0), gc_balance


def _splice_hits(
    sequence: str,
    definitions: Sequence[SpliceMotifDefinition],
    *,
    genomic_start: int,
    allele: str,
) -> tuple[SpliceMotifHit, ...]:
    hits: list[SpliceMotifHit] = []
    for definition in definitions:
        for start, end, strand, matched, score in _scan_iupac(
            sequence,
            definition.consensus,
            genomic_start=genomic_start,
            strand_aware=definition.strand_aware,
            threshold=definition.threshold,
        ):
            body = {
                "motif_id": definition.motif_id,
                "start": start,
                "end": end,
                "strand": strand,
                "matched": matched,
                "allele": allele,
            }
            hits.append(
                SpliceMotifHit(
                    motif_id=definition.motif_id,
                    name=definition.name,
                    role=definition.role,
                    start=start,
                    end=end,
                    strand=strand,
                    matched_sequence=matched,
                    score=round(score, 9),
                    allele=allele,
                    source_id=definition.source_id,
                    source_version=definition.source_version,
                    content_address=content_hash(body),
                )
            )
    return tuple(sorted(hits, key=lambda item: item.signature))


def _utr_hits(
    sequence: str,
    definitions: Sequence[UtrMotifDefinition],
    *,
    region: str,
    genomic_start: int,
    allele: str,
) -> tuple[UtrRegulatoryHit, ...]:
    hits: list[UtrRegulatoryHit] = []
    for definition in definitions:
        for start, end, strand, matched, score in _scan_iupac(
            sequence,
            definition.consensus,
            genomic_start=genomic_start,
            strand_aware=definition.strand_aware,
            threshold=definition.threshold,
        ):
            body = {
                "motif_id": definition.motif_id,
                "start": start,
                "end": end,
                "strand": strand,
                "matched": matched,
                "allele": allele,
                "region": region,
            }
            hits.append(
                UtrRegulatoryHit(
                    motif_id=definition.motif_id,
                    name=definition.name,
                    element_kind=definition.element_kind,
                    region=region,
                    start=start,
                    end=end,
                    strand=strand,
                    matched_sequence=matched,
                    score=round(score, 9),
                    allele=allele,
                    source_id=definition.source_id,
                    source_version=definition.source_version,
                    content_address=content_hash(body),
                )
            )
    return tuple(sorted(hits, key=lambda item: item.signature))


def _promoter_hits(
    sequence: str,
    definitions: Sequence[PromoterMotifDefinition],
    *,
    genomic_start: int,
) -> tuple[PromoterMotifHit, ...]:
    hits: list[PromoterMotifHit] = []
    for definition in definitions:
        for start, end, strand, matched, score in _scan_iupac(
            sequence,
            definition.consensus,
            genomic_start=genomic_start,
            strand_aware=definition.strand_aware,
            threshold=definition.threshold,
        ):
            body = {
                "motif_id": definition.motif_id,
                "start": start,
                "end": end,
                "strand": strand,
                "matched": matched,
            }
            hits.append(
                PromoterMotifHit(
                    motif_id=definition.motif_id,
                    name=definition.name,
                    element_kind=definition.element_kind,
                    start=start,
                    end=end,
                    strand=strand,
                    matched_sequence=matched,
                    score=round(score, 9),
                    source_id=definition.source_id,
                    source_version=definition.source_version,
                    content_address=content_hash(body),
                )
            )
    return tuple(sorted(hits, key=lambda item: item.signature))


def _scan_iupac(
    sequence: str,
    consensus: str,
    *,
    genomic_start: int,
    strand_aware: bool,
    threshold: float,
) -> tuple[tuple[int, int, str, str, float], ...]:
    normalized = sequence.upper()
    pattern = consensus.upper()
    reverse = _reverse_complement(pattern)
    results: list[tuple[int, int, str, str, float]] = []
    for offset in range(0, len(normalized) - len(pattern) + 1):
        window = normalized[offset : offset + len(pattern)]
        score = _match_score(window, pattern)
        if score >= threshold:
            results.append(
                (
                    genomic_start + offset,
                    genomic_start + offset + len(pattern) - 1,
                    "+",
                    window,
                    score,
                )
            )
        if strand_aware and reverse != pattern:
            reverse_score = _match_score(window, reverse)
            if reverse_score >= threshold:
                results.append(
                    (
                        genomic_start + offset,
                        genomic_start + offset + len(pattern) - 1,
                        "-",
                        window,
                        reverse_score,
                    )
                )
    return tuple(results)


def _match_score(sequence: str, consensus: str) -> float:
    if len(sequence) != len(consensus) or not sequence:
        return 0.0
    return sum(
        base in _IUPAC.get(symbol, frozenset())
        for base, symbol in zip(sequence, consensus, strict=True)
    ) / len(consensus)


def _find_upstream_orfs(
    sequence: str, genomic_start: int, minimum_codons: int
) -> tuple[UtrOpenReadingFrame, ...]:
    normalized = sequence.upper()
    results: list[UtrOpenReadingFrame] = []
    for offset in range(0, len(normalized) - 2):
        if normalized[offset : offset + 3] != "ATG":
            continue
        for stop_offset in range(offset + 3, len(normalized) - 2, 3):
            stop = normalized[stop_offset : stop_offset + 3]
            if stop not in {"TAA", "TAG", "TGA"}:
                continue
            codon_length = (stop_offset - offset) // 3 + 1
            if codon_length >= minimum_codons:
                start = genomic_start + offset
                end = genomic_start + stop_offset + 2
                body = {"start": start, "end": end, "frame": offset % 3, "stop": stop}
                results.append(
                    UtrOpenReadingFrame(
                        start=start,
                        end=end,
                        frame=offset % 3,
                        stop_codon=stop,
                        codon_length=codon_length,
                        content_address=content_hash(body),
                    )
                )
            break
    return tuple(results)


def _reverse_complement(sequence: str) -> str:
    complements = {
        "A": "T",
        "C": "G",
        "G": "C",
        "T": "A",
        "R": "Y",
        "Y": "R",
        "S": "S",
        "W": "W",
        "K": "M",
        "M": "K",
        "B": "V",
        "D": "H",
        "H": "D",
        "V": "B",
        "N": "N",
    }
    return "".join(complements[base] for base in reversed(sequence.upper()))


def _sequence(row: Mapping[str, Any], *keys: str) -> str:
    value = _value(row, *keys)
    sequence = str(value).strip().upper()
    if not sequence:
        raise ValidationError("sequence must not be empty")
    return sequence


def _coordinates(row: Mapping[str, Any], length: int) -> tuple[str, int, int]:
    chromosome = str(row.get("chromosome", row.get("chrom", row.get("contig", "unknown"))))
    start = int(row.get("start", row.get("window_start", 1)))
    end = int(row.get("end", start + length - 1))
    if start < 1 or end < start:
        raise ValidationError("sequence interval must satisfy 1 <= start <= end")
    return chromosome, start, end


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


def _context(row: Mapping[str, Any]) -> str | None:
    value = row.get("context_key", row.get("context"))
    return str(value) if value not in {None, "", "."} else None


def _source_id(row: Mapping[str, Any]) -> str:
    return str(row.get("source_id", row.get("source", "unspecified"))) or "unspecified"


def _source_version(row: Mapping[str, Any]) -> str:
    return str(row.get("source_version", row.get("version", "unspecified"))) or "unspecified"


def _raw_hash(row: Mapping[str, Any]) -> str:
    return content_hash(dict(row))


__all__ = [
    "NucleosomePropensityReport",
    "NucleosomePropensityWindow",
    "NucleosomeSequencePropensityModel",
    "PromoterCoreGrammarReport",
    "PromoterGrammarEvaluation",
    "PromoterGrammarPair",
    "PromoterGrammarRule",
    "PromoterMotifDefinition",
    "PromoterMotifHit",
    "SequenceAlphaIssue",
    "SequenceAlphaState",
    "SpliceMotifDefinition",
    "SpliceMotifHit",
    "SpliceRegulatoryNoncodingScanner",
    "SpliceRegulatoryScanReport",
    "SpliceRegulatoryWindow",
    "UtrMotifDefinition",
    "UtrOpenReadingFrame",
    "UtrRegulatoryHit",
    "UtrRegulatoryScanReport",
    "UtrRegulatoryScanner",
    "UtrRegulatoryWindow",
]
