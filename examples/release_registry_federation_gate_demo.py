"""Run the release-registry federation gate against downloaded directories.

This example deliberately accepts only persisted release-registry packages.
It never manufactures a release record, imports an old repository, or embeds
the contents of a local download in the output.  The result is a portable
federation package plus an independently recomputed assurance gate package.

Typical use:

    python examples/release_registry_federation_gate_demo.py \
        --root ./downloaded-release-registries \
        --recursive \
        --output ./out/release-registry-gate \
        --format summary

The root may contain unrelated download notes.  Discovery admits only exact
registry directories that pass the release-registry loader.  Explicit
``--input`` paths are useful when a download has already been curated.
"""

# ruff: noqa: E501

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from glio_noncode import assurance_history_series_release_registry as registry
from glio_noncode import assurance_history_series_release_registry_federation as federation
from glio_noncode import assurance_history_series_release_registry_federation_gate as gate
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_json

DEFAULT_FEDERATION_ID = "glio-noncode-downloaded-release-registry-federation"
DEFAULT_GATE_ID = gate.DEFAULT_GATE_ID
DEFAULT_OUTPUT_DIRECTORY = Path("./glio-noncode-release-registry-gate")
DEFAULT_FORMAT = "summary"
FORMATS = ("json", "csv", "markdown", "summary")


@dataclass(frozen=True)
class DownloadedGateRun:
    """Addresses and paths produced by one downloaded-data demonstration."""

    root: Path | None
    registry_directories: tuple[Path, ...]
    federation_directory: Path
    gate_directory: Path
    federation: Any
    gate: Any

    def summary(self) -> dict[str, Any]:
        """Return only stable review fields; filesystem paths stay out of it."""

        return {
            "registry_count": len(self.registry_directories),
            "federation": self.federation.summary(),
            "assurance": self.gate.assurance.summary(),
            "gate": self.gate.gate.summary(),
            "artifacts": {
                "federation_files": list(federation.FILES),
                "gate_files": list(gate.FILES),
            },
        }


def _path(value: str | Path, field: str) -> Path:
    candidate = Path(value)
    if not candidate.exists():
        raise ValidationError(f"{field} does not exist")
    if candidate.is_symlink() or not candidate.is_dir():
        raise ValidationError(f"{field} must be a regular directory")
    return candidate


def _unique_directories(values: Sequence[str | Path], field: str) -> tuple[Path, ...]:
    output: list[Path] = []
    seen: set[Path] = set()
    for raw in values:
        candidate = _path(raw, field)
        resolved = candidate.resolve()
        if resolved in seen:
            raise ValidationError(f"{field} contains a duplicate directory")
        seen.add(resolved)
        output.append(candidate)
    return tuple(output)


def discover_downloaded_registries(root: str | Path, *, recursive: bool = False) -> tuple[Path, ...]:
    """Discover exact release-registry packages below a downloaded-data root."""

    root_path = _path(root, "download root")
    discovered = federation.discover_federation_registry_directories(root_path, recursive=recursive)
    if not discovered:
        raise ValidationError("download root contains no exact release-registry packages")
    return _unique_directories(discovered, "discovered registries")


def inspect_downloaded_registries(
    directories: Sequence[str | Path],
) -> tuple[dict[str, Any], ...]:
    """Load and summarize each candidate before aggregation."""

    selected = _unique_directories(directories, "registry directories")
    previews: list[dict[str, Any]] = []
    for directory in selected:
        value = registry.load_decision_assurance_history_series_release_registry(directory)
        previews.append(
            {
                "directory_name": directory.name,
                "registry_id": value.registry_id,
                "registry_address": value.content_address,
                "entry_count": value.entry_count,
                "accepted": value.accepted_count == value.entry_count,
                "release_ready": value.release_ready_count == value.entry_count,
                "state": "blocked" if value.blocked_count else "held" if value.hold_count else "ready",
            }
        )
    return tuple(previews)


def build_downloaded_gate(
    directories: Sequence[str | Path],
    *,
    federation_id: str = DEFAULT_FEDERATION_ID,
    gate_id: str = DEFAULT_GATE_ID,
) -> tuple[Any, Any]:
    """Build a federation and independent gate from already downloaded data."""

    selected = _unique_directories(directories, "registry directories")
    if not selected:
        raise ValidationError("at least one registry directory is required")
    federation_value = federation.build_federation_from_directories(
        selected,
        federation_id=federation_id,
    )
    gate_value = gate.build_federation_assurance_gate(
        federation_value,
        gate_id=gate_id,
    )
    return federation_value, gate_value


