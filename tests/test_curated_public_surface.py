"""Contract tests for curated post-migration scientific root exports."""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import importlib
import importlib.util
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from types import ModuleType
from typing import Any

import glio_noncode
from glio_noncode import _public_surface

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_TOOL = REPOSITORY_ROOT / "tools" / "migrate_public_surface.py"


def _load_migration_tool() -> ModuleType:
    specification = importlib.util.spec_from_file_location(
        "glio_noncode_curated_surface_test_support",
        MIGRATION_TOOL,
    )
    if specification is None or specification.loader is None:
        raise RuntimeError(f"cannot load {MIGRATION_TOOL}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


migration = _load_migration_tool()


def _resolve(descriptor: tuple[str, str | None]) -> object:
    module_name, attribute = descriptor
    module = importlib.import_module(module_name)
    return module if attribute is None else getattr(module, attribute)


def _root(name: str) -> object:
    return getattr(glio_noncode, name)


class CuratedPublicSurfaceTests(unittest.TestCase):
    manifest: Any

    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = migration.build_manifest(REPOSITORY_ROOT)

    def test_generated_curated_contract_matches_configuration_exactly(self) -> None:
        expected = migration.CURATED_EXPORTS
        self.assertEqual(_public_surface.CURATED_EXPORTS, expected)
        self.assertEqual(_public_surface.CURATED_ALL, tuple(expected))
        self.assertEqual(_public_surface.ALL[-len(expected) :], tuple(expected))
        self.assertEqual(len(expected), 233)
        for name, descriptor in expected.items():
            self.assertEqual(_public_surface.ALL.count(name), 1, name)
            self.assertEqual(_public_surface.EXPORTS[name], descriptor)

        legacy_all = _public_surface.ALL[: -len(expected)]
        payload = json.dumps(
            legacy_all,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        self.assertEqual(hashlib.sha256(payload).hexdigest(), migration.LEGACY_ALL_DIGEST)

    def test_every_curated_descriptor_resolves_through_the_lazy_root(self) -> None:
        for name, descriptor in migration.CURATED_EXPORTS.items():
            self.assertIs(getattr(glio_noncode, name), _resolve(descriptor), name)

        self.assertIs(
            _root("case_workflow_capabilities"),
            importlib.import_module("glio_noncode.case_workflow").capabilities,
        )
        self.assertIs(
            _root("expression_evidence_public_projection"),
            importlib.import_module("glio_noncode.expression_evidence").public_projection,
        )
        self.assertIs(
            _root("expression_claim_public_projection"),
            importlib.import_module("glio_noncode.expression_claims").public_projection,
        )
        self.assertEqual(
            _root("EXPRESSION_EVIDENCE_SCHEMA_VERSION"),
            importlib.import_module("glio_noncode.expression_evidence").SCHEMA_VERSION,
        )
        self.assertEqual(
            _root("EXPRESSION_CLAIMS_SCHEMA_VERSION"),
            importlib.import_module("glio_noncode.expression_claims").SCHEMA_VERSION,
        )

    def test_operational_contracts_keep_canonical_module_identity(self) -> None:
        expected_identities = {
            "AtlasObservation": ("glio_noncode.atlas", "AtlasObservation"),
            "ReferenceBundleProvider": (
                "glio_noncode.atlas",
                "ReferenceBundleProvider",
            ),
            "EncodeProvider": ("glio_noncode.atlas", "EncodeProvider"),
            "EvidenceGraph": ("glio_noncode.evidence", "EvidenceGraph"),
            "AggregateSupport": ("glio_noncode.evidence", "AggregateSupport"),
            "EvidenceGraphLimits": (
                "glio_noncode.evidence",
                "EvidenceGraphLimits",
            ),
            "FetchReceipt": ("glio_noncode.data_sources", "FetchReceipt"),
            "ReferenceRetrievalLimits": (
                "glio_noncode.data_sources",
                "ReferenceRetrievalLimits",
            ),
            "PublicReferenceRetriever": (
                "glio_noncode.data_sources",
                "PublicReferenceRetriever",
            ),
            "PolicyDecision": ("glio_noncode.policy", "PolicyDecision"),
            "PolicyLimits": ("glio_noncode.policy", "PolicyLimits"),
            "ResearchPolicy": ("glio_noncode.policy", "ResearchPolicy"),
            "ExperimentPlanningLimits": (
                "glio_noncode.experiments",
                "ExperimentPlanningLimits",
            ),
            "ExperimentPlanner": (
                "glio_noncode.experiments",
                "ExperimentPlanner",
            ),
            "BuiltHypotheses": ("glio_noncode.hypotheses", "BuiltHypotheses"),
            "HypothesisWorkLimits": (
                "glio_noncode.hypotheses",
                "HypothesisWorkLimits",
            ),
            "HypothesisBuilder": (
                "glio_noncode.hypotheses",
                "HypothesisBuilder",
            ),
            "RuntimeEvent": ("glio_noncode.events", "RuntimeEvent"),
            "EventLog": ("glio_noncode.events", "EventLog"),
            "ValidationLimits": (
                "glio_noncode.validation",
                "ValidationLimits",
            ),
            "ValidationReport": (
                "glio_noncode.validation",
                "ValidationReport",
            ),
            "ContractValidator": (
                "glio_noncode.validation",
                "ContractValidator",
            ),
            "ReleaseGate": ("glio_noncode.validation", "ReleaseGate"),
            "ADAPTER_CLAIM_COLLECTION_VERSION": (
                "glio_noncode.adapters",
                "ADAPTER_CLAIM_COLLECTION_VERSION",
            ),
            "ADAPTER_HARD_MAX_CLAIMS_TOTAL": (
                "glio_noncode.adapters",
                "ADAPTER_HARD_MAX_CLAIMS_TOTAL",
            ),
            "AdapterClaimAttribution": (
                "glio_noncode.adapters",
                "AdapterClaimAttribution",
            ),
            "AdapterClaimCollectionReport": (
                "glio_noncode.adapters",
                "AdapterClaimCollectionReport",
            ),
        }
        for public_name, descriptor in expected_identities.items():
            self.assertEqual(migration.CURATED_EXPORTS[public_name], descriptor)
            self.assertIs(getattr(glio_noncode, public_name), _resolve(descriptor))

    def test_public_reference_bundle_alias_does_not_replace_legacy_name(self) -> None:
        public_reference = importlib.import_module("glio_noncode.data_sources").ReferenceBundle
        legacy_reference = importlib.import_module(
            "glio_noncode.frontier_data_alpha"
        ).ReferenceBundle

        self.assertEqual(
            migration.CURATED_EXPORTS["PublicReferenceBundle"],
            ("glio_noncode.data_sources", "ReferenceBundle"),
        )
        self.assertIs(_root("PublicReferenceBundle"), public_reference)
        self.assertIs(_root("ReferenceBundle"), legacy_reference)
        self.assertIsNot(
            _root("PublicReferenceBundle"),
            _root("ReferenceBundle"),
        )

    def test_existing_atlas_root_bindings_are_not_reclassified_as_curated(self) -> None:
        atlas = importlib.import_module("glio_noncode.atlas")
        for name in ("AtlasQuery", "AtlasBundle", "PublicAtlasRetriever"):
            self.assertNotIn(name, migration.CURATED_EXPORTS)
            self.assertIs(getattr(glio_noncode, name), getattr(atlas, name))

    def test_existing_runtime_root_bindings_are_not_reclassified_as_curated(self) -> None:
        expected_identities = {
            "CaseRuntime": ("glio_noncode.runtime", "CaseRuntime"),
            "RunInspection": ("glio_noncode.run_catalog", "RunInspection"),
            "inspect_run": ("glio_noncode.run_catalog", "inspect_run"),
        }
        for name, descriptor in expected_identities.items():
            self.assertNotIn(name, migration.CURATED_EXPORTS)
            self.assertEqual(_public_surface.EXPORTS[name], descriptor)
            self.assertIs(getattr(glio_noncode, name), _resolve(descriptor))

    def test_report_aliases_preserve_canonical_callable_identity(self) -> None:
        reports = importlib.import_module("glio_noncode.reports")
        expected_aliases = {
            "summarize_report_dossier": "summarize",
            "build_dossier_report": "build_report",
            "render_dossier_markdown": "render_markdown",
            "render_dossier_json": "render_json",
            "render_dossier_report": "render_report",
            "render_dossier_report_json": "render_report_json",
            "render_dossier_report_markdown": "render_report_markdown",
            "dossier_report_capabilities": "report_capabilities",
        }
        for public_name, canonical_name in expected_aliases.items():
            self.assertIs(getattr(glio_noncode, public_name), getattr(reports, canonical_name))

    def test_run_assessment_exports_preserve_canonical_identity(self) -> None:
        assessments = importlib.import_module("glio_noncode.assessments")
        expected = {
            "RUN_ASSESSMENT_VERSION": "RUN_ASSESSMENT_VERSION",
            "MAX_RUN_ASSESSMENT_BYTES": "MAX_RUN_ASSESSMENT_BYTES",
            "VerifiedRunAssessment": "VerifiedRunAssessment",
            "build_run_assessment": "build_run_assessment",
            "run_assessment_capabilities": "assessment_capabilities",
        }
        for public_name, canonical_name in expected.items():
            self.assertIs(
                getattr(glio_noncode, public_name),
                getattr(assessments, canonical_name),
            )

    def test_static_stub_declares_every_curated_name(self) -> None:
        stub_path = REPOSITORY_ROOT / "src" / "glio_noncode" / "__init__.pyi"
        tree = ast.parse(stub_path.read_text(encoding="utf-8"), filename=str(stub_path))
        names: set[str] = set()
        for statement in tree.body:
            if isinstance(statement, ast.ImportFrom):
                names.update(alias.asname or alias.name for alias in statement.names)
            elif isinstance(statement, ast.Import):
                names.update(alias.asname or alias.name for alias in statement.names)
        self.assertEqual(set(migration.CURATED_EXPORTS) - names, set())

    def test_rendering_and_regeneration_inputs_are_byte_deterministic(self) -> None:
        repeated = migration.build_manifest(REPOSITORY_ROOT)
        self.assertEqual(repeated, self.manifest)
        manifest_path, stub_path = migration.generated_paths(REPOSITORY_ROOT)
        self.assertEqual(
            manifest_path.read_text(encoding="utf-8"),
            migration.render_manifest(self.manifest),
        )
        self.assertEqual(
            stub_path.read_text(encoding="utf-8"),
            migration.render_stub(self.manifest),
        )
        migration.check_generated(self.manifest, REPOSITORY_ROOT)

    def test_checker_rejects_stale_curated_configuration_metadata(self) -> None:
        stale_exports = dict(self.manifest.curated_exports)
        stale_exports.pop("prepare_case")
        stale = dataclasses.replace(self.manifest, curated_exports=stale_exports)
        with self.assertRaisesRegex(
            migration.SurfaceMigrationError,
            "CURATED_EXPORTS differs from configured additions",
        ):
            migration.validate_manifest(stale, REPOSITORY_ROOT)

    def test_plain_import_still_loads_only_manifest_and_package(self) -> None:
        code = """
import json
import sys
import glio_noncode
print(json.dumps(sorted(
    name for name in sys.modules
    if name == "glio_noncode" or name.startswith("glio_noncode.")
)))
"""
        environment = os.environ.copy()
        source_root = str(REPOSITORY_ROOT / "src")
        existing = environment.get("PYTHONPATH")
        environment["PYTHONPATH"] = (
            source_root if not existing else source_root + os.pathsep + existing
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=REPOSITORY_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout),
            ["glio_noncode", "glio_noncode._public_surface"],
        )


if __name__ == "__main__":
    unittest.main()
