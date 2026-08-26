"""Static source-to-evidence lineage for module certification.

This module adds explainability to the certification matrix without executing
package code.  It reads source, test, and Markdown bytes once, records only
relative paths plus digests and line counts, and links those records to the
module and dependency identities already present in the inventory.
"""

from __future__ import annotations

import ast
import csv
import io
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_certification import build_module_certification
from .module_certification_contracts import ModuleCertificationMatrix
from .module_certification_lineage_contracts import (
    MODULE_CERTIFICATION_LINEAGE_BOUNDARY,
    MODULE_CERTIFICATION_LINEAGE_DEFAULT_LIMIT,
    MODULE_CERTIFICATION_LINEAGE_MAX_EDGES,
    MODULE_CERTIFICATION_LINEAGE_MAX_EVIDENCE,
    MODULE_CERTIFICATION_LINEAGE_MAX_LIMIT,
    MODULE_CERTIFICATION_LINEAGE_VERSION,
    CertificationEvidenceKind,
    CertificationLineageRelation,
    CertificationLineageTargetKind,
    ModuleCertificationEvidence,
    ModuleCertificationLineage,
    ModuleCertificationLineageEdge,
    address_module_certification_evidence,
    address_module_certification_lineage_edge,
)
from .module_inventory_contracts import ModuleInventory
from .module_inventory_query import inventory_from_mapping
from .serialization import canonical_json, content_hash, hash_bytes, jsonable

_PACKAGE_REFERENCE = re.compile(r"\bglio_noncode(?:\.[A-Za-z_][A-Za-z0-9_]*)+")
_PYTHON_FILE_REFERENCE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\.py\b")
_FORBIDDEN_KEYS = frozenset(
    {
        "agent",
        "agent_id",
        "assistant",
        "author",
        "email",
        "language",
        "model",
        "patient",
        "subject",
    }
)


@dataclass(frozen=True, slots=True)
class _FileSnapshot:
    """Private one-read representation used while constructing the graph."""

    relative_path: str
    payload: bytes
    text: str
    line_count: int
    digest: str


def _inventory(value: ModuleInventory | Mapping[str, Any]) -> ModuleInventory:
    if isinstance(value, ModuleInventory):
        return value
    if isinstance(value, Mapping):
        return inventory_from_mapping(value)
    raise ValidationError("module certification lineage requires a typed inventory")


def _source_root(source_root: str | Path | None) -> Path:
    return Path(source_root) if source_root is not None else Path(__file__).resolve().parent


def _roots(
    source_root: str | Path | None,
    test_root: str | Path | None,
    docs_root: str | Path | None,
) -> tuple[Path, Path, Path]:
    source = _source_root(source_root)
    tests = Path(test_root) if test_root is not None else source.parent.parent / "tests"
    docs = Path(docs_root) if docs_root is not None else source.parent.parent / "docs"
    return source, tests, docs


def _line_count(payload: bytes) -> int:
    if not payload:
        return 0
    return payload.count(b"\n") + (0 if payload.endswith(b"\n") else 1)


def _snapshots(root: Path, suffixes: frozenset[str]) -> tuple[_FileSnapshot, ...]:
    """Read eligible files once, preserving safe root-relative coordinates."""

    if not root.exists() or not root.is_dir():
        return ()
    rows: list[_FileSnapshot] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().casefold()):
        if path.is_symlink() or not path.is_file() or path.suffix.casefold() not in suffixes:
            continue
        try:
            payload = path.read_bytes()
        except OSError:
            continue
        relative = path.relative_to(root).as_posix()
        text = payload.decode("utf-8", errors="ignore")
        rows.append(
            _FileSnapshot(
                relative_path=relative,
                payload=payload,
                text=text,
                line_count=_line_count(payload),
                digest=hash_bytes(payload),
            )
        )
    return tuple(rows)


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(body, prefix=prefix)


