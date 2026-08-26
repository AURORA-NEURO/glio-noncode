"""Deterministic review and remediation records for release attestations.

This module turns the final cross-plane attestation into a bounded operational
review surface.  It preserves the attestation's address-only boundary while
giving a release reviewer a stable row for every check, an explicit
disposition, and a closed or open action.  The output is intentionally free of
timestamps and execution payloads so two reviews of the same attestation
reconcile byte-for-byte.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping
from io import StringIO
from typing import Any

from .errors import ValidationError
from .release_assurance_attestation_contracts import (
    RELEASE_ASSURANCE_ATTESTATION_CHECK_COUNT,
    RELEASE_ASSURANCE_ATTESTATION_COMPONENT_IDS,
    RELEASE_ASSURANCE_ATTESTATION_DEFAULT_LIMIT,
    RELEASE_ASSURANCE_ATTESTATION_MAX_LIMIT,
    ReleaseAssuranceAttestation,
    ReleaseAssuranceAttestationCheck,
    ReleaseAssuranceAttestationRuntimeReport,
)
from .release_assurance_support import forbidden_keys
from .serialization import canonical_json, content_hash, jsonable

RELEASE_ASSURANCE_ATTESTATION_REVIEW_VERSION = "release-assurance-attestation-review-v1"
RELEASE_ASSURANCE_ATTESTATION_REVIEW_SCHEMA_VERSION = (
    "release-assurance-attestation-review-schema-v1"
)
RELEASE_ASSURANCE_ATTESTATION_REVIEW_BOUNDARY = "public_attestation_review"
RELEASE_ASSURANCE_ATTESTATION_REVIEW_MAX_ITEMS = 1000
RELEASE_ASSURANCE_ATTESTATION_REVIEW_ITEM_COUNT = RELEASE_ASSURANCE_ATTESTATION_CHECK_COUNT


def _text(value: Any, field: str, *, maximum: int = 360) -> str:
    if value is None:
        raise ValidationError(f"{field} must not be empty")
    result = str(value).strip()
    if not result:
        raise ValidationError(f"{field} must not be empty")
    if len(result) > maximum:
        raise ValidationError(f"{field} exceeds the maximum length")
    return result


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _int(value: Any, field: str, *, minimum: int = 0, maximum: int | None = None) -> int:
    if isinstance(value, bool):
        raise ValidationError(f"{field} must be an integer")
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(f"{field} must be an integer") from exc
    if result < minimum or (maximum is not None and result > maximum):
        bound = f"between {minimum} and {maximum}" if maximum is not None else f"at least {minimum}"
        raise ValidationError(f"{field} must be {bound}")
    return result


def _strings(value: Any, field: str, *, maximum: int = 64) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise ValidationError(f"{field} must be an array")
    result = tuple(_text(item, f"{field}[{index}]") for index, item in enumerate(value))
    if len(result) > maximum or len(set(result)) != len(result):
        raise ValidationError(f"{field} must be bounded and unique")
    return result


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return {str(key): item for key, item in value.items()}


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(dict(body), prefix=prefix)


def _priority(check: ReleaseAssuranceAttestationCheck) -> int:
    if check.passed:
        return 0
    if check.category in {"boundary", "acceptance"} or check.component_id == "cross-plane":
        return 100
    if check.category in {"conservation", "completeness"}:
        return 80
    return 60


def _severity(check: ReleaseAssuranceAttestationCheck) -> str:
    if check.passed:
        return "none"
    if _priority(check) >= 100:
        return "critical"
    if _priority(check) >= 80:
        return "high"
    return "moderate"


def _disposition(check: ReleaseAssuranceAttestationCheck) -> str:
    return "retain" if check.passed else "block-release"


def _action_state(check: ReleaseAssuranceAttestationCheck) -> str:
    return "closed" if check.passed else "open"


def _action_title(check: ReleaseAssuranceAttestationCheck) -> str:
    if check.passed:
        return "Retain accepted evidence"
    return f"Resolve failed {check.category} check"


def _action_text(check: ReleaseAssuranceAttestationCheck) -> str:
    if check.passed:
        return "No remediation is required; preserve the retained check evidence."
    return (
        f"Resolve {check.check_id}, reconcile the observed value with the expected value, "
        "then issue a new attestation."
    )


class ReleaseAssuranceAttestationReviewItem:
    """Public reviewer row derived from one attestation check."""

    __slots__ = (
        "item_id",
        "check_id",
        "component_id",
        "category",
        "passed",
        "priority",
        "severity",
        "disposition",
        "action_state",
        "action_title",
        "action_text",
        "detail",
        "evidence_addresses",
        "source_address",
        "content_address",
    )

    def __init__(
        self,
        item_id: str,
        check_id: str,
        component_id: str,
        category: str,
        passed: bool,
        priority: int,
        severity: str,
        disposition: str,
        action_state: str,
        action_title: str,
        action_text: str,
        detail: str,
        evidence_addresses: tuple[str, ...],
        source_address: str,
        content_address: str,
    ) -> None:
        self.item_id = item_id
        self.check_id = check_id
        self.component_id = component_id
        self.category = category
        self.passed = passed
        self.priority = priority
        self.severity = severity
        self.disposition = disposition
        self.action_state = action_state
        self.action_title = action_title
        self.action_text = action_text
        self.detail = detail
        self.evidence_addresses = evidence_addresses
        self.source_address = source_address
        self.content_address = content_address
        self._validate()

    def _body(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "check_id": self.check_id,
            "component_id": self.component_id,
            "category": self.category,
            "passed": self.passed,
            "priority": self.priority,
            "severity": self.severity,
            "disposition": self.disposition,
            "action_state": self.action_state,
            "action_title": self.action_title,
            "action_text": self.action_text,
            "detail": self.detail,
            "evidence_addresses": self.evidence_addresses,
            "source_address": self.source_address,
        }

    def _validate(self) -> None:
        _text(self.item_id, "review_item.item_id", maximum=180)
        _text(self.check_id, "review_item.check_id", maximum=180)
        _text(self.component_id, "review_item.component_id", maximum=96)
        _text(self.category, "review_item.category", maximum=64)
        _bool(self.passed, "review_item.passed")
        _int(self.priority, "review_item.priority", maximum=100)
        _text(self.severity, "review_item.severity", maximum=24)
        _text(self.disposition, "review_item.disposition", maximum=48)
        _text(self.action_state, "review_item.action_state", maximum=24)
        _text(self.action_title, "review_item.action_title", maximum=180)
        _text(self.action_text, "review_item.action_text", maximum=360)
        _text(self.detail, "review_item.detail", maximum=360)
        _strings(self.evidence_addresses, "review_item.evidence_addresses")
        _text(self.source_address, "review_item.source_address")
        _text(self.content_address, "review_item.content_address")
        if self.passed and (self.priority, self.severity, self.disposition, self.action_state) != (
            0,
            "none",
            "retain",
            "closed",
        ):
            raise ValidationError("accepted review item controls do not reconcile")
        if not self.passed and self.action_state != "open":
            raise ValidationError("failed review item must remain open")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self._body() | {"content_address": self.content_address})

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ReleaseAssuranceAttestationReviewItem:
        body = _mapping(value, "review item")
        allowed = {
            "item_id",
            "check_id",
            "component_id",
            "category",
            "passed",
            "priority",
            "severity",
            "disposition",
            "action_state",
            "action_title",
            "action_text",
            "detail",
            "evidence_addresses",
            "source_address",
            "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(f"review item contains unsupported fields: {sorted(unknown)}")
        item = cls(
            item_id=_text(body.get("item_id"), "review_item.item_id", maximum=180),
            check_id=_text(body.get("check_id"), "review_item.check_id", maximum=180),
            component_id=_text(body.get("component_id"), "review_item.component_id", maximum=96),
            category=_text(body.get("category"), "review_item.category", maximum=64),
            passed=_bool(body.get("passed"), "review_item.passed"),
            priority=_int(body.get("priority"), "review_item.priority", maximum=100),
            severity=_text(body.get("severity"), "review_item.severity", maximum=24),
            disposition=_text(body.get("disposition"), "review_item.disposition", maximum=48),
            action_state=_text(body.get("action_state"), "review_item.action_state", maximum=24),
            action_title=_text(body.get("action_title"), "review_item.action_title", maximum=180),
            action_text=_text(body.get("action_text"), "review_item.action_text", maximum=360),
            detail=_text(body.get("detail"), "review_item.detail", maximum=360),
            evidence_addresses=_strings(
                body.get("evidence_addresses"), "review_item.evidence_addresses"
            ),
            source_address=_text(body.get("source_address"), "review_item.source_address"),
            content_address=_text(body.get("content_address"), "review_item.content_address"),
        )
        if (
            _address(item._body(), "release-assurance-attestation-review-item")
            != item.content_address
        ):
            raise ValidationError("review item content address does not reconcile")
        return item


class ReleaseAssuranceAttestationReview:
    """Complete bounded review of a final attestation."""

    __slots__ = (
        "review_version",
        "schema_version",
        "review_id",
        "attestation_id",
        "source_address",
        "items",
        "open_action_count",
        "closed_action_count",
        "accepted",
        "content_address",
    )

    def __init__(
        self,
        review_version: str,
        schema_version: str,
        review_id: str,
        attestation_id: str,
        source_address: str,
        items: tuple[ReleaseAssuranceAttestationReviewItem, ...],
        open_action_count: int,
        closed_action_count: int,
        accepted: bool,
        content_address: str,
    ) -> None:
        self.review_version = review_version
        self.schema_version = schema_version
        self.review_id = review_id
        self.attestation_id = attestation_id
        self.source_address = source_address
        self.items = items
        self.open_action_count = open_action_count
        self.closed_action_count = closed_action_count
        self.accepted = accepted
        self.content_address = content_address
        self._validate()

    @property
    def item_count(self) -> int:
        return len(self.items)

    @property
    def failed_item_ids(self) -> tuple[str, ...]:
        return tuple(item.item_id for item in self.items if not item.passed)

    @property
    def boundary(self) -> str:
        return RELEASE_ASSURANCE_ATTESTATION_REVIEW_BOUNDARY

    def _body(self) -> dict[str, Any]:
        return {
            "review_version": self.review_version,
            "schema_version": self.schema_version,
            "review_id": self.review_id,
            "attestation_id": self.attestation_id,
            "source_address": self.source_address,
            "items": tuple(item.to_dict() for item in self.items),
            "open_action_count": self.open_action_count,
            "closed_action_count": self.closed_action_count,
            "accepted": self.accepted,
        }

    def _validate(self) -> None:
        _text(self.review_version, "review.review_version", maximum=96)
        _text(self.schema_version, "review.schema_version", maximum=120)
        _text(self.review_id, "review.review_id", maximum=160)
        _text(self.attestation_id, "review.attestation_id", maximum=160)
        _text(self.source_address, "review.source_address")
        if (
            not isinstance(self.items, tuple)
            or len(self.items) > RELEASE_ASSURANCE_ATTESTATION_REVIEW_MAX_ITEMS
        ):
            raise ValidationError("review items exceed the bounded maximum")
        if len({item.item_id for item in self.items}) != len(self.items):
            raise ValidationError("review item IDs must be unique")
        _int(self.open_action_count, "review.open_action_count")
        _int(self.closed_action_count, "review.closed_action_count")
        if self.open_action_count + self.closed_action_count != len(self.items):
            raise ValidationError("review action counters do not reconcile")
        _bool(self.accepted, "review.accepted")
        _text(self.content_address, "review.content_address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(
            self._body()
            | {
                "boundary": self.boundary,
                "item_count": self.item_count,
                "failed_item_ids": self.failed_item_ids,
                "content_address": self.content_address,
            }
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ReleaseAssuranceAttestationReview:
        body = _mapping(value, "attestation review")
        allowed = {
            "review_version",
            "schema_version",
            "review_id",
            "attestation_id",
            "source_address",
            "items",
            "open_action_count",
            "closed_action_count",
            "accepted",
            "content_address",
            "boundary",
            "item_count",
            "failed_item_ids",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(
                f"attestation review contains unsupported fields: {sorted(unknown)}"
            )
        if body.get("review_version") != RELEASE_ASSURANCE_ATTESTATION_REVIEW_VERSION:
            raise ValidationError("attestation review version is invalid")
        if body.get("schema_version") != RELEASE_ASSURANCE_ATTESTATION_REVIEW_SCHEMA_VERSION:
            raise ValidationError("attestation review schema version is invalid")
        if body.get("boundary") not in (None, RELEASE_ASSURANCE_ATTESTATION_REVIEW_BOUNDARY):
            raise ValidationError("attestation review boundary is invalid")
        raw_items = body.get("items")
        if not isinstance(raw_items, (list, tuple)):
            raise ValidationError("attestation review items must be an array")
        items = tuple(
            ReleaseAssuranceAttestationReviewItem.from_mapping(item) for item in raw_items
        )
        review = cls(
            review_version=str(body.get("review_version")),
            schema_version=str(body.get("schema_version")),
            review_id=_text(body.get("review_id"), "review.review_id", maximum=160),
            attestation_id=_text(body.get("attestation_id"), "review.attestation_id", maximum=160),
            source_address=_text(body.get("source_address"), "review.source_address"),
            items=items,
            open_action_count=_int(body.get("open_action_count"), "review.open_action_count"),
            closed_action_count=_int(body.get("closed_action_count"), "review.closed_action_count"),
            accepted=_bool(body.get("accepted"), "review.accepted"),
            content_address=_text(body.get("content_address"), "review.content_address"),
        )
        if body.get("item_count") != review.item_count:
            raise ValidationError("review item count does not reconcile")
        if tuple(body.get("failed_item_ids", ())) != review.failed_item_ids:
            raise ValidationError("review failed item IDs do not reconcile")
        if (
            _address(review._body(), "release-assurance-attestation-review")
            != review.content_address
        ):
            raise ValidationError("attestation review content address does not reconcile")
        return review


def _build_item(check: ReleaseAssuranceAttestationCheck) -> ReleaseAssuranceAttestationReviewItem:
    body = {
        "item_id": f"review:{check.check_id}",
        "check_id": check.check_id,
        "component_id": check.component_id,
        "category": check.category,
        "passed": check.passed,
        "priority": _priority(check),
        "severity": _severity(check),
        "disposition": _disposition(check),
        "action_state": _action_state(check),
        "action_title": _action_title(check),
        "action_text": _action_text(check),
        "detail": check.detail,
        "evidence_addresses": check.evidence_addresses,
        "source_address": check.content_address,
    }
    return ReleaseAssuranceAttestationReviewItem(
        **body,
        content_address=_address(body, "release-assurance-attestation-review-item"),
    )


def build_release_assurance_attestation_review(
    attestation: ReleaseAssuranceAttestation | Mapping[str, Any],
    *,
    runtime: ReleaseAssuranceAttestationRuntimeReport | None = None,
    review_id: str | None = None,
) -> ReleaseAssuranceAttestationReview:
    """Create one deterministic review item for each attestation check."""

    selected = (
        attestation
        if isinstance(attestation, ReleaseAssuranceAttestation)
        else ReleaseAssuranceAttestation.from_mapping(attestation)
    )
    items = tuple(_build_item(check) for check in selected.checks)
    open_count = sum(item.action_state == "open" for item in items)
    closed_count = len(items) - open_count
    source_address = selected.content_address
    accepted = (
        len(items) == RELEASE_ASSURANCE_ATTESTATION_REVIEW_ITEM_COUNT
        and selected.accepted
        and open_count == 0
        and (runtime is None or runtime.accepted)
        and not forbidden_keys([item.to_dict() for item in items])
    )
    body = {
        "review_version": RELEASE_ASSURANCE_ATTESTATION_REVIEW_VERSION,
        "schema_version": RELEASE_ASSURANCE_ATTESTATION_REVIEW_SCHEMA_VERSION,
        "review_id": review_id or f"{selected.attestation_id}-review",
        "attestation_id": selected.attestation_id,
        "source_address": source_address,
        "items": tuple(item.to_dict() for item in items),
        "open_action_count": open_count,
        "closed_action_count": closed_count,
        "accepted": accepted,
    }
    return ReleaseAssuranceAttestationReview(
        **(body | {"items": items}),
        content_address=_address(body, "release-assurance-attestation-review"),
    )


def audit_release_assurance_attestation_review(
    review: ReleaseAssuranceAttestationReview,
    attestation: ReleaseAssuranceAttestation,
    *,
    runtime: ReleaseAssuranceAttestationRuntimeReport | None = None,
) -> tuple[dict[str, Any], ...]:
    """Return explicit reconciliation rows for a review artifact."""

    expected_ids = tuple(f"review:{check.check_id}" for check in attestation.checks)
    actual_ids = tuple(item.item_id for item in review.items)
    checks: list[dict[str, Any]] = [
        {
            "check_id": "review:attestation-id",
            "passed": review.attestation_id == attestation.attestation_id,
            "observed": review.attestation_id,
            "expected": attestation.attestation_id,
        },
        {
            "check_id": "review:source-address",
            "passed": review.source_address == attestation.content_address,
            "observed": review.source_address,
            "expected": attestation.content_address,
        },
        {
            "check_id": "review:item-count",
            "passed": review.item_count
            == len(attestation.checks)
            == RELEASE_ASSURANCE_ATTESTATION_CHECK_COUNT,
            "observed": review.item_count,
            "expected": RELEASE_ASSURANCE_ATTESTATION_CHECK_COUNT,
        },
        {
            "check_id": "review:item-order",
            "passed": actual_ids == expected_ids,
            "observed": actual_ids,
            "expected": expected_ids,
        },
        {
            "check_id": "review:action-conservation",
            "passed": review.open_action_count + review.closed_action_count == review.item_count,
            "observed": review.open_action_count + review.closed_action_count,
            "expected": review.item_count,
        },
        {
            "check_id": "review:accepted",
            "passed": review.accepted == (attestation.accepted and review.open_action_count == 0),
            "observed": review.accepted,
            "expected": attestation.accepted and review.open_action_count == 0,
        },
        {
            "check_id": "review:runtime",
            "passed": runtime is None
            or review.accepted == (attestation.accepted and runtime.accepted),
            "observed": None if runtime is None else runtime.accepted,
            "expected": None if runtime is None else (attestation.accepted and runtime.accepted),
        },
        {
            "check_id": "review:boundary",
            "passed": not forbidden_keys(review.to_dict()),
            "observed": (),
            "expected": "no restricted public metadata",
        },
    ]
    return tuple(checks)


def query_release_assurance_attestation_review(
    review: ReleaseAssuranceAttestationReview,
    *,
    component_id: str | None = None,
    category: str | None = None,
    action_state: str | None = None,
    severity: str | None = None,
    failed_only: bool = False,
    text: str | None = None,
    offset: int = 0,
    limit: int = RELEASE_ASSURANCE_ATTESTATION_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Query review items with deterministic filters and bounded pagination."""

    offset = _int(offset, "review_query.offset")
    limit = _int(
        limit,
        "review_query.limit",
        minimum=1,
        maximum=min(
            RELEASE_ASSURANCE_ATTESTATION_MAX_LIMIT, RELEASE_ASSURANCE_ATTESTATION_REVIEW_MAX_ITEMS
        ),
    )
    normalized_text = None if text is None else str(text).strip().lower()
    rows = []
    for item in review.items:
        if component_id and item.component_id != component_id:
            continue
        if category and item.category != category:
            continue
        if action_state and item.action_state != action_state:
            continue
        if severity and item.severity != severity:
            continue
        if failed_only and item.passed:
            continue
        if normalized_text and normalized_text not in canonical_json(item.to_dict()).lower():
            continue
        rows.append(item.to_dict())
    page = tuple(rows[offset : offset + limit])
    return {
        "review_id": review.review_id,
        "attestation_id": review.attestation_id,
        "filters": {
            "component_id": component_id,
            "category": category,
            "action_state": action_state,
            "severity": severity,
            "failed_only": failed_only,
            "text": text,
        },
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": page,
        "has_more": offset + len(page) < len(rows),
        "accepted": True,
        "content_address": content_hash(
            {
                "review_id": review.review_id,
                "filters": {
                    "component_id": component_id,
                    "category": category,
                    "action_state": action_state,
                    "severity": severity,
                    "failed_only": failed_only,
                    "text": text,
                },
                "total": len(rows),
                "offset": offset,
                "limit": limit,
                "items": page,
            },
            prefix="release-assurance-attestation-review-query",
        ),
    }


