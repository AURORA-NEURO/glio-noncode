"""Bounded control-plane contracts for inspectable research workflows.

The control plane is intentionally explicit.  A mission names its research
boundary, data scope, provenance, and resource budget.  An invocation names
one registered role and one registered tool.  The executor checks both before
calling a handler and returns one of four typed outcomes: an evidence
envelope, a workflow decision, a typed error, or an explicit abstention.

The registry is data-driven in this module so a fresh checkout can inspect the
complete architecture without a service dependency.  Handlers are injected
by the application; no role can discover arbitrary callables or reach around
the policy gate.
"""

from __future__ import annotations

import threading
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any, Protocol, TypeAlias

from .errors import GlioError, PolicyViolation, SourceError, ValidationError
from .events import EventLog
from .models import EvidenceState, EvidenceTier
from .policy import ResearchPolicy
from .serialization import content_hash, jsonable, require_non_empty, utc_now
from .workflow import ResourceEnvelope


class Plane(StrEnum):
    """One of the six bounded product planes."""

    CONTROL = "control"
    DATA = "data"
    ATLAS = "atlas"
    INFERENCE = "inference"
    VALIDATION = "validation"
    LIFECYCLE = "lifecycle"


class SafetyClass(StrEnum):
    """Operational boundary for a registered tool."""

    READ_ONLY = "read_only"
    COMPUTE = "compute"
    EXTERNAL_FETCH = "external_fetch"
    EVENT_WRITE = "event_write"
    REVIEW_REQUIRED = "review_required"


class ClaimCeiling(StrEnum):
    """Maximum semantic claim class an output may represent."""

    OBSERVATION = "observation"
    EVIDENCE = "evidence"
    HYPOTHESIS = "hypothesis"
    RESEARCH_RELEASE = "research_release"


class InvocationState(StrEnum):
    """Terminal state of a control-plane invocation."""

    COMPLETED = "completed"
    ABSTAINED = "abstained"
    FAILED = "failed"
    REJECTED = "rejected"


_CLAIM_RANK = {
    ClaimCeiling.OBSERVATION: 0,
    ClaimCeiling.EVIDENCE: 1,
    ClaimCeiling.HYPOTHESIS: 2,
    ClaimCeiling.RESEARCH_RELEASE: 3,
}


def _claim_allowed(agent: ClaimCeiling, mission: ClaimCeiling) -> bool:
    return _CLAIM_RANK[agent] <= _CLAIM_RANK[mission]


