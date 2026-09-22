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
        self.assertIn('id="sequence-review-view"', html)
        self.assertIn('id="sequence-review-open"', html)
        self.assertIn('id="sequence-batch-list"', html)
        self.assertIn('id="sequence-batch-view"', html)
        self.assertIn('id="geo-consistency-list"', html)
        self.assertIn("/v1/geo-count-consistency", javascript)
        self.assertIn("/v1/geo-expression-analyses", javascript)
        self.assertIn("/v1/geo-review/summary", javascript)
        self.assertIn("geo-review-summary.v1", javascript)
        self.assertIn("geo-expression-analysis-page.v1", javascript)
        self.assertIn("/v1/geo-expression-consistency", javascript)
        self.assertIn("geo-expression-consistency-page.v1", javascript)
        self.assertIn("geoConsistencyFilterQuery", javascript)
        self.assertIn("geoExpressionConsistencyFilterQuery", javascript)
        self.assertIn("/v1/sequence-analyses", javascript)
        self.assertIn("/v1/sequence-review/summary", javascript)
        self.assertIn("/v1/sequence-review/motifs", javascript)
        self.assertIn("/v1/sequence-batches", javascript)
        self.assertIn("sequence-haplotype-batch-changes.v1", javascript)
        self.assertIn("glio-noncode.sequence-review-motifs.v1", javascript)
        self.assertIn("sequence-haplotype-analysis.v1", javascript)
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
            channels = [int(hex_color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
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
        self.assertIn("request !== model.sequenceListRequest", script)
        self.assertIn(
            "await Promise.all([loadRuns(false, true), loadGeoAnalyses(false, true), loadGeoReviewSummary(), loadGeoExpressionAnalyses(), loadGeoConsistencyRecords(), loadGeoExpressionConsistencyRecords(), loadSequenceAnalyses(), loadSequenceBatches(), loadSequenceReview()])",
            script,
        )


if __name__ == "__main__":
    unittest.main()
