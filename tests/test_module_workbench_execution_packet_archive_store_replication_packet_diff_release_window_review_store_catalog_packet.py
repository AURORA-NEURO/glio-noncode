"""Deep regression coverage for portable catalog release packets."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import json
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from http.client import HTTPConnection
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog,
    write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet import (
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacket,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketArtifact,
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet,
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_from_directory,
    load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_capabilities,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_csv,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_json,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_query_capabilities,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_query_csv,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_query_json,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_query_schema,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_schema,
    query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet,
    render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_markdown,
    render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_query_markdown,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_query,
    write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime import (
    run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime,
)
from glio_noncode.serialization import canonical_bytes, content_hash


class CatalogPacketTests(unittest.TestCase):
    """Exercise exact transport around all five catalog release projections."""

    @staticmethod
    def _store(
        store_id: str,
        *,
        state: str = "ready",
        release_ready: bool = True,
        accepted: bool = True,
        window_address: str = "window:one",
        ledger_address: str | None = None,
    ) -> SimpleNamespace:
        ledger = SimpleNamespace(
            window_address=window_address,
            content_address=ledger_address or f"ledger:{store_id}",
            head_address=f"entry:{store_id}",
            entry_count=1,
        )
        return SimpleNamespace(
            store_id=store_id,
            content_address=f"store:{store_id}",
            ledger_address=ledger.content_address,
            head_address=ledger.head_address,
            entry_count=1,
            state=state,
            release_ready=release_ready,
            accepted=accepted,
            append_only=True,
            operation_count=1,
            ledger=ledger,
        )

    def _catalog(self, *stores: SimpleNamespace, catalog_id: str = "catalog"):
        return build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
            stores,
            catalog_id=catalog_id,
        )

    def _components(self, catalog=None, **kwargs):
        catalog = catalog or self._catalog(self._store("alpha"), self._store("beta"))
        runtime = run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime(
            catalog
        )
        federation = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation(
            catalog,
            federation_id=kwargs.get("federation_id", "federation"),
            selected_window_address=kwargs.get("selected_window_address"),
            store_ids=kwargs.get("store_ids"),
            require_same_window=kwargs.get("require_same_window", True),
            require_unique_ledger=kwargs.get("require_unique_ledger", True),
            minimum_members=kwargs.get("minimum_members", 1),
            minimum_ready=kwargs.get("minimum_ready", 1),
        )
        assurance = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance(
            catalog,
            stores=getattr(catalog, "stores", ()),
            assurance_id=kwargs.get("assurance_id", "assurance"),
        )
        gate = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate(
            catalog,
            runtime,
            federation,
            assurance,
            gate_id=kwargs.get("gate_id", "gate"),
        )
        return catalog, runtime, federation, assurance, gate

    def _packet(self, catalog=None, **kwargs):
        catalog, runtime, federation, assurance, gate = self._components(catalog, **kwargs)
        return build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
            catalog,
            runtime,
            federation,
            assurance,
            gate,
            packet_id=kwargs.get("packet_id", "packet"),
        )

    @staticmethod
    def _payloads(packet):
        return {
            "catalog": packet.catalog.to_dict(),
            "runtime": packet.runtime.to_dict(),
            "federation": packet.federation.to_dict(),
            "assurance": packet.assurance.to_dict(),
            "gate": packet.gate.to_dict(),
        }

    def _write_catalog_directory(self, root: str, catalog=None) -> Path:
        destination = Path(root) / "catalog"
        write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
            catalog or self._components()[0], destination
        )
        return destination

    def test_packet_contains_five_ordered_component_artifacts(self) -> None:
        packet = self._packet()
        self.assertEqual(packet.artifact_count, 5)
        self.assertEqual(
            [item.kind for item in packet.artifacts],
            ["catalog", "runtime", "federation", "assurance", "gate"],
        )
        self.assertEqual(
            [item.ordinal for item in packet.artifacts],
            list(range(packet.artifact_count)),
        )
        self.assertEqual(
            [item.file_name for item in packet.artifacts],
            ["catalog.json", "runtime.json", "federation.json", "assurance.json", "gate.json"],
        )
        self.assertEqual(packet.catalog_id, packet.catalog.catalog_id)
        self.assertEqual(packet.catalog_address, packet.catalog.content_address)
        self.assertEqual(packet.runtime_address, packet.runtime.content_address)
        self.assertEqual(packet.federation_address, packet.federation.content_address)
        self.assertEqual(packet.assurance_address, packet.assurance.content_address)
        self.assertEqual(packet.gate_address, packet.gate.content_address)

    def test_packet_artifact_byte_measurements_are_exact(self) -> None:
        packet = self._packet()
        payloads = self._payloads(packet)
        for artifact in packet.artifacts:
            raw = canonical_bytes(payloads[artifact.kind])
            self.assertEqual(artifact.byte_count, len(raw))
            self.assertEqual(
                artifact.content_address,
                payloads[artifact.kind]["content_address"],
            )
            self.assertGreater(artifact.byte_count, 0)

    def test_packet_verification_recomputes_bytes_and_links(self) -> None:
        packet = self._packet()
        receipt = verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
            packet,
            payloads=self._payloads(packet),
        )
        self.assertTrue(receipt.accepted)
        self.assertEqual(receipt.failed_count, 0)
        self.assertEqual(receipt.check_count, len(receipt.checks))
        self.assertEqual(receipt.passed_count, receipt.check_count)
        self.assertEqual(receipt.packet_address, packet.content_address)
        self.assertTrue(
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
                packet
            ).accepted
        )

    def test_packet_verification_receipt_is_addressed_and_conserved(self) -> None:
        packet = self._packet()
        receipt = verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
            packet
        )
        self.assertTrue(receipt.content_address.startswith("module-workbench"))
        self.assertEqual(
            receipt.passed_count + receipt.failed_count,
            receipt.check_count,
        )
        self.assertEqual(
            [item.ordinal for item in receipt.checks],
            list(range(receipt.check_count)),
        )
        for check in receipt.checks:
            self.assertEqual(check.state, "passed")
            self.assertTrue(check.passed)

    def test_packet_json_csv_and_markdown_are_deterministic(self) -> None:
        packet = self._packet()
        first = module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_json(
            packet
        )
        second = module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_json(
            packet
        )
        self.assertEqual(first, second)
        document = json.loads(first)
        self.assertEqual(document["content_address"], packet.content_address)
        self.assertEqual(len(document["artifacts"]), 5)
        rows = list(
            csv.DictReader(
                module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_csv(
                    packet
                ).splitlines()
            )
        )
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[0]["kind"], "catalog")
        markdown = render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_markdown(
            packet
        )
        self.assertIn("Durable Review-Store Catalog Packet", markdown)
        self.assertIn("gate.json", markdown)
        self.assertIn(packet.content_address, markdown)

    def test_packet_query_supports_kind_text_paging_and_receipts(self) -> None:
        packet = self._packet()
        result = query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
            packet, kind="gate", text="gate", offset=0, limit=1
        )
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["file_name"], "gate.json")
        self.assertEqual(result["offset"], 0)
        self.assertEqual(result["limit"], 1)
        self.assertTrue(
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_query(
                result
            )
        )
        self.assertIn(
            "gate.json",
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_query_json(
                result
            ),
        )
        csv_value = module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_query_csv(
            result
        )
        self.assertEqual(len(list(csv.DictReader(csv_value.splitlines()))), 1)
        markdown = render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_query_markdown(
            result
        )
        self.assertIn("Catalog Packet Query", markdown)

    def test_packet_query_receipt_rejects_mutation(self) -> None:
        packet = self._packet()
        result = query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
            packet
        )
        result["total"] = 99
        with self.assertRaises(ValidationError):
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_query(
                result
            )

    def test_packet_query_rejects_invalid_kind_and_bounds(self) -> None:
        packet = self._packet()
        with self.assertRaises(ValidationError):
            query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
                packet, kind="unknown"
            )
        with self.assertRaises(ValidationError):
            query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
                packet, offset=-1
            )
        with self.assertRaises(ValidationError):
            query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
                packet, limit=0
            )
        with self.assertRaises(ValidationError):
            query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
                packet, limit=513
            )
        with self.assertRaises(ValidationError):
            query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
                packet, offset=True
            )

    def test_packet_schema_and_capabilities_are_identity_free(self) -> None:
        values = (
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_schema(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_capabilities(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_query_schema(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_query_capabilities(),
        )
        for value in values:
            encoded = json.dumps(value).casefold()
            self.assertNotIn('"agent"', encoded)
            self.assertNotIn('"language"', encoded)
            self.assertNotIn('"model"', encoded)
            self.assertNotIn('"user"', encoded)
        schema = values[0]
        capabilities = values[1]
        self.assertEqual(schema["exact_artifacts"], True)
        self.assertEqual(schema["files"].__len__(), 6)
        self.assertEqual(capabilities["component_count"], 5)
        self.assertTrue(capabilities["atomic_write"])
        self.assertTrue(capabilities["rehydrates_components"])
        self.assertTrue(values[3]["addressed_receipts"])

    def test_packet_from_directory_builds_from_persisted_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            catalog_directory = self._write_catalog_directory(root)
            packet = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_from_directory(
                catalog_directory,
                packet_id="directory-packet",
            )
            self.assertEqual(packet.packet_id, "directory-packet")
            self.assertTrue(packet.accepted)
            self.assertTrue(packet.release_ready)
            self.assertEqual(packet.catalog_id, "catalog")
            self.assertNotIn(str(catalog_directory), json.dumps(packet.to_dict()))

    def test_packet_write_and_load_is_an_exact_six_file_round_trip(self) -> None:
        packet = self._packet()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "packet"
            written = write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
                packet, destination
            )
            self.assertEqual(written, destination)
            self.assertEqual(
                sorted(item.name for item in destination.iterdir()),
                [
                    "assurance.json",
                    "catalog.json",
                    "federation.json",
                    "gate.json",
                    "manifest.json",
                    "runtime.json",
                ],
            )
            loaded = load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
                destination
            )
            self.assertEqual(loaded.content_address, packet.content_address)
            self.assertEqual(loaded.to_dict(), packet.to_dict())
            self.assertEqual(loaded.catalog.content_address, packet.catalog.content_address)
            self.assertEqual(loaded.runtime.content_address, packet.runtime.content_address)
            self.assertEqual(loaded.federation.content_address, packet.federation.content_address)
            self.assertEqual(loaded.assurance.content_address, packet.assurance.content_address)
            self.assertEqual(loaded.gate.content_address, packet.gate.content_address)
            self.assertIsInstance(
                loaded,
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacket,
            )

    def test_packet_write_bytes_are_stable_across_destinations(self) -> None:
        packet = self._packet()
        with tempfile.TemporaryDirectory() as root:
            left = Path(root) / "left"
            right = Path(root) / "right"
            write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
                packet, left
            )
            write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
                packet, right
            )
            for name in (
                "manifest.json",
                "catalog.json",
                "runtime.json",
                "federation.json",
                "assurance.json",
                "gate.json",
            ):
                self.assertEqual((left / name).read_bytes(), (right / name).read_bytes())

    def test_packet_write_rejects_existing_destination_without_overwrite(self) -> None:
        packet = self._packet()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "packet"
            write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
                packet, destination
            )
            with self.assertRaises(ValidationError):
                write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
                    packet, destination
                )
            replacement = self._packet(packet_id="replacement")
            write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
                replacement, destination, overwrite=True
            )
            loaded = load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
                destination
            )
            self.assertEqual(loaded.packet_id, "replacement")

    def test_packet_write_requires_hydrated_components(self) -> None:
        packet = self._packet()
        del packet.catalog
        del packet.runtime
        del packet.federation
        del packet.assurance
        del packet.gate
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValidationError):
                write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
                    packet, Path(root) / "packet"
                )

    def test_packet_loader_rejects_changed_artifact_bytes(self) -> None:
        packet = self._packet()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "packet"
            write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
                packet, destination
            )
            path = destination / "gate.json"
            path.write_bytes(path.read_bytes() + b" ")
            with self.assertRaises(ValidationError):
                load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
                    destination
                )

    def test_packet_loader_rejects_noncanonical_component_json(self) -> None:
        packet = self._packet()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "packet"
            write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
                packet, destination
            )
            path = destination / "catalog.json"
            document = json.loads(path.read_text())
            path.write_text(json.dumps(document, indent=2), encoding="utf-8")
            with self.assertRaises(ValidationError):
                load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
                    destination
                )

    def test_packet_loader_rejects_missing_and_extra_files(self) -> None:
        packet = self._packet()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "packet"
            write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
                packet, destination
            )
            (destination / "gate.json").unlink()
            with self.assertRaises(ValidationError):
                load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
                    destination
                )
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "packet"
            write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
                packet, destination
            )
            (destination / "extra.json").write_bytes(b"{}")
            with self.assertRaises(ValidationError):
                load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
                    destination
                )

    def test_packet_loader_rejects_manifest_address_mutation(self) -> None:
        packet = self._packet()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "packet"
            write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
                packet, destination
            )
            manifest = json.loads((destination / "manifest.json").read_text())
            manifest["accepted"] = False
            (destination / "manifest.json").write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
                    destination
                )

    def test_packet_loader_rejects_manifest_structure_and_kind_mismatch(self) -> None:
        packet = self._packet()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "packet"
            write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
                packet, destination
            )
            manifest = json.loads((destination / "manifest.json").read_text())
            manifest["artifact_files"] = []
            (destination / "manifest.json").write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
                    destination
                )
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "packet"
            write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
                packet, destination
            )
            manifest = json.loads((destination / "manifest.json").read_text())
            manifest["artifacts"][0]["file_name"] = "gate.json"
            manifest["artifact_files"][0]["file_name"] = "gate.json"
            manifest_body = {
                key: item for key, item in manifest.items() if key != "manifest_address"
            }
            manifest["manifest_address"] = content_hash(
                manifest_body,
                prefix="module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-manifest",
            )
            (destination / "manifest.json").write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
                    destination
                )

    def test_packet_verification_detects_payload_address_divergence(self) -> None:
        packet = self._packet()
        payloads = self._payloads(packet)
        payloads["gate"] = dict(payloads["gate"])
        payloads["gate"]["content_address"] = "gate:wrong"
        receipt = verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
            packet, payloads=payloads
        )
        self.assertFalse(receipt.accepted)
        self.assertGreaterEqual(receipt.failed_count, 1)
        self.assertTrue(any(item.kind == "content-gate" for item in receipt.checks))

    def test_packet_verification_detects_byte_and_summary_tampering(self) -> None:
        packet = self._packet()
        payloads = self._payloads(packet)
        payloads["runtime"] = dict(payloads["runtime"])
        payloads["runtime"]["state"] = "blocked"
        receipt = verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
            packet, payloads=payloads
        )
        self.assertFalse(receipt.accepted)
        self.assertTrue(any(item.kind == "bytes-runtime" for item in receipt.checks))
        tampered = packet.to_dict()
        tampered["packet_id"] = "tampered"
        self.assertNotEqual(
            content_hash(
                tampered | {"content_address": None},
                prefix="module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet",
            ),
            packet.content_address,
        )

    def test_held_gate_produces_accepted_non_ready_packet(self) -> None:
        catalog = self._catalog(
            self._store("held", state="held", release_ready=False),
            catalog_id="held-catalog",
        )
        packet = self._packet(catalog)
        self.assertEqual(packet.state, "held")
        self.assertTrue(packet.accepted)
        self.assertFalse(packet.release_ready)
        self.assertTrue(
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
                packet
            ).accepted
        )

    def test_blocked_gate_produces_transportable_rejected_packet(self) -> None:
        catalog = self._catalog(
            self._store("blocked", state="blocked", release_ready=False, accepted=False),
            catalog_id="blocked-catalog",
        )
        packet = self._packet(catalog)
        self.assertEqual(packet.state, "blocked")
        self.assertFalse(packet.accepted)
        self.assertFalse(packet.release_ready)
        self.assertTrue(
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
                packet
            ).accepted
        )
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "blocked-packet"
            write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
                packet, destination
            )
            loaded = load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
                destination
            )
            self.assertFalse(loaded.accepted)
            self.assertEqual(loaded.state, "blocked")

    def test_packet_constructor_rejects_missing_artifact_kind(self) -> None:
        packet = self._packet()
        artifacts = list(packet.artifacts)
        artifacts[-1] = (
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketArtifact(
                ordinal=4,
                kind="assurance",
                file_name="gate.json",
                byte_count=1,
                byte_address="bytes:one",
                content_address="gate:one",
            )
        )
        with self.assertRaises(ValidationError):
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacket(
                packet_id=packet.packet_id,
                version=packet.version,
                boundary=packet.boundary,
                catalog_id=packet.catalog_id,
                catalog_address=packet.catalog_address,
                runtime_address=packet.runtime_address,
                federation_address=packet.federation_address,
                assurance_address=packet.assurance_address,
                gate_address=packet.gate_address,
                artifact_count=5,
                state=packet.state,
                release_ready=packet.release_ready,
                accepted=packet.accepted,
                artifacts=tuple(artifacts),
                content_address=packet.content_address,
            )

    def test_packet_public_projection_omits_hydrated_component_attributes(self) -> None:
        packet = self._packet()
        document = packet.to_dict()
        self.assertNotIn("catalog", document)
        self.assertNotIn("runtime", document)
        self.assertNotIn("federation", document)
        self.assertNotIn("assurance", document)
        self.assertNotIn("gate", document)
        self.assertEqual(document["artifact_count"], 5)

    def test_cli_packet_and_query_commands_build_real_catalog_output(self) -> None:
        catalog = self._components()[0]
        with tempfile.TemporaryDirectory() as root:
            catalog_directory = self._write_catalog_directory(root, catalog)
            summary_path = Path(root) / "packet-summary.json"
            query_path = Path(root) / "packet-query.json"
            packet_result = main(
                [
                    "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet",
                    "--catalog-directory",
                    str(catalog_directory),
                    "--format",
                    "summary",
                    "--output",
                    str(summary_path),
                ]
            )
            query_result = main(
                [
                    "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-query",
                    "--catalog-directory",
                    str(catalog_directory),
                    "--kind",
                    "gate",
                    "--output",
                    str(query_path),
                ]
            )
            self.assertEqual(packet_result, 0)
            self.assertEqual(query_result, 0)
            self.assertEqual(json.loads(summary_path.read_text())["state"], "ready")
            self.assertEqual(json.loads(summary_path.read_text())["artifact_count"], 5)
            self.assertEqual(json.loads(query_path.read_text())["total"], 1)

    def test_cli_packet_schema_commands_are_discoverable(self) -> None:
        commands = (
            "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-schema",
            "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-capabilities",
            "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-query-schema",
            "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-query-capabilities",
        )
        for command in commands:
            output = StringIO()
            with redirect_stdout(output):
                result = main([command])
            self.assertEqual(result, 0)
            self.assertTrue(json.loads(output.getvalue()))

    def test_http_packet_routes_build_summaries_queries_and_schemas(self) -> None:
        catalog = self._components()[0]
        with tempfile.TemporaryDirectory() as root:
            destination = self._write_catalog_directory(root, catalog)
            server = create_server("127.0.0.1", 0, str(Path(root) / "data"))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet"
            try:
                cases = (
                    (base, {"catalog_directory": str(destination), "format": "summary"}, "ready"),
                    (
                        base + "/query",
                        {"catalog_directory": str(destination), "kind": "gate"},
                        None,
                    ),
                    (base + "/schema", {}, None),
                    (base + "/capabilities", {}, None),
                    (base + "/query/schema", {}, None),
                    (base + "/query/capabilities", {}, None),
                )
                for path, params, expected_state in cases:
                    connection = HTTPConnection("127.0.0.1", server.server_address[1], timeout=15)
                    connection.request("GET", path + ("?" + urlencode(params) if params else ""))
                    response = connection.getresponse()
                    payload = json.loads(response.read().decode("utf-8"))
                    self.assertEqual(response.status, 200)
                    if expected_state is not None:
                        self.assertEqual(payload["state"], expected_state)
                    elif path.endswith("/query"):
                        self.assertEqual(payload["total"], 1)
                    else:
                        self.assertTrue(payload)
                    connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_http_packet_csv_and_markdown_content_negotiation(self) -> None:
        catalog = self._components()[0]
        with tempfile.TemporaryDirectory() as root:
            destination = self._write_catalog_directory(root, catalog)
            server = create_server("127.0.0.1", 0, str(Path(root) / "data"))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet"
            try:
                for suffix, content_type, marker in (
                    ("?format=csv", "text/csv", "kind,file_name"),
                    ("?format=markdown", "text/markdown", "Durable Review-Store Catalog Packet"),
                ):
                    connection = HTTPConnection("127.0.0.1", server.server_address[1], timeout=15)
                    connection.request(
                        "GET", base + suffix + "&catalog_directory=" + str(destination)
                    )
                    response = connection.getresponse()
                    body = response.read().decode("utf-8")
                    self.assertEqual(response.status, 200)
                    self.assertIn(content_type, response.getheader("Content-Type", ""))
                    self.assertIn(marker, body)
                    connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_real_downloaded_catalog_packet_is_release_ready(self) -> None:
        catalog_directory = Path(
            r"C:\Users\murar\AppData\Local\Temp\glio-noncode-review-store-catalog-real-4c5ab6bf5c9e4c73a6d03f25f8f09c2b"
        )
        if not catalog_directory.is_dir():
            self.skipTest("real downloaded catalog fixture is not present")
        packet = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_from_directory(
            catalog_directory
        )
        self.assertEqual(packet.state, "ready")
        self.assertTrue(packet.accepted)
        self.assertTrue(packet.release_ready)
        self.assertEqual(packet.artifact_count, 5)
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "real-packet"
            write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
                packet, destination
            )
            loaded = load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
                destination
            )
            self.assertEqual(loaded.content_address, packet.content_address)
            self.assertTrue(
                verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
                    loaded
                ).accepted
            )


if __name__ == "__main__":
    unittest.main()
