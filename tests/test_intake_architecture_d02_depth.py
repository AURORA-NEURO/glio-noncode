"""D02 depth, compliance, projection, and closure tests.

These tests exercise the additional denominator introduced by the D02 build.
They intentionally inspect the public projections rather than implementation
details so a future refactor must preserve the same observable contract.
"""

from __future__ import annotations

import csv
import io
import json
import unittest
from pathlib import Path

from glio_noncode.intake_architecture_access import build_intake_architecture_access_manifest
from glio_noncode.intake_architecture_bundle import (
    verify_intake_architecture_release,
)
from glio_noncode.intake_architecture_compliance import (
    find_attribution_intake_paths,
    find_forbidden_intake_paths,
    run_intake_architecture_compliance,
)
from glio_noncode.intake_architecture_contracts import (
    INTAKE_ARCHITECTURE_CASE_COUNT,
    INTAKE_ARCHITECTURE_EVALUATION_CHECK_COUNT,
    INTAKE_ARCHITECTURE_EVALUATION_CHECKS_PER_CASE,
    INTAKE_ARCHITECTURE_EVALUATION_GLOBAL_CHECK_COUNT,
    INTAKE_ARCHITECTURE_OPERATION_COUNT,
    INTAKE_ARCHITECTURE_PLANE_COUNT,
    INTAKE_ARCHITECTURE_QUALITY_CHECK_COUNT,
    INTAKE_ARCHITECTURE_STAGE_COUNT,
    IntakeArchitectureCheckKind,
    IntakeArchitectureState,
)
from glio_noncode.intake_architecture_depth import audit_intake_architecture_depth
from glio_noncode.intake_architecture_exports import (
    intake_architecture_compliance_json,
    intake_architecture_evaluation_json,
    intake_architecture_receipts_csv,
    intake_architecture_report_markdown,
)
from glio_noncode.intake_architecture_invariants import intake_architecture_invariants
from glio_noncode.intake_architecture_lineage import (
    build_intake_architecture_lineage,
    verify_intake_architecture_lineage,
)
from glio_noncode.intake_architecture_metrics import measure_intake_architecture
from glio_noncode.intake_architecture_observability import (
    audit_intake_architecture_trace,
    build_intake_architecture_trace,
)
from glio_noncode.intake_architecture_public_data import (
    audit_intake_architecture_data,
    default_intake_architecture_fixture,
)
from glio_noncode.intake_architecture_quality import run_intake_architecture_quality_gate
from glio_noncode.intake_architecture_runtime import run_intake_architecture
from glio_noncode.intake_architecture_schema import (
    default_intake_architecture_schema,
    validate_intake_architecture_schema,
)
from glio_noncode.intake_architecture_validation import build_intake_architecture_validation_matrix


