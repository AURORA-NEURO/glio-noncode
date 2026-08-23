"""Fixture manifest and scope statement."""

from typing import Any

from .validation_beta_frontier_public_data import ValidationBetaFrontierFixture, default_validation_beta_frontier_fixture


def build_validation_beta_frontier_fixture_manifest(fixture: ValidationBetaFrontierFixture | None = None) -> dict[str, Any]:
    value = fixture or default_validation_beta_frontier_fixture()
    return {"fixture_id": value.fixture_id, "fixture_version": value.fixture_version, "context_key": value.context_key, "evidence_boundary": value.evidence_boundary, "source_count": len(value.sources), "record_count": len(value.records), "positive_count": len(value.positive_records), "control_count": len(value.control_records), "content_address": value.content_address}


__all__ = ["build_validation_beta_frontier_fixture_manifest"]
