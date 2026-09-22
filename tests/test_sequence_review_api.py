from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from threading import Thread

from glio_noncode.api import create_server
from tests.test_cli_sequence import _input
from tests.test_cli_sequence_batch import _batch_input


class SequenceReviewApiTests(unittest.TestCase):
    def test_summary_motifs_verification_and_csv_are_bounded_http_projections(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                headers = {"Content-Type": "application/json"}
                connection.request(
                    "POST", "/v1/sequence-analyses", json.dumps(_input()).encode(), headers
                )
                saved_analysis = connection.getresponse()
                self.assertEqual(saved_analysis.status, 201)
                saved_analysis.read()
                connection.request(
                    "POST", "/v1/sequence-batches", json.dumps(_batch_input()).encode(), headers
                )
                saved_batch = connection.getresponse()
                self.assertEqual(saved_batch.status, 201)
                saved_batch.read()

                connection.request("GET", "/v1/sequence-review/summary")
                summary_response = connection.getresponse()
                summary = json.loads(summary_response.read())
                self.assertEqual(summary_response.status, 200)
                self.assertEqual(summary["catalogs"]["sequence_analyses"]["record_count"], 1)
                self.assertEqual(summary["catalogs"]["sequence_batches"]["record_count"], 1)
                self.assertNotIn("AACCGGTTAACC", json.dumps(summary))

                connection.request("GET", "/v1/sequence-review/motifs?motif_contains=joint")
                motifs_response = connection.getresponse()
                motifs = json.loads(motifs_response.read())
                self.assertEqual(motifs_response.status, 200)
                self.assertEqual(motifs["total_count"], 1)
                self.assertEqual(motifs["rows"][0]["motif_id"], "joint")
                self.assertNotIn("PRIVATE_SAMPLE_1", json.dumps(motifs))

                connection.request("GET", "/v1/sequence-review/verify")
                verification_response = connection.getresponse()
                verification = json.loads(verification_response.read())
                self.assertEqual(verification_response.status, 200)
                self.assertEqual(verification["verified_count"], 2)
                self.assertEqual(verification["failed_count"], 0)

                connection.request("GET", "/v1/sequence-review/motifs.csv?motif_contains=joint")
                csv_response = connection.getresponse()
                csv_body = csv_response.read().decode()
                self.assertEqual(csv_response.status, 200)
                self.assertIn("occurrence_count", csv_body.splitlines()[0])
                self.assertIn(",joint,jointly-created motif,", csv_body)
                self.assertEqual(csv_response.getheader("Content-Type"), "text/csv; charset=utf-8")

                connection.request("GET", "/v1/sequence-review/summary?unexpected=1")
                self.assertEqual(connection.getresponse().status, 400)
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
