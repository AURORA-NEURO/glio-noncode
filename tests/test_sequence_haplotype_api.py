from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from threading import Thread

from glio_noncode._cli_sequence_batch import build_batch_report
from glio_noncode.api import create_server
from tests.test_cli_sequence import _input
from tests.test_cli_sequence_batch import _batch_input


class SequenceHaplotypeApiTests(unittest.TestCase):
    def test_http_analysis_returns_public_report_and_rejects_query_parameters(self) -> None:
        server = create_server("127.0.0.1", 0)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            connection = HTTPConnection(host, port, timeout=30)
            payload = json.dumps(_input(), separators=(",", ":")).encode("utf-8")
            connection.request(
                "POST",
                "/v1/sequence-haplotype",
                body=payload,
                headers={"Content-Type": "application/json"},
            )
            response = connection.getresponse()
            report = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertEqual(report["analysis_state"], "supported")
            self.assertNotIn("AACCGGTTAACC", json.dumps(report))
            self.assertNotIn("PRIVATE_SAMPLE_1", json.dumps(report))

            connection.request(
                "POST",
                "/v1/sequence-haplotype?unexpected=1",
                body=payload,
                headers={"Content-Type": "application/json"},
            )
            self.assertEqual(connection.getresponse().status, 400)

            connection.request(
                "POST",
                "/v1/sequence-haplotype",
                body=json.dumps({"schema": "wrong"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            invalid_response = connection.getresponse()
            invalid = json.loads(invalid_response.read())
            self.assertEqual(invalid_response.status, 400)
            self.assertEqual(invalid["error"], "invalid_sequence_haplotype_input")
            connection.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_persisted_http_analysis_has_catalog_changes_csv_and_report_export(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                payload = json.dumps(_input(), separators=(",", ":")).encode("utf-8")
                connection.request(
                    "POST",
                    "/v1/sequence-analyses",
                    body=payload,
                    headers={"Content-Type": "application/json"},
                )
                saved_response = connection.getresponse()
                saved = json.loads(saved_response.read())
                self.assertEqual(saved_response.status, 201)
                analysis_id = saved["record"]["analysis_id"]

                connection.request("GET", "/v1/sequence-analyses?limit=5")
                catalog_response = connection.getresponse()
                catalog = json.loads(catalog_response.read())
                self.assertEqual(catalog_response.status, 200)
                self.assertEqual(catalog["total_count"], 1)
                self.assertEqual(catalog["rows"][0]["analysis_id"], analysis_id)

                connection.request("GET", f"/v1/sequence-analyses/{analysis_id}?change=created")
                changes_response = connection.getresponse()
                changes = json.loads(changes_response.read())
                self.assertEqual(changes_response.status, 200)
                self.assertEqual(changes["total_changes"], 1)

                connection.request("GET", f"/v1/sequence-analyses/{analysis_id}/changes.csv")
                csv_response = connection.getresponse()
                csv_body = csv_response.read().decode("utf-8")
                self.assertEqual(csv_response.status, 200)
                self.assertIn("matched_sequence", csv_body)
                self.assertNotIn("PRIVATE_SAMPLE_1", csv_body)

                connection.request("GET", f"/v1/sequence-analyses/{analysis_id}/report.json")
                report_response = connection.getresponse()
                report = json.loads(report_response.read())
                self.assertEqual(report_response.status, 200)
                self.assertEqual(report["content_address"], saved["report"]["content_address"])

                connection.request("GET", f"/v1/sequence-analyses/{analysis_id}?unknown=1")
                self.assertEqual(connection.getresponse().status, 400)
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_http_batch_projection_returns_aggregate_changes_only(self) -> None:
        server = create_server("127.0.0.1", 0)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            connection = HTTPConnection(host, port, timeout=30)
            connection.request(
                "POST",
                "/v1/sequence-haplotype/batch",
                body=json.dumps(_batch_input(), separators=(",", ":")).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            response = connection.getresponse()
            report = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertEqual(report["design"]["analysis_count"], 3)
            serialized = json.dumps(report)
            self.assertNotIn("AACCGGTTAACC", serialized)
            self.assertNotIn("PRIVATE_SAMPLE_1", serialized)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_persisted_batch_http_catalog_and_report_export(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                connection.request(
                    "POST",
                    "/v1/sequence-batches",
                    body=json.dumps(_batch_input(), separators=(",", ":")).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
                saved_response = connection.getresponse()
                saved = json.loads(saved_response.read())
                self.assertEqual(saved_response.status, 201)
                batch_id = saved["record"]["batch_id"]

                connection.request("GET", "/v1/sequence-batches?limit=5")
                catalog_response = connection.getresponse()
                catalog = json.loads(catalog_response.read())
                self.assertEqual(catalog_response.status, 200)
                self.assertEqual(catalog["rows"][0]["batch_id"], batch_id)

                connection.request("GET", f"/v1/sequence-batches/{batch_id}/report.json")
                report_response = connection.getresponse()
                report = json.loads(report_response.read())
                self.assertEqual(report_response.status, 200)
                self.assertEqual(report["content_address"], saved["report"]["content_address"])

                connection.request("GET", f"/v1/sequence-batches/{batch_id}?motif_contains=joint")
                changes_response = connection.getresponse()
                changes = json.loads(changes_response.read())
                self.assertEqual(changes_response.status, 200)
                self.assertEqual(changes["total_changes"], 1)

                connection.request("GET", f"/v1/sequence-batches/{batch_id}/changes.csv")
                csv_response = connection.getresponse()
                csv_body = csv_response.read().decode("utf-8")
                self.assertEqual(csv_response.status, 200)
                self.assertIn("analysis_fraction", csv_body)
                self.assertNotIn("PRIVATE_SAMPLE_1", csv_body)
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_http_batch_comparison_preserves_aggregate_boundary(self) -> None:
        left = build_batch_report(
            {"schema": "glio-noncode.sequence-haplotype-batch-input.v1", "analyses": [_input()]}
        )
        right = build_batch_report(_batch_input())
        server = create_server("127.0.0.1", 0)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            connection = HTTPConnection(host, port, timeout=30)
            connection.request(
                "POST",
                "/v1/sequence-haplotype/batch/compare",
                body=json.dumps({"left": left, "right": right}, separators=(",", ":")).encode(
                    "utf-8"
                ),
                headers={"Content-Type": "application/json"},
            )
            response = connection.getresponse()
            report = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertEqual(report["status"], "completed")
            self.assertNotIn("PRIVATE_SAMPLE_1", json.dumps(report))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_http_batch_comparison_rejects_ambiguous_envelopes(self) -> None:
        server = create_server("127.0.0.1", 0)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            connection = HTTPConnection(host, port, timeout=30)
            connection.request(
                "POST",
                "/v1/sequence-haplotype/batch/compare",
                body=json.dumps({"left": {}, "right": {}, "extra": True}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            response = connection.getresponse()
            payload = json.loads(response.read())
            self.assertEqual(response.status, 400)
            self.assertEqual(payload["error"], "invalid_sequence_batch_comparison_request")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_persisted_batch_comparison_uses_saved_batch_ids_and_exports_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                headers = {"Content-Type": "application/json"}
                batch_reports = [
                    {
                        "schema": "glio-noncode.sequence-haplotype-batch-input.v1",
                        "analyses": [_input()],
                    },
                    _batch_input(),
                ]
                batch_ids = []
                for batch_input in batch_reports:
                    connection.request(
                        "POST",
                        "/v1/sequence-batches",
                        body=json.dumps(batch_input, separators=(",", ":")).encode(),
                        headers=headers,
                    )
                    response = connection.getresponse()
                    payload = json.loads(response.read())
                    self.assertEqual(response.status, 201)
                    batch_ids.append(payload["record"]["batch_id"])
                connection.request(
                    "POST",
                    "/v1/sequence-comparisons",
                    body=json.dumps(
                        {"left_batch_id": batch_ids[0], "right_batch_id": batch_ids[1]},
                        separators=(",", ":"),
                    ).encode(),
                    headers=headers,
                )
                comparison_response = connection.getresponse()
                comparison = json.loads(comparison_response.read())
                self.assertEqual(comparison_response.status, 201)
                comparison_id = comparison["record"]["comparison_id"]

                connection.request("GET", "/v1/sequence-comparisons?limit=5")
                catalog_response = connection.getresponse()
                catalog = json.loads(catalog_response.read())
                self.assertEqual(catalog_response.status, 200)
                self.assertEqual(catalog["rows"][0]["comparison_id"], comparison_id)
                connection.request(
                    "GET", f"/v1/sequence-comparisons/{comparison_id}?direction=decreased"
                )
                changes_response = connection.getresponse()
                changes = json.loads(changes_response.read())
                self.assertEqual(changes_response.status, 200)
                self.assertEqual(changes["total_changes"], 1)
                connection.request("GET", f"/v1/sequence-comparisons/{comparison_id}/changes.csv")
                csv_response = connection.getresponse()
                csv_body = csv_response.read().decode()
                self.assertEqual(csv_response.status, 200)
                self.assertIn("delta_fraction", csv_body)
                self.assertNotIn("PRIVATE_SAMPLE_1", csv_body)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)
