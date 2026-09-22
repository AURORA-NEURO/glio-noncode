"""Append-only evidence graph and dependence-aware aggregation."""

from __future__ import annotations

import hashlib
import heapq
import math
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from threading import RLock
from typing import cast

from .errors import ValidationError
from .models import (
    EdgeType,
    EvidenceClaim,
    EvidenceState,
    EvidenceTier,
    HypothesisEdge,
    ReferenceContext,
    SupportLevel,
)
from .serialization import canonical_bytes, freeze_json

MAX_EVIDENCE_CLAIMS = 20_000
"""Hard ceiling for claims retained by one in-memory graph."""

MAX_EVIDENCE_CLAIMS_PER_EDGE = 10_000
"""Hard ceiling for claims attached to one hypothesis edge."""

MAX_EVIDENCE_DEPENDENCIES_PER_CLAIM = 10_000
"""Hard ceiling for the lineage references carried by one claim."""

MAX_EVIDENCE_CLAIM_BYTES = 16 * 1024 * 1024
"""Maximum canonical JSON size of one claim."""

MAX_EVIDENCE_GRAPH_BYTES = 128 * 1024 * 1024
"""Maximum combined canonical JSON size of claims in one graph."""


def _bounded_positive_integer(value: object, field_name: str, ceiling: int) -> int:
    if type(value) is not int:
        raise ValidationError(f"{field_name} must be an integer")
    if value < 1:
        raise ValidationError(f"{field_name} must be positive")
    if value > ceiling:
        raise ValidationError(f"{field_name} must not exceed the safety ceiling of {ceiling}")
    return value


def _required_string(value: object, field_name: str) -> str:
    if type(value) is not str:
        raise ValidationError(f"{field_name} must be a string")
    if not value.strip():
        raise ValidationError(f"{field_name} must not be empty")
    return value


def _unit_interval(value: object, field_name: str) -> float:
    if type(value) not in {int, float}:
        raise ValidationError(f"{field_name} must be a finite number")
    try:
        number = float(cast(int | float, value))
    except OverflowError as exc:
        raise ValidationError(f"{field_name} must be a finite number") from exc
    if not math.isfinite(number):
        raise ValidationError(f"{field_name} must be a finite number")
    if not 0.0 <= number <= 1.0:
        raise ValidationError(f"{field_name} must be between 0 and 1")
    return number


