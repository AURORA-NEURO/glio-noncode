"""Run the complete downloaded-data packet, diff, policy, and handoff flow."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import downloaded_data_review_packet as packet_model
from . import downloaded_data_review_packet_diff as diff_model
from . import downloaded_data_review_packet_diff_policy as policy_model
from . import downloaded_data_review_packet_diff_policy_audit as policy_audit_model
from . import downloaded_data_review_packet_diff_policy_package as package_model
from . import downloaded_data_review_packet_diff_policy_package_audit as package_audit_model
from ._safe_persistence import _validate_parent, atomic_write_text, read_text
from .downloaded_data_review_packet_diff_policy_run_contracts import (
    BOUNDARY,
    PROFILES,
    RUN_PREFIX,
    VERSION,
    DownloadedDataReviewPacketDiffPolicyRun,
    address_run,
    capabilities,
    run_schema,
)
from .errors import ValidationError
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash

MAX_LIMIT = 256
RUN_RESOURCES = ("summary", "lineage", "diff", "policy", "package")


@dataclass(frozen=True)
class DownloadedDataReviewPacketDiffPolicyRunArtifacts:
    """In-memory typed products retained long enough to persist each receipt."""

    receipt: DownloadedDataReviewPacketDiffPolicyRun
    left_packet: Any
    right_packet: Any
    diff: Any
    policy: Any
    policy_audit: Any
    package: Any
    package_audit: Any

    def to_dict(self) -> dict[str, Any]:
        return self.receipt.to_dict()

    def summary(self) -> dict[str, Any]:
        return self.receipt.summary()


def _label(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 256 or value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _optional_count(value: int | None, field: str) -> int | None:
    if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > diff_model.MAX_ITEMS):
        raise ValidationError(f"{field} is outside its bound")
    return value


def _ordered_settings(
    profile: str,
    *,
    maximum_added: int | None,
    maximum_removed: int | None,
    maximum_changed: int | None,
    maximum_member_changed: int | None,
    maximum_field_changed: int | None,
    maximum_type_changed: int | None,
    allowed_resources: Sequence[str] | None,
    allowed_changes: Sequence[str] | None,
    allow_runtime_change: bool | None,
    require_change: bool,
) -> dict[str, Any]:
    if profile not in PROFILES:
        raise ValidationError("review run profile must be strict or release")
    release = profile == "release"
    defaults = (0, 0, 256, 64, 128, 64, True, False) if release else (0, 0, 0, 0, 0, 0, False, False)
    values = (maximum_added, maximum_removed, maximum_changed, maximum_member_changed, maximum_field_changed, maximum_type_changed)
    return {
        "maximum_added": defaults[0] if values[0] is None else _optional_count(values[0], "maximum added"),
        "maximum_removed": defaults[1] if values[1] is None else _optional_count(values[1], "maximum removed"),
        "maximum_changed": defaults[2] if values[2] is None else _optional_count(values[2], "maximum changed"),
        "maximum_member_changed": defaults[3] if values[3] is None else _optional_count(values[3], "maximum member changed"),
        "maximum_field_changed": defaults[4] if values[4] is None else _optional_count(values[4], "maximum field changed"),
        "maximum_type_changed": defaults[5] if values[5] is None else _optional_count(values[5], "maximum type changed"),
        "allowed_resources": tuple(allowed_resources) if allowed_resources is not None else diff_model.RESOURCES,
        "allowed_changes": tuple(allowed_changes) if allowed_changes is not None else diff_model.CHANGES,
        "allow_runtime_change": defaults[6] if allow_runtime_change is None else allow_runtime_change,
        "require_change": defaults[7] if not require_change else True,
    }


def _receipt(
    run_id: str,
    profile: str,
    packet_id: str,
    left_packet: Any,
    right_packet: Any,
    diff: Any,
    policy: Any,
    policy_audit: Any,
    package: Any,
    package_audit: Any,
) -> DownloadedDataReviewPacketDiffPolicyRun:
    body = {
        "run_id": run_id, "version": VERSION, "boundary": BOUNDARY, "profile": profile, "packet_id": packet_id,
        "left_packet_address": left_packet.packet_address, "right_packet_address": right_packet.packet_address,
        "left_packet_byte_count": len(left_packet.packet_bytes), "right_packet_byte_count": len(right_packet.packet_bytes),
        "diff_address": diff.content_address, "diff_item_count": len(diff.items), "diff_changed_count": sum(item.change == "changed" for item in diff.items),
        "policy_address": policy.content_address, "policy_check_count": policy.check_count, "policy_passed_count": policy.passed_count, "policy_failed_count": policy.failed_count,
        "policy_accepted": policy.accepted, "policy_state": policy.state, "policy_audit_address": policy_audit.content_address, "policy_audit_accepted": policy_audit.accepted,
        "package_address": package.package_address, "package_byte_count": len(package.package_bytes), "package_audit_address": package_audit.content_address,
        "package_audit_check_count": package_audit.check_count, "package_audit_passed_count": package_audit.passed_count, "package_audit_accepted": package_audit.accepted,
        "content_address": RUN_PREFIX + ":pending",
    }
    provisional = DownloadedDataReviewPacketDiffPolicyRun(**body)
    return DownloadedDataReviewPacketDiffPolicyRun(**(body | {"content_address": address_run(provisional)}))


def build_run(
    left_source: str | Path | bytes,
    right_source: str | Path | bytes,
    *,
    run_id: str = RUN_PREFIX,
    packet_id: str | None = None,
    profile: str = "strict",
    maximum_added: int | None = None,
    maximum_removed: int | None = None,
    maximum_changed: int | None = None,
    maximum_member_changed: int | None = None,
    maximum_field_changed: int | None = None,
    maximum_type_changed: int | None = None,
    allowed_resources: Sequence[str] | None = None,
    allowed_changes: Sequence[str] | None = None,
    allow_runtime_change: bool | None = None,
    require_change: bool = False,
) -> DownloadedDataReviewPacketDiffPolicyRunArtifacts:
    run_id = _label(run_id, "review run ID")
    packet_id = _label(packet_id or run_id + "-packets", "review run packet ID")
    settings = _ordered_settings(profile, maximum_added=maximum_added, maximum_removed=maximum_removed, maximum_changed=maximum_changed, maximum_member_changed=maximum_member_changed, maximum_field_changed=maximum_field_changed, maximum_type_changed=maximum_type_changed, allowed_resources=allowed_resources, allowed_changes=allowed_changes, allow_runtime_change=allow_runtime_change, require_change=require_change)
    left_packet = packet_model.build_from_download(left_source, packet_id=packet_id)
    right_packet = packet_model.build_from_download(right_source, packet_id=packet_id)
    diff = diff_model.build_diff(left_packet, right_packet, diff_id=run_id + "-diff")
    policy = policy_model.build_policy(diff, policy_id=profile + "-" + run_id + "-policy", **settings)
    policy_audit = policy_audit_model.audit_policy(policy)
    if not policy_audit.accepted:
        raise ValidationError("review run policy audit did not accept the typed policy")
    package = package_model.build_package(diff, policy, policy_audit, package_id=run_id + "-package")
    package_audit = package_audit_model.audit_package(package)
    if not package_audit.accepted:
        raise ValidationError("review run package audit did not accept the typed package")
    receipt = _receipt(run_id, profile, packet_id, left_packet, right_packet, diff, policy, policy_audit, package, package_audit)
    return DownloadedDataReviewPacketDiffPolicyRunArtifacts(receipt, left_packet, right_packet, diff, policy, policy_audit, package, package_audit)


def verify_run(value: Any, *, package: Any | None = None) -> DownloadedDataReviewPacketDiffPolicyRun:
    receipt = value.receipt if isinstance(value, DownloadedDataReviewPacketDiffPolicyRunArtifacts) else value if isinstance(value, DownloadedDataReviewPacketDiffPolicyRun) else load_run(value)
    if address_run(receipt) != receipt.content_address:
        raise ValidationError("downloaded-data review run address does not replay")
    if _has_forbidden_key(receipt.to_dict()):
        raise ValidationError("downloaded-data review run crosses the public boundary")
    if package is not None:
        package_value = package_model.verify_package(package)
        if package_value.package_address != receipt.package_address or len(package_value.package_bytes) != receipt.package_byte_count:
            raise ValidationError("review run package lineage does not replay")
    return DownloadedDataReviewPacketDiffPolicyRun.from_mapping(receipt.to_dict())


def load_run(value: bytes | bytearray | str | Path | Mapping[str, Any]) -> DownloadedDataReviewPacketDiffPolicyRun:
    if isinstance(value, Mapping):
        raw = dict(value)
    elif isinstance(value, (bytes, bytearray)):
        raw = _strict_json_loads(bytes(value).decode("utf-8"))
    else:
        raw = _strict_json_loads(read_text(value, field="downloaded-data review run", max_bytes=4 * 1024 * 1024))
    return DownloadedDataReviewPacketDiffPolicyRun.from_mapping(raw)


def run_json(value: Any) -> str:
    return canonical_json(verify_run(value).to_dict()) + "\n"


def write_run(value: Any, destination: str | Path, *, allow_existing: bool = False) -> DownloadedDataReviewPacketDiffPolicyRun:
    receipt = verify_run(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("downloaded-data review run destination already exists")
    if path.exists() and not path.is_file():
        raise ValidationError("downloaded-data review run destination is not a file")
    _validate_parent(path.parent, "downloaded-data review run destination")
    atomic_write_text(path, run_json(receipt), field="downloaded-data review run destination")
    return receipt


def query_run(value: Any, *, resource: str = "summary") -> dict[str, Any]:
    if resource not in RUN_RESOURCES:
        raise ValidationError("downloaded-data review run resource is unsupported")
    receipt = verify_run(value)
    if resource == "summary":
        result: Any = {"resource": resource, "value": receipt.to_dict()}
    elif resource == "lineage":
        result = {"resource": resource, "value": {"packet_id": receipt.packet_id, "left_packet_address": receipt.left_packet_address, "right_packet_address": receipt.right_packet_address, "diff_address": receipt.diff_address, "policy_address": receipt.policy_address, "policy_audit_address": receipt.policy_audit_address, "package_address": receipt.package_address, "package_audit_address": receipt.package_audit_address}}
    elif resource == "diff":
        result = {"resource": resource, "value": {"diff_address": receipt.diff_address, "item_count": receipt.diff_item_count, "changed_count": receipt.diff_changed_count}}
    elif resource == "policy":
        result = {"resource": resource, "value": {"profile": receipt.profile, "policy_address": receipt.policy_address, "check_count": receipt.policy_check_count, "passed_count": receipt.policy_passed_count, "failed_count": receipt.policy_failed_count, "accepted": receipt.policy_accepted, "state": receipt.policy_state, "audit_address": receipt.policy_audit_address, "audit_accepted": receipt.policy_audit_accepted}}
    else:
        result = {"resource": resource, "value": {"package_address": receipt.package_address, "package_byte_count": receipt.package_byte_count, "audit_address": receipt.package_audit_address, "audit_check_count": receipt.package_audit_check_count, "audit_passed_count": receipt.package_audit_passed_count, "audit_accepted": receipt.package_audit_accepted}}
    return result | {"run_address": receipt.content_address, "content_address": content_hash(result, prefix=RUN_PREFIX + "-query")}


def run_csv(value: Any) -> str:
    receipt = verify_run(value)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=("stage", "address", "state", "accepted", "count"), lineterminator="\n")
    writer.writeheader()
    rows = (
        {"stage": "diff", "address": receipt.diff_address, "state": "complete", "accepted": True, "count": receipt.diff_item_count},
        {"stage": "policy", "address": receipt.policy_address, "state": receipt.policy_state, "accepted": receipt.policy_accepted, "count": receipt.policy_check_count},
        {"stage": "policy-audit", "address": receipt.policy_audit_address, "state": "complete", "accepted": receipt.policy_audit_accepted, "count": receipt.policy_check_count},
        {"stage": "package", "address": receipt.package_address, "state": "complete", "accepted": True, "count": receipt.package_byte_count},
        {"stage": "package-audit", "address": receipt.package_audit_address, "state": "complete", "accepted": receipt.package_audit_accepted, "count": receipt.package_audit_check_count},
    )
    writer.writerows(rows)
    return stream.getvalue()


def render_run_markdown(value: Any) -> str:
    receipt = verify_run(value)
    return "\n".join((
        "# Downloaded Data Review Run", "", f"- Run: `{receipt.content_address}`", f"- Profile: **{receipt.profile}**", f"- Diff items: **{receipt.diff_item_count}**", f"- Changed items: **{receipt.diff_changed_count}**", f"- Policy: **{receipt.policy_state}** ({receipt.policy_passed_count}/{receipt.policy_check_count})", f"- Policy audit accepted: **{str(receipt.policy_audit_accepted).lower()}**", f"- Package bytes: **{receipt.package_byte_count}**", f"- Package audit: **{receipt.package_audit_passed_count}/{receipt.package_audit_check_count}**", "", "| stage | address | accepted |", "| --- | --- | --- |", f"| left packet | `{receipt.left_packet_address}` | true |", f"| right packet | `{receipt.right_packet_address}` | true |", f"| diff | `{receipt.diff_address}` | true |", f"| policy | `{receipt.policy_address}` | {str(receipt.policy_accepted).lower()} |", f"| policy audit | `{receipt.policy_audit_address}` | {str(receipt.policy_audit_accepted).lower()} |", f"| package | `{receipt.package_address}` | true |", f"| package audit | `{receipt.package_audit_address}` | {str(receipt.package_audit_accepted).lower()} |", "", "The receipt is source-free and contains structural addresses, counts, and decision state; source archive bytes and record values are not retained.", "", ))


__all__ = ["DownloadedDataReviewPacketDiffPolicyRunArtifacts", "build_run", "capabilities", "load_run", "query_run", "render_run_markdown", "run_csv", "run_json", "run_schema", "verify_run", "write_run"]
