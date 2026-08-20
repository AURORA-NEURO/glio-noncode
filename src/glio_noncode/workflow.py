"""Typed workflow compilation with dependencies and resource envelopes."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

from .errors import ValidationError


class StepKind(str, Enum):
    INGEST = "ingest"
    NORMALIZE = "normalize"
    CONTEXT = "context"
    EVIDENCE = "evidence"
    INTEGRATE = "integrate"
    VALIDATE = "validate"
    REVIEW = "review"
    EXPORT = "export"


@dataclass(frozen=True, slots=True)
class ResourceEnvelope:
    """Declared runtime envelope used for scheduling and cost accounting."""

    cpu: float = 1.0
    memory_gb: float = 1.0
    gpu_count: int = 0
    storage_gb: float = 1.0
    network_egress: bool = False
    max_seconds: int = 300

    def __post_init__(self) -> None:
        if self.cpu <= 0 or self.memory_gb <= 0 or self.storage_gb <= 0 or self.max_seconds <= 0:
            raise ValidationError("resource envelope values must be positive")
        if self.gpu_count < 0:
            raise ValidationError("gpu_count cannot be negative")

    def fits(self, capacity: "ResourceEnvelope") -> bool:
        return (
            self.cpu <= capacity.cpu
            and self.memory_gb <= capacity.memory_gb
            and self.gpu_count <= capacity.gpu_count
            and self.storage_gb <= capacity.storage_gb
            and (not self.network_egress or capacity.network_egress)
        )


@dataclass(frozen=True, slots=True)
class WorkflowStep:
    """One bounded operation in a compiled case workflow."""

    step_id: str
    kind: StepKind
    depends_on: tuple[str, ...] = ()
    resource: ResourceEnvelope = field(default_factory=ResourceEnvelope)
    optional: bool = False
    deterministic: bool = True
    input_contract: str = "unspecified"
    output_contract: str = "unspecified"

    def __post_init__(self) -> None:
        if not self.step_id:
            raise ValidationError("workflow step ID is required")


@dataclass(frozen=True, slots=True)
class CompiledWorkflow:
    """Topologically ordered workflow and aggregate resource envelope."""

    workflow_id: str
    steps: tuple[WorkflowStep, ...]
    total_cpu: float
    peak_memory_gb: float
    total_storage_gb: float
    max_seconds: int
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "workflow_id": self.workflow_id,
            "steps": [
                {
                    "step_id": step.step_id,
                    "kind": step.kind.value,
                    "depends_on": list(step.depends_on),
                    "resource": {
                        "cpu": step.resource.cpu,
                        "memory_gb": step.resource.memory_gb,
                        "gpu_count": step.resource.gpu_count,
                        "storage_gb": step.resource.storage_gb,
                        "network_egress": step.resource.network_egress,
                        "max_seconds": step.resource.max_seconds,
                    },
                    "optional": step.optional,
                    "deterministic": step.deterministic,
                    "input_contract": step.input_contract,
                    "output_contract": step.output_contract,
                }
                for step in self.steps
            ],
            "total_cpu": self.total_cpu,
            "peak_memory_gb": self.peak_memory_gb,
            "total_storage_gb": self.total_storage_gb,
            "max_seconds": self.max_seconds,
            "warnings": list(self.warnings),
        }


class WorkflowCompiler:
    """Compile and validate a DAG without silently dropping optional steps."""

    def compile(self, workflow_id: str, steps: Iterable[WorkflowStep]) -> CompiledWorkflow:
        step_list = list(steps)
        by_id = {step.step_id: step for step in step_list}
        if len(by_id) != len(step_list):
            raise ValidationError("workflow step IDs must be unique")
        for step in step_list:
            missing = set(step.depends_on) - set(by_id)
            if missing:
                raise ValidationError(f"workflow step {step.step_id} has missing dependencies: {sorted(missing)}")
        ordered: list[WorkflowStep] = []
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(step_id: str) -> None:
            if step_id in visiting:
                raise ValidationError(f"workflow cycle includes {step_id}")
            if step_id in visited:
                return
            visiting.add(step_id)
            for dependency in by_id[step_id].depends_on:
                visit(dependency)
            visiting.remove(step_id)
            visited.add(step_id)
            ordered.append(by_id[step_id])

        for step in step_list:
            visit(step.step_id)
        warnings = []
        if any(not step.deterministic for step in ordered):
            warnings.append("At least one workflow step is nondeterministic and must record a seed or model digest.")
        if any(step.resource.network_egress for step in ordered):
            warnings.append("Workflow requests network egress; local-only policy should be reviewed.")
        return CompiledWorkflow(
            workflow_id=workflow_id,
            steps=tuple(ordered),
            total_cpu=round(sum(step.resource.cpu for step in ordered), 6),
            peak_memory_gb=round(max(step.resource.memory_gb for step in ordered), 6),
            total_storage_gb=round(sum(step.resource.storage_gb for step in ordered), 6),
            max_seconds=sum(step.resource.max_seconds for step in ordered),
            warnings=tuple(warnings),
        )

    def compile_initial_slice(self, workflow_id: str = "mvp-initial") -> CompiledWorkflow:
        return self.compile(
            workflow_id,
            (
                WorkflowStep("ingest", StepKind.INGEST, resource=ResourceEnvelope(cpu=1, memory_gb=1, storage_gb=1, max_seconds=60), output_contract="case_manifest"),
                WorkflowStep("normalize", StepKind.NORMALIZE, ("ingest",), resource=ResourceEnvelope(cpu=1, memory_gb=2, storage_gb=1, max_seconds=120), input_contract="case_manifest", output_contract="canonical_case"),
                WorkflowStep("context", StepKind.CONTEXT, ("normalize",), resource=ResourceEnvelope(cpu=1, memory_gb=2, storage_gb=1, max_seconds=180), input_contract="canonical_case", output_contract="contextual_case"),
                WorkflowStep("evidence", StepKind.EVIDENCE, ("context",), resource=ResourceEnvelope(cpu=2, memory_gb=4, storage_gb=3, max_seconds=600), input_contract="contextual_case", output_contract="evidence_claims"),
                WorkflowStep("integrate", StepKind.INTEGRATE, ("evidence",), resource=ResourceEnvelope(cpu=2, memory_gb=4, storage_gb=2, max_seconds=300), input_contract="evidence_claims", output_contract="hypotheses"),
                WorkflowStep("validate", StepKind.VALIDATE, ("integrate",), resource=ResourceEnvelope(cpu=1, memory_gb=2, storage_gb=1, max_seconds=180), input_contract="hypotheses", output_contract="validation_routes"),
                WorkflowStep("review", StepKind.REVIEW, ("validate",), resource=ResourceEnvelope(cpu=1, memory_gb=1, storage_gb=1, max_seconds=30), input_contract="validation_routes", output_contract="reviewable_dossier"),
                WorkflowStep("export", StepKind.EXPORT, ("review",), resource=ResourceEnvelope(cpu=1, memory_gb=1, storage_gb=1, max_seconds=60), input_contract="reviewable_dossier", output_contract="research_snapshot"),
            ),
        )
