"""Publication projection rules and artifact receipts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Iterable, Mapping

from .cohort_beta_frontier_claim_boundary import CohortBetaFrontierClaimBoundary
from .cohort_beta_frontier_fixture_eval import CohortBetaFrontierEvaluation
from .cohort_beta_frontier_policy import CohortBetaFrontierDisposition, CohortBetaFrontierPolicy
from .cohort_beta_frontier_public_data import CohortBetaFrontierFixture
from .serialization import content_hash, jsonable


class CohortBetaFrontierArtifactAudience(StrEnum):
    RESEARCH_REVIEW = "research_review"
    PUBLIC_SUMMARY = "public_summary"
    OPERATIONS = "operations"


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierPublicationField:
    name: str
    purpose: str
    visible_to: tuple[CohortBetaFrontierArtifactAudience, ...]
    redacted_by_default: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierPublicationArtifact:
    artifact_id: str
    artifact_kind: str
    audience: CohortBetaFrontierArtifactAudience
    record_ids: tuple[str, ...]
    fields: tuple[CohortBetaFrontierPublicationField, ...]
    claim_ceiling: tuple[str, ...]
    publishable: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierPublicationPlan:
    artifacts: tuple[CohortBetaFrontierPublicationArtifact, ...]
    publishable_records: tuple[str, ...]
    held_records: tuple[str, ...]
    accepted: bool
    content_address: str

    def artifact(self, artifact_id: str) -> CohortBetaFrontierPublicationArtifact:
        return next(item for item in self.artifacts if item.artifact_id == artifact_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_cohort_beta_frontier_publication_fields() -> tuple[CohortBetaFrontierPublicationField, ...]:
    raw = (("operation", "operation identifier", (CohortBetaFrontierArtifactAudience.RESEARCH_REVIEW, CohortBetaFrontierArtifactAudience.PUBLIC_SUMMARY, CohortBetaFrontierArtifactAudience.OPERATIONS), False), ("record_id", "pseudonymous row key", (CohortBetaFrontierArtifactAudience.RESEARCH_REVIEW, CohortBetaFrontierArtifactAudience.OPERATIONS), True), ("state", "bounded result state", (CohortBetaFrontierArtifactAudience.RESEARCH_REVIEW, CohortBetaFrontierArtifactAudience.PUBLIC_SUMMARY, CohortBetaFrontierArtifactAudience.OPERATIONS), False), ("disposition", "publication policy result", (CohortBetaFrontierArtifactAudience.RESEARCH_REVIEW, CohortBetaFrontierArtifactAudience.OPERATIONS), False), ("source_receipts", "public source receipt references", (CohortBetaFrontierArtifactAudience.RESEARCH_REVIEW, CohortBetaFrontierArtifactAudience.PUBLIC_SUMMARY), False), ("content_address", "immutable result receipt", (CohortBetaFrontierArtifactAudience.RESEARCH_REVIEW, CohortBetaFrontierArtifactAudience.PUBLIC_SUMMARY, CohortBetaFrontierArtifactAudience.OPERATIONS), False))
    return tuple(CohortBetaFrontierPublicationField(name, purpose, visible_to, redacted, content_hash({"name": name, "purpose": purpose, "redacted": redacted}, prefix="publication-field")) for name, purpose, visible_to, redacted in raw)


def _artifact(artifact_id: str, kind: str, audience: CohortBetaFrontierArtifactAudience, record_ids: tuple[str, ...], fields: tuple[CohortBetaFrontierPublicationField, ...], boundary: CohortBetaFrontierClaimBoundary, publishable: bool) -> CohortBetaFrontierPublicationArtifact:
    body = {"artifact_id": artifact_id, "artifact_kind": kind, "audience": audience, "record_ids": record_ids, "fields": fields, "claim_ceiling": boundary.allowed_claims, "publishable": publishable}
    return CohortBetaFrontierPublicationArtifact(artifact_id, kind, audience, record_ids, fields, boundary.allowed_claims, publishable, content_hash(body, prefix="publication-artifact"))


def build_cohort_beta_frontier_publication_plan(fixture: CohortBetaFrontierFixture, evaluation: CohortBetaFrontierEvaluation, policy: CohortBetaFrontierPolicy, boundary: CohortBetaFrontierClaimBoundary, fields: Iterable[CohortBetaFrontierPublicationField] | None = None) -> CohortBetaFrontierPublicationPlan:
    selected_fields = tuple(fields or default_cohort_beta_frontier_publication_fields())
    publishable = tuple(row.record_id for row in evaluation.rows if policy.for_record(row.record_id).disposition is CohortBetaFrontierDisposition.PUBLISH)
    held = tuple(row.record_id for row in evaluation.rows if row.record_id not in publishable)
    artifacts = (_artifact("public-summary", "aggregate_summary", CohortBetaFrontierArtifactAudience.PUBLIC_SUMMARY, publishable, tuple(field for field in selected_fields if CohortBetaFrontierArtifactAudience.PUBLIC_SUMMARY in field.visible_to), boundary, bool(publishable)), _artifact("research-review", "review_queue", CohortBetaFrontierArtifactAudience.RESEARCH_REVIEW, held, selected_fields, boundary, False), _artifact("operations", "release_receipts", CohortBetaFrontierArtifactAudience.OPERATIONS, tuple(row.record_id for row in evaluation.rows), selected_fields, boundary, True))
    body = {"fixture": fixture.fixture_id, "artifacts": artifacts, "publishable": publishable, "held": held}
    return CohortBetaFrontierPublicationPlan(artifacts, publishable, held, len(publishable) == 4 and len(held) == 12 and len(artifacts) == 3, content_hash(body, prefix="publication-plan"))


def publication_manifest(plan: CohortBetaFrontierPublicationPlan) -> Mapping[str, Any]:
    return {"artifact_ids": tuple(item.artifact_id for item in plan.artifacts), "publishable_records": plan.publishable_records, "held_records": plan.held_records, "accepted": plan.accepted, "addresses": tuple(item.content_address for item in plan.artifacts)}


__all__ = ["CohortBetaFrontierArtifactAudience", "CohortBetaFrontierPublicationArtifact", "CohortBetaFrontierPublicationField", "CohortBetaFrontierPublicationPlan", "build_cohort_beta_frontier_publication_plan", "default_cohort_beta_frontier_publication_fields", "publication_manifest"]
