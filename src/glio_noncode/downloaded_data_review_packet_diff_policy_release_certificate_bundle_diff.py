"""Source-free longitudinal diffs between downloaded-data release bundles."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import downloaded_data_review_packet_diff_policy_release_certificate_bundle as bundle_model
from .downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_contracts import (
    BOUNDARY,
    BUNDLE_PREFIX,
    CHANGES,
    DIFF_PREFIX,
    DIRECTIONS,
    ITEM_PREFIX,
    MAX_ITEMS,
    MAX_LIMIT,
    RESOURCE_FIELDS,
    RESOURCES,
    STATE_TRANSITIONS,
    VERSION,
    DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiff,
    DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffItem,
    address_diff,
    address_item,
    capabilities,
    diff_schema,
    item_schema,
)
from ._safe_persistence import _validate_parent, atomic_write_text, read_text
from .errors import ValidationError
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash

DEFAULT_DIFF_ID = DIFF_PREFIX


def _label(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 256 or value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = True) -> str:
    value = _text(value, field, 4096, required=required)
    if value and ("/" in value or "\\" in value or '"' in value or ":" not in value):
        raise ValidationError(f"{field} must be a content address")
    if prefix is not None and value and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _item(ordinal: int, resource: str, identity: str, left: Mapping[str, Any] | None, right: Mapping[str, Any] | None, left_address: str, right_address: str) -> DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffItem:
    left_snapshot = dict(left or {})
    right_snapshot = dict(right or {})
    changed_fields = tuple(name for name in RESOURCE_FIELDS[resource] if left_snapshot.get(name) != right_snapshot.get(name))
    change = "added" if left is None else "removed" if right is None else "unchanged" if not changed_fields else "changed"
    body = {"ordinal": ordinal, "resource": resource, "identity": identity, "change": change, "changed_fields": changed_fields, "left_address": left_address if left is not None else "", "right_address": right_address if right is not None else "", "left_snapshot": left_snapshot, "right_snapshot": right_snapshot, "content_address": ITEM_PREFIX + ":pending"}
    provisional = DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffItem(**body)
    return DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffItem(**(body | {"content_address": address_item(provisional)}))


def _paired(resource: str, left_rows: Mapping[str, tuple[Mapping[str, Any], str]], right_rows: Mapping[str, tuple[Mapping[str, Any], str]], ordinal: int) -> tuple[DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffItem, ...]:
    rows: list[DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffItem] = []
    for identity in sorted(set(left_rows) | set(right_rows)):
        left = left_rows.get(identity)
        right = right_rows.get(identity)
        rows.append(_item(ordinal + len(rows), resource, identity, left[0] if left else None, right[0] if right else None, left[1] if left else "", right[1] if right else ""))
    return tuple(rows)


def _rows(bundle: Any) -> dict[str, dict[str, tuple[Mapping[str, Any], str]]]:
    certificate, certificate_audit, run, run_audit, package, _review = bundle_model.load_bundle(bundle)
    return {
        "certificate": {"decision": ({"profile": certificate.profile, "policy_state": certificate.policy_state, "policy_accepted": certificate.policy_accepted, "release_state": certificate.release_state, "release_eligible": certificate.release_eligible}, certificate.content_address)},
        "run": {"summary": ({"diff_item_count": run.diff_item_count, "diff_changed_count": run.diff_changed_count, "policy_passed_count": run.policy_passed_count, "policy_failed_count": run.policy_failed_count, "package_byte_count": run.package_byte_count}, run.content_address)},
        "package": {"summary": ({"package_byte_count": len(package.package_bytes), "member_count": len(package.manifest.members), "package_address": package.package_address}, package.package_address)},
        "audits": {
            "run-audit": ({"run_audit_accepted": run_audit.accepted, "policy_audit_accepted": certificate.policy_audit_accepted, "package_audit_accepted": certificate.package_audit_accepted, "certificate_audit_accepted": certificate_audit.accepted}, run_audit.content_address),
        },
        "members": {item.relative_path: ({"media_type": item.media_type, "byte_count": item.byte_count, "byte_address": item.byte_address, "content_address": item.content_address}, item.content_address) for item in bundle.manifest.members},
    }


def build_diff(left: Any, right: Any, *, diff_id: str = DEFAULT_DIFF_ID) -> DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiff:
    left_bundle = bundle_model.verify_bundle(left)
    right_bundle = bundle_model.verify_bundle(right)
    left_certificate, _left_certificate_audit, left_run, _left_run_audit, _left_package, _left_review = bundle_model.load_bundle(left_bundle)
    right_certificate, _right_certificate_audit, right_run, _right_run_audit, _right_package, _right_review = bundle_model.load_bundle(right_bundle)
    if left_run.packet_id != right_run.packet_id:
        raise ValidationError("release bundle diff requires matching downloaded-data packet IDs")
    items: list[DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffItem] = []
    left_rows = _rows(left_bundle)
    right_rows = _rows(right_bundle)
    for resource in RESOURCES:
        items.extend(_paired(resource, left_rows[resource], right_rows[resource], len(items) + 1))
    counts = {change: sum(item.change == change for item in items) for change in CHANGES}
    state_transition = "blocked-to-ready" if left_certificate.release_state == "blocked" and right_certificate.release_state == "ready" else "ready-to-blocked" if left_certificate.release_state == "ready" and right_certificate.release_state == "blocked" else "same-ready" if left_certificate.release_state == "ready" else "same-blocked"
    direction = "unchanged" if counts["added"] + counts["removed"] + counts["changed"] == 0 else "improved" if not left_certificate.release_eligible and right_certificate.release_eligible else "regressed" if left_certificate.release_eligible and not right_certificate.release_eligible else "changed"
    body = {"diff_id": _label(diff_id, "release bundle diff ID"), "version": VERSION, "boundary": BOUNDARY, "packet_id": _label(left_run.packet_id, "release bundle diff packet ID"), "left_bundle_address": left_bundle.bundle_address, "right_bundle_address": right_bundle.bundle_address, "left_release_state": left_certificate.release_state, "right_release_state": right_certificate.release_state, "left_release_eligible": left_certificate.release_eligible, "right_release_eligible": right_certificate.release_eligible, "state_transition": state_transition, "direction": direction, "added_count": counts["added"], "removed_count": counts["removed"], "changed_count": counts["changed"], "unchanged_count": counts["unchanged"], "items": tuple(items), "content_address": DIFF_PREFIX + ":pending"}
    provisional = DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiff(**body)
    return DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiff(**(body | {"content_address": address_diff(provisional)}))


def verify_diff(value: Any) -> DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiff:
    diff = value if isinstance(value, DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiff) else load_diff(value)
    if address_diff(diff) != diff.content_address:
        raise ValidationError("release bundle diff address does not replay")
    if _has_forbidden_key(diff.to_dict()):
        raise ValidationError("release bundle diff crosses the public boundary")
    return DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiff.from_mapping(diff.to_dict())


def load_diff(value: bytes | bytearray | str | Path | Mapping[str, Any]) -> DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiff:
    if isinstance(value, Mapping):
        raw = dict(value)
    elif isinstance(value, (bytes, bytearray)):
        raw = _strict_json_loads(bytes(value).decode("utf-8"))
    else:
        raw = _strict_json_loads(read_text(value, field="downloaded-data release bundle diff", max_bytes=16 * 1024 * 1024))
    return DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiff.from_mapping(raw)


def diff_json(value: Any) -> str:
    return canonical_json(verify_diff(value).to_dict()) + "\n"


def write_diff(value: Any, destination: str | Path, *, allow_existing: bool = False) -> DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiff:
    diff = verify_diff(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("release bundle diff destination already exists")
    if path.exists() and not path.is_file():
        raise ValidationError("release bundle diff destination is not a file")
    _validate_parent(path.parent, "release bundle diff destination")
    atomic_write_text(path, diff_json(diff), field="release bundle diff destination")
    return diff


def query_diff(value: Any, *, resource: str = "", change: str = "", direction: str = "", text: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    diff = verify_diff(value)
    resource = _text(resource, "release bundle diff query resource", 64, required=False)
    change = _text(change, "release bundle diff query change", 64, required=False)
    direction = _text(direction, "release bundle diff query direction", 64, required=False)
    text = _text(text, "release bundle diff query text", required=False)
    if resource and resource not in RESOURCES or change and change not in CHANGES or direction and direction not in DIRECTIONS or offset < 0 or limit < 1 or limit > MAX_LIMIT:
        raise ValidationError("release bundle diff query filters are invalid")
    matches = tuple(item for item in diff.items if (not resource or item.resource == resource) and (not change or item.change == change) and (not direction or diff.direction == direction) and (not text or text.casefold() in " ".join((item.resource, item.identity, item.change, *item.changed_fields)).casefold()))
    selected = matches[offset:offset + limit]
    result = {"diff_address": diff.content_address, "resource": resource, "change": change, "direction": direction, "text": text, "offset": offset, "limit": limit, "total": len(diff.items), "matched": len(matches), "returned": len(selected), "truncated": offset + len(selected) < len(matches), "items": tuple(item.to_dict() for item in selected)}
    return result | {"content_address": content_hash(result, prefix=DIFF_PREFIX + "-query")}


def diff_csv(value: Any, *, resource: str = "", change: str = "", direction: str = "", text: str = "", offset: int = 0, limit: int = 50) -> str:
    result = query_diff(value, resource=resource, change=change, direction=direction, text=text, offset=offset, limit=limit)
    stream = io.StringIO(newline="")
    fields = ("ordinal", "resource", "identity", "change", "changed_fields", "left_address", "right_address", "content_address")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in result["items"]:
        writer.writerow({field: ",".join(item[field]) if field == "changed_fields" else item[field] for field in fields})
    return stream.getvalue()


def render_diff_markdown(value: Any) -> str:
    diff = verify_diff(value)
    lines = ["# Downloaded Data Release Bundle Diff", "", f"- Packet ID: `{diff.packet_id}`", f"- Direction: **{diff.direction}**", f"- State transition: **{diff.state_transition}**", f"- Added / removed / changed / unchanged: **{diff.added_count} / {diff.removed_count} / {diff.changed_count} / {diff.unchanged_count}**", f"- Diff address: `{diff.content_address}`", "", "| # | resource | identity | change | fields |", "| ---: | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.resource}` | `{item.identity}` | `{item.change}` | `{', '.join(item.changed_fields)} |" for item in diff.items)
    return "\n".join(lines) + "\n"


__all__ = ["DEFAULT_DIFF_ID", "build_diff", "capabilities", "diff_csv", "diff_json", "diff_schema", "item_schema", "load_diff", "query_diff", "render_diff_markdown", "verify_diff", "write_diff"]
