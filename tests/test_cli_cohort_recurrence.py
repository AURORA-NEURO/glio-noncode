from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import jsonschema

from glio_noncode._cli_cohort_recurrence import INPUT_SCHEMA, build_parser
from glio_noncode.cli import main
from glio_noncode.cohort import CohortObservation
from glio_noncode.models import ReferenceContext

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "cohort_observations.schema.json"


def _input_document() -> dict[str, object]:
    context = ReferenceContext(
        "GRCh38",
        "diffuse_glioma",
        "adult",
        "stem_like",
        territory="enhancer",
        treatment_phase="pretreatment",
        assay_support=("whole_genome",),
        source_version="public-fixture-v1",
    )
    observations: list[dict[str, object]] = []
    for subject_index in range(6):
        target = CohortObservation(
            observation_id=f"target-{subject_index}",
            subject_id=f"subject-{subject_index}",
            locus_id="target-locus",
            mutated=subject_index < 5,
            callable=True,
            mutability_score=0.5 + subject_index / 10_000,
            chromatin_score=0.6 + subject_index / 10_000,
            ancestry_group="ancestry-1",
            disease_class="diffuse_glioma",
            context=context,
            variant_class="SNV",
            sequence_context="ACA>T",
            molecular_context="IDH-mutant",
            recurrence_phase="primary",
            locus_length=1,
            batch_id=f"batch-{subject_index % 2}",
            ascertainment_group=f"ascertainment-{subject_index % 2}",
        )
        observations.append(target.to_dict())
        for control_index in range(5):
            control = CohortObservation(
                observation_id=f"control-{control_index}-{subject_index}",
                subject_id=f"subject-{subject_index}",
                locus_id=f"control-locus-{control_index}",
                mutated=subject_index < control_index,
                callable=True,
                mutability_score=0.48 + control_index / 1_000,
                chromatin_score=0.59 + control_index / 1_000,
                ancestry_group="ancestry-1",
                disease_class="diffuse_glioma",
                context=context,
                variant_class="SNV",
                sequence_context="ACA>T",
                molecular_context="IDH-mutant",
                recurrence_phase="primary",
                locus_length=1,
                batch_id=f"batch-{subject_index % 2}",
                ascertainment_group=f"ascertainment-{subject_index % 2}",
            )
            observations.append(control.to_dict())
    return {"schema": INPUT_SCHEMA, "locus_id": "target-locus", "observations": observations}


class CohortRecurrenceCliTests(unittest.TestCase):
    def test_schema_and_input_record_round_trip(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        document = _input_document()

        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.validate(document, schema)
        record = document["observations"][0]
        self.assertEqual(CohortObservation.from_dict(record).to_dict(), record)

    def test_focused_cli_dispatches_auditable_matched_recurrence(self) -> None:
        document = _input_document()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            input_path = root / "input.json"
            output_path = root / "recurrence.json"
            input_path.write_text(json.dumps(document), encoding="utf-8")

            exit_code = main(
                [
                    "cohort-recurrence",
                    str(input_path),
                    "--control-limit",
                    "5",
                    "--output",
                    str(output_path),
                ]
            )

            text = output_path.read_text(encoding="utf-8")
            report = json.loads(text)
            self.assertEqual(exit_code, 0)
            self.assertEqual(report["schema_version"], "glio.cohort-recurrence.v2")
            self.assertEqual(report["status"], "estimated")
            self.assertEqual(report["callable_count"], 6)
            self.assertEqual(len(report["matched_control"]["control_rates"]), 5)
            self.assertNotIn(str(root), text)
            self.assertNotIn("subject-0", text)

    def test_non_estimable_data_is_successfully_reported_not_discarded(self) -> None:
        document = _input_document()
        for row in document["observations"]:
            if row["locus_id"] == "target-locus":
                row.pop("sequence_context")

        stdout = io.StringIO()
        with tempfile.TemporaryDirectory() as temporary:
            input_path = Path(temporary) / "missing-match.json"
            input_path.write_text(json.dumps(document), encoding="utf-8")
            with contextlib.redirect_stdout(stdout):
                exit_code = main(["cohort-recurrence", str(input_path)])

        report = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(report["status"], "not_estimable")
        self.assertIn("sequence_context", report["matched_control"]["unmatched_covariates"])

    def test_invalid_input_returns_path_free_error_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            input_path = root / "invalid.json"
            output_path = root / "error.json"
            input_path.write_text('{"schema":"wrong"}', encoding="utf-8")
            exit_code = main(["cohort-recurrence", str(input_path), "--output", str(output_path)])
            text = output_path.read_text(encoding="utf-8")

        self.assertEqual(exit_code, 2)
        self.assertEqual(json.loads(text)["status"], "invalid")
        self.assertNotIn(str(root), text)

    def test_cli_control_limit_is_bounded(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            build_parser().parse_args(["input.json", "--control-limit", "501"])
        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
