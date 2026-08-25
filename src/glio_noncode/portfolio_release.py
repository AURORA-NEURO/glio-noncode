"""Deterministic multi-run portfolio release assembly and verification.

The local runtime already supports replay-gated dossiers, workspaces, batches,
review operations, and single-run release bundles.  This module composes those
surfaces into one portable handoff without changing their source records.  It
is deliberately a read-only operation over :class:`CaseRuntime`:

* selection is explicit, bounded, and content-addressed;
* every selected run retains its own dossier and workspace gate evidence;
* blocked members remain visible with stable failed-check identifiers;
* artifact paths are namespaced by run and verified as exact UTF-8 bytes;
* the package manifest can be reopened without the producing runtime; and
* no private identifiers, attribution fields, or language metadata cross the
  public boundary.

The package is a research handoff.  ``accepted`` means that the declared
release contracts passed; it does not make a clinical claim or authorize a
treatment decision.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable, Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from .dossier_release import DossierReleaseBundle, build_dossier_release_bundle
from .errors import StoreError, ValidationError
from .models import Dossier
from .module_fabric_support import contains_private_key
from .portfolio_release_contracts import (
    PORTFOLIO_RELEASE_ARTIFACT_PREFIX,
    PORTFOLIO_RELEASE_DEFAULT_MAX_RUNS,
    PORTFOLIO_RELEASE_MANIFEST,
    PORTFOLIO_RELEASE_MAX_RUNS,
    PORTFOLIO_RELEASE_VERSION,
    PortfolioArtifactKind,
    PortfolioReleaseArtifact,
    PortfolioReleaseBundle,
    PortfolioReleaseMember,
    PortfolioReleaseState,
    PortfolioReleaseVerification,
    address_check,
)
from .run_catalog import RunInspection, inspect_run
from .run_portfolio import build_run_portfolio
from .run_workspace import _has_forbidden_key, _public_projection
from .runtime import CaseRuntime
from .serialization import canonical_json, content_hash, hash_bytes, jsonable
from .workspace_history import WorkspaceHistory, build_persisted_workspace_history
from .workspace_release import WorkspaceReleaseBundle, build_workspace_release_bundle


def _text(value: Any) -> str:
    """Return a trimmed public string representation."""

    return str(value).strip()


def _unique(values: Iterable[Any]) -> tuple[str, ...]:
    """Normalize warnings and identifiers while retaining first-seen order."""

    output: list[str] = []
    for value in values:
        item = _text(value)
        if item and item not in output:
            output.append(item)
    return tuple(output)


def _safe_component(value: str, field: str) -> str:
    """Validate a run or release component before it enters a path."""

    normalized = _text(value)
    if (
        not normalized
        or len(normalized) > 128
        or normalized in {".", ".."}
        or any(char in normalized for char in ("/", "\\"))
        or ".." in normalized
    ):
        raise ValidationError(f"{field} contains an unsafe path fragment")
    return normalized


def _safe_relative_path(value: str) -> bool:
    """Return whether a manifest path is a safe relative POSIX path."""

    if not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts:
        return False
    if any(part in {"", ".", ".."} for part in path.parts):
        return False
    return all(len(part) <= 160 for part in path.parts)


def _json_text(value: Any) -> str:
    """Render canonical JSON with one terminal newline for portable files."""

    return canonical_json(jsonable(value)) + "\n"


def _csv_text(headers: tuple[str, ...], rows: Iterable[tuple[Any, ...]]) -> str:
    """Render deterministic UTF-8 CSV with LF line endings."""

    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return output.getvalue()


def _artifact_kind(artifact_id: str, media_type: str) -> PortfolioArtifactKind:
    """Map a source artifact identity to a stable portfolio facet."""

    lowered = artifact_id.casefold()
    if lowered.endswith("events") or "run-events" in lowered:
        return PortfolioArtifactKind.EVENTS
    if "release" in lowered or "gate" in lowered:
        return PortfolioArtifactKind.RELEASE_GATE
    if "dossier" in lowered:
        return PortfolioArtifactKind.DOSSIER
    if "workspace" in lowered or "history" in lowered:
        return PortfolioArtifactKind.WORKSPACE
    if lowered.endswith("summary") or "summary" in lowered:
        return PortfolioArtifactKind.SUMMARY
    if media_type == "text/csv":
        return PortfolioArtifactKind.CSV
    if media_type == "text/markdown":
        return PortfolioArtifactKind.MARKDOWN
    return PortfolioArtifactKind.MEMBER


def _artifact(
    artifact_id: str,
    relative_path: str,
    media_type: str,
    payload: str,
    *,
    kind: PortfolioArtifactKind,
    member_run_id: str | None,
) -> PortfolioReleaseArtifact:
    """Create an artifact whose address describes exact encoded bytes."""

    path = _text(relative_path)
    if not _safe_relative_path(path):
        raise ValidationError(f"unsafe portfolio artifact path: {relative_path!r}")
    if media_type == "application/json":
        try:
            payload = _json_text(_public_projection(json.loads(payload)))
        except json.JSONDecodeError:
            # Verification will reject malformed JSON artifacts.  Keeping the
            # original bytes here preserves a useful diagnostic in a blocked
            # package instead of failing assembly before checks are emitted.
            pass
    encoded = payload.encode("utf-8")
    return PortfolioReleaseArtifact(
        artifact_id=_safe_component(artifact_id, "artifact_id"),
        relative_path=path,
        media_type=_text(media_type),
        kind=kind,
        member_run_id=member_run_id,
        byte_count=len(encoded),
        line_count=len(payload.splitlines()),
        content_address=hash_bytes(encoded, prefix=PORTFOLIO_RELEASE_ARTIFACT_PREFIX),
        payload=payload,
    )


def _member_address(body: Mapping[str, Any]) -> str:
    """Address a member projection after removing its derived address."""

    clean = dict(body)
    clean.pop("content_address", None)
    return content_hash(clean, prefix="portfolio-release-member")


def _bundle_address(body: Mapping[str, Any]) -> str:
    """Address the package manifest body after removing its derived address."""

    clean = dict(body)
    clean.pop("content_address", None)
    return content_hash(clean, prefix="portfolio-release")


def _public_json_payload(payload: str) -> tuple[bool, str | None]:
    """Check a JSON artifact for private or prohibited attribution fields."""

    try:
        value = json.loads(payload)
    except json.JSONDecodeError:
        return False, "JSON artifact is not valid JSON"
    if _has_forbidden_key(value) or contains_private_key(value):
        return False, "JSON artifact violates the public boundary"
    return True, None


def _prefix_release_artifacts(
    run_id: str,
    release: DossierReleaseBundle | WorkspaceReleaseBundle,
    release_kind: str,
) -> list[PortfolioReleaseArtifact]:
    """Namespace an existing release's artifacts inside a portfolio package."""

    safe_run = _safe_component(run_id, "run_id")
    base = f"members/{safe_run}/{release_kind}"
    artifacts: list[PortfolioReleaseArtifact] = []
    source_kind = PortfolioArtifactKind.DOSSIER if release_kind == "dossier" else PortfolioArtifactKind.WORKSPACE
    for item in release.artifacts:
        filename = _text(item.filename)
        if not filename or Path(filename).name != filename:
            raise ValidationError(f"source release contains an unsafe artifact filename: {filename!r}")
        artifact_id = f"{safe_run}:{release_kind}:{item.artifact_id}"
        artifacts.append(
            _artifact(
                artifact_id,
                f"{base}/{filename}",
                item.media_type,
                item.payload,
                kind=(
                    source_kind
                    if item.media_type == "application/json"
                    else _artifact_kind(item.artifact_id, item.media_type)
                ),
                member_run_id=safe_run,
            )
        )
    manifest_kind = PortfolioArtifactKind.DOSSIER if release_kind == "dossier" else PortfolioArtifactKind.WORKSPACE
    artifacts.append(
        _artifact(
            f"{safe_run}:{release_kind}:manifest",
            f"{base}/{PORTFOLIO_RELEASE_MANIFEST}",
            "application/json",
            _json_text(release.manifest_dict()),
            kind=manifest_kind,
            member_run_id=safe_run,
        )
    )
    return artifacts


