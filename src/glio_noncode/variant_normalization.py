"""Deterministic VRS-style normalization reports for supported variant classes.

The implementation emits the structural shape of a GA4GH Variation
Representation allele and keeps the sequence identifier explicit.  It does not
pretend that a local assembly name is a RefGet digest: when a true sequence
digest is not supplied, the report records that limitation and never silently
claims reference-equivalence.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .identity import normalize_allele, normalize_chromosome, normalize_variant
from .models import VariantIdentity, VariantKind
from .serialization import content_hash, jsonable


class NormalizationState(StrEnum):
    SUPPORTED = "supported"
    AMBIGUOUS = "ambiguous"
    ABSTAINED = "abstained"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class NormalizationCandidate:
    """One canonical identity and its VRS-shaped allele representation."""

    variant: VariantIdentity
    vrs_allele: Mapping[str, Any]
    transformation_steps: tuple[str, ...]
    reference_digest_supplied: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class NormalizationReport:
    """Normalization outcome including ambiguity and provenance explanations."""

    input_id: str
    input_hash: str
    state: NormalizationState
    candidates: tuple[NormalizationCandidate, ...]
    selected_candidate_id: str | None
    ambiguities: tuple[str, ...]
    warnings: tuple[str, ...]
    transformation_provenance: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class VRSNormalizer:
    """Normalize SNVs/indels and explicitly abstain on unsupported structures."""

    def normalize(
        self,
        raw: VariantIdentity | Mapping[str, Any] | str,
        *,
        genome_build: str = "GRCh38",
        sequence_digest: str | None = None,
        reference_sequence: str | None = None,
        reference_start: int | None = None,
    ) -> NormalizationReport:
        input_hash = content_hash(raw.to_dict() if isinstance(raw, VariantIdentity) else raw)
        try:
            variant = self._coerce_variant(raw, genome_build)
        except (TypeError, ValueError, ValidationError) as exc:
            return self._report(
                input_id=self._input_id(raw),
                input_hash=input_hash,
                state=NormalizationState.INVALID,
                candidates=(),
                selected=None,
                ambiguities=(),
                warnings=(str(exc),),
                provenance=("input parsing failed",),
            )
        if (
            variant.kind in {VariantKind.BREAKEND, VariantKind.CNV, VariantKind.HAPLOTYPE}
            or "<" in variant.alternate
        ):
            return self._report(
                input_id=variant.variant_id,
                input_hash=input_hash,
                state=NormalizationState.ABSTAINED,
                candidates=(),
                selected=None,
                ambiguities=(),
                warnings=(
                    f"variant kind {variant.kind.value} requires a structural "
                    "or haplotype normalizer",
                ),
                provenance=("no unsupported identity was silently flattened",),
            )
        normalized, steps = self._trim_common_sequence(variant)
        candidates = [
            self._candidate(
                normalized,
                genome_build=genome_build,
                sequence_digest=sequence_digest,
                steps=steps,
            )
        ]
        ambiguities: list[str] = []
        warnings: list[str] = []
        if reference_sequence is None:
            warnings.append(
                "reference sequence was not supplied; repeat-aware left alignment was not attempted"
            )
        else:
            repeat_candidates = self._repeat_shift_candidates(
                normalized,
                reference_sequence,
                sequence_digest,
                steps,
                reference_start=reference_start,
            )
            if len(repeat_candidates) > 1:
                candidates = repeat_candidates
                ambiguities.append(
                    "multiple equivalent repeat placements were observed; no "
                    "placement was silently preferred"
                )
        state = (
            NormalizationState.AMBIGUOUS if len(candidates) > 1 else NormalizationState.SUPPORTED
        )
        selected = candidates[0].variant.variant_id if len(candidates) == 1 else None
        return self._report(
            input_id=variant.variant_id,
            input_hash=input_hash,
            state=state,
            candidates=tuple(candidates),
            selected=selected,
            ambiguities=tuple(ambiguities),
            warnings=tuple(warnings),
            provenance=tuple(steps) + ("VRS-shaped allele emitted from normalized coordinates",),
        )

    @staticmethod
    def _input_id(raw: VariantIdentity | Mapping[str, Any] | str) -> str:
        if isinstance(raw, VariantIdentity):
            return raw.variant_id
        if isinstance(raw, Mapping):
            return str(raw.get("variant_id", raw.get("id", "unidentified-input")))
        return str(raw)

    @staticmethod
    def _coerce_variant(
        raw: VariantIdentity | Mapping[str, Any] | str,
        genome_build: str,
    ) -> VariantIdentity:
        if isinstance(raw, VariantIdentity):
            return raw
        if isinstance(raw, str):
            return normalize_variant({"notation": raw, "genome_build": genome_build})
        if not isinstance(raw, Mapping):
            raise ValidationError("normalization input must be a variant, mapping, or notation")
        if "notation" in raw:
            return normalize_variant(raw, default_build=genome_build)
        chromosome = normalize_chromosome(str(raw.get("chromosome", raw.get("chrom", ""))))
        start = int(raw.get("start", raw.get("position", raw.get("pos", 0))))
        reference = normalize_allele(str(raw.get("reference", raw.get("ref", ""))))
        alternate = normalize_allele(str(raw.get("alternate", raw.get("alt", ""))))
        if start < 1:
            raise ValidationError("variant start must be positive")
        return normalize_variant(
            {
                "notation": f"{chromosome}:{start}:{reference}>{alternate}",
                "genome_build": str(raw.get("genome_build", genome_build)),
                "variant_id": str(raw.get("variant_id", raw.get("id", ""))) or None,
                "annotations": dict(raw.get("annotations", {})),
            }
        )

    @staticmethod
    def _trim_common_sequence(variant: VariantIdentity) -> tuple[VariantIdentity, tuple[str, ...]]:
        reference = variant.reference
        alternate = variant.alternate
        start = variant.start
        steps: list[str] = []
        while len(reference) > 1 and len(alternate) > 1 and reference[0] == alternate[0]:
            reference = reference[1:]
            alternate = alternate[1:]
            start += 1
            steps.append("trimmed shared prefix")
        while len(reference) > 1 and len(alternate) > 1 and reference[-1] == alternate[-1]:
            reference = reference[:-1]
            alternate = alternate[:-1]
            steps.append("trimmed shared suffix")
        if not steps:
            steps.append("no shared prefix or suffix trimming required")
        return (
            replace(
                variant,
                start=start,
                end=start + len(reference) - 1,
                reference=reference,
                alternate=alternate,
                variant_id=f"{variant.genome_build}:{variant.chromosome}:{start}:{reference}>{alternate}",
            ),
            tuple(steps),
        )

    def _repeat_shift_candidates(
        self,
        variant: VariantIdentity,
        reference_sequence: str,
        sequence_digest: str | None,
        steps: tuple[str, ...],
        *,
        reference_start: int | None,
    ) -> list[NormalizationCandidate]:
        sequence = reference_sequence.upper()
        if not sequence or variant.kind not in {VariantKind.INDEL}:
            return [
                self._candidate(
                    variant,
                    genome_build=variant.genome_build,
                    sequence_digest=sequence_digest,
                    steps=steps,
                )
            ]
        # The bounded shift detects equivalent one-base repeat placements.  A
        # complex repeat is reported as ambiguous rather than being greedily
        # assigned a leftmost coordinate without a reference-equivalence proof.
        candidates = [variant]
        motif = (
            variant.alternate[-1]
            if len(variant.alternate) > len(variant.reference)
            else variant.reference[-1]
        )
        window_start = reference_start if reference_start is not None else variant.start
        cursor = variant.start - window_start - 2
        while 0 <= cursor < len(sequence) and sequence[cursor] == motif and len(candidates) < 32:
            shifted = replace(
                variant,
                start=variant.start - (len(candidates)),
                end=variant.end - (len(candidates)),
                variant_id=(
                    f"{variant.genome_build}:{variant.chromosome}:"
                    f"{variant.start - len(candidates)}:"
                    f"{variant.reference}>{variant.alternate}"
                ),
            )
            candidates.append(shifted)
            cursor -= 1
        return [
            self._candidate(
                candidate,
                genome_build=variant.genome_build,
                sequence_digest=sequence_digest,
                steps=steps + ("detected equivalent one-base repeat placement",),
            )
            for candidate in candidates
        ]

    @staticmethod
    def _candidate(
        variant: VariantIdentity,
        *,
        genome_build: str,
        sequence_digest: str | None,
        steps: tuple[str, ...],
    ) -> NormalizationCandidate:
        sequence_id = sequence_digest or f"local:{genome_build}:{variant.chromosome}"
        vrs = {
            "type": "Allele",
            "location": {
                "type": "SequenceLocation",
                "sequence_id": sequence_id,
                "interval": {
                    "type": "SimpleInterval",
                    "start": variant.start - 1,
                    "end": variant.end,
                },
            },
            "state": {
                "type": "LiteralSequenceExpression",
                "sequence": variant.alternate,
            },
        }
        body = {"variant": variant, "vrs_allele": vrs, "steps": steps}
        return NormalizationCandidate(
            variant=variant,
            vrs_allele=vrs,
            transformation_steps=steps,
            reference_digest_supplied=sequence_digest is not None,
            content_address=content_hash(body),
        )

    @staticmethod
    def _report(
        *,
        input_id: str,
        input_hash: str,
        state: NormalizationState,
        candidates: tuple[NormalizationCandidate, ...],
        selected: str | None,
        ambiguities: tuple[str, ...],
        warnings: tuple[str, ...],
        provenance: tuple[str, ...],
    ) -> NormalizationReport:
        body = {
            "input_id": input_id,
            "input_hash": input_hash,
            "state": state,
            "candidates": candidates,
            "selected": selected,
            "ambiguities": ambiguities,
            "warnings": warnings,
            "provenance": provenance,
        }
        return NormalizationReport(
            input_id=input_id,
            input_hash=input_hash,
            state=state,
            candidates=candidates,
            selected_candidate_id=selected,
            ambiguities=ambiguities,
            warnings=warnings,
            transformation_provenance=provenance,
            content_address=content_hash(body),
        )
