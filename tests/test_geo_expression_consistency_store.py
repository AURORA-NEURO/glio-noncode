from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.errors import ValidationError
from glio_noncode.geo_expression_analysis_store import GeoExpressionAnalysisStore
from glio_noncode.geo_expression_consistency_store import GeoExpressionConsistencyStore

from .test_geo_consistency import _contrast_report


class GeoExpressionConsistencyStoreTests(unittest.TestCase):
    def _saved_reports(self, root: Path) -> tuple[GeoExpressionAnalysisStore, list[str]]:
        expression_store = GeoExpressionAnalysisStore(root / "workspace")
        first = expression_store.save(_contrast_report(root, "GSE123456"))
        second = expression_store.save(
            _contrast_report(root, "GSE123457", reverse_discordant=True, sample_base=101)
        )
        return expression_store, [first["analysis_id"], second["analysis_id"]]

    def test_saved_consistency_is_immutable_paged_and_aggregate_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _expression_store, analysis_ids = self._saved_reports(root)
            store = GeoExpressionConsistencyStore(root / "workspace")
            record = store.save_from_expression_analyses(
                analysis_ids,
                feature_ids=("probe-a-concordant", "probe-b-discordant", "probe-not-reported"),
            )
            self.assertEqual(
                store.save_from_expression_analyses(
                    analysis_ids,
                    feature_ids=("probe-a-concordant", "probe-b-discordant", "probe-not-reported"),
                ),
                record,
            )
            catalog = store.list_reports()
            self.assertEqual(catalog["total_count"], 1)
            self.assertNotIn("GSM", json.dumps(catalog))
            page = store.page_features(record["comparison_id"], limit=2)
            self.assertEqual(page["schema"], "glio-noncode.geo-expression-consistency-page.v1")
            self.assertEqual(page["total_features"], 3)
            self.assertEqual(len(page["features"]), 2)
            self.assertNotIn('"sample_ids":', json.dumps(page))
            filtered = store.page_features(
                record["comparison_id"], direction_consistency="discordant_among_reported"
            )
            self.assertEqual(filtered["total_features"], 1)
            csv_body = store.features_csv(record["comparison_id"], feature_contains="probe")
            self.assertIn("feature_id", csv_body.splitlines()[0])
            self.assertIn("probe-b-discordant", csv_body)
            self.assertNotIn("GSM", csv_body)

    def test_filters_and_tampered_addresses_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _expression_store, analysis_ids = self._saved_reports(root)
            store = GeoExpressionConsistencyStore(root / "workspace")
            record = store.save_from_expression_analyses(
                analysis_ids, feature_ids=("probe-a-concordant",)
            )
            with self.assertRaises(ValidationError):
                store.page_features(
                    record["comparison_id"],
                    direction_consistency="not-a-direction-state",
                )
            report = store.get_report(record["comparison_id"])["report"]
            report["summary"] = dict(report["summary"], feature_count=99)
            with self.assertRaises(ValidationError):
                store.save(report)

    def test_http_catalog_page_and_csv_are_available(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _expression_store, analysis_ids = self._saved_reports(root)
            store = GeoExpressionConsistencyStore(root / "workspace")
            record = store.save_from_expression_analyses(
                analysis_ids, feature_ids=("probe-a-concordant", "probe-b-discordant")
            )
            server = create_server("127.0.0.1", 0, str(root / "workspace"))
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                connection.request("GET", "/v1/geo-expression-consistency?limit=5")
                response = connection.getresponse()
                catalog = json.loads(response.read())
                self.assertEqual(response.status, 200)
                self.assertEqual(catalog["rows"][0]["comparison_id"], record["comparison_id"])

                connection.request(
                    "POST",
                    "/v1/geo-expression-consistency",
                    body=json.dumps(
                        {
                            "analysis_ids": analysis_ids,
                            "feature_ids": ["probe-a-concordant", "probe-b-discordant"],
                        }
                    ),
                    headers={"Content-Type": "application/json"},
                )
                response = connection.getresponse()
                created = json.loads(response.read())
                self.assertEqual(response.status, 201)
                self.assertEqual(created["record"]["comparison_id"], record["comparison_id"])

                connection.request(
                    "GET",
                    f"/v1/geo-expression-consistency/{record['comparison_id']}?limit=1",
                )
                response = connection.getresponse()
                page = json.loads(response.read())
                self.assertEqual(response.status, 200)
                self.assertEqual(len(page["features"]), 1)
                self.assertNotIn("GSM", json.dumps(page))

                connection.request(
                    "GET",
                    f"/v1/geo-expression-consistency/{record['comparison_id']}/features.csv",
                )
                response = connection.getresponse()
                csv_body = response.read().decode("utf-8")
                self.assertEqual(response.status, 200)
                self.assertIn("probe-a-concordant", csv_body)
                self.assertNotIn("GSM", csv_body)
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
