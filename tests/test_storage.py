from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path

from glio_noncode.errors import StoreError
from glio_noncode.storage import ObjectStore, RunStore


def _address(index: int) -> str:
    return f"sha256:{index:064x}"


class StorageBoundaryTests(unittest.TestCase):
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
                threading.Thread(target=write, args=(index,))
                for index in range(writer_count)
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

    def test_get_run_rejects_non_object_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = RunStore(directory)
            path = Path(directory) / "runs" / "run-invalid.json"
            path.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(StoreError, "must be an object"):
                store.get_run("run-invalid")


if __name__ == "__main__":
    unittest.main()
