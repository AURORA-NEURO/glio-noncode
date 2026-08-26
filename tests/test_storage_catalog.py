"""Deep contract, export, packet, CLI, and HTTP tests for storage catalogs."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.batch_runtime import BatchRuntime
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.runtime import CaseRuntime
from glio_noncode.serialization import canonical_json
from glio_noncode.storage_catalog import (
    build_storage_catalog,
    diff_storage_catalog,
    query_storage_catalog,
    storage_catalog_capabilities,
    storage_catalog_entries_csv,
    storage_catalog_indexes_csv,
    storage_catalog_json,
    storage_catalog_markdown,
    storage_catalog_schema,
    verify_storage_catalog,
)
from glio_noncode.storage_catalog_contracts import (
    STORAGE_CATALOG_INDEXES,
    STORAGE_CATALOG_RESOURCES,
    StorageCatalog,
)
from glio_noncode.storage_catalog_observability import (
    build_storage_catalog_observability,
    query_storage_catalog_observability,
    storage_catalog_observability_capabilities,
    storage_catalog_observability_events_csv,
    storage_catalog_observability_json,
    storage_catalog_observability_metrics_csv,
    storage_catalog_observability_schema,
)
from glio_noncode.storage_catalog_observability_contracts import StorageCatalogObservability
from glio_noncode.storage_catalog_packet import (
    build_storage_catalog_packet,
    load_storage_catalog_packet,
    storage_catalog_packet_capabilities,
    storage_catalog_packet_schema,
    verify_storage_catalog_packet,
    write_storage_catalog_packet,
)
from glio_noncode.storage_catalog_packet_contracts import STORAGE_CATALOG_PACKET_PAYLOAD_IDS

from .helpers import fixture_manifest


class StorageCatalogTests(unittest.TestCase):
    def _runtime(self, directory: str) -> CaseRuntime:
        runtime = CaseRuntime(directory)
        runtime.evaluate(fixture_manifest())
        return runtime

    def _populated_catalog(self, directory: str):
        runtime = self._runtime(directory)
        BatchRuntime(runtime=runtime).evaluate(
            [
                fixture_manifest().to_dict(),
                replace(
                    fixture_manifest(),
                    case_id="storage-catalog-batch-case",
                    requested_by="storage-catalog-requester",
                ).to_dict(),
            ]
        )
        return runtime, build_storage_catalog(runtime)

    def test_empty_catalog_is_closed_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = build_storage_catalog(CaseRuntime(directory))
            second = build_storage_catalog(CaseRuntime(directory))
            self.assertTrue(first.accepted)
            self.assertEqual(first.to_dict(), second.to_dict())
            self.assertEqual(first.content_address, second.content_address)
            self.assertEqual(first.entry_count, 0)
            self.assertEqual(first.index_row_count, 0)
            self.assertEqual(first.audit_address.split(":", 1)[0], "storage-audit")
            self.assertEqual(
                tuple(first.to_dict()),
                (
                    "storage_catalog_version",
                    "root",
                    "audit_address",
                    "entries",
                    "address_index",
                    "path_index",
                    "kind_index",
                    "state_index",
                    "accepted",
                    "boundary",
                    "entry_count",
                    "object_count",
                    "missing_count",
                    "run_count",
                    "batch_count",
                    "unexpected_count",
                    "index_row_count",
                    "content_address",
                ),
            )

    def test_populated_catalog_normalizes_all_core_resources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, catalog = self._populated_catalog(directory)
            self.assertTrue(catalog.accepted)
            self.assertGreaterEqual(catalog.object_count, 7)
            self.assertEqual(catalog.run_count, 2)
            self.assertEqual(catalog.batch_count, 1)
            self.assertEqual(catalog.missing_count, 0)
            self.assertEqual(catalog.unexpected_count, 0)
            self.assertEqual(len(catalog.entries), catalog.entry_count)
            self.assertEqual(
                tuple(item.entry_id for item in catalog.entries),
                tuple(sorted(item.entry_id for item in catalog.entries)),
            )
            self.assertTrue(
                all(item.audit_address == catalog.audit_address for item in catalog.entries)
            )
            self.assertTrue(all(item.path for item in catalog.entries))
            self.assertTrue(
                all(item.target_address for item in catalog.entries if item.kind.value == "object")
            )
            self.assertTrue(
                any(
                    item.resource_key.startswith("batch-")
                    for item in catalog.entries
                    if item.kind.value == "batch"
                )
            )
            self.assertEqual(runtime.store.root, Path(directory))
            for index_name in STORAGE_CATALOG_INDEXES:
                rows = tuple(getattr(catalog, f"{index_name}_index"))
                self.assertEqual(
                    tuple(row.key for row in rows), tuple(sorted(row.key for row in rows))
                )
                self.assertTrue(all(row.entry_ids for row in rows))

    def test_exact_kind_resource_and_prefix_queries_use_indexes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _runtime, catalog = self._populated_catalog(directory)
            objects = query_storage_catalog(catalog, resource="objects", limit=500)
            self.assertEqual(objects.total, catalog.object_count)
            self.assertEqual(objects.index_used, "kind")
            self.assertTrue(all(item["kind"] == "object" for item in objects.items))
            runs = query_storage_catalog(catalog, kind="run", limit=500)
            self.assertEqual(runs.total, 2)
            self.assertEqual(runs.index_used, "kind")
            self.assertTrue(all(item["entry_id"].startswith("run:") for item in runs.items))
            target = next(item.target_address for item in catalog.entries if item.target_address)
            by_prefix = query_storage_catalog(catalog, prefix=target[:20], limit=500)
            self.assertGreaterEqual(by_prefix.total, 1)
            self.assertIn("address", by_prefix.index_used or "")
            by_path = query_storage_catalog(catalog, prefix="runs/", limit=500)
            self.assertEqual(by_path.total, 2)
            self.assertIn("path", by_path.index_used or "")

    def test_boolean_text_and_pagination_filters_are_stable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _runtime, catalog = self._populated_catalog(directory)
            accepted = query_storage_catalog(catalog, accepted=True, limit=500)
            self.assertEqual(accepted.total, catalog.entry_count)
            referenced = query_storage_catalog(catalog, referenced=True, limit=500)
            self.assertEqual(referenced.total, catalog.entry_count)
            page = query_storage_catalog(catalog, offset=1, limit=2)
            self.assertEqual(page.offset, 1)
            self.assertEqual(len(page.items), 2)
            self.assertTrue(page.has_more)
            tail = query_storage_catalog(catalog, offset=10_000, limit=50)
            self.assertEqual(tail.items, ())
            self.assertFalse(tail.has_more)
            text = query_storage_catalog(catalog, text="run-", limit=500)
            self.assertTrue(all("run-" in json.dumps(item).lower() for item in text.items))
            self.assertEqual(
                query_storage_catalog(catalog, kind="run", state="accepted", limit=500).total,
                2,
            )

    def test_missing_orphan_and_unexpected_entries_are_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = self._runtime(directory)
            run_record = runtime.get_run(runtime._run_id(fixture_manifest()))
            dossier_address = str(run_record["dossier_address"])
            dossier_path = runtime.store.store.objects / (
                dossier_address.split(":", 1)[1] + ".json"
            )
            dossier_path.unlink()
            runtime.store.store.put({"catalog_orphan": True})
            (Path(directory) / "objects" / "untracked.bin").write_bytes(b"unexpected")
            catalog = build_storage_catalog(runtime)
            self.assertFalse(catalog.accepted)
            self.assertGreaterEqual(catalog.missing_count, 1)
            self.assertGreaterEqual(
                sum(item.state.value == "orphan" for item in catalog.entries), 1
            )
            self.assertEqual(catalog.unexpected_count, 1)
            missing = query_storage_catalog(catalog, state="missing", limit=500)
            orphan = query_storage_catalog(catalog, state="orphan", limit=500)
            unexpected = query_storage_catalog(catalog, resource="unexpected", limit=500)
            self.assertTrue(all(item["state"] == "missing" for item in missing.items))
            self.assertTrue(all(item["state"] == "orphan" for item in orphan.items))
            self.assertEqual(unexpected.total, 1)
            self.assertEqual(unexpected.items[0]["path"], "objects/untracked.bin")

    def test_catalog_mapping_roundtrip_and_strict_verification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _runtime, catalog = self._populated_catalog(directory)
            decoded = verify_storage_catalog(json.loads(storage_catalog_json(catalog)))
            self.assertEqual(decoded.to_dict(), catalog.to_dict())
            self.assertEqual(
                StorageCatalog.from_mapping(catalog.to_dict()).content_address,
                catalog.content_address,
            )
            tampered = catalog.to_dict()
            tampered["entries"] = list(tampered["entries"])
            tampered["entries"][0]["resource_key"] = "changed"
            with self.assertRaises(ValidationError):
                verify_storage_catalog(tampered)
            unknown = catalog.to_dict()
            unknown["private_detail"] = "not allowed"
            with self.assertRaises(ValidationError):
                verify_storage_catalog(unknown)

    def test_query_contract_rejects_unsupported_values_and_bounds(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = build_storage_catalog(CaseRuntime(directory))
            for kwargs in (
                {"resource": "nope"},
                {"kind": "nope"},
                {"state": "nope"},
                {"limit": 0},
                {"limit": 501},
                {"offset": -1},
                {"accepted": "true"},
            ):
                with self.assertRaises(ValidationError):
                    query_storage_catalog(catalog, **kwargs)

    def test_catalog_diff_reports_structural_changes(self) -> None:
        with (
            tempfile.TemporaryDirectory() as left_directory,
            tempfile.TemporaryDirectory() as right_directory,
        ):
            left = build_storage_catalog(CaseRuntime(left_directory))
            _runtime, right = self._populated_catalog(right_directory)
            result = diff_storage_catalog(left, right)
            self.assertTrue(result.accepted)
            self.assertEqual(result.baseline_address, left.content_address)
            self.assertEqual(result.candidate_address, right.content_address)
            self.assertEqual(result.removed_entry_ids, ())
            self.assertGreater(len(result.added_entry_ids), 0)
            self.assertTrue(result.counts_changed)
            self.assertTrue(result.content_address.startswith("storage-catalog-diff:"))
            self.assertEqual(diff_storage_catalog(right, right).added_entry_ids, ())
            self.assertEqual(diff_storage_catalog(right, right).changed_entry_ids, ())

    def test_exports_have_fixed_headers_and_no_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _runtime, catalog = self._populated_catalog(directory)
            entries = storage_catalog_entries_csv(catalog)
            indexes = storage_catalog_indexes_csv(catalog)
            markdown = storage_catalog_markdown(catalog)
            self.assertTrue(entries.startswith("entry_id,kind,state,resource_key"))
            self.assertTrue(indexes.startswith("index_name,key,entry_ids,content_address"))
            self.assertIn("# Storage catalog", markdown)
            self.assertIn(catalog.content_address, markdown)
            serialized = (storage_catalog_json(catalog) + entries + indexes + markdown).lower()
            self.assertNotIn('"payload"', serialized)
            self.assertNotIn('"content"', serialized)

    def test_observability_is_deterministic_and_identity_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _runtime, catalog = self._populated_catalog(directory)
            first = build_storage_catalog_observability(catalog)
            second = build_storage_catalog_observability(catalog)
            self.assertEqual(first.to_dict(), second.to_dict())
            self.assertEqual(first.catalog_address, catalog.content_address)
            self.assertGreaterEqual(first.event_count, catalog.entry_count * 2)
            self.assertEqual(first.metric_count, 19)
            self.assertEqual(
                tuple(item.sequence for item in first.events),
                tuple(range(1, first.event_count + 1)),
            )
            self.assertEqual(
                tuple(item.name for item in first.metrics),
                tuple(sorted(item.name for item in first.metrics)),
            )
            self.assertEqual(
                StorageCatalogObservability.from_mapping(first.to_dict()).content_address,
                first.content_address,
            )
            self.assertTrue(storage_catalog_observability_json(first).startswith("{"))
            self.assertTrue(
                storage_catalog_observability_events_csv(first).startswith(
                    "sequence,event_type,entry_id"
                )
            )
            self.assertTrue(
                storage_catalog_observability_metrics_csv(first).startswith("name,value,unit")
            )

    def test_observability_queries_filter_event_type_state_and_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _runtime, catalog = self._populated_catalog(directory)
            observation = build_storage_catalog_observability(catalog)
            missing = query_storage_catalog_observability(
                observation, event_type="run-entry", limit=500
            )
            self.assertEqual(missing.total, catalog.run_count)
            self.assertTrue(all(item["event_type"] == "run-entry" for item in missing.items))
            accepted = query_storage_catalog_observability(observation, state="accepted", limit=500)
            self.assertGreater(accepted.total, 0)
            self.assertTrue(all(item["state"] == "accepted" for item in accepted.items))
            searched = query_storage_catalog_observability(observation, text="batch:", limit=500)
            self.assertTrue(all("batch:" in json.dumps(item) for item in searched.items))
            self.assertEqual(
                query_storage_catalog_observability(observation, offset=9999).items, ()
            )
            with self.assertRaises(ValidationError):
                query_storage_catalog_observability(observation, event_type="unsupported")

    def test_packet_has_fixed_artifacts_and_roundtrips_offline(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            tempfile.TemporaryDirectory() as packet_directory,
        ):
            _runtime, catalog = self._populated_catalog(directory)
            packet = build_storage_catalog_packet(catalog)
            self.assertTrue(packet.accepted)
            self.assertEqual(
                tuple(item.artifact_id for item in packet.artifacts),
                STORAGE_CATALOG_PACKET_PAYLOAD_IDS,
            )
            self.assertEqual(packet.manifest.payload_artifact_count, 10)
            self.assertEqual(packet.manifest.artifact_count, 11)
            self.assertTrue(packet.content_address.startswith("storage-catalog-packet:"))
            self.assertFalse(any("payload" in key for key in packet.to_dict()))
            write_storage_catalog_packet(packet, packet_directory)
            verification = verify_storage_catalog_packet(packet_directory)
            self.assertTrue(verification.accepted, verification.to_dict())
            self.assertEqual(verification.checked_artifact_count, 10)
            loaded = load_storage_catalog_packet(packet_directory)
            self.assertTrue(loaded.verification.accepted)
            self.assertEqual(loaded.catalog.content_address, catalog.content_address)
            self.assertEqual(loaded.observability.catalog_address, catalog.content_address)
            self.assertEqual(loaded.packet_id, packet.packet_id)

    def test_packet_verifier_detects_tamper_extra_and_nonempty_destination(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            tempfile.TemporaryDirectory() as packet_directory,
        ):
            _runtime, catalog = self._populated_catalog(directory)
            packet = build_storage_catalog_packet(catalog)
            write_storage_catalog_packet(packet, packet_directory)
            with self.assertRaises(ValidationError):
                write_storage_catalog_packet(packet, packet_directory)
            (Path(packet_directory) / "catalog" / "entries.csv").write_text(
                "tampered\n", encoding="utf-8"
            )
            (Path(packet_directory) / "extra.txt").write_text("extra", encoding="utf-8")
            verification = verify_storage_catalog_packet(packet_directory)
            self.assertFalse(verification.accepted)
            self.assertIn("catalog/entries.csv", verification.tampered_paths)
            self.assertIn("extra.txt", verification.unexpected_paths)
            with self.assertRaises(ValidationError):
                load_storage_catalog_packet(packet_directory)

    def test_schemas_and_capabilities_close_the_public_boundary(self) -> None:
        schema = storage_catalog_schema()
        capabilities = storage_catalog_capabilities()
        observation_schema = storage_catalog_observability_schema()
        observation_capabilities = storage_catalog_observability_capabilities()
        packet_schema = storage_catalog_packet_schema()
        packet_capabilities = storage_catalog_packet_capabilities()
        self.assertTrue(schema["address_only"])
        self.assertFalse(schema["payload_exposure"])
        self.assertEqual(tuple(schema["indexes"]), STORAGE_CATALOG_INDEXES)
        self.assertEqual(tuple(capabilities["resources"]), STORAGE_CATALOG_RESOURCES)
        self.assertTrue(observation_schema["timestamp_free"])
        self.assertFalse(observation_capabilities["payload_exposure"])
        self.assertEqual(tuple(packet_schema["payload_ids"]), STORAGE_CATALOG_PACKET_PAYLOAD_IDS)
        self.assertEqual(packet_capabilities["payload_count"], 10)
        for value in (
            schema,
            capabilities,
            observation_schema,
            observation_capabilities,
            packet_schema,
            packet_capabilities,
        ):
            encoded = json.dumps(value, sort_keys=True).lower()
            self.assertNotIn('"agent"', encoded)
            self.assertNotIn('"assistant"', encoded)
            self.assertNotIn('"author"', encoded)

    def test_cli_exposes_catalog_family(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "catalog.json"
            self.assertEqual(
                main(["storage-catalog", "--data-root", directory, "--output", str(output)]), 0
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(payload["accepted"])
            self.assertEqual(payload["entry_count"], 0)
            for command, filename in (
                ("storage-catalog-schema", "schema.json"),
                ("storage-catalog-capabilities", "capabilities.json"),
                ("storage-catalog-observability-schema", "observation-schema.json"),
                ("storage-catalog-observability-capabilities", "observation-capabilities.json"),
                ("storage-catalog-packet-schema", "packet-schema.json"),
                ("storage-catalog-packet-capabilities", "packet-capabilities.json"),
            ):
                target = Path(directory) / filename
                self.assertEqual(main([command, "--output", str(target)]), 0)
                self.assertTrue(json.loads(target.read_text(encoding="utf-8")))
            packet_directory = Path(directory) / "packet"
            self.assertEqual(
                main(
                    [
                        "storage-catalog-packet",
                        "--data-root",
                        directory,
                        "--destination",
                        str(packet_directory),
                    ]
                ),
                0,
            )
            verify_output = Path(directory) / "verify.json"
            self.assertEqual(
                main(
                    [
                        "storage-catalog-packet-verify",
                        str(packet_directory),
                        "--output",
                        str(verify_output),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(verify_output.read_text(encoding="utf-8"))["accepted"])

    def test_http_get_and_post_surfaces_return_catalog_identities(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = self._runtime(directory)
            expected = build_storage_catalog(runtime)
            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=60)
                for path in (
                    "/v1/storage/catalog",
                    "/v1/storage/catalog/schema",
                    "/v1/storage/catalog/capabilities",
                    "/v1/storage/catalog/entries.csv",
                    "/v1/storage/catalog/indexes.csv",
                    "/v1/storage/catalog/observability",
                    "/v1/storage/catalog/observability/schema",
                    "/v1/storage/catalog/observability/capabilities",
                    "/v1/storage/catalog/observability/events.csv",
                    "/v1/storage/catalog/observability/metrics.csv",
                    "/v1/storage/catalog/packet",
                    "/v1/storage/catalog/packet/schema",
                    "/v1/storage/catalog/packet/capabilities",
                ):
                    connection.request("GET", path)
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200, path)
                    body = response.read()
                    self.assertTrue(body, path)
                connection.request("GET", "/v1/storage/catalog")
                response = connection.getresponse()
                payload = json.loads(response.read())
                self.assertEqual(payload["catalog"]["content_address"], expected.content_address)
                query_body = json.dumps(
                    {"catalog": expected.to_dict(), "query": {"resource": "objects"}}
                ).encode()
                connection.request(
                    "POST",
                    "/v1/storage/catalog/query",
                    body=query_body,
                    headers={
                        "Content-Type": "application/json",
                        "Content-Length": str(len(query_body)),
                    },
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                query_payload = json.loads(response.read())
                self.assertEqual(query_payload["total"], expected.object_count)
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_every_resource_selector_reconciles_with_kind_counts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _runtime, catalog = self._populated_catalog(directory)
            expected = {
                "entries": catalog.entry_count,
                "objects": catalog.object_count,
                "runs": catalog.run_count,
                "batches": catalog.batch_count,
                "missing": catalog.missing_count,
                "unexpected": catalog.unexpected_count,
            }
            for resource, count in expected.items():
                result = query_storage_catalog(catalog, resource=resource, limit=500)
                self.assertEqual(result.total, count, resource)
                self.assertEqual(len(result.items), count, resource)
                if resource != "entries":
                    self.assertEqual(result.index_used, "kind", resource)

    def test_catalog_query_from_serialized_mapping_matches_typed_query(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _runtime, catalog = self._populated_catalog(directory)
            mapping = json.loads(storage_catalog_json(catalog))
            typed = query_storage_catalog(
                catalog,
                kind="object",
                prefix="sha256:",
                text="object:",
                accepted=True,
                referenced=True,
                offset=1,
                limit=3,
            )
            serialized = query_storage_catalog(
                mapping,
                kind="object",
                prefix="sha256:",
                text="object:",
                accepted=True,
                referenced=True,
                offset=1,
                limit=3,
            )
            self.assertEqual(serialized.to_dict(), typed.to_dict())
            self.assertEqual(serialized.content_address, typed.content_address)

    def test_catalog_index_rows_are_self_addressed_and_reject_reordering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _runtime, catalog = self._populated_catalog(directory)
            for index_name in STORAGE_CATALOG_INDEXES:
                for row in getattr(catalog, f"{index_name}_index"):
                    self.assertTrue(row.content_address.startswith("storage-catalog-index-row:"))
                    self.assertEqual(row.entry_ids, tuple(sorted(set(row.entry_ids))))
            mapping = catalog.to_dict()
            mapping["kind_index"] = list(reversed(mapping["kind_index"]))
            with self.assertRaises(ValidationError):
                StorageCatalog.from_mapping(mapping)

    def test_object_orphan_state_overrides_object_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, _catalog = self._populated_catalog(directory)
            orphan_address = runtime.store.store.put(
                {"catalog_orphan_payload": "structurally valid"}
            )
            catalog = build_storage_catalog(runtime)
            row = next(item for item in catalog.entries if item.target_address == orphan_address)
            self.assertEqual(row.kind.value, "object")
            self.assertEqual(row.state.value, "orphan")
            self.assertFalse(row.accepted)
            self.assertFalse(catalog.accepted)
            result = query_storage_catalog(catalog, state="orphan", limit=500)
            self.assertIn(row.entry_id, {item["entry_id"] for item in result.items})

    def test_invalid_external_pointer_is_rejected_before_catalog_missing_projection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = self._runtime(directory)
            run_id = runtime._run_id(fixture_manifest())
            run_path = runtime.store.runs / f"{run_id}.json"
            raw = json.loads(run_path.read_text(encoding="utf-8"))
            raw["input_address"] = "external-address:reference"
            run_path.write_text(json.dumps(raw), encoding="utf-8")
            catalog = build_storage_catalog(runtime)
            self.assertEqual(catalog.missing_count, 0)
            run = next(item for item in catalog.entries if item.kind.value == "run")
            self.assertEqual(run.state.value, "rejected")
            self.assertFalse(run.accepted)
            self.assertGreaterEqual(run.warning_count, 1)

    def test_observability_metric_values_reconcile_catalog_counts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _runtime, catalog = self._populated_catalog(directory)
            observation = build_storage_catalog_observability(catalog)
            metrics = {item.name: item.value for item in observation.metrics}
            self.assertEqual(metrics["entry_count"], catalog.entry_count)
            self.assertEqual(metrics["object_count"], catalog.object_count)
            self.assertEqual(metrics["run_count"], catalog.run_count)
            self.assertEqual(metrics["batch_count"], catalog.batch_count)
            self.assertEqual(metrics["missing_count"], catalog.missing_count)
            self.assertEqual(metrics["unexpected_count"], catalog.unexpected_count)
            self.assertEqual(metrics["index_row_count"], catalog.index_row_count)
            self.assertEqual(metrics["accepted_catalog"], 1)
            self.assertEqual(metrics["warning_total"], 0)

    def test_observability_strict_mapping_rejects_unknown_or_tampered_event(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _runtime, catalog = self._populated_catalog(directory)
            observation = build_storage_catalog_observability(catalog)
            unknown = observation.to_dict()
            unknown["unexpected"] = True
            with self.assertRaises(ValidationError):
                StorageCatalogObservability.from_mapping(unknown)
            tampered = observation.to_dict()
            tampered["events"] = list(tampered["events"])
            tampered["events"][0]["value"] += 1
            with self.assertRaises(ValidationError):
                StorageCatalogObservability.from_mapping(tampered)

    def test_observability_event_classes_cover_issues_and_index_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = self._runtime(directory)
            runtime.store.store.put({"orphan_for_observation": True})
            (Path(directory) / "objects" / "extra.data").write_text("extra", encoding="utf-8")
            catalog = build_storage_catalog(runtime)
            observation = build_storage_catalog_observability(catalog)
            event_types = {item.event_type.value for item in observation.events}
            self.assertIn("entry-seen", event_types)
            self.assertIn("object-entry", event_types)
            self.assertIn("orphan-entry", event_types)
            self.assertIn("unexpected-entry", event_types)
            self.assertIn("index-built", event_types)
            self.assertTrue(
                all(item.catalog_address == catalog.content_address for item in observation.events)
            )

    def test_packet_artifact_bytes_and_metadata_are_reconciled(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _runtime, catalog = self._populated_catalog(directory)
            packet = build_storage_catalog_packet(catalog)
            payloads = {item.artifact_id: item.content for item in packet.artifacts}
            self.assertEqual(tuple(payloads), STORAGE_CATALOG_PACKET_PAYLOAD_IDS)
            for artifact in packet.artifacts:
                self.assertEqual(artifact.byte_count, len(artifact.content))
                self.assertEqual(artifact.line_count, artifact.content.count(b"\n"))
                self.assertEqual(artifact.source_address, catalog.content_address)
                self.assertNotIn(b"subject_id", artifact.content)
                self.assertNotIn(b"agent_id", artifact.content)
            manifest = packet.manifest.to_dict()
            self.assertEqual(
                tuple(row["artifact_id"] for row in manifest["artifacts"]),
                STORAGE_CATALOG_PACKET_PAYLOAD_IDS,
            )

    def test_packet_boundary_and_manifest_are_canonical(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            tempfile.TemporaryDirectory() as destination,
        ):
            _runtime, catalog = self._populated_catalog(directory)
            packet = build_storage_catalog_packet(catalog, packet_id="catalog-review-001")
            write_storage_catalog_packet(packet, destination)
            manifest_path = Path(destination) / "manifest.json"
            self.assertEqual(
                manifest_path.read_text(encoding="utf-8"),
                canonical_json(packet.manifest.to_dict()) + "\n",
            )
            boundary = json.loads(
                (Path(destination) / "catalog" / "boundary.json").read_text(encoding="utf-8")
            )
            self.assertEqual(boundary["boundary"], "public_storage_catalog_packet")
            self.assertFalse(boundary["payload_exposure"])
            self.assertFalse(boundary["source_object_bytes"])
            self.assertTrue(verify_storage_catalog_packet(destination).accepted)

    def test_packet_verifier_rejects_manifest_drift_and_missing_files(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            tempfile.TemporaryDirectory() as destination,
        ):
            _runtime, catalog = self._populated_catalog(directory)
            packet = build_storage_catalog_packet(catalog)
            write_storage_catalog_packet(packet, destination)
            manifest_path = Path(destination) / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["payload_artifact_count"] = 9
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            (Path(destination) / "catalog" / "metrics.csv").unlink()
            verification = verify_storage_catalog_packet(destination)
            self.assertFalse(verification.accepted)
            self.assertIn("catalog/metrics.csv", verification.missing_paths)
            self.assertTrue(verification.manifest_drift)

    def test_packet_verifier_rejects_unsafe_manifest_path(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            tempfile.TemporaryDirectory() as destination,
        ):
            _runtime, catalog = self._populated_catalog(directory)
            packet = build_storage_catalog_packet(catalog)
            write_storage_catalog_packet(packet, destination)
            manifest_path = Path(destination) / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"][0]["relative_path"] = "../outside.json"
            manifest_body = {
                key: manifest[key]
                for key in (
                    "version",
                    "schema_version",
                    "packet_id",
                    "catalog_address",
                    "observability_address",
                    "artifact_count",
                    "payload_artifact_count",
                    "artifacts",
                    "accepted",
                )
            }
            from glio_noncode.serialization import content_hash

            manifest["content_address"] = content_hash(
                manifest_body, prefix="storage-catalog-packet-manifest"
            )
            manifest_path.write_text(canonical_json(manifest) + "\n", encoding="utf-8")
            verification = verify_storage_catalog_packet(destination)
            self.assertFalse(verification.accepted)
            self.assertIn("../outside.json", verification.unsafe_paths)

    def test_cli_catalog_query_and_observability_formats(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = self._runtime(directory)
            runtime.store.store.put({"cli_catalog_orphan": True})
            entries_output = Path(directory) / "entries.csv"
            self.assertEqual(
                main(
                    [
                        "storage-catalog",
                        "--data-root",
                        directory,
                        "--format",
                        "entries-csv",
                        "--output",
                        str(entries_output),
                    ]
                ),
                2,
            )
            self.assertTrue(
                entries_output.read_text(encoding="utf-8").startswith("entry_id,kind,state")
            )
            observability_output = Path(directory) / "observation.json"
            self.assertEqual(
                main(
                    [
                        "storage-catalog-observability",
                        "--data-root",
                        directory,
                        "--output",
                        str(observability_output),
                    ]
                ),
                2,
            )
            observation = json.loads(observability_output.read_text(encoding="utf-8"))
            self.assertFalse(observation["accepted"])
            query_output = Path(directory) / "query.json"
            self.assertEqual(
                main(
                    [
                        "storage-catalog",
                        "--data-root",
                        directory,
                        "--state",
                        "orphan",
                        "--output",
                        str(query_output),
                    ]
                ),
                2,
            )
            query = json.loads(query_output.read_text(encoding="utf-8"))
            self.assertEqual(query["query"]["total"], 1)

    def test_http_post_verify_diff_observability_and_packet_verification(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            tempfile.TemporaryDirectory() as packet_directory,
        ):
            runtime = self._runtime(directory)
            catalog = build_storage_catalog(runtime)
            observation = build_storage_catalog_observability(catalog)
            packet = build_storage_catalog_packet(catalog)
            write_storage_catalog_packet(packet, packet_directory)
            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=60)

                def post(path: str, value: object) -> tuple[int, dict[str, object]]:
                    body = json.dumps(value).encode()
                    connection.request(
                        "POST",
                        path,
                        body=body,
                        headers={
                            "Content-Type": "application/json",
                            "Content-Length": str(len(body)),
                        },
                    )
                    response = connection.getresponse()
                    return response.status, json.loads(response.read())

                status, verified = post(
                    "/v1/storage/catalog/verify", {"catalog": catalog.to_dict()}
                )
                self.assertEqual(status, 200)
                self.assertEqual(verified["content_address"], catalog.content_address)
                status, queried = post(
                    "/v1/storage/catalog/observability/query",
                    {"observability": observation.to_dict(), "query": {"event_type": "entry-seen"}},
                )
                self.assertEqual(status, 200)
                self.assertGreater(queried["total"], 0)
                status, diff = post(
                    "/v1/storage/catalog/diff",
                    {"baseline": catalog.to_dict(), "candidate": catalog.to_dict()},
                )
                self.assertEqual(status, 200)
                self.assertEqual(diff["added_entry_ids"], [])
                status, packet_result = post(
                    "/v1/storage/catalog/packet/verify", {"directory": packet_directory}
                )
                self.assertEqual(status, 200)
                self.assertTrue(packet_result["accepted"])
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
