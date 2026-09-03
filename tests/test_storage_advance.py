from __future__ import annotations

import json
import multiprocessing
import tempfile
import threading
import unittest
from pathlib import Path
from queue import Empty, Queue
from typing import Any
from unittest.mock import patch

from glio_noncode.errors import StoreError
from glio_noncode.storage import ObjectStore, RunStore


def _address(index: int) -> str:
    return f"sha256:{index:064x}"


def _run_record(
    run_id: str,
    *,
    input_index: int = 1,
    event_index: int = 10,
    dossier_index: int = 20,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "input_address": _address(input_index),
        "event_address": _address(event_index),
        "event_history": [_address(event_index)],
        "dossier_address": _address(dossier_index),
        "dossier_history": [_address(dossier_index)],
    }


def _process_advance(
    root: str,
    index: int,
    barrier: Any,
    results: Any,
) -> None:
    try:
        store = RunStore(root)
        expected_run = store.get_run("run-process-cas")
        barrier.wait(timeout=20)
        store.advance_run(
            "run-process-cas",
            expected_run=expected_run,
            event_address=_address(100 + index),
            dossier_address=_address(1_000 + index),
        )
        results.put(("ok", index))
    except BaseException as exc:  # pragma: no cover - parent asserts serialized result
        results.put(("error", index, type(exc).__name__, str(exc)))


class _StringSubclass(str):
    pass


