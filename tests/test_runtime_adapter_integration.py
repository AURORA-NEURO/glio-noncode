from __future__ import annotations

import json
import tempfile
import threading
import unittest
from dataclasses import replace
from pathlib import Path
from urllib.request import Request, urlopen

from glio_noncode.adapters import (
    AdapterClaimCollectionReport,
    AdapterMetadata,
    AdapterRegistry,
    AdapterRegistrySnapshot,
    AdapterResolutionReport,
)
from glio_noncode.api import create_server
from glio_noncode.case_workflow import run_case
from glio_noncode.errors import ValidationError
from glio_noncode.models import (
    CandidateElement,
    CaseManifest,
    EdgeType,
    EvidenceClaim,
    EvidenceState,
    EvidenceTier,
    ReferenceContext,
    VariantIdentity,
)
from glio_noncode.runtime import CaseRuntime
from glio_noncode.serialization import content_hash

from .helpers import fixture_manifest
from .test_case_workflow import prepared as prepared_case_fixture


class RuntimeEvidenceAdapter:
    def __init__(
        self,
        element: CandidateElement,
        *,
        adapter_id: str = "runtime-evidence",
        invalid_edge: bool = False,
    ) -> None:
        self.element = element
        self.invalid_edge = invalid_edge
        self.metadata = AdapterMetadata(
            adapter_id=adapter_id,
            display_name="Runtime evidence fixture",
            version="2026.09",
            license="synthetic-fixture",
            data_access="local_fixture",
            supported_contexts=(element.context.key,),
            channels=("adapter_signal",),
            failure_modes=("empty_result",),
            validation_status="integration-tested",
            source_ids=(element.source_id,),
        )

    def resolve_variant_elements(
        self,
        variant: VariantIdentity,
        context: ReferenceContext,
    ) -> tuple[CandidateElement, ...]:
        return (self.element,)

    def resolve_elements(
        self,
        variant_id: str,
        context: ReferenceContext,
    ) -> tuple[CandidateElement, ...]:
        raise AssertionError("typed variant resolution must take precedence")

    def collect_claims(
        self,
        variant_id: str,
        element_id: str,
        context: ReferenceContext,
    ) -> tuple[EvidenceClaim, ...]:
        edge_id = "edge-invalid"
        if not self.invalid_edge:
            digest = content_hash(
                {
                    "source": variant_id,
                    "target": element_id,
                    "type": EdgeType.VARIANT_TO_ELEMENT.value,
                }
            ).split(":", 1)[1]
            edge_id = f"edge-{digest[:20]}"
        return (
            EvidenceClaim(
                evidence_id=content_hash(
                    {
                        "adapter": self.metadata.adapter_id,
                        "variant": variant_id,
                        "element": element_id,
                    },
                    prefix="claim",
                ),
                edge_id=edge_id,
                source_id=self.element.source_id,
                channel="adapter_signal",
                state=EvidenceState.SUPPORTED,
                tier=EvidenceTier.EXPERIMENTAL,
                score=0.94,
                confidence=0.92,
                context=context,
                summary="Bounded external adapter support for this variant-element edge.",
                payload={"assay": "synthetic_runtime_fixture"},
                produced_by=self.metadata.adapter_id,
                created_at="2026-09-07T12:00:00+00:00",
            ),
        )


def _adapter_element(
    manifest: CaseManifest | None = None,
    *,
    conflicting: bool = False,
) -> CandidateElement:
    manifest = fixture_manifest() if manifest is None else manifest
    original = manifest.candidate_elements[0]
    return replace(
        original,
        element_id=(original.element_id if conflicting else "enhancer-adapter-runtime"),
        start=original.start + (1 if conflicting else 20),
        end=original.end + (1 if conflicting else 20),
        source_id="runtime-adapter-source",
        context=manifest.context,
        target_genes=("GENE_ADAPTER",),
        state_ids=("state-adapter-supported",),
        annotations={"mechanism": "adapter-backed regulatory activity"},
    )


