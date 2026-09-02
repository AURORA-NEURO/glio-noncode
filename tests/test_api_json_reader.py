from __future__ import annotations

import io
import unittest
from email.message import Message

from glio_noncode.api import (
    MAX_JSON_NESTING_DEPTH,
    MAX_JSON_REQUEST_BYTES,
    ApiHandler,
)


def _handler(body: bytes, *content_lengths: str) -> ApiHandler:
    handler = object.__new__(ApiHandler)
    headers = Message()
    for value in content_lengths:
        headers.add_header("Content-Length", value)
    handler.headers = headers
    handler.rfile = io.BytesIO(body)
    return handler


class ApiJsonReaderTests(unittest.TestCase):
    def test_valid_object_uses_the_declared_byte_length(self) -> None:
        body = '{"label":"café","score":1.5}'.encode()

        self.assertEqual(
            _handler(body, str(len(body)))._read_json(),
            {"label": "café", "score": 1.5},
        )

    def test_legacy_strict_flag_cannot_enable_permissive_json(self) -> None:
        body = b'{"outer":{"value":1,"value":2}}'

        with self.assertRaisesRegex(ValueError, "duplicate object keys"):
            _handler(body, str(len(body)))._read_json(strict=False)

    def test_missing_multiple_and_malformed_content_lengths_are_rejected(self) -> None:
        cases = (
            ((), "missing Content-Length"),
            (("2", "2"), "multiple Content-Length headers"),
            (("",), "invalid Content-Length"),
            (("-1",), "invalid Content-Length"),
            (("+2",), "invalid Content-Length"),
            (("2.0",), "invalid Content-Length"),
            (("NaN",), "invalid Content-Length"),
        )
        for values, message in cases:
            with self.subTest(values=values), self.assertRaisesRegex(ValueError, message):
                _handler(b"{}", *values)._read_json()

    def test_transfer_encoding_cannot_make_body_framing_ambiguous(self) -> None:
        handler = _handler(b"{}", "2")
        handler.headers.add_header("Transfer-Encoding", "chunked")

        with self.assertRaisesRegex(ValueError, "Transfer-Encoding is not supported"):
            handler._read_json()

    def test_empty_oversized_and_short_bodies_have_distinct_errors(self) -> None:
        self.assertEqual(MAX_JSON_REQUEST_BYTES, 5_000_000)

        with self.assertRaisesRegex(ValueError, "must not be empty"):
            _handler(b"", "0")._read_json()
        with self.assertRaisesRegex(
            ValueError,
            f"exceeds {MAX_JSON_REQUEST_BYTES} bytes",
        ):
            _handler(b"", str(MAX_JSON_REQUEST_BYTES + 1))._read_json()
        with self.assertRaisesRegex(
            ValueError,
            f"exceeds {MAX_JSON_REQUEST_BYTES} bytes",
        ):
            _handler(b"", "9" * 5_000)._read_json()
        with self.assertRaisesRegex(ValueError, "ended before Content-Length"):
            _handler(b"{}", "3")._read_json()

    def test_duplicate_keys_are_rejected_at_every_object_depth(self) -> None:
        for body in (
            b'{"value":1,"value":2}',
            b'{"outer":{"value":1,"value":2}}',
        ):
            with self.subTest(body=body), self.assertRaisesRegex(
                ValueError, "duplicate object keys"
            ):
                _handler(body, str(len(body)))._read_json()

    def test_all_non_finite_number_spellings_are_rejected(self) -> None:
        for number in (b"NaN", b"Infinity", b"-Infinity", b"1e1000000"):
            body = b'{"value":' + number + b"}"
            with self.subTest(number=number), self.assertRaisesRegex(
                ValueError, "non-finite number"
            ):
                _handler(body, str(len(body)))._read_json()

    def test_top_level_json_must_remain_an_object(self) -> None:
        body = b"[]"

        with self.assertRaisesRegex(ValueError, "JSON body must be an object"):
            _handler(body, str(len(body)))._read_json()

    def test_json_nesting_is_bounded_without_counting_string_brackets(self) -> None:
        exact = (b'{"value":' * MAX_JSON_NESTING_DEPTH) + b"0" + (
            b"}" * MAX_JSON_NESTING_DEPTH
        )
        self.assertIsInstance(_handler(exact, str(len(exact)))._read_json(), dict)

        over = b'{"value":' + exact + b"}"
        with self.assertRaisesRegex(ValueError, "MAX_JSON_NESTING_DEPTH"):
            _handler(over, str(len(over)))._read_json()

        brackets_in_string = b'{"value":"[[[{{{\\\"}}}]]]"}'
        self.assertEqual(
            _handler(brackets_in_string, str(len(brackets_in_string)))._read_json(),
            {"value": '[[[{{{"}}}]]]'},
        )


class ApiBodyChunkReaderTests(unittest.TestCase):
    def test_streaming_reader_yields_bounded_chunks_without_materializing(self) -> None:
        body = b"x" * 70_000

        chunks = list(
            _handler(body, str(len(body)))._read_body_chunks(max_bytes=len(body))
        )

        self.assertEqual(tuple(map(len, chunks)), (65_536, 4_464))
        self.assertEqual(b"".join(chunks), body)

    def test_streaming_reader_uses_the_same_strict_body_framing(self) -> None:
        cases = (
            ((), "missing Content-Length"),
            (("2", "2"), "multiple Content-Length headers"),
            (("",), "invalid Content-Length"),
            (("-1",), "invalid Content-Length"),
            (("0",), "must not be empty"),
            (("3",), "exceeds 2 bytes"),
            (("9" * 5_000,), "exceeds 2 bytes"),
        )
        for values, message in cases:
            with self.subTest(values=values), self.assertRaisesRegex(ValueError, message):
                list(_handler(b"{}", *values)._read_body_chunks(max_bytes=2))

        handler = _handler(b"{}", "2")
        handler.headers.add_header("Transfer-Encoding", "chunked")
        with self.assertRaisesRegex(ValueError, "Transfer-Encoding is not supported"):
            list(handler._read_body_chunks(max_bytes=2))

    def test_streaming_reader_rejects_short_bodies_and_invalid_internal_limits(self) -> None:
        with self.assertRaisesRegex(ValueError, "ended before Content-Length"):
            list(_handler(b"{}", "3")._read_body_chunks(max_bytes=3))
        for max_bytes in (False, 0, 1.5):
            with self.subTest(max_bytes=max_bytes), self.assertRaisesRegex(
                ValueError,
                "max_bytes must be a positive integer",
            ):
                list(
                    _handler(b"{}", "2")._read_body_chunks(  # type: ignore[arg-type]
                        max_bytes=max_bytes
                    )
                )


if __name__ == "__main__":
    unittest.main()
