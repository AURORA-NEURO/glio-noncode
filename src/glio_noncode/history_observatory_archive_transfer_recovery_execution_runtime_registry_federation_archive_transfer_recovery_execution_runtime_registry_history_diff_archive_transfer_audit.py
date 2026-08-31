"""Independent assurance for history-diff archive transfer manifests."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_transfer as transfer_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash


VERSION = transfer_model.VERSION + "-audit-v1"
BOUNDARY = transfer_model.BOUNDARY + "_audit"
AUDIT_PREFIX = transfer_model.TRANSFER_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "version",
    "boundary",
    "transfer-address",
    "chunk-order",
    "range-conservation",
    "chunk-receipts",
    "archive-linkage",
    "manifest-address",
    "manifest-fields",
    "canonical-bytes",
    "payload-replay",
    "nested-archive",
    "progress-replay",
    "mapping-round-trip",
    "public-boundary",
    "bound-conservation",
    "chunk-addresses",
    "deterministic-bytes",
)
MAX_CHECKS = len(CHECK_IDS)
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("transfer_address", "archive_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, allow_pending: bool = False) -> str:
    value = _text(value, field, 8192)
    if allow_pending and value.startswith("pending:"):
        return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a public address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    lower = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < lower or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


class HistoryDiffArchiveTransferAuditCheck:
    """One independently addressed transfer assertion."""

    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "audit ordinal", MAX_CHECKS, positive=True)
        if check_id not in CHECK_IDS or CHECK_IDS[self.ordinal - 1] != check_id:
            raise ValidationError("audit check identity or order is invalid")
        self.check_id = check_id
        if not isinstance(passed, bool):
            raise ValidationError("audit check result must be boolean")
        self.passed = passed
        self.detail = _text(detail, "audit detail", 4096)
        self.evidence_addresses = tuple(_address(item, "audit evidence address") for item in _sequence(evidence_addresses, "audit evidence", 16))
        if not self.evidence_addresses:
            raise ValidationError("audit check needs evidence")
        self.content_address = _address(content_address, "audit check address", CHECK_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if not transfer_model._public(self.to_dict()):
            raise ValidationError("audit check crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_check(self) != self.content_address:
            raise ValidationError("audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> HistoryDiffArchiveTransferAuditCheck:
        value = _mapping(value, "history diff archive transfer audit check")
        _strict(value, set(cls.FIELDS), "history diff archive transfer audit check")
        return cls(*(value[field] for field in cls.FIELDS))


class HistoryDiffArchiveTransferAudit:
    """The fixed-size independent audit of a transfer manifest."""

    FIELDS = AUDIT_FIELDS

    def __init__(self, transfer_address: str, archive_address: str, checks: Sequence[HistoryDiffArchiveTransferAuditCheck], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.transfer_address = _address(transfer_address, "audit transfer address", transfer_model.TRANSFER_PREFIX)
        self.archive_address = _address(archive_address, "audit archive address", transfer_model.archive_model.ARCHIVE_PREFIX)
        self.checks = tuple(item if isinstance(item, HistoryDiffArchiveTransferAuditCheck) else HistoryDiffArchiveTransferAuditCheck.from_mapping(item) for item in _sequence(checks, "audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "audit check count", MAX_CHECKS, positive=True)
        self.passed_count = _count(passed_count, "audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "audit failed count", MAX_CHECKS)
        if not isinstance(accepted, bool):
            raise ValidationError("audit acceptance must be boolean")
        self.accepted = accepted
        self.content_address = _address(content_address, "audit address", AUDIT_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.check_count != MAX_CHECKS or len(self.checks) != MAX_CHECKS or tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("audit checks are incomplete or out of order")
        if self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0):
            raise ValidationError("audit counts or acceptance do not replay")
        if any(self.transfer_address not in item.evidence_addresses for item in self.checks):
            raise ValidationError("audit evidence does not retain the transfer address")
        if not transfer_model._public(self.to_dict()):
            raise ValidationError("audit crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_audit(self) != self.content_address:
            raise ValidationError("audit address does not replay")

    @property
    def passed(self) -> bool:
        return self.accepted

    def to_dict(self) -> dict[str, Any]:
        return {"transfer_address": self.transfer_address, "archive_address": self.archive_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> HistoryDiffArchiveTransferAudit:
        value = _mapping(value, "history diff archive transfer audit")
        _strict(value, set(cls.FIELDS), "history diff archive transfer audit")
        return cls(value["transfer_address"], value["archive_address"], tuple(HistoryDiffArchiveTransferAuditCheck.from_mapping(item) for item in _sequence(value["checks"], "audit checks", MAX_CHECKS)), value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_check(value: HistoryDiffArchiveTransferAuditCheck) -> str:
    if not isinstance(value, HistoryDiffArchiveTransferAuditCheck):
        raise ValidationError("audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


def address_audit(value: HistoryDiffArchiveTransferAudit) -> str:
    if not isinstance(value, HistoryDiffArchiveTransferAudit):
        raise ValidationError("audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> HistoryDiffArchiveTransferAuditCheck:
    provisional = HistoryDiffArchiveTransferAuditCheck(ordinal, check_id, bool(passed), detail, evidence, "pending:check")
    return HistoryDiffArchiveTransferAuditCheck(ordinal, check_id, bool(passed), detail, evidence, address_check(provisional))


def _replay_checks(value: transfer_model.HistoryDiffArchiveTransfer) -> tuple[HistoryDiffArchiveTransferAuditCheck, ...]:
    transfer_address = value.content_address
    archive_address = value.archive_address
    manifest = transfer_model.manifest_document(value)
    evidence = (transfer_address, archive_address)
    order_ok = tuple(item.index for item in value.chunks) == tuple(range(value.chunk_count)) and tuple(item.offset for item in value.chunks) == tuple(sum(chunk.size for chunk in value.chunks[:index]) for index in range(value.chunk_count))
    range_ok = sum(item.size for item in value.chunks) == value.archive_size and value.chunk_count == (value.archive_size + value.chunk_size - 1) // value.chunk_size
    receipts_ok = all(item.content_address.startswith(transfer_model.CHUNK_PREFIX + ":") and item.size > 0 for item in value.chunks)
    payload_ok = True
    nested_ok = True
    if value._payload:
        try:
            assembled = transfer_model.assemble_archive_bytes(value)
            payload_ok = all(len(value._payload[item.index]) == item.size and transfer_model.address_chunk(value._payload[item.index]) == item.content_address for item in value.chunks)
            nested_ok = transfer_model.archive_model.load_archive_bytes(assembled).content_address == archive_address
        except ValidationError:
            payload_ok = False
            nested_ok = False
    manifest_fields = all(manifest[field] == value.to_dict()[field] for field in ("version", "boundary", "transfer_id", "archive_address", "archive_size", "chunk_size", "chunk_count", "chunks")) and manifest["transfer_address"] == transfer_address
    canonical_ok = canonical_bytes(manifest) == transfer_model.manifest_json(value).encode("utf-8")
    progress = transfer_model.HistoryDiffArchiveTransferAssembler(value).progress()
    progress_ok = progress.received_indices == () and progress.missing_indices == tuple(range(value.chunk_count)) and not progress.complete
    mapping_ok = transfer_model.transfer_from_mapping(value.to_dict()).to_dict() == value.to_dict()
    public_ok = transfer_model._public(value.to_dict()) and transfer_model._public(manifest)
    bounds_ok = value.archive_size <= transfer_model.MAX_TRANSFER_BYTES and value.chunk_count <= transfer_model.MAX_CHUNKS and transfer_model.MIN_CHUNK_SIZE <= value.chunk_size <= transfer_model.MAX_CHUNK_SIZE
    rematerialized = transfer_model.transfer_from_mapping(value.to_dict())
    deterministic_ok = transfer_model.address_transfer(rematerialized) == transfer_address and transfer_model.manifest_json(rematerialized) == transfer_model.manifest_json(value)
    return (
        _check(1, "version", value.version == transfer_model.VERSION, "transfer version is current", evidence),
        _check(2, "boundary", value.boundary == transfer_model.BOUNDARY, "transfer boundary is public and value-free", evidence),
        _check(3, "transfer-address", transfer_model.address_transfer(value) == transfer_address, "transfer address replays from the public manifest", (transfer_address,)),
        _check(4, "chunk-order", order_ok, "chunk indices and offsets are canonical", (transfer_address, *(tuple(item.content_address for item in value.chunks[:2]) or evidence))),
        _check(5, "range-conservation", range_ok, "chunk ranges conserve archive bytes", evidence),
        _check(6, "chunk-receipts", receipts_ok, "each chunk has a bounded addressed receipt", (transfer_address, *(tuple(item.content_address for item in value.chunks[:2]) or evidence))),
        _check(7, "archive-linkage", archive_address.startswith(transfer_model.archive_model.ARCHIVE_PREFIX + ":"), "transfer retains the history-diff archive address", evidence),
        _check(8, "manifest-address", manifest["manifest_address"].startswith(transfer_model.MANIFEST_PREFIX + ":"), "manifest receipt is addressed", (manifest["manifest_address"], transfer_address)),
        _check(9, "manifest-fields", manifest_fields, "manifest fields replay the transfer", (manifest["manifest_address"], transfer_address)),
        _check(10, "canonical-bytes", canonical_ok, "manifest JSON is canonical", (transfer_address, manifest["manifest_address"])),
        _check(11, "payload-replay", payload_ok, "available chunk payloads replay their receipts", evidence),
        _check(12, "nested-archive", nested_ok, "complete payload reassembles through the nested archive verifier", (archive_address, transfer_address)),
        _check(13, "progress-replay", progress_ok, "an empty receiver reports every chunk missing", (progress.content_address, transfer_address)),
        _check(14, "mapping-round-trip", mapping_ok, "public transfer mapping round-trips", (transfer_address,)),
        _check(15, "public-boundary", public_ok, "transfer and manifest contain only public bounded fields", (transfer_address, manifest["manifest_address"])),
        _check(16, "bound-conservation", bounds_ok, "transfer size, chunk count, and chunk policy remain bounded", evidence),
        _check(17, "chunk-addresses", all(item.content_address.startswith(transfer_model.CHUNK_PREFIX + ":") for item in value.chunks), "chunk address identities use the transfer namespace", (transfer_address, *(tuple(item.content_address for item in value.chunks[:2]) or evidence))),
        _check(18, "deterministic-bytes", deterministic_ok, "manifest and transfer addresses replay deterministically", (transfer_address, manifest["manifest_address"])),
    )


def audit_transfer(value: transfer_model.HistoryDiffArchiveTransfer) -> HistoryDiffArchiveTransferAudit:
    if not isinstance(value, transfer_model.HistoryDiffArchiveTransfer):
        raise ValidationError("transfer audit requires a typed history diff archive transfer")
    transfer_model.verify_transfer(value)
    checks = _replay_checks(value)
    body = {"transfer_address": value.content_address, "archive_address": value.archive_address, "checks": checks, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": all(item.passed for item in checks)}
    provisional = HistoryDiffArchiveTransferAudit(**body, content_address="pending:audit")
    return HistoryDiffArchiveTransferAudit(**body, content_address=address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> HistoryDiffArchiveTransferAudit:
    return HistoryDiffArchiveTransferAudit.from_mapping(value)


def verify_audit(value: HistoryDiffArchiveTransferAudit) -> HistoryDiffArchiveTransferAudit:
    if not isinstance(value, HistoryDiffArchiveTransferAudit):
        raise ValidationError("transfer audit verification requires a typed audit")
    value._validate()
    if not value.accepted:
        raise ValidationError("transfer audit contains failed checks")
    return value


def audit_json(value: HistoryDiffArchiveTransferAudit) -> str:
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value: HistoryDiffArchiveTransferAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=HistoryDiffArchiveTransferAuditCheck.FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_audit_markdown(value: HistoryDiffArchiveTransferAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    lines = ["# Federation History-Diff Archive Transfer Audit", "", f"- Transfer: `{value.transfer_address}`", f"- Archive: `{value.archive_address}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{str(value.accepted).lower()}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{str(item.passed).lower()}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Federation history-diff archive transfer audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_CHECKS}, "check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 16}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Federation history-diff archive transfer audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"transfer_address": {"type": "string", "pattern": "^" + transfer_model.TRANSFER_PREFIX + ":"}, "archive_address": {"type": "string", "pattern": "^" + transfer_model.archive_model.ARCHIVE_PREFIX + ":"}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "check_count": {"type": "integer", "const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_count": MAX_CHECKS, "checks": list(CHECK_IDS), "features": ["independent range recomputation", "manifest receipt replay", "nested history-diff archive replay", "empty-progress replay", "mapping round-trip", "public-boundary check", "JSON CSV and Markdown projections"], "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "HistoryDiffArchiveTransferAudit", "HistoryDiffArchiveTransferAuditCheck", "VERSION", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_schema", "audit_transfer", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
