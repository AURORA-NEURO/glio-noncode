"""Independent audit for complete downloaded-data review runs."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import downloaded_data_review_packet_diff_policy_package as package_model
from . import downloaded_data_review_packet_diff_policy_package_audit as package_audit_model
from . import downloaded_data_review_packet_diff_policy_run as run_model
from . import downloaded_data_review_packet_diff_policy_run_contracts as run_contracts
from ._safe_persistence import _validate_parent, atomic_write_text, read_text
from .errors import ValidationError
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash

AUDIT_VERSION = run_contracts.VERSION + "-audit-v1"
AUDIT_BOUNDARY = run_contracts.BOUNDARY + "_audit"
AUDIT_PREFIX = run_contracts.RUN_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "audit-address", "audit-canonical", "audit-profile", "audit-packet-lineage", "audit-diff-lineage",
    "audit-policy-lineage", "audit-policy-audit-lineage", "audit-package-availability", "audit-package-lineage",
    "audit-package-audit-lineage", "audit-state", "audit-counts", "audit-public-boundary",
)
MAX_LIMIT = 256


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 256)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field, 4096)
    if not value.startswith(prefix + ":") or len(value.rsplit(":", 1)[-1]) != 64:
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


class DownloadedDataReviewPacketDiffPolicyRunAuditCheck:
    FIELDS = ("check_id", "passed", "observed", "required", "detail", "content_address")

    def __init__(self, check_id: str, passed: bool, observed: Any, required: Any, detail: str, content_address: str) -> None:
        self.check_id = _label(check_id, "review run audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("review run audit check ID is unsupported")
        if not isinstance(passed, bool):
            raise ValidationError("review run audit check result must be boolean")
        self.passed = passed
        self.observed = observed
        self.required = required
        self.detail = _text(detail, "review run audit detail", 2048)
        self.content_address = _address(content_address, "review run audit check address", CHECK_PREFIX) if not content_address.endswith(":pending") else content_address
        if not content_address.endswith(":pending") and address_check(self) != content_address:
            raise ValidationError("review run audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataReviewPacketDiffPolicyRunAuditCheck:
        if not isinstance(value, Mapping) or set(value) != set(cls.FIELDS):
            raise ValidationError("review run audit check fields are not exact")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataReviewPacketDiffPolicyRunAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataReviewPacketDiffPolicyRunAudit:
    FIELDS = ("run_id", "run_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, run_id: str, run_address: str, checks: tuple[DownloadedDataReviewPacketDiffPolicyRunAuditCheck, ...], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.run_id = _label(run_id, "review run audit run ID")
        self.run_address = _address(run_address, "review run audit run address", run_contracts.RUN_PREFIX)
        self.checks = tuple(checks)
        self.check_count = check_count
        self.passed_count = passed_count
        self.failed_count = failed_count
        self.accepted = accepted
        self.content_address = _address(content_address, "review run audit address", AUDIT_PREFIX) if not content_address.endswith(":pending") else content_address
        if self.check_count != len(self.checks) or self.check_count != len(CHECK_IDS) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0):
            raise ValidationError("review run audit aggregates do not replay")
        if not content_address.endswith(":pending") and address_audit(self) != content_address:
            raise ValidationError("review run audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"run_id": self.run_id, "run_address": self.run_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataReviewPacketDiffPolicyRunAudit:
        if not isinstance(value, Mapping) or set(value) != set(cls.FIELDS):
            raise ValidationError("review run audit fields are not exact")
        return cls(value["run_id"], value["run_address"], tuple(DownloadedDataReviewPacketDiffPolicyRunAuditCheck.from_mapping(item) for item in value["checks"]), value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: DownloadedDataReviewPacketDiffPolicyRunAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> DownloadedDataReviewPacketDiffPolicyRunAuditCheck:
    body = {"check_id": check_id, "passed": bool(passed), "observed": observed, "required": required, "detail": detail, "content_address": CHECK_PREFIX + ":pending"}
    provisional = DownloadedDataReviewPacketDiffPolicyRunAuditCheck(**body)
    return DownloadedDataReviewPacketDiffPolicyRunAuditCheck(**(body | {"content_address": address_check(provisional)}))


def _receipt(run_id: str, run_address: str, checks: tuple[DownloadedDataReviewPacketDiffPolicyRunAuditCheck, ...]) -> DownloadedDataReviewPacketDiffPolicyRunAudit:
    body = {"run_id": run_id or "unavailable", "run_address": run_address or run_contracts.RUN_PREFIX + ":" + "0" * 64, "checks": checks, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": bool(checks) and all(item.passed for item in checks), "content_address": AUDIT_PREFIX + ":pending"}
    provisional = DownloadedDataReviewPacketDiffPolicyRunAudit(**body)
    return DownloadedDataReviewPacketDiffPolicyRunAudit(**(body | {"content_address": address_audit(provisional)}))


def audit_run(value: Any, *, package: Any | None = None) -> DownloadedDataReviewPacketDiffPolicyRunAudit:
    try:
        run = run_model.verify_run(value, package=package)
        package_value = package_model.verify_package(package) if package is not None else None
        package_audit = package_audit_model.audit_package(package_value) if package_value is not None else None
        checks = (
            _check("audit-address", run_contracts.address_run(run) == run.content_address, run.content_address, "replayable", "run address replays"),
            _check("audit-canonical", run_model.run_json(run) == canonical_json(run.to_dict()) + "\n", "canonical", "canonical", "run JSON reload is canonical"),
            _check("audit-profile", run.profile in run_contracts.PROFILES, run.profile, run_contracts.PROFILES, "run profile is supported"),
            _check("audit-packet-lineage", run.left_packet_address.startswith(run_contracts.PACKET_PREFIX + ":") and run.right_packet_address.startswith(run_contracts.PACKET_PREFIX + ":") and run.left_packet_address != run.right_packet_address, (run.left_packet_address, run.right_packet_address), "packet namespaces and distinct addresses", "packet lineage is retained"),
            _check("audit-diff-lineage", run.diff_address.startswith(run_contracts.DIFF_PREFIX + ":"), run.diff_address, "diff namespace", "diff lineage is retained"),
            _check("audit-policy-lineage", run.policy_address.startswith(run_contracts.POLICY_PREFIX + ":") and run.policy_state == ("ready" if run.policy_accepted else "blocked"), {"address": run.policy_address, "state": run.policy_state}, "addressed and state-conserving", "policy lineage and state replay"),
            _check("audit-policy-audit-lineage", run.policy_audit_address.startswith(run_contracts.POLICY_AUDIT_PREFIX + ":") and run.policy_audit_accepted, run.policy_audit_address, "accepted policy audit", "policy audit lineage is retained"),
            _check("audit-package-availability", package_value is not None, "available" if package_value is not None else "missing", "available", "package bytes are supplied for independent audit"),
            _check("audit-package-lineage", package_value is not None and package_value.package_address == run.package_address and package_value.manifest.diff_address == run.diff_address and package_value.manifest.policy_address == run.policy_address and package_value.manifest.audit_address == run.policy_audit_address, run.package_address, "package, diff, policy, and policy-audit lineage", "package lineage replays"),
            _check("audit-package-audit-lineage", package_audit is not None and package_audit.content_address == run.package_audit_address and package_audit.accepted == run.package_audit_accepted, run.package_audit_address, "accepted package audit", "package audit lineage replays"),
            _check("audit-state", run.policy_accepted == (run.policy_state == "ready") and run.package_audit_accepted and run.policy_audit_accepted, {"policy_state": run.policy_state, "policy_accepted": run.policy_accepted}, "conserving accepted evidence", "run state conserves all audit gates"),
            _check("audit-counts", run.diff_changed_count <= run.diff_item_count and run.policy_passed_count + run.policy_failed_count == run.policy_check_count and run.package_audit_passed_count <= run.package_audit_check_count, {"diff": (run.diff_changed_count, run.diff_item_count), "policy": (run.policy_passed_count, run.policy_failed_count, run.policy_check_count), "package_audit": (run.package_audit_passed_count, run.package_audit_check_count)}, "conserved", "run counters conserve their stages"),
            _check("audit-public-boundary", not _has_forbidden_key(run.to_dict()), "clean", "clean", "run receipt contains no prohibited public keys"),
        )
        return _receipt(run.run_id, run.content_address, checks)
    except Exception as exc:
        checks = tuple(_check(check_id, False, "unavailable", "replayable", f"review run audit unavailable: {exc}") for check_id in CHECK_IDS)
        return _receipt("unavailable", run_contracts.RUN_PREFIX + ":" + "0" * 64, checks)


def verify_audit(value: Any) -> DownloadedDataReviewPacketDiffPolicyRunAudit:
    audit = value if isinstance(value, DownloadedDataReviewPacketDiffPolicyRunAudit) else load_audit(value)
    if address_audit(audit) != audit.content_address:
        raise ValidationError("review run audit address does not replay")
    return DownloadedDataReviewPacketDiffPolicyRunAudit.from_mapping(audit.to_dict())


def load_audit(value: bytes | bytearray | str | Path | Mapping[str, Any]) -> DownloadedDataReviewPacketDiffPolicyRunAudit:
    if isinstance(value, Mapping):
        raw = value
    elif isinstance(value, (bytes, bytearray)):
        raw = _strict_json_loads(bytes(value).decode("utf-8"))
    else:
        raw = _strict_json_loads(read_text(value, field="downloaded-data review run audit", max_bytes=16 * 1024 * 1024))
    return DownloadedDataReviewPacketDiffPolicyRunAudit.from_mapping(raw)


def audit_json(value: Any) -> str:
    return canonical_json(verify_audit(value).to_dict()) + "\n"


def write_audit(value: Any, destination: str | Path, *, allow_existing: bool = False) -> DownloadedDataReviewPacketDiffPolicyRunAudit:
    audit = verify_audit(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("downloaded-data review run audit destination already exists")
    _validate_parent(path.parent, "downloaded-data review run audit destination")
    atomic_write_text(path, audit_json(audit), field="downloaded-data review run audit destination")
    return audit


def query_audit(value: Any, *, passed: bool | None = None, text: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    audit = verify_audit(value)
    if passed is not None and not isinstance(passed, bool):
        raise ValidationError("review run audit passed filter must be boolean")
    if not isinstance(text, str) or len(text) > 4096 or offset < 0 or limit < 1 or limit > MAX_LIMIT:
        raise ValidationError("review run audit query bounds are invalid")
    matches = tuple(item for item in audit.checks if (passed is None or item.passed == passed) and (not text or text.casefold() in " ".join((item.check_id, item.detail, str(item.observed))).casefold()))
    selected = matches[offset:offset + limit]
    result = {"audit_address": audit.content_address, "passed": passed, "text": text, "offset": offset, "limit": limit, "total": len(audit.checks), "matched": len(matches), "returned": len(selected), "truncated": offset + len(selected) < len(matches), "checks": tuple(item.to_dict() for item in selected)}
    return result | {"content_address": content_hash(result, prefix=AUDIT_PREFIX + "-query")}


def audit_csv(value: Any, *, passed: bool | None = None, text: str = "", offset: int = 0, limit: int = 50) -> str:
    result = query_audit(value, passed=passed, text=text, offset=offset, limit=limit)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=DownloadedDataReviewPacketDiffPolicyRunAuditCheck.FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in result["checks"]:
        writer.writerow({field: canonical_json(item[field]) if field in {"observed", "required"} else item[field] for field in writer.fieldnames})
    return stream.getvalue()


def render_audit_markdown(value: Any) -> str:
    audit = verify_audit(value)
    lines = ["# Downloaded Data Review Run Audit", "", f"- Run: `{audit.run_address}`", f"- Result: **{audit.passed_count}/{audit.check_count}**", f"- Accepted: **{str(audit.accepted).lower()}**", "", "| check | passed | detail |", "| --- | --- | --- |"]
    lines.extend(f"| {item.check_id} | {str(item.passed).lower()} | {item.detail} |" for item in audit.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data review run audit check", "type": "object", "additionalProperties": False, "required": list(DownloadedDataReviewPacketDiffPolicyRunAuditCheck.FIELDS), "properties": {"check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "observed": {}, "required": {}, "detail": {"type": "string"}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data review run audit", "type": "object", "additionalProperties": False, "required": list(DownloadedDataReviewPacketDiffPolicyRunAudit.FIELDS), "properties": {"run_id": {"type": "string"}, "run_address": {"type": "string"}, "checks": {"type": "array", "minItems": len(CHECK_IDS), "maxItems": len(CHECK_IDS)}, "check_count": {"const": len(CHECK_IDS)}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": AUDIT_VERSION, "boundary": AUDIT_BOUNDARY, "check_ids": CHECK_IDS, "independent": True, "requires_package_bytes": True, "source_free": True, "content_addressed": True}


__all__ = ["audit_csv", "audit_json", "audit_schema", "audit_run", "capabilities", "check_schema", "load_audit", "query_audit", "render_audit_markdown", "verify_audit", "write_audit"]
