"""Export helpers for JSON-compatible aggregate payloads."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .sequence_regulation_frontier_pipeline import SequenceRegulationPipelineReport
from .serialization import jsonable


def sequence_regulation_payload(report: SequenceRegulationPipelineReport) -> dict[str, Any]:
    """Return the stable full report payload."""

    return report.to_dict()


def write_sequence_regulation_json(
    report: SequenceRegulationPipelineReport,
    output: str | Path,
) -> Path:
    path = Path(output)
    if not path.parent.exists():
        raise ValidationError("output directory does not exist")
    path.write_text(
        json.dumps(jsonable(sequence_regulation_payload(report)), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


__all__ = ["sequence_regulation_payload", "write_sequence_regulation_json"]
