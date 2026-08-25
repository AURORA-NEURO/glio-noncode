"""Machine-readable schema and validators for the D14 closure projections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .evidence_lifecycle_frontier_offline_closure_contracts import (
    EVIDENCE_LIFECYCLE_CLOSURE_SCHEMA_VERSION,
    EvidenceLifecycleClosureCheck,
    evidence_lifecycle_closure_check,
)
from .evidence_lifecycle_frontier_offline_closure_support import all_rows, safe_relative_path
from .evidence_lifecycle_frontier_offline_contracts import EvidenceLifecycleOfflineBundle
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleClosureSchemaAudit:
    bundle_id: str
    schema_version: str
    checks: tuple[EvidenceLifecycleClosureCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed_count": sum(item.passed for item in self.checks),
            "failed_count": sum(not item.passed for item in self.checks),
        }


def evidence_lifecycle_closure_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Evidence lifecycle D14 closure",
        "version": EVIDENCE_LIFECYCLE_CLOSURE_SCHEMA_VERSION,
        "boundary": "public_aggregate_evidence_lifecycle_closure_handoff",
        "resources": {
            "artifacts": {
                "type": "array",
                "required": ["artifact_id", "relative_path", "content_address"],
            },
            "records": {
                "type": "array",
                "required": ["record_id", "operation", "role", "observed_state", "content_address"],
            },
            "executions": {
                "type": "array",
                "required": ["record_id", "state", "accepted", "content_address"],
            },
            "checks": {"type": "array", "required": ["check_id", "passed", "content_address"]},
            "sources": {"type": "array", "required": ["source_id", "uri", "content_address"]},
            "events": {"type": "array", "required": ["event_id", "sequence", "content_address"]},
            "stages": {
                "type": "array",
                "required": ["stage_id", "sequence", "output_address", "content_address"],
            },
            "edges": {
                "type": "array",
                "required": ["edge_id", "parent_id", "child_id", "content_address"],
            },
            "queue": {
                "type": "array",
                "required": ["item_id", "record_id", "disposition", "content_address"],
            },
            "reviews": {
                "type": "array",
                "required": ["record_id", "accepted", "release_state", "content_address"],
            },
            "scenarios": {
                "type": "array",
                "required": ["scenario_id", "operation", "expected_state", "content_address"],
            },
        },
        "privacy": {
            "direct_identity_fields": "excluded",
            "payload_text": "not exported",
            "source_boundary": "public_aggregate_non_patient",
        },
    }


def validate_evidence_lifecycle_closure_schema(
    bundle: EvidenceLifecycleOfflineBundle,
) -> EvidenceLifecycleClosureSchemaAudit:
    rows = all_rows(bundle)
    schema = evidence_lifecycle_closure_schema()
    checks: list[EvidenceLifecycleClosureCheck] = [
        evidence_lifecycle_closure_check(
            "schema-version",
            "manifest",
            schema["version"] == EVIDENCE_LIFECYCLE_CLOSURE_SCHEMA_VERSION,
            schema["version"],
            EVIDENCE_LIFECYCLE_CLOSURE_SCHEMA_VERSION,
            "schema version is stable",
        ),
        evidence_lifecycle_closure_check(
            "schema-boundary",
            "boundary",
            schema["boundary"] == "public_aggregate_evidence_lifecycle_closure_handoff",
            schema["boundary"],
            "public_aggregate_evidence_lifecycle_closure_handoff",
            "schema boundary is public aggregate",
        ),
        evidence_lifecycle_closure_check(
            "schema-resource-count",
            "manifest",
            len(schema["resources"]) == 11,
            len(schema["resources"]),
            11,
            "all closure row resources are declared",
        ),
        evidence_lifecycle_closure_check(
            "schema-artifact-count",
            "manifest",
            len(rows["artifacts"]) == 21,
            len(rows["artifacts"]),
            21,
            "artifact rows are present",
        ),
        evidence_lifecycle_closure_check(
            "schema-artifact-fields",
            "manifest",
            all(
                all(field in row for field in schema["resources"]["artifacts"]["required"])
                for row in rows["artifacts"]
            ),
            True,
            True,
            "artifact rows contain required fields",
        ),
        evidence_lifecycle_closure_check(
            "schema-record-fields",
            "fixture",
            all(
                all(field in row for field in schema["resources"]["records"]["required"])
                for row in rows["records"]
            ),
            True,
            True,
            "record rows contain required fields",
        ),
        evidence_lifecycle_closure_check(
            "schema-execution-fields",
            "evaluation",
            all(
                all(field in row for field in schema["resources"]["executions"]["required"])
                for row in rows["executions"]
            ),
            True,
            True,
            "execution rows contain required fields",
        ),
        evidence_lifecycle_closure_check(
            "schema-check-fields",
            "evaluation",
            all(
                all(field in row for field in schema["resources"]["checks"]["required"])
                for row in rows["checks"]
            ),
            True,
            True,
            "check rows contain required fields",
        ),
        evidence_lifecycle_closure_check(
            "schema-source-fields",
            "fixture",
            all(
                all(field in row for field in schema["resources"]["sources"]["required"])
                for row in rows["sources"]
            ),
            True,
            True,
            "source rows contain required fields",
        ),
        evidence_lifecycle_closure_check(
            "schema-event-fields",
            "observability",
            all(
                all(field in row for field in schema["resources"]["events"]["required"])
                for row in rows["events"]
            ),
            True,
            True,
            "event rows contain required fields",
        ),
        evidence_lifecycle_closure_check(
            "schema-stage-fields",
            "runtime",
            all(
                all(field in row for field in schema["resources"]["stages"]["required"])
                for row in rows["stages"]
            ),
            True,
            True,
            "stage rows contain required fields",
        ),
        evidence_lifecycle_closure_check(
            "schema-edge-fields",
            "lineage",
            all(
                all(field in row for field in schema["resources"]["edges"]["required"])
                for row in rows["edges"]
            ),
            True,
            True,
            "edge rows contain required fields",
        ),
        evidence_lifecycle_closure_check(
            "schema-queue-fields",
            "queue",
            all(
                all(field in row for field in schema["resources"]["queue"]["required"])
                for row in rows["queue"]
            ),
            True,
            True,
            "queue rows contain required fields",
        ),
        evidence_lifecycle_closure_check(
            "schema-review-fields",
            "review",
            all(
                all(field in row for field in schema["resources"]["reviews"]["required"])
                for row in rows["reviews"]
            ),
            True,
            True,
            "review rows contain required fields",
        ),
        evidence_lifecycle_closure_check(
            "schema-scenario-fields",
            "fixture",
            all(
                all(field in row for field in schema["resources"]["scenarios"]["required"])
                for row in rows["scenarios"]
            ),
            True,
            True,
            "scenario rows contain required fields",
        ),
        evidence_lifecycle_closure_check(
            "schema-safe-paths",
            "boundary",
            all(safe_relative_path(str(row.get("relative_path"))) for row in rows["artifacts"]),
            True,
            True,
            "artifact paths are safe",
        ),
        evidence_lifecycle_closure_check(
            "schema-privacy-policy",
            "boundary",
            schema["privacy"]["direct_identity_fields"] == "excluded"
            and schema["privacy"]["payload_text"] == "not exported",
            schema["privacy"],
            "excluded",
            "privacy behavior is declared",
        ),
    ]
    accepted = all(item.passed for item in checks)
    body = {
        "bundle_id": bundle.bundle_id,
        "schema_version": EVIDENCE_LIFECYCLE_CLOSURE_SCHEMA_VERSION,
        "checks": checks,
        "accepted": accepted,
    }
    return EvidenceLifecycleClosureSchemaAudit(
        **body, content_address=content_hash(body, prefix="evidence-lifecycle-closure-schema-audit")
    )


__all__ = [
    "EvidenceLifecycleClosureSchemaAudit",
    "evidence_lifecycle_closure_schema",
    "validate_evidence_lifecycle_closure_schema",
]
