"""Public aggregate fixture for Domain 14 C05-C12.

The fixture is deliberately synthetic and non-patient.  Each capability has
one positive record and three negative controls: an unresolved boundary, a
context or input failure, and an empty or contradictory case.  Source URIs
are public HTTPS receipts and are never treated as patient evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .lifecycle_beta_frontier_contracts import (
    LIFECYCLE_BETA_FRONTIER_BOUNDARY,
    LIFECYCLE_BETA_FRONTIER_CONTEXT_KEY,
    LIFECYCLE_BETA_FRONTIER_VERSION,
    LifecycleBetaFrontierFixture,
    LifecycleBetaFrontierOperation,
    LifecycleBetaFrontierRecord,
    LifecycleBetaFrontierRole,
    LifecycleBetaFrontierSourceReceipt,
    LifecycleBetaFrontierState,
)
from .serialization import content_hash, jsonable


LIFECYCLE_BETA_FRONTIER_SOURCE_COUNT = 9
LIFECYCLE_BETA_FRONTIER_POSITIVE_COUNT = 8
LIFECYCLE_BETA_FRONTIER_CONTROL_COUNT = 24


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierDataCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierDataAudit:
    fixture_id: str
    checks: tuple[LifecycleBetaFrontierDataCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _source(source_id: str, title: str) -> LifecycleBetaFrontierSourceReceipt:
    body = {
        "source_id": source_id,
        "title": title,
        "uri": f"https://example.org/glio-noncode/lifecycle/{source_id}",
        "access_note": "public aggregate receipt; no patient-level records",
    }
    return LifecycleBetaFrontierSourceReceipt(**body, content_address=content_hash(body))


def _payload(operation: LifecycleBetaFrontierOperation, kind: str, context: str) -> dict[str, Any]:
    """Build small, explicit payloads that exercise each boundary."""

    if operation is LifecycleBetaFrontierOperation.TIER_ADJUDICATION:
        observations = [{
            "observation_id": "tier-positive",
            "claim_id": "claim-tier-1",
            "edge_id": "edge-tier-1",
            "context_key": context,
            "tier": "direct_perturbation",
            "direction": "supports",
            "support": 0.92,
            "confidence": 0.88,
            "source_id": "src-tier",
            "source_version": "v1",
            "raw_hash": "sha256:tier-positive",
            "rationale": "declared aggregate perturbation observation",
        }]
        if kind == "contradiction":
            observations.append({**observations[0], "observation_id": "tier-against", "direction": "against"})
        if kind == "foreign":
            observations[0]["context_key"] = "GRCh38|glioma|pediatric|stem_like|core|untreated"
        if kind == "unclassified":
            observations[0]["tier"] = "unclassified"
        return {"observations": observations}
    if operation is LifecycleBetaFrontierOperation.PROVENANCE_LINEAGE:
        graph = {
            "graph_id": "lineage-graph",
            "version": 3,
            "claims": [
                {"claim_id": "claim-current", "context_key": context, "active": True, "parents": ["claim-parent"], "supersedes": "claim-parent", "source_ids": ["src-lineage"]},
                {"claim_id": "claim-parent", "context_key": context, "active": False, "parents": [], "source_ids": ["src-lineage"]},
            ],
            "citations": [{"citation_id": "citation-lineage", "source_id": "src-lineage", "version": "v1"}],
        }
        if kind == "missing_parent":
            graph["claims"][0]["parents"] = ["claim-missing"]
        if kind == "foreign":
            graph["claims"][0]["context_key"] = "GRCh38|glioma|pediatric|stem_like|core|untreated"
        if kind == "empty":
            graph["claims"] = []
        return {"graph": graph, "claim_id": "claim-current"}
    if operation is LifecycleBetaFrontierOperation.UNCERTAINTY_LEDGER:
        entries = [
            {"observation_id": "uncertainty-measurement", "claim_id": "claim-uncertainty", "edge_id": "edge-uncertainty", "context_key": context, "dimension": "measurement", "value": 0.22, "source_id": "src-uncertainty", "source_version": "v1", "raw_hash": "sha256:uncertainty-1", "rationale": "replicate spread"},
            {"observation_id": "uncertainty-transport", "claim_id": "claim-uncertainty", "edge_id": "edge-uncertainty", "context_key": context, "dimension": "transport", "value": 0.41, "source_id": "src-uncertainty", "source_version": "v1", "raw_hash": "sha256:uncertainty-2", "rationale": "context transfer gap"},
        ]
        if kind == "foreign":
            entries[0]["context_key"] = "GRCh38|glioma|pediatric|stem_like|core|untreated"
        if kind == "empty":
            entries = []
        if kind == "invalid":
            entries[0]["value"] = 1.4
        return {"entries": entries}
    if operation is LifecycleBetaFrontierOperation.REVIEW_ROUTING:
        claims = [
            {"claim_id": "route-claim-1", "edge_id": "route-edge-1", "context_key": context, "claim_type": "functional", "state": "supported", "uncertainty": 0.72, "contradictory": False},
            {"claim_id": "route-claim-2", "edge_id": "route-edge-2", "context_key": context, "claim_type": "sequence", "state": "contradictory", "uncertainty": 0.91, "contradictory": True},
        ]
        if kind == "foreign":
            claims[0]["context_key"] = "GRCh38|glioma|pediatric|stem_like|core|untreated"
        if kind == "empty":
            claims = []
        return {"graph_id": "routing-graph", "graph_version": 2, "claims": claims, "required_roles": ["domain_expert", "data_provenance"]}
    if operation is LifecycleBetaFrontierOperation.BLINDED_ADJUDICATION:
        observations = [{"observation_id": "blind-observation", "claim_id": "blind-claim", "edge_id": "blind-edge", "context_key": context, "evidence_digest": "sha256:evidence-digest", "source_ids": ["src-blinded"], "source_versions": {"src-blinded": "v1"}, "source_receipt_hash": "sha256:source-receipt", "raw_hash": "sha256:blind-observation"}]
        decisions = [{"verdict": "supports", "confidence": 0.82, "rationale": "masked record is internally coherent"}, {"verdict": "supports", "confidence": 0.77, "rationale": "masked record retains declared context"}]
        if kind == "split":
            decisions[1] = {**decisions[1], "verdict": "against"}
        if kind == "missing":
            decisions = decisions[:1]
        if kind == "foreign":
            observations[0]["context_key"] = "GRCh38|glioma|pediatric|stem_like|core|untreated"
        return {"observations": observations, "decisions": decisions}
    if operation is LifecycleBetaFrontierOperation.COMMENT_CHANGE_LOG:
        comments = [{"comment_id": "comment-1", "review_id": "review-1", "target_type": "claim", "target_id": "claim-comment", "context_key": context, "author_role": "domain_reviewer", "text": "retain source boundary", "state": "open", "raw_hash": "sha256:comment-1", "created_at": "2026-08-20T00:00:00+00:00"}]
        changes = [{"change_id": "change-1", "review_id": "review-1", "target_type": "claim", "target_id": "claim-comment", "context_key": context, "actor_role": "data_reviewer", "action": "annotate", "before_hash": "sha256:before", "after_hash": "sha256:after", "rationale": "record boundary clarification", "raw_hash": "sha256:change-1", "created_at": "2026-08-20T00:00:00+00:00"}]
        if kind == "duplicate":
            comments.append({**comments[0]})
        if kind == "foreign":
            comments[0]["context_key"] = "GRCh38|glioma|pediatric|stem_like|core|untreated"
        if kind == "empty":
            comments, changes = [], []
        return {"review_id": "review-1", "comments": comments, "changes": changes}
    if operation is LifecycleBetaFrontierOperation.RELEASE_DECISION:
        gates = [{"gate_id": "gate-integrity", "label": "integrity", "passed": True, "blocking": True, "context_key": context, "evidence_hash": "sha256:integrity", "reason": "receipt closes", "source_id": "src-release", "raw_hash": "sha256:gate-integrity"}, {"gate_id": "gate-review", "label": "review", "passed": True, "blocking": True, "context_key": context, "evidence_hash": "sha256:review", "reason": "roles complete", "source_id": "src-release", "raw_hash": "sha256:gate-review"}]
        if kind == "blocking":
            gates[1] = {**gates[1], "passed": False, "reason": "review role incomplete"}
        if kind == "rejected":
            return {"gates": gates, "requested_decision": "rejected", "completed_roles": ["domain_expert", "data_provenance"]}
        if kind == "foreign":
            gates[0]["context_key"] = "GRCh38|glioma|pediatric|stem_like|core|untreated"
        return {"graph_id": "release-graph", "graph_version": 3, "gates": gates, "required_roles": ["domain_expert", "data_provenance"], "completed_roles": ["domain_expert", "data_provenance"], "requested_decision": "approved"}
    if operation is LifecycleBetaFrontierOperation.EVIDENCE_DELTA:
        before = {"graph_id": "delta-graph", "version": 1, "context_key": context, "claims": [{"claim_id": "delta-claim", "value": "baseline", "source_id": "src-delta"}], "citations": [{"citation_id": "delta-citation", "version": "v1"}]}
        after = {"graph_id": "delta-graph", "version": 2, "context_key": context, "claims": [{"claim_id": "delta-claim", "value": "updated", "source_id": "src-delta"}, {"claim_id": "delta-added", "value": "new", "source_id": "src-delta"}], "citations": [{"citation_id": "delta-citation", "version": "v2"}]}
        if kind == "stable":
            after = before
        if kind == "foreign":
            after["context_key"] = "GRCh38|glioma|pediatric|stem_like|core|untreated"
        if kind == "empty":
            before["claims"], after["claims"] = [], []
            before["citations"], after["citations"] = [], []
        return {"before": before, "after": after}
    raise ValueError(f"unsupported operation: {operation}")


def _record(record_id: str, operation: LifecycleBetaFrontierOperation, role: LifecycleBetaFrontierRole, kind: str, expected: LifecycleBetaFrontierState, issues: tuple[str, ...], source_ids: tuple[str, ...], notes: str) -> LifecycleBetaFrontierRecord:
    body = {
        "record_id": record_id,
        "operation": operation,
        "role": role,
        "context_key": LIFECYCLE_BETA_FRONTIER_CONTEXT_KEY,
        "source_ids": source_ids,
        "payload": {"kind": kind, "data": _payload(operation, kind, LIFECYCLE_BETA_FRONTIER_CONTEXT_KEY)},
        "expected_state": expected,
        "expected_issue_codes": issues,
        "notes": notes,
    }
    return LifecycleBetaFrontierRecord(**body, content_address=content_hash(body))


def default_lifecycle_beta_frontier_fixture() -> LifecycleBetaFrontierFixture:
    """Return 32 deterministic records, one positive and three controls per surface."""

    source_pairs = (
        ("src-tier", "Evidence-tier aggregate receipt"),
        ("src-lineage", "Provenance lineage aggregate receipt"),
        ("src-uncertainty", "Uncertainty driver aggregate receipt"),
        ("src-routing", "Review routing aggregate receipt"),
        ("src-blinded", "Blinded adjudication aggregate receipt"),
        ("src-comments", "Review comment aggregate receipt"),
        ("src-release", "Research release aggregate receipt"),
        ("src-delta", "Evidence delta aggregate receipt"),
        ("src-control", "Negative control aggregate receipt"),
    )
    sources = tuple(_source(*item) for item in source_pairs)
    rows: list[LifecycleBetaFrontierRecord] = []
    rows.extend((
        _record("C05-POS-001", LifecycleBetaFrontierOperation.TIER_ADJUDICATION, LifecycleBetaFrontierRole.POSITIVE, "positive", LifecycleBetaFrontierState.SUPPORTED, (), ("src-tier",), "highest supporting tier remains visible"),
        _record("C05-CTRL-001", LifecycleBetaFrontierOperation.TIER_ADJUDICATION, LifecycleBetaFrontierRole.CONTROL, "contradiction", LifecycleBetaFrontierState.CONTRADICTORY, ("tier_direction_conflict",), ("src-control",), "supporting and against observations are not averaged"),
        _record("C05-CTRL-002", LifecycleBetaFrontierOperation.TIER_ADJUDICATION, LifecycleBetaFrontierRole.CONTROL, "foreign", LifecycleBetaFrontierState.OUT_OF_DOMAIN, ("context_mismatch",), ("src-control",), "foreign context is excluded"),
        _record("C05-CTRL-003", LifecycleBetaFrontierOperation.TIER_ADJUDICATION, LifecycleBetaFrontierRole.CONTROL, "unclassified", LifecycleBetaFrontierState.PARTIAL, ("unclassified_tier",), ("src-control",), "unclassified evidence remains partial"),
        _record("C06-POS-001", LifecycleBetaFrontierOperation.PROVENANCE_LINEAGE, LifecycleBetaFrontierRole.POSITIVE, "positive", LifecycleBetaFrontierState.SUPPORTED, (), ("src-lineage",), "parent and supersession edges are retained"),
        _record("C06-CTRL-001", LifecycleBetaFrontierOperation.PROVENANCE_LINEAGE, LifecycleBetaFrontierRole.CONTROL, "missing_parent", LifecycleBetaFrontierState.PARTIAL, ("missing_parent",), ("src-control",), "unresolved parent is visible"),
        _record("C06-CTRL-002", LifecycleBetaFrontierOperation.PROVENANCE_LINEAGE, LifecycleBetaFrontierRole.CONTROL, "foreign", LifecycleBetaFrontierState.OUT_OF_DOMAIN, ("context_mismatch",), ("src-control",), "foreign claim lineage is blocked"),
        _record("C06-CTRL-003", LifecycleBetaFrontierOperation.PROVENANCE_LINEAGE, LifecycleBetaFrontierRole.CONTROL, "empty", LifecycleBetaFrontierState.ABSTAINED, ("no_claims",), ("src-control",), "empty lineage abstains"),
        _record("C07-POS-001", LifecycleBetaFrontierOperation.UNCERTAINTY_LEDGER, LifecycleBetaFrontierRole.POSITIVE, "positive", LifecycleBetaFrontierState.SUPPORTED, (), ("src-uncertainty",), "dimension-labeled uncertainty is retained"),
        _record("C07-CTRL-001", LifecycleBetaFrontierOperation.UNCERTAINTY_LEDGER, LifecycleBetaFrontierRole.CONTROL, "foreign", LifecycleBetaFrontierState.OUT_OF_DOMAIN, ("context_mismatch",), ("src-control",), "foreign uncertainty is not transported"),
        _record("C07-CTRL-002", LifecycleBetaFrontierOperation.UNCERTAINTY_LEDGER, LifecycleBetaFrontierRole.CONTROL, "empty", LifecycleBetaFrontierState.ABSTAINED, ("no_entries",), ("src-control",), "no observations abstain"),
        _record("C07-CTRL-003", LifecycleBetaFrontierOperation.UNCERTAINTY_LEDGER, LifecycleBetaFrontierRole.CONTROL, "invalid", LifecycleBetaFrontierState.PARTIAL, ("invalid_uncertainty",), ("src-control",), "out-of-range values are quarantined"),
        _record("C08-POS-001", LifecycleBetaFrontierOperation.REVIEW_ROUTING, LifecycleBetaFrontierRole.POSITIVE, "positive", LifecycleBetaFrontierState.CONTRADICTORY, ("contradictory_claim",), ("src-routing",), "routing preserves contradiction priority"),
        _record("C08-CTRL-001", LifecycleBetaFrontierOperation.REVIEW_ROUTING, LifecycleBetaFrontierRole.CONTROL, "foreign", LifecycleBetaFrontierState.OUT_OF_DOMAIN, ("context_mismatch",), ("src-control",), "foreign claims are not assigned"),
        _record("C08-CTRL-002", LifecycleBetaFrontierOperation.REVIEW_ROUTING, LifecycleBetaFrontierRole.CONTROL, "empty", LifecycleBetaFrontierState.ABSTAINED, ("no_active_claims",), ("src-control",), "empty queue abstains"),
        _record("C08-CTRL-003", LifecycleBetaFrontierOperation.REVIEW_ROUTING, LifecycleBetaFrontierRole.CONTROL, "positive", LifecycleBetaFrontierState.REVIEW_REQUIRED, ("required_role",), ("src-control",), "role assignment retains staffing requirement"),
        _record("C09-POS-001", LifecycleBetaFrontierOperation.BLINDED_ADJUDICATION, LifecycleBetaFrontierRole.POSITIVE, "positive", LifecycleBetaFrontierState.ADJUDICATED, (), ("src-blinded",), "agreeing masked decisions are reconciled"),
        _record("C09-CTRL-001", LifecycleBetaFrontierOperation.BLINDED_ADJUDICATION, LifecycleBetaFrontierRole.CONTROL, "split", LifecycleBetaFrontierState.SPLIT_DECISION, ("split_verdict",), ("src-control",), "split verdicts remain unresolved"),
        _record("C09-CTRL-002", LifecycleBetaFrontierOperation.BLINDED_ADJUDICATION, LifecycleBetaFrontierRole.CONTROL, "missing", LifecycleBetaFrontierState.REVIEW_REQUIRED, ("required_decision_count",), ("src-control",), "missing reviewer decision blocks closure"),
        _record("C09-CTRL-003", LifecycleBetaFrontierOperation.BLINDED_ADJUDICATION, LifecycleBetaFrontierRole.CONTROL, "foreign", LifecycleBetaFrontierState.OUT_OF_DOMAIN, ("context_mismatch",), ("src-control",), "foreign case is excluded"),
        _record("C10-POS-001", LifecycleBetaFrontierOperation.COMMENT_CHANGE_LOG, LifecycleBetaFrontierRole.POSITIVE, "positive", LifecycleBetaFrontierState.READY_FOR_REVIEW, (), ("src-comments",), "comment and before-after change are append-only"),
        _record("C10-CTRL-001", LifecycleBetaFrontierOperation.COMMENT_CHANGE_LOG, LifecycleBetaFrontierRole.CONTROL, "duplicate", LifecycleBetaFrontierState.PARTIAL, ("duplicate_log_id",), ("src-control",), "duplicate log IDs are rejected"),
        _record("C10-CTRL-002", LifecycleBetaFrontierOperation.COMMENT_CHANGE_LOG, LifecycleBetaFrontierRole.CONTROL, "foreign", LifecycleBetaFrontierState.OUT_OF_DOMAIN, ("context_mismatch",), ("src-control",), "foreign comment is excluded"),
        _record("C10-CTRL-003", LifecycleBetaFrontierOperation.COMMENT_CHANGE_LOG, LifecycleBetaFrontierRole.CONTROL, "empty", LifecycleBetaFrontierState.ABSTAINED, ("no_review_items",), ("src-control",), "empty review log abstains"),
        _record("C11-POS-001", LifecycleBetaFrontierOperation.RELEASE_DECISION, LifecycleBetaFrontierRole.POSITIVE, "positive", LifecycleBetaFrontierState.APPROVED, (), ("src-release",), "all research gates and roles are complete"),
        _record("C11-CTRL-001", LifecycleBetaFrontierOperation.RELEASE_DECISION, LifecycleBetaFrontierRole.CONTROL, "blocking", LifecycleBetaFrontierState.REVIEW_REQUIRED, ("blocking_gate",), ("src-control",), "blocking gate requires review"),
        _record("C11-CTRL-002", LifecycleBetaFrontierOperation.RELEASE_DECISION, LifecycleBetaFrontierRole.CONTROL, "rejected", LifecycleBetaFrontierState.REJECTED, ("explicit_rejection",), ("src-control",), "explicit rejection is retained"),
        _record("C11-CTRL-003", LifecycleBetaFrontierOperation.RELEASE_DECISION, LifecycleBetaFrontierRole.CONTROL, "foreign", LifecycleBetaFrontierState.REVIEW_REQUIRED, ("gate_context_mismatch",), ("src-control",), "foreign gate is not silently approved"),
        _record("C12-POS-001", LifecycleBetaFrontierOperation.EVIDENCE_DELTA, LifecycleBetaFrontierRole.POSITIVE, "positive", LifecycleBetaFrontierState.REVIEW_REQUIRED, ("citation_changed", "claim_added", "claim_changed"), ("src-delta",), "changed evidence requires reconciliation"),
        _record("C12-CTRL-001", LifecycleBetaFrontierOperation.EVIDENCE_DELTA, LifecycleBetaFrontierRole.CONTROL, "stable", LifecycleBetaFrontierState.READY_FOR_REVIEW, (), ("src-control",), "unchanged snapshots have no delta"),
        _record("C12-CTRL-002", LifecycleBetaFrontierOperation.EVIDENCE_DELTA, LifecycleBetaFrontierRole.CONTROL, "foreign", LifecycleBetaFrontierState.OUT_OF_DOMAIN, ("context_changed",), ("src-control",), "context change is critical"),
        _record("C12-CTRL-003", LifecycleBetaFrontierOperation.EVIDENCE_DELTA, LifecycleBetaFrontierRole.CONTROL, "empty", LifecycleBetaFrontierState.READY_FOR_REVIEW, (), ("src-control",), "empty snapshots remain comparable"),
    ))
    body = {"fixture_id": "lifecycle-beta-frontier", "fixture_version": LIFECYCLE_BETA_FRONTIER_VERSION, "context_key": LIFECYCLE_BETA_FRONTIER_CONTEXT_KEY, "evidence_boundary": LIFECYCLE_BETA_FRONTIER_BOUNDARY, "sources": sources, "records": tuple(rows)}
    return LifecycleBetaFrontierFixture(**body, content_address=content_hash(body))


def _data_check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> LifecycleBetaFrontierDataCheck:
    body = {"check_id": check_id, "passed": passed, "observed": observed, "required": required, "detail": detail}
    return LifecycleBetaFrontierDataCheck(**body, content_address=content_hash(body))


def audit_lifecycle_beta_frontier_data(fixture: LifecycleBetaFrontierFixture | None = None) -> LifecycleBetaFrontierDataAudit:
    fixture = fixture or default_lifecycle_beta_frontier_fixture()
    source_ids = {item.source_id for item in fixture.sources}
    checks = tuple(_data_check(*row) for row in (
        ("boundary", fixture.evidence_boundary == LIFECYCLE_BETA_FRONTIER_BOUNDARY, fixture.evidence_boundary, LIFECYCLE_BETA_FRONTIER_BOUNDARY, "aggregate boundary is exact"),
        ("version", fixture.fixture_version == LIFECYCLE_BETA_FRONTIER_VERSION, fixture.fixture_version, LIFECYCLE_BETA_FRONTIER_VERSION, "fixture version is exact"),
        ("sources", len(fixture.sources) == LIFECYCLE_BETA_FRONTIER_SOURCE_COUNT, len(fixture.sources), LIFECYCLE_BETA_FRONTIER_SOURCE_COUNT, "source receipts are complete"),
        ("records", len(fixture.records) == 32, len(fixture.records), 32, "four rows cover each operation"),
        ("positive", len(fixture.positive_records) == LIFECYCLE_BETA_FRONTIER_POSITIVE_COUNT, len(fixture.positive_records), LIFECYCLE_BETA_FRONTIER_POSITIVE_COUNT, "one positive per operation"),
        ("controls", len(fixture.control_records) == LIFECYCLE_BETA_FRONTIER_CONTROL_COUNT, len(fixture.control_records), LIFECYCLE_BETA_FRONTIER_CONTROL_COUNT, "three controls per operation"),
        ("unique-records", len({item.record_id for item in fixture.records}) == len(fixture.records), len({item.record_id for item in fixture.records}), len(fixture.records), "record IDs are unique"),
        ("source-bindings", all(set(item.source_ids) <= source_ids for item in fixture.records), True, True, "record receipts resolve"),
        ("operations", {item.operation for item in fixture.records} == set(LifecycleBetaFrontierOperation), tuple(sorted({item.operation.value for item in fixture.records})), tuple(item.value for item in LifecycleBetaFrontierOperation), "all eight operations are covered"),
        ("context", all(item.context_key == fixture.context_key for item in fixture.records), fixture.context_key, fixture.context_key, "record contexts are exact"),
        ("addresses", all(item.content_address.startswith("sha256:") for item in fixture.records), True, True, "record addresses are closed"),
    ))
    body = {"fixture_id": fixture.fixture_id, "checks": checks, "accepted": all(item.passed for item in checks)}
    return LifecycleBetaFrontierDataAudit(fixture.fixture_id, checks, body["accepted"], content_hash(body))


def load_lifecycle_beta_frontier_fixture(path: str | Path) -> LifecycleBetaFrontierFixture:
    import json

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not payload.get("records"):
        raise ValueError("lifecycle beta frontier fixture requires records")
    sources = tuple(LifecycleBetaFrontierSourceReceipt(**item) for item in payload["sources"])
    records = tuple(LifecycleBetaFrontierRecord(**{**item, "operation": LifecycleBetaFrontierOperation(str(item["operation"])), "role": LifecycleBetaFrontierRole(str(item["role"])), "source_ids": tuple(str(value) for value in item["source_ids"]), "expected_state": LifecycleBetaFrontierState(str(item["expected_state"])), "expected_issue_codes": tuple(str(value) for value in item["expected_issue_codes"])}) for item in payload["records"])
    return LifecycleBetaFrontierFixture(fixture_id=str(payload["fixture_id"]), fixture_version=str(payload["fixture_version"]), context_key=str(payload["context_key"]), evidence_boundary=str(payload["evidence_boundary"]), sources=sources, records=records, content_address=str(payload.get("content_address", content_hash({"sources": sources, "records": records}))))


__all__ = [
    "LIFECYCLE_BETA_FRONTIER_BOUNDARY",
    "LIFECYCLE_BETA_FRONTIER_CONTEXT_KEY",
    "LIFECYCLE_BETA_FRONTIER_CONTROL_COUNT",
    "LIFECYCLE_BETA_FRONTIER_POSITIVE_COUNT",
    "LIFECYCLE_BETA_FRONTIER_SOURCE_COUNT",
    "LIFECYCLE_BETA_FRONTIER_VERSION",
    "LifecycleBetaFrontierDataAudit",
    "LifecycleBetaFrontierDataCheck",
    "audit_lifecycle_beta_frontier_data",
    "default_lifecycle_beta_frontier_fixture",
    "load_lifecycle_beta_frontier_fixture",
]