class D02DenominatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_intake_architecture_fixture()
        cls.runtime = run_intake_architecture(cls.fixture)
        cls.evaluation = cls.runtime.evaluation

    def test_closed_denominators(self) -> None:
        self.assertEqual(len(self.fixture.sources), 6)
        self.assertEqual(len(self.fixture.operations), INTAKE_ARCHITECTURE_OPERATION_COUNT)
        self.assertEqual(len(self.fixture.cases), INTAKE_ARCHITECTURE_CASE_COUNT)
        self.assertEqual(len(self.runtime.stages), INTAKE_ARCHITECTURE_STAGE_COUNT)
        self.assertEqual(
            len(self.runtime.evaluation.checks), INTAKE_ARCHITECTURE_EVALUATION_CHECK_COUNT
        )
        self.assertEqual(len(self.runtime.compliance.checks), 12)
        self.assertEqual(len(self.runtime.artifacts), 8)

    def test_evaluation_check_partition(self) -> None:
        case_checks = tuple(
            item for item in self.evaluation.checks if item.case_id != "__fixture__"
        )
        global_checks = tuple(
            item for item in self.evaluation.checks if item.case_id == "__fixture__"
        )
        self.assertEqual(
            len(case_checks),
            INTAKE_ARCHITECTURE_CASE_COUNT * INTAKE_ARCHITECTURE_EVALUATION_CHECKS_PER_CASE,
        )
        self.assertEqual(len(global_checks), INTAKE_ARCHITECTURE_EVALUATION_GLOBAL_CHECK_COUNT)
        self.assertEqual(
            len(case_checks) + len(global_checks), INTAKE_ARCHITECTURE_EVALUATION_CHECK_COUNT
        )
        self.assertTrue(all(item.passed for item in self.evaluation.checks))
        self.assertTrue(all(":" in item.content_address for item in self.evaluation.checks))

    def test_check_kinds_cover_operational_planes(self) -> None:
        kinds = {item.kind for item in self.evaluation.checks}
        self.assertIn(IntakeArchitectureCheckKind.OPERATION, kinds)
        self.assertIn(IntakeArchitectureCheckKind.SOURCE, kinds)
        self.assertIn(IntakeArchitectureCheckKind.IDENTITY, kinds)
        self.assertIn(IntakeArchitectureCheckKind.INTEGRITY, kinds)
        self.assertGreaterEqual(len(kinds), 4)
        self.assertEqual(
            len(
                {item.check_id for item in self.evaluation.checks if item.case_id == "__fixture__"}
            ),
            10,
        )

    def test_case_level_checks_are_evenly_distributed(self) -> None:
        counts = {}
        for item in self.evaluation.checks:
            if item.case_id != "__fixture__":
                counts[item.case_id] = counts.get(item.case_id, 0) + 1
        self.assertEqual(len(counts), INTAKE_ARCHITECTURE_CASE_COUNT)
        self.assertEqual(set(counts.values()), {INTAKE_ARCHITECTURE_EVALUATION_CHECKS_PER_CASE})

    def test_data_audit_has_expanded_source_and_context_controls(self) -> None:
        audit = audit_intake_architecture_data(self.fixture)
        self.assertTrue(audit.accepted)
        self.assertEqual(len(audit.checks), 17)
        self.assertEqual(
            {item.check_id for item in audit.checks[-5:]},
            {
                "source-addresses",
                "operation-source-joins",
                "operation-addresses",
                "scenario-payloads",
                "delegated-context",
            },
        )
        self.assertTrue(all(item.passed for item in audit.checks))


class D02ComplianceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime = run_intake_architecture()
        cls.report = run_intake_architecture_compliance(cls.runtime)

    def test_compliance_is_accepted(self) -> None:
        self.assertTrue(self.report.accepted)
        self.assertEqual(self.report.passed_checks, 12)
        self.assertEqual(self.report.failed_checks, 0)
        self.assertEqual(self.report.forbidden_paths, ())
        self.assertEqual(self.report.attribution_paths, ())
        self.assertTrue(all(":" in item.content_address for item in self.report.checks))

    def test_private_path_scanner_returns_paths_only(self) -> None:
        value = {"nested": [{"patient_id": "redacted-value"}, {"safe": True}]}
        paths = find_forbidden_intake_paths(value)
        self.assertEqual(paths, ("$.nested[0].patient_id",))
        self.assertNotIn("redacted-value", paths)

    def test_attribution_path_scanner_returns_paths_only(self) -> None:
        value = {"nested": [{"metadata": {"a" + "gent" + "_id": "redacted-value"}}]}
        paths = find_attribution_intake_paths(value)
        self.assertEqual(paths, ("$.nested[0].metadata.a" + "gent" + "_id",))
        self.assertNotIn("redacted-value", paths)

    def test_runtime_projection_is_bounded(self) -> None:
        projection = self.runtime.to_dict()
        encoded = json.dumps(projection, sort_keys=True).lower()
        for token in ("patient_id", "participant_id", "medical_record_number", "email", "phone"):
            self.assertNotIn(token, encoded)
        self.assertIn("public aggregate intake identity only", encoded)

    def test_compliance_json_is_stable(self) -> None:
        first = intake_architecture_compliance_json(self.runtime)
        second = intake_architecture_compliance_json(self.runtime)
        self.assertEqual(first, second)
        payload = json.loads(first)
        self.assertEqual(payload["passed_checks"], 12)
        self.assertEqual(payload["forbidden_paths"], [])