def release_assurance_attestation_review_json(
    review: ReleaseAssuranceAttestationReview | Mapping[str, Any],
) -> str:
    selected = (
        review
        if isinstance(review, ReleaseAssuranceAttestationReview)
        else ReleaseAssuranceAttestationReview.from_mapping(review)
    )
    return canonical_json(selected.to_dict()) + "\n"


def release_assurance_attestation_review_csv(
    review: ReleaseAssuranceAttestationReview | Mapping[str, Any],
) -> str:
    selected = (
        review
        if isinstance(review, ReleaseAssuranceAttestationReview)
        else ReleaseAssuranceAttestationReview.from_mapping(review)
    )
    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        (
            "item_id",
            "check_id",
            "component_id",
            "category",
            "passed",
            "priority",
            "severity",
            "disposition",
            "action_state",
            "action_title",
            "source_address",
            "content_address",
        )
    )
    for item in selected.items:
        writer.writerow(
            (
                item.item_id,
                item.check_id,
                item.component_id,
                item.category,
                str(item.passed).lower(),
                item.priority,
                item.severity,
                item.disposition,
                item.action_state,
                item.action_title,
                item.source_address,
                item.content_address,
            )
        )
    return output.getvalue()


def release_assurance_attestation_review_markdown(
    review: ReleaseAssuranceAttestationReview | Mapping[str, Any],
) -> str:
    selected = (
        review
        if isinstance(review, ReleaseAssuranceAttestationReview)
        else ReleaseAssuranceAttestationReview.from_mapping(review)
    )
    lines = [
        "# Release assurance attestation review",
        "",
        f"- Review: `{selected.review_id}`",
        f"- Attestation: `{selected.attestation_id}`",
        f"- Accepted: `{str(selected.accepted).lower()}`",
        f"- Actions: `{selected.open_action_count} open / {selected.closed_action_count} closed`",
        "",
        "| Priority | Severity | Component | Check | State | Disposition |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| {item.priority} | {item.severity} | {item.component_id} | "
        f"`{item.check_id}` | {item.action_state} | {item.disposition} |"
        for item in selected.items
    )
    lines.extend(
        ("", "The review contains public action dispositions and content addresses only.", "")
    )
    return "\n".join(lines)


