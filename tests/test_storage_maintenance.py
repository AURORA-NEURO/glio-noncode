"""Deep contract, API, CLI, and packet tests for storage maintenance planning."""

from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.runtime import CaseRuntime
from glio_noncode.storage_audit import build_storage_audit
from glio_noncode.storage_maintenance import (
    build_storage_maintenance_plan,
    build_storage_maintenance_policy,
    diff_storage_maintenance,
    query_storage_maintenance,
    storage_maintenance_csv,
    storage_maintenance_markdown,
)
from glio_noncode.storage_maintenance_contracts import (
    StorageMaintenanceActionKind,
    StorageMaintenancePlan,
    StorageMaintenanceSeverity,
    StorageMaintenanceState,
)
from glio_noncode.storage_maintenance_observability import (
    build_storage_maintenance_observability,
    query_storage_maintenance_events,
    storage_maintenance_events_csv,
    storage_maintenance_metrics_csv,
)
from glio_noncode.storage_maintenance_packet import (
    build_storage_maintenance_packet,
    load_storage_maintenance_packet,
    verify_storage_maintenance_packet,
    write_storage_maintenance_packet,
)
from glio_noncode.storage_maintenance_review import (
    build_storage_maintenance_review_queue,
    query_storage_maintenance_review,
    storage_maintenance_review_csv,
    storage_maintenance_review_markdown,
)

from .helpers import fixture_manifest


