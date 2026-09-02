from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.case_workflow import (
    CaseRunResult,
    PreparedCase,
    RegulatoryTrackSource,
    VariantSource,
    capabilities,
    case_workflow_schema,
    prepare_case,
    run_case,
)
from glio_noncode.errors import ValidationError
from glio_noncode.models import ReferenceContext
from glio_noncode.replay import ReplayVerifier
from glio_noncode.runtime import CaseRuntime

VCF = "\n".join(
    (
        "##fileformat=VCFv4.3",
        "##source=inline-fixture",
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1",
        "7\t100\tvar-1\tA\tT\t99\tPASS\tDP=42\tGT\t0/1",
    )
)


def context(build: str = "GRCh38") -> ReferenceContext:
    return ReferenceContext(
        genome_build=build,
        disease_class="diffuse_glioma",
        age_group="adult",
        cell_state="stem_like",
        territory="tumor_core",
        treatment_phase="pre_treatment",
        source_version="fixture-context-v1",
    )


def variant(payload: str | bytes = VCF, build: str = "GRCh38") -> VariantSource:
    return VariantSource(
        source_id="fixture-variants",
        input_format="vcf",
        genome_build=build,
        payload=payload,
        metadata={"assay": "research_fixture"},
    )


def track(
    source_id: str = "fixture-track",
    feature_id: str = "EGFR",
    build: str = "GRCh38",
    *,
    payload: str | bytes | None = None,
) -> RegulatoryTrackSource:
    value = payload if payload is not None else f"7\t90\t130\t{feature_id}\t800\t+\n"
    return RegulatoryTrackSource(
        source_id=source_id,
        input_format="bed",
        genome_build=build,
        context=context(build),
        payload=value,
        metadata={"license": "synthetic-test-only"},
        target_gene_keys=("Name",),
    )


def prepared(**overrides: object) -> PreparedCase:
    values: dict[str, object] = {
        "case_id": "case-workflow-fixture",
        "subject_id": "subject-research-fixture",
        "context": context(),
        "variant_source": variant(),
        "regulatory_tracks": (track(),),
        "metadata": {"purpose": "local research fixture"},
        "requested_by": "researcher-local",
    }
    values.update(overrides)
    return prepare_case(**values)  # type: ignore[arg-type]


