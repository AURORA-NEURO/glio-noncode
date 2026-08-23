"""Public aggregate fixture and boundary audit for the module fabric."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .capability_registry import CapabilityRegistry, default_capability_registry
from .errors import ValidationError
from .module_fabric_contracts import (
    FabricFixture,
    FabricRecord,
    FabricRole,
    FabricSourceReceipt,
    FabricState,
    MODULE_FABRIC_BOUNDARY,
    MODULE_FABRIC_CONTEXT_KEY,
    MODULE_FABRIC_DOMAIN_IDS,
    MODULE_FABRIC_FOREIGN_CONTEXT,
    MODULE_FABRIC_VERSION,
)
from .module_fabric_support import parse_capability_id, parse_fixture_text, public_source_ids
from .serialization import content_hash, jsonable, require_non_empty


MODULE_FABRIC_SOURCE_COUNT = 5
MODULE_FABRIC_RECORD_COUNT = 32
MODULE_FABRIC_POSITIVE_COUNT = 16
MODULE_FABRIC_CONTROL_COUNT = 16


@dataclass(frozen=True, slots=True)
class FabricDataCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricDataAudit:
    fixture_id: str
    checks: tuple[FabricDataCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _source(source_id: str, title: str, uri: str, version: str) -> FabricSourceReceipt:
    body = {
        "source_id": source_id,
        "title": title,
        "uri": uri,
        "scope": "public_aggregate",
        "version": version,
    }
    return FabricSourceReceipt(**body, content_address=content_hash(body))


def default_module_fabric_sources() -> tuple[FabricSourceReceipt, ...]:
    """Return stable public source receipts used by the checked-in fixture."""

    return (
        _source(
            "blueprint-receipt",
            "GLIO-NONCODE capability blueprint receipt",
            "https://github.com/AURORA-NEURO/glio-noncode",
            "blueprint-2026-08-20",
        ),
        _source(
            "ensembl-reference",
            "Ensembl public reference portal",
            "https://www.ensembl.org/info/data/index.html",
            "public reference portal",
        ),
        _source(
            "ncbi-reference",
            "NCBI public reference resources",
            "https://www.ncbi.nlm.nih.gov/datasets/",
            "public aggregate index",
        ),
        _source(
            "encode-portal",
            "ENCODE public data portal",
            "https://www.encodeproject.org/",
            "public aggregate portal",
        ),
        _source(
            "gdc-portal",
            "NCI Genomic Data Commons public portal",
            "https://portal.gdc.cancer.gov/",
            "public aggregate portal",
        ),
    )


def _record_body(
    record_id: str,
    domain_id: str,
    capability_id: str,
    role: FabricRole,
    payload: Mapping[str, Any],
    expected_state: FabricState,
    expected_issue_codes: tuple[str, ...],
    notes: str,
    source_ids: tuple[str, ...],
) -> dict[str, Any]:
    body = {
        "record_id": record_id,
        "domain_id": domain_id,
        "capability_id": capability_id,
        "role": role,
        "context_key": MODULE_FABRIC_CONTEXT_KEY,
        "source_ids": source_ids,
        "payload": dict(payload),
        "expected_state": expected_state,
        "expected_issue_codes": expected_issue_codes,
        "notes": notes,
    }
    return body


def _record(**kwargs: Any) -> FabricRecord:
    body = _record_body(**kwargs)
    return FabricRecord(**body, content_address=content_hash(body))


def _positive_payload(domain_id: str, capability_id: str, order: int) -> dict[str, Any]:
    return {
        "record_role": "positive",
        "declared_domain_id": domain_id,
        "declared_capability_id": capability_id,
        "required_capability_order": order,
        "declared_context_key": MODULE_FABRIC_CONTEXT_KEY,
        "minimum_implementation_references": 1,
        "minimum_test_references": 1,
        "source_mode": "public_aggregate",
        "claim_boundary": "reference resolution and declared evidence closure only",
    }


def _control_payload(domain_id: str, capability_id: str, order: int) -> dict[str, Any]:
    foreign_domain = MODULE_FABRIC_DOMAIN_IDS[(int(domain_id[1:]) % 16)]
    return {
        "record_role": "control",
        "control_kind": "foreign_context_and_domain",
        "declared_domain_id": foreign_domain,
        "declared_capability_id": capability_id,
        "required_capability_order": order,
        "declared_context_key": MODULE_FABRIC_FOREIGN_CONTEXT,
        "minimum_implementation_references": 1,
        "minimum_test_references": 1,
        "source_mode": "public_aggregate",
        "claim_boundary": "control must remain review-only",
    }


def default_module_fabric_fixture(
    registry: CapabilityRegistry | None = None,
) -> FabricFixture:
    """Build the canonical 32-row fixture from the checked-in capability ledger."""

    catalog = registry or default_capability_registry()
    records: list[FabricRecord] = []
    source_ids = tuple(item.source_id for item in default_module_fabric_sources())
    for index, domain_id in enumerate(MODULE_FABRIC_DOMAIN_IDS):
        capability_id = f"GNC-{domain_id}-C01"
        record = catalog.record(capability_id)
        positive_sources = (source_ids[index % len(source_ids)], "blueprint-receipt")
        records.append(
            _record(
                record_id=f"{domain_id}-C01-POS-001",
                domain_id=domain_id,
                capability_id=capability_id,
                role=FabricRole.POSITIVE,
                payload=_positive_payload(domain_id, capability_id, record.spec.capability_order),
                expected_state=FabricState.ACCEPTED,
                expected_issue_codes=(),
                notes="declared capability references resolve inside its owning domain",
                source_ids=tuple(dict.fromkeys(positive_sources)),
            )
        )
        records.append(
            _record(
                record_id=f"{domain_id}-C01-CTRL-001",
                domain_id=domain_id,
                capability_id=capability_id,
                role=FabricRole.CONTROL,
                payload=_control_payload(domain_id, capability_id, record.spec.capability_order),
                expected_state=FabricState.REVIEW,
                expected_issue_codes=("context_mismatch", "foreign_domain"),
                notes="foreign context and domain controls remain visible and non-publishable",
                source_ids=(source_ids[(index + 1) % len(source_ids)],),
            )
        )
    body = {
        "fixture_id": "module-fabric-public-aggregate-001",
        "fixture_version": MODULE_FABRIC_VERSION,
        "context_key": MODULE_FABRIC_CONTEXT_KEY,
        "evidence_boundary": MODULE_FABRIC_BOUNDARY,
        "sources": default_module_fabric_sources(),
        "records": records,
    }
    return FabricFixture(**body, content_address=content_hash(body))


def _source_from_mapping(value: Mapping[str, Any]) -> FabricSourceReceipt:
    body = {
        "source_id": str(value.get("source_id", "")),
        "title": str(value.get("title", "")),
        "uri": str(value.get("uri", "")),
        "scope": str(value.get("scope", "")),
        "version": str(value.get("version", "")),
    }
    expected = str(value.get("content_address", ""))
    if body["scope"] != "public_aggregate":
        raise ValidationError(f"module-fabric source scope is not public aggregate: {body['source_id']}")
    result = _source(body["source_id"], body["title"], body["uri"], body["version"])
    if expected and expected != result.content_address:
        raise ValidationError(f"module-fabric source address drift: {result.source_id}")
    return result


def _record_from_mapping(value: Mapping[str, Any]) -> FabricRecord:
    raw_role = FabricRole(str(value.get("role", "")))
    raw_state = FabricState(str(value.get("expected_state", "")))
    body = _record_body(
        record_id=str(value.get("record_id", "")),
        domain_id=str(value.get("domain_id", "")),
        capability_id=str(value.get("capability_id", "")),
        role=raw_role,
        payload=value.get("payload", {}) if isinstance(value.get("payload", {}), Mapping) else {},
        expected_state=raw_state,
        expected_issue_codes=tuple(str(item) for item in value.get("expected_issue_codes", ())),
        notes=str(value.get("notes", "")),
        source_ids=tuple(str(item) for item in value.get("source_ids", ())),
    )
    result = FabricRecord(**body, content_address=content_hash(body))
    expected = str(value.get("content_address", ""))
    if expected and expected != result.content_address:
        raise ValidationError(f"module-fabric record address drift: {result.record_id}")
    return result


def load_module_fabric_fixture(path: str | Path) -> FabricFixture:
    """Load a checked-in or caller-supplied fixture and recompute all addresses."""

    location = Path(path)
    root = parse_fixture_text(location.read_text(encoding="utf-8"))
    sources_raw = root.get("sources", ())
    records_raw = root.get("records", ())
    if not isinstance(sources_raw, list) or not isinstance(records_raw, list):
        raise ValidationError("module-fabric fixture requires sources and records arrays")
    sources = tuple(_source_from_mapping(item) for item in sources_raw if isinstance(item, Mapping))
    records = tuple(_record_from_mapping(item) for item in records_raw if isinstance(item, Mapping))
    body = {
        "fixture_id": str(root.get("fixture_id", "")),
        "fixture_version": str(root.get("fixture_version", "")),
        "context_key": str(root.get("context_key", "")),
        "evidence_boundary": str(root.get("evidence_boundary", "")),
        "sources": sources,
        "records": records,
    }
    result = FabricFixture(**body, content_address=content_hash(body))
    expected = str(root.get("content_address", ""))
    if expected and expected != result.content_address:
        raise ValidationError("module-fabric fixture content address drift")
    return result


def module_fabric_fixture_json(fixture: FabricFixture | None = None) -> str:
    """Render canonical JSON suitable for a checked-in public fixture."""

    value = fixture or default_module_fabric_fixture()
    return json.dumps(value.to_dict(), indent=2, sort_keys=True) + "\n"


def _data_check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> FabricDataCheck:
    body = {
        "check_id": check_id,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return FabricDataCheck(**body, content_address=content_hash(body))


def audit_module_fabric_data(
    fixture: FabricFixture | None = None,
    registry: CapabilityRegistry | None = None,
) -> FabricDataAudit:
    """Audit scope, identity, source closure, balance, and address stability."""

    value = fixture or default_module_fabric_fixture(registry)
    catalog = registry or default_capability_registry()
    source_ids = tuple(item.source_id for item in value.sources)
    checks = (
        _data_check("identity:version", value.fixture_version == MODULE_FABRIC_VERSION, value.fixture_version, MODULE_FABRIC_VERSION, "fixture version is pinned"),
        _data_check("identity:boundary", value.evidence_boundary == MODULE_FABRIC_BOUNDARY, value.evidence_boundary, MODULE_FABRIC_BOUNDARY, "fixture boundary is public aggregate"),
        _data_check("identity:context", value.context_key == MODULE_FABRIC_CONTEXT_KEY, value.context_key, MODULE_FABRIC_CONTEXT_KEY, "fixture context is exact"),
        _data_check("sources:count", len(value.sources) == MODULE_FABRIC_SOURCE_COUNT, len(value.sources), MODULE_FABRIC_SOURCE_COUNT, "source receipt floor is explicit"),
        _data_check("sources:unique", len(source_ids) == len(set(source_ids)), len(source_ids), "unique source IDs", "source IDs are unique"),
        _data_check("sources:https", all(item.uri.startswith("https://") for item in value.sources), [item.uri.startswith("https://") for item in value.sources], True, "all source receipts use HTTPS"),
        _data_check("records:count", len(value.records) == MODULE_FABRIC_RECORD_COUNT, len(value.records), MODULE_FABRIC_RECORD_COUNT, "record denominator is explicit"),
        _data_check("records:unique", len({item.record_id for item in value.records}) == len(value.records), len({item.record_id for item in value.records}), len(value.records), "record IDs are unique"),
        _data_check("records:domain-coverage", set(value.domain_ids) == set(MODULE_FABRIC_DOMAIN_IDS), value.domain_ids, MODULE_FABRIC_DOMAIN_IDS, "all sixteen domains are present"),
        _data_check("records:balance", len(value.positive_records) == MODULE_FABRIC_POSITIVE_COUNT and len(value.control_records) == MODULE_FABRIC_CONTROL_COUNT, {"positive": len(value.positive_records), "control": len(value.control_records)}, {"positive": MODULE_FABRIC_POSITIVE_COUNT, "control": MODULE_FABRIC_CONTROL_COUNT}, "positive and control rows are balanced"),
        _data_check("records:source-closure", all(public_source_ids(item.source_ids, source_ids) for item in value.records), True, True, "every record joins only known public sources"),
        _data_check("records:catalog-closure", all(_catalog_has(catalog, item.capability_id) for item in value.records), True, True, "every fixture capability exists in the ledger"),
        _data_check("records:addresses", all(item.content_address.startswith("sha256:") for item in value.records), True, True, "every record is content addressed"),
        _data_check("fixture:address", value.content_address.startswith("sha256:"), value.content_address[:7], "sha256:", "fixture is content addressed"),
    )
    passed = sum(item.passed for item in checks)
    body = {"fixture_id": value.fixture_id, "checks": checks, "accepted": passed == len(checks)}
    return FabricDataAudit(value.fixture_id, checks, passed == len(checks), content_hash(body))


def _catalog_has(registry: CapabilityRegistry, capability_id: str) -> bool:
    try:
        registry.record(capability_id)
    except ValidationError:
        return False
    return True


__all__ = [
    "MODULE_FABRIC_CONTROL_COUNT",
    "MODULE_FABRIC_POSITIVE_COUNT",
    "MODULE_FABRIC_RECORD_COUNT",
    "MODULE_FABRIC_SOURCE_COUNT",
    "FabricDataAudit",
    "FabricDataCheck",
    "audit_module_fabric_data",
    "default_module_fabric_fixture",
    "default_module_fabric_sources",
    "load_module_fabric_fixture",
    "module_fabric_fixture_json",
]
