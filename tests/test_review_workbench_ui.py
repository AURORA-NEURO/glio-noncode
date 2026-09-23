from __future__ import annotations

import json
import re
import tempfile
import unittest
from http.client import HTTPConnection
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.review_workbench_ui import workbench_asset
from glio_noncode.runtime import CaseRuntime

from .helpers import fixture_manifest


class ReviewWorkbenchUiTests(unittest.TestCase):
    def test_workbench_supports_skip_navigation_and_concise_selection_status(self) -> None:
        page = workbench_asset("/")
        script = workbench_asset("/assets/review-workbench.js")
        assert page is not None
        assert script is not None
        html = page[0].decode("utf-8")
        javascript = script[0].decode("utf-8")

        self.assertIn('href="#main-content">Skip to main content</a>', html)
        self.assertIn('<main id="main-content" class="page-shell" tabindex="-1">', html)
        self.assertIn(
            'id="selection-announcement" class="visually-hidden" role="status" '
            'aria-live="polite" aria-atomic="true"',
            html,
        )
        self.assertIn('class="workspace" aria-label="Selected run review">', html)
        self.assertNotIn('class="workspace" aria-label="Selected run review" aria-live=', html)
        self.assertIn("function announceSelection(text)", javascript)
        self.assertIn("GEO analysis ${page.summary.accession} opened.", javascript)
        self.assertIn("Case run ${run?.case_id || runId} opened.", javascript)
        self.assertIn("feature_contains", javascript)
        self.assertIn("fdr_significant", javascript)
        self.assertIn("min_abs_median_effect", javascript)
        self.assertIn("results.csv", javascript)
        self.assertIn("geoFilterTimer", javascript)
        self.assertIn("geo-result-filters", html)
        self.assertIn('id="geo-compare-selection"', html)
        self.assertIn('id="geo-review-summary"', html)
        self.assertIn('id="geo-review-status"', html)
        self.assertIn('id="geo-review-open"', html)
        self.assertIn('id="geo-review-view"', html)
        self.assertIn('id="geo-review-catalog-table"', html)
        self.assertIn('id="geo-result-filter-summary"', html)
        self.assertIn('id="geo-expression-filter-summary"', html)
        self.assertIn('id="geo-consistency-filter-summary"', html)
        self.assertIn('id="geo-sensitivity-filter-summary"', html)
        self.assertIn('id="geo-expression-consistency-filter-summary"', html)
        self.assertIn('id="geo-ledger-json-export"', html)
        self.assertIn("Ranked + tracked", html)
        self.assertIn('id="geo-review-tested-count"', html)
        self.assertIn('id="geo-review-fdr-count"', html)
        self.assertIn('id="geo-metric-reported"', html)
        self.assertIn('id="geo-metric-reported-detail"', html)
        self.assertIn('id="geo-review-reported-count"', html)
        self.assertIn('id="geo-review-consistency-coverage"', html)
        self.assertIn('id="geo-review-consistency-coverage-detail"', html)
        self.assertIn('id="geo-review-sensitivity-coverage"', html)
        self.assertIn('id="geo-review-sensitivity-coverage-detail"', html)
        self.assertIn('id="geo-review-expression-coverage"', html)
        self.assertIn('id="geo-review-expression-coverage-detail"', html)
        self.assertIn('id="geo-sensitivity-sign-fdr-filter"', html)
        self.assertIn('id="geo-run-csv-export"', html)
        self.assertIn('id="geo-review-preflight-count"', html)
        self.assertIn('id="geo-review-preflight-kinds"', html)
        self.assertIn('id="geo-review-preflight-states"', html)
        self.assertIn('id="geo-preflight-list"', html)
        self.assertIn('id="geo-preflight-accession-filter"', html)
        self.assertIn('id="geo-preflight-kind-filter"', html)
        self.assertIn('id="geo-preflight-load-more"', html)
        self.assertIn('id="geo-preflight-ledger-export"', html)
        self.assertIn('id="geo-preflight-ledger-json-export"', html)
        self.assertIn('id="geo-preflight-view"', html)
        self.assertIn('id="geo-preflight-metrics"', html)
        self.assertIn('id="geo-consistency-features"', html)
        self.assertIn('id="geo-consistency-view"', html)
        self.assertIn('id="geo-consistency-feature-filter"', html)
        self.assertIn('id="geo-consistency-sign-fdr-filter"', html)
        self.assertIn('id="geo-expression-analysis-list"', html)
        self.assertIn('id="geo-expression-analysis-view"', html)
        self.assertIn('id="geo-expression-consistency-view"', html)
        self.assertIn('id="geo-expression-consistency-feature-filter"', html)
        self.assertIn('id="sequence-analysis-list"', html)
        self.assertIn('id="sequence-analysis-view"', html)
        self.assertIn('id="sequence-download-provenance"', html)
        self.assertIn('id="sequence-review-view"', html)
        self.assertIn('id="sequence-review-open"', html)
        self.assertIn('id="sequence-review-source-filter"', html)
        self.assertIn('id="sequence-review-genome-filter"', html)
        self.assertIn('id="sequence-review-motif-filter-summary"', html)
        self.assertIn('id="sequence-review-motif-load-more"', html)
        self.assertIn('id="sequence-review-verification-table"', html)
        self.assertIn('id="sequence-review-verification-summary"', html)
        self.assertIn('id="sequence-batch-list"', html)
        self.assertIn('id="sequence-analysis-load-more"', html)
        self.assertIn('id="sequence-batch-load-more"', html)
        self.assertIn('id="sequence-batch-view"', html)
        self.assertIn('id="sequence-batch-change-filter-summary"', html)
        self.assertIn('id="sequence-analysis-motif-filter"', html)
        self.assertIn('id="sequence-analysis-change-load-more"', html)
        self.assertIn('id="sequence-batch-change-load-more"', html)
        self.assertIn('id="sequence-comparison-view"', html)
        self.assertIn('id="sequence-comparison-list"', html)
        self.assertIn('id="sequence-comparison-list-load-more"', html)
        self.assertIn('id="sequence-comparison-direction-filter"', html)
        self.assertIn('id="sequence-comparison-filter-summary"', html)
        self.assertIn('id="sequence-comparison-load-more"', html)
        self.assertIn('id="geo-consistency-list"', html)
        self.assertIn('id="geo-consistency-list-load-more"', html)
        self.assertIn('id="geo-sensitivity-list-load-more"', html)
        self.assertIn('id="geo-expression-consistency-list-load-more"', html)
        self.assertIn('id="module-workbench-list"', html)
        self.assertIn('id="module-workbench-load-more"', html)
        self.assertIn('id="module-workbench-overview"', html)
        self.assertIn('id="module-workbench-overall-score"', html)
        self.assertIn('id="module-workbench-depth-percent"', html)
        self.assertIn('id="module-workbench-high-risk-count"', html)
        self.assertIn('id="module-workbench-blocked-count"', html)
        self.assertIn('id="module-workbench-search"', html)
        self.assertIn('id="module-workbench-risk-filter"', html)
        self.assertIn('id="module-workbench-depth-filter"', html)
        self.assertIn('id="module-triage-list"', html)
        self.assertIn('id="module-triage-load-more"', html)
        self.assertIn('id="module-triage-risk-filter"', html)
        self.assertIn('id="module-triage-reason-filter"', html)
        self.assertIn('id="module-workbench-view"', html)
        self.assertIn('id="module-workbench-certification-table"', html)
        self.assertIn('id="module-workbench-evidence-table"', html)
        self.assertIn('id="module-workbench-lineage-table"', html)
        self.assertIn('id="module-workbench-tasks-table"', html)
        self.assertIn('id="module-workbench-portfolio-table"', html)
        self.assertIn('id="module-workbench-portfolio-summary"', html)
        self.assertIn('id="module-workbench-portfolio-summary-text"', html)
        self.assertIn('id="module-workbench-execution-table"', html)
        self.assertIn('id="module-workbench-execution-summary"', html)
        self.assertIn('id="module-workbench-execution-ledger-summary"', html)
        self.assertIn('id="module-workbench-execution-events-table"', html)
        self.assertIn('id="module-workbench-execution-events-summary"', html)
        self.assertIn("<th>Transition</th>", html)
        self.assertIn('id="module-workbench-limitations"', html)
        self.assertIn('id="module-workbench-triage-score"', html)
        self.assertIn('id="module-workbench-triage-summary"', html)
        self.assertIn('id="module-workbench-triage-note"', html)
        self.assertIn("/v1/geo-count-consistency", javascript)
        self.assertIn("sign_test_fdr_sensitivity", javascript)
        self.assertIn("ranked_feature_count", javascript)
        self.assertIn("Report coverage", javascript)
        self.assertIn("runs.csv", javascript)
        self.assertIn("Study coverage", javascript)
        self.assertIn("studies.csv", javascript)
        self.assertIn("geo-expression-consistency-coverage", javascript)
        self.assertIn("/v1/geo-expression-analyses", javascript)
        self.assertIn("/v1/geo-review/summary", javascript)
        self.assertIn("/v1/geo-preflights", javascript)
        self.assertIn("function openGeoPreflight", javascript)
        self.assertIn("function preflightMetricRows", javascript)
        self.assertIn("pair_key_", javascript)
        self.assertIn("item.normalization", javascript)
        self.assertIn("function geoPreflightQuery", javascript)
        self.assertIn("loadGeoPreflights(true)", javascript)
        self.assertIn("catalogRow.sample_count", javascript)
        self.assertIn("source.count_matrix?.source_sha256", javascript)
        self.assertIn("source.sample_metadata?.source_sha256", javascript)
        self.assertIn("report_schema", javascript)
        self.assertIn("/v1/geo-review/summary.csv?verify_reports=true", javascript)
        self.assertIn("/v1/geo-review/ledger.json?verify_reports=true", javascript)
        self.assertIn("tracked_feature_id_count_total", javascript)
        self.assertIn("filtered_result_summary", javascript)
        self.assertIn("filtered_feature_summary", javascript)
        self.assertIn("Download health ledger", javascript)
        self.assertIn("geo-review-summary.v1", javascript)
        self.assertIn("const accessionValues = new Set()", javascript)
        self.assertIn("geo-review-preflight-count", javascript)
        self.assertIn("function renderGeoReviewBreakdown", javascript)
        self.assertIn("tested_feature_count_total", javascript)
        self.assertIn("fdr_significant_feature_count_total", javascript)
        self.assertIn("function openGeoReview()", javascript)
        self.assertIn("geo-expression-analysis-page.v1", javascript)
        self.assertIn("/v1/geo-expression-consistency", javascript)
        self.assertIn("geo-expression-consistency-page.v1", javascript)
        self.assertIn("geoConsistencyFilterQuery", javascript)
        self.assertIn("geoExpressionConsistencyFilterQuery", javascript)
        self.assertIn("function loadGeoConsistencyRecords(append = false)", javascript)
        self.assertIn("function loadGeoSensitivityRecords(append = false)", javascript)
        self.assertIn("function loadGeoExpressionConsistencyRecords(append = false)", javascript)
        self.assertIn("function loadModuleAssessments(append = false)", javascript)
        self.assertIn("function moduleAssessmentQuery(offset)", javascript)
        self.assertIn("function reloadModuleAssessments()", javascript)
        self.assertIn("function renderModuleWorkbenchOverview()", javascript)
        self.assertIn("function loadModuleWorkbenchOverview()", javascript)
        self.assertIn("/v1/module-workbench?format=summary", javascript)
        self.assertIn("/v1/module-workbench/execution?include_items=false&include_events=false", javascript)
        self.assertIn("module-execution-task-count", javascript)
        self.assertIn("module-execution-overview-summary", javascript)
        self.assertIn("moduleExecutionSummary", javascript)
        self.assertIn("function previewModuleExecutionPlan()", javascript)
        self.assertIn("module-execution-preview-button", javascript)
        self.assertIn("/v1/module-workbench/execution/plan/preview/query?", javascript)
        self.assertIn("durable ledger unchanged", javascript)
        self.assertIn("added_task_count", javascript)
        self.assertIn("removed_task_count", javascript)
        self.assertIn("added_dependency_edge_count", javascript)
        self.assertIn("comparison.candidate_plan_address", javascript)
        self.assertIn("moduleWorkbenchSummaryRequest", javascript)
        self.assertIn("function renderModuleExecution()", javascript)
        self.assertIn("function renderModuleExecutionPlan()", javascript)
        self.assertIn("function loadModuleExecutionPlan(moduleId)", javascript)
        self.assertIn("/v1/module-workbench/execution/plan/query?resource=nodes&module_id=", javascript)
        self.assertIn("module-workbench-plan-table", javascript)
        self.assertIn("deferred_prerequisite_count", javascript)
        self.assertIn("function renderModulePortfolio()", javascript)
        self.assertIn("/v1/module-workbench/portfolio/query?module_id=", javascript)
        self.assertIn("portfolio_summary", javascript)
        self.assertIn("module-workbench-execution-events-table", javascript)
        self.assertIn("module events", javascript)
        self.assertIn("resource=events&module_id=", javascript)
        self.assertIn("function postJson(path, payload)", javascript)
        self.assertIn("executionActionsByState", javascript)
        self.assertIn("/v1/module-workbench/execution/command", javascript)
        self.assertIn("expected_ledger_address", javascript)
        self.assertIn("transitions are detail-required", javascript)
        self.assertIn("/v1/module-workbench/execution/query?resource=items&module_id=", javascript)
        self.assertIn("module-workbench-execution-v1", javascript)
        self.assertIn("selected execution items", javascript)
        self.assertIn("function renderModuleTriage()", javascript)
        self.assertIn("function moduleTriageQuery(offset)", javascript)
        self.assertIn("function loadModuleTriage(append = false)", javascript)
        self.assertIn("function reloadModuleTriage()", javascript)
        self.assertIn("/v1/module-workbench/triage/query?${moduleTriageQuery(offset)}", javascript)
        self.assertIn("moduleTriageFilters.reason", javascript)
        self.assertIn("module-workbench-triage-score", javascript)
        self.assertIn("Recommended task IDs", javascript)
        self.assertIn("moduleFilters.depth_band", javascript)
        self.assertIn("function openModuleWorkbenchDetail(moduleId)", javascript)
        self.assertIn("/v1/module-workbench/query?${moduleAssessmentQuery(offset)}", javascript)
        self.assertIn("/v1/module-workbench/detail?module_id=", javascript)
        self.assertIn("module-workbench-detail-v1", javascript)
        self.assertIn("loadGeoConsistencyRecords(true)", javascript)
        self.assertIn("loadGeoSensitivityRecords(true)", javascript)
        self.assertIn("loadGeoExpressionConsistencyRecords(true)", javascript)
        self.assertIn("/v1/sequence-analyses", javascript)
        self.assertIn("function loadSequenceAnalyses(append = false)", javascript)
        self.assertIn("loadSequenceAnalyses(true)", javascript)
        self.assertIn("sequenceListRequest", javascript)
        self.assertIn("/v1/sequence-review/summary", javascript)
        self.assertIn("/v1/sequence-review/verify", javascript)
        self.assertIn("sequenceReviewVerification", javascript)
        self.assertIn("summary.catalogs.sequence_comparisons", javascript)
        self.assertIn("sequence-review-verification-table", javascript)
        self.assertIn("verification.failed_count", javascript)
        self.assertIn("/v1/sequence-review/motifs", javascript)
        self.assertIn("/v1/sequence-review/motifs.csv", javascript)
        self.assertIn("filterQuery.delete(\"limit\")", javascript)
        self.assertIn("filterQuery.delete(\"offset\")", javascript)
        self.assertIn("function sequenceReviewMotifQuery", javascript)
        self.assertIn("function loadMoreSequenceReviewMotifs", javascript)
        self.assertIn("sequenceReviewMotifRequest", javascript)
        self.assertIn("sequence-review-motif-load-more", javascript)
        self.assertIn("/v1/sequence-batches", javascript)
        self.assertIn("function loadSequenceBatches(append = false)", javascript)
        self.assertIn("loadSequenceBatches(true)", javascript)
        self.assertIn("sequenceBatchListRequest", javascript)
        self.assertIn("filtered_change_summary", javascript)
        self.assertIn("/v1/sequence-comparisons", javascript)
        self.assertIn("function openSequenceComparison", javascript)
        self.assertIn("function sequenceAnalysisFilterQuery", javascript)
        self.assertIn("function loadMoreSequenceAnalysisChanges", javascript)
        self.assertIn("function loadMoreSequenceBatchChanges", javascript)
        self.assertIn("sequence-analysis-change-load-more", javascript)
        self.assertIn("sequence-batch-change-load-more", javascript)
        self.assertIn("changeSummary.created_count", javascript)
        self.assertIn("changeSummary.disrupted_count", javascript)
        self.assertIn("function loadSequenceComparisons(append = false)", javascript)
        self.assertIn("loadSequenceComparisons(true)", javascript)
        self.assertIn("function loadMoreSequenceComparisonChanges", javascript)
        self.assertIn("sequence-comparison-load-more", javascript)
        self.assertIn("sequence-batch-comparison-changes.v1", javascript)
        self.assertIn("sequence-haplotype-batch-changes.v1", javascript)
        self.assertIn("glio-noncode.sequence-review-motifs.v1", javascript)
        self.assertIn("filtered_motif_summary", javascript)
        self.assertIn('params.set("source_id", sourceId)', javascript)
        self.assertIn('params.set("genome_build", genomeBuild)', javascript)
        self.assertIn("sequence-haplotype-analysis.v1", javascript)
        self.assertIn("source.downloaded_inputs", javascript)
        self.assertIn("sequence-download-provenance", javascript)
        self.assertIn("reports_with_complete_download_receipts_count", javascript)
        self.assertIn("complete download receipts", javascript)
        self.assertIn("result_state", javascript)
        self.assertIn("Missing bounded rows remain", html)
        self.assertIn("Compare exact IDs", html)

    def test_visible_workbench_text_has_a_readable_minimum_size(self) -> None:
        stylesheet = workbench_asset("/assets/review-workbench.css")
        assert stylesheet is not None
        css = stylesheet[0].decode("utf-8")
        declarations = re.findall(r"(?<![\w-])font(?:-size)?\s*:\s*([^;{}]+)", css)
        pixel_sizes = [
            float(match.group(1))
            for declaration in declarations
            if (match := re.search(r"(?<![\w.])(\d+(?:\.\d+)?)px", declaration))
        ]

        self.assertTrue(pixel_sizes)
        self.assertGreaterEqual(min(pixel_sizes), 12)

    def test_workbench_muted_text_and_focus_colors_keep_contrast(self) -> None:
        stylesheet = workbench_asset("/assets/review-workbench.css")
        assert stylesheet is not None
        css = stylesheet[0].decode("utf-8")
        variables = dict(re.findall(r"(--(?:muted|soft))\s*:\s*(#[0-9a-fA-F]{6})", css))
        self.assertEqual(set(variables), {"--muted", "--soft"})

        def luminance(hex_color: str) -> float:
            channels = [int(hex_color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
            linear = [
                value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
                for value in channels
            ]
            return sum(
                value * weight
                for value, weight in zip(linear, (0.2126, 0.7152, 0.0722), strict=True)
            )

        def contrast(foreground: str, background: str) -> float:
            lighter, darker = sorted((luminance(foreground), luminance(background)), reverse=True)
            return (lighter + 0.05) / (darker + 0.05)

        for name, color in variables.items():
            with self.subTest(color=name):
                self.assertGreaterEqual(contrast(color, "#ffffff"), 4.5)
        focus_color = re.search(r"outline:\s*3px solid (#[0-9a-fA-F]{6})", css)
        self.assertIsNotNone(focus_color)
        assert focus_color is not None
        self.assertGreaterEqual(contrast(focus_color.group(1), "#ffffff"), 3.0)

    def test_assets_are_fixed_allowlisted_package_resources(self) -> None:
        for path, content_type in (
            ("/", "text/html; charset=utf-8"),
            ("/workspace/", "text/html; charset=utf-8"),
            ("/assets/review-workbench.css", "text/css; charset=utf-8"),
            ("/assets/review-workbench.js", "text/javascript; charset=utf-8"),
        ):
            with self.subTest(path=path):
                asset = workbench_asset(path)
                self.assertIsNotNone(asset)
                assert asset is not None
                self.assertEqual(asset[1], content_type)
                self.assertTrue(asset[0])

        for path in ("/assets/../../README.md", "/assets/review-workbench.js?x=1", "README.md"):
            with self.subTest(path=path):
                self.assertIsNone(workbench_asset(path))

    def test_server_serves_local_assets_and_replay_verified_review_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                connection.request("GET", "/")
                page = connection.getresponse()
                page_body = page.read().decode("utf-8")
                self.assertEqual(page.status, 200)
                self.assertIn("text/html", page.getheader("Content-Type", ""))
                self.assertIn("default-src 'none'", page.getheader("Content-Security-Policy", ""))
                self.assertEqual(page.getheader("X-Content-Type-Options"), "nosniff")
                self.assertIn("/assets/review-workbench.js", page_body)
                self.assertNotIn("<script>", page_body)

                connection.request("GET", "/assets/review-workbench.js")
                script = connection.getresponse()
                script_body = script.read().decode("utf-8")
                self.assertEqual(script.status, 200)
                self.assertIn("/v1/runs?limit=", script_body)
                self.assertIn("/review-workspace", script_body)
                self.assertIn("textContent", script_body)
                self.assertNotIn("innerHTML", script_body)
                self.assertEqual(
                    script.getheader("Content-Security-Policy"),
                    page.getheader("Content-Security-Policy"),
                )

                connection.request("GET", f"/v1/runs/{dossier.run_id}/review-workspace")
                response = connection.getresponse()
                payload = json.loads(response.read())
                self.assertEqual(response.status, 200)
                self.assertTrue(payload["accepted"])
                self.assertEqual(payload["run_id"], dossier.run_id)
                self.assertNotIn("payload", payload)

                connection.request("GET", "/assets/../../README.md")
                rejected = connection.getresponse()
                body = json.loads(rejected.read())
                self.assertEqual(rejected.status, 404)
                self.assertEqual(body["error"], "not_found")
                self.assertNotIn("contents", body)
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_page_assets_have_no_external_origins(self) -> None:
        for path in ("/", "/assets/review-workbench.css", "/assets/review-workbench.js"):
            asset = workbench_asset(path)
            assert asset is not None
            with self.subTest(path=path):
                text = asset[0].decode("utf-8")
                self.assertNotIn("http://", text)
                self.assertNotIn("https://", text)

    def test_workspace_selection_and_catalog_loads_are_generation_gated(self) -> None:
        asset = workbench_asset("/assets/review-workbench.js")
        assert asset is not None
        script = asset[0].decode("utf-8")

        self.assertGreaterEqual(script.count("request !== model.selectionRequest"), 4)
        self.assertIn("request !== model.runListRequest", script)
        self.assertIn("request !== model.geoListRequest", script)
        self.assertIn("request !== model.geoExpressionListRequest", script)
        self.assertIn("request !== model.geoExpressionConsistencyListRequest", script)
        self.assertIn("request !== model.geoConsistencyListRequest", script)
        self.assertIn("request !== model.geoSensitivityListRequest", script)
        self.assertIn("request !== model.sequenceListRequest", script)
        self.assertIn("request !== model.sequenceComparisonListRequest", script)
        self.assertIn("request !== model.moduleTriageListRequest", script)
        self.assertIn('$("refresh-button").addEventListener("click"', script)
        self.assertIn("loadGeoSensitivityRecords(), loadGeoExpressionConsistencyRecords()", script)
        self.assertIn(
            (
                "await Promise.all([loadRuns(false, true), loadGeoAnalyses(false, true), "
                "loadGeoReviewSummary(), loadGeoPreflights(), loadGeoExpressionAnalyses(), "
                "loadGeoConsistencyRecords(), loadGeoSensitivityRecords(), "
                "loadGeoExpressionConsistencyRecords(), "
                "loadSequenceAnalyses(), loadSequenceBatches(), loadSequenceComparisons(), "
                "loadSequenceReview(), loadModuleWorkbenchOverview(), loadModuleAssessments(), loadModuleTriage()])"
            ),
            script,
        )


if __name__ == "__main__":
    unittest.main()
