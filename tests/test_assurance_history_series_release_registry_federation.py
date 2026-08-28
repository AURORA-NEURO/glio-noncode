"""Deep contracts for release-registry federation."""

# ruff: noqa: E501

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from urllib.request import urlopen

from glio_noncode import assurance_history_series_release_registry as registry
from glio_noncode import assurance_history_series_release_registry_federation as federation
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import hash_bytes
from tests.test_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_review_decision_ledger_assurance_history_series_release import ReleaseFixture


class FederationFixture(unittest.TestCase):
    fixture = ReleaseFixture("runTest")

    def ready_registry(self, suffix: str = "ready"):
        package = self.fixture.ready_package(package_id=f"package:{suffix}", release_id=f"release:{suffix}")
        return registry.build_decision_assurance_history_series_release_registry((package,), registry_id=f"registry:{suffix}")

    def held_registry(self, suffix: str = "held"):
        package = self.fixture.held_package(package_id=f"package:{suffix}", release_id=f"release:{suffix}")
        return registry.build_decision_assurance_history_series_release_registry((package,), registry_id=f"registry:{suffix}")

    def blocked_registry(self, suffix: str = "blocked"):
        package = self.fixture.blocked_package(package_id=f"package:{suffix}", release_id=f"release:{suffix}")
        return registry.build_decision_assurance_history_series_release_registry((package,), registry_id=f"registry:{suffix}")

    @staticmethod
    def build(values, policy=None):
        return federation.build_federation(values, federation_id="federation:test", policy=policy)

    @staticmethod
    def write(value, path, **kwargs):
        return federation.write_federation(value, path, **kwargs)

    @staticmethod
    def write_diff(value, path, **kwargs):
        return federation.write_federation_diff(value, path, **kwargs)


