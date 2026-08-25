"""Compact review summaries for the architecture-program handoff."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Any

from .program_runtime_offline_contracts import ProgramRuntimeOfflineBundle
from .program_runtime_offline_query import _payload, _rows
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ProgramRuntimeOfflineSummary:
    bundle_id: str
    counters: tuple[tuple[str, int | float], ...]
    domains: tuple[dict[str, Any], ...]
    states: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str

    @property
    def counter_map(self) -> dict[str, int | float]:
        return dict(self.counters)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramRuntimeOfflineSummaryAudit:
    bundle_id: str
    checks: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str

    @property
    def passed_count(self) -> int:
        return sum(item["passed"] for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed_count": self.passed_count,
            "failed_count": len(self.checks) - self.passed_count,
        }


def _check(
    check_id: str, passed: bool, observed: Any, required: Any, detail: str
) -> dict[str, Any]:
    body = {
        "check_id": check_id,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return body | {
        "content_address": content_hash(body, prefix="program-runtime-offline-summary-check")
    }


def build_program_runtime_offline_summary(
    bundle: ProgramRuntimeOfflineBundle,
) -> ProgramRuntimeOfflineSummary:
    """Build stable counters without embedding full runtime payloads."""

    domains = _rows(bundle, "domains")
    stages = _rows(bundle, "stages")
    quality = _payload(bundle, "quality") or {}
    operational = _payload(bundle, "operational") or {}
    domain_rows = tuple(
        {
            "domain_id": item.get("domain_id"),
            "domain": item.get("domain"),
            "runtime_state": item.get("runtime_state"),
            "accepted": item.get("accepted"),
            "stage_count": item.get("stage_count", 0),
            "evaluation_check_count": item.get("evaluation_check_count", 0),
            "artifact_count": item.get("artifact_count", 0),
            "issue_count": len(item.get("issue_codes", ())),
            "content_address": item.get("content_address"),
        }
        for item in sorted(domains, key=lambda value: str(value.get("domain_id")))
    )
    state_counts: dict[str, int] = {}
    for item in domains:
        state = str(item.get("runtime_state", "unknown"))
        state_counts[state] = state_counts.get(state, 0) + 1
    states = tuple(
        {"state": state, "count": count} for state, count in sorted(state_counts.items())
    )
    counters: tuple[tuple[str, int | float], ...] = tuple(
        sorted(
            {
                "artifact_count": bundle.artifact_count,
                "domain_count": len(domains),
                "program_check_count": len(_rows(bundle, "checks")),
                "quality_check_count": len(_rows(bundle, "quality")),
                "release_check_count": len(_rows(bundle, "release_checks")),
                "stage_count": len(stages),
                "specification_count": len(_rows(bundle, "specifications")),
                "capability_count": len(_rows(bundle, "capabilities")),
                "accepted_domain_count": sum(bool(item.get("accepted")) for item in domains),
                "total_stage_count": sum(int(item.get("stage_count", 0)) for item in domains),
                "total_evaluation_check_count": sum(
                    int(item.get("evaluation_check_count", 0)) for item in domains
                ),
                "total_domain_artifact_count": sum(
                    int(item.get("artifact_count", 0)) for item in domains
                ),
                "operational_work_units": int(
                    operational.get("counters", {}).get("total_stage_work_units", 0)
                ),
                "quality_passed_check_count": int(quality.get("passed_checks", 0)),
            }.items()
        )
    )
    body = {
        "bundle_id": bundle.bundle_id,
        "counters": counters,
        "domains": domain_rows,
        "states": states,
        "accepted": bundle.ready,
    }
    return ProgramRuntimeOfflineSummary(
        **body,
        content_address=content_hash(body, prefix="program-runtime-offline-summary"),
    )


def audit_program_runtime_offline_summary(
    summary: ProgramRuntimeOfflineSummary,
) -> ProgramRuntimeOfflineSummaryAudit:
    counters = summary.counter_map
    checks = (
        _check(
            "summary-accepted", summary.accepted, summary.accepted, True, "summary source is ready"
        ),
        _check(
            "summary-domains",
            counters.get("domain_count") == len(summary.domains),
            counters.get("domain_count"),
            len(summary.domains),
            "domain counter matches rows",
        ),
        _check(
            "summary-states",
            sum(int(item["count"]) for item in summary.states) == len(summary.domains),
            sum(int(item["count"]) for item in summary.states),
            len(summary.domains),
            "state rows conserve domains",
        ),
        _check(
            "summary-addresses",
            all(item.get("content_address") for item in summary.domains),
            True,
            True,
            "domain rows retain addresses",
        ),
        _check(
            "summary-unique-domains",
            len({item.get("domain_id") for item in summary.domains}) == len(summary.domains),
            len({item.get("domain_id") for item in summary.domains}),
            len(summary.domains),
            "domain rows are unique",
        ),
        _check(
            "summary-counter-keys",
            len(counters) >= 10,
            len(counters),
            ">=10",
            "summary retains operational counters",
        ),
    )
    accepted = all(item["passed"] for item in checks)
    body = {"bundle_id": summary.bundle_id, "checks": checks, "accepted": accepted}
    return ProgramRuntimeOfflineSummaryAudit(
        bundle_id=summary.bundle_id,
        checks=checks,
        accepted=accepted,
        content_address=content_hash(body, prefix="program-runtime-offline-summary-audit"),
    )


def program_runtime_offline_summary_csv(summary: ProgramRuntimeOfflineSummary) -> str:
    output = io.StringIO()
    fieldnames = (
        "domain_id",
        "domain",
        "runtime_state",
        "accepted",
        "stage_count",
        "evaluation_check_count",
        "artifact_count",
        "issue_count",
        "content_address",
    )
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(summary.domains)
    return output.getvalue()


def program_runtime_offline_summary_markdown(summary: ProgramRuntimeOfflineSummary) -> str:
    lines = [
        "# Architecture program offline summary",
        "",
        f"Bundle: `{summary.bundle_id}`",
        f"Accepted: `{str(summary.accepted).lower()}`",
        "",
        "## Counters",
        "",
    ]
    lines.extend(f"- `{key}`: `{value}`" for key, value in summary.counters)
    lines.extend(
        [
            "",
            "## Domains",
            "",
            "| Domain | State | Accepted | Stages | Checks | Artifacts |",
            "| --- | --- | --- | ---: | ---: | ---: |",
        ]
    )
    lines.extend(
        f"| `{item['domain_id']}` | `{item['runtime_state']}` | "
        f"`{str(item['accepted']).lower()}` | {item['stage_count']} | "
        f"{item['evaluation_check_count']} | {item['artifact_count']} |"
        for item in summary.domains
    )
    return "\n".join(lines) + "\n"


__all__ = [
    "ProgramRuntimeOfflineSummary",
    "ProgramRuntimeOfflineSummaryAudit",
    "audit_program_runtime_offline_summary",
    "build_program_runtime_offline_summary",
    "program_runtime_offline_summary_csv",
    "program_runtime_offline_summary_markdown",
]
