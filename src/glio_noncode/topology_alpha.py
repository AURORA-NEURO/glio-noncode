"""Deep topology contracts for Domain 09.

The adapters here keep motif orientation, CTCF/cohesin evidence, IDH-state
insulator observations, and structural-variant rewiring simulations separate.
They preserve contact edges, exact contexts, state labels, source hashes, and
competing outcomes. None of the outputs is a causal chromatin claim or a
clinical interpretation.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from statistics import median
from typing import Any

from .errors import ValidationError
from .identity import normalize_chromosome
from .serialization import content_hash, jsonable, require_non_empty


class TopologyAlphaState(StrEnum):
    """Evidence state shared by topology-alpha adapters."""

    SUPPORTED = "supported"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    ABSTAINED = "abstained"
    INVALID = "invalid"
    OUT_OF_DOMAIN = "out_of_domain"
    CONTRADICTORY = "contradictory"


@dataclass(frozen=True, slots=True)
class TopologyAlphaIssue:
    """Addressable topology issue with raw provenance."""

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
class BoundaryMotifOrientationObservation:
    """One motif observation attached to one boundary side."""

    observation_id: str
    boundary_id: str
    chromosome: str
    boundary_position: int
    side: str
    motif_id: str
    orientation: str
    score: float
    context_key: str
    source_id: str
    source_version: str
    raw_hash: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.observation_id, "observation_id"),
            (self.boundary_id, "boundary_id"),
            (self.chromosome, "chromosome"),
            (self.motif_id, "motif_id"),
            (self.context_key, "context_key"),
            (self.source_id, "source_id"),
            (self.source_version, "source_version"),
            (self.raw_hash, "raw_hash"),
        ):
            require_non_empty(str(value), name)
        if self.side not in {"left", "right"}:
            raise ValidationError("boundary motif side must be left or right")
        if self.orientation not in {"+", "-"}:
            raise ValidationError("boundary motif orientation must be + or -")
        if not 0 <= self.score <= 1:
            raise ValidationError("boundary motif score must be between zero and one")
        if self.boundary_position < 1:
            raise ValidationError("boundary position must be positive")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BoundaryMotifOrientationResult:
    """Orientation relationships observed around one boundary."""

    boundary_id: str
    chromosome: str
    boundary_position: int
    context_key: str
    relationship_labels: tuple[str, ...]
    left_orientations: tuple[str, ...]
    right_orientations: tuple[str, ...]
    motif_ids: tuple[str, ...]
    median_score: float
    state: TopologyAlphaState
    observation_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    raw_hashes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BoundaryMotifOrientationReport:
    """Boundary motif orientations and issues."""

    input_hash: str
    context_key: str | None
    state: TopologyAlphaState
    observations: tuple[BoundaryMotifOrientationObservation, ...]
    results: tuple[BoundaryMotifOrientationResult, ...]
    issues: tuple[TopologyAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class BoundaryMotifOrientationAnalyzer:
    """Classify convergent, divergent, and tandem motif orientations."""

    def analyze(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str | None = None,
        minimum_score: float = 0.5,
    ) -> BoundaryMotifOrientationReport:
        values = tuple(records)
        input_hash = content_hash(values)
        observations: list[BoundaryMotifOrientationObservation] = []
        issues: list[TopologyAlphaIssue] = []
        context_mismatch = False
        if not 0 <= minimum_score <= 1:
            issue = TopologyAlphaIssue(
                "invalid_boundary_parameter",
                "minimum score must be between zero and one",
                input_hash,
                severity="error",
            )
            return self._report(
                input_hash, context_key, TopologyAlphaState.INVALID, (), (), (issue,)
            )
        for row_number, row in enumerate(values, start=1):
            if not isinstance(row, Mapping):
                issues.append(
                    TopologyAlphaIssue(
                        "row_not_object",
                        "boundary motif row must be an object",
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
                    _issue(
                        row,
                        row_number,
                        "context_mismatch",
                        "boundary motif is outside the requested context",
                    )
                )
                continue
            try:
                score = float(_value(row, "score", "motif_score", default=1.0))
                if score < minimum_score:
                    continue
                observations.append(
                    BoundaryMotifOrientationObservation(
                        observation_id=str(
                            _value(row, "observation_id", "id", default=f"row-{row_number}")
                        ),
                        boundary_id=str(_value(row, "boundary_id", "boundary")),
                        chromosome=normalize_chromosome(
                            str(_value(row, "chromosome", "chrom", "contig"))
                        ),
                        boundary_position=int(
                            _value(row, "boundary_position", "position", "boundary_pos")
                        ),
                        side=str(_value(row, "side", "boundary_side")).lower(),
                        motif_id=str(_value(row, "motif_id", "motif")),
                        orientation=str(_value(row, "orientation", "strand")),
                        score=score,
                        context_key=row_context or context_key or "unspecified",
                        source_id=_source_id(row),
                        source_version=_source_version(row),
                        raw_hash=raw_hash,
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(_issue(row, row_number, "invalid_boundary_motif_row", str(exc)))
        groups: dict[tuple[str, str], list[BoundaryMotifOrientationObservation]] = defaultdict(list)
        for observation in observations:
            groups[(observation.boundary_id, observation.context_key)].append(observation)
        results: list[BoundaryMotifOrientationResult] = []
        for (boundary_id, row_context), group in sorted(groups.items()):
            left = tuple(sorted({item.orientation for item in group if item.side == "left"}))
            right = tuple(sorted({item.orientation for item in group if item.side == "right"}))
            labels = tuple(
                sorted(
                    {
                        "convergent"
                        if left_orientation == "+" and right_orientation == "-"
                        else "divergent"
                        if left_orientation == "-" and right_orientation == "+"
                        else "tandem"
                        for left_orientation in left
                        for right_orientation in right
                    }
                )
            )
            state = (
                TopologyAlphaState.AMBIGUOUS
                if len(labels) > 1
                else TopologyAlphaState.SUPPORTED
                if labels
                else TopologyAlphaState.PARTIAL
            )
            body = {
                "boundary_id": boundary_id,
                "context_key": row_context,
                "left": left,
                "right": right,
                "labels": labels,
            }
            results.append(
                BoundaryMotifOrientationResult(
                    boundary_id=boundary_id,
                    chromosome=group[0].chromosome,
                    boundary_position=group[0].boundary_position,
                    context_key=row_context,
                    relationship_labels=labels,
                    left_orientations=left,
                    right_orientations=right,
                    motif_ids=tuple(sorted({item.motif_id for item in group})),
                    median_score=round(float(median(item.score for item in group)), 9),
                    state=state,
                    observation_ids=tuple(sorted(item.observation_id for item in group)),
                    source_ids=tuple(sorted({item.source_id for item in group})),
                    raw_hashes=tuple(sorted(item.raw_hash for item in group)),
                    content_address=content_hash(body | {"state": state}),
                )
            )
        state = _aggregate_state(results, issues, context_mismatch)
        return self._report(
            input_hash, context_key, state, tuple(observations), tuple(results), tuple(issues)
        )

    @staticmethod
    def _report(
        input_hash: str,
        context_key: str | None,
        state: TopologyAlphaState,
        observations: tuple[BoundaryMotifOrientationObservation, ...],
        results: tuple[BoundaryMotifOrientationResult, ...],
        issues: tuple[TopologyAlphaIssue, ...],
    ) -> BoundaryMotifOrientationReport:
        return BoundaryMotifOrientationReport(
            input_hash=input_hash,
            context_key=context_key,
            state=state,
            observations=observations,
            results=results,
            issues=issues,
            warnings=(
                (
                    "Motif orientation is a boundary observation, not proof of loop extrusion "
                    "or insulation."
                ),
                "Multiple compatible orientation labels remain ambiguous.",
            ),
            content_address=content_hash(
                {
                    "input_hash": input_hash,
                    "state": state,
                    "observations": observations,
                    "results": results,
                    "issues": issues,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class CTCFCohesinDisruptionResult:
    """Reference/alternate CTCF and cohesin comparison."""

    variant_id: str
    context_key: str
    reference_ctcf: float | None
    alternate_ctcf: float | None
    reference_cohesin: float | None
    alternate_cohesin: float | None
    ctcf_delta: float | None
    cohesin_delta: float | None
    combined_delta: float | None
    disruption_label: str
    state: TopologyAlphaState
    source_ids: tuple[str, ...]
    raw_hashes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CTCFCohesinDisruptionReport:
    """CTCF/cohesin results and issues."""

    input_hash: str
    context_key: str | None
    state: TopologyAlphaState
    results: tuple[CTCFCohesinDisruptionResult, ...]
    issues: tuple[TopologyAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class CTCFCohesinDisruptionModel:
    """Compare declared CTCF and cohesin channels without causal inference."""

    def analyze(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str | None = None,
        disruption_threshold: float = 0.2,
    ) -> CTCFCohesinDisruptionReport:
        values = tuple(records)
        input_hash = content_hash(values)
        issues: list[TopologyAlphaIssue] = []
        parsed: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        context_mismatch = False
        if disruption_threshold < 0:
            issue = TopologyAlphaIssue(
                "invalid_disruption_parameter",
                "disruption threshold must be non-negative",
                input_hash,
                severity="error",
            )
            return self._report(input_hash, context_key, TopologyAlphaState.INVALID, (), (issue,))
        for row_number, row in enumerate(values, start=1):
            if not isinstance(row, Mapping):
                issues.append(
                    TopologyAlphaIssue(
                        "row_not_object",
                        "CTCF/cohesin row must be an object",
                        content_hash({"row": row}),
                        row_number,
                        severity="error",
                    )
                )
                continue
            row_context = _context(row)
            if context_key and row_context and row_context != context_key:
                context_mismatch = True
                issues.append(
                    _issue(
                        row,
                        row_number,
                        "context_mismatch",
                        "CTCF/cohesin row is outside the requested context",
                    )
                )
                continue
            try:
                variant = str(_value(row, "variant_id", "variant", "id"))
                assay_context = row_context or context_key or "unspecified"
                parsed[(variant, assay_context)].append(
                    {
                        "ctcf_ref": _optional_float(
                            _value(row, "reference_ctcf", "ctcf_reference", default=None)
                        ),
                        "ctcf_alt": _optional_float(
                            _value(row, "alternate_ctcf", "ctcf_alternate", default=None)
                        ),
                        "cohesin_ref": _optional_float(
                            _value(row, "reference_cohesin", "cohesin_reference", default=None)
                        ),
                        "cohesin_alt": _optional_float(
                            _value(row, "alternate_cohesin", "cohesin_alternate", default=None)
                        ),
                        "source_id": _source_id(row),
                        "raw_hash": _raw_hash(row),
                    }
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(_issue(row, row_number, "invalid_ctcf_cohesin_row", str(exc)))
        results: list[CTCFCohesinDisruptionResult] = []
        for (variant, row_context), group in sorted(parsed.items()):

            def _median(rows: Sequence[Mapping[str, Any]], key: str) -> float | None:
                values_for_key = [item[key] for item in rows if item[key] is not None]
                return None if not values_for_key else float(median(values_for_key))

            ctcf_ref, ctcf_alt = _median(group, "ctcf_ref"), _median(group, "ctcf_alt")
            cohesin_ref, cohesin_alt = _median(group, "cohesin_ref"), _median(group, "cohesin_alt")
            ctcf_delta = None if ctcf_ref is None or ctcf_alt is None else ctcf_alt - ctcf_ref
            cohesin_delta = (
                None if cohesin_ref is None or cohesin_alt is None else cohesin_alt - cohesin_ref
            )
            deltas = [value for value in (ctcf_delta, cohesin_delta) if value is not None]
            combined = None if not deltas else sum(deltas) / len(deltas)
            if combined is None:
                label = "unknown"
                state = TopologyAlphaState.PARTIAL
            else:
                directions = {
                    "loss"
                    if value < -disruption_threshold
                    else "gain"
                    if value > disruption_threshold
                    else "stable"
                    for value in deltas
                }
                label = (
                    "disrupted"
                    if combined < -disruption_threshold
                    else "gained"
                    if combined > disruption_threshold
                    else "stable"
                )
                state = (
                    TopologyAlphaState.AMBIGUOUS
                    if "loss" in directions and "gain" in directions
                    else TopologyAlphaState.SUPPORTED
                    if len(deltas) == 2
                    else TopologyAlphaState.PARTIAL
                )
            body = {
                "variant_id": variant,
                "context_key": row_context,
                "ctcf_delta": ctcf_delta,
                "cohesin_delta": cohesin_delta,
            }
            results.append(
                CTCFCohesinDisruptionResult(
                    variant_id=variant,
                    context_key=row_context,
                    reference_ctcf=None if ctcf_ref is None else round(ctcf_ref, 9),
                    alternate_ctcf=None if ctcf_alt is None else round(ctcf_alt, 9),
                    reference_cohesin=None if cohesin_ref is None else round(cohesin_ref, 9),
                    alternate_cohesin=None if cohesin_alt is None else round(cohesin_alt, 9),
                    ctcf_delta=None if ctcf_delta is None else round(ctcf_delta, 9),
                    cohesin_delta=None if cohesin_delta is None else round(cohesin_delta, 9),
                    combined_delta=None if combined is None else round(combined, 9),
                    disruption_label=label,
                    state=state,
                    source_ids=tuple(sorted({item["source_id"] for item in group})),
                    raw_hashes=tuple(sorted(item["raw_hash"] for item in group)),
                    content_address=content_hash(body | {"state": state}),
                )
            )
        return self._report(
            input_hash,
            context_key,
            _aggregate_state(results, issues, context_mismatch),
            tuple(results),
            tuple(issues),
        )

    @staticmethod
    def _report(
        input_hash: str,
        context_key: str | None,
        state: TopologyAlphaState,
        results: tuple[CTCFCohesinDisruptionResult, ...],
        issues: tuple[TopologyAlphaIssue, ...],
    ) -> CTCFCohesinDisruptionReport:
        return CTCFCohesinDisruptionReport(
            input_hash,
            context_key,
            state,
            results,
            issues,
            (
                (
                    "CTCF/cohesin deltas are assay comparisons, not insulation or causal-effect "
                    "claims."
                ),
                "Missing channel evidence remains partial.",
            ),
            content_hash(
                {"input_hash": input_hash, "state": state, "results": results, "issues": issues}
            ),
        )


@dataclass(frozen=True, slots=True)
class IDHInsulatorDysfunctionResult:
    """IDH-state comparison for one insulator region."""

    region_id: str
    context_key: str
    idh_mutant_score: float | None
    idh_wildtype_score: float | None
    insulator_delta: float | None
    mutant_methylation: float | None
    wildtype_methylation: float | None
    dysfunction_index: float | None
    label: str
    state: TopologyAlphaState
    source_ids: tuple[str, ...]
    raw_hashes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IDHInsulatorDysfunctionReport:
    """IDH insulator comparisons and issues."""

    input_hash: str
    context_key: str | None
    state: TopologyAlphaState
    results: tuple[IDHInsulatorDysfunctionResult, ...]
    issues: tuple[TopologyAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class IDHInsulatorDysfunctionModel:
    """Compare declared IDH-mutant and IDH-wildtype insulator evidence."""

    def assess(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str | None = None,
        dysfunction_threshold: float = 0.2,
    ) -> IDHInsulatorDysfunctionReport:
        values = tuple(records)
        input_hash = content_hash(values)
        issues: list[TopologyAlphaIssue] = []
        parsed: dict[tuple[str, str], dict[str, list[dict[str, Any]]]] = defaultdict(
            lambda: defaultdict(list)
        )
        context_mismatch = False
        for row_number, row in enumerate(values, start=1):
            if not isinstance(row, Mapping):
                issues.append(
                    TopologyAlphaIssue(
                        "row_not_object",
                        "IDH insulator row must be an object",
                        content_hash({"row": row}),
                        row_number,
                        severity="error",
                    )
                )
                continue
            row_context = _context(row)
            if context_key and row_context and row_context != context_key:
                context_mismatch = True
                issues.append(
                    _issue(
                        row,
                        row_number,
                        "context_mismatch",
                        "IDH insulator row is outside the requested context",
                    )
                )
                continue
            try:
                state_id = str(_value(row, "molecular_state", "state"))
                if state_id not in {"IDH-mutant", "IDH-wildtype"}:
                    raise ValidationError("molecular_state must be IDH-mutant or IDH-wildtype")
                parsed[
                    (
                        str(_value(row, "region_id", "region", "id")),
                        row_context or context_key or "unspecified",
                    )
                ][state_id].append(
                    {
                        "score": _optional_float(
                            _value(row, "insulator_score", "boundary_score", "score", default=None)
                        ),
                        "methylation": _optional_float(
                            _value(row, "methylation_fraction", "methylation", "beta", default=None)
                        ),
                        "source_id": _source_id(row),
                        "raw_hash": _raw_hash(row),
                    }
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(_issue(row, row_number, "invalid_idh_insulator_row", str(exc)))
        results: list[IDHInsulatorDysfunctionResult] = []
        for (region_id, row_context), states in sorted(parsed.items()):
            mutant = states.get("IDH-mutant", [])
            wildtype = states.get("IDH-wildtype", [])

            def _median(rows: list[dict[str, Any]], key: str) -> float | None:
                values_for_key = [row[key] for row in rows if row[key] is not None]
                return None if not values_for_key else float(median(values_for_key))

            mut_score, wt_score = _median(mutant, "score"), _median(wildtype, "score")
            mut_methylation, wt_methylation = (
                _median(mutant, "methylation"),
                _median(wildtype, "methylation"),
            )
            delta = None if mut_score is None or wt_score is None else mut_score - wt_score
            index = None if delta is None else max(0.0, -delta)
            label = (
                "unknown"
                if index is None
                else "dysfunction_candidate"
                if index >= dysfunction_threshold
                else "no_declared_loss"
            )
            state = TopologyAlphaState.PARTIAL if delta is None else TopologyAlphaState.SUPPORTED
            all_rows = mutant + wildtype
            body = {
                "region_id": region_id,
                "context_key": row_context,
                "delta": delta,
                "index": index,
            }
            results.append(
                IDHInsulatorDysfunctionResult(
                    region_id=region_id,
                    context_key=row_context,
                    idh_mutant_score=None if mut_score is None else round(mut_score, 9),
                    idh_wildtype_score=None if wt_score is None else round(wt_score, 9),
                    insulator_delta=None if delta is None else round(delta, 9),
                    mutant_methylation=None
                    if mut_methylation is None
                    else round(mut_methylation, 9),
                    wildtype_methylation=None
                    if wt_methylation is None
                    else round(wt_methylation, 9),
                    dysfunction_index=None if index is None else round(index, 9),
                    label=label,
                    state=state,
                    source_ids=tuple(sorted({row["source_id"] for row in all_rows})),
                    raw_hashes=tuple(sorted(row["raw_hash"] for row in all_rows)),
                    content_address=content_hash(body | {"state": state}),
                )
            )
        return self._report(
            input_hash,
            context_key,
            _aggregate_state(results, issues, context_mismatch),
            tuple(results),
            tuple(issues),
        )

    @staticmethod
    def _report(
        input_hash: str,
        context_key: str | None,
        state: TopologyAlphaState,
        results: tuple[IDHInsulatorDysfunctionResult, ...],
        issues: tuple[TopologyAlphaIssue, ...],
    ) -> IDHInsulatorDysfunctionReport:
        return IDHInsulatorDysfunctionReport(
            input_hash,
            context_key,
            state,
            results,
            issues,
            (
                (
                    "IDH insulator comparisons are state-qualified descriptive evidence, not a "
                    "mechanistic dysfunction diagnosis."
                ),
                (
                    "Methylation is retained as a separate channel and is not converted into "
                    "silencing."
                ),
            ),
            content_hash(
                {"input_hash": input_hash, "state": state, "results": results, "issues": issues}
            ),
        )


@dataclass(frozen=True, slots=True)
class SVTopologyRewireResult:
    """One SV event's deterministic contact-edge simulation."""

    sv_id: str
    context_key: str
    sv_kind: str
    preserved_edge_ids: tuple[str, ...]
    lost_edge_ids: tuple[str, ...]
    gained_edge_ids: tuple[str, ...]
    rewired_edge_ids: tuple[str, ...]
    affected_node_ids: tuple[str, ...]
    state: TopologyAlphaState
    source_ids: tuple[str, ...]
    raw_hashes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SVTopologyRewiringReport:
    """SV topology simulations and issues."""

    input_hash: str
    context_key: str | None
    state: TopologyAlphaState
    results: tuple[SVTopologyRewireResult, ...]
    issues: tuple[TopologyAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class SVTopologyRewiringSimulator:
    """Apply declared edge deletions and additions for each SV event."""

    def simulate(
        self,
        contacts: Iterable[Mapping[str, Any]],
        events: Iterable[Mapping[str, Any]],
        *,
        context_key: str | None = None,
    ) -> SVTopologyRewiringReport:
        contact_values = tuple(contacts)
        event_values = tuple(events)
        input_hash = content_hash({"contacts": contact_values, "events": event_values})
        issues: list[TopologyAlphaIssue] = []
        contact_edges: dict[str, dict[str, Any]] = {}
        context_mismatch = False
        for row_number, row in enumerate(contact_values, start=1):
            if not isinstance(row, Mapping):
                issues.append(
                    TopologyAlphaIssue(
                        "row_not_object",
                        "contact edge must be an object",
                        content_hash({"row": row}),
                        row_number,
                        severity="error",
                    )
                )
                continue
            row_context = _context(row)
            if context_key and row_context and row_context != context_key:
                context_mismatch = True
                continue
            try:
                edge_id = str(_value(row, "edge_id", "contact_id", "id"))
                source_node = str(_value(row, "source_node", "source", "from_node"))
                target_node = str(_value(row, "target_node", "target", "to_node"))
                contact_edges[edge_id] = {
                    "source": source_node,
                    "target": target_node,
                    "context": row_context or context_key or "unspecified",
                    "raw_hash": _raw_hash(row),
                    "source_id": _source_id(row),
                }
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(_issue(row, row_number, "invalid_contact_edge", str(exc)))
        results: list[SVTopologyRewireResult] = []
        for row_number, event in enumerate(event_values, start=1):
            if not isinstance(event, Mapping):
                issues.append(
                    TopologyAlphaIssue(
                        "row_not_object",
                        "SV event must be an object",
                        content_hash({"row": event}),
                        row_number,
                        severity="error",
                    )
                )
                continue
            row_context = _context(event)
            if context_key and row_context and row_context != context_key:
                context_mismatch = True
                issues.append(
                    _issue(
                        event,
                        row_number,
                        "context_mismatch",
                        "SV event is outside the requested context",
                    )
                )
                continue
            try:
                sv_id = str(_value(event, "sv_id", "event_id", "id"))
                deleted = {
                    str(item)
                    for item in event.get("deleted_edge_ids", event.get("deleted_edges", ()))
                }
                gained = {
                    str(item)
                    for item in event.get("gained_edge_ids", event.get("gained_edges", ()))
                }
                rewired = {
                    str(item)
                    for item in event.get("rewired_edge_ids", event.get("rewired_edges", ()))
                }
                affected = {
                    str(item) for item in event.get("affected_node_ids", event.get("nodes", ()))
                }
                lost = tuple(sorted(edge_id for edge_id in deleted if edge_id in contact_edges))
                preserved = tuple(
                    sorted(
                        edge_id
                        for edge_id in contact_edges
                        if edge_id not in deleted and edge_id not in rewired
                    )
                )
                gained_ids = tuple(sorted(gained))
                rewired_ids = tuple(sorted(rewired))
                state = (
                    TopologyAlphaState.SUPPORTED
                    if lost or gained_ids or rewired_ids
                    else TopologyAlphaState.PARTIAL
                )
                results.append(
                    SVTopologyRewireResult(
                        sv_id=sv_id,
                        context_key=row_context or context_key or "unspecified",
                        sv_kind=str(_value(event, "sv_kind", "kind", default="structural_variant")),
                        preserved_edge_ids=preserved,
                        lost_edge_ids=lost,
                        gained_edge_ids=gained_ids,
                        rewired_edge_ids=rewired_ids,
                        affected_node_ids=tuple(sorted(affected)),
                        state=state,
                        source_ids=tuple(
                            sorted(
                                {str(_value(event, "source_id", "source", default="unspecified"))}
                                | {edge["source_id"] for edge in contact_edges.values()}
                            )
                        ),
                        raw_hashes=tuple(
                            sorted(
                                {_raw_hash(event)}
                                | {
                                    contact_edges[edge_id]["raw_hash"]
                                    for edge_id in lost
                                    if edge_id in contact_edges
                                }
                            )
                        ),
                        content_address=content_hash(
                            {
                                "sv_id": sv_id,
                                "lost": lost,
                                "gained": gained_ids,
                                "rewired": rewired_ids,
                                "state": state,
                            }
                        ),
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(_issue(event, row_number, "invalid_sv_event", str(exc)))
        state = (
            TopologyAlphaState.OUT_OF_DOMAIN
            if context_mismatch and not results
            else _aggregate_state(results, issues, False)
        )
        return SVTopologyRewiringReport(
            input_hash=input_hash,
            context_key=context_key,
            state=state,
            results=tuple(results),
            issues=tuple(issues),
            warnings=(
                (
                    "SV rewiring is a declared contact-edge simulation, not a prediction of 3D "
                    "structure or function."
                ),
                (
                    "Edges not explicitly deleted or rewired are preserved as simulation "
                    "bookkeeping only."
                ),
            ),
            content_address=content_hash(
                {"input_hash": input_hash, "state": state, "results": results, "issues": issues}
            ),
        )


def _aggregate_state(
    results: Sequence[Any], issues: Sequence[TopologyAlphaIssue], context_mismatch: bool
) -> TopologyAlphaState:
    if context_mismatch and not results:
        return TopologyAlphaState.OUT_OF_DOMAIN
    if any(item.state == TopologyAlphaState.AMBIGUOUS for item in results):
        return TopologyAlphaState.AMBIGUOUS
    if issues or any(item.state == TopologyAlphaState.PARTIAL for item in results):
        return TopologyAlphaState.PARTIAL
    if not results:
        return TopologyAlphaState.ABSTAINED
    return TopologyAlphaState.SUPPORTED


def _issue(row: Mapping[str, Any], row_number: int, code: str, message: str) -> TopologyAlphaIssue:
    return TopologyAlphaIssue(
        code,
        message,
        _raw_hash(row),
        row_number,
        source_id=_source_id(row),
        severity="error",
        raw_record=dict(row),
    )


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


def _optional_float(value: Any) -> float | None:
    if value is None or (isinstance(value, str) and value in {"", "."}):
        return None
    return float(value)


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
    "BoundaryMotifOrientationAnalyzer",
    "BoundaryMotifOrientationObservation",
    "BoundaryMotifOrientationReport",
    "BoundaryMotifOrientationResult",
    "CTCFCohesinDisruptionModel",
    "CTCFCohesinDisruptionReport",
    "CTCFCohesinDisruptionResult",
    "IDHInsulatorDysfunctionModel",
    "IDHInsulatorDysfunctionReport",
    "IDHInsulatorDysfunctionResult",
    "SVTopologyRewireResult",
    "SVTopologyRewiringReport",
    "SVTopologyRewiringSimulator",
    "TopologyAlphaIssue",
    "TopologyAlphaState",
]
