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
from .causal_reasoning import FactorGraphConstructor, FactorObservation
from .cell_context import ContextObservationParser
from .chromatin_context import ChromatinTrackKind, ChromatinTrackParser
from .cohort_discovery import CohortQuery, CohortQueryBuilder, CohortVariantRecord
from .control_plane import ClaimCeiling, MissionContext, default_control_plane_registry
from .control_plane_app import ControlPlaneApplication
from .data_sources import PublicReferenceRetriever, default_source_catalog
from .errors import GlioError
from .evidence_lifecycle import (
    CitationResolver,
    EvidenceCitation,
    EvidenceDossierPublisher,
    VersionedEvidenceClaim,
    VersionedEvidenceGraphConstructor,
)
from .intake import IntakeFormat, VariantIntake
from .link_graph import GeneFeatureParser
from .mission_runtime import MissionPlanBuilder, MissionRequest
from .models import CaseManifest, ReferenceContext, VariantIdentity
from .reference_registry import default_reference_registry
from .regulatory_tracks import RegulatoryTrackFormat, RegulatoryTrackParser
from .runtime import CaseRuntime
from .schema import schema_document
from .sequence_adapters import (
    LongContextVariantEffectAdapter,
    SequenceContextEncoder,
    SequenceFoundationModelAdapter,
)
from .specimen_context import PurityPloidyImporter
from .structural_extensions import CopyNumberSegmentHarmonizer, SVConsensusImporter
from .topology_context import (
    ContactMatrixParser,
    TadBoundaryParser,
    TopologyAssay,
)
from .variant_normalization import VRSNormalizer
from .workspace import CaseWorkspaceBuilder, RegulatoryTrackBrowser


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

    citations = subparsers.add_parser(
        "parse-citations", help="parse a versioned citation manifest with quarantine accounting"
    )
    citations.add_argument("input", type=str)
    citations.add_argument("--source-id", default=None)
    citations.add_argument("--source-version", default="unspecified")
    citations.add_argument("--format", choices=("tsv", "csv", "json"), default=None)
    citations.add_argument("--output", default=None)

    evidence_graph = subparsers.add_parser(
        "evidence-graph", help="build and validate an immutable versioned evidence graph"
    )
    evidence_graph.add_argument("input", type=str)
    evidence_graph.add_argument("--context-key", required=True)
    evidence_graph.add_argument("--graph-id", default="evidence-graph")
    evidence_graph.add_argument("--output", default=None)

    workspace_case = subparsers.add_parser(
        "workspace-case", help="build a deterministic case research workspace"
    )
    workspace_case.add_argument("manifest", type=str)
    workspace_case.add_argument("--output", default=None)

    workspace_track = subparsers.add_parser(
        "workspace-track", help="build an exact-context regulatory track workspace"
    )
    workspace_track.add_argument("input", type=str)
    workspace_track.add_argument("--context-key", required=True)
    workspace_track.add_argument("--source-id", default=None)
    workspace_track.add_argument(
        "--format", choices=[item.value for item in RegulatoryTrackFormat], default=None
    )
    workspace_track.add_argument("--genome-build", default="GRCh38")
    workspace_track.add_argument("--output", default=None)

    mission_plan = subparsers.add_parser(
        "mission-plan", help="expand a mission request into a typed plan and compiled workflow"
    )
    mission_plan.add_argument("input", type=str)
    mission_plan.add_argument("--output", default=None)

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

    chromatin = subparsers.add_parser(
        "parse-chromatin", help="parse a context-qualified ATAC, DNase, histone, or H3K27ac track"
    )
    chromatin.add_argument("input", type=str)
    chromatin.add_argument("--source-id", default=None)
    chromatin.add_argument(
        "--track-kind", choices=[item.value for item in ChromatinTrackKind], required=True
    )
    chromatin.add_argument("--format", choices=("tsv", "json"), default=None)
    chromatin.add_argument("--output", default=None)

    context = subparsers.add_parser(
        "parse-context",
        help="parse context-qualified disease, age, molecular, or territory observations",
    )
    context.add_argument("input", type=str)
    context.add_argument("--source-id", default=None)
    context.add_argument("--format", choices=("tsv", "json"), default=None)
    context.add_argument("--output", default=None)

    contacts = subparsers.add_parser(
        "parse-contacts", help="parse a context-qualified Hi-C or Micro-C contact matrix"
    )
    contacts.add_argument("input", type=str)
    contacts.add_argument("--source-id", default=None)
    contacts.add_argument(
        "--assay", choices=[item.value for item in TopologyAssay], required=True
    )
    contacts.add_argument("--format", choices=("tsv", "json"), default=None)
    contacts.add_argument("--output", default=None)

    boundaries = subparsers.add_parser(
        "parse-boundaries", help="parse context-qualified TAD boundary candidates"
    )
    boundaries.add_argument("input", type=str)
    boundaries.add_argument("--source-id", default=None)
    boundaries.add_argument(
        "--assay", choices=[item.value for item in TopologyAssay], required=True
    )
    boundaries.add_argument("--format", choices=("tsv", "json"), default=None)
    boundaries.add_argument("--output", default=None)

    genes = subparsers.add_parser(
        "parse-genes", help="parse context-qualified gene intervals for link baselines"
    )
    genes.add_argument("input", type=str)
    genes.add_argument("--source-id", default=None)
    genes.add_argument("--format", choices=("tsv", "json"), default=None)
    genes.add_argument("--genome-build", default="GRCh38")
    genes.add_argument("--output", default=None)

    factor_graph = subparsers.add_parser(
        "factor-graph", help="construct a replayable factor graph from JSON factors"
    )
    factor_graph.add_argument("input", type=str)
    factor_graph.add_argument("--context-key", required=True)
    factor_graph.add_argument("--graph-id", default="factor-graph")
    factor_graph.add_argument("--output", default=None)

    cohort_query = subparsers.add_parser(
        "cohort-query", help="apply an exact-context cohort query to a JSON record bundle"
    )
    cohort_query.add_argument("input", type=str)
    cohort_query.add_argument("--output", default=None)

    encode_sequence = subparsers.add_parser(
        "encode-sequence", help="emit deterministic sequence context features"
    )
    encode_sequence.add_argument("sequence", type=str)
    encode_sequence.add_argument("--sequence-id", required=True)
    encode_sequence.add_argument("--source-id", default="sequence-cli")
    encode_sequence.add_argument("--kmer-size", type=int, default=3)
    encode_sequence.add_argument("--output", default=None)

    effect = subparsers.add_parser(
        "parse-effect", help="parse a foundation or long-context model output table"
    )
    effect.add_argument("input", type=str)
    effect.add_argument("--source-id", default=None)
    effect.add_argument("--adapter", choices=("foundation", "long-context"), default="foundation")
    effect.add_argument("--output", default=None)
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
        if args.command == "parse-citations":
            input_path = Path(args.input)
            result = CitationResolver().parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
                source_version=args.source_version,
                input_format=args.format,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "evidence-graph":
            payload = _read_json(args.input)
            citations = tuple(
                EvidenceCitation.from_mapping(
                    row,
                    fallback_source_id=str(row.get("source_id", "declared_source")),
                    fallback_version=str(row.get("version", "unspecified")),
                    fallback_row_number=index,
                )
                for index, row in enumerate(payload.get("citations", ()), start=1)
            )
            claims = tuple(
                VersionedEvidenceClaim.from_mapping(
                    row,
                    fallback_id=f"{Path(args.input).stem}:{index}",
                    context_key=args.context_key,
                )
                for index, row in enumerate(payload.get("claims", ()), start=1)
            )
            graph = VersionedEvidenceGraphConstructor().construct(
                claims,
                citations=citations,
                graph_id=args.graph_id,
                context_key=args.context_key,
            )
            _write_json(EvidenceDossierPublisher().publish(graph).to_dict(), args.output)
            return 0
        if args.command == "workspace-case":
            manifest = CaseManifest.from_dict(_read_json(args.manifest))
            _write_json(CaseWorkspaceBuilder().build(manifest).to_dict(), args.output)
            return 0
        if args.command == "workspace-track":
            input_path = Path(args.input)
            batch = RegulatoryTrackParser().parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
                genome_build=args.genome_build,
                input_format=args.format,
            )
            workspace = RegulatoryTrackBrowser().build(batch, context_key=args.context_key)
            _write_json(workspace.to_dict(), args.output)
            return 0
        if args.command == "mission-plan":
            payload = _read_json(args.input)
            raw = dict(payload.get("mission", payload))
            mission = MissionContext(
                mission_id=str(raw.get("mission_id", "mission-cli")),
                project_id=str(raw.get("project_id", "glio-noncode")),
                intended_use=str(raw.get("intended_use", "research hypothesis exploration")),
                requested_question=str(raw.get("requested_question", "bounded research question")),
                claim_ceiling=ClaimCeiling(
                    str(raw.get("claim_ceiling", ClaimCeiling.HYPOTHESIS.value))
                ),
                allowed_source_ids=tuple(str(item) for item in raw.get("allowed_source_ids", ())),
                allowed_data_scopes=tuple(
                    str(item)
                    for item in raw.get("allowed_data_scopes", ("synthetic", "public_reference"))
                ),
                allowed_mutations=tuple(
                    str(item) for item in raw.get(
                        "allowed_mutations", ("none", "event_log", "content_addressed_store")
                    )
                ),
            )
            request = MissionRequest(
                mission=mission,
                requested_agent_ids=tuple(
                    str(item) for item in payload.get("requested_agent_ids", ())
                ),
                workflow_id=str(payload.get("workflow_id", "mission-cli-workflow")),
            )
            _write_json(MissionPlanBuilder().plan(request).to_dict(), args.output)
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
        if args.command == "parse-chromatin":
            input_path = Path(args.input)
            result = ChromatinTrackParser().parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
                track_kind=args.track_kind,
                input_format=args.format,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "parse-context":
            input_path = Path(args.input)
            result = ContextObservationParser().parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
                input_format=args.format,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "parse-contacts":
            input_path = Path(args.input)
            result = ContactMatrixParser().parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
                assay=args.assay,
                input_format=args.format,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "parse-boundaries":
            input_path = Path(args.input)
            result = TadBoundaryParser().parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
                assay=args.assay,
                input_format=args.format,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "parse-genes":
            input_path = Path(args.input)
            result = GeneFeatureParser().parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
                input_format=args.format,
                default_genome_build=args.genome_build,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "factor-graph":
            payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
            rows = payload.get("factors", payload) if isinstance(payload, dict) else payload
            if not isinstance(rows, list):
                raise ValueError("factor graph JSON must contain a factors list")
            factors = tuple(
                FactorObservation.from_mapping(
                    row,
                    fallback_id=f"{Path(args.input).stem}:{index}",
                    context_key=args.context_key,
                )
                for index, row in enumerate(rows, start=1)
            )
            result = FactorGraphConstructor().construct(
                factors, context_key=args.context_key, graph_id=args.graph_id
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "cohort-query":
            payload = _read_json(args.input)
            context = ReferenceContext.from_dict(payload["context"])
            records = tuple(
                CohortVariantRecord(
                    record_id=str(item["record_id"]),
                    variant=VariantIdentity.from_dict(item["variant"]),
                    context_key=str(item.get("context_key", context.key)),
                    source_id=str(item.get("source_id", "cohort-cli")),
                    sample_id=str(item.get("sample_id", "unspecified")),
                    callable=bool(item.get("callable", True)),
                    sequence_context=item.get("sequence_context"),
                    chromatin_features={
                        str(key): float(value)
                        for key, value in dict(item.get("chromatin_features", {})).items()
                    },
                    annotations=dict(item.get("annotations", {})),
                )
                for item in payload.get("records", ())
            )
            query_raw = dict(payload.get("query", {}))
            query = CohortQuery(
                query_id=str(query_raw.get("query_id", "cohort-cli")),
                context_key=str(query_raw.get("context_key", context.key)),
                variant_kinds=tuple(str(item) for item in query_raw.get("variant_kinds", ())),
                origins=tuple(str(item) for item in query_raw.get("origins", ())),
                chromosomes=tuple(str(item) for item in query_raw.get("chromosomes", ())),
                sample_ids=tuple(str(item) for item in query_raw.get("sample_ids", ())),
                require_callable=bool(query_raw.get("require_callable", True)),
            )
            result = CohortQueryBuilder().build(query, records)
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "encode-sequence":
            result = SequenceContextEncoder().encode(
                args.sequence,
                sequence_id=args.sequence_id,
                source_id=args.source_id,
                kmer_size=args.kmer_size,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "parse-effect":
            input_path = Path(args.input)
            adapter = (
                LongContextVariantEffectAdapter()
                if args.adapter == "long-context"
                else SequenceFoundationModelAdapter()
            )
            result = adapter.parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
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
