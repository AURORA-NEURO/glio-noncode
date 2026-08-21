"""Scientific-beta adapters and scorers for regulatory 3D topology.

This module keeps observed loop/stripe and promoter-capture records distinct
from inferred enhancer-promoter links. Contact scores are bounded descriptive
summaries with exact context and source receipts; activity-by-contact is a
declared product of two measured components, not a probability or causal
claim.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from statistics import median
from typing import Any

from .errors import ValidationError
from .identity import normalize_chromosome
from .serialization import content_hash, jsonable, require_non_empty
from .topology_context import TopologyState


class TopologyBetaKind(StrEnum):
    LOOP = "loop"
    STRIPE = "stripe"


@dataclass(frozen=True, slots=True)
class TopologyBetaIssue:
    """Quarantined topology-beta row with raw source provenance."""

    code: str
    message: str
    raw_hash: str
    row_number: int | None = None
    source_id: str = "unspecified"
    severity: str = "warning"
    raw_record: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty(self.code, "topology beta issue code")
        require_non_empty(self.message, "topology beta issue message")
        require_non_empty(self.raw_hash, "topology beta issue raw_hash")
        if self.row_number is not None and self.row_number < 1:
            raise ValidationError("topology beta issue row_number must be positive")
        if self.severity not in {"warning", "error"}:
            raise ValidationError("topology beta issue severity must be warning or error")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LoopStripeObservation:
    """One normalized loop or stripe feature with two genomic anchors."""

    feature_id: str
    feature_kind: TopologyBetaKind
    chromosome_a: str
    start_a: int
    end_a: int
    chromosome_b: str
    start_b: int
    end_b: int
    signal: float
    context_key: str
    source_id: str
    source_version: str
    raw_hash: str
    resolution: int | None = None
    replicate_id: str | None = None
    caller: str | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "feature_id",
            "chromosome_a",
            "chromosome_b",
            "context_key",
            "source_id",
            "source_version",
            "raw_hash",
        ):
            require_non_empty(str(getattr(self, name)), name)
        for label, start, end in (
            ("a", self.start_a, self.end_a),
            ("b", self.start_b, self.end_b),
        ):
            if start < 1 or end < start:
                raise ValidationError(f"loop/stripe interval {label} is invalid")
        if self.signal < 0:
            raise ValidationError("loop/stripe signal cannot be negative")
        if self.resolution is not None and self.resolution < 1:
            raise ValidationError("loop/stripe resolution must be positive")

    @property
    def endpoints(self) -> tuple[tuple[str, int, int], tuple[str, int, int]]:
        return (
            (normalize_chromosome(self.chromosome_a), self.start_a, self.end_a),
            (normalize_chromosome(self.chromosome_b), self.start_b, self.end_b),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LoopStripeBatch:
    source_id: str
    input_hash: str
    observations: tuple[LoopStripeObservation, ...]
    issues: tuple[TopologyBetaIssue, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class LoopStripeAdapter:
    """Parse loop/stripe feature records from JSON or TSV snapshots."""

    def parse_text(
        self,
        text: str,
        *,
        source_id: str,
        source_version: str = "unspecified",
        input_format: str | None = None,
        coordinate_system: str = "bed",
    ) -> LoopStripeBatch:
        rows, json_mode = _rows(text, input_format, "features")
        if coordinate_system not in {"bed", "one_based"}:
            raise ValidationError("loop/stripe coordinate_system must be bed or one_based")
        records: list[LoopStripeObservation] = []
        issues: list[TopologyBetaIssue] = []
        for index, row in enumerate(rows, start=1 if json_mode else 2):
            if not isinstance(row, Mapping):
                issues.append(
                    TopologyBetaIssue(
                        "invalid_loop_stripe_row",
                        "row must be an object",
                        content_hash(row),
                        row_number=index,
                        source_id=source_id,
                        severity="error",
                    )
                )
                continue
            raw_hash = content_hash(row)
            try:
                start_a, end_a = _interval(row, "a", coordinate_system)
                start_b, end_b = _interval(row, "b", coordinate_system)
                records.append(
                    LoopStripeObservation(
                        feature_id=str(
                            _value(
                                row,
                                "feature_id",
                                "loop_id",
                                "stripe_id",
                                default=f"{source_id}:{index}",
                            )
                        ),
                        feature_kind=TopologyBetaKind(
                            str(_value(row, "feature_kind", "kind", "type", default="loop"))
                        ),
                        chromosome_a=normalize_chromosome(
                            str(_value(row, "chromosome_a", "chrom1", "chrom_a"))
                        ),
                        start_a=start_a,
                        end_a=end_a,
                        chromosome_b=normalize_chromosome(
                            str(_value(row, "chromosome_b", "chrom2", "chrom_b"))
                        ),
                        start_b=start_b,
                        end_b=end_b,
                        signal=float(_value(row, "signal", "score", "count")),
                        context_key=str(_value(row, "context_key", "context")),
                        source_id=source_id,
                        source_version=str(
                            _value(row, "source_version", "version", default=source_version)
                        ),
                        raw_hash=raw_hash,
                        resolution=_optional_int(row, "resolution", "bin_size"),
                        replicate_id=_optional_text(row, "replicate_id", "replicate"),
                        caller=_optional_text(row, "caller", "algorithm"),
                        attributes=dict(row),
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    TopologyBetaIssue(
                        "invalid_loop_stripe_row",
                        str(exc),
                        raw_hash,
                        row_number=index,
                        source_id=source_id,
                        severity="error",
                        raw_record=dict(row),
                    )
                )
        input_hash = content_hash(text)
        return LoopStripeBatch(
            source_id=source_id,
            input_hash=input_hash,
            observations=tuple(records),
            issues=tuple(issues),
            content_address=content_hash(
                {
                    "source_id": source_id,
                    "source_version": source_version,
                    "input_hash": input_hash,
                    "observations": records,
                    "issues": issues,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class PromoterCaptureContact:
    """One promoter-capture bait-to-element observation."""

    contact_id: str
    promoter_id: str
    target_element_id: str
    promoter_chromosome: str
    promoter_start: int
    promoter_end: int
    target_chromosome: str
    target_start: int
    target_end: int
    signal: float
    context_key: str
    source_id: str
    source_version: str
    raw_hash: str
    resolution: int | None = None
    replicate_id: str | None = None
    bait_id: str | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "contact_id",
            "promoter_id",
            "target_element_id",
            "promoter_chromosome",
            "target_chromosome",
            "context_key",
            "source_id",
            "source_version",
            "raw_hash",
        ):
            require_non_empty(str(getattr(self, name)), name)
        for label, start, end in (
            ("promoter", self.promoter_start, self.promoter_end),
            ("target", self.target_start, self.target_end),
        ):
            if start < 1 or end < start:
                raise ValidationError(f"promoter-capture {label} interval is invalid")
        if self.signal < 0:
            raise ValidationError("promoter-capture signal cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PromoterCaptureBatch:
    source_id: str
    input_hash: str
    contacts: tuple[PromoterCaptureContact, ...]
    issues: tuple[TopologyBetaIssue, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class PromoterCaptureContactAdapter:
    """Parse promoter-capture contact snapshots with coordinate provenance."""

    def parse_text(
        self,
        text: str,
        *,
        source_id: str,
        source_version: str = "unspecified",
        input_format: str | None = None,
        coordinate_system: str = "bed",
    ) -> PromoterCaptureBatch:
        rows, json_mode = _rows(text, input_format, "contacts")
        if coordinate_system not in {"bed", "one_based"}:
            raise ValidationError("promoter-capture coordinate_system must be bed or one_based")
        contacts: list[PromoterCaptureContact] = []
        issues: list[TopologyBetaIssue] = []
        for index, row in enumerate(rows, start=1 if json_mode else 2):
            if not isinstance(row, Mapping):
                issues.append(
                    TopologyBetaIssue(
                        "invalid_promoter_capture_row",
                        "row must be an object",
                        content_hash(row),
                        row_number=index,
                        source_id=source_id,
                        severity="error",
                    )
                )
                continue
            raw_hash = content_hash(row)
            try:
                promoter_start, promoter_end = _interval(row, "promoter", coordinate_system)
                target_start, target_end = _interval(row, "target", coordinate_system)
                contacts.append(
                    PromoterCaptureContact(
                        contact_id=str(
                            _value(
                                row, "contact_id", "interaction_id", default=f"{source_id}:{index}"
                            )
                        ),
                        promoter_id=str(_value(row, "promoter_id", "gene_id", "promoter")),
                        target_element_id=str(
                            _value(row, "target_element_id", "enhancer_id", "element_id")
                        ),
                        promoter_chromosome=normalize_chromosome(
                            str(
                                _value(row, "promoter_chromosome", "promoter_chrom", "chromosome_a")
                            )
                        ),
                        promoter_start=promoter_start,
                        promoter_end=promoter_end,
                        target_chromosome=normalize_chromosome(
                            str(_value(row, "target_chromosome", "target_chrom", "chromosome_b"))
                        ),
                        target_start=target_start,
                        target_end=target_end,
                        signal=float(_value(row, "signal", "count", "score")),
                        context_key=str(_value(row, "context_key", "context")),
                        source_id=source_id,
                        source_version=str(
                            _value(row, "source_version", "version", default=source_version)
                        ),
                        raw_hash=raw_hash,
                        resolution=_optional_int(row, "resolution", "bin_size"),
                        replicate_id=_optional_text(row, "replicate_id", "replicate"),
                        bait_id=_optional_text(row, "bait_id", "bait"),
                        attributes=dict(row),
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    TopologyBetaIssue(
                        "invalid_promoter_capture_row",
                        str(exc),
                        raw_hash,
                        row_number=index,
                        source_id=source_id,
                        severity="error",
                        raw_record=dict(row),
                    )
                )
        input_hash = content_hash(text)
        return PromoterCaptureBatch(
            source_id=source_id,
            input_hash=input_hash,
            contacts=tuple(contacts),
            issues=tuple(issues),
            content_address=content_hash(
                {
                    "source_id": source_id,
                    "source_version": source_version,
                    "input_hash": input_hash,
                    "contacts": contacts,
                    "issues": issues,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class EnhancerPromoterContactEvidence:
    """Normalized enhancer-to-promoter contact evidence for scoring."""

    enhancer_id: str
    promoter_id: str
    signal: float
    context_key: str
    source_id: str
    source_version: str
    raw_hash: str
    contact_id: str = "contact-input"
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "enhancer_id",
            "promoter_id",
            "context_key",
            "source_id",
            "source_version",
            "raw_hash",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if self.signal < 0:
            raise ValidationError("enhancer-promoter signal cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EnhancerPromoterContactScore:
    """Bounded descriptive enhancer-promoter contact score."""

    enhancer_id: str
    promoter_id: str
    context_key: str
    state: TopologyState
    observations: tuple[EnhancerPromoterContactEvidence, ...]
    median_signal: float | None
    signal_spread: float | None
    normalized_contact_score: float | None
    source_ids: tuple[str, ...]
    source_versions: tuple[str, ...]
    reason: str
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class EnhancerPromoterContactScorer:
    """Summarize exact-context enhancer-promoter contact evidence."""

    def score(
        self,
        observations: Iterable[EnhancerPromoterContactEvidence | Mapping[str, Any]],
        *,
        enhancer_id: str,
        promoter_id: str,
        context_key: str,
        signal_scale: float = 10.0,
        ambiguity_tolerance: float = 0.50,
    ) -> EnhancerPromoterContactScore:
        require_non_empty(enhancer_id, "enhancer_id")
        require_non_empty(promoter_id, "promoter_id")
        require_non_empty(context_key, "context_key")
        if signal_scale <= 0:
            raise ValidationError("signal_scale must be positive")
        if ambiguity_tolerance < 0:
            raise ValidationError("ambiguity_tolerance cannot be negative")
        values = tuple(_coerce_contact(value) for value in observations)
        pair_rows = tuple(
            value
            for value in values
            if value.enhancer_id == enhancer_id and value.promoter_id == promoter_id
        )
        exact = tuple(value for value in pair_rows if value.context_key == context_key)
        if not exact:
            state = TopologyState.OUT_OF_DOMAIN if pair_rows else TopologyState.ABSENT
            reason = (
                "contact observations exist only for another context"
                if pair_rows
                else "no enhancer-promoter contact observations were supplied"
            )
            return self._result(
                enhancer_id,
                promoter_id,
                context_key,
                state,
                (),
                None,
                None,
                None,
                reason,
            )
        signals = tuple(value.signal for value in exact)
        median_signal = median(signals)
        spread = max(signals) - min(signals) if len(signals) > 1 else 0.0
        state = TopologyState.AMBIGUOUS if spread > ambiguity_tolerance else TopologyState.SUPPORTED
        return self._result(
            enhancer_id,
            promoter_id,
            context_key,
            state,
            exact,
            median_signal,
            spread,
            min(1.0, median_signal / signal_scale),
            "exact-context contact observations support a bounded descriptive score",
            signal_scale=signal_scale,
        )

    @staticmethod
    def _result(
        enhancer_id: str,
        promoter_id: str,
        context_key: str,
        state: TopologyState,
        observations: tuple[EnhancerPromoterContactEvidence, ...],
        median_signal: float | None,
        signal_spread: float | None,
        normalized_contact_score: float | None,
        reason: str,
        *,
        signal_scale: float = 10.0,
    ) -> EnhancerPromoterContactScore:
        return EnhancerPromoterContactScore(
            enhancer_id=enhancer_id,
            promoter_id=promoter_id,
            context_key=context_key,
            state=state,
            observations=observations,
            median_signal=median_signal,
            signal_spread=signal_spread,
            normalized_contact_score=normalized_contact_score,
            source_ids=tuple(sorted({value.source_id for value in observations})),
            source_versions=tuple(sorted({value.source_version for value in observations})),
            reason=reason,
            warnings=(
                "Contact score is a bounded descriptive transform, not a probability "
                "or causal link.",
                "Exact context, source version, and replicate disagreement remain "
                "attached to the result.",
                f"The declared signal scale is {signal_scale}; it is not externally "
                "calibrated here.",
            ),
            content_address=content_hash(
                {
                    "enhancer_id": enhancer_id,
                    "promoter_id": promoter_id,
                    "context_key": context_key,
                    "state": state,
                    "observations": observations,
                    "median_signal": median_signal,
                    "signal_spread": signal_spread,
                    "normalized_contact_score": normalized_contact_score,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class EnhancerActivityObservation:
    """One context-qualified enhancer activity measurement."""

    enhancer_id: str
    activity_signal: float
    context_key: str
    source_id: str
    source_version: str
    raw_hash: str
    replicate_id: str | None = None
    assay: str = "activity"
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "enhancer_id",
            "context_key",
            "source_id",
            "source_version",
            "raw_hash",
            "assay",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if self.activity_signal < 0:
            raise ValidationError("enhancer activity_signal cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ActivityByContactResult:
    """Descriptive activity-by-contact combination with both components retained."""

    enhancer_id: str
    promoter_id: str
    context_key: str
    model_id: str
    model_version: str
    state: TopologyState
    contact_state: TopologyState
    activity_state: TopologyState
    contact_component: float | None
    activity_component: float | None
    activity_by_contact_score: float | None
    contact_observations: tuple[EnhancerPromoterContactEvidence, ...]
    activity_observations: tuple[EnhancerActivityObservation, ...]
    source_ids: tuple[str, ...]
    source_versions: tuple[str, ...]
    reason: str
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ActivityByContactScorer:
    """Combine measured activity and contact components under exact context."""

    def score(
        self,
        contacts: Iterable[EnhancerPromoterContactEvidence | Mapping[str, Any]],
        activities: Iterable[EnhancerActivityObservation | Mapping[str, Any]],
        *,
        enhancer_id: str,
        promoter_id: str,
        context_key: str,
        model_id: str,
        model_version: str,
        contact_scale: float = 10.0,
        activity_scale: float = 1.0,
        ambiguity_tolerance: float = 0.50,
    ) -> ActivityByContactResult:
        require_non_empty(model_id, "model_id")
        require_non_empty(model_version, "model_version")
        if contact_scale <= 0 or activity_scale <= 0:
            raise ValidationError("contact_scale and activity_scale must be positive")
        contact_values = tuple(_coerce_contact(value) for value in contacts)
        activity_values = tuple(_coerce_activity(value) for value in activities)
        pair_rows = tuple(
            value
            for value in contact_values
            if value.enhancer_id == enhancer_id and value.promoter_id == promoter_id
        )
        exact_contacts = tuple(value for value in pair_rows if value.context_key == context_key)
        enhancer_rows = tuple(
            value for value in activity_values if value.enhancer_id == enhancer_id
        )
        exact_activities = tuple(
            value for value in enhancer_rows if value.context_key == context_key
        )
        contact_state, contact_component = self._component(
            tuple(value.signal for value in exact_contacts),
            contact_scale,
            ambiguity_tolerance,
            has_other_context=bool(pair_rows and not exact_contacts),
        )
        activity_state, activity_component = self._component(
            tuple(value.activity_signal for value in exact_activities),
            activity_scale,
            ambiguity_tolerance,
            has_other_context=bool(enhancer_rows and not exact_activities),
        )
        if (
            contact_state == TopologyState.OUT_OF_DOMAIN
            or activity_state == TopologyState.OUT_OF_DOMAIN
        ):
            state = TopologyState.OUT_OF_DOMAIN
        elif contact_state in {TopologyState.ABSENT, TopologyState.ABSTAINED} or activity_state in {
            TopologyState.ABSENT,
            TopologyState.ABSTAINED,
        }:
            state = TopologyState.ABSTAINED
        elif TopologyState.AMBIGUOUS in {contact_state, activity_state}:
            state = TopologyState.AMBIGUOUS
        elif contact_state == TopologyState.PARTIAL or activity_state == TopologyState.PARTIAL:
            state = TopologyState.PARTIAL
        else:
            state = TopologyState.SUPPORTED
        combined = (
            round(contact_component * activity_component, 9)
            if contact_component is not None
            and activity_component is not None
            and state not in {TopologyState.OUT_OF_DOMAIN, TopologyState.ABSTAINED}
            else None
        )
        return ActivityByContactResult(
            enhancer_id=enhancer_id,
            promoter_id=promoter_id,
            context_key=context_key,
            model_id=model_id,
            model_version=model_version,
            state=state,
            contact_state=contact_state,
            activity_state=activity_state,
            contact_component=contact_component,
            activity_component=activity_component,
            activity_by_contact_score=combined,
            contact_observations=exact_contacts,
            activity_observations=exact_activities,
            source_ids=tuple(
                sorted(
                    {value.source_id for value in exact_contacts}
                    | {value.source_id for value in exact_activities}
                )
            ),
            source_versions=tuple(
                sorted(
                    {value.source_version for value in exact_contacts}
                    | {value.source_version for value in exact_activities}
                )
            ),
            reason="activity and contact components were combined under declared scales",
            warnings=(
                "Activity-by-contact is a descriptive product of two measured "
                "components, not a probability or causal effect.",
                "Missing activity, missing contact, and other-context records are not "
                "silently imputed or transported.",
                "Model calibration, matched negative controls, and external transport "
                "evaluation remain required.",
            ),
            content_address=content_hash(
                {
                    "enhancer_id": enhancer_id,
                    "promoter_id": promoter_id,
                    "context_key": context_key,
                    "model_id": model_id,
                    "model_version": model_version,
                    "state": state,
                    "contact_state": contact_state,
                    "activity_state": activity_state,
                    "contact_component": contact_component,
                    "activity_component": activity_component,
                    "combined": combined,
                    "contacts": exact_contacts,
                    "activities": exact_activities,
                }
            ),
        )

    @staticmethod
    def _component(
        values: tuple[float, ...],
        scale: float,
        ambiguity_tolerance: float,
        *,
        has_other_context: bool,
    ) -> tuple[TopologyState, float | None]:
        if not values:
            return (
                TopologyState.OUT_OF_DOMAIN if has_other_context else TopologyState.ABSENT,
                None,
            )
        spread = max(values) - min(values) if len(values) > 1 else 0.0
        state = TopologyState.AMBIGUOUS if spread > ambiguity_tolerance else TopologyState.SUPPORTED
        return state, min(1.0, median(values) / scale)


def _rows(
    text: str,
    input_format: str | None,
    collection_key: str,
) -> tuple[tuple[Mapping[str, Any], ...], bool]:
    if not isinstance(text, str) or not text.strip():
        raise ValidationError("topology beta input must not be empty")
    selected = (input_format or "").lower().strip()
    if not selected:
        selected = "json" if text.lstrip().startswith(("{", "[")) else "tsv"
    if selected == "json":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"invalid topology beta JSON: {exc}") from exc
        rows = payload.get(collection_key, payload) if isinstance(payload, Mapping) else payload
        if isinstance(rows, Mapping):
            rows = [rows]
        if not isinstance(rows, list):
            raise ValidationError(f"topology beta JSON must contain a {collection_key} list")
        return tuple(rows), True
    if selected == "tsv":
        reader = csv.DictReader(io.StringIO(text), delimiter="\t")
        if not reader.fieldnames:
            raise ValidationError("topology beta TSV requires a header")
        return tuple(reader), False
    raise ValidationError(f"unsupported topology beta format: {selected}")


def _interval(row: Mapping[str, Any], label: str, coordinate_system: str) -> tuple[int, int]:
    start = int(
        _value(
            row,
            f"start_{label}",
            f"{label}_start",
            "start1" if label == "a" else "start2" if label == "b" else "start",
        )
    )
    end = int(
        _value(
            row,
            f"end_{label}",
            f"{label}_end",
            "end1" if label == "a" else "end2" if label == "b" else "end",
        )
    )
    if coordinate_system == "bed":
        if start < 0 or end <= start:
            raise ValidationError(
                f"{label} interval must satisfy 0 <= start < end in BED coordinates"
            )
        return start + 1, end
    if start < 1 or end < start:
        raise ValidationError(f"{label} interval must satisfy 1 <= start <= end")
    return start, end


def _value(row: Mapping[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        value = row.get(name)
        if value is not None and value != "":
            return value
    if default is not None:
        return default
    raise ValidationError(f"topology beta field is required: {names[0]}")


def _optional_text(row: Mapping[str, Any], *names: str) -> str | None:
    for name in names:
        value = row.get(name)
        if value is not None and value != "":
            return str(value)
    return None


def _optional_int(row: Mapping[str, Any], *names: str) -> int | None:
    value = _optional_text(row, *names)
    return None if value is None else int(value)


def _coerce_contact(
    value: EnhancerPromoterContactEvidence | Mapping[str, Any],
) -> EnhancerPromoterContactEvidence:
    if isinstance(value, EnhancerPromoterContactEvidence):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("contact evidence must be a mapping")
    return EnhancerPromoterContactEvidence(
        enhancer_id=str(value.get("enhancer_id", value.get("target_element_id", ""))),
        promoter_id=str(value.get("promoter_id", value.get("gene_id", ""))),
        signal=float(value.get("signal", value.get("contact_signal", 0.0))),
        context_key=str(value.get("context_key", value.get("context", ""))),
        source_id=str(value.get("source_id", "contact-input")),
        source_version=str(value.get("source_version", value.get("version", "unspecified"))),
        raw_hash=str(value.get("raw_hash", content_hash(dict(value)))),
        contact_id=str(value.get("contact_id", value.get("interaction_id", "contact-input"))),
        attributes=dict(value),
    )


def _coerce_activity(
    value: EnhancerActivityObservation | Mapping[str, Any],
) -> EnhancerActivityObservation:
    if isinstance(value, EnhancerActivityObservation):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("activity evidence must be a mapping")
    return EnhancerActivityObservation(
        enhancer_id=str(value.get("enhancer_id", value.get("element_id", ""))),
        activity_signal=float(
            value.get("activity_signal", value.get("signal", value.get("score", 0.0)))
        ),
        context_key=str(value.get("context_key", value.get("context", ""))),
        source_id=str(value.get("source_id", "activity-input")),
        source_version=str(value.get("source_version", value.get("version", "unspecified"))),
        raw_hash=str(value.get("raw_hash", content_hash(dict(value)))),
        replicate_id=(
            None if value.get("replicate_id") is None else str(value.get("replicate_id"))
        ),
        assay=str(value.get("assay", "activity")),
        attributes=dict(value),
    )


__all__ = [
    "ActivityByContactResult",
    "ActivityByContactScorer",
    "EnhancerActivityObservation",
    "EnhancerPromoterContactEvidence",
    "EnhancerPromoterContactScore",
    "EnhancerPromoterContactScorer",
    "LoopStripeAdapter",
    "LoopStripeBatch",
    "LoopStripeObservation",
    "PromoterCaptureBatch",
    "PromoterCaptureContact",
    "PromoterCaptureContactAdapter",
    "TopologyBetaIssue",
    "TopologyBetaKind",
]