class FederationCoreTests(FederationFixture):
    def test_ready_registries_are_sorted_and_release_ready(self):
        value = self.build((self.ready_registry("z"), self.ready_registry("a")))
        self.assertEqual(value.federation.state, "ready")
        self.assertTrue(value.federation.accepted)
        self.assertTrue(value.federation.release_ready)
        self.assertEqual((value.federation.member_count, value.federation.package_count), (2, 2))
        self.assertEqual([member.registry_id for member in value.federation.members], ["registry:a", "registry:z"])
        self.assertEqual((value.federation.ready_count, value.federation.hold_count, value.federation.blocked_count), (2, 0, 0))
        self.assertEqual((value.federation.accepted_count, value.federation.release_ready_count), (2, 2))

    def test_federation_preserves_source_registry_and_entry_provenance(self):
        value = self.build((self.ready_registry("one"), self.held_registry("two")))
        self.assertEqual([package.registry_id for package in value.federation.packages], ["registry:one", "registry:two"])
        for package in value.federation.packages:
            member = next(item for item in value.federation.members if item.registry_id == package.registry_id)
            self.assertEqual(package.registry_address, member.registry_address)
            self.assertTrue(package.registry_entry_address.startswith(registry.ENTRY_PREFIX + ":"))
            self.assertTrue(package.package_address.startswith("module-workbench"))
            self.assertTrue(package.release_address.startswith("module-workbench"))

    def test_input_order_does_not_change_any_address(self):
        one, two = self.ready_registry("one"), self.held_registry("two")
        first = self.build((one, two))
        second = self.build((two, one))
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.federation.content_address, second.federation.content_address)
        self.assertEqual(first.verification.content_address, second.verification.content_address)
        self.assertEqual(first.policy_evaluation.content_address, second.policy_evaluation.content_address)
        self.assertEqual(first.runtime.content_address, second.runtime.content_address)

    def test_held_member_produces_accepted_but_not_ready_federation(self):
        value = self.build((self.ready_registry("ready"), self.held_registry("held")))
        self.assertEqual((value.federation.state, value.federation.accepted, value.federation.release_ready), ("held", True, False))
        self.assertEqual((value.policy_evaluation.state, value.policy_evaluation.accepted, value.policy_evaluation.release_ready), ("held", True, False))
        self.assertEqual((value.runtime.state, value.runtime.accepted, value.runtime.release_ready), ("held", True, False))
        self.assertGreater(value.policy_evaluation.failed_count, 0)
        self.assertEqual(value.policy_evaluation.required_failure_count, 0)

    def test_blocked_member_fails_closed_across_policy_and_runtime(self):
        value = self.build((self.ready_registry("ready"), self.blocked_registry("blocked")))
        self.assertEqual(value.federation.state, "blocked")
        self.assertFalse(value.federation.accepted)
        self.assertFalse(value.federation.release_ready)
        self.assertEqual(value.policy_evaluation.state, "blocked")
        self.assertFalse(value.policy_evaluation.accepted)
        self.assertEqual(value.runtime.state, "blocked")
        self.assertFalse(value.runtime.accepted)
        self.assertFalse(value.runtime.release_ready)
        self.assertGreater(value.policy_evaluation.required_failure_count, 0)

    def test_empty_federation_requires_explicit_policy_permission(self):
        with self.assertRaises(ValidationError):
            self.build(())
        policy = federation.default_federation_policy(allow_empty=True)
        value = self.build((), policy=policy)
        self.assertEqual(value.federation.state, "empty")
        self.assertTrue(value.federation.accepted)
        self.assertFalse(value.federation.release_ready)
        self.assertEqual(value.runtime.state, "empty")
        self.assertTrue(value.runtime.accepted)

    def test_custom_policy_can_allow_held_members_but_not_blocked_members(self):
        policy = federation.default_federation_policy(maximum_blocked_members=0, maximum_held_members=1)
        held = self.build((self.held_registry("held"),), policy=policy)
        self.assertEqual((held.policy_evaluation.state, held.policy_evaluation.accepted), ("held", True))
        policy = federation.default_federation_policy(maximum_blocked_members=1, maximum_held_members=1)
        blocked = self.build((self.blocked_registry("blocked"),), policy=policy)
        self.assertEqual((blocked.policy_evaluation.state, blocked.policy_evaluation.accepted), ("blocked", False))

    def test_policy_minimum_counts_fail_as_required_policy_checks(self):
        policy = federation.default_federation_policy(minimum_member_count=2, minimum_package_count=2)
        value = self.build((self.ready_registry("one"),), policy=policy)
        failed = {check.check_id for check in value.policy_evaluation.checks if not check.passed}
        self.assertEqual(failed, {"minimum-members", "minimum-packages"})
        self.assertEqual(value.policy_evaluation.required_failure_count, 2)
        self.assertEqual(value.runtime.state, "blocked")

    def test_non_release_ready_policy_can_publish_a_held_runtime(self):
        policy = federation.default_federation_policy(require_all_release_ready=False)
        value = self.build((self.held_registry("held"),), policy=policy)
        self.assertEqual(value.policy_evaluation.state, "ready")
        self.assertTrue(value.policy_evaluation.accepted)
        self.assertTrue(value.policy_evaluation.release_ready)
        self.assertEqual(value.runtime.state, "ready")
        self.assertTrue(value.runtime.release_ready)

    def test_member_and_package_content_addresses_are_recomputed(self):
        value = self.build((self.ready_registry("one"),))
        member = value.federation.members[0]
        package = value.federation.packages[0]
        self.assertEqual(federation.address_federation_member(member), member.content_address)
        self.assertEqual(federation.address_federation_package(package), package.content_address)
        self.assertEqual(federation.address_federation(value.federation), value.federation.content_address)
        self.assertEqual(federation.address_federation_policy(value.policy), value.policy.content_address)
        self.assertEqual(federation.address_federation_verification(value.verification), value.verification.content_address)
        self.assertEqual(federation.address_policy_evaluation(value.policy_evaluation), value.policy_evaluation.content_address)
        self.assertEqual(federation.address_federation_runtime(value.runtime), value.runtime.content_address)

    def test_bundle_links_all_closure_documents(self):
        value = self.build((self.ready_registry("one"),))
        self.assertEqual(value.verification.federation_address, value.federation.content_address)
        self.assertEqual(value.policy_evaluation.federation_address, value.federation.content_address)
        self.assertEqual(value.policy_evaluation.policy_address, value.policy.content_address)
        self.assertEqual(value.runtime.federation_address, value.federation.content_address)
        self.assertEqual(value.runtime.policy_address, value.policy.content_address)
        self.assertEqual(value.runtime.policy_evaluation_address, value.policy_evaluation.content_address)
        self.assertEqual(value.runtime.accepted, value.verification.accepted and value.policy_evaluation.accepted)

    def test_builder_rejects_non_typed_duplicate_and_over_capacity_inputs(self):
        with self.assertRaises(ValidationError):
            self.build([object()])
        one = self.ready_registry("one")
        with self.assertRaises(ValidationError):
            self.build((one, one))
        with self.assertRaises(ValidationError):
            federation.build_federation((one,) * (federation.MAX_REGISTRIES + 1))

    def test_registry_identity_is_unique_even_if_package_payloads_are_equal(self):
        first = self.ready_registry("first")
        second = registry.build_decision_assurance_history_series_release_registry(first.entries and (self.fixture.ready_package(package_id="package:second", release_id="release:second"),), registry_id="registry:first")
        with self.assertRaises(ValidationError):
            self.build((first, second))

    def test_cross_registry_package_ids_are_source_scoped(self):
        first_package = self.fixture.ready_package(package_id="package:shared", release_id="release:first")
        second_package = self.fixture.held_package(package_id="package:shared", release_id="release:second")
        first = registry.build_decision_assurance_history_series_release_registry((first_package,), registry_id="registry:first")
        second = registry.build_decision_assurance_history_series_release_registry((second_package,), registry_id="registry:second")
        value = self.build((first, second))
        self.assertEqual({(item.registry_id, item.package_id) for item in value.federation.packages}, {("registry:first", "package:shared"), ("registry:second", "package:shared")})
        self.assertEqual(len(value.federation.packages), 2)

    def test_mapping_round_trip_preserves_nested_typed_closure(self):
        value = self.build((self.ready_registry("one"), self.held_registry("two")))
        restored = federation.federation_bundle_from_mapping(value.to_dict())
        self.assertEqual(restored.to_dict(), value.to_dict())
        self.assertEqual(restored.summary(), value.summary())

    def test_unknown_fields_are_rejected_at_every_mapping_boundary(self):
        value = self.build((self.ready_registry("one"),))
        cases = (
            (value.federation.to_dict(), federation.federation_from_mapping),
            (value.policy.to_dict(), federation.federation_policy_from_mapping),
            (value.verification.to_dict(), federation.federation_verification_from_mapping),
            (value.policy_evaluation.to_dict(), federation.policy_evaluation_from_mapping),
            (value.runtime.to_dict(), federation.federation_runtime_from_mapping),
            (value.federation.members[0].to_dict(), federation.federation_member_from_mapping),
            (value.federation.packages[0].to_dict(), federation.federation_package_from_mapping),
        )
        for body, parser in cases:
            with self.subTest(parser=parser.__name__):
                body = dict(body)
                body["unknown"] = True
                with self.assertRaises(ValidationError):
                    parser(body)

    def test_public_projections_are_path_free_and_identity_free(self):
        value = self.build((self.ready_registry("one"), self.held_registry("two")))
        payload = json.dumps(value.to_dict(), sort_keys=True).casefold()
        for forbidden in ("source_path", "filesystem", "agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "token", "user"):
            self.assertNotIn(f'"{forbidden}"', payload)
        self.assertNotIn("c:\\", payload)
        self.assertNotIn("/users/", payload)

    def test_structural_verification_has_conserved_required_checks(self):
        value = self.build((self.ready_registry("one"), self.held_registry("two")))
        verification = federation.verify_federation_verification(value.verification)
        self.assertTrue(verification.accepted)
        self.assertEqual(verification.check_count, 7)
        self.assertEqual(verification.passed_count + verification.failed_count, verification.check_count)
        self.assertEqual(verification.required_failure_count, 0)
        self.assertEqual({check.severity for check in verification.checks}, {"required"})

    def test_policy_and_runtime_checks_have_stable_ordinals_and_addresses(self):
        value = self.build((self.ready_registry("one"), self.held_registry("two")))
        self.assertEqual([check.ordinal for check in value.policy_evaluation.checks], list(range(7)))
        self.assertEqual([stage.ordinal for stage in value.runtime.stages], list(range(federation.MAX_STAGES)))
        self.assertEqual(len({check.content_address for check in value.policy_evaluation.checks}), 7)
        self.assertEqual(len({stage.content_address for stage in value.runtime.stages}), federation.MAX_STAGES)
        for stage in value.runtime.stages:
            self.assertEqual(federation.address_federation_stage(stage), stage.content_address)


class FederationVerificationTests(FederationFixture):
    def test_mutating_federation_summary_fails_verification(self):
        value = self.build((self.ready_registry("one"),))
        value.federation.package_count = 9
        with self.assertRaises(ValidationError):
            federation.verify_federation(value.federation)

    def test_mutating_member_or_package_address_fails_verification(self):
        value = self.build((self.ready_registry("one"),))
        value.federation.members[0].registry_id = "registry:tampered"
        with self.assertRaises(ValidationError):
            federation.verify_federation(value.federation)
        value = self.build((self.ready_registry("two"),))
        value.federation.packages[0].content_address = "package:tampered"
        with self.assertRaises(ValidationError):
            federation.verify_federation(value.federation)

    def test_mutating_verification_policy_or_runtime_receipt_fails(self):
        value = self.build((self.ready_registry("one"),))
        value.verification.passed_count = 0
        with self.assertRaises(ValidationError):
            federation.verify_federation_bundle(value)
        value = self.build((self.ready_registry("two"),))
        value.policy_evaluation.release_ready = False
        with self.assertRaises(ValidationError):
            federation.verify_federation_bundle(value)
        value = self.build((self.ready_registry("three"),))
        value.runtime.stage_count = 1
        with self.assertRaises(ValidationError):
            federation.verify_federation_bundle(value)

    def test_policy_evaluation_rejects_invalid_bounds_and_addresses(self):
        with self.assertRaises(ValidationError):
            federation.default_federation_policy(minimum_member_count=0)
        with self.assertRaises(ValidationError):
            federation.default_federation_policy(maximum_held_members=federation.MAX_REGISTRIES + 1)
        value = self.build((self.ready_registry("one"),))
        with self.assertRaises(ValidationError):
            federation.DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicyEvaluation(
                value.federation.content_address,
                "bad",
                value.policy_evaluation.state,
                value.policy_evaluation.accepted,
                value.policy_evaluation.release_ready,
                value.policy_evaluation.check_count,
                value.policy_evaluation.passed_count,
                value.policy_evaluation.failed_count,
                value.policy_evaluation.required_failure_count,
                value.policy_evaluation.checks,
                value.policy_evaluation.content_address,
            )

    def test_direct_stage_and_diff_item_shapes_are_fail_closed(self):
        value = self.build((self.ready_registry("one"),))
        stage = value.runtime.stages[0].to_dict()
        stage["accepted"] = False
        stage["content_address"] = "pending:stage"
        with self.assertRaises(ValidationError):
            federation.federation_stage_from_mapping(stage)
        baseline = self.build((self.ready_registry("same"),))
        candidate = self.build((self.blocked_registry("same"),))
        diff = federation.build_federation_diff(baseline, candidate)
        body = diff.items[0].to_dict()
        body["action"] = "added"
        with self.assertRaises(ValidationError):
            federation.federation_diff_item_from_mapping(body)


class FederationPersistenceTests(FederationFixture):
    def test_persistence_has_exact_eight_files_and_manifest_receipts(self):
        value = self.build((self.ready_registry("one"), self.held_registry("two")))
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "federation"
            self.write(value, destination)
            self.assertEqual({item.name for item in destination.iterdir()}, set(federation.FILES))
            loaded = federation.load_federation(destination)
            self.assertEqual(loaded.to_dict(), value.to_dict())
            manifest = json.loads((destination / federation.MANIFEST_NAME).read_text(encoding="utf-8"))
            self.assertEqual(tuple(manifest["files"]), federation.FILES)
            self.assertEqual(manifest["artifact_count"], len(federation.FILES) - 1)
            members_raw = (destination / federation.MEMBERS_NAME).read_bytes()
            receipt = next(item for item in manifest["artifacts"] if item["name"] == federation.MEMBERS_NAME)
            self.assertEqual(receipt["byte_address"], hash_bytes(members_raw, prefix=f"{federation.PREFIX}-file-members"))

    def test_persistence_is_canonical_repeatable_and_overwrite_guarded(self):
        value = self.build((self.ready_registry("one"),))
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "federation"
            self.write(value, destination)
            first = {name: (destination / name).read_bytes() for name in federation.FILES}
            with self.assertRaises(ValidationError):
                self.write(value, destination)
            self.write(value, destination, overwrite=True)
            second = {name: (destination / name).read_bytes() for name in federation.FILES}
            self.assertEqual(first, second)

    def test_persistence_rejects_tampered_documents_and_extra_files(self):
        value = self.build((self.ready_registry("one"), self.held_registry("two")))
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "federation"
            self.write(value, destination)
            for name in (federation.FEDERATION_NAME, federation.MEMBERS_NAME, federation.PACKAGES_NAME, federation.POLICY_NAME, federation.VERIFICATION_NAME, federation.POLICY_EVALUATION_NAME, federation.RUNTIME_NAME):
                original = (destination / name).read_bytes()
                (destination / name).write_bytes(original + b" ")
                with self.assertRaises(ValidationError):
                    federation.load_federation(destination)
                self.write(value, destination, overwrite=True)
            (destination / "unexpected.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                federation.load_federation(destination)

    def test_persistence_rejects_symlinked_documents_when_supported(self):
        value = self.build((self.ready_registry("one"),))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination = root / "federation"
            self.write(value, destination)
            target = root / "target.json"
            target.write_bytes((destination / federation.FEDERATION_NAME).read_bytes())
            try:
                (destination / federation.FEDERATION_NAME).unlink()
                (destination / federation.FEDERATION_NAME).symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation unavailable")
            with self.assertRaises(ValidationError):
                federation.load_federation(destination)

    def test_directory_builder_admits_only_verified_registry_directories(self):
        first_value = self.ready_registry("one")
        second_value = self.held_registry("two")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first_registry = root / "first-registry"
            second_registry = root / "second-registry"
            registry.write_decision_assurance_history_series_release_registry(first_value, first_registry)
            registry.write_decision_assurance_history_series_release_registry(second_value, second_registry)
            built = federation.build_federation_from_directories((second_registry, first_registry), federation_id="federation:test")
            self.assertEqual(built.summary(), self.build((first_value, second_value)).summary())


class FederationQueryExportTests(FederationFixture):
    def test_query_resources_are_bounded_and_conserved(self):
        value = self.build((self.ready_registry("ready"), self.held_registry("held"), self.blocked_registry("blocked")))
        expected = {"summary": 1, "members": 3, "packages": 3, "ready": 1, "held": 1, "blocked": 1, "accepted": 2, "release-ready": 1, "verification-checks": 7, "policy-checks": 7, "stages": 5}
        for resource, count in expected.items():
            with self.subTest(resource=resource):
                result = federation.query_federation(value, resource=resource, limit=federation.MAX_QUERY_ITEMS)
                self.assertEqual((result.total_count, result.returned_count), (count, count))
                self.assertEqual(result.content_address, federation.address_federation_query(result))

    def test_query_pagination_and_text_filter_are_deterministic(self):
        value = self.build((self.ready_registry("alpha"), self.held_registry("beta"), self.blocked_registry("gamma")))
        first = federation.query_federation(value, resource="packages", offset=1, limit=1)
        second = federation.query_federation(value, resource="packages", offset=1, limit=1)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.items[0]["registry_id"], "registry:beta")
        filtered = federation.query_federation(value, resource="packages", text="PACKAGE:GAMMA")
        self.assertEqual(filtered.returned_count, 1)
        self.assertEqual(filtered.items[0]["state"], "blocked")
        filtered = federation.query_federation(value, resource="accepted", accepted=True)
        self.assertEqual(filtered.returned_count, 2)

    def test_query_typed_and_keyword_arguments_cannot_be_mixed(self):
        value = self.build((self.ready_registry("one"),))
        query = federation.FederationQuery(resource="members", limit=1)
        with self.assertRaises(ValidationError):
            federation.query_federation(value, query=query, text="registry")
        with self.assertRaises(ValidationError):
            federation.FederationQuery(resource="invalid")
        with self.assertRaises(ValidationError):
            federation.FederationQuery(limit=0)
        with self.assertRaises(ValidationError):
            federation.FederationQuery(state="hold")

    def test_query_mapping_and_all_exports_are_canonical(self):
        value = self.build((self.ready_registry("one"), self.held_registry("two")))
        result = federation.query_federation(value, resource="packages", limit=1)
        restored = federation.federation_query_from_mapping(result.to_dict())
        self.assertEqual(restored.to_dict(), result.to_dict())
        self.assertEqual(federation.federation_query_json(result), federation.federation_query_json(restored))
        self.assertIn("Federation Query", federation.render_federation_query_markdown(result))
        self.assertGreater(len(federation.federation_query_csv(result).splitlines()), 1)
        self.assertTrue(federation.federation_json(value).startswith("{"))
        self.assertGreater(len(federation.federation_members_csv(value).splitlines()), 1)
        self.assertGreater(len(federation.federation_packages_csv(value).splitlines()), 1)
        self.assertGreater(len(federation.federation_checks_csv(value).splitlines()), 1)
        self.assertGreater(len(federation.federation_policy_checks_csv(value).splitlines()), 1)
        self.assertGreater(len(federation.federation_stages_csv(value).splitlines()), 1)
        self.assertIn("Registry Federation", federation.render_federation_markdown(value))

    def test_query_public_projection_has_no_source_paths_or_private_keys(self):
        value = self.build((self.ready_registry("one"), self.held_registry("two")))
        result = federation.query_federation(value, resource="packages")
        payload = json.dumps(result.to_dict(), sort_keys=True).casefold()
        for forbidden in ("source_path", "filesystem", "agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "token", "user"):
            self.assertNotIn(f'"{forbidden}"', payload)

    def test_summary_query_remains_one_row_under_filters(self):
        value = self.build((self.ready_registry("one"), self.held_registry("two")))
        result = federation.query_federation(value, resource="summary", text="federation:test")
        self.assertEqual(result.returned_count, 1)
        self.assertEqual(result.items[0]["member_count"], 2)


class FederationDiffTests(FederationFixture):
    def test_diff_conserves_member_and_package_actions(self):
        baseline = self.build((self.ready_registry("same"), self.held_registry("removed")))
        candidate = self.build((self.ready_registry("same"), self.blocked_registry("removed"), self.ready_registry("added")))
        value = federation.build_federation_diff(baseline, candidate, diff_id="diff:test")
        self.assertEqual(value.item_count, 6)
        self.assertEqual((value.added_count, value.removed_count, value.unchanged_count, value.changed_count), (2, 0, 2, 2))
        self.assertEqual(value.regressed_count, 2)
        self.assertEqual((value.state, value.release_ready), ("regressed", False))
        self.assertEqual(value.content_address, federation.address_federation_diff(value))

    def test_same_federation_diff_is_unchanged_and_ready(self):
        value = self.build((self.ready_registry("one"), self.held_registry("two")))
        diff = federation.build_federation_diff(value, value)
        self.assertEqual((diff.state, diff.release_ready, diff.regressed_count), ("unchanged", True, 0))
        self.assertEqual(diff.unchanged_count, 4)

    def test_added_and_removed_state_directions_are_explicit(self):
        baseline = self.build((self.blocked_registry("blocked"), self.ready_registry("removed")))
        candidate = self.build((self.ready_registry("blocked"), self.blocked_registry("added")))
        value = federation.build_federation_diff(baseline, candidate)
        items = {item.key: item for item in value.items}
        self.assertEqual(items["member:registry:blocked"].direction, "improved")
        self.assertEqual(items["member:registry:removed"].direction, "regressed")
        self.assertEqual(items["member:registry:added"].direction, "changed")
        self.assertEqual(items["package:registry:blocked/package:blocked"].direction, "improved")

    def test_diff_queries_partition_actions_and_directions(self):
        baseline = self.build((self.ready_registry("same"), self.held_registry("old")))
        candidate = self.build((self.ready_registry("same"), self.ready_registry("new")))
        value = federation.build_federation_diff(baseline, candidate)
        expected = {"summary": 1, "items": 6, "added": 2, "removed": 2, "unchanged": 2, "changed": 0, "improved": 2, "regressed": 2}
        for resource, count in expected.items():
            with self.subTest(resource=resource):
                result = federation.query_federation_diff(value, resource=resource)
                self.assertEqual((result.total_count, result.returned_count), (count, count))

    def test_diff_query_filter_and_mapping_round_trip_are_stable(self):
        baseline = self.build((self.held_registry("same"),))
        candidate = self.build((self.ready_registry("same"), self.ready_registry("added")))
        value = federation.build_federation_diff(baseline, candidate)
        result = federation.query_federation_diff(value, resource="improved", text="SAME")
        self.assertEqual(result.returned_count, 2)
        restored = federation.federation_diff_query_from_mapping(result.to_dict())
        self.assertEqual(restored.to_dict(), result.to_dict())
        self.assertEqual(federation.federation_diff_query_json(result), federation.federation_diff_query_json(restored))
        self.assertIn("Diff Query", federation.render_federation_diff_query_markdown(result))
        self.assertGreater(len(federation.federation_diff_query_csv(result).splitlines()), 1)
        self.assertTrue(federation.federation_diff_json(value).startswith("{"))
        self.assertGreater(len(federation.federation_diff_csv(value).splitlines()), 1)
        self.assertIn("Federation Diff", federation.render_federation_diff_markdown(value))

    def test_diff_mapping_rejects_unknown_fields_and_bad_actions(self):
        baseline = self.build((self.ready_registry("same"),))
        candidate = self.build((self.blocked_registry("same"),))
        value = federation.build_federation_diff(baseline, candidate)
        body = value.to_dict()
        body["unknown"] = True
        with self.assertRaises(ValidationError):
            federation.federation_diff_from_mapping(body)
        body = value.to_dict()
        body["items"][0]["action"] = "added"
        with self.assertRaises(ValidationError):
            federation.federation_diff_from_mapping(body)
        with self.assertRaises(ValidationError):
            federation.FederationDiffQuery(resource="invalid")
        with self.assertRaises(ValidationError):
            federation.FederationDiffQuery(direction="invalid")

    def test_diff_item_addresses_are_unique_and_public(self):
        baseline = self.build((self.ready_registry("one"), self.held_registry("two")))
        candidate = self.build((self.blocked_registry("one"), self.ready_registry("three")))
        value = federation.build_federation_diff(baseline, candidate)
        self.assertEqual(len(value.items), len({item.content_address for item in value.items}))
        payload = json.dumps(value.to_dict(), sort_keys=True).casefold()
        for forbidden in ("source_path", "raw_payload", "agent", "language", "model"):
            self.assertNotIn(f'"{forbidden}"', payload)

    def test_diff_persistence_has_exact_two_files_and_reloads(self):
        baseline = self.build((self.ready_registry("one"),))
        candidate = self.build((self.blocked_registry("one"),))
        value = federation.build_federation_diff(baseline, candidate)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "diff"
            self.write_diff(value, destination)
            self.assertEqual({item.name for item in destination.iterdir()}, set(federation.DIFF_FILES))
            loaded = federation.load_federation_diff(destination)
            self.assertEqual(loaded.to_dict(), value.to_dict())
            manifest = json.loads((destination / federation.MANIFEST_NAME).read_text(encoding="utf-8"))
            self.assertEqual(manifest["diff_address"], value.content_address)
            self.assertEqual(manifest["artifact_count"], 1)

    def test_diff_persistence_rejects_extra_missing_and_tampered_documents(self):
        baseline = self.build((self.ready_registry("one"),))
        candidate = self.build((self.blocked_registry("one"),))
        value = federation.build_federation_diff(baseline, candidate)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "diff"
            self.write_diff(value, destination)
            (destination / federation.DIFF_NAME).write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                federation.load_federation_diff(destination)
            self.write_diff(value, destination, overwrite=True)
            (destination / "extra.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                federation.load_federation_diff(destination)
            (destination / "extra.json").unlink()
            (destination / federation.MANIFEST_NAME).unlink()
            with self.assertRaises(ValidationError):
                federation.load_federation_diff(destination)


class FederationSchemaCapabilityTests(FederationFixture):
    def test_all_contract_schemas_are_closed_and_valid_json_schema(self):
        schemas = (
            federation.federation_schema(),
            federation.federation_member_schema(),
            federation.federation_package_schema(),
            federation.federation_policy_schema(),
            federation.federation_check_schema(),
            federation.federation_verification_schema(),
            federation.federation_policy_check_schema(),
            federation.federation_policy_evaluation_schema(),
            federation.federation_stage_schema(),
            federation.federation_runtime_schema(),
            federation.federation_query_schema(),
            federation.federation_diff_schema(),
            federation.federation_diff_item_schema(),
            federation.federation_diff_query_schema(),
        )
        for schema in schemas:
            with self.subTest(title=schema["title"]):
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
                self.assertFalse(schema["additionalProperties"])
                self.assertTrue(set(schema["required"]) <= set(schema["properties"]))
                self.assertEqual(json.loads(json.dumps(schema)), schema)

    def test_capabilities_describe_exact_transport_and_runtime_contracts(self):
        value = federation.federation_capabilities()
        self.assertEqual(value["package"]["files"], list(federation.FILES))
        self.assertEqual(value["diff"]["files"], list(federation.DIFF_FILES))
        self.assertEqual(value["limits"], {"registries": federation.MAX_REGISTRIES, "packages": federation.MAX_PACKAGES, "checks": federation.MAX_CHECKS, "stages": federation.MAX_STAGES})
        self.assertEqual(value["checks"]["structural_count"], 7)
        self.assertEqual(value["checks"]["policy_count"], 7)
        self.assertFalse(value["public_boundary"]["source_paths"])
        self.assertFalse(value["public_boundary"]["nested_payloads"])

    def test_contract_schema_public_keys_exclude_private_boundary_names(self):
        schemas = [federation.federation_schema(), federation.federation_policy_schema(), federation.federation_verification_schema(), federation.federation_policy_evaluation_schema(), federation.federation_runtime_schema(), federation.federation_diff_schema()]
        encoded = json.dumps(schemas, sort_keys=True).casefold()
        for forbidden in ("source_path", "raw_payload", "private_metadata", "generated_by", "agent_id", "language_model"):
            self.assertNotIn(f'"{forbidden}"', encoded)


class FederationCliApiTests(FederationFixture):
    base = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history-series-release-registry-federation"

    @staticmethod
    def capture_cli(arguments):
        output = StringIO()
        with redirect_stdout(output):
            status = main(arguments)
        return status, output.getvalue()

    def test_cli_builds_verifies_queries_diffs_and_schema_contracts(self):
        first_value = self.ready_registry("first")
        second_value = self.held_registry("second")
        baseline_value = self.build((first_value, second_value))
        candidate_value = self.build((first_value, self.blocked_registry("second")))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first_dir, second_dir = root / "first", root / "second"
            registry.write_decision_assurance_history_series_release_registry(first_value, first_dir)
            registry.write_decision_assurance_history_series_release_registry(second_value, second_dir)
            output_dir = root / "federation"
            status, output = self.capture_cli([self.base, "--input", str(second_dir), "--input", str(first_dir), "--federation-id", "federation:cli", "--destination", str(output_dir), "--format", "summary"])
            self.assertEqual(status, 0)
            self.assertIn('"member_count": 2', output)
            status, output = self.capture_cli([self.base + "-verify", "--input", str(output_dir)])
            self.assertEqual(status, 0)
            self.assertIn('"runtime_state": "held"', output)
            status, output = self.capture_cli([self.base + "-query", "--input", str(output_dir), "--resource", "packages"])
            self.assertEqual(status, 0)
            self.assertIn('"returned_count": 2', output)
            baseline_dir, candidate_dir = root / "baseline", root / "candidate"
            self.write(baseline_value, baseline_dir)
            self.write(candidate_value, candidate_dir)
            diff_dir = root / "diff"
            status, output = self.capture_cli([self.base + "-diff", "--baseline", str(baseline_dir), "--candidate", str(candidate_dir), "--destination", str(diff_dir), "--format", "summary"])
            self.assertEqual(status, 0)
            self.assertIn('"state": "regressed"', output)
            status, output = self.capture_cli([self.base + "-diff-verify", "--input", str(diff_dir)])
            self.assertEqual(status, 0)
            self.assertIn('"release_ready": false', output)
            for suffix in ("schema", "member-schema", "package-schema", "policy-schema", "check-schema", "verification-schema", "policy-check-schema", "policy-evaluation-schema", "stage-schema", "runtime-schema", "query-schema", "diff-schema", "diff-item-schema", "diff-query-schema", "capabilities"):
                status, output = self.capture_cli([self.base + "-" + suffix])
                self.assertEqual(status, 0)
                self.assertTrue(output.strip())

    def test_cli_can_emit_csv_and_markdown_for_federation_and_diff_queries(self):
        baseline = self.build((self.ready_registry("one"),))
        candidate = self.build((self.ready_registry("one"), self.ready_registry("two")))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline_dir, candidate_dir, diff_dir = root / "baseline", root / "candidate", root / "diff"
            self.write(baseline, baseline_dir)
            self.write(candidate, candidate_dir)
            source_dir = root / "source-registry"
            registry.write_decision_assurance_history_series_release_registry(self.ready_registry("one"), source_dir)
            status, output = self.capture_cli([self.base, "--input", str(source_dir), "--destination", str(root / "fed"), "--format", "markdown"])
            self.assertEqual(status, 0)
            self.assertIn("Decision Assurance", output)
            status, output = self.capture_cli([self.base + "-diff", "--baseline", str(baseline_dir), "--candidate", str(candidate_dir), "--destination", str(diff_dir), "--format", "csv"])
            self.assertEqual(status, 0)
            self.assertIn("ordinal,key,action", output)
            status, output = self.capture_cli([self.base + "-diff-query", "--input", str(diff_dir), "--resource", "added", "--format", "markdown"])
            self.assertEqual(status, 0)
            self.assertIn("Diff Query", output)

    def test_api_reads_federation_queries_verification_diff_and_contracts(self):
        baseline = self.build((self.ready_registry("one"), self.held_registry("two")))
        candidate = self.build((self.ready_registry("one"), self.blocked_registry("two")))
        diff = federation.build_federation_diff(baseline, candidate, diff_id="diff:api")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            federation_dir, diff_dir = root / "federation", root / "diff"
            self.write(baseline, federation_dir)
            self.write_diff(diff, diff_dir)
            server = create_server("127.0.0.1", 0)
            server.glio_assurance_history_series_release_registry_federation_directory = str(federation_dir)
            server.glio_assurance_history_series_release_registry_federation_diff_directory = str(diff_dir)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation"
                summary = json.loads(urlopen(base + "?format=summary", timeout=10).read().decode())
                self.assertEqual(summary["member_count"], 2)
                query = json.loads(urlopen(base + "/query?resource=held", timeout=10).read().decode())
                self.assertEqual(query["returned_count"], 1)
                verified = json.loads(urlopen(base + "/verify", timeout=10).read().decode())
                self.assertTrue(verified["verification_accepted"])
                diff_summary = json.loads(urlopen(base + "/diff?format=summary", timeout=10).read().decode())
                self.assertEqual(diff_summary["state"], "regressed")
                schema = json.loads(urlopen(base + "/policy-evaluation-schema", timeout=10).read().decode())
                self.assertFalse(schema["additionalProperties"])
                capabilities = json.loads(urlopen(base + "/capabilities", timeout=10).read().decode())
                self.assertEqual(capabilities["package"]["files"], list(federation.FILES))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=10)


class FederationDiscoveryTests(FederationFixture):
    def _write_source(self, root, registry_id):
        directory = root / registry_id
        registry.write_decision_assurance_history_series_release_registry(
            self.ready_registry(registry_id), directory
        )
        return directory

    def test_shallow_discovery_is_sorted_and_ignores_unrelated_download_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "notes").mkdir()
            (root / "notes" / "README.txt").write_text("download notes", encoding="utf-8")
            second = self._write_source(root, "zeta")
            first = self._write_source(root, "alpha")
            self.assertEqual(
                federation.discover_federation_registry_directories(root),
                (first, second),
            )

    def test_recursive_discovery_reaches_grouped_downloads(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            group_a = root / "institution-a"
            group_b = root / "institution-b"
            group_a.mkdir()
            group_b.mkdir()
            first = self._write_source(group_a, "one")
            second = self._write_source(group_b, "two")
            self.assertEqual(
                federation.discover_federation_registry_directories(root), (),
            )
            self.assertEqual(
                federation.discover_federation_registry_directories(root, recursive=True),
                tuple(sorted((first, second), key=lambda item: str(item).casefold())),
            )

    def test_discovery_does_not_treat_the_root_as_a_registry(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in registry.FILES:
                (root / name).write_text("{}", encoding="utf-8")
            self.assertEqual(federation.discover_federation_registry_directories(root), ())

    def test_discovery_requires_a_real_root_directory(self):
        with self.assertRaises(ValidationError):
            federation.discover_federation_registry_directories("does-not-exist")
        with tempfile.NamedTemporaryFile() as temporary:
            with self.assertRaises(ValidationError):
                federation.discover_federation_registry_directories(temporary.name)

    def test_discovery_skips_symlinked_children(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            real = self._write_source(root, "real")
            link = root / "linked"
            try:
                link.symlink_to(real, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("directory symlinks are unavailable")
            self.assertEqual(federation.discover_federation_registry_directories(root), (real,))

    def test_symlinked_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "target"
            target.mkdir()
            linked = root / "linked-root"
            try:
                linked.symlink_to(target, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("directory symlinks are unavailable")
            with self.assertRaises(ValidationError):
                federation.discover_federation_registry_directories(linked)

    def test_exact_file_set_is_required_for_discovery(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            incomplete = root / "incomplete"
            incomplete.mkdir()
            for name in registry.FILES[:-1]:
                (incomplete / name).write_text("{}", encoding="utf-8")
            self.assertEqual(federation.discover_federation_registry_directories(root), ())

    def test_root_builder_uses_discovered_registry_directories(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self._write_source(root, "first")
            second = self._write_source(root, "second")
            value = federation.build_federation_from_root(root, federation_id="federation:root")
            direct = federation.build_federation_from_directories(
                (first, second), federation_id="federation:root"
            )
            self.assertEqual(value.to_dict(), direct.to_dict())
            self.assertEqual(value.runtime.state, federation.FederationState.READY.value)

    def test_recursive_root_builder_preserves_grouped_input_order_deterministically(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            group = root / "group"
            group.mkdir()
            first = self._write_source(group, "first")
            second = self._write_source(group, "second")
            left = federation.build_federation_from_root(
                root, federation_id="federation:nested", recursive=True
            )
            right = federation.build_federation_from_directories(
                (second, first), federation_id="federation:nested"
            )
            self.assertEqual(left.to_dict(), right.to_dict())

    def test_root_builder_respects_explicit_empty_policy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            policy = federation.default_federation_policy(
                policy_id="policy:empty-root", allow_empty=True
            )
            value = federation.build_federation_from_root(
                root, federation_id="federation:empty-root", policy=policy
            )
            self.assertEqual(value.federation.state, federation.FederationState.EMPTY.value)
            self.assertTrue(value.runtime.accepted)
            self.assertFalse(value.runtime.release_ready)

    def test_corrupt_discovered_registry_is_loaded_and_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = self._write_source(root, "corrupt")
            (directory / registry.REGISTRY_NAME).write_text("{}", encoding="utf-8")
            self.assertEqual(federation.discover_federation_registry_directories(root), (directory,))
            with self.assertRaises(ValidationError):
                federation.build_federation_from_root(root)

    def test_inspection_preview_is_path_free_and_public(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_source(root, "one")
            self._write_source(root, "two")
            preview = federation.inspect_federation_registry_root(root)
            encoded = json.dumps(preview, sort_keys=True)
            self.assertNotIn(str(root), encoded)
            self.assertEqual(preview["candidate_count"], 2)
            self.assertEqual(preview["verified_count"], 2)
            self.assertEqual([item["registry_id"] for item in preview["registries"]], ["registry:one", "registry:two"])
            self.assertNotIn("source_path", encoded)
            self.assertNotIn("private", encoded.casefold())

    def test_inspection_preview_is_repeatable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_source(root, "repeat")
            first = federation.inspect_federation_registry_root(root)
            second = federation.inspect_federation_registry_root(root)
            self.assertEqual(first, second)
            self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))

    def test_inspection_recursive_preview_has_stable_registry_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first_group, second_group = root / "b", root / "a"
            first_group.mkdir()
            second_group.mkdir()
            self._write_source(first_group, "z")
            self._write_source(second_group, "a")
            preview = federation.inspect_federation_registry_root(root, recursive=True)
            self.assertEqual([item["registry_id"] for item in preview["registries"]], ["registry:a", "registry:z"])


class FederationExportContractTests(FederationFixture):
    def setUp(self):
        self.value = self.build((self.ready_registry("one"), self.held_registry("two")))

    def test_export_document_names_are_fixed(self):
        documents = federation.federation_export_documents(self.value)
        self.assertEqual(
            tuple(documents),
            (
                "summary.csv",
                "members.csv",
                "packages.csv",
                "verification.csv",
                "policy-evaluation.csv",
                "runtime.csv",
                "review.md",
            ),
        )

    def test_summary_csv_is_one_row_with_summary_field_order(self):
        text = federation.federation_summary_csv(self.value)
        lines = text.splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(
            lines[0],
            "federation_id,version,boundary,state,accepted,release_ready,member_count,package_count,ready_count,hold_count,blocked_count,accepted_count,release_ready_count,content_address",
        )
        self.assertIn("federation:test", lines[1])

    def test_member_csv_conserves_members_and_is_canonical(self):
        text = federation.federation_members_csv(self.value)
        self.assertEqual(len(text.splitlines()), self.value.federation.member_count + 1)
        self.assertTrue(text.endswith("\n"))
        self.assertEqual(text, federation.federation_members_csv(self.value))
        self.assertIn("registry_id", text.splitlines()[0])

    def test_package_csv_conserves_packages(self):
        text = federation.federation_packages_csv(self.value)
        self.assertEqual(len(text.splitlines()), self.value.federation.package_count + 1)
        self.assertIn("package_id", text.splitlines()[0])
        self.assertIn("two", text)

    def test_verification_csv_conserves_independent_checks(self):
        text = federation.federation_verification_csv(self.value)
        self.assertEqual(len(text.splitlines()), self.value.verification.check_count + 1)
        self.assertIn("member-count-bounded", text)
        self.assertIn("required", text)

    def test_policy_csv_conserves_policy_checks(self):
        text = federation.federation_policy_evaluation_csv(self.value)
        self.assertEqual(len(text.splitlines()), self.value.policy_evaluation.check_count + 1)
        self.assertIn("release-readiness", text)
        self.assertIn("optional", text)

    def test_runtime_csv_retains_stage_address_columns(self):
        text = federation.federation_runtime_csv(self.value)
        header = text.splitlines()[0]
        self.assertIn("input_address", header)
        self.assertIn("output_address", header)
        self.assertEqual(len(text.splitlines()), self.value.runtime.stage_count + 1)

    def test_markdown_export_contains_summary_and_rows(self):
        text = federation.render_federation_markdown(self.value)
        self.assertTrue(text.startswith("# Decision Assurance History Series Release Registry Federation\n"))
        self.assertIn("## Summary", text)
        self.assertIn("## Items", text)
        self.assertIn("package_id", text)

    def test_export_document_map_is_repeatable(self):
        first = federation.federation_export_documents(self.value)
        second = federation.federation_export_documents(self.value)
        self.assertEqual(first, second)
        self.assertEqual(
            {name: len(raw.encode("utf-8")) for name, raw in first.items()},
            {name: len(raw.encode("utf-8")) for name, raw in second.items()},
        )

    def test_exports_fail_if_bundle_is_mutated_after_build(self):
        original = self.value.federation.content_address
        self.value.federation.content_address = "tampered:federation"
        with self.assertRaises(ValidationError):
            federation.federation_export_documents(self.value)
        self.value.federation.content_address = original

    def test_export_documents_do_not_include_paths_or_private_keys(self):
        documents = federation.federation_export_documents(self.value)
        encoded = json.dumps(documents, sort_keys=True)
        self.assertNotIn("source_path", encoded)
        self.assertNotIn("private", encoded.casefold())
        self.assertNotIn("model", encoded.casefold())
        self.assertNotIn("agent", encoded.casefold())

    def test_empty_federation_exports_headers_without_fake_rows(self):
        policy = federation.default_federation_policy(policy_id="policy:empty-export", allow_empty=True)
        value = self.build((), policy=policy)
        self.assertEqual(len(federation.federation_summary_csv(value).splitlines()), 2)
        self.assertEqual(len(federation.federation_members_csv(value).splitlines()), 1)
        self.assertEqual(len(federation.federation_packages_csv(value).splitlines()), 1)
        self.assertEqual(len(federation.federation_runtime_csv(value).splitlines()), 1 + value.runtime.stage_count)

    def test_exports_are_available_for_blocked_closure(self):
        blocked = self.build((self.blocked_registry("blocked"),))
        self.assertEqual(blocked.runtime.state, federation.FederationState.BLOCKED.value)
        self.assertIn("blocked", federation.federation_summary_csv(blocked))
        self.assertIn("blocked", federation.render_federation_markdown(blocked))
        self.assertEqual(len(federation.federation_policy_evaluation_csv(blocked).splitlines()), 8)


class FederationQueryMatrixTests(FederationFixture):
    def setUp(self):
        self.ready = self.ready_registry("ready")
        self.held = self.held_registry("held")
        self.value = self.build((self.ready, self.held))

    def test_every_query_resource_has_expected_cardinality(self):
        expected = {
            "summary": 1,
            "members": 2,
            "packages": 2,
            "ready": 1,
            "held": 1,
            "blocked": 0,
            "accepted": 2,
            "release-ready": 1,
            "verification-checks": 7,
            "policy-checks": 7,
            "stages": 5,
        }
        for resource, count in expected.items():
            with self.subTest(resource=resource):
                result = federation.query_federation(self.value, resource=resource)
                self.assertEqual(result.total_count, count)
                self.assertEqual(result.returned_count, count)
                self.assertEqual(len(result.items), count)

    def test_query_state_filter_is_independent_of_resource(self):
        for resource in ("members", "packages", "ready", "held", "blocked"):
            with self.subTest(resource=resource):
                result = federation.query_federation(self.value, resource=resource, state="held")
                self.assertTrue(all(item.get("state") == "held" for item in result.items))

    def test_query_acceptance_and_readiness_filters_compose(self):
        result = federation.query_federation(
            self.value, resource="packages", accepted=True, release_ready=False
        )
        self.assertEqual(result.returned_count, 1)
        self.assertEqual(result.items[0]["registry_id"], "registry:held")
        self.assertTrue(result.items[0]["accepted"])
        self.assertFalse(result.items[0]["release_ready"])

    def test_query_text_matches_registry_and_package_fields(self):
        member = federation.query_federation(self.value, resource="members", text="registry:ready")
        package = federation.query_federation(self.value, resource="packages", text="held")
        self.assertEqual(member.returned_count, 1)
        self.assertEqual(package.returned_count, 1)
        self.assertEqual(member.items[0]["registry_id"], "registry:ready")
        self.assertEqual(package.items[0]["registry_id"], "registry:held")

    def test_query_pagination_has_stable_offsets(self):
        first = federation.query_federation(self.value, resource="packages", offset=0, limit=1)
        second = federation.query_federation(self.value, resource="packages", offset=1, limit=1)
        empty = federation.query_federation(self.value, resource="packages", offset=2, limit=1)
        self.assertEqual(first.total_count, second.total_count)
        self.assertEqual(first.returned_count, second.returned_count, 1)
        self.assertEqual(empty.returned_count, 0)
        self.assertNotEqual(first.items[0]["registry_id"], second.items[0]["registry_id"])

    def test_query_result_round_trip_is_address_preserving(self):
        result = federation.query_federation(self.value, resource="policy-checks", limit=3)
        rebuilt = federation.federation_query_from_mapping(result.to_dict())
        self.assertEqual(rebuilt.to_dict(), result.to_dict())
        self.assertEqual(federation.address_federation_query(rebuilt), result.content_address)

    def test_query_json_csv_and_markdown_all_verify_the_same_result(self):
        result = federation.query_federation(self.value, resource="packages")
        self.assertEqual(json.loads(federation.federation_query_json(result)), result.to_dict())
        self.assertIn("registry_id", federation.federation_query_csv(result).splitlines()[0])
        self.assertIn("Federation Query", federation.render_federation_query_markdown(result))

    def test_summary_query_stays_one_row_with_nonmatching_filters(self):
        result = federation.query_federation(self.value, resource="summary", text="missing")
        self.assertEqual(result.total_count, 0)
        self.assertEqual(result.returned_count, 0)

    def test_query_rejects_negative_and_zero_limit_parameters(self):
        with self.assertRaises(ValidationError):
            federation.query_federation(self.value, resource="members", offset=-1)
        with self.assertRaises(ValidationError):
            federation.query_federation(self.value, resource="members", limit=0)
        with self.assertRaises(ValidationError):
            federation.query_federation(self.value, resource="members", limit=federation.MAX_QUERY_ITEMS + 1)

    def test_query_rejects_mixed_typed_and_keyword_arguments(self):
        query = federation.FederationQuery(resource="members")
        with self.assertRaises(ValidationError):
            federation.query_federation(self.value, query, resource="packages")

    def test_query_resources_are_case_sensitive_and_closed(self):
        for resource in ("Members", "all", "source-paths", "verification"):
            with self.subTest(resource=resource):
                with self.assertRaises(ValidationError):
                    federation.query_federation(self.value, resource=resource)

    def test_query_public_items_never_embed_nested_payloads(self):
        result = federation.query_federation(self.value, resource="packages")
        for item in result.items:
            self.assertNotIn("entries", item)
            self.assertNotIn("series", item)
            self.assertNotIn("policy", item)
            self.assertNotIn("source_path", item)

    def test_query_items_are_sorted_by_federation_ordinal(self):
        result = federation.query_federation(self.value, resource="packages")
        self.assertEqual([item["ordinal"] for item in result.items], [0, 1])

    def test_query_mapping_rejects_missing_and_unknown_fields(self):
        body = federation.query_federation(self.value, resource="members").to_dict()
        missing = dict(body)
        missing.pop("content_address")
        unknown = dict(body)
        unknown["unexpected"] = True
        with self.assertRaises(ValidationError):
            federation.federation_query_from_mapping(missing)
        with self.assertRaises(ValidationError):
            federation.federation_query_from_mapping(unknown)


class FederationFailureMatrixTests(FederationFixture):
    def test_member_mapping_requires_each_contract_field(self):
        body = self.build((self.ready_registry("one"),)).federation.members[0].to_dict()
        for field in body:
            with self.subTest(field=field):
                candidate = dict(body)
                candidate.pop(field)
                with self.assertRaises(ValidationError):
                    federation.federation_member_from_mapping(candidate)

    def test_package_mapping_requires_each_contract_field(self):
        body = self.build((self.ready_registry("one"),)).federation.packages[0].to_dict()
        for field in body:
            with self.subTest(field=field):
                candidate = dict(body)
                candidate.pop(field)
                with self.assertRaises(ValidationError):
                    federation.federation_package_from_mapping(candidate)

    def test_federation_mapping_requires_each_contract_field(self):
        body = self.build((self.ready_registry("one"),)).federation.to_dict()
        for field in body:
            with self.subTest(field=field):
                candidate = dict(body)
                candidate.pop(field)
                with self.assertRaises(ValidationError):
                    federation.federation_from_mapping(candidate)

    def test_policy_mapping_requires_each_contract_field(self):
        body = self.build((self.ready_registry("one"),)).policy.to_dict()
        for field in body:
            with self.subTest(field=field):
                candidate = dict(body)
                candidate.pop(field)
                with self.assertRaises(ValidationError):
                    federation.federation_policy_from_mapping(candidate)

    def test_check_mapping_requires_each_contract_field(self):
        body = self.build((self.ready_registry("one"),)).verification.checks[0].to_dict()
        for field in body:
            with self.subTest(field=field):
                candidate = dict(body)
                candidate.pop(field)
                with self.assertRaises(ValidationError):
                    federation.federation_check_from_mapping(candidate)

    def test_verification_mapping_requires_each_contract_field(self):
        body = self.build((self.ready_registry("one"),)).verification.to_dict()
        for field in body:
            with self.subTest(field=field):
                candidate = dict(body)
                candidate.pop(field)
                with self.assertRaises(ValidationError):
                    federation.federation_verification_from_mapping(candidate)

    def test_policy_check_mapping_requires_each_contract_field(self):
        body = self.build((self.ready_registry("one"),)).policy_evaluation.checks[0].to_dict()
        for field in body:
            with self.subTest(field=field):
                candidate = dict(body)
                candidate.pop(field)
                with self.assertRaises(ValidationError):
                    federation.policy_check_from_mapping(candidate)

    def test_policy_evaluation_mapping_requires_each_contract_field(self):
        body = self.build((self.ready_registry("one"),)).policy_evaluation.to_dict()
        for field in body:
            with self.subTest(field=field):
                candidate = dict(body)
                candidate.pop(field)
                with self.assertRaises(ValidationError):
                    federation.policy_evaluation_from_mapping(candidate)

    def test_stage_mapping_requires_each_contract_field(self):
        body = self.build((self.ready_registry("one"),)).runtime.stages[0].to_dict()
        for field in body:
            with self.subTest(field=field):
                candidate = dict(body)
                candidate.pop(field)
                with self.assertRaises(ValidationError):
                    federation.federation_stage_from_mapping(candidate)

    def test_runtime_mapping_requires_each_contract_field(self):
        body = self.build((self.ready_registry("one"),)).runtime.to_dict()
        for field in body:
            with self.subTest(field=field):
                candidate = dict(body)
                candidate.pop(field)
                with self.assertRaises(ValidationError):
                    federation.federation_runtime_from_mapping(candidate)

    def test_bundle_mapping_requires_each_component(self):
        body = self.build((self.ready_registry("one"),)).to_dict()
        for field in body:
            with self.subTest(field=field):
                candidate = dict(body)
                candidate.pop(field)
                with self.assertRaises(ValidationError):
                    federation.federation_bundle_from_mapping(candidate)

    def test_diff_item_mapping_requires_each_contract_field(self):
        value = self.build((self.ready_registry("one"),))
        diff = federation.build_federation_diff(value, value)
        body = diff.items[0].to_dict()
        for field in body:
            with self.subTest(field=field):
                candidate = dict(body)
                candidate.pop(field)
                with self.assertRaises(ValidationError):
                    federation.federation_diff_item_from_mapping(candidate)

    def test_diff_mapping_requires_each_contract_field(self):
        value = self.build((self.ready_registry("one"),))
        body = federation.build_federation_diff(value, value).to_dict()
        for field in body:
            with self.subTest(field=field):
                candidate = dict(body)
                candidate.pop(field)
                with self.assertRaises(ValidationError):
                    federation.federation_diff_from_mapping(candidate)

    def test_all_mapping_boundaries_reject_non_objects(self):
        functions = (
            federation.federation_member_from_mapping,
            federation.federation_package_from_mapping,
            federation.federation_from_mapping,
            federation.federation_policy_from_mapping,
            federation.federation_check_from_mapping,
            federation.federation_verification_from_mapping,
            federation.policy_check_from_mapping,
            federation.policy_evaluation_from_mapping,
            federation.federation_stage_from_mapping,
            federation.federation_runtime_from_mapping,
            federation.federation_bundle_from_mapping,
            federation.federation_diff_item_from_mapping,
            federation.federation_diff_from_mapping,
        )
        for function in functions:
            with self.subTest(function=function.__name__):
                with self.assertRaises(ValidationError):
                    function([])

    def test_federation_query_mapping_rejects_non_object(self):
        with self.assertRaises(ValidationError):
            federation.federation_query_from_mapping([])
        with self.assertRaises(ValidationError):
            federation.federation_diff_query_from_mapping([])

    def test_state_enum_accepts_only_public_federation_states(self):
        for state in ("ready", "held", "blocked", "empty"):
            with self.subTest(state=state):
                self.assertEqual(federation.FederationState(state).value, state)
        for state in ("hold", "passed", "unknown", "private"):
            with self.subTest(state=state):
                with self.assertRaises(ValueError):
                    federation.FederationState(state)

    def test_policy_boundaries_reject_zero_negative_and_overflow_values(self):
        values = (
            {"minimum_member_count": 0},
            {"minimum_package_count": 0},
            {"minimum_member_count": -1},
            {"minimum_package_count": -1},
            {"maximum_blocked_members": -1},
            {"maximum_held_members": federation.MAX_REGISTRIES + 1},
        )
        for override in values:
            with self.subTest(override=override):
                with self.assertRaises(ValidationError):
                    federation.default_federation_policy(**override)

    def test_query_bounds_reject_boolean_counts(self):
        for field, value in (("offset", True), ("limit", False)):
            with self.subTest(field=field):
                kwargs = {field: value}
                with self.assertRaises(ValidationError):
                    federation.FederationQuery(**kwargs)

    def test_diff_query_bounds_reject_invalid_actions_and_directions(self):
        for kwargs in (
            {"action": "promote"},
            {"direction": "worsened"},
            {"offset": -1},
            {"limit": 0},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValidationError):
                    federation.FederationDiffQuery(**kwargs)

    def test_stage_constructor_rejects_passed_but_unaccepted_state(self):
        with self.assertRaises(ValidationError):
            federation.DecisionAssuranceHistorySeriesReleaseRegistryFederationStage(
                0,
                "stage:test",
                "kind:test",
                "passed",
                False,
                "invalid acceptance",
                "input:test",
                "output:test",
                "pending:stage",
            )

    def test_runtime_constructor_rejects_inconsistent_stage_counts(self):
        value = self.build((self.ready_registry("one"),))
        with self.assertRaises(ValidationError):
            federation.DecisionAssuranceHistorySeriesReleaseRegistryFederationRuntime(
                value.runtime.federation_address,
                value.runtime.policy_address,
                value.runtime.policy_evaluation_address,
                value.runtime.state,
                value.runtime.accepted,
                value.runtime.release_ready,
                value.runtime.stage_count,
                value.runtime.passed_count + 1,
                value.runtime.held_count,
                value.runtime.blocked_count,
                value.runtime.stages,
                "pending:runtime",
            )

    def test_blocked_package_cannot_be_hidden_by_ready_state_field(self):
        value = self.build((self.blocked_registry("blocked"),))
        mapping = value.federation.to_dict()
        mapping["state"] = "ready"
        with self.assertRaises(ValidationError):
            federation.federation_from_mapping(mapping)


class FederationDeterminismTests(FederationFixture):
    def test_all_addresses_are_stable_across_fresh_builds(self):
        left = self.build((self.ready_registry("one"), self.held_registry("two")))
        right = self.build((self.ready_registry("one"), self.held_registry("two")))
        self.assertEqual(left.to_dict(), right.to_dict())
        self.assertEqual(federation.federation_json(left), federation.federation_json(right))

    def test_member_addresses_ignore_ordinal_reassignment(self):
        left = self.build((self.ready_registry("one"), self.ready_registry("two")))
        right = self.build((self.ready_registry("zero"), self.ready_registry("one"), self.ready_registry("two")))
        left_members = {item.registry_id: item.content_address for item in left.federation.members}
        right_members = {item.registry_id: item.content_address for item in right.federation.members}
        self.assertEqual(left_members["registry:one"], right_members["registry:one"])
        self.assertEqual(left_members["registry:two"], right_members["registry:two"])

    def test_package_addresses_ignore_ordinal_reassignment(self):
        left = self.build((self.ready_registry("one"), self.ready_registry("two")))
        right = self.build((self.ready_registry("zero"), self.ready_registry("one"), self.ready_registry("two")))
        left_packages = {(item.registry_id, item.package_id): item.content_address for item in left.federation.packages}
        right_packages = {(item.registry_id, item.package_id): item.content_address for item in right.federation.packages}
        for key in left_packages:
            self.assertEqual(left_packages[key], right_packages[key])

    def test_federation_diff_does_not_mark_unrelated_records_changed(self):
        baseline = self.build((self.ready_registry("one"), self.ready_registry("two")))
        candidate = self.build((self.ready_registry("zero"), self.ready_registry("one"), self.ready_registry("two")))
        diff = federation.build_federation_diff(baseline, candidate)
        unchanged = {item.key for item in diff.items if item.action == "unchanged"}
        self.assertIn("member:registry:one", unchanged)
        self.assertIn("member:registry:two", unchanged)
        self.assertIn("package:registry:one/package:one", unchanged)
        self.assertIn("package:registry:two/package:two", unchanged)

    def test_diff_summary_counts_conserve_the_complete_key_union(self):
        baseline = self.build((self.ready_registry("one"),))
        candidate = self.build((self.ready_registry("one"), self.ready_registry("two")))
        diff = federation.build_federation_diff(baseline, candidate)
        self.assertEqual(
            diff.item_count,
            diff.added_count + diff.removed_count + diff.unchanged_count + diff.changed_count,
        )
        self.assertEqual(
            diff.item_count,
            len({item.key for item in diff.items}),
        )

    def test_public_projection_is_recursive_and_path_free(self):
        value = self.build((self.ready_registry("one"), self.held_registry("two")))
        payload = value.to_dict()
        self.assertTrue(federation._public(payload))
        encoded = json.dumps(payload, sort_keys=True)
        for forbidden in ("agent", "assistant", "author", "language", "model", "private", "source_path", "user"):
            self.assertNotIn(forbidden, encoded.casefold())

    def test_capability_lists_are_repeatable_and_json_serializable(self):
        first = federation.federation_capabilities()
        second = federation.federation_capabilities()
        self.assertEqual(first, second)
        json.dumps(first)
        self.assertEqual(first["checks"]["structural_count"], 7)
        self.assertEqual(first["checks"]["policy_count"], 7)

    def test_schema_documents_are_repeatable_and_closed(self):
        functions = (
            federation.federation_member_schema,
            federation.federation_package_schema,
            federation.federation_schema,
            federation.federation_policy_schema,
            federation.federation_check_schema,
            federation.federation_verification_schema,
            federation.federation_policy_evaluation_schema,
            federation.federation_runtime_schema,
            federation.federation_query_schema,
            federation.federation_diff_schema,
            federation.federation_diff_query_schema,
        )
        for function in functions:
            with self.subTest(function=function.__name__):
                first = function()
                second = function()
                self.assertEqual(first, second)
                self.assertFalse(first["additionalProperties"])
                json.dumps(first)

    def test_round_trip_through_every_typed_component_preserves_addresses(self):
        value = self.build((self.ready_registry("one"), self.held_registry("two")))
        rebuilt = federation.federation_bundle_from_mapping(value.to_dict())
        self.assertEqual(rebuilt.federation.content_address, value.federation.content_address)
        self.assertEqual(rebuilt.policy.content_address, value.policy.content_address)
        self.assertEqual(rebuilt.verification.content_address, value.verification.content_address)
        self.assertEqual(rebuilt.policy_evaluation.content_address, value.policy_evaluation.content_address)
        self.assertEqual(rebuilt.runtime.content_address, value.runtime.content_address)

    def test_state_score_orders_ready_above_held_above_blocked(self):
        ready = federation._state_score("ready", True, True)
        held = federation._state_score("held", True, False)
        blocked = federation._state_score("blocked", False, False)
        self.assertGreater(ready, held)
        self.assertGreater(held, blocked)

    def test_root_preview_and_federation_build_agree_on_source_addresses(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_registry(root, "one")
            self._write_registry(root, "two")
            preview = federation.inspect_federation_registry_root(root)
            value = federation.build_federation_from_root(root)
            self.assertEqual(
                [item["registry_address"] for item in preview["registries"]],
                [member.registry_address for member in value.federation.members],
            )

    def _write_registry(self, root, registry_id):
        registry.write_decision_assurance_history_series_release_registry(
            self.ready_registry(registry_id), root / registry_id
        )


class FederationPersistenceMatrixTests(FederationFixture):
    def setUp(self):
        self.value = self.build((self.ready_registry("one"), self.held_registry("two")))

    def test_every_federation_document_is_utf8_canonical_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "federation"
            self.write(self.value, destination)
            for name in federation.FILES:
                with self.subTest(name=name):
                    raw = (destination / name).read_bytes()
                    decoded = raw.decode("utf-8")
                    self.assertEqual(raw, decoded.encode("utf-8"))
                    self.assertEqual(json.loads(decoded), json.loads(decoded))
                    self.assertFalse(decoded.startswith(" "))

    def test_manifest_contains_one_receipt_for_every_non_manifest_document(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "federation"
            self.write(self.value, destination)
            manifest = json.loads((destination / federation.MANIFEST_NAME).read_text(encoding="utf-8"))
            names = [item["name"] for item in manifest["artifacts"]]
            self.assertEqual(names, list(federation.FILES[1:]))
            self.assertEqual(len(names), len(set(names)))
            self.assertEqual(manifest["artifact_count"], len(names))
            self.assertEqual(manifest["federation_address"], self.value.federation.content_address)
            self.assertEqual(manifest["runtime_address"], self.value.runtime.content_address)

    def test_manifest_receipts_match_exact_bytes_for_every_document(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "federation"
            self.write(self.value, destination)
            manifest = json.loads((destination / federation.MANIFEST_NAME).read_text(encoding="utf-8"))
            for item in manifest["artifacts"]:
                with self.subTest(name=item["name"]):
                    raw = (destination / item["name"]).read_bytes()
                    self.assertEqual(item["bytes"], len(raw))
                    self.assertEqual(
                        item["byte_address"],
                        federation._file_address(item["name"], raw),
                    )

    def test_missing_each_non_manifest_document_is_rejected(self):
        for name in federation.FILES[1:]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                destination = Path(temporary) / "federation"
                self.write(self.value, destination)
                (destination / name).unlink()
                with self.assertRaises(ValidationError):
                    federation.load_federation(destination)

    def test_extra_each_common_file_kind_is_rejected(self):
        for name in ("extra.json", "README.md", "nested.txt"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                destination = Path(temporary) / "federation"
                self.write(self.value, destination)
                (destination / name).write_text("unexpected", encoding="utf-8")
                with self.assertRaises(ValidationError):
                    federation.load_federation(destination)

    def test_manifest_federation_linkage_is_checked(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "federation"
            self.write(self.value, destination)
            path = destination / federation.MANIFEST_NAME
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["federation_address"] = "tampered:federation"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaises(ValidationError):
                federation.load_federation(destination)

    def test_manifest_file_order_is_checked(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "federation"
            self.write(self.value, destination)
            path = destination / federation.MANIFEST_NAME
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["files"] = list(reversed(manifest["files"]))
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaises(ValidationError):
                federation.load_federation(destination)

    def test_members_split_projection_is_checked_against_federation(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "federation"
            self.write(self.value, destination)
            path = destination / federation.MEMBERS_NAME
            body = json.loads(path.read_text(encoding="utf-8"))
            body["members"][0]["registry_id"] = "changed"
            path.write_text(json.dumps(body), encoding="utf-8")
            with self.assertRaises(ValidationError):
                federation.load_federation(destination)

    def test_packages_split_projection_is_checked_against_federation(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "federation"
            self.write(self.value, destination)
            path = destination / federation.PACKAGES_NAME
            body = json.loads(path.read_text(encoding="utf-8"))
            body["packages"][0]["package_id"] = "changed"
            path.write_text(json.dumps(body), encoding="utf-8")
            with self.assertRaises(ValidationError):
                federation.load_federation(destination)

    def test_policy_document_is_checked_against_nested_evaluation(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "federation"
            self.write(self.value, destination)
            path = destination / federation.POLICY_NAME
            body = json.loads(path.read_text(encoding="utf-8"))
            body["policy_id"] = "changed"
            path.write_text(json.dumps(body), encoding="utf-8")
            with self.assertRaises(ValidationError):
                federation.load_federation(destination)

    def test_noncanonical_whitespace_is_rejected_by_byte_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "federation"
            self.write(self.value, destination)
            path = destination / federation.RUNTIME_NAME
            body = json.loads(path.read_text(encoding="utf-8"))
            path.write_text(json.dumps(body, indent=2), encoding="utf-8")
            with self.assertRaises(ValidationError):
                federation.load_federation(destination)

    def test_directory_loader_rejects_a_file_instead_of_a_directory(self):
        with tempfile.NamedTemporaryFile() as temporary:
            with self.assertRaises(ValidationError):
                federation.load_federation(temporary.name)

    def test_directory_loader_rejects_a_symlinked_directory_when_supported(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination = root / "federation"
            self.write(self.value, destination)
            linked = root / "linked"
            try:
                linked.symlink_to(destination, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("directory symlinks are unavailable")
            with self.assertRaises(ValidationError):
                federation.load_federation(linked)

    def test_overwrite_only_replaces_the_target_federation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination = root / "federation"
            unrelated = root / "unrelated.txt"
            unrelated.write_text("keep", encoding="utf-8")
            self.write(self.value, destination)
            self.write(self.value, destination, overwrite=True)
            self.assertEqual(unrelated.read_text(encoding="utf-8"), "keep")
            self.assertEqual(federation.load_federation(destination).to_dict(), self.value.to_dict())

    def test_failed_new_write_does_not_leave_a_partial_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination = root / "federation"
            invalid = self.build((self.ready_registry("one"),))
            invalid.federation.content_address = "invalid:federation"
            with self.assertRaises(ValidationError):
                self.write(invalid, destination)
            self.assertFalse(destination.exists())

    def test_diff_directory_has_its_own_exact_file_set(self):
        diff = federation.build_federation_diff(self.value, self.value)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "diff"
            self.write_diff(diff, destination)
            self.assertEqual({item.name for item in destination.iterdir()}, set(federation.DIFF_FILES))
            self.assertEqual(federation.load_federation_diff(destination).to_dict(), diff.to_dict())

    def test_diff_manifest_receipts_cover_only_the_diff_document(self):
        diff = federation.build_federation_diff(self.value, self.value)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "diff"
            self.write_diff(diff, destination)
            manifest = json.loads((destination / federation.MANIFEST_NAME).read_text(encoding="utf-8"))
            self.assertEqual(manifest["files"], list(federation.DIFF_FILES))
            self.assertEqual(manifest["artifact_count"], 1)
            self.assertEqual(manifest["artifacts"][0]["name"], federation.DIFF_NAME)


class FederationRuntimePolicyMatrixTests(FederationFixture):
    def test_ready_input_has_five_passed_runtime_stages(self):
        value = self.build((self.ready_registry("ready"),))
        self.assertEqual(value.runtime.state, "ready")
        self.assertTrue(value.runtime.accepted)
        self.assertTrue(value.runtime.release_ready)
        self.assertEqual(value.runtime.passed_count, 5)
        self.assertEqual(value.runtime.held_count, 0)
        self.assertEqual(value.runtime.blocked_count, 0)
        self.assertEqual([stage.state for stage in value.runtime.stages], ["passed"] * 5)

    def test_held_input_has_a_held_policy_and_completion_stage(self):
        value = self.build((self.held_registry("held"),))
        self.assertEqual(value.runtime.state, "held")
        self.assertTrue(value.runtime.accepted)
        self.assertFalse(value.runtime.release_ready)
        self.assertEqual(value.runtime.held_count, 3)
        self.assertEqual([stage.state for stage in value.runtime.stages], ["passed", "passed", "held", "held", "held"])

    def test_blocked_input_has_blocked_structure_and_completion_stages(self):
        value = self.build((self.blocked_registry("blocked"),))
        self.assertEqual(value.runtime.state, "blocked")
        self.assertFalse(value.runtime.accepted)
        self.assertFalse(value.runtime.release_ready)
        self.assertEqual(value.runtime.blocked_count, 3)
        self.assertEqual([stage.state for stage in value.runtime.stages], ["passed", "passed", "blocked", "blocked", "blocked"])

    def test_mixed_ready_and_held_input_is_accepted_but_not_release_ready(self):
        value = self.build((self.ready_registry("ready"), self.held_registry("held")))
        self.assertEqual(value.federation.state, "held")
        self.assertEqual(value.runtime.state, "held")
        self.assertEqual(value.federation.accepted_count, 2)
        self.assertEqual(value.federation.release_ready_count, 1)
        self.assertTrue(value.runtime.accepted)
        self.assertFalse(value.runtime.release_ready)

    def test_mixed_ready_and_blocked_input_remains_blocked(self):
        value = self.build((self.ready_registry("ready"), self.blocked_registry("blocked")))
        self.assertEqual(value.federation.blocked_count, 1)
        self.assertEqual(value.runtime.state, "blocked")
        self.assertFalse(value.runtime.accepted)

    def test_optional_readiness_policy_turns_held_input_into_ready_evaluation(self):
        policy = federation.default_federation_policy(
            policy_id="policy:optional",
            require_all_release_ready=False,
        )
        value = self.build((self.held_registry("held"),), policy=policy)
        self.assertEqual(value.policy_evaluation.state, "ready")
        self.assertTrue(value.policy_evaluation.accepted)
        self.assertTrue(value.policy_evaluation.release_ready)
        self.assertEqual(value.runtime.state, "ready")
        self.assertTrue(value.runtime.release_ready)

    def test_held_member_budget_can_block_an_otherwise_accepted_federation(self):
        policy = federation.default_federation_policy(
            policy_id="policy:no-held",
            maximum_held_members=0,
            require_all_release_ready=False,
        )
        value = self.build((self.held_registry("held"),), policy=policy)
        self.assertEqual(value.policy_evaluation.state, "blocked")
        self.assertFalse(value.policy_evaluation.accepted)
        self.assertEqual(value.runtime.state, "blocked")

    def test_minimum_member_and_package_checks_fail_independently(self):
        policy = federation.default_federation_policy(
            policy_id="policy:minima",
            minimum_member_count=2,
            minimum_package_count=2,
        )
        value = self.build((self.ready_registry("one"),), policy=policy)
        checks = {check.check_id: check for check in value.policy_evaluation.checks}
        self.assertFalse(checks["minimum-members"].passed)
        self.assertFalse(checks["minimum-packages"].passed)
        self.assertEqual(value.policy_evaluation.required_failure_count, 2)

    def test_blocked_state_check_fails_even_when_blocked_member_budget_is_relaxed(self):
        policy = federation.default_federation_policy(
            policy_id="policy:blocked-budget",
            maximum_blocked_members=1,
            require_all_release_ready=False,
        )
        value = self.build((self.blocked_registry("blocked"),), policy=policy)
        checks = {check.check_id: check for check in value.policy_evaluation.checks}
        self.assertTrue(checks["blocked-member-budget"].passed)
        self.assertFalse(checks["blocked-state"].passed)
        self.assertFalse(value.runtime.accepted)

    def test_empty_policy_accepts_an_explicit_empty_federation(self):
        policy = federation.default_federation_policy(policy_id="policy:empty", allow_empty=True)
        value = self.build((), policy=policy)
        checks = {check.check_id: check for check in value.policy_evaluation.checks}
        self.assertTrue(value.policy_evaluation.accepted)
        self.assertEqual(value.policy_evaluation.state, "empty")
        self.assertTrue(checks["empty-federation-policy"].passed)
        self.assertFalse(value.runtime.release_ready)

    def test_empty_policy_without_permission_is_rejected_before_build(self):
        with self.assertRaises(ValidationError):
            self.build(())

    def test_policy_check_ordinals_are_contiguous_and_addressed(self):
        value = self.build((self.ready_registry("one"),))
        checks = value.policy_evaluation.checks
        self.assertEqual([check.ordinal for check in checks], list(range(len(checks))))
        self.assertEqual(len({check.content_address for check in checks}), len(checks))
        self.assertEqual(value.policy_evaluation.check_count, len(checks))

    def test_runtime_stage_ordinals_are_contiguous_and_addressed(self):
        value = self.build((self.ready_registry("one"),))
        stages = value.runtime.stages
        self.assertEqual([stage.ordinal for stage in stages], list(range(len(stages))))
        self.assertEqual(len({stage.content_address for stage in stages}), len(stages))
        self.assertEqual(value.runtime.stage_count, len(stages))

    def test_each_runtime_stage_links_to_the_expected_previous_receipt(self):
        value = self.build((self.ready_registry("one"),))
        stages = value.runtime.stages
        self.assertEqual(stages[0].input_address, value.policy.content_address)
        self.assertEqual(stages[0].output_address, value.federation.content_address)
        self.assertEqual(stages[1].input_address, value.federation.content_address)
        self.assertEqual(stages[1].output_address, value.verification.content_address)
        self.assertEqual(stages[2].input_address, value.verification.content_address)
        self.assertEqual(stages[2].output_address, value.policy_evaluation.content_address)
        self.assertEqual(stages[3].input_address, value.policy_evaluation.content_address)
        self.assertEqual(stages[3].output_address, value.federation.content_address)
        self.assertEqual(stages[4].input_address, value.federation.content_address)
        self.assertEqual(stages[4].output_address, value.federation.content_address)


class FederationPublicContractExtraTests(FederationFixture):
    def test_all_primary_addresses_use_their_declared_prefixes(self):
        value = self.build((self.ready_registry("one"),))
        self.assertTrue(value.federation.content_address.startswith(federation.PREFIX + ":"))
        self.assertTrue(value.policy.content_address.startswith(federation.POLICY_PREFIX + ":"))
        self.assertTrue(value.verification.content_address.startswith(federation.VERIFICATION_PREFIX + ":"))
        self.assertTrue(value.policy_evaluation.content_address.startswith(federation.POLICY_EVALUATION_PREFIX + ":"))
        self.assertTrue(value.runtime.content_address.startswith(federation.RUNTIME_PREFIX + ":"))

    def test_member_and_package_addresses_use_distinct_prefixes(self):
        value = self.build((self.ready_registry("one"),))
        self.assertTrue(value.federation.members[0].content_address.startswith(federation.MEMBER_PREFIX + ":"))
        self.assertTrue(value.federation.packages[0].content_address.startswith(federation.PACKAGE_PREFIX + ":"))
        self.assertNotEqual(value.federation.members[0].content_address, value.federation.packages[0].content_address)

    def test_check_and_stage_addresses_are_unique_within_their_planes(self):
        value = self.build((self.ready_registry("one"),))
        checks = value.verification.checks + value.policy_evaluation.checks
        stages = value.runtime.stages
        self.assertEqual(len({item.content_address for item in checks}), len(checks))
        self.assertEqual(len({item.content_address for item in stages}), len(stages))
        self.assertTrue(all(item.content_address.startswith(federation.CHECK_PREFIX + ":") for item in checks[: value.verification.check_count]))
        self.assertTrue(all(item.content_address.startswith(federation.POLICY_EVALUATION_PREFIX + "-check:") for item in checks[value.verification.check_count :]))
        self.assertTrue(all(item.content_address.startswith(federation.STAGE_PREFIX + ":") for item in stages))

    def test_bundle_summary_contains_only_cross_linked_receipts(self):
        value = self.build((self.ready_registry("one"),))
        summary = value.summary()
        self.assertEqual(summary["federation_id"], value.federation.federation_id)
        self.assertEqual(summary["policy_address"], value.policy.content_address)
        self.assertEqual(summary["verification_address"], value.verification.content_address)
        self.assertEqual(summary["policy_evaluation_address"], value.policy_evaluation.content_address)
        self.assertEqual(summary["runtime_address"], value.runtime.content_address)

    def test_federation_json_is_a_complete_public_bundle_document(self):
        value = self.build((self.ready_registry("one"), self.held_registry("two")))
        document = json.loads(federation.federation_json(value))
        self.assertEqual(document["federation"]["content_address"], value.federation.content_address)
        self.assertEqual(document["policy"]["content_address"], value.policy.content_address)
        self.assertEqual(document["verification"]["content_address"], value.verification.content_address)
        self.assertEqual(document["policy_evaluation"]["content_address"], value.policy_evaluation.content_address)
        self.assertEqual(document["runtime"]["content_address"], value.runtime.content_address)

    def test_federation_capabilities_describe_every_query_resource(self):
        capabilities = federation.federation_capabilities()
        self.assertEqual(capabilities["queries"]["resources"], list(federation.FederationQuery.RESOURCES))
        self.assertEqual(capabilities["queries"]["diff_resources"], list(federation.FederationDiffQuery.RESOURCES))
        self.assertEqual(capabilities["queries"]["max_limit"], federation.MAX_QUERY_ITEMS)

    def test_federation_capabilities_describe_every_artifact_file(self):
        capabilities = federation.federation_capabilities()
        self.assertEqual(capabilities["package"]["files"], list(federation.FILES))
        self.assertEqual(capabilities["diff"]["files"], list(federation.DIFF_FILES))
        self.assertEqual(capabilities["package"]["manifest"], federation.MANIFEST_NAME)
        self.assertEqual(capabilities["diff"]["files"][1], federation.DIFF_NAME)

    def test_federation_public_boundary_flags_are_all_false_for_private_surfaces(self):
        boundary = federation.federation_capabilities()["public_boundary"]
        self.assertFalse(boundary["source_paths"])
        self.assertFalse(boundary["nested_payloads"])
        self.assertTrue(boundary["identity_free"])

    def test_verification_rejects_a_wrong_typed_component(self):
        value = self.build((self.ready_registry("one"),))
        with self.assertRaises(ValidationError):
            federation.verify_federation("not-a-federation")
        with self.assertRaises(ValidationError):
            federation.verify_federation_bundle(value.federation)
        with self.assertRaises(ValidationError):
            federation.verify_policy_evaluation(value.policy)

    def test_diff_same_snapshot_has_no_directional_regressions(self):
        value = self.build((self.ready_registry("one"),))
        diff = federation.build_federation_diff(value, value)
        self.assertEqual(diff.state, "unchanged")
        self.assertEqual(diff.improved_count, 0)
        self.assertEqual(diff.regressed_count, 0)
        self.assertTrue(diff.release_ready)

    def test_diff_added_ready_snapshot_is_not_a_regression(self):
        baseline = self.build((self.ready_registry("one"),))
        candidate = self.build((self.ready_registry("one"), self.ready_registry("two")))
        diff = federation.build_federation_diff(baseline, candidate)
        self.assertGreater(diff.added_count, 0)
        self.assertEqual(diff.regressed_count, 0)
        self.assertTrue(diff.release_ready)

    def test_diff_blocked_candidate_marks_release_not_ready(self):
        baseline = self.build((self.ready_registry("one"),))
        candidate = self.build((self.blocked_registry("one"),))
        diff = federation.build_federation_diff(baseline, candidate)
        self.assertEqual(diff.state, "regressed")
        self.assertGreater(diff.regressed_count, 0)
        self.assertFalse(diff.release_ready)

    def test_diff_query_summary_is_a_single_projection_row(self):
        value = self.build((self.ready_registry("one"),))
        result = federation.query_federation_diff(federation.build_federation_diff(value, value), resource="summary")
        self.assertEqual(result.total_count, 1)
        self.assertEqual(result.returned_count, 1)
        self.assertEqual(result.items[0]["state"], "unchanged")

    def test_diff_query_action_and_direction_filters_can_be_combined(self):
        baseline = self.build((self.ready_registry("one"),))
        candidate = self.build((self.ready_registry("one"), self.ready_registry("two")))
        diff = federation.build_federation_diff(baseline, candidate)
        result = federation.query_federation_diff(diff, resource="items", action="added", direction="improved")
        self.assertTrue(all(item["action"] == "added" for item in result.items))
        self.assertTrue(all(item["direction"] == "improved" for item in result.items))

    def test_federation_from_mapping_rejects_private_fields(self):
        body = self.build((self.ready_registry("one"),)).federation.to_dict()
        body["source_path"] = "C:/private"
        with self.assertRaises(ValidationError):
            federation.federation_from_mapping(body)

    def test_policy_mapping_round_trip_is_address_preserving(self):
        value = self.build((self.ready_registry("one"),))
        rebuilt = federation.federation_policy_from_mapping(value.policy.to_dict())
        self.assertEqual(rebuilt.to_dict(), value.policy.to_dict())
        self.assertEqual(federation.address_federation_policy(rebuilt), value.policy.content_address)

    def test_verification_mapping_round_trip_is_address_preserving(self):
        value = self.build((self.ready_registry("one"),))
        rebuilt = federation.federation_verification_from_mapping(value.verification.to_dict())
        self.assertEqual(rebuilt.to_dict(), value.verification.to_dict())
        self.assertEqual(federation.address_federation_verification(rebuilt), value.verification.content_address)

    def test_runtime_mapping_round_trip_is_address_preserving(self):
        value = self.build((self.ready_registry("one"),))
        rebuilt = federation.federation_runtime_from_mapping(value.runtime.to_dict())
        self.assertEqual(rebuilt.to_dict(), value.runtime.to_dict())
        self.assertEqual(federation.address_federation_runtime(rebuilt), value.runtime.content_address)

    def test_export_document_map_contains_no_binary_or_path_values(self):
        value = self.build((self.ready_registry("one"),))
        documents = federation.federation_export_documents(value)
        for name, document in documents.items():
            with self.subTest(name=name):
                self.assertIsInstance(document, str)
                self.assertNotIn("C:\\", document)
                self.assertNotIn("file://", document)

    def test_summary_csv_rejects_a_tampered_runtime_receipt(self):
        value = self.build((self.ready_registry("one"),))
        original = value.runtime.content_address
        value.runtime.content_address = "tampered:runtime"
        with self.assertRaises(ValidationError):
            federation.federation_summary_csv(value)
        value.runtime.content_address = original

    def test_discovery_preview_keeps_registry_entries_out_of_public_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_registry_for_preview(root, "one")
            preview = federation.inspect_federation_registry_root(root)
            encoded = json.dumps(preview)
            self.assertNotIn("package_address", encoded)
            self.assertNotIn("release_address", encoded)
            self.assertIn("registry_address", encoded)

    def _write_registry_for_preview(self, root, registry_id):
        registry.write_decision_assurance_history_series_release_registry(
            self.ready_registry(registry_id), root / registry_id
        )


class FederationDiscoveryCliTests(FederationFixture):
    command = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history-series-release-registry-federation"

    def test_cli_discover_emits_verified_path_free_preview(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry.write_decision_assurance_history_series_release_registry(
                self.ready_registry("one"), root / "one"
            )
            output = StringIO()
            with redirect_stdout(output):
                status = main([self.command + "-discover", "--root", str(root)])
            self.assertEqual(status, 0)
            preview = json.loads(output.getvalue())
            self.assertEqual(preview["verified_count"], 1)
            self.assertEqual(preview["registries"][0]["registry_id"], "registry:one")
            self.assertNotIn(str(root), output.getvalue())

    def test_cli_discover_recursive_mode_finds_grouped_registries(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            nested = root / "download" / "group"
            nested.mkdir(parents=True)
            registry.write_decision_assurance_history_series_release_registry(
                self.ready_registry("nested"), nested / "registry"
            )
            output = StringIO()
            with redirect_stdout(output):
                status = main([self.command + "-discover", "--root", str(root), "--recursive"])
            self.assertEqual(status, 0)
            preview = json.loads(output.getvalue())
            self.assertEqual(preview["candidate_count"], 1)
            self.assertEqual(preview["registries"][0]["registry_id"], "registry:nested")

    def test_cli_discover_rejects_a_missing_root(self):
        status = main([self.command + "-discover", "--root", "missing-root"])
        self.assertEqual(status, 2)
