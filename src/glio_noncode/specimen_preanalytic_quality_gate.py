"""Integrated release gate for Domain 03 C13-C16."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .specimen_preanalytic_bundle import SpecimenPreanalyticEvidenceBundleBuilder
from .specimen_preanalytic_contracts import default_specimen_preanalytic_contracts
from .specimen_preanalytic_fixture_eval import evaluate_specimen_preanalytic_fixture
from .specimen_preanalytic_lineage import (
    audit_specimen_preanalytic_lineage,
    build_specimen_preanalytic_lineage,
)
from .specimen_preanalytic_public_data import (
    SpecimenPreanalyticFixtureCatalog,
    audit_specimen_preanalytic_data,
)
from .specimen_preanalytic_reconciliation import (
    audit_specimen_preanalytic_receipt_index,
    build_specimen_preanalytic_receipt_index,
)
from .specimen_preanalytic_replay import replay_specimen_preanalytic_fixture
from .specimen_preanalytic_runtime import (
    SpecimenPreanalyticPipelineRequest,
    run_specimen_preanalytic_pipeline,
)
from .specimen_preanalytic_scenario_matrix import evaluate_specimen_preanalytic_scenarios


@dataclass(frozen=True, slots=True)
class SpecimenPreanalyticQualityCheck:
    check_id: str
    passed: bool
    observed: Any
    expected: Any
    message: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenPreanalyticQualityGateReport:
    fixture_id: str
    state: str
    checks: tuple[SpecimenPreanalyticQualityCheck, ...]
    evaluation_address: str
    replay_address: str
    scenario_address: str
    lineage_address: str
    reconciliation_address: str
    bundle_address: str
    runtime_address: str
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == "accepted" and all(check.passed for check in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check.check_id for check in self.checks if not check.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed": self.passed,
            "failed_check_ids": self.failed_check_ids,
            "check_count": len(self.checks),
        }


def evaluate_specimen_preanalytic_quality_gate(
    catalog: SpecimenPreanalyticFixtureCatalog,
) -> SpecimenPreanalyticQualityGateReport:
    """Run the full evidence, replay, graph, bundle, reconciliation, and runtime gate."""

    data = audit_specimen_preanalytic_data(catalog)
    evaluation = evaluate_specimen_preanalytic_fixture(catalog)
    replay = replay_specimen_preanalytic_fixture(catalog)
    scenarios = evaluate_specimen_preanalytic_scenarios(catalog)
    contracts = default_specimen_preanalytic_contracts()
    graph = build_specimen_preanalytic_lineage(catalog)
    graph_audit = audit_specimen_preanalytic_lineage(graph)
    index = build_specimen_preanalytic_receipt_index(catalog)
    reconciliation = audit_specimen_preanalytic_receipt_index(catalog, index)
    bundle = SpecimenPreanalyticEvidenceBundleBuilder().build(catalog)
    bundle_ok = SpecimenPreanalyticEvidenceBundleBuilder().verify(bundle)
    request = SpecimenPreanalyticPipelineRequest(
        "quality-gate-runtime",
        "examples/specimen-preanalytic-public-aggregate.json",
        catalog.context_key,
        "accepted_only",
    )
    runtime = run_specimen_preanalytic_pipeline(request, catalog)
    checks = (
        _check("data-audit", data.passed, data.state, "accepted", "public data boundary"),
        _check("evaluation", evaluation.passed, evaluation.state, "accepted", "fixture evaluator"),
        _check(
            "receipt-floor",
            len(evaluation.receipts) == 12,
            len(evaluation.receipts),
            12,
            "one receipt per record",
        ),
        _check(
            "evaluation-check-floor",
            len(evaluation.checks) >= 120,
            len(evaluation.checks),
            ">=120",
            "deep fixture assertions",
        ),
        _check(
            "positive-floor",
            sum(receipt.role == "positive" for receipt in evaluation.receipts) == 4,
            4,
            4,
            "positive floor",
        ),
        _check(
            "control-floor",
            sum(receipt.role == "control" for receipt in evaluation.receipts) == 8,
            8,
            8,
            "control floor",
        ),
        _check(
            "operation-coverage",
            set(evaluation.operation_ids) == {item.operation.value for item in contracts.contracts},
            evaluation.operation_ids,
            tuple(item.operation.value for item in contracts.contracts),
            "contract coverage",
        ),
        _check(
            "contracts",
            len(contracts.contracts) == 4,
            len(contracts.contracts),
            4,
            "four operation contracts",
        ),
        _check("replay", replay.passed, replay.state, "accepted", "replay expectation"),
        _check("scenarios", scenarios.passed, scenarios.state, "accepted", "scenario transitions"),
        _check(
            "scenario-count",
            len(scenarios.scenarios) == 12,
            len(scenarios.scenarios),
            12,
            "scenario floor",
        ),
        _check("lineage", graph_audit.passed, graph_audit.state, "accepted", "lineage graph audit"),
        _check(
            "lineage-shape",
            (len(graph.nodes), len(graph.edges)) == (29, 28),
            (len(graph.nodes), len(graph.edges)),
            (29, 28),
            "lineage shape",
        ),
        _check(
            "reconciliation",
            reconciliation.passed,
            reconciliation.state,
            "accepted",
            "receipt-index reconciliation",
        ),
        _check(
            "reconciliation-check-floor",
            len(reconciliation.checks) == 16,
            len(reconciliation.checks),
            16,
            "reconciliation checks",
        ),
        _check(
            "bundle-state",
            bundle.state == "accepted",
            bundle.state,
            "accepted",
            "accepted bundle state",
        ),
        _check("bundle-address", bundle_ok, bundle.content_address, "verified", "bundle address"),
        _check(
            "bundle-entry-floor",
            len(bundle.entries) == 12,
            len(bundle.entries),
            12,
            "bundle entry floor",
        ),
        _check(
            "runtime-published",
            runtime.published,
            runtime.state,
            "published",
            "runtime publication",
        ),
        _check(
            "runtime-stage-floor",
            len(runtime.stage_receipts) == 4,
            len(runtime.stage_receipts),
            4,
            "four runtime stages",
        ),
        _check(
            "runtime-stage-conservation",
            all(stage.input_count == stage.output_count for stage in runtime.stage_receipts),
            True,
            True,
            "runtime count conservation",
        ),
        _check(
            "runtime-address",
            runtime.content_address.startswith("sha256:"),
            runtime.content_address,
            "sha256:<digest>",
            "runtime address",
        ),
        _check(
            "deterministic-evaluation",
            evaluation.content_address
            == evaluate_specimen_preanalytic_fixture(catalog).content_address,
            True,
            True,
            "evaluation determinism",
        ),
        _check(
            "sanitized-evaluation",
            not _forbidden_keys(evaluation.to_dict()),
            True,
            True,
            "evaluation projection boundary",
        ),
        _check(
            "sanitized-runtime",
            not _forbidden_keys(runtime.to_dict()),
            True,
            True,
            "runtime projection boundary",
        ),
    )
    state = "accepted" if all(check.passed for check in checks) else "review"
    body = {
        "fixture_id": catalog.fixture_id,
        "state": state,
        "checks": checks,
        "evaluation_address": evaluation.content_address,
        "replay_address": replay.content_address,
        "scenario_address": scenarios.content_address,
        "lineage_address": graph.content_address,
        "reconciliation_address": reconciliation.content_address,
        "bundle_address": bundle.content_address,
        "runtime_address": runtime.content_address,
    }
    return SpecimenPreanalyticQualityGateReport(
        catalog.fixture_id,
        state,
        checks,
        evaluation.content_address,
        replay.content_address,
        scenarios.content_address,
        graph.content_address,
        reconciliation.content_address,
        bundle.content_address,
        runtime.content_address,
        content_hash(body),
    )


def _check(
    check_id: str, passed: bool, observed: Any, expected: Any, message: str
) -> SpecimenPreanalyticQualityCheck:
    return SpecimenPreanalyticQualityCheck(check_id, bool(passed), observed, expected, message)


def _forbidden_keys(value: Any) -> tuple[str, ...]:
    forbidden = {
        "records",
        "raw_records",
        "payload",
        "patient_id",
        "subject_id",
        "medical_record_number",
        "sample_patient_id",
        "participant_id",
        "case_uuid",
        "individual_id",
        "person_id",
    }
    found: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).lower()
            if normalized in forbidden:
                found.add(normalized)
            found.update(_forbidden_keys(nested))
    elif isinstance(value, (list, tuple)):
        for nested in value:
            found.update(_forbidden_keys(nested))
    return tuple(sorted(found))


__all__ = [
    "SpecimenPreanalyticQualityCheck",
    "SpecimenPreanalyticQualityGateReport",
    "evaluate_specimen_preanalytic_quality_gate",
]
