"""CLI integration checks for the Domain 11 C01-C04 surface."""

from __future__ import annotations

import csv
import io
import json
import subprocess
import sys

import pytest


COMMANDS = (
    "causal-foundation-frontier-data-audit",
    "causal-foundation-frontier-contracts",
    "causal-foundation-frontier-schema",
    "causal-foundation-frontier-evaluate",
    "causal-foundation-frontier-metrics",
    "causal-foundation-frontier-policy",
    "causal-foundation-frontier-review",
    "causal-foundation-frontier-quality-gate",
    "causal-foundation-frontier-runtime",
    "causal-foundation-frontier-release",
    "causal-foundation-frontier-depth-audit",
    "causal-foundation-frontier-integrity",
    "causal-foundation-frontier-scenarios",
    "causal-foundation-frontier-validation-matrix",
    "causal-foundation-frontier-summary",
)


def run_cli(command: str) -> str:
    completed = subprocess.run(
        [sys.executable, "-m", "glio_noncode", command],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


@pytest.mark.parametrize("command", COMMANDS)
def test_causal_foundation_cli_commands_emit_json(command):
    value = json.loads(run_cli(command))
    assert isinstance(value, dict)
    assert value


def test_cli_data_audit_reports_closed_fixture():
    value = json.loads(run_cli("causal-foundation-frontier-data-audit"))
    assert value["accepted"] is True
    assert value["record_count"] == 16
    assert value["source_count"] == 5
    assert value["failed_checks"] == []


def test_cli_evaluation_reports_all_rows():
    value = json.loads(run_cli("causal-foundation-frontier-evaluate"))
    assert value["accepted"] is True
    assert value["state_match_count"] == 16
    assert value["issue_match_count"] == 16
    assert value["failed_record_ids"] == []
    assert len(value["rows"]) == 16


def test_cli_contracts_are_capability_keyed():
    value = json.loads(run_cli("causal-foundation-frontier-contracts"))
    assert value["accepted"] is True
    assert {item["capability_id"] for item in value["contracts"]} == {"GNC-D11-C01", "GNC-D11-C02", "GNC-D11-C03", "GNC-D11-C04"}


def test_cli_policy_exposes_decision_distribution():
    value = json.loads(run_cli("causal-foundation-frontier-policy"))
    decisions = value["decisions"]
    assert len(decisions) == 16
    assert sum(item["decision"] == "retain" for item in decisions) == 4
    assert sum(item["decision"] == "quarantine" for item in decisions) == 8
    assert sum(item["decision"] == "abstain" for item in decisions) == 2
    assert sum(item["decision"] == "review" for item in decisions) == 2


def test_cli_review_queue_preserves_control_priority():
    value = json.loads(run_cli("causal-foundation-frontier-review"))
    assert value["accepted"] is True
    assert value["retained_count"] == 4
    assert value["blocked_count"] == 10
    assert len(value["items"]) == 16
    assert any(item["priority"] == "critical" for item in value["items"])


def test_cli_quality_gate_has_no_blocking_check():
    value = json.loads(run_cli("causal-foundation-frontier-quality-gate"))
    assert value["accepted"] is True
    assert value["blocking_check_ids"] == []
    assert value["passed_count"] == 13
    assert value["failed_count"] == 0


def test_cli_runtime_exposes_ordered_stages():
    value = json.loads(run_cli("causal-foundation-frontier-runtime"))
    assert value["accepted"] is True
    assert value["stage_count"] == 19
    assert value["stage_ids"][0] == "data-audit"
    assert value["stage_ids"][-1] == "artifact-inventory"
    assert len(value["stages"]) == 19


def test_cli_release_is_ready():
    value = json.loads(run_cli("causal-foundation-frontier-release"))
    assert value["accepted"] is True
    assert value["state"] == "ready"
    assert value["passed_count"] == 5
    assert value["failed_check_ids"] == []


def test_cli_depth_audit_is_closed():
    value = json.loads(run_cli("causal-foundation-frontier-depth-audit"))
    assert value["accepted"] is True
    assert value["passed_count"] == 10
    assert value["required_count"] == 10


def test_cli_integrity_is_closed():
    value = json.loads(run_cli("causal-foundation-frontier-integrity"))
    assert value["accepted"] is True
    assert value["failed_check_ids"] == []
    assert len(value["checks"]) == 8


def test_cli_scenario_and_validation_matrices_are_complete():
    scenarios = json.loads(run_cli("causal-foundation-frontier-scenarios"))
    matrix = json.loads(run_cli("causal-foundation-frontier-validation-matrix"))
    assert scenarios["accepted"] is True
    assert scenarios["operation_count"] == 4
    assert matrix["accepted"] is True
    assert matrix["cell_count"] == 16
    assert matrix["passed_count"] == 16


def test_cli_summary_is_small_and_actionable():
    value = json.loads(run_cli("causal-foundation-frontier-summary"))
    assert value["accepted"] is True
    assert value["retained_count"] == 4
    assert value["review_count"] == 4
    assert value["quarantine_count"] == 10
    assert value["top_issue_codes"][0] == ["context_mismatch", 4]


def test_cli_csv_has_header_and_sixteen_rows():
    text = run_cli("export-causal-foundation-frontier-review-csv")
    rows = list(csv.DictReader(io.StringIO(text)))
    assert len(rows) == 16
    assert rows[0]["record_id"] == "D11-C01-P"
    assert rows[-1]["record_id"] == "D11-C04-C3"
    assert rows[0]["accepted"] == "True"


def test_cli_markdown_contains_boundaries():
    text = run_cli("export-causal-foundation-frontier-review-markdown")
    assert text.startswith("# Causal foundation review")
    assert "D11-C01-P" in text
    assert "context_mismatch" in text
    assert "decision" in text


def test_cli_json_export_contains_release_and_artifact_planes():
    value = json.loads(run_cli("export-causal-foundation-frontier-json"))
    assert value["accepted"] is True
    assert value["release"]["state"] == "ready"
    assert value["bundle"]["publishable"] is True
    assert value["artifacts"]["resolved_count"] == 16


def test_cli_rejects_unpinned_custom_fixture_path():
    completed = subprocess.run(
        [sys.executable, "-m", "glio_noncode", "causal-foundation-frontier-evaluate", "not-a-fixture.json"],
        capture_output=True,
        text=True,
    )
    assert completed.returncode != 0
    assert "pinned public aggregate" in completed.stderr
