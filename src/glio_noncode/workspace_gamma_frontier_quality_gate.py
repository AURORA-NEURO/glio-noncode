"""Composable quality gate for the C09-C12 release rehearsal."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .workspace_gamma_frontier_contracts import GammaFrontierContractRegistry
from .workspace_gamma_frontier_fixture_eval import GammaFrontierEvaluation
from .workspace_gamma_frontier_lineage import GammaFrontierLineageGraph
from .workspace_gamma_frontier_projection_assertions import GammaFrontierProjectionAudit
from .workspace_gamma_frontier_public_data import GammaFrontierDataAudit, GammaFrontierFixture
from .workspace_gamma_frontier_reconciliation import GammaFrontierReconciliation
from .workspace_gamma_frontier_schema import GammaFrontierSchemaManifest


@dataclass(frozen=True, slots=True)
class GammaFrontierGateCheck:
    """One named gate check with severity and observed evidence."""

    check_id: str
    passed: bool
    blocking: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GammaFrontierQualityGate:
    """Quality gate report retaining all checks and failed IDs."""

    fixture_id: str
    checks: tuple[GammaFrontierGateCheck, ...]
    accepted: bool
    blocking_failures: tuple[str, ...]
    advisory_failures: tuple[str, ...]
    content_address: str

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed_count": self.passed_count}


def _check(
    check_id: str, passed: bool, blocking: bool, observed: Any, required: Any, detail: str
) -> GammaFrontierGateCheck:
    body = {
        "check_id": check_id,
        "passed": passed,
        "blocking": blocking,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return GammaFrontierGateCheck(**body, content_address=content_hash(body))


def evaluate_gamma_frontier_quality(
    fixture: GammaFrontierFixture,
    evaluation: GammaFrontierEvaluation,
    data_audit: GammaFrontierDataAudit,
    contracts: GammaFrontierContractRegistry,
    schema: GammaFrontierSchemaManifest,
    lineage: GammaFrontierLineageGraph,
    reconciliation: GammaFrontierReconciliation,
    projection_audit: GammaFrontierProjectionAudit,
) -> GammaFrontierQualityGate:
    """Require data, execution, contract, schema, lineage, and projection evidence."""

    checks = [
        _check(
            "data-audit",
            data_audit.accepted,
            True,
            data_audit.accepted,
            True,
            "public aggregate fixture audit accepted",
        ),
        _check(
            "fixture-evaluation",
            evaluation.accepted,
            True,
            evaluation.accepted,
            True,
            "all positive and control expectations matched",
        ),
        _check(
            "operation-contracts",
            len(contracts.contracts) == 4
            and {item.operation for item in contracts.contracts}
            == set(item.operation for item in fixture.records),
            True,
            len(contracts.contracts),
            4,
            "four surface contracts are registered",
        ),
        _check(
            "operation-schemas",
            len(schema.operations) == 4
            and all(
                schema.by_operation(item.operation).required_fields()
                for item in contracts.contracts
            ),
            True,
            len(schema.operations),
            4,
            "every surface has required fields",
        ),
        _check(
            "lineage-nodes",
            len(lineage.nodes) >= len(fixture.records) + len(fixture.sources) + 1,
            True,
            len(lineage.nodes),
            len(fixture.records) + len(fixture.sources) + 1,
            "source and row nodes are retained",
        ),
        _check(
            "lineage-edges",
            len(lineage.edges) >= len(fixture.records) * 2,
            True,
            len(lineage.edges),
            len(fixture.records) * 2,
            "source-to-output edges are retained",
        ),
        _check(
            "reconciliation",
            reconciliation.accepted,
            True,
            reconciliation.accepted,
            True,
            "expected and observed states reconcile",
        ),
        _check(
            "projection-audit",
            projection_audit.accepted,
            True,
            projection_audit.accepted,
            True,
            "serialized projection shape is valid",
        ),
        _check(
            "boundary",
            fixture.evidence_boundary == "public_aggregate_non_patient",
            False,
            fixture.evidence_boundary,
            "public_aggregate_non_patient",
            "fixture boundary remains explicit",
        ),
        _check(
            "control-retention",
            len(fixture.control_records) >= 12,
            False,
            len(fixture.control_records),
            12,
            "negative controls remain in the release evidence",
        ),
    ]
    blocking = tuple(item.check_id for item in checks if not item.passed and item.blocking)
    advisory = tuple(item.check_id for item in checks if not item.passed and not item.blocking)
    body = {
        "fixture_id": fixture.fixture_id,
        "checks": tuple(checks),
        "accepted": not blocking,
        "blocking_failures": blocking,
        "advisory_failures": advisory,
    }
    return GammaFrontierQualityGate(**body, content_address=content_hash(body))


__all__ = ["GammaFrontierGateCheck", "GammaFrontierQualityGate", "evaluate_gamma_frontier_quality"]
