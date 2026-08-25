"""Read-only query and comparison surfaces for portfolio release manifests."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .portfolio_release import verify_portfolio_release_bundle
from .portfolio_release_contracts import (
    PORTFOLIO_RELEASE_MANIFEST,
    PORTFOLIO_RELEASE_MAX_RUNS,
    PortfolioArtifactKind,
    PortfolioReleaseArtifact,
    PortfolioReleaseBundle,
    PortfolioReleaseCheck,
    PortfolioReleaseDiff,
    PortfolioReleaseMember,
    PortfolioReleaseQueryResult,
    PortfolioReleaseState,
)
from .serialization import content_hash


def _text(value: Any) -> str:
    """Normalize public query text."""

    return str(value).strip()


def _safe_limit(offset: int, limit: int) -> None:
    """Validate bounded query pagination."""

    if offset < 0:
        raise ValidationError("offset must be non-negative")
    if limit < 1 or limit > PORTFOLIO_RELEASE_MAX_RUNS:
        raise ValidationError(f"limit must be between 1 and {PORTFOLIO_RELEASE_MAX_RUNS}")


def _manifest(path: str | Path) -> dict[str, Any]:
    """Read one release manifest without trusting its derived fields."""

    root = Path(path)
    manifest_path = root / PORTFOLIO_RELEASE_MANIFEST
    if not root.is_dir() or not manifest_path.is_file():
        raise ValidationError("portfolio release manifest is missing")
    try:
        value = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError("portfolio release manifest is not valid JSON") from exc
    if not isinstance(value, dict):
        raise ValidationError("portfolio release manifest must be an object")
    return value


def _member(value: Mapping[str, Any]) -> PortfolioReleaseMember:
    """Hydrate a manifest member while preserving its immutable address."""

    try:
        state = PortfolioReleaseState(_text(value.get("state", "blocked")))
    except ValueError as exc:
        raise ValidationError("portfolio release member state is invalid") from exc
    artifact_ids = value.get("artifact_ids", [])
    failed = value.get("failed_check_ids", [])
    warnings = value.get("warnings", [])
    if not all(isinstance(item, list) for item in (artifact_ids, failed, warnings)):
        raise ValidationError("portfolio release member arrays are invalid")
    body = {
        "run_id": _text(value.get("run_id", "")),
        "case_id": _text(value.get("case_id", "")),
        "dossier_address": value.get("dossier_address"),
        "workspace_history_address": value.get("workspace_history_address"),
        "dossier_release_id": value.get("dossier_release_id"),
        "workspace_release_id": value.get("workspace_release_id"),
        "dossier_state": _text(value.get("dossier_state", "unavailable")),
        "workspace_state": _text(value.get("workspace_state", "unavailable")),
        "state": state,
        "accepted": bool(value.get("accepted", False)),
        "artifact_ids": tuple(_text(item) for item in artifact_ids),
        "failed_check_ids": tuple(_text(item) for item in failed),
        "warnings": tuple(_text(item) for item in warnings),
    }
    return PortfolioReleaseMember(
        **body,
        content_address=_text(value.get("content_address", "")),
    )


def _artifact(
    value: Mapping[str, Any],
    root: Path,
    *,
    include_payload: bool,
) -> PortfolioReleaseArtifact:
    """Hydrate one artifact and optionally read its exact bytes."""

    try:
        kind = PortfolioArtifactKind(_text(value.get("kind", "member")))
    except ValueError as exc:
        raise ValidationError("portfolio release artifact kind is invalid") from exc
    relative_path = _text(value.get("relative_path", ""))
    payload = ""
    if include_payload:
        target = root.joinpath(*Path(relative_path).parts)
        if not target.is_file():
            raise ValidationError(f"portfolio release artifact is missing: {relative_path}")
        try:
            payload = target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise ValidationError(f"portfolio release artifact is unreadable: {relative_path}") from exc
    return PortfolioReleaseArtifact(
        artifact_id=_text(value.get("artifact_id", "")),
        relative_path=relative_path,
        media_type=_text(value.get("media_type", "")),
        kind=kind,
        member_run_id=value.get("member_run_id"),
        byte_count=int(value.get("byte_count", -1)),
        line_count=int(value.get("line_count", -1)),
        content_address=_text(value.get("content_address", "")),
        payload=payload,
    )


def _members(manifest: Mapping[str, Any]) -> tuple[PortfolioReleaseMember, ...]:
    values = manifest.get("members", [])
    if not isinstance(values, list):
        raise ValidationError("portfolio release members must be an array")
    return tuple(sorted((_member(item) for item in values if isinstance(item, Mapping)), key=lambda item: item.run_id))


def _artifacts(
    manifest: Mapping[str, Any],
    root: Path,
    *,
    include_payloads: bool,
) -> tuple[PortfolioReleaseArtifact, ...]:
    values = manifest.get("artifacts", [])
    if not isinstance(values, list):
        raise ValidationError("portfolio release artifacts must be an array")
    return tuple(
        sorted(
            (_artifact(item, root, include_payload=include_payloads) for item in values if isinstance(item, Mapping)),
            key=lambda item: item.relative_path,
        )
    )


def load_portfolio_release_bundle(
    destination: str | Path,
    *,
    include_payloads: bool = False,
) -> PortfolioReleaseBundle:
    """Hydrate a verified directory into an immutable bundle projection."""

    root = Path(destination)
    verify_portfolio_release_bundle(root)
    manifest = _manifest(root)
    try:
        state = PortfolioReleaseState(_text(manifest.get("state", "blocked")))
    except ValueError as exc:
        raise ValidationError("portfolio release state is invalid") from exc
    raw_checks = manifest.get("checks", [])
    if not isinstance(raw_checks, list):
        raise ValidationError("portfolio release checks must be an array")
    checks = tuple(
        PortfolioReleaseCheck(
            check_id=_text(item.get("check_id", "")),
            passed=bool(item.get("passed", False)),
            observed=item.get("observed"),
            required=item.get("required"),
            detail=_text(item.get("detail", "")),
            scope=_text(item.get("scope", "portfolio")),
            content_address=_text(item.get("content_address", "")),
        )
        for item in raw_checks
        if isinstance(item, Mapping)
    )
    return PortfolioReleaseBundle(
        release_id=_text(manifest.get("release_id", "")),
        as_of=_text(manifest.get("as_of", "")),
        selection=dict(manifest.get("selection", {})) if isinstance(manifest.get("selection"), Mapping) else {},
        state=state,
        accepted=bool(manifest.get("accepted", False)),
        members=_members(manifest),
        artifacts=_artifacts(manifest, root, include_payloads=include_payloads),
        checks=checks,
        content_address=_text(manifest.get("content_address", "")),
    )


def query_portfolio_release(
    destination: str | Path,
    *,
    run_id: str | None = None,
    case_id: str | None = None,
    state: str | PortfolioReleaseState | None = None,
    artifact_kind: str | PortfolioArtifactKind | None = None,
    media_type: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = PORTFOLIO_RELEASE_MAX_RUNS,
    include_payloads: bool = False,
) -> PortfolioReleaseQueryResult:
    """Query a verified package's members and namespaced artifacts."""

    _safe_limit(offset, limit)
    root = Path(destination)
    verification = verify_portfolio_release_bundle(root)
    manifest = _manifest(root)
    members = _members(manifest)
    artifacts = _artifacts(manifest, root, include_payloads=include_payloads)
    normalized_state = _text(state.value if isinstance(state, PortfolioReleaseState) else state) if state else None
    if normalized_state and normalized_state not in {item.value for item in PortfolioReleaseState}:
        raise ValidationError("state is not a valid portfolio release state")
    normalized_kind = _text(artifact_kind.value if isinstance(artifact_kind, PortfolioArtifactKind) else artifact_kind) if artifact_kind else None
    if normalized_kind and normalized_kind not in {item.value for item in PortfolioArtifactKind}:
        raise ValidationError("artifact_kind is not a valid portfolio artifact kind")
    normalized_text = _text(text).casefold() if text else None
    selected_members = []
    for item in members:
        if run_id is not None and item.run_id != _text(run_id):
            continue
        if case_id is not None and item.case_id != _text(case_id):
            continue
        if normalized_state is not None and item.state.value != normalized_state:
            continue
        if normalized_text is not None:
            haystack = " ".join(
                (item.run_id, item.case_id, item.state.value, item.dossier_state, item.workspace_state, *item.warnings, *item.failed_check_ids)
            ).casefold()
            if normalized_text not in haystack:
                continue
        selected_members.append(item)
    selected_members = selected_members[offset : offset + limit]
    selected_run_ids = {item.run_id for item in selected_members}
    selected_artifacts = []
    for item in artifacts:
        if item.member_run_id is not None and item.member_run_id not in selected_run_ids:
            continue
        if normalized_kind is not None and item.kind.value != normalized_kind:
            continue
        if media_type is not None and item.media_type != _text(media_type):
            continue
        if normalized_text is not None and normalized_text not in f"{item.artifact_id} {item.relative_path} {item.kind.value}".casefold():
            continue
        selected_artifacts.append(item)
    query = {
        "run_id": run_id,
        "case_id": case_id,
        "state": normalized_state,
        "artifact_kind": normalized_kind,
        "media_type": media_type,
        "text": text,
        "offset": offset,
        "limit": limit,
        "include_payloads": include_payloads,
        "verified": verification.accepted,
    }
    body = {
        "query": query,
        "members": [item.to_dict() for item in selected_members],
        "artifacts": [item.to_dict(include_payload=include_payloads) for item in selected_artifacts],
        "total_members": len(members),
        "total_artifacts": len(artifacts),
        "accepted": verification.accepted,
    }
    return PortfolioReleaseQueryResult(
        query=query,
        members=tuple(selected_members),
        artifacts=tuple(selected_artifacts),
        total_members=len(members),
        total_artifacts=len(artifacts),
        accepted=verification.accepted,
        content_address=content_hash(body, prefix="portfolio-release-query"),
    )


