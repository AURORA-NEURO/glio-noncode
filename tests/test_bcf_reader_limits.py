from __future__ import annotations

import struct
import unittest
import zlib
from unittest.mock import patch

from glio_noncode.bcf import (
    BCF_MAX_BGZF_BLOCK_BYTES,
    BCF_MAX_BGZF_BLOCKS,
    BCF_MAX_BGZF_DECOMPRESSED_BLOCK_BYTES,
    BCF_MAX_DECOMPRESSED_BYTES,
    BCF_MAX_HEADER_BYTES,
    BCF_MAX_INPUT_BYTES,
    BCF_MAX_RECORD_BYTES,
    BCF_MAX_RECORDS,
    BcfReader,
)
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import content_hash
from tests.test_bcf import _bgzf, _raw_bcf


def _layout(raw: bytes) -> tuple[int, int, int, bytes, bytes]:
    header_length = struct.unpack_from("<I", raw, 5)[0]
    record_offset = 9 + header_length
    shared_length, individual_length = struct.unpack_from("<II", raw, record_offset)
    record_bytes = 8 + shared_length + individual_length
    shared_start = record_offset + 8
    individual_start = shared_start + shared_length
    return (
        header_length,
        record_offset,
        record_bytes,
        raw[shared_start:individual_start],
        raw[individual_start : individual_start + individual_length],
    )


def _repeat_records(raw: bytes, count: int) -> bytes:
    _, record_offset, _, _, _ = _layout(raw)
    return raw[:record_offset] + (raw[record_offset:] * count)


def _two_bgzf_blocks(raw: bytes) -> bytes:
    split = len(raw) // 2
    return _bgzf(raw[:split]) + _bgzf(raw[split:])


