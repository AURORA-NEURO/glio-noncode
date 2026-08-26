"""Prioritized review queue and release-facing views for certification gaps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .module_certification_contracts import ModuleCertificationMatrix
from .serialization import canonical_json, content_hash, jsonable


class CertificationReviewSeverity:
    """Stable severity vocabulary for human review routing."""

    BLOCKING = "blocking"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True, slots=True)
class ModuleCertificationReviewItem:
    """One review entry grouped from one or more module certification gaps."""

    review_id: str
    module_id: str
    family: str
    role: str
    severity: str
    priority: int
    score: float
    gap_count: int
    gap_ids: tuple[str, ...]
    check_kinds: tuple[str, ...]
    disposition: str
    content_address: str

    def __post_init__(self) -> None:
        if not all(
            isinstance(getattr(self, field), str) and getattr(self, field).strip()
            for field in (
                "review_id",
                "module_id",
                "family",
                "role",
                "severity",
                "disposition",
                "content_address",
            )
        ):
            raise ValidationError("certification review item identifiers are required")
        if self.severity not in {
            CertificationReviewSeverity.BLOCKING,
            CertificationReviewSeverity.HIGH,
            CertificationReviewSeverity.MEDIUM,
            CertificationReviewSeverity.LOW,
        }:
            raise ValidationError("certification review severity is unsupported")
        if not 0.0 <= self.score <= 1.0 or self.priority < 0 or self.gap_count < 1:
            raise ValidationError("certification review item values are invalid")
        if not self.gap_ids or tuple(sorted(set(self.gap_ids))) != self.gap_ids:
            raise ValidationError("certification review gap IDs must be sorted and unique")
        if not self.check_kinds or tuple(sorted(set(self.check_kinds))) != self.check_kinds:
            raise ValidationError("certification review check kinds must be sorted and unique")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleCertificationReviewQueue:
    """Conserved, bounded queue of module review work."""

    matrix_address: str
    items: tuple[ModuleCertificationReviewItem, ...]
    blocking_count: int
    high_count: int
    medium_count: int
    low_count: int
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        if not self.matrix_address.strip() or not self.content_address.strip():
            raise ValidationError("certification review queue addresses are required")
        order = tuple((item.priority, item.module_id, item.review_id) for item in self.items)
        if order != tuple(sorted(order)):
            raise ValidationError("certification review queue is not priority ordered")
        if sum((self.blocking_count, self.high_count, self.medium_count, self.low_count)) != len(
            self.items
        ):
            raise ValidationError("certification review severity counts do not conserve items")

    @property
    def item_count(self) -> int:
        return len(self.items)

    def to_dict(self, *, include_items: bool = True) -> dict[str, Any]:
        result = {
            "version": "module-certification-review-v1",
            "matrix_address": self.matrix_address,
            "item_count": self.item_count,
            "blocking_count": self.blocking_count,
            "high_count": self.high_count,
            "medium_count": self.medium_count,
            "low_count": self.low_count,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_items:
            result["items"] = [item.to_dict() for item in self.items]
        return result


def _severity(gap_kind: str, role: str) -> tuple[str, int]:
    if gap_kind in {"parse", "dependency", "boundary"}:
        return CertificationReviewSeverity.BLOCKING, 0
    if role == "integration" and gap_kind in {"documentation", "export"}:
        return CertificationReviewSeverity.HIGH, 20
    if gap_kind in {"test", "documentation", "export"}:
        return CertificationReviewSeverity.MEDIUM, 40
    return CertificationReviewSeverity.LOW, 70


def build_module_certification_review_queue(
    matrix: ModuleCertificationMatrix,
) -> ModuleCertificationReviewQueue:
    """Group all gaps by module while retaining check-level identity."""

    if not isinstance(matrix, ModuleCertificationMatrix):
        raise ValidationError("certification review requires a typed matrix")
    gaps_by_module: dict[str, list[Any]] = {}
    for gap in matrix.gaps:
        gaps_by_module.setdefault(gap.module_id, []).append(gap)
    rows = {row.module_id: row for row in matrix.rows}
    items: list[ModuleCertificationReviewItem] = []
    for module_id in sorted(gaps_by_module):
        gaps = tuple(
            sorted(gaps_by_module[module_id], key=lambda item: (item.priority, item.kind.value))
        )
        row = rows[module_id]
        severity, priority = min(
            (_severity(gap.kind.value, row.role) for gap in gaps), key=lambda item: item[1]
        )
        body = {
            "review_id": f"review:{module_id}",
            "module_id": module_id,
            "family": row.family,
            "role": row.role,
            "severity": severity,
            "priority": priority,
            "score": row.score,
            "gap_count": len(gaps),
            "gap_ids": tuple(sorted(gap.gap_id for gap in gaps)),
            "check_kinds": tuple(sorted(gap.kind.value for gap in gaps)),
            "disposition": "open",
        }
        items.append(
            ModuleCertificationReviewItem(
                **body,
                content_address=content_hash(body, prefix="module-certification-review-item"),
            )
        )
    ordered = tuple(sorted(items, key=lambda item: (item.priority, item.module_id, item.review_id)))
    body = {
        "matrix_address": matrix.content_address,
        "items": ordered,
        "blocking_count": sum(
            item.severity == CertificationReviewSeverity.BLOCKING for item in ordered
        ),
        "high_count": sum(item.severity == CertificationReviewSeverity.HIGH for item in ordered),
        "medium_count": sum(
            item.severity == CertificationReviewSeverity.MEDIUM for item in ordered
        ),
        "low_count": sum(item.severity == CertificationReviewSeverity.LOW for item in ordered),
        "accepted": matrix.accepted,
    }
    return ModuleCertificationReviewQueue(
        **body, content_address=content_hash(body, prefix="module-certification-review-queue")
    )


def query_module_certification_review(
    value: ModuleCertificationReviewQueue,
    *,
    severity: str | None = None,
    role: str | None = None,
    disposition: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    """Return a bounded page for review routing and dashboards."""

    if not isinstance(value, ModuleCertificationReviewQueue):
        raise ValidationError("certification review query requires a typed queue")
    if offset < 0 or limit < 1 or limit > 512:
        raise ValidationError("certification review pagination is invalid")
    rows = list(value.items)
    if severity is not None:
        rows = [item for item in rows if item.severity == severity]
    if role is not None:
        rows = [item for item in rows if item.role == role]
    if disposition is not None:
        rows = [item for item in rows if item.disposition == disposition]
    if text is not None:
        rows = [
            item for item in rows if text.casefold() in canonical_json(item.to_dict()).casefold()
        ]
    body = {
        "resource": "review",
        "query": {
            "severity": severity,
            "role": role,
            "disposition": disposition,
            "text": text,
            "offset": offset,
            "limit": limit,
        },
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < len(rows),
        "items": tuple(rows[offset : offset + limit]),
        "matrix_address": value.matrix_address,
        "accepted": value.accepted,
    }
    return body | {
        "content_address": content_hash(body, prefix="module-certification-review-query")
    }


def render_module_certification_review_markdown(value: ModuleCertificationReviewQueue) -> str:
    selected = value
    lines = [
        "# Module certification review queue",
        "",
        f"- Matrix address: `{selected.matrix_address}`",
        f"- Open items: **{selected.item_count:,}**",
        f"- Blocking / high / medium / low: **{selected.blocking_count:,} / "
        f"{selected.high_count:,} / {selected.medium_count:,} / {selected.low_count:,}**",
        f"- Accepted input: **{str(selected.accepted).lower()}**",
        "",
        "| Priority | Severity | Module | Role | Score | Gaps | Checks |",
        "| ---: | --- | --- | --- | ---: | ---: | --- |",
    ]
    for item in selected.items:
        lines.append(
            f"| {item.priority} | {item.severity} | `{item.module_id}` | {item.role} | "
            f"{item.score * 100:.2f}% | {item.gap_count} | {', '.join(item.check_kinds)} |"
        )
    return "\n".join(lines) + "\n"


def module_certification_review_schema() -> dict[str, Any]:
    return {
        "version": "module-certification-review-v1",
        "boundary": "public_aggregate_module_certification_review",
        "severity": ["blocking", "high", "medium", "low"],
        "dispositions": ["open"],
        "filters": ["severity", "role", "disposition", "text"],
        "ordering": "priority, module_id, review_id",
        "conservation": "one review item per module with one or more gaps",
    }


def module_certification_review_capabilities() -> dict[str, Any]:
    operations = (
        "group_gaps_by_module",
        "route_parse_gaps",
        "route_dependency_gaps",
        "route_boundary_gaps",
        "route_coverage_gaps",
        "route_integration_gaps",
        "query_review_queue",
        "render_review_markdown",
    )
    return {
        "version": "module-certification-review-v1",
        "operation_count": len(operations),
        "operations": list(operations),
        "read_only": True,
        "deterministic": True,
    }


__all__ = [
    "CertificationReviewSeverity",
    "ModuleCertificationReviewItem",
    "ModuleCertificationReviewQueue",
    "build_module_certification_review_queue",
    "module_certification_review_capabilities",
    "module_certification_review_schema",
    "query_module_certification_review",
    "render_module_certification_review_markdown",
]
