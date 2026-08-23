"""Public aggregate fixture and boundary receipts for Domain 12 C05-C08."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .cohort_beta import CohortBetaState
from .serialization import content_hash, jsonable, require_non_empty

C05_C08_CONTEXT = "GRCh38|glioma|adult|stem_like|tumor_core|pre_treatment"
C05_C08_FOREIGN_CONTEXT = "GRCh38|glioma|adult|stem_like|tumor_margin|post_treatment"
C05_C08_BOUNDARY = "descriptive_public_aggregate_evidence"
C05_C08_FIXTURE_VERSION = "2026.08.d12-c05-c08.v1"


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierSource:
    """One public source receipt used to define the aggregate fixture."""

    source_id: str
    label: str
    url: str
    version: str
    retrieval_note: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("source_id", "label", "url", "version", "retrieval_note"):
            require_non_empty(str(getattr(self, name)), name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierRecord:
    """A pseudonymous operation input with an expected bounded state."""

    operation: str
    record_id: str
    payload: Mapping[str, Any]
    expected_state: CohortBetaState
    control_class: str
    source_ids: tuple[str, ...]
    rationale: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("operation", "record_id", "control_class", "rationale"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.payload:
            raise ValueError("frontier record payload must not be empty")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierFixture:
    """Closed fixture containing positive, control, and foreign-context paths."""

    fixture_id: str
    fixture_version: str
    context_key: str
    foreign_context_key: str
    boundary: str
    sources: tuple[CohortBetaFrontierSource, ...]
    records: tuple[CohortBetaFrontierRecord, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    content_address: str = ""

    def __post_init__(self) -> None:
        require_non_empty(self.fixture_id, "fixture_id")
        require_non_empty(self.fixture_version, "fixture_version")
        require_non_empty(self.context_key, "context_key")
        require_non_empty(self.foreign_context_key, "foreign_context_key")
        require_non_empty(self.boundary, "boundary")
        if len(self.records) != 16:
            raise ValueError("C05-C08 fixture must contain sixteen operation paths")
        if {item.operation for item in self.records} != {"C05", "C06", "C07", "C08"}:
            raise ValueError("fixture must cover C05, C06, C07, and C08")

    @property
    def operations(self) -> tuple[str, ...]:
        return tuple(sorted({item.operation for item in self.records}))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierDataAudit:
    """Boundary audit for source closure, pseudonymous rows, and context paths."""

    fixture_id: str
    source_count: int
    record_count: int
    operation_counts: Mapping[str, int]
    control_counts: Mapping[str, int]
    foreign_context_count: int
    public_source_count: int
    accepted: bool
    findings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _source(source_id: str, label: str, url: str, version: str, note: str) -> CohortBetaFrontierSource:
    body = {"source_id": source_id, "label": label, "url": url, "version": version, "retrieval_note": note}
    return CohortBetaFrontierSource(**body, content_address=content_hash(body, prefix="source"))


def _record(operation: str, record_id: str, payload: Mapping[str, Any], state: CohortBetaState, control_class: str, source_ids: tuple[str, ...], rationale: str) -> CohortBetaFrontierRecord:
    body = {"operation": operation, "record_id": record_id, "payload": payload, "expected_state": state, "control_class": control_class, "source_ids": source_ids, "rationale": rationale}
    return CohortBetaFrontierRecord(**body, content_address=content_hash(body, prefix="record"))


def _recurrence_rows(context: str, prefix: str, *, mode: str) -> dict[str, Any]:
    rows = [{"record_id": f"{prefix}-r1", "variant_id": f"{prefix}-v1", "sample_id": f"{prefix}-s1", "chromosome": "chr7", "position": 100, "context_key": context, "region_id": "reg-c05", "source_id": "gdc-aggregate", "source_version": C05_C08_FIXTURE_VERSION}, {"record_id": f"{prefix}-r2", "variant_id": f"{prefix}-v1", "sample_id": f"{prefix}-s2", "chromosome": "chr7", "position": 100, "context_key": context, "region_id": "reg-c05", "source_id": "gdc-aggregate", "source_version": C05_C08_FIXTURE_VERSION}, {"record_id": f"{prefix}-r3", "variant_id": f"{prefix}-v2", "sample_id": f"{prefix}-s2", "chromosome": "chr7", "position": 110, "context_key": context, "region_id": "reg-c05", "source_id": "icgc-aggregate", "source_version": C05_C08_FIXTURE_VERSION}]
    if mode == "absence":
        rows = [dict(rows[0], variant_id=f"{prefix}-single", position=400)]
    elif mode == "foreign":
        rows = [dict(rows[0], context_key=C05_C08_FOREIGN_CONTEXT)]
    elif mode == "partial":
        rows = [dict(rows[0], callable=False)]
    return {"observations": rows, "minimum_recurrent_samples": 2, "hotspot_window_bp": 20, "minimum_hotspot_variants": 2, "minimum_hotspot_samples": 2}


def _burden_payload(context: str, prefix: str, *, mode: str) -> dict[str, Any]:
    region_context = C05_C08_FOREIGN_CONTEXT if mode == "foreign" else context
    regions = [{"region_id": "reg-c06", "chromosome": "chr7", "start": 100, "end": 200, "callable_bases": 1000, "context_key": region_context, "source_id": "gdc-callable", "source_version": C05_C08_FIXTURE_VERSION}]
    rows = [{"record_id": f"{prefix}-r1", "variant_id": f"{prefix}-v1", "sample_id": f"{prefix}-s1", "chromosome": "chr7", "position": 120, "context_key": context, "callable": True, "source_id": "gdc-aggregate", "source_version": C05_C08_FIXTURE_VERSION}, {"record_id": f"{prefix}-r2", "variant_id": f"{prefix}-v2", "sample_id": f"{prefix}-s2", "chromosome": "chr7", "position": 150, "context_key": context, "callable": True, "source_id": "icgc-aggregate", "source_version": C05_C08_FIXTURE_VERSION}]
    if mode == "absence":
        rows = []
    elif mode == "foreign":
        rows = [dict(rows[0], context_key=C05_C08_FOREIGN_CONTEXT)]
    return {"regions": regions, "observations": rows, "background_rate": None if mode == "partial" else 0.001}


def _functional_payload(context: str, prefix: str, *, mode: str) -> dict[str, Any]:
    rows = [{"observation_id": f"{prefix}-f1", "variant_id": f"{prefix}-v1", "sample_id": f"{prefix}-s1", "feature_id": "motif-loss", "feature_class": "sequence", "support": 0.9, "direction": "loss", "context_key": context, "source_id": "encode-functional", "source_version": C05_C08_FIXTURE_VERSION}, {"observation_id": f"{prefix}-f2", "variant_id": f"{prefix}-v2", "sample_id": f"{prefix}-s2", "feature_id": "motif-loss", "feature_class": "sequence", "support": 0.8, "direction": "loss", "context_key": context, "source_id": "encode-functional", "source_version": C05_C08_FIXTURE_VERSION}, {"observation_id": f"{prefix}-c1", "variant_id": f"{prefix}-c1", "sample_id": f"{prefix}-cs1", "feature_id": "motif-loss", "feature_class": "sequence", "support": 0.2, "direction": "loss", "context_key": context, "source_id": "depmap-control", "source_version": C05_C08_FIXTURE_VERSION, "is_control": True}, {"observation_id": f"{prefix}-c2", "variant_id": f"{prefix}-c2", "sample_id": f"{prefix}-cs2", "feature_id": "motif-loss", "feature_class": "sequence", "support": 0.3, "direction": "loss", "context_key": context, "source_id": "depmap-control", "source_version": C05_C08_FIXTURE_VERSION, "is_control": True}]
    if mode == "partial":
        rows = [row for row in rows if not row.get("is_control")]
    elif mode == "foreign":
        rows = [dict(rows[0], context_key=C05_C08_FOREIGN_CONTEXT)]
    elif mode == "absence":
        rows = [row for row in rows if row.get("is_control")]
    return {"observations": rows, "minimum_observed_variants": 2, "ambiguity_margin": 0.01}


def _pathway_payload(context: str, prefix: str, *, mode: str) -> dict[str, Any]:
    rows = [{"observation_id": f"{prefix}-p1", "variant_id": f"{prefix}-v1", "sample_id": f"{prefix}-s1", "gene_id": "GENE1", "set_id": "path-c08", "set_kind": "pathway", "support": 0.9, "direction": "activated", "context_key": context, "source_id": "encode-pathway", "source_version": C05_C08_FIXTURE_VERSION}, {"observation_id": f"{prefix}-p2", "variant_id": f"{prefix}-v2", "sample_id": f"{prefix}-s2", "gene_id": "GENE2", "set_id": "path-c08", "set_kind": "pathway", "support": 0.8, "direction": "activated", "context_key": context, "source_id": "encode-pathway", "source_version": C05_C08_FIXTURE_VERSION}, {"observation_id": f"{prefix}-c1", "variant_id": f"{prefix}-c1", "sample_id": f"{prefix}-cs1", "gene_id": "GENE1", "set_id": "path-c08", "set_kind": "pathway", "support": 0.2, "direction": "activated", "context_key": context, "source_id": "depmap-control", "source_version": C05_C08_FIXTURE_VERSION, "is_control": True}, {"observation_id": f"{prefix}-c2", "variant_id": f"{prefix}-c2", "sample_id": f"{prefix}-cs2", "gene_id": "GENE2", "set_id": "path-c08", "set_kind": "pathway", "support": 0.3, "direction": "activated", "context_key": context, "source_id": "depmap-control", "source_version": C05_C08_FIXTURE_VERSION, "is_control": True}]
    if mode == "partial":
        rows = [row for row in rows if not row.get("is_control")]
    elif mode == "foreign":
        rows = [dict(rows[0], context_key=C05_C08_FOREIGN_CONTEXT)]
    elif mode == "contradictory":
        rows = [dict(rows[0], direction="repressed"), *rows[1:]]
    return {"observations": rows, "set_kind": "pathway", "minimum_genes": 2, "ambiguity_margin": 0.01}


def default_cohort_beta_frontier_fixture() -> CohortBetaFrontierFixture:
    sources = (_source("gdc-aggregate", "Genomic Data Commons aggregate portal", "https://gdc.cancer.gov/", "public-aggregate-2026", "Public portal receipt; no individual-level payload is embedded."), _source("icgc-aggregate", "ICGC Data Portal aggregate portal", "https://dcc.icgc.org/", "public-aggregate-2026", "Public portal receipt for cohort-level recurrence context."), _source("gdc-callable", "GDC callable interval context", "https://gdc.cancer.gov/", "public-aggregate-2026", "Callable-space boundary receipt."), _source("encode-functional", "ENCODE functional genomics portal", "https://www.encodeproject.org/", "public-aggregate-2026", "Functional annotation definition receipt."), _source("encode-pathway", "ENCODE regulatory annotation portal", "https://www.encodeproject.org/", "public-aggregate-2026", "Pathway and regulatory set definition receipt."), _source("depmap-control", "DepMap public portal", "https://depmap.org/portal/", "public-aggregate-2026", "Public comparator definition receipt."))
    records = (
        _record("C05", "c05-positive", _recurrence_rows(C05_C08_CONTEXT, "c05p", mode="positive"), CohortBetaState.SUPPORTED, "positive", ("gdc-aggregate", "icgc-aggregate"), "two samples share one variant and a local cluster is retained"),
        _record("C05", "c05-absence", _recurrence_rows(C05_C08_CONTEXT, "c05a", mode="absence"), CohortBetaState.ABSENT, "negative_control", ("gdc-aggregate",), "single-sample observation does not reach recurrence thresholds"),
        _record("C05", "c05-foreign", _recurrence_rows(C05_C08_FOREIGN_CONTEXT, "c05f", mode="foreign"), CohortBetaState.OUT_OF_DOMAIN, "foreign_context", ("gdc-aggregate",), "context mismatch must not be projected into the target"),
        _record("C05", "c05-partial", _recurrence_rows(C05_C08_CONTEXT, "c05x", mode="partial"), CohortBetaState.PARTIAL, "incomplete_control", ("gdc-aggregate",), "exact rows are present but callable support is absent"),
        _record("C06", "c06-positive", _burden_payload(C05_C08_CONTEXT, "c06p", mode="positive"), CohortBetaState.SUPPORTED, "positive", ("gdc-callable", "gdc-aggregate", "icgc-aggregate"), "observed distinct burden exceeds callable-space comparator"),
        _record("C06", "c06-absence", _burden_payload(C05_C08_CONTEXT, "c06a", mode="absence"), CohortBetaState.ABSENT, "negative_control", ("gdc-callable",), "zero overlapping variants remains an explicit absence"),
        _record("C06", "c06-foreign", _burden_payload(C05_C08_FOREIGN_CONTEXT, "c06f", mode="foreign"), CohortBetaState.OUT_OF_DOMAIN, "foreign_context", ("gdc-callable", "gdc-aggregate"), "region context does not match the requested context"),
        _record("C06", "c06-partial", _burden_payload(C05_C08_CONTEXT, "c06x", mode="partial"), CohortBetaState.PARTIAL, "incomplete_control", ("gdc-callable", "gdc-aggregate"), "burden is present without a comparator"),
        _record("C07", "c07-positive", _functional_payload(C05_C08_CONTEXT, "c07p", mode="positive"), CohortBetaState.SUPPORTED, "positive", ("encode-functional", "depmap-control"), "feature support is contrasted against control support"),
        _record("C07", "c07-partial", _functional_payload(C05_C08_CONTEXT, "c07x", mode="partial"), CohortBetaState.PARTIAL, "incomplete_control", ("encode-functional",), "feature support is summarized without controls"),
        _record("C07", "c07-foreign", _functional_payload(C05_C08_FOREIGN_CONTEXT, "c07f", mode="foreign"), CohortBetaState.OUT_OF_DOMAIN, "foreign_context", ("encode-functional",), "foreign context is retained as out of domain"),
        _record("C07", "c07-absence", _functional_payload(C05_C08_CONTEXT, "c07a", mode="absence"), CohortBetaState.ABSENT, "negative_control", ("depmap-control",), "controls without observed rows cannot support convergence"),
        _record("C08", "c08-positive", _pathway_payload(C05_C08_CONTEXT, "c08p", mode="positive"), CohortBetaState.SUPPORTED, "positive", ("encode-pathway", "depmap-control"), "pathway membership contrasts observed and control support"),
        _record("C08", "c08-partial", _pathway_payload(C05_C08_CONTEXT, "c08x", mode="partial"), CohortBetaState.PARTIAL, "incomplete_control", ("encode-pathway",), "set evidence lacks a comparator"),
        _record("C08", "c08-foreign", _pathway_payload(C05_C08_FOREIGN_CONTEXT, "c08f", mode="foreign"), CohortBetaState.OUT_OF_DOMAIN, "foreign_context", ("encode-pathway",), "foreign context cannot be combined with target evidence"),
        _record("C08", "c08-contradictory", _pathway_payload(C05_C08_CONTEXT, "c08c", mode="contradictory"), CohortBetaState.CONTRADICTORY, "contradictory_control", ("encode-pathway", "depmap-control"), "opposing leading directions remain visible"),
    )
    body = {"fixture_id": "cohort-beta-frontier-c05-c08", "fixture_version": C05_C08_FIXTURE_VERSION, "context_key": C05_C08_CONTEXT, "foreign_context_key": C05_C08_FOREIGN_CONTEXT, "boundary": C05_C08_BOUNDARY, "sources": sources, "records": records}
    return CohortBetaFrontierFixture(**body, metadata={"record_policy": "pseudonymous aggregate rows", "operation_count": 4}, content_address=content_hash(body, prefix="fixture"))


def audit_cohort_beta_frontier_data(fixture: CohortBetaFrontierFixture) -> CohortBetaFrontierDataAudit:
    operation_counts = {operation: sum(item.operation == operation for item in fixture.records) for operation in fixture.operations}
    control_counts = {control: sum(item.control_class == control for item in fixture.records) for control in sorted({item.control_class for item in fixture.records})}
    foreign = sum(item.control_class == "foreign_context" for item in fixture.records)
    findings = ("all rows are pseudonymous aggregate inputs", "each operation has positive and negative paths", "foreign-context rows are isolated by contract")
    accepted = len(fixture.sources) >= 4 and len(fixture.records) == 16 and foreign == 4 and all(count == 4 for count in operation_counts.values())
    body = {"fixture_id": fixture.fixture_id, "source_count": len(fixture.sources), "record_count": len(fixture.records), "operation_counts": operation_counts, "control_counts": control_counts, "foreign_context_count": foreign, "accepted": accepted}
    return CohortBetaFrontierDataAudit(fixture.fixture_id, len(fixture.sources), len(fixture.records), operation_counts, control_counts, foreign, len(fixture.sources), accepted, findings, content_hash(body, prefix="audit"))


def cohort_beta_frontier_fixture_json(fixture: CohortBetaFrontierFixture | None = None) -> str:
    import json
    return json.dumps((fixture or default_cohort_beta_frontier_fixture()).to_dict(), sort_keys=True, indent=2)


__all__ = ["C05_C08_BOUNDARY", "C05_C08_CONTEXT", "C05_C08_FIXTURE_VERSION", "C05_C08_FOREIGN_CONTEXT", "CohortBetaFrontierDataAudit", "CohortBetaFrontierFixture", "CohortBetaFrontierRecord", "CohortBetaFrontierSource", "audit_cohort_beta_frontier_data", "cohort_beta_frontier_fixture_json", "default_cohort_beta_frontier_fixture"]
