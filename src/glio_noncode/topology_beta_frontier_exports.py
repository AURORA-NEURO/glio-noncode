"""Sanitized JSON, CSV, and Markdown exports for review consumers."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from .topology_beta_frontier_fixture_eval import TopologyBetaFrontierEvaluation
from .topology_beta_frontier_public_data import TopologyBetaFrontierFixture


def export_topology_beta_frontier_manifest(fixture: TopologyBetaFrontierFixture, evaluation: TopologyBetaFrontierEvaluation) -> str:
    payload = {"fixture": {"fixture_id": fixture.fixture_id, "version": fixture.version, "boundary": fixture.boundary, "context_key": fixture.context_key, "source_count": len(fixture.sources), "record_count": len(fixture.records)}, "evaluation": {"fixture_id": evaluation.fixture_id, "accepted": evaluation.accepted, "state_match_count": evaluation.state_match_count, "issue_match_count": evaluation.issue_match_count, "rows": [{"record_id": row.record_id, "operation": row.operation, "role": row.role, "state": row.observed_state, "issues": row.observed_issue_codes, "source_ids": row.adapter.source_ids, "result_address": row.adapter.content_address} for row in evaluation.rows]}}
    return json.dumps(payload, sort_keys=True, indent=2)


def export_topology_beta_frontier_review_csv(evaluation: TopologyBetaFrontierEvaluation) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(("record_id", "operation", "role", "state", "issues", "evidence_count", "source_ids", "result_address"))
    for row in evaluation.rows:
        writer.writerow((row.record_id, row.operation, row.role, row.observed_state, ";".join(row.observed_issue_codes), len(row.adapter.evidence_ids), ";".join(row.adapter.source_ids), row.adapter.content_address))
    return buffer.getvalue()


def render_topology_beta_frontier_review_markdown(evaluation: TopologyBetaFrontierEvaluation) -> str:
    lines = ["# Domain 09 topology beta review", "", "| Record | Operation | Role | State | Issues |", "|---|---|---|---|---|"]
    lines.extend(f"| {row.record_id} | {row.operation} | {row.role} | {row.observed_state} | {', '.join(row.observed_issue_codes) or 'none'} |" for row in evaluation.rows)
    return "\n".join(lines) + "\n"


def export_topology_beta_frontier_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, indent=2)


__all__ = ["export_topology_beta_frontier_manifest", "export_topology_beta_frontier_payload", "export_topology_beta_frontier_review_csv", "render_topology_beta_frontier_review_markdown"]
