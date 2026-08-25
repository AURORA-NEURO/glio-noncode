"""Deterministic metrics and event projections for portfolio handoffs."""

from __future__ import annotations

import csv
import io
from collections import Counter
from dataclasses import dataclass
from typing import Any

from .module_fabric_support import contains_private_key
from .portfolio_release_contracts import PortfolioReleaseBundle
from .run_workspace import _has_forbidden_key
from .serialization import content_hash

PORTFOLIO_RELEASE_OBSERVABILITY_VERSION = "portfolio-release-observability-v1"


@dataclass(frozen=True, slots=True)
class PortfolioReleaseEvent:
    """One stable lifecycle observation without wall-clock nondeterminism."""

    sequence: int
    event_id: str
    stage: str
    run_id: str | None
    state: str
    detail: str
    address: str | None
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "event_id": self.event_id,
            "stage": self.stage,
            "run_id": self.run_id,
            "state": self.state,
            "detail": self.detail,
            "address": self.address,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class PortfolioReleaseMetric:
    """One numeric or categorical package metric."""

    metric_id: str
    value: int | float | str
    unit: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_id": self.metric_id,
            "value": self.value,
            "unit": self.unit,
            "detail": self.detail,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class PortfolioReleaseObservability:
    """Complete public observability report for one portfolio package."""

    release_id: str
    release_address: str
    events: tuple[PortfolioReleaseEvent, ...]
    metrics: tuple[PortfolioReleaseMetric, ...]
    accepted: bool
    content_address: str

    @property
    def event_count(self) -> int:
        """Return the number of ordered lifecycle observations."""

        return len(self.events)

    @property
    def metric_count(self) -> int:
        """Return the number of stable metric rows."""

        return len(self.metrics)

    def to_dict(self) -> dict[str, Any]:
        return {
            "observability_version": PORTFOLIO_RELEASE_OBSERVABILITY_VERSION,
            "release_id": self.release_id,
            "release_address": self.release_address,
            "event_count": self.event_count,
            "metric_count": self.metric_count,
            "events": [item.to_dict() for item in self.events],
            "metrics": [item.to_dict() for item in self.metrics],
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def _event(
    sequence: int,
    event_id: str,
    stage: str,
    run_id: str | None,
    state: str,
    detail: str,
    address: str | None,
) -> PortfolioReleaseEvent:
    """Create an addressed lifecycle event."""

    body = {
        "sequence": sequence,
        "event_id": event_id,
        "stage": stage,
        "run_id": run_id,
        "state": state,
        "detail": detail,
        "address": address,
    }
    return PortfolioReleaseEvent(
        **body,
        content_address=content_hash(body, prefix="portfolio-release-event"),
    )


def _metric(
    metric_id: str,
    value: int | float | str,
    unit: str,
    detail: str,
) -> PortfolioReleaseMetric:
    """Create an addressed metric row."""

    body = {"metric_id": metric_id, "value": value, "unit": unit, "detail": detail}
    return PortfolioReleaseMetric(
        **body,
        content_address=content_hash(body, prefix="portfolio-release-metric"),
    )


def build_portfolio_release_observability(
    bundle: PortfolioReleaseBundle,
) -> PortfolioReleaseObservability:
    """Materialize lifecycle events and metrics from a release package."""

    events: list[PortfolioReleaseEvent] = [
        _event(
            0,
            "portfolio-selected",
            "selection",
            None,
            bundle.state.value,
            f"selected {bundle.member_count} persisted runs",
            bundle.content_address,
        )
    ]
    for sequence, member in enumerate(sorted(bundle.members, key=lambda item: item.run_id), start=1):
        events.append(
            _event(
                sequence,
                f"member-{member.run_id}",
                "member",
                member.run_id,
                member.state.value,
                f"member has {member.artifact_count} artifacts and {len(member.failed_check_ids)} failed checks",
                member.content_address,
            )
        )
    check_start = len(events)
    for offset, check in enumerate(sorted(bundle.checks, key=lambda item: item.check_id), start=check_start):
        events.append(
            _event(
                offset,
                f"check-{check.check_id}",
                "check",
                None,
                "passed" if check.passed else "failed",
                check.detail,
                check.content_address,
            )
        )
    events.append(
        _event(
            len(events),
            "portfolio-addressed",
            "release",
            None,
            bundle.state.value,
            "final release address is available",
            bundle.content_address,
        )
    )

    kind_counts = Counter(item.kind.value for item in bundle.artifacts)
    media_counts = Counter(item.media_type for item in bundle.artifacts)
    metrics = [
        _metric("member_count", bundle.member_count, "members", "selected portfolio members"),
        _metric("ready_member_count", bundle.ready_member_count, "members", "members passing all release gates"),
        _metric("blocked_member_count", bundle.blocked_member_count, "members", "members retained for review but not ready"),
        _metric("artifact_count", bundle.artifact_count, "artifacts", "exact-byte package artifacts"),
        _metric("artifact_bytes", sum(item.byte_count for item in bundle.artifacts), "bytes", "UTF-8 bytes across all artifacts"),
        _metric("warning_count", bundle.warning_count, "warnings", "member warnings retained in the handoff"),
        _metric("failed_check_count", len(bundle.failed_check_ids), "checks", "failed package checks"),
        _metric("dossier_artifact_count", kind_counts.get("dossier", 0), "artifacts", "namespaced dossier artifacts"),
        _metric("workspace_artifact_count", kind_counts.get("workspace", 0), "artifacts", "namespaced workspace artifacts"),
        _metric("json_artifact_count", media_counts.get("application/json", 0), "artifacts", "JSON artifacts subject to boundary checks"),
        _metric("csv_artifact_count", media_counts.get("text/csv", 0), "artifacts", "tabular public projections"),
        _metric("markdown_artifact_count", media_counts.get("text/markdown", 0), "artifacts", "human-readable reports"),
        _metric("release_accepted", int(bundle.accepted), "boolean", "whether the package passes its declared release gate"),
    ]
    boundary_payload = {
        "events": [item.to_dict() for item in events],
        "metrics": [item.to_dict() for item in metrics],
    }
    accepted = (
        all(item.content_address.startswith("portfolio-release-event:") for item in events)
        and all(item.content_address.startswith("portfolio-release-metric:") for item in metrics)
        and len({item.sequence for item in events}) == len(events)
        and not _has_forbidden_key(boundary_payload)
        and not contains_private_key(boundary_payload)
    )
    body = {
        "observability_version": PORTFOLIO_RELEASE_OBSERVABILITY_VERSION,
        "release_id": bundle.release_id,
        "release_address": bundle.content_address,
        "events": [item.to_dict() for item in events],
        "metrics": [item.to_dict() for item in metrics],
        "accepted": accepted,
    }
    return PortfolioReleaseObservability(
        release_id=bundle.release_id,
        release_address=bundle.content_address,
        events=tuple(events),
        metrics=tuple(metrics),
        accepted=accepted,
        content_address=content_hash(body, prefix="portfolio-release-observability"),
    )


def portfolio_release_metrics_csv(
    report: PortfolioReleaseObservability,
) -> str:
    """Export stable metric rows for dashboards and offline review."""

    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("metric_id", "value", "unit", "detail", "content_address"))
    for item in report.metrics:
        writer.writerow((item.metric_id, item.value, item.unit, item.detail, item.content_address))
    return output.getvalue()


def portfolio_release_events_csv(
    report: PortfolioReleaseObservability,
) -> str:
    """Export the ordered event transcript as CSV."""

    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("sequence", "event_id", "stage", "run_id", "state", "detail", "address", "content_address"))
    for item in report.events:
        writer.writerow((item.sequence, item.event_id, item.stage, item.run_id or "", item.state, item.detail, item.address or "", item.content_address))
    return output.getvalue()


__all__ = [
    "PORTFOLIO_RELEASE_OBSERVABILITY_VERSION",
    "PortfolioReleaseEvent",
    "PortfolioReleaseMetric",
    "PortfolioReleaseObservability",
    "build_portfolio_release_observability",
    "portfolio_release_events_csv",
    "portfolio_release_metrics_csv",
]
