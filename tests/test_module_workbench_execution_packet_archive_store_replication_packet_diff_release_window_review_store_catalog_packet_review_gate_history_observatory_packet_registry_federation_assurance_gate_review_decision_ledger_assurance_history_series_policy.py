"""Deep contracts for decision-assurance history-series policies."""

# ruff: noqa: E501

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import (
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_review_decision_ledger_assurance_history_series_policy as policy,
)
from glio_noncode.errors import ValidationError
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.serialization import canonical_bytes, canonical_json, hash_bytes
from tests.test_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_review_decision_ledger_assurance_history_series import SeriesFixture


class PolicyFixture(SeriesFixture):
    def policy_value(self, policy_id="policy:test", **updates):
        value = policy.default_decision_assurance_history_series_policy(policy_id=policy_id)
        body = value.to_dict()
        body.update(updates)
        body["content_address"] = "pending:custom-policy"
        provisional = policy.DecisionAssuranceHistorySeriesPolicy(**body)
        body["content_address"] = policy.address_decision_assurance_history_series_policy(provisional)
        return policy.DecisionAssuranceHistorySeriesPolicy(**body)

    def evaluate(self, values, **updates):
        return policy.evaluate_decision_assurance_history_series_policy(self.build_series(values), self.policy_value(**updates))

    def write_evaluation(self, value, destination, **kwargs):
        return policy.write_decision_assurance_history_series_policy_evaluation(value, destination, **kwargs)


