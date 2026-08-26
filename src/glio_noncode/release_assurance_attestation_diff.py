"""Structural diffs between two public release attestations."""

from __future__ import annotations

import csv
from collections.abc import Mapping
from io import StringIO
from typing import Any

from .release_assurance_attestation_contracts import (
    ReleaseAssuranceAttestation,
    ReleaseAssuranceAttestationDiff,
)
from .serialization import canonical_json, content_hash


def _as_attestation(
    value: ReleaseAssuranceAttestation | Mapping[str, Any],
) -> ReleaseAssuranceAttestation:
    return (
        value
        if isinstance(value, ReleaseAssuranceAttestation)
        else ReleaseAssuranceAttestation.from_mapping(value)
    )


def _changed_fields(
    left: Mapping[str, Any], right: Mapping[str, Any], excluded: set[str]
) -> tuple[str, ...]:
    return tuple(
        sorted(
            key
            for key in set(left) | set(right)
            if key not in excluded and left.get(key) != right.get(key)
        )
    )


def diff_release_assurance_attestations(
    left: ReleaseAssuranceAttestation | Mapping[str, Any],
    right: ReleaseAssuranceAttestation | Mapping[str, Any],
) -> ReleaseAssuranceAttestationDiff:
    """Compare component and check identities without carrying source rows."""

    before = _as_attestation(left)
    after = _as_attestation(right)
    left_components = {item.component_id: item.to_dict() for item in before.components}
    right_components = {item.component_id: item.to_dict() for item in after.components}
    shared_components = sorted(set(left_components) & set(right_components))
    changed_components = tuple(
        item for item in shared_components if left_components[item] != right_components[item]
    )
    unchanged_components = tuple(
        item for item in shared_components if item not in changed_components
    )
    left_checks = {item.check_id: item.to_dict() for item in before.checks}
    right_checks = {item.check_id: item.to_dict() for item in after.checks}
    shared_checks = sorted(set(left_checks) & set(right_checks))
    changed_checks = tuple(
        item for item in shared_checks if left_checks[item] != right_checks[item]
    )
    unchanged_checks = tuple(item for item in shared_checks if item not in changed_checks)
    policy_fields = _changed_fields(
        before.policy.to_dict(), after.policy.to_dict(), {"policy_version"}
    )
    body = {
        "left_attestation_id": before.attestation_id,
        "right_attestation_id": after.attestation_id,
        "left_address": before.content_address,
        "right_address": after.content_address,
        "added_component_ids": tuple(sorted(set(right_components) - set(left_components))),
        "removed_component_ids": tuple(sorted(set(left_components) - set(right_components))),
        "changed_component_ids": changed_components,
        "unchanged_component_ids": unchanged_components,
        "added_check_ids": tuple(sorted(set(right_checks) - set(left_checks))),
        "removed_check_ids": tuple(sorted(set(left_checks) - set(right_checks))),
        "changed_check_ids": changed_checks,
        "unchanged_check_ids": unchanged_checks,
        "changed_policy_fields": policy_fields,
        "identical": before.content_address == after.content_address,
        "accepted": before.accepted and after.accepted,
    }
    return ReleaseAssuranceAttestationDiff(
        **body, content_address=content_hash(body, prefix="release-assurance-attestation-diff")
    )


def release_assurance_attestation_diff_json(value: ReleaseAssuranceAttestationDiff) -> str:
    """Return canonical JSON for a structural diff."""

    return canonical_json(value.to_dict()) + "\n"


def release_assurance_attestation_diff_csv(value: ReleaseAssuranceAttestationDiff) -> str:
    """Return one row per diff class for tabular review."""

    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("change_type", "identifier"))
    for change_type, values in (
        ("added_component", value.added_component_ids),
        ("removed_component", value.removed_component_ids),
        ("changed_component", value.changed_component_ids),
        ("unchanged_component", value.unchanged_component_ids),
        ("added_check", value.added_check_ids),
        ("removed_check", value.removed_check_ids),
        ("changed_check", value.changed_check_ids),
        ("unchanged_check", value.unchanged_check_ids),
        ("changed_policy_field", value.changed_policy_fields),
    ):
        for identifier in values:
            writer.writerow((change_type, identifier))
    return output.getvalue()


def release_assurance_attestation_diff_markdown(value: ReleaseAssuranceAttestationDiff) -> str:
    """Render a compact structural diff for reviewers."""

    rows = [
        {
            "change_type": "added components",
            "count": len(value.added_component_ids),
            "items": ", ".join(value.added_component_ids),
        },
        {
            "change_type": "removed components",
            "count": len(value.removed_component_ids),
            "items": ", ".join(value.removed_component_ids),
        },
        {
            "change_type": "changed components",
            "count": len(value.changed_component_ids),
            "items": ", ".join(value.changed_component_ids),
        },
        {
            "change_type": "added checks",
            "count": len(value.added_check_ids),
            "items": ", ".join(value.added_check_ids),
        },
        {
            "change_type": "removed checks",
            "count": len(value.removed_check_ids),
            "items": ", ".join(value.removed_check_ids),
        },
        {
            "change_type": "changed checks",
            "count": len(value.changed_check_ids),
            "items": ", ".join(value.changed_check_ids),
        },
        {
            "change_type": "changed policy fields",
            "count": len(value.changed_policy_fields),
            "items": ", ".join(value.changed_policy_fields),
        },
    ]
    lines = [
        "# Release assurance attestation diff",
        "",
        f"- Left: `{value.left_address}`",
        f"- Right: `{value.right_address}`",
        f"- Identical: `{str(value.identical).lower()}`",
        "",
        "| Change | Count | Items |",
        "| --- | ---: | --- |",
    ]
    lines.extend(
        f"| {row['change_type']} | {row['count']} | {row['items'] or 'None'} |" for row in rows
    )
    return "\n".join(lines) + "\n"


def release_assurance_attestation_diff_export_payloads(
    value: ReleaseAssuranceAttestationDiff,
) -> dict[str, bytes]:
    """Return all deterministic diff exports."""

    return {
        "diff.json": release_assurance_attestation_diff_json(value).encode("utf-8"),
        "diff.csv": release_assurance_attestation_diff_csv(value).encode("utf-8"),
        "diff.md": release_assurance_attestation_diff_markdown(value).encode("utf-8"),
    }


def release_assurance_attestation_diff_schema() -> dict[str, Any]:
    """Describe address-only diff resources."""

    return {
        "version": "release-assurance-attestation-diff-schema-v1",
        "identity": ["component_id", "check_id"],
        "policy_fields": True,
        "source_payloads": False,
        "address_only": True,
    }


def release_assurance_attestation_diff_capabilities() -> dict[str, Any]:
    """Describe diff guarantees."""

    return {
        "version": "release-assurance-attestation-diff-capabilities-v1",
        "component_diff": True,
        "check_diff": True,
        "policy_diff": True,
        "identical_detection": True,
        "json_export": True,
        "csv_export": True,
        "markdown_export": True,
        "source_payloads": False,
    }


__all__ = [
    "diff_release_assurance_attestations",
    "release_assurance_attestation_diff_capabilities",
    "release_assurance_attestation_diff_csv",
    "release_assurance_attestation_diff_export_payloads",
    "release_assurance_attestation_diff_json",
    "release_assurance_attestation_diff_markdown",
    "release_assurance_attestation_diff_schema",
]
