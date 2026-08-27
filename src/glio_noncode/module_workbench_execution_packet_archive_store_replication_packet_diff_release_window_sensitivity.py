"""Compare explicit release-window policies without granting approval.

Policy sensitivity is an analysis plane over one verified packet-diff matrix.
It is useful when a release review needs to see how strict, review, and
exception policies behave on exactly the same evidence. Each scenario builds a
normal release-window decision, retains its policy and window addresses, and
reports state counts. The sensitivity aggregate is analysis-only: it never
mutates a packet store and its preferred scenario is not an approval receipt.
"""

from __future__ import annotations

# ruff: noqa: E501
import csv
import io
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive_store_replication_packet_diff_batch import (
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffBatch,
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_batch_from_directories,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_batch,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_contracts import (
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindow,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowPolicy,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowState,
)
from .serialization import canonical_json, content_hash

MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_SENSITIVITY_VERSION = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-sensitivity-v1"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_SENSITIVITY_BOUNDARY = "public_aggregate_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_SENSITIVITY_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-sensitivity"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_SENSITIVITY_SCENARIO_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-sensitivity-scenario"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_SENSITIVITY_QUERY_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-sensitivity-query"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_SENSITIVITY_MAX_SCENARIOS = 64
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_SENSITIVITY_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_SENSITIVITY_MAX_LIMIT = 512


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value


def _address(value: Any, field: str) -> str:
    value = _text(value, field, 256)
    if ":" not in value or value.startswith(":") or value.endswith(":"):
        raise ValidationError(f"{field} must be a content address")
    return value


def _count(value: Any, field: str, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValidationError(f"{field} must be a non-negative integer")
    if maximum is not None and value > maximum:
        raise ValidationError(f"{field} exceeds the published limit")
    return value


def _ratio(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
        raise ValidationError(f"{field} must be a ratio between zero and one")
    return float(value)


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _public_boundary(value: Any) -> bool:
    forbidden = {
        "agent",
        "agent_id",
        "agent_name",
        "assistant",
        "assistant_id",
        "author",
        "author_id",
        "codex",
        "email",
        "hostname",
        "model",
        "openai",
        "private",
        "token",
        "user",
        "user_id",
        "username",
    }
    if isinstance(value, Mapping):
        return all(
            str(key).casefold() not in forbidden and _public_boundary(item)
            for key, item in value.items()
        )
    if isinstance(value, (tuple, list)):
        return all(_public_boundary(item) for item in value)
    return True


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowSensitivityScenario:
    """One policy outcome in an analysis-only sensitivity matrix."""

    def __init__(
        self,
        ordinal: int,
        scenario_id: str,
        policy_address: str,
        window_address: str,
        state: str,
        release_ready: bool,
        accepted: bool,
        score: float,
        item_count: int,
        passed_count: int,
        warning_count: int,
        blocker_count: int,
        detail: str,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.scenario_id = scenario_id
        self.policy_address = policy_address
        self.window_address = window_address
        self.state = state
        self.release_ready = release_ready
        self.accepted = accepted
        self.score = score
        self.item_count = item_count
        self.passed_count = passed_count
        self.warning_count = warning_count
        self.blocker_count = blocker_count
        self.detail = detail
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(
            self.ordinal,
            "sensitivity scenario ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_SENSITIVITY_MAX_SCENARIOS,
        )
        _text(self.scenario_id, "sensitivity scenario ID", 256)
        _address(self.policy_address, "sensitivity policy address")
        _address(self.window_address, "sensitivity window address")
        if self.state not in {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowState
        }:
            raise ValidationError("sensitivity scenario state is invalid")
        _bool(self.release_ready, "sensitivity scenario release-ready flag")
        _bool(self.accepted, "sensitivity scenario accepted flag")
        _ratio(self.score, "sensitivity scenario score")
        _count(self.item_count, "sensitivity scenario item count", 256)
        _count(self.passed_count, "sensitivity scenario passed count", 64)
        _count(self.warning_count, "sensitivity scenario warning count", 64)
        _count(self.blocker_count, "sensitivity scenario blocker count", 64)
        if (
            self.passed_count > 64
            or self.passed_count + self.warning_count + self.blocker_count < self.passed_count
        ):
            raise ValidationError("sensitivity scenario check counts are invalid")
        _text(self.detail, "sensitivity scenario detail", 2048)
        _address(self.content_address, "sensitivity scenario address")
        if not _public_boundary(self.to_dict()):
            raise ValidationError("sensitivity scenario crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "scenario_id": self.scenario_id,
            "policy_address": self.policy_address,
            "window_address": self.window_address,
            "state": self.state,
            "release_ready": self.release_ready,
            "accepted": self.accepted,
            "score": self.score,
            "item_count": self.item_count,
            "passed_count": self.passed_count,
            "warning_count": self.warning_count,
            "blocker_count": self.blocker_count,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_scenario(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowSensitivityScenario,
) -> str:
    """Address one sensitivity scenario without its address field."""

    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_SENSITIVITY_SCENARIO_PREFIX,
    )


def _scenario(
    ordinal: int,
    scenario_id: str,
    policy: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowPolicy,
    window: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindow,
) -> (
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowSensitivityScenario
):
    body = {
        "ordinal": ordinal,
        "scenario_id": scenario_id,
        "policy_address": policy.content_address,
        "window_address": window.content_address,
        "state": window.state,
        "release_ready": window.release_ready,
        "accepted": window.accepted,
        "score": window.score,
        "item_count": window.item_count,
        "passed_count": window.passed_count,
        "warning_count": window.warning_count,
        "blocker_count": window.blocker_count,
        "detail": "policy scenario evaluated for comparison; not an approval",
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowSensitivityScenario(
        **body,
        content_address=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_SENSITIVITY_SCENARIO_PREFIX
        + ":pending-scenario",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowSensitivityScenario(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_scenario(
            provisional
        ),
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowSensitivity:
    """Analysis-only comparison of several policies over one matrix."""

    def __init__(
        self,
        sensitivity_id: str,
        version: str,
        boundary: str,
        batch_address: str,
        scenarios: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowSensitivityScenario,
            ...,
        ],
        scenario_count: int,
        accepted_count: int,
        promotable_count: int,
        hold_count: int,
        blocked_count: int,
        best_promotable_scenario_id: str | None,
        best_promotable_window_address: str | None,
        analysis_only: bool,
        accepted: bool,
        detail: str,
        content_address: str,
    ) -> None:
        self.sensitivity_id = sensitivity_id
        self.version = version
        self.boundary = boundary
        self.batch_address = batch_address
        self.scenarios = scenarios
        self.scenario_count = scenario_count
        self.accepted_count = accepted_count
        self.promotable_count = promotable_count
        self.hold_count = hold_count
        self.blocked_count = blocked_count
        self.best_promotable_scenario_id = best_promotable_scenario_id
        self.best_promotable_window_address = best_promotable_window_address
        self.analysis_only = analysis_only
        self.accepted = accepted
        self.detail = detail
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.sensitivity_id, "sensitivity ID", 256)
        if (
            self.version
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_SENSITIVITY_VERSION
        ):
            raise ValidationError("sensitivity version is invalid")
        if (
            self.boundary
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_SENSITIVITY_BOUNDARY
        ):
            raise ValidationError("sensitivity boundary is invalid")
        _address(self.batch_address, "sensitivity batch address")
        if self.scenario_count != len(self.scenarios) or not self.scenarios:
            raise ValidationError("sensitivity scenario count does not conserve")
        _count(
            self.scenario_count,
            "sensitivity scenario count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_SENSITIVITY_MAX_SCENARIOS,
        )
        if tuple(item.ordinal for item in self.scenarios) != tuple(range(self.scenario_count)):
            raise ValidationError("sensitivity scenario ordinals are not ordered")
        if len({item.scenario_id for item in self.scenarios}) != self.scenario_count:
            raise ValidationError("sensitivity scenario IDs must be unique")
        if any(
            address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_scenario(
                item
            )
            != item.content_address
            for item in self.scenarios
        ):
            raise ValidationError("sensitivity scenario address mismatch")
        counts = {
            "accepted_count": sum(item.accepted for item in self.scenarios),
            "promotable_count": sum(item.state == "promotable" for item in self.scenarios),
            "hold_count": sum(item.state == "hold" for item in self.scenarios),
            "blocked_count": sum(item.state == "blocked" for item in self.scenarios),
        }
        for field, expected in counts.items():
            if getattr(self, field) != expected:
                raise ValidationError(f"sensitivity {field} does not conserve")
            _count(getattr(self, field), f"sensitivity {field}", self.scenario_count)
        _bool(self.analysis_only, "sensitivity analysis-only flag")
        if not self.analysis_only:
            raise ValidationError("sensitivity reports must be analysis-only")
        _bool(self.accepted, "sensitivity accepted flag")
        if self.accepted != (self.accepted_count == self.scenario_count):
            raise ValidationError("sensitivity accepted state does not conserve")
        if self.best_promotable_scenario_id is None:
            if self.best_promotable_window_address is not None or self.promotable_count:
                raise ValidationError("sensitivity best promotable scenario does not conserve")
        else:
            _text(self.best_promotable_scenario_id, "best promotable scenario ID", 256)
            _address(self.best_promotable_window_address, "best promotable window address")
            matching = [
                item
                for item in self.scenarios
                if item.scenario_id == self.best_promotable_scenario_id
            ]
            if (
                len(matching) != 1
                or matching[0].state != "promotable"
                or matching[0].window_address != self.best_promotable_window_address
            ):
                raise ValidationError("sensitivity best promotable scenario is invalid")
        _text(self.detail, "sensitivity detail", 4096)
        _address(self.content_address, "sensitivity address")
        if not _public_boundary(self.to_dict()):
            raise ValidationError("sensitivity crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "sensitivity_id": self.sensitivity_id,
            "version": self.version,
            "boundary": self.boundary,
            "batch_address": self.batch_address,
            "scenario_count": self.scenario_count,
            "accepted_count": self.accepted_count,
            "promotable_count": self.promotable_count,
            "hold_count": self.hold_count,
            "blocked_count": self.blocked_count,
            "best_promotable_scenario_id": self.best_promotable_scenario_id,
            "best_promotable_window_address": self.best_promotable_window_address,
            "analysis_only": self.analysis_only,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }

    def to_dict(self, *, include_scenarios: bool = True) -> dict[str, Any]:
        body = self.summary() | {"detail": self.detail}
        if include_scenarios:
            body["scenarios"] = [item.to_dict() for item in self.scenarios]
        return body


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowSensitivity,
) -> str:
    """Address the complete sensitivity analysis."""

    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_SENSITIVITY_PREFIX,
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity(
    batch: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffBatch,
    scenarios: Sequence[
        tuple[
            str, ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowPolicy
        ]
    ],
    *,
    sensitivity_id: str = (
        "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff-release-window-sensitivity"
    ),
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowSensitivity:
    """Evaluate several policies against one verified packet matrix."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_batch(batch)
    _count(
        len(scenarios),
        "sensitivity scenario input count",
        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_SENSITIVITY_MAX_SCENARIOS,
    )
    if not scenarios:
        raise ValidationError("sensitivity analysis requires at least one scenario")
    sensitivity_id = _text(sensitivity_id, "sensitivity ID", 256)
    seen: set[str] = set()
    values: list[
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowSensitivityScenario
    ] = []
    for ordinal, entry in enumerate(scenarios):
        if not isinstance(entry, tuple) or len(entry) != 2:
            raise ValidationError("sensitivity scenario must contain ID and policy")
        scenario_id, policy = entry
        scenario_id = _text(scenario_id, "sensitivity scenario ID", 256)
        if scenario_id in seen:
            raise ValidationError("sensitivity scenario IDs must be unique")
        seen.add(scenario_id)
        if not isinstance(
            policy,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowPolicy,
        ):
            raise ValidationError("sensitivity scenario policy must be typed")
        policy._validate()
        window = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window(
            batch, policy, window_id=f"{sensitivity_id}:{scenario_id}"
        )
        values.append(_scenario(ordinal, scenario_id, policy, window))
    scenario_tuple = tuple(values)
    promotable = [item for item in scenario_tuple if item.state == "promotable"]
    best = (
        sorted(promotable, key=lambda item: (-item.score, -item.passed_count, item.ordinal))[0]
        if promotable
        else None
    )
    body = {
        "sensitivity_id": sensitivity_id,
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_SENSITIVITY_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_SENSITIVITY_BOUNDARY,
        "batch_address": batch.content_address,
        "scenarios": scenario_tuple,
        "scenario_count": len(scenario_tuple),
        "accepted_count": sum(item.accepted for item in scenario_tuple),
        "promotable_count": sum(item.state == "promotable" for item in scenario_tuple),
        "hold_count": sum(item.state == "hold" for item in scenario_tuple),
        "blocked_count": sum(item.state == "blocked" for item in scenario_tuple),
        "best_promotable_scenario_id": best.scenario_id if best else None,
        "best_promotable_window_address": best.window_address if best else None,
        "analysis_only": True,
        "accepted": all(item.accepted for item in scenario_tuple),
        "detail": "policy sensitivity analysis completed; no scenario is an approval",
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowSensitivity(
        **body,
        content_address=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_SENSITIVITY_PREFIX
        + ":pending-sensitivity",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowSensitivity(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity(
            provisional
        ),
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_from_directories(
    pairs: Sequence[tuple[str, str | Path, str | Path]],
    scenarios: Sequence[
        tuple[
            str, ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowPolicy
        ]
    ],
    *,
    batch_id: str = (
        "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff-batch"
    ),
    sensitivity_id: str = (
        "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff-release-window-sensitivity"
    ),
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowSensitivity:
    """Build sensitivity analysis from persisted packet directories."""

    batch = build_module_workbench_execution_packet_archive_store_replication_packet_diff_batch_from_directories(
        pairs, batch_id=batch_id
    )
    return build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity(
        batch, scenarios, sensitivity_id=sensitivity_id
    )


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowSensitivity,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowSensitivity:
    """Verify scenario addresses and the aggregate analysis address."""

    if not isinstance(
        value,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowSensitivity,
    ):
        raise ValidationError("sensitivity verification requires a typed analysis")
    for item in value.scenarios:
        if (
            address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_scenario(
                item
            )
            != item.content_address
        ):
            raise ValidationError("sensitivity scenario address mismatch")
    if (
        address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity(
            value
        )
        != value.content_address
    ):
        raise ValidationError("sensitivity address mismatch")
    return value


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowSensitivity,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity(
        value
    )
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowSensitivity,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity(
        value
    )
    output = io.StringIO(newline="")
    fields = (
        "ordinal",
        "scenario_id",
        "policy_address",
        "window_address",
        "state",
        "release_ready",
        "accepted",
        "score",
        "item_count",
        "passed_count",
        "warning_count",
        "blocker_count",
        "detail",
        "content_address",
    )
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for item in value.scenarios:
        writer.writerow(item.to_dict())
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_markdown(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowSensitivity,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity(
        value
    )
    lines = [
        "# Archive Store Replication Packet Diff Release Window Sensitivity",
        "",
        f"- analysis-only: `{str(value.analysis_only).lower()}`",
        f"- scenarios: `{value.scenario_count}`; promotable: `{value.promotable_count}`; hold: `{value.hold_count}`; blocked: `{value.blocked_count}`",
        f"- best promotable scenario: `{value.best_promotable_scenario_id}`",
        f"- address: `{value.content_address}`",
        "",
        "| # | Scenario | State | Ready | Score | Passed | Warnings | Blockers |",
        "|---:|---|---|---|---:|---:|---:|---:|",
    ]
    for item in value.scenarios:
        lines.append(
            f"| {item.ordinal} | {item.scenario_id} | {item.state} | {str(item.release_ready).lower()} | "
            f"{item.score:.6f} | {item.passed_count} | {item.warning_count} | {item.blocker_count} |"
        )
    return "\n".join(lines) + "\n"


def query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowSensitivity,
    *,
    resource: str = "summary",
    state: str | None = None,
    release_ready: bool | None = None,
    accepted: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_SENSITIVITY_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return a bounded sensitivity summary or scenario page."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity(
        value
    )
    if (
        isinstance(offset, bool)
        or isinstance(limit, bool)
        or offset < 0
        or limit < 1
        or limit
        > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_SENSITIVITY_MAX_LIMIT
    ):
        raise ValidationError("sensitivity query paging is invalid")
    normalized = _text(resource, "sensitivity query resource", 64).casefold()
    if normalized == "summary":
        rows = [value.summary()]
        index_used = "sensitivity_id"
    elif normalized == "scenarios":
        rows = [item.to_dict() for item in value.scenarios]
        if state is not None:
            state = _text(state, "sensitivity query state", 64)
            rows = [row for row in rows if row["state"] == state]
        if release_ready is not None:
            _bool(release_ready, "sensitivity query release-ready filter")
            rows = [row for row in rows if row["release_ready"] is release_ready]
        if accepted is not None:
            _bool(accepted, "sensitivity query accepted filter")
            rows = [row for row in rows if row["accepted"] is accepted]
        index_used = "scenario_id"
    else:
        raise ValidationError("unsupported sensitivity query resource")
    if text is not None:
        text = _text(text, "sensitivity query text", 512)
        needle = text.casefold()
        rows = [row for row in rows if needle in canonical_json(row).casefold()]
    body = {
        "resource": normalized,
        "query": {
            "state": state,
            "release_ready": release_ready,
            "accepted": accepted,
            "text": text,
        },
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "index_used": index_used,
        "reference_address": value.content_address,
        "items": rows[offset : offset + limit],
        "accepted": value.accepted,
        "analysis_only": True,
    }
    return body | {
        "content_address": content_hash(
            body,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_SENSITIVITY_QUERY_PREFIX,
        )
    }


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_query(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify a sensitivity query address and analysis-only marker."""

    if not isinstance(value, Mapping) or not isinstance(value.get("content_address"), str):
        raise ValidationError("sensitivity query response must be addressed")
    if value.get("analysis_only") is not True:
        raise ValidationError("sensitivity query must remain analysis-only")
    body = {key: item for key, item in value.items() if key != "content_address"}
    expected = content_hash(
        body,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_SENSITIVITY_QUERY_PREFIX,
    )
    if value["content_address"] != expected:
        raise ValidationError("sensitivity query address mismatch")
    return dict(value)


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_query_json(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_query(
        value
    )
    return canonical_json(value) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_query_csv(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_query(
        value
    )
    output = io.StringIO(newline="")
    fields = (
        "resource",
        "total",
        "offset",
        "limit",
        "index_used",
        "accepted",
        "analysis_only",
        "reference_address",
        "content_address",
        "ordinal",
        "scenario_id",
        "policy_address",
        "window_address",
        "state",
        "release_ready",
        "score",
        "passed_count",
        "warning_count",
        "blocker_count",
        "detail",
    )
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    envelope = {key: value.get(key) for key in fields if key in value}
    for row in value.get("items", []):
        if isinstance(row, Mapping):
            writer.writerow(envelope | dict(row))
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_query_markdown(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_query(
        value
    )
    lines = [
        "# Archive Store Replication Packet Diff Release Window Sensitivity Query",
        "",
        f"- resource: `{value.get('resource')}`",
        f"- page: `{value.get('offset')}` to `{value.get('limit')}` of `{value.get('total')}`",
        f"- analysis-only: `{str(value.get('analysis_only')).lower()}`",
        f"- address: `{value.get('content_address')}`",
        "",
        "| # | Scenario | State | Ready | Score | Detail |",
        "|---:|---|---|---|---:|---|",
    ]
    for row in value.get("items", []):
        lines.append(
            f"| {row.get('ordinal')} | {row.get('scenario_id')} | {row.get('state')} | "
            f"{str(row.get('release_ready')).lower()} | {row.get('score')} | {row.get('detail')} |"
        )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_schema() -> (
    dict[str, Any]
):
    """Describe the analysis-only sensitivity contract."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_SENSITIVITY_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_SENSITIVITY_BOUNDARY,
        "states": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowState
        ],
        "conservation": [
            "scenario_count",
            "state_counts",
            "accepted_count",
            "best_promotable_reference",
        ],
        "analysis_only": True,
        "approval_granting": False,
        "path_free": True,
        "timestamp_free": True,
        "identity_free": True,
        "fail_closed": True,
        "limits": {
            "max_scenarios": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_SENSITIVITY_MAX_SCENARIOS,
            "max_query_limit": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_SENSITIVITY_MAX_LIMIT,
        },
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_capabilities() -> (
    dict[str, Any]
):
    """Declare analysis-only sensitivity operations."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_SENSITIVITY_VERSION,
        "operations": [
            "build",
            "build_from_directories",
            "verify",
            "json",
            "csv",
            "markdown",
            "query",
        ],
        "analysis_only": True,
        "approval_granting": False,
        "bounded": True,
        "path_free": True,
        "timestamp_free": True,
        "identity_free": True,
        "fail_closed": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_query_schema() -> (
    dict[str, Any]
):
    """Describe sensitivity scenario filters."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_SENSITIVITY_VERSION,
        "query_version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_SENSITIVITY_QUERY_PREFIX
        + "-v1",
        "resources": {"summary": ["summary"], "scenarios": ["scenarios"]},
        "filters": ["state", "release_ready", "accepted", "text"],
        "analysis_only": True,
        "paging": {
            "offset_minimum": 0,
            "limit_minimum": 1,
            "limit_maximum": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_SENSITIVITY_MAX_LIMIT,
        },
        "path_free": True,
        "timestamp_free": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_query_capabilities() -> (
    dict[str, Any]
):
    """Declare sensitivity query and export operations."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_SENSITIVITY_VERSION,
        "query_version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_SENSITIVITY_QUERY_PREFIX
        + "-v1",
        "operations": [
            "summary",
            "scenarios",
            "filter",
            "page",
            "json",
            "csv",
            "markdown",
            "verify",
        ],
        "analysis_only": True,
        "approval_granting": False,
        "bounded": True,
        "path_free": True,
        "timestamp_free": True,
        "identity_free": True,
        "fail_closed": True,
    }


__all__ = [
    name
    for name in globals()
    if name.startswith(
        "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_SENSITIVITY"
    )
    or name.startswith(
        "ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowSensitivity"
    )
    or name.startswith(
        "address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity"
    )
    or name.startswith(
        "build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity"
    )
    or name.startswith(
        "verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity"
    )
    or name.startswith(
        "module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity"
    )
    or name.startswith(
        "query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity"
    )
    or name.startswith(
        "render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity"
    )
]
