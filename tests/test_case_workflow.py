from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator

from glio_noncode.adapters import ADAPTER_HARD_MAX_SELECTED, AdapterLimits
from glio_noncode.case_workflow import (
    MAX_CASE_CANDIDATE_ELEMENTS,
    MAX_CASE_REGULATORY_TRACKS,
    MAX_CASE_RNA_CONSEQUENCES,
    MAX_CASE_RUNTIME_WORK_ITEMS,
    MAX_CASE_TARGET_GENE_KEY_LENGTH,
    MAX_CASE_TARGET_GENE_KEYS,
    MAX_CASE_TARGETS_PER_ELEMENT,
    CaseRunResult,
    PreparedCase,
    RegulatoryTrackSource,
    VariantSource,
    capabilities,
    case_workflow_schema,
    prepare_case,
    prepare_request_schema,
    prepared_case_schema,
    regulatory_track_source_schema,
    run_case,
    run_request_schema,
    run_result_schema,
    variant_source_schema,
)
from glio_noncode.errors import ValidationError
from glio_noncode.intake import (
    MAX_VARIANT_INTAKE_AUXILIARY_LINES,
    MAX_VARIANT_INTAKE_RECORDS,
)
from glio_noncode.models import ReferenceContext
from glio_noncode.regulatory_tracks import (
    MAX_REGULATORY_TRACK_AUXILIARY_LINES,
    MAX_REGULATORY_TRACK_RECORDS,
)
from glio_noncode.replay import ReplayVerifier
from glio_noncode.runtime import CaseRuntime
from glio_noncode.serialization import content_hash
from glio_noncode.storage import MAX_RUN_HISTORY_ENTRIES

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

        unsorted_rows = prepared(
            regulatory_tracks=(
                track(
                    payload=(
                        "7\t140\t180\tGENE-Z\t800\t+\n"
                        "7\t90\t130\tGENE-A\t800\t+\n"
                    )
                ),
            )
        )
        self.assertTrue(unsorted_rows.accepted, unsorted_rows.to_dict())
        self.assertEqual(
            [item.element_id for item in unsorted_rows.manifest.candidate_elements],  # type: ignore[union-attr]
            ["GENE-A", "GENE-Z"],
        )
        self.assertEqual(
            PreparedCase.from_mapping(unsorted_rows.to_dict()).to_dict(),
            unsorted_rows.to_dict(),
        )

    def test_regulatory_track_iterables_are_bounded_for_both_parameter_names(self) -> None:
        from itertools import repeat

        alias = prepared(regulatory_tracks=(), tracks=(track(),))
        self.assertTrue(alias.accepted, alias.to_dict())

        for parameter_name in ("regulatory_tracks", "tracks"):
            arguments: dict[str, object] = {
                "regulatory_tracks": (),
                parameter_name: repeat(track(), MAX_CASE_REGULATORY_TRACKS + 1),
            }
            with (
                self.subTest(parameter_name=parameter_name),
                self.assertRaisesRegex(
                    ValidationError,
                    f"maximum of {MAX_CASE_REGULATORY_TRACKS}",
                ),
            ):
                prepared(**arguments)

        for invalid in ("track.json", {"source_id": "not-an-iterable-container"}):
            with (
                self.subTest(invalid=type(invalid).__name__),
                self.assertRaisesRegex(
                    ValidationError,
                    "iterable of track objects",
                ),
            ):
                prepared(regulatory_tracks=invalid)

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

    def test_accepted_preparation_replays_hard_gates_provenance_and_receipts(self) -> None:
        value = prepared()
        assert value.manifest is not None

        def run_id_for(manifest: object) -> str:
            address = manifest.content_address  # type: ignore[attr-defined]
            requested_by = manifest.requested_by  # type: ignore[attr-defined]
            digest = content_hash(
                {"input": address, "requested_by": requested_by}
            ).split(":", 1)[1]
            return f"run-{digest[:24]}"

        mismatched_variant = replace(value.manifest.variants[0], genome_build="GRCh37")
        mismatched_manifest = replace(value.manifest, variants=(mismatched_variant,))
        with self.assertRaisesRegex(ValidationError, "variant genome build"):
            PreparedCase(
                state="accepted",
                manifest=mismatched_manifest,
                run_id=run_id_for(mismatched_manifest),
                live_reference=False,
                stage_receipts=value.stage_receipts,
                issues=value.issues,
            )

        with self.assertRaisesRegex(ValidationError, "live_reference provenance"):
            PreparedCase(
                state="accepted",
                manifest=value.manifest,
                run_id=value.run_id,
                live_reference=True,
                stage_receipts=value.stage_receipts,
                issues=value.issues,
            )

        metadata_without_provenance = dict(value.manifest.metadata)
        metadata_without_provenance.pop("case_workflow_provenance")
        no_provenance_manifest = replace(
            value.manifest,
            metadata=metadata_without_provenance,
        )
        with self.assertRaisesRegex(ValidationError, "requires case_workflow_provenance"):
            PreparedCase(
                state="accepted",
                manifest=no_provenance_manifest,
                run_id=run_id_for(no_provenance_manifest),
                live_reference=False,
                stage_receipts=value.stage_receipts,
                issues=value.issues,
            )

        with self.assertRaisesRegex(ValidationError, "receipt topology"):
            PreparedCase(
                state="accepted",
                manifest=value.manifest,
                run_id=value.run_id,
                live_reference=False,
                stage_receipts=(),
                issues=value.issues,
            )

        mutable = prepared()
        object.__setattr__(mutable, "stage_receipts", ())
        with self.assertRaisesRegex(ValidationError, "receipt topology"):
            _ = mutable.content_address

    def test_accepted_preparation_rejects_readdressed_nested_provenance(self) -> None:
        value = prepared()
        assert value.manifest is not None
        metadata = json.loads(json.dumps(value.manifest.metadata))
        intake_receipt = metadata["case_workflow_provenance"]["variant_source"][
            "intake_receipt"
        ]
        intake_receipt["record_count"] += 1
        intake_body = {
            key: item for key, item in intake_receipt.items() if key != "content_address"
        }
        intake_receipt["content_address"] = content_hash(intake_body)
        tampered_manifest = replace(value.manifest, metadata=metadata)
        digest = content_hash(
            {
                "input": tampered_manifest.content_address,
                "requested_by": tampered_manifest.requested_by,
            }
        ).split(":", 1)[1]
        with self.assertRaisesRegex(ValidationError, "variant receipt does not match"):
            PreparedCase(
                state="accepted",
                manifest=tampered_manifest,
                run_id=f"run-{digest[:24]}",
                live_reference=False,
                stage_receipts=value.stage_receipts,
                issues=value.issues,
            )

        two_tracks = prepared(
            regulatory_tracks=(
                track("track-alpha", "GENE-A"),
                track("track-zeta", "GENE-Z"),
            )
        )
        assert two_tracks.manifest is not None
        metadata = json.loads(json.dumps(two_tracks.manifest.metadata))
        metadata["case_workflow_provenance"]["regulatory_tracks"].reverse()
        tampered_manifest = replace(two_tracks.manifest, metadata=metadata)
        digest = content_hash(
            {
                "input": tampered_manifest.content_address,
                "requested_by": tampered_manifest.requested_by,
            }
        ).split(":", 1)[1]
        with self.assertRaisesRegex(ValidationError, "track provenance is not canonical"):
            PreparedCase(
                state="accepted",
                manifest=tampered_manifest,
                run_id=f"run-{digest[:24]}",
                live_reference=False,
                stage_receipts=two_tracks.stage_receipts,
                issues=two_tracks.issues,
            )

        shared_source = prepared(
            regulatory_tracks=(
                track(payload="7\t90\t130\tGENE-A\t800\t+\n7\t140\t180\tGENE-B\t800\t+\n"),
            )
        )
        assert shared_source.manifest is not None
        candidates = list(shared_source.manifest.candidate_elements)
        candidates[1] = replace(
            candidates[1],
            context=replace(candidates[1].context, source_version="forged-context-version"),
        )
        tampered_manifest = replace(
            shared_source.manifest,
            candidate_elements=tuple(candidates),
        )
        digest = content_hash(
            {
                "input": tampered_manifest.content_address,
                "requested_by": tampered_manifest.requested_by,
            }
        ).split(":", 1)[1]
        with self.assertRaisesRegex(ValidationError, "context does not match provenance"):
            PreparedCase(
                state="accepted",
                manifest=tampered_manifest,
                run_id=f"run-{digest[:24]}",
                live_reference=False,
                stage_receipts=shared_source.stage_receipts,
                issues=shared_source.issues,
            )

        changed_candidate = replace(
            shared_source.manifest.candidate_elements[0],
            target_genes=("FORGED-GENE",),
        )
        tampered_manifest = replace(
            shared_source.manifest,
            candidate_elements=(changed_candidate, *shared_source.manifest.candidate_elements[1:]),
        )
        digest = content_hash(
            {
                "input": tampered_manifest.content_address,
                "requested_by": tampered_manifest.requested_by,
            }
        ).split(":", 1)[1]
        with self.assertRaisesRegex(ValidationError, "candidate address"):
            PreparedCase(
                state="accepted",
                manifest=tampered_manifest,
                run_id=f"run-{digest[:24]}",
                live_reference=False,
                stage_receipts=shared_source.stage_receipts,
                issues=shared_source.issues,
            )

        collision_context = ReferenceContext(
            genome_build="GRCh38",
            disease_class="diffuse|glioma",
            age_group="adult",
            cell_state="stem_like",
            territory="tumor_core",
            treatment_phase="pre_treatment",
            source_version="collision-v1",
        )
        collision = prepared(
            context=collision_context,
            regulatory_tracks=(
                RegulatoryTrackSource(
                    source_id="fixture-track",
                    input_format="bed",
                    genome_build="GRCh38",
                    context=collision_context,
                    payload="7\t90\t130\tEGFR\t800\t+\n",
                    target_gene_keys=("Name",),
                ),
            ),
        )
        assert collision.manifest is not None
        candidate = collision.manifest.candidate_elements[0]
        colliding_but_different = replace(
            candidate.context,
            disease_class="diffuse",
            age_group="glioma|adult",
        )
        self.assertEqual(candidate.context.key, colliding_but_different.key)
        tampered_manifest = replace(
            collision.manifest,
            candidate_elements=(replace(candidate, context=colliding_but_different),),
        )
        digest = content_hash(
            {
                "input": tampered_manifest.content_address,
                "requested_by": tampered_manifest.requested_by,
            }
        ).split(":", 1)[1]
        with self.assertRaisesRegex(ValidationError, "context does not match provenance"):
            PreparedCase(
                state="accepted",
                manifest=tampered_manifest,
                run_id=f"run-{digest[:24]}",
                live_reference=False,
                stage_receipts=collision.stage_receipts,
                issues=collision.issues,
            )

    def test_generated_legacy_v1_track_provenance_without_full_context_reopens(self) -> None:
        value = prepared()
        assert value.manifest is not None
        metadata = json.loads(json.dumps(value.manifest.metadata))
        track_provenance = metadata["case_workflow_provenance"]["regulatory_tracks"][0]
        track_provenance.pop("context")
        legacy_manifest = replace(value.manifest, metadata=metadata)
        digest = content_hash(
            {
                "input": legacy_manifest.content_address,
                "requested_by": legacy_manifest.requested_by,
            }
        ).split(":", 1)[1]
        legacy_receipts = (
            *value.stage_receipts[:-1],
            replace(value.stage_receipts[-1], output_address=legacy_manifest.content_address),
        )
        legacy = PreparedCase(
            state="accepted",
            manifest=legacy_manifest,
            run_id=f"run-{digest[:24]}",
            live_reference=value.live_reference,
            stage_receipts=legacy_receipts,
            issues=value.issues,
        )
        self.assertEqual(PreparedCase.from_mapping(legacy.to_dict()).to_dict(), legacy.to_dict())

    def test_run_result_closes_preparation_prefix_runtime_metadata_and_addresses(self) -> None:
        value = prepared()
        with tempfile.TemporaryDirectory() as directory:
            result = run_case(value, data_root=directory)

        with self.assertRaisesRegex(ValidationError, "preparation receipt prefix"):
            CaseRunResult(
                state=result.state,
                prepared=result.prepared,
                dossier=result.dossier,
                run_record=result.run_record,
                replay_report=result.replay_report,
                stage_receipts=(result.stage_receipts[-1],),
                issues=result.issues,
            )

        blocked_preparation = prepared(variant_source=variant(build="GRCh37"))
        with tempfile.TemporaryDirectory() as directory:
            blocked_from_preparation = run_case(blocked_preparation, data_root=directory)
        with self.assertRaisesRegex(ValidationError, "dropped preparation evidence"):
            CaseRunResult(
                state=blocked_from_preparation.state,
                prepared=blocked_from_preparation.prepared,
                dossier=None,
                run_record=None,
                replay_report=None,
                stage_receipts=blocked_from_preparation.stage_receipts,
                issues=(),
            )
        forged_source = replace(
            blocked_from_preparation.stage_receipts[-1],
            source_id="forged-run",
        )
        with self.assertRaisesRegex(ValidationError, "source_id does not match"):
            CaseRunResult(
                state=blocked_from_preparation.state,
                prepared=blocked_from_preparation.prepared,
                dossier=None,
                run_record=None,
                replay_report=None,
                stage_receipts=(
                    *blocked_from_preparation.stage_receipts[:-1],
                    forged_source,
                ),
                issues=blocked_from_preparation.issues,
            )

        forged_runtime = replace(
            result.stage_receipts[-1],
            metadata={"persisted": True, "replay_valid": True, "unexpected": True},
        )
        with self.assertRaisesRegex(ValidationError, "runtime metadata"):
            CaseRunResult(
                state=result.state,
                prepared=result.prepared,
                dossier=result.dossier,
                run_record=result.run_record,
                replay_report=result.replay_report,
                stage_receipts=(*result.stage_receipts[:-1], forged_runtime),
                issues=result.issues,
            )

        with tempfile.TemporaryDirectory() as directory:
            occupied = Path(directory) / "occupied"
            occupied.write_text("not a directory", encoding="utf-8")
            blocked = run_case(value, data_root=occupied)
        forged_output = replace(
            blocked.stage_receipts[-1],
            output_address="sha256:" + "0" * 64,
        )
        with self.assertRaisesRegex(ValidationError, "absent dossier"):
            CaseRunResult(
                state=blocked.state,
                prepared=blocked.prepared,
                dossier=blocked.dossier,
                run_record=blocked.run_record,
                replay_report=blocked.replay_report,
                stage_receipts=(*blocked.stage_receipts[:-1], forged_output),
                issues=blocked.issues,
            )

    def test_run_record_addresses_and_histories_match_runtime_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            serialized = run_case(prepared(), data_root=directory).to_dict()

        malformed = json.loads(json.dumps(serialized))
        malformed["run_record"]["event_address"] = "not-an-address"
        malformed["run_record"]["event_history"] = ["not-an-address"]
        with self.assertRaisesRegex(ValidationError, "canonical sha256"):
            CaseRunResult.from_mapping(malformed)

        over_limit = json.loads(json.dumps(serialized))
        over_limit["run_record"]["event_history"] = [
            f"sha256:{index:064x}" for index in range(MAX_RUN_HISTORY_ENTRIES + 1)
        ]
        over_limit["run_record"]["event_address"] = over_limit["run_record"][
            "event_history"
        ][-1]
        with self.assertRaisesRegex(ValidationError, f"maximum of {MAX_RUN_HISTORY_ENTRIES}"):
            CaseRunResult.from_mapping(over_limit)

        schema = run_result_schema()["properties"]["run_record"]["oneOf"][0]
        self.assertEqual(
            schema["properties"]["event_history"]["maxItems"],
            MAX_RUN_HISTORY_ENTRIES,
        )
        self.assertEqual(
            schema["properties"]["dossier_history"]["maxItems"],
            MAX_RUN_HISTORY_ENTRIES,
        )

    def test_dossier_recursive_and_deep_payloads_raise_validation_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            serialized = run_case(prepared(), data_root=directory).to_dict()

        recursive = json.loads(json.dumps(serialized))
        cycle: list[object] = []
        cycle.append(cycle)
        recursive["dossier"]["hypotheses"] = cycle
        with self.assertRaises(ValidationError):
            CaseRunResult.from_mapping(recursive)

        deeply_nested = json.loads(json.dumps(serialized))
        root: dict[str, object] = {}
        cursor = root
        for _ in range(2_000):
            child: dict[str, object] = {}
            cursor["child"] = child
            cursor = child
        deeply_nested["dossier"]["hypotheses"] = [root]
        with self.assertRaises(ValidationError):
            CaseRunResult.from_mapping(deeply_nested)

    def test_source_mapping_identifiers_are_strict_strings(self) -> None:
        for field_name, invalid in (
            ("source_id", 7),
            ("genome_build", 38),
            ("input_format", ["vcf"]),
            ("sample_id", 101),
        ):
            raw = variant().to_dict()
            raw[field_name] = invalid
            with (
                self.subTest(source="variant", field=field_name),
                self.assertRaises(ValidationError),
            ):
                VariantSource.from_mapping(raw)

        for field_name, invalid in (
            ("source_id", 7),
            ("genome_build", 38),
            ("input_format", ["bed"]),
            ("target_gene_keys", ["Name", 7]),
        ):
            raw = track().to_dict()
            raw[field_name] = invalid
            with self.subTest(source="track", field=field_name), self.assertRaises(ValidationError):
                RegulatoryTrackSource.from_mapping(raw)

        for invalid_keys in ("Name", None, ("Name", " Name ")):
            with self.subTest(direct_target_keys=invalid_keys), self.assertRaises(ValidationError):
                RegulatoryTrackSource(
                    source_id="strict-track",
                    input_format="bed",
                    genome_build="GRCh38",
                    context=context(),
                    payload="7\t90\t130\tEGFR\t800\t+\n",
                    target_gene_keys=invalid_keys,  # type: ignore[arg-type]
                )

    def test_target_gene_key_work_is_bounded_before_track_conversion(self) -> None:
        exact_keys = tuple(f"gene_key_{index}" for index in range(MAX_CASE_TARGET_GENE_KEYS))
        boundary = RegulatoryTrackSource(
            source_id="bounded-target-keys",
            input_format="bed",
            genome_build="GRCh38",
            context=context(),
            payload="7\t90\t130\tEGFR\t800\t+\n",
            target_gene_keys=exact_keys,
        )
        self.assertEqual(boundary.target_gene_keys, exact_keys)

        with self.assertRaisesRegex(
            ValidationError,
            f"maximum of {MAX_CASE_TARGET_GENE_KEYS} items",
        ):
            RegulatoryTrackSource(
                source_id="too-many-target-keys",
                input_format="bed",
                genome_build="GRCh38",
                context=context(),
                payload="7\t90\t130\tEGFR\t800\t+\n",
                target_gene_keys=exact_keys + ("one_too_many",),
            )

        exact_length = "g" * MAX_CASE_TARGET_GENE_KEY_LENGTH
        self.assertEqual(
            RegulatoryTrackSource(
                source_id="bounded-target-key-length",
                input_format="bed",
                genome_build="GRCh38",
                context=context(),
                payload="7\t90\t130\tEGFR\t800\t+\n",
                target_gene_keys=(exact_length,),
            ).target_gene_keys,
            (exact_length,),
        )
        with self.assertRaisesRegex(
            ValidationError,
            f"must not exceed {MAX_CASE_TARGET_GENE_KEY_LENGTH} characters",
        ):
            RegulatoryTrackSource(
                source_id="too-long-target-key",
                input_format="bed",
                genome_build="GRCh38",
                context=context(),
                payload="7\t90\t130\tEGFR\t800\t+\n",
                target_gene_keys=(exact_length + "g",),
            )

    def test_aggregate_candidate_element_work_is_bounded_across_tracks(self) -> None:
        import glio_noncode.case_workflow as workflow

        sources = (
            track("track-a", "GENE-A"),
            track("track-b", "GENE-B"),
            track("track-c", "GENE-C"),
        )
        original_limit = workflow.MAX_CASE_CANDIDATE_ELEMENTS
        try:
            workflow.MAX_CASE_CANDIDATE_ELEMENTS = 1
            exact = prepared(regulatory_tracks=sources[:1])
            self.assertTrue(exact.accepted, exact.to_dict())
            self.assertEqual(len(exact.manifest.candidate_elements), 1)  # type: ignore[union-attr]

            exceeded = prepared(regulatory_tracks=sources)
            self.assertTrue(exceeded.blocked)
            self.assertEqual(
                [issue.code for issue in exceeded.issues].count("candidate_element_limit_exceeded"),
                2,
            )
            track_receipts = exceeded.stage_receipts[1:]
            self.assertEqual(track_receipts[1].record_count, 1)
            self.assertEqual(track_receipts[2].record_count, 0)

            persisted = exact.to_dict()
            workflow.MAX_CASE_CANDIDATE_ELEMENTS = 0
            with self.assertRaisesRegex(
                ValidationError,
                "candidate_elements exceeds the maximum",
            ):
                PreparedCase.from_mapping(persisted)
        finally:
            workflow.MAX_CASE_CANDIDATE_ELEMENTS = original_limit

    def test_variant_candidate_target_work_is_bounded_and_published(self) -> None:
        import glio_noncode.case_workflow as workflow

        # The one-variant/one-element fixture costs one pair scan, one gene,
        # and one unresolved state expansion: three conservative work items.
        with patch.object(workflow, "MAX_CASE_RUNTIME_WORK_ITEMS", 3):
            boundary = prepared()
            self.assertTrue(boundary.accepted, boundary.to_dict())
            persisted = boundary.to_dict()

        with patch.object(workflow, "MAX_CASE_RUNTIME_WORK_ITEMS", 2):
            exceeded = prepared()
            self.assertTrue(exceeded.blocked)
            self.assertIn(
                "case_runtime_work_limit_exceeded",
                {item.code for item in exceeded.issues},
            )
            with self.assertRaisesRegex(ValidationError, "runtime work items"):
                PreparedCase.from_mapping(persisted)
            with self.assertRaisesRegex(ValidationError, "runtime work items"):
                run_case(persisted)

        over_targets = json.loads(json.dumps(persisted))
        over_targets["manifest"]["candidate_elements"][0]["target_genes"] = [
            f"GENE-{index}" for index in range(MAX_CASE_TARGETS_PER_ELEMENT + 1)
        ]
        self.assertFalse(Draft202012Validator(prepared_case_schema()).is_valid(over_targets))
        with self.assertRaisesRegex(
            ValidationError,
            f"maximum of {MAX_CASE_TARGETS_PER_ELEMENT}",
        ):
            PreparedCase.from_mapping(over_targets)

        manifest_schema = prepared_case_schema()["properties"]["manifest"]["oneOf"][0]
        candidate_schema = manifest_schema["properties"]["candidate_elements"]["items"]
        self.assertEqual(
            candidate_schema["properties"]["target_genes"]["maxItems"],
            MAX_CASE_TARGETS_PER_ELEMENT,
        )
        self.assertEqual(
            candidate_schema["properties"]["state_ids"]["maxItems"],
            MAX_CASE_TARGETS_PER_ELEMENT,
        )
        expected_limits = {
            "max_targets_per_element_collection": MAX_CASE_TARGETS_PER_ELEMENT,
            "max_work_items": MAX_CASE_RUNTIME_WORK_ITEMS,
        }
        self.assertEqual(prepare_request_schema()["x-runtime-limits"], expected_limits)
        self.assertEqual(run_request_schema()["x-runtime-limits"], expected_limits)
        self.assertEqual(
            capabilities()["runtime_work_limits"]["max_work_items"],
            MAX_CASE_RUNTIME_WORK_ITEMS,
        )

    def test_reference_context_mapping_is_strict_and_canonical(self) -> None:
        raw_context = {
            "genome_build": " GRCh38 ",
            "disease_class": " diffuse_glioma ",
            "age_group": " adult ",
            "cell_state": " stem_like ",
            "assay_support": [" RNA-seq ", "ATAC-seq"],
        }
        raw_track = track().to_dict()
        raw_track["context"] = raw_context
        rebuilt = RegulatoryTrackSource.from_mapping(raw_track)
        self.assertEqual(rebuilt.context.genome_build, "GRCh38")
        self.assertEqual(rebuilt.context.disease_class, "diffuse_glioma")
        self.assertEqual(rebuilt.context.assay_support, ("RNA-seq", "ATAC-seq"))
        self.assertEqual(rebuilt.context.territory, "unknown")
        self.assertEqual(rebuilt.context.source_version, "unspecified")

        malformed_contexts = (
            raw_context | {"disease_class": 7},
            raw_context | {"territory": None},
            raw_context | {"assay_support": "RNA-seq"},
            raw_context | {"assay_support": None},
            raw_context | {"assay_support": ["RNA-seq", " RNA-seq "]},
        )
        for malformed in malformed_contexts:
            raw_track = track().to_dict()
            raw_track["context"] = malformed
            with self.subTest(context=malformed), self.assertRaises(ValidationError):
                RegulatoryTrackSource.from_mapping(raw_track)

        with self.assertRaises(ValidationError):
            ReferenceContext(
                "GRCh38",
                "diffuse_glioma",
                "adult",
                "stem_like",
                assay_support="RNA-seq",  # type: ignore[arg-type]
            )

    def test_payload_encoding_declarations_are_strict_and_canonical(self) -> None:
        for factory, label in (
            (VariantSource.from_mapping, "variant"),
            (RegulatoryTrackSource.from_mapping, "track"),
        ):
            raw = variant().to_dict() if label == "variant" else track().to_dict()
            raw["data_encoding"] = raw["payload_encoding"]
            with (
                self.subTest(source=label, case="dual encoding"),
                self.assertRaisesRegex(
                    ValidationError,
                    "at most one payload encoding",
                ),
            ):
                factory(raw)

            raw = variant().to_dict() if label == "variant" else track().to_dict()
            raw["payload_encoding"] = 7
            with (
                self.subTest(source=label, case="typed encoding"),
                self.assertRaisesRegex(
                    ValidationError,
                    "payload encoding must be text or base64",
                ),
            ):
                factory(raw)

            raw = variant().to_dict() if label == "variant" else track().to_dict()
            raw["payload"] = "ZE=="
            raw["payload_encoding"] = "base64"
            with (
                self.subTest(source=label, case="canonical base64"),
                self.assertRaisesRegex(
                    ValidationError,
                    "not canonical base64",
                ),
            ):
                factory(raw)

    def test_metadata_uses_canonical_json_keys_and_values(self) -> None:
        canonical = VariantSource(
            source_id="canonical-metadata",
            input_format="vcf",
            genome_build="GRCh38",
            payload=VCF,
            metadata={"nested": ("rna", {"replicate": 1})},
        )
        self.assertEqual(
            canonical.metadata,
            {"nested": ["rna", {"replicate": 1}]},
        )
        self.assertEqual(VariantSource.from_mapping(canonical.to_dict()), canonical)
        with self.assertRaisesRegex(TypeError, "canonical metadata is immutable"):
            canonical.metadata["added"] = True  # type: ignore[index]
        nested = canonical.metadata["nested"]
        assert isinstance(nested, list)
        nested_mapping = nested[1]
        assert isinstance(nested_mapping, dict)
        with self.assertRaisesRegex(TypeError, "canonical metadata is immutable"):
            nested_mapping["replicate"] = 2

        recursive: dict[str, object] = {}
        recursive["self"] = recursive
        invalid_metadata = (
            {7: "numeric key"},
            {"nested": {7: "numeric key"}},
            {"value": float("nan")},
            {"value": float("inf")},
            {"value": {"not", "json"}},
            recursive,
        )
        for metadata in invalid_metadata:
            with self.subTest(metadata=repr(metadata)[:40]), self.assertRaises(ValidationError):
                VariantSource(
                    source_id="invalid-metadata",
                    input_format="vcf",
                    genome_build="GRCh38",
                    payload=VCF,
                    metadata=metadata,  # type: ignore[arg-type]
                )

        for factory, raw in (
            (VariantSource.from_mapping, variant().to_dict()),
            (RegulatoryTrackSource.from_mapping, track().to_dict()),
        ):
            raw["metadata"] = None
            with self.assertRaisesRegex(ValidationError, "metadata must be an object"):
                factory(raw)

    def test_case_metadata_is_immutable_and_reserves_workflow_provenance(self) -> None:
        original_metadata = {"nested": {"purpose": "research"}}
        value = prepared(metadata=original_metadata)
        assert value.manifest is not None
        original_address = value.manifest.content_address
        original_run_id = value.run_id
        original_metadata["nested"]["purpose"] = "mutated-after-prepare"
        self.assertEqual(value.manifest.content_address, original_address)

        nested = value.manifest.metadata["nested"]
        assert isinstance(nested, dict)
        with self.assertRaisesRegex(TypeError, "canonical metadata is immutable"):
            nested["purpose"] = "mutated-through-result"
        self.assertEqual(value.manifest.content_address, original_address)
        self.assertEqual(value.run_id, original_run_id)

        with self.assertRaisesRegex(ValidationError, "reserved keys"):
            prepared(metadata={"case_workflow_provenance": {"forged": True}})

        metadata_schema = prepare_request_schema()["properties"]["metadata"]
        self.assertEqual(
            metadata_schema["propertyNames"],
            {"not": {"const": "case_workflow_provenance"}},
        )

    def test_manifest_nested_identity_maps_are_deeply_immutable(self) -> None:
        value = prepared()
        assert value.manifest is not None
        manifest = value.manifest
        identities = (manifest.content_address, value.run_id, value.content_address)

        variant = manifest.variants[0]
        candidate = manifest.candidate_elements[0]
        with self.assertRaisesRegex(TypeError, "canonical metadata is immutable"):
            variant.annotations["forged"] = True  # type: ignore[index]
        variant_info = variant.annotations["info"]
        assert isinstance(variant_info, dict)
        with self.assertRaisesRegex(TypeError, "canonical metadata is immutable"):
            variant_info["DP"] = "999"
        with self.assertRaisesRegex(TypeError, "canonical metadata is immutable"):
            candidate.features["track_score"] = 0.0  # type: ignore[index]
        candidate_attributes = candidate.annotations["track_attributes"]
        assert isinstance(candidate_attributes, dict)
        with self.assertRaisesRegex(TypeError, "canonical metadata is immutable"):
            candidate_attributes["Name"] = "FORGED"

        self.assertEqual(
            (manifest.content_address, value.run_id, value.content_address),
            identities,
        )

        restored = PreparedCase.from_mapping(value.to_dict())
        assert restored.manifest is not None
        with self.assertRaisesRegex(TypeError, "canonical metadata is immutable"):
            restored.manifest.variants[0].annotations["forged"] = True  # type: ignore[index]
        with self.assertRaisesRegex(TypeError, "canonical metadata is immutable"):
            restored.manifest.candidate_elements[0].features["track_score"] = 0.0  # type: ignore[index]

    def test_persisted_manifest_nested_fields_reject_scalar_coercion(self) -> None:
        serialized = prepared().to_dict()
        mutations = (
            ("variant coordinate", ("variants", 0, "start"), "100"),
            ("variant annotation", ("variants", 0, "annotations"), {"bad": float("inf")}),
            ("candidate coordinate", ("candidate_elements", 0, "start"), True),
            ("candidate feature", ("candidate_elements", 0, "features", "track_score"), True),
            ("candidate context", ("candidate_elements", 0, "context"), None),
            ("candidate genes", ("candidate_elements", 0, "target_genes"), "EGFR"),
        )
        for label, path, replacement in mutations:
            tampered = json.loads(json.dumps(serialized))
            target: object = tampered["manifest"]
            for part in path[:-1]:
                target = target[part]  # type: ignore[index]
            target[path[-1]] = replacement  # type: ignore[index]
            with self.subTest(label=label), self.assertRaises(ValidationError):
                PreparedCase.from_mapping(tampered)

    def test_persisted_candidate_features_accept_finite_integer_json_numbers(self) -> None:
        from glio_noncode.case_workflow import _candidate_element

        value = prepared()
        assert value.manifest is not None
        raw = value.manifest.candidate_elements[0].to_dict()
        raw["features"]["track_score"] = 1
        self.assertTrue(
            Draft202012Validator(
                prepared_case_schema()["properties"]["manifest"]["oneOf"][0]["properties"][
                    "candidate_elements"
                ]["items"]
            ).is_valid(raw)
        )
        hydrated = _candidate_element(raw, "candidate")
        self.assertIs(type(hydrated.features["track_score"]), int)
        self.assertEqual(hydrated.to_dict()["features"]["track_score"], 1)

    def test_persisted_receipts_and_issues_reject_scalar_coercion(self) -> None:
        serialized = prepared().to_dict()
        tampered = json.loads(json.dumps(serialized))
        tampered["stage_receipts"][0]["record_count"] = "1"
        with self.assertRaises(ValidationError):
            PreparedCase.from_mapping(tampered)

    def test_required_persisted_content_addresses_reject_null(self) -> None:
        prepared_mapping = prepared().to_dict()
        tampered = json.loads(json.dumps(prepared_mapping))
        tampered["content_address"] = None
        with self.assertRaises(ValidationError):
            PreparedCase.from_mapping(tampered)

        tampered = json.loads(json.dumps(prepared_mapping))
        tampered["stage_receipts"][0]["content_address"] = None
        with self.assertRaises(ValidationError):
            PreparedCase.from_mapping(tampered)

        with tempfile.TemporaryDirectory() as directory:
            run_mapping = run_case(prepared(), data_root=directory).to_dict()
        run_mapping["content_address"] = None
        with self.assertRaises(ValidationError):
            CaseRunResult.from_mapping(run_mapping)

    def test_run_bundle_cross_links_reject_readdressed_dossier(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            serialized = run_case(prepared(), data_root=directory).to_dict()
        dossier = serialized["dossier"]
        assert isinstance(dossier, dict)
        dossier["warnings"].append("readdressed-but-not-replayed")
        dossier_payload = {key: item for key, item in dossier.items() if key != "content_address"}
        dossier["content_address"] = content_hash(dossier_payload)
        with self.assertRaisesRegex(
            ValidationError,
            "run record dossier_address does not match",
        ):
            CaseRunResult.from_mapping(serialized)

    def test_dossier_identity_maps_are_frozen_and_revalidated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = run_case(prepared(), data_root=directory)
        assert result.dossier is not None
        payload = result.dossier.evidence[0].payload
        with self.assertRaisesRegex(TypeError, "canonical metadata is immutable"):
            payload["forged"] = True  # type: ignore[index]

        dict.__setitem__(payload, "forged", True)
        with self.assertRaisesRegex(
            ValidationError,
            "dossier content_address does not match its hydrated payload",
        ):
            _ = result.content_address

    def test_execution_revalidates_prepared_identity_after_base_method_mutation(self) -> None:
        value = prepared()
        assert value.manifest is not None
        dict.__setitem__(value.manifest.metadata, "forged", True)
        with (
            tempfile.TemporaryDirectory() as directory,
            self.assertRaisesRegex(
                ValidationError,
                "run_id does not match",
            ),
        ):
            run_case(value, data_root=directory)

    def test_persisted_dossier_rejects_typed_hydration_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            serialized = run_case(prepared(), data_root=directory).to_dict()
        dossier = serialized["dossier"]
        assert isinstance(dossier, dict)
        dossier["case_id"] = 7
        dossier_payload = {key: item for key, item in dossier.items() if key != "content_address"}
        dossier["content_address"] = content_hash(dossier_payload)
        with self.assertRaises(ValidationError):
            CaseRunResult.from_mapping(serialized)

        blocked = prepared(variant_source=variant(build="GRCh37")).to_dict()
        self.assertTrue(blocked["issues"])
        tampered = json.loads(json.dumps(blocked))
        tampered["issues"][0]["code"] = 7
        with self.assertRaises(ValidationError):
            PreparedCase.from_mapping(tampered)

    def test_persisted_manifest_hydration_rejects_coercion_and_freezes_identity(self) -> None:
        value = prepared(metadata={"nested": {"purpose": "rehydration"}})
        serialized = value.to_dict()
        restored = PreparedCase.from_mapping(serialized)
        self.assertEqual(restored.to_dict(), serialized)
        assert restored.manifest is not None
        identities = (
            restored.manifest.content_address,
            restored.run_id,
            restored.content_address,
        )
        with self.assertRaisesRegex(TypeError, "canonical metadata is immutable"):
            restored.manifest.metadata["added"] = True  # type: ignore[index]
        nested = restored.manifest.metadata["nested"]
        assert isinstance(nested, dict)
        with self.assertRaisesRegex(TypeError, "canonical metadata is immutable"):
            nested["purpose"] = "mutated"
        with self.assertRaisesRegex(TypeError, "canonical metadata is immutable"):
            restored.manifest.input_versions["forged"] = "sha256:forged"  # type: ignore[index]
        self.assertEqual(
            (
                restored.manifest.content_address,
                restored.run_id,
                restored.content_address,
            ),
            identities,
        )

        tampered_values = []
        tampered = json.loads(json.dumps(serialized))
        tampered["manifest"]["context"]["disease_class"] = 7
        tampered_values.append(tampered)
        tampered = json.loads(json.dumps(serialized))
        tampered["manifest"]["input_versions"]["fixture-variants"] = 7
        tampered_values.append(tampered)
        tampered = json.loads(json.dumps(serialized))
        tampered["manifest"]["case_id"] = 7
        tampered_values.append(tampered)
        for tampered in tampered_values:
            with self.subTest(tampered=tampered["manifest"]), self.assertRaises(ValidationError):
                PreparedCase.from_mapping(tampered)

        with tempfile.TemporaryDirectory() as directory:
            result_mapping = run_case(value, data_root=directory).to_dict()
        result_mapping["prepared"]["manifest"]["context"]["age_group"] = None
        with self.assertRaises(ValidationError):
            CaseRunResult.from_mapping(result_mapping)

    def test_persisted_output_schemas_validate_real_accepted_and_blocked_artifacts(self) -> None:
        prepared_schema = prepared_case_schema()
        result_schema = run_result_schema()
        for schema in (
            prepared_schema,
            result_schema,
            run_request_schema(),
            case_workflow_schema(),
        ):
            with self.subTest(schema=schema["$id"]):
                Draft202012Validator.check_schema(schema)

        accepted_prepared = prepared()
        blocked_prepared = prepared(variant_source=variant(build="GRCh37"))
        prepared_validator = Draft202012Validator(prepared_schema)
        for value in (accepted_prepared, blocked_prepared):
            with self.subTest(prepared_state=value.state):
                self.assertTrue(
                    prepared_validator.is_valid(value.to_dict()),
                    list(prepared_validator.iter_errors(value.to_dict())),
                )

        with tempfile.TemporaryDirectory() as directory:
            accepted_result = run_case(accepted_prepared, data_root=directory)
        with tempfile.TemporaryDirectory() as directory:
            blocked_result = run_case(blocked_prepared, data_root=directory)
        result_validator = Draft202012Validator(result_schema)
        for value in (accepted_result, blocked_result):
            with self.subTest(run_state=value.state):
                self.assertTrue(
                    result_validator.is_valid(value.to_dict()),
                    list(result_validator.iter_errors(value.to_dict())),
                )

        run_request = {"prepared": accepted_prepared.to_dict()}
        self.assertTrue(Draft202012Validator(run_request_schema()).is_valid(run_request))
        self.assertTrue(Draft202012Validator(case_workflow_schema()).is_valid(run_request))

    def test_prepared_schema_rejects_nested_runtime_invalid_values(self) -> None:
        validator = Draft202012Validator(prepared_case_schema())
        accepted = prepared().to_dict()

        def replaced(path: tuple[str | int, ...], value: object) -> dict[str, object]:
            result = json.loads(json.dumps(accepted))
            target: object = result
            for part in path[:-1]:
                target = target[part]  # type: ignore[index]
            target[path[-1]] = value  # type: ignore[index]
            return result

        malformed = (
            (
                "partial persisted context",
                ("manifest", "context"),
                {
                    "genome_build": "GRCh38",
                    "disease_class": "diffuse_glioma",
                    "age_group": "adult",
                    "cell_state": "stem_like",
                },
            ),
            ("variant coordinate", ("manifest", "variants", 0, "start"), "100"),
            ("candidate coordinate", ("manifest", "candidate_elements", 0, "start"), True),
            (
                "candidate feature",
                ("manifest", "candidate_elements", 0, "features", "track_score"),
                "0.8",
            ),
            ("negative receipt count", ("stage_receipts", 0, "record_count"), -1),
            ("inconsistent state flag", ("accepted",), False),
            ("invalid manifest address", ("manifest_address",), "sha256:not-an-address"),
        )
        for label, path, replacement in malformed:
            tampered = replaced(path, replacement)
            with self.subTest(label=label):
                self.assertFalse(validator.is_valid(tampered))
                with self.assertRaises(ValidationError):
                    PreparedCase.from_mapping(tampered)

        no_element_target = replaced(
            ("manifest", "candidate_elements", 0, "target_genes"),
            [],
        )
        no_element_target["manifest"]["candidate_elements"][0]["state_ids"] = []  # type: ignore[index]
        self.assertFalse(validator.is_valid(no_element_target))
        with self.assertRaises(ValidationError):
            PreparedCase.from_mapping(no_element_target)

        blocked = prepared(variant_source=variant(build="GRCh37")).to_dict()
        malformed_issue = json.loads(json.dumps(blocked))
        malformed_issue["issues"][0]["line_number"] = "1"
        self.assertFalse(validator.is_valid(malformed_issue))
        with self.assertRaises(ValidationError):
            PreparedCase.from_mapping(malformed_issue)

        executable_blocked = json.loads(json.dumps(blocked))
        executable_blocked["manifest"] = accepted["manifest"]
        executable_blocked["manifest_address"] = accepted["manifest_address"]
        executable_blocked["run_id"] = accepted["run_id"]
        self.assertFalse(validator.is_valid(executable_blocked))
        with self.assertRaises(ValidationError):
            PreparedCase.from_mapping(executable_blocked)

        manifest_schema = prepared_case_schema()["properties"]["manifest"]["oneOf"][0]
        self.assertEqual(
            manifest_schema["properties"]["variants"]["maxItems"],
            MAX_VARIANT_INTAKE_RECORDS,
        )
        self.assertEqual(
            manifest_schema["properties"]["candidate_elements"]["maxItems"],
            MAX_CASE_CANDIDATE_ELEMENTS,
        )

    def test_run_result_schema_rejects_malformed_nested_bundle_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            accepted = run_case(prepared(), data_root=directory).to_dict()
        validator = Draft202012Validator(run_result_schema())

        def replaced(path: tuple[str | int, ...], value: object) -> dict[str, object]:
            result = json.loads(json.dumps(accepted))
            target: object = result
            for part in path[:-1]:
                target = target[part]  # type: ignore[index]
            target[path[-1]] = value  # type: ignore[index]
            return result

        malformed = (
            ("empty event history", ("run_record", "event_history"), []),
            ("typed replay flag", ("replay_report", "event_chain_valid"), "true"),
            ("failed accepted replay", ("replay_report", "event_chain_valid"), False),
            ("non-array dossier warnings", ("dossier", "warnings"), "not-an-array"),
            ("inconsistent run flag", ("blocked",), True),
            (
                "malformed runtime receipt",
                ("stage_receipts", -1, "output_address"),
                "not-an-address",
            ),
        )
        for label, path, replacement in malformed:
            tampered = replaced(path, replacement)
            with self.subTest(label=label):
                self.assertFalse(validator.is_valid(tampered))
                with self.assertRaises(ValidationError):
                    CaseRunResult.from_mapping(tampered)

        extra_dossier_field = json.loads(json.dumps(accepted))
        extra_dossier_field["dossier"]["unexpected"] = True
        self.assertFalse(validator.is_valid(extra_dossier_field))
        with self.assertRaises(ValidationError):
            CaseRunResult.from_mapping(extra_dossier_field)

        malformed_dossier_child = replaced(("dossier", "hypotheses", 0), "not-an-object")
        self.assertFalse(validator.is_valid(malformed_dossier_child))

        duplicate_runtime_receipt = json.loads(json.dumps(accepted))
        duplicate_runtime_receipt["stage_receipts"].append(
            duplicate_runtime_receipt["stage_receipts"][-1]
        )
        self.assertFalse(validator.is_valid(duplicate_runtime_receipt))
        with self.assertRaises(ValidationError):
            CaseRunResult.from_mapping(duplicate_runtime_receipt)

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
        self.assertFalse(schema["unevaluatedProperties"])
        self.assertEqual(
            schema["oneOf"],
            [
                {"$ref": "#/$defs/prepare_request"},
                {"$ref": "#/$defs/run_request"},
            ],
        )
        self.assertFalse(schema["$defs"]["variant_source"]["additionalProperties"])
        self.assertFalse(advertised["server_local_paths"])
        self.assertIn("inline_bytes", advertised["source_transport"])
        self.assertIn("manifest_address", advertised["deterministic_outputs"])
        self.assertIn("effective_manifest_address", advertised["deterministic_outputs"])
        self.assertEqual(
            advertised["runtime_work_limits"]["max_adapter_ids"],
            ADAPTER_HARD_MAX_SELECTED,
        )
        self.assertEqual(
            advertised["runtime_work_limits"]["hard_max_adapter_ids"],
            ADAPTER_HARD_MAX_SELECTED,
        )
        self.assertEqual(
            advertised["runtime_work_limits"]["default_registry_max_adapter_ids"],
            AdapterLimits().max_selected_adapters,
        )
        adapter_contract = advertised["optional_execution_inputs"]["adapter_ids"]
        self.assertEqual(adapter_contract["max_items"], ADAPTER_HARD_MAX_SELECTED)
        self.assertEqual(adapter_contract["hard_max_items"], ADAPTER_HARD_MAX_SELECTED)
        self.assertEqual(
            adapter_contract["default_registry_max_items"],
            AdapterLimits().max_selected_adapters,
        )
        self.assertEqual(adapter_contract["execution_registry_scope"], "selected_execution")
        self.assertEqual(
            adapter_contract["persisted_source_records"],
            [
                "adapter_input_manifest",
                "adapter_registry_snapshot",
                "adapter_resolution_report",
                "adapter_claim_collection_report",
            ],
        )
        self.assertEqual(
            advertised["preparation_inputs"]["regulatory_tracks"]["max_items"],
            MAX_CASE_REGULATORY_TRACKS,
        )
        self.assertEqual(
            advertised["preparation_inputs"]["regulatory_tracks"]["max_target_gene_keys_per_track"],
            MAX_CASE_TARGET_GENE_KEYS,
        )
        self.assertEqual(
            advertised["preparation_inputs"]["regulatory_tracks"]["max_target_gene_key_length"],
            MAX_CASE_TARGET_GENE_KEY_LENGTH,
        )
        self.assertEqual(
            advertised["preparation_inputs"]["regulatory_tracks"][
                "max_candidate_elements_per_case"
            ],
            MAX_CASE_CANDIDATE_ELEMENTS,
        )
        self.assertEqual(
            advertised["preparation_inputs"]["variant_source"],
            {
                "max_records": MAX_VARIANT_INTAKE_RECORDS,
                "max_auxiliary_lines": MAX_VARIANT_INTAKE_AUXILIARY_LINES,
            },
        )

        relations = run_result_schema()["x-runtime-relations"]
        self.assertTrue(
            any(
                "runtime receipt input_address binds prepared.manifest_address" in relation
                for relation in relations
            )
        )
        self.assertTrue(
            any(
                "blocked pre-execution outcome" in relation
                and "binds prepared.content_address" in relation
                for relation in relations
            )
        )
        self.assertTrue(
            any(
                "for accepted executions" in relation
                and "when present" in relation
                and "effective evaluation identity" in relation
                for relation in relations
            )
        )
        self.assertTrue(
            any(
                "dossier.input_address, run_record.input_address, and "
                "replay_report.input_address" in relation
                and "effective_manifest_address" in relation
                for relation in relations
            )
        )

    def test_request_schemas_compose_canonical_bounded_inputs(self) -> None:
        prepare_schema = prepare_request_schema()
        run_schema = run_request_schema()
        workflow = case_workflow_schema()
        advertised = capabilities()

        self.assertFalse(prepare_schema["additionalProperties"])
        self.assertEqual(
            set(prepare_schema["required"]),
            {"case_id", "subject_id", "context", "variant_source"},
        )
        prepare_properties = prepare_schema["properties"]
        self.assertNotIn("tracks", prepare_properties)
        self.assertNotIn("data_root", prepare_properties)
        self.assertEqual(
            prepare_properties["regulatory_tracks"]["maxItems"],
            MAX_CASE_REGULATORY_TRACKS,
        )
        self.assertEqual(
            prepare_properties["regulatory_tracks"]["x-parser-limits"],
            {
                "max_records_per_track": MAX_REGULATORY_TRACK_RECORDS,
                "max_auxiliary_lines_per_track": MAX_REGULATORY_TRACK_AUXILIARY_LINES,
                "max_candidate_elements_per_case": MAX_CASE_CANDIDATE_ELEMENTS,
            },
        )
        self.assertFalse(prepare_properties["variant_source"]["additionalProperties"])
        self.assertNotIn("$id", prepare_properties["variant_source"])
        self.assertEqual(
            variant_source_schema()["x-parser-limits"],
            {
                "max_records": MAX_VARIANT_INTAKE_RECORDS,
                "max_auxiliary_lines": MAX_VARIANT_INTAKE_AUXILIARY_LINES,
            },
        )
        self.assertEqual(
            prepare_properties["variant_source"]["x-parser-limits"],
            variant_source_schema()["x-parser-limits"],
        )
        self.assertFalse(prepare_properties["regulatory_tracks"]["items"]["additionalProperties"])
        self.assertNotIn("$id", prepare_properties["regulatory_tracks"]["items"])
        self.assertEqual(
            set(prepare_properties["context"]["required"]),
            {"genome_build", "disease_class", "age_group", "cell_state"},
        )
        context_properties = regulatory_track_source_schema()["properties"]["context"]["properties"]
        self.assertTrue(context_properties["assay_support"]["uniqueItems"])
        self.assertEqual(context_properties["territory"]["default"], "unknown")
        self.assertEqual(
            regulatory_track_source_schema()["properties"]["target_gene_keys"]["default"],
            ["gene", "gene_id", "gene_name", "target_gene"],
        )
        self.assertEqual(
            regulatory_track_source_schema()["properties"]["target_gene_keys"]["maxItems"],
            MAX_CASE_TARGET_GENE_KEYS,
        )
        self.assertEqual(
            regulatory_track_source_schema()["properties"]["target_gene_keys"]["items"][
                "maxLength"
            ],
            MAX_CASE_TARGET_GENE_KEY_LENGTH,
        )

        self.assertFalse(run_schema["additionalProperties"])
        self.assertEqual(run_schema["required"], ["prepared"])
        self.assertEqual(
            set(run_schema["properties"]),
            {"prepared", "rna_consequences", "adapter_ids"},
        )
        self.assertNotIn("$id", run_schema["properties"]["prepared"])
        self.assertNotIn("$id", run_schema["properties"]["rna_consequences"])
        self.assertEqual(
            run_schema["properties"]["rna_consequences"]["maxItems"],
            MAX_CASE_RNA_CONSEQUENCES,
        )
        self.assertTrue(run_schema["properties"]["rna_consequences"]["uniqueItems"])
        self.assertEqual(
            run_schema["properties"]["adapter_ids"]["maxItems"],
            capabilities()["optional_execution_inputs"]["adapter_ids"]["max_items"],
        )
        self.assertTrue(run_schema["properties"]["adapter_ids"]["uniqueItems"])
        self.assertIn("invalid_adapter_selection", advertised["fail_closed_gates"])
        self.assertNotIn("data_root", run_schema["properties"])

        self.assertEqual(workflow["$defs"]["prepare_request"], prepare_schema)
        self.assertEqual(workflow["$defs"]["run_request"], run_schema)
        schema_ids: list[str] = []

        def collect_schema_ids(value: object) -> None:
            if isinstance(value, dict):
                identifier = value.get("$id")
                if isinstance(identifier, str):
                    schema_ids.append(identifier)
                for child in value.values():
                    collect_schema_ids(child)
            elif isinstance(value, list):
                for child in value:
                    collect_schema_ids(child)

        collect_schema_ids(workflow)
        self.assertEqual(len(schema_ids), len(set(schema_ids)))
        self.assertEqual(advertised["schemas"]["prepare_request"], prepare_schema["$id"])
        self.assertEqual(advertised["schemas"]["run_request"], run_schema["$id"])
        self.assertEqual(
            advertised["preparation_inputs"]["regulatory_tracks"]["max_records_per_track"],
            MAX_REGULATORY_TRACK_RECORDS,
        )
        self.assertEqual(
            advertised["preparation_inputs"]["regulatory_tracks"]["max_auxiliary_lines_per_track"],
            MAX_REGULATORY_TRACK_AUXILIARY_LINES,
        )


if __name__ == "__main__":
    unittest.main()
