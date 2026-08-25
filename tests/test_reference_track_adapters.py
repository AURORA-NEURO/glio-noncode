from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.atlas import PublicAtlasRetriever
from glio_noncode.cli import main
from glio_noncode.data_sources import ReferenceBundle
from glio_noncode.identity import parse_variant
from glio_noncode.models import EvidenceState, ReferenceContext
from glio_noncode.reference_interval_index import ReferenceIndexQuery
from glio_noncode.reference_manifest import ReferenceAccessMode, ReferenceArtifactState
from glio_noncode.reference_registry import CoordinateSystem
from glio_noncode.reference_track_adapters import (
    DeclaredReferenceTrackAdapter,
    ReferenceTrackAdapterRegistry,
    ReferenceTrackAdapterState,
    ReferenceTrackConformanceCategory,
    ReferenceTrackMetadata,
    ReferenceTrackProbe,
    ReferenceTrackQueryState,
    conform_reference_track_adapter,
)


CONTEXT = "GRCh38|glioma|adult|stem_like|unknown|unknown"
GENERAL = "GRCh38|all|all|all|unknown|unknown"
FOREIGN = "GRCh38|brain|adult|astrocyte|unknown|unknown"


def metadata(**overrides: object) -> ReferenceTrackMetadata:
    values: dict[str, object] = {
        "adapter_id": "declared-atac",
        "display_name": "Declared ATAC public track",
        "version": "2026.08",
        "assembly": "GRCh38",
        "track_type": "open_chromatin",
        "source_id": "SRC-ATAC-PUBLIC",
        "source_version": "release-1",
        "license": "CC-BY-4.0",
        "access_mode": ReferenceAccessMode.LOCAL_CACHE,
        "uri": "urn:glio:track:declared-atac:2026.08",
        "coordinate_system": CoordinateSystem.ONE_BASED_INCLUSIVE,
        "supported_contexts": ("GRCh38|glioma|adult|*|unknown|unknown",),
        "channels": ("accessibility",),
        "limitations": (
            "Accessibility overlap is not proof of regulatory activity or causality.",
        ),
    }
    values.update(overrides)
    return ReferenceTrackMetadata(**values)


def rows() -> list[dict[str, object]]:
    return [
        {
            "record_id": "exact",
            "chromosome": "7",
            "start": 100,
            "end": 120,
            "context_key": CONTEXT,
            "payload": {"signal": 0.9, "sample_id": "removed"},
        },
        {
            "record_id": "general",
            "chromosome": "chr7",
            "start": 110,
            "end": 135,
            "context_key": GENERAL,
            "payload": {"signal": 0.5},
        },
    ]


class EmptyReference:
    def retrieve(self, variant, context, *, window_bp=None):
        return ReferenceBundle(
            variant_id=variant.variant_id,
            context_key=context.key,
            sequence=None,
            elements=(),
            raw_features=(),
            receipts=(),
            warnings=(),
            content_address="reference-bundle:empty",
        )


class ReferenceTrackAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter_metadata = metadata()
        self.build = DeclaredReferenceTrackAdapter.from_rows(
            self.adapter_metadata,
            rows(),
            block_size=1,
        )
        self.adapter = self.build.adapter

    def test_declaration_builds_public_safe_adapter_and_query(self) -> None:
        self.assertTrue(self.build.accepted, self.build.to_dict())
        self.assertEqual(self.adapter.state, ReferenceTrackAdapterState.ACCEPTED)
        report = self.adapter.query(
            ReferenceIndexQuery.from_mapping(
                {
                    "chromosome": "7",
                    "start": 112,
                    "end": 116,
                    "context_key": CONTEXT,
                }
            )
        )
        self.assertEqual(report.state, ReferenceTrackQueryState.SUPPORTED)
        self.assertEqual([item.record_id for item in report.matches], ["exact", "general"])
        self.assertNotIn("sample_id", json.dumps(report.to_dict()).lower())
        self.assertEqual(report.metadata.license, "CC-BY-4.0")
        self.assertEqual(report.metadata.access_mode, ReferenceAccessMode.LOCAL_CACHE)

    def test_adapter_context_gate_distinguishes_out_of_domain_and_absent(self) -> None:
        out_of_domain = self.adapter.query(
            {
                "chromosome": "7",
                "start": 112,
                "end": 116,
                "context_key": FOREIGN,
            }
        )
        absent = self.adapter.query(
            {
                "chromosome": "8",
                "start": 112,
                "end": 116,
                "context_key": CONTEXT,
            }
        )
        self.assertEqual(out_of_domain.state, ReferenceTrackQueryState.OUT_OF_DOMAIN)
        self.assertEqual(absent.state, ReferenceTrackQueryState.ABSENT)
        self.assertEqual(absent.interval_candidate_count, 0)

    def test_round_trip_reopens_declared_adapter_and_rejects_tampering(self) -> None:
        reopened = DeclaredReferenceTrackAdapter.from_dict(self.adapter.to_dict())
        self.assertEqual(reopened.content_address, self.adapter.content_address)
        self.assertEqual(reopened.to_dict(), self.adapter.to_dict())
        tampered = self.adapter.to_dict()
        tampered["metadata"]["license"] = "changed"
        with self.assertRaises(Exception):
            DeclaredReferenceTrackAdapter.from_dict(tampered)

    def test_unavailable_source_abstains_without_becoming_absent(self) -> None:
        unavailable = DeclaredReferenceTrackAdapter.from_rows(
            metadata(state=ReferenceArtifactState.UNAVAILABLE),
            rows(),
        ).adapter
        report = unavailable.query(
            {
                "chromosome": "7",
                "start": 112,
                "end": 116,
                "context_key": CONTEXT,
            }
        )
        self.assertEqual(report.state, ReferenceTrackQueryState.ABSTAINED)
        self.assertFalse(report.accepted)
        self.assertTrue(any("unavailable" in warning for warning in report.warnings))

    def test_conformance_requires_limitations_and_deterministic_probe(self) -> None:
        probe = ReferenceTrackProbe.from_mapping(
            {
                "probe_id": "supported-overlap",
                "query": {
                    "chromosome": "7",
                    "start": 112,
                    "end": 116,
                    "context_key": CONTEXT,
                },
                "expected_state": "supported",
            }
        )
        report = conform_reference_track_adapter(self.adapter, (probe,))
        self.assertTrue(report.accepted, report.to_dict())
        self.assertEqual(report.state, ReferenceTrackAdapterState.ACCEPTED)
        self.assertTrue(
            any(
                check.category is ReferenceTrackConformanceCategory.DETERMINISM
                and check.accepted
                for check in report.checks
            )
        )
        no_probe = conform_reference_track_adapter(self.adapter)
        self.assertFalse(no_probe.accepted)
        self.assertEqual(no_probe.state, ReferenceTrackAdapterState.REVIEW)

    def test_registry_queries_all_adapters_and_builds_manifest(self) -> None:
        second_metadata = metadata(
            adapter_id="declared-histone",
            display_name="Declared histone public track",
            track_type="histone_mark",
            source_id="SRC-HISTONE-PUBLIC",
            channels=("histone",),
            uri="urn:glio:track:declared-histone:2026.08",
        )
        second = DeclaredReferenceTrackAdapter.from_rows(second_metadata, rows()).adapter
        registry = ReferenceTrackAdapterRegistry((second, self.adapter))
        reports = registry.query_all(
            {
                "chromosome": "7",
                "start": 112,
                "end": 116,
                "context_key": CONTEXT,
            }
        )
        self.assertEqual([report.adapter_id for report in reports], ["declared-atac", "declared-histone"])
        manifest = registry.manifest()
        self.assertTrue(manifest.accepted)
        self.assertEqual(manifest.artifact_count, 2)
        self.assertEqual(registry.health()["count"], 2)

    def test_atlas_emits_declared_track_observations_and_evidence_boundary(self) -> None:
        registry = ReferenceTrackAdapterRegistry((self.adapter,))
        variant = parse_variant("7:100:A>T", genome_build="GRCh38", variant_id="v1")
        context = ReferenceContext("GRCh38", "glioma", "adult", "stem_like")
        bundle = PublicAtlasRetriever(
            EmptyReference(),
            track_adapters=registry,
        ).retrieve(variant, context)
        track_observation = next(
            item for item in bundle.observations if item.feature_type == "reference_track:open_chromatin"
        )
        self.assertEqual(track_observation.state, EvidenceState.SUPPORTED)
        self.assertEqual(track_observation.source_id, "SRC-ATAC-PUBLIC")
        self.assertEqual(track_observation.payload["metadata"]["license"], "CC-BY-4.0")
        self.assertEqual(len(bundle.track_reports), 1)
        self.assertTrue(bundle.to_evidence_claims(variant=variant, context=context))

    def test_cli_build_query_conformance_and_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            row_path = root / "rows.json"
            metadata_path = root / "metadata.json"
            adapter_path = root / "adapter.json"
            query_path = root / "query.json"
            conformance_path = root / "conformance.json"
            schema_path = root / "schema.json"
            row_path.write_text(json.dumps({"records": rows()}), encoding="utf-8")
            metadata_path.write_text(json.dumps(self.adapter_metadata.to_dict()), encoding="utf-8")
            self.assertEqual(
                main(
                    [
                        "build-reference-adapter",
                        str(row_path),
                        "--metadata",
                        str(metadata_path),
                        "--output",
                        str(adapter_path),
                    ]
                ),
                0,
            )
            build_payload = json.loads(adapter_path.read_text(encoding="utf-8"))
            adapter_path.write_text(json.dumps(build_payload["adapter"]), encoding="utf-8")
            self.assertEqual(
                main(
                    [
                        "query-reference-adapter",
                        str(adapter_path),
                        "--chromosome",
                        "7",
                        "--start",
                        "112",
                        "--end",
                        "116",
                        "--context-key",
                        CONTEXT,
                        "--output",
                        str(query_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "reference-adapter-conformance",
                        str(adapter_path),
                        "--output",
                        str(conformance_path),
                    ]
                ),
                2,
            )
            self.assertEqual(
                main(["reference-adapter-schema", "--output", str(schema_path)]),
                0,
            )
            self.assertEqual(
                json.loads(schema_path.read_text(encoding="utf-8"))["version"],
                "reference-track-adapter-schema-v1",
            )
            self.assertEqual(
                json.loads(query_path.read_text(encoding="utf-8"))["state"],
                "supported",
            )

    def test_api_build_query_and_capability_routes(self) -> None:
        server = create_server("127.0.0.1", 0, ".glio-reference-adapter-test")
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            connection = HTTPConnection(host, port, timeout=20)
            connection.request("GET", "/v1/reference/adapters/schema")
            schema_response = connection.getresponse()
            self.assertEqual(schema_response.status, 200)
            self.assertEqual(
                json.loads(schema_response.read())["adapter_version"],
                "reference-track-adapter-v1",
            )
            body = json.dumps(
                {
                    "metadata": self.adapter_metadata.to_dict(),
                    "records": rows(),
                }
            ).encode()
            connection.request(
                "POST",
                "/v1/reference/adapters/build",
                body=body,
                headers={"Content-Type": "application/json", "Content-Length": str(len(body))},
            )
            build_response = connection.getresponse()
            self.assertEqual(build_response.status, 200)
            build_payload = json.loads(build_response.read())
            query_body = json.dumps(
                {
                    "adapter": build_payload["adapter"],
                    "query": {
                        "chromosome": "7",
                        "start": 112,
                        "end": 116,
                        "context_key": CONTEXT,
                    },
                }
            ).encode()
            connection.request(
                "POST",
                "/v1/reference/adapters/query",
                body=query_body,
                headers={
                    "Content-Type": "application/json",
                    "Content-Length": str(len(query_body)),
                },
            )
            query_response = connection.getresponse()
            self.assertEqual(query_response.status, 200)
            self.assertEqual(json.loads(query_response.read())["state"], "supported")
            connection.request("GET", "/v1/reference/adapters/capabilities")
            capabilities_response = connection.getresponse()
            self.assertEqual(capabilities_response.status, 200)
            self.assertIn("release_gate", json.loads(capabilities_response.read()))
            connection.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
