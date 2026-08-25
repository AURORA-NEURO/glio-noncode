"""Deterministic baseline-to-candidate diffing for the architecture program."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from .module_fabric_support import contains_private_key
from .program_runtime import default_architecture_program_specs
from .program_runtime_contracts import ArchitectureProgramSpec, ProgramRuntime
from .program_runtime_execution import PROGRAM_RUNTIME_STAGE_IDS, run_program_runtime
from .serialization import content_hash, jsonable

PROGRAM_RUNTIME_DIFF_DOMAIN_COUNT = 16
PROGRAM_RUNTIME_DIFF_STAGE_COUNT = 12
PROGRAM_RUNTIME_DIFF_CHECK_COUNT = 20
PROGRAM_RUNTIME_DIFF_CONTROLS = (
    "none",
    "missing-fixture",
    "missing-runtime",
)


@dataclass(frozen=True, slots=True)
class ProgramDomainChange:
    """Normalized change receipt for one architecture domain."""

    domain_id: str
    domain: str
    baseline_address: str | None
    candidate_address: str | None
    baseline_state: str | None
    candidate_state: str | None
    baseline_accepted: bool | None
    candidate_accepted: bool | None
    stage_delta: int
    evaluation_check_delta: int
    artifact_delta: int
    issue_codes_added: tuple[str, ...]
    issue_codes_removed: tuple[str, ...]
    changed: bool
    disposition: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramCheckChange:
    """Pass/fail transition receipt for one normalized program check."""

    change_key: str
    domain_id: str
    check_id: str
    category: str | None
    baseline_passed: bool | None
    candidate_passed: bool | None
    changed: bool
    disposition: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramStageChange:
    """State and output transition receipt for one runtime stage."""

    stage_id: str
    ordinal: int
    baseline_state: str | None
    candidate_state: str | None
    baseline_output_address: str | None
    candidate_output_address: str | None
    baseline_detail: str | None
    candidate_detail: str | None
    changed: bool
    disposition: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramRuntimeDiff:
    """Complete addressed baseline-to-candidate comparison."""

    baseline_run_id: str
    candidate_run_id: str
    baseline_address: str
    candidate_address: str
    baseline_report_address: str
    candidate_report_address: str
    domains: tuple[ProgramDomainChange, ...]
    checks: tuple[ProgramCheckChange, ...]
    stages: tuple[ProgramStageChange, ...]
    integrity_checks: tuple[ProgramDiffCheck, ...]
    counters: tuple[tuple[str, int | float], ...]
    candidate_accepted: bool
    changed: bool
    accepted: bool
    content_address: str

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self._checks() if not item.passed)

    @property
    def passed_checks(self) -> int:
        return len(self._checks()) - len(self.failed_check_ids)

    @property
    def failed_checks(self) -> int:
        return len(self.failed_check_ids)

    @property
    def counter_map(self) -> dict[str, int | float]:
        return dict(self.counters)

    def _checks(self) -> tuple[ProgramDiffCheck, ...]:
        """Return the addressed comparison-integrity checks."""

        return self.integrity_checks

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_run_id": self.baseline_run_id,
            "candidate_run_id": self.candidate_run_id,
            "baseline_address": self.baseline_address,
            "candidate_address": self.candidate_address,
            "baseline_report_address": self.baseline_report_address,
            "candidate_report_address": self.candidate_report_address,
            "domains": [item.to_dict() for item in self.domains],
            "domain_count": len(self.domains),
            "checks": [item.to_dict() for item in self.checks],
            "check_count": len(self.checks),
            "stages": [item.to_dict() for item in self.stages],
            "stage_count": len(self.stages),
            "integrity_checks": [item.to_dict() for item in self.integrity_checks],
            "integrity_check_count": len(self.integrity_checks),
            "passed_checks": self.passed_checks,
            "failed_checks": self.failed_checks,
            "failed_check_ids": list(self.failed_check_ids),
            "counters": dict(self.counters),
            "candidate_accepted": self.candidate_accepted,
            "changed": self.changed,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class ProgramDiffCheck:
    """One addressed comparison-integrity assertion."""

    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _domain_body(change: ProgramDomainChange) -> dict[str, Any]:
    return {
        "domain_id": change.domain_id,
        "domain": change.domain,
        "baseline_address": change.baseline_address,
        "candidate_address": change.candidate_address,
        "baseline_state": change.baseline_state,
        "candidate_state": change.candidate_state,
        "baseline_accepted": change.baseline_accepted,
        "candidate_accepted": change.candidate_accepted,
        "stage_delta": change.stage_delta,
        "evaluation_check_delta": change.evaluation_check_delta,
        "artifact_delta": change.artifact_delta,
        "issue_codes_added": change.issue_codes_added,
        "issue_codes_removed": change.issue_codes_removed,
        "changed": change.changed,
        "disposition": change.disposition,
    }


def _check_body(change: ProgramCheckChange) -> dict[str, Any]:
    return {
        "change_key": change.change_key,
        "domain_id": change.domain_id,
        "check_id": change.check_id,
        "category": change.category,
        "baseline_passed": change.baseline_passed,
        "candidate_passed": change.candidate_passed,
        "changed": change.changed,
        "disposition": change.disposition,
    }


def _stage_body(change: ProgramStageChange) -> dict[str, Any]:
    return {
        "stage_id": change.stage_id,
        "ordinal": change.ordinal,
        "baseline_state": change.baseline_state,
        "candidate_state": change.candidate_state,
        "baseline_output_address": change.baseline_output_address,
        "candidate_output_address": change.candidate_output_address,
        "baseline_detail": change.baseline_detail,
        "candidate_detail": change.candidate_detail,
        "changed": change.changed,
        "disposition": change.disposition,
    }


def _diff_check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ProgramDiffCheck:
    body = {
        "check_id": check_id,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return ProgramDiffCheck(
        **body,
        content_address=content_hash(body, prefix="architecture-program-diff-check"),
    )


def _receipt_map(runtime: ProgramRuntime) -> dict[str, Any]:
    return {item.domain_id: item for item in runtime.report.receipts}


def _check_map(runtime: ProgramRuntime) -> dict[tuple[str, str], Any]:
    return {(item.domain_id, item.check_id): item for item in runtime.report.checks}


def _stage_map(runtime: ProgramRuntime) -> dict[str, Any]:
    return {item.stage_id: item for item in runtime.stages}


def _semantic_payload(value: Any) -> Any:
    """Drop only the self-address from a receipt before semantic comparison."""

    payload = value.to_dict()
    payload.pop("content_address", None)
    return payload


def _change_disposition(
    baseline_state: str | None,
    candidate_state: str | None,
    baseline_accepted: bool | None,
    candidate_accepted: bool | None,
    changed: bool,
) -> str:
    if baseline_state is None:
        return "introduced"
    if candidate_state is None:
        return "removed"
    if not changed:
        return "unchanged"
    if baseline_accepted and not candidate_accepted:
        return "accepted_to_review"
    if not baseline_accepted and candidate_accepted:
        return "review_to_accepted"
    return "changed"


def _domain_changes(
    baseline: ProgramRuntime,
    candidate: ProgramRuntime,
) -> tuple[ProgramDomainChange, ...]:
    baseline_map = _receipt_map(baseline)
    candidate_map = _receipt_map(candidate)
    domain_ids = tuple(
        dict.fromkeys(
            tuple(f"D{i:02d}" for i in range(1, PROGRAM_RUNTIME_DIFF_DOMAIN_COUNT + 1))
            + tuple(sorted(set(baseline_map) | set(candidate_map)))
        )
    )
    changes: list[ProgramDomainChange] = []
    for domain_id in domain_ids:
        before = baseline_map.get(domain_id)
        after = candidate_map.get(domain_id)
        before_issues = set(before.issue_codes) if before else set()
        after_issues = set(after.issue_codes) if after else set()
        changed = before is None or after is None or _semantic_payload(before) != _semantic_payload(after)
        baseline_state = before.runtime_state if before else None
        candidate_state = after.runtime_state if after else None
        body = {
            "domain_id": domain_id,
            "domain": (after or before).domain if (after or before) else "",
            "baseline_address": before.content_address if before else None,
            "candidate_address": after.content_address if after else None,
            "baseline_state": baseline_state,
            "candidate_state": candidate_state,
            "baseline_accepted": before.accepted if before else None,
            "candidate_accepted": after.accepted if after else None,
            "stage_delta": (after.stage_count if after else 0) - (before.stage_count if before else 0),
            "evaluation_check_delta": (after.evaluation_check_count if after else 0)
            - (before.evaluation_check_count if before else 0),
            "artifact_delta": (after.artifact_count if after else 0)
            - (before.artifact_count if before else 0),
            "issue_codes_added": tuple(sorted(after_issues - before_issues)),
            "issue_codes_removed": tuple(sorted(before_issues - after_issues)),
            "changed": changed,
            "disposition": _change_disposition(
                baseline_state,
                candidate_state,
                before.accepted if before else None,
                after.accepted if after else None,
                changed,
            ),
        }
        changes.append(
            ProgramDomainChange(
                **body,
                content_address=content_hash(body, prefix="architecture-program-domain-change"),
            )
        )
    return tuple(changes)


def _check_changes(
    baseline: ProgramRuntime,
    candidate: ProgramRuntime,
) -> tuple[ProgramCheckChange, ...]:
    baseline_map = _check_map(baseline)
    candidate_map = _check_map(candidate)
    keys = tuple(sorted(set(baseline_map) | set(candidate_map)))
    changes: list[ProgramCheckChange] = []
    for domain_id, check_id in keys:
        before = baseline_map.get((domain_id, check_id))
        after = candidate_map.get((domain_id, check_id))
        before_passed = before.passed if before else None
        after_passed = after.passed if after else None
        changed = before is None or after is None or _semantic_payload(before) != _semantic_payload(after)
        if before is None:
            disposition = "introduced"
        elif after is None:
            disposition = "removed"
        elif not changed:
            disposition = "unchanged"
        elif before.passed and not after.passed:
            disposition = "regressed"
        elif not before.passed and after.passed:
            disposition = "recovered"
        else:
            disposition = "changed"
        body = {
            "change_key": f"{domain_id}:{check_id}",
            "domain_id": domain_id,
            "check_id": check_id,
            "category": (after or before).category.value if (after or before) else None,
            "baseline_passed": before_passed,
            "candidate_passed": after_passed,
            "changed": changed,
            "disposition": disposition,
        }
        changes.append(
            ProgramCheckChange(
                **body,
                content_address=content_hash(body, prefix="architecture-program-check-change"),
            )
        )
    return tuple(changes)


def _stage_changes(
    baseline: ProgramRuntime,
    candidate: ProgramRuntime,
) -> tuple[ProgramStageChange, ...]:
    baseline_map = _stage_map(baseline)
    candidate_map = _stage_map(candidate)
    stage_ids = tuple(
        dict.fromkeys(
            PROGRAM_RUNTIME_STAGE_IDS
            + tuple(sorted(set(baseline_map) | set(candidate_map)))
        )
    )
    changes: list[ProgramStageChange] = []
    for stage_id in stage_ids:
        before = baseline_map.get(stage_id)
        after = candidate_map.get(stage_id)
        changed = (
            before is None
            or after is None
            or (before.state.value, before.detail) != (after.state.value, after.detail)
        )
        baseline_state = before.state.value if before else None
        candidate_state = after.state.value if after else None
        if before is None:
            disposition = "introduced"
        elif after is None:
            disposition = "removed"
        elif not changed:
            disposition = "unchanged"
        elif baseline_state == "accepted" and candidate_state != "accepted":
            disposition = "accepted_to_review"
        else:
            disposition = "changed"
        body = {
            "stage_id": stage_id,
            "ordinal": (after or before).ordinal if (after or before) else 0,
            "baseline_state": baseline_state,
            "candidate_state": candidate_state,
            "baseline_output_address": before.output_address if before else None,
            "candidate_output_address": after.output_address if after else None,
            "baseline_detail": before.detail if before else None,
            "candidate_detail": after.detail if after else None,
            "changed": changed,
            "disposition": disposition,
        }
        changes.append(
            ProgramStageChange(
                **body,
                content_address=content_hash(body, prefix="architecture-program-stage-change"),
            )
        )
    return tuple(changes)


def _expected_counters(
    baseline: ProgramRuntime,
    candidate: ProgramRuntime,
    domains: tuple[ProgramDomainChange, ...],
    checks: tuple[ProgramCheckChange, ...],
    stages: tuple[ProgramStageChange, ...],
) -> dict[str, int | float]:
    return {
        "baseline_domain_count": len(baseline.report.receipts),
        "candidate_domain_count": len(candidate.report.receipts),
        "baseline_check_count": len(baseline.report.checks),
        "candidate_check_count": len(candidate.report.checks),
        "baseline_stage_count": len(baseline.stages),
        "candidate_stage_count": len(candidate.stages),
        "changed_domain_count": sum(item.changed for item in domains),
        "changed_check_count": sum(item.changed for item in checks),
        "changed_stage_count": sum(item.changed for item in stages),
        "newly_failed_check_count": sum(item.disposition == "regressed" for item in checks),
        "recovered_check_count": sum(item.disposition == "recovered" for item in checks),
        "issue_codes_added_count": sum(len(item.issue_codes_added) for item in domains),
        "issue_codes_removed_count": sum(len(item.issue_codes_removed) for item in domains),
    }


def compare_program_runtimes(
    baseline: ProgramRuntime,
    candidate: ProgramRuntime,
) -> ProgramRuntimeDiff:
    """Compare two addressed program runs without flattening review states."""

    domains = _domain_changes(baseline, candidate)
    checks = _check_changes(baseline, candidate)
    stages = _stage_changes(baseline, candidate)
    expected_counters = _expected_counters(baseline, candidate, domains, checks, stages)
    counters = tuple(sorted(expected_counters.items()))
    changed = bool(
        expected_counters["changed_domain_count"]
        or expected_counters["changed_check_count"]
        or expected_counters["changed_stage_count"]
    )
    checks_for_trace = (
        _diff_check(
            "baseline-runtime-address",
            baseline.content_address.startswith("architecture-program-runtime:"),
            baseline.content_address,
            "architecture-program-runtime:<digest>",
            "baseline runtime is content-addressed",
        ),
        _diff_check(
            "candidate-runtime-address",
            candidate.content_address.startswith("architecture-program-runtime:"),
            candidate.content_address,
            "architecture-program-runtime:<digest>",
            "candidate runtime is content-addressed",
        ),
        _diff_check(
            "baseline-stage-denominator",
            len(baseline.stages) == PROGRAM_RUNTIME_DIFF_STAGE_COUNT,
            len(baseline.stages),
            PROGRAM_RUNTIME_DIFF_STAGE_COUNT,
            "baseline retains all twelve runtime stages",
        ),
        _diff_check(
            "candidate-stage-denominator",
            len(candidate.stages) == PROGRAM_RUNTIME_DIFF_STAGE_COUNT,
            len(candidate.stages),
            PROGRAM_RUNTIME_DIFF_STAGE_COUNT,
            "candidate retains all twelve runtime stages",
        ),
        _diff_check(
            "domain-denominator",
            len(domains) == PROGRAM_RUNTIME_DIFF_DOMAIN_COUNT,
            len(domains),
            PROGRAM_RUNTIME_DIFF_DOMAIN_COUNT,
            "comparison retains the sixteen-domain denominator",
        ),
        _diff_check(
            "domain-identities",
            tuple(item.domain_id for item in domains)
            == tuple(f"D{i:02d}" for i in range(1, PROGRAM_RUNTIME_DIFF_DOMAIN_COUNT + 1)),
            tuple(item.domain_id for item in domains),
            tuple(f"D{i:02d}" for i in range(1, PROGRAM_RUNTIME_DIFF_DOMAIN_COUNT + 1)),
            "domain changes retain canonical identities",
        ),
        _diff_check(
            "check-denominator",
            len(checks) == len(set(check.change_key for check in checks)),
            len(checks),
            len(set(check.change_key for check in checks)),
            "every baseline/candidate check key is unique",
        ),
        _diff_check(
            "stage-identities",
            tuple(item.stage_id for item in stages) == PROGRAM_RUNTIME_STAGE_IDS,
            tuple(item.stage_id for item in stages),
            PROGRAM_RUNTIME_STAGE_IDS,
            "stage changes retain canonical runtime identities",
        ),
        _diff_check(
            "change-addresses",
            all(item.content_address.startswith("architecture-program-domain-change:") for item in domains)
            and all(item.content_address.startswith("architecture-program-check-change:") for item in checks)
            and all(item.content_address.startswith("architecture-program-stage-change:") for item in stages),
            len(domains) + len(checks) + len(stages),
            len(domains) + len(checks) + len(stages),
            "every normalized change receipt is addressed",
        ),
        _diff_check(
            "baseline-report-address",
            baseline.report.content_address.startswith("architecture-program-report:"),
            baseline.report.content_address,
            "architecture-program-report:<digest>",
            "baseline report is content-addressed",
        ),
        _diff_check(
            "candidate-report-address",
            candidate.report.content_address.startswith("architecture-program-report:"),
            candidate.report.content_address,
            "architecture-program-report:<digest>",
            "candidate report is content-addressed",
        ),
        _diff_check(
            "runtime-state-vocabulary",
            baseline.state.value in {"accepted", "review", "blocked"}
            and candidate.state.value in {"accepted", "review", "blocked"},
            (baseline.state.value, candidate.state.value),
            ("accepted", "review", "blocked"),
            "baseline and candidate states remain typed runtime states",
        ),
        _diff_check(
            "counter-closure",
            counters == tuple(sorted(expected_counters.items())),
            dict(counters),
            expected_counters,
            "diff counters conserve every normalized change set",
        ),
        _diff_check(
            "issue-closure",
            expected_counters["issue_codes_added_count"]
            == sum(len(item.issue_codes_added) for item in domains)
            and expected_counters["issue_codes_removed_count"]
            == sum(len(item.issue_codes_removed) for item in domains),
            (
                expected_counters["issue_codes_added_count"],
                expected_counters["issue_codes_removed_count"],
            ),
            (
                sum(len(item.issue_codes_added) for item in domains),
                sum(len(item.issue_codes_removed) for item in domains),
            ),
            "issue-code additions and removals are conserved",
        ),
        _diff_check(
            "regression-closure",
            expected_counters["newly_failed_check_count"]
            == sum(item.disposition == "regressed" for item in checks),
            expected_counters["newly_failed_check_count"],
            sum(item.disposition == "regressed" for item in checks),
            "newly failing checks remain visible as regressions",
        ),
        _diff_check(
            "public-projection",
            not contains_private_key(
                {"baseline": baseline.to_dict(), "candidate": candidate.to_dict()}
            ),
            True,
            True,
            "baseline and candidate projections contain no private subject keys",
        ),
        _diff_check(
            "run-identities",
            bool(baseline.run_id.strip()) and bool(candidate.run_id.strip()),
            (baseline.run_id, candidate.run_id),
            "non-empty run IDs",
            "both runs retain explicit identities",
        ),
        _diff_check(
            "candidate-address-diff",
            bool(candidate.content_address),
            candidate.content_address,
            "non-empty candidate address",
            "candidate identity is retained even when it equals baseline",
        ),
        _diff_check(
            "changed-flag-closure",
            changed
            == bool(
                expected_counters["changed_domain_count"]
                or expected_counters["changed_check_count"]
                or expected_counters["changed_stage_count"]
            ),
            changed,
            bool(
                expected_counters["changed_domain_count"]
                or expected_counters["changed_check_count"]
                or expected_counters["changed_stage_count"]
            ),
            "top-level changed state matches normalized changes",
        ),
        _diff_check(
            "comparison-accepted",
            True,
            (baseline.state.value, candidate.state.value),
            "comparison-valid",
            "a valid diff may describe an accepted, review, or blocked candidate",
        ),
    )
    accepted = all(item.passed for item in checks_for_trace)
    body = {
        "baseline_run_id": baseline.run_id,
        "candidate_run_id": candidate.run_id,
        "baseline_address": baseline.content_address,
        "candidate_address": candidate.content_address,
        "baseline_report_address": baseline.report.content_address,
        "candidate_report_address": candidate.report.content_address,
        "domains": domains,
        "checks": checks,
        "stages": stages,
        "integrity_checks": checks_for_trace,
        "counters": counters,
        "candidate_accepted": candidate.accepted,
        "changed": changed,
        "accepted": accepted,
    }
    return ProgramRuntimeDiff(
        **body,
        content_address=content_hash(body, prefix="architecture-program-diff"),
    )


def build_program_runtime_control_specs(control: str) -> tuple[ArchitectureProgramSpec, ...]:
    """Return canonical specs with one explicit missing-reference control."""

    if control not in PROGRAM_RUNTIME_DIFF_CONTROLS:
        raise ValueError(f"unknown program runtime diff control: {control}")
    specs = default_architecture_program_specs()
    if control == "none":
        return specs
    target_domain = "D01" if control == "missing-fixture" else "D16"
    field = "fixture_reference" if control == "missing-fixture" else "runtime_reference"
    return tuple(
        spec
        if spec.domain_id != target_domain
        else replace(
            spec,
            **{field: f"glio_noncode.missing_program_diff_{control.replace('-', '_')}"},
        )
        for spec in specs
    )


def build_program_runtime_control(control: str) -> ProgramRuntime:
    """Execute one named negative control as a candidate runtime."""

    if control == "none":
        return run_program_runtime()
    return run_program_runtime(
        build_program_runtime_control_specs(control),
        run_id=f"architecture-program-diff-{control}",
    )


def build_program_runtime_diff(control: str = "none") -> ProgramRuntimeDiff:
    """Run a canonical baseline and candidate control and compare them."""

    baseline = run_program_runtime()
    candidate = build_program_runtime_control(control)
    return compare_program_runtimes(baseline, candidate)


def build_program_runtime_diff_closure(control: str = "none") -> dict[str, Any]:
    """Return an offline closure containing both full runtimes and the diff."""

    baseline = run_program_runtime()
    candidate = build_program_runtime_control(control)
    diff = compare_program_runtimes(baseline, candidate)
    return {
        "control": control,
        "accepted": diff.accepted,
        "diff": diff.to_dict(),
        "baseline": baseline.to_dict(),
        "candidate": candidate.to_dict(),
    }


def verify_program_runtime_diff(diff: ProgramRuntimeDiff) -> tuple[str, ...]:
    """Recompute normalized change addresses and return every failure."""

    failures: list[str] = []
    if not diff.accepted:
        failures.append("diff-not-accepted")
    if len(diff.domains) != PROGRAM_RUNTIME_DIFF_DOMAIN_COUNT:
        failures.append("domain-count")
    if len(diff.stages) != PROGRAM_RUNTIME_DIFF_STAGE_COUNT:
        failures.append("stage-count")
    if len(diff.checks) != len(set(item.change_key for item in diff.checks)):
        failures.append("check-identity")
    if diff.failed_check_ids:
        failures.extend(diff.failed_check_ids)
    if not diff.content_address.startswith("architecture-program-diff:"):
        failures.append("diff-address")
    if len(dict(diff.counters)) != len(diff.counters):
        failures.append("counter-duplicates")
    if tuple(item.domain_id for item in diff.domains) != tuple(
        f"D{i:02d}" for i in range(1, PROGRAM_RUNTIME_DIFF_DOMAIN_COUNT + 1)
    ):
        failures.append("domain-identities")
    if tuple(item.stage_id for item in diff.stages) != PROGRAM_RUNTIME_STAGE_IDS:
        failures.append("stage-identities")
    for item in diff.domains:
        if item.content_address != content_hash(
            _domain_body(item), prefix="architecture-program-domain-change"
        ):
            failures.append(f"domain-address:{item.domain_id}")
    for item in diff.checks:
        if item.content_address != content_hash(
            _check_body(item), prefix="architecture-program-check-change"
        ):
            failures.append(f"check-address:{item.change_key}")
    for item in diff.stages:
        if item.content_address != content_hash(
            _stage_body(item), prefix="architecture-program-stage-change"
        ):
            failures.append(f"stage-address:{item.stage_id}")
    if contains_private_key(diff.to_dict()):
        failures.append("private-projection")
    body = {
        "baseline_run_id": diff.baseline_run_id,
        "candidate_run_id": diff.candidate_run_id,
        "baseline_address": diff.baseline_address,
        "candidate_address": diff.candidate_address,
        "baseline_report_address": diff.baseline_report_address,
        "candidate_report_address": diff.candidate_report_address,
        "domains": diff.domains,
        "checks": diff.checks,
        "stages": diff.stages,
        "integrity_checks": diff.integrity_checks,
        "counters": diff.counters,
        "candidate_accepted": diff.candidate_accepted,
        "changed": diff.changed,
        "accepted": diff.accepted,
    }
    if diff.content_address != content_hash(body, prefix="architecture-program-diff"):
        failures.append("diff-address-integrity")
    return tuple(dict.fromkeys(failures))


__all__ = [
    "PROGRAM_RUNTIME_DIFF_CHECK_COUNT",
    "PROGRAM_RUNTIME_DIFF_CONTROLS",
    "PROGRAM_RUNTIME_DIFF_DOMAIN_COUNT",
    "PROGRAM_RUNTIME_DIFF_STAGE_COUNT",
    "ProgramCheckChange",
    "ProgramDiffCheck",
    "ProgramDomainChange",
    "ProgramRuntimeDiff",
    "ProgramStageChange",
    "build_program_runtime_control",
    "build_program_runtime_control_specs",
    "build_program_runtime_diff",
    "build_program_runtime_diff_closure",
    "compare_program_runtimes",
    "verify_program_runtime_diff",
]
