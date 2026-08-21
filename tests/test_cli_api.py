from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.cli import main

from .helpers import ROOT


class CliApiTests(unittest.TestCase):
    def test_schema_command_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "schema.json"
            self.assertEqual(main(["schema", "--output", str(output)]), 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertIn("$defs", payload)

    def test_intake_command_writes_canonical_batch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "variants.tsv"
            output = Path(directory) / "intake.json"
            source.write_text(
                "chrom\tpos\tref\talt\nchr7\t10\tA\tT\n",
                encoding="utf-8",
            )
            self.assertEqual(
                main(
                    [
                        "intake",
                        str(source),
                        "--source-id",
                        "test-tsv",
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["receipt"]["accepted_count"], 1)
            self.assertEqual(payload["variants"][0]["variant_id"], "test-tsv:2")

    def test_capability_track_and_normalize_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            track = Path(directory) / "track.bed"
            track_output = Path(directory) / "track.json"
            normalize_output = Path(directory) / "normalize.json"
            track.write_text("7\t99\t120\treg-1\t800\t+\n", encoding="utf-8")
            self.assertEqual(
                main(["parse-track", str(track), "--output", str(track_output)]),
                0,
            )
            track_payload = json.loads(track_output.read_text(encoding="utf-8"))
            self.assertEqual(track_payload["features"][0]["start"], 100)
            self.assertEqual(
                main(["normalize", "7:100:A>T", "--output", str(normalize_output)]),
                0,
            )
            normalize_payload = json.loads(normalize_output.read_text(encoding="utf-8"))
            self.assertEqual(normalize_payload["state"], "supported")

    def test_structural_extension_commands_write_reconciled_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            sv_source = Path(directory) / "calls.tsv"
            sv_output = Path(directory) / "calls.json"
            cn_source = Path(directory) / "segments.tsv"
            cn_output = Path(directory) / "segments.json"
            sv_source.write_text(
                "caller_id\tevent_id\tchrom\tstart\tend\tsvtype\tsupport\n"
                "a\ta1\t7\t100\t200\tDEL\t1\n"
                "b\tb1\t7\t102\t201\tDEL\t1\n",
                encoding="utf-8",
            )
            cn_source.write_text(
                "caller_id\tsegment_id\tchrom\tstart\tend\tcopy_number\n"
                "a\ta1\t7\t1\t100\t2\n"
                "b\tb1\t7\t1\t100\t2\n",
                encoding="utf-8",
            )
            self.assertEqual(
                main(["sv-consensus", str(sv_source), "--output", str(sv_output)]), 0
            )
            self.assertEqual(
                main(["harmonize-cn", str(cn_source), "--output", str(cn_output)]), 0
            )
            self.assertEqual(
                json.loads(sv_output.read_text(encoding="utf-8"))["consensus"][0]["state"],
                "supported",
            )
            self.assertEqual(
                json.loads(cn_output.read_text(encoding="utf-8"))["segments"][0]["state"],
                "supported",
            )

    def test_purity_ploidy_command_preserves_measurement_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "purity.tsv"
            output = Path(directory) / "purity.json"
            source.write_text(
                "sample_id\tcaller_id\tpurity\tploidy\n"
                "tumor-1\tcaller-a\t70\t2.3\n",
                encoding="utf-8",
            )
            self.assertEqual(
                main(["purity-ploidy", str(source), "--output", str(output)]), 0
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["records"][0]["purity"], 0.7)

    def test_parse_ccre_command_writes_track_batch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "ccre.tsv"
            output = Path(directory) / "ccre.json"
            source.write_text(
                "chrom\tstart\tend\tccre_id\tregistry_class\n"
                "7\t99\t120\tEH38E1\tenhancer\n",
                encoding="utf-8",
            )
            self.assertEqual(
                main(["parse-ccre", str(source), "--output", str(output)]), 0
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["records"][0]["ccre_id"], "EH38E1")

    def test_parse_chromatin_command_writes_context_track_batch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "atac.tsv"
            output = Path(directory) / "atac.json"
            source.write_text(
                "chrom\tstart\tend\ttrack_id\tsignal\tcontext\n"
                "7\t99\t120\tatac-1\t4.5\tGRCh38|glioma|adult|stem_like|unknown|unknown\n",
                encoding="utf-8",
            )
            self.assertEqual(
                main(
                    [
                        "parse-chromatin",
                        str(source),
                        "--track-kind",
                        "atac",
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["observations"][0]["track_kind"], "atac")
            self.assertEqual(payload["observations"][0]["start"], 100)

    def test_parse_context_command_writes_observation_batch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "context.tsv"
            output = Path(directory) / "context.json"
            source.write_text(
                "subject_id\tdimension\tcandidate_id\tcandidate_label\tcontext_key\n"
                "case-1\tdisease_ontology\tMONDO:001\tglioma\t"
                "GRCh38|glioma|adult|stem_like|unknown|unknown\n",
                encoding="utf-8",
            )
            self.assertEqual(
                main(["parse-context", str(source), "--output", str(output)]), 0
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["observations"][0]["candidate_id"], "MONDO:001")

    def test_parse_topology_commands_write_source_accounted_batches(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            contacts = Path(directory) / "contacts.tsv"
            contacts_output = Path(directory) / "contacts.json"
            boundaries = Path(directory) / "boundaries.tsv"
            boundaries_output = Path(directory) / "boundaries.json"
            contacts.write_text(
                "chrom1\tstart1\tend1\tchrom2\tstart2\tend2\tcount\tcontext\n"
                "7\t99\t120\t7\t299\t320\t10\tGRCh38|glioma|adult|stem_like|unknown|unknown\n",
                encoding="utf-8",
            )
            boundaries.write_text(
                "boundary_id\tchromosome\tposition\tscore\tcontext\n"
                "b1\t7\t1000\t0.8\tGRCh38|glioma|adult|stem_like|unknown|unknown\n",
                encoding="utf-8",
            )
            self.assertEqual(
                main(
                    [
                        "parse-contacts",
                        str(contacts),
                        "--assay",
                        "hi-c",
                        "--output",
                        str(contacts_output),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "parse-boundaries",
                        str(boundaries),
                        "--assay",
                        "micro-c",
                        "--output",
                        str(boundaries_output),
                    ]
                ),
                0,
            )
            self.assertEqual(
                json.loads(contacts_output.read_text(encoding="utf-8"))["records"][0]["start_a"],
                100,
            )
            self.assertEqual(
                json.loads(boundaries_output.read_text(encoding="utf-8"))["observations"][0]["assay"],
                "micro-c",
            )

    def test_parse_genes_command_writes_link_baseline_batch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "genes.tsv"
            output = Path(directory) / "genes.json"
            source.write_text(
                "gene_id\tsymbol\tchromosome\tstart\tend\tcontext\n"
                "g1\tGENE1\t7\t199\t300\tGRCh38|glioma|adult|stem_like|unknown|unknown\n",
                encoding="utf-8",
            )
            self.assertEqual(
                main(["parse-genes", str(source), "--output", str(output)]), 0
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["genes"][0]["gene_id"], "g1")
            self.assertEqual(payload["genes"][0]["start"], 200)

    def test_factor_graph_command_writes_replayable_graph(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "factors.json"
            output = Path(directory) / "graph.json"
            source.write_text(
                json.dumps(
                    {
                        "factors": [
                            {
                                "factor_id": "f1",
                                "edge_id": "edge-1",
                                "factor_type": "link",
                                "source_id": "source-1",
                                "source_version": "v1",
                                "state": "supported",
                                "support": 0.8,
                                "uncertainty": 0.2,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                main(
                    [
                        "factor-graph",
                        str(source),
                        "--context-key",
                        "GRCh38|glioma|adult|stem_like|unknown|unknown",
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "supported")
            self.assertEqual(payload["active_factor_ids"], ["f1"])

    def test_evidence_lifecycle_commands_write_quarantine_and_dossier_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            citations = Path(directory) / "citations.tsv"
            citation_output = Path(directory) / "citations.json"
            graph_input = Path(directory) / "graph.json"
            dossier_output = Path(directory) / "dossier.json"
            citations.write_text(
                "citation_id\tsource_uri\ttitle\tversion\tcitation_text\n"
                "c1\thttps://example.test/1\tOne\tv1\tOne citation\n",
                encoding="utf-8",
            )
            self.assertEqual(
                main(
                    [
                        "parse-citations",
                        str(citations),
                        "--source-id",
                        "source-1",
                        "--source-version",
                        "v1",
                        "--output",
                        str(citation_output),
                    ]
                ),
                0,
            )
            self.assertEqual(
                json.loads(citation_output.read_text(encoding="utf-8"))["state"], "supported"
            )
            graph_input.write_text(
                json.dumps(
                    {
                        "citations": [
                            {
                                "citation_id": "c1",
                                "source_id": "source-1",
                                "source_uri": "https://example.test/1",
                                "title": "One",
                                "version": "v1",
                                "citation_text": "One citation",
                                "retrieved_at": "2026-08-20T00:00:00+00:00",
                            }
                        ],
                        "claims": [
                            {
                                "claim_id": "claim-1",
                                "edge_id": "edge-1",
                                "source_ids": ["source-1"],
                                "state": "supported",
                                "support": 0.8,
                                "confidence": 0.9,
                                "claim_type": "functional",
                                "summary": "A bounded research claim",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                main(
                    [
                        "evidence-graph",
                        str(graph_input),
                        "--context-key",
                        "GRCh38|glioma|adult|stem_like|unknown|unknown",
                        "--output",
                        str(dossier_output),
                    ]
                ),
                0,
            )
            dossier = json.loads(dossier_output.read_text(encoding="utf-8"))
            self.assertEqual(dossier["release_state"], "review_required")
            self.assertTrue(dossier["integrity_digest"].startswith("sha256:"))

    def test_workspace_commands_write_case_and_track_views(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.json"
            track = Path(directory) / "track.bed"
            manifest_output = Path(directory) / "workspace.json"
            track_output = Path(directory) / "track-workspace.json"
            manifest.write_text(
                json.dumps(
                    {
                        "case_id": "case-cli",
                        "subject_id": "subject-cli",
                        "context": {
                            "genome_build": "GRCh38",
                            "disease_class": "glioma",
                            "age_group": "adult",
                            "cell_state": "stem_like",
                        },
                        "variants": [
                            {
                                "variant_id": "v1",
                                "kind": "snv",
                                "chromosome": "7",
                                "start": 100,
                                "end": 100,
                                "reference": "A",
                                "alternate": "T",
                                "genome_build": "GRCh38",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            track.write_text("7\t99\t120\treg-1\t800\t+\n", encoding="utf-8")
            self.assertEqual(
                main(["workspace-case", str(manifest), "--output", str(manifest_output)]), 0
            )
            self.assertEqual(
                main(
                    [
                        "workspace-track",
                        str(track),
                        "--context-key",
                        "GRCh38|glioma|adult|stem_like|unknown|unknown",
                        "--output",
                        str(track_output),
                    ]
                ),
                0,
            )
            self.assertEqual(
                json.loads(manifest_output.read_text(encoding="utf-8"))["kind"], "case"
            )
            self.assertEqual(
                len(json.loads(track_output.read_text(encoding="utf-8"))["records"]), 1
            )

    def test_mission_plan_command_writes_dependency_safe_plan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "mission.json"
            output = Path(directory) / "mission-plan.json"
            source.write_text(
                json.dumps(
                    {
                        "mission": {
                            "mission_id": "mission-cli",
                            "project_id": "glio-noncode",
                            "intended_use": "research hypothesis exploration",
                            "requested_question": "Which observations require review?",
                        },
                        "requested_agent_ids": ["A02"],
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(main(["mission-plan", str(source), "--output", str(output)]), 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertIn("A01", payload["selected_agent_ids"])
            self.assertEqual(payload["workflow"]["steps"][0]["step_id"], "ingest")

    def test_cohort_query_command_writes_context_selection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "cohort.json"
            output = Path(directory) / "query.json"
            context = {
                "genome_build": "GRCh38",
                "disease_class": "glioma",
                "age_group": "adult",
                "cell_state": "stem_like",
                "territory": "unknown",
                "treatment_phase": "unknown",
            }
            source.write_text(
                json.dumps(
                    {
                        "context": context,
                        "query": {"query_id": "q1", "variant_kinds": ["snv"]},
                        "records": [
                            {
                                "record_id": "r1",
                                "variant": {
                                    "variant_id": "v1",
                                    "kind": "snv",
                                    "chromosome": "chr7",
                                    "start": 100,
                                    "end": 100,
                                    "reference": "A",
                                    "alternate": "T",
                                    "genome_build": "GRCh38",
                                    "origin": "somatic",
                                },
                                "source_id": "cohort",
                                "sample_id": "s1",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                main(["cohort-query", str(source), "--output", str(output)]), 0
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "supported")
            self.assertEqual(payload["variant_ids"], ["v1"])

    def test_sequence_adapter_commands_write_typed_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            sequence_output = Path(directory) / "sequence.json"
            effects = Path(directory) / "effects.tsv"
            effect_output = Path(directory) / "effects.json"
            self.assertEqual(
                main(
                    [
                        "encode-sequence",
                        "ACGTACGT",
                        "--sequence-id",
                        "window-1",
                        "--output",
                        str(sequence_output),
                    ]
                ),
                0,
            )
            effects.write_text(
                "model_id\tmodel_version\tvariant_id\tref_score\talt_score\tcontext_length\n"
                "model-a\t1\tv1\t0.2\t0.8\t512\n",
                encoding="utf-8",
            )
            self.assertEqual(
                main(["parse-effect", str(effects), "--output", str(effect_output)]), 0
            )
            self.assertEqual(
                json.loads(sequence_output.read_text(encoding="utf-8"))["length"],
                8,
            )
            self.assertEqual(
                len(json.loads(effect_output.read_text(encoding="utf-8"))["observations"]),
                1,
            )

    def test_health_and_evaluate_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=5)
                connection.request("GET", "/healthz")
                health = connection.getresponse()
                self.assertEqual(health.status, 200)
                self.assertEqual(json.loads(health.read())["status"], "ok")
                manifest = (ROOT / "examples" / "case-small.json").read_bytes()
                connection.request(
                    "POST",
                    "/v1/evaluate",
                    body=manifest,
                    headers={"Content-Type": "application/json"},
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                dossier = json.loads(response.read())
                self.assertEqual(dossier["case_id"], "case-demo-001")
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)
