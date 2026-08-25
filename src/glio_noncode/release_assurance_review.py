"""Reviewer queue generated from whole-product release-assurance evidence."""

from __future__ import annotations

from .release_assurance_contracts import (
    ReleaseAssurancePlane,
    ReleaseAssuranceReviewItem,
    ReleaseAssuranceReviewQueue,
    ReleaseAssuranceRuntimeReport,
    ReleaseAssuranceState,
    check,
)
from .serialization import content_hash


def _item(
    review_id: str,
    priority: int,
    state: ReleaseAssuranceState,
    topic: str,
    reason: str,
    action: str,
    evidence_addresses: tuple[str, ...],
    accepted: bool,
) -> ReleaseAssuranceReviewItem:
    body = {
        "review_id": review_id,
        "priority": priority,
        "state": state,
        "topic": topic,
        "reason": reason,
        "action": action,
        "evidence_addresses": evidence_addresses,
        "accepted": accepted,
    }
    return ReleaseAssuranceReviewItem(
        **body,
        content_address=content_hash(body, prefix="release-assurance-review-item"),
    )


def build_release_assurance_review_queue(
    runtime: ReleaseAssuranceRuntimeReport,
) -> ReleaseAssuranceReviewQueue:
    """Prioritize blocked checks, blocked stages, controls, and release review."""

    items: list[ReleaseAssuranceReviewItem] = []
    for check_item in runtime.snapshot.checks:
        if not check_item.passed:
            items.append(_item(
                f"check:{check_item.check_id}",
                10,
                ReleaseAssuranceState.BLOCKED,
                check_item.check_id,
                check_item.detail,
                "repair or explain the failed cross-plane check",
                check_item.evidence_addresses,
                False,
            ))
    for stage in runtime.stages:
        if stage.state is ReleaseAssuranceState.BLOCKED:
            items.append(_item(
                f"stage:{stage.stage_id}",
                5,
                ReleaseAssuranceState.BLOCKED,
                stage.stage_id,
                stage.detail,
                "repair the blocked runtime stage and replay",
                (stage.input_address, stage.output_address),
                False,
            ))
    for failure in runtime.failures.cases:
        if not failure.passed:
            items.append(_item(
                f"control:{failure.case_id}",
                20,
                ReleaseAssuranceState.BLOCKED,
                failure.case_id,
                failure.mutation,
                "restore the expected fail-closed negative control",
                (failure.content_address,),
                False,
            ))
    if not items:
        items.append(_item(
            "release-decision",
            50,
            ReleaseAssuranceState.READY,
            runtime.snapshot.bundle_id,
            "all release-assurance planes and replay stages are accepted",
            "perform human release review and retain the checkpoint",
            (runtime.snapshot.content_address, runtime.content_address),
            runtime.accepted,
        ))
    items.sort(key=lambda item: (item.priority, item.review_id))
    accepted = runtime.accepted and all(item.accepted for item in items)
    body = {
        "bundle_id": runtime.snapshot.bundle_id,
        "run_id": runtime.run_id,
        "items": items,
        "accepted": accepted,
    }
    return ReleaseAssuranceReviewQueue(
        runtime.snapshot.bundle_id,
        runtime.run_id,
        tuple(items),
        accepted,
        content_hash(body, prefix="release-assurance-review-queue"),
    )


def audit_release_assurance_review_queue(
    queue: ReleaseAssuranceReviewQueue,
    runtime: ReleaseAssuranceRuntimeReport,
) -> tuple:
    """Audit reviewer ordering, evidence, and release-state consistency."""

    ids = tuple(item.review_id for item in queue.items)
    return (
        check("review:non-empty", "review", ReleaseAssurancePlane.RUNTIME,
              bool(ids), len(ids), ">0", "review queue retains a decision row"),
        check("review:identities", "review", ReleaseAssurancePlane.RUNTIME,
              len(ids) == len(set(ids)), len(ids), len(set(ids)), "review identifiers are unique"),
        check("review:ordering", "review", ReleaseAssurancePlane.RUNTIME,
              tuple((item.priority, item.review_id) for item in queue.items)
              == tuple(sorted((item.priority, item.review_id) for item in queue.items)),
              tuple(item.review_id for item in queue.items[:3]), "priority order", "reviews are sorted"),
        check("review:evidence", "review", ReleaseAssurancePlane.PUBLIC_BOUNDARY,
              all(item.evidence_addresses for item in queue.items),
              sum(bool(item.evidence_addresses) for item in queue.items), len(queue.items),
              "every review row retains evidence addresses"),
        check("review:bundle", "review", ReleaseAssurancePlane.RUNTIME,
              queue.bundle_id == runtime.snapshot.bundle_id, queue.bundle_id, runtime.snapshot.bundle_id,
              "review bundle matches runtime"),
        check("review:accepted", "review", ReleaseAssurancePlane.RUNTIME,
              queue.accepted == (runtime.accepted and all(item.accepted for item in queue.items)),
              queue.accepted, runtime.accepted, "queue acceptance follows runtime and review items"),
    )


__all__ = ["audit_release_assurance_review_queue", "build_release_assurance_review_queue"]