class StorageMaintenanceTests(unittest.TestCase):
    def _runtime(self, directory: str) -> tuple[CaseRuntime, object]:
        runtime = CaseRuntime(directory)
        return runtime, runtime.evaluate(fixture_manifest())

    def _get(self, connection: HTTPConnection, path: str) -> tuple[int, dict]:
        connection.request("GET", path)
        response = connection.getresponse()
        return response.status, json.loads(response.read())

    def _post(
        self,
        connection: HTTPConnection,
        path: str,
        payload: dict,
    ) -> tuple[int, dict]:
        body = json.dumps(payload).encode("utf-8")
        connection.request(
            "POST",
            path,
            body=body,
            headers={"Content-Type": "application/json", "Content-Length": str(len(body))},
        )
        response = connection.getresponse()
        return response.status, json.loads(response.read())

    def test_clean_plan_is_deterministic_strict_and_review_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            first = build_storage_maintenance_plan(runtime)
            second = build_storage_maintenance_plan(runtime)
            self.assertEqual(first.to_dict(), second.to_dict())
            self.assertEqual(first.state, StorageMaintenanceState.CLEAN)
            self.assertTrue(first.accepted)
            self.assertTrue(first.audit_accepted)
            self.assertFalse(first.safe_to_apply)
            self.assertFalse(first.requires_review)
            self.assertEqual(first.action_count, 1)
            self.assertEqual(first.actions[0].kind, StorageMaintenanceActionKind.NO_ACTION)
            self.assertEqual(first.actions[0].severity, StorageMaintenanceSeverity.NONE)
            self.assertTrue(first.actions[0].review_only)
            self.assertFalse(first.actions[0].approval_required)
            self.assertEqual(first, StorageMaintenancePlan.from_mapping(first.to_dict()))
            serialized = json.dumps(first.to_dict(), sort_keys=True).lower()
            for forbidden in (
                "agent_id",
                "assistant_id",
                "author_name",
                "email_address",
                "language_name",
                "model_name",
                "patient_id",
                "producer_name",
                "subject_id",
            ):
                self.assertNotIn(forbidden, serialized)

    def test_plan_exports_are_stable_and_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, _ = self._runtime(directory)
            plan = build_storage_maintenance_plan(runtime)
            queried = query_storage_maintenance(plan, limit=1)
            self.assertEqual(queried.total, 1)
            self.assertFalse(queried.has_more)
            self.assertEqual(queried.items[0]["kind"], "no-action")
            self.assertIn("action_id", storage_maintenance_csv(plan).splitlines()[0])
            self.assertIn("# Storage maintenance plan", storage_maintenance_markdown(plan))
            self.assertEqual(
                query_storage_maintenance(plan, text="accepted").total,
                1,
            )
            self.assertEqual(query_storage_maintenance(plan, reversible_only=True).total, 0)
            with self.assertRaises(ValidationError):
                query_storage_maintenance(plan, kind="unsupported")
            with self.assertRaises(ValidationError):
                query_storage_maintenance(plan, limit=501)

    def test_orphan_and_unexpected_entries_route_to_reversible_review(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, _ = self._runtime(directory)
            orphan_address = runtime.store.store.put({"orphan": True})
            (Path(directory) / "objects" / "leftover.tmp").write_text("leftover", encoding="utf-8")
            report = build_storage_audit(runtime)
            plan = build_storage_maintenance_plan(report)
            self.assertFalse(plan.audit_accepted)
            self.assertEqual(plan.state, StorageMaintenanceState.REVIEW)
            self.assertEqual(plan.orphan_count, 1)
            self.assertEqual(plan.unexpected_count, 1)
            kinds = tuple(item.kind for item in plan.actions)
            self.assertIn(StorageMaintenanceActionKind.QUARANTINE_ORPHAN, kinds)
            self.assertIn(StorageMaintenanceActionKind.QUARANTINE_UNEXPECTED, kinds)
            self.assertTrue(all(item.reversible for item in plan.actions))
            reversible = query_storage_maintenance(plan, reversible_only=True)
            self.assertEqual(reversible.total, 2)
            self.assertTrue(
                any(orphan_address == item["target_address"] for item in reversible.items)
            )
            self.assertTrue(all(item["review_only"] for item in reversible.items))

    def test_missing_and_invalid_objects_block_recovery_routing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, dossier = self._runtime(directory)
            run_record = runtime.get_run(dossier.run_id)
            digest = str(run_record["dossier_address"]).split(":", 1)[1]
            (runtime.store.store.objects / f"{digest}.json").unlink()
            report = build_storage_audit(runtime)
            plan = build_storage_maintenance_plan(report)
            self.assertEqual(plan.state, StorageMaintenanceState.BLOCKED)
            self.assertIn(
                StorageMaintenanceActionKind.RESTORE_MISSING_OBJECT,
                tuple(item.kind for item in plan.actions),
            )
            self.assertTrue(
                any(item.severity is StorageMaintenanceSeverity.HIGH for item in plan.actions)
            )
            self.assertFalse(plan.safe_to_apply)
            self.assertEqual(StorageMaintenancePlan.from_mapping(plan.to_dict()), plan)

    def test_invalid_object_and_failed_index_actions_have_precise_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, dossier = self._runtime(directory)
            run_record = runtime.get_run(dossier.run_id)
            digest = str(run_record["event_address"]).split(":", 1)[1]
            event_path = runtime.store.store.objects / f"{digest}.json"
            event = json.loads(event_path.read_text(encoding="utf-8"))
            event["events"][0]["event_type"] = "tampered"
            event_path.write_text(json.dumps(event), encoding="utf-8")
            report = build_storage_audit(runtime)
            plan = build_storage_maintenance_plan(report)
            self.assertEqual(plan.state, StorageMaintenanceState.BLOCKED)
            invalid = [
                item
                for item in plan.actions
                if item.kind is StorageMaintenanceActionKind.REPAIR_INVALID_OBJECT
            ]
            self.assertTrue(invalid)
            self.assertTrue(all(item.target_path.startswith("objects/") for item in invalid))
            failed = [
                item
                for item in plan.actions
                if item.kind is StorageMaintenanceActionKind.REPLAY_RUN
            ]
            self.assertTrue(failed)
            self.assertTrue(all(item.target_path.startswith("runs/") for item in failed))

    def test_policy_can_suppress_classes_and_fail_closed_on_action_overflow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, _ = self._runtime(directory)
            runtime.store.store.put({"orphan": True})
            (Path(directory) / "objects" / "leftover.tmp").write_text("leftover", encoding="utf-8")
            policy = build_storage_maintenance_policy(
                plan_id="bounded-plan",
                max_actions=1,
                include_orphans=True,
                include_unexpected=True,
                include_missing=False,
                include_invalid=False,
                include_failed_indexes=False,
            )
            plan = build_storage_maintenance_plan(runtime, policy=policy)
            self.assertEqual(plan.plan_id, "bounded-plan")
            self.assertEqual(plan.action_count, 1)
            self.assertFalse(plan.accepted)
            self.assertEqual(plan.state, StorageMaintenanceState.BLOCKED)
            self.assertEqual(plan.policy, policy)
            with self.assertRaises(ValidationError):
                build_storage_maintenance_plan(runtime, policy=policy, plan_id="other-plan")
            with self.assertRaises(ValidationError):
                build_storage_maintenance_policy(plan_id="bad-bool", include_orphans=1)  # type: ignore[arg-type]

    def test_plan_diff_tracks_action_and_audit_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, _ = self._runtime(directory)
            before = build_storage_maintenance_plan(runtime)
            runtime.store.store.put({"orphan": True})
            after = build_storage_maintenance_plan(runtime)
            result = diff_storage_maintenance(before, after)
            self.assertTrue(result.accepted)
            self.assertTrue(result.audit_changed)
            self.assertTrue(result.state_changed)
            self.assertTrue(result.changed_action_ids)
            self.assertEqual(result, diff_storage_maintenance(before.to_dict(), after.to_dict()))

    def test_observability_is_timestamp_free_addressed_and_replayable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            plan = build_storage_maintenance_plan(runtime)
            projection = build_storage_maintenance_observability(plan)
            self.assertGreaterEqual(projection.event_count, 3)
            self.assertEqual(projection.metric_count, 14)
            self.assertEqual(
                projection,
                type(projection).from_mapping(projection.to_dict()),
            )
            self.assertTrue(
                all(item.plan_address == plan.content_address for item in projection.events)
            )
            self.assertTrue(
                all(item.plan_address == plan.content_address for item in projection.metrics)
            )
            self.assertEqual(
                len(query_storage_maintenance_events(projection, event_type="action-routed")),
                1,
            )
            self.assertEqual(
                query_storage_maintenance_events(projection, kind="no-action")[0].kind.value,
                "no-action",
            )
            self.assertEqual(
                query_storage_maintenance_events(projection, severity="none")[0].severity.value,
                "none",
            )
            self.assertIn("event_id", storage_maintenance_events_csv(projection).splitlines()[0])
            self.assertIn(
                "metric_name", storage_maintenance_metrics_csv(projection).splitlines()[0]
            )
            with self.assertRaises(ValidationError):
                query_storage_maintenance_events(projection, event_type="unknown")

    def test_review_queue_orders_blocked_routes_before_quarantine(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, dossier = self._runtime(directory)
            run_record = runtime.get_run(dossier.run_id)
            digest = str(run_record["dossier_address"]).split(":", 1)[1]
            (runtime.store.store.objects / f"{digest}.json").unlink()
            runtime.store.store.put({"orphan": True})
            queue = build_storage_maintenance_review_queue(build_storage_maintenance_plan(runtime))
            self.assertTrue(queue.accepted)
            self.assertGreaterEqual(queue.blocked_count, 1)
            self.assertGreaterEqual(queue.review_count, 1)
            priorities = tuple(item.priority for item in queue.items)
            self.assertEqual(priorities, tuple(sorted(priorities, reverse=True)))
            self.assertEqual(queue, type(queue).from_mapping(queue.to_dict()))
            blocked = query_storage_maintenance_review(queue, disposition="blocked")
            self.assertGreaterEqual(blocked.total, 1)
            self.assertTrue(all(item["priority"] >= 300 for item in blocked.items))
            self.assertGreaterEqual(
                query_storage_maintenance_review(queue, route="recovery").total, 1
            )
            self.assertIn("review_id", storage_maintenance_review_csv(queue).splitlines()[0])
            self.assertIn(
                "# Storage maintenance review queue", storage_maintenance_review_markdown(queue)
            )
            with self.assertRaises(ValidationError):
                query_storage_maintenance_review(queue, route="unknown")

    def test_packet_writes_verifies_and_hydrates_exact_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            plan = build_storage_maintenance_plan(runtime)
            packet = build_storage_maintenance_packet(plan)
            destination = Path(directory) / "packet"
            write_storage_maintenance_packet(packet, destination)
            verification = verify_storage_maintenance_packet(destination)
            self.assertTrue(verification.accepted, verification.to_dict())
            offline = load_storage_maintenance_packet(destination)
            self.assertEqual(offline.plan, plan)
            self.assertEqual(offline.verification, verification)
            self.assertEqual(
                sorted(path.relative_to(destination).as_posix() for path in destination.rglob("*")),
                [
                    "maintenance",
                    "maintenance/actions.csv",
                    "maintenance/capabilities.json",
                    "maintenance/observability.json",
                    "maintenance/plan.json",
                    "maintenance/review-queue.json",
                    "maintenance/schema.json",
                    "maintenance/summary.json",
                    "manifest.json",
                ],
            )
            with self.assertRaises(ValidationError):
                write_storage_maintenance_packet(packet, destination)

    def test_packet_tamper_and_unexpected_file_detection_refuse_hydration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            packet = build_storage_maintenance_packet(build_storage_maintenance_plan(runtime))
            destination = Path(directory) / "packet"
            write_storage_maintenance_packet(packet, destination)
            actions = destination / "maintenance" / "actions.csv"
            actions.write_text(actions.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
            (destination / "unexpected.txt").write_text("unexpected", encoding="utf-8")
            verification = verify_storage_maintenance_packet(destination)
            self.assertFalse(verification.accepted)
            self.assertIn("maintenance/actions.csv", verification.tampered_paths)
            self.assertIn("unexpected.txt", verification.unexpected_paths)
            with self.assertRaises(ValidationError):
                load_storage_maintenance_packet(destination)

    def test_packet_public_boundary_rejects_prohibited_json_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            packet = build_storage_maintenance_packet(build_storage_maintenance_plan(runtime))
            destination = Path(directory) / "packet"
            write_storage_maintenance_packet(packet, destination)
            plan_path = destination / "maintenance" / "plan.json"
            payload = json.loads(plan_path.read_text(encoding="utf-8"))
            payload["agent_id"] = "prohibited"
            plan_path.write_text(json.dumps(payload), encoding="utf-8")
            verification = verify_storage_maintenance_packet(destination)
            self.assertFalse(verification.accepted)
            self.assertTrue(verification.boundary_violations)

    def test_cli_surfaces_build_query_packet_and_verify(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plan_path = Path(directory) / "plan.json"
            packet_path = Path(directory) / "packet"
            self.assertEqual(
                main(
                    [
                        "storage-maintenance",
                        "--data-root",
                        directory,
                        "--output",
                        str(plan_path),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(plan_path.read_text(encoding="utf-8"))["accepted"])
            query_path = Path(directory) / "query.json"
            self.assertEqual(
                main(
                    [
                        "storage-maintenance",
                        "--data-root",
                        directory,
                        "--kind",
                        "no-action",
                        "--output",
                        str(query_path),
                    ]
                ),
                0,
            )
            self.assertEqual(json.loads(query_path.read_text(encoding="utf-8"))["total"], 1)
            packet_result = Path(directory) / "packet-result.json"
            self.assertEqual(
                main(
                    [
                        "storage-maintenance-packet",
                        "--data-root",
                        directory,
                        "--destination",
                        str(packet_path),
                        "--output",
                        str(packet_result),
                    ]
                ),
                0,
            )
            verification_path = Path(directory) / "verification.json"
            self.assertEqual(
                main(
                    [
                        "storage-maintenance-packet-verify",
                        str(packet_path),
                        "--output",
                        str(verification_path),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(verification_path.read_text(encoding="utf-8"))["accepted"])
            observability_path = Path(directory) / "observability.json"
            self.assertEqual(
                main(
                    [
                        "storage-maintenance-observability",
                        "--data-root",
                        directory,
                        "--output",
                        str(observability_path),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(observability_path.read_text(encoding="utf-8"))["accepted"])
            review_path = Path(directory) / "review.json"
            self.assertEqual(
                main(
                    [
                        "storage-maintenance-review",
                        "--data-root",
                        directory,
                        "--output",
                        str(review_path),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(review_path.read_text(encoding="utf-8"))["accepted"])
            self.assertEqual(main(["storage-maintenance-schema"]), 0)
            self.assertEqual(main(["storage-maintenance-packet-capabilities"]), 0)

    def test_http_surfaces_share_plan_and_packet_addresses(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=60)
                status, maintenance = self._get(connection, "/v1/storage/maintenance?limit=1")
                self.assertEqual(status, 200)
                self.assertTrue(maintenance["plan"]["accepted"])
                self.assertEqual(maintenance["query"]["total"], 1)
                status, schema = self._get(connection, "/v1/storage/maintenance/schema")
                self.assertEqual(status, 200)
                self.assertEqual(schema["boundary"], "public_storage_maintenance")
                status, packet_schema = self._get(
                    connection, "/v1/storage/maintenance/packet/schema"
                )
                self.assertEqual(status, 200)
                self.assertEqual(packet_schema["payload_count"], 7)
                status, packet = self._get(connection, "/v1/storage/maintenance/packet")
                self.assertEqual(status, 200)
                self.assertEqual(packet["plan_address"], maintenance["plan"]["content_address"])
                status, observability = self._get(
                    connection, "/v1/storage/maintenance/observability"
                )
                self.assertEqual(status, 200)
                self.assertEqual(
                    observability["plan_address"], maintenance["plan"]["content_address"]
                )
                status, event_page = self._get(
                    connection,
                    "/v1/storage/maintenance/observability?event_type=action-routed&limit=1",
                )
                self.assertEqual(status, 200)
                self.assertEqual(len(event_page["events"]), 1)
                status, review = self._get(connection, "/v1/storage/maintenance/review?limit=1")
                self.assertEqual(status, 200)
                self.assertEqual(
                    review["queue"]["plan_address"], maintenance["plan"]["content_address"]
                )
                status, review_schema = self._get(
                    connection, "/v1/storage/maintenance/review/schema"
                )
                self.assertEqual(status, 200)
                self.assertTrue(review_schema["review_only"])
                connection.request("GET", "/v1/storage/maintenance/observability/events.csv")
                csv_response = connection.getresponse()
                self.assertEqual(csv_response.status, 200)
                self.assertIn("event_id", csv_response.read().decode("utf-8").splitlines()[0])
                connection.request("GET", "/v1/storage/maintenance/observability/metrics.csv")
                metrics_response = connection.getresponse()
                self.assertEqual(metrics_response.status, 200)
                self.assertIn(
                    "metric_name", metrics_response.read().decode("utf-8").splitlines()[0]
                )
                status, verified = self._post(
                    connection,
                    "/v1/storage/maintenance/verify",
                    {"plan": maintenance["plan"]},
                )
                self.assertEqual(status, 200)
                self.assertEqual(
                    verified["content_address"], maintenance["plan"]["content_address"]
                )
                status, queried = self._post(
                    connection,
                    "/v1/storage/maintenance/query",
                    {"plan": maintenance["plan"], "query": {"kind": "no-action", "limit": 1}},
                )
                self.assertEqual(status, 200)
                self.assertEqual(queried["total"], 1)
                status, diff = self._post(
                    connection,
                    "/v1/storage/maintenance/diff",
                    {"baseline": maintenance["plan"], "candidate": maintenance["plan"]},
                )
                self.assertEqual(status, 200)
                self.assertFalse(diff["state_changed"])
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
