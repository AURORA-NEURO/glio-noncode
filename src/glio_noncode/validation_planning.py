"""Evidence-gap and reporter-assay validation planning contracts.

Domain 13 turns unresolved evidence into bounded review packages.  MPRA and
STARR-seq planners generate sequence constructs and controls only when the
declared context, model system, insert bounds, and allele checks pass.  A
package is a research design artifact, not an efficacy, safety, or causal
claim.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .causal_reasoning import CausalState, RegulatoryCausalHypothesis
from .errors import ValidationError
from .models import ReferenceContext
from .serialization import content_hash, jsonable


class PlanState(StrEnum):
    """Review state for validation plans and experiment packages."""

    READY_FOR_REVIEW = "ready_for_review"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    ABSTAINED = "abstained"


class ValidationAssay(StrEnum):
    """MVP reporter assays supported by the planners."""

    MPRA = "mpra"
    STARR_SEQ = "starr_seq"


@dataclass(frozen=True, slots=True)
class EvidenceGap:
    """One missing or unresolved evidence requirement."""

    gap_id: str
    category: str
    description: str
    impact: float
    required_channels: tuple[str, ...]
    context_key: str
    source_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.gap_id.strip() or not self.category.strip() or not self.description.strip():
            raise ValidationError("evidence gap identifiers and description are required")
        if not 0.0 <= self.impact <= 1.0:
            raise ValidationError("evidence gap impact must be between 0 and 1")
        if not self.context_key.strip():
            raise ValidationError("evidence gap context_key is required")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GapAnalysis:
    """Evidence gaps ranked for review without silently filling them."""

    hypothesis_id: str
    context_key: str
    state: PlanState
    gaps: tuple[EvidenceGap, ...]
    available_channels: tuple[str, ...]
    priority_order: tuple[str, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class EvidenceGapAnalyzer:
    """Derive explicit planning gaps from a typed causal hypothesis."""

    def analyze(
        self,
        hypothesis: RegulatoryCausalHypothesis,
        *,
        available_channels: Iterable[str] = (),
    ) -> GapAnalysis:
        channels = tuple(sorted(set(str(item) for item in available_channels)))
        gaps: list[EvidenceGap] = []
        for index, missing in enumerate(hypothesis.missing_evidence, start=1):
            gaps.append(
                EvidenceGap(
                    gap_id=f"{hypothesis.hypothesis_id}:missing:{index}",
                    category=missing,
                    description=f"Resolve missing hypothesis evidence: {missing}.",
                    impact=0.85,
                    required_channels=(missing,),
                    context_key=hypothesis.context_key,
                    source_ids=(),
                )
            )
        if hypothesis.contradictory_edges:
            gaps.append(
                EvidenceGap(
                    gap_id=f"{hypothesis.hypothesis_id}:contradiction",
                    category="contradiction",
                    description=(
                        "Adjudicate contradictory factor-graph edges before causal follow-up."
                    ),
                    impact=1.0,
                    required_channels=("review",),
                    context_key=hypothesis.context_key,
                )
            )
        if hypothesis.uncertainty >= 0.5:
            gaps.append(
                EvidenceGap(
                    gap_id=f"{hypothesis.hypothesis_id}:uncertainty",
                    category="uncertainty",
                    description=(
                        "Reduce high uncertainty with context-matched measurements and controls."
                    ),
                    impact=round(hypothesis.uncertainty, 6),
                    required_channels=("measurement", "negative_control"),
                    context_key=hypothesis.context_key,
                )
            )
        if not gaps and hypothesis.state != CausalState.SUPPORTED:
            gaps.append(
                EvidenceGap(
                    gap_id=f"{hypothesis.hypothesis_id}:state",
                    category="state",
                    description=(
                        "Hypothesis state is not supported; route to review before assay design."
                    ),
                    impact=1.0,
                    required_channels=("review",),
                    context_key=hypothesis.context_key,
                )
            )
        ordered = tuple(
            gap.gap_id
            for gap in sorted(gaps, key=lambda item: (-item.impact, item.gap_id))
        )
        state = PlanState.PARTIAL if gaps else PlanState.READY_FOR_REVIEW
        warnings = (
            "Gap analysis identifies design needs; it does not prove that a later assay "
            "will validate the hypothesis.",
        )
        if not gaps:
            warnings += ("No declared gap remains in the supplied hypothesis snapshot.",)
        body = {
            "hypothesis": hypothesis,
            "channels": channels,
            "gaps": tuple(gaps),
            "state": state,
        }
        return GapAnalysis(
            hypothesis_id=hypothesis.hypothesis_id,
            context_key=hypothesis.context_key,
            state=state,
            gaps=tuple(gaps),
            available_channels=channels,
            priority_order=ordered,
            warnings=warnings,
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class AssayConstraints:
    """Declared constraints that an assay route must satisfy."""

    constraint_id: str
    context_key: str
    model_system: str
    min_insert_length: int
    max_insert_length: int
    max_constructs: int
    required_controls: tuple[str, ...]
    required_readouts: tuple[str, ...]
    require_both_alleles: bool = True

    def __post_init__(self) -> None:
        if (
            not self.constraint_id.strip()
            or not self.context_key.strip()
            or not self.model_system.strip()
        ):
            raise ValidationError("assay constraint identifiers are required")
        if self.min_insert_length < 1 or self.max_insert_length < self.min_insert_length:
            raise ValidationError("assay insert length bounds are invalid")
        if self.max_constructs < 1:
            raise ValidationError("max_constructs must be positive")
        if not self.required_controls or not self.required_readouts:
            raise ValidationError("assay constraints require controls and readouts")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AssayCapability:
    """Available assay/model capability supplied by an inventory snapshot."""

    assay: ValidationAssay
    model_systems: tuple[str, ...]
    min_insert_length: int
    max_insert_length: int
    controls: tuple[str, ...]
    readouts: tuple[str, ...]
    source_id: str
    feasibility: float

    def __post_init__(self) -> None:
        if not self.model_systems or not self.controls or not self.readouts:
            raise ValidationError("assay capability requires models, controls, and readouts")
        if self.min_insert_length < 1 or self.max_insert_length < self.min_insert_length:
            raise ValidationError("assay capability insert bounds are invalid")
        if not 0.0 <= self.feasibility <= 1.0:
            raise ValidationError("assay feasibility must be between 0 and 1")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AssayRoute:
    """Eligibility route with blockers, alternatives, and sensitivity notes."""

    route_id: str
    assay: ValidationAssay
    state: PlanState
    model_system: str
    satisfied_constraints: tuple[str, ...]
    blockers: tuple[str, ...]
    alternatives: tuple[str, ...]
    sensitivity: Mapping[str, str]
    feasibility: float
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class AssayEligibilityRouter:
    """Route assays against explicit constraints instead of guessing suitability."""

    def route(
        self,
        constraints: AssayConstraints,
        inventory: Iterable[AssayCapability],
        *,
        assay: ValidationAssay,
    ) -> tuple[AssayRoute, ...]:
        values = tuple(capability for capability in inventory if capability.assay == assay)
        routes: list[AssayRoute] = []
        for index, capability in enumerate(values, start=1):
            blockers: list[str] = []
            satisfied: list[str] = []
            if constraints.model_system in capability.model_systems:
                satisfied.append("model_system")
            else:
                blockers.append("model_system_not_available")
            if (
                constraints.min_insert_length >= capability.min_insert_length
                and constraints.max_insert_length <= capability.max_insert_length
            ):
                satisfied.append("insert_length_range")
            else:
                blockers.append("insert_length_range_not_supported")
            missing_controls = sorted(set(constraints.required_controls) - set(capability.controls))
            if missing_controls:
                blockers.append("missing_controls:" + ",".join(missing_controls))
            else:
                satisfied.append("controls")
            missing_readouts = sorted(set(constraints.required_readouts) - set(capability.readouts))
            if missing_readouts:
                blockers.append("missing_readouts:" + ",".join(missing_readouts))
            else:
                satisfied.append("readouts")
            state = PlanState.READY_FOR_REVIEW if not blockers else PlanState.BLOCKED
            routes.append(
                AssayRoute(
                    route_id=f"{assay.value}:{index}",
                    assay=assay,
                    state=state,
                    model_system=constraints.model_system,
                    satisfied_constraints=tuple(satisfied),
                    blockers=tuple(blockers),
                    alternatives=tuple(
                        sorted(
                            f"{item.assay.value}:{item.model_systems[0]}"
                            for item in values
                            if item is not capability and item.model_systems
                        )
                    ),
                    sensitivity={
                        "model_system": "route changes if the declared model is unavailable",
                        "insert_length": "route changes if target sequence exceeds assay bounds",
                    },
                    feasibility=capability.feasibility,
                    rationale=(
                        "Eligibility is a constraint check for research review; it does not "
                        "establish assay success."
                    ),
                )
            )
        if not routes:
            routes.append(
                AssayRoute(
                    route_id=f"{assay.value}:none",
                    assay=assay,
                    state=PlanState.ABSTAINED,
                    model_system=constraints.model_system,
                    satisfied_constraints=(),
                    blockers=("assay_not_present_in_inventory",),
                    alternatives=(),
                    sensitivity={},
                    feasibility=0.0,
                    rationale="No inventory capability was supplied for this assay.",
                )
            )
        return tuple(
            sorted(
                routes,
                key=lambda item: (
                    item.state != PlanState.READY_FOR_REVIEW,
                    -item.feasibility,
                    item.route_id,
                ),
            )
        )


@dataclass(frozen=True, slots=True)
class ValidationTarget:
    """One allele-aware target sequence for a reporter design."""

    target_id: str
    variant_id: str
    element_id: str
    sequence: str
    variant_offset: int
    reference_allele: str
    alternate_allele: str
    context: ReferenceContext
    source_id: str

    def __post_init__(self) -> None:
        for name in ("target_id", "variant_id", "element_id", "sequence", "source_id"):
            if not str(getattr(self, name)).strip():
                raise ValidationError(f"validation target {name} is required")
        sequence = self.sequence.upper()
        if any(base not in "ACGTN" for base in sequence):
            raise ValidationError("validation target sequence contains unsupported bases")
        if (
            self.variant_offset < 0
            or self.variant_offset + len(self.reference_allele) > len(sequence)
        ):
            raise ValidationError("validation target allele offset is outside the sequence")
        observed = sequence[self.variant_offset : self.variant_offset + len(self.reference_allele)]
        if observed != self.reference_allele.upper():
            raise ValidationError("validation target reference allele does not match sequence")

    @property
    def alternate_sequence(self) -> str:
        return (
            self.sequence[: self.variant_offset]
            + self.alternate_allele.upper()
            + self.sequence[self.variant_offset + len(self.reference_allele) :]
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"alternate_sequence": self.alternate_sequence}


@dataclass(frozen=True, slots=True)
class ExperimentConstruct:
    """One allele/control construct in an experiment package."""

    construct_id: str
    assay: ValidationAssay
    target_id: str
    allele: str
    sequence: str
    is_control: bool
    control_type: str | None
    context_key: str
    source_id: str
    notes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.construct_id.strip() or not self.target_id.strip() or not self.sequence.strip():
            raise ValidationError("construct identifiers and sequence are required")
        if self.allele not in {"reference", "alternate", "control"}:
            raise ValidationError("construct allele must be reference, alternate, or control")
        if self.is_control != (self.allele == "control"):
            raise ValidationError("construct control flag does not match allele")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ExperimentPackage:
    """Review package containing constructs, controls, and blockers."""

    package_id: str
    assay: ValidationAssay
    context_key: str
    state: PlanState
    targets: tuple[str, ...]
    constructs: tuple[ExperimentConstruct, ...]
    controls: tuple[str, ...]
    readouts: tuple[str, ...]
    blockers: tuple[str, ...]
    alternatives: tuple[str, ...]
    sensitivity: Mapping[str, str]
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class _ReporterDesignPlanner:
    assay: ValidationAssay

    def plan(
        self,
        targets: Iterable[ValidationTarget],
        constraints: AssayConstraints,
    ) -> ExperimentPackage:
        values = tuple(targets)
        if constraints.context_key.strip() == "":
            raise ValidationError("assay constraints require context")
        blockers: list[str] = []
        constructs: list[ExperimentConstruct] = []
        for target in values:
            if target.context.key != constraints.context_key:
                blockers.append(f"{target.target_id}:context_mismatch")
                continue
            length = len(target.sequence)
            if not constraints.min_insert_length <= length <= constraints.max_insert_length:
                blockers.append(f"{target.target_id}:insert_length")
                continue
            constructs.extend(self._constructs(target, constraints))
        if len(constructs) > constraints.max_constructs:
            blockers.append("max_constructs_exceeded")
        if not values:
            blockers.append("no_validation_targets")
        if blockers:
            state = PlanState.BLOCKED
        elif not constructs:
            state = PlanState.ABSTAINED
        else:
            state = PlanState.READY_FOR_REVIEW
        package_id = f"{self.assay.value}:{constraints.constraint_id}"
        body = {
            "package_id": package_id,
            "assay": self.assay,
            "context": constraints.context_key,
            "targets": values,
            "constructs": tuple(constructs),
            "state": state,
            "blockers": tuple(blockers),
        }
        return ExperimentPackage(
            package_id=package_id,
            assay=self.assay,
            context_key=constraints.context_key,
            state=state,
            targets=tuple(target.target_id for target in values),
            constructs=tuple(constructs),
            controls=constraints.required_controls,
            readouts=constraints.required_readouts,
            blockers=tuple(dict.fromkeys(blockers)),
            alternatives=(
                "Re-route to another assay or model system after human review.",
                "Reduce target count or split the package when the construct budget is exceeded.",
            ),
            sensitivity={
                "construct_budget": "state changes when max_constructs is increased or decreased",
                "insert_bounds": "targets outside assay insert bounds remain blocked",
                "allele_pair": "reference/alternate pairing can be disabled only by "
                "explicit review",
            },
            limitations=(
                "Construct generation does not establish expression, effect size, or assay "
                "success.",
                "Sequence synthesis, cloning, cell model, randomization, and batch controls "
                "require expert review.",
            ),
            content_address=content_hash(body),
        )

    def _constructs(
        self,
        target: ValidationTarget,
        constraints: AssayConstraints,
    ) -> tuple[ExperimentConstruct, ...]:
        values = [
            ExperimentConstruct(
                construct_id=content_hash(
                    {"assay": self.assay, "target": target.target_id, "allele": "reference"},
                    prefix="construct",
                ),
                assay=self.assay,
                target_id=target.target_id,
                allele="reference",
                sequence=target.sequence.upper(),
                is_control=False,
                control_type=None,
                context_key=target.context.key,
                source_id=target.source_id,
                notes=(
                    "Reference allele construct; sequence identity must be rechecked before "
                    "synthesis.",
                ),
            )
        ]
        if constraints.require_both_alleles:
            values.append(
                ExperimentConstruct(
                    construct_id=content_hash(
                        {"assay": self.assay, "target": target.target_id, "allele": "alternate"},
                        prefix="construct",
                    ),
                    assay=self.assay,
                    target_id=target.target_id,
                    allele="alternate",
                    sequence=target.alternate_sequence,
                    is_control=False,
                    control_type=None,
                    context_key=target.context.key,
                    source_id=target.source_id,
                    notes=(
                        "Alternate allele construct; edit interpretation remains "
                        "assay-dependent.",
                    ),
                )
            )
        return tuple(values)


class MPRAPlanner(_ReporterDesignPlanner):
    """Plan bounded MPRA allele constructs."""

    assay = ValidationAssay.MPRA


class STARRSeqPlanner(_ReporterDesignPlanner):
    """Plan bounded STARR-seq allele constructs."""

    assay = ValidationAssay.STARR_SEQ


@dataclass(frozen=True, slots=True)
class ValidationPlan:
    """Combined gap, route, and experiment-package review artifact."""

    plan_id: str
    context_key: str
    state: PlanState
    gap_analysis: GapAnalysis
    routes: tuple[AssayRoute, ...]
    packages: tuple[ExperimentPackage, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ValidationPlanBuilder:
    """Assemble validation components and retain the weakest review state."""

    def build(
        self,
        plan_id: str,
        gap_analysis: GapAnalysis,
        routes: Iterable[AssayRoute],
        packages: Iterable[ExperimentPackage],
    ) -> ValidationPlan:
        route_values = tuple(routes)
        package_values = tuple(packages)
        states = [gap_analysis.state] + [route.state for route in route_values] + [
            package.state for package in package_values
        ]
        if PlanState.BLOCKED in states:
            state = PlanState.BLOCKED
        elif PlanState.ABSTAINED in states:
            state = PlanState.ABSTAINED
        elif PlanState.PARTIAL in states:
            state = PlanState.PARTIAL
        else:
            state = PlanState.READY_FOR_REVIEW
        body = {
            "plan_id": plan_id,
            "context": gap_analysis.context_key,
            "gap_analysis": gap_analysis,
            "routes": route_values,
            "packages": package_values,
            "state": state,
        }
        return ValidationPlan(
            plan_id=plan_id,
            context_key=gap_analysis.context_key,
            state=state,
            gap_analysis=gap_analysis,
            routes=route_values,
            packages=package_values,
            warnings=(
                "Validation plans require human review, experimental controls, and "
                "institutional approvals before execution.",
            ),
            content_address=content_hash(body),
        )


__all__ = [
    "AssayCapability",
    "AssayConstraints",
    "AssayEligibilityRouter",
    "AssayRoute",
    "EvidenceGap",
    "EvidenceGapAnalyzer",
    "ExperimentConstruct",
    "ExperimentPackage",
    "GapAnalysis",
    "MPRAPlanner",
    "PlanState",
    "STARRSeqPlanner",
    "ValidationAssay",
    "ValidationPlan",
    "ValidationPlanBuilder",
    "ValidationTarget",
]
