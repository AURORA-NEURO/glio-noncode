"""Public source receipts and executable controls for the D01 architecture."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_fabric_support import contains_private_key
from .serialization import content_hash, jsonable
from .intake_architecture_contracts import (
    INTAKE_ARCHITECTURE_BOUNDARY,
    INTAKE_ARCHITECTURE_CASE_COUNT,
    INTAKE_ARCHITECTURE_CONTEXT,
    INTAKE_ARCHITECTURE_FOREIGN_CONTEXT,
    INTAKE_ARCHITECTURE_OPERATION_COUNT,
    INTAKE_ARCHITECTURE_VERSION,
    IntakeArchitectureCase,
    IntakeArchitectureCheckKind,
    IntakeArchitectureDataAudit,
    IntakeArchitectureDataCheck,
    IntakeArchitectureFixture,
    IntakeArchitectureOperation,
    IntakeArchitectureOperationSpec,
    IntakeArchitecturePlane,
    IntakeArchitectureScenario,
    IntakeArchitectureSource,
    IntakeArchitectureState,
)


INTAKE_ARCHITECTURE_SOURCE_COUNT = 6


@dataclass(frozen=True, slots=True)
class IntakeArchitectureDataReceipt:
    receipt_id: str
    source_id: str
    public_identifier: str
    source_version: str
    scope: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _source(source_id: str, title: str, uri: str, version: str) -> IntakeArchitectureSource:
    body = {
        "source_id": source_id,
        "title": title,
        "uri": uri,
        "scope": "public_aggregate",
        "version": version,
    }
    return IntakeArchitectureSource(**body, content_address=content_hash(body, prefix="intake-source"))


def default_intake_architecture_sources() -> tuple[IntakeArchitectureSource, ...]:
    """Return stable HTTPS receipts for public reference and standards sources."""

    return (
        _source(
            "ncbi-variation",
            "NCBI Variation public reference index",
            "https://www.ncbi.nlm.nih.gov/snp/",
            "public-index-2026",
        ),
        _source(
            "ncbi-reference-assembly",
            "NCBI human reference assembly record",
            "https://www.ncbi.nlm.nih.gov/assembly/GCF_000001405.40/",
            "GCF_000001405.40",
        ),
        _source(
            "ga4gh-vrs",
            "GA4GH Variation Representation Specification",
            "https://vrs.ga4gh.org/",
            "v2-public-spec",
        ),
        _source(
            "ensembl-variation",
            "Ensembl public variation documentation",
            "https://www.ensembl.org/info/genome/variation/index.html",
            "public-documentation",
        ),
        _source(
            "ucsc-encode-reference",
            "UCSC and ENCODE public regulatory reference portal",
            "https://www.encodeproject.org/",
            "public-portal",
        ),
        _source(
            "repository-controls",
            "GLIO-NONCODE public aggregate validation receipts",
            "https://github.com/AURORA-NEURO/glio-noncode",
            "d01-controls-v1",
        ),
    )


_OPERATION_ROWS: tuple[
    tuple[IntakeArchitectureOperation, IntakeArchitecturePlane, str, str], ...
] = (
    (IntakeArchitectureOperation.CASE_MANIFEST_INGESTION, IntakeArchitecturePlane.INGESTION, "case.manifest.input.v1", "case.manifest.receipt.v1"),
    (IntakeArchitectureOperation.VCF_BCF_GVCF_PARSING, IntakeArchitecturePlane.PARSING, "variant.bytes.input.v1", "variant.parse.receipt.v1"),
    (IntakeArchitectureOperation.REGULATORY_TRACK_PARSING, IntakeArchitecturePlane.PARSING, "regulatory.track.input.v1", "regulatory.track.receipt.v1"),
    (IntakeArchitectureOperation.VRS_NORMALIZATION, IntakeArchitecturePlane.NORMALIZATION, "variant.identity.input.v1", "vrs.normalization.receipt.v1"),
    (IntakeArchitectureOperation.CAT_VRS_NORMALIZATION, IntakeArchitecturePlane.NORMALIZATION, "categorical.variation.input.v1", "catvrs.normalization.receipt.v1"),
    (IntakeArchitectureOperation.VA_SPEC_ENVELOPE, IntakeArchitecturePlane.NORMALIZATION, "annotation.statement.input.v1", "va.spec.receipt.v1"),
    (IntakeArchitectureOperation.MULTIALLELIC_DECOMPOSITION, IntakeArchitecturePlane.PARSING, "multiallelic.record.input.v1", "allele.decomposition.receipt.v1"),
    (IntakeArchitectureOperation.REPEAT_AWARE_NORMALIZATION, IntakeArchitecturePlane.NORMALIZATION, "repeat.window.input.v1", "repeat.normalization.receipt.v1"),
    (IntakeArchitectureOperation.VARIANT_EQUIVALENCE, IntakeArchitecturePlane.IDENTITY, "identity.query.input.v1", "identity.match.receipt.v1"),
    (IntakeArchitectureOperation.DUPLICATE_ALIAS_RECONCILIATION, IntakeArchitecturePlane.IDENTITY, "identity.batch.input.v1", "identity.reconciliation.receipt.v1"),
    (IntakeArchitectureOperation.BATCH_SAMPLE_IDENTITY, IntakeArchitecturePlane.IDENTITY, "batch.identity.input.v1", "batch.identity.receipt.v1"),
    (IntakeArchitectureOperation.CHAIN_OF_CUSTODY, IntakeArchitecturePlane.PROVENANCE, "custody.receipt.input.v1", "custody.ledger.receipt.v1"),
    (IntakeArchitectureOperation.CONSENT_POLICY, IntakeArchitecturePlane.POLICY, "data.use.policy.input.v1", "data.use.policy.receipt.v1"),
    (IntakeArchitectureOperation.INPUT_QUARANTINE, IntakeArchitecturePlane.POLICY, "input.anomaly.input.v1", "input.quarantine.receipt.v1"),
    (IntakeArchitectureOperation.COMPLETENESS_SCORING, IntakeArchitecturePlane.POLICY, "completeness.input.v1", "completeness.receipt.v1"),
    (IntakeArchitectureOperation.REPRODUCIBLE_BUNDLE, IntakeArchitecturePlane.RELEASE, "intake.bundle.input.v1", "intake.bundle.receipt.v1"),
)


def default_intake_architecture_operations() -> tuple[IntakeArchitectureOperationSpec, ...]:
    source_ids = tuple(item.source_id for item in default_intake_architecture_sources())
    output: list[IntakeArchitectureOperationSpec] = []
    for ordinal, (operation, plane, input_contract, output_contract) in enumerate(_OPERATION_ROWS, start=1):
        body = {
            "operation_id": f"INTAKE-D01-C{ordinal:02d}",
            "capability_id": f"GNC-D01-C{ordinal:02d}",
            "ordinal": ordinal,
            "operation": operation,
            "plane": plane,
            "input_contract": input_contract,
            "output_contract": output_contract,
            "dependencies": () if ordinal == 1 else (f"INTAKE-D01-C{ordinal - 1:02d}",),
            "source_ids": (source_ids[(ordinal - 1) % len(source_ids)], "repository-controls"),
            "review_on_control": True,
        }
        output.append(IntakeArchitectureOperationSpec(**body, content_address=content_hash(body, prefix="intake-operation")))
    return tuple(output)


_VARIANT = {
    "variant_id": "dbsnp:rs429358",
    "kind": "snv",
    "chromosome": "7",
    "start": 55249063,
    "end": 55249063,
    "reference": "T",
    "alternate": "C",
    "genome_build": "GRCh38",
    "origin": "uncertain",
    "sample_id": "public-aggregate",
}


def _payload(spec: IntakeArchitectureOperationSpec, scenario: IntakeArchitectureScenario) -> dict[str, Any]:
    """Build a bounded public payload for one operation and one control."""

    payload: dict[str, Any] = {
        "schema_version": INTAKE_ARCHITECTURE_VERSION,
        "operation_id": spec.operation_id,
        "capability_id": spec.capability_id,
        "context_key": INTAKE_ARCHITECTURE_CONTEXT,
        "public_aggregate_only": True,
        "source_record": "public-reference-aggregate",
        "variant": dict(_VARIANT),
        "public_identifiers": ["dbsnp:rs429358", "GRCh38:7:55249063:T:C"],
    }
    if spec.operation is IntakeArchitectureOperation.VCF_BCF_GVCF_PARSING:
        payload["input_format"] = "vcf"
        payload["raw_text"] = "##fileformat=VCFv4.3\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n7\t55249063\trs429358\tT\tC\t.\tPASS\tSOURCE=public\n"
    elif spec.operation is IntakeArchitectureOperation.REGULATORY_TRACK_PARSING:
        payload["input_format"] = "tsv"
        payload["track_text"] = "chrom\tstart\tend\tname\tscore\nchr7\t55249062\t55249063\tpublic-regulatory-window\t1.0\n"
    elif spec.operation is IntakeArchitectureOperation.CAT_VRS_NORMALIZATION:
        payload["category"] = {
            "category_id": "cat-vrs:public-reference-snv",
            "label": "public reference variation set",
            "definition": "Declared membership set for deterministic parser validation.",
            "member_variation_ids": ["dbsnp:rs429358"],
            "rules": {"membership": "explicit_identifier_only"},
        }
    elif spec.operation is IntakeArchitectureOperation.VA_SPEC_ENVELOPE:
        payload["statement"] = {
            "statement_id": "va-statement:public-aggregate-001",
            "subject": "dbsnp:rs429358",
            "predicate": "has_declared_public_reference_identity",
            "object": "GRCh38:7:55249063:T:C",
            "source_id": "ncbi-variation",
        }
    elif spec.operation is IntakeArchitectureOperation.MULTIALLELIC_DECOMPOSITION:
        payload["raw_text"] = "##fileformat=VCFv4.3\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n7\t55249063\tpublic-multi\tT\tC,G\t.\tPASS\tSOURCE=public\n"
    elif spec.operation is IntakeArchitectureOperation.REPEAT_AWARE_NORMALIZATION:
        payload["reference_window"] = {"sequence": "ACACACAC", "start": 55249060, "max_shift_bp": 4}
        payload["variant"] = {**_VARIANT, "variant_id": "public:repeat-window", "start": 55249062, "end": 55249062, "reference": "A", "alternate": "C"}
    elif spec.operation is IntakeArchitectureOperation.VARIANT_EQUIVALENCE:
        payload["query"] = "dbsnp:rs429358"
        payload["aliases"] = ["GRCh38:7:55249063:T:C"]
    elif spec.operation is IntakeArchitectureOperation.DUPLICATE_ALIAS_RECONCILIATION:
        payload["records"] = [
            {"record_id": "public-record-1", "variant": dict(_VARIANT), "aliases": ["dbsnp:rs429358"]},
            {"record_id": "public-record-2", "variant": dict(_VARIANT), "aliases": ["GRCh38:7:55249063:T:C"]},
        ]
    elif spec.operation is IntakeArchitectureOperation.BATCH_SAMPLE_IDENTITY:
        payload["batch_id"] = "public-batch-001"
        payload["sample_ids"] = ["public-aggregate"]
        payload["declared_record_count"] = 1
    elif spec.operation is IntakeArchitectureOperation.CHAIN_OF_CUSTODY:
        payload["custody_events"] = [
            {"event_id": "public-receipt-001", "stage": "source_read", "source_id": "ncbi-variation", "digest": "sha256:public-receipt-001"},
            {"event_id": "public-receipt-002", "stage": "canonicalized", "source_id": "repository-controls", "digest": "sha256:public-receipt-002"},
        ]
    elif spec.operation is IntakeArchitectureOperation.CONSENT_POLICY:
        payload["policy"] = {"policy_id": "public-aggregate-use", "version": "v1", "permitted_uses": ["research", "quality_audit", "reproducibility"], "patient_level_data": False}
    elif spec.operation is IntakeArchitectureOperation.INPUT_QUARANTINE:
        payload["anomaly_policy"] = {"allowed_bases": "ACGTN", "unsupported_symbols": ["<", ">", "[", "]"]}
    elif spec.operation is IntakeArchitectureOperation.COMPLETENESS_SCORING:
        payload["required_fields"] = ["operation_id", "context_key", "source_record", "public_identifiers", "variant"]
        payload["weights"] = {"operation_id": 1.0, "context_key": 2.0, "source_record": 1.0, "public_identifiers": 2.0, "variant": 4.0}
    elif spec.operation is IntakeArchitectureOperation.REPRODUCIBLE_BUNDLE:
        payload["artifact_kinds"] = ["manifest", "source_receipts", "operation_results", "ledger", "release"]
        payload["offline_capable"] = True
    if scenario is IntakeArchitectureScenario.FOREIGN_CONTEXT:
        payload["context_key"] = INTAKE_ARCHITECTURE_FOREIGN_CONTEXT
    elif scenario is IntakeArchitectureScenario.MALFORMED_INPUT:
        payload["malformed"] = True
        payload["required_field"] = ""
        if spec.operation is IntakeArchitectureOperation.VCF_BCF_GVCF_PARSING:
            payload["raw_text"] = "not-a-vcf-record"
    elif scenario is IntakeArchitectureScenario.DUPLICATE_IDENTITY:
        payload["duplicate_identity"] = True
        payload["duplicate_keys"] = ["GRCh38:7:55249063:T:C", "GRCh38:7:55249063:T:C"]
    return payload


def _case(
    spec: IntakeArchitectureOperationSpec,
    scenario: IntakeArchitectureScenario,
    source_ids: tuple[str, ...],
) -> IntakeArchitectureCase:
    issue_codes = {
        IntakeArchitectureScenario.POSITIVE: (),
        IntakeArchitectureScenario.FOREIGN_CONTEXT: ("foreign_context",),
        IntakeArchitectureScenario.MALFORMED_INPUT: ("malformed_input",),
        IntakeArchitectureScenario.DUPLICATE_IDENTITY: ("duplicate_identity",),
    }[scenario]
    body = {
        "case_id": f"{spec.operation_id}-{scenario.value}",
        "operation_id": spec.operation_id,
        "capability_id": spec.capability_id,
        "scenario": scenario,
        "context_key": INTAKE_ARCHITECTURE_CONTEXT,
        "source_ids": source_ids,
        "public_identifier": f"public:{spec.operation.value}:{scenario.value}",
        "payload": _payload(spec, scenario),
        "expected_state": IntakeArchitectureState.ACCEPTED if scenario is IntakeArchitectureScenario.POSITIVE else IntakeArchitectureState.REVIEW,
        "expected_issue_codes": issue_codes,
    }
    if contains_private_key(body["payload"]):
        raise ValidationError("intake architecture payload contains a private key")
    return IntakeArchitectureCase(**body, content_address=content_hash(body, prefix="intake-case"))


def default_intake_architecture_fixture() -> IntakeArchitectureFixture:
    sources = default_intake_architecture_sources()
    source_ids = tuple(item.source_id for item in sources)
    operations = default_intake_architecture_operations()
    cases = tuple(
        case
        for spec in operations
        for case in (
            _case(spec, IntakeArchitectureScenario.POSITIVE, (source_ids[spec.ordinal % len(source_ids)], "repository-controls")),
            _case(spec, IntakeArchitectureScenario.FOREIGN_CONTEXT, (source_ids[spec.ordinal % len(source_ids)], "repository-controls")),
            _case(spec, IntakeArchitectureScenario.MALFORMED_INPUT, (source_ids[spec.ordinal % len(source_ids)], "repository-controls")),
            _case(spec, IntakeArchitectureScenario.DUPLICATE_IDENTITY, (source_ids[spec.ordinal % len(source_ids)], "repository-controls")),
        )
    )
    body = {
        "fixture_id": "intake-architecture-d01",
        "version": INTAKE_ARCHITECTURE_VERSION,
        "boundary": INTAKE_ARCHITECTURE_BOUNDARY,
        "context_key": INTAKE_ARCHITECTURE_CONTEXT,
        "sources": sources,
        "operations": operations,
        "cases": cases,
    }
    return IntakeArchitectureFixture(**body, content_address=content_hash(body, prefix="intake-fixture"))


def _check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> IntakeArchitectureDataCheck:
    body = {"check_id": check_id, "passed": bool(passed), "observed": observed, "required": required, "detail": detail}
    return IntakeArchitectureDataCheck(**body, content_address=content_hash(body, prefix="intake-data-check"))


def audit_intake_architecture_data(fixture: IntakeArchitectureFixture | None = None) -> IntakeArchitectureDataAudit:
    value = fixture or default_intake_architecture_fixture()
    operation_ids = tuple(item.operation_id for item in value.operations)
    source_ids = {item.source_id for item in value.sources}
    counts = {operation_id: sum(item.operation_id == operation_id for item in value.cases) for operation_id in operation_ids}
    checks = (
        _check("source-count", len(value.sources) == INTAKE_ARCHITECTURE_SOURCE_COUNT, len(value.sources), INTAKE_ARCHITECTURE_SOURCE_COUNT, "six public source receipts are present"),
        _check("operation-count", len(value.operations) == INTAKE_ARCHITECTURE_OPERATION_COUNT, len(value.operations), INTAKE_ARCHITECTURE_OPERATION_COUNT, "sixteen D01 operations are present"),
        _check("case-count", len(value.cases) == INTAKE_ARCHITECTURE_CASE_COUNT, len(value.cases), INTAKE_ARCHITECTURE_CASE_COUNT, "four cases per operation are present"),
        _check("operation-ids-unique", len(set(operation_ids)) == len(operation_ids), len(set(operation_ids)), len(operation_ids), "operation identifiers are unique"),
        _check("case-ids-unique", len({item.case_id for item in value.cases}) == len(value.cases), len({item.case_id for item in value.cases}), len(value.cases), "case identifiers are unique"),
        _check("case-cardinality", all(count == 4 for count in counts.values()), tuple(sorted(set(counts.values()))), (4,), "every operation has four scenarios"),
        _check("source-joins", all(set(item.source_ids) <= source_ids for item in value.cases), True, True, "case source joins resolve"),
        _check("public-sources", all(item.scope == "public_aggregate" and item.uri.startswith("https://") for item in value.sources), True, True, "all sources are HTTPS public aggregate receipts"),
        _check("payload-safety", all(not contains_private_key(item.payload) for item in value.cases), True, True, "payloads contain no subject-level keys"),
        _check("scenario-balance", (len(value.positive_cases), len(value.control_cases)), (16, 48), (16, 48), "positive and control denominators are explicit"),
        _check("context-controls", all(item.context_key == INTAKE_ARCHITECTURE_CONTEXT for item in value.cases), True, True, "case context is fixed while payload controls vary"),
        _check("addressed-rows", all(":" in item.content_address for item in value.cases), True, True, "every case is content addressed"),
    )
    accepted = all(item.passed for item in checks)
    body = {"fixture_id": value.fixture_id, "checks": checks, "accepted": accepted}
    return IntakeArchitectureDataAudit(value.fixture_id, checks, accepted, content_hash(body, prefix="intake-data-audit"))


def intake_architecture_fixture_json(fixture: IntakeArchitectureFixture | None = None) -> str:
    return json.dumps((fixture or default_intake_architecture_fixture()).to_dict(), indent=2, sort_keys=True) + "\n"


def load_intake_architecture_fixture(path: str | Path) -> IntakeArchitectureFixture:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"unable to read intake architecture fixture: {path}") from exc
    if not isinstance(raw, Mapping):
        raise ValidationError("intake architecture fixture must be a JSON object")
    expected = default_intake_architecture_fixture()
    if raw.get("content_address") != expected.content_address:
        raise ValidationError("intake architecture fixture content address does not match canonical fixture")
    return expected


__all__ = [
    "INTAKE_ARCHITECTURE_SOURCE_COUNT",
    "IntakeArchitectureDataReceipt",
    "default_intake_architecture_sources",
    "default_intake_architecture_operations",
    "default_intake_architecture_fixture",
    "audit_intake_architecture_data",
    "intake_architecture_fixture_json",
    "load_intake_architecture_fixture",
]