class RuntimeAdapterIntegrationTests(unittest.TestCase):
    def test_adapter_claims_materialize_into_replay_closed_hypotheses(self) -> None:
        manifest = fixture_manifest()
        registry = AdapterRegistry()
        registry.register(RuntimeEvidenceAdapter(_adapter_element()))

        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory, adapter_registry=registry)
            dossier = runtime.evaluate(manifest, adapter_ids=("runtime-evidence",))
            snapshot = runtime.load_run_snapshot(dossier.run_id)
            events = snapshot.event_log.all()
            adapter_event = next(
                event for event in events if event.event_type == "adapter_evidence_collected"
            )
            source_addresses = adapter_event.payload["source_bundle_addresses"]
            self.assertEqual(len(source_addresses), 4)

            source_records = tuple(
                runtime.store.store.get(address) for address in source_addresses
            )
            base, registry_raw, resolution_raw, claims_raw = source_records
            self.assertEqual(content_hash(base), source_addresses[0])
            self.assertEqual(
                AdapterRegistrySnapshot.from_dict(registry_raw),
                registry.snapshot(),
            )
            resolution = AdapterResolutionReport.from_dict(resolution_raw)
            report = AdapterClaimCollectionReport.from_dict(claims_raw)
            self.assertEqual(report.resolution_address, resolution.content_address)
            self.assertEqual(report.claim_count, 1)
            self.assertIn(_adapter_element(), snapshot.manifest.candidate_elements)
            for key, address in zip(
                (
                    "adapter_input_manifest",
                    "adapter_registry_snapshot",
                    "adapter_resolution_report",
                    "adapter_claim_collection_report",
                ),
                source_addresses,
                strict=True,
            ):
                self.assertEqual(snapshot.manifest.input_versions[key], address)

            claim = report.claims[0]
            persisted = next(
                item for item in dossier.evidence if item.evidence_id == claim.evidence_id
            )
            self.assertEqual(persisted, claim)
            matching_edges = tuple(
                edge
                for hypothesis in dossier.hypotheses
                for edge in hypothesis.edges
                if claim.evidence_id in edge.claim_ids
            )
            self.assertGreater(len(matching_edges), 0)
            self.assertTrue(all(edge.edge_id == claim.edge_id for edge in matching_edges))

        with tempfile.TemporaryDirectory() as baseline_directory:
            baseline = CaseRuntime(baseline_directory).evaluate(manifest)
            self.assertNotEqual(baseline.run_id, dossier.run_id)
            self.assertNotEqual(baseline.content_address, dossier.content_address)

    def test_adapter_failures_and_element_conflicts_write_no_run_objects(self) -> None:
        cases: tuple[tuple[RuntimeEvidenceAdapter, str], ...] = (
            (
                RuntimeEvidenceAdapter(_adapter_element(), invalid_edge=True),
                "unknown or ineligible edge",
            ),
            (
                RuntimeEvidenceAdapter(_adapter_element(conflicting=True)),
                "conflicts with an existing manifest element",
            ),
        )
        for adapter, expected in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as directory:
                registry = AdapterRegistry()
                registry.register(adapter)
                runtime = CaseRuntime(directory, adapter_registry=registry)
                with self.assertRaisesRegex(ValidationError, expected):
                    runtime.evaluate(
                        fixture_manifest(),
                        adapter_ids=(adapter.metadata.adapter_id,),
                    )
                self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())
                self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())

    def test_adapter_selection_is_exact_and_requires_a_configured_registry(self) -> None:
        manifest = fixture_manifest()
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            for malformed in (["runtime-evidence"], (1,), "runtime-evidence"):
                with self.subTest(malformed=malformed), self.assertRaises(ValidationError):
                    runtime.evaluate(manifest, adapter_ids=malformed)  # type: ignore[arg-type]
            with self.assertRaisesRegex(ValidationError, "configured AdapterRegistry"):
                runtime.evaluate(manifest, adapter_ids=("runtime-evidence",))
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())

    def test_case_workflow_exposes_adapter_selection_and_dynamic_identity(self) -> None:
        prepared = prepared_case_fixture()
        assert prepared.manifest is not None
        registry = AdapterRegistry()
        registry.register(RuntimeEvidenceAdapter(_adapter_element(prepared.manifest)))

        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory, adapter_registry=registry)
            result = run_case(
                prepared,
                runtime=runtime,
                adapter_ids=("runtime-evidence",),
            )
            self.assertTrue(result.accepted, result.to_dict())
            assert result.dossier is not None
            self.assertNotEqual(result.dossier.run_id, prepared.run_id)
            runtime_receipt = result.stage_receipts[-1]
            self.assertEqual(runtime_receipt.metadata["adapter_ids"], ["runtime-evidence"])
            self.assertEqual(
                runtime_receipt.metadata["evaluation_run_id"],
                result.dossier.run_id,
            )
            snapshot = runtime.load_run_snapshot(result.dossier.run_id)
            self.assertIn(
                "adapter_claim_collection_report",
                snapshot.manifest.input_versions,
            )

        invalid = run_case(
            prepared,
            adapter_ids=("not canonical adapter id",),
        )
        self.assertFalse(invalid.accepted)
        self.assertIn("invalid_adapter_selection", {item.code for item in invalid.issues})

    def test_http_surface_lists_and_executes_configured_adapters(self) -> None:
        prepared = prepared_case_fixture()
        assert prepared.manifest is not None
        registry = AdapterRegistry()
        registry.register(RuntimeEvidenceAdapter(_adapter_element(prepared.manifest)))

        with tempfile.TemporaryDirectory() as directory:
            server = create_server(
                "127.0.0.1",
                0,
                Path(directory) / "data",
                adapter_registry=registry,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                with urlopen(f"{base}/v1/case-workflow/adapters", timeout=5) as response:
                    advertised = json.loads(response.read().decode("utf-8"))
                self.assertTrue(advertised["configured"])
                self.assertEqual(advertised["adapter_ids"], ["runtime-evidence"])
                self.assertEqual(advertised["registry_snapshot"]["count"], 1)

                request = Request(
                    f"{base}/v1/case-workflow/run",
                    data=json.dumps(
                        {
                            "prepared": prepared.to_dict(),
                            "adapter_ids": ["runtime-evidence"],
                        }
                    ).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(request, timeout=10) as response:
                    result = json.loads(response.read().decode("utf-8"))
                self.assertTrue(result["accepted"])
                self.assertNotEqual(result["dossier"]["run_id"], prepared.run_id)
                self.assertEqual(
                    result["stage_receipts"][-1]["metadata"]["adapter_ids"],
                    ["runtime-evidence"],
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
