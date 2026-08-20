"""Command-line entry point for local case evaluation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .api import create_server
from .control_plane import default_control_plane_registry
from .data_sources import PublicReferenceRetriever, default_source_catalog
from .errors import GlioError
from .models import CaseManifest
from .runtime import CaseRuntime
from .schema import schema_document


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
