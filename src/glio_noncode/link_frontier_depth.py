"""Operation-specific depth checks for Domain 10 link frontier evidence.

The generic fixture gate verifies dispatch, expected states, and source closure.
This module verifies the shape of each operation's actual output so a passing
fixture cannot hide a shallow adapter or a dropped evidence field.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_frontier_contracts import LinkFrontierContractRegistry, default_link_frontier_contracts
from .link_frontier_fixture_eval import LinkFrontierEvaluation, evaluate_link_frontier_fixture
from .link_frontier_public_data import (
    LinkFrontierFixture,
    LinkFrontierOperation,
    LinkFrontierRole,
    default_link_frontier_fixture,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkFrontierDepthCheck:
    check_id: str
    operation: LinkFrontierOperation | None
    passed: bool
    expected: Any
    observed: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkFrontierOperationDepth:
    operation: LinkFrontierOperation
    check_count: int
    passed_count: int
    issue_codes: tuple[str, ...]
    output_fields: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkFrontierDepthAudit:
    fixture_id: str
    operations: tuple[LinkFrontierOperationDepth, ...]
    checks: tuple[LinkFrontierDepthCheck, ...]
    accepted: bool
    content_address: str

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "failed_check_ids": list(self.failed_check_ids),
            "passed_count": self.passed_count,
        }


def _check(
    check_id: str,
    operation: LinkFrontierOperation | None,
    passed: bool,
    expected: Any,
    observed: Any,
    detail: str,
) -> LinkFrontierDepthCheck:
    body = {
        "check_id": check_id,
        "operation": operation,
        "passed": passed,
        "expected": expected,
        "observed": observed,
        "detail": detail,
    }
    return LinkFrontierDepthCheck(**body, content_address=content_hash(body))


def _positive_execution(fixture: LinkFrontierFixture, evaluation: LinkFrontierEvaluation, operation: LinkFrontierOperation):
    record = next(item for item in fixture.records if item.operation is operation and item.role is LinkFrontierRole.POSITIVE)
    return record, evaluation.execution_map()[record.record_id]


def _control_execution(fixture: LinkFrontierFixture, evaluation: LinkFrontierEvaluation, operation: LinkFrontierOperation, suffix: str):
    record = next(item for item in fixture.records if item.record_id == f"{operation.name.replace('_', '')[:3]}{suffix}")
    return record, evaluation.execution_map()[record.record_id]


def _dependence_checks(fixture: LinkFrontierFixture, evaluation: LinkFrontierEvaluation) -> list[LinkFrontierDepthCheck]:
    _record, execution = _positive_execution(fixture, evaluation, LinkFrontierOperation.DEPENDENCE_CORRECTION)
    links = execution.output.get("links", [])
    checks = [
        _check("C13:links_present", LinkFrontierOperation.DEPENDENCE_CORRECTION, bool(links), True, bool(links), "positive dependence output has links"),
        _check("C13:raw_support_retained", LinkFrontierOperation.DEPENDENCE_CORRECTION, all("raw_support" in row for row in links), True, tuple(tuple(sorted(row)) for row in links), "raw support remains inspectable"),
        _check("C13:corrected_support_bounded", LinkFrontierOperation.DEPENDENCE_CORRECTION, all(0 <= row["corrected_support"] <= row["raw_support"] <= 1 for row in links), True, tuple(row.get("corrected_support") for row in links), "correction never increases support"),
        _check("C13:group_size_retained", LinkFrontierOperation.DEPENDENCE_CORRECTION, all(row.get("group_size", 0) >= 1 for row in links), True, tuple(row.get("group_size") for row in links), "dependence group size is explicit"),
        _check("C13:context_retained", LinkFrontierOperation.DEPENDENCE_CORRECTION, all(row.get("context_key") == fixture.context_key for row in links), fixture.context_key, tuple(row.get("context_key") for row in links), "context is copied into each corrected link"),
        _check("C13:zero_control", LinkFrontierOperation.DEPENDENCE_CORRECTION, "zero_corrected_support" in evaluation.execution_map()["C13-CTRL-001"].issue_codes, True, evaluation.execution_map()["C13-CTRL-001"].issue_codes, "zero support is not silently accepted"),
        _check("C13:address", LinkFrontierOperation.DEPENDENCE_CORRECTION, bool(execution.output.get("content_address")), True, bool(execution.output.get("content_address")), "operation output is addressed"),
    ]
    return checks


def _ranking_checks(fixture: LinkFrontierFixture, evaluation: LinkFrontierEvaluation) -> list[LinkFrontierDepthCheck]:
    _record, execution = _positive_execution(fixture, evaluation, LinkFrontierOperation.TARGET_GENE_RANKING)
    ranks = execution.output.get("ranks", [])
    checks = [
        _check("C14:ranks_present", LinkFrontierOperation.TARGET_GENE_RANKING, bool(ranks), True, bool(ranks), "positive ranking output has ranks"),
        _check("C14:rank_sequence", LinkFrontierOperation.TARGET_GENE_RANKING, tuple(row.get("rank") for row in ranks) == tuple(range(1, len(ranks) + 1)), True, tuple(row.get("rank") for row in ranks), "ranks are contiguous"),
        _check("C14:gene_identity", LinkFrontierOperation.TARGET_GENE_RANKING, all(row.get("gene_id") for row in ranks), True, tuple(row.get("gene_id") for row in ranks), "gene identity is retained"),
        _check("C14:component_scores", LinkFrontierOperation.TARGET_GENE_RANKING, all(row.get("component_scores") is not None for row in ranks), True, tuple(row.get("component_scores") for row in ranks), "component scores are retained"),
        _check("C14:alternative_gene", LinkFrontierOperation.TARGET_GENE_RANKING, len({row.get("gene_id") for row in ranks}) > 1, True, tuple(row.get("gene_id") for row in ranks), "alternative genes remain visible"),
        _check("C14:top_mapping", LinkFrontierOperation.TARGET_GENE_RANKING, execution.output.get("top_gene_by_variant", {}).get("v1") == "GENE1", "GENE1", execution.output.get("top_gene_by_variant"), "top mapping is deterministic"),
        _check("C14:zero_control", LinkFrontierOperation.TARGET_GENE_RANKING, "zero_rank_support" in evaluation.execution_map()["C14-CTRL-001"].issue_codes, True, evaluation.execution_map()["C14-CTRL-001"].issue_codes, "zero score remains review"),
        _check("C14:address", LinkFrontierOperation.TARGET_GENE_RANKING, bool(execution.output.get("content_address")), True, bool(execution.output.get("content_address")), "operation output is addressed"),
    ]
    return checks


def _calibration_checks(fixture: LinkFrontierFixture, evaluation: LinkFrontierEvaluation) -> list[LinkFrontierDepthCheck]:
    record, execution = _positive_execution(fixture, evaluation, LinkFrontierOperation.CALIBRATION_ABSTENTION)
    decisions = execution.output.get("decisions", [])
    checks = [
        _check("C15:decision_present", LinkFrontierOperation.CALIBRATION_ABSTENTION, bool(decisions), True, bool(decisions), "positive calibration output has decisions"),
        _check("C15:accepted_id", LinkFrontierOperation.CALIBRATION_ABSTENTION, execution.output.get("accepted_ids") == ["cal-1"], ["cal-1"], execution.output.get("accepted_ids"), "calibrated link is accepted"),
        _check("C15:uncertainty_retained", LinkFrontierOperation.CALIBRATION_ABSTENTION, all("uncertainty" in row for row in decisions), True, tuple(row.get("uncertainty") for row in decisions), "uncertainty is retained"),
        _check("C15:error_retained", LinkFrontierOperation.CALIBRATION_ABSTENTION, all("calibration_error" in row for row in decisions), True, tuple(row.get("calibration_error") for row in decisions), "calibration error is retained"),
        _check("C15:thresholds_declared", LinkFrontierOperation.CALIBRATION_ABSTENTION, "maximum_uncertainty" in record.payload and "maximum_calibration_error" in record.payload, True, record.payload, "thresholds are fixture data"),
        _check("C15:uncertainty_control", LinkFrontierOperation.CALIBRATION_ABSTENTION, "link_uncertainty_high" in evaluation.execution_map()["C15-CTRL-001"].issue_codes, True, evaluation.execution_map()["C15-CTRL-001"].issue_codes, "high uncertainty abstains"),
        _check("C15:error_control", LinkFrontierOperation.CALIBRATION_ABSTENTION, "link_calibration_error_high" in evaluation.execution_map()["C15-CTRL-002"].issue_codes, True, evaluation.execution_map()["C15-CTRL-002"].issue_codes, "high error abstains"),
        _check("C15:address", LinkFrontierOperation.CALIBRATION_ABSTENTION, bool(execution.output.get("content_address")), True, bool(execution.output.get("content_address")), "operation output is addressed"),
    ]
    return checks


def _publication_checks(fixture: LinkFrontierFixture, evaluation: LinkFrontierEvaluation) -> list[LinkFrontierDepthCheck]:
    _record, execution = _positive_execution(fixture, evaluation, LinkFrontierOperation.EVIDENCE_PUBLICATION)
    output = execution.output
    checks = [
        _check("C16:published_state", LinkFrontierOperation.EVIDENCE_PUBLICATION, output.get("state") == "published", "published", output.get("state"), "publication state is explicit"),
        _check("C16:bundle_address", LinkFrontierOperation.EVIDENCE_PUBLICATION, bool(output.get("bundle_address")), True, bool(output.get("bundle_address")), "bundle address is retained"),
        _check("C16:records_address", LinkFrontierOperation.EVIDENCE_PUBLICATION, bool(output.get("records_address")), True, bool(output.get("records_address")), "records address is retained"),
        _check("C16:link_ids", LinkFrontierOperation.EVIDENCE_PUBLICATION, output.get("link_ids") == ["pub-1", "pub-2"], ["pub-1", "pub-2"], output.get("link_ids"), "link IDs are deterministic"),
        _check("C16:context", LinkFrontierOperation.EVIDENCE_PUBLICATION, output.get("context_key") == fixture.context_key, fixture.context_key, output.get("context_key"), "publication context is exact"),
        _check("C16:context_control", LinkFrontierOperation.EVIDENCE_PUBLICATION, "publication_context_mismatch" in evaluation.execution_map()["C16-CTRL-001"].issue_codes, True, evaluation.execution_map()["C16-CTRL-001"].issue_codes, "cross-context publication is blocked"),
        _check("C16:source_control", LinkFrontierOperation.EVIDENCE_PUBLICATION, "invalid_publication_input" in evaluation.execution_map()["C16-CTRL-002"].issue_codes, True, evaluation.execution_map()["C16-CTRL-002"].issue_codes, "missing source is blocked"),
        _check("C16:address", LinkFrontierOperation.EVIDENCE_PUBLICATION, bool(execution.content_address), True, bool(execution.content_address), "execution output is addressed"),
    ]
    return checks


def _contract_checks(contracts: LinkFrontierContractRegistry) -> list[LinkFrontierDepthCheck]:
    checks: list[LinkFrontierDepthCheck] = []
    for contract in contracts.contracts:
        prefix = contract.operation.value
        checks.extend(
            (
                _check(f"contract:{prefix}:fields", contract.operation, bool(contract.required_payload_fields), True, contract.required_payload_fields, "required fields are declared"),
                _check(f"contract:{prefix}:positive", contract.operation, bool(contract.positive_states), True, contract.positive_states, "positive state is declared"),
                _check(f"contract:{prefix}:controls", contract.operation, bool(contract.control_states), True, contract.control_states, "control states are declared"),
                _check(f"contract:{prefix}:issues", contract.operation, bool(contract.issue_vocabulary), True, contract.issue_vocabulary, "issue vocabulary is declared"),
                _check(f"contract:{prefix}:limits", contract.operation, len(contract.prohibited_claims) >= 4, True, contract.prohibited_claims, "interpretation limits are declared"),
            )
        )
    return checks


def run_link_frontier_depth_audit(
    fixture: LinkFrontierFixture | None = None,
    *,
    evaluation: LinkFrontierEvaluation | None = None,
    contracts: LinkFrontierContractRegistry | None = None,
) -> LinkFrontierDepthAudit:
    fixture = fixture or default_link_frontier_fixture()
    evaluation = evaluation or evaluate_link_frontier_fixture(fixture)
    contracts = contracts or default_link_frontier_contracts()
    checks = (
        _dependence_checks(fixture, evaluation)
        + _ranking_checks(fixture, evaluation)
        + _calibration_checks(fixture, evaluation)
        + _publication_checks(fixture, evaluation)
        + _contract_checks(contracts)
    )
    operation_reports: list[LinkFrontierOperationDepth] = []
    for operation in LinkFrontierOperation:
        operation_checks = tuple(item for item in checks if item.operation is operation)
        positive = next(item for item in evaluation.executions if item.operation is operation and item.role is LinkFrontierRole.POSITIVE)
        fields = tuple(sorted(positive.output))
        issue_codes = tuple(sorted({code for item in evaluation.executions if item.operation is operation for code in item.issue_codes}))
        body = {
            "operation": operation,
            "check_count": len(operation_checks),
            "passed_count": sum(item.passed for item in operation_checks),
            "issue_codes": issue_codes,
            "output_fields": fields,
            "accepted": bool(operation_checks) and all(item.passed for item in operation_checks),
        }
        operation_reports.append(LinkFrontierOperationDepth(**body, content_address=content_hash(body)))
    body = {
        "fixture_id": fixture.fixture_id,
        "operations": tuple(operation_reports),
        "checks": tuple(checks),
        "accepted": bool(checks) and all(item.passed for item in checks),
    }
    return LinkFrontierDepthAudit(**body, content_address=content_hash(body))


__all__ = [
    "LinkFrontierDepthAudit",
    "LinkFrontierDepthCheck",
    "LinkFrontierOperationDepth",
    "run_link_frontier_depth_audit",
]
