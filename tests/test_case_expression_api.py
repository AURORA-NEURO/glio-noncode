from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request, urlopen

from glio_noncode.api import create_server
from glio_noncode.expression_claims import RNAElementGeneTarget
from glio_noncode.expression_evidence import (
    AllelicCountObservation,
    ExpressionBatch,
    ExpressionObservation,
    ExpressionScale,
    PhaseStatus,
    PredictedRegulatoryEffect,
    RegulatoryDirection,
)
from glio_noncode.models import ReferenceContext

CONTEXT_KEY = "GRCh38|diffuse_glioma|adult|stem_like|tumor_core|pre_treatment"


def _case_request() -> dict[str, object]:
    context = {
        "genome_build": "GRCh38",
        "disease_class": "diffuse_glioma",
        "age_group": "adult",
        "cell_state": "stem_like",
        "territory": "tumor_core",
        "treatment_phase": "pre_treatment",
    }
    vcf = "\n".join(
        (
            "##fileformat=VCFv4.3",
            "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1",
            "7\t100\tvar-1\tA\tT\t99\tPASS\tDP=42\tGT\t0/1",
        )
    )
    return {
        "case_id": "case-api-fixture",
        "subject_id": "subject-local",
        "context": context,
        "variant_source": {
            "source_id": "fixture-variants",
            "input_format": "vcf",
            "genome_build": "GRCh38",
            "payload": vcf,
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


class CaseExpressionApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.server = create_server("127.0.0.1", 0, Path(self.temporary.name) / "data")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temporary.cleanup()

    def _get(self, path: str) -> tuple[int, dict[str, object]]:
        with urlopen(self.base + path, timeout=30) as response:
            return response.status, json.loads(response.read())

    def _post(self, path: str, payload: object) -> tuple[int, dict[str, object]]:
        request = Request(
            self.base + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read())

    def _expression(self, sample: str, value: float) -> ExpressionObservation:
        return ExpressionObservation(
            feature_id="SOX2",
            sample_key=sample,
            value=value,
            scale=ExpressionScale.LOG2_TPM,
            context_key=CONTEXT_KEY,
            source_id="rna-reference",
        )

    def test_case_prepare_and_run_use_the_server_runtime(self) -> None:
        status, prepared = self._post(
            "/v1/case-workflow/prepare", {"request": _case_request()}
        )
        self.assertEqual(status, 200)
        self.assertTrue(prepared["accepted"])
        status, result = self._post(
            "/v1/case-workflow/run", {"prepared": prepared, "data_root": "ignored"}
        )
        self.assertEqual(status, 200)
        self.assertTrue(result["accepted"])
        self.assertTrue(result["replay_report"]["event_chain_valid"])
        self.assertTrue((Path(self.temporary.name) / "data" / "runs").is_dir())

    def test_expression_analysis_and_integration_are_sample_free(self) -> None:
        target = self._expression("tumour-secret", 20)
        references = ExpressionBatch(
            tuple(
                self._expression(f"reference-{index}", value)
                for index, value in enumerate((1, 2, 3, 4, 5, 6, 7))
            )
        )
        status, outlier = self._post(
            "/v1/expression-evidence/outlier",
            {
                "target": target.to_dict(),
                "references": references.to_dict(),
                "expected_direction": "gain",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(outlier["state"], "supported")

        prediction = PredictedRegulatoryEffect(
            prediction_id="prediction-1",
            variant_id="variant-1",
            feature_id="SOX2",
            direction=RegulatoryDirection.GAIN,
            context_key=CONTEXT_KEY,
            source_id="sequence-model",
        )
        status, consequence = self._post(
            "/v1/expression-evidence/integrate",
            {"prediction": prediction.to_dict(), "expression_result": outlier},
        )
        self.assertEqual(status, 200)
        self.assertEqual(consequence["state"], "supported")
        rendered = json.dumps(consequence)
        self.assertNotIn("sample_key", rendered)
        self.assertNotIn("tumour-secret", rendered)

        target = RNAElementGeneTarget(
            variant_id="variant-1",
            element_id="element-SOX2",
            gene_id="SOX2",
            context=ReferenceContext(
                genome_build="GRCh38",
                disease_class="diffuse_glioma",
                age_group="adult",
                cell_state="stem_like",
                territory="tumor_core",
                treatment_phase="pre_treatment",
            ),
        )
        status, claim = self._post(
            "/v1/expression-claims/derive",
            {"evidence": consequence, "target": target.to_dict()},
        )
        self.assertEqual(status, 200)
        self.assertEqual(claim["edge_id"], target.edge_id)
        self.assertEqual(claim["channel"], "matched_rna_consequence")

        status, batch = self._post(
            "/v1/expression-claims/match",
            {
                "evidence": [consequence],
                "targets": [target.to_dict()],
                "require_complete": True,
            },
        )
        self.assertEqual(status, 200)
        self.assertTrue(batch["complete"])
        self.assertEqual(batch["claims"], [claim])

        observation = AllelicCountObservation(
            feature_id="SOX2",
            variant_id="variant-1",
            sample_key="tumour-secret",
            ref_count=20,
            alt_count=80,
            phase=PhaseStatus.PHASED,
            context_key=CONTEXT_KEY,
            source_id="rna-tumour",
            expected_alt_fraction=0.5,
        )
        status, allelic = self._post(
            "/v1/expression-evidence/allelic", {"observation": observation.to_dict()}
        )
        self.assertEqual(status, 200)
        self.assertEqual(allelic["state"], "supported")

    def test_discovery_endpoints_are_public_and_deterministic(self) -> None:
        for path in (
            "/v1/case-workflow/schema",
            "/v1/case-workflow/capabilities",
            "/v1/expression-evidence/schema",
            "/v1/expression-evidence/capabilities",
            "/v1/expression-claims/schema",
            "/v1/expression-claims/capabilities",
        ):
            status, payload = self._get(path)
            self.assertEqual(status, 200)
            self.assertIsInstance(payload, dict)


if __name__ == "__main__":
    unittest.main()
