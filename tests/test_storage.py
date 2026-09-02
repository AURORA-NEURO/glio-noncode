from __future__ import annotations

import json
import multiprocessing
import tempfile
import threading
import unittest
from pathlib import Path
from queue import Empty
from typing import Any
from unittest.mock import patch

from glio_noncode.errors import StoreError
from glio_noncode.storage import MAX_RUN_HISTORY_ENTRIES, ObjectStore, RunStore


def _address(index: int) -> str:
    return f"sha256:{index:064x}"


def _process_run_write(
    root: str,
    index: int,
    barrier: Any,
    results: Any,
) -> None:
    try:
        barrier.wait(timeout=20)
        RunStore(root).save_run(
            "run-process-concurrent",
            input_address=_address(1),
            event_address=_address(100 + index),
            dossier_address=_address(1_000 + index),
        )
        results.put(("ok", index))
    except BaseException as exc:  # pragma: no cover - parent asserts serialized failure
        results.put(("error", index, repr(exc)))


def _process_object_write(
    root: str,
    index: int,
    barrier: Any,
    results: Any,
    fixed_winner: int | None = None,
) -> None:
    value = {"winner": index % 2 if fixed_winner is None else fixed_winner}
    try:
        barrier.wait(timeout=20)
        ObjectStore(root).put_at(_address(999), value)
        results.put(("ok", index, value))
    except BaseException as exc:  # pragma: no cover - parent asserts serialized result
        results.put(("error", index, repr(exc)))


def _process_blocking_run_read(
    root: str,
    ready: Any,
    release: Any,
    results: Any,
) -> None:
    original_read_bytes = Path.read_bytes

    def blocked_read(path: Path) -> bytes:
        if path.name != "run-reader-writer.json":
            return original_read_bytes(path)
        with path.open("rb") as handle:
            ready.set()
            if not release.wait(timeout=20):
                raise TimeoutError("test reader was not released")
            return handle.read()

    try:
        with patch.object(Path, "read_bytes", blocked_read):
            record = RunStore(root).get_run("run-reader-writer")
        results.put(("ok", record["event_address"]))
    except BaseException as exc:  # pragma: no cover - parent asserts serialized result
        results.put(("error", repr(exc)))


