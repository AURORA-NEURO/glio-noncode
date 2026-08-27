# ruff: noqa: E501

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from http.client import HTTPConnection
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode

import glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff as packet_diff
import glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review as packet_review
import glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance as packet_assurance
import glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate as packet_gate
import glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history as history
import glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory as observatory
import glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime as runtime
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet,
)
from glio_noncode.serialization import canonical_bytes


class ObservatoryFixture(unittest.TestCase):
    """Reusable public packet/history fixture for observatory tests."""

    @staticmethod
    def store(
        store_id: str, *, state: str = "ready", release_ready: bool = True, accepted: bool = True
    ) -> SimpleNamespace:
        ledger = SimpleNamespace(
            window_address="window:fixture",
            content_address=f"ledger:{store_id}",
            head_address=f"entry:{store_id}",
            entry_count=1,
        )
        return SimpleNamespace(
            store_id=store_id,
            content_address=f"store:{store_id}",
            ledger_address=ledger.content_address,
            head_address=ledger.head_address,
            entry_count=1,
            state=state,
            release_ready=release_ready,
            accepted=accepted,
            append_only=True,
            operation_count=1,
            ledger=ledger,
        )

    def catalog(self, *stores: SimpleNamespace):
        return build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_test_catalog(
            stores
        )

    def packet(
        self,
        *,
        packet_id: str = "packet",
        state: str = "ready",
        release_ready: bool = True,
        accepted: bool = True,
    ):
        catalog = self.catalog(
            self.store(packet_id, state=state, release_ready=release_ready, accepted=accepted)
        )
        from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance import (
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance,
        )
        from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation import (
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation,
        )
        from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate import (
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate,
        )
        from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime import (
            run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime,
        )

        catalog = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
            (self.store(packet_id, state=state, release_ready=release_ready, accepted=accepted),),
            catalog_id=f"catalog:{packet_id}",
        )
        catalog_runtime = run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime(
            catalog
        )
        federation = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation(
            catalog
        )
        assurance = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance(
            catalog
        )
        gate = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate(
            catalog, catalog_runtime, federation, assurance
        )
        return build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
            catalog,
            catalog_runtime,
            federation,
            assurance,
            gate,
            packet_id=packet_id,
        )

    def history_value(self, decision: str = "promote", suffix: str = "0"):
        if decision == "block":
            left = self.packet(packet_id=f"left:{suffix}")
            right = self.packet(
                packet_id=f"blocked:{suffix}", state="blocked", release_ready=False, accepted=False
            )
        elif decision in {"hold", "supersede"}:
            left = self.packet(packet_id=f"left:{suffix}")
            right = self.packet(
                packet_id=f"held:{suffix}", state="held", release_ready=False, accepted=True
            )
        else:
            left = self.packet(packet_id=f"left:{suffix}")
            right = self.packet(packet_id=f"right:{suffix}")
        diff = packet_diff.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff(
            left, right, diff_id=f"diff:{suffix}"
        )
        review = packet_review.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
            diff,
            review_id=f"review:{suffix}",
            decision=decision,
            decision_id=f"decision:{suffix}",
            detail=f"{decision} fixture {suffix}",
        )
        assurance = packet_assurance.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
            review, diff=diff, assurance_id=f"assurance:{suffix}"
        )
        gate = packet_gate.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
            diff, review, assurance, gate_id=f"gate:{suffix}"
        )
        return history.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            gate, history_id=f"history:{suffix}", detail=f"history {decision} {suffix}"
        )

    def write_history(self, root: str | Path, value, name: str) -> Path:
        destination = Path(root) / name
        history.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history(
            value, destination
        )
        return destination

    def build(self, decisions: tuple[str, ...] = ("promote", "promote")):
        return observatory.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
            tuple(
                self.history_value(decision, str(index)) for index, decision in enumerate(decisions)
            ),
            observatory_id="observatory:fixture",
        )

    @staticmethod
    def http_json(
        server, path: str, params: dict[str, str | tuple[str, ...]]
    ) -> tuple[int, str, dict]:
        query: list[tuple[str, str]] = []
        for key, value in params.items():
            if isinstance(value, tuple):
                query.extend((key, item) for item in value)
            else:
                query.append((key, value))
        connection = HTTPConnection("127.0.0.1", server.server_address[1], timeout=15)
        connection.request("GET", path + "?" + urlencode(query))
        response = connection.getresponse()
        content_type = response.getheader("Content-Type", "")
        payload = json.loads(response.read().decode("utf-8"))
        connection.close()
        return response.status, content_type, payload

    def real_packet(self) -> Path:
        return Path(r"C:\Users\murar\AppData\Local\Temp\glio-noncode-real-demo-9b0hnhh2\packet")


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_test_catalog(
    stores,
):
    """Keep fixture construction local while preserving the public builder."""

    return build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_test_catalog_builder(
        stores
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_test_catalog_builder(
    stores,
):
    return build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
        stores,
        catalog_id="catalog:fixture",
    )


