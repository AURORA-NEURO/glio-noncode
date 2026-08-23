"""Public aggregate receipts and deterministic C05-C08 editing scenarios."""
from __future__ import annotations
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from .serialization import content_hash, jsonable
from .editing_design_frontier_contracts import EDITING_DESIGN_FRONTIER_BOUNDARY, EDITING_DESIGN_FRONTIER_CONTEXT_KEY, EDITING_DESIGN_FRONTIER_FOREIGN_CONTEXT, EDITING_DESIGN_FRONTIER_VERSION, EditingDesignFixture, EditingDesignOperation, EditingDesignRecord, EditingDesignRole, EditingDesignSourceReceipt, EditingDesignState

EDITING_DESIGN_FRONTIER_SOURCE_COUNT = 5
EDITING_DESIGN_FRONTIER_RECORD_COUNT = 16
EDITING_DESIGN_FRONTIER_POSITIVE_COUNT = 4
EDITING_DESIGN_FRONTIER_CONTROL_COUNT = 12

@dataclass(frozen=True, slots=True)
class EditingDesignDataCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

@dataclass(frozen=True, slots=True)
class EditingDesignDataAudit:
    fixture_id: str
    checks: tuple[EditingDesignDataCheck, ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def _source(source_id: str, title: str, uri: str, scope: str) -> EditingDesignSourceReceipt:
    body = {"source_id": source_id, "title": title, "uri": uri, "scope": scope, "version": "public portal receipt"}
    return EditingDesignSourceReceipt(**body, content_address=content_hash(body))

def _sources() -> tuple[EditingDesignSourceReceipt, ...]:
    return (_source("ncbi-refseq", "NCBI Reference Sequence", "https://www.ncbi.nlm.nih.gov/refseq/", "public sequence and coordinate receipt"), _source("addgene", "Addgene CRISPR resources", "https://www.addgene.org/crispr/", "public perturbation planning reference"), _source("broad-gpp", "Broad GPP public portal", "https://portals.broadinstitute.org/gpp/public/", "public guide design reference"), _source("encode", "ENCODE project portal", "https://www.encodeproject.org/", "public regulatory assay context"), _source("pubmed", "PubMed biomedical literature", "https://pubmed.ncbi.nlm.nih.gov/", "public literature index"))

def _sequence(reference: str = "C", length: int = 41, offset: int = 20) -> str:
    bases = ("ACGT" * ((length // 4) + 1))[:length]
    return bases[:offset] + reference + bases[offset + len(reference):]

def _target(target_id: str, *, context_key: str = EDITING_DESIGN_FRONTIER_CONTEXT_KEY, reference: str = "C", alternate: str = "T", sequence: str | None = None, offset: int = 20) -> dict[str, Any]:
    return {"target_id": target_id, "sequence": sequence or _sequence(reference, offset=offset), "reference": reference, "alternate": alternate, "variant_offset": offset, "context_key": context_key}

def _base_payload(**overrides: Any) -> dict[str, Any]:
    value = {"design_id": "base-design-001", "context_key": EDITING_DESIGN_FRONTIER_CONTEXT_KEY, "targets": [_target("base-target-001")], "editing_window": [4, 40], "controls": ["non_targeting", "positive_control"], "readouts": ["editing_rate", "viability"]}; value.update(overrides); return value

def _crispr_payload(**overrides: Any) -> dict[str, Any]:
    value = {"design_id": "crispr-design-001", "context_key": EDITING_DESIGN_FRONTIER_CONTEXT_KEY, "targets": [{"target_id": "crispr-target-001", "sequence": _sequence()}], "modes": ["crispri", "crispra"], "guide_length": 20, "max_guides": 3, "controls": ["non_targeting", "positive_control"], "readouts": ["expression", "viability"]}; value.update(overrides); return value

def _prime_payload(**overrides: Any) -> dict[str, Any]:
    value = {"design_id": "prime-design-001", "context_key": EDITING_DESIGN_FRONTIER_CONTEXT_KEY, "targets": [_target("prime-target-001")], "pbs_length": 13, "rtt_length": 20, "flank_length": 41, "max_edit_length": 4, "controls": ["non_targeting", "positive_control"], "readouts": ["editing_rate", "viability"]}; value.update(overrides); return value

def _reporter_payload(**overrides: Any) -> dict[str, Any]:
    value = {"design_id": "reporter-design-001", "context_key": EDITING_DESIGN_FRONTIER_CONTEXT_KEY, "max_constructs": 2, "constructs": [{"construct_id": "reporter-reference", "allele": "reference", "sequence": _sequence("C", length=30, offset=14)}, {"construct_id": "reporter-alternate", "allele": "alternate", "sequence": _sequence("T", length=30, offset=14)}], "controls": ["empty_vector", "positive_control"], "readouts": ["reporter_activity", "viability"]}; value.update(overrides); return value

def _record(record_id: str, capability: str, operation: EditingDesignOperation, role: EditingDesignRole, payload: Mapping[str, Any], state: EditingDesignState, issues: tuple[str, ...], notes: str, source_ids: tuple[str, ...] = ("ncbi-refseq", "addgene")) -> EditingDesignRecord:
    body = {"record_id": record_id, "capability": capability, "operation": operation, "role": role, "context_key": payload.get("context_key", EDITING_DESIGN_FRONTIER_CONTEXT_KEY), "source_ids": source_ids, "payload": dict(payload), "expected_state": state, "expected_issue_codes": issues, "notes": notes}
    return EditingDesignRecord(**body, content_address=content_hash(body))

def default_editing_design_frontier_fixture() -> EditingDesignFixture:
    records = (
        _record("D13-C05-POS-001", "crispr-interference-activation-design", EditingDesignOperation.CRISPR_DESIGN, EditingDesignRole.POSITIVE, _crispr_payload(), EditingDesignState.DESIGNED, (), "bounded CRISPRi and CRISPRa candidates are emitted", ("ncbi-refseq", "addgene", "broad-gpp")),
        _record("D13-C05-CTRL-001", "crispr-interference-activation-design", EditingDesignOperation.CRISPR_DESIGN, EditingDesignRole.CONTROL, _crispr_payload(modes=["unsupported_mode"]), EditingDesignState.REVIEW, ("mode_unsupported",), "unsupported design mode remains review-only", ("ncbi-refseq", "addgene", "broad-gpp")),
        _record("D13-C05-CTRL-002", "crispr-interference-activation-design", EditingDesignOperation.CRISPR_DESIGN, EditingDesignRole.CONTROL, _crispr_payload(targets=[]), EditingDesignState.REVIEW, ("targets_missing",), "empty target inventory remains review-only", ("ncbi-refseq", "addgene", "broad-gpp")),
        _record("D13-C05-CTRL-003", "crispr-interference-activation-design", EditingDesignOperation.CRISPR_DESIGN, EditingDesignRole.CONTROL, _crispr_payload(context_key=EDITING_DESIGN_FRONTIER_FOREIGN_CONTEXT), EditingDesignState.BLOCKED, ("context_mismatch",), "foreign context is blocked", ("ncbi-refseq", "addgene", "broad-gpp")),
        _record("D13-C06-POS-001", "base-editing-design", EditingDesignOperation.BASE_EDITING, EditingDesignRole.POSITIVE, _base_payload(), EditingDesignState.DESIGNED, (), "single-base edit lies within the declared editing window", ("ncbi-refseq", "broad-gpp")),
        _record("D13-C06-CTRL-001", "base-editing-design", EditingDesignOperation.BASE_EDITING, EditingDesignRole.CONTROL, _base_payload(targets=[_target("base-target-foreign", context_key=EDITING_DESIGN_FRONTIER_FOREIGN_CONTEXT)]), EditingDesignState.BLOCKED, ("context_mismatch",), "foreign base-edit target is blocked", ("ncbi-refseq", "broad-gpp")),
        _record("D13-C06-CTRL-002", "base-editing-design", EditingDesignOperation.BASE_EDITING, EditingDesignRole.CONTROL, _base_payload(targets=[_target("base-target-multi", alternate="AT")]), EditingDesignState.REVIEW, ("substitution_not_single_base",), "multi-base substitution remains review-only", ("ncbi-refseq", "broad-gpp")),
        _record("D13-C06-CTRL-003", "base-editing-design", EditingDesignOperation.BASE_EDITING, EditingDesignRole.CONTROL, _base_payload(targets=[]), EditingDesignState.REVIEW, ("targets_missing",), "empty base-edit inventory remains review-only", ("ncbi-refseq", "broad-gpp")),
        _record("D13-C07-POS-001", "prime-editing-design", EditingDesignOperation.PRIME_EDITING, EditingDesignRole.POSITIVE, _prime_payload(), EditingDesignState.DESIGNED, (), "PBS, RTT, flank, and edit-length bounds close the package", ("ncbi-refseq", "broad-gpp")),
        _record("D13-C07-CTRL-001", "prime-editing-design", EditingDesignOperation.PRIME_EDITING, EditingDesignRole.CONTROL, _prime_payload(targets=[_target("prime-target-foreign", context_key=EDITING_DESIGN_FRONTIER_FOREIGN_CONTEXT)]), EditingDesignState.BLOCKED, ("context_mismatch",), "foreign prime-edit target is blocked", ("ncbi-refseq", "broad-gpp")),
        _record("D13-C07-CTRL-002", "prime-editing-design", EditingDesignOperation.PRIME_EDITING, EditingDesignRole.CONTROL, _prime_payload(targets=[_target("prime-target-long", alternate="A" * 8)]), EditingDesignState.REVIEW, ("edit_length_exceeded",), "long edit remains review-only", ("ncbi-refseq", "broad-gpp")),
        _record("D13-C07-CTRL-003", "prime-editing-design", EditingDesignOperation.PRIME_EDITING, EditingDesignRole.CONTROL, _prime_payload(flank_length=10), EditingDesignState.REVIEW, ("flank_shortage",), "short flank remains review-only", ("ncbi-refseq", "broad-gpp")),
        _record("D13-C08-POS-001", "allele-specific-reporter-design", EditingDesignOperation.ALLELE_REPORTER, EditingDesignRole.POSITIVE, _reporter_payload(), EditingDesignState.DESIGNED, (), "paired reference and alternate reporter constructs close the package", ("encode", "addgene", "pubmed")),
        _record("D13-C08-CTRL-001", "allele-specific-reporter-design", EditingDesignOperation.ALLELE_REPORTER, EditingDesignRole.CONTROL, _reporter_payload(context_key=EDITING_DESIGN_FRONTIER_FOREIGN_CONTEXT), EditingDesignState.BLOCKED, ("context_mismatch",), "foreign reporter context is blocked", ("encode", "addgene", "pubmed")),
        _record("D13-C08-CTRL-002", "allele-specific-reporter-design", EditingDesignOperation.ALLELE_REPORTER, EditingDesignRole.CONTROL, _reporter_payload(constructs=[]), EditingDesignState.REVIEW, ("constructs_missing",), "empty reporter inventory remains review-only", ("encode", "addgene", "pubmed")),
        _record("D13-C08-CTRL-003", "allele-specific-reporter-design", EditingDesignOperation.ALLELE_REPORTER, EditingDesignRole.CONTROL, _reporter_payload(max_constructs=1), EditingDesignState.REVIEW, ("construct_budget_exceeded",), "construct budget overflow remains review-only", ("encode", "addgene", "pubmed")),
    )
    body = {"fixture_id": "editing-design-public-aggregate-001", "fixture_version": EDITING_DESIGN_FRONTIER_VERSION, "context_key": EDITING_DESIGN_FRONTIER_CONTEXT_KEY, "evidence_boundary": EDITING_DESIGN_FRONTIER_BOUNDARY, "sources": _sources(), "records": records}
    return EditingDesignFixture(**body, content_address=content_hash(body))

def audit_editing_design_frontier_data(fixture: EditingDesignFixture) -> EditingDesignDataAudit:
    source_ids = {source.source_id for source in fixture.sources}; record_ids = tuple(record.record_id for record in fixture.records); counts = Counter(record.operation.value for record in fixture.records); markers = tuple(record.record_id for record in fixture.records if any(marker in json.dumps(record.payload).lower() for marker in ("api_key", "password", "patient_id", "sample_id", "access_token")))
    values = (("source-count", len(fixture.sources), 5, "public source receipts"), ("record-count", len(fixture.records), 16, "four rows per operation"), ("positive-count", len(fixture.positive_records), 4, "one positive per operation"), ("control-count", len(fixture.control_records), 12, "three controls per operation"), ("unique-record-ids", len(record_ids), len(set(record_ids)), "identities are unique"), ("known-sources", all(set(record.source_ids) <= source_ids for record in fixture.records), True, "source joins close"), ("https-receipts", all(source.uri.startswith("https://") for source in fixture.sources), True, "receipts use HTTPS"), ("no-private-markers", markers, (), "fixture has no private markers"), ("balanced-operations", sorted(counts.values()), [4, 4, 4, 4], "operations are balanced"))
    checks = []
    for check_id, observed, required, detail in values:
        body = {"check_id": check_id, "passed": observed == required, "observed": observed, "required": required, "detail": detail}; checks.append(EditingDesignDataCheck(**body, content_address=content_hash(body)))
    return EditingDesignDataAudit(fixture.fixture_id, tuple(checks), all(check.passed for check in checks), content_hash(tuple(checks)))

def load_editing_design_frontier_fixture(path: str | Path) -> EditingDesignFixture:
    raw = json.loads(Path(path).read_text(encoding="utf-8")); expected = default_editing_design_frontier_fixture()
    if not isinstance(raw, Mapping) or raw.get("fixture_version") != EDITING_DESIGN_FRONTIER_VERSION or raw.get("fixture_id") != expected.fixture_id or raw.get("content_address") != expected.content_address: raise ValueError("editing-design fixture identity mismatch")
    return expected

def editing_design_frontier_fixture_json(fixture: EditingDesignFixture | None = None) -> str: return json.dumps(jsonable(fixture or default_editing_design_frontier_fixture()), indent=2, sort_keys=True) + "\n"

__all__ = ["EDITING_DESIGN_FRONTIER_CONTROL_COUNT", "EDITING_DESIGN_FRONTIER_POSITIVE_COUNT", "EDITING_DESIGN_FRONTIER_RECORD_COUNT", "EDITING_DESIGN_FRONTIER_SOURCE_COUNT", "EditingDesignDataAudit", "EditingDesignDataCheck", "audit_editing_design_frontier_data", "default_editing_design_frontier_fixture", "editing_design_frontier_fixture_json", "load_editing_design_frontier_fixture"]
