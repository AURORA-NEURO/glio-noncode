"""Focused contracts for static certification lineage and quality reporting."""

from __future__ import annotations

import csv
import io
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.module_certification import build_module_certification
from glio_noncode.module_certification_lineage import (
    build_module_certification_lineage,
    module_certification_evidence_csv,
    module_certification_lineage_capabilities,
    module_certification_lineage_edges_csv,
    module_certification_lineage_json,
    module_certification_lineage_schema,
    query_module_certification_lineage,
    render_module_certification_lineage_markdown,
    verify_module_certification_lineage,
)
from glio_noncode.module_certification_lineage_contracts import (
    CertificationEvidenceKind,
    CertificationLineageRelation,
    CertificationLineageTargetKind,
)
from glio_noncode.module_certification_quality import (
    build_module_certification_quality,
    module_certification_family_csv,
    module_certification_quality_capabilities,
    module_certification_quality_csv,
    module_certification_quality_json,
    module_certification_quality_schema,
    query_module_certification_quality,
    render_module_certification_quality_markdown,
    verify_module_certification_quality,
)
from glio_noncode.module_certification_quality_contracts import CertificationReadiness
from glio_noncode.module_inventory import build_module_inventory


class LineageQualityFixture(unittest.TestCase):
    """Build small repository snapshots with explicit source/test/doc evidence."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "src" / "glio_noncode"
        self.tests = self.root / "tests"
        self.docs = self.root / "docs"
        self.source.mkdir(parents=True)
        self.tests.mkdir()
        self.docs.mkdir()
        (self.source / "__init__.py").write_text(
            "from . import alpha\n",
            encoding="utf-8",
        )
        (self.source / "alpha.py").write_text(
            "from .beta import helper\n\n"
            "class Alpha:\n    pass\n\n"
            "def public_api(value: int) -> int:\n    return helper(value)\n",
            encoding="utf-8",
        )
        (self.source / "beta.py").write_text(
            "def helper(value: int) -> int:\n    return value + 1\n",
            encoding="utf-8",
        )
        (self.tests / "test_alpha.py").write_text(
            "from glio_noncode.alpha import public_api\n\n"
            "def test_alpha_contract():\n    assert public_api(1) == 2\n",
            encoding="utf-8",
        )
        (self.docs / "ALPHA.md").write_text(
            "# Alpha\n\nThe `glio_noncode.alpha` module uses `beta.py`.\n",
            encoding="utf-8",
        )
        self.inventory = build_module_inventory(self.source, test_root=self.tests)
        self.matrix = build_module_certification(
            self.inventory,
            source_root=self.source,
            test_root=self.tests,
            docs_root=self.docs,
        )
        self.lineage = build_module_certification_lineage(
            self.inventory,
            matrix=self.matrix,
            source_root=self.source,
            test_root=self.tests,
            docs_root=self.docs,
        )
        self.quality = build_module_certification_quality(self.matrix, self.lineage)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_fixture_has_expected_module_rows(self) -> None:
        self.assertEqual(self.inventory.module_count, 3)
        self.assertEqual(
            {item.module_id for item in self.inventory.modules},
            {"glio_noncode", "glio_noncode.alpha", "glio_noncode.beta"},
        )
        self.assertEqual(self.matrix.module_count, self.inventory.module_count)

    def test_source_evidence_conserves_modules(self) -> None:
        source = [
            item for item in self.lineage.evidence if item.kind is CertificationEvidenceKind.SOURCE
        ]
        self.assertEqual(len(source), self.inventory.module_count)
        self.assertEqual(self.lineage.source_count, self.inventory.module_count)
        self.assertTrue(all(item.line_count > 0 for item in source))
        self.assertTrue(
            all("/" not in item.evidence_id or ":" in item.evidence_id for item in source)
        )

    def test_test_and_documentation_evidence_is_explicit(self) -> None:
        test_rows = [
            item for item in self.lineage.evidence if item.kind is CertificationEvidenceKind.TEST
        ]
        documentation = [
            item
            for item in self.lineage.evidence
            if item.kind is CertificationEvidenceKind.DOCUMENTATION
        ]
        self.assertTrue(any(item.module_id == "glio_noncode.alpha" for item in test_rows))
        self.assertTrue(any(item.module_id == "glio_noncode.alpha" for item in documentation))
        self.assertTrue(all(item.relative_path == "test_alpha.py" for item in test_rows))
        self.assertTrue(all(item.relative_path == "ALPHA.md" for item in documentation))
        self.assertEqual(self.lineage.test_count, 1)
        self.assertEqual(self.lineage.documentation_count, 2)

    def test_export_evidence_comes_from_package_ast(self) -> None:
        exports = [
            item for item in self.lineage.evidence if item.kind is CertificationEvidenceKind.EXPORT
        ]
        self.assertTrue(any(item.module_id == "glio_noncode" for item in exports))
        self.assertTrue(any(item.module_id == "glio_noncode.alpha" for item in exports))
        self.assertEqual(self.lineage.export_count, 2)
        self.assertTrue(all(item.relative_path == "__init__.py" for item in exports))

    def test_dependency_edges_retain_resolution(self) -> None:
        dependencies = [
            item
            for item in self.lineage.edges
            if item.target_kind is CertificationLineageTargetKind.MODULE
        ]
        self.assertTrue(dependencies)
        alpha_edges = [item for item in dependencies if item.source_module == "glio_noncode.alpha"]
        self.assertTrue(any(item.target_id == "glio_noncode.beta" for item in alpha_edges))
        self.assertTrue(
            all(item.relation is CertificationLineageRelation.DEPENDS_ON for item in dependencies)
        )
        self.assertTrue(all(item.resolved for item in dependencies))
        self.assertEqual(
            self.lineage.relation_counts[CertificationLineageRelation.DEPENDS_ON.value],
            len(dependencies),
        )

    def test_each_evidence_row_has_a_support_edge(self) -> None:
        evidence_ids = {item.evidence_id for item in self.lineage.evidence}
        evidence_edges = {
            item.target_id
            for item in self.lineage.edges
            if item.target_kind is CertificationLineageTargetKind.EVIDENCE
        }
        self.assertEqual(evidence_edges, evidence_ids)
        self.assertTrue(
            all(
                item.relation
                in {CertificationLineageRelation.SUPPORTS, CertificationLineageRelation.EXPORTS}
                for item in self.lineage.edges
                if item.target_kind is CertificationLineageTargetKind.EVIDENCE
            )
        )

    def test_lineage_is_deterministic(self) -> None:
        again = build_module_certification_lineage(
            self.inventory,
            matrix=self.matrix,
            source_root=self.source,
            test_root=self.tests,
            docs_root=self.docs,
        )
        self.assertEqual(self.lineage.content_address, again.content_address)
        self.assertEqual(self.lineage.to_dict(), again.to_dict())
        self.assertEqual(
            module_certification_lineage_json(self.lineage),
            module_certification_lineage_json(again),
        )

    def test_lineage_verifier_accepts_fresh_build(self) -> None:
        self.assertIs(verify_module_certification_lineage(self.lineage), self.lineage)

    def test_lineage_verifier_rejects_tampered_evidence(self) -> None:
        original = self.lineage.evidence[0]
        altered = replace(original, detail="changed detail")
        tampered = replace(self.lineage, evidence=(altered,) + self.lineage.evidence[1:])
        with self.assertRaises(ValidationError):
            verify_module_certification_lineage(tampered)

    def test_lineage_verifier_rejects_wrong_type(self) -> None:
        with self.assertRaises(ValidationError):
            verify_module_certification_lineage({})  # type: ignore[arg-type]

    def test_lineage_queries_are_bounded_and_filterable(self) -> None:
        evidence = query_module_certification_lineage(
            self.lineage,
            resource="evidence",
            module_id="glio_noncode.alpha",
            kind="test",
            limit=1,
        )
        self.assertEqual(evidence["total"], 1)
        self.assertFalse(evidence["has_more"])
        self.assertEqual(evidence["items"][0]["relative_path"], "test_alpha.py")
        edges = query_module_certification_lineage(
            self.lineage,
            resource="edges",
            relation="depends_on",
            resolved=True,
            limit=10,
        )
        self.assertTrue(edges["items"])
        modules = query_module_certification_lineage(self.lineage, resource="modules", limit=10)
        self.assertEqual(modules["total"], 3)
        self.assertEqual(modules["items"][0]["module_id"], "glio_noncode")

    def test_lineage_queries_reject_invalid_input(self) -> None:
        with self.assertRaises(ValidationError):
            query_module_certification_lineage(self.lineage, resource="nope")
        with self.assertRaises(ValidationError):
            query_module_certification_lineage(self.lineage, offset=-1)
        with self.assertRaises(ValidationError):
            query_module_certification_lineage(self.lineage, limit=513)

    def test_lineage_query_has_content_address(self) -> None:
        result = query_module_certification_lineage(self.lineage, resource="modules")
        self.assertTrue(result["content_address"].startswith("module-certification-lineage-query:"))
        self.assertEqual(result["lineage_address"], self.lineage.content_address)

    def test_lineage_csv_exports_are_parseable(self) -> None:
        evidence = list(
            csv.DictReader(io.StringIO(module_certification_evidence_csv(self.lineage)))
        )
        edges = list(
            csv.DictReader(io.StringIO(module_certification_lineage_edges_csv(self.lineage)))
        )
        self.assertEqual(len(evidence), self.lineage.evidence_count)
        self.assertEqual(len(edges), self.lineage.edge_count)
        self.assertEqual(
            set(evidence[0]),
            {
                "evidence_id",
                "module_id",
                "kind",
                "relative_path",
                "relation",
                "detail",
                "source_digest",
                "line_count",
                "content_address",
            },
        )
        self.assertIn("evidence_ids", edges[0])

    def test_lineage_markdown_contains_structure_not_source_payload(self) -> None:
        markdown = render_module_certification_lineage_markdown(self.lineage)
        self.assertIn("Module certification evidence lineage", markdown)
        self.assertIn("test_alpha.py", markdown)
        self.assertNotIn("return value + 1", markdown)

    def test_lineage_schema_and_capabilities_are_machine_readable(self) -> None:
        schema = module_certification_lineage_schema()
        capabilities = module_certification_lineage_capabilities()
        self.assertEqual(schema["resources"], ["evidence", "edges", "modules"])
        self.assertEqual(capabilities["operation_count"], len(capabilities["operations"]))
        self.assertTrue(capabilities["static_only"])
        self.assertFalse(capabilities["absolute_paths"])

    def test_lineage_public_output_excludes_absolute_paths(self) -> None:
        encoded = json.dumps(self.lineage.to_dict(), sort_keys=True)
        self.assertNotIn(str(self.root), encoded)
        self.assertNotIn("\\", encoded)

    def test_quality_check_counts_conserve(self) -> None:
        for item in self.quality.check_coverage:
            self.assertEqual(item.passed_count + item.failed_count, item.applicable_count)
            self.assertEqual(item.applicable_count + item.not_applicable_count, item.module_count)
        self.assertEqual(len(self.quality.check_coverage), 8)

    def test_quality_family_counts_conserve(self) -> None:
        self.assertTrue(self.quality.family_coverage)
        self.assertEqual(
            sum(item.module_count for item in self.quality.family_coverage),
            self.matrix.module_count,
        )
        for item in self.quality.family_coverage:
            self.assertEqual(
                sum(
                    (
                        item.certified_count,
                        item.review_count,
                        item.blocked_count,
                        item.uncovered_count,
                    )
                ),
                item.module_count,
            )

    def test_quality_evidence_coverage_is_bounded(self) -> None:
        self.assertGreaterEqual(self.quality.evidence_coverage_percent, 0.0)
        self.assertLessEqual(self.quality.evidence_coverage_percent, 100.0)
        self.assertEqual(self.quality.overall_score, self.matrix.overall_score)

    def test_quality_readiness_reports_warning_for_review_rows(self) -> None:
        self.assertIn(
            self.quality.readiness, {CertificationReadiness.WARNING, CertificationReadiness.READY}
        )
        self.assertEqual(self.quality.blocker_modules, ())

    def test_quality_is_deterministic_and_verifiable(self) -> None:
        again = build_module_certification_quality(self.matrix, self.lineage)
        self.assertEqual(self.quality.content_address, again.content_address)
        self.assertEqual(
            module_certification_quality_json(self.quality),
            module_certification_quality_json(again),
        )
        self.assertIs(verify_module_certification_quality(self.quality), self.quality)

    def test_quality_rejects_lineage_from_another_matrix(self) -> None:
        other = replace(self.lineage, matrix_address="sha256:other")
        with self.assertRaises(ValidationError):
            build_module_certification_quality(self.matrix, other)

    def test_quality_verifier_rejects_tampered_measure(self) -> None:
        original = self.quality.check_coverage[0]
        altered = replace(original, pass_percent=0.0)
        tampered = replace(
            self.quality, check_coverage=(altered,) + self.quality.check_coverage[1:]
        )
        with self.assertRaises(ValidationError):
            verify_module_certification_quality(tampered)

    def test_quality_queries_cover_each_resource(self) -> None:
        for resource in ("checks", "families", "blockers", "gaps", "summary"):
            result = query_module_certification_quality(self.quality, resource=resource, limit=20)
            self.assertEqual(result["resource"], resource)
            self.assertIn("content_address", result)
        family = self.quality.family_coverage[0].family
        result = query_module_certification_quality(
            self.quality, resource="families", family=family, limit=10
        )
        self.assertEqual(result["total"], 1)

    def test_quality_queries_reject_invalid_paging(self) -> None:
        with self.assertRaises(ValidationError):
            query_module_certification_quality(self.quality, resource="unknown")
        with self.assertRaises(ValidationError):
            query_module_certification_quality(self.quality, offset=-1)
        with self.assertRaises(ValidationError):
            query_module_certification_quality(self.quality, limit=513)

    def test_quality_csv_exports_have_stable_headers(self) -> None:
        checks = list(csv.DictReader(io.StringIO(module_certification_quality_csv(self.quality))))
        families = list(csv.DictReader(io.StringIO(module_certification_family_csv(self.quality))))
        self.assertEqual(len(checks), len(self.quality.check_coverage))
        self.assertEqual(len(families), len(self.quality.family_coverage))
        self.assertIn("pass_percent", checks[0])
        self.assertIn("coverage_percent", families[0])

    def test_quality_markdown_contains_readiness_and_family(self) -> None:
        markdown = render_module_certification_quality_markdown(self.quality)
        self.assertIn("Module certification quality", markdown)
        self.assertIn(self.quality.readiness.value, markdown)
        self.assertIn(self.quality.family_coverage[0].family, markdown)

    def test_quality_schema_and_capabilities_are_complete(self) -> None:
        schema = module_certification_quality_schema()
        capabilities = module_certification_quality_capabilities()
        self.assertEqual(schema["resources"], ["checks", "families", "blockers", "gaps", "summary"])
        self.assertEqual(capabilities["operation_count"], len(capabilities["operations"]))
        self.assertIn("classify_release_readiness", capabilities["operations"])


class BlockingLineageQualityFixture(unittest.TestCase):
    """Ensure parse failures become visible release blockers."""

    def test_parse_failure_is_blocked_and_retained(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "src" / "glio_noncode"
            tests = root / "tests"
            docs = root / "docs"
            source.mkdir(parents=True)
            tests.mkdir()
            docs.mkdir()
            (source / "__init__.py").write_text("", encoding="utf-8")
            (source / "broken.py").write_text("def broken(:\n", encoding="utf-8")
            inventory = build_module_inventory(source, test_root=tests)
            matrix = build_module_certification(
                inventory, source_root=source, test_root=tests, docs_root=docs
            )
            lineage = build_module_certification_lineage(
                inventory,
                matrix=matrix,
                source_root=source,
                test_root=tests,
                docs_root=docs,
            )
            quality = build_module_certification_quality(matrix, lineage)
            self.assertTrue(inventory.accepted)
            self.assertEqual(quality.readiness, CertificationReadiness.BLOCKED)
            self.assertTrue(quality.blocker_modules)
            self.assertTrue(quality.accepted)
            self.assertTrue(any(item.module_id.endswith("broken") for item in lineage.evidence))


if __name__ == "__main__":
    unittest.main()
