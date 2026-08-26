"""Build and render the public cross-plane release attestation.

This boundary joins three independently addressed products of the repository:
the whole-product release-assurance runtime, the D01-D16 program-release
closure, and the mission-plan release catalog gate.  It performs no workflow
execution and does not copy the source rows from any of those planes.  The
result is a compact, deterministic decision that can be transported and
verified by a consumer that does not have the source checkout.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping
from io import StringIO
from typing import Any

from .errors import ValidationError
from .mission_plan_release import build_mission_plan_release
from .mission_plan_release_catalog import (
    MissionPlanReleaseCatalog,
    build_mission_plan_release_catalog,
)
from .mission_plan_release_catalog_gate import (
    MissionPlanReleaseCatalogGate,
    build_mission_plan_release_catalog_gate,
)
from .mission_runtime_public import build_public_mission_plan
from .program_release_closure_bundle import build_program_release_snapshot
from .program_release_closure_contracts import ProgramReleaseSnapshot
from .release_assurance_attestation_contracts import (
    RELEASE_ASSURANCE_ATTESTATION_BOUNDARY,
    RELEASE_ASSURANCE_ATTESTATION_CHECK_COUNT,
    RELEASE_ASSURANCE_ATTESTATION_CHECKS_PER_COMPONENT,
    RELEASE_ASSURANCE_ATTESTATION_COMPONENT_COUNT,
    RELEASE_ASSURANCE_ATTESTATION_COMPONENT_IDS,
    RELEASE_ASSURANCE_ATTESTATION_CROSS_CHECK_COUNT,
    RELEASE_ASSURANCE_ATTESTATION_SCHEMA_VERSION,
    RELEASE_ASSURANCE_ATTESTATION_VERSION,
    ReleaseAssuranceAttestation,
    ReleaseAssuranceAttestationCheck,
    ReleaseAssuranceAttestationComponent,
    ReleaseAssuranceAttestationPolicy,
)
from .release_assurance_contracts import ReleaseAssuranceRuntimeReport
from .release_assurance_support import forbidden_keys
from .serialization import canonical_json, content_hash, jsonable, require_non_empty


def _check(
    check_id: str,
    component_id: str,
    category: str,
    passed: bool,
    observed: Any,
    expected: Any,
    evidence_addresses: tuple[str, ...],
    detail: str,
) -> ReleaseAssuranceAttestationCheck:
    body = {
        "check_id": check_id,
        "component_id": component_id,
        "category": category,
        "passed": bool(passed),
        "observed": observed,
        "expected": expected,
        "evidence_addresses": evidence_addresses,
        "detail": detail,
    }
    return ReleaseAssuranceAttestationCheck(
        **body,
        content_address=content_hash(body, prefix="release-assurance-attestation-check"),
    )


def _component(
    component_id: str,
    title: str,
    source_address: str,
    state: str,
    observed_count: int,
    expected_count: int,
    accepted: bool,
    dependencies: tuple[str, ...],
    limitations: tuple[str, ...],
) -> ReleaseAssuranceAttestationComponent:
    body = {
        "component_id": component_id,
        "title": title,
        "source_address": source_address,
        "state": state,
        "observed_count": observed_count,
        "expected_count": expected_count,
        "readiness_percent": min(100.0, round(100.0 * observed_count / max(1, expected_count), 2)),
        "dependency_ids": dependencies,
        "limitations": limitations,
        "accepted": accepted,
    }
    return ReleaseAssuranceAttestationComponent(
        **body,
        content_address=content_hash(body, prefix="release-assurance-attestation-component"),
    )


def _private_paths(value: Any, path: str = "") -> tuple[str, ...]:
    """Find prohibited public metadata recursively without returning values."""

    if isinstance(value, Mapping):
        result: list[str] = []
        for key, child in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}" if path else key_text
            if key_text.casefold() in {
                "agent",
                "agent_id",
                "assistant",
                "author",
                "email",
                "language",
                "model",
                "patient",
                "producer",
                "programming_language",
                "request",
                "subject",
                "token",
                "tool_id",
            }:
                result.append(child_path)
            result.extend(_private_paths(child, child_path))
        return tuple(result)
    if isinstance(value, (list, tuple)):
        result: list[str] = []
        for index, child in enumerate(value):
            result.extend(_private_paths(child, f"{path}[{index}]"))
        return tuple(result)
    return ()


def build_default_release_assurance_catalog_gate() -> tuple[
    MissionPlanReleaseCatalog, MissionPlanReleaseCatalogGate
]:
    """Build one minimal public catalog for the default product attestation."""

    receipt = build_public_mission_plan(
        {
            "mission": {
                "mission_id": "glio-noncode-product-release",
                "project_id": "glio-noncode",
                "intended_use": "research hypothesis exploration",
                "requested_question": "bounded release assurance",
                "claim_ceiling": "hypothesis",
            },
            "workflow_id": "product-release-workflow",
            "workflow_steps": [
                {
                    "step_id": "validate-release",
                    "kind": "validate",
                    "resource": {"cpu": 1, "memory_gb": 1, "storage_gb": 1, "max_seconds": 60},
                    "input_contract": "public-release",
                    "output_contract": "release-assurance",
                }
            ],
        }
    )
    release = build_mission_plan_release(receipt, release_id="glio-noncode-product-release")
    catalog = build_mission_plan_release_catalog(
        [release], catalog_id="glio-noncode-product-release-catalog"
    ).catalog
    return catalog, build_mission_plan_release_catalog_gate(catalog)


def _as_policy(
    value: ReleaseAssuranceAttestationPolicy | Mapping[str, Any] | None,
) -> ReleaseAssuranceAttestationPolicy:
    if value is None:
        return ReleaseAssuranceAttestationPolicy()
    return (
        value
        if isinstance(value, ReleaseAssuranceAttestationPolicy)
        else ReleaseAssuranceAttestationPolicy.from_mapping(value)
    )


def _catalog_check_observed(
    gate: MissionPlanReleaseCatalogGate, check_id: str, fallback: int
) -> int:
    for item in gate.checks:
        if (
            item.check_id == check_id
            and isinstance(item.observed, int)
            and not isinstance(item.observed, bool)
        ):
            return item.observed
    return fallback


def _build_components(
    runtime: ReleaseAssuranceRuntimeReport,
    program_release: ProgramReleaseSnapshot,
    catalog: MissionPlanReleaseCatalog,
    catalog_gate: MissionPlanReleaseCatalogGate,
    policy: ReleaseAssuranceAttestationPolicy,
) -> tuple[ReleaseAssuranceAttestationComponent, ...]:
    return (
        _component(
            "release-assurance",
            "Whole-product release-assurance runtime",
            runtime.content_address,
            runtime.state.value,
            len(runtime.stages),
            policy.minimum_runtime_stage_count,
            runtime.accepted,
            (),
            ("This row certifies deterministic aggregate controls, not scientific validity.",),
        ),
        _component(
            "program-release-closure",
            "D01-D16 program release closure",
            program_release.content_address,
            "ready" if program_release.accepted else "blocked",
            len(program_release.domains),
            policy.minimum_program_domain_count,
            program_release.accepted,
            ("release-assurance",),
            ("The closure preserves research-use and public aggregate boundaries.",),
        ),
        _component(
            "mission-plan-release-catalog-gate",
            "Mission-plan release catalog gate",
            catalog_gate.content_address,
            "ready" if catalog_gate.accepted else "blocked",
            len(catalog.entries),
            policy.minimum_catalog_entry_count,
            catalog_gate.accepted,
            ("program-release-closure",),
            ("The catalog gate is a public handoff policy, not workflow authorization.",),
        ),
    )


def _component_checks(
    component: ReleaseAssuranceAttestationComponent,
    runtime: ReleaseAssuranceRuntimeReport,
    program_release: ProgramReleaseSnapshot,
    catalog: MissionPlanReleaseCatalog,
    catalog_gate: MissionPlanReleaseCatalogGate,
    policy: ReleaseAssuranceAttestationPolicy,
) -> tuple[ReleaseAssuranceAttestationCheck, ...]:
    address = (component.source_address,)
    cid = component.component_id
    if cid == "release-assurance":
        values = (
            (
                "source-address",
                "address",
                bool(component.source_address),
                component.source_address,
                "non-empty source address",
                "runtime address is present",
            ),
            (
                "accepted",
                "acceptance",
                not policy.require_runtime_accepted or runtime.accepted,
                runtime.accepted,
                True,
                "runtime acceptance follows policy",
            ),
            (
                "stage-count",
                "depth",
                len(runtime.stages) >= policy.minimum_runtime_stage_count,
                len(runtime.stages),
                policy.minimum_runtime_stage_count,
                "runtime exposes the required stage depth",
            ),
            (
                "stage-states",
                "state",
                all(item.state.value == "ready" for item in runtime.stages),
                tuple(item.state.value for item in runtime.stages),
                "ready",
                "every runtime stage is ready",
            ),
            (
                "replay",
                "determinism",
                runtime.replay.accepted,
                runtime.replay.deterministic,
                True,
                "runtime replay is deterministic",
            ),
            (
                "boundary",
                "boundary",
                not forbidden_keys(runtime.to_dict()),
                (),
                "no restricted public metadata",
                "runtime projection remains public",
            ),
        )
    elif cid == "program-release-closure":
        values = (
            (
                "source-address",
                "address",
                bool(component.source_address),
                component.source_address,
                "non-empty source address",
                "closure address is present",
            ),
            (
                "accepted",
                "acceptance",
                not policy.require_program_release_accepted or program_release.accepted,
                program_release.accepted,
                True,
                "program closure acceptance follows policy",
            ),
            (
                "domain-count",
                "depth",
                len(program_release.domains) >= policy.minimum_program_domain_count,
                len(program_release.domains),
                policy.minimum_program_domain_count,
                "D01-D16 domains meet the closure depth",
            ),
            (
                "domain-acceptance",
                "acceptance",
                all(item.accepted for item in program_release.domains),
                sum(item.accepted for item in program_release.domains),
                len(program_release.domains),
                "every program domain is accepted",
            ),
            (
                "gate-acceptance",
                "acceptance",
                all(item.passed for item in program_release.gates),
                sum(item.passed for item in program_release.gates),
                len(program_release.gates),
                "every program release gate passes",
            ),
            (
                "boundary",
                "boundary",
                not forbidden_keys(jsonable(program_release)),
                (),
                "no restricted public metadata",
                "closure projection remains public",
            ),
        )
    else:
        values = (
            (
                "source-address",
                "address",
                bool(component.source_address),
                component.source_address,
                "non-empty source address",
                "catalog gate address is present",
            ),
            (
                "accepted",
                "acceptance",
                not policy.require_catalog_gate_accepted or catalog_gate.accepted,
                catalog_gate.accepted,
                True,
                "catalog gate acceptance follows policy",
            ),
            (
                "entry-count",
                "depth",
                len(catalog.entries) >= policy.minimum_catalog_entry_count,
                len(catalog.entries),
                policy.minimum_catalog_entry_count,
                "catalog entries meet the minimum",
            ),
            (
                "check-count",
                "depth",
                len(catalog_gate.checks) >= policy.minimum_catalog_check_count,
                len(catalog_gate.checks),
                policy.minimum_catalog_check_count,
                "catalog gate exposes the minimum checks",
            ),
            (
                "check-acceptance",
                "acceptance",
                all(item.accepted for item in catalog_gate.checks),
                catalog_gate.passed_check_count,
                len(catalog_gate.checks),
                "every catalog gate check passes",
            ),
            (
                "boundary",
                "boundary",
                not forbidden_keys(jsonable(catalog_gate)),
                (),
                "no restricted public metadata",
                "catalog gate projection remains public",
            ),
        )
    return tuple(
        _check(f"{cid}:{suffix}", cid, category, passed, observed, expected, address, detail)
        for suffix, category, passed, observed, expected, detail in values
    )


def _cross_checks(
    components: tuple[ReleaseAssuranceAttestationComponent, ...],
    checks: tuple[ReleaseAssuranceAttestationCheck, ...],
    runtime: ReleaseAssuranceRuntimeReport,
    program_release: ProgramReleaseSnapshot,
    catalog: MissionPlanReleaseCatalog,
    catalog_gate: MissionPlanReleaseCatalogGate,
    policy: ReleaseAssuranceAttestationPolicy,
) -> tuple[ReleaseAssuranceAttestationCheck, ...]:
    addresses = tuple(item.source_address for item in components)
    checks_by_component = {
        component_id: sum(item.component_id == component_id for item in checks)
        for component_id in RELEASE_ASSURANCE_ATTESTATION_COMPONENT_IDS
    }
    return (
        _check(
            "cross:component-closure",
            "cross-plane",
            "closure",
            tuple(item.component_id for item in components)
            == RELEASE_ASSURANCE_ATTESTATION_COMPONENT_IDS,
            tuple(item.component_id for item in components),
            RELEASE_ASSURANCE_ATTESTATION_COMPONENT_IDS,
            addresses,
            "all required component rows are present in dependency order",
        ),
        _check(
            "cross:component-count",
            "cross-plane",
            "closure",
            len(components) == RELEASE_ASSURANCE_ATTESTATION_COMPONENT_COUNT,
            len(components),
            RELEASE_ASSURANCE_ATTESTATION_COMPONENT_COUNT,
            addresses,
            "component denominator is closed",
        ),
        _check(
            "cross:address-uniqueness",
            "cross-plane",
            "address",
            not policy.require_unique_component_addresses or len(addresses) == len(set(addresses)),
            len(addresses),
            len(set(addresses)),
            addresses,
            "component source addresses are unique when required",
        ),
        _check(
            "cross:check-closure",
            "cross-plane",
            "closure",
            len(checks)
            == RELEASE_ASSURANCE_ATTESTATION_COMPONENT_COUNT
            * RELEASE_ASSURANCE_ATTESTATION_CHECKS_PER_COMPONENT
            and all(checks_by_component.values()),
            len(checks),
            RELEASE_ASSURANCE_ATTESTATION_COMPONENT_COUNT
            * RELEASE_ASSURANCE_ATTESTATION_CHECKS_PER_COMPONENT,
            tuple(item.content_address for item in checks),
            "check denominator is closed across every component",
        ),
        _check(
            "cross:all-checks",
            "cross-plane",
            "acceptance",
            not policy.require_all_checks_passed or all(item.passed for item in checks),
            sum(item.passed for item in checks),
            len(checks),
            tuple(item.content_address for item in checks),
            "all retained checks pass when policy requires it",
        ),
        _check(
            "cross:source-addresses",
            "cross-plane",
            "lineage",
            all(addresses),
            addresses,
            "non-empty addresses",
            addresses,
            "every component retains an immutable source address",
        ),
        _check(
            "cross:catalog-link",
            "cross-plane",
            "lineage",
            catalog_gate.catalog_address == catalog.content_address,
            catalog_gate.catalog_address,
            catalog.content_address,
            (catalog_gate.content_address, catalog.content_address),
            "catalog gate points at the exact catalog",
        ),
        _check(
            "cross:source-acceptance",
            "cross-plane",
            "acceptance",
            runtime.accepted and program_release.accepted and catalog_gate.accepted,
            {
                "runtime": runtime.accepted,
                "program": program_release.accepted,
                "catalog": catalog_gate.accepted,
            },
            True,
            addresses,
            "all source planes are accepted",
        ),
    )


def build_release_assurance_attestation(
    runtime: ReleaseAssuranceRuntimeReport | None = None,
    *,
    program_release: ProgramReleaseSnapshot | None = None,
    catalog: MissionPlanReleaseCatalog | None = None,
    catalog_gate: MissionPlanReleaseCatalogGate | None = None,
    policy: ReleaseAssuranceAttestationPolicy | Mapping[str, Any] | None = None,
    attestation_id: str = "glio-noncode-release-assurance-attestation",
    bundle_id: str = "glio-noncode-release-assurance-attestation",
    run_id: str = "glio-noncode-release-assurance-attestation-run",
) -> ReleaseAssuranceAttestation:
    """Build the final address-only attestation from verified source planes."""

    require_non_empty(attestation_id, "attestation_id")
    require_non_empty(bundle_id, "bundle_id")
    require_non_empty(run_id, "run_id")
    selected_policy = _as_policy(policy)
    if (catalog is None) != (catalog_gate is None):
        raise ValidationError("catalog and catalog_gate must be supplied together")
    if runtime is None:
        from .release_assurance_runtime import run_release_assurance

        selected_runtime = run_release_assurance()
    else:
        selected_runtime = runtime
    selected_program = program_release or build_program_release_snapshot()
    if catalog is None and catalog_gate is None:
        default_catalog, default_gate = build_default_release_assurance_catalog_gate()
        selected_catalog = catalog or default_catalog
        selected_gate = catalog_gate or default_gate
    else:
        selected_catalog = catalog
        selected_gate = catalog_gate
    if selected_gate.catalog_address != selected_catalog.content_address:
        raise ValidationError("catalog gate does not point at the supplied catalog")
    components = _build_components(
        selected_runtime, selected_program, selected_catalog, selected_gate, selected_policy
    )
    checks = tuple(
        item
        for component in components
        for item in _component_checks(
            component,
            selected_runtime,
            selected_program,
            selected_catalog,
            selected_gate,
            selected_policy,
        )
    )
    checks += _cross_checks(
        components,
        checks,
        selected_runtime,
        selected_program,
        selected_catalog,
        selected_gate,
        selected_policy,
    )
    overall = round(sum(item.readiness_percent for item in components) / max(1, len(components)), 2)
    accepted = (
        len(components) == RELEASE_ASSURANCE_ATTESTATION_COMPONENT_COUNT
        and len(checks) == RELEASE_ASSURANCE_ATTESTATION_CHECK_COUNT
        and all(item.passed for item in checks)
        and not _private_paths(
            {"components": components, "checks": checks, "policy": selected_policy}
        )
    )
    body = {
        "attestation_version": RELEASE_ASSURANCE_ATTESTATION_VERSION,
        "schema_version": RELEASE_ASSURANCE_ATTESTATION_SCHEMA_VERSION,
        "attestation_id": attestation_id,
        "bundle_id": bundle_id,
        "run_id": run_id,
        "policy": selected_policy,
        "components": components,
        "checks": checks,
        "overall_percent": overall,
        "accepted": accepted,
    }
    return ReleaseAssuranceAttestation(
        **body,
        content_address=content_hash(body, prefix="release-assurance-attestation"),
    )


def release_assurance_attestation_json(
    value: ReleaseAssuranceAttestation | Mapping[str, Any],
) -> str:
    """Return canonical JSON for a public attestation."""

    selected = (
        value
        if isinstance(value, ReleaseAssuranceAttestation)
        else ReleaseAssuranceAttestation.from_mapping(value)
    )
    return canonical_json(selected.to_dict()) + "\n"


def release_assurance_attestation_csv(
    value: ReleaseAssuranceAttestation | Mapping[str, Any],
) -> str:
    """Return stable component and check rows for tabular review."""

    selected = (
        value
        if isinstance(value, ReleaseAssuranceAttestation)
        else ReleaseAssuranceAttestation.from_mapping(value)
    )
    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        (
            "row_type",
            "row_id",
            "component_id",
            "category",
            "state",
            "passed",
            "observed",
            "expected",
            "source_address",
            "content_address",
        )
    )
    for item in selected.components:
        writer.writerow(
            (
                "component",
                item.component_id,
                item.component_id,
                "component",
                item.state,
                str(item.accepted).lower(),
                item.observed_count,
                item.expected_count,
                item.source_address,
                item.content_address,
            )
        )
    for item in selected.checks:
        writer.writerow(
            (
                "check",
                item.check_id,
                item.check_id,
                item.category,
                "",
                str(item.passed).lower(),
                canonical_json(item.observed),
                canonical_json(item.expected),
                "|".join(item.evidence_addresses),
                item.content_address,
            )
        )
    return output.getvalue()


def release_assurance_attestation_markdown(
    value: ReleaseAssuranceAttestation | Mapping[str, Any],
) -> str:
    """Render a deterministic reviewer summary without source payloads."""

    selected = (
        value
        if isinstance(value, ReleaseAssuranceAttestation)
        else ReleaseAssuranceAttestation.from_mapping(value)
    )
    lines = [
        "# Release assurance attestation",
        "",
        f"- Attestation: `{selected.attestation_id}`",
        f"- Boundary: `{RELEASE_ASSURANCE_ATTESTATION_BOUNDARY}`",
        f"- Readiness: `{selected.overall_percent:.2f}%`",
        f"- Accepted: `{str(selected.accepted).lower()}`",
        f"- Components: `{selected.component_count}`",
        f"- Checks: `{selected.passed_check_count}/{selected.check_count}`",
        "",
        "## Components",
        "",
        "| Component | State | Observed | Expected | Accepted | Address |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ]
    lines.extend(
        f"| {item.title} | {item.state} | {item.observed_count} | "
        f"{item.expected_count} | {str(item.accepted).lower()} | "
        f"`{item.source_address}` |"
        for item in selected.components
    )
    lines.extend(("", "## Failed checks", ""))
    failed = [item for item in selected.checks if not item.passed]
    lines.extend(f"- `{item.check_id}`: {item.detail}" for item in failed) or lines.append("- None")
    lines.extend(("", "This artifact contains public aggregate release evidence only."))
    return "\n".join(lines) + "\n"


def release_assurance_attestation_export_payloads(
    value: ReleaseAssuranceAttestation | Mapping[str, Any],
) -> dict[str, bytes]:
    """Return exact UTF-8 payloads used by the portable packet."""

    selected = (
        value
        if isinstance(value, ReleaseAssuranceAttestation)
        else ReleaseAssuranceAttestation.from_mapping(value)
    )
    component_output = StringIO()
    component_writer = csv.writer(component_output, lineterminator="\n")
    component_writer.writerow(
        (
            "component_id",
            "title",
            "state",
            "observed_count",
            "expected_count",
            "readiness_percent",
            "accepted",
            "source_address",
            "content_address",
        )
    )
    for item in selected.components:
        component_writer.writerow(
            (
                item.component_id,
                item.title,
                item.state,
                item.observed_count,
                item.expected_count,
                item.readiness_percent,
                str(item.accepted).lower(),
                item.source_address,
                item.content_address,
            )
        )
    check_output = StringIO()
    check_writer = csv.writer(check_output, lineterminator="\n")
    check_writer.writerow(
        (
            "check_id",
            "component_id",
            "category",
            "passed",
            "observed",
            "expected",
            "detail",
            "content_address",
        )
    )
    for item in selected.checks:
        check_writer.writerow(
            (
                item.check_id,
                item.component_id,
                item.category,
                str(item.passed).lower(),
                canonical_json(item.observed),
                canonical_json(item.expected),
                item.detail,
                item.content_address,
            )
        )
    return {
        "attestation.json": release_assurance_attestation_json(selected).encode("utf-8"),
        "components.csv": component_output.getvalue().encode("utf-8"),
        "checks.csv": check_output.getvalue().encode("utf-8"),
        "summary.json": (
            canonical_json(
                {
                    "attestation_id": selected.attestation_id,
                    "content_address": selected.content_address,
                    "overall_percent": selected.overall_percent,
                    "component_count": selected.component_count,
                    "check_count": selected.check_count,
                    "passed_check_count": selected.passed_check_count,
                    "accepted": selected.accepted,
                }
            )
            + "\n"
        ).encode("utf-8"),
        "report.md": release_assurance_attestation_markdown(selected).encode("utf-8"),
        "policy.json": (canonical_json(selected.policy.to_dict()) + "\n").encode("utf-8"),
        "schema.json": (canonical_json(release_assurance_attestation_schema()) + "\n").encode(
            "utf-8"
        ),
    }


def release_assurance_attestation_schema() -> dict[str, Any]:
    """Describe the attestation's public resources and fixed denominators."""

    return {
        "version": RELEASE_ASSURANCE_ATTESTATION_SCHEMA_VERSION,
        "attestation_version": RELEASE_ASSURANCE_ATTESTATION_VERSION,
        "boundary": RELEASE_ASSURANCE_ATTESTATION_BOUNDARY,
        "component_ids": list(RELEASE_ASSURANCE_ATTESTATION_COMPONENT_IDS),
        "denominators": {
            "component_count": RELEASE_ASSURANCE_ATTESTATION_COMPONENT_COUNT,
            "checks_per_component": RELEASE_ASSURANCE_ATTESTATION_CHECKS_PER_COMPONENT,
            "cross_check_count": RELEASE_ASSURANCE_ATTESTATION_CROSS_CHECK_COUNT,
            "check_count": RELEASE_ASSURANCE_ATTESTATION_CHECK_COUNT,
        },
        "resources": {
            "components": {
                "key": "component_id",
                "required": ["component_id", "source_address", "accepted"],
            },
            "checks": {
                "key": "check_id",
                "required": ["check_id", "component_id", "passed", "evidence_addresses"],
            },
        },
        "public_boundary": {
            "aggregate_only": True,
            "timestamp_free": True,
            "source_payloads": False,
            "workflow_execution": False,
            "restricted_metadata": True,
        },
    }


