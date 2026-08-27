"""Run the complete build-to-release packet handoff as one typed artifact."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_workbench_contracts import ModuleWorkbenchReport
from .module_workbench_execution_contracts import ModuleWorkbenchExecutionCommand
from .module_workbench_execution_packet import (
    build_module_workbench_execution_packet,
    verify_module_workbench_execution_packet,
    verify_module_workbench_execution_packet_value,
    write_module_workbench_execution_packet,
)
from .module_workbench_execution_packet_contracts import ModuleWorkbenchExecutionPacket
from .module_workbench_execution_packet_query import (
    query_module_workbench_execution_packet,
    replay_module_workbench_execution_packet,
)
from .module_workbench_execution_packet_release import (
    build_module_workbench_execution_packet_release,
)
from .module_workbench_execution_packet_release_contracts import (
    ModuleWorkbenchExecutionPacketRelease,
)
from .module_workbench_execution_packet_runtime_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_RUNTIME_BOUNDARY,
    MODULE_WORKBENCH_EXECUTION_PACKET_RUNTIME_DEFAULT_LIMIT,
    MODULE_WORKBENCH_EXECUTION_PACKET_RUNTIME_MAX_LIMIT,
    MODULE_WORKBENCH_EXECUTION_PACKET_RUNTIME_VERSION,
    ModuleWorkbenchExecutionPacketRuntime,
    ModuleWorkbenchExecutionPacketRuntimeStage,
    ModuleWorkbenchExecutionPacketRuntimeStageKind,
    ModuleWorkbenchExecutionPacketRuntimeStageState,
    address_module_workbench_execution_packet_runtime,
    address_module_workbench_execution_packet_runtime_stage,
)
from .serialization import canonical_json, content_hash


def _stage(
    kind: ModuleWorkbenchExecutionPacketRuntimeStageKind,
    accepted: bool,
    artifact_address: str,
    detail: str,
) -> ModuleWorkbenchExecutionPacketRuntimeStage:
    state = (
        ModuleWorkbenchExecutionPacketRuntimeStageState.COMPLETED
        if accepted
        else ModuleWorkbenchExecutionPacketRuntimeStageState.BLOCKED
    )
    body = {
        "kind": kind,
        "state": state,
        "accepted": accepted,
        "artifact_address": artifact_address,
        "detail": detail,
    }
    provisional = ModuleWorkbenchExecutionPacketRuntimeStage(**body, content_address="pending")
    return ModuleWorkbenchExecutionPacketRuntimeStage(
        **body,
        content_address=address_module_workbench_execution_packet_runtime_stage(provisional),
    )


def _runtime(
    packet: ModuleWorkbenchExecutionPacket,
    verification_address: str,
    replay_address: str,
    release: ModuleWorkbenchExecutionPacketRelease,
    stages: tuple[ModuleWorkbenchExecutionPacketRuntimeStage, ...],
) -> ModuleWorkbenchExecutionPacketRuntime:
    body = {
        "packet_id": packet.packet_id,
        "packet_address": packet.content_address,
        "verification_address": verification_address,
        "replay_address": replay_address,
        "release_address": release.content_address,
        "stages": stages,
        "stage_count": len(stages),
        "completed_count": sum(item.accepted for item in stages),
        "blocked_count": sum(not item.accepted for item in stages),
        "accepted": all(item.accepted for item in stages),
    }
    provisional = ModuleWorkbenchExecutionPacketRuntime(**body, content_address="pending")
    return ModuleWorkbenchExecutionPacketRuntime(
        **body,
        content_address=address_module_workbench_execution_packet_runtime(provisional),
    )


def run_module_workbench_execution_packet_runtime(
    report: ModuleWorkbenchReport,
    portfolio: Any | None = None,
    commands: Iterable[ModuleWorkbenchExecutionCommand] = (),
    policy: Any | None = None,
    *,
    destination: str | Path | None = None,
    allow_existing: bool = False,
) -> ModuleWorkbenchExecutionPacketRuntime:
    """Build, optionally persist, verify, query, replay, and release a packet."""

    if not isinstance(report, ModuleWorkbenchReport):
        raise ValidationError("packet runtime requires a typed workbench report")
    packet = build_module_workbench_execution_packet(
        report,
        portfolio=portfolio,
        commands=tuple(commands),
        policy=policy,
    )
    stages: list[ModuleWorkbenchExecutionPacketRuntimeStage] = [
        _stage(
            ModuleWorkbenchExecutionPacketRuntimeStageKind.BUILD,
            packet.accepted,
            packet.content_address,
            f"built {packet.artifact_count} exact-byte artifacts",
        )
    ]
    if destination is None:
        stages.append(
            _stage(
                ModuleWorkbenchExecutionPacketRuntimeStageKind.WRITE,
                True,
                packet.content_address,
                "retained packet in memory; no filesystem destination requested",
            )
        )
        verification = verify_module_workbench_execution_packet_value(packet)
        verification_address = verification.content_address
        verified = verification.accepted
    else:
        write_module_workbench_execution_packet(packet, destination, allow_existing=allow_existing)
        stages.append(
            _stage(
                ModuleWorkbenchExecutionPacketRuntimeStageKind.WRITE,
                True,
                packet.content_address,
                "wrote manifest and artifacts with atomic replacement",
            )
        )
        verification = verify_module_workbench_execution_packet(destination)
        verification_address = verification.content_address
        verified = verification.accepted
    stages.append(
        _stage(
            ModuleWorkbenchExecutionPacketRuntimeStageKind.VERIFY,
            verified,
            verification_address,
            "verified manifest shape, paths, bytes, canonical JSON, and public fields",
        )
    )
    stages.append(
        _stage(
            ModuleWorkbenchExecutionPacketRuntimeStageKind.LOAD,
            verified,
            packet.content_address,
            "packet is loadable as an immutable typed manifest",
        )
    )
    query = query_module_workbench_execution_packet(packet, resource="summary")
    stages.append(
        _stage(
            ModuleWorkbenchExecutionPacketRuntimeStageKind.QUERY,
            bool(query.get("accepted")),
            str(query["content_address"]),
            "queried the bounded packet summary resource",
        )
    )
    replay = replay_module_workbench_execution_packet(packet)
    stages.append(
        _stage(
            ModuleWorkbenchExecutionPacketRuntimeStageKind.REPLAY,
            bool(replay.get("accepted")),
            str(replay["content_address"]),
            f"replayed {replay.get('artifact_count', 0)} packet artifacts",
        )
    )
    release = build_module_workbench_execution_packet_release(packet)
    stages.append(
        _stage(
            ModuleWorkbenchExecutionPacketRuntimeStageKind.RELEASE,
            release.accepted,
            release.content_address,
            f"evaluated {release.check_count} release checks",
        )
    )
    return _runtime(
        packet, verification_address, str(replay["content_address"]), release, tuple(stages)
    )


def verify_module_workbench_execution_packet_runtime(
    value: ModuleWorkbenchExecutionPacketRuntime,
) -> ModuleWorkbenchExecutionPacketRuntime:
    """Verify stage addresses, order, counts, and aggregate runtime address."""

    if not isinstance(value, ModuleWorkbenchExecutionPacketRuntime):
        raise ValidationError("packet runtime verification requires a typed runtime")
    for stage in value.stages:
        if address_module_workbench_execution_packet_runtime_stage(stage) != stage.content_address:
            raise ValidationError(f"packet runtime stage address mismatch: {stage.kind.value}")
    if address_module_workbench_execution_packet_runtime(value) != value.content_address:
        raise ValidationError("packet runtime address mismatch")
    return value


def query_module_workbench_execution_packet_runtime(
    value: ModuleWorkbenchExecutionPacketRuntime,
    *,
    resource: str = "stages",
    state: str | None = None,
    accepted: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_RUNTIME_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return bounded packet runtime stages or one summary row."""

    verify_module_workbench_execution_packet_runtime(value)
    if offset < 0 or limit < 1 or limit > MODULE_WORKBENCH_EXECUTION_PACKET_RUNTIME_MAX_LIMIT:
        raise ValidationError("packet runtime paging is invalid")
    normalized = resource.casefold().strip()
    if normalized == "stages":
        rows = [item.to_dict() for item in value.stages]
        index_used = "kind"
    elif normalized == "summary":
        rows = [value.to_dict(include_stages=False)]
        index_used = "packet_id"
    else:
        raise ValidationError("packet runtime resource must be stages or summary")
    if state:
        rows = [row for row in rows if row.get("state") == state]
    if accepted is not None:
        rows = [row for row in rows if row.get("accepted") is accepted]
    if text:
        rows = [row for row in rows if text.casefold() in canonical_json(row).casefold()]
    body = {
        "packet_id": value.packet_id,
        "runtime_address": value.content_address,
        "resource": normalized,
        "query": {"state": state, "accepted": accepted, "text": text},
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "index_used": index_used,
        "items": rows[offset : offset + limit],
        "accepted": value.accepted,
    }
    return body | {
        "content_address": content_hash(
            body, prefix="module-workbench-execution-packet-runtime-query"
        )
    }


