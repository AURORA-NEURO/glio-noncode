"""D01 module-fabric closure, compliance, and projection tests."""

from __future__ import annotations

import csv
import io
import json
import unittest
from pathlib import Path

from glio_noncode.module_fabric_compliance import (
    find_module_fabric_forbidden_paths,
    find_module_fabric_metadata_paths,
    run_module_fabric_compliance,
)
from glio_noncode.module_fabric_contracts import (
    MODULE_FABRIC_CHECK_COUNT,
    MODULE_FABRIC_CHECKS_PER_RECORD,
    MODULE_FABRIC_GLOBAL_CHECK_COUNT,
    MODULE_FABRIC_STAGE_COUNT,
    FabricCheckPlane,
    FabricRole,
    FabricState,
)
from glio_noncode.module_fabric_depth import audit_module_fabric_depth
from glio_noncode.module_fabric_exports import (
    module_fabric_checks_csv,
    module_fabric_compliance_json,
    module_fabric_summary,
)
from glio_noncode.module_fabric_fixture_eval import evaluate_module_fabric_fixture
from glio_noncode.module_fabric_metrics import measure_module_fabric
from glio_noncode.module_fabric_observability import (
    build_module_fabric_trace,
    verify_module_fabric_trace,
)
from glio_noncode.module_fabric_public_data import (
    default_module_fabric_fixture,
)
from glio_noncode.module_fabric_quality_gate import run_module_fabric_quality_gate
from glio_noncode.module_fabric_runtime import run_module_fabric_runtime


class ModuleFabricD01CheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_module_fabric_fixture()
        cls.evaluation = evaluate_module_fabric_fixture(cls.fixture)
        cls.runtime = run_module_fabric_runtime(cls.fixture)

    def test_record_and_global_check_partition(self) -> None:
        record_checks = tuple(item for item in self.evaluation.checks if item.record_id != "__fixture__")
        global_checks = tuple(item for item in self.evaluation.checks if item.record_id == "__fixture__")
        self.assertEqual(len(record_checks), 32 * MODULE_FABRIC_CHECKS_PER_RECORD)
        self.assertEqual(len(global_checks), MODULE_FABRIC_GLOBAL_CHECK_COUNT)
        self.assertEqual(len(self.evaluation.checks), MODULE_FABRIC_CHECK_COUNT)
        self.assertTrue(all(item.passed for item in self.evaluation.checks))

    def test_record_checks_are_even(self) -> None:
        counts: dict[str, int] = {}
        for item in self.evaluation.checks:
            if item.record_id != "__fixture__":
                counts[item.record_id] = counts.get(item.record_id, 0) + 1
        self.assertEqual(len(counts), 32)
        self.assertEqual(set(counts.values()), {MODULE_FABRIC_CHECKS_PER_RECORD})

    def test_check_planes_cover_integration_surface(self) -> None:
        planes = {item.plane for item in self.evaluation.checks}
        self.assertEqual(
            planes,
            {
                FabricCheckPlane.IDENTITY,
                FabricCheckPlane.PUBLIC_BOUNDARY,
                FabricCheckPlane.REFERENCE_RESOLUTION,
                FabricCheckPlane.TEST_SURFACE,
                FabricCheckPlane.DOMAIN_CLOSURE,
                FabricCheckPlane.CONTROL,
                FabricCheckPlane.INTEGRITY,
            },
        )

    def test_global_checks_have_stable_identity(self) -> None:
        identifiers = {item.check_id for item in self.evaluation.checks if item.record_id == "__fixture__"}
        self.assertEqual(len(identifiers), MODULE_FABRIC_GLOBAL_CHECK_COUNT)
        self.assertTrue(all(item.check_id.startswith("__fixture__:") for item in self.evaluation.checks if item.record_id == "__fixture__"))


