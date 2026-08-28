"""Demonstrate longitudinal assurance history on persisted downloaded data.

The demo accepts one or more current-format decision-ledger packages produced
from downloaded release-registry evidence, or current-format assurance-gate
packages produced by the assurance layer. It recomputes assurance when given
ledgers, appends the verified gate snapshots to an immutable history, and can
compare that history with an earlier persisted history.

Example using decision ledgers:

    python examples/release_registry_federation_gate_review_decision_ledger_assurance_history_demo.py \
        --ledger ./downloaded/run-one/ledger \
        --ledger ./downloaded/run-two/ledger \
        --destination ./demo-output/history \
        --format markdown

The emitted report contains addresses and outcome fields only. Input paths,
local machine details, and non-public metadata are never copied into the
history or report.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from glio_noncode import assurance_history_series_release_registry_federation_gate_review as review
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance as assurance
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history as history
from glio_noncode.errors import GlioError


@dataclass(frozen=True)
class DemoResult:
    """Path-free result summary for a downloaded-data history run."""

    source_kind: str
    source_count: int
    history_id: str
    history_address: str
    head_address: str
    state: str
    release_ready: bool
    accepted: bool
    entry_count: int
    initial_count: int
    stable_count: int
    improved_count: int
    regressed_count: int
    changed_count: int
    diff_address: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_kind": self.source_kind,
            "source_count": self.source_count,
            "history_id": self.history_id,
            "history_address": self.history_address,
            "head_address": self.head_address,
            "state": self.state,
            "release_ready": self.release_ready,
            "accepted": self.accepted,
            "entry_count": self.entry_count,
            "initial_count": self.initial_count,
            "stable_count": self.stable_count,
            "improved_count": self.improved_count,
            "regressed_count": self.regressed_count,
            "changed_count": self.changed_count,
            "diff_address": self.diff_address,
        }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="demonstrate longitudinal assurance history on downloaded data"
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--ledger",
        action="append",
        type=Path,
        metavar="DIRECTORY",
        help="current-format persisted decision ledger; repeatable in chronological order",
    )
    source.add_argument(
        "--assurance-gate",
        action="append",
        type=Path,
        metavar="DIRECTORY",
        help="current-format persisted assurance gate; repeatable in chronological order",
    )
    parser.add_argument(
        "--snapshot-id",
        action="append",
        default=None,
        help="stable snapshot identity; repeatable and aligned with the input order",
    )
    parser.add_argument(
        "--history-id",
        default=history.DEFAULT_HISTORY_ID,
        help="public history identity used for address construction",
    )
    parser.add_argument(
        "--destination",
        type=Path,
        required=True,
        help="exact three-file history package destination",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=None,
        help="optional persisted history used to build a comparison diff",
    )
    parser.add_argument(
        "--diff-destination",
        type=Path,
        default=None,
        help="optional exact two-file diff destination; defaults below destination/diff",
    )
    parser.add_argument("--allow-existing", action="store_true")
    parser.add_argument("--format", choices=("json", "csv", "markdown", "summary"), default="summary")
    parser.add_argument("--report", type=Path, default=None, help="optional path for the path-free report")
    return parser


def _regular_directory(path: Path, field: str) -> Path:
    if not path.exists():
        raise ValueError(f"{field} does not exist")
    if path.is_symlink() or not path.is_dir():
        raise ValueError(f"{field} must be a regular directory")
    return path


def _unique_inputs(values: Sequence[Path], field: str) -> tuple[Path, ...]:
    if not values:
        raise ValueError(f"at least one {field} is required")
    result: list[Path] = []
    seen: set[Path] = set()
    for value in values:
        directory = _regular_directory(value, field)
        resolved = directory.resolve()
        if resolved in seen:
            raise ValueError(f"{field} contains a duplicate directory")
        seen.add(resolved)
        result.append(directory)
    return tuple(result)


def _load_gates(
    *,
    ledgers: Sequence[Path],
    assurance_gates: Sequence[Path],
) -> tuple[str, tuple[assurance.DecisionLedgerAssuranceGate, ...]]:
    if ledgers and assurance_gates:
        raise ValueError("ledger and assurance-gate inputs cannot be combined")
    if ledgers:
        selected = _unique_inputs(ledgers, "decision ledger directories")
        gates: list[assurance.DecisionLedgerAssuranceGate] = []
        for directory in selected:
            ledger = review.load_decision_ledger(directory)
            gate = assurance.build_assurance_gate(ledger)
            assurance.verify_assurance_gate_against_ledger(gate, ledger)
            gates.append(gate)
        return "decision-ledger", tuple(gates)
    selected = _unique_inputs(assurance_gates, "assurance-gate directories")
    return "assurance-gate", tuple(assurance.load_assurance_gate(directory) for directory in selected)


def _summary(value: history.AssuranceHistory, source_kind: str, source_count: int, diff: history.AssuranceHistoryDiff | None) -> DemoResult:
    summary = value.summary()
    return DemoResult(
        source_kind=source_kind,
        source_count=source_count,
        history_id=value.history_id,
        history_address=value.content_address,
        head_address=value.head_address,
        state=value.state,
        release_ready=value.release_ready,
        accepted=value.accepted,
        entry_count=value.entry_count,
        initial_count=summary["initial_count"],
        stable_count=summary["stable_count"],
        improved_count=summary["improved_count"],
        regressed_count=summary["regressed_count"],
        changed_count=summary["changed_count"],
        diff_address=None if diff is None else diff.content_address,
    )


def _render(value: history.AssuranceHistory, result: DemoResult, diff: history.AssuranceHistoryDiff | None, output_format: str) -> str:
    if output_format == "summary":
        return json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n"
    if output_format == "csv":
        return history.history_csv(value)
    if output_format == "markdown":
        report = [history.render_history_markdown(value)]
        if diff is not None:
            report.append(history.render_diff_markdown(diff))
        return "\n".join(report)
    payload: dict[str, Any] = {"history": value.to_dict(), "result": result.to_dict()}
    if diff is not None:
        payload["diff"] = diff.to_dict()
    return json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"


def _write_report(value: str, destination: Path | None) -> None:
    if destination is None:
        sys.stdout.write(value)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(value, encoding="utf-8")


def run_demo(
    *,
    ledgers: Sequence[Path] = (),
    assurance_gates: Sequence[Path] = (),
    snapshot_ids: Sequence[str] = (),
    history_id: str = history.DEFAULT_HISTORY_ID,
    destination: Path,
    baseline: Path | None = None,
    diff_destination: Path | None = None,
    overwrite: bool = False,
) -> tuple[DemoResult, history.AssuranceHistory, history.AssuranceHistoryDiff | None]:
    """Build and persist a history from persisted downloaded-data outputs."""

    source_kind, gates = _load_gates(ledgers=ledgers, assurance_gates=assurance_gates)
    value = history.build_history(gates, history_id=history_id, snapshot_ids=snapshot_ids)
    destination.parent.mkdir(parents=True, exist_ok=True)
    history.write_history(value, destination, overwrite=overwrite)
    loaded = history.load_history(destination)
    diff = None
    if baseline is not None:
        diff = history.build_diff(history.load_history(baseline), loaded)
        target = diff_destination or destination.parent / "diff"
        target.parent.mkdir(parents=True, exist_ok=True)
        history.write_diff(diff, target, overwrite=overwrite)
    return _summary(loaded, source_kind, len(gates), diff), loaded, diff


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result, value, diff = run_demo(
            ledgers=tuple(args.ledger or ()),
            assurance_gates=tuple(args.assurance_gate or ()),
            snapshot_ids=tuple(args.snapshot_id or ()),
            history_id=args.history_id,
            destination=args.destination,
            baseline=args.baseline,
            diff_destination=args.diff_destination,
            overwrite=args.allow_existing,
        )
        _write_report(_render(value, result, diff, args.format), args.report)
        return 0 if result.release_ready else 2
    except (GlioError, OSError, ValueError) as error:
        _write_report(json.dumps({"error": str(error)}, sort_keys=True) + "\n", None)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