def _evidence(
    *,
    evidence_id: str,
    module_id: str,
    kind: CertificationEvidenceKind,
    relative_path: str,
    relation: CertificationLineageRelation,
    detail: str,
    source_digest: str,
    line_count: int,
) -> ModuleCertificationEvidence:
    body = {
        "evidence_id": evidence_id,
        "module_id": module_id,
        "kind": kind,
        "relative_path": relative_path,
        "relation": relation,
        "detail": detail,
        "source_digest": source_digest,
        "line_count": line_count,
    }
    return ModuleCertificationEvidence(
        **body,
        content_address=_address(body, "module-certification-evidence"),
    )


def _edge(
    *,
    source_module: str,
    target_kind: CertificationLineageTargetKind,
    target_id: str,
    relation: CertificationLineageRelation,
    resolved: bool,
    evidence_ids: tuple[str, ...],
) -> ModuleCertificationLineageEdge:
    body = {
        "source_module": source_module,
        "target_kind": target_kind,
        "target_id": target_id,
        "relation": relation,
        "resolved": resolved,
        "evidence_ids": tuple(sorted(set(evidence_ids))),
    }
    return ModuleCertificationLineageEdge(
        **body,
        content_address=_address(body, "module-certification-lineage-edge"),
    )


def _module_references(
    snapshots: tuple[_FileSnapshot, ...],
    module_ids: set[str],
) -> dict[str, tuple[_FileSnapshot, ...]]:
    """Build a reverse index for explicit package and source-file references."""

    by_module: dict[str, list[_FileSnapshot]] = {module_id: [] for module_id in module_ids}
    by_filename: dict[str, set[str]] = {}
    for module_id in module_ids:
        name = module_id.rsplit(".", 1)[-1]
        by_filename.setdefault(f"{name}.py", set()).add(module_id)
    for snapshot in snapshots:
        references = set(_PACKAGE_REFERENCE.findall(snapshot.text)) & module_ids
        for filename in _PYTHON_FILE_REFERENCE.findall(snapshot.text):
            references.update(by_filename.get(filename, set()))
        for module_id in sorted(references):
            by_module[module_id].append(snapshot)
    return {key: tuple(value) for key, value in by_module.items()}


def _export_references(source: Path, package: str = "glio_noncode") -> set[str]:
    """Extract package export targets with AST only; no import is performed."""

    init_path = source / "__init__.py"
    try:
        tree = ast.parse(init_path.read_text(encoding="utf-8"), filename="__init__.py")
    except (OSError, UnicodeDecodeError, SyntaxError):
        return set()
    values: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == package or alias.name.startswith(f"{package}."):
                    values.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                base = package
                if module:
                    base = f"{package}.{module}"
                for alias in node.names:
                    if alias.name != "*":
                        values.add(f"{base}.{alias.name}")
            elif module == package or module.startswith(f"{package}."):
                values.add(module)
    return values


def _source_evidence(
    inventory: ModuleInventory,
) -> tuple[dict[str, ModuleCertificationEvidence], list[ModuleCertificationEvidence]]:
    by_module: dict[str, ModuleCertificationEvidence] = {}
    rows: list[ModuleCertificationEvidence] = []
    for module in inventory.modules:
        evidence = _evidence(
            evidence_id=f"source:{module.module_id}",
            module_id=module.module_id,
            kind=CertificationEvidenceKind.SOURCE,
            relative_path=module.relative_path,
            relation=CertificationLineageRelation.SUPPORTS,
            detail=(
                f"inventory source row; {module.physical_lines} physical lines, "
                f"{module.public_symbol_count} public symbols"
            ),
            source_digest=module.source_digest,
            line_count=module.physical_lines,
        )
        by_module[module.module_id] = evidence
        rows.append(evidence)
    return by_module, rows


def _reference_evidence(
    *,
    kind: CertificationEvidenceKind,
    relation: CertificationLineageRelation,
    references: dict[str, tuple[_FileSnapshot, ...]],
) -> list[ModuleCertificationEvidence]:
    rows: list[ModuleCertificationEvidence] = []
    for module_id in sorted(references):
        for snapshot in references[module_id]:
            evidence = _evidence(
                evidence_id=f"{kind.value}:{module_id}:{snapshot.relative_path}",
                module_id=module_id,
                kind=kind,
                relative_path=snapshot.relative_path,
                relation=relation,
                detail=f"static reference found in {snapshot.relative_path}",
                source_digest=snapshot.digest,
                line_count=snapshot.line_count,
            )
            rows.append(evidence)
    return rows