class CaseWorkflowTests(unittest.TestCase):
    def test_vcf_bed_case_persists_and_reopens_with_valid_replay(self) -> None:
        value = prepared()
        self.assertTrue(value.accepted, value.to_dict())
        self.assertIsNotNone(value.manifest)
        assert value.manifest is not None
        self.assertEqual([item.variant_id for item in value.manifest.variants], ["var-1"])
        self.assertEqual([item.element_id for item in value.manifest.candidate_elements], ["EGFR"])
        self.assertEqual(value.manifest.candidate_elements[0].target_genes, ("EGFR",))

        with tempfile.TemporaryDirectory() as directory:
            result = run_case(value, data_root=directory)
            self.assertTrue(result.accepted, result.to_dict())
            self.assertIsNotNone(result.dossier)
            self.assertIsNotNone(result.replay_report)
            assert result.dossier is not None
            assert result.replay_report is not None
            self.assertEqual(result.dossier.run_id, value.run_id)
            self.assertTrue(result.replay_report.event_chain_valid)
            self.assertTrue(result.replay_report.stored_dossier_matches_address)

            reopened = CaseRuntime(directory)
            run_record = reopened.get_run(result.dossier.run_id)
            stored = reopened.get_dossier(str(run_record["dossier_address"]))
            events = reopened.store.store.get(str(run_record["event_address"]))
            replayed = ReplayVerifier().verify(run_record, events, stored)
            self.assertTrue(replayed.event_chain_valid)
            self.assertTrue(replayed.stored_dossier_matches_address)
            self.assertEqual(run_record["input_address"], value.manifest_address)

    def test_prepare_identity_excludes_observational_receipt_timestamp(self) -> None:
        first = prepared()
        second = prepared()
        self.assertTrue(first.accepted)
        self.assertEqual(first.manifest_address, second.manifest_address)
        self.assertEqual(first.run_id, second.run_id)
        self.assertEqual(first.content_address, second.content_address)
        self.assertTrue(all(item.observed_at for item in first.stage_receipts))
        assert first.manifest is not None
        serialized_provenance = json.dumps(first.manifest.metadata, sort_keys=True)
        self.assertNotIn("created_at", serialized_provenance)
        intake_receipt = first.manifest.metadata["case_workflow_provenance"]["variant_source"][
            "intake_receipt"
        ]
        self.assertNotIn("created_at", intake_receipt)

    def test_track_input_order_is_canonical_and_provenance_is_addressed(self) -> None:
        alpha = track("track-alpha", "enh-alpha")
        zeta = track("track-zeta", "enh-zeta")
        forward = prepared(regulatory_tracks=(zeta, alpha))
        reverse = prepared(regulatory_tracks=(alpha, zeta))
        self.assertEqual(forward.manifest_address, reverse.manifest_address)
        self.assertEqual(forward.run_id, reverse.run_id)
        assert forward.manifest is not None
        self.assertEqual(
            [item.element_id for item in forward.manifest.candidate_elements],
            ["enh-alpha", "enh-zeta"],
        )
        provenance = forward.manifest.metadata["case_workflow_provenance"]
        self.assertTrue(provenance["variant_source"]["batch_address"].startswith("sha256:"))
        self.assertEqual(
            [item["source_id"] for item in provenance["regulatory_tracks"]],
            ["track-alpha", "track-zeta"],
        )
        self.assertTrue(
            all(
                item["batch_address"].startswith("sha256:")
                for item in provenance["regulatory_tracks"]
            )
        )
        self.assertTrue(all(item.startswith("sha256:") for item in forward.provenance_addresses))

    def test_fail_closed_gates_are_typed(self) -> None:
        cases = {
            "intake": prepared(
                variant_source=VariantSource(
                    source_id="bad-variants",
                    input_format="tsv",
                    genome_build="GRCh38",
                    payload="chrom\tpos\tref\n7\tbad\tA\n",
                )
            ),
            "variant_build": prepared(variant_source=variant(build="GRCh37")),
            "track_build": prepared(regulatory_tracks=(track(build="GRCh37"),)),
            "empty": prepared(regulatory_tracks=(track(payload="# no features\n"),)),
            "duplicate": prepared(
                regulatory_tracks=(
                    track("track-one", "duplicate-element"),
                    track("track-two", "duplicate-element"),
                )
            ),
        }
        expected = {
            "intake": {"missing_tsv_columns", "no_variants"},
            "variant_build": {"genome_build_mismatch"},
            "track_build": {"genome_build_mismatch"},
            "empty": {"no_candidate_elements"},
            "duplicate": {"duplicate_element_id"},
        }
        for name, value in cases.items():
            with self.subTest(name=name):
                self.assertTrue(value.blocked, value.to_dict())
                self.assertIsNone(value.manifest)
                self.assertIsNone(value.run_id)
                self.assertTrue(expected[name] <= {item.code for item in value.issues})
                with tempfile.TemporaryDirectory() as directory:
                    result = run_case(value, data_root=directory)
                    self.assertTrue(result.blocked)
                    self.assertIsNone(result.dossier)

    def test_zero_elements_is_allowed_only_for_live_reference(self) -> None:
        blocked = prepared(regulatory_tracks=(track(payload="# header only\n"),))
        accepted = prepared(
            regulatory_tracks=(track(payload="# header only\n"),),
            live_reference=True,
        )
        self.assertTrue(blocked.blocked)
        self.assertTrue(accepted.accepted, accepted.to_dict())
        assert accepted.manifest is not None
        self.assertEqual(accepted.manifest.candidate_elements, ())

    def test_runtime_filesystem_error_is_a_blocked_typed_result(self) -> None:
        value = prepared()
        with tempfile.TemporaryDirectory() as directory:
            not_a_directory = Path(directory) / "occupied"
            not_a_directory.write_text("not a data root", encoding="utf-8")
            result = run_case(value, data_root=not_a_directory)
        self.assertTrue(result.blocked)
        self.assertIsNone(result.dossier)
        self.assertIn("runtime_error", {item.code for item in result.issues})
        runtime_receipt = result.stage_receipts[-1]
        self.assertEqual(str(runtime_receipt.state), "blocked")
        self.assertEqual(runtime_receipt.error_count, 1)

    def test_strict_mapping_round_trips_and_rejects_tampering(self) -> None:
        source = variant(VCF.encode("utf-8"))
        self.assertEqual(VariantSource.from_mapping(source.to_dict()), source)
        source_track = track(payload=b"7\t90\t130\tEGFR\t800\t+\n")
        self.assertEqual(RegulatoryTrackSource.from_mapping(source_track.to_dict()), source_track)

        value = prepared()
        restored = PreparedCase.from_mapping(value.to_dict())
        self.assertEqual(restored.to_dict(), value.to_dict())
        tampered = value.to_dict()
        tampered["unknown"] = True
        with self.assertRaises(ValidationError):
            PreparedCase.from_mapping(tampered)
        tampered = value.to_dict()
        tampered["content_address"] = "sha256:" + "0" * 64
        with self.assertRaises(ValidationError):
            PreparedCase.from_mapping(tampered)

        with tempfile.TemporaryDirectory() as directory:
            result = run_case(value, data_root=directory)
            restored_result = CaseRunResult.from_mapping(result.to_dict())
            self.assertEqual(restored_result.to_dict(), result.to_dict())

    def test_public_summaries_do_not_leak_payload_paths_or_raw_values(self) -> None:
        secret_path = r"C:\private\patient-source.vcf"
        secret_marker = "RAW-PAYLOAD-MUST-NOT-LEAK"
        source = VariantSource(
            source_id=secret_path,
            input_format="vcf",
            genome_build="GRCh38",
            payload=VCF.replace("DP=42", f"TOKEN={secret_marker}"),
            metadata={"source_path": secret_path, "raw": secret_marker},
        )
        value = prepared(variant_source=source)
        summary = json.dumps(value.public_summary(), sort_keys=True)
        self.assertNotIn(secret_path, summary)
        self.assertNotIn(secret_marker, summary)
        self.assertNotIn("raw_hash", summary)
        with tempfile.TemporaryDirectory() as directory:
            result_summary = json.dumps(
                run_case(value, data_root=directory).public_summary(), sort_keys=True
            )
        self.assertNotIn(secret_path, result_summary)
        self.assertNotIn(secret_marker, result_summary)

    def test_schema_and_capabilities_expose_strict_inline_contract(self) -> None:
        schema = case_workflow_schema()
        advertised = capabilities()
        self.assertEqual(schema["version"], "case-workflow-v1")
        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(schema["$defs"]["variant_source"]["additionalProperties"])
        self.assertFalse(advertised["server_local_paths"])
        self.assertIn("inline_bytes", advertised["source_transport"])
        self.assertIn("manifest_address", advertised["deterministic_outputs"])


if __name__ == "__main__":
    unittest.main()