def diff_portfolio_releases(
    left: str | Path,
    right: str | Path,
) -> PortfolioReleaseDiff:
    """Compare two verified packages by stable member and artifact addresses."""

    left_root = Path(left)
    right_root = Path(right)
    left_verification = verify_portfolio_release_bundle(left_root)
    right_verification = verify_portfolio_release_bundle(right_root)
    left_manifest = _manifest(left_root)
    right_manifest = _manifest(right_root)
    left_members = {item.run_id: item for item in _members(left_manifest)}
    right_members = {item.run_id: item for item in _members(right_manifest)}
    left_artifacts = {item.artifact_id: item for item in _artifacts(left_manifest, left_root, include_payloads=False)}
    right_artifacts = {item.artifact_id: item for item in _artifacts(right_manifest, right_root, include_payloads=False)}
    common_runs = tuple(sorted(set(left_members) & set(right_members)))
    common_artifacts = tuple(sorted(set(left_artifacts) & set(right_artifacts)))
    body = {
        "left_release_id": _text(left_manifest.get("release_id", "")),
        "right_release_id": _text(right_manifest.get("release_id", "")),
        "added_run_ids": tuple(sorted(set(right_members) - set(left_members))),
        "removed_run_ids": tuple(sorted(set(left_members) - set(right_members))),
        "common_run_ids": common_runs,
        "changed_run_ids": tuple(
            item for item in common_runs if left_members[item].content_address != right_members[item].content_address
        ),
        "added_artifact_ids": tuple(sorted(set(right_artifacts) - set(left_artifacts))),
        "removed_artifact_ids": tuple(sorted(set(left_artifacts) - set(right_artifacts))),
        "changed_artifact_ids": tuple(
            item for item in common_artifacts if left_artifacts[item].content_address != right_artifacts[item].content_address
        ),
        "accepted": (
            left_verification.manifest_version_valid
            and left_verification.manifest_address_valid
            and left_verification.public_boundary_valid
            and left_verification.path_safety_valid
            and not left_verification.failed_artifact_ids
            and not left_verification.failed_member_ids
            and not left_verification.unexpected_paths
            and right_verification.manifest_version_valid
            and right_verification.manifest_address_valid
            and right_verification.public_boundary_valid
            and right_verification.path_safety_valid
            and not right_verification.failed_artifact_ids
            and not right_verification.failed_member_ids
            and not right_verification.unexpected_paths
        ),
    }
    return PortfolioReleaseDiff(**body, content_address=content_hash(body, prefix="portfolio-release-diff"))


def export_portfolio_release_summary_csv(result: PortfolioReleaseQueryResult) -> str:
    """Export a query result's member rows without artifact payloads."""

    lines = [
        "run_id,case_id,state,accepted,dossier_state,workspace_state,artifact_count,failed_check_ids,warnings"
    ]
    for item in result.members:
        values = (
            item.run_id,
            item.case_id,
            item.state.value,
            str(item.accepted).lower(),
            item.dossier_state,
            item.workspace_state,
            str(item.artifact_count),
            ";".join(item.failed_check_ids),
            ";".join(item.warnings),
        )
        escaped = [f'"{value.replace(chr(34), chr(34) + chr(34))}"' for value in values]
        lines.append(",".join(escaped))
    return "\n".join(lines) + "\n"


__all__ = [
    "diff_portfolio_releases",
    "export_portfolio_release_summary_csv",
    "load_portfolio_release_bundle",
    "query_portfolio_release",
]