def _member_artifacts(
    runtime: CaseRuntime,
    run_id: str,
) -> tuple[PortfolioReleaseMember, list[PortfolioReleaseArtifact]]:
    """Build one member and all of its namespaced public artifacts."""

    safe_run = _safe_component(run_id, "run_id")
    warnings: list[str] = []
    artifacts: list[PortfolioReleaseArtifact] = []
    inspection: RunInspection | None = None
    dossier_release: DossierReleaseBundle | None = None
    workspace_history: WorkspaceHistory | None = None
    workspace_release: WorkspaceReleaseBundle | None = None
    case_id = ""
    dossier_address: str | None = None

    try:
        inspection = inspect_run(runtime, safe_run)
        case_id = inspection.summary.case_id
        dossier_address = inspection.summary.dossier_address
        warnings.extend(inspection.summary.warnings)
        if not inspection.accepted:
            warnings.append("run replay integrity is not accepted")
        else:
            dossier = Dossier.from_dict(inspection.dossier_record)
            dossier_release = build_dossier_release_bundle(dossier, inspection)
            artifacts.extend(_prefix_release_artifacts(safe_run, dossier_release, "dossier"))
            artifacts.extend(
                [
                    _artifact(
                        f"{safe_run}:run-record",
                        f"members/{safe_run}/run-record.json",
                        "application/json",
                        _json_text(inspection.run_record),
                        kind=PortfolioArtifactKind.SUMMARY,
                        member_run_id=safe_run,
                    ),
                    _artifact(
                        f"{safe_run}:run-summary",
                        f"members/{safe_run}/run-summary.json",
                        "application/json",
                        _json_text(inspection.summary.to_dict()),
                        kind=PortfolioArtifactKind.SUMMARY,
                        member_run_id=safe_run,
                    ),
                    _artifact(
                        f"{safe_run}:run-events",
                        f"members/{safe_run}/run-events.json",
                        "application/json",
                        _json_text(
                            {
                                "run_id": safe_run,
                                "event_address": inspection.summary.event_address,
                                "events": inspection.event_record.get("events", []),
                                "replay": inspection.replay.to_dict(),
                            }
                        ),
                        kind=PortfolioArtifactKind.EVENTS,
                        member_run_id=safe_run,
                    ),
                ]
            )
    except (AttributeError, KeyError, StoreError, TypeError, ValueError, ValidationError) as exc:
        warnings.append(f"run member assembly failed: {type(exc).__name__}: {exc}")

    try:
        workspace_history = build_persisted_workspace_history(runtime, safe_run)
        workspace_release = build_workspace_release_bundle(workspace_history)
        artifacts.extend(_prefix_release_artifacts(safe_run, workspace_release, "workspace"))
    except (AttributeError, KeyError, StoreError, TypeError, ValueError, ValidationError) as exc:
        warnings.append(f"workspace member assembly failed: {type(exc).__name__}: {exc}")

    dossier_state = dossier_release.state if dossier_release is not None else "unavailable"
    workspace_state = workspace_release.state if workspace_release is not None else "unavailable"
    failed: list[str] = []
    if dossier_release is not None:
        failed.extend(f"dossier:{item}" for item in dossier_release.failed_check_ids)
    if workspace_release is not None:
        failed.extend(f"workspace:{item}" for item in workspace_release.failed_check_ids)
    if not inspection or not inspection.accepted:
        failed.append("run:integrity")
    member_ready = bool(
        inspection
        and inspection.accepted
        and dossier_release is not None
        and dossier_release.accepted
        and workspace_release is not None
        and workspace_release.accepted
    )
    if not member_ready and not failed:
        failed.append("member:release-gate")
    state = PortfolioReleaseState.READY if member_ready else PortfolioReleaseState.BLOCKED
    member_body: dict[str, Any] = {
        "run_id": safe_run,
        "case_id": case_id,
        "dossier_address": dossier_address,
        "workspace_history_address": workspace_history.content_address if workspace_history else None,
        "dossier_release_id": dossier_release.release_id if dossier_release else None,
        "workspace_release_id": workspace_release.release_id if workspace_release else None,
        "dossier_state": dossier_state,
        "workspace_state": workspace_state,
        "state": state,
        "accepted": member_ready,
        "artifact_ids": (),
        "failed_check_ids": tuple(sorted(_unique(failed))),
        "warnings": _unique(warnings),
    }
    member_artifact_id = f"{safe_run}:member"
    member_body["artifact_ids"] = tuple(sorted([item.artifact_id for item in artifacts] + [member_artifact_id]))
    member_address_body = dict(member_body)
    member_address_body["state"] = state.value
    member_address_body["ready"] = member_ready
    member_address_body["artifact_count"] = len(member_body["artifact_ids"])
    member = PortfolioReleaseMember(
        **member_body,
        content_address=_member_address(member_address_body),
    )
    artifacts.append(
        _artifact(
            member_artifact_id,
            f"members/{safe_run}/member.json",
            "application/json",
            _json_text(member.to_dict()),
            kind=PortfolioArtifactKind.MEMBER,
            member_run_id=safe_run,
        )
    )
    return member, artifacts


