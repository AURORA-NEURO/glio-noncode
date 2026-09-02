from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode._cli_case import build_parser, main
from glio_noncode.case_workflow import PreparedCase
from glio_noncode.expression_evidence import (
    ExpressionDirection,
    RegulatoryDirection,
    RNAConsequenceEvidence,
    RNAEvidenceState,
)
from glio_noncode.serialization import content_hash

VCF = "\n".join(
    (
        "##fileformat=VCFv4.3",
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1",
        "7\t100\tvar-1\tA\tT\t99\tPASS\tDP=42\tGT\t0/1",
    )
)


def request() -> dict[str, object]:
    context = {
        "genome_build": "GRCh38",
        "disease_class": "diffuse_glioma",
        "age_group": "adult",
        "cell_state": "stem_like",
        "territory": "tumor_core",
        "treatment_phase": "pre_treatment",
    }
    return {
        "case_id": "case-cli-fixture",
        "subject_id": "subject-local",
        "context": context,
        "variant_source": {
            "source_id": "fixture-variants",
            "input_format": "vcf",
            "genome_build": "GRCh38",
            "payload": VCF,
        },
        "regulatory_tracks": [
            {
                "source_id": "fixture-track",
                "input_format": "bed",
                "genome_build": "GRCh38",
                "context": context,
                "payload": "7\t90\t130\tEGFR\t800\t+\n",
                "target_gene_keys": ["Name"],
            }
        ],
        "requested_by": "researcher-local",
    }


class CaseCliTests(unittest.TestCase):
    def _write(self, root: Path, name: str, value: object) -> Path:
        path = root / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def _rna_consequence(self, prepared: dict[str, object]) -> RNAConsequenceEvidence:
        typed = PreparedCase.from_mapping(prepared)
        assert typed.manifest is not None
        prediction_id = "prediction:case-cli:egfr"
        return RNAConsequenceEvidence(
            prediction_id=prediction_id,
            prediction_address=content_hash(
                {"prediction_id": prediction_id},
                prefix="regulatory-effect-prediction",
            ),
            variant_id=typed.manifest.variants[0].variant_id,
            feature_id="EGFR",
            context_key=typed.manifest.context.key,
            predicted_direction=RegulatoryDirection.GAIN,
            state=RNAEvidenceState.SUPPORTED,
            expression_state=RNAEvidenceState.SUPPORTED,
            expression_direction=ExpressionDirection.UP,
            expression_robust_z=6.0,
            expression_result_address=content_hash(
                {"prediction_id": prediction_id, "component": "expression"},
                prefix="expression-outlier",
            ),
            allelic_state=None,
            allelic_direction=None,
            allelic_log2_ratio=None,
            allelic_q_value=None,
            allelic_result_address=None,
            reason_codes=("case_cli_directional_support",),
        )

    def test_parser_exposes_prepare_run_and_discovery(self) -> None:
        choices = build_parser()._subparsers._group_actions[0].choices
        self.assertEqual(set(choices), {"prepare", "run", "schema", "capabilities"})

    def test_prepare_then_run_executes_the_complete_local_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            request_path = self._write(root, "request.json", request())
            prepared_path = root / "prepared.json"
            self.assertEqual(
                main(["prepare", "--request", str(request_path), "--output", str(prepared_path)]),
                0,
            )
            prepared = json.loads(prepared_path.read_text())
            self.assertTrue(prepared["accepted"])
            self.assertEqual(len(prepared["manifest"]["variants"]), 1)
            self.assertEqual(len(prepared["manifest"]["candidate_elements"]), 1)

            result_path = root / "result.json"
            self.assertEqual(
                main([
                    "run", "--prepared", str(prepared_path), "--data-root", str(root / "data"),
                    "--output", str(result_path),
                ]),
                0,
            )
            result = json.loads(result_path.read_text())
            self.assertTrue(result["accepted"])
            self.assertTrue(result["replay_report"]["event_chain_valid"])
            self.assertTrue(result["replay_report"]["stored_dossier_matches_address"])

            rna = self._rna_consequence(prepared)
            rna_path = self._write(root, "rna-consequences.json", [rna.to_dict()])
            rna_result_path = root / "rna-result.json"
            self.assertEqual(
                main(
                    [
                        "run",
                        "--prepared",
                        str(prepared_path),
                        "--rna-consequences",
                        str(rna_path),
                        "--data-root",
                        str(root / "rna-data"),
                        "--output",
                        str(rna_result_path),
                    ]
                ),
                0,
            )
            rna_result = json.loads(rna_result_path.read_text())
            self.assertTrue(rna_result["accepted"])
            self.assertNotEqual(rna_result["dossier"]["run_id"], prepared["run_id"])
            self.assertTrue(
                any(
                    item["channel"] == "matched_rna_consequence"
                    for item in rna_result["dossier"]["evidence"]
                )
            )
            self.assertEqual(
                rna_result["stage_receipts"][-1]["metadata"]["rna_consequence_count"],
                1,
            )

    def test_blocked_request_has_nonzero_exit_and_discovery_is_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            invalid = request()
            invalid["regulatory_tracks"] = []
            request_path = self._write(root, "blocked.json", invalid)
            output = root / "blocked-result.json"
            self.assertEqual(
                main([
                    "prepare", "--request", str(request_path), "--summary",
                    "--output", str(output),
                ]),
                2,
            )
            summary = json.loads(output.read_text())
            self.assertTrue(summary["blocked"])
            self.assertIn("no_candidate_elements", summary["issue_codes"])

            schema_path = root / "schema.json"
            capabilities_path = root / "capabilities.json"
            self.assertEqual(main(["schema", "--output", str(schema_path)]), 0)
            self.assertEqual(main(["capabilities", "--output", str(capabilities_path)]), 0)
            self.assertEqual(json.loads(schema_path.read_text())["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self.assertFalse(
                json.loads(capabilities_path.read_text())["server_local_paths"]
            )

    def test_request_schema_components_are_machine_readable(self) -> None:
        expected_ids = {
            "prepare-request": "urn:glio-noncode:case-workflow:prepare-request:v1",
            "run-request": "urn:glio-noncode:case-workflow:run-request:v1",
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for component, expected_id in expected_ids.items():
                with self.subTest(component=component):
                    output = root / f"{component}.json"
                    self.assertEqual(
                        main(
                            [
                                "schema",
                                "--component",
                                component,
                                "--output",
                                str(output),
                            ]
                        ),
                        0,
                    )
                    payload = json.loads(output.read_text(encoding="utf-8"))
                    self.assertEqual(payload["$id"], expected_id)
                    self.assertFalse(payload["additionalProperties"])


if __name__ == "__main__":
    unittest.main()
