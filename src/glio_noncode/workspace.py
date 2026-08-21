"""Deterministic research-workspace contracts.

Domain 15 provides the read model behind case, cohort, variant, and regulatory
track research surfaces. It deliberately does not depend on a browser toolkit:
workspace records are immutable, searchable, filterable, and serializable so a
CLI, API, notebook, or future graphical client can render the same result.
Exact context, source IDs, unresolved state, and accessibility metadata travel
with each record. A workspace is a research navigation artifact, not a
diagnostic, treatment, or clinical decision surface.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .cohort_discovery import CohortDiscoveryEvidence, CohortState
from .errors import ValidationError
from .identity import normalize_chromosome
from .models import (
    CaseManifest,
    Dossier,
    EvidenceClaim,
    EvidenceState,
    ResearchStatus,
    VariantIdentity,
)
from .regulatory_tracks import RegulatoryTrackBatch
from .serialization import content_hash, jsonable, require_non_empty
from .validation_planning import PlanState, ValidationPlan


class WorkspaceKind(StrEnum):
    """Top-level research workspace surfaces."""

    CASE = "case"
    COHORT = "cohort"
    REGULATORY_TRACK = "regulatory_track"


class WorkspaceRecordType(StrEnum):
    """Typed records rendered by workspace sections."""

    VARIANT = "variant"
    REGULATORY_ELEMENT = "regulatory_element"
    HYPOTHESIS = "hypothesis"
    EVIDENCE = "evidence"
    EXPERIMENT = "experiment"
    COHORT_RECORD = "cohort_record"
    CONTROL = "control"
    SUMMARY = "summary"


class WorkspaceState(StrEnum):
    """Research-display state that preserves evidence boundaries."""

    SUPPORTED = "supported"
    PARTIAL = "partial"
    ABSENT = "absent"
    ABSTAINED = "abstained"
    OUT_OF_DOMAIN = "out_of_domain"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class WorkspaceSection:
    """Accessible section metadata for a client renderer."""

    section_id: str
    title: str
    record_types: tuple[WorkspaceRecordType, ...]
    order: int
    accessible_label: str
    description: str

    def __post_init__(self) -> None:
        for name in ("section_id", "title", "accessible_label", "description"):
            require_non_empty(getattr(self, name), name)
        if self.order < 0:
            raise ValidationError("workspace section order cannot be negative")
        if not self.record_types:
            raise ValidationError("workspace section requires at least one record type")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkspaceRecord:
    """One context-qualified record in a workspace read model."""

    record_id: str
    record_type: WorkspaceRecordType
    label: str
    context_key: str
    state: WorkspaceState
    source_ids: tuple[str, ...] = ()
    chromosome: str | None = None
    start: int | None = None
    end: int | None = None
    tags: tuple[str, ...] = ()
    fields: Mapping[str, Any] = field(default_factory=dict)
    searchable_text: str = ""
    content_address: str = ""

    def __post_init__(self) -> None:
        for name in ("record_id", "label", "context_key"):
            require_non_empty(str(getattr(self, name)), name)
        if (self.start is None) != (self.end is None):
            raise ValidationError("workspace record coordinates require start and end together")
        if self.start is not None and (self.start < 1 or self.end is None or self.end < self.start):
            raise ValidationError("workspace record coordinates are invalid")
        if self.chromosome is None and self.start is not None:
            raise ValidationError("workspace record interval requires chromosome")
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValidationError("workspace record source IDs must be unique")
        if len(self.tags) != len(set(self.tags)):
            raise ValidationError("workspace record tags must be unique")

    @property
    def coordinate_label(self) -> str | None:
        if self.chromosome is None or self.start is None or self.end is None:
            return None
        return f"{self.chromosome}:{self.start}-{self.end}"

    @property
    def searchable(self) -> str:
        parts = [self.record_id, self.label, self.searchable_text, *self.tags]
        parts.extend(str(value) for value in self.fields.values())
        return " ".join(parts).casefold()

    def to_dict(self) -> dict[str, Any]:
        payload = jsonable(self)
        payload["coordinate_label"] = self.coordinate_label
        payload["searchable_text"] = self.searchable_text
        return payload


@dataclass(frozen=True, slots=True)
class WorkspaceQuery:
    """Bounded exact-context filtering and pagination contract."""

    text: str = ""
    context_key: str | None = None
    record_types: tuple[WorkspaceRecordType, ...] = ()
    states: tuple[WorkspaceState, ...] = ()
    chromosome: str | None = None
    start: int | None = None
    end: int | None = None
    source_ids: tuple[str, ...] = ()
    tags_all: tuple[str, ...] = ()
    offset: int = 0
    limit: int = 50

    def __post_init__(self) -> None:
        if self.offset < 0 or self.limit < 1 or self.limit > 500:
            raise ValidationError("workspace offset or limit is outside the bounded range")
        if (self.start is None) != (self.end is None):
            raise ValidationError("workspace query coordinates require start and end together")
        if self.start is not None and (self.start < 1 or self.end is None or self.end < self.start):
            raise ValidationError("workspace query interval is invalid")
        if self.context_key is not None and not self.context_key.strip():
            raise ValidationError("workspace query context cannot be blank")

    def matches(self, record: WorkspaceRecord) -> bool:
        if self.context_key is not None and record.context_key != self.context_key:
            return False
        if self.text.strip() and self.text.casefold() not in record.searchable:
            return False
        if self.record_types and record.record_type not in self.record_types:
            return False
        if self.states and record.state not in self.states:
            return False
        if self.chromosome is not None and normalize_chromosome(
            record.chromosome
        ) != normalize_chromosome(self.chromosome):
            return False
        if self.start is not None and (
            record.start is None
            or record.end is None
            or record.end < self.start
            or record.start > (self.end or self.start)
        ):
            return False
        if self.source_ids and not set(self.source_ids).intersection(record.source_ids):
            return False
        if self.tags_all and not set(self.tags_all).issubset(record.tags):
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkspacePage:
    """Paginated search output with deterministic facets."""

    workspace_id: str
    workspace_kind: WorkspaceKind
    query: WorkspaceQuery
    state: WorkspaceState
    records: tuple[WorkspaceRecord, ...]
    total_matches: int
    facets: Mapping[str, Mapping[str, int]]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ResearchWorkspace:
    """Immutable renderable workspace snapshot."""

    workspace_id: str
    kind: WorkspaceKind
    context_key: str
    records: tuple[WorkspaceRecord, ...]
    sections: tuple[WorkspaceSection, ...]
    state: WorkspaceState
    warnings: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.workspace_id, "workspace_id")
        require_non_empty(self.context_key, "context_key")
        ids = tuple(record.record_id for record in self.records)
        if len(ids) != len(set(ids)):
            raise ValidationError("workspace record IDs must be unique")

    def search(self, query: WorkspaceQuery | None = None) -> WorkspacePage:
        return WorkspaceBrowser().search(self, query or WorkspaceQuery())

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class WorkspaceBrowser:
    """Search, facet, interval, and command-palette operations over a snapshot."""

    def search(
        self, workspace: ResearchWorkspace, query: WorkspaceQuery | None = None
    ) -> WorkspacePage:
        query = query or WorkspaceQuery()
        warnings = list(workspace.warnings)
        if query.context_key is not None and query.context_key != workspace.context_key:
            warnings.append("requested context does not match workspace context")
            return self._page(workspace, query, (), 0, warnings, WorkspaceState.OUT_OF_DOMAIN)
        matched = tuple(record for record in workspace.records if query.matches(record))
        ordered = tuple(
            sorted(matched, key=lambda item: (item.record_type.value, item.label, item.record_id))
        )
        page = ordered[query.offset : query.offset + query.limit]
        state = self._state(page, total_matches=len(ordered))
        return self._page(workspace, query, page, len(ordered), warnings, state, ordered)

    def command_palette(
        self,
        workspace: ResearchWorkspace,
        text: str,
        *,
        limit: int = 20,
    ) -> WorkspacePage:
        if not text.strip():
            raise ValidationError("command palette text must not be blank")
        if limit < 1 or limit > 100:
            raise ValidationError("command palette limit is outside the bounded range")
        return self.search(workspace, WorkspaceQuery(text=text, limit=limit))

    def overlap(
        self,
        workspace: ResearchWorkspace,
        chromosome: str,
        start: int,
        end: int,
        *,
        context_key: str | None = None,
        limit: int = 100,
    ) -> WorkspacePage:
        return self.search(
            workspace,
            WorkspaceQuery(
                context_key=context_key,
                chromosome=chromosome,
                start=start,
                end=end,
                limit=limit,
            ),
        )

    @staticmethod
    def _state(records: Iterable[WorkspaceRecord], *, total_matches: int) -> WorkspaceState:
        values = tuple(records)
        if not values and total_matches == 0:
            return WorkspaceState.ABSENT
        states = {record.state for record in values}
        if WorkspaceState.OUT_OF_DOMAIN in states:
            return WorkspaceState.OUT_OF_DOMAIN
        if WorkspaceState.AMBIGUOUS in states:
            return WorkspaceState.AMBIGUOUS
        if WorkspaceState.PARTIAL in states:
            return WorkspaceState.PARTIAL
        if WorkspaceState.ABSTAINED in states:
            return WorkspaceState.ABSTAINED
        if states == {WorkspaceState.SUPPORTED}:
            return WorkspaceState.SUPPORTED
        return WorkspaceState.PARTIAL

    def _page(
        self,
        workspace: ResearchWorkspace,
        query: WorkspaceQuery,
        records: tuple[WorkspaceRecord, ...],
        total_matches: int,
        warnings: Iterable[str],
        state: WorkspaceState,
        facet_records: Iterable[WorkspaceRecord] | None = None,
    ) -> WorkspacePage:
        values = tuple(facet_records if facet_records is not None else records)
        facets = {
            "record_type": dict(sorted(Counter(item.record_type.value for item in values).items())),
            "state": dict(sorted(Counter(item.state.value for item in values).items())),
            "source_id": dict(
                sorted(
                    Counter(source_id for item in values for source_id in item.source_ids).items()
                )
            ),
        }
        body = {
            "workspace_id": workspace.workspace_id,
            "workspace_kind": workspace.kind,
            "query": query,
            "state": state,
            "records": records,
            "total_matches": total_matches,
            "facets": facets,
            "warnings": tuple(dict.fromkeys(warnings)),
        }
        return WorkspacePage(
            workspace_id=workspace.workspace_id,
            workspace_kind=workspace.kind,
            query=query,
            state=state,
            records=records,
            total_matches=total_matches,
            facets=facets,
            warnings=tuple(dict.fromkeys(warnings)),
            content_address=content_hash(body),
        )


class CaseWorkspaceBuilder:
    """Build a case workspace from the canonical manifest and optional outputs."""

    def build(
        self,
        manifest: CaseManifest,
        *,
        dossier: Dossier | None = None,
        validation_plan: ValidationPlan | None = None,
    ) -> ResearchWorkspace:
        records: list[WorkspaceRecord] = []
        for variant in manifest.variants:
            records.append(self._variant_record(variant, manifest))
        for element in manifest.candidate_elements:
            records.append(
                WorkspaceRecord(
                    record_id=element.element_id,
                    record_type=WorkspaceRecordType.REGULATORY_ELEMENT,
                    label=element.element_id,
                    context_key=element.context.key,
                    state=WorkspaceState.SUPPORTED,
                    source_ids=(element.source_id,),
                    chromosome=element.chromosome,
                    start=element.start,
                    end=element.end,
                    tags=tuple(
                        dict.fromkeys(
                            (element.element_type, *element.target_genes, *element.state_ids)
                        )
                    ),
                    fields={
                        "element_type": element.element_type,
                        "target_genes": element.target_genes,
                        "state_ids": element.state_ids,
                        "features": element.features,
                    },
                    searchable_text=" ".join(
                        (
                            element.element_id,
                            element.element_type,
                            *element.target_genes,
                            *element.state_ids,
                        )
                    ),
                )
            )
        warnings: list[str] = [
            "Case workspace is a research navigation artifact; it does not make a diagnosis "
            "or treatment recommendation."
        ]
        if dossier is None:
            warnings.append(
                "No dossier snapshot supplied; hypothesis and evidence sections are incomplete."
            )
        else:
            records.extend(self._dossier_records(dossier))
        if validation_plan is not None:
            records.extend(self._validation_records(validation_plan, manifest.context.key))
        sections = (
            WorkspaceSection(
                "variants",
                "Variants",
                (WorkspaceRecordType.VARIANT,),
                0,
                "Variants in the case manifest",
                "Canonical variant identities and their declared source context.",
            ),
            WorkspaceSection(
                "regulatory-elements",
                "Regulatory elements",
                (WorkspaceRecordType.REGULATORY_ELEMENT,),
                1,
                "Candidate regulatory elements",
                "Context-qualified candidate intervals; overlap is not mechanism.",
            ),
            WorkspaceSection(
                "hypotheses",
                "Hypotheses",
                (WorkspaceRecordType.HYPOTHESIS,),
                2,
                "Research hypotheses",
                "Typed research hypotheses with alternatives and uncertainty.",
            ),
            WorkspaceSection(
                "evidence",
                "Evidence",
                (WorkspaceRecordType.EVIDENCE,),
                3,
                "Evidence claims",
                "Source-linked claims with unresolved and contradictory states retained.",
            ),
            WorkspaceSection(
                "validation",
                "Validation planning",
                (WorkspaceRecordType.EXPERIMENT,),
                4,
                "Validation experiment options",
                "Review-only experiment packages and assay constraints.",
            ),
        )
        state = (
            WorkspaceState.PARTIAL if dossier is None or not records else WorkspaceState.SUPPORTED
        )
        body = {
            "workspace_id": f"case:{manifest.case_id}",
            "kind": WorkspaceKind.CASE,
            "context_key": manifest.context.key,
            "records": records,
            "sections": sections,
            "state": state,
            "warnings": warnings,
        }
        return ResearchWorkspace(
            workspace_id=f"case:{manifest.case_id}",
            kind=WorkspaceKind.CASE,
            context_key=manifest.context.key,
            records=tuple(records),
            sections=sections,
            state=state,
            warnings=tuple(warnings),
            content_address=content_hash(body),
        )

    @staticmethod
    def _variant_record(variant: VariantIdentity, manifest: CaseManifest) -> WorkspaceRecord:
        source_ids = tuple(sorted(str(key) for key in manifest.input_versions))
        return WorkspaceRecord(
            record_id=variant.variant_id,
            record_type=WorkspaceRecordType.VARIANT,
            label=variant.canonical_key,
            context_key=manifest.context.key,
            state=WorkspaceState.SUPPORTED,
            source_ids=source_ids,
            chromosome=variant.chromosome,
            start=variant.start,
            end=variant.end,
            tags=(variant.kind.value, variant.origin.value, variant.chromosome),
            fields={
                "variant_id": variant.variant_id,
                "kind": variant.kind.value,
                "origin": variant.origin.value,
                "reference": variant.reference,
                "alternate": variant.alternate,
                "sample_id": variant.sample_id,
                "annotations": variant.annotations,
            },
            searchable_text=variant.canonical_key,
        )

    def _dossier_records(self, dossier: Dossier) -> tuple[WorkspaceRecord, ...]:
        records: list[WorkspaceRecord] = []
        for hypothesis in dossier.hypotheses:
            state = (
                WorkspaceState.SUPPORTED
                if hypothesis.status in {ResearchStatus.REVIEWED, ResearchStatus.RELEASED_RESEARCH}
                else WorkspaceState.PARTIAL
            )
            records.append(
                WorkspaceRecord(
                    record_id=hypothesis.hypothesis_id,
                    record_type=WorkspaceRecordType.HYPOTHESIS,
                    label=hypothesis.mechanism,
                    context_key=hypothesis.context.key,
                    state=state,
                    source_ids=hypothesis.provenance,
                    tags=tuple(
                        dict.fromkeys(
                            hype for hype in (hypothesis.state_id, hypothesis.gene_id) if hype
                        )
                    ),
                    fields={
                        "variant_id": hypothesis.variant_id,
                        "element_id": hypothesis.element_id,
                        "gene_id": hypothesis.gene_id,
                        "state_id": hypothesis.state_id,
                        "support": hypothesis.support,
                        "uncertainty": hypothesis.uncertainty,
                        "missing_evidence": hypothesis.missing_evidence,
                        "alternatives": hypothesis.alternatives,
                    },
                    searchable_text=" ".join(
                        (
                            hypothesis.hypothesis_id,
                            hypothesis.mechanism,
                            hypothesis.variant_id,
                            hypothesis.element_id,
                            hypothesis.gene_id,
                            hypothesis.state_id,
                        )
                    ),
                )
            )
        for claim in dossier.evidence:
            records.append(self._evidence_record(claim, dossier.case_id))
        for experiment in dossier.experiments:
            records.append(
                WorkspaceRecord(
                    record_id=experiment.option_id,
                    record_type=WorkspaceRecordType.EXPERIMENT,
                    label=experiment.assay.value,
                    context_key=dossier.hypotheses[0].context.key
                    if dossier.hypotheses
                    else "unspecified",
                    state=WorkspaceState.PARTIAL,
                    source_ids=(),
                    tags=(experiment.assay.value, experiment.cost_class),
                    fields={
                        "tests_edges": experiment.tests_edges,
                        "expected_information_gain": experiment.expected_information_gain,
                        "feasibility": experiment.feasibility,
                        "required_context": experiment.required_context,
                        "controls": experiment.controls,
                        "readouts": experiment.readouts,
                        "limitations": experiment.limitations,
                    },
                    searchable_text=" ".join(
                        (experiment.option_id, experiment.assay.value, *experiment.readouts)
                    ),
                )
            )
        return tuple(records)

    @staticmethod
    def _evidence_record(claim: EvidenceClaim, case_id: str) -> WorkspaceRecord:
        state_map = {
            EvidenceState.SUPPORTED: WorkspaceState.SUPPORTED,
            EvidenceState.MEASURED_NEGATIVE: WorkspaceState.PARTIAL,
            EvidenceState.CONTRADICTORY: WorkspaceState.AMBIGUOUS,
            EvidenceState.ABSENT: WorkspaceState.ABSENT,
            EvidenceState.OUT_OF_DOMAIN: WorkspaceState.OUT_OF_DOMAIN,
            EvidenceState.ABSTAINED: WorkspaceState.ABSTAINED,
            EvidenceState.UNSUPPORTED: WorkspaceState.PARTIAL,
        }
        return WorkspaceRecord(
            record_id=claim.evidence_id,
            record_type=WorkspaceRecordType.EVIDENCE,
            label=claim.summary,
            context_key=claim.context.key,
            state=state_map[claim.state],
            source_ids=(claim.source_id,),
            tags=(claim.channel, claim.tier.value),
            fields={
                "case_id": case_id,
                "edge_id": claim.edge_id,
                "channel": claim.channel,
                "tier": claim.tier.value,
                "score": claim.score,
                "confidence": claim.confidence,
                "payload": claim.payload,
                "supersedes": claim.supersedes,
            },
            searchable_text=" ".join(
                (claim.evidence_id, claim.edge_id, claim.channel, claim.summary)
            ),
        )

    @staticmethod
    def _validation_records(plan: ValidationPlan, context_key: str) -> tuple[WorkspaceRecord, ...]:
        records: list[WorkspaceRecord] = []
        for route in plan.routes:
            records.append(
                WorkspaceRecord(
                    record_id=route.route_id,
                    record_type=WorkspaceRecordType.EXPERIMENT,
                    label=route.assay.value,
                    context_key=context_key,
                    state=WorkspaceState.PARTIAL
                    if route.state != PlanState.READY_FOR_REVIEW
                    else WorkspaceState.SUPPORTED,
                    source_ids=plan.gap_analysis.source_ids,
                    tags=(route.assay.value, route.model_system),
                    fields={
                        "model_system": route.model_system,
                        "blockers": route.blockers,
                        "alternatives": route.alternatives,
                        "sensitivity": route.sensitivity,
                    },
                    searchable_text=" ".join(
                        (route.route_id, route.assay.value, route.model_system)
                    ),
                )
            )
        return tuple(records)


class CohortWorkspaceBuilder:
    """Build a cohort workspace from query, background, and control outputs."""

    def build(self, evidence: CohortDiscoveryEvidence) -> ResearchWorkspace:
        records: list[WorkspaceRecord] = []
        for item in evidence.query.records:
            variant = item.variant
            records.append(
                WorkspaceRecord(
                    record_id=item.record_id,
                    record_type=WorkspaceRecordType.COHORT_RECORD,
                    label=variant.canonical_key,
                    context_key=item.context_key,
                    state=WorkspaceState.SUPPORTED,
                    source_ids=(item.source_id,),
                    chromosome=variant.chromosome,
                    start=variant.start,
                    end=variant.end,
                    tags=(variant.kind.value, variant.origin.value, item.sample_id),
                    fields={
                        "variant_id": variant.variant_id,
                        "sample_id": item.sample_id,
                        "callable": item.callable,
                        "sequence_context": item.sequence_context,
                        "chromatin_features": item.chromatin_features,
                        "annotations": item.annotations,
                    },
                    searchable_text=" ".join(
                        (item.record_id, variant.variant_id, variant.canonical_key)
                    ),
                )
            )
        if evidence.background is not None:
            background = evidence.background
            records.append(
                WorkspaceRecord(
                    record_id=f"background:{evidence.evidence_id}",
                    record_type=WorkspaceRecordType.SUMMARY,
                    label="Local mutation background",
                    context_key=background.context_key,
                    state=_cohort_state(background.state),
                    source_ids=tuple(background.interval_ids),
                    tags=("background",),
                    fields={
                        "observed_count": background.observed_count,
                        "callable_bases": background.callable_bases,
                        "target_callable_bases": background.target_callable_bases,
                        "background_rate": background.background_rate,
                        "expected_count": background.expected_count,
                        "uncertainty": background.uncertainty,
                        "limitations": background.limitations,
                    },
                    searchable_text="local mutation background",
                )
            )
        for result in evidence.sequence_controls + evidence.chromatin_controls:
            for control in result.controls:
                records.append(
                    WorkspaceRecord(
                        record_id=control.control_id,
                        record_type=WorkspaceRecordType.CONTROL,
                        label=control.candidate_id,
                        context_key=control.context_key,
                        state=_cohort_state(result.state),
                        source_ids=(control.source_id,),
                        tags=("control", control.control_type, *control.matched_dimensions),
                        fields={
                            "target_id": control.target_id,
                            "candidate_id": control.candidate_id,
                            "distance": control.distance,
                            "candidate_count": result.candidate_count,
                            "max_distance": result.max_distance,
                            "reason": result.reason,
                            "limitations": result.limitations,
                        },
                        searchable_text=" ".join(
                            (control.control_id, control.candidate_id, control.control_type)
                        ),
                    )
                )
        warnings = list(evidence.limitations)
        state = _cohort_state(evidence.state)
        sections = (
            WorkspaceSection(
                "cohort-records",
                "Cohort records",
                (WorkspaceRecordType.COHORT_RECORD,),
                0,
                "Selected cohort records",
                "Exact-context records selected by the declared cohort query.",
            ),
            WorkspaceSection(
                "background",
                "Background summary",
                (WorkspaceRecordType.SUMMARY,),
                1,
                "Local mutation background summary",
                "Callable-space summary with uncertainty and research limitations.",
            ),
            WorkspaceSection(
                "controls",
                "Matched controls",
                (WorkspaceRecordType.CONTROL,),
                2,
                "Context-matched control candidates",
                "Negative-control candidates and distances; not null proofs.",
            ),
        )
        body = {
            "workspace_id": f"cohort:{evidence.evidence_id}",
            "kind": WorkspaceKind.COHORT,
            "context_key": evidence.context_key,
            "records": records,
            "sections": sections,
            "state": state,
            "warnings": warnings,
        }
        return ResearchWorkspace(
            workspace_id=f"cohort:{evidence.evidence_id}",
            kind=WorkspaceKind.COHORT,
            context_key=evidence.context_key,
            records=tuple(records),
            sections=sections,
            state=state,
            warnings=tuple(warnings),
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class VariantDetail:
    """Variant explorer output with related record IDs and limitations."""

    workspace_id: str
    variant_id: str
    state: WorkspaceState
    variant: WorkspaceRecord | None
    related_record_ids: tuple[str, ...]
    related_by_type: Mapping[str, tuple[str, ...]]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class VariantExplorer:
    """Resolve one variant and its declared workspace relationships."""

    def inspect(
        self,
        workspace: ResearchWorkspace,
        variant_id: str,
        *,
        context_key: str | None = None,
    ) -> VariantDetail:
        require_non_empty(variant_id, "variant_id")
        if context_key is not None and context_key != workspace.context_key:
            return self._detail(
                workspace,
                variant_id,
                None,
                (),
                ("requested context is out of domain",),
                WorkspaceState.OUT_OF_DOMAIN,
            )
        variant = next(
            (
                record
                for record in workspace.records
                if record.record_type == WorkspaceRecordType.VARIANT
                and (
                    record.record_id == variant_id or record.fields.get("variant_id") == variant_id
                )
            ),
            None,
        )
        if variant is None:
            return self._detail(
                workspace,
                variant_id,
                None,
                (),
                ("variant is absent from the workspace",),
                WorkspaceState.ABSTAINED,
            )
        related: list[WorkspaceRecord] = []
        for record in workspace.records:
            if record.record_id == variant.record_id:
                continue
            if record.fields.get("variant_id") == variant_id or variant_id in record.tags:
                related.append(record)
        return self._detail(workspace, variant_id, variant, tuple(related), (), variant.state)

    @staticmethod
    def _detail(
        workspace: ResearchWorkspace,
        variant_id: str,
        variant: WorkspaceRecord | None,
        related: tuple[WorkspaceRecord, ...],
        warnings: tuple[str, ...],
        state: WorkspaceState,
    ) -> VariantDetail:
        by_type: dict[str, list[str]] = {}
        for record in related:
            by_type.setdefault(record.record_type.value, []).append(record.record_id)
        related_ids = tuple(record.record_id for record in related)
        body = {
            "workspace_id": workspace.workspace_id,
            "variant_id": variant_id,
            "state": state,
            "variant": variant,
            "related_record_ids": related_ids,
            "related_by_type": by_type,
            "warnings": warnings,
        }
        return VariantDetail(
            workspace_id=workspace.workspace_id,
            variant_id=variant_id,
            state=state,
            variant=variant,
            related_record_ids=related_ids,
            related_by_type={key: tuple(value) for key, value in sorted(by_type.items())},
            warnings=warnings,
            content_address=content_hash(body),
        )


class RegulatoryTrackBrowser:
    """Convert a parsed regulatory track into an exact-context interval workspace."""

    def build(self, batch: RegulatoryTrackBatch, *, context_key: str) -> ResearchWorkspace:
        require_non_empty(context_key, "context_key")
        records = tuple(
            WorkspaceRecord(
                record_id=feature.feature_id,
                record_type=WorkspaceRecordType.REGULATORY_ELEMENT,
                label=feature.feature_id,
                context_key=context_key,
                state=WorkspaceState.SUPPORTED,
                source_ids=(feature.source_id,),
                chromosome=feature.chromosome,
                start=feature.start,
                end=feature.end,
                tags=(feature.feature_type, feature.chromosome),
                fields={
                    "feature_type": feature.feature_type,
                    "score": feature.score,
                    "strand": feature.strand,
                    "genome_build": feature.genome_build,
                    "attributes": feature.attributes,
                    "source_line": feature.source_line,
                    "raw_hash": feature.raw_hash,
                },
                searchable_text=" ".join(
                    (feature.feature_id, feature.feature_type, str(feature.attributes))
                ),
            )
            for feature in batch.features
        )
        warnings = tuple(
            [
                "Track browser displays annotations and intervals; overlap is not activity "
                "or causality.",
                *(
                    f"{len(batch.issues)} source parse issue(s) remain attached to the track."
                    for _ in (1,)
                    if batch.issues
                ),
            ]
        )
        section = WorkspaceSection(
            "regulatory-elements",
            "Regulatory elements",
            (WorkspaceRecordType.REGULATORY_ELEMENT,),
            0,
            "Regulatory interval records",
            "Parsed intervals with source coordinates, attributes, and row hashes.",
        )
        body = {
            "workspace_id": f"track:{batch.source_id}:{batch.input_hash}",
            "kind": WorkspaceKind.REGULATORY_TRACK,
            "context_key": context_key,
            "records": records,
            "sections": (section,),
            "state": WorkspaceState.PARTIAL if batch.issues else WorkspaceState.SUPPORTED,
            "warnings": warnings,
        }
        return ResearchWorkspace(
            workspace_id=f"track:{batch.source_id}:{batch.input_hash}",
            kind=WorkspaceKind.REGULATORY_TRACK,
            context_key=context_key,
            records=records,
            sections=(section,),
            state=WorkspaceState.PARTIAL if batch.issues else WorkspaceState.SUPPORTED,
            warnings=warnings,
            content_address=content_hash(body),
        )


def _cohort_state(state: CohortState) -> WorkspaceState:
    mapping = {
        CohortState.SUPPORTED: WorkspaceState.SUPPORTED,
        CohortState.PARTIAL: WorkspaceState.PARTIAL,
        CohortState.ABSENT: WorkspaceState.ABSENT,
        CohortState.AMBIGUOUS: WorkspaceState.AMBIGUOUS,
        CohortState.OUT_OF_DOMAIN: WorkspaceState.OUT_OF_DOMAIN,
        CohortState.ABSTAINED: WorkspaceState.ABSTAINED,
    }
    return mapping[state]


__all__ = [
    "CaseWorkspaceBuilder",
    "CohortWorkspaceBuilder",
    "ResearchWorkspace",
    "RegulatoryTrackBrowser",
    "VariantDetail",
    "VariantExplorer",
    "WorkspaceBrowser",
    "WorkspaceKind",
    "WorkspacePage",
    "WorkspaceQuery",
    "WorkspaceRecord",
    "WorkspaceRecordType",
    "WorkspaceSection",
    "WorkspaceState",
]
