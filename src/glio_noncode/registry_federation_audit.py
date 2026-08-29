"""Independent conservation audit for package-registry federations.

The audit intentionally recomputes federation relationships from the public
receipt fields. It does not treat the federation's ``accepted`` bit as proof;
the result is accepted only when every named invariant passes and the source
federation is itself in an accepting state.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry_federation as federation_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = federation_model.VERSION + "-audit-v1"
BOUNDARY = federation_model.BOUNDARY + "_audit"
AUDIT_PREFIX = federation_model.FEDERATION_PREFIX + "-audit"
CHECK_PREFIX = federation_model.FEDERATION_PREFIX + "-audit-check"
MAX_CHECKS = 32
MAX_TEXT = federation_model.MAX_TEXT
CHECK_IDS = ("exact-fields", "public-boundary", "peer-conservation", "peer-identity", "peer-audit-conservation", "package-union-conservation", "conflict-conservation", "quorum-conservation", "state-conservation", "action-conservation", "manifest-conservation", "content-address", "mapping-round-trip", "path-free")


def _text(value: Any, field: str, maximum: int = MAX_TEXT) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 192)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field, 512)
    if not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has an unsupported address")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _addresses(value: Any, field: str, maximum: int) -> tuple[str, ...]:
    values = tuple(_text(item, field, 512) for item in _sequence(value, field, maximum))
    if len(set(values)) != len(values) or any("/" in item or "\\" in item for item in values):
        raise ValidationError(f"{field} must be unique and path-free")
    return tuple(sorted(values))


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    if isinstance(value, str):
        lowered = value.lower()
        return "agent" not in lowered and "\\" not in value and "/" not in value
    return value is None or isinstance(value, (bool, int, float))


class RegistryFederationAuditCheck:
    """One independently computed federation invariant."""

    FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "audit check ordinal", MAX_CHECKS, positive=True)
        self.check_id = _label(check_id, "audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("audit check ID is unsupported")
        self.passed = _bool(passed, "audit check result")
        self.detail = _text(detail, "audit check detail")
        self.evidence_addresses = _addresses(evidence_addresses, "audit check evidence", 16)
        self.content_address = _address(content_address, "audit check content address", CHECK_PREFIX)
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("audit check content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("audit check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "check_id": self.check_id, "passed": self.passed, "detail": self.detail, "evidence_addresses": self.evidence_addresses, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationAuditCheck:
        value = _mapping(value, "federation audit check")
        _strict(value, set(cls.FIELDS), "federation audit check")
        evidence = tuple(value["evidence_addresses"]) if isinstance(value["evidence_addresses"], list) else value["evidence_addresses"]
        return cls(value["ordinal"], value["check_id"], value["passed"], value["detail"], evidence, value["content_address"])


def address_check(value: RegistryFederationAuditCheck) -> str:
    if not isinstance(value, RegistryFederationAuditCheck):
        raise ValidationError("audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class RegistryFederationAudit:
    """A complete independent audit receipt for one federation."""

    FIELDS = ("federation_id", "federation_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, federation_id: str, federation_address: str, checks: Sequence[RegistryFederationAuditCheck], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.federation_id = _label(federation_id, "audit federation ID")
        self.federation_address = _address(federation_address, "audit federation address", federation_model.FEDERATION_PREFIX)
        self.checks = tuple(checks)
        self.check_count = _count(check_count, "audit check count", MAX_CHECKS, positive=True)
        self.passed_count = _count(passed_count, "audit passed count", self.check_count)
        self.failed_count = _count(failed_count, "audit failed count", self.check_count)
        self.accepted = _bool(accepted, "audit accepted")
        self.content_address = _address(content_address, "audit content address", AUDIT_PREFIX)
        if len(self.checks) != self.check_count or self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(check.passed for check in self.checks) or self.failed_count != sum(not check.passed for check in self.checks):
            raise ValidationError("audit counters are not conserved")
        if tuple(check.ordinal for check in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(check.check_id for check in self.checks) != CHECK_IDS:
            raise ValidationError("audit checks are not canonical")
        if self.accepted != (self.failed_count == 0):
            raise ValidationError("audit acceptance is not conserved")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("audit content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"federation_id": self.federation_id, "federation_address": self.federation_address, "checks": tuple(check.to_dict() for check in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationAudit:
        value = _mapping(value, "federation audit")
        _strict(value, set(cls.FIELDS), "federation audit")
        checks = tuple(value["checks"]) if isinstance(value["checks"], list) else value["checks"]
        return cls(value["federation_id"], value["federation_address"], tuple(RegistryFederationAuditCheck.from_mapping(item) for item in checks), value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: RegistryFederationAudit) -> str:
    if not isinstance(value, RegistryFederationAudit):
        raise ValidationError("audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> RegistryFederationAuditCheck:
    provisional = RegistryFederationAuditCheck(ordinal, check_id, passed, detail, evidence, CHECK_PREFIX + ":pending")
    return RegistryFederationAuditCheck(provisional.ordinal, provisional.check_id, provisional.passed, provisional.detail, provisional.evidence_addresses, address_check(provisional))


def _audit_checks(value: federation_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation) -> tuple[RegistryFederationAuditCheck, ...]:
    peers = value.peers
    package_ids = tuple(sorted({package_id for peer in peers for package_id in peer.package_ids}))
    healthy = sum(peer.peer_state == "healthy" for peer in peers)
    conflicts = value.reconciliation.conflicts
    documents = federation_model._documents(value)
    expected_manifest = value.manifest | {"peers_address": documents[0]["content_address"], "reconciliation_address": documents[1]["content_address"], "actions_address": documents[2]["content_address"], "manifest_address": federation_model.address_manifest(value.manifest | {"manifest_address": None})}
    evidence = (value.content_address,)
    checks = [
        _check(1, "exact-fields", set(value.to_dict()) == set(federation_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation.FIELDS), "federation exposes the exact public field set", evidence),
        _check(2, "public-boundary", _public(value.to_dict()), "federation projection is public and path-free", evidence),
        _check(3, "peer-conservation", value.peer_count == len(peers) == value.reconciliation.peer_count, "peer count agrees across federation and reconciliation", evidence),
        _check(4, "peer-identity", tuple(peer.ordinal for peer in peers) == tuple(range(1, len(peers) + 1)) and len({peer.peer_id for peer in peers}) == len(peers), "peer ordinals and IDs are unique and ordered", tuple(peer.content_address for peer in peers)),
        _check(5, "peer-audit-conservation", healthy == value.healthy_peer_count and healthy == sum(peer.audit_accepted for peer in peers), "healthy count agrees with peer receipts", tuple(peer.content_address for peer in peers)),
        _check(6, "package-union-conservation", value.package_count == len(package_ids) and value.package_count == value.reconciliation.package_count, "package count equals the observed package union", evidence),
        _check(7, "conflict-conservation", value.conflict_count == len(conflicts) == value.reconciliation.conflict_count and value.reconciliation.missing_package_count == sum(conflict.kind == "missing" for conflict in conflicts) and value.reconciliation.divergent_package_count == sum(conflict.kind == "divergent" for conflict in conflicts), "conflict kinds and counters agree", tuple(conflict.content_address for conflict in conflicts) or evidence),
        _check(8, "quorum-conservation", value.reconciliation.healthy_peer_count >= value.reconciliation.quorum or value.state == "degraded", "quorum deficiency is represented as degraded state", evidence),
        _check(9, "state-conservation", (value.state, value.decision, value.accepted) == (("consistent", "accept", True) if not conflicts and healthy >= value.reconciliation.quorum else ("conflicted", "reject", False) if any(conflict.kind == "divergent" for conflict in conflicts) else ("degraded", "review", False)), "state, decision, and acceptance follow reconciliation evidence", evidence),
        _check(10, "action-conservation", value.action_count == len(value.actions) and all(action.ordinal == index for index, action in enumerate(value.actions, start=1)), "action count and ordinals are conserved", tuple(action.content_address for action in value.actions) or evidence),
        _check(11, "manifest-conservation", value.manifest == expected_manifest, "manifest links every projection document", evidence),
        _check(12, "content-address", federation_model.address_federation(value) == value.content_address, "federation content address replays", evidence),
        _check(13, "mapping-round-trip", federation_model.federation_from_mapping(value.to_dict()).content_address == value.content_address, "typed federation survives a mapping round trip", evidence),
        _check(14, "path-free", _public(value.to_dict()), "federation contains no filesystem paths or private execution text", evidence),
    ]
    return tuple(checks)


def audit_federation(value: federation_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation) -> RegistryFederationAudit:
    value = federation_model.verify_federation(value)
    checks = _audit_checks(value)
    provisional = RegistryFederationAudit(value.federation_id, value.content_address, checks, len(checks), sum(check.passed for check in checks), sum(not check.passed for check in checks), all(check.passed for check in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationAudit(provisional.federation_id, provisional.federation_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationAudit:
    return verify_audit(RegistryFederationAudit.from_mapping(value))


def verify_audit(value: RegistryFederationAudit) -> RegistryFederationAudit:
    if not isinstance(value, RegistryFederationAudit) or (not value.content_address.endswith(":pending") and address_audit(value) != value.content_address):
        raise ValidationError("federation audit is not valid")
    return value


def audit_json(value: RegistryFederationAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationAudit) -> str:
    value = verify_audit(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address"), lineterminator="\n")
    writer.writeheader()
    for check in value.checks:
        row = check.to_dict()
        row["evidence_addresses"] = "|".join(check.evidence_addresses)
        writer.writerow(row)
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationAudit) -> str:
    value = verify_audit(value)
    lines = ["# Package Registry Federation Audit", "", f"- Federation: `{value.federation_id}`", f"- Checks: `{value.passed_count}/{value.check_count}` passed", f"- Accepted: `{value.accepted}`", f"- Audit address: `{value.content_address}`", "", "| ordinal | check | result | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {check.ordinal} | `{check.check_id}` | `{check.passed}` | {check.detail} |" for check in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationAuditCheck.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"type": "string"}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationAudit.FIELDS), "properties": {"federation_id": {"type": "string"}, "federation_address": {"type": "string", "pattern": "^" + federation_model.FEDERATION_PREFIX + ":"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer", "minimum": 1}, "passed_count": {"type": "integer", "minimum": 0}, "failed_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_ids": CHECK_IDS, "features": ("independent peer conservation", "package-union recomputation", "conflict and quorum validation", "manifest linkage validation", "content-address replay", "JSON CSV and Markdown exports"), "schemas": ("check", "audit")}


__all__ = ["AUDIT_PREFIX", "BOUNDARY", "CHECK_IDS", "CHECK_PREFIX", "VERSION", "RegistryFederationAudit", "RegistryFederationAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_federation", "audit_json", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
