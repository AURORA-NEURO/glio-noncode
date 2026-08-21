from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main

CONTEXT = "GRCh38|glioma|adult|stem_like|core|untreated"


class FrontierContextAlphaCliTests(unittest.TestCase):
    def test_cell_state_ood_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "cell-ood.json"
            source.write_text(
                json.dumps(
                    {
                        "context_key": CONTEXT,
                        "records": [
                            {"cell_id": "cell-1", "distance": 0.5, "support_score": 0.9},
                            {"cell_id": "cell-2", "distance": 4.5, "support_score": 0.2},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            output = root / "output.json"
            self.assertEqual(
                main(["detect-cell-state-ood", str(source), "--output", str(output)]), 0
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["in_domain_ids"], ["cell-1"])
            self.assertEqual(payload["ood_ids"], ["cell-2"])

    def test_atlas_snapshot_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "snapshot.json"
            source.write_text(
                json.dumps(
                    {
                        "context_key": CONTEXT,
                        "snapshot_id": "snapshot-1",
                        "atlas_type": "insulator",
                        "version": "v1",
                        "records": [{"id": "b-1", "context_key": CONTEXT}],
                    }
                ),
                encoding="utf-8",
            )
            output = root / "output.json"
            self.assertEqual(
                main(["publish-atlas-snapshot", str(source), "--output", str(output)]), 0
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "published")
            self.assertTrue(payload["snapshot_address"].startswith("sha256:"))


if __name__ == "__main__":
    unittest.main()