class ObservatoryCoreTests(ObservatoryFixture):
    def test_ready_fixture_is_accepted_and_path_free(self):
        value = self.build()
        self.assertTrue(value.accepted)
        self.assertTrue(value.release_ready)
        self.assertEqual(value.state, "ready")
        self.assertEqual(value.observation_count, 2)
        self.assertEqual(value.transition_count, 1)
        self.assertEqual(value.rollup.observation_count, 2)
        self.assertEqual(value.rollup.transition_count, 1)
        self.assertEqual(value.rollup.stable_count, 1)
        self.assertNotIn("C:\\", json.dumps(value.to_dict()))

    def test_reruns_have_the_same_addresses(self):
        first = self.build()
        second = self.build()
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(
            observatory.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_json(
                first
            ),
            observatory.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_json(
                second
            ),
        )
        self.assertEqual(
            first.observations[0].content_address, second.observations[0].content_address
        )
        self.assertEqual(
            first.transitions[0].content_address, second.transitions[0].content_address
        )

    def test_observation_order_is_explicit_and_contiguous(self):
        value = self.build(("promote", "hold", "block", "promote"))
        self.assertEqual([item.ordinal for item in value.observations], [0, 1, 2, 3])
        self.assertEqual([item.ordinal for item in value.transitions], [0, 1, 2])
        self.assertEqual(value.observations[-1].ordinal, 3)
        self.assertEqual(value.latest_observation_address, value.observations[-1].content_address)

    def test_transition_classification_preserves_regression_block_and_recovery(self):
        value = self.build(("promote", "hold", "block", "promote"))
        self.assertEqual(
            [item.kind for item in value.transitions], ["regressed", "blocked", "recovered"]
        )
        self.assertEqual(value.rollup.regressed_count, 1)
        self.assertEqual(value.rollup.blocked_transition_count, 1)
        self.assertEqual(value.rollup.recovered_count, 1)

    def test_hold_and_supersede_transition_kinds_are_distinct(self):
        value = self.build(("promote", "hold", "supersede"))
        self.assertEqual([item.kind for item in value.transitions], ["regressed", "superseded"])
        self.assertEqual(value.rollup.superseded_count, 1)
        self.assertEqual(value.rollup.held_count, 2)

    def test_mixed_state_is_explicit_and_not_release_ready(self):
        value = self.build(("promote", "hold"))
        self.assertEqual(value.state, "mixed")
        self.assertTrue(value.accepted)
        self.assertFalse(value.release_ready)
        self.assertEqual(value.rollup.ready_count, 1)
        self.assertEqual(value.rollup.held_count, 1)

    def test_rollup_conserves_all_observation_and_transition_categories(self):
        value = self.build(("promote", "hold", "block", "promote", "supersede", "hold"))
        rollup = value.rollup
        self.assertEqual(
            rollup.observation_count, rollup.ready_count + rollup.held_count + rollup.blocked_count
        )
        self.assertEqual(rollup.observation_count, rollup.accepted_count + rollup.blocked_count)
        self.assertEqual(
            rollup.observation_count,
            rollup.promote_count + rollup.hold_count + rollup.block_count + rollup.supersede_count,
        )
        self.assertEqual(
            rollup.transition_count,
            rollup.stable_count
            + rollup.promoted_count
            + rollup.recovered_count
            + rollup.regressed_count
            + rollup.held_transition_count
            + rollup.blocked_transition_count
            + rollup.superseded_count
            + rollup.changed_count,
        )
        self.assertEqual(rollup.unique_history_count, value.observation_count)
        self.assertEqual(rollup.unique_gate_count, value.observation_count)
        self.assertEqual(rollup.unique_head_count, value.observation_count)

    def test_custom_observation_ids_are_preserved(self):
        histories = tuple(self.history_value("promote", str(index)) for index in range(2))
        value = observatory.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
            histories,
            observatory_id="observatory:custom",
            observation_ids=("baseline", "candidate"),
        )
        self.assertEqual(value.observatory_id, "observatory:custom")
        self.assertEqual(
            [item.observation_id for item in value.observations], ["baseline", "candidate"]
        )

    def test_observation_ids_have_bounded_cardinality(self):
        histories = tuple(self.history_value("promote", str(index)) for index in range(2))
        with self.assertRaises(ValidationError):
            observatory.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
                histories, observation_ids=("only-one",)
            )
        with self.assertRaises(ValidationError):
            observatory.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
                histories, observation_ids=("same", "same")
            )

    def test_empty_and_oversized_inputs_fail_closed(self):
        with self.assertRaises(ValidationError):
            observatory.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
                ()
            )
        too_many = tuple(
            self.history_value("promote", str(index))
            for index in range(
                observatory.MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_MAX_OBSERVATIONS
                + 1
            )
        )
        with self.assertRaises(ValidationError):
            observatory.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
                too_many
            )

    def test_invalid_history_type_fails_before_projection(self):
        with self.assertRaises(ValidationError):
            observatory.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
                (object(),)
            )
        with self.assertRaises(ValidationError):
            observatory.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_from_mappings(
                ("not-a-mapping",)
            )

    def test_mapping_round_trip_rehydrates_exact_value(self):
        value = self.build(("promote", "hold", "block"))
        restored = observatory.observatory_from_mapping(value.to_dict())
        self.assertEqual(restored.content_address, value.content_address)
        self.assertEqual(restored.to_dict(), value.to_dict())

    def test_mapping_mutations_are_rejected(self):
        value = self.build()
        mutation = value.to_dict()
        mutation["observatory_id"] = "bad"
        mutation["observations"][0]["content_address"] = "sha256:bad"
        with self.assertRaises(ValidationError):
            observatory.observatory_from_mapping(mutation)
        mutation = value.to_dict()
        mutation["checks"][0]["agent"] = "forbidden"
        with self.assertRaises(ValidationError):
            observatory.observatory_from_mapping(mutation)

    def test_public_boundary_rejects_agent_language_model_and_user_keys(self):
        value = self.build()
        for forbidden in ("agent", "language", "model", "user", "custom_agent", "source_language"):
            mutation = value.to_dict()
            mutation[forbidden] = "forbidden"
            with self.assertRaises(ValidationError, msg=forbidden):
                observatory.observatory_from_mapping(mutation)

    def test_schema_declares_states_files_and_resources(self):
        schema = observatory.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_schema()
        self.assertEqual(schema["exact_files"], ["manifest.json", "observatory.json"])
        self.assertEqual(
            schema["resources"],
            ["summary", "observations", "transitions", "checks", "verification"],
        )
        self.assertIn("mixed", schema["states"])
        self.assertTrue(schema["identity_free"])
        self.assertTrue(schema["timestamp_free"])

    def test_capabilities_declare_independent_verification_and_exports(self):
        capabilities = observatory.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_capabilities()
        self.assertTrue(capabilities["independent_verification"])
        self.assertTrue(capabilities["atomic_write"])
        self.assertEqual(capabilities["exports"], ["json", "csv", "markdown"])
        self.assertIn("query", capabilities["operations"])


