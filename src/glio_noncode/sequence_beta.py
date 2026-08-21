"""Scientific-beta motif grammar and allele-specific sequence contracts.

The Domain 06 MVP separates deterministic sequence context from external model
receipts. This module adds four transparent local-window operations:

* motif disruption scanning;
* motif creation scanning;
* motif spacing and grammar analysis; and
* a cooperative transcription-factor grammar score.

Consensus matching is a declared motif operation, not a learned predictor.
Every result retains motif-source versions, sequence hashes, window bounds, and
explicit warnings about strand, context, calibration, and untested sequence
classes.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, hash_bytes, jsonable, require_non_empty


class SequenceBetaState(StrEnum):
    """Evidence state shared by motif and grammar operations."""

    SUPPORTED = "supported"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    ABSTAINED = "abstained"
    INVALID = "invalid"
    OUT_OF_DOMAIN = "out_of_domain"


@dataclass(frozen=True, slots=True)
class SequenceBetaIssue:
    """Addressable sequence-grammar issue with raw input provenance."""

    code: str
    message: str
    raw_hash: str
    source_id: str = "unspecified"
    severity: str = "warning"
    raw_record: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty(self.code, "issue code")
        require_non_empty(self.message, "issue message")
        require_non_empty(self.raw_hash, "issue raw_hash")
        if self.severity not in {"warning", "error"}:
            raise ValidationError("issue severity must be warning or error")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MotifDefinition:
    """A declared IUPAC consensus motif definition."""

    motif_id: str
    name: str
    consensus: str
    source_id: str
    source_version: str
    threshold: float = 1.0
    strand_aware: bool = True
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("motif_id", "name", "consensus", "source_id", "source_version"):
            require_non_empty(str(getattr(self, name)), name)
        normalized = self.consensus.upper()
        if any(base not in _IUPAC for base in normalized):
            raise ValidationError("motif consensus contains unsupported IUPAC symbols")
        if not 0 < self.threshold <= 1:
            raise ValidationError("motif threshold must be between zero and one")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MotifHit:
    """One motif match within a supplied sequence window."""

    motif_id: str
    motif_name: str
    start: int
    end: int
    strand: str
    matched_sequence: str
    score: float
    source_id: str
    source_version: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.motif_id, "motif_id")
        if self.start < 1 or self.end < self.start:
            raise ValidationError("motif hit interval is invalid")
        if self.strand not in {"+", "-"}:
            raise ValidationError("motif hit strand must be + or -")
        if not 0 <= self.score <= 1:
            raise ValidationError("motif hit score must be between zero and one")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MotifScanReport:
    """Reference/alternate motif comparison for one local sequence window."""

    variant_id: str
    context_key: str | None
    state: SequenceBetaState
    window_start: int
    reference_sequence_hash: str
    alternate_sequence_hash: str
    reference_hits: tuple[MotifHit, ...]
    alternate_hits: tuple[MotifHit, ...]
    disrupted_hits: tuple[MotifHit, ...]
    created_hits: tuple[MotifHit, ...]
    retained_hit_count: int
    source_ids: tuple[str, ...]
    source_versions: tuple[str, ...]
    issues: tuple[SequenceBetaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class MotifDisruptionScanner:
    """Scan reference/alternate windows and retain motif losses."""

    def scan(
        self,
        reference_sequence: str,
        alternate_sequence: str,
        *,
        variant_id: str,
        motifs: Iterable[MotifDefinition],
        window_start: int = 1,
        context_key: str | None = None,
    ) -> MotifScanReport:
        return _scan_motifs(
            reference_sequence,
            alternate_sequence,
            variant_id=variant_id,
            motifs=motifs,
            window_start=window_start,
            context_key=context_key,
        )


class MotifCreationScanner:
    """Scan reference/alternate windows and retain motif gains."""

    def scan(
        self,
        reference_sequence: str,
        alternate_sequence: str,
        *,
        variant_id: str,
        motifs: Iterable[MotifDefinition],
        window_start: int = 1,
        context_key: str | None = None,
    ) -> MotifScanReport:
        return _scan_motifs(
            reference_sequence,
            alternate_sequence,
            variant_id=variant_id,
            motifs=motifs,
            window_start=window_start,
            context_key=context_key,
        )


@dataclass(frozen=True, slots=True)
class MotifGrammarRule:
    """Declared spacing/orientation rule for two motif IDs."""

    rule_id: str
    motif_a: str
    motif_b: str
    minimum_spacing: int
    maximum_spacing: int
    allowed_orientations: tuple[str, ...] = ("same", "opposite", "any")
    source_id: str = "grammar-input"
    source_version: str = "unspecified"

    def __post_init__(self) -> None:
        for name in ("rule_id", "motif_a", "motif_b", "source_id", "source_version"):
            require_non_empty(str(getattr(self, name)), name)
        if self.minimum_spacing < 0 or self.maximum_spacing < self.minimum_spacing:
            raise ValidationError("motif grammar spacing bounds are invalid")
        if not set(self.allowed_orientations) <= {"same", "opposite", "any"}:
            raise ValidationError("motif grammar orientation is unsupported")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MotifGrammarObservation:
    """One compatible motif pair under a declared grammar rule."""

    rule_id: str
    motif_a_hit: MotifHit
    motif_b_hit: MotifHit
    spacing: int
    orientation_relation: str
    state: SequenceBetaState
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MotifGrammarReport:
    """Spacing/grammar result with all matching pairs retained."""

    context_key: str | None
    state: SequenceBetaState
    observations: tuple[MotifGrammarObservation, ...]
    unmatched_rule_ids: tuple[str, ...]
    issues: tuple[SequenceBetaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class MotifSpacingGrammarAnalyzer:
    """Evaluate declared motif spacing and orientation rules."""

    def analyze(
        self,
        hits: Iterable[MotifHit | Mapping[str, Any]],
        rules: Iterable[MotifGrammarRule],
        *,
        context_key: str | None = None,
    ) -> MotifGrammarReport:
        hit_values = tuple(_coerce_hit(value) for value in hits)
        rule_values = tuple(rules)
        observations: list[MotifGrammarObservation] = []
        unmatched: list[str] = []
        issues: list[SequenceBetaIssue] = []
        for rule in rule_values:
            a_hits = tuple(hit for hit in hit_values if hit.motif_id == rule.motif_a)
            b_hits = tuple(hit for hit in hit_values if hit.motif_id == rule.motif_b)
            rule_matches: list[MotifGrammarObservation] = []
            for hit_a in a_hits:
                for hit_b in b_hits:
                    spacing = _spacing(hit_a, hit_b)
                    relation = _orientation_relation(hit_a.strand, hit_b.strand)
                    orientation_ok = (
                        "any" in rule.allowed_orientations or relation in rule.allowed_orientations
                    )
                    if rule.minimum_spacing <= spacing <= rule.maximum_spacing and orientation_ok:
                        body = {
                            "rule_id": rule.rule_id,
                            "a": hit_a.content_address,
                            "b": hit_b.content_address,
                            "spacing": spacing,
                        }
                        rule_matches.append(
                            MotifGrammarObservation(
                                rule.rule_id,
                                hit_a,
                                hit_b,
                                spacing,
                                relation,
                                SequenceBetaState.SUPPORTED,
                                content_hash(body),
                            )
                        )
            if not rule_matches:
                unmatched.append(rule.rule_id)
            observations.extend(rule_matches)
        if not rule_values or not hit_values:
            state = SequenceBetaState.ABSTAINED
        elif unmatched and observations:
            state = SequenceBetaState.PARTIAL
        elif unmatched:
            state = SequenceBetaState.ABSTAINED
        elif len(observations) > len(rule_values):
            state = SequenceBetaState.AMBIGUOUS
        else:
            state = SequenceBetaState.SUPPORTED
        return MotifGrammarReport(
            context_key=context_key,
            state=state,
            observations=tuple(observations),
            unmatched_rule_ids=tuple(unmatched),
            issues=tuple(issues),
            warnings=(
                "Spacing compatibility is a declared grammar observation, not proof "
                "of cooperative binding.",
                "All compatible pairs are retained; the analyzer does not select a preferred pair.",
            ),
            content_address=content_hash(
                {
                    "context_key": context_key,
                    "state": state,
                    "observations": observations,
                    "unmatched": unmatched,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class GrammarInteraction:
    """One weighted cooperative interaction in a declared grammar model."""

    interaction_id: str
    motif_a: str
    motif_b: str
    weight: float
    maximum_spacing: int
    required: bool = False
    source_id: str = "grammar-model"
    source_version: str = "unspecified"

    def __post_init__(self) -> None:
        for name in ("interaction_id", "motif_a", "motif_b", "source_id", "source_version"):
            require_non_empty(str(getattr(self, name)), name)
        if self.maximum_spacing < 0:
            raise ValidationError("interaction maximum_spacing must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CooperativeGrammarScore:
    """Descriptive cooperative grammar score with per-interaction contributions."""

    sequence_id: str
    model_id: str
    model_version: str
    context_key: str | None
    state: SequenceBetaState
    score: float
    interaction_contributions: Mapping[str, float]
    matched_motif_ids: tuple[str, ...]
    missing_required_interactions: tuple[str, ...]
    sequence_hash: str
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class CooperativeTFGrammarModel:
    """Compute a reproducible weighted motif-interaction score."""

    def score(
        self,
        hits: Iterable[MotifHit | Mapping[str, Any]],
        interactions: Iterable[GrammarInteraction],
        *,
        sequence_id: str,
        sequence: str,
        model_id: str,
        model_version: str,
        context_key: str | None = None,
        baseline: float = 0.0,
    ) -> CooperativeGrammarScore:
        if not sequence_id.strip() or not model_id.strip() or not model_version.strip():
            raise ValidationError("grammar score IDs and model metadata are required")
        normalized_sequence = sequence.strip().upper()
        if not normalized_sequence or any(base not in "ACGTN" for base in normalized_sequence):
            raise ValidationError("grammar sequence must contain only A/C/G/T/N")
        hit_values = tuple(_coerce_hit(value) for value in hits)
        interaction_values = tuple(interactions)
        contributions: dict[str, float] = {}
        missing: list[str] = []
        score = baseline
        for interaction in interaction_values:
            a_hits = tuple(hit for hit in hit_values if hit.motif_id == interaction.motif_a)
            b_hits = tuple(hit for hit in hit_values if hit.motif_id == interaction.motif_b)
            compatible = any(
                _spacing(hit_a, hit_b) <= interaction.maximum_spacing
                for hit_a in a_hits
                for hit_b in b_hits
            )
            if compatible:
                contributions[interaction.interaction_id] = interaction.weight
                score += interaction.weight
            elif interaction.required:
                missing.append(interaction.interaction_id)
        if not interaction_values:
            state = SequenceBetaState.ABSTAINED
        elif missing and contributions:
            state = SequenceBetaState.PARTIAL
        elif missing:
            state = SequenceBetaState.ABSTAINED
        else:
            state = SequenceBetaState.SUPPORTED
        return CooperativeGrammarScore(
            sequence_id=sequence_id,
            model_id=model_id,
            model_version=model_version,
            context_key=context_key,
            state=state,
            score=round(score, 9),
            interaction_contributions={
                key: round(value, 9) for key, value in contributions.items()
            },
            matched_motif_ids=tuple(sorted({hit.motif_id for hit in hit_values})),
            missing_required_interactions=tuple(missing),
            sequence_hash=hash_bytes(normalized_sequence.encode("utf-8")),
            warnings=(
                "Cooperative grammar score is a model-defined descriptive score, "
                "not a probability.",
                "Model calibration, perturbation validation, and negative-control "
                "performance are not supplied here.",
            ),
            content_address=content_hash(
                {
                    "sequence_id": sequence_id,
                    "model_id": model_id,
                    "model_version": model_version,
                    "context_key": context_key,
                    "state": state,
                    "score": score,
                    "contributions": contributions,
                }
            ),
        )


def _scan_motifs(
    reference_sequence: str,
    alternate_sequence: str,
    *,
    variant_id: str,
    motifs: Iterable[MotifDefinition],
    window_start: int,
    context_key: str | None,
) -> MotifScanReport:
    if not variant_id.strip() or window_start < 1:
        raise ValidationError("variant_id and positive window_start are required")
    ref = reference_sequence.strip().upper()
    alt = alternate_sequence.strip().upper()
    input_hash = content_hash({"variant_id": variant_id, "reference": ref, "alternate": alt})
    motifs_values = tuple(motifs)
    if not ref or not alt:
        issue = SequenceBetaIssue(
            "empty_sequence_window",
            "reference and alternate windows are required",
            input_hash,
            severity="error",
        )
        return _scan_report(
            variant_id, window_start, ref, alt, (), (), (), (), (), (issue,), context_key
        )
    if any(base not in "ACGTN" for base in ref + alt):
        issue = SequenceBetaIssue(
            "invalid_sequence_alphabet",
            "sequence windows must contain only A/C/G/T/N",
            input_hash,
            severity="error",
        )
        return _scan_report(
            variant_id, window_start, ref, alt, (), (), (), (), (), (issue,), context_key
        )
    if not motifs_values:
        return _scan_report(
            variant_id,
            window_start,
            ref,
            alt,
            (),
            (),
            (),
            (),
            (),
            (),
            context_key,
            state=SequenceBetaState.ABSTAINED,
        )
    ref_hits = _find_hits(ref, motifs_values, window_start)
    alt_hits = _find_hits(alt, motifs_values, window_start)
    ref_keys = {_hit_key(hit) for hit in ref_hits}
    alt_keys = {_hit_key(hit) for hit in alt_hits}
    disrupted = tuple(hit for hit in ref_hits if _hit_key(hit) not in alt_keys)
    created = tuple(hit for hit in alt_hits if _hit_key(hit) not in ref_keys)
    retained = len(ref_hits) - len(disrupted)
    source_ids = tuple(sorted({motif.source_id for motif in motifs_values}))
    source_versions = tuple(sorted({motif.source_version for motif in motifs_values}))
    return _scan_report(
        variant_id,
        window_start,
        ref,
        alt,
        ref_hits,
        alt_hits,
        disrupted,
        created,
        source_ids,
        (),
        context_key,
        retained=retained,
        source_versions=source_versions,
    )


def _find_hits(
    sequence: str, motifs: tuple[MotifDefinition, ...], window_start: int
) -> tuple[MotifHit, ...]:
    hits: list[MotifHit] = []
    for motif in motifs:
        consensus = motif.consensus.upper()
        strands = (
            (("+", consensus), ("-", _reverse_complement(consensus)))
            if motif.strand_aware
            else (("+", consensus),)
        )
        for strand, pattern in strands:
            for index in range(len(sequence) - len(pattern) + 1):
                matched = sequence[index : index + len(pattern)]
                score = sum(
                    base in _IUPAC[pattern[offset]] for offset, base in enumerate(matched)
                ) / len(pattern)
                if score >= motif.threshold:
                    body = {
                        "motif_id": motif.motif_id,
                        "strand": strand,
                        "start": window_start + index,
                        "matched": matched,
                        "score": score,
                    }
                    hits.append(
                        MotifHit(
                            motif.motif_id,
                            motif.name,
                            window_start + index,
                            window_start + index + len(pattern) - 1,
                            strand,
                            matched,
                            round(score, 6),
                            motif.source_id,
                            motif.source_version,
                            content_hash(body),
                        )
                    )
    return tuple(sorted(hits, key=lambda hit: (hit.start, hit.end, hit.motif_id, hit.strand)))


def _scan_report(
    variant_id: str,
    window_start: int,
    reference: str,
    alternate: str,
    reference_hits: tuple[MotifHit, ...],
    alternate_hits: tuple[MotifHit, ...],
    disrupted: tuple[MotifHit, ...],
    created: tuple[MotifHit, ...],
    source_ids: tuple[str, ...],
    issues: tuple[SequenceBetaIssue, ...],
    context_key: str | None,
    *,
    retained: int = 0,
    source_versions: tuple[str, ...] = (),
    state: SequenceBetaState | None = None,
) -> MotifScanReport:
    selected_state = state or (SequenceBetaState.PARTIAL if issues else SequenceBetaState.SUPPORTED)
    return MotifScanReport(
        variant_id=variant_id,
        context_key=context_key,
        state=selected_state,
        window_start=window_start,
        reference_sequence_hash=hash_bytes(reference.encode("utf-8")),
        alternate_sequence_hash=hash_bytes(alternate.encode("utf-8")),
        reference_hits=reference_hits,
        alternate_hits=alternate_hits,
        disrupted_hits=disrupted,
        created_hits=created,
        retained_hit_count=retained,
        source_ids=source_ids,
        source_versions=source_versions,
        issues=issues,
        warnings=(
            "Motif comparison is limited to the supplied local sequence windows and "
            "declared consensus motifs.",
            "A motif loss or gain is not a calibrated regulatory-effect or clinical claim.",
        ),
        content_address=content_hash(
            {
                "variant_id": variant_id,
                "reference_hash": hash_bytes(reference.encode("utf-8")),
                "alternate_hash": hash_bytes(alternate.encode("utf-8")),
                "reference_hits": reference_hits,
                "alternate_hits": alternate_hits,
                "disrupted": disrupted,
                "created": created,
                "context_key": context_key,
                "state": selected_state,
            }
        ),
    )


def _coerce_hit(value: MotifHit | Mapping[str, Any]) -> MotifHit:
    if isinstance(value, MotifHit):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("motif hit must be a MotifHit or mapping")
    return MotifHit(
        motif_id=str(value.get("motif_id", "")),
        motif_name=str(value.get("motif_name", value.get("name", value.get("motif_id", "")))),
        start=int(value.get("start", 0)),
        end=int(value.get("end", value.get("start", 0))),
        strand=str(value.get("strand", "+")),
        matched_sequence=str(value.get("matched_sequence", value.get("sequence", "N"))),
        score=float(value.get("score", 1.0)),
        source_id=str(value.get("source_id", "motif-input")),
        source_version=str(value.get("source_version", "unspecified")),
        content_address=str(value.get("content_address", content_hash(dict(value)))),
    )


def _hit_key(hit: MotifHit) -> tuple[str, int, int, str]:
    return hit.motif_id, hit.start, hit.end, hit.strand


def _spacing(left: MotifHit, right: MotifHit) -> int:
    if left.start <= right.start:
        return max(0, right.start - left.end - 1)
    return max(0, left.start - right.end - 1)


def _orientation_relation(left: str, right: str) -> str:
    return "same" if left == right else "opposite"


def _reverse_complement(sequence: str) -> str:
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
    return "".join(complement.get(base, "N") for base in reversed(sequence))


_IUPAC: dict[str, set[str]] = {
    "A": {"A"},
    "C": {"C"},
    "G": {"G"},
    "T": {"T"},
    "R": {"A", "G"},
    "Y": {"C", "T"},
    "S": {"G", "C"},
    "W": {"A", "T"},
    "K": {"G", "T"},
    "M": {"A", "C"},
    "B": {"C", "G", "T"},
    "D": {"A", "G", "T"},
    "H": {"A", "C", "T"},
    "V": {"A", "C", "G"},
    "N": {"A", "C", "G", "T", "N"},
}


__all__ = [
    "CooperativeGrammarScore",
    "CooperativeTFGrammarModel",
    "GrammarInteraction",
    "MotifCreationScanner",
    "MotifDefinition",
    "MotifDisruptionScanner",
    "MotifGrammarObservation",
    "MotifGrammarReport",
    "MotifGrammarRule",
    "MotifHit",
    "MotifScanReport",
    "MotifSpacingGrammarAnalyzer",
    "SequenceBetaIssue",
    "SequenceBetaState",
]