def _export_evidence(
    inventory: ModuleInventory,
    source: Path,
    exports: set[str],
) -> list[ModuleCertificationEvidence]:
    rows: list[ModuleCertificationEvidence] = []
    try:
        init_payload = (source / "__init__.py").read_bytes()
        init_digest = hash_bytes(init_payload)
        init_lines = _line_count(init_payload)
    except OSError:
        return rows
    for module in inventory.modules:
        if module.module_id not in exports and not module.relative_path.endswith("__init__.py"):
            continue
        rows.append(
            _evidence(
                evidence_id=f"export:{module.module_id}:__init__.py",
                module_id=module.module_id,
                kind=CertificationEvidenceKind.EXPORT,
                relative_path="__init__.py",
                relation=CertificationLineageRelation.EXPORTS,
                detail="package export AST contains or represents the module surface",
                source_digest=init_digest,
                line_count=init_lines,
            )
        )
    return rows


def _module_edges(
    inventory: ModuleInventory,
    source_evidence: Mapping[str, ModuleCertificationEvidence],
) -> list[ModuleCertificationLineageEdge]:
    known = {item.module_id for item in inventory.modules}
    rows: list[ModuleCertificationLineageEdge] = []
    for dependency in inventory.dependencies:
        evidence_ids = [source_evidence[dependency.source_module].evidence_id]
        if dependency.target_module in source_evidence:
            evidence_ids.append(source_evidence[dependency.target_module].evidence_id)
        rows.append(
            _edge(
                source_module=dependency.source_module,
                target_kind=CertificationLineageTargetKind.MODULE,
                target_id=dependency.target_module,
                relation=CertificationLineageRelation.DEPENDS_ON,
                resolved=dependency.resolved and dependency.target_module in known,
                evidence_ids=tuple(evidence_ids),
            )
        )
    return rows


def _evidence_edges(
    evidence: tuple[ModuleCertificationEvidence, ...],
) -> list[ModuleCertificationLineageEdge]:
    rows: list[ModuleCertificationLineageEdge] = []
    for item in evidence:
        relation = item.relation
        rows.append(
            _edge(
                source_module=item.module_id,
                target_kind=CertificationLineageTargetKind.EVIDENCE,
                target_id=item.evidence_id,
                relation=relation,
                resolved=True,
                evidence_ids=(item.evidence_id,),
            )
        )
    return rows