class ObservatoryQueryTests(ObservatoryFixture):
    def setUp(self):
        self.value = self.build(("promote", "hold", "block", "promote", "supersede"))

    def test_query_each_resource_is_addressed(self):
        for resource, expected in (
            ("summary", 1),
            ("observations", 5),
            ("transitions", 4),
            ("checks", len(self.value.checks)),
            ("verification", 1),
        ):
            result = observatory.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
                self.value, resource=resource
            )
            self.assertEqual(result.total, expected)
            self.assertTrue(result.content_address)
            self.assertTrue(
                observatory.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_query(
                    result
                )
            )

    def test_query_filters_state_and_transition_kind(self):
        held = observatory.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
            self.value, resource="observations", state="held"
        )
        self.assertEqual(held.total, 2)
        self.assertTrue(all(item["state"] == "held" for item in held.items))
        blocked = observatory.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
            self.value, resource="observations", accepted=False
        )
        self.assertEqual(blocked.total, 1)
        transitions = observatory.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
            self.value, resource="transitions", transition_kind="recovered"
        )
        self.assertEqual(transitions.total, 1)
        self.assertEqual(transitions.items[0]["kind"], "recovered")

    def test_query_filters_text_and_release_readiness(self):
        text = observatory.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
            self.value, resource="observations", text="observation-0001"
        )
        self.assertEqual(text.total, 1)
        ready = observatory.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
            self.value, resource="observations", release_ready=True
        )
        self.assertEqual(ready.total, 2)
        self.assertTrue(all(item["release_ready"] for item in ready.items))

    def test_query_pagination_is_bounded_and_deterministic(self):
        first = observatory.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
            self.value, resource="observations", offset=1, limit=2
        )
        second = observatory.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
            self.value, resource="observations", offset=1, limit=2
        )
        self.assertEqual(first.items, second.items)
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual([item["ordinal"] for item in first.items], [1, 2])
        with self.assertRaises(ValidationError):
            observatory.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
                self.value, resource="observations", offset=-1
            )
        with self.assertRaises(ValidationError):
            observatory.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
                self.value, resource="observations", limit=0
            )

    def test_query_export_formats_are_stable(self):
        result = observatory.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
            self.value, resource="transitions"
        )
        json_value = observatory.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_query_json(
            result
        )
        csv_value = observatory.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_query_csv(
            result
        )
        markdown = observatory.render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_query_markdown(
            result
        )
        self.assertEqual(json.loads(json_value), result.to_dict())
        self.assertIn("ordinal", csv_value)
        self.assertIn("gate history observatory query", markdown)
        self.assertEqual(
            json_value,
            observatory.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_query_json(
                result
            ),
        )

    def test_verification_has_all_passed_checks(self):
        verification = observatory.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
            self.value
        )
        self.assertTrue(verification.accepted)
        self.assertEqual(verification.failed_count, 0)
        self.assertEqual(verification.passed_count, verification.check_count)
        self.assertEqual(len(verification.checks), verification.check_count)
        self.assertNotIn("agent", json.dumps(verification.to_dict()))

    def test_verification_schema_and_capabilities_are_identity_free(self):
        schema = observatory.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_verification_schema()
        capabilities = observatory.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_verification_capabilities()
        self.assertEqual(schema["resources"], ["summary", "checks"])
        self.assertTrue(schema["independent"])
        self.assertTrue(capabilities["recomputes"])
        self.assertNotIn("model", json.dumps(capabilities))


