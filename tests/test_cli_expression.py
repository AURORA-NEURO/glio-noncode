from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode._cli_expression import build_parser, main
from glio_noncode.expression_evidence import (
    AllelicCountBatch,
    AllelicCountObservation,
    ExpressionBatch,
    ExpressionObservation,
    ExpressionScale,
    PhaseStatus,
    PredictedRegulatoryEffect,
    RegulatoryDirection,
)

CONTEXT = "GRCh38|glioma|adult|stem_like|unknown|unknown"


class ExpressionCliTests(unittest.TestCase):
    def _write(self, root: Path, name: str, value: object) -> Path:
        path = root / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def _expression(self, sample: str, value: float) -> ExpressionObservation:
        return ExpressionObservation(
            feature_id="SOX2",
            sample_key=sample,
            value=value,
            scale=ExpressionScale.LOG2_TPM,
            context_key=CONTEXT,
            source_id="rna-reference",
        )

    def _allelic(self, sample: str, ref: int, alt: int) -> AllelicCountObservation:
        return AllelicCountObservation(
            feature_id="SOX2",
            variant_id="variant-1",
            sample_key=sample,
            ref_count=ref,
            alt_count=alt,
            phase=PhaseStatus.PHASED,
            context_key=CONTEXT,
            source_id="rna-tumour",
            expected_alt_fraction=0.5,
        )

    def test_parser_exposes_the_complete_nested_group(self) -> None:
        choices = build_parser()._subparsers._group_actions[0].choices
        self.assertEqual(
            set(choices),
            {"outlier", "allelic", "allelic-batch", "integrate", "schema", "capabilities"},
        )

    def test_outlier_allelic_batch_and_integration_execute(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = self._write(root, "target.json", self._expression("tumour", 20).to_dict())
            references = ExpressionBatch(
                tuple(
                    self._expression(f"reference-{index}", value)
                    for index, value in enumerate((1, 2, 3, 4, 5, 6, 7))
                )
            )
            reference_path = self._write(root, "references.json", references.to_dict())
            expression_path = root / "expression-result.json"
            self.assertEqual(
                main([
                    "outlier", "--target", str(target), "--references", str(reference_path),
                    "--expected-direction", "gain", "--output", str(expression_path),
                ]),
                0,
            )
            self.assertEqual(json.loads(expression_path.read_text())["state"], "supported")

            batch = AllelicCountBatch(
                (self._allelic("tumour-a", 20, 80), self._allelic("tumour-b", 50, 50))
            )
            batch_path = self._write(root, "allelic-batch.json", batch.to_dict())
            batch_output = root / "allelic-results.json"
            self.assertEqual(
                main(["allelic-batch", "--input", str(batch_path), "--output", str(batch_output)]),
                0,
            )
            batch_payload = json.loads(batch_output.read_text())
            self.assertEqual(batch_payload["result_count"], 2)
            self.assertTrue(batch_payload["content_address"].startswith("allelic-imbalance-batch:"))

            prediction = PredictedRegulatoryEffect(
                prediction_id="prediction-1",
                variant_id="variant-1",
                feature_id="SOX2",
                direction=RegulatoryDirection.GAIN,
                context_key=CONTEXT,
                source_id="sequence-model",
            )
            prediction_path = self._write(root, "prediction.json", prediction.to_dict())
            integrated_path = root / "integrated.json"
            self.assertEqual(
                main([
                    "integrate", "--prediction", str(prediction_path),
                    "--expression-result", str(expression_path), "--output", str(integrated_path),
                ]),
                0,
            )
            integrated = json.loads(integrated_path.read_text())
            self.assertEqual(integrated["state"], "supported")
            self.assertNotIn("sample_key", json.dumps(integrated))

    def test_schema_capabilities_and_invalid_inputs_are_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            schema_path = root / "schema.json"
            capabilities_path = root / "capabilities.json"
            self.assertEqual(main(["schema", "--output", str(schema_path)]), 0)
            self.assertEqual(main(["capabilities", "--output", str(capabilities_path)]), 0)
            self.assertTrue(json.loads(schema_path.read_text())["public"])
            self.assertTrue(
                json.loads(capabilities_path.read_text())["privacy"][
                    "public_results_are_sample_free"
                ]
            )
            bad = self._write(root, "bad.json", [])
            self.assertEqual(main(["allelic", "--input", str(bad)]), 2)


if __name__ == "__main__":
    unittest.main()
