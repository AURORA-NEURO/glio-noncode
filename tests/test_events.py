from __future__ import annotations

import copy
import math
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import glio_noncode.events as events_module
from glio_noncode.errors import ValidationError
from glio_noncode.events import (
    MAX_EVENT_IDENTIFIER_LENGTH,
    EventLog,
    RuntimeEvent,
)
from glio_noncode.models import ReviewDecision, ReviewState
from glio_noncode.replay import ReplayVerifier
from glio_noncode.runtime import CaseRuntime
from glio_noncode.serialization import canonical_bytes, canonical_json, content_hash

from .helpers import fixture_manifest


def _two_event_log(run_id: str = "run-events-v1") -> EventLog:
    log = EventLog(run_id)
    log.append("case_received", {"case_id": "case-1"}, event_id="event-1")
    log.append(
        "dossier_created",
        {"dossier_id": "dossier-1", "counts": [1, 2]},
        event_id="event-2",
    )
    return log


def _reseal(raw_event: dict[str, object]) -> None:
    body = {key: value for key, value in raw_event.items() if key != "event_hash"}
    raw_event["event_hash"] = content_hash(body)


class RuntimeEventTests(unittest.TestCase):
    def test_payload_is_copied_recursively_and_exports_are_detached(self) -> None:
        source = {"rows": [{"score": 1.0}], "labels": ["a", "b"]}
        log = EventLog("run-immutable")
        event = log.append("evaluated", source, event_id="event-immutable")
        original = event.to_dict()

        source["rows"][0]["score"] = 0.0
        source["labels"].append("mutated")
        self.assertEqual(event.to_dict(), original)
        self.assertTrue(log.verify())

        with self.assertRaises(TypeError):
            event.payload["extra"] = True  # type: ignore[index]
        with self.assertRaises(TypeError):
            event.payload["rows"][0]["score"] = 0.0  # type: ignore[index]

        exported = log.to_record()
        exported["events"][0]["payload"]["rows"][0]["score"] = -1.0
        self.assertEqual(log.to_record()["events"][0], original)
        self.assertTrue(log.verify())

    def test_valid_generated_v1_round_trip_preserves_identity_and_continues_chain(self) -> None:
        original = _two_event_log()
        raw = original.to_record()
        address = content_hash(raw)

        hydrated = EventLog.from_record(raw, expected_address=address)

        self.assertEqual(hydrated.to_record(), raw)
        self.assertEqual(hydrated.record_address, address)
        self.assertEqual(hydrated.head, original.head)
        self.assertTrue(hydrated.verify())
        continuation = hydrated.append("review_recorded", {}, event_id="event-3")
        self.assertEqual(continuation.previous_hash, original.head)
        self.assertTrue(hydrated.verify())
        self.assertEqual(
            frozenset(raw),
            frozenset({"run_id", "events"}),
        )
        self.assertEqual(
            frozenset(raw["events"][0]),
            frozenset(
                {
                    "event_id",
                    "run_id",
                    "event_type",
                    "payload",
                    "created_at",
                    "previous_hash",
                    "event_hash",
                }
            ),
        )

    def test_empty_generated_v1_record_remains_valid_and_addressable(self) -> None:
        log = EventLog("empty-run")
        record = log.to_record()

        hydrated = EventLog.from_record(record, expected_address=log.record_address)

        self.assertEqual(hydrated.to_record(), record)
        self.assertEqual(hydrated.head, "genesis")
        self.assertTrue(hydrated.verify())

    def test_runtime_event_requires_canonical_payload_and_aware_timestamp(self) -> None:
        valid = {
            "event_id": "event-1",
            "run_id": "run-1",
            "event_type": "created",
            "payload": {},
            "created_at": "2026-09-02T12:00:00+00:00",
            "previous_hash": None,
            "event_hash": "sha256:" + "0" * 64,
        }
        mutations = {
            "missing timestamp": lambda row: row.pop("created_at"),
            "invented naive timestamp": lambda row: row.__setitem__(
                "created_at", "2026-09-02T12:00:00"
            ),
            "non-UTC timestamp": lambda row: row.__setitem__(
                "created_at", "2026-09-02T07:00:00-05:00"
            ),
            "Z timestamp spelling": lambda row: row.__setitem__(
                "created_at", "2026-09-02T12:00:00Z"
            ),
            "space timestamp separator": lambda row: row.__setitem__(
                "created_at", "2026-09-02 12:00:00+00:00"
            ),
            "noncanonical fractional timestamp": lambda row: row.__setitem__(
                "created_at", "2026-09-02T12:00:00.000000+00:00"
            ),
            "non-string timestamp": lambda row: row.__setitem__("created_at", 1),
            "array payload": lambda row: row.__setitem__("payload", []),
            "non-string payload key": lambda row: row.__setitem__("payload", {1: "value"}),
            "non-finite payload": lambda row: row.__setitem__("payload", {"value": math.nan}),
            "python-only payload": lambda row: row.__setitem__("payload", {"value": {1, 2}}),
            "non-string event ID": lambda row: row.__setitem__("event_id", 1),
            "blank run ID": lambda row: row.__setitem__("run_id", "  "),
            "non-string event type": lambda row: row.__setitem__("event_type", True),
            "malformed previous hash": lambda row: row.__setitem__("previous_hash", "sha256:x"),
            "non-string event hash": lambda row: row.__setitem__("event_hash", False),
            "unknown signed field": lambda row: row.__setitem__("sequence", 1),
            "non-string signed field name": lambda row: row.__setitem__(1, "unknown"),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                candidate = copy.deepcopy(valid)
                mutate(candidate)
                with self.assertRaises(ValueError):
                    RuntimeEvent.from_dict(candidate)

    def test_identifier_and_payload_byte_limits_apply_before_append(self) -> None:
        log = EventLog("run-bounds")
        with self.assertRaisesRegex(ValueError, "maximum length"):
            log.append(
                "created",
                {},
                event_id="x" * (MAX_EVENT_IDENTIFIER_LENGTH + 1),
            )
        payload_size = len(canonical_bytes({"value": "bounded"}))
        with (
            patch.object(events_module, "MAX_EVENT_PAYLOAD_BYTES", payload_size - 1),
            self.assertRaisesRegex(ValueError, "maximum canonical size"),
        ):
            log.append("created", {"value": "bounded"}, event_id="event-too-large")
        self.assertEqual(log.all(), ())
        self.assertEqual(log.head, "genesis")


class EventLogHydrationTests(unittest.TestCase):
    def test_record_and_entry_shapes_are_exact_and_types_are_not_coerced(self) -> None:
        valid = _two_event_log().to_record()
        mutations = {
            "missing run ID": lambda row: row.pop("run_id"),
            "unknown record field": lambda row: row.__setitem__("accepted", True),
            "non-string record field name": lambda row: row.__setitem__(1, "unknown"),
            "integer run ID": lambda row: row.__setitem__("run_id", 7),
            "blank run ID": lambda row: row.__setitem__("run_id", ""),
            "missing events": lambda row: row.pop("events"),
            "tuple events": lambda row: row.__setitem__("events", tuple(row["events"])),
            "object events": lambda row: row.__setitem__("events", {}),
            "non-object entry": lambda row: row["events"].__setitem__(0, []),
            "missing event field": lambda row: row["events"][0].pop("payload"),
            "unknown event field": lambda row: row["events"][0].__setitem__("extra", None),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                candidate = copy.deepcopy(valid)
                mutate(candidate)
                with self.assertRaises(ValueError):
                    EventLog.from_record(candidate)
        for value in (None, [], "record"):
            with self.subTest(top_level=type(value).__name__):
                with self.assertRaises(ValueError):
                    EventLog.from_record(value)  # type: ignore[arg-type]

    def test_hydration_rejects_hash_link_run_and_duplicate_identity_failures(self) -> None:
        valid = _two_event_log().to_record()

        tampered_payload = copy.deepcopy(valid)
        tampered_payload["events"][0]["payload"]["case_id"] = "tampered"
        with self.assertRaisesRegex(ValueError, "hash"):
            EventLog.from_record(tampered_payload)

        wrong_hash = copy.deepcopy(valid)
        wrong_hash["events"][0]["event_hash"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(ValueError, "hash"):
            RuntimeEvent.from_dict(wrong_hash["events"][0])
        with self.assertRaisesRegex(ValueError, "hash"):
            EventLog.from_record(wrong_hash)

        broken_link = copy.deepcopy(valid)
        broken_link["events"][1]["previous_hash"] = "sha256:" + "0" * 64
        _reseal(broken_link["events"][1])
        with self.assertRaisesRegex(ValueError, "previous_hash"):
            EventLog.from_record(broken_link)

        foreign_run = copy.deepcopy(valid)
        foreign_run["events"][0]["run_id"] = "other-run"
        _reseal(foreign_run["events"][0])
        with self.assertRaisesRegex(ValueError, "run_id"):
            EventLog.from_record(foreign_run)

        first = RuntimeEvent.from_dict(valid["events"][0])
        duplicate = RuntimeEvent(
            event_id=first.event_id,
            run_id=first.run_id,
            event_type="duplicate",
            payload={},
            created_at="2026-09-02T12:00:00+00:00",
            previous_hash=first.event_hash,
        ).seal()
        duplicate_record = {
            "run_id": first.run_id,
            "events": [first.to_dict(), duplicate.to_dict()],
        }
        with self.assertRaisesRegex(ValueError, "duplicate event_id"):
            EventLog.from_record(duplicate_record)

    def test_expected_outer_content_address_is_verified(self) -> None:
        first = _two_event_log()
        second = EventLog(first.run_id)
        second.append("different", {}, event_id="different-event")

        self.assertNotEqual(first.record_address, second.record_address)
        with self.assertRaisesRegex(ValueError, "expected content address"):
            EventLog.from_record(
                second.to_record(),
                expected_address=first.record_address,
            )
        with self.assertRaisesRegex(ValueError, "canonical sha256"):
            EventLog.from_record(second.to_record(), expected_address="sha256:invalid")

    def test_replay_closes_event_record_over_persisted_run_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            run_record = runtime.get_run(dossier.run_id)
            event_record = runtime.store.store.get(run_record["event_address"])
            dossier_record = runtime.get_dossier(run_record["dossier_address"])
            verifier = ReplayVerifier()

            self.assertTrue(
                verifier.verify(run_record, event_record, dossier_record).event_chain_valid
            )
            wrong_pointer = dict(run_record)
            wrong_pointer["event_address"] = "sha256:" + "0" * 64
            report = verifier.verify(wrong_pointer, event_record, dossier_record)

            self.assertFalse(report.event_chain_valid)
            self.assertTrue(report.stored_dossier_matches_address)
            self.assertIn("event chain verification failed", report.warnings)

    def test_direct_review_rejects_valid_chain_stored_under_wrong_address(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            run_record = runtime.get_run(dossier.run_id)
            wrong_log = EventLog(dossier.run_id)
            wrong_log.append("replacement", {}, event_id="replacement-event")
            event_digest = run_record["event_address"].split(":", 1)[1]
            event_path = runtime.store.store.objects / f"{event_digest}.json"
            event_path.write_text(canonical_json(wrong_log.to_record()), encoding="utf-8")
            runtime._logs.clear()
            review = ReviewDecision(
                review_id="review-wrong-event-object",
                case_id=dossier.case_id,
                reviewer="scientific-reviewer",
                state=ReviewState.ACCEPTED,
                reviewed_hypothesis_ids=(dossier.hypotheses[0].hypothesis_id,),
                rationale="Reviewed the complete evidence record.",
                checked_claim_ids=tuple(claim.evidence_id for claim in dossier.evidence),
            )

            with self.assertRaisesRegex(ValidationError, "invalid event record"):
                runtime.review(dossier, review)

    def test_duplicate_append_is_atomic(self) -> None:
        log = EventLog("run-duplicate")
        first = log.append("created", {}, event_id="same-id")
        before = log.to_record()

        with self.assertRaisesRegex(ValueError, "already exists"):
            log.append("changed", {"changed": True}, event_id="same-id")

        self.assertEqual(log.to_record(), before)
        self.assertEqual(log.head, first.event_hash)
        self.assertTrue(log.verify())

    def test_entry_and_record_bounds_reject_without_partial_mutation(self) -> None:
        with patch.object(events_module, "MAX_EVENT_LOG_ENTRIES", 2):
            log = _two_event_log("run-entry-limit")
            before = log.to_record()
            with self.assertRaisesRegex(ValueError, "cannot exceed 2"):
                log.append("third", {}, event_id="event-3")
            self.assertEqual(log.to_record(), before)
            self.assertTrue(log.verify())

            previous = RuntimeEvent.from_dict(before["events"][-1])
            third = RuntimeEvent(
                event_id="event-3",
                run_id=log.run_id,
                event_type="third",
                payload={},
                created_at="2026-09-02T12:00:00+00:00",
                previous_hash=previous.event_hash,
            ).seal()
            oversized = copy.deepcopy(before)
            oversized["events"].append(third.to_dict())
            with self.assertRaisesRegex(ValueError, "cannot exceed 2"):
                EventLog.from_record(oversized)

        log = EventLog("run-byte-limit")
        log.append("first", {"value": "one"}, event_id="event-1")
        before = log.to_record()
        exact_size = len(canonical_bytes(before))
        with patch.object(events_module, "MAX_EVENT_RECORD_BYTES", exact_size):
            with self.assertRaisesRegex(ValueError, "maximum canonical size"):
                log.append("second", {"value": "two"}, event_id="event-2")
            self.assertEqual(log.to_record(), before)
            self.assertTrue(log.verify())

    def test_concurrent_appends_form_one_valid_serial_chain(self) -> None:
        log = EventLog("run-concurrent")

        def append(index: int) -> None:
            log.append("worker", {"index": index}, event_id=f"event-{index}")

        with ThreadPoolExecutor(max_workers=8) as pool:
            tuple(pool.map(append, range(64)))

        events = log.all()
        self.assertEqual(len(events), 64)
        self.assertEqual(len({event.event_id for event in events}), 64)
        self.assertTrue(log.verify())
        self.assertEqual(EventLog.from_record(log.to_record()).to_record(), log.to_record())


if __name__ == "__main__":
    unittest.main()
