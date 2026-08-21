"""Hardening and operational depth for the D13-D16 frontier surfaces."""

from __future__ import annotations

import csv
import io
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .frontier_data_alpha import (
    FrontierIssue,
    FrontierState,
    _address,
    _bounded,
    _context,
    _float,
    _mapping,
    _required_text,
    _text,
    _tuple_text,
)
from .serialization import canonical_json, jsonable, require_non_empty


def _dna(value: Any, *, field: str) -> str:
    result = "".join(_text(value, field=field).upper().split())
    if result and not set(result).issubset(set("ACGTN")):
        raise ValidationError(f"{field} contains unsupported bases")
    return result


@dataclass(frozen=True, slots=True)
class AlignmentAudit:
    candidate_id: str
    context_key: str
    guide_sequence: str
    target_sequence: str
    mismatch_count: int
    mismatch_positions: tuple[int, ...]
    pam: str
    pam_match: bool
    alignment_score: float
    risk_score: float
    state: FrontierState
    issues: tuple[FrontierIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AlignmentAuditReport:
    audits: tuple[AlignmentAudit, ...]
    high_risk_ids: tuple[str, ...]
    review_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class OffTargetAlignmentAuditor:
    """Audit guide/target alignments with mismatch-position and PAM receipts."""

    def audit(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
        maximum_mismatches: int = 3,
        risk_threshold: float = 0.35,
    ) -> AlignmentAuditReport:
        context_key = require_non_empty(context_key, "context_key")
        if maximum_mismatches < 0:
            raise ValidationError("maximum_mismatches must not be negative")
        risk_threshold = _bounded(risk_threshold, field="risk_threshold")
        audits: list[AlignmentAudit] = []
        for index, raw in enumerate(records, start=1):
            row = _mapping(raw, label=f"alignment {index}")
            candidate_id = (
                _text(row.get("candidate_id", row.get("id")), field="candidate_id")
                or f"candidate:{index}"
            )
            guide = _dna(row.get("guide_sequence"), field="guide_sequence")
            target = _dna(row.get("target_sequence"), field="target_sequence")
            pam = _text(row.get("pam", ""), field="pam").upper()
            if len(guide) != len(target):
                raise ValidationError(f"{candidate_id} guide and target lengths differ")
            mismatch_positions = tuple(
                index
                for index, (left, right) in enumerate(zip(guide, target, strict=True))
                if left != right
            )
            mismatch_count = len(mismatch_positions)
            pam_match = bool(row.get("pam_match", bool(pam)))
            positional_weight = sum(1.0 / (position + 1) for position in mismatch_positions) / max(
                1, len(guide)
            )
            risk = round(
                max(
                    0.0,
                    (1.0 - mismatch_count / max(1, len(guide)))
                    * (1.0 if pam_match else 0.5)
                    * (1.0 - positional_weight),
                ),
                6,
            )
            score = round(1.0 - risk, 6)
            issues: list[FrontierIssue] = []
            if mismatch_count <= maximum_mismatches and pam_match and risk >= risk_threshold:
                issues.append(
                    FrontierIssue(
                        "alignment_off_target_risk",
                        "alignment remains a high-risk off-target candidate",
                        "review",
                        record_id=candidate_id,
                    )
                )
            if _context(row, context_key) != context_key:
                issues.append(
                    FrontierIssue(
                        "alignment_context_mismatch",
                        "alignment context differs from requested context",
                        "blocking",
                        "context_key",
                        candidate_id,
                    )
                )
            state = FrontierState.ACCEPTED if not issues else FrontierState.REVIEW
            audits.append(
                AlignmentAudit(
                    candidate_id,
                    context_key,
                    guide,
                    target,
                    mismatch_count,
                    mismatch_positions,
                    pam,
                    pam_match,
                    score,
                    risk,
                    state,
                    tuple(issues),
                )
            )
        high = tuple(item.candidate_id for item in audits if item.risk_score >= risk_threshold)
        review = tuple(item.candidate_id for item in audits if item.state != FrontierState.ACCEPTED)
        return AlignmentAuditReport(tuple(audits), high, review, _address(audits))


@dataclass(frozen=True, slots=True)
class ReadinessCheck:
    check_id: str
    passed: bool
    message: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationReadinessReport:
    package_id: str
    context_key: str
    checks: tuple[ReadinessCheck, ...]
    passed_ids: tuple[str, ...]
    failed_ids: tuple[str, ...]
    state: FrontierState
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ValidationExecutionReadinessChecker:
    """Check an experiment package before execution without executing it."""

    def evaluate(
        self,
        package: Mapping[str, Any],
        *,
        package_id: str,
        context_key: str,
        required_controls: Sequence[str] = (),
        required_outputs: Sequence[str] = (),
    ) -> ValidationReadinessReport:
        package_id = require_non_empty(package_id, "package_id")
        context_key = require_non_empty(context_key, "context_key")
        data = _mapping(package, label="validation package")
        experiments = tuple(
            _mapping(item, label="readiness experiment") for item in data.get("experiments", ())
        )
        controls = {
            _text(item.get("control_id", item.get("id")), field="control_id")
            for item in data.get("controls", ())
            if isinstance(item, Mapping)
        }
        outputs = set(_tuple_text(data.get("outputs", ()), field="outputs"))
        checks: list[ReadinessCheck] = []
        checks.append(
            ReadinessCheck(
                "experiments_present",
                bool(experiments),
                "experiments are declared" if experiments else "no experiments are declared",
            )
        )
        checks.append(
            ReadinessCheck(
                "context_match",
                _text(data.get("context_key"), field="context_key") in {"", context_key},
                "package context is compatible",
            )
        )
        missing_controls = tuple(item for item in required_controls if item not in controls)
        checks.append(
            ReadinessCheck(
                "controls_present",
                not missing_controls,
                "required controls are present"
                if not missing_controls
                else f"missing controls: {', '.join(missing_controls)}",
            )
        )
        missing_outputs = tuple(item for item in required_outputs if item not in outputs)
        checks.append(
            ReadinessCheck(
                "outputs_declared",
                not missing_outputs,
                "required outputs are declared"
                if not missing_outputs
                else f"missing outputs: {', '.join(missing_outputs)}",
            )
        )
        checks.append(
            ReadinessCheck(
                "experiment_contexts",
                all(_context(item, context_key) == context_key for item in experiments),
                "experiment contexts are compatible",
            )
        )
        passed = tuple(item.check_id for item in checks if item.passed)
        failed = tuple(item.check_id for item in checks if not item.passed)
        return ValidationReadinessReport(
            package_id,
            context_key,
            tuple(checks),
            passed,
            failed,
            FrontierState.ACCEPTED if not failed else FrontierState.REVIEW,
            _address(checks),
        )


@dataclass(frozen=True, slots=True)
class GraphIntegrityReport:
    context_key: str
    node_count: int
    edge_count: int
    duplicate_node_ids: tuple[str, ...]
    dangling_node_ids: tuple[str, ...]
    cycle_node_ids: tuple[str, ...]
    issues: tuple[FrontierIssue, ...]
    state: FrontierState
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class EvidenceGraphIntegrityAuditor:
    """Audit evidence graph identity, context, dangling edges, and cycles."""

    def audit(
        self,
        nodes: Iterable[Mapping[str, Any]],
        edges: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
    ) -> GraphIntegrityReport:
        context_key = require_non_empty(context_key, "context_key")
        node_rows = tuple(_mapping(item, label="evidence node") for item in nodes)
        edge_rows = tuple(_mapping(item, label="evidence edge") for item in edges)
        node_ids = tuple(
            _required_text(item.get("node_id", item.get("id")), field="node_id")
            for item in node_rows
        )
        counts = Counter(node_ids)
        duplicates = tuple(sorted(identifier for identifier, count in counts.items() if count > 1))
        known = set(node_ids)
        adjacency: dict[str, list[str]] = {identifier: [] for identifier in known}
        dangling: set[str] = set()
        issues: list[FrontierIssue] = []
        for row in node_rows:
            if _context(row, context_key) != context_key:
                issues.append(
                    FrontierIssue(
                        "graph_node_context_mismatch",
                        "evidence node context differs from graph context",
                        "blocking",
                        "context_key",
                        _text(row.get("node_id", row.get("id")), field="node_id"),
                    )
                )
        for row in edge_rows:
            source = _required_text(row.get("source_id"), field="source_id")
            target = _required_text(row.get("target_id"), field="target_id")
            if source not in known or target not in known:
                dangling.update(
                    identifier for identifier in (source, target) if identifier not in known
                )
            else:
                adjacency[source].append(target)
        if duplicates:
            issues.append(
                FrontierIssue(
                    "duplicate_graph_nodes",
                    "evidence graph contains duplicate node IDs",
                    "blocking",
                )
            )
        if dangling:
            issues.append(
                FrontierIssue(
                    "dangling_graph_edges",
                    "evidence graph contains edges to missing nodes",
                    "review",
                )
            )
        cycle_nodes: set[str] = set()
        visiting: set[str] = set()
        visited: set[str] = set()

        def walk(node_id: str) -> None:
            if node_id in visiting:
                cycle_nodes.add(node_id)
                return
            if node_id in visited:
                return
            visiting.add(node_id)
            for child in adjacency.get(node_id, ()):
                walk(child)
                if child in cycle_nodes:
                    cycle_nodes.add(node_id)
            visiting.remove(node_id)
            visited.add(node_id)

        for identifier in sorted(known):
            walk(identifier)
        if cycle_nodes:
            issues.append(
                FrontierIssue(
                    "cyclic_evidence_graph", "evidence graph contains a directed cycle", "blocking"
                )
            )
        state = FrontierState.ACCEPTED if not issues else FrontierState.REVIEW
        return GraphIntegrityReport(
            context_key,
            len(node_rows),
            len(edge_rows),
            duplicates,
            tuple(sorted(dangling)),
            tuple(sorted(cycle_nodes)),
            tuple(issues),
            state,
            _address({"nodes": node_rows, "edges": edge_rows}),
        )


@dataclass(frozen=True, slots=True)
class EvidenceLineageEntry:
    item_id: str
    parent_ids: tuple[str, ...]
    source_addresses: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLineageReport:
    entries: tuple[EvidenceLineageEntry, ...]
    root_ids: tuple[str, ...]
    manifest_address: str
    state: FrontierState

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class EvidenceLineageBuilder:
    """Create an immutable item-to-source lineage manifest."""

    def build(
        self, records: Iterable[Mapping[str, Any]], *, context_key: str
    ) -> EvidenceLineageReport:
        context_key = require_non_empty(context_key, "context_key")
        entries: list[EvidenceLineageEntry] = []
        for index, raw in enumerate(records, start=1):
            row = _mapping(raw, label=f"lineage item {index}")
            item_id = _text(row.get("item_id", row.get("id")), field="item_id") or f"item:{index}"
            parents = _tuple_text(row.get("parent_ids", ()), field="parent_ids")
            sources = _tuple_text(
                row.get("source_addresses", row.get("sources", ())), field="source_addresses"
            )
            if not sources:
                raise ValidationError(f"{item_id} has no source addresses")
            if _context(row, context_key) != context_key:
                raise ValidationError(f"{item_id} context does not match lineage context")
            entries.append(
                EvidenceLineageEntry(
                    item_id, tuple(sorted(set(parents))), tuple(sorted(set(sources))), _address(row)
                )
            )
        known = {entry.item_id for entry in entries}
        roots = tuple(
            entry.item_id
            for entry in entries
            if not entry.parent_ids or not set(entry.parent_ids).intersection(known)
        )
        manifest = {"context_key": context_key, "entries": entries, "root_ids": roots}
        return EvidenceLineageReport(
            tuple(sorted(entries, key=lambda item: item.item_id)),
            roots,
            _address(manifest),
            FrontierState.PUBLISHED,
        )


@dataclass(frozen=True, slots=True)
class RenderedArtifact:
    artifact_id: str
    format: str
    mime_type: str
    content: str
    byte_count: int
    line_count: int
    content_address: str
    state: FrontierState

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ReportArtifactRenderer:
    """Render report rows into deterministic text artifacts with byte receipts."""

    def render(
        self,
        rows: Iterable[Mapping[str, Any]],
        *,
        artifact_id: str,
        format: str,
        columns: Sequence[str] = (),
    ) -> RenderedArtifact:
        artifact_id = require_non_empty(artifact_id, "artifact_id")
        format = require_non_empty(format, "format").lower()
        normalized = tuple(dict(_mapping(row, label="artifact row")) for row in rows)
        if format == "json":
            content = canonical_json(normalized) + "\n"
            mime = "application/json"
        elif format == "markdown":
            fields = tuple(columns or sorted({key for row in normalized for key in row}))
            content = (
                "| " + " | ".join(fields) + " |\n| " + " | ".join("---" for _ in fields) + " |\n"
            )
            content += "".join(
                "| " + " | ".join(str(row.get(field, "")) for field in fields) + " |\n"
                for row in normalized
            )
            mime = "text/markdown"
        elif format == "csv":
            fields = tuple(columns or sorted({key for row in normalized for key in row}))
            stream = io.StringIO()
            writer = csv.DictWriter(
                stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n"
            )
            writer.writeheader()
            writer.writerows(normalized)
            content = stream.getvalue()
            mime = "text/csv"
        else:
            raise ValidationError("format must be json, markdown, or csv")
        return RenderedArtifact(
            artifact_id,
            format,
            mime,
            content,
            len(content.encode("utf-8")),
            len(content.splitlines()),
            _address(content),
            FrontierState.PUBLISHED,
        )


@dataclass(frozen=True, slots=True)
class HumanFactorsEvent:
    event_id: str
    event_type: str
    target_id: str | None
    valid: bool
    issue: str | None

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class HumanFactorsScenarioReport:
    scenario_id: str
    events: tuple[HumanFactorsEvent, ...]
    completed: bool
    recovery_count: int
    state: FrontierState
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class HumanFactorsScenarioSimulator:
    """Simulate keyboard/focus/error-recovery sequences for a workbench surface."""

    _allowed = {"focus", "activate", "submit", "error", "recover", "escape", "navigate"}

    def simulate(
        self, events: Iterable[Mapping[str, Any]], *, scenario_id: str
    ) -> HumanFactorsScenarioReport:
        scenario_id = require_non_empty(scenario_id, "scenario_id")
        output: list[HumanFactorsEvent] = []
        focused: str | None = None
        recovering = False
        recovery_count = 0
        for index, raw in enumerate(events, start=1):
            row = _mapping(raw, label=f"human-factors event {index}")
            event_id = (
                _text(row.get("event_id", row.get("id")), field="event_id") or f"event:{index}"
            )
            kind = _text(row.get("event_type", row.get("type")), field="event_type").lower()
            target = _text(row.get("target_id"), field="target_id") or None
            valid = kind in self._allowed
            issue: str | None = None
            if not valid:
                issue = "unknown_event_type"
            elif kind in {"activate", "submit"} and focused is None:
                valid = False
                issue = "activation_without_focus"
            elif kind == "error":
                recovering = True
            elif kind == "recover":
                if not recovering:
                    valid = False
                    issue = "recovery_without_error"
                else:
                    recovering = False
                    recovery_count += 1
            elif kind == "focus":
                focused = target
            elif kind == "escape":
                focused = None
            output.append(HumanFactorsEvent(event_id, kind, target, valid, issue))
        completed = bool(output) and all(item.valid for item in output) and not recovering
        return HumanFactorsScenarioReport(
            scenario_id,
            tuple(output),
            completed,
            recovery_count,
            FrontierState.ACCEPTED if completed else FrontierState.REVIEW,
            _address(output),
        )


@dataclass(frozen=True, slots=True)
class SecurityPathFinding:
    path: str
    key: str
    category: str
    redacted_value_type: str
    severity: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SecurityPathReport:
    findings: tuple[SecurityPathFinding, ...]
    sensitive_path_count: int
    secret_path_count: int
    state: FrontierState
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class SecurityPathScanner:
    """Find sensitive and secret-like keys while never returning raw values."""

    def scan(
        self,
        payload: Mapping[str, Any],
        *,
        sensitive_keys: Sequence[str] = ("subject_id", "patient_id", "sample_id", "genotype"),
        secret_keys: Sequence[str] = ("password", "token", "secret", "api_key"),
    ) -> SecurityPathReport:
        sensitive = {item.lower() for item in sensitive_keys}
        secrets = {item.lower() for item in secret_keys}
        findings: list[SecurityPathFinding] = []

        def walk(value: Any, path: str) -> None:
            if isinstance(value, Mapping):
                for key, child in value.items():
                    key_text = str(key)
                    child_path = f"{path}.{key_text}" if path else key_text
                    lowered = key_text.lower()
                    if lowered in secrets or any(token in lowered for token in secrets):
                        findings.append(
                            SecurityPathFinding(
                                child_path, key_text, "secret", type(child).__name__, "blocking"
                            )
                        )
                    elif lowered in sensitive or any(token in lowered for token in sensitive):
                        findings.append(
                            SecurityPathFinding(
                                child_path, key_text, "sensitive", type(child).__name__, "review"
                            )
                        )
                    walk(child, child_path)
            elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
                for index, child in enumerate(value):
                    walk(child, f"{path}[{index}]")

        walk(payload, "")
        state = (
            FrontierState.ACCEPTED
            if not any(item.severity == "blocking" for item in findings)
            else FrontierState.REVIEW
        )
        return SecurityPathReport(
            tuple(findings),
            sum(item.category == "sensitive" for item in findings),
            sum(item.category == "secret" for item in findings),
            state,
            _address(findings),
        )


@dataclass(frozen=True, slots=True)
class DependencyResolution:
    service_id: str
    dependencies: tuple[str, ...]
    order: int | None
    state: FrontierState
    issue: str | None

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DependencyResolutionReport:
    resolutions: tuple[DependencyResolution, ...]
    execution_order: tuple[str, ...]
    missing_dependencies: tuple[str, ...]
    cycle_ids: tuple[str, ...]
    state: FrontierState
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class DeploymentDependencyResolver:
    """Resolve service dependencies and retain missing/cycle diagnostics."""

    def resolve(self, services: Iterable[Mapping[str, Any]]) -> DependencyResolutionReport:
        rows = tuple(_mapping(item, label="deployment service") for item in services)
        dependencies = {
            _required_text(row.get("service_id", row.get("id")), field="service_id"): _tuple_text(
                row.get("depends_on", row.get("dependencies", ())), field="dependencies"
            )
            for row in rows
        }
        missing = tuple(
            sorted(
                {
                    dependency
                    for values in dependencies.values()
                    for dependency in values
                    if dependency not in dependencies
                }
            )
        )
        order: list[str] = []
        visiting: set[str] = set()
        visited: set[str] = set()
        cycle: set[str] = set()

        def visit(service_id: str) -> None:
            if service_id in visiting:
                cycle.add(service_id)
                return
            if service_id in visited:
                return
            visiting.add(service_id)
            for dependency in dependencies[service_id]:
                if dependency in dependencies:
                    visit(dependency)
                    if dependency in cycle:
                        cycle.add(service_id)
            visiting.remove(service_id)
            visited.add(service_id)
            order.append(service_id)

        for service_id in sorted(dependencies):
            visit(service_id)
        resolutions = tuple(
            DependencyResolution(
                service_id,
                dependencies[service_id],
                order.index(service_id)
                if service_id in order and service_id not in cycle
                else None,
                FrontierState.ACCEPTED
                if service_id not in cycle
                and not any(dep in missing for dep in dependencies[service_id])
                else FrontierState.REVIEW,
                "cycle"
                if service_id in cycle
                else "missing_dependency"
                if any(dep in missing for dep in dependencies[service_id])
                else None,
            )
            for service_id in sorted(dependencies)
        )
        state = FrontierState.ACCEPTED if not missing and not cycle else FrontierState.REVIEW
        return DependencyResolutionReport(
            resolutions,
            tuple(item for item in order if item not in cycle),
            missing,
            tuple(sorted(cycle)),
            state,
            _address(resolutions),
        )


@dataclass(frozen=True, slots=True)
class PrivacyAccountEntry:
    request_id: str
    site_id: str
    epsilon: float
    delta: float
    cumulative_epsilon: float
    cumulative_delta: float
    allowed: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PrivacyAccountReport:
    entries: tuple[PrivacyAccountEntry, ...]
    total_epsilon: float
    total_delta: float
    allowed_ids: tuple[str, ...]
    denied_ids: tuple[str, ...]
    state: FrontierState
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class FederatedPrivacyAccountant:
    """Compose site-local epsilon/delta requests against declared budgets."""

    def account(
        self,
        requests: Iterable[Mapping[str, Any]],
        *,
        epsilon_budget: float,
        delta_budget: float,
        per_site_epsilon_budget: float | None = None,
    ) -> PrivacyAccountReport:
        epsilon_budget = _float(epsilon_budget, field="epsilon_budget")
        delta_budget = _float(delta_budget, field="delta_budget")
        per_site_budget = (
            epsilon_budget
            if per_site_epsilon_budget is None
            else _float(per_site_epsilon_budget, field="per_site_epsilon_budget")
        )
        total_epsilon = 0.0
        total_delta = 0.0
        site_totals: dict[str, float] = {}
        entries: list[PrivacyAccountEntry] = []
        for index, raw in enumerate(requests, start=1):
            row = _mapping(raw, label=f"privacy request {index}")
            request_id = (
                _text(row.get("request_id", row.get("id")), field="request_id")
                or f"request:{index}"
            )
            site_id = _required_text(row.get("site_id"), field="site_id")
            epsilon = _float(row.get("epsilon", 0.0), field="epsilon")
            delta = _float(row.get("delta", 0.0), field="delta")
            proposed_epsilon = total_epsilon + epsilon
            proposed_delta = total_delta + delta
            site_epsilon = site_totals.get(site_id, 0.0) + epsilon
            allowed = (
                proposed_epsilon <= epsilon_budget
                and proposed_delta <= delta_budget
                and site_epsilon <= per_site_budget
            )
            reason = "within_composed_budgets" if allowed else "privacy_budget_exceeded"
            if allowed:
                total_epsilon = proposed_epsilon
                total_delta = proposed_delta
                site_totals[site_id] = site_epsilon
            entries.append(
                PrivacyAccountEntry(
                    request_id,
                    site_id,
                    epsilon,
                    delta,
                    round(total_epsilon, 6),
                    round(total_delta, 6),
                    allowed,
                    reason,
                )
            )
        allowed_ids = tuple(item.request_id for item in entries if item.allowed)
        denied_ids = tuple(item.request_id for item in entries if not item.allowed)
        return PrivacyAccountReport(
            tuple(entries),
            round(total_epsilon, 6),
            round(total_delta, 6),
            allowed_ids,
            denied_ids,
            FrontierState.ACCEPTED if not denied_ids else FrontierState.REVIEW,
            _address(entries),
        )


@dataclass(frozen=True, slots=True)
class ReleaseHistoryEntry:
    sequence: int
    release_id: str
    version: str
    action: str
    result: str
    predecessor_address: str | None
    entry_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReleaseHistoryReport:
    entries: tuple[ReleaseHistoryEntry, ...]
    current_version: str | None
    valid_chain: bool
    state: FrontierState
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ReleaseHistoryLedger:
    """Maintain an append-only release history with predecessor hashes."""

    def append(
        self,
        history: Iterable[Mapping[str, Any]],
        *,
        release_id: str,
        version: str,
        action: str,
        result: str,
    ) -> ReleaseHistoryReport:
        release_id = require_non_empty(release_id, "release_id")
        version = require_non_empty(version, "version")
        action = require_non_empty(action, "action")
        result = require_non_empty(result, "result")
        entries: list[ReleaseHistoryEntry] = []
        expected_sequence = 1
        predecessor: str | None = None
        valid = True
        for raw in history:
            row = _mapping(raw, label="release history")
            sequence = int(row.get("sequence", expected_sequence))
            raw_address = _text(row.get("entry_address"), field="entry_address") or None
            item = ReleaseHistoryEntry(
                sequence,
                _required_text(row.get("release_id"), field="release_id"),
                _required_text(row.get("version"), field="version"),
                _required_text(row.get("action"), field="action"),
                _required_text(row.get("result"), field="result"),
                _text(row.get("predecessor_address"), field="predecessor_address") or None,
                raw_address or _address(row),
            )
            if sequence != expected_sequence or item.predecessor_address != predecessor:
                valid = False
            predecessor = item.entry_address
            expected_sequence += 1
            entries.append(item)
        new = ReleaseHistoryEntry(
            expected_sequence,
            release_id,
            version,
            action,
            result,
            predecessor,
            _address(
                {
                    "sequence": expected_sequence,
                    "release_id": release_id,
                    "version": version,
                    "action": action,
                    "result": result,
                    "predecessor_address": predecessor,
                }
            ),
        )
        entries.append(new)
        return ReleaseHistoryReport(
            tuple(entries),
            version,
            valid,
            FrontierState.ACCEPTED if valid else FrontierState.REVIEW,
            _address(entries),
        )


def run_hardening_operation(
    operation: str, payload: Mapping[str, Any], *, context_key: str | None = None
) -> Any:
    """Run a hardening operation from a JSON payload."""

    operation = require_non_empty(operation, "operation")
    data = _mapping(payload, label="payload")
    context = context_key or _text(data.get("context_key"), field="context_key")
    if operation == "audit-off-target-alignments":
        return OffTargetAlignmentAuditor().audit(
            data.get("records", ()),
            context_key=context,
            maximum_mismatches=int(data.get("maximum_mismatches", 3)),
            risk_threshold=_float(data.get("risk_threshold", 0.35), field="risk_threshold"),
        )
    if operation == "check-validation-readiness":
        return ValidationExecutionReadinessChecker().evaluate(
            data.get("package", data),
            package_id=_required_text(data.get("package_id"), field="package_id"),
            context_key=context,
            required_controls=_tuple_text(
                data.get("required_controls", ()), field="required_controls"
            ),
            required_outputs=_tuple_text(
                data.get("required_outputs", ()), field="required_outputs"
            ),
        )
    if operation == "audit-evidence-graph-integrity":
        return EvidenceGraphIntegrityAuditor().audit(
            data.get("nodes", ()), data.get("edges", ()), context_key=context
        )
    if operation == "build-evidence-lineage":
        return EvidenceLineageBuilder().build(data.get("records", ()), context_key=context)
    if operation == "render-report-artifact":
        return ReportArtifactRenderer().render(
            data.get("rows", ()),
            artifact_id=_required_text(data.get("artifact_id"), field="artifact_id"),
            format=_required_text(data.get("format"), field="format"),
            columns=_tuple_text(data.get("columns", ()), field="columns"),
        )
    if operation == "simulate-human-factors":
        return HumanFactorsScenarioSimulator().simulate(
            data.get("events", ()),
            scenario_id=_required_text(data.get("scenario_id"), field="scenario_id"),
        )
    if operation == "scan-security-paths":
        return SecurityPathScanner().scan(
            data.get("payload", data),
            sensitive_keys=_tuple_text(
                data.get("sensitive_keys", ("subject_id", "patient_id", "sample_id", "genotype")),
                field="sensitive_keys",
            ),
            secret_keys=_tuple_text(
                data.get("secret_keys", ("password", "token", "secret", "api_key")),
                field="secret_keys",
            ),
        )
    if operation == "resolve-deployment-dependencies":
        return DeploymentDependencyResolver().resolve(data.get("services", ()))
    if operation == "account-federated-privacy":
        return FederatedPrivacyAccountant().account(
            data.get("requests", ()),
            epsilon_budget=_float(data.get("epsilon_budget"), field="epsilon_budget"),
            delta_budget=_float(data.get("delta_budget"), field="delta_budget"),
            per_site_epsilon_budget=_float(
                data["per_site_epsilon_budget"], field="per_site_epsilon_budget"
            )
            if data.get("per_site_epsilon_budget") is not None
            else None,
        )
    if operation == "append-release-history":
        return ReleaseHistoryLedger().append(
            data.get("history", ()),
            release_id=_required_text(data.get("release_id"), field="release_id"),
            version=_required_text(data.get("version"), field="version"),
            action=_required_text(data.get("action"), field="action"),
            result=_required_text(data.get("result"), field="result"),
        )
    raise ValidationError(f"unknown hardening operation: {operation}")


HARDENING_OPERATIONS = (
    "audit-off-target-alignments",
    "check-validation-readiness",
    "audit-evidence-graph-integrity",
    "build-evidence-lineage",
    "render-report-artifact",
    "simulate-human-factors",
    "scan-security-paths",
    "resolve-deployment-dependencies",
    "account-federated-privacy",
    "append-release-history",
)