def _portfolio_summary_rows(
    members: tuple[PortfolioReleaseMember, ...],
) -> tuple[tuple[Any, ...], ...]:
    """Return deterministic tabular member rows."""

    return tuple(
        (
            item.run_id,
            item.case_id,
            item.state.value,
            item.accepted,
            item.dossier_state,
            item.workspace_state,
            item.artifact_count,
            ";".join(item.failed_check_ids),
            ";".join(item.warnings),
        )
        for item in sorted(members, key=lambda value: value.run_id)
    )


def render_portfolio_release_report(
    bundle: PortfolioReleaseBundle,
) -> str:
    """Render a bounded human-readable report for an offline handoff."""

    lines = [
        "# Portfolio release",
        "",
        f"- Release: `{bundle.release_id}`",
        f"- State: `{bundle.state.value}`",
        f"- Accepted: `{str(bundle.accepted).lower()}`",
        f"- As of: `{bundle.as_of}`",
        f"- Members: `{bundle.member_count}`",
        f"- Ready members: `{bundle.ready_member_count}`",
        f"- Blocked members: `{bundle.blocked_member_count}`",
        f"- Artifacts: `{bundle.artifact_count}`",
        "",
        "## Package checks",
        "",
        "| Check | Passed | Scope | Detail |",
        "| --- | --- | --- | --- |",
    ]
    for check in bundle.checks:
        lines.append(
            f"| `{check.check_id}` | `{str(check.passed).lower()}` | `{check.scope}` | {check.detail} |"
        )
    lines.extend(
        [
            "",
            "## Members",
            "",
            "| Run | Case | State | Dossier | Workspace | Artifacts | Failed checks |",
            "| --- | --- | --- | --- | --- | ---: | --- |",
        ]
    )
    for member in sorted(bundle.members, key=lambda value: value.run_id):
        lines.append(
            "| "
            + " | ".join(
                (
                    f"`{member.run_id}`",
                    member.case_id,
                    f"`{member.state.value}`",
                    f"`{member.dossier_state}`",
                    f"`{member.workspace_state}`",
                    str(member.artifact_count),
                    "; ".join(member.failed_check_ids) or "—",
                )
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "This package is a research handoff and does not make a clinical or treatment decision.",
            "",
        ]
    )
    return "\n".join(lines)


