"""Text report renderer for workbench release summaries."""
from __future__ import annotations
from typing import Any

def render_workbench_release_report(runtime: Any) -> str:
    lines = ["Workbench release frontier", f"run_id: {runtime.run_id}", f"rows: {runtime.metrics.row_count}", f"accepted: {str(runtime.accepted).lower()}", "states:"]
    lines.extend(f"- {key}: {value}" for key, value in sorted(runtime.metrics.state_counts.items()))
    lines.append(f"stages: {len(runtime.stages)}")
    return "\n".join(lines) + "\n"

__all__ = ["render_workbench_release_report"]