class ObservatoryPersistenceTests(ObservatoryFixture):
    def test_exact_two_file_round_trip(self):
        value = self.build()
        with tempfile.TemporaryDirectory() as root:
            destination = observatory.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
                value, Path(root) / "observatory"
            )
            self.assertEqual(
                {item.name for item in destination.iterdir()}, {"manifest.json", "observatory.json"}
            )
            loaded = observatory.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
                destination
            )
            self.assertEqual(loaded.to_dict(), value.to_dict())
            self.assertEqual(loaded.content_address, value.content_address)

    def test_overwrite_requires_explicit_flag(self):
        value = self.build()
        with tempfile.TemporaryDirectory() as root:
            destination = observatory.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
                value, Path(root) / "observatory"
            )
            with self.assertRaises(ValidationError):
                observatory.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
                    value, destination
                )
            observatory.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
                value, destination, overwrite=True
            )

    def test_extra_file_is_rejected(self):
        value = self.build()
        with tempfile.TemporaryDirectory() as root:
            destination = observatory.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
                value, Path(root) / "observatory"
            )
            (destination / "extra.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                observatory.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
                    destination
                )

    def test_missing_file_is_rejected(self):
        value = self.build()
        with tempfile.TemporaryDirectory() as root:
            destination = observatory.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
                value, Path(root) / "observatory"
            )
            (destination / "manifest.json").unlink()
            with self.assertRaises(ValidationError):
                observatory.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
                    destination
                )

    def test_noncanonical_document_is_rejected(self):
        value = self.build()
        with tempfile.TemporaryDirectory() as root:
            destination = observatory.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
                value, Path(root) / "observatory"
            )
            document = destination / "observatory.json"
            document.write_bytes(b'{ "wrong": true }\n')
            with self.assertRaises(ValidationError):
                observatory.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
                    destination
                )

    def test_manifest_byte_address_tamper_is_rejected(self):
        value = self.build()
        with tempfile.TemporaryDirectory() as root:
            destination = observatory.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
                value, Path(root) / "observatory"
            )
            manifest_path = destination / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["byte_count"] += 1
            manifest_path.write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                observatory.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
                    destination
                )

    def test_nested_observation_tamper_is_rejected(self):
        value = self.build()
        with tempfile.TemporaryDirectory() as root:
            destination = observatory.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
                value, Path(root) / "observatory"
            )
            document_path = destination / "observatory.json"
            document = json.loads(document_path.read_text(encoding="utf-8"))
            document["observations"][0]["detail"] = "tampered"
            document_path.write_bytes(canonical_bytes(document))
            with self.assertRaises(ValidationError):
                observatory.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
                    destination
                )

    def test_file_path_and_symlink_inputs_are_rejected(self):
        value = self.build()
        with tempfile.TemporaryDirectory() as root:
            destination = observatory.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
                value, Path(root) / "observatory"
            )
            with self.assertRaises(ValidationError):
                observatory.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
                    destination / "observatory.json"
                )
            try:
                link = Path(root) / "link"
                link.symlink_to(destination, target_is_directory=True)
            except (OSError, NotImplementedError):
                return
            with self.assertRaises(ValidationError):
                observatory.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
                    link
                )


