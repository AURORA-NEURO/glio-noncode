"""Executable privacy and replay contract for the operator demo."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEMO = REPOSITORY_ROOT / "examples" / "case_expression_workflow_demo.py"
SOURCE_ROOT = REPOSITORY_ROOT / "src"


def _keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return {str(key) for key in value} | {
            nested
            for item in value.values()
            for nested in _keys(item)
        }
    if isinstance(value, list):
        return {nested for item in value for nested in _keys(item)}
    return set()


class CaseExpressionWorkflowDemoTests(unittest.TestCase):
    def test_demo_is_replay_verified_sample_free_and_offline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            guard = root / "network-guard"
            guard.mkdir()
            sentinel = root / "network-attempted"
            guard_active = root / "network-guard-active"
            (guard / "sitecustomize.py").write_text(
                """\
import os
import socket
from pathlib import Path

_original_socket = socket.socket
Path(os.environ["GLIO_DEMO_NETWORK_GUARD_ACTIVE"]).write_text("active", encoding="utf-8")

def _blocked(*args, **kwargs):
    Path(os.environ["GLIO_DEMO_NETWORK_SENTINEL"]).write_text("blocked", encoding="utf-8")
    raise RuntimeError("network use is blocked in the workflow demo test")

class _GuardedSocket(_original_socket):
    def connect(self, *args, **kwargs):
        return _blocked(*args, **kwargs)

    def connect_ex(self, *args, **kwargs):
        return _blocked(*args, **kwargs)

socket.socket = _GuardedSocket
socket.create_connection = _blocked
""",
                encoding="utf-8",
            )
            environment = os.environ.copy()
            existing_path = environment.get("PYTHONPATH")
            python_paths = [str(guard), str(SOURCE_ROOT)]
            if existing_path:
                python_paths.append(existing_path)
            environment["PYTHONPATH"] = os.pathsep.join(python_paths)
            environment["GLIO_DEMO_NETWORK_SENTINEL"] = str(sentinel)
            environment["GLIO_DEMO_NETWORK_GUARD_ACTIVE"] = str(guard_active)
            data_root = root / "runtime"
            completed = subprocess.run(
                [sys.executable, str(DEMO), "--data-root", str(data_root)],
                cwd=REPOSITORY_ROOT,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
                timeout=60,
            )

            self.assertEqual(completed.stderr, "")
            self.assertTrue(guard_active.exists(), "the subprocess network guard did not load")
            self.assertFalse(sentinel.exists(), "the demo attempted a network connection")
            self.assertTrue((data_root / "runs").is_dir())
            summary = json.loads(completed.stdout)

        self.assertTrue(summary["accepted"])
        self.assertTrue(summary["research_use_only"])
        self.assertIn("RESEARCH USE ONLY", summary["warning"])
        self.assertNotEqual(
            summary["preparation"]["prepared_run_id"],
            summary["evaluation"]["evaluation_run_id"],
        )
        self.assertTrue(summary["evaluation"]["rna_input_address"].startswith("sha256:"))
        self.assertEqual(summary["rna_evidence"]["state"], "supported")
        claim = summary["matched_rna_claim"]
        edge = summary["element_to_gene_edge"]
        path = summary["causal_path_support"]
        self.assertEqual(claim["channel"], "matched_rna_consequence")
        self.assertTrue(claim["claim_address"].startswith("ev-rna-"))
        self.assertEqual(claim["edge_id"], edge["edge_id"])
        self.assertIn(claim["claim_address"], edge["claim_addresses"])
        self.assertTrue(path["matched_rna_claim_linked"])
        self.assertIn(claim["claim_address"], path["supporting_claim_addresses"])
        self.assertTrue(summary["replay"]["accepted"])
        self.assertTrue(summary["replay"]["event_chain_valid"])
        self.assertTrue(summary["replay"]["stored_dossier_matches_address"])

        forbidden_keys = {
            "sample_key",
            "subject_id",
            "value",
            "ref_count",
            "alt_count",
            "other_count",
            "payload",
            "data_root",
        }
        self.assertTrue(forbidden_keys.isdisjoint(_keys(summary)))
        rendered = json.dumps(summary, sort_keys=True)
        for private_value in (
            "private:tumour-expression-key",
            "private:reference-",
            "synthetic-subject-private",
            "SYNTHETIC_PRIVATE",
            "20.125",
            "3.125",
            "4.875",
            "#CHROM",
        ):
            self.assertNotIn(private_value, rendered)


if __name__ == "__main__":
    unittest.main()
