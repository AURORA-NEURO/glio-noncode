"""Depth tests for threshold, matrix, and handoff publication surfaces."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.validation_beta_frontier_handoff import (
    VALIDATION_BETA_FRONTIER_ALLOWED_USES,
    VALIDATION_BETA_FRONTIER_EXCLUDED_USES,
    build_validation_beta_frontier_handoff,
    render_validation_beta_frontier_handoff_markdown,
    validate_validation_beta_frontier_handoff,
    validation_beta_frontier_handoff_summary,
)
from glio_noncode.validation_beta_frontier_public_data import ValidationBetaFrontierOperation
from glio_noncode.validation_beta_frontier_runtime import run_validation_beta_frontier_runtime
from glio_noncode.validation_beta_frontier_thresholds import (
    build_validation_beta_frontier_threshold_report,
    default_validation_beta_frontier_threshold_profiles,
    validate_validation_beta_frontier_threshold_report,
    validation_beta_frontier_threshold_summary,
)
from glio_noncode.validation_beta_frontier_validation_matrix import (
    VALIDATION_BETA_FRONTIER_EVIDENCE_PLANES,
    build_validation_beta_frontier_validation_matrix,
    validate_validation_beta_frontier_matrix,
    validation_beta_frontier_matrix_summary,
)


class ValidationBetaFrontierDepthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.thresholds = build_validation_beta_frontier_threshold_report()
        self.matrix = build_validation_beta_frontier_validation_matrix()
        self.handoff = build_validation_beta_frontier_handoff()

    def test_threshold_profiles_cover_all_operations(self) -> None:
        profiles = default_validation_beta_frontier_threshold_profiles()
        self.assertEqual(len(profiles), 8)
        self.assertEqual({item.operation for item in profiles}, set(ValidationBetaFrontierOperation))
        self.assertEqual(len({item.profile_id for item in profiles}), 8)

    def test_threshold_profiles_have_ordered_bounds(self) -> None:
        for profile in self.thresholds.profiles:
            self.assertLessEqual(profile.lower, profile.nominal)
            self.assertLessEqual(profile.nominal, profile.upper)
            self.assertTrue(profile.content_address.startswith("sha256:"))

    def test_threshold_report_has_five_positions_per_operation(self) -> None:
        self.assertTrue(self.thresholds.accepted)
        self.assertEqual(self.thresholds.profile_count, 8)
        self.assertEqual(self.thresholds.probe_count, 40)
        for operation in ValidationBetaFrontierOperation:
            self.assertEqual(tuple(item.position for item in self.thresholds.by_operation(operation)), ("below", "lower", "nominal", "upper", "above"))

    def test_threshold_probe_states_are_explicit(self) -> None:
        self.assertEqual(
            {item.observed_state for item in self.thresholds.probes},
            {"below_minimum", "at_lower_boundary", "within_spec", "at_upper_boundary", "above_maximum"},
        )
        self.assertTrue(validate_validation_beta_frontier_threshold_report(self.thresholds))

    def test_threshold_summary_is_addressed(self) -> None:
        summary = validation_beta_frontier_threshold_summary(self.thresholds)
        self.assertTrue(summary["accepted"])
        self.assertEqual(summary["probe_count"], 40)
        self.assertTrue(summary["content_address"].startswith("sha256:"))

    def test_threshold_mutation_is_not_accepted(self) -> None:
        mutated = replace(self.thresholds, failed_probe_ids=(self.thresholds.probes[0].probe_id,))
        self.assertFalse(validate_validation_beta_frontier_threshold_report(mutated))

    def test_matrix_has_six_named_evidence_planes(self) -> None:
        self.assertEqual(self.matrix.axes, VALIDATION_BETA_FRONTIER_EVIDENCE_PLANES)
        self.assertEqual(len(self.matrix.axes), 6)
        self.assertEqual(self.matrix.operation_count, 8)

    def test_matrix_has_one_cell_per_fixture_record(self) -> None:
        self.assertTrue(self.matrix.accepted)
        self.assertEqual(self.matrix.cell_count, 32)
        self.assertEqual(len({item.record_id for item in self.matrix.cells}), 32)
        self.assertTrue(validate_validation_beta_frontier_matrix(self.matrix))

    def test_matrix_has_four_cells_per_operation(self) -> None:
        for operation in ValidationBetaFrontierOperation:
            cells = self.matrix.by_operation(operation)
            self.assertEqual(len(cells), 4)
            self.assertEqual({item.role.value for item in cells}, {"positive", "control"})
            self.assertTrue(all(item.evidence_planes == VALIDATION_BETA_FRONTIER_EVIDENCE_PLANES for item in cells))

    def test_matrix_plane_lookup_is_conservative(self) -> None:
        for plane in VALIDATION_BETA_FRONTIER_EVIDENCE_PLANES:
            self.assertEqual(len(self.matrix.by_plane(plane)), 32)
        with self.assertRaises(ValidationError):
            self.matrix.by_plane("")

    def test_matrix_summary_exposes_failed_cells(self) -> None:
        summary = validation_beta_frontier_matrix_summary(self.matrix)
        self.assertTrue(summary["accepted"])
        self.assertEqual(summary["cell_count"], 32)
        self.assertEqual(summary["failed_cell_ids"], ())

    def test_matrix_mutation_is_not_accepted(self) -> None:
        mutated = replace(self.matrix, failed_cell_ids=(self.matrix.cells[0].cell_id,))
        self.assertFalse(validate_validation_beta_frontier_matrix(mutated))

    def test_handoff_has_explicit_allowed_and_excluded_uses(self) -> None:
        self.assertEqual(self.handoff.allowed_uses, VALIDATION_BETA_FRONTIER_ALLOWED_USES)
        self.assertEqual(self.handoff.excluded_uses, VALIDATION_BETA_FRONTIER_EXCLUDED_USES)
        self.assertTrue(set(self.handoff.allowed_uses).isdisjoint(self.handoff.excluded_uses))

    def test_handoff_conserves_operations_records_and_sources(self) -> None:
        self.assertTrue(self.handoff.accepted)
        self.assertEqual(self.handoff.operation_count, 8)
        self.assertEqual(self.handoff.record_count, 32)
        self.assertEqual(len(self.handoff.source_ids), 7)
        self.assertEqual(len(self.handoff.operation_items), 8)

    def test_handoff_items_conserve_positive_and_controls(self) -> None:
        for operation in ValidationBetaFrontierOperation:
            item = self.handoff.item(operation)
            self.assertEqual(item.record_count, 4)
            self.assertEqual(item.positive_count, 1)
            self.assertEqual(item.control_count, 3)
            self.assertEqual(item.accepted_count, 4)
            self.assertEqual(len(item.required_checks), 3)

    def test_handoff_validation_and_summary_are_stable(self) -> None:
        self.assertTrue(validate_validation_beta_frontier_handoff(self.handoff))
        summary = validation_beta_frontier_handoff_summary(self.handoff)
        self.assertTrue(summary["accepted"])
        self.assertEqual(summary["publication_surface_count"], 6)
        self.assertTrue(summary["content_address"].startswith("sha256:"))

    def test_handoff_markdown_is_reviewable_and_bounded(self) -> None:
        markdown = render_validation_beta_frontier_handoff_markdown(self.handoff)
        self.assertIn("# Validation-beta frontier research handoff", markdown)
        self.assertIn("| Operation | Records | Positive | Controls | Review rows | Sources |", markdown)
        self.assertIn("## Reproducibility", markdown)
        self.assertNotIn("patient-level inference result", markdown.lower())

    def test_handoff_mutation_is_not_accepted(self) -> None:
        mutated = replace(self.handoff, excluded_uses=())
        self.assertFalse(validate_validation_beta_frontier_handoff(mutated))

    def test_runtime_exposes_new_depth_surfaces(self) -> None:
        report = run_validation_beta_frontier_runtime()
        self.assertTrue(report.accepted)
        self.assertTrue(report.thresholds.accepted)
        self.assertEqual(report.thresholds.probe_count, 40)
        self.assertTrue(report.validation_matrix.accepted)
        self.assertEqual(report.validation_matrix.cell_count, 32)
        self.assertTrue(report.handoff.accepted)
        self.assertEqual(report.handoff.record_count, 32)
        self.assertEqual(len(report.stages), 25)

    def test_runtime_depth_stage_contains_package_surfaces(self) -> None:
        report = run_validation_beta_frontier_runtime()
        depth_stage = next(item for item in report.stages if item.stage_id == "depth")
        self.assertEqual(depth_stage.state, "completed")
        self.assertTrue(depth_stage.output_address)

    def test_root_package_exports_new_surfaces(self) -> None:
        import glio_noncode

        self.assertTrue(hasattr(glio_noncode, "build_validation_beta_frontier_handoff"))
        self.assertTrue(hasattr(glio_noncode, "build_validation_beta_frontier_threshold_report"))
        self.assertTrue(hasattr(glio_noncode, "build_validation_beta_frontier_validation_matrix"))

    def test_cli_threshold_matrix_and_handoff_commands(self) -> None:
        commands = (
            "validation-beta-frontier-thresholds",
            "validation-beta-frontier-validation-matrix",
            "validation-beta-frontier-handoff",
        )
        with tempfile.TemporaryDirectory() as directory:
            for command in commands:
                output = Path(directory) / f"{command}.json"
                self.assertEqual(main([command, "--output", str(output)]), 0)
                payload = json.loads(output.read_text(encoding="utf-8"))
                self.assertTrue(payload["accepted"])

    def test_cli_handoff_markdown_can_be_projected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "handoff.json"
            self.assertEqual(main(["validation-beta-frontier-handoff", "--output", str(output)]), 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["record_count"], 32)
            self.assertEqual(payload["operation_count"], 8)


if __name__ == "__main__":
    unittest.main()