class D02ProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime = run_intake_architecture()

    def test_receipts_csv_has_one_header_and_all_checks(self) -> None:
        text = intake_architecture_receipts_csv(self.runtime)
        rows = list(csv.DictReader(io.StringIO(text)))
        self.assertEqual(len(rows), INTAKE_ARCHITECTURE_EVALUATION_CHECK_COUNT)
        self.assertEqual(len(text.splitlines()), INTAKE_ARCHITECTURE_EVALUATION_CHECK_COUNT + 1)
        self.assertEqual(
            set(rows[0]),
            {
                "check_id",
                "case_id",
                "kind",
                "passed",
                "observed",
                "required",
                "detail",
                "content_address",
            },
        )
        self.assertTrue(all(row["passed"] == "true" for row in rows))
        self.assertNotIn("raw_text", text)
        self.assertNotIn("patient_id", text)

    def test_evaluation_json_contains_checks(self) -> None:
        payload = json.loads(intake_architecture_evaluation_json(self.runtime))
        self.assertTrue(payload["accepted"])
        self.assertEqual(len(payload["results"]), INTAKE_ARCHITECTURE_CASE_COUNT)
        self.assertEqual(len(payload["checks"]), INTAKE_ARCHITECTURE_EVALUATION_CHECK_COUNT)

    def test_markdown_contains_every_stage(self) -> None:
        markdown = intake_architecture_report_markdown(self.runtime)
        self.assertIn("## Operation coverage", markdown)
        self.assertIn("## Runtime stages", markdown)
        self.assertIn("## Boundary", markdown)
        for stage in self.runtime.stages:
            self.assertIn(f"`{stage.stage_id}`", markdown)

    def test_metrics_expose_new_denominators(self) -> None:
        metrics = measure_intake_architecture(self.runtime)
        self.assertEqual(metrics.evaluation_check_count, INTAKE_ARCHITECTURE_EVALUATION_CHECK_COUNT)
        self.assertEqual(metrics.compliance_check_count, 12)
        self.assertEqual(metrics.stage_count, INTAKE_ARCHITECTURE_STAGE_COUNT)
        self.assertEqual(dict(metrics.state_counts), {"accepted": 16, "review": 48})
        self.assertTrue(
            all(item.evaluation_check_count == 28 for item in metrics.operation_metrics)
        )

    def test_operation_issue_counts(self) -> None:
        metrics = measure_intake_architecture(self.runtime)
        for item in metrics.operation_metrics:
            counts = dict(item.issue_code_counts)
            self.assertEqual(counts["duplicate_identity"], 1)
            self.assertEqual(counts["foreign_context"], 1)
            self.assertEqual(counts["malformed_input"], 1)


class D02ReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_intake_architecture_fixture()
        cls.runtime = run_intake_architecture(cls.fixture)

    def test_eight_artifacts_have_distinct_kinds(self) -> None:
        kinds = tuple(item.artifact_kind for item in self.runtime.artifacts)
        self.assertEqual(
            kinds,
            (
                "manifest",
                "source_receipts",
                "operation_results",
                "evaluation_checks",
                "review_queue",
                "ledger",
                "schema_manifest",
                "release_receipt",
            ),
        )
        self.assertEqual(len(set(kinds)), 8)
        self.assertTrue(all(item.offline_capable for item in self.runtime.artifacts))

    def test_release_and_rollback(self) -> None:
        release = self.runtime.release
        self.assertEqual(release.version, "d02.2026.08.1")
        self.assertEqual(release.rollback_version, "d02.2026.07.1")
        self.assertEqual(release.state, IntakeArchitectureState.ACCEPTED)
        self.assertEqual(verify_intake_architecture_release(release), ())
        self.assertEqual(len(release.artifact_addresses), 8)

    def test_access_manifest_tracks_every_artifact(self) -> None:
        manifest = build_intake_architecture_access_manifest(self.runtime)
        self.assertTrue(manifest.accepted)
        self.assertEqual(len(manifest.entries), 8)
        self.assertTrue(all(item.read_allowed for item in manifest.entries))
        self.assertTrue(
            all(not item.write_allowed and not item.network_allowed for item in manifest.entries)
        )

    def test_depth_report_is_accepted(self) -> None:
        report = audit_intake_architecture_depth(self.runtime)
        self.assertTrue(report.accepted)
        self.assertEqual(report.operation_count, 16)
        self.assertEqual(report.case_count, 64)
        self.assertEqual(report.stage_count, 24)
        self.assertEqual(report.receipt_count, 16)
        self.assertEqual(len(report.checks), 9)


