"""Deep contracts for the multi-history assurance observatory boundary."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from examples import release_registry_federation_gate_review_decision_ledger_assurance_history_demo as history_demo
from examples import release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_verification_query_demo as verification_query_demo
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance as assurance
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history as history
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory as observatory
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_bytes, canonical_json
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance import AssuranceFixture


class ObservatoryFixture(AssuranceFixture):
    """Build independent current-format histories from persisted-download gates."""

    def setUp(self) -> None:
        super().setUp()
        self.ready_gate = assurance.build_assurance_gate(self.ready_ledger, gate_id="gate:observatory-ready")
        self.held_gate = assurance.build_assurance_gate(self.held_ledger, gate_id="gate:observatory-held")
        self.blocked_gate = assurance.build_assurance_gate(self.blocked_ledger, gate_id="gate:observatory-blocked")

    def make_history(self, history_id: str, gates, snapshots) -> history.AssuranceHistory:
        return history.build_history(tuple(gates), history_id=history_id, snapshot_ids=tuple(snapshots))

    def make_observatory(self, histories=None, member_ids=None) -> observatory.AssuranceHistoryObservatory:
        histories = histories or (
            self.make_history("history:one", (self.ready_gate,), ("one:0",)),
            self.make_history("history:two", (self.ready_gate,), ("two:0",)),
        )
        resolved_member_ids = tuple(member_ids) if member_ids is not None else tuple(f"source:{index}" for index in range(len(histories)))
        return observatory.build_observatory(tuple(histories), observatory_id="observatory:test", member_ids=resolved_member_ids)

    @staticmethod
    def capture_cli(argv):
        output = StringIO()
        with redirect_stdout(output):
            status = main(argv)
        return status, output.getvalue()

    @staticmethod
    def write_history(value: history.AssuranceHistory, root: Path, name: str) -> Path:
        target = root / name
        history.write_history(value, target)
        return target

    @staticmethod
    def write_observatory(value: observatory.AssuranceHistoryObservatory, root: Path, name: str = "observatory") -> Path:
        target = root / name
        observatory.write_observatory(value, target)
        return target

    def assert_public(self, value) -> None:
        payload = value.to_dict() if hasattr(value, "to_dict") else value
        text = canonical_json(payload)
        self.assertNotIn("C:\\", text)
        self.assertNotIn("/Users/", text)
        forbidden = {"agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "token", "user"}

        def walk(node):
            if isinstance(node, dict):
                for key, item in node.items():
                    self.assertNotIn(key.lower(), forbidden)
                    walk(item)
            elif isinstance(node, (list, tuple)):
                for item in node:
                    walk(item)

        walk(payload)

    def server(self):
        server = create_server("127.0.0.1", 0)
        import threading

        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread


class ObservatoryBuildTests(ObservatoryFixture):
    def test_empty_observatory_is_explicit(self):
        value = observatory.build_observatory((), observatory_id="observatory:empty")
        self.assertEqual(value.state, "empty")
        self.assertFalse(value.accepted)
        self.assertFalse(value.release_ready)
        self.assertEqual(value.member_count, 0)
        self.assertEqual(value.entry_count, 0)
        self.assertTrue(value.content_address.startswith(observatory.OBSERVATORY_PREFIX + ":"))

    def test_ready_observatory_conserves_member_and_history_totals(self):
        value = self.make_observatory()
        self.assertEqual(value.state, "ready")
        self.assertTrue(value.accepted)
        self.assertTrue(value.release_ready)
        self.assertEqual(value.member_count, 2)
        self.assertEqual(value.entry_count, 2)
        self.assertEqual(value.ready_member_count, 2)
        self.assertEqual(value.promote_count, 2)
        self.assertEqual(value.hold_count, 0)
        self.assertEqual(value.regressed_count, 0)

    def test_hold_and_block_states_are_fail_closed(self):
        held = self.make_observatory((self.make_history("history:held", (self.held_gate,), ("held:0",)),))
        blocked = self.make_observatory((self.make_history("history:blocked", (self.blocked_gate,), ("blocked:0",)),))
        self.assertEqual(held.state, "held")
        self.assertFalse(held.release_ready)
        self.assertEqual(blocked.state, "blocked")
        self.assertFalse(blocked.release_ready)

    def test_mixed_state_retains_source_postures(self):
        empty = self.make_history("history:empty", (), ())
        ready = self.make_history("history:ready", (self.ready_gate,), ("ready:0",))
        value = self.make_observatory((empty, ready))
        self.assertEqual(value.state, "mixed")
        self.assertEqual(value.empty_member_count, 1)
        self.assertEqual(value.mixed_member_count, 0)
        self.assertFalse(value.release_ready)

    def test_repeated_build_is_deterministic(self):
        first = self.make_observatory()
        second = self.make_observatory()
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(observatory.observatory_json(first), observatory.observatory_json(second))
        self.assertEqual(observatory.metrics_json(first), observatory.metrics_json(second))

    def test_member_order_is_canonical(self):
        first = self.make_history("history:one", (self.ready_gate,), ("one:0",))
        second = self.make_history("history:two", (self.ready_gate,), ("two:0",))
        value = observatory.build_observatory((second, first), observatory_id="observatory:test", member_ids=("source:b", "source:a"))
        self.assertEqual(tuple(item.member_id for item in value.members), ("source:a", "source:b"))

    def test_custom_member_identity_changes_only_observatory_graph(self):
        value = self.make_observatory()
        other = observatory.build_observatory((self.make_history("history:one", (self.ready_gate,), ("one:0",)), self.make_history("history:two", (self.ready_gate,), ("two:0",))), observatory_id="observatory:test", member_ids=("source:x", "source:y"))
        self.assertNotEqual(value.content_address, other.content_address)
        self.assertEqual(tuple(item.history_address for item in value.members), tuple(item.history_address for item in other.members))

    def test_member_projection_replays_history_counters(self):
        value = self.make_observatory((self.make_history("history:one", (self.ready_gate, self.held_gate), ("one:0", "one:1")), self.make_history("history:two", (self.ready_gate,), ("two:0",))))
        first, second = value.members
        self.assertEqual(first.entry_count, 2)
        self.assertEqual(first.initial_count, 1)
        self.assertEqual(first.regressed_count, 1)
        self.assertEqual(first.latest_transition, "regressed")
        self.assertEqual(second.latest_transition, "initial")
        self.assertEqual(value.warning_check_count, sum(item.warning_check_count for item in value.members))

    def test_mapping_round_trip_is_typed(self):
        value = self.make_observatory()
        mapped = observatory.observatory_from_mapping(value.to_dict() | {"members": [item.to_dict() for item in value.members]})
        self.assertEqual(mapped.to_dict(), value.to_dict())
        self.assertEqual(observatory.member_from_mapping(value.members[0].to_dict()).to_dict(), value.members[0].to_dict())

    def test_mapping_rejects_unknown_fields(self):
        value = self.make_observatory()
        with self.assertRaises(ValidationError):
            observatory.observatory_from_mapping(value.to_dict() | {"unexpected": True})
        with self.assertRaises(ValidationError):
            observatory.member_from_mapping(value.members[0].to_dict() | {"unexpected": True})

    def test_public_projection_is_recursive(self):
        value = self.make_observatory()
        self.assert_public(value)
        self.assert_public(value.members[0])
        self.assert_public(observatory.capabilities())

    def test_typed_boundary_rejects_plain_mappings(self):
        with self.assertRaises(ValidationError):
            observatory.verify_observatory({})
        with self.assertRaises(ValidationError):
            observatory.address_observatory({})
        with self.assertRaises(ValidationError):
            observatory.build_observatory(({},))

    def test_verification_has_eight_independent_checks(self):
        value = self.make_observatory()
        verified = observatory.build_verification(value)
        self.assertEqual(verified.check_count, 8)
        self.assertEqual(verified.passed_count, 8)
        self.assertEqual(verified.warning_count, 0)
        self.assertEqual(verified.blocker_count, 0)
        self.assertEqual(verified.state, "promote")
        self.assertTrue(verified.release_ready)
        self.assertTrue(all(check.passed for check in verified.checks))
        self.assertTrue(all(check.content_address.startswith(observatory.CHECK_PREFIX + ":") for check in verified.checks))

    def test_verification_tracks_hold_and_block_terminal_states(self):
        held = self.make_observatory((self.make_history("history:held", (self.held_gate,), ("held:0",)),), ("source:held",))
        blocked = self.make_observatory((self.make_history("history:blocked", (self.blocked_gate,), ("blocked:0",)),), ("source:blocked",))
        self.assertEqual(observatory.build_verification(held).state, "hold")
        self.assertEqual(observatory.build_verification(blocked).state, "block")

    def test_metrics_are_derived_not_free_text(self):
        value = self.make_observatory((self.make_history("history:one", (self.ready_gate, self.held_gate), ("one:0", "one:1")), self.make_history("history:two", (self.ready_gate,), ("two:0",))))
        metrics = observatory.metrics_document(value)
        self.assertEqual(metrics["member_state_counts"]["ready"], 1)
        self.assertEqual(metrics["transition_counts"]["regressed"], 1)
        self.assertEqual(metrics["quality_totals"]["finding_count"], value.finding_count)
        self.assertEqual(metrics["release_ready_member_count"], 1)

    def test_schema_contracts_are_closed_and_bounded(self):
        self.assertFalse(observatory.observatory_schema()["additionalProperties"])
        self.assertFalse(observatory.member_schema()["additionalProperties"])
        self.assertFalse(observatory.verification_schema()["additionalProperties"])
        self.assertFalse(observatory.metrics_schema()["additionalProperties"])
        self.assertEqual(observatory.diff_schema()["properties"]["items"]["maxItems"], observatory.MAX_MEMBERS * 2)
        self.assertFalse(observatory.query_schema()["additionalProperties"])
        self.assertFalse(observatory.diff_query_schema()["additionalProperties"])

    def test_capabilities_describe_exact_package_and_resources(self):
        value = observatory.capabilities()
        self.assertEqual(tuple(value["package_files"]), observatory.FILES)
        self.assertEqual(tuple(value["diff_package_files"]), observatory.DIFF_FILES)
        self.assertEqual(tuple(value["resources"]["observatory"]), observatory.ObservatoryQuery.RESOURCES)
        self.assertIn("independent eight-check verification", value["features"])
        self.assert_public(value)


class ObservatoryDiffTests(ObservatoryFixture):
    def test_identical_diff_is_unchanged(self):
        value = self.make_observatory()
        diff = observatory.build_diff(value, value)
        self.assertEqual(diff.state, "unchanged")
        self.assertEqual(diff.item_count, 2)
        self.assertEqual(diff.unchanged_count, 2)
        self.assertEqual(diff.improved_count, 0)
        self.assertEqual(diff.regressed_count, 0)
        self.assertEqual(observatory.address_diff(diff), diff.content_address)

    def test_added_and_removed_members_are_addressed(self):
        baseline = self.make_observatory((self.make_history("history:one", (self.ready_gate,), ("one:0",)),), ("source:one",))
        candidate = self.make_observatory((self.make_history("history:one", (self.ready_gate,), ("one:0",)), self.make_history("history:two", (self.ready_gate,), ("two:0",))), ("source:one", "source:two"))
        diff = observatory.build_diff(baseline, candidate)
        self.assertEqual(diff.added_count, 1)
        self.assertEqual(diff.items[-1].action, "added")
        self.assertEqual(diff.items[-1].direction, "improved")
        self.assertEqual(diff.state, "improved")

    def test_removed_member_is_regression(self):
        baseline = self.make_observatory((self.make_history("history:one", (self.ready_gate,), ("one:0",)), self.make_history("history:two", (self.ready_gate,), ("two:0",))), ("source:one", "source:two"))
        candidate = self.make_observatory((self.make_history("history:one", (self.ready_gate,), ("one:0",)),), ("source:one",))
        diff = observatory.build_diff(baseline, candidate)
        removed = next(item for item in diff.items if item.action == "removed")
        self.assertEqual(removed.key, "source:two")
        self.assertEqual(removed.direction, "regressed")
        self.assertEqual(diff.state, "regressed")

    def test_changed_member_classifies_regression(self):
        baseline = self.make_observatory((self.make_history("history:one", (self.ready_gate,), ("one:0",)),), ("source:one",))
        candidate = self.make_observatory((self.make_history("history:one", (self.held_gate,), ("one:0",)),), ("source:one",))
        diff = observatory.build_diff(baseline, candidate)
        self.assertEqual(diff.changed_count, 1)
        self.assertEqual(diff.regressed_count, 1)
        self.assertEqual(diff.state, "regressed")

    def test_changed_equal_quality_is_mixed(self):
        baseline = self.make_observatory((self.make_history("history:one", (self.ready_gate,), ("one:0",)),), ("source:one",))
        candidate = self.make_observatory((self.make_history("history:one", (self.ready_gate,), ("one:1",)),), ("source:one",))
        diff = observatory.build_diff(baseline, candidate)
        self.assertEqual(diff.changed_count, 1)
        self.assertEqual(diff.mixed_count, 1)
        self.assertEqual(diff.state, "unchanged")
        self.assertEqual(diff.items[0].direction, "mixed")

    def test_diff_mapping_round_trip_and_independent_verification(self):
        baseline = self.make_observatory()
        candidate = self.make_observatory((self.make_history("history:one", (self.ready_gate,), ("one:0",)), self.make_history("history:two", (self.held_gate,), ("two:0",))), ("source:one", "source:two"))
        value = observatory.build_diff(baseline, candidate)
        mapped = observatory.diff_from_mapping(value.to_dict())
        self.assertEqual(mapped.to_dict(), value.to_dict())
        self.assertIs(observatory.verify_diff_against_observatories(value, baseline, candidate), value)

    def test_diff_rejects_wrong_typed_inputs(self):
        with self.assertRaises(ValidationError):
            observatory.build_diff({}, {})
        with self.assertRaises(ValidationError):
            observatory.verify_diff({})
        with self.assertRaises(ValidationError):
            observatory.address_diff_item({})


class ObservatoryQueryTests(ObservatoryFixture):
    def test_summary_and_member_queries_are_bounded(self):
        value = self.make_observatory()
        summary = observatory.query_observatory(value)
        members = observatory.query_observatory(value, resource="members", limit=1)
        self.assertEqual(summary.total_count, 1)
        self.assertEqual(summary.returned_count, 1)
        self.assertEqual(members.total_count, 2)
        self.assertEqual(members.returned_count, 1)
        self.assertEqual(members.records[0]["member_id"], "source:0")

    def test_state_readiness_and_text_filters(self):
        value = self.make_observatory()
        self.assertEqual(observatory.query_observatory(value, resource="ready").total_count, 2)
        self.assertEqual(observatory.query_observatory(value, resource="accepted", accepted=True).total_count, 2)
        self.assertEqual(observatory.query_observatory(value, resource="rejected", accepted=False).total_count, 0)
        self.assertEqual(observatory.query_observatory(value, resource="members", text="source:1").total_count, 1)
        regressed = self.make_observatory((self.make_history("history:one", (self.ready_gate, self.held_gate), ("one:0", "one:1")), self.make_history("history:two", (self.ready_gate,), ("two:0",))))
        self.assertEqual(observatory.query_observatory(regressed, resource="members", latest_transition="regressed").total_count, 1)

    def test_query_round_trip_address_and_renderers(self):
        value = self.make_observatory()
        result = observatory.query_observatory(value, resource="members")
        self.assertEqual(observatory.address_query(result), result.content_address)
        self.assertIn("member_id", observatory.query_json(result))
        self.assertIn("member_id", observatory.query_csv(result))
        self.assertIn("Assurance history observatory query", observatory.render_query_markdown(result))

    def test_diff_queries_support_action_direction_and_state(self):
        baseline = self.make_observatory((self.make_history("history:one", (self.ready_gate,), ("one:0",)),), ("source:one",))
        candidate = self.make_observatory((self.make_history("history:one", (self.held_gate,), ("one:0",)), self.make_history("history:two", (self.ready_gate,), ("two:0",))), ("source:one", "source:two"))
        diff = observatory.build_diff(baseline, candidate)
        self.assertEqual(observatory.query_diff(diff, resource="added").total_count, 1)
        self.assertEqual(observatory.query_diff(diff, resource="regressed").total_count, 1)
        self.assertEqual(observatory.query_diff(diff, action="changed").total_count, 1)
        self.assertEqual(observatory.query_diff(diff, resource="items", state="held").total_count, 1)
        result = observatory.query_diff(diff, resource="items")
        self.assertEqual(observatory.address_diff_query(result), result.content_address)
        self.assertIn("direction", observatory.diff_query_csv(result).splitlines()[0])

    def test_query_rejects_unsupported_resources_and_windows(self):
        value = self.make_observatory()
        with self.assertRaises(ValidationError):
            observatory.ObservatoryQuery(resource="not-supported")
        with self.assertRaises(ValidationError):
            observatory.query_observatory(value, resource="members", limit=0)
        with self.assertRaises(ValidationError):
            observatory.ObservatoryDiffQuery(resource="not-supported")


class ObservatoryPersistenceTests(ObservatoryFixture):
    def test_exact_five_file_package_round_trip(self):
        value = self.make_observatory()
        with tempfile.TemporaryDirectory() as temporary:
            destination = self.write_observatory(value, Path(temporary))
            self.assertEqual({item.name for item in destination.iterdir()}, set(observatory.FILES))
            package = observatory.load_package(destination)
            self.assertEqual(package.observatory.to_dict(), value.to_dict())
            self.assertEqual(package.verification.to_dict(), observatory.load_verification(destination).to_dict())
            self.assertEqual(package.metrics, observatory.metrics_document(value))

    def test_storage_separates_summary_members_verification_and_metrics(self):
        value = self.make_observatory()
        with tempfile.TemporaryDirectory() as temporary:
            destination = self.write_observatory(value, Path(temporary))
            summary = json.loads((destination / observatory.OBSERVATORY_NAME).read_text(encoding="utf-8"))
            members = json.loads((destination / observatory.MEMBERS_NAME).read_text(encoding="utf-8"))
            self.assertNotIn("members", summary)
            self.assertEqual(summary["member_count"], members["member_count"])
            self.assertEqual(len(members["members"]), value.member_count)

    def test_deterministic_package_bytes(self):
        value = self.make_observatory()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.write_observatory(value, root, "first")
            second = self.write_observatory(value, root, "second")
            for name in observatory.FILES:
                self.assertEqual((first / name).read_bytes(), (second / name).read_bytes())

    def test_overwrite_requires_explicit_authorization(self):
        value = self.make_observatory()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination = self.write_observatory(value, root)
            with self.assertRaises(ValidationError):
                observatory.write_observatory(value, destination)
            observatory.write_observatory(value, destination, overwrite=True)

    def test_extra_file_is_rejected(self):
        value = self.make_observatory()
        with tempfile.TemporaryDirectory() as temporary:
            destination = self.write_observatory(value, Path(temporary))
            (destination / "unexpected.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                observatory.load_observatory(destination)

    def test_manifest_tampering_is_rejected(self):
        value = self.make_observatory()
        with tempfile.TemporaryDirectory() as temporary:
            destination = self.write_observatory(value, Path(temporary))
            manifest = json.loads((destination / observatory.MANIFEST_NAME).read_text(encoding="utf-8"))
            manifest["observatory_id"] = "observatory:tampered"
            (destination / observatory.MANIFEST_NAME).write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                observatory.load_observatory(destination)

    def test_metrics_tampering_is_rejected(self):
        value = self.make_observatory()
        with tempfile.TemporaryDirectory() as temporary:
            destination = self.write_observatory(value, Path(temporary))
            metrics = json.loads((destination / observatory.METRICS_NAME).read_text(encoding="utf-8"))
            metrics["entry_count"] += 1
            (destination / observatory.METRICS_NAME).write_bytes(canonical_bytes(metrics))
            with self.assertRaises(ValidationError):
                observatory.load_observatory(destination)

    def test_verification_tampering_is_rejected(self):
        value = self.make_observatory()
        with tempfile.TemporaryDirectory() as temporary:
            destination = self.write_observatory(value, Path(temporary))
            verification = json.loads((destination / observatory.VERIFICATION_NAME).read_text(encoding="utf-8"))
            verification["passed_count"] = 7
            (destination / observatory.VERIFICATION_NAME).write_bytes(canonical_bytes(verification))
            with self.assertRaises(ValidationError):
                observatory.load_observatory(destination)

    def test_diff_package_round_trip_and_exact_files(self):
        baseline = self.make_observatory()
        candidate = self.make_observatory((self.make_history("history:one", (self.ready_gate,), ("one:0",)),), ("source:one",))
        value = observatory.build_diff(baseline, candidate)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "diff"
            observatory.write_diff(value, destination)
            self.assertEqual({item.name for item in destination.iterdir()}, set(observatory.DIFF_FILES))
            self.assertEqual(observatory.load_diff(destination).to_dict(), value.to_dict())

    def test_verification_query_resources_filters_and_renderers(self):
        verification = observatory.build_verification(self.make_observatory())
        checks = observatory.query_verification(verification, resource="checks")
        self.assertEqual(checks.total_count, 8)
        self.assertEqual(checks.returned_count, 8)
        self.assertEqual(observatory.query_verification(verification, resource="failed").total_count, 0)
        self.assertEqual(observatory.query_verification(verification, resource="required").total_count, 8)
        self.assertEqual(observatory.query_verification(verification, resource="optional").total_count, 0)
        filtered = observatory.query_verification(verification, resource="checks", severity="required", passed=True, offset=1, limit=2)
        self.assertEqual(filtered.total_count, 8)
        self.assertEqual(filtered.returned_count, 2)
        text_filtered = observatory.query_verification(verification, resource="checks", text="recomputed")
        self.assertEqual(text_filtered.total_count, 2)
        self.assertTrue(filtered.content_address.startswith(observatory.VERIFICATION_QUERY_PREFIX + ":"))
        self.assertEqual(observatory.verification_query_json(filtered), canonical_json(filtered.to_dict()))
        self.assertIn("check_id", observatory.verification_query_csv(filtered))
        self.assertIn("Assurance history observatory verification query", observatory.render_verification_query_markdown(filtered))
        summary = observatory.query_verification(verification)
        self.assertEqual(summary.total_count, 1)
        self.assertEqual(summary.records[0]["verification_id"], verification.verification_id)
        with self.assertRaises(ValidationError):
            observatory.query_verification(verification, resource="unsupported")
        with self.assertRaises(ValidationError):
            observatory.VerificationQuery(limit=0)

    def test_diff_extra_file_is_rejected(self):
        value = observatory.build_diff(self.make_observatory(), self.make_observatory())
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "diff"
            observatory.write_diff(value, destination)
            (destination / "unexpected.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                observatory.load_diff(destination)


class ObservatoryVerificationQueryTests(ObservatoryFixture):
    def verification(self):
        return observatory.build_verification(self.make_observatory())

    def test_all_resources_are_explicit_and_bounded(self):
        verification = self.verification()
        expected = {"summary": 1, "checks": 8, "failed": 0, "required": 8, "optional": 0}
        for resource, count in expected.items():
            result = observatory.query_verification(verification, resource=resource, limit=3)
            self.assertEqual(result.total_count, count)
            self.assertLessEqual(result.returned_count, 3)

    def test_summary_is_a_verification_projection(self):
        verification = self.verification()
        result = observatory.query_verification(verification, resource="summary", severity="required", passed=False, text="no-match")
        self.assertEqual(result.total_count, 1)
        self.assertEqual(result.records[0], verification.summary())
        self.assertEqual(result.query.severity, "required")
        self.assertFalse(result.query.passed)

    def test_required_filter_composes_with_severity_and_pass_state(self):
        verification = self.verification()
        result = observatory.query_verification(verification, resource="checks", severity="required", passed=True)
        self.assertEqual(result.total_count, 8)
        self.assertTrue(all(item["severity"] == "required" and item["passed"] for item in result.records))

    def test_failed_filter_is_fail_closed(self):
        verification = self.verification()
        failed = observatory.query_verification(verification, resource="failed")
        contradictory = observatory.query_verification(verification, resource="failed", passed=True)
        self.assertEqual(failed.total_count, 0)
        self.assertEqual(contradictory.total_count, 0)
        self.assertEqual(contradictory.returned_count, 0)

    def test_optional_resource_is_empty_for_current_required_contract(self):
        result = observatory.query_verification(self.verification(), resource="optional")
        self.assertEqual(result.total_count, 0)
        self.assertEqual(result.records, ())
        self.assertTrue(result.content_address.startswith(observatory.VERIFICATION_QUERY_PREFIX + ":"))

    def test_severity_filter_rejects_non_enum(self):
        with self.assertRaises(ValidationError):
            observatory.VerificationQuery(resource="checks", severity="critical")

    def test_pass_filter_requires_boolean(self):
        with self.assertRaises(ValidationError):
            observatory.VerificationQuery(resource="checks", passed="true")

    def test_text_filter_is_case_insensitive(self):
        verification = self.verification()
        upper = observatory.query_verification(verification, resource="checks", text="RECOMPUTED")
        lower = observatory.query_verification(verification, resource="checks", text="recomputed")
        self.assertEqual(upper.records, lower.records)
        self.assertEqual(upper.total_count, lower.total_count)
        self.assertEqual(upper.total_count, 2)

    def test_pagination_is_applied_after_filtering(self):
        verification = self.verification()
        first = observatory.query_verification(verification, resource="checks", offset=0, limit=2)
        second = observatory.query_verification(verification, resource="checks", offset=2, limit=2)
        self.assertEqual(first.total_count, 8)
        self.assertEqual(second.total_count, 8)
        self.assertEqual(first.returned_count, 2)
        self.assertEqual(second.returned_count, 2)
        self.assertNotEqual(first.records, second.records)

    def test_offset_past_total_returns_addressed_empty_window(self):
        result = observatory.query_verification(self.verification(), resource="checks", offset=8, limit=2)
        self.assertEqual(result.total_count, 8)
        self.assertEqual(result.returned_count, 0)
        self.assertEqual(result.records, ())

    def test_window_limits_are_positive_and_bounded(self):
        for kwargs in ({"limit": 0}, {"limit": -1}, {"offset": -1}, {"offset": observatory.MAX_QUERY_ITEMS + 1}, {"limit": observatory.MAX_QUERY_ITEMS + 1}):
            with self.assertRaises(ValidationError):
                observatory.VerificationQuery(**kwargs)

    def test_query_constructor_normalizes_only_the_declared_fields(self):
        query = observatory.VerificationQuery(resource="checks", severity="required", passed=True, text="needle", offset=2, limit=7)
        self.assertEqual(query.to_dict(), {"resource": "checks", "severity": "required", "passed": True, "text": "needle", "offset": 2, "limit": 7})

    def test_query_requires_typed_verification(self):
        with self.assertRaises(ValidationError):
            observatory.query_verification({"content_address": "history:plain"}, resource="checks")

    def test_query_requires_typed_query_when_supplied(self):
        with self.assertRaises(ValidationError):
            observatory.query_verification(self.verification(), query={"resource": "checks"})

    def test_query_result_address_changes_with_window(self):
        verification = self.verification()
        first = observatory.query_verification(verification, resource="checks", limit=1)
        second = observatory.query_verification(verification, resource="checks", limit=2)
        self.assertNotEqual(first.content_address, second.content_address)
        self.assertEqual(observatory.address_verification_query(first), first.content_address)
        self.assertEqual(observatory.address_verification_query(second), second.content_address)

    def test_query_is_deterministic(self):
        verification = self.verification()
        first = observatory.query_verification(verification, resource="required", offset=1, limit=3)
        second = observatory.query_verification(verification, resource="required", offset=1, limit=3)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(observatory.verification_query_json(first), observatory.verification_query_json(second))

    def test_query_result_rejects_bad_verification_address(self):
        query = observatory.VerificationQuery(resource="checks")
        with self.assertRaises(ValidationError):
            observatory.VerificationQueryResult("not-addressed", query, 0, (), "pending:verification-query")

    def test_query_result_rejects_window_over_limit(self):
        query = observatory.VerificationQuery(resource="checks", limit=1)
        with self.assertRaises(ValidationError):
            observatory.VerificationQueryResult("verification:one", query, 2, ({"check_id": "one"}, {"check_id": "two"}), "pending:verification-query")

    def test_query_result_rejects_non_public_record(self):
        query = observatory.VerificationQuery(resource="checks")
        with self.assertRaises(ValidationError):
            observatory.VerificationQueryResult("verification:one", query, 1, ({"private": "secret"},), "pending:verification-query")

    def test_json_csv_and_markdown_share_selection(self):
        result = observatory.query_verification(self.verification(), resource="checks", limit=2)
        json_payload = json.loads(observatory.verification_query_json(result))
        csv_text = observatory.verification_query_csv(result)
        markdown = observatory.render_verification_query_markdown(result)
        self.assertEqual(len(json_payload["records"]), 2)
        self.assertIn("check_id", csv_text)
        self.assertIn("member-identities", markdown)
        self.assertIn(result.content_address, markdown)

    def test_renderers_reject_plain_values(self):
        for renderer in (observatory.verification_query_json, observatory.verification_query_csv, observatory.render_verification_query_markdown):
            with self.assertRaises(ValidationError):
                renderer({"records": ()})

    def test_schema_is_closed_and_describes_summary_or_checks(self):
        schema = observatory.verification_query_schema()
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(tuple(schema["properties"]["query"]["properties"]["resource"]["enum"]), observatory.VerificationQuery.RESOURCES)
        alternatives = schema["properties"]["records"]["items"]["anyOf"]
        self.assertEqual(len(alternatives), 2)

    def test_capabilities_publish_verification_resources_and_schema(self):
        capabilities = observatory.capabilities()
        self.assertEqual(tuple(capabilities["resources"]["verification"]), observatory.VerificationQuery.RESOURCES)
        self.assertIn("verification-query", capabilities["schemas"])

    def test_public_query_result_contains_no_private_keys_or_paths(self):
        result = observatory.query_verification(self.verification(), resource="checks", limit=2)
        self.assert_public(result)

    def test_query_uses_loaded_verification_address(self):
        verification = self.verification()
        result = observatory.query_verification(verification, resource="checks")
        self.assertEqual(result.verification_address, verification.content_address)
        self.assertEqual(result.records[0]["check_id"], verification.checks[0].check_id)


class ObservatoryVerificationQueryDemoTests(ObservatoryFixture):
    def package(self, root: Path) -> Path:
        history_value = self.make_history("history:demo", (self.ready_gate,), ("demo:0",))
        history_directory = self.write_history(history_value, root, "history")
        observatory_directory = root / "observatory"
        value = observatory.build_observatory_from_directories((history_directory,), observatory_id="observatory:demo", member_ids=("source:demo",))
        observatory.write_observatory(value, observatory_directory)
        return observatory_directory

    def test_demo_loads_and_queries_exact_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = verification_query_demo.run_demo(input_directory=self.package(Path(temporary)), resource="checks", severity="required", passed=True, limit=4)
            self.assertEqual(result.total_count, 8)
            self.assertEqual(result.returned_count, 4)
            self.assertTrue(result.content_address.startswith(observatory.VERIFICATION_QUERY_PREFIX + ":"))

    def test_demo_summary_is_path_free(self):
        with tempfile.TemporaryDirectory() as temporary:
            package = self.package(Path(temporary))
            result = verification_query_demo.run_demo(input_directory=package)
            report = verification_query_demo._summary(result)
            self.assertNotIn(str(package), report)
            self.assertNotIn("C:\\", report)
            self.assertIn("verification_address", report)

    def test_demo_json_is_canonical_projection(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = verification_query_demo.run_demo(input_directory=self.package(Path(temporary)), resource="failed")
            rendered = verification_query_demo._render(result, "json")
            self.assertEqual(json.loads(rendered), json.loads(canonical_json(result.to_dict())))
            self.assertTrue(rendered.endswith("\n"))

    def test_demo_csv_and_markdown_are_public(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = verification_query_demo.run_demo(input_directory=self.package(Path(temporary)), resource="checks", limit=1)
            csv_report = verification_query_demo._render(result, "csv")
            markdown_report = verification_query_demo._render(result, "markdown")
            self.assertIn("check_id", csv_report)
            self.assertIn("Assurance history observatory verification query", markdown_report)
            self.assertNotIn(str(Path(temporary)), csv_report + markdown_report)

    def test_demo_report_writes_only_requested_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = verification_query_demo.run_demo(input_directory=self.package(root), resource="required", limit=1)
            report_path = root / "reports" / "checks.json"
            verification_query_demo._write(verification_query_demo._render(result, "json"), report_path)
            self.assertEqual(json.loads(report_path.read_text(encoding="utf-8")), json.loads(canonical_json(result.to_dict())))

    def test_demo_main_returns_zero_for_empty_matches(self):
        with tempfile.TemporaryDirectory() as temporary:
            package = self.package(Path(temporary))
            output = StringIO()
            with redirect_stdout(output):
                status = verification_query_demo.main(["--input", str(package), "--resource", "failed", "--format", "summary"])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output.getvalue())["total_count"], 0)

    def test_demo_main_returns_one_for_missing_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = StringIO()
            with redirect_stdout(output):
                status = verification_query_demo.main(["--input", str(Path(temporary) / "missing")])
            self.assertEqual(status, 1)
            self.assertIn("error", json.loads(output.getvalue()))

    def test_demo_rejects_invalid_query_before_rendering(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValidationError):
                verification_query_demo.run_demo(input_directory=self.package(Path(temporary)), resource="not-a-resource")

    def test_demo_parser_declares_all_bounded_controls(self):
        parser = verification_query_demo._parser()
        arguments = {action.dest for action in parser._actions}
        self.assertTrue({"input", "resource", "severity", "passed", "text", "offset", "limit", "format", "report"} <= arguments)

    def test_demo_summary_contains_window_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = verification_query_demo.run_demo(input_directory=self.package(Path(temporary)), resource="checks", offset=2, limit=3)
            summary = json.loads(verification_query_demo._summary(result))
            self.assertEqual(summary["offset"], 2)
            self.assertEqual(summary["limit"], 3)
            self.assertEqual(summary["returned_count"], 3)

    def test_demo_run_result_preserves_query_address(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = verification_query_demo.run_demo(input_directory=self.package(Path(temporary)), resource="required")
            self.assertEqual(result.verification_address.split(":", 1)[0], observatory.VERIFICATION_PREFIX)
            self.assertEqual(observatory.address_verification_query(result), result.content_address)


class ObservatoryVerificationQueryMatrixTests(ObservatoryFixture):
    def verification(self):
        return observatory.build_verification(self.make_observatory())

    def test_resource_and_severity_matrix_is_conservative(self):
        verification = self.verification()
        for resource in observatory.VerificationQuery.RESOURCES:
            for severity in (None, "required", "optional"):
                result = observatory.query_verification(verification, resource=resource, severity=severity)
                self.assertLessEqual(result.returned_count, result.total_count)
                if resource == "failed":
                    self.assertTrue(all(not item["passed"] for item in result.records))
                if resource == "required":
                    self.assertTrue(all(item["severity"] == "required" for item in result.records))
                if resource == "optional":
                    self.assertTrue(all(item["severity"] == "optional" for item in result.records))

    def test_pass_state_matrix_contains_only_requested_values(self):
        verification = self.verification()
        for passed in (True, False, None):
            result = observatory.query_verification(verification, resource="checks", passed=passed)
            if passed is not None:
                self.assertTrue(all(item["passed"] is passed for item in result.records))
            self.assertEqual(result.total_count, 8 if passed is not False else 0)

    def test_filter_composition_can_produce_empty_result(self):
        result = observatory.query_verification(self.verification(), resource="optional", severity="required", passed=True, text="missing")
        self.assertEqual(result.total_count, 0)
        self.assertEqual(result.returned_count, 0)
        self.assertEqual(result.records, ())

    def test_check_order_matches_verification_order(self):
        verification = self.verification()
        result = observatory.query_verification(verification, resource="checks")
        self.assertEqual(tuple(item["check_id"] for item in result.records), tuple(check.check_id for check in verification.checks))

    def test_check_records_keep_complete_public_fields(self):
        result = observatory.query_verification(self.verification(), resource="checks")
        required = {"check_id", "severity", "passed", "detail", "expected", "observed", "content_address"}
        self.assertTrue(all(set(item) == required for item in result.records))

    def test_text_filter_searches_detail_expected_and_observed(self):
        verification = self.verification()
        for needle in ("unique", "public", "reproducible", "ready"):
            result = observatory.query_verification(verification, resource="checks", text=needle)
            self.assertGreaterEqual(result.total_count, 1)

    def test_text_filter_is_stable_for_whitespace_case(self):
        verification = self.verification()
        first = observatory.query_verification(verification, resource="checks", text="public")
        second = observatory.query_verification(verification, resource="checks", text="PUBLIC")
        self.assertEqual(first.records, second.records)
        self.assertNotEqual(first.query.text, second.query.text)

    def test_offset_limit_matrix_never_exceeds_limit(self):
        verification = self.verification()
        for offset in (0, 1, 4, 8, 4096):
            for limit in (1, 2, 7, 4096):
                result = observatory.query_verification(verification, resource="checks", offset=offset, limit=limit)
                self.assertLessEqual(result.returned_count, limit)
                self.assertLessEqual(result.returned_count, result.total_count)

    def test_different_resources_have_distinct_query_addresses(self):
        verification = self.verification()
        addresses = {observatory.query_verification(verification, resource=resource).content_address for resource in observatory.VerificationQuery.RESOURCES}
        self.assertEqual(len(addresses), len(observatory.VerificationQuery.RESOURCES))

    def test_different_verifications_have_distinct_query_addresses(self):
        histories = (self.make_history("history:one", (self.ready_gate,), ("one:0",)), self.make_history("history:two", (self.ready_gate,), ("two:0",)))
        first = observatory.build_verification(observatory.build_observatory(histories, observatory_id="observatory:first", member_ids=("source:one", "source:two")))
        second = observatory.build_verification(observatory.build_observatory(histories, observatory_id="observatory:second", member_ids=("source:one", "source:two")))
        first_result = observatory.query_verification(first, resource="checks")
        second_result = observatory.query_verification(second, resource="checks")
        self.assertNotEqual(first_result.verification_address, second_result.verification_address)
        self.assertNotEqual(first_result.content_address, second_result.content_address)

    def test_result_dictionary_has_stable_top_level_shape(self):
        result = observatory.query_verification(self.verification(), resource="checks", limit=1)
        self.assertEqual(tuple(result.to_dict()), ("verification_address", "query", "total_count", "returned_count", "records", "content_address"))
        self.assertEqual(tuple(result.to_dict()["query"]), ("resource", "severity", "passed", "text", "offset", "limit"))

    def test_empty_result_serializations_are_still_structured(self):
        result = observatory.query_verification(self.verification(), resource="failed")
        self.assertEqual(json.loads(observatory.verification_query_json(result))["records"], [])
        self.assertIn("verification_address", observatory.verification_query_csv(result).splitlines()[0])
        self.assertIn("Summary", observatory.render_verification_query_markdown(result))

    def test_query_schema_has_filter_nullability(self):
        properties = observatory.verification_query_schema()["properties"]["query"]["properties"]
        self.assertEqual(properties["severity"]["anyOf"][-1], {"type": "null"})
        self.assertEqual(properties["passed"]["anyOf"][-1], {"type": "null"})
        self.assertEqual(properties["text"]["anyOf"][-1], {"type": "null"})

    def test_long_text_and_resource_values_are_rejected(self):
        with self.assertRaises(ValidationError):
            observatory.VerificationQuery(resource="x" * 65)
        with self.assertRaises(ValidationError):
            observatory.VerificationQuery(text="x" * 513)

    def test_query_result_accepts_pending_address_only_during_construction(self):
        query = observatory.VerificationQuery(resource="checks", limit=1)
        result = observatory.VerificationQueryResult("verification:one", query, 0, (), "pending:verification-query")
        self.assertEqual(result.content_address, "pending:verification-query")

    def test_query_result_requires_addressed_final_content(self):
        query = observatory.VerificationQuery(resource="checks", limit=1)
        with self.assertRaises(ValidationError):
            observatory.VerificationQueryResult("verification:one", query, 0, (), "query:wrong")

    def test_capabilities_limits_match_constructor_limits(self):
        limits = observatory.capabilities()["limits"]
        self.assertEqual(limits["max_checks"], observatory.MAX_CHECKS)
        self.assertEqual(limits["max_query_items"], observatory.MAX_QUERY_ITEMS)

    def test_query_output_does_not_mutate_verification(self):
        verification = self.verification()
        before = verification.to_dict()
        observatory.query_verification(verification, resource="checks", text="ready", offset=1, limit=2)
        self.assertEqual(verification.to_dict(), before)

    def test_resource_filter_and_severity_filter_intersect(self):
        result = observatory.query_verification(self.verification(), resource="optional", severity="optional")
        self.assertEqual(result.total_count, 0)
        self.assertEqual(result.returned_count, 0)

    def test_failed_query_address_is_repeatable_when_empty(self):
        verification = self.verification()
        first = observatory.query_verification(verification, resource="failed")
        second = observatory.query_verification(verification, resource="failed")
        self.assertEqual(first.content_address, second.content_address)

    def test_query_records_are_detached_from_source_check_dicts(self):
        verification = self.verification()
        result = observatory.query_verification(verification, resource="checks", limit=1)
        result.records[0]["detail"] = "local mutation"
        self.assertNotEqual(verification.checks[0].detail, "local mutation")

    def test_query_result_content_address_is_not_verification_address(self):
        verification = self.verification()
        result = observatory.query_verification(verification, resource="checks")
        self.assertNotEqual(result.content_address, result.verification_address)

    def test_query_result_records_are_tuple_ordered(self):
        result = observatory.query_verification(self.verification(), resource="checks", limit=3)
        self.assertIsInstance(result.records, tuple)
        self.assertEqual(result.returned_count, len(result.records))

    def test_query_summary_has_no_check_records(self):
        result = observatory.query_verification(self.verification(), resource="summary")
        self.assertNotIn("check_id", result.records[0])

    def test_query_filter_text_can_match_check_identifier(self):
        result = observatory.query_verification(self.verification(), resource="checks", text="member-identities")
        self.assertEqual(result.total_count, 1)
        self.assertEqual(result.records[0]["check_id"], "member-identities")

    def test_query_schema_declares_bounded_records(self):
        records = observatory.verification_query_schema()["properties"]["records"]
        self.assertEqual(records["maxItems"], observatory.MAX_CHECKS)

    def test_query_summary_window_is_always_one_record(self):
        result = observatory.query_verification(self.verification(), resource="summary", offset=4096, limit=1)
        self.assertEqual(result.total_count, 1)
        self.assertEqual(result.returned_count, 1)
        self.assertEqual(result.records[0]["state"], "promote")

    def test_query_resource_names_are_serialized_as_strings(self):
        result = observatory.query_verification(self.verification(), resource="checks", limit=1)
        self.assertIsInstance(result.to_dict()["query"]["resource"], str)

    def test_query_limit_is_serialized_as_integer(self):
        result = observatory.query_verification(self.verification(), resource="checks", limit=1)
        self.assertIsInstance(result.to_dict()["query"]["limit"], int)

    def test_query_offset_is_serialized_as_integer(self):
        result = observatory.query_verification(self.verification(), resource="checks", offset=1, limit=1)
        self.assertIsInstance(result.to_dict()["query"]["offset"], int)


class ObservatoryOperatorSurfaceTests(ObservatoryFixture):
    COMMAND = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history-observatory"

    def test_cli_capabilities_and_schemas(self):
        status, output = self.capture_cli([self.COMMAND + "-capabilities"])
        self.assertEqual(status, 0)
        self.assertEqual(tuple(json.loads(output)["package_files"]), observatory.FILES)
        status, output = self.capture_cli([self.COMMAND + "-verification-schema"])
        self.assertEqual(status, 0)
        self.assertFalse(json.loads(output)["additionalProperties"])
        status, output = self.capture_cli([self.COMMAND + "-diff-query-schema"])
        self.assertEqual(status, 0)
        self.assertFalse(json.loads(output)["additionalProperties"])

    def test_cli_build_verify_query_and_diff(self):
        first = self.make_history("history:one", (self.ready_gate,), ("one:0",))
        second = self.make_history("history:two", (self.ready_gate,), ("two:0",))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first_dir = self.write_history(first, root, "first")
            second_dir = self.write_history(second, root, "second")
            destination = root / "observatory"
            status, output = self.capture_cli([self.COMMAND, "--history-directory", str(first_dir), "--history-directory", str(second_dir), "--member-id", "source:one", "--member-id", "source:two", "--destination", str(destination), "--format", "summary"])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output)["member_count"], 2)
            status, output = self.capture_cli([self.COMMAND + "-verify", "--input", str(destination)])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output)["state"], "promote")
            status, output = self.capture_cli([self.COMMAND + "-query", "--input", str(destination), "--resource", "members"])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output)["total_count"], 2)
            diff_destination = root / "diff"
            status, output = self.capture_cli([self.COMMAND + "-diff", "--baseline", str(destination), "--candidate", str(destination), "--destination", str(diff_destination), "--format", "summary"])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output)["unchanged_count"], 2)
            status, output = self.capture_cli([self.COMMAND + "-diff-query", "--input", str(diff_destination), "--resource", "items"])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output)["total_count"], 2)
            status, output = self.capture_cli([self.COMMAND + "-verification-query", "--input", str(destination), "--resource", "checks", "--severity", "required", "--passed"])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output)["total_count"], 8)
            status, output = self.capture_cli([self.COMMAND + "-verification-query-schema"])
            self.assertEqual(status, 0)
            self.assertFalse(json.loads(output)["additionalProperties"])

    def test_http_build_verify_query_diff_and_schema(self):
        first = self.make_history("history:one", (self.ready_gate,), ("one:0",))
        second = self.make_history("history:two", (self.ready_gate,), ("two:0",))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first_dir = self.write_history(first, root, "first")
            second_dir = self.write_history(second, root, "second")
            observatory_dir = root / "observatory"
            diff_dir = root / "diff"
            server, thread = self.server()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                prefix = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory"
                for suffix in ("/schema", "/member-schema", "/verification-schema", "/verification-query-schema", "/metrics-schema", "/package-schema", "/query-schema", "/diff/schema", "/diff/item-schema", "/diff/query-schema", "/capabilities"):
                    with urlopen(base + prefix + suffix) as response:
                        self.assertEqual(response.status, 200)
                        self.assertIsInstance(json.loads(response.read()), dict)
                query = urlencode([("history_directory", str(first_dir)), ("history_directory", str(second_dir)), ("member_id", "source:one"), ("member_id", "source:two"), ("destination", str(observatory_dir)), ("format", "summary")])
                with urlopen(base + prefix + "?" + query) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(json.loads(response.read())["member_count"], 2)
                with urlopen(base + prefix + "/verify?input=" + str(observatory_dir)) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(json.loads(response.read())["state"], "promote")
                with urlopen(base + prefix + "/query?input=" + str(observatory_dir) + "&resource=members") as response:
                    self.assertEqual(json.loads(response.read())["total_count"], 2)
                with urlopen(base + prefix + "/verification/query?input=" + str(observatory_dir) + "&resource=checks&severity=required&passed=true") as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(json.loads(response.read())["total_count"], 8)
                diff_query = urlencode({"baseline": str(observatory_dir), "candidate": str(observatory_dir), "destination": str(diff_dir), "format": "summary"})
                with urlopen(base + prefix + "/diff?" + diff_query) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(json.loads(response.read())["unchanged_count"], 2)
                with urlopen(base + prefix + "/diff/verify?input=" + str(diff_dir)) as response:
                    self.assertEqual(json.loads(response.read())["unchanged_count"], 2)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_real_downloaded_history_package_can_be_observed(self):
        source = Path(r"C:\Users\murar\AppData\Local\Temp\glio-noncode-history-demo-current") / "history"
        if not source.exists():
            self.skipTest("current downloaded-data history package is not present")
        value = observatory.build_observatory_from_directories((source,), observatory_id="observatory:downloaded")
        self.assertEqual(value.member_count, 1)
        self.assertTrue(value.members[0].history_address.startswith(history.HISTORY_PREFIX + ":"))
        self.assert_public(value)

    def test_demo_module_has_no_input_path_in_public_output(self):
        self.assertTrue(hasattr(history_demo, "main"))


if __name__ == "__main__":
    unittest.main()
