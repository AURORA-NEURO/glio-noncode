"""Static evidence extraction and per-module certification matrix construction."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_certification_contracts import (
    MODULE_CERTIFICATION_BOUNDARY,
    MODULE_CERTIFICATION_VERSION,
    CertificationCheckKind,
    CertificationCheckState,
    CertificationState,
    ModuleCertificationCheck,
    ModuleCertificationGap,
    ModuleCertificationMatrix,
    ModuleCertificationRow,
)
from .module_inventory_contracts import ModuleInventory, ModuleRole, ModuleState
from .module_inventory_query import inventory_from_mapping
from .serialization import canonical_json, content_hash, jsonable

_PACKAGE = "glio_noncode"
_PACKAGE_REFERENCE = re.compile(r"\bglio_noncode(?:\.[A-Za-z_][A-Za-z0-9_]*)+")
_PYTHON_FILE_REFERENCE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\.py\b")
_FORBIDDEN_WORDS = frozenset(
    {"agent", "assistant", "author", "email", "language", "model", "patient", "subject"}
)
_CHECK_ORDER = tuple(CertificationCheckKind)


def _inventory(value: ModuleInventory | dict[str, Any]) -> ModuleInventory:
    if isinstance(value, ModuleInventory):
        return value
    if isinstance(value, dict):
        return inventory_from_mapping(value)
    raise ValidationError("module certification requires a typed inventory")


def _address(body: Any, prefix: str) -> str:
    return content_hash(body, prefix=prefix)


def _source_root(source_root: str | Path | None) -> Path:
    return Path(source_root) if source_root is not None else Path(__file__).resolve().parent


def _text_tokens(root: Path, *, markdown: bool = False) -> tuple[set[str], set[str]]:
    """Read each evidence file once and return module and file-reference tokens."""

    module_tokens: set[str] = set()
    file_tokens: set[str] = set()
    if not root.exists() or not root.is_dir():
        return module_tokens, file_tokens
    suffixes = {".md", ".markdown"} if markdown else {".py"}
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().casefold()):
        if path.is_symlink() or not path.is_file() or path.suffix.casefold() not in suffixes:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        module_tokens.update(_PACKAGE_REFERENCE.findall(text))
        if markdown:
            file_tokens.update(_PYTHON_FILE_REFERENCE.findall(text))
    return module_tokens, file_tokens


def _exported_modules(source_root: Path) -> set[str]:
    """Statically inspect package imports, never importing the package."""

    init_path = source_root / "__init__.py"
    try:
        tree = ast.parse(init_path.read_text(encoding="utf-8"), filename=str(init_path))
    except (OSError, UnicodeDecodeError, SyntaxError):
        return set()
    exported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level and node.module:
                base = _PACKAGE
                if node.level > 1:
                    base = _PACKAGE + "." * (node.level - 1)
                exported.add(f"{base}.{node.module}")
            elif node.level and not node.module:
                for alias in node.names:
                    if alias.name != "*":
                        exported.add(f"{_PACKAGE}.{alias.name}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == _PACKAGE or alias.name.startswith(f"{_PACKAGE}."):
                    exported.add(alias.name)
    return exported


def _module_evidence(
    module_id: str,
    inventory_row: Any,
    test_modules: set[str],
    doc_modules: set[str],
    doc_files: set[str],
    exported: set[str],
) -> dict[CertificationCheckKind, tuple[CertificationCheckState, Any, Any, str, tuple[str, ...]]]:
    public = inventory_row.public_symbol_count > 0
    dependency_required = inventory_row.import_count > 0
    doc_reference = module_id in doc_modules or f"{module_id.rsplit('.', 1)[-1]}.py" in doc_files
    exported_reference = module_id in exported or inventory_row.relative_path.endswith(
        "__init__.py"
    )
    return {
        CertificationCheckKind.PARSE: (
            CertificationCheckState.PASSED
            if inventory_row.state is ModuleState.PARSED
            else CertificationCheckState.FAILED,
            inventory_row.state.value,
            "parsed",
            "AST parse state is accepted",
            (inventory_row.state.value,),
        ),
        CertificationCheckKind.SYMBOL: (
            CertificationCheckState.PASSED if public else CertificationCheckState.NOT_APPLICABLE,
            inventory_row.public_symbol_count,
            ">0 public symbols or not applicable",
            "public symbol surface is represented",
            (f"public_symbols={inventory_row.public_symbol_count}",),
        ),
        CertificationCheckKind.DEPENDENCY: (
            CertificationCheckState.PASSED
            if not dependency_required
            or inventory_row.local_dependency_count == inventory_row.import_count
            else CertificationCheckState.FAILED,
            inventory_row.local_dependency_count,
            inventory_row.import_count,
            "local dependency edges are resolved",
            (
                f"imports={inventory_row.import_count}",
                f"resolved={inventory_row.local_dependency_count}",
            ),
        ),
        CertificationCheckKind.TEST: (
            CertificationCheckState.PASSED
            if module_id in test_modules or inventory_row.test_reference_count > 0
            else (
                CertificationCheckState.FAILED if public else CertificationCheckState.NOT_APPLICABLE
            ),
            inventory_row.test_reference_count,
            ">0 test references for public modules",
            "test reference evidence is present",
            (f"test_references={inventory_row.test_reference_count}",),
        ),
        CertificationCheckKind.DOCUMENTATION: (
            CertificationCheckState.PASSED
            if doc_reference
            else (
                CertificationCheckState.FAILED if public else CertificationCheckState.NOT_APPLICABLE
            ),
            doc_reference,
            True,
            "documentation references the module ID or source file",
            (
                "module_id"
                if module_id in doc_modules
                else "source_file"
                if doc_reference
                else "no_reference",
            ),
        ),
        CertificationCheckKind.EXPORT: (
            CertificationCheckState.PASSED
            if exported_reference
            else (
                CertificationCheckState.FAILED if public else CertificationCheckState.NOT_APPLICABLE
            ),
            exported_reference,
            True,
            "public module surface is represented in package exports",
            ("package_export" if exported_reference else "not_exported",),
        ),
        CertificationCheckKind.BOUNDARY: (
            CertificationCheckState.FAILED
            if any(word in module_id.casefold().split(".") for word in _FORBIDDEN_WORDS)
            else CertificationCheckState.PASSED,
            module_id,
            "safe module identifier",
            "module identifier contains no forbidden identity or attribution token",
            (module_id,),
        ),
        CertificationCheckKind.SCALE: (
            CertificationCheckState.PASSED
            if 0 < inventory_row.physical_lines <= 100000
            else CertificationCheckState.NOT_APPLICABLE
            if inventory_row.physical_lines == 0
            else CertificationCheckState.FAILED,
            inventory_row.physical_lines,
            "1..100000 physical lines",
            "module size is within the static review bound",
            (f"physical_lines={inventory_row.physical_lines}",),
        ),
    }


def _check(
    kind: CertificationCheckKind,
    state: CertificationCheckState,
    observed: Any,
    required: Any,
    detail: str,
    evidence: tuple[str, ...],
) -> ModuleCertificationCheck:
    body = {
        "kind": kind,
        "state": state,
        "observed": observed,
        "required": required,
        "detail": detail,
        "evidence": tuple(sorted(set(evidence))),
    }
    return ModuleCertificationCheck(
        **body, content_address=_address(body, "module-certification-check")
    )


def _gap(
    module_id: str,
    kind: CertificationCheckKind,
    priority: int,
    detail: str,
    next_action: str,
    evidence: tuple[str, ...],
) -> ModuleCertificationGap:
    body = {
        "gap_id": f"{kind.value}:{module_id}",
        "module_id": module_id,
        "kind": kind,
        "priority": priority,
        "detail": detail,
        "next_action": next_action,
        "evidence": tuple(sorted(set(evidence))),
    }
    return ModuleCertificationGap(
        **body, content_address=_address(body, "module-certification-gap")
    )


def _gap_priority(kind: CertificationCheckKind, role: str) -> int:
    base = {
        CertificationCheckKind.PARSE: 0,
        CertificationCheckKind.DEPENDENCY: 10,
        CertificationCheckKind.BOUNDARY: 0,
        CertificationCheckKind.TEST: 30,
        CertificationCheckKind.DOCUMENTATION: 45,
        CertificationCheckKind.EXPORT: 50,
        CertificationCheckKind.SYMBOL: 60,
        CertificationCheckKind.SCALE: 70,
    }[kind]
    if role == ModuleRole.INTEGRATION.value and kind in {
        CertificationCheckKind.EXPORT,
        CertificationCheckKind.DOCUMENTATION,
    }:
        return max(0, base - 10)
    return base


def build_module_certification(
    value: ModuleInventory | dict[str, Any],
    *,
    source_root: str | Path | None = None,
    test_root: str | Path | None = None,
    docs_root: str | Path | None = None,
) -> ModuleCertificationMatrix:
    """Build a complete static certification matrix from inventory evidence."""

    inventory = _inventory(value)
    source = _source_root(source_root)
    tests = Path(test_root) if test_root is not None else source.parent.parent / "tests"
    docs = Path(docs_root) if docs_root is not None else source.parent.parent / "docs"
    test_modules, _ = _text_tokens(tests)
    doc_modules, doc_files = _text_tokens(docs, markdown=True)
    exported = _exported_modules(source)
    rows: list[ModuleCertificationRow] = []
    gaps: list[ModuleCertificationGap] = []
    for module in inventory.modules:
        evidence = _module_evidence(
            module.module_id, module, test_modules, doc_modules, doc_files, exported
        )
        checks = tuple(_check(kind, *evidence[kind]) for kind in _CHECK_ORDER)
        passed = sum(item.state is CertificationCheckState.PASSED for item in checks)
        failed = sum(item.state is CertificationCheckState.FAILED for item in checks)
        not_applicable = len(checks) - passed - failed
        denominator = passed + failed
        score = round(passed / denominator, 6) if denominator else 0.0
        blocking = any(
            item.state is CertificationCheckState.FAILED
            and item.kind
            in {
                CertificationCheckKind.PARSE,
                CertificationCheckKind.DEPENDENCY,
                CertificationCheckKind.BOUNDARY,
            }
            for item in checks
        )
        state = (
            CertificationState.BLOCKED
            if blocking
            else CertificationState.CERTIFIED
            if failed == 0 and score >= 0.8
            else CertificationState.REVIEW
            if denominator
            else CertificationState.UNCOVERED
        )
        body = {
            "module_id": module.module_id,
            "family": module.family,
            "role": module.role.value,
            "physical_lines": module.physical_lines,
            "public_symbol_count": module.public_symbol_count,
            "checks": checks,
            "passed_count": passed,
            "failed_count": failed,
            "not_applicable_count": not_applicable,
            "score": score,
            "state": state,
            "gap_count": failed,
        }
        rows.append(
            ModuleCertificationRow(
                **body, content_address=_address(body, "module-certification-row")
            )
        )
        for check in checks:
            if check.state is not CertificationCheckState.FAILED:
                continue
            next_action = {
                CertificationCheckKind.PARSE: (
                    "repair syntax or encoding, then rebuild the inventory"
                ),
                CertificationCheckKind.DEPENDENCY: (
                    "resolve local imports or declare an explicit abstention"
                ),
                CertificationCheckKind.TEST: (
                    "add a deterministic test reference for the public module surface"
                ),
                CertificationCheckKind.DOCUMENTATION: (
                    "add a documentation reference for the module contract"
                ),
                CertificationCheckKind.EXPORT: (
                    "review package exposure and export the intended public surface"
                ),
                CertificationCheckKind.BOUNDARY: (
                    "rename the module to remove forbidden public identity tokens"
                ),
                CertificationCheckKind.SYMBOL: (
                    "declare a public symbol or mark the module as internal"
                ),
                CertificationCheckKind.SCALE: "split or explicitly review the oversized module",
            }[check.kind]
            gaps.append(
                _gap(
                    module.module_id,
                    check.kind,
                    _gap_priority(check.kind, module.role.value),
                    check.detail,
                    next_action,
                    check.evidence,
                )
            )
    rows_tuple = tuple(sorted(rows, key=lambda item: item.module_id))
    gaps_tuple = tuple(
        sorted(gaps, key=lambda item: (item.priority, item.module_id, item.kind.value))
    )
    overall = (
        round(sum(item.score for item in rows_tuple) / len(rows_tuple), 6) if rows_tuple else 0.0
    )
    body = {
        "inventory_address": inventory.content_address,
        "rows": rows_tuple,
        "gaps": gaps_tuple,
        "check_kind_count": len(_CHECK_ORDER),
        "module_count": len(rows_tuple),
        "certified_count": sum(item.state is CertificationState.CERTIFIED for item in rows_tuple),
        "review_count": sum(item.state is CertificationState.REVIEW for item in rows_tuple),
        "blocked_count": sum(item.state is CertificationState.BLOCKED for item in rows_tuple),
        "uncovered_count": sum(item.state is CertificationState.UNCOVERED for item in rows_tuple),
        "overall_score": overall,
        "overall_percent": round(overall * 100.0, 2),
        "accepted": inventory.accepted,
    }
    return ModuleCertificationMatrix(
        **body, content_address=_address(body, "module-certification-matrix")
    )


def verify_module_certification(value: ModuleCertificationMatrix) -> ModuleCertificationMatrix:
    """Verify row, check, and gap addresses without source access."""

    if not isinstance(value, ModuleCertificationMatrix):
        raise ValidationError("module certification verification requires a typed matrix")
    for row in value.rows:
        for check in row.checks:
            body = {
                key: jsonable(item)
                for key, item in check.to_dict().items()
                if key != "content_address"
            }
            if _address(body, "module-certification-check") != check.content_address:
                raise ValidationError(
                    f"module certification check address mismatch: {row.module_id}"
                )
        body = {
            key: jsonable(item) for key, item in row.to_dict().items() if key != "content_address"
        }
        if _address(body, "module-certification-row") != row.content_address:
            raise ValidationError(f"module certification row address mismatch: {row.module_id}")
    for gap in value.gaps:
        body = {
            key: jsonable(item) for key, item in gap.to_dict().items() if key != "content_address"
        }
        if _address(body, "module-certification-gap") != gap.content_address:
            raise ValidationError(f"module certification gap address mismatch: {gap.gap_id}")
    return value


def module_certification_json(value: ModuleCertificationMatrix) -> str:
    return canonical_json(value.to_dict()) + "\n"


def module_certification_schema() -> dict[str, Any]:
    return {
        "version": MODULE_CERTIFICATION_VERSION,
        "boundary": MODULE_CERTIFICATION_BOUNDARY,
        "check_kinds": [item.value for item in CertificationCheckKind],
        "check_states": [item.value for item in CertificationCheckState],
        "module_states": [item.value for item in CertificationState],
        "row_fields": [
            "module_id",
            "family",
            "role",
            "physical_lines",
            "public_symbol_count",
            "checks",
            "passed_count",
            "failed_count",
            "not_applicable_count",
            "score",
            "state",
            "gap_count",
            "content_address",
        ],
        "gap_fields": [
            "gap_id",
            "module_id",
            "kind",
            "priority",
            "detail",
            "next_action",
            "evidence",
            "content_address",
        ],
        "static_evidence": [
            "inventory_row",
            "test_reference_tokens",
            "documentation_tokens",
            "package_import_ast",
        ],
    }


def module_certification_capabilities() -> dict[str, Any]:
    operations = (
        "extract_test_references",
        "extract_documentation_references",
        "extract_package_exports",
        "check_parse_state",
        "check_symbol_surface",
        "check_dependency_resolution",
        "check_test_evidence",
        "check_documentation_evidence",
        "check_export_evidence",
        "check_public_boundary",
        "check_implementation_scale",
        "score_module_rows",
        "build_gap_queue",
        "verify_row_addresses",
    )
    return {
        "version": MODULE_CERTIFICATION_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "static_only": True,
        "read_only": True,
        "deterministic": True,
        "source_execution": False,
    }


__all__ = [
    "build_module_certification",
    "module_certification_capabilities",
    "module_certification_json",
    "module_certification_schema",
    "verify_module_certification",
]
