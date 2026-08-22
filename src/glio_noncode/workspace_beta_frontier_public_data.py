"""Public aggregate fixture for the Domain 15 C05-C08 projection frontier.

This module defines a compact, replayable evidence package for four scientific
workbench projections.  The payloads are serialized mappings on purpose: the
same fixture can be consumed by the Python API, the command line, a notebook,
or a future renderer without hidden runtime state.  Each record declares its
expected state and issue vocabulary so positive paths and control paths are
equally testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty

BETA_FRONTIER_FIXTURE_VERSION = "2026.08.d15-c05-c08.v1"
BETA_FRONTIER_CONTEXT_KEY = "GRCh38|glioma|adult|stem_like|core|untreated"
BETA_FRONTIER_OTHER_CONTEXT_KEY = "GRCh38|glioma|adult|bulk_like|core|untreated"
BETA_FRONTIER_EVIDENCE_BOUNDARY = "public_aggregate_non_patient"
BETA_FRONTIER_SOURCE_COUNT = 5
BETA_FRONTIER_POSITIVE_COUNT = 4
BETA_FRONTIER_CONTROL_COUNT = 12


class BetaFrontierOperation(StrEnum):
    """Projection surfaces exercised by the fixture."""

    TOPOLOGY_VIEWPORT = "topology_viewport"
    CAUSAL_CHAIN = "causal_chain"
    POSTERIOR_DECOMPOSITION = "posterior_decomposition"
    EVIDENCE_TABLE = "evidence_table"


class BetaFrontierRole(StrEnum):
    """Fixture row role used for acceptance accounting."""

    POSITIVE = "positive"
    CONTROL = "control"


@dataclass(frozen=True, slots=True)
class BetaFrontierSourceReceipt:
    """Public source receipt retained with every fixture package."""

    source_id: str
    title: str
    uri: str
    access_note: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("source_id", "title", "uri", "access_note", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.uri.startswith("https://"):
            raise ValueError("beta frontier source URI must use HTTPS")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BetaFrontierRecord:
    """One executable projection case with an expected result contract."""

    record_id: str
    operation: BetaFrontierOperation
    role: BetaFrontierRole
    context_key: str
    source_ids: tuple[str, ...]
    payload: dict[str, Any]
    expected_state: str
    expected_issue_codes: tuple[str, ...]
    notes: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("record_id", "context_key", "expected_state", "notes", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.source_ids:
            raise ValueError("beta frontier record requires source IDs")
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValueError("beta frontier record source IDs must be unique")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BetaFrontierFixture:
    """Immutable public aggregate package for the four projection surfaces."""

    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    sources: tuple[BetaFrontierSourceReceipt, ...]
    records: tuple[BetaFrontierRecord, ...]
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "fixture_id",
            "fixture_version",
            "context_key",
            "evidence_boundary",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not self.sources or not self.records:
            raise ValueError("beta frontier fixture requires sources and records")
        if len({item.record_id for item in self.records}) != len(self.records):
            raise ValueError("beta frontier fixture record IDs must be unique")

    @property
    def positive_records(self) -> tuple[BetaFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is BetaFrontierRole.POSITIVE)

    @property
    def control_records(self) -> tuple[BetaFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is BetaFrontierRole.CONTROL)

    def record_map(self) -> dict[str, BetaFrontierRecord]:
        return {item.record_id: item for item in self.records}

    def source_map(self) -> dict[str, BetaFrontierSourceReceipt]:
        return {item.source_id: item for item in self.sources}

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BetaFrontierCatalog:
    """Index of fixture records and source receipts."""

    fixture_id: str
    record_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    operations: tuple[BetaFrontierOperation, ...]
    context_key: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BetaFrontierDataCheck:
    """One deterministic fixture integrity assertion."""

    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BetaFrontierDataAudit:
    """Aggregate fixture integrity report."""

    fixture_id: str
    checks: tuple[BetaFrontierDataCheck, ...]
    accepted: bool
    failed_check_ids: tuple[str, ...]
    content_address: str

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed_count": self.passed_count,
            "failed_check_ids": list(self.failed_check_ids),
        }


def _source(source_id: str, title: str, uri: str, access_note: str) -> BetaFrontierSourceReceipt:
    body = {
        "source_id": source_id,
        "title": title,
        "uri": uri,
        "access_note": access_note,
    }
    return BetaFrontierSourceReceipt(**body, content_address=content_hash(body))


def _record(
    record_id: str,
    operation: BetaFrontierOperation,
    role: BetaFrontierRole,
    payload: dict[str, Any],
    expected_state: str,
    expected_issue_codes: tuple[str, ...],
    notes: str,
    source_ids: tuple[str, ...] | None = None,
) -> BetaFrontierRecord:
    receipts = source_ids or (
        ("topology-public", "workbench-public")
        if role is BetaFrontierRole.POSITIVE
        else ("workbench-public",)
    )
    body = {
        "record_id": record_id,
        "operation": operation,
        "role": role,
        "context_key": BETA_FRONTIER_CONTEXT_KEY,
        "source_ids": receipts,
        "payload": payload,
        "expected_state": expected_state,
        "expected_issue_codes": expected_issue_codes,
        "notes": notes,
    }
    return BetaFrontierRecord(**body, content_address=content_hash(body))


def _loop(context_key: str = BETA_FRONTIER_CONTEXT_KEY, feature_id: str = "loop-beta-1") -> dict[str, Any]:
    return {
        "feature_id": feature_id,
        "feature_kind": "loop",
        "chromosome_a": "7",
        "start_a": 100,
        "end_a": 120,
        "chromosome_b": "7",
        "start_b": 1000,
        "end_b": 1020,
        "signal": 8.5,
        "context_key": context_key,
        "source_id": "hic-public",
        "source_version": "aggregate-v2",
        "raw_hash": f"sha256:{feature_id}",
        "resolution": 10,
        "caller": "aggregate-caller",
    }


def _contact(context_key: str = BETA_FRONTIER_CONTEXT_KEY, contact_id: str = "contact-beta-1") -> dict[str, Any]:
    return {
        "contact_id": contact_id,
        "promoter_id": "GENE1",
        "target_element_id": "element-beta-1",
        "promoter_chromosome": "7",
        "promoter_start": 1000,
        "promoter_end": 1020,
        "target_chromosome": "7",
        "target_start": 100,
        "target_end": 120,
        "signal": 5.0,
        "context_key": context_key,
        "source_id": "capture-public",
        "source_version": "aggregate-v3",
        "raw_hash": f"sha256:{contact_id}",
        "resolution": 5,
        "bait_id": "bait-GENE1",
    }


def _contact_score(context_key: str = BETA_FRONTIER_CONTEXT_KEY) -> dict[str, Any]:
    return {
        "enhancer_id": "element-beta-1",
        "promoter_id": "GENE1",
        "context_key": context_key,
        "state": "supported",
        "median_signal": 5.0,
        "signal_spread": 0.4,
        "normalized_contact_score": 0.72,
        "source_ids": ["capture-public"],
        "source_versions": ["aggregate-v3"],
        "reason": "bounded aggregate contact score",
        "warnings": [],
        "content_address": "sha256:contact-score-beta-1",
    }


def _activity(context_key: str = BETA_FRONTIER_CONTEXT_KEY) -> dict[str, Any]:
    return {
        "enhancer_id": "element-beta-1",
        "promoter_id": "GENE1",
        "context_key": context_key,
        "model_id": "abc-public",
        "model_version": "1.2",
        "state": "supported",
        "contact_state": "supported",
        "activity_state": "supported",
        "contact_component": 0.72,
        "activity_component": 0.68,
        "activity_by_contact_score": 0.4896,
        "source_ids": ["capture-public", "access-public"],
        "source_versions": ["aggregate-v3", "aggregate-v1"],
        "reason": "bounded descriptive activity by contact",
        "warnings": [],
        "content_address": "sha256:activity-beta-1",
    }


def _mediator(
    mediator_kind: str,
    source_node: str,
    target_node: str,
    evidence_id: str,
    context_key: str = BETA_FRONTIER_CONTEXT_KEY,
    state: str = "supported",
    support: float | None = 0.8,
    uncertainty: float = 0.1,
) -> dict[str, Any]:
    return {
        "mediator_kind": mediator_kind,
        "source_node": source_node,
        "target_node": target_node,
        "context_key": context_key,
        "model_id": "causal-public",
        "model_version": "2.1",
        "state": state,
        "support": support,
        "uncertainty": uncertainty,
        "sensitivity": 0.7,
        "evidence_ids": [evidence_id],
        "negative_evidence_ids": [],
        "source_ids": [f"source-{evidence_id}"],
        "source_versions": ["aggregate-v1"],
        "reason": "declared exact-context mediator summary",
        "warnings": ["research summary"],
        "content_address": f"sha256:{evidence_id}",
    }


def _posterior(context_key: str = BETA_FRONTIER_CONTEXT_KEY) -> dict[str, Any]:
    return {
        "hypothesis_id": "hypothesis-beta-1",
        "state": "supported",
        "declared_prior": 0.2,
        "evidence_support": 0.75,
        "posterior_proxy": 0.652174,
        "calibration_status": "unvalidated_research_proxy",
        "uncertainty": 0.3,
        "observation_ids": ["posterior-observation-1"],
        "limitations": ["aggregate evidence", "not a clinical probability"],
        "content_address": f"sha256:posterior-{content_hash(context_key)}",
    }


def _components(context_key: str = BETA_FRONTIER_CONTEXT_KEY) -> list[dict[str, Any]]:
    return [
        {
            "component_id": "sequence",
            "label": "sequence support",
            "contribution": 0.4,
            "context_key": context_key,
            "state": "supported",
            "source_ids": ["sequence-public"],
            "observation_ids": ["sequence-observation-1"],
            "explanation": "declared sequence contribution",
        },
        {
            "component_id": "topology",
            "label": "topology support",
            "contribution": 0.35,
            "context_key": context_key,
            "state": "supported",
            "source_ids": ["capture-public"],
            "observation_ids": ["topology-observation-1"],
            "explanation": "declared topology contribution",
        },
    ]


def _workspace(context_key: str = BETA_FRONTIER_CONTEXT_KEY) -> dict[str, Any]:
    return {
        "workspace_id": "workspace-beta-public",
        "kind": "case",
        "context_key": context_key,
        "state": "partial",
        "warnings": ["aggregate workspace retains unresolved rows"],
        "records": [
            {
                "record_id": "evidence-beta-sequence",
                "record_type": "evidence",
                "label": "sequence supports element",
                "context_key": context_key,
                "state": "supported",
                "source_ids": ["sequence-public"],
                "tags": ["sequence", "tier-1"],
                "fields": {"channel": "sequence", "tier": "tier-1", "confidence": 0.91},
                "searchable_text": "sequence element",
            },
            {
                "record_id": "evidence-beta-topology",
                "record_type": "evidence",
                "label": "topology remains partial",
                "context_key": context_key,
                "state": "partial",
                "source_ids": ["capture-public"],
                "tags": ["topology", "tier-2"],
                "fields": {"channel": "topology", "tier": "tier-2", "confidence": 0.54},
                "searchable_text": "topology promoter contact",
            },
            {
                "record_id": "evidence-beta-causal",
                "record_type": "evidence",
                "label": "causal chain summary",
                "context_key": context_key,
                "state": "supported",
                "source_ids": ["causal-public"],
                "tags": ["causal", "tier-1"],
                "fields": {"channel": "causal", "tier": "tier-1", "confidence": 0.63},
                "searchable_text": "mediator chain",
            },
            {
                "record_id": "summary-beta-not-evidence",
                "record_type": "summary",
                "label": "workspace summary",
                "context_key": context_key,
                "state": "partial",
                "source_ids": ["workbench-public"],
                "tags": ["summary", "tier-3"],
                "fields": {"channel": "summary", "tier": "tier-3", "confidence": 0.2},
                "searchable_text": "workspace summary",
            },
        ],
        "sections": [
            {
                "section_id": "evidence",
                "title": "Evidence",
                "record_types": ["evidence"],
                "order": 0,
                "accessible_label": "Evidence",
                "description": "Evidence records",
            },
            {
                "section_id": "summary",
                "title": "Summary",
                "record_types": ["summary"],
                "order": 1,
                "accessible_label": "Summary",
                "description": "Context summary",
            },
        ],
    }


def _topology_payload(context_key: str = BETA_FRONTIER_CONTEXT_KEY) -> dict[str, Any]:
    return {
        "context_key": context_key,
        "loops": [_loop(context_key)],
        "contacts": [_contact(context_key)],
        "contact_scores": [_contact_score(context_key)],
        "activity_results": [_activity(context_key)],
        "focus_chromosome": "7",
        "focus_start": 90,
        "focus_end": 1100,
        "max_nodes": 50,
        "max_edges": 50,
    }


def _causal_payload(context_key: str = BETA_FRONTIER_CONTEXT_KEY) -> dict[str, Any]:
    return {
        "context_key": context_key,
        "results": [
            _mediator("sequence_to_element", "variant-beta-1", "element-beta-1", "causal-1", context_key),
            _mediator("element_to_gene", "element-beta-1", "GENE1", "causal-2", context_key),
            _mediator("gene_to_state", "GENE1", "state-beta-1", "causal-3", context_key),
            _mediator("element_to_gene", "element-beta-1", "GENE2", "causal-4", context_key, support=0.4, uncertainty=0.4),
        ],
    }


def _posterior_payload(context_key: str = BETA_FRONTIER_CONTEXT_KEY) -> dict[str, Any]:
    return {"context_key": context_key, "posterior": _posterior(context_key), "components": _components(context_key)}


def _table_payload(context_key: str = BETA_FRONTIER_CONTEXT_KEY) -> dict[str, Any]:
    return {
        "context_key": context_key,
        "workspace": _workspace(context_key),
        "filter": {
            "context_key": context_key,
            "channels": ["sequence", "topology", "causal"],
            "tiers": ["tier-1", "tier-2"],
            "min_confidence": 0.5,
            "offset": 0,
            "limit": 10,
        },
    }


def default_beta_frontier_fixture() -> BetaFrontierFixture:
    """Return the deterministic 16-row C05-C08 aggregate fixture."""

    sources = (
        _source("sequence-public", "Public sequence aggregate", "https://example.org/sequence", "aggregate sequence receipt"),
        _source("hic-public", "Public loop aggregate", "https://example.org/loops", "aggregate loop receipt"),
        _source("capture-public", "Public promoter capture aggregate", "https://example.org/capture", "aggregate contact receipt"),
        _source("causal-public", "Public mediator summary", "https://example.org/mediators", "aggregate mediator receipt"),
        _source("workbench-public", "Public workbench manifest", "https://example.org/workbench", "fixture manifest receipt"),
    )
    records = (
        _record("topology-positive", BetaFrontierOperation.TOPOLOGY_VIEWPORT, BetaFrontierRole.POSITIVE, _topology_payload(), "supported", (), "exact-context topology contains loop, contact, score, and activity edges"),
        _record("topology-foreign-context", BetaFrontierOperation.TOPOLOGY_VIEWPORT, BetaFrontierRole.CONTROL, {**_topology_payload(), "loops": [_loop(BETA_FRONTIER_OTHER_CONTEXT_KEY)], "contacts": [_contact(BETA_FRONTIER_OTHER_CONTEXT_KEY)], "contact_scores": [_contact_score(BETA_FRONTIER_OTHER_CONTEXT_KEY)], "activity_results": [_activity(BETA_FRONTIER_OTHER_CONTEXT_KEY)]}, "out_of_domain", ("context_mismatch",), "foreign topology context is withheld"),
        _record("topology-invalid-focus", BetaFrontierOperation.TOPOLOGY_VIEWPORT, BetaFrontierRole.CONTROL, {**_topology_payload(), "focus_start": 0}, "invalid", ("invalid_projection_input",), "invalid focus interval is rejected"),
        _record("topology-empty", BetaFrontierOperation.TOPOLOGY_VIEWPORT, BetaFrontierRole.CONTROL, {**_topology_payload(), "loops": [], "contacts": [], "contact_scores": [], "activity_results": []}, "absent", ("no_topology_observations",), "empty topology remains absent"),
        _record("causal-positive", BetaFrontierOperation.CAUSAL_CHAIN, BetaFrontierRole.POSITIVE, _causal_payload(), "complete", (), "all required mediator kinds and an alternative path remain visible"),
        _record("causal-foreign-context", BetaFrontierOperation.CAUSAL_CHAIN, BetaFrontierRole.CONTROL, {"context_key": BETA_FRONTIER_CONTEXT_KEY, "results": [_mediator("sequence_to_element", "variant-beta-1", "element-beta-1", "foreign-1", BETA_FRONTIER_OTHER_CONTEXT_KEY), _mediator("element_to_gene", "element-beta-1", "GENE1", "foreign-2", BETA_FRONTIER_OTHER_CONTEXT_KEY), _mediator("gene_to_state", "GENE1", "state-beta-1", "foreign-3", BETA_FRONTIER_OTHER_CONTEXT_KEY)]}, "out_of_domain", ("context_mismatch",), "foreign chain context is withheld"),
        _record("causal-missing-mediator", BetaFrontierOperation.CAUSAL_CHAIN, BetaFrontierRole.CONTROL, {"context_key": BETA_FRONTIER_CONTEXT_KEY, "results": _causal_payload()["results"][:2]}, "incomplete", ("missing_mediator",), "missing required mediator remains explicit"),
        _record("causal-contradiction", BetaFrontierOperation.CAUSAL_CHAIN, BetaFrontierRole.CONTROL, {"context_key": BETA_FRONTIER_CONTEXT_KEY, "results": [_mediator("sequence_to_element", "variant-beta-1", "element-beta-1", "causal-negative-1", state="contradictory", support=None, uncertainty=1.0), _mediator("element_to_gene", "element-beta-1", "GENE1", "causal-negative-2", state="contradictory", support=None, uncertainty=1.0), _mediator("gene_to_state", "GENE1", "state-beta-1", "causal-negative-3", state="contradictory", support=None, uncertainty=1.0)]}, "contradictory", ("contradictory_mediator",), "contradictory mediator state is not collapsed"),
        _record("posterior-positive", BetaFrontierOperation.POSTERIOR_DECOMPOSITION, BetaFrontierRole.POSITIVE, _posterior_payload(), "supported", (), "declared support reconciles exactly to two components"),
        _record("posterior-foreign-component", BetaFrontierOperation.POSTERIOR_DECOMPOSITION, BetaFrontierRole.CONTROL, {**_posterior_payload(), "components": [{"component_id": "foreign", "label": "foreign", "contribution": 0.65, "context_key": BETA_FRONTIER_OTHER_CONTEXT_KEY}, {"component_id": "local", "label": "local", "contribution": 0.1, "context_key": BETA_FRONTIER_CONTEXT_KEY}]}, "partial", ("foreign_component", "unreconciled_components"), "foreign component is withheld and residual remains"),
        _record("posterior-unreconciled", BetaFrontierOperation.POSTERIOR_DECOMPOSITION, BetaFrontierRole.CONTROL, {**_posterior_payload(), "components": [{"component_id": "local", "label": "local", "contribution": 0.2, "context_key": BETA_FRONTIER_CONTEXT_KEY}]}, "partial", ("unreconciled_components",), "declared support and visible components do not reconcile"),
        _record("posterior-no-support", BetaFrontierOperation.POSTERIOR_DECOMPOSITION, BetaFrontierRole.CONTROL, {"context_key": BETA_FRONTIER_CONTEXT_KEY, "posterior": {**_posterior(), "evidence_support": None, "posterior_proxy": None, "state": "abstained"}, "components": []}, "abstained", ("missing_support",), "missing support forces abstention"),
        _record("table-positive", BetaFrontierOperation.EVIDENCE_TABLE, BetaFrontierRole.POSITIVE, _table_payload(), "partial", (), "filtered evidence table retains supported and partial states"),
        _record("table-foreign-context", BetaFrontierOperation.EVIDENCE_TABLE, BetaFrontierRole.CONTROL, {**_table_payload(), "filter": {"context_key": BETA_FRONTIER_OTHER_CONTEXT_KEY}}, "out_of_domain", ("context_mismatch",), "foreign table context returns no rows"),
        _record("table-no-match", BetaFrontierOperation.EVIDENCE_TABLE, BetaFrontierRole.CONTROL, {**_table_payload(), "filter": {"context_key": BETA_FRONTIER_CONTEXT_KEY, "channels": ["missing-channel"]}}, "absent", ("no_matching_rows",), "dimension filter can produce an empty table"),
        _record("table-pagination", BetaFrontierOperation.EVIDENCE_TABLE, BetaFrontierRole.CONTROL, {**_table_payload(), "filter": {"context_key": BETA_FRONTIER_CONTEXT_KEY, "channels": ["sequence", "topology"], "offset": 1, "limit": 1}}, "partial", ("pagination_applied",), "pagination retains total match count"),
    )
    body = {
        "fixture_id": "workspace-beta-frontier-public",
        "fixture_version": BETA_FRONTIER_FIXTURE_VERSION,
        "context_key": BETA_FRONTIER_CONTEXT_KEY,
        "evidence_boundary": BETA_FRONTIER_EVIDENCE_BOUNDARY,
        "sources": sources,
        "records": records,
    }
    return BetaFrontierFixture(**body, content_address=content_hash(body))


def build_beta_frontier_catalog(fixture: BetaFrontierFixture | None = None) -> BetaFrontierCatalog:
    fixture = fixture or default_beta_frontier_fixture()
    body = {
        "fixture_id": fixture.fixture_id,
        "record_ids": tuple(item.record_id for item in fixture.records),
        "source_ids": tuple(item.source_id for item in fixture.sources),
        "operations": tuple(sorted({item.operation for item in fixture.records}, key=lambda value: value.value)),
        "context_key": fixture.context_key,
    }
    return BetaFrontierCatalog(**body, content_address=content_hash(body))


def audit_beta_frontier_data(fixture: BetaFrontierFixture | None = None) -> BetaFrontierDataAudit:
    fixture = fixture or default_beta_frontier_fixture()

    def check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> BetaFrontierDataCheck:
        body = {"check_id": check_id, "passed": passed, "observed": observed, "required": required, "detail": detail}
        return BetaFrontierDataCheck(**body, content_address=content_hash(body))

    checks = (
        check("fixture:source-count", len(fixture.sources) == 5, len(fixture.sources), 5, "five public receipts are present"),
        check("fixture:record-count", len(fixture.records) == 16, len(fixture.records), 16, "sixteen projection cases are present"),
        check("fixture:positive-count", len(fixture.positive_records) == 4, len(fixture.positive_records), 4, "one positive path per surface"),
        check("fixture:control-count", len(fixture.control_records) == 12, len(fixture.control_records), 12, "three controls per surface"),
        check("fixture:operation-coverage", set(item.operation for item in fixture.records) == set(BetaFrontierOperation), tuple(sorted({item.operation.value for item in fixture.records})), tuple(item.value for item in BetaFrontierOperation), "all four projection surfaces are covered"),
        check("fixture:source-uris", all(item.uri.startswith("https://") for item in fixture.sources), True, True, "source receipts use HTTPS"),
        check("fixture:boundary", fixture.evidence_boundary == BETA_FRONTIER_EVIDENCE_BOUNDARY, fixture.evidence_boundary, BETA_FRONTIER_EVIDENCE_BOUNDARY, "boundary is public aggregate data"),
        check("fixture:context", all(item.context_key == fixture.context_key for item in fixture.records), True, True, "record contract context is exact"),
        check("fixture:addresses", all(item.content_address.startswith("sha256:") for item in fixture.records), True, True, "records are content addressed"),
    )
    failed = tuple(item.check_id for item in checks if not item.passed)
    body = {"fixture_id": fixture.fixture_id, "checks": checks, "accepted": not failed, "failed_check_ids": failed}
    return BetaFrontierDataAudit(**body, content_address=content_hash(body))


def load_beta_frontier_fixture(path: str | Path | None = None) -> BetaFrontierFixture:
    """Load the default package; external fixture loading remains opt-in."""

    if path is None:
        return default_beta_frontier_fixture()
    raise ValueError(f"external beta frontier fixture loading is not enabled: {path}")


__all__ = [
    "BETA_FRONTIER_CONTEXT_KEY",
    "BETA_FRONTIER_CONTROL_COUNT",
    "BETA_FRONTIER_EVIDENCE_BOUNDARY",
    "BETA_FRONTIER_FIXTURE_VERSION",
    "BETA_FRONTIER_OTHER_CONTEXT_KEY",
    "BETA_FRONTIER_POSITIVE_COUNT",
    "BETA_FRONTIER_SOURCE_COUNT",
    "BetaFrontierCatalog",
    "BetaFrontierDataAudit",
    "BetaFrontierDataCheck",
    "BetaFrontierFixture",
    "BetaFrontierOperation",
    "BetaFrontierRecord",
    "BetaFrontierRole",
    "BetaFrontierSourceReceipt",
    "audit_beta_frontier_data",
    "build_beta_frontier_catalog",
    "default_beta_frontier_fixture",
    "load_beta_frontier_fixture",
]
