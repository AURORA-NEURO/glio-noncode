"""Build, verify, query, and persist module630 policy-decision transports."""
# ruff: noqa: E501

from __future__ import annotations

import csv
import io
import zipfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_629 as diff_model
from . import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_630 as policy_model
from . import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_630_aud as policy_audit_model
from . import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_631_ct as contract_model
from ._safe_persistence import _validate_parent, atomic_write_bytes, read_bytes
from .errors import ValidationError
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, hash_bytes

VERSION = contract_model.VERSION
BOUNDARY = contract_model.BOUNDARY
PACKAGE_PREFIX = contract_model.PACKAGE_PREFIX
MANIFEST_PREFIX = contract_model.MANIFEST_PREFIX
MEMBER_PREFIX = contract_model.MEMBER_PREFIX
FILE_NAMES = contract_model.FILE_NAMES
PAYLOAD_NAMES = contract_model.PAYLOAD_NAMES
MEDIA_TYPES = contract_model.MEDIA_TYPES
PACKAGE_FORMAT = contract_model.PACKAGE_FORMAT
MAX_PACKAGE_BYTES = contract_model.MAX_PACKAGE_BYTES
MAX_MEMBER_BYTES = contract_model.MAX_MEMBER_BYTES
MAX_LIMIT = 256
DEFAULT_PACKAGE_ID = "module631-transport"
_FIXED_ATTRIBUTES = 0o100644 << 16


def _review(diff: Any, policy: Any, audit: Any) -> str:
    failed = tuple(item.check_id for item in policy.checks if not item.passed)
    lines = ["# Module631 Policy Decision Transport", "", f"- Policy state: **{policy.state}**", f"- Policy accepted: **{str(policy.accepted).lower()}**", f"- Policy checks: **{policy.passed_count}/{policy.check_count}**", f"- Audit accepted: **{str(audit.accepted).lower()}**", f"- Audit checks: **{audit.passed_count}/{audit.check_count}**", f"- Diff: `{diff.content_address}`", f"- Policy: `{policy.content_address}`", f"- Audit: `{audit.content_address}`", ""]
    if failed:
        lines.extend(["## Retained failed controls", "", *[f"- `{check_id}`" for check_id in failed], ""])
    lines.extend(["## Evidence", "", policy_model.render_policy_markdown(policy), policy_audit_model.render_audit_markdown(audit)])
    return "\n".join(lines).replace("\n\n\n\n", "\n\n\n")


def _payloads(diff: Any, policy: Any, audit: Any) -> dict[str, bytes]:
    return {"catalog-diff.json": diff_model.diff_json(diff).encode("utf-8"), "policy.json": policy_model.policy_json(policy).encode("utf-8"), "policy-audit.json": policy_audit_model.audit_json(audit).encode("utf-8"), "review.md": _review(diff, policy, audit).encode("utf-8")}


def _member(path: str, payload: bytes) -> contract_model.Member:
    provisional = contract_model.Member(path, MEDIA_TYPES[path], len(payload), contract_model.address_member_bytes(payload), MEMBER_PREFIX + ":pending")
    return contract_model.Member(path, MEDIA_TYPES[path], len(payload), provisional.byte_address, contract_model.address_member(provisional))


