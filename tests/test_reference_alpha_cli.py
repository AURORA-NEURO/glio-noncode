from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main


class ReferenceAlphaCliTests(unittest.TestCase):
    def _write(self, root: Path, name: str, payload: object) -> Path:
        path = root / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_gene_alias_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            query = self._write(root, "queries.json", {"queries": [{"query": "EGFR"}]})
            catalog = self._write(
                root,
                "catalog.json",
                {"records": [{"gene_id": "EGFR", "symbol": "EGFR", "assembly": "GRCh38"}]},
            )
            output = root / "out.json"
            self.assertEqual(
                main(
                    [
                        "resolve-gene-alias",
                        str(query),
                        "--catalog",
                        str(catalog),
                        "--assembly",
                        "GRCh38",
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "supported")
            self.assertEqual(payload["resolutions"][0]["matches"][0]["symbol"], "EGFR")

    def test_population_frequency_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "frequencies.json",
                {
                    "records": [
                        {
                            "variant_id": "v1",
                            "population": "EUR",
                            "AC": 1,
                            "AN": 50,
                            "genome_build": "GRCh38",
                        }
                    ]
                },
            )
            output = root / "out.json"
            self.assertEqual(
                main(
                    [
                        "adapt-population-frequency",
                        str(source),
                        "--genome-build",
                        "GRCh38",
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["observations"][0]["allele_frequency"], 0.02)

    def test_reference_snapshot_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "resources.json",
                {
                    "resources": [
                        {
                            "resource_id": "ref",
                            "kind": "fasta",
                            "uri": "ref.fa",
                            "checksum": "a" * 64,
                        }
                    ]
                },
            )
            output = root / "out.json"
            self.assertEqual(
                main(
                    [
                        "build-reference-snapshot",
                        str(source),
                        "--snapshot-id",
                        "s1",
                        "--assembly",
                        "GRCh38",
                        "--source-id",
                        "local",
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "supported")
            self.assertTrue(payload["manifest_hash"].startswith("sha256:"))

    def test_license_evaluation_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resources = self._write(root, "resources.json", {"resources": [{"resource_id": "ref"}]})
            restrictions = self._write(
                root,
                "restrictions.json",
                {
                    "restrictions": [
                        {
                            "resource_id": "ref",
                            "license_id": "MIT",
                            "allowed_uses": ["research"],
                            "redistribution_allowed": True,
                        }
                    ]
                },
            )
            output = root / "out.json"
            self.assertEqual(
                main(
                    [
                        "evaluate-license-use",
                        str(resources),
                        "--restrictions",
                        str(restrictions),
                        "--requested-use",
                        "research",
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(payload["decisions"][0]["allowed"])


if __name__ == "__main__":
    unittest.main()