class StorageBoundaryTests(unittest.TestCase):
    def _process_results(self, processes: tuple[Any, ...], results: Any) -> list[Any]:
        for process in processes:
            process.start()
        for process in processes:
            process.join(timeout=30)
        try:
            self.assertFalse(
                [process.pid for process in processes if process.is_alive()],
                "storage writer process did not terminate",
            )
            self.assertTrue(all(process.exitcode == 0 for process in processes))
            output = []
            for _ in processes:
                try:
                    output.append(results.get(timeout=5))
                except Empty as exc:  # pragma: no cover - assertion exposes process state
                    self.fail(f"storage writer did not report a result: {exc}")
            return output
        finally:
            for process in processes:
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=5)

    def test_immutable_object_address_rejects_different_existing_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ObjectStore(directory)
            address = store.put({"value": "first"})
            self.assertEqual(store.put_at(address, {"value": "first"}), address)
            digest = address.split(":", 1)[1]
            stored_path = Path(directory) / "objects" / f"{digest}.json"
            stored_path.write_text('{\n  "value": "first"\n}', encoding="utf-8")
            self.assertEqual(store.put_at(address, {"value": "first"}), address)
            with self.assertRaisesRegex(StoreError, "immutable address"):
                store.put_at(address, {"value": "second"})
            self.assertEqual(store.get(address), {"value": "first"})
            self.assertFalse(store.exists("sha256:" + "../" * 21 + "x"))
            self.assertFalse(store.exists("sha256:" + "g" * 64))

    def test_run_id_grammar_prevents_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = RunStore(root / "runtime")
            invalid = (
                "../escape",
                "run-../escape",
                "run-nested/path",
                "run-nested\\path",
                "not-a-run",
                "run-",
                "run-" + "a" * 125,
            )
            for run_id in invalid:
                with self.subTest(run_id=run_id):
                    with self.assertRaisesRegex(StoreError, "invalid run_id"):
                        store.save_run(
                            run_id,
                            input_address=_address(1),
                            event_address=_address(2),
                            dossier_address=_address(3),
                        )
                    with self.assertRaisesRegex(StoreError, "invalid run_id"):
                        store.get_run(run_id)
            self.assertFalse((root / "escape.json").exists())

    def test_concurrent_run_updates_retain_every_snapshot_across_instances(self) -> None:
        writer_count = 16
        with tempfile.TemporaryDirectory() as directory:
            stores = tuple(RunStore(directory) for _ in range(writer_count))
            self.assertTrue(all(store._lock is stores[0]._lock for store in stores))
            barrier = threading.Barrier(writer_count)
            failures: list[BaseException] = []

            def write(index: int) -> None:
                try:
                    barrier.wait(timeout=10)
                    stores[index].save_run(
                        "run-concurrent",
                        input_address=_address(1),
                        event_address=_address(100 + index),
                        dossier_address=_address(1_000 + index),
                    )
                except BaseException as exc:  # pragma: no cover - assertion reports details
                    failures.append(exc)

            threads = tuple(
                threading.Thread(target=write, args=(index,)) for index in range(writer_count)
            )
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=15)

            self.assertFalse(failures, failures)
            self.assertFalse(any(thread.is_alive() for thread in threads))
            record = stores[0].get_run("run-concurrent")
            self.assertEqual(
                set(record["event_history"]),
                {_address(100 + index) for index in range(writer_count)},
            )
            self.assertEqual(
                set(record["dossier_history"]),
                {_address(1_000 + index) for index in range(writer_count)},
            )
            self.assertFalse(tuple((Path(directory) / "runs").glob("*.tmp")))

    def test_unrelated_object_and_run_writes_do_not_share_process_locks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            from glio_noncode import storage as storage_module

            object_store = ObjectStore(directory)
            run_store = RunStore(directory)
            original_atomic_write = storage_module._atomic_write_text

            for first_name, first_write, second_write in (
                (
                    f"{_address(700).split(':', 1)[1]}.json",
                    lambda: object_store.put_at(_address(700), {"value": "first"}),
                    lambda: object_store.put_at(_address(701), {"value": "second"}),
                ),
                (
                    "run-independent-a.json",
                    lambda: run_store.save_run(
                        "run-independent-a",
                        input_address=_address(1),
                        event_address=_address(2),
                        dossier_address=_address(3),
                    ),
                    lambda: run_store.save_run(
                        "run-independent-b",
                        input_address=_address(4),
                        event_address=_address(5),
                        dossier_address=_address(6),
                    ),
                ),
            ):
                with self.subTest(first_name=first_name):
                    first_entered = threading.Event()
                    release_first = threading.Event()
                    second_finished = threading.Event()
                    failures: list[BaseException] = []

                    def controlled_write(
                        path: Path,
                        text: str,
                        *,
                        target_name: str = first_name,
                        entered: threading.Event = first_entered,
                        release: threading.Event = release_first,
                    ) -> None:
                        if path.name == target_name:
                            entered.set()
                            if not release.wait(timeout=10):
                                raise TimeoutError("first independent writer was not released")
                        original_atomic_write(path, text)

                    def run_first(
                        operation: Any = first_write,
                        errors: list[BaseException] = failures,
                    ) -> None:
                        try:
                            operation()
                        except BaseException as exc:  # pragma: no cover - asserted below
                            errors.append(exc)

                    def run_second(
                        operation: Any = second_write,
                        errors: list[BaseException] = failures,
                        finished: threading.Event = second_finished,
                    ) -> None:
                        try:
                            operation()
                        except BaseException as exc:  # pragma: no cover - asserted below
                            errors.append(exc)
                        finally:
                            finished.set()

                    with patch("glio_noncode.storage._atomic_write_text", controlled_write):
                        first = threading.Thread(target=run_first)
                        second = threading.Thread(target=run_second)
                        first.start()
                        self.assertTrue(first_entered.wait(timeout=5))
                        second.start()
                        self.assertTrue(second_finished.wait(timeout=5))
                        release_first.set()
                        first.join(timeout=5)
                        second.join(timeout=5)
                    self.assertFalse(first.is_alive())
                    self.assertFalse(second.is_alive())
                    self.assertFalse(failures, failures)

    def test_cross_process_run_updates_retain_every_snapshot(self) -> None:
        writer_count = 8
        context = multiprocessing.get_context("spawn")
        with tempfile.TemporaryDirectory() as directory:
            barrier = context.Barrier(writer_count)
            results = context.Queue()
            processes = tuple(
                context.Process(
                    target=_process_run_write,
                    args=(directory, index, barrier, results),
                )
                for index in range(writer_count)
            )
            output = self._process_results(processes, results)
            self.assertTrue(all(item[0] == "ok" for item in output), output)
            record = RunStore(directory).get_run("run-process-concurrent")
            self.assertEqual(
                set(record["event_history"]),
                {_address(100 + index) for index in range(writer_count)},
            )
            self.assertEqual(
                set(record["dossier_history"]),
                {_address(1_000 + index) for index in range(writer_count)},
            )

    def test_cross_process_immutable_object_race_has_one_canonical_winner(self) -> None:
        writer_count = 8
        context = multiprocessing.get_context("spawn")
        with tempfile.TemporaryDirectory() as directory:
            barrier = context.Barrier(writer_count)
            results = context.Queue()
            processes = tuple(
                context.Process(
                    target=_process_object_write,
                    args=(directory, index, barrier, results),
                )
                for index in range(writer_count)
            )
            output = self._process_results(processes, results)
            successes = [item for item in output if item[0] == "ok"]
            failures = [item for item in output if item[0] == "error"]
            self.assertTrue(successes, output)
            self.assertTrue(failures, output)
            stored = ObjectStore(directory).get(_address(999))
            self.assertIn(stored, ({"winner": 0}, {"winner": 1}))
            self.assertTrue(all(item[2] == stored for item in successes), output)
            self.assertTrue(
                all("immutable address" in item[2] for item in failures),
                output,
            )

    def test_cross_process_identical_object_writes_are_idempotent(self) -> None:
        writer_count = 4
        context = multiprocessing.get_context("spawn")
        with tempfile.TemporaryDirectory() as directory:
            barrier = context.Barrier(writer_count)
            results = context.Queue()
            processes = tuple(
                context.Process(
                    target=_process_object_write,
                    args=(directory, index, barrier, results, 7),
                )
                for index in range(writer_count)
            )
            output = self._process_results(processes, results)
            self.assertTrue(all(item[0] == "ok" for item in output), output)
            self.assertEqual(ObjectStore(directory).get(_address(999)), {"winner": 7})

    def test_cross_process_run_reader_holds_lock_until_file_handle_closes(self) -> None:
        context = multiprocessing.get_context("spawn")
        with tempfile.TemporaryDirectory() as directory:
            store = RunStore(directory)
            store.save_run(
                "run-reader-writer",
                input_address=_address(1),
                event_address=_address(10),
                dossier_address=_address(20),
            )
            reader_open = context.Event()
            release_reader = context.Event()
            reader_results = context.Queue()
            writer_contended = threading.Event()
            write_started = threading.Event()
            failures: list[BaseException] = []

            from glio_noncode import storage as storage_module

            original_atomic_write = storage_module._atomic_write_text
            original_try_lock = storage_module._try_filesystem_lock

            def observed_write(path: Path, text: str) -> None:
                write_started.set()
                original_atomic_write(path, text)

            def observed_try_lock(handle: Any) -> bool:
                acquired = original_try_lock(handle)
                if not acquired:
                    writer_contended.set()
                return acquired

            def write() -> None:
                try:
                    store.save_run(
                        "run-reader-writer",
                        input_address=_address(1),
                        event_address=_address(11),
                        dossier_address=_address(21),
                    )
                except BaseException as exc:  # pragma: no cover - asserted below
                    failures.append(exc)

            reader = context.Process(
                target=_process_blocking_run_read,
                args=(directory, reader_open, release_reader, reader_results),
            )
            with (
                patch("glio_noncode.storage._atomic_write_text", observed_write),
                patch("glio_noncode.storage._try_filesystem_lock", observed_try_lock),
            ):
                writer = threading.Thread(target=write)
                reader.start()
                self.assertTrue(reader_open.wait(timeout=5))
                writer.start()
                self.assertTrue(writer_contended.wait(timeout=5))
                self.assertFalse(write_started.is_set())
                release_reader.set()
                reader.join(timeout=10)
                writer.join(timeout=5)

            self.assertFalse(reader.is_alive())
            self.assertEqual(reader.exitcode, 0)
            self.assertFalse(writer.is_alive())
            self.assertFalse(failures)
            self.assertTrue(write_started.is_set())
            self.assertEqual(reader_results.get(timeout=5), ("ok", _address(10)))
            record = store.get_run("run-reader-writer")
            self.assertEqual(record["event_address"], _address(11))
            self.assertEqual(record["dossier_address"], _address(21))

    def test_run_identity_and_history_growth_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = RunStore(directory)
            store.save_run(
                "run-bounded",
                input_address=_address(1),
                event_address=_address(10),
                dossier_address=_address(20),
            )
            with self.assertRaisesRegex(StoreError, "input_address is immutable"):
                store.save_run(
                    "run-bounded",
                    input_address=_address(2),
                    event_address=_address(11),
                    dossier_address=_address(21),
                )

            with patch("glio_noncode.storage.MAX_RUN_HISTORY_ENTRIES", 2):
                store.save_run(
                    "run-bounded",
                    input_address=_address(1),
                    event_address=_address(11),
                    dossier_address=_address(21),
                )
                with self.assertRaisesRegex(StoreError, "exceeds 2 entries"):
                    store.save_run(
                        "run-bounded",
                        input_address=_address(1),
                        event_address=_address(12),
                        dossier_address=_address(22),
                    )
            self.assertEqual(MAX_RUN_HISTORY_ENTRIES, 1_000)

    def test_get_run_rejects_non_object_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = RunStore(directory)
            path = Path(directory) / "runs" / "run-invalid.json"
            path.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(StoreError, "must be an object"):
                store.get_run("run-invalid")

    def test_run_reads_validate_exact_links_and_upgrade_legacy_histories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = RunStore(directory)
            store.save_run(
                "run-strict",
                input_address=_address(1),
                event_address=_address(2),
                dossier_address=_address(3),
            )
            path = Path(directory) / "runs" / "run-strict.json"
            valid = json.loads(path.read_text(encoding="utf-8"))
            mutations = {
                "unknown field": lambda value: value.__setitem__("unexpected", True),
                "wrong run": lambda value: value.__setitem__("run_id", "run-foreign"),
                "bad input": lambda value: value.__setitem__("input_address", "sha256:bad"),
                "missing current event": lambda value: value.__setitem__(
                    "event_history", [_address(9)]
                ),
                "duplicate dossier history": lambda value: value.__setitem__(
                    "dossier_history", [_address(3), _address(3)]
                ),
            }
            for label, mutate in mutations.items():
                with self.subTest(label=label):
                    malformed = json.loads(json.dumps(valid))
                    mutate(malformed)
                    path.write_text(json.dumps(malformed), encoding="utf-8")
                    with self.assertRaises(StoreError):
                        store.get_run("run-strict")
            path.write_text(json.dumps(valid), encoding="utf-8")
            self.assertEqual(store.get_run("run-strict"), valid)

            legacy_path = Path(directory) / "runs" / "run-legacy.json"
            legacy_path.write_text(
                json.dumps(
                    {
                        "run_id": "run-legacy",
                        "input_address": _address(10),
                        "event_address": _address(11),
                        "dossier_address": _address(12),
                    }
                ),
                encoding="utf-8",
            )
            reopened = store.get_run("run-legacy")
            self.assertEqual(reopened["event_history"], [_address(11)])
            self.assertEqual(reopened["dossier_history"], [_address(12)])

            dossier_history_path = Path(directory) / "runs" / "run-dossier-legacy.json"
            dossier_history_path.write_text(
                json.dumps(
                    {
                        "run_id": "run-dossier-legacy",
                        "input_address": _address(20),
                        "event_address": _address(21),
                        "dossier_address": _address(23),
                        "dossier_history": [_address(22), _address(23)],
                    }
                ),
                encoding="utf-8",
            )
            dossier_history_legacy = store.get_run("run-dossier-legacy")
            self.assertEqual(dossier_history_legacy["event_history"], [_address(21)])
            self.assertEqual(
                dossier_history_legacy["dossier_history"],
                [_address(22), _address(23)],
            )
            store.save_run(
                "run-dossier-legacy",
                input_address=_address(20),
                event_address=_address(24),
                dossier_address=_address(25),
            )
            upgraded_dossier_history = store.get_run("run-dossier-legacy")
            self.assertEqual(
                upgraded_dossier_history["event_history"],
                [_address(21), _address(24)],
            )
            self.assertEqual(
                upgraded_dossier_history["dossier_history"],
                [_address(22), _address(23), _address(25)],
            )

            store.save_run(
                "run-legacy",
                input_address=_address(10),
                event_address=_address(13),
                dossier_address=_address(14),
            )
            upgraded = store.get_run("run-legacy")
            self.assertEqual(upgraded["event_history"], [_address(11), _address(13)])
            self.assertEqual(upgraded["dossier_history"], [_address(12), _address(14)])


if __name__ == "__main__":
    unittest.main()
