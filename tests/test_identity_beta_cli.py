from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main


class IdentityBetaCliTests(unittest.TestCase):
    def _run(
        self,
        root: Path,
        name: str,
        payload: dict[str, object],
        *args: str,
    ) -> dict[str, object]:
        source = root / f"{name}.json"
        output = root / f"{name}-output.json"
        source.write_text(json.dumps(payload), encoding="utf-8")
        self.assertEqual(main([*args, str(source), "--output", str(output)]), 0)
        return json.loads(output.read_text(encoding="utf-8"))

    def _record(self, record_id: str, variant_id: str, alias: str) -> dict[str, object]:
        return {
            "record_id": record_id,
            "variant_id": variant_id,
            "kind": "snv",
            "chromosome": "chr7",
            "start": 100,
            "end": 100,
            "reference": "A",
            "alternate": "T",
            "genome_build": "GRCh38",
            "source_id": "source-1",
            "source_version": "v1",
            "aliases": [alias],
        }

    def test_equivalence_reconciliation_and_sample_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            equivalence = self._run(
                root,
                "equivalence",
                {"records": [self._record("r1", "v1", "legacy-v1")]},
                "resolve-variant-equivalence",
                "--query",
                "legacy-v1",
            )
            self.assertEqual(equivalence["state"], "supported")
            self.assertEqual(equivalence["record_ids"], ["r1"])

            reconciliation = self._run(
                root,
                "reconciliation",
                {
                    "records": [
                        self._record("r1", "v1", "legacy-v1"),
                        self._record("r2", "v1-copy", "legacy-v1"),
                    ]
                },
                "reconcile-variant-aliases",
            )
            self.assertEqual(reconciliation["state"], "partial")
            self.assertEqual(reconciliation["duplicate_record_ids"], ["r1", "r2"])

            sample = self._run(
                root,
                "sample",
                {
                    "observations": [
                        {
                            "observation_id": "o1",
                            "batch_id": "b1",
                            "sample_id": "s1",
                            "subject_id": "subject-1",
                            "source_id": "source",
                            "source_version": "v1",
                            "raw_hash": "sha256:o1",
                        }
                    ]
                },
                "check-batch-sample-identity",
                "--require-subject",
            )
            self.assertEqual(sample["state"], "supported")

    def test_custody_command_emits_chain_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            custody = self._run(
                root,
                "custody",
                {
                    "events": [
                        {
                            "event_id": "e1",
                            "artifact_id": "a1",
                            "event_kind": "received",
                            "actor_id": "operator",
                            "occurred_at": "2026-08-21T00:00:00+00:00",
                            "output_hashes": ["sha256:raw"],
                            "source_id": "source",
                        },
                        {
                            "event_id": "e2",
                            "artifact_id": "a1",
                            "event_kind": "transformed",
                            "actor_id": "pipeline",
                            "occurred_at": "2026-08-21T00:01:00+00:00",
                            "input_hashes": ["sha256:raw"],
                            "output_hashes": ["sha256:normalized"],
                            "source_id": "source",
                            "previous_event_id": "e1",
                        },
                    ]
                },
                "capture-chain-of-custody",
            )
            self.assertEqual(custody["state"], "supported")
            self.assertEqual(custody["chains"][0]["event_ids"], ["e1", "e2"])
            self.assertTrue(custody["chains"][0]["chain_digest"])


if __name__ == "__main__":
    unittest.main()
