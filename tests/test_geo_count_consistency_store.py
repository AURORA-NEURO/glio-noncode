from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode._cli_geo_count_consistency import main as count_consistency_main
from glio_noncode.api import create_server
from glio_noncode.geo_analysis_store import GeoAnalysisStore
from glio_noncode.geo_count_consistency_store import GeoCountConsistencyStore

from .test_geo_count_consistency import _report


class GeoCountConsistencyStoreTests(unittest.TestCase):
    def _saved_workspace(self, root: Path) -> tuple[Path, str, str]:
        workspace = root / "workspace"
        source = GeoAnalysisStore(workspace)
        first_id = source.save(_report(root / "first", "GSE141945"))["analysis_id"]
        second_id = source.save(
            _report(root / "second", "GSE141946", direction_fixture=True)
        )["analysis_id"]
        return workspace, first_id, second_id

    def test_store_is_immutable_cataloged_and_privacy_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace, first_id, second_id = self._saved_workspace(Path(directory))
            store = GeoCountConsistencyStore(workspace)
            record = store.save_from_analysis_ids(
                [first_id, second_id], feature_ids=["SIGNAL", "SKEWED_DIRECTION"]
            )
            same = store.save_from_analysis_ids(
                [first_id, second_id], feature_ids=["SIGNAL", "SKEWED_DIRECTION"]
            )
            page = store.page_features(
                record["comparison_id"], feature_contains="signal", limit=1
            )
            exported = store.features_csv(record["comparison_id"], feature_contains="signal")
            studies_csv = store.studies_csv(record["comparison_id"])

            self.assertEqual(record, same)
            self.assertEqual(store.list_reports()["total_count"], 1)
            self.assertEqual(page["schema"], "glio-noncode.geo-count-consistency-page.v1")
            self.assertEqual(page["features"][0]["feature_id"], "SIGNAL")
            self.assertEqual(page["filtered_feature_summary"]["feature_count"], 1)
            self.assertEqual(
                sum(page["filtered_feature_summary"]["direction_consistency_counts"].values()),
                page["total_features"],
            )
            self.assertIn("feature_id,direction_consistency", exported)
            self.assertIn("ranked_feature_count", studies_csv.splitlines()[0])
            self.assertIn("tracked_feature_ids", studies_csv.splitlines()[0])
            self.assertNotIn("PRIVATE_SUBJECT_", studies_csv)
            expected_ranked = sum(
                GeoAnalysisStore(workspace).get_report(analysis_id)["report"]["summary"][
                    "ranked_feature_count"
                ]
                for analysis_id in (first_id, second_id)
            )
            self.assertEqual(record["summary"]["ranked_feature_count_total"], expected_ranked)
            self.assertEqual(record["summary"]["additional_tracked_feature_count_total"], 0)
            public = json.dumps(store.get_report(record["comparison_id"]))
            self.assertNotIn("PRIVATE_SUBJECT_", public)
            self.assertNotIn("analysis_id", public)

    def test_focused_cli_can_persist_a_completed_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = _report(root / "first", "GSE141945")
            second = _report(root / "second", "GSE141946", direction_fixture=True)
            first_path = root / "first.json"
            second_path = root / "second.json"
            first_path.write_text(json.dumps(first), encoding="utf-8")
            second_path.write_text(json.dumps(second), encoding="utf-8")
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = count_consistency_main(
                    [
                        str(first_path),
                        str(second_path),
                        "--feature-id",
                        "SIGNAL",
                        "--data-root",
                        str(root / "workspace"),
                        "--save-to-workspace",
                    ]
                )
            self.assertEqual(result, 0)
            self.assertEqual(json.loads(stdout.getvalue())["status"], "completed")
            self.assertIn("Saved GEO count consistency", stderr.getvalue())
            self.assertEqual(
                GeoCountConsistencyStore(root / "workspace").list_reports()["total_count"],
                1,
            )

    def test_http_catalog_page_csv_and_post_are_aggregate_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace, first_id, second_id = self._saved_workspace(root)
            server = create_server("127.0.0.1", 0, str(workspace))
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            connection = None
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                body = json.dumps(
                    {"analysis_ids": [first_id, second_id], "feature_ids": ["SIGNAL"]}
                )
                connection.request(
                    "POST",
                    "/v1/geo-count-consistency",
                    body=body,
                    headers={"Content-Type": "application/json"},
                )
                response = connection.getresponse()
                created = json.loads(response.read())
                self.assertEqual(response.status, 201)
                comparison_id = created["record"]["comparison_id"]

                connection.request("GET", "/v1/geo-count-consistency")
                response = connection.getresponse()
                catalog = json.loads(response.read())
                self.assertEqual(response.status, 200)
                self.assertEqual(catalog["total_count"], 1)

                connection.request(
                    "GET", f"/v1/geo-count-consistency/{comparison_id}?feature_contains=signal"
                )
                response = connection.getresponse()
                page = json.loads(response.read())
                self.assertEqual(response.status, 200)
                self.assertEqual(page["features"][0]["feature_id"], "SIGNAL")
                self.assertNotIn("PRIVATE_SUBJECT_", json.dumps(page))
                self.assertNotIn("analysis_id", json.dumps(page))

                connection.request(
                    "GET", f"/v1/geo-count-consistency/{comparison_id}/features.csv"
                )
                response = connection.getresponse()
                csv_payload = response.read().decode("utf-8")
                self.assertEqual(response.status, 200)
                self.assertIn("feature_id,direction_consistency", csv_payload)

                connection.request(
                    "GET", f"/v1/geo-count-consistency/{comparison_id}/studies.csv"
                )
                response = connection.getresponse()
                studies_csv_payload = response.read().decode("utf-8")
                self.assertEqual(response.status, 200)
                self.assertIn("ranked_feature_count", studies_csv_payload.splitlines()[0])
                self.assertIn("tracked_feature_ids", studies_csv_payload.splitlines()[0])
            finally:
                if connection is not None:
                    connection.close()
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
