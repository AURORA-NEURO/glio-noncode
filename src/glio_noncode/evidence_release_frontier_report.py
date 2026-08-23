"""Text report renderer for a release summary."""
from __future__ import annotations
from typing import Any

def render_evidence_release_report(summary: Any) -> str:
    lines = ["Evidence release frontier", f"release_id: {summary.release_id}", f"rows: {summary.row_count}", f"accepted: {str(summary.accepted).lower()}", "states:"]
    lines.extend(f"- {key}: {value}" for key, value in sorted(summary.state_counts.items()))
    return "\n".join(lines) + "\n"

__all__ = ["render_evidence_release_report"]