class D02CrossProductTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_intake_architecture_fixture()
        cls.runtime = run_intake_architecture(cls.fixture)

    def test_quality_and_invariants_close_together(self) -> None:
        quality = run_intake_architecture_quality_gate(self.runtime)
        self.assertTrue(quality.accepted)
        self.assertEqual(quality.passed_checks, INTAKE_ARCHITECTURE_QUALITY_CHECK_COUNT)
        self.assertEqual(intake_architecture_invariants(self.runtime), ())

    def test_validation_matrix_is_seven_planes_deep(self) -> None:
        matrix = build_intake_architecture_validation_matrix(self.fixture)
        self.assertTrue(matrix.accepted)
        self.assertEqual(
            len(matrix.cells), INTAKE_ARCHITECTURE_PLANE_COUNT * INTAKE_ARCHITECTURE_OPERATION_COUNT
        )
        self.assertEqual(
            len({item.plane for item in matrix.cells}), INTAKE_ARCHITECTURE_PLANE_COUNT
        )
        self.assertTrue(all(item.passed for item in matrix.cells))

    def test_trace_follows_stage_denominator(self) -> None:
        trace = build_intake_architecture_trace(self.runtime)
        self.assertTrue(trace.accepted)
        self.assertEqual(len(trace.events), INTAKE_ARCHITECTURE_STAGE_COUNT)
        self.assertEqual(audit_intake_architecture_trace(trace), ())
        self.assertEqual(tuple(item.ordinal for item in trace.events), tuple(range(1, 25)))

    def test_lineage_is_addressed(self) -> None:
        lineage = build_intake_architecture_lineage(self.runtime)
        self.assertTrue(lineage.accepted)
        self.assertEqual(verify_intake_architecture_lineage(lineage), ())
        self.assertGreaterEqual(len(lineage.nodes), INTAKE_ARCHITECTURE_OPERATION_COUNT)
        self.assertTrue(all(":" in item.content_address for item in lineage.nodes))

    def test_schema_is_expanded_and_private_scope_is_absent(self) -> None:
        schema = default_intake_architecture_schema()
        self.assertTrue(schema.accepted)
        self.assertEqual(len(schema.fields), 18)
        self.assertEqual(validate_intake_architecture_schema(schema), ())
        self.assertTrue(all(item.privacy_scope == "public_aggregate" for item in schema.fields))
        self.assertEqual(len({item.field_id for item in schema.fields}), 18)

    def test_runtime_replay_is_content_stable(self) -> None:
        first = run_intake_architecture(self.fixture).content_address
        second = run_intake_architecture(self.fixture).content_address
        self.assertEqual(first, second)


class D02ClosureArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.path = (
            Path(__file__).parents[1] / "data" / "intake-architecture-d02-runtime-closure.json"
        )
        cls.payload = json.loads(cls.path.read_text(encoding="utf-8"))

    def test_closure_contains_all_projection_sections(self) -> None:
        required = {
            "module",
            "boundary",
            "fixture",
            "data_audit",
            "evaluation",
            "runtime",
            "quality",
            "compliance",
            "depth",
            "metrics",
            "trace",
            "access",
            "lineage",
            "validation",
            "schema",
            "runbook",
            "failures",
            "report_markdown",
        }
        self.assertTrue(required <= set(self.payload))
        self.assertEqual(self.payload["module"], "D02")

    def test_closure_denominators_are_reconciled(self) -> None:
        self.assertEqual(len(self.payload["fixture"]["cases"]), 64)
        self.assertEqual(len(self.payload["evaluation"]["results"]), 64)
        self.assertEqual(len(self.payload["evaluation"]["checks"]), 458)
        self.assertEqual(len(self.payload["runtime"]["stages"]), 24)
        self.assertEqual(len(self.payload["runtime"]["artifacts"]), 8)
        self.assertEqual(len(self.payload["compliance"]["checks"]), 12)
        self.assertEqual(self.payload["quality"]["passed_checks"], 24)

    def test_closure_is_accepted_end_to_end(self) -> None:
        for key in (
            "data_audit",
            "evaluation",
            "quality",
            "compliance",
            "depth",
            "trace",
            "access",
            "lineage",
            "validation",
            "schema",
        ):
            self.assertTrue(self.payload[key]["accepted"], key)
        self.assertEqual(self.payload["runtime"]["state"], "accepted")
        self.assertNotIn("patient_id", json.dumps(self.payload["compliance"]).lower())
        self.assertNotIn("a" + "gent" + "_id", json.dumps(self.payload["compliance"]).lower())


if __name__ == "__main__":
    unittest.main()