class ObservatoryRuntimeTests(ObservatoryFixture):
    def test_default_policy_accepts_ready_observatory(self):
        value = self.build()
        report = runtime.run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime(
            value
        )
        self.assertTrue(report.accepted)
        self.assertTrue(report.release_ready)
        self.assertEqual(report.state, "ready")
        self.assertEqual(
            [item.name for item in report.stages],
            ["load", "verify", "policy", "project", "complete"],
        )
        self.assertTrue(all(item.state == "passed" for item in report.stages))
        self.assertEqual(report.policy_evaluation.check_count, 8)

    def test_runtime_addresses_are_stable(self):
        value = self.build()
        first = runtime.run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime(
            value, runtime_id="runtime:stable"
        )
        second = runtime.run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime(
            value, runtime_id="runtime:stable"
        )
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(
            first.policy_evaluation.content_address, second.policy_evaluation.content_address
        )
        self.assertEqual(
            [stage.content_address for stage in first.stages],
            [stage.content_address for stage in second.stages],
        )

    def test_mixed_observatory_is_blocked_by_default_policy(self):
        value = self.build(("promote", "hold"))
        report = runtime.run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime(
            value
        )
        self.assertFalse(report.accepted)
        self.assertFalse(report.release_ready)
        self.assertEqual(report.state, "blocked")
        self.assertEqual(report.policy_evaluation.failed_count, 3)
        failed = [item.kind for item in report.policy_evaluation.checks if not item.passed]
        self.assertEqual(
            failed, ["latest-release-ready", "regression-budget", "mixed-state-policy"]
        )

    def test_policy_can_allow_mixed_state_but_latest_not_ready_stays_held(self):
        value = self.build(("promote", "hold"))
        policy = runtime.default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_policy(
            allow_mixed_state=True, maximum_regressions=1, require_latest_release_ready=False
        )
        report = runtime.run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime(
            value, policy=policy
        )
        self.assertTrue(report.accepted)
        self.assertFalse(report.release_ready)
        self.assertEqual(report.state, "held")

    def test_regression_budget_is_explicit(self):
        value = self.build(("promote", "hold", "promote"))
        strict = runtime.default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_policy(
            maximum_regressions=0, allow_mixed_state=True
        )
        report = runtime.run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime(
            value, policy=strict
        )
        self.assertFalse(report.accepted)
        self.assertIn(
            "regression-budget",
            [item.kind for item in report.policy_evaluation.checks if not item.passed],
        )

    def test_blocked_budget_is_explicit(self):
        value = self.build(("promote", "block", "promote"))
        policy = runtime.default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_policy(
            maximum_blocked_observations=0,
            allow_mixed_state=True,
            require_latest_release_ready=True,
        )
        report = runtime.run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime(
            value, policy=policy
        )
        self.assertFalse(report.accepted)
        self.assertIn(
            "blocked-budget",
            [item.kind for item in report.policy_evaluation.checks if not item.passed],
        )

    def test_policy_thresholds_are_bounded(self):
        with self.assertRaises(ValidationError):
            runtime.default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_policy(
                minimum_observations=0
            )
        with self.assertRaises(ValidationError):
            runtime.default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_policy(
                maximum_regressions=-1
            )
        with self.assertRaises(ValidationError):
            runtime.default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_policy(
                policy_id="x" * 257
            )

    def test_runtime_queries_are_bounded(self):
        value = self.build()
        report = runtime.run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime(
            value
        )
        stages = runtime.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime(
            report, resource="stages"
        )
        checks = runtime.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime(
            report, resource="policy-checks", passed=True
        )
        summary = runtime.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime(
            report, resource="summary"
        )
        self.assertEqual(stages.total, 5)
        self.assertEqual(checks.total, 8)
        self.assertEqual(summary.total, 1)
        self.assertTrue(
            runtime.address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_query(
                stages
            )
            == stages.content_address
        )

    def test_runtime_query_stage_text_filter(self):
        value = self.build()
        report = runtime.run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime(
            value
        )
        result = runtime.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime(
            report, resource="stages", stage="verify", text="independent"
        )
        self.assertEqual(result.total, 1)
        self.assertEqual(result.items[0]["name"], "verify")
        self.assertEqual(result.items[0]["state"], "passed")

    def test_runtime_exports_are_deterministic(self):
        value = self.build()
        report = runtime.run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime(
            value
        )
        self.assertEqual(
            json.loads(
                runtime.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_json(
                    report
                )
            ),
            report.to_dict(),
        )
        self.assertIn(
            "name",
            runtime.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_csv(
                report
            ),
        )
        self.assertIn(
            "gate history observatory runtime",
            runtime.render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_markdown(
                report
            ),
        )

    def test_runtime_schema_capabilities_and_policy_surfaces(self):
        schema = runtime.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_schema()
        capabilities = runtime.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_capabilities()
        policy_schema = runtime.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_policy_schema()
        self.assertEqual(schema["exact_files"], ["manifest.json", "runtime.json"])
        self.assertTrue(schema["policy_governed"])
        self.assertTrue(capabilities["ordered_stages"])
        self.assertEqual(len(policy_schema["fields"]), 7)

    def test_runtime_mapping_round_trip(self):
        value = self.build()
        report = runtime.run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime(
            value
        )
        restored = runtime.runtime_from_mapping(report.to_dict())
        self.assertEqual(restored.to_dict(), report.to_dict())
        self.assertEqual(restored.content_address, report.content_address)


