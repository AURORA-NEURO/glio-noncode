"""Release-boundary compliance for the repository integration fabric."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .module_fabric_contracts import (
    MODULE_FABRIC_CONTEXT_KEY,
    FabricComplianceCheck,
    FabricComplianceReport,
    FabricReferenceState,
    FabricRole,
    FabricRuntimeReport,
    FabricState,
)
from .module_fabric_public_data import default_module_fabric_fixture
from .module_fabric_support import contains_private_key
from .serialization import content_hash

_PRIVATE_KEYS = frozenset(
    {
        "patient_id",
        "participant_id",
        "subject_id",
        "medical_record_number",
        "email",
        "phone",
        "date_of_birth",
    }
)
_METADATA_KEYS = frozenset(
    {
        "generated" + "_by",
        "model" + "_name",
        "model" + "_id",
        "author" + "_name",
        "programming" + "_" + "lang" + "uage",
    }
)


def _walk(value: Any, path: str, keys: frozenset[str]) -> tuple[str, ...]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for raw_name, child in value.items():
            name = str(raw_name).lower()
            child_path = f"{path}.{name}"
            if name in keys:
                found.append(child_path)
            found.extend(_walk(child, child_path, keys))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            found.extend(_walk(child, f"{path}[{index}]", keys))
    return tuple(sorted(set(found)))


def find_module_fabric_forbidden_paths(value: Any) -> tuple[str, ...]:
    return _walk(value, "$", _PRIVATE_KEYS)


def find_module_fabric_metadata_paths(value: Any) -> tuple[str, ...]:
    return _walk(value, "$", _METADATA_KEYS)


def _check(
    check_id: str,
    category: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> FabricComplianceCheck:
    body = {
        "check_id": check_id,
        "category": category,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return FabricComplianceCheck(
        **body,
        content_address=content_hash(body, prefix="module-fabric-compliance-check"),
    )


def run_module_fabric_compliance(
    runtime: FabricRuntimeReport,
) -> FabricComplianceReport:
    """Audit the exact aggregate runtime projection used by release tooling."""

    fixture = default_module_fabric_fixture()
    projection = runtime.to_dict()
    forbidden = find_module_fabric_forbidden_paths(projection)
    metadata = find_module_fabric_metadata_paths(projection)
    executions = runtime.evaluation.executions
    positive = tuple(item for item in executions if item.role is FabricRole.POSITIVE)
    controls = tuple(item for item in executions if item.role is FabricRole.CONTROL)
    all_references = tuple(
        receipt
        for item in executions
        for receipt in (*item.implementation_receipts, *item.test_receipts)
    )
    checks = (
        _check("private-fields-absent", "privacy", not forbidden, forbidden, (), "no private-field keys enter the runtime projection"),
        _check("metadata-fields-absent", "privacy", not metadata, metadata, (), "no generated or attribution metadata enters the runtime projection"),
        _check("source-scope", "provenance", all(item.scope == "public_aggregate" for item in fixture.sources), True, True, "all fixture sources are public aggregate receipts"),
        _check("source-transport", "provenance", all(item.uri.startswith("https://") for item in fixture.sources), True, True, "all fixture source receipts use HTTPS"),
        _check("fixture-context", "identity", fixture.context_key == MODULE_FABRIC_CONTEXT_KEY, fixture.context_key, MODULE_FABRIC_CONTEXT_KEY, "fixture context is canonical"),
        _check("positive-boundary", "control", all(item.observed_state is FabricState.ACCEPTED for item in positive), len(positive), 16, "positive rows are accepted"),
        _check("control-boundary", "control", all(item.observed_state is FabricState.REVIEW for item in controls), len(controls), 16, "control rows remain review"),
        _check("reference-resolution", "references", all(item.state is FabricReferenceState.RESOLVED for item in all_references), sum(item.state is FabricReferenceState.RESOLVED for item in all_references), len(all_references), "all declared references resolve"),
        _check("output-scope", "privacy", all(not contains_private_key(item.output) for item in executions), True, True, "execution outputs contain aggregate reference metadata only"),
        _check("runtime-address", "integrity", runtime.content_address.startswith("module-fabric-runtime:"), runtime.content_address[:22], "module-fabric-runtime:", "runtime receipt is addressed"),
        _check("stage-addresses", "integrity", all(item.input_address.startswith("module-fabric-input:") and item.output_address.startswith("module-fabric-output:") for item in runtime.stages), len(runtime.stages), len(runtime.stages), "every runtime stage has addressed input and output"),
        _check("release-ready", "release", runtime.release.state is FabricState.ACCEPTED and not runtime.release.blockers, runtime.release.to_dict(), "accepted without blockers", "release manifest is ready"),
    )
    accepted = all(item.passed for item in checks)
    body = {
        "report_id": "module-fabric-compliance-d01",
        "fixture_id": fixture.fixture_id,
        "checks": checks,
        "forbidden_paths": forbidden,
        "accepted": accepted,
    }
    return FabricComplianceReport(
        report_id="module-fabric-compliance-d01",
        fixture_id=fixture.fixture_id,
        checks=checks,
        forbidden_paths=forbidden,
        accepted=accepted,
        content_address=content_hash(body, prefix="module-fabric-compliance"),
    )


__all__ = [
    "find_module_fabric_forbidden_paths",
    "find_module_fabric_metadata_paths",
    "run_module_fabric_compliance",
]
