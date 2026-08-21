from __future__ import annotations

import copy
import unittest

from glio_noncode.errors import ValidationError
from glio_noncode.reference_annotation_public_data import (
    REFERENCE_ANNOTATION_CONTEXT_KEY,
    ReferenceAnnotationOperation,
    ReferenceAnnotationRole,
    audit_reference_annotation_data,
    build_reference_annotation_catalog,
    default_reference_annotation_fixture,
    load_reference_annotation_fixture,
)


class ReferenceAnnotationPublicDataTests(unittest.TestCase):
    def test_default_fixture_has_five_sources_and_sixteen_records(self) -> None:
        fixture = default_reference_annotation_fixture()
        self.assertEqual(len(fixture.sources), 5)
        self.assertEqual(len(fixture.records), 16)
        self.assertEqual(len(fixture.positive_records), 4)
        self.assertEqual(len(fixture.control_records), 12)

    def test_fixture_covers_four_operations_with_balanced_roles(self) -> None:
        fixture = default_reference_annotation_fixture()
        self.assertEqual(
            {record.operation for record in fixture.records}, set(ReferenceAnnotationOperation)
        )
        for operation in ReferenceAnnotationOperation:
            rows = [record for record in fixture.records if record.operation is operation]
            self.assertEqual(len(rows), 4)
            self.assertEqual(sum(row.role is ReferenceAnnotationRole.POSITIVE for row in rows), 1)
            self.assertEqual(sum(row.role is ReferenceAnnotationRole.CONTROL for row in rows), 3)

    def test_data_audit_accepts_public_boundary(self) -> None:
        audit = audit_reference_annotation_data()
        self.assertTrue(audit.accepted)
        self.assertEqual(len(audit.checks), 26)
        self.assertEqual(audit.failed_check_ids, ())

    def test_catalog_rejects_duplicate_record_identity(self) -> None:
        fixture = default_reference_annotation_fixture()
        duplicate = copy.copy(fixture.records[0])
        mutated = fixture.records + (duplicate,)
        with self.assertRaises(ValidationError):
            build_reference_annotation_catalog(
                fixture.__class__(
                    fixture.fixture_id,
                    fixture.fixture_version,
                    fixture.context_key,
                    fixture.evidence_boundary,
                    fixture.sources,
                    mutated,
                    "bad",
                )
            )

    def test_record_context_is_exact(self) -> None:
        fixture = default_reference_annotation_fixture()
        self.assertEqual(fixture.context_key, REFERENCE_ANNOTATION_CONTEXT_KEY)
        self.assertTrue(
            all(
                record.context_key == REFERENCE_ANNOTATION_CONTEXT_KEY for record in fixture.records
            )
        )

    def test_source_receipts_are_http_and_addressed(self) -> None:
        fixture = default_reference_annotation_fixture()
        self.assertTrue(all(source.uri.startswith("https://") for source in fixture.sources))
        self.assertTrue(
            all(source.content_address.startswith("sha256:") for source in fixture.sources)
        )

    def test_serialized_fixture_descriptor_resolves_to_typed_fixture(self) -> None:
        fixture = load_reference_annotation_fixture(
            {"fixture": "default_reference_annotation_fixture"}
        )
        self.assertEqual(fixture.fixture_id, "reference-annotation-public-aggregate")
        self.assertEqual(fixture.fixture_version, "2026.08.c05-c08.v1")

    def test_fixture_records_keep_expected_issue_codes(self) -> None:
        fixture = default_reference_annotation_fixture()
        by_id = {record.record_id: record for record in fixture.records}
        self.assertIn("invalid_gencode_row", by_id["C05-CTRL-001"].expected_issue_codes)
        self.assertIn("ambiguous_mane_match", by_id["C06-CTRL-001"].expected_issue_codes)
        self.assertIn("term_match_ambiguous", by_id["C07-CTRL-001"].expected_issue_codes)
        self.assertIn("disease_mapping_ambiguous", by_id["C08-CTRL-001"].expected_issue_codes)

    def test_fixture_source_references_close_over_source_catalog(self) -> None:
        fixture = default_reference_annotation_fixture()
        catalog = build_reference_annotation_catalog(fixture)
        self.assertTrue(
            all(set(record.source_ids) <= set(catalog.source_ids) for record in fixture.records)
        )

    def test_fixture_hashes_are_stable(self) -> None:
        first = default_reference_annotation_fixture()
        second = default_reference_annotation_fixture()
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(
            build_reference_annotation_catalog(first).content_address,
            build_reference_annotation_catalog(second).content_address,
        )