def _canonical_content_address(value: object, field_name: str) -> str:
    address = _required_string(value, field_name)
    prefix, separator, digest = address.rpartition(":")
    if (
        separator != ":"
        or not prefix
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ValidationError(f"{field_name} must be a canonical content address")
    return address


def _safe_fsum(values: Iterable[float], field_name: str) -> float:
    try:
        result = math.fsum(values)
    except (OverflowError, ValueError) as exc:
        raise ValidationError(f"{field_name} overflowed finite arithmetic") from exc
    if not math.isfinite(result):
        raise ValidationError(f"{field_name} must remain finite")
    return result


@dataclass(frozen=True, slots=True)
class EvidenceGraphLimits:
    """Hard-ceiling, downward-configurable limits for an evidence graph."""

    max_claims: int = MAX_EVIDENCE_CLAIMS
    max_claims_per_edge: int = MAX_EVIDENCE_CLAIMS_PER_EDGE
    max_dependencies_per_claim: int = MAX_EVIDENCE_DEPENDENCIES_PER_CLAIM
    max_claim_bytes: int = MAX_EVIDENCE_CLAIM_BYTES
    max_graph_bytes: int = MAX_EVIDENCE_GRAPH_BYTES

    def __post_init__(self) -> None:
        for field_name, ceiling in (
            ("max_claims", MAX_EVIDENCE_CLAIMS),
            ("max_claims_per_edge", MAX_EVIDENCE_CLAIMS_PER_EDGE),
            ("max_dependencies_per_claim", MAX_EVIDENCE_DEPENDENCIES_PER_CLAIM),
            ("max_claim_bytes", MAX_EVIDENCE_CLAIM_BYTES),
            ("max_graph_bytes", MAX_EVIDENCE_GRAPH_BYTES),
        ):
            object.__setattr__(
                self,
                field_name,
                _bounded_positive_integer(getattr(self, field_name), field_name, ceiling),
            )


DEFAULT_EVIDENCE_GRAPH_LIMITS = EvidenceGraphLimits()


@dataclass(frozen=True, slots=True)
class AggregateSupport:
    """Transparent aggregate with source grouping and negative evidence."""

    score: float
    uncertainty: float
    context_support: float
    supported_claim_ids: tuple[str, ...]
    negative_claim_ids: tuple[str, ...]
    missing_claim_ids: tuple[str, ...]
    channel_groups: tuple[str, ...]
    rationale: str
    context_support_claim_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("score", "uncertainty", "context_support"):
            object.__setattr__(
                self,
                field_name,
                _unit_interval(getattr(self, field_name), field_name),
            )
        claim_id_groups = (
            self.supported_claim_ids,
            self.negative_claim_ids,
            self.missing_claim_ids,
        )
        for field_name, values in (
            ("supported_claim_ids", self.supported_claim_ids),
            ("negative_claim_ids", self.negative_claim_ids),
            ("missing_claim_ids", self.missing_claim_ids),
            ("channel_groups", self.channel_groups),
            ("context_support_claim_ids", self.context_support_claim_ids),
        ):
            if type(values) is not tuple:
                raise ValidationError(f"{field_name} must be a tuple")
            for index, value in enumerate(values):
                _required_string(value, f"{field_name}[{index}]")
            if len(values) > MAX_EVIDENCE_CLAIMS:
                raise ValidationError(
                    f"{field_name} exceeds the safety ceiling of {MAX_EVIDENCE_CLAIMS} items"
                )
            if len(values) != len(set(values)):
                raise ValidationError(f"{field_name} must contain unique values")
            if values != tuple(sorted(values)):
                raise ValidationError(f"{field_name} must use canonical sorted order")
        classified_ids = tuple(item for values in claim_id_groups for item in values)
        if len(classified_ids) != len(set(classified_ids)):
            raise ValidationError("aggregate claim classifications must be disjoint")
        informative_ids = set(self.supported_claim_ids) | set(self.negative_claim_ids)
        if not set(self.context_support_claim_ids).issubset(informative_ids):
            raise ValidationError(
                "context support claim IDs must identify supported or negative claims"
            )
        if self.context_support > 0.0 and not self.context_support_claim_ids:
            raise ValidationError(
                "non-zero context support requires auditable context support claim IDs"
            )
        if len(self.context_support_claim_ids) > len(self.channel_groups):
            raise ValidationError(
                "context support claim IDs cannot exceed the number of channel groups"
            )
        _required_string(self.rationale, "rationale")

    def to_dict(self) -> dict[str, object]:
        return {
            "score": self.score,
            "uncertainty": self.uncertainty,
            "context_support": self.context_support,
            "context_support_claim_ids": list(self.context_support_claim_ids),
            "supported_claim_ids": list(self.supported_claim_ids),
            "negative_claim_ids": list(self.negative_claim_ids),
            "missing_claim_ids": list(self.missing_claim_ids),
            "channel_groups": list(self.channel_groups),
            "rationale": self.rationale,
        }


class EvidenceGraph:
    """Bounded in-memory append-only graph used by a single case run."""

    def __init__(self, *, limits: EvidenceGraphLimits | None = None) -> None:
        selected = DEFAULT_EVIDENCE_GRAPH_LIMITS if limits is None else limits
        if not isinstance(selected, EvidenceGraphLimits):
            raise ValidationError("limits must be EvidenceGraphLimits")
        self.limits = selected
        self._claims: dict[str, EvidenceClaim] = {}
        self._edge_claims: dict[str, list[str]] = defaultdict(list)
        self._claim_fingerprints: dict[str, bytes] = {}
        self._claim_sizes: dict[str, int] = {}
        self._external_dependencies: set[str] = set()
        self._edge_bindings: dict[str, tuple[EdgeType, str, str]] = {}
        self._context_fingerprint: bytes | None = None
        self._graph_bytes = 0
        self._lock = RLock()

    def append(self, claim: EvidenceClaim) -> None:
        """Append one claim atomically after validating identity and lineage closure."""

        self.extend((claim,))

    def extend(self, claims: Iterable[EvidenceClaim]) -> None:
        """Atomically append a bounded, causally ordered claim iterable."""

        if isinstance(claims, (str, bytes, bytearray, Mapping)):
            raise ValidationError("claims must be an iterable of EvidenceClaim objects")
        try:
            iterator = iter(claims)
        except TypeError as exc:
            raise ValidationError("claims must be iterable") from exc

        with self._lock:
            remaining = self.limits.max_claims - len(self._claims)
            staged: list[tuple[EvidenceClaim, bytes, int]] = []
            staged_by_id: dict[str, EvidenceClaim] = {}
            staged_fingerprints: dict[str, bytes] = {}
            edge_counts: dict[str, int] = {}
            external_dependencies = set(self._external_dependencies)
            context_fingerprint = self._context_fingerprint
            projected_bytes = self._graph_bytes

            for index, claim in enumerate(iterator):
                if index >= remaining:
                    raise ValidationError(
                        "evidence graph exceeds the configured maximum of "
                        f"{self.limits.max_claims} claims"
                    )
                canonical, fingerprint = self._validate_claim(claim)
                evidence_id = claim.evidence_id
                claim_context_fingerprint = self._claim_context_fingerprint(claim)
                if context_fingerprint is None:
                    context_fingerprint = claim_context_fingerprint
                elif claim_context_fingerprint != context_fingerprint:
                    raise ValidationError("all evidence claims must share the graph context")
                previous = staged_by_id.get(evidence_id)
                previous_fingerprint = staged_fingerprints.get(evidence_id)
                if previous is None:
                    previous = self._claims.get(evidence_id)
                    if previous is not None:
                        self._assert_stored_claim(evidence_id, previous)
                        previous_fingerprint = self._claim_fingerprints[evidence_id]
                if previous is not None:
                    if previous_fingerprint == fingerprint:
                        raise ValidationError(f"duplicate evidence ID: {evidence_id}")
                    raise ValidationError(
                        f"evidence ID collision has different content: {evidence_id}"
                    )
                if evidence_id in external_dependencies:
                    raise ValidationError(
                        f"evidence ID collides with an earlier external dependency: {evidence_id}"
                    )

                for dependency in claim.depends_on:
                    dependency_claim = staged_by_id.get(dependency)
                    if dependency_claim is None:
                        dependency_claim = self._claims.get(dependency)
                        if dependency_claim is not None:
                            self._assert_stored_claim(dependency, dependency_claim)
                    if dependency_claim is None:
                        _canonical_content_address(
                            dependency,
                            f"evidence claim {evidence_id} dependency",
                        )
                        external_dependencies.add(dependency)

                if claim.supersedes is not None:
                    superseded = staged_by_id.get(claim.supersedes)
                    if superseded is None:
                        superseded = self._claims.get(claim.supersedes)
                        if superseded is not None:
                            self._assert_stored_claim(claim.supersedes, superseded)
                    if superseded is None:
                        raise ValidationError(
                            f"superseded evidence is not present: {claim.supersedes}"
                        )
                    if superseded.edge_id != claim.edge_id:
                        raise ValidationError(
                            f"evidence claim {evidence_id} cannot supersede evidence on "
                            f"another edge: {claim.supersedes}"
                        )

                edge_count = (
                    edge_counts.get(
                        claim.edge_id,
                        len(self._edge_claims.get(claim.edge_id, ())),
                    )
                    + 1
                )
                if edge_count > self.limits.max_claims_per_edge:
                    raise ValidationError(
                        f"edge {claim.edge_id} exceeds the configured maximum of "
                        f"{self.limits.max_claims_per_edge} claims"
                    )
                edge_counts[claim.edge_id] = edge_count
                claim_size = len(canonical)
                if claim_size > self.limits.max_graph_bytes - projected_bytes:
                    raise ValidationError(
                        "evidence graph exceeds the configured maximum canonical size of "
                        f"{self.limits.max_graph_bytes} bytes"
                    )
                projected_bytes += claim_size
                staged.append((claim, fingerprint, claim_size))
                staged_by_id[evidence_id] = claim
                staged_fingerprints[evidence_id] = fingerprint

            # A producer can mutate a previously yielded object before exhaustion.
            # Revalidate every staged identity immediately before the atomic commit.
            for claim, fingerprint, claim_size in staged:
                canonical, current_fingerprint = self._validate_claim(claim)
                if current_fingerprint != fingerprint or len(canonical) != claim_size:
                    raise ValidationError(
                        f"evidence claim mutated during extension: {claim.evidence_id}"
                    )

            for claim, fingerprint, claim_size in staged:
                self._claims[claim.evidence_id] = claim
                self._edge_claims[claim.edge_id].append(claim.evidence_id)
                self._claim_fingerprints[claim.evidence_id] = fingerprint
                self._claim_sizes[claim.evidence_id] = claim_size
            self._external_dependencies = external_dependencies
            self._context_fingerprint = context_fingerprint
            self._graph_bytes = projected_bytes

    def get(self, evidence_id: str) -> EvidenceClaim:
        evidence_id = _required_string(evidence_id, "evidence_id")
        with self._lock:
            claim = self._claims[evidence_id]
            self._assert_stored_claim(evidence_id, claim)
            return claim

    def for_edge(self, edge_id: str) -> tuple[EvidenceClaim, ...]:
        edge_id = _required_string(edge_id, "edge_id")
        with self._lock:
            claim_ids = self._edge_claims.get(edge_id, ())
            if len(claim_ids) != len(set(claim_ids)):
                raise ValidationError(f"edge {edge_id} contains duplicate claim indexes")
            claims: list[EvidenceClaim] = []
            for evidence_id in sorted(claim_ids):
                claim = self._claims.get(evidence_id)
                if claim is None:
                    raise ValidationError(
                        f"edge {edge_id} indexes unknown evidence claim {evidence_id}"
                    )
                self._assert_stored_claim(evidence_id, claim)
                if claim.edge_id != edge_id:
                    raise ValidationError(
                        f"evidence claim {evidence_id} is bound to {claim.edge_id}, not {edge_id}"
                    )
                claims.append(claim)
            return tuple(claims)

    def all_claims(self) -> tuple[EvidenceClaim, ...]:
        with self._lock:
            self._validate_graph_integrity()
            return tuple(self._claims[evidence_id] for evidence_id in self._canonical_claim_ids())

    def aggregate(self, edge: HypothesisEdge) -> AggregateSupport:
        """Aggregate active same-edge claims after closing declared references.

        ``edge.claim_ids`` is a closure floor: unresolved declarations are reported
        as missing, while every resolved declaration must belong to the edge. All
        registered claims on that edge are then included so callers can stage
        additional same-edge observations before aggregation.
        """

        with self._lock:
            self._validate_edge(edge)
            indexed_ids = self._edge_claims.get(edge.edge_id, ())
            indexed_id_set = set(indexed_ids)
            if len(indexed_ids) != len(indexed_id_set):
                raise ValidationError(f"edge {edge.edge_id} contains duplicate claim indexes")
            unresolved_declared_ids: list[str] = []
            for evidence_id in edge.claim_ids:
                claim = self._claims.get(evidence_id)
                if claim is None:
                    unresolved_declared_ids.append(evidence_id)
                    continue
                self._assert_stored_claim(evidence_id, claim)
                if claim.edge_id != edge.edge_id or evidence_id not in indexed_id_set:
                    raise ValidationError(
                        f"evidence claim {evidence_id} is bound to {claim.edge_id}, "
                        f"not {edge.edge_id}"
                    )

            binding = (edge.edge_type, edge.source_id, edge.target_id)
            previous_binding = self._edge_bindings.get(edge.edge_id)
            if previous_binding is not None and previous_binding != binding:
                raise ValidationError(
                    f"edge ID collision has a conflicting typed identity: {edge.edge_id}"
                )

            registered: list[EvidenceClaim] = []
            for evidence_id in sorted(indexed_ids):
                claim = self._claims.get(evidence_id)
                if claim is None:
                    raise ValidationError(
                        f"edge {edge.edge_id} indexes unknown evidence claim {evidence_id}"
                    )
                self._assert_stored_claim(evidence_id, claim)
                if claim.edge_id != edge.edge_id:
                    raise ValidationError(
                        f"evidence claim {evidence_id} is bound to {claim.edge_id}, "
                        f"not {edge.edge_id}"
                    )
                registered.append(claim)

            superseded_ids = {
                claim.supersedes for claim in registered if claim.supersedes is not None
            }
            claims = tuple(claim for claim in registered if claim.evidence_id not in superseded_ids)

            supported = tuple(claim for claim in claims if claim.state is EvidenceState.SUPPORTED)
            negative = tuple(
                claim
                for claim in claims
                if claim.state in (EvidenceState.MEASURED_NEGATIVE, EvidenceState.CONTRADICTORY)
            )
            missing = tuple(
                claim
                for claim in claims
                if claim.state
                in (
                    EvidenceState.ABSENT,
                    EvidenceState.UNSUPPORTED,
                    EvidenceState.OUT_OF_DOMAIN,
                    EvidenceState.ABSTAINED,
                )
            )
            missing_ids = tuple(
                sorted((*unresolved_declared_ids, *(claim.evidence_id for claim in missing)))
            )

            groups: set[str] = set()
            informative_groups: set[str] = set()
            supported_by_group: dict[str, float] = {}
            negative_by_group: dict[str, float] = {}
            context_support_by_group: dict[str, EvidenceClaim] = {}
            for claim in claims:
                group = self._channel_group(claim.channel)
                groups.add(group)
                if claim.state is EvidenceState.SUPPORTED:
                    informative_groups.add(group)
                    value = self._claim_value(claim)
                    supported_by_group[group] = max(
                        value,
                        supported_by_group.get(group, 0.0),
                    )
                elif claim.state in (
                    EvidenceState.MEASURED_NEGATIVE,
                    EvidenceState.CONTRADICTORY,
                ):
                    informative_groups.add(group)
                    value = self._claim_value(claim)
                    negative_by_group[group] = max(
                        value,
                        negative_by_group.get(group, 0.0),
                    )
                if claim.state in (
                    EvidenceState.SUPPORTED,
                    EvidenceState.MEASURED_NEGATIVE,
                    EvidenceState.CONTRADICTORY,
                ):
                    previous_context_claim = context_support_by_group.get(group)
                    if (
                        previous_context_claim is None
                        or claim.confidence > previous_context_claim.confidence
                        or (
                            claim.confidence == previous_context_claim.confidence
                            and claim.evidence_id < previous_context_claim.evidence_id
                        )
                    ):
                        context_support_by_group[group] = claim

            positive = self._dependence_adjusted_mean(tuple(supported_by_group.values()))
            negative_total = _safe_fsum(
                sorted(negative_by_group.values()),
                "negative evidence penalty",
            )
            negative_penalty = min(0.45, negative_total * 0.22)
            score = round(max(0.0, min(1.0, positive - negative_penalty)), 6)
            context_support_claims = tuple(
                context_support_by_group[group] for group in sorted(context_support_by_group)
            )
            context_total = _safe_fsum(
                sorted(claim.confidence for claim in context_support_claims),
                "context support",
            )
            context_support = (
                0.0
                if not context_support_claims
                else round(context_total / len(context_support_claims), 6)
            )
            uncertainty = round(
                max(
                    0.0,
                    min(
                        1.0,
                        1.0
                        - (0.65 * context_support)
                        - (0.25 * min(1.0, len(informative_groups) / 3.0))
                        + (0.15 if missing_ids else 0.0),
                    ),
                ),
                6,
            )
            superseded_count = len(registered) - len(claims)
            rationale = (
                f"{len(supported)} supported, {len(negative)} negative, "
                f"{len(missing_ids)} missing/unsupported; "
                f"{len(informative_groups)} informative channel groups with "
                f"dependence-adjusted scoring and at most one highest-confidence context claim "
                f"per group; {superseded_count} superseded claim(s) excluded."
            )
            result = AggregateSupport(
                score=score,
                uncertainty=uncertainty,
                context_support=context_support,
                supported_claim_ids=tuple(sorted(claim.evidence_id for claim in supported)),
                negative_claim_ids=tuple(sorted(claim.evidence_id for claim in negative)),
                missing_claim_ids=missing_ids,
                channel_groups=tuple(sorted(groups)),
                rationale=rationale,
                context_support_claim_ids=tuple(
                    sorted(claim.evidence_id for claim in context_support_claims)
                ),
            )
            self._edge_bindings.setdefault(edge.edge_id, binding)
            return result

    def _validate_claim(self, claim: object) -> tuple[bytes, bytes]:
        if type(claim) is not EvidenceClaim:
            raise ValidationError("claims must contain only EvidenceClaim objects")
        for field_name in (
            "evidence_id",
            "edge_id",
            "source_id",
            "channel",
            "summary",
            "produced_by",
            "created_at",
        ):
            _required_string(getattr(claim, field_name), f"evidence {field_name}")
        if type(claim.state) is not EvidenceState:
            raise ValidationError("evidence state must be an EvidenceState")
        if type(claim.tier) is not EvidenceTier:
            raise ValidationError("evidence tier must be an EvidenceTier")
        if claim.score is not None:
            _unit_interval(claim.score, "evidence score")
        _unit_interval(claim.confidence, "evidence confidence")
        if type(claim.context) is not ReferenceContext:
            raise ValidationError("evidence context must be a ReferenceContext")
        try:
            context_raw = claim.context.to_dict()
            if canonical_bytes(context_raw) != canonical_bytes(
                ReferenceContext.from_dict(context_raw, persisted=True).to_dict()
            ):
                raise ValidationError("evidence context is not canonical")
        except (OverflowError, RecursionError, TypeError, UnicodeError, ValueError) as exc:
            raise ValidationError(f"invalid evidence context: {exc}") from exc
        if type(claim.depends_on) is not tuple:
            raise ValidationError("evidence depends_on must be a tuple")
        if len(claim.depends_on) > self.limits.max_dependencies_per_claim:
            raise ValidationError(
                f"evidence claim {claim.evidence_id} dependencies exceeds the configured "
                f"maximum of {self.limits.max_dependencies_per_claim} items"
            )
        for index, dependency in enumerate(claim.depends_on):
            _required_string(dependency, f"evidence depends_on[{index}]")
        if len(claim.depends_on) != len(set(claim.depends_on)):
            raise ValidationError("evidence depends_on must contain unique values")
        if claim.evidence_id in claim.depends_on:
            raise ValidationError("an evidence claim cannot depend on itself")
        if claim.supersedes is not None:
            _required_string(claim.supersedes, "evidence supersedes")
            if claim.supersedes == claim.evidence_id:
                raise ValidationError("an evidence claim cannot supersede itself")
        if not isinstance(claim.payload, Mapping):
            raise ValidationError("evidence payload must be an object")
        try:
            freeze_json(claim.payload, field="evidence payload")
            raw = claim.to_dict()
            rehydrated = EvidenceClaim.from_dict(raw)
            canonical = canonical_bytes(raw)
            if canonical != canonical_bytes(rehydrated.to_dict()):
                raise ValidationError("evidence claim is not canonical")
        except (OverflowError, RecursionError, TypeError, UnicodeError, ValueError) as exc:
            raise ValidationError(f"invalid evidence claim: {exc}") from exc
        if len(canonical) > self.limits.max_claim_bytes:
            raise ValidationError(
                f"evidence claim {claim.evidence_id} exceeds the configured maximum "
                f"canonical size of {self.limits.max_claim_bytes} bytes"
            )
        return canonical, hashlib.sha256(canonical).digest()

    @staticmethod
    def _claim_context_fingerprint(claim: EvidenceClaim) -> bytes:
        # ``source_version`` and ``assay_support`` describe evidence provenance,
        # not the case domain. ReferenceContext.key contains the six dimensions
        # that define whether claims belong to the same case graph.
        return hashlib.sha256(canonical_bytes(claim.context.key)).digest()

    def _validate_edge(self, edge: object) -> None:
        if type(edge) is not HypothesisEdge:
            raise ValidationError("edge must be a HypothesisEdge")
        for field_name in ("edge_id", "source_id", "target_id"):
            _required_string(getattr(edge, field_name), f"edge {field_name}")
        if type(edge.edge_type) is not EdgeType:
            raise ValidationError("edge edge_type must be an EdgeType")
        if type(edge.support_level) is not SupportLevel:
            raise ValidationError("edge support_level must be a SupportLevel")
        for field_name in ("support", "uncertainty", "context_fit"):
            _unit_interval(getattr(edge, field_name), f"edge {field_name}")
        if type(edge.claim_ids) is not tuple:
            raise ValidationError("edge claim_ids must be a tuple")
        if not edge.claim_ids:
            raise ValidationError("edge claim_ids must not be empty")
        if len(edge.claim_ids) > self.limits.max_claims_per_edge:
            raise ValidationError(
                f"edge {edge.edge_id} claim_ids exceeds the configured maximum of "
                f"{self.limits.max_claims_per_edge} items"
            )
        for index, evidence_id in enumerate(edge.claim_ids):
            _required_string(evidence_id, f"edge claim_ids[{index}]")
        if len(edge.claim_ids) != len(set(edge.claim_ids)):
            raise ValidationError("edge claim_ids must contain unique values")
        if type(edge.alternatives) is not tuple:
            raise ValidationError("edge alternatives must be a tuple")
        for index, alternative in enumerate(edge.alternatives):
            _required_string(alternative, f"edge alternatives[{index}]")
        if len(edge.alternatives) != len(set(edge.alternatives)):
            raise ValidationError("edge alternatives must contain unique values")
        try:
            edge_size = len(canonical_bytes(edge.to_dict()))
        except (OverflowError, RecursionError, TypeError, UnicodeError, ValueError) as exc:
            raise ValidationError(f"invalid hypothesis edge: {exc}") from exc
        if edge_size > self.limits.max_claim_bytes:
            raise ValidationError(
                f"edge {edge.edge_id} exceeds the configured maximum canonical size of "
                f"{self.limits.max_claim_bytes} bytes"
            )

    def _assert_stored_claim(self, evidence_id: str, claim: EvidenceClaim) -> None:
        if claim.evidence_id != evidence_id:
            raise ValidationError(f"stored evidence claim identity was mutated: {evidence_id}")
        canonical, fingerprint = self._validate_claim(claim)
        if self._claim_fingerprints.get(evidence_id) != fingerprint or self._claim_sizes.get(
            evidence_id
        ) != len(canonical):
            raise ValidationError(f"stored evidence claim was mutated: {evidence_id}")

    def _validate_graph_integrity(self) -> None:
        claim_ids = tuple(self._claims)
        if len(claim_ids) > self.limits.max_claims:
            raise ValidationError("evidence graph exceeds its configured claim limit")
        if set(claim_ids) != set(self._claim_fingerprints) or set(claim_ids) != set(
            self._claim_sizes
        ):
            raise ValidationError("evidence graph claim indexes are inconsistent")

        indexed_ids = tuple(
            evidence_id
            for edge_claim_ids in self._edge_claims.values()
            for evidence_id in edge_claim_ids
        )
        if len(indexed_ids) != len(set(indexed_ids)) or set(indexed_ids) != set(claim_ids):
            raise ValidationError("evidence graph edge indexes are inconsistent")

        positions = {evidence_id: index for index, evidence_id in enumerate(claim_ids)}
        external_dependencies: set[str] = set()
        context_fingerprints: set[bytes] = set()
        total_bytes = 0
        for evidence_id, claim in self._claims.items():
            self._assert_stored_claim(evidence_id, claim)
            context_fingerprints.add(self._claim_context_fingerprint(claim))
            total_bytes += self._claim_sizes[evidence_id]
            if evidence_id not in self._edge_claims.get(claim.edge_id, ()):
                raise ValidationError(
                    f"evidence claim {evidence_id} is absent from edge {claim.edge_id}"
                )
            for dependency in claim.depends_on:
                dependency_position = positions.get(dependency)
                if dependency_position is None:
                    _canonical_content_address(
                        dependency,
                        f"evidence claim {evidence_id} dependency",
                    )
                    external_dependencies.add(dependency)
                elif dependency_position >= positions[evidence_id]:
                    raise ValidationError(
                        f"evidence claim {evidence_id} has a forward or cyclic dependency"
                    )
            if claim.supersedes is not None:
                superseded_position = positions.get(claim.supersedes)
                if superseded_position is None or superseded_position >= positions[evidence_id]:
                    raise ValidationError(
                        f"evidence claim {evidence_id} must supersede earlier evidence"
                    )
                if self._claims[claim.supersedes].edge_id != claim.edge_id:
                    raise ValidationError(
                        f"evidence claim {evidence_id} supersedes evidence on another edge"
                    )
        if external_dependencies != self._external_dependencies:
            raise ValidationError("evidence graph external dependency index is inconsistent")
        expected_context = next(iter(context_fingerprints), None)
        if len(context_fingerprints) > 1 or expected_context != self._context_fingerprint:
            raise ValidationError("evidence graph context index is inconsistent")
        if total_bytes != self._graph_bytes or total_bytes > self.limits.max_graph_bytes:
            raise ValidationError("evidence graph byte accounting is inconsistent")

    def _canonical_claim_ids(self) -> tuple[str, ...]:
        successors: dict[str, set[str]] = defaultdict(set)
        indegree = {evidence_id: 0 for evidence_id in self._claims}
        for evidence_id, claim in self._claims.items():
            predecessors = {
                dependency for dependency in claim.depends_on if dependency in self._claims
            }
            if claim.supersedes is not None:
                predecessors.add(claim.supersedes)
            for predecessor in predecessors:
                if evidence_id not in successors[predecessor]:
                    successors[predecessor].add(evidence_id)
                    indegree[evidence_id] += 1

        ready = [evidence_id for evidence_id, degree in indegree.items() if degree == 0]
        heapq.heapify(ready)
        ordered: list[str] = []
        while ready:
            evidence_id = heapq.heappop(ready)
            ordered.append(evidence_id)
            for successor in sorted(successors.get(evidence_id, ())):
                indegree[successor] -= 1
                if indegree[successor] == 0:
                    heapq.heappush(ready, successor)
        if len(ordered) != len(self._claims):
            raise ValidationError("evidence graph contains a dependency cycle")
        return tuple(ordered)

    @staticmethod
    def _channel_group(channel: str) -> str:
        channel = _required_string(channel, "evidence channel")
        mapping = {
            "regulatory_overlap": "regulatory_atlas",
            "motif_delta": "sequence",
            "sequence_model": "sequence",
            "conservation": "sequence",
            "accessibility": "chromatin",
            "histone_activity": "chromatin",
            "methylation": "chromatin",
            "contact": "topology",
            "boundary": "topology",
            "qtl": "linking",
            "coaccessibility": "linking",
            "perturbation": "functional",
            "cohort": "cohort",
            "matched_rna_consequence": "expression",
        }
        return mapping.get(channel, channel)

    def _group_channels(self, claims: Iterable[EvidenceClaim]) -> list[str]:
        if isinstance(claims, (str, bytes, bytearray, Mapping)):
            raise ValidationError("claims must be an iterable of EvidenceClaim objects")
        try:
            iterator = iter(claims)
        except TypeError as exc:
            raise ValidationError("claims must be iterable") from exc
        groups: set[str] = set()
        for index, claim in enumerate(iterator):
            if index >= self.limits.max_claims:
                raise ValidationError(
                    "channel grouping exceeds the configured maximum of "
                    f"{self.limits.max_claims} claims"
                )
            if type(claim) is not EvidenceClaim:
                raise ValidationError("claims must contain only EvidenceClaim objects")
            groups.add(self._channel_group(claim.channel))
        return sorted(groups)

    @staticmethod
    def _claim_value(claim: EvidenceClaim) -> float:
        if type(claim) is not EvidenceClaim:
            raise ValidationError("claim must be an EvidenceClaim")
        if type(claim.tier) is not EvidenceTier:
            raise ValidationError("evidence tier must be an EvidenceTier")
        score = 0.0 if claim.score is None else _unit_interval(claim.score, "evidence score")
        confidence = _unit_interval(claim.confidence, "evidence confidence")
        tier_weight = {
            EvidenceTier.REFERENCE: 0.72,
            EvidenceTier.COMPUTED: 0.74,
            EvidenceTier.EXPERIMENTAL: 0.95,
            EvidenceTier.COHORT: 0.82,
            EvidenceTier.REVIEWED: 1.00,
        }[claim.tier]
        result = score * confidence * tier_weight
        if not math.isfinite(result):  # pragma: no cover - guarded unit intervals
            raise ValidationError("evidence claim value must remain finite")
        return result

    @staticmethod
    def _dependence_adjusted_mean(values: Sequence[float]) -> float:
        if not isinstance(values, (list, tuple)):
            raise ValidationError("aggregate values must be a list or tuple")
        if len(values) > MAX_EVIDENCE_CLAIMS:
            raise ValidationError(
                f"aggregate values exceeds the safety ceiling of {MAX_EVIDENCE_CLAIMS} items"
            )
        normalized = [
            _unit_interval(value, f"aggregate values[{index}]")
            for index, value in enumerate(values)
        ]
        if not normalized:
            return 0.0
        ordered = sorted(normalized, reverse=True)
        weights = tuple(1.0 / (index + 1) for index in range(len(ordered)))
        denominator = _safe_fsum(weights, "dependence-adjusted denominator")
        numerator = _safe_fsum(
            (value * weight for value, weight in zip(ordered, weights, strict=True)),
            "dependence-adjusted numerator",
        )
        result = numerator / denominator
        if not math.isfinite(result):  # pragma: no cover - guarded arithmetic
            raise ValidationError("dependence-adjusted mean must remain finite")
        return result
