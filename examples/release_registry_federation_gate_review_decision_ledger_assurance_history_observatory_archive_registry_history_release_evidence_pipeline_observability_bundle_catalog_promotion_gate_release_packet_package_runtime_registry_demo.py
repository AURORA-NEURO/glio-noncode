"""Demonstrate the durable package runtime and registry on downloaded handoffs.

The input directories are ordinary verified observability bundle downloads. The
runtime rebuilds the catalog, diff, report, promotion gate, gate audit, release
packet, package audit, and bounded package query. With ``--package-destination``
it persists and reloads the exact five-file package. The optional registry then
indexes those package directories and can be persisted as a two-file release
set. Public output contains labels, counts, decisions, and content addresses;
local input paths are used only as private function arguments.
"""

from __future__ import annotations

# ruff: noqa: E501
import argparse
import json
from pathlib import Path
from typing import Any

from glio_noncode.assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry import (
    audit_registry,
    build_registry_from_directories,
    load_registry,
    query_registry,
    registry_csv,
    render_registry_markdown,
    write_registry,
)
from glio_noncode.assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry_diff import (
    audit_diff,
    build_diff as build_registry_diff,
    diff_csv,
    diff_json,
    render_diff_markdown,
)
from glio_noncode.assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_runtime import (
    render_runtime_markdown,
    run_package_runtime,
    runtime_csv,
    runtime_json,
)
def _pairs(labels: list[str], directories: list[str], parser: argparse.ArgumentParser, name: str) -> tuple[tuple[str, str], ...]:
    if not labels or len(labels) != len(directories):
        parser.error(f"{name} labels and directories must be supplied in equal non-zero counts")
    return tuple(zip(labels, directories, strict=True))


def _write_or_print(text: str, output: str | None) -> None:
    if output:
        destination = Path(output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding="utf-8")
    else:
        print(text, end="" if text.endswith("\n") else "\n")


def _registry_payload(value, resource: str) -> dict[str, Any]:
    page = query_registry(value, resource=resource, limit=32)
    assurance = audit_registry(value)
    return {
        "summary": value.summary(),
        "audit": {
            "state": assurance.state,
            "accepted": assurance.accepted,
            "check_count": assurance.check_count,
            "passed_count": assurance.passed_count,
            "failed_count": assurance.failed_count,
        },
        "query": page.to_dict(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--left-label", action="append", required=True)
    parser.add_argument("--left-directory", action="append", required=True)
    parser.add_argument("--right-label", action="append", required=True)
    parser.add_argument("--right-directory", action="append", required=True)
    parser.add_argument("--runtime-id", default="glio-noncode-downloaded-runtime")
    parser.add_argument("--package-id", default="glio-noncode-downloaded-package")
    parser.add_argument("--package-destination")
    parser.add_argument("--registry-package-directory", action="append")
    parser.add_argument("--registry-id", default="glio-noncode-downloaded-registry")
    parser.add_argument("--registry-destination")
    parser.add_argument("--left-registry-directory")
    parser.add_argument("--right-registry-directory")
    parser.add_argument("--resource", choices=("summary", "manifest", "gate", "audit", "packet", "actions", "evidence", "files"), default="summary")
    parser.add_argument("--registry-resource", choices=("summary", "entries", "accepted", "ready", "held", "blocked", "addresses"), default="entries")
    parser.add_argument("--source")
    parser.add_argument("--severity")
    parser.add_argument("--check-id")
    parser.add_argument("--text")
    parser.add_argument("--limit", type=int, default=16)
    parser.add_argument("--max-added", type=int)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--format", choices=("summary", "json", "csv", "markdown"), default="summary")
    parser.add_argument("--output")
    args = parser.parse_args()

    runtime = run_package_runtime(
        _pairs(args.left_label, args.left_directory, parser, "left"),
        _pairs(args.right_label, args.right_directory, parser, "right"),
        runtime_id=args.runtime_id,
        package_id=args.package_id,
        resource=args.resource,
        source=args.source,
        severity=args.severity,
        check_id=args.check_id,
        text=args.text,
        limit=args.limit,
        max_added=args.max_added,
        destination=args.package_destination,
        overwrite=args.overwrite,
    )

    package_directories = list(args.registry_package_directory or ())
    if args.package_destination and args.package_destination not in package_directories:
        package_directories.append(args.package_destination)
    registry = None
    registry_revision = None
    registry_revision_audit = None
    if package_directories:
        registry = build_registry_from_directories(tuple(package_directories), registry_id=args.registry_id)
        if args.registry_destination:
            write_registry(registry, args.registry_destination, overwrite=args.overwrite)
        if args.left_registry_directory and args.right_registry_directory:
            left_registry = load_registry(args.left_registry_directory)
            right_registry = load_registry(args.right_registry_directory)
            registry_revision = build_registry_diff(left_registry, right_registry, diff_id="glio-noncode-downloaded-registry-diff")
            registry_revision_audit = audit_diff(registry_revision)

    if args.format == "json":
        payload: dict[str, Any] = {"runtime": json.loads(runtime_json(runtime))}
        if registry is not None:
            payload["registry"] = _registry_payload(registry, args.registry_resource)
        if registry_revision is not None:
            payload["registry_diff"] = json.loads(diff_json(registry_revision))
            payload["registry_diff_audit"] = registry_revision_audit.to_dict()
        rendered = json.dumps(payload, indent=2, sort_keys=True)
    elif args.format == "csv":
        rendered = runtime_csv(runtime)
        if registry is not None:
            rendered += registry_csv(registry)
        if registry_revision is not None:
            rendered += diff_csv(registry_revision)
    elif args.format == "markdown":
        rendered = render_runtime_markdown(runtime)
        if registry is not None:
            rendered += "\n" + render_registry_markdown(registry)
        if registry_revision is not None:
            rendered += "\n" + render_diff_markdown(registry_revision)
    else:
        summary: dict[str, Any] = {"runtime": runtime.summary()}
        if registry is not None:
            summary["registry"] = _registry_payload(registry, args.registry_resource)
        if registry_revision is not None:
            summary["registry_diff"] = registry_revision.summary()
            summary["registry_diff_audit"] = {
                "state": registry_revision_audit.state,
                "accepted": registry_revision_audit.accepted,
                "checks": [registry_revision_audit.passed_count, registry_revision_audit.check_count],
            }
        rendered = json.dumps(summary, indent=2, sort_keys=True)
    _write_or_print(rendered, args.output)
    return 0 if runtime.package.packet.release_ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