def _validate_build_options(
    *,
    max_runs: int,
    due_soon_hours: int,
    run_ids: Iterable[str] | None,
) -> tuple[str, ...]:
    """Validate and normalize bounded selection controls."""

    if max_runs < 1 or max_runs > PORTFOLIO_RELEASE_MAX_RUNS:
        raise ValidationError(
            f"max_runs must be between 1 and {PORTFOLIO_RELEASE_MAX_RUNS}"
        )
    if due_soon_hours < 1:
        raise ValidationError("due_soon_hours must be positive")
    values = tuple(_safe_component(item, "run_id") for item in (run_ids or ()))
    if len(values) != len(set(values)):
        raise ValidationError("run_ids must be unique")
    return values


def build_portfolio_release(
    runtime: CaseRuntime,
    *,
    run_ids: Iterable[str] | None = None,
    case_id: str | None = None,
    status: str | None = None,
    reviewer: str | None = None,
    due_state: str | None = None,
    release_state: str | None = None,
    text: str | None = None,
    release_ready_only: bool = False,
    include_blocked: bool = True,
    as_of: str | None = None,
    due_soon_hours: int = 72,
    max_runs: int = PORTFOLIO_RELEASE_DEFAULT_MAX_RUNS,
) -> PortfolioReleaseBundle:
    """Build a deterministic repository-wide portfolio release package.

    The source portfolio is evaluated without a page limit.  Explicit run IDs
    are applied after the public portfolio filters so a caller can combine a
    dashboard query with a handoff selection.  Unknown requested IDs remain in
    the package checks rather than silently disappearing.
    """

    requested_ids = _validate_build_options(
        max_runs=max_runs,
        due_soon_hours=due_soon_hours,
        run_ids=run_ids,
    )
    portfolio = build_run_portfolio(
        runtime,
        case_id=case_id,
        status=status,
        reviewer=reviewer,
        due_state=due_state,
        release_state=release_state,
        text=text,
        release_ready_only=release_ready_only,
        as_of=as_of,
        due_soon_hours=due_soon_hours,
        limit=None,
    )
    available = {item.run_id: item for item in portfolio.rows}
    if requested_ids:
        selected_rows = tuple(available[item] for item in requested_ids if item in available)
        missing_ids = tuple(item for item in requested_ids if item not in available)
    else:
        selected_rows = portfolio.rows
        missing_ids = ()
    if not include_blocked:
        selected_rows = tuple(item for item in selected_rows if item.release_ready)
    selected_rows = tuple(selected_rows[:max_runs])
    selected_ids = tuple(item.run_id for item in selected_rows)
    selection = {
        "run_ids": list(requested_ids),
        "case_id": case_id,
        "status": status,
        "reviewer": reviewer,
        "due_state": due_state,
        "release_state": release_state,
        "text": text,
        "release_ready_only": release_ready_only,
        "include_blocked": include_blocked,
        "as_of": as_of,
        "due_soon_hours": due_soon_hours,
        "max_runs": max_runs,
    }
    release_seed = {
        "selection": selection,
        "selected_run_ids": selected_ids,
        "portfolio_address": portfolio.content_address,
    }
    release_id = f"portfolio-release-{content_hash(release_seed).split(':', 1)[1][:24]}"

    members_list: list[PortfolioReleaseMember] = []
    artifacts: list[PortfolioReleaseArtifact] = []
    for run_id in selected_ids:
        member, member_artifacts = _member_artifacts(runtime, run_id)
        members_list.append(member)
        artifacts.extend(member_artifacts)
    members = tuple(sorted(members_list, key=lambda item: item.run_id))
    artifacts = sorted(artifacts, key=lambda item: item.relative_path)

    preliminary_checks = (
        address_check(
            "selection-not-empty",
            bool(members),
            len(members),
            ">=1",
            "a portfolio release must contain at least one selected run",
        ),
        address_check(
            "requested-runs-found",
            not missing_ids,
            list(missing_ids),
            [],
            "every explicitly requested run must be present in the filtered portfolio",
        ),
        address_check(
            "selection-bound",
            len(members) <= max_runs,
            len(members),
            f"<= {max_runs}",
            "portfolio releases remain bounded for safe offline handoff",
        ),
        address_check(
            "portfolio-projection-accepted",
            portfolio.accepted,
            portfolio.accepted,
            True,
            "the source cross-run operational projection passed its public contract",
        ),
        address_check(
            "member-identities-unique",
            len({item.run_id for item in members}) == len(members),
            len({item.run_id for item in members}),
            len(members),
            "selected members have unique run identities",
        ),
        address_check(
            "member-addresses-valid",
            all(item.content_address.startswith("portfolio-release-member:") for item in members),
            sum(item.content_address.startswith("portfolio-release-member:") for item in members),
            len(members),
            "every member projection is content-addressed",
        ),
        address_check(
            "member-release-gates",
            bool(members) and all(item.ready for item in members),
            sum(item.ready for item in members),
            len(members),
            "every selected member must pass run, dossier, and workspace gates",
        ),
        address_check(
            "public-boundary",
            not _has_forbidden_key(portfolio.to_dict()) and not contains_private_key(portfolio.to_dict()),
            True,
            True,
            "portfolio projections contain no private identifiers or attribution metadata",
        ),
    )

    portfolio_projection = portfolio.to_dict()
    base_artifacts = list(artifacts)
    base_artifacts.extend(
        [
            _artifact(
                "portfolio:projection",
                "portfolio.json",
                "application/json",
                _json_text(portfolio_projection),
                kind=PortfolioArtifactKind.PORTFOLIO,
                member_run_id=None,
            ),
            _artifact(
                "portfolio:members",
                "portfolio-members.json",
                "application/json",
                _json_text([item.to_dict() for item in members]),
                kind=PortfolioArtifactKind.SUMMARY,
                member_run_id=None,
            ),
            _artifact(
                "portfolio:summary-csv",
                "portfolio-summary.csv",
                "text/csv",
                _csv_text(
                    (
                        "run_id",
                        "case_id",
                        "state",
                        "accepted",
                        "dossier_state",
                        "workspace_state",
                        "artifact_count",
                        "failed_check_ids",
                        "warnings",
                    ),
                    _portfolio_summary_rows(members),
                ),
                kind=PortfolioArtifactKind.CSV,
                member_run_id=None,
            ),
        ]
    )
    preliminary_bundle_body = {
        "release_version": PORTFOLIO_RELEASE_VERSION,
        "release_id": release_id,
        "as_of": portfolio.as_of,
        "selection": selection,
        "state": PortfolioReleaseState.BLOCKED.value,
        "accepted": False,
        "members": [item.to_dict() for item in members],
        "artifacts": [item.to_dict(include_payload=False) for item in base_artifacts],
        "checks": [item.to_dict() for item in preliminary_checks],
    }
    report_seed = PortfolioReleaseBundle(
        release_id=release_id,
        as_of=portfolio.as_of,
        selection=selection,
        state=PortfolioReleaseState.BLOCKED,
        accepted=False,
        members=members,
        artifacts=tuple(base_artifacts),
        checks=preliminary_checks,
        content_address=_bundle_address(preliminary_bundle_body),
    )
    base_artifacts.append(
        _artifact(
            "portfolio:report",
            "portfolio-report.md",
            "text/markdown",
            render_portfolio_release_report(report_seed),
            kind=PortfolioArtifactKind.MARKDOWN,
            member_run_id=None,
        )
    )
    base_artifacts = sorted(base_artifacts, key=lambda item: item.relative_path)
    artifact_check = address_check(
        "artifact-closure",
        len(base_artifacts) > 0
        and len({item.artifact_id for item in base_artifacts}) == len(base_artifacts)
        and len({item.relative_path for item in base_artifacts}) == len(base_artifacts)
        and all(item.content_address.startswith(f"{PORTFOLIO_RELEASE_ARTIFACT_PREFIX}:") for item in base_artifacts),
        len(base_artifacts),
        "unique addressed artifacts",
        "every artifact has a unique path, identity, and exact-byte address",
    )
    checks = preliminary_checks + (artifact_check,)
    checks_artifact = _artifact(
        "portfolio:checks",
        "portfolio-checks.json",
        "application/json",
        _json_text([item.to_dict() for item in checks]),
        kind=PortfolioArtifactKind.RELEASE_GATE,
        member_run_id=None,
    )
    final_artifacts = tuple(sorted(base_artifacts + [checks_artifact], key=lambda item: item.relative_path))
    accepted = bool(members) and all(item.passed for item in checks)
    state = PortfolioReleaseState.READY if accepted else PortfolioReleaseState.BLOCKED
    body = {
        "release_version": PORTFOLIO_RELEASE_VERSION,
        "release_id": release_id,
        "as_of": portfolio.as_of,
        "selection": selection,
        "state": state.value,
        "accepted": accepted,
        "member_count": len(members),
        "ready_member_count": sum(item.ready for item in members),
        "blocked_member_count": sum(not item.ready for item in members),
        "artifact_count": len(final_artifacts),
        "warning_count": sum(len(item.warnings) for item in members),
        "failed_check_ids": [item.check_id for item in checks if not item.passed],
        "members": [item.to_dict() for item in members],
        "artifacts": [item.to_dict(include_payload=False) for item in final_artifacts],
        "checks": [item.to_dict() for item in checks],
    }
    return PortfolioReleaseBundle(
        release_id=release_id,
        as_of=portfolio.as_of,
        selection=selection,
        state=state,
        accepted=accepted,
        members=members,
        artifacts=final_artifacts,
        checks=checks,
        content_address=_bundle_address(body),
    )


