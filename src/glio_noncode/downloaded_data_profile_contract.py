"""Derive a value-free data dictionary and schema-drift contract.

The profile boundary describes what was observed.  This boundary turns those
observations into an explicit structural contract: required and optional
fields, member coverage, dominant value types, mixed-type drift, and stable
empty/sparse/uniform/mixed/complete states.  It never copies source values.
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

VERSION = "downloaded-data-profile-contract-v1"
BOUNDARY = "public_downloaded_data_profile_contract"
CONTRACT_PREFIX = "glio-noncode-download-profile-contract"
FIELD_PREFIX = CONTRACT_PREFIX + "-field"
MEMBER_PREFIX = CONTRACT_PREFIX + "-member"
TYPE_PREFIX = CONTRACT_PREFIX + "-type"
STATES = ("empty", "sparse", "uniform", "mixed", "complete")
TYPE_FIELDS = ("value_type", "observed_count", "field_count", "member_count", "content_address")
FIELD_FIELDS = (
    "field_name",
    "observed_count",
    "missing_count",
    "member_count",
    "type_counts",
    "dominant_value_type",
    "type_consistent",
    "required",
    "state",
    "member_addresses",
    "content_address",
)
MEMBER_FIELDS = (
    "member_name",
    "member_address",
    "member_ordinal",
    "data_kind",
    "record_count",
    "field_count",
    "required_field_count",
    "optional_field_count",
    "mixed_type_field_count",
    "field_names",
    "required_field_names",
    "optional_field_names",
    "mixed_type_field_names",
    "content_address",
)
CONTRACT_FIELDS = (
    "profile_address",
    "version",
    "boundary",
    "record_count",
    "member_count",
    "field_count",
    "required_field_count",
    "optional_field_count",
    "sparse_field_count",
    "mixed_type_field_count",
    "types",
    "members",
    "fields",
    "content_address",
)
MAX_TYPE_ROWS = len(profile_model.VALUE_TYPES)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 256)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _key(value: Any, field: str) -> str:
    value = _text(value, field, ingestion_model.MAX_IDENTIFIER)
    if not value or value.strip() != value or any(ord(char) < 32 for char in value) or any(char in "\r\n\t" for char in value):
        raise ValidationError(f"{field} must be a public field name")
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
        return all(str(key).casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


def _state(observed_count: int, missing_count: int, type_counts: Sequence[profile_model.DownloadedDataTypeCount]) -> str:
    nonzero = tuple(item for item in type_counts if item.count)
    if not observed_count:
        return "empty"
    if len(nonzero) > 1:
        return "mixed"
    if missing_count:
        return "sparse"
    if nonzero:
        return "complete"
    return "uniform"


def _dominant(type_counts: Sequence[profile_model.DownloadedDataTypeCount]) -> str:
    nonzero = tuple(item for item in type_counts if item.count)
    if not nonzero:
        return ""
    return max(nonzero, key=lambda item: (item.count, -profile_model.VALUE_TYPES.index(item.value_type))).value_type


class DownloadedDataContractType:
    """Aggregate observation counts for one value type across fields."""

    FIELDS = TYPE_FIELDS

    def __init__(self, value_type: str, observed_count: int, field_count: int, member_count: int, content_address: str) -> None:
        self.value_type = _label(value_type, "contract type")
        if self.value_type not in profile_model.VALUE_TYPES:
            raise ValidationError("contract type is unsupported")
        self.observed_count = _count(observed_count, "contract type observed count", profile_model.MAX_TOTAL_RECORDS * MAX_TYPE_ROWS)
        self.field_count = _count(field_count, "contract type field count", profile_model.MAX_FIELDS)
        self.member_count = _count(member_count, "contract type member count", profile_model.MAX_MEMBERS)
        self.content_address = _address(content_address, "contract type address", TYPE_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "contract type address")
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("contract type crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_type(self) != self.content_address:
            raise ValidationError("contract type address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataContractType:
        value = _mapping(value, "contract type")
        _strict(value, set(cls.FIELDS), "contract type")
        return cls(*(value[field] for field in cls.FIELDS))


def address_type(value: DownloadedDataContractType) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=TYPE_PREFIX)


class DownloadedDataContractField:
    """Value-free inferred contract for one public field name."""

    FIELDS = FIELD_FIELDS

    def __init__(self, field_name: str, observed_count: int, missing_count: int, member_count: int, type_counts: Sequence[profile_model.DownloadedDataTypeCount | Mapping[str, Any]], dominant_value_type: str, type_consistent: bool, required: bool, state: str, member_addresses: Sequence[str], content_address: str) -> None:
        self.field_name = _key(field_name, "contract field name")
        self.observed_count = _count(observed_count, "contract field observed count", profile_model.MAX_TOTAL_RECORDS)
        self.missing_count = _count(missing_count, "contract field missing count", profile_model.MAX_TOTAL_RECORDS)
        self.member_count = _count(member_count, "contract field member count", profile_model.MAX_MEMBERS)
        self.type_counts = tuple(item if isinstance(item, profile_model.DownloadedDataTypeCount) else profile_model.DownloadedDataTypeCount.from_mapping(item) for item in _sequence(type_counts, "contract field type counts", MAX_TYPE_ROWS))
        self.dominant_value_type = _label(dominant_value_type, "contract field dominant type",) if dominant_value_type else ""
        if self.dominant_value_type and self.dominant_value_type not in profile_model.VALUE_TYPES:
            raise ValidationError("contract field dominant type is unsupported")
        self.type_consistent = _bool(type_consistent, "contract field type consistency")
        self.required = _bool(required, "contract field required state")
        self.state = _label(state, "contract field state")
        if self.state not in STATES:
            raise ValidationError("contract field state is unsupported")
        self.member_addresses = tuple(_address(item, "contract field member address") for item in _sequence(member_addresses, "contract field member addresses", profile_model.MAX_MEMBERS))
        self.content_address = _address(content_address, "contract field address", FIELD_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "contract field address")
        self._validate()

    def _validate(self) -> None:
        if tuple(item.value_type for item in self.type_counts) != profile_model.VALUE_TYPES or sum(item.count for item in self.type_counts) != self.observed_count:
            raise ValidationError("contract field type counts do not conserve observations")
        if self.missing_count + self.observed_count > profile_model.MAX_TOTAL_RECORDS or self.member_count != len(self.member_addresses) or len(set(self.member_addresses)) != len(self.member_addresses) or tuple(sorted(self.member_addresses)) != self.member_addresses:
            raise ValidationError("contract field coverage does not replay")
        expected_state = _state(self.observed_count, self.missing_count, self.type_counts)
        if self.state != expected_state or self.type_consistent != (sum(item.count > 0 for item in self.type_counts) <= 1) or self.required != (self.missing_count == 0):
            raise ValidationError("contract field state does not replay")
        if self.dominant_value_type != _dominant(self.type_counts):
            raise ValidationError("contract field dominant type does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("contract field crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_field(self) != self.content_address:
            raise ValidationError("contract field address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"field_name": self.field_name, "observed_count": self.observed_count, "missing_count": self.missing_count, "member_count": self.member_count, "type_counts": tuple(item.to_dict() for item in self.type_counts), "dominant_value_type": self.dominant_value_type, "type_consistent": self.type_consistent, "required": self.required, "state": self.state, "member_addresses": self.member_addresses, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataContractField:
        value = _mapping(value, "contract field")
        _strict(value, set(cls.FIELDS), "contract field")
        return cls(*(value[field] for field in cls.FIELDS))


def address_field(value: DownloadedDataContractField) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=FIELD_PREFIX)


class DownloadedDataContractMember:
    """Value-free inferred contract for one selected member."""

    FIELDS = MEMBER_FIELDS

    def __init__(self, member_name: str, member_address: str, member_ordinal: int, data_kind: str, record_count: int, field_count: int, required_field_count: int, optional_field_count: int, mixed_type_field_count: int, field_names: Sequence[str], required_field_names: Sequence[str], optional_field_names: Sequence[str], mixed_type_field_names: Sequence[str], content_address: str) -> None:
        self.member_name = ingestion_model._safe_member_name(member_name, "contract member name")
        self.member_address = _address(member_address, "contract member address")
        self.member_ordinal = _count(member_ordinal, "contract member ordinal", profile_model.MAX_MEMBERS, positive=True)
        self.data_kind = _label(data_kind, "contract member data kind")
        if self.data_kind not in ingestion_model.DATA_KINDS:
            raise ValidationError("contract member data kind is unsupported")
        self.record_count = _count(record_count, "contract member record count", profile_model.MAX_RECORDS)
        self.field_count = _count(field_count, "contract member field count", profile_model.MAX_FIELDS)
        self.required_field_count = _count(required_field_count, "contract member required field count", profile_model.MAX_FIELDS)
        self.optional_field_count = _count(optional_field_count, "contract member optional field count", profile_model.MAX_FIELDS)
        self.mixed_type_field_count = _count(mixed_type_field_count, "contract member mixed field count", profile_model.MAX_FIELDS)
        self.field_names = tuple(_key(item, "contract member field name") for item in _sequence(field_names, "contract member field names", profile_model.MAX_FIELDS))
        self.required_field_names = tuple(_key(item, "contract member required field name") for item in _sequence(required_field_names, "contract member required field names", profile_model.MAX_FIELDS))
        self.optional_field_names = tuple(_key(item, "contract member optional field name") for item in _sequence(optional_field_names, "contract member optional field names", profile_model.MAX_FIELDS))
        self.mixed_type_field_names = tuple(_key(item, "contract member mixed field name") for item in _sequence(mixed_type_field_names, "contract member mixed field names", profile_model.MAX_FIELDS))
        self.content_address = _address(content_address, "contract member address", MEMBER_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "contract member address")
        self._validate()

    def _validate(self) -> None:
        if self.field_count != len(self.field_names) or len(set(self.field_names)) != len(self.field_names) or tuple(sorted(self.field_names)) != self.field_names or self.required_field_count != len(self.required_field_names) or self.optional_field_count != len(self.optional_field_names) or self.mixed_type_field_count != len(self.mixed_type_field_names) or self.required_field_count + self.optional_field_count != self.field_count or set(self.required_field_names).intersection(self.optional_field_names) or set(self.required_field_names).union(self.optional_field_names) != set(self.field_names) or not set(self.mixed_type_field_names).issubset(self.field_names):
            raise ValidationError("contract member field aggregates do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("contract member crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_member(self) != self.content_address:
            raise ValidationError("contract member address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataContractMember:
        value = _mapping(value, "contract member")
        _strict(value, set(cls.FIELDS), "contract member")
        return cls(*(value[field] for field in cls.FIELDS))


def address_member(value: DownloadedDataContractMember) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MEMBER_PREFIX)


class DownloadedDataProfileContract:
    """Addressed value-free data dictionary and schema-drift contract."""

    FIELDS = CONTRACT_FIELDS

    def __init__(self, profile_address: str, version: str, boundary: str, record_count: int, member_count: int, field_count: int, required_field_count: int, optional_field_count: int, sparse_field_count: int, mixed_type_field_count: int, types: Sequence[DownloadedDataContractType | Mapping[str, Any]], members: Sequence[DownloadedDataContractMember | Mapping[str, Any]], fields: Sequence[DownloadedDataContractField | Mapping[str, Any]], content_address: str) -> None:
        self.profile_address = _address(profile_address, "contract profile address", profile_model.PROFILE_PREFIX)
        self.version = _text(version, "contract version")
        self.boundary = _text(boundary, "contract boundary", 512)
        self.record_count = _count(record_count, "contract record count", profile_model.MAX_RECORDS)
        self.member_count = _count(member_count, "contract member count", profile_model.MAX_MEMBERS)
        self.field_count = _count(field_count, "contract field count", profile_model.MAX_FIELDS)
        self.required_field_count = _count(required_field_count, "contract required field count", profile_model.MAX_FIELDS)
        self.optional_field_count = _count(optional_field_count, "contract optional field count", profile_model.MAX_FIELDS)
        self.sparse_field_count = _count(sparse_field_count, "contract sparse field count", profile_model.MAX_FIELDS)
        self.mixed_type_field_count = _count(mixed_type_field_count, "contract mixed field count", profile_model.MAX_FIELDS)
        self.types = tuple(item if isinstance(item, DownloadedDataContractType) else DownloadedDataContractType.from_mapping(item) for item in _sequence(types, "contract type rows", MAX_TYPE_ROWS))
        self.members = tuple(item if isinstance(item, DownloadedDataContractMember) else DownloadedDataContractMember.from_mapping(item) for item in _sequence(members, "contract members", profile_model.MAX_MEMBERS))
        self.fields = tuple(item if isinstance(item, DownloadedDataContractField) else DownloadedDataContractField.from_mapping(item) for item in _sequence(fields, "contract fields", profile_model.MAX_FIELDS))
        self.content_address = _address(content_address, "contract address", CONTRACT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "contract address")
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("contract version or boundary is not current")
        if len(self.types) != MAX_TYPE_ROWS or tuple(item.value_type for item in self.types) != profile_model.VALUE_TYPES:
            raise ValidationError("contract type rows are not canonical")
        if len(self.members) != self.member_count or len({item.member_address for item in self.members}) != self.member_count or tuple(item.member_ordinal for item in self.members) != tuple(sorted(item.member_ordinal for item in self.members)):
            raise ValidationError("contract members are not canonical")
        if len(self.fields) != self.field_count or len({item.field_name for item in self.fields}) != self.field_count or tuple(item.field_name for item in self.fields) != tuple(sorted(item.field_name for item in self.fields)):
            raise ValidationError("contract fields are not canonical")
        if self.required_field_count + self.optional_field_count != self.field_count or self.sparse_field_count != sum(item.state == "sparse" for item in self.fields) or self.mixed_type_field_count != sum(item.state == "mixed" for item in self.fields):
            raise ValidationError("contract field-state aggregates do not replay")
        if self.record_count != sum(item.record_count for item in self.members) or self.field_count != len(self.fields) or not _public(self.to_dict()):
            raise ValidationError("contract aggregates or public boundary failed")
        if not self.content_address.endswith(":pending") and address_contract(self) != self.content_address:
            raise ValidationError("contract address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"profile_address": self.profile_address, "version": self.version, "boundary": self.boundary, "record_count": self.record_count, "member_count": self.member_count, "field_count": self.field_count, "required_field_count": self.required_field_count, "optional_field_count": self.optional_field_count, "sparse_field_count": self.sparse_field_count, "mixed_type_field_count": self.mixed_type_field_count, "types": tuple(item.to_dict() for item in self.types), "members": tuple(item.to_dict() for item in self.members), "fields": tuple(item.to_dict() for item in self.fields), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field not in {"types", "members", "fields"}}

    def field(self, field_name: str) -> DownloadedDataContractField:
        field_name = _key(field_name, "contract field lookup")
        for item in self.fields:
            if item.field_name == field_name:
                return item
        raise ValidationError("contract field was not found")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContract:
        value = _mapping(value, "downloaded data profile contract")
        _strict(value, set(cls.FIELDS), "downloaded data profile contract")
        return cls(*(value[field] for field in cls.FIELDS))


def address_contract(value: DownloadedDataProfileContract) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CONTRACT_PREFIX)


def _contract_field(field: profile_model.DownloadedDataFieldProfile, member_addresses: Sequence[str]) -> DownloadedDataContractField:
    type_counts = tuple(field.type_counts)
    body = {"field_name": field.field_name, "observed_count": field.observed_count, "missing_count": field.missing_count, "member_count": len(member_addresses), "type_counts": type_counts, "dominant_value_type": _dominant(type_counts), "type_consistent": sum(item.count > 0 for item in type_counts) <= 1, "required": field.missing_count == 0, "state": _state(field.observed_count, field.missing_count, type_counts), "member_addresses": tuple(sorted(member_addresses)), "content_address": FIELD_PREFIX + ":pending"}
    provisional = DownloadedDataContractField(**body)
    return DownloadedDataContractField(**(body | {"content_address": address_field(provisional)}))


def _contract_member(member: profile_model.DownloadedDataMemberProfile) -> DownloadedDataContractMember:
    field_names = tuple(sorted(item.field_name for item in member.fields))
    local_profiles = {item.field_name: item for item in member.fields}
    required_names = tuple(name for name in field_names if local_profiles[name].missing_count == 0)
    optional_names = tuple(name for name in field_names if local_profiles[name].missing_count != 0)
    mixed_names = tuple(name for name in field_names if sum(type_count.count > 0 for type_count in local_profiles[name].type_counts) > 1)
    body = {"member_name": member.member_name, "member_address": member.member_address, "member_ordinal": member.member_ordinal, "data_kind": member.data_kind, "record_count": member.record_count, "field_count": len(field_names), "required_field_count": len(required_names), "optional_field_count": len(optional_names), "mixed_type_field_count": len(mixed_names), "field_names": field_names, "required_field_names": required_names, "optional_field_names": optional_names, "mixed_type_field_names": mixed_names, "content_address": MEMBER_PREFIX + ":pending"}
    provisional = DownloadedDataContractMember(**body)
    return DownloadedDataContractMember(**(body | {"content_address": address_member(provisional)}))


def build_contract(profile: profile_model.DownloadedDataProfile) -> DownloadedDataProfileContract:
    """Infer a bounded contract from a typed structural profile."""

    if not isinstance(profile, profile_model.DownloadedDataProfile):
        raise ValidationError("contract requires a typed downloaded data profile")
    member_addresses: dict[str, list[str]] = {}
    for member in profile.members:
        for field in member.fields:
            member_addresses.setdefault(field.field_name, []).append(member.member_address)
    fields = tuple(_contract_field(field, member_addresses.get(field.field_name, ())) for field in profile.fields)
    members = tuple(_contract_member(member) for member in profile.members)
    types = []
    for value_type in profile_model.VALUE_TYPES:
        field_rows = tuple(field for field in fields if any(item.value_type == value_type and item.count for item in field.type_counts))
        member_rows = {address for field in field_rows for address in field.member_addresses}
        observed = sum(next(item.count for item in field.type_counts if item.value_type == value_type) for field in fields)
        body = {"value_type": value_type, "observed_count": observed, "field_count": len(field_rows), "member_count": len(member_rows), "content_address": TYPE_PREFIX + ":pending"}
        provisional = DownloadedDataContractType(**body)
        types.append(DownloadedDataContractType(**(body | {"content_address": address_type(provisional)})))
    body = {"profile_address": profile.content_address, "version": VERSION, "boundary": BOUNDARY, "record_count": profile.record_count, "member_count": len(members), "field_count": len(fields), "required_field_count": sum(item.required for item in fields), "optional_field_count": sum(not item.required for item in fields), "sparse_field_count": sum(item.state == "sparse" for item in fields), "mixed_type_field_count": sum(item.state == "mixed" for item in fields), "types": tuple(types), "members": members, "fields": fields, "content_address": CONTRACT_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContract(**body)
    return DownloadedDataProfileContract(**(body | {"content_address": address_contract(provisional)}))


def contract_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContract:
    return DownloadedDataProfileContract.from_mapping(value)


def contract_json(value: DownloadedDataProfileContract) -> str:
    return canonical_json(DownloadedDataProfileContract.from_mapping(value.to_dict()).to_dict())


def contract_csv(value: DownloadedDataProfileContract) -> str:
    value = DownloadedDataProfileContract.from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(FIELD_FIELDS)
    for field in value.fields:
        writer.writerow(tuple(canonical_json(field.to_dict()[name]) if name in {"type_counts", "member_addresses"} else field.to_dict()[name] for name in FIELD_FIELDS))
    return stream.getvalue()


def render_contract_markdown(value: DownloadedDataProfileContract) -> str:
    value = DownloadedDataProfileContract.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Contract", "", f"- Profile: `{value.profile_address}`", f"- Records: `{value.record_count}`", f"- Members: `{value.member_count}`", f"- Fields: `{value.field_count}`", f"- Required fields: `{value.required_field_count}`", f"- Optional fields: `{value.optional_field_count}`", f"- Sparse fields: `{value.sparse_field_count}`", f"- Mixed-type fields: `{value.mixed_type_field_count}`", f"- Address: `{value.content_address}`", "", "| field | observed | missing | members | dominant type | state |", "| --- | ---: | ---: | ---: | --- | --- |"]
    lines.extend(f"| `{item.field_name}` | {item.observed_count} | {item.missing_count} | {item.member_count} | `{item.dominant_value_type}` | `{item.state}` |" for item in value.fields)
    return "\n".join(lines) + "\n"


def type_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract type", "type": "object", "additionalProperties": False, "required": list(TYPE_FIELDS), "properties": {"value_type": {"enum": list(profile_model.VALUE_TYPES)}, "observed_count": {"type": "integer", "minimum": 0}, "field_count": {"type": "integer", "minimum": 0}, "member_count": {"type": "integer", "minimum": 0}, "content_address": {"type": "string"}}}


def field_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract field", "type": "object", "additionalProperties": False, "required": list(FIELD_FIELDS), "properties": {"field_name": {"type": "string"}, "observed_count": {"type": "integer", "minimum": 0}, "missing_count": {"type": "integer", "minimum": 0}, "member_count": {"type": "integer", "minimum": 0}, "type_counts": {"type": "array", "items": profile_model.type_count_schema()}, "dominant_value_type": {"enum": list(profile_model.VALUE_TYPES) + [""]}, "type_consistent": {"type": "boolean"}, "required": {"type": "boolean"}, "state": {"enum": list(STATES)}, "member_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def member_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract member", "type": "object", "additionalProperties": False, "required": list(MEMBER_FIELDS), "properties": {"member_name": {"type": "string"}, "member_address": {"type": "string"}, "member_ordinal": {"type": "integer", "minimum": 1}, "data_kind": {"type": "string"}, "record_count": {"type": "integer", "minimum": 0}, "field_count": {"type": "integer", "minimum": 0}, "required_field_count": {"type": "integer", "minimum": 0}, "optional_field_count": {"type": "integer", "minimum": 0}, "mixed_type_field_count": {"type": "integer", "minimum": 0}, "field_names": {"type": "array", "items": {"type": "string"}}, "required_field_names": {"type": "array", "items": {"type": "string"}}, "optional_field_names": {"type": "array", "items": {"type": "string"}}, "mixed_type_field_names": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def contract_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract", "type": "object", "additionalProperties": False, "required": list(CONTRACT_FIELDS), "properties": {"profile_address": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "record_count": {"type": "integer", "minimum": 0}, "member_count": {"type": "integer", "minimum": 0}, "field_count": {"type": "integer", "minimum": 0}, "required_field_count": {"type": "integer", "minimum": 0}, "optional_field_count": {"type": "integer", "minimum": 0}, "sparse_field_count": {"type": "integer", "minimum": 0}, "mixed_type_field_count": {"type": "integer", "minimum": 0}, "types": {"type": "array", "items": type_schema()}, "members": {"type": "array", "items": member_schema()}, "fields": {"type": "array", "items": field_schema()}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "states": STATES, "value_types": profile_model.VALUE_TYPES, "operations": ("build_contract", "contract_from_mapping", "contract_json", "contract_csv", "render_contract_markdown"), "limits": {"max_members": profile_model.MAX_MEMBERS, "max_fields": profile_model.MAX_FIELDS}}


__all__ = ["BOUNDARY", "CONTRACT_FIELDS", "CONTRACT_PREFIX", "DownloadedDataContractField", "DownloadedDataContractMember", "DownloadedDataContractType", "DownloadedDataProfileContract", "FIELD_FIELDS", "FIELD_PREFIX", "MAX_TYPE_ROWS", "MEMBER_FIELDS", "MEMBER_PREFIX", "STATES", "TYPE_FIELDS", "TYPE_PREFIX", "VERSION", "address_contract", "address_field", "address_member", "address_type", "build_contract", "capabilities", "contract_csv", "contract_from_mapping", "contract_json", "contract_schema", "field_schema", "member_schema", "render_contract_markdown", "type_schema"]
