"""Build and verify source-free release eligibility certificates."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import downloaded_data_review_packet_diff_policy_package as package_model
from . import downloaded_data_review_packet_diff_policy_run as run_model
from . import downloaded_data_review_packet_diff_policy_run_audit as run_audit_model
from ._safe_persistence import _validate_parent, atomic_write_text, read_text
from .downloaded_data_review_packet_diff_policy_release_certificate_contracts import (
    BOUNDARY,
    CERTIFICATE_PREFIX,
    DownloadedDataReviewPacketDiffPolicyReleaseCertificate,
    VERSION,
    address_certificate,
    capabilities,
    certificate_schema,
)
from .errors import ValidationError
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash

MAX_LIMIT = 256
CERTIFICATE_RESOURCES = ("summary", "lineage", "decision", "evidence")


def _label(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 256 or value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _same_mapping(left: Any, right: Any) -> bool:
    return canonical_json(left) == canonical_json(right)


def _certificate(
    certificate_id: str,
    run_value: Any,
    package_value: Any,
    run_audit_value: Any,
) -> DownloadedDataReviewPacketDiffPolicyReleaseCertificate:
    body = {
        "certificate_id": certificate_id,
        "version": VERSION,
        "boundary": BOUNDARY,
        "run_id": run_value.run_id,
        "run_address": run_value.content_address,
        "package_address": package_value.package_address,
        "package_byte_count": len(package_value.package_bytes),
        "run_audit_address": run_audit_value.content_address,
        "run_audit_accepted": run_audit_value.accepted,
        "profile": run_value.profile,
        "policy_address": run_value.policy_address,
        "policy_state": run_value.policy_state,
        "policy_accepted": run_value.policy_accepted,
        "policy_audit_address": run_value.policy_audit_address,
        "policy_audit_accepted": run_value.policy_audit_accepted,
        "package_audit_address": run_value.package_audit_address,
        "package_audit_accepted": run_value.package_audit_accepted,
        "release_eligible": run_audit_value.accepted and run_value.policy_accepted and run_value.policy_audit_accepted and run_value.package_audit_accepted and run_value.policy_state == "ready",
        "release_state": "ready" if run_audit_value.accepted and run_value.policy_accepted and run_value.policy_audit_accepted and run_value.package_audit_accepted and run_value.policy_state == "ready" else "blocked",
        "content_address": CERTIFICATE_PREFIX + ":pending",
    }
    provisional = DownloadedDataReviewPacketDiffPolicyReleaseCertificate(**body)
    return DownloadedDataReviewPacketDiffPolicyReleaseCertificate(**(body | {"content_address": address_certificate(provisional)}))


def _recomputed_run_audit(run_value: Any, package_value: Any) -> Any:
    audit_value = run_audit_model.audit_run(run_value, package=package_value)
    if not audit_value.accepted:
        raise ValidationError("release certificate requires an accepted independent run audit")
    return audit_value


def build_certificate(
    run: Any,
    package: Any,
    run_audit: Any | None = None,
    *,
    certificate_id: str | None = None,
) -> DownloadedDataReviewPacketDiffPolicyReleaseCertificate:
    """Create a certificate only after replaying the supplied run and package."""

    package_value = package_model.verify_package(package)
    run_value = run_model.verify_run(run, package=package_value)
    computed_audit = _recomputed_run_audit(run_value, package_value)
    if run_audit is None:
        audit_value = computed_audit
    else:
        audit_value = run_audit_model.verify_audit(run_audit)
        if not _same_mapping(audit_value.to_dict(), computed_audit.to_dict()):
            raise ValidationError("supplied run audit does not replay the supplied run and package")
    certificate_id = _label(certificate_id or run_value.run_id + "-certificate", "release certificate ID")
    certificate = _certificate(certificate_id, run_value, package_value, audit_value)
    return verify_certificate(certificate, run=run_value, package=package_value, run_audit=audit_value)


def verify_certificate(
    value: Any,
    *,
    run: Any | None = None,
    package: Any | None = None,
    run_audit: Any | None = None,
) -> DownloadedDataReviewPacketDiffPolicyReleaseCertificate:
    certificate = value if isinstance(value, DownloadedDataReviewPacketDiffPolicyReleaseCertificate) else load_certificate(value)
    if address_certificate(certificate) != certificate.content_address:
        raise ValidationError("downloaded-data release certificate address does not replay")
    if _has_forbidden_key(certificate.to_dict()):
        raise ValidationError("downloaded-data release certificate crosses the public boundary")
    run_value = None
    package_value = None
    audit_value = None
    if run is not None or package is not None or run_audit is not None:
        if run is None or package is None or run_audit is None:
            raise ValidationError("certificate lineage verification requires run, package, and run audit")
        package_value = package_model.verify_package(package)
        run_value = run_model.verify_run(run, package=package_value)
        audit_value = run_audit_model.verify_audit(run_audit)
        if certificate.run_id != run_value.run_id or certificate.run_address != run_value.content_address or certificate.package_address != package_value.package_address or certificate.package_byte_count != len(package_value.package_bytes) or certificate.run_audit_address != audit_value.content_address:
            raise ValidationError("release certificate run or package lineage does not replay")
        if certificate.policy_address != run_value.policy_address or certificate.policy_audit_address != run_value.policy_audit_address or certificate.package_audit_address != run_value.package_audit_address:
            raise ValidationError("release certificate policy lineage does not replay")
        if certificate.run_audit_accepted != audit_value.accepted:
            raise ValidationError("release certificate run audit acceptance does not replay")
    return DownloadedDataReviewPacketDiffPolicyReleaseCertificate.from_mapping(certificate.to_dict())


def load_certificate(value: bytes | bytearray | str | Path | Mapping[str, Any]) -> DownloadedDataReviewPacketDiffPolicyReleaseCertificate:
    if isinstance(value, Mapping):
        raw = dict(value)
    elif isinstance(value, (bytes, bytearray)):
        raw = _strict_json_loads(bytes(value).decode("utf-8"))
    else:
        raw = _strict_json_loads(read_text(value, field="downloaded-data release certificate", max_bytes=4 * 1024 * 1024))
    return DownloadedDataReviewPacketDiffPolicyReleaseCertificate.from_mapping(raw)


def certificate_json(value: Any) -> str:
    return canonical_json(verify_certificate(value).to_dict()) + "\n"


def write_certificate(value: Any, destination: str | Path, *, allow_existing: bool = False) -> DownloadedDataReviewPacketDiffPolicyReleaseCertificate:
    certificate = verify_certificate(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("downloaded-data release certificate destination already exists")
    if path.exists() and not path.is_file():
        raise ValidationError("downloaded-data release certificate destination is not a file")
    _validate_parent(path.parent, "downloaded-data release certificate destination")
    atomic_write_text(path, certificate_json(certificate), field="downloaded-data release certificate destination")
    return certificate


def query_certificate(value: Any, *, resource: str = "summary") -> dict[str, Any]:
    if resource not in CERTIFICATE_RESOURCES:
        raise ValidationError("downloaded-data release certificate resource is unsupported")
    certificate = verify_certificate(value)
    if resource == "summary":
        result: Any = {"resource": resource, "value": certificate.summary()}
    elif resource == "lineage":
        result = {"resource": resource, "value": {"run_id": certificate.run_id, "run_address": certificate.run_address, "package_address": certificate.package_address, "run_audit_address": certificate.run_audit_address, "policy_address": certificate.policy_address, "policy_audit_address": certificate.policy_audit_address, "package_audit_address": certificate.package_audit_address}}
    elif resource == "decision":
        result = {"resource": resource, "value": {"profile": certificate.profile, "policy_state": certificate.policy_state, "policy_accepted": certificate.policy_accepted, "release_state": certificate.release_state, "release_eligible": certificate.release_eligible}}
    else:
        result = {"resource": resource, "value": {"run_audit_accepted": certificate.run_audit_accepted, "policy_audit_accepted": certificate.policy_audit_accepted, "package_audit_accepted": certificate.package_audit_accepted, "package_byte_count": certificate.package_byte_count}}
    return result | {"certificate_address": certificate.content_address, "content_address": content_hash(result, prefix=CERTIFICATE_PREFIX + "-query")}


def certificate_csv(value: Any) -> str:
    certificate = verify_certificate(value)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=("evidence", "address", "accepted", "state"), lineterminator="\n")
    writer.writeheader()
    writer.writerows((
        {"evidence": "run-audit", "address": certificate.run_audit_address, "accepted": certificate.run_audit_accepted, "state": "complete"},
        {"evidence": "policy", "address": certificate.policy_address, "accepted": certificate.policy_accepted, "state": certificate.policy_state},
        {"evidence": "policy-audit", "address": certificate.policy_audit_address, "accepted": certificate.policy_audit_accepted, "state": "complete"},
        {"evidence": "package-audit", "address": certificate.package_audit_address, "accepted": certificate.package_audit_accepted, "state": "complete"},
        {"evidence": "release", "address": certificate.content_address, "accepted": certificate.release_eligible, "state": certificate.release_state},
    ))
    return stream.getvalue()


def render_certificate_markdown(value: Any) -> str:
    certificate = verify_certificate(value)
    return "\n".join((
        "# Downloaded Data Release Certificate", "",
        f"- Certificate: `{certificate.content_address}`",
        f"- Profile: **{certificate.profile}**",
        f"- Release state: **{certificate.release_state}**",
        f"- Eligible: **{str(certificate.release_eligible).lower()}**",
        f"- Policy: **{certificate.policy_state}** ({str(certificate.policy_accepted).lower()})",
        f"- Independent run audit: **{str(certificate.run_audit_accepted).lower()}**",
        f"- Package bytes: **{certificate.package_byte_count}**",
        "", "| evidence | address | accepted |", "| --- | --- | --- |",
        f"| run | `{certificate.run_address}` | true |",
        f"| package | `{certificate.package_address}` | true |",
        f"| run audit | `{certificate.run_audit_address}` | {str(certificate.run_audit_accepted).lower()} |",
        f"| policy audit | `{certificate.policy_audit_address}` | {str(certificate.policy_audit_accepted).lower()} |",
        f"| package audit | `{certificate.package_audit_address}` | {str(certificate.package_audit_accepted).lower()} |",
        "", "This certificate is source-free and records only addressed review evidence and the resulting release eligibility decision.", "",
    ))


__all__ = [
    "CERTIFICATE_RESOURCES", "DownloadedDataReviewPacketDiffPolicyReleaseCertificate", "build_certificate", "capabilities", "certificate_csv", "certificate_json", "certificate_schema", "load_certificate", "query_certificate", "render_certificate_markdown", "verify_certificate", "write_certificate",
]
