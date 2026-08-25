"""Contract coverage for the versioned reference and adapter boundary."""

from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.reference_manifest import (
    ADAPTER_CONFORMANCE_VERSION,
    REFERENCE_MANIFEST_VERSION,
    AdapterConformanceProbe,
    AdapterConformanceState,
    ReferenceAccessMode,
    ReferenceArtifact,
    ReferenceArtifactState,
    adapter_conformance_input_from_dict,
    build_reference_manifest,
    conform_adapter,
    query_reference_manifest,
    reference_manifest_from_dict,
    reference_manifest_schema,
    reference_manifest_summary,
    verify_reference_manifest,
)
from glio_noncode.adapters import AdapterMetadata, StaticElementAdapter

from .helpers import fixture_manifest


class ReferenceManifestTests(unittest.TestCase):
    def _adapter_and_manifest(self):
        case = fixture_manifest()
        metadata = AdapterMetadata(
            adapter_id="fixture-adapter",
            display_name="Fixture reference adapter",
            version="2026.08",
            license="synthetic-fixture",
            data_access="local_fixture",
            supported_contexts=(case.context.key,),
            channels=("regulatory_element",),
            failure_modes=("missing_context", "empty_result"),
            validation_status="tested",
        )
        artifact = ReferenceArtifact(
            artifact_id="fixture-reference",
            adapter_id=metadata.adapter_id,
            source_id="fixture-source",
            display_name="Synthetic regulatory fixture",
            version=metadata.version,
            release="fixture-2026.08",
            uri="urn:glio-noncode:fixture:reference",
            license=metadata.license,
            access_mode=ReferenceAccessMode.LOCAL_CACHE,
            size_bytes=0,
            schema_version="fixture-reference-v1",
            coordinate_system=case.context.genome_build,
            supported_contexts=(case.context.key,),
            channels=metadata.channels,
        )
        manifest = build_reference_manifest(
            (artifact,),
            manifest_id="fixture-reference-manifest",
            release_id="fixture-release-2026.08",
            assembly=case.context.genome_build,
        )
        return case, metadata, manifest

    def test_default_manifest_is_versioned_addressed_and_public(self) -> None:
        from glio_noncode.reference_manifest import build_default_reference_manifest

        manifest = build_default_reference_manifest()
        self.assertTrue(manifest.accepted)
        self.assertEqual(manifest.version, REFERENCE_MANIFEST_VERSION)
        self.assertEqual(verify_reference_manifest(manifest), ())
        self.assertEqual(manifest.artifact_count, 2)
        self.assertEqual(reference_manifest_summary(manifest)["available_count"], 2)
        payload = json.dumps(manifest.to_dict(), sort_keys=True)
        for forbidden in ("agent", "model", "language", "credential", "secret"):
            self.assertNotIn(forbidden, payload.lower())

    def test_manifest_round_trip_query_and_schema(self) -> None:
        _, _, manifest = self._adapter_and_manifest()
        reopened = reference_manifest_from_dict(manifest.to_dict())
        self.assertEqual(reopened, manifest)
        rows = query_reference_manifest(
            manifest,
            adapter_id="fixture-adapter",
            context=manifest.artifacts[0].supported_contexts[0],
            channel="regulatory_element",
        )
        self.assertEqual(tuple(item.artifact_id for item in rows), ("fixture-reference",))
        schema = reference_manifest_schema()
        self.assertEqual(schema["properties"]["version"]["const"], REFERENCE_MANIFEST_VERSION)

    def test_manifest_rejects_tampered_address_and_duplicate_receipts(self) -> None:
        _, _, manifest = self._adapter_and_manifest()
        tampered = dict(manifest.to_dict())
        tampered["release_id"] = "changed-release"
        with self.assertRaises(ValidationError):
            reference_manifest_from_dict(tampered)
        missing_address = dict(manifest.to_dict())
        missing_address["artifacts"] = [dict(manifest.artifacts[0].to_dict())]
        del missing_address["artifacts"][0]["content_address"]
        with self.assertRaises(ValidationError):
            reference_manifest_from_dict(missing_address)
        duplicate = build_reference_manifest(
            (manifest.artifacts[0], manifest.artifacts[0]),
            manifest_id="duplicate-manifest",
            release_id="duplicate-release",
            assembly=manifest.assembly,
        )
        self.assertFalse(duplicate.accepted)
        self.assertIn("artifact-ids-unique", verify_reference_manifest(duplicate))

    def test_adapter_conformance_accepts_repeatable_static_adapter(self) -> None:
        case, metadata, manifest = self._adapter_and_manifest()
        adapter = StaticElementAdapter(metadata, case.candidate_elements)
        probe = AdapterConformanceProbe(
            probe_id="fixture-probe",
            variant_id=case.variants[0].variant_id,
            context=case.context,
            expected_element_ids=tuple(sorted(item.element_id for item in case.candidate_elements)),
        )
        report = conform_adapter(adapter, manifest, (probe,))
        self.assertTrue(report.accepted)
        self.assertEqual(report.state, AdapterConformanceState.ACCEPTED)
        self.assertEqual(report.version, ADAPTER_CONFORMANCE_VERSION)
        self.assertEqual(report.failed_checks, 0)
        self.assertGreaterEqual(report.invocation_count, 2)

    def test_adapter_conformance_blocks_unavailable_receipt(self) -> None:
        case, metadata, manifest = self._adapter_and_manifest()
        unavailable = ReferenceArtifact(
            **{
                **manifest.artifacts[0].body(),
                "state": ReferenceArtifactState.QUARANTINED,
            }
        )
        blocked_manifest = build_reference_manifest(
            (unavailable,),
            manifest_id=manifest.manifest_id,
            release_id=manifest.release_id,
            assembly=manifest.assembly,
        )
        report = conform_adapter(
            StaticElementAdapter(metadata, case.candidate_elements),
            blocked_manifest,
            (),
        )
        self.assertFalse(report.accepted)
        self.assertEqual(report.state, AdapterConformanceState.BLOCKED)
        self.assertTrue(any(item.check_id == "manifest:artifact-available" and not item.passed for item in report.checks))

    def test_portable_static_conformance_input_round_trips(self) -> None:
        case, metadata, manifest = self._adapter_and_manifest()
        payload = {
            "manifest": manifest.to_dict(),
            "metadata": metadata.to_dict(),
            "elements": [item.to_dict() for item in case.candidate_elements],
            "probes": [
                {
                    "probe_id": "fixture-probe",
                    "variant_id": case.variants[0].variant_id,
                    "context": case.context.to_dict(),
                    "expected_element_ids": [item.element_id for item in case.candidate_elements],
                }
            ],
        }
        adapter, reopened, probes = adapter_conformance_input_from_dict(payload)
        report = conform_adapter(adapter, reopened, probes)
        self.assertTrue(report.accepted)

    def test_api_exposes_manifest_summary_query_and_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=60)
                for path in (
                    "/v1/reference/manifest",
                    "/v1/reference/manifest/summary",
                    "/v1/reference/manifest/schema",
                    "/v1/reference/manifest/query?context=GRCh38&limit=1",
                ):
                    connection.request("GET", path)
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200, path)
                    payload = json.loads(response.read())
                    self.assertIsInstance(payload, dict)
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_cli_exports_manifest_and_conformance(self) -> None:
        case, metadata, manifest = self._adapter_and_manifest()
        with tempfile.TemporaryDirectory() as directory:
            summary_path = Path(directory) / "summary.json"
            self.assertEqual(
                main(["reference-manifest", "--format", "summary", "--output", str(summary_path)]),
                0,
            )
            self.assertEqual(json.loads(summary_path.read_text(encoding="utf-8"))["artifact_count"], 2)
            input_path = Path(directory) / "conformance.json"
            input_path.write_text(
                json.dumps(
                    {
                        "manifest": manifest.to_dict(),
                        "metadata": metadata.to_dict(),
                        "elements": [item.to_dict() for item in case.candidate_elements],
                        "probes": [
                            {
                                "probe_id": "fixture-probe",
                                "variant_id": case.variants[0].variant_id,
                                "context": case.context.to_dict(),
                                "expected_element_ids": [item.element_id for item in case.candidate_elements],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            report_path = Path(directory) / "report.json"
            self.assertEqual(
                main(["adapter-conformance", str(input_path), "--output", str(report_path)]),
                0,
            )
            self.assertTrue(json.loads(report_path.read_text(encoding="utf-8"))["accepted"])


if __name__ == "__main__":
    unittest.main()
