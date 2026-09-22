"""Verify portable release-evidence ZIPs from the command line."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import downloaded_data_quality_d494_release_evidence_archive as archive_model
from . import downloaded_data_quality_d494_release_evidence_archive_audit as audit_model
from ._safe_persistence import _validate_parent, atomic_write_text
from .errors import ValidationError

EXIT_READY = 0
EXIT_INVALID = 2
EXIT_BLOCKED = 3
VERIFICATION_SCOPE = "integrity and linked-evidence replay; publisher identity is not authenticated"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="glio-noncode verify-release-evidence",
        description=(
            "Validate a canonical release-evidence ZIP, replay its independent audit, "
            "and report readiness without extracting payload files."
        ),
    )
    parser.add_argument("archive", type=Path, help="portable release-evidence ZIP to verify")
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        help="verification report format (default: json)",
    )
    parser.add_argument(
        "--output",
        default="-",
        help="report destination, or - for standard output (default: -)",
    )
    return parser


def _empty_audit() -> dict[str, Any]:
    return {
        "completed": False,
        "accepted": False,
        "check_count": 0,
        "passed_count": 0,
        "failed_count": 0,
        "content_address": None,
        "failed_check_ids": [],
        "checks": [],
    }


def _invalid_report(path: Path, *, code: str, message: str) -> dict[str, Any]:
    return {
        "schema": "glio-noncode.release-evidence-verification.v1",
        "archive_name": path.name or "<input>",
        "archive_valid": False,
        "status": "invalid",
        "verification_scope": VERIFICATION_SCOPE,
        "bundle_id": None,
        "diff_id": None,
        "archive_address": None,
        "manifest_address": None,
        "manifest_state": None,
        "release_ready": False,
        "file_count": 0,
        "payload_bytes": 0,
        "blocked_reasons": ["invalid_archive"],
        "audit": _empty_audit(),
        "files": [],
        "error": {"code": code, "message": message},
    }


def verify_archive(path: str | Path) -> tuple[dict[str, Any], int]:
    """Load, replay, and audit one bounded canonical archive."""

    source = Path(path)
    try:
        archive = archive_model.load_archive(source)
        audit = audit_model.audit_archive(archive)
    except OSError:
        return (
            _invalid_report(
                source,
                code="archive_read_error",
                message="The input archive could not be read as a regular file.",
            ),
            EXIT_INVALID,
        )
    except (ValueError, ValidationError):
        return (
            _invalid_report(
                source,
                code="invalid_archive",
                message="The input is not a canonical release-evidence archive.",
            ),
            EXIT_INVALID,
        )

    manifest = archive.manifest
    blocked_reasons: list[str] = []
    if not manifest.release_ready or manifest.state != "ready":
        blocked_reasons.append("manifest_not_release_ready")
    if not audit.accepted:
        blocked_reasons.append("archive_audit_failed")

    status = "ready" if not blocked_reasons else "blocked"
    report = {
        "schema": "glio-noncode.release-evidence-verification.v1",
        "archive_name": source.name or "<input>",
        "archive_valid": True,
        "status": status,
        "verification_scope": VERIFICATION_SCOPE,
        "bundle_id": manifest.bundle_id,
        "diff_id": manifest.diff_id,
        "archive_address": archive.content_address,
        "manifest_address": manifest.content_address,
        "manifest_state": manifest.state,
        "release_ready": manifest.release_ready,
        "file_count": manifest.file_count,
        "payload_bytes": manifest.total_size,
        "blocked_reasons": blocked_reasons,
        "audit": {
            "completed": True,
            "accepted": audit.accepted,
            "check_count": audit.check_count,
            "passed_count": audit.passed_count,
            "failed_count": audit.failed_count,
            "content_address": audit.content_address,
            "failed_check_ids": [item.check_id for item in audit.checks if not item.passed],
            "checks": [
                {
                    "ordinal": item.ordinal,
                    "check_id": item.check_id,
                    "passed": item.passed,
                    "detail": item.detail,
                }
                for item in audit.checks
            ],
        },
        "files": [
            {
                "path": item.path,
                "media_type": item.media_type,
                "size": item.size,
                "sha256": item.sha256,
                "content_address": item.content_address,
            }
            for item in manifest.files
        ],
        "error": None,
    }
    return report, EXIT_READY if status == "ready" else EXIT_BLOCKED


def _markdown_cell(value: object) -> str:
    text = str(value).replace("\\", "\\\\").replace("|", "\\|")
    return text.replace("\r", " ").replace("\n", " ").replace("`", "\\`")


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Release-evidence verification",
        "",
        f"- Status: **{_markdown_cell(report['status'])}**",
        f"- Archive valid: `{str(report['archive_valid']).lower()}`",
        f"- Archive: `{_markdown_cell(report['archive_name'])}`",
        f"- Bundle: `{_markdown_cell(report['bundle_id'] or '—')}`",
        f"- Comparison: `{_markdown_cell(report['diff_id'] or '—')}`",
        f"- Release ready: `{str(report['release_ready']).lower()}`",
        f"- Payload: {report['file_count']} files, {report['payload_bytes']} bytes",
        f"- Archive address: `{_markdown_cell(report['archive_address'] or '—')}`",
        "",
    ]
    error = report["error"]
    if error is not None:
        detail = _markdown_cell(error["message"])
        lines.extend((f"- Error: `{_markdown_cell(error['code'])}` — {detail}", ""))
    reasons = report["blocked_reasons"]
    if reasons:
        lines.extend(("## Blockers", "", *[f"- `{_markdown_cell(item)}`" for item in reasons], ""))

    audit = report["audit"]
    lines.extend(
        (
            "## Independent audit",
            "",
            f"- Accepted: `{str(audit['accepted']).lower()}`",
            f"- Checks: {audit['passed_count']}/{audit['check_count']}",
            "",
            "| Check | Passed | Detail |",
            "| --- | --- | --- |",
        )
    )
    lines.extend(
        (
            f"| {_markdown_cell(item['check_id'])} | {str(item['passed']).lower()} | "
            f"{_markdown_cell(item['detail'])} |"
        )
        for item in audit["checks"]
    )
    if report["files"]:
        lines.extend(
            (
                "",
                "## Allowlisted members",
                "",
                "| Path | Bytes | SHA-256 |",
                "| --- | ---: | --- |",
            )
        )
        lines.extend(
            f"| `{_markdown_cell(item['path'])}` | {item['size']} | `{item['sha256']}` |"
            for item in report["files"]
        )
    lines.extend(
        (
            "",
            (
                "This verifies archive integrity and linked evidence. It does not establish "
                "publisher identity or provide a digital signature."
            ),
            "",
        )
    )
    return "\n".join(lines)


def _write_report(report: dict[str, Any], output_format: str, destination: str) -> None:
    if output_format == "json":
        rendered = (
            json.dumps(
                report,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        )
    else:
        rendered = _render_markdown(report)

    if destination == "-":
        sys.stdout.write(rendered)
        return

    output_path = Path(destination)
    _validate_parent(output_path.parent, "CLI output")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(output_path, rendered, field="CLI output")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.output != "-":
        try:
            if args.archive.resolve(strict=False) == Path(args.output).resolve(strict=False):
                print("error: report output must not replace the input archive", file=sys.stderr)
                return EXIT_INVALID
        except OSError:
            print("error: report paths could not be resolved safely", file=sys.stderr)
            return EXIT_INVALID

    report, status = verify_archive(args.archive)
    try:
        _write_report(report, args.format, args.output)
    except (OSError, ValidationError) as error:
        code = getattr(error, "code", "output_error")
        print(f"error: verification report could not be written ({code})", file=sys.stderr)
        return EXIT_INVALID
    return status


__all__ = ["build_parser", "main", "verify_archive"]
