"""JSON, CSV, and Markdown exports for deployment frontier review."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from .deployment_frontier_contracts import DeploymentFrontierEvaluation
from .deployment_frontier_report import render_deployment_frontier_report
from .deployment_frontier_summary import DeploymentFrontierSummary
from .serialization import jsonable


def export_deployment_frontier_json(value: Any) -> str:
    return json.dumps(jsonable(value), indent=2, sort_keys=True) + "\n"


def export_deployment_frontier_review_csv(evaluation: DeploymentFrontierEvaluation) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=("record_id", "operation", "role", "state", "issue_codes"))
    writer.writeheader()
    for item in evaluation.executions:
        writer.writerow({"record_id": item.record_id, "operation": item.operation.value, "role": item.role.value, "state": item.state.value, "issue_codes": ";".join(item.issue_codes)})
    return output.getvalue()


def export_deployment_frontier_report_markdown(summary: DeploymentFrontierSummary) -> str:
    return render_deployment_frontier_report(summary)


__all__ = ["export_deployment_frontier_json", "export_deployment_frontier_report_markdown", "export_deployment_frontier_review_csv"]
