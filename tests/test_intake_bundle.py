"""Compact intake evidence bundle tests."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.intake_bundle import (
    IntakeBundleEntry,
    IntakeBundleFormat,
    IntakeEvidenceBundleBuilder,
    build_intake_evidence_bundle,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "examples" / "intake-public-aggregate.json"


class IntakeBundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = IntakeEvidenceBundleBuilder()

    def test_bundle_contains_four_positive_and_eight_review_entries(self) -> None:
        bundle = self.builder.build(FIXTURE_PATH)
        self.assertTrue(bundle.accepted)
        self.assertEqual(bundle.state.value, "accepted")
        self.assertEqual(len(bundle.entries), 12)
        self.assertEqual(sum(entry.entry_class == "positive" for entry in bundle.entries), 4)
        self.assertEqual(sum(entry.entry_class == "review" for entry in bundle.entries), 8)
        self.assertEqual(bundle.context_key.split("|"), [
            "GRCh38",
            "diffuse_glioma",
            "adult",
            "malignant_oligodendrocyte_like",
            "tumor_core",
            "pre_treatment",
        ])

    def test_bundle_has_all_capability_ids_and_no_raw_payload_fields(self) -> None:
        bundle = build_intake_evidence_bundle(FIXTURE_PATH)
        self.assertEqual(
            {entry.capability_id for entry in bundle.entries},
            {"GNC-D01-C13", "GNC-D01-C14", "GNC-D01-C15", "GNC-D01-C16"},
        )
        serialized = json.dumps(bundle.to_dict(), sort_keys=True).casefold()
        self.assertNotIn("consent_status", serialized)
        self.assertNotIn("private_note", serialized)
        self.assertNotIn("medical_record", serialized)
        self.assertNotIn("patient_id", serialized)
        self.assertTrue(all(entry.evidence_address.startswith("sha256:") for entry in bundle.entries))

    def test_bundle_is_content_addressed_and_verifiable(self) -> None:
        bundle = self.builder.build(FIXTURE_PATH)
        payload = bundle.to_dict()
        self.assertRegex(bundle.content_address, r"^sha256:[0-9a-f]{64}$")
        self.assertTrue(self.builder.verify(payload))
        mutated = copy.deepcopy(payload)
        mutated["entries"][0]["state"] = "tampered"
        self.assertFalse(self.builder.verify(mutated))
        self.assertFalse(self.builder.verify({}))

    def test_bundle_is_deterministic_and_custom_id_is_addressed(self) -> None:
        first = self.builder.build(FIXTURE_PATH)
        second = self.builder.build(FIXTURE_PATH)
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())
        custom = self.builder.build(FIXTURE_PATH, bundle_id="custom-intake-bundle")
        self.assertNotEqual(first.bundle_id, custom.bundle_id)
        self.assertNotEqual(first.content_address, custom.content_address)

    def test_json_csv_and_markdown_renderings_are_available(self) -> None:
        bundle = self.builder.build(FIXTURE_PATH)
        json_text = bundle.render(IntakeBundleFormat.JSON)
        csv_text = bundle.render(IntakeBundleFormat.CSV)
        markdown = bundle.render(IntakeBundleFormat.MARKDOWN)
        self.assertEqual(json.loads(json_text)["entry_count"], 12)
        self.assertEqual(len(csv_text.splitlines()), 13)
        self.assertIn("# Intake evidence bundle", markdown)
        self.assertIn("GNC-D01-C13", markdown)
        self.assertIn("evidence_boundary", bundle.quality_summary)

    def test_write_uses_suffix_and_explicit_format(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            json_path = root / "bundle.json"
            csv_path = root / "bundle.csv"
            md_path = root / "bundle.output"
            self.builder.write(FIXTURE_PATH, json_path)
            self.builder.write(FIXTURE_PATH, csv_path)
            self.builder.write(FIXTURE_PATH, md_path, output_format=IntakeBundleFormat.MARKDOWN)
            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8"))["entry_count"], 12)
            self.assertTrue(csv_path.read_text(encoding="utf-8").startswith("entry_id,"))
            self.assertTrue(md_path.read_text(encoding="utf-8").startswith("# Intake evidence bundle"))

    def test_review_bundle_requires_explicit_allow_review(self) -> None:
        raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        raw["provenance"]["patient_level_data"] = True
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaises(ValueError):
                self.builder.build(path)
            bundle = self.builder.build(path, allow_review=True)
        self.assertFalse(bundle.accepted)
        self.assertEqual(bundle.state.value, "review")

    def test_entry_contract_requires_nonempty_content_address(self) -> None:
        with self.assertRaises(ValueError):
            IntakeBundleEntry(
                "entry",
                "positive",
                "GNC-D01-C13",
                "operation",
                "accepted",
                "public",
                "source",
                "not-addressed",
                "summary",
            )


if __name__ == "__main__":
    unittest.main()