def persist_downloaded_gate(
    directories: Sequence[str | Path],
    output: str | Path,
    *,
    federation_id: str = DEFAULT_FEDERATION_ID,
    gate_id: str = DEFAULT_GATE_ID,
    overwrite: bool = False,
) -> DownloadedGateRun:
    """Persist the exact federation and gate packages for a downloaded run."""

    selected = _unique_directories(directories, "registry directories")
    federation_value, gate_value = build_downloaded_gate(
        selected,
        federation_id=federation_id,
        gate_id=gate_id,
    )
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    federation_directory = output_path / "federation"
    gate_directory = output_path / "gate"
    federation.write_federation(federation_value, federation_directory, overwrite=overwrite)
    gate.write_federation_assurance_gate(gate_value, gate_directory, overwrite=overwrite)
    federation.load_federation(federation_directory)
    gate.load_federation_assurance_gate(gate_directory)
    return DownloadedGateRun(
        root=None,
        registry_directories=selected,
        federation_directory=federation_directory,
        gate_directory=gate_directory,
        federation=federation_value,
        gate=gate_value,
    )


def run_downloaded_gate_demo(
    *,
    root: str | Path | None = None,
    directories: Sequence[str | Path] = (),
    recursive: bool = False,
    output: str | Path = DEFAULT_OUTPUT_DIRECTORY,
    federation_id: str = DEFAULT_FEDERATION_ID,
    gate_id: str = DEFAULT_GATE_ID,
    overwrite: bool = False,
) -> DownloadedGateRun:
    """Discover or select downloaded registries, then persist both closures."""

    if root is not None and directories:
        raise ValidationError("root and explicit registry directories cannot be combined")
    selected = discover_downloaded_registries(root, recursive=recursive) if root is not None else _unique_directories(directories, "registry directories")
    if not selected:
        raise ValidationError("root or at least one explicit registry directory is required")
    run = persist_downloaded_gate(
        selected,
        output,
        federation_id=federation_id,
        gate_id=gate_id,
        overwrite=overwrite,
    )
    return DownloadedGateRun(
        root=None if root is None else Path(root),
        registry_directories=run.registry_directories,
        federation_directory=run.federation_directory,
        gate_directory=run.gate_directory,
        federation=run.federation,
        gate=run.gate,
    )


def render_downloaded_gate(run: DownloadedGateRun, output_format: str = DEFAULT_FORMAT) -> str:
    """Render a run using the same stable exporters exposed by the package."""

    if output_format not in FORMATS:
        raise ValidationError(f"unsupported output format: {output_format}")
    if output_format == "summary":
        return canonical_json(run.summary())
    if output_format == "csv":
        return gate.assurance_gate_csv(run.gate)
    if output_format == "markdown":
        return gate.render_assurance_gate_markdown(run.gate)
    return gate.assurance_gate_json(run.gate)


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the demonstration CLI without hidden environment inputs."""

    parser = argparse.ArgumentParser(description="gate downloaded release-registry packages")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--root", help="download root containing registry packages")
    source.add_argument("--input", action="append", help="one persisted registry package; repeatable")
    parser.add_argument("--recursive", action="store_true", help="search nested download directories")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_DIRECTORY), help="directory receiving federation/ and gate/")
    parser.add_argument("--federation-id", default=DEFAULT_FEDERATION_ID)
    parser.add_argument("--gate-id", default=DEFAULT_GATE_ID)
    parser.add_argument("--allow-existing", action="store_true", help="replace an existing output package")
    parser.add_argument("--format", choices=FORMATS, default=DEFAULT_FORMAT)
    parser.add_argument("--report", default=None, help="optional report file; stdout is used otherwise")
    return parser


def _write_report(text: str, destination: str | None) -> None:
    if destination is None:
        sys.stdout.write(text)
        if not text.endswith("\n"):
            sys.stdout.write("\n")
        return
    report = Path(destination)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the downloaded-data demo and return a release decision status."""

    args = build_argument_parser().parse_args(argv)
    try:
        run = run_downloaded_gate_demo(
            root=args.root,
            directories=tuple(args.input or ()),
            recursive=args.recursive,
            output=args.output,
            federation_id=args.federation_id,
            gate_id=args.gate_id,
            overwrite=args.allow_existing,
        )
        _write_report(render_downloaded_gate(run, args.format), args.report)
        return 0 if run.gate.gate.release_ready else 2
    except (ValidationError, OSError, ValueError) as exc:
        _write_report(canonical_json({"error": "downloaded_gate_demo_failed", "message": str(exc)}), None)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
