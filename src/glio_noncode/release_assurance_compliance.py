"""Public-boundary compliance checks for release-assurance projections."""

from __future__ import annotations

import re

from .release_assurance_contracts import (
    RELEASE_ASSURANCE_RUNTIME_STAGE_TOTAL,
    ReleaseAssuranceComplianceItem,
    ReleaseAssuranceComplianceReport,
    ReleaseAssuranceExportPacket,
    ReleaseAssurancePlane,
    ReleaseAssuranceRuntimeReport,
    ReleaseAssuranceSnapshot,
)
from .release_assurance_support import forbidden_keys, safe_relative_path
from .serialization import content_hash

_ADDRESS = re.compile(r"^[a-z0-9-]+:[0-9a-f]{64}$")


def _item(item_id: str, scope: str, rule: str, observed, passed: bool, detail: str) -> ReleaseAssuranceComplianceItem:
    body = {
        "item_id": item_id,
        "scope": scope,
        "rule": rule,
        "observed": observed,
        "passed": passed,
        "detail": detail,
    }
    return ReleaseAssuranceComplianceItem(
        **body,
        content_address=content_hash(body, prefix="release-assurance-compliance-item"),
    )


def _address_items(snapshot: ReleaseAssuranceSnapshot) -> list[ReleaseAssuranceComplianceItem]:
    values = (
        ("snapshot", snapshot.content_address),
        ("service-source", snapshot.service_snapshot_address),
        ("public-audit", snapshot.public_audit_address),
        *((f"domain:{item.domain_id}", item.content_address) for item in snapshot.domains),
        *((f"evidence:{item.link_id}", item.content_address) for item in snapshot.evidence),
        *((f"check:{item.check_id}", item.content_address) for item in snapshot.checks),
    )
    return [
        _item(
            f"address:{label}",
            "address",
            "content-address-format",
            address,
            bool(_ADDRESS.fullmatch(address)),
            "public content addresses use a stable prefix and sha256 digest",
        )
        for label, address in values
    ]


def audit_release_assurance_compliance(
    snapshot: ReleaseAssuranceSnapshot,
    *,
    runtime: ReleaseAssuranceRuntimeReport | None = None,
    packet: ReleaseAssuranceExportPacket | None = None,
) -> ReleaseAssuranceComplianceReport:
    """Audit metadata, address shape, stage closure, and export paths."""

    items = _address_items(snapshot)
    addresses = tuple(item.content_address for item in (*snapshot.domains, *snapshot.evidence, *snapshot.checks))
    items.extend((
        _item("boundary:forbidden-keys", "snapshot", "recursive-forbidden-key-filter",
              forbidden_keys(snapshot.to_dict()), not forbidden_keys(snapshot.to_dict()),
              "aggregate snapshot contains no prohibited metadata"),
        _item("boundary:address-uniqueness", "snapshot", "unique-row-addresses",
              len(addresses), len(set(addresses)), "domain, evidence, and check addresses are unique"),
        _item("boundary:domain-source", "snapshot", "non-empty-domain-sources",
              tuple(bool(item.source_address) for item in snapshot.domains),
              all(bool(item.source_address) for item in snapshot.domains),
              "every domain retains a source address"),
        _item("boundary:evidence-sources", "snapshot", "non-empty-evidence-sources",
              tuple(bool(item.source_address) for item in snapshot.evidence),
              all(bool(item.source_address) for item in snapshot.evidence),
              "every evidence link retains a source address"),
    ))
    if runtime is not None:
        items.extend((
            _item("runtime:stage-count", "runtime", "stage-denominator",
                  len(runtime.stages), len(runtime.stages) == RELEASE_ASSURANCE_RUNTIME_STAGE_TOTAL,
                  "runtime has twelve ordered stages"),
            _item("runtime:stage-ordinals", "runtime", "contiguous-stage-ordinals",
                  tuple(item.ordinal for item in runtime.stages),
                  tuple(item.ordinal for item in runtime.stages) == tuple(range(1, len(runtime.stages) + 1)),
                  "runtime stages are contiguous and ordered"),
            _item("runtime:accepted", "runtime", "runtime-acceptance",
                  runtime.accepted, runtime.accepted, "runtime acceptance remains explicit"),
            _item("runtime:boundary", "runtime", "runtime-forbidden-keys",
                  forbidden_keys(runtime.to_dict()), not forbidden_keys(runtime.to_dict()),
                  "runtime report contains no prohibited metadata"),
        ))
    if packet is not None:
        unsafe: list[str] = []
        for artifact in packet.artifacts:
            try:
                safe_relative_path(artifact.relative_path)
            except Exception:
                unsafe.append(artifact.relative_path)
        items.extend((
            _item("export:artifact-count", "export", "artifact-denominator",
                  len(packet.artifacts), len(packet.artifacts) == 10,
                  "export packet has ten artifacts"),
            _item("export:paths", "export", "safe-relative-paths",
                  tuple(unsafe), not unsafe, "export paths cannot escape their root"),
            _item("export:boundary", "export", "export-forbidden-keys",
                  forbidden_keys(packet.to_dict()), not forbidden_keys(packet.to_dict()),
                  "export packet metadata is public-safe"),
        ))
    accepted = snapshot.accepted and all(item.passed for item in items)
    body = {"bundle_id": snapshot.bundle_id, "items": items, "accepted": accepted}
    return ReleaseAssuranceComplianceReport(
        snapshot.bundle_id,
        tuple(items),
        accepted,
        content_hash(body, prefix="release-assurance-compliance"),
    )


def compliance_summary(report: ReleaseAssuranceComplianceReport) -> dict[str, object]:
    """Return compact counters for health and review clients."""

    return {
        "bundle_id": report.bundle_id,
        "accepted": report.accepted,
        "item_count": len(report.items),
        "passed_item_count": sum(item.passed for item in report.items),
        "failed_item_ids": report.failed_item_ids,
        "content_address": report.content_address,
        "plane": ReleaseAssurancePlane.PUBLIC_BOUNDARY.value,
    }


__all__ = ["audit_release_assurance_compliance", "compliance_summary"]