def validate_release_assurance_attestation_schema(
    value: ReleaseAssuranceAttestation, schema: Mapping[str, Any] | None = None
) -> tuple[ReleaseAssuranceAttestationCheck, ...]:
    """Validate an attestation against the current public schema."""

    selected = dict(schema or release_assurance_attestation_schema())
    return (
        _check(
            "schema:version",
            "schema",
            "schema",
            selected.get("version") == RELEASE_ASSURANCE_ATTESTATION_SCHEMA_VERSION,
            selected.get("version"),
            RELEASE_ASSURANCE_ATTESTATION_SCHEMA_VERSION,
            (value.content_address,),
            "schema version is current",
        ),
        _check(
            "schema:components",
            "schema",
            "schema",
            len(value.components) == selected["denominators"]["component_count"],
            len(value.components),
            selected["denominators"]["component_count"],
            (value.content_address,),
            "component denominator matches schema",
        ),
        _check(
            "schema:checks",
            "schema",
            "schema",
            len(value.checks) == selected["denominators"]["check_count"],
            len(value.checks),
            selected["denominators"]["check_count"],
            (value.content_address,),
            "check denominator matches schema",
        ),
        _check(
            "schema:component-fields",
            "schema",
            "schema",
            all(
                all(
                    field in item.to_dict()
                    for field in selected["resources"]["components"]["required"]
                )
                for item in value.components
            ),
            True,
            True,
            (value.content_address,),
            "component rows expose required fields",
        ),
        _check(
            "schema:check-fields",
            "schema",
            "schema",
            all(
                all(
                    field in item.to_dict() for field in selected["resources"]["checks"]["required"]
                )
                for item in value.checks
            ),
            True,
            True,
            (value.content_address,),
            "check rows expose required fields",
        ),
        _check(
            "schema:public-boundary",
            "schema",
            "boundary",
            not forbidden_keys(value.to_dict()),
            (),
            "no restricted public metadata",
            (value.content_address,),
            "attestation remains inside the public boundary",
        ),
    )


