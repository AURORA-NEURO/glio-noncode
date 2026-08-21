"""Sequence context and model-output adapter contracts.

The sequence plane separates deterministic representations from external model
outputs. A feature vector is not a learned embedding, an adapter receipt is
not a validation result, and an ensemble delta is not a probability of
regulatory effect. Missing model metadata, malformed rows, and disagreement
remain visible in the result.
"""

from __future__ import annotations

import csv
import io
import json
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable


class SequenceAdapterState(StrEnum):
    SUPPORTED = "supported"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    ABSTAINED = "abstained"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class SequenceAdapterIssue:
    code: str
    message: str
    source_line: int | None = None
    raw_hash: str | None = None
    severity: str = "error"
    remediation: str = (
        "Inspect the source output and route malformed or unsupported rows to review."
    )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceFeatureVector:
    """Transparent sequence context representation."""

    sequence_id: str
    source_id: str
    sequence_hash: str
    length: int
    gc_fraction: float
    ambiguous_fraction: float
    kmer_size: int
    kmer_frequencies: Mapping[str, float]
    content_address: str

    def __post_init__(self) -> None:
        if not self.sequence_id or not self.source_id or not self.sequence_hash:
            raise ValidationError("sequence feature IDs and source are required")
        if self.length < 1 or self.kmer_size < 1:
            raise ValidationError("sequence length and kmer_size must be positive")
        if not 0.0 <= self.gc_fraction <= 1.0 or not 0.0 <= self.ambiguous_fraction <= 1.0:
            raise ValidationError("sequence fractions must be between 0 and 1")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class SequenceContextEncoder:
    """Encode bounded sequence context without a learned-model claim."""

    def __init__(self, *, max_length: int = 5_000_000) -> None:
        if max_length < 1:
            raise ValidationError("max_length must be positive")
        self.max_length = max_length

    def encode(
        self,
        sequence: str,
        *,
        sequence_id: str,
        source_id: str,
        kmer_size: int = 3,
    ) -> SequenceFeatureVector:
        if not sequence_id.strip() or not source_id.strip():
            raise ValidationError("sequence_id and source_id are required")
        normalized = sequence.strip().upper()
        if not normalized or len(normalized) > self.max_length:
            raise ValidationError("sequence is empty or exceeds the encoder bound")
        if kmer_size < 1 or kmer_size > 8:
            raise ValidationError("kmer_size must be between 1 and 8")
        if any(base not in "ACGTN" for base in normalized):
            raise ValidationError("sequence must contain only A/C/G/T/N")
        counts = Counter(
            normalized[index : index + kmer_size]
            for index in range(len(normalized) - kmer_size + 1)
            if "N" not in normalized[index : index + kmer_size]
        )
        total = sum(counts.values()) or 1
        frequencies = {
            kmer: round(count / total, 9) for kmer, count in sorted(counts.items())
        }
        gc_fraction = (normalized.count("G") + normalized.count("C")) / len(normalized)
        ambiguous_fraction = normalized.count("N") / len(normalized)
        body = {
            "sequence_id": sequence_id,
            "source_id": source_id,
            "sequence_hash": content_hash(normalized),
            "length": len(normalized),
            "gc_fraction": gc_fraction,
            "ambiguous_fraction": ambiguous_fraction,
            "kmer_size": kmer_size,
            "kmer_frequencies": frequencies,
        }
        return SequenceFeatureVector(
            sequence_id=sequence_id,
            source_id=source_id,
            sequence_hash=body["sequence_hash"],
            length=len(normalized),
            gc_fraction=round(gc_fraction, 9),
            ambiguous_fraction=round(ambiguous_fraction, 9),
            kmer_size=kmer_size,
            kmer_frequencies=frequencies,
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class VariantEffectObservation:
    """One external model's reported reference/alternate effect delta."""

    observation_id: str
    model_id: str
    model_version: str
    variant_id: str
    reference_score: float
    alternate_score: float
    delta: float
    context_length: int
    source_id: str
    raw_hash: str
    reported_uncertainty: float | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "observation_id",
            "model_id",
            "model_version",
            "variant_id",
            "source_id",
            "raw_hash",
        ):
            if not str(getattr(self, name)).strip():
                raise ValidationError(f"effect observation {name} is required")
        for name in ("reference_score", "alternate_score", "delta"):
            if not isfinite(getattr(self, name)):
                raise ValidationError(f"effect {name} must be finite")
        if self.context_length < 1:
            raise ValidationError("effect context_length must be positive")
        if self.reported_uncertainty is not None and not 0.0 <= self.reported_uncertainty <= 1.0:
            raise ValidationError("reported_uncertainty must be between 0 and 1")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class VariantEffectBatch:
    adapter_id: str
    source_id: str
    input_hash: str
    observations: tuple[VariantEffectObservation, ...]
    issues: tuple[SequenceAdapterIssue, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class _EffectTableAdapter:
    """Shared strict parser for model output tables."""

    adapter_id = "sequence-effect"
    minimum_context_length = 1

    def parse_text(
        self,
        text: str,
        *,
        source_id: str,
        adapter_id: str | None = None,
    ) -> VariantEffectBatch:
        if not isinstance(text, str) or not text.strip():
            raise ValidationError("effect adapter input must not be empty")
        first = next(line.strip() for line in text.splitlines() if line.strip())
        if first.startswith(("{", "[")):
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValidationError(f"invalid effect adapter JSON: {exc}") from exc
            rows = payload.get("observations", payload) if isinstance(payload, Mapping) else payload
            if not isinstance(rows, list):
                raise ValidationError("effect adapter JSON must contain observations")
            json_mode = True
        else:
            reader = csv.DictReader(io.StringIO(text), delimiter="\t")
            if not reader.fieldnames:
                raise ValidationError("effect adapter TSV requires a header")
            rows = tuple(reader)
            json_mode = False
        observations: list[VariantEffectObservation] = []
        issues: list[SequenceAdapterIssue] = []
        selected_adapter = adapter_id or self.adapter_id
        for index, row in enumerate(rows, start=1 if json_mode else 2):
            if not isinstance(row, Mapping):
                issues.append(SequenceAdapterIssue("invalid_effect_row", "row must be an object"))
                continue
            raw_hash = content_hash(row)
            try:
                reference = float(self._value(row, "reference_score", "ref_score"))
                alternate = float(self._value(row, "alternate_score", "alt_score"))
                context_length = int(
                    self._value(
                        row,
                        "context_length",
                        "window_bp",
                        default=self.minimum_context_length,
                    )
                )
                if context_length < self.minimum_context_length:
                    raise ValidationError(
                        f"context_length must be at least {self.minimum_context_length}"
                    )
                reported_delta = self._value(row, "delta", "effect_delta", default=None)
                delta = (
                    alternate - reference if reported_delta is None else float(reported_delta)
                )
                if abs(delta - (alternate - reference)) > 1e-6:
                    raise ValidationError("reported delta does not equal alternate minus reference")
                observations.append(
                    VariantEffectObservation(
                        observation_id=f"{source_id}:{index}",
                        model_id=str(self._value(row, "model_id", "model")),
                        model_version=str(
                            self._value(row, "model_version", "version", default="unspecified")
                        ),
                        variant_id=str(self._value(row, "variant_id", "variant")),
                        reference_score=reference,
                        alternate_score=alternate,
                        delta=round(delta, 9),
                        context_length=context_length,
                        source_id=source_id,
                        raw_hash=raw_hash,
                        reported_uncertainty=(
                            float(self._value(row, "uncertainty"))
                            if self._value(row, "uncertainty") is not None
                            else None
                        ),
                        attributes=dict(row),
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    SequenceAdapterIssue(
                        "invalid_effect_row",
                        str(exc),
                        None if json_mode else index,
                        raw_hash,
                    )
                )
        body = {
            "adapter_id": selected_adapter,
            "source_id": source_id,
            "input_hash": content_hash(text),
            "observations": tuple(observations),
            "issues": tuple(issues),
        }
        return VariantEffectBatch(
            adapter_id=selected_adapter,
            source_id=source_id,
            input_hash=content_hash(text),
            observations=tuple(observations),
            issues=tuple(issues),
            content_address=content_hash(body),
        )

    @staticmethod
    def _value(row: Mapping[str, Any], *names: str, default: Any = None) -> Any:
        for name in names:
            value = row.get(name)
            if value is not None and value != "":
                return value
        return default


class SequenceFoundationModelAdapter(_EffectTableAdapter):
    """Strict adapter for a declared sequence foundation-model output."""

    adapter_id = "sequence-foundation-model"


class LongContextVariantEffectAdapter(_EffectTableAdapter):
    """Strict adapter requiring a declared long context window."""

    adapter_id = "long-context-variant-effect"
    minimum_context_length = 1_024


@dataclass(frozen=True, slots=True)
class EnsembleDelta:
    variant_id: str
    state: SequenceAdapterState
    observation_ids: tuple[str, ...]
    model_ids: tuple[str, ...]
    mean_delta: float | None
    disagreement: float | None
    context_length_min: int | None
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class RegulatoryTrackDeltaEnsemble:
    """Combine model deltas while retaining spread and model provenance."""

    def __init__(self, *, disagreement_tolerance: float = 0.25) -> None:
        if disagreement_tolerance < 0:
            raise ValidationError("disagreement_tolerance cannot be negative")
        self.disagreement_tolerance = disagreement_tolerance

    def combine(
        self,
        observations: Iterable[VariantEffectObservation],
    ) -> tuple[EnsembleDelta, ...]:
        grouped: dict[str, list[VariantEffectObservation]] = defaultdict(list)
        for observation in observations:
            grouped[observation.variant_id].append(observation)
        results: list[EnsembleDelta] = []
        for variant_id in sorted(grouped):
            rows = tuple(grouped[variant_id])
            deltas = tuple(row.delta for row in rows)
            mean_delta = sum(deltas) / len(deltas)
            disagreement = max(deltas) - min(deltas)
            if len(rows) == 1:
                state = SequenceAdapterState.PARTIAL
            elif disagreement > self.disagreement_tolerance:
                state = SequenceAdapterState.AMBIGUOUS
            else:
                state = SequenceAdapterState.SUPPORTED
            limitations = (
                "Ensemble delta is a model-output comparison, not a probability "
                "of regulatory effect.",
                "External calibration and negative-control performance are not "
                "established by this adapter.",
            )
            body = {
                "variant_id": variant_id,
                "observation_ids": tuple(row.observation_id for row in rows),
                "mean_delta": mean_delta,
                "disagreement": disagreement,
                "state": state,
            }
            results.append(
                EnsembleDelta(
                    variant_id=variant_id,
                    state=state,
                    observation_ids=tuple(row.observation_id for row in rows),
                    model_ids=tuple(sorted({row.model_id for row in rows})),
                    mean_delta=round(mean_delta, 9),
                    disagreement=round(disagreement, 9),
                    context_length_min=min(row.context_length for row in rows),
                    limitations=limitations,
                    content_address=content_hash(body),
                )
            )
        return tuple(results)


__all__ = [
    "EnsembleDelta",
    "LongContextVariantEffectAdapter",
    "RegulatoryTrackDeltaEnsemble",
    "SequenceAdapterIssue",
    "SequenceAdapterState",
    "SequenceContextEncoder",
    "SequenceFeatureVector",
    "SequenceFoundationModelAdapter",
    "VariantEffectBatch",
    "VariantEffectObservation",
]
