"""Source-qualified identity resolution for the D01 architecture."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .identity_beta import VariantEquivalenceResolver, VariantIdentityRecord
from .models import VariantIdentity
from .intake_architecture_contracts import (
    INTAKE_ARCHITECTURE_CONTEXT,
    IntakeArchitectureCase,
    IntakeArchitectureIdentityReceipt,
    IntakeArchitectureOperation,
    IntakeArchitectureState,
    addressed,
)


def _record(record_id: str, payload: Mapping[str, Any], source_id: str, aliases: tuple[str, ...] = ()) -> VariantIdentityRecord:
    raw_variant = payload.get("variant", payload)
    if not isinstance(raw_variant, Mapping):
        raise ValidationError("identity record requires a variant object")
    return VariantIdentityRecord(
        record_id=record_id,
        variant=VariantIdentity.from_dict(raw_variant),
        source_id=source_id,
        source_version="d01-public-reference-v1",
        raw_hash=addressed(raw_variant, "identity-raw"),
        aliases=tuple(dict.fromkeys((*aliases, str(raw_variant.get("variant_id", "")), *[str(item) for item in payload.get("public_identifiers", ())]))),
        sample_id="public-aggregate",
        batch_id="public-batch-001",
        context_key=INTAKE_ARCHITECTURE_CONTEXT,
    )


def resolve_public_identity(payload: Mapping[str, Any], source_id: str) -> tuple[int, int, str | None, tuple[str, ...], IntakeArchitectureState, str]:
    records_raw = payload.get("records")
    if isinstance(records_raw, list) and records_raw:
        records = tuple(_record(str(item.get("record_id", f"public-record-{index}")), item, source_id, tuple(str(alias) for alias in item.get("aliases", ()))) for index, item in enumerate(records_raw, start=1) if isinstance(item, Mapping))
    else:
        records = (_record("public-record-1", payload, source_id, tuple(str(alias) for alias in payload.get("aliases", ()))),)
    query = str(payload.get("query", payload.get("public_identifiers", [records[0].variant.variant_id])[0]))
    result = VariantEquivalenceResolver().resolve(records, query, genome_build="GRCh38", context_key=INTAKE_ARCHITECTURE_CONTEXT)
    state = IntakeArchitectureState.ACCEPTED if result.state.value == "supported" else IntakeArchitectureState.REVIEW
    return len(records), len(result.record_ids), result.equivalence_key, result.aliases, state, result.content_address


def check_batch_identity(payload: Mapping[str, Any]) -> tuple[IntakeArchitectureState, tuple[str, ...], str]:
    sample_ids = tuple(str(value) for value in payload.get("sample_ids", ()))
    issues: list[str] = []
    if not sample_ids:
        issues.append("sample_identity_missing")
    if len(sample_ids) != len(set(sample_ids)):
        issues.append("sample_identity_duplicate")
    if int(payload.get("declared_record_count", len(sample_ids))) != len(sample_ids):
        issues.append("batch_count_mismatch")
    state = IntakeArchitectureState.ACCEPTED if not issues else IntakeArchitectureState.REVIEW
    return state, tuple(sorted(set(issues))), addressed({"sample_count": len(sample_ids), "issues": issues}, "batch-identity")


def reconcile_aliases(payload: Mapping[str, Any], source_id: str) -> tuple[int, tuple[str, ...], IntakeArchitectureState, str]:
    records_raw = payload.get("records", ())
    records = tuple(_record(str(item.get("record_id", f"public-record-{index}")), item, source_id, tuple(str(alias) for alias in item.get("aliases", ()))) for index, item in enumerate(records_raw, start=1) if isinstance(item, Mapping))
    if not records:
        return 0, ("identity_records_missing",), IntakeArchitectureState.REVIEW, addressed(payload, "identity-reconcile-error")
    keys = {item.equivalence_key for item in records}
    state = IntakeArchitectureState.ACCEPTED if len(keys) == 1 else IntakeArchitectureState.REVIEW
    return len(records), ("duplicate_identity",) if len(records) > 1 else (), state, addressed({"record_count": len(records), "keys": sorted(keys)}, "identity-reconcile")


def resolve_intake_architecture_identity(case: IntakeArchitectureCase) -> IntakeArchitectureIdentityReceipt:
    payload = case.payload
    try:
        operation_number = int(case.operation_id[-2:])
        operation = list(IntakeArchitectureOperation)[operation_number - 1]
        if operation is IntakeArchitectureOperation.BATCH_SAMPLE_IDENTITY:
            state, issues, address = check_batch_identity(payload)
            body = {"case_id": case.case_id, "resolver": "BatchSampleIdentityChecker", "record_count": int(payload.get("declared_record_count", 0)), "matched_record_count": 0, "equivalence_key": None, "aliases": (), "state": state}
        elif operation is IntakeArchitectureOperation.DUPLICATE_ALIAS_RECONCILIATION:
            count, issues, state, address = reconcile_aliases(payload, case.source_ids[0])
            body = {"case_id": case.case_id, "resolver": "DuplicateAliasReconciler", "record_count": count, "matched_record_count": count, "equivalence_key": None, "aliases": (), "state": state}
        else:
            count, matched, key, aliases, state, address = resolve_public_identity(payload, case.source_ids[0])
            issues = ()
            body = {"case_id": case.case_id, "resolver": "VariantEquivalenceResolver", "record_count": count, "matched_record_count": matched, "equivalence_key": key, "aliases": aliases, "state": state}
    except (TypeError, ValueError, KeyError, IndexError, ValidationError) as exc:
        address = addressed(payload, "identity-error")
        issues = ("malformed_input", str(exc))
        body = {"case_id": case.case_id, "resolver": "identity-boundary", "record_count": 0, "matched_record_count": 0, "equivalence_key": None, "aliases": (), "state": IntakeArchitectureState.REVIEW}
    if case.scenario.value == "duplicate_identity":
        issues = tuple(sorted(set(issues) | {"duplicate_identity"}))
        body["state"] = IntakeArchitectureState.REVIEW
    return IntakeArchitectureIdentityReceipt(**body, content_address=addressed({**body, "issues": issues, "input_address": address}, "intake-identity-receipt"))


__all__ = [
    "resolve_public_identity",
    "check_batch_identity",
    "reconcile_aliases",
    "resolve_intake_architecture_identity",
]