def _zip_info(path: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(path, date_time=contract_model.FIXED_ZIP_DATE)
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 0
    info.create_version = 20
    info.extract_version = 20
    info.flag_bits = 0
    info.internal_attr = 0
    info.external_attr = _FIXED_ATTRIBUTES
    info.extra = b""
    info.comment = b""
    return info


def _zip_bytes(manifest: contract_model.Manifest, payloads: Mapping[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED, allowZip64=False) as archive:
        archive.writestr(_zip_info("manifest.json"), (canonical_json(manifest.to_dict()) + "\n").encode("utf-8"))
        for path in PAYLOAD_NAMES:
            archive.writestr(_zip_info(path), payloads[path])
    value = stream.getvalue()
    if len(value) > MAX_PACKAGE_BYTES:
        raise ValidationError("module631 package exceeds its byte ceiling")
    return value


def build_package(diff: Any, policy: Any, audit: Any = None, *, package_id: str = DEFAULT_PACKAGE_ID) -> contract_model.Transport:
    diff_value = diff_model.verify_diff(diff)
    policy_value = policy_model.verify_policy(policy)
    if policy_value.diff_address != diff_value.content_address:
        raise ValidationError("module631 policy does not point to the supplied diff")
    audit_value = policy_audit_model.audit_policy(policy_value, diff=diff_value) if audit is None else policy_audit_model.verify_audit(audit)
    if audit_value.diff_address != diff_value.content_address or audit_value.policy_address != policy_value.content_address or not audit_value.accepted:
        raise ValidationError("module631 audit lineage or acceptance is invalid")
    payloads = _payloads(diff_value, policy_value, audit_value)
    members = tuple(_member(path, payloads[path]) for path in PAYLOAD_NAMES)
    provisional = contract_model.Manifest(package_id, VERSION, BOUNDARY, diff_value.content_address, policy_value.content_address, audit_value.content_address, policy_value.state, policy_value.accepted, audit_value.accepted, members, PACKAGE_FORMAT, MANIFEST_PREFIX + ":pending")
    manifest = contract_model.Manifest(package_id, VERSION, BOUNDARY, diff_value.content_address, policy_value.content_address, audit_value.content_address, policy_value.state, policy_value.accepted, audit_value.accepted, members, PACKAGE_FORMAT, contract_model.address_manifest(provisional))
    package_bytes = _zip_bytes(manifest, payloads)
    return verify_package(contract_model.Transport(manifest, package_bytes, hash_bytes(package_bytes, prefix=PACKAGE_PREFIX)))


def _read_zip(value: Any) -> tuple[bytes, dict[str, bytes], dict[str, zipfile.ZipInfo]]:
    raw = value.package_bytes if isinstance(value, contract_model.Transport) else bytes(value) if isinstance(value, (bytes, bytearray)) else read_bytes(value, field="module631 package", max_bytes=MAX_PACKAGE_BYTES)
    if len(raw) > MAX_PACKAGE_BYTES:
        raise ValidationError("module631 package exceeds its byte ceiling")
    try:
        with zipfile.ZipFile(io.BytesIO(raw), "r") as archive:
            infos = archive.infolist()
            if len(infos) != len(FILE_NAMES) or tuple(info.filename for info in infos) != FILE_NAMES or len(set(info.filename for info in infos)) != len(FILE_NAMES):
                raise ValidationError("module631 package member set or order is not fixed")
            bodies: dict[str, bytes] = {}
            records: dict[str, zipfile.ZipInfo] = {}
            for info in infos:
                if info.date_time != contract_model.FIXED_ZIP_DATE or info.compress_type != zipfile.ZIP_STORED or info.create_system != 0 or info.create_version != 20 or info.extract_version != 20 or info.flag_bits != 0 or info.internal_attr != 0 or info.external_attr != _FIXED_ATTRIBUTES or info.extra or info.comment:
                    raise ValidationError("module631 ZIP metadata is not canonical")
                body = archive.read(info)
                if info.file_size > MAX_MEMBER_BYTES or len(body) != info.file_size or len(body) > MAX_MEMBER_BYTES:
                    raise ValidationError("module631 package member size is invalid")
                bodies[info.filename] = body
                records[info.filename] = info
            return raw, bodies, records
    except (KeyError, OSError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise ValidationError("module631 package is not a readable fixed ZIP") from exc


def _manifest_and_bodies(value: Any) -> tuple[contract_model.Transport, dict[str, bytes]]:
    raw, bodies, _records = _read_zip(value)
    parsed = _strict_json_loads(bodies["manifest.json"].decode("utf-8"))
    if bodies["manifest.json"] != (canonical_json(parsed) + "\n").encode("utf-8"):
        raise ValidationError("module631 manifest is not canonical")
    manifest = contract_model.Manifest.from_mapping(parsed)
    if contract_model.address_manifest(manifest) != manifest.content_address:
        raise ValidationError("module631 manifest address does not replay")
    for path in PAYLOAD_NAMES:
        member = next(item for item in manifest.members if item.relative_path == path)
        body = bodies[path]
        if member.byte_count != len(body) or member.byte_address != contract_model.address_member_bytes(body) or member.content_address != contract_model.address_member(member):
            raise ValidationError("module631 member address or byte count does not replay")
    if raw != _zip_bytes(manifest, bodies):
        raise ValidationError("module631 ZIP bytes are not deterministic")
    return contract_model.Transport(manifest, raw, hash_bytes(raw, prefix=PACKAGE_PREFIX)), bodies


def verify_package(value: Any) -> contract_model.Transport:
    package, _ = _manifest_and_bodies(value)
    if _has_forbidden_key(package.to_dict()) or package.package_address != hash_bytes(package.package_bytes, prefix=PACKAGE_PREFIX):
        raise ValidationError("module631 package address or public boundary does not replay")
    return package


def load_package(value: Any) -> tuple[Any, Any, Any, str]:
    package, bodies = _manifest_and_bodies(value)
    diff = diff_model.verify_diff(_strict_json_loads(bodies["catalog-diff.json"].decode("utf-8")))
    policy = policy_model.verify_policy(_strict_json_loads(bodies["policy.json"].decode("utf-8")))
    audit = policy_audit_model.verify_audit(_strict_json_loads(bodies["policy-audit.json"].decode("utf-8")))
    review = bodies["review.md"].decode("utf-8")
    if package.manifest.diff_address != diff.content_address or package.manifest.policy_address != policy.content_address or package.manifest.audit_address != audit.content_address or policy.diff_address != diff.content_address or audit.diff_address != diff.content_address or audit.policy_address != policy.content_address or not audit.accepted or review != _review(diff, policy, audit):
        raise ValidationError("module631 nested lineage or review does not replay")
    if package.manifest.policy_state != policy.state or package.manifest.policy_accepted != policy.accepted or package.manifest.audit_accepted != audit.accepted:
        raise ValidationError("module631 policy decision flags do not replay")
    return diff, policy, audit, review


def write_package(value: Any, destination: str | Path, *, allow_existing: bool = False) -> contract_model.Transport:
    package = verify_package(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("module631 package destination already exists")
    _validate_parent(path.parent, "module631 package destination")
    atomic_write_bytes(path, package.package_bytes, field="module631 package destination")
    return package


def package_json(value: Any) -> str:
    return canonical_json(verify_package(value).to_dict()) + "\n"


def query_package(value: Any, *, resource: str = "summary", text: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    package = verify_package(value)
    diff, policy, audit, review = load_package(package)
    if resource not in {"summary", "manifest", "members", "diff", "policy", "audit", "review"}:
        raise ValidationError("module631 query resource is unsupported")
    if not isinstance(text, str) or len(text) > 4096 or not isinstance(offset, int) or offset < 0 or not isinstance(limit, int) or limit < 1 or limit > MAX_LIMIT:
        raise ValidationError("module631 query bounds are invalid")
    values: tuple[Any, ...] = (package.summary(),) if resource == "summary" else (package.manifest.to_dict(),) if resource == "manifest" else package.manifest.to_dict()["members"] if resource == "members" else (diff.to_dict(),) if resource == "diff" else (policy.to_dict(),) if resource == "policy" else (audit.to_dict(),) if resource == "audit" else (review,)
    total = len(values)
    matches = tuple(item for item in values if not text or text.casefold() in canonical_json(item).casefold())
    selected = matches[offset:offset + limit]
    result = {"package_address": package.package_address, "resource": resource, "text": text, "offset": offset, "limit": limit, "total": total, "matched": len(matches), "returned": len(selected), "truncated": offset + len(selected) < len(matches), "values": selected}
    return result | {"content_address": hash_bytes(canonical_json(result).encode("utf-8"), prefix=PACKAGE_PREFIX + "-query")}


def package_csv(value: Any, *, resource: str = "members", offset: int = 0, limit: int = 50) -> str:
    result = query_package(value, resource=resource, offset=offset, limit=limit)
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(("resource", "value"))
    for item in result["values"]:
        writer.writerow((resource, canonical_json(item) if not isinstance(item, str) else item))
    return stream.getvalue()


def render_package_markdown(value: Any) -> str:
    package = verify_package(value)
    diff, policy, audit, _ = load_package(package)
    lines = ["# Module631 Fixed Policy Decision Transport", "", f"- Package: `{package.package_address}`", f"- State: **{policy.state}**", f"- Policy accepted: **{str(policy.accepted).lower()}**", f"- Audit: **{audit.passed_count}/{audit.check_count}**", f"- Diff: `{diff.content_address}`", "", "| member | bytes | content address |", "| --- | ---: | --- |"]
    lines.extend(f"| `{item.relative_path}` | {item.byte_count} | `{item.content_address}` |" for item in package.manifest.members)
    return "\n".join(lines) + "\n"


def capabilities() -> dict[str, Any]:
    return contract_model.capabilities() | {"operations": ("build_package", "verify_package", "load_package", "write_package", "package_json", "package_csv", "render_package_markdown", "query_package")}


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Module631 transport member", "type": "object", "additionalProperties": False, "required": ["relative_path", "media_type", "byte_count", "byte_address", "content_address"]}


build_transport = build_package
verify_transport = verify_package
load_transport = load_package
write_transport = write_package
transport_json = package_json
transport_csv = package_csv
render_transport_markdown = render_package_markdown
Package = contract_model.Package
Manifest = contract_model.Manifest
Member = contract_model.Member
address_manifest = contract_model.address_manifest
address_member = contract_model.address_member
address_member_bytes = contract_model.address_member_bytes
package_schema = contract_model.package_schema
manifest_schema = contract_model.manifest_schema

__all__ = ["BOUNDARY", "DEFAULT_PACKAGE_ID", "FILE_NAMES", "MANIFEST_PREFIX", "MAX_MEMBER_BYTES", "MAX_PACKAGE_BYTES", "MEMBER_PREFIX", "PACKAGE_FORMAT", "PACKAGE_PREFIX", "PAYLOAD_NAMES", "VERSION", "build_package", "build_transport", "capabilities", "check_schema", "load_package", "load_transport", "manifest_schema", "package_csv", "package_json", "package_schema", "query_package", "render_package_markdown", "render_transport_markdown", "transport_csv", "transport_json", "verify_package", "verify_transport", "write_package", "write_transport"]
