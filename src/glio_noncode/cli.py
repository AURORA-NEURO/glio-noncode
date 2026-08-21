"""Command-line entry point for local case evaluation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .api import create_server
from .atlas_extensions import CcreAtlasProfile, CcreTrackParser
from .capability_registry import default_capability_registry
from .control_plane import default_control_plane_registry
from .control_plane_app import ControlPlaneApplication
from .data_sources import PublicReferenceRetriever, default_source_catalog
from .errors import GlioError
from .intake import IntakeFormat, VariantIntake
from .models import CaseManifest
from .reference_registry import default_reference_registry
from .regulatory_tracks import RegulatoryTrackFormat, RegulatoryTrackParser
from .runtime import CaseRuntime
from .schema import schema_document
from .specimen_context import PurityPloidyImporter
from .structural_extensions import CopyNumberSegmentHarmonizer, SVConsensusImporter
from .variant_normalization import VRSNormalizer


def _read_json(path: str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("input JSON must be an object")
    return payload


def _write_json(payload: Any, output: str | None) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if output:
        Path(output).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="glio-noncode", description="Inspectable research hypothesis runtime"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    evaluate = subparsers.add_parser("evaluate", help="evaluate a case manifest")
    evaluate.add_argument("manifest", type=str)
    evaluate.add_argument("--data-root", default=".glio")
    evaluate.add_argument("--output", default=None)
    evaluate.add_argument(
        "--live-reference",
        action="store_true",
        help="retrieve bounded sequence and annotation data from public APIs",
    )
    evaluate.add_argument(
        "--window-bp", default=2000, type=int, help="half-window for live reference retrieval"
    )

    fetch_public = subparsers.add_parser(
        "fetch-public", help="retrieve and emit live public reference data for a manifest"
    )
    fetch_public.add_argument("manifest", type=str)
    fetch_public.add_argument("--data-root", default=".glio")
    fetch_public.add_argument("--output", default=None)
    fetch_public.add_argument("--window-bp", default=2000, type=int)

    serve = subparsers.add_parser("serve", help="run the local JSON API")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", default=8765, type=int)
    serve.add_argument("--data-root", default=".glio")

    schema = subparsers.add_parser("schema", help="print the public contract summary")
    schema.add_argument("--output", default=None)

    subparsers.add_parser("sources", help="print the live public source catalog")
    subparsers.add_parser("registry", help="print the bounded control-plane registry")
    subparsers.add_parser("bindings", help="print executable control-plane handler bindings")
    subparsers.add_parser("capabilities", help="print the 256-capability implementation ledger")
    subparsers.add_parser("references", help="print the reference assembly registry")

    intake = subparsers.add_parser("intake", help="canonicalize a VCF, TSV, or JSON variant source")
    intake.add_argument("input", type=str)
    intake.add_argument("--source-id", default=None)
    intake.add_argument("--format", choices=[item.value for item in IntakeFormat], default=None)
    intake.add_argument("--genome-build", default="GRCh38")
    intake.add_argument("--sample-id", default=None)
    intake.add_argument("--include-no-call", action="store_true")
    intake.add_argument("--output", default=None)

    track = subparsers.add_parser(
        "parse-track", help="parse a BED, narrowPeak, GFF3, or JSON regulatory track"
    )
    track.add_argument("input", type=str)
    track.add_argument("--source-id", default=None)
    track.add_argument(
        "--format", choices=[item.value for item in RegulatoryTrackFormat], default=None
    )
    track.add_argument("--genome-build", default="GRCh38")
    track.add_argument("--output", default=None)

    normalize = subparsers.add_parser("normalize", help="emit a VRS-style normalization report")
    normalize.add_argument("notation", type=str)
    normalize.add_argument("--genome-build", default="GRCh38")
    normalize.add_argument("--sequence-digest", default=None)
    normalize.add_argument("--reference-sequence", default=None)
    normalize.add_argument("--reference-start", type=int, default=None)
    normalize.add_argument("--output", default=None)

    sv_consensus = subparsers.add_parser(
        "sv-consensus", help="import and reconcile multi-caller structural observations"
    )
    sv_consensus.add_argument("input", type=str)
    sv_consensus.add_argument("--source-id", default=None)
    sv_consensus.add_argument("--format", choices=("tsv", "json"), default=None)
    sv_consensus.add_argument("--breakpoint-tolerance", type=int, default=10)
    sv_consensus.add_argument("--output", default=None)

    cn = subparsers.add_parser(
        "harmonize-cn", help="harmonize multi-caller copy-number segments"
    )
    cn.add_argument("input", type=str)
    cn.add_argument("--source-id", default=None)
    cn.add_argument("--output", default=None)

    purity = subparsers.add_parser(
        "purity-ploidy", help="import purity and ploidy measurements with source receipts"
    )
    purity.add_argument("input", type=str)
    purity.add_argument("--source-id", default=None)
    purity.add_argument("--format", choices=("tsv", "json"), default=None)
    purity.add_argument("--output", default=None)

    ccre = subparsers.add_parser(
        "parse-ccre", help="parse an ENCODE SCREEN-style cCRE track"
    )
    ccre.add_argument("input", type=str)
    ccre.add_argument("--source-id", default=None)
    ccre.add_argument(
        "--profile", choices=[item.value for item in CcreAtlasProfile], default="encode_screen_ccre"
    )
    ccre.add_argument("--format", choices=("tsv", "json"), default=None)
    ccre.add_argument("--output", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "schema":
            _write_json(schema_document(), args.output)
            return 0
        if args.command == "sources":
            _write_json(default_source_catalog().manifest(), None)
            return 0
        if args.command == "registry":
            _write_json(default_control_plane_registry().manifest(), None)
            return 0
        if args.command == "bindings":
            _write_json(ControlPlaneApplication().manifest(), None)
            return 0
        if args.command == "capabilities":
            _write_json(default_capability_registry().manifest(), None)
            return 0
        if args.command == "references":
            _write_json(default_reference_registry().manifest(), None)
            return 0
        if args.command == "intake":
            input_path = Path(args.input)
            source_id = args.source_id or input_path.stem
            intake_engine = VariantIntake(default_build=args.genome_build)
            if args.format == IntakeFormat.BCF.value or input_path.suffix.lower() == ".bcf":
                batch = intake_engine.parse_bytes(
                    input_path.read_bytes(),
                    source_id=source_id,
                    genome_build=args.genome_build,
                    sample_id=args.sample_id,
                    include_no_call=args.include_no_call,
                )
            else:
                batch = intake_engine.parse_text(
                    input_path.read_text(encoding="utf-8"),
                    source_id=source_id,
                    input_format=args.format,
                    genome_build=args.genome_build,
                    sample_id=args.sample_id,
                    include_no_call=args.include_no_call,
                )
            _write_json(batch.to_dict(), args.output)
            return 0
        if args.command == "parse-track":
            input_path = Path(args.input)
            batch = RegulatoryTrackParser().parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
                genome_build=args.genome_build,
                input_format=args.format,
            )
            _write_json(batch.to_dict(), args.output)
            return 0
        if args.command == "normalize":
            report = VRSNormalizer().normalize(
                args.notation,
                genome_build=args.genome_build,
                sequence_digest=args.sequence_digest,
                reference_sequence=args.reference_sequence,
                reference_start=args.reference_start,
            )
            _write_json(report.to_dict(), args.output)
            return 0
        if args.command == "sv-consensus":
            input_path = Path(args.input)
            batch = SVConsensusImporter(
                breakpoint_tolerance=args.breakpoint_tolerance
            ).parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
                input_format=args.format,
            )
            _write_json(batch.to_dict(), args.output)
            return 0
        if args.command == "harmonize-cn":
            input_path = Path(args.input)
            result = CopyNumberSegmentHarmonizer().parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "purity-ploidy":
            input_path = Path(args.input)
            result = PurityPloidyImporter().parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
                input_format=args.format,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "parse-ccre":
            input_path = Path(args.input)
            result = CcreTrackParser().parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
                profile=args.profile,
                input_format=args.format,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "evaluate":
            manifest = CaseManifest.from_dict(_read_json(args.manifest))
            retriever = (
                PublicReferenceRetriever(
                    cache_root=Path(args.data_root) / "source-cache", window_bp=args.window_bp
                )
                if args.live_reference
                else None
            )
            dossier = CaseRuntime(args.data_root, reference_retriever=retriever).evaluate(
                manifest,
                live_reference=args.live_reference,
            )
            _write_json(dossier.to_dict(), args.output)
            return 0
        if args.command == "fetch-public":
            manifest = CaseManifest.from_dict(_read_json(args.manifest))
            retriever = PublicReferenceRetriever(
                cache_root=Path(args.data_root) / "source-cache",
                window_bp=args.window_bp,
            )
            _write_json(retriever.enrich_manifest(manifest).to_dict(), args.output)
            return 0
        if args.command == "serve":
            server = create_server(args.host, args.port, args.data_root)
            print(f"glio-noncode listening on http://{args.host}:{args.port}")
            server.serve_forever()
            return 0
    except (GlioError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 1
