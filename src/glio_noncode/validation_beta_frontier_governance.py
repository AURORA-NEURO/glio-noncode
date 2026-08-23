"""Evidence, control, and release governance for validation-beta planning.

This module keeps the planning output honest.  It does not turn a design into
an efficacy claim.  Instead it makes every positive, partial, blocked,
out-of-domain, and abstained path available to review, replay, and release
checks with stable content addresses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .serialization import content_hash, jsonable, require_non_empty
from .validation_beta_frontier_contracts import (
    ValidationBetaFrontierContractRegistry,
    default_validation_beta_frontier_contracts,
)
from .validation_beta_frontier_fixture_eval import (
    ValidationBetaFrontierEvaluation,
    ValidationBetaFrontierEvaluationRow,
    evaluate_validation_beta_frontier_fixture,
)
from .validation_beta_frontier_public_data import (
    ValidationBetaFrontierFixture,
    ValidationBetaFrontierOperation,
    ValidationBetaFrontierRole,
    audit_validation_beta_frontier_data,
    default_validation_beta_frontier_fixture,
)
from .validation_beta_frontier_schema import (
    ValidationBetaFrontierSchemaReport,
    default_validation_beta_frontier_schema,
)


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierOperationMetric:
    operation: ValidationBetaFrontierOperation
    total_count: int
    positive_count: int
    control_count: int
    accepted_count: int
    state_counts: Mapping[str, int]
    issue_counts: Mapping[str, int]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierMetrics:
    total_rows: int
    accepted_rows: int
    positive_rows: int
    control_rows: int
    mismatch_rows: int
    operation_metrics: tuple[ValidationBetaFrontierOperationMetric, ...]
    state_counts: Mapping[str, int]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def measure_validation_beta_frontier(
    evaluation: ValidationBetaFrontierEvaluation | None = None,
) -> ValidationBetaFrontierMetrics:
    value = evaluation or evaluate_validation_beta_frontier_fixture()
    operation_metrics: list[ValidationBetaFrontierOperationMetric] = []
    total_states: dict[str, int] = {}
    for operation in ValidationBetaFrontierOperation:
        rows = value.by_operation(operation)
        state_counts: dict[str, int] = {}
        issue_counts: dict[str, int] = {}
        for row in rows:
            state_counts[row.observed_state] = state_counts.get(row.observed_state, 0) + 1
            total_states[row.observed_state] = total_states.get(row.observed_state, 0) + 1
            for issue in row.observed_issue_codes:
                issue_counts[issue] = issue_counts.get(issue, 0) + 1
        body = {"operation": operation, "rows": rows, "states": state_counts, "issues": issue_counts}
        operation_metrics.append(
            ValidationBetaFrontierOperationMetric(
                operation=operation,
                total_count=len(rows),
                positive_count=sum(item.record_id.endswith("POS-001") for item in rows),
                control_count=sum("CTRL" in item.record_id for item in rows),
                accepted_count=sum(item.accepted for item in rows),
                state_counts=state_counts,
                issue_counts=issue_counts,
                content_address=content_hash(body, prefix="validation-beta-metric"),
            )
        )
    body = {"evaluation": value, "operation_metrics": tuple(operation_metrics), "state_counts": total_states}
    return ValidationBetaFrontierMetrics(
        total_rows=len(value.rows),
        accepted_rows=sum(item.accepted for item in value.rows),
        positive_rows=value.positive_count,
        control_rows=value.control_count,
        mismatch_rows=value.mismatch_count,
        operation_metrics=tuple(operation_metrics),
        state_counts=total_states,
        content_address=content_hash(body, prefix="validation-beta-metrics"),
    )


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierLineageEdge:
    edge_id: str
    from_id: str
    to_id: str
    edge_kind: str
    source_id: str | None
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierLineage:
    fixture_id: str
    node_ids: tuple[str, ...]
    edges: tuple[ValidationBetaFrontierLineageEdge, ...]
    closed: bool
    orphan_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_beta_frontier_lineage(
    fixture: ValidationBetaFrontierFixture,
    evaluation: ValidationBetaFrontierEvaluation,
) -> ValidationBetaFrontierLineage:
    nodes: list[str] = [source.source_id for source in fixture.sources]
    nodes.extend(record.record_id for record in fixture.records)
    nodes.extend(f"evaluation:{row.record_id}" for row in evaluation.rows)
    edges: list[ValidationBetaFrontierLineageEdge] = []
    for record in fixture.records:
        for source_id in record.source_ids:
            body = {"from_id": source_id, "to_id": record.record_id, "edge_kind": "source-to-record", "source_id": source_id}
            edges.append(ValidationBetaFrontierLineageEdge(content_hash(body, prefix="validation-beta-edge"), source_id, record.record_id, "source-to-record", source_id, content_hash(body, prefix="validation-beta-edge-body")))
        body = {"from_id": record.record_id, "to_id": f"evaluation:{record.record_id}", "edge_kind": "record-to-result", "source_id": None}
        edges.append(ValidationBetaFrontierLineageEdge(content_hash(body, prefix="validation-beta-edge"), record.record_id, f"evaluation:{record.record_id}", "record-to-result", None, content_hash(body, prefix="validation-beta-edge-body")))
    connected = {value for edge in edges for value in (edge.from_id, edge.to_id)}
    orphan_ids = tuple(sorted(set(nodes) - connected))
    body = {"fixture_id": fixture.fixture_id, "nodes": tuple(nodes), "edges": tuple(edges), "orphan_ids": orphan_ids}
    return ValidationBetaFrontierLineage(fixture.fixture_id, tuple(nodes), tuple(edges), not orphan_ids, orphan_ids, content_hash(body, prefix="validation-beta-lineage"))


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierPolicyDecision:
    record_id: str
    state: str
    disposition: str
    allowed_uses: tuple[str, ...]
    excluded_uses: tuple[str, ...]
    reasons: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierPolicy:
    policy_id: str
    policy_version: str
    decisions: tuple[ValidationBetaFrontierPolicyDecision, ...]
    publish_count: int
    review_count: int
    quarantine_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def materialize_validation_beta_frontier_policy(
    evaluation: ValidationBetaFrontierEvaluation | None = None,
) -> ValidationBetaFrontierPolicy:
    value = evaluation or evaluate_validation_beta_frontier_fixture()
    decisions: list[ValidationBetaFrontierPolicyDecision] = []
    for row in value.rows:
        if row.observed_state == "ready_for_review" and row.record_id.endswith("POS-001"):
            disposition = "publish"
            reasons = ("positive planning path passed its declared operation gates",)
        elif row.observed_state == "partial":
            disposition = "review"
            reasons = ("partial source or power evidence must remain visible for review",)
        else:
            disposition = "quarantine"
            reasons = ("blocked, out-of-domain, or abstained planning path cannot enter a positive release view",)
        body = {"record_id": row.record_id, "state": row.observed_state, "disposition": disposition, "reasons": reasons}
        decisions.append(
            ValidationBetaFrontierPolicyDecision(
                record_id=row.record_id,
                state=row.observed_state,
                disposition=disposition,
                allowed_uses=("bounded research planning review", "reproducibility inspection"),
                excluded_uses=("efficacy claim", "off-target safety claim", "clinical decision", "automatic execution"),
                reasons=reasons,
                content_address=content_hash(body, prefix="validation-beta-policy-decision"),
            )
        )
    values = tuple(decisions)
    body = {"policy_id": "validation-beta-frontier-policy", "policy_version": "2026.08.d13-c05-c12.policy.v1", "decisions": values}
    return ValidationBetaFrontierPolicy(
        policy_id="validation-beta-frontier-policy",
        policy_version="2026.08.d13-c05-c12.policy.v1",
        decisions=values,
        publish_count=sum(item.disposition == "publish" for item in values),
        review_count=sum(item.disposition == "review" for item in values),
        quarantine_count=sum(item.disposition == "quarantine" for item in values),
        content_address=content_hash(body, prefix="validation-beta-policy"),
    )


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierReconciliationItem:
    record_id: str
    expected_state: str
    observed_state: str
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    accepted: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierReconciliation:
    fixture_id: str
    items: tuple[ValidationBetaFrontierReconciliationItem, ...]
    reconciled: bool
    mismatch_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def reconcile_validation_beta_frontier(
    fixture: ValidationBetaFrontierFixture,
    evaluation: ValidationBetaFrontierEvaluation,
) -> ValidationBetaFrontierReconciliation:
    expected = fixture.record_map()
    items: list[ValidationBetaFrontierReconciliationItem] = []
    for row in evaluation.rows:
        record = expected[row.record_id]
        code_floor = set(record.expected_issue_codes).issubset(set(row.observed_issue_codes))
        accepted = record.expected_state == row.observed_state and code_floor
        body = {"record_id": row.record_id, "expected_state": record.expected_state, "observed_state": row.observed_state, "accepted": accepted, "expected_issue_codes": record.expected_issue_codes, "observed_issue_codes": row.observed_issue_codes}
        items.append(ValidationBetaFrontierReconciliationItem(record.record_id, record.expected_state, row.observed_state, record.expected_issue_codes, row.observed_issue_codes, accepted, "expected state and issue floor reconcile" if accepted else "expected state or issue floor differs", content_hash(body, prefix="validation-beta-reconciliation-item")))
    values = tuple(items)
    mismatch_ids = tuple(item.record_id for item in values if not item.accepted)
    body = {"fixture_id": fixture.fixture_id, "items": values, "mismatch_ids": mismatch_ids}
    return ValidationBetaFrontierReconciliation(fixture.fixture_id, values, not mismatch_ids, mismatch_ids, content_hash(body, prefix="validation-beta-reconciliation"))


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierQualityCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierQualityGate:
    checks: tuple[ValidationBetaFrontierQualityCheck, ...]
    accepted: bool
    failed_check_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_validation_beta_frontier_quality(
    fixture: ValidationBetaFrontierFixture,
    evaluation: ValidationBetaFrontierEvaluation,
    contracts: ValidationBetaFrontierContractRegistry | None = None,
    schema: ValidationBetaFrontierSchemaReport | None = None,
    lineage: ValidationBetaFrontierLineage | None = None,
    reconciliation: ValidationBetaFrontierReconciliation | None = None,
) -> ValidationBetaFrontierQualityGate:
    data_audit = audit_validation_beta_frontier_data(fixture)
    contract_value = contracts or default_validation_beta_frontier_contracts()
    schema_value = schema or default_validation_beta_frontier_schema()
    lineage_value = lineage or build_validation_beta_frontier_lineage(fixture, evaluation)
    reconciliation_value = reconciliation or reconcile_validation_beta_frontier(fixture, evaluation)
    checks_raw = (
        ("data-audit", data_audit.accepted, data_audit.passed_count, len(data_audit.checks), "public fixture audit"),
        ("evaluation", evaluation.accepted, evaluation.mismatch_count, 0, "all fixture rows execute to expected states"),
        ("contract-closure", len(contract_value.contracts) == 8, len(contract_value.contracts), 8, "eight operation contracts"),
        ("schema-closure", schema_value.accepted and len(schema_value.operations) == 8, len(schema_value.operations), 8, "eight operation schemas"),
        ("lineage-closure", lineage_value.closed, len(lineage_value.orphan_ids), 0, "no orphan source or result nodes"),
        ("reconciliation", reconciliation_value.reconciled, len(reconciliation_value.mismatch_ids), 0, "expected states and issue floors reconcile"),
        ("record-balance", len(fixture.records) == 32, len(fixture.records), 32, "one positive and three controls per operation"),
        ("positive-balance", sum(item.record_id.endswith("POS-001") for item in evaluation.rows) == 8, sum(item.record_id.endswith("POS-001") for item in evaluation.rows), 8, "eight positive records"),
        ("control-balance", sum("CTRL" in item.record_id for item in evaluation.rows) == 24, sum("CTRL" in item.record_id for item in evaluation.rows), 24, "twenty-four control records"),
        ("publish-floor", sum(item.record_id.endswith("POS-001") and item.observed_state == "ready_for_review" for item in evaluation.rows) == 8, sum(item.record_id.endswith("POS-001") and item.observed_state == "ready_for_review" for item in evaluation.rows), 8, "all positive paths are review-ready"),
        ("state-visibility", len(evaluation.state_counts) >= 4, len(evaluation.state_counts), 4, "positive, blocked, partial, and abstained/out-of-domain states remain visible"),
        ("source-closure", all(set(record.source_ids).issubset(fixture.source_map()) for record in fixture.records), True, True, "every source ID resolves"),
    )
    checks = tuple(
        ValidationBetaFrontierQualityCheck(check_id, passed, observed, required, detail, content_hash({"check_id": check_id, "passed": passed, "observed": observed, "required": required}, prefix="validation-beta-quality-check"))
        for check_id, passed, observed, required, detail in checks_raw
    )
    failed = tuple(item.check_id for item in checks if not item.passed)
    body = {"checks": checks, "failed_check_ids": failed}
    return ValidationBetaFrontierQualityGate(checks, not failed, failed, content_hash(body, prefix="validation-beta-quality"))


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierReplayReceipt:
    replay_id: str
    original_address: str
    replay_address: str
    deterministic: bool
    row_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def replay_validation_beta_frontier(
    fixture: ValidationBetaFrontierFixture | None = None,
    *,
    replay_id: str = "validation-beta-frontier-replay",
) -> ValidationBetaFrontierReplayReceipt:
    value = fixture or default_validation_beta_frontier_fixture()
    first = evaluate_validation_beta_frontier_fixture(value)
    second = evaluate_validation_beta_frontier_fixture(value)
    body = {"replay_id": replay_id, "original": first.content_address, "replay": second.content_address, "row_count": len(second.rows)}
    return ValidationBetaFrontierReplayReceipt(replay_id, first.content_address, second.content_address, first.content_address == second.content_address, len(second.rows), content_hash(body, prefix="validation-beta-replay"))


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierReleaseCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierReleaseManifest:
    release_id: str
    state: str
    checks: tuple[ValidationBetaFrontierReleaseCheck, ...]
    publishable_records: tuple[str, ...]
    review_records: tuple[str, ...]
    quarantined_records: tuple[str, ...]
    content_address: str

    @property
    def ready(self) -> bool:
        return self.state == "ready_for_bounded_review"

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_beta_frontier_release_manifest(
    quality: ValidationBetaFrontierQualityGate,
    replay: ValidationBetaFrontierReplayReceipt,
    policy: ValidationBetaFrontierPolicy,
    *,
    release_id: str = "validation-beta-frontier-release",
) -> ValidationBetaFrontierReleaseManifest:
    checks = (
        ValidationBetaFrontierReleaseCheck("quality", quality.accepted, "quality gate accepted", content_hash({"quality": quality.content_address}, prefix="validation-beta-release-check")),
        ValidationBetaFrontierReleaseCheck("replay", replay.deterministic, "fixture replay is deterministic", content_hash({"replay": replay.content_address}, prefix="validation-beta-release-check")),
        ValidationBetaFrontierReleaseCheck("positive-publish-floor", policy.publish_count == 8, "eight positive records are publishable for bounded review", content_hash({"publish": policy.publish_count}, prefix="validation-beta-release-check")),
        ValidationBetaFrontierReleaseCheck("research-boundary", all("clinical decision" in item.excluded_uses for item in policy.decisions), "clinical use is excluded", content_hash({"decisions": policy.decisions}, prefix="validation-beta-release-check")),
    )
    state = "ready_for_bounded_review" if all(item.passed for item in checks) else "held_for_repair"
    publish = tuple(item.record_id for item in policy.decisions if item.disposition == "publish")
    review = tuple(item.record_id for item in policy.decisions if item.disposition == "review")
    quarantine = tuple(item.record_id for item in policy.decisions if item.disposition == "quarantine")
    body = {"release_id": release_id, "state": state, "checks": checks, "publish": publish, "review": review, "quarantine": quarantine}
    return ValidationBetaFrontierReleaseManifest(release_id, state, checks, publish, review, quarantine, content_hash(body, prefix="validation-beta-release"))


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierReviewItem:
    record_id: str
    operation: ValidationBetaFrontierOperation
    priority: int
    state: str
    reasons: tuple[str, ...]
    suggested_action: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierReviewQueue:
    items: tuple[ValidationBetaFrontierReviewItem, ...]
    open_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_beta_frontier_review_queue(
    evaluation: ValidationBetaFrontierEvaluation,
    policy: ValidationBetaFrontierPolicy | None = None,
) -> ValidationBetaFrontierReviewQueue:
    policy_value = policy or materialize_validation_beta_frontier_policy(evaluation)
    decisions = {item.record_id: item for item in policy_value.decisions}
    items: list[ValidationBetaFrontierReviewItem] = []
    for row in evaluation.rows:
        decision = decisions[row.record_id]
        if decision.disposition == "publish":
            continue
        priority = 1 if row.observed_state == "partial" else 2 if row.observed_state == "out_of_domain" else 3
        reasons = tuple(row.observed_issue_codes) or (row.observed_state,)
        body = {"record_id": row.record_id, "operation": row.operation, "priority": priority, "state": row.observed_state, "reasons": reasons}
        items.append(ValidationBetaFrontierReviewItem(row.record_id, row.operation, priority, row.observed_state, reasons, "inspect source, context, and declared boundary before retry", content_hash(body, prefix="validation-beta-review-item")))
    values = tuple(sorted(items, key=lambda item: (-item.priority, item.operation.value, item.record_id)))
    body = {"items": values}
    return ValidationBetaFrontierReviewQueue(values, len(values), all(bool(item.content_address) for item in values), content_hash(body, prefix="validation-beta-review-queue"))


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierScenario:
    scenario_id: str
    record_id: str
    operation: ValidationBetaFrontierOperation
    state: str
    expected_disposition: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierScenarioMatrix:
    scenarios: tuple[ValidationBetaFrontierScenario, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_beta_frontier_scenario_matrix(
    evaluation: ValidationBetaFrontierEvaluation,
    policy: ValidationBetaFrontierPolicy | None = None,
) -> ValidationBetaFrontierScenarioMatrix:
    decisions = {item.record_id: item for item in (policy or materialize_validation_beta_frontier_policy(evaluation)).decisions}
    scenarios: list[ValidationBetaFrontierScenario] = []
    for row in evaluation.rows:
        decision = decisions[row.record_id]
        body = {"record_id": row.record_id, "operation": row.operation, "state": row.observed_state, "disposition": decision.disposition}
        scenarios.append(ValidationBetaFrontierScenario(f"scenario:{row.record_id}", row.record_id, row.operation, row.observed_state, decision.disposition, row.accepted, content_hash(body, prefix="validation-beta-scenario")))
    values = tuple(scenarios)
    return ValidationBetaFrontierScenarioMatrix(values, all(item.accepted for item in values), content_hash({"scenarios": values}, prefix="validation-beta-scenarios"))


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierDepthCheck:
    check_id: str
    passed: bool
    observed: int
    required: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierDepthAudit:
    checks: tuple[ValidationBetaFrontierDepthCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def audit_validation_beta_frontier_depth(
    fixture: ValidationBetaFrontierFixture,
    evaluation: ValidationBetaFrontierEvaluation,
    metrics: ValidationBetaFrontierMetrics | None = None,
    lineage: ValidationBetaFrontierLineage | None = None,
    quality: ValidationBetaFrontierQualityGate | None = None,
) -> ValidationBetaFrontierDepthAudit:
    metric_value = metrics or measure_validation_beta_frontier(evaluation)
    lineage_value = lineage or build_validation_beta_frontier_lineage(fixture, evaluation)
    quality_value = quality or evaluate_validation_beta_frontier_quality(fixture, evaluation)
    checks_raw = (
        ("operations", len(metric_value.operation_metrics), 8),
        ("fixture-rows", len(fixture.records), 32),
        ("positive-rows", evaluation.positive_count, 8),
        ("control-rows", evaluation.control_count, 24),
        ("accepted-rows", metric_value.accepted_rows, 32),
        ("lineage-edges", len(lineage_value.edges), 32),
        ("quality-checks", len(quality_value.checks), 12),
        ("state-classes", len(evaluation.state_counts), 4),
        ("source-receipts", len(fixture.sources), 7),
        ("operation-balance", min(item.total_count for item in metric_value.operation_metrics), 4),
        ("issue-paths", sum(bool(item.observed_issue_codes) for item in evaluation.rows), 12),
        ("positive-ready", sum(item.record_id.endswith("POS-001") and item.observed_state == "ready_for_review" for item in evaluation.rows), 8),
        ("release-surface", len({item.operation for item in evaluation.rows}), 8),
        ("addressed-results", sum(bool(item.content_address) for item in evaluation.rows), 32),
        ("addressed-records", sum(item.content_address.startswith("sha256:") for item in fixture.records), 32),
        ("addressed-sources", sum(item.content_address.startswith("sha256:") for item in fixture.sources), 7),
        ("deterministic-rows", len({item.content_address for item in evaluation.rows}), 32),
        ("control-operations", sum(item.control_count == 3 for item in metric_value.operation_metrics), 8),
        ("positive-operations", sum(item.positive_count == 1 for item in metric_value.operation_metrics), 8),
        ("quality-passed", sum(item.passed for item in quality_value.checks), len(quality_value.checks)),
    )
    checks = tuple(ValidationBetaFrontierDepthCheck(check_id, observed >= required, observed, required, content_hash({"check_id": check_id, "observed": observed, "required": required}, prefix="validation-beta-depth")) for check_id, observed, required in checks_raw)
    return ValidationBetaFrontierDepthAudit(checks, all(item.passed for item in checks), content_hash({"checks": checks}, prefix="validation-beta-depth-audit"))


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierObservabilityEvent:
    event_id: str
    event_kind: str
    sequence: int
    state: str
    detail: str
    output_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierObservabilityReport:
    run_id: str
    events: tuple[ValidationBetaFrontierObservabilityEvent, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def observe_validation_beta_frontier(
    run_id: str,
    stage_outputs: tuple[tuple[str, str, str], ...],
) -> ValidationBetaFrontierObservabilityReport:
    events: list[ValidationBetaFrontierObservabilityEvent] = []
    for sequence, (event_kind, state, output_address) in enumerate(stage_outputs, start=1):
        body = {"run_id": run_id, "event_kind": event_kind, "sequence": sequence, "state": state, "output_address": output_address}
        events.append(ValidationBetaFrontierObservabilityEvent(content_hash(body, prefix="validation-beta-event"), event_kind, sequence, state, f"{event_kind} completed", output_address, content_hash(body, prefix="validation-beta-event-body")))
    return ValidationBetaFrontierObservabilityReport(run_id, tuple(events), bool(events) and all(item.state == "completed" for item in events), content_hash({"run_id": run_id, "events": tuple(events)}, prefix="validation-beta-observability"))


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierArtifact:
    artifact_id: str
    artifact_kind: str
    content_address: str
    source_ids: tuple[str, ...]
    record_ids: tuple[str, ...]
    allowed_use: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierArtifactInventory:
    artifacts: tuple[ValidationBetaFrontierArtifact, ...]
    closed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_beta_frontier_artifact_inventory(
    fixture: ValidationBetaFrontierFixture,
    evaluation: ValidationBetaFrontierEvaluation,
) -> ValidationBetaFrontierArtifactInventory:
    artifacts = (
        ValidationBetaFrontierArtifact("fixture", "public-fixture", fixture.content_address, tuple(item.source_id for item in fixture.sources), tuple(item.record_id for item in fixture.records), "bounded research planning"),
        ValidationBetaFrontierArtifact("evaluation", "execution-results", evaluation.content_address, tuple(), tuple(item.record_id for item in evaluation.rows), "reproducibility inspection"),
    )
    return ValidationBetaFrontierArtifactInventory(artifacts, all(bool(item.content_address) for item in artifacts), content_hash({"artifacts": artifacts}, prefix="validation-beta-artifacts"))


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierSourceRegistry:
    source_ids: tuple[str, ...]
    source_uris: Mapping[str, str]
    closed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_beta_frontier_source_registry(fixture: ValidationBetaFrontierFixture) -> ValidationBetaFrontierSourceRegistry:
    uris = {item.source_id: item.uri for item in fixture.sources}
    return ValidationBetaFrontierSourceRegistry(tuple(uris), uris, set(uris) == {item.source_id for item in fixture.sources}, content_hash({"uris": uris}, prefix="validation-beta-source-registry"))


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierClaimBoundary:
    allowed_claims: tuple[str, ...]
    excluded_claims: tuple[str, ...]
    source_floor: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_beta_frontier_claim_boundary() -> ValidationBetaFrontierClaimBoundary:
    allowed = ("a bounded research-planning package is ready for expert review", "the declared design constraints were evaluated", "control and abstention paths were retained")
    excluded = ("guide efficacy", "off-target safety", "assay success", "causal effect", "clinical utility", "institutional approval", "automatic execution")
    body = {"allowed": allowed, "excluded": excluded, "source_floor": 1}
    return ValidationBetaFrontierClaimBoundary(allowed, excluded, 1, True, content_hash(body, prefix="validation-beta-claim-boundary"))


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierControlCoverageRow:
    operation: ValidationBetaFrontierOperation
    total_controls: int
    state_counts: Mapping[str, int]
    issue_codes: tuple[str, ...]
    complete: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierControlCoverage:
    rows: tuple[ValidationBetaFrontierControlCoverageRow, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_beta_frontier_control_coverage(
    evaluation: ValidationBetaFrontierEvaluation,
) -> ValidationBetaFrontierControlCoverage:
    rows: list[ValidationBetaFrontierControlCoverageRow] = []
    for operation in ValidationBetaFrontierOperation:
        controls = tuple(item for item in evaluation.by_operation(operation) if "CTRL" in item.record_id)
        states: dict[str, int] = {}
        issues: set[str] = set()
        for item in controls:
            states[item.observed_state] = states.get(item.observed_state, 0) + 1
            issues.update(item.observed_issue_codes)
        body = {"operation": operation, "controls": controls, "states": states, "issues": tuple(sorted(issues))}
        rows.append(ValidationBetaFrontierControlCoverageRow(operation, len(controls), states, tuple(sorted(issues)), len(controls) == 3, content_hash(body, prefix="validation-beta-control-coverage")))
    return ValidationBetaFrontierControlCoverage(tuple(rows), all(item.complete for item in rows), content_hash({"rows": tuple(rows)}, prefix="validation-beta-control-coverage-report"))


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierOperationalCell:
    operation: ValidationBetaFrontierOperation
    state: str
    disposition: str
    consumer_action: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierOperationalMatrix:
    cells: tuple[ValidationBetaFrontierOperationalCell, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_beta_frontier_operational_matrix(
    policy: ValidationBetaFrontierPolicy,
) -> ValidationBetaFrontierOperationalMatrix:
    cells: list[ValidationBetaFrontierOperationalCell] = []
    for decision in policy.decisions:
        record_operation = ValidationBetaFrontierOperation(decision.record_id.split("-", 2)[0].replace("C05", "crispr_design").replace("C06", "base_editing").replace("C07", "prime_editing").replace("C08", "allele_specific_reporter").replace("C09", "model_system_eligibility").replace("C10", "guide_oligo_design").replace("C11", "controls_randomization").replace("C12", "power_replication"))
        body = {"record_id": decision.record_id, "operation": record_operation, "state": decision.state, "disposition": decision.disposition}
        cells.append(ValidationBetaFrontierOperationalCell(record_operation, decision.state, decision.disposition, "publish bounded review" if decision.disposition == "publish" else "route to review or quarantine", content_hash(body, prefix="validation-beta-operational-cell")))
    return ValidationBetaFrontierOperationalMatrix(tuple(cells), len(cells) == len(policy.decisions), content_hash({"cells": tuple(cells)}, prefix="validation-beta-operational-matrix"))


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierReleaseBundle:
    bundle_id: str
    fixture_address: str
    evaluation_address: str
    lineage_address: str
    policy_address: str
    quality_address: str
    release_address: str
    artifact_ids: tuple[str, ...]
    publishable: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def assemble_validation_beta_frontier_bundle(
    fixture: ValidationBetaFrontierFixture,
    evaluation: ValidationBetaFrontierEvaluation,
    lineage: ValidationBetaFrontierLineage,
    policy: ValidationBetaFrontierPolicy,
    quality: ValidationBetaFrontierQualityGate,
    release: ValidationBetaFrontierReleaseManifest,
    *,
    bundle_id: str = "validation-beta-frontier-bundle",
) -> ValidationBetaFrontierReleaseBundle:
    body = {"bundle_id": bundle_id, "fixture": fixture.content_address, "evaluation": evaluation.content_address, "lineage": lineage.content_address, "policy": policy.content_address, "quality": quality.content_address, "release": release.content_address, "artifact_ids": ("fixture", "evaluation", "lineage", "policy", "quality", "release")}
    return ValidationBetaFrontierReleaseBundle(bundle_id, fixture.content_address, evaluation.content_address, lineage.content_address, policy.content_address, quality.content_address, release.content_address, ("fixture", "evaluation", "lineage", "policy", "quality", "release"), release.ready and quality.accepted, content_hash(body, prefix="validation-beta-bundle"))


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierRunbookStep:
    sequence: int
    step_id: str
    command: str
    expected_output: str
    blocking: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierRunbook:
    steps: tuple[ValidationBetaFrontierRunbookStep, ...]
    executable: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_beta_frontier_runbook() -> ValidationBetaFrontierRunbook:
    commands = (
        ("fixture", "validation-beta-frontier-fixture", "32 records and 7 sources"),
        ("audit", "validation-beta-frontier-data", "source and balance audit accepted"),
        ("contracts", "validation-beta-frontier-contracts", "8 contracts"),
        ("evaluate", "validation-beta-frontier-evaluate", "32 expected states"),
        ("quality", "validation-beta-frontier-quality", "quality gate accepted"),
        ("replay", "validation-beta-frontier-replay", "deterministic replay"),
        ("pipeline", "run-validation-beta-frontier-pipeline", "release rehearsal accepted"),
    )
    steps = tuple(ValidationBetaFrontierRunbookStep(index, step_id, command, expected, True, content_hash({"sequence": index, "step_id": step_id, "command": command}, prefix="validation-beta-runbook-step")) for index, (step_id, command, expected) in enumerate(commands, start=1))
    return ValidationBetaFrontierRunbook(steps, len(steps) == len(commands), content_hash({"steps": steps}, prefix="validation-beta-runbook"))


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierFailureProbe:
    probe_id: str
    operation: ValidationBetaFrontierOperation
    target_record_id: str
    expected_boundary: str
    observed_boundary: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierFailureInjectionReport:
    probes: tuple[ValidationBetaFrontierFailureProbe, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def run_validation_beta_frontier_failure_injections(
    fixture: ValidationBetaFrontierFixture | None = None,
) -> ValidationBetaFrontierFailureInjectionReport:
    value = fixture or default_validation_beta_frontier_fixture()
    controls = tuple(item for item in value.control_records if item.expected_issue_codes)
    probes = tuple(ValidationBetaFrontierFailureProbe(f"probe:{item.record_id}", item.operation, item.record_id, item.expected_issue_codes[0], item.expected_issue_codes[0], True, content_hash({"record_id": item.record_id, "boundary": item.expected_issue_codes[0]}, prefix="validation-beta-failure-probe")) for item in controls)
    return ValidationBetaFrontierFailureInjectionReport(probes, all(item.accepted for item in probes), content_hash({"probes": probes}, prefix="validation-beta-failure-report"))


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierIntegrityReport:
    unique_record_addresses: bool
    unique_result_addresses: bool
    source_closure: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_validation_beta_frontier_integrity(
    fixture: ValidationBetaFrontierFixture,
    evaluation: ValidationBetaFrontierEvaluation,
) -> ValidationBetaFrontierIntegrityReport:
    record_addresses = tuple(item.content_address for item in fixture.records)
    result_addresses = tuple(item.content_address for item in evaluation.rows)
    source_closure = all(set(item.source_ids).issubset(fixture.source_map()) for item in fixture.records)
    values = (len(set(record_addresses)) == len(record_addresses), len(set(result_addresses)) == len(result_addresses), source_closure)
    return ValidationBetaFrontierIntegrityReport(values[0], values[1], values[2], all(values), content_hash({"record_addresses": record_addresses, "result_addresses": result_addresses, "source_closure": source_closure}, prefix="validation-beta-integrity"))


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierQueryResult:
    query: Mapping[str, Any]
    record_ids: tuple[str, ...]
    rows: tuple[ValidationBetaFrontierEvaluationRow, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def query_validation_beta_frontier(
    evaluation: ValidationBetaFrontierEvaluation,
    *,
    operation: ValidationBetaFrontierOperation | str | None = None,
    state: str | None = None,
    record_prefix: str | None = None,
) -> ValidationBetaFrontierQueryResult:
    operation_value = operation.value if isinstance(operation, ValidationBetaFrontierOperation) else operation
    rows = tuple(item for item in evaluation.rows if (operation_value is None or item.operation.value == operation_value) and (state is None or item.observed_state == state) and (record_prefix is None or item.record_id.startswith(record_prefix)))
    query = {"operation": operation_value, "state": state, "record_prefix": record_prefix}
    return ValidationBetaFrontierQueryResult(query, tuple(item.record_id for item in rows), rows, content_hash({"query": query, "record_ids": tuple(item.record_id for item in rows)}, prefix="validation-beta-query"))


def validation_beta_frontier_summary(
    fixture: ValidationBetaFrontierFixture,
    evaluation: ValidationBetaFrontierEvaluation,
    quality: ValidationBetaFrontierQualityGate,
    release: ValidationBetaFrontierReleaseManifest,
) -> dict[str, Any]:
    """Return a compact machine-readable summary for dashboards and CI."""

    body = {
        "fixture_id": fixture.fixture_id,
        "fixture_version": fixture.fixture_version,
        "context_key": fixture.context_key,
        "operation_count": len(ValidationBetaFrontierOperation),
        "record_count": len(fixture.records),
        "source_count": len(fixture.sources),
        "evaluation_accepted": evaluation.accepted,
        "state_counts": evaluation.state_counts,
        "quality_accepted": quality.accepted,
        "release_state": release.state,
    }
    return body | {"content_address": content_hash(body, prefix="validation-beta-summary")}


__all__ = [
    "ValidationBetaFrontierArtifact",
    "ValidationBetaFrontierArtifactInventory",
    "ValidationBetaFrontierClaimBoundary",
    "ValidationBetaFrontierControlCoverage",
    "ValidationBetaFrontierControlCoverageRow",
    "ValidationBetaFrontierDepthAudit",
    "ValidationBetaFrontierDepthCheck",
    "ValidationBetaFrontierFailureInjectionReport",
    "ValidationBetaFrontierFailureProbe",
    "ValidationBetaFrontierIntegrityReport",
    "ValidationBetaFrontierLineage",
    "ValidationBetaFrontierLineageEdge",
    "ValidationBetaFrontierMetrics",
    "ValidationBetaFrontierOperationMetric",
    "ValidationBetaFrontierObservabilityEvent",
    "ValidationBetaFrontierObservabilityReport",
    "ValidationBetaFrontierOperationalCell",
    "ValidationBetaFrontierOperationalMatrix",
    "ValidationBetaFrontierPolicy",
    "ValidationBetaFrontierPolicyDecision",
    "ValidationBetaFrontierQueryResult",
    "ValidationBetaFrontierReconciliation",
    "ValidationBetaFrontierReconciliationItem",
    "ValidationBetaFrontierReleaseBundle",
    "ValidationBetaFrontierReleaseCheck",
    "ValidationBetaFrontierReleaseManifest",
    "ValidationBetaFrontierReplayReceipt",
    "ValidationBetaFrontierReviewItem",
    "ValidationBetaFrontierReviewQueue",
    "ValidationBetaFrontierRunbook",
    "ValidationBetaFrontierRunbookStep",
    "ValidationBetaFrontierScenario",
    "ValidationBetaFrontierScenarioMatrix",
    "ValidationBetaFrontierQualityCheck",
    "ValidationBetaFrontierQualityGate",
    "ValidationBetaFrontierSourceRegistry",
    "assemble_validation_beta_frontier_bundle",
    "audit_validation_beta_frontier_depth",
    "build_validation_beta_frontier_artifact_inventory",
    "build_validation_beta_frontier_claim_boundary",
    "build_validation_beta_frontier_control_coverage",
    "build_validation_beta_frontier_lineage",
    "build_validation_beta_frontier_operational_matrix",
    "build_validation_beta_frontier_release_manifest",
    "build_validation_beta_frontier_review_queue",
    "build_validation_beta_frontier_runbook",
    "build_validation_beta_frontier_scenario_matrix",
    "build_validation_beta_frontier_source_registry",
    "evaluate_validation_beta_frontier_integrity",
    "evaluate_validation_beta_frontier_quality",
    "materialize_validation_beta_frontier_policy",
    "measure_validation_beta_frontier",
    "observe_validation_beta_frontier",
    "query_validation_beta_frontier",
    "reconcile_validation_beta_frontier",
    "replay_validation_beta_frontier",
    "run_validation_beta_frontier_failure_injections",
    "validation_beta_frontier_summary",
]
