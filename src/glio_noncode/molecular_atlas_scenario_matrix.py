"""Independent state and review scenarios for Domain 05 C05–C08."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .molecular_atlas_fixture_eval import MolecularAtlasEvaluationReport
from .molecular_atlas_public_data import (
    MolecularAtlasFixture,
    MolecularAtlasOperation,
    MolecularAtlasRole,
    default_molecular_atlas_fixture,
)
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class MolecularAtlasScenarioResult:
    """One independent scenario expectation and observation."""

    scenario_id: str
    operation: MolecularAtlasOperation
    source_record_id: str
    expected_state: str
    observed_state: str
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    expected_review: bool
    observed_review: bool
    passed: bool
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.scenario_id, "molecular atlas scenario id")
        require_non_empty(self.source_record_id, "molecular atlas scenario record id")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MolecularAtlasScenarioMatrix:
    """Scenario suite covering state separation and histone review states."""

    fixture_id: str
    results: tuple[MolecularAtlasScenarioResult, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return all(result.passed for result in self.results)

    @property
    def failed_scenario_ids(self) -> tuple[str, ...]:
        return tuple(result.scenario_id for result in self.results if not result.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "failed_scenario_ids": list(self.failed_scenario_ids),
        }


def _address(body: Any) -> str:
    return content_hash(body)


def evaluate_molecular_atlas_scenarios(
    fixture: MolecularAtlasFixture | None = None,
    *,
    report: MolecularAtlasEvaluationReport,
) -> MolecularAtlasScenarioMatrix:
    """Evaluate named floors from sanitized execution receipts."""

    selected = fixture or default_molecular_atlas_fixture()
    by_id = {receipt.record_id: receipt for receipt in report.receipts}
    definitions = (
        (
            "idh-mutant-supported",
            MolecularAtlasOperation.IDH_MUTANT_PROFILE,
            "C05-POS-001",
            "supported",
            (),
            False,
            "exact IDH-mutant context supports one match",
        ),
        (
            "idh-mutant-context-mismatch",
            MolecularAtlasOperation.IDH_MUTANT_PROFILE,
            "C05-CTRL-001",
            "out_of_domain",
            ("state_context_mismatch",),
            True,
            "IDH-mutant context drift remains outside domain",
        ),
        (
            "idh-mutant-absent",
            MolecularAtlasOperation.IDH_MUTANT_PROFILE,
            "C05-CTRL-002",
            "abstained",
            ("no_state_atlas_overlap",),
            True,
            "IDH-mutant absence is explicit abstention",
        ),
        (
            "idh-mutant-ambiguous",
            MolecularAtlasOperation.IDH_MUTANT_PROFILE,
            "C05-CTRL-003",
            "ambiguous",
            ("ambiguous_state_match",),
            True,
            "multiple IDH-mutant overlaps remain ambiguous",
        ),
        (
            "idh-wildtype-supported",
            MolecularAtlasOperation.IDH_WILDTYPE_PROFILE,
            "C06-POS-001",
            "supported",
            (),
            False,
            "exact IDH-wildtype context supports one match",
        ),
        (
            "idh-wildtype-context-mismatch",
            MolecularAtlasOperation.IDH_WILDTYPE_PROFILE,
            "C06-CTRL-001",
            "out_of_domain",
            ("state_context_mismatch",),
            True,
            "IDH-wildtype context drift remains outside domain",
        ),
        (
            "idh-wildtype-absent",
            MolecularAtlasOperation.IDH_WILDTYPE_PROFILE,
            "C06-CTRL-002",
            "abstained",
            ("no_state_atlas_overlap",),
            True,
            "IDH-wildtype absence is explicit abstention",
        ),
        (
            "idh-wildtype-ambiguous",
            MolecularAtlasOperation.IDH_WILDTYPE_PROFILE,
            "C06-CTRL-003",
            "ambiguous",
            ("ambiguous_state_match",),
            True,
            "multiple IDH-wildtype overlaps remain ambiguous",
        ),
        (
            "h3k27-supported",
            MolecularAtlasOperation.H3K27_ALTERED_PROFILE,
            "C07-POS-001",
            "supported",
            (),
            False,
            "exact H3K27-altered context supports one match",
        ),
        (
            "h3k27-context-mismatch",
            MolecularAtlasOperation.H3K27_ALTERED_PROFILE,
            "C07-CTRL-001",
            "out_of_domain",
            ("state_context_mismatch",),
            True,
            "H3K27-altered age drift remains outside domain",
        ),
        (
            "h3k27-absent",
            MolecularAtlasOperation.H3K27_ALTERED_PROFILE,
            "C07-CTRL-002",
            "abstained",
            ("no_state_atlas_overlap",),
            True,
            "H3K27-altered absence is explicit abstention",
        ),
        (
            "h3k27-ambiguous",
            MolecularAtlasOperation.H3K27_ALTERED_PROFILE,
            "C07-CTRL-003",
            "ambiguous",
            ("ambiguous_state_match",),
            True,
            "multiple H3K27-altered overlaps remain ambiguous",
        ),
        (
            "histone-supported",
            MolecularAtlasOperation.HISTONE_HARMONIZATION,
            "C08-POS-001",
            "supported",
            (),
            False,
            "concordant histone replicates support an observed interval",
        ),
        (
            "histone-disagreement",
            MolecularAtlasOperation.HISTONE_HARMONIZATION,
            "C08-CTRL-002",
            "ambiguous",
            ("histone_signal_disagreement",),
            True,
            "large histone signal spread remains ambiguous",
        ),
        (
            "histone-single-replicate",
            MolecularAtlasOperation.HISTONE_HARMONIZATION,
            "C08-CTRL-003",
            "partial",
            ("histone_single_replicate",),
            True,
            "single histone replicate remains partial",
        ),
    )
    results: list[MolecularAtlasScenarioResult] = []
    records = selected.record_map()
    for (
        scenario_id,
        operation,
        record_id,
        expected_state,
        expected_issue_codes,
        expected_review,
        detail,
    ) in definitions:
        receipt = by_id[record_id]
        record = records[record_id]
        observed_review = receipt.adapter_state != "supported"
        expected_role = (
            MolecularAtlasRole.CONTROL if expected_review else MolecularAtlasRole.POSITIVE
        )
        passed = (
            receipt.operation is operation
            and record.role is expected_role
            and receipt.adapter_state == expected_state
            and set(expected_issue_codes) <= set(receipt.observed_issue_codes)
            and observed_review == expected_review
        )
        body = {
            "scenario_id": scenario_id,
            "operation": operation,
            "source_record_id": record_id,
            "expected_state": expected_state,
            "observed_state": receipt.adapter_state,
            "expected_issue_codes": expected_issue_codes,
            "observed_issue_codes": receipt.observed_issue_codes,
            "expected_review": expected_review,
            "observed_review": observed_review,
            "passed": passed,
            "detail": detail,
        }
        results.append(MolecularAtlasScenarioResult(**body, content_address=_address(body)))
    body = {"fixture_id": selected.fixture_id, "results": results}
    return MolecularAtlasScenarioMatrix(selected.fixture_id, tuple(results), _address(body))


__all__ = [
    "MolecularAtlasScenarioMatrix",
    "MolecularAtlasScenarioResult",
    "evaluate_molecular_atlas_scenarios",
]
