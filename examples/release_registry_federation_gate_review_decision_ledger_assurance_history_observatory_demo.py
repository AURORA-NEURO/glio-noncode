"""Demonstrate a cross-run assurance observatory on downloaded data.

The inputs are current-format persisted assurance-history packages.  Each
package can have been produced from a different downloaded release-registry
run.  The demo keeps those histories source-scoped, computes a deterministic
aggregate, persists the exact observatory package, and optionally compares it
with a previously observed package.

Example:

    python examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_demo.py \
        --history ./downloaded/run-one/history \
        --history ./downloaded/run-two/history \
        --destination ./demo-output/observatory \
        --format markdown

Reports contain public addresses and outcome counters only.  Input paths and
local machine metadata are never copied into the public package.
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

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory as observatory
from glio_noncode.errors import GlioError


@dataclass(frozen=True)
class DemoResult:
    """Path-free summary of an observatory run."""

    source_count: int
    observatory_id: str
    observatory_address: str
    state: str
    release_ready: bool
    accepted: bool
    member_count: int
    entry_count: int
    ready_member_count: int
    held_member_count: int
    blocked_member_count: int
    empty_member_count: int
    mixed_member_count: int
    improved_count: int
    regressed_count: int
    diff_address: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_count": self.source_count,
            "observatory_id": self.observatory_id,
            "observatory_address": self.observatory_address,
            "state": self.state,
            "release_ready": self.release_ready,
            "accepted": self.accepted,
            "member_count": self.member_count,
            "entry_count": self.entry_count,
            "ready_member_count": self.ready_member_count,
            "held_member_count": self.held_member_count,
            "blocked_member_count": self.blocked_member_count,
            "empty_member_count": self.empty_member_count,
            "mixed_member_count": self.mixed_member_count,
            "improved_count": self.improved_count,
            "regressed_count": self.regressed_count,
            "diff_address": self.diff_address,
        }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="demonstrate an assurance-history observatory on downloaded data")
    parser.add_argument("--history", action="append", type=Path, required=True, metavar="DIRECTORY", help="current-format persisted assurance history; repeatable")
    parser.add_argument("--member-id", action="append", default=None, help="stable public member identity aligned with --history")
    parser.add_argument("--observatory-id", default=observatory.DEFAULT_OBSERVATORY_ID)
    parser.add_argument("--destination", type=Path, required=True, help="exact five-file observatory package destination")
    parser.add_argument("--baseline", type=Path, default=None, help="optional persisted observatory for a member-level diff")
    parser.add_argument("--diff-destination", type=Path, default=None, help="optional exact two-file diff destination")
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


def _unique_inputs(values: Sequence[Path]) -> tuple[Path, ...]:
    if not values:
        raise ValueError("at least one history directory is required")
    selected: list[Path] = []
    seen: set[Path] = set()
    for value in values:
        directory = _regular_directory(value, "history directory")
        resolved = directory.resolve()
        if resolved in seen:
            raise ValueError("history directories must be unique")
        seen.add(resolved)
        selected.append(directory)
    return tuple(selected)


def _summary(value: observatory.AssuranceHistoryObservatory, source_count: int, diff: observatory.ObservatoryDiff | None) -> DemoResult:
    return DemoResult(
        source_count=source_count,
        observatory_id=value.observatory_id,
        observatory_address=value.content_address,
        state=value.state,
        release_ready=value.release_ready,
        accepted=value.accepted,
        member_count=value.member_count,
        entry_count=value.entry_count,
        ready_member_count=value.ready_member_count,
        held_member_count=value.held_member_count,
        blocked_member_count=value.blocked_member_count,
        empty_member_count=value.empty_member_count,
        mixed_member_count=value.mixed_member_count,
        improved_count=0 if diff is None else diff.improved_count,
        regressed_count=0 if diff is None else diff.regressed_count,
        diff_address=None if diff is None else diff.content_address,
    )


def _render(value: observatory.AssuranceHistoryObservatory, result: DemoResult, diff: observatory.ObservatoryDiff | None, output_format: str) -> str:
    if output_format == "summary":
        return json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n"
    if output_format == "csv":
        return observatory.observatory_csv(value)
    if output_format == "markdown":
        reports = [observatory.render_observatory_markdown(value)]
        if diff is not None:
            reports.append(observatory.render_diff_markdown(diff))
        return "\n".join(reports)
    payload: dict[str, Any] = {"observatory": value.to_dict(), "verification": observatory.build_verification(value).to_dict(), "metrics": observatory.metrics_document(value), "result": result.to_dict()}
    if diff is not None:
        payload["diff"] = diff.to_dict()
    return json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"


def _write_report(report: str, destination: Path | None) -> None:
    if destination is None:
        sys.stdout.write(report)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(report, encoding="utf-8")


def run_demo(*, histories: Sequence[Path], member_ids: Sequence[str] = (), observatory_id: str = observatory.DEFAULT_OBSERVATORY_ID, destination: Path, baseline: Path | None = None, diff_destination: Path | None = None, overwrite: bool = False) -> tuple[DemoResult, observatory.AssuranceHistoryObservatory, observatory.ObservatoryDiff | None]:
    """Load, aggregate, verify, and persist current-format history packages."""

    selected = _unique_inputs(histories)
    if member_ids and len(member_ids) != len(selected):
        raise ValueError("member ID count must equal history directory count")
    value = observatory.build_observatory_from_directories(selected, observatory_id=observatory_id, member_ids=tuple(member_ids))
    destination.parent.mkdir(parents=True, exist_ok=True)
    observatory.write_observatory(value, destination, overwrite=overwrite)
    loaded = observatory.load_observatory(destination)
    diff = None
    if baseline is not None:
        diff = observatory.build_diff(observatory.load_observatory(_regular_directory(baseline, "baseline observatory")), loaded)
        target = diff_destination or destination.parent / "diff"
        target.parent.mkdir(parents=True, exist_ok=True)
        observatory.write_diff(diff, target, overwrite=overwrite)
    return _summary(loaded, len(selected), diff), loaded, diff


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result, value, diff = run_demo(histories=tuple(args.history or ()), member_ids=tuple(args.member_id or ()), observatory_id=args.observatory_id, destination=args.destination, baseline=args.baseline, diff_destination=args.diff_destination, overwrite=args.allow_existing)
        _write_report(_render(value, result, diff, args.format), args.report)
        return 0 if result.release_ready else 2
    except (GlioError, OSError, ValueError) as error:
        _write_report(json.dumps({"error": str(error)}, sort_keys=True) + "\n", None)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
