from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from glio_noncode._cli_support import (
    DEFAULT_MAX_JSON_NESTING_DEPTH,
    read_json,
    read_mapping,
    read_text,
)


class CliSupportTests(unittest.TestCase):
    def _raw(self, root: Path, name: str, value: str) -> str:
        path = root / name
        path.write_text(value, encoding="utf-8")
        return str(path)

    def test_json_rejects_duplicate_keys_and_non_finite_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            invalid = {
                "duplicate": '{"case_id":"one","case_id":"two"}',
                "nan": '{"value":NaN}',
                "infinity": '{"value":Infinity}',
                "overflow": '{"value":1e9999}',
            }
            for name, payload in invalid.items():
                with self.subTest(name=name), self.assertRaises(ValueError):
                    read_json(self._raw(root, f"{name}.json", payload), name)

    def test_json_nesting_has_an_exact_bound_and_ignores_string_brackets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            exact = (
                "[" * DEFAULT_MAX_JSON_NESTING_DEPTH + "0" + "]" * (DEFAULT_MAX_JSON_NESTING_DEPTH)
            )
            self.assertIsNotNone(read_json(self._raw(root, "exact.json", exact), "exact"))
            exceeded = "[" + exact + "]"
            with self.assertRaisesRegex(ValueError, "nesting exceeds"):
                read_json(self._raw(root, "exceeded.json", exceeded), "exceeded")
            self.assertEqual(
                read_json(
                    self._raw(root, "strings.json", '{"text":"[[[\\"]]]}"}'),
                    "strings",
                ),
                {"text": '[[["]]]}'},
            )

    def test_byte_limits_are_exact_for_files_and_unicode_stdin(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = self._raw(root, "exact.txt", "1234")
            self.assertEqual(read_text(path, max_bytes=4), "1234")
            with self.assertRaisesRegex(ValueError, "3-byte limit"):
                read_text(path, max_bytes=3)

        with patch("sys.stdin", io.StringIO("ééé")):
            with self.assertRaisesRegex(ValueError, "5-byte limit"):
                read_text("-", max_bytes=5)

    def test_mapping_shape_and_limit_configuration_are_strict(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            array_path = self._raw(root, "array.json", "[]")
            with self.assertRaisesRegex(ValueError, "must be a JSON object"):
                read_mapping(array_path, "mapping")
            for kwargs in ({"max_bytes": True}, {"max_nesting_depth": 0}):
                with (
                    self.subTest(kwargs=kwargs),
                    self.assertRaisesRegex(
                        ValueError,
                        "positive integer",
                    ),
                ):
                    read_json(array_path, "mapping", **kwargs)

    def test_unpaired_unicode_surrogates_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = self._raw(Path(temporary), "surrogate.json", '"\\ud800"')
            with self.assertRaisesRegex(ValueError, "canonical Unicode JSON"):
                read_json(path, "surrogate")


if __name__ == "__main__":
    unittest.main()
