"""Bounded threshold probes for workspace query and render limits."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Any

from .serialization import content_hash, jsonable
from .workspace_frontier_public_data import WorkspaceFrontierOperation


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierThresholdProfile:
    profile_id: str
    operation: WorkspaceFrontierOperation
    page_limits: tuple[int, ...]
    offsets: tuple[int, ...]
    interval_spans: tuple[int, ...]
    text_modes: tuple[str, ...]
    query_modes: tuple[str, ...]
    expected_review: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierThresholdProbe:
    probe_id: str
    profile_id: str
    page_limit: int
    offset: int
    interval_span: int
    text_mode: str
    query_mode: str
    accepted: bool
    review_required: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierThresholdReport:
    profiles: tuple[WorkspaceFrontierThresholdProfile, ...]
    probes: tuple[WorkspaceFrontierThresholdProbe, ...]
    accepted_probe_ids: tuple[str, ...]
    review_probe_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _profile(operation: WorkspaceFrontierOperation) -> WorkspaceFrontierThresholdProfile:
    body = {"profile_id": f"workspace-threshold:{operation.value}", "operation": operation, "page_limits": (1, 10, 50), "offsets": (0, 1, 25), "interval_spans": (1, 25, 100), "text_modes": ("empty", "exact", "partial"), "query_modes": ("text", "interval", "faceted"), "expected_review": operation is not WorkspaceFrontierOperation.VARIANT_EXPLORER}
    return WorkspaceFrontierThresholdProfile(**body, content_address=content_hash(body))


def default_workspace_frontier_threshold_profiles() -> tuple[WorkspaceFrontierThresholdProfile, ...]:
    return tuple(_profile(operation) for operation in WorkspaceFrontierOperation)


def build_workspace_frontier_threshold_report(profiles: tuple[WorkspaceFrontierThresholdProfile, ...] | None = None) -> WorkspaceFrontierThresholdReport:
    profiles = profiles or default_workspace_frontier_threshold_profiles()
    probes: list[WorkspaceFrontierThresholdProbe] = []
    for profile in profiles:
        combinations = product(profile.page_limits, profile.offsets, profile.interval_spans, profile.text_modes, profile.query_modes)
        for index, (page_limit, offset, interval_span, text_mode, query_mode) in enumerate(combinations, start=1):
            accepted = page_limit <= 50 and offset >= 0 and interval_span >= 1
            review = profile.expected_review or text_mode == "empty" or offset > 20
            body = {"probe_id": f"{profile.profile_id}:{index:03d}", "profile_id": profile.profile_id, "page_limit": page_limit, "offset": offset, "interval_span": interval_span, "text_mode": text_mode, "query_mode": query_mode, "accepted": accepted, "review_required": review, "detail": "bounded query and rendering threshold"}
            probes.append(WorkspaceFrontierThresholdProbe(**body, content_address=content_hash(body)))
    accepted_ids = tuple(item.probe_id for item in probes if item.accepted and not item.review_required)
    review_ids = tuple(item.probe_id for item in probes if item.review_required or not item.accepted)
    body = {"profiles": profiles, "probes": tuple(probes), "accepted_probe_ids": accepted_ids, "review_probe_ids": review_ids}
    return WorkspaceFrontierThresholdReport(profiles=profiles, probes=tuple(probes), accepted_probe_ids=accepted_ids, review_probe_ids=review_ids, content_address=content_hash(body))


__all__ = ["WorkspaceFrontierThresholdProbe", "WorkspaceFrontierThresholdProfile", "WorkspaceFrontierThresholdReport", "build_workspace_frontier_threshold_report", "default_workspace_frontier_threshold_profiles"]