class ModuleFabricD01ComplianceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime = run_module_fabric_runtime()
        cls.report = run_module_fabric_compliance(cls.runtime)

    def test_report_is_accepted(self) -> None:
        self.assertTrue(self.report.accepted)
        self.assertEqual(len(self.report.checks), 12)
        self.assertEqual(self.report.passed_checks, 12)
        self.assertEqual(self.report.failed_checks, 0)
        self.assertEqual(self.report.forbidden_paths, ())
        self.assertTrue(all(":" in item.content_address for item in self.report.checks))

    def test_forbidden_path_scanner_does_not_return_values(self) -> None:
        value = {"nested": [{"patient_id": "value-not-in-receipt"}, {"safe": True}]}
        paths = find_module_fabric_forbidden_paths(value)
        self.assertEqual(paths, ("$.nested[0].patient_id",))
        self.assertNotIn("value-not-in-receipt", paths)

    def test_metadata_path_scanner_is_exact_key_based(self) -> None:
        value = {"metadata": {"model" + "_name": "value-not-in-receipt"}}
        paths = find_module_fabric_metadata_paths(value)
        self.assertEqual(paths, ("$.metadata." + "model" + "_name",))
        self.assertNotIn("value-not-in-receipt", paths)

    def test_compliance_json_is_stable_and_sanitized(self) -> None:
        first = module_fabric_compliance_json(self.runtime)
        second = module_fabric_compliance_json(self.runtime)
        self.assertEqual(first, second)
        payload = json.loads(first)
        self.assertEqual(payload["passed_checks"], 12)
        self.assertEqual(payload["forbidden_paths"], [])


class ModuleFabricD01RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_module_fabric_fixture()
        cls.runtime = run_module_fabric_runtime(cls.fixture)

    def test_runtime_stages_close(self) -> None:
        self.assertEqual(len(self.runtime.stages), MODULE_FABRIC_STAGE_COUNT)
        self.assertEqual(tuple(item.ordinal for item in self.runtime.stages), tuple(range(1, 25)))
        self.assertTrue(all(item.state is FabricState.ACCEPTED for item in self.runtime.stages))
        self.assertEqual(len({item.stage_id for item in self.runtime.stages}), MODULE_FABRIC_STAGE_COUNT)

    def test_runtime_contains_compliance_and_evaluation(self) -> None:
        self.assertEqual(len(self.runtime.evaluation.executions), 32)
        self.assertEqual(len(self.runtime.evaluation.checks), MODULE_FABRIC_CHECK_COUNT)
        self.assertTrue(self.runtime.compliance.accepted)
        self.assertEqual(len(self.runtime.compliance.checks), 12)

    def test_positive_and_control_state_conservation(self) -> None:
        positives = tuple(item for item in self.runtime.evaluation.executions if item.role is FabricRole.POSITIVE)
        controls = tuple(item for item in self.runtime.evaluation.executions if item.role is FabricRole.CONTROL)
        self.assertEqual(len(positives), 16)
        self.assertEqual(len(controls), 16)
        self.assertTrue(all(item.observed_state is FabricState.ACCEPTED for item in positives))
        self.assertTrue(all(item.observed_state is FabricState.REVIEW for item in controls))

    def test_trace_matches_runtime(self) -> None:
        trace = build_module_fabric_trace(self.runtime)
        self.assertTrue(trace.accepted)
        self.assertEqual(len(trace.observations), MODULE_FABRIC_STAGE_COUNT)
        self.assertEqual(verify_module_fabric_trace(trace), ())
        self.assertEqual(tuple(item.stage_id for item in self.runtime.stages), tuple(item.stage_id for item in trace.observations))

    def test_metrics_expose_conserved_reference_counts(self) -> None:
        metrics = measure_module_fabric(self.fixture, self.runtime.evaluation)
        self.assertEqual(metrics.record_count, 32)
        self.assertEqual(metrics.domain_count, 16)
        self.assertEqual(metrics.accepted_count, 16)
        self.assertEqual(metrics.review_count, 16)
        self.assertEqual(metrics.failed_reference_count, 0)
        self.assertEqual(metrics.implementation_reference_count + metrics.test_reference_count, 408)

    def test_depth_and_quality_agree(self) -> None:
        depth = audit_module_fabric_depth(self.fixture)
        quality = run_module_fabric_quality_gate(self.fixture)
        self.assertTrue(depth.accepted)
        self.assertEqual(len(depth.checks), 30)
        self.assertTrue(quality.accepted)
        self.assertEqual(len(quality.checks), 20)


