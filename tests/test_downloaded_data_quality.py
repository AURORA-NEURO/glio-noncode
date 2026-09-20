"""Deep regression coverage for downloaded-data quality decisions."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from glio_noncode import downloaded_data_catalog as catalog_model
from glio_noncode import downloaded_data_ingestion as ingestion_model
from glio_noncode import downloaded_data_profile as profile_model
from glio_noncode import downloaded_data_quality as quality_model
from glio_noncode import downloaded_data_quality_audit as audit_model
from glio_noncode import downloaded_data_quality_diff as diff_model
from glio_noncode import downloaded_data_quality_diff_audit as diff_audit_model
from glio_noncode import downloaded_data_quality_diff_query as diff_query_model
from glio_noncode import downloaded_data_quality_diff_query_audit as diff_query_audit_model
from glio_noncode import downloaded_data_quality_diff_runtime as diff_runtime_model
from glio_noncode import downloaded_data_quality_diff_runtime_audit as diff_runtime_audit_model
from glio_noncode import downloaded_data_quality_query as query_model
from glio_noncode import downloaded_data_quality_query_audit as query_audit_model
from glio_noncode import downloaded_data_quality_runtime as runtime_model
from glio_noncode.errors import ValidationError


class DownloadedDataQualityTests(unittest.TestCase):
    @staticmethod
    def _zip(*, missing: bool = False) -> bytes:
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            if missing:
                archive.writestr("data/rows.json", json.dumps([{"id": "a"}, {"id": "b"}], separators=(",", ":")))
            else:
                archive.writestr("data/rows.json", json.dumps([{"id": "a", "value": 1}, {"id": "b", "value": 2}], separators=(",", ":")))
            archive.writestr("data/labels.csv", "id,label\na,alpha\nb,beta\n")
        return stream.getvalue()

    @classmethod
    def _profile(cls, *, missing: bool = False) -> profile_model.DownloadedDataProfile:
        raw = cls._zip(missing=missing)
        catalog = catalog_model.build_catalog(raw, catalog_id="quality-catalog")
        batch = ingestion_model.build_ingest(raw, catalog=catalog, batch_id="quality-batch", record_limit=100)
        return profile_model.build_profile(batch, profile_id="quality-profile")

    def test_accepted_quality_replays_through_audit_and_query(self) -> None:
        profile = self._profile()
        policy = quality_model.build_policy(
            policy_id="quality-policy-accepted",
            required_members=("data/labels.csv", "data/rows.json"),
            required_fields=("id", "label", "value"),
            allowed_value_types=("string", "integer"),
            max_missing_ratio_ppm=500_000,
            max_null_ratio_ppm=0,
            min_member_records=2,
        )
        quality = quality_model.build_quality(profile, policy=policy, result_id="quality-result-accepted")
        self.assertEqual((quality.state, quality.accepted, quality.failed_count), ("accepted", True, 0))
        self.assertEqual(quality_model.quality_from_mapping(quality.to_dict()).content_address, quality.content_address)
        audit = audit_model.audit_quality(quality)
        self.assertEqual((audit.passed_count, audit.check_count, audit.accepted), (18, 18, True))
        query = query_model.query_quality(quality, resources=("summary", "findings"), limit=100)
        self.assertEqual((query.returned_count, query.matched_count), (quality.check_count + 1, quality.check_count + 1))
        query_audit = query_audit_model.audit_query(query)
        self.assertEqual((query_audit.passed_count, query_audit.check_count, query_audit.accepted), (12, 12, True))

    def test_review_and_blocked_states_are_explicit(self) -> None:
        profile = self._profile(missing=True)
        review_policy = quality_model.build_policy(policy_id="quality-policy-review", required_fields=("value",), max_missing_ratio_ppm=0, failure_state="review")
        blocked_policy = quality_model.build_policy(policy_id="quality-policy-blocked", required_fields=("value",), max_missing_ratio_ppm=0, failure_state="blocked")
        review = quality_model.build_quality(profile, policy=review_policy, result_id="quality-result-review")
        blocked = quality_model.build_quality(profile, policy=blocked_policy, result_id="quality-result-blocked")
        self.assertEqual((review.state, review.accepted, review.failed_count), ("review", False, 2))
        self.assertEqual((blocked.state, blocked.accepted, blocked.failed_count), ("blocked", False, 2))
        self.assertEqual({item.rule_id for item in review.findings if not item.passed}, {"required-field", "field-missing-ratio"})

    def test_query_filters_and_pagination_replay(self) -> None:
        quality = quality_model.build_quality(self._profile(), policy=quality_model.build_policy(policy_id="quality-policy-query"), result_id="quality-result-query")
        query = query_model.query_quality(quality, resources=("findings",), scope="field", limit=2)
        self.assertEqual(query.returned_count, 2)
        self.assertTrue(query.truncated)
        self.assertTrue(all(row.scope == "field" for row in query.rows))
        self.assertEqual(query_model.query_from_mapping(query.to_dict()).content_address, query.content_address)
        self.assertEqual(query_audit_model.audit_query(query).passed_count, 12)

    def test_strict_boundaries_reject_coercion_and_tampering(self) -> None:
        with self.assertRaises(ValidationError):
            quality_model.build_policy(policy_id="quality-policy-bad", min_records="1")
        with self.assertRaises(ValidationError):
            quality_model.build_policy(policy_id="quality-policy-bad", allowed_value_types=("integer", "integer"))
        with self.assertRaises(ValidationError):
            quality_model.build_policy(policy_id="quality-policy-bad", required_fields="value")
        quality = quality_model.build_quality(self._profile(), policy=quality_model.build_policy(policy_id="quality-policy-tamper"), result_id="quality-result-tamper")
        altered = quality.to_dict()
        altered["accepted"] = False
        with self.assertRaises(ValidationError):
            quality_model.quality_from_mapping(altered)
        altered_query = query_model.query_quality(quality, resources=("summary",), limit=1).to_dict()
        altered_query["returned_count"] = 0
        with self.assertRaises(ValidationError):
            query_model.query_from_mapping(altered_query)

    def test_schemas_and_capabilities_are_public_and_bounded(self) -> None:
        for schema in (quality_model.policy_schema(), quality_model.finding_schema(), quality_model.quality_schema(), audit_model.check_schema(), audit_model.audit_schema(), query_model.row_schema(), query_model.query_schema(), query_audit_model.check_schema(), query_audit_model.audit_schema()):
            self.assertFalse(any(key.casefold() in ingestion_model.FORBIDDEN_PUBLIC_KEYS for key in schema.get("properties", {})))
        self.assertEqual(quality_model.capabilities()["version"], quality_model.VERSION)
        self.assertEqual(audit_model.capabilities()["check_ids"], audit_model.CHECK_IDS)
        self.assertEqual(query_model.capabilities()["resources"], query_model.RESOURCES)

    def test_runtime_persists_exact_files_and_rejects_tampering(self) -> None:
        profile = self._profile()
        runtime = runtime_model.build_runtime(
            profile,
            policy=quality_model.build_policy(policy_id="quality-policy-runtime"),
            runtime_id="quality-runtime",
            result_id="quality-result-runtime",
            resources=("summary", "findings"),
            limit=100,
        )
        self.assertTrue(runtime.release_ready)
        self.assertEqual(runtime_model.runtime_from_mapping(runtime.to_dict()).content_address, runtime.content_address)
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "runtime"
            runtime_model.persist_runtime(runtime, destination)
            self.assertEqual(tuple(sorted(path.name for path in destination.iterdir())), tuple(sorted(runtime_model.FILES)))
            self.assertEqual(runtime_model.load_runtime(destination).content_address, runtime.content_address)
            quality_path = destination / "quality.json"
            altered = json.loads(quality_path.read_text(encoding="utf-8"))
            altered["accepted"] = not altered["accepted"]
            quality_path.write_text(json.dumps(altered), encoding="utf-8")
            with self.assertRaises(ValidationError):
                runtime_model.load_runtime(destination)

    def test_quality_diff_replays_regressions_and_filters(self) -> None:
        profile = self._profile()
        left = quality_model.build_quality(profile, policy=quality_model.build_policy(policy_id="quality-diff-left"), result_id="quality-diff-left-result")
        right = quality_model.build_quality(profile, policy=quality_model.build_policy(policy_id="quality-diff-right", max_distinct_values=1), result_id="quality-diff-right-result")
        value = diff_model.build_diff(left, right, diff_id="quality-diff")
        self.assertGreater(value.changed_count, 0)
        self.assertGreater(value.regressed_count, 0)
        self.assertEqual(diff_model.diff_from_mapping(value.to_dict()).content_address, value.content_address)
        audit = diff_audit_model.audit_diff(value)
        self.assertEqual((audit.check_count, audit.passed_count, audit.accepted), (14, 14, True))
        query = diff_query_model.query_diff(value, resources=("summary", "regressed"), direction="regressed", limit=2)
        self.assertEqual(query.returned_count, min(2, value.regressed_count))
        self.assertTrue(diff_query_audit_model.audit_query(query).accepted)

    def test_quality_diff_runtime_persists_exact_files_and_rejects_noncanonical_tamper(self) -> None:
        profile = self._profile()
        left = quality_model.build_quality(profile, policy=quality_model.build_policy(policy_id="quality-runtime-diff-left"), result_id="quality-runtime-diff-left")
        right = quality_model.build_quality(profile, policy=quality_model.build_policy(policy_id="quality-runtime-diff-right", max_distinct_values=1), result_id="quality-runtime-diff-right")
        runtime = diff_runtime_model.build_runtime(left, right, runtime_id="quality-diff-runtime", resources=("summary", "items"), limit=25)
        self.assertTrue(diff_runtime_audit_model.audit_runtime(runtime).accepted)
        self.assertEqual(diff_runtime_model.runtime_from_mapping(runtime.to_dict()).content_address, runtime.content_address)
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "runtime"
            diff_runtime_model.persist_runtime(runtime, destination)
            self.assertEqual(tuple(sorted(path.name for path in destination.iterdir())), tuple(sorted(diff_runtime_model.FILES)))
            self.assertEqual(diff_runtime_model.load_runtime(destination).content_address, runtime.content_address)
            diff_path = destination / "diff.json"
            altered = json.loads(diff_path.read_text(encoding="utf-8"))
            altered["regressed_count"] += 1
            diff_path.write_text(json.dumps(altered), encoding="utf-8")
            with self.assertRaises(ValidationError):
                diff_runtime_model.load_runtime(destination)

    def test_cli_and_api_surface_replays_profile_json(self) -> None:
        from urllib.parse import urlencode
        from urllib.request import urlopen

        from glio_noncode.api import create_server
        from glio_noncode.cli import main

        profile = self._profile()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile_path = root / "profile.json"
            profile_path.write_text(profile_model.profile_json(profile), encoding="utf-8")
            quality_path = root / "quality.json"
            self.assertEqual(main(["downloaded-data-quality", str(profile_path), "--format", "json", "--output", str(quality_path)]), 0)
            self.assertEqual(main(["downloaded-data-quality-audit", str(quality_path), "--format", "json", "--output", str(root / "audit.json")]), 0)
            self.assertEqual(main(["downloaded-data-quality-query", str(quality_path), "--resource", "findings", "--limit", "2", "--format", "json", "--output", str(root / "query.json")]), 0)
            runtime_path = root / "runtime"
            self.assertEqual(main(["downloaded-data-quality-runtime", str(profile_path), "--destination", str(runtime_path), "--overwrite", "--format", "summary", "--output", str(root / "runtime-summary.json")]), 0)
            self.assertEqual(main(["downloaded-data-quality-query-audit", str(runtime_path), "--format", "json", "--output", str(root / "query-audit.json")]), 0)
            self.assertEqual(main(["downloaded-data-quality-runtime-audit", str(runtime_path), "--format", "json", "--output", str(root / "runtime-audit.json")]), 0)
            self.assertEqual(tuple(sorted(path.name for path in runtime_path.iterdir())), tuple(sorted(runtime_model.FILES)))
            right_quality = quality_model.build_quality(profile, policy=quality_model.build_policy(policy_id="surface-diff-right", max_distinct_values=1), result_id="surface-diff-right")
            right_quality_path = root / "right-quality.json"
            right_quality_path.write_text(quality_model.quality_json(right_quality), encoding="utf-8")
            diff_path = root / "diff.json"
            self.assertEqual(main(["downloaded-data-quality-diff", str(quality_path), str(right_quality_path), "--format", "json", "--output", str(diff_path)]), 0)
            self.assertEqual(main(["downloaded-data-quality-diff-audit", str(diff_path), "--format", "json", "--output", str(root / "diff-audit.json")]), 0)
            diff_runtime_path = root / "diff-runtime"
            self.assertEqual(main(["downloaded-data-quality-diff-runtime", str(quality_path), str(right_quality_path), "--destination", str(diff_runtime_path), "--overwrite", "--resource", "summary", "--resource", "regressed", "--format", "summary", "--output", str(root / "diff-runtime-summary.json")]), 0)
            self.assertEqual(main(["downloaded-data-quality-diff-query", str(diff_runtime_path), "--resource", "regressed", "--direction", "regressed", "--limit", "2", "--format", "json", "--output", str(root / "diff-query.json")]), 0)
            self.assertEqual(main(["downloaded-data-quality-diff-query-audit", str(diff_runtime_path), "--format", "json", "--output", str(root / "diff-query-audit.json")]), 0)
            self.assertEqual(main(["downloaded-data-quality-diff-runtime-audit", str(diff_runtime_path), "--format", "json", "--output", str(root / "diff-runtime-audit.json")]), 0)
            self.assertEqual(tuple(sorted(path.name for path in diff_runtime_path.iterdir())), tuple(sorted(diff_runtime_model.FILES)))

            server = create_server("127.0.0.1", 0)
            import threading

            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/quality"
                query = urlencode({"input": str(profile_path), "format": "json"})
                api_quality = json.loads(urlopen(base + "?" + query, timeout=10).read().decode())
                self.assertEqual((api_quality["accepted"], api_quality["record_count"]), (True, profile.record_count))
                api_query = json.loads(urlopen(base + "/query?" + urlencode({"input": str(quality_path), "resource": "findings", "limit": "2"}), timeout=10).read().decode())
                self.assertEqual(api_query["returned_count"], 2)
                api_runtime = json.loads(urlopen(base + "/runtime?" + urlencode({"input": str(profile_path), "destination": str(root / "api-runtime"), "overwrite": "true"}), timeout=10).read().decode())
                self.assertTrue(api_runtime["release_ready"])
                api_runtime_audit = json.loads(urlopen(base + "/runtime/audit?" + urlencode({"input": str(runtime_path)}), timeout=10).read().decode())
                self.assertTrue(api_runtime_audit["accepted"])
                diff_base = base + "/diff"
                api_diff = json.loads(urlopen(diff_base + "?" + urlencode({"left": str(quality_path), "right": str(right_quality_path), "format": "json"}), timeout=10).read().decode())
                self.assertGreater(api_diff["regressed_count"], 0)
                api_diff_query = json.loads(urlopen(diff_base + "/query?" + urlencode({"input": str(diff_path), "resource": "regressed", "direction": "regressed", "limit": "2"}), timeout=10).read().decode())
                self.assertGreater(api_diff_query["returned_count"], 0)
                api_diff_runtime = json.loads(urlopen(diff_base + "/runtime?" + urlencode({"left": str(quality_path), "right": str(right_quality_path), "destination": str(root / "api-diff-runtime"), "overwrite": "true"}), timeout=10).read().decode())
                self.assertTrue(api_diff_runtime["release_ready"])
                api_diff_runtime_audit = json.loads(urlopen(diff_base + "/runtime/audit?" + urlencode({"input": str(diff_runtime_path)}), timeout=10).read().decode())
                self.assertTrue(api_diff_runtime_audit["accepted"])
                diff_schema = json.loads(urlopen(diff_base + "/schema", timeout=10).read().decode())
                self.assertFalse(diff_schema["additionalProperties"])
                schema = json.loads(urlopen(base + "/schema", timeout=10).read().decode())
                self.assertFalse(schema["additionalProperties"])
                capabilities = json.loads(urlopen(base + "/capabilities", timeout=10).read().decode())
                self.assertEqual(capabilities["version"], quality_model.VERSION)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=10)


if __name__ == "__main__":
    unittest.main()