def build_module_certification_lineage(
    value: ModuleInventory | Mapping[str, Any],
    *,
    matrix: ModuleCertificationMatrix | None = None,
    source_root: str | Path | None = None,
    test_root: str | Path | None = None,
    docs_root: str | Path | None = None,
) -> ModuleCertificationLineage:
    """Build source, test, documentation, export, and dependency lineage."""

    inventory = _inventory(value)
    selected_matrix = matrix or build_module_certification(
        inventory, source_root=source_root, test_root=test_root, docs_root=docs_root
    )
    if not isinstance(selected_matrix, ModuleCertificationMatrix):
        raise ValidationError("module certification lineage matrix is invalid")
    source, tests, docs = _roots(source_root, test_root, docs_root)
    test_snapshots = _snapshots(tests, frozenset({".py"}))
    doc_snapshots = _snapshots(docs, frozenset({".md", ".markdown"}))
    module_ids = {item.module_id for item in inventory.modules}
    source_by_module, source_rows = _source_evidence(inventory)
    test_refs = _module_references(test_snapshots, module_ids)
    doc_refs = _module_references(doc_snapshots, module_ids)
    evidence_rows = source_rows
    evidence_rows.extend(
        _reference_evidence(
            kind=CertificationEvidenceKind.TEST,
            relation=CertificationLineageRelation.SUPPORTS,
            references=test_refs,
        )
    )
    evidence_rows.extend(
        _reference_evidence(
            kind=CertificationEvidenceKind.DOCUMENTATION,
            relation=CertificationLineageRelation.SUPPORTS,
            references=doc_refs,
        )
    )
    evidence_rows.extend(_export_evidence(inventory, source, _export_references(source)))
    evidence = tuple(sorted(evidence_rows, key=lambda item: item.evidence_id))
    if len(evidence) > MODULE_CERTIFICATION_LINEAGE_MAX_EVIDENCE:
        raise ValidationError("module certification lineage evidence limit exceeded")
    edges = tuple(
        sorted(
            _evidence_edges(evidence) + _module_edges(inventory, source_by_module),
            key=lambda item: (
                item.source_module,
                item.target_kind.value,
                item.target_id,
                item.relation.value,
            ),
        )
    )
    if len(edges) > MODULE_CERTIFICATION_LINEAGE_MAX_EDGES:
        raise ValidationError("module certification lineage edge limit exceeded")
    covered = {
        kind.value: len({item.module_id for item in evidence if item.kind is kind})
        for kind in CertificationEvidenceKind
    }
    relation_counts = {
        relation.value: sum(item.relation is relation for item in edges)
        for relation in CertificationLineageRelation
    }
    body = {
        "inventory_address": inventory.content_address,
        "matrix_address": selected_matrix.content_address,
        "evidence": evidence,
        "edges": edges,
        "module_count": inventory.module_count,
        "evidence_count": len(evidence),
        "edge_count": len(edges),
        "covered_module_counts": dict(sorted(covered.items())),
        "relation_counts": dict(sorted(relation_counts.items())),
        "accepted": inventory.accepted and selected_matrix.accepted,
    }
    return ModuleCertificationLineage(
        **body,
        content_address=_address(body, "module-certification-lineage"),
    )


def verify_module_certification_lineage(
    value: ModuleCertificationLineage,
) -> ModuleCertificationLineage:
    """Verify every lineage row and the aggregate address without source access."""

    if not isinstance(value, ModuleCertificationLineage):
        raise ValidationError("lineage verification requires a typed graph")
    for item in value.evidence:
        if address_module_certification_evidence(item) != item.content_address:
            raise ValidationError(f"lineage evidence address mismatch: {item.evidence_id}")
        if item.relative_path.startswith(("/", "\\")) or "\\" in item.relative_path:
            raise ValidationError(f"lineage path is not public-safe: {item.evidence_id}")
    evidence_ids = {item.evidence_id for item in value.evidence}
    module_ids = {item.module_id for item in value.evidence}
    for item in value.edges:
        if address_module_certification_lineage_edge(item) != item.content_address:
            raise ValidationError(f"lineage edge address mismatch: {item.target_id}")
        if any(identifier not in evidence_ids for identifier in item.evidence_ids):
            raise ValidationError(f"lineage edge references missing evidence: {item.target_id}")
        if item.source_module not in module_ids:
            raise ValidationError(f"lineage edge source is not covered: {item.source_module}")
    projection = jsonable(value.to_dict())
    if any(key.casefold() in _FORBIDDEN_KEYS for key in projection):
        raise ValidationError("lineage public boundary contains a forbidden key")
    body = {
        key: jsonable(item)
        for key, item in projection.items()
        if key not in {"content_address", "version", "boundary"}
    }
    if _address(body, "module-certification-lineage") != value.content_address:
        raise ValidationError("module certification lineage aggregate address mismatch")
    return value


def _module_rows(value: ModuleCertificationLineage) -> list[dict[str, Any]]:
    evidence_by_module: dict[str, list[ModuleCertificationEvidence]] = {}
    for item in value.evidence:
        evidence_by_module.setdefault(item.module_id, []).append(item)
    edges_by_module: dict[str, list[ModuleCertificationLineageEdge]] = {}
    for item in value.edges:
        edges_by_module.setdefault(item.source_module, []).append(item)
    rows: list[dict[str, Any]] = []
    for module_id in sorted(set(evidence_by_module) | set(edges_by_module)):
        module_evidence = tuple(
            sorted(evidence_by_module.get(module_id, ()), key=lambda x: x.evidence_id)
        )
        module_edges = tuple(edges_by_module.get(module_id, ()))
        kinds = tuple(sorted({item.kind.value for item in module_evidence}))
        body = {
            "module_id": module_id,
            "evidence_count": len(module_evidence),
            "evidence_kinds": kinds,
            "edge_count": len(module_edges),
            "resolved_dependency_count": sum(
                item.target_kind is CertificationLineageTargetKind.MODULE and item.resolved
                for item in module_edges
            ),
            "unresolved_dependency_count": sum(
                item.target_kind is CertificationLineageTargetKind.MODULE and not item.resolved
                for item in module_edges
            ),
        }
        rows.append(
            body | {"content_address": _address(body, "module-certification-lineage-module")}
        )
    return rows


