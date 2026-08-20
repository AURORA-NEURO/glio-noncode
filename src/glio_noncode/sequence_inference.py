"""Deterministic sequence and motif inference over retrieved reference windows."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .data_sources import SequenceSlice
from .errors import ValidationError
from .models import EvidenceClaim, EvidenceState, EvidenceTier, ReferenceContext, VariantIdentity
from .serialization import content_hash, jsonable


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
            if not str(getattr(self, name)).strip():
                raise ValidationError(f"{name} must not be empty")
        if any(base not in _IUPAC for base in self.pattern.upper()):
            raise ValidationError(f"motif pattern contains unsupported IUPAC bases: {self.pattern}")

    @property
    def normalized_pattern(self) -> str:
        return self.pattern.upper()

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


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
        if self.start < 1 or self.end < self.start:
            raise ValidationError("motif hit interval is invalid")
        if self.strand not in {"+", "-"}:
            raise ValidationError("motif hit strand must be + or -")

    @property
    def signature(self) -> tuple[str, str, int, int, str]:
        return (self.motif_id, self.strand, self.start, self.end, self.matched_sequence)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


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
        normalized = sequence.upper()
        if not normalized or any(base not in "ACGTN" for base in normalized):
            raise ValidationError("motif scanner sequence must contain only A/C/G/T/N")
        if genomic_start < 1:
            raise ValidationError("motif scanner genomic_start must be positive")
        hits: list[MotifHit] = []
        for motif in motifs:
            pattern = motif.normalized_pattern
            reverse_pattern = _reverse_complement_iupac(pattern)
            for offset in range(0, len(normalized) - len(pattern) + 1):
                window = normalized[offset : offset + len(pattern)]
                if _matches(window, pattern):
                    hits.append(
                        MotifHit(
                            motif_id=motif.motif_id,
                            name=motif.name,
                            start=genomic_start + offset,
                            end=genomic_start + offset + len(pattern) - 1,
                            strand="+",
                            matched_sequence=window,
                            source_id=motif.source_id,
                        )
                    )
                if reverse_pattern != pattern and _matches(window, reverse_pattern):
                    hits.append(
                        MotifHit(
                            motif_id=motif.motif_id,
                            name=motif.name,
                            start=genomic_start + offset,
                            end=genomic_start + offset + len(pattern) - 1,
                            strand="-",
                            matched_sequence=window,
                            source_id=motif.source_id,
                        )
                    )
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
        reference_observed = sequence.sequence[offset : offset + len(variant.reference)].upper()
        if reference_observed != variant.reference.upper():
            return self._abstention(
                variant,
                sequence,
                SequenceAnalysisState.REFERENCE_MISMATCH,
                (
                    f"retrieved reference {reference_observed!r} does not match "
                    f"declared {variant.reference!r}"
                ),
                reference_observed=reference_observed,
            )
        alternate_sequence = (
            sequence.sequence[:offset]
            + variant.alternate.upper()
            + sequence.sequence[offset + len(variant.reference) :]
        )
        reference_hits = self.scanner.scan(
            sequence.sequence,
            genomic_start=sequence.start,
            motifs=motifs,
        )
        alternate_hits = self.scanner.scan(
            alternate_sequence,
            genomic_start=sequence.start,
            motifs=motifs,
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
            "alternate_length_delta": len(variant.alternate) - len(variant.reference),
        }
        return SequenceAnalysisResult(
            variant_id=variant.variant_id,
            state=SequenceAnalysisState.SUPPORTED,
            source_id=sequence.source_id,
            reference_interval=(sequence.chromosome, sequence.start, sequence.end),
            reference_sequence_hash=content_hash(sequence.sequence),
            alternate_sequence_hash=content_hash(alternate_sequence),
            reference_allele_observed=reference_observed,
            alternate_length_delta=len(variant.alternate) - len(variant.reference),
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


def _matches(sequence: str, pattern: str) -> bool:
    return len(sequence) == len(pattern) and all(
        base in _IUPAC[code] for base, code in zip(sequence, pattern, strict=True)
    )


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
