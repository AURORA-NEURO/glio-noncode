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
from glio_noncode import downloaded_data_quality_diff_gate as diff_gate_model
from glio_noncode import downloaded_data_quality_diff_gate_audit as diff_gate_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_query as diff_gate_query_model
from glio_noncode import downloaded_data_quality_diff_gate_query_audit as diff_gate_query_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_runtime as diff_gate_runtime_model
from glio_noncode import downloaded_data_quality_diff_gate_runtime_audit as diff_gate_runtime_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_history as diff_gate_history_model
from glio_noncode import downloaded_data_quality_diff_gate_history_audit as diff_gate_history_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_history_query as diff_gate_history_query_model
from glio_noncode import downloaded_data_quality_diff_gate_history_query_audit as diff_gate_history_query_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_history_runtime as diff_gate_history_runtime_model
from glio_noncode import downloaded_data_quality_diff_gate_history_runtime_audit as diff_gate_history_runtime_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation as diff_gate_remediation_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_audit as diff_gate_remediation_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_query as diff_gate_remediation_query_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_query_audit as diff_gate_remediation_query_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_runtime as diff_gate_remediation_runtime_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_runtime_audit as diff_gate_remediation_runtime_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution as diff_gate_remediation_resolution_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_audit as diff_gate_remediation_resolution_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_query as diff_gate_remediation_resolution_query_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_query_audit as diff_gate_remediation_resolution_query_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_runtime as diff_gate_remediation_resolution_runtime_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_runtime_audit as diff_gate_remediation_resolution_runtime_audit_model
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

    def test_quality_diff_gate_classifies_regressions_and_replays_queries(self) -> None:
        profile = self._profile()
        left = quality_model.build_quality(profile, policy=quality_model.build_policy(policy_id="quality-gate-left"), result_id="quality-gate-left")
        right = quality_model.build_quality(profile, policy=quality_model.build_policy(policy_id="quality-gate-right", max_distinct_values=1), result_id="quality-gate-right")
        diff = diff_model.build_diff(left, right, diff_id="quality-gate-diff")
        gate = diff_gate_model.evaluate(diff, gate_id="quality-gate")
        self.assertEqual((gate.state, gate.decision, gate.accepted), ("blocked", "block", False))
        self.assertEqual(gate.blocked_count, diff.regressed_count)
        self.assertEqual(diff_gate_model.gate_from_mapping(gate.to_dict()).content_address, gate.content_address)
        self.assertTrue(diff_gate_audit_model.audit_gate(gate).accepted)
        query = diff_gate_query_model.query_gate(gate, resources=("summary", "blocked"), outcome="blocked", limit=2)
        self.assertEqual(query.returned_count, 2)
        self.assertTrue(diff_gate_query_audit_model.audit_query(query).accepted)

    def test_quality_diff_gate_runtime_persists_blocked_closure_and_rejects_tamper(self) -> None:
        profile = self._profile()
        left = quality_model.build_quality(profile, policy=quality_model.build_policy(policy_id="quality-gate-runtime-left"), result_id="quality-gate-runtime-left")
        right = quality_model.build_quality(profile, policy=quality_model.build_policy(policy_id="quality-gate-runtime-right", max_distinct_values=1), result_id="quality-gate-runtime-right")
        diff = diff_model.build_diff(left, right, diff_id="quality-gate-runtime-diff")
        runtime = diff_gate_runtime_model.build_runtime(diff, runtime_id="quality-gate-runtime", resources=("summary", "findings"), limit=1000)
        self.assertEqual((runtime.gate.decision, runtime.state, runtime.release_ready, runtime.query_truncated), ("block", "incomplete", False, False))
        runtime_audit = diff_gate_runtime_audit_model.audit_runtime(runtime)
        self.assertEqual((runtime_audit.check_count, runtime_audit.passed_count, runtime_audit.accepted), (19, 19, True))
        self.assertEqual(diff_gate_runtime_model.runtime_from_mapping(runtime.to_dict()).content_address, runtime.content_address)
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "gate-runtime"
            diff_gate_runtime_model.persist_runtime(runtime, destination)
            self.assertEqual(tuple(sorted(path.name for path in destination.iterdir())), tuple(sorted(diff_gate_runtime_model.FILES)))
            self.assertEqual(diff_gate_runtime_model.load_runtime(destination).content_address, runtime.content_address)
            altered = json.loads((destination / "gate.json").read_text(encoding="utf-8"))
            altered["blocked_count"] += 1
            (destination / "gate.json").write_text(json.dumps(altered), encoding="utf-8")
            with self.assertRaises(ValidationError):
                diff_gate_runtime_model.load_runtime(destination)

    def test_quality_diff_gate_remediation_replays_required_actions(self) -> None:
        profile = self._profile()
        left = quality_model.build_quality(profile, policy=quality_model.build_policy(policy_id="quality-remediation-left"), result_id="quality-remediation-left")
        right = quality_model.build_quality(profile, policy=quality_model.build_policy(policy_id="quality-remediation-right", max_distinct_values=1), result_id="quality-remediation-right")
        diff = diff_model.build_diff(left, right, diff_id="quality-remediation-diff")
        gate = diff_gate_model.evaluate(diff, gate_id="quality-remediation-gate")
        plan = diff_gate_remediation_model.build_plan(gate, plan_id="quality-remediation-plan")
        self.assertEqual((plan.state, plan.decision, plan.accepted), ("blocked", "block", False))
        self.assertGreater(plan.required_action_count, 0)
        self.assertTrue(all(item.required for item in plan.actions if item.outcome != "safe"))
        self.assertTrue(all(item.action == "none" for item in plan.actions if item.outcome == "safe"))
        self.assertEqual(diff_gate_remediation_model.plan_from_mapping(plan.to_dict()).content_address, plan.content_address)
        self.assertEqual(diff_gate_remediation_model.capabilities()["action_kinds"], diff_gate_remediation_model.ACTION_KINDS)
        audit = diff_gate_remediation_audit_model.audit_plan(plan)
        self.assertEqual((audit.check_count, audit.passed_count, audit.accepted), (18, 18, True))
        query = diff_gate_remediation_query_model.query_plan(plan, resources=("summary", "required", "blocked", "critical"), required_only=True, limit=25)
        self.assertGreater(query.returned_count, 0)
        query_audit = diff_gate_remediation_query_audit_model.audit_query(query)
        self.assertEqual((query_audit.check_count, query_audit.passed_count, query_audit.accepted), (12, 12, True))

    def test_quality_diff_gate_remediation_runtime_persists_blocked_closure_and_rejects_tamper(self) -> None:
        profile = self._profile()
        left = quality_model.build_quality(profile, policy=quality_model.build_policy(policy_id="quality-remediation-runtime-left"), result_id="quality-remediation-runtime-left")
        right = quality_model.build_quality(profile, policy=quality_model.build_policy(policy_id="quality-remediation-runtime-right", max_distinct_values=1), result_id="quality-remediation-runtime-right")
        diff = diff_model.build_diff(left, right, diff_id="quality-remediation-runtime-diff")
        gate = diff_gate_model.evaluate(diff, gate_id="quality-remediation-runtime-gate")
        runtime = diff_gate_remediation_runtime_model.build_runtime(gate, runtime_id="quality-remediation-runtime", resources=("summary", "blocked"), limit=100)
        self.assertEqual((runtime.state, runtime.release_ready, runtime.query_truncated), ("complete", False, False))
        runtime_audit = diff_gate_remediation_runtime_audit_model.audit_runtime(runtime)
        self.assertEqual((runtime_audit.check_count, runtime_audit.passed_count, runtime_audit.accepted), (16, 16, True))
        self.assertEqual(diff_gate_remediation_runtime_model.runtime_from_mapping(runtime.to_dict()).content_address, runtime.content_address)
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "remediation-runtime"
            diff_gate_remediation_runtime_model.persist_runtime(runtime, destination)
            self.assertEqual(tuple(sorted(path.name for path in destination.iterdir())), tuple(sorted(diff_gate_remediation_runtime_model.FILES)))
            self.assertEqual(diff_gate_remediation_runtime_model.load_runtime(destination).content_address, runtime.content_address)
            altered = json.loads((destination / "plan.json").read_text(encoding="utf-8"))
            altered["required_action_count"] += 1
            (destination / "plan.json").write_text(json.dumps(altered), encoding="utf-8")
            with self.assertRaises(ValidationError):
                diff_gate_remediation_runtime_model.load_runtime(destination)
        runtime = diff_gate_remediation_runtime_model.build_runtime(gate, resources=("summary", "required", "blocked", "critical"), limit=25)
        self.assertEqual((runtime.state, runtime.release_ready, runtime.query_truncated), ("complete", False, False))
        runtime_audit = diff_gate_remediation_runtime_audit_model.audit_runtime(runtime)
        self.assertEqual((runtime_audit.check_count, runtime_audit.passed_count, runtime_audit.accepted), (16, 16, True))
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "remediation-runtime"
            diff_gate_remediation_runtime_model.persist_runtime(runtime, destination)
            self.assertEqual(tuple(sorted(path.name for path in destination.iterdir())), tuple(sorted(diff_gate_remediation_runtime_model.FILES)))
            self.assertEqual(diff_gate_remediation_runtime_model.load_runtime(destination).content_address, runtime.content_address)

    def test_quality_diff_gate_remediation_resolution_replays_pending_and_closed_dispositions(self) -> None:
        profile = self._profile()
        left = quality_model.build_quality(profile, policy=quality_model.build_policy(policy_id="quality-resolution-left"), result_id="quality-resolution-left")
        right = quality_model.build_quality(profile, policy=quality_model.build_policy(policy_id="quality-resolution-right", max_distinct_values=1), result_id="quality-resolution-right")
        diff = diff_model.build_diff(left, right, diff_id="quality-resolution-diff")
        gate = diff_gate_model.evaluate(diff, gate_id="quality-resolution-gate")
        plan = diff_gate_remediation_model.build_plan(gate, plan_id="quality-resolution-plan")
        pending = diff_gate_remediation_resolution_model.build_resolution(plan, resolution_id="quality-resolution-pending")
        self.assertEqual((pending.state, pending.decision, pending.release_ready), ("review", "hold", False))
        self.assertGreater(pending.required_open_count, 0)
        self.assertEqual(diff_gate_remediation_resolution_model.resolution_from_mapping(pending.to_dict()).content_address, pending.content_address)
        pending_audit = diff_gate_remediation_resolution_audit_model.audit_resolution(pending)
        self.assertEqual((pending_audit.check_count, pending_audit.passed_count, pending_audit.accepted), (14, 14, True))
        pending_query = diff_gate_remediation_resolution_query_model.query_resolution(pending, resources=("summary", "pending", "open"), limit=100)
        self.assertTrue(diff_gate_remediation_resolution_query_audit_model.audit_query(pending_query).accepted)
        statuses = {item.content_address: "resolved" for item in plan.actions if item.required}
        closed = diff_gate_remediation_resolution_model.build_resolution(plan, resolution_id="quality-resolution-closed", statuses=statuses)
        self.assertEqual((closed.state, closed.decision, closed.release_ready, closed.required_open_count), ("clear", "promote", True, 0))

    def test_quality_diff_gate_remediation_resolution_runtime_persists_pending_closure_and_rejects_tamper(self) -> None:
        profile = self._profile()
        left = quality_model.build_quality(profile, policy=quality_model.build_policy(policy_id="quality-resolution-runtime-left"), result_id="quality-resolution-runtime-left")
        right = quality_model.build_quality(profile, policy=quality_model.build_policy(policy_id="quality-resolution-runtime-right", max_distinct_values=1), result_id="quality-resolution-runtime-right")
        diff = diff_model.build_diff(left, right, diff_id="quality-resolution-runtime-diff")
        gate = diff_gate_model.evaluate(diff, gate_id="quality-resolution-runtime-gate")
        plan = diff_gate_remediation_model.build_plan(gate, plan_id="quality-resolution-runtime-plan")
        resolution = diff_gate_remediation_resolution_model.build_resolution(plan, resolution_id="quality-resolution-runtime-resolution")
        runtime = diff_gate_remediation_resolution_runtime_model.build_runtime(resolution, runtime_id="quality-resolution-runtime", resources=("summary", "pending", "open"), limit=100)
        self.assertEqual((runtime.state, runtime.release_ready, runtime.query_truncated), ("complete", False, False))
        runtime_audit = diff_gate_remediation_resolution_runtime_audit_model.audit_runtime(runtime)
        self.assertEqual((runtime_audit.check_count, runtime_audit.passed_count, runtime_audit.accepted), (16, 16, True))
        self.assertEqual(diff_gate_remediation_resolution_runtime_model.runtime_from_mapping(runtime.to_dict()).content_address, runtime.content_address)
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "resolution-runtime"
            diff_gate_remediation_resolution_runtime_model.persist_runtime(runtime, destination)
            self.assertEqual(tuple(sorted(path.name for path in destination.iterdir())), tuple(sorted(diff_gate_remediation_resolution_runtime_model.FILES)))
            self.assertEqual(diff_gate_remediation_resolution_runtime_model.load_runtime(destination).content_address, runtime.content_address)
            altered = json.loads((destination / "resolution.json").read_text(encoding="utf-8"))
            altered["pending_count"] += 1
            (destination / "resolution.json").write_text(json.dumps(altered), encoding="utf-8")
            with self.assertRaises(ValidationError):
                diff_gate_remediation_resolution_runtime_model.load_runtime(destination)

    def test_quality_diff_gate_history_replays_ancestry_transitions_and_queries(self) -> None:
        profile = self._profile()
        left = quality_model.build_quality(profile, policy=quality_model.build_policy(policy_id="quality-history-left"), result_id="quality-history-left")
        right = quality_model.build_quality(profile, policy=quality_model.build_policy(policy_id="quality-history-right", max_distinct_values=1), result_id="quality-history-right")
        diff = diff_model.build_diff(left, right, diff_id="quality-history-diff")
        runtime = diff_gate_runtime_model.build_runtime(diff, runtime_id="quality-history-runtime", resources=("summary", "findings"), limit=1000)
        history = diff_gate_history_model.build_history(runtime, history_id="quality-history", snapshot_id="candidate-1")
        history = diff_gate_history_model.append_history(history, runtime, snapshot_id="candidate-2", expected_head=history.head_address)
        self.assertEqual(tuple(item.transition for item in history.entries), ("initial", "unchanged"))
        self.assertTrue(diff_gate_history_audit_model.audit_history(history).accepted)
        query = diff_gate_history_query_model.query_history(history, resources=("summary", "entries", "block", "unchanged"), transition="unchanged", limit=10)
        self.assertEqual((query.returned_count, query.truncated), (3, False))
        self.assertTrue(diff_gate_history_query_audit_model.audit_query(query).accepted)
        self.assertEqual(diff_gate_history_model.history_from_mapping(history.to_dict()).content_address, history.content_address)
        with self.assertRaises(ValidationError):
            diff_gate_history_model.append_history(history, runtime, snapshot_id="candidate-2")
        with self.assertRaises(ValidationError):
            diff_gate_history_model.append_history(history, runtime, snapshot_id="candidate-3", expected_head="stale:head")

    def test_quality_diff_gate_history_runtime_persists_and_replays_latest_readiness(self) -> None:
        profile = self._profile()
        left = quality_model.build_quality(profile, policy=quality_model.build_policy(policy_id="quality-history-runtime-left"), result_id="quality-history-runtime-left")
        right = quality_model.build_quality(profile, policy=quality_model.build_policy(policy_id="quality-history-runtime-right", max_distinct_values=1), result_id="quality-history-runtime-right")
        diff = diff_model.build_diff(left, right, diff_id="quality-history-runtime-diff")
        gate_runtime = diff_gate_runtime_model.build_runtime(diff, runtime_id="quality-history-runtime-gate", resources=("summary", "findings"), limit=1000)
        history = diff_gate_history_model.build_history(gate_runtime, history_id="quality-history-runtime-history", snapshot_id="blocked")
        runtime = diff_gate_history_runtime_model.build_runtime(history, resources=("summary", "entries", "latest"), limit=1000)
        self.assertEqual((runtime.accepted, runtime.release_ready, runtime.state, runtime.latest_state), (True, False, "complete", "blocked"))
        audit = diff_gate_history_runtime_audit_model.audit_runtime(runtime)
        self.assertEqual((audit.check_count, audit.passed_count, audit.accepted), (19, 19, True))
        self.assertEqual(diff_gate_history_runtime_model.runtime_from_mapping(runtime.to_dict()).content_address, runtime.content_address)
        malformed_runtime = runtime.to_dict()
        malformed_runtime["history_address"] = "glio-noncode-download-quality-diff-gate-history:not-a-digest"
        with self.assertRaises(ValidationError):
            diff_gate_history_runtime_model.runtime_from_mapping(malformed_runtime)
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "history-runtime"
            diff_gate_history_runtime_model.persist_runtime(runtime, destination)
            self.assertEqual(tuple(sorted(path.name for path in destination.iterdir())), tuple(sorted(diff_gate_history_runtime_model.FILES)))
            self.assertEqual(diff_gate_history_runtime_model.load_runtime(destination).content_address, runtime.content_address)
            altered = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
            altered["artifact_addresses"] = list(reversed(altered["artifact_addresses"]))
            (destination / "manifest.json").write_text(json.dumps(altered), encoding="utf-8")
            with self.assertRaises(ValidationError):
                diff_gate_history_runtime_model.load_runtime(destination)

    def test_quality_diff_gate_replays_category_threshold_reasons(self) -> None:
        profile = self._profile()
        left = quality_model.build_quality(
            profile,
            policy=quality_model.build_policy(policy_id="quality-gate-threshold-left"),
            result_id="quality-gate-threshold-left",
        )
        right = quality_model.build_quality(
            profile,
            policy=quality_model.build_policy(
                policy_id="quality-gate-threshold-right", max_distinct_values=1
            ),
            result_id="quality-gate-threshold-right",
        )
        diff = diff_model.build_diff(left, right, diff_id="quality-gate-threshold-diff")
        provisional = diff_gate_model.DownloadedDataQualityDiffGatePolicy(
            "quality-gate-threshold-policy",
            ("improved", "changed", "unchanged", "added", "removed"),
            diff_gate_model.MAX_FINDINGS,
            0,
            0,
            0,
            True,
            True,
            True,
            diff_gate_model.POLICY_PREFIX + ":pending",
        )
        policy = diff_gate_model.DownloadedDataQualityDiffGatePolicy(
            provisional.policy_id,
            provisional.allowed_directions,
            provisional.maximum_regressed,
            provisional.maximum_changed,
            provisional.maximum_added,
            provisional.maximum_removed,
            provisional.require_diff_audit,
            provisional.require_query_audit,
            provisional.require_complete_query,
            diff_gate_model.address_policy(provisional),
        )
        gate = diff_gate_model.evaluate(diff, policy=policy, gate_id="quality-gate-threshold")
        self.assertTrue(
            any(
                "maximum_changed_exceeded" in item.reason_codes
                for item in gate.findings
                if item.change == "changed"
            )
        )
        self.assertTrue(diff_gate_audit_model.audit_gate(gate).accepted)

    def test_quality_policy_rejects_noncanonical_content_addresses(self) -> None:
        policy = quality_model.build_policy(policy_id="quality-address-boundary")
        altered = policy.to_dict()
        altered["content_address"] = quality_model.POLICY_PREFIX + ":short"
        with self.assertRaisesRegex(ValidationError, "canonical content address"):
            quality_model.policy_from_mapping(altered)

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
            gate_path = root / "diff-gate.json"
            self.assertEqual(main(["downloaded-data-quality-diff-gate", str(diff_path), "--format", "json", "--output", str(gate_path)]), 2)
            self.assertEqual(main(["downloaded-data-quality-diff-gate-audit", str(gate_path), "--format", "json", "--output", str(root / "diff-gate-audit.json")]), 0)
            self.assertEqual(main(["downloaded-data-quality-diff-gate-remediation", str(gate_path), "--format", "json", "--output", str(root / "diff-gate-remediation.json")]), 2)
            self.assertEqual(main(["downloaded-data-quality-diff-gate-remediation-audit", str(root / "diff-gate-remediation.json"), "--format", "json", "--output", str(root / "diff-gate-remediation-audit.json")]), 0)
            self.assertEqual(main(["downloaded-data-quality-diff-gate-remediation-query", str(root / "diff-gate-remediation.json"), "--resource", "required", "--required-only", "--limit", "25", "--format", "json", "--output", str(root / "diff-gate-remediation-query.json")]), 0)
            self.assertEqual(main(["downloaded-data-quality-diff-gate-remediation-query-audit", str(root / "diff-gate-remediation-query.json"), "--format", "json", "--output", str(root / "diff-gate-remediation-query-audit.json")]), 0)
            remediation_runtime_path = root / "diff-gate-remediation-runtime"
            self.assertEqual(main(["downloaded-data-quality-diff-gate-remediation-runtime", str(gate_path), "--destination", str(remediation_runtime_path), "--overwrite", "--resource", "summary", "--resource", "blocked", "--limit", "100", "--format", "summary", "--output", str(root / "diff-gate-remediation-runtime-summary.json")]), 2)
            self.assertEqual(main(["downloaded-data-quality-diff-gate-remediation-runtime-audit", str(remediation_runtime_path), "--format", "json", "--output", str(root / "diff-gate-remediation-runtime-audit.json")]), 0)
            self.assertEqual(tuple(sorted(path.name for path in remediation_runtime_path.iterdir())), tuple(sorted(diff_gate_remediation_runtime_model.FILES)))
            remediation_runtime_path = root / "diff-gate-remediation-runtime"
            self.assertEqual(main(["downloaded-data-quality-diff-gate-remediation-runtime", str(gate_path), "--destination", str(remediation_runtime_path), "--overwrite", "--resource", "summary", "--resource", "required", "--resource", "blocked", "--resource", "critical", "--limit", "25", "--format", "summary", "--output", str(root / "diff-gate-remediation-runtime-summary.json")]), 2)
            self.assertEqual(main(["downloaded-data-quality-diff-gate-remediation-runtime-audit", str(remediation_runtime_path), "--format", "json", "--output", str(root / "diff-gate-remediation-runtime-audit.json")]), 0)
            resolution_path = root / "diff-gate-remediation-resolution.json"
            self.assertEqual(main(["downloaded-data-quality-diff-gate-remediation-resolution", str(root / "diff-gate-remediation.json"), "--format", "json", "--output", str(resolution_path)]), 2)
            self.assertEqual(main(["downloaded-data-quality-diff-gate-remediation-resolution-audit", str(resolution_path), "--format", "json", "--output", str(root / "diff-gate-remediation-resolution-audit.json")]), 0)
            self.assertEqual(main(["downloaded-data-quality-diff-gate-remediation-resolution-query", str(resolution_path), "--resource", "summary", "--resource", "pending", "--resource", "open", "--limit", "100", "--format", "json", "--output", str(root / "diff-gate-remediation-resolution-query.json")]), 0)
            self.assertEqual(main(["downloaded-data-quality-diff-gate-remediation-resolution-query-audit", str(root / "diff-gate-remediation-resolution-query.json"), "--format", "json", "--output", str(root / "diff-gate-remediation-resolution-query-audit.json")]), 0)
            resolution_runtime_path = root / "diff-gate-remediation-resolution-runtime"
            self.assertEqual(main(["downloaded-data-quality-diff-gate-remediation-resolution-runtime", str(resolution_path), "--destination", str(resolution_runtime_path), "--overwrite", "--resource", "summary", "--resource", "pending", "--resource", "open", "--limit", "100", "--format", "summary", "--output", str(root / "diff-gate-remediation-resolution-runtime-summary.json")]), 2)
            self.assertEqual(main(["downloaded-data-quality-diff-gate-remediation-resolution-runtime-audit", str(resolution_runtime_path), "--format", "json", "--output", str(root / "diff-gate-remediation-resolution-runtime-audit.json")]), 0)
            self.assertEqual(tuple(sorted(path.name for path in resolution_runtime_path.iterdir())), tuple(sorted(diff_gate_remediation_resolution_runtime_model.FILES)))
            self.assertEqual(main(["downloaded-data-quality-diff-gate-query", str(gate_path), "--resource", "blocked", "--outcome", "blocked", "--limit", "2", "--format", "json", "--output", str(root / "diff-gate-query.json")]), 0)
            self.assertEqual(main(["downloaded-data-quality-diff-gate-query-audit", str(root / "diff-gate-query.json"), "--format", "json", "--output", str(root / "diff-gate-query-audit.json")]), 0)
            diff_gate_runtime_path = root / "diff-gate-runtime"
            self.assertEqual(main(["downloaded-data-quality-diff-gate-runtime", str(diff_path), "--destination", str(diff_gate_runtime_path), "--overwrite", "--resource", "summary", "--resource", "findings", "--limit", "1000", "--format", "summary", "--output", str(root / "diff-gate-runtime-summary.json")]), 2)
            self.assertEqual(main(["downloaded-data-quality-diff-gate-runtime-audit", str(diff_gate_runtime_path), "--format", "json", "--output", str(root / "diff-gate-runtime-audit.json")]), 0)
            self.assertEqual(tuple(sorted(path.name for path in diff_gate_runtime_path.iterdir())), tuple(sorted(diff_gate_runtime_model.FILES)))
            history_path = root / "diff-gate-history.json"
            self.assertEqual(main(["downloaded-data-quality-diff-gate-history", str(diff_gate_runtime_path), "--snapshot-id", "candidate-1", "--format", "json", "--output", str(history_path)]), 0)
            history_two_path = root / "diff-gate-history-two.json"
            self.assertEqual(main(["downloaded-data-quality-diff-gate-history", str(diff_gate_runtime_path), "--history", str(history_path), "--snapshot-id", "candidate-2", "--format", "json", "--output", str(history_two_path)]), 0)
            self.assertEqual(main(["downloaded-data-quality-diff-gate-history-audit", str(history_two_path), "--format", "json", "--output", str(root / "diff-gate-history-audit.json")]), 0)
            self.assertEqual(main(["downloaded-data-quality-diff-gate-history-query", str(history_two_path), "--resource", "entries", "--resource", "unchanged", "--transition", "unchanged", "--limit", "10", "--format", "json", "--output", str(root / "diff-gate-history-query.json")]), 0)
            self.assertEqual(main(["downloaded-data-quality-diff-gate-history-query-audit", str(root / "diff-gate-history-query.json"), "--format", "json", "--output", str(root / "diff-gate-history-query-audit.json")]), 0)
            history_runtime_path = root / "diff-gate-history-runtime"
            self.assertEqual(main(["downloaded-data-quality-diff-gate-history-runtime", str(history_two_path), "--destination", str(history_runtime_path), "--overwrite", "--resource", "summary", "--resource", "entries", "--resource", "latest", "--limit", "1000", "--format", "summary", "--output", str(root / "diff-gate-history-runtime-summary.json")]), 2)
            self.assertEqual(main(["downloaded-data-quality-diff-gate-history-runtime-audit", str(history_runtime_path), "--format", "json", "--output", str(root / "diff-gate-history-runtime-audit.json")]), 0)
            self.assertEqual(tuple(sorted(path.name for path in history_runtime_path.iterdir())), tuple(sorted(diff_gate_history_runtime_model.FILES)))

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
                api_gate = json.loads(urlopen(diff_base + "/gate?" + urlencode({"input": str(diff_path), "format": "json"}), timeout=10).read().decode())
                self.assertEqual(api_gate["decision"], "block")
                self.assertGreater(api_gate["blocked_count"], 0)
                api_remediation = json.loads(urlopen(diff_base + "/gate/remediation?" + urlencode({"input": str(gate_path)}), timeout=10).read().decode())
                self.assertEqual((api_remediation["state"], api_remediation["decision"], api_remediation["accepted"]), ("blocked", "block", False))
                api_remediation_audit = json.loads(urlopen(diff_base + "/gate/remediation/audit?" + urlencode({"input": str(root / "diff-gate-remediation.json")}), timeout=10).read().decode())
                self.assertTrue(api_remediation_audit["accepted"])
                api_remediation_query = json.loads(urlopen(diff_base + "/gate/remediation/query?" + urlencode({"input": str(root / "diff-gate-remediation.json"), "resource": "required", "required_only": "true", "limit": "25"}), timeout=10).read().decode())
                self.assertGreater(api_remediation_query["returned_count"], 0)
                api_remediation_query_audit = json.loads(urlopen(diff_base + "/gate/remediation/query-audit?" + urlencode({"input": str(root / "diff-gate-remediation-query.json")}), timeout=10).read().decode())
                self.assertTrue(api_remediation_query_audit["accepted"])
                api_remediation_runtime = json.loads(urlopen(diff_base + "/gate/remediation/runtime?" + urlencode({"input": str(gate_path), "resource": ["summary", "required", "blocked", "critical"], "limit": "25", "destination": str(root / "api-remediation-runtime"), "overwrite": "true"}, doseq=True), timeout=10).read().decode())
                self.assertEqual((api_remediation_runtime["state"], api_remediation_runtime["release_ready"]), ("complete", False))
                api_remediation_runtime_audit = json.loads(urlopen(diff_base + "/gate/remediation/runtime/audit?" + urlencode({"input": str(remediation_runtime_path)}), timeout=10).read().decode())
                self.assertTrue(api_remediation_runtime_audit["accepted"])
                api_resolution = json.loads(urlopen(diff_base + "/gate/remediation/resolution?" + urlencode({"input": str(root / "diff-gate-remediation.json")}), timeout=10).read().decode())
                self.assertEqual((api_resolution["state"], api_resolution["decision"], api_resolution["release_ready"]), ("review", "hold", False))
                api_resolution_audit = json.loads(urlopen(diff_base + "/gate/remediation/resolution/audit?" + urlencode({"input": str(resolution_path)}), timeout=10).read().decode())
                self.assertTrue(api_resolution_audit["accepted"])
                api_resolution_query = json.loads(urlopen(diff_base + "/gate/remediation/resolution/query?" + urlencode({"input": str(resolution_path), "resource": ["summary", "pending", "open"], "limit": "100"}, doseq=True), timeout=10).read().decode())
                self.assertGreater(api_resolution_query["returned_count"], 0)
                api_resolution_query_audit = json.loads(urlopen(diff_base + "/gate/remediation/resolution/query-audit?" + urlencode({"input": str(root / "diff-gate-remediation-resolution-query.json")}), timeout=10).read().decode())
                self.assertTrue(api_resolution_query_audit["accepted"])
                api_resolution_runtime = json.loads(urlopen(diff_base + "/gate/remediation/resolution/runtime?" + urlencode({"input": str(resolution_path), "resource": ["summary", "pending", "open"], "limit": "100", "destination": str(root / "api-resolution-runtime"), "overwrite": "true"}, doseq=True), timeout=10).read().decode())
                self.assertEqual((api_resolution_runtime["state"], api_resolution_runtime["release_ready"]), ("complete", False))
                api_resolution_runtime_audit = json.loads(urlopen(diff_base + "/gate/remediation/resolution/runtime/audit?" + urlencode({"input": str(resolution_runtime_path)}), timeout=10).read().decode())
                self.assertTrue(api_resolution_runtime_audit["accepted"])
                api_remediation_runtime = json.loads(urlopen(diff_base + "/gate/remediation/runtime?" + urlencode({"input": str(gate_path), "resource": ["summary", "blocked"], "limit": "100"}, doseq=True), timeout=10).read().decode())
                self.assertEqual((api_remediation_runtime["state"], api_remediation_runtime["release_ready"], api_remediation_runtime["query_truncated"]), ("complete", False, False))
                api_remediation_runtime_audit = json.loads(urlopen(diff_base + "/gate/remediation/runtime/audit?" + urlencode({"input": str(remediation_runtime_path)}), timeout=10).read().decode())
                self.assertTrue(api_remediation_runtime_audit["accepted"])
                api_gate_query = json.loads(urlopen(diff_base + "/gate/query?" + urlencode({"input": str(gate_path), "resource": "blocked", "outcome": "blocked", "limit": "2"}), timeout=10).read().decode())
                self.assertEqual(api_gate_query["returned_count"], 2)
                api_gate_audit = json.loads(urlopen(diff_base + "/gate/audit?" + urlencode({"input": str(gate_path)}), timeout=10).read().decode())
                self.assertTrue(api_gate_audit["accepted"])
                api_gate_runtime = json.loads(urlopen(diff_base + "/gate/runtime?" + urlencode({"input": str(diff_path), "resource": ["summary", "findings"], "limit": "1000", "destination": str(root / "api-gate-runtime"), "overwrite": "true"}, doseq=True), timeout=10).read().decode())
                self.assertEqual((api_gate_runtime["decision"], api_gate_runtime["gate_state"], api_gate_runtime["state"], api_gate_runtime["query_truncated"]), ("block", "blocked", "incomplete", False))
                api_gate_runtime_audit = json.loads(urlopen(diff_base + "/gate/runtime/audit?" + urlencode({"input": str(diff_gate_runtime_path)}), timeout=10).read().decode())
                self.assertTrue(api_gate_runtime_audit["accepted"])
                api_history = json.loads(urlopen(diff_base + "/gate/history?" + urlencode({"input": str(diff_gate_runtime_path), "snapshot_id": "candidate-api-1"}), timeout=10).read().decode())
                self.assertEqual((api_history["entry_count"], api_history["state"]), (1, "blocked"))
                api_history_audit = json.loads(urlopen(diff_base + "/gate/history/audit?" + urlencode({"input": str(history_two_path)}), timeout=10).read().decode())
                self.assertTrue(api_history_audit["accepted"])
                api_history_query = json.loads(urlopen(diff_base + "/gate/history/query?" + urlencode({"input": str(history_two_path), "resource": ["entries", "unchanged"], "transition": "unchanged", "limit": "10"}, doseq=True), timeout=10).read().decode())
                self.assertEqual(api_history_query["returned_count"], 2)
                api_history_query_audit = json.loads(urlopen(diff_base + "/gate/history/query-audit?" + urlencode({"input": str(root / "diff-gate-history-query.json")}), timeout=10).read().decode())
                self.assertTrue(api_history_query_audit["accepted"])
                api_history_runtime = json.loads(urlopen(diff_base + "/gate/history/runtime?" + urlencode({"input": str(history_two_path), "resource": ["summary", "entries", "latest"], "limit": "1000", "destination": str(root / "api-history-runtime"), "overwrite": "true"}, doseq=True), timeout=10).read().decode())
                self.assertEqual((api_history_runtime["release_ready"], api_history_runtime["state"], api_history_runtime["latest_state"]), (False, "complete", "blocked"))
                api_history_runtime_audit = json.loads(urlopen(diff_base + "/gate/history/runtime/audit?" + urlencode({"input": str(history_runtime_path)}), timeout=10).read().decode())
                self.assertTrue(api_history_runtime_audit["accepted"])
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
