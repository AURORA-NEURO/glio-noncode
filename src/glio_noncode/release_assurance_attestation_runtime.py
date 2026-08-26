"""Deterministic execution record for the final release attestation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .mission_plan_release_catalog import MissionPlanReleaseCatalog
from .mission_plan_release_catalog_gate import MissionPlanReleaseCatalogGate
from .program_release_closure_bundle import build_program_release_snapshot
from .program_release_closure_contracts import ProgramReleaseSnapshot
from .release_assurance_attestation import (
    build_default_release_assurance_catalog_gate,
    build_release_assurance_attestation,
)
from .release_assurance_attestation_contracts import (
    RELEASE_ASSURANCE_ATTESTATION_RUNTIME_STAGE_TOTAL,
    ReleaseAssuranceAttestationPolicy,
    ReleaseAssuranceAttestationReplay,
    ReleaseAssuranceAttestationRuntimeReport,
    ReleaseAssuranceAttestationRuntimeStage,
    ReleaseAssuranceAttestationRuntimeState,
)
from .release_assurance_contracts import ReleaseAssuranceRuntimeReport
from .release_assurance_runtime import run_release_assurance
from .serialization import content_hash, require_non_empty


def _stage(
    ordinal: int,
    stage_id: str,
    input_address: str,
    output_address: str,
    accepted: bool,
    detail: str,
) -> ReleaseAssuranceAttestationRuntimeStage:
    body = {
        "ordinal": ordinal,
        "stage_id": stage_id,
        "state": ReleaseAssuranceAttestationRuntimeState.READY
        if accepted
        else ReleaseAssuranceAttestationRuntimeState.BLOCKED,
        "input_address": input_address,
        "output_address": output_address,
        "detail": detail,
    }
    return ReleaseAssuranceAttestationRuntimeStage(
        **body,
        content_address=content_hash(body, prefix="release-assurance-attestation-runtime-stage"),
    )


def _address(value: Any) -> str:
    return str(getattr(value, "content_address", ""))


def _selected_policy(
    value: ReleaseAssuranceAttestationPolicy | Mapping[str, Any] | None,
) -> ReleaseAssuranceAttestationPolicy | Mapping[str, Any] | None:
    if value is None or isinstance(value, (ReleaseAssuranceAttestationPolicy, Mapping)):
        return value
    raise ValidationError("attestation runtime policy must be an object")


def run_release_assurance_attestation(
    runtime: ReleaseAssuranceRuntimeReport | None = None,
    *,
    program_release: ProgramReleaseSnapshot | None = None,
    catalog: MissionPlanReleaseCatalog | None = None,
    catalog_gate: MissionPlanReleaseCatalogGate | None = None,
    policy: ReleaseAssuranceAttestationPolicy | Mapping[str, Any] | None = None,
    attestation_id: str = "glio-noncode-release-assurance-attestation",
    bundle_id: str = "glio-noncode-release-assurance-attestation",
    run_id: str = "glio-noncode-release-assurance-attestation-run",
) -> ReleaseAssuranceAttestationRuntimeReport:
    """Build, replay, and publish a staged cross-plane attestation."""

    require_non_empty(run_id, "run_id")
    selected_policy = _selected_policy(policy)
    if (catalog is None) != (catalog_gate is None):
        raise ValidationError("catalog and catalog_gate must be supplied together")
    selected_runtime = runtime or run_release_assurance()
    selected_program = program_release or build_program_release_snapshot()
    selected_catalog = catalog
    selected_gate = catalog_gate
    if selected_catalog is None and selected_gate is None:
        selected_catalog, selected_gate = build_default_release_assurance_catalog_gate()
    selected = build_release_assurance_attestation(
        selected_runtime,
        program_release=selected_program,
        catalog=selected_catalog,
        catalog_gate=selected_gate,
        policy=selected_policy,
        attestation_id=attestation_id,
        bundle_id=bundle_id,
        run_id=run_id,
    )
    stages: list[ReleaseAssuranceAttestationRuntimeStage] = []
    stages.append(
        _stage(
            1,
            "source-resolution",
            "",
            selected.content_address,
            True,
            "resolve the three immutable source-plane addresses",
        )
    )
    stages.append(
        _stage(
            2,
            "runtime-acceptance",
            stages[-1].output_address,
            selected.components[0].source_address,
            selected.components[0].accepted,
            "bind the whole-product release-assurance runtime",
        )
    )
    stages.append(
        _stage(
            3,
            "program-closure",
            stages[-1].output_address,
            selected.components[1].source_address,
            selected.components[1].accepted,
            "bind the D01-D16 program-release closure",
        )
    )
    stages.append(
        _stage(
            4,
            "catalog-gate",
            stages[-1].output_address,
            selected.components[2].source_address,
            selected.components[2].accepted,
            "bind the mission-plan release catalog gate",
        )
    )
    stages.append(
        _stage(
            5,
            "cross-plane-checks",
            stages[-1].output_address,
            content_hash(selected.checks, prefix="release-assurance-attestation-checks"),
            all(item.passed for item in selected.checks),
            "reconcile component order, addresses, acceptance, and boundary",
        )
    )
    first = build_release_assurance_attestation(
        selected_runtime,
        program_release=selected_program,
        catalog=selected_catalog,
        catalog_gate=selected_gate,
        policy=selected_policy,
        attestation_id=attestation_id,
        bundle_id=bundle_id,
        run_id=run_id,
    )
    second = build_release_assurance_attestation(
        selected_runtime,
        program_release=selected_program,
        catalog=selected_catalog,
        catalog_gate=selected_gate,
        policy=selected_policy,
        attestation_id=attestation_id,
        bundle_id=bundle_id,
        run_id=run_id,
    )
    deterministic = first.content_address == second.content_address == selected.content_address
    replay = ReleaseAssuranceAttestationReplay(
        first.content_address,
        second.content_address,
        selected.content_address,
        deterministic,
        deterministic,
        content_hash(
            {
                "first_address": first.content_address,
                "second_address": second.content_address,
                "expected_address": selected.content_address,
                "deterministic": deterministic,
            },
            prefix="release-assurance-attestation-replay",
        ),
    )
    stages.append(
        _stage(
            6,
            "deterministic-replay",
            stages[-1].output_address,
            replay.content_address,
            replay.accepted,
            "rebuild the attestation twice from the same typed inputs",
        )
    )
    observability_address = content_hash(
        {
            "component_count": selected.component_count,
            "check_count": selected.check_count,
            "passed_check_count": selected.passed_check_count,
            "overall_percent": selected.overall_percent,
        },
        prefix="release-assurance-attestation-observability",
    )
    stages.append(
        _stage(
            7,
            "aggregate-observability",
            stages[-1].output_address,
            observability_address,
            True,
            "publish aggregate counts without source rows",
        )
    )
    accepted = (
        selected.accepted
        and replay.accepted
        and all(item.state is ReleaseAssuranceAttestationRuntimeState.READY for item in stages)
    )
    final_address = content_hash(
        {
            "attestation": selected.content_address,
            "replay": replay.content_address,
            "stage_count": len(stages) + 1,
        },
        prefix="release-assurance-attestation-finalize",
    )
    stages.append(
        _stage(
            8,
            "public-state",
            stages[-1].output_address,
            final_address,
            accepted,
            "publish the final product attestation state",
        )
    )
    accepted = accepted and len(stages) == RELEASE_ASSURANCE_ATTESTATION_RUNTIME_STAGE_TOTAL
    state = (
        ReleaseAssuranceAttestationRuntimeState.READY
        if accepted
        else ReleaseAssuranceAttestationRuntimeState.BLOCKED
    )
    body = {
        "run_id": run_id,
        "state": state,
        "stages": tuple(stages),
        "attestation": selected,
        "replay": replay,
        "accepted": accepted,
    }
    return ReleaseAssuranceAttestationRuntimeReport(
        run_id=run_id,
        state=state,
        stages=tuple(stages),
        attestation=selected,
        replay=replay,
        accepted=accepted,
        content_address=content_hash(body, prefix="release-assurance-attestation-runtime"),
    )


build_release_assurance_attestation_runtime = run_release_assurance_attestation


def release_assurance_attestation_runtime_json(
    value: ReleaseAssuranceAttestationRuntimeReport,
) -> str:
    """Return the canonical runtime projection."""

    from .serialization import canonical_json

    return canonical_json(value.to_dict()) + "\n"


def release_assurance_attestation_runtime_csv(
    value: ReleaseAssuranceAttestationRuntimeReport,
) -> str:
    """Return one deterministic row per runtime stage."""

    import csv
    from io import StringIO

    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        (
            "ordinal",
            "stage_id",
            "state",
            "input_address",
            "output_address",
            "detail",
            "content_address",
        )
    )
    for item in value.stages:
        writer.writerow(
            (
                item.ordinal,
                item.stage_id,
                item.state.value,
                item.input_address,
                item.output_address,
                item.detail,
                item.content_address,
            )
        )
    return output.getvalue()


def release_assurance_attestation_runtime_markdown(
    value: ReleaseAssuranceAttestationRuntimeReport,
) -> str:
    """Render a stable runtime stage report."""

    lines = [
        "# Release assurance attestation runtime",
        "",
        f"- Run: `{value.run_id}`",
        f"- State: `{value.state.value}`",
        f"- Accepted: `{str(value.accepted).lower()}`",
        f"- Stages: `{len(value.stages)}/{RELEASE_ASSURANCE_ATTESTATION_RUNTIME_STAGE_TOTAL}`",
        f"- Attestation: `{value.attestation.content_address}`",
        "",
        "| Ordinal | Stage | State | Input | Output |",
        "| ---: | --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| {item.ordinal} | {item.stage_id} | {item.state.value} | "
        f"`{item.input_address}` | `{item.output_address}` |"
        for item in value.stages
    )
    lines.extend(
        ("", "Replay deterministic: `" + str(value.replay.deterministic).lower() + "`", "")
    )
    return "\n".join(lines)


def release_assurance_attestation_runtime_capabilities() -> dict[str, Any]:
    """Describe runtime guarantees and explicit non-capabilities."""

    return {
        "version": "release-assurance-attestation-runtime-capabilities-v1",
        "stage_count": RELEASE_ASSURANCE_ATTESTATION_RUNTIME_STAGE_TOTAL,
        "deterministic_replay": True,
        "address_chaining": True,
        "timestamp_free": True,
        "handler_execution": False,
        "source_payloads": False,
        "clinical_authorization": False,
        "public_boundary": True,
    }


__all__ = [
    "build_release_assurance_attestation_runtime",
    "release_assurance_attestation_runtime_capabilities",
    "release_assurance_attestation_runtime_csv",
    "release_assurance_attestation_runtime_json",
    "release_assurance_attestation_runtime_markdown",
    "run_release_assurance_attestation",
]
