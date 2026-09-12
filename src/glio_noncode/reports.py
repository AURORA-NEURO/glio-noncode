"""Bounded, content-addressed reports over exact research dossiers.

The dossier is the scientific record. Reports are deterministic derived views;
they never substitute for dossier validation or the release gate.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .models import Dossier, EvidenceState, ResearchStatus
from .serialization import (
    canonical_bytes,
    canonical_json,
    content_hash,
    freeze_json,
    hash_bytes,
    jsonable,
)
from .validation import (
    DEFAULT_VALIDATION_LIMITS,
    ContractValidator,
    ReleaseGate,
    ValidationLimits,
)

REPORT_SUMMARY_VERSION = "dossier-summary-2026.09"
SUMMARY_ADDRESS_PREFIX = "dossier-summary"
REPORT_VERSION = "dossier-report-2026.09"
REPORT_ADDRESS_PREFIX = "dossier-report"
RENDERED_REPORT_VERSION = "rendered-dossier-report-2026.09"
RENDERED_REPORT_ADDRESS_PREFIX = "rendered-dossier-report"
REPORT_PAYLOAD_ADDRESS_PREFIX = "dossier-report-payload"

_HARD_MAX_REPORT_HYPOTHESES = 10_000
_HARD_MAX_REPORT_EVIDENCE_CLAIMS = 20_000
_HARD_MAX_REPORT_EXPERIMENTS = 10_000
_HARD_MAX_REPORT_EDGES_PER_HYPOTHESIS = 1_024
_HARD_MAX_REPORT_TOTAL_EDGES = 20_000
_HARD_MAX_REPORT_SEQUENCE_ITEMS = 20_000
_HARD_MAX_REPORT_SOURCE_RECEIPTS = 256_000
_HARD_MAX_REPORT_SOURCE_BUNDLES = 3_006
_HARD_MAX_REPORT_ISSUE_CODES = 256
_HARD_MAX_REPORT_TEXT_CHARACTERS = 1_048_576
_HARD_MAX_REPORT_TOTAL_CHARACTERS = 134_217_728
_HARD_MAX_REPORT_DOSSIER_BYTES = 134_217_728
_HARD_MAX_REPORT_SUMMARY_BYTES = 262_144
_HARD_MAX_REPORT_MARKDOWN_BYTES = 33_554_432
_HARD_MAX_RENDERED_REPORT_BYTES = 33_554_432
_HARD_MAX_REPORT_STRUCTURED_NODES = 1_000_000

# Public aliases advertise the supported maxima. The private copies above stay
# authoritative if a caller rebinds a module attribute.
MAX_REPORT_HYPOTHESES = _HARD_MAX_REPORT_HYPOTHESES
MAX_REPORT_EVIDENCE_CLAIMS = _HARD_MAX_REPORT_EVIDENCE_CLAIMS
MAX_REPORT_EXPERIMENTS = _HARD_MAX_REPORT_EXPERIMENTS
MAX_REPORT_EDGES_PER_HYPOTHESIS = _HARD_MAX_REPORT_EDGES_PER_HYPOTHESIS
MAX_REPORT_TOTAL_EDGES = _HARD_MAX_REPORT_TOTAL_EDGES
MAX_REPORT_SEQUENCE_ITEMS = _HARD_MAX_REPORT_SEQUENCE_ITEMS
MAX_REPORT_SOURCE_RECEIPTS = _HARD_MAX_REPORT_SOURCE_RECEIPTS
MAX_REPORT_SOURCE_BUNDLES = _HARD_MAX_REPORT_SOURCE_BUNDLES
MAX_REPORT_ISSUE_CODES = _HARD_MAX_REPORT_ISSUE_CODES
MAX_REPORT_TEXT_CHARACTERS = _HARD_MAX_REPORT_TEXT_CHARACTERS
MAX_REPORT_TOTAL_CHARACTERS = _HARD_MAX_REPORT_TOTAL_CHARACTERS
MAX_REPORT_DOSSIER_BYTES = _HARD_MAX_REPORT_DOSSIER_BYTES
MAX_REPORT_SUMMARY_BYTES = _HARD_MAX_REPORT_SUMMARY_BYTES
MAX_REPORT_MARKDOWN_BYTES = _HARD_MAX_REPORT_MARKDOWN_BYTES
MAX_RENDERED_REPORT_BYTES = _HARD_MAX_RENDERED_REPORT_BYTES
MAX_REPORT_STRUCTURED_NODES = _HARD_MAX_REPORT_STRUCTURED_NODES

_STATE_ORDER = tuple(state.value for state in EvidenceState)
_NEGATIVE_STATES = frozenset({EvidenceState.MEASURED_NEGATIVE, EvidenceState.CONTRADICTORY})
_MISSING_STATES = frozenset(
    {
        EvidenceState.ABSENT,
        EvidenceState.UNSUPPORTED,
        EvidenceState.ABSTAINED,
        EvidenceState.OUT_OF_DOMAIN,
    }
)
_SUMMARY_FIELDS = frozenset(
    {
        "report_version",
        "dossier_address",
        "input_address",
        "event_head",
        "policy_version",
        "case_id",
        "run_id",
        "status",
        "research_use_only",
        "is_releasable",
        "hypothesis_count",
        "edge_count",
        "evidence_count",
        "experiment_count",
        "warning_count",
        "supported_claim_count",
        "negative_claim_count",
        "missing_claim_count",
        "evidence_state_counts",
        "active_claim_count",
        "superseded_claim_count",
        "orphan_claim_count",
        "top_hypothesis_id",
        "top_support",
        "top_uncertainty",
        "recommended_experiment_id",
        "release_gate_valid",
        "release_gate_issue_codes",
        "content_address",
    }
)


class ReportAudience(StrEnum):
    """Explicit disclosure boundary for a report projection."""

    REVIEW = "review"
    PUBLIC = "public"


class ReportFormat(StrEnum):
    """Supported deterministic report encodings."""

    JSON = "json"
    MARKDOWN = "markdown"


def _positive_integer(value: object, field: str, ceiling: int) -> int:
    if type(value) is not int:
        raise ValidationError(f"{field} must be an integer")
    if value <= 0:
        raise ValidationError(f"{field} must be positive")
    if value > ceiling:
        raise ValidationError(f"{field} exceeds the safety ceiling of {ceiling}")
    return value


@dataclass(frozen=True, slots=True)
class ReportLimits:
    """Downward-configurable work and serialization limits for reports.

    ``max_source_receipts=None`` preserves the legacy coupling to
    ``max_sequence_items``. Public report functions use ``DEFAULT_REPORT_LIMITS``,
    which explicitly enables the supported 256,000-receipt capacity.
    """

    max_hypotheses: int = MAX_REPORT_HYPOTHESES
    max_evidence_claims: int = MAX_REPORT_EVIDENCE_CLAIMS
    max_experiments: int = MAX_REPORT_EXPERIMENTS
    max_edges_per_hypothesis: int = MAX_REPORT_EDGES_PER_HYPOTHESIS
    max_total_edges: int = MAX_REPORT_TOTAL_EDGES
    max_sequence_items: int = MAX_REPORT_SEQUENCE_ITEMS
    max_issue_codes: int = MAX_REPORT_ISSUE_CODES
    max_text_characters: int = MAX_REPORT_TEXT_CHARACTERS
    max_total_characters: int = MAX_REPORT_TOTAL_CHARACTERS
    max_dossier_bytes: int = MAX_REPORT_DOSSIER_BYTES
    max_summary_bytes: int = MAX_REPORT_SUMMARY_BYTES
    max_markdown_bytes: int = MAX_REPORT_MARKDOWN_BYTES
    max_rendered_report_bytes: int = MAX_RENDERED_REPORT_BYTES
    max_structured_nodes: int = MAX_REPORT_STRUCTURED_NODES
    max_source_receipts: int | None = None

    def __post_init__(self) -> None:
        for field, ceiling in (
            ("max_hypotheses", _HARD_MAX_REPORT_HYPOTHESES),
            ("max_evidence_claims", _HARD_MAX_REPORT_EVIDENCE_CLAIMS),
            ("max_experiments", _HARD_MAX_REPORT_EXPERIMENTS),
            ("max_edges_per_hypothesis", _HARD_MAX_REPORT_EDGES_PER_HYPOTHESIS),
            ("max_total_edges", _HARD_MAX_REPORT_TOTAL_EDGES),
            ("max_sequence_items", _HARD_MAX_REPORT_SEQUENCE_ITEMS),
            ("max_issue_codes", _HARD_MAX_REPORT_ISSUE_CODES),
            ("max_text_characters", _HARD_MAX_REPORT_TEXT_CHARACTERS),
            ("max_total_characters", _HARD_MAX_REPORT_TOTAL_CHARACTERS),
            ("max_dossier_bytes", _HARD_MAX_REPORT_DOSSIER_BYTES),
            ("max_summary_bytes", _HARD_MAX_REPORT_SUMMARY_BYTES),
            ("max_markdown_bytes", _HARD_MAX_REPORT_MARKDOWN_BYTES),
            ("max_rendered_report_bytes", _HARD_MAX_RENDERED_REPORT_BYTES),
            ("max_structured_nodes", _HARD_MAX_REPORT_STRUCTURED_NODES),
        ):
            _positive_integer(getattr(self, field), field, ceiling)
        if self.max_source_receipts is not None:
            _positive_integer(
                self.max_source_receipts,
                "max_source_receipts",
                _HARD_MAX_REPORT_SOURCE_RECEIPTS,
            )
        if self.max_edges_per_hypothesis > self.max_total_edges:
            raise ValidationError("max_edges_per_hypothesis cannot exceed max_total_edges")
        if self.max_text_characters > self.max_total_characters:
            raise ValidationError("max_text_characters cannot exceed max_total_characters")


DEFAULT_REPORT_LIMITS = ReportLimits(max_source_receipts=MAX_REPORT_SOURCE_RECEIPTS)


def _validated_limits(value: object) -> ReportLimits:
    if type(value) is not ReportLimits:
        raise ValidationError("limits must be an exact ReportLimits object")
    return ReportLimits(
        max_hypotheses=value.max_hypotheses,
        max_evidence_claims=value.max_evidence_claims,
        max_experiments=value.max_experiments,
        max_edges_per_hypothesis=value.max_edges_per_hypothesis,
        max_total_edges=value.max_total_edges,
        max_sequence_items=value.max_sequence_items,
        max_issue_codes=value.max_issue_codes,
        max_text_characters=value.max_text_characters,
        max_total_characters=value.max_total_characters,
        max_dossier_bytes=value.max_dossier_bytes,
        max_summary_bytes=value.max_summary_bytes,
        max_markdown_bytes=value.max_markdown_bytes,
        max_rendered_report_bytes=value.max_rendered_report_bytes,
        max_structured_nodes=value.max_structured_nodes,
        max_source_receipts=value.max_source_receipts,
    )


def _validation_limits(limits: ReportLimits) -> ValidationLimits:
    return ValidationLimits(
        max_hypotheses=limits.max_hypotheses,
        max_evidence_claims=limits.max_evidence_claims,
        max_experiments=limits.max_experiments,
        max_edges_per_hypothesis=limits.max_edges_per_hypothesis,
        max_total_edges=limits.max_total_edges,
        max_claims_per_edge=min(
            limits.max_evidence_claims,
            limits.max_sequence_items,
            10_000,
        ),
        max_dependencies_per_claim=min(limits.max_sequence_items, 10_000),
        max_source_receipts=(
            min(limits.max_sequence_items, _HARD_MAX_REPORT_SOURCE_RECEIPTS)
            if limits.max_source_receipts is None
            else limits.max_source_receipts
        ),
        max_source_bundles=min(
            limits.max_sequence_items,
            _HARD_MAX_REPORT_SOURCE_BUNDLES,
        ),
        max_sequence_items=limits.max_sequence_items,
        max_structured_nodes=limits.max_structured_nodes,
        max_string_characters=limits.max_text_characters,
        max_total_characters=limits.max_total_characters,
        max_canonical_bytes=limits.max_dossier_bytes,
        max_issues=DEFAULT_VALIDATION_LIMITS.max_issues,
    )


def _validate_dossier(value: object, limits: ReportLimits) -> Dossier:
    if type(value) is not Dossier:
        raise ValidationError("dossier must be an exact Dossier object")
    report = ContractValidator(limits=_validation_limits(limits)).validate_dossier(value)
    if not report.valid:
        codes = tuple(sorted({issue.code for issue in report.issues}))
        raise ValidationError(
            "dossier failed canonical contract validation before reporting: "
            + (", ".join(codes[:8]) or "unknown_validation_error")
        )
    return value


def _strict_dict(
    value: object,
    *,
    label: str,
    fields: frozenset[str],
) -> dict[str, Any]:
    if type(value) is not dict:
        raise ValidationError(f"{label} must be an exact JSON object")
    if any(type(key) is not str for key in value):
        raise ValidationError(f"{label} keys must be strings")
    unknown = set(value) - fields
    if unknown:
        raise ValidationError(f"{label} contains unknown fields: {sorted(unknown)}")
    missing = fields - set(value)
    if missing:
        raise ValidationError(f"{label} is missing required fields: {sorted(missing)}")
    return value


def _text(value: object, field: str, maximum: int) -> str:
    if type(value) is not str:
        raise ValidationError(f"{field} must be a string")
    if not value.strip():
        raise ValidationError(f"{field} must not be empty")
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds the safety ceiling of {maximum} characters")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValidationError(f"{field} must be valid UTF-8") from exc
    return value


def _nonnegative_integer(value: object, field: str, maximum: int) -> int:
    if type(value) is not int:
        raise ValidationError(f"{field} must be an integer")
    if value < 0 or value > maximum:
        raise ValidationError(f"{field} must be between 0 and {maximum}")
    return value


def _boolean(value: object, field: str) -> bool:
    if type(value) is not bool:
        raise ValidationError(f"{field} must be a boolean")
    return value


def _score(value: object, field: str) -> float | None:
    if value is None:
        return None
    if type(value) is not float or not 0.0 <= value <= 1.0:
        raise ValidationError(f"{field} must be a float between 0 and 1 or null")
    return value


def _address(value: object, prefix: str, field: str) -> str:
    if (
        type(value) is not str
        or len(value) != len(prefix) + 65
        or not value.startswith(prefix + ":")
        or any(character not in "0123456789abcdef" for character in value[len(prefix) + 1 :])
    ):
        raise ValidationError(f"{field} must be a canonical {prefix} content address")
    return value


def _state_counts(value: object) -> tuple[tuple[str, int], ...]:
    if type(value) is not tuple or len(value) != len(_STATE_ORDER):
        raise ValidationError("evidence_state_counts must cover every EvidenceState")
    result: list[tuple[str, int]] = []
    for index, item in enumerate(value):
        if type(item) is not tuple or len(item) != 2:
            raise ValidationError(f"evidence_state_counts[{index}] must be a pair")
        state, count = item
        if type(state) is not str or state != _STATE_ORDER[index]:
            raise ValidationError("evidence_state_counts must use canonical state order")
        result.append(
            (
                state,
                _nonnegative_integer(
                    count,
                    f"evidence_state_counts.{state}",
                    _HARD_MAX_REPORT_EVIDENCE_CLAIMS,
                ),
            )
        )
    return tuple(result)


def _state_counts_from_json(value: object) -> tuple[tuple[str, int], ...]:
    if type(value) is not dict or any(type(key) is not str for key in value):
        raise ValidationError("evidence_state_counts must be an exact JSON object")
    if set(value) != set(_STATE_ORDER):
        raise ValidationError("evidence_state_counts must cover exactly every EvidenceState")
    return tuple(
        (
            state,
            _nonnegative_integer(
                value[state],
                f"evidence_state_counts.{state}",
                _HARD_MAX_REPORT_EVIDENCE_CLAIMS,
            ),
        )
        for state in _STATE_ORDER
    )


def _issue_codes(value: object, limits: ReportLimits) -> tuple[str, ...]:
    if type(value) is not tuple:
        raise ValidationError("release_gate_issue_codes must be a tuple")
    if len(value) > limits.max_issue_codes:
        raise ValidationError("release_gate_issue_codes exceed the configured maximum")
    codes = tuple(
        _text(item, f"release_gate_issue_codes[{index}]", 128) for index, item in enumerate(value)
    )
    if codes != tuple(sorted(set(codes))):
        raise ValidationError("release_gate_issue_codes must be sorted and unique")
    return codes


def _summary_body(summary: DossierSummary) -> dict[str, object]:
    return {
        "report_version": summary.report_version,
        "dossier_address": summary.dossier_address,
        "input_address": summary.input_address,
        "event_head": summary.event_head,
        "policy_version": summary.policy_version,
        "case_id": summary.case_id,
        "run_id": summary.run_id,
        "status": summary.status,
        "research_use_only": summary.research_use_only,
        "is_releasable": summary.is_releasable,
        "hypothesis_count": summary.hypothesis_count,
        "edge_count": summary.edge_count,
        "evidence_count": summary.evidence_count,
        "experiment_count": summary.experiment_count,
        "warning_count": summary.warning_count,
        "supported_claim_count": summary.supported_claim_count,
        "negative_claim_count": summary.negative_claim_count,
        "missing_claim_count": summary.missing_claim_count,
        "evidence_state_counts": dict(summary.evidence_state_counts),
        "active_claim_count": summary.active_claim_count,
        "superseded_claim_count": summary.superseded_claim_count,
        "orphan_claim_count": summary.orphan_claim_count,
        "top_hypothesis_id": summary.top_hypothesis_id,
        "top_support": summary.top_support,
        "top_uncertainty": summary.top_uncertainty,
        "recommended_experiment_id": summary.recommended_experiment_id,
        "release_gate_valid": summary.release_gate_valid,
        "release_gate_issue_codes": list(summary.release_gate_issue_codes),
    }


@dataclass(frozen=True, slots=True)
class DossierSummary:
    """Strict, replay-verifiable aggregate view of one canonical dossier."""

    # Preserve the original attributes first for source-level compatibility.
    case_id: str
    run_id: str
    status: str
    hypothesis_count: int
    evidence_count: int
    supported_claim_count: int
    negative_claim_count: int
    missing_claim_count: int
    top_hypothesis_id: str | None
    top_support: float | None
    top_uncertainty: float | None
    recommended_experiment_id: str | None
    warning_count: int
    report_version: str
    dossier_address: str
    input_address: str
    event_head: str
    policy_version: str
    research_use_only: bool
    is_releasable: bool
    edge_count: int
    experiment_count: int
    evidence_state_counts: tuple[tuple[str, int], ...]
    active_claim_count: int
    superseded_claim_count: int
    orphan_claim_count: int
    release_gate_valid: bool
    release_gate_issue_codes: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        self._validated_body(DEFAULT_REPORT_LIMITS)

    def _validated_body(self, limits: ReportLimits) -> dict[str, object]:
        limits = _validated_limits(limits)
        if type(self.report_version) is not str or self.report_version != REPORT_SUMMARY_VERSION:
            raise ValidationError("dossier summary version is unsupported")
        _text(self.case_id, "dossier summary case_id", limits.max_text_characters)
        _text(self.run_id, "dossier summary run_id", limits.max_text_characters)
        _text(
            self.policy_version,
            "dossier summary policy_version",
            limits.max_text_characters,
        )
        _address(self.dossier_address, "sha256", "dossier summary dossier_address")
        _address(self.input_address, "sha256", "dossier summary input_address")
        _address(self.event_head, "sha256", "dossier summary event_head")
        if type(self.status) is not str:
            raise ValidationError("dossier summary status must be a string")
        try:
            ResearchStatus(self.status)
        except (TypeError, ValueError) as exc:
            raise ValidationError("dossier summary status is unsupported") from exc
        _boolean(self.research_use_only, "dossier summary research_use_only")
        _boolean(self.is_releasable, "dossier summary is_releasable")
        _boolean(self.release_gate_valid, "dossier summary release_gate_valid")
        for field, value, maximum in (
            ("hypothesis_count", self.hypothesis_count, limits.max_hypotheses),
            ("edge_count", self.edge_count, limits.max_total_edges),
            ("evidence_count", self.evidence_count, limits.max_evidence_claims),
            ("experiment_count", self.experiment_count, limits.max_experiments),
            ("warning_count", self.warning_count, limits.max_sequence_items),
            ("supported_claim_count", self.supported_claim_count, limits.max_evidence_claims),
            ("negative_claim_count", self.negative_claim_count, limits.max_evidence_claims),
            ("missing_claim_count", self.missing_claim_count, limits.max_evidence_claims),
            ("active_claim_count", self.active_claim_count, limits.max_evidence_claims),
            ("superseded_claim_count", self.superseded_claim_count, limits.max_evidence_claims),
            ("orphan_claim_count", self.orphan_claim_count, limits.max_evidence_claims),
        ):
            _nonnegative_integer(value, f"dossier summary {field}", maximum)
        counts = _state_counts(self.evidence_state_counts)
        if sum(count for _, count in counts) != self.evidence_count:
            raise ValidationError("evidence state counts do not conserve evidence_count")
        if (
            self.supported_claim_count + self.negative_claim_count + self.missing_claim_count
            != self.evidence_count
        ):
            raise ValidationError("grouped claim counts do not conserve evidence_count")
        if (
            self.active_claim_count + self.superseded_claim_count + self.orphan_claim_count
            != self.evidence_count
        ):
            raise ValidationError("claim lifecycle counts do not conserve evidence_count")
        if self.hypothesis_count:
            _text(
                self.top_hypothesis_id,
                "dossier summary top_hypothesis_id",
                limits.max_text_characters,
            )
            if _score(self.top_support, "dossier summary top_support") is None:
                raise ValidationError("a non-empty hypothesis set must have top_support")
            if _score(self.top_uncertainty, "dossier summary top_uncertainty") is None:
                raise ValidationError("a non-empty hypothesis set must have top_uncertainty")
        elif any(
            value is not None
            for value in (self.top_hypothesis_id, self.top_support, self.top_uncertainty)
        ):
            raise ValidationError("an empty hypothesis set cannot name a top hypothesis")
        if self.experiment_count:
            _text(
                self.recommended_experiment_id,
                "dossier summary recommended_experiment_id",
                limits.max_text_characters,
            )
        elif self.recommended_experiment_id is not None:
            raise ValidationError("an empty experiment set cannot name a recommendation")
        _issue_codes(self.release_gate_issue_codes, limits)
        body = _summary_body(self)
        expected = content_hash(body, prefix=SUMMARY_ADDRESS_PREFIX)
        if (
            _address(
                self.content_address,
                SUMMARY_ADDRESS_PREFIX,
                "dossier summary content_address",
            )
            != expected
        ):
            raise ValidationError("dossier summary content_address does not match its payload")
        payload = body | {"content_address": self.content_address}
        if len(canonical_bytes(payload)) > limits.max_summary_bytes:
            raise ValidationError("dossier summary exceeds its serialized-size ceiling")
        return body

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> DossierSummary:
        """Rehydrate an exact JSON representation and verify its address."""

        value = _strict_dict(raw, label="dossier summary", fields=_SUMMARY_FIELDS)
        raw_codes = value["release_gate_issue_codes"]
        if type(raw_codes) is not list or len(raw_codes) > _HARD_MAX_REPORT_ISSUE_CODES:
            raise ValidationError("release_gate_issue_codes must be a bounded JSON array")
        summary = cls(
            case_id=value["case_id"],
            run_id=value["run_id"],
            status=value["status"],
            hypothesis_count=value["hypothesis_count"],
            evidence_count=value["evidence_count"],
            supported_claim_count=value["supported_claim_count"],
            negative_claim_count=value["negative_claim_count"],
            missing_claim_count=value["missing_claim_count"],
            top_hypothesis_id=value["top_hypothesis_id"],
            top_support=value["top_support"],
            top_uncertainty=value["top_uncertainty"],
            recommended_experiment_id=value["recommended_experiment_id"],
            warning_count=value["warning_count"],
            report_version=value["report_version"],
            dossier_address=value["dossier_address"],
            input_address=value["input_address"],
            event_head=value["event_head"],
            policy_version=value["policy_version"],
            research_use_only=value["research_use_only"],
            is_releasable=value["is_releasable"],
            edge_count=value["edge_count"],
            experiment_count=value["experiment_count"],
            evidence_state_counts=_state_counts_from_json(value["evidence_state_counts"]),
            active_claim_count=value["active_claim_count"],
            superseded_claim_count=value["superseded_claim_count"],
            orphan_claim_count=value["orphan_claim_count"],
            release_gate_valid=value["release_gate_valid"],
            release_gate_issue_codes=tuple(raw_codes),
            content_address=value["content_address"],
        )
        if canonical_bytes(value) != canonical_bytes(summary.to_dict()):
            raise ValidationError("dossier summary is not an exact canonical typed representation")
        return summary

    def verify(self, dossier: Dossier) -> bool:
        """Fail closed unless this summary exactly recomputes from the dossier."""

        try:
            if type(dossier) is not Dossier or dossier.content_address != self.dossier_address:
                return False
            expected = summarize(dossier)
            return canonical_bytes(self.to_dict()) == canonical_bytes(expected.to_dict())
        except Exception:  # noqa: BLE001 - verification deliberately fails closed
            return False

    def to_dict(self) -> dict[str, object]:
        return self._validated_body(DEFAULT_REPORT_LIMITS) | {
            "content_address": self.content_address
        }


def _lifecycle(dossier: Dossier) -> tuple[dict[str, str], tuple[int, int, int]]:
    referenced = {
        claim_id
        for hypothesis in dossier.hypotheses
        for edge in hypothesis.edges
        for claim_id in edge.claim_ids
    }
    superseded = {claim.supersedes for claim in dossier.evidence if claim.supersedes is not None}
    states = {
        claim.evidence_id: (
            "superseded"
            if claim.evidence_id in superseded
            else "orphan"
            if claim.evidence_id not in referenced
            else "active"
        )
        for claim in dossier.evidence
    }
    counts = (
        sum(value == "active" for value in states.values()),
        sum(value == "superseded" for value in states.values()),
        sum(value == "orphan" for value in states.values()),
    )
    return states, counts


def summarize(
    dossier: Dossier,
    *,
    limits: ReportLimits | None = None,
) -> DossierSummary:
    """Create a compact authenticated view without hiding uncertainty states."""

    selected = _validated_limits(DEFAULT_REPORT_LIMITS if limits is None else limits)
    dossier = _validate_dossier(dossier, selected)
    top = min(
        dossier.hypotheses,
        key=lambda item: (-item.support, item.uncertainty, item.hypothesis_id),
        default=None,
    )
    recommended = min(
        dossier.experiments,
        key=lambda item: (-item.priority, item.option_id),
        default=None,
    )
    state_counts = tuple(
        (state.value, sum(claim.state is state for claim in dossier.evidence))
        for state in EvidenceState
    )
    by_state = dict(state_counts)
    _, lifecycle_counts = _lifecycle(dossier)
    gate = ReleaseGate(limits=_validation_limits(selected)).check(dossier)
    gate_codes = tuple(sorted({issue.code for issue in gate.issues}))
    if len(gate_codes) > selected.max_issue_codes:
        raise ValidationError("release gate issue codes exceed the report limit")
    values: dict[str, Any] = {
        "case_id": dossier.case_id,
        "run_id": dossier.run_id,
        "status": dossier.status.value,
        "hypothesis_count": len(dossier.hypotheses),
        "evidence_count": len(dossier.evidence),
        "supported_claim_count": by_state[EvidenceState.SUPPORTED.value],
        "negative_claim_count": sum(by_state[state.value] for state in _NEGATIVE_STATES),
        "missing_claim_count": sum(by_state[state.value] for state in _MISSING_STATES),
        "top_hypothesis_id": top.hypothesis_id if top else None,
        "top_support": top.support if top else None,
        "top_uncertainty": top.uncertainty if top else None,
        "recommended_experiment_id": recommended.option_id if recommended else None,
        "warning_count": len(dossier.warnings),
        "report_version": REPORT_SUMMARY_VERSION,
        "dossier_address": dossier.content_address,
        "input_address": dossier.input_address,
        "event_head": dossier.event_head,
        "policy_version": dossier.policy_version,
        "research_use_only": dossier.research_use_only,
        "is_releasable": dossier.is_releasable,
        "edge_count": sum(len(item.edges) for item in dossier.hypotheses),
        "experiment_count": len(dossier.experiments),
        "evidence_state_counts": state_counts,
        "active_claim_count": lifecycle_counts[0],
        "superseded_claim_count": lifecycle_counts[1],
        "orphan_claim_count": lifecycle_counts[2],
        "release_gate_valid": gate.valid,
        "release_gate_issue_codes": gate_codes,
    }
    body = {
        "report_version": values["report_version"],
        "dossier_address": values["dossier_address"],
        "input_address": values["input_address"],
        "event_head": values["event_head"],
        "policy_version": values["policy_version"],
        "case_id": values["case_id"],
        "run_id": values["run_id"],
        "status": values["status"],
        "research_use_only": values["research_use_only"],
        "is_releasable": values["is_releasable"],
        "hypothesis_count": values["hypothesis_count"],
        "edge_count": values["edge_count"],
        "evidence_count": values["evidence_count"],
        "experiment_count": values["experiment_count"],
        "warning_count": values["warning_count"],
        "supported_claim_count": values["supported_claim_count"],
        "negative_claim_count": values["negative_claim_count"],
        "missing_claim_count": values["missing_claim_count"],
        "evidence_state_counts": dict(state_counts),
        "active_claim_count": values["active_claim_count"],
        "superseded_claim_count": values["superseded_claim_count"],
        "orphan_claim_count": values["orphan_claim_count"],
        "top_hypothesis_id": values["top_hypothesis_id"],
        "top_support": values["top_support"],
        "top_uncertainty": values["top_uncertainty"],
        "recommended_experiment_id": values["recommended_experiment_id"],
        "release_gate_valid": values["release_gate_valid"],
        "release_gate_issue_codes": list(gate_codes),
    }
    summary = DossierSummary(
        **values,
        content_address=content_hash(body, prefix=SUMMARY_ADDRESS_PREFIX),
    )
    summary._validated_body(selected)
    return summary


def _markdown_text_parts(value: str) -> Iterator[str]:
    """Yield the legacy Markdown escaping one bounded fragment at a time."""

    first = 0
    while first < len(value):
        character = value[first]
        if not (
            character in "\r\n\t"
            or unicodedata.category(character).startswith("C")
            or character.isspace()
        ):
            break
        first += 1
    if first == len(value):
        return

    last = len(value)
    while last > first:
        character = value[last - 1]
        if not (
            character in "\r\n\t"
            or unicodedata.category(character).startswith("C")
            or character.isspace()
        ):
            break
        last -= 1

    previous_space = False
    for index in range(first, last):
        character = value[index]
        if character in "\r\n\t" or unicodedata.category(character).startswith("C"):
            if not previous_space:
                yield " "
                previous_space = True
            continue
        previous_space = character.isspace()
        if character == "&":
            yield "&amp;"
        elif character == "<":
            yield "&lt;"
        elif character == ">":
            yield "&gt;"
        elif character in "\\`*_{}[]()#!|":
            yield "\\" + character
        else:
            yield character


def _markdown_text(value: str) -> str:
    """Escape untrusted input into one safe Markdown text run."""

    return "".join(_markdown_text_parts(value))


class _BoundedMarkdownWriter:
    """Accumulate UTF-8 Markdown only after each fragment fits its byte budget."""

    __slots__ = ("_maximum", "_payload")

    def __init__(self, maximum: int) -> None:
        self._maximum = maximum
        self._payload = bytearray()

    def write(self, value: str) -> None:
        try:
            encoded = value.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ValidationError("dossier Markdown report must be valid UTF-8") from exc
        if len(encoded) > self._maximum - len(self._payload):
            raise ValidationError(
                "dossier Markdown report exceeds the configured maximum of "
                f"{self._maximum} bytes"
            )
        self._payload.extend(encoded)

    def write_text(self, value: str) -> None:
        for part in _markdown_text_parts(value):
            self.write(part)

    def write_joined_text(self, values: Iterable[str], separator: str = ", ") -> None:
        first = True
        for value in values:
            if not first:
                self.write(separator)
            self.write_text(value)
            first = False

    def newline(self, count: int = 1) -> None:
        self.write("\n" * count)

    def finish(self) -> str:
        return self._payload.decode("utf-8")


def _bounded_utf8(payload: str, maximum: int, field: str) -> bytes:
    try:
        encoded = payload.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValidationError(f"{field} must be valid UTF-8") from exc
    if len(encoded) > maximum:
        raise ValidationError(f"{field} exceeds the configured maximum of {maximum} bytes")
    return encoded


def render_markdown(
    dossier: Dossier,
    *,
    limits: ReportLimits | None = None,
) -> str:
    """Render a bounded review dossier with untrusted Markdown escaped."""

    selected = _validated_limits(DEFAULT_REPORT_LIMITS if limits is None else limits)
    summary = summarize(dossier, limits=selected)
    lifecycle, _ = _lifecycle(dossier)
    writer = _BoundedMarkdownWriter(selected.max_markdown_bytes)
    writer.write("# Research Dossier: ")
    writer.write_text(dossier.case_id)
    writer.newline(2)
    writer.write("- Status: ")
    writer.write_text(dossier.status.value)
    writer.newline()
    writer.write("- Run: ")
    writer.write_text(dossier.run_id)
    writer.newline()
    writer.write("- Research-use only: ")
    writer.write(str(dossier.research_use_only).lower())
    writer.newline()
    writer.write("- Policy: ")
    writer.write_text(dossier.policy_version)
    writer.newline()
    writer.write("- Input: ")
    writer.write_text(dossier.input_address)
    writer.newline()
    writer.write("- Content: ")
    writer.write_text(dossier.content_address)
    writer.newline()
    writer.write("- Summary: ")
    writer.write_text(summary.content_address)
    writer.newline()
    writer.write("- Release gate valid: ")
    writer.write(str(summary.release_gate_valid).lower())
    writer.newline(2)
    writer.write("## Evidence state summary")
    writer.newline(2)
    for state, count in summary.evidence_state_counts:
        writer.write("- ")
        writer.write_text(state)
        writer.write(": ")
        writer.write(str(count))
        writer.newline()
    writer.write("- Active: ")
    writer.write(str(summary.active_claim_count))
    writer.newline()
    writer.write("- Superseded: ")
    writer.write(str(summary.superseded_claim_count))
    writer.newline()
    writer.write("- Orphan: ")
    writer.write(str(summary.orphan_claim_count))
    writer.newline(2)
    writer.write("## Hypotheses")
    writer.newline(2)
    hypotheses = sorted(
        dossier.hypotheses,
        key=lambda item: (-item.support, item.uncertainty, item.hypothesis_id),
    )
    for index, hypothesis in enumerate(hypotheses, start=1):
        writer.write("### ")
        writer.write(str(index))
        writer.write(". ")
        writer.write_text(hypothesis.hypothesis_id)
        writer.newline()
        writer.write("- Variant: ")
        writer.write_text(hypothesis.variant_id)
        writer.newline()
        writer.write("- Element: ")
        writer.write_text(hypothesis.element_id)
        writer.newline()
        writer.write("- Gene: ")
        writer.write_text(hypothesis.gene_id)
        writer.newline()
        writer.write("- State: ")
        writer.write_text(hypothesis.state_id)
        writer.newline()
        writer.write("- Support: ")
        writer.write(canonical_json(hypothesis.support))
        writer.newline()
        writer.write("- Uncertainty: ")
        writer.write(canonical_json(hypothesis.uncertainty))
        writer.newline()
        writer.write("- Mechanism: ")
        writer.write_text(hypothesis.mechanism)
        writer.newline()
        writer.write("- Missing evidence: ")
        writer.write(str(len(hypothesis.missing_evidence)))
        writer.newline()
        writer.write("- Negative evidence: ")
        writer.write(str(len(hypothesis.negative_evidence)))
        writer.newline(2)
        for edge in hypothesis.edges:
            writer.write("  - ")
            writer.write_text(edge.edge_type.value)
            writer.write(" ")
            writer.write_text(edge.source_id)
            writer.write(" → ")
            writer.write_text(edge.target_id)
            writer.write("; support ")
            writer.write(canonical_json(edge.support))
            writer.write("; uncertainty ")
            writer.write(canonical_json(edge.uncertainty))
            writer.newline()
        writer.newline()
    writer.write("## Evidence ledger")
    writer.newline(2)
    for claim in dossier.evidence:
        writer.write("- ")
        writer.write_text(claim.evidence_id)
        writer.write(" [")
        writer.write(lifecycle[claim.evidence_id])
        writer.write("] ")
        writer.write_text(claim.state.value)
        writer.write(" ")
        writer.write_text(claim.channel)
        writer.write(": ")
        writer.write_text(claim.summary)
        writer.newline()
    writer.newline()
    writer.write("## Validation routes")
    writer.newline(2)
    experiments = sorted(
        dossier.experiments,
        key=lambda item: (-item.priority, item.option_id),
    )
    for option in experiments:
        writer.write("- ")
        writer.write_text(option.option_id)
        writer.write(" ")
        writer.write_text(option.assay.value)
        writer.write(" priority ")
        writer.write(canonical_json(option.priority))
        writer.newline()
        writer.write("  - Readouts: ")
        writer.write_joined_text(option.readouts)
        writer.newline()
        writer.write("  - Controls: ")
        writer.write_joined_text(option.controls)
        writer.newline()
        writer.write("  - Limitations: ")
        writer.write_joined_text(option.limitations)
        writer.newline()
    if dossier.warnings:
        writer.newline()
        writer.write("## Warnings")
        writer.newline(2)
        for warning in dossier.warnings:
            writer.write("- ")
            writer.write_text(warning)
            writer.newline()
    return writer.finish()


def render_json(
    dossier: Dossier,
    *,
    limits: ReportLimits | None = None,
) -> str:
    """Return bounded canonical dossier JSON, preserving legacy semantics."""

    selected = _validated_limits(DEFAULT_REPORT_LIMITS if limits is None else limits)
    dossier = _validate_dossier(dossier, selected)
    payload = canonical_json(dossier.to_dict())
    _bounded_utf8(payload, selected.max_dossier_bytes, "dossier JSON export")
    return payload


_REPORT_FIELDS = frozenset(
    {
        "report_version",
        "audience",
        "dossier_address",
        "summary_address",
        "projection",
        "content_address",
    }
)
_RENDERED_REPORT_FIELDS = frozenset(
    {
        "rendered_report_version",
        "report_address",
        "dossier_address",
        "audience",
        "format",
        "media_type",
        "byte_count",
        "line_count",
        "payload_address",
        "payload",
        "content_address",
    }
)
_PUBLIC_PROJECTION_FIELDS = frozenset(
    {
        "report_version",
        "audience",
        "dossier_address",
        "summary_address",
        "status",
        "research_use_only",
        "is_releasable",
        "hypothesis_count",
        "edge_count",
        "evidence_count",
        "experiment_count",
        "warning_count",
        "supported_claim_count",
        "negative_claim_count",
        "missing_claim_count",
        "evidence_state_counts",
        "active_claim_count",
        "superseded_claim_count",
        "orphan_claim_count",
        "release_gate_valid",
        "release_gate_issue_codes",
        "public_safe",
    }
)


def _audience(value: ReportAudience | str) -> ReportAudience:
    if type(value) is ReportAudience:
        return value
    if type(value) is str:
        try:
            return ReportAudience(value)
        except ValueError as exc:
            raise ValidationError("report audience must be review or public") from exc
    raise ValidationError("report audience must be an exact ReportAudience or string")


def _format(value: ReportFormat | str) -> ReportFormat:
    if type(value) is ReportFormat:
        return value
    if type(value) is str:
        try:
            return ReportFormat(value)
        except ValueError as exc:
            raise ValidationError("report format must be json or markdown") from exc
    raise ValidationError("report format must be an exact ReportFormat or string")


def _public_projection(summary: DossierSummary) -> dict[str, object]:
    """Return only aggregate, version, gate, and content-address fields."""

    return {
        "report_version": REPORT_VERSION,
        "audience": ReportAudience.PUBLIC.value,
        "dossier_address": summary.dossier_address,
        "summary_address": summary.content_address,
        "status": summary.status,
        "research_use_only": summary.research_use_only,
        "is_releasable": summary.is_releasable,
        "hypothesis_count": summary.hypothesis_count,
        "edge_count": summary.edge_count,
        "evidence_count": summary.evidence_count,
        "experiment_count": summary.experiment_count,
        "warning_count": summary.warning_count,
        "supported_claim_count": summary.supported_claim_count,
        "negative_claim_count": summary.negative_claim_count,
        "missing_claim_count": summary.missing_claim_count,
        "evidence_state_counts": dict(summary.evidence_state_counts),
        "active_claim_count": summary.active_claim_count,
        "superseded_claim_count": summary.superseded_claim_count,
        "orphan_claim_count": summary.orphan_claim_count,
        "release_gate_valid": summary.release_gate_valid,
        "release_gate_issue_codes": list(summary.release_gate_issue_codes),
        "public_safe": True,
    }


def _validate_public_projection(value: dict[str, Any]) -> None:
    _strict_dict(
        value,
        label="public dossier report projection",
        fields=_PUBLIC_PROJECTION_FIELDS,
    )
    if (
        type(value["report_version"]) is not str
        or value["report_version"] != REPORT_VERSION
        or type(value["audience"]) is not str
        or value["audience"] != "public"
    ):
        raise ValidationError("public report version or audience is invalid")
    _address(value["dossier_address"], "sha256", "public report dossier_address")
    _address(
        value["summary_address"],
        SUMMARY_ADDRESS_PREFIX,
        "public report summary_address",
    )
    if type(value["status"]) is not str:
        raise ValidationError("public report status must be a string")
    try:
        ResearchStatus(value["status"])
    except (TypeError, ValueError) as exc:
        raise ValidationError("public report status is unsupported") from exc
    for field in (
        "research_use_only",
        "is_releasable",
        "release_gate_valid",
        "public_safe",
    ):
        _boolean(value[field], f"public report {field}")
    if value["public_safe"] is not True:
        raise ValidationError("public report must retain the public_safe boundary")
    for field, maximum in (
        ("hypothesis_count", _HARD_MAX_REPORT_HYPOTHESES),
        ("edge_count", _HARD_MAX_REPORT_TOTAL_EDGES),
        ("evidence_count", _HARD_MAX_REPORT_EVIDENCE_CLAIMS),
        ("experiment_count", _HARD_MAX_REPORT_EXPERIMENTS),
        ("warning_count", _HARD_MAX_REPORT_SEQUENCE_ITEMS),
        ("supported_claim_count", _HARD_MAX_REPORT_EVIDENCE_CLAIMS),
        ("negative_claim_count", _HARD_MAX_REPORT_EVIDENCE_CLAIMS),
        ("missing_claim_count", _HARD_MAX_REPORT_EVIDENCE_CLAIMS),
        ("active_claim_count", _HARD_MAX_REPORT_EVIDENCE_CLAIMS),
        ("superseded_claim_count", _HARD_MAX_REPORT_EVIDENCE_CLAIMS),
        ("orphan_claim_count", _HARD_MAX_REPORT_EVIDENCE_CLAIMS),
    ):
        _nonnegative_integer(value[field], f"public report {field}", maximum)
    counts = _state_counts_from_json(value["evidence_state_counts"])
    evidence_count = value["evidence_count"]
    if sum(count for _, count in counts) != evidence_count:
        raise ValidationError("public report state counts do not conserve evidence_count")
    if (
        value["supported_claim_count"]
        + value["negative_claim_count"]
        + value["missing_claim_count"]
        != evidence_count
    ):
        raise ValidationError("public report grouped counts do not conserve evidence_count")
    if (
        value["active_claim_count"] + value["superseded_claim_count"] + value["orphan_claim_count"]
        != evidence_count
    ):
        raise ValidationError("public report lifecycle counts do not conserve evidence_count")
    raw_codes = value["release_gate_issue_codes"]
    if type(raw_codes) is not list:
        raise ValidationError("public report release_gate_issue_codes must be a JSON array")
    _issue_codes(tuple(raw_codes), DEFAULT_REPORT_LIMITS)


def _report_body(report: DossierReport) -> dict[str, object]:
    return {
        "report_version": report.report_version,
        "audience": report.audience,
        "dossier_address": report.dossier_address,
        "summary_address": report.summary_address,
        "projection": jsonable(report.projection),
    }


@dataclass(frozen=True, slots=True)
class DossierReport:
    """Addressed review or aggregate-only public summary projection."""

    report_version: str
    audience: str
    dossier_address: str
    summary_address: str
    projection: Mapping[str, Any]
    content_address: str

    def __post_init__(self) -> None:
        if type(self.projection) is not dict:
            raise ValidationError("dossier report projection must be an exact JSON object")
        self._validated_body()
        object.__setattr__(
            self,
            "projection",
            freeze_json(self.projection, field="dossier report projection"),
        )

    def _validated_body(self) -> dict[str, object]:
        if type(self.report_version) is not str or self.report_version != REPORT_VERSION:
            raise ValidationError("dossier report version is unsupported")
        if type(self.audience) is not str:
            raise ValidationError("dossier report audience must be a string")
        audience = _audience(self.audience)
        _address(self.dossier_address, "sha256", "dossier report dossier_address")
        _address(
            self.summary_address,
            SUMMARY_ADDRESS_PREFIX,
            "dossier report summary_address",
        )
        projection = jsonable(self.projection)
        if type(projection) is not dict:
            raise ValidationError("dossier report projection must be a JSON object")
        if audience is ReportAudience.REVIEW:
            summary = DossierSummary.from_dict(projection)
            if (
                summary.dossier_address != self.dossier_address
                or summary.content_address != self.summary_address
            ):
                raise ValidationError("review report projection has mismatched provenance")
        else:
            _validate_public_projection(projection)
            if (
                projection["dossier_address"] != self.dossier_address
                or projection["summary_address"] != self.summary_address
            ):
                raise ValidationError("public report projection has mismatched provenance")
        body = _report_body(self)
        expected = content_hash(body, prefix=REPORT_ADDRESS_PREFIX)
        if (
            _address(
                self.content_address,
                REPORT_ADDRESS_PREFIX,
                "dossier report content_address",
            )
            != expected
        ):
            raise ValidationError("dossier report content_address does not match its payload")
        if (
            len(canonical_bytes(body | {"content_address": self.content_address}))
            > _HARD_MAX_REPORT_SUMMARY_BYTES
        ):
            raise ValidationError("dossier report exceeds its serialized-size ceiling")
        return body

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> DossierReport:
        value = _strict_dict(raw, label="dossier report", fields=_REPORT_FIELDS)
        projection = value["projection"]
        if type(projection) is not dict:
            raise ValidationError("dossier report projection must be an exact JSON object")
        report = cls(
            report_version=value["report_version"],
            audience=value["audience"],
            dossier_address=value["dossier_address"],
            summary_address=value["summary_address"],
            projection=projection,
            content_address=value["content_address"],
        )
        if canonical_bytes(value) != canonical_bytes(report.to_dict()):
            raise ValidationError("dossier report is not an exact canonical representation")
        return report

    def verify(self, dossier: Dossier) -> bool:
        """Recompute this projection against its claimed source dossier."""

        try:
            if type(dossier) is not Dossier or dossier.content_address != self.dossier_address:
                return False
            expected = build_report(dossier, audience=ReportAudience(self.audience))
            return canonical_bytes(self.to_dict()) == canonical_bytes(expected.to_dict())
        except Exception:  # noqa: BLE001 - verification deliberately fails closed
            return False

    def to_dict(self) -> dict[str, object]:
        return self._validated_body() | {"content_address": self.content_address}


def build_report(
    dossier: Dossier,
    *,
    audience: ReportAudience | str = ReportAudience.REVIEW,
    limits: ReportLimits | None = None,
) -> DossierReport:
    """Build a deterministic, explicitly audience-scoped dossier report."""

    selected_limits = _validated_limits(DEFAULT_REPORT_LIMITS if limits is None else limits)
    selected_audience = _audience(audience)
    summary = summarize(dossier, limits=selected_limits)
    projection = (
        summary.to_dict()
        if selected_audience is ReportAudience.REVIEW
        else _public_projection(summary)
    )
    body = {
        "report_version": REPORT_VERSION,
        "audience": selected_audience.value,
        "dossier_address": summary.dossier_address,
        "summary_address": summary.content_address,
        "projection": projection,
    }
    report = DossierReport(
        report_version=REPORT_VERSION,
        audience=selected_audience.value,
        dossier_address=summary.dossier_address,
        summary_address=summary.content_address,
        projection=projection,
        content_address=content_hash(body, prefix=REPORT_ADDRESS_PREFIX),
    )
    if len(canonical_bytes(report.to_dict())) > selected_limits.max_summary_bytes:
        raise ValidationError("dossier report exceeds the configured serialized-size limit")
    return report


def _compact_markdown(report: DossierReport) -> str:
    projection = jsonable(report.projection)
    if type(projection) is not dict:  # pragma: no cover - constructor invariant
        raise ValidationError("dossier report projection must be a JSON object")
    title = "Public Dossier Report" if report.audience == "public" else "Review Dossier Report"
    lines = [
        f"# {title}",
        "",
        f"- Report: {_markdown_text(report.content_address)}",
        f"- Dossier: {_markdown_text(report.dossier_address)}",
        f"- Summary: {_markdown_text(report.summary_address)}",
        f"- Status: {_markdown_text(str(projection['status']))}",
        f"- Research-use only: {str(projection['research_use_only']).lower()}",
        f"- Release gate valid: {str(projection['release_gate_valid']).lower()}",
    ]
    if report.audience == "review":
        top = projection["top_hypothesis_id"]
        experiment = projection["recommended_experiment_id"]
        lines.extend(
            [
                f"- Case: {_markdown_text(str(projection['case_id']))}",
                f"- Run: {_markdown_text(str(projection['run_id']))}",
                f"- Top hypothesis: {'none' if top is None else _markdown_text(str(top))}",
                "- Recommended experiment: "
                + ("none" if experiment is None else _markdown_text(str(experiment))),
            ]
        )
    lines.extend(
        [
            "",
            "## Counts",
            "",
            f"- Hypotheses: {projection['hypothesis_count']}",
            f"- Edges: {projection['edge_count']}",
            f"- Evidence: {projection['evidence_count']}",
            f"- Experiments: {projection['experiment_count']}",
            f"- Warnings: {projection['warning_count']}",
            f"- Active evidence: {projection['active_claim_count']}",
            f"- Superseded evidence: {projection['superseded_claim_count']}",
            f"- Orphan evidence: {projection['orphan_claim_count']}",
            "",
            "## Evidence states",
            "",
        ]
    )
    states = projection["evidence_state_counts"]
    if not isinstance(states, Mapping):  # pragma: no cover - projection invariant
        raise ValidationError("report evidence_state_counts must be an object")
    lines.extend(f"- {_markdown_text(state)}: {states[state]}" for state in _STATE_ORDER)
    codes = projection["release_gate_issue_codes"]
    if codes:
        lines.extend(["", "## Release gate issue codes", ""])
        lines.extend(f"- {_markdown_text(str(code))}" for code in codes)
    lines.append("")
    return "\n".join(lines)


def _rendered_body(value: RenderedReport) -> dict[str, object]:
    return {
        "rendered_report_version": value.rendered_report_version,
        "report_address": value.report_address,
        "dossier_address": value.dossier_address,
        "audience": value.audience,
        "format": value.format,
        "media_type": value.media_type,
        "byte_count": value.byte_count,
        "line_count": value.line_count,
        "payload_address": value.payload_address,
        "payload": value.payload,
    }


@dataclass(frozen=True, slots=True)
class RenderedReport:
    """A report projection bound to its exact UTF-8 rendering."""

    rendered_report_version: str
    report_address: str
    dossier_address: str
    audience: str
    format: str
    media_type: str
    byte_count: int
    line_count: int
    payload_address: str
    payload: str
    content_address: str

    def __post_init__(self) -> None:
        self._validated_body(DEFAULT_REPORT_LIMITS)

    def _validated_body(self, limits: ReportLimits) -> dict[str, object]:
        limits = _validated_limits(limits)
        if (
            type(self.rendered_report_version) is not str
            or self.rendered_report_version != RENDERED_REPORT_VERSION
        ):
            raise ValidationError("rendered report version is unsupported")
        _address(self.report_address, REPORT_ADDRESS_PREFIX, "rendered report report_address")
        _address(self.dossier_address, "sha256", "rendered report dossier_address")
        if type(self.audience) is not str:
            raise ValidationError("rendered report audience must be a string")
        _audience(self.audience)
        if type(self.format) is not str:
            raise ValidationError("rendered report format must be a string")
        selected_format = _format(self.format)
        media_type = (
            "application/json"
            if selected_format is ReportFormat.JSON
            else "text/markdown; charset=utf-8"
        )
        if type(self.media_type) is not str or self.media_type != media_type:
            raise ValidationError("rendered report media_type does not match its format")
        if type(self.payload) is not str:
            raise ValidationError("rendered report payload must be a string")
        encoded = _bounded_utf8(
            self.payload,
            limits.max_rendered_report_bytes,
            "rendered report payload",
        )
        if self.byte_count != len(encoded) or type(self.byte_count) is not int:
            raise ValidationError("rendered report byte_count does not match its payload")
        if self.line_count != len(self.payload.splitlines()) or type(self.line_count) is not int:
            raise ValidationError("rendered report line_count does not match its payload")
        expected_payload_address = hash_bytes(
            encoded,
            prefix=REPORT_PAYLOAD_ADDRESS_PREFIX,
        )
        if (
            _address(
                self.payload_address,
                REPORT_PAYLOAD_ADDRESS_PREFIX,
                "rendered report payload_address",
            )
            != expected_payload_address
        ):
            raise ValidationError("rendered report payload_address does not match its bytes")
        body = _rendered_body(self)
        expected = content_hash(body, prefix=RENDERED_REPORT_ADDRESS_PREFIX)
        if (
            _address(
                self.content_address,
                RENDERED_REPORT_ADDRESS_PREFIX,
                "rendered report content_address",
            )
            != expected
        ):
            raise ValidationError("rendered report content_address does not match its payload")
        return body

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> RenderedReport:
        value = _strict_dict(
            raw,
            label="rendered dossier report",
            fields=_RENDERED_REPORT_FIELDS,
        )
        rendered = cls(
            rendered_report_version=value["rendered_report_version"],
            report_address=value["report_address"],
            dossier_address=value["dossier_address"],
            audience=value["audience"],
            format=value["format"],
            media_type=value["media_type"],
            byte_count=value["byte_count"],
            line_count=value["line_count"],
            payload_address=value["payload_address"],
            payload=value["payload"],
            content_address=value["content_address"],
        )
        if canonical_bytes(value) != canonical_bytes(rendered.to_dict()):
            raise ValidationError("rendered report is not an exact canonical representation")
        return rendered

    def verify(self, report: DossierReport) -> bool:
        """Re-render the claimed report and compare every byte and field."""

        try:
            if (
                type(report) is not DossierReport
                or report.content_address != self.report_address
                or report.dossier_address != self.dossier_address
                or report.audience != self.audience
            ):
                return False
            expected = render_report(report, format=ReportFormat(self.format))
            return canonical_bytes(self.to_dict()) == canonical_bytes(expected.to_dict())
        except Exception:  # noqa: BLE001 - verification deliberately fails closed
            return False

    def to_dict(self) -> dict[str, object]:
        return self._validated_body(DEFAULT_REPORT_LIMITS) | {
            "content_address": self.content_address
        }


def render_report(
    report: DossierReport,
    *,
    format: ReportFormat | str = ReportFormat.JSON,
    limits: ReportLimits | None = None,
) -> RenderedReport:
    """Render and byte-address a report projection."""

    selected_limits = _validated_limits(DEFAULT_REPORT_LIMITS if limits is None else limits)
    if type(report) is not DossierReport:
        raise ValidationError("report must be an exact DossierReport object")
    report.to_dict()
    selected_format = _format(format)
    payload = (
        canonical_json(report.to_dict())
        if selected_format is ReportFormat.JSON
        else _compact_markdown(report)
    )
    encoded = _bounded_utf8(
        payload,
        selected_limits.max_rendered_report_bytes,
        "rendered report payload",
    )
    values: dict[str, Any] = {
        "rendered_report_version": RENDERED_REPORT_VERSION,
        "report_address": report.content_address,
        "dossier_address": report.dossier_address,
        "audience": report.audience,
        "format": selected_format.value,
        "media_type": (
            "application/json"
            if selected_format is ReportFormat.JSON
            else "text/markdown; charset=utf-8"
        ),
        "byte_count": len(encoded),
        "line_count": len(payload.splitlines()),
        "payload_address": hash_bytes(encoded, prefix=REPORT_PAYLOAD_ADDRESS_PREFIX),
        "payload": payload,
    }
    rendered = RenderedReport(
        **values,
        content_address=content_hash(values, prefix=RENDERED_REPORT_ADDRESS_PREFIX),
    )
    rendered._validated_body(selected_limits)
    return rendered


def render_report_json(
    report: DossierReport,
    *,
    limits: ReportLimits | None = None,
) -> str:
    """Render canonical JSON without changing legacy :func:`render_json`."""

    return render_report(report, format=ReportFormat.JSON, limits=limits).payload


def render_report_markdown(
    report: DossierReport,
    *,
    limits: ReportLimits | None = None,
) -> str:
    """Render a safe, compact Markdown report projection."""

    return render_report(report, format=ReportFormat.MARKDOWN, limits=limits).payload


def report_capabilities() -> dict[str, object]:
    """Return deterministic discovery metadata for future transport surfaces."""

    return {
        "summary_version": REPORT_SUMMARY_VERSION,
        "report_version": REPORT_VERSION,
        "rendered_report_version": RENDERED_REPORT_VERSION,
        "audiences": [item.value for item in ReportAudience],
        "formats": [item.value for item in ReportFormat],
        "features": [
            "exact canonical dossier validation",
            "all-state and lifecycle count conservation",
            "deterministic ranking",
            "content-addressed projections and UTF-8 payloads",
            "bounded Markdown and JSON",
            "aggregate-only public projection",
        ],
        "public_projection_fields": sorted(_PUBLIC_PROJECTION_FIELDS),
        "hard_limits": {
            "hypotheses": _HARD_MAX_REPORT_HYPOTHESES,
            "evidence_claims": _HARD_MAX_REPORT_EVIDENCE_CLAIMS,
            "experiments": _HARD_MAX_REPORT_EXPERIMENTS,
            "total_edges": _HARD_MAX_REPORT_TOTAL_EDGES,
            "source_receipts": _HARD_MAX_REPORT_SOURCE_RECEIPTS,
            "source_bundles": _HARD_MAX_REPORT_SOURCE_BUNDLES,
            "structured_nodes": _HARD_MAX_REPORT_STRUCTURED_NODES,
            "total_characters": _HARD_MAX_REPORT_TOTAL_CHARACTERS,
            "summary_bytes": _HARD_MAX_REPORT_SUMMARY_BYTES,
            "rendered_report_bytes": _HARD_MAX_RENDERED_REPORT_BYTES,
        },
    }


__all__ = [
    "DEFAULT_REPORT_LIMITS",
    "DossierReport",
    "DossierSummary",
    "RENDERED_REPORT_VERSION",
    "REPORT_VERSION",
    "REPORT_SUMMARY_VERSION",
    "RenderedReport",
    "ReportAudience",
    "ReportFormat",
    "ReportLimits",
    "build_report",
    "render_report",
    "render_report_json",
    "render_report_markdown",
    "render_json",
    "render_markdown",
    "report_capabilities",
    "summarize",
]
