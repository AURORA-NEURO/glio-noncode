#!/usr/bin/env python3
"""Generate the immutable root-package public-surface manifest.

This is the migration half of the eager-to-lazy root-package transition.  It
does not edit ``glio_noncode.__init__``.  Instead, it replays that module's
imports in source order, reconciles the replay with the final eager runtime,
and writes data that a later lazy loader can consume without importing the
whole package.

The runtime is authoritative for collisions.  Source replay supplies the
provenance needed for constants, star imports, and assigned aliases.  A
binding which cannot be traced to exactly one importable object is rejected;
silently choosing one of several same-valued constants would make the lazy
surface observably different from the eager one.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib
import json
import sys
import types
from dataclasses import dataclass
from pathlib import Path

MANIFEST_VERSION = 2
SUPPORTED_GENERATED_VERSIONS = frozenset({1, MANIFEST_VERSION})
PACKAGE_NAME = "glio_noncode"
LEGACY_ALL_DIGEST = "92622f9cc8f55b9956927bca80dda54658c7c14eaaa3c55124ac34077be3e9ff"
IGNORED_RUNTIME_NAMES = frozenset(
    {
        "__all__",
        "__builtins__",
        "__cached__",
        "__doc__",
        "__file__",
        "__loader__",
        "__name__",
        "__package__",
        "__path__",
        "__spec__",
    }
)
STALE_EXPORT_REPAIRS: dict[str, tuple[str, str]] = {
    "AtlasArchitectureField": (
        "glio_noncode.atlas_architecture_data_dictionary",
        "AtlasArchitectureField",
    ),
    "query_review_workspace_execution_release_transitions_view": (
        "glio_noncode.review_workspace_execution_release",
        "query_review_workspace_execution_release_transitions_view",
    ),
}

Descriptor = tuple[str, str | None]

CURATED_EXPORTS: dict[str, Descriptor] = {
    "WORKFLOW_VERSION": ("glio_noncode.case_workflow", "WORKFLOW_VERSION"),
    "WorkflowState": ("glio_noncode.case_workflow", "WorkflowState"),
    "WorkflowSeverity": ("glio_noncode.case_workflow", "WorkflowSeverity"),
    "WorkflowStage": ("glio_noncode.case_workflow", "WorkflowStage"),
    "VariantSource": ("glio_noncode.case_workflow", "VariantSource"),
    "VariantSourceInput": ("glio_noncode.case_workflow", "VariantSourceInput"),
    "RegulatoryTrackSource": ("glio_noncode.case_workflow", "RegulatoryTrackSource"),
    "RegulatoryTrackSourceInput": (
        "glio_noncode.case_workflow",
        "RegulatoryTrackSourceInput",
    ),
    "WorkflowIssue": ("glio_noncode.case_workflow", "WorkflowIssue"),
    "StageReceipt": ("glio_noncode.case_workflow", "StageReceipt"),
    "PreparedCase": ("glio_noncode.case_workflow", "PreparedCase"),
    "CaseRunResult": ("glio_noncode.case_workflow", "CaseRunResult"),
    "prepare_case": ("glio_noncode.case_workflow", "prepare_case"),
    "run_case": ("glio_noncode.case_workflow", "run_case"),
    "case_workflow_schema": ("glio_noncode.case_workflow", "case_workflow_schema"),
    "variant_source_schema": ("glio_noncode.case_workflow", "variant_source_schema"),
    "regulatory_track_source_schema": (
        "glio_noncode.case_workflow",
        "regulatory_track_source_schema",
    ),
    "prepared_case_schema": ("glio_noncode.case_workflow", "prepared_case_schema"),
    "run_result_schema": ("glio_noncode.case_workflow", "run_result_schema"),
    "case_workflow_capabilities": ("glio_noncode.case_workflow", "capabilities"),
    "EXPRESSION_EVIDENCE_SCHEMA_VERSION": (
        "glio_noncode.expression_evidence",
        "SCHEMA_VERSION",
    ),
    "RNAEvidenceState": ("glio_noncode.expression_evidence", "RNAEvidenceState"),
    "ExpressionScale": ("glio_noncode.expression_evidence", "ExpressionScale"),
    "RegulatoryDirection": (
        "glio_noncode.expression_evidence",
        "RegulatoryDirection",
    ),
    "ExpressionDirection": (
        "glio_noncode.expression_evidence",
        "ExpressionDirection",
    ),
    "AllelicDirection": ("glio_noncode.expression_evidence", "AllelicDirection"),
    "PhaseStatus": ("glio_noncode.expression_evidence", "PhaseStatus"),
    "DispersionMethod": ("glio_noncode.expression_evidence", "DispersionMethod"),
    "ExpectedFractionMethod": (
        "glio_noncode.expression_evidence",
        "ExpectedFractionMethod",
    ),
    "ExpressionObservation": (
        "glio_noncode.expression_evidence",
        "ExpressionObservation",
    ),
    "ExpressionBatch": ("glio_noncode.expression_evidence", "ExpressionBatch"),
    "RobustOutlierPolicy": (
        "glio_noncode.expression_evidence",
        "RobustOutlierPolicy",
    ),
    "ExpressionOutlierResult": (
        "glio_noncode.expression_evidence",
        "ExpressionOutlierResult",
    ),
    "RobustExpressionOutlierAnalyzer": (
        "glio_noncode.expression_evidence",
        "RobustExpressionOutlierAnalyzer",
    ),
    "AllelicCountObservation": (
        "glio_noncode.expression_evidence",
        "AllelicCountObservation",
    ),
    "AllelicCountBatch": (
        "glio_noncode.expression_evidence",
        "AllelicCountBatch",
    ),
    "AllelicImbalancePolicy": (
        "glio_noncode.expression_evidence",
        "AllelicImbalancePolicy",
    ),
    "AllelicImbalanceResult": (
        "glio_noncode.expression_evidence",
        "AllelicImbalanceResult",
    ),
    "AllelicImbalanceAnalyzer": (
        "glio_noncode.expression_evidence",
        "AllelicImbalanceAnalyzer",
    ),
    "PredictedRegulatoryEffect": (
        "glio_noncode.expression_evidence",
        "PredictedRegulatoryEffect",
    ),
    "RNAConsequenceEvidence": (
        "glio_noncode.expression_evidence",
        "RNAConsequenceEvidence",
    ),
    "RNAConsequenceIntegrator": (
        "glio_noncode.expression_evidence",
        "RNAConsequenceIntegrator",
    ),
    "expression_evidence_schema": (
        "glio_noncode.expression_evidence",
        "expression_evidence_schema",
    ),
    "expression_evidence_capabilities": (
        "glio_noncode.expression_evidence",
        "expression_evidence_capabilities",
    ),
    "expression_evidence_public_projection": (
        "glio_noncode.expression_evidence",
        "public_projection",
    ),
    "EXPRESSION_CLAIMS_SCHEMA_VERSION": (
        "glio_noncode.expression_claims",
        "SCHEMA_VERSION",
    ),
    "RNA_CONSEQUENCE_CHANNEL": (
        "glio_noncode.expression_claims",
        "RNA_CONSEQUENCE_CHANNEL",
    ),
    "RNAElementGeneTarget": (
        "glio_noncode.expression_claims",
        "RNAElementGeneTarget",
    ),
    "RNAClaimPolicy": ("glio_noncode.expression_claims", "RNAClaimPolicy"),
    "DEFAULT_RNA_CLAIM_POLICY": (
        "glio_noncode.expression_claims",
        "DEFAULT_RNA_CLAIM_POLICY",
    ),
    "RNAClaimDerivation": (
        "glio_noncode.expression_claims",
        "RNAClaimDerivation",
    ),
    "RNAClaimBatch": ("glio_noncode.expression_claims", "RNAClaimBatch"),
    "element_gene_edge_id": (
        "glio_noncode.expression_claims",
        "element_gene_edge_id",
    ),
    "matches_rna_consequence": (
        "glio_noncode.expression_claims",
        "matches_rna_consequence",
    ),
    "rna_consequence_to_claim": (
        "glio_noncode.expression_claims",
        "rna_consequence_to_claim",
    ),
    "match_rna_consequences": (
        "glio_noncode.expression_claims",
        "match_rna_consequences",
    ),
    "expression_claims_schema": (
        "glio_noncode.expression_claims",
        "expression_claims_schema",
    ),
    "expression_claims_capabilities": (
        "glio_noncode.expression_claims",
        "expression_claims_capabilities",
    ),
    "expression_claim_public_projection": (
        "glio_noncode.expression_claims",
        "public_projection",
    ),
}


class SurfaceMigrationError(RuntimeError):
    """Raised when the eager surface cannot be represented without guessing."""


@dataclass(frozen=True)
class Replay:
    """Source-order import provenance recovered from the eager initializer."""

    bindings: dict[str, Descriptor]
    constants: dict[str, object]
    assigned_aliases: dict[str, Descriptor]


@dataclass(frozen=True)
class SurfaceManifest:
    """Deterministic, fully reconciled description of the root namespace."""

    source_digest: str
    all_digest: str
    surface_digest: str
    all_names: tuple[str, ...]
    exports: dict[str, Descriptor]
    constants: dict[str, object]
    assigned_aliases: dict[str, Descriptor]
    repaired_exports: dict[str, Descriptor]
    implicit_modules: dict[str, str]
    child_modules: dict[str, str]
    lazy_modules: tuple[str, ...]
    export_child_conflicts: tuple[str, ...]
    curated_exports: dict[str, Descriptor]
    curated_all: tuple[str, ...]


def repository_root() -> Path:
    """Return the repository containing this tool."""

    return Path(__file__).resolve().parents[1]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _all_digest(names: tuple[str, ...]) -> str:
    payload = json.dumps(
        names,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return _sha256(payload)


def _module_name(node: ast.ImportFrom) -> str:
    if node.level != 1:
        raise SurfaceMigrationError(
            f"unsupported import level {node.level} at line {node.lineno}"
        )
    if node.module is None:
        return PACKAGE_NAME
    return f"{PACKAGE_NAME}.{node.module}"


def _star_names(module: types.ModuleType) -> tuple[str, ...]:
    declared = getattr(module, "__all__", None)
    if declared is None:
        return tuple(name for name in vars(module) if not name.startswith("_"))
    names = tuple(declared)
    if not all(isinstance(name, str) for name in names):
        raise SurfaceMigrationError(f"{module.__name__}.__all__ contains a non-string")
    return names


def replay_initializer(tree: ast.Module) -> Replay:
    """Replay imports and simple aliases in the same order as the initializer."""

    bindings: dict[str, Descriptor] = {}
    constants: dict[str, object] = {}
    assigned_aliases: dict[str, Descriptor] = {}

    for statement in tree.body:
        if isinstance(statement, ast.ImportFrom):
            module_name = _module_name(statement)
            if statement.module is None:
                for alias in statement.names:
                    if alias.name == "*":
                        raise SurfaceMigrationError(
                            f"unsupported 'from . import *' at line {statement.lineno}"
                        )
                    local_name = alias.asname or alias.name
                    child_name = f"{PACKAGE_NAME}.{alias.name}"
                    importlib.import_module(child_name)
                    bindings[local_name] = (child_name, None)
                    constants.pop(local_name, None)
                continue

            module = importlib.import_module(module_name)
            if len(statement.names) == 1 and statement.names[0].name == "*":
                for source_name in _star_names(module):
                    if not hasattr(module, source_name):
                        raise SurfaceMigrationError(
                            f"{module_name}.__all__ names missing attribute {source_name!r}"
                        )
                    bindings[source_name] = (module_name, source_name)
                    constants.pop(source_name, None)
                continue

            for alias in statement.names:
                if alias.name == "*":
                    raise SurfaceMigrationError(
                        f"mixed star import at line {statement.lineno} is unsupported"
                    )
                local_name = alias.asname or alias.name
                if not hasattr(module, alias.name):
                    raise SurfaceMigrationError(
                        f"line {statement.lineno}: {module_name} has no {alias.name!r}"
                    )
                bindings[local_name] = (module_name, alias.name)
                constants.pop(local_name, None)
            continue

        if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
            continue
        target = statement.targets[0]
        if not isinstance(target, ast.Name) or target.id == "__all__":
            continue

        name = target.id
        if isinstance(statement.value, ast.Name):
            source_name = statement.value.id
            if source_name not in bindings:
                raise SurfaceMigrationError(
                    f"line {statement.lineno}: alias {name!r} has no traced source "
                    f"{source_name!r}"
                )
            descriptor = bindings[source_name]
            bindings[name] = descriptor
            assigned_aliases[name] = descriptor
            constants.pop(name, None)
            continue

        try:
            value = ast.literal_eval(statement.value)
        except (TypeError, ValueError):
            # ``__all__`` mutations and computed values are intentionally not
            # evaluated here.  Every other final binding still has to reconcile
            # against the eager runtime below.
            continue
        constants[name] = value
        bindings.pop(name, None)
        assigned_aliases.pop(name, None)

    return Replay(bindings, constants, assigned_aliases)


def _resolve(descriptor: Descriptor) -> object:
    module_name, attribute = descriptor
    module = importlib.import_module(module_name)
    if attribute is None:
        return module
    if not hasattr(module, attribute):
        raise SurfaceMigrationError(
            f"descriptor {descriptor!r} names an attribute that does not exist"
        )
    return getattr(module, attribute)


def _defining_descriptor(value: object) -> Descriptor | None:
    module_name = getattr(value, "__module__", None)
    attribute = getattr(value, "__name__", None)
    if not isinstance(module_name, str) or not isinstance(attribute, str):
        return None
    try:
        module = importlib.import_module(module_name)
    except (ImportError, ValueError):
        return None
    if getattr(module, attribute, object()) is value:
        return module_name, attribute
    return None


def _loaded_identity_index() -> dict[int, tuple[Descriptor, ...]]:
    candidates: dict[int, set[Descriptor]] = {}
    for module_name, module in tuple(sys.modules.items()):
        if not module_name.startswith(f"{PACKAGE_NAME}.") or not isinstance(
            module, types.ModuleType
        ):
            continue
        for attribute, value in vars(module).items():
            candidates.setdefault(id(value), set()).add((module_name, attribute))
    return {
        identity: tuple(sorted(descriptors, key=lambda item: (item[0], item[1] or "")))
        for identity, descriptors in candidates.items()
    }


def _descriptor_for_runtime_value(
    name: str,
    value: object,
    replayed: Descriptor | None,
    identity_index: dict[int, tuple[Descriptor, ...]],
) -> Descriptor:
    if isinstance(value, types.ModuleType):
        return value.__name__, None

    if replayed is not None:
        try:
            if _resolve(replayed) is value:
                return replayed
        except SurfaceMigrationError:
            pass

    defining = _defining_descriptor(value)
    if defining is not None:
        return defining

    candidates = tuple(
        descriptor
        for descriptor in identity_index.get(id(value), ())
        if _resolve(descriptor) is value
    )
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise SurfaceMigrationError(
            f"untraceable eager root binding {name!r} ({type(value).__name__})"
        )
    rendered = ", ".join(f"{module}:{attribute}" for module, attribute in candidates)
    raise SurfaceMigrationError(f"ambiguous eager root binding {name!r}: {rendered}")


def _discover_child_modules(package_dir: Path) -> dict[str, str]:
    children: dict[str, str] = {}
    for path in sorted(package_dir.iterdir(), key=lambda item: item.name):
        if path.is_file() and path.suffix == ".py":
            name = path.stem
            if name.startswith("_"):
                continue
        elif path.is_dir() and (path / "__init__.py").is_file():
            name = path.name
        else:
            continue
        if name.startswith("_"):
            continue
        if not name.isidentifier():
            raise SurfaceMigrationError(f"child module basename is not an identifier: {name!r}")
        children[name] = f"{PACKAGE_NAME}.{name}"
    return dict(sorted(children.items()))


def _surface_payload(
    *,
    source_digest: str,
    all_names: tuple[str, ...],
    exports: dict[str, Descriptor],
    constants: dict[str, object],
    assigned_aliases: dict[str, Descriptor],
    repaired_exports: dict[str, Descriptor],
    implicit_modules: dict[str, str],
    child_modules: dict[str, str],
    lazy_modules: tuple[str, ...],
    conflicts: tuple[str, ...],
    curated_exports: dict[str, Descriptor],
    curated_all: tuple[str, ...],
) -> bytes:
    payload = {
        "manifest_version": MANIFEST_VERSION,
        "source_digest": source_digest,
        "all": list(all_names),
        "exports": [[name, module, attribute] for name, (module, attribute) in exports.items()],
        "constants": [[name, value] for name, value in constants.items()],
        "assigned_aliases": [
            [name, module, attribute]
            for name, (module, attribute) in assigned_aliases.items()
        ],
        "repaired_exports": [
            [name, module, attribute]
            for name, (module, attribute) in repaired_exports.items()
        ],
        "implicit_modules": list(implicit_modules.items()),
        "child_modules": list(child_modules.items()),
        "lazy_modules": list(lazy_modules),
        "export_child_conflicts": list(conflicts),
        "curated_exports": [
            [name, module, attribute]
            for name, (module, attribute) in curated_exports.items()
        ],
        "curated_all": list(curated_all),
    }
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _is_lazy_initializer(tree: ast.Module) -> bool:
    has_lazy_package = any(
        isinstance(statement, ast.ClassDef) and statement.name == "_LazyPackage"
        for statement in tree.body
    )
    has_surface_import = any(
        isinstance(statement, ast.ImportFrom)
        and statement.level == 1
        and any(alias.name == "_public_surface" for alias in statement.names)
        for statement in tree.body
    )
    return has_lazy_package and has_surface_import


def _manifest_from_generated(source_root: Path) -> SurfaceManifest:
    source_root_text = str(source_root)
    if source_root_text not in sys.path:
        sys.path.insert(0, source_root_text)
    surface = importlib.import_module(f"{PACKAGE_NAME}._public_surface")
    if surface.MANIFEST_VERSION not in SUPPORTED_GENERATED_VERSIONS:
        raise SurfaceMigrationError(
            f"unsupported generated manifest version {surface.MANIFEST_VERSION!r}"
        )
    conflicts = tuple(surface.CANONICAL_EXPORT_CHILD_CONFLICTS)
    if tuple(surface.EXPORT_CHILD_CONFLICTS) != conflicts:
        raise SurfaceMigrationError("generated conflict aliases disagree")
    manifest = SurfaceManifest(
        source_digest=surface.SOURCE_DIGEST,
        all_digest=surface.ALL_DIGEST,
        surface_digest=surface.SURFACE_DIGEST,
        all_names=tuple(surface.ALL),
        exports=dict(surface.EXPORTS),
        constants=dict(surface.CONSTANTS),
        assigned_aliases=dict(surface.ASSIGNED_ALIASES),
        repaired_exports=dict(surface.REPAIRED_EXPORTS),
        implicit_modules=dict(surface.IMPLICIT_MODULES),
        child_modules=dict(surface.CHILD_MODULES),
        lazy_modules=tuple(surface.LAZY_MODULES),
        export_child_conflicts=conflicts,
        curated_exports=dict(getattr(surface, "CURATED_EXPORTS", {})),
        curated_all=tuple(getattr(surface, "CURATED_ALL", ())),
    )
    return manifest


def _apply_curated_exports(manifest: SurfaceManifest) -> SurfaceManifest:
    previous_exports = manifest.curated_exports
    previous_all = manifest.curated_all
    if tuple(previous_exports) != previous_all:
        raise SurfaceMigrationError(
            "generated CURATED_ALL differs from CURATED_EXPORTS order"
        )

    legacy_all = manifest.all_names
    if previous_all:
        if legacy_all[-len(previous_all) :] != previous_all:
            raise SurfaceMigrationError("generated curated names are not the ALL suffix")
        legacy_all = legacy_all[: -len(previous_all)]
    if _all_digest(legacy_all) != LEGACY_ALL_DIGEST:
        raise SurfaceMigrationError(
            "captured legacy ALL order or duplicates differ from the migration baseline"
        )

    exports = dict(manifest.exports)
    for name, descriptor in previous_exports.items():
        if exports.get(name) != descriptor:
            raise SurfaceMigrationError(
                f"generated curated descriptor for {name!r} differs from EXPORTS"
            )
        exports.pop(name)

    collisions = sorted(
        name for name in CURATED_EXPORTS if name in exports or name in legacy_all
    )
    if collisions:
        raise SurfaceMigrationError(
            f"curated additions collide with the captured legacy surface: {collisions!r}"
        )
    for descriptor in CURATED_EXPORTS.values():
        _resolve(descriptor)
    exports.update(CURATED_EXPORTS)
    exports = dict(sorted(exports.items()))

    curated_exports = dict(CURATED_EXPORTS)
    curated_all = tuple(curated_exports)
    all_names = legacy_all + curated_all
    lazy_modules = tuple(
        sorted(
            {module for module, _attribute in exports.values()}
            | set(manifest.child_modules.values())
        )
    )
    conflicts = tuple(sorted(set(exports).intersection(manifest.child_modules)))
    all_digest = _all_digest(all_names)
    surface_digest = _sha256(
        _surface_payload(
            source_digest=manifest.source_digest,
            all_names=all_names,
            exports=exports,
            constants=manifest.constants,
            assigned_aliases=manifest.assigned_aliases,
            repaired_exports=manifest.repaired_exports,
            implicit_modules=manifest.implicit_modules,
            child_modules=manifest.child_modules,
            lazy_modules=lazy_modules,
            conflicts=conflicts,
            curated_exports=curated_exports,
            curated_all=curated_all,
        )
    )
    return SurfaceManifest(
        source_digest=manifest.source_digest,
        all_digest=all_digest,
        surface_digest=surface_digest,
        all_names=all_names,
        exports=exports,
        constants=manifest.constants,
        assigned_aliases=manifest.assigned_aliases,
        repaired_exports=manifest.repaired_exports,
        implicit_modules=manifest.implicit_modules,
        child_modules=manifest.child_modules,
        lazy_modules=lazy_modules,
        export_child_conflicts=conflicts,
        curated_exports=curated_exports,
        curated_all=curated_all,
    )


def build_manifest(repo_root: Path | None = None) -> SurfaceManifest:
    """Capture and reconcile the current root package.

    A legacy eager initializer is replayed and reconciled against final runtime
    identity.  After migration, the compact initializer is detected and the
    captured eager baseline is reconstructed from its generated manifest.
    """

    root = (repo_root or repository_root()).resolve()
    source_root = root / "src"
    package_dir = source_root / PACKAGE_NAME
    initializer = package_dir / "__init__.py"
    source_bytes = initializer.read_bytes()
    source = source_bytes.decode("utf-8")
    tree = ast.parse(source, filename=str(initializer))

    source_root_text = str(source_root)
    if source_root_text not in sys.path:
        sys.path.insert(0, source_root_text)
    if _is_lazy_initializer(tree):
        return _apply_curated_exports(_manifest_from_generated(source_root))

    package = importlib.import_module(PACKAGE_NAME)
    replay = replay_initializer(tree)

    all_names = tuple(package.__all__)
    if not all(isinstance(name, str) for name in all_names):
        raise SurfaceMigrationError("glio_noncode.__all__ contains a non-string")

    child_modules = _discover_child_modules(package_dir)
    runtime = vars(package)
    constants = {
        name: value
        for name, value in replay.constants.items()
        if name in runtime and name not in IGNORED_RUNTIME_NAMES
    }
    for name, expected in constants.items():
        if runtime[name] != expected:
            raise SurfaceMigrationError(
                f"literal binding {name!r} changed during eager initialization"
            )

    runtime_surface_names = {
        name
        for name in runtime
        if name not in IGNORED_RUNTIME_NAMES
        and (not name.startswith("_") or name in replay.bindings)
    }
    canonical_names = (
        runtime_surface_names
        | set(replay.bindings)
        | set(all_names)
        | set(STALE_EXPORT_REPAIRS)
    ) - set(constants)
    identity_index = _loaded_identity_index()
    exports: dict[str, Descriptor] = {}
    for name in sorted(canonical_names):
        if name in STALE_EXPORT_REPAIRS:
            descriptor = STALE_EXPORT_REPAIRS[name]
            _resolve(descriptor)
            exports[name] = descriptor
            continue
        if name in runtime:
            exports[name] = _descriptor_for_runtime_value(
                name,
                runtime[name],
                replay.bindings.get(name),
                identity_index,
            )
            continue
        if name in replay.bindings:
            descriptor = replay.bindings[name]
            _resolve(descriptor)
            exports[name] = descriptor
            continue
        raise SurfaceMigrationError(f"untraceable declared root name {name!r}")

    implicit_modules = {
        name: value.__name__
        for name, value in runtime.items()
        if name not in IGNORED_RUNTIME_NAMES
        and not name.startswith("_")
        and isinstance(value, types.ModuleType)
        and replay.bindings.get(name) != (value.__name__, None)
    }
    implicit_modules = dict(sorted(implicit_modules.items()))
    assigned_aliases = {
        name: descriptor
        for name, descriptor in sorted(replay.assigned_aliases.items())
        if exports.get(name) == descriptor
    }
    repaired_exports = dict(sorted(STALE_EXPORT_REPAIRS.items()))
    lazy_modules = tuple(
        sorted(
            {module for module, _attribute in exports.values()}
            | set(child_modules.values())
        )
    )
    conflicts = tuple(sorted(set(exports).intersection(child_modules)))
    source_digest = _sha256(source_bytes)
    all_digest = _all_digest(all_names)
    surface_digest = _sha256(
        _surface_payload(
            source_digest=source_digest,
            all_names=all_names,
            exports=exports,
            constants=dict(sorted(constants.items())),
            assigned_aliases=assigned_aliases,
            repaired_exports=repaired_exports,
            implicit_modules=implicit_modules,
            child_modules=child_modules,
            lazy_modules=lazy_modules,
            conflicts=conflicts,
            curated_exports={},
            curated_all=(),
        )
    )
    manifest = SurfaceManifest(
        source_digest=source_digest,
        all_digest=all_digest,
        surface_digest=surface_digest,
        all_names=all_names,
        exports=exports,
        constants=dict(sorted(constants.items())),
        assigned_aliases=assigned_aliases,
        repaired_exports=repaired_exports,
        implicit_modules=implicit_modules,
        child_modules=child_modules,
        lazy_modules=lazy_modules,
        export_child_conflicts=conflicts,
        curated_exports={},
        curated_all=(),
    )
    return _apply_curated_exports(manifest)


def _render_string_tuple(name: str, values: tuple[str, ...]) -> list[str]:
    lines = [f"{name} = ("]
    lines.extend(f"    {value!r}," for value in values)
    lines.append(")")
    return lines


def _render_descriptor_dict(name: str, values: dict[str, Descriptor]) -> list[str]:
    lines = [f"{name} = {{"]
    lines.extend(
        f"    {local!r}: ({module!r}, {attribute!r}),"
        for local, (module, attribute) in values.items()
    )
    lines.append("}")
    return lines


def _render_string_dict(name: str, values: dict[str, str]) -> list[str]:
    lines = [f"{name} = {{"]
    lines.extend(f"    {key!r}: {value!r}," for key, value in values.items())
    lines.append("}")
    return lines


def render_manifest(manifest: SurfaceManifest) -> str:
    """Render a deterministic Python data module."""

    lines = [
        '"""Generated lazy-root public-surface manifest; do not edit by hand."""',
        "",
        "# Generated by tools/migrate_public_surface.py.",
        f"MANIFEST_VERSION = {MANIFEST_VERSION}",
        f"SOURCE_DIGEST = {manifest.source_digest!r}",
        f"ALL_DIGEST = {manifest.all_digest!r}",
        f"SURFACE_DIGEST = {manifest.surface_digest!r}",
        "",
    ]
    lines.extend(_render_string_tuple("ALL", manifest.all_names))
    lines.append("")
    lines.extend(_render_descriptor_dict("EXPORTS", manifest.exports))
    lines.extend(["", "CONSTANTS = {"])
    lines.extend(f"    {name!r}: {value!r}," for name, value in manifest.constants.items())
    lines.extend(["}", ""])
    lines.extend(_render_descriptor_dict("ASSIGNED_ALIASES", manifest.assigned_aliases))
    lines.append("")
    lines.extend(_render_descriptor_dict("REPAIRED_EXPORTS", manifest.repaired_exports))
    lines.append("")
    lines.extend(_render_descriptor_dict("CURATED_EXPORTS", manifest.curated_exports))
    lines.append("")
    lines.extend(_render_string_tuple("CURATED_ALL", manifest.curated_all))
    lines.append("")
    lines.extend(_render_string_dict("IMPLICIT_MODULES", manifest.implicit_modules))
    lines.append("")
    lines.extend(_render_string_dict("CHILD_MODULES", manifest.child_modules))
    lines.append("")
    lines.extend(_render_string_tuple("LAZY_MODULES", manifest.lazy_modules))
    lines.append("")
    lines.extend(
        _render_string_tuple(
            "CANONICAL_EXPORT_CHILD_CONFLICTS",
            manifest.export_child_conflicts,
        )
    )
    lines.extend(
        [
            "",
            "# Short alias retained for checker and loader ergonomics.",
            "EXPORT_CHILD_CONFLICTS = CANONICAL_EXPORT_CHILD_CONFLICTS",
            "",
        ]
    )
    return "\n".join(lines)


def _stub_import(local: str, descriptor: Descriptor) -> str:
    module_name, attribute = descriptor
    if attribute is None:
        child_name = module_name[len(PACKAGE_NAME) + 1 :]
        if module_name.startswith(f"{PACKAGE_NAME}.") and "." not in child_name:
            return f"from . import {child_name} as {local}"
        return f"import {module_name} as {local}"
    if module_name.startswith(f"{PACKAGE_NAME}."):
        relative = module_name[len(PACKAGE_NAME) + 1 :]
        return f"from .{relative} import {attribute} as {local}"
    return f"from {module_name} import {attribute} as {local}"


def render_stub(manifest: SurfaceManifest) -> str:
    """Render the static root-package surface matching the runtime manifest."""

    lines = [
        '"""Generated static public surface for :mod:`glio_noncode`."""',
        "",
        "# Generated by tools/migrate_public_surface.py.",
    ]
    stub_exports = dict(manifest.exports)
    for name, module_name in manifest.child_modules.items():
        stub_exports.setdefault(name, (module_name, None))
    lines.extend(
        _stub_import(name, descriptor)
        for name, descriptor in sorted(stub_exports.items())
    )
    if manifest.constants:
        lines.append("")
        for name, value in manifest.constants.items():
            annotation = type(value).__name__
            if annotation not in {"bool", "bytes", "float", "int", "str"}:
                annotation = "object"
            lines.append(f"{name}: {annotation}")
    lines.extend(["", "__all__: list[str]", ""])
    return "\n".join(lines)


def validate_manifest(manifest: SurfaceManifest, repo_root: Path | None = None) -> None:
    """Validate every descriptor and every derived manifest invariant."""

    root = (repo_root or repository_root()).resolve()
    source_root = root / "src"
    package_dir = source_root / PACKAGE_NAME
    source_root_text = str(source_root)
    if source_root_text not in sys.path:
        sys.path.insert(0, source_root_text)
    package = importlib.import_module(PACKAGE_NAME)
    initializer = package_dir / "__init__.py"
    source_bytes = initializer.read_bytes()
    tree = ast.parse(source_bytes.decode("utf-8"), filename=str(initializer))
    lazy_mode = _is_lazy_initializer(tree)
    if not lazy_mode and manifest.source_digest != _sha256(source_bytes):
        raise SurfaceMigrationError("SOURCE_DIGEST does not match glio_noncode.__init__")
    if len(manifest.source_digest) != 64 or any(
        character not in "0123456789abcdef" for character in manifest.source_digest
    ):
        raise SurfaceMigrationError("SOURCE_DIGEST is not a lowercase SHA-256 digest")
    if manifest.all_names != tuple(package.__all__):
        raise SurfaceMigrationError("ALL differs from the root package __all__ sequence")
    if manifest.all_digest != _all_digest(manifest.all_names):
        raise SurfaceMigrationError("ALL_DIGEST does not match ALL")
    if tuple(manifest.exports) != tuple(sorted(manifest.exports)):
        raise SurfaceMigrationError("EXPORTS is not sorted by local name")
    if tuple(manifest.constants) != tuple(sorted(manifest.constants)):
        raise SurfaceMigrationError("CONSTANTS is not sorted by local name")
    if tuple(manifest.assigned_aliases) != tuple(sorted(manifest.assigned_aliases)):
        raise SurfaceMigrationError("ASSIGNED_ALIASES is not sorted by local name")
    if tuple(manifest.repaired_exports) != tuple(sorted(manifest.repaired_exports)):
        raise SurfaceMigrationError("REPAIRED_EXPORTS is not sorted by local name")
    if tuple(manifest.implicit_modules) != tuple(sorted(manifest.implicit_modules)):
        raise SurfaceMigrationError("IMPLICIT_MODULES is not sorted by local name")
    if tuple(manifest.child_modules) != tuple(sorted(manifest.child_modules)):
        raise SurfaceMigrationError("CHILD_MODULES is not sorted by local name")
    if manifest.curated_exports != CURATED_EXPORTS:
        raise SurfaceMigrationError("CURATED_EXPORTS differs from configured additions")
    if manifest.curated_all != tuple(CURATED_EXPORTS):
        raise SurfaceMigrationError("CURATED_ALL differs from configured addition order")
    if manifest.curated_all and (
        manifest.all_names[-len(manifest.curated_all) :] != manifest.curated_all
    ):
        raise SurfaceMigrationError("curated names are not the ALL suffix")
    duplicate_curated = [
        name for name in manifest.curated_all if manifest.all_names.count(name) != 1
    ]
    if duplicate_curated:
        raise SurfaceMigrationError(
            f"curated names must occur exactly once in ALL: {duplicate_curated!r}"
        )
    for name, descriptor in manifest.curated_exports.items():
        if manifest.exports.get(name) != descriptor:
            raise SurfaceMigrationError(
                f"curated export {name!r} differs from its configured descriptor"
            )
    if set(manifest.all_names) - set(manifest.exports):
        missing = sorted(set(manifest.all_names) - set(manifest.exports))
        raise SurfaceMigrationError(f"ALL has names missing from EXPORTS: {missing!r}")
    overlap = sorted(set(manifest.exports).intersection(manifest.constants))
    if overlap:
        raise SurfaceMigrationError(f"exports overlap literal constants: {overlap!r}")

    discovered_children = _discover_child_modules(package_dir)
    if manifest.child_modules != discovered_children:
        added = sorted(set(discovered_children) - set(manifest.child_modules))
        removed = sorted(set(manifest.child_modules) - set(discovered_children))
        changed = sorted(
            name
            for name in set(discovered_children).intersection(manifest.child_modules)
            if discovered_children[name] != manifest.child_modules[name]
        )
        raise SurfaceMigrationError(
            "CHILD_MODULES differs from the package directory: "
            f"added={added!r}, removed={removed!r}, changed={changed!r}"
        )

    runtime = vars(package)
    for name, descriptor in manifest.exports.items():
        value = _resolve(descriptor)
        if name in STALE_EXPORT_REPAIRS and descriptor != STALE_EXPORT_REPAIRS[name]:
            raise SurfaceMigrationError(f"stale repair {name!r} has wrong descriptor")
        if lazy_mode:
            root_value = getattr(package, name)
            if root_value is not value:
                raise SurfaceMigrationError(
                    f"lazy root identity for {name!r} differs from its descriptor"
                )
        elif name not in STALE_EXPORT_REPAIRS and (
            name not in runtime or runtime[name] is not value
        ):
            raise SurfaceMigrationError(
                f"descriptor for {name!r} does not preserve eager runtime identity"
            )

    for name, value in manifest.constants.items():
        if getattr(package, name, object()) != value:
            raise SurfaceMigrationError(f"constant {name!r} differs from root runtime")
    for name, descriptor in manifest.assigned_aliases.items():
        if manifest.exports.get(name) != descriptor:
            raise SurfaceMigrationError(f"assigned alias {name!r} differs from EXPORTS")
    if manifest.repaired_exports != dict(sorted(STALE_EXPORT_REPAIRS.items())):
        raise SurfaceMigrationError("REPAIRED_EXPORTS differs from required repairs")
    for name, module_name in manifest.implicit_modules.items():
        if manifest.exports.get(name) != (module_name, None):
            raise SurfaceMigrationError(
                f"implicit module {name!r} differs from its canonical descriptor"
            )
    expected_conflicts = tuple(
        sorted(set(manifest.exports).intersection(manifest.child_modules))
    )
    if manifest.export_child_conflicts != expected_conflicts:
        raise SurfaceMigrationError("canonical export/child-module conflicts are stale")
    expected_lazy_modules = tuple(
        sorted(
            {module for module, _attribute in manifest.exports.values()}
            | set(manifest.child_modules.values())
        )
    )
    if manifest.lazy_modules != expected_lazy_modules:
        raise SurfaceMigrationError("LAZY_MODULES is stale or unsorted")
    expected_surface_digest = _sha256(
        _surface_payload(
            source_digest=manifest.source_digest,
            all_names=manifest.all_names,
            exports=manifest.exports,
            constants=manifest.constants,
            assigned_aliases=manifest.assigned_aliases,
            repaired_exports=manifest.repaired_exports,
            implicit_modules=manifest.implicit_modules,
            child_modules=manifest.child_modules,
            lazy_modules=manifest.lazy_modules,
            conflicts=manifest.export_child_conflicts,
            curated_exports=manifest.curated_exports,
            curated_all=manifest.curated_all,
        )
    )
    if manifest.surface_digest != expected_surface_digest:
        raise SurfaceMigrationError("SURFACE_DIGEST does not match manifest content")


def generated_paths(repo_root: Path | None = None) -> tuple[Path, Path]:
    root = (repo_root or repository_root()).resolve()
    package_dir = root / "src" / PACKAGE_NAME
    return package_dir / "_public_surface.py", package_dir / "__init__.pyi"


def write_generated(manifest: SurfaceManifest, repo_root: Path | None = None) -> None:
    manifest_path, stub_path = generated_paths(repo_root)
    manifest_path.write_text(render_manifest(manifest), encoding="utf-8", newline="\n")
    stub_path.write_text(render_stub(manifest), encoding="utf-8", newline="\n")


def check_generated(manifest: SurfaceManifest, repo_root: Path | None = None) -> None:
    manifest_path, stub_path = generated_paths(repo_root)
    expected = {
        manifest_path: render_manifest(manifest),
        stub_path: render_stub(manifest),
    }
    stale = [
        str(path)
        for path, content in expected.items()
        if not path.is_file() or path.read_text(encoding="utf-8") != content
    ]
    if stale:
        raise SurfaceMigrationError(
            "generated public-surface files are stale: " + ", ".join(stale)
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate descriptors and fail if generated files differ",
    )
    args = parser.parse_args(argv)
    manifest = build_manifest()
    if args.check:
        validate_manifest(manifest)
        check_generated(manifest)
        print(
            f"public surface is current: {len(manifest.exports)} descriptors, "
            f"{len(manifest.all_names)} __all__ entries, {manifest.surface_digest}"
        )
    else:
        write_generated(manifest)
        importlib.invalidate_caches()
        surface_name = f"{PACKAGE_NAME}._public_surface"
        if surface_name in sys.modules:
            importlib.reload(sys.modules[surface_name])
        if PACKAGE_NAME in sys.modules:
            importlib.reload(sys.modules[PACKAGE_NAME])
        manifest = build_manifest()
        validate_manifest(manifest)
        check_generated(manifest)
        print(
            f"wrote public surface: {len(manifest.exports)} descriptors, "
            f"{len(manifest.all_names)} __all__ entries, {manifest.surface_digest}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