def write_portfolio_release_bundle(
    bundle: PortfolioReleaseBundle,
    destination: str | Path,
) -> Path:
    """Write a portfolio bundle into a new or empty directory."""

    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise ValueError("portfolio release destination must be empty")
    for artifact in bundle.artifacts:
        if not _safe_relative_path(artifact.relative_path):
            raise ValidationError(f"unsafe portfolio artifact path: {artifact.relative_path}")
        target = root.joinpath(*PurePosixPath(artifact.relative_path).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(artifact.payload, encoding="utf-8", newline="")
    (root / PORTFOLIO_RELEASE_MANIFEST).write_text(
        canonical_json(bundle.manifest_dict()),
        encoding="utf-8",
        newline="",
    )
    return root


def _iter_files(root: Path) -> tuple[Path, ...]:
    """Return all regular and symlink paths below a release root."""

    manifest_path = root / PORTFOLIO_RELEASE_MANIFEST
    return tuple(
        sorted(
            (item for item in root.rglob("*") if item != manifest_path),
            key=lambda item: item.as_posix(),
        )
    )


def verify_portfolio_release_bundle(
    destination: str | Path,
) -> PortfolioReleaseVerification:
    """Reopen a portfolio directory and verify every manifest invariant."""

    root = Path(destination)
    if not root.is_dir():
        raise ValidationError("portfolio release directory is missing")
    manifest_path = root / PORTFOLIO_RELEASE_MANIFEST
    if not manifest_path.is_file():
        raise ValidationError("portfolio release manifest is missing")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError("portfolio release manifest is not valid JSON") from exc
    if not isinstance(manifest, dict):
        raise ValidationError("portfolio release manifest must be a JSON object")

    warnings: list[str] = []
    failed_artifacts: list[str] = []
    failed_members: list[str] = []
    manifest_version_valid = manifest.get("release_version") == PORTFOLIO_RELEASE_VERSION
    if not manifest_version_valid:
        warnings.append("portfolio release manifest version is invalid")
    manifest_body = dict(manifest)
    declared_address = _text(manifest_body.pop("content_address", ""))
    manifest_address_valid = bool(declared_address) and _bundle_address(manifest_body) == declared_address
    if not manifest_address_valid:
        warnings.append("portfolio release manifest content address is invalid")

    raw_artifacts = manifest.get("artifacts", [])
    if not isinstance(raw_artifacts, list):
        raise ValidationError("portfolio release manifest artifacts must be an array")
    try:
        declared_artifact_count = int(manifest.get("artifact_count", -1))
    except (TypeError, ValueError):
        declared_artifact_count = -1
    if declared_artifact_count != len(raw_artifacts):
        warnings.append("portfolio release artifact count mismatch")
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    declared_paths: set[str] = set()
    verified_artifact_count = 0
    public_boundary_valid = True
    path_safety_valid = True
    for raw in raw_artifacts:
        if not isinstance(raw, dict):
            failed_artifacts.append("invalid-artifact")
            path_safety_valid = False
            continue
        artifact_id = _text(raw.get("artifact_id", ""))
        relative_path = _text(raw.get("relative_path", ""))
        if artifact_id in seen_ids or relative_path in seen_paths:
            failed_artifacts.append(artifact_id or "duplicate-artifact")
            warnings.append(f"duplicate portfolio artifact identity for {artifact_id or relative_path}")
            continue
        seen_ids.add(artifact_id)
        seen_paths.add(relative_path)
        declared_paths.add(relative_path)
        if not _safe_relative_path(relative_path):
            failed_artifacts.append(artifact_id or "unsafe-artifact")
            path_safety_valid = False
            continue
        target = root.joinpath(*PurePosixPath(relative_path).parts)
        if target.is_symlink() or not target.is_file():
            failed_artifacts.append(artifact_id or "missing-artifact")
            warnings.append(f"portfolio artifact is missing or symlinked: {relative_path}")
            continue
        try:
            payload_bytes = target.read_bytes()
            payload = payload_bytes.decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            failed_artifacts.append(artifact_id or "invalid-encoding")
            warnings.append(f"portfolio artifact could not be read: {relative_path}: {exc}")
            continue
        boundary_ok = True
        boundary_detail: str | None = None
        if _text(raw.get("media_type", "")) == "application/json":
            boundary_ok, boundary_detail = _public_json_payload(payload)
            if not boundary_ok:
                failed_artifacts.append(artifact_id or "public-boundary")
                public_boundary_valid = False
                warnings.append(f"{boundary_detail}: {relative_path}")
        expected_address = _text(raw.get("content_address", ""))
        if hash_bytes(payload_bytes, prefix=PORTFOLIO_RELEASE_ARTIFACT_PREFIX) != expected_address:
            if artifact_id not in failed_artifacts:
                failed_artifacts.append(artifact_id or "address-mismatch")
            warnings.append(f"portfolio artifact byte address mismatch: {relative_path}")
            continue
        try:
            expected_bytes = int(raw.get("byte_count", -1))
            expected_lines = int(raw.get("line_count", -1))
        except (TypeError, ValueError):
            failed_artifacts.append(artifact_id or "invalid-size")
            continue
        if len(payload_bytes) != expected_bytes or len(payload.splitlines()) != expected_lines:
            failed_artifacts.append(artifact_id or "size-mismatch")
            warnings.append(f"portfolio artifact size metadata mismatch: {relative_path}")
            continue
        if not boundary_ok:
            continue
        verified_artifact_count += 1

    actual_paths = {
        item.relative_to(root).as_posix()
        for item in _iter_files(root)
        if item.is_file() or item.is_symlink()
    }
    unexpected_paths = tuple(sorted(actual_paths - declared_paths))
    if unexpected_paths:
        warnings.append("unexpected files are present in the portfolio release")

    raw_members = manifest.get("members", [])
    if not isinstance(raw_members, list):
        raise ValidationError("portfolio release manifest members must be an array")
    try:
        declared_member_count = int(manifest.get("member_count", -1))
    except (TypeError, ValueError):
        declared_member_count = -1
    if declared_member_count != len(raw_members):
        warnings.append("portfolio release member count mismatch")
    seen_runs: set[str] = set()
    verified_member_count = 0
    declared_artifact_ids = seen_ids
    for raw_member in raw_members:
        if not isinstance(raw_member, dict):
            failed_members.append("invalid-member")
            continue
        run_id = _text(raw_member.get("run_id", ""))
        if run_id in seen_runs or not run_id:
            failed_members.append(run_id or "duplicate-member")
            continue
        seen_runs.add(run_id)
        member_body = dict(raw_member)
        declared_member_address = _text(member_body.pop("content_address", ""))
        if not declared_member_address or _member_address(member_body) != declared_member_address:
            failed_members.append(run_id)
            warnings.append(f"portfolio member address mismatch: {run_id}")
            continue
        raw_ids = raw_member.get("artifact_ids", [])
        if not isinstance(raw_ids, list) or any(_text(item) not in declared_artifact_ids for item in raw_ids):
            failed_members.append(run_id)
            warnings.append(f"portfolio member artifact closure is incomplete: {run_id}")
            continue
        if _has_forbidden_key(raw_member) or contains_private_key(raw_member):
            failed_members.append(run_id)
            public_boundary_valid = False
            warnings.append(f"portfolio member violates the public boundary: {run_id}")
            continue
        verified_member_count += 1

    accepted = bool(
        manifest.get("accepted", False)
        and manifest_version_valid
        and manifest_address_valid
        and public_boundary_valid
        and path_safety_valid
        and declared_artifact_count == len(raw_artifacts)
        and declared_member_count == len(raw_members)
        and not failed_artifacts
        and not failed_members
        and not unexpected_paths
        and verified_artifact_count == len(raw_artifacts)
        and verified_member_count == len(raw_members)
    )
    body = {
        "path": str(root),
        "release_id": _text(manifest.get("release_id", "")),
        "accepted": accepted,
        "manifest_version_valid": manifest_version_valid,
        "manifest_address_valid": manifest_address_valid,
        "public_boundary_valid": public_boundary_valid,
        "path_safety_valid": path_safety_valid,
        "artifact_count": len(raw_artifacts),
        "verified_artifact_count": verified_artifact_count,
        "member_count": len(raw_members),
        "verified_member_count": verified_member_count,
        "failed_artifact_ids": tuple(sorted(failed_artifacts)),
        "failed_member_ids": tuple(sorted(failed_members)),
        "unexpected_paths": unexpected_paths,
        "warnings": tuple(sorted(set(warnings))),
    }
    return PortfolioReleaseVerification(**body, content_address=content_hash(body, prefix="portfolio-release-verification"))


__all__ = [
    "build_portfolio_release",
    "render_portfolio_release_report",
    "verify_portfolio_release_bundle",
    "write_portfolio_release_bundle",
]