def release_assurance_attestation_capabilities() -> dict[str, Any]:
    """Return the supported attestation operations and explicit limits."""

    return {
        "version": "release-assurance-attestation-capabilities-v1",
        "cross_plane_binding": True,
        "runtime_replay": True,
        "program_release_closure": True,
        "mission_catalog_gate": True,
        "explicit_policy": True,
        "exact_byte_packet": True,
        "bounded_query": True,
        "address_only_diff": True,
        "aggregate_observability": True,
        "strict_hydration": True,
        "read_only": True,
        "timestamp_free": True,
        "handler_execution": False,
        "clinical_authorization": False,
        "limits": {
            "component_count": RELEASE_ASSURANCE_ATTESTATION_COMPONENT_COUNT,
            "check_count": RELEASE_ASSURANCE_ATTESTATION_CHECK_COUNT,
        },
        "boundary": {
            "source_payloads": False,
            "workflow_inputs": False,
            "routing_metadata": False,
            "attribution": False,
            "language_metadata": False,
            "model_metadata": False,
            "producer_metadata": False,
            "identity_metadata": False,
        },
    }


__all__ = [
    "RELEASE_ASSURANCE_ATTESTATION_BOUNDARY",
    "RELEASE_ASSURANCE_ATTESTATION_CHECK_COUNT",
    "RELEASE_ASSURANCE_ATTESTATION_CHECKS_PER_COMPONENT",
    "RELEASE_ASSURANCE_ATTESTATION_COMPONENT_COUNT",
    "RELEASE_ASSURANCE_ATTESTATION_COMPONENT_IDS",
    "RELEASE_ASSURANCE_ATTESTATION_CROSS_CHECK_COUNT",
    "RELEASE_ASSURANCE_ATTESTATION_SCHEMA_VERSION",
    "RELEASE_ASSURANCE_ATTESTATION_VERSION",
    "build_default_release_assurance_catalog_gate",
    "build_release_assurance_attestation",
    "release_assurance_attestation_capabilities",
    "release_assurance_attestation_csv",
    "release_assurance_attestation_export_payloads",
    "release_assurance_attestation_json",
    "release_assurance_attestation_markdown",
    "release_assurance_attestation_schema",
    "validate_release_assurance_attestation_schema",
]
