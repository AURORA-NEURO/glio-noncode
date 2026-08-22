"""Public aggregate fixture for the Domain 15 C09-C12 collaboration frontier.

The fixture is deliberately small enough to inspect by hand and rich enough to
exercise every accepted path plus multiple negative controls for each surface.
It contains only aggregate research planning values, public source receipts,
and deterministic expectations.  No row represents a person, a specimen, or a
clinical decision.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty

GAMMA_FRONTIER_FIXTURE_VERSION = "2026.08.d15-c09-c12.v1"
GAMMA_FRONTIER_CONTEXT_KEY = "GRCh38|glioma|adult|stem_like|core|untreated"
GAMMA_FRONTIER_OTHER_CONTEXT_KEY = "GRCh38|glioma|adult|differentiated|core|untreated"
GAMMA_FRONTIER_EVIDENCE_BOUNDARY = "public_aggregate_non_patient"
GAMMA_FRONTIER_SOURCE_COUNT = 5
GAMMA_FRONTIER_POSITIVE_COUNT = 4
GAMMA_FRONTIER_CONTROL_COUNT = 12


class GammaFrontierOperation(StrEnum):
    """Four collaboration surfaces verified by the public package."""

    EXPERIMENT_BOARD = "experiment_board"
    LAUNCH_PLAN = "launch_plan"
    SHAREABLE_SNAPSHOT = "shareable_snapshot"
    COLLABORATION_ACCESS = "collaboration_access"


class GammaFrontierRole(StrEnum):
    """Fixture row role used for positive and control accounting."""

    POSITIVE = "positive"
    CONTROL = "control"


@dataclass(frozen=True, slots=True)
class GammaFrontierSourceReceipt:
    """Public source receipt retained with every package."""

    source_id: str
    title: str
    uri: str
    access_note: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("source_id", "title", "uri", "access_note", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.uri.startswith("https://"):
            raise ValueError("gamma frontier source URI must use HTTPS")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GammaFrontierRecord:
    """One executable surface case with an expected result contract."""

    record_id: str
    operation: GammaFrontierOperation
    role: GammaFrontierRole
    context_key: str
    source_ids: tuple[str, ...]
    payload: dict[str, Any]
    expected_state: str
    expected_issue_codes: tuple[str, ...]
    notes: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("record_id", "context_key", "expected_state", "notes", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.source_ids or len(self.source_ids) != len(set(self.source_ids)):
            raise ValueError("gamma frontier record source IDs must be non-empty and unique")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GammaFrontierFixture:
    """Immutable aggregate package for C09-C12."""

    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    sources: tuple[GammaFrontierSourceReceipt, ...]
    records: tuple[GammaFrontierRecord, ...]
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "fixture_id",
            "fixture_version",
            "context_key",
            "evidence_boundary",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not self.sources or not self.records:
            raise ValueError("gamma frontier fixture requires sources and records")
        if len({item.record_id for item in self.records}) != len(self.records):
            raise ValueError("gamma frontier record IDs must be unique")

    @property
    def positive_records(self) -> tuple[GammaFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is GammaFrontierRole.POSITIVE)

    @property
    def control_records(self) -> tuple[GammaFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is GammaFrontierRole.CONTROL)

    def record_map(self) -> dict[str, GammaFrontierRecord]:
        return {item.record_id: item for item in self.records}

    def source_map(self) -> dict[str, GammaFrontierSourceReceipt]:
        return {item.source_id: item for item in self.sources}

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GammaFrontierCatalog:
    """Index of records, sources, operations, and context."""

    fixture_id: str
    record_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    operations: tuple[GammaFrontierOperation, ...]
    context_key: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GammaFrontierDataCheck:
    """One deterministic fixture integrity assertion."""

    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GammaFrontierDataAudit:
    """Aggregate data boundary and fixture-shape report."""

    fixture_id: str
    checks: tuple[GammaFrontierDataCheck, ...]
    accepted: bool
    failed_check_ids: tuple[str, ...]
    content_address: str

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed_count": self.passed_count,
            "failed_check_ids": list(self.failed_check_ids),
        }


def _source(source_id: str, title: str, uri: str, access_note: str) -> GammaFrontierSourceReceipt:
    body = {"source_id": source_id, "title": title, "uri": uri, "access_note": access_note}
    return GammaFrontierSourceReceipt(**body, content_address=content_hash(body))


def _record(
    record_id: str,
    operation: GammaFrontierOperation,
    role: GammaFrontierRole,
    payload: dict[str, Any],
    expected_state: str,
    expected_issue_codes: tuple[str, ...],
    notes: str,
    source_ids: tuple[str, ...] = ("workspace-public",),
    context_key: str = GAMMA_FRONTIER_CONTEXT_KEY,
) -> GammaFrontierRecord:
    body = {
        "record_id": record_id,
        "operation": operation,
        "role": role,
        "context_key": context_key,
        "source_ids": source_ids,
        "payload": payload,
        "expected_state": expected_state,
        "expected_issue_codes": expected_issue_codes,
        "notes": notes,
    }
    return GammaFrontierRecord(**body, content_address=content_hash(body))


def _cards(
    context_key: str = GAMMA_FRONTIER_CONTEXT_KEY,
    *,
    malformed: bool = False,
    missing_dependency: bool = False,
) -> list[dict[str, Any]]:
    first = {
        "experiment_id": "exp-board-01",
        "target_id": "target-aggregate-1",
        "title": "Context-preserving perturbation readout",
        "assay_type": "aggregate_reporter",
        "status": "ready",
        "context_key": context_key,
        "priority": 4 if not malformed else 9,
        "owner": "planning-group",
        "source_id": "workspace-public",
        "readout": "normalized aggregate signal",
        "notes": ["public aggregate", "review before scheduling"],
    }
    second = {
        "experiment_id": "exp-board-02",
        "target_id": "target-aggregate-1",
        "title": "Orthogonal confirmation readout",
        "assay_type": "aggregate_confirmation",
        "status": "blocked",
        "context_key": context_key,
        "priority": 5,
        "owner": "planning-group",
        "dependencies": ["exp-board-99" if missing_dependency else "exp-board-01"],
        "blockers": ["aggregate reference pending"],
        "source_id": "workspace-public",
        "readout": "directionally concordant signal",
    }
    return [first, second]


def _launches(
    context_key: str = GAMMA_FRONTIER_CONTEXT_KEY,
    *,
    foreign: bool = False,
    bad_runtime: bool = False,
    bad_resource: bool = False,
) -> list[dict[str, Any]]:
    active_context = GAMMA_FRONTIER_OTHER_CONTEXT_KEY if foreign else context_key
    return [
        {
            "request_id": "launch-01",
            "artifact_id": "notebook-aggregate-summary",
            "runtime": "python" if not bad_runtime else "wasm",
            "mode": "notebook",
            "context_key": active_context,
            "entrypoint": "summary.main",
            "parameters": {"window": 2000, "tier": "aggregate"},
            "resource_profile": "small" if not bad_resource else "xlarge",
            "source_id": "workspace-public",
        }
    ]


def _snapshot(
    context_key: str = GAMMA_FRONTIER_CONTEXT_KEY, *, tampered: bool = False, expired: bool = False
) -> dict[str, Any]:
    return {
        "snapshot_payload": {
            "workspace_id": "public-workspace-1",
            "rows": ["aggregate-1", "aggregate-2"],
        },
        "snapshot_id": "snapshot-gamma-01",
        "snapshot_type": "review_projection",
        "context_key": context_key,
        "key_id": "public-fixture-key",
        "signing_secret": "gamma-fixture-secret",
        "verify_secret": "gamma-fixture-secret" if not tampered else "wrong-fixture-secret",
        "audience": ["review-group"],
        "expires_at": "2000-01-01T00:00:00+00:00" if expired else None,
        "now": "2026-08-22T12:00:00+00:00",
    }


def _collaboration(
    context_key: str = GAMMA_FRONTIER_CONTEXT_KEY,
    *,
    foreign: bool = False,
    inactive: bool = False,
    unknown: bool = False,
) -> dict[str, Any]:
    request_context = GAMMA_FRONTIER_OTHER_CONTEXT_KEY if foreign else context_key
    member_id = "missing-member" if unknown else "reviewer-gamma"
    return {
        "workspace_id": "public-workspace-1",
        "members": [
            {
                "member_id": "reviewer-gamma",
                "display_label": "Aggregate reviewer",
                "role": "reviewer",
                "context_key": context_key,
                "active": not inactive,
                "source_id": "workspace-public",
            },
            {
                "member_id": "viewer-gamma",
                "display_label": "Aggregate viewer",
                "role": "viewer",
                "context_key": context_key,
                "active": True,
                "source_id": "workspace-public",
            },
        ],
        "requests": [
            {
                "request_id": "access-gamma-01",
                "member_id": member_id,
                "action": "approve",
                "target_id": "snapshot-gamma-01",
                "context_key": request_context,
                "reason": "review aggregate projection",
            },
        ],
    }


def default_gamma_frontier_fixture() -> GammaFrontierFixture:
    """Build the canonical four-positive twelve-control public fixture."""

    records = (
        _record(
            "gamma-board-positive",
            GammaFrontierOperation.EXPERIMENT_BOARD,
            GammaFrontierRole.POSITIVE,
            {"cards": _cards()},
            "blocked",
            (),
            "two cards, one declared dependency, one retained blocker",
        ),
        _record(
            "gamma-board-foreign",
            GammaFrontierOperation.EXPERIMENT_BOARD,
            GammaFrontierRole.CONTROL,
            {"cards": _cards(GAMMA_FRONTIER_OTHER_CONTEXT_KEY)},
            "out_of_domain",
            ("context_mismatch",),
            "foreign context is excluded from the board",
            context_key=GAMMA_FRONTIER_OTHER_CONTEXT_KEY,
        ),
        _record(
            "gamma-board-dependency",
            GammaFrontierOperation.EXPERIMENT_BOARD,
            GammaFrontierRole.CONTROL,
            {"cards": _cards(missing_dependency=True)},
            "blocked",
            ("unknown_dependency",),
            "missing dependency remains visible as a warning",
        ),
        _record(
            "gamma-board-invalid",
            GammaFrontierOperation.EXPERIMENT_BOARD,
            GammaFrontierRole.CONTROL,
            {"cards": [_cards(malformed=True)[0]]},
            "abstained",
            ("invalid_experiment_card",),
            "invalid priority is retained as a malformed-card receipt",
        ),
        _record(
            "gamma-launch-positive",
            GammaFrontierOperation.LAUNCH_PLAN,
            GammaFrontierRole.POSITIVE,
            {"requests": _launches()},
            "ready_for_review",
            (),
            "bounded offline notebook descriptor",
        ),
        _record(
            "gamma-launch-foreign",
            GammaFrontierOperation.LAUNCH_PLAN,
            GammaFrontierRole.CONTROL,
            {
                "requests": _launches(GAMMA_FRONTIER_OTHER_CONTEXT_KEY),
                "context_key": GAMMA_FRONTIER_CONTEXT_KEY,
            },
            "out_of_domain",
            ("context_mismatch",),
            "foreign launch request is quarantined",
        ),
        _record(
            "gamma-launch-runtime",
            GammaFrontierOperation.LAUNCH_PLAN,
            GammaFrontierRole.CONTROL,
            {"requests": _launches(bad_runtime=True)},
            "abstained",
            ("invalid_launch_request",),
            "unsupported runtime is rejected",
        ),
        _record(
            "gamma-launch-resource",
            GammaFrontierOperation.LAUNCH_PLAN,
            GammaFrontierRole.CONTROL,
            {"requests": _launches(bad_resource=True)},
            "abstained",
            ("resource_profile_not_allowed",),
            "unbounded resource profile is rejected",
        ),
        _record(
            "gamma-snapshot-positive",
            GammaFrontierOperation.SHAREABLE_SNAPSHOT,
            GammaFrontierRole.POSITIVE,
            _snapshot(),
            "verified",
            (),
            "valid HMAC envelope verifies",
        ),
        _record(
            "gamma-snapshot-tampered",
            GammaFrontierOperation.SHAREABLE_SNAPSHOT,
            GammaFrontierRole.CONTROL,
            _snapshot(tampered=True),
            "blocked",
            ("snapshot_signature_invalid",),
            "wrong secret blocks verification",
        ),
        _record(
            "gamma-snapshot-expired",
            GammaFrontierOperation.SHAREABLE_SNAPSHOT,
            GammaFrontierRole.CONTROL,
            _snapshot(expired=True),
            "expired",
            ("snapshot_expired",),
            "expired envelope remains visible",
        ),
        _record(
            "gamma-snapshot-foreign",
            GammaFrontierOperation.SHAREABLE_SNAPSHOT,
            GammaFrontierRole.CONTROL,
            _snapshot(GAMMA_FRONTIER_OTHER_CONTEXT_KEY),
            "blocked",
            ("snapshot_context_mismatch",),
            "foreign context is blocked before sharing",
        ),
        _record(
            "gamma-collab-positive",
            GammaFrontierOperation.COLLABORATION_ACCESS,
            GammaFrontierRole.POSITIVE,
            _collaboration(),
            "allowed",
            (),
            "reviewer access is allowed by the explicit matrix",
        ),
        _record(
            "gamma-collab-foreign",
            GammaFrontierOperation.COLLABORATION_ACCESS,
            GammaFrontierRole.CONTROL,
            _collaboration(foreign=True),
            "out_of_domain",
            ("context_mismatch",),
            "foreign request is outside the workspace context",
        ),
        _record(
            "gamma-collab-inactive",
            GammaFrontierOperation.COLLABORATION_ACCESS,
            GammaFrontierRole.CONTROL,
            _collaboration(inactive=True),
            "denied",
            ("inactive_member",),
            "inactive member is denied",
        ),
        _record(
            "gamma-collab-unknown",
            GammaFrontierOperation.COLLABORATION_ACCESS,
            GammaFrontierRole.CONTROL,
            _collaboration(unknown=True),
            "denied",
            ("unknown_member",),
            "unknown member is denied by default",
        ),
    )
    sources = (
        _source(
            "workspace-public",
            "Research workspace design receipt",
            "https://example.org/glio/workspace",
            "aggregate design reference",
        ),
        _source(
            "planning-public",
            "Validation planning receipt",
            "https://example.org/glio/planning",
            "public planning vocabulary",
        ),
        _source(
            "runtime-public",
            "Runtime reproducibility receipt",
            "https://example.org/glio/runtime",
            "bounded runtime reference",
        ),
        _source(
            "sharing-public",
            "Snapshot sharing receipt",
            "https://example.org/glio/sharing",
            "research-use sharing reference",
        ),
        _source(
            "policy-public",
            "Collaboration policy receipt",
            "https://example.org/glio/policy",
            "explicit policy reference",
        ),
    )
    body = {
        "fixture_id": "workspace-gamma-frontier-c09-c12",
        "fixture_version": GAMMA_FRONTIER_FIXTURE_VERSION,
        "context_key": GAMMA_FRONTIER_CONTEXT_KEY,
        "evidence_boundary": GAMMA_FRONTIER_EVIDENCE_BOUNDARY,
        "sources": sources,
        "records": records,
    }
    return GammaFrontierFixture(**body, content_address=content_hash(body))


def build_gamma_frontier_catalog(
    fixture: GammaFrontierFixture | None = None,
) -> GammaFrontierCatalog:
    """Build a stable index used by API and release consumers."""

    fixture = fixture or default_gamma_frontier_fixture()
    body = {
        "fixture_id": fixture.fixture_id,
        "record_ids": tuple(item.record_id for item in fixture.records),
        "source_ids": tuple(item.source_id for item in fixture.sources),
        "operations": tuple(sorted({item.operation for item in fixture.records}, key=str)),
        "context_key": fixture.context_key,
    }
    return GammaFrontierCatalog(**body, content_address=content_hash(body))


def audit_gamma_frontier_data(
    fixture: GammaFrontierFixture | None = None,
) -> GammaFrontierDataAudit:
    """Check counts, HTTPS receipts, operation coverage, and context boundaries."""

    fixture = fixture or default_gamma_frontier_fixture()
    checks: list[GammaFrontierDataCheck] = []

    def check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> None:
        body = {
            "check_id": check_id,
            "passed": passed,
            "observed": observed,
            "required": required,
            "detail": detail,
        }
        checks.append(GammaFrontierDataCheck(**body, content_address=content_hash(body)))

    check(
        "source-count",
        len(fixture.sources) == GAMMA_FRONTIER_SOURCE_COUNT,
        len(fixture.sources),
        GAMMA_FRONTIER_SOURCE_COUNT,
        "five public source receipts are required",
    )
    check(
        "record-count",
        len(fixture.records) == GAMMA_FRONTIER_POSITIVE_COUNT + GAMMA_FRONTIER_CONTROL_COUNT,
        len(fixture.records),
        16,
        "four positives and twelve controls are required",
    )
    check(
        "positive-count",
        len(fixture.positive_records) == GAMMA_FRONTIER_POSITIVE_COUNT,
        len(fixture.positive_records),
        GAMMA_FRONTIER_POSITIVE_COUNT,
        "one accepted path per operation",
    )
    check(
        "control-count",
        len(fixture.control_records) == GAMMA_FRONTIER_CONTROL_COUNT,
        len(fixture.control_records),
        GAMMA_FRONTIER_CONTROL_COUNT,
        "three controls per operation",
    )
    check(
        "https-only",
        all(item.uri.startswith("https://") for item in fixture.sources),
        tuple(item.uri for item in fixture.sources),
        "all HTTPS",
        "source receipts use HTTPS",
    )
    check(
        "operation-coverage",
        {item.operation.value for item in fixture.records}
        == {item.value for item in GammaFrontierOperation},
        tuple(sorted({item.operation.value for item in fixture.records})),
        tuple(item.value for item in GammaFrontierOperation),
        "every C09-C12 surface has records",
    )
    check(
        "context-boundary",
        fixture.context_key == GAMMA_FRONTIER_CONTEXT_KEY,
        fixture.context_key,
        GAMMA_FRONTIER_CONTEXT_KEY,
        "fixture has one declared exact context",
    )
    failed = tuple(item.check_id for item in checks if not item.passed)
    body = {
        "fixture_id": fixture.fixture_id,
        "checks": tuple(checks),
        "accepted": not failed,
        "failed_check_ids": failed,
    }
    return GammaFrontierDataAudit(**body, content_address=content_hash(body))


def load_gamma_frontier_fixture(path: str | Path | None = None) -> GammaFrontierFixture:
    """Load a canonical JSON fixture, or return the built-in public fixture."""

    if path is None:
        return default_gamma_frontier_fixture()
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    sources = tuple(GammaFrontierSourceReceipt(**item) for item in payload["sources"])
    records = []
    for item in payload["records"]:
        record_body = dict(item)
        record_body["operation"] = GammaFrontierOperation(item["operation"])
        record_body["role"] = GammaFrontierRole(item["role"])
        record_body["source_ids"] = tuple(item["source_ids"])
        record_body["expected_issue_codes"] = tuple(item.get("expected_issue_codes", ()))
        records.append(GammaFrontierRecord(**record_body))
    body = {
        key: payload[key]
        for key in ("fixture_id", "fixture_version", "context_key", "evidence_boundary")
    }
    return GammaFrontierFixture(
        **body,
        sources=sources,
        records=tuple(records),
        content_address=str(
            payload.get(
                "content_address", content_hash({**body, "sources": sources, "records": records})
            )
        ),
    )


__all__ = [
    "GAMMA_FRONTIER_CONTEXT_KEY",
    "GAMMA_FRONTIER_CONTROL_COUNT",
    "GAMMA_FRONTIER_EVIDENCE_BOUNDARY",
    "GAMMA_FRONTIER_FIXTURE_VERSION",
    "GAMMA_FRONTIER_OTHER_CONTEXT_KEY",
    "GAMMA_FRONTIER_POSITIVE_COUNT",
    "GAMMA_FRONTIER_SOURCE_COUNT",
    "GammaFrontierCatalog",
    "GammaFrontierDataAudit",
    "GammaFrontierDataCheck",
    "GammaFrontierFixture",
    "GammaFrontierOperation",
    "GammaFrontierRecord",
    "GammaFrontierRole",
    "GammaFrontierSourceReceipt",
    "audit_gamma_frontier_data",
    "build_gamma_frontier_catalog",
    "default_gamma_frontier_fixture",
    "load_gamma_frontier_fixture",
]
