"""CSV export of review rows with stable columns."""
from __future__ import annotations
import csv
import io
from typing import Any

def export_evidence_release_review_csv(evaluation: Any) -> str:
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("record_id", "capability", "operation", "role", "state", "issue_codes", "content_address"))
    for row in evaluation.executions:
        writer.writerow((row.record_id, row.capability, row.operation.value, row.role.value, row.observed_state.value, ";".join(row.issue_codes), row.content_address))
    return output.getvalue()

__all__ = ["export_evidence_release_review_csv"]