class ModuleFabricD01ProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime = run_module_fabric_runtime()

    def test_checks_csv_has_all_rows(self) -> None:
        text = module_fabric_checks_csv(self.runtime)
        rows = list(csv.DictReader(io.StringIO(text)))
        self.assertEqual(len(rows), MODULE_FABRIC_CHECK_COUNT)
        self.assertEqual(len(text.splitlines()), MODULE_FABRIC_CHECK_COUNT + 1)
        self.assertEqual(rows[0]["passed"], "true")
        self.assertEqual(rows[-1]["record_id"], "__fixture__")
        self.assertNotIn("patient_id", text)

    def test_summary_preserves_evaluation_denominator(self) -> None:
        summary = module_fabric_summary()
        self.assertEqual(summary["record_count"], 32)
        self.assertEqual(summary["evaluation_check_count"], MODULE_FABRIC_CHECK_COUNT)
        self.assertEqual(summary["compliance_check_count"], 0)
        self.assertTrue(summary["accepted"])

    def test_runtime_projection_is_json_round_trippable(self) -> None:
        payload = json.loads(json.dumps(self.runtime.to_dict()))
        self.assertEqual(payload["state"], "accepted")
        self.assertEqual(len(payload["stages"]), MODULE_FABRIC_STAGE_COUNT)
        self.assertEqual(len(payload["evaluation"]["checks"]), MODULE_FABRIC_CHECK_COUNT)
        self.assertEqual(payload["compliance"]["passed_checks"], 12)


class ModuleFabricD01ClosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        path = Path(__file__).parents[1] / "data" / "module-fabric-d01-runtime-closure.json"
        cls.payload = json.loads(path.read_text(encoding="utf-8"))

    def test_closure_sections_are_present(self) -> None:
        required = {
            "module",
            "boundary",
            "fixture",
            "data_audit",
            "evaluation",
            "runtime",
            "compliance",
            "quality",
            "depth",
            "metrics",
            "lineage",
            "replay",
            "release",
            "trace",
            "scenario_matrix",
            "schema",
            "catalog",
            "data_dictionary",
            "source_registry",
            "operation_ledger",
            "operation_ledger_audit",
            "recovery",
            "failures",
            "summary",
            "report",
            "report_markdown",
            "runtime_markdown",
            "checks_csv",
        }
        self.assertTrue(required <= set(self.payload))
        self.assertEqual(self.payload["module"], "D01")

    def test_closure_denominators_are_reconciled(self) -> None:
        self.assertEqual(len(self.payload["fixture"]["records"]), 32)
        self.assertEqual(len(self.payload["evaluation"]["executions"]), 32)
        self.assertEqual(len(self.payload["evaluation"]["checks"]), 394)
        self.assertEqual(len(self.payload["runtime"]["stages"]), 24)
        self.assertEqual(len(self.payload["runtime"]["compliance"]["checks"]), 12)
        self.assertEqual(self.payload["quality"]["checks"][-1]["passed"], True)
        self.assertEqual(self.payload["depth"]["passed_checks"], 30)

    def test_closure_acceptance_states_are_explicit(self) -> None:
        for key in ("data_audit", "evaluation", "runtime", "compliance", "quality", "depth", "lineage", "replay", "release", "trace", "scenario_matrix", "schema", "source_registry", "operation_ledger_audit", "failures"):
            value = self.payload[key]
            if "accepted" in value:
                self.assertTrue(value["accepted"], key)
        self.assertEqual(self.payload["runtime"]["state"], "accepted")


if __name__ == "__main__":
    unittest.main()
