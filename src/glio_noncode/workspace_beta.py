"""Scientific-beta research-workbench projections.

The first workspace layer provides case, cohort, variant, and interval search.
This module adds four deeper projections for the research workbench:

* a two-anchor topology viewport for loops, promoter capture, and bounded
  activity-by-contact summaries;
* a causal-chain explorer that keeps missing mediators, alternative paths,
  contradictory evidence, and exact context visible;
* a posterior decomposition viewer that exposes declared-prior support and
  residuals without presenting a research proxy as a clinical probability;
* an evidence table with typed filters, deterministic facets, and pagination.

Every projection is immutable and content-addressed. These are renderable
research artifacts, not diagnostic, treatment, or clinical decision outputs.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite
from typing import Any

from .causal_beta import CausalBetaState, CausalMediatorResult, MediatorKind
from .errors import ValidationError
from .identity import normalize_chromosome
from .inference_extensions import DriverPosteriorResult, InferenceState
from .serialization import content_hash, jsonable, require_non_empty
from .topology_beta import (
    ActivityByContactResult,
    EnhancerPromoterContactScore,
    LoopStripeObservation,
    PromoterCaptureContact,
    TopologyBetaKind,
)
from .topology_context import TopologyState
from .workspace import (
    ResearchWorkspace,
    WorkspaceQuery,
    WorkspaceRecord,
    WorkspaceRecordType,
    WorkspaceState,
)


class TopologyNodeKind(StrEnum):
    """Node roles that can be rendered in a topology viewport."""

    LOCUS = "locus"
    PROMOTER = "promoter"
    ELEMENT = "element"


class TopologyEdgeKind(StrEnum):
    """Observed or derived topology edge roles."""

    LOOP = "loop"
    STRIPE = "stripe"
    PROMOTER_CAPTURE = "promoter_capture"
    CONTACT_SCORE = "contact_score"
    ACTIVITY_BY_CONTACT = "activity_by_contact"


@dataclass(frozen=True, slots=True)
class TopologyViewportNode:
    """A context-qualified topology node with optional genomic coordinates."""

    node_id: str
    label: str
    kind: TopologyNodeKind
    context_key: str
    state: WorkspaceState
    source_ids: tuple[str, ...] = ()
    chromosome: str | None = None
    start: int | None = None
    end: int | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("node_id", "label", "context_key"):
            require_non_empty(getattr(self, name), name)
        if (self.start is None) != (self.end is None):
            raise ValidationError("topology node coordinates require start and end together")
        if self.start is not None and (self.start < 1 or self.end is None or self.end < self.start):
            raise ValidationError("topology node coordinates are invalid")
        if self.chromosome is None and self.start is not None:
            raise ValidationError("topology node interval requires chromosome")
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValidationError("topology node source IDs must be unique")

    @property
    def coordinate_label(self) -> str | None:
        if self.chromosome is None or self.start is None or self.end is None:
            return None
        return f"{self.chromosome}:{self.start}-{self.end}"

    def to_dict(self) -> dict[str, Any]:
        payload = jsonable(self)
        payload["coordinate_label"] = self.coordinate_label
        return payload


@dataclass(frozen=True, slots=True)
class TopologyViewportEdge:
    """One edge in the viewport, retaining source and model receipts."""

    edge_id: str
    label: str
    kind: TopologyEdgeKind
    source_node_id: str
    target_node_id: str
    context_key: str
    state: WorkspaceState
    score: float | None = None
    source_ids: tuple[str, ...] = ()
    source_versions: tuple[str, ...] = ()
    observation_ids: tuple[str, ...] = ()
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "edge_id",
            "label",
            "source_node_id",
            "target_node_id",
            "context_key",
        ):
            require_non_empty(getattr(self, name), name)
        if self.source_node_id == self.target_node_id:
            raise ValidationError("topology edge cannot connect a node to itself")
        if self.score is not None and (not isfinite(self.score) or self.score < 0):
            raise ValidationError("topology edge score must be finite and non-negative")
        for name in ("source_ids", "source_versions", "observation_ids"):
            values = getattr(self, name)
            if len(values) != len(set(values)):
                raise ValidationError(f"topology edge {name} must be unique")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyViewport:
    """Deterministic 3D-topology read model for one exact context."""

    viewport_id: str
    context_key: str
    nodes: tuple[TopologyViewportNode, ...]
    edges: tuple[TopologyViewportEdge, ...]
    state: WorkspaceState
    focus: Mapping[str, Any]
    warnings: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.viewport_id, "viewport_id")
        require_non_empty(self.context_key, "context_key")
        node_ids = tuple(node.node_id for node in self.nodes)
        edge_ids = tuple(edge.edge_id for edge in self.edges)
        if len(node_ids) != len(set(node_ids)):
            raise ValidationError("topology viewport node IDs must be unique")
        if len(edge_ids) != len(set(edge_ids)):
            raise ValidationError("topology viewport edge IDs must be unique")
        if any(
            edge.source_node_id not in node_ids or edge.target_node_id not in node_ids
            for edge in self.edges
        ):
            raise ValidationError("topology viewport edge references an absent node")

    @property
    def observed_edge_count(self) -> int:
        return sum(
            edge.kind
            in {
                TopologyEdgeKind.LOOP,
                TopologyEdgeKind.STRIPE,
                TopologyEdgeKind.PROMOTER_CAPTURE,
            }
            for edge in self.edges
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class TopologyViewer:
    """Build a bounded, exact-context two-anchor topology viewport."""

    def build(
        self,
        *,
        context_key: str,
        loops: Iterable[LoopStripeObservation] | Any = (),
        contacts: Iterable[PromoterCaptureContact] | Any = (),
        contact_scores: Iterable[EnhancerPromoterContactScore | Mapping[str, Any]] = (),
        activity_results: Iterable[ActivityByContactResult | Mapping[str, Any]] = (),
        focus_chromosome: str | None = None,
        focus_start: int | None = None,
        focus_end: int | None = None,
        max_nodes: int = 500,
        max_edges: int = 1000,
    ) -> TopologyViewport:
        require_non_empty(context_key, "context_key")
        if max_nodes < 1 or max_nodes > 10_000:
            raise ValidationError("topology max_nodes is outside the bounded range")
        if max_edges < 1 or max_edges > 20_000:
            raise ValidationError("topology max_edges is outside the bounded range")
        if (focus_start is None) != (focus_end is None):
            raise ValidationError("topology focus coordinates require start and end together")
        if focus_start is not None and (
            focus_start < 1 or focus_end is None or focus_end < focus_start
        ):
            raise ValidationError("topology focus interval is invalid")
        if focus_start is not None and not focus_chromosome:
            raise ValidationError("topology focus interval requires focus chromosome")

        loop_values, loop_issues = _observation_values(loops, "observations")
        contact_values, contact_issues = _observation_values(contacts, "contacts")
        score_values = tuple(_coerce_contact_score(value) for value in contact_scores)
        activity_values = tuple(_coerce_activity(value) for value in activity_results)
        nodes: dict[str, TopologyViewportNode] = {}
        edges: list[TopologyViewportEdge] = []
        warnings: list[str] = []
        exact_count = 0
        other_context_count = 0
        usable_count = 0

        for issue in (*loop_issues, *contact_issues):
            warnings.append(f"topology input issue retained: {issue}")

        for observation in loop_values:
            if observation.context_key != context_key:
                other_context_count += 1
                continue
            exact_count += 1
            if not _has_focus(
                (
                    (observation.chromosome_a, observation.start_a, observation.end_a),
                    (observation.chromosome_b, observation.start_b, observation.end_b),
                ),
                focus_chromosome,
                focus_start,
                focus_end,
            ):
                continue
            usable_count += 1
            first_id = _locus_id(observation.chromosome_a, observation.start_a, observation.end_a)
            second_id = _locus_id(observation.chromosome_b, observation.start_b, observation.end_b)
            self._add_locus_node(
                nodes,
                first_id,
                observation.chromosome_a,
                observation.start_a,
                observation.end_a,
                context_key,
                observation.source_id,
                observation.feature_id,
            )
            self._add_locus_node(
                nodes,
                second_id,
                observation.chromosome_b,
                observation.start_b,
                observation.end_b,
                context_key,
                observation.source_id,
                observation.feature_id,
            )
            edge_kind = (
                TopologyEdgeKind.STRIPE
                if observation.feature_kind.value == "stripe"
                else TopologyEdgeKind.LOOP
            )
            edges.append(
                TopologyViewportEdge(
                    edge_id=f"{edge_kind.value}:{observation.feature_id}",
                    label=observation.feature_id,
                    kind=edge_kind,
                    source_node_id=first_id,
                    target_node_id=second_id,
                    context_key=context_key,
                    state=WorkspaceState.SUPPORTED,
                    score=observation.signal,
                    source_ids=(observation.source_id,),
                    source_versions=(observation.source_version,),
                    observation_ids=(observation.feature_id,),
                    attributes={
                        "resolution": observation.resolution,
                        "replicate_id": observation.replicate_id,
                        "caller": observation.caller,
                        "raw_hash": observation.raw_hash,
                        "attributes": observation.attributes,
                    },
                )
            )

        for contact in contact_values:
            if contact.context_key != context_key:
                other_context_count += 1
                continue
            exact_count += 1
            if not _has_focus(
                (
                    (contact.promoter_chromosome, contact.promoter_start, contact.promoter_end),
                    (contact.target_chromosome, contact.target_start, contact.target_end),
                ),
                focus_chromosome,
                focus_start,
                focus_end,
            ):
                continue
            usable_count += 1
            promoter_id = f"promoter:{contact.promoter_id}"
            element_id = f"element:{contact.target_element_id}"
            self._add_named_node(
                nodes,
                promoter_id,
                contact.promoter_id,
                TopologyNodeKind.PROMOTER,
                context_key,
                contact.source_id,
                chromosome=contact.promoter_chromosome,
                start=contact.promoter_start,
                end=contact.promoter_end,
                attributes={"bait_id": contact.bait_id, "contact_id": contact.contact_id},
            )
            self._add_named_node(
                nodes,
                element_id,
                contact.target_element_id,
                TopologyNodeKind.ELEMENT,
                context_key,
                contact.source_id,
                chromosome=contact.target_chromosome,
                start=contact.target_start,
                end=contact.target_end,
                attributes={"contact_id": contact.contact_id},
            )
            edges.append(
                TopologyViewportEdge(
                    edge_id=f"{TopologyEdgeKind.PROMOTER_CAPTURE.value}:{contact.contact_id}",
                    label=contact.contact_id,
                    kind=TopologyEdgeKind.PROMOTER_CAPTURE,
                    source_node_id=element_id,
                    target_node_id=promoter_id,
                    context_key=context_key,
                    state=WorkspaceState.SUPPORTED,
                    score=contact.signal,
                    source_ids=(contact.source_id,),
                    source_versions=(contact.source_version,),
                    observation_ids=(contact.contact_id,),
                    attributes={
                        "resolution": contact.resolution,
                        "replicate_id": contact.replicate_id,
                        "raw_hash": contact.raw_hash,
                        "attributes": contact.attributes,
                    },
                )
            )

        for score in score_values:
            if score.context_key != context_key:
                other_context_count += 1
                continue
            exact_count += 1
            edge = self._score_edge(score, context_key, activity=False)
            self._ensure_symbolic_nodes(
                nodes, edge, score.enhancer_id, score.promoter_id, context_key
            )
            edges.append(edge)
            usable_count += 1

        for result in activity_values:
            if result.context_key != context_key:
                other_context_count += 1
                continue
            exact_count += 1
            edge = self._activity_edge(result, context_key)
            self._ensure_symbolic_nodes(
                nodes, edge, result.enhancer_id, result.promoter_id, context_key
            )
            edges.append(edge)
            usable_count += 1

        if other_context_count:
            warnings.append(
                f"{other_context_count} topology observation(s) were withheld because their "
                "context did not match the requested context."
            )
        if focus_start is not None:
            warnings.append(
                "viewport is interval-focused; omitted edges remain outside the declared focus"
            )
        if not exact_count:
            state = WorkspaceState.OUT_OF_DOMAIN if other_context_count else WorkspaceState.ABSENT
        elif not usable_count:
            state = WorkspaceState.ABSENT
        elif loop_issues or contact_issues or other_context_count:
            state = WorkspaceState.PARTIAL
        else:
            state = WorkspaceState.SUPPORTED

        nodes, edges, truncated = _bound_topology(nodes, edges, max_nodes, max_edges)
        if truncated:
            warnings.append(
                "topology viewport was bounded; omitted records remain available in "
                "source snapshots"
            )
            state = WorkspaceState.PARTIAL if state == WorkspaceState.SUPPORTED else state
        if not nodes and edges:
            raise ValidationError("topology viewport cannot contain edges without nodes")
        warning_tuple = tuple(dict.fromkeys(warnings))
        focus = {
            "chromosome": focus_chromosome,
            "start": focus_start,
            "end": focus_end,
            "is_interval_focused": focus_start is not None,
        }
        body = {
            "viewport_id": f"topology:{context_key}:{content_hash((nodes, edges, focus))}",
            "context_key": context_key,
            "nodes": nodes,
            "edges": edges,
            "state": state,
            "focus": focus,
            "warnings": warning_tuple,
        }
        return TopologyViewport(
            viewport_id=body["viewport_id"],
            context_key=context_key,
            nodes=tuple(nodes.values()),
            edges=tuple(edges),
            state=state,
            focus=focus,
            warnings=warning_tuple,
            content_address=content_hash(body),
        )

    @staticmethod
    def _add_locus_node(
        nodes: dict[str, TopologyViewportNode],
        node_id: str,
        chromosome: str,
        start: int,
        end: int,
        context_key: str,
        source_id: str,
        observation_id: str,
    ) -> None:
        TopologyViewer._add_named_node(
            nodes,
            node_id,
            node_id.removeprefix("locus:"),
            TopologyNodeKind.LOCUS,
            context_key,
            source_id,
            chromosome=chromosome,
            start=start,
            end=end,
            attributes={"observation_ids": (observation_id,)},
        )

    @staticmethod
    def _add_named_node(
        nodes: dict[str, TopologyViewportNode],
        node_id: str,
        label: str,
        kind: TopologyNodeKind,
        context_key: str,
        source_id: str,
        *,
        chromosome: str | None = None,
        start: int | None = None,
        end: int | None = None,
        attributes: Mapping[str, Any] | None = None,
    ) -> None:
        current = nodes.get(node_id)
        if current is None:
            nodes[node_id] = TopologyViewportNode(
                node_id=node_id,
                label=label,
                kind=kind,
                context_key=context_key,
                state=WorkspaceState.SUPPORTED,
                source_ids=(source_id,),
                chromosome=chromosome,
                start=start,
                end=end,
                attributes=dict(attributes or {}),
            )
            return
        sources = tuple(sorted(set((*current.source_ids, source_id))))
        prior_observations = tuple(current.attributes.get("observation_ids", ()))
        new_observations = tuple((attributes or {}).get("observation_ids", ()))
        nodes[node_id] = TopologyViewportNode(
            node_id=current.node_id,
            label=current.label,
            kind=current.kind,
            context_key=current.context_key,
            state=current.state,
            source_ids=sources,
            chromosome=current.chromosome or chromosome,
            start=current.start or start,
            end=current.end or end,
            attributes={
                **dict(current.attributes),
                "observation_ids": tuple(sorted(set((*prior_observations, *new_observations)))),
            },
        )

    @staticmethod
    def _ensure_symbolic_nodes(
        nodes: dict[str, TopologyViewportNode],
        edge: TopologyViewportEdge,
        enhancer_id: str,
        promoter_id: str,
        context_key: str,
    ) -> None:
        TopologyViewer._add_named_node(
            nodes,
            edge.source_node_id,
            enhancer_id,
            TopologyNodeKind.ELEMENT,
            context_key,
            edge.source_ids[0] if edge.source_ids else "unspecified",
        )
        TopologyViewer._add_named_node(
            nodes,
            edge.target_node_id,
            promoter_id,
            TopologyNodeKind.PROMOTER,
            context_key,
            edge.source_ids[0] if edge.source_ids else "unspecified",
        )

    @staticmethod
    def _score_edge(
        score: EnhancerPromoterContactScore,
        context_key: str,
        *,
        activity: bool,
    ) -> TopologyViewportEdge:
        state = _topology_state(score.state)
        return TopologyViewportEdge(
            edge_id=f"{TopologyEdgeKind.CONTACT_SCORE.value}:{score.enhancer_id}:{score.promoter_id}",
            label=f"{score.enhancer_id} → {score.promoter_id}",
            kind=TopologyEdgeKind.CONTACT_SCORE,
            source_node_id=f"element:{score.enhancer_id}",
            target_node_id=f"promoter:{score.promoter_id}",
            context_key=context_key,
            state=state,
            score=score.normalized_contact_score,
            source_ids=score.source_ids,
            source_versions=score.source_versions,
            observation_ids=tuple(item.contact_id for item in score.observations),
            attributes={
                "median_signal": score.median_signal,
                "signal_spread": score.signal_spread,
                "reason": score.reason,
                "warnings": score.warnings,
                "activity_edge": activity,
            },
        )

    @staticmethod
    def _activity_edge(
        result: ActivityByContactResult,
        context_key: str,
    ) -> TopologyViewportEdge:
        return TopologyViewportEdge(
            edge_id=f"{TopologyEdgeKind.ACTIVITY_BY_CONTACT.value}:{result.enhancer_id}:{result.promoter_id}",
            label=f"{result.enhancer_id} → {result.promoter_id}",
            kind=TopologyEdgeKind.ACTIVITY_BY_CONTACT,
            source_node_id=f"element:{result.enhancer_id}",
            target_node_id=f"promoter:{result.promoter_id}",
            context_key=context_key,
            state=_topology_state(result.state),
            score=result.activity_by_contact_score,
            source_ids=result.source_ids,
            source_versions=result.source_versions,
            observation_ids=tuple(item.contact_id for item in result.contact_observations)
            + tuple(item.observation_id for item in result.activity_observations),
            attributes={
                "contact_state": result.contact_state,
                "activity_state": result.activity_state,
                "contact_component": result.contact_component,
                "activity_component": result.activity_component,
                "model_id": result.model_id,
                "model_version": result.model_version,
                "reason": result.reason,
                "warnings": result.warnings,
            },
        )


class CausalChainState(StrEnum):
    """Chain-level state distinct from individual mediator states."""

    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    CONTRADICTORY = "contradictory"
    OUT_OF_DOMAIN = "out_of_domain"
    ABSTAINED = "abstained"


@dataclass(frozen=True, slots=True)
class CausalChainNode:
    """A node in a sequence-to-state causal research path."""

    node_id: str
    label: str
    role: str
    context_key: str
    state: WorkspaceState
    source_ids: tuple[str, ...] = ()
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("node_id", "label", "role", "context_key"):
            require_non_empty(getattr(self, name), name)
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValidationError("causal chain node source IDs must be unique")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalChainEdge:
    """One mediator edge in the chain, including negative evidence IDs."""

    edge_id: str
    source_node_id: str
    target_node_id: str
    mediator_kind: MediatorKind
    context_key: str
    state: WorkspaceState
    support: float | None
    uncertainty: float
    evidence_ids: tuple[str, ...]
    negative_evidence_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    source_versions: tuple[str, ...]
    reason: str
    warnings: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "edge_id",
            "source_node_id",
            "target_node_id",
            "context_key",
            "reason",
        ):
            require_non_empty(getattr(self, name), name)
        if self.source_node_id == self.target_node_id:
            raise ValidationError("causal chain edge cannot connect a node to itself")
        if self.support is not None and (not isfinite(self.support) or not 0 <= self.support <= 1):
            raise ValidationError("causal chain support must be between zero and one")
        if not 0 <= self.uncertainty <= 1:
            raise ValidationError("causal chain uncertainty must be between zero and one")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalChainView:
    """Renderable causal-chain projection with explicit completeness."""

    chain_id: str
    context_key: str
    nodes: tuple[CausalChainNode, ...]
    edges: tuple[CausalChainEdge, ...]
    state: CausalChainState
    missing_mediator_kinds: tuple[MediatorKind, ...]
    alternative_edge_ids: tuple[str, ...]
    warnings: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.chain_id, "chain_id")
        require_non_empty(self.context_key, "context_key")
        node_ids = {node.node_id for node in self.nodes}
        if len(node_ids) != len(self.nodes):
            raise ValidationError("causal chain node IDs must be unique")
        edge_ids = {edge.edge_id for edge in self.edges}
        if len(edge_ids) != len(self.edges):
            raise ValidationError("causal chain edge IDs must be unique")
        if any(
            edge.source_node_id not in node_ids or edge.target_node_id not in node_ids
            for edge in self.edges
        ):
            raise ValidationError("causal chain edge references an absent node")

    @property
    def complete(self) -> bool:
        return self.state == CausalChainState.COMPLETE

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class CausalChainExplorer:
    """Join the three declared mediator types into a transparent chain view."""

    REQUIRED = (
        MediatorKind.SEQUENCE_TO_ELEMENT,
        MediatorKind.ELEMENT_TO_GENE,
        MediatorKind.GENE_TO_STATE,
    )

    def explore(
        self,
        results: Iterable[CausalMediatorResult | Mapping[str, Any]] | Mapping[str, Any],
        *,
        context_key: str,
        required_kinds: Sequence[MediatorKind] = REQUIRED,
        chain_id: str | None = None,
    ) -> CausalChainView:
        require_non_empty(context_key, "context_key")
        values = tuple(_coerce_causal_result(value) for value in _result_values(results))
        required = tuple(dict.fromkeys(MediatorKind(str(value)) for value in required_kinds))
        exact = tuple(value for value in values if value.context_key == context_key)
        other_context = tuple(value for value in values if value.context_key != context_key)
        nodes: dict[str, CausalChainNode] = {}
        edges: list[CausalChainEdge] = []
        kind_counts: Counter[MediatorKind] = Counter()
        for index, result in enumerate(exact, start=1):
            kind_counts[result.mediator_kind] += 1
            edge_id = (
                f"{result.mediator_kind.value}:{result.source_node}:{result.target_node}:{index}"
            )
            edge = CausalChainEdge(
                edge_id=edge_id,
                source_node_id=result.source_node,
                target_node_id=result.target_node,
                mediator_kind=result.mediator_kind,
                context_key=context_key,
                state=_causal_state(result.state),
                support=result.support,
                uncertainty=result.uncertainty,
                evidence_ids=result.evidence_ids,
                negative_evidence_ids=result.negative_evidence_ids,
                source_ids=result.source_ids,
                source_versions=result.source_versions,
                reason=result.reason,
                warnings=result.warnings,
            )
            edges.append(edge)
            self._upsert_node(nodes, result.source_node, result.source_node, result, source=True)
            self._upsert_node(nodes, result.target_node, result.target_node, result, source=False)

        missing = tuple(kind for kind in required if kind_counts[kind] == 0)
        alternatives = tuple(edge.edge_id for edge in edges if kind_counts[edge.mediator_kind] > 1)
        warnings: list[str] = [
            "Causal-chain edges are evidence summaries; they do not establish a causal probability "
            "or clinical mechanism.",
            "Missing, negative-control, and against-direction evidence remain visible "
            "in each edge.",
        ]
        if other_context:
            warnings.append(
                f"{len(other_context)} mediator result(s) were withheld because their "
                "context did not match."
            )
        if missing:
            warnings.append("Missing mediator kinds: " + ", ".join(kind.value for kind in missing))
        if alternatives:
            warnings.append(
                "Multiple mediator paths are retained as alternatives; they are not collapsed."
            )
        if not exact:
            state = CausalChainState.OUT_OF_DOMAIN if other_context else CausalChainState.ABSTAINED
        elif any(edge.state == WorkspaceState.AMBIGUOUS for edge in edges):
            state = CausalChainState.CONTRADICTORY
        elif any(edge.state == WorkspaceState.OUT_OF_DOMAIN for edge in edges):
            state = CausalChainState.OUT_OF_DOMAIN
        elif missing or any(edge.state != WorkspaceState.SUPPORTED for edge in edges):
            state = CausalChainState.INCOMPLETE
        else:
            state = CausalChainState.COMPLETE
        warnings_tuple = tuple(dict.fromkeys(warnings))
        final_chain_id = chain_id or f"causal-chain:{context_key}:{content_hash((exact, required))}"
        body = {
            "chain_id": final_chain_id,
            "context_key": context_key,
            "nodes": nodes,
            "edges": edges,
            "state": state,
            "missing_mediator_kinds": missing,
            "alternative_edge_ids": alternatives,
            "warnings": warnings_tuple,
        }
        return CausalChainView(
            chain_id=final_chain_id,
            context_key=context_key,
            nodes=tuple(nodes[key] for key in sorted(nodes)),
            edges=tuple(edges),
            state=state,
            missing_mediator_kinds=missing,
            alternative_edge_ids=alternatives,
            warnings=warnings_tuple,
            content_address=content_hash(body),
        )

    @staticmethod
    def _upsert_node(
        nodes: dict[str, CausalChainNode],
        node_id: str,
        label: str,
        result: CausalMediatorResult,
        *,
        source: bool,
    ) -> None:
        role = _mediator_role(result.mediator_kind, source=source)
        state = _causal_state(result.state)
        current = nodes.get(node_id)
        if current is None:
            nodes[node_id] = CausalChainNode(
                node_id=node_id,
                label=label,
                role=role,
                context_key=result.context_key,
                state=state,
                source_ids=result.source_ids,
                attributes={"mediator_kinds": (result.mediator_kind.value,)},
            )
            return
        nodes[node_id] = CausalChainNode(
            node_id=current.node_id,
            label=current.label,
            role=current.role,
            context_key=current.context_key,
            state=_worse_workspace_state(current.state, state),
            source_ids=tuple(sorted(set((*current.source_ids, *result.source_ids)))),
            attributes={
                **dict(current.attributes),
                "mediator_kinds": tuple(
                    sorted(
                        set(
                            (
                                *current.attributes.get("mediator_kinds", ()),
                                result.mediator_kind.value,
                            )
                        )
                    )
                ),
            },
        )


@dataclass(frozen=True, slots=True)
class PosteriorComponent:
    """One declared support contribution to a research posterior proxy."""

    component_id: str
    label: str
    contribution: float
    context_key: str
    state: WorkspaceState = WorkspaceState.SUPPORTED
    source_ids: tuple[str, ...] = ()
    observation_ids: tuple[str, ...] = ()
    explanation: str = ""

    def __post_init__(self) -> None:
        for name in ("component_id", "label", "context_key"):
            require_non_empty(getattr(self, name), name)
        if not isfinite(self.contribution) or not -1 <= self.contribution <= 1:
            raise ValidationError("posterior contribution must be between -1 and 1")
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValidationError("posterior component source IDs must be unique")
        if len(self.observation_ids) != len(set(self.observation_ids)):
            raise ValidationError("posterior component observation IDs must be unique")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PosteriorDecompositionView:
    """Posterior-proxy decomposition with an explicit unexplained residual."""

    view_id: str
    hypothesis_id: str
    context_key: str
    state: WorkspaceState
    declared_prior: float
    evidence_support: float | None
    posterior_proxy: float | None
    calibration_status: str
    component_total: float
    residual: float | None
    components: tuple[PosteriorComponent, ...]
    normalized_shares: Mapping[str, float]
    warnings: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.view_id, "view_id")
        require_non_empty(self.hypothesis_id, "hypothesis_id")
        require_non_empty(self.context_key, "context_key")
        if not 0 <= self.declared_prior <= 1:
            raise ValidationError("declared prior must be between zero and one")
        if self.evidence_support is not None and not 0 <= self.evidence_support <= 1:
            raise ValidationError("evidence support must be between zero and one")
        if self.posterior_proxy is not None and not 0 <= self.posterior_proxy <= 1:
            raise ValidationError("posterior proxy must be between zero and one")
        if len({component.component_id for component in self.components}) != len(self.components):
            raise ValidationError("posterior component IDs must be unique")

    @property
    def is_reconciled(self) -> bool:
        return self.residual is not None and abs(self.residual) <= 0.05

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class PosteriorDecompositionViewer:
    """Render declared support components without inventing missing evidence."""

    def view(
        self,
        posterior: DriverPosteriorResult | Mapping[str, Any],
        components: Iterable[PosteriorComponent | Mapping[str, Any]] | Mapping[str, Any] = (),
        *,
        context_key: str,
        residual_tolerance: float = 0.05,
    ) -> PosteriorDecompositionView:
        require_non_empty(context_key, "context_key")
        if residual_tolerance < 0 or residual_tolerance > 1:
            raise ValidationError("posterior residual_tolerance must be between zero and one")
        result = _coerce_posterior(posterior)
        values = tuple(
            _coerce_component(value) for value in _result_values(components, key="components")
        )
        exact = tuple(value for value in values if value.context_key == context_key)
        other_context = tuple(value for value in values if value.context_key != context_key)
        support = result.evidence_support
        total = round(sum(value.contribution for value in exact), 9)
        residual = round(support - total, 9) if support is not None else None
        absolute_total = sum(abs(value.contribution) for value in exact)
        shares = {
            value.component_id: round(abs(value.contribution) / absolute_total, 9)
            if absolute_total
            else 0.0
            for value in exact
        }
        warnings: list[str] = [
            "Posterior proxy and component contributions are research summaries, not calibrated "
            "clinical probabilities.",
            "The declared prior, calibration status, and unexplained residual remain visible.",
        ]
        if other_context:
            warnings.append(
                f"{len(other_context)} posterior component(s) were withheld because "
                "their context did not match."
            )
        if support is None:
            warnings.append("No evidence support was declared; decomposition abstains.")
        elif not exact:
            warnings.append(
                "No exact-context components were supplied; all support remains residual."
            )
        elif residual is not None and abs(residual) > residual_tolerance:
            warnings.append(
                "Component contributions do not reconcile to declared evidence support."
            )
        if any(value.state == WorkspaceState.AMBIGUOUS for value in exact):
            warnings.append("At least one component is ambiguous; shares are descriptive only.")
        if support is None:
            state = WorkspaceState.ABSTAINED
        elif not exact and other_context:
            state = WorkspaceState.OUT_OF_DOMAIN
        elif not exact:
            state = WorkspaceState.PARTIAL
        elif any(value.state == WorkspaceState.AMBIGUOUS for value in exact):
            state = WorkspaceState.AMBIGUOUS
        elif residual is not None and abs(residual) > residual_tolerance:
            state = WorkspaceState.PARTIAL
        else:
            state = _inference_state(result.state)
        view_id = f"posterior-decomposition:{result.hypothesis_id}:{context_key}"
        warning_tuple = tuple(dict.fromkeys(warnings))
        body = {
            "view_id": view_id,
            "hypothesis_id": result.hypothesis_id,
            "context_key": context_key,
            "state": state,
            "declared_prior": result.declared_prior,
            "evidence_support": support,
            "posterior_proxy": result.posterior_proxy,
            "components": exact,
            "residual": residual,
            "warnings": warning_tuple,
        }
        return PosteriorDecompositionView(
            view_id=view_id,
            hypothesis_id=result.hypothesis_id,
            context_key=context_key,
            state=state,
            declared_prior=result.declared_prior,
            evidence_support=support,
            posterior_proxy=result.posterior_proxy,
            calibration_status=result.calibration_status,
            component_total=total,
            residual=residual,
            components=exact,
            normalized_shares=shares,
            warnings=warning_tuple,
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class EvidenceTableFilter:
    """Bounded evidence-table filter contract."""

    text: str = ""
    context_key: str | None = None
    channels: tuple[str, ...] = ()
    tiers: tuple[str, ...] = ()
    states: tuple[WorkspaceState, ...] = ()
    source_ids: tuple[str, ...] = ()
    record_types: tuple[WorkspaceRecordType, ...] = (WorkspaceRecordType.EVIDENCE,)
    min_confidence: float | None = None
    offset: int = 0
    limit: int = 50

    def __post_init__(self) -> None:
        if self.context_key is not None and not self.context_key.strip():
            raise ValidationError("evidence table context cannot be blank")
        for name, values in (
            ("channels", self.channels),
            ("tiers", self.tiers),
            ("source_ids", self.source_ids),
        ):
            if any(not str(value).strip() for value in values):
                raise ValidationError(f"evidence table {name} cannot contain blank values")
            if len(values) != len(set(values)):
                raise ValidationError(f"evidence table {name} must be unique")
        if self.min_confidence is not None and not 0 <= self.min_confidence <= 1:
            raise ValidationError("evidence table min_confidence must be between zero and one")
        if self.offset < 0 or self.limit < 1 or self.limit > 500:
            raise ValidationError("evidence table offset or limit is outside the bounded range")

    def to_query(self) -> WorkspaceQuery:
        return WorkspaceQuery(
            text=self.text,
            context_key=self.context_key,
            record_types=self.record_types,
            states=self.states,
            source_ids=self.source_ids,
            offset=0,
            limit=500,
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceTableRow:
    """Flattened evidence row retaining its full source receipt."""

    record_id: str
    label: str
    record_type: WorkspaceRecordType
    context_key: str
    state: WorkspaceState
    channel: str | None
    tier: str | None
    confidence: float | None
    source_ids: tuple[str, ...]
    tags: tuple[str, ...]
    fields: Mapping[str, Any]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceTableView:
    """Paginated evidence table output with pre-pagination facets."""

    table_id: str
    workspace_id: str
    state: WorkspaceState
    filter: EvidenceTableFilter
    rows: tuple[EvidenceTableRow, ...]
    total_matches: int
    facets: Mapping[str, Mapping[str, int]]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class EvidenceTableAndFilters:
    """Filter workspace evidence while preserving exact context and facets."""

    def build(
        self,
        workspace: ResearchWorkspace,
        table_filter: EvidenceTableFilter | None = None,
    ) -> EvidenceTableView:
        table_filter = table_filter or EvidenceTableFilter(context_key=workspace.context_key)
        if (
            table_filter.context_key is not None
            and table_filter.context_key != workspace.context_key
        ):
            return self._empty(
                workspace,
                table_filter,
                WorkspaceState.OUT_OF_DOMAIN,
                ("requested evidence context does not match workspace context",),
            )
        query = table_filter.to_query()
        candidates = tuple(record for record in workspace.records if query.matches(record))
        filtered = tuple(
            record for record in candidates if self._matches_dimensions(record, table_filter)
        )
        ordered = tuple(
            sorted(
                filtered,
                key=lambda record: (record.record_type.value, record.label, record.record_id),
            )
        )
        page_records = ordered[table_filter.offset : table_filter.offset + table_filter.limit]
        rows = tuple(self._row(record) for record in page_records)
        state = _aggregate_workspace_state(page_records, len(ordered))
        facets = self._facets(ordered)
        warnings = tuple(
            dict.fromkeys(
                (
                    *workspace.warnings,
                    "Evidence table filters records; filtering does not change the "
                    "underlying evidence state.",
                    *(
                        ("At least one evidence record remains unresolved or partial.",)
                        if any(record.state != WorkspaceState.SUPPORTED for record in ordered)
                        else ()
                    ),
                )
            )
        )
        body = {
            "workspace_id": workspace.workspace_id,
            "filter": table_filter,
            "rows": rows,
            "total_matches": len(ordered),
            "facets": facets,
            "state": state,
            "warnings": warnings,
        }
        return EvidenceTableView(
            table_id=f"evidence-table:{workspace.workspace_id}:{content_hash(table_filter)}",
            workspace_id=workspace.workspace_id,
            state=state,
            filter=table_filter,
            rows=rows,
            total_matches=len(ordered),
            facets=facets,
            warnings=warnings,
            content_address=content_hash(body),
        )

    @staticmethod
    def _matches_dimensions(record: WorkspaceRecord, table_filter: EvidenceTableFilter) -> bool:
        fields = record.fields
        channel = str(fields.get("channel", record.tags[0] if record.tags else ""))
        tier = str(fields.get("tier", record.tags[1] if len(record.tags) > 1 else ""))
        if table_filter.channels and channel not in table_filter.channels:
            return False
        if table_filter.tiers and tier not in table_filter.tiers:
            return False
        if table_filter.min_confidence is not None:
            confidence = fields.get("confidence")
            if confidence is None:
                return False
            try:
                if float(confidence) < table_filter.min_confidence:
                    return False
            except (TypeError, ValueError):
                return False
        return True

    @staticmethod
    def _row(record: WorkspaceRecord) -> EvidenceTableRow:
        channel = record.fields.get("channel")
        if channel is None and record.tags:
            channel = record.tags[0]
        tier = record.fields.get("tier")
        if tier is None and len(record.tags) > 1:
            tier = record.tags[1]
        confidence = record.fields.get("confidence")
        if confidence is not None:
            try:
                confidence = round(float(confidence), 9)
            except (TypeError, ValueError):
                confidence = None
        payload = {
            "record_id": record.record_id,
            "label": record.label,
            "record_type": record.record_type,
            "context_key": record.context_key,
            "state": record.state,
            "channel": channel,
            "tier": tier,
            "confidence": confidence,
            "source_ids": record.source_ids,
            "tags": record.tags,
            "fields": record.fields,
        }
        return EvidenceTableRow(
            record_id=record.record_id,
            label=record.label,
            record_type=record.record_type,
            context_key=record.context_key,
            state=record.state,
            channel=str(channel) if channel is not None else None,
            tier=str(tier) if tier is not None else None,
            confidence=confidence,
            source_ids=record.source_ids,
            tags=record.tags,
            fields=record.fields,
            content_address=content_hash(payload),
        )

    @staticmethod
    def _facets(records: Iterable[WorkspaceRecord]) -> dict[str, dict[str, int]]:
        values = tuple(records)
        channel_counts = Counter(
            str(record.fields.get("channel", record.tags[0] if record.tags else ""))
            for record in values
        )
        tier_counts = Counter(
            str(record.fields.get("tier", record.tags[1] if len(record.tags) > 1 else ""))
            for record in values
        )
        return {
            "record_type": dict(
                sorted(Counter(record.record_type.value for record in values).items())
            ),
            "state": dict(sorted(Counter(record.state.value for record in values).items())),
            "channel": dict(sorted(channel_counts.items())),
            "tier": dict(sorted(tier_counts.items())),
            "source_id": dict(
                sorted(Counter(source for record in values for source in record.source_ids).items())
            ),
        }

    @staticmethod
    def _empty(
        workspace: ResearchWorkspace,
        table_filter: EvidenceTableFilter,
        state: WorkspaceState,
        warnings: tuple[str, ...],
    ) -> EvidenceTableView:
        body = {
            "workspace_id": workspace.workspace_id,
            "filter": table_filter,
            "state": state,
            "warnings": warnings,
        }
        return EvidenceTableView(
            table_id=f"evidence-table:{workspace.workspace_id}:{content_hash(table_filter)}",
            workspace_id=workspace.workspace_id,
            state=state,
            filter=table_filter,
            rows=(),
            total_matches=0,
            facets={"record_type": {}, "state": {}, "channel": {}, "tier": {}, "source_id": {}},
            warnings=warnings,
            content_address=content_hash(body),
        )


def _observation_values(value: Any, key: str) -> tuple[tuple[Any, ...], tuple[str, ...]]:
    if value is None:
        return (), ()
    if hasattr(value, key):
        values = getattr(value, key)
        issues = tuple(str(issue.message) for issue in getattr(value, "issues", ()))
        return tuple(values), issues
    if isinstance(value, Mapping) and key in value:
        rows = value[key]
        if not isinstance(rows, (list, tuple)):
            raise ValidationError(f"topology {key} must be a sequence")
        return tuple(
            _coerce_loop(row) if key == "observations" else _coerce_contact(row) for row in rows
        ), ()
    if isinstance(value, (str, bytes)):
        raise ValidationError(f"topology {key} must be a sequence")
    return tuple(
        _coerce_loop(item) if key == "observations" else _coerce_contact(item) for item in value
    ), ()


def _result_values(value: Any, *, key: str | None = None) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, Mapping):
        if key is not None and key in value:
            raw = value[key]
        elif "results" in value:
            raw = value["results"]
        elif "observations" in value:
            raw = value["observations"]
        elif "components" in value:
            raw = value["components"]
        else:
            raw = (value,)
        if not isinstance(raw, (list, tuple)):
            raise ValidationError("projection collection must be a sequence")
        return tuple(raw)
    if isinstance(value, (str, bytes)):
        raise ValidationError("projection collection must be a sequence")
    return tuple(value)


def _coerce_loop(value: LoopStripeObservation | Mapping[str, Any]) -> LoopStripeObservation:
    if isinstance(value, LoopStripeObservation):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("topology loop must be an observation or mapping")
    return LoopStripeObservation(
        feature_id=str(value.get("feature_id", value.get("loop_id", "loop"))),
        feature_kind=TopologyBetaKind(str(value.get("feature_kind", value.get("kind", "loop")))),
        chromosome_a=str(value.get("chromosome_a", value.get("chrom1", ""))),
        start_a=int(value["start_a"]),
        end_a=int(value["end_a"]),
        chromosome_b=str(value.get("chromosome_b", value.get("chrom2", ""))),
        start_b=int(value["start_b"]),
        end_b=int(value["end_b"]),
        signal=float(value.get("signal", value.get("score", 0))),
        context_key=str(value.get("context_key", value.get("context", ""))),
        source_id=str(value.get("source_id", "unspecified")),
        source_version=str(value.get("source_version", "unspecified")),
        raw_hash=str(value.get("raw_hash", content_hash(value))),
        resolution=int(value["resolution"]) if value.get("resolution") is not None else None,
        replicate_id=str(value["replicate_id"]) if value.get("replicate_id") is not None else None,
        caller=str(value["caller"]) if value.get("caller") is not None else None,
        attributes=dict(value.get("attributes", {})),
    )


def _coerce_contact(value: PromoterCaptureContact | Mapping[str, Any]) -> PromoterCaptureContact:
    if isinstance(value, PromoterCaptureContact):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("topology contact must be a contact or mapping")
    return PromoterCaptureContact(
        contact_id=str(value.get("contact_id", value.get("interaction_id", "contact"))),
        promoter_id=str(value.get("promoter_id", value.get("gene_id", ""))),
        target_element_id=str(value.get("target_element_id", value.get("element_id", ""))),
        promoter_chromosome=str(value.get("promoter_chromosome", value.get("promoter_chrom", ""))),
        promoter_start=int(value["promoter_start"]),
        promoter_end=int(value["promoter_end"]),
        target_chromosome=str(value.get("target_chromosome", value.get("target_chrom", ""))),
        target_start=int(value["target_start"]),
        target_end=int(value["target_end"]),
        signal=float(value.get("signal", value.get("score", 0))),
        context_key=str(value.get("context_key", value.get("context", ""))),
        source_id=str(value.get("source_id", "unspecified")),
        source_version=str(value.get("source_version", "unspecified")),
        raw_hash=str(value.get("raw_hash", content_hash(value))),
        resolution=int(value["resolution"]) if value.get("resolution") is not None else None,
        replicate_id=str(value["replicate_id"]) if value.get("replicate_id") is not None else None,
        bait_id=str(value["bait_id"]) if value.get("bait_id") is not None else None,
        attributes=dict(value.get("attributes", {})),
    )


def _coerce_contact_score(
    value: EnhancerPromoterContactScore | Mapping[str, Any],
) -> EnhancerPromoterContactScore:
    if isinstance(value, EnhancerPromoterContactScore):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("contact score must be a score or mapping")
    return EnhancerPromoterContactScore(
        enhancer_id=str(value["enhancer_id"]),
        promoter_id=str(value["promoter_id"]),
        context_key=str(value["context_key"]),
        state=TopologyState(str(value.get("state", TopologyState.SUPPORTED.value))),
        observations=tuple(),
        median_signal=_optional_float(value.get("median_signal")),
        signal_spread=_optional_float(value.get("signal_spread")),
        normalized_contact_score=_optional_float(value.get("normalized_contact_score")),
        source_ids=tuple(str(item) for item in value.get("source_ids", ())),
        source_versions=tuple(str(item) for item in value.get("source_versions", ())),
        reason=str(value.get("reason", "declared contact score")),
        warnings=tuple(str(item) for item in value.get("warnings", ())),
        content_address=str(value.get("content_address", content_hash(value))),
    )


def _coerce_activity(value: ActivityByContactResult | Mapping[str, Any]) -> ActivityByContactResult:
    if isinstance(value, ActivityByContactResult):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("activity-by-contact result must be a result or mapping")
    return ActivityByContactResult(
        enhancer_id=str(value["enhancer_id"]),
        promoter_id=str(value["promoter_id"]),
        context_key=str(value["context_key"]),
        model_id=str(value.get("model_id", "declared-model")),
        model_version=str(value.get("model_version", "unspecified")),
        state=TopologyState(str(value.get("state", TopologyState.SUPPORTED.value))),
        contact_state=TopologyState(str(value.get("contact_state", TopologyState.SUPPORTED.value))),
        activity_state=TopologyState(
            str(value.get("activity_state", TopologyState.SUPPORTED.value))
        ),
        contact_component=_optional_float(value.get("contact_component")),
        activity_component=_optional_float(value.get("activity_component")),
        activity_by_contact_score=_optional_float(value.get("activity_by_contact_score")),
        contact_observations=tuple(),
        activity_observations=tuple(),
        source_ids=tuple(str(item) for item in value.get("source_ids", ())),
        source_versions=tuple(str(item) for item in value.get("source_versions", ())),
        reason=str(value.get("reason", "declared activity-by-contact result")),
        warnings=tuple(str(item) for item in value.get("warnings", ())),
        content_address=str(value.get("content_address", content_hash(value))),
    )


def _coerce_causal_result(value: CausalMediatorResult | Mapping[str, Any]) -> CausalMediatorResult:
    if isinstance(value, CausalMediatorResult):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("causal chain item must be a result or mapping")
    return CausalMediatorResult(
        mediator_kind=MediatorKind(str(value["mediator_kind"])),
        source_node=str(value["source_node"]),
        target_node=str(value["target_node"]),
        context_key=str(value["context_key"]),
        model_id=str(value.get("model_id", "declared-model")),
        model_version=str(value.get("model_version", "unspecified")),
        state=CausalBetaState(str(value.get("state", CausalBetaState.ABSTAINED.value))),
        support=_optional_float(value.get("support")),
        uncertainty=float(value.get("uncertainty", 1.0)),
        sensitivity=_optional_float(value.get("sensitivity")),
        evidence_ids=tuple(str(item) for item in value.get("evidence_ids", ())),
        negative_evidence_ids=tuple(str(item) for item in value.get("negative_evidence_ids", ())),
        source_ids=tuple(str(item) for item in value.get("source_ids", ())),
        source_versions=tuple(str(item) for item in value.get("source_versions", ())),
        reason=str(value.get("reason", "declared mediator result")),
        warnings=tuple(str(item) for item in value.get("warnings", ())),
        content_address=str(value.get("content_address", content_hash(value))),
    )


def _coerce_posterior(value: DriverPosteriorResult | Mapping[str, Any]) -> DriverPosteriorResult:
    if isinstance(value, DriverPosteriorResult):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("posterior must be a result or mapping")
    return DriverPosteriorResult(
        hypothesis_id=str(value.get("hypothesis_id", "hypothesis")),
        state=InferenceState(str(value.get("state", InferenceState.ABSTAINED.value))),
        declared_prior=float(value["declared_prior"]),
        evidence_support=_optional_float(value.get("evidence_support")),
        posterior_proxy=_optional_float(value.get("posterior_proxy")),
        calibration_status=str(value.get("calibration_status", "unspecified")),
        uncertainty=float(value.get("uncertainty", 1.0)),
        observation_ids=tuple(str(item) for item in value.get("observation_ids", ())),
        limitations=tuple(str(item) for item in value.get("limitations", ())),
        content_address=str(value.get("content_address", content_hash(value))),
    )


def _coerce_component(value: PosteriorComponent | Mapping[str, Any]) -> PosteriorComponent:
    if isinstance(value, PosteriorComponent):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("posterior component must be a component or mapping")
    return PosteriorComponent(
        component_id=str(value.get("component_id", value.get("id", "component"))),
        label=str(value.get("label", value.get("component_id", "component"))),
        contribution=float(value.get("contribution", value.get("value", 0.0))),
        context_key=str(value.get("context_key", value.get("context", ""))),
        state=WorkspaceState(str(value.get("state", WorkspaceState.SUPPORTED.value))),
        source_ids=tuple(str(item) for item in value.get("source_ids", ())),
        observation_ids=tuple(str(item) for item in value.get("observation_ids", ())),
        explanation=str(value.get("explanation", "")),
    )


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    result = float(value)
    if not isfinite(result):
        raise ValidationError("numeric value must be finite")
    return result


def _locus_id(chromosome: str, start: int, end: int) -> str:
    return f"locus:{chromosome}:{start}-{end}"


def _has_focus(
    intervals: Iterable[tuple[str, int, int]],
    chromosome: str | None,
    start: int | None,
    end: int | None,
) -> bool:
    if start is None or end is None or chromosome is None:
        return True
    return any(
        normalize_chromosome(item_chromosome) == normalize_chromosome(chromosome)
        and item_end >= start
        and item_start <= end
        for item_chromosome, item_start, item_end in intervals
    )


def _bound_topology(
    nodes: Mapping[str, TopologyViewportNode],
    edges: Iterable[TopologyViewportEdge],
    max_nodes: int,
    max_edges: int,
) -> tuple[dict[str, TopologyViewportNode], list[TopologyViewportEdge], bool]:
    ordered_edges = sorted(edges, key=lambda edge: (edge.kind.value, edge.label, edge.edge_id))
    kept_edges = ordered_edges[:max_edges]
    referenced = {
        node_id for edge in kept_edges for node_id in (edge.source_node_id, edge.target_node_id)
    }
    ordered_nodes = sorted(
        nodes.items(), key=lambda item: (item[1].kind.value, item[1].label, item[0])
    )
    kept_node_ids = {node_id for node_id, _ in ordered_nodes[:max_nodes]}
    if referenced - kept_node_ids:
        kept_node_ids = set(node_id for node_id, _ in ordered_nodes if node_id in referenced)
        if len(kept_node_ids) > max_nodes:
            kept_node_ids = set(sorted(kept_node_ids)[:max_nodes])
    final_edges = [
        edge
        for edge in kept_edges
        if edge.source_node_id in kept_node_ids and edge.target_node_id in kept_node_ids
    ]
    final_nodes = {node_id: nodes[node_id] for node_id in sorted(kept_node_ids)}
    truncated = len(ordered_edges) > len(final_edges) or len(nodes) > len(final_nodes)
    return final_nodes, final_edges, truncated


def _topology_state(state: TopologyState) -> WorkspaceState:
    return {
        TopologyState.SUPPORTED: WorkspaceState.SUPPORTED,
        TopologyState.PARTIAL: WorkspaceState.PARTIAL,
        TopologyState.ABSENT: WorkspaceState.ABSENT,
        TopologyState.AMBIGUOUS: WorkspaceState.AMBIGUOUS,
        TopologyState.OUT_OF_DOMAIN: WorkspaceState.OUT_OF_DOMAIN,
        TopologyState.ABSTAINED: WorkspaceState.ABSTAINED,
        TopologyState.CONTRADICTORY: WorkspaceState.AMBIGUOUS,
    }[state]


def _causal_state(state: CausalBetaState) -> WorkspaceState:
    return {
        CausalBetaState.SUPPORTED: WorkspaceState.SUPPORTED,
        CausalBetaState.PARTIAL: WorkspaceState.PARTIAL,
        CausalBetaState.ABSTAINED: WorkspaceState.ABSTAINED,
        CausalBetaState.OUT_OF_DOMAIN: WorkspaceState.OUT_OF_DOMAIN,
        CausalBetaState.CONTRADICTORY: WorkspaceState.AMBIGUOUS,
        CausalBetaState.AMBIGUOUS: WorkspaceState.AMBIGUOUS,
    }[state]


def _inference_state(state: InferenceState) -> WorkspaceState:
    return {
        InferenceState.SUPPORTED: WorkspaceState.SUPPORTED,
        InferenceState.ABSTAINED: WorkspaceState.ABSTAINED,
        InferenceState.OUT_OF_DOMAIN: WorkspaceState.OUT_OF_DOMAIN,
        InferenceState.MEASURED_NEGATIVE: WorkspaceState.PARTIAL,
        InferenceState.CONTRADICTORY: WorkspaceState.AMBIGUOUS,
        InferenceState.UNSUPPORTED: WorkspaceState.PARTIAL,
    }[state]


def _mediator_role(kind: MediatorKind, *, source: bool) -> str:
    if kind == MediatorKind.SEQUENCE_TO_ELEMENT:
        return "sequence" if source else "regulatory_element"
    if kind == MediatorKind.ELEMENT_TO_GENE:
        return "regulatory_element" if source else "gene"
    return "gene" if source else "molecular_state"


def _worse_workspace_state(first: WorkspaceState, second: WorkspaceState) -> WorkspaceState:
    order = {
        WorkspaceState.SUPPORTED: 0,
        WorkspaceState.PARTIAL: 1,
        WorkspaceState.ABSTAINED: 2,
        WorkspaceState.ABSENT: 2,
        WorkspaceState.AMBIGUOUS: 3,
        WorkspaceState.OUT_OF_DOMAIN: 4,
    }
    return first if order[first] >= order[second] else second


def _aggregate_workspace_state(records: Iterable[WorkspaceRecord], total: int) -> WorkspaceState:
    values = tuple(records)
    if not values and total == 0:
        return WorkspaceState.ABSENT
    if any(record.state == WorkspaceState.OUT_OF_DOMAIN for record in values):
        return WorkspaceState.OUT_OF_DOMAIN
    if any(record.state == WorkspaceState.AMBIGUOUS for record in values):
        return WorkspaceState.AMBIGUOUS
    if any(record.state == WorkspaceState.PARTIAL for record in values):
        return WorkspaceState.PARTIAL
    if any(record.state in {WorkspaceState.ABSTAINED, WorkspaceState.ABSENT} for record in values):
        return WorkspaceState.PARTIAL
    return WorkspaceState.SUPPORTED


__all__ = [
    "CausalChainEdge",
    "CausalChainExplorer",
    "CausalChainNode",
    "CausalChainState",
    "CausalChainView",
    "EvidenceTableAndFilters",
    "EvidenceTableFilter",
    "EvidenceTableRow",
    "EvidenceTableView",
    "PosteriorComponent",
    "PosteriorDecompositionView",
    "PosteriorDecompositionViewer",
    "TopologyEdgeKind",
    "TopologyNodeKind",
    "TopologyViewer",
    "TopologyViewport",
    "TopologyViewportEdge",
    "TopologyViewportNode",
]
