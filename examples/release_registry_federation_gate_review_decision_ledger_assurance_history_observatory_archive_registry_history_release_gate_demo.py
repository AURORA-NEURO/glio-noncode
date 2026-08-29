"""Demonstrate policy evaluation over a persisted registry history.

Example::

    python examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate_demo.py \
        --input ./review-output/history --format markdown
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate as gate
from glio_noncode.errors import GlioError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="demonstrate a policy-governed registry history release gate")
    parser.add_argument("--input", required=True, type=Path, help="exact four-file registry history directory")
    parser.add_argument("--policy-id", default=gate.DEFAULT_POLICY_ID)
    parser.add_argument("--minimum-snapshots", type=int, default=gate.DEFAULT_MINIMUM_SNAPSHOTS)
    parser.add_argument("--require-audit-complete", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--require-all-snapshots-accepted", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--require-final-release-ready", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--allowed-transition-state", action="append", choices=gate.history_model.STATES, default=None)
    parser.add_argument("--max-removed-items-per-transition", type=int, default=gate.DEFAULT_MAX_REMOVED_ITEMS)
    parser.add_argument("--max-changed-items-per-transition", type=int, default=gate.DEFAULT_MAX_CHANGED_ITEMS)
    parser.add_argument("--max-regressed-transitions", type=int, default=gate.DEFAULT_MAX_REGRESSED_TRANSITIONS)
    parser.add_argument("--max-mixed-transitions", type=int, default=gate.DEFAULT_MAX_MIXED_TRANSITIONS)
    parser.add_argument("--format", choices=("json", "csv", "markdown", "summary"), default="summary")
    return parser


def _render(value: gate.RegistryHistoryReleaseGate, output_format: str) -> str:
    if output_format == "json":
        return gate.gate_json(value)
    if output_format == "csv":
        return gate.gate_csv(value)
    if output_format == "markdown":
        return gate.render_gate_markdown(value)
    return json.dumps(value.summary(), indent=2, sort_keys=True) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        allowed_states = tuple(args.allowed_transition_state) if args.allowed_transition_state else gate.DEFAULT_ALLOWED_TRANSITION_STATES
        policy = gate.RegistryHistoryReleasePolicy(
            policy_id=args.policy_id,
            minimum_snapshots=args.minimum_snapshots,
            require_audit_complete=args.require_audit_complete,
            require_all_snapshots_accepted=args.require_all_snapshots_accepted,
            require_final_release_ready=args.require_final_release_ready,
            allowed_transition_states=allowed_states,
            max_removed_items_per_transition=args.max_removed_items_per_transition,
            max_changed_items_per_transition=args.max_changed_items_per_transition,
            max_regressed_transitions=args.max_regressed_transitions,
            max_mixed_transitions=args.max_mixed_transitions,
        )
        value = gate.evaluate_history_from_directory(args.input, policy)
        sys.stdout.write(_render(value, args.format))
        return 0 if value.accepted else 2
    except (GlioError, OSError, ValueError) as error:
        sys.stdout.write(json.dumps({"error": str(error)}, sort_keys=True) + "\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
