"""Regression coverage for configurable quality-policy gates."""

from __future__ import annotations

import csv
import io
import json
import unittest
from dataclasses import replace

from glio_noncode.errors import ValidationError
from glio_noncode.module_certification_quality_policy import (
    build_module_certification_quality_policy,
    compare_module_certification_quality_gates,
    compare_module_certification_quality_policies,
    default_module_certification_quality_policy,
    evaluate_module_certification_quality_policy,
    module_certification_quality_policy_capabilities,
    module_certification_quality_policy_csv,
    module_certification_quality_policy_json,
    module_certification_quality_policy_schema,
    query_module_certification_quality_policy,
    verify_module_certification_quality_gate,
    verify_module_certification_quality_policy,
)
from tests.test_module_certification_lineage_quality import LineageQualityFixture


class QualityPolicyFixture(LineageQualityFixture):
    """Apply strict and permissive policies to the shared quality fixture."""

    def setUp(self) -> None:
        super().setUp()
        self.strict = default_module_certification_quality_policy()
        self.gate = evaluate_module_certification_quality_policy(self.quality, self.strict)

    def test_default_policy_is_strict(self) -> None:
        self.assertEqual(self.strict.minimum_evidence_coverage_percent, 100.0)
        self.assertEqual(self.strict.minimum_check_pass_percent, 100.0)
        self.assertEqual(self.strict.minimum_family_score, 0.8)
        self.assertTrue(self.strict.require_no_blockers)
        self.assertTrue(self.strict.require_all_modules_certified)
        self.assertTrue(self.strict.require_ready)

    def test_policy_is_content_addressed(self) -> None:
        again = default_module_certification_quality_policy()
        self.assertEqual(self.strict.content_address, again.content_address)
        self.assertIs(verify_module_certification_quality_policy(self.strict), self.strict)

    def test_strict_gate_has_per_kind_and_family_checks(self) -> None:
        identifiers = {item.check_id for item in self.gate.checks}
        self.assertIn("evidence-coverage", identifiers)
        self.assertIn("readiness", identifiers)
        self.assertIn("check-pass-rate:test", identifiers)
        self.assertIn("family-score:core", identifiers)
        self.assertEqual(
            self.gate.passed_count + self.gate.failed_count,
            self.gate.check_count,
        )

    def test_strict_gate_is_not_accepted_for_review_fixture(self) -> None:
        self.assertFalse(self.gate.accepted)
        self.assertGreater(self.gate.failed_count, 0)

    def test_permissive_policy_can_accept_a_valid_warning(self) -> None:
        policy = build_module_certification_quality_policy(
            minimum_evidence_coverage_percent=0.0,
            minimum_check_pass_percent=0.0,
            minimum_family_score=0.0,
            require_no_blockers=False,
            require_all_modules_certified=False,
            require_ready=False,
        )
        gate = evaluate_module_certification_quality_policy(self.quality, policy)
        self.assertTrue(gate.accepted, gate.to_dict())
        self.assertEqual(gate.failed_count, 0)

    def test_policy_thresholds_change_decisions(self) -> None:
        permissive = build_module_certification_quality_policy(
            minimum_evidence_coverage_percent=0.0,
            minimum_check_pass_percent=0.0,
            minimum_family_score=0.0,
            require_no_blockers=False,
            require_all_modules_certified=False,
            require_ready=False,
        )
        permissive_gate = evaluate_module_certification_quality_policy(self.quality, permissive)
        self.assertNotEqual(self.gate.content_address, permissive_gate.content_address)
        self.assertNotEqual(self.strict.content_address, permissive.content_address)
        self.assertTrue(permissive_gate.accepted)

    def test_policy_rejects_invalid_thresholds(self) -> None:
        with self.assertRaises(ValidationError):
            build_module_certification_quality_policy(minimum_evidence_coverage_percent=-1.0)
        with self.assertRaises(ValidationError):
            build_module_certification_quality_policy(minimum_check_pass_percent=101.0)
        with self.assertRaises(ValidationError):
            build_module_certification_quality_policy(minimum_family_score=1.1)

    def test_policy_rejects_non_boolean_controls(self) -> None:
        with self.assertRaises(ValidationError):
            build_module_certification_quality_policy(require_no_blockers=1)  # type: ignore[arg-type]
        with self.assertRaises(ValidationError):
            build_module_certification_quality_policy(require_all_modules_certified=0)  # type: ignore[arg-type]
        with self.assertRaises(ValidationError):
            build_module_certification_quality_policy(require_ready="yes")  # type: ignore[arg-type]

    def test_gate_verifier_accepts_fresh_gate(self) -> None:
        self.assertIs(verify_module_certification_quality_gate(self.gate), self.gate)

    def test_policy_verifier_rejects_tampered_policy(self) -> None:
        tampered = replace(self.strict, minimum_family_score=0.0)
        with self.assertRaises(ValidationError):
            verify_module_certification_quality_policy(tampered)

    def test_gate_verifier_rejects_tampered_check(self) -> None:
        original = self.gate.checks[0]
        altered = replace(original, detail="tampered")
        tampered = replace(self.gate, checks=(altered,) + self.gate.checks[1:])
        with self.assertRaises(ValidationError):
            verify_module_certification_quality_gate(tampered)

    def test_gate_verifier_rejects_wrong_type(self) -> None:
        with self.assertRaises(ValidationError):
            verify_module_certification_quality_gate({})  # type: ignore[arg-type]

    def test_policy_json_is_stable(self) -> None:
        again = evaluate_module_certification_quality_policy(self.quality, self.strict)
        self.assertEqual(
            module_certification_quality_policy_json(self.gate),
            module_certification_quality_policy_json(again),
        )
        payload = json.loads(module_certification_quality_policy_json(self.gate))
        self.assertEqual(payload["quality_address"], self.quality.content_address)

    def test_policy_query_returns_all_checks(self) -> None:
        result = query_module_certification_quality_policy(self.gate, limit=64)
        self.assertEqual(result["total"], self.gate.check_count)
        self.assertEqual(len(result["items"]), self.gate.check_count)
        self.assertEqual(result["policy_address"], self.strict.content_address)

    def test_policy_query_filters_passed(self) -> None:
        result = query_module_certification_quality_policy(self.gate, passed=True, limit=64)
        self.assertEqual(result["total"], self.gate.passed_count)
        self.assertTrue(all(item["passed"] for item in result["items"]))

    def test_policy_query_filters_text(self) -> None:
        result = query_module_certification_quality_policy(
            self.gate,
            text="evidence",
            limit=64,
        )
        self.assertTrue(result["items"])
        self.assertTrue(all("evidence" in json.dumps(item).casefold() for item in result["items"]))

    def test_policy_query_rejects_invalid_paging(self) -> None:
        with self.assertRaises(ValidationError):
            query_module_certification_quality_policy(self.gate, offset=-1)
        with self.assertRaises(ValidationError):
            query_module_certification_quality_policy(self.gate, limit=513)

    def test_policy_csv_is_parseable(self) -> None:
        rows = list(csv.DictReader(io.StringIO(module_certification_quality_policy_csv(self.gate))))
        self.assertEqual(len(rows), self.gate.check_count)
        self.assertEqual(rows[0]["check_id"], self.gate.checks[0].check_id)

    def test_policy_schema_declares_all_controls(self) -> None:
        schema = module_certification_quality_policy_schema()
        self.assertIn("minimum_evidence_coverage_percent", schema["policy_fields"])
        self.assertIn("require_ready", schema["policy_fields"])
        self.assertIn("accepted", schema["gate_fields"])
        self.assertEqual(schema["query_filters"], ["passed", "text"])

    def test_policy_capabilities_are_consistent(self) -> None:
        capabilities = module_certification_quality_policy_capabilities()
        self.assertEqual(capabilities["operation_count"], len(capabilities["operations"]))
        self.assertTrue(capabilities["customizable"])
        self.assertTrue(capabilities["deterministic"])

    def test_policy_output_excludes_fixture_path(self) -> None:
        encoded = json.dumps(self.gate.to_dict(), sort_keys=True)
        self.assertNotIn(str(self.root), encoded)
        self.assertNotIn("\\", encoded)

    def test_policy_checks_have_unique_addresses(self) -> None:
        addresses = [item.content_address for item in self.gate.checks]
        self.assertEqual(len(addresses), len(set(addresses)))

    def test_policy_gate_links_exact_quality_address(self) -> None:
        self.assertEqual(self.gate.quality_address, self.quality.content_address)

    def test_policy_comparison_reports_changed_fields(self) -> None:
        relaxed = build_module_certification_quality_policy(
            minimum_evidence_coverage_percent=90.0,
            minimum_check_pass_percent=95.0,
            minimum_family_score=0.7,
            require_no_blockers=False,
            require_all_modules_certified=False,
            require_ready=False,
        )
        result = compare_module_certification_quality_policies(self.strict, relaxed)
        self.assertEqual(result["resource"], "policies")
        self.assertIn("minimum_evidence_coverage_percent", result["changed_fields"])
        self.assertIn("require_ready", result["changed_fields"])
        self.assertTrue(result["content_address"].startswith("module-certification-quality-policy-diff:"))

    def test_policy_comparison_is_symmetric_in_addresses(self) -> None:
        relaxed = build_module_certification_quality_policy(
            minimum_evidence_coverage_percent=0.0,
            minimum_check_pass_percent=0.0,
            minimum_family_score=0.0,
            require_no_blockers=False,
            require_all_modules_certified=False,
            require_ready=False,
        )
        left_right = compare_module_certification_quality_policies(self.strict, relaxed)
        right_left = compare_module_certification_quality_policies(relaxed, self.strict)
        self.assertEqual(left_right["changed_fields"], right_left["changed_fields"])
        self.assertNotEqual(left_right["content_address"], right_left["content_address"])

    def test_identical_policy_comparison_has_no_changed_fields(self) -> None:
        result = compare_module_certification_quality_policies(self.strict, self.strict)
        self.assertEqual(result["changed_fields"], ())
        self.assertEqual(result["left_policy_address"], result["right_policy_address"])

    def test_policy_comparison_rejects_wrong_types(self) -> None:
        with self.assertRaises(ValidationError):
            compare_module_certification_quality_policies({}, self.strict)  # type: ignore[arg-type]

    def test_gate_comparison_reports_decision_changes(self) -> None:
        relaxed = build_module_certification_quality_policy(
            minimum_evidence_coverage_percent=0.0,
            minimum_check_pass_percent=0.0,
            minimum_family_score=0.0,
            require_no_blockers=False,
            require_all_modules_certified=False,
            require_ready=False,
        )
        relaxed_gate = evaluate_module_certification_quality_policy(self.quality, relaxed)
        result = compare_module_certification_quality_gates(self.gate, relaxed_gate)
        self.assertEqual(result["resource"], "gates")
        self.assertTrue(result["changed_check_ids"])
        self.assertTrue(result["accepted_changed"])

    def test_identical_gate_comparison_is_empty(self) -> None:
        result = compare_module_certification_quality_gates(self.gate, self.gate)
        self.assertEqual(result["changed_check_ids"], ())
        self.assertFalse(result["accepted_changed"])

    def test_gate_comparison_rejects_wrong_types(self) -> None:
        with self.assertRaises(ValidationError):
            compare_module_certification_quality_gates({}, self.gate)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
