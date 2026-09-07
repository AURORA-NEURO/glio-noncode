from __future__ import annotations

import tempfile
import unittest
from unittest.mock import patch

import glio_noncode.batch_runtime as batch_module
from glio_noncode.batch_release import build_persisted_batch_release
from glio_noncode.batch_runtime import (
    MAX_BATCH_INDEX_BYTES,
    MAX_BATCH_INPUT_BYTES,
    MAX_BATCH_ITEM_INPUT_BYTES,
    MAX_BATCH_RESULT_BYTES,
    BatchRuntime,
)
from glio_noncode.errors import StoreError, ValidationError
from glio_noncode.storage import ObjectStore

from .helpers import fixture_manifest


class _OversizedCanonicalBytes:
    def __len__(self) -> int:
        return MAX_BATCH_INPUT_BYTES + 1


class BatchBoundedReadTests(unittest.TestCase):
    def test_reopen_and_release_never_use_legacy_unbounded_get(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = BatchRuntime(directory)
            result = runtime.evaluate([fixture_manifest().to_dict()])

            with patch.object(
                ObjectStore,
                "get",
                side_effect=AssertionError("legacy unbounded read used"),
            ):
                reopened = runtime.get(result.batch_id)
                release = build_persisted_batch_release(runtime.runtime, result.batch_id)

            self.assertEqual(reopened.result_address, result.result_address)
            self.assertTrue(release.accepted)

    def test_reopen_uses_separate_explicit_object_ceilings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = BatchRuntime(directory)
            result = runtime.evaluate([fixture_manifest().to_dict()])
            store = runtime.runtime.store.store

            with patch.object(store, "get_verified", wraps=store.get_verified) as verified:
                runtime.get(result.batch_id)

            maxima = [call.kwargs["max_bytes"] for call in verified.call_args_list]
            self.assertIn(MAX_BATCH_INPUT_BYTES, maxima)
            self.assertIn(MAX_BATCH_RESULT_BYTES, maxima)
            self.assertIn(MAX_BATCH_ITEM_INPUT_BYTES, maxima)

    def test_batch_index_read_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = BatchRuntime(directory)
            result = runtime.evaluate([fixture_manifest().to_dict()])
            index_path = runtime._index_path(result.batch_id)
            index_path.write_bytes(b"{" + b" " * MAX_BATCH_INDEX_BYTES)

            with self.assertRaisesRegex(StoreError, "index exceeds"):
                runtime.get(result.batch_id)

    def test_batch_index_rejects_duplicate_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = BatchRuntime(directory)
            result = runtime.evaluate([fixture_manifest().to_dict()])
            index_path = runtime._index_path(result.batch_id)
            payload = index_path.read_text(encoding="utf-8")
            duplicate = payload.replace(
                '"accepted":true',
                '"accepted":true,"accepted":true',
                1,
            )
            self.assertNotEqual(duplicate, payload)
            index_path.write_text(duplicate, encoding="utf-8")

            with self.assertRaisesRegex(StoreError, "invalid batch index"):
                runtime.get(result.batch_id)

    def test_batch_input_is_size_checked_before_object_store_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = BatchRuntime(directory)
            with (
                patch.object(
                    batch_module,
                    "canonical_bytes",
                    return_value=_OversizedCanonicalBytes(),
                ),
                patch.object(
                    runtime.runtime.store.store,
                    "put",
                    side_effect=AssertionError("oversized input reached persistence"),
                ),
            ):
                with self.assertRaisesRegex(ValidationError, "batch input exceeds"):
                    runtime.evaluate([fixture_manifest().to_dict()])


if __name__ == "__main__":
    unittest.main()
