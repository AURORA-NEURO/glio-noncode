from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.frontier_data_alpha import FrontierState
from glio_noncode.frontier_fixture_eval import (
    FIXTURE_SCHEMA_VERSION,
    FrontierFixtureEvaluator,
    evaluate_frontier_fixture,
)
from glio_noncode.serialization import canonical_json

FIXTURE_PATH = Path(__file__).parents[1] / "examples" / "frontier-glioma-case.json"
EXPECTED_CONTEXT = (
    "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"
)
FRONTIER_CAPABILITIES = {
    "GNC-D13-C13",
    "GNC-D13-C14",
    "GNC-D13-C15",
    "GNC-D13-C16",
    "GNC-D14-C13",
    "GNC-D14-C14",
    "GNC-D14-C15",
    "GNC-D14-C16",
    "GNC-D15-C13",
    "GNC-D15-C14",
    "GNC-D15-C15",
    "GNC-D15-C16",
    "GNC-D16-C13",
    "GNC-D16-C14",
    "GNC-D16-C15",
    "GNC-D16-C16",
}


class FrontierFixtureEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.evaluator = FrontierFixtureEvaluator()
        cls.fixture = cls.evaluator.load_file(FIXTURE_PATH)

    def test_fixture_is_declared_as_non_patient_level_data(self) -> None:
        provenance = self.fixture["provenance"]
        self.assertEqual(provenance["source_class"], "public_aggregate_reference_identifiers")
        self.assertFalse(provenance["patient_level_data"])
        self.assertIn("deterministic repository contract", provenance["evidence_boundary"])

    def test_fixture_has_two_independent_source_receipts(self) -> None:
        receipts = self.fixture["source_receipts"]
        self.assertEqual(len(receipts), 2)
        self.assertEqual(
            {item["source_id"] for item in receipts},
            {"glioma-regulatory-reference", "regulatory-assay-contract-reference"},
        )
        self.assertTrue(all(item["accession"] for item in receipts))

    def test_fixture_context_key_is_exact_and_ordered(self) -> None:
        report = self.evaluator.evaluate(self.fixture)
        self.assertEqual(report.context_key, EXPECTED_CONTEXT)
        self.assertEqual(report.state, FrontierState.ACCEPTED)

    def test_public_data_boundary_is_accepted_before_pipeline_execution(self) -> None:
        report = self.evaluator.evaluate(self.fixture)
        self.assertEqual(report.data_report["state"], "accepted")
        self.assertTrue(report.data_report["accepted"])
        self.assertEqual(report.data_report["record_count"], 10)
        self.assertEqual(report.data_report["sensitive_paths"], [])
        self.assertIn("data-boundary:public-catalog", report.passed_check_ids)

    def test_contract_inventory_is_accepted_before_pipeline_execution(self) -> None:
        report = self.evaluator.evaluate(self.fixture)
        self.assertEqual(report.contract_manifest["contract_count"], 79)
        self.assertEqual(len(report.contract_manifest["capability_ids"]), 16)
        self.assertIn("contract-boundary:frontier-inventory", report.passed_check_ids)

    def test_frontier_fixture_passes_all_checks(self) -> None:
        report = self.evaluator.evaluate(self.fixture)
        self.assertTrue(report.passed)
        self.assertEqual(report.failed_check_ids, ())
        self.assertEqual(len(report.checks), 49)
        self.assertEqual(len(report.passed_check_ids), 49)

    def test_all_sixteen_catalog_capabilities_receive_fixture_receipts(self) -> None:
        report = self.evaluator.evaluate(self.fixture)
        observed = {
            capability_id for check in report.checks for capability_id in check.capability_ids
        }
        self.assertEqual(observed, FRONTIER_CAPABILITIES)
        frontier_checks = [check for check in report.checks if check.capability_ids]
        self.assertEqual(len(frontier_checks), 16)
        self.assertTrue(all(check.passed for check in frontier_checks))
        self.assertTrue(
            all(check.content_address.startswith("sha256:") for check in frontier_checks)
        )

    def test_pipeline_reports_retain_each_expected_stage(self) -> None:
        report = self.evaluator.evaluate(self.fixture)
        expected = {
            "validation": {
                "off_target_risk",
                "value_of_information",
                "experiment_package",
                "claim_update",
            },
            "evidence": {"reclassification", "supersession", "audit_bundle", "signed_dossier"},
            "workbench": {"structured_review", "report_export", "search_palette", "accessibility"},
            "deployment": {
                "security_policy",
                "deployment_bundle",
                "federated_execution",
                "release_rollback",
            },
        }
        for name, stage_ids in expected.items():
            with self.subTest(pipeline=name):
                stages = report.pipeline_reports[name]["stages"]
                self.assertTrue(stage_ids.issubset({stage["stage_id"] for stage in stages}))
                self.assertTrue(
                    all(
                        stage["state"] in {"accepted", "published"}
                        for stage in stages
                        if stage["stage_id"] in stage_ids
                    )
                )

    def test_hardening_receipts_cover_every_operation(self) -> None:
        report = self.evaluator.evaluate(self.fixture)
        self.assertEqual(
            set(report.hardening_reports),
            {
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
            },
        )
        self.assertTrue(
            all(
                report.hardening_reports[name].get(
                    "content_address", report.hardening_reports[name].get("manifest_address")
                )
                or report.hardening_reports[name].get("entry_address")
                for name in report.hardening_reports
            )
        )

    def test_release_operation_adapter_covers_all_seventeen_commands(self) -> None:
        report = self.evaluator.evaluate(self.fixture)
        self.assertEqual(len(report.operation_reports), 17)
        self.assertEqual(
            set(report.operation_reports),
            {
                "estimate-off-target-risk",
                "optimize-validation-voi",
                "export-experiment-package",
                "ingest-result-update-claims",
                "reclassify-evidence",
                "manage-deprecation-supersession",
                "build-audit-reproducibility-bundle",
                "publish-signed-dossier",
                "verify-signed-dossier",
                "evaluate-structured-review",
                "build-export-report",
                "search-command-palette",
                "evaluate-accessibility-human-factors",
                "evaluate-privacy-security-policy",
                "build-local-deployment-bundle",
                "coordinate-federated-execution",
                "decide-release-rollback",
            },
        )
        self.assertTrue(all(report.operation_reports[name] for name in report.operation_reports))

    def test_release_operation_checks_are_successful_and_addressed(self) -> None:
        report = self.evaluator.evaluate(self.fixture)
        checks = [check for check in report.checks if check.check_id.startswith("operation:")]
        self.assertEqual(len(checks), 17)
        self.assertTrue(all(check.passed for check in checks))
        self.assertTrue(all(check.content_address.startswith("sha256:") for check in checks))

    def test_signed_dossier_operation_is_verified_without_secret_output(self) -> None:
        report = self.evaluator.evaluate(self.fixture)
        verification = report.operation_reports["verify-signed-dossier"]
        self.assertTrue(verification["valid_signature"])
        self.assertTrue(verification["payload_address_matches"])
        self.assertTrue(verification["audience_allowed"])
        self.assertNotIn("fixture-signing-secret-v1", canonical_json(verification))

    def test_negative_controls_preserve_review_boundaries(self) -> None:
        report = self.evaluator.evaluate(self.fixture)
        self.assertEqual(
            set(report.negative_control_reports),
            {
                "validation-context-mismatch",
                "evidence-cycle-review",
                "workbench-accessibility-review",
                "deployment-policy-review",
            },
        )
        self.assertTrue(
            all(check.passed for check in report.checks if check.check_id.startswith("negative:"))
        )
        for check_id, result in report.negative_control_reports.items():
            with self.subTest(control=check_id):
                self.assertEqual(result["state"], "review")
                self.assertTrue(result["blocked_stage_ids"])

    def test_report_serialization_is_stable(self) -> None:
        first = self.evaluator.evaluate(self.fixture).to_dict()
        second = self.evaluator.evaluate(copy.deepcopy(self.fixture)).to_dict()
        self.assertEqual(canonical_json(first), canonical_json(second))
        self.assertEqual(first["content_address"], second["content_address"])

    def test_file_and_mapping_entry_points_match(self) -> None:
        from_file = evaluate_frontier_fixture(FIXTURE_PATH).to_dict()
        from_mapping = self.evaluator.evaluate(self.fixture).to_dict()
        self.assertEqual(from_file, from_mapping)

    def test_output_contains_no_raw_signing_secret(self) -> None:
        output = canonical_json(self.evaluator.evaluate(self.fixture).to_dict())
        self.assertNotIn("fixture-signing-secret-v1", output)
        self.assertNotIn("patient_id", output)
        self.assertNotIn("api_key", output)

    def test_fixture_id_and_version_are_retained(self) -> None:
        report = self.evaluator.evaluate(self.fixture)
        self.assertEqual(report.fixture_id, "glioma-frontier-public-aggregate-001")
        self.assertEqual(report.fixture_version, FIXTURE_SCHEMA_VERSION)

    def test_each_check_has_a_content_address(self) -> None:
        report = self.evaluator.evaluate(self.fixture)
        for check in report.checks:
            with self.subTest(check=check.check_id):
                self.assertRegex(check.content_address, r"^sha256:[0-9a-f]{64}$")

    def test_source_ids_are_sorted_for_stable_reporting(self) -> None:
        report = self.evaluator.evaluate(self.fixture)
        self.assertEqual(report.source_ids, tuple(sorted(report.source_ids)))

    def test_validation_context_mismatch_changes_positive_state(self) -> None:
        mutated = copy.deepcopy(self.fixture)
        mutated["pipelines"]["validation"]["risk_records"][0]["context_key"] = (
            "GRCh38|diffuse_glioma|adult|other_state|tumor_core|pre_treatment"
        )
        report = self.evaluator.evaluate(mutated)
        self.assertEqual(report.state, FrontierState.REVIEW)
        self.assertIn("validation:off_target_risk", report.failed_check_ids)
        self.assertEqual(report.pipeline_reports["validation"]["stages"][0]["state"], "review")

    def test_missing_required_accessibility_criterion_fails_positive_state(self) -> None:
        mutated = copy.deepcopy(self.fixture)
        mutated["pipelines"]["workbench"]["accessibility_surface"]["contrast"] = False
        report = self.evaluator.evaluate(mutated)
        self.assertEqual(report.state, FrontierState.REVIEW)
        self.assertIn("workbench:accessibility", report.failed_check_ids)

    def test_non_addressed_deployment_artifact_fails_positive_state(self) -> None:
        mutated = copy.deepcopy(self.fixture)
        mutated["pipelines"]["deployment"]["deployment"]["artifacts"][0]["digest"] = "local-file"
        report = self.evaluator.evaluate(mutated)
        self.assertEqual(report.state, FrontierState.REVIEW)
        self.assertIn("deployment:deployment_bundle", report.failed_check_ids)

    def test_incomplete_review_form_fails_positive_state(self) -> None:
        mutated = copy.deepcopy(self.fixture)
        mutated["pipelines"]["workbench"]["form_response"].pop("rationale")
        report = self.evaluator.evaluate(mutated)
        self.assertEqual(report.state, FrontierState.REVIEW)
        self.assertIn("workbench:structured_review", report.failed_check_ids)

    def test_zero_federated_sites_fails_positive_state(self) -> None:
        mutated = copy.deepcopy(self.fixture)
        mutated["pipelines"]["deployment"]["sites"] = []
        report = self.evaluator.evaluate(mutated)
        self.assertEqual(report.state, FrontierState.REVIEW)
        self.assertIn("deployment:federated_execution", report.failed_check_ids)

    def test_public_fixture_numeric_values_are_explicitly_bounded(self) -> None:
        values = self.fixture["pipelines"]["validation"]["risk_records"][0]
        self.assertGreaterEqual(values["on_target_score"], 0.0)
        self.assertLessEqual(values["on_target_score"], 1.0)
        for candidate in values["off_targets"]:
            self.assertGreaterEqual(candidate["score"], 0.0)
            self.assertLessEqual(candidate["score"], 1.0)

    def test_fixture_source_receipts_do_not_contain_subject_identifiers(self) -> None:
        receipts = json.dumps(self.fixture["source_receipts"], sort_keys=True)
        self.assertNotIn("patient_id", receipts)
        self.assertNotIn("sample_id", receipts)
        self.assertNotIn("subject_id", receipts)

    def test_validator_rejects_wrong_fixture_version(self) -> None:
        mutated = copy.deepcopy(self.fixture)
        mutated["fixture_version"] = "frontier-fixture-v0"
        with self.assertRaises(ValidationError):
            self.evaluator.validate_fixture(mutated)

    def test_validator_rejects_patient_level_data(self) -> None:
        mutated = copy.deepcopy(self.fixture)
        mutated["provenance"]["patient_level_data"] = True
        with self.assertRaises(ValidationError):
            self.evaluator.validate_fixture(mutated)

    def test_sensitive_public_record_changes_data_boundary_state(self) -> None:
        mutated = copy.deepcopy(self.fixture)
        mutated["pipelines"]["validation"]["risk_records"][0]["patient_id"] = "forbidden"
        report = self.evaluator.evaluate(mutated)
        self.assertEqual(report.state, FrontierState.REVIEW)
        self.assertIn("data-boundary:public-catalog", report.failed_check_ids)
        self.assertEqual(report.data_report["state"], "review")
        self.assertIn(
            "records[EGFR-regulatory-guide-01].patient_id",
            report.data_report["sensitive_paths"],
        )

    def test_validator_rejects_empty_source_receipts(self) -> None:
        mutated = copy.deepcopy(self.fixture)
        mutated["source_receipts"] = []
        with self.assertRaises(ValidationError):
            self.evaluator.validate_fixture(mutated)

    def test_validator_rejects_missing_context_field(self) -> None:
        mutated = copy.deepcopy(self.fixture)
        del mutated["context"]["cell_state"]
        with self.assertRaises(ValidationError):
            self.evaluator.validate_fixture(mutated)

    def test_validator_rejects_missing_pipeline(self) -> None:
        mutated = copy.deepcopy(self.fixture)
        del mutated["pipelines"]["evidence"]
        with self.assertRaises(ValidationError):
            self.evaluator.validate_fixture(mutated)

    def test_validator_rejects_missing_hardening_operation(self) -> None:
        mutated = copy.deepcopy(self.fixture)
        del mutated["hardening"]["scan-security-paths"]
        with self.assertRaises(ValidationError):
            self.evaluator.validate_fixture(mutated)

    def test_validator_rejects_negative_control_without_expected_state(self) -> None:
        mutated = copy.deepcopy(self.fixture)
        del mutated["negative_controls"][0]["expected_state"]
        with self.assertRaises(ValidationError):
            self.evaluator.validate_fixture(mutated)

    def test_load_file_rejects_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text("{invalid", encoding="utf-8")
            with self.assertRaises(ValidationError):
                self.evaluator.load_file(path)

    def test_load_file_rejects_non_object_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "array.json"
            path.write_text("[]", encoding="utf-8")
            with self.assertRaises(ValidationError):
                self.evaluator.load_file(path)

    def test_missing_fixture_path_is_reported_as_os_error(self) -> None:
        with self.assertRaises(OSError):
            self.evaluator.load_file(Path("does-not-exist-frontier-fixture.json"))


if __name__ == "__main__":
    unittest.main()
