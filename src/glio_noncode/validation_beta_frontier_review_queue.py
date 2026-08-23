"""Review queue filters that keep partial and control paths visible."""

from typing import Any

from .validation_beta_frontier_governance import ValidationBetaFrontierReviewQueue, ValidationBetaFrontierReviewItem, build_validation_beta_frontier_review_queue


def filter_validation_beta_frontier_review_queue(queue: ValidationBetaFrontierReviewQueue, *, operation: str | None = None, minimum_priority: int = 1) -> tuple[ValidationBetaFrontierReviewItem, ...]:
    return tuple(item for item in queue.items if (operation is None or item.operation.value == operation) and item.priority >= minimum_priority)


def validation_beta_frontier_review_summary(queue: ValidationBetaFrontierReviewQueue) -> dict[str, Any]:
    return {"open_count": queue.open_count, "by_priority": {str(priority): sum(item.priority == priority for item in queue.items) for priority in sorted({item.priority for item in queue.items})}, "content_address": queue.content_address}


__all__ = ["ValidationBetaFrontierReviewItem", "ValidationBetaFrontierReviewQueue", "build_validation_beta_frontier_review_queue", "filter_validation_beta_frontier_review_queue", "validation_beta_frontier_review_summary"]
