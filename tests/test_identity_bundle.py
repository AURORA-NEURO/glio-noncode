from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.identity_bundle import (
    IdentityBundleEntry,
    IdentityBundleFormat,
    IdentityEvidenceBundleBuilder,
    build_identity_evidence_bundle,
)
from glio_noncode.identity_public_data import IdentityDataState, IdentityFixtureCatalog

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "examples" / "identity-public-aggregate.json"
CONTEXT = "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"


class IdentityBundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = IdentityEvidenceBundleBuilder()

    def test_bundle_contains_four_positive_and_eight_review_entries(self) -> None:
        bundle = self.builder.build(FIXTURE)
        self.assertTrue(bundle.accepted)
        self.assertEqual(bundle.quality_state, IdentityDataState.ACCEPTED)
        self.assertEqual(len(bundle.entries), 12)
        self.assertEqual(sum(entry.entry_class == "positive" for entry in bundle.entries), 4)
        self.assertEqual(sum(entry.entry_class == "review" for entry in bundle.entries), 8)
        self.assertEqual(bundle.context_key, CONTEXT)

    def test_positive_entries_retain_kind_and_public_identity(self) -> None:
        bundle = self.builder.build(FIXTURE)
        entries = {entry.entry_id: entry for entry in bundle.entries}
        self.assertEqual(entries["equivalence:rs121913502"].kind, "equivalence")
        self.assertEqual(entries["reconciliation:rs121913502"].kind, "reconciliation")
        self.assertEqual(entries["sample:public-aggregate-01"].kind, "sample")
        self.assertEqual(entries["custody:public-aggregate-artifact-01"].kind, "custody")
        self.assertEqual(
            entries["equivalence:rs121913502"].public_identifier,
            "dbsnp:rs121913502",
        )

    def test_review_entries_retain_control_kinds(self) -> None:
        bundle = self.builder.build(FIXTURE)
        entries = {entry.entry_id: entry for entry in bundle.entries}
        self.assertEqual(entries["negative:equivalence:absent-query"].kind, "equivalence")
        self.assertEqual(entries["negative:reconciliation:ambiguous-alias"].kind, "reconciliation")
        self.assertEqual(entries["negative:sample:cross-subject"].kind, "sample")
        self.assertEqual(entries["negative:custody:broken-link"].kind, "custody")

    def test_bundle_has_component_contract_and_quality_summaries(self) -> None:
        bundle = self.builder.build(FIXTURE)
        self.assertEqual(bundle.contract_manifest["contract_count"], 4)
        self.assertEqual(bundle.component_summaries["quality"]["check_count"], 12)
        self.assertEqual(bundle.component_summaries["fixture"]["check_count"], 37)
        self.assertEqual(bundle.component_summaries["data"]["positive_count"], 4)
        self.assertEqual(bundle.component_summaries["scenarios"]["scenario_count"], 12)

    def test_bundle_is_content_addressed_and_verifiable(self) -> None:
        bundle = self.builder.build(FIXTURE)
        payload = bundle.to_dict()
        self.assertRegex(bundle.content_address, r"^sha256:[0-9a-f]{64}$")
        self.assertTrue(IdentityEvidenceBundleBuilder.verify(payload))
        payload["entries"][0]["state"] = "review"
        self.assertFalse(IdentityEvidenceBundleBuilder.verify(payload))

    def test_bundle_is_deterministic(self) -> None:
        first = self.builder.build(FIXTURE).to_dict()
        second = build_identity_evidence_bundle(FIXTURE).to_dict()
        self.assertEqual(first, second)

    def test_json_render_is_sorted_and_json_ready(self) -> None:
        bundle = self.builder.build(FIXTURE)
        rendered = bundle.render(IdentityBundleFormat.JSON)
        payload = json.loads(rendered)
        self.assertTrue(payload["accepted"])
        self.assertEqual(payload["entry_count"], 12)
        self.assertTrue(rendered.endswith("\n"))

    def test_csv_render_has_one_row_per_entry(self) -> None:
        rows = self.builder.build(FIXTURE).render(IdentityBundleFormat.CSV).splitlines()
        self.assertEqual(len(rows), 13)
        self.assertEqual(
            rows[0],
            "entry_id,entry_class,kind,state,source_id,public_identifier,content_address",
        )

    def test_markdown_render_contains_boundary_and_table(self) -> None:
        rendered = self.builder.build(FIXTURE).render(IdentityBundleFormat.MARKDOWN)
        self.assertIn("# Identity evidence bundle", rendered)
        self.assertIn(CONTEXT, rendered)
        self.assertIn("## Entries", rendered)
        self.assertIn("equivalence:rs121913502", rendered)

    def test_suffix_infers_output_format(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            json_path = root / "bundle.json"
            csv_path = root / "bundle.csv"
            md_path = root / "bundle.md"
            self.builder.write(FIXTURE, json_path)
            self.builder.write(FIXTURE, csv_path)
            self.builder.write(FIXTURE, md_path)
            self.assertTrue(json.loads(json_path.read_text(encoding="utf-8"))["accepted"])
            self.assertTrue(csv_path.read_text(encoding="utf-8").startswith("entry_id,"))
            self.assertTrue(md_path.read_text(encoding="utf-8").startswith("# Identity"))

    def test_explicit_format_overrides_recognized_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bundle.json"
            self.builder.write(FIXTURE, path, output_format=IdentityBundleFormat.MARKDOWN)
            self.assertTrue(path.read_text(encoding="utf-8").startswith("# Identity"))

    def test_explicit_format_overrides_nonstandard_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bundle.output"
            self.builder.write(FIXTURE, path, output_format=IdentityBundleFormat.CSV)
            self.assertTrue(path.read_text(encoding="utf-8").startswith("entry_id,"))

    def test_bundle_does_not_copy_raw_payload_values(self) -> None:
        serialized = json.dumps(self.builder.build(FIXTURE).to_dict(), sort_keys=True).casefold()
        self.assertNotIn("public-aggregate-subject-01", serialized)
        self.assertNotIn("sha256:identity-artifact-raw", serialized)
        self.assertNotIn("patient_id", serialized)
        self.assertNotIn("secret", serialized)

    def test_entry_rejects_blank_fields(self) -> None:
        with self.assertRaises(ValidationError):
            IdentityBundleEntry(" ", "positive", "sample", "supported", "source", "id", "sha256:x")

    def test_invalid_render_format_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.builder.build(FIXTURE).render("yaml")

    def test_verify_rejects_non_mapping_and_missing_address(self) -> None:
        self.assertFalse(IdentityEvidenceBundleBuilder.verify([]))
        payload = self.builder.build(FIXTURE).to_dict()
        payload.pop("content_address")
        self.assertFalse(IdentityEvidenceBundleBuilder.verify(payload))

    def test_verify_ignores_only_derived_count_fields(self) -> None:
        payload = self.builder.build(FIXTURE).to_dict()
        payload["entry_count"] = 999
        payload["accepted"] = False
        self.assertTrue(IdentityEvidenceBundleBuilder.verify(payload))

    def test_custom_bundle_id_changes_address(self) -> None:
        first = self.builder.build(FIXTURE, bundle_id="one")
        second = self.builder.build(FIXTURE, bundle_id="two")
        self.assertNotEqual(first.content_address, second.content_address)

    def test_custom_bundle_id_requires_text(self) -> None:
        with self.assertRaises(ValidationError):
            self.builder.build(FIXTURE, bundle_id=" ")

    def test_invalid_record_kind_remains_catalog_validation(self) -> None:
        raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
        raw["records"][0]["kind"] = "invalid"
        with self.assertRaises(ValidationError):
            IdentityFixtureCatalog.from_fixture(raw)


if __name__ == "__main__":
    unittest.main()
