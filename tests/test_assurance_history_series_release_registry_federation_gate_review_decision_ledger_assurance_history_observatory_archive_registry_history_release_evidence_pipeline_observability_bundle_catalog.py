"""Deep contracts for verified observability-bundle catalogs and queries."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle as bundle
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog as catalog
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_query as catalog_query
from glio_noncode.errors import ValidationError
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_diff import RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffFixture


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogFixture(RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffFixture):
    CATALOG_COMMAND = RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffFixture.DIFF_COMMAND.removesuffix("-diff") + "-catalog"


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogBuildTests(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogFixture):
    def test_catalog_is_label_sorted_addressed_and_mapping_replayable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.bundle_for(root / "first", "first")
            second = self.bundle_for(root / "second", "second")
            value = catalog.build_catalog_from_directories({"zulu": second, "alpha": first}, catalog_id="catalog:downloaded")
            self.assertEqual(value.catalog_id, "catalog:downloaded")
            self.assertEqual(value.entry_count, 2)
            self.assertEqual(value.accepted_count, 2)
            self.assertEqual(value.ready_count, 2)
            self.assertEqual(value.rejected_count, 0)
            self.assertEqual(tuple(entry.label for entry in value.entries), ("alpha", "zulu"))
            self.assertEqual(tuple(entry.ordinal for entry in value.entries), (1, 2))
            self.assertEqual(catalog.address_catalog(value), value.content_address)
            replayed = catalog.catalog_from_mapping(json.loads(catalog.catalog_json(value)))
            self.assertEqual(replayed.to_dict(), value.to_dict())
            self.assertEqual(catalog.catalog_csv(value).splitlines()[0], "ordinal,label,bundle_address,pipeline_state,pipeline_accepted,observability_state,audit_state,audit_accepted,content_address")
            self.assertIn("alpha", catalog.render_catalog_markdown(value))
            self.assertNotIn(str(root), catalog.catalog_json(value))
            self.assert_public(value)

    def test_catalog_accepts_typed_bundles_and_rejects_duplicate_or_tampered_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.bundle_for(root / "source", "source")
            typed = bundle.verify_bundle(source)
            value = catalog.build_catalog((("typed", typed),))
            self.assertEqual(value.entry_count, 1)
            with self.assertRaises(ValidationError):
                catalog.build_catalog((("same", typed), ("same", typed)))
            tampered = source / bundle.OBSERVABILITY_NAME
            tampered.write_bytes(tampered.read_bytes() + b"\n")
            with self.assertRaises(ValidationError):
                catalog.build_catalog_from_directories((("tampered", source),))

    def test_catalog_schemas_capabilities_and_bounds_are_public(self):
        self.assert_public(catalog.entry_schema())
        self.assert_public(catalog.catalog_schema())
        self.assert_public(catalog.capabilities())
        self.assertEqual(catalog.capabilities()["limits"]["max_entries"], catalog.MAX_ENTRIES)
        self.assertEqual(catalog.build_catalog(()).entry_count, 0)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogQueryTests(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogFixture):
    def test_query_resources_filters_and_pagination_are_deterministic(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.bundle_for(root / "first", "first")
            second = self.bundle_for(root / "second", "second")
            value = catalog.build_catalog_from_directories((("alpha", first), ("beta", second)))
            self.assertEqual(catalog_query.query_catalog(value).total_count, 1)
            self.assertEqual(catalog_query.query_catalog(value, resource="entries").total_count, 2)
            self.assertEqual(catalog_query.query_catalog(value, resource="accepted").total_count, 2)
            self.assertEqual(catalog_query.query_catalog(value, resource="ready").total_count, 2)
            page = catalog_query.query_catalog(value, resource="entries", offset=1, limit=1)
            self.assertEqual(page.returned_count, 1)
            self.assertEqual(page.records[0]["label"], "beta")
            filtered = catalog_query.query_catalog(value, resource="evidence", label="alpha")
            self.assertEqual(filtered.total_count, 1)
            self.assertEqual(filtered.records[0]["bundle_address"], value.entries[0].bundle_address)
            self.assertEqual(catalog_query.address_query(page), page.content_address)
            replayed = catalog_query.query_result_from_mapping(json.loads(catalog_query.query_json(page)))
            self.assertEqual(replayed.to_dict(), page.to_dict())
            self.assertIn("beta", catalog_query.render_query_markdown(page))
            self.assertTrue(catalog_query.query_csv(page).startswith("ordinal,label,accepted,state,"))
            self.assert_public(page)

    def test_query_contracts_reject_invalid_filters_and_expose_capabilities(self):
        with self.assertRaises(ValidationError):
            catalog_query.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogQuery(state="unknown")
        with self.assertRaises(ValidationError):
            catalog_query.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogQuery(limit=0)
        self.assert_public(catalog_query.query_schema())
        self.assert_public(catalog_query.query_result_schema())
        self.assert_public(catalog_query.capabilities())


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogCliApiTests(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogFixture):
    def test_cli_catalog_query_and_contract_commands(self):
        from glio_noncode.cli import main

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.bundle_for(root / "first", "first")
            second = self.bundle_for(root / "second", "second")
            output = root / "catalog.json"
            arguments = [self.CATALOG_COMMAND, "--label", "alpha", "--directory", str(first), "--label", "beta", "--directory", str(second), "--format", "json", "--output", str(output)]
            self.assertEqual(main(arguments), 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["entry_count"], 2)
            query_output = root / "query.json"
            query_arguments = [self.CATALOG_COMMAND + "-query", "--label", "alpha", "--directory", str(first), "--label", "beta", "--directory", str(second), "--resource", "ready", "--limit", "1", "--output", str(query_output)]
            self.assertEqual(main(query_arguments), 0)
            self.assertEqual(json.loads(query_output.read_text(encoding="utf-8"))["returned_count"], 1)
            self.assertEqual(main([self.CATALOG_COMMAND + "-schema"]), 0)
            self.assertEqual(main([self.CATALOG_COMMAND + "-entry-schema"]), 0)
            self.assertEqual(main([self.CATALOG_COMMAND + "-capabilities"]), 0)
            self.assertEqual(main([self.CATALOG_COMMAND + "-query-query-schema"]), 0)
            self.assertEqual(main([self.CATALOG_COMMAND + "-query-query-result-schema"]), 0)
            self.assertEqual(main([self.CATALOG_COMMAND + "-query-query-capabilities"]), 0)

    def test_http_catalog_query_schema_and_capability_routes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.bundle_for(root / "first", "first")
            second = self.bundle_for(root / "second", "second")
            server, thread = self.server()
            try:
                prefix = f"http://127.0.0.1:{server.server_port}/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry/history/release-gate/release-evidence-pipeline/observability/bundle/catalog"
                params = [("label", "alpha"), ("directory", str(first)), ("label", "beta"), ("directory", str(second)), ("format", "summary")]
                with urlopen(prefix + "?" + urlencode(params)) as response:
                    payload = json.loads(response.read())
                    self.assertEqual(payload["entry_count"], 2)
                    self.assertEqual(payload["ready_count"], 2)
                with urlopen(prefix + "/query?" + urlencode(params + [("resource", "ready"), ("limit", "1")])) as response:
                    self.assertEqual(json.loads(response.read())["returned_count"], 1)
                with urlopen(prefix + "/schema") as response:
                    self.assertIn("entries", json.loads(response.read())["properties"])
                with urlopen(prefix + "/entry-schema") as response:
                    self.assertIn("label", json.loads(response.read())["properties"])
                with urlopen(prefix + "/query-schema") as response:
                    self.assertIn("resource", json.loads(response.read())["properties"])
                with urlopen(prefix + "/query-result-schema") as response:
                    self.assertIn("catalog_address", json.loads(response.read())["properties"])
                with urlopen(prefix + "/query-capabilities") as response:
                    self.assertIn("deterministic pagination", json.loads(response.read())["features"])
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


if __name__ == "__main__":
    unittest.main()
