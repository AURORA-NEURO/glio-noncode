"""Public aggregate source receipts and deterministic design-planning scenarios."""
from __future__ import annotations
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from .serialization import content_hash, jsonable
from .validation_design_frontier_contracts import VALIDATION_DESIGN_FRONTIER_BOUNDARY, VALIDATION_DESIGN_FRONTIER_CONTEXT_KEY, VALIDATION_DESIGN_FRONTIER_FOREIGN_CONTEXT, VALIDATION_DESIGN_FRONTIER_VERSION, ValidationDesignFixture, ValidationDesignOperation, ValidationDesignRecord, ValidationDesignRole, ValidationDesignSourceReceipt, ValidationDesignState

VALIDATION_DESIGN_FRONTIER_SOURCE_COUNT = 5
VALIDATION_DESIGN_FRONTIER_RECORD_COUNT = 16
VALIDATION_DESIGN_FRONTIER_POSITIVE_COUNT = 4
VALIDATION_DESIGN_FRONTIER_CONTROL_COUNT = 12

@dataclass(frozen=True, slots=True)
class ValidationDesignDataCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

@dataclass(frozen=True, slots=True)
class ValidationDesignDataAudit:
    fixture_id: str
    checks: tuple[ValidationDesignDataCheck, ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def _source(source_id: str, title: str, uri: str, scope: str) -> ValidationDesignSourceReceipt:
    body = {"source_id": source_id, "title": title, "uri": uri, "scope": scope, "version": "public portal receipt"}
    return ValidationDesignSourceReceipt(**body, content_address=content_hash(body))

def _sources() -> tuple[ValidationDesignSourceReceipt, ...]:
    return (_source("europepmc", "Europe PMC literature service", "https://europepmc.org/", "public literature and citation index"), _source("pubmed", "PubMed biomedical literature", "https://pubmed.ncbi.nlm.nih.gov/", "public indexed article metadata"), _source("gdc", "NCI Genomic Data Commons", "https://gdc.cancer.gov/", "public aggregate disease and genomic reference"), _source("encode", "ENCODE project portal", "https://www.encodeproject.org/", "public functional assay reference"), _source("addgene", "Addgene repository", "https://www.addgene.org/", "public construct and protocol reference"))

def _record(record_id: str, capability: str, operation: ValidationDesignOperation, role: ValidationDesignRole, payload: Mapping[str, Any], state: ValidationDesignState, issues: tuple[str, ...], notes: str, source_ids: tuple[str, ...]) -> ValidationDesignRecord:
    context = payload.get("context_key") if isinstance(payload.get("context_key"), str) else VALIDATION_DESIGN_FRONTIER_CONTEXT_KEY
    body = {"record_id": record_id, "capability": capability, "operation": operation, "role": role, "context_key": context, "source_ids": source_ids, "payload": dict(payload), "expected_state": state, "expected_issue_codes": issues, "notes": notes}
    return ValidationDesignRecord(**body, content_address=content_hash(body))

def _gap(**overrides: Any) -> dict[str, Any]:
    value = {"target_id": "target-regulatory-001", "context_key": VALIDATION_DESIGN_FRONTIER_CONTEXT_KEY, "required_evidence": ["sequence", "regulatory", "functional"], "available_evidence": [{"dimension": "sequence", "state": "supported", "source_ids": ["europepmc"]}, {"dimension": "regulatory", "state": "supported", "source_ids": ["encode", "gdc"]}, {"dimension": "functional", "state": "supported", "source_ids": ["pubmed"]}]}; value.update(overrides); return value

def _route(**overrides: Any) -> dict[str, Any]:
    value = {"target_id": "target-regulatory-001", "context_key": VALIDATION_DESIGN_FRONTIER_CONTEXT_KEY, "requested_assay": "mpra", "capabilities": [{"assay": "mpra", "supported": True, "readouts": ["allele_activity"], "limits": {"max_constructs": 24}}, {"assay": "starr_seq", "supported": True, "readouts": ["element_activity"], "limits": {"max_constructs": 16}}]}; value.update(overrides); return value

def _mpra(**overrides: Any) -> dict[str, Any]:
    value = {"package_id": "mpra-package-001", "context_key": VALIDATION_DESIGN_FRONTIER_CONTEXT_KEY, "construct_budget": 8, "constructs": [{"construct_id": "mpra-ref", "reference": "A", "alternate": "G", "sequence_length": 180}, {"construct_id": "mpra-alt", "reference": "C", "alternate": "T", "sequence_length": 180}], "controls": [{"control_id": "negative", "type": "negative"}, {"control_id": "reference", "type": "reference"}]}; value.update(overrides); return value

def _starr(**overrides: Any) -> dict[str, Any]:
    value = {"package_id": "starr-package-001", "context_key": VALIDATION_DESIGN_FRONTIER_CONTEXT_KEY, "construct_budget": 8, "constructs": [{"construct_id": "starr-enhancer-001", "element_id": "enhancer-001", "strand": "+", "sequence_length": 240}, {"construct_id": "starr-enhancer-002", "element_id": "enhancer-002", "strand": "-", "sequence_length": 220}], "controls": [{"control_id": "empty-vector", "type": "empty"}, {"control_id": "reference", "type": "reference"}]}; value.update(overrides); return value

def default_validation_design_frontier_fixture() -> ValidationDesignFixture:
    records = (
        _record("D13-C01-POS-001", "evidence-gap-analysis", ValidationDesignOperation.GAP_ANALYSIS, ValidationDesignRole.POSITIVE, _gap(), ValidationDesignState.READY, (), "all required planning dimensions have public support receipts", ("europepmc", "encode", "gdc")),
        _record("D13-C01-CTRL-001", "evidence-gap-analysis", ValidationDesignOperation.GAP_ANALYSIS, ValidationDesignRole.CONTROL, _gap(required_evidence=["sequence", "regulatory", "functional", "replication"]), ValidationDesignState.REVIEW, ("gap_dimensions",), "an uncovered replication dimension remains explicit", ("europepmc", "encode", "gdc")),
        _record("D13-C01-CTRL-002", "evidence-gap-analysis", ValidationDesignOperation.GAP_ANALYSIS, ValidationDesignRole.CONTROL, _gap(available_evidence=[]), ValidationDesignState.REVIEW, ("gap_dimensions",), "an empty evidence inventory remains review-only", ("europepmc", "encode", "gdc")),
        _record("D13-C01-CTRL-003", "evidence-gap-analysis", ValidationDesignOperation.GAP_ANALYSIS, ValidationDesignRole.CONTROL, _gap(context_key=VALIDATION_DESIGN_FRONTIER_FOREIGN_CONTEXT), ValidationDesignState.BLOCKED, ("context_mismatch",), "foreign planning context is blocked", ("europepmc", "encode", "gdc")),
        _record("D13-C02-POS-001", "assay-eligibility-routing", ValidationDesignOperation.ASSAY_ELIGIBILITY, ValidationDesignRole.POSITIVE, _route(), ValidationDesignState.ROUTED, (), "the requested assay has a supported bounded capability", ("pubmed", "addgene")),
        _record("D13-C02-CTRL-001", "assay-eligibility-routing", ValidationDesignOperation.ASSAY_ELIGIBILITY, ValidationDesignRole.CONTROL, _route(requested_assay="unsupported_assay"), ValidationDesignState.REVIEW, ("assay_unsupported",), "unsupported assay remains review-only", ("pubmed", "addgene")),
        _record("D13-C02-CTRL-002", "assay-eligibility-routing", ValidationDesignOperation.ASSAY_ELIGIBILITY, ValidationDesignRole.CONTROL, _route(capabilities=[]), ValidationDesignState.REVIEW, ("assay_unsupported",), "no capability receipt remains review-only", ("pubmed", "addgene")),
        _record("D13-C02-CTRL-003", "assay-eligibility-routing", ValidationDesignOperation.ASSAY_ELIGIBILITY, ValidationDesignRole.CONTROL, _route(context_key=VALIDATION_DESIGN_FRONTIER_FOREIGN_CONTEXT), ValidationDesignState.BLOCKED, ("context_mismatch",), "foreign assay routing is blocked", ("pubmed", "addgene")),
        _record("D13-C03-POS-001", "mpra-construct-package", ValidationDesignOperation.MPRA_PACKAGE, ValidationDesignRole.POSITIVE, _mpra(), ValidationDesignState.PACKAGED, (), "allele-paired bounded constructs and controls close the package", ("addgene", "encode")),
        _record("D13-C03-CTRL-001", "mpra-construct-package", ValidationDesignOperation.MPRA_PACKAGE, ValidationDesignRole.CONTROL, _mpra(constructs=[{**_mpra()["constructs"][0], "alternate": "A"}]), ValidationDesignState.REVIEW, ("allele_unchanged",), "unchanged reference/alternate pair remains review-only", ("addgene", "encode")),
        _record("D13-C03-CTRL-002", "mpra-construct-package", ValidationDesignOperation.MPRA_PACKAGE, ValidationDesignRole.CONTROL, _mpra(construct_budget=1), ValidationDesignState.REVIEW, ("construct_budget_exceeded",), "budget overflow remains review-only", ("addgene", "encode")),
        _record("D13-C03-CTRL-003", "mpra-construct-package", ValidationDesignOperation.MPRA_PACKAGE, ValidationDesignRole.CONTROL, _mpra(context_key=VALIDATION_DESIGN_FRONTIER_FOREIGN_CONTEXT), ValidationDesignState.BLOCKED, ("context_mismatch",), "foreign MPRA package is blocked", ("addgene", "encode")),
        _record("D13-C04-POS-001", "starrseq-construct-package", ValidationDesignOperation.STARRSEQ_PACKAGE, ValidationDesignRole.POSITIVE, _starr(), ValidationDesignState.PACKAGED, (), "bounded element constructs and controls close the package", ("addgene", "encode")),
        _record("D13-C04-CTRL-001", "starrseq-construct-package", ValidationDesignOperation.STARRSEQ_PACKAGE, ValidationDesignRole.CONTROL, _starr(constructs=[{**_starr()["constructs"][0], "strand": "?"}]), ValidationDesignState.REVIEW, ("construct_field_missing",), "unsupported strand is held for review", ("addgene", "encode")),
        _record("D13-C04-CTRL-002", "starrseq-construct-package", ValidationDesignOperation.STARRSEQ_PACKAGE, ValidationDesignRole.CONTROL, _starr(constructs=[]), ValidationDesignState.REVIEW, ("constructs_missing",), "empty construct set remains review-only", ("addgene", "encode")),
        _record("D13-C04-CTRL-003", "starrseq-construct-package", ValidationDesignOperation.STARRSEQ_PACKAGE, ValidationDesignRole.CONTROL, _starr(context_key=VALIDATION_DESIGN_FRONTIER_FOREIGN_CONTEXT), ValidationDesignState.BLOCKED, ("context_mismatch",), "foreign STARR-seq package is blocked", ("addgene", "encode")),
    )
    body = {"fixture_id": "validation-design-public-aggregate-001", "fixture_version": VALIDATION_DESIGN_FRONTIER_VERSION, "context_key": VALIDATION_DESIGN_FRONTIER_CONTEXT_KEY, "evidence_boundary": VALIDATION_DESIGN_FRONTIER_BOUNDARY, "sources": _sources(), "records": records}
    return ValidationDesignFixture(**body, content_address=content_hash(body))

def audit_validation_design_frontier_data(fixture: ValidationDesignFixture) -> ValidationDesignDataAudit:
    source_ids = {source.source_id for source in fixture.sources}; record_ids = tuple(record.record_id for record in fixture.records); counts = Counter(record.operation.value for record in fixture.records); markers = tuple(record.record_id for record in fixture.records if any(marker in json.dumps(record.payload).lower() for marker in ("api_key", "password", "patient_id", "sample_id", "access_token")))
    values = (("source-count", len(fixture.sources), 5, "public source receipts"), ("record-count", len(fixture.records), 16, "four rows per operation"), ("positive-count", len(fixture.positive_records), 4, "one positive per operation"), ("control-count", len(fixture.control_records), 12, "three controls per operation"), ("unique-record-ids", len(record_ids), len(set(record_ids)), "identities are unique"), ("known-sources", all(set(record.source_ids) <= source_ids for record in fixture.records), True, "source joins close"), ("https-receipts", all(source.uri.startswith("https://") for source in fixture.sources), True, "receipts use HTTPS"), ("no-private-markers", markers, (), "fixture has no private markers"), ("balanced-operations", sorted(counts.values()), [4, 4, 4, 4], "operations are balanced"))
    checks = []
    for check_id, observed, required, detail in values:
        body = {"check_id": check_id, "passed": observed == required, "observed": observed, "required": required, "detail": detail}; checks.append(ValidationDesignDataCheck(**body, content_address=content_hash(body)))
    return ValidationDesignDataAudit(fixture.fixture_id, tuple(checks), all(check.passed for check in checks), content_hash(tuple(checks)))

def load_validation_design_frontier_fixture(path: str | Path) -> ValidationDesignFixture:
    raw = json.loads(Path(path).read_text(encoding="utf-8")); expected = default_validation_design_frontier_fixture()
    if not isinstance(raw, Mapping) or raw.get("fixture_version") != VALIDATION_DESIGN_FRONTIER_VERSION or raw.get("fixture_id") != expected.fixture_id or raw.get("content_address") != expected.content_address: raise ValueError("validation-design fixture identity mismatch")
    return expected

def validation_design_frontier_fixture_json(fixture: ValidationDesignFixture | None = None) -> str:
    return json.dumps(jsonable(fixture or default_validation_design_frontier_fixture()), indent=2, sort_keys=True) + "\n"

__all__ = ["VALIDATION_DESIGN_FRONTIER_CONTROL_COUNT", "VALIDATION_DESIGN_FRONTIER_POSITIVE_COUNT", "VALIDATION_DESIGN_FRONTIER_RECORD_COUNT", "VALIDATION_DESIGN_FRONTIER_SOURCE_COUNT", "ValidationDesignDataAudit", "ValidationDesignDataCheck", "audit_validation_design_frontier_data", "default_validation_design_frontier_fixture", "load_validation_design_frontier_fixture", "validation_design_frontier_fixture_json"]