@dataclass(frozen=True, slots=True)
class ToolContract:
    """A single allowlisted operation exposed to one bounded role."""

    tool_id: str
    owner_agent_id: str
    name: str
    description: str
    input_contract: str
    output_contract: str
    safety_class: SafetyClass
    resource: ResourceEnvelope = field(default_factory=ResourceEnvelope)
    deterministic: bool = True
    network_egress: bool = False
    mutation_scope: str = "none"
    allowed_source_ids: tuple[str, ...] = ()
    requires_policy_decision: bool = True
    requires_human_review: bool = False

    def __post_init__(self) -> None:
        for name in (
            "tool_id",
            "owner_agent_id",
            "name",
            "description",
            "input_contract",
            "output_contract",
        ):
            require_non_empty(getattr(self, name), name)
        if self.mutation_scope == "none" and self.safety_class == SafetyClass.EVENT_WRITE:
            raise ValidationError("event-write tools must declare a mutation scope")
        if self.network_egress and not self.allowed_source_ids:
            raise ValidationError("network tools must declare allowed source IDs")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AgentSpec:
    """Bounded role metadata used by planning and invocation gates."""

    agent_id: str
    name: str
    plane: Plane
    purpose: str
    input_contracts: tuple[str, ...]
    output_contracts: tuple[str, ...]
    allowed_tool_ids: tuple[str, ...]
    dependency_agent_ids: tuple[str, ...] = ()
    claim_ceiling: ClaimCeiling = ClaimCeiling.EVIDENCE
    review_required: bool = False
    may_abstain: bool = True
    prohibited_actions: tuple[str, ...] = (
        "invent_missing_measurements",
        "alter_upstream_evidence",
        "bypass_policy_gate",
        "promote_own_claim_tier",
    )

    def __post_init__(self) -> None:
        for name in ("agent_id", "name", "purpose"):
            require_non_empty(getattr(self, name), name)
        if not self.input_contracts or not self.output_contracts:
            raise ValidationError(f"{self.agent_id} must declare input and output contracts")
        if not self.allowed_tool_ids:
            raise ValidationError(f"{self.agent_id} must declare at least one tool")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MissionContext:
    """Research intent and boundary carried into every invocation."""

    mission_id: str
    project_id: str
    intended_use: str
    requested_question: str
    claim_ceiling: ClaimCeiling = ClaimCeiling.HYPOTHESIS
    allowed_source_ids: tuple[str, ...] = ()
    allowed_data_scopes: tuple[str, ...] = ("synthetic", "public_reference")
    allowed_mutations: tuple[str, ...] = ("none", "event_log", "content_addressed_store")
    research_use_only: bool = True
    allow_network: bool = False
    private_data_allowed: bool = False
    subject_scope: str = "pseudonymous_research_subject"
    created_at: str = field(default_factory=lambda: utc_now().isoformat())

    def __post_init__(self) -> None:
        for name in ("mission_id", "project_id", "intended_use", "requested_question"):
            require_non_empty(getattr(self, name), name)
        if not self.research_use_only:
            raise ValidationError("control-plane missions must be research-use only")
        if self.allow_network and not self.allowed_source_ids:
            raise ValidationError("network-enabled missions must declare allowed sources")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProvenanceContext:
    """Immutable provenance supplied to a role rather than hidden in memory."""

    input_hashes: tuple[str, ...]
    source_versions: Mapping[str, str] = field(default_factory=dict)
    upstream_event_ids: tuple[str, ...] = ()
    reference_build: str = "unspecified"
    model_digests: tuple[str, ...] = ()
    parent_bundle_addresses: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.input_hashes:
            raise ValidationError("provenance requires at least one input hash")
        require_non_empty(self.reference_build, "reference_build")

    @property
    def digest(self) -> str:
        return content_hash(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkflowBudget:
    """Mission-level limits enforced before a handler is called."""

    capacity: ResourceEnvelope = field(default_factory=ResourceEnvelope)
    max_invocations: int = 128
    max_network_requests: int = 32
    max_seconds: int = 3_600
    max_cost_units: float = 1_000.0

    def __post_init__(self) -> None:
        if self.max_invocations < 1 or self.max_network_requests < 0 or self.max_seconds < 1:
            raise ValidationError("workflow budget limits must be non-negative and useful")
        if self.max_cost_units <= 0:
            raise ValidationError("max_cost_units must be positive")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class InvocationRequest:
    """Complete request envelope presented to the policy gate and handler."""

    request_id: str
    mission: MissionContext
    agent_id: str
    tool_id: str
    input_payload: Mapping[str, Any]
    provenance: ProvenanceContext
    idempotency_key: str
    resource: ResourceEnvelope | None = None
    budget: WorkflowBudget = field(default_factory=WorkflowBudget)
    deadline_seconds: int = 300
    requested_at: str = field(default_factory=lambda: utc_now().isoformat())

    def __post_init__(self) -> None:
        for name in ("request_id", "agent_id", "tool_id", "idempotency_key"):
            require_non_empty(getattr(self, name), name)
        if self.deadline_seconds < 1:
            raise ValidationError("deadline_seconds must be positive")

    def effective_resource(self, tool: ToolContract) -> ResourceEnvelope:
        return self.resource or tool.resource

    @property
    def input_digest(self) -> str:
        return content_hash(self.input_payload)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceEnvelope:
    """Typed evidence result; absence and abstention remain distinct states."""

    evidence_id: str
    agent_id: str
    tool_id: str
    state: EvidenceState
    tier: EvidenceTier
    claim_summary: str
    payload_hash: str
    source_ids: tuple[str, ...] = ()
    provenance_digest: str = ""
    confidence: float | None = None
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("evidence_id", "agent_id", "tool_id", "claim_summary", "payload_hash"):
            require_non_empty(getattr(self, name), name)
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValidationError("evidence confidence must be between 0 and 1")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkflowDecision:
    """Planner result that names every selected role and tool."""

    decision: str
    selected_agent_ids: tuple[str, ...] = ()
    selected_tool_ids: tuple[str, ...] = ()
    requires_human_review: bool = False
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    abstained: bool = False

    def __post_init__(self) -> None:
        require_non_empty(self.decision, "decision")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TypedInvocationError:
    """Serializable error that never masquerades as evidence."""

    code: str
    message: str
    retryable: bool = False
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty(self.code, "code")
        require_non_empty(self.message, "message")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class Abstention:
    """Explicit non-answer with a reason and remediation path."""

    reason_code: str
    scope: str
    explanation: str
    missing_inputs: tuple[str, ...] = ()
    remediation: str = "Collect the missing input or route the case for review."

    def __post_init__(self) -> None:
        for name in ("reason_code", "scope", "explanation", "remediation"):
            require_non_empty(getattr(self, name), name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


ControlOutput: TypeAlias = EvidenceEnvelope | WorkflowDecision | TypedInvocationError | Abstention


@dataclass(frozen=True, slots=True)
class ControlPolicyDecision:
    """Decision produced before scheduling or handler execution."""

    allowed: bool
    violations: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    policy_version: str = "control-plane-2026.08"

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ScheduleDecision:
    """Admission result with current counters for observability."""

    admitted: bool
    reason: str
    total_invocations: int
    network_requests: int
    active_requests: int

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ArbitrationResult:
    """Conflict-aware merge of envelopes from independent branches."""

    accepted: tuple[EvidenceEnvelope, ...]
    conflicts: tuple[str, ...] = ()
    abstentions: tuple[Abstention, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewRoute:
    """Human review gate emitted by the lifecycle boundary."""

    required: bool
    gate: str
    priority: str
    reasons: tuple[str, ...] = ()
    blocked: bool = False

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class InvocationResult:
    """Final execution record, including policy and scheduling facts."""

    request_id: str
    state: InvocationState
    agent_id: str
    tool_id: str
    response: ControlOutput | None = None
    error: TypedInvocationError | None = None
    policy: ControlPolicyDecision | None = None
    schedule: ScheduleDecision | None = None
    review_route: ReviewRoute | None = None
    event_ids: tuple[str, ...] = ()
    cached: bool = False
    started_at: str = ""
    finished_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AgentSeed:
    """Compact registry source record used to build the public catalog."""

    agent_id: str
    name: str
    plane: Plane
    purpose: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    dependencies: tuple[str, ...] = ()
    claim_ceiling: ClaimCeiling = ClaimCeiling.EVIDENCE
    review_required: bool = False
    network: bool = False


_AGENT_SEEDS: tuple[AgentSeed, ...] = (
    AgentSeed(
        "A01",
        "Mission Planner",
        Plane.CONTROL,
        "Translate a research question into bounded work.",
        ("mission_context",),
        ("workflow_decision",),
    ),
    AgentSeed(
        "A02",
        "Workflow Compiler",
        Plane.CONTROL,
        "Compile a dependency-safe role graph with declared budgets.",
        ("mission_context", "agent_registry"),
        ("workflow_decision",),
        ("A01",),
    ),
    AgentSeed(
        "A03",
        "Policy & Claim Gate",
        Plane.CONTROL,
        "Enforce research-use, data-scope, and claim ceilings.",
        ("mission_context", "invocation_request"),
        ("policy_decision",),
        ("A02",),
    ),
    AgentSeed(
        "A04",
        "Resource Scheduler",
        Plane.CONTROL,
        "Admit work within CPU, memory, network, time, and call limits.",
        ("workflow_budget", "invocation_request"),
        ("schedule_decision",),
        ("A02",),
    ),
    AgentSeed(
        "A05",
        "Evidence Arbiter",
        Plane.CONTROL,
        "Merge independent evidence without erasing conflicts.",
        ("evidence_envelope",),
        ("arbitration_result",),
        ("A03", "A04"),
    ),
    AgentSeed(
        "A06",
        "Human Review Router",
        Plane.CONTROL,
        "Route abstentions, release transitions, and policy-sensitive work.",
        ("invocation_result",),
        ("review_route",),
        ("A05",),
        ClaimCeiling.RESEARCH_RELEASE,
        True,
    ),
    AgentSeed(
        "A07",
        "Variant Intake",
        Plane.DATA,
        "Parse declared variants and preserve raw input provenance.",
        ("case_manifest",),
        ("variant_identity",),
    ),
    AgentSeed(
        "A08",
        "Variant Identity/VRS",
        Plane.DATA,
        "Normalize alleles and variation identities across references.",
        ("variant_identity",),
        ("canonical_variant",),
        ("A07",),
    ),
    AgentSeed(
        "A09",
        "Reference Build & Liftover",
        Plane.DATA,
        "Resolve reference assemblies and explicit coordinate transforms.",
        ("canonical_variant", "reference_registry"),
        ("reference_bundle",),
        ("A08",),
        network=True,
    ),
    AgentSeed(
        "A10",
        "Structural Variant Reconstruction",
        Plane.DATA,
        "Reconstruct complex and breakend allele paths.",
        ("canonical_variant",),
        ("variation_graph",),
        ("A08",),
    ),
    AgentSeed(
        "A11",
        "Pangenome Projection",
        Plane.DATA,
        "Project identities across graph and linear reference paths.",
        ("canonical_variant", "reference_bundle"),
        ("projection_bundle",),
        ("A09",),
    ),
    AgentSeed(
        "A12",
        "Sample Lineage",
        Plane.DATA,
        "Track sample relationships without exposing direct identifiers.",
        ("case_manifest",),
        ("lineage_record",),
        ("A07",),
    ),
    AgentSeed(
        "A13",
        "Origin & Clonality",
        Plane.DATA,
        "Represent origin and clonality uncertainty explicitly.",
        ("variant_identity", "lineage_record"),
        ("origin_assessment",),
        ("A12",),
    ),
    AgentSeed(
        "A14",
        "Assay QC",
        Plane.DATA,
        "Check assay support, controls, and measurement quality.",
        ("case_manifest", "assay_record"),
        ("qc_assessment",),
        ("A07",),
    ),
    AgentSeed(
        "A15",
        "Regulatory Atlas",
        Plane.ATLAS,
        "Retrieve context-qualified regulatory annotations.",
        ("reference_bundle", "context"),
        ("candidate_element",),
        ("A09", "A14"),
        network=True,
    ),
    AgentSeed(
        "A16",
        "Brain Reference Atlas",
        Plane.ATLAS,
        "Resolve brain-region and cell-context references.",
        ("context", "reference_bundle"),
        ("context_annotation",),
        ("A09", "A14"),
        network=True,
    ),
    AgentSeed(
        "A17",
        "Glioma Cell-State Atlas",
        Plane.ATLAS,
        "Resolve glioma state and lineage annotations.",
        ("context", "reference_bundle"),
        ("cell_state_annotation",),
        ("A09", "A14"),
        network=True,
    ),
    AgentSeed(
        "A18",
        "Chromatin Context",
        Plane.ATLAS,
        "Collect chromatin accessibility and mark context.",
        ("candidate_element", "context"),
        ("chromatin_evidence",),
        ("A15",),
        network=True,
    ),
    AgentSeed(
        "A19",
        "Methylation Context",
        Plane.ATLAS,
        "Collect methylation context with assay provenance.",
        ("candidate_element", "context"),
        ("methylation_evidence",),
        ("A15",),
        network=True,
    ),
    AgentSeed(
        "A20",
        "3D Genome",
        Plane.ATLAS,
        "Collect contact and topology context without inferring missing contacts.",
        ("candidate_element", "context"),
        ("contact_evidence",),
        ("A15",),
        network=True,
    ),
    AgentSeed(
        "A21",
        "Literature & Knowledge",
        Plane.ATLAS,
        "Extract bounded literature observations and citations.",
        ("canonical_variant", "context"),
        ("literature_evidence",),
        ("A08",),
        network=True,
    ),
    AgentSeed(
        "A22",
        "Functional Data",
        Plane.ATLAS,
        "Collect functional measurements and assay metadata.",
        ("canonical_variant", "context"),
        ("functional_evidence",),
        ("A08", "A14"),
        network=True,
    ),
    AgentSeed(
        "A23",
        "Sequence Ensemble",
        Plane.INFERENCE,
        "Compute sequence-based deltas with model and input digests.",
        ("canonical_variant", "reference_bundle"),
        ("sequence_evidence",),
        ("A08", "A15"),
        ClaimCeiling.HYPOTHESIS,
    ),
    AgentSeed(
        "A24",
        "Motif Grammar",
        Plane.INFERENCE,
        "Evaluate motif grammar changes with explicit sequence windows.",
        ("sequence_evidence", "candidate_element"),
        ("motif_evidence",),
        ("A23", "A15"),
        ClaimCeiling.HYPOTHESIS,
    ),
    AgentSeed(
        "A25",
        "Accessibility Delta",
        Plane.INFERENCE,
        "Estimate accessibility changes only within supported contexts.",
        ("sequence_evidence", "chromatin_evidence"),
        ("accessibility_evidence",),
        ("A23", "A18"),
        ClaimCeiling.HYPOTHESIS,
    ),
    AgentSeed(
        "A26",
        "Topology Rewiring",
        Plane.INFERENCE,
        "Evaluate contact rewiring hypotheses from measured contacts.",
        ("contact_evidence", "candidate_element"),
        ("topology_evidence",),
        ("A20",),
        ClaimCeiling.HYPOTHESIS,
    ),
    AgentSeed(
        "A27",
        "Variant-Element Link",
        Plane.INFERENCE,
        "Score variant-to-element links with contextual features.",
        ("canonical_variant", "candidate_element"),
        ("link_evidence",),
        ("A08", "A15"),
        ClaimCeiling.HYPOTHESIS,
    ),
    AgentSeed(
        "A28",
        "Element-Gene Link",
        Plane.INFERENCE,
        "Score element-to-gene links from explicit evidence paths.",
        ("candidate_element", "contact_evidence"),
        ("link_evidence",),
        ("A15", "A20"),
        ClaimCeiling.HYPOTHESIS,
    ),
    AgentSeed(
        "A29",
        "Allele-Specific Evidence",
        Plane.INFERENCE,
        "Compare alleles while preserving assay and mapping uncertainty.",
        ("canonical_variant", "functional_evidence"),
        ("allele_evidence",),
        ("A08", "A22"),
        ClaimCeiling.HYPOTHESIS,
    ),
    AgentSeed(
        "A30",
        "Cell-State Mechanism",
        Plane.INFERENCE,
        "Assemble context-specific mechanism paths.",
        ("link_evidence", "cell_state_annotation"),
        ("mechanism_edge",),
        ("A17", "A27", "A28"),
        ClaimCeiling.HYPOTHESIS,
    ),
    AgentSeed(
        "A31",
        "Clonal Longitudinal",
        Plane.INFERENCE,
        "Compare longitudinal observations without treating missing timepoints as negatives.",
        ("origin_assessment", "functional_evidence"),
        ("longitudinal_evidence",),
        ("A13", "A22"),
        ClaimCeiling.HYPOTHESIS,
    ),
    AgentSeed(
        "A32",
        "Cohort Recurrence",
        Plane.INFERENCE,
        "Estimate recurrence with matched denominators and cohort provenance.",
        ("canonical_variant", "cohort_record"),
        ("cohort_evidence",),
        ("A08",),
        ClaimCeiling.HYPOTHESIS,
    ),
    AgentSeed(
        "A33",
        "Germline Context",
        Plane.INFERENCE,
        "Separate inherited context from somatic observations.",
        ("origin_assessment", "cohort_record"),
        ("germline_evidence",),
        ("A13",),
        ClaimCeiling.EVIDENCE,
    ),
    AgentSeed(
        "A34",
        "Causal Chain",
        Plane.INFERENCE,
        "Assemble an edge-labeled causal lattice with weakest-link visibility.",
        ("mechanism_edge", "evidence_envelope"),
        ("causal_lattice",),
        ("A30",),
        ClaimCeiling.HYPOTHESIS,
    ),
    AgentSeed(
        "A35",
        "Driver Posterior",
        Plane.INFERENCE,
        "Compute a calibrated research posterior with declared priors.",
        ("causal_lattice", "evidence_envelope"),
        ("hypothesis_posterior",),
        ("A34", "A05"),
        ClaimCeiling.HYPOTHESIS,
        True,
    ),
    AgentSeed(
        "A36",
        "Uncertainty & OOD",
        Plane.INFERENCE,
        "Detect unsupported domains and attach uncertainty reasons.",
        ("hypothesis_posterior", "context"),
        ("uncertainty_assessment",),
        ("A35",),
        ClaimCeiling.HYPOTHESIS,
        True,
    ),
    AgentSeed(
        "A37",
        "Negative Controls",
        Plane.VALIDATION,
        "Construct measured-negative and matched-negative controls.",
        ("candidate_element", "context"),
        ("negative_control_set",),
        ("A15",),
    ),
    AgentSeed(
        "A38",
        "Benchmark",
        Plane.VALIDATION,
        "Run versioned benchmarks with leakage and calibration checks.",
        ("hypothesis_posterior", "negative_control_set"),
        ("benchmark_report",),
        ("A35", "A37"),
        ClaimCeiling.EVIDENCE,
        True,
    ),
    AgentSeed(
        "A39",
        "Assay Router",
        Plane.VALIDATION,
        "Route hypotheses to assays supported by the evidence gap.",
        ("uncertainty_assessment", "candidate_element"),
        ("assay_route",),
        ("A36",),
    ),
    AgentSeed(
        "A40",
        "Guide/Oligo Design",
        Plane.VALIDATION,
        "Design research reagents with off-target and coordinate checks.",
        ("assay_route", "canonical_variant"),
        ("reagent_design",),
        ("A39", "A08"),
        ClaimCeiling.EVIDENCE,
    ),
    AgentSeed(
        "A41",
        "Power & Controls",
        Plane.VALIDATION,
        "Estimate power and control requirements for a proposed assay.",
        ("assay_route", "benchmark_report"),
        ("power_plan",),
        ("A39", "A38"),
        ClaimCeiling.EVIDENCE,
    ),
    AgentSeed(
        "A42",
        "Validation VOI",
        Plane.VALIDATION,
        "Rank validation actions by information value and cost.",
        ("power_plan", "uncertainty_assessment"),
        ("validation_priority",),
        ("A41", "A36"),
        ClaimCeiling.HYPOTHESIS,
    ),
    AgentSeed(
        "A43",
        "Evidence Graph",
        Plane.LIFECYCLE,
        "Persist content-addressed evidence paths and replay metadata.",
        ("evidence_envelope", "causal_lattice"),
        ("evidence_graph_bundle",),
        ("A05", "A34"),
    ),
    AgentSeed(
        "A44",
        "Report & Visualization",
        Plane.LIFECYCLE,
        "Render inspectable reports without flattening caveats.",
        ("evidence_graph_bundle", "hypothesis_posterior"),
        ("research_report",),
        ("A43", "A35"),
    ),
    AgentSeed(
        "A45",
        "Reviewer & Adjudication",
        Plane.LIFECYCLE,
        "Record expert decisions and disagreement reasons.",
        ("research_report", "evidence_graph_bundle"),
        ("review_decision",),
        ("A44",),
        ClaimCeiling.RESEARCH_RELEASE,
        True,
    ),
    AgentSeed(
        "A46",
        "Reclassification",
        Plane.LIFECYCLE,
        "Recompute affected claims when evidence or references change.",
        ("evidence_graph_bundle", "review_decision"),
        ("reclassification_event",),
        ("A43", "A45"),
        ClaimCeiling.RESEARCH_RELEASE,
        True,
    ),
    AgentSeed(
        "A47",
        "Monitoring & Drift",
        Plane.LIFECYCLE,
        "Monitor source, model, calibration, and context drift.",
        ("benchmark_report", "evidence_graph_bundle"),
        ("drift_report",),
        ("A38", "A43"),
        ClaimCeiling.EVIDENCE,
        True,
    ),
    AgentSeed(
        "A48",
        "Security & Privacy",
        Plane.LIFECYCLE,
        "Enforce data minimization, access, and export controls.",
        ("mission_context", "invocation_request"),
        ("security_decision",),
        ("A03",),
        ClaimCeiling.RESEARCH_RELEASE,
        True,
    ),
)


class ControlPlaneRegistry:
    """Validated registry of all bounded roles and their tools."""

    def __init__(self, agents: Iterable[AgentSpec], tools: Iterable[ToolContract]) -> None:
        agent_list = tuple(agents)
        tool_list = tuple(tools)
        self._agents = {agent.agent_id: agent for agent in agent_list}
        self._tools = {tool.tool_id: tool for tool in tool_list}
        if len(self._agents) != len(agent_list):
            raise ValidationError("agent IDs must be unique")
        if len(self._tools) != len(tool_list):
            raise ValidationError("tool IDs must be unique")
        self.validate()

    def validate(self) -> None:
        if len(self._agents) != 48:
            raise ValidationError(
                f"control-plane registry requires 48 agents, found {len(self._agents)}"
            )
        if len(self._tools) != 96:
            raise ValidationError(
                f"control-plane registry requires 96 tools, found {len(self._tools)}"
            )
        for agent in self._agents.values():
            for dependency in agent.dependency_agent_ids:
                if dependency not in self._agents:
                    raise ValidationError(f"{agent.agent_id} depends on unknown agent {dependency}")
            for tool_id in agent.allowed_tool_ids:
                tool = self._tools.get(tool_id)
                if tool is None:
                    raise ValidationError(f"{agent.agent_id} references unknown tool {tool_id}")
                if tool.owner_agent_id != agent.agent_id:
                    raise ValidationError(f"tool {tool_id} has the wrong owner")
        for tool in self._tools.values():
            if tool.owner_agent_id not in self._agents:
                raise ValidationError(
                    f"tool {tool.tool_id} has unknown owner {tool.owner_agent_id}"
                )

    def agent(self, agent_id: str) -> AgentSpec:
        try:
            return self._agents[agent_id]
        except KeyError as exc:
            raise ValidationError(f"unknown agent: {agent_id}") from exc

    def tool(self, tool_id: str) -> ToolContract:
        try:
            return self._tools[tool_id]
        except KeyError as exc:
            raise ValidationError(f"unknown tool: {tool_id}") from exc

    def agents(self) -> tuple[AgentSpec, ...]:
        return tuple(self._agents.values())

    def tools(self) -> tuple[ToolContract, ...]:
        return tuple(self._tools.values())

    def manifest(self) -> dict[str, Any]:
        return {
            "registry_version": "control-plane-2026.08",
            "agent_count": len(self._agents),
            "tool_count": len(self._tools),
            "planes": [plane.value for plane in Plane],
            "agents": [agent.to_dict() for agent in self.agents()],
            "tools": [tool.to_dict() for tool in self.tools()],
        }


def default_control_plane_registry() -> ControlPlaneRegistry:
    """Build the complete six-plane registry from its explicit source table."""

    agents: list[AgentSpec] = []
    tools: list[ToolContract] = []
    for seed in _AGENT_SEEDS:
        inspect_id = f"{seed.agent_id}.inspect"
        publish_id = f"{seed.agent_id}.publish"
        agents.append(
            AgentSpec(
                agent_id=seed.agent_id,
                name=seed.name,
                plane=seed.plane,
                purpose=seed.purpose,
                input_contracts=seed.inputs,
                output_contracts=seed.outputs,
                allowed_tool_ids=(inspect_id, publish_id),
                dependency_agent_ids=seed.dependencies,
                claim_ceiling=seed.claim_ceiling,
                review_required=seed.review_required,
            )
        )
        source_ids = (
            (
                "SRC-ENSEMBL-REST",
                "SRC-UCSC-REST",
                "SRC-ENCODE-REST",
            )
            if seed.network
            else ()
        )
        tools.extend(
            (
                ToolContract(
                    tool_id=inspect_id,
                    owner_agent_id=seed.agent_id,
                    name=f"{seed.name.lower().replace(' ', '-')}.inspect",
                    description=(
                        f"Read declared inputs for {seed.name}; no upstream mutation is permitted."
                    ),
                    input_contract=", ".join(seed.inputs),
                    output_contract="inspection_record",
                    safety_class=SafetyClass.EXTERNAL_FETCH
                    if seed.network
                    else SafetyClass.READ_ONLY,
                    resource=ResourceEnvelope(
                        cpu=1.0,
                        memory_gb=2.0,
                        storage_gb=0.5,
                        network_egress=seed.network,
                        max_seconds=120,
                    ),
                    network_egress=seed.network,
                    allowed_source_ids=source_ids,
                ),
                ToolContract(
                    tool_id=publish_id,
                    owner_agent_id=seed.agent_id,
                    name=f"{seed.name.lower().replace(' ', '-')}.publish",
                    description=(
                        f"Emit a typed {seed.outputs[0]} result and an event-log "
                        f"record for {seed.name}."
                    ),
                    input_contract="inspection_record",
                    output_contract=seed.outputs[0],
                    safety_class=SafetyClass.REVIEW_REQUIRED
                    if seed.review_required
                    else SafetyClass.EVENT_WRITE,
                    resource=ResourceEnvelope(
                        cpu=1.0, memory_gb=2.0, storage_gb=1.0, max_seconds=180
                    ),
                    mutation_scope="event_log",
                    requires_human_review=seed.review_required,
                ),
            )
        )
    return ControlPlaneRegistry(agents, tools)


class PolicyClaimGate:
    """Apply mission, claim, source, and data-minimization policy."""

    _sensitive_keys = frozenset(
        {
            "name",
            "full_name",
            "email",
            "phone",
            "address",
            "mrn",
            "medical_record_number",
            "date_of_birth",
            "dob",
            "patient_name",
        }
    )

    def __init__(self, policy: ResearchPolicy | None = None) -> None:
        self.policy = policy or ResearchPolicy()

    def inspect(
        self, request: InvocationRequest, agent: AgentSpec, tool: ToolContract
    ) -> ControlPolicyDecision:
        violations: list[str] = []
        warnings: list[str] = ["Research-use only; outputs require domain review before release."]
        policy = self.policy.inspect_texts(
            (request.mission.intended_use, request.mission.requested_question)
        )
        violations.extend(policy.violations)
        if not _claim_allowed(agent.claim_ceiling, request.mission.claim_ceiling):
            violations.append(
                "agent claim ceiling "
                f"{agent.claim_ceiling.value} exceeds mission ceiling "
                f"{request.mission.claim_ceiling.value}"
            )
        if tool.network_egress and not request.mission.allow_network:
            violations.append("network egress is not enabled for this mission")
        source_difference = set(tool.allowed_source_ids) - set(request.mission.allowed_source_ids)
        if source_difference:
            violations.append(
                f"tool sources are outside the mission allowlist: {sorted(source_difference)}"
            )
        if tool.mutation_scope not in request.mission.allowed_mutations:
            violations.append(f"mutation scope is not allowed: {tool.mutation_scope}")
        declared_scope = request.input_payload.get("data_scope")
        if (
            isinstance(declared_scope, str)
            and declared_scope not in request.mission.allowed_data_scopes
        ):
            violations.append(f"data scope is not allowed for this mission: {declared_scope}")
        sensitive = self._find_sensitive_keys(request.input_payload)
        if sensitive and not request.mission.private_data_allowed:
            violations.append(
                f"direct identifiers are not allowed in invocation payload: {sorted(sensitive)}"
            )
        if not request.provenance.input_hashes:
            violations.append("provenance input hashes are required")
        return ControlPolicyDecision(
            allowed=not violations,
            violations=tuple(dict.fromkeys(violations)),
            warnings=tuple(dict.fromkeys(warnings + list(policy.warnings))),
            policy_version=policy.policy_version,
        )

    @classmethod
    def _find_sensitive_keys(cls, value: object, path: str = "payload") -> set[str]:
        found: set[str] = set()
        if isinstance(value, Mapping):
            for key, child in value.items():
                key_text = str(key).lower()
                if key_text in cls._sensitive_keys:
                    found.add(f"{path}.{key_text}")
                found.update(cls._find_sensitive_keys(child, f"{path}.{key_text}"))
        elif isinstance(value, (list, tuple)):
            for index, child in enumerate(value):
                found.update(cls._find_sensitive_keys(child, f"{path}[{index}]"))
        return found


class MissionPlanner:
    """Dependency planner that expands requested roles without hidden work."""

    def __init__(self, registry: ControlPlaneRegistry | None = None) -> None:
        self.registry = registry or default_control_plane_registry()

    def plan(self, mission: MissionContext, requested_agent_ids: Iterable[str]) -> WorkflowDecision:
        requested = tuple(dict.fromkeys(requested_agent_ids))
        if not requested:
            return WorkflowDecision(
                decision="abstain",
                abstained=True,
                reasons=("no agent roles were requested",),
            )
        selected: set[str] = set()
        reasons: list[str] = []

        def include(agent_id: str) -> None:
            agent = self.registry.agent(agent_id)
            if not _claim_allowed(agent.claim_ceiling, mission.claim_ceiling):
                raise PolicyViolation(
                    f"{agent_id} requires claim ceiling {agent.claim_ceiling.value}, "
                    f"mission allows {mission.claim_ceiling.value}"
                )
            if agent_id in selected:
                return
            for dependency in agent.dependency_agent_ids:
                include(dependency)
            selected.add(agent_id)

        for agent_id in requested:
            include(agent_id)
        ordered = tuple(
            agent.agent_id for agent in self.registry.agents() if agent.agent_id in selected
        )
        selected_tools = tuple(
            tool_id
            for agent_id in ordered
            for tool_id in self.registry.agent(agent_id).allowed_tool_ids
        )
        if any(self.registry.agent(agent_id).review_required for agent_id in ordered):
            reasons.append("At least one selected role requires human review.")
        if any(self.registry.tool(tool_id).network_egress for tool_id in selected_tools):
            reasons.append("The plan includes public-source network retrieval.")
        return WorkflowDecision(
            decision="planned",
            selected_agent_ids=ordered,
            selected_tool_ids=selected_tools,
            requires_human_review=any(
                self.registry.agent(agent_id).review_required for agent_id in ordered
            ),
            reasons=tuple(reasons),
        )


class ResourceScheduler:
    """Thread-safe admission controller for bounded invocations."""

    def __init__(self, capacity: ResourceEnvelope | None = None) -> None:
        self.capacity = capacity or ResourceEnvelope(
            cpu=8, memory_gb=32, storage_gb=100, network_egress=True, max_seconds=3_600
        )
        self._lock = threading.Lock()
        self._total_invocations = 0
        self._network_requests = 0
        self._active: dict[str, ResourceEnvelope] = {}

    def admit(self, request: InvocationRequest, tool: ToolContract) -> ScheduleDecision:
        resource = request.effective_resource(tool)
        with self._lock:
            if request.request_id in self._active:
                return self._snapshot(False, "request is already active")
            if not resource.fits(self.capacity):
                return self._snapshot(False, "requested resources exceed scheduler capacity")
            if resource.max_seconds > request.deadline_seconds:
                return self._snapshot(False, "resource deadline exceeds invocation deadline")
            if self._total_invocations >= request.budget.max_invocations:
                return self._snapshot(False, "mission invocation budget exhausted")
            is_network = resource.network_egress or tool.network_egress
            if is_network and self._network_requests >= request.budget.max_network_requests:
                return self._snapshot(False, "mission network request budget exhausted")
            projected_seconds = (
                sum(item.max_seconds for item in self._active.values()) + resource.max_seconds
            )
            if projected_seconds > request.budget.max_seconds:
                return self._snapshot(False, "mission wall-time budget exhausted")
            self._total_invocations += 1
            if is_network:
                self._network_requests += 1
            self._active[request.request_id] = resource
            return self._snapshot(True, "admitted")

    def release(self, request_id: str) -> None:
        with self._lock:
            self._active.pop(request_id, None)

    def snapshot(self) -> ScheduleDecision:
        with self._lock:
            return self._snapshot(True, "snapshot")

    def _snapshot(self, admitted: bool, reason: str) -> ScheduleDecision:
        return ScheduleDecision(
            admitted=admitted,
            reason=reason,
            total_invocations=self._total_invocations,
            network_requests=self._network_requests,
            active_requests=len(self._active),
        )


class EvidenceArbiter:
    """Retain one consistent envelope per ID and expose conflicts explicitly."""

    def arbitrate(self, envelopes: Iterable[EvidenceEnvelope]) -> ArbitrationResult:
        grouped: dict[str, list[EvidenceEnvelope]] = {}
        for envelope in envelopes:
            grouped.setdefault(envelope.evidence_id, []).append(envelope)
        accepted: list[EvidenceEnvelope] = []
        conflicts: list[str] = []
        abstentions: list[Abstention] = []
        for evidence_id, candidates in grouped.items():
            hashes = {candidate.payload_hash for candidate in candidates}
            if len(hashes) > 1:
                conflicts.append(evidence_id)
                abstentions.append(
                    Abstention(
                        reason_code="conflicting_evidence_payloads",
                        scope=evidence_id,
                        explanation=(
                            "Independent branches returned different payload hashes "
                            "for one evidence ID."
                        ),
                        remediation=(
                            "Route the conflict for adjudication; do not silently "
                            "choose one branch."
                        ),
                    )
                )
                continue
            ordered = sorted(
                candidates, key=lambda item: (item.tier.value, item.agent_id, item.tool_id)
            )
            accepted.append(ordered[-1])
        return ArbitrationResult(tuple(accepted), tuple(conflicts), tuple(abstentions))


class HumanReviewRouter:
    """Turn role and outcome metadata into a concrete review gate."""

    def route(self, agent: AgentSpec, response: ControlOutput) -> ReviewRoute:
        reasons: list[str] = []
        if agent.review_required:
            reasons.append(f"{agent.agent_id} is designated review-required")
        if isinstance(response, Abstention):
            reasons.append(f"abstention requires review: {response.reason_code}")
        if isinstance(response, TypedInvocationError) and not response.retryable:
            reasons.append(f"non-retryable typed error: {response.code}")
        required = bool(reasons)
        return ReviewRoute(
            required=required,
            gate="expert_review" if required else "automatic_research_path",
            priority="high" if isinstance(response, Abstention) else "normal",
            reasons=tuple(reasons),
            blocked=isinstance(response, Abstention),
        )


class Handler(Protocol):
    def __call__(self, request: InvocationRequest) -> ControlOutput: ...


class ControlPlaneExecutor:
    """Execute only registered handlers with policy, budget, and event guards."""

    def __init__(
        self,
        registry: ControlPlaneRegistry | None = None,
        *,
        policy_gate: PolicyClaimGate | None = None,
        scheduler: ResourceScheduler | None = None,
        review_router: HumanReviewRouter | None = None,
    ) -> None:
        self.registry = registry or default_control_plane_registry()
        self.policy_gate = policy_gate or PolicyClaimGate()
        self.scheduler = scheduler or ResourceScheduler()
        self.review_router = review_router or HumanReviewRouter()
        self.event_log = EventLog("control-plane")
        self._handlers: dict[str, Handler] = {}
        self._idempotent: dict[str, InvocationResult] = {}
        self._lock = threading.Lock()

    def register(self, tool_id: str, handler: Handler) -> None:
        self.registry.tool(tool_id)
        with self._lock:
            if tool_id in self._handlers:
                raise ValidationError(f"handler already registered for {tool_id}")
            self._handlers[tool_id] = handler

    def execute(self, request: InvocationRequest) -> InvocationResult:
        started = utc_now().isoformat()
        agent = self.registry.agent(request.agent_id)
        tool = self.registry.tool(request.tool_id)
        if tool.owner_agent_id != agent.agent_id or tool.tool_id not in agent.allowed_tool_ids:
            return self._rejected(
                request, started, "tool is not allowlisted for the selected agent"
            )
        with self._lock:
            cached = self._idempotent.get(request.idempotency_key)
        if cached is not None:
            return replace(cached, cached=True)
        policy = self.policy_gate.inspect(request, agent, tool)
        if not policy.allowed:
            return self._rejected(request, started, "; ".join(policy.violations), policy=policy)
        schedule = self.scheduler.admit(request, tool)
        if not schedule.admitted:
            return self._result(
                request,
                InvocationState.REJECTED,
                started,
                error=TypedInvocationError("resource_denied", schedule.reason, retryable=True),
                policy=policy,
                schedule=schedule,
            )
        self.event_log.append(
            "control_invocation_admitted",
            {
                "request_id": request.request_id,
                "mission_id": request.mission.mission_id,
                "agent_id": request.agent_id,
                "tool_id": request.tool_id,
                "input_digest": request.input_digest,
                "provenance_digest": request.provenance.digest,
            },
            event_id=f"{request.request_id}:admitted",
        )
        try:
            handler = self._handlers.get(tool.tool_id)
            if handler is None:
                response: ControlOutput = TypedInvocationError(
                    "handler_unavailable",
                    f"no executable handler is registered for {tool.tool_id}",
                    retryable=False,
                )
            else:
                response = handler(request)
            result = self._classify(request, response, started, policy, schedule, agent)
        except SourceError as exc:
            response = Abstention(
                reason_code="source_unavailable",
                scope=tool.tool_id,
                explanation=str(exc),
                remediation=(
                    "Retry only under the source policy or use a declared alternate "
                    "source; do not infer a negative."
                ),
            )
            result = self._classify(request, response, started, policy, schedule, agent)
        except GlioError as exc:
            result = self._result(
                request,
                InvocationState.FAILED,
                started,
                error=TypedInvocationError(exc.code, str(exc), retryable=False),
                policy=policy,
                schedule=schedule,
                review_route=ReviewRoute(False, "automatic_research_path", "normal"),
            )
        except Exception as exc:  # pragma: no cover - process boundary for injected handlers
            result = self._result(
                request,
                InvocationState.FAILED,
                started,
                error=TypedInvocationError("handler_failure", str(exc), retryable=False),
                policy=policy,
                schedule=schedule,
                review_route=ReviewRoute(False, "automatic_research_path", "normal"),
            )
        finally:
            self.scheduler.release(request.request_id)
        self.event_log.append(
            "control_invocation_completed",
            {
                "request_id": request.request_id,
                "state": result.state.value,
                "response_digest": content_hash(result.response.to_dict())
                if result.response
                else None,
                "error_code": result.error.code if result.error else None,
            },
            event_id=f"{request.request_id}:completed",
        )
        result = replace(
            result, event_ids=(f"{request.request_id}:admitted", f"{request.request_id}:completed")
        )
        with self._lock:
            self._idempotent[request.idempotency_key] = result
        return result

    def _classify(
        self,
        request: InvocationRequest,
        response: ControlOutput,
        started: str,
        policy: ControlPolicyDecision,
        schedule: ScheduleDecision,
        agent: AgentSpec,
    ) -> InvocationResult:
        if isinstance(response, Abstention):
            state = InvocationState.ABSTAINED
        elif isinstance(response, TypedInvocationError):
            state = InvocationState.FAILED
        elif isinstance(response, (EvidenceEnvelope, WorkflowDecision)):
            state = InvocationState.COMPLETED
        else:
            response = TypedInvocationError(
                "invalid_handler_output",
                "handler returned an unregistered control-plane output type",
                retryable=False,
            )
            state = InvocationState.FAILED
        route = self.review_router.route(agent, response)
        return self._result(
            request,
            state,
            started,
            response=response,
            policy=policy,
            schedule=schedule,
            review_route=route,
        )

    def _rejected(
        self,
        request: InvocationRequest,
        started: str,
        message: str,
        *,
        policy: ControlPolicyDecision | None = None,
    ) -> InvocationResult:
        return self._result(
            request,
            InvocationState.REJECTED,
            started,
            error=TypedInvocationError("policy_denied", message, retryable=False),
            policy=policy,
        )

    def _result(
        self,
        request: InvocationRequest,
        state: InvocationState,
        started: str,
        *,
        response: ControlOutput | None = None,
        error: TypedInvocationError | None = None,
        policy: ControlPolicyDecision | None = None,
        schedule: ScheduleDecision | None = None,
        review_route: ReviewRoute | None = None,
    ) -> InvocationResult:
        return InvocationResult(
            request_id=request.request_id,
            state=state,
            agent_id=request.agent_id,
            tool_id=request.tool_id,
            response=response,
            error=error,
            policy=policy,
            schedule=schedule,
            review_route=review_route,
            started_at=started,
            finished_at=utc_now().isoformat(),
        )
