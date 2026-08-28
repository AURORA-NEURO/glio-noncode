"""Run the release-registry federation gate review on a persisted gate.

The example is intentionally input-only: it never fabricates a registry,
federation, gate, finding, or scientific result. Point it at a current-format
gate package produced by the upstream release-registry federation gate.

Example:

    python examples/release_registry_federation_gate_review_demo.py \
        --gate ./downloaded/federation-gate \
        --output ./demo-output \
        --format markdown

The output directory receives separate queue, ledger, and optional diff
packages. The source gate directory is never written.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from glio_noncode import assurance_history_series_release_registry_federation_gate_review as review
from glio_noncode.errors import GlioError


@dataclass(frozen=True)
class DemoResult:
    """Path-free summary returned by the demo runner."""

    gate_address: str
    queue_address: str
    ledger_address: str
    queue_state: str
    ledger_state: str
    queue_release_ready: bool
    ledger_release_ready: bool
    item_count: int
    failed_count: int
    entry_count: int
    diff_address: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_address": self.gate_address,
            "queue_address": self.queue_address,
            "ledger_address": self.ledger_address,
            "queue_state": self.queue_state,
            "ledger_state": self.ledger_state,
            "queue_release_ready": self.queue_release_ready,
            "ledger_release_ready": self.ledger_release_ready,
            "item_count": self.item_count,
            "failed_count": self.failed_count,
            "entry_count": self.entry_count,
            "diff_address": self.diff_address,
        }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Demonstrate release-registry federation gate review on real persisted data"
    )
    parser.add_argument(
        "--gate",
        type=Path,
        required=True,
        help="current-format persisted federation assurance-gate directory",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="empty or explicitly replaceable output directory",
    )
    parser.add_argument("--queue-id", default="queue:demo")
    parser.add_argument("--ledger-id", default="ledger:demo")
    parser.add_argument("--diff-id", default="diff:demo")
    parser.add_argument(
        "--append-action",
        choices=tuple(review.ReviewAction),
        default=None,
        help="optional action to append to one failed queue item",
    )
    parser.add_argument("--item-id", default=None)
    parser.add_argument("--item-address", default=None)
    parser.add_argument("--rationale", default=None)
    parser.add_argument("--evidence-address", default=review.NO_EVIDENCE)
    parser.add_argument("--baseline-ledger", type=Path, default=None)
    parser.add_argument(
        "--format",
        choices=("json", "csv", "markdown", "summary"),
        default="summary",
        help="render the final demo result",
    )
    parser.add_argument("--allow-existing", action="store_true")
    return parser


def _ensure_directory(path: Path) -> None:
    if path.exists() and not path.is_dir():
        raise ValueError(f"output path is not a directory: {path}")


def _failed_item(
    queue: review.FederationReviewQueue,
    item_id: str | None,
) -> review.FederationReviewItem:
    failed = tuple(item for item in queue.items if not item.passed)
    if item_id is not None:
        matches = tuple(item for item in failed if item.item_id == item_id)
        if len(matches) != 1:
            raise ValueError("--item-id must identify exactly one failed queue item")
        return matches[0]
    if len(failed) != 1:
        raise ValueError("--item-id is required when the source gate has zero or multiple failures")
    return failed[0]


def _render_review(value: review.FederationReviewBundle, output_format: str) -> str:
    if output_format == "csv":
        return review.review_csv(value)
    if output_format == "markdown":
        return review.render_review_markdown(value)
    if output_format == "json":
        return review.review_json(value)
    return json.dumps(value.summary(), indent=2, sort_keys=True) + "\n"


def _render_ledger(value: review.FederationReviewDecisionLedger, output_format: str) -> str:
    if output_format == "csv":
        return review.decision_ledger_csv(value)
    if output_format == "markdown":
        return review.render_decision_ledger_markdown(value)
    if output_format == "json":
        return review.decision_ledger_json(value)
    return json.dumps(value.summary(), indent=2, sort_keys=True) + "\n"


def _render_diff(value: review.FederationReviewDecisionDiff, output_format: str) -> str:
    if output_format == "csv":
        return review.diff_csv(value)
    if output_format == "markdown":
        return review.render_diff_markdown(value)
    if output_format == "json":
        return review.diff_json(value)
    return json.dumps(value.summary(), indent=2, sort_keys=True) + "\n"


def run_demo(
    gate_directory: Path,
    output_directory: Path,
    *,
    queue_id: str,
    ledger_id: str,
    diff_id: str,
    append_action: str | None = None,
    item_id: str | None = None,
    item_address: str | None = None,
    rationale: str | None = None,
    evidence_address: str = review.NO_EVIDENCE,
    baseline_ledger_directory: Path | None = None,
    overwrite: bool = False,
) -> tuple[
    DemoResult,
    review.FederationReviewBundle,
    review.FederationReviewDecisionLedger,
    review.FederationReviewDecisionDiff | None,
]:
    """Build a queue, ledger, optional append, and optional diff from a gate."""

    if not gate_directory.is_dir():
        raise ValueError(f"gate directory does not exist: {gate_directory}")
    _ensure_directory(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    gate = review.gate_model.load_federation_assurance_gate(gate_directory)
    review.verify_review_against_gate(
        review.build_review_from_gate_directory(gate_directory, queue_id=queue_id),
        gate,
    )
    bundle = review.build_review(gate, queue_id=queue_id)
    queue_directory = output_directory / "review"
    review.write_review(bundle, queue_directory, overwrite=overwrite)
    loaded_bundle = review.load_review(queue_directory)
    ledger = review.build_decision_ledger(loaded_bundle, ledger_id=ledger_id)
    if append_action is not None:
        selected = _failed_item(ledger, item_id)
        if rationale is None:
            raise ValueError("--rationale is required with --append-action")
        ledger = review.append_decision(
            ledger,
            item_id=selected.item_id if item_id is None else item_id,
            item_address=item_address,
            action=append_action,
            rationale=rationale,
            evidence_address=evidence_address,
            expected_head_address=ledger.head_address,
        )
    ledger_directory = output_directory / "ledger"
    review.write_decision_ledger(ledger, ledger_directory, overwrite=overwrite)
    loaded_ledger = review.load_decision_ledger(ledger_directory)
    diff: review.FederationReviewDecisionDiff | None = None
    if baseline_ledger_directory is not None:
        baseline = review.load_decision_ledger(baseline_ledger_directory)
        diff = review.build_decision_diff(baseline, loaded_ledger, diff_id=diff_id)
        review.write_decision_diff(diff, output_directory / "diff", overwrite=overwrite)
    result = DemoResult(
        gate_address=gate.gate.content_address,
        queue_address=loaded_bundle.queue.content_address,
        ledger_address=loaded_ledger.content_address,
        queue_state=loaded_bundle.queue.state,
        ledger_state=loaded_ledger.state,
        queue_release_ready=loaded_bundle.queue.release_ready,
        ledger_release_ready=loaded_ledger.release_ready,
        item_count=loaded_bundle.queue.item_count,
        failed_count=loaded_bundle.queue.failed_count,
        entry_count=loaded_ledger.entry_count,
        diff_address=None if diff is None else diff.content_address,
    )
    return result, loaded_bundle, loaded_ledger, diff


def _render_final(
    result: DemoResult,
    bundle: review.FederationReviewBundle,
    ledger: review.FederationReviewDecisionLedger,
    diff: review.FederationReviewDecisionDiff | None,
    output_format: str,
) -> str:
    if output_format == "summary":
        return json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n"
    if diff is not None:
        return _render_diff(diff, output_format)
    if output_format == "json":
        payload = {"review": bundle.to_dict(), "ledger": ledger.to_dict()}
        return json.dumps(payload, sort_keys=True) + "\n"
    if output_format == "csv":
        return review.review_csv(bundle) + "\n" + review.decision_ledger_csv(ledger)
    return _render_review(bundle, output_format) + "\n" + _render_ledger(ledger, output_format)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result, bundle, ledger, diff = run_demo(
            args.gate,
            args.output,
            queue_id=args.queue_id,
            ledger_id=args.ledger_id,
            diff_id=args.diff_id,
            append_action=args.append_action,
            item_id=args.item_id,
            item_address=args.item_address,
            rationale=args.rationale,
            evidence_address=args.evidence_address,
            baseline_ledger_directory=args.baseline_ledger,
            overwrite=args.allow_existing,
        )
        print(_render_final(result, bundle, ledger, diff, args.format), end="")
        return 0 if ledger.release_ready else 2
    except (GlioError, OSError, ValueError) as exc:
        print(f"demo failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