def release_assurance_attestation_review_export_payloads(
    review: ReleaseAssuranceAttestationReview,
) -> dict[str, bytes]:
    return {
        "review.json": release_assurance_attestation_review_json(review).encode("utf-8"),
        "review.csv": release_assurance_attestation_review_csv(review).encode("utf-8"),
        "review.md": release_assurance_attestation_review_markdown(review).encode("utf-8"),
    }


def release_assurance_attestation_review_schema() -> dict[str, Any]:
    return {
        "version": RELEASE_ASSURANCE_ATTESTATION_REVIEW_SCHEMA_VERSION,
        "boundary": RELEASE_ASSURANCE_ATTESTATION_REVIEW_BOUNDARY,
        "item_count": RELEASE_ASSURANCE_ATTESTATION_REVIEW_ITEM_COUNT,
        "item_fields": [
            "item_id",
            "check_id",
            "component_id",
            "category",
            "passed",
            "priority",
            "severity",
            "disposition",
            "action_state",
            "action_title",
            "action_text",
            "detail",
            "evidence_addresses",
            "source_address",
            "content_address",
        ],
        "closed_states": ["closed"],
        "open_states": ["open"],
        "source_payloads": False,
        "timestamp_free": True,
    }


def release_assurance_attestation_review_capabilities() -> dict[str, Any]:
    return {
        "version": "release-assurance-attestation-review-capabilities-v1",
        "one_item_per_check": True,
        "deterministic_disposition": True,
        "open_action_routing": True,
        "bounded_query": True,
        "component_filter": True,
        "category_filter": True,
        "severity_filter": True,
        "failed_only_filter": True,
        "review_audit": True,
        "json_export": True,
        "csv_export": True,
        "markdown_export": True,
        "source_payloads": False,
        "restricted_metadata": False,
        "supported_components": list(RELEASE_ASSURANCE_ATTESTATION_COMPONENT_IDS),
    }


__all__ = [
    "RELEASE_ASSURANCE_ATTESTATION_REVIEW_BOUNDARY",
    "RELEASE_ASSURANCE_ATTESTATION_REVIEW_ITEM_COUNT",
    "RELEASE_ASSURANCE_ATTESTATION_REVIEW_SCHEMA_VERSION",
    "RELEASE_ASSURANCE_ATTESTATION_REVIEW_VERSION",
    "ReleaseAssuranceAttestationReview",
    "ReleaseAssuranceAttestationReviewItem",
    "audit_release_assurance_attestation_review",
    "build_release_assurance_attestation_review",
    "query_release_assurance_attestation_review",
    "release_assurance_attestation_review_capabilities",
    "release_assurance_attestation_review_csv",
    "release_assurance_attestation_review_export_payloads",
    "release_assurance_attestation_review_json",
    "release_assurance_attestation_review_markdown",
    "release_assurance_attestation_review_schema",
]
