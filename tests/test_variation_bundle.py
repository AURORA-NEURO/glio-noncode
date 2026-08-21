from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.variation_bundle import (
    VariationBundleEntry,
    VariationBundleFormat,
    VariationEvidenceBundleBuilder,
    build_variation_evidence_bundle,
)
from glio_noncode.variation_public_data import VariationDataState, VariationFixtureCatalog

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "examples" / "variation-public-aggregate.json"
CONTEXT = "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"


class VariationBundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = VariationEvidenceBundleBuilder()

    def test_bundle_contains_five_positive_and_five_review_entries(self) -> None:
        bundle = self.builder.build(FIXTURE)
        self.assertTrue(bundle.accepted)
        self.assertEqual(bundle.quality_state, VariationDataState.ACCEPTED)
        self.assertEqual(len(bundle.entries), 10)
        self.assertEqual(sum(entry.entry_class == "positive" for entry in bundle.entries), 5)
        self.assertEqual(sum(entry.entry_class == "review" for entry in bundle.entries), 5)
        self.assertEqual(bundle.context_key, CONTEXT)

    def test_bundle_entries_retain_operation_kind_and_public_identity(self) -> None:
        bundle = self.builder.build(FIXTURE)
        positive = {
            entry.entry_id: entry
            for entry in bundle.entries
            if entry.entry_class == "positive"
        }
        self.assertEqual(positive["dbsnp:rs121913502:vrs"].kind, "vrs")
        self.assertEqual(positive["categorical:rs121913502"].kind, "categorical")
        self.assertEqual(positive["annotation:rs121913502"].kind, "annotation")
        self.assertEqual(positive["multiallelic:rs121913502"].kind, "multiallelic")
        self.assertEqual(positive["repeat-window:public-reference-01"].kind, "repeat")
        self.assertEqual(
            positive["dbsnp:rs121913502:vrs"].public_identifier,
            "dbsnp:rs121913502",
        )

    def test_review_entries_retain_control_kind(self) -> None:
        bundle = self.builder.build(FIXTURE)
        review = {
            entry.entry_id: entry
            for entry in bundle.entries
            if entry.entry_class == "review"
        }
        self.assertEqual(review["negative:vrs-symbolic-breakend"].kind, "vrs")
        self.assertEqual(review["negative:categorical-label-only"].kind, "categorical")
        self.assertEqual(review["negative:annotation-context-mismatch"].kind, "annotation")
        self.assertEqual(review["negative:multiallelic-symbolic"].kind, "multiallelic")
        self.assertEqual(review["negative:repeat-reference-mismatch"].kind, "repeat")

    def test_bundle_has_quality_contract_and_component_summaries(self) -> None:
        bundle = self.builder.build(FIXTURE)
        self.assertEqual(bundle.contract_manifest["contract_count"], 5)
        self.assertEqual(bundle.component_summaries["quality"]["check_count"], 12)
        self.assertEqual(bundle.component_summaries["fixture"]["check_count"], 29)
        self.assertEqual(bundle.component_summaries["data"]["record_count"], 5)
        self.assertEqual(bundle.component_summaries["scenarios"]["scenario_count"], 10)

    def test_bundle_is_content_addressed_and_verifiable(self) -> None:
        bundle = self.builder.build(FIXTURE)
        payload = bundle.to_dict()
        self.assertRegex(bundle.content_address, r"^sha256:[0-9a-f]{64}$")
        self.assertTrue(VariationEvidenceBundleBuilder.verify(payload))
        payload["entries"][0]["state"] = "review"
        self.assertFalse(VariationEvidenceBundleBuilder.verify(payload))

    def test_bundle_is_deterministic(self) -> None:
        first = self.builder.build(FIXTURE).to_dict()
        second = build_variation_evidence_bundle(FIXTURE).to_dict()
        self.assertEqual(first, second)

    def test_json_render_is_sorted_and_json_ready(self) -> None:
        bundle = self.builder.build(FIXTURE)
        rendered = bundle.render(VariationBundleFormat.JSON)
        payload = json.loads(rendered)
        self.assertTrue(payload["accepted"])
        self.assertEqual(payload["entry_count"], 10)
        self.assertTrue(rendered.endswith("\n"))

    def test_csv_render_has_one_row_per_entry(self) -> None:
        bundle = self.builder.build(FIXTURE)
        rows = bundle.render(VariationBundleFormat.CSV).splitlines()
        self.assertEqual(len(rows), 11)
        self.assertEqual(
            rows[0],
            "entry_id,entry_class,kind,state,source_id,public_identifier,content_address",
        )

    def test_markdown_render_contains_boundary_and_table(self) -> None:
        bundle = self.builder.build(FIXTURE)
        rendered = bundle.render(VariationBundleFormat.MARKDOWN)
        self.assertIn("# Variation evidence bundle", rendered)
        self.assertIn(CONTEXT, rendered)
        self.assertIn("## Entries", rendered)
        self.assertIn("dbsnp:rs121913502", rendered)

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
            self.assertTrue(md_path.read_text(encoding="utf-8").startswith("# Variation"))

    def test_explicit_format_overrides_nonstandard_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bundle.output"
            self.builder.write(FIXTURE, path, output_format=VariationBundleFormat.MARKDOWN)
            self.assertTrue(path.read_text(encoding="utf-8").startswith("# Variation"))

    def test_explicit_format_overrides_recognized_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bundle.json"
            self.builder.write(FIXTURE, path, output_format=VariationBundleFormat.MARKDOWN)
            self.assertTrue(path.read_text(encoding="utf-8").startswith("# Variation"))

    def test_custom_bundle_id_is_retained(self) -> None:
        bundle = self.builder.build(FIXTURE, bundle_id="custom-variation-bundle")
        self.assertEqual(bundle.bundle_id, "custom-variation-bundle")

    def test_bundle_does_not_copy_raw_payload_values(self) -> None:
        serialized = json.dumps(self.builder.build(FIXTURE).to_dict(), sort_keys=True).casefold()
        self.assertNotIn("cccccc", serialized)
        self.assertNotIn("evidence:ncbi-clinvar-rs121913502", serialized)
        self.assertNotIn("patient_id", serialized)
        self.assertNotIn("secret", serialized)

    def test_entry_rejects_blank_fields(self) -> None:
        with self.assertRaises(ValidationError):
            VariationBundleEntry(" ", "positive", "vrs", "supported", "source", "id", "sha256:x")

    def test_invalid_render_format_is_rejected(self) -> None:
        bundle = self.builder.build(FIXTURE)
        with self.assertRaises(ValueError):
            bundle.render("yaml")

    def test_failed_fixture_bundle_is_review_state(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        fixture["records"][0]["payload"]["alternate"] = "<DEL>"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "failed.json"
            path.write_text(json.dumps(fixture), encoding="utf-8")
            bundle = self.builder.build(path)
        self.assertFalse(bundle.accepted)
        self.assertEqual(bundle.quality_state, VariationDataState.REVIEW)
        self.assertTrue(bundle.component_summaries["quality"]["failed_check_ids"])

    def test_bundle_to_dict_includes_entry_counts(self) -> None:
        payload = self.builder.build(FIXTURE).to_dict()
        self.assertEqual(payload["entry_count"], 10)
        self.assertEqual(payload["positive_entry_count"], 5)
        self.assertEqual(payload["review_entry_count"], 5)

    def test_bundle_source_ids_are_sorted_for_stable_consumers(self) -> None:
        bundle = self.builder.build(FIXTURE)
        self.assertEqual(
            bundle.source_ids,
            tuple(sorted(bundle.source_ids)),
        )

    def test_bundle_entries_have_unique_ids(self) -> None:
        bundle = self.builder.build(FIXTURE)
        entry_ids = tuple(entry.entry_id for entry in bundle.entries)
        self.assertEqual(len(entry_ids), len(set(entry_ids)))

    def test_bundle_entries_have_unique_content_addresses(self) -> None:
        bundle = self.builder.build(FIXTURE)
        addresses = tuple(entry.content_address for entry in bundle.entries)
        self.assertEqual(len(addresses), len(set(addresses)))

    def test_verify_rejects_non_mapping(self) -> None:
        self.assertFalse(VariationEvidenceBundleBuilder.verify([]))
        self.assertFalse(VariationEvidenceBundleBuilder.verify({"content_address": 1}))

    def test_verify_ignores_only_derived_convenience_fields(self) -> None:
        payload = self.builder.build(FIXTURE).to_dict()
        payload["entry_count"] = 999
        payload["accepted"] = False
        self.assertTrue(VariationEvidenceBundleBuilder.verify(payload))

    def test_verify_rejects_missing_content_address(self) -> None:
        payload = self.builder.build(FIXTURE).to_dict()
        payload.pop("content_address")
        self.assertFalse(VariationEvidenceBundleBuilder.verify(payload))

    def test_json_and_markdown_render_have_terminal_newlines(self) -> None:
        bundle = self.builder.build(FIXTURE)
        self.assertTrue(bundle.render("json").endswith("\n"))
        self.assertTrue(bundle.render("markdown").endswith("\n"))

    def test_bundle_id_changes_address(self) -> None:
        first = self.builder.build(FIXTURE, bundle_id="one")
        second = self.builder.build(FIXTURE, bundle_id="two")
        self.assertNotEqual(first.content_address, second.content_address)

    def test_custom_bundle_id_requires_text(self) -> None:
        with self.assertRaises(ValidationError):
            self.builder.build(FIXTURE, bundle_id=" ")

    def test_invalid_record_kind_is_a_validation_error(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        fixture["records"][0]["kind"] = "unsupported"
        with self.assertRaises(ValidationError):
            VariationFixtureCatalog.from_fixture(fixture)


if __name__ == "__main__":
    unittest.main()
