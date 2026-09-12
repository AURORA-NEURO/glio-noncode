from __future__ import annotations

import json
import tempfile
import threading
import unittest
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from glio_noncode.adapters import AdapterLimits, AdapterMetadata, AdapterRegistry
from glio_noncode.api import create_server
from glio_noncode.case_workflow import PreparedCase
from glio_noncode.expression_claims import RNAElementGeneTarget
from glio_noncode.expression_evidence import (
    AllelicCountBatch,
    AllelicCountObservation,
    ExpressionBatch,
    ExpressionDirection,
    ExpressionObservation,
    ExpressionScale,
    PhaseStatus,
    PredictedRegulatoryEffect,
    RegulatoryDirection,
    RNAConsequenceEvidence,
    RNAEvidenceState,
)
from glio_noncode.models import ReferenceContext
from glio_noncode.serialization import content_hash

CONTEXT_KEY = "GRCh38|diffuse_glioma|adult|stem_like|tumor_core|pre_treatment"


class _DiscoveryAdapter:
    def __init__(self) -> None:
        self.metadata = AdapterMetadata(
            adapter_id="api-discovery-adapter",
            display_name="API discovery adapter",
            version="1",
            license="test-only",
            data_access="local",
            supported_contexts=(CONTEXT_KEY,),
            channels=("regulatory_element",),
            failure_modes=("empty_result",),
        )

    def resolve_elements(
        self,
        variant_id: str,
        context: ReferenceContext,
    ) -> tuple[Any, ...]:
        del variant_id, context
        return ()

    def collect_claims(
        self,
        variant_id: str,
        element_id: str,
        context: ReferenceContext,
    ) -> tuple[Any, ...]:
        del variant_id, element_id, context
        return ()


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

    def _post_raw_json(
        self, path: str, body: bytes
    ) -> tuple[int, dict[str, object]]:
        request = Request(
            self.base + path,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=30) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            try:
                return error.code, json.loads(error.read())
            finally:
                error.close()

    def _expression(self, sample: str, value: float) -> ExpressionObservation:
        return ExpressionObservation(
            feature_id="SOX2",
            sample_key=sample,
            value=value,
            scale=ExpressionScale.LOG2_TPM,
            context_key=CONTEXT_KEY,
            source_id="rna-reference",
        )

    def _case_rna_consequence(
        self, prepared: dict[str, object]
    ) -> RNAConsequenceEvidence:
        typed = PreparedCase.from_mapping(prepared)
        assert typed.manifest is not None
        prediction_id = "prediction:case-api:egfr"
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
            reason_codes=("case_api_directional_support",),
        )

    def test_case_prepare_and_run_use_the_server_runtime(self) -> None:
        status, prepared = self._post(
            "/v1/case-workflow/prepare", {"request": _case_request()}
        )
        self.assertEqual(status, 200)
        self.assertTrue(prepared["accepted"])
        status, result = self._post(
            "/v1/case-workflow/run", {"prepared": prepared}
        )
        self.assertEqual(status, 200)
        self.assertTrue(result["accepted"])
        self.assertTrue(result["replay_report"]["event_chain_valid"])
        self.assertTrue((Path(self.temporary.name) / "data" / "runs").is_dir())

    def test_case_run_carries_rna_evidence_into_the_persisted_graph(self) -> None:
        status, prepared = self._post(
            "/v1/case-workflow/prepare", {"request": _case_request()}
        )
        self.assertEqual(status, 200)
        rna = self._case_rna_consequence(prepared)
        status, result = self._post(
            "/v1/case-workflow/run",
            {"prepared": prepared, "rna_consequences": [rna.to_dict()]},
        )
        self.assertEqual(status, 200)
        self.assertTrue(result["accepted"])
        self.assertNotEqual(result["dossier"]["run_id"], prepared["run_id"])
        claim = next(
            item
            for item in result["dossier"]["evidence"]
            if item["channel"] == "matched_rna_consequence"
        )
        self.assertEqual(
            claim["payload"]["rna_consequence"]["content_address"],
            rna.content_address,
        )
        receipt = result["stage_receipts"][-1]
        self.assertEqual(receipt["metadata"]["rna_consequence_count"], 1)
        self.assertTrue(receipt["metadata"]["rna_input_address"].startswith("sha256:"))
        self.assertTrue(result["replay_report"]["event_chain_valid"])

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

        status, batch = self._post(
            "/v1/expression-evidence/allelic-batch",
            {"batch": AllelicCountBatch((observation,)).to_dict()},
        )
        self.assertEqual(status, 200)
        self.assertEqual(batch["result_count"], 1)
        self.assertEqual(batch["results"], [allelic])

    def test_discovery_endpoints_are_public_and_deterministic(self) -> None:
        for path in (
            "/v1/case-workflow/schema",
            "/v1/case-workflow/capabilities",
            "/v1/case-workflow/adapters",
            "/v1/expression-evidence/schema",
            "/v1/expression-evidence/capabilities",
            "/v1/expression-claims/schema",
            "/v1/expression-claims/capabilities",
        ):
            status, payload = self._get(path)
            self.assertEqual(status, 200)
            self.assertIsInstance(payload, dict)

        _, adapters = self._get("/v1/case-workflow/adapters")
        self.assertFalse(adapters["configured"])
        self.assertEqual(adapters["registry_scope"], "full_discovery")
        self.assertEqual(adapters["adapter_metadata"], [])
        self.assertIsNone(adapters["limits"])

    def test_adapter_discovery_exposes_configured_effective_limits(self) -> None:
        registry = AdapterRegistry(AdapterLimits(max_selected_adapters=3))
        with tempfile.TemporaryDirectory() as directory:
            server = create_server(
                "127.0.0.1",
                0,
                Path(directory) / "data",
                adapter_registry=registry,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with urlopen(
                    f"http://127.0.0.1:{server.server_port}"
                    "/v1/case-workflow/adapters",
                    timeout=30,
                ) as response:
                    self.assertEqual(response.status, 200)
                    advertised = json.loads(response.read())
                self.assertTrue(advertised["configured"])
                self.assertEqual(advertised["registry_scope"], "full_discovery")
                self.assertEqual(advertised["adapter_metadata"], [])
                self.assertEqual(advertised["limits"], registry.limits.to_dict())
                self.assertEqual(advertised["limits"]["max_selected_adapters"], 3)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_adapter_discovery_returns_bounded_json_when_registry_validation_fails(
        self,
    ) -> None:
        registry = AdapterRegistry()
        adapter = _DiscoveryAdapter()
        registry.register(adapter)
        adapter.metadata = replace(
            adapter.metadata,
            display_name="drifted metadata",
            content_address="",
        )
        with tempfile.TemporaryDirectory() as directory:
            server = create_server(
                "127.0.0.1",
                0,
                Path(directory) / "data",
                adapter_registry=registry,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with self.assertRaises(HTTPError) as caught:
                    urlopen(
                        f"http://127.0.0.1:{server.server_port}"
                        "/v1/case-workflow/adapters",
                        timeout=30,
                    )
                self.assertEqual(caught.exception.code, 422)
                body = json.loads(caught.exception.read())
                self.assertEqual(body["error"], "validation_error")
                self.assertIn("metadata drift", body["message"])
                self.assertLessEqual(len(body["message"]), 2_048)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_adapter_discovery_contains_unexpected_failures_as_json(self) -> None:
        registry = AdapterRegistry()
        with tempfile.TemporaryDirectory() as directory:
            server = create_server(
                "127.0.0.1",
                0,
                Path(directory) / "data",
                adapter_registry=registry,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with patch.object(
                    AdapterRegistry,
                    "discovery",
                    side_effect=RuntimeError("private adapter failure detail"),
                ):
                    with self.assertRaises(HTTPError) as caught:
                        urlopen(
                            f"http://127.0.0.1:{server.server_port}"
                            "/v1/case-workflow/adapters",
                            timeout=30,
                        )
                self.assertEqual(caught.exception.code, 500)
                body = json.loads(caught.exception.read())
                self.assertEqual(
                    body,
                    {
                        "error": "internal_error",
                        "message": "adapter discovery failed",
                    },
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_scientific_routes_reject_ambiguous_or_non_finite_json(self) -> None:
        duplicate_routes = (
            ("/v1/case-workflow/prepare", "invalid_case_workflow_request"),
            ("/v1/case-workflow/run", "invalid_case_workflow_execution"),
            ("/v1/expression-evidence/outlier", "invalid_expression_outlier"),
            ("/v1/expression-evidence/allelic", "invalid_allelic_observation"),
            ("/v1/expression-evidence/allelic-batch", "invalid_allelic_batch"),
            ("/v1/expression-evidence/integrate", "invalid_rna_integration"),
            ("/v1/expression-claims/derive", "invalid_expression_claim"),
            ("/v1/expression-claims/match", "invalid_expression_claim_batch"),
        )
        for path, error_code in duplicate_routes:
            with self.subTest(path=path):
                status, payload = self._post_raw_json(path, b'{"input":{},"input":{}}')
                self.assertEqual(status, 400)
                self.assertEqual(payload["error"], error_code)
                self.assertEqual(
                    payload["message"], "JSON body contains duplicate object keys"
                )

        status, payload = self._post_raw_json(
            "/v1/expression-evidence/outlier",
            b'{"target":{"value":NaN},"references":{}}',
        )
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"], "invalid_expression_outlier")
        self.assertEqual(payload["message"], "JSON body contains a non-finite number")

    def test_scientific_routes_reject_unknown_fields_and_alias_collisions(self) -> None:
        requests = (
            (
                "/v1/case-workflow/prepare",
                {"request": {}, "ignored": True},
                "invalid_case_workflow_request",
            ),
            (
                "/v1/case-workflow/run",
                {"unexpected": True},
                "invalid_case_workflow_execution",
            ),
            (
                "/v1/case-workflow/run",
                {"prepared": {}, "data_root": "caller-controlled"},
                "invalid_case_workflow_execution",
            ),
            (
                "/v1/expression-evidence/outlier",
                {"target": {}, "references": {}, "expected_direktion": "gain"},
                "invalid_expression_outlier",
            ),
            (
                "/v1/expression-evidence/allelic",
                {"unexpected": True},
                "invalid_allelic_observation",
            ),
            (
                "/v1/expression-evidence/allelic-batch",
                {"unexpected": True},
                "invalid_allelic_batch",
            ),
            (
                "/v1/expression-evidence/integrate",
                {"unexpected": True},
                "invalid_rna_integration",
            ),
            (
                "/v1/expression-claims/derive",
                {"unexpected": True},
                "invalid_expression_claim",
            ),
            (
                "/v1/expression-claims/match",
                {"unexpected": True},
                "invalid_expression_claim_batch",
            ),
        )
        for path, request_body, error_code in requests:
            with self.subTest(path=path):
                status, payload = self._post_raw_json(
                    path,
                    json.dumps(request_body).encode("utf-8"),
                )
                self.assertEqual(status, 400)
                self.assertEqual(payload["error"], error_code)
                self.assertIn("unknown fields", payload["message"])

        for path, request_body, expected_message in (
            (
                "/v1/expression-evidence/allelic",
                {"observation": {}, "input": {}},
                "use observation or input, not both",
            ),
            (
                "/v1/expression-evidence/allelic-batch",
                {"batch": {}, "input": {}},
                "use batch or input, not both",
            ),
        ):
            with self.subTest(path=path):
                status, payload = self._post_raw_json(
                    path,
                    json.dumps(request_body).encode("utf-8"),
                )
                self.assertEqual(status, 400)
                self.assertEqual(payload["message"], expected_message)


if __name__ == "__main__":
    unittest.main()
