"""Offline artifact inventory and release manifest for structural evidence."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

from .serialization import canonical_json, content_hash
from .structural_architecture_contracts import (
    STRUCTURAL_ARCHITECTURE_ARTIFACT_COUNT,
    StructuralArchitectureArtifact,
    StructuralArchitectureCheck,
    StructuralArchitectureCheckKind,
    StructuralArchitectureEvaluation,
    StructuralArchitectureFixture,
    StructuralArchitectureLedger,
    StructuralArchitectureRelease,
    StructuralArchitectureState,
    addressed,
)


def build_structural_architecture_artifacts(
    fixture: StructuralArchitectureFixture,
    evaluation: StructuralArchitectureEvaluation,
    ledger: StructuralArchitectureLedger,
) -> tuple[StructuralArchitectureArtifact, ...]:
    """Materialize six bounded artifact receipts for offline use."""

    source_addresses = tuple(source.content_address for source in fixture.sources)
    definitions = (
        ("fixture", "application/json", len(fixture.cases), "retained"),
        ("evaluation", "application/json", len(evaluation.receipts), "retained"),
        ("review", "text/csv", evaluation.control_count, "retained"),
        ("lineage", "application/json", len(ledger.events), "retained"),
        ("metrics", "application/json", len(fixture.operations), "retained"),
        ("release-notes", "text/markdown", 1, "retained"),
    )
    artifacts: list[StructuralArchitectureArtifact] = []
    for artifact_type, media_type, row_count, retention in definitions:
        body = {
            "artifact_id": f"structural-architecture:{artifact_type}",
            "artifact_type": artifact_type,
            "media_type": media_type,
            "row_count": row_count,
            "source_addresses": source_addresses,
            "retention": retention,
        }
        artifacts.append(StructuralArchitectureArtifact(**body, content_address=content_hash(body)))
    return tuple(artifacts)


def build_structural_architecture_release(
    fixture: StructuralArchitectureFixture,
    artifacts: tuple[StructuralArchitectureArtifact, ...],
    evaluation: StructuralArchitectureEvaluation,
    ledger: StructuralArchitectureLedger,
) -> StructuralArchitectureRelease:
    """Publish only when all receipts and the lineage chain are closed."""

    checks = (
        _check(
            "artifact-count",
            len(artifacts) == STRUCTURAL_ARCHITECTURE_ARTIFACT_COUNT,
            len(artifacts),
            STRUCTURAL_ARCHITECTURE_ARTIFACT_COUNT,
            "six artifact receipts",
        ),
        _check(
            "evaluation",
            evaluation.accepted,
            evaluation.state.value,
            "accepted",
            "all cases match declarations",
        ),
        _check(
            "ledger",
            ledger.accepted,
            ledger.state if hasattr(ledger, "state") else ledger.accepted,
            True,
            "lineage is contiguous",
        ),
        _check(
            "artifact-addresses",
            all(item.content_address.startswith("sha256:") for item in artifacts),
            tuple(item.artifact_id for item in artifacts),
            "addressed artifacts",
            "artifact identities are stable",
        ),
    )
    published = all(item.passed for item in checks)
    state = (
        StructuralArchitectureState.PUBLISHED if published else StructuralArchitectureState.REVIEW
    )
    rollback_key = addressed(
        {
            "fixture_id": fixture.fixture_id,
            "artifact_addresses": tuple(item.content_address for item in artifacts),
        },
        "structural-rollback",
    )
    body = {
        "fixture_id": fixture.fixture_id,
        "state": state,
        "artifacts": artifacts,
        "rollback_key": rollback_key,
        "checks": checks,
    }
    return StructuralArchitectureRelease(
        fixture_id=fixture.fixture_id,
        state=state,
        artifacts=artifacts,
        rollback_key=rollback_key,
        checks=checks,
        content_address=addressed(body, "structural-release"),
    )


def render_structural_architecture_review_csv(
    evaluation: StructuralArchitectureEvaluation,
) -> str:
    """Render a deterministic review CSV with no raw payload columns."""

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=(
            "case_id",
            "operation_id",
            "expected_state",
            "observed_state",
            "result_state",
            "issue_codes",
            "passed",
        ),
        lineterminator="\n",
    )
    writer.writeheader()
    for receipt in evaluation.receipts:
        writer.writerow(
            {
                "case_id": receipt.case_id,
                "operation_id": receipt.operation_id,
                "expected_state": receipt.expected_state.value,
                "observed_state": receipt.observed_state.value,
                "result_state": receipt.observed_result_state,
                "issue_codes": ";".join(receipt.observed_issue_codes),
                "passed": str(receipt.passed).lower(),
            }
        )
    return output.getvalue()


def render_structural_architecture_markdown(
    release: StructuralArchitectureRelease,
) -> str:
    """Render a small human-readable release receipt."""

    lines = [
        "# Structural architecture release",
        "",
        f"- Fixture: `{release.fixture_id}`",
        f"- State: `{release.state.value}`",
        f"- Rollback key: `{release.rollback_key}`",
        "",
        "| Artifact | Media type | Rows | Address |",
        "| --- | --- | ---: | --- |",
    ]
    lines.extend(
        f"| {item.artifact_id} | {item.media_type} | {item.row_count} | `{item.content_address}` |"
        for item in release.artifacts
    )
    return "\n".join(lines) + "\n"


def write_structural_architecture_bundle(
    fixture: StructuralArchitectureFixture,
    evaluation: StructuralArchitectureEvaluation,
    ledger: StructuralArchitectureLedger,
    output: str | Path,
) -> StructuralArchitectureRelease:
    """Write JSON, CSV, and Markdown siblings below an output directory."""

    directory = Path(output)
    directory.mkdir(parents=True, exist_ok=True)
    artifacts = build_structural_architecture_artifacts(fixture, evaluation, ledger)
    release = build_structural_architecture_release(fixture, artifacts, evaluation, ledger)
    (directory / "fixture.json").write_text(canonical_json(fixture.to_dict()), encoding="utf-8")
    (directory / "evaluation.json").write_text(
        canonical_json(evaluation.to_dict()), encoding="utf-8"
    )
    (directory / "lineage.json").write_text(canonical_json(ledger.to_dict()), encoding="utf-8")
    (directory / "review.csv").write_text(
        render_structural_architecture_review_csv(evaluation), encoding="utf-8"
    )
    (directory / "release.md").write_text(
        render_structural_architecture_markdown(release), encoding="utf-8"
    )
    (directory / "release.json").write_text(canonical_json(release.to_dict()), encoding="utf-8")
    return release


def _check(
    check_id: str, passed: bool, observed: Any, required: Any, detail: str
) -> StructuralArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": StructuralArchitectureCheckKind.RELEASE,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return StructuralArchitectureCheck(
        **body, content_address=addressed(body, "structural-release-check")
    )


__all__ = [
    "build_structural_architecture_artifacts",
    "build_structural_architecture_release",
    "render_structural_architecture_markdown",
    "render_structural_architecture_review_csv",
    "write_structural_architecture_bundle",
]
