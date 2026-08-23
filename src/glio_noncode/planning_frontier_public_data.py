"""Public aggregate receipts and deterministic D13 C09-C12 scenarios."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .planning_frontier_contracts import (
    PLANNING_FRONTIER_BOUNDARY,
    PLANNING_FRONTIER_CONTEXT_KEY,
    PLANNING_FRONTIER_FOREIGN_CONTEXT,
    PLANNING_FRONTIER_VERSION,
    PlanningFixture,
    PlanningOperation,
    PlanningRecord,
    PlanningRole,
    PlanningSourceReceipt,
    PlanningState,
)
from .serialization import content_hash, jsonable


PLANNING_FRONTIER_SOURCE_COUNT = 5
PLANNING_FRONTIER_RECORD_COUNT = 16
PLANNING_FRONTIER_POSITIVE_COUNT = 4
PLANNING_FRONTIER_CONTROL_COUNT = 12


@dataclass(frozen=True, slots=True)
class PlanningDataCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlanningDataAudit:
    fixture_id: str
    checks: tuple[PlanningDataCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _source(source_id: str, title: str, uri: str, scope: str) -> PlanningSourceReceipt:
    body = {
        "source_id": source_id,
        "title": title,
        "uri": uri,
        "scope": scope,
        "version": "public portal receipt",
    }
    return PlanningSourceReceipt(**body, content_address=content_hash(body))


def _sources() -> tuple[PlanningSourceReceipt, ...]:
    return (
        _source("ncbi-refseq", "NCBI Reference Sequence", "https://www.ncbi.nlm.nih.gov/refseq/", "public sequence context"),
        _source("addgene", "Addgene public repository", "https://www.addgene.org/", "public plasmid and perturbation context"),
        _source("encode", "ENCODE project portal", "https://www.encodeproject.org/", "public regulatory assay context"),
        _source("pubmed", "PubMed biomedical literature", "https://pubmed.ncbi.nlm.nih.gov/", "public literature index"),
        _source("gtex", "GTEx portal", "https://gtexportal.org/home/", "public tissue expression context"),
    )


def _record(
    record_id: str,
    capability: str,
    operation: PlanningOperation,
    role: PlanningRole,
    payload: Mapping[str, Any],
    state: PlanningState,
    issues: tuple[str, ...],
    notes: str,
    source_ids: tuple[str, ...],
) -> PlanningRecord:
    body = {
        "record_id": record_id,
        "capability": capability,
        "operation": operation,
        "role": role,
        "context_key": payload.get("context_key", PLANNING_FRONTIER_CONTEXT_KEY),
        "source_ids": source_ids,
        "payload": dict(payload),
        "expected_state": state,
        "expected_issue_codes": issues,
        "notes": notes,
    }
    return PlanningRecord(**body, content_address=content_hash(body))


def _eligibility_payload(**overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "request_id": "eligibility-request-001",
        "context_key": PLANNING_FRONTIER_CONTEXT_KEY,
        "model_system": "adult_glioma_stem_like",
        "minimum_evidence_strength": "moderate",
        "observations": [
            {
                "model_id": "model-001",
                "model_system": "adult_glioma_stem_like",
                "cell_state": "stem_like",
                "context_key": PLANNING_FRONTIER_CONTEXT_KEY,
                "declared_context_keys": [PLANNING_FRONTIER_CONTEXT_KEY],
                "evidence_strength": "replicated",
                "supports_context": True,
                "blockers": [],
                "source_id": "gtex",
            }
        ],
        "controls": ["reference_model", "non_targeting"],
        "readouts": ["state_marker", "viability"],
    }
    value.update(overrides)
    return value


def _guide_payload(**overrides: Any) -> dict[str, Any]:
    rows = [{
        "observation_id": "guide-observation-001",
        "design_id": "design-001",
        "target_id": "target-001",
        "oligo_id": "oligo-001",
        "oligo_type": "guide",
        "sequence": "ACGTACGTACGTACGTACGT",
        "context_key": PLANNING_FRONTIER_CONTEXT_KEY,
        "strand": "+",
        "start_offset": 20,
        "pam": "NGG",
    }]
    value: dict[str, Any] = {
        "source_id": "broad-guide-receipt",
        "source_version": "public aggregate 2026-08",
        "input_format": "json",
        "context_key": PLANNING_FRONTIER_CONTEXT_KEY,
        "text": json.dumps({"observations": rows}, sort_keys=True),
    }
    value.update(overrides)
    return value


def _control_payload(**overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "plan_id": "controls-plan-001",
        "context_key": PLANNING_FRONTIER_CONTEXT_KEY,
        "randomization_seed": "public-seed-001",
        "control_types": ["non_targeting", "positive_control"],
        "biological_replicates": 2,
        "technical_replicates": 2,
        "targets": [
            {"target_id": "target-001", "condition": "baseline", "context_key": PLANNING_FRONTIER_CONTEXT_KEY},
            {"target_id": "target-002", "condition": "baseline", "context_key": PLANNING_FRONTIER_CONTEXT_KEY},
        ],
    }
    value.update(overrides)
    return value


def _power_payload(**overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "request_id": "power-request-001",
        "context_key": PLANNING_FRONTIER_CONTEXT_KEY,
        "observations": [
            {
                "observation_id": "power-observation-001",
                "design_id": "design-001",
                "assay_id": "expression-001",
                "effect_size": 0.8,
                "variance": 0.5,
                "alpha": 0.05,
                "target_power": 0.8,
                "planned_replicates": 24,
                "blocking_factor_count": 1,
                "context_key": PLANNING_FRONTIER_CONTEXT_KEY,
                "source_id": "pubmed",
            },
            {
                "observation_id": "power-observation-002",
                "design_id": "design-001",
                "assay_id": "expression-001",
                "effect_size": 0.82,
                "variance": 0.52,
                "alpha": 0.05,
                "target_power": 0.8,
                "planned_replicates": 24,
                "blocking_factor_count": 1,
                "context_key": PLANNING_FRONTIER_CONTEXT_KEY,
                "source_id": "pubmed",
            },
        ],
    }
    value.update(overrides)
    return value


def default_planning_frontier_fixture() -> PlanningFixture:
    records = (
        _record("D13-C09-POS-001", "model-system-eligibility", PlanningOperation.MODEL_ELIGIBILITY, PlanningRole.POSITIVE, _eligibility_payload(), PlanningState.READY_FOR_REVIEW, (), "declared model support and replicated evidence meet the gate", ("gtex", "pubmed")),
        _record("D13-C09-CTRL-001", "model-system-eligibility", PlanningOperation.MODEL_ELIGIBILITY, PlanningRole.CONTROL, _eligibility_payload(context_key=PLANNING_FRONTIER_FOREIGN_CONTEXT, observations=[dict(_eligibility_payload()["observations"][0], context_key=PLANNING_FRONTIER_FOREIGN_CONTEXT)]), PlanningState.BLOCKED, ("context_mismatch", "context_not_declared_supported"), "foreign model observation is blocked", ("gtex",)),
        _record("D13-C09-CTRL-002", "model-system-eligibility", PlanningOperation.MODEL_ELIGIBILITY, PlanningRole.CONTROL, _eligibility_payload(observations=[dict(_eligibility_payload()["observations"][0], declared_context_keys=[], evidence_strength="exploratory")]), PlanningState.REVIEW, ("context_not_declared_supported", "evidence_below_threshold", "no_declared_eligible_model_system"), "weak or undeclared model support remains review-only", ("gtex",)),
        _record("D13-C09-CTRL-003", "model-system-eligibility", PlanningOperation.MODEL_ELIGIBILITY, PlanningRole.CONTROL, _eligibility_payload(observations=[]), PlanningState.ABSTAINED, ("no_model_observations",), "empty model evidence abstains", ("gtex",)),
        _record("D13-C10-POS-001", "guide-oligo-adaptation", PlanningOperation.GUIDE_OLIGO, PlanningRole.POSITIVE, _guide_payload(), PlanningState.READY_FOR_REVIEW, (), "public guide row is adapted with a stable address", ("addgene", "ncbi-refseq")),
        _record("D13-C10-CTRL-001", "guide-oligo-adaptation", PlanningOperation.GUIDE_OLIGO, PlanningRole.CONTROL, _guide_payload(text=json.dumps({"observations": [dict(json.loads(_guide_payload()["text"])["observations"][0], context_key=PLANNING_FRONTIER_FOREIGN_CONTEXT)]})), PlanningState.BLOCKED, ("context_mismatch",), "foreign guide context is blocked", ("addgene",)),
        _record("D13-C10-CTRL-002", "guide-oligo-adaptation", PlanningOperation.GUIDE_OLIGO, PlanningRole.CONTROL, _guide_payload(text=json.dumps({"observations": [{"design_id": "design-002", "target_id": "target-002", "sequence": ""}]})), PlanningState.REVIEW, ("invalid_guide_oligo_row",), "malformed guide row is quarantined", ("addgene",)),
        _record("D13-C10-CTRL-003", "guide-oligo-adaptation", PlanningOperation.GUIDE_OLIGO, PlanningRole.CONTROL, _guide_payload(text=""), PlanningState.ABSTAINED, ("empty_source",), "empty source abstains", ("addgene",)),
        _record("D13-C11-POS-001", "controls-randomization", PlanningOperation.CONTROLS_RANDOMIZATION, PlanningRole.POSITIVE, _control_payload(), PlanningState.READY_FOR_REVIEW, (), "seeded assignments are deterministic and context-closed", ("addgene", "pubmed")),
        _record("D13-C11-CTRL-001", "controls-randomization", PlanningOperation.CONTROLS_RANDOMIZATION, PlanningRole.CONTROL, _control_payload(targets=[{"target_id": "target-foreign", "context_key": PLANNING_FRONTIER_FOREIGN_CONTEXT}]), PlanningState.BLOCKED, ("context_mismatch",), "foreign target block is retained", ("addgene",)),
        _record("D13-C11-CTRL-002", "controls-randomization", PlanningOperation.CONTROLS_RANDOMIZATION, PlanningRole.CONTROL, _control_payload(targets=[{"context_key": PLANNING_FRONTIER_CONTEXT_KEY}]), PlanningState.REVIEW, ("missing_target_id",), "missing target identity remains review-only", ("addgene",)),
        _record("D13-C11-CTRL-003", "controls-randomization", PlanningOperation.CONTROLS_RANDOMIZATION, PlanningRole.CONTROL, _control_payload(targets=[]), PlanningState.ABSTAINED, ("no_targets",), "empty target plan abstains", ("addgene",)),
        _record("D13-C12-POS-001", "power-replication", PlanningOperation.POWER_REPLICATION, PlanningRole.POSITIVE, _power_payload(), PlanningState.READY_FOR_REVIEW, (), "effect and noise inputs produce an addressed estimate", ("pubmed", "gtex")),
        _record("D13-C12-CTRL-001", "power-replication", PlanningOperation.POWER_REPLICATION, PlanningRole.CONTROL, _power_payload(observations=[dict(_power_payload()["observations"][0], context_key=PLANNING_FRONTIER_FOREIGN_CONTEXT)]), PlanningState.BLOCKED, ("context_mismatch",), "foreign power observation is blocked", ("pubmed",)),
        _record("D13-C12-CTRL-002", "power-replication", PlanningOperation.POWER_REPLICATION, PlanningRole.CONTROL, _power_payload(observations=[dict(_power_payload()["observations"][0], variance=0)]), PlanningState.REVIEW, ("invalid_power_row",), "non-positive variance is invalid", ("pubmed",)),
        _record("D13-C12-CTRL-003", "power-replication", PlanningOperation.POWER_REPLICATION, PlanningRole.CONTROL, _power_payload(observations=[]), PlanningState.ABSTAINED, ("no_power_observations",), "empty power evidence abstains", ("pubmed",)),
    )
    body = {
        "fixture_id": "planning-public-aggregate-001",
        "fixture_version": PLANNING_FRONTIER_VERSION,
        "context_key": PLANNING_FRONTIER_CONTEXT_KEY,
        "evidence_boundary": PLANNING_FRONTIER_BOUNDARY,
        "sources": _sources(),
        "records": records,
    }
    return PlanningFixture(**body, content_address=content_hash(body))


def audit_planning_frontier_data(fixture: PlanningFixture) -> PlanningDataAudit:
    source_ids = {source.source_id for source in fixture.sources}
    record_ids = tuple(record.record_id for record in fixture.records)
    counts = Counter(record.operation.value for record in fixture.records)
    private_records = tuple(
        record.record_id
        for record in fixture.records
        if any(marker in json.dumps(record.payload).lower() for marker in ("api_key", "password", "patient_id", "sample_id", "access_token"))
    )
    values = (
        ("source-count", len(fixture.sources), PLANNING_FRONTIER_SOURCE_COUNT, "five public source receipts"),
        ("record-count", len(fixture.records), PLANNING_FRONTIER_RECORD_COUNT, "four records per operation"),
        ("positive-count", len(fixture.positive_records), PLANNING_FRONTIER_POSITIVE_COUNT, "one positive per operation"),
        ("control-count", len(fixture.control_records), PLANNING_FRONTIER_CONTROL_COUNT, "three controls per operation"),
        ("unique-record-ids", len(record_ids), len(set(record_ids)), "record identities are unique"),
        ("known-sources", all(set(record.source_ids) <= source_ids for record in fixture.records), True, "source joins close"),
        ("https-receipts", all(source.uri.startswith("https://") for source in fixture.sources), True, "receipts use HTTPS"),
        ("no-private-markers", private_records, (), "fixture excludes private markers"),
        ("balanced-operations", sorted(counts.values()), [4, 4, 4, 4], "operations are balanced"),
    )
    checks = []
    for check_id, observed, required, detail in values:
        body = {"check_id": check_id, "passed": observed == required, "observed": observed, "required": required, "detail": detail}
        checks.append(PlanningDataCheck(**body, content_address=content_hash(body)))
    return PlanningDataAudit(fixture.fixture_id, tuple(checks), all(check.passed for check in checks), content_hash(tuple(checks)))


def load_planning_frontier_fixture(path: str | Path) -> PlanningFixture:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    expected = default_planning_frontier_fixture()
    if not isinstance(raw, Mapping) or raw.get("fixture_id") != expected.fixture_id or raw.get("fixture_version") != expected.fixture_version or raw.get("content_address") != expected.content_address:
        raise ValueError("planning fixture identity mismatch")
    return expected


def planning_frontier_fixture_json(fixture: PlanningFixture | None = None) -> str:
    return json.dumps(jsonable(fixture or default_planning_frontier_fixture()), indent=2, sort_keys=True) + "\n"


__all__ = [
    "PLANNING_FRONTIER_CONTROL_COUNT",
    "PLANNING_FRONTIER_POSITIVE_COUNT",
    "PLANNING_FRONTIER_RECORD_COUNT",
    "PLANNING_FRONTIER_SOURCE_COUNT",
    "PlanningDataAudit",
    "PlanningDataCheck",
    "audit_planning_frontier_data",
    "default_planning_frontier_fixture",
    "load_planning_frontier_fixture",
    "planning_frontier_fixture_json",
]
