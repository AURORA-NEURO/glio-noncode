"""Scientific-beta perturbation and allele-specific reporter planners.

The validation-beta layer turns context-qualified sequence targets into
reviewable CRISPRi/CRISPRa, base-editing, prime-editing, and allele-specific
reporter design packages. Candidate generation is deterministic and keeps the
declared sequence, edit, guide window, model/version receipt, control
requirements, budget, and blockers together.

The planners are design aids. Guide scores are transparent heuristics, not
validated activity or specificity predictions. A ready package still requires
sequence rechecking, off-target analysis, synthesis checks, controls, model
system review, institutional approvals, and experimental validation.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty


class ValidationBetaState(StrEnum):
    """Review state for validation-beta design packages."""

    READY_FOR_REVIEW = "ready_for_review"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    AMBIGUOUS = "ambiguous"
    ABSTAINED = "abstained"


class PerturbationMode(StrEnum):
    """Design family supported by this beta layer."""

    CRISPRI = "crispri"
    CRISPRA = "crispra"
    BASE_EDITING = "base_editing"
    PRIME_EDITING = "prime_editing"
    ALLELE_SPECIFIC_REPORTER = "allele_specific_reporter"


class GuideStrand(StrEnum):
    FORWARD = "forward"
    REVERSE = "reverse"


@dataclass(frozen=True, slots=True)
class ValidationBetaIssue:
    """A structured design input issue or non-fatal package warning."""

    code: str
    message: str
    raw_hash: str
    target_id: str | None = None
    severity: str = "warning"
    raw_record: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty(self.code, "validation beta issue code")
        require_non_empty(self.message, "validation beta issue message")
        require_non_empty(self.raw_hash, "validation beta issue raw_hash")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationBetaTarget:
    """A context-qualified sequence target with an explicit allele edit."""

    target_id: str
    variant_id: str
    element_id: str
    sequence: str
    variant_offset: int
    reference_allele: str
    alternate_allele: str
    context_key: str
    source_id: str
    source_version: str = "unspecified"
    raw_hash: str = "unspecified"
    gene_id: str | None = None
    annotations: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "target_id",
            "variant_id",
            "element_id",
            "sequence",
            "reference_allele",
            "alternate_allele",
            "context_key",
            "source_id",
            "source_version",
            "raw_hash",
        ):
            require_non_empty(str(getattr(self, name)), name)
        sequence = self.sequence.upper()
        if any(base not in "ACGTN" for base in sequence):
            raise ValidationError("validation beta target sequence contains unsupported bases")
        if self.variant_offset < 0 or self.variant_offset + len(self.reference_allele) > len(
            sequence
        ):
            raise ValidationError("validation beta target variant offset is outside the sequence")
        observed = sequence[self.variant_offset : self.variant_offset + len(self.reference_allele)]
        if observed != self.reference_allele.upper():
            raise ValidationError("validation beta target reference allele does not match sequence")

    @property
    def alternate_sequence(self) -> str:
        return (
            self.sequence.upper()[: self.variant_offset]
            + self.alternate_allele.upper()
            + self.sequence.upper()[self.variant_offset + len(self.reference_allele) :]
        )

    @classmethod
    def from_mapping(
        cls,
        raw: Mapping[str, Any],
        *,
        default_context_key: str | None = None,
        default_source_id: str = "validation-input",
        default_source_version: str = "unspecified",
    ) -> ValidationBetaTarget:
        if not isinstance(raw, Mapping):
            raise ValidationError("validation beta target must be an object")
        return cls(
            target_id=str(raw.get("target_id", raw.get("id", ""))),
            variant_id=str(raw.get("variant_id", raw.get("variant", ""))),
            element_id=str(raw.get("element_id", raw.get("element", ""))),
            sequence=str(raw.get("sequence", "")),
            variant_offset=int(raw.get("variant_offset", raw.get("offset", -1))),
            reference_allele=str(raw.get("reference_allele", raw.get("reference", ""))),
            alternate_allele=str(raw.get("alternate_allele", raw.get("alternate", ""))),
            context_key=str(raw.get("context_key", raw.get("context", default_context_key or ""))),
            source_id=str(raw.get("source_id", default_source_id)),
            source_version=str(
                raw.get("source_version", raw.get("version", default_source_version))
            ),
            raw_hash=str(raw.get("raw_hash", content_hash(dict(raw)))),
            gene_id=(str(raw["gene_id"]) if raw.get("gene_id") not in (None, "") else None),
            annotations=dict(raw.get("annotations", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"alternate_sequence": self.alternate_sequence}


@dataclass(frozen=True, slots=True)
class GuideDesignConstraints:
    """Explicit sequence, scoring, edit-window, and budget constraints."""

    design_id: str
    context_key: str
    mode: PerturbationMode
    guide_length: int = 20
    max_guides: int = 4
    minimum_on_target: float = 0.40
    minimum_specificity: float = 0.70
    maximum_off_target: float = 0.30
    require_variant_overlap: bool = True
    require_pam: bool = False
    pam_pattern: str = "NGG"
    editing_window_start: int = 4
    editing_window_end: int = 8
    pbs_length: int = 13
    rtt_length: int = 20
    maximum_edit_length: int = 50
    control_requirements: tuple[str, ...] = ("non_targeting", "positive_control")
    readout_requirements: tuple[str, ...] = ("editing_rate", "viability")
    model_system: str = "declared_model"

    def __post_init__(self) -> None:
        for name in ("design_id", "context_key", "pam_pattern", "model_system"):
            require_non_empty(str(getattr(self, name)), name)
        if self.guide_length < 1 or self.max_guides < 1:
            raise ValidationError("guide_length and max_guides must be positive")
        for name, value in (
            ("minimum_on_target", self.minimum_on_target),
            ("minimum_specificity", self.minimum_specificity),
            ("maximum_off_target", self.maximum_off_target),
        ):
            if not 0 <= value <= 1:
                raise ValidationError(f"{name} must be between zero and one")
        if self.editing_window_start < 0 or self.editing_window_end < self.editing_window_start:
            raise ValidationError("editing window bounds are invalid")
        if self.pbs_length < 1 or self.rtt_length < 1 or self.maximum_edit_length < 1:
            raise ValidationError("prime-editing lengths must be positive")
        if not self.control_requirements or not self.readout_requirements:
            raise ValidationError("validation beta constraints require controls and readouts")

    @classmethod
    def from_mapping(
        cls,
        raw: Mapping[str, Any],
        *,
        context_key: str | None = None,
        mode: PerturbationMode | str | None = None,
    ) -> GuideDesignConstraints:
        if not isinstance(raw, Mapping):
            raise ValidationError("validation beta constraints must be an object")
        selected_mode = mode or raw.get("mode", PerturbationMode.CRISPRI.value)
        return cls(
            design_id=str(raw.get("design_id", raw.get("id", "validation-beta"))),
            context_key=str(raw.get("context_key", context_key or "")),
            mode=PerturbationMode(str(selected_mode)),
            guide_length=int(raw.get("guide_length", 20)),
            max_guides=int(raw.get("max_guides", 4)),
            minimum_on_target=float(raw.get("minimum_on_target", 0.40)),
            minimum_specificity=float(raw.get("minimum_specificity", 0.70)),
            maximum_off_target=float(raw.get("maximum_off_target", 0.30)),
            require_variant_overlap=_as_bool(raw.get("require_variant_overlap"), default=True),
            require_pam=_as_bool(raw.get("require_pam"), default=False),
            pam_pattern=str(raw.get("pam_pattern", "NGG")),
            editing_window_start=int(raw.get("editing_window_start", 4)),
            editing_window_end=int(raw.get("editing_window_end", 8)),
            pbs_length=int(raw.get("pbs_length", 13)),
            rtt_length=int(raw.get("rtt_length", 20)),
            maximum_edit_length=int(raw.get("maximum_edit_length", 50)),
            control_requirements=tuple(
                str(item)
                for item in raw.get("control_requirements", ("non_targeting", "positive_control"))
            ),
            readout_requirements=tuple(
                str(item) for item in raw.get("readout_requirements", ("editing_rate", "viability"))
            ),
            model_system=str(raw.get("model_system", "declared_model")),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GuideCandidate:
    """One deterministic guide or pegRNA candidate."""

    guide_id: str
    target_id: str
    mode: PerturbationMode
    guide_sequence: str
    strand: GuideStrand
    start_offset: int
    variant_overlap: bool
    pam: str | None
    on_target_score: float
    specificity_score: float
    off_target_score: float
    source_id: str
    source_version: str
    raw_hash: str
    pbs_sequence: str | None = None
    rtt_sequence: str | None = None
    edit_payload: str | None = None
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "guide_id",
            "target_id",
            "guide_sequence",
            "source_id",
            "source_version",
            "raw_hash",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if self.start_offset < 0 or not self.guide_sequence:
            raise ValidationError("guide candidate sequence or offset is invalid")
        for name, value in (
            ("on_target_score", self.on_target_score),
            ("specificity_score", self.specificity_score),
            ("off_target_score", self.off_target_score),
        ):
            if not isfinite(value) or not 0 <= value <= 1:
                raise ValidationError(f"{name} must be finite and between zero and one")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GuideDesignPackage:
    """Review package for CRISPR or editing guide designs."""

    package_id: str
    mode: PerturbationMode
    context_key: str
    model_system: str
    state: ValidationBetaState
    target_ids: tuple[str, ...]
    guides: tuple[GuideCandidate, ...]
    controls: tuple[str, ...]
    readouts: tuple[str, ...]
    blockers: tuple[str, ...]
    alternatives: tuple[str, ...]
    sensitivity: Mapping[str, str]
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class _GuideDesignPlanner:
    mode: PerturbationMode

    def plan(
        self,
        targets: Iterable[ValidationBetaTarget | Mapping[str, Any]],
        constraints: GuideDesignConstraints,
    ) -> GuideDesignPackage:
        if constraints.mode != self.mode:
            raise ValidationError(
                f"constraints mode {constraints.mode.value} does not match "
                f"planner {self.mode.value}"
            )
        values = tuple(_coerce_target(item) for item in targets)
        blockers: list[str] = []
        guides: list[GuideCandidate] = []
        for target in values:
            if target.context_key != constraints.context_key:
                blockers.append(f"{target.target_id}:context_mismatch")
                continue
            target_guides, target_blockers = self._plan_target(target, constraints)
            guides.extend(target_guides)
            blockers.extend(target_blockers)
        if len(guides) > constraints.max_guides:
            blockers.append("max_guides_exceeded")
        if not values:
            blockers.append("no_validation_targets")
        if not guides and not blockers:
            blockers.append("no_eligible_guides")
        if blockers:
            state = ValidationBetaState.BLOCKED
        elif len(guides) < min(constraints.max_guides, len(values)):
            state = ValidationBetaState.PARTIAL
        else:
            state = ValidationBetaState.READY_FOR_REVIEW
        package_id = f"{self.mode.value}:{constraints.design_id}"
        return self._package(
            package_id, constraints, values, tuple(guides), tuple(dict.fromkeys(blockers)), state
        )

    def _plan_target(
        self,
        target: ValidationBetaTarget,
        constraints: GuideDesignConstraints,
    ) -> tuple[tuple[GuideCandidate, ...], tuple[str, ...]]:
        sequence = target.sequence.upper()
        if len(sequence) < constraints.guide_length:
            return (), (f"{target.target_id}:sequence_shorter_than_guide",)
        starts = _candidate_starts(target, constraints.guide_length)
        candidates: list[GuideCandidate] = []
        blockers: list[str] = []
        for start in starts:
            guide_sequence = sequence[start : start + constraints.guide_length]
            overlap = _overlaps_variant(
                start,
                start + constraints.guide_length,
                target.variant_offset,
                target.variant_offset + len(target.reference_allele),
            )
            if constraints.require_variant_overlap and not overlap:
                continue
            pam = _pam_for_start(sequence, start, constraints.guide_length, constraints.pam_pattern)
            if constraints.require_pam and pam is None:
                continue
            on_target, specificity, off_target = _heuristic_scores(sequence, guide_sequence)
            if on_target < constraints.minimum_on_target:
                continue
            if (
                specificity < constraints.minimum_specificity
                or off_target > constraints.maximum_off_target
            ):
                continue
            relative = target.variant_offset - start
            if self.mode == PerturbationMode.BASE_EDITING and not (
                constraints.editing_window_start <= relative <= constraints.editing_window_end
            ):
                continue
            pbs, rtt, payload = self._editing_payload(target, start, constraints)
            if self.mode == PerturbationMode.PRIME_EDITING and pbs is None:
                blockers.append(f"{target.target_id}:prime_editing_flank_shortage")
                continue
            guide_id = content_hash(
                {
                    "mode": self.mode,
                    "target": target.target_id,
                    "sequence": guide_sequence,
                    "start": start,
                    "pam": pam,
                    "pbs": pbs,
                    "rtt": rtt,
                },
                prefix="guide",
            )
            candidates.append(
                GuideCandidate(
                    guide_id=guide_id,
                    target_id=target.target_id,
                    mode=self.mode,
                    guide_sequence=guide_sequence,
                    strand=GuideStrand.FORWARD,
                    start_offset=start,
                    variant_overlap=overlap,
                    pam=pam,
                    on_target_score=round(on_target, 9),
                    specificity_score=round(specificity, 9),
                    off_target_score=round(off_target, 9),
                    source_id=target.source_id,
                    source_version=target.source_version,
                    raw_hash=content_hash(
                        {"target": target.raw_hash, "sequence": guide_sequence, "mode": self.mode}
                    ),
                    pbs_sequence=pbs,
                    rtt_sequence=rtt,
                    edit_payload=payload,
                    notes=self._notes(target, relative, pam),
                )
            )
        candidates.sort(
            key=lambda item: (
                -item.specificity_score,
                -item.on_target_score,
                item.start_offset,
                item.guide_id,
            )
        )
        if not candidates:
            blockers.append(f"{target.target_id}:no_candidate_meets_declared_constraints")
        return tuple(candidates), tuple(dict.fromkeys(blockers))

    def _editing_payload(
        self,
        target: ValidationBetaTarget,
        start: int,
        constraints: GuideDesignConstraints,
    ) -> tuple[str | None, str | None, str | None]:
        if self.mode == PerturbationMode.BASE_EDITING:
            if len(target.reference_allele) != 1 or len(target.alternate_allele) != 1:
                return None, None, None
            edit = f"{target.reference_allele.upper()}>{target.alternate_allele.upper()}"
            if edit not in {"C>T", "A>G", "G>A", "T>C"}:
                return None, None, None
            return None, None, edit
        if self.mode != PerturbationMode.PRIME_EDITING:
            return None, None, None
        sequence = target.sequence.upper()
        pbs_start = target.variant_offset - constraints.pbs_length
        if pbs_start < 0:
            return None, None, None
        pbs = sequence[pbs_start : target.variant_offset]
        if len(pbs) != constraints.pbs_length:
            return None, None, None
        edit = target.alternate_allele.upper()
        rtt_tail = sequence[target.variant_offset + len(target.reference_allele) :]
        rtt = (edit + rtt_tail)[: constraints.rtt_length]
        if len(rtt) < len(edit):
            return None, None, None
        if (
            len(target.reference_allele) > constraints.maximum_edit_length
            or len(edit) > constraints.maximum_edit_length
        ):
            return None, None, None
        return pbs, rtt, edit

    def _notes(
        self,
        target: ValidationBetaTarget,
        relative_offset: int,
        pam: str | None,
    ) -> tuple[str, ...]:
        notes = [
            "Candidate is generated from the declared target sequence and must be "
            "rechecked against the reference before use.",
            f"Variant-relative guide offset: {relative_offset}.",
        ]
        if pam is None:
            notes.append(
                "No observed PAM was required; a compatible PAM and orientation must "
                "be validated externally."
            )
        else:
            notes.append(f"Observed declared PAM pattern: {pam}.")
        if self.mode in {PerturbationMode.CRISPRI, PerturbationMode.CRISPRA}:
            notes.append(
                "CRISPRi/a placement is a targeting hypothesis; repression or activation "
                "efficacy is not predicted here."
            )
        if self.mode == PerturbationMode.BASE_EDITING:
            notes.append(
                "Base-editing chemistry and bystander edits require editor-specific validation."
            )
        if self.mode == PerturbationMode.PRIME_EDITING:
            notes.append(
                "PBS and RTT sequences are design placeholders requiring pegRNA and "
                "nicking validation."
            )
        return tuple(notes)

    @staticmethod
    def _package(
        package_id: str,
        constraints: GuideDesignConstraints,
        targets: tuple[ValidationBetaTarget, ...],
        guides: tuple[GuideCandidate, ...],
        blockers: tuple[str, ...],
        state: ValidationBetaState,
    ) -> GuideDesignPackage:
        body = {
            "package_id": package_id,
            "mode": constraints.mode,
            "context_key": constraints.context_key,
            "targets": targets,
            "guides": guides,
            "blockers": blockers,
            "state": state,
        }
        return GuideDesignPackage(
            package_id=package_id,
            mode=constraints.mode,
            context_key=constraints.context_key,
            model_system=constraints.model_system,
            state=state,
            target_ids=tuple(item.target_id for item in targets),
            guides=guides,
            controls=constraints.control_requirements,
            readouts=constraints.readout_requirements,
            blockers=blockers,
            alternatives=(
                "Recheck the target against the current reference and rerun design after "
                "sequence correction.",
                "Change guide length, PAM requirement, or edit window only with explicit review.",
                "Route to an orthogonal assay when no candidate satisfies the declared "
                "constraints.",
            ),
            sensitivity={
                "guide_budget": "state changes when max_guides changes",
                "specificity_threshold": (
                    "candidate set changes with the declared specificity and off-target gates"
                ),
                "context_key": "context mismatch blocks transport of the design",
                "pam_requirement": "requiring an observed PAM can reduce the candidate set to zero",
            },
            limitations=(
                "Heuristic scores are not validated on-target or off-target predictions.",
                "Design packages do not establish perturbation efficacy, allele editing, "
                "safety, or causality.",
                "Controls, editor choice, delivery, sequencing, bystander effects, and "
                "approvals require expert review.",
            ),
            content_address=content_hash(body),
        )


class CRISPRiDesignPlanner(_GuideDesignPlanner):
    """Plan context-qualified CRISPR interference guides."""

    mode = PerturbationMode.CRISPRI


class CRISPRaDesignPlanner(_GuideDesignPlanner):
    """Plan context-qualified CRISPR activation guides."""

    mode = PerturbationMode.CRISPRA


class BaseEditingDesignPlanner(_GuideDesignPlanner):
    """Plan base-editing candidates within a declared editing window."""

    mode = PerturbationMode.BASE_EDITING

    def _plan_target(
        self,
        target: ValidationBetaTarget,
        constraints: GuideDesignConstraints,
    ) -> tuple[tuple[GuideCandidate, ...], tuple[str, ...]]:
        if len(target.reference_allele) != 1 or len(target.alternate_allele) != 1:
            return (), (f"{target.target_id}:base_editing_requires_single_base_substitution",)
        if f"{target.reference_allele.upper()}>{target.alternate_allele.upper()}" not in {
            "C>T",
            "A>G",
            "G>A",
            "T>C",
        }:
            return (), (f"{target.target_id}:unsupported_base_edit_substitution",)
        return super()._plan_target(target, constraints)


class PrimeEditingDesignPlanner(_GuideDesignPlanner):
    """Plan pegRNA-like candidates with declared PBS and RTT lengths."""

    mode = PerturbationMode.PRIME_EDITING

    def _plan_target(
        self,
        target: ValidationBetaTarget,
        constraints: GuideDesignConstraints,
    ) -> tuple[tuple[GuideCandidate, ...], tuple[str, ...]]:
        if (
            len(target.reference_allele) > constraints.maximum_edit_length
            or len(target.alternate_allele) > constraints.maximum_edit_length
        ):
            return (), (f"{target.target_id}:edit_exceeds_prime_editing_length",)
        return super()._plan_target(target, constraints)


@dataclass(frozen=True, slots=True)
class ReporterConstruct:
    """One allele or control reporter construct."""

    construct_id: str
    target_id: str
    allele: str
    sequence: str
    context_key: str
    source_id: str
    is_control: bool
    control_type: str | None
    notes: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("construct_id", "target_id", "allele", "sequence", "context_key", "source_id"):
            require_non_empty(str(getattr(self, name)), name)
        if self.allele not in {"reference", "alternate", "control"}:
            raise ValidationError("reporter construct allele is invalid")
        if self.is_control != (self.allele == "control"):
            raise ValidationError("reporter construct control flag does not match allele")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AlleleSpecificReporterPackage:
    """Review package for reference/alternate reporter constructs."""

    package_id: str
    context_key: str
    model_system: str
    state: ValidationBetaState
    target_ids: tuple[str, ...]
    constructs: tuple[ReporterConstruct, ...]
    controls: tuple[str, ...]
    readouts: tuple[str, ...]
    blockers: tuple[str, ...]
    alternatives: tuple[str, ...]
    sensitivity: Mapping[str, str]
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class AlleleSpecificReporterPlanner:
    """Plan matched reference/alternate reporter constructs."""

    def plan(
        self,
        targets: Iterable[ValidationBetaTarget | Mapping[str, Any]],
        constraints: GuideDesignConstraints,
    ) -> AlleleSpecificReporterPackage:
        if constraints.mode != PerturbationMode.ALLELE_SPECIFIC_REPORTER:
            raise ValidationError("reporter planner requires allele_specific_reporter constraints")
        values = tuple(_coerce_target(item) for item in targets)
        constructs: list[ReporterConstruct] = []
        blockers: list[str] = []
        for target in values:
            if target.context_key != constraints.context_key:
                blockers.append(f"{target.target_id}:context_mismatch")
                continue
            if not target.reference_allele or not target.alternate_allele:
                blockers.append(f"{target.target_id}:missing_allele")
                continue
            constructs.extend(
                (
                    ReporterConstruct(
                        construct_id=content_hash(
                            {
                                "target": target.target_id,
                                "allele": "reference",
                                "mode": constraints.mode,
                            },
                            prefix="reporter",
                        ),
                        target_id=target.target_id,
                        allele="reference",
                        sequence=target.sequence.upper(),
                        context_key=target.context_key,
                        source_id=target.source_id,
                        is_control=False,
                        control_type=None,
                        notes=(
                            "Reference construct; sequence identity must be rechecked before "
                            "synthesis.",
                        ),
                    ),
                    ReporterConstruct(
                        construct_id=content_hash(
                            {
                                "target": target.target_id,
                                "allele": "alternate",
                                "mode": constraints.mode,
                            },
                            prefix="reporter",
                        ),
                        target_id=target.target_id,
                        allele="alternate",
                        sequence=target.alternate_sequence,
                        context_key=target.context_key,
                        source_id=target.source_id,
                        is_control=False,
                        control_type=None,
                        notes=(
                            "Alternate construct; equal handling and normalization require review.",
                        ),
                    ),
                )
            )
        if len(constructs) > constraints.max_guides:
            blockers.append("max_constructs_exceeded")
        if not values:
            blockers.append("no_validation_targets")
        if not constructs and not blockers:
            blockers.append("no_reporter_constructs")
        state = ValidationBetaState.BLOCKED if blockers else ValidationBetaState.READY_FOR_REVIEW
        package_id = f"{PerturbationMode.ALLELE_SPECIFIC_REPORTER.value}:{constraints.design_id}"
        body = {
            "package_id": package_id,
            "context_key": constraints.context_key,
            "targets": values,
            "constructs": constructs,
            "blockers": blockers,
            "state": state,
        }
        return AlleleSpecificReporterPackage(
            package_id=package_id,
            context_key=constraints.context_key,
            model_system=constraints.model_system,
            state=state,
            target_ids=tuple(item.target_id for item in values),
            constructs=tuple(constructs),
            controls=constraints.control_requirements,
            readouts=constraints.readout_requirements,
            blockers=tuple(dict.fromkeys(blockers)),
            alternatives=(
                "Keep reference and alternate constructs paired through synthesis and assay "
                "normalization.",
                "Use a perturbation design when the reporter cannot represent the allele class.",
            ),
            sensitivity={
                "construct_budget": "state changes when max_guides changes",
                "context_key": "context mismatch blocks construct transport",
                "allele_pair": "removing either allele requires explicit review",
            },
            limitations=(
                "Reporter constructs do not establish endogenous regulation or clinical effect.",
                "Allele balance, copy number, chromatin context, transfection, and readout "
                "normalization require validation.",
                "Controls and institutional approvals remain required before execution.",
            ),
            content_address=content_hash(body),
        )


def _coerce_target(value: ValidationBetaTarget | Mapping[str, Any]) -> ValidationBetaTarget:
    if isinstance(value, ValidationBetaTarget):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("validation beta target must be a mapping")
    return ValidationBetaTarget.from_mapping(value)


def _candidate_starts(target: ValidationBetaTarget, guide_length: int) -> tuple[int, ...]:
    lower = max(0, target.variant_offset - guide_length + 1)
    upper = min(target.variant_offset, len(target.sequence) - guide_length)
    return tuple(range(lower, upper + 1))


def _overlaps_variant(start: int, end: int, variant_start: int, variant_end: int) -> bool:
    return start < variant_end and variant_start < end


def _pam_for_start(sequence: str, start: int, guide_length: int, pattern: str) -> str | None:
    if not pattern:
        return ""
    pam_start = start + guide_length
    pam = sequence[pam_start : pam_start + len(pattern)]
    if len(pam) != len(pattern) or not _matches_iupac(pam, pattern):
        return None
    return pam


def _matches_iupac(sequence: str, pattern: str) -> bool:
    alphabet = {
        "A": {"A"},
        "C": {"C"},
        "G": {"G"},
        "T": {"T"},
        "N": {"A", "C", "G", "T", "N"},
        "R": {"A", "G"},
        "Y": {"C", "T"},
        "W": {"A", "T"},
        "S": {"C", "G"},
        "K": {"G", "T"},
        "M": {"A", "C"},
        "B": {"C", "G", "T"},
        "D": {"A", "G", "T"},
        "H": {"A", "C", "T"},
        "V": {"A", "C", "G"},
    }
    return len(sequence) == len(pattern) and all(
        base in alphabet.get(code, {code})
        for base, code in zip(sequence.upper(), pattern.upper(), strict=True)
    )


def _heuristic_scores(sequence: str, guide: str) -> tuple[float, float, float]:
    gc_fraction = (guide.count("G") + guide.count("C")) / max(1, len(guide))
    on_target = max(0.0, 1.0 - abs(gc_fraction - 0.5))
    repeats = max(0, sequence.count(guide) - 1)
    off_target = min(1.0, repeats * 0.25)
    specificity = 1.0 - off_target
    return on_target, specificity, off_target


def _as_bool(value: Any, *, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n"}:
            return False
    return bool(value)


__all__ = [
    "AlleleSpecificReporterPackage",
    "AlleleSpecificReporterPlanner",
    "BaseEditingDesignPlanner",
    "CRISPRaDesignPlanner",
    "CRISPRiDesignPlanner",
    "GuideCandidate",
    "GuideDesignConstraints",
    "GuideDesignPackage",
    "GuideStrand",
    "PrimeEditingDesignPlanner",
    "PerturbationMode",
    "ReporterConstruct",
    "ValidationBetaIssue",
    "ValidationBetaState",
    "ValidationBetaTarget",
]
