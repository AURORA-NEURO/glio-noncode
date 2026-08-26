"""Cross-artifact release and independent lineage-audit contract tests."""

from __future__ import annotations

import csv
import io
import json
import unittest
from dataclasses import replace

from glio_noncode.errors import ValidationError
from glio_noncode.module_certification_lineage_audit import (
    build_module_certification_lineage_audit,
    module_certification_lineage_audit_capabilities,
    module_certification_lineage_audit_csv,
    module_certification_lineage_audit_json,
    module_certification_lineage_audit_schema,
    query_module_certification_lineage_audit,
    verify_module_certification_lineage_audit,
)
from glio_noncode.module_certification_lineage_audit_contracts import (
    CertificationLineageAuditPlane,
)
from glio_noncode.module_certification_release import (
    build_module_certification_release,
    module_certification_release_capabilities,
    module_certification_release_checks_csv,
    module_certification_release_json,
    module_certification_release_schema,
    query_module_certification_release,
    render_module_certification_release_markdown,
    verify_module_certification_release,
)
from glio_noncode.module_certification_release_contracts import CertificationReleasePlane
from tests.test_module_certification_lineage_quality import LineageQualityFixture


class CertificationReleaseFixture(LineageQualityFixture):
    """Reuse the deterministic three-module source fixture for release checks."""

    def setUp(self) -> None:
        super().setUp()
        self.audit = build_module_certification_lineage_audit(self.lineage)
        self.release = build_module_certification_release(
            self.matrix,
            self.lineage,
            self.quality,
        )

    def test_audit_has_independent_check_planes(self) -> None:
        planes = {item.plane for item in self.audit.checks}
        self.assertTrue(planes)
        self.assertIn(CertificationLineageAuditPlane.IDENTITY, planes)
        self.assertIn(CertificationLineageAuditPlane.GRAPH, planes)
        self.assertIn(CertificationLineageAuditPlane.PUBLIC, planes)
        self.assertEqual(self.audit.passed_count + self.audit.failed_count, self.audit.check_count)

    def test_audit_accepts_fresh_lineage(self) -> None:
        self.assertTrue(self.audit.accepted, self.audit.to_dict())
        self.assertIs(verify_module_certification_lineage_audit(self.audit), self.audit)

    def test_audit_is_deterministic(self) -> None:
        again = build_module_certification_lineage_audit(self.lineage)
        self.assertEqual(self.audit.content_address, again.content_address)
        self.assertEqual(
            module_certification_lineage_audit_json(self.audit),
            module_certification_lineage_audit_json(again),
        )

    def test_audit_rejects_tampered_check(self) -> None:
        original = self.audit.checks[0]
        altered = replace(original, detail="tampered")
        tampered = replace(self.audit, checks=(altered,) + self.audit.checks[1:])
        with self.assertRaises(ValidationError):
            verify_module_certification_lineage_audit(tampered)

    def test_audit_rejects_wrong_type(self) -> None:
        with self.assertRaises(ValidationError):
            verify_module_certification_lineage_audit({})  # type: ignore[arg-type]

    def test_audit_query_filters_plane(self) -> None:
        result = query_module_certification_lineage_audit(
            self.audit,
            plane=CertificationLineageAuditPlane.GRAPH.value,
            limit=50,
        )
        self.assertTrue(result["items"])
        self.assertTrue(all(item["plane"] == "graph" for item in result["items"]))
        self.assertEqual(result["audit_address"], self.audit.content_address)

    def test_audit_query_filters_failed_state(self) -> None:
        result = query_module_certification_lineage_audit(self.audit, passed=False, limit=10)
        self.assertEqual(result["total"], self.audit.failed_count)
        self.assertFalse(result["items"])

    def test_audit_query_rejects_invalid_page(self) -> None:
        with self.assertRaises(ValidationError):
            query_module_certification_lineage_audit(self.audit, offset=-1)
        with self.assertRaises(ValidationError):
            query_module_certification_lineage_audit(self.audit, limit=513)

    def test_audit_csv_has_one_row_per_check(self) -> None:
        rows = list(csv.DictReader(io.StringIO(module_certification_lineage_audit_csv(self.audit))))
        self.assertEqual(len(rows), self.audit.check_count)
        self.assertEqual(rows[0]["check_id"], self.audit.checks[0].check_id)

    def test_audit_schema_and_capabilities_are_complete(self) -> None:
        schema = module_certification_lineage_audit_schema()
        capabilities = module_certification_lineage_audit_capabilities()
        self.assertEqual(schema["version"], "module-certification-lineage-audit-v1")
        self.assertEqual(capabilities["operation_count"], len(capabilities["operations"]))
        self.assertTrue(capabilities["independent"])

    def test_release_reconciles_component_addresses(self) -> None:
        self.assertEqual(self.release.matrix_address, self.matrix.content_address)
        self.assertEqual(self.release.lineage_address, self.lineage.content_address)
        self.assertEqual(self.release.quality_address, self.quality.content_address)
        self.assertEqual(
            self.release.passed_count + self.release.failed_count,
            self.release.check_count,
        )

    def test_release_has_all_planes(self) -> None:
        planes = {item.plane for item in self.release.checks}
        self.assertEqual(
            planes,
            {
                CertificationReleasePlane.MATRIX,
                CertificationReleasePlane.LINEAGE,
                CertificationReleasePlane.QUALITY,
                CertificationReleasePlane.BOUNDARY,
            },
        )

    def test_release_accepts_structural_warning_report(self) -> None:
        self.assertTrue(self.release.accepted, self.release.to_dict())
        self.assertFalse(self.release.release_eligible)
        self.assertEqual(self.release.readiness, self.quality.readiness.value)
        self.assertTrue(self.release.recommended_actions)

    def test_release_is_deterministic_and_verifiable(self) -> None:
        again = build_module_certification_release(self.matrix, self.lineage, self.quality)
        self.assertEqual(self.release.content_address, again.content_address)
        self.assertEqual(
            module_certification_release_json(self.release),
            module_certification_release_json(again),
        )
        self.assertIs(verify_module_certification_release(self.release), self.release)

    def test_release_rejects_tampered_check(self) -> None:
        original = self.release.checks[0]
        altered = replace(original, detail="tampered")
        tampered = replace(self.release, checks=(altered,) + self.release.checks[1:])
        with self.assertRaises(ValidationError):
            verify_module_certification_release(tampered)

    def test_release_rejects_incompatible_quality_address(self) -> None:
        other_quality = replace(self.quality, matrix_address="sha256:other")
        with self.assertRaises(ValidationError):
            build_module_certification_release(self.matrix, self.lineage, other_quality)

    def test_release_query_filters_plane_and_pass_state(self) -> None:
        result = query_module_certification_release(
            self.release,
            plane=CertificationReleasePlane.QUALITY.value,
            passed=True,
            limit=20,
        )
        self.assertTrue(result["items"])
        self.assertTrue(all(item["plane"] == "quality" for item in result["items"]))
        self.assertTrue(all(item["passed"] for item in result["items"]))
        self.assertEqual(result["release_address"], self.release.content_address)

    def test_release_query_returns_policy_failure(self) -> None:
        result = query_module_certification_release(self.release, passed=False, limit=20)
        self.assertGreaterEqual(result["total"], 1)
        self.assertTrue(
            any(item["check_id"] == "release-readiness-policy" for item in result["items"])
        )

    def test_release_query_rejects_invalid_page(self) -> None:
        with self.assertRaises(ValidationError):
            query_module_certification_release(self.release, offset=-1)
        with self.assertRaises(ValidationError):
            query_module_certification_release(self.release, limit=513)

    def test_release_csv_is_parseable(self) -> None:
        rows = list(
            csv.DictReader(io.StringIO(module_certification_release_checks_csv(self.release)))
        )
        self.assertEqual(len(rows), self.release.check_count)
        self.assertIn("release-readiness-policy", {row["check_id"] for row in rows})

    def test_release_markdown_exposes_actions(self) -> None:
        markdown = render_module_certification_release_markdown(self.release)
        self.assertIn("Module certification release control", markdown)
        self.assertIn("Recommended actions", markdown)
        for action in self.release.recommended_actions:
            self.assertIn(action, markdown)

    def test_release_schema_and_capabilities_are_complete(self) -> None:
        schema = module_certification_release_schema()
        capabilities = module_certification_release_capabilities()
        self.assertIn("release_eligible", schema["report_fields"])
        self.assertEqual(capabilities["operation_count"], len(capabilities["operations"]))
        self.assertEqual(capabilities["release_gate"], "release_eligible")

    def test_release_public_projection_has_no_absolute_fixture_path(self) -> None:
        encoded = json.dumps(self.release.to_dict(), sort_keys=True)
        self.assertNotIn(str(self.root), encoded)
        self.assertNotIn("\\", encoded)

    def test_release_check_order_is_stable(self) -> None:
        identifiers = tuple(item.check_id for item in self.release.checks)
        self.assertEqual(identifiers, tuple(sorted(identifiers)))

    def test_release_action_order_is_stable(self) -> None:
        self.assertEqual(
            self.release.recommended_actions,
            tuple(sorted(set(self.release.recommended_actions))),
        )


if __name__ == "__main__":
    unittest.main()
