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
