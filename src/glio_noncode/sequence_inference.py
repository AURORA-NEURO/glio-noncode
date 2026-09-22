"""Deterministic sequence and motif inference over retrieved reference windows."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from itertools import islice
from typing import Any

from .data_sources import SequenceSlice
from .errors import ValidationError
from .models import (
    EvidenceClaim,
    EvidenceState,
    EvidenceTier,
    ReferenceContext,
    VariantIdentity,
    VariantKind,
)
from .serialization import content_hash, jsonable
from .variant_genotype import phased_alternate_haplotype_indices

MAX_MOTIF_DEFINITIONS = 2_048
# Keep a standalone ceiling while allowing Atlas to enforce its narrower
# public-surface limit (currently 1,024) when motifs enter a retrieval run.
MAX_MOTIF_PATTERN_LENGTH = 4_096
MAX_MOTIF_SCAN_SEQUENCE_BP = 10_000_000
MAX_MOTIF_SCAN_BASE_COMPARISONS = 50_000_000
MAX_MOTIF_HITS = 50_000
MAX_MOTIF_HIT_SEQUENCE_BASES = 10_000_000
MAX_HAPLOTYPE_VARIANTS = 1_024
MAX_HAPLOTYPE_MOTIF_DELTAS = 50_000
MAX_PHASE_SET_LABEL_LENGTH = 256


def _validate_phase_set_label(phase_set: str) -> None:
    if type(phase_set) is not str or not phase_set.strip():
        raise ValidationError("phase_set must be non-empty text")
    if (
        len(phase_set) > MAX_PHASE_SET_LABEL_LENGTH
        or any(ord(character) < 32 or ord(character) == 127 for character in phase_set)
    ):
        raise ValidationError("phase_set exceeds its text boundary")
    if phase_set.strip().casefold() in {".", "unknown", "unphased", "unspecified"}:
        raise ValidationError("phase_set must identify a resolved phase block")


def _validate_phased_sample_id(sample_id: str) -> None:
    if (
        type(sample_id) is not str
        or not sample_id.strip()
        or sample_id.strip().casefold() in {".", "unknown", "unspecified"}
    ):
        raise ValidationError("phased variants require an explicit sample_id")


class SequenceAnalysisState(StrEnum):
    """Outcome of applying an identity to a retrieved sequence."""

    SUPPORTED = "supported"
    REFERENCE_MISMATCH = "reference_mismatch"
    OUT_OF_WINDOW = "out_of_window"
    ABSTAINED = "abstained"


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


@dataclass(frozen=True, slots=True)
class MotifDefinition:
    """Small transparent motif pattern with IUPAC bases."""

    motif_id: str
    name: str
    pattern: str
    source_id: str = "curated_motif_fixture"

    def __post_init__(self) -> None:
        for name in ("motif_id", "name", "pattern", "source_id"):
            value = getattr(self, name)
            if type(value) is not str or not value.strip():
                raise ValidationError(f"{name} must be a non-empty string")
        if len(self.pattern) > MAX_MOTIF_PATTERN_LENGTH:
            raise ValidationError("motif pattern exceeds the maximum length")
        if any(base not in _IUPAC for base in self.pattern.upper()):
            raise ValidationError(f"motif pattern contains unsupported IUPAC bases: {self.pattern}")

    @property
    def normalized_pattern(self) -> str:
        return self.pattern.upper()

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _bounded_motif_definitions(
    motifs: Iterable[MotifDefinition],
) -> tuple[MotifDefinition, ...]:
    try:
        motif_iterator = iter(motifs)
    except TypeError as exc:
        raise ValidationError("motif scanner motifs must be iterable") from exc
    motif_list = tuple(islice(motif_iterator, MAX_MOTIF_DEFINITIONS + 1))
    if len(motif_list) > MAX_MOTIF_DEFINITIONS:
        raise ValidationError("motif scanner motif count exceeds the maximum")
    if any(type(motif) is not MotifDefinition for motif in motif_list):
        raise ValidationError("motif scanner requires MotifDefinition instances")
    return motif_list


@dataclass(frozen=True, slots=True)
class MotifHit:
    """A motif match in one sequence representation."""

    motif_id: str
    name: str
    start: int
    end: int
    strand: str
    matched_sequence: str
    source_id: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.motif_id, "motif_id"),
            (self.name, "motif name"),
            (self.matched_sequence, "matched_sequence"),
            (self.source_id, "motif source_id"),
        ):
            if type(value) is not str or not value.strip():
                raise ValidationError(f"{name} must be a non-empty string")
        if type(self.start) is not int or type(self.end) is not int:
            raise ValidationError("motif hit interval coordinates must be integers")
        if self.start < 1 or self.end < self.start:
            raise ValidationError("motif hit interval is invalid")
        if type(self.strand) is not str or self.strand not in {"+", "-"}:
            raise ValidationError("motif hit strand must be + or -")

    @property
    def signature(self) -> tuple[str, str, int, int, str]:
        return (self.motif_id, self.strand, self.start, self.end, self.matched_sequence)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PhasedVariantIdentity:
    """One literal variant assigned to a caller-declared phased haplotype."""

    variant: VariantIdentity
    phase_set: str
    haplotype_index: int

    def __post_init__(self) -> None:
        if type(self.variant) is not VariantIdentity:
            raise ValidationError("phased variant must contain a VariantIdentity")
        _validate_phase_set_label(self.phase_set)
        _validate_phased_sample_id(self.variant.sample_id)
        if type(self.haplotype_index) is not int or not 1 <= self.haplotype_index <= 32:
            raise ValidationError("haplotype_index must be an integer from 1 through 32")

    @classmethod
    def from_vcf_call(
        cls,
        variant: VariantIdentity,
        *,
        genotype: object,
        phase_set: str,
        alternate_count: int,
        alternate_index: int,
    ) -> tuple[PhasedVariantIdentity, ...]:
        """Build assignments from an explicit VCF GT/PS for the selected ALT.

        The supplied ``variant`` must represent ``alternate_index`` in the
        source record. The returned tuple has one entry for each copy of that
        ALT. An empty tuple means the complete phased call does not carry it;
        an unphased or incomplete call is rejected rather than inferred.
        """

        if type(variant) is not VariantIdentity:
            raise ValidationError("VCF phased-call input must contain a VariantIdentity")
        _validate_phase_set_label(phase_set)
        _validate_phased_sample_id(variant.sample_id)
        haplotypes = phased_alternate_haplotype_indices(
            genotype,
            alternate_count,
            alternate_index,
        )
        if haplotypes is None:
            raise ValidationError(
                "VCF GT must be fully called and explicitly phased with '|' separators"
            )
        return tuple(
            cls(variant=variant, phase_set=phase_set, haplotype_index=haplotype_index)
            for haplotype_index in haplotypes
        )


class HaplotypeMotifChange(StrEnum):
    """Direction of a motif change between reference and alternate haplotypes."""

    CREATED = "created"
    DISRUPTED = "disrupted"


@dataclass(frozen=True, slots=True)
class HaplotypeMotifDelta:
    """Motif delta with reference and haplotype coordinates kept distinct."""

    change: HaplotypeMotifChange
    motif_id: str
    name: str
    strand: str
    matched_sequence: str
    source_id: str
    reference_interval: tuple[str, int, int] | None
    haplotype_interval: tuple[int, int] | None
    variant_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.change) is not HaplotypeMotifChange:
            raise ValidationError("haplotype motif change must be a HaplotypeMotifChange")
        for value, label in (
            (self.motif_id, "motif_id"),
            (self.name, "motif name"),
            (self.matched_sequence, "matched_sequence"),
            (self.source_id, "motif source_id"),
        ):
            if type(value) is not str or not value.strip():
                raise ValidationError(f"{label} must be non-empty text")
        if type(self.strand) is not str or self.strand not in {"+", "-"}:
            raise ValidationError("haplotype motif strand must be + or -")
        if self.reference_interval is not None:
            if (
                type(self.reference_interval) is not tuple
                or len(self.reference_interval) != 3
                or type(self.reference_interval[0]) is not str
                or not self.reference_interval[0]
                or type(self.reference_interval[1]) is not int
                or type(self.reference_interval[2]) is not int
                or self.reference_interval[1] < 1
                or self.reference_interval[2] < self.reference_interval[1]
            ):
                raise ValidationError("reference_interval must be a valid genomic interval")
        if self.haplotype_interval is not None and (
            type(self.haplotype_interval) is not tuple
            or len(self.haplotype_interval) != 2
            or type(self.haplotype_interval[0]) is not int
            or type(self.haplotype_interval[1]) is not int
            or self.haplotype_interval[0] < 1
            or self.haplotype_interval[1] < self.haplotype_interval[0]
        ):
            raise ValidationError("haplotype_interval must be a valid 1-based interval")
        if self.change is HaplotypeMotifChange.CREATED and self.haplotype_interval is None:
            raise ValidationError("created motif deltas require a haplotype interval")
        if self.change is HaplotypeMotifChange.DISRUPTED and self.reference_interval is None:
            raise ValidationError("disrupted motif deltas require a reference interval")
        if not isinstance(self.variant_ids, tuple) or any(
            type(variant_id) is not str or not variant_id for variant_id in self.variant_ids
        ):
            raise ValidationError("motif delta variant_ids must be a tuple of non-empty strings")
        if len(self.variant_ids) != len(set(self.variant_ids)):
            raise ValidationError("motif delta variant_ids must be unique")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class HaplotypeSequenceAnalysisResult:
    """Content-addressed motif comparison for one explicitly phased sequence."""

    phase_set: str
    haplotype_index: int
    variant_ids: tuple[str, ...]
    state: SequenceAnalysisState
    source_id: str
    reference_interval: tuple[str, int, int]
    reference_sequence_hash: str
    alternate_sequence_hash: str | None
    alternate_length_delta: int | None
    gc_fraction_reference: float | None
    gc_fraction_alternate: float | None
    motif_set_hash: str
    created_hits: tuple[HaplotypeMotifDelta, ...]
    disrupted_hits: tuple[HaplotypeMotifDelta, ...]
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    @property
    def motif_delta_count(self) -> int:
        return len(self.created_hits) + len(self.disrupted_hits)


@dataclass(frozen=True, slots=True)
class _HaplotypeCoordinateBlock:
    """Map a contiguous alternate-sequence block to reference coordinates."""

    alternate_start: int
    alternate_end: int
    reference_start: int | None
    variant_id: str | None


@dataclass(frozen=True, slots=True)
class SequenceAnalysisResult:
    """Reference/alternate sequence comparison with motif delta and limits."""

    variant_id: str
    state: SequenceAnalysisState
    source_id: str
    reference_interval: tuple[str, int, int]
    reference_sequence_hash: str | None
    alternate_sequence_hash: str | None
    reference_allele_observed: str | None
    alternate_length_delta: int | None
    gc_fraction_reference: float | None
    gc_fraction_alternate: float | None
    created_hits: tuple[MotifHit, ...]
    disrupted_hits: tuple[MotifHit, ...]
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    @property
    def motif_delta_count(self) -> int:
        return len(self.created_hits) + len(self.disrupted_hits)

    def to_claim(self, *, context: ReferenceContext, edge_id: str) -> EvidenceClaim:
        """Create a computed claim with no probabilistic effect score."""

        if self.state == SequenceAnalysisState.SUPPORTED:
            claim_state = EvidenceState.SUPPORTED
            confidence = 0.8
        elif self.state == SequenceAnalysisState.REFERENCE_MISMATCH:
            claim_state = EvidenceState.ABSTAINED
            confidence = 0.0
        elif self.state == SequenceAnalysisState.OUT_OF_WINDOW:
            claim_state = EvidenceState.OUT_OF_DOMAIN
            confidence = 0.0
        else:
            claim_state = EvidenceState.ABSTAINED
            confidence = 0.0
        return EvidenceClaim(
            evidence_id=f"{self.content_address}:sequence",
            edge_id=edge_id,
            source_id=self.source_id,
            channel="motif_delta",
            state=claim_state,
            tier=EvidenceTier.COMPUTED,
            score=None,
            confidence=confidence,
            context=context,
            summary=(
                f"Sequence comparison for {self.variant_id}: "
                f"{len(self.created_hits)} motif hits created and "
                f"{len(self.disrupted_hits)} disrupted; no effect probability inferred."
            ),
            payload={"analysis": self.to_dict()},
            produced_by="deterministic_sequence_inference",
        )


class MotifScanner:
    """Scan both strands using only explicit IUPAC matching."""

    def scan(
        self,
        sequence: str,
        *,
        genomic_start: int,
        motifs: Iterable[MotifDefinition],
    ) -> tuple[MotifHit, ...]:
        if type(sequence) is not str:
            raise ValidationError("motif scanner sequence must be a string")
        if len(sequence) > MAX_MOTIF_SCAN_SEQUENCE_BP:
            raise ValidationError(
                "motif scanner sequence exceeds the "
                f"{MAX_MOTIF_SCAN_SEQUENCE_BP}-base limit"
            )
        normalized = sequence.upper()
        if not normalized or any(base not in "ACGTN" for base in normalized):
            raise ValidationError("motif scanner sequence must contain only A/C/G/T/N")
        if type(genomic_start) is not int or genomic_start < 1:
            raise ValidationError("motif scanner genomic_start must be positive")
        motif_list = _bounded_motif_definitions(motifs)
        scan_work = 0
        for motif in motif_list:
            pattern = motif.normalized_pattern
            candidate_starts = len(normalized) - len(pattern) + 1
            if candidate_starts <= 0:
                continue
            reverse_pattern = _reverse_complement_iupac(pattern)
            strand_count = 1 if reverse_pattern == pattern else 2
            scan_work += candidate_starts * len(pattern) * strand_count
            if scan_work > MAX_MOTIF_SCAN_BASE_COMPARISONS:
                raise ValidationError(
                    "motif scan exceeds the "
                    f"{MAX_MOTIF_SCAN_BASE_COMPARISONS}-base-comparison limit"
                )
        hits: list[MotifHit] = []
        hit_sequence_bases = 0

        def append_hit(
            motif: MotifDefinition,
            *,
            offset: int,
            strand: str,
            window: str,
        ) -> None:
            nonlocal hit_sequence_bases
            if len(hits) >= MAX_MOTIF_HITS:
                raise ValidationError(f"motif scan exceeds the {MAX_MOTIF_HITS}-hit limit")
            next_hit_sequence_bases = hit_sequence_bases + len(window)
            if next_hit_sequence_bases > MAX_MOTIF_HIT_SEQUENCE_BASES:
                raise ValidationError(
                    "motif scan hit sequences exceed the "
                    f"{MAX_MOTIF_HIT_SEQUENCE_BASES}-base output limit"
                )
            hits.append(
                MotifHit(
                    motif_id=motif.motif_id,
                    name=motif.name,
                    start=genomic_start + offset,
                    end=genomic_start + offset + len(window) - 1,
                    strand=strand,
                    matched_sequence=window,
                    source_id=motif.source_id,
                )
            )
            hit_sequence_bases = next_hit_sequence_bases

        for motif in motif_list:
            pattern = motif.normalized_pattern
            reverse_pattern = _reverse_complement_iupac(pattern)
            for offset in range(0, len(normalized) - len(pattern) + 1):
                window = normalized[offset : offset + len(pattern)]
                if _matches(window, pattern):
                    append_hit(motif, offset=offset, strand="+", window=window)
                if reverse_pattern != pattern and _matches(window, reverse_pattern):
                    append_hit(motif, offset=offset, strand="-", window=window)
        return tuple(sorted(hits, key=lambda hit: hit.signature))


class SequenceInference:
    """Apply a variant to a real reference window and compare motif hits."""

    def __init__(self, *, scanner: MotifScanner | None = None) -> None:
        self.scanner = scanner or MotifScanner()

    def analyze(
        self,
        variant: VariantIdentity,
        sequence: SequenceSlice,
        *,
        motifs: Iterable[MotifDefinition] = (),
    ) -> SequenceAnalysisResult:
        if type(variant) is not VariantIdentity:
            raise ValidationError("sequence analysis variant must be a VariantIdentity")
        if type(sequence) is not SequenceSlice:
            raise ValidationError("sequence analysis input must be a SequenceSlice")
        if _genome_build_key(variant.genome_build) != _genome_build_key(sequence.assembly):
            return self._abstention(
                variant,
                sequence,
                SequenceAnalysisState.ABSTAINED,
                "variant and sequence genome builds do not match",
            )
        if variant.kind not in {VariantKind.SNV, VariantKind.INDEL}:
            return self._abstention(
                variant,
                sequence,
                SequenceAnalysisState.ABSTAINED,
                "sequence inference supports only literal SNV and indel alleles",
            )
        reference = variant.reference.upper()
        alternate = variant.alternate.upper()
        if (
            not reference
            or not alternate
            or any(base not in "ACGT" for base in reference + alternate)
        ):
            return self._abstention(
                variant,
                sequence,
                SequenceAnalysisState.ABSTAINED,
                "sequence inference requires unambiguous literal A/C/G/T alleles",
            )
        if reference == alternate:
            return self._abstention(
                variant,
                sequence,
                SequenceAnalysisState.ABSTAINED,
                "reference and alternate alleles are identical",
            )
        if len(reference) != len(alternate):
            return self._abstention(
                variant,
                sequence,
                SequenceAnalysisState.ABSTAINED,
                "length-changing indels require alternate-haplotype coordinate mapping",
            )
        if variant.end != variant.start + len(reference) - 1:
            return self._abstention(
                variant,
                sequence,
                SequenceAnalysisState.ABSTAINED,
                "variant interval length does not match its literal reference allele",
            )
        motif_list = _bounded_motif_definitions(motifs)
        if variant.chromosome != sequence.chromosome:
            return self._abstention(
                variant,
                sequence,
                SequenceAnalysisState.ABSTAINED,
                "variant and sequence contigs do not match",
            )
        if variant.start < sequence.start or variant.end > sequence.end:
            return self._abstention(
                variant,
                sequence,
                SequenceAnalysisState.OUT_OF_WINDOW,
                "variant interval is not fully contained in the retrieved sequence window",
            )
        offset = variant.start - sequence.start
        reference_observed = sequence.sequence[offset : offset + len(reference)].upper()
        if reference_observed != reference:
            return self._abstention(
                variant,
                sequence,
                SequenceAnalysisState.REFERENCE_MISMATCH,
                (
                    f"retrieved reference {reference_observed!r} does not match "
                    f"declared {reference!r}"
                ),
                reference_observed=reference_observed,
            )
        alternate_sequence = (
            sequence.sequence[:offset]
            + alternate
            + sequence.sequence[offset + len(reference) :]
        )
        reference_hits = self.scanner.scan(
            sequence.sequence,
            genomic_start=sequence.start,
            motifs=motif_list,
        )
        alternate_hits = self.scanner.scan(
            alternate_sequence,
            genomic_start=sequence.start,
            motifs=motif_list,
        )
        reference_signatures = {hit.signature for hit in reference_hits}
        alternate_signatures = {hit.signature for hit in alternate_hits}
        created = tuple(hit for hit in alternate_hits if hit.signature not in reference_signatures)
        disrupted = tuple(
            hit for hit in reference_hits if hit.signature not in alternate_signatures
        )
        payload = {
            "variant_id": variant.variant_id,
            "source_id": sequence.source_id,
            "reference_interval": (sequence.chromosome, sequence.start, sequence.end),
            "reference_sequence_hash": content_hash(sequence.sequence),
            "alternate_sequence_hash": content_hash(alternate_sequence),
            "created_hits": created,
            "disrupted_hits": disrupted,
            "alternate_length_delta": len(alternate) - len(reference),
        }
        return SequenceAnalysisResult(
            variant_id=variant.variant_id,
            state=SequenceAnalysisState.SUPPORTED,
            source_id=sequence.source_id,
            reference_interval=(sequence.chromosome, sequence.start, sequence.end),
            reference_sequence_hash=content_hash(sequence.sequence),
            alternate_sequence_hash=content_hash(alternate_sequence),
            reference_allele_observed=reference_observed,
            alternate_length_delta=len(alternate) - len(reference),
            gc_fraction_reference=_gc_fraction(sequence.sequence),
            gc_fraction_alternate=_gc_fraction(alternate_sequence),
            created_hits=created,
            disrupted_hits=disrupted,
            limitations=(
                (
                    "Motif matching is a deterministic pattern comparison; it is not "
                    "a binding measurement."
                ),
                (
                    "Sequence-only changes do not establish chromatin activity, "
                    "target gene, or causal effect."
                ),
            ),
            content_address=content_hash(payload),
        )

    def analyze_haplotype(
        self,
        phased_variants: Iterable[PhasedVariantIdentity],
        sequence: SequenceSlice,
        *,
        motifs: Iterable[MotifDefinition] = (),
    ) -> HaplotypeSequenceAnalysisResult:
        """Apply one explicitly phased, non-overlapping variant set to a reference window.

        ``phase_set`` and ``haplotype_index`` are supplied by the genotype
        adapter. This method checks that all records agree, but it does not
        infer or repair phase from unphased calls.
        """

        if type(sequence) is not SequenceSlice:
            raise ValidationError("haplotype sequence input must be a SequenceSlice")
        phased = _bounded_phased_variants(phased_variants)
        if not phased:
            raise ValidationError("haplotype sequence analysis requires at least one variant")
        motif_list = _bounded_motif_definitions(motifs)
        first = phased[0]
        if any(
            item.phase_set != first.phase_set
            or item.haplotype_index != first.haplotype_index
            for item in phased[1:]
        ):
            raise ValidationError("all variants must belong to one phase set and haplotype")
        if any(item.variant.sample_id != first.variant.sample_id for item in phased[1:]):
            raise ValidationError("phased variants must belong to one sample")
        variant_ids = tuple(item.variant.variant_id for item in phased)
        if len(variant_ids) != len(set(variant_ids)):
            raise ValidationError("haplotype variant IDs must be unique")
        ordered = tuple(
            sorted(
                phased,
                key=lambda item: (
                    item.variant.start,
                    item.variant.end,
                    item.variant.variant_id,
                ),
            )
        )
        for previous, current in zip(ordered, ordered[1:], strict=False):
            if current.variant.start <= previous.variant.end:
                return self._haplotype_abstention(
                    ordered,
                    sequence,
                    motif_list,
                    SequenceAnalysisState.ABSTAINED,
                    "overlapping variants require joint complex-allele normalization",
                )
        if any(
            _genome_build_key(item.variant.genome_build) != _genome_build_key(sequence.assembly)
            for item in ordered
        ):
            return self._haplotype_abstention(
                ordered,
                sequence,
                motif_list,
                SequenceAnalysisState.ABSTAINED,
                "phased variants and sequence genome builds do not match",
            )
        if any(item.variant.chromosome != sequence.chromosome for item in ordered):
            return self._haplotype_abstention(
                ordered,
                sequence,
                motif_list,
                SequenceAnalysisState.ABSTAINED,
                "phased variants and sequence contigs do not match",
            )

        for item in ordered:
            variant = item.variant
            if variant.kind not in {VariantKind.SNV, VariantKind.INDEL}:
                return self._haplotype_abstention(
                    ordered,
                    sequence,
                    motif_list,
                    SequenceAnalysisState.ABSTAINED,
                    f"variant {variant.variant_id} is not a literal SNV or indel",
                )
            reference = variant.reference.upper()
            alternate = variant.alternate.upper()
            if (
                not reference
                or not alternate
                or any(base not in "ACGT" for base in reference + alternate)
            ):
                return self._haplotype_abstention(
                    ordered,
                    sequence,
                    motif_list,
                    SequenceAnalysisState.ABSTAINED,
                    (
                        f"variant {variant.variant_id} does not have unambiguous literal "
                        "A/C/G/T alleles"
                    ),
                )
            if reference == alternate:
                return self._haplotype_abstention(
                    ordered,
                    sequence,
                    motif_list,
                    SequenceAnalysisState.ABSTAINED,
                    f"variant {variant.variant_id} has identical reference and alternate alleles",
                )
            if variant.end != variant.start + len(reference) - 1:
                return self._haplotype_abstention(
                    ordered,
                    sequence,
                    motif_list,
                    SequenceAnalysisState.ABSTAINED,
                    (
                        f"variant {variant.variant_id} interval length does not match "
                        "its reference allele"
                    ),
                )
            if variant.start < sequence.start or variant.end > sequence.end:
                return self._haplotype_abstention(
                    ordered,
                    sequence,
                    motif_list,
                    SequenceAnalysisState.OUT_OF_WINDOW,
                    (
                        f"variant {variant.variant_id} is not fully contained in the "
                        "retrieved sequence window"
                    ),
                )
            offset = variant.start - sequence.start
            observed = sequence.sequence[offset : offset + len(reference)].upper()
            if observed != reference:
                return self._haplotype_abstention(
                    ordered,
                    sequence,
                    motif_list,
                    SequenceAnalysisState.REFERENCE_MISMATCH,
                    (
                        f"retrieved reference {observed!r} for variant {variant.variant_id} "
                        f"does not match declared {reference!r}"
                    ),
                )

        alternate_length = len(sequence.sequence) + sum(
            len(item.variant.alternate) - len(item.variant.reference) for item in ordered
        )
        if alternate_length < 1 or alternate_length > MAX_MOTIF_SCAN_SEQUENCE_BP:
            raise ValidationError(
                "constructed haplotype exceeds the "
                f"{MAX_MOTIF_SCAN_SEQUENCE_BP}-base sequence limit"
            )

        alternate_parts: list[str] = []
        coordinate_blocks: list[_HaplotypeCoordinateBlock] = []
        reference_cursor = 0
        alternate_cursor = 0

        def append_block(
            text: str,
            *,
            reference_start: int | None,
            variant_id: str | None,
        ) -> None:
            nonlocal alternate_cursor
            if not text:
                return
            alternate_parts.append(text)
            block_end = alternate_cursor + len(text)
            coordinate_blocks.append(
                _HaplotypeCoordinateBlock(
                    alternate_start=alternate_cursor,
                    alternate_end=block_end,
                    reference_start=reference_start,
                    variant_id=variant_id,
                )
            )
            alternate_cursor = block_end

        for item in ordered:
            variant = item.variant
            offset = variant.start - sequence.start
            append_block(
                sequence.sequence[reference_cursor:offset],
                reference_start=sequence.start + reference_cursor,
                variant_id=None,
            )
            alternate = variant.alternate.upper()
            reference = variant.reference.upper()
            if len(reference) == len(alternate):
                # Equal-length substitutions preserve a direct coordinate map,
                # even where the alternate bases differ from the reference.
                append_block(
                    alternate,
                    reference_start=variant.start,
                    variant_id=variant.variant_id,
                )
            else:
                # For length-changing alleles, only shared allele ends have an
                # unambiguous base-to-base mapping. VCF-style retained anchors
                # therefore remain mapped instead of making every hit touching
                # the anchor look newly created.
                shared_prefix = 0
                shared_limit = min(len(reference), len(alternate))
                while (
                    shared_prefix < shared_limit
                    and reference[shared_prefix] == alternate[shared_prefix]
                ):
                    shared_prefix += 1

                shared_suffix = 0
                while (
                    shared_suffix < len(reference) - shared_prefix
                    and shared_suffix < len(alternate) - shared_prefix
                    and reference[-(shared_suffix + 1)] == alternate[-(shared_suffix + 1)]
                ):
                    shared_suffix += 1

                append_block(
                    alternate[:shared_prefix],
                    reference_start=variant.start,
                    variant_id=variant.variant_id,
                )
                alternate_middle_end = len(alternate) - shared_suffix
                append_block(
                    alternate[shared_prefix:alternate_middle_end],
                    reference_start=None,
                    variant_id=variant.variant_id,
                )
                append_block(
                    alternate[alternate_middle_end:],
                    reference_start=variant.end - shared_suffix + 1,
                    variant_id=variant.variant_id,
                )
            reference_cursor = offset + len(variant.reference)
        append_block(
            sequence.sequence[reference_cursor:],
            reference_start=sequence.start + reference_cursor,
            variant_id=None,
        )
        alternate_sequence = "".join(alternate_parts)
        reference_hits = self.scanner.scan(
            sequence.sequence,
            genomic_start=sequence.start,
            motifs=motif_list,
        )
        alternate_hits = self.scanner.scan(
            alternate_sequence,
            genomic_start=1,
            motifs=motif_list,
        )
        reference_signatures = {hit.signature for hit in reference_hits}
        alternate_signatures: set[tuple[str, str, int, int, str]] = set()
        created: list[HaplotypeMotifDelta] = []
        for hit in alternate_hits:
            reference_interval, contributing_variant_ids = _map_haplotype_hit(
                hit,
                coordinate_blocks=coordinate_blocks,
                phased_variants=ordered,
                chromosome=sequence.chromosome,
            )
            signature = (
                hit.motif_id,
                hit.strand,
                reference_interval[1] if reference_interval is not None else -1,
                reference_interval[2] if reference_interval is not None else -1,
                hit.matched_sequence,
            )
            if reference_interval is not None:
                alternate_signatures.add(signature)
            if reference_interval is None or signature not in reference_signatures:
                created.append(
                    HaplotypeMotifDelta(
                        change=HaplotypeMotifChange.CREATED,
                        motif_id=hit.motif_id,
                        name=hit.name,
                        strand=hit.strand,
                        matched_sequence=hit.matched_sequence,
                        source_id=hit.source_id,
                        reference_interval=reference_interval,
                        haplotype_interval=(hit.start, hit.end),
                        variant_ids=contributing_variant_ids,
                    )
                )
        disrupted = tuple(
            HaplotypeMotifDelta(
                change=HaplotypeMotifChange.DISRUPTED,
                motif_id=hit.motif_id,
                name=hit.name,
                strand=hit.strand,
                matched_sequence=hit.matched_sequence,
                source_id=hit.source_id,
                reference_interval=(sequence.chromosome, hit.start, hit.end),
                haplotype_interval=None,
                variant_ids=_reference_hit_variant_ids(hit, ordered),
            )
            for hit in reference_hits
            if hit.signature not in alternate_signatures
        )
        if len(created) + len(disrupted) > MAX_HAPLOTYPE_MOTIF_DELTAS:
            raise ValidationError(
                "haplotype motif deltas exceed the "
                f"{MAX_HAPLOTYPE_MOTIF_DELTAS}-delta output limit"
            )
        created_hits = tuple(created)
        reference_hash = content_hash(sequence.sequence)
        alternate_hash = content_hash(alternate_sequence)
        motif_set_hash = content_hash(motif_list)
        reference_interval = (sequence.chromosome, sequence.start, sequence.end)
        variant_keys = tuple(item.variant.canonical_key for item in ordered)
        alternate_length_delta = len(alternate_sequence) - len(sequence.sequence)
        payload = {
            "phase_set": first.phase_set,
            "haplotype_index": first.haplotype_index,
            "variant_ids": tuple(item.variant.variant_id for item in ordered),
            "variant_keys": variant_keys,
            "source_id": sequence.source_id,
            "reference_interval": reference_interval,
            "reference_sequence_hash": reference_hash,
            "alternate_sequence_hash": alternate_hash,
            "alternate_length_delta": alternate_length_delta,
            "motif_set_hash": motif_set_hash,
            "created_hits": created_hits,
            "disrupted_hits": disrupted,
        }
        return HaplotypeSequenceAnalysisResult(
            phase_set=first.phase_set,
            haplotype_index=first.haplotype_index,
            variant_ids=tuple(item.variant.variant_id for item in ordered),
            state=SequenceAnalysisState.SUPPORTED,
            source_id=sequence.source_id,
            reference_interval=reference_interval,
            reference_sequence_hash=reference_hash,
            alternate_sequence_hash=alternate_hash,
            alternate_length_delta=alternate_length_delta,
            gc_fraction_reference=_gc_fraction(sequence.sequence),
            gc_fraction_alternate=_gc_fraction(alternate_sequence),
            motif_set_hash=motif_set_hash,
            created_hits=created_hits,
            disrupted_hits=disrupted,
            limitations=(
                (
                    "Phase set and haplotype assignment are caller-provided; this analysis "
                    "does not infer or independently validate genotype phase."
                ),
                (
                    "Haplotype motif intervals are 1-based offsets in the constructed alternate "
                    "window; genomic intervals are reported only for contiguous coordinate "
                    "mappings."
                ),
                (
                    "Motif matching is a deterministic pattern comparison; it is not a "
                    "binding measurement."
                ),
                (
                    "Sequence-only changes do not establish chromatin activity, target gene, "
                    "or causal effect."
                ),
            ),
            content_address=content_hash(payload),
        )

    @staticmethod
    def _haplotype_abstention(
        phased_variants: tuple[PhasedVariantIdentity, ...],
        sequence: SequenceSlice,
        motifs: tuple[MotifDefinition, ...],
        state: SequenceAnalysisState,
        reason: str,
    ) -> HaplotypeSequenceAnalysisResult:
        first = phased_variants[0]
        reference_hash = content_hash(sequence.sequence)
        motif_set_hash = content_hash(motifs)
        variant_ids = tuple(item.variant.variant_id for item in phased_variants)
        payload = {
            "phase_set": first.phase_set,
            "haplotype_index": first.haplotype_index,
            "variant_ids": variant_ids,
            "variant_keys": tuple(item.variant.canonical_key for item in phased_variants),
            "source_id": sequence.source_id,
            "reference_interval": (sequence.chromosome, sequence.start, sequence.end),
            "reference_sequence_hash": reference_hash,
            "state": state,
            "reason": reason,
            "motif_set_hash": motif_set_hash,
        }
        return HaplotypeSequenceAnalysisResult(
            phase_set=first.phase_set,
            haplotype_index=first.haplotype_index,
            variant_ids=variant_ids,
            state=state,
            source_id=sequence.source_id,
            reference_interval=(sequence.chromosome, sequence.start, sequence.end),
            reference_sequence_hash=reference_hash,
            alternate_sequence_hash=None,
            alternate_length_delta=None,
            gc_fraction_reference=_gc_fraction(sequence.sequence),
            gc_fraction_alternate=None,
            motif_set_hash=motif_set_hash,
            created_hits=(),
            disrupted_hits=(),
            limitations=(reason,),
            content_address=content_hash(payload),
        )

    @staticmethod
    def _abstention(
        variant: VariantIdentity,
        sequence: SequenceSlice,
        state: SequenceAnalysisState,
        reason: str,
        *,
        reference_observed: str | None = None,
    ) -> SequenceAnalysisResult:
        payload = {
            "variant_id": variant.variant_id,
            "source_id": sequence.source_id,
            "state": state,
            "reason": reason,
            "reference_observed": reference_observed,
        }
        return SequenceAnalysisResult(
            variant_id=variant.variant_id,
            state=state,
            source_id=sequence.source_id,
            reference_interval=(sequence.chromosome, sequence.start, sequence.end),
            reference_sequence_hash=content_hash(sequence.sequence),
            alternate_sequence_hash=None,
            reference_allele_observed=reference_observed,
            alternate_length_delta=None,
            gc_fraction_reference=_gc_fraction(sequence.sequence),
            gc_fraction_alternate=None,
            created_hits=(),
            disrupted_hits=(),
            limitations=(reason,),
            content_address=content_hash(payload),
        )


def _bounded_phased_variants(
    phased_variants: Iterable[PhasedVariantIdentity],
) -> tuple[PhasedVariantIdentity, ...]:
    try:
        iterator = iter(phased_variants)
    except TypeError as exc:
        raise ValidationError("phased variants must be iterable") from exc
    records = tuple(islice(iterator, MAX_HAPLOTYPE_VARIANTS + 1))
    if len(records) > MAX_HAPLOTYPE_VARIANTS:
        raise ValidationError(
            f"haplotype analysis exceeds the {MAX_HAPLOTYPE_VARIANTS}-variant limit"
        )
    if any(type(item) is not PhasedVariantIdentity for item in records):
        raise ValidationError("haplotype analysis requires PhasedVariantIdentity records")
    return records


def _map_haplotype_hit(
    hit: MotifHit,
    *,
    coordinate_blocks: list[_HaplotypeCoordinateBlock],
    phased_variants: tuple[PhasedVariantIdentity, ...],
    chromosome: str,
) -> tuple[tuple[str, int, int] | None, tuple[str, ...]]:
    """Map one alternate hit only when its bases form a contiguous reference interval."""

    hit_start = hit.start - 1
    hit_end = hit.end
    covered_until = hit_start
    mapped_segments: list[tuple[int, int]] = []
    contributing: set[str] = set()
    contains_unmapped_bases = False

    for block in coordinate_blocks:
        if block.alternate_end <= hit_start or block.alternate_start >= hit_end:
            continue
        overlap_start = max(hit_start, block.alternate_start)
        overlap_end = min(hit_end, block.alternate_end)
        if overlap_start != covered_until:
            raise ValidationError("alternate haplotype coordinate map is not contiguous")
        covered_until = overlap_end
        if block.variant_id is not None:
            contributing.add(block.variant_id)
        if block.reference_start is None:
            contains_unmapped_bases = True
            continue
        reference_start = block.reference_start + overlap_start - block.alternate_start
        mapped_segments.append((reference_start, reference_start + overlap_end - overlap_start - 1))

    if covered_until != hit_end:
        raise ValidationError("alternate haplotype coordinate map does not cover the motif hit")

    # A deletion can create a junction even if its retained VCF anchor is
    # outside the hit. Attribute that junction to the edit spanning the gap.
    for left, right in zip(mapped_segments, mapped_segments[1:], strict=False):
        gap_start = left[1] + 1
        gap_end = right[0] - 1
        if gap_start <= gap_end:
            for item in phased_variants:
                variant = item.variant
                if variant.start <= gap_end and variant.end >= gap_start:
                    contributing.add(variant.variant_id)

    mapped_length = sum(end - start + 1 for start, end in mapped_segments)
    contiguous = (
        not contains_unmapped_bases
        and mapped_length == hit_end - hit_start
        and bool(mapped_segments)
        and all(
            current[0] == previous[1] + 1
            for previous, current in zip(mapped_segments, mapped_segments[1:], strict=False)
        )
    )
    reference_interval = (
        (chromosome, mapped_segments[0][0], mapped_segments[-1][1])
        if contiguous
        else None
    )
    ordered_variant_ids = tuple(
        item.variant.variant_id
        for item in phased_variants
        if item.variant.variant_id in contributing
    )
    return reference_interval, ordered_variant_ids


def _reference_hit_variant_ids(
    hit: MotifHit,
    phased_variants: tuple[PhasedVariantIdentity, ...],
) -> tuple[str, ...]:
    return tuple(
        item.variant.variant_id
        for item in phased_variants
        if item.variant.start <= hit.end and item.variant.end >= hit.start
    )


def _matches(sequence: str, pattern: str) -> bool:
    return len(sequence) == len(pattern) and all(
        base in _IUPAC[code] for base, code in zip(sequence, pattern, strict=True)
    )


def _genome_build_key(value: str) -> str:
    """Compare only well-known assembly aliases; retain unknown labels exactly."""

    normalized = value.strip().casefold()
    aliases = {
        "grch38": "grch38",
        "hg38": "grch38",
        "grch37": "grch37",
        "hg19": "grch37",
    }
    return aliases.get(normalized, normalized)


def _reverse_complement_iupac(pattern: str) -> str:
    complement = {
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
        "V": "B",
        "D": "H",
        "H": "D",
        "N": "N",
    }
    return "".join(complement[base] for base in reversed(pattern.upper()))


def _reverse_complement(sequence: str) -> str:
    complement = str.maketrans("ACGTN", "TGCAN")
    return sequence.translate(complement)[::-1]


def _gc_fraction(sequence: str) -> float:
    if not sequence:
        return 0.0
    return round(sum(base in "GCgc" for base in sequence) / len(sequence), 6)
