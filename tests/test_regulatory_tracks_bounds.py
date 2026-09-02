from __future__ import annotations

import json
import unittest

from glio_noncode.errors import ValidationError
from glio_noncode.regulatory_tracks import (
    MAX_REGULATORY_TRACK_AUXILIARY_LINES,
    MAX_REGULATORY_TRACK_RECORDS,
    RegulatoryTrackFormat,
    RegulatoryTrackParser,
)


def _bed_rows(count: int) -> str:
    return "".join(
        f"7\t{index * 10}\t{index * 10 + 5}\tbed-{index}\t800\t+\n"
        for index in range(count)
    )


def _gff_rows(count: int) -> str:
    return "##gff-version 3\n" + "".join(
        f"7\tfixture\tenhancer\t{index * 10 + 1}\t{index * 10 + 5}\t.\t+\t.\tID=gff-{index}\n"
        for index in range(count)
    )


def _json_rows(count: int) -> str:
    return json.dumps(
        {
            "features": [
                {
                    "id": f"json-{index}",
                    "chrom": "7",
                    "start": index * 10 + 1,
                    "end": index * 10 + 5,
                }
                for index in range(count)
            ]
        }
    )


class RegulatoryTrackBoundTests(unittest.TestCase):
    def test_parser_policy_rejects_invalid_or_unbounded_limits(self) -> None:
        invalid = (
            {"max_records": True},
            {"max_records": 0},
            {"max_records": 1.5},
            {"max_records": MAX_REGULATORY_TRACK_RECORDS + 1},
            {"max_auxiliary_lines": False},
            {"max_auxiliary_lines": 0},
            {"max_auxiliary_lines": 1.5},
            {
                "max_auxiliary_lines": MAX_REGULATORY_TRACK_AUXILIARY_LINES + 1,
            },
        )
        for arguments in invalid:
            with self.subTest(arguments=arguments), self.assertRaises(ValidationError):
                RegulatoryTrackParser(**arguments)

        for source_id, genome_build in ((None, "GRCh38"), ("source", None)):
            with self.subTest(source_id=source_id, genome_build=genome_build), self.assertRaises(
                ValidationError
            ):
                RegulatoryTrackParser().parse_text(
                    _bed_rows(1),
                    source_id=source_id,  # type: ignore[arg-type]
                    genome_build=genome_build,  # type: ignore[arg-type]
                )

    def test_exact_record_limit_is_accepted_for_every_format(self) -> None:
        parser = RegulatoryTrackParser(max_records=2)
        cases = (
            (RegulatoryTrackFormat.BED, _bed_rows(2)),
            (RegulatoryTrackFormat.GFF3, _gff_rows(2)),
            (RegulatoryTrackFormat.JSON, _json_rows(2)),
        )
        for input_format, text in cases:
            with self.subTest(input_format=input_format):
                batch = parser.parse_text(
                    text,
                    source_id=f"bounded-{input_format.value}",
                    genome_build="GRCh38",
                    input_format=input_format,
                )
                self.assertEqual(len(batch.features), 2)
                self.assertEqual(batch.errors, ())

    def test_over_limit_inputs_stop_before_parsing_the_sentinel_record(self) -> None:
        parser = RegulatoryTrackParser(max_records=2)
        cases = (
            (RegulatoryTrackFormat.BED, _bed_rows(2) + "not-a-valid-bed-row\n"),
            (
                RegulatoryTrackFormat.GFF3,
                _gff_rows(2) + "not-a-valid-gff-row\n",
            ),
            (RegulatoryTrackFormat.JSON, _json_rows(3)),
        )
        for input_format, text in cases:
            with self.subTest(input_format=input_format):
                batch = parser.parse_text(
                    text,
                    source_id=f"bounded-{input_format.value}",
                    genome_build="GRCh38",
                    input_format=input_format,
                )
                self.assertEqual(len(batch.features), 2)
                self.assertEqual(
                    tuple(issue.code for issue in batch.errors),
                    ("record_limit_exceeded",),
                )
                self.assertEqual(batch.errors[0].line_number, 4 if input_format == "gff3" else 3)

    def test_json_rejects_duplicate_keys_and_non_finite_numbers(self) -> None:
        parser = RegulatoryTrackParser()
        invalid = (
            '[{"id":"first","id":"second","chrom":"7","start":1,"end":2}]',
            '[{"id":"non-finite","chrom":"7","start":1,"end":2,"score":NaN}]',
        )
        for text in invalid:
            with self.subTest(text=text):
                batch = parser.parse_text(
                    text,
                    source_id="strict-json",
                    genome_build="GRCh38",
                    input_format="json",
                )
                self.assertEqual(batch.features, ())
                self.assertEqual(
                    tuple(issue.code for issue in batch.errors),
                    ("invalid_json",),
                )

    def test_over_limit_receipt_is_deterministic_and_addresses_unread_tail(self) -> None:
        parser = RegulatoryTrackParser(max_records=1)
        prefix = _bed_rows(1) + "7\t20\t25\tsentinel\n"
        first = parser.parse_text(
            prefix + "7\t30\t35\ttail-a\n",
            source_id="bounded-tail",
            genome_build="GRCh38",
            input_format="bed",
        )
        repeated = parser.parse_text(
            prefix + "7\t30\t35\ttail-a\n",
            source_id="bounded-tail",
            genome_build="GRCh38",
            input_format="bed",
        )
        changed_tail = parser.parse_text(
            prefix + "7\t30\t35\ttail-b\n",
            source_id="bounded-tail",
            genome_build="GRCh38",
            input_format="bed",
        )
        self.assertEqual(first, repeated)
        self.assertNotEqual(first.input_hash, changed_tail.input_hash)
        self.assertNotEqual(first.content_address, changed_tail.content_address)

    def test_auxiliary_lines_are_bounded_before_record_processing(self) -> None:
        parser = RegulatoryTrackParser(max_records=2, max_auxiliary_lines=2)
        batch = parser.parse_text(
            "# header-one\n\n# header-three\n" + _bed_rows(1),
            source_id="bounded-headers",
            genome_build="GRCh38",
            input_format="bed",
        )
        self.assertEqual(batch.features, ())
        self.assertEqual(
            tuple(issue.code for issue in batch.errors),
            ("auxiliary_line_limit_exceeded",),
        )
        self.assertEqual(batch.errors[0].line_number, 3)

        with self.assertRaisesRegex(ValidationError, "format detection"):
            parser.parse_text(
                "\n\n\n" + _bed_rows(1),
                source_id="bounded-detection",
                genome_build="GRCh38",
            )


if __name__ == "__main__":
    unittest.main()
