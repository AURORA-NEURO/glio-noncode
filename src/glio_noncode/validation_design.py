"""Validation routing, guide enumeration, and research power planning."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .data_sources import SequenceSlice
from .errors import ValidationError
from .models import AssayType, ExperimentOption, Hypothesis, VariantIdentity
from .serialization import content_hash, jsonable
from .uncertainty import UncertaintyReport


class DesignStatus(StrEnum):
    """Outcome of deterministic design generation."""

    READY_FOR_REVIEW = "ready_for_review"
    ABSTAINED = "abstained"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class ValidationRoute:
    """One ranked research validation route."""

    route_id: str
    assay: AssayType
    tests_edge_ids: tuple[str, ...]
    priority: float
    rationale: str
    controls: tuple[str, ...]
    readouts: tuple[str, ...]
    blockers: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class AssayRouter:
    """Rank existing assay options against explicit uncertainty components."""

    def route(
        self,
        hypothesis: Hypothesis,
        options: Iterable[ExperimentOption],
        uncertainty: UncertaintyReport,
    ) -> tuple[ValidationRoute, ...]:
        edge_ids = {edge.edge_id for edge in hypothesis.edges}
        routes: list[ValidationRoute] = []
        for option in options:
            tested = tuple(edge_id for edge_id in option.tests_edges if edge_id in edge_ids)
            if not tested:
                continue
            priority = round(option.priority * max(0.1, uncertainty.overall), 6)
            blockers: list[str] = []
            if uncertainty.band.value == "abstain":
                blockers.append(
                    "uncertainty report is abstained; resolve missing domain inputs first"
                )
            routes.append(
                ValidationRoute(
                    route_id=option.option_id,
                    assay=option.assay,
                    tests_edge_ids=tested,
                    priority=priority,
                    rationale=(
                        f"{option.assay.value} targets {len(tested)} declared edges; "
                        "priority combines option value, feasibility, and unresolved uncertainty."
                    ),
                    controls=option.controls,
                    readouts=option.readouts,
                    blockers=tuple(blockers),
                )
            )
        return tuple(sorted(routes, key=lambda route: (-route.priority, route.route_id)))


@dataclass(frozen=True, slots=True)
class GuideCandidate:
    """One protospacer/PAM candidate with unassessed off-target status."""

    guide_id: str
    sequence: str
    chromosome: str
    start: int
    end: int
    strand: str
    pam: str
    target_variant_id: str
    gc_fraction: float
    off_target_status: str = "unassessed"
    limitations: tuple[str, ...] = (
        (
            "Off-target status requires a reference-aware search and is not "
            "inferred from this local window."
        ),
        "Guide presence does not establish editing efficiency or assay suitability.",
    )

    def __post_init__(self) -> None:
        if self.start < 1 or self.end < self.start:
            raise ValidationError("guide interval is invalid")
        if self.strand not in {"+", "-"}:
            raise ValidationError("guide strand must be + or -")
        if self.off_target_status not in {"unassessed", "checked", "blocked"}:
            raise ValidationError("guide off_target_status is invalid")
        if not 0.0 <= self.gc_fraction <= 1.0:
            raise ValidationError("guide GC fraction must be between 0 and 1")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GuideDesignResult:
    """Guide enumeration result, including source window and blockers."""

    target_variant_id: str
    status: DesignStatus
    source_id: str
    window: tuple[str, int, int]
    candidates: tuple[GuideCandidate, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class GuideDesigner:
    """Enumerate SpCas9-like NGG candidates without claiming efficacy."""

    def design(
        self,
        variant: VariantIdentity,
        sequence: SequenceSlice,
        *,
        protospacer_length: int = 20,
        pam_pattern: str = "NGG",
        max_candidates: int = 50,
    ) -> GuideDesignResult:
        if protospacer_length < 10 or protospacer_length > 40:
            raise ValidationError("protospacer_length must be between 10 and 40")
        if pam_pattern != "NGG":
            raise ValidationError("the initial guide designer supports only the explicit NGG PAM")
        if max_candidates < 1 or max_candidates > 1000:
            raise ValidationError("max_candidates must be between 1 and 1000")
        if variant.chromosome != sequence.chromosome:
            return self._blocked(variant, sequence, "variant and sequence contigs do not match")
        if variant.start < sequence.start or variant.end > sequence.end:
            return self._blocked(
                variant, sequence, "variant interval is outside the retrieved sequence window"
            )
        offset = variant.start - sequence.start
        observed = sequence.sequence[offset : offset + len(variant.reference)].upper()
        if observed != variant.reference.upper():
            return self._blocked(
                variant,
                sequence,
                f"retrieved reference {observed!r} does not match declared {variant.reference!r}",
            )
        reference = sequence.sequence.upper()
        candidates: list[GuideCandidate] = []
        for index in range(0, len(reference) - protospacer_length - 3 + 1):
            pam = reference[index + protospacer_length : index + protospacer_length + 3]
            if pam[1:] != "GG":
                continue
            guide_start = sequence.start + index
            guide_end = guide_start + protospacer_length - 1
            if not (guide_start <= variant.start <= guide_end):
                continue
            candidates.append(
                self._candidate(
                    variant,
                    sequence,
                    reference[index : index + protospacer_length],
                    guide_start,
                    guide_end,
                    "+",
                    pam,
                )
            )
        reverse = _reverse_complement(reference)
        for index in range(0, len(reverse) - protospacer_length - 3 + 1):
            pam = reverse[index + protospacer_length : index + protospacer_length + 3]
            if pam[1:] != "GG":
                continue
            reverse_guide = reverse[index : index + protospacer_length]
            forward_start = sequence.end - (index + protospacer_length - 1)
            forward_end = forward_start + protospacer_length - 1
            if not (forward_start <= variant.start <= forward_end):
                continue
            candidates.append(
                self._candidate(
                    variant,
                    sequence,
                    reverse_guide,
                    forward_start,
                    forward_end,
                    "-",
                    pam,
                )
            )
        candidates = sorted(
            candidates,
            key=lambda candidate: (
                abs(candidate.start - variant.start),
                candidate.strand,
                candidate.sequence,
            ),
        )[:max_candidates]
        warnings = (
            (
                "Candidates are local sequence designs only; off-target search, guide "
                "synthesis, and assay validation are not performed."
            ),
        )
        status = DesignStatus.READY_FOR_REVIEW if candidates else DesignStatus.ABSTAINED
        if not candidates:
            warnings += (
                "No NGG guide spanning the declared variant was found in the retrieved window.",
            )
        payload = {
            "variant_id": variant.variant_id,
            "window": (sequence.chromosome, sequence.start, sequence.end),
            "candidates": candidates,
            "status": status,
        }
        return GuideDesignResult(
            target_variant_id=variant.variant_id,
            status=status,
            source_id=sequence.source_id,
            window=(sequence.chromosome, sequence.start, sequence.end),
            candidates=tuple(candidates),
            warnings=warnings,
            content_address=content_hash(payload),
        )

    @staticmethod
    def _candidate(
        variant: VariantIdentity,
        sequence: SequenceSlice,
        guide: str,
        start: int,
        end: int,
        strand: str,
        pam: str,
    ) -> GuideCandidate:
        guide_id = (
            "guide-"
            + content_hash(
                {"variant": variant.variant_id, "sequence": guide, "start": start, "strand": strand}
            ).split(":", 1)[1][:20]
        )
        return GuideCandidate(
            guide_id=guide_id,
            sequence=guide,
            chromosome=sequence.chromosome,
            start=start,
            end=end,
            strand=strand,
            pam=pam,
            target_variant_id=variant.variant_id,
            gc_fraction=round(sum(base in "GC" for base in guide) / len(guide), 6),
        )

    @staticmethod
    def _blocked(
        variant: VariantIdentity, sequence: SequenceSlice, reason: str
    ) -> GuideDesignResult:
        payload = {
            "variant_id": variant.variant_id,
            "window": (sequence.chromosome, sequence.start, sequence.end),
            "reason": reason,
        }
        return GuideDesignResult(
            target_variant_id=variant.variant_id,
            status=DesignStatus.BLOCKED,
            source_id=sequence.source_id,
            window=(sequence.chromosome, sequence.start, sequence.end),
            candidates=(),
            warnings=(
                reason,
                "Guide design did not proceed; no negative assay conclusion was made.",
            ),
            content_address=content_hash(payload),
        )


@dataclass(frozen=True, slots=True)
class PowerPlan:
    """Approximate two-group planning envelope with declared assumptions."""

    effect_size: float
    baseline_rate: float
    alpha: float
    target_power: float
    samples_per_group: int
    total_samples: int
    controls: tuple[str, ...]
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class PowerPlanner:
    """Use a transparent normal approximation for early research planning."""

    _z = {0.80: 0.8416, 0.85: 1.0364, 0.90: 1.2816, 0.95: 1.6449, 0.975: 1.96, 0.99: 2.3263}

    def plan(
        self,
        *,
        effect_size: float,
        baseline_rate: float = 0.5,
        alpha: float = 0.05,
        target_power: float = 0.80,
        controls: Iterable[str] = (),
    ) -> PowerPlan:
        if effect_size <= 0:
            raise ValidationError("effect_size must be positive")
        for name, value in (
            ("baseline_rate", baseline_rate),
            ("alpha", alpha),
            ("target_power", target_power),
        ):
            if not 0.0 < value < 1.0:
                raise ValidationError(f"{name} must be between 0 and 1")
        z_power = self._z.get(round(target_power, 3))
        if z_power is None:
            raise ValidationError(
                "target_power must be one of the supported planning values: "
                "0.80, 0.85, 0.90, 0.95, 0.975, 0.99"
            )
        z_alpha = 1.96 if alpha <= 0.05 else 1.6449
        variance = 2.0 * baseline_rate * (1.0 - baseline_rate)
        samples = math.ceil(variance * ((z_alpha + z_power) / effect_size) ** 2)
        samples = max(2, samples)
        control_values = tuple(dict.fromkeys(controls)) or (
            "negative_control",
            "positive_control",
            "technical_replicates",
        )
        payload = {
            "effect_size": effect_size,
            "baseline_rate": baseline_rate,
            "alpha": alpha,
            "target_power": target_power,
            "samples_per_group": samples,
            "controls": control_values,
        }
        return PowerPlan(
            effect_size=effect_size,
            baseline_rate=baseline_rate,
            alpha=alpha,
            target_power=target_power,
            samples_per_group=samples,
            total_samples=samples * 2,
            controls=control_values,
            limitations=(
                (
                    "Normal approximation is a planning envelope, not a finalized "
                    "statistical analysis."
                ),
                (
                    "Dispersion, batch effects, dropout, multiple testing, and "
                    "assay-specific variance are not estimated here."
                ),
            ),
            content_address=content_hash(payload),
        )


def _reverse_complement(sequence: str) -> str:
    complement = str.maketrans("ACGTN", "TGCAN")
    return sequence.translate(complement)[::-1]
