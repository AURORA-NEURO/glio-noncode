"""Demonstrate registry construction from downloaded observatory archives.

The inputs are already verified single-file ZIP archives. The registry keeps
each archive content address, projects bounded observatory posture summaries,
recomputes aggregate metrics, persists an exact five-file package, and exposes
public entry queries.

Example::

    python examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_demo.py \
        --input observatory-one.zip --input observatory-two.zip \
        --destination ./review-output/registry --resource entries --format markdown
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry as registry
from glio_noncode.errors import GlioError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="demonstrate a verified observatory archive registry")
    parser.add_argument("--input", action="append", required=True, type=Path, help="downloaded observatory archive ZIP; repeat for each member")
    parser.add_argument("--entry-id", action="append", default=None)
    parser.add_argument("--registry-id", default=registry.DEFAULT_REGISTRY_ID)
    parser.add_argument("--verification-id", default=None)
    parser.add_argument("--destination", type=Path, default=None, help="optional exact five-file registry directory")
    parser.add_argument("--resource", choices=registry.RegistryQuery.RESOURCES, default="summary")
    parser.add_argument("--state", choices=tuple(registry.RegistryState), default=None)
    parser.add_argument("--accepted", action="store_true", default=None)
    parser.add_argument("--release-ready", action="store_true", default=None)
    parser.add_argument("--text", default=None)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=registry.DEFAULT_LIMIT)
    parser.add_argument("--format", choices=("summary", "json", "csv", "markdown"), default="summary")
    return parser


def run_demo(*, inputs: Sequence[Path], entry_ids: Sequence[str] | None = None, registry_id: str = registry.DEFAULT_REGISTRY_ID, verification_id: str | None = None, destination: Path | None = None, resource: str = "summary", state: str | None = None, accepted: bool | None = None, release_ready: bool | None = None, text: str | None = None, offset: int = 0, limit: int = registry.DEFAULT_LIMIT) -> tuple[registry.ObservatoryArchiveRegistry, registry.RegistryQueryResult]:
    """Build, optionally persist/reload, and query a public registry."""

    value = registry.build_registry_from_archive_files(tuple(inputs), entry_ids=entry_ids, registry_id=registry_id, verification_id=verification_id)
    if destination is not None:
        registry.write_registry(value, destination)
        value = registry.load_registry(destination)
    result = registry.query_registry(value, resource=resource, state=state, accepted=accepted, release_ready=release_ready, text=text, offset=offset, limit=limit)
    return value, result


def _render(value: registry.ObservatoryArchiveRegistry, result: registry.RegistryQueryResult, output_format: str) -> str:
    if output_format == "json":
        return registry.query_json(result)
    if output_format == "csv":
        return registry.query_csv(result)
    if output_format == "markdown":
        return registry.render_query_markdown(result)
    return json.dumps({"registry": value.summary(), "query": result.to_dict()}, indent=2, sort_keys=True) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        value, result = run_demo(inputs=args.input, entry_ids=args.entry_id, registry_id=args.registry_id, verification_id=args.verification_id, destination=args.destination, resource=args.resource, state=args.state, accepted=args.accepted, release_ready=args.release_ready, text=args.text, offset=args.offset, limit=args.limit)
        sys.stdout.write(_render(value, result, args.format))
        return 0
    except (GlioError, OSError, ValueError) as error:
        sys.stdout.write(json.dumps({"error": str(error)}, sort_keys=True) + "\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