class RunStoreAdvanceTests(unittest.TestCase):
    def test_verified_object_reads_are_bounded_canonical_and_address_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ObjectStore(directory)
            value = {"items": [1, 2, 3], "kind": "verified"}
            address = store.put(value)
            path = Path(directory) / "objects" / f"{address.removeprefix('sha256:')}.json"
            canonical = path.read_bytes()

            self.assertEqual(store.get_verified(address, max_bytes=len(canonical)), value)
            with self.assertRaisesRegex(StoreError, "positive integer"):
                store.get_verified(address, max_bytes=True)

            path.write_bytes(canonical + b" ")
            with self.assertRaisesRegex(StoreError, "exceeds"):
                store.get_verified(address, max_bytes=len(canonical))
            with self.assertRaisesRegex(StoreError, "not canonical JSON"):
                store.get_verified(address, max_bytes=len(canonical) + 1)

            path.write_bytes(b'{"items":[1,2,4],"kind":"verified"}')
            with self.assertRaisesRegex(StoreError, "does not match its content address"):
                store.get_verified(address, max_bytes=1_024)

            domain_address = _address(501)
            store.put_at(domain_address, value)
            self.assertEqual(store.get_canonical(domain_address, max_bytes=1_024), value)
            with self.assertRaisesRegex(StoreError, "does not match its content address"):
                store.get_verified(domain_address, max_bytes=1_024)

    def test_object_store_rejects_ambiguous_json_without_rewriting_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ObjectStore(directory)
            address = _address(500)
            store.put_at(address, {"value": "original"})
            path = Path(directory) / "objects" / f"{address.removeprefix('sha256:')}.json"

            for malformed in (
                b'{"value":"first","value":"second"}',
                b'{"value":NaN}',
            ):
                with self.subTest(malformed=malformed):
                    path.write_bytes(malformed)
                    with self.assertRaisesRegex(StoreError, "invalid stored object"):
                        store.get(address)
                    with self.assertRaisesRegex(StoreError, "invalid stored object"):
                        store.put_at(address, {"value": "replacement"})
                    self.assertEqual(path.read_bytes(), malformed)

    def test_create_run_succeeds_once_and_preserves_declared_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = RunStore(directory)
            path = store.create_run(
                "run-create",
                input_address=_address(1),
                event_address=_address(10),
                dossier_address=_address(20),
                dossier_history=(_address(19),),
            )

            self.assertEqual(
                store.get_run("run-create"),
                {
                    "run_id": "run-create",
                    "input_address": _address(1),
                    "event_address": _address(10),
                    "event_history": [_address(10)],
                    "dossier_address": _address(20),
                    "dossier_history": [_address(19), _address(20)],
                },
            )
            self.assertEqual(path, Path(directory) / "runs" / "run-create.json")

    def test_create_run_rejects_existing_index_without_rewriting_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = RunStore(directory)
            path = store.create_run(
                "run-create-existing",
                input_address=_address(1),
                event_address=_address(10),
                dossier_address=_address(20),
            )
            before = path.read_bytes()

            with self.assertRaisesRegex(StoreError, "run already exists"):
                RunStore(directory).create_run(
                    "run-create-existing",
                    input_address=_address(2),
                    event_address=_address(11),
                    dossier_address=_address(21),
                )

            self.assertEqual(path.read_bytes(), before)

            malformed = b'{"run_id":"run-create-existing",broken'
            path.write_bytes(malformed)
            with self.assertRaisesRegex(StoreError, "run already exists"):
                store.create_run(
                    "run-create-existing",
                    input_address=_address(3),
                    event_address=_address(12),
                    dossier_address=_address(22),
                )
            self.assertEqual(path.read_bytes(), malformed)

    def test_create_run_write_failure_releases_locks_for_retry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = RunStore(directory)
            path = Path(directory) / "runs" / "run-create-retry.json"

            with patch(
                "glio_noncode.storage._atomic_write_text",
                side_effect=OSError("injected write failure"),
            ):
                with self.assertRaisesRegex(OSError, "injected write failure"):
                    store.create_run(
                        "run-create-retry",
                        input_address=_address(1),
                        event_address=_address(10),
                        dossier_address=_address(20),
                    )
            self.assertFalse(path.exists())

            RunStore(directory).create_run(
                "run-create-retry",
                input_address=_address(1),
                event_address=_address(10),
                dossier_address=_address(20),
            )
            self.assertEqual(
                store.get_run("run-create-retry")["event_address"],
                _address(10),
            )

    def test_two_instances_racing_from_one_state_have_exactly_one_winner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            stores = (RunStore(directory), RunStore(directory))
            stores[0].save_run(
                "run-thread-cas",
                input_address=_address(1),
                event_address=_address(10),
                dossier_address=_address(20),
            )
            expected_run = stores[0].get_run("run-thread-cas")
            barrier = threading.Barrier(2)
            results: Queue[tuple[str, int, BaseException | None]] = Queue()

            def advance(index: int) -> None:
                try:
                    barrier.wait(timeout=10)
                    stores[index].advance_run(
                        "run-thread-cas",
                        expected_run=expected_run,
                        event_address=_address(100 + index),
                        dossier_address=_address(1_000 + index),
                    )
                    results.put(("ok", index, None))
                except BaseException as exc:  # pragma: no cover - asserted below
                    results.put(("error", index, exc))

            threads = tuple(threading.Thread(target=advance, args=(index,)) for index in range(2))
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=15)
            self.assertFalse(any(thread.is_alive() for thread in threads))

            output = [results.get(timeout=5) for _ in threads]
            winners = [item for item in output if item[0] == "ok"]
            losers = [item for item in output if item[0] == "error"]
            self.assertEqual(len(winners), 1, output)
            self.assertEqual(len(losers), 1, output)
            self.assertIsInstance(losers[0][2], StoreError)
            self.assertIn("expected current state", str(losers[0][2]))

            winner = winners[0][1]
            record = stores[0].get_run("run-thread-cas")
            self.assertEqual(record["input_address"], _address(1))
            self.assertEqual(record["event_address"], _address(100 + winner))
            self.assertEqual(record["dossier_address"], _address(1_000 + winner))
            self.assertEqual(
                record["event_history"],
                [_address(10), _address(100 + winner)],
            )
            self.assertEqual(
                record["dossier_history"],
                [_address(20), _address(1_000 + winner)],
            )
            self.assertNotIn(_address(101 - winner), record["event_history"])
            self.assertNotIn(_address(1_001 - winner), record["dossier_history"])
            self.assertFalse(tuple((Path(directory) / "runs").glob("*.tmp")))

    def test_stale_missing_and_wrong_input_advances_leave_index_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = RunStore(directory)
            missing_path = Path(directory) / "runs" / "run-missing.json"
            with self.assertRaisesRegex(StoreError, "run not found"):
                store.advance_run(
                    "run-missing",
                    expected_run={
                        "run_id": "run-missing",
                        "input_address": _address(1),
                        "event_address": _address(10),
                        "event_history": [_address(10)],
                        "dossier_address": _address(20),
                        "dossier_history": [_address(20)],
                    },
                    event_address=_address(11),
                    dossier_address=_address(21),
                )
            self.assertFalse(missing_path.exists())

            path = store.save_run(
                "run-stale",
                input_address=_address(1),
                event_address=_address(10),
                dossier_address=_address(20),
            )
            before = path.read_bytes()
            current = store.get_run("run-stale")
            stale_pairs = (
                (_address(9), _address(20)),
                (_address(10), _address(19)),
                (_address(9), _address(19)),
            )
            for expected_event, expected_dossier in stale_pairs:
                with self.subTest(
                    expected_event=expected_event,
                    expected_dossier=expected_dossier,
                ):
                    stale = dict(current)
                    stale["event_address"] = expected_event
                    stale["event_history"] = [expected_event]
                    stale["dossier_address"] = expected_dossier
                    stale["dossier_history"] = [expected_dossier]
                    with self.assertRaisesRegex(StoreError, "expected current state"):
                        store.advance_run(
                            "run-stale",
                            expected_run=stale,
                            event_address=_address(11),
                            dossier_address=_address(21),
                        )
                    self.assertEqual(path.read_bytes(), before)

            wrong_input = dict(current)
            wrong_input["input_address"] = _address(2)
            with self.assertRaisesRegex(StoreError, "expected current state"):
                store.advance_run(
                    "run-stale",
                    expected_run=wrong_input,
                    event_address=_address(11),
                    dossier_address=_address(21),
                )
            self.assertEqual(path.read_bytes(), before)

    def test_complete_snapshot_rejects_aba_after_legacy_pointer_rewind(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = RunStore(directory)
            path = store.create_run(
                "run-aba",
                input_address=_address(1),
                event_address=_address(10),
                dossier_address=_address(20),
            )
            original = store.get_run("run-aba")
            store.advance_run(
                "run-aba",
                expected_run=original,
                event_address=_address(11),
                dossier_address=_address(21),
            )
            store.save_run(
                "run-aba",
                input_address=_address(1),
                event_address=_address(10),
                dossier_address=_address(20),
            )
            rewound = store.get_run("run-aba")
            self.assertEqual(rewound["event_address"], original["event_address"])
            self.assertEqual(rewound["dossier_address"], original["dossier_address"])
            self.assertNotEqual(rewound, original)
            before = path.read_bytes()

            with self.assertRaisesRegex(StoreError, "expected current state"):
                store.advance_run(
                    "run-aba",
                    expected_run=original,
                    event_address=_address(12),
                    dossier_address=_address(22),
                )
            self.assertEqual(path.read_bytes(), before)

    def test_advance_requires_exact_scalar_and_history_types(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = RunStore(directory)
            path = store.save_run(
                "run-exact-types",
                input_address=_address(1),
                event_address=_address(10),
                dossier_address=_address(20),
            )
            before = path.read_bytes()
            expected = store.get_run("run-exact-types")
            for field_name, value in (
                ("event_address", _address(11)),
                ("dossier_address", _address(21)),
            ):
                with self.subTest(field_name=field_name):
                    with self.assertRaises(StoreError):
                        store.advance_run(
                            "run-exact-types",
                            expected_run=expected,
                            event_address=(
                                _StringSubclass(value)
                                if field_name == "event_address"
                                else _address(11)
                            ),
                            dossier_address=(
                                _StringSubclass(value)
                                if field_name == "dossier_address"
                                else _address(21)
                            ),
                        )
                    self.assertEqual(path.read_bytes(), before)

            with self.assertRaisesRegex(StoreError, "invalid run_id"):
                store.advance_run(
                    _StringSubclass("run-exact-types"),
                    expected_run=expected,
                    event_address=_address(11),
                    dossier_address=_address(21),
                )
            with self.assertRaisesRegex(StoreError, "run record must be an object"):
                store.advance_run(
                    "run-exact-types",
                    expected_run=[],  # type: ignore[arg-type]
                    event_address=_address(11),
                    dossier_address=_address(21),
                )
            with self.assertRaisesRegex(StoreError, "dossier_history must be a tuple"):
                store.advance_run(
                    "run-exact-types",
                    expected_run=expected,
                    event_address=_address(11),
                    dossier_address=_address(21),
                    dossier_history=[_address(20)],  # type: ignore[arg-type]
                )
            self.assertEqual(path.read_bytes(), before)

    def test_advance_strictly_rejects_malformed_current_json_without_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = RunStore(directory)
            path = store.save_run(
                "run-duplicate-json",
                input_address=_address(1),
                event_address=_address(10),
                dossier_address=_address(20),
            )
            expected = store.get_run("run-duplicate-json")
            duplicated = path.read_text(encoding="utf-8").replace(
                '"run_id":',
                '"run_id":"run-duplicate-json","run_id":',
                1,
            )
            path.write_text(duplicated, encoding="utf-8")
            before = path.read_bytes()

            with self.assertRaisesRegex(StoreError, "invalid run record"):
                store.advance_run(
                    "run-duplicate-json",
                    expected_run=expected,
                    event_address=_address(11),
                    dossier_address=_address(21),
                )
            self.assertEqual(path.read_bytes(), before)

    def test_oversized_run_record_is_bounded_and_never_rewritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = RunStore(directory)
            path = Path(directory) / "runs" / "run-oversized.json"
            oversized = b"{" + (b" " * (1 << 20)) + b"}"
            path.write_bytes(oversized)

            with self.assertRaisesRegex(StoreError, "run record exceeds"):
                store.get_run("run-oversized")
            with self.assertRaisesRegex(StoreError, "run record exceeds"):
                store.advance_run(
                    "run-oversized",
                    expected_run=_run_record("run-oversized"),
                    event_address=_address(11),
                    dossier_address=_address(21),
                )
            self.assertEqual(path.read_bytes(), oversized)

    def test_advance_upgrades_legacy_history_and_enforces_history_bound_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = RunStore(directory)
            path = Path(directory) / "runs" / "run-legacy-cas.json"
            path.write_text(
                json.dumps(
                    {
                        "run_id": "run-legacy-cas",
                        "input_address": _address(1),
                        "event_address": _address(10),
                        "dossier_address": _address(20),
                    }
                ),
                encoding="utf-8",
            )
            with patch("glio_noncode.storage.MAX_RUN_HISTORY_ENTRIES", 2):
                expected = store.get_run("run-legacy-cas")
                store.advance_run(
                    "run-legacy-cas",
                    expected_run=expected,
                    event_address=_address(11),
                    dossier_address=_address(21),
                )
                current = store.get_run("run-legacy-cas")
                self.assertEqual(current["event_history"], [_address(10), _address(11)])
                self.assertEqual(current["dossier_history"], [_address(20), _address(21)])
                before = path.read_bytes()
                with self.assertRaisesRegex(StoreError, "exceeds 2 entries"):
                    store.advance_run(
                        "run-legacy-cas",
                        expected_run=current,
                        event_address=_address(12),
                        dossier_address=_address(22),
                    )
                self.assertEqual(path.read_bytes(), before)

    def test_cross_process_compare_and_swap_has_one_winner(self) -> None:
        context = multiprocessing.get_context("spawn")
        with tempfile.TemporaryDirectory() as directory:
            RunStore(directory).save_run(
                "run-process-cas",
                input_address=_address(1),
                event_address=_address(10),
                dossier_address=_address(20),
            )
            barrier = context.Barrier(2)
            results = context.Queue()
            processes = tuple(
                context.Process(
                    target=_process_advance,
                    args=(directory, index, barrier, results),
                )
                for index in range(2)
            )
            for process in processes:
                process.start()
            for process in processes:
                process.join(timeout=30)
            try:
                self.assertFalse(
                    [process.pid for process in processes if process.is_alive()],
                    "storage CAS process did not terminate",
                )
                self.assertTrue(all(process.exitcode == 0 for process in processes))
                output = []
                for _ in processes:
                    try:
                        output.append(results.get(timeout=5))
                    except Empty as exc:  # pragma: no cover - assertion exposes state
                        self.fail(f"storage CAS process did not report a result: {exc}")
            finally:
                for process in processes:
                    if process.is_alive():
                        process.terminate()
                        process.join(timeout=5)

            winners = [item for item in output if item[0] == "ok"]
            losers = [item for item in output if item[0] == "error"]
            self.assertEqual(len(winners), 1, output)
            self.assertEqual(len(losers), 1, output)
            self.assertEqual(losers[0][2], "StoreError")
            self.assertIn("expected current state", losers[0][3])
            winner = winners[0][1]
            record = RunStore(directory).get_run("run-process-cas")
            self.assertEqual(record["event_address"], _address(100 + winner))
            self.assertEqual(record["dossier_address"], _address(1_000 + winner))
            self.assertEqual(
                record["event_history"],
                [_address(10), _address(100 + winner)],
            )
            self.assertEqual(
                record["dossier_history"],
                [_address(20), _address(1_000 + winner)],
            )


if __name__ == "__main__":
    unittest.main()
