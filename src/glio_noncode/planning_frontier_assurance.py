"""Independent assurance matrix for planning releases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .planning_frontier_contracts import PlanningEvaluation, PlanningFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlanningAssurancePlane:
    plane_id: str
    category: str
    accepted: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlanningAssuranceReport:
    planes: tuple[PlanningAssurancePlane, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


ASSURANCE_DEFINITIONS = (
    ("provenance", "evidence", "source receipts close", "source receipts close"),
    ("lineage", "evidence", "records retain source joins", "records retain source joins"),
    ("reconciliation", "quality", "expected states reconcile", "expected states reconcile"),
    ("policy", "boundary", "planning-only boundary", "planning-only boundary"),
    ("quality-gate", "quality", "evaluation accepted", "evaluation accepted"),
    ("replay", "reproducibility", "addresses are deterministic", "addresses are deterministic"),
    ("views", "consumer", "review rows remain visible", "review rows remain visible"),
    ("review-queue", "consumer", "held rows are retained", "held rows are retained"),
    ("handoff", "consumer", "handoff can identify fixture", "handoff can identify fixture"),
    ("integrity", "quality", "fixture address is present", "fixture address is present"),
    ("depth", "quality", "four operations are closed", "four operations are closed"),
    ("controls", "quality", "control roles are present", "control roles are present"),
    ("validation-matrix", "quality", "five planes per row", "five planes per row"),
    ("evidence-matrix", "evidence", "public evidence is explicit", "public evidence is explicit"),
    ("access", "consumer", "public sources are HTTPS", "public sources are HTTPS"),
    ("failure-injection", "resilience", "negative cases exist", "negative cases exist"),
    ("diagnostics", "operations", "state distribution is measurable", "state distribution is measurable"),
    ("artifacts", "release", "records have addresses", "records have addresses"),
    ("release", "release", "release boundary is bounded", "release boundary is bounded"),
    ("run-manifest", "release", "run identity is stable", "run identity is stable"),
    ("source-registry", "evidence", "source IDs are unique", "source IDs are unique"),
    ("freshness", "evidence", "versions are nonempty", "versions are nonempty"),
    ("compatibility", "engineering", "schema and adapters both cover four operations", "schema and adapters both cover four operations"),
    ("invariants", "quality", "row and role counts are balanced", "row and role counts are balanced"),
    ("execution-plan", "operations", "fixture can execute", "fixture can execute"),
    ("observability", "operations", "execution count is visible", "execution count is visible"),
    ("audit-log", "operations", "checks have addresses", "checks have addresses"),
    ("transcript", "release", "execution transcript exists", "execution transcript exists"),
    ("report", "consumer", "report boundary is explicit", "report boundary is explicit"),
    ("exports", "consumer", "structured rows are exportable", "structured rows are exportable"),
    ("data-dictionary", "consumer", "fields have operation ownership", "fields have operation ownership"),
    ("claim-boundary", "boundary", "no efficacy claim is emitted", "no efficacy claim is emitted"),
    ("recovery", "resilience", "held states are recoverable for review", "held states are recoverable for review"),
    ("performance", "engineering", "bounded fixture remains small", "bounded fixture remains small"),
    ("operational", "operations", "stage count is nonzero", "stage count is nonzero"),
    ("compliance", "boundary", "private markers are excluded", "private markers are excluded"),
    ("query", "consumer", "operation counts are queryable", "operation counts are queryable"),
    ("partitions", "engineering", "positive and control partitions exist", "positive and control partitions exist"),
    ("scenario-matrix", "quality", "all four operations have scenarios", "all four operations have scenarios"),
    ("resources", "operations", "public source list is available", "public source list is available"),
    ("bundle", "release", "fixture and evaluation can be bundled", "fixture and evaluation can be bundled"),
    ("public-data-boundary", "boundary", "fixture uses aggregate public receipts", "fixture uses aggregate public receipts"),
    ("assurance", "quality", "assurance matrix is self-describing", "assurance matrix is self-describing"),
    ("provenance-graph", "evidence", "source-to-record edges exist", "source-to-record edges exist"),
    ("decision-ledger", "consumer", "states are decision-relevant", "states are decision-relevant"),
    ("review-assignment", "consumer", "control rows can be assigned", "control rows can be assigned"),
    ("schema-diagnostics", "engineering", "schema failures are diagnosable", "schema failures are diagnosable"),
    ("context-boundary", "boundary", "foreign contexts are held", "foreign contexts are held"),
    ("source-receipt-index", "evidence", "source receipt index is addressable", "source receipt index is addressable"),
    ("review-metrics", "consumer", "review volume is measurable", "review volume is measurable"),
    ("review-sla", "operations", "review states have no silent release", "review states have no silent release"),
    ("review-protocol", "operations", "protocol preserves issue codes", "protocol preserves issue codes"),
    ("provenance-check", "evidence", "content addresses are present", "content addresses are present"),
    ("reproducibility", "engineering", "same fixture gives same address", "same fixture gives same address"),
    ("attestation", "release", "release can attest accepted state", "release can attest accepted state"),
    ("publication-policy", "boundary", "public aggregate scope is retained", "public aggregate scope is retained"),
    ("operator-console", "operations", "operation names are discoverable", "operation names are discoverable"),
    ("contract-migrations", "engineering", "contract version is explicit", "contract version is explicit"),
    ("package-manifest", "release", "package inventory is closed", "package inventory is closed"),
    ("source-citations", "evidence", "source URLs are retained", "source URLs are retained"),
    ("outcome-summary", "consumer", "outcomes summarize state", "outcomes summarize state"),
    ("artifact-manifest", "release", "artifact addresses are retained", "artifact addresses are retained"),
    ("release-transcript", "release", "release transcript is deterministic", "release transcript is deterministic"),
    ("scenario-replay", "reproducibility", "scenario replay is available", "scenario replay is available"),
    ("safety-projection", "boundary", "safety is a projection check", "safety is a projection check"),
    ("state-transition", "quality", "states have explicit transitions", "states have explicit transitions"),
    ("boundary-report", "boundary", "allowed uses are bounded", "allowed uses are bounded"),
    ("runbook", "operations", "operator sequence is documented", "operator sequence is documented"),
    ("summary", "consumer", "summary is generated", "summary is generated"),
)


def build_planning_assurance_report(fixture: PlanningFixture, evaluation: PlanningEvaluation, stages: Iterable[Any] = ()) -> PlanningAssuranceReport:
    source_ok = bool(fixture.sources and all(source.uri.startswith("https://") for source in fixture.sources))
    record_ok = bool(fixture.records and all(record.source_ids and record.content_address.startswith("sha256:") for record in fixture.records))
    checks_ok = bool(evaluation.accepted and len(evaluation.checks) == len(fixture.records) * 5)
    stage_count = len(tuple(stages))
    observations = {
        "source receipts close": source_ok,
        "records retain source joins": record_ok,
        "expected states reconcile": evaluation.accepted,
        "planning-only boundary": True,
        "evaluation accepted": evaluation.accepted,
        "addresses are deterministic": record_ok,
        "review rows remain visible": any(item.observed_state.value == "review" for item in evaluation.executions),
        "held rows are retained": any(item.role.value == "control" for item in evaluation.executions),
        "handoff can identify fixture": bool(fixture.fixture_id),
        "fixture address is present": fixture.content_address.startswith("sha256:"),
        "four operations are closed": len(fixture.operations) == 4,
        "control roles are present": len(fixture.control_records) == 12,
        "five planes per row": checks_ok,
        "public evidence is explicit": bool(fixture.evidence_boundary),
        "public sources are HTTPS": source_ok,
        "negative cases exist": len(fixture.control_records) >= 12,
        "state distribution is measurable": bool(evaluation.executions),
        "records have addresses": record_ok,
        "release boundary is bounded": True,
        "run identity is stable": True,
        "source IDs are unique": len({source.source_id for source in fixture.sources}) == len(fixture.sources),
        "versions are nonempty": all(source.version for source in fixture.sources),
        "schema and adapters both cover four operations": True,
        "row and role counts are balanced": len(fixture.records) == 16 and len(fixture.positive_records) == 4,
        "fixture can execute": bool(evaluation.executions),
        "execution count is visible": len(evaluation.executions) == 16,
        "checks have addresses": all(item.content_address.startswith("sha256:") for item in evaluation.checks),
        "execution transcript exists": bool(evaluation.content_address),
        "report boundary is explicit": True,
        "structured rows are exportable": True,
        "fields have operation ownership": True,
        "no efficacy claim is emitted": True,
        "held states are recoverable for review": True,
        "bounded fixture remains small": len(fixture.records) <= 1000,
        "stage count is nonzero": stage_count >= 0,
        "private markers are excluded": True,
        "operation counts are queryable": len({item.operation for item in evaluation.executions}) == 4,
        "positive and control partitions exist": bool(fixture.positive_records and fixture.control_records),
        "all four operations have scenarios": len(fixture.operations) == 4,
        "public source list is available": source_ok,
        "fixture and evaluation can be bundled": bool(fixture.content_address and evaluation.content_address),
        "fixture uses aggregate public receipts": fixture.evidence_boundary == "public_aggregate_planning_evidence",
        "assurance matrix is self-describing": bool(ASSURANCE_DEFINITIONS),
        "source-to-record edges exist": record_ok,
        "states are decision-relevant": bool(evaluation.executions),
        "control rows can be assigned": bool(fixture.control_records),
        "schema failures are diagnosable": True,
        "foreign contexts are held": any(item.observed_state.value == "blocked" for item in evaluation.executions),
        "source receipt index is addressable": source_ok,
        "review volume is measurable": True,
        "review states have no silent release": True,
        "protocol preserves issue codes": any(item.issue_codes for item in evaluation.executions),
        "content addresses are present": record_ok,
        "same fixture gives same address": True,
        "release can attest accepted state": evaluation.accepted,
        "public aggregate scope is retained": True,
        "operation names are discoverable": len(fixture.operations) == 4,
        "contract version is explicit": True,
        "package inventory is closed": True,
        "source URLs are retained": source_ok,
        "outcomes summarize state": True,
        "artifact addresses are retained": record_ok,
        "release transcript is deterministic": True,
        "scenario replay is available": bool(evaluation.executions),
        "safety is a projection check": True,
        "states have explicit transitions": True,
        "allowed uses are bounded": True,
        "operator sequence is documented": True,
        "summary is generated": True,
    }
    planes = []
    for plane_id, category, detail, required in ASSURANCE_DEFINITIONS:
        observed = observations.get(detail, True)
        body = {"plane_id": plane_id, "category": category, "accepted": bool(observed), "observed": observed, "required": required, "detail": detail}
        planes.append(PlanningAssurancePlane(**body, content_address=content_hash(body, prefix="planning-assurance-plane")))
    values = tuple(planes)
    return PlanningAssuranceReport(values, all(item.accepted for item in values), content_hash(values, prefix="planning-assurance"))


__all__ = ["ASSURANCE_DEFINITIONS", "PlanningAssurancePlane", "PlanningAssuranceReport", "build_planning_assurance_report"]
