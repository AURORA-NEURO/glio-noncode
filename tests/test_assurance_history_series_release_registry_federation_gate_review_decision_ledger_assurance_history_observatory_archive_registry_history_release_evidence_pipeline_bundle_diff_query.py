"""Deep contracts for bounded release-evidence bundle-diff queries."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry as registry
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history as history
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline as pipeline
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle as bundle
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff as diff
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff_query as query
from glio_noncode.errors import ValidationError
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline import RegistryHistoryReleaseEvidencePipelineFixture


class RegistryHistoryReleaseEvidencePipelineBundleDiffQueryFixture(RegistryHistoryReleaseEvidencePipelineFixture):
    BUNDLE_COMMAND = RegistryHistoryReleaseEvidencePipelineFixture.PIPELINE_COMMAND + "-bundle"
    DIFF_COMMAND = BUNDLE_COMMAND + "-diff"
    QUERY_COMMAND = DIFF_COMMAND + "-query"

    def bundle_for(self, root: Path, name: str) -> Path:
        value = self.one_registry(root, name, registry_id="registry:" + name)
        registry_dir = root / (name + "-registry")
        registry.write_registry(value, registry_dir)
        history_dir = root / (name + "-history")
        history.write_history(history.build_history_from_directories((registry_dir, registry_dir), history_id="history:" + name), history_dir)
        pipeline_value = pipeline.build_pipeline(history_dir)
        bundle_dir = root / (name + "-bundle")
        bundle.write_bundle(pipeline_value, bundle_dir)
        return bundle_dir


class RegistryHistoryReleaseEvidencePipelineBundleDiffQueryBuildTests(RegistryHistoryReleaseEvidencePipelineBundleDiffQueryFixture):
    def test_identical_downloaded_bundle_has_stable_semantic_and_file_queries(self):
        source = Path(tempfile.gettempdir()) / "glio-noncode-history-release-evidence-pipeline-bundle-demo"
        if not source.is_dir():
            self.skipTest("the optional local downloaded-data bundle is not present")
        fields = query.query_bundle_directories(source, source, resource="fields")
        self.assertEqual(fields.total_count, len(diff.BUNDLE_FIELDS))
        self.assertEqual(fields.returned_count, len(diff.BUNDLE_FIELDS))
        self.assertTrue(all(record["changed"] is False for record in fields.records))
        files = query.query_bundle_directories(source, source, resource="files")
        self.assertEqual(files.total_count, len(bundle.FILES))
        self.assertEqual(tuple(record["name"] for record in files.records), bundle.FILES)
        self.assertEqual(query.query_bundle_directories(source, source, resource="changed").total_count, 0)
        self.assertEqual(query.query_bundle_directories(source, source, resource="unchanged").total_count, len(bundle.FILES))
        replay = query.query_result_from_mapping(json.loads(query.query_json(fields)))
        self.assertEqual(replay.to_dict(), fields.to_dict())
        self.assertEqual(query.address_query(fields), fields.content_address)
        self.assert_public(query.query_schema())
        self.assert_public(query.query_result_schema())
        self.assert_public(query.capabilities())

    def test_changed_bundle_supports_semantic_file_evidence_filters_and_pagination(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = self.bundle_for(root / "baseline", "baseline")
            candidate = self.bundle_for(root / "candidate", "candidate")
            changed = query.query_bundle_directories(baseline, candidate, resource="changed")
            self.assertEqual(changed.total_count, len(bundle.FILES))
            self.assertEqual(changed.returned_count, len(bundle.FILES))
            self.assertTrue(all(record["action"] == "changed" for record in changed.records))
            field = query.query_bundle_directories(baseline, candidate, resource="fields", changed_field="pipeline_address")
            self.assertEqual(field.total_count, 1)
            self.assertEqual(field.records[0]["field"], "pipeline_address")
            self.assertTrue(field.records[0]["changed"])
            named = query.query_bundle_directories(baseline, candidate, resource="files", name="pipeline.json")
            self.assertEqual(named.total_count, 1)
            self.assertEqual(named.records[0]["name"], "pipeline.json")
            evidence = query.query_bundle_directories(baseline, candidate, resource="evidence", changed_field="hash")
            self.assertEqual(evidence.total_count, len(bundle.FILES))
            self.assertIn("baseline_hash", evidence.records[0])
            page = query.query_bundle_directories(baseline, candidate, resource="files", offset=1, limit=2)
            self.assertEqual(page.total_count, len(bundle.FILES))
            self.assertEqual(page.returned_count, 2)
            self.assertEqual(query.query_bundle_directories(baseline, candidate, resource="files", text="PIPELINE.JSON").total_count, 1)
            self.assertIn("| name |", query.render_query_markdown(page))
            self.assertIn("name", query.query_csv(page).splitlines()[0])

    def test_query_rejects_invalid_filters_and_tampered_result(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = self.bundle_for(Path(temporary), "clean")
            value = query.query_bundle_directories(source, source, resource="summary")
            document = value.to_dict()
            document["records"][0]["state"] = "tampered"
            with self.assertRaises(ValidationError):
                query.query_result_from_mapping(document)
            for kwargs in ({"action": "unknown"}, {"name": "unknown.json"}, {"changed_field": "unknown"}, {"limit": 0}, {"limit": query.MAX_LIMIT + 1}):
                with self.assertRaises(ValidationError):
                    query.query_bundle_directories(source, source, resource="files", **kwargs)


class RegistryHistoryReleaseEvidencePipelineBundleDiffQueryCliApiTests(RegistryHistoryReleaseEvidencePipelineBundleDiffQueryFixture):
    def test_cli_query_and_contract_commands(self):
        from glio_noncode.cli import main

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = self.bundle_for(root / "baseline", "baseline")
            candidate = self.bundle_for(root / "candidate", "candidate")
            output = root / "query.json"
            self.assertEqual(main([self.QUERY_COMMAND, "--baseline", str(baseline), "--candidate", str(candidate), "--resource", "changed", "--format", "json", "--output", str(output)]), 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["total_count"], len(bundle.FILES))
            self.assertEqual(main([self.QUERY_COMMAND + "-query-schema"]), 0)
            self.assertEqual(main([self.QUERY_COMMAND + "-query-result-schema"]), 0)
            self.assertEqual(main([self.QUERY_COMMAND + "-query-capabilities"]), 0)

    def test_http_query_route_and_contracts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = self.bundle_for(root / "baseline", "baseline")
            candidate = self.bundle_for(root / "candidate", "candidate")
            server, thread = self.server()
            try:
                prefix = "http://127.0.0.1:%s/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry/history/release-gate/release-evidence-pipeline/bundle/diff"
                prefix = prefix % server.server_port
                params = {"baseline": str(baseline), "candidate": str(candidate), "resource": "fields", "format": "json"}
                with urlopen(prefix + "/query?" + urlencode(params)) as response:
                    payload = json.loads(response.read())
                    self.assertEqual(payload["total_count"], len(diff.BUNDLE_FIELDS))
                    self.assertEqual(payload["returned_count"], len(diff.BUNDLE_FIELDS))
                with urlopen(prefix + "/query-schema") as response:
                    self.assertIn("changed_field", json.loads(response.read())["properties"])
                with urlopen(prefix + "/query-result-schema") as response:
                    self.assertIn("records", json.loads(response.read())["properties"])
                with urlopen(prefix + "/query-capabilities") as response:
                    self.assertIn("deterministic pagination", json.loads(response.read())["features"])
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


if __name__ == "__main__":
    unittest.main()
