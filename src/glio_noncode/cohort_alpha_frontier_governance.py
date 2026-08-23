"""Shared governance planes for the C09-C12 alpha release."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .cohort_alpha import CohortAlphaState
from .cohort_alpha_frontier_contracts import CohortAlphaFrontierContractRegistry
from .cohort_alpha_frontier_fixture_eval import CohortAlphaFrontierEvaluation, evaluate_cohort_alpha_frontier_fixture
from .cohort_alpha_frontier_public_data import CohortAlphaFrontierFixture
from .cohort_alpha_frontier_schema import CohortAlphaFrontierSchemaReport
from .serialization import content_hash, jsonable


class CohortAlphaFrontierDisposition(StrEnum):
    PUBLISH = "publish"
    REVIEW = "review"
    QUARANTINE = "quarantine"


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierOperationMetric:
    operation: str
    total: int
    accepted: int
    supported: int
    partial: int
    abstained: int
    out_of_domain: int
    ambiguous: int
    acceptance_percent: float
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierMetrics:
    total_rows: int
    accepted_rows: int
    supported_rows: int
    control_rows: int
    mismatch_rows: int
    acceptance_percent: float
    operations: tuple[CohortAlphaFrontierOperationMetric, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def measure_cohort_alpha_frontier(evaluation: CohortAlphaFrontierEvaluation) -> CohortAlphaFrontierMetrics:
    metrics = []
    for operation in sorted({item.operation for item in evaluation.rows}):
        rows = tuple(item for item in evaluation.rows if item.operation == operation)
        counts = {state.value: sum(item.observed_state is state for item in rows) for state in CohortAlphaState}
        accepted = sum(item.accepted for item in rows)
        body = {"operation": operation, "rows": rows, "accepted": accepted, "counts": counts}
        metrics.append(CohortAlphaFrontierOperationMetric(operation, len(rows), accepted, counts["supported"], counts["partial"], counts["abstained"], counts["out_of_domain"], counts["ambiguous"], round(100 * accepted / max(1, len(rows)), 2), content_hash(body, prefix="alpha-metric")))
    values = tuple(metrics)
    accepted_rows = sum(item.accepted for item in evaluation.rows)
    return CohortAlphaFrontierMetrics(len(evaluation.rows), accepted_rows, evaluation.supported_count, evaluation.control_count, evaluation.mismatch_count, round(100 * accepted_rows / max(1, len(evaluation.rows)), 2), values, content_hash({"rows": values, "accepted_rows": accepted_rows}, prefix="alpha-metrics"))


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierLineageEdge:
    parent: str
    child: str
    relation: str
    operation: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierLineage:
    nodes: tuple[str, ...]
    edges: tuple[CohortAlphaFrontierLineageEdge, ...]
    closed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_lineage(fixture: CohortAlphaFrontierFixture, evaluation: CohortAlphaFrontierEvaluation) -> CohortAlphaFrontierLineage:
    nodes = {fixture.fixture_id, *[source.source_id for source in fixture.sources]}
    edges = []
    for record in fixture.records:
        nodes.update((record.record_id, f"result:{record.record_id}"))
        for source_id in record.source_ids:
            nodes.add(source_id)
            body = {"parent": source_id, "child": record.record_id, "operation": record.operation, "relation": "source_to_input"}
            edges.append(CohortAlphaFrontierLineageEdge(source_id, record.record_id, "source_to_input", record.operation, content_hash(body, prefix="alpha-lineage-edge")))
        body = {"parent": record.record_id, "child": f"result:{record.record_id}", "operation": record.operation, "relation": "input_to_result"}
        edges.append(CohortAlphaFrontierLineageEdge(record.record_id, f"result:{record.record_id}", "input_to_result", record.operation, content_hash(body, prefix="alpha-lineage-edge")))
    closed = len(evaluation.rows) == len(fixture.records) and len(edges) >= 32
    return CohortAlphaFrontierLineage(tuple(sorted(nodes)), tuple(edges), closed, content_hash({"nodes": sorted(nodes), "edges": edges, "closed": closed}, prefix="alpha-lineage"))


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierProvenance:
    source_ids: tuple[str, ...]
    source_addresses: tuple[str, ...]
    result_addresses: tuple[str, ...]
    closed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_provenance(fixture: CohortAlphaFrontierFixture, evaluation: CohortAlphaFrontierEvaluation) -> CohortAlphaFrontierProvenance:
    source_ids = tuple(sorted(source.source_id for source in fixture.sources))
    addresses = tuple(source.content_address for source in fixture.sources)
    results = tuple(row.content_address for row in evaluation.rows)
    closed = len(source_ids) == 6 and len(addresses) == 6 and len(results) == 16
    return CohortAlphaFrontierProvenance(source_ids, addresses, results, closed, content_hash({"source_ids": source_ids, "addresses": addresses, "results": results}, prefix="alpha-provenance"))


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierPolicyDecision:
    record_id: str
    operation: str
    state: CohortAlphaState
    disposition: CohortAlphaFrontierDisposition
    rationale: str
    prohibited_claims: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierPolicy:
    decisions: tuple[CohortAlphaFrontierPolicyDecision, ...]
    publishable_count: int
    review_count: int
    quarantine_count: int
    content_address: str

    def for_record(self, record_id: str) -> CohortAlphaFrontierPolicyDecision:
        return next(item for item in self.decisions if item.record_id == record_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def materialize_cohort_alpha_frontier_policy(evaluation: CohortAlphaFrontierEvaluation, contracts: CohortAlphaFrontierContractRegistry) -> CohortAlphaFrontierPolicy:
    decisions = []
    for row in evaluation.rows:
        if row.expected_state is CohortAlphaState.SUPPORTED and row.observed_state is CohortAlphaState.SUPPORTED and row.accepted:
            disposition = CohortAlphaFrontierDisposition.PUBLISH
            rationale = "supported exact-context alpha result passed fixture reconciliation"
        elif row.observed_state in {CohortAlphaState.PARTIAL, CohortAlphaState.AMBIGUOUS}:
            disposition = CohortAlphaFrontierDisposition.REVIEW
            rationale = "missing phase, comparator, or direction agreement requires review"
        else:
            disposition = CohortAlphaFrontierDisposition.QUARANTINE
            rationale = "abstained or foreign-context result is excluded from target publication"
        prohibited = contracts.by_operation(row.operation).prohibited_claims
        body = {"record_id": row.record_id, "operation": row.operation, "state": row.observed_state, "disposition": disposition, "rationale": rationale, "prohibited": prohibited}
        decisions.append(CohortAlphaFrontierPolicyDecision(row.record_id, row.operation, row.observed_state, disposition, rationale, prohibited, content_hash(body, prefix="alpha-policy")))
    values = tuple(decisions)
    return CohortAlphaFrontierPolicy(values, sum(item.disposition is CohortAlphaFrontierDisposition.PUBLISH for item in values), sum(item.disposition is CohortAlphaFrontierDisposition.REVIEW for item in values), sum(item.disposition is CohortAlphaFrontierDisposition.QUARANTINE for item in values), content_hash(values, prefix="alpha-policy-set"))


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierReconciliationItem:
    record_id: str
    operation: str
    expected_state: str
    observed_state: str
    matched: bool
    disposition: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierReconciliation:
    items: tuple[CohortAlphaFrontierReconciliationItem, ...]
    reconciled: bool
    mismatch_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def reconcile_cohort_alpha_frontier(fixture: CohortAlphaFrontierFixture, evaluation: CohortAlphaFrontierEvaluation, policy: CohortAlphaFrontierPolicy) -> CohortAlphaFrontierReconciliation:
    items = []
    for row in evaluation.rows:
        decision = policy.for_record(row.record_id)
        matched = row.expected_state is row.observed_state
        body = {"record_id": row.record_id, "expected": row.expected_state, "observed": row.observed_state, "matched": matched, "disposition": decision.disposition}
        items.append(CohortAlphaFrontierReconciliationItem(row.record_id, row.operation, row.expected_state.value, row.observed_state.value, matched, decision.disposition.value, content_hash(body, prefix="alpha-reconciliation-item")))
    values = tuple(items)
    return CohortAlphaFrontierReconciliation(values, len(values) == len(fixture.records) and all(item.matched for item in values), sum(not item.matched for item in values), content_hash(values, prefix="alpha-reconciliation"))


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierReviewItem:
    record_id: str
    operation: str
    priority: int
    reason: str
    required_evidence: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierReviewQueue:
    items: tuple[CohortAlphaFrontierReviewItem, ...]
    open_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_review_queue(evaluation: CohortAlphaFrontierEvaluation, policy: CohortAlphaFrontierPolicy) -> CohortAlphaFrontierReviewQueue:
    items = []
    for row in evaluation.rows:
        decision = policy.for_record(row.record_id)
        if decision.disposition is CohortAlphaFrontierDisposition.PUBLISH:
            continue
        priority = 1 if decision.disposition is CohortAlphaFrontierDisposition.QUARANTINE else 2
        evidence = ("exact context receipt", "phase or comparator receipt") if row.operation in {"C09", "C10"} else ("exposure phase receipt", "cohort concordance receipt")
        items.append(CohortAlphaFrontierReviewItem(row.record_id, row.operation, priority, decision.rationale, evidence, content_hash({"record_id": row.record_id, "operation": row.operation, "priority": priority}, prefix="alpha-review-item")))
    values = tuple(sorted(items, key=lambda item: (item.priority, item.operation, item.record_id)))
    return CohortAlphaFrontierReviewQueue(values, len(values), all(item.priority in {1, 2} for item in values), content_hash(values, prefix="alpha-review"))


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierGateCheck:
    check_id: str
    accepted: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierQualityGate:
    checks: tuple[CohortAlphaFrontierGateCheck, ...]
    accepted: bool
    blocking_failures: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_cohort_alpha_frontier_quality(fixture: CohortAlphaFrontierFixture, evaluation: CohortAlphaFrontierEvaluation, contracts: CohortAlphaFrontierContractRegistry, schema: CohortAlphaFrontierSchemaReport, lineage: CohortAlphaFrontierLineage, reconciliation: CohortAlphaFrontierReconciliation) -> CohortAlphaFrontierQualityGate:
    checks_raw = (("fixture-cardinality", len(fixture.records) == 16, "sixteen bounded paths"), ("evaluation", evaluation.accepted, "all expected states observed"), ("contracts", {item.operation for item in contracts.contracts} == {"C09", "C10", "C11", "C12"}, "four operation contracts"), ("schema", schema.accepted, "field schema accepted"), ("lineage", lineage.closed, "source and result lineage closed"), ("reconciliation", reconciliation.reconciled, "expected and observed states match"))
    checks = tuple(CohortAlphaFrontierGateCheck(check_id, accepted, detail, content_hash({"check_id": check_id, "accepted": accepted, "detail": detail}, prefix="alpha-gate-check")) for check_id, accepted, detail in checks_raw)
    return CohortAlphaFrontierQualityGate(checks, all(item.accepted for item in checks), sum(not item.accepted for item in checks), content_hash(checks, prefix="alpha-quality"))


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierReplayReceipt:
    replay_id: str
    original_address: str
    replay_address: str
    deterministic: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def replay_cohort_alpha_frontier(fixture: CohortAlphaFrontierFixture, replay_id: str = "cohort-alpha-frontier-replay") -> CohortAlphaFrontierReplayReceipt:
    first = evaluate_cohort_alpha_frontier_fixture(fixture)
    second = evaluate_cohort_alpha_frontier_fixture(fixture)
    deterministic = first.content_address == second.content_address and first.rows == second.rows
    body = {"replay_id": replay_id, "original": first.content_address, "replay": second.content_address, "deterministic": deterministic}
    return CohortAlphaFrontierReplayReceipt(replay_id, first.content_address, second.content_address, deterministic, content_hash(body, prefix="alpha-replay"))


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierReleaseBundle:
    bundle_id: str
    fixture_address: str
    evaluation_address: str
    metrics_address: str
    policy_address: str
    reconciliation_address: str
    quality_address: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def assemble_cohort_alpha_frontier_bundle(fixture: CohortAlphaFrontierFixture, evaluation: CohortAlphaFrontierEvaluation, metrics: CohortAlphaFrontierMetrics, policy: CohortAlphaFrontierPolicy, reconciliation: CohortAlphaFrontierReconciliation, quality: CohortAlphaFrontierQualityGate) -> CohortAlphaFrontierReleaseBundle:
    body = {"bundle_id": "cohort-alpha-frontier-c09-c12-bundle", "fixture": fixture.content_address, "evaluation": evaluation.content_address, "metrics": metrics.content_address, "policy": policy.content_address, "reconciliation": reconciliation.content_address, "quality": quality.content_address, "accepted": quality.accepted and reconciliation.reconciled}
    return CohortAlphaFrontierReleaseBundle(body["bundle_id"], fixture.content_address, evaluation.content_address, metrics.content_address, policy.content_address, reconciliation.content_address, quality.content_address, body["accepted"], content_hash(body, prefix="alpha-bundle"))


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierReleaseManifest:
    release_id: str
    ready: bool
    claim_ceiling: str
    checks: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_release_manifest(bundle: CohortAlphaFrontierReleaseBundle, quality: CohortAlphaFrontierQualityGate, replay: CohortAlphaFrontierReplayReceipt) -> CohortAlphaFrontierReleaseManifest:
    checks = ("bundle" if bundle.accepted else "bundle_failed", "quality" if quality.accepted else "quality_failed", "replay" if replay.deterministic else "replay_failed")
    ready = all(item.endswith("_failed") is False for item in checks)
    body = {"release_id": "cohort-alpha-frontier-c09-c12-release", "ready": ready, "checks": checks, "claim_ceiling": "descriptive clonality, phase, treatment-selection, and replication summaries only"}
    return CohortAlphaFrontierReleaseManifest(body["release_id"], ready, body["claim_ceiling"], checks, content_hash(body, prefix="alpha-release"))


__all__ = ["CohortAlphaFrontierDisposition", "CohortAlphaFrontierGateCheck", "CohortAlphaFrontierLineage", "CohortAlphaFrontierLineageEdge", "CohortAlphaFrontierMetrics", "CohortAlphaFrontierOperationMetric", "CohortAlphaFrontierPolicy", "CohortAlphaFrontierPolicyDecision", "CohortAlphaFrontierProvenance", "CohortAlphaFrontierQualityGate", "CohortAlphaFrontierReconciliation", "CohortAlphaFrontierReconciliationItem", "CohortAlphaFrontierReleaseBundle", "CohortAlphaFrontierReleaseManifest", "CohortAlphaFrontierReplayReceipt", "CohortAlphaFrontierReviewItem", "CohortAlphaFrontierReviewQueue", "assemble_cohort_alpha_frontier_bundle", "build_cohort_alpha_frontier_lineage", "build_cohort_alpha_frontier_provenance", "build_cohort_alpha_frontier_release_manifest", "build_cohort_alpha_frontier_review_queue", "evaluate_cohort_alpha_frontier_quality", "materialize_cohort_alpha_frontier_policy", "measure_cohort_alpha_frontier", "reconcile_cohort_alpha_frontier", "replay_cohort_alpha_frontier"]