def query_module_certification_lineage(
    value: ModuleCertificationLineage,
    *,
    resource: str = "evidence",
    module_id: str | None = None,
    kind: str | None = None,
    relation: str | None = None,
    resolved: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_CERTIFICATION_LINEAGE_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return a bounded evidence, edge, or module lineage page."""

    if not isinstance(value, ModuleCertificationLineage):
        raise ValidationError("lineage query requires a typed graph")
    if offset < 0 or limit < 1 or limit > MODULE_CERTIFICATION_LINEAGE_MAX_LIMIT:
        raise ValidationError("lineage pagination is invalid")
    if resource not in {"evidence", "edges", "modules"}:
        raise ValidationError("lineage resource must be evidence, edges, or modules")
    if resource == "evidence":
        rows: list[Any] = list(value.evidence)
        if module_id is not None:
            rows = [item for item in rows if item.module_id == module_id]
        if kind is not None:
            rows = [item for item in rows if item.kind.value == kind]
        if relation is not None:
            rows = [item for item in rows if item.relation.value == relation]
    elif resource == "edges":
        rows = list(value.edges)
        if module_id is not None:
            rows = [item for item in rows if item.source_module == module_id]
        if relation is not None:
            rows = [item for item in rows if item.relation.value == relation]
        if resolved is not None:
            rows = [item for item in rows if item.resolved is resolved]
        if kind is not None:
            rows = [item for item in rows if item.target_kind.value == kind]
    else:
        rows = _module_rows(value)
        if module_id is not None:
            rows = [item for item in rows if item["module_id"] == module_id]
        if kind is not None:
            rows = [item for item in rows if kind in item["evidence_kinds"]]
    if text:
        rows = [
            item for item in rows if text.casefold() in canonical_json(jsonable(item)).casefold()
        ]
    serializable = tuple(jsonable(item) for item in rows[offset : offset + limit])
    body = {
        "version": MODULE_CERTIFICATION_LINEAGE_VERSION,
        "resource": resource,
        "query": {
            "module_id": module_id,
            "kind": kind,
            "relation": relation,
            "resolved": resolved,
            "text": text,
            "offset": offset,
            "limit": limit,
        },
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < len(rows),
        "items": serializable,
        "lineage_address": value.content_address,
        "accepted": value.accepted,
    }
    return body | {"content_address": _address(body, "module-certification-lineage-query")}


def module_certification_lineage_json(value: ModuleCertificationLineage) -> str:
    return canonical_json(value.to_dict()) + "\n"


def module_certification_evidence_csv(value: ModuleCertificationLineage) -> str:
    fields = (
        "evidence_id",
        "module_id",
        "kind",
        "relative_path",
        "relation",
        "detail",
        "source_digest",
        "line_count",
        "content_address",
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in value.evidence:
        row = item.to_dict()
        writer.writerow(row)
    return output.getvalue()


def module_certification_lineage_edges_csv(value: ModuleCertificationLineage) -> str:
    fields = (
        "source_module",
        "target_kind",
        "target_id",
        "relation",
        "resolved",
        "evidence_ids",
        "content_address",
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in value.edges:
        row = item.to_dict()
        row["evidence_ids"] = "|".join(item.evidence_ids)
        writer.writerow(row)
    return output.getvalue()


def render_module_certification_lineage_markdown(value: ModuleCertificationLineage) -> str:
    """Render a compact human review without embedding source contents."""

    lines = [
        "# Module certification evidence lineage",
        "",
        f"- Inventory address: `{value.inventory_address}`",
        f"- Matrix address: `{value.matrix_address}`",
        f"- Modules: **{value.module_count:,}**",
        f"- Evidence / edges: **{value.evidence_count:,} / {value.edge_count:,}**",
        f"- Accepted: **{str(value.accepted).lower()}**",
        "",
        "| Evidence kind | Covered modules | Records |",
        "| --- | ---: | ---: |",
    ]
    for kind in CertificationEvidenceKind:
        rows = [item for item in value.evidence if item.kind is kind]
        lines.append(
            f"| {kind.value} | {value.covered_module_counts.get(kind.value, 0):,} | {len(rows):,} |"
        )
    lines.extend(
        [
            "",
            "| Source module | Target | Relation | Resolved |",
            "| --- | --- | --- | --- |",
        ]
    )
    for item in value.edges:
        lines.append(
            f"| `{item.source_module}` | `{item.target_id}` | {item.relation.value} | "
            f"{str(item.resolved).lower()} |"
        )
    return "\n".join(lines) + "\n"


def module_certification_lineage_schema() -> dict[str, Any]:
    return {
        "version": MODULE_CERTIFICATION_LINEAGE_VERSION,
        "boundary": MODULE_CERTIFICATION_LINEAGE_BOUNDARY,
        "resources": ["evidence", "edges", "modules"],
        "evidence_kinds": [item.value for item in CertificationEvidenceKind],
        "relations": [item.value for item in CertificationLineageRelation],
        "target_kinds": [item.value for item in CertificationLineageTargetKind],
        "evidence_fields": [
            "evidence_id",
            "module_id",
            "kind",
            "relative_path",
            "relation",
            "detail",
            "source_digest",
            "line_count",
            "content_address",
        ],
        "edge_fields": [
            "source_module",
            "target_kind",
            "target_id",
            "relation",
            "resolved",
            "evidence_ids",
            "content_address",
        ],
        "module_fields": [
            "module_id",
            "evidence_count",
            "evidence_kinds",
            "edge_count",
            "resolved_dependency_count",
            "unresolved_dependency_count",
            "content_address",
        ],
        "guarantees": [
            "source, test, and documentation files are read as static bytes",
            "source execution and module imports are disabled",
            "paths are repository-relative and use forward slashes",
            "evidence and edges are sorted, bounded, and content addressed",
            "unresolved dependency edges remain explicit",
            "payloads contain digests and counts instead of source contents",
        ],
        "query_filters": ["module_id", "kind", "relation", "resolved", "text"],
    }


def module_certification_lineage_capabilities() -> dict[str, Any]:
    operations = (
        "index_source_evidence",
        "index_test_references",
        "index_documentation_references",
        "parse_package_exports",
        "link_dependency_edges",
        "retain_unresolved_edges",
        "count_evidence_by_kind",
        "query_evidence",
        "query_edges",
        "query_module_coverage",
        "export_evidence_csv",
        "export_edges_csv",
        "render_lineage_markdown",
        "verify_content_addresses",
    )
    return {
        "version": MODULE_CERTIFICATION_LINEAGE_VERSION,
        "boundary": MODULE_CERTIFICATION_LINEAGE_BOUNDARY,
        "operation_count": len(operations),
        "operations": list(operations),
        "static_only": True,
        "read_only": True,
        "deterministic": True,
        "source_execution": False,
        "absolute_paths": False,
        "max_evidence": MODULE_CERTIFICATION_LINEAGE_MAX_EVIDENCE,
        "max_edges": MODULE_CERTIFICATION_LINEAGE_MAX_EDGES,
    }


__all__ = [
    "build_module_certification_lineage",
    "module_certification_evidence_csv",
    "module_certification_lineage_capabilities",
    "module_certification_lineage_edges_csv",
    "module_certification_lineage_json",
    "module_certification_lineage_schema",
    "query_module_certification_lineage",
    "render_module_certification_lineage_markdown",
    "verify_module_certification_lineage",
]
