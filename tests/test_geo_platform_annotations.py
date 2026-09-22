from __future__ import annotations

import gzip
import hashlib
import tempfile
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.geo_platform_annotations import read_geo_platform_annotations


def _platform_payload(*, rows: tuple[str, ...] | None = None) -> bytes:
    feature_rows = rows or (
        'probe-1\t"GENE A|GENE B"\t9606',
        "probe-2\tGENE2\t9607",
    )
    return (
        "\n".join(
            (
                "^PLATFORM = arraystar-v3",
                "!Platform_geo_accession = GPL123",
                "!Platform_title = Fixture platform",
                "!Platform_table_begin",
                "ID\tGene Symbol\tTaxonomy ID",
                *feature_rows,
                "!platform_table_end",
            )
        )
        + "\n"
    ).encode("utf-8")


class GeoPlatformAnnotationTests(unittest.TestCase):
    def _read(self, payload: bytes, *, columns: tuple[str, ...] = ("gene symbol",)):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "GPL123.soft"
            path.write_bytes(payload)
            return read_geo_platform_annotations(
                path,
                expected_platform_id="gpl123",
                annotation_columns=columns,
            )

    def test_reads_compressed_and_plain_soft_tables_with_exact_source_hash(self) -> None:
        payload = _platform_payload()
        compressed = gzip.compress(payload, mtime=0)

        for source in (payload, compressed):
            with self.subTest(compressed=source is compressed):
                annotations = self._read(source)
                self.assertEqual(annotations.platform_id, "GPL123")
                self.assertEqual(annotations.id_column, "ID")
                self.assertEqual(annotations.annotation_columns, ("Gene Symbol",))
                self.assertEqual(
                    annotations.records,
                    (("probe-1", ("GENE A|GENE B",)), ("probe-2", ("GENE2",))),
                )
                self.assertEqual(annotations.source_sha256, hashlib.sha256(source).hexdigest())
                self.assertEqual(annotations.source_bytes, len(source))

    def test_rejects_platform_mismatch_duplicate_ids_and_absent_columns(self) -> None:
        with self.assertRaisesRegex(ValidationError, "differs from the matrix"):
            self._read(
                _platform_payload().replace(
                    b"!Platform_geo_accession = GPL123",
                    b"!Platform_geo_accession = GPL456",
                )
            )

        with self.assertRaisesRegex(ValidationError, "repeats a feature ID"):
            self._read(
                _platform_payload(rows=("probe-1\tGENE1\t1", "probe-1\tGENE2\t2"))
            )

        with self.assertRaisesRegex(ValidationError, "column is absent"):
            self._read(_platform_payload(), columns=("missing field",))

    def test_rejects_malformed_table_rows_and_duplicate_headers(self) -> None:
        with self.assertRaisesRegex(ValidationError, "duplicate column names"):
            self._read(
                _platform_payload().replace(
                    b"ID\tGene Symbol\tTaxonomy ID",
                    b"ID\tGene Symbol\tgene symbol",
                )
            )

        with self.assertRaisesRegex(ValidationError, "unterminated quoted field"):
            self._read(_platform_payload(rows=('probe-1\t"GENE1\t9606',)))

        with self.assertRaisesRegex(ValidationError, "malformed quoted fields"):
            self._read(_platform_payload(rows=('probe-1\t"GENE1"suffix\t9606',)))

    def test_selects_matching_platform_from_concatenated_soft_file(self) -> None:
        other_platform = (
            "\n".join(
                (
                    "^PLATFORM = arraystar-v2",
                    "!Platform_geo_accession = GPL456",
                    "!Platform_table_begin",
                    "ID\tOther field",
                    "other-probe\tignored",
                    "!Platform_table_end",
                )
            )
            + "\n"
        ).encode("utf-8")

        annotations = self._read(other_platform + _platform_payload())

        self.assertEqual(len(annotations.records), 2)
        self.assertEqual(annotations.records[0], ("probe-1", ("GENE A|GENE B",)))


if __name__ == "__main__":
    unittest.main()