class PolicyCoreTests(PolicyFixture):
    def test_default_policy_is_public_and_addressed(self):
        value = policy.default_decision_assurance_history_series_policy()
        self.assertEqual(value.minimum_histories, 1)
        self.assertEqual(value.maximum_blocked_histories, 0)
        self.assertEqual(policy.address_decision_assurance_history_series_policy(value), value.content_address)
        payload = canonical_json(value.to_dict()).casefold()
        self.assertNotIn(str(self.real_packet()).casefold(), payload)
        for forbidden in ("agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "token", "user"):
            self.assertNotIn(f'"{forbidden}"', payload)

    def test_custom_policy_mapping_round_trip_and_tamper_rejection(self):
        value = self.policy_value(minimum_histories=2, minimum_observations=4, maximum_held_histories=2, allow_mixed_state=False)
        restored = policy.decision_assurance_history_series_policy_from_mapping(value.to_dict())
        self.assertEqual(restored.to_dict(), value.to_dict())
        body = value.to_dict()
        body["private"] = True
        with self.assertRaises(ValidationError):
            policy.decision_assurance_history_series_policy_from_mapping(body)
        body = value.to_dict()
        body["maximum_blocked_histories"] = 300
        with self.assertRaises(ValidationError):
            policy.decision_assurance_history_series_policy_from_mapping(body)
        body = value.to_dict()
        body["content_address"] = "policy:tampered"
        with self.assertRaises(ValidationError):
            policy.decision_assurance_history_series_policy_from_mapping(body)

    def test_invalid_policy_limits_and_booleans_are_rejected(self):
        value = policy.default_decision_assurance_history_series_policy()
        body = value.to_dict()
        body["minimum_histories"] = -1
        with self.assertRaises(ValidationError):
            policy.DecisionAssuranceHistorySeriesPolicy(**body)
        body = value.to_dict()
        body["allow_mixed_state"] = 1
        with self.assertRaises(ValidationError):
            policy.DecisionAssuranceHistorySeriesPolicy(**body)

    def test_default_policy_holds_for_held_history_but_accepts_it(self):
        value = self.evaluate((self.ready_history("history:ready"), self.held_history("history:held")), require_current_release_ready=False)
        self.assertEqual(value.check_count, 9)
        self.assertEqual(value.passed_count, 8)
        self.assertEqual(value.warning_count, 1)
        self.assertEqual(value.blocker_count, 0)
        self.assertEqual(value.state, "hold")
        self.assertTrue(value.accepted)
        self.assertFalse(value.release_ready)
        self.assertEqual(value.checks[3].kind, "held-ceiling")
        self.assertFalse(value.checks[3].passed)
        self.assertFalse(value.checks[3].required)

    def test_blocked_history_is_a_required_policy_failure(self):
        value = self.evaluate((self.ready_history("history:ready"), self.blocked_history("history:blocked")))
        self.assertGreaterEqual(value.blocker_count, 1)
        self.assertEqual(value.state, "blocked")
        self.assertFalse(value.accepted)
        self.assertFalse(value.release_ready)
        self.assertFalse(next(item for item in value.checks if item.kind == "blocked-ceiling").passed)

    def test_relaxed_policy_can_pass_mixed_history_series(self):
        value = self.evaluate((self.ready_history("history:ready"), self.held_history("history:held"), self.blocked_history("history:blocked")), minimum_histories=3, minimum_observations=3, maximum_held_histories=1, maximum_blocked_histories=1, require_current_accepted=False, require_current_release_ready=False, allow_mixed_state=True)
        self.assertEqual(value.state, "passed")
        self.assertTrue(value.accepted)
        self.assertTrue(value.release_ready)
        self.assertEqual(value.passed_count, 9)

    def test_mixed_state_rule_can_block_when_explicitly_disallowed(self):
        value = self.evaluate((self.ready_history("history:ready"), self.held_history("history:held")), maximum_held_histories=1, allow_mixed_state=False)
        self.assertEqual(value.state, "blocked")
        self.assertFalse(next(item for item in value.checks if item.kind == "mixed-state").passed)
        self.assertTrue(next(item for item in value.checks if item.kind == "mixed-state").required)

    def test_minimum_history_and_observation_rules_are_independent(self):
        value = self.evaluate((self.ready_history("history:one"),), minimum_histories=2, minimum_observations=2)
        self.assertFalse(next(item for item in value.checks if item.kind == "minimum-histories").passed)
        self.assertFalse(next(item for item in value.checks if item.kind == "minimum-observations").passed)
        self.assertEqual(value.blocker_count, 2)

    def test_evaluation_mapping_recomputes_checks_and_addresses(self):
        value = self.evaluate((self.ready_history("history:mapped"),), maximum_held_histories=1)
        restored = policy.decision_assurance_history_series_policy_evaluation_from_mapping(value.to_dict())
        self.assertEqual(restored.to_dict(), value.to_dict())
        body = value.to_dict()
        body["checks"][0]["detail"] = "tampered"
        with self.assertRaises(ValidationError):
            policy.decision_assurance_history_series_policy_evaluation_from_mapping(body)
        body = value.to_dict()
        body["policy_address"] = "policy:tampered"
        with self.assertRaises(ValidationError):
            policy.decision_assurance_history_series_policy_evaluation_from_mapping(body)

    def test_policy_check_direct_shape_rejects_tampered_receipt(self):
        value = self.evaluate((self.ready_history("history:check"),), maximum_held_histories=1)
        body = value.checks[0].to_dict()
        body["content_address"] = "check:tampered"
        with self.assertRaises(ValidationError):
            policy.DecisionAssuranceHistorySeriesPolicyCheck(**body)


class PolicyExportTests(PolicyFixture):
    def setUp(self):
        super().setUp()
        self.value = self.evaluate((self.ready_history("history:export"),), maximum_held_histories=1)

    def test_json_csv_markdown_schemas_and_capabilities(self):
        self.assertIn('"policy_id"', policy.decision_assurance_history_series_policy_json(self.value.policy))
        self.assertIn("minimum_histories", policy.decision_assurance_history_series_policy_csv(self.value.policy))
        self.assertIn('"check_count"', policy.decision_assurance_history_series_policy_evaluation_json(self.value))
        self.assertIn("check_id", policy.decision_assurance_history_series_policy_evaluation_csv(self.value))
        self.assertIn("# Federation Review Decision Assurance History Series Policy", policy.render_decision_assurance_history_series_policy_markdown(self.value.policy))
        self.assertIn("# Federation Review Decision Assurance History Series Policy Evaluation", policy.render_decision_assurance_history_series_policy_evaluation_markdown(self.value))
        self.assertEqual(policy.capabilities()["checks"]["count"], 9)
        for schema in (policy.decision_assurance_history_series_policy_schema(), policy.decision_assurance_history_series_policy_check_schema(), policy.decision_assurance_history_series_policy_evaluation_schema()):
            self.assertFalse(schema["additionalProperties"])

    def test_exports_reject_invalid_typed_values(self):
        body = self.value.to_dict()
        body["content_address"] = "evaluation:tampered"
        with self.assertRaises(ValidationError):
            policy.decision_assurance_history_series_policy_evaluation_from_mapping(body)


class PolicyPersistenceTests(PolicyFixture):
    def setUp(self):
        super().setUp()
        self.value = self.evaluate((self.ready_history("history:persist"), self.held_history("history:held")))

    def test_persistence_has_exact_three_files_and_round_trips(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "policy"
            self.write_evaluation(self.value, destination)
            self.assertEqual({item.name for item in destination.iterdir()}, set(policy.FILES))
            loaded = policy.load_decision_assurance_history_series_policy_evaluation(destination)
            self.assertEqual(loaded.to_dict(), self.value.to_dict())
            self.assertEqual(canonical_bytes(json.loads((destination / "evaluation.json").read_text())), (destination / "evaluation.json").read_bytes())

    def test_persistence_repeatability_and_receipt_linkage(self):
        with tempfile.TemporaryDirectory() as temporary:
            first = Path(temporary) / "first"
            second = Path(temporary) / "second"
            self.write_evaluation(self.value, first)
            self.write_evaluation(self.value, second)
            self.assertEqual([item.read_bytes() for item in first.iterdir()], [item.read_bytes() for item in second.iterdir()])
            manifest = json.loads((first / "manifest.json").read_text())
            self.assertEqual(manifest["artifact_count"], 2)
            self.assertEqual(manifest["policy_address"], self.value.policy.content_address)
            self.assertEqual(manifest["evaluation_address"], self.value.content_address)

    def test_persistence_rejects_missing_extra_noncanonical_and_tampered_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "policy"
            self.write_evaluation(self.value, destination)
            (destination / "policy.json").unlink()
            with self.assertRaises(ValidationError):
                policy.load_decision_assurance_history_series_policy_evaluation(destination)
            self.write_evaluation(self.value, destination, overwrite=True)
            (destination / "extra.json").write_text("{}")
            with self.assertRaises(ValidationError):
                policy.load_decision_assurance_history_series_policy_evaluation(destination)
            (destination / "extra.json").unlink()
            (destination / "evaluation.json").write_text(json.dumps(json.loads((destination / "evaluation.json").read_text()), indent=2))
            with self.assertRaises(ValidationError):
                policy.load_decision_assurance_history_series_policy_evaluation(destination)
            self.write_evaluation(self.value, destination, overwrite=True)
            raw = json.loads((destination / "policy.json").read_text())
            raw["policy_id"] = "policy:tampered"
            (destination / "policy.json").write_bytes(canonical_bytes(raw))
            with self.assertRaises(ValidationError):
                policy.load_decision_assurance_history_series_policy_evaluation(destination)

    def test_persistence_rejects_symlink_and_nonempty_destination_without_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "policy"
            destination.mkdir()
            (destination / "old").write_text("old")
            with self.assertRaises(ValidationError):
                self.write_evaluation(self.value, destination)
            self.write_evaluation(self.value, destination, overwrite=True)
            link = destination / "link.json"
            try:
                link.symlink_to(destination / "policy.json")
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable")
            with self.assertRaises(ValidationError):
                policy.load_decision_assurance_history_series_policy_evaluation(destination)


class PolicyRealDataTests(PolicyFixture):
    def test_downloaded_data_series_can_be_evaluated_without_source_paths(self):
        value = self.evaluate((self.ready_history("download:ready"),), maximum_held_histories=1)
        self.assertTrue(value.release_ready)
        payload = canonical_json(value.to_dict()).casefold()
        self.assertNotIn(str(self.real_packet()).casefold(), payload)
        self.assertNotIn("source_path", payload)


class PolicyCliApiTests(PolicyFixture):
    base = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decisions-assurance-history-series-policy"

    def capture_cli(self, arguments):
        from contextlib import redirect_stdout
        from io import StringIO

        output = StringIO()
        with redirect_stdout(output):
            status = main(arguments)
        return status, output.getvalue()

    def test_cli_evaluates_and_verifies_a_persisted_series_policy(self):
        value = self.build_series((self.ready_history("cli:ready"),), "cli:series")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            series_directory = root / "series"
            evaluation_directory = root / "evaluation"
            from glio_noncode import write_decision_assurance_history_series

            write_decision_assurance_history_series(value, series_directory)
            status, output = self.capture_cli([self.base, "--input", str(series_directory), "--destination", str(evaluation_directory), "--format", "summary"])
            self.assertEqual(status, 0)
            self.assertIn('"state": "passed"', output)
            status, output = self.capture_cli([self.base + "-verify", "--input", str(evaluation_directory)])
            self.assertEqual(status, 0)
            self.assertIn('"accepted": true', output)
            for suffix in ("-schema", "-check-schema", "-evaluation-schema", "-capabilities"):
                status, output = self.capture_cli([self.base + suffix])
                self.assertEqual(status, 0)
                self.assertTrue(output.strip())

    def test_api_evaluates_and_verifies_a_persisted_series_policy(self):
        value = self.build_series((self.ready_history("api:ready"),), "api:series")
        evaluation = self.evaluate((self.ready_history("api:ready"),), maximum_held_histories=1)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            series_directory = root / "series"
            evaluation_directory = root / "evaluation"
            from glio_noncode import write_decision_assurance_history_series

            write_decision_assurance_history_series(value, series_directory)
            self.write_evaluation(evaluation, evaluation_directory)
            server = create_server("127.0.0.1", 0)
            server.glio_assurance_history_series_directory = str(series_directory)
            server.glio_assurance_history_series_policy_directory = str(evaluation_directory)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decisions/assurance-history-series/policy"
                summary = json.loads(urlopen(base + "?format=summary", timeout=10).read().decode())
                self.assertEqual(summary["state"], "passed")
                verified = json.loads(urlopen(base + "/verify", timeout=10).read().decode())
                self.assertTrue(verified["accepted"])
                schema = json.loads(urlopen(base + "/schema", timeout=10).read().decode())
                self.assertFalse(schema["additionalProperties"])
                capabilities = json.loads(urlopen(base + "/capabilities", timeout=10).read().decode())
                self.assertEqual(capabilities["checks"]["count"], 9)
                markdown = urlopen(base + "?" + urlencode({"format": "markdown"}), timeout=10).read().decode()
                self.assertIn("# Federation Review Decision Assurance History Series Policy Evaluation", markdown)
            finally:
                server.shutdown()
                thread.join(timeout=10)


class PolicyBoundaryMatrixTests(PolicyFixture):
    """Exercise policy boundaries independently so one rule cannot mask another."""

    def test_empty_series_fails_coverage_and_is_not_release_ready(self):
        value = policy.evaluate_decision_assurance_history_series_policy(self.build_series(), self.policy_value())
        self.assertEqual(value.state, "blocked")
        self.assertFalse(value.accepted)
        self.assertFalse(value.release_ready)
        self.assertEqual(value.check_count, 9)
        self.assertEqual(value.passed_count, 5)
        self.assertEqual(value.blocker_count, 4)
        self.assertEqual({item.kind for item in value.checks if not item.passed}, {"minimum-histories", "minimum-observations", "current-acceptance", "current-release-readiness"})

    def test_zero_minimums_still_require_no_blockers_when_requested(self):
        value = self.evaluate((), minimum_histories=0, minimum_observations=0, require_current_accepted=False, require_current_release_ready=False)
        self.assertEqual(value.state, "passed")
        self.assertTrue(value.accepted)
        self.assertTrue(value.release_ready)
        self.assertEqual(value.check_count, 9)
        self.assertEqual(value.passed_count, 9)

    def test_blocked_ceiling_boundary_is_inclusive(self):
        one_blocked = self.evaluate((self.blocked_history("history:blocked"),), maximum_blocked_histories=1, require_current_accepted=False, require_current_release_ready=False)
        self.assertTrue(next(item for item in one_blocked.checks if item.kind == "blocked-ceiling").passed)
        two_blocked = self.evaluate((self.blocked_history("history:blocked-a"), self.blocked_history("history:blocked-b")), maximum_blocked_histories=1, require_current_accepted=False, require_current_release_ready=False)
        self.assertFalse(next(item for item in two_blocked.checks if item.kind == "blocked-ceiling").passed)
        self.assertEqual(two_blocked.state, "blocked")

    def test_held_ceiling_boundary_is_inclusive_and_optional(self):
        one_held = self.evaluate((self.held_history("history:held"),), maximum_held_histories=1, require_current_accepted=False, require_current_release_ready=False)
        self.assertTrue(next(item for item in one_held.checks if item.kind == "held-ceiling").passed)
        two_held = self.evaluate((self.held_history("history:held-a"), self.held_history("history:held-b")), maximum_held_histories=1, require_current_accepted=False, require_current_release_ready=False)
        held_check = next(item for item in two_held.checks if item.kind == "held-ceiling")
        self.assertFalse(held_check.passed)
        self.assertFalse(held_check.required)
        self.assertEqual(two_held.state, "hold")
        self.assertTrue(two_held.accepted)
        self.assertFalse(two_held.release_ready)

    def test_observation_minimum_is_independent_from_history_minimum(self):
        history_value = self.ready_history("history:observation")
        high_observation = self.evaluate((history_value,), minimum_histories=1, minimum_observations=2)
        self.assertTrue(next(item for item in high_observation.checks if item.kind == "minimum-histories").passed)
        self.assertFalse(next(item for item in high_observation.checks if item.kind == "minimum-observations").passed)
        high_history = self.evaluate((history_value,), minimum_histories=2, minimum_observations=1)
        self.assertFalse(next(item for item in high_history.checks if item.kind == "minimum-histories").passed)
        self.assertTrue(next(item for item in high_history.checks if item.kind == "minimum-observations").passed)

    def test_acceptance_and_release_readiness_requirements_can_be_disabled_separately(self):
        held = self.held_history("history:held")
        require_both = policy.evaluate_decision_assurance_history_series_policy(self.build_series((held,)), self.policy_value(maximum_held_histories=1))
        self.assertFalse(require_both.accepted)
        self.assertFalse(require_both.release_ready)
        allow_unaccepted = self.evaluate((held,), maximum_held_histories=1, require_current_accepted=False)
        self.assertFalse(allow_unaccepted.accepted)
        self.assertFalse(allow_unaccepted.release_ready)
        allow_unready = self.evaluate((held,), maximum_held_histories=1, require_current_release_ready=False)
        self.assertTrue(allow_unready.accepted)
        self.assertTrue(allow_unready.release_ready)
        allow_both = self.evaluate((held,), maximum_held_histories=1, require_current_accepted=False, require_current_release_ready=False)
        self.assertTrue(allow_both.accepted)
        self.assertTrue(allow_both.release_ready)

    def test_mixed_state_rule_is_required_only_when_disallowed(self):
        values = (self.ready_history("history:ready"), self.held_history("history:held"))
        allowed = self.evaluate(values, maximum_held_histories=1, allow_mixed_state=True)
        mixed_allowed_check = next(item for item in allowed.checks if item.kind == "mixed-state")
        self.assertTrue(mixed_allowed_check.passed)
        self.assertFalse(mixed_allowed_check.required)
        disallowed = self.evaluate(values, maximum_held_histories=1, allow_mixed_state=False)
        mixed_disallowed_check = next(item for item in disallowed.checks if item.kind == "mixed-state")
        self.assertFalse(mixed_disallowed_check.passed)
        self.assertTrue(mixed_disallowed_check.required)
        self.assertEqual(disallowed.state, "blocked")

    def test_every_policy_check_uses_the_series_as_evidence(self):
        value = self.evaluate((self.ready_history("history:evidence"),), maximum_held_histories=1)
        self.assertEqual({check.evidence_address for check in value.checks}, {value.series_address})
        self.assertEqual([check.ordinal for check in value.checks], list(range(9)))
        self.assertEqual([check.check_id for check in value.checks], [f"policy:test:check:{index}" for index in range(9)])
        self.assertEqual(len({check.content_address for check in value.checks}), 9)
        for check in value.checks:
            self.assertEqual(policy.address_decision_assurance_history_series_policy_check(check), check.content_address)

    def test_evaluation_address_changes_with_policy_and_series_content(self):
        first = self.evaluate((self.ready_history("history:first"),), maximum_held_histories=1)
        second = self.evaluate((self.ready_history("history:first"),), maximum_held_histories=2)
        third = self.evaluate((self.ready_history("history:second"),), maximum_held_histories=1)
        self.assertNotEqual(first.policy.content_address, second.policy.content_address)
        self.assertNotEqual(first.content_address, second.content_address)
        self.assertNotEqual(first.series_address, third.series_address)
        self.assertNotEqual(first.content_address, third.content_address)
        self.assertEqual(policy.address_decision_assurance_history_series_policy_evaluation(first), first.content_address)

    def test_policy_evaluation_to_dict_contains_only_public_fields(self):
        value = self.evaluate((self.ready_history("history:public-evaluation"),), maximum_held_histories=1)
        payload = canonical_json(value.to_dict()).casefold()
        self.assertNotIn(str(self.real_packet()).casefold(), payload)
        self.assertNotIn("source_path", payload)
        self.assertNotIn("filesystem", payload)
        for forbidden in ("agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "token", "user"):
            self.assertNotIn(f'"{forbidden}"', payload)

    def test_policy_ids_are_bounded_and_do_not_affect_rule_meaning(self):
        left = self.evaluate((self.ready_history("history:id"),), policy_id="policy:left", maximum_held_histories=1)
        right = self.evaluate((self.ready_history("history:id"),), policy_id="policy:right", maximum_held_histories=1)
        self.assertEqual(left.state, right.state)
        self.assertEqual(left.check_count, right.check_count)
        self.assertNotEqual(left.policy.content_address, right.policy.content_address)
        self.assertNotEqual(left.content_address, right.content_address)
        with self.assertRaises(ValidationError):
            self.policy_value(policy_id="")
        with self.assertRaises(ValidationError):
            self.policy_value(policy_id="x" * 257)

    def test_policy_schema_required_fields_match_the_typed_contract(self):
        schema = policy.decision_assurance_history_series_policy_schema()
        self.assertEqual(schema["properties"]["version"]["const"], policy.VERSION)
        self.assertEqual(schema["properties"]["boundary"]["const"], policy.BOUNDARY)
        self.assertEqual(schema["properties"]["minimum_histories"]["maximum"], policy.MAX_HISTORIES)
        self.assertEqual(schema["properties"]["minimum_observations"]["maximum"], policy.MAX_OBSERVATIONS)
        self.assertIn("content_address", schema["required"])
        check_schema = policy.decision_assurance_history_series_policy_check_schema()
        self.assertEqual(check_schema["properties"]["ordinal"]["maximum"], policy.MAX_CHECKS)
        evaluation_schema = policy.decision_assurance_history_series_policy_evaluation_schema()
        self.assertEqual(evaluation_schema["properties"]["check_count"]["maximum"], policy.MAX_CHECKS)
        self.assertEqual(set(evaluation_schema["required"]), {"series_address", "series_id", "policy_id", "policy_address", "check_count", "state", "accepted", "release_ready", "content_address"})

    def test_capability_projection_is_deterministic_and_self_describing(self):
        first = policy.capabilities()
        second = policy.capabilities()
        self.assertEqual(first, second)
        self.assertEqual(first["version"], policy.VERSION)
        self.assertEqual(first["boundary"], policy.BOUNDARY)
        self.assertEqual(first["policy"]["maximum_histories"], policy.MAX_HISTORIES)
        self.assertEqual(first["policy"]["maximum_observations"], policy.MAX_OBSERVATIONS)
        self.assertEqual(first["policy"]["maximum_checks"], policy.MAX_CHECKS)
        self.assertIn("blocked-ceiling", first["checks"]["required_rules"])
        self.assertIn("held-ceiling", first["checks"]["optional_rules"])
        self.assertEqual(first["persistence"]["files"], list(policy.FILES))

    def test_policy_evaluation_replay_is_stable_after_round_trip(self):
        value = self.evaluate((self.ready_history("history:round-trip"),), maximum_held_histories=1)
        mapped = policy.decision_assurance_history_series_policy_evaluation_from_mapping(value.to_dict())
        self.assertEqual(policy.decision_assurance_history_series_policy_evaluation_json(mapped), policy.decision_assurance_history_series_policy_evaluation_json(value))
        self.assertEqual(policy.decision_assurance_history_series_policy_evaluation_csv(mapped), policy.decision_assurance_history_series_policy_evaluation_csv(value))
        self.assertEqual(policy.render_decision_assurance_history_series_policy_evaluation_markdown(mapped), policy.render_decision_assurance_history_series_policy_evaluation_markdown(value))

    def test_policy_evaluation_rejects_unknown_fields_at_every_mapping_boundary(self):
        value = self.evaluate((self.ready_history("history:strict"),), maximum_held_histories=1)
        body = value.policy.to_dict()
        body["unexpected"] = True
        with self.assertRaises(ValidationError):
            policy.decision_assurance_history_series_policy_from_mapping(body)
        body = value.checks[0].to_dict()
        body["unexpected"] = True
        with self.assertRaises(ValidationError):
            policy.decision_assurance_history_series_policy_check_from_mapping(body)
        body = value.to_dict()
        body["unexpected"] = True
        with self.assertRaises(ValidationError):
            policy.decision_assurance_history_series_policy_evaluation_from_mapping(body)

    def test_policy_persistence_loader_rejects_directory_and_file_inputs(self):
        value = self.evaluate((self.ready_history("history:input"),), maximum_held_histories=1)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(ValidationError):
                policy.load_decision_assurance_history_series_policy_evaluation(root / "missing")
            file_path = root / "file"
            file_path.write_text("x")
            with self.assertRaises(ValidationError):
                policy.load_decision_assurance_history_series_policy_evaluation(file_path)
            destination = root / "evaluation"
            self.write_evaluation(value, destination)
            with self.assertRaises(ValidationError):
                self.write_evaluation(value, destination)

    def test_policy_persistence_rejects_manifest_contract_tamper(self):
        value = self.evaluate((self.ready_history("history:manifest"),), maximum_held_histories=1)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "evaluation"
            self.write_evaluation(value, destination)
            manifest_path = destination / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["artifact_count"] = 3
            manifest_path.write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                policy.load_decision_assurance_history_series_policy_evaluation(destination)
            self.write_evaluation(value, destination, overwrite=True)
            manifest = json.loads(manifest_path.read_text())
            manifest["files"] = ["manifest.json"]
            manifest_path.write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                policy.load_decision_assurance_history_series_policy_evaluation(destination)

    def test_policy_persistence_rejects_nested_evaluation_linkage_tamper(self):
        value = self.evaluate((self.ready_history("history:nested"),), maximum_held_histories=1)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "evaluation"
            self.write_evaluation(value, destination)
            evaluation_path = destination / "evaluation.json"
            body = json.loads(evaluation_path.read_text())
            body["policy_address"] = "policy:tampered"
            evaluation_path.write_bytes(canonical_bytes(body))
            with self.assertRaises(ValidationError):
                policy.load_decision_assurance_history_series_policy_evaluation(destination)

    def test_policy_rules_handle_a_long_series_with_conserved_counts(self):
        histories = tuple(self.ready_history(f"history:ready-{index:02d}") for index in range(4))
        value = self.evaluate(histories, minimum_histories=4, minimum_observations=4, maximum_held_histories=0, maximum_blocked_histories=0)
        self.assertEqual(value.state, "passed")
        self.assertEqual(value.check_count, 9)
        self.assertEqual(value.passed_count, 9)
        self.assertEqual(value.warning_count, 0)
        self.assertEqual(value.blocker_count, 0)
        self.assertEqual(value.series_id, "series:test")
        self.assertEqual(value.policy.minimum_histories, 4)

    def test_policy_rules_handle_a_long_series_with_one_optional_failure(self):
        histories = tuple(self.ready_history(f"history:ready-{index:02d}") for index in range(4)) + (self.held_history("history:held"),)
        value = self.evaluate(histories, minimum_histories=5, minimum_observations=5, maximum_held_histories=0, require_current_release_ready=False)
        self.assertEqual(value.state, "hold")
        self.assertTrue(value.accepted)
        self.assertFalse(value.release_ready)
        self.assertEqual(value.warning_count, 1)
        self.assertEqual(value.blocker_count, 0)
        self.assertFalse(next(item for item in value.checks if item.kind == "held-ceiling").passed)

    def test_all_state_and_readiness_fields_are_boolean_in_serialized_evaluation(self):
        value = self.evaluate((self.ready_history("history:booleans"),), maximum_held_histories=1)
        body = value.to_dict()
        for field in ("accepted", "release_ready"):
            self.assertIs(type(body[field]), bool)
        for check in body["checks"]:
            self.assertIs(type(check["passed"]), bool)
            self.assertIs(type(check["required"]), bool)

    def test_policy_evaluation_summary_is_smaller_than_full_public_projection(self):
        value = self.evaluate((self.ready_history("history:summary"),), maximum_held_histories=1)
        summary = value.summary()
        full = value.to_dict()
        self.assertLess(len(canonical_json(summary)), len(canonical_json(full)))
        self.assertNotIn("checks", summary)
        self.assertNotIn("policy", summary)
        self.assertEqual(summary["check_count"], 9)
        self.assertEqual(summary["state"], "passed")

    def test_policy_evaluation_retains_the_full_policy_snapshot(self):
        value = self.evaluate((self.ready_history("history:policy-snapshot"),), minimum_histories=1, minimum_observations=1, maximum_held_histories=2, maximum_blocked_histories=3, require_current_accepted=True, require_current_release_ready=True, allow_mixed_state=False)
        self.assertEqual(value.to_dict()["policy"], value.policy.to_dict())
        self.assertEqual(value.summary()["policy_id"], value.policy.policy_id)
        self.assertEqual(value.summary()["policy_address"], value.policy.content_address)
        self.assertEqual(value.to_dict()["series_address"], value.series_address)
        self.assertEqual(value.to_dict()["series_id"], value.series_id)
        self.assertEqual(value.to_dict()["check_count"], 9)
        self.assertEqual(value.to_dict()["passed_count"], 9)

    def test_policy_limit_maxima_are_accepted_at_the_declared_boundary(self):
        value = self.policy_value(minimum_histories=policy.MAX_HISTORIES, minimum_observations=policy.MAX_OBSERVATIONS, maximum_held_histories=policy.MAX_HISTORIES, maximum_blocked_histories=policy.MAX_HISTORIES)
        self.assertEqual(value.minimum_histories, policy.MAX_HISTORIES)
        self.assertEqual(value.minimum_observations, policy.MAX_OBSERVATIONS)
        self.assertEqual(value.maximum_held_histories, policy.MAX_HISTORIES)
        self.assertEqual(value.maximum_blocked_histories, policy.MAX_HISTORIES)
        with self.assertRaises(ValidationError):
            self.policy_value(minimum_histories=policy.MAX_HISTORIES + 1)
        with self.assertRaises(ValidationError):
            self.policy_value(minimum_observations=policy.MAX_OBSERVATIONS + 1)
        with self.assertRaises(ValidationError):
            self.policy_value(maximum_held_histories=policy.MAX_HISTORIES + 1)
        with self.assertRaises(ValidationError):
            self.policy_value(maximum_blocked_histories=policy.MAX_HISTORIES + 1)

    def test_policy_evaluation_preserves_check_order_under_failed_rules(self):
        value = self.evaluate((self.blocked_history("history:blocked"), self.held_history("history:held")), minimum_histories=3, minimum_observations=3, maximum_held_histories=0, maximum_blocked_histories=0)
        self.assertEqual([item.ordinal for item in value.checks], list(range(9)))
        self.assertEqual([item.kind for item in value.checks], ["minimum-histories", "minimum-observations", "blocked-ceiling", "held-ceiling", "current-acceptance", "current-release-readiness", "mixed-state", "public-boundary", "aggregate-conservation"])
        self.assertEqual(value.passed_count + value.warning_count + value.blocker_count, value.check_count)
        self.assertEqual(value.blocker_count, sum(not item.passed and item.required for item in value.checks))
        self.assertEqual(value.warning_count, sum(not item.passed and not item.required for item in value.checks))
        self.assertEqual(value.passed_count, sum(item.passed for item in value.checks))

    def test_policy_evaluation_check_ids_are_namespaced_by_policy_id(self):
        left = self.evaluate((self.ready_history("history:namespace"),), policy_id="policy:left", maximum_held_histories=1)
        right = self.evaluate((self.ready_history("history:namespace"),), policy_id="policy:right", maximum_held_histories=1)
        self.assertEqual(left.checks[0].check_id, "policy:left:check:0")
        self.assertEqual(right.checks[0].check_id, "policy:right:check:0")
        self.assertNotEqual(left.checks[0].content_address, right.checks[0].content_address)
        self.assertNotEqual(left.checks[-1].content_address, right.checks[-1].content_address)
        self.assertEqual(len(left.checks), len(right.checks))
        self.assertEqual([item.kind for item in left.checks], [item.kind for item in right.checks])

    def test_policy_evaluation_mapping_rejects_changed_summary_policy_id(self):
        value = self.evaluate((self.ready_history("history:linkage"),), maximum_held_histories=1)
        body = value.to_dict()
        body["policy_id"] = "policy:other"
        with self.assertRaises(ValidationError):
            policy.decision_assurance_history_series_policy_evaluation_from_mapping(body)
        body = value.to_dict()
        body["policy"]["policy_id"] = "policy:other"
        with self.assertRaises(ValidationError):
            policy.decision_assurance_history_series_policy_evaluation_from_mapping(body)
        body = value.to_dict()
        body["checks"][0]["check_id"] = "policy:other:check:0"
        with self.assertRaises(ValidationError):
            policy.decision_assurance_history_series_policy_evaluation_from_mapping(body)

    def test_policy_persistence_artifact_receipts_are_canonical_and_complete(self):
        value = self.evaluate((self.ready_history("history:receipts"),), maximum_held_histories=1)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "evaluation"
            self.write_evaluation(value, destination)
            manifest = json.loads((destination / "manifest.json").read_text())
            self.assertEqual(tuple(manifest["files"]), policy.FILES)
            self.assertEqual(len(manifest["artifacts"]), manifest["artifact_count"])
            for artifact in manifest["artifacts"]:
                path = destination / artifact["name"]
                raw = path.read_bytes()
                self.assertEqual(artifact["bytes"], len(raw))
                self.assertEqual(artifact["byte_address"], hash_bytes(raw))
                self.assertEqual(canonical_bytes(json.loads(raw.decode())), raw)

    def test_policy_markdown_is_deterministic_for_the_same_evaluation(self):
        value = self.evaluate((self.ready_history("history:markdown"),), maximum_held_histories=1)
        first = policy.render_decision_assurance_history_series_policy_evaluation_markdown(value)
        second = policy.render_decision_assurance_history_series_policy_evaluation_markdown(value)
        self.assertEqual(first, second)
        self.assertIn("series_address", first)
        self.assertIn("policy_address", first)
        self.assertIn("minimum-histories", first)
        self.assertIn("public-boundary", first)
        self.assertTrue(first.endswith("\n"))

    def test_policy_capability_rule_partition_has_no_duplicates(self):
        capabilities = policy.capabilities()
        required = capabilities["checks"]["required_rules"]
        optional = capabilities["checks"]["optional_rules"]
        self.assertEqual(len(required), len(set(required)))
        self.assertEqual(len(optional), len(set(optional)))
        self.assertFalse(set(required) & set(optional))
        self.assertEqual(set(required) | set(optional), {item.kind for item in self.evaluate((self.ready_history("history:rules"),), maximum_held_histories=1).checks})


class PolicyOutputContractTests(PolicyFixture):
    def test_policy_csv_is_single_record_with_stable_columns(self):
        value = self.policy_value(minimum_histories=2, minimum_observations=3, maximum_held_histories=4, maximum_blocked_histories=5)
        rendered = policy.decision_assurance_history_series_policy_csv(value)
        rows = rendered.splitlines()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].split(","), [
            "policy_id",
            "minimum_histories",
            "minimum_observations",
            "maximum_held_histories",
            "maximum_blocked_histories",
            "require_current_accepted",
            "require_current_release_ready",
            "allow_mixed_state",
            "content_address",
        ])
        self.assertIn("policy:test", rows[1])
        self.assertIn(value.content_address, rows[1])

    def test_evaluation_csv_has_one_row_per_check_and_preserves_ordinals(self):
        value = self.evaluate((self.ready_history("history:csv"),), maximum_held_histories=1)
        rendered = policy.decision_assurance_history_series_policy_evaluation_csv(value)
        rows = rendered.splitlines()
        self.assertEqual(len(rows), value.check_count + 1)
        self.assertEqual(rows[0].split(","), [
            "ordinal",
            "check_id",
            "kind",
            "passed",
            "required",
            "detail",
            "evidence_address",
            "content_address",
        ])
        for expected, row in enumerate(rows[1:]):
            self.assertTrue(row.startswith(f"{expected},"))
        self.assertEqual(len({row.rsplit(",", 1)[-1] for row in rows[1:]}), value.check_count)

    def test_json_exports_are_canonical_and_include_nested_policy_and_checks(self):
        value = self.evaluate((self.ready_history("history:json"),), maximum_held_histories=1)
        rendered = policy.decision_assurance_history_series_policy_evaluation_json(value)
        self.assertEqual(rendered.encode("utf-8"), canonical_bytes(json.loads(rendered)))
        body = json.loads(rendered)
        self.assertEqual(body["policy"]["policy_id"], value.policy.policy_id)
        self.assertEqual(body["policy"]["content_address"], value.policy.content_address)
        self.assertEqual(len(body["checks"]), value.check_count)
        self.assertEqual(body["checks"][0]["ordinal"], 0)
        self.assertEqual(body["checks"][-1]["ordinal"], value.check_count - 1)
        self.assertEqual(body["content_address"], value.content_address)
        self.assertEqual(body["state"], value.state)
        self.assertEqual(body["accepted"], value.accepted)
        self.assertEqual(body["release_ready"], value.release_ready)

    def test_markdown_contains_summary_before_check_records_and_no_source_paths(self):
        value = self.evaluate((self.ready_history("history:markdown-layout"),), maximum_held_histories=1)
        rendered = policy.render_decision_assurance_history_series_policy_evaluation_markdown(value)
        self.assertLess(rendered.index("## Summary"), rendered.index("## Records"))
        self.assertLess(rendered.index("series_address"), rendered.index("minimum-histories"))
        self.assertLess(rendered.index("minimum-histories"), rendered.index("aggregate-conservation"))
        self.assertNotIn(str(self.real_packet()), rendered)
        self.assertNotIn("source_path", rendered)
        self.assertNotIn("filesystem", rendered)
        self.assertTrue(rendered.count("| policy:") == 0)
        self.assertEqual(rendered, policy.render_decision_assurance_history_series_policy_evaluation_markdown(value))

    def test_all_public_renderers_verify_address_integrity_before_output(self):
        value = self.evaluate((self.ready_history("history:renderer-integrity"),), maximum_held_histories=1)
        policy_body = value.policy.to_dict()
        policy_body["content_address"] = "pending:renderer-integrity-policy"
        tampered_policy = policy.DecisionAssuranceHistorySeriesPolicy(**policy_body)
        tampered_policy.content_address = "policy:tampered-render"
        with self.assertRaises(ValidationError):
            policy.decision_assurance_history_series_policy_json(tampered_policy)
        tampered_evaluation = policy.DecisionAssuranceHistorySeriesPolicyEvaluation(
            series_address=value.series_address,
            series_id=value.series_id,
            policy=value.policy,
            check_count=value.check_count,
            passed_count=value.passed_count,
            warning_count=value.warning_count,
            blocker_count=value.blocker_count,
            state=value.state,
            accepted=value.accepted,
            release_ready=value.release_ready,
            checks=value.checks,
            content_address="pending:renderer-integrity-evaluation",
        )
        tampered_evaluation.content_address = "evaluation:tampered-render"
        for renderer in (
            policy.decision_assurance_history_series_policy_evaluation_json,
            policy.decision_assurance_history_series_policy_evaluation_csv,
            policy.render_decision_assurance_history_series_policy_evaluation_markdown,
        ):
            with self.subTest(renderer=renderer.__name__), self.assertRaises(ValidationError):
                renderer(tampered_evaluation)


if __name__ == "__main__":
    unittest.main()