class BcfReaderLimitTests(unittest.TestCase):
    def test_exact_raw_limits_preserve_document_and_legacy_hashes(self) -> None:
        raw = _raw_bcf()
        header_length, _, record_bytes, shared, individual = _layout(raw)
        expected = BcfReader().read(raw)

        bounded = BcfReader(
            max_input_bytes=len(raw),
            max_decompressed_bytes=len(raw),
            max_bgzf_blocks=1,
            max_bgzf_block_bytes=1,
            max_header_bytes=header_length,
            max_records=1,
            max_record_bytes=record_bytes,
        ).read(raw)

        self.assertEqual(bounded.to_dict(), expected.to_dict())
        self.assertEqual(bounded.input_hash, content_hash(raw.hex()))
        self.assertEqual(
            bounded.records[0].raw_hash,
            content_hash({"shared": shared.hex(), "individual": individual.hex()}),
        )
        self.assertEqual(
            bounded.content_address,
            content_hash(
                {
                    "version": bounded.version,
                    "header_text": bounded.header_text,
                    "records": list(bounded.records),
                    "bgzf_blocks": bounded.bgzf_blocks,
                }
            ),
        )

    def test_exact_bgzf_limits_preserve_document_byte_for_byte(self) -> None:
        raw = _raw_bcf()
        bgzf = _bgzf(raw)
        header_length, _, record_bytes, _, _ = _layout(raw)
        expected = BcfReader().read(bgzf)

        bounded = BcfReader(
            max_input_bytes=len(bgzf),
            max_decompressed_bytes=len(raw),
            max_bgzf_blocks=1,
            max_bgzf_block_bytes=len(bgzf),
            max_header_bytes=header_length,
            max_records=1,
            max_record_bytes=record_bytes,
        ).read(bgzf)

        self.assertEqual(bounded.to_dict(), expected.to_dict())
        self.assertEqual(bounded.input_hash, content_hash(bgzf.hex()))
        self.assertEqual(bounded.records[0].raw_hash, BcfReader().read(raw).records[0].raw_hash)

    def test_limit_configuration_is_strict_and_cannot_raise_hard_ceilings(self) -> None:
        limits = {
            "max_input_bytes": BCF_MAX_INPUT_BYTES,
            "max_decompressed_bytes": BCF_MAX_DECOMPRESSED_BYTES,
            "max_bgzf_blocks": BCF_MAX_BGZF_BLOCKS,
            "max_bgzf_block_bytes": BCF_MAX_BGZF_BLOCK_BYTES,
            "max_header_bytes": BCF_MAX_HEADER_BYTES,
            "max_records": BCF_MAX_RECORDS,
            "max_record_bytes": BCF_MAX_RECORD_BYTES,
        }
        for name, ceiling in limits.items():
            for value in (False, 0, 1.5, ceiling + 1):
                with self.subTest(name=name, value=value), self.assertRaisesRegex(
                    ValidationError,
                    name,
                ):
                    BcfReader(**{name: value})  # type: ignore[arg-type]

    def test_malformed_input_types_fail_with_typed_validation(self) -> None:
        for value in (b"", bytearray(b"BCF"), memoryview(b"BCF"), "BCF"):
            with self.subTest(value_type=type(value).__name__), self.assertRaises(
                ValidationError
            ):
                BcfReader().read(value)  # type: ignore[arg-type]

    def test_input_limit_fails_before_legacy_hashing(self) -> None:
        raw = _raw_bcf()
        with patch(
            "glio_noncode.bcf._legacy_hex_content_hash",
            side_effect=AssertionError("oversized input must not be hashed"),
        ) as legacy_hash:
            with self.assertRaisesRegex(ValidationError, "max_input_bytes"):
                BcfReader(max_input_bytes=len(raw) - 1).read(raw)
        legacy_hash.assert_not_called()

    def test_raw_decompressed_and_header_limits_fail_before_header_decode(self) -> None:
        raw = _raw_bcf()
        header_length, _, _, _, _ = _layout(raw)
        for arguments, message in (
            ({"max_decompressed_bytes": len(raw) - 1}, "max_decompressed_bytes"),
            ({"max_header_bytes": header_length - 1}, "max_header_bytes"),
        ):
            reader = BcfReader(**arguments)
            with self.subTest(arguments=arguments), patch.object(
                reader,
                "_parse_header",
                wraps=reader._parse_header,
            ) as parse_header:
                with self.assertRaisesRegex(ValidationError, message):
                    reader.read(raw)
            parse_header.assert_not_called()

    def test_per_record_limit_fails_before_record_allocation_and_decode(self) -> None:
        raw = _raw_bcf()
        _, _, record_bytes, _, _ = _layout(raw)
        reader = BcfReader(max_record_bytes=record_bytes - 1)
        with patch.object(reader, "_record", wraps=reader._record) as decode_record:
            with self.assertRaisesRegex(ValidationError, "max_record_bytes"):
                reader.read(raw)
        decode_record.assert_not_called()

    def test_record_count_stops_before_decoding_the_overflow_record(self) -> None:
        raw = _repeat_records(_raw_bcf(), 2)
        reader = BcfReader(max_records=1)
        with patch.object(reader, "_record", wraps=reader._record) as decode_record:
            with self.assertRaisesRegex(ValidationError, "max_records"):
                reader.read(raw)
        self.assertEqual(decode_record.call_count, 1)

        exact = BcfReader(max_records=2).read(raw)
        self.assertEqual(len(exact.records), 2)

    def test_bgzf_block_count_stops_before_inflating_overflow_member(self) -> None:
        bgzf = _two_bgzf_blocks(_raw_bcf())
        with patch(
            "glio_noncode.bcf.zlib.decompressobj",
            wraps=zlib.decompressobj,
        ) as decompress:
            with self.assertRaisesRegex(ValidationError, "max_bgzf_blocks"):
                BcfReader(max_bgzf_blocks=1).read(bgzf)
        self.assertEqual(decompress.call_count, 1)

        exact = BcfReader(max_bgzf_blocks=2).read(bgzf)
        self.assertEqual(exact.bgzf_blocks, 2)
        self.assertEqual(len(exact.records), 1)

    def test_bgzf_member_size_fails_before_inflation(self) -> None:
        bgzf = _bgzf(_raw_bcf())
        with patch(
            "glio_noncode.bcf.zlib.decompressobj",
            side_effect=AssertionError("oversized member must not be inflated"),
        ) as decompress:
            with self.assertRaisesRegex(ValidationError, "max_bgzf_block_bytes"):
                BcfReader(max_bgzf_block_bytes=len(bgzf) - 1).read(bgzf)
        decompress.assert_not_called()

    def test_declared_decompressed_limit_fails_before_inflation(self) -> None:
        raw = _raw_bcf()
        bgzf = _bgzf(raw)
        with patch(
            "glio_noncode.bcf.zlib.decompressobj",
            side_effect=AssertionError("oversized output must not be inflated"),
        ) as decompress:
            with self.assertRaisesRegex(ValidationError, "max_decompressed_bytes"):
                BcfReader(max_decompressed_bytes=len(raw) - 1).read(bgzf)
        decompress.assert_not_called()

    def test_bgzf_decompression_bomb_is_rejected_from_declared_size(self) -> None:
        bgzf = _bgzf(b"A" * (BCF_MAX_BGZF_DECOMPRESSED_BLOCK_BYTES + 1))
        with patch(
            "glio_noncode.bcf.zlib.decompressobj",
            side_effect=AssertionError("declared bomb must not be inflated"),
        ) as decompress:
            with self.assertRaisesRegex(ValidationError, "decompressed block"):
                BcfReader(max_input_bytes=len(bgzf)).read(bgzf)
        decompress.assert_not_called()

    def test_bgzf_decompressed_block_exact_format_ceiling_is_accepted(self) -> None:
        payload = b"A" * BCF_MAX_BGZF_DECOMPRESSED_BLOCK_BYTES
        bgzf = _bgzf(payload)

        decoded, blocks = BcfReader(
            max_input_bytes=len(bgzf),
            max_decompressed_bytes=len(payload),
        )._decompress(bgzf)

        self.assertEqual(decoded, payload)
        self.assertEqual(blocks, 1)

    def test_bgzf_decompression_bomb_with_forged_size_is_still_bounded(self) -> None:
        bgzf = bytearray(_bgzf(b"A" * 200_000))
        struct.pack_into("<I", bgzf, len(bgzf) - 4, 1)

        with self.assertRaisesRegex(ValidationError, "bounded output allowance"):
            BcfReader(max_input_bytes=len(bgzf)).read(bytes(bgzf))

    def test_bgzf_rejects_bytes_after_the_declared_gzip_stream(self) -> None:
        payload = _raw_bcf()
        bgzf = bytearray(_bgzf(payload))
        bgzf.extend(b"JUNK" + struct.pack("<I", len(payload)))
        struct.pack_into("<H", bgzf, 16, len(bgzf) - 1)

        with self.assertRaisesRegex(ValidationError, "after its gzip stream"):
            BcfReader(max_input_bytes=len(bgzf)).read(bytes(bgzf))


if __name__ == "__main__":
    unittest.main()