class RuntimePersistenceAndSurfaceTests(ObservatoryFixture):
    def test_ready_runtime_round_trip(self):
        value = self.build()
        report = runtime.run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime(
            value
        )
        with tempfile.TemporaryDirectory() as root:
            destination = runtime.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime(
                report, Path(root) / "runtime"
            )
            self.assertEqual(
                {item.name for item in destination.iterdir()}, {"manifest.json", "runtime.json"}
            )
            loaded = runtime.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime(
                destination
            )
            self.assertEqual(loaded.to_dict(), report.to_dict())

    def test_runtime_overwrite_guard_and_extra_file(self):
        value = self.build()
        report = runtime.run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime(
            value
        )
        with tempfile.TemporaryDirectory() as root:
            destination = runtime.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime(
                report, Path(root) / "runtime"
            )
            with self.assertRaises(ValidationError):
                runtime.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime(
                    report, destination
                )
            (destination / "extra.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                runtime.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime(
                    destination
                )

    def test_runtime_manifest_and_nested_tamper_are_rejected(self):
        value = self.build()
        report = runtime.run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime(
            value
        )
        with tempfile.TemporaryDirectory() as root:
            destination = runtime.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime(
                report, Path(root) / "runtime"
            )
            manifest_path = destination / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["byte_count"] += 1
            manifest_path.write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                runtime.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime(
                    destination
                )
            manifest_path.write_bytes(
                canonical_bytes(json.loads(runtime_manifest_bytes_for_report(report)))
            )
            document = json.loads((destination / "runtime.json").read_text(encoding="utf-8"))
            document["runtime_id"] = "tampered"
            (destination / "runtime.json").write_bytes(canonical_bytes(document))
            with self.assertRaises(ValidationError):
                runtime.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime(
                    destination
                )

    def test_blocked_runtime_is_not_persisted(self):
        value = self.build(("promote", "hold"))
        report = runtime.run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime(
            value
        )
        self.assertFalse(report.accepted)
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValidationError):
                runtime.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime(
                    report, Path(root) / "blocked"
                )

    def test_runtime_query_exports_are_stable(self):
        value = self.build()
        report = runtime.run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime(
            value
        )
        result = runtime.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime(
            report, resource="policy-checks"
        )
        self.assertEqual(
            json.loads(
                runtime.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_query_json(
                    result
                )
            ),
            result.to_dict(),
        )
        self.assertIn(
            "ordinal",
            runtime.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_query_csv(
                result
            ),
        )
        self.assertIn(
            "gate history observatory runtime query",
            runtime.render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_query_markdown(
                result
            ),
        )

    def test_cli_schema_and_capability_commands(self):
        commands = (
            "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-schema",
            "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-capabilities",
            "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-runtime-schema",
            "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-runtime-policy-schema",
        )
        for command in commands:
            output = StringIO()
            with redirect_stdout(output):
                status = main([command])
            self.assertEqual(status, 0, command)
            self.assertTrue(json.loads(output.getvalue()), command)

    def test_cli_builds_and_queries_persisted_history_archives(self):
        with tempfile.TemporaryDirectory() as root:
            history_directory = self.write_history(
                root, self.history_value("promote", "cli"), "history"
            )
            destination = Path(root) / "observatory"
            output = StringIO()
            with redirect_stdout(output):
                status = main(
                    [
                        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory",
                        "--history-directory",
                        str(history_directory),
                        "--history-directory",
                        str(history_directory),
                        "--destination",
                        str(destination),
                        "--format",
                        "summary",
                    ]
                )
            self.assertEqual(status, 0)
            self.assertTrue(destination.is_dir())
            summary = json.loads(output.getvalue())
            self.assertEqual(summary["observation_count"], 2)
            query_output = StringIO()
            with redirect_stdout(query_output):
                status = main(
                    [
                        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-query",
                        "--input",
                        str(destination),
                        "--resource",
                        "observations",
                        "--format",
                        "json",
                    ]
                )
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(query_output.getvalue())["total"], 2)
            runtime_destination = Path(root) / "runtime"
            runtime_output = StringIO()
            with redirect_stdout(runtime_output):
                status = main(
                    [
                        "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-runtime",
                        "--history-directory",
                        str(history_directory),
                        "--history-directory",
                        str(history_directory),
                        "--destination",
                        str(runtime_destination),
                        "--format",
                        "summary",
                    ]
                )
            self.assertEqual(status, 0)
            self.assertTrue(runtime_destination.is_dir())
            self.assertTrue(json.loads(runtime_output.getvalue())["accepted"])

    def test_http_schema_build_query_and_runtime_routes(self):
        with tempfile.TemporaryDirectory() as root:
            history_directory = self.write_history(
                root, self.history_value("promote", "http"), "history"
            )
            server = create_server("127.0.0.1", 0, Path(root) / "data")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory"
            try:
                status, content_type, schema = self.http_json(server, base + "/schema", {})
                self.assertEqual(status, 200)
                self.assertIn("application/json", content_type)
                self.assertEqual(schema["exact_files"], ["manifest.json", "observatory.json"])
                history_directory_two = self.write_history(
                    root, self.history_value("promote", "http-two"), "history-two"
                )
                status, _, summary = self.http_json(
                    server,
                    base,
                    {"history_directory": (str(history_directory), str(history_directory_two))},
                )
                self.assertEqual(status, 200)
                self.assertEqual(summary["observation_count"], 2)
                status, _, query = self.http_json(
                    server,
                    base + "/query",
                    {
                        "history_directory": (str(history_directory), str(history_directory_two)),
                        "resource": "observations",
                        "limit": "1",
                    },
                )
                self.assertEqual(status, 200)
                self.assertEqual(query["total"], 2)
                self.assertEqual(len(query["items"]), 1)
                status, _, runtime_schema = self.http_json(server, base + "/runtime/schema", {})
                self.assertEqual(status, 200)
                self.assertEqual(runtime_schema["exact_files"], ["manifest.json", "runtime.json"])
                status, _, runtime_summary = self.http_json(
                    server,
                    base + "/runtime",
                    {"history_directory": (str(history_directory), str(history_directory_two))},
                )
                self.assertEqual(status, 200)
                self.assertTrue(runtime_summary["accepted"])
                status, _, runtime_query = self.http_json(
                    server,
                    base + "/runtime/query",
                    {
                        "history_directory": (str(history_directory), str(history_directory_two)),
                        "resource": "policy-checks",
                        "passed": "true",
                    },
                )
                self.assertEqual(status, 200)
                self.assertEqual(runtime_query["total"], 8)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_real_downloaded_packet_builds_history_observatory_and_runtime(self):
        packet_directory = self.real_packet()
        if not packet_directory.is_dir():
            self.skipTest("retained downloaded packet fixture is not installed")
        with tempfile.TemporaryDirectory() as root:
            history_value = history.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_from_directories(
                packet_directory, packet_directory, history_id="history:downloaded"
            )
            history_directory = self.write_history(root, history_value, "downloaded-history")
            value = observatory.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_from_directories(
                (history_directory, history_directory),
                observation_ids=("downloaded-baseline", "downloaded-rerun"),
            )
            self.assertTrue(value.accepted)
            self.assertTrue(value.release_ready)
            self.assertEqual(value.rollup.stable_count, 1)
            report = runtime.run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime(
                value
            )
            self.assertTrue(report.accepted)
            self.assertTrue(report.release_ready)
            self.assertEqual(
                observatory.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
                    value
                ).failed_count,
                0,
            )


def runtime_manifest_bytes_for_report(report) -> bytes:
    """Build the exact manifest used by the runtime writer for tamper tests."""

    document = canonical_bytes(report.to_dict())
    body = {
        "manifest_version": runtime.MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_VERSION,
        "runtime": report.to_dict(),
        "byte_count": len(document),
        "byte_address": runtime.hash_bytes(
            document,
            prefix=runtime.MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_PREFIX
            + "-bytes",
        ),
    }
    return canonical_bytes(
        body
        | {
            "manifest_address": runtime.content_hash(
                body,
                prefix=runtime.MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_PREFIX
                + "-manifest",
            )
        }
    )


if __name__ == "__main__":
    unittest.main()
