"""Static comparison and reverse-dependency impact propagation for inventories."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .module_impact_contracts import (
    ImpactChangeKind,
    ImpactPropagation,
    ImpactSeverity,
    ModuleDependencyChange,
    ModuleImpactAssessment,
    ModuleImpactChange,
    ModuleImpactDiff,
    ModuleImpactReport,
)
from .module_inventory_contracts import (
    ModuleDependency,
    ModuleInventory,
    ModuleRecord,
    ModuleSymbol,
)
from .module_inventory_query import inventory_from_mapping
from .serialization import canonical_json, content_hash, jsonable

_SUMMARY_FIELDS = (
    "module_count",
    "parsed_module_count",
    "domain_count",
    "total_physical_lines",
    "total_nonblank_lines",
    "total_public_symbols",
    "symbol_count",
    "dependency_count",
    "issue_count",
)
_SEVERITY_SCORE = {
    ImpactSeverity.NONE: 0.0,
    ImpactSeverity.LOW: 25.0,
    ImpactSeverity.MODERATE: 50.0,
    ImpactSeverity.HIGH: 75.0,
    ImpactSeverity.CRITICAL: 100.0,
}


def _as_inventory(value: ModuleInventory | Mapping[str, Any]) -> ModuleInventory:
    if isinstance(value, ModuleInventory):
        return value
    if isinstance(value, Mapping):
        return inventory_from_mapping(value)
    raise ValidationError("module impact input must be an inventory")


def _address(value: Mapping[str, Any], prefix: str) -> str:
    return content_hash(value, prefix=prefix)


def _symbol_signature(item: ModuleSymbol) -> tuple[Any, ...]:
    return (item.kind, item.line, item.end_line, item.public)


def _dependency_signature(item: ModuleDependency) -> tuple[Any, ...]:
    return (item.source_module, item.target_module, item.import_name, item.relative, item.resolved)


def _dependency_key(item: ModuleDependency) -> str:
    return f"{item.source_module}|{item.target_module}|{item.import_name}"


def _change_severity(
    kind: ImpactChangeKind,
    removed_symbols: tuple[str, ...],
    changed_symbols: tuple[str, ...],
    added_dependencies: tuple[str, ...],
    removed_dependencies: tuple[str, ...],
    test_reference_delta: int,
) -> ImpactSeverity:
    if kind is ImpactChangeKind.REMOVED:
        return ImpactSeverity.CRITICAL
    if kind is ImpactChangeKind.ADDED:
        return ImpactSeverity.LOW
    if removed_symbols:
        return ImpactSeverity.CRITICAL
    if removed_dependencies:
        return ImpactSeverity.HIGH
    if added_dependencies or changed_symbols:
        return ImpactSeverity.HIGH
    if test_reference_delta < 0:
        return ImpactSeverity.MODERATE
    return ImpactSeverity.MODERATE


def _module_change(
    module_id: str,
    left: ModuleRecord | None,
    right: ModuleRecord | None,
    left_symbols: Mapping[str, ModuleSymbol],
    right_symbols: Mapping[str, ModuleSymbol],
    left_dependencies: Mapping[str, ModuleDependency],
    right_dependencies: Mapping[str, ModuleDependency],
) -> ModuleImpactChange:
    if left is None:
        kind = ImpactChangeKind.ADDED
    elif right is None:
        kind = ImpactChangeKind.REMOVED
    elif (
        left.content_address == right.content_address and left.source_digest == right.source_digest
    ):
        kind = ImpactChangeKind.UNCHANGED
    else:
        kind = ImpactChangeKind.CHANGED
    if left is None or right is None:
        added_symbols = tuple(sorted(right_symbols)) if right is not None else ()
        removed_symbols = tuple(sorted(left_symbols)) if left is not None else ()
        changed_symbols: tuple[str, ...] = ()
        added_dependencies = tuple(sorted(right_dependencies)) if right is not None else ()
        removed_dependencies = tuple(sorted(left_dependencies)) if left is not None else ()
        physical_delta = right.physical_lines if right is not None else -left.physical_lines
        nonblank_delta = right.nonblank_lines if right is not None else -left.nonblank_lines
        public_symbol_delta = (
            right.public_symbol_count if right is not None else -left.public_symbol_count
        )
        import_delta = right.import_count if right is not None else -left.import_count
        test_reference_delta = (
            right.test_reference_count if right is not None else -left.test_reference_count
        )
    else:
        added_symbols = tuple(sorted(set(right_symbols) - set(left_symbols)))
        removed_symbols = tuple(sorted(set(left_symbols) - set(right_symbols)))
        changed_symbols = tuple(
            sorted(
                name
                for name in set(left_symbols) & set(right_symbols)
                if _symbol_signature(left_symbols[name]) != _symbol_signature(right_symbols[name])
            )
        )
        added_dependencies = tuple(sorted(set(right_dependencies) - set(left_dependencies)))
        removed_dependencies = tuple(sorted(set(left_dependencies) - set(right_dependencies)))
        physical_delta = right.physical_lines - left.physical_lines
        nonblank_delta = right.nonblank_lines - left.nonblank_lines
        public_symbol_delta = right.public_symbol_count - left.public_symbol_count
        import_delta = right.import_count - left.import_count
        test_reference_delta = right.test_reference_count - left.test_reference_count
    body = {
        "module_id": module_id,
        "kind": kind,
        "left_address": left.content_address if left is not None else None,
        "right_address": right.content_address if right is not None else None,
        "physical_delta": physical_delta,
        "nonblank_delta": nonblank_delta,
        "public_symbol_delta": public_symbol_delta,
        "import_delta": import_delta,
        "test_reference_delta": test_reference_delta,
        "added_symbols": added_symbols,
        "removed_symbols": removed_symbols,
        "changed_symbols": changed_symbols,
        "added_dependencies": added_dependencies,
        "removed_dependencies": removed_dependencies,
        "severity": _change_severity(
            kind,
            removed_symbols,
            changed_symbols,
            added_dependencies,
            removed_dependencies,
            test_reference_delta,
        ),
    }
    return ModuleImpactChange(**body, content_address=_address(body, "module-impact-change"))


def _dependency_changes(
    left: tuple[ModuleDependency, ...], right: tuple[ModuleDependency, ...]
) -> tuple[ModuleDependencyChange, ...]:
    left_by_key = {_dependency_key(item): item for item in left}
    right_by_key = {_dependency_key(item): item for item in right}
    rows: list[ModuleDependencyChange] = []
    for key in sorted(set(left_by_key) | set(right_by_key)):
        old = left_by_key.get(key)
        new = right_by_key.get(key)
        if old is not None and new is not None:
            if _dependency_signature(old) == _dependency_signature(new):
                continue
            kind = ImpactChangeKind.CHANGED
            selected = new
        elif new is not None:
            kind = ImpactChangeKind.ADDED
            selected = new
        else:
            kind = ImpactChangeKind.REMOVED
            selected = old
        body = {
            "source_module": selected.source_module,
            "target_module": selected.target_module,
            "import_name": selected.import_name,
            "kind": kind,
            "relative": selected.relative,
            "left_resolved": old.resolved if old is not None else None,
            "right_resolved": new.resolved if new is not None else None,
        }
        rows.append(
            ModuleDependencyChange(
                **body, content_address=_address(body, "module-impact-dependency-change")
            )
        )
    return tuple(rows)


def build_module_impact_diff(
    left: ModuleInventory | Mapping[str, Any],
    right: ModuleInventory | Mapping[str, Any],
) -> ModuleImpactDiff:
    """Compare two inventories without reading source files or importing modules."""

    old = _as_inventory(left)
    new = _as_inventory(right)
    left_modules = {item.module_id: item for item in old.modules}
    right_modules = {item.module_id: item for item in new.modules}
    left_symbols = defaultdict(dict)
    right_symbols = defaultdict(dict)
    for item in old.symbols:
        left_symbols[item.module_id][item.name] = item
    for item in new.symbols:
        right_symbols[item.module_id][item.name] = item
    left_dependencies = defaultdict(dict)
    right_dependencies = defaultdict(dict)
    for item in old.dependencies:
        left_dependencies[item.source_module][_dependency_key(item)] = item
    for item in new.dependencies:
        right_dependencies[item.source_module][_dependency_key(item)] = item
    changes = tuple(
        _module_change(
            module_id,
            left_modules.get(module_id),
            right_modules.get(module_id),
            left_symbols.get(module_id, {}),
            right_symbols.get(module_id, {}),
            left_dependencies.get(module_id, {}),
            right_dependencies.get(module_id, {}),
        )
        for module_id in sorted(set(left_modules) | set(right_modules))
    )
    dependency_changes = _dependency_changes(old.dependencies, new.dependencies)
    left_summary = old.summary()
    right_summary = new.summary()
    summary_delta = {
        field: int(right_summary.get(field, 0)) - int(left_summary.get(field, 0))
        for field in _SUMMARY_FIELDS
        if right_summary.get(field, 0) != left_summary.get(field, 0)
    }
    body = {
        "left_inventory_address": old.content_address,
        "right_inventory_address": new.content_address,
        "changes": changes,
        "dependencies": dependency_changes,
        "changed_summary_fields": tuple(sorted(summary_delta)),
        "summary_delta": summary_delta,
        "accepted": old.accepted and new.accepted,
    }
    return ModuleImpactDiff(**body, content_address=_address(body, "module-impact-diff"))


def _reverse_edges(*inventories: ModuleInventory) -> dict[str, tuple[str, ...]]:
    known = {item.module_id for inventory in inventories for item in inventory.modules}
    reverse: dict[str, set[str]] = defaultdict(set)
    for inventory in inventories:
        for edge in inventory.dependencies:
            if edge.target_module in known and edge.source_module in known:
                reverse[edge.target_module].add(edge.source_module)
    return {key: tuple(sorted(value)) for key, value in reverse.items()}


def _severity_for_distance(severity: ImpactSeverity, distance: int) -> ImpactSeverity:
    if distance <= 0:
        return severity
    if severity is ImpactSeverity.CRITICAL:
        return ImpactSeverity.HIGH if distance == 1 else ImpactSeverity.MODERATE
    if severity is ImpactSeverity.HIGH:
        return ImpactSeverity.HIGH if distance == 1 else ImpactSeverity.MODERATE
    if severity is ImpactSeverity.MODERATE:
        return ImpactSeverity.MODERATE if distance == 1 else ImpactSeverity.LOW
    if severity is ImpactSeverity.LOW:
        return ImpactSeverity.LOW
    return ImpactSeverity.NONE


def _risk(severity: ImpactSeverity, distance: int) -> float:
    return round(_SEVERITY_SCORE[severity] / (1.0 + max(0, distance) * 0.2), 2)


def _reasons(
    change: ModuleImpactChange | None,
    distance: int,
    sources: tuple[str, ...],
) -> tuple[str, ...]:
    reasons: set[str] = set()
    if change is not None:
        reasons.add(f"direct {change.kind.value} module")
        if change.removed_symbols:
            reasons.add("public or private symbols removed")
        if change.changed_symbols:
            reasons.add("symbols moved or changed shape")
        if change.added_dependencies:
            reasons.add("dependency edges added")
        if change.removed_dependencies:
            reasons.add("dependency edges removed")
        if change.test_reference_delta < 0:
            reasons.add("test references decreased")
    if distance:
        reasons.add(f"reverse dependency distance {distance}")
        reasons.add("changed source: " + ", ".join(sources))
    return tuple(sorted(reasons))


def build_module_impact_report(
    left: ModuleInventory | Mapping[str, Any],
    right: ModuleInventory | Mapping[str, Any],
    diff: ModuleImpactDiff | Mapping[str, Any] | None = None,
) -> ModuleImpactReport:
    """Propagate direct module changes through both snapshots' reverse graphs."""

    old = _as_inventory(left)
    new = _as_inventory(right)
    selected_diff = (
        diff if isinstance(diff, ModuleImpactDiff) else build_module_impact_diff(old, new)
    )
    if not isinstance(selected_diff, ModuleImpactDiff):
        raise ValidationError("module impact report requires a typed diff")
    changes = {item.module_id: item for item in selected_diff.changes}
    direct = {
        item.module_id
        for item in selected_diff.changes
        if item.kind is not ImpactChangeKind.UNCHANGED
    }
    reverse = _reverse_edges(old, new)
    paths_by_module: dict[str, list[tuple[int, str, str]]] = defaultdict(list)
    for seed in sorted(direct):
        queue: deque[tuple[str, int, str]] = deque([(seed, 0, seed)])
        visited = {seed: 0}
        while queue:
            current, distance, path = queue.popleft()
            if distance:
                paths_by_module[current].append((distance, seed, path))
            for dependent in reverse.get(current, ()):
                next_distance = distance + 1
                if next_distance < visited.get(dependent, 10**9):
                    visited[dependent] = next_distance
                    queue.append((dependent, next_distance, f"{path}->{dependent}"))
    assessments: list[ModuleImpactAssessment] = []
    for module_id in sorted(direct | set(paths_by_module)):
        change = changes.get(module_id)
        if module_id in direct:
            severity = change.severity if change is not None else ImpactSeverity.MODERATE
            sources = (module_id,)
            paths = (module_id,)
            distance = 0
            propagation = ImpactPropagation.DIRECT
        else:
            selected_paths = paths_by_module[module_id]
            distance = min(item[0] for item in selected_paths)
            sources = tuple(sorted({item[1] for item in selected_paths}))
            paths = tuple(sorted(item[2] for item in selected_paths if item[0] == distance))
            seed_severities = [changes[source].severity for source in sources if source in changes]
            seed_severity = max(seed_severities, key=lambda item: _SEVERITY_SCORE[item])
            severity = _severity_for_distance(seed_severity, distance)
            propagation = (
                ImpactPropagation.DEPENDENT if distance == 1 else ImpactPropagation.TRANSITIVE
            )
        reasons = _reasons(change, distance, sources)
        body = {
            "module_id": module_id,
            "propagation": propagation,
            "distance": distance,
            "severity": severity,
            "risk_score": _risk(severity, distance),
            "direct_change_kind": change.kind if change is not None else None,
            "changed_sources": sources,
            "paths": paths,
            "reasons": reasons,
        }
        assessments.append(
            ModuleImpactAssessment(
                **body, content_address=_address(body, "module-impact-assessment")
            )
        )
    assessments_tuple = tuple(sorted(assessments, key=lambda item: item.module_id))
    body = {
        "diff_address": selected_diff.content_address,
        "assessments": assessments_tuple,
        "direct_count": sum(
            item.propagation is ImpactPropagation.DIRECT for item in assessments_tuple
        ),
        "dependent_count": sum(
            item.propagation is ImpactPropagation.DEPENDENT for item in assessments_tuple
        ),
        "transitive_count": sum(
            item.propagation is ImpactPropagation.TRANSITIVE for item in assessments_tuple
        ),
        "critical_count": sum(
            item.severity is ImpactSeverity.CRITICAL for item in assessments_tuple
        ),
        "high_count": sum(item.severity is ImpactSeverity.HIGH for item in assessments_tuple),
        "accepted": selected_diff.accepted,
    }
    return ModuleImpactReport(**body, content_address=_address(body, "module-impact-report"))


def verify_module_impact_diff(value: ModuleImpactDiff) -> ModuleImpactDiff:
    """Verify row addresses and ordering without accessing source files."""

    if not isinstance(value, ModuleImpactDiff):
        raise ValidationError("module impact verification requires a typed diff")
    for row in value.changes:
        body = {
            key: jsonable(item) for key, item in row.to_dict().items() if key != "content_address"
        }
        if _address(body, "module-impact-change") != row.content_address:
            raise ValidationError(f"module impact change address mismatch: {row.module_id}")
    for row in value.dependencies:
        body = {
            key: jsonable(item) for key, item in row.to_dict().items() if key != "content_address"
        }
        if _address(body, "module-impact-dependency-change") != row.content_address:
            raise ValidationError(f"module impact dependency address mismatch: {row.key}")
    return value


def module_impact_json(value: ModuleImpactDiff | ModuleImpactReport) -> str:
    """Return canonical newline-terminated JSON for a diff or report."""

    return canonical_json(value.to_dict()) + "\n"


__all__ = [
    "build_module_impact_diff",
    "build_module_impact_report",
    "module_impact_json",
    "verify_module_impact_diff",
]