def module_workbench_execution_packet_runtime_json(
    value: ModuleWorkbenchExecutionPacketRuntime,
) -> str:
    """Return canonical packet runtime JSON."""

    verify_module_workbench_execution_packet_runtime(value)
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_runtime_csv(
    value: ModuleWorkbenchExecutionPacketRuntime,
) -> str:
    """Return one stable CSV row per runtime stage."""

    verify_module_workbench_execution_packet_runtime(value)
    fields = ("kind", "state", "accepted", "artifact_address", "detail", "content_address")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for stage in value.stages:
        writer.writerow(stage.to_dict())
    return output.getvalue()


def module_workbench_execution_packet_runtime_schema() -> dict[str, Any]:
    """Describe ordered packet runtime stages and query resources."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_RUNTIME_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_RUNTIME_BOUNDARY,
        "stage_order": [item.value for item in ModuleWorkbenchExecutionPacketRuntimeStageKind],
        "stage_states": [item.value for item in ModuleWorkbenchExecutionPacketRuntimeStageState],
        "resources": ["stages", "summary"],
        "inputs": ["typed_workbench_report", "optional_packet_directory"],
        "path_free": True,
        "timestamp_free": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_runtime_capabilities() -> dict[str, Any]:
    """Declare runtime operations for local and offline clients."""

    operations = (
        "build_packet",
        "write_packet",
        "verify_packet",
        "load_packet",
        "query_packet",
        "replay_packet",
        "evaluate_release",
        "retain_stage_addresses",
        "query_stages",
        "query_summary",
        "export_json",
        "export_csv",
        "verify_runtime_address",
    )
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_RUNTIME_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "ordered": True,
        "deterministic": True,
        "offline": True,
        "atomic_writes": True,
        "identity_free": True,
    }


__all__ = [
    "module_workbench_execution_packet_runtime_capabilities",
    "module_workbench_execution_packet_runtime_csv",
    "module_workbench_execution_packet_runtime_json",
    "module_workbench_execution_packet_runtime_schema",
    "query_module_workbench_execution_packet_runtime",
    "run_module_workbench_execution_packet_runtime",
    "verify_module_workbench_execution_packet_runtime",
]
