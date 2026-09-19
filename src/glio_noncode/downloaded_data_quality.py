"""Deterministic quality decisions over downloaded-data structural profiles.

This boundary turns a value-free profile into an explicit operational decision.
It does not interpret the source data or claim scientific validity.  Instead it
checks bounded, user-declared structural requirements: record coverage,
member and field presence, missingness, nullness, observed value types,
cardinality, and serialized value size.  Every check is replayable and keeps
the profile, policy, member, and field addresses that support the decision.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile as profile_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-quality-v1"
BOUNDARY = "public_downloaded_data_quality"
POLICY_PREFIX = "glio-noncode-download-quality-policy"
FINDING_PREFIX = "glio-noncode-download-quality-finding"
QUALITY_PREFIX = "glio-noncode-download-quality"
MAX_POLICY_ITEMS = 4_096
MAX_FINDINGS = profile_model.MAX_FIELDS * 10 + profile_model.MAX_MEMBERS * 3 + 32
MAX_RATIO_PPM = 1_000_000
MAX_DETAIL = 1_024
STATES = ("accepted", "review", "blocked")
SEVERITIES = ("review", "blocked")
SCOPES = ("summary", "member", "field")
RULE_IDS = (
    "record-count-min",
    "record-count-max",
    "required-member",
    "required-field",
    "member-record-min",
    "field-missing-ratio",
    "field-null-ratio",
    "field-value-type",
    "field-distinct-count",
    "field-value-size",
)

POLICY_FIELDS = (
    "policy_id",
    "version",
    "boundary",
    "min_records",
    "max_records",
    "required_members",
    "required_fields",
    "allowed_value_types",
    "max_missing_ratio_ppm",
    "max_null_ratio_ppm",
    "max_distinct_values",
    "max_value_size",
    "min_member_records",
    "failure_state",
    "content_address",
)
FINDING_FIELDS = (
    "ordinal",
    "rule_id",
    "scope",
    "member_name",
    "field_name",
    "severity",
    "passed",
    "measured",
    "limit",
    "detail",
    "evidence_addresses",
    "content_address",
)
QUALITY_FIELDS = (
    "result_id",
    "version",
    "boundary",
    "profile_address",
    "policy",
    "record_count",
    "member_count",
    "field_count",
    "check_count",
    "passed_count",
    "failed_count",
    "state",
    "accepted",
    "findings",
    "content_address",
)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if (
        not isinstance(value, str)
        or len(value) > maximum
        or (required and not value)
        or any(ord(char) < 32 and char not in "\n\t" for char in value)
    ):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, maximum: int = 256) -> str:
    value = _text(value, field, maximum)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 2048)
    if "/" in value or "\\" in value or '"' in value or ":" not in value:
        raise ValidationError(f"{field} must be a content address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > maximum:
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
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(
            str(key).casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child)
            for key, child in value.items()
        )
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


def _ratio(value: Any, field: str) -> int:
    return _count(value, field, MAX_RATIO_PPM)


def _names(value: Any, field: str, *, members: bool) -> tuple[str, ...]:
    items = _sequence(value, field, MAX_POLICY_ITEMS)
    normalized = tuple(
        ingestion_model._safe_member_name(item, field) if members else ingestion_model._key(item, field)
        for item in items
    )
    if len(set(normalized)) != len(normalized) or normalized != tuple(sorted(normalized)):
        raise ValidationError(f"{field} must be unique and sorted")
    return normalized


def _types(value: Any) -> tuple[str, ...]:
    items = tuple(_label(item, "allowed value type") for item in _sequence(value, "allowed value types", len(profile_model.VALUE_TYPES)))
    if len(set(items)) != len(items) or any(item not in profile_model.VALUE_TYPES for item in items):
        raise ValidationError("allowed value types contain an unsupported or duplicate value")
    order = {item: index for index, item in enumerate(profile_model.VALUE_TYPES)}
    if items != tuple(sorted(items, key=order.__getitem__)):
        raise ValidationError("allowed value types must use canonical type order")
    return items


def _replayed_or_pending(value: Any, field: str, prefix: str) -> str:
    if isinstance(value, str) and value.endswith(":pending"):
        return _text(value, field)
    return _address(value, field, prefix)


class DownloadedDataQualityPolicy:
    """Bounded structural acceptance policy for one or more profiles."""

    FIELDS = POLICY_FIELDS

    def __init__(
        self,
        policy_id: str,
        version: str,
        boundary: str,
        min_records: int,
        max_records: int,
        required_members: Sequence[str],
        required_fields: Sequence[str],
        allowed_value_types: Sequence[str],
        max_missing_ratio_ppm: int,
        max_null_ratio_ppm: int,
        max_distinct_values: int,
        max_value_size: int,
        min_member_records: int,
        failure_state: str,
        content_address: str,
    ) -> None:
        self.policy_id = _label(policy_id, "quality policy ID")
        self.version = _text(version, "quality policy version")
        self.boundary = _text(boundary, "quality policy boundary", 512)
        self.min_records = _count(min_records, "quality policy minimum records", profile_model.MAX_RECORDS)
        self.max_records = _count(max_records, "quality policy maximum records", profile_model.MAX_RECORDS)
        self.required_members = _names(required_members, "quality policy required members", members=True)
        self.required_fields = _names(required_fields, "quality policy required fields", members=False)
        self.allowed_value_types = _types(allowed_value_types)
        self.max_missing_ratio_ppm = _ratio(max_missing_ratio_ppm, "quality policy missing ratio")
        self.max_null_ratio_ppm = _ratio(max_null_ratio_ppm, "quality policy null ratio")
        self.max_distinct_values = _count(max_distinct_values, "quality policy distinct value limit", profile_model.MAX_DISTINCT_VALUES)
        self.max_value_size = _count(max_value_size, "quality policy value size limit", ingestion_model.MAX_RECORD_BYTES)
        self.min_member_records = _count(min_member_records, "quality policy minimum member records", profile_model.MAX_RECORDS)
        self.failure_state = _label(failure_state, "quality policy failure state")
        if self.failure_state not in SEVERITIES:
            raise ValidationError("quality policy failure state is unsupported")
        self.content_address = _replayed_or_pending(content_address, "quality policy address", POLICY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.min_records > self.max_records:
            raise ValidationError("quality policy record bounds are inverted")
        if self.required_members and len(self.required_members) > profile_model.MAX_MEMBERS:
            raise ValidationError("quality policy requires too many members")
        if self.required_fields and len(self.required_fields) > profile_model.MAX_FIELDS:
            raise ValidationError("quality policy requires too many fields")
        if not _public(self.to_dict()):
            raise ValidationError("quality policy crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_policy(self) != self.content_address:
            raise ValidationError("quality policy address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field not in {"required_members", "required_fields"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataQualityPolicy:
        value = _mapping(value, "downloaded data quality policy")
        _strict(value, set(cls.FIELDS), "downloaded data quality policy")
        return cls(*(value[field] for field in cls.FIELDS))


def address_policy(value: DownloadedDataQualityPolicy) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=POLICY_PREFIX)


def build_policy(
    *,
    policy_id: str = "glio-noncode-downloaded-data-quality-policy",
    min_records: int = 1,
    max_records: int = profile_model.MAX_RECORDS,
    required_members: Sequence[str] = (),
    required_fields: Sequence[str] = (),
    allowed_value_types: Sequence[str] = (),
    max_missing_ratio_ppm: int = MAX_RATIO_PPM,
    max_null_ratio_ppm: int = MAX_RATIO_PPM,
    max_distinct_values: int = profile_model.MAX_DISTINCT_VALUES,
    max_value_size: int = ingestion_model.MAX_RECORD_BYTES,
    min_member_records: int = 0,
    failure_state: str = "blocked",
) -> DownloadedDataQualityPolicy:
    member_values = _sequence(required_members, "quality policy required members", MAX_POLICY_ITEMS)
    field_values = _sequence(required_fields, "quality policy required fields", MAX_POLICY_ITEMS)
    type_values = _sequence(allowed_value_types, "quality policy allowed value types", len(profile_model.VALUE_TYPES))
    body = {
        "policy_id": policy_id,
        "version": VERSION,
        "boundary": BOUNDARY,
        "min_records": min_records,
        "max_records": max_records,
        "required_members": tuple(sorted(member_values, key=lambda item: item if isinstance(item, str) else "")),
        "required_fields": tuple(sorted(field_values, key=lambda item: item if isinstance(item, str) else "")),
        "allowed_value_types": tuple(sorted(type_values, key=lambda item: profile_model.VALUE_TYPES.index(item) if isinstance(item, str) and item in profile_model.VALUE_TYPES else len(profile_model.VALUE_TYPES))),
        "max_missing_ratio_ppm": max_missing_ratio_ppm,
        "max_null_ratio_ppm": max_null_ratio_ppm,
        "max_distinct_values": max_distinct_values,
        "max_value_size": max_value_size,
        "min_member_records": min_member_records,
        "failure_state": failure_state,
    }
    provisional = DownloadedDataQualityPolicy(**body, content_address=POLICY_PREFIX + ":pending")
    return DownloadedDataQualityPolicy(**body, content_address=address_policy(provisional))


class DownloadedDataQualityFinding:
    """One deterministic rule result with edge-level structural evidence."""

    FIELDS = FINDING_FIELDS

    def __init__(
        self,
        ordinal: int,
        rule_id: str,
        scope: str,
        member_name: str,
        field_name: str,
        severity: str,
        passed: bool,
        measured: int,
        limit: int,
        detail: str,
        evidence_addresses: Sequence[str],
        content_address: str,
    ) -> None:
        self.ordinal = _count(ordinal, "quality finding ordinal", MAX_FINDINGS, positive=True)
        self.rule_id = _label(rule_id, "quality finding rule")
        if self.rule_id not in RULE_IDS:
            raise ValidationError("quality finding rule is unsupported")
        self.scope = _label(scope, "quality finding scope")
        if self.scope not in SCOPES:
            raise ValidationError("quality finding scope is unsupported")
        self.member_name = ingestion_model._safe_member_name(member_name, "quality finding member") if member_name else ""
        self.field_name = ingestion_model._key(field_name, "quality finding field") if field_name else ""
        self.severity = _label(severity, "quality finding severity")
        if self.severity not in SEVERITIES:
            raise ValidationError("quality finding severity is unsupported")
        self.passed = _bool(passed, "quality finding result")
        self.measured = _count(measured, "quality finding measured value", profile_model.MAX_TOTAL_RECORDS)
        self.limit = _count(limit, "quality finding limit", max(profile_model.MAX_TOTAL_RECORDS, ingestion_model.MAX_RECORD_BYTES))
        self.detail = _text(detail, "quality finding detail", MAX_DETAIL)
        self.evidence_addresses = tuple(_address(item, "quality finding evidence address") for item in _sequence(evidence_addresses, "quality finding evidence", 4))
        if not self.evidence_addresses:
            raise ValidationError("quality finding requires evidence")
        self.content_address = _replayed_or_pending(content_address, "quality finding address", FINDING_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.scope == "summary" and (self.member_name or self.field_name):
            raise ValidationError("summary finding contains scoped names")
        if self.scope == "member" and not self.member_name:
            raise ValidationError("member finding is missing its member")
        if self.scope == "field" and not self.field_name:
            raise ValidationError("field finding is missing its field")
        if not _public(self.to_dict()):
            raise ValidationError("quality finding crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_finding(self) != self.content_address:
            raise ValidationError("quality finding address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataQualityFinding:
        value = _mapping(value, "downloaded data quality finding")
        _strict(value, set(cls.FIELDS), "downloaded data quality finding")
        return cls(*(value[field] for field in cls.FIELDS))


def address_finding(value: DownloadedDataQualityFinding) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=FINDING_PREFIX)


class DownloadedDataQuality:
    """Replayable quality decision for a structural profile."""

    FIELDS = QUALITY_FIELDS

    def __init__(
        self,
        result_id: str,
        version: str,
        boundary: str,
        profile_address: str,
        policy: DownloadedDataQualityPolicy | Mapping[str, Any],
        record_count: int,
        member_count: int,
        field_count: int,
        check_count: int,
        passed_count: int,
        failed_count: int,
        state: str,
        accepted: bool,
        findings: Sequence[DownloadedDataQualityFinding | Mapping[str, Any]],
        content_address: str,
    ) -> None:
        self.result_id = _label(result_id, "quality result ID")
        self.version = _text(version, "quality result version")
        self.boundary = _text(boundary, "quality result boundary", 512)
        self.profile_address = _address(profile_address, "quality profile address", profile_model.PROFILE_PREFIX)
        self.policy = policy if isinstance(policy, DownloadedDataQualityPolicy) else DownloadedDataQualityPolicy.from_mapping(policy)
        self.record_count = _count(record_count, "quality record count", profile_model.MAX_RECORDS)
        self.member_count = _count(member_count, "quality member count", profile_model.MAX_MEMBERS)
        self.field_count = _count(field_count, "quality field count", profile_model.MAX_FIELDS)
        self.check_count = _count(check_count, "quality check count", MAX_FINDINGS)
        self.passed_count = _count(passed_count, "quality passed count", MAX_FINDINGS)
        self.failed_count = _count(failed_count, "quality failed count", MAX_FINDINGS)
        self.state = _label(state, "quality state")
        if self.state not in STATES:
            raise ValidationError("quality state is unsupported")
        self.accepted = _bool(accepted, "quality acceptance")
        self.findings = tuple(item if isinstance(item, DownloadedDataQualityFinding) else DownloadedDataQualityFinding.from_mapping(item) for item in _sequence(findings, "quality findings", MAX_FINDINGS))
        self.content_address = _replayed_or_pending(content_address, "quality result address", QUALITY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.profile_address == self.policy.content_address:
            raise ValidationError("quality profile and policy addresses must be distinct")
        if self.check_count != len(self.findings) or self.passed_count != sum(item.passed for item in self.findings) or self.failed_count != self.check_count - self.passed_count:
            raise ValidationError("quality finding counts do not replay")
        if tuple(item.ordinal for item in self.findings) != tuple(range(1, self.check_count + 1)):
            raise ValidationError("quality finding ordinals are not canonical")
        expected_state = "accepted" if self.failed_count == 0 else self.policy.failure_state
        if self.state != expected_state or self.accepted != (self.state == "accepted"):
            raise ValidationError("quality decision does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("quality result crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_quality(self) != self.content_address:
            raise ValidationError("quality result address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "version": self.version,
            "boundary": self.boundary,
            "profile_address": self.profile_address,
            "policy": self.policy.to_dict(),
            "record_count": self.record_count,
            "member_count": self.member_count,
            "field_count": self.field_count,
            "check_count": self.check_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "state": self.state,
            "accepted": self.accepted,
            "findings": tuple(item.to_dict() for item in self.findings),
            "content_address": self.content_address,
        }

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field not in {"policy", "findings"}}

    def finding(self, ordinal: int) -> DownloadedDataQualityFinding:
        ordinal = _count(ordinal, "quality finding lookup", MAX_FINDINGS, positive=True)
        for item in self.findings:
            if item.ordinal == ordinal:
                return item
        raise ValidationError("quality finding was not found")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataQuality:
        value = _mapping(value, "downloaded data quality result")
        _strict(value, set(cls.FIELDS), "downloaded data quality result")
        return cls(*(value[field] for field in cls.FIELDS))


def address_quality(value: DownloadedDataQuality) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUALITY_PREFIX)


def _finding(
    ordinal: int,
    rule_id: str,
    scope: str,
    member_name: str,
    field_name: str,
    severity: str,
    passed: bool,
    measured: int,
    limit: int,
    detail: str,
    evidence: Sequence[str],
) -> DownloadedDataQualityFinding:
    body = {"ordinal": ordinal, "rule_id": rule_id, "scope": scope, "member_name": member_name, "field_name": field_name, "severity": severity, "passed": passed, "measured": measured, "limit": limit, "detail": detail, "evidence_addresses": tuple(evidence), "content_address": FINDING_PREFIX + ":pending"}
    provisional = DownloadedDataQualityFinding(**body)
    return DownloadedDataQualityFinding(**(body | {"content_address": address_finding(provisional)}))


def _ppm(numerator: int, denominator: int) -> int:
    if numerator <= 0 or denominator <= 0:
        return 0
    return (numerator * MAX_RATIO_PPM + denominator - 1) // denominator


def build_quality(
    profile: profile_model.DownloadedDataProfile,
    *,
    policy: DownloadedDataQualityPolicy | Mapping[str, Any] | None = None,
    result_id: str = "glio-noncode-downloaded-data-quality",
) -> DownloadedDataQuality:
    """Evaluate a structural profile against a declared quality policy."""

    if not isinstance(profile, profile_model.DownloadedDataProfile):
        raise ValidationError("quality evaluation requires a typed downloaded data profile")
    resolved_policy = policy if isinstance(policy, DownloadedDataQualityPolicy) else (build_policy() if policy is None else DownloadedDataQualityPolicy.from_mapping(policy))
    evidence = (profile.content_address,)
    findings: list[DownloadedDataQualityFinding] = []
    next_ordinal = 1

    def add(rule: str, scope: str, member: str, field: str, passed: bool, measured: int, limit: int, detail: str, extra: Sequence[str] = ()) -> None:
        nonlocal next_ordinal
        findings.append(_finding(next_ordinal, rule, scope, member, field, resolved_policy.failure_state, passed, measured, limit, detail, evidence + tuple(extra)))
        next_ordinal += 1

    add("record-count-min", "summary", "", "", profile.record_count >= resolved_policy.min_records, profile.record_count, resolved_policy.min_records, f"records={profile.record_count}; minimum={resolved_policy.min_records}")
    add("record-count-max", "summary", "", "", profile.record_count <= resolved_policy.max_records, profile.record_count, resolved_policy.max_records, f"records={profile.record_count}; maximum={resolved_policy.max_records}")

    members_by_name = {item.member_name: item for item in profile.members}
    fields_by_name = {item.field_name: item for item in profile.fields}
    for member_name in resolved_policy.required_members:
        member = members_by_name.get(member_name)
        add("required-member", "member", member_name, "", member is not None, 1 if member is not None else 0, 1, f"required member present={member is not None}", () if member is None else (member.content_address,))
    for field_name in resolved_policy.required_fields:
        field = fields_by_name.get(field_name)
        add("required-field", "field", "", field_name, field is not None, 1 if field is not None else 0, 1, f"required field present={field is not None}", () if field is None else (field.content_address,))

    for member in profile.members:
        add("member-record-min", "member", member.member_name, "", member.record_count >= resolved_policy.min_member_records, member.record_count, resolved_policy.min_member_records, f"member={member.member_name}; records={member.record_count}; minimum={resolved_policy.min_member_records}", (member.content_address,))
    for field in profile.fields:
        missing_ppm = _ppm(field.missing_count, profile.record_count)
        null_ppm = _ppm(field.null_count, field.observed_count)
        add("field-missing-ratio", "field", "", field.field_name, missing_ppm <= resolved_policy.max_missing_ratio_ppm, missing_ppm, resolved_policy.max_missing_ratio_ppm, f"field={field.field_name}; missing_ppm={missing_ppm}; maximum={resolved_policy.max_missing_ratio_ppm}", (field.content_address,))
        add("field-null-ratio", "field", "", field.field_name, null_ppm <= resolved_policy.max_null_ratio_ppm, null_ppm, resolved_policy.max_null_ratio_ppm, f"field={field.field_name}; null_ppm={null_ppm}; maximum={resolved_policy.max_null_ratio_ppm}", (field.content_address,))
        disallowed = sum(item.count for item in field.type_counts if item.value_type not in resolved_policy.allowed_value_types) if resolved_policy.allowed_value_types else 0
        add("field-value-type", "field", "", field.field_name, disallowed == 0, disallowed, 0, f"field={field.field_name}; disallowed_values={disallowed}", (field.content_address,)) if resolved_policy.allowed_value_types else None
        distinct_failed = field.distinct_truncated or field.distinct_value_count > resolved_policy.max_distinct_values
        add("field-distinct-count", "field", "", field.field_name, not distinct_failed, field.distinct_value_count, resolved_policy.max_distinct_values, f"field={field.field_name}; distinct={field.distinct_value_count}; truncated={field.distinct_truncated}; maximum={resolved_policy.max_distinct_values}", (field.content_address,))
        add("field-value-size", "field", "", field.field_name, field.max_value_size <= resolved_policy.max_value_size, field.max_value_size, resolved_policy.max_value_size, f"field={field.field_name}; maximum_value_bytes={field.max_value_size}; limit={resolved_policy.max_value_size}", (field.content_address,))

    if len(findings) > MAX_FINDINGS:
        raise ValidationError("quality policy generated too many findings")
    failed = sum(not item.passed for item in findings)
    body = {"result_id": result_id, "version": VERSION, "boundary": BOUNDARY, "profile_address": profile.content_address, "policy": resolved_policy, "record_count": profile.record_count, "member_count": profile.member_count, "field_count": profile.field_count, "check_count": len(findings), "passed_count": len(findings) - failed, "failed_count": failed, "state": "accepted" if not failed else resolved_policy.failure_state, "accepted": not failed, "findings": tuple(findings)}
    provisional = DownloadedDataQuality(**body, content_address=QUALITY_PREFIX + ":pending")
    return DownloadedDataQuality(**(body | {"content_address": address_quality(provisional)}))


def quality_from_mapping(value: Mapping[str, Any]) -> DownloadedDataQuality:
    return DownloadedDataQuality.from_mapping(value)


def policy_from_mapping(value: Mapping[str, Any]) -> DownloadedDataQualityPolicy:
    return DownloadedDataQualityPolicy.from_mapping(value)


def quality_json(value: DownloadedDataQuality) -> str:
    return canonical_json(DownloadedDataQuality.from_mapping(value.to_dict()).to_dict())


def policy_json(value: DownloadedDataQualityPolicy) -> str:
    return canonical_json(DownloadedDataQualityPolicy.from_mapping(value.to_dict()).to_dict())


def quality_csv(value: DownloadedDataQuality) -> str:
    value = DownloadedDataQuality.from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(FINDING_FIELDS)
    writer.writerows(tuple(item.to_dict()[field] if field != "evidence_addresses" else ";".join(item.evidence_addresses) for field in FINDING_FIELDS) for item in value.findings)
    return stream.getvalue()


def render_quality_markdown(value: DownloadedDataQuality) -> str:
    value = DownloadedDataQuality.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Quality", "", f"- Result: `{value.result_id}`", f"- Profile: `{value.profile_address}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- State: `{value.state}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| # | rule | scope | target | passed | measured | limit |", "| ---: | --- | --- | --- | --- | ---: | ---: |"]
    lines.extend(f"| {item.ordinal} | `{item.rule_id}` | `{item.scope}` | `{item.field_name or item.member_name or 'summary'}` | `{item.passed}` | {item.measured} | {item.limit} |" for item in value.findings)
    return "\n".join(lines) + "\n"


def policy_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality policy", "type": "object", "additionalProperties": False, "required": list(POLICY_FIELDS), "properties": {"policy_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "min_records": {"type": "integer", "minimum": 0}, "max_records": {"type": "integer", "minimum": 0}, "required_members": {"type": "array", "items": {"type": "string"}}, "required_fields": {"type": "array", "items": {"type": "string"}}, "allowed_value_types": {"type": "array", "items": {"enum": list(profile_model.VALUE_TYPES)}}, "max_missing_ratio_ppm": {"type": "integer", "minimum": 0, "maximum": MAX_RATIO_PPM}, "max_null_ratio_ppm": {"type": "integer", "minimum": 0, "maximum": MAX_RATIO_PPM}, "max_distinct_values": {"type": "integer", "minimum": 0, "maximum": profile_model.MAX_DISTINCT_VALUES}, "max_value_size": {"type": "integer", "minimum": 0}, "min_member_records": {"type": "integer", "minimum": 0}, "failure_state": {"enum": list(SEVERITIES)}, "content_address": {"type": "string"}}}


def finding_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality finding", "type": "object", "additionalProperties": False, "required": list(FINDING_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "rule_id": {"enum": list(RULE_IDS)}, "scope": {"enum": list(SCOPES)}, "member_name": {"type": "string"}, "field_name": {"type": "string"}, "severity": {"enum": list(SEVERITIES)}, "passed": {"type": "boolean"}, "measured": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 0}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def quality_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality result", "type": "object", "additionalProperties": False, "required": list(QUALITY_FIELDS), "properties": {"result_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "profile_address": {"type": "string"}, "policy": policy_schema(), "record_count": {"type": "integer", "minimum": 0}, "member_count": {"type": "integer", "minimum": 0}, "field_count": {"type": "integer", "minimum": 0}, "check_count": {"type": "integer", "minimum": 0}, "passed_count": {"type": "integer", "minimum": 0}, "failed_count": {"type": "integer", "minimum": 0}, "state": {"enum": list(STATES)}, "accepted": {"type": "boolean"}, "findings": {"type": "array", "items": finding_schema()}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "states": STATES, "rule_ids": RULE_IDS, "operations": ("build_policy", "policy_from_mapping", "build_quality", "quality_from_mapping", "quality_json", "quality_csv", "render_quality_markdown"), "limits": {"max_findings": MAX_FINDINGS, "max_ratio_ppm": MAX_RATIO_PPM}}


__all__ = ["BOUNDARY", "FINDING_FIELDS", "MAX_FINDINGS", "MAX_RATIO_PPM", "POLICY_FIELDS", "QUALITY_FIELDS", "RULE_IDS", "STATES", "DownloadedDataQuality", "DownloadedDataQualityFinding", "DownloadedDataQualityPolicy", "address_finding", "address_policy", "address_quality", "build_policy", "build_quality", "capabilities", "finding_schema", "policy_from_mapping", "policy_json", "policy_schema", "quality_csv", "quality_from_mapping", "quality_json", "quality_schema", "render_quality_markdown"]
