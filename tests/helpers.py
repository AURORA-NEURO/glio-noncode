"""Shared fixture helpers for unit and integration tests."""

from __future__ import annotations

import json
from pathlib import Path

from glio_noncode.models import CaseManifest


ROOT = Path(__file__).resolve().parents[1]


def fixture_manifest() -> CaseManifest:
    payload = json.loads((ROOT / "examples" / "case-small.json").read_text(encoding="utf-8"))
    return CaseManifest.from_dict(payload)
